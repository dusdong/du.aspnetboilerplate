#!/usr/bin/env python3
"""复验 Module Zero 冻结实物、实际缺包和证据诊断。"""

import argparse
from contextlib import redirect_stderr
from copy import deepcopy
import io
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import r3_leaf_verify
import r3_web_host
import verify
from r2_diagnostics import edited_zip
from r2_packages import write_json
from r3_leaf_packages import R2_VERSION, TFM
from r3_module_zero_assets import check_assets
from r3_module_zero_packages import R2_IDS, R3_IDS, TOP_PACKAGE, expected_edges, read_r3
from r3_module_zero_roles import check_roles
from r3_module_zero_verify import ModuleZeroRun, PROFILE
from verify import ROOT, read_json, require, sha256
from verify_r3_web_host import verify_dispatch


def case_report(report, stage, expected):
    require(report["exitCode"] == 1 and report["stages"][stage]["status"] == "failed" and
            all(part in report["reason"] for part in expected),
            f"{stage} 未得到预期诊断 {expected}：{report.get('reason')}")
    stages = report["stages"]
    remaining = list(stages)[list(stages).index(stage) + 1:]
    require(all(stages[name]["status"] == "not_run" and stages[name]["reason"] for name in remaining),
            f"{stage} 失败后的阶段应保留未执行原因")


