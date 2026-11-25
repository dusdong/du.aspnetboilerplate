# R3 模板 net9.0 换包验收

2026-11-25，固定模板更换 13 个维护包后通过完整对照。Web.Host 和独立 Migrator 从空 NuGet 缓存还原，在 macOS ARM64、.NET 9.0.10、SQL Server 16.0.4236.2 Developer 和原版 Angular production 产物上完成租户登录、授权和用户查询。[原版构建基线](r3-web-host-baseline.md) · [原版运行恢复点](r3-template-runtime-baseline.md#交接数据恢复点)

## 固定输入与复跑

主仓从 `148bda55d9fea121a66fa2445388fb0cf552643b` 接续，模板固定在 `2e9536872673a7ff1986a19e798c51684d16afe5`。原件根目录按[冻结登记](../../eng/r3_template_net9_reference.json)布局，保留 13 个主包、5 份生产清单和原版返修轮 6 份还原资产的登记路径与字节。验证机本地原件根为主仓的 `.git/`。移动原件时可改用新根目录。还原访问 nuget.org，运行目录须能容纳源码、独立包缓存和产物，首次成功约占 1 GB。以下入口只执行还原和构建，成功状态为 `build_verified`。

~~~sh
R3_FROZEN_ROOT="$PWD/.git"
R3_BUILD_EVIDENCE="$PWD/.git/r3-template-net9-packages/local-builds"
python3 -B eng/verify.py --profile r3-template-net9-packages \
  --frozen-root "$R3_FROZEN_ROOT" --evidence-root "$R3_BUILD_EVIDENCE"
~~~

默认使用 PATH 中的 ARM64 `dotnet`，也可传 `--dotnet` 指定可执行文件。隔离目录的 `global.json` 固定构建 SDK，使用空的全局包缓存、HTTP 缓存及插件缓存。精确包 ID 映射优先将 13 个维护包限制在当轮受控源，nuget.org 供其余依赖使用。各项目资产的有效配置、来源、缓存内容摘要和归档摘要与实际缓存和日志核对。验收结束再次核对原件、受控源副本及原版比较证据的 37 个文件摘要。[验证入口](../../eng/r3_template_net9_packages.py)

每次复跑按固定 Git blob 对四个项目应用七处引用替换，保留项目拓扑和声明元数据，并输出 `template-package-references.patch`。如需单独重放，在主仓运行下列命令，随后可在隔离副本审查差异。`R3_BUILD_RUN` 为一次候选构建目录，`R3_TEMPLATE_REPLAY` 为独立源码目录。

~~~sh
mkdir -p "$R3_TEMPLATE_REPLAY"
git -C module-zero-core-template archive \
  2e9536872673a7ff1986a19e798c51684d16afe5 aspnet-core | tar -xf - -C "$R3_TEMPLATE_REPLAY"
git -C "$R3_TEMPLATE_REPLAY" apply --no-index --check "$R3_BUILD_RUN/template-package-references.patch"
git -C "$R3_TEMPLATE_REPLAY" apply --no-index "$R3_BUILD_RUN/template-package-references.patch"
~~~

| 来源批次 | 冻结版本及包 |
| --- | --- |
| [R2 核心](r2-core-package-consumption.md#源码与产物) | `10.5.1-r2.1` 的 `Du.Abp`、`Du.Abp.Web.Common`、`Du.Abp.AspNetCore`、`Du.Abp.EntityFramework.Common`、`Du.Abp.EntityFrameworkCore` |
| [R3 集成组件](r3-signalr-log4net-candidates.md#用已锁定实物复验消费) | `10.5.1-r3.1` 的 `Du.Abp.AspNetCore.SignalR`、`Du.Abp.Castle.Log4Net` |
| [R3 Module Zero](r3-module-zero-candidates.md#复跑冻结批次) | `10.5.1-r3.3` 的 `Du.Abp.Zero.Common`、`Du.Abp.ZeroCore`、`Du.Abp.ZeroCore.EntityFrameworkCore` |
| [R3 映射](r3-automapper-downstream.md#冻结产物) | `Du.Abp.AutoMapper 10.5.1-r3.4`、`Du.AutoMapper 14.0.0-r3.4`、`Du.AutoMapper.Collection 11.0.0-r3.4` |

## 实际包图与构建输出

| 项目后缀 | 直接项目引用 | 直接维护包 | 应用包数 | 维护包数 |
| --- | --- | --- | ---: | ---: |
| Web.Host | Web.Core | `Du.Abp.Castle.Log4Net` | 116 | 13 |
| Web.Core | Application、EntityFrameworkCore | `Du.Abp.AspNetCore`、`Du.Abp.ZeroCore`、`Du.Abp.AspNetCore.SignalR` | 97 | 12 |
| Application | Core | | 48 | 9 |
| EntityFrameworkCore | Core | | 100 | 9 |
| Core | | `Du.Abp.AutoMapper`、`Du.Abp.ZeroCore.EntityFrameworkCore` | 48 | 9 |
| Migrator | Core、EntityFrameworkCore | `Du.Abp.Castle.Log4Net` | 81 | 10 |

每个项目保存实际 `project.assets.json`、项目与包边、SDK pack、C# 编译引用及其路径和摘要。构建前后资产摘要一致。两入口的 SDK apphost 和六项目的目标参考包均为 `9.0.23`。产物 `.runtimeconfig.json` 中的两个共享框架起始版本均为 `9.0.0`，实际运行时补丁版本由业务进程验证。

Web.Host 的 `.deps.json` 与实际复制对应 168 个 NuGet 运行文件和 4 份项目引用 DLL，另有 321 项标记为 `compileOnly` 的库条目。Migrator 分别对应 70 个 NuGet 运行文件和 2 份项目引用 DLL。有 19 个还原包未进入 Migrator 的 `.deps.json`，输出核验记录了 SDK 选用的共享框架参考和从运行复制项剔除的托管 RID 候选。两个入口的维护框架 DLL 均来自 `lib/net9.0/`，两份映射包 DLL 均来自 `lib/net8.0/`。各输出清单分别关联 NuGet 包、目录、归档内路径和 SHA-256。

| 依赖 | 原版解析 | 候选解析及来源 |
| --- | --- | --- |
| EF Core、Abstractions、Relational | `9.0.5` | `9.0.18`，由 R2 EF Core 依赖链引入 |
| SQL Server Provider | `9.0.5` | `9.0.5`，沿用 EntityFrameworkCore 项目直接声明。Host 与 Migrator 均从 `lib/net8.0/` 复制，DLL 与原版同摘要 |
| EF Design、Tools | `9.0.5` | `9.0.5`，保留私有引用。Design 见于 EntityFrameworkCore 与 Web.Host，Tools 仅见于 EntityFrameworkCore |
| JwtBearer | `9.0.5` | `9.0.5`，由 Web.Core 声明 |
| MVC NewtonsoftJson、Razor RuntimeCompilation | `9.0.5` | `9.0.18`，由 R2 `Du.Abp.AspNetCore` 引入 |
| SqlClient、SNI | `5.1.6`、`5.1.1` | 同版，仍由 SQL Server Provider 依赖链引入 |
| AutoMapper、Collection | `14.0.0`、`11.0.0` | `Du.AutoMapper 14.0.0-r3.4`、`Du.AutoMapper.Collection 11.0.0-r3.4`，由冻结适配器精确引用 |
| log4net | `3.1.0` | `3.3.2`，由 `Du.Abp.Castle.Log4Net` 引入 |

完整 `third-party-differences.json` 逐项目记录已解析版本和边的变化，包括提交该需求的包或项目。七处维护包引用以外的模板声明均与原版相同。组合的还原和构建未出现包降级。

## 构建实测证据

只构建通过轮位于验证机 `.git/r3-template-net9-packages/package-1/runs/r3-template-net9-packages-lnux1wk3/`。`report.json` 保存实际还原、构建和 MSBuild 查询的命令、工作目录、退出码及日志。两次还原各退出 0，均为 0 警告、0 错误。两次 Release 构建各退出 0，Web.Host 的 307 条警告与原版构建的四类 C# 诊断一致，随后构建的 Migrator 为 0 警告、0 错误。`launch-manifest.json` 保存两个 Release 目录、入口 DLL 的待启动参数及各自输出清单。

| 证据 | SHA-256 |
| --- | --- |
| `report.json` | `c3dc2393e1c581dcbdbf0ba27852f15c5c5ec0af31dd54d2f1c592f4db40d6eb` |
| `frozen-packages.json` | `e43a849df0c5102e4920954e30fc3359c2e4bacca8b095ba0ba0480983befed0` |
| `template-package-references.patch` | `5c4635ff40973edb0b278b67538d5560128cfdc438682397e115fce8285930b5` |
| `launch-manifest.json` | `2d1579616729580f296baef2b93bd040d5a44292e35e96892518e295f54b6462` |
| `Web.Host-output.json` | `9a4ae3b028f4e10bdd6a21219f8ab964b6bcbdf2cd372b8d547935bc0086bc3b` |
| `Migrator-output.json` | `c41c97dd1da2364d82a74b7534b25560364abfd0a12cba3848325a0068b2a567` |

`package-1/runs/` 保留首次还原后资产规则仍要求原版单包源的失败、补丁末尾换行的重放失败及各自修复后的通过轮。`package-1/debug-from-first-restore/` 保留编译项目引用、传递 SDK pack 与 Migrator 托管 RID 冲突选择的早期诊断。

~~~sh
python3 -B eng/tests/verify_r3_template_net9_packages.py \
  "$R3_BUILD_RUN" "$R3_DIAGNOSTIC_EVIDENCE" "$R3_FROZEN_ROOT"
~~~

定向入口使用独立副本运行三条诊断。缺少 `Du.Abp.10.5.1-r2.1.nupkg` 与同版本归档摘要错误均经真实 profile 在 `packages` 阶段退出 1。将 Core 资产副本的传递核心包换成 `Abp/10.2.0` 的夹具在 `assets` 阶段退出 1。原始命令与诊断在 `package-1/candidate-diagnostics/`。

## 运行复验

使用专用环回 SQL Server、Python 环境中的 `pymssql` 和 Playwright，以及可执行的 Chrome 或 Playwright Chromium。原版手册列出无凭据 JSON 配置字段、SQL Server 备份读取和恢复权限，以及 `R3_TEMPLATE_SQL_USER`、`R3_TEMPLATE_SQL_PASSWORD`、`R3_TEMPLATE_TENANT_PASSWORD` 三个环境变量。换包入口从返修轮现有备份恢复新库。测试账号还需能读取恢复后的库，并供 Migrator 和 Host 连接。已禁用的原版验收账号应保留历史状态。[运行环境和凭据](r3-template-runtime-baseline.md#复跑)

按返修轮路径在 `R3_FROZEN_ROOT` 下保留 `report.json`、`angular-production-files.json`、实际 Angular production 输出及备份。让 `localBackupDirectory` 和 `sqlBackupDirectory` 访问同一份 `r3_template_cf4314cdfe038c35.bak`。本地摘要为 `93da0a5ceb9fd98821aa654fedcd13cc91c53ca25cb41f845115a7f05f81d988`，服务端备份集为 `4311036b-9b8a-43f5-944c-5d549e4fed08`。使用容器时可将核对后的副本映射到容器，恢复出的数据和日志各用新的物理路径。默认沿用原版 Host `14436` 和 Angular `14236`。端口变更时，仅在本轮前端副本改写两个地址，报告源与服务目录的摘要、实际入口脚本和 CORS。[固定恢复点](r3-template-runtime-baseline.md#交接数据恢复点)

~~~sh
python -B eng/verify.py --profile r3-template-net9-packages-runtime \
  --frozen-root "$R3_FROZEN_ROOT" --runtime-config "$R3_RUNTIME_CONFIG" \
  --evidence-root "$R3_RUNTIME_EVIDENCE"
~~~

全流程从干净模板还原并构建，核对 1,193 个冻结 Angular 文件。它验证 SQL 实例、备份标头和校验和，在两个新库中读回 30 条迁移及既有租户、账号、授权和用户记录。Migrator 的 .NET 启动观测器从 EF Core 迁移命令即将执行的 SQL 连接读回实例名、`DB_NAME()`、会话和连接标识，关联实际进程。迁移出口、连接证据、迁移前后状态通过后，再在 Release Host 的 `Development` 环境中执行真实业务。Host 启动观测器记录实际加载的程序集身份、上下文、位置和摘要。两个共享框架的启动选择和实际加载路径都必须对应 `9.0.10`。浏览器提交登录前两库计数须为 `1/1`，搜索后须为 `2/1`。

`report.json` 中 `status=passed` 表示完整入口通过。`migrator-target.jsonl` 保留迁移连接读数，`host-loaded.json` 保留同一 Host 的运行观测，`host-loaded-verification.json` 将其关联归档和输出。`candidate-round.json` 保留浏览器的请求、业务字段、表格及两库计数。`original-candidate-comparison.json` 保存原版及候选的实际组合和业务对照。

## 正式运行结果

完整候选轮 `r3-template-net9-packages-runtime-a8smhbra` 退出 0。其正式报告 SHA-256 为 `349da1e3b84ff8d821c740cd7b4a26ec27ec7f176d5cc6d3cd1dcada72745a19`。验收要求及当时的实施方案见[稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md)和[归档制品](../../openspec/changes/archive/2026-11-25-validate-r3-net9-template-package-migration/)。

环境为 macOS ARM64、SDK `10.0.404`、SQL Server `16.0.4236.2` Developer 和 Chrome `158.0.8127.37`。候选 Migrator PID `51063` 在同一候选库观察到三条迁移命令连接，PID `51143` 提供实际浏览器请求。Angular 1,193 个文件均与冻结原件字节一致，实际入口脚本为 `main-PZGEMKYC.js`。

| 核对项 | 原版返修轮 | 维护包正式轮 |
| --- | --- | --- |
| .NET 与 ASP.NET Core 共享运行时 | 两者均为 `9.0.10` | 两者均为 `9.0.10` |
| 框架与映射 | 11 个原版 ABP 包 `10.2.0`，解析 AutoMapper `14.0.0`、Collection `11.0.0` | Host 实际加载全部 11 个维护 ABP DLL、唯一维护 AutoMapper 引擎。Collection 来自已核对的维护包输出，本场景未加载 |
| SQL 运行链 | Provider 和 EF Core、Abstractions、Relational `9.0.5`，SqlClient `5.1.6` | 实际加载 Provider `9.0.5`，EF Core、Abstractions、Relational `9.0.18`，SqlClient Unix 资产 `5.1.6` |
| 恢复点与业务身份 | 30 条迁移，`Default` ID `1`，账号 `2`，`Pages.Users` | 候选库与对照库的迁移前后均匹配原版恢复点 |
| 实际关键词请求及页面 | HTTP 200，`totalCount=1`，唯一用户 `3`，用户名 `r3usercf4314cdfe038c35` | 相同请求关键字段、结果与唯一用户名单元格 |
| 当轮业务写入 | 恢复库 `1 → 2`，同期源库 `2 → 2` | 候选库 `1 → 2`，独立对照库 `1 → 1` |

真实负例在独立诊断库确认旧备份和已占用目标在恢复前被拒绝。即使 Migrator 退出 0 且两库原有 30 条迁移，实际连到对照库和缺连接证据都在启动 Host 前退出 1。登录起点 `1/2` 时停止提交。浏览器查询成功但写入对照库时，入口按实测 `1/1 → 1/2` 退出 1。运行时补丁偏离、来源或摘要冲突、重复引擎和缺失记录使用正式轮证据副本测试。完整候选入口、原版完整入口、定向诊断以及 OpenSpec 严格校验通过。

首次错连诊断复制了已经运行的 Migrator 目录，新增的日志文件触发输出清单断言。修正后按构建清单复制文件，并将模板声明的 Log4Net 文件输出导向 `/dev/null`，保留脱敏控制台日志。原版入口的一次并行复验在等待 Angular 页面与应用配置时超时，串行从干净目录重新执行后完成两轮业务，退出 0。正式候选与原版复验的 Host、Migrator 和前端均已退出，新建的专用 SQL Server 容器已清理，环回端口均已释放。

~~~sh
python -B eng/tests/verify_r3_template_net9_runtime.py \
  "$R3_PASSED_RUN" "$R3_DIAGNOSTIC_EVIDENCE" "$R3_FROZEN_ROOT" "$R3_RUNTIME_CONFIG" \
  --early-backup r3_template_95542a4a796773ee.bak
python -B -m unittest discover -s eng/tests -v
openspec-cn validate --all --strict --no-interactive
~~~

复跑诊断需在该专用 SQL 实例的映射目录额外准备早期备份，`R3_PASSED_RUN` 指向完整通过轮，诊断使用独立的数据库路径。

完整报告及对应原版回归、首错和负例的证据副本在验证机 `.git/r3-template-net9-packages/package-2/records/`，由 `evidence-index.json` 登记来源和摘要。诊断复用通过轮的实际 DLL，并读取报告内的原绝对路径。历史通过轮可从 `.git/r3-template-net9-packages/package-2/execution/candidate/r3-template-net9-packages-runtime-a8smhbra/` 定位。原路径失效时，按验证机 `.git/r3-template-net9-packages/closeout/交接.md` 恢复完整运行树至原路径，或以本页的[运行复验](#运行复验)重新取得通过轮。

结果只覆盖登记的 macOS ARM64、.NET 9、SQL Server 与 Angular 组合。.NET 10、迁移后回退及公开发包各有后续验收。
