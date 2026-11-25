"""在隔离目录中验收同批 SignalR 与 Log4Net 候选。"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from r2_assets import identity_text
from r2_packages import NUGET_SOURCE, SDK, verify_source, version_range, write_json
from r2_verify import ERRORS, environment
from r3_leaf_assets import (APP, TARGET, check_assets, check_log4net, check_log4net_compile, check_output,
                            check_runtime, check_signalr)
from r3_leaf_packages import (CASTLE, CORE, LOG4NET, R2_IDS, R2_VERSION, R3_IDS, SOURCE_PROOF, TFM,
                              checked_file, read_leaf, read_r2, verify_production, verify_restore_config)
from r3_web_host import inside, runtime_selection
from verify import ROOT, TOOLS, R0Run, VerificationError, make_run_directory, read_json, require, sha256


PROFILE = "r3-signalr-log4net"
STAGES = ("preflight", "packages", "restore", "assets", "build", "output", "host", "signalr", "log4net", "runtime")
FILES = ("global.json", "SignalRLog4Net.csproj", "Program.cs")


class IntegrationRun(R0Run):
    def __init__(self, evidence, dotnet, strict_runtime_baseline=False):
        self.repo, self.evidence, self.dotnet = ROOT, evidence, dotnet
        self.report_path = evidence / "report.json"
        self.work = evidence / "consumer"
        self.project = self.work / FILES[1]
        self.cache = self.work / "packages"
        self.assets_path = self.work / "obj/project.assets.json"
        self.output = self.work / "bin" / "Release" / TFM
        self.env = environment(self.work, self.dotnet)
        self.metadata_tool = evidence / "tools/metadata/bin/Release/net10.0/R2Metadata.dll"
        self.strict_runtime_baseline = strict_runtime_baseline
        self.feeds = {}
        self.packages = {}
        self.report = {
            "profile": PROFILE, "status": "running", "exitCode": None, "command": [sys.executable, *sys.argv],
            "cwd": str(Path.cwd()), "startedAt": datetime.now(timezone.utc).isoformat(),
            "environment": {"macOS": platform.mac_ver()[0], "os": platform.system(),
                            "architecture": platform.machine(), "dotnet": str(dotnet)},
            "inputs": {},
            "stages": {stage: {"status": "not_run", "exitCode": None, "commands": [], "evidence": []}
                       for stage in STAGES},
            "scope": {"verifiedTarget": TFM, "host": "Kestrel 回环独立宿主",
                      "excluded": ["完整模板", "真实登录", "数据库", "Angular", "其他平台与目标", "发布", "CI", "部署"]},
        }
        self.save()

    def preflight(self, feed, manifest_path, symbols, r2_feed):
        require(platform.system() == "Darwin" and platform.machine() == "arm64", "当前实测组合需要 macOS ARM64")
        require(self.dotnet.is_file() and os.access(self.dotnet, os.X_OK), f"缺少可执行文件 {self.dotnet}")
        dotnet_file = self.read_command(["file", self.dotnet], self.repo, "dotnet-file.log")
        require("Mach-O" in dotnet_file and "arm64" in dotnet_file, f"dotnet 实物不是 macOS ARM64：{dotnet_file}")
        self.report["environment"]["dotnetSha256"] = sha256(self.dotnet)
        for directory in (feed, symbols, r2_feed):
            require(directory.is_dir(), f"缺少输入目录 {directory}")
        location = manifest_path.parent
        declared = read_json(manifest_path)
        self.version = declared["version"]
        registrations = self.repo / "eng/r3_leaf_reference.json"
        self.registration = read_json(registrations).get(self.version)
        require(self.registration and re.fullmatch(r"10\.5\.1-r3\.[1-9][0-9]*", self.version),
                f"未登记候选批次 {self.version}")
        self.report["inputs"].update({"candidateManifest": str(manifest_path), "manifestSha256": sha256(manifest_path),
                                      "registrationSha256": sha256(registrations), "r2Feed": str(r2_feed),
                                      "candidateFeed": str(feed), "candidateSymbols": str(symbols)})
        checked_file(location, manifest_path.name, self.registration["manifestSha256"])
        require(declared["schemaVersion"] == 1 and declared["sdk"] == SDK, "生产清单格式或 SDK 不符")
        if self.strict_runtime_baseline:
            self.report["environment"]["requiredSharedRuntimeVersion"] = self.registration["runtimeVersion"]
        self.declared = declared
        self.source = verify_source(self, manifest_path, declared)
        current = self.git_inputs("consumer")
        template = self.git(self.repo, "consumer-template-gitlink.log", "ls-tree", current["head"],
                            "--", "module-zero-core-template")
        expected_template = self.registration["templateGitlink"]
        require(template == f"160000 commit {expected_template}\tmodule-zero-core-template",
                "实际主仓模板 gitlink 与原版参照不符")
        proof_path = checked_file(location, SOURCE_PROOF, self.registration["sourceProofSha256"])
        require(read_json(proof_path) == declared["sourceProof"], "独立源码证明与清单不符")
        self.report["inputs"].update({"source": self.source, "producerSuperproject": declared["superproject"],
                                      "consumerSuperproject": current, "templateGitlink": expected_template,
                                      "sourceProofPath": str(proof_path),
                                      "sourceProofSha256": sha256(proof_path)})
        self.work.mkdir()
        for name in FILES:
            shutil.copy2(self.repo / "validation/signalr-log4net" / name, self.work)
        self.report["inputs"]["consumerFiles"] = {name: sha256(self.work / name) for name in FILES}
        xml = ET.parse(self.project)
        require(xml.getroot().get("Sdk") == "Microsoft.NET.Sdk.Web" and
                not any(xml.findall(f".//{tag}") for tag in
                        ("ProjectReference", "Reference", "HintPath", "Import", "FrameworkReference")),
                "消费项目应仅通过 Web SDK 和 NuGet 包接入框架")
        self.run_dotnet(["--version"], "sdk.log")
        self.report["environment"]["sdk"] = (self.evidence / "sdk.log").read_text().strip()
        require(self.report["environment"]["sdk"] == SDK, f"实际所选 .NET SDK 须为 {SDK}")
        self.run_dotnet(["--info"], "dotnet-info.log")

    def verify_packages(self, feed, manifest_path, symbols, r2_feed):
        declared = self.declared
        require(set(declared["packages"]) == set(declared["production"]) == set(R3_IDS), "R3 候选或生产项集合不符")
        reference_path = self.repo / "eng/r3_r2_reference.json"
        reference = read_json(reference_path)
        require(reference["version"] == R2_VERSION and reference["frameworkTree"] == self.source["baseTree"],
                "R2 版本或生产框架对照树与登记不符")
        self.packages.update({name: read_r2(r2_feed, reference, name) for name in R2_IDS})
        core = self.packages[CORE]
        require(declared["r2Core"] == {"id": CORE, "version": R2_VERSION, "archiveFile": Path(core["archive"]).name,
                                      "archiveSha256": core["archiveSha256"], "assetPath": core["asset"],
                                      "assetSha256": core["assetSha256"]}, "生产清单的 R2 核心与主仓登记不符")
        for name, entry in declared["packages"].items():
            path = checked_file(feed, f"{name}.{self.version}.nupkg", entry["package"]["sha256"])
            symbol = checked_file(symbols, f"{name}.{self.version}.snupkg", entry["symbols"]["sha256"])
            require((path.name, symbol.name) == (entry["package"]["file"], entry["symbols"]["file"]),
                    f"{name} 清单归档文件名不符")
            self.packages[name] = read_leaf(path, symbol, name, self.version, entry, self.source, declared["sourceProof"])
        self.production = {name: verify_production(manifest_path.parent, declared, self.packages, name)
                           for name in R3_IDS}
        config = verify_restore_config(manifest_path.parent, declared, self.production)
        write_json(self.evidence_file("candidate.json"), {"source": self.source, "r2ReferenceSha256": sha256(reference_path),
                   "packages": self.packages, "production": self.production, "productionRestore": config})
        self.verify_template_reference()
        self.prepare_sources()

    def verify_template_reference(self):
        path = self.repo / "docs/maintenance/r3-web-host-baseline.json"
        baseline = read_json(path)
        host, = (details[TFM] for name, details in baseline["projects"].items() if name.endswith(".Web.Host.csproj"))
        packages = {entry["id"]: entry for entry in host["packages"]}
        original = {name: entry for name, entry in packages.items()
                    if name in (CASTLE.removeprefix("Du."), "Abp.AspNetCore.SignalR", LOG4NET)}
        require(baseline["templateCommit"] == self.registration["templateGitlink"] and
                {name: entry["version"] for name, entry in original.items()} ==
                {"Abp.Castle.Log4Net": "10.2.0", "Abp.AspNetCore.SignalR": "10.2.0", LOG4NET: "3.1.0"} and
                original["Abp.Castle.Log4Net"]["dependencies"][LOG4NET] == "3.1.0",
                "原版 Web.Host 基线的 Log4Net 或框架身份不符")
        self.original = {"path": str(path), "sha256": sha256(path), "packages": original}

    def prepare_sources(self):
        self.feeds = {R2_VERSION: self.work / "feed-r2", self.version: self.work / "feed-r3"}
        config = ET.Element("configuration")
        sources = ET.SubElement(config, "packageSources")
        mapping = ET.SubElement(config, "packageSourceMapping")
        for section in (sources, mapping, ET.SubElement(config, "fallbackPackageFolders")):
            ET.SubElement(section, "clear")
        for index, (version, ids) in enumerate(((R2_VERSION, R2_IDS), (self.version, R3_IDS)), start=2):
            target = self.feeds[version]
            target.mkdir()
            key = f"r{index}"
            ET.SubElement(sources, "add", key=key, value=str(target))
            source = ET.SubElement(mapping, "packageSource", key=key)
            for name in ids:
                entry = self.packages[name]
                copy = Path(shutil.copy2(entry["archive"], target))
                require(sha256(copy) == entry["archiveSha256"], f"{name} 受控源复制字节不符")
                ET.SubElement(source, "package", pattern=name)
        ET.SubElement(sources, "add", key="nuget.org", value=NUGET_SOURCE)
        ET.SubElement(ET.SubElement(mapping, "packageSource", key="nuget.org"), "package", pattern="*")
        ET.indent(config)
        ET.ElementTree(config).write(self.evidence_file("consumer/NuGet.Config"), encoding="utf-8", xml_declaration=True)

    def run_dotnet(self, args, log, **kwargs):
        return self.command([self.dotnet, *args], self.work, log, extra_env=self.env, **kwargs)

    @property
    def build_properties(self):
        return ["-p:Configuration=Release", f"-p:R3CandidateVersion={self.version}", "-p:UseSharedCompilation=false"]

    def restore(self):
        empty = {}
        for key in ("NUGET_PACKAGES", "NUGET_HTTP_CACHE_PATH", "NUGET_PLUGINS_CACHE_PATH"):
            folder = Path(self.env[key])
            require(not folder.exists() or not any(folder.iterdir()), f"还原前缓存必须为空：{folder}")
            empty[key] = str(folder)
        self.report["emptyCachesBeforeRestore"] = empty
        self.run_dotnet(["restore", self.project, "--configfile", self.work / "NuGet.Config",
                         "--no-http-cache", "--force", "--verbosity", "normal", *self.build_properties], "restore.log")
        self.evidence_file("consumer/obj/project.assets.json")
        self.restored_sha256 = sha256(self.assets_path)

    def build_tool(self, name, project, sources):
        folder = self.evidence / "tools" / name
        folder.mkdir(parents=True)
        for file in (project, "Program.cs"):
            shutil.copy2(sources / file, folder)
        shutil.copy2(self.work / "global.json", folder)
        self.command([self.dotnet, "build", folder / project, "-c", "Release", "--disable-build-servers"],
                     folder, f"build-tool-{name}.log", extra_env=environment(folder, self.dotnet))

    def satisfies_range(self, version, constraint):
        _, log = self.run_dotnet([self.metadata_tool, "--satisfies-range", version, version_range(constraint)],
                                 "log4net-range.log")
        return read_json(log) is True

    def read_assets(self):
        self.build_tool("metadata", "R2Metadata.csproj", self.repo / "eng/r2-metadata")
        self.assets = check_assets(read_json(self.assets_path), self.project, self.cache, self.feeds,
                                   self.packages, self.satisfies_range)
        write_json(self.evidence_file("assets-inventory.json"), self.assets)
        write_json(self.evidence_file("template-dependencies.json"), {
            "original": self.original,
            "maintenance": compare_log4net(self.production[CASTLE]["log4net"], self.assets)})
        self.report["restoreAssetsSha256"] = self.restored_sha256
        self.report["resolvedPackages"] = len(self.assets["packages"])

    def build(self):
        self.run_dotnet(["build", self.project, "--no-restore", "--disable-build-servers",
                         "--verbosity", "minimal", *self.build_properties], "build.log")
        require(sha256(self.assets_path) == self.restored_sha256, "Release 构建改写了原始还原资产")

    def verify_output(self):
        self.run_dotnet(["msbuild", self.project, "-nologo", *self.build_properties,
                         "-target:ResolveLockFileCopyLocalFiles;_HandlePackageFileConflicts",
                         "-getItem:ReferenceCopyLocalPaths"], "runtime-selection.log")
        selection = runtime_selection(read_json(self.evidence / "runtime-selection.log")["Items"], self.assets, self.cache)
        require(sha256(self.assets_path) == self.restored_sha256, "运行复制项求值改写了还原资产")
        write_json(self.evidence_file("runtime-selection.json"), selection)
        for suffix in ("dll", "deps.json", "runtimeconfig.json"):
            self.evidence_file(f"consumer/bin/Release/{TFM}/{APP}.{suffix}")
        self.output_dlls = check_output(self.output, self.assets, selection)
        self.run_dotnet(["msbuild", self.project, "-nologo", *self.build_properties,
                         "-target:ResolveReferences", "-getItem:ReferencePath"], "compile-selection.log")
        compile_selection = check_log4net_compile(read_json(self.evidence / "compile-selection.log")["Items"],
                                                  self.assets, self.cache)
        require(sha256(self.assets_path) == self.restored_sha256, "编译引用求值改写了还原资产")
        self.inspect_assemblies(compile_selection)
        write_json(self.evidence_file("output.json"), self.output_dlls)

    def inspect_assemblies(self, compile_selection):
        self.build_tool("api", "ApiInventory.csproj", self.repo / TOOLS)
        api = self.evidence / "tools/api/bin/Release/net9.0/ApiInventory.dll"
        files = [self.output / dll for dll in self.output_dlls]
        log4net = self.assets["log4net"]
        package = self.assets["packages"][log4net["package"]]
        runtime_asset = inside(self.cache, Path(package["cachePath"]) / log4net["selectedAssets"]["runtime"]["asset"])
        compile_asset = Path(compile_selection["path"])
        inspect = list(dict.fromkeys([*files, compile_asset, runtime_asset]))
        _, info = self.run_dotnet([self.metadata_tool, *inspect], "assembly-targets.log")
        targets = {entry["path"]: entry["targets"] for entry in map(json.loads, info.read_text().splitlines())}
        require(all(len(targets[str(path)]) == 1 and targets[str(path)][0] for path in (compile_asset, runtime_asset)),
                f"{log4net['package']} 选中资产缺少唯一 TargetFrameworkAttribute")
        for path in files:
            dll = path.name
            target = targets[str(runtime_asset)][0] if dll == "log4net.dll" else TARGET
            require(targets.get(str(path)) == [target], f"{dll} 实际 TargetFrameworkAttribute 预期 {target}")
            _, log = self.run_dotnet([api, path], f"assembly-{dll}.json")
            inventory = read_json(log)
            assembly = inventory["assembly"]
            require(assembly["name"] == path.stem and
                    (dll == "log4net.dll" or assembly["version"] == "10.5.1.0") and
                    self.output_dlls[dll]["sha256"] == inventory["sha256"],
                    f"{dll} 实际程序集身份或摘要不符")
            self.output_dlls[dll].update(identity=identity_text(assembly), target=target, path=str(path))
        comparison = self.evidence / "template-dependencies.json"
        detail = read_json(comparison)
        detail["maintenance"]["selectedCompile"] = {**compile_selection, "target": targets[str(compile_asset)][0]}
        detail["maintenance"]["selectedRuntime"] = self.output_dlls["log4net.dll"]
        write_json(comparison, detail)

    def host(self, output=None, timeout=40):
        output = output or self.output
        host_dir = self.evidence / "host"
        host_dir.mkdir()
        env = {**self.env, "ASPNETCORE_ENVIRONMENT": "Production", "DOTNET_ENVIRONMENT": "Production"}
        env["NO_PROXY"] = ",".join(filter(None, (os.environ.get("NO_PROXY"), "127.0.0.1", "localhost")))
        args = [str(self.dotnet), str(output / f"{APP}.dll")]
        log = self.evidence_file("host/host.log")
        record = {"argv": args, "cwd": str(host_dir), "log": "host/host.log", "exitCode": None, "timeoutSeconds": timeout}
        self.stage["commands"].append(record)
        self.report["hostProcess"] = record
        with log.open("wb") as stream, subprocess.Popen(
                args, cwd=host_dir, env=os.environ | env, stdout=stream, stderr=subprocess.STDOUT) as host:
            record["pid"] = host.pid
            self.save()
            try:
                host.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                record["timedOut"] = True
                self.stop_host(host, record)
            except BaseException:
                self.stop_host(host, record)
                raise
            finally:
                record.update(exitCode=host.returncode, reaped=host.poll() is not None)
                if (host_dir / "host.json").is_file():
                    self.evidence_file("host/host.json")
                for name in ("castle.log", "log4net.config"):
                    if (host_dir / name).is_file():
                        self.evidence_file(f"host/{name}")
                self.save()
        path = host_dir / "host.json"
        evidence = read_json(path) if path.is_file() else {}
        record["shutdown"] = evidence.get("shutdown", {})
        require(not record.get("timedOut"), f"Kestrel 宿主超时并已等候退出，详见 {log}")
        require(record["exitCode"] == 0 and not evidence.get("failure"),
                f"Kestrel 宿主退出码 {record['exitCode']}：{evidence.get('failure') or log}")
        require(re.fullmatch(r"http://127\.0\.0\.1:[1-9][0-9]*", evidence.get("address", "")) and
                record["shutdown"].get("hostStopped") is True and record["shutdown"].get("clientStopped") is True,
                f"缺少实际 Kestrel 回环连接或停机记录：{path}")
        self.host_evidence = evidence

    @staticmethod
    def stop_host(host, record):
        if host.poll() is None:
            host.terminate()
            record["termination"] = "SIGTERM"
            try:
                host.wait(timeout=8)
            except subprocess.TimeoutExpired:
                host.kill()
                record["termination"] = "SIGKILL"
                host.wait()

    def signalr(self):
        write_json(self.evidence_file("notification.json"), check_signalr(self.host_evidence))

    def log4net(self):
        write_json(self.evidence_file("logging.json"), check_log4net(self.host_evidence, self.evidence / "host"))

    def runtime(self):
        runtime = check_runtime(self.host_evidence, self.output, self.output_dlls, self.dotnet,
                                self.report["hostProcess"]["pid"])
        write_json(self.evidence_file("runtime.json"), runtime)
        observed = {name: info["version"] for name, info in runtime["shared"].items()}
        self.report["environment"]["loadedSharedRuntimeVersions"] = observed
        if self.strict_runtime_baseline:
            expected = self.registration["runtimeVersion"]
            require(set(observed.values()) == {expected},
                    f"严格复现要求两个共享运行时均为 {expected}，实际 {observed}")
        comparison = self.evidence / "template-dependencies.json"
        detail = read_json(comparison)
        detail["maintenance"]["loaded"] = runtime["assemblies"][LOG4NET]
        write_json(comparison, detail)

    def run_stages(self, stages):
        try:
            for name, action, args in stages:
                self.step(name, action, *args)
        except ERRORS as error:
            self.report.update(status="failed", exitCode=1, reason=str(error))
            if self.stage["status"] == "running":
                self.stage.update(status="failed", exitCode=1, reason=str(error))
            for stage in self.report["stages"].values():
                if stage["status"] == "not_run":
                    stage["reason"] = str(error)
            print(f"{PROFILE} 验收失败：{error}", file=sys.stderr)
        else:
            self.report.update(status="passed", exitCode=0)
        self.report["finishedAt"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return self.report["exitCode"]

    def execute(self, feed, manifest, symbols, r2_feed):
        inputs = (feed, manifest, symbols, r2_feed)
        return self.run_stages([("preflight", self.preflight, inputs), ("packages", self.verify_packages, inputs),
                                ("restore", self.restore, ()), ("assets", self.read_assets, ()), ("build", self.build, ()),
                                ("output", self.verify_output, ()), ("host", self.host, ()), ("signalr", self.signalr, ()),
                                ("log4net", self.log4net, ()), ("runtime", self.runtime, ())])


def compare_log4net(production, assets):
    selected = assets["log4net"]
    differences = {}
    for component, before, now in (
            ("version", production["resolvedVersion"], selected["version"]),
            *((section, list(production["assets"][section]), [selected["selectedAssets"][section]["asset"]])
              for section in ("compile", "runtime"))):
        if before != now:
            differences[component] = {"production": before, "consumer": now}
    return {"sourceDeclaration": production["declaredVersion"], "production": production,
            "dependencyEdge": selected, "package": assets["packages"][selected["package"]],
            "differences": differences,
            "impact": ("消费选择与生产不同，验收范围以本轮构建和实际加载为准" if differences
                       else "消费包版本及资产路径与生产一致")}


def execute(args):
    run = IntegrationRun(make_run_directory(args.evidence_root, f"{PROFILE}-"), args.dotnet.resolve(),
                         args.strict_runtime_baseline)
    print(f"{PROFILE} report: {run.report_path}", flush=True)
    return run.execute(*(path.resolve() for path in (args.candidate_feed, args.candidate_manifest,
                                                      args.candidate_symbols, args.r2_feed)))
