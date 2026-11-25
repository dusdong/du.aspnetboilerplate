"""从固定原版模板构建并运行两轮可比较的租户浏览器验收。"""

from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
from threading import Thread
import time
from urllib import error, request
import xml.etree.ElementTree as ET

from r3_template_browser import AUTH, USER_CONFIG, browser_round
from r3_template_sql import ADMIN, RuntimeDatabase
from r3_web_host import ABP_VERSION, INPUTS, PREFIX, PROVIDER, R3Run, STAGES as HOST_STAGES, TEMPLATE, TFM
from r3_web_host import artifact, is_abp, is_maintained, project_path, write_json
from verify import ROOT, VerificationError, make_run_directory, read_json, require, sha256


PLANNING_COMMIT = "ecb1c88aaa02aba61a47cfed0fb3db8362cb31ac"
LOCK_SHA = "3e55c44022c5c15bf2c474eb483f8161945151261f06d00218fffbdb86c0d14f"
ANGULAR_PACKAGES = {"@angular/core": "19.2.1", "@angular/cli": "19.2.1",
                    "abp-ng2-module": "12.1.0", "abp-web-resources": "6.1.0"}
RUNTIME_STAGES = ("runtime_inputs", "migrator_build", "angular_build", "sql_preflight",
                  "migrate_and_seed", "prepare_and_backup", "source_browser", "restore_database", "restore_browser", "cleanup")
APP_PORTS = ("frontendPort", "hostPort")
SQL_FIELDS = ("sqlPort", "sqlServerName", "sqlBackupDirectory", "localBackupDirectory")
CREDENTIALS = ("R3_TEMPLATE_SQL_USER", "R3_TEMPLATE_SQL_PASSWORD", "R3_TEMPLATE_TENANT_PASSWORD")
HTTP = request.build_opener(request.ProxyHandler({}))


def check_lock(path):
    actual = sha256(path)
    require(actual == LOCK_SHA, f"Angular yarn.lock 摘要不符，预期 {LOCK_SHA}，实际 {actual}")


def check_login_deltas(before, after, source, restored):
    deltas = {database: after[database] - before[database] for database in (source, restored)}
    require(deltas == {source: 0, restored: 1},
            f"恢复轮成功登录增量不符，预期 {source}=0 / {restored}=1，实际 {deltas}")
    return deltas


def inventory(root, *, include_app_data=False, exclude=()):
    rows = {path.relative_to(root).as_posix(): sha256(path) for path in sorted(root.rglob("*"))
            if path.is_file() and path.relative_to(root).as_posix() not in exclude
            and (include_app_data or "App_Data" not in path.relative_to(root).parts)}
    require(rows, f"找不到产物：{root}")
    summary = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    return {"sha256": summary, "files": rows}


