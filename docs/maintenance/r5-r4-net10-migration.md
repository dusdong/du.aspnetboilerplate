# 将存量 R4 应用从 .NET 9 迁到 .NET 10

适用于已经用 nuget.org 的 R4 维护包运行的存量应用。准备两份独立的应用源码、应用的完整 SQL Server 备份、可恢复该备份的隔离实例，以及原应用使用的客户端产物和一个已授权的测试租户账号。下文用固定模板举例。原版 `Abp.*` 包的应用，先在原 TFM 上完成换包与业务对照，再开始运行时迁移。[.NET 9 换包前置路径](r3-template-net9-packages.md) · [R4 新库历史实测](r4-public-install.md)

R5 本地三包候选另有固定模板的运行时接续与同库包切换证据。本文步骤使用当前 R4 公开组合。[R5 候选验收](r5-automapper-template.md)

## 核对源与目标

| 输入 | R4 源端实测 | R4 目标实测及本轮目标 |
| --- | --- | --- |
| 框架与运行时 | `net9.0`。Migrator、Web.Host 内的 `Microsoft.NETCore.App`、`Microsoft.AspNetCore.App` 均为 `9.0.10` | `net10.0`。两入口的两套共享框架均为 `10.0.15` |
| SDK 和平台 | SDK `10.0.404`，macOS ARM64 `27.2.1`（`26B131`） | 同源端 |
| 公开维护包 | 11 个 `Du.Abp*` `10.5.1`、`Du.AutoMapper 14.0.0`、`Du.AutoMapper.Collection 11.0.0`。Web.Host 还原全部 13 个，Migrator 还原 10 个 | 同一批公开包及归档摘要 |
| 数据库链 | 两入口 EF Core `9.0.18`、SQL Server Provider `9.0.5`、SqlClient `5.1.6` | 两入口 EF Core 和 SQL Server Provider `10.0.15`、SqlClient `6.1.7` |
| 源码、数据库和客户端 | `module-zero-core-template@2e9536872673a7ff1986a19e798c51684d16afe5` 的 R4 换包版，SQL Server Developer `16.0.4236.2`，冻结 Angular production（1,193 个文件，入口 `main-PZGEMKYC.js`），Chrome `158.0.8127.37` | 同一模板的运行时升级版、同一隔离库及同一客户端 |

.NET 9 已于 2026-11-10 结束支持，`9.0.23` 为末版。源端使用自己实际运行的补丁建立隔离基线，表中的 `9.0.10` 用于辨认历史证据。2026-11-26 核对的目标为支持中的两套 `10.0.15`。部署准备时重新检查服务版本，以两入口实际加载为准。源或目标的补丁、包图、Provider、系统或 Angular 组合有差异时，从自己的隔离备份重跑受影响路径。Windows、Linux 原生完整消费者及其他 Provider 仍待对应组合验收。[官方支持周期](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core) · [本轮复核和待验组合](r5-runtime-migration-review.md) · [公开包摘要](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json)

## 修改并构建两代源码

保留正在部署的 `net9.0` 源码副本。在另一个副本里，按项目引用图更新两入口及其可达项目。固定模板的 `AbpCompanyName.AbpProjectName.` 前缀可换成自己的项目名称。共享版本写在 `Directory.Packages.props` 或 `Directory.Build.props` 的应用，在相应定义处更新。

| 工程 | TFM | 直接 NuGet 引用 |
| --- | --- | --- |
| Core | `net9.0 → net10.0` | 保留 `Du.Abp.ZeroCore.EntityFrameworkCore`、`Du.Abp.AutoMapper` |
| Application | `net9.0 → net10.0` | 保留直接包引用 |
| EntityFrameworkCore | `net9.0 → net10.0` | `Microsoft.EntityFrameworkCore.SqlServer`、`Microsoft.EntityFrameworkCore.Design`、`Microsoft.EntityFrameworkCore.Tools` 从 `9.0.5` 改为 `10.0.15` |
| Web.Core | `net9.0 → net10.0` | `Microsoft.AspNetCore.Authentication.JwtBearer` 从 `9.0.5` 改为 `10.0.15`，保留三个 `Du.Abp*` 引用 |
| Web.Host | `net9.0 → net10.0` | `Microsoft.EntityFrameworkCore.Design` 从 `9.0.5` 改为 `10.0.15`，保留 `Du.Abp.Castle.Log4Net` |
| Migrator | `net9.0 → net10.0` | 保留 `Du.Abp.Castle.Log4Net` |

