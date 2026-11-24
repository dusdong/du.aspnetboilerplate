"""从候选包运行 R2 本地验收。"""

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener
import xml.etree.ElementTree as ET
import zipfile

from r2_assets import check_assets, check_http, check_output, compare_r1_graph, verify_runtime
from r2_packages import NUGET_SOURCE, R1_COMMIT, R1_TREE, SDK, TARGETS, commit_tree, verify_packages, verify_source, write_json
from verify import BASELINE, ROOT, TOOLS, R0Run, VerificationError, make_run_directory, read_json, require, sha256


RECORD = {"id": "8df27508-4dd1-45f5-b9c6-927f43e5fd1b", "value": "r2-sqlite"}
CONSUMER = Path("validation/minimal-backend")
FILES = ("global.json", "MinimalBackend.csproj", "Program.cs")
TARGET_STAGES = ("sdk", "restore", "assets", "build", "output", "http", "runtime")
STAGES = ("preflight", "tools", "packages", "negative_packages", "negative_missing_package",
          *(f"{tfm}/{stage}" for tfm in TARGETS for stage in TARGET_STAGES), "negative_evidence")
ERRORS = (VerificationError, OSError, ValueError, KeyError, AttributeError, TypeError, IndexError,
          ET.ParseError, zipfile.BadZipFile, subprocess.SubprocessError)


def environment(root, dotnet):
    return {
        "DOTNET_ROOT": str(dotnet.parent), "DOTNET_CLI_HOME": str(root / "dotnet-home"),
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1",
        "NUGET_PACKAGES": str(root / "packages"), "NUGET_HTTP_CACHE_PATH": str(root / "http-cache"),
        "NUGET_PLUGINS_CACHE_PATH": str(root / "plugins-cache"),
    }


