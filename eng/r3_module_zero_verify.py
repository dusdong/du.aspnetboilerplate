"""从冻结实包复验经典 Module Zero 的 SQLite 消费。"""

from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from uuid import uuid4
import xml.etree.ElementTree as ET

from r2_packages import NUGET_SOURCE, SDK, write_json
from r2_verify import ERRORS, environment
from r3_leaf_packages import R2_VERSION, TFM, checked_file
from r3_module_zero_assets import APP, check_assets, check_output, check_runtime
from r3_module_zero_packages import R2_IDS, R3_IDS, verify_packages
from r3_module_zero_roles import check_roles
from verify import ROOT, R0Run, make_run_directory, read_json, require, sha256


PROFILE = "r3-module-zero"
STAGES = ("preflight", "packages", "restore", "assets", "build", "output", "process", "roles", "runtime", "inputs")
FILES = ("global.json", f"{APP}.csproj", "ProbeModule.cs", "Program.cs", "RuntimeEvidence.cs")
REFERENCE = "eng/r3_module_zero_reference.json"


class ModuleZeroRun(R0Run):
    def __init__(self, evidence, dotnet, strict):
        self.repo, self.evidence, self.dotnet = ROOT, evidence, dotnet
        self.report_path = evidence / "report.json"
        self.work = evidence / "consumer"
        self.project = self.work / f"{APP}.csproj"
        self.cache = self.work / "packages"
        self.assets_path = self.work / "obj/project.assets.json"
        self.output = self.work / "bin/Release" / TFM
        self.env = {**environment(self.work, dotnet), "MSBUILDDISABLENODEREUSE": "1"}
        self.strict = strict
        self.report = {
            "profile": PROFILE, "status": "running", "exitCode": None, "command": [sys.executable, *sys.argv],
            "cwd": str(Path.cwd()), "startedAt": datetime.now(timezone.utc).isoformat(),
            "environment": {"os": platform.system(), "macOS": platform.mac_ver()[0],
                            "architecture": platform.machine(), "dotnet": str(dotnet),
                            "runtimeMode": "strict" if strict else "ordinary"},
            "inputs": {},
            "stages": {name: {"status": "not_run", "exitCode": None, "commands": [], "evidence": []} for name in STAGES},
            "scope": {"target": TFM, "platform": "macOS ARM64", "provider": "SQLite",
                      "excluded": ["SQL Server", "真实登录", "完整模板", "Angular",
                                   "其他平台与目标", "公开发包", "CI", "部署"]},
        }
        self.save()

    def run_dotnet(self, args, log, **kwargs):
        return self.command([self.dotnet, *args], self.work, log, extra_env=self.env, **kwargs)

    @property
    def properties(self):
        return ["-p:Configuration=Release", f"-p:R3CandidateVersion={self.version}",
                "-p:UseSharedCompilation=false", "-p:RestoreFallbackFolders="]

    def preflight(self, manifest_path, feed, symbols, r2_feed):
        self.report["inputs"].update(candidateManifest=str(manifest_path), candidateFeed=str(feed),
                                     candidateSymbols=str(symbols), r2Feed=str(r2_feed))
        candidate = read_json(manifest_path)
        self.version = candidate["version"]
        reference = self.repo / REFERENCE
        registration = read_json(reference).get(self.version)
        require(registration and re.fullmatch(r"10\.5\.1-r3\.[1-9][0-9]*", self.version),
                f"未登记冻结批次 {self.version}")
        checked_file(manifest_path.parent, manifest_path.name, registration["manifestSha256"])
        self.report["inputs"].update(candidateVersion=self.version, manifestSha256=sha256(manifest_path),
                                     registrationSha256=sha256(reference), git=self.git_inputs("consumer"))
        self.registration, self.declared = registration, candidate
        self.required_runtime = registration["strictRuntimeVersion"] if self.strict else None
        require(platform.system() == "Darwin" and platform.machine() == "arm64",
                "当前 Module Zero 复验实现要求 macOS ARM64")
        require(self.dotnet.is_file() and os.access(self.dotnet, os.X_OK), f"缺少 .NET 可执行文件 {self.dotnet}")
        executable = self.read_command(["file", self.dotnet], self.repo, "dotnet-file.log")
        require("Mach-O" in executable and "arm64" in executable, f"dotnet 实物应为 macOS ARM64：{executable}")
        self.prepare_project()
        for args, log in ((["--version"], "sdk.log"), (["--info"], "dotnet-info.log"),
                          (["--list-runtimes"], "dotnet-runtimes.log")):
            self.run_dotnet(args, log)
        sdk = (self.evidence / "sdk.log").read_text().strip()
        self.report["environment"].update(sdk=sdk, dotnetSha256=sha256(self.dotnet),
                                          requiredSharedRuntime=self.required_runtime)
        require(sdk == SDK, f"消费项目实际选用 SDK 应为 {SDK}，实际 {sdk}")

    def prepare_project(self):
        self.work.mkdir()
        self.project_sources = {name: self.repo / "validation/module-zero" / name for name in FILES}
        self.report["inputs"]["consumerSourceSha256"] = {
            name: sha256(path) for name, path in self.project_sources.items()}
        for source in self.project_sources.values():
            shutil.copyfile(source, self.work / source.name)
        project_xml = ET.parse(self.project).getroot()
        require(all(project_xml.find(f".//{item}") is None for item in
                    ("ProjectReference", "Reference", "HintPath", "Import", "FrameworkReference")),
                "消费项目应仅通过 NuGet 接入框架")

    def packages(self, manifest_path, feed, symbols, r2_feed):
        self.candidate = verify_packages(self, manifest_path, self.declared, self.registration, feed, symbols, r2_feed)
        write_json(self.evidence_file("candidate.json"), self.candidate)
        self.prepare_sources(self.candidate["packages"])

    def prepare_sources(self, packages, missing=None):
        self.feeds = {R2_VERSION: self.work / "feed-r2", self.version: self.work / "feed-r3"}
        config = ET.Element("configuration")
        sources = ET.SubElement(config, "packageSources")
        mapping = ET.SubElement(config, "packageSourceMapping")
        for section in (sources, mapping, ET.SubElement(config, "fallbackPackageFolders")):
            ET.SubElement(section, "clear")
        for label, version, ids in (("r2", R2_VERSION, R2_IDS), ("r3", self.version, R3_IDS)):
            feed = self.feeds[version]
            feed.mkdir()
            ET.SubElement(sources, "add", key=label, value=str(feed))
            source = ET.SubElement(mapping, "packageSource", key=label)
            for name in ids:
                ET.SubElement(source, "package", pattern=name)
                if name != missing:
                    record = packages[name]
                    copied = Path(shutil.copyfile(record["archive"], feed / Path(record["archive"]).name))
                    require(sha256(copied) == record["archiveSha256"], f"{name} 受控源复制字节不符")
        ET.SubElement(sources, "add", key="nuget.org", value=NUGET_SOURCE)
        ET.SubElement(ET.SubElement(mapping, "packageSource", key="nuget.org"), "package", pattern="*")
        ET.indent(config)
        ET.ElementTree(config).write(self.evidence_file("consumer/NuGet.Config"), encoding="utf-8", xml_declaration=True)

    def restore(self):
        caches = {name: self.env[name] for name in ("NUGET_PACKAGES", "NUGET_HTTP_CACHE_PATH", "NUGET_PLUGINS_CACHE_PATH")}
        require(all(not Path(path).exists() or not any(Path(path).iterdir()) for path in caches.values()),
                "还原前必须使用独立空缓存")
        self.report["emptyCachesBeforeRestore"] = caches
        try:
            self.run_dotnet(["restore", self.project, "--configfile", self.work / "NuGet.Config",
                             "--no-http-cache", "--force", "--verbosity", "normal", *self.properties], "restore.log")
        finally:
            if self.assets_path.is_file():
                self.evidence_file("consumer/obj/project.assets.json")
        self.assets_digest = sha256(self.assets_path)

    def assets(self):
        self.inventory = check_assets(read_json(self.assets_path), self.project, self.cache, self.feeds,
                                      self.candidate["packages"])
        write_json(self.evidence_file("assets-inventory.json"), self.inventory)

    def build(self):
        self.run_dotnet(["build", self.project, "--no-restore", "--disable-build-servers",
                         "--verbosity", "minimal", f"-bl:{self.evidence_file('build.binlog')}",
                         *self.properties], "build.log")

    def verify_output(self):
        self.run_dotnet(["msbuild", self.project, "-nologo", *self.properties,
                         "-target:ResolveReferences", "-getItem:ReferencePath"], "compile-selection.log")
        self.run_dotnet(["msbuild", self.project, "-nologo", *self.properties,
                         "-target:ResolveLockFileCopyLocalFiles;_HandlePackageFileConflicts",
                         "-getItem:ReferenceCopyLocalPaths"], "runtime-selection.log")
        require(sha256(self.assets_path) == self.assets_digest, "Release 构建或引用求值改写了原始还原资产")
        for suffix in ("dll", "deps.json", "runtimeconfig.json"):
            self.evidence_file(f"consumer/bin/Release/{TFM}/{APP}.{suffix}")
        self.outputs = check_output(self.output, self.inventory, self.cache,
                                   read_json(self.evidence / "compile-selection.log")["Items"],
                                   read_json(self.evidence / "runtime-selection.log")["Items"])
        write_json(self.evidence_file("output.json"), self.outputs)

    def probe(self):
        work = self.evidence / "probe"
        work.mkdir()
        self.marker = uuid4().hex
        self.database = work / "roles.sqlite"
        self.probe_path = work / "probe.json"
        argv = [str(self.dotnet), str(self.output / f"{APP}.dll"), self.marker]
        log = self.evidence_file("probe/process.log")
        record = {"argv": argv, "cwd": str(work), "environmentOverrides": self.env, "log": "probe/process.log",
                  "exitCode": None, "timeoutSeconds": 60}
        self.stage["commands"].append(record)
        self.report["process"] = record
        with log.open("wb") as stream, subprocess.Popen(
                argv, cwd=work, stdout=stream, stderr=subprocess.STDOUT, env=os.environ | self.env) as process:
            record["pid"] = process.pid
            self.save()
            try:
                process.wait(timeout=record["timeoutSeconds"])
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                record["timedOut"] = True
            finally:
                record.update(exitCode=process.returncode, reaped=process.returncode is not None)
                for path in (self.probe_path, self.database):
                    if path.is_file():
                        self.evidence_file(path.relative_to(self.evidence).as_posix())
            require(record["exitCode"] == 0 and not record.get("timedOut"),
                    f"消费进程未正常结束（退出码 {record['exitCode']}）：{log}")
        require(self.probe_path.is_file(), "消费进程退出 0 但缺少 probe.json")
        self.observed = read_json(self.probe_path)

    def roles(self):
        roles = check_roles(self.observed, self.database, self.marker)
        write_json(self.evidence_file("roles-verified.json"), roles)

    def runtime(self):
        runtime = check_runtime(self.observed["runtime"], self.dotnet, self.report["process"]["pid"],
                                self.output, self.inventory, self.outputs, self.cache)
        write_json(self.evidence_file("runtime-verified.json"), runtime)
        self.report["environment"]["actualSharedRuntimes"] = runtime["shared"]
        versions = {name: record["version"] for name, record in runtime["shared"].items()}
        if self.required_runtime:
            require(set(versions.values()) == {self.required_runtime},
                    f"严格运行时要求两项均为 {self.required_runtime}，实际 {versions}")

    def verify_inputs(self, manifest_path):
        root = manifest_path.parent
        hashes = {manifest_path: self.registration["manifestSha256"],
                  root / "source.patch": self.declared["sourceProof"]["patchSha256"],
                  root / "du-r3-candidate-source.json": self.registration["sourceProofSha256"]}
        r2_manifest = Path(self.candidate["r2Manifest"])
        hashes.update({r2_manifest: self.declared["r2"]["manifestSha256"],
                       r2_manifest.parent / "source.patch": self.candidate["r2Source"]["patchSha256"],
                       r2_manifest.parent / "du-core-candidate-source.json": self.candidate["r2ProofSha256"]})
        for items in [*self.declared["production"].values(),
                      {key: self.declared["restore"][key] for key in ("config", "commands")}]:
            hashes.update({root / item["path"]: item["sha256"] for item in items.values()})
        for name, info in self.candidate["packages"].items():
            for key in ("archive", "symbol"):
                if key in info:
                    hashes[Path(info[key])] = info[f"{key}Sha256"]
            require(sha256(self.feeds[info["version"]] / Path(info["archive"]).name) == info["archiveSha256"],
                    f"{name} 受控源实物字节在消费期间改变")
        require(sha256(self.assets_path) == self.assets_digest, "还原资产在消费期间改变")
        for name, source in self.project_sources.items():
            expected = self.report["inputs"]["consumerSourceSha256"][name]
            require(sha256(source) == sha256(self.work / name) == expected, f"{name} 源码在消费期间改变")
        for path, digest in hashes.items():
            require(sha256(path) == digest, f"冻结输入在消费期间改变：{path}")
        write_json(self.evidence_file("inputs-after.json"), {str(path): digest for path, digest in hashes.items()})



    def run_stages(self, stages):
        for name, action, *args in stages:
            try:
                self.step(name, action, *args)
            except ERRORS as error:
                reason = str(error)
                self.stage.update(status="failed", exitCode=1, reason=reason)
                for stage, evidence in self.report["stages"].items():
                    if evidence["status"] == "not_run":
                        evidence["reason"] = f"因 {name} 阶段失败：{reason}"
                self.report.update(status="failed", exitCode=1, reason=reason)
                print(reason, file=sys.stderr)
                break
        else:
            self.report.update(status="passed", exitCode=0)
        self.report["finishedAt"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return self.report["exitCode"]


def execute(args):
    run = ModuleZeroRun(make_run_directory(args.evidence_root, "r3-module-zero-"), args.dotnet.resolve(),
                        args.strict_runtime_baseline)
    print(f"R3 Module Zero report: {run.report_path}", flush=True)
    manifest, feed, symbols, r2 = (path.resolve() for path in
                                    (args.candidate_manifest, args.candidate_feed, args.candidate_symbols, args.r2_feed))
    return run.run_stages((
        ("preflight", run.preflight, manifest, feed, symbols, r2),
        ("packages", run.packages, manifest, feed, symbols, r2),
        ("restore", run.restore), ("assets", run.assets), ("build", run.build), ("output", run.verify_output),
        ("process", run.probe), ("roles", run.roles), ("runtime", run.runtime), ("inputs", run.verify_inputs, manifest),
    ))
