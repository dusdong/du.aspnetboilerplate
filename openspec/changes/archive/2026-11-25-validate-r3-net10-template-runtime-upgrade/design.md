# 完整模板运行时升级设计

## Context

正式 .NET 9 对照取自主仓 `a4ffcaa` 的 `r3-template-net9-packages-runtime-a8smhbra`，报告 SHA-256 为 `349da1e3b84ff8d821c740cd7b4a26ec27ec7f176d5cc6d3cd1dcada72745a19`。该轮使用 SDK `10.0.404` 构建，实际 Host 的两项共享运行时均为 `9.0.10`，EF Core / Relational 为 `9.0.18`，SQL Server Provider 为 `9.0.5`。R2 的 `net10.0` 五包已有 SQLite 最小消费者记录。完整 SQL Server 模板是本轮新增的运行组合。[正式对照](../../../../docs/maintenance/r3-template-net9-packages.md#正式运行结果) · [R2 验收](../../../../docs/maintenance/r2-core-package-consumption.md)

## Goals / Non-Goals

本轮固定维护包版应用、前端、账号、请求及数据起点，使业务差异可以归到运行时升级。模板范围为 Core、Application、EntityFrameworkCore、Web.Core、Web.Host、Migrator。Web.Mvc、Angular 依赖升级、其他平台支持和公开发行各自按路线安排。回退轮验证原版应用，本轮为它交付可恢复的数据库和写入边界。

## Decisions

### 在同目标换包补丁上叠加运行时补丁

从 `module-zero-core-template@2e9536872673a7ff1986a19e798c51684d16afe5` 的干净副本重放四个工程的七处维护包引用替换。以此为前像，为六个工程显式设置 `net10.0`。更新 EntityFrameworkCore 的 SqlServer、Design、Tools，Web.Host 的 Design 及 Web.Core 的 JwtBearer。保留项目引用、原有包引用元数据和业务代码。两份补丁能各自重放，便于消费者区分换包与目标框架调整。[换包复跑入口](../../../../docs/maintenance/r3-template-net9-packages.md#固定输入与复跑)

首轮拟固定 SDK `10.0.404`、两项共享运行时 `10.0.15`，上述四种 Microsoft 直接依赖以 `10.0.15` 为候选补丁。R2 包的 `net10.0` 依赖组已声明 EF Core、Relational 及适用的 ASP.NET Core MVC 组件 `10.0.15`。实施时以实际还原、构建和进程加载回读核实整套版本，记录共享框架、SQL Server Provider、SqlClient 的 RID 资产及认证依赖变化。直接引用的设计期工具单独核对。若候选版本或范围无法解析，先记录冲突和修订组合，再从干净输入复跑。

### 从实际归档核对每个目标所用的资产

| 冻结版本 | 包 | 本轮初始选择 |
| --- | --- | --- |
| `10.5.1-r2.1` | Du.Abp、Du.Abp.Web.Common、Du.Abp.AspNetCore、Du.Abp.EntityFramework.Common、Du.Abp.EntityFrameworkCore | 5 个 `lib/net10.0` |
| `10.5.1-r3.1`、`10.5.1-r3.3`、`10.5.1-r3.4` | SignalR 与 Castle.Log4Net、三个 Module Zero 包、Du.Abp.AutoMapper | 6 个 `lib/net9.0` |
| `14.0.0-r3.4`、`11.0.0-r3.4` | Du.AutoMapper、Du.AutoMapper.Collection | 2 个 `lib/net8.0` |

沿用已登记的 13 个包和 5 份生产清单，按 SHA-256 验证归档后，从归档本身取得目标 DLL 的期望摘要。现有登记中五个核心 DLL 的摘要对应 `net9.0`，保留供原入口复验。新入口使用隔离包源映射和空缓存，从各项目还原图、两个入口的 `.deps.json`、实际输出和 Host 加载信息核对选中的包及程序集，保留原有 `Abp.*` 和映射类型身份。候选只有在实际组合出现可复现的依赖或二进制问题时才进入相应组件修复。为修复分配新候选版本并记录输入，旧包和原版对照继续可追溯。[冻结登记](../../../../eng/r3_template_net9_reference.json) · [现有构建验证](../../../../eng/r3_template_net9_packages.py)

### 让两个版本顺序服务同一个候选库

复用 `eng/verify.py` 的验证入口与现有还原、SQL、浏览器和进程观测能力，为升级增加独立 profile。既有 .NET 9 入口固定检查 `9.0.10` 和 `1/1 → 2/1`，升级入口按版本及阶段提供预期值。两阶段使用实际 Host、Migrator 与同一份 1,193 文件的 Angular production 产物，每次登录使用新的浏览器会话。可在服务副本仅改两个环回端点，记录差异与真正加载的入口脚本。[原有运行验证](../../../../eng/r3_template_net9_runtime.py) · [进程观测器](../../../../eng/r3-template-observer/StartupHook.cs)

## Migration Plan

1. 在专用 SQL Server Developer 实例复现基线组合（基线版本 `16.0.4236.2`）。登记实例和候选库、对照库身份。校验登录前备份 `r3_template_cf4314cdfe038c35.bak` 的 SHA-256 及备份集 `4311036b-9b8a-43f5-944c-5d549e4fed08`，恢复到两个独立的新库，回读 30 条迁移、租户、用户与授权，确认计数 `1/1`。凭据由验收环境注入。[备份与运行条件](../../../../docs/maintenance/r3-template-net9-packages.md#运行复验)
2. 用已验的维护包版 .NET 9 产物（或从相同输入核验后的重建产物）在候选库运行 Migrator、Host 和既有浏览器路径。确认两库计数为 `2/1`，记录候选库该账号的两条成功登录行标识，标出当轮新增行，停止 .NET 9 应用。此时对候选库做带校验和的独立备份，记录备份集 ID 与文件 SHA-256，并执行 `RESTORE VERIFYONLY WITH CHECKSUM` 校验介质。
3. 读取候选库迁移历史，从 SQL Server 系统目录按架构名、表名和对象名采集模板业务表的列、主键、唯一键、索引及外键定义，保留键列顺序、索引包含列和过滤条件。在该库执行本轮 .NET 10 Release Migrator。将实际迁移命令连接上的实例、库名、会话及连接标识与 PID 关联。在同一 PID 核对入口 DLL 的路径与 SHA-256、实际共享运行时的路径与补丁版本，以及已加载的 `Microsoft.EntityFrameworkCore`、`Microsoft.EntityFrameworkCore.SqlServer` 的路径与摘要。分别与本轮构建清单、登记的运行时和包资产核对。以独立诊断轮复现 `2/1` 起点，用 .NET 9 Migrator 连到该轮正确候选库，要求在启动 .NET 10 Host 前识别版本错误。
4. 确认 Migrator 成功退出后，重新采集并比较业务表定义。逐条比较迁移 ID 与 `ProductVersion`，回读既有业务、.NET 9 登录行和两库 `2/1` 计数。默认要求迁移历史和业务表定义均与执行前一致。若出现模型或结构差异，记录实际差异并检查迁移 SQL 和数据影响。确需新迁移时，先登记新增 ID 和预期结构变化，再从升级前备份恢复候选库复跑，要求原 30 条历史完整且实际增量与登记一致。
5. 以本轮 Release Host 在与 .NET 9 对照相同的 `Development` 环境提供请求。记录两项共享框架的启动选择与实际加载路径，以及 Host PID、程序集标识、加载上下文、路径和摘要。核对实际加载的 11 个框架 DLL、唯一映射引擎和 SQL 运行链。单列 Collection 的实际加载情况。
6. 登录 `Default`（租户 1、账号 2），确认 `Pages.Users`。用 `r3usercf4314cdfe038c35` 发起相同搜索，核对请求、唯一用户 3 和页面单元格。确认库间计数 `2/1 → 3/1`，记录本次成功登录行标识并核对前一次登录仍在。停止应用，以与升级前相同的方式制作、校验独立的升级后备份。
7. 按各自的备份集 ID 与文件 SHA-256，将两份备份实际恢复到独立于候选库、对照库的两个新临时库。逐库回读迁移历史及租户 1、账号 2 的成功登录行，与各自备份前采集的记录逐项比较。升级前恢复库有 2 条，升级后恢复库有 3 条，该账号新增的唯一成功登录行属于 .NET 10 当轮业务。将两个备份集、各自恢复结果和这条写入的标识交给回退轮。

## Risks / Trade-offs

- 单目标模块与 EF Core 10 的二进制兼容性要由真实进程判定。保存第一个失败阶段、包内资产和异常，便于定位需要修补的具体候选。
- 同一服务器上的两个库起初拥有相同的迁移和业务数据。使用迁移连接的实时读数、先前登录行标识和独立对照库计数，可以发现错连或重建后产生的假阳性。观测器依赖 EF 的迁移事件。若 EF Core 10 缺少有效记录，升级验证应失败并保留诊断。
- .NET 9 留存的程序集复验读取历史绝对路径。新报告保存运行时真实路径，并附相对证据根和摘要以便搬移。旧记录继续按原手册恢复。本轮备份、报告和脱敏配置独立登记。
