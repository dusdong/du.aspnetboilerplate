"""在同一专用数据库上验证维护版模板的两代运行时。"""

import json
import os
from pathlib import Path

from r3_template_net10_upgrade import EF, PATCH_VERSION, PROVIDER, UpgradeBuildRun
from r3_template_net9_packages import CandidateRun
from r3_template_net9_runtime import (EXPECTED_RUNTIME, SHARED, CandidateRuntime, check_migration_target,
                                      unique_loaded, verify_host_assemblies, verify_shared_runtime)
from r3_template_runtime import inventory, shared_runtime_trace
from r3_template_upgrade_sql import UpgradeDatabase, added_login, verify_login_start
from r3_web_host import PREFIX, artifact, project_path, write_json
from verify import ROOT, make_run_directory, read_json, require, sha256


PROFILE = "r3-template-net10-upgrade-runtime"
VERSIONS = {"net9": EXPECTED_RUNTIME, "net10": PATCH_VERSION}
MIGRATOR_SHARED = SHARED | {"Microsoft.AspNetCore.App": "Microsoft.AspNetCore.Identity"}
MIGRATOR_EF = {
    EXPECTED_RUNTIME: {EF: "9.0.18", PROVIDER: "9.0.5"},
    PATCH_VERSION: dict.fromkeys((EF, PROVIDER), PATCH_VERSION),
}
STAGES = (
    ("net9_build", "build_net9"), ("runtime_inputs", "inputs"), ("observer_build", "build_observer"),
    ("angular_freeze", "angular"), ("sql_preflight", "sql_preflight"), ("restore_pair", "restore_pair"),
    ("net9_migrator", "migrate_net9"), ("net9_browser", "browser_net9"), ("net9_loaded", "loaded"),
    ("before_upgrade_backup", "before_upgrade_backup"), ("net10_migrator", "migrate_net10"),
    ("net10_browser", "browser_net10"), ("net10_loaded", "loaded"),
    ("after_upgrade_backup", "after_upgrade_backup"), ("recover_backups", "recover_backups"),
)


def verify_migrator_assemblies(observed, launch, output, expected, report, runtime_version):
    pid = launch["pid"]
    require(observed.get("pid") == pid,
            f"Migrator 实际加载 PID 不符，预期 {pid}，实际 {observed.get('pid')}")
    rows = observed["assemblies"]
    verify_shared_runtime(rows, launch, report, runtime_version, anchors=MIGRATOR_SHARED,
                          process_name="Migrator")
    entries = {PREFIX + "Migrator": expected["entry"]}
    for name in (EF, PROVIDER):
        relative = name + ".dll"
        source = expected["packageCopies"][relative]
        version = MIGRATOR_EF[runtime_version][name]
        require(source["package"] == f"{name}/{version}",
                f"Migrator {name} 预期包版本 {version}，实际 {source['package']}")
        entries[name] = {"path": relative, **source}
    report["assemblies"] = verified = {}
    for name, source in entries.items():
        row = unique_loaded(rows, name, pid, process_name="Migrator")
        path = output / source["path"]
        verified[name] = {"loaded": row, "expected": source, "expectedPath": str(path)}
        require(Path(row["path"]) == path == path.resolve()
                and row["sha256"] == source["sha256"] == sha256(path),
                f"Migrator PID {pid} 的 {name} 预期 {path} / {source['sha256']}，"
                f"实际 {row['path']} / {row['sha256']}")
        if name == PREFIX + "Migrator":
            require(launch["entrySha256"] == row["sha256"] and Path(launch["argv"][1]) == path,
                    f"Migrator PID {pid} 的已加载入口与启动命令不一致：{launch}")
    contexts = {item["loaded"]["contextId"] for item in (*verified.values(), *report["sharedRuntime"].values())}
    require(len(contexts) == 1, f"Migrator PID {pid} 的程序集分属多个加载上下文：{contexts}")


