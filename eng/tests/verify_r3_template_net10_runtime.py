"""在独立 SQL 库和正式运行证据副本上验证升级拒绝路径。"""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_leaf_packages import checked_file
from r3_template_net10_runtime import PATCH_VERSION, PROFILE, UpgradeRuntime
from r3_template_net9_runtime import check_migration_target, verify_host_assemblies
from r3_template_runtime import CREDENTIALS
from r3_web_host import artifact, project_path, write_json
from verify import ROOT, VerificationError, make_run_directory, read_json, require, sha256


REAL_CASES = {
    "net9_migrator": ("net10_migrator", f"共享运行时补丁偏离 {PATCH_VERSION}"),
    "wrong_migration_target": ("net10_migrator", "实际迁移连接目标不符"),
    "missing_migration_target": ("net10_migrator", "缺少迁移连接证据"),
    "missing_previous_login": ("net10_browser", "业务起点登录记录预期"),
    "wrong_login_target": ("net10_browser", "登录写入目标或行增量不符"),
}
FIXTURE_CASES = (
    ("wrong_runtime_major", "System.Private.CoreLib", "path", "9.0.10", "Microsoft.NETCore.App=9.0.10"),
    ("wrong_runtime_patch", "Microsoft.AspNetCore.Hosting", "path", "10.0.3", "Microsoft.AspNetCore.App=10.0.3"),
    ("wrong_framework_origin", "Abp", "path", "/fixture/Abp.dll", "Abp 从本轮输出之外加载"),
    ("wrong_provider_digest", "Microsoft.EntityFrameworkCore.SqlServer", "sha256", "0" * 64,
     "Microsoft.EntityFrameworkCore.SqlServer 加载位置或摘要与登记归档、输出不一致"),
)


def supplied_file(root, relative, digest=None):
    relative = Path(relative)
    path = root / relative
    require(not relative.is_absolute() and ".." not in relative.parts and path == path.resolve(),
            f"通过轮实物必须是传入目录中的常规文件：{relative}")
    if digest is not None:
        return checked_file(root, relative, digest)
    require(path.is_file(), f"缺少实物 {path}")
    return path


def supplied_output(root, base, phase, entry):
    registered = base["inputs"]["entryOutputs"][phase][entry]
    manifest = supplied_file(root, registered["path"], registered["sha256"])
    output = manifest.parent.relative_to(root) / "source/aspnet-core" / project_path(entry).parent / (
        f"bin/Release/{phase}.0")
    expected = read_json(manifest)
    files = {name: supplied_file(root, output / name, digest) for name, digest in expected["files"]["files"].items()}
    return manifest, output, expected, files


def fixture_cases(passed_run, base, evidence):
    passed_run = passed_run.resolve(strict=True)
    observed_path = supplied_file(passed_run, "net10-host-loaded.json")
    observed = read_json(observed_path)
    manifest, output_relative, expected, files = supplied_output(passed_run, base, "net10", "Web.Host")
    browser = base["rounds"]["net10"]
    launch = browser["host"]
    recorded_output = Path(launch["cwd"])
    entry = expected["entry"]["path"]
    require(recorded_output.is_absolute() and ".." not in recorded_output.parts
            and Path(launch["argv"][1]) == recorded_output / entry
            and Path(browser["inputs"]["path"]) == output_relative / entry
            and expected["entry"]["sha256"] == browser["inputs"]["sha256"] == launch["entrySha256"]
            == expected["files"]["files"].get(entry),
            "正式轮报告中的 Host 启动记录、入口相对路径或摘要不一致")
    output = passed_run / output_relative
    copies = {recorded_output / name: path for name, path in files.items()}

    def verify_sample(sample):
        # 只为已登记的原始输出路径选取相对位置相同、摘要已核对的副本。原始观测及夹具文件保留原路径。
        rows = []
        for row in sample["assemblies"]:
            path = Path(row["path"])
            copied = copies.get(path)
            if copied is None:
                require(not path.is_relative_to(output),
                        f"Host PID {launch['pid']} 的 {row['name']} 从本轮输出之外加载：{path}")
                rows.append(row)
            else:
                rows.append(row | {"path": str(copied)})
        verify_host_assemblies(sample | {"assemblies": rows}, launch, output, expected, {},
                               runtime_version=PATCH_VERSION)

    verify_sample(observed)
    write_json(evidence / "fixture-baseline.json", {
        "pid": observed["pid"], "originalOutput": str(recorded_output), "suppliedOutput": str(output),
        "manifest": artifact(manifest, passed_run), "observed": artifact(observed_path, passed_run),
        "verifiedFiles": len(files),
    })
    results = []
    for case, assembly, key, value, reason in FIXTURE_CASES:
        fixture = deepcopy(observed)
        row = next(row for row in fixture["assemblies"] if row["name"] == assembly)
        if case.startswith("wrong_runtime_"):
            original = Path(row["path"])
            value = str(original.parent.parent / value / original.name)
        row[key] = value
        input_path = evidence / f"{case}.json"
        write_json(input_path, fixture)
        try:
            verify_sample(fixture)
        except VerificationError as error:
            require(reason in str(error), f"{case} 失败原因不符：{error}")
            results.append({"case": case, "kind": "fixture", "assertionRejected": True, "reason": str(error),
                            "input": artifact(input_path, evidence), "baseline": str(observed_path)})
        else:
            raise VerificationError(f"{case} 未被拒绝")
    return results


