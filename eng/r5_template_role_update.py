"""固定模板两代公开包的 SQL Server 用户角色更新验收。"""

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
import time
from urllib import error, request
from urllib.parse import urlencode
from zipfile import ZipFile

from r3_template_browser import AUTH, SESSION, USER_CONFIG, check_session
from r3_template_net10_runtime import verify_migrator_assemblies
from r3_template_net9_runtime import check_migration_target, unique_loaded, verify_entry_assemblies
from r3_template_runtime import available, shared_runtime_trace
from r3_template_upgrade_sql import UpgradeDatabase
from r3_web_host import artifact, write_json
from r5_template_role_prepare import verify_prepared
from verify import ROOT, VerificationError, read_json, require, sha256


RUNTIME = "10.0.15"
SDK = "10.0.404"
SQL_VERSION = "16.0.4236.2"
SQL_IMAGE = "mcr.microsoft.com/mssql/server@sha256:0ec7739e1c5ec2f57861facbe1f2b74f1d3e147c7c97edf91eeea920c5944d9c"
RELEASES = ("r4", "r5")
PROVIDER = "Microsoft.EntityFrameworkCore.SqlServer"
APP = "/api/services/app/"
KEEP_TIME = "2000-02-03T04:05:06"
ROLE_NAMES = {"A": "du-role-a", "B": "du-role-b"}
ROLE_DISPLAYS = {"A": "Role Check A", "B": "Role Check B"}
MAP_PACKAGES = {"Du.Abp.AutoMapper": "Abp.AutoMapper", "Du.AutoMapper": "AutoMapper",
                "Du.AutoMapper.Collection": "AutoMapper.Collection"}
DB_KEYS = ("serverName", "database", "databaseId", "databaseGuid")
STEPS = (("keep", ("durolekeep", "Keep", "First", False), None, "A"),
         ("replace", ("durolereplace", "Replace", "Second", True), ["du-role-b"], "B"),
         ("clear", ("duroleclear", "Clear", "Third", False), [], None))
IDENTITY = """
SELECT CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')) AS serverName,
       DB_NAME() AS [database], DB_ID() AS databaseId,
       CONVERT(nvarchar(36), database_guid) AS databaseGuid
FROM sys.database_recovery_status WHERE database_id = DB_ID()
"""
CHECK_ERRORS = (VerificationError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError)


def fields(user_name, name, surname, active):
    return {"userName": user_name, "name": name, "surname": surname,
            "emailAddress": user_name + "@example.invalid", "isActive": active}


SEED_FIELDS = fields("durolecheck", "Seed", "User", True)


def time_value(value, *, allow_local_offset=False):
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,7}))?([+-]\d{2}:\d{2})?",
                         value or "")
    require(match is not None, f"固定模板的创建时间格式不符：{value!r}")
    if match[3]:
        local_offset = datetime.fromisoformat(match[1]).astimezone().strftime("%z")
        require(allow_local_offset and match[3].replace(":", "") == local_offset,
                f"固定模板的创建时间带有意外偏移：{value!r}")
    return match[1], (match[2] or "").ljust(7, "0")


def check_fields(actual, expected):
    for key, value in expected.items():
        observed = actual.get(key)
        require(type(observed) is type(value) and observed == value,
                f"{key} 预期 {value!r}，实际 {observed!r}")


def result(http):
    require(http.get("error") is None, f"HTTP 回执不可用：{http.get('error')}")
    body = http.get("body")
    require(http.get("status") == 200 and isinstance(body, dict) and body.get("success") is True
            and isinstance(body.get("result"), dict), f"HTTP/ABP 回执不符：HTTP {http.get('status')}")
    return body["result"]


def check_dto(dto, expected, *, allow_local_offset=False):
    check_fields(dto, {"id": expected["id"], **expected["fields"]})
    check_fields(dto, {"roleNames": [role["normalizedName"] for role in expected["roles"]]})
    require(time_value(dto.get("creationTime"), allow_local_offset=allow_local_offset)
            == time_value(expected["creationTime"]),
            f"DTO 创建时间预期 {expected['creationTime']}，实际 {dto.get('creationTime')}")


class SqlIdentityMismatch(VerificationError):
    """独立 SQL 已返回数据，但实测库身份不符合比较前提。"""


def check_sql(data, expected, identity):
    if data["identity"] != identity:
        raise SqlIdentityMismatch(f"独立 SQL 实际库身份不符：{data['identity']}，预期 {identity}")
    require(len(data["users"]) == 1, f"预期唯一目标用户行：{data['users']}")
    user, = data["users"]
    check_fields(user, {"id": expected["id"], "tenantId": expected["tenantId"],
                        "creatorUserId": expected["creatorUserId"], "isDeleted": False, **expected["fields"]})
    require(time_value(user.get("creationTime")) == time_value(expected["creationTime"]),
            f"SQL 创建时间预期 {expected['creationTime']}，实际 {user.get('creationTime')}")
    catalog = [{**role, "tenantId": expected["tenantId"], "isDeleted": False} for role in expected["catalog"]]
    require(data["catalog"] == catalog, f"测试角色定义在提交后改变：{data['catalog']}，预期 {catalog}")
    relations = data["relations"]
    require(len(relations) == len(expected["roles"]),
            f"直接角色关联数量预期 {len(expected['roles'])}，实际 {relations}")
    for row, role in zip(relations, expected["roles"]):
        check_fields(row, {"userId": expected["id"], "tenantId": expected["tenantId"], "roleId": role["id"],
                           "joinedRoleId": role["id"], "roleName": role["name"],
                           "normalizedName": role["normalizedName"], "roleTenantId": expected["tenantId"],
                           "roleIsDeleted": False})