class Diagnostics:
    def __init__(self, accepted, output):
        self.accepted, self.output = accepted, output
        self.report = read_json(accepted / "report.json")
        require(self.report["profile"] == PROFILE and self.report["exitCode"] == 0, "需要同 profile 的成功报告")
        self.inputs = self.report["inputs"]
        self.dotnet = Path(self.report["environment"]["dotnet"])
        self.version = self.inputs["candidateVersion"]
        self.candidate = read_json(accepted / "candidate.json")
        self.packages = self.candidate["packages"]
        self.cases = {}

    def results(self, label, mode, report, path):
        self.cases[label] = {"mode": mode, "report": str(path), "diagnosticExitCode": report["exitCode"],
                             "reason": report["reason"], "sha256": sha256(path)}
        print(f"{mode} {label}：退出 {report['exitCode']}，{report['reason']}", flush=True)

    def create(self, label):
        case = self.output / label
        case.mkdir()
        return case

    def staged(self, root, mode, stage, expected, run, action):
        run.report["diagnosticMode"] = mode
        require(run.run_stages(((stage, action),)) == 1, f"{root.name} 应退出 1")
        report = read_json(run.report_path)
        case_report(report, stage, expected)
        self.results(root.name, mode, report, run.report_path)
        return report

    def missing_transitive(self):
        root = self.create("missing-transitive-package")
        name = R3_IDS[0]
        run = ModuleZeroRun(root, self.dotnet, True)
        run.version = self.version
        run.report["inputs"].update(validatedRun=str(self.accepted), omittedPackage=name,
                                     packageArchive=self.packages[name]["archive"])

        def attempt():
            run.prepare_project()
            run.prepare_sources(self.packages, missing=name)
            run.restore()

        report = self.staged(root, "实测 NuGet", "restore", ("退出码 1", "restore.log"), run, attempt)
        log = (root / "restore.log").read_text()
        require(report["stages"]["restore"]["commands"][0]["exitCode"] == 1 and "NU1101" in log and name in log and
                not (run.cache / name.lower()).exists(), f"实际 NuGet 缺传递包诊断未定位 {name}")

    def same_version_bytes(self, name):
        root = self.create(f"same-version-bytes-{name}")
        r3, r2 = Path(self.inputs["candidateFeed"]), Path(self.inputs["r2Feed"])
        path = root / Path(self.packages[name]["archive"]).name
        if name in R2_IDS:
            original = r2
            r2 = root / "feed"
            path = r2 / path.name
            for proof in ("manifest.json", "source.patch", "du-core-candidate-source.json"):
                shutil.copyfile(original.parent / proof, root / proof)
        else:
            original = r3
            r3 = root / "feed"
            path = r3 / path.name
        shutil.copytree(original, root / "feed")
        edited_zip(path, lambda _: {"diagnostic-same-version.txt": b"modified archive"})
        command = [sys.executable, "-B", str(ROOT / "eng/verify.py"), "--profile", PROFILE,
                   "--dotnet", str(self.dotnet), "--candidate-manifest", self.inputs["candidateManifest"],
                   "--candidate-feed", str(r3), "--candidate-symbols", self.inputs["candidateSymbols"],
                   "--r2-feed", str(r2), "--evidence-root", str(root)]
        with (root / "entry.log").open("w") as stream:
            process = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        require(process.returncode == 1, f"{root.name} CLI 应退出 1")
        report_path, = root.glob("r3-module-zero-*/report.json")
        report = read_json(report_path)
        case_report(report, "packages", (name, "SHA-256 不符"))
        self.results(root.name, "实测 CLI 与改字节副本", report, report_path)

    def wrong_nuspec_range(self):
        root = self.create("wrong-nuspec-range")
        feed = root / "feed"
        feed.mkdir()
        original = self.packages[TOP_PACKAGE]
        stored = Path(original["archive"])
        path = Path(shutil.copyfile(stored, feed / stored.name))

        def edit(archive):
            name, = (file for file in archive.namelist() if file.endswith(".nuspec"))
            before = archive.read(name)
            after = before.replace(f'version="[{R2_VERSION}]"'.encode(), f'version="{R2_VERSION}"'.encode())
            require(before != after, "范围夹具没有改动精确依赖声明")
            return {name: after}

        edited_zip(path, edit)
        entry = deepcopy(read_json(Path(self.inputs["candidateManifest"]))["packages"][TOP_PACKAGE])
        # 本夹具只替换内层摘要，让语义验证实际执行。
        entry["package"]["sha256"] = sha256(path)
        write_json(root / "fixture-entry.json", entry)
        run = ModuleZeroRun(root, self.dotnet, True)

        def check():
            read_r3(feed, Path(self.inputs["candidateSymbols"]), TOP_PACKAGE, self.version, entry,
                    self.candidate["source"], expected_edges(self.version)[TOP_PACKAGE])

        self.staged(root, "模拟封装语义", "packages", (TOP_PACKAGE, "nuspec 框架依赖 ID 或范围不符"), run, check)

    def asset_cases(self):
        work = self.accepted / "consumer"
        assets = read_json(work / "obj/project.assets.json")
        key = f"{TOP_PACKAGE}/{self.version}"
        file = self.packages[TOP_PACKAGE]["asset"]
        for label, expected in (("wrong-restored-range", "依赖范围不符"),
                                ("wrong-asset-owner", "错目标、缺失或多来源")):
            root = self.create(label)
            data = deepcopy(assets)
            graph = data["targets"][TFM]
            if label == "wrong-restored-range":
                graph[key]["dependencies"][R2_IDS[-1]] = R2_VERSION
            else:
                next(item for name, item in graph.items() if name.startswith("Castle.Core/"))["compile"][file] = {}
            fixture = root / "project.assets.json"
            write_json(fixture, data)
            run = ModuleZeroRun(root, self.dotnet, True)

            def check():
                check_assets(read_json(fixture), work / "ModuleZeroProbe.csproj", work / "packages",
                             {R2_VERSION: work / "feed-r2", self.version: work / "feed-r3"}, self.packages)

            self.staged(root, "模拟还原证据", "assets", (TOP_PACKAGE, expected), run, check)

    def role_cases(self):
        observed = read_json(self.accepted / "probe/probe.json")
        database = self.accepted / "probe/roles.sqlite"
        self.verify_role_cases(observed, database)

    def verify_role_cases(self, observed, database):
        cases = {
            "missing-transaction-commit": "缺少同一角色仓储 DbContext 的 SQLite 事务提交",
            "missing-unit-completion": "工作单元完成与两次独立读回的顺序不符",
            "reused-read-context": "独立读回必须使用各自的作用域、工作单元和 DbContext",
            "missing-own-role": "缺少正确的本租户角色读回",
            "missing-cross-tenant-null": "明确返回 null",
            "cross-tenant-role-visible": "明确返回 null",
        }
        for label, expected in cases.items():
            root = self.create(label)
            fixture = deepcopy(observed)
            first = fixture["reads"][0]
            if label == "missing-transaction-commit":
                del fixture["commits"][-1]
            elif label == "missing-unit-completion":
                del fixture["writes"][0]["completedSequence"]
            elif label == "reused-read-context":
                first["work"]["contextId"] = fixture["writes"][0]["work"]["contextId"]
            elif label == "missing-own-role":
                del first["own"]["result"]
            elif label == "missing-cross-tenant-null":
                del first["other"]["result"]
            else:
                first["other"]["result"] = fixture["writes"][1]["role"]
            evidence = root / "probe.json"
            write_json(evidence, fixture)
            run = ModuleZeroRun(root, self.dotnet, True)
            run.report.update(process=self.report["process"], originalRun=str(self.accepted))
            report = self.staged(root, "模拟进程报告", "roles", (expected,), run,
                                 lambda: check_roles(read_json(evidence), database, observed["marker"]))
            require(report["process"]["exitCode"] == 0, f"{label} 需沿用实际进程退出 0 的结果")