class R2Run(R0Run):
    def __init__(self, evidence, dotnet):
        self.repo = ROOT
        self.evidence = evidence
        self.report_path = evidence / "report.json"
        self.dotnet = dotnet.resolve()
        self.metadata_tool = evidence / "tools/metadata/bin/Release/net10.0/R2Metadata.dll"
        self.api_tool = evidence / "tools/api/bin/Release/net9.0/ApiInventory.dll"
        self.report = {
            "profile": "r2", "status": "running", "exitCode": None,
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "command": [sys.executable, *sys.argv], "cwd": str(Path.cwd()),
            "environment": {"macOS": platform.mac_ver()[0], "architecture": platform.machine(),
                            "dotnet": str(self.dotnet), "python": platform.python_version()},
            "inputs": {}, "targets": {}, "negativeCases": {},
            "stages": {stage: {"status": "not_run", "exitCode": None, "commands": [], "evidence": []}
                       for stage in STAGES},
        }
        self.save()

    def step(self, name, action, *args, **kwargs):
        """每个目标独立记录阶段，并让失败停在对应目标。"""
        self.stage = self.report["stages"][name]
        self.stage["status"] = "running"
        self.save()
        print(f"R2 {name}", flush=True)
        try:
            outcome = action(*args, **kwargs)
        except ERRORS as error:
            self.stage.update(status="failed", exitCode=1, reason=str(error))
            self.save()
            raise VerificationError(f"{name}：{error}") from error
        self.stage.update(status="passed", exitCode=0)
        self.save()
        return outcome

    def preflight(self, feed, manifest, r1):
        require(platform.system() == "Darwin" and platform.machine() == "arm64",
                "R2 当前验收环境为 macOS arm64")
        require(feed.is_dir() and manifest.is_file() and r1.is_dir(), "候选源、清单或 R1 对照目录缺失")
        product = read_json(manifest)
        self.report["inputs"].update({"repository": str(self.repo), "feed": str(feed),
            "manifest": str(manifest), "manifestSha256": sha256(manifest), "r1Evidence": str(r1),
            "r1ReleaseOutputsSha256": sha256(r1 / "release-outputs.json"),
            "r0BaselineSha256": sha256(self.repo / BASELINE), "declaredSource": product["superproject"]})
        self.report["inputs"]["source"] = verify_source(self, manifest, product)
        r1_tree = commit_tree(self, self.repo / "aspnetboilerplate", R1_COMMIT, "r1-reference")
        require(r1_tree == R1_TREE, "固定 R1 对照提交的实际树与既有记录不同")
        self.report["inputs"]["r1Source"] = {"commit": R1_COMMIT, "tree": r1_tree}
        self.report["environment"]["dotnetSha256"] = sha256(self.dotnet)
        elf = self.read_command(["file", self.dotnet], self.evidence, "dotnet-file.log")
        require("Mach-O" in elf and "arm64" in elf, f"dotnet 不是 macOS ARM64 宿主：{elf}")

    def install_tools(self):
        root = self.evidence / "tools"
        metadata = root / "metadata"
        api = root / "api"
        shutil.copytree(self.repo / "eng/r2-metadata", metadata, ignore=shutil.ignore_patterns("bin", "obj"))
        api.mkdir()
        for file in ("ApiInventory.csproj", "Program.cs"):
            shutil.copy2(self.repo / TOOLS / file, api)
        shutil.copy2(self.repo / CONSUMER / "global.json", api)
        for name, cwd in (("metadata", metadata), ("api", api)):
            self.command([self.dotnet, "build", "-c", "Release", "--disable-build-servers"],
                         cwd, f"build-{name}.log", extra_env=environment(cwd, self.dotnet))

    def check_dependency_ranges(self, version, ranges, label):
        values = sorted(set(ranges.values()))
        _, log = self.command([self.dotnet, self.metadata_tool, "--internal-ranges", version, *values],
                              self.evidence, f"{label}-internal-ranges.log")
        invalid = set(read_json(log))
        failures = {edge: value for edge, value in ranges.items() if value in invalid}
        require(not failures, f"内部依赖范围须包含本批版本 {version} 且以它为下界：{failures}")

    def consumer(self, tfm, feed, version, folder):
        root = self.evidence / folder
        root.mkdir()
        project = root / "MinimalBackend.csproj"
        for file in FILES:
            shutil.copy2(self.repo / CONSUMER / file, root)
        xml = ET.parse(project)
        require(xml.getroot().get("Sdk") == "Microsoft.NET.Sdk.Web", "消费者应使用 Microsoft.NET.Sdk.Web")
        forbidden = ("ProjectReference", "Reference", "HintPath", "Import", "FrameworkReference")
        require(not any(list(xml.iter(tag)) for tag in forbidden), "消费者包含项目、文件或额外框架引用")
        cfg = root / "NuGet.Config"
        config = ET.Element("configuration")
        sources = ET.SubElement(config, "packageSources")
        ET.SubElement(sources, "clear")
        ET.SubElement(sources, "add", key="candidate", value=str(feed))
        ET.SubElement(sources, "add", key="nuget.org", value=NUGET_SOURCE)
        ET.SubElement(ET.SubElement(config, "fallbackPackageFolders"), "clear")
        mapping = ET.SubElement(config, "packageSourceMapping")
        candidate = ET.SubElement(mapping, "packageSource", key="candidate")
        for pattern in ("Du.Abp", "Du.Abp.*"):
            ET.SubElement(candidate, "package", pattern=pattern)
        ET.SubElement(ET.SubElement(mapping, "packageSource", key="nuget.org"), "package", pattern="*")
        ET.indent(config)
        ET.ElementTree(config).write(cfg, encoding="utf-8", xml_declaration=True)
        env = environment(root, self.dotnet)
        Path(env["NUGET_PACKAGES"]).mkdir()
        Path(env["NUGET_HTTP_CACHE_PATH"]).mkdir()
        properties = [f"-p:TargetFrameworks={tfm}", f"-p:R2CandidateVersion={version}",
                      "--disable-build-servers"]
        restore = [self.dotnet, "restore", project, "--configfile", cfg, "--no-http-cache",
                   "-p:Configuration=Release", *properties]
        build = [self.dotnet, "build", project, "--no-restore", "-c", "Release", "-f", tfm, *properties]
        return root, env, restore, build

    def target_preflight(self, tfm, root, env):
        version, _, _ = TARGETS[tfm]
        _, sdk = self.command([self.dotnet, "--version"], root, f"{tfm}-sdk.log", extra_env=env)
        require(sdk.read_text().strip() == SDK, f"{tfm} 消费目录没有选中 SDK {SDK}")
        _, info = self.command([self.dotnet, "--info"], root, f"{tfm}-info.log", extra_env=env)
        require(re.search(r"(?im)^\s*Architecture:\s+arm64\s*$|^\s*体系结构[：:]\s+arm64\s*$", info.read_text())
                or re.search(r"(?m)^\s*RID:\s+osx-arm64\s*$", info.read_text()), f"{tfm} dotnet --info 未确认 arm64")
        _, log = self.command([self.dotnet, "--list-runtimes"], root, f"{tfm}-runtimes.log", extra_env=env)
        found = log.read_text().splitlines()
        for runtime in ("Microsoft.NETCore.App", "Microsoft.AspNetCore.App"):
            require(any(line.startswith(f"{runtime} {version} [") for line in found), f"缺少 {runtime} {version}")

    def restore(self, tfm, root, env, command, expected=(0,), prefix=""):
        for variable in ("NUGET_PACKAGES", "NUGET_HTTP_CACHE_PATH"):
            require(not any(Path(env[variable]).iterdir()), f"{tfm} {variable} 需要空缓存")
        return self.command(command, root, f"{prefix}{tfm}-restore.log", accepted=expected, extra_env=env)

    def assets(self, tfm, root, env, feed, candidate):
        evidence = root / "obj/project.assets.json"
        data = read_json(evidence)
        details = check_assets(data, tfm, root / "MinimalBackend.csproj",
                               Path(env["NUGET_PACKAGES"]), feed, candidate, TARGETS[tfm][1],
                               self.check_dependency_ranges)
        inventory = self.evidence_file(f"{tfm}-assets-inventory.json")
        write_json(inventory, details)
        delta = self.evidence_file(f"{tfm}-r1-restore-differences.json")
        write_json(delta, compare_r1_graph(Path(candidate["r1Evidence"]), tfm, data, details))
        self.stage["evidence"].append(str(evidence.relative_to(self.evidence)))
        return details

    def output(self, tfm, output, candidate, packages):
        for name in ("MinimalBackend.deps.json", "MinimalBackend.runtimeconfig.json"):
            self.stage["evidence"].append(str((output / name).relative_to(self.evidence)))
        return check_output(output, tfm, candidate, packages)

    def host_http(self, tfm, root, output, env):
        dll = output / "MinimalBackend.dll"
        trace = {"DOTNET_HOST_TRACE": "1", "DOTNET_HOST_TRACEFILE": str(root / "dotnet-host-trace.log"),
                 "COREHOST_TRACE": "1", "COREHOST_TRACEFILE": str(root / "corehost-trace.log")}
        argv = [str(self.dotnet), str(dll)]
        log_path = self.evidence_file(f"{tfm}-host.log")
        result = self.evidence_file(f"{tfm}-http.json")
        process_record = {"argv": argv, "cwd": str(root), "log": log_path.name, "exitCode": None,
                          "environmentOverrides": env | trace}
        self.stage["commands"].append(process_record)
        self.save()
        responses = {}
        with log_path.open("wb") as log:
            with subprocess.Popen(argv, cwd=root, env=os.environ | env | trace,
                                  stdout=log, stderr=subprocess.STDOUT) as host:
                process_record["pid"] = host.pid
                try:
                    deadline = time.monotonic() + 35
                    while time.monotonic() < deadline:
                        match = re.search(r"^R2_LISTEN (http://127\.0\.0\.1:[0-9]+)$",
                                          log_path.read_text(errors="replace"), re.MULTILINE)
                        if match:
                            break
                        require(host.poll() is None, f"{tfm} 宿主在监听前退出，详见 {log_path}")
                        time.sleep(0.15)
                    require(match, f"{tfm} 未在时限内公布 HTTP 回环端口，详见 {log_path}")
                    address = match[1] + "/records"
                    opener = build_opener(ProxyHandler({}))
                    for method, payload in (("post", json.dumps(RECORD).encode()), ("get", None)):
                        request = Request(address, data=payload, method=method.upper(),
                                          headers={"Content-Type": "application/json"})
                        try:
                            response = opener.open(request, timeout=20)
                        except HTTPError as error:
                            response = error
                        with response:
                            raw_body = response.read().decode("utf-8", errors="replace")
                            responses[method] = {"url": address, "request": RECORD if payload else None,
                                                 "status": response.status, "headers": dict(response.headers),
                                                 "rawBody": raw_body}
                            write_json(result, responses)
                            responses[method]["body"] = json.loads(raw_body) if raw_body else None
                            write_json(result, responses)
                finally:
                    if host.poll() is None:
                        host.terminate()
                    try:
                        host.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        host.kill()
                        host.wait(timeout=5)
                    process_record["exitCode"] = host.returncode
                    self.save()
        require(process_record["exitCode"] == 0, f"{tfm} 宿主关停退出码 {process_record['exitCode']}")
        return check_http(responses, RECORD), process_record["pid"]

    def run_target(self, tfm, feed, candidate):
        target = self.report["targets"][tfm] = {"status": "running", "framework": tfm}
        try:
            root, env, restore, build = self.consumer(tfm, feed, candidate["version"], tfm)
            target.update(workDir=str(root), nugetConfig=str(root / "NuGet.Config"),
                          projectAssets=str(root / "obj/project.assets.json"))
            self.step(f"{tfm}/sdk", self.target_preflight, tfm, root, env)
            self.step(f"{tfm}/restore", self.restore, tfm, root, env, restore)
            packages = self.step(f"{tfm}/assets", self.assets, tfm, root, env, feed, candidate)
            self.step(f"{tfm}/build", self.command, build, root, f"{tfm}-build.log", extra_env=env)
            output = root / "bin/Release" / tfm
            graph = self.step(f"{tfm}/output", self.output, tfm, output, candidate, packages)
            queried, pid = self.step(f"{tfm}/http", self.host_http, tfm, root, output, env)
            self.step(f"{tfm}/runtime", verify_runtime, queried, output, tfm, candidate, packages, graph,
                      TARGETS[tfm][0], self.dotnet, pid)
            target.update(status="passed", assetsInventory=f"{tfm}-assets-inventory.json",
                          runtimeEvidence=f"{tfm}-http.json", resolvedPackages=len(packages), pid=pid)
        except ERRORS as error:
            target.update(status="failed", reason=str(error))
            return False
        finally:
            for stage in TARGET_STAGES:
                step = self.report["stages"][f"{tfm}/{stage}"]
                if step["status"] == "not_run":
                    step["reason"] = target.get("reason", "上一阶段缺失")
            self.save()
        return True

    def execute_r2(self, feed, manifest, symbols, r1):
        from r2_diagnostics import negative_evidence, negative_packages, negative_restore

        try:
            self.step("preflight", self.preflight, feed, manifest, r1)
            self.step("tools", self.install_tools)
            candidate = self.step("packages", verify_packages, self, feed, manifest, symbols, r1)
            self.report["candidate"] = candidate
            write_json(self.evidence / "candidate.json", candidate)
            self.step("negative_packages", negative_packages, self, feed, manifest, symbols, r1)
            self.step("negative_missing_package", negative_restore, self, feed, candidate)
            target_results = [self.run_target(tfm, feed, candidate) for tfm in TARGETS]
            require(all(target_results), "R2 存在未通过的独立目标，详见 targets")
            self.step("negative_evidence", negative_evidence, self, feed, candidate)
        except ERRORS as error:
            self.report.update(status="failed", exitCode=1, reason=str(error))
            for tfm in TARGETS:
                self.report["targets"].setdefault(tfm, {"status": "not_run", "reason": str(error)})
            for stage in self.report["stages"].values():
                if stage["status"] == "not_run":
                    stage.setdefault("reason", str(error))
            print(f"R2 验收失败：{error}", file=sys.stderr)
        else:
            self.report.update(status="passed", exitCode=0)
        self.report["finishedAt"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return self.report["exitCode"]


def execute(args):
    selected = args.dotnet or shutil.which("dotnet")
    run = R2Run(make_run_directory(args.evidence_root, "r2-"), Path(selected or "/dotnet"))
    print(f"R2 report: {run.report_path}", flush=True)
    manifest = args.candidate_manifest.resolve()
    symbols = args.candidate_symbols or manifest.parent / "symbols"
    return run.execute_r2(args.candidate_feed.resolve(), manifest, symbols.resolve(), args.r1_evidence.resolve())
