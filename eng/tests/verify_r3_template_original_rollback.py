"""用独立回退数据库与正式观测副本验证拒绝路径。"""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_template_original_rollback import ROLES, RollbackRun, verify_query_target
from r3_template_runtime import CREDENTIALS
from r3_web_host import artifact, write_json
from verify import ROOT, VerificationError, make_run_directory, read_json, require
from verify_r3_template_net10_runtime import supplied_output


REAL_CASES = {
    "maintenance_migrator": ("after_upgrade", "migrator", "启动入口与原版清单不符"),
    "wrong_migration_database": ("after_upgrade", "migrator", "迁移连接目标不符"),
    "original_third_before_login": ("before_upgrade", "browser", "认证前含升级轮原行 3"),
    "wrong_login_database": ("before_upgrade", "login_write", "登录写入目标或行增量不符"),
    "search_failure_after_login": ("after_upgrade", "browser", "User/GetAll HTTP 500"),
}


class DiagnosticRun(RollbackRun):
    def __init__(self, args, root, case):
        super().__init__(ROOT, make_run_directory(root, case + "-"), args.frozen_root, args.rollback_upgrade_run,
                         args.runtime_config, args.dotnet)
        self.case = case
        self.report["diagnostic"] = {"case": case, "kind": "real"}

    def launch_migrator(self, database):
        if self.case == "wrong_migration_database":
            return super().launch_migrator(self.databases["before_upgrade"])
        if self.case != "maintenance_migrator":
            return super().launch_migrator(database)
        evidence, relative, expected, files = supplied_output(
            self.upgrade_run, read_json(self.upgrade_run / "report.json"), "net9", "Migrator")
        output = self.evidence / "maintenance-migrator"
        for filename, origin in files.items():
            destination = output / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, destination)
        self.report["diagnostic"]["maintenanceInput"] = {
            "manifest": artifact(evidence, self.upgrade_run), "output": str(relative),
            "entry": expected["entry"], "files": len(files),
        }
        with self.process(output, "Migrator", ["-q"], database, f"{self.role}-migrator", trace=True) as (
                process, log, launch):
            process.wait(timeout=300)
        return launch, log

    def browser_database(self, target, control):
        return control if self.case == "wrong_login_database" else target

    def process_environment(self, entry):
        env = super().process_environment(entry)
        if self.case == "search_failure_after_login" and self.role == "after_upgrade" and entry == "Web.Host":
            env["R3_TEMPLATE_OBSERVER_FAIL_LIST"] = "1"
        return env

    def browser(self, target, control, record):
        if self.case == "original_third_before_login":
            # 仅向本轮已核准的升级前诊断库加入实际升级轮原行，保留 datetime2 精度。
            self.db.query(target, f"""
SET IDENTITY_INSERT dbo.AbpUserLoginAttempts ON;
INSERT INTO dbo.AbpUserLoginAttempts
    (Id, CreationTime, Result, TenantId, UserId, TenancyName, UserNameOrEmailAddress)
SELECT Id, CreationTime, Result, TenantId, UserId, TenancyName, UserNameOrEmailAddress
FROM [{control}].dbo.AbpUserLoginAttempts
WHERE Id = 3 AND TenantId = 1 AND UserId = 2 AND Result = 1;
SET IDENTITY_INSERT dbo.AbpUserLoginAttempts OFF;
""")
        super().browser(target, control, record)

    def execute_diagnostic(self, role):
        if self.case == "search_failure_after_login":
            return self.execute_full()
        return self.execute_steps((*self.input_steps(), ("observer_build", self.build_observer),
                                   (role, lambda: self.run_path(role))), business=True)


def check_diagnostic(run, code, role, phase, reason):
    result = run.report["paths"][role]
    require(code == result["exitCode"] == 1 and result["status"] == "failed"
            and result["failurePhase"] == phase and reason in result["reason"],
            f"{run.case} 失败阶段或原因不符，见 {run.report_path}")
    target, control = (result[key] for key in ("target", "control"))
    if phase == "migrator":
        record = result["migrator"]
        actual = target if run.case == "maintenance_migrator" else control
        require(record["launch"]["exitCode"] == 0 and record["connections"]["observed"]
                and {row["database"] for row in record["connections"]["observed"]} == {actual}
                and "browser" not in result, f"{run.case} 未经过真实迁移或启动了 Host")
        return
    browser = result["browser"]
    steps = browser["outcome"]["steps"]
    if run.case == "original_third_before_login":
        require("authentication" not in steps and not browser.get("authenticationMayHaveStarted")
                and browser["beforeLoginRows"][target][-1] == run.checkpoints["after_upgrade"]["loginRows"][-1],
                "诊断未在提交认证前拒绝升级轮原行 3")
        require(run.login_rows() == browser["beforeLoginRows"], "认证拒绝后成功登录行变化")
    elif run.case == "wrong_login_database":
        diff = browser["loginDifferences"]
        require(steps["search"]["status"] == 200 and steps["search"]["items"] == run.business["matches"]
                and diff[target] == {"status": "known", "added": [], "removed": []}
                and len(diff[control]["added"]) == 1 and diff[control]["removed"] == [],
                "对照库写入诊断未完成真实查询或未观察到唯一新增行")
    else:
        second = run.report["paths"]["before_upgrade"]
        diff = browser["loginDifferences"]
        require(steps["authentication"]["success"] and steps["search"]["status"] == 500
                and browser["readTarget"]["events"][-1]["status"] == 500
                and diff[target] == {"status": "known", "added": [browser["addedLogin"]], "removed": []}
                and diff[control] == {"status": "known", "added": [], "removed": []},
                "未在清理前记录查询首错及已提交的真实登录")
        require(second["status"] == "passed" and second["exitCode"] == 0
                and {target, control}.isdisjoint({second["target"], second["control"]})
                and reason in run.report["reason"], "独立升级前路径未通过或第一路径首错丢失")


