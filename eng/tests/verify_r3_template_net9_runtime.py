"""用已核对的真实构建和专用 SQL 实例复验换包入口的业务负例。"""

import argparse
from contextlib import contextmanager
import copy
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_template_net9_runtime import CandidateRuntime, verify_host_assemblies
from r3_template_runtime import CREDENTIALS
from r3_web_host import artifact, write_json
from verify import ROOT, VerificationError, make_run_directory, read_json, require


SQL_CASES = {
    "early_backup": ("sql_preflight", "冻结备份摘要不符"),
    "occupied_database": ("sql_preflight", "目标已存在"),
    "wrong_migration_target": ("migrator", "实际迁移连接目标不符"),
    "missing_migration_target": ("migrator", "缺少迁移连接证据"),
    "login_count_drift": ("browser", "提交前成功登录计数预期两库各 1"),
    "wrong_login_target": ("browser", "登录写入目标或增量不符"),
}


class SqlDiagnostic(CandidateRuntime):
    def __init__(self, args, base, case):
        evidence = make_run_directory(args.evidence_root, case + "-")
        super().__init__(ROOT, evidence, args.frozen_root, args.runtime_config)
        self.base = base
        self.case = case
        self.early_backup = args.early_backup
        self.report["diagnostic"] = {"case": case, "kind": "real", "build": str(args.passed_run)}
        for name, target in (("Web.Host", self.output), ("Migrator", self.migrator_output)):
            manifest = args.passed_run / (name + "-output.json")
            shutil.copyfile(manifest, self.evidence / manifest.name)
            built = args.passed_run / target.relative_to(evidence)
            for file in read_json(manifest)["files"]["files"]:
                destination = target / file
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(built / file, destination)

    def observer_from_full_run(self):
        expected = self.base["inputs"]["startupObserver"]
        shutil.copytree(Path(self.report["diagnostic"]["build"]) / Path(expected["path"]).parent,
                        self.evidence / "observer")
        self.observer = self.evidence / "observer/Observer.dll"
        actual = artifact(self.observer, self.evidence)
        require(actual["sha256"] == expected["sha256"], "诊断的观测器与全流程构建证据不符")
        self.report["inputs"]["startupObserver"] = actual
        self.dotnet = Path(self.base["environment"]["dotnet"])

    def sql_preflight(self):
        if self.case == "early_backup":
            self.backup["name"] = self.early_backup
        self.sql_inputs(self.backup)
        if self.case == "early_backup":
            self.report["diagnostic"]["earlyBackup"] = artifact(self.db.local_backup, self.db.local_backup.parent)
        if self.case == "occupied_database":
            self.db.require_new_database(self.db.source)
            self.db.query("master", f"CREATE DATABASE [{self.db.source}]")
        self.report["sql"] = self.db.preflight(frozen_backup=self.backup)

    def process_environment(self, entry):
        if entry == "Migrator" and self.case == "missing_migration_target":
            return {}
        return super().process_environment(entry)

    @contextmanager
    def process(self, output, entry, arguments, database, label, *, trace=False):
        if (entry, self.case) in (("Migrator", "wrong_migration_target"), ("Web.Host", "wrong_login_target")):
            database = self.db.restored
        with super().process(output, entry, arguments, database, label, trace=trace) as process:
            yield process

    def round(self, database, label, *, before_login=None):
        def drift_before_login():
            self.db.query(self.db.restored, """
INSERT dbo.AbpUserLoginAttempts (CreationTime, Result, TenancyName, TenantId, UserId, UserNameOrEmailAddress)
VALUES (SYSUTCDATETIME(), 1, N'Default', 1, 2, N'admin')
""")
            before_login()

        callback = drift_before_login if self.case == "login_count_drift" else before_login
        return super().round(database, label, before_login=callback)

    def execute_diagnostic(self):
        steps = (("runtime_inputs", self.inputs), ("observer_build", self.observer_from_full_run),
                 ("angular_freeze", self.angular), ("sql_preflight", self.sql_preflight),
                 ("restore_pair", self.restore_pair), ("migrator", self.migrate), ("browser", self.browser))
        expected_stage, expected_reason = SQL_CASES[self.case]
        code = self.execute_steps(steps)
        stages = self.report["stages"]
        require(code == 1 and stages[expected_stage]["status"] == "failed"
                and expected_reason in stages[expected_stage]["reason"] and stages["cleanup"]["status"] == "passed"
                and stages["frozen_inputs_after"]["status"] == "passed",
                f"{self.case} 未在 {expected_stage} 按预期失败，详见 {self.report_path}")
        if expected_stage in ("sql_preflight", "migrator"):
            require(stages["browser"]["commands"] == [] and stages["browser"]["status"] == "not_run",
                    f"{self.case} 失败后仍启动 Host")
        if expected_stage == "sql_preflight":
            require(not any("RESTORE DATABASE" in item["statement"] for item in self.db.commands),
                    f"{self.case} 失败后仍恢复了数据库")
        elif expected_stage == "migrator":
            command, = stages["migrator"]["commands"]
            target = self.report["sql"]["migrationConnection"]
            require(command["exitCode"] == 0 and len(self.report["sql"]["beforeMigration"]) == 2
                    and all(len(state["migrations"]) == 30 for state in self.report["sql"]["beforeMigration"].values()),
                    f"{self.case} 没有保留正常退出和相同迁移起点的真实负例")
            if self.case == "wrong_migration_target":
                require(target["observed"] and {row["database"] for row in target["observed"]} == {self.db.restored}
                        and {row["pid"] for row in target["observed"]} == {command["pid"]},
                        "真实错连未从该 Migrator 的迁移连接观察到对照库")
            else:
                require(not target["observed"], "无观测器诊断仍有连接证据")
        else:
            outcome = self.report["rounds"]["candidate"]
            counters = self.report["sql"]["loginComparison"]
            if self.case == "login_count_drift":
                require("tenant" in outcome["steps"] and "authentication" not in outcome["steps"]
                        and counters["before"] == {self.db.source: 1, self.db.restored: 2}
                        and "after" not in counters, "漂移后浏览器仍提交了登录")
            else:
                require(outcome["steps"] == self.baseline["rounds"]["restore"]["steps"]
                        and counters["after"] == {self.db.source: 1, self.db.restored: 2},
                        "写错目标负例缺少成功的真实浏览器或数据库证据")
        return {"kind": "real", "case": self.case, "report": str(self.report_path), "exitCode": code,
                "failedStage": expected_stage, "reason": stages[expected_stage]["reason"]}