def available(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


class SpaHandler(SimpleHTTPRequestHandler):
    def log_message(self, format_, *args):
        # 浏览器报告只记录已核对的请求路径和字段。
        pass

    def send_head(self):
        path = Path(self.translate_path(self.path))
        if not path.is_file() and not path.suffix and "text/html" in self.headers.get("Accept", ""):
            self.path = "/index.html"
        return super().send_head()


def shared_runtime_trace(log, label):
    log_text = log.read_text(encoding="utf-8")
    shared = {}
    for name in ("Microsoft.NETCore.App", "Microsoft.AspNetCore.App"):
        found = sorted(set(re.findall(r"(?:Chose FX version|Resolved framework:)\s*\[([^\]]+/shared/"
                                      + re.escape(name) + r"/[^\]]+)\]", log_text)))
        require(len(found) == 1, f"{label} 启动记录缺少唯一 {name} 路径，详见 {log.name}")
        shared[name] = {"path": found[0], "version": Path(found[0]).name}
    return shared


class RuntimeSupport:
    database_type = RuntimeDatabase

    def setup_runtime(self, config_file):
        self.config_file = config_file
        self.run_id = secrets.token_hex(8)
        self.credentials = tuple(os.environ.pop(name, None) for name in CREDENTIALS)
        self.passwords = [value for value in self.credentials[1:] if value]
        self.processes = []
        self.ports = {}

    def inputs(self):
        config = read_json(self.config_file)
        require(isinstance(config, dict) and set(APP_PORTS) <= config.keys() <= {*APP_PORTS, *SQL_FIELDS, "chrome"},
                "运行配置须仅包含规定的无凭据字段，详见复跑文档")
        self.config_input = config
        for key in APP_PORTS:
            require(type(config[key]) is int and 1024 <= config[key] <= 65535, f"运行配置端口不符：{key}")
        require(config["frontendPort"] != config["hostPort"], "Host 和 Angular 需要两个独立端口")
        self.ports = {key: config[key] for key in APP_PORTS}
        frontend = f"http://127.0.0.1:{config['frontendPort']}"
        host = f"http://127.0.0.1:{config['hostPort']}"
        self.runtime = self.ports | {"frontend": frontend, "host": host}
        require(all(available(port) for port in self.ports.values()), f"本轮应用端口已使用：{self.ports}")
        self.ports_checked = True
        self.report["inputs"]["runtimeConfig"] = self.runtime.copy()
        self.report["inputs"]["runtimeConfigFile"] = str(self.config_file.resolve())
        self.report["inputs"]["profileSources"] = [artifact(self.repo / "eng" / filename, self.repo)
                                                    for filename in ("verify.py", "r3_web_host.py",
                                                                     "r3_template_runtime.py", "r3_template_sql.py",
                                                                     "r3_template_browser.py")]
        self.report["inputs"]["runtimeOverrides"] = {
            "ASPNETCORE_ENVIRONMENT": "Development", "DOTNET_ENVIRONMENT": "Development",
            "Kestrel__Endpoints__Http__Url": host,
            "App__ServerRootAddress": host + "/", "App__ClientRootAddress": frontend + "/",
            "App__CorsOrigins": frontend,
            "ConnectionStrings__Default": "进程环境注入，按阶段切换源库和恢复库",
            "Logging__LogLevel__Default": "Warning", "Logging__LogLevel__Microsoft.Hosting.Lifetime": "Information",
            "HOME": "本轮隔离目录，隔离本机用户机密配置"
        }
        (self.evidence / "runtime-home").mkdir()


    def sql_inputs(self, frozen_backup=None):
        config = self.config_input
        missing = [key for key in SQL_FIELDS if config.get(key) in (None, "")]
        missing.extend(key for key, value in zip(CREDENTIALS, self.credentials) if not value)
        require(not missing, f"缺少 SQL Server 或登录输入：{', '.join(missing)}")
        port = config["sqlPort"]
        require(type(port) is int and 1024 <= port <= 65535 and port not in self.ports.values(),
                "sqlPort 必须是独立于 Host 和 Angular 的有效环回端口")
        require(isinstance(config["sqlServerName"], str)
                and re.fullmatch(r"[a-zA-Z0-9_-]{1,63}", config["sqlServerName"]),
                "sqlServerName 须明确指定专用测试实例名")
        require(isinstance(config["sqlBackupDirectory"], str)
                and re.fullmatch(r"/[a-zA-Z0-9_/-]+", config["sqlBackupDirectory"]),
                "sqlBackupDirectory 须使用明确的 SQL Server Linux 绝对路径")
        local = config["localBackupDirectory"]
        require(isinstance(local, str) and Path(local).is_absolute() and Path(local).is_dir(),
                "localBackupDirectory 须指向运行机可读取的现有备份目录")
        sql_config = {key: config[key] for key in SQL_FIELDS}
        sql_config["localBackupDirectory"] = Path(local).resolve(strict=True)
        self.report["inputs"]["runtimeConfig"].update(
            sql_config | {"localBackupDirectory": str(sql_config["localBackupDirectory"])})
        user, sql_password, self.admin_password = self.credentials
        try:
            self.db = self.database_type(sql_config, user, sql_password, self.run_id, frozen_backup=frozen_backup)
            self.report["environment"]["pymssql"] = version("pymssql")
        except (ImportError, PackageNotFoundError) as error:
            raise VerificationError("SQL Server 客户端 pymssql 不可用，请在入口的 Python 环境安装") from error
        chrome = config.get("chrome")
        self.runtime["chrome"] = str(Path(chrome).resolve(strict=True)) if chrome else None
        self.report["inputs"]["runtimeConfig"]["chrome"] = self.runtime["chrome"]
        self.report["environment"]["playwright"] = version("playwright")


    def redact(self, message):
        for password in self.passwords:
            message = message.replace(password, "[已脱敏]")
        message = re.sub(r"(?im)^(.*(?:Host database|Connection string)\s*:\s*).*$", r"\1[已脱敏]", message)
        return message


    def process_environment(self, entry):
        return {}

    @contextmanager
    def process(self, output, entry, arguments, database, label, *, trace=False):
        log = self.evidence_file(f"{label}.console.log")
        command = [str(self.dotnet), str(output / (PREFIX + entry + ".dll")), *arguments]
        overrides = self.report["inputs"]["runtimeOverrides"]
        env = {key: value for key, value in os.environ.items() if key in ("PATH", "TMPDIR", "LANG", "LC_ALL")}
        env.update(self.env)
        env.update({key: value for key, value in overrides.items() if key not in ("ConnectionStrings__Default", "HOME")})
        env.update(HOME=str(self.evidence / "runtime-home"),
                   ConnectionStrings__Default=self.db.connection_string(database))
        env.update(self.process_environment(entry))
        if trace:
            env.update(COREHOST_TRACE="1", COREHOST_TRACE_VERBOSITY="4")
        file_setting = ET.parse(output / "log4net.config").find("./appender/file")
        require(file_setting is not None and file_setting.get("value"), "缺少固定模板的 Log4Net 文件路径")
        file_log = Path(os.path.abspath(output / file_setting.get("value")))
        require(file_log.parent.resolve().is_relative_to(self.evidence), f"文件日志路径超出本轮目录：{file_log}")
        file_log.parent.mkdir(parents=True, exist_ok=True)
        require((not file_log.exists() and not file_log.is_symlink())
                or (file_log.is_symlink() and file_log.readlink() == Path("/dev/null")),
                f"应用文件日志路径已存在：{file_log}")
        if not file_log.is_symlink():
            file_log.symlink_to("/dev/null")
        record = {"argv": command, "cwd": str(output), "log": log.name, "database": database,
                  "entrySha256": sha256(Path(command[1])), "exitCode": None}
        self.stage["commands"].append(record)
        with log.open("w", encoding="utf-8") as sink, subprocess.Popen(
            command, cwd=output, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, encoding="utf-8", errors="replace",
        ) as process:
            def copy_console():
                for line in process.stdout:
                    sink.write(self.redact(line))
                    sink.flush()

            thread = Thread(target=copy_console, daemon=True)
            thread.start()
            record["pid"] = process.pid
            self.processes.append(process)
            self.save()
            try:
                yield process, log, record
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                thread.join(timeout=5)
                record["exitCode"] = process.returncode
                self.save()


    @contextmanager
    def launch_host(self, database, label):
        require(inventory(self.output) == self.host_inventory, "实际启动的 Release Host 产物与构建证据不符")
        require(available(self.ports["hostPort"]), f"Host 端口已被占用：{self.ports['hostPort']}")
        with self.process(self.output, "Web.Host", [], database, label, trace=True) as (process, log, record):
            deadline = time.monotonic() + 75
            log_text = ""
            while time.monotonic() < deadline:
                require(process.poll() is None, f"Release Host 启动退出 {process.returncode}，详见 {log.name}")
                log_text = log.read_text(encoding="utf-8")
                environment = re.search(r"Hosting environment:\s+(\w+)", log_text)
                if environment:
                    require(environment[1] == "Development", f"Host 实际环境为 {environment[1]}，预期 Development")
                    if f"Now listening on: {self.runtime['host']}" in log_text:
                        break
                time.sleep(0.2)
            else:
                raise VerificationError(f"Release Host 未报告本轮地址和实际 Development 环境，详见 {log.name}")
            record.update(environment=environment[1], address=self.runtime["host"],
                          sharedRuntime=shared_runtime_trace(log, "Host"))
            with HTTP.open(self.runtime["host"] + USER_CONFIG, timeout=10) as response:
                require(response.status == 200, f"Host 应用配置 HTTP {response.status}")
            yield record
            require(process.poll() is None, f"Release Host 在 {label} 完成前退出，详见 {log.name}")
        require(record["exitCode"] == 0, f"Release Host {label} 未正常停止，退出 {record['exitCode']}")


    def round(self, database, label, *, before_login=None, after_browser=None, search_request_id=None):
        require(inventory(self.browser_output, include_app_data=True) == self.angular_inventory,
                "实际提供的 Angular production 产物已改变")
        outcome = {"database": database, "inputs": self.report["inputs"]["host"]["entry"],
                   "frontendSha256": self.angular_inventory["sha256"], "exitCode": 1}
        self.report.setdefault("rounds", {})[label] = outcome
        try:
            with self.launch_host(database, "host-" + label) as record:
                outcome["host"] = record
                handler = partial(SpaHandler, directory=str(self.browser_output))
                with ThreadingHTTPServer(("127.0.0.1", self.ports["frontendPort"]), handler) as server:
                    thread = Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    try:
                        browser_round(self.runtime, self.browser_output, self.business, self.admin_password,
                                      outcome, before_login=before_login, search_request_id=search_request_id)
                    finally:
                        try:
                            if after_browser:
                                after_browser()
                        finally:
                            server.shutdown()
                            thread.join()
            outcome["exitCode"] = 0
        except Exception as failure:
            outcome["reason"] = self.redact(str(failure))
            raise
        finally:
            write_json(self.evidence_file(f"{label}-round.json"), outcome)
        return outcome


    def frozen_angular(self, manifest_sha256):
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
            "originalManifestSha256": manifest_sha256, "originalInventory": self.original_angular["sha256"],
            "servedInventory": self.angular_inventory["sha256"], "files": len(expected),
            "configOriginalSha256": config_before, "configServedSha256": expected[config_name],
            "configChanges": changes, "cors": self.runtime["frontend"],
        }
        write_json(self.evidence_file("angular-production-files.json"), self.angular_inventory)

    def cleanup(self):
        ports = {key: {"number": port, "released": available(port)} for key, port in self.ports.items()} \
            if getattr(self, "ports_checked", False) else {}
        processes = {process.pid: process.poll() for process in self.processes}
        self.report["cleanup"] = {"ports": ports, "processes": processes}
        require(all(item["released"] for item in ports.values()) and all(code is not None for code in processes.values()),
                f"本轮进程或应用端口仍在使用：{self.report['cleanup']}")