def check_query_fixtures(passed, evidence):
    original = read_json(passed / "report.json")
    require(original["status"] == "passed" and original["exitCode"] == 0 and not original.get("diagnostic"),
            "查询夹具需要正式通过轮")
    outcome = original["paths"]["after_upgrade"]["browser"]
    target = outcome["readTarget"]["expected"]
    search = outcome["outcome"]["steps"]["search"]
    observed = passed / "after_upgrade-host-search.jsonl"
    events = outcome["readTarget"]["events"]
    require(observed.is_file()
            and [json.loads(line) for line in observed.read_text().splitlines()] == events,
            "正式通过轮缺少匹配的 Host 原始查询观测")

    def verify(rows):
        verify_query_target(rows, target["pid"], target["serverName"], target["database"], search,
                            outcome["searchRequestId"], search["keyword"][0])

    verify(events)
    results = []
    for case, marker in (("count_control", "count 连接不符"), ("list_control", "list 连接不符"),
                         ("no_list_connection", "缺少唯一 list 实际 SQL 连接"),
                         ("initial_list", "缺少唯一 Host 关键词请求"),
                         ("foreign_request", "其他进程或请求"), ("foreign_pid", "其他进程或请求")):
        fixture = deepcopy(events)
        if case in ("count_control", "list_control"):
            step = case.split("_")[0]
            row = next(row for row in fixture if row["kind"] == "connection" and row["step"] == step)
            row["database"] = original["paths"]["after_upgrade"]["control"]
        elif case == "no_list_connection":
            fixture = [row for row in fixture if (row["kind"], row.get("step")) != ("connection", "list")]
        elif case == "initial_list":
            next(row for row in fixture if row["kind"] == "request")["keyword"] = ""
        elif case == "foreign_request":
            next(row for row in fixture if row["kind"] == "connection")["activityId"] += "-other"
        else:
            next(row for row in fixture if row["kind"] == "connection")["pid"] += 1
        path = evidence / f"{case}.json"
        write_json(path, fixture)
        try:
            verify(fixture)
        except VerificationError as error:
            require(marker in str(error), f"{case} 拒绝原因不符：{error}")
            results.append({"case": case, "kind": "fixture", "assertionRejected": True, "reason": str(error),
                            "fixture": artifact(path, evidence), "baseline": artifact(observed, passed)})
        else:
            raise VerificationError(f"{case} 未拒绝")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("frozen-root", "rollback-upgrade-run", "runtime-config", "evidence-root", "passed-run"):
        parser.add_argument("--" + key, required=True, type=lambda value: Path(value).resolve())
    parser.add_argument("--dotnet", type=Path)
    parser.add_argument("--case", choices=REAL_CASES)
    args = parser.parse_args()
    for name in ("PWDEBUG", "DEBUG"):
        os.environ.pop(name, None)
    credentials = {name: os.environ.pop(name) for name in CREDENTIALS}
    evidence = make_run_directory(args.evidence_root, "r3-original-rollback-diagnostics-")
    print(f"回退诊断记录：{evidence}", flush=True)
    results = []
    for case, (role, phase, reason) in REAL_CASES.items():
        if args.case and case != args.case:
            continue
        os.environ.update(credentials)
        run = DiagnosticRun(args, evidence, case)
        code = run.execute_diagnostic(role)
        check_diagnostic(run, code, role, phase, reason)
        results.append({"case": case, "kind": "real", "exitCode": code, "phase": phase,
                        "report": artifact(run.report_path, evidence)})
    fixtures = check_query_fixtures(args.passed_run, evidence) if not args.case else []
    write_json(evidence / "diagnostics.json", {"realCases": results, "fixtures": fixtures})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except VerificationError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
