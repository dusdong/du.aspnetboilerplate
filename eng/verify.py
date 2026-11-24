#!/usr/bin/env python3
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
MAINTENANCE = Path("docs/maintenance")
TOOLS = MAINTENANCE / "baseline-tools"
BASELINE = MAINTENANCE / "release-baseline.json"
TOOL_FILES = [Path("eng/verify.py")] + [
    TOOLS / name for name in ("reproduce.zsh", "inventory.py", "ApiInventory.csproj", "Program.cs")
]
STAGES = (
    "preflight", "primary_materialize", "sdk", "primary_restore", "repeat_materialize",
    "repeat_restore", "restore_compare", "project_identity", "release_build", "api_compare",
    "dotnet_tests", "verify_inputs",
)


class VerificationError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def vstest_version(output):
    match = re.search(r"^VSTest[^\n]*? (\d+\.\d+\.\d+(?:-[\w.-]+)? \([^)]+\))\s*$",
                      output, re.MULTILINE)
    return match[1] if match else None


def read_trx(path, suite):
    name = suite["suite"]
    try:
        root = ET.parse(path).getroot()
        namespace = root.tag[:-len("TestRun")]
        require(root.tag == f"{namespace}TestRun" and
                (not namespace or namespace.endswith("}")), "根元素必须为 TestRun")
        results = root.findall(f"{namespace}Results/{namespace}UnitTestResult")
        require(results, "没有 UnitTestResult 明细（匹配数为零）")
        outcomes = Counter(row.get("outcome") for row in results)
        unexpected = outcomes.keys() - {"Passed", "Failed", "NotExecuted"}
        require(not unexpected, f"非预期的明细结果 {list(unexpected)}")
        skipped = [row for row in results if row.get("outcome") == "NotExecuted"]
        actual_names = Counter(row.get("testName", "") for row in skipped)
        expected_reasons = {row["test"]: row["reason"] for row in suite["skippedTests"]}
        require(actual_names == Counter(expected_reasons.keys()),
                f"跳过用例应为 {sorted(expected_reasons)}，实际为 {dict(actual_names)}")

        detail = {"passed": outcomes["Passed"], "failed": outcomes["Failed"], "skipped": len(skipped)}
        expected_detail = {key: suite[key] for key in detail}
        require(detail == expected_detail, f"明细计数应为 {expected_detail}，实际为 {detail}")
        summaries = root.findall(f"{namespace}ResultSummary/{namespace}Counters")
        require(len(summaries) == 1, f"需要一份汇总计数，实际为 {len(summaries)}")
        expected = {"total": len(results), "executed": detail["passed"] + detail["failed"],
                    "passed": detail["passed"], "failed": detail["failed"], "notExecuted": len(skipped)}
        summary = {key: int(summaries[0].attrib[key]) for key in expected}
        require(expected["total"] == suite["totalReported"], "明细总计与基线不符")
        known_difference = (
            name == "Abp.Tests" and detail == {"passed": 1105, "failed": 0, "skipped": 2}
            and summary["notExecuted"] == 0
        )
        expected_summary = expected | {"notExecuted": 0} if known_difference else expected
        require(summary == expected_summary, f"汇总计数应为 {expected_summary}，实际为 {summary}")
        reasons = []
        for row in skipped:
            test = row.attrib["testName"]
            message = row.findtext(f"{namespace}Output/{namespace}ErrorInfo/{namespace}Message")
            reasons.append({"test": test, "reason": message or expected_reasons[test],
                            "reasonSource": "trx" if message else "baseline"})
        return {
            **detail, "summary": summary, "skippedTests": reasons,
            "knownSummaryDifference": {"notExecuted": {"summary": 0, "details": 2}} if known_difference else None,
        }
    except (OSError, ET.ParseError, VerificationError, KeyError, ValueError) as error:
        raise VerificationError(f"{name} TRX {path}: {error}") from error


