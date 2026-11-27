# 参考 Silo：一条适合维护型 fork 的路线

## 当前阶段（2026-11-27）

公开版 `v10.5.2` 已在 `0d42db5` 完成收尾。2026-11-27 已按四张公开消费依赖图完成补丁后维护审查，决定为**维护包无需补丁**。存量 .NET 9 部署继续迁往受支持的 .NET 10 组合。遇到适用的上游变动、依赖变更或新服务公告时，从本次记录续查。[收尾交付](#2026-11-27-公开发行收尾) · [维护决定与行动](r5-public-patch-review.md#本轮维护决定) · [下轮检查点](r5-public-patch-review.md#下轮检查点与验证边界)

固定模板已按消费者指南用公开输入完成 `v10.5.1 → v10.5.2 → v10.5.1` 同库回退。保存的 R4 在一次管理员新登录后分别查回两版写入的用户，替换映射 DLL 的副本在启动迁移前被拒绝。[消费者指南](r5-consumer-package-rollback.md) · [独立验收与适用范围](r5-automapper-template.md#独立消费者验收) · [公开包同库回退历史](#公开包同库回退与后续检查)

公开 R4 和 R5 已在同一 macOS ARM64、.NET 10 与 SQLite 环境下分别通过已有用户更新、按键集合更新和查询投影。两张原始还原图仅三个映射包有版本差异。[逐项实测与公开复跑](r5-public-mapping-behavior.md) · [对照计划](r5-public-mapping-consumer-plan.md)

公开 R4 与 R5 已分别在固定模板及独立 SQL Server 新库实测用户更新。各版的保留、替换和清空三步都通过，回执、独立 GET 和 SQL 一致，创建时间保持原值。对应需求已同步到稳定规范，OpenSpec 已归档。[实测结果与复跑](r5-template-user-role-update.md) · [验收计划](r5-template-user-role-update-plan.md) · [稳定规范](../../openspec/specs/automapper-package-consumption/spec.md#requirement-两代公开映射包可对照固定模板的用户角色更新提交) · [归档](../../openspec/changes/archive/2026-11-27-validate-r5-template-user-role-update/)

R5 首轮维护审查已在 `4d051e8` 归档。存量 `net9.0` 消费者的迁移指引和增量审查已交付，变更已归档。本轮通过两代四入口公开源 Release 构建，并回读 R4 固定组合的同库实测。[存量迁移指引](r5-r4-net10-migration.md) · [增量审查](r5-runtime-migration-review.md) · [迁移与审查归档](../../openspec/changes/archive/2026-11-26-review-r5-runtime-migration-readiness/)

集合映射补丁已公开发行 `v10.5.2`。三个新主包、三个符号包、三个公开 PDB 和十个沿用包完成核验。发布者公开源安装与同库接续，以及独立消费者按固定公开指南新装，均通过实测。公开发行规范已同步，发行变更已归档。原冻结候选的本地三阶段同库包切换保留为历史回退依据。[R5 发行验收](r5-public-release.md) · [公开发行稳定规范](../../openspec/specs/public-package-release/spec.md) · [发行归档](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/) · [三包冻结与消费](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md) · [补丁候选任务](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/tasks.md)

- R0 已验收并归档。上游 `v10.5.1` 的首批五包源码基线记录了公共 API、还原图和三套回归，实测环境为 macOS ARM64、.NET 9，EF Core 关系型用例使用 SQLite。[R0 基线](release-baseline.json) · [R0 归档](../../openspec/changes/archive/2026-11-24-establish-maintenance-baseline/)
- R0 统一复验已完成本地与 GitHub Actions 的独立配对验收并归档。两次执行均用 `python3 eng/verify.py --profile r0` 复验固定的原版 R0 源码。[复验手册](baseline-evidence/README.md#统一入口) · [配对验收记录](baseline-evidence/README.md#统一入口验收记录) · [统一复验归档](../../openspec/changes/archive/2026-11-24-unify-r0-baseline-verification/)
- R1 首项已验收并归档，在同一 .NET 9 环境接入上游 EF Core 查询过滤修复 #7219。首批 .NET 10 / EF Core 10 源码已通过 macOS ARM64、UTM Windows ARM64 和 GitHub Windows x64 验收，已合入框架 `dev` 并由主仓 gitlink 固定。[R1 首项验收记录](r1-efcore-query-filter.md) · [R1 运行时迁移验收](r1-dotnet10-runtime-migration.md) · [迁移归档](../../openspec/changes/archive/2026-11-25-migrate-r1-core-to-dotnet10/)
- R2 本地候选 `10.5.1-r2.1` 的五个核心包已通过 macOS ARM64 的 `net9.0` 与 `net10.0` 独立后端验收，覆盖两条传递依赖链、实际程序集加载和 SQLite 工作单元提交。OpenSpec 已归档。框架 `dev` 已推送同树实现，主仓 gitlink 记录该提交。完整模板属于 R3，公开包发布属于 R4。[R2 候选包消费验收](r2-core-package-consumption.md) · [R2 归档](../../openspec/changes/archive/2026-11-25-validate-r2-core-package-consumption/)
- R3 首包已验收并归档。在 macOS ARM64 上构建了固定模板的原版 `net9.0` Web.Host，核对了实际还原图、运行资产与六个维护包缺口。首包记录保持原始验收口径。[R3 首包验收](r3-web-host-baseline.md) · [模板 Web.Host 基线规范](../../openspec/specs/template-host-baseline/spec.md) · [R3 首包归档](../../openspec/changes/archive/2026-11-25-baseline-r3-web-host-dependencies/)
- R3 第二包已验收并归档。SignalR 与 Log4Net 的同批候选 `10.5.1-r3.1` 已通过 macOS ARM64 独立 `net9.0` 宿主验收，框架 `dev` 已交付同树实现。该批将候选缺口从六个减为四个。[R3 第二包验收](r3-signalr-log4net-candidates.md) · [集成候选包消费规范](../../openspec/specs/web-host-integration-package-consumption/spec.md) · [R3 第二包归档](../../openspec/changes/archive/2026-11-25-add-r3-signalr-log4net-candidates/)
- R3 Module Zero 的三个候选包 `10.5.1-r3.3` 已在 macOS ARM64 的独立 `net9.0` 消费者中验证 SQLite 角色提交与双向租户隔离。主仓 `d54f782` 固定了与冻结候选同树的框架提交 `819c64cf`，OpenSpec 已归档，该主仓提交的 R0 基线 CI 已通过。[Module Zero 交付与 CI 记录](r3-module-zero-candidates.md#git-交付) · [Module Zero 归档](../../openspec/changes/archive/2026-11-25-add-r3-module-zero-candidates/)
- R3 AutoMapper 的三份冻结候选完成本机验收，补齐固定 Web.Host 的最后一项候选包 `Abp.AutoMapper`。六项均已取得独立候选，剩余缺口为 **0**。三仓已交付，主仓固定相应 gitlink，稳定规范已同步并归档。[AutoMapper 引擎验收](r3-automapper-engine.md) · [下游实包验收](r3-automapper-downstream.md#消费验收记录) · [Git 交付](r3-automapper-downstream.md#git-交付)
- R3 原版模板运行对照已验收并归档。最终返修轮在 macOS ARM64、SQL Server Developer 和 Angular production 客户端下以受限 SQL 账号完成两轮验收。恢复轮在恢复库新增 1 条成功登录记录，源库计数保持不变。[返修验收](r3-template-runtime-baseline.md#2026-11-25-返修复验) · [恢复点](r3-template-runtime-baseline.md#交接数据恢复点) · [稳定规范](../../openspec/specs/template-runtime-baseline/spec.md) · [归档](../../openspec/changes/archive/2026-11-25-baseline-r3-original-template-runtime/)
- R3 固定模板 `net9.0` 同目标换包已通过正式运行验收并归档。Web.Host 和 Migrator 使用 13 个冻结维护包，在 macOS ARM64、两项 `.NET 9.0.10` 共享运行时、SQL Server Developer `16.0.4236.2` 和原版 Angular production 产物上复验。候选库与独立对照库均从最终返修轮的登录前备份恢复，浏览器复现相同的租户登录、授权和用户查询，两库成功登录计数从 `1/1` 变为 `2/1`。[正式运行结果](r3-template-net9-packages.md#正式运行结果) · [模板维护包消费规范](../../openspec/specs/template-maintenance-package-consumption/spec.md) · [归档](../../openspec/changes/archive/2026-11-25-validate-r3-net9-template-package-migration/) · [后续验收顺序](#r3验证升级路径和实际消费者)
- R3 固定维护版模板的 .NET 10 / EF Core 10 升级已通过本机完整运行验收，OpenSpec 已同步并归档。两代应用在同一 SQL Server 候选库接续，原 30 条迁移与表结构保持一致。两轮 Angular 业务将候选、对照库登录计数从 `1/1` 经 `2/1` 推到 `3/1`，升级前后两份备份均实际恢复并逐行核对登录记录。[升级与双恢复点](r3-template-net10-upgrade.md#2026-11-25-正式运行验收) · [稳定规范](../../openspec/specs/template-runtime-upgrade/spec.md) · [归档](../../openspec/changes/archive/2026-11-25-validate-r3-net10-template-runtime-upgrade/)
- R3 固定原版模板已在两个恢复点完成本机回退验收，OpenSpec 已同步并归档。原版 `net9.0` Migrator 和 Host 在 SQL Server Developer 上复现 Angular 登录及授权查询，两库成功登录计数从 `3/2` 经 `4/2` 到 `4/3`。升级后路径保留了 .NET 10 写入，升级前路径确认选择较早恢复点会舍弃该写入。[原版回退结果与范围](r3-original-template-rollback.md#正式运行结果) · [稳定规范](../../openspec/specs/template-application-rollback/spec.md) · [归档](../../openspec/changes/archive/2026-11-26-validate-r3-original-template-rollback/)

- R4 已首次公开发行。13 个主包、13 个符号包和 18 个调试目标完成公开核验，两代四入口通过公开源同库接续，`net10.0` 新库安装通过。`net9.0` 留作存量应用迁移兼容性实测。原版双路径回退和映射专项使用同批冻结归档的本地证据。[发行说明](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1) · [公开源复验](r4-release-candidate.md#公开源模板消费) · [历史冻结交接](r4-release-candidate.md#发布者交接)

**原路线与研究说明**

> 适用对象：基于经典 ASP.NET Boilerplate（`aspnetboilerplate/aspnetboilerplate`）维护并独立发行的项目。  
> 文档版本：1.0。编制与证据核查日期：2026-11-21。  
> 状态：维护路线与发布审查基线；各阶段的完成状态以项目实际实施记录为准。  
> 配套文档：[有参考价值的 ASP.NET Boilerplate fork 项目](fork-references.md)。

## 1. 先固定目标和兼容性硬约束

本项目的目标是形成一个可追溯、可升级、可验证、维护范围明确的 ASP.NET Boilerplate 独立发行版。第一阶段优先处理运行时升级、重要缺陷、依赖维护、发包和消费者迁移；架构重构作为后续独立议题评估。

### 1.1 用户已经确定的长期规则

**本 fork 的既有 `Abp` 及 `Abp.*` 代码命名空间永久保持不变。`Du.` 前缀只用于 NuGet 包名，不进入代码命名空间。此规则是以后所有代码改动、文档示例、迁移方案和发布审查的兼容性硬约束。**

这条规则覆盖后续大版本、运行时升级和新发行线，不能因为重命名品牌、整理目录或替换依赖而自动解除。新增框架模块也应沿用合适的 `Abp.*` 命名空间。嵌入的第三方源码保留其原有命名空间；本规则不要求把业务应用自己的命名空间改成 `Abp.*`。

| 对象 | 规则 | 属性 |
| --- | --- | --- |
| 既有框架代码的命名空间 | 保持原来的 `Abp` / `Abp.*`，禁止改为 `Du.Abp.*` | 用户明确的硬约束 |
| 新增框架代码的命名空间 | 使用适当的 `Abp.*`，不因包前缀引入 `Du.*` | 用户约束的实施规则 |
| 既有公共类型全名 | 不因品牌或包名变更顺带修改；其他公共 API 变化单独审查和说明 | 配套兼容策略，不等于永久冻结所有 API |
| NuGet `PackageId` | `Abp` → `Du.Abp`；`Abp.X` → `Du.Abp.X` | 用户确定的发行身份 |
| 既有 `AssemblyName`、`RootNamespace` | 保留各项目原值，不随 PackageId 批量重命名 | 本路线采用的配套兼容策略 |
| `AssemblyVersion`、文件版本与包版本 | 单独制定版本政策；不能从“名称不变”推导出“版本号永久不变” | 需明确的发行政策 |
| 外部协议、配置键、序列化类型名、数据库语义 | 不为改发行品牌而顺带修改；确有功能变更时单独验证和记录 | 兼容性审查范围 |

包映射应明确到每一个正式发行的项目：

| 上游包 | 本项目 NuGet 包 | 既有程序集名 | 代码命名空间 |
| --- | --- | --- | --- |
| `Abp` | `Du.Abp` | `Abp` | 保持原有 `Abp` / `Abp.*` |
| `Abp.AspNetCore` | `Du.Abp.AspNetCore` | `Abp.AspNetCore` | 保持原值 |
| `Abp.EntityFrameworkCore` | `Du.Abp.EntityFrameworkCore` | `Abp.EntityFrameworkCore` | 保持原值 |
| `Abp.Web.Common` | `Du.Abp.Web.Common` | `Abp.Web.Common` | 保持原值 |
| `Abp.ZeroCore` | `Du.Abp.ZeroCore` | `Abp.ZeroCore` | 保持原值 |

**包名不等于命名空间，也不要求与程序集名相同。** `yopichy` 已经通过独立 `AbpLts.*` PackageId、保留 `Abp.*` 程序集和代码名称的方式提供了实际例子；本项目采用的是用户自己的 `Du.Abp*` 包身份，不复用其他维护者的包名。[A2]

核心项目的意图可表达为：

```xml
<PropertyGroup>
  <TargetFramework>net10.0</TargetFramework>
  <AssemblyName>Abp</AssemblyName>
  <RootNamespace>Abp</RootNamespace>
  <PackageId>Du.Abp</PackageId>
</PropertyGroup>
```

这里的 .NET 10 是首条维护线的建议目标；`PackageId` 映射与命名空间约束则是已经确定的规则。此示例不代表已经发布了相应版本。

### 1.2 “命名空间不变”的能力边界

保持类型名称可以减少源码迁移，并有助于维持使用类型名的集成点，但不能单独保证完整兼容。升级 EF Core、AutoMapper 或运行时仍可能改变方法签名、依赖解析、行为和部署要求。

因此，兼容性至少需要分开验证：

1. **源码兼容：**原有 `using Abp...`、类型引用和受支持的公共 API 能否继续编译。
2. **二进制兼容：**已编译扩展与实际程序集身份、签名和公共 API 是否匹配；不能凭名称不变直接承诺。
3. **行为兼容：**租户过滤、权限、UoW、事务、审计和异常处理是否保持预期语义。
4. **数据兼容：**既有数据库、Blob 名称、缓存值、持久化任务和序列化数据能否继续使用。
5. **发行兼容：**包依赖、目标框架、安装步骤和部署要求是否清楚且可执行。

## 2. 从 Silo 借鉴什么

Silo 是从 MinIO 派生的独立对象存储项目。其公开宣言把独立交付、兼容协议和已有数据、持续安全维护作为主要方向。我们能借鉴的是它已经公开实现的工程机制；现有证据不足以据此推导出多年治理稳定、所有部署可无风险回退或确定的商业成功。[S1]、[S2]

本次参考的 Silo 源码快照为 `d66020003cb20f07c765f71c0a060c9ef986f545`；最新已核实发行标签为 `RELEASE.2026-11-12T00-00-00Z`，对应构建源码 `44e848fedf8cec3d8c0da4b1aa8422390a2b7a8b`。[S1]、[S7]

| Silo 已公开的做法 | 对本项目的具体启发 | 采用时的边界 |
| --- | --- | --- |
| 独立产品与发行身份，同时保留 `MINIO_*`、相关请求头、路径和存储约定 | NuGet 改为 `Du.Abp*`，公共代码契约继续使用 `Abp.*` | S3 协议兼容不能直接证明 .NET 二进制兼容 |
| 用 rebrand guard 检查哪些旧标识必须保留 | 把命名空间、程序集、公共类型和包名映射规则做成自动检查 | 不能只靠全仓库字符串搜索，更不能全局替换 `Abp` |
| 旧版本写入、新版本读写、再由旧版本读取的测试 | 对代表性应用建立升级和有条件回退验证 | 只对实际测试的组合负责，不承诺任意版本回退 |
| 检查发布提交本身的构建和安全结果 | 发布必须绑定实际源码 SHA、对应测试结果和最终包 | PR 临时合并提交或依赖提交成功不等于发行验证 |
| 服务器、Console、客户端、打包工程形成配套交付 | 同时照顾框架包、模板、迁移说明和真实消费者 | 不必为独立品牌重写所有可继续使用的上游组件 |
| 公开安全处置记录，包括不受影响与无需新补丁的判断 | 每项重要上游修复、依赖公告都留下适用性、测试和发行记录 | 一次扫描结果只是当时快照 |
| 明确维护范围与责任，并提供可阅读的贡献和维护说明 | 先支持一条主维护线和有限模块矩阵，说明维护者与支持边界 | 不因使用“LTS”字样就作出无法兑现的期限或 SLA |

上述机制分别可以在宣言、兼容性说明、改名检查器、升级脚本、发布工作流、安全记录和组件规范中核查。[S2]—[S12]

### 2.1 最值得迁移的原则：更改交付身份，保护使用者依赖的契约

Silo 保留旧协议及运维兼容入口，是为了让已有客户端和数据继续工作。本项目需要同样明确地区分“发行身份”与“代码契约”：

- 新身份体现在 NuGet 包、项目说明、维护者、发行记录和支持入口。
- 原有 `Abp.*` 命名空间及类型名称不随品牌变化。
- 原有配置项、接口、持久化格式和数据库语义不作无目的的改名。
- 代码生成器、模板、文档示例和扩展模块也遵守同一规则。

### 2.2 不能直接照搬的部分

Silo 的 `minio-upgrade.sh` 使用 Docker 容器夹具验证固定版本组合，覆盖部分对象、权限和升级场景。用户的应用部署要求是 Linux、macOS、Windows 原生运行，因此这里采用它的验证顺序，改用本机应用进程和受支持的数据服务，不要求引入 Docker、Kubernetes 或虚拟机来运行应用。[S5]

Silo 的升级测试也不是数据库 schema 任意降级的证明。若本项目修改数据库结构或持久化格式，必须分别说明：可原地回退、需要恢复备份，还是该升级不可降级。

Silo 的发行资产包括三平台二进制，但当前 Go 测试工作流主要在 Ubuntu 上运行，并包含交叉编译。三平台产物不等于三平台都完成原生全量测试；本文提出的应用原生验收是本项目需要自行落实的要求。[S7]、[S11]

Silo 的许可证、维护组织和依赖生态与 ASP.NET Boilerplate 不同。工程经验可以复用，许可责任仍应按本项目及具体第三方依赖逐项确认。[A1]、[S1]

### 2.3 用真实消费者验证维护价值

公开下游中，可以核实两种不同层次的采用：RAGFlow 的默认 Compose 配置使用 Silo 镜像，同时保留旧的环境变量和健康检查入口；BuildKit 的具体提交则把 S3 集成测试服务端和客户端切换到 Silo / mcli。[S13]、[S14]

前者是默认部署配置采用，后者是集成测试采用，都不能推导成所有下游用户已经生产迁移。对本项目，更有用的验收证据是一个真实旧 ABP 应用通过实际 `Du.Abp*` 包完成升级，再由另一个独立消费者验证安装和关键路径。

Silo 还明确限定协同维护组件，并继续复用满足要求的上游 SDK。这支持一个适合本项目的选择：维护用户真正依赖的完整组合，同时让可以继续复用的成熟依赖保持独立，不为发行品牌扩大 fork 范围。[S12]

## 3. 用有限范围形成第一个可靠发行版

### 3.1 建议的首版范围

首版围绕“.NET 10、既有 Abp API 使用习惯、重要修复、独立包、可执行迁移”收敛。保留现有模块系统、Castle Windsor 和拦截架构作为起点；核心 DI 重写、全面 NativeAOT、默认对象映射替换分别立项。

| 层次 | 建议范围 | 验收重点 |
| --- | --- | --- |
| 框架基础 | 核心、模块加载、DI、UoW、授权、验证、审计 | 初始化、生命周期与拦截语义 |
| Web | 业务实际使用的 ASP.NET Core 与公共 Web 支持包 | 启动、请求处理、认证授权、错误响应 |
| 数据访问 | EF Core 及首批真实使用的数据库提供程序 | 事务、迁移、过滤、并发、批量更新 |
| 多租户与身份 | 若现有应用需要，则纳入 Module Zero / OpenIddict 相关包 | 租户隔离、权限、身份数据保存 |
| 可选集成 | 按真实消费者需求纳入 Redis、后台任务、邮件、Blob 等 | 包依赖闭包与最小集成用例 |
| 后续研究 | Mapperly、编译期拦截、其他 ORM 和更多提供程序 | 独立设计、验证与支持决定 |

维护范围应列出具体模块和版本，不能只写“支持旧 ABP 全生态”。保留源码但未正式支持的模块，应明确标注；不要因为源码树中还有项目，就把它列入首版承诺。

### 3.2 单一事实来源

为正式发行的每个项目维护一份包映射与支持清单，至少包含：源码项目、原 PackageId、新 PackageId、AssemblyName、RootNamespace、目标框架、内部依赖、发行状态和消费者测试。

打包脚本、依赖检查和发布说明应读取或核对这份清单，避免三套手工列表逐渐失配。初期可用一份简单的结构化文件完成，无需建设额外平台。

## 4. 分阶段执行路线

下列阶段以验收结果推进，不预先承诺未经容量评估的交付日期。

| 阶段 | 核心工作 | 阶段产物 | 进入下一阶段的条件 |
| --- | --- | --- | --- |
| R0 固定基线与规则 | 固定上游 tag/SHA；记录硬约束；盘点包和真实消费者 | 上游记录、包映射、支持矩阵、公共 API 基线 | 能复现基线；迁移范围明确 |
| R1 维护与升级 | 审查重要上游修复；迁移 .NET 10；处理依赖和 API 变化 | 小而可追溯的提交、回归用例、变更说明 | 核心行为测试通过，重要修复逐项有结论 |
| R2 独立包交付 | 改 PackageId；转换内部依赖；统一版本；修复打包脚本 | `Du.Abp*` 候选包、符号包、依赖清单 | 命名空间和程序集检查通过，消费者无新旧框架混装 |
| R3 消费者迁移 | 从候选包源安装、升级代表性应用并回退 | 可运行模板、迁移指南、实测包清单及平台结果 | 从干净检出复跑安装，用同一组测试数据在原版、升级与回退后完成登录及受权限控制的业务请求 |
| R4 首次正式发行 | 对最终提交执行门禁；记录源码与产物关系；发布 | tag、NuGet 包、发布说明和支持矩阵 | 发行证据完整，实际发布包完成消费者验证 |
| R5 持续维护 | 跟踪上游和依赖公告；处理回归；更新支持状态 | 定期补丁、维护记录、下一次候选版本 | 每次补丁重复必要门禁 |
| R6 有边界地演进 | 评估 Mapperly、Serilog、编译期拦截等 | 可选模块、独立设计与迁移说明 | 不破坏命名空间硬约束，且收益覆盖维护成本 |

### R0：固定可追溯的基线

R0 已于 2026-11-24 验收。基线范围为官方 `v10.5.1` 源码上的首批五包及 macOS ARM64 环境的 .NET 9 回归，EF Core 套件使用 SQLite。

以官方稳定 tag 为来源，另外记录需要吸收的 tag 之后修复。按本次研究，官方最新已核实版本是 `v10.5.1`；`#7219` 位于该版本之后，需单独审查。[A3]、[A4]

不要把其他 fork 的较大版本号当成“已经包含上游全部修复”。例如 `AbpLts 10.5.3` 是独立发行线，并未自动包含官方 `Abp 10.5.1` 的全部变更；详细差异见配套文档。

建立公共 API 与命名基线时，保存完整类型名、公开方法签名、程序集身份和关键资源名称。基线必须来自固定源码或已确认的包，不用会持续变化的默认分支名称代替。

上游提交、首批五包、实际依赖图、公共 API 与回归结果见 [R0 维护基线](release-baseline.json)。[复验手册](baseline-evidence/README.md) 提供还原、构建和测试命令。

### R1：先保住重要行为，再处理可选架构变化

将上游修复、运行时升级、依赖升级和本项目功能分别整理成可审查的提交。优先验证多租户、查询过滤、软删除、认证存储、事务、权限和 Webhook 等涉及正确性与隔离的路径。

对于已经包含在选定 tag 中的修复，重点是验证它们经过 EF Core 10 等适配后仍然成立；对于 tag 之后的修复，记录是否移植、如何调整以及测试结果。不要仅凭提交是否出现在祖先图中判断等价补丁是否已经吸收。

`yopichy` 的 .NET 10、EF Core API、测试宿主和打包改动可以作为直接研究起点；保留原作者和来源 SHA。引入任何依赖大版本时，同时检查许可、API 和行为变化。[A2]、[A5]

**2026-11-24 首项补丁已验收。** 在 R0 基线的 .NET 9 环境中吸收了上游 #7219，完成 Release 构建和三套回归。框架提交 `d08617b51bb7c7e5d0bea942e7e10b2677240c35` 已推送到 fork 的 `dev`，主仓接入提交为 `9964e312b36499b625bd2b7615da741b87b8f003`。该补丁作为 .NET 10 / EF Core 10 迁移的行为对照。[补丁验收记录](r1-efcore-query-filter.md) · [稳定规范](../../openspec/specs/efcore-query-filters/spec.md) · [首项归档](../../openspec/changes/archive/2026-11-24-adopt-efcore-query-filter-fix/)

**2026-11-25 运行时迁移完成 Git 交付与归档。** 三套 .NET 10 核心回归为 1341 通过、0 失败、2 项既有跳过。六个 .NET 9 调用方通过默认目标 Release 构建，定向验收包括 Module Zero 的四项批量更新。默认 Windows 解决方案在 UTM ARM64 和 GitHub x64 各取得 2805 通过、0 失败、9 项既有跳过。框架原样合入实测源码树。[验收与交付记录](r1-dotnet10-runtime-migration.md) · [框架 PR #1](https://github.com/dusdong/aspnetboilerplate/pull/1)

| 顺序 | 交付物 | 进入下一项的依据 |
| --- | --- | --- |
| R1 首项 | 在 `net9.0` 上吸收上游 #7219，记录修复候选与 R0 的差异 | 查询结果与异常契约有实际用例覆盖，三个套件的结果、五包的 API 和依赖差异均可核对 |
| R1 运行时迁移 | 以通过验收的补丁候选为起点，迁移首批五包及其测试到 .NET 10 / EF Core 10 | 先核对 R0 中 11 个项目的引用图及同仓其他引用方，再决定目标框架调整范围。候选须完成 Release 构建和行为对照，并逐项说明上游重要修复在新运行时的验证状态 |
| R2 至 R3 | 用干净的最小消费者安装五个 `Du.Abp*` 候选包，再迁移选定的免费模板入口 | R2 核实还原图、程序集与实际加载结果；R3 先补齐所选入口的依赖，再验收启动、升级、回退及所声明的平台与 Provider |

R4 的发行对象是通过上述验收的具体候选。后续补丁进入 R5；R6 的架构替换由实际消费需求单独排期。

### R2：完成包依赖整体迁移

首批五个包的双目标实测组合及复跑命令见 [R2 候选包消费验收](r2-core-package-consumption.md)。

只修改顶层 PackageId 不够。正式包的内部依赖应指向本项目对应的 `Du.Abp*` 包，原有框架程序集仍叫 `Abp*`。

必须检查实际 `.nupkg` 的 nuspec 与消费者还原结果：

- 本项目框架包之间的依赖是否全部转换。
- 第三方插件是否把上游 `Abp*` 或另一发行线 `AbpLts*` 重新带入依赖图。
- 包是否包含正确的 DLL、目标框架、符号、许可证和源码仓库信息。
- 生成器和分析器是否按预期供消费者使用。
- 打包是否依赖本机缓存、私有 feed 或旧 `bin/obj` 产物。

第三方包不能仅因名字包含 `Abp` 就自动改名；对其依赖和兼容性逐项处理。某个插件无法切换到新包身份时，应先确认支持办法，而不是允许两套同名框架程序集无意混装。

### R3：验证升级路径和实际消费者

固定模板 `2e953687` 的原版 `net9.0` Web.Host 基线覆盖还原、Release 构建和 11 个 ABP 包的运行资产。R2 的五个核心包已完成双目标独立后端验收。基线记录的其余六个 ABP 包已有下表的独立消费候选，补包缺口从 **6 降至 0**。[原版 Web.Host 基线](r3-web-host-baseline.md) · [R2 双目标验收](r2-core-package-consumption.md)

| 独立候选批次 | 覆盖的 Web.Host 包缺口 | 本机验收 |
| --- | --- | --- |
| `10.5.1-r3.1` | `Du.Abp.AspNetCore.SignalR`、`Du.Abp.Castle.Log4Net` | [SignalR 与 Log4Net 消费](r3-signalr-log4net-candidates.md#消费验证器复验记录) |
| `10.5.1-r3.3` | `Du.Abp.Zero.Common`、`Du.Abp.ZeroCore`、`Du.Abp.ZeroCore.EntityFrameworkCore` | [Module Zero 消费](r3-module-zero-candidates.md#验收记录) |
| `10.5.1-r3.4` | `Du.Abp.AutoMapper`，使用 `Du.AutoMapper 14.0.0-r3.4` 与 `Du.AutoMapper.Collection 11.0.0-r3.4` | [AutoMapper 消费](r3-automapper-downstream.md#消费验收记录) |

完整 Web.Host 按下表依次验证原版行为、同目标换包、运行时升级和回退。

| 顺序 | 操作 | 通过条件 |
| --- | --- | --- |
| 1. 原版运行对照（已通过） | 用原版 `net9.0` Host 连接 SQL Server，按模板的 `angular/yarn.lock` 安装客户端，保存登录前备份并实际恢复到新库。 | 两轮用 `Pages.Users` 账号登录，通过相同的关键词读到唯一预期用户。恢复轮在恢复库新增 1 条成功登录记录，源库增量为 0。[最终两轮结果](r3-template-runtime-baseline.md#2026-11-25-返修复验) |
| 2. 同目标换包（已通过） | 从干净检出和空 NuGet 缓存开始，保持 `net9.0` 和前端输入，切换为维护候选，构建并启动 Web.Host。 | 核对还原图、Host 输出与实际加载的程序集来源，确认 11 个原版 ABP 包均由对应维护包提供。把最终返修轮的登录前备份恢复到候选库和独立对照库，复跑登录与用户查询，两库计数从 `1/1` 变为 `2/1`。[正式运行结果](r3-template-net9-packages.md#正式运行结果) |
| 3. 运行时升级（本机已通过） | 将模板迁到 .NET 10 / EF Core 10，核对维护包资产与 SQL Server Provider，从同一候选库的 `2/1` 登录状态接续。 | Migrator 连接同一库，迁移历史和业务表结构完整保留。Angular 使用同一账号和请求读到唯一用户 3；候选库新增唯一登录行，两份备份均独立恢复并回读。[正式运行与双恢复点](r3-template-net10-upgrade.md#2026-11-25-正式运行验收) |
| 4. 回退（本机已通过） | 分别从升级后与升级前备份重建独立库，再以原版 Release Migrator、Host 和冻结 Angular 客户端逐库验收。 | 原版能在两个恢复点登录并用 `Pages.Users` 查询到唯一用户 3。实际 SQL 连接证明读写正确，两库逐行核对成功登录。直接切回保留升级轮写入，选择升级前备份会舍弃它。[回退步骤、实测组合与写入边界](r3-original-template-rollback.md#切回步骤与数据边界) |

建议使用来自真实业务的最小数据集，至少包含不同租户、软删除记录、权限、持久化任务、认证数据，以及业务实际使用的 Blob 或缓存结构。测试必须避免泄露真实生产个人数据。

三平台验证应让应用在 Windows、Linux、macOS 对应环境中以原生进程运行。数据库可使用支持矩阵中明确的受支持服务实例，不能因为一个提供程序在某个平台可还原，就宣称完整数据库部署也受支持。

### R4：发布绑定精确提交和最终产物

参考 Silo 对发布提交与通过检查之间关系的明确核验，本项目应保存“源码 SHA → 测试记录 → 候选包 → 消费者结果 → 正式发行”的对应关系。[S6]、[S7]

建议流程：

1. 以 R3 通过的整套包清单为起点，确定正式包版本及其内部依赖范围。例如，Module Zero 的候选 nuspec 已精确引用 `[10.5.1-r3.3]` 和 `[10.5.1-r2.1]`。若采用统一正式版本，先更新这些依赖，再冻结最终源码 SHA 和包清单。[候选包依赖表](r3-module-zero-candidates.md#消费闭包与运行)
2. 对该 SHA 执行 Release 构建、必要回归、命名检查和依赖审查。
3. 用最终源码按正式版本重新打包，核对各包 nuspec 的依赖范围和符号包，记录供发布的最终产物摘要。若签名改变字节，以签名后的包作为验收输入。
4. 复用 R3 的模板、测试库和迁移步骤，从空缓存只用这套最终框架包还原，核对实际依赖图，复验启动、升级、登录和受权限控制的业务请求。
5. 按发布授权建立 tag 并提交包。依赖主包先经匿名下载、仓库验签和冻结内容核对，再提交对应下游。分别登记公开主包及符号。
6. 从公开包源使用空缓存验证实际发布包，并在空库实跑安装说明。通过公开消费和新库验收后发布 GitHub Release，附精确提交、支持范围、安装步骤及校验清单。

绿色 badge、不同 SHA 的历史测试、自动 dependency submission，均不能替代候选版本的验证。NuGet 包应按不可变发行物管理，出现错误时发布新版本，不用覆盖同一版本来隐藏变化。

### R5：把持续维护控制在可承担的规模内

R4 的交接基线是已公开的 `v10.5.1`。macOS ARM64、SQL Server Developer `16.0.4236.2` 和固定模板通过 `net10.0` 新库安装，实测运行时 `10.0.15`。同批 `net9.0` 存量迁移在 `9.0.10` 实测，可用作迁移对照，微软已于 2026-11-10 结束 .NET 9 支持。公开源同库接续使用冻结 Angular 客户端。原版两条回退路径沿用同批冻结源的历史实测。[公开发行与支持范围](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1) · [回退实测](r4-release-candidate.md#实测支持矩阵)

待补的 R4 组合包括 Windows、Linux 原生应用、其他数据库 Provider 和不同 Angular 组合。后续支持范围按实际证据更新。[公开发行规范](../../openspec/specs/public-package-release/spec.md) · [首发归档](../../openspec/changes/archive/2026-11-26-publish-r4-first-public-release/)

首轮按一条主发行线完成。三仓上游修复、四个入口的实际包图及两套共享运行时已有可复查记录。出现真实消费者需求并具备相应验证能力时，再考虑并行维护分支。[维护决定](r5-first-maintenance-review.md#本轮决定) · [下轮检查点](r5-first-maintenance-review.md#下轮检查点)

旧包共享集合计划的正式调用随预热顺序稳定变化，冷启动两种注册顺序出现同一异常。候选的正式调用和预热均符合预期。引擎、Collection 和适配器的三对归档已冻结，独立 ABP 消费者验证对象更新、按键集合与关系型投影。实际依赖固定到对应候选版本，适配器仍精确引用 `Du.Abp [10.5.1]`。[共享集合计划对照](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/shared-collection-plan-observation.md) · [三包冻结与独立消费](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md)

固定模板已用候选加十个公开 R4 包实测 `net10.0` 新库、两代同库接续。在固定 `net10.0` 与同一 SQL Server 库切换包并回退，候选及回退阶段均通过 Angular 授权查询读回首阶段经应用创建的租户用户，三阶段各自核对实际包图、编译输出和加载资产。[模板结果及发行交接条件](r5-automapper-template.md)

#### 2026-11-26 收尾复核

主仓 `main` 的 `99f44b7` 固定引擎 `d264ff75`、Collection `d22aaf5` 和经典框架 `7933e71`。GitHub 三条本轮推送分支的头提交已回读，三个生产 gitlink 对应的源码树与原批次逐一相符。该提交下两项变更均已归档，活动变更为零。GitHub 最新发行是 `v10.5.1`；当日 NuGet 三个包的版本索引仅列 R4 版本。[主仓交付](https://github.com/dusdong/du.aspnetboilerplate/commit/99f44b730458ecacbc086b4ffc5dfc0ace367015) · [冻结来源与 gitlink](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md#批次交接) · [公开发行](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1)

| 复核对象 | 证据与范围 |
| --- | --- |
| 归档与业务 | 收尾日志记录 OpenSpec 15/15、Python 45/45、R4 公开消费回归 12/12、资产诊断 9/9，以及从提交后 HEAD 离线回读两个归档、13 个维护包、407 个本地链接和 125 个锚点。SQL Server、Host 和浏览器结果来自相应模板实跑轮。[模板结果](r5-automapper-template.md) · [迁移审查](r5-runtime-migration-review.md) |
| 缓存与保留证据 | 58 个缓存目录已按清单删除，未留恢复副本。原占 11.49 GiB，清理前后共享卷可用量的快照差为 10.38 GiB。清理前后登记的 1,142 项摘要一致。本次重新读取文件，1,141 项仍逐字节一致，包括冻结包、7 份 SQL 备份和正式报告。唯一差异是工作日志 `任务记录.md` 后续追加 824 字节，原 32,744 字节的摘要仍匹配。冻结批次离线复核通过。 |

验证机保留两份原始交接记录，位于主仓 Git 目录的 `review-r5-runtime-migration-readiness/closeout/main/handoff.md` 和 `closeout/cleanup/handoff.md`（共用前述任务目录）。其他检出可用上表所引提交和归档文档复核源码与批次关系。

后续三包待发批次完成复验和发行前演练，已同步候选验收规范并归档。新制包引擎 `54f6277a` 已交付到登记子仓的 `maintenance/v14`。本次归档的协调提交固定该引擎、两项沿用生产提交及同一模板。待发批次与 `99f44b7` 对应的原冻结批次分别登记。[新引擎交付](https://github.com/dusdong/AutoMapper/commit/54f6277af80783e5d07e896f75df0dcc0c4b4502) · [新批次与目标核对](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md)

#### 2026-11-27 发行准备复核

主仓协调提交为 `cebc3e38a511783092963893bf5ad3161d0f0a19`。GitHub 的 `main`、引擎 `maintenance/v14` 和协调提交中的四个 gitlink 已回读。引擎为 `54f6277a`，Collection 为 `d22aaf58`，经典框架为 `7933e71f`，固定模板为 `2e953687`。GitHub Actions 运行 `45846709281` 对该主仓提交执行了 R0 基线复验，`verify-r0` 于北京时间 11 月 26 日 23:14:42 成功结束。[主仓提交](https://github.com/dusdong/du.aspnetboilerplate/commit/cebc3e38a511783092963893bf5ad3161d0f0a19) · [CI 运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45846709281)

该提交交付时活动变更为零。发行准备阶段的复核通过稳定规范 15/15、归档任务检查 19/19。归档后 `net9.0`、`net10.0` 两份原始构建报告各有 9 个通过阶段、退出码 0，读取的九份归档制品均与交付提交逐字节对账。两轮输入是 **R4 已公开签名包**。其中 `net10.0` 外层记账脚本因 zsh 只读变量退出 1，构建子进程及报告已单独核对。R5 的六份归档当时通过了离线复核。R5 公开包的消费结果见下节。[归档与发行前演练](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-rehearsal.md) · [批次与发行清单摘要](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md#实物清单)

发行准备复核时，GitHub 最新 Release 为 `v10.5.1`，目标仓库没有 `v10.5.2` tag，NuGet 三个版本索引仅列出 `14.0.0`、`11.0.0` 和 `10.5.1`。[当时的公开发行](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1) · [发行前版本核对](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/source-and-engine-validation.md#版本与原批次核对)

#### 2026-11-27 公开发行收尾

附注标签 `v10.5.2` 指向生产组合 `cebc3e38`。发布者公开源新装通过 16/16 个阶段，同库升级通过 26/26 个阶段。独立消费者按固定指南从空缓存新装，Migrator 退出 0、数据库有 30 条迁移记录，Swagger 返回 HTTP 200。[公开发行验收](r5-public-release.md) · [三项消费实测](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/consumption-validation.md)

收尾提交 `0d42db5` 已交付至 GitHub `main`。该提交下发行任务 6/6 已归档、活动变更为零，稳定规范 15/15、归档 20/20，36 组本地链接检查通过。该提交的路径未命中 R0 工作流，发行工作流由手动触发，GitHub 对此 SHA 返回 0 次运行。协调提交的 R0 运行另有记录。[收尾提交](https://github.com/dusdong/du.aspnetboilerplate/commit/0d42db5eb4ff620863b5f58c7eb9c675c2f67d87) · [发行归档](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/tasks.md) · [协调提交 R0 运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45846709281)

#### 本轮缓存处置

2026-11-27，维护者确认清单后，52 个 NuGet 缓存目录已全部删除，逐项确认路径均已消失。26 个 `packages` 与 26 个 `http-cache` 在删除前经 `du -sk` 实测共占 13,842,736 KiB（13.20 GiB）。共享 APFS 卷的可用空间从 18,293,248 KiB 增至 30,575,380 KiB，观测净增 12,282,132 KiB（11.71 GiB）。

清理前后独立重读的 66,068 项原登记证据均与原快照匹配，包括冻结包、十个沿用包的验签日志、15 份 SQL 介质（含演练副本）、原始报告及生产 ApiCompat 缓存。22 个日志软链仍指向 `/dev/null`。清理前已存在的 500 个收尾文件也已逐项对照，摘要一致。冻结批次通过离线核验。复跑旧验收时，在新目录先还原再构建。

验证机的原始清单位于主仓 Git 目录的 `prepare-r5-mapping-patch-release/closeout/cache-inventory/cleanup-preview.tsv`，SHA-256 为 `994b59a1cd2b58d4c345c954d732a6dff870784cf4ca1e87666d05c13e6a2479`。逐项处置和复核证据见同一 Git 目录下的 `publish-r5-mapping-patch/close-cache/handoff.md`。上一轮已删除的 58 项见上节。

#### 2026-11-27 公开补丁维护决定

同一公开版本的四图共核对 207 个实际或原上游身份与版本组合。原名命中的三个 AutoMapper 公告都有本版同摘要实物的回补证据，内建集合上下文已随本版修正。**维护包无需补丁。** CVE-2026-56158 的精确组件与版本范围继续待 Microsoft 补充，四个入口的实际运行时按已确认的服务状态处理。[上游及公告审查](r5-public-patch-review.md#三仓六分支与上轮未决项) · [共享运行时](r5-public-patch-review.md#共享运行时与-cve-2026-56158)

| 负责方 | 行动及检查点 |
| --- | --- |
| 维护包 | 沿用公开组合。按六条分支、NuGet 全页、GitHub 重叠水位续查。收到确认适用的修复或 14 基线的定向兼容场景后复审。 |
| 模板 | 以固定提交和四入口还原图为消费基线，模板或依赖改变时重新验证两个入口。 |
| 运行环境 | .NET 9 已停止服务，迁至支持中的 .NET 10。当前两套共享框架的基线为 `10.0.15`，按官方后续服务版复查，并继续跟踪 CVE-2026-56158 原始范围。 |
| 应用 | 按部署实测两个入口的加载版本并复核包图，结合实际配置验证集合映射与回退点。更换平台、Provider 或 Angular 产物后形成对应实测。 |

[四方详细行动](r5-public-patch-review.md#本轮维护决定) · [精确续查水位](r5-public-patch-review.md#下轮检查点与验证边界)

审查收尾提交 `800cdbe` 已交付至 GitHub `main`。稳定规范新增一条要求和四个场景，归档任务 6/6。归档前全仓严格校验 16/16。该提交下活动变更为零，稳定规范 15/15、归档 21/21，收尾记录检查了 64 组本地链接和 38 个锚点。该提交的改动未命中 R0 推送触发路径，GitHub Actions 运行数为零。[收尾提交](https://github.com/dusdong/du.aspnetboilerplate/commit/800cdbea50fe7ed2b481f2d1303a1d0c64a3c37c) · [稳定规范](../../openspec/specs/maintenance-release-review/spec.md#requirement-跨公开补丁的审查能说明既有结论的适用范围) · [审查任务归档](../../openspec/changes/archive/2026-11-27-review-r5-public-patch-baseline/tasks.md)

#### 公开补丁维护审查的原计划

审查启动时，`review-r5-public-patch-baseline` 要回答使用 `v10.5.2` 的应用是否还需要维护包补丁，以及模板或部署环境应承担哪些行动。完成结论见上节。[归档提案](../../openspec/changes/archive/2026-11-27-review-r5-public-patch-baseline/proposal.md)

1. **确定消费者实际安装了什么。** 用公开校验附件和同一次升级的四张原图，逐入口列出三个更新包、十个沿用包和传递依赖相对 R4 的差异。[R5 消费实测](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/consumption-validation.md)
2. **重新判断公告适用性。** 按新包图和原上游身份匹配存量及新修订公告，从上次完整位置接续三仓六分支和 Microsoft 服务公告。单独补核 CVE-2026-56158 的组件范围。[续查起点](r5-runtime-migration-review.md#共享运行时与下轮检查点)
3. **给出维护决定。** 按包、模板、运行环境和应用分别登记行动，结论为需补丁、无需补丁或暂不能判定，并留下依据和下一次重查条件。Windows、Linux、其他 Provider 和 Angular 组合按实际消费者需求安排验收，R6 按既有立项条件推进。[维护审查规范](../../openspec/specs/maintenance-release-review/spec.md)

#### 公开包同库回退与后续检查

公开包三阶段在 macOS ARM64、固定 `net10.0` 模板、.NET 和 ASP.NET Core `10.0.15`、SQL Server Developer `16.0.4236.2` 与冻结 Angular 通过。各段从独立空缓存还原两个入口，首末包图一致，中段符合已登记的三个映射包及四条约束变化。回退 R4 使用同一管理员会话分别查回 R4 创建的 A 和 R5 创建的 B，保留三段迁移历史和成功登录行。[三阶段证据与复跑](r5-automapper-template.md#公开-r4r5-同库回退实测) · [映射消费稳定规范](../../openspec/specs/automapper-package-consumption/spec.md#scenario-切回公开旧版后仍可查询新版写入) · [实施与验收归档](../../openspec/changes/archive/2026-11-27-validate-r5-public-package-rollback/tasks.md)

历史本地候选切换验证了 R4 创建的一个用户。备份恢复按各自选定的历史恢复点验证，恢复点之后的写入会舍弃。其他业务、平台、Provider 和客户端组合仍按实际消费者需求验证。[公开发行与历史证据](r5-public-release.md#公开消费与回退证据)

2026-11-27，收尾提交 `75ca30d` 已交付至 GitHub `main`。该提交下五项任务全部归档，稳定规范新增三个场景，活动变更为零。Python 回归 56/56，稳定规范 15/15，归档检查 22/22。归档后的 CLI 探针读到五份规划制品。同库业务结论来自此前 22/22 阶段的正式实跑。GitHub Actions 为此提交通过了 R0 基线复验。[收尾提交](https://github.com/dusdong/du.aspnetboilerplate/commit/75ca30d93ebe3855c03d85f5020d202f4e1371f9) · [R0 运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45947407474) · [同库实跑与清理边界](r5-automapper-template.md#公开-r4r5-同库回退实测)

**公告续查按来源变化启动。** GitHub 包公告从 `2026-11-27T03:08:35Z` 重叠查询，Microsoft 服务公告从 `03:08:30Z` 接续。CVE-2026-56158 等待 MSRC、CVRF 或 CVE Program 提供现代 .NET 的产品、组件和版本范围，再对照四入口实际加载资产。若指向独立包，再按包图判断维护包责任。Windows .NET Framework 的文档更正单独保留。上游六条分支与四项待核实或暂缓的兼容问题按原检查点复查。[服务公告证据](r5-public-patch-review.md#共享运行时与-cve-2026-56158) · [各来源续查条件](r5-public-patch-review.md#下轮检查点与验证边界)

#### 消费者指南的独立验收

`document-r5-consumer-package-rollback` 的指南及实跑已完成。在干净目录用固定模板、匿名发行附件和 nuget.org 构建 R4、R5，各版 Web.Host 和 Migrator 分别核对 13 个、10 个维护包。三阶段沿用同一座测试库及 30 个迁移 ID，末段直接运行首段封存的 R4 产物。独立演练覆盖 macOS ARM64、`net10.0`、SQL Server Developer `16.0.4236.2` 的后端 API。Angular 和备份恢复以各自的历史实测为准。[消费者指南](r5-consumer-package-rollback.md) · [独立验收结果](r5-automapper-template.md#独立消费者验收) · [历史 Angular 实测](r5-automapper-template.md#公开-r4r5-同库回退实测) · [历史备份实测](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/consumption-validation.md#sql-server-与租户业务) · [归档任务](../../openspec/changes/archive/2026-11-27-document-r5-consumer-package-rollback/tasks.md)

建议的维护活动包括定期检查上游 PR/发行、依赖公告、消费者回归和支持矩阵；频率由实际容量确定。外部支持期限、响应时间和商业 SLA 应在有能力兑现后明确发布，不能从“LTS”名称中推定。

每项重要问题至少留下：来源、适用模块、影响判断、处理决定、修复提交、测试、首次包含该修复的发行版本。对于不受影响、已经修复或暂不升级的情况，也记录理由和复核条件。

同时约定停止维护时的处理方式：公开受影响的版本和范围，保留源码、tag、包映射和最后可用的迁移说明，给出接续维护或迁移入口。Silo 宣言中的发行节奏与退出条件属于其公开承诺，本项目应按自身能力制定，不能照抄为已保证的服务期限。[S2]、[S9]、[S10]

### R6：将架构演进作为可选择的能力

中央包管理和独立日志模块通常可以先以小范围工程变化引入。Mapperly、编译期拦截和替换 Windsor 涉及更多契约，需要单独证明它们对现有应用的收益与迁移成本。

候选模块仍必须保持适当的 `Abp.*` 命名空间，NuGet 包使用 `Du.Abp.<Module>`。发布新包不构成修改既有公共类型命名空间的理由。

## 5. 将兼容性硬约束落实为发布门禁

### 5.1 必须能自动发现的错误

| 检查 | 检查对象 | 不通过的典型情况 |
| --- | --- | --- |
| 命名空间检查 | 框架源码及生成代码 | 把 `namespace Abp...` 改成 `namespace Du.Abp...` |
| 公共类型名比较 | 实际构建的程序集 | 既有公共类型全名因品牌改名而变化 |
| 程序集名称比较 | 输出 DLL 元数据与包内容 | 既有 `Abp.dll` 被改成 `Du.Abp.dll` |
| 包映射检查 | 包清单与 nuspec | 首个核心包误命名为 `Du.Abp.Abp`，或遗漏某个内部依赖 |
| 依赖闭包检查 | 消费者还原的依赖图 | 意外混入原 `Abp*` 与另一发行线的同名程序集 |
| 源码/二进制兼容检查 | 公共 API 基线与代表性扩展 | 名称虽然保留，但签名或加载行为出现未说明变化 |
| 消费者测试 | 实际候选包 | 仓库测试通过，用户按文档却缺少生成器或运行依赖 |

命名空间检查宜使用编译器语法或元数据分析识别实际声明。`rg` 可用于快速审查，但单次正则搜索不能覆盖文件作用域命名空间、别名、生成代码和反射字符串的所有情况。

门禁的目标是防止兼容性退化。修复已有错误或更新 API 基线时，必须记录具体理由；**不得通过更新基线把 `Abp.*` → `Du.Abp.*` 的违约改名合法化。**

### 5.2 发布审查清单

- [ ] 既有 `Abp` / `Abp.*` 命名空间保持不变；公共类型全名未因包品牌迁移而变化。
- [ ] `Du.` 仅作为本项目 NuGet PackageId 前缀，没有进入框架代码命名空间。
- [ ] 既有 AssemblyName 与 RootNamespace 未因包名映射而变化。
- [ ] 包映射完整，内部依赖一致，消费者无意外混装。
- [ ] 目标框架、依赖和公共 API 变化已经记录。
- [ ] 当前上游重要修复逐项有适用性结论。
- [ ] 候选 SHA 的 Release 构建、关键回归和必要平台验证完成。
- [ ] 实际包的安装与升级步骤可以按文档复现。
- [ ] 回退能力及数据库/持久化格式限制已经写清。
- [ ] 发布说明、源码 SHA、包清单、支持矩阵和校验信息相互对应。

## 6. 最小文档与维护记录

建议在项目中形成以下少量、职责清楚的文档。文件名可以按仓库现有规范调整，内容应避免重复维护。

| 文档 | 应回答的问题 |
| --- | --- |
| 兼容性政策 | 哪些契约永久保留？什么变更需要迁移说明？ |
| 上游与补丁记录 | 基于哪个 tag/SHA？重要后续修复处理到哪里？ |
| 包映射与支持矩阵 | 哪些 `Du.Abp*` 包正式支持哪些平台、数据库和模块？ |
| 升级指南 | 如何替换包引用、升级运行时、处理插件和已有数据？ |
| 发布说明 | 本版本改变了什么、基于什么、验证了什么、有哪些限制？ |
| 安全与维护说明 | 如何报告问题、维护哪些版本、如何记录修复和退出维护？ |

首次发布说明至少列出本项目版本、对应上游、额外补丁、运行时和数据库矩阵、包身份映射、公共 API/行为变化、验证范围、已知限制以及回退说明。

贡献与 AI 开发规范中也应重复最核心的一句：**NuGet 改名只改变 PackageId；既有 `Abp.*` 代码命名空间永久不变。** 自动生成代码、批量重命名和迁移脚本都必须接受同一检查。

## 7. 采用顺序与完成标准

首条维护线按以下顺序推进。各阶段依据验证结果进入下一步。

1. **取得原版基线（R0，已验收）。** 已固定上游 `v10.5.1` 对照，核对首批五个后端候选的包身份和依赖，并保存原版构建、程序集与行为记录。维护要求见 [稳定规范](../../openspec/specs/maintenance-baseline/spec.md)，计划制品与任务见 [R0 归档](../../openspec/changes/archive/2026-11-24-establish-maintenance-baseline/)。
2. **迁移框架（R1）。** 复核上游修复与已选依赖，分别实现必要补丁和 .NET 10 迁移。用原版记录比较核心、Web 与 EF Core 行为，明确公共 API 和运行时差异。
3. **验证独立包（R2）。** 从首批后端候选生成 `Du.Abp*` 预发行包。核对实际包和干净消费者的还原图，验证框架包依赖闭合以及既有程序集、类型和命名空间。
4. **验证兼容组合（R3）。** 用实际候选包验证模板、代表性业务应用和支持平台。AutoMapper 与 Angular 各自跟踪依赖兼容，样例先覆盖多 DbContext 和拦截器，按测试证据扩大消费者和数据库范围。
5. **发行与维护（R4–R5）。** 把同一候选提交的构建、回归、包产物和消费者结果关联起来，依据实测结果发布支持矩阵、升级与回退说明，并维护一条主发行线。
6. **评估架构演进（R6）。** 根据真实消费需求独立评估 Mapperly、编译期拦截和其他架构变化。

首版是否完成，应以“用户能够按说明安装、迁移和确认兼容性，维护者能够解释每个关键差异及其验证结果”判断。仅有 fork 仓库、版本号、绿色 badge 或 NuGet 上传记录，都不能单独证明上述目标已经达到。

## 8. 参考资料与证据边界

以下为一手项目资料。标记为“建议”的内容是针对本项目的工程判断，不是 Silo 或其他维护者对本项目作出的承诺。默认分支、在线网页与包信息可能继续变化；固定 SHA 链接用于复核本次源码观察。

### Silo

- [S1] [Silo 仓库 README（固定源码）](https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/README.md)。项目定位、组件与发行入口。
- [S2] [Silo Manifesto](https://silo.pgsty.com/about/manifesto/)。独立维护、兼容性和维护承诺的公开说明。
- [S3] [服务器兼容性审计](https://silo.pgsty.com/compatibility/server/) · [迁移说明](https://silo.pgsty.com/compatibility/migration/)。保留的契约、行为变化与迁移边界；网页内容按核查日理解。
- [S4] [Rebrand guard](https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/buildscripts/rebrand-guard/main.go)。将允许改名与必须保留的标识规则变为代码检查。
- [S5] [升级与回退测试脚本](https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/buildscripts/minio-upgrade.sh)。固定旧/新版本组合与特定测试数据，不代表任意部署都能无损回退。
- [S6] [发布提交检查脚本](https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/buildscripts/check-release-commit.sh)。核对指定提交与必要检查结果。
- [S7] [2026-11-12 发行](https://github.com/pgsty/silo/releases/tag/RELEASE.2026-11-12T00-00-00Z)。实际产物与发行说明。
- [S8] [发布工作流](https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/.github/workflows/release.yml) · [发行测试](https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/.github/workflows/test-release.yml) · [发行定稿](https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/.github/workflows/finalize-release.yml)。应区分工作流定义、实际运行记录与产物状态。
- [S9] [安全维护政策](https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/SECURITY.md) · [漏洞报告规范](https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/VULNERABILITY_REPORT.md)。支持范围与影响判断。
- [S10] [官方安全账本](https://silo.pgsty.com/about/security-advisories/)。修复、影响边界及无需新增补丁的判断记录。
- [S11] [Go CI 工作流](https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/.github/workflows/go.yml)。实际 runner、检查和交叉编译定义。
- [S12] [维护与协作规范](https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/AGENTS.md) · [组件版本矩阵](https://silo.pgsty.com/compatibility/versions/)。组件边界和依赖复用政策。
- [S13] [RAGFlow 采用 Silo 的固定部署配置](https://github.com/infiniflow/ragflow/blob/7d171d2cf3d26264c3bbbdc46122ba45676c90c9/docker/docker-compose-base.yml)。证明该配置采用，不代表所有用户的实际部署。
- [S14] [BuildKit S3 集成测试切换提交](https://github.com/moby/buildkit/commit/4509d3ac465a62e27de90d4239e34b966c3e3de1)。证明集成测试采用，不代表整个产品的生产存储迁移。

### ASP.NET Boilerplate 与参考 fork

- [A1] [ASP.NET Boilerplate 仓库](https://github.com/aspnetboilerplate/aspnetboilerplate) · [MIT 许可证](https://github.com/aspnetboilerplate/aspnetboilerplate/blob/dev/LICENSE)。本文针对经典 ASP.NET Boilerplate，不是 `abpframework/abp`。
- [A2] [yopichy 核心项目文件](https://github.com/yopichy/aspnetboilerplate/blob/0e5b06ce33471403da0804d6a948b5794ee31739/src/Abp/Abp.csproj) · [打包脚本](https://github.com/yopichy/aspnetboilerplate/blob/0e5b06ce33471403da0804d6a948b5794ee31739/nupkg/pack.ps1)。独立包身份与既有程序集名称分离的实际例子。
- [A3] [上游 v10.5.1](https://github.com/aspnetboilerplate/aspnetboilerplate/releases/tag/v10.5.1)。核查基线和包含的修复。
- [A4] [上游 PR #7219](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7219)。嵌套 compiled query 过滤状态修复。
- [A5] [yopichy .NET 10 迁移提交](https://github.com/yopichy/aspnetboilerplate/commit/a5d37de73ff91b40ccaa86db4a2737d60dba2dcf) · [v10.5.3 发行说明](https://github.com/yopichy/aspnetboilerplate/releases/tag/v10.5.3)。迁移工作与维护者报告的验证范围。

[S1]: https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/README.md
[S2]: https://silo.pgsty.com/about/manifesto/
[S3]: https://silo.pgsty.com/compatibility/server/
[S4]: https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/buildscripts/rebrand-guard/main.go
[S5]: https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/buildscripts/minio-upgrade.sh
[S6]: https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/buildscripts/check-release-commit.sh
[S7]: https://github.com/pgsty/silo/releases/tag/RELEASE.2026-11-12T00-00-00Z
[S8]: https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/.github/workflows/release.yml
[S9]: https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/SECURITY.md
[S10]: https://silo.pgsty.com/about/security-advisories/
[S11]: https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/.github/workflows/go.yml
[S12]: https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/AGENTS.md
[S13]: https://github.com/infiniflow/ragflow/blob/7d171d2cf3d26264c3bbbdc46122ba45676c90c9/docker/docker-compose-base.yml
[S14]: https://github.com/moby/buildkit/commit/4509d3ac465a62e27de90d4239e34b966c3e3de1
[A1]: https://github.com/aspnetboilerplate/aspnetboilerplate
[A2]: https://github.com/yopichy/aspnetboilerplate/blob/0e5b06ce33471403da0804d6a948b5794ee31739/src/Abp/Abp.csproj
[A3]: https://github.com/aspnetboilerplate/aspnetboilerplate/releases/tag/v10.5.1
[A4]: https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7219
[A5]: https://github.com/yopichy/aspnetboilerplate/commit/a5d37de73ff91b40ccaa86db4a2737d60dba2dcf
