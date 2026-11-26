# 用 R4 维护包安装固定模板

本示例用 `net10.0` 构建 ASP.NET Core 免费模板的 Migrator 和 Web.Host，并在新的 SQL Server 测试库检查迁移与 HTTP 接口。模板固定为 `2e9536872673a7ff1986a19e798c51684d16afe5`。[模板源码](https://github.com/dusdong/module-zero-core-template/tree/2e9536872673a7ff1986a19e798c51684d16afe5)

| 场景 | 版本与当前证据 |
| --- | --- |
| 新安装示例 | `net10.0`，SDK `10.0.404`，.NET 和 ASP.NET Core `10.0.15`。从 nuget.org 还原后，Migrator 将空库迁移到 30 条模板记录，Web.Host 的 Swagger JSON 返回 HTTP 200。 |
| 存量应用迁移兼容性实测 | `net9.0`，.NET 和 ASP.NET Core `9.0.10`。从 nuget.org 还原后完成存量数据迁移、租户登录和授权查询，同库继续由 `net10.0` 接续。微软于 2026-11-10 结束 .NET 9 支持。 |

[本地实测矩阵](https://github.com/dusdong/du.aspnetboilerplate/blob/5758c8186b68dcc42ecc90164cf9d3f53cf3345e/docs/maintenance/r4-release-candidate.md#实测支持矩阵) · [.NET 支持周期](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core)

2026-11-26 的公开源实测在 macOS ARM64 运行 Migrator 和 Web.Host，使用独立的 SQL Server Developer `16.0.4236.2` 实例。新安装使用 `sqlcmd`（Go）`v1.10.0`。[sqlcmd 安装](https://learn.microsoft.com/sql/tools/sqlcmd/sqlcmd-download-install)

准备 Bash、Python 3、curl、tar、`sqlcmd`、表中所列的 .NET SDK 和共享运行时，以及可创建测试数据库的独立 SQL Server 实例。以下命令在同一个 Bash 会话中顺序执行。两入口分别使用便于复验的 `Release` 输出。Swagger JSON 用于核对 Host HTTP 响应。

## 取得源码并切换版本

```bash
set -euo pipefail
work="$(mktemp -d "${TMPDIR:-/tmp}/du-r4-install.XXXXXXXX")"
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
dotnet --version
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
        text = replace_once(text, f'Include="{package}" Version="10.2.0"',
                            f'Include="Du.{package}" Version="[10.5.1]"', path)
    for package in microsoft_refs.get(name, ()):
        text = replace_once(text, f'Include="{package}" Version="9.0.5"',
                            f'Include="{package}" Version="10.0.15"', path)
    path.write_text(text, encoding="utf-8")
PY
```

维护框架项目直接改用 `Du.Abp*` `10.5.1` 包。传递依赖会还原 `Du.AutoMapper 14.0.0` 和 `Du.AutoMapper.Collection 11.0.0`。模板的 `Abp` 命名空间和程序集身份保持原样。

## 从 nuget.org 还原并构建

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
    --no-http-cache --force -p:Configuration=Release \
    -p:RestoreAdditionalProjectSources= -p:RestoreFallbackFolders= \
    -p:RestoreAdditionalProjectFallbackFolders= -p:DisableImplicitNuGetFallbackFolder=true
  dotnet build "$project" --configuration Release --no-restore
done
```

## 新建测试库并运行 Migrator

填写测试 SQL Server 地址（例如 `127.0.0.1,1433`）与 SQL 登录。示例使用 `DuAbpR4Smoke` 并信任该测试实例的证书。库名已存在时创建会失败，以便保留原库。

```bash
read -r -p 'SQL Server: ' sql_server
read -r -p 'SQL login: ' sql_login
read -r -s -p 'SQL password: ' SQLCMDPASSWORD
printf '\n'
export SQLCMDPASSWORD

sql() { sqlcmd -b -C -S "$sql_server" -U "$sql_login" "$@"; }
sql -d master -Q 'CREATE DATABASE [DuAbpR4Smoke]'

escaped_password=${SQLCMDPASSWORD//\"/\"\"}
export ConnectionStrings__Default="Server=$sql_server;Database=DuAbpR4Smoke;User ID=$sql_login;Password=\"$escaped_password\";Encrypt=True;TrustServerCertificate=True"
unset escaped_password

(
  cd "src/$prefix.Migrator/bin/Release/net10.0"
  dotnet "$prefix.Migrator.dll" -q
)

sql -d DuAbpR4Smoke -Q "
SET NOCOUNT ON;
IF OBJECT_ID(N'dbo.__EFMigrationsHistory', N'U') IS NULL
  THROW 50001, 'Missing EF migration history', 1;
IF NOT EXISTS (
  SELECT 1 FROM dbo.__EFMigrationsHistory WHERE MigrationId = N'20170424115119_Initial_Migrations'
)
  THROW 50002, 'Missing template migration', 1;
SELECT DB_NAME() AS DatabaseName, COUNT(*) AS MigrationCount FROM dbo.__EFMigrationsHistory;
"
```

Migrator 应退出 0。SQL 应返回 `DuAbpR4Smoke` 和大于零的迁移条数，并通过初始迁移 ID 的断言。

## 检查 Web.Host

使用空闲的环回端口 `5008`。检查完成后结束此次启动的 Host。

```bash
(
  cd "src/$prefix.Web.Host/bin/Release/net10.0"
  export ASPNETCORE_ENVIRONMENT=Development DOTNET_ENVIRONMENT=Development
  export Kestrel__Endpoints__Http__Url=http://127.0.0.1:5008
  export App__ServerRootAddress=http://127.0.0.1:5008/
  dotnet "$prefix.Web.Host.dll" > "$work/host.log" 2>&1 &
  pid=$!
  trap 'kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true' EXIT
  url=http://127.0.0.1:5008/swagger/v1/swagger.json
  status="$(curl --fail --silent --show-error --retry 20 --retry-connrefused \
    --retry-delay 1 --max-time 5 -o "$work/swagger.json" -w '%{http_code}' "$url")"
  kill -0 "$pid"
  test "$status" = 200
  python3 - "$work/swagger.json" <<'PY'
import json
import sys
from pathlib import Path

document = json.loads(Path(sys.argv[1]).read_text())
assert document["openapi"].startswith("3.") and document["info"]["version"] == "v1"
print("HTTP 200, Swagger v1")
PY
)
unset SQLCMDPASSWORD ConnectionStrings__Default
```

本示例保留刚创建的测试库以及工作目录中的 Host 日志和 Swagger 响应。
