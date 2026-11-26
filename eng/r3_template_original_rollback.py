"""用固定原版 Release 应用在升级前后恢复点验证真实回退业务。"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
from zipfile import ZipFile

from r2_packages import nuspec_metadata
from r3_leaf_packages import checked_file
from r3_template_browser import USERS
from r3_template_net10_runtime import MIGRATOR_SHARED
from r3_template_net9_runtime import (ANGULAR_MANIFEST, EXPECTED_RUNTIME, ORIGINAL, ORIGINAL_REPORT, SHARED,
                                     check_migration_target, verify_entry_assemblies)
from r3_template_runtime import RuntimeSupport, inventory, shared_runtime_trace
from r3_template_upgrade_sql import UpgradeDatabase, added_login
from r3_web_host import (ABP_VERSION, DEPS_TARGET, INPUTS, NUGET_SOURCE, PREFIX, R3Run, TEMPLATE, TFM,
                         artifact, inside, is_abp, package_hashes, write_json)
from verify import ROOT, VerificationError, make_run_directory, read_json, require, sha256


PROFILE = "r3-template-original-rollback"
OBSERVER_SDK = "9.0.306"
PLAN = Path("openspec/changes/validate-r3-original-template-rollback")
ARCHIVED_PLAN = PLAN.parent / "archive" / f"2026-11-26-{PLAN.name}"
PLAN_BASE_COMMIT = "d731068b6c7d51ae3e4035d4b4620ec00d6e03ea"
PLAN_BASE_TREE = "e1f982eaa5a7be89b5bb14959f85cfb8298cc022"
OUT_OF_SCOPE = (
    "从源码还原和构建原版 Web.Host、Migrator 与 Angular production",
    "从空库初始化种子、应用新的迁移或逆向迁移",
    "其他运行平台、数据库 Provider 和本轮用例范围以外的业务",
    "生产流量切换、现场恢复耗时及 R4 发行",
)
UPGRADE_RUN = "r3-template-net10-upgrade-runtime-ifj4cd74"
UPGRADE_REPORT = "744809c912236ca8674769922274e823cafe7f91d7313e084e4d11e93b2b6308"
UPGRADE_CATALOG = "c2d3d201947f3590b87e1498555936e7a20cd72fa2b5b3b88305ef368066a01f"
ROLES = ("after_upgrade", "before_upgrade")
ENTRY_POINTS = {"host": "Web.Host", "migrator": "Migrator"}
VERSIONS = {"AutoMapper": "14.0.0", "AutoMapper.Collection": "11.0.0",
            **dict.fromkeys(("Microsoft.EntityFrameworkCore", "Microsoft.EntityFrameworkCore.Abstractions",
                             "Microsoft.EntityFrameworkCore.Relational", "Microsoft.EntityFrameworkCore.SqlServer"),
                            "9.0.5"),
            "Microsoft.Data.SqlClient": "5.1.6"}
LOGIN_FIELDS = {"id", "creationTime", "result", "tenantId", "userId", "tenancyName", "loginName"}
STEPS = ("original_inputs", "runtime_inputs", "angular_freeze", "upgrade_inputs", "sql_preflight", "restore_pair")
CLEANUP = ("cleanup", "frozen_inputs_after")
BUSINESS_STEPS = ("observer_build", ROLES[0], "independent_recovery", ROLES[1])


def verify_release_files(output, manifest, entry):
    # App_Data 由应用运行时创建，两个冻结清单均排除了该目录。
    # 原版 Migrator 还在其 log4net.config 指定位置写入运行日志。
    exclude = ("Logs/Logs.txt",) if entry == "Migrator" else ()
    observed = inventory(output, exclude=exclude)
    for name in sorted(observed["files"].keys() | manifest["files"].keys()):
        wanted = manifest["files"].get(name)
        actual = observed["files"].get(name)
        require(actual == wanted and not (output / name).is_symlink()
                and (output / name).resolve() == output / name,
                f"原版 {entry} Release 来源不符：{name}，预期原版摘要 {wanted}，实际 {actual}")
    require(observed == manifest, f"原版 {entry} Release 清单摘要不符：{output}")


def original_package_copies(entry, raw, output, inventory_rows, cache, abp_names):
    deps = read_json(output / f"{PREFIX}{entry}.deps.json")
    config = read_json(output / f"{PREFIX}{entry}.runtimeconfig.json")["runtimeOptions"]
    restore = raw["project"]["restore"]
    require(set(restore["sources"]) == {NUGET_SOURCE} and restore["originalTargetFrameworks"] == [TFM]
            and set(raw["targets"]) == {TFM} and config["tfm"] == TFM
            and {item["name"]: item["version"] for item in config["frameworks"]} == dict.fromkeys(SHARED, "9.0.0")
            and deps["runtimeTarget"]["name"] == DEPS_TARGET,
            f"原版 {entry} 的还原源、目标或共享框架声明不符")
    graph = raw["targets"][TFM]
    packages = {key.split("/")[0]: key.split("/")[1] for key, row in graph.items() if row["type"] == "package"}
    require(all(not package.casefold().startswith("du.") for package in packages)
            and {key: val for key, val in packages.items() if is_abp(key)} == dict.fromkeys(abp_names, ABP_VERSION),
            f"原版 {entry} 框架包身份不符")
    target = deps["targets"][DEPS_TARGET]
    copies = {}
    for name, version in (dict.fromkeys(abp_names, ABP_VERSION) | VERSIONS).items():
        key = f"{name}/{version}"
        require(packages.get(name) == version and key in target and deps["libraries"][key]["type"] == "package",
                f"原版 {entry} 预期包 {key}，还原版本 {packages.get(name)} 或 .deps.json 不符")
        library = raw["libraries"][key]
        hashes = package_hashes(cache, key, library["path"])
        require(library["sha512"] == hashes["contentSha512"]
                and deps["libraries"][key]["sha512"] == "sha512-" + hashes["contentSha512"],
                f"原版 {entry} 的 {key} 还原图、.deps.json 或缓存摘要不一致")
        with ZipFile(cache / hashes["archive"]["path"]) as archive:
            metadata = nuspec_metadata(archive)
            require((metadata.findtext("id"), metadata.findtext("version")) == (name, version),
                    f"原版 {entry} 归档包身份不符：{key}")
            found = []
            for section in ("runtime", "runtimeTargets"):
                for asset in target[key].get(section, {}):
                    if Path(asset).name != name + ".dll":
                        continue
                    relative = asset if section == "runtimeTargets" else Path(asset).name
                    require(asset in graph[key].get(section, {}) and archive.namelist().count(asset) == 1,
                            f"原版 {entry} 的 {key} 运行资产在还原图或归档中缺失：{asset}")
                    digest = hashlib.sha256(archive.read(asset)).hexdigest()
                    require(digest == inventory_rows["files"].get(relative),
                            f"原版 {entry} 的 {relative} 与 {key} 归档资产摘要不符")
                    found.append(relative)
                    require(relative not in copies, f"原版 {entry} 的 {relative} 有多个包来源")
                    copies[relative] = {"package": key, "packageAsset": asset, "sha256": digest, **hashes}
            require(name + ".dll" in found, f"原版 {entry} 缺少 {key} 主运行 DLL")
            if name == "Microsoft.Data.SqlClient":
                require(any(path.startswith("runtimes/unix/") for path in found),
                        f"原版 {entry} 缺少 {key} Unix 运行资产")
    return packages, copies


def verify_checkpoint_logins(role, expected, observed):
    require(observed == expected,
            f"{role} 的成功登录行与正式恢复点不一致，预期 {expected}，实际 {observed}")


def verify_query_target(events, pid, server, database, search, request_id, keyword):
    location = f"Host PID {pid} 请求 {request_id}，预期 {server}/{database}"
    require(search.get("requestId") == request_id and search.get("path") == USERS
            and search.get("method") == "GET" and search.get("keyword") == [keyword],
            f"{location} 缺少匹配的浏览器关键词请求：{search}")
    requests = [row for row in events if row.get("kind") == "request"]
    require(len(requests) == 1 and requests[0].get("activityId")
            and (requests[0].get("method"), requests[0].get("path"), requests[0].get("keyword"))
            == ("GET", USERS, keyword),
            f"{location} 缺少唯一 Host 关键词请求：{requests}")
    activity = requests[0]["activityId"]
    require(all((row.get("pid"), row.get("requestId"), row.get("activityId")) == (pid, request_id, activity)
                for row in events), f"{location} 存在其他进程或请求的证据：{events}")
    responses = [row.get("status") for row in events if row.get("kind") == "response"]
    require(responses == [search["status"]] == [200], f"{location} Host 或浏览器响应不符：{responses} / {search}")
    command_ids = set()
    for step in ("count", "list"):
        connections = [row for row in events if row.get("kind") == "connection" and row.get("step") == step]
        require(len(connections) == 1, f"{location} 缺少唯一 {step} 实际 SQL 连接：{connections}")
        row, = connections
        require((row.get("serverName"), row.get("database")) == (server, database),
                f"{location} 的 {step} 连接不符，实际 {row.get('serverName')}/{row.get('database')}")
        require(all(row.get(field) for field in ("sessionId", "commandId", "connectionId", "clientConnectionId",
                                                 "context")),
                f"{location} 的 {step} SQL 连接证据不完整：{row}")
        command = row["commandId"]
        completed = [item.get("commandId") for item in events
                     if item.get("kind") == "completed" and item.get("step") == step]
        require(command not in command_ids and completed == [command],
                f"{location} 的 {step} 缺少同命令成功证据：{row} / {completed}")
        command_ids.add(command)


def verify_path_login_start(expected, observed, target, original_third):
    rows = observed[target]
    if original_third not in expected[target]:
        require(original_third not in rows,
                f"{target} 认证前含升级轮原行 3，预期 {expected[target]}，实际 {rows}")
    for database, before in expected.items():
        verify_checkpoint_logins(database, before, observed[database])


class RollbackDatabase(UpgradeDatabase):
    def __init__(self, config, user, password, run_id, *, frozen_backup):
        super().__init__(config, user, password, run_id, frozen_backup=frozen_backup)
        self.source = f"{self.prefix}_after_upgrade"
        self.restored = f"{self.prefix}_before_upgrade"


class RollbackRun(RuntimeSupport, R3Run):
    database_type = RollbackDatabase

    def __init__(self, repo, evidence, frozen_root, upgrade_run, runtime_config, dotnet=None):
        super().__init__(repo, evidence)
        self.setup_runtime(runtime_config)
        self.original = inside(frozen_root, ORIGINAL)
        self.upgrade_run = upgrade_run
        self.dotnet = Path(dotnet or self.dotnet).resolve() if dotnet or self.dotnet else None
        self.browser_output = self.evidence / "angular-browser"
        self.original_hashes = {}
        self.previous_sql_commands = []
        del self.report["inputs"]["planningCommit"], self.report["inputs"]["planningTree"]
        self.report.update(
            profile=PROFILE, runId=self.run_id, coverageNotRun=list(OUT_OF_SCOPE),
            paths={role: {"status": "not_run", "exitCode": None} for role in ROLES},
            stages={name: {"status": "not_run", "exitCode": None, "commands": [], "evidence": []}
                    for name in (*STEPS, *BUSINESS_STEPS, *CLEANUP)},
        )
        self.save()

    def frozen_file(self, root, path, digest):
        source = checked_file(root, path, digest)
        self.original_hashes[source] = digest
        return source

    def original_output(self, record):
        return inside(self.original, record["entry"]["path"]).parent

    def release(self, label):
        entry = ENTRY_POINTS[label]
        record = self.baseline["inputs"][label]
        reference = self.baseline["rawAssets"][entry] if label == "host" else record["assets"]
        raw = self.frozen_file(self.original, reference["path"], reference["sha256"])
        manifest_path = inside(self.original, f"release-{label}-files.json")
        manifest = read_json(manifest_path)
        entry_name = PREFIX + entry + ".dll"
        require(manifest["sha256"] == record["inventory"]
                and manifest["files"].get(entry_name) == record["entry"]["sha256"],
                f"原版 {entry} 的输出清单或入口摘要与原版报告不符")
        frozen = self.original_output(record)
        verify_release_files(frozen, manifest, entry)
        self.original_hashes[manifest_path] = sha256(manifest_path)
        self.original_hashes.update({frozen / name: digest for name, digest in manifest["files"].items()})
        abp_names = self.baseline["inputs"]["host"]["abpPackages"] if label == "host" else [
            name for name in record["resolvedPackages"] if is_abp(name)]
        require(len(set(abp_names)) == (11 if label == "host" else 8), f"原版 {entry} ABP 输入数目不符")
        cache = inside(self.original, "packages")
        packages, copies = original_package_copies(entry, read_json(raw), frozen, manifest, cache, abp_names)
        host_packages = self.original_host_packages
        expected = ({item["id"]: item["version"] for item in host_packages.values()}
                    if label == "host" else record["resolvedPackages"])
        require(packages == expected, f"原版 {entry} 完整还原包列表与原版报告不符")
        require(all(host_packages[item["package"]]["archive"] == item["archive"] for item in copies.values()),
                f"原版 {entry} 运行包归档摘要与原版清单不符")
        self.original_hashes.update({cache / item["archive"]["path"]: item["archive"]["sha256"]
                                     for item in copies.values()})

        output = self.evidence / "release" / entry / "bin" / "Release" / TFM
        for name in manifest["files"]:
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(frozen / name, target)
        verify_release_files(output, manifest, entry)
        copied_assets = self.evidence_file(f"{entry}.project.assets.json")
        shutil.copy2(raw, copied_assets)
        copied_reference = artifact(copied_assets, self.evidence)
        require(copied_reference["sha256"] == reference["sha256"], f"原版 {entry} 的还原图副本摘要不符")
        origins = {"entry": {"path": entry_name, "sha256": record["entry"]["sha256"]},
                   "files": manifest, "packageCopies": copies, "resolvedPackages": packages,
                   "frameworkDlls": sorted(name + ".dll" for name in abp_names), "assets": copied_reference}
        manifest_copy = self.evidence_file(f"{entry}-output.json")
        write_json(manifest_copy, origins)
        self.report["inputs"][label] = {
            "entry": artifact(output / entry_name, self.evidence), "files": len(manifest["files"]),
            "inventory": manifest["sha256"], "manifest": artifact(manifest_copy, self.evidence),
            "frozenOutput": str(frozen),
        }
        return output, manifest, origins

    def execution_inputs(self):
        inputs = self.report["inputs"]
        inputs["executionCommit"] = self.git(self.repo, "main-current-head.log", "rev-parse", "HEAD")
        inputs["executionTree"] = self.git(self.repo, "main-current-tree.log", "rev-parse", "HEAD^{tree}")
        active = (self.repo / PLAN).is_dir()
        plan = PLAN if active else ARCHIVED_PLAN
        status = self.git(self.repo, "rollback-plan-status.log", "status", "--porcelain=v1",
                          "--untracked-files=all", "--", plan).splitlines()
        artifacts = [artifact(path, self.repo) for path in sorted((self.repo / plan).rglob("*")) if path.is_file()]
        change_state = "active" if active else "archived"
        inputs["planning"] = {
            "change": PLAN.name, "baseCommit": PLAN_BASE_COMMIT, "baseTree": PLAN_BASE_TREE,
            "changePath": plan.as_posix(),
            "changeState": change_state if artifacts else "unavailable",
            "artifactSource": "working_tree" if artifacts else "unavailable",
            "gitStatus": status, "artifacts": artifacts,
        }

    def original_inputs(self):
        self.execution_inputs()
        source = self.frozen_file(self.original, "report.json", ORIGINAL_REPORT)
        self.baseline = read_json(source)
        self.business = self.baseline["sql"]["expected"]
        commit, tree = INPUTS[TEMPLATE]
        baseline_inputs = self.baseline["inputs"]
        reported_template = baseline_inputs["submodules"][TEMPLATE]
        runtime = self.baseline["rounds"]["restore"]["host"]["sharedRuntime"]
        require(self.baseline["profile"] == "r3-template-runtime" and self.baseline["status"] == "passed"
                and self.baseline["exitCode"] == 0 and baseline_inputs["configuration"] == "Release"
                and baseline_inputs["targetFramework"] == TFM
                and (reported_template["commit"], reported_template["tree"]) == (commit, tree)
                and {name: item["version"] for name, item in runtime.items()} == dict.fromkeys(SHARED, EXPECTED_RUNTIME),
                "返修轮报告的固定模板、正式状态或实际共享框架不符")
        self.git_tree(self.repo / TEMPLATE, "fixed-template", commit, tree)
        gitlink = self.git(self.repo, "template-gitlink.log", "ls-tree", "HEAD", "--", TEMPLATE)
        require(gitlink.split() == ["160000", "commit", commit, TEMPLATE], "主仓模板 gitlink 与原版输入不符")
        self.report["inputs"]["original"] = {
            "path": str(source), "sha256": ORIGINAL_REPORT, "templateCommit": commit, "templateTree": tree,
            "executionCommit": baseline_inputs["executionCommit"], "executionTree": baseline_inputs["executionTree"],
        }
        expected = self.baseline["inventories"]["assets-inventory.json"]
        inventory_path = self.frozen_file(self.original, expected["path"], expected["sha256"])
        project = baseline_inputs["entryProject"].removeprefix("aspnet-core/")
        self.original_host_packages = read_json(inventory_path)[project]["packages"]
        self.output, self.host_inventory, self.host_output = self.release("host")
        self.migrator_output, self.migrator_inventory, self.migrator_manifest = self.release("migrator")

    def angular_inputs(self):
        manifest = self.frozen_file(self.original, "angular-production-files.json", ANGULAR_MANIFEST)
        self.original_angular = read_json(manifest)
        angular = self.baseline["inputs"]["angular"]
        self.frozen_file(self.original, angular["lock"]["path"], angular["lock"]["sha256"])
        self.original_frontend = inside(self.original, angular["output"])
        steps = self.baseline["rounds"]["restore"]["steps"]
        script, digest = (steps["client"][key] for key in ("script", "scriptSha256"))
        require(angular["configuration"] == "production"
                and angular["inventory"] == self.original_angular["sha256"]
                and script == "main-PZGEMKYC.js" and self.original_angular["files"].get(script) == digest
                and script in (self.original_frontend / "index.html").read_text(encoding="utf-8"),
                "Angular production 入口脚本与返修轮报告不符")
        self.frozen_angular(ANGULAR_MANIFEST)
        self.report["inputs"]["angular"]["entryScript"] = {"path": script, "sha256": digest}
        self.original_hashes.update({self.original_frontend / path: hash_
                                     for path, hash_ in self.original_angular["files"].items()})

    def upgrade_registration(self):
        return "r3-template-net10-upgrade-runtime", UPGRADE_RUN, UPGRADE_REPORT, None

    def upgrade_inputs(self):
        profile, registered_run, digest, registered_checkpoints = self.upgrade_registration()
        source = self.frozen_file(self.upgrade_run, "report.json", digest)
        upgrade = read_json(source)
        require(upgrade["profile"] == profile and upgrade["status"] == "passed"
                and upgrade["exitCode"] == 0
                and upgrade["inputs"]["submodules"][TEMPLATE]["commit"] == INPUTS[TEMPLATE][0]
                and upgrade["inputs"]["originalRuntime"]["sha256"] == ORIGINAL_REPORT,
                "正式升级报告的状态、固定模板或原版来源不符")
        if registered_checkpoints is not None:
            require(upgrade["runId"] == registered_run and set(registered_checkpoints) == set(ROLES),
                    "升级报告运行标识或登记恢复点不符")
            self.check_upgrade_provenance(upgrade)
        self.checkpoints = upgrade["sql"]["checkpoints"]
        self.sql_version = upgrade["sql"]["productVersion"]
        require(set(self.checkpoints) == set(ROLES), "正式升级报告缺少升级前后恢复点")
        self.expected_catalogs = {}
        media_inputs = self.report["inputs"]["upgrade"] = {"runId": registered_run, "path": str(source),
                                                           "sha256": digest, "checkpoints": {}}
        for index, role in enumerate(ROLES):
            checkpoint = self.checkpoints[role]
            media = checkpoint["media"]
            name = Path(media["serverPath"]).name
            require(name == f"r3_template_{upgrade['runId']}_{role}.bak"
                    and checkpoint["recovered"]["backupSetId"] == media["backupSetId"],
                    f"{role} 介质角色、备份集或正式轮实际恢复记录不符")
            catalog_digest = UPGRADE_CATALOG
            if registered_checkpoints is not None:
                registered = registered_checkpoints[role]
                require(registered["name"] == name and all(
                    media[field] == registered[field] for field in ("sha256", "size", "backupSetId")),
                    f"{role} 介质与本轮登记不符")
                catalog_digest = registered["catalogSha256"]
            self.expected_catalogs[role] = self.frozen_file(
                self.upgrade_run, "net10-catalog-after.json" if index == 0 else "net10-catalog-before.json",
                catalog_digest)
            rows = checkpoint["loginRows"]
            require(checkpoint["business"] == self.business and len(self.business["migrations"]) == 30
                    and [row["id"] for row in rows] == list(range(1, 4 - index))
                    and all(set(row) == LOGIN_FIELDS for row in rows),
                    f"{role} 正式恢复点的迁移、业务或成功登录行不符")
            media_inputs["checkpoints"][role] = {
                "name": name, "sha256": media["sha256"], "backupSetId": media["backupSetId"],
                "size": media["size"], "catalogSha256": catalog_digest,
            }
        require(self.checkpoints["after_upgrade"]["loginRows"][:-1] == self.checkpoints["before_upgrade"]["loginRows"],
                "正式升级报告的保留登录行不一致")
        for field in ("sha256", "backupSetId"):
            require(len({self.checkpoints[role]["media"][field] for role in ROLES}) == len(ROLES),
                    f"正式升级报告的介质 {field} 重复")

    def sql_preflight(self):
        first = self.checkpoints[ROLES[0]]["media"]
        self.sql_inputs({**first, "name": Path(first["serverPath"]).name})
        # 先核对两份本机实物，再连接专用实例验证实际挂载的标头。
        directory = self.db.config["localBackupDirectory"]
        for role in ROLES:
            media = self.checkpoints[role]["media"]
            self.frozen_file(directory, Path(media["serverPath"]).name, media["sha256"])
        sql = self.report["sql"] = self.db.preflight(frozen_backup=first)
        require(sql["productVersion"] == self.sql_version,
                f"专用 SQL Server 版本不符，预期 {self.sql_version}，实际 {sql['productVersion']}")
        sql["checkpoints"] = {ROLES[0]: {"medium": sql["backup"]}, ROLES[1]: {}}
        self.media = {role: self.db.frozen_medium(self.checkpoints[role]["media"]) for role in ROLES}
        second = self.checkpoints[ROLES[1]]["media"]
        sql["checkpoints"][ROLES[1]]["medium"] = self.media[ROLES[1]].verify_frozen_backup(second)

    def restore_pair(self):
        records = self.report["sql"]["checkpoints"]
        self.databases = dict(zip(ROLES, (self.db.source, self.db.restored), strict=True))
        for role, database in self.databases.items():
            expected = self.checkpoints[role]
            record = records[role]
            record["restore"] = self.media[role].restore(record["medium"], database=database)
            record["identity"] = self.db.state_identity(database)
            record["business"] = self.db.business(database, [row["migrationId"] for row in self.business["migrations"]],
                                                  self.business["keyword"], self.business["matches"][0])
            require(record["business"] == expected["business"],
                    f"{role} 的迁移 ID、ProductVersion、租户、账号、授权或搜索用户不符")
            actual_catalog = self.db.catalog(database)
            prefix = "independent-" if self.stage is self.report["stages"]["independent_recovery"] else ""
            catalog_path = self.evidence_file(f"{prefix}{role}-catalog.json")
            write_json(catalog_path, actual_catalog)
            record["catalog"] = artifact(catalog_path, self.evidence)
            require(actual_catalog == read_json(self.expected_catalogs[role]),
                    f"{role} 的系统目录与正式升级轮不一致：{catalog_path}")
            record["loginRows"] = self.db.successful_logins(database, self.business)
            verify_checkpoint_logins(role, expected["loginRows"], record["loginRows"])
        identities = [record["identity"] for record in records.values()]
        for key in ("database", "databaseId", "databaseGuid"):
            require(len({identity[key] for identity in identities}) == len(ROLES),
                    f"升级前后恢复库的实际 {key} 重复：{identities}")
        require(len({item["path"] for identity in identities for item in identity["files"]}) == 4,
                f"升级前后恢复库的物理文件未独立：{identities}")
        self.active_checkpoints = records
        self.approved_rows = {record["identity"]["database"]: record["loginRows"] for record in records.values()}

    def build_observer(self):
        require(self.dotnet and self.dotnet.is_file(), "缺少执行原版 Release 及编译观测器的 dotnet")
        project = self.evidence / "observer"
        shutil.copytree(self.repo / "eng/r3-template-observer", project, ignore=shutil.ignore_patterns("obj", "bin"))
        write_json(project / "global.json", {"sdk": {"version": OBSERVER_SDK, "rollForward": "disable"}})
        config = self.evidence_file("observer-NuGet.Config")
        config.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
        sdk = self.command([self.dotnet, "--version"], project, "dotnet-version.log", extra_env=self.env)[1]
        self.report["environment"].update(sdk=sdk.read_text().strip(), dotnet=str(self.dotnet),
                                          dotnetSha256=sha256(self.dotnet))
        self.command([self.dotnet, "restore", "Observer.csproj", "--configfile", config, "--no-http-cache"],
                     project, "observer-restore.log", extra_env=self.env)
        self.command([self.dotnet, "build", "Observer.csproj", "--configuration", "Release", "--no-restore",
                      "--disable-build-servers", "-p:UseSharedCompilation=false"],
                     project, "observer-build.log", extra_env=self.env)
        self.observer = project / "bin/Release/net9.0/Observer.dll"
        self.report["inputs"]["startupObserver"] = artifact(self.observer, self.evidence)

    def process_environment(self, entry):
        require(sha256(self.observer) == self.report["inputs"]["startupObserver"]["sha256"], "进程观测器摘要已改变")
        env = {"DOTNET_STARTUP_HOOKS": str(self.observer)}
        if entry == "Migrator":
            return env | {"R3_TEMPLATE_OBSERVER_MODE": "migrator",
                          "R3_TEMPLATE_OBSERVER_EVIDENCE": str(self.evidence_file(f"{self.role}-migrator-target.jsonl")),
                          "R3_TEMPLATE_OBSERVER_ASSEMBLIES": str(self.evidence_file(f"{self.role}-migrator-loaded.json"))}
        return env | {"R3_TEMPLATE_OBSERVER_MODE": "host",
                      "R3_TEMPLATE_OBSERVER_EVIDENCE": str(self.evidence_file(f"{self.role}-host-loaded.json")),
                      "R3_TEMPLATE_OBSERVER_REQUESTS": str(self.evidence_file(f"{self.role}-host-search.jsonl")),
                      "R3_TEMPLATE_OBSERVER_REQUEST_ID": self.request_id,
                      "R3_TEMPLATE_OBSERVER_KEYWORD": self.business["keyword"]}

    def sql_state(self, label):
        result = {}
        for role, database in self.databases.items():
            identity = self.db.state_identity(database)
            business = self.db.business(database, [row["migrationId"] for row in self.business["migrations"]],
                                        self.business["keyword"], self.business["matches"][0])
            catalog = self.db.catalog(database)
            path = self.evidence_file(f"{self.role}-{label}-{role}-catalog.json")
            write_json(path, catalog)
            result[database] = {"identity": identity, "business": business, "catalog": artifact(path, self.evidence)}
            require(identity == self.active_checkpoints[role]["identity"] and business == self.business
                    and catalog == read_json(self.expected_catalogs[role]),
                    f"{label} 的 {database} 实际身份、迁移、业务或表结构偏离恢复点，见 {path}")
        return result

    def login_rows(self):
        return {name: self.db.successful_logins(name, self.business) for name in self.databases.values()}

    def read_events(self, name):
        path = self.evidence / name
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []

    def launch_migrator(self, database):
        verify_release_files(self.migrator_output, self.migrator_inventory, "Migrator")
        with self.process(self.migrator_output, "Migrator", ["-q"], database, f"{self.role}-migrator", trace=True) as (
                process, log, launch):
            process.wait(timeout=300)
        return launch, log

    def verify_assemblies(self, entry, launch, output, manifest, report):
        label = "host" if entry == "Web.Host" else "migrator"
        path = self.evidence / f"{self.role}-{label}-loaded.json"
        require(path.is_file(), f"{entry} PID {launch['pid']} 缺少实际程序集记录：{path.name}")
        report["evidence"] = artifact(path, self.evidence)
        expected_entry = manifest["entry"]
        require(Path(launch["argv"][1]) == output / expected_entry["path"]
                and launch["entrySha256"] == expected_entry["sha256"],
                f"{entry} PID {launch['pid']} 的启动入口与原版清单不符：{launch}")
        anchors = MIGRATOR_SHARED if entry == "Migrator" else SHARED
        framework = {Path(dll).stem for dll in manifest["frameworkDlls"]}
        optional = {"AutoMapper", "Abp.AutoMapper"} if entry == "Migrator" else set()
        verify_entry_assemblies(read_json(path), launch, output, manifest, report, EXPECTED_RUNTIME, entry,
                                framework, anchors=anchors, optional_assemblies=optional)

    def migrate(self, target, record):
        record["before"] = self.sql_state("before-migration")
        before = record["beforeLoginRows"] = self.login_rows()
        for database, rows in self.approved_rows.items():
            verify_checkpoint_logins(database, rows, before[database])
        launch, log = self.launch_migrator(target)
        record["launch"] = launch
        server = self.db.identity["serverName"]
        rows = self.read_events(f"{self.role}-migrator-target.jsonl")
        record["connections"] = {"expected": {"pid": launch["pid"], "serverName": server, "database": target},
                                 "observed": rows}
        require(launch["exitCode"] == 0, f"Migrator -q 退出 {launch['exitCode']}，详见 {log.name}")
        check_migration_target(rows, launch["pid"], server, target)
        launch["sharedRuntime"] = shared_runtime_trace(log, "Migrator")
        self.verify_assemblies("Migrator", launch, self.migrator_output, self.migrator_manifest,
                               record.setdefault("loaded", {}))
        record["after"] = self.sql_state("after-migration")
        record["afterLoginRows"] = self.login_rows()
        require(record["afterLoginRows"] == before, "Migrator 改变了两库的成功登录行")

    def browser_database(self, target, control):
        return target

    def capture_login_end(self, record, target, control, original_third):
        if not record.get("authenticationMayHaveStarted"):
            return
        record["afterLoginRows"] = after = dict.fromkeys(self.databases.values())
        record["loginDifferences"] = differences = {name: {"status": "unknown"} for name in after}
        for name in after:
            try:
                after[name] = self.db.successful_logins(name, self.business)
            except Exception as error:
                record["subsequentErrors"].append(
                    {"phase": "login_readback", "database": name, "reason": self.redact(str(error))})
                continue
            before = record["beforeLoginRows"][name]
            differences[name] = {"status": "known", "added": [row for row in after[name] if row not in before],
                                 "removed": [row for row in before if row not in after[name]]}
        if all(rows is not None for rows in after.values()):
            try:
                added = added_login(record["beforeLoginRows"], after, target, control)
                require(self.role != "before_upgrade" or added["id"] != original_third["id"]
                        or added["creationTime"] != original_third["creationTime"],
                        f"{target} 新增的 ID 3 未能与升级轮原写入区分：{added}")
                record["addedLogin"] = added
            except VerificationError as error:
                record["subsequentErrors"].append({"phase": "login_write", "reason": self.redact(str(error))})

    def browser(self, target, control, record):
        original_third = self.checkpoints["after_upgrade"]["loginRows"][-1]
        self.request_id = secrets.token_hex(16)
        record.update(searchRequestId=self.request_id, subsequentErrors=[])

        def before_login():
            start = record["beforeLoginRows"] = self.login_rows()
            verify_path_login_start(self.approved_rows, start, target, original_third)
            record["authenticationMayHaveStarted"] = True

        browser_error = None
        try:
            self.round(self.browser_database(target, control), self.role, before_login=before_login,
                       after_browser=lambda: self.capture_login_end(record, target, control, original_third),
                       search_request_id=self.request_id)
        except (Exception, KeyboardInterrupt) as error:
            browser_error = error

        outcome = record["outcome"] = self.report.get("rounds", {}).get(self.role, {})
        host = outcome.get("host")
        if host:
            try:
                self.verify_assemblies("Web.Host", host, self.output, self.host_output,
                                       record.setdefault("loaded", {}))
                events = self.read_events(f"{self.role}-host-search.jsonl")
                search = outcome.get("steps", {}).get("search", {})
                server = self.db.identity["serverName"]
                record["readTarget"] = {"expected": {"pid": host["pid"], "serverName": server, "database": target},
                                        "events": events}
                if not browser_error:
                    verify_query_target(events, host["pid"], server, target, search, self.request_id,
                                        self.business["keyword"])
                    steps = outcome["steps"]
                    require(steps["client"]["script"] == self.report["inputs"]["angular"]["entryScript"]["path"]
                            and steps["client"]["scriptSha256"] == self.report["inputs"]["angular"]["entryScript"]["sha256"],
                            "浏览器主脚本未对应冻结 Angular production 清单")
                    record["readTarget"]["verified"] = True
            except Exception as error:
                record["subsequentErrors"].append({"phase": "host_evidence", "reason": self.redact(str(error))})
        if browser_error:
            raise browser_error
        if record["subsequentErrors"]:
            first, *later = record["subsequentErrors"]
            record["subsequentErrors"] = later
            record["failurePhase"] = first["phase"]
            raise VerificationError(first["reason"])
        record["after"] = self.sql_state("after-business")
        self.approved_rows = record["afterLoginRows"]

    def run_path(self, role):
        self.role = role
        target = self.databases[role]
        control, = (name for name in self.databases.values() if name != target)
        record = self.report["paths"][role]
        record.update(status="running", target=target, control=control, checkpoints=self.active_checkpoints)
        phase = "migrator"
        try:
            self.migrate(target, record.setdefault("migrator", {}))
            phase = "browser"
            self.browser(target, control, record.setdefault("browser", {}))
        except (Exception, KeyboardInterrupt) as error:
            failure_phase = record.get("browser", {}).get("failurePhase", phase)
            record.update(status="failed", exitCode=1, failurePhase=failure_phase,
                          reason=self.redact(str(error)) or type(error).__name__)
            raise
        else:
            record.update(status="passed", exitCode=0)

    def restore_independent(self):
        first_pair = self.report["sql"]
        self.previous_sql_commands.extend(self.db.commands)
        first_id = self.run_id
        self.run_id = secrets.token_hex(8)
        try:
            self.sql_preflight()
            self.restore_pair()
        finally:
            if self.report["sql"] is not first_pair:
                first_pair["independentRecovery"] = self.report["sql"]
            self.report["sql"] = first_pair
            self.run_id = first_id

    def frozen_inputs_after(self):
        for path, expected in self.original_hashes.items():
            checked_file(path.parent, path.name, expected)
        self.report["frozenInputsAfter"] = {"verified": len(self.original_hashes)}
        if hasattr(self, "checkpoints") and hasattr(self, "db"):
            directory = self.db.config["localBackupDirectory"]
            self.report["frozenInputsAfter"]["media"] = {
                role: artifact(directory / Path(checkpoint["media"]["serverPath"]).name, directory)
                for role, checkpoint in self.checkpoints.items()
                if directory / Path(checkpoint["media"]["serverPath"]).name in self.original_hashes}

    def execute_steps(self, steps, *, business=False):
        failures = []
        for stage, action in (*steps, *((name, getattr(self, name)) for name in CLEANUP)):
            if stage == "independent_recovery" and not failures:
                self.report["stages"][stage]["reason"] = "前一路径通过，继续使用核准的两库"
                continue
            can_continue = failures and failures[0][0] == ROLES[0] and len(failures) == 1
            if failures and stage not in CLEANUP and not (can_continue and stage in (*ROLES, "independent_recovery")):
                self.report["stages"][stage]["reason"] = "前置阶段失败"
                continue
            try:
                self.step(stage, action)
            except (Exception, KeyboardInterrupt) as error:
                reason = self.redact(str(error)) or type(error).__name__
                self.report["stages"][stage].update(status="failed", exitCode=1, reason=reason)
                failures.append((stage, reason))
                if isinstance(error, KeyboardInterrupt):
                    failures.append((stage, "接到中断，停止后续业务路径"))
        if hasattr(self, "db"):
            commands = self.evidence / "sql-commands.json"
            write_json(commands, self.previous_sql_commands + self.db.commands)
            self.report["sqlCommands"] = artifact(commands, self.evidence)
        if failures:
            self.report["reason"] = failures[0][1]
            self.report["subsequentErrors"] = [reason for _, reason in failures[1:]]
            print(f"{PROFILE}：{failures[0][1]}", file=sys.stderr)
        self.report.update(status="failed" if failures else "passed" if business else "inputs_verified",
                           exitCode=int(bool(failures)),
                           finishedAt=datetime.now(timezone.utc).isoformat())
        self.save()
        return self.report["exitCode"]

    def input_steps(self):
        self.report["inputs"]["rollbackSources"] = [artifact(self.repo / "eng" / name, self.repo) for name in
                                                  ("r3_template_original_rollback.py", "r3_template_upgrade_sql.py",
                                                   "r3_template_net9_runtime.py", "r3_template_net10_runtime.py",
                                                   "r3-template-observer/Observer.csproj",
                                                   "r3-template-observer/StartupHook.cs")]
        actions = (self.original_inputs, self.inputs, self.angular_inputs, self.upgrade_inputs,
                   self.sql_preflight, self.restore_pair)
        return tuple(zip(STEPS, actions, strict=True))

    def execute_full(self):
        return self.execute_steps((*self.input_steps(), ("observer_build", self.build_observer),
                                   (ROLES[0], lambda: self.run_path(ROLES[0])),
                                   ("independent_recovery", self.restore_independent),
                                   (ROLES[1], lambda: self.run_path(ROLES[1]))), business=True)


def execute(args):
    for name in ("DEBUG", "PWDEBUG"):
        os.environ.pop(name, None)
    run = RollbackRun(ROOT, make_run_directory(args.evidence_root, PROFILE + "-"),
                      args.frozen_root.resolve(), args.rollback_upgrade_run.resolve(), args.runtime_config, args.dotnet)
    print(f"{PROFILE} report: {run.report_path}", flush=True)
    return run.execute_full()
