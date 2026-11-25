# net9.0 模板换包设计

## Context

主仓从 `148bda55d9fea121a66fa2445388fb0cf552643b` 接续，模板固定在 `2e9536872673a7ff1986a19e798c51684d16afe5`。原版实测是 macOS ARM64、SDK `10.0.404`、两项 .NET 共享运行时 `9.0.10`、SQL Server Developer `16.0.4236.2`。原版 Web.Host 五项目闭包与独立 Migrator 已有可比较的输出。[原版运行手册](../../../../docs/maintenance/r3-template-runtime-baseline.md) · [原版包图](../../../../docs/maintenance/r3-web-host-baseline.md#实际还原与产物)

| 冻结版本 | Host 预期维护包 |
| --- | --- |
| `10.5.1-r2.1` | `Du.Abp`、`Du.Abp.Web.Common`、`Du.Abp.AspNetCore`、`Du.Abp.EntityFramework.Common`、`Du.Abp.EntityFrameworkCore` |
| `10.5.1-r3.1` | `Du.Abp.AspNetCore.SignalR`、`Du.Abp.Castle.Log4Net` |
| `10.5.1-r3.3` | `Du.Abp.Zero.Common`、`Du.Abp.ZeroCore`、`Du.Abp.ZeroCore.EntityFrameworkCore` |
| `10.5.1-r3.4`、`14.0.0-r3.4`、`11.0.0-r3.4` | 依次为 `Du.Abp.AutoMapper`、`Du.AutoMapper`、`Du.AutoMapper.Collection` |

按各批已登记来源核对 13 个主包及 nuspec。R2 的最低版本边、R3 的精确版本边和引擎、Collection 的独立版本分别验证，保留原归档字节。[R2 核心](../../../../docs/maintenance/r2-core-package-consumption.md) · [SignalR 与 Log4Net](../../../../docs/maintenance/r3-signalr-log4net-candidates.md) · [Module Zero](../../../../docs/maintenance/r3-module-zero-candidates.md) · [映射批次](../../../../docs/maintenance/r3-automapper-downstream.md#冻结产物)

## Goals / Non-Goals

交付可在干净模板副本重放的项目引用变更、完整 Host 和 Migrator 的实包构建、同一前端和数据库恢复点的业务报告。验收保持 `net9.0`、EF Core 9、Release Host 的 `Development` 环境及已验的 Angular production 代码。其他模板入口、.NET 10、迁移后回退和 R4 发包保留各自的验收步骤。

## Decisions

### 1. 在真实模板项目上重放引用变更

主仓提供可审查、可重放的迁移补丁或等价的确定性项目文件变更，验证固定前像并输出实际差异。从模板提交物化隔离源码，保持项目引用拓扑。直接引用使用冻结的精确版本，保留原有包引用的元数据。

| 项目 | 换成对应维护包的直接引用 |
| --- | --- |
| Core | `Abp.AutoMapper`、`Abp.ZeroCore.EntityFrameworkCore` |
| Web.Core | `Abp.AspNetCore`、`Abp.ZeroCore`、`Abp.AspNetCore.SignalR` |
| Web.Host、Migrator | 各自的 `Abp.Castle.Log4Net` |

其余维护包通过这些依赖进入。Application、EntityFrameworkCore 与子项目仍参与真实还原。原版 SQL Server、EF Design/Tools 和 JwtBearer 均由模板直接声明为 `9.0.5`，R2 的 EF Core、Relational 与部分 MVC 组件要求 `9.0.18`。先保留模板第三方声明并采集实际解析、告警和运行结果；若存在具体降级、资产或运行冲突，以证据确定最小的 9.0.x 调整，保留原始失败、修改理由和重跑结果。不得通过抑制降级诊断获得通过。框架候选本身若需要修改，登记为候选缺陷并回到相应组件生产新批。

### 2. 核对每个阶段实际使用的包和 DLL

拟在 `eng/verify.py` 增加 `r3-template-net9-packages`。复用现有源码物化、依赖图、资产摘要、浏览器和 SQL 核对逻辑。原版 profile 继续执行其固定原包断言。候选入口只把已核对的 13 个维护包映射到受控源，公共源提供其余依赖，各次运行使用独立 NuGet 配置、空全局包缓存及 HTTP 缓存。以各项目的 `project.assets.json`、实际归档、编译/复制项、Host 和 Migrator 各自的 `.deps.json` 与 Release 输出核对闭包，单列 SDK pack 和仅编译资产。报告列出 SQL Server、EF Core/Relational、SqlClient、映射及日志依赖的版本和相对原版差异。

在实际处理登录与搜索的 Host 中收集程序集加载记录。可用只观察加载的启动钩子或等价运行时事件，在业务请求完成时覆盖所有加载上下文，关联 PID、程序集全名、路径和 SHA-256。11 个框架 DLL 使用各包的 `net9.0` 资产，两个映射包使用各自的 `net8.0` 资产。区分磁盘存在、真实加载和仅作传递依赖的扩展。不得为补齐记录主动载入待验 DLL。若必需框架 DLL 尚未观测，报告具体组件及尚缺的模板运行路径。[既有资产检查](../../../../eng/r3_web_host.py) · [进程加载对照](../../../../validation/automapper-minimal/Program.cs)

从处理业务的 Host 启动记录读取 `Microsoft.NETCore.App` 和 `Microsoft.AspNetCore.App` 的实际加载路径及版本。正式对照要求两者均为 `9.0.10`。任一项偏离时，本轮正式对照失败，保留实测版本。若需要解释另一补丁组合的换包差异，再让原版和候选 Host 使用该组合、同一冻结前端及从同一备份分别恢复的新库，比较同一业务场景，单独登记结果。

### 3. 从最终返修备份恢复，保留独立数据库对照

基准报告位于 `.git/r3-template-runtime/revision-1/runs/r3-template-runtime-89igcw5r/`，备份文件名为 `r3_template_cf4314cdfe038c35.bak`，备份集 ID 为 `4311036b-9b8a-43f5-944c-5d549e4fed08`，SHA-256 为 `93da0a5ceb9fd98821aa654fedcd13cc91c53ca25cb41f845115a7f05f81d988`。入口接受可搬迁的实物路径，按登记身份选取。上一轮容器已停、测试账号已禁用，执行前在专用实例核对可用凭据、服务端备份路径和恢复权限。不得假定原登录可用。

复用既有目标库存在性、物理路径、备份标头、`VERIFYONLY`、`FILELISTONLY` 和实际恢复核对。现有原版流程会创建源库并生成新备份，候选入口需要读取已有介质，并将历史源库名与本轮新目标名分别处理。在新的物理路径恢复候选库及只用于比较计数的独立对照库，两者均从同一冻结备份开始。核实 30 条迁移及版本、`Default` 租户 1、账号 2、合成用户 3 和成功登录基数 1。在候选库运行同一构建的维护版 `Migrator -q`，检查退出码并再次读回迁移历史、种子及业务字段。若出现待执行的新迁移或模型差异，停止同比验收，保存原因。[原版 SQL 验证](../../../../eng/r3_template_sql.py)

从 `Migrator -q` 执行迁移的已打开 SQL 连接读取 `SERVERPROPERTY('ServerName')` 和 `DB_NAME()`，将结果与 Migrator PID、本轮预期实例名和候选库名一同记录。启动参数只表达预期目标。若连接缺少实测记录或目标不符，入口在启动 Host 前返回非零。负例使用独立诊断轮的两份恢复库，保持预期目标为候选库，仅将 Migrator 的实际连接指向对照库，检验两库初始状态相同时仍能识别错连。

### 4. 复用原版前端，在同一业务请求上比较

逐文件比对返修轮 `angular-production-files.json` 后，从独立副本提供冻结的 1,193 个文件。优先复用原业务端口；如需更换，允许在副本仅覆盖 `assets/appconfig.production.json` 两个地址，并记录变更前后摘要、浏览器实际加载的入口脚本及对应 CORS 配置。复用原版 `browser_round` 的真实租户选择、登录、授权、关键词响应和精确表格行断言。在 `before_login` 回调中读取两库内租户 1、账号 2 的成功登录计数。任一读数偏离 1 时记录两库读数并在提交前终止。完成搜索后再次读取，候选库须为 `1 → 2`，对照库须为 `1 → 1`。原版归档的同期源库是 2 → 2，两次验证均要求对照库增量为零。[浏览器验收](../../../../eng/r3_template_browser.py) · [原版恢复轮](../../../../docs/maintenance/r3-template-runtime-baseline.md#2026-11-25-返修复验)

## Risks / Trade-offs

- 仅看包名或 `.deps.json` 无法确定进程最终选中了哪份同名 DLL。验收同时保存包、输出和加载证据，失败时指出差异发生的阶段。
- 修改端口、SQL 实例环境或第三方补丁版本会影响对照解释。报告区分可定位的环境配置与实际软件版本差异，凡超出同目标口径的结果单独记录。

## Migration Plan

通过后交接模板差异、13 包清单、实际加载与第三方版本、备份身份、原版/候选比较表和可复跑命令，供下一轮升级运行时使用。失败时保留首次失败和部分证据，释放本轮启动的进程及端口。可以在新目录、新库重试，冻结候选、前端原件和登录前备份继续供原版对照复用。