def read_events(path):
    lines = path.read_bytes().splitlines(keepends=True) if path.exists() else []
    return [json.loads(line) for line in lines if line.endswith(b"\n")]


def check_connection(call, events, pid, user_id, identity, *, complete):
    trace = call["request"]
    request_rows = [row["request"] for row in events if row["kind"] == "request"]
    require(len(request_rows) == 1, f"请求 {trace['id']} 缺少唯一业务请求开始事件")
    binding, = request_rows
    check_fields(binding, {"pid": pid, "requestId": trace["id"], "method": trace["method"],
                           "path": trace["path"], "userId": user_id})
    require(binding.get("activityId"), f"请求 {trace['id']} 缺少 Activity ID")
    require(all(row["request"] == binding for row in events), f"请求 {trace['id']} 的事件关联不一致")
    bad = [row for row in events if row["kind"] == "probeError"]
    require(not bad, f"请求 {trace['id']} 的实际连接探查失败：{bad}")
    connections = [row for row in events if row["kind"] == "connection"]
    require(connections, f"请求 {trace['id']} 缺少目标用户业务命令的连接实测")
    for row in connections:
        actual = {key: row.get(key) for key in DB_KEYS}
        require(actual == identity, f"请求 {trace['id']} 业务库预期 {identity}，实际 {actual}")
        require(all(row.get(key) for key in ("sessionId", "connectionId", "clientConnectionId", "context", "commandId")),
                f"请求 {trace['id']} 命令的连接信息不全：{row}")
    if complete:
        responses = [row["status"] for row in events if row["kind"] == "response"]
        require(responses == [call["status"]], f"请求 {trace['id']} 的 Host 与 HTTP 状态不符：{responses}")
        done = [(row["commandId"], row["operation"]) for row in events if row["kind"] == "completed"]
        expected = [(row["commandId"], row["operation"]) for row in connections]
        needed = {"lookup", "write"} if trace["method"] == "PUT" else {"lookup"}
        require(len(set(expected)) == len(expected) and sorted(done) == sorted(expected)
                and {row["operation"] for row in connections} == needed,
                f"请求 {trace['id']} 缺少匹配和完整的目标用户命令：预期类别 {needed}，实测 {expected} / {done}")


class RoleDatabase(UpgradeDatabase):
    def __init__(self, port, password, run_id):
        super().__init__({"sqlPort": port, "sqlBackupDirectory": "/var/opt/mssql/backup",
                          "localBackupDirectory": Path(".")}, "sa", password, run_id)
        self.names = {label: f"r5_role_{run_id}_{label}" for label in RELEASES}
        self.sql_port = port

    def connection_string(self, database):
        require(database in self.names.values(), f"连接超出本轮数据库：{database}")
        return (f"Server=tcp:127.0.0.1,{self.sql_port};Initial Catalog={database};User ID=sa;"
                f"Password={self.password};Encrypt=True;TrustServerCertificate=True;"
                "Connect Timeout=15;Application Name=R5RoleUpdate")

    def create(self, name):
        require(name in self.names.values(), f"创建超出本轮数据库：{name}")
        self.require_new_database(name)
        self.query("master", f"CREATE DATABASE [{name}]")
        identity = self.identify(name)
        table_count, = self.query(name, "SELECT COUNT(*) AS count FROM sys.tables WHERE is_ms_shipped = 0")
        require(table_count == {"count": 0}, f"数据库并非空库：{name} / {table_count}")
        return identity, table_count

    def identify(self, database):
        observed, = self.query(database, IDENTITY)
        require(observed["database"] == database and observed["serverName"] == self.identity["serverName"]
                and observed["databaseId"] > 0 and observed["databaseGuid"], f"数据库身份无效：{observed}")
        return observed

    def snapshot(self, database, tenant_id, user_id, role_ids):
        row, = self.query(database, IDENTITY.replace(
            "FROM sys.database_recovery_status", """,
            (SELECT Id AS id, TenantId AS tenantId, UserName AS userName, Name AS name, Surname AS surname,
                    EmailAddress AS emailAddress, IsActive AS isActive, IsDeleted AS isDeleted,
                    CreatorUserId AS creatorUserId, CONVERT(nvarchar(33), CreationTime, 126) AS creationTime
             FROM dbo.AbpUsers WHERE TenantId = %s AND Id = %s FOR JSON PATH, INCLUDE_NULL_VALUES) AS users,
            (SELECT ur.Id AS associationId, ur.UserId AS userId, ur.TenantId AS tenantId, ur.RoleId AS roleId,
                    r.Id AS joinedRoleId, r.Name AS roleName, r.NormalizedName AS normalizedName,
                    r.TenantId AS roleTenantId, r.IsDeleted AS roleIsDeleted
             FROM dbo.AbpUserRoles AS ur LEFT JOIN dbo.AbpRoles AS r ON ur.RoleId = r.Id
             WHERE ur.UserId = %s ORDER BY ur.Id FOR JSON PATH, INCLUDE_NULL_VALUES) AS relations,
            (SELECT Id AS id, Name AS name, NormalizedName AS normalizedName, TenantId AS tenantId, IsDeleted AS isDeleted
             FROM dbo.AbpRoles WHERE Id IN (%s, %s) ORDER BY Id FOR JSON PATH, INCLUDE_NULL_VALUES) AS catalog
FROM sys.database_recovery_status"""), (tenant_id, user_id, user_id, *role_ids))
        return {"identity": {key: row[key] for key in DB_KEYS},
                **{key: json.loads(row[key] or "[]") for key in ("users", "relations", "catalog")}}


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