class Diagnostic(UpgradeRuntime):
    def __init__(self, args, baseline, case):
        evidence = make_run_directory(args.evidence_root, f"{case}-")
        super().__init__(ROOT, evidence, args.frozen_root, args.runtime_config, Path(baseline["environment"]["dotnet"]))
        self.baseline_run = baseline
        self.case = case
        self.passed_run = args.passed_run
        self.report["diagnostic"] = {"case": case, "kind": "real", "passedRun": str(self.passed_run),
                                     "reportSha256": sha256(self.passed_run / "report.json")}
        self.copy_outputs()

    def copy_outputs(self):
        for phase, directory in self.builds.items():
            directory.mkdir(exist_ok=True)
            for entry in ("Web.Host", "Migrator"):
                manifest, relative, _, files = supplied_output(self.passed_run, self.baseline_run, phase, entry)
                shutil.copyfile(manifest, directory / f"{entry}-output.json")
                target = directory / relative.relative_to(manifest.parent.relative_to(self.passed_run))
                for filename, origin in files.items():
                    destination = target / filename
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(origin, destination)

    def build_observer(self):
        record = self.baseline_run["inputs"]["startupObserver"]
        source = supplied_file(self.passed_run, record["path"], record["sha256"])
        self.observer = self.evidence / "Observer.dll"
        shutil.copyfile(source, self.observer)
        self.report["inputs"]["startupObserver"] = artifact(self.observer, self.evidence)

    def restore_pair(self):
        sql = self.report["sql"]
        checkpoint = self.baseline_run["sql"]["checkpoints"]["before_upgrade"]
        if self.case == "missing_previous_login":
            restored = self.db.restore(sql["backup"], database=self.db.source)
        else:
            restored = self.db.restore_diagnostic_start(checkpoint["media"])
        control = self.db.restore(sql["backup"], database=self.db.restored)
        sql["restores"] = {self.db.source: restored, self.db.restored: control}
        sql["databaseIdentities"] = {database: self.db.state_identity(database) for database in sql["restores"]}
        require(all(state == self.business for state in self.sql_state().values()), "诊断起点迁移历史或业务数据不符")
        recorded_control = self.baseline_run["sql"]["initialLoginRows"][self.baseline_run["sql"]["restoreDatabase"]]
        sql["upgradeStartLoginRows"] = {self.db.source: checkpoint["loginRows"], self.db.restored: recorded_control}
        actual = self.login_rows()
        expected = {self.db.source: recorded_control, self.db.restored: recorded_control} \
            if self.case == "missing_previous_login" else sql["upgradeStartLoginRows"]
        require(actual == expected, f"诊断起点的实际登录行不符：{actual}")
        sql["diagnosticStartLoginRows"] = actual

    def launch_migrator(self, phase, database):
        if self.case == "net9_migrator":
            phase = "net9"
        if self.case == "wrong_migration_target":
            database = self.db.restored
        return super().launch_migrator(phase, database)

    def process_environment(self, entry):
        env = super().process_environment(entry)
        if self.case == "missing_migration_target" and entry == "Migrator":
            # 保留真实连接观测到另一文件，使验收入口确实缺少所要求的关联记录。
            env["R3_TEMPLATE_OBSERVER_EVIDENCE"] = str(self.evidence_file("unregistered-migrator-target.jsonl"))
        return env

    def round(self, database, label, *, before_login=None):
        if self.case == "wrong_login_target":
            database = self.db.restored
        return super().round(database, label, before_login=before_login)

    def verify_rejection(self, code):
        stage, expected_reason = REAL_CASES[self.case]
        stages = self.report["stages"]
        reason = stages[stage].get("reason", "")
        require(code == 1 and stages[stage]["status"] == "failed" and expected_reason in reason
                and all(stages[item]["status"] == "passed" for item in ("cleanup", "frozen_inputs_after")),
                f"{self.case} 未在 {stage} 按预期拒绝，详见 {self.report_path}")
        sql = self.report["sql"]
        if stage == "net10_migrator":
            require(stages["net10_browser"]["status"] == "not_run" and not stages["net10_browser"]["commands"],
                    f"{self.case} 失败后启动了 .NET 10 Host")
            record = sql["migrations"]["net10"]
            launch = record["launch"]
            observed = record["connection"]["observed"]
            require(launch["exitCode"] == 0 and record["beforeLoginRows"] == sql["upgradeStartLoginRows"],
                    f"{self.case} 缺少退出 0 的真实迁移或 2/1 起点：{record}")
            if self.case == "net9_migrator":
                require(observed and {row["database"] for row in observed} == {self.db.source}
                        and {row["version"] for row in launch["sharedRuntime"].values()} == {"9.0.10"}
                        and "/net9.0/" in launch["argv"][1],
                        "真实 .NET 9 Migrator 缺少正确候选库和实际运行时证据")
            elif self.case == "wrong_migration_target":
                require(observed and {row["database"] for row in observed} == {self.db.restored}
                        and {row["pid"] for row in observed} == {launch["pid"]},
                        "真实错连缺少同 PID 连接到对照库的证据")
            else:
                path = self.evidence / "unregistered-migrator-target.jsonl"
                require(not observed and path.is_file(), "缺连接诊断未确认独立观测文件存在")
                independent = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                check_migration_target(independent, launch["pid"], sql["serverName"], self.db.source)
        else:
            steps = self.report["rounds"]["net10"]["steps"]
            round_data = sql["businessRounds"]["net10"]
            if self.case == "missing_previous_login":
                require("tenant" in steps and "authentication" not in steps and "afterLoginRows" not in round_data
                        and round_data["beforeLoginRows"] == sql["diagnosticStartLoginRows"],
                        "缺前一条登录的诊断仍提交了认证")
            else:
                before, after = round_data["beforeLoginRows"], round_data["afterLoginRows"]
                require(steps == self.baseline_run["rounds"]["net10"]["steps"]
                        and self.report["rounds"]["net10"]["host"]["database"] == self.db.restored
                        and len(after[self.db.restored]) == 2 and after[self.db.restored][:1] == before[self.db.restored]
                        and after[self.db.source] == before[self.db.source],
                        "错库诊断缺少真实成功业务、候选库原行和对照库新增行")
        return {"case": self.case, "kind": "real", "exitCode": code, "failedStage": stage, "reason": reason,
                "report": str(self.report_path), "reportSha256": sha256(self.report_path)}

    def execute_diagnostic(self):
        steps = [("runtime_inputs", self.inputs), ("observer_build", self.build_observer),
                 ("angular_freeze", self.angular), ("sql_preflight", self.sql_preflight),
                 ("restore_pair", self.restore_pair)]
        if self.case != "missing_previous_login":
            steps.append(("net10_migrator", self.migrate_net10))
        steps.append(("net10_browser", self.browser_net10))
        return self.verify_rejection(self.execute_steps(steps))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--passed-run", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--frozen-root", type=Path)
    parser.add_argument("--runtime-config", type=Path)
    parser.add_argument("--fixtures-only", action="store_true", help="仅核对通过轮副本及 Host 观测夹具")
    args = parser.parse_args()
    if not args.fixtures_only and (args.frozen_root is None or args.runtime_config is None):
        parser.error("真实诊断需要 --frozen-root 和 --runtime-config")
    args.passed_run = args.passed_run.resolve(strict=True)
    base = read_json(supplied_file(args.passed_run, "report.json"))
    require(base["profile"] == PROFILE and base["status"] == "passed" and base["exitCode"] == 0,
            "诊断需要完整实际通过轮")
    evidence = make_run_directory(args.evidence_root, "r3-net10-runtime-diagnostics-")
    summary = evidence / "diagnostics.json"
    results = {"real": [], "fixtures": fixture_cases(args.passed_run, base, evidence),
               "fixtureBaseline": artifact(evidence / "fixture-baseline.json", evidence)}
    write_json(summary, results)
    print(summary, flush=True)
    if args.fixtures_only:
        return 0
    args.frozen_root = args.frozen_root.resolve(strict=True)
    for name in ("DEBUG", "PWDEBUG"):
        os.environ.pop(name, None)
    credentials = {name: os.environ[name] for name in CREDENTIALS}
    for case in REAL_CASES:
        os.environ.update(credentials)
        results["real"].append(Diagnostic(args, base, case).execute_diagnostic())
        write_json(summary, results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
