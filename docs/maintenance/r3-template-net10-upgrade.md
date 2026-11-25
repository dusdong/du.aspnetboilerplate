# R3 模板 .NET 10 升级复跑

固定模板为 `module-zero-core-template@2e9536872673a7ff1986a19e798c51684d16afe5`。升级从主仓 `a4ffcaa83a48bb8c7684264ca6aad0d82faf63ae` 接续，使用 .NET 9 对照已验收的 13 个维护包和 5 份生产清单。固定输入的相对路径和 SHA-256 见冻结登记。验证机的原件根目录是主仓的 `.git/`。[正式 .NET 9 对照](r3-template-net9-packages.md#正式运行结果) · [冻结登记](../../eng/r3_template_net9_reference.json)

升级验收要求已纳入稳定规范，提案、设计与已完成任务随变更归档。[稳定规范](../../openspec/specs/template-runtime-upgrade/spec.md) · [归档](../../openspec/changes/archive/2026-11-25-validate-r3-net10-template-runtime-upgrade/)

## 空缓存 Release 构建

从主仓根目录运行。构建入口使用 macOS ARM64 的 `dotnet`，从 PATH 查找，或通过 `--dotnet` 传入绝对路径。SDK 固定为 `10.0.404`。还原需要访问 nuget.org。为独立源码、NuGet 缓存和构建输出预留约 1 GiB。

~~~sh
R3_FROZEN_ROOT="$PWD/.git"
R3_BUILD_EVIDENCE="$PWD/.git/r3-template-net10-upgrade/local-builds"
python3 -B eng/verify.py --profile r3-template-net10-upgrade \
  --frozen-root "$R3_FROZEN_ROOT" --evidence-root "$R3_BUILD_EVIDENCE"
~~~

入口从固定提交展开 `aspnet-core/`，在独立空缓存中按两个入口强制还原。受控源用精确 ID 映射提供 13 个维护包，nuget.org 提供其余依赖。Web.Host 和 Migrator 均使用 `--no-restore` 构建 Release，并在各自的 `bin/Release/net10.0` 核对输出、`.deps.json` 和 `.runtimeconfig.json`。成功状态为 `build_verified`。共享运行时实际选择、SQL Server 迁移、浏览器业务和恢复点还原属于后续运行验收。[构建入口](../../eng/r3_template_net10_upgrade.py)

### 重放两份补丁

`R3_BUILD_RUN` 指向一次运行目录。此例在证据目录下创建独立源码副本。每份补丁先检查再应用，按同一顺序操作。

~~~sh
R3_TEMPLATE_REPLAY="$(mktemp -d "$R3_BUILD_EVIDENCE/patch-replay.XXXXXX")"
git -C module-zero-core-template archive --format=tar \
  --output="$R3_TEMPLATE_REPLAY/template-source.tar" \
  2e9536872673a7ff1986a19e798c51684d16afe5 aspnet-core
tar -xf "$R3_TEMPLATE_REPLAY/template-source.tar" -C "$R3_TEMPLATE_REPLAY"
git -C "$R3_TEMPLATE_REPLAY" apply --no-index --check "$R3_BUILD_RUN/template-package-references.patch" &&
  git -C "$R3_TEMPLATE_REPLAY" apply --no-index "$R3_BUILD_RUN/template-package-references.patch" &&
  git -C "$R3_TEMPLATE_REPLAY" apply --no-index --check "$R3_BUILD_RUN/template-runtime-upgrade.patch" &&
  git -C "$R3_TEMPLATE_REPLAY" apply --no-index "$R3_BUILD_RUN/template-runtime-upgrade.patch"
~~~

第一份补丁替换四个工程的七个框架包引用，固定维护包版本。第二份以换包后的源码为前像，将六个工程改为 `net10.0`，将 EntityFrameworkCore 的 SqlServer、Design、Tools，Web.Host 的 Design 及 Web.Core 的 JwtBearer 从 `9.0.5` 升至 `10.0.15`。两份补丁均保留项目引用和原有包引用元数据，包括设计期引用的 `PrivateAssets` 与 `IncludeAssets`。`template-upgrade-projects.json` 记录第二份补丁前后的 Git blob 和 SHA-256，以及两份补丁的摘要。

| 工程后缀 | 模板原始 Git blob | 换包后 Git blob |
| --- | --- | --- |
| Application | `833a7c98ae9c2450ff0d51c7698c75848d6896e1` | `833a7c98ae9c2450ff0d51c7698c75848d6896e1` |
| Core | `be28ccded3ea0b37367cb54fa88e0afd3c911cb0` | `77391fdb5bfc50838867d7daf6b3211b45323303` |
| EntityFrameworkCore | `0db02503a7fb2616bd839ab8fec79eb63099a8d9` | `0db02503a7fb2616bd839ab8fec79eb63099a8d9` |
| Migrator | `c91c58b199dbcc742b360dbf0a0c401e9aa5a8e4` | `c5fc624b5e8c70dc19a1180e50c7008e4512acd2` |
| Web.Core | `a7be79e8a57e525cba6c13c3efd7d4d9b875dfa1` | `b5cee78f297a01db4906155b7d0c25a0ca04b768` |
| Web.Host | `e044651c24aad5691fe65e682db547c50e0dcd66` | `9dc4012119389372efce0cc968792eaec2258f4e` |

### 检查产物与复跑负例

- `frozen-packages.json` 记录 13 个归档的来源、摘要、实际 TFM 及 DLL 摘要。R2 的五个核心包选 `lib/net10.0`，R3 六个框架包选 `lib/net9.0`，两个映射包选 `lib/net8.0`。
- `raw-assets/` 保留六个工程的实际还原图。用 `assets-inventory.json` 核对各工程的直接声明、项目与包的传递边、NuGet 源和编译引用。Web.Host 有三条维护包传递依赖由 SDK 在还原时裁剪，报告关联实际裁剪范围与 `Microsoft.AspNetCore.App` 引用包内的编译 DLL。[NuGet 裁剪规则](https://learn.microsoft.com/en-us/nuget/consume-packages/package-references-in-project-files#prunepackagereference)
- `Web.Host-output.json` 和 `Migrator-output.json` 记录每个入口的运行复制项、归档资产和摘要。其 `sqlServerChain` 包含 EF Core、Relational、SQL Server Provider、SqlClient 的编译引用、运行资产、RID 文件及依赖边。`third-party-differences.json` 保留与原版还原的逐项目差异。
- `launch-manifest.json` 给出待运行业务轮的两条命令、输出目录和对应清单的 SHA-256。运行阶段可使用该清单从已核对的 Release 输出启动。

在已通过构建的运行目录上复跑两个负例。诊断分别在复制的 Migrator 输出中替换 `.NET 9` 核心 DLL，在复制的 Web.Host 还原图中置入 `9.0.5` Provider。两个子进程预期退出 1，诊断入口在两个断言通过时退出 0。

~~~sh
python3 -B eng/tests/verify_r3_template_net10_upgrade.py \
  "$R3_BUILD_RUN" "$R3_BUILD_EVIDENCE/negative-cases" "$R3_FROZEN_ROOT"
~~~

## 2026-11-25 构建验收

macOS ARM64（27.2.1，26B131）和 SDK `10.0.404` 上的通过轮为 `r3-template-net10-upgrade-vpx3ilcu`。验证机保存于 `.git/r3-template-net10-upgrade/package-1/builds/`，该轮 `report.json` 的 SHA-256 是 `0ae53a5382a615cbf7edcba4bb38b857d2e580d6104efe9f59a07402b2de3ad1`。退出码为 0。两入口的还原均为 0 警告、0 错误。Release 构建分别为 Web.Host 307 条编译警告、Migrator 0 条警告，均为 0 错误。37 个输入及受控源副本的摘要复验一致。

| 入口 | 还原包 | 维护包 | NuGet 运行复制文件 | 项目引用复制 DLL |
| --- | ---: | ---: | ---: | ---: |
| Web.Host | 94 | 13 | 176 | 4 |
| Migrator | 66 | 10 | 77 | 2 |

两入口选用 EF Core、Abstractions、Relational 和 SQL Server Provider `10.0.15`。SqlClient 从 `5.1.6` 升至 `6.1.7`，编译引用来自 `ref/net9.0/`，输出包含 `lib/net9.0/` 基础 DLL 和 Unix、Windows 两份 RID DLL。SNI 从 `5.1.1` 升至 `6.0.3`，三份原生复制文件分别对应 `win-arm64`、`win-x64` 和 `win-x86`。两入口均有 `Azure.Identity 1.17.1` 和 `Microsoft.Identity.Client 4.84.2`，Host 的 Web 认证依赖将 `System.IdentityModel.Tokens.Jwt` 解析至 `8.19.2`，Migrator 解析至 `7.7.1`。这些结果来自还原与输出证据，实际 RID 加载由运行阶段确认。

两个入口的 `.runtimeconfig.json` 均声明两项共享框架的起始版本为 `10.0.0`，引用包与 apphost 为 SDK 安装的 `10.0.15`。Migrator 的 `System.Security.Cryptography.Pkcs 10.0.13` 编译引用仍来自 NuGet，SDK 从运行复制项剔除了包内的基础及 Windows RID DLL。构建报告保留 SDK 冲突项、`Microsoft.AspNetCore.App` 平台清单条目及编译 DLL 摘要。

独立重放从 Git archive 开始，检查 882 个文件，只有登记的六个工程发生变化。错误核心 DLL 在 Migrator 输出阶段退出 1，旧 Provider 在 Web.Host 资产阶段退出 1。历史 .NET 9 通过轮的六个项目还原图、编译引用和两入口输出通过只读复验，另复验了三条换包拒绝路径和正式 Host 加载证据的八条拒绝路径。

## 完整运行复验

运行入口在两个独立空 NuGet 缓存中构建同一固定模板的 .NET 9 维护版和 .NET 10 升级版。保留 SDK `10.0.404`，安装实际运行所需的两项 `9.0.10` 和两项 `10.0.15` 共享框架。运行依赖 `pymssql`、Playwright 与 Chrome 或 Playwright Chromium。准备独占、只监听环回的 SQL Server Developer，按原版手册提供无凭据的运行配置与环境变量。账号需要连接本轮恢复库、读取系统目录和业务记录、创建与恢复新库、备份候选库。确保本地目录和服务器目录映射到同一份介质，SQL Server 可以在其中创建升级前后的独立备份。整个双构建、浏览器副本和日志约需 2 GiB，诊断另需空间。[环境与账号配置](r3-template-runtime-baseline.md#复跑)

沿用 .NET 9 正式对照的 `R3_FROZEN_ROOT` 和冻结 Angular production 输出。将登录前备份 `r3_template_cf4314cdfe038c35.bak` 的副本放入配置的备份映射目录。备份集为 `4311036b-9b8a-43f5-944c-5d549e4fed08`，SHA-256 为 `93da0a5ceb9fd98821aa654fedcd13cc91c53ca25cb41f845115a7f05f81d988`。前端服务副本仅允许改两个环回地址。按下列命令从主仓根运行，凭据通过原版手册指定的三个环境变量注入。[冻结文件与备份](r3-template-net9-packages.md#运行复验)

~~~sh
python -B eng/verify.py --profile r3-template-net10-upgrade-runtime \
  --frozen-root "$R3_FROZEN_ROOT" --runtime-config "$R3_RUNTIME_CONFIG" \
  --evidence-root "$R3_RUNTIME_EVIDENCE"
~~~

入口在同一实例恢复随机命名的候选及独立对照，`.NET 9` 应用在候选库登录与查询后形成 `2/1` 起点，并在退出后生成升级前备份。随后实际运行 `.NET 10` Migrator，读回每条迁移命令所用的实例、数据库、会话和连接标识。两代每次启动均核对实际 DLL 和 PID。升级前后的系统目录覆盖用户表列、主键与唯一键、索引键的顺序和包含列、过滤定义与外键。原 30 条迁移和注册业务状态逐项比较。

升级后的 Host 在新的浏览器会话处理同一客户端请求，核对共享框架、11 个维护框架 DLL、AutoMapper 引擎和 SQL 链的实际来源。业务完成后候选库保留两条原行并新增一条成功登录行，独立对照库保持一条。入口分别将两个独立备份恢复到新的 SQL 库名与物理路径，逐库比较迁移历史、业务身份及登录行。运行完成后可依本轮报告的绝对路径和摘要保留备份，再停止本轮独占 SQL Server。后续回退轮使用独立的恢复库。

| 运行目录中的记录 | 用于核对 |
| --- | --- |
| `report.json`、`net9-build/report.json` | 外层升级结果、两代实际命令、退出码、候选出入参及证据路径。外层 `status=passed` 覆盖双恢复点 |
| `net9-migrator-target.jsonl`、`net10-migrator-target.jsonl`、两代 `*-migrator-loaded.json` | 同 PID 的迁移连接、实际入口、共享运行时和程序集。报告的 `sql.migrations` 关联对应输出摘要 |
| `net10-catalog-before.json`、`net10-catalog-after.json`、`sql-commands.json` | 迁移前后实际系统目录与脱敏 SQL 命令及退出状态 |
| `net9-round.json`、`net10-round.json`、两代 `*-host-loaded-verification.json` | 两次实际请求、用户和权限、搜索及页面、处理请求的 Host PID 与程序集 |
| `report.json` 中 `sql.checkpoints`、`sql.rollbackWriteBoundary` | 备份集、文件摘要、独立恢复库文件及实读迁移和登录行、恢复到升级前时会缺少的新增行 |

正式轮通过后，保持同一专用实例和备份映射可用。下列诊断命令会从通过轮取得校验过的 Release 产物，并在独立的新数据库还原相应起点。它将五个真实拒绝场景与四个改写 Host 观测证据的夹具分别记录到 `diagnostics.json`。真实拒绝要求相应验证阶段退出 1，诊断命令在全部预期断言成立时退出 0。

~~~sh
python -B eng/tests/verify_r3_template_net10_runtime.py \
  --passed-run "$R3_PASSED_RUN" --frozen-root "$R3_FROZEN_ROOT" \
  --runtime-config "$R3_RUNTIME_CONFIG" --evidence-root "$R3_RUNTIME_EVIDENCE"
~~~

若要搬移诊断输入，保留通过轮的 `report.json` 与 `net10-host-loaded.json`，以及报告中 `inputs.entryOutputs.net10.Web.Host` 指定的相对清单和清单内的全部 Release 文件。文件应按原相对路径复制为实物。同机重放 Host 夹具时，两项共享框架仍从原记录的已安装运行时读取。报告中原始 Host 路径与 PID 用于验证来源，文件摘要只从传入通过轮目录核对。仅诊断夹具时无需 SQL Server 或浏览器。

~~~sh
python -B eng/tests/verify_r3_template_net10_runtime.py --fixtures-only \
  --passed-run "$R3_COPIED_RUN" --evidence-root "$R3_RUNTIME_EVIDENCE"
~~~

入口先验证传入目录的清单及全部 Host 输出，再用未修改的原观测验证基准，最后执行四项夹具。基准匹配记录位于 `fixture-baseline.json`。复跑真实诊断还须按原相对路径保留 .NET 9 Web.Host、两代 Migrator 的清单及输出、报告中 `inputs.startupObserver` 指定的观测器，并在本轮 SQL 备份映射中准备冻结介质及正式轮的升级前备份。

## 2026-11-25 正式运行验收

完整轮为 `r3-template-net10-upgrade-runtime-ifj4cd74`，SQL 运行标识为 `c8e9e2cca8c981df`。外层 26 个阶段全部通过，退出 0；`report.json` SHA-256 为 `744809c912236ca8674769922274e823cafe7f91d7313e084e4d11e93b2b6308`。使用 macOS ARM64（27.2.1，26B131）、SDK `10.0.404`、专用实例 `r3-net10-runtime-20261125` 的 SQL Server Developer `16.0.4236.2`、Chrome `158.0.8127.37`。1,193 个冻结 Angular 文件与服务副本一致，实际主脚本为 `main-PZGEMKYC.js`。两个 Release Host 都在 `Development` 处理请求。

| 核对项 | .NET 9 维护版 | .NET 10 升级版 |
| --- | --- | --- |
| 两项实际共享框架 | `9.0.10` | `10.0.15` |
| Migrator 与 Host PID | `19308`、`19343` | `19472`、`19485` |
| 实际 EF Core、Abstractions、Relational / SQL Server Provider / SqlClient | `9.0.18` / `9.0.5` / `5.1.6` Unix DLL | `10.0.15` / `10.0.15` / `6.1.7` Unix DLL |
| Host 维护程序集 | 11 个 ABP DLL 和唯一 AutoMapper 引擎均实际加载 | 11 个 ABP DLL 和唯一 AutoMapper 引擎均实际加载 |
| `AutoMapper.Collection` | 已核对还原和输出，场景中未加载 | 已核对还原和输出，场景中未加载 |
| 候选、对照库成功登录计数 | `1/1 → 2/1`，新增登录行 ID `2` | `2/1 → 3/1`，保留行 ID `1`、`2`，新增 ID `3` |

候选库为 `r3_template_c8e9e2cca8c981df_candidate`，对照库为 `r3_template_c8e9e2cca8c981df_control`。两代 Migrator 各观测到 3 条实际迁移命令连接，均指向同一候选库。两个迁移进程和两个 Host 均退出 0。.NET 10 Migrator 前后的 30 条迁移 ID 与 `ProductVersion` 逐项一致，36 张表的目录比较覆盖 340 条列、36 条键列、157 条索引列和 26 条外键列记录，前后目录证据 SHA-256 均为 `c2d3d201947f3590b87e1498555936e7a20cd72fa2b5b3b88305ef368066a01f`。本轮无需新增迁移。

两次真实业务均登录 `Default`（租户 1，账号 2），确认 `Pages.Users`。使用 `Keyword=r3usercf4314cdfe038c35` 发出查询，HTTP 200，`totalCount=1`，唯一用户 ID `3`。两次页面都显示唯一的预期用户名单元格。

### 恢复点与写入边界

两个备份分别以 `COPY_ONLY, CHECKSUM` 制作，执行 `RESTORE VERIFYONLY WITH CHECKSUM` 并实际恢复到两个新的库名与文件。两库都读回各自备份中的 30 条迁移 ID 与 `ProductVersion`、租户授权和查询用户。还原后还逐行对比了账号成功登录记录，包括记录 ID 和创建时间。

| 恢复点 | 介质、备份集 ID 与 SHA-256 | 实际恢复库和登录行 ID |
| --- | --- | --- |
| 升级前 | `r3_template_c8e9e2cca8c981df_before_upgrade.bak` · `fa559c46-091e-457c-9c7e-5c64e7085643` · `15a246b74c1b07ae3459525eb67923058151b39590dad14c2903979b8d7ffa3d` | `r3_template_c8e9e2cca8c981df_before_upgrade` · `1, 2` |
| 升级后 | `r3_template_c8e9e2cca8c981df_after_upgrade.bak` · `8df1e277-cde8-4683-a350-9bbf55a48975` · `21fd40d536999e40dbf014b47ae450d04736a8c9da96c3bcb2d44603610a1479` | `r3_template_c8e9e2cca8c981df_after_upgrade` · `1, 2, 3` |

恢复到升级前会缺少 .NET 10 当轮新增的成功登录行 ID `3`（租户 1，账号 2）。行 ID `2` 是本轮 .NET 9 业务写入，两个恢复点都已读回。原版应用在升级验收时待验，后续已完成两个恢复点的业务复验。[原版应用回退](r3-original-template-rollback.md#正式运行结果)

验证机在 `.git/r3-template-net10-upgrade/package-2/` 留有小型证据索引、保留路径和复跑日志。通过轮与两份可恢复介质分别存于该目录的 `execution/` 所指专用证据目录内的 `runs/` 和 `sql-mount/`。

### 拒绝场景与历史回归

独立诊断轮 `r3-net10-runtime-diagnostics-r7dfr4za` 退出 0。三个实际 Migrator 均退出 0，验证阶段因实际运行时为 `9.0.10`、实际迁移连接落在对照库、缺少登记的连接观测而分别退出 1，三次均未进入 Host。正确候选库上的 .NET 9 负例从升级前备份复现 `2/1` 起点。缺少 .NET 9 登录行时在提交认证前拒绝；写入对照库的诊断完成了真实查询，后端按 `2/1 → 2/2` 及行级写入拒绝。两项业务负例均退出 1。修改正式 Host 观测副本的四项夹具分别触发主版本、补丁、框架 DLL 来源及 Provider 摘要断言。

初次完整轮在 .NET 9 Migrator 的共享框架核对失败。该进程实际从 ASP.NET Core 共享框架加载了 `Microsoft.AspNetCore.Identity`，观测中没有 `Microsoft.AspNetCore.Hosting`。校正 Migrator 的核对项后，两代应用从干净输入完整重跑。Host 继续核对 `Microsoft.AspNetCore.Hosting`。独立历史入口 `r3-template-net9-packages-runtime-6bplqz7s` 通过 20 个阶段，原有八项 Host 证据断言也复验通过。