def legacy_dispatch(root, inputs):
    root.mkdir()
    verify_dispatch(root)
    options = [flag for name in ("candidateFeed", "candidateManifest", "candidateSymbols", "r2Feed")
               for flag in ({"candidateFeed": "--candidate-feed", "candidateManifest": "--candidate-manifest",
                             "candidateSymbols": "--candidate-symbols", "r2Feed": "--r2-feed"}[name], inputs[name])]
    options += ["--evidence-root", str(root), "--dotnet", str(root / "dotnet")]
    args = ["verify.py", "--profile", "r3-signalr-log4net", *options, "--strict-runtime-baseline"]
    with patch.object(sys, "argv", args), patch.object(r3_leaf_verify, "execute", return_value=47) as entry:
        require(verify.main() == 47 and entry.call_args.args[0].strict_runtime_baseline,
                "前批 R3 的参数分派失效")
    args = ["verify.py", "--profile", "r3-web-host", "--evidence-root", str(root)]
    with patch.object(sys, "argv", args), patch.object(r3_web_host, "execute", return_value=49) as entry:
        require(verify.main() == 49 and entry.call_args.args[0].evidence_root == root,
                "原版 Web.Host 的参数分派失效")
    for profile in ("r0", "r2", "r3-web-host"):
        invalid = ["verify.py", "--profile", profile, "--strict-runtime-baseline"]
        stderr = io.StringIO()
        with patch.object(sys, "argv", invalid), redirect_stderr(stderr):
            try:
                verify.main()
            except SystemExit as error:
                require(error.code == 2, f"{profile} 应拒绝 R3 严格参数并退出 2")
            else:
                raise verify.VerificationError(f"{profile} 接受了 R3 严格参数")
        (root / f"{profile}-invalid.log").write_text(stderr.getvalue(), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accepted_run", type=Path)
    parser.add_argument("new_evidence", type=Path)
    args = parser.parse_args()
    output = args.new_evidence.resolve()
    output.mkdir()
    test = Diagnostics(args.accepted_run.resolve(), output)
    legacy_dispatch(output / "legacy-dispatch", test.inputs)
    test.same_version_bytes(R2_IDS[-1])
    test.same_version_bytes(R3_IDS[0])
    test.wrong_nuspec_range()
    test.asset_cases()
    test.role_cases()
    test.missing_transitive()
    write_json(output / "summary.json", {"exitCode": 0, "validatedRun": str(test.accepted), "cases": test.cases})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