class UpgradeRuntime(CandidateRuntime, UpgradeBuildRun):
    profile = PROFILE
    database_type = UpgradeDatabase
    runtime_stages = tuple(stage for stage, _ in STAGES)

    def __init__(self, repo, evidence, frozen_root, runtime_config, dotnet=None):
        super().__init__(repo, evidence, frozen_root, runtime_config, dotnet)
        self.report.update(profile=PROFILE, coverageNotRun=["原版应用回退", "其他消费组合、平台、CI 和部署"])
        self.builds = {"net10": evidence, "net9": evidence / "net9-build"}
        self.save()

    def build_net9(self):
        directory = self.builds["net9"]
        directory.mkdir()
        build = CandidateRun(self.repo, directory, self.frozen_root, self.dotnet)
        exit_code = build.execute_build()
        self.report["inputs"]["net9Build"] = artifact(build.report_path, self.evidence) | {"exitCode": exit_code}
        require(exit_code == 0, f".NET 9 干净构建退出 {exit_code}，详见 {build.report_path}")

    def inputs(self):
        super().inputs()
        self.report["inputs"]["profileSources"].extend(
            artifact(self.repo / "eng" / source, self.repo)
            for source in ("r3_template_net10_upgrade.py", "r3_template_net10_runtime.py", "r3_template_upgrade_sql.py"))
        self.report["inputs"]["entryOutputs"] = {}
        for phase, directory in self.builds.items():
            self.report["inputs"]["entryOutputs"][phase] = {
                entry: artifact(directory / f"{entry}-output.json", self.evidence)
                for entry in ("Web.Host", "Migrator")
            }

    def entry_output(self, phase, entry):
        directory = self.builds[phase]
        manifest = directory / f"{entry}-output.json"
        reference = self.report["inputs"]["entryOutputs"][phase][entry]
        require(sha256(manifest) == reference["sha256"], f"{phase} {entry} 构建清单已改变")
        tfm = phase + ".0"
        output = directory / "source/aspnet-core" / project_path(entry).parent / f"bin/Release/{tfm}"
        return output, read_json(manifest)

    def process_environment(self, entry):
        require(sha256(self.observer) == self.report["inputs"]["startupObserver"]["sha256"], "进程观测器摘要已改变")
        suffix = "host-loaded.json" if entry == "Web.Host" else "migrator-target.jsonl"
        result = {"DOTNET_STARTUP_HOOKS": str(self.observer),
                  "R3_TEMPLATE_OBSERVER_MODE": "host" if entry == "Web.Host" else "migrator",
                  "R3_TEMPLATE_OBSERVER_EVIDENCE": str(self.evidence_file(f"{self.phase}-{suffix}"))}
        if entry == "Migrator":
            result["R3_TEMPLATE_OBSERVER_ASSEMBLIES"] = str(self.evidence_file(f"{self.phase}-migrator-loaded.json"))
        return result

    def login_rows(self):
        return {database: self.db.successful_logins(database, self.business)
                for database in (self.db.source, self.db.restored)}

    def restore_pair(self):
        super().restore_pair()
        sql = self.report["sql"]
        sql["databaseIdentities"] = {database: self.db.state_identity(database)
                                     for database in (self.db.source, self.db.restored)}
        require(len({row["databaseGuid"] for row in sql["databaseIdentities"].values()}) == 2,
                f"候选和对照库的数据库身份重复：{sql['databaseIdentities']}")
        sql["initialLoginRows"] = self.login_rows()
        verify_login_start(sql["initialLoginRows"], self.db.source, self.db.restored, 1)

    def launch_migrator(self, phase, database):
        output, manifest = self.entry_output(phase, "Migrator")
        require(inventory(output) == manifest["files"], f"{phase} 实际启动的 Migrator 产物已改变")
        with self.process(output, "Migrator", ["-q"], database, f"{self.phase}-migrator", trace=True) as (
                process, log, launch):
            process.wait(timeout=300)
        return launch, log

    def run_migrator(self, phase, count, expected_logins):
        self.phase = phase
        source, control = self.db.source, self.db.restored
        sql = self.report["sql"]
        record = sql.setdefault("migrations", {})[phase] = {"beforeLoginRows": self.login_rows()}
        verify_login_start(record["beforeLoginRows"], source, control, count, expected=expected_logins)
        record["before"] = before = self.sql_state()
        require(all(state == self.business for state in before.values()), f"{phase} 迁移前与冻结数据偏离")
        catalog_before = self.db.catalog(source) if phase == "net10" else None
        if catalog_before:
            write_json(self.evidence_file("net10-catalog-before.json"), catalog_before)
        launch, log = self.launch_migrator(phase, source)
        record["launch"] = launch
        target = record["connection"] = {"expected": {"pid": launch["pid"], "serverName": sql["serverName"],
                                                       "database": source}, "observed": []}
        evidence = self.evidence / f"{phase}-migrator-target.jsonl"
        if evidence.is_file():
            target["observed"] = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines()]
        require(launch["exitCode"] == 0, f"{phase} Migrator -q 退出 {launch['exitCode']}，详见 {log.name}")
        check_migration_target(target["observed"], launch["pid"], sql["serverName"], source)
        launch["sharedRuntime"] = shared_runtime_trace(log, "Migrator")
        path = self.evidence / f"{phase}-migrator-loaded.json"
        require(path.is_file(), f"Migrator PID {launch['pid']} 缺少实际程序集记录：{path.name}")
        output, manifest = self.entry_output(phase, "Migrator")
        record["loadedVerification"] = loaded = {}
        verify_migrator_assemblies(read_json(path), launch, output, manifest, loaded, VERSIONS[phase])
        record["after"] = self.sql_state()
        require(record["after"] == before, f"{phase} Migrator 改变了既有迁移历史或业务数据")
        record["afterLoginRows"] = self.login_rows()
        verify_login_start(record["afterLoginRows"], source, control, count, expected=expected_logins)
        record["databaseIdentities"] = identities = {database: self.db.state_identity(database)
                                                     for database in (source, control)}
        require(identities == sql["databaseIdentities"], f"{phase} Migrator 后两库身份或文件路径改变：{identities}")
        if catalog_before:
            catalog_after = self.db.catalog(source)
            write_json(self.evidence_file("net10-catalog-after.json"), catalog_after)
            changed = [name for name in catalog_before if catalog_after[name] != catalog_before[name]]
            require(not changed, f"迁移后 SQL Server 目录变化，见升级前后目录证据：{changed}")
            record["catalog"] = {"unchanged": True, "rowsByKind": {k: len(v) for k, v in catalog_after.items()}}

    def migrate_net9(self):
        self.run_migrator("net9", 1, self.report["sql"]["initialLoginRows"])

    def migrate_net10(self):
        self.run_migrator("net10", 2, self.report["sql"]["upgradeStartLoginRows"])

    def run_browser(self, phase, count, expected_logins):
        self.phase = phase
        self.output, self.host_output = self.entry_output(phase, "Web.Host")
        self.host_inventory = self.host_output["files"]
        self.report["inputs"]["host"] = {"entry": artifact(self.output / self.host_output["entry"]["path"],
                                                           self.evidence)}
        sql = self.report["sql"]
        source, control = self.db.source, self.db.restored
        record = sql.setdefault("businessRounds", {})[phase] = {}

        def before_login():
            record["beforeLoginRows"] = self.login_rows()
            verify_login_start(record["beforeLoginRows"], source, control, count, expected=expected_logins)

        outcome = self.round(source, phase, before_login=before_login)
        record["afterLoginRows"] = self.login_rows()
        record["addedLogin"] = added_login(record["beforeLoginRows"], record["afterLoginRows"], source, control)
        require(outcome["steps"] == self.baseline["rounds"]["restore"]["steps"],
                f"{phase} 的请求、授权、响应、单元格或入口脚本与基线不同")
        require(all(state == self.business for state in self.sql_state().values()),
                f"{phase} 登录后既有迁移历史或业务字段变化")

    def browser_net9(self):
        self.run_browser("net9", 1, self.report["sql"]["initialLoginRows"])

    def browser_net10(self):
        self.run_browser("net10", 2, self.report["sql"]["upgradeStartLoginRows"])

    def loaded(self):
        phase = self.phase
        launch = self.report["rounds"][phase]["host"]
        evidence = self.evidence / f"{phase}-host-loaded.json"
        require(evidence.is_file(), f"Host PID {launch['pid']} 缺少实际程序集记录：{evidence.name}")
        report = self.report.setdefault("hostAssemblyComparison", {})[phase] = {"pid": launch["pid"]}
        verify_host_assemblies(read_json(evidence), launch, self.output, self.host_output, report,
                               runtime_version=VERSIONS[phase])
        write_json(self.evidence_file(f"{phase}-host-loaded-verification.json"), report)

    def save_backup(self, label, phase):
        sql = self.report["sql"]
        rows = self.login_rows()
        require(rows == sql["businessRounds"][phase]["afterLoginRows"], f"{label} 备份前登录记录变化")
        business = self.sql_state()[self.db.source]
        medium = self.db.checkpoint(label)
        sql.setdefault("checkpoints", {})[label] = {
            "media": medium.backup(), "loginRows": rows[self.db.source], "business": business,
        }
        require(rows == self.login_rows(), f"{label} 备份期间登录记录变化")
        return rows

    def before_upgrade_backup(self):
        self.report["sql"]["upgradeStartLoginRows"] = self.save_backup("before_upgrade", "net9")

    def after_upgrade_backup(self):
        self.save_backup("after_upgrade", "net10")

    def recover_backups(self):
        sql = self.report["sql"]
        recovered = {}
        paths = {row["path"] for identity in sql["databaseIdentities"].values() for row in identity["files"]}
        for label, expected in sql["checkpoints"].items():
            medium = self.db.checkpoint(label)
            backup = expected["media"]
            restore = medium.restore(backup)
            restore["identity"] = medium.state_identity(medium.restored)
            restore["loginRows"] = medium.successful_logins(medium.restored, self.business)
            expected_business = expected["business"]
            ids = [row["migrationId"] for row in expected_business["migrations"]]
            restore["business"] = medium.business(medium.restored, ids, self.business["keyword"],
                                                   self.business["matches"][0])
            expected["recovered"] = recovered[label] = restore
            require(restore["loginRows"] == expected["loginRows"] and restore["business"] == expected_business,
                    f"{label} 恢复后登录行、迁移历史或业务字段与备份前不符")
            files = set(restore["files"].values())
            require(files.isdisjoint(paths), f"{label} 恢复使用了相同的物理路径：{files & paths}")
            paths.update(files)
        before, after = (recovered[label]["loginRows"] for label in ("before_upgrade", "after_upgrade"))
        prior, upgraded = (sql["businessRounds"][phase]["addedLogin"] for phase in VERSIONS)
        require(len(before) == 2 and prior in before and len(after) == 3
                and [row for row in after if row != upgraded] == before and upgraded in after,
                f"两个恢复点的写入边界不符：{before} / {after}")
        identities = [*sql["databaseIdentities"].values(), *(entry["identity"] for entry in recovered.values())]
        require(len({item["databaseGuid"] for item in identities}) == 4, f"四个数据库 GUID 未独立：{identities}")
        media = [entry["media"] for entry in sql["checkpoints"].values()]
        require(len({item["backupSetId"] for item in media}) == 2 and len({item["sha256"] for item in media}) == 2,
                "升级前后备份集或文件摘要重复")
        sql["rollbackWriteBoundary"] = {"preservedBeforeUpgrade": before, "absentAtBeforeUpgrade": [upgraded],
                                        "presentAfterUpgrade": after, "originalApplicationRollback": "待验"}

    def execute_full(self):
        return self.execute_steps((*self.build_steps(), *((stage, getattr(self, name)) for stage, name in STAGES)))


def execute(args):
    for name in ("DEBUG", "PWDEBUG"):
        os.environ.pop(name, None)
    run = UpgradeRuntime(ROOT, make_run_directory(args.evidence_root, PROFILE + "-"),
                         args.frozen_root.resolve(), args.runtime_config, args.dotnet)
    print(f"{PROFILE} report: {run.report_path}", flush=True)
    return run.execute_full()
