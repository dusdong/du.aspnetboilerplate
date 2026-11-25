# R3 固定模板原版回退复跑

固定原版模板已在升级前后两个 SQL Server 恢复点通过回退验收。两条路径均从真实迁移连接、Angular 业务请求及两库成功登录行核对实际读写。升级后状态允许直接切回原版应用并保留本例 .NET 10 写入。[正式运行结果](#正式运行结果) · [稳定规范](../../openspec/specs/template-application-rollback/spec.md) · [归档设计](../../openspec/changes/archive/2026-11-26-validate-r3-original-template-rollback/design.md)

## 冻结输入

在原件根目录保留 `r3-template-runtime/revision-1/runs/r3-template-runtime-89igcw5r/` 的原版返修轮。固定模板提交为 `2e9536872673a7ff1986a19e798c51684d16afe5`。该轮 `report.json` 的 SHA-256 为 `d60dfea17e2d3ffe00d6b1914f429cca7cd60d2a114f913561d62dde0044985c`，其中的相对路径定位两套 `net9.0` Release 输出、各自的还原图、运行资产及 Angular production 输出。复跑还需要该轮的 `release-host-files.json`、`release-migrator-files.json`、`assets-inventory.json`、`angular-production-files.json`、原版 NuGet 缓存 `packages/` 及报告登记的 `yarn.lock`。缺少实物时按原版手册定位可核对的原件，复跑入口要求实物与冻结摘要一致。[原版返修轮](r3-template-runtime-baseline.md#2026-11-25-返修复验)

两套 Release 目录分别核对入口及 495、82 个文件。Host 的 11 个 ABP 包和 Migrator 的 8 个可达 ABP 包均为 `10.2.0`。两套还原图均指向 nuget.org，并通过 `.deps.json`、包缓存来源和实际归档读取核对运行复制项。AutoMapper 为 `14.0.0`，Collection 为 `11.0.0`，EF Core、Abstractions、Relational 和 SQL Server Provider 均为 `9.0.5`，SqlClient 为 `5.1.6`，含 Unix 运行资产。历史原版 Host 启动证据记录两项共享运行时为 `9.0.10`。本入口在新运行目录复制核对后的 Release 文件和 1,193 个 Angular production 文件，检查 `index.html` 引用冻结主脚本 `main-PZGEMKYC.js`。前端副本仅按配置更新两个环回地址。[原版与维护版版本对照](r3-template-net9-packages.md#正式运行结果)

取升级正式轮 `r3-template-net10-upgrade-runtime-ifj4cd74` 的 `report.json`、`net10-catalog-before.json` 和 `net10-catalog-after.json`。正式报告摘要为 `744809c912236ca8674769922274e823cafe7f91d7313e084e4d11e93b2b6308`，前后目录的摘要均为 `c2d3d201947f3590b87e1498555936e7a20cd72fa2b5b3b88305ef368066a01f`。验证机可从 `.git/r3-template-net10-upgrade/package-2/execution/runs/` 查找该目录。从同一 `execution/sql-mount/` 获取下列备份，按原文件名准备只读副本供本轮主机与 SQL Server 读取。[升级轮正式恢复点](r3-template-net10-upgrade.md#恢复点与写入边界)

| 恢复角色 | 冻结介质 | 备份集 ID | SHA-256 | 成功登录行 ID |
| --- | --- | --- | --- | --- |
| `after_upgrade` | `r3_template_c8e9e2cca8c981df_after_upgrade.bak` | `8df1e277-cde8-4683-a350-9bbf55a48975` | `21fd40d536999e40dbf014b47ae450d04736a8c9da96c3bcb2d44603610a1479` | 1、2、3 |
| `before_upgrade` | `r3_template_c8e9e2cca8c981df_before_upgrade.bak` | `fa559c46-091e-457c-9c7e-5c64e7085643` | `15a246b74c1b07ae3459525eb67923058151b39590dad14c2903979b8d7ffa3d` | 1、2 |

## 完整复跑

准备独占、仅监听环回的 SQL Server `16.0.4236.2` Developer 和带 `pymssql`、Playwright 的 Python。应用需要 `Microsoft.NETCore.App` 和 `Microsoft.AspNetCore.App` `9.0.10`，观测器从本机 SDK `9.0.306` 与对应目标包离线构建。使用已安装的 Playwright Chromium，或通过无凭据配置的 `chrome` 指定本机 Chrome 可执行文件。按原版手册使用三个进程环境变量注入凭据。将 `localBackupDirectory` 和 `sqlBackupDirectory` 映射到同一组只读备份。SQL 账户需要核对实例和目标、验证备份、恢复新库，应用账户需要运行模板迁移并访问业务表。[配置和凭据入口](r3-template-runtime-baseline.md#复跑)

从任意干净工作目录调用主仓入口。令 `R3_REPO` 为主仓根目录，`R3_FROZEN_ROOT` 为原件根目录（验证机为主仓 `.git/`），`R3_UPGRADE_RUN` 为正式升级轮目录，`R3_RUNTIME_CONFIG` 为本轮专用实例的配置，`R3_EVIDENCE_ROOT` 为独立证据根目录。

~~~sh
python -B "$R3_REPO/eng/verify.py" --profile r3-template-original-rollback \
  --frozen-root "$R3_FROZEN_ROOT" --rollback-upgrade-run "$R3_UPGRADE_RUN" \
  --runtime-config "$R3_RUNTIME_CONFIG" --evidence-root "$R3_EVIDENCE_ROOT"
~~~

每次生成独立运行目录和 SQL 标识。SQL 预检核对两份本机文件 SHA-256、专用实例、两个未占用的目标库名及物理路径。服务端对每份介质读取标头的备份集 ID，再执行 `RESTORE VERIFYONLY WITH CHECKSUM`。按 `after_upgrade`、`before_upgrade` 依次恢复到新库 `r3_template_<本轮标识>_after_upgrade`、`r3_template_<本轮标识>_before_upgrade`，使用独立数据和日志路径。读回 `ONLINE`、实际数据库 ID 和 GUID、文件路径及实例名。文件摘要、备份集 ID、目标库或文件占用任一不符都会失败。

恢复后的两库分别对照其正式恢复点。逐条校验 30 条迁移的 ID 和 `ProductVersion`，以及 36 张表登记的列、键、索引和外键。业务侧校验 `Default` 租户 1、账号 2、`Admin` 角色授予 `Pages.Users` 的依据，以及 `r3usercf4314cdfe038c35` 唯一命中的用户 3。成功登录只查租户 1 和账号 2，按 `id`、`creationTime`、`result`、`tenantId`、`userId`、`tenancyName`、`loginName` 七字段逐行比较。升级后库的原始行 3 创建时间为 `2026-11-25T21:55:58.3636350`。

入口串行复跑两个恢复点。每条路径运行原版 `Migrator -q`，从实际迁移命令连接读取实例与库名，随后复查两库身份、迁移、目录、业务和登录行。原版 Host 用 `Development` 启动。用独立 Angular 会话提交租户登录，从授权菜单搜索。在浏览器请求和 Host 观测中用同一个本轮请求 ID 关联计数与列表查询，然后分别在各命令实际使用的连接及事务中读取实例、库名与 SQL 会话 ID。只有两条路径均通过且清理、冻结实物复核成功时整轮退出 0。

每次认证前核准两个库的实读快照。认证可能已提交时，在停止应用前逐库读回，保存新增和移除的七字段行。若业务异常，保留首错。读回异常另记，缺少的终值标为 `unknown`。升级后路径失败时，入口从同一对冻结介质再恢复两个新库并核准起点，才运行独立的升级前路径。第一条路径失败时整轮退出 1，即使第二条通过。

| 本轮记录 | 复核依据 |
| --- | --- |
| `report.json` | 冻结输入、各路径退出状态、实际业务、逐行差异、首错与后续错误 |
| `Web.Host-output.json`、`Migrator-output.json` | 各入口全部输出摘要、还原图及原版包归档与选择的运行资产 |
| `angular-production-files.json` | 本轮前端副本清单，对应报告登记的冻结清单与地址变化 |
| `*-catalog.json` | 恢复、迁移前后及业务后读回的两库系统目录 |
| `*-migrator-target.jsonl`、`*-host-search.jsonl` | 实际迁移连接和关键词请求中的计数、列表连接证据 |
| `*-migrator-loaded.json`、`*-host-loaded.json`、`*-round.json` | 进程加载、上下文、程序集摘要，以及浏览器请求与页面记录 |
| `sql-commands.json` | 备份标头、校验和、实际恢复和两库只读核对的 SQL 命令与退出状态 |

报告用 `stages` 和 `paths` 记录各阶段及两条业务路径的实际状态，`coverageNotRun` 列出本入口范围以外的工作。`inputs.planning` 记录规划基点，并登记工作树中实际读取的制品路径、摘要及对应的 Git 状态。入口优先读取活动目录，归档后从归档目录读取。`changePath` 和 `changeState` 记录本轮所读目录和状态。用 `inputs.executionCommit` 和 `executionTree` 核对执行检出，冻结原版返修轮的代码身份见 `inputs.original`。

入口停止应用和前端监听并记录所有子进程的退出状态。保留报告及证据，复核冻结备份摘要后，由本次专用 SQL Server 的操作者释放该实例。新一轮从两份冻结介质恢复新的独立库。

## 切回步骤与数据边界

在受测组合中，先停止升级版应用，再将已核对的原版 Release Migrator、Host 和冻结 Angular 客户端切到升级后的状态。运行原版 `Migrator -q` 并复核目标库、迁移历史、目录和业务起点，再启动原版 Host 并用新会话登录、授权、查询。两代应用在这组结构上兼容，30 条迁移及已核对的表结构一致，无需逆向迁移或恢复到旧备份。正式测试使用独立库重建该状态，原来三条成功登录行完整保留。[升级后库结果](#正式运行结果)

如果已查实升级后的状态与原版不兼容，且同组合在升级前恢复点通过，则用已核对备份恢复升级前数据库，再用同一原版应用和新会话复验。选择较早的恢复点会舍弃恢复点之后的写入。本例可证实舍弃的是 .NET 10 成功登录行 3，其创建时间为 `2026-11-25T21:55:58.3636350`。原版再次登录后复用了 ID 3，七字段比较以不同创建时间区分两笔写入。环境或证据缺项只能判定对应路径未通过验证。[升级前库结果](#正式运行结果)

本结论覆盖受测租户登录、已登记的权限与查询、目录和该账号的成功登录行。现场流量切换、恢复时长、其他业务数据及平台或 Provider 的回退需要各自的验收。

## 正式运行结果

返修通过轮 `r3-template-original-rollback-3nceeuiw` 退出 0，`report.json` 的 SHA-256 为 `65d22ef6f1d0e129a533bd857dd47524d4053272f8492cf31bddb300dd21c38c`。验证机可从 `.git/r3-original-template-rollback/package-2/revision-1/execution/runs/` 定位运行目录。本轮 OpenSpec 制品来自基于 `d731068` 的未提交工作树，执行检出的 HEAD 同为 `d731068`。实测 macOS ARM64 `27.2.1`、SQL Server Developer `16.0.4236.2`、Python `3.12.14`、pymssql `2.3.13`、Playwright `1.59.0`、Chrome `158.0.8127.37`。原版 Migrator 和 Host 均实际使用两项 `9.0.10` 共享框架，EF Core、Relational、SQL Server Provider `9.0.5` 及 Unix SqlClient `5.1.6`。两个 Host 的实际程序集均包含 11 个原版 ABP DLL，单一 AutoMapper 引擎来自原版 `14.0.0` 包。Collection `11.0.0` 作为输出核对，两条业务路径均未加载。

| 路径 | 实际运行与查询 | 成功登录行变化 |
| --- | --- | --- |
| `after_upgrade` · 退出 0 | `r3_template_ae81d155b027988c_after_upgrade`，Migrator PID 47588，Host PID 47608。同一关键词请求的计数和列表均读该库，HTTP 200，总数 1，用户 ID 3，页面唯一用户名与关键词一致。 | 保留升级后原行 1、2、3，新增 ID 4，时间 `2026-11-25T23:34:40.9589260`。升级前对照库保留两条原行。 |
| `before_upgrade` · 退出 0 | `r3_template_ae81d155b027988c_before_upgrade`，Migrator PID 47760，Host PID 47775。新会话的同一关键词请求验证两条查询读该库，结果和页面均匹配。 | 保留升级前原行 1、2，新增 ID 3，时间 `2026-11-25T23:34:50.2003190`。升级后对照库保留四条原值。 |

两条路径均通过 `Default` 租户账号 2 的认证和 `Pages.Users` 授权。两库计数按升级后库和升级前库的顺序从 `3/2` 经 `4/2` 到 `4/3`。正式轮 186 个 SQL 调用均退出 0。两组应用进程、监听端口和本轮 SQL 实例已释放，历史介质及只读挂载副本的最终摘要均与表中登记相同。

正式和诊断轮受测代码对应 `d731068` 之上的 19 文件验收候选。验证机可核对 `.git/r3-original-template-rollback/package-2/candidate-files.json`，该清单的 SHA-256 为 `d598d419c86e2fb3f3ff07d2b7b9247119aaca164d1b416961c65b29cc6ed1e4`。归档收尾将规划和稳定规范整理到正式位置，运行代码仅调整规划目录定位及其报告字段。收尾在实际归档目录定向复验规划元数据，并运行 Python 回归。SQL Server 和浏览器实测采用前述冻结报告。

## 独立诊断

保持专用 SQL Server 和只读备份映射可用，设置 `R3_ROLLBACK_RUN` 为完整通过轮路径。用以下命令在独立证据目录执行诊断。

~~~sh
python -B "$R3_REPO/eng/tests/verify_r3_template_original_rollback.py" \
  --frozen-root "$R3_FROZEN_ROOT" --rollback-upgrade-run "$R3_UPGRADE_RUN" \
  --runtime-config "$R3_RUNTIME_CONFIG" --evidence-root "$R3_EVIDENCE_ROOT" \
  --passed-run "$R3_ROLLBACK_RUN"
~~~

真实诊断用本轮新库运行维护版 Migrator 连正确库、原版 Migrator 连错库、认证前在升级前库发现升级轮原行 3、浏览器写入对照库，以及成功登录后让同次关键词列表查询失败。夹具从正式通过轮的查询证据复制并改变指定字段，覆盖计数或列表错读、缺项、初始列表以及其他进程或请求。每条真实负例应退出 1，所有预期拒绝通过时诊断入口退出 0。

返修诊断轮 `r3-original-rollback-diagnostics-hlklird_` 退出 0，五项真实负例和六项查询证据夹具均按预期拒绝。登录后故障的子报告为 `search_failure_after_login-ovt92gbd/report.json`。第一路径首错是关键词查询 HTTP 500，清理前目标库实读新增 ID 4，对照库行保持原值。第二路径使用重新恢复并核准的两库，真实查询通过。该子报告整轮退出 1。回读故障夹具另证实读不到的终值会标为 `unknown`。