def check_assembly_failures(passed, base):
    observed = read_json(passed / "host-loaded.json")
    expected = read_json(passed / "Web.Host-output.json")
    launch = base["rounds"]["candidate"]["host"]
    output = Path(launch["cwd"])
    cases = ("core_runtime_patch", "aspnet_runtime_patch", "startup_runtime_patch", "wrong_assembly_origin",
             "wrong_assembly_digest", "duplicate_engine", "missing_abp_assembly", "wrong_pid")
    result = {}
    for case in cases:
        sample, process = copy.deepcopy(observed), copy.deepcopy(launch)
        rows = sample["assemblies"]
        if case in ("core_runtime_patch", "aspnet_runtime_patch"):
            shared, anchor = (("Microsoft.NETCore.App", "System.Private.CoreLib") if case.startswith("core") else
                              ("Microsoft.AspNetCore.App", "Microsoft.AspNetCore.Hosting"))
            row = next(row for row in rows if row["name"] == anchor)
            row["path"] = str(Path(row["path"]).parent.parent / "9.0.99" / Path(row["path"]).name)
            reason = f"{shared}=9.0.99 (启动选择 9.0.10)"
        elif case == "startup_runtime_patch":
            shared = "Microsoft.NETCore.App"
            process["sharedRuntime"][shared]["version"] = "9.0.99"
            reason = f"{shared}=9.0.10 (启动选择 9.0.99)"
        elif case == "wrong_assembly_origin":
            next(row for row in rows if row["name"] == "Abp")["path"] = "/fixture/Abp.dll"
            reason = "Abp 从本轮输出之外加载"
        elif case == "wrong_assembly_digest":
            next(row for row in rows if row["name"] == "Abp")["sha256"] = "0" * 64
            reason = "Abp 加载位置或摘要与登记归档、输出不一致"
        elif case == "duplicate_engine":
            engine = next(row for row in rows if row["name"] == "AutoMapper")
            rows.append(engine | {"contextId": engine["contextId"] + 1, "context": "fixture"})
            reason = "AutoMapper 加载记录应唯一"
        elif case == "missing_abp_assembly":
            rows[:] = [row for row in rows if row["name"] != "Abp.Zero.Common"]
            reason = "Abp.Zero.Common 加载记录应唯一"
        else:
            sample["pid"] += 1
            reason = "运行程序集证据 PID 不符"
        try:
            verify_host_assemblies(sample, process, output, expected, {})
        except VerificationError as failure:
            require(reason in str(failure), f"{case} 失败原因不符：{failure}")
            result[case] = {"kind": "fixture", "exitCode": 1, "reason": str(failure)}
        else:
            raise VerificationError(f"{case} 未被程序集核验拒绝")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("passed_run", type=lambda value: Path(value).resolve())
    parser.add_argument("evidence_root", type=lambda value: Path(value).resolve())
    parser.add_argument("frozen_root", type=lambda value: Path(value).resolve())
    parser.add_argument("runtime_config", type=lambda value: Path(value).resolve())
    parser.add_argument("--early-backup", required=True, help="已挂载早期备份的文件名")
    args = parser.parse_args()
    require(Path(args.early_backup).name == args.early_backup, "早期备份须为文件名")
    for name in ("DEBUG", "PWDEBUG"):
        os.environ.pop(name, None)
    credentials = {name: os.environ[name] for name in CREDENTIALS}
    base = read_json(args.passed_run / "report.json")
    require(base["profile"] == "r3-template-net9-packages-runtime" and base["status"] == "passed",
            "诊断要求从真实完整候选通过轮取得构建和运行观测")
    args.evidence_root.mkdir(parents=True, exist_ok=True)
    cases = {"real": [], "fixtures": check_assembly_failures(args.passed_run, base)}
    summary = args.evidence_root / "diagnostics.json"
    write_json(summary, cases)
    for case in SQL_CASES:
        os.environ.update(credentials)
        runner = SqlDiagnostic(args, base, case)
        cases["real"].append(runner.execute_diagnostic())
        write_json(summary, cases)
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