class R0Run:
    def __init__(self, repo, evidence):
        self.repo = repo
        self.evidence = evidence
        self.report_path = evidence / "report.json"
        self.report = {
            "profile": "r0", "status": "running", "exitCode": None,
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "command": [sys.executable, *sys.argv], "cwd": str(Path.cwd()),
            "environment": {
                "python": platform.python_version(), "platform": platform.system(),
                "macOS": platform.mac_ver()[0], "architecture": platform.machine(),
            },
            "inputs": {"repository": str(repo)},
            "stages": {stage: {"status": "not_run", "exitCode": None, "commands": [],
                               "evidence": []} for stage in STAGES},
        }
        self.save()

    def save(self):
        temporary = self.report_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.report_path)

    def step(self, name, action, *args):
        self.stage = self.report["stages"][name]
        self.stage["status"] = "running"
        self.save()
        print(f"R0 {name}", flush=True)
        try:
            action(*args)
        except (VerificationError, OSError, ValueError, KeyError, TypeError) as error:
            self.stage.update(status="failed", exitCode=1, reason=str(error))
            raise VerificationError(f"{name}: {error}") from error
        else:
            self.stage.update(status="passed", exitCode=0)
        finally:
            self.save()

    def evidence_file(self, name):
        if name not in self.stage["evidence"]:
            self.stage["evidence"].append(name)
        return self.evidence / name

    def command(self, args, cwd, log, *, accepted=(0,), output=None, extra_env=None):
        args = [str(arg) for arg in args]
        path = self.evidence_file(log)
        record = {"argv": args, "cwd": str(cwd), "log": log, "exitCode": None}
        self.stage["commands"].append(record)
        if output:
            record["output"] = output
        if extra_env:
            record["environmentOverrides"] = extra_env
        env = (os.environ | extra_env) if extra_env else None
        self.save()
        with path.open("w+b") as log_file:
            if output:
                with self.evidence_file(output).open("wb") as stdout:
                    result = subprocess.run(args, cwd=cwd, stdout=stdout, stderr=log_file, env=env)
            else:
                result = subprocess.run(args, cwd=cwd, stdout=log_file, stderr=subprocess.STDOUT, env=env)
        record["exitCode"] = result.returncode
        require(result.returncode in accepted, f"退出码 {result.returncode}，详见 {path}")
        return result.returncode, path

    def read_command(self, args, cwd, log):
        _, path = self.command(args, cwd, log)
        return path.read_text(encoding="utf-8").rstrip()

    def git(self, repo, log, *args):
        _, path = self.command(["git", "-C", repo, *args], self.repo, log,
                               extra_env={"GIT_OPTIONAL_LOCKS": "0"})
        return path.read_text(encoding="utf-8").rstrip()

    def git_inputs(self, label):
        framework = self.repo / "aspnetboilerplate"
        head = self.git(self.repo, f"{label}-head.log", "rev-parse", "HEAD")
        gitlinks = self.git(self.repo, f"{label}-gitlinks.log", "ls-tree", head, "--", "aspnetboilerplate")
        mode, kind, gitlink, path = gitlinks.split()
        require((mode, kind, path) == ("160000", "commit", "aspnetboilerplate"),
                f"{head} 缺少 aspnetboilerplate gitlink")
        top = self.git(framework, f"{label}-framework-root.log", "rev-parse", "--show-toplevel")
        require(Path(top).resolve() == framework, f"框架子模块未检出：{framework}")
        checkout = self.git(framework, f"{label}-framework-head.log", "rev-parse", "HEAD")
        status = self.git(framework, f"{label}-framework-status.log", "status", "--porcelain", "-uall")
        return {"head": head, "frameworkGitlink": gitlink, "frameworkCheckout": checkout,
                "frameworkStatus": status.splitlines()}

    def input_files(self, label):
        status = self.git(self.repo, f"{label}-input-status.log", "status", "--porcelain=v1", "-uall",
                          "--", *(str(path) for path in self.paths))
        return {"sha256": {str(path): sha256(self.repo / path) for path in self.paths},
                "worktreeStatus": status.splitlines(), "dirty": bool(status)}

    def shell(self, phase, which="primary", suite=None, logs=()):
        cmd = ["zsh", self.repo / TOOLS / "reproduce.zsh", self.evidence, which, phase, self.work]
        if suite:
            cmd.append(suite)
        cwd = self.repo if phase in {"inputs", "materialize"} else self.work / which
        try:
            return self.command(cmd, cwd, f"{which}-{phase}{'-' + suite if suite else ''}.log")
        finally:
            for log in logs:
                if (self.evidence / log).is_file():
                    self.evidence_file(log)

    def preflight(self):
        require(sys.version_info >= (3, 10), "需要 Python 3.10 或以上")
        require(shutil.which("git"), "未找到必需工具 git")
        inputs = self.report["inputs"]
        inputs["git"] = self.git_inputs("before")
        baseline_path = self.repo / BASELINE
        baseline = read_json(baseline_path)
        inputs.update(baseline=str(BASELINE), baselineSha256=sha256(baseline_path),
                      historicalSuperproject=baseline["superprojectInputCommit"],
                      fixedFrameworkCommit=baseline["frameworkInputCommit"])
        self.baseline = baseline
        validation = baseline["validation"]
        self.packages = baseline["initialPackageClosure"]["packages"]
        self.suites = validation["tests"]["suites"]
        self.restore_baseline = MAINTENANCE / validation["restore"]["inventory"]
        self.paths = [Path(".gitmodules"), BASELINE, self.restore_baseline, *TOOL_FILES]
        self.paths += [MAINTENANCE / p["apiInventory"] for p in self.packages]
        inputs["files"] = self.input_files("before")
        require(baseline["stage"] == "R0" and baseline["schemaVersion"] == 1, "需要已接受的 R0 基线清单")
        needed = ("zsh", "tar", "dotnet", "python3", "find")
        missing = [tool for tool in needed if not shutil.which(tool)]
        require(not missing, f"未找到必需工具 {', '.join(missing)}")
        env = self.report["environment"]
        expected = validation["environment"]
        require(env["platform"] == "Darwin" and env["architecture"] == expected["architecture"],
                f"R0 要求 macOS {expected['architecture']}，实际为 {env['platform']} {env['architecture']}")
        framework = self.repo / "aspnetboilerplate"
        commit = inputs["fixedFrameworkCommit"]
        require(re.fullmatch(r"[a-f0-9]{40}", commit), f"无效的固定框架 SHA：{commit}")
        try:
            kind = self.git(framework, "r0-object.log", "cat-file", "-t", commit)
            require(kind == "commit", f"Git 对象类型为 {kind}")
        except VerificationError as error:
            raise VerificationError(f"无法读取固定的框架提交对象 {commit}：{error}") from error
        inputs["fixedFrameworkTree"] = self.git(framework, "r0-tree.log", "rev-parse", f"{commit}^{{tree}}")
        _, plan_path = self.shell("inputs")
        planned = plan_path.read_text(encoding="utf-8").splitlines()
        script_commit, *planned_names = planned
        separator = planned_names.index("--")
        package_names, suite_names = planned_names[:separator], planned_names[separator + 1:]
        restore = read_json(self.repo / self.restore_baseline)
        expected_projects = [p["project"] for p in self.packages] + [s["project"] for s in self.suites]
        require(script_commit == commit and
                sorted(f"src/{name}/{name}.csproj" for name in package_names) ==
                sorted(p["project"] for p in self.packages) and
                suite_names == [s["suite"] for s in self.suites] and
                sorted(expected_projects) == sorted(restore["entryProjects"]),
                "已接受基线、还原清单与脚本的框架提交或项目入口不一致")
        require(len(restore["projects"]) == 11 and all(
            [(target["targetFramework"], target["runtimeIdentifier"]) for target in project["targets"]]
            == [("net9.0", None)] for project in restore["projects"].values()
        ), f"{self.restore_baseline} 需要 11 个项目，各含一个无 RID 的 net9.0 目标")

    def sdk(self):
        cwd = self.work / "primary"
        sdk = self.read_command(["dotnet", "--version"], cwd, "dotnet-version.log")
        info = self.read_command(["dotnet", "--info"], cwd, "dotnet-info.log")
        runtimes = self.read_command(["dotnet", "--list-runtimes"], cwd, "dotnet-runtimes.log")
        rid = re.search(r"^\s*RID:\s*(\S+)", info, re.MULTILINE)
        env = self.report["environment"]
        msbuild = re.search(r"^\s*MSBuild version:\s*(\S+)", info, re.MULTILINE)
        env.update(dotnetSdk=sdk, hostRid=rid[1] if rid else None,
                   msbuild=msbuild[1] if msbuild else None, dotnetRuntimes=runtimes.splitlines())
        expected = self.baseline["validation"]["environment"]
        require(sdk == expected["dotnetSdk"], f"{cwd} 的实际 SDK 应为 {expected['dotnetSdk']}，实际为 {sdk}")
        require(env["hostRid"] == expected["hostRid"],
                f".NET 宿主 RID 应为 {expected['hostRid']}，实际为 {env['hostRid']}")
        for runtime in ("Microsoft.NETCore.App", "Microsoft.AspNetCore.App"):
            require(re.search(rf"^{re.escape(runtime)} 9\.\d+\.\d+ \[", runtimes, re.MULTILINE),
                    f"缺少 {runtime} 9 运行时，详见 dotnet-runtimes.log")

    def restore(self, which):
        self.stage["coverage"] = "restore_only" if which == "repeat" else "primary"
        self.stage["nugetPackages"] = str(self.work / f"{which}-packages")
        logs = [f"{which}-{name}.log" for name in ("dotnet-info", "new", "sln", "sources", "restore", "inventory")]
        self.shell("restore", which, logs=[*logs, f"{which}.NuGet.Config", f"{which}-restore-inventory.json"])
        actual = self.evidence / f"{which}-restore-inventory.json"
        projects = read_json(actual)["projects"]
        self.stage.update(projects=len(projects), projectTargets=sum(len(p["targets"]) for p in projects.values()))

    def compare_restore(self):
        primary = self.evidence / "primary-restore-inventory.json"
        repeat = self.evidence / "repeat-restore-inventory.json"
        baseline = self.repo / self.restore_baseline
        differences = []
        for label, before, after in (
            ("baseline-primary", baseline, primary), ("baseline-repeat", baseline, repeat),
            ("primary-repeat", primary, repeat),
        ):
            code, path = self.command([sys.executable, self.repo / TOOLS / "inventory.py", "compare-restore",
                                       before, after], self.repo, f"restore-{label}.log", accepted=(0, 1))
            if code:
                differences.append(str(path))
        require(not differences, f"实际还原图出现差异，详见 {', '.join(differences)}")

    def identity(self):
        names = [package["assemblyName"] for package in self.packages]
        self.shell("identity", logs=[f"{name}-msbuild.json.log" for name in names])
        self.dlls = {}
        self.stage["projects"] = []
        primary = self.work / "primary"
        for p in self.packages:
            name = p["assemblyName"]
            log = self.evidence / f"{name}-msbuild.json.log"
            try:
                # 旧手册接口在 JSON 正文前后保留命令和退出码。
                text = log.read_text(encoding="utf-8")
                offset = re.search(r"^\{\s*$", text, re.MULTILINE)
                require(offset, "缺少 MSBuild JSON 求值")
                data, _ = json.JSONDecoder().raw_decode(text[offset.start():])
                props = data["Properties"]
                tfms = (props["TargetFrameworks"] or props["TargetFramework"]).split(";")
                refs = sorted(Path(ref["FullPath"]).resolve().relative_to(primary).as_posix()
                              for ref in data["Items"]["ProjectReference"])
                actual = {"PackageId": props["PackageId"], "PackageVersion": props["PackageVersion"],
                          "AssemblyName": props["AssemblyName"], "RootNamespace": props["RootNamespace"],
                          "TargetFrameworks": tfms, "RuntimeIdentifier": props["RuntimeIdentifier"] or None,
                          "ProjectReference": refs}
                expected = {"PackageId": p["originalPackageId"], "PackageVersion": p["originalPackageVersion"],
                            "AssemblyName": name, "RootNamespace": p["rootNamespace"],
                            "TargetFrameworks": p["targetFrameworks"], "RuntimeIdentifier": p["runtimeIdentifier"],
                            "ProjectReference": sorted(p["internalProjectReferences"])}
                target = Path(props["TargetPath"])
                require(target.is_absolute() and target.is_relative_to(primary) and target.name == f"{name}.dll",
                        f"无效的主轮 TargetPath：{target}")
                self.stage["projects"].append({"project": p["project"], "actual": actual,
                                               "expected": expected, "targetPath": str(target)})
                require(actual == expected, f"身份有差异，预期 {expected}，实际 {actual}")
                self.dlls[name] = target
            except (OSError, KeyError, ValueError, VerificationError) as error:
                raise VerificationError(f"{p['project']} 求值 {log}: {error}") from error

    def api(self):
        primary = self.work / "primary"
        for p in self.packages:
            name = p["assemblyName"]
            target = self.dlls[name]
            require(target.is_file(), f"{p['project']} 缺少 Release DLL {target}，求值见 {name}-msbuild.json.log")
        tools = self.work / "tools"
        tools.mkdir()
        for source in ("ApiInventory.csproj", "Program.cs"):
            shutil.copyfile(self.repo / TOOLS / source, tools / source)
        self.command(
            ["dotnet", "build", tools / "ApiInventory.csproj", "--configuration", "Release",
             f"-p:RestoreConfigFile={self.evidence / 'primary.NuGet.Config'}"],
            primary, "api-tool-build.log", extra_env={"NUGET_PACKAGES": str(self.work / "primary-packages")},
        )
        extractor = tools / "bin/Release/net9.0/ApiInventory.dll"
        self.stage["assemblies"] = []
        differences = []
        for p in self.packages:
            name = p["assemblyName"]
            target = self.dlls[name]
            digest = sha256(target)
            labels = [f"api/{name}.json", f"api/{name}.repeat.json"]
            for label in labels:
                self.command(["dotnet", extractor, target], primary, f"{label}.log", output=label)
            manifests = [self.evidence / label for label in labels]
            first = read_json(manifests[0])
            version = self.baseline["validation"]["api"]["extractorVersion"]
            require(first["sha256"] == digest and first["extractorVersion"] == version,
                    f"{name} 的 API 提取器版本或 DLL 摘要不符，详见 {manifests[0]}")
            require(manifests[0].read_bytes() == manifests[1].read_bytes(), f"{name} 两次 API 提取不一致：{labels}")
            comparison = f"api/{name}.comparison.json"
            code, _ = self.command([sys.executable, self.repo / TOOLS / "inventory.py", "compare-api",
                                    self.repo / MAINTENANCE / p["apiInventory"], manifests[0]],
                                   self.repo, f"{comparison}.log", output=comparison, accepted=(0, 1))
            self.stage["assemblies"].append({"assembly": name, "path": str(target), "sha256": digest,
                                              "extractorVersion": version, "repeatIdentical": True,
                                              "manifests": labels, "comparison": comparison, "exitCode": code})
            if code:
                differences.append(f"{name}: {comparison}")
        require(not differences, f"API 有差异，详见 {', '.join(differences)}")

    def sqlite(self):
        sqlite = self.baseline["validation"]["tests"]["sqlite"]
        suite = next(s for s in self.suites if s["suite"] == sqlite["suite"])
        primary = self.work / "primary"
        config = primary / sqlite["source"]
        path = Path("sqlite-test-configuration.cs")
        shutil.copyfile(config, self.evidence_file(str(path)))
        inv = read_json(self.evidence / "primary-restore-inventory.json")
        targets = inv["projects"][suite["project"]]["targets"]
        resolved = {p["id"]: p["version"] for p in targets[0]["packages"]}
        providers = {name: resolved.get(name) for name in sqlite["providers"]}
        require(providers == sqlite["providers"], f"SQLite Provider 版本不一致：{providers}")
        rows = [p for p in targets[0]["packages"] if p["id"] == "SQLitePCLRaw.lib.e_sqlite3"]
        native = sqlite["nativeRuntimeAsset"]
        package_asset = self.work / "primary-packages" / rows[0]["id"].lower() / rows[0]["version"] / native
        output_asset = primary / Path(suite["project"]).parent / "bin/Release" / suite["targetFramework"] / native
        require(package_asset.is_file() and output_asset.is_file(),
                f"{suite['suite']} 缺少 SQLite 原生资产：{package_asset} 或 {output_asset}")
        digest = sha256(output_asset)
        require(digest == sha256(package_asset), f"{suite['suite']} SQLite 原生资产摘要与还原包不符")
        self.stage["sqlite"] = {"source": str(path), "configuration": sqlite["configuration"],
                                "providerVersions": providers, "nativeAsset": str(output_asset),
                                "nativeAssetSha256": digest}

    def tests(self):
        self.sqlite()
        self.stage["suites"] = []
        errors = []
        for suite in self.suites:
            name = suite["suite"]
            trx = f"trx/{name}.trx"
            test_log = f"{name}-test.log"
            result = {"suite": name, "project": suite["project"], "trx": trx, "status": "failed"}
            self.stage["suites"].append(result)
            try:
                self.shell("test", suite=name, logs=[test_log, trx])
                result.update(read_trx(self.evidence / trx, suite))
                output = (self.evidence / test_log).read_text(encoding="utf-8")
                version = vstest_version(output)
                require(version, f"{name} 日志缺少 VSTest 版本：{test_log}")
                result.update(status="passed", vstest=version,
                              duplicateDiscoveryIdsExcluded=output.count("Skipping test case with duplicate ID"))
            except (VerificationError, OSError) as error:
                result["reason"] = str(error)
                errors.append(f"{name}: {error}")
        require(not errors, "\n".join(errors))
        self.stage["totals"] = {key: sum(s[key] for s in self.stage["suites"])
                                for key in ("passed", "failed", "skipped")}

    def verify_inputs(self):
        inputs = self.report["inputs"]
        inputs["gitAfter"] = self.git_inputs("after")
        inputs["filesAfter"] = self.input_files("after")
        require(inputs["gitAfter"] == inputs["git"], "运行期间主仓或框架检出发生变化")
        require(inputs["filesAfter"] == inputs["files"], "运行期间复验工具或基线输入发生变化")

    def execute(self, work_root):
        try:
            self.work = make_run_directory(work_root, "r0-work-")
            (self.evidence / "api").mkdir()
            self.report["workDirectory"] = str(self.work)
            self.step("preflight", self.preflight)
            self.step("primary_materialize", self.shell, "materialize")
            self.step("sdk", self.sdk)
            self.step("primary_restore", self.restore, "primary")
            self.step("repeat_materialize", self.shell, "materialize", "repeat")
            self.step("repeat_restore", self.restore, "repeat")
            self.step("restore_compare", self.compare_restore)
            self.step("project_identity", self.identity)
            self.step("release_build", lambda: self.shell("build", logs=["build.log"]))
            self.step("api_compare", self.api)
            self.step("dotnet_tests", self.tests)
            self.step("verify_inputs", self.verify_inputs)
        except (VerificationError, OSError, KeyboardInterrupt) as error:
            reason = str(error) or "执行中断"
            print(f"R0 failed: {reason}", file=sys.stderr)
            for stage in self.report["stages"].values():
                if stage["status"] == "running":
                    stage.update(status="failed", exitCode=1, reason=reason)
                if stage["status"] == "not_run":
                    stage["reason"] = f"复验已停止：{reason}"
            self.report.update(status="failed", exitCode=1, reason=reason)
        else:
            self.report.update(status="passed", exitCode=0)
        self.report["finishedAt"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return self.report["exitCode"]


def make_run_directory(parent, prefix):
    if parent is not None:
        parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=parent, prefix=prefix)).resolve()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=("r0", "r2"))
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--candidate-feed", type=Path)
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--candidate-symbols", type=Path)
    parser.add_argument("--r1-evidence", type=Path)
    parser.add_argument("--dotnet", type=Path)
    args = parser.parse_args()
    if args.profile == "r2":
        if not all((args.candidate_feed, args.candidate_manifest, args.r1_evidence, args.evidence_root)):
            parser.error("r2 需要 --candidate-feed、--candidate-manifest、--r1-evidence 和 --evidence-root")
        if args.work_root:
            parser.error("r2 在 --evidence-root 下建立隔离工作目录")
        sys.dont_write_bytecode = True
        from r2_verify import execute
        return execute(args)
    if any((args.candidate_feed, args.candidate_manifest, args.candidate_symbols, args.r1_evidence, args.dotnet)):
        parser.error("候选、R1 对照和私有 dotnet 参数适用于 r2")
    run = R0Run(ROOT, make_run_directory(args.evidence_root, "r0-"))
    print(f"R0 report: {run.report_path}", flush=True)
    return run.execute(args.work_root)


if __name__ == "__main__":
    raise SystemExit(main())
