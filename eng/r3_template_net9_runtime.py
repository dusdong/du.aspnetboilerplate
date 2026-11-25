"""完整模板维护包在最终返修恢复点的原版对照。"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys

from r3_leaf_packages import checked_file
from r3_template_net9_packages import CandidateRun
from r3_template_runtime import RuntimeSupport, inventory
from r3_web_host import PREFIX, artifact, project_path, write_json
from verify import ROOT, VerificationError, make_run_directory, read_json, require, sha256


PROFILE = "r3-template-net9-packages-runtime"
ORIGINAL = Path("r3-template-runtime/revision-1/runs/r3-template-runtime-89igcw5r")
ORIGINAL_REPORT = "d60dfea17e2d3ffe00d6b1914f429cca7cd60d2a114f913561d62dde0044985c"
ANGULAR_MANIFEST = "99a2520978f5917fdc98545dc043b90ff5f9f2ed83872b52dbb8e273fa71c12b"
SHARED = {"Microsoft.NETCore.App": "System.Private.CoreLib",
          "Microsoft.AspNetCore.App": "Microsoft.AspNetCore.Hosting"}
EXPECTED_RUNTIME = "9.0.10"
HOST_LIBRARIES = ("AutoMapper", "Microsoft.EntityFrameworkCore", "Microsoft.EntityFrameworkCore.Abstractions",
                  "Microsoft.EntityFrameworkCore.Relational", "Microsoft.EntityFrameworkCore.SqlServer",
                  "Microsoft.Data.SqlClient")
MIGRATION_EVENT = "Microsoft.EntityFrameworkCore.Database.Command.CommandExecuting"
RUNTIME_STAGES = ("runtime_inputs", "observer_build", "angular_freeze", "sql_preflight",
                  "restore_pair", "migrator", "browser", "loaded_assemblies", "comparison")


def check_migration_target(rows, pid, server, database):
    require(rows, f"Migrator PID {pid} 缺少迁移连接证据，预期 {server}/{database}")
    for row in rows:
        require(row.get("pid") == pid and row.get("eventName") == MIGRATION_EVENT
                and all(row.get(key) for key in ("migrator", "sessionId", "context", "connectionId",
                                                  "commandId", "clientConnectionId")),
                f"Migrator PID {pid} 的迁移连接记录无法关联：{row}")
        require((row.get("serverName"), row.get("database")) == (server, database),
                f"Migrator PID {pid} 实际迁移连接目标不符，预期 {server}/{database}，"
                f"实际 {row.get('serverName')}/{row.get('database')}")


def check_start_counts(counts, candidate, control):
    require(counts == {candidate: 1, control: 1}, f"提交前成功登录计数预期两库各 1，实际 {counts}")


def check_end_counts(counts, candidate, control):
    require(counts == {candidate: 2, control: 1},
            f"登录写入目标或增量不符，预期 {candidate}=2 / {control}=1，实际 {counts}")


def unique_loaded(rows, name, pid, *, optional=False, process_name="Host"):
    matches = [row for row in rows if (row.get("name") or "").casefold() == name.casefold()]
    if optional and not matches:
        return None
    require(len(matches) == 1, f"{process_name} PID {pid} 的 {name} 加载记录应唯一，实际 {matches}")
    row, = matches
    require(row["isDefaultContext"] is True and row["context"] == "Default"
            and row["contextId"] > 0 and row["moduleVersionId"]
            and row["name"] == name and row["fullName"].startswith(name + ", Version=")
            and row["diskFullName"] == row["fullName"] and Path(row["path"]).is_absolute(),
            f"{process_name} PID {pid} 的 {name} 实际程序集身份、上下文或文件不符：{row}")
    return row


def verify_shared_runtime(rows, launch, report, expected_version, *, anchors=SHARED, process_name="Host"):
    pid = launch["pid"]
    trace = launch["sharedRuntime"]
    shared = report["sharedRuntime"] = {}
    for name, anchor in anchors.items():
        row = unique_loaded(rows, anchor, pid, process_name=process_name)
        loaded = Path(row["path"])
        shared[name] = {"expectedVersion": expected_version, "actualVersion": loaded.parent.name,
                        "selectedAtStartup": trace[name], "loaded": row}
    require(all(record["actualVersion"] == expected_version
                and record["selectedAtStartup"]["version"] == expected_version for record in shared.values()),
            f"进程 PID {pid} 的共享运行时补丁偏离 {expected_version}："
            + ", ".join(f"{name}={record['actualVersion']} (启动选择 {record['selectedAtStartup']['version']})"
                        for name, record in shared.items()))
    for name, record in shared.items():
        row = record["loaded"]
        path = Path(row["path"])
        require(path.parent.parent.name == name and path.parent.parent.parent.name == "shared"
                and path.parent == Path(record["selectedAtStartup"]["path"]).resolve()
                and sha256(path) == row["sha256"],
                f"进程 PID {pid} 的 {name} 实际共享运行时文件不符：{row}")


def verify_host_assemblies(observed, launch, output, expected, report, *, runtime_version=EXPECTED_RUNTIME):
    pid = launch.get("pid")
    require(pid and observed.get("pid") == pid,
            f"运行程序集证据 PID 不符，Host {pid}，观测 {observed.get('pid')}")
    rows = observed["assemblies"]
    verify_shared_runtime(rows, launch, report, runtime_version)

    framework_names = {Path(path).stem for path, item in expected["maintenanceDlls"].items()
                       if item["package"].startswith("Du.Abp")}
    require(len(framework_names) == 11, f"Host 预期维护框架程序集不满 11 项：{sorted(framework_names)}")
    tracked = report["assemblies"] = {}
    for name in sorted(framework_names | set(HOST_LIBRARIES) | {"AutoMapper.Collection", PREFIX + "Web.Host"}):
        row = unique_loaded(rows, name, pid, optional=name == "AutoMapper.Collection")
        if name == PREFIX + "Web.Host":
            origins = {expected["entry"]["path"]: expected["entry"]}
        else:
            origins = {path: item for path, item in expected["packageCopies"].items()
                       if Path(path).name == name + ".dll"}
        require(origins, f"Host PID {pid} 的 {name} 缺少包或入口输出来源")
        if not row:
            tracked[name] = {"loaded": False, "outputOrigins": origins}
            continue
        path = Path(row["path"])
        tracked[name] = {"loaded": True, **row, "outputOrigins": origins}
        require(path.is_relative_to(output) and path == path.resolve(),
                f"Host PID {pid} 的 {name} 从本轮输出之外加载：{path}")
        relative = path.relative_to(output).as_posix()
        origin = origins.get(relative)
        require(origin and origin["sha256"] == expected["files"]["files"].get(relative)
                == sha256(path) == row["sha256"],
                f"Host PID {pid} 的 {name} 加载位置或摘要与登记归档、输出不一致：{path}")
        if name == "Microsoft.Data.SqlClient":
            require(relative.startswith("runtimes/unix/"), f"Host PID {pid} 的 SqlClient 未加载 Unix 资产：{relative}")
    contexts = {item["contextId"] for item in tracked.values() if item["loaded"]}
    contexts.update(item["loaded"]["contextId"] for item in report["sharedRuntime"].values())
    require(len(contexts) == 1, f"Host PID {pid} 运行程序集分属多个默认上下文：{contexts}")


class CandidateRuntime(RuntimeSupport, CandidateRun):
    runtime_stages = RUNTIME_STAGES

    def __init__(self, repo, evidence, frozen_root, runtime_config, dotnet=None):
        super().__init__(repo, evidence, frozen_root, dotnet)
        self.setup_runtime(runtime_config)
        self.browser_output = evidence / "angular-browser"
        self.migrator_output = self.root / project_path("Migrator").parent / f"bin/Release/{self.tfm}"
        self.report.update(profile=PROFILE, runId=self.run_id,
                           coverageNotRun=[".NET 10 / EF Core 10 升级", "升级后回退",
                                           "其他消费组合、平台、CI 和部署"])
        self.report["stages"].update(
            {stage: {"status": "not_run", "exitCode": None, "commands": [], "evidence": []}
             for stage in (*self.runtime_stages, "cleanup", "frozen_inputs_after")})
        self.save()

    def inputs(self):
        super().inputs()
        self.report["inputs"]["profileSources"].extend(
            artifact(self.repo / "eng" / source, self.repo)
            for source in ("r3_template_net9_runtime.py", "r3_template_net9_packages.py",
                           "r3-template-observer/StartupHook.cs", "r3-template-observer/Observer.csproj"))
        self.report["inputs"]["runtimeOverrides"]["ConnectionStrings__Default"] = "按进程使用本轮候选库连接"
        for name, expected in (("report.json", ORIGINAL_REPORT), ("angular-production-files.json", ANGULAR_MANIFEST)):
            path = checked_file(self.frozen_root, ORIGINAL / name, expected)
            self.original_hashes[path] = expected
        self.baseline = read_json(self.frozen_root / ORIGINAL / "report.json")
        original_round = self.baseline["rounds"]["restore"]
        self.business = self.baseline["sql"]["expected"]
        self.original_angular = read_json(self.frozen_root / ORIGINAL / "angular-production-files.json")
        self.original_frontend = self.frozen_root / ORIGINAL / self.baseline["inputs"]["angular"]["output"]
        backup = self.baseline["sql"]["backup"]
        relative = Path("r3-template-runtime/sql-server/backup") / Path(backup["serverPath"]).name
        original = checked_file(self.frozen_root, relative, backup["sha256"])
        self.original_hashes[original] = backup["sha256"]
        self.backup = {"name": original.name, **{name: backup[name] for name in ("database", "backupSetId", "sha256")}}
        require(self.baseline["status"] == "passed" and original_round["exitCode"] == 0
                and {name: row["version"] for name, row in original_round["host"]["sharedRuntime"].items()}
                == dict.fromkeys(SHARED, EXPECTED_RUNTIME)
                and self.baseline["sql"]["loginCountAtBackup"] == 1 and len(self.business["migrations"]) == 30,
                "冻结原版报告缺少正式通过、运行时、登录基数或迁移记录")
        for filename, expected in self.original_angular["files"].items():
            path = checked_file(self.original_frontend, filename, expected)
            self.original_hashes[path] = expected
        self.report["inputs"]["originalRuntime"] = {"report": str(self.frozen_root / ORIGINAL / "report.json"),
                                                   "sha256": ORIGINAL_REPORT, "backup": self.backup}
        self.host_output = read_json(self.evidence / "Web.Host-output.json")
        self.host_inventory = self.host_output["files"]
        self.migrator_inventory = read_json(self.evidence / "Migrator-output.json")["files"]
        self.report["inputs"]["host"] = {"entry": artifact(self.output / (PREFIX + "Web.Host.dll"), self.evidence)}

    def build_observer(self):
        project = self.evidence / "observer"
        shutil.copytree(self.repo / "eng/r3-template-observer", project, ignore=shutil.ignore_patterns("obj", "bin"))
        self.run_dotnet(["restore", project / "Observer.csproj", "--configfile", self.config, "--no-http-cache"],
                        "observer-restore.log")
        self.run_dotnet(["build", project / "Observer.csproj", "--configuration", "Release", "--no-restore",
                         "--disable-build-servers", "-p:UseSharedCompilation=false"], "observer-build.log")
        self.observer = project / "bin/Release/net9.0/Observer.dll"
        self.report["inputs"]["startupObserver"] = artifact(self.observer, self.evidence)

    def process_environment(self, entry):
        mode, filename = ("host", "host-loaded.json") if entry == "Web.Host" else ("migrator", "migrator-target.jsonl")
        require(sha256(self.observer) == self.report["inputs"]["startupObserver"]["sha256"], "进程观测器摘要已改变")
        return {"DOTNET_STARTUP_HOOKS": str(self.observer), "R3_TEMPLATE_OBSERVER_MODE": mode,
                "R3_TEMPLATE_OBSERVER_EVIDENCE": str(self.evidence_file(filename))}

    def angular(self):
        require(len(self.original_angular["files"]) == 1193
                and not any(path.is_symlink() for path in self.original_frontend.rglob("*"))
                and inventory(self.original_frontend, include_app_data=True) == self.original_angular,
                "最终返修轮 Angular production 实物与冻结清单不符")
        shutil.copytree(self.original_frontend, self.browser_output)
        config_path = self.browser_output / "assets/appconfig.production.json"
        config = read_json(config_path)
        overrides = {"remoteServiceBaseUrl": self.runtime["host"], "appBaseUrl": self.runtime["frontend"]}
        changes = {key: {"before": config[key], "after": value} for key, value in overrides.items()
                   if config[key] != value}
        if changes:
            write_json(config_path, config | overrides)
        self.angular_inventory = inventory(self.browser_output, include_app_data=True)
        expected = dict(self.original_angular["files"])
        config_name = config_path.relative_to(self.browser_output).as_posix()
        config_before = expected[config_name]
        if changes:
            expected[config_name] = sha256(config_path)
        require(self.angular_inventory["files"] == expected, "本轮 Angular 副本出现未登记文件变化")
        self.report["inputs"]["angular"] = {
            "originalManifestSha256": ANGULAR_MANIFEST, "originalInventory": self.original_angular["sha256"],
            "servedInventory": self.angular_inventory["sha256"], "files": len(expected),
            "configOriginalSha256": config_before, "configServedSha256": expected[config_name],
            "configChanges": changes, "cors": self.runtime["frontend"],
        }
        write_json(self.evidence_file("angular-production-files.json"), self.angular_inventory)

    def sql_preflight(self):
        self.sql_inputs(self.backup)
        self.report["sql"] = self.db.preflight(frozen_backup=self.backup)

    def sql_state(self):
        migrations = [row["migrationId"] for row in self.business["migrations"]]
        return {database: self.db.business(database, migrations, self.business["keyword"], self.business["matches"][0])
                for database in (self.db.source, self.db.restored)}

    def login_counts(self):
        return {database: self.db.login_count(database, self.business)
                for database in (self.db.source, self.db.restored)}

    def restore_pair(self):
        sql = self.report["sql"]
        sql["restores"] = restores = {}
        # 预检已核对两库都不存在及各自的两个目标文件，再开始恢复。
        for database in (self.db.source, self.db.restored):
            restores[database] = self.db.restore(sql["backup"], database=database)
        require(set(restores[self.db.source]["files"].values()).isdisjoint(restores[self.db.restored]["files"].values()),
                "两份恢复库使用了相同物理路径")
        sql["beforeMigration"] = states = self.sql_state()
        require(all(state == self.business for state in states.values()), "迁移前两库历史或业务字段偏离冻结报告")
        sql["countsBeforeMigration"] = self.login_counts()
        check_start_counts(sql["countsBeforeMigration"], self.db.source, self.db.restored)

    def migrate(self):
        require(inventory(self.migrator_output) == self.migrator_inventory, "实际启动的 Migrator 产物已改变")
        with self.process(self.migrator_output, "Migrator", ["-q"], self.db.source, "migrator") as (process, log, record):
            code = process.wait(timeout=300)
        sql = self.report["sql"]
        expected = {"pid": record["pid"], "serverName": self.config_input["sqlServerName"], "database": self.db.source}
        sql["migrationConnection"] = target = {"expected": expected, "observed": []}
        evidence = self.evidence / "migrator-target.jsonl"
        if evidence.is_file():
            target["observed"] = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines()]
        require(code == 0, f"Migrator -q 退出 {code}，详见 {log.name}")
        check_migration_target(target["observed"], expected["pid"], expected["serverName"], expected["database"])
        sql["afterMigration"] = self.sql_state()
        require(sql["afterMigration"] == sql["beforeMigration"], "原版恢复库的迁移历史或业务字段在迁移后变化")
        sql["countsAfterMigration"] = self.login_counts()
        check_start_counts(sql["countsAfterMigration"], self.db.source, self.db.restored)

    def browser(self):
        sql = self.report["sql"]
        counts = sql["loginComparison"] = {"candidate": self.db.source, "control": self.db.restored}

        def before_login():
            counts["before"] = self.login_counts()
            check_start_counts(counts["before"], self.db.source, self.db.restored)

        try:
            outcome = self.round(self.db.source, "candidate", before_login=before_login)
            counts["after"] = self.login_counts()
            counts["deltas"] = {name: count - counts["before"][name] for name, count in counts["after"].items()}
            check_end_counts(counts["after"], self.db.source, self.db.restored)
            require(outcome["steps"] == self.baseline["rounds"]["restore"]["steps"],
                    "实际浏览器请求、授权、响应、表格或入口脚本与原版不一致")
        except Exception as failure:
            outcome = self.report.get("rounds", {}).get("candidate")
            if outcome:
                outcome.update(exitCode=1, reason=self.redact(str(failure)))
            raise
        finally:
            outcome = self.report.get("rounds", {}).get("candidate")
            if outcome:
                outcome["loginComparison"] = counts
                write_json(self.evidence_file("candidate-round.json"), outcome)

    def loaded(self):
        launch = self.report["rounds"]["candidate"]["host"]
        evidence = self.evidence / "host-loaded.json"
        require(evidence.is_file(), f"Host PID {launch['pid']} 缺少结束时的实际程序集记录")
        record = self.report["hostAssemblyComparison"] = {"pid": launch["pid"], "evidence": evidence.name}
        verify_host_assemblies(read_json(evidence), launch, self.output, self.host_output, record)
        write_json(self.evidence_file("host-loaded-verification.json"), record)

    def comparison(self):
        original = self.baseline["rounds"]["restore"]
        candidate = self.report["rounds"]["candidate"]
        differences = read_json(self.evidence / "third-party-differences.json")["Web.Host"]["versions"]
        tracked = set(HOST_LIBRARIES) | {"Microsoft.EntityFrameworkCore.Design", "Microsoft.AspNetCore.Authentication.JwtBearer",
                                         "log4net", "Microsoft.Data.SqlClient.SNI.runtime"}
        result = {"original": {"host": original["host"], "login": original["loginCountComparison"],
                               "browser": original["browser"], "steps": original["steps"],
                               "sqlVersion": self.baseline["sql"]["productVersion"]},
                  "candidate": {"host": candidate["host"], "login": candidate["loginComparison"],
                                "browser": candidate["browser"], "steps": candidate["steps"],
                                "sqlVersion": self.report["sql"]["productVersion"]},
                  "thirdParty": {side: {name: version for name, version in versions.items() if name in tracked}
                                 for side, versions in differences.items()}}
        write_json(self.evidence_file("original-candidate-comparison.json"), result)

    def frozen_inputs_after(self):
        self.inputs_after()
        if hasattr(self, "original_angular"):
            require(inventory(self.original_frontend, include_app_data=True) == self.original_angular,
                    "冻结 Angular 原件目录在执行期间变化")
        if self.report.get("sql", {}).get("backup"):
            require(sha256(self.db.local_backup) == self.baseline["sql"]["backup"]["sha256"],
                    "SQL Server 挂载的冻结备份在执行期间变化")

    def execute_full(self):
        actions = (self.inputs, self.build_observer, self.angular, self.sql_preflight, self.restore_pair,
                   self.migrate, self.browser, self.loaded, self.comparison)
        return self.execute_steps((*self.build_steps(), *zip(RUNTIME_STAGES, actions, strict=True)))

    def execute_steps(self, steps):
        stage = "preflight"
        failures = []
        try:
            for stage, action in steps:
                self.step(stage, action)
        except (Exception, KeyboardInterrupt) as error:
            failures.append(self.redact(str(error)) or type(error).__name__)
            self.report["stages"][stage].update(status="failed", exitCode=1, reason=failures[0])
        finally:
            for name, action in (("cleanup", self.cleanup), ("frozen_inputs_after", self.frozen_inputs_after)):
                try:
                    self.step(name, action)
                except VerificationError as error:
                    failures.append(self.redact(str(error)))
            if hasattr(self, "db"):
                sql_commands = self.evidence / "sql-commands.json"
                write_json(sql_commands, self.db.commands)
                self.report["sqlCommands"] = artifact(sql_commands, self.evidence)
            for item in self.report["stages"].values():
                if item["status"] == "not_run":
                    item["reason"] = f"{stage} 未通过"
            self.report.update(status="failed" if failures else "passed", exitCode=int(bool(failures)),
                               finishedAt=datetime.now(timezone.utc).isoformat())
            if failures:
                self.report["reason"] = "\n".join(failures)
                print(f"{self.report['profile']}：{self.report['reason']}", file=sys.stderr)
            self.save()
        return self.report["exitCode"]


def execute(args):
    for name in ("DEBUG", "PWDEBUG"):
        os.environ.pop(name, None)
    run = CandidateRuntime(ROOT, make_run_directory(args.evidence_root, PROFILE + "-"),
                           args.frozen_root.resolve(), args.runtime_config, args.dotnet)
    print(f"{PROFILE} report: {run.report_path}", flush=True)
    return run.execute_full()
