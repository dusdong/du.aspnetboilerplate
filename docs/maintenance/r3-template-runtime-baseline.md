# R3 原版模板运行对照

原版对照从固定模板构建 `net9.0` Release Web.Host、独立 Migrator 和 Angular production 客户端。它在同一台专用 SQL Server 上创建两个不同的库，保存首次验收登录前的备份。两轮各用独立浏览器上下文，通过同一前端产物选择租户、登录并查询用户。原版依赖的首次构建记录见 [R3 Web.Host 基线](r3-web-host-baseline.md)。

## 复跑

在 macOS ARM64 主仓根目录运行。构建需要 SDK `10.0.404`、固定模板 Git 对象 `2e9536872673a7ff1986a19e798c51684d16afe5`、可访问锁文件中的包源、Node.js 22、Yarn Classic 1.22 和 Python 3.10 以上。后续运行使用 .NET 9 共享运行时、`pymssql` 和 Playwright。使用本机已安装 Chromium/Chrome 时，在配置中指定其可执行文件。若使用 Playwright 的 Chromium，先运行 `python -m playwright install chromium`。

```sh
python -m pip install 'pymssql==2.3.13' 'playwright==1.59.0'
```

准备只用于本轮测试的环回 Linux SQL Server 实例，在配置中明确登记该实例名。服务端版本和版别随报告保存。给连接账号授予创建源库和恢复新库所需的权限，例如在 `master` 中授予 `CREATE DATABASE`。该权限也用于读取和验证备份介质。连接账号在它新建的源库中须具备 `BACKUP DATABASE`，预检在调用 Migrator 前实测该权限。恢复证据来自备份标头、实际恢复命令、恢复库自己的文件与业务记录。[SQL Server RESTORE 权限](https://learn.microsoft.com/en-us/sql/t-sql/statements/restore-statements-transact-sql?view=sql-server-ver16#permissions) · [备份介质权限](https://learn.microsoft.com/en-us/sql/relational-databases/backup-restore/backup-history-and-header-information-sql-server?view=sql-server-ver16)

SQL Server 进程需能写入备份目录及实例的默认数据、日志目录。备份目录也须从运行机可读，以计算同一介质的 SHA-256。使用容器时可将专用本机目录映射到容器的备份目录。预检核对登记的实例名，只探测本轮随机生成的数据库和文件目标。已有目标库即使不可访问也会被拒绝。恢复使用新库名和新物理路径。[SQL Server 目标存在性判定](https://learn.microsoft.com/en-us/sql/t-sql/functions/has-dbaccess-transact-sql?view=sql-server-ver16)

把以下字段存入无凭据的 JSON 文件，按本机环境替换。如省略 `chrome`，使用 Playwright 的 Chromium。暂时只有 `hostPort`、`frontendPort` 时，入口仍会构建和核对 Web.Host、Migrator 及 Angular。缺少 SQL 配置、凭据、可读的本机备份目录或客户端时，`sql_preflight` 会报告缺项并返回非零，数据库和浏览器阶段保持未执行。

```json
{
  "sqlPort": 15436,
  "sqlServerName": "r3-template-sql-20261125",
  "sqlBackupDirectory": "/var/opt/mssql/r3-backup",
  "localBackupDirectory": "/absolute/path/to/r3-backup",
  "hostPort": 14436,
  "frontendPort": 14236,
  "chrome": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
}
```

通过现有凭据渠道把 `R3_TEMPLATE_SQL_USER`、`R3_TEMPLATE_SQL_PASSWORD`、`R3_TEMPLATE_TENANT_PASSWORD` 注入入口进程环境。最后一项对应固定模板的默认租户管理员种子。后端以每次运行专用的 `ConnectionStrings__Default` 环境值连接指定库。前端地址来自当轮输出中的 `assets/appconfig.production.json`，Host 的 `App__CorsOrigins` 指向该地址。Host 直接运行 Release DLL，以启动日志中的 `Development` 与共享框架路径为准。报告只登记认证请求路径、状态、用户标识及授权结果。阶段日志脱敏后留存。可将 `YARN_CACHE_FOLDER` 指向下载缓存，`node_modules` 仍从空目录按冻结锁文件重建。下载缓存缺失时，取消设置 `YARN_CACHE_FOLDER`，由入口在新运行目录从锁文件登记的包源重新下载。

```sh
python -B eng/verify.py --profile r3-template-runtime \
  --runtime-config "$R3_RUNTIME_CONFIG" --evidence-root "$R3_EVIDENCE_ROOT"
python -B -m unittest discover -s eng/tests -p test_r3_template_runtime.py -v
openspec-cn validate --all --strict --no-interactive
```

每次执行生成独立目录。入口先核对固定模板和后端资产，单独还原并构建 Migrator，运行 `yarn install --frozen-lockfile` 和 `yarn ng build --configuration production`。SQL 预检通过后运行 `Migrator -q` 并核对完整迁移历史、共享库租户和管理员种子。准备会话通过模板用户管理入口创建合成用户并退出。直连 SQL Server 核对唯一匹配记录后，执行带校验和的完整复制备份并验证备份介质。每轮浏览器先等待无关键词的初始列表，再核对本次搜索对应的请求、响应和用户名单元格。恢复轮在提交登录前分别对两库计数，登录后以相同条件复查。

从报告定位以下证据。

| 文件 | 内容 |
| --- | --- |
| `report.json` | 固定输入、工具版本、阶段、工作目录、实际命令与退出码、SQL 期望值、备份及资源释放 |
| `release-host-files.json`、`release-migrator-files.json`、`angular-production-files.json` | 各实际输出的逐文件 SHA-256 |
| `host-output.json`、`migrator.project.assets.json` | 原版 Host 运行资产和 Migrator 还原闭包 |
| `sql-commands.json` | 用于核对实例、迁移、备份、恢复及计数的脱敏 SQL 记录 |
| `source-round.json`、`restore-round.json` | 应用配置、租户选择、登录、会话、权限、搜索请求和结果，含恢复轮的两库计数 |

## 交接数据恢复点

同目标换包以最终返修轮为原版对照。报告和两轮结果位于 `.git/r3-template-runtime/revision-1/runs/r3-template-runtime-89igcw5r/`，接受的脚本与证据摘要见 `.git/r3-template-runtime/revision-1/candidate/manifest.json`。[最终返修验收](#2026-11-25-返修复验)

- 恢复 `.git/r3-template-runtime/sql-server/backup/r3_template_cf4314cdfe038c35.bak`。先按最终报告的 `sql.backup` 核对 SHA-256 和备份集 ID，再按同目录的 `sql-commands.json` 对照运行 `RESTORE VERIFYONLY`、`RESTORE FILELISTONLY` 和 `RESTORE DATABASE ... WITH CHECKSUM, RECOVERY, MOVE ...`，目标使用新的库名与物理文件。
- 沿用固定模板提交、Angular 锁文件及 production 客户端输入，保持 `net9.0` 与 Release Host 的 `Development` 环境。按最终报告的 `sql.expected` 和两轮结果，对比 30 条迁移、`Default` 租户 ID `1`、管理员 ID `2`、`Pages.Users` 及 `Keyword=r3usercf4314cdfe038c35` 对应的唯一用户 ID `3` 和用户名单元格。

源库、恢复库与备份路径留在本轮本地证据。独占的 SQL Server 由其操作者停止，Host 和 Angular 由入口释放。验收要求与当时的方案分别见[稳定规范](../../openspec/specs/template-runtime-baseline/spec.md)及[归档制品](../../openspec/changes/archive/2026-11-25-baseline-r3-original-template-runtime/)。

## 2026-11-25 本机验收

正式执行目录为 `.git/r3-template-runtime/runs/r3-template-runtime-tthrpdx7/`。入口退出 0。验收使用 macOS 27.2.1 ARM64（`26B131`）、SDK `10.0.404`、实际加载的 `Microsoft.NETCore.App` 与 `Microsoft.AspNetCore.App` `9.0.10`、Node.js `22.22.0`、Yarn Classic `1.22.22`、Playwright `1.59.0` 和 Chrome `158.0.8127.37`。SQL Server `16.0.4236.2` Developer 的 Linux x64 容器走环回端口 `15436`。Host 和前端分别绑定环回端口 `14436` 和 `14236`。

| 输入或输出 | 正式轮的身份 |
| --- | --- |
| 固定模板 | `2e9536872673a7ff1986a19e798c51684d16afe5` |
| Web.Host Release DLL SHA-256 | `44580a5528922c36fb38fa647e7898fc396ebb85089a04805522bce0b0826d4d`，11 个原版 ABP 包均为 `10.2.0`，SQL Server Provider 为 `9.0.5` |
| Migrator Release DLL SHA-256 | `bbeda3f3caf860059d4320466f1ced9f4921e21efed7a619af613deb4aaf89df` |
| Angular 锁文件 SHA-256 | `3e55c44022c5c15bf2c474eb483f8161945151261f06d00218fffbdb86c0d14f` |
| Angular production 输出清单摘要 | `59203802dd274be9c00c041d1529238d72bd7ddc914a8f84224fbd84923bce37` |

Migrator 退出 0，源库与恢复库读回相同的 30 条迁移历史。两轮均运行同一 Release Host，实际环境为 `Development`。浏览器分别读回 `Default` 租户 ID `1`、管理员 ID `2` 和 `Pages.Users` 权限。初始用户列表有 2 条，搜索请求 `Keyword=r3user95542a4a796773ee` 返回 HTTP 200、`totalCount=1` 和唯一的用户 ID `3`。页面唯一数据行的用户名单元格与搜索词精确相等，以下两轮的接口结果相同。

| 轮次 | 数据库 | 同一租户和账号的成功登录记录 |
| --- | --- | --- |
| 首轮 | `r3_template_95542a4a796773ee_source` | 1 → 2 |
| 恢复轮 | `r3_template_95542a4a796773ee_restore` | 1 → 2。同期源库 2 → 2 |

保留的登录前备份为 `.git/r3-template-runtime/sql-server/backup/r3_template_95542a4a796773ee.bak`，备份集 ID 为 `877e7510-7081-4512-89d3-3c7183e902f5`，SHA-256 为 `63fa0d65a124c3a9094d55b5eb01e008f8f1d3665b89a5767710ae4ac282d382`。备份采用 `COPY_ONLY, CHECKSUM`，恢复后的实例记录显示该备份集已完整还原至新库并为 `ONLINE`。

诊断轮与正式轮使用不同的数据库。真实错目标诊断验证了错误实例名及目标库已存在时只执行读取并拒绝后续写入。真实误连诊断让恢复轮仍访问诊断源库，即使浏览器搜索成功，登录记录显示源库增加 1、恢复库增加 0，该阶段仍报错。其余错误模板、锁文件漂移、缺少种子、错租户、初始列表替代搜索及缺少结果行使用定向夹具验证。首次执行受本机 Yarn 4 接管而停在版本检查。后续修正了宿主启动方法与构建清单属性的命名冲突、Angular 整页重载时的会话证据采集，以及原版权限响应使用字符串的解析。正式轮从新目录重建前后端，使用独立 NuGet 缓存和预热的 Yarn 下载缓存，`node_modules` 从空目录安装。诊断阶段与正式阶段分别留在 `.git/r3-template-runtime/`。

Host、Migrator 和前端均退出，专用 SQL Server 容器经 Docker 超时强制停止，容器退出码为 137。所有本轮端口均已释放，备份在停止后重新核对摘要。未执行同目标维护包换包、.NET 10 / EF Core 10 升级、升级后回退、其他运行组合、CI 或部署。

## 2026-11-25 返修复验

| 检查 | 实测结果 | 本机证据目录 |
| --- | --- | --- |
| 仅提供前后端端口 | Web.Host、Migrator 和冻结锁文件的 Angular production 均构建并核对通过。SQL 预检列出缺失的四个 SQL 配置字段和三个凭据环境变量，入口退出 1。迁移、数据库写入和浏览器阶段均未执行。 | `.git/r3-template-runtime/revision-1/runs/r3-template-runtime-dpgetdxe/` |
| 最小权限 SQL 正式轮 | 同一 macOS ARM64、SQL Server Developer `16.0.4236.2`、.NET 9 和 Chrome 组合。账号在 `master` 中有 `CREATE DATABASE`，无 `sysadmin`、`VIEW SERVER STATE` 或 `VIEW ANY DATABASE` 权限。源库建库后实测具备 `BACKUP DATABASE`。完整 18 阶段通过，入口退出 0。 | `.git/r3-template-runtime/revision-1/runs/r3-template-runtime-89igcw5r/` |
| 缺权和隐藏目标 | 真实缺权账号在 SQL 预检退出 1，只执行权限和实例身份的读取。具备建库权限的账号即使看不到已有源库的目录记录，仍通过按目标调用 `HAS_DBACCESS` 识别已有库并拒绝写入。 | `.git/r3-template-runtime/revision-1/diagnostics/` |

返修后的正式轮在两库读到同一组 30 条迁移。两轮的 `Keyword=r3usercf4314cdfe038c35` 均绑定 HTTP 200、`totalCount=1`、唯一用户 ID `3` 和页面用户名单元格。恢复轮同期源库登录计数为 2 → 2，恢复库为 1 → 2。

返修轮备份 `.git/r3-template-runtime/sql-server/backup/r3_template_cf4314cdfe038c35.bak` 已验证可恢复。备份集 ID 为 `4311036b-9b8a-43f5-944c-5d549e4fed08`，SHA-256 为 `93da0a5ceb9fd98821aa654fedcd13cc91c53ca25cb41f845115a7f05f81d988`。首版备份及原有两轮、误连和原始报告保留，按各自的脚本摘要关联。返修候选的两条入口使用同一组脚本摘要，构建基线清单均与首次 Web.Host 基线字节一致。

四个正式 .NET 进程退出码均为 0。返修测试账号在完成验证后禁用。专用 SQL Server 执行 `SHUTDOWN` 后容器停止，容器退出码为 255，运行端口均无监听。33 项 Python 测试与 OpenSpec 严格校验 9/9 通过。