HTTP = request.build_opener(request.ProxyHandler({}), NoRedirect())


def check(observation, action, *args):
    try:
        action(*args)
    except SqlIdentityMismatch as failure:
        observation.update(status="input_incomparable", reason=str(failure))
    except CHECK_ERRORS as failure:
        observation.update(status="failed", reason=str(failure))
    else:
        observation["status"] = "passed"
    return observation["status"] == "passed"


def run_phases(side, record):
    for step, values, requested, role in STEPS:
        current = record["phases"][step]
        expected = side.expected(fields(*values), role)
        current.clear()
        current.update(status="failed", expected=expected)
        payload = expected["fields"] | {"id": expected["id"], "roleNames": requested, "creationTime": KEEP_TIME}
        response = side.put(step, payload)
        current["put"] = receipt = {"http": response}
        put_ok = check(receipt, lambda: check_dto(result(response), expected))
        # 在收到传输错误时仍可核对已记录的业务连接，后续操作只有读。
        envelope = response.get("body")
        success = isinstance(envelope, dict) and envelope.get("success") is True
        has_dto = success and isinstance(envelope.get("result"), dict)
        usable = response.get("error") is None and (has_dto or
                  isinstance(envelope, dict) and envelope.get("success") is False and isinstance(envelope.get("error"), dict))
        current["putConnection"] = binding = {}
        put_target = check(binding, side.bind, response, binding, has_dto)
        if not usable:
            receipt["availability"] = "missing"

        diagnostic = not usable
        current["get"] = get_read = {"diagnostic": diagnostic}
        current["sql"] = sql_read = {"diagnostic": diagnostic}
        if diagnostic and not put_target:
            for read in (get_read, sql_read):
                read.update(status="not_run", reason="PUT 已发出，无法核实该请求业务命令的目标库")
            return "input_incomparable"

        current["getConnection"] = get_binding = {}
        get_response = side.get(step)
        get_read["http"] = get_response
        get_ok = check(get_read, lambda: check_dto(result(get_response), expected))
        get_envelope = get_response.get("body")
        get_has_dto = isinstance(get_envelope, dict) and isinstance(get_envelope.get("result"), dict)
        get_target = check(get_binding, side.bind, get_response, get_binding, get_has_dto)

        def verify_sql():
            sql_read["observed"] = side.sql()
            check_sql(sql_read["observed"], expected, side.identity)

        sql_ok = check(sql_read, verify_sql)
        if not put_target or not get_target or sql_read["status"] == "input_incomparable":
            return "input_incomparable"
        if not all((put_ok, get_ok, sql_ok)):
            return "failed"
        current["status"] = "passed"
    return "passed"


def side_report():
    return {"status": "not_run", "phases": {
        name: {"status": "not_run", "reason": "依赖的输入或前一步未通过"} for name, *_ in STEPS}}


def finish(report):
    sides = [item["status"] for item in report["sides"].values()]
    if report.get("inputError") or "input_incomparable" in sides:
        status = "input_incomparable"
    elif sides == ["passed", "passed"]:
        status = "passed"
    elif sides.count("failed") == 2:
        status = "both_failed"
    else:
        status = "one_side_failed"
    passed = status == "passed" and "cleanupError" not in report
    report.update(status="cleanup_failed" if status == "passed" and not passed else status, exitCode=0 if passed else 1)
    return report["exitCode"]