R4 维护包引用使用已发布版本，示例为精确 `[10.5.1]`。保留 `ProjectReference`、`PrivateAssets` 和 `IncludeAssets`。派生应用以自己的直接引用、锁文件、实际传递图及 Provider 兼容性决定额外调整。保留源端锁文件，目标端如需更新锁文件，审查变更后用 `--locked-mode` 确认可重复还原。[固定模板变更](r3-template-net10-upgrade.md#重放两份补丁) · [NuGet PackageReference](https://learn.microsoft.com/en-us/nuget/consume-packages/package-references-in-project-files)

在 Bash 中运行下面的构建。将三个路径或名称变量改为应用中真实存在的值，两个根目录应指向各代包含 `src/` 的独立源码副本。模板示例用 `global.json` 选择 SDK `10.0.404`。已有该文件的应用，先核对所选 SDK 能构建两个目标，再按应用约定保留各代文件。应用另有私有依赖时，按实际包源和图单独登记其验证输入。

```bash
set -euo pipefail
source_net9=/path/to/application-net9/aspnet-core
source_net10=/path/to/application-net10/aspnet-core
prefix=AbpCompanyName.AbpProjectName
work="$(mktemp -d "${TMPDIR:-/tmp}/du-r4-migration.XXXXXXXX")"
cat > "$work/NuGet.Config" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
  </packageSources>
  <fallbackPackageFolders><clear /></fallbackPackageFolders>
</configuration>
XML

build_release() (
  root=$1
  tfm=$2
  cd "$root"
  export NUGET_PACKAGES="$work/$tfm/packages"
  export NUGET_HTTP_CACHE_PATH="$work/$tfm/http-cache"
  export NUGET_PLUGINS_CACHE_PATH="$work/$tfm/plugins-cache"
  export NUGET_SCRATCH="$work/$tfm/scratch"
  mkdir -p "$NUGET_PACKAGES" "$NUGET_HTTP_CACHE_PATH" "$NUGET_PLUGINS_CACHE_PATH" "$NUGET_SCRATCH"
  dotnet --version
  for entry in Migrator Web.Host; do
    name="$prefix.$entry"
    project="src/$name/$name.csproj"
    dotnet restore "$project" --configfile "$work/NuGet.Config" \
      --source https://api.nuget.org/v3/index.json --packages "$NUGET_PACKAGES" \
      --no-http-cache --force -p:Configuration=Release \
      -p:RestoreAdditionalProjectSources= -p:RestoreFallbackFolders= \
      -p:RestoreAdditionalProjectFallbackFolders= -p:DisableImplicitNuGetFallbackFolder=true
    dotnet build "$project" --configuration Release --no-restore
    cp "src/$name/obj/project.assets.json" "$work/$tfm/$entry.project.assets.json"
    test -f "src/$name/bin/Release/$tfm/$name.dll"
  done
)

build_release "$source_net9" net9.0
build_release "$source_net10" net10.0
printf 'Evidence directory: %s\n' "$work"
```

在每入口的 `project.assets.json` 用 `targets[TFM]` 的包节点检查实际版本，包含直接、传递依赖及选中资产。核对全局缓存中维护包的 `.nupkg.metadata` 来源和 `.nupkg` SHA-256 与公开清单一致。保存两代各入口的整个 Release 目录和其中的 `.deps.json`、`.runtimeconfig.json`。只换共享运行时补丁时，先对照相应的四张 R4 包图，核对包 ID、解析版本、依赖边及资产项，各入口的 EF Core 和 Provider 仍按其自己的包图认定。[R4 四图和提取方法](r5-first-maintenance-review.md#固定模板的还原图) · [公开清单](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json)

## 恢复到隔离库并建立源端基线

以下 SQL 在测试实例的 `master` 执行。可用 SSMS 的查询窗口或安装了 `sqlcmd` 后用 `sqlcmd -b -S <测试实例> -d master -i <脚本文件>`。将备份放在 SQL Server 服务可读的位置，先用 `RESTORE HEADERONLY` 确认来源、备份集和 `Position`，用 `RESTORE FILELISTONLY` 取得逻辑文件名。若备份做了加密，先在隔离实例准备恢复所需的证书和密钥。按备份本身的文件布局填写每个 `MOVE`，数据文件和日志应使用新的物理路径。对每个租户独立库也完成隔离恢复，在测试库中改用对应的隔离连接，再放行 Migrator。[SQL Server 恢复到新位置](https://learn.microsoft.com/sql/relational-databases/backup-restore/restore-a-database-to-a-new-location-sql-server) · [sqlcmd 安装](https://learn.microsoft.com/sql/tools/sqlcmd/sqlcmd-download-install)

```sql
RESTORE HEADERONLY FROM DISK = N'/backup/application-full.bak';
RESTORE FILELISTONLY FROM DISK = N'/backup/application-full.bak' WITH FILE = 1;
GO
IF DB_ID(N'DuR4UpgradeCheck') IS NOT NULL
    THROW 50000, 'Choose an unused test database name.', 1;

RESTORE DATABASE [DuR4UpgradeCheck] FROM DISK = N'/backup/application-full.bak'
WITH FILE = 1,
     MOVE N'ApplicationData' TO N'/data/DuR4UpgradeCheck.mdf',
     MOVE N'ApplicationLog' TO N'/data/DuR4UpgradeCheck_log.ldf',
     RECOVERY;
GO
USE [DuR4UpgradeCheck];
GO
SELECT CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')) AS ServerName,
       DB_NAME() AS DatabaseName;
```

### 在迁移或登录前核对连接

固定模板的 Web.Host 在 `Development` 会把 User Secrets 加在环境变量之后，同名条目可以覆盖 `ConnectionStrings__Default`。Migrator 读取自己的 Release 目录配置，默认不加载 User Secrets。下例沿用 R4 实测的 `Development`。每次启动都创建一个空目录，并仅在子进程中把 `APPDATA` 指向该目录。所用 .NET 的 User Secrets 读取规则优先采用该目录，进程继承的同名配置也由 `env -i` 清除。派生应用在运行前从自身入口复核有效配置和连接解析器，并核对外部服务与后台任务的测试配置。[模板 Web.Core 配置入口](https://github.com/dusdong/module-zero-core-template/blob/2e9536872673a7ff1986a19e798c51684d16afe5/aspnet-core/src/AbpCompanyName.AbpProjectName.Web.Core/Configuration/HostingEnvironmentExtensions.cs) · [模板配置顺序](https://github.com/dusdong/module-zero-core-template/blob/2e9536872673a7ff1986a19e798c51684d16afe5/aspnet-core/src/AbpCompanyName.AbpProjectName.Core/Configuration/AppConfigurations.cs) · [.NET User Secrets 目录规则](https://github.com/dotnet/runtime/blob/v10.0.15/src/libraries/Microsoft.Extensions.Configuration.UserSecrets/src/PathHelper.cs) · [验收环境对照](r5-runtime-migration-review.md#本轮复验命令与范围)

示例使用监听环回的隔离 SQL Server、仅能访问该测试库且具备迁移所需权限的 SQL 登录，以及只用一个数据库的模板。用管理连接执行上面的实例和库名查询，将独立读出的实例名和测试库名填入下面变量。以下 Bash 示例每次用同一测试账号通过 `sqlcmd` 查询实例和库名，再按同一服务器地址、库名、登录构造应用连接。已有其他 SQL 客户端时，可执行同一只读查询并在启动前核对结果。示例对环回测试实例启用加密并信任其证书，派生部署按自身证书策略配置。若恢复库保存了租户独立连接，示例会在启动前停止。此类应用须先还原每个目标库，核对并改写恢复库中的租户连接，再按实际解析器逐一证明连接只可达对应测试库。[sqlcmd 参数](https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-utility)

```bash
r4_sql_address=tcp:127.0.0.1,1433
r4_sql_database=DuR4UpgradeCheck
r4_sql_instance='替换为恢复后查询读出的 ServerName'
set +x
read -r -p 'Test SQL login: ' r4_sql_login
read -r -s -p 'Test SQL password: ' r4_sql_password
printf '\n'

run_entry() (
  root=$1
  tfm=$2
  entry=$3
  shift 3
  name="$prefix.$entry"
  : "${r4_sql_instance:?}" "${r4_sql_database:?}" "${r4_sql_login:?}" "${r4_sql_password:?}"
  r4_sql_result="$work/$tfm/$entry.sql-preflight.log"
  if ! env -i PATH="$PATH" /bin/bash --noprofile --norc -c '
      IFS= read -r SQLCMDPASSWORD <&3 || exit 1
      exec 3<&-
      export SQLCMDPASSWORD
      exec sqlcmd "$@"
    ' r4-sql-check -b -C -h -1 -W -o "$r4_sql_result" \
      -S "$r4_sql_address" -d "$r4_sql_database" -U "$r4_sql_login" -Q "
SET NOCOUNT ON;
IF EXISTS (SELECT 1 FROM dbo.AbpTenants WHERE IsDeleted = 0 AND DATALENGTH(ConnectionString) > 0)
    THROW 50001, 'Review isolated tenant database routes before starting.', 1;
SELECT CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')) + N'|' + DB_NAME();" \
      3<<<"$r4_sql_password" >/dev/null; then
    printf '隔离库预检失败，应用尚未启动。结果文件：%s\n' "$r4_sql_result" >&2
    exit 1
  fi
  observed="$(cat "$r4_sql_result")"
  if [ "${observed%$'\r'}" != "$r4_sql_instance|$r4_sql_database" ]; then
    printf '%s\n' '实际 SQL 实例或库名与恢复记录不符，应用尚未启动。' >&2
    exit 1
  fi
  printf '已核对隔离目标 %s / %s\n' "$r4_sql_instance" "$r4_sql_database"
  r4_connection="Server=\"${r4_sql_address//\"/\"\"}\";Database=\"${r4_sql_database//\"/\"\"}\";User ID=\"${r4_sql_login//\"/\"\"}\";Password=\"${r4_sql_password//\"/\"\"}\";Encrypt=True;TrustServerCertificate=True"
  cd "$root/src/$name/bin/Release/$tfm"
  r4_user_config="$(mktemp -d "$work/runtime-user-config.XXXXXXXX")"
  env -i PATH="$PATH" APPDATA="$r4_user_config" \
    DOTNET_ENVIRONMENT=Development ASPNETCORE_ENVIRONMENT=Development \
    Kestrel__Endpoints__Http__Url=http://127.0.0.1:5008 \
    App__ServerRootAddress=http://127.0.0.1:5008/ \
    App__ClientRootAddress=http://127.0.0.1:4200/ App__CorsOrigins=http://127.0.0.1:4200 \
    COREHOST_TRACE=1 COREHOST_TRACEFILE="$work/$tfm/$entry.hostfxr.log" \
    DOTNET_HOST_TRACE=1 DOTNET_HOST_TRACEFILE="$work/$tfm/$entry.hostfxr.log" \
    /bin/bash --noprofile --norc -c '
      IFS= read -r ConnectionStrings__Default <&3 || exit 1
      exec 3<&-
      export ConnectionStrings__Default
      exec dotnet "$@"
    ' r4-entry "$name.dll" "$@" 3<<<"$r4_connection"
)

run_entry "$source_net9" net9.0 Migrator -q
```

固定模板的 Migrator 用 `-q` 无交互运行，成功退出 0。确认迁移日志与实际 SQL 连接都落在隔离库。用应用的连接诊断或 SQL Server Extended Events 记录两代 Migrator 及处理验收请求的 Host 所用实例、数据库和会话，将其与各阶段进程与请求关联。固定模板单库的对账查询如下，按实际租户 ID、已知记录 ID 改写参数。初始、源迁移后、目标迁移后的快照都保留。

```sql
USE [DuR4UpgradeCheck];
GO
SELECT CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')) AS ServerName,
       CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) AS ProductVersion,
       DB_NAME() AS DatabaseName;
SELECT [MigrationId], [ProductVersion] FROM dbo.__EFMigrationsHistory ORDER BY [MigrationId];
DECLARE @TenantId int = 1, @RecordId bigint = 3;
SELECT Id, TenancyName FROM dbo.AbpTenants WHERE Id = @TenantId;
SELECT Id, TenantId, UserName FROM dbo.AbpUsers WHERE TenantId = @TenantId AND Id = @RecordId;
```

用同一启动函数运行 Web.Host，通过隔离库预检后再打开浏览器。保留原客户端构建，只将 Angular production 副本的 `assets/appconfig.production.json` 中 `remoteServiceBaseUrl` 设为 `http://127.0.0.1:5008`，`appBaseUrl` 设为 `http://127.0.0.1:4200`。由应用现有的静态站点服务发布客户端，确保前端路由可回退到 `index.html`。如需使用别的空闲环回端口，同时修改启动函数和客户端配置。

```bash
run_entry "$source_net9" net9.0 Web.Host
```

在新浏览器会话选择测试租户并登录，记录登录账号、租户标识、所需权限、同一关键词请求、HTTP 状态、返回行数和一条已有业务记录的主键及稳定字段。固定模板从 `Session/GetCurrentLoginInformations` 核对身份，在 `/AbpUserConfiguration/GetAll` 查 `Pages.Users`，再从 Users 页按唯一用户名搜索。浏览器网络记录中的 `GET /api/services/app/User/GetAll` 应显示 `Keyword`、HTTP 200、`totalCount` 和记录 ID，页面也应显示对应用户名。证据只保留必要字段和请求标识，移除认证信息。[R4 公开同库实测](r4-release-candidate.md#公开源模板消费)

## 创建恢复点并用目标版回读

1. 停止源端 Host 和测试库写入，用下面的 SQL 保存升级前恢复点。选一个全新的备份文件，从 `RESTORE HEADERONLY` 记录本轮备份集 ID 与位置并计算文件 SHA-256。保留与之对应的源版 Release 目录和客户端。

   ```sql
   BACKUP DATABASE [DuR4UpgradeCheck]
   TO DISK = N'/backup/du-r4-before-upgrade.bak'
   WITH COPY_ONLY, CHECKSUM;
   RESTORE VERIFYONLY FROM DISK = N'/backup/du-r4-before-upgrade.bak'
   WITH FILE = 1, CHECKSUM;
   ```
2. 保持隔离连接不变，先运行目标 Migrator，再用目标 Host 重做同一租户的授权查询。按两轮存下的迁移 ID 与 `ProductVersion`、应用相关列、键、索引和外键逐项对账。若派生应用确有新迁移，将实际新增 ID、数据变化及结构变化与升级前预先审查的脚本对齐。目标 Migrator 失败，或有未预期的差异时先停在迁移阶段。

   ```bash
   run_entry "$source_net10" net10.0 Migrator -q
   run_entry "$source_net10" net10.0 Web.Host
   ```
3. 对照每次启动 trace 和该进程实际加载的程序集路径。可在迁移调用结束前和 Host 处理验收请求时，用应用内已有诊断或临时输出 `Environment.ProcessId` 及 `AppDomain.CurrentDomain.GetAssemblies()` 的程序集名和 `Location`，把证据绑定到本次 Release 进程。模板关注 `System.Private.CoreLib.dll`（.NET）、`Microsoft.AspNetCore.Hosting.dll`（Host）或 `Microsoft.AspNetCore.Identity.dll`（Migrator）、`Microsoft.EntityFrameworkCore.dll` 和 `Microsoft.EntityFrameworkCore.SqlServer.dll`。前两套按共享目录版本核对，EF Core 与 Provider 按各入口的包图、`.deps.json`、DLL 路径和摘要核对。记录目标 Host 处理的请求与实际查询库，检查相同租户、授权、关键词、主键和业务字段。[.NET 主机跟踪变量](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-environment-variables#dotnet_host_trace) · [历史 Migrator 核验实现](../../eng/r3_template_net10_runtime.py)
4. 停止目标 Host 和测试库写入，用另一个新文件名保存升级后备份及其摘要。将升级前后两份备份分别恢复到两个新库及物理路径，核对各自的迁移记录、租户与业务记录。升级前备份对应源版，升级后备份对应目标版。恢复到升级前会舍弃该恢复点之后的全部写入。另一种仅切回旧应用产物的路径，须先在升级后库副本验证旧应用与当前 schema 和数据。R4 中已实际分别恢复两点，升级前读回成功登录行 `1, 2`，升级后读回 `1, 2, 3`，回到升级前会丢失行 `3`。用自己的写入对账决定恢复点。验证完成后退出测试 Host，在当前 Bash 会话执行 `unset r4_sql_login r4_sql_password`。

## 当前证据

2026-11-26 的 R4 公开源实测中，两代两入口均退出 0。同一隔离库保留 30 条迁移 ID 和 `ProductVersion`，两个全新浏览器会话在 `Default` 租户获得 `Pages.Users`，相同关键词查询均返回 HTTP 200、总数 1、用户 ID `3`。本轮复核了固定组合的历史同库结果。指引沿用该 Development 组合，使用单独的 User Secrets 目录隔离配置。本轮实跑了 SQL 预检并核对四个入口的连接配置。业务回读及恢复点引用原 R4 实测。消费者以自己的数据、项目和部署建立独立的同库业务证据。[原报告、摘要与本轮核对](r5-runtime-migration-review.md#公开发行和历史证据) · [原版应用、冻结源回退实测](r3-original-template-rollback.md#正式运行结果)
