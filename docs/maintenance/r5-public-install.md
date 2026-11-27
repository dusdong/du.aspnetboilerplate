# 用 R5 映射补丁安装固定模板

本指南从 nuget.org 还原维护包，用 `net10.0` 构建 ASP.NET Core 免费模板的 Migrator 和 Web.Host。在新 SQL Server 测试库执行模板迁移，再检查 Web.Host 的 Swagger JSON。模板源码固定为 `2e9536872673a7ff1986a19e798c51684d16afe5`。[固定模板](https://github.com/dusdong/module-zero-core-template/tree/2e9536872673a7ff1986a19e798c51684d16afe5)

| 包 | 本示例解析的版本 |
| --- | --- |
| [Du.Abp.AutoMapper](https://www.nuget.org/packages/Du.Abp.AutoMapper/10.5.2) | `10.5.2`，由 Core 精确引用 |
| [Du.AutoMapper](https://www.nuget.org/packages/Du.AutoMapper/14.0.1) | `14.0.1`，由映射包的精确依赖传递引入 |
| [Du.AutoMapper.Collection](https://www.nuget.org/packages/Du.AutoMapper.Collection/11.0.1) | `11.0.1`，由适配器的精确依赖传递引入 |
| 其余被引用的 Du 框架包 | `10.5.1`，沿用 R4 公开包 |

准备 Bash、Python 3、curl、tar、Go 版 `sqlcmd` 以及 .NET SDK `10.0.404`。该 SDK 包含 .NET 和 ASP.NET Core `10.0.15` 共享运行时。准备独立的 SQL Server 测试实例，以及有权创建数据库、执行模板迁移和访问新库的 SQL 登录。在终端启动 `bash`，并在同一会话中依次执行以下命令。Host 使用环回端口 `5008`，占用时将下文的 `host_port` 改为其他空闲端口。[.NET 10 下载](https://dotnet.microsoft.com/en-us/download/dotnet/10.0) · [sqlcmd 安装](https://learn.microsoft.com/sql/tools/sqlcmd/sqlcmd-download-install)

## 取得模板并固定引用

```bash
set -euo pipefail
work="$(mktemp -d "${TMPDIR:-/tmp}/du-r5-install.XXXXXXXX")"
printf '工作目录 %s\n' "$work"
template=2e9536872673a7ff1986a19e798c51684d16afe5
cd "$work"
curl --fail --silent --show-error --location --retry 2 \
  "https://codeload.github.com/dusdong/module-zero-core-template/tar.gz/$template" \
  -o template.tar.gz
tar -xzf template.tar.gz
mv "module-zero-core-template-$template" template

cat > global.json <<'EOF'
{"sdk":{"version":"10.0.404","rollForward":"disable"}}
EOF
test "$(dotnet --version)" = 10.0.404
dotnet --list-runtimes

cd template/aspnet-core
python3 - <<'PY'
from pathlib import Path

prefix = "AbpCompanyName.AbpProjectName"
framework_refs = {
    "Core": ("Abp.ZeroCore.EntityFrameworkCore", "Abp.AutoMapper"),
    "Web.Core": ("Abp.AspNetCore", "Abp.ZeroCore", "Abp.AspNetCore.SignalR"),
    "Web.Host": ("Abp.Castle.Log4Net",),
    "Migrator": ("Abp.Castle.Log4Net",),
}
microsoft_refs = {
    "EntityFrameworkCore": ("Microsoft.EntityFrameworkCore.SqlServer",
                            "Microsoft.EntityFrameworkCore.Design",
                            "Microsoft.EntityFrameworkCore.Tools"),
    "Web.Core": ("Microsoft.AspNetCore.Authentication.JwtBearer",),
    "Web.Host": ("Microsoft.EntityFrameworkCore.Design",),
}

def replace_once(text, old, new, path):
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected exactly one {old}")
    return text.replace(old, new)

for name in ("Core", "Application", "EntityFrameworkCore", "Web.Core", "Web.Host", "Migrator"):
    project = f"{prefix}.{name}"
    path = Path("src") / project / f"{project}.csproj"
    text = replace_once(path.read_text(encoding="utf-8"), "<TargetFramework>net9.0</TargetFramework>",
                        "<TargetFramework>net10.0</TargetFramework>", path)
    for package in framework_refs.get(name, ()):
        version = "10.5.2" if package == "Abp.AutoMapper" else "10.5.1"
        text = replace_once(text, f'Include="{package}" Version="10.2.0"',
                            f'Include="Du.{package}" Version="[{version}]"', path)
    for package in microsoft_refs.get(name, ()):
        text = replace_once(text, f'Include="{package}" Version="9.0.5"',
                            f'Include="{package}" Version="10.0.15"', path)
    path.write_text(text, encoding="utf-8")
PY
```

Core 直接引用 `Du.Abp.AutoMapper [10.5.2]` 和 `Du.Abp.ZeroCore.EntityFrameworkCore [10.5.1]`。示例中其余直接引用的 Du 包也精确固定为 `[10.5.1]`。模板代码继续使用 `Abp` 命名空间。

## 仅从 nuget.org 还原并构建

从上一节结束的 `template/aspnet-core` 目录继续。两入口共用本次新建的空缓存。显式传入独立 NuGet 配置，避免读取模板自带的包源配置。

```bash
cat > "$work/NuGet.Config" <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
  </packageSources>
  <fallbackPackageFolders><clear /></fallbackPackageFolders>
</configuration>
EOF

prefix=AbpCompanyName.AbpProjectName
mkdir "$work/packages" "$work/http-cache"
export NUGET_PACKAGES="$work/packages"
export NUGET_HTTP_CACHE_PATH="$work/http-cache"
for entry in Migrator Web.Host; do
  project="src/$prefix.$entry/$prefix.$entry.csproj"
  dotnet restore "$project" --configfile "$work/NuGet.Config" \
    --source https://api.nuget.org/v3/index.json --packages "$NUGET_PACKAGES" \
    --no-http-cache --force --disable-build-servers -p:Configuration=Release \
    -p:RestoreAdditionalProjectSources= -p:RestoreFallbackFolders= \
    -p:RestoreAdditionalProjectFallbackFolders= -p:DisableImplicitNuGetFallbackFolder=true
  dotnet build "$project" --configuration Release --no-restore --disable-build-servers
done
```

检查两个入口的 `obj/project.assets.json` 和 Release 输出。这里的包图和 DLL 检查确认还原版本与可供加载的文件。Collection 由映射功能按需使用，Migrator 中的引擎和适配器也属于按需资产。本示例的迁移和 Swagger 请求只验证这两个入口的启动与运行路径。

```bash
python3 - "$prefix" <<'PY'
import json
import sys
from pathlib import Path

expected = {
    "Du.Abp.AutoMapper": ("10.5.2", "Abp.AutoMapper.dll"),
    "Du.AutoMapper": ("14.0.1", "AutoMapper.dll"),
    "Du.AutoMapper.Collection": ("11.0.1", "AutoMapper.Collection.dll"),
}
for entry in ("Migrator", "Web.Host"):
    project = Path("src") / f"{sys.argv[1]}.{entry}"
    graph = json.loads((project / "obj/project.assets.json").read_text(encoding="utf-8"))
    resolved = graph["targets"]["net10.0"]
    for package, (version, dll) in expected.items():
        matches = [key for key in resolved if key.split("/", 1)[0].casefold() == package.casefold()]
        if matches != [f"{package}/{version}"]:
            raise SystemExit(f"{entry}: expected {package}/{version}, found {matches}")
        output = project / "bin/Release/net10.0" / dll
        if not output.is_file():
            raise SystemExit(f"{entry}: missing {output}")
        print(f"{entry}: {matches[0]} -> {dll}")
PY
```

## 创建空库并验证迁移和 HTTP

输入专用 SQL Server 的地址（如 `127.0.0.1,1433`）、SQL 登录和密码。密码输入时隐藏。本次连接信任该测试实例的证书，仅用于隔离测试。脚本每次生成新的库名，创建成功后先确认用户表数为零，随后运行 Migrator。

```bash
(
  read -r -p 'SQL Server: ' sql_server
  read -r -p 'SQL login: ' sql_login
  read -r -s -p 'SQL password: ' SQLCMDPASSWORD
  printf '\n'
  export SQLCMDPASSWORD
  sql() { sqlcmd -b -C -W -S "$sql_server" -U "$sql_login" "$@"; }

  db="DuAbpR5Smoke_$(python3 -c 'import secrets; print(secrets.token_hex(6))')"
  sql -d master -Q "CREATE DATABASE [$db]"
  sql -d "$db" -Q "
  SET NOCOUNT ON;
  IF EXISTS (SELECT 1 FROM sys.tables WHERE is_ms_shipped = 0)
    THROW 50000, 'Expected an empty test database', 1;
  SELECT DB_NAME() AS DatabaseName, COUNT(*) AS UserTableCount FROM sys.tables WHERE is_ms_shipped = 0;
  " | tee "$work/sql-before.txt"

  export ConnectionStrings__Default="Server=\"${sql_server//\"/\"\"}\";Database=$db;User ID=\"${sql_login//\"/\"\"}\";Password=\"${SQLCMDPASSWORD//\"/\"\"}\";Encrypt=True;TrustServerCertificate=True"
  export ASPNETCORE_ENVIRONMENT=Development DOTNET_ENVIRONMENT=Development
  (
    cd "src/$prefix.Migrator/bin/Release/net10.0"
    exec dotnet "$prefix.Migrator.dll" -q
  ) | tee "$work/migrator.log"
  printf 'Migrator exit 0\n'

  sql -d "$db" -Q "
  SET NOCOUNT ON;
  IF OBJECT_ID(N'dbo.__EFMigrationsHistory', N'U') IS NULL
    THROW 50001, 'Missing EF migration history', 1;
  IF NOT EXISTS (
    SELECT 1 FROM dbo.__EFMigrationsHistory WHERE MigrationId = N'20170424115119_Initial_Migrations'
  )
    THROW 50002, 'Missing template migration', 1;
  SELECT DB_NAME() AS DatabaseName, COUNT(*) AS MigrationCount FROM dbo.__EFMigrationsHistory;
  " | tee "$work/sql-after.txt"

  host_port=5008
  base="http://127.0.0.1:$host_port"
  cd "src/$prefix.Web.Host/bin/Release/net10.0"
  export Kestrel__Endpoints__Http__Url="$base"
  export App__ServerRootAddress="$base/"
  dotnet "$prefix.Web.Host.dll" > "$work/host.log" 2>&1 &
  pid=$!
  printf 'Web.Host PID %s\n' "$pid"
  trap 'kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true' EXIT

  status="$(curl --noproxy '*' --fail --silent --show-error --retry 30 --retry-connrefused \
    --retry-delay 1 --max-time 5 --retry-max-time 45 \
    -o "$work/swagger.json" -w '%{http_code}' "$base/swagger/v1/swagger.json")"
  kill -0 "$pid"
  grep -F "Now listening on: $base" "$work/host.log"
  test "$status" = 200
  python3 - "$work/swagger.json" <<'PY'
import json
import sys
from pathlib import Path

document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not document["openapi"].startswith("3.") or document["info"]["version"] != "v1":
    raise SystemExit("Unexpected Swagger document")
print("HTTP 200, Swagger v1")
PY
)
```

检查 `Migrator exit 0`、SQL 返回的新库名和迁移条数，以及 `HTTP 200, Swagger v1`。固定模板的迁移历史应有 30 条记录。命令结束时会关闭此次启动的 Web.Host，保留测试库及工作目录中的包图、日志和 Swagger 响应。