class LiveSide:
    def __init__(self, run, label, launches, record):
        self.run, self.label, self.launches, self.record = run, label, launches, record
        self.db = run.database
        self.name = self.db.names[label]
        self.root = run.root / label
        self.root.mkdir()
        self.events = self.root / "user-requests.jsonl"
        self.snapshot = self.root / "Web.Host-initial-assemblies.json"
        self.initial_id = secrets.token_hex(16)
        self.headers = {}
        self.record.update(database=self.name, processes={}, seed={})

    def http(self, path, *, body=None, method=None, marker=None, auth=False):
        path, _, query = path.partition("?")
        method = method or ("POST" if body is not None else "GET")
        trace = {"method": method, "path": path, "query": query}
        if marker:
            trace["id"] = marker
        if body is not None:
            trace["json"] = {key: "[已脱敏]" if key == "password" else value for key, value in body.items()}
        row = {"request": trace, "status": None, "body": None}
        req = request.Request(self.base + path + ("?" + query if query else ""),
                              json.dumps(body).encode() if body is not None else None,
                              {"Content-Type": "application/json", **self.headers}, method=method)
        data = bytearray()
        parsed = None
        try:
            try:
                response = HTTP.open(req, timeout=18)
            except error.HTTPError as failure:
                response = failure
            wire = response.fp if isinstance(response, error.HTTPError) else response
            with response:
                row["status"] = response.status
                length = wire.length
                while chunk := response.read1(65536):
                    data.extend(chunk)
                # read1() 遇到提前 EOF 也会返回空字节。HTTP 库为分块及合法的读到连接关闭保留 length=None。
                if length is not None and len(data) < length:
                    raise http.client.IncompleteRead(b"", length - len(data))
            parsed = json.loads(data)
        except http.client.IncompleteRead as failure:
            data.extend(failure.partial)
            missing = f"，还缺 {failure.expected} 字节" if failure.expected is not None else ""
            row["error"] = f"IncompleteRead: HTTP 响应提前结束，已接收 {len(data)} 字节{missing}"
        except (OSError, ValueError, http.client.HTTPException) as failure:
            row["error"] = self.run.redact(f"{type(failure).__name__}: {failure}")
        if auth and isinstance(parsed, dict) and isinstance(parsed.get("result"), dict):
            tokens = parsed["result"]
            self.run.secrets.extend(value for key in ("accessToken", "encryptedAccessToken")
                                    if isinstance(value := tokens.get(key), str) and value)
        raw = self.run.redact(data.decode("utf-8", errors="replace"))
        row["rawBody"] = raw
        if parsed is not None:
            row["body"] = json.loads(raw)
        return row, parsed if auth else None

    def put(self, step, payload):
        marker = secrets.token_hex(16)
        query = urlencode({"r5RoleRequest": marker, "r5RoleUser": self.user_id})
        return self.http(APP + "User/Update?" + query, method="PUT", body=payload, marker=marker)[0]

    def get(self, step):
        marker = self.initial_id if step == "initial" else secrets.token_hex(16)
        query = urlencode({"Id": self.user_id, "r5RoleRequest": marker})
        return self.http(APP + "User/Get?" + query, marker=marker)[0]

    def sql(self):
        try:
            return self.db.snapshot(self.name, self.tenant_id, self.user_id,
                                    [role["id"] for role in self.roles.values()])
        except self.db.client.Error as failure:
            raise VerificationError(self.run.redact(str(failure))) from failure

    def bind(self, http, evidence, complete):
        marker = http["request"]["id"]
        deadline = time.monotonic() + (3 if complete else 1)
        while True:
            rows = [row for row in read_events(self.events) if row["request"]["requestId"] == marker]
            if any(row["kind"] == "response" for row in rows) or time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        evidence["events"] = rows
        try:
            evidence["currentIdentity"] = self.db.identify(self.name)
        except self.db.client.Error as failure:
            raise VerificationError(self.run.redact(str(failure))) from failure
        require(evidence["currentIdentity"] == self.identity,
                f"请求 {marker} 的预检库身份已改变：{evidence['currentIdentity']}")
        check_connection(http, rows, self.pid, self.user_id, self.identity, complete=complete)

    def expected(self, values, role):
        return {"id": self.user_id, "tenantId": self.tenant_id, "creatorUserId": self.admin_id,
                "creationTime": self.original_time, "fields": values, "roles": [self.roles[role]] if role else [],
                "catalog": sorted(self.roles.values(), key=lambda item: item["id"])}

    @contextmanager
    def process(self, entry, **overrides):
        launch = self.launches[entry].copy()
        self.record["processes"][entry] = launch
        application_log = Path("/dev/null")
        env = process_env(self.root) | overrides | {
            "ConnectionStrings__Default": self.db.connection_string(self.name),
            "CONSUMER_ROLLBACK_APP_LOG": str(application_log),
            "DOTNET_STARTUP_HOOKS": str(self.run.observer),
            "DOTNET_HOST_TRACE": "1", "DOTNET_HOST_TRACE_VERBOSITY": "4",
            "DOTNET_ROLL_FORWARD": "Disable",
            "ASPNETCORE_ENVIRONMENT": "Development", "DOTNET_ENVIRONMENT": "Development",
        }
        stdout = self.root / f"{entry}-console.log"
        launch.update(console=stdout.name, applicationLog=str(application_log), exitCode=None)
        with TemporaryDirectory(prefix="home-", dir=self.root) as home, stdout.open("w", encoding="utf-8") as sink, subprocess.Popen(
            launch["argv"], cwd=launch["cwd"], env=env | {"HOME": home, "APPDATA": home}, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, errors="replace", start_new_session=True,
        ) as child:
            launch["pid"] = child.pid

            def copy_console():
                with child.stdout:
                    for line in child.stdout:
                        sink.write(self.run.redact(line))
                        sink.flush()

            thread = Thread(target=copy_console)
            thread.start()
            try:
                yield child, launch, stdout
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)
                thread.join()
                launch["exitCode"] = child.returncode

    def migrate(self):
        before, empty = self.db.create(self.name)
        self.identity = self.record["preflight"] = before
        self.record["emptyTables"] = empty
        require(all(before[key] != other[key] for other in self.run.database_ids
                    for key in ("database", "databaseId", "databaseGuid")), f"两侧使用同一数据库：{before}")
        self.run.database_ids.append(before)
        events_path = self.root / "Migrator-target.jsonl"
        loaded_path = self.root / "Migrator-assemblies.json"
        with self.process("Migrator", R3_TEMPLATE_OBSERVER_MODE="migrator",
                          R3_TEMPLATE_OBSERVER_EVIDENCE=str(events_path),
                          R3_TEMPLATE_OBSERVER_ASSEMBLIES=str(loaded_path)) as (child, launch, log):
            child.wait(timeout=180)
        require(launch["exitCode"] == 0, f"Migrator 退出 {launch['exitCode']}，详见 {log}")
        launch["sharedRuntime"] = shared_runtime_trace(log, "Migrator")
        rows = read_events(events_path)
        check_migration_target(rows, launch["pid"], before["serverName"], self.name)
        self.record["migrationTarget"] = artifact(events_path, self.root) | {"events": len(rows)}
        self.record["creationTimeColumn"] = self.db.query(self.name, """
SELECT TYPE_NAME(user_type_id) AS [type], scale
FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.AbpUsers') AND name = N'CreationTime'
""")
        require(self.record["creationTimeColumn"] == [{"type": "datetime2", "scale": 7}],
                f"固定模板 CreationTime 精度不符：{self.record['creationTimeColumn']}")
        self.record["migrationIdentity"] = self.db.identify(self.name)
        require(self.record["migrationIdentity"] == before, "迁移前后数据库身份不一致")
        self.record["migratorAssets"] = self.assets("Migrator", launch, loaded_path)
        self.seed = self.record["seed"]["database"] = self.db.seed(self.name, self.run.migration_ids)
        require(all(row["productVersion"] == RUNTIME for row in self.seed["migrations"]),
                "迁移历史的 EF Core ProductVersion 不符")
        self.tenant_id, self.admin_id = self.seed["tenant"]["tenantId"], self.seed["account"]["userId"]

    def assets(self, entry, launch, loaded_path):
        prepared = self.run.prepared
        output = Path(launch["cwd"])
        expected = read_json(prepared / launch["outputVerification"]["path"])
        signed = read_json(prepared / launch["signedPackages"]["path"])
        observed = read_json(loaded_path)
        verification = {"observation": artifact(loaded_path, self.root), "packages": {}}
        require(expected["sqlServerProvider"]["package"] == f"{PROVIDER}/{RUNTIME}", "封存 Provider 版本不符")
        if entry == "Web.Host":
            framework = {Path(path).stem for path, item in expected["packageCopies"].items()
                         if item["package"].startswith("Du.Abp")}
            require(len(framework) == 11, f"固定 Web.Host 框架程序集不符：{sorted(framework)}")
            verify_entry_assemblies(observed, launch, output, expected, verification, RUNTIME, entry, framework)
        else:
            verify_migrator_assemblies(observed, launch, output, expected, verification, RUNTIME)
        for package, name in MAP_PACKAGES.items():
            proof = signed[package]
            dll = output / (name + ".dll")
            archive = Path(proof["nupkg"])
            require(sha256(archive) == proof["sha256"], f"{entry} {package} 签后归档摘要不符：{archive}")
            with ZipFile(archive) as bundle:
                asset_sha = hashlib.sha256(bundle.read(proof["member"])).hexdigest()
            require(Path(proof["output"]) == dll and sha256(dll) == proof["dllSha256"] == asset_sha,
                    f"{entry} {package} 包内所选资产和输出不符")
            actual = unique_loaded(observed["assemblies"], name, launch["pid"],
                                   optional=entry == "Migrator" or name == "AutoMapper.Collection", process_name=entry)
            if actual:
                require(Path(actual["path"]) == dll and actual["sha256"] == asset_sha,
                        f"{entry} {package} 实际加载资产不符：{actual}")
            verification["packages"][package] = proof | {"state": "loaded" if actual else "output_only", "loaded": actual}
        return verification

    def authenticate(self, evidence):
        self.headers = {"Abp-TenantId": str(self.tenant_id)}
        # 固定模板在独占环回新实例上创建的临时种子管理员。
        password = "123qwe"
        self.run.secrets.append(password)
        evidence["authenticate"], auth = self.http(AUTH, auth=True,
                                                 body={"userNameOrEmailAddress": "admin", "password": password})
        check_fields(result(evidence["authenticate"]), {"userId": self.admin_id})
        token = auth["result"]["accessToken"]
        require(isinstance(token, str) and token, "登录缺少访问令牌")
        self.headers["Authorization"] = "Bearer " + token
        evidence["session"] = self.http(SESSION)[0]
        session = result(evidence["session"])
        check_session({"tenantId": session["tenant"]["id"], "userId": session["user"]["id"],
                       "userName": session["user"]["userName"]}, self.seed)
        check_fields(session["tenant"], {"tenancyName": "Default"})
        evidence["permissions"] = self.http(USER_CONFIG)[0]
        body = evidence["permissions"]["body"]
        granted = (body.get("result") or body)["auth"]["grantedPermissions"]
        require(evidence["permissions"]["status"] == 200
                and all(granted.get(key) in (True, "true") for key in ("Pages.Users", "Pages.Roles")),
                "租户会话缺少用户或角色权限")
        evidence["loginRows"] = self.db.successful_logins(self.name, self.seed)
        require(len(evidence["loginRows"]) == 1, "新库须有唯一的本轮管理员成功登录记录")
        check_fields(evidence["loginRows"][0], {"tenancyName": "Default", "loginName": "admin"})

    def seed_business(self):
        evidence = self.record["seed"]
        self.authenticate(evidence)
        self.roles = {}
        evidence["roles"] = roles = {}
        for label, name in ROLE_NAMES.items():
            role = roles[label] = {}
            role["http"] = self.http(APP + "Role/Create", body={
                "name": name, "displayName": ROLE_DISPLAYS[label], "grantedPermissions": []})[0]
            receipt = result(role["http"])
            check_fields(receipt, {"name": name, "displayName": ROLE_DISPLAYS[label], "normalizedName": name.upper()})
            role_id = receipt["id"]
            require(type(role_id) is int and role_id > 0, f"角色 {label} 的 ID 无效：{role_id}")
            role["sql"] = self.db.query(self.name, """
SELECT Id AS id, Name AS name, DisplayName AS displayName, NormalizedName AS normalizedName,
       TenantId AS tenantId, IsStatic AS isStatic, IsDefault AS isDefault, IsDeleted AS isDeleted
FROM dbo.AbpRoles WHERE Id = %s""", (role_id,))
            role["grants"] = self.db.query(self.name, """
SELECT TenantId AS tenantId, RoleId AS roleId, Name AS name
FROM dbo.AbpPermissions WHERE RoleId = %s AND IsGranted = 1""", (role_id,))
            require(len(role["sql"]) == 1 and not role["grants"], f"角色 {label} 非唯一或存在授予权限")
            row, = role["sql"]
            check_fields(row, {"id": role_id, "name": name, "normalizedName": name.upper(),
                               "displayName": ROLE_DISPLAYS[label], "tenantId": self.tenant_id,
                               "isStatic": False, "isDefault": False, "isDeleted": False})
            self.roles[label] = {key: row[key] for key in ("id", "name", "normalizedName")}
        require(self.roles["A"]["id"] != self.roles["B"]["id"], "A、B 角色 ID 重复")
        password = "DuA!" + secrets.token_hex(12)
        self.run.secrets.append(password)
        evidence["create"] = self.http(APP + "User/Create", body=SEED_FIELDS | {
            "roleNames": [self.roles["A"]["name"]], "password": password})[0]
        receipt = result(evidence["create"])
        self.user_id = receipt["id"]
        require(type(self.user_id) is int and self.user_id > 0 and self.user_id != self.admin_id,
                "普通用户创建 ID 与管理员冲突或无效")
        evidence["get"] = self.get("initial")
        evidence["sql"] = self.sql()
        require(len(evidence["sql"]["users"]) == 1, "初态未找到唯一的普通用户")
        self.original_time = evidence["sql"]["users"][0]["creationTime"]
        require(time_value(self.original_time) != time_value(KEEP_TIME), "更新请求的创建时间与初态相同")
        expected = evidence["expected"] = self.expected(SEED_FIELDS, "A")
        evidence["connection"] = connection = {}
        self.bind(evidence["get"], connection, True)
        check_sql(evidence["sql"], expected, self.identity)
        check_dto(receipt, expected, allow_local_offset=True)
        check_dto(result(evidence["get"]), expected)
        evidence["status"] = "passed"

    def execute(self, port):
        self.migrate()
        require(available(port), f"Host 环回端口已被使用：{port}")
        self.base = f"http://127.0.0.1:{port}"
        loaded = self.root / "Web.Host-assemblies.json"
        with self.process("Web.Host", R3_TEMPLATE_OBSERVER_MODE="host", R3_TEMPLATE_OBSERVER_EVIDENCE=str(loaded),
                          R5_ROLE_REQUEST_EVIDENCE=str(self.events), R5_ROLE_INITIAL_REQUEST=self.initial_id,
                          R5_ROLE_INITIAL_ASSEMBLIES=str(self.snapshot), Kestrel__Endpoints__Http__Url=self.base,
                          App__ServerRootAddress=self.base + "/", App__ClientRootAddress=self.base + "/",
                          App__CorsOrigins=self.base, Logging__LogLevel__Default="Warning",
                          Logging__LogLevel__Microsoft__Hosting__Lifetime="Information") as (child, launch, log):
            self.pid = child.pid
            deadline = time.monotonic() + 75
            while time.monotonic() < deadline:
                require(child.poll() is None, f"Host 提前退出 {child.returncode}，详见 {log}")
                console = log.read_text()
                if f"Now listening on: {self.base}" in console and "Hosting environment: Development" in console:
                    break
                time.sleep(0.2)
            else:
                raise VerificationError(f"Host 未在 {self.base} 启动，详见 {log}")
            launch.update(address=self.base, environment="Development", sharedRuntime=shared_runtime_trace(log, "Host"))
            require(all(item["version"] == RUNTIME for item in launch["sharedRuntime"].values()), "Host 共享运行时不符")
            require(self.db.identify(self.name) == self.identity, "Host 建种前的数据库身份不一致")
            self.seed_business()
            self.record["hostInitialAssets"] = self.assets("Web.Host", launch, self.snapshot)
            outcome = run_phases(self, self.record)
            require(child.poll() is None, f"Web.Host 在场景完成前退出 {child.returncode}")
        require(launch["exitCode"] == 0, f"Web.Host 未正常停止，退出 {launch['exitCode']}，详见 {log}")
        self.record["hostAssets"] = self.assets("Web.Host", launch, loaded)
        return outcome