class RuntimeRun(RuntimeSupport, R3Run):
    def __init__(self, repo, evidence, config_file):
        super().__init__(repo, evidence)
        self.setup_runtime(config_file)
        self.angular = self.root.parent / "angular"
        self.browser_output = self.angular / "dist/browser"
        self.migrator_entry = project_path("Migrator")
        self.migrator_output = self.root / self.migrator_entry.parent / f"bin/Release/{TFM}"
        self.report.update(profile="r3-template-runtime", runId=self.run_id,
                           coverageNotRun=["同目标维护包替换", ".NET 10 / EF Core 10 升级",
                                           "升级后回退", "其他消费组合、平台、CI 和部署"])
        self.report["stages"].update(
            {stage: {"status": "not_run", "exitCode": None, "commands": [], "evidence": []}
             for stage in RUNTIME_STAGES})

    def preflight(self):
        fixed = self.git(self.repo, "runtime-template-gitlink.log", "ls-tree", PLANNING_COMMIT, "--", TEMPLATE)
        require(fixed.split() == ["160000", "commit", INPUTS[TEMPLATE][0], TEMPLATE],
                f"R3 运行设计基点 {PLANNING_COMMIT} 的模板 gitlink 不符：{fixed}")
        self.report["inputs"]["runtimePlanningCommit"] = PLANNING_COMMIT
        super().preflight()

    def inspect_output(self):
        super().inspect_output()
        rows = self.host["frameworkRuntimeDlls"]
        require(len(rows) == 11 and {row["version"] for row in rows} == {ABP_VERSION},
                "实际 Release Host 的 11 个原版 ABP 运行库版本不符")
        target = self.assets[self.entry.as_posix()]
        providers = [row["version"] for row in target["packages"].values() if row["id"] == PROVIDER]
        require(providers == ["9.0.5"], f"实际 Release Host 的 SQL Server Provider 版本不符：{providers}")
        self.host_inventory = inventory(self.output)
        self.report["inputs"]["host"] = {"entry": artifact(self.output / (PREFIX + "Web.Host.dll"), self.evidence),
                                         "inventory": self.host_inventory["sha256"],
                                         "abpPackages": sorted(row["packageId"] for row in rows),
                                         "abpVersion": ABP_VERSION, "sqlServerProvider": providers[0]}
        write_json(self.evidence_file("release-host-files.json"), self.host_inventory)

    def build_migrator(self):
        self.run_dotnet(["restore", self.migrator_entry, "--configfile", self.config, "--no-http-cache",
                         "--force", "-p:Configuration=Release", "--verbosity", "normal"], "migrator-restore.log")
        path = self.root / self.migrator_entry.parent / "obj/project.assets.json"
        saved = self.evidence_file("migrator.project.assets.json")
        shutil.copyfile(path, saved)
        data = read_json(saved)
        require(data["project"]["restore"]["originalTargetFrameworks"] == [TFM]
                and set(data["project"]["restore"]["sources"]) == {"https://api.nuget.org/v3/index.json"},
                "Migrator 目标框架或实际还原来源不符")
        packages = {key: rows for key, rows in data["targets"][TFM].items() if rows["type"] == "package"}
        ids = dict(key.split("/", 1) for key in packages)
        require(all(not is_maintained(name) and (not is_abp(name) or value == ABP_VERSION)
                    for name, value in ids.items()) and ids.get(PROVIDER) == "9.0.5",
                "Migrator 混入维护包或原版 ABP/SQL Server Provider 版本不符")
        self.run_dotnet(["build", self.migrator_entry, "--configuration", "Release", "--no-restore",
                         "--disable-build-servers", "-p:UseSharedCompilation=false",
                         "--verbosity", "minimal"], "migrator-build.log")
        require(sha256(path) == sha256(saved), "Migrator 构建改写了还原图")
        self.migrator_inventory = inventory(self.migrator_output)
        write_json(self.evidence_file("release-migrator-files.json"), self.migrator_inventory)
        self.report["inputs"]["migrator"] = {
            "project": str(self.migrator_entry), "resolvedPackages": ids,
            "assets": artifact(saved, self.evidence),
            "entry": artifact(self.migrator_output / (PREFIX + "Migrator.dll"), self.evidence),
            "inventory": self.migrator_inventory["sha256"]
        }

    def angular_build(self):
        archive = self.evidence_file("angular-source.tar")
        self.git(self.repo / TEMPLATE, "angular-archive.log", "archive", "--format=tar",
                 f"--output={archive}", INPUTS[TEMPLATE][0], "angular")
        self.command(["tar", "-xf", archive, "-C", self.root.parent], self.evidence, "angular-extract.log")
        lock = self.angular / "yarn.lock"
        check_lock(lock)
        require(not (self.angular / "node_modules").exists(), "Angular 隔离目录的 node_modules 必须为空")
        node = self.read_command(["node", "--version"], self.angular, "node-version.log")
        yarn_env = {"YARN_IGNORE_PATH": "1"}
        cache = Path(os.environ.get("YARN_CACHE_FOLDER") or self.evidence / "yarn-cache").resolve()
        _, version_log = self.command(["yarn", "--version"], self.angular, "yarn-version.log", extra_env=yarn_env)
        yarn = version_log.read_text(encoding="utf-8").strip()
        require(re.fullmatch(r"1\.22\.\d+", yarn), f"需要 Yarn Classic 1.22，实际 {yarn}")
        self.report["environment"].update(node=node, yarn=yarn)
        self.command(["yarn", "install", "--frozen-lockfile", "--non-interactive", "--no-progress",
                      "--cache-folder", cache], self.angular, "angular-install.log", extra_env=yarn_env)
        check_lock(lock)
        versions = {name: read_json(self.angular / "node_modules" / name / "package.json")["version"]
                    for name in ANGULAR_PACKAGES}
        require(versions == ANGULAR_PACKAGES, f"Angular 已安装版本与固定锁定版本不符：{versions}")
        self.command(["yarn", "ng", "build", "--configuration", "production"], self.angular, "angular-build.log",
                     extra_env=yarn_env)
        check_lock(lock)
        frontend_asset = self.browser_output / "assets/appconfig.production.json"
        config = read_json(frontend_asset)
        overrides = {"remoteServiceBaseUrl": self.runtime["host"], "appBaseUrl": self.runtime["frontend"]}
        diff = {key: {"from": config[key], "to": value} for key, value in overrides.items()}
        before = sha256(frontend_asset)
        write_json(frontend_asset, config | overrides)
        require((self.browser_output / "index.html").is_file()
                and len(list(self.browser_output.glob("main-*.js"))) == 1, "Angular production 入口或主脚本缺失")
        self.angular_inventory = inventory(self.browser_output)
        write_json(self.evidence_file("angular-production-files.json"), self.angular_inventory)
        self.report["inputs"]["angular"] = {
            "archive": artifact(archive, self.evidence), "lock": artifact(lock, self.evidence),
            "packageVersions": versions, "cache": str(cache), "nodeModulesInitiallyAbsent": True,
            "configuration": "production", "configSourceSha256": before,
            "config": artifact(frontend_asset, self.evidence), "configDiff": diff,
            "output": str(self.browser_output.relative_to(self.evidence)), "inventory": self.angular_inventory["sha256"]
        }

    def sql_preflight(self):
        self.sql_inputs()
        self.report["sql"] = self.db.preflight()
        self.report["sql"]["sourceCreation"] = self.db.create_source()

    def migrate(self):
        require(inventory(self.migrator_output) == self.migrator_inventory, "实际启动的 Migrator 产物已改变")
        with self.process(self.migrator_output, "Migrator", ["-q"], self.db.source, "migrator") as (process, log, _):
            code = process.wait(timeout=300)
        require(code == 0, f"Migrator -q 退出 {code}，详见 {log.name}")
        migrations = self.root / project_path("EntityFrameworkCore").parent / "Migrations"
        self.expected_migrations = sorted(path.stem for path in migrations.glob("*.cs")
                                          if re.match(r"^\d{14}_", path.name)
                                          and not path.name.endswith(".Designer.cs"))
        require(self.expected_migrations, "固定模板迁移源码为空")
        self.report["sql"]["sourceSeed"] = self.db.seed(self.db.source, self.expected_migrations)

    def api(self, path, payload, headers):
        req = request.Request(self.runtime["host"] + path, json.dumps(payload).encode(),
                              {"Content-Type": "application/json", **headers})
        try:
            with HTTP.open(req, timeout=20) as response:
                data = json.load(response)
                status = response.status
        except error.HTTPError as failure:
            raise VerificationError(f"准备会话 {path} HTTP {failure.code}") from failure
        require(data.get("success") is True, f"准备会话 {path} 未返回成功结果")
        self.stage.setdefault("requests", []).append({"method": "POST", "path": path,
                                                      "status": status, "success": True})
        return data["result"]

    def prepare(self):
        source = self.db.source
        seed = self.report["sql"]["sourceSeed"]
        self.keyword = "r3user" + self.run_id
        with self.launch_host(source, "host-prepare"):
            headers = {"Abp-TenantId": str(seed["tenant"]["tenantId"])}
            login = self.api(AUTH, {"userNameOrEmailAddress": ADMIN, "password": self.admin_password}, headers)
            self.passwords.extend(item for item in (login.get("accessToken"), login.get("encryptedAccessToken")) if item)
            require(login.get("userId") == seed["account"]["userId"] and login.get("accessToken"),
                    f"准备会话登录用户与数据库预期不符，预期 {seed['account']['userId']}，实际 {login.get('userId')}")
            password = "R3a!" + secrets.token_hex(12)
            self.passwords.append(password)
            result = self.api("/api/services/app/User/Create",
                              {"userName": self.keyword, "name": "Runtime", "surname": "Fixture",
                               "emailAddress": self.keyword + "@example.invalid", "isActive": True,
                               "roleNames": [], "password": password},
                              headers | {"Authorization": "Bearer " + login["accessToken"]})
            self.expected_user = {"id": result["id"], "userName": result["userName"]}
            require(self.expected_user["userName"] == self.keyword, "应用创建的测试用户名与本轮搜索词不符")
        self.business = self.db.business(source, self.expected_migrations, self.keyword, self.expected_user)
        self.report["sql"].update(expected=self.business,
                                  loginCountAtBackup=self.db.login_count(source, self.business))
        self.report["sql"]["backup"] = self.db.backup()

    def source_round(self):
        database = self.db.source
        before = self.db.login_count(database, self.business)
        self.first = self.round(database, "source")
        try:
            after = self.db.login_count(database, self.business)
            self.first["loginCount"] = {"before": before, "after": after, "delta": after - before}
            require(after - before == 1, f"源库成功登录增量不符，预期 1，实际 {after - before}")
        except Exception as failure:
            self.first.update(exitCode=1, reason=self.redact(str(failure)))
            raise
        finally:
            write_json(self.evidence_file("source-round.json"), self.first)

    def restore(self):
        restored = self.db.restored
        self.report["sql"]["restore"] = self.db.restore(self.report["sql"]["backup"])
        actual = self.db.business(restored, self.expected_migrations, self.keyword, self.expected_user)
        require(actual == self.business, f"恢复后的迁移历史或业务字段与源库不一致：{actual}")
        before = self.db.login_count(restored, self.business)
        require(before == self.report["sql"]["loginCountAtBackup"], f"恢复库的登录前起点不符：{before}")
        self.report["sql"].update(restoredBusiness=actual, restoredLoginCountAtBackup=before)

    def restore_round(self):
        source, restored = self.db.source, self.db.restored
        record = self.report["sql"]["replayedLogin"] = {"sourceDatabase": source, "restoredDatabase": restored}

        def read_counts():
            return {database: self.db.login_count(database, self.business) for database in (source, restored)}

        def before_login():
            record["before"] = read_counts()

        second = self.round(restored, "restore", before_login=before_login)
        try:
            record["after"] = read_counts()
            record["deltas"] = {database: record["after"][database] - record["before"][database]
                                for database in (source, restored)}
            check_login_deltas(record["before"], record["after"], source, restored)
            require(self.first["steps"] == second["steps"] and self.first["browser"] == second["browser"]
                    and self.first["host"]["address"] == second["host"]["address"]
                    and self.first["host"]["sharedRuntime"] == second["host"]["sharedRuntime"],
                    "两轮浏览器、业务字段或宿主运行时不一致")
        except Exception as failure:
            second.update(exitCode=1, reason=self.redact(str(failure)))
            raise
        finally:
            second["loginCountComparison"] = record
            write_json(self.evidence_file("restore-round.json"), second)

    def execute_runtime(self):
        actions = (self.preflight, self.materialize, self.toolchain, super().restore, self.inventory,
                   self.build, self.inspect_output, self.gaps, self.inputs, self.build_migrator,
                   self.angular_build, self.sql_preflight, self.migrate, self.prepare, self.source_round,
                   self.restore, self.restore_round)
        failure = None
        stage = HOST_STAGES[0]
        try:
            for stage, action in zip(HOST_STAGES + RUNTIME_STAGES[:-1], actions, strict=True):
                self.step(stage, action)
        except (Exception, KeyboardInterrupt) as error:
            failure = self.redact(str(error)) or type(error).__name__
            self.report["stages"][stage].update(status="failed", exitCode=1, reason=failure)
        finally:
            try:
                self.step("cleanup", self.cleanup)
            except VerificationError as error:
                failure = f"{failure}; {error}" if failure else str(error)
            if hasattr(self, "db"):
                sql_commands = self.evidence / "sql-commands.json"
                write_json(sql_commands, self.db.commands)
                self.report["sqlCommands"] = artifact(sql_commands, self.evidence)
            for item in self.report["stages"].values():
                if item["status"] == "not_run":
                    item["reason"] = f"{stage} 未通过"
            self.report.update(status="failed" if failure else "passed", exitCode=int(failure is not None),
                               finishedAt=datetime.now(timezone.utc).isoformat())
            if failure:
                self.report["reason"] = failure
                print(f"R3 原版模板运行验证失败：{failure}", file=sys.stderr)
            self.save()
        return self.report["exitCode"]


def execute(args):
    # 调试模式会输出浏览器协议或暂停登录页面，隔离本机全局调试设置。
    for name in ("DEBUG", "PWDEBUG"):
        os.environ.pop(name, None)
    run = RuntimeRun(ROOT, make_run_directory(args.evidence_root, "r3-template-runtime-"), args.runtime_config)
    print(f"R3 原版模板运行报告：{run.report_path}", flush=True)
    return run.execute_runtime()
