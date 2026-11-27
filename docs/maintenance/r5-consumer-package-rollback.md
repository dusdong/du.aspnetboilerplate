# 用公开包演练 R4 → R5 → R4 同库回退

在一座专用空库上，用 R4 创建用户 A，用 R5 查回 A 并创建、查回 B，随后用保存的 R4 产物重新登录一次，分别查回 A、B。示例针对经典 ABP 固定模板的后端 API，并采用 `net10.0`、macOS ARM64、SDK `10.0.404`、.NET 与 ASP.NET Core `10.0.15`、SQL Server Developer `16.0.4236.2`。各版的映射引擎、Collection、适配器版本依次为 R4 的 `14.0.0 / 11.0.0 / 10.5.1` 和 R5 的 `14.0.1 / 11.0.1 / 10.5.2`。R5 延用十个 R4 的 `10.5.1` 包。[R4 安装](r4-public-install.md) · [R5 安装](r5-public-install.md) · [固定模板](https://github.com/dusdong/module-zero-core-template/tree/2e9536872673a7ff1986a19e798c51684d16afe5)

同库切回保留两版已经提交的写入，也恢复旧版集合映射行为。恢复备份只保留所选恢复点之前的写入，若选在创建 B 之前，恢复出的库不会含 B。存量应用按自己的迁移、租户独立连接和业务数据验证两条路径。历史资料分别记录了固定 Angular 客户端与两次备份恢复的观测。[Angular 历史实测](r5-automapper-template.md#公开-r4r5-同库回退实测) · [备份操作与写入边界](r5-r4-net10-migration.md#创建恢复点并用目标版回读)

## 准备工具与隔离库

准备 Bash、curl、tar、Python 3.10 或更新版、ARM64 .NET SDK `10.0.404` 及两套 `10.0.15` 共享框架。另准备专用 SQL Server Developer `16.0.4236.2`，仅通过环回端口访问。启用 SQL 认证，使用能创建专用测试库、运行其迁移并查询其目录与业务表的测试账号。脚本给新库生成随机名称，验证创建前后的实例名与 SQL 版本，并留存新库名称。使用管理员连接从该专用实例查询 `SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(128));`，将读数填入 `--server-name`。脚本使用加密 SQL 连接并信任隔离实例证书。示例的 Host 和管理员都只用于本机测试。[.NET 下载](https://dotnet.microsoft.com/en-us/download/dotnet/10.0) · [SQL 连接预检](r5-r4-net10-migration.md#在迁移或登录前核对连接)

将本页保存为 Markdown 原文，在 Bash 中把 `guide` 指向该文件。以下命令生成虚拟环境和脚本，并显示所用指南与脚本的摘要。也可将下一节的 Python 代码复制到 `exercise.py`。

```bash
set -euo pipefail
guide=/absolute/path/to/r5-consumer-package-rollback.md
work="$(mktemp -d "${TMPDIR:-/tmp}/du-package-rollback.XXXXXXXX")"
printf '工作目录 %s\n' "$work"
shasum -a 256 "$guide"
awk '/^```python$/{copy=1;next} copy && /^```$/{exit} copy' "$guide" > "$work/exercise.py"
test -s "$work/exercise.py"
shasum -a 256 "$work/exercise.py"
python3 -m venv "$work/venv"
"$work/venv/bin/python" -m pip --isolated install --index-url https://pypi.org/simple --disable-pip-version-check pymssql==2.4.6
```

## 演练脚本

```python
import argparse
import contextlib
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib import error, parse, request
import zipfile

import pymssql

TEMPLATE = "2e9536872673a7ff1986a19e798c51684d16afe5"
RELEASE_ASSETS = "https://api.github.com/repos/dusdong/du.aspnetboilerplate/releases/assets"
ATTACHMENTS = {
    "R4": (794231663, "c3a905b6a6373a59236214f94fce953abb530fc61c80a7fe94ff99f028f534b0"),
    "R5": (798453420, "be08d2d354d71dcb09802f8161496f213ebdd257826ed5adbf6af77fe9000dd5"),
}
NUGET = "https://api.nuget.org/v3/index.json"
PREFIX = "AbpCompanyName.AbpProjectName"
SDK = "10.0.404"
RUNTIME = "10.0.15"
TFM = "net10.0"
ENTRIES = {"Migrator": 10, "Web.Host": 13}
MAPPING = {
    "Du.Abp.AutoMapper": "Abp.AutoMapper.dll",
    "Du.AutoMapper": "AutoMapper.dll",
    "Du.AutoMapper.Collection": "AutoMapper.Collection.dll",
}
HTTP = request.build_opener(request.ProxyHandler({}))
BUILD_ENV = {key: os.environ[key] for key in (
    "PATH", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy",
    "NO_PROXY", "no_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR",
) if key in os.environ}

IDENTITY = """
SELECT CAST(SERVERPROPERTY('ServerName') AS nvarchar(128)) AS instance,
       CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128)) AS version,
       CAST(SERVERPROPERTY('Edition') AS nvarchar(128)) AS edition,
       DB_NAME() AS [name], DB_ID() AS id,
       CONVERT(varchar(36), database_guid) AS [guid]
FROM sys.database_recovery_status WHERE database_id = DB_ID()
"""
MIGRATIONS = "SELECT MigrationId, ProductVersion FROM dbo.__EFMigrationsHistory ORDER BY MigrationId"
USER_ROW = """
SELECT Id AS id, TenantId AS tenantId, UserName AS userName, Name AS name,
       Surname AS surname, EmailAddress AS emailAddress, IsActive AS isActive
FROM dbo.AbpUsers WHERE TenantId = %s AND Id = %s AND IsDeleted = 0
"""

class ManifestMismatch(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        return digest.hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")


def command(args, cwd, log, env):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True,
                            errors="replace", timeout=900)
    log.write_text(json.dumps({"argv": list(map(str, args)), "cwd": str(cwd),
                               "exitCode": result.returncode}, ensure_ascii=False) + "\n"
                   + result.stdout + result.stderr)
    require(result.returncode == 0, f"{args[0]} 退出 {result.returncode}，见 {log}")
    return result.stdout


def download(url, path, env, headers=()):
    command(["curl", "-q", "--fail", "--silent", "--show-error", "--location",
             "--retry", "2", "--connect-timeout", "10", "--max-time", "45", *headers,
             "--output", str(path), url], path.parent, path.with_suffix(path.suffix + ".log"), env)


def project(source, name):
    return source / "src" / f"{PREFIX}.{name}" / f"{PREFIX}.{name}.csproj"


def change_project(path, old, new):
    text = path.read_text(encoding="utf-8")
    require(text.count(old) == 1, f"{path} 应恰有一处 {old}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def prepare(root, env):
    archive = root / "template.tar.gz"
    download(f"https://codeload.github.com/dusdong/module-zero-core-template/tar.gz/{TEMPLATE}", archive, env)
    command(["tar", "-xzf", str(archive)], root, root / "template-extract.log", env)
    (root / f"module-zero-core-template-{TEMPLATE}").rename(root / "source-R4")
    r4 = root / "source-R4/aspnet-core"
    refs = {
        "Core": ["Abp.ZeroCore.EntityFrameworkCore", "Abp.AutoMapper"],
        "Web.Core": ["Abp.AspNetCore", "Abp.ZeroCore", "Abp.AspNetCore.SignalR"],
        "Web.Host": ["Abp.Castle.Log4Net"],
        "Migrator": ["Abp.Castle.Log4Net"],
    }
    microsoft = {
        "EntityFrameworkCore": ["Microsoft.EntityFrameworkCore.SqlServer",
                                "Microsoft.EntityFrameworkCore.Design", "Microsoft.EntityFrameworkCore.Tools"],
        "Web.Core": ["Microsoft.AspNetCore.Authentication.JwtBearer"],
        "Web.Host": ["Microsoft.EntityFrameworkCore.Design"],
    }
    for name in ("Core", "Application", "EntityFrameworkCore", "Web.Core", "Web.Host", "Migrator"):
        file = project(r4, name)
        change_project(file, "<TargetFramework>net9.0</TargetFramework>",
                       "<TargetFramework>net10.0</TargetFramework>")
        for package in refs.get(name, []):
            change_project(file, f'Include="{package}" Version="10.2.0"',
                           f'Include="Du.{package}" Version="[10.5.1]"')
        for package in microsoft.get(name, []):
            change_project(file, f'Include="{package}" Version="9.0.5"',
                           f'Include="{package}" Version="{RUNTIME}"')
    shutil.copytree(root / "source-R4", root / "source-R5")
    change_project(project(root / "source-R5/aspnet-core", "Core"),
                   'Include="Du.Abp.AutoMapper" Version="[10.5.1]"',
                   'Include="Du.Abp.AutoMapper" Version="[10.5.2]"')
    migrations = r4 / "src" / f"{PREFIX}.EntityFrameworkCore" / "Migrations"
    ids = sorted(match for file in migrations.glob("*.Designer.cs")
                 for match in re.findall(r'\[Migration\("([^"]+)"\)\]', file.read_text(encoding="utf-8-sig")))
    require(len(ids) == len(set(ids)) == 30, f"固定模板迁移 ID 不符：{ids}")
    seed = r4 / "src" / f"{PREFIX}.Core" / "Authorization/Users/User.cs"
    passwords = re.findall(r'DefaultPassword\s*=\s*"([^"]+)"', seed.read_text(encoding="utf-8-sig"))
    require(len(passwords) == 1, "未找到固定模板的管理员种子密码")
    return ids, passwords[0]


def expected_packages(root, env):
    attachments = {}
    for release, (asset, digest) in ATTACHMENTS.items():
        path = root / f"{release}-PACKAGE-CHECKSUMS.json"
        # 每次请求使用新的重定向，避免缓存中的短期下载地址失效。
        download(f"{RELEASE_ASSETS}/{asset}?consumer={int(time.time())}", path, env,
                 ("--header", "Accept: application/octet-stream"))
        require(sha256(path) == digest, f"{path.name} SHA-256 预期 {digest}，实际 {sha256(path)}")
        attachments[release] = read_json(path)
    r4 = {pkg: value["mainPackage"]["anonymousDownloadSha256"]
          for pkg, value in attachments["R4"]["packages"].items()}
    new = {pkg: value["mainPackage"]["anonymousDownloadSha256"]
           for pkg, value in attachments["R5"]["packages"].items()}
    carried = {pkg: value["anonymousDownloadSha256"]
               for pkg, value in attachments["R5"]["carriedPackages"].items()}
    require(len(r4) == 13 and new.keys() == MAPPING.keys() and
            carried == {pkg: digest for pkg, digest in r4.items() if pkg not in MAPPING},
            "两个公开附件中的 3 个新包或 10 个沿用包不符")
    return {"R4": r4, "R5": carried | new}


def verify_entry(assets, cache, output, release, entry, checksums):
    graph = read_json(assets)
    package_folders = [Path(folder) for folder in graph["packageFolders"]]
    require(package_folders == [cache],
            f"{release} {entry} 缓存目录预期 {cache}，实际 {package_folders}")
    sources = list(graph["project"]["restore"]["sources"])
    require(sources == [NUGET], f"{release} {entry} 包源预期 {[NUGET]}，实际 {sources}")
    expected_versions = {pkg: "10.5.1" for pkg in checksums}
    expected_versions.update({
        "Du.Abp.AutoMapper": "10.5.1" if release == "R4" else "10.5.2",
        "Du.AutoMapper": "14.0.0" if release == "R4" else "14.0.1",
        "Du.AutoMapper.Collection": "11.0.0" if release == "R4" else "11.0.1",
    })
    expected_ids = set(checksums)
    if entry == "Migrator":
        expected_ids -= {"Du.Abp.AspNetCore", "Du.Abp.AspNetCore.SignalR", "Du.Abp.Web.Common"}
    target = graph["targets"][TFM]
    observed = {}
    for identity, node in target.items():
        pkg, version = identity.split("/", 1)
        if node["type"] != "package":
            continue
        require(not re.match(r"^(Abp|AutoMapper)(\.|$)", pkg, flags=re.I),
                f"{release} {entry} 出现上游包 {identity}")
        if not pkg.casefold().startswith("du."):
            continue
        require(pkg in expected_ids and version == expected_versions[pkg],
                f"{release} {entry} 包版本预期 {expected_versions.get(pkg)}，实际 {identity}")
        folder = cache / graph["libraries"][identity]["path"]
        package = folder / (identity.replace("/", ".").lower() + ".nupkg")
        origin = read_json(folder / ".nupkg.metadata")["source"]
        require(origin == NUGET, f"{release} {entry} {pkg} 来源预期 {NUGET}，实际 {origin}")
        digest = sha256(package)
        require(digest == checksums[pkg],
                f"{release} {entry} {pkg} SHA-256 预期 {checksums[pkg]}，实际 {digest}")
        row = {"version": version, "source": origin, "nupkg": str(package), "sha256": digest}
        if pkg in MAPPING:
            dll = MAPPING[pkg]
            selected = [file for file in node["runtime"] if Path(file).name == dll]
            require(len(selected) == 1, f"{release} {entry} {identity} DLL 资产不唯一：{selected}")
            with zipfile.ZipFile(package) as bundle:
                member_digest = hashlib.sha256(bundle.read(selected[0])).hexdigest()
            output_digest = sha256(output / dll)
            require(output_digest == member_digest,
                    f"{release} {entry} {dll} SHA-256 预期 {member_digest}，实际 {output_digest}")
            row.update(member=selected[0], output=str(output / dll), dllSha256=output_digest)
        observed[pkg] = row
    require(set(observed) == expected_ids and len(observed) == ENTRIES[entry],
            f"{release} {entry} 维护包预期 {sorted(expected_ids)}，实际 {sorted(observed)}")
    return observed


def inventory(directory):
    return {file.relative_to(directory).as_posix(): sha256(file)
            for file in sorted(directory.rglob("*")) if file.is_file()}


def build(root, release, checksums, env):
    source = root / f"source-{release}/aspnet-core"
    cache = root / f"packages-{release}"
    cache.mkdir()
    http_cache = root / f"http-cache-{release}"
    http_cache.mkdir()
    config = root / "NuGet.Config"
    env = env | {"NUGET_PACKAGES": str(cache), "NUGET_HTTP_CACHE_PATH": str(http_cache)}
    for entry in ENTRIES:
        csproj = project(source, entry)
        label = f"{release}-{entry}"
        command(["dotnet", "restore", str(csproj), "--configfile", str(config),
                 "--source", NUGET, "--packages", str(cache), "--no-http-cache", "--force",
                 "--disable-build-servers", "-p:Configuration=Release", "-p:RestoreAdditionalProjectSources=",
                 "-p:RestoreFallbackFolders=", "-p:RestoreAdditionalProjectFallbackFolders=",
                 "-p:DisableImplicitNuGetFallbackFolder=true"], source, root / f"{label}-restore.log", env)
        command(["dotnet", "build", str(csproj), "-c", "Release", "--no-restore",
                 "--disable-build-servers"], source, root / f"{label}-build.log", env)
        assets = root / f"{label}-assets.json"
        shutil.copy2(csproj.parent / "obj/project.assets.json", assets)
        directory = root / "output" / release / entry
        shutil.copytree(csproj.parent / f"bin/Release/{TFM}", directory)
        runtimeconfig = directory / f"{PREFIX}.{entry}.runtimeconfig.json"
        config_json = read_json(runtimeconfig)
        options = config_json["runtimeOptions"]
        frameworks = [options["framework"]] if "framework" in options else options["frameworks"]
        names = {framework["name"] for framework in frameworks}
        require(names == {"Microsoft.NETCore.App", "Microsoft.AspNetCore.App"},
                f"{label} 共享框架不符：{names}")
        for framework in frameworks:
            framework["version"] = RUNTIME
        options["rollForward"] = "Disable"
        save(runtimeconfig, config_json)
        # 把模板的滚动日志移出将被封存的 Release 目录。
        log_config = directory / "log4net.config"
        log_text = log_config.read_text(encoding="utf-8-sig")
        log_config.write_text(re.sub(r'(<file value=")[^"]+(" />)',
                                     r'\1${CONSUMER_ROLLBACK_APP_LOG}\2', log_text))
        save(root / f"{label}-packages.json", verify_entry(assets, cache, directory, release, entry, checksums))
        save(root / f"{label}-manifest.json", inventory(directory))


class Exercise:
    def __init__(self, root, args, sql_password):
        self.root = root
        self.args = args
        self.sql_password = sql_password
        self.sensitive = [sql_password]
        self.suffix = secrets.token_hex(6)
        self.db = f"DuRollback_{self.suffix}"
        self.receipts = {}
        self.base = f"http://127.0.0.1:{args.http_port}"
        self.identity = None
        self.history = None
        self.stage = "inputs"
        self.summary = {stage: {"status": "not-run", "steps": {name: "not-run" for name in steps}}
                        for stage, steps in {
            "inputs": ("public-inputs", "build-R4", "build-R5"),
            "R4-create": ("verify-output", "preflight", "migrate", "start-host", "authenticate", "create-A"),
            "R5-create": ("verify-output", "preflight", "migrate", "start-host", "authenticate",
                          "read-A", "create-B", "read-B"),
            "R4-rollback": ("verify-output", "preflight", "migrate", "start-host", "authenticate",
                            "read-A", "read-B"),
            "R4-dll-replaced": ("verify-output", "preflight", "migrate", "start-host", "authenticate"),
        }.items()}

    def evidence(self, name, data):
        save(self.root / f"{self.stage}-{name}.json", data)

    def redact(self, text):
        for secret in self.sensitive:
            if secret:
                text = text.replace(secret, "[已隐藏]")
        return text

    @contextlib.contextmanager
    def step(self, name):
        stage = self.summary[self.stage]
        stage["status"] = "running"
        stage["steps"][name] = "running"
        self.write_summary()
        try:
            yield
        except Exception as exc:
            stage["status"] = "failed"
            stage["steps"][name] = "failed"
            self.evidence(f"{name}-error", {"error": self.redact(str(exc))})
            raise
        else:
            stage["steps"][name] = "passed"
        finally:
            self.write_summary()

    def write_summary(self):
        save(self.root / "steps.json", self.summary)

    def sql(self, text, params=None, database=None):
        with pymssql.connect(server="127.0.0.1", port=str(self.args.sql_port),
                             user=self.args.sql_login, password=self.sql_password,
                             database=database or self.db, as_dict=True, autocommit=True,
                             encryption="require", login_timeout=8, timeout=15) as connection:
            with connection.cursor() as cursor:
                cursor.execute(text, params)
                return cursor.fetchall() if cursor.description else []

    def check_identity(self, database):
        rows = self.sql(IDENTITY, database=database)
        require(len(rows) == 1, f"{database} 预期一条数据库身份，实际 {rows}")
        row = rows[0]
        expected = {"instance": self.args.server_name, "version": "16.0.4236.2", "name": database}
        require(all(row[key] == value for key, value in expected.items()) and
                "Developer" in row["edition"] and row["guid"],
                f"SQL 预期 {expected}、Developer 版及 GUID，实际 {row}")
        if database == self.db and self.identity is not None:
            require(row == self.identity, f"数据库身份预期 {self.identity}，实际 {row}")
        return row

    def new_database(self):
        master = self.check_identity("master")
        self.sql(f"CREATE DATABASE [{self.db}]", database="master")
        self.identity = self.check_identity(self.db)
        tables = self.sql("SELECT name FROM sys.tables WHERE is_ms_shipped = 0 ORDER BY name")
        self.evidence("new-database", {"master": master, "database": self.identity, "tables": tables})
        require(tables == [], f"专用库应为空库，实际 {tables}")

    def verify_output(self, base, release):
        for entry in ENTRIES:
            expected = read_json(self.root / f"{release}-{entry}-manifest.json")
            actual = inventory(base / entry)
            difference = {file: {"expected": expected.get(file), "actual": actual.get(file)}
                          for file in sorted(expected.keys() | actual.keys())
                          if expected.get(file) != actual.get(file)}
            self.evidence(f"{entry}-integrity", {"directory": str(base / entry),
                                                "fileCount": len(actual), "difference": difference})
            if difference:
                raise ManifestMismatch(f"{entry} {base / entry} 文件清单不符：{difference}")

    def runtime_envs(self, base):
        # 两入口从各自的 Release 目录取配置。模板的环境变量覆盖 JSON，
        # Web.Host 的 Development User Secrets 再覆盖环境变量。
        # 用本轮新建的绝对路径隔离 APPDATA 和进程 home，清除继承的运行配置。
        clean_home = self.root / f"{self.stage}-home"
        clean_home.mkdir()
        localhost = f"127.0.0.1,{self.args.sql_port}"
        def quote(connection_value):
            return '"' + connection_value.replace('"', '""') + '"'

        connection = (f"Server={localhost};Database={self.db};User ID={quote(self.args.sql_login)};"
                      f"Password={quote(self.sql_password)};Encrypt=True;TrustServerCertificate=True")
        envs = {}
        for entry in ENTRIES:
            dir_path = base / entry
            actual = self.check_identity(self.db)
            settings = dir_path / "appsettings.json"
            require(isinstance(read_json(settings)["ConnectionStrings"]["Default"], str),
                    f"{entry} 模板连接配置缺失")
            self.evidence(f"{entry}-connection", {"cwd": str(dir_path),
                          "settingsSha256": sha256(settings), "server": localhost,
                          "override": "ConnectionStrings__Default", "userSecretsDirectory": str(clean_home),
                          "database": actual})
            envs[entry] = {"PATH": BUILD_ENV["PATH"], "HOME": str(clean_home), "APPDATA": str(clean_home),
                           "DOTNET_ENVIRONMENT": "Development", "ASPNETCORE_ENVIRONMENT": "Development",
                           "TMPDIR": self.native_temp, "ConnectionStrings__Default": connection,
                           "Kestrel__Endpoints__Http__Url": self.base,
                           "App__ServerRootAddress": self.base + "/", "DOTNET_HOST_TRACE": "1",
                           "DOTNET_HOST_TRACEFILE": str(self.root / f"{self.stage}-{entry}-dotnet.log"),
                           "CONSUMER_ROLLBACK_APP_LOG": str(self.root / f"{self.stage}-{entry}-application.log")}
        return envs

    def sql_snapshot(self, label):
        identity = self.check_identity(self.db)
        tables = self.sql("SELECT name FROM sys.tables WHERE is_ms_shipped = 0 ORDER BY name")
        if not tables:
            data = {"database": identity, "tables": tables}
        else:
            data = {"database": identity, "tables": tables, "migrations": self.sql(MIGRATIONS),
                    "tenantConnections": self.sql("""
                        SELECT Id, TenancyName,
                               CASE WHEN NULLIF(ConnectionString, '') IS NULL THEN 0 ELSE 1 END AS separate
                        FROM dbo.AbpTenants ORDER BY Id"""),
                    "users": self.sql("SELECT Id, TenantId, UserName, Name, Surname, EmailAddress, IsActive, IsDeleted "
                                      "FROM dbo.AbpUsers ORDER BY Id"),
                    "logins": self.sql("SELECT Id, TenantId, UserId, Result FROM dbo.AbpUserLoginAttempts ORDER BY Id")}
        self.evidence(label, data)
        return data

    def compare_history(self, data, ids):
        ids_actual = [row["MigrationId"] for row in data["migrations"]]
        require(ids_actual == ids, f"迁移 ID 预期 {ids}，实际 {ids_actual}")
        require(not any(row["separate"] for row in data["tenantConnections"]),
                f"模板租户有独立连接，停止：{data['tenantConnections']}")
        if self.history is not None:
            require(data["migrations"] == self.history, "迁移历史变化，见各阶段 SQL 快照")

    @contextlib.contextmanager
    def process(self, entry, base, env):
        cwd = base / entry
        dll = f"{PREFIX}.{entry}.dll"
        argv = ["dotnet", dll] + (["-q"] if entry == "Migrator" else [])
        # stdout/stderr 先经管道，由父进程脱敏后落盘。应用框架日志另行留存。
        from threading import Thread

        stdout_log = self.root / f"{self.stage}-{entry}-stdout.log"
        with subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, errors="replace") as child:
            observation = {"argv": argv, "cwd": str(cwd), "pid": child.pid, "exitCode": None}
            self.evidence(entry + "-process", observation)

            def copy_output():
                with stdout_log.open("w") as log:
                    for line in child.stdout:
                        log.write(self.redact(line))
                        log.flush()

            drain = Thread(target=copy_output)
            drain.start()
            try:
                yield child
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                drain.join()
                observation["exitCode"] = child.returncode
                self.evidence(entry + "-process", observation)
                app_log = Path(env["CONSUMER_ROLLBACK_APP_LOG"])
                if app_log.exists():
                    app_log.write_text(self.redact(app_log.read_text(errors="replace")))

    def read_api(self, path, headers=None, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = request.Request(self.base + path, data, {"Content-Type": "application/json", **(headers or {})})
        try:
            with HTTP.open(req, timeout=12) as response:
                return response.status, json.loads(response.read())
        except error.HTTPError as exc:
            try:
                body = json.loads(exc.read())
            except (UnicodeError, ValueError):
                body = {}
            return exc.code, body

    def readiness(self, child):
        path = "/swagger/v1/swagger.json"
        log = self.root / f"{self.stage}-Web.Host-stdout.log"
        for _ in range(120):
            require(child.poll() is None, f"Web.Host 提前退出 {child.returncode}")
            try:
                status, body = self.read_api(path)
                listening = log.exists() and f"Now listening on: {self.base}" in log.read_text()
                if status == 200 and str(body.get("openapi", "")).startswith("3.") and listening:
                    self.evidence("Web.Host-listening", {"pid": child.pid, "address": self.base,
                                                         "path": path, "status": status})
                    return
            except (error.URLError, ValueError):
                pass
            time.sleep(0.5)
        raise RuntimeError(f"未观察到本轮 Host 监听 {self.base} 并返回 Swagger，见 {log}")

    def login(self, password):
        path = "/api/TokenAuth/Authenticate"
        tenant_sql = self.sql("SELECT Id, TenancyName FROM dbo.AbpTenants "
                              "WHERE TenancyName = 'Default' AND IsActive = 1 AND IsDeleted = 0")
        require(len(tenant_sql) == 1, f"Default 租户不唯一：{tenant_sql}")
        self.tenant_id = tenant_sql[0]["Id"]
        admins = self.sql("SELECT Id FROM dbo.AbpUsers WHERE TenantId = %s AND UserName = 'admin' "
                          "AND IsActive = 1 AND IsDeleted = 0", (self.tenant_id,))
        require(len(admins) == 1, f"Default/admin 不唯一：{admins}")
        admin_id = admins[0]["Id"]
        headers = {"Abp-TenantId": str(self.tenant_id)}
        status, data = self.read_api(path, headers, {"userNameOrEmailAddress": "admin", "password": password})
        auth = data.get("result") or {}
        token = auth.get("accessToken")
        self.sensitive.extend(value for value in (token, auth.get("encryptedAccessToken")) if value)
        self.evidence("authenticate-api", {"path": path, "status": status, "success": data.get("success"),
                                           "userId": auth.get("userId")})
        require(status == 200 and data.get("success") is True and token and auth.get("userId") == admin_id,
                "租户的管理员认证未成功，见认证回执")
        headers["Authorization"] = "Bearer " + token
        path = "/api/services/app/Session/GetCurrentLoginInformations"
        status, data = self.read_api(path, headers)
        result = data.get("result") or {}
        user = result.get("user") or {}
        tenant = result.get("tenant") or {}
        identity = {"tenantId": tenant.get("id"), "userId": user.get("id"), "userName": user.get("userName")}
        self.evidence("session-api", {"path": path, "status": status, "success": data.get("success"),
                                      "identity": identity, "tenancyName": tenant.get("tenancyName")})
        require(status == 200 and data.get("success") is True and
                identity == {"tenantId": self.tenant_id, "userId": admin_id, "userName": "admin"}
                and tenant.get("tenancyName") == "Default", "授权会话身份不符")
        path = "/AbpUserConfiguration/GetAll"
        status, data = self.read_api(path, headers)
        permission = (data.get("result") or data).get("auth", {}).get("grantedPermissions", {}).get("Pages.Users")
        self.evidence("authorization-api", {"path": path, "status": status, "Pages.Users": permission})
        require(status == 200 and permission in (True, "true"), "Default/admin 会话缺少 Pages.Users")
        return headers, admin_id

    def create(self, label, headers):
        name = f"durollback{label.lower()}{self.suffix}"
        fields = {"userName": name, "name": f"Consumer{label}", "surname": "Rollback",
                  "emailAddress": name + "@example.invalid", "isActive": True}
        password = "DuA!" + secrets.token_hex(12)
        self.sensitive.append(password)
        path = "/api/services/app/User/Create"
        status, data = self.read_api(path, headers, fields | {"password": password, "roleNames": []})
        result = data.get("result") or {}
        receipt = {"stage": self.stage, "tenantId": self.tenant_id, "tenancyName": "Default",
                   "path": path, "status": status, "success": data.get("success"),
                   "submitted": fields, "id": result.get("id"), "userName": result.get("userName")}
        self.evidence(f"{label}-create-receipt", receipt)
        self.receipts[label] = receipt
        require(status == 200 and data.get("success") is True and isinstance(receipt["id"], int)
                and receipt["id"] > 0 and receipt["userName"] == name, f"{label} 创建回执不符：{receipt}")
        rows = self.read_sql_user(label)
        require(rows == [{"id": receipt["id"], "tenantId": self.tenant_id, **fields}],
                f"{label} 创建后的 SQL 用户行不符：{rows}")

    def read_sql_user(self, label):
        receipt = self.receipts[label]
        snapshot = {"tenantId": self.tenant_id, "id": receipt["id"], "rows": None}
        try:
            snapshot["rows"] = self.sql(USER_ROW, (self.tenant_id, receipt["id"]))
        except Exception as exc:
            snapshot["error"] = self.redact(str(exc))
            raise
        finally:
            self.evidence(f"{label}-sql-user", snapshot)
        return snapshot["rows"]

    def read_user(self, label, headers):
        receipt = self.receipts[label]
        expected = {"id": receipt["id"], **receipt["submitted"]}
        path = "/api/services/app/User/GetAll"
        query = parse.urlencode({"Keyword": receipt["userName"], "SkipCount": 0, "MaxResultCount": 10})
        event = {"path": path, "query": query, "requestId": secrets.token_hex(8), "tenantId": self.tenant_id,
                 "expected": expected}
        try:
            status, body = self.read_api(path + "?" + query, headers | {"X-Request-ID": event["requestId"]})
            result = body.get("result") or {}
            items = result.get("items")
            event.update(status=status, success=body.get("success"), totalCount=result.get("totalCount"),
                         itemCount=len(items) if isinstance(items, list) else None,
                         items=[{key: row.get(key) for key in expected} if isinstance(row, dict) else None
                                for row in items] if isinstance(items, list) else None)
            require(status == 200 and event["success"] is True and event["totalCount"] == 1
                    and event["items"] == [expected], f"{label} 授权查询不符，见逐人回执")
        except Exception as exc:
            event["error"] = self.redact(str(exc))
            raise
        finally:
            self.evidence(f"{label}-read-api", event)
            active_error = sys.exc_info()[0] is not None
            try:
                rows = self.read_sql_user(label)
                require(rows == [{"tenantId": self.tenant_id, **expected}], f"{label} SQL 用户行不符：{rows}")
            except Exception as exc:
                self.evidence(f"{label}-sql-user-error", {"error": self.redact(str(exc))})
                if not active_error:
                    raise

    def run_stage(self, stage, release, base, ids, password):
        self.stage = stage
        with self.step("verify-output"):
            self.verify_output(base, release)
        with self.step("preflight"):
            with socket.socket() as sock:
                # 已退出的 Host 可能留下 TIME_WAIT。允许复用关闭的连接，
                # 仍以成功绑定和监听确认当前没有进程占用该端口。
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", self.args.http_port))
                sock.listen(1)
            before = self.sql_snapshot("before")
            if stage == "R4-create":
                require(before["tables"] == [], "首段迁移前测试库应为空")
            else:
                self.compare_history(before, ids)
            envs = self.runtime_envs(base)

        with self.step("migrate"):
            with self.process("Migrator", base, envs["Migrator"]) as child:
                code = child.wait(timeout=240)
                require(code == 0, f"Migrator 退出 {code}")
            after = self.sql_snapshot("after-migrate")
            self.compare_history(after, ids)
            if stage == "R4-create":
                self.history = after["migrations"]
            stdout = (self.root / f"{self.stage}-Migrator-stdout.log").read_text()
            require("Host database:" in stdout and self.db in stdout, "迁移进程日志缺少预期测试库名")

        with self.process("Web.Host", base, envs["Web.Host"]) as child:
            with self.step("start-host"):
                self.readiness(child)
            try:
                with self.step("authenticate"):
                    headers, admin_id = self.login(password)
                if stage == "R4-create":
                    with self.step("create-A"):
                        self.create("A", headers)
                elif stage == "R5-create":
                    with self.step("read-A"):
                        self.read_user("A", headers)
                    with self.step("create-B"):
                        self.create("B", headers)
                    with self.step("read-B"):
                        self.read_user("B", headers)
                else:
                    with self.step("read-A"):
                        self.read_user("A", headers)
                    with self.step("read-B"):
                        self.read_user("B", headers)
                after_login = self.sql_snapshot("after-business")
                self.compare_history(after_login, ids)
                logins_added = [row for row in after_login["logins"] if row not in after["logins"]]
                require(len(logins_added) == 1 and logins_added[0]["TenantId"] == self.tenant_id
                        and logins_added[0]["UserId"] == admin_id and logins_added[0]["Result"] == 1,
                        f"{stage} 应且只应新增一条成功认证行，实际 {logins_added}")
                self.evidence("login-delta", logins_added)
            except Exception:
                try:
                    self.sql_snapshot("after-failure")
                except Exception as exc:
                    self.evidence("after-failure-error", {"error": self.redact(str(exc))})
                raise
        self.summary[stage]["status"] = "passed"
        self.write_summary()

    def reject_replaced_dll(self, ids, password):
        r4 = self.root / "output/R4"
        copy = self.root / "output/R4-replaced"
        shutil.copytree(r4, copy)
        shutil.copy2(self.root / "output/R5/Migrator/AutoMapper.dll", copy / "Migrator/AutoMapper.dll")
        self.stage = "R4-dll-replaced"
        before = self.sql_snapshot("negative-before")
        try:
            self.run_stage(self.stage, "R4", copy, ids, password)
        except ManifestMismatch as exc:
            after = self.sql_snapshot("negative-after")
            difference = read_json(self.root / f"{self.stage}-Migrator-integrity.json")["difference"]
            evidence = {"error": str(exc), "rejected": True, "databaseEqual": before == after,
                        "processEvidence": [path.name for path in self.root.glob(f"{self.stage}-*-process.json")]}
            self.evidence("expected-stop", evidence)
            require(set(difference) == {"AutoMapper.dll"} and before == after and not evidence["processEvidence"],
                    f"替换 DLL 后的停止位置或数据库快照不符：{evidence}")
            self.summary[self.stage]["status"] = "rejected-as-expected"
            self.write_summary()
        else:
            raise RuntimeError("替换 DLL 的 R4 副本竟通过回退")

    def run(self, guide, native_temp):
        root = self.root
        self.native_temp = native_temp
        env = BUILD_ENV | {"HOME": str(root / "tools-home"), "DOTNET_CLI_HOME": str(root / "tools-home"),
                           "TMPDIR": self.native_temp,
                           "DOTNET_NOLOGO": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1"}
        Path(env["HOME"]).mkdir()
        (root / "global.json").write_text(json.dumps({"sdk": {"version": SDK, "rollForward": "disable"}}))
        (root / "NuGet.Config").write_text(f"""<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources><clear /><add key="nuget.org" value="{NUGET}" /></packageSources>
  <fallbackPackageFolders><clear /></fallbackPackageFolders>
</configuration>
""")
        with self.step("public-inputs"):
            self.evidence("environment", {"guideSha256": sha256(guide), "scriptSha256": sha256(Path(__file__)),
                          "platform": platform.platform(), "machine": platform.machine(),
                          "pythonVersion": platform.python_version(), "pymssqlVersion": pymssql.__version__,
                          "templateCommit": TEMPLATE})
            sdk = command(["dotnet", "--version"], root, root / "sdk.log", env).strip()
            require(sdk == SDK, f"SDK 预期 {SDK}，实际 {sdk}")
            runtimes = command(["dotnet", "--list-runtimes"], root, root / "runtimes.log", env).splitlines()
            for framework in ("Microsoft.NETCore.App", "Microsoft.AspNetCore.App"):
                require(any(line.startswith(f"{framework} {RUNTIME} ") for line in runtimes),
                        f"缺少 {framework} {RUNTIME}")
            ids, password = prepare(root, env)
            self.sensitive.append(password)
            self.evidence("template", {"archiveSha256": sha256(root / "template.tar.gz"), "migrationIds": ids})
            checksums = expected_packages(root, env)
        for release in ("R4", "R5"):
            with self.step(f"build-{release}"):
                print(f"还原、构建和校验 {release}", flush=True)
                build(root, release, checksums[release], env)
        self.summary["inputs"]["status"] = "passed"
        self.stage = "R4-create"
        self.new_database()
        for stage, release in (("R4-create", "R4"), ("R5-create", "R5"), ("R4-rollback", "R4")):
            print(f"执行 {stage}", flush=True)
            self.run_stage(stage, release, root / "output" / release, ids, password)
        print("检查映射 DLL 被替换时的启动前停止", flush=True)
        self.reject_replaced_dll(ids, password)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--guide", type=Path, required=True)
    parser.add_argument("--output-parent", type=Path, required=True)
    parser.add_argument("--sql-port", type=int, required=True)
    parser.add_argument("--sql-login", required=True)
    parser.add_argument("--server-name", required=True)
    parser.add_argument("--http-port", type=int, default=5008)
    args = parser.parse_args()
    require(args.guide.is_file(), "需要本轮使用的指南原文")
    require(platform.system() == "Darwin" and platform.machine() == "arm64", "本例环境为 macOS ARM64")
    root = Path(tempfile.mkdtemp(prefix="run-", dir=args.output_parent.resolve()))
    print(f"结果目录 {root}", flush=True)
    exercise = Exercise(root, args, os.environ.get("DU_ROLLBACK_SQL_PASSWORD") or
                        getpass.getpass("专用实例 SQL 密码："))
    try:
        # macOS 的 .NET 命名互斥量需要可用且路径较短的临时目录。
        with tempfile.TemporaryDirectory(prefix="du-dotnet-", dir="/tmp") as native_temp:
            exercise.run(args.guide.resolve(), native_temp)
    except Exception as exc:
        exercise.summary[exercise.stage]["status"] = "failed"
        exercise.evidence("failure", {"error": exercise.redact(str(exc)), "exitCode": 1})
        exercise.write_summary()
        print(f"{exercise.stage} 失败：{exercise.redact(str(exc))}", file=sys.stderr)
        return 1
    print(f"三阶段及异常输入检查通过。测试库 {exercise.db} 保留供回读。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 运行与回读

在同一 Bash 会话中将示例端口、登录名和实例名改成本轮专用实例的实际值。Host 端口须空闲，三个阶段均在同一个环回地址启动和退出。运行时输入 SQL 密码。若从测试工具注入，可将密码仅放在本次进程的 `DU_ROLLBACK_SQL_PASSWORD` 环境变量中。应用登录使用固定模板在专用库中生成的 `Default/admin` 种子。

```bash
"$work/venv/bin/python" "$work/exercise.py" --guide "$guide" --output-parent "$work" \
  --sql-port 14333 --sql-login sa --server-name '替换为专用实例名' --http-port 5008
```

程序先分别从空缓存还原和构建 R4、R5，保存四张入口包图。核验两份匿名发行附件及其 SHA-256，按入口核对 10/13 个签后包和三份映射 DLL 的实际字节。R4 的两套封存输出以 `output/R4/` 为准，含经固定运行时和日志位置的配置。运行日志写到输出目录之外。末段直接使用首段的封存文件。[`v10.5.1` 公开附件](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json) · [`v10.5.2` 公开附件](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.2/R5-PACKAGE-CHECKSUMS.json)

每段都在旧 Host 已停止时核对输出清单和连接，确认两入口将使用已验证的环回 SQL 实例、库名及数据库 GUID，再运行 Migrator，最后启动本段 Host。首段迁移前须为空库，首段迁移后须与模板的 30 个迁移 ID 一致。其余两段迁移前后都须与首段按 ID 排序的历史逐行一致。连接预检同时检查既有模板租户没有独立连接。保留的 `*-dotnet.log` 可对照进程实际选择的框架版本，`*-process.json` 和 `*-listening.json` 记录进程路径、PID、退出码与 Host 监听地址。[模板的配置顺序](https://github.com/dusdong/module-zero-core-template/blob/2e9536872673a7ff1986a19e798c51684d16afe5/aspnet-core/src/AbpCompanyName.AbpProjectName.Core/Configuration/AppConfigurations.cs)

核对 `steps.json`、创建回执、独立授权查询和 SQL 快照。查询通过条件为 HTTP 200、`success=true`、`totalCount=1`、唯一用户的 ID 和用户名与创建回执一致，姓名、邮箱及启用状态与提交值一致。按租户及用户 ID 核实同库的应用记录。三个阶段各新增一条租户管理员的成功认证记录。末段 A、B 用同一次登录，以两个请求分别留证。

整体成功时命令退出 0。任一业务步骤失败时退出 1，在 `steps.json` 留下失败和未执行步骤。收到创建响应后立即写入创建回执。若 R5 创建 B 后查询失败，保留 A 的读回、B 的创建和失败查询，以及可查询到的 B 的 SQL 行或缺项。若回退阶段 A 成功、B 失败，分别保留两个查询结果。创建或查询失败时退出 Host，保留本轮隔离库供回读。

成功路径之后，脚本还会在复制的 R4 Migrator 目录中换入一份 R5 的 `AutoMapper.dll`，执行相同的切回入口。检查 `R4-dll-replaced-expected-stop.json`，应记录预期的校验失败、目录中无本段进程证据、迁移与业务快照相同。完成后关闭专用测试实例或按本机策略处置这座随机命名的测试库。保留所需报告时只提供脱敏数据。