def process_env(home):
    return {key: value for key, value in os.environ.items() if key in ("PATH", "TMPDIR", "LANG", "LC_ALL")} | {
        "HOME": str(home), "APPDATA": str(home), "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1"}


class LiveRun:
    def __init__(self, args):
        self.args = args
        self.root = args.output.resolve()
        self.prepared = args.prepared.resolve()
        self.secrets = []
        self.database_ids = []
        self.run_id = secrets.token_hex(8)
        self.report = {"schemaVersion": 1, "source": "live", "runId": self.run_id,
                       "prepared": str(self.prepared), "preparedReportSha256": args.report_sha256,
                       "status": "running", "sides": {label: side_report() for label in RELEASES}}
        self.root.mkdir(mode=0o700)
        self.save()

    def redact(self, message):
        for value in self.secrets:
            message = message.replace(value, "[已脱敏]")
        message = re.sub(r'(?i)("(?:accessToken|encryptedAccessToken|password)"\s*:\s*")[^"\r\n]*',
                         r"\1[已脱敏]", message)
        return re.sub(r"(?im)^(.*(?:Host database|Connection string)\s*:\s*).*$", r"\1[已脱敏]", message)

    def save(self):
        temporary = self.root / "report.tmp"
        write_json(temporary, self.report)
        temporary.replace(self.root / "report.json")

    def command(self, argv, *, cwd=None, env=None, log=None, timeout=180, must_pass=True):
        result = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, errors="replace", timeout=timeout)
        stdout, stderr = self.redact(result.stdout).strip(), self.redact(result.stderr).strip()
        if log:
            (self.root / log).write_text(stdout + "\n" + stderr + "\n")
        evidence = {"argv": [str(item) for item in argv], "cwd": str(cwd) if cwd else None,
                    "exitCode": result.returncode}
        if log:
            evidence["log"] = log
        else:
            evidence.update(stdout=stdout, stderr=stderr)
        self.report.setdefault("commands", []).append(evidence)
        if must_pass:
            require(result.returncode == 0, f"{argv[0]} 退出 {result.returncode}，{log or stderr}")
        return result.returncode, stdout

    def verify_inputs(self):
        # 先验证共同附件及报告。若单侧输出失配，分别核对以确定另一侧能否独立执行。
        try:
            launches = verify_prepared(self.prepared, self.args.report_sha256)
        except CHECK_ERRORS as failure:
            launches = {}
            for label in RELEASES:
                try:
                    launches.update(verify_prepared(self.prepared, self.args.report_sha256, only_release=label))
                except CHECK_ERRORS as side_failure:
                    self.report["sides"][label].update(status="input_incomparable",
                                                        reason=self.redact(str(side_failure)))
            require(launches, str(failure))
        sealed = read_json(self.prepared / "report.json")
        require(platform.system() == "Darwin" and platform.machine() == "arm64", "本轮要求 macOS ARM64")
        toolchain = sealed["toolchain"]
        require(toolchain["sdk"] == SDK and toolchain["runtimeConfigVersion"] == RUNTIME
                and toolchain["targetFramework"] == "net10.0", "准备工具链不符")
        require(sealed["template"]["commit"] == "2e9536872673a7ff1986a19e798c51684d16afe5",
                "准备模板提交不符")
        self.migration_ids = sealed["template"]["migrationIds"]
        self.report.update(platform=platform.platform(), toolchain=toolchain, template=sealed["template"],
                           preparations=launches)
        self.report["profileSources"] = [artifact(ROOT / "eng" / name, ROOT) for name in (
            "r5_template_role_update.py", "r5_template_role_prepare.py", "r3_template_net9_runtime.py",
            "r3-template-observer/Observer.csproj", "r3-template-observer/StartupHook.cs",
            "r3-template-observer/RoleRequestObserver.cs",
        )]
        self.dotnet = toolchain["dotnet"]
        return launches

    def build_observer(self):
        observer = self.root / "observer"
        shutil.copytree(ROOT / "eng/r3-template-observer", observer, ignore=shutil.ignore_patterns("bin", "obj"))
        write_json(observer / "global.json", {"sdk": {"version": SDK, "rollForward": "disable"}})
        project = observer / "Observer.csproj"
        project.write_text(project.read_text().replace("<TargetFramework>net9.0</TargetFramework>",
                                                       "<TargetFramework>net10.0</TargetFramework>"))
        env = process_env(self.root)
        _, actual = self.command([self.dotnet, "--version"], cwd=observer, env=env)
        require(actual.splitlines()[-1] == SDK, f"实际观测构建 SDK 不符：{actual}")
        _, output = self.command([self.dotnet, "--info"], cwd=observer, env=env, log="dotnet-info.log")
        require("Architecture: arm64" in output or "Architecture:       arm64" in output
                or re.search(r"Architecture:\s+arm64", output), "实际 .NET 宿主架构不符")
        self.command([self.dotnet, "build", "Observer.csproj", "-c", "Release", "--disable-build-servers",
                      "-p:NuGetAudit=false", "-p:UseSharedCompilation=false"],
                     cwd=observer, env=env, log="observer-build.log")
        self.observer = observer / "bin/Release/net10.0/Observer.dll"
        self.report["observer"] = artifact(self.observer, self.root)

    @contextmanager
    def sql_server(self):
        name = "r5-role-" + self.run_id
        resource = self.report["sqlResource"] = {"name": name, "image": SQL_IMAGE}
        password = "DuS!" + secrets.token_hex(20)
        self.secrets.append(password)
        launched = False
        try:
            _, endpoint = self.command(["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"])
            require(endpoint.startswith("unix://") and not os.environ.get("DOCKER_HOST"),
                    "本轮只允许使用本机 Unix socket 的 Docker")
            self.command(["docker", "image", "inspect", "--format", "{{.Id}} {{.Os}}/{{.Architecture}}", SQL_IMAGE])
            _, container_id = self.command(["docker", "run", "--detach", "--pull=never", "--platform", "linux/amd64",
                                            "--name", name, "--hostname", name, "--publish", "127.0.0.1::1433",
                                            "--env", "ACCEPT_EULA=Y", "--env", "MSSQL_PID=Developer",
                                            "--env", "MSSQL_SA_PASSWORD", SQL_IMAGE],
                                           env=os.environ | {"MSSQL_SA_PASSWORD": password}, timeout=60)
            launched = True
            resource["containerId"] = container_id
            _, mapped = self.command(["docker", "port", container_id, "1433/tcp"])
            mapping = re.fullmatch(r"127\.0\.0\.1:(\d+)", mapped)
            require(mapping, f"SQL Server 容器端口非独占环回：{mapped}")
            resource["endpoint"] = mapped
            self.database = RoleDatabase(int(mapping[1]), password, self.run_id)
            client = self.database.client
            self.report["pymssql"] = client.__version__
            deadline = time.monotonic() + 125
            while time.monotonic() < deadline:
                try:
                    identity, = self.database.query("master", """
SELECT CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')) AS serverName,
       CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) AS productVersion,
       CONVERT(nvarchar(128), SERVERPROPERTY('Edition')) AS edition, DB_NAME() AS [database]
""")
                except client.Error as failure:
                    resource["lastStartupError"] = self.redact(str(failure))
                    time.sleep(1)
                else:
                    break
            else:
                raise VerificationError(f"专用 SQL Server 正常启动前超时：{resource.get('lastStartupError')}")
            resource["identity"] = self.database.identity = identity
            require(identity["serverName"] == name and identity["database"] == "master"
                    and identity["productVersion"] == SQL_VERSION and "Developer" in identity["edition"],
                    f"专用 SQL Server 发行或身份不符：{identity}")
            yield
        finally:
            if launched:
                try:
                    self.command(["docker", "logs", container_id], log="sql-server.log", timeout=15, must_pass=False)
                finally:
                    try:
                        self.command(["docker", "rm", "--force", "--volumes", container_id], timeout=45)
                        listing, actual = self.command(["docker", "ps", "-a", "--quiet", "--no-trunc",
                                                        "--filter", f"id={container_id}"])
                        require(listing == 0 and not actual, "容器仍存在")
                        resource["removed"] = True
                    except CHECK_ERRORS as failure:
                        self.report["cleanupError"] = self.redact(str(failure))
            if hasattr(self, "database"):
                write_json(self.root / "sql-commands.json", self.database.commands)

    def execute(self):
        try:
            launches = self.verify_inputs()
            self.build_observer()
            with self.sql_server():
                for label, port in zip(RELEASES, (self.args.r4_port, self.args.r5_port)):
                    item = self.report["sides"][label]
                    if label not in launches:
                        continue
                    try:
                        item["status"] = LiveSide(self, label, launches[label], item).execute(port)
                    except (self.database.client.Error, *CHECK_ERRORS) as failure:
                        item.update(status="input_incomparable", reason=self.redact(str(failure)))
                    print(f"{label} {item['status']}" + (f" · {item['reason']}" if item.get("reason") else ""), flush=True)
                    self.save()
            rechecked = {}
            for label in launches:
                rechecked.update(verify_prepared(self.prepared, self.args.report_sha256, only_release=label))
            require(rechecked == launches, "执行后的封存入口已改变")
            self.report["sealedOutputsUnchanged"] = list(rechecked)
        except (ImportError, *CHECK_ERRORS) as failure:
            self.report["inputError"] = self.redact(str(failure))
        finally:
            finish(self.report)
            self.save()
        print(f"{self.report['status']} · {self.root / 'report.json'}", flush=True)
        return self.report["exitCode"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--r4-port", type=int, required=True)
    parser.add_argument("--r5-port", type=int, required=True)
    args = parser.parse_args()
    if args.r4_port == args.r5_port or not all(1024 <= p <= 65535 for p in (args.r4_port, args.r5_port)):
        parser.error("需要两个不同的非系统环回 Host 端口")
    if args.output.exists() or args.output.resolve().is_relative_to(args.prepared.resolve()):
        parser.error("证据目录必须尚不存在且位于封存目录之外")
    return LiveRun(args).execute()


if __name__ == "__main__":
    raise SystemExit(main())
