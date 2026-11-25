# R3 首包设计

## Context

以[提案](proposal.md)所选的原版 Web.Host 为对照。规划阶段做了静态源码核对和 R2 原始证据回读，R3 模板的实际还原和构建留待实施取证。

| 对象 | 提交 | 树 | 用途 |
| --- | --- | --- | --- |
| 规划主仓 `main` | `105b1263160d049c97a975ee088b79982f1c547d` | `eae117e6926381b1558d6d25e113869e11804968` | 固定下列子仓输入 |
| 模板 `module-zero-core-template` | `2e9536872673a7ff1986a19e798c51684d16afe5` | `b6a9e7386e3073e820eed83fe418d6c6096468bc` | 原版 Web.Host 构建输入 |
| 框架 `aspnetboilerplate` | `457be917b46c4fb6237831baac5abb848ffe1c4b` | `fb0abb6be5cb69b0e5ff395f4b010cf28511f9c8` | 维护线项目图，与 R2 实包候选树相同 |

模板源登记为 `dusdong/module-zero-core-template`，兼容参考来自 `aspnetboilerplate/module-zero-core-template`。框架源登记为 `dusdong/aspnetboilerplate`。R2 的归档、候选包与报告原件继续按当时的来源证明识别。本轮读到五份 `.nupkg` 的摘要均吻合登记值，包内两个目标的 DLL 路径和 nuspec 的四条内部依赖边与记录一致。R2 的 SQLite 事务和 HTTP 读回证据适用于原独立最小后端。[子模块登记](../../../../.gitmodules) · [R2 实物及运行证据](../../../../docs/maintenance/r2-core-package-consumption.md) · [R2 归档](../2026-11-25-validate-r2-core-package-consumption/)

## Goals / Non-Goals

建立可保存、可重跑的原版 Host 构建对照，把模板还原图与维护框架项目图对应到可补齐的包。保留依赖证据的边界，使后续可以比较同入口、同目标、同 Provider 的候选构建。[规范增量](specs/template-host-baseline/spec.md)

本包落点在主仓，构建输入是固定模板源码。后续包使用本包产出的基线判断迁移差异、运行范围和回退条件。

## Decisions

### 固定 Angular 配套 Web.Host 的模板项目图

入口是 `aspnet-core/src/AbpCompanyName.AbpProjectName.Web.Host/AbpCompanyName.AbpProjectName.Web.Host.csproj`。下表使用相同命名前缀后的简写，覆盖入口可达的五个 `net9.0` 项目及五条项目引用。

| 模板项目 | 直接项目引用 | ABP 原包直接声明，均为 `10.2.0` | 相关第三方声明 |
| --- | --- | --- | --- |
| Web.Host | Web.Core | `Abp.Castle.Log4Net` | EF Core Design `9.0.5`，私有 |
| Web.Core | Application、EntityFrameworkCore | `Abp.AspNetCore`、`Abp.ZeroCore`、`Abp.AspNetCore.SignalR` | JWT Bearer `9.0.5`、Swashbuckle `8.1.2` |
| Application | Core | — | — |
| EntityFrameworkCore | Core | — | EF Core SQL Server、Tools、Design 均为 `9.0.5`，Tools 与 Design 为私有 |
| Core | — | `Abp.AutoMapper`、`Abp.ZeroCore.EntityFrameworkCore` | Castle Windsor MS DI `4.1.0` |

`Startup` 注册 WebHost 模块，导航至 Web.Core 模块，并配置 Log4Net 与 SignalR 端点。模板 `AbpProjectNameDbContextConfigurer` 的两个重载都使用 `UseSqlServer`，EF 模块初始化时按标志执行种子流程。包含 SQL Server Provider 的实际构建是本轮的对照，数据库连接、种子、迁移、启动和登录留到实际运行阶段。按单个入口构建可减少 MVC、Migrator、测试项目和 Angular 前端引入的其他输入。[模板源码目录](../../../../module-zero-core-template/aspnet-core/src/) · [R0 全模板声明盘点](../../../../docs/maintenance/release-baseline.json)

### 对照维护框架项目图与实包

框架源码以模板六个直接包 ID 对应的 `src/<原 ID>/<原 ID>.csproj` 为根，递归跟随 `ProjectReference` 得到下列十一节点。映射暂以源码普通项目身份和 R2 已实际产出的包为准。六个待补项目的原 `PackageId` 与 `AssemblyName` 均为表中原 ID，根命名空间为 `Abp`。R2 五项目的根命名空间沿用各自登记值。候选只改 NuGet `PackageId`，后续逐包验真实编译和依赖组。

| 框架原 ID | 直接内部项目引用 | 当前源码目标 | 维护版包 |
| --- | --- | --- | --- |
| `Abp` | — | `net9.0;net10.0` | R2 `Du.Abp` |
| `Abp.Web.Common` | `Abp` | `net9.0;net10.0` | R2 `Du.Abp.Web.Common` |
| `Abp.AspNetCore` | `Abp.Web.Common` | `net9.0;net10.0` | R2 `Du.Abp.AspNetCore` |
| `Abp.EntityFramework.Common` | `Abp` | `net9.0;net10.0` | R2 `Du.Abp.EntityFramework.Common` |
| `Abp.EntityFrameworkCore` | `Abp.EntityFramework.Common` | `net9.0;net10.0` | R2 `Du.Abp.EntityFrameworkCore` |
| `Abp.AspNetCore.SignalR` | `Abp` | `net9.0` | 待补 `Du.Abp.AspNetCore.SignalR` |
| `Abp.Castle.Log4Net` | `Abp` | `net9.0` | 待补 `Du.Abp.Castle.Log4Net` |
| `Abp.Zero.Common` | `Abp` | `net9.0` | 待补 `Du.Abp.Zero.Common` |
| `Abp.ZeroCore` | `Abp.Zero.Common` | `net9.0` | 待补 `Du.Abp.ZeroCore` |
| `Abp.ZeroCore.EntityFrameworkCore` | `Abp.ZeroCore`、`Abp.EntityFrameworkCore` | `net9.0` | 待补 `Du.Abp.ZeroCore.EntityFrameworkCore` |
| `Abp.AutoMapper` | `Abp` | `net9.0` | 待补 `Du.Abp.AutoMapper` |

十一节点是维护源码的静态预期。原版模板包版本、传递边和框架程序集所有者需要从本轮实际还原读出。R2 候选包的 EF Core/MVC `net9.0` 依赖线在验收记录中为 `9.0.18`，模板的 SQL Server/Design 等声明为 `9.0.5`。后续需对照真实解析的 EF Core、Relational、SQL Server、SqlClient 和私有工具版本，判断目标候选所需的依赖调整。维护端 `Abp.AutoMapper` 当前声明 Mapper `14.0.0` 与 Collection `11.0.0`，原版模板的实际映射依赖同样从包图读取。R2 的目标、包身份和四条内部边直接引用已验记录，基线复跑仅还原原 ID。这样在普通工作站取得固定模板提交和公开包即可复跑，历史 R2 私有工件继续用于单独审计与以后候选取证。[框架源码](../../../../aspnetboilerplate/src/) · [R2 五包身份与依赖](../../../../docs/maintenance/r2-core-package-consumption.md#源码与产物) · [AutoMapper 兼容边界](../../../../docs/compatibility/automapper.md)

### 主仓复用验证入口并隔离固定输入

扩展 `eng/verify.py` 增加 `python3 eng/verify.py --profile r3-web-host --evidence-root <证据父目录>`，R3 流程和资产核对实现位于 `eng/r3_web_host.py`。复用现有运行目录、命令日志、摘要及阶段报告惯例，并沿用 R1 与 R2 已验证的资产字段和哈希含义。R0、R2 的 profile 契约及冻结输入继续使用原入口。该入口覆盖一个固定组合，模板入口或基线改变需明确更新输入登记。[验证入口](../../../../eng/verify.py) · [R1 资产读取](../../../../eng/r1_restore_inventory.py) · [R2 资产核对](../../../../eng/r2_assets.py)

1. 检查主仓、模板与框架的固定对象和对应树、基线主仓中登记的 gitlink 和子模块来源，记录实际执行的主仓提交及其 gitlink。用 `git archive` 从固定模板提交导出 `aspnet-core/` 到新目录，确认入口及五个项目相对路径；从固定框架提交读取项目声明用于闭包比对。保留本次命令、源码输入清单和摘要。当前子仓检出只用于访问 Git 对象。
2. 在源码副本父层设置使用 `10.0.404`、`rollForward=disable` 的 `global.json`，以执行目录的 `dotnet --version` 实证 SDK，核对 macOS ARM64 与所用 dotnet 架构，登记系统构建号、SDK 路径与工具版本。SDK 沿用已验 R2 工具版本，项目的目标仍为 `net9.0`，本次构建无需启动 .NET 9 Host。
3. 每轮创建专属 NuGet 全局包目录与独立 HTTP 缓存，校验还原资产里只出现指定包目录及公开源。有效 `NuGet.Config` 在证据目录生成并通过 `--configfile` 显式使用，`<clear />` 后唯一包源为 `https://api.nuget.org/v3/index.json`。保存有效配置和摘要，并登记原配置包含同一公开源及旧的 `ABP Nightly Source`（MyGet）。模板的稳定包对照限定到 nuget.org。若该源不可取得必需输入，报告实际失败。
4. 在隔离的 `aspnet-core` 下对固定 Host 执行 `dotnet restore <Host.csproj> --configfile <有效配置> --no-http-cache -p:Configuration=Release`，核对真实资产后使用相同的工作目录、SDK、包目录、项目及 Release 配置运行 `dotnet build <Host.csproj> --configuration Release --no-restore`。保留每步退出码、日志和警告。使用同一副本实际生成的 Host DLL、`.deps.json` 和目标输出定位证据。

### 逐项目核对实际解析和最终输出

- 保存五份原始 `project.assets.json`，以实际项目路径、项目引用和 `net9.0` 目标定位并核对闭包。记录六个直接 ABP 声明所在项目和声明版本，读出每项目每目标的直接与传递 ID、解析版本及依赖边。对包读取实际缓存元数据，核对来源与 NuGet 内容 SHA-512，另保存归档和诊断所需文件的 SHA-256。NuGet 内容标识和归档字节摘要分别登记。
- 在应用包图之外，按项目和目标读取 `project.frameworks.<TFM>.downloadDependencies`。从本轮专用缓存核对实际下载的 SDK 构建包，记录 ID、版本、来源及可验证的哈希。对使用 SDK 安装目录中现成 targeting pack 或 apphost pack 的情况，按实际选用的本机 pack 记录身份、版本和可得证据；取不到的下载来源或包哈希注明原因。下载清单允许为空，按用途分别统计，避免将工具链输入计入应用闭包或候选缺口。
- 读取选中的 `compile`、`runtime`、`runtimeTargets`、`native`、构建及分析器等资产，记录项目声明中的私有、包含和排除规则。模板 Host 启用 `PreserveCompilationContext`，应区分运行输出、引用程序集、编译专用项、共享框架、工具和私有资产，并按实际目标判断 RID 资产的用途。
- 比较 Host 还原图的入口及各项目、包节点与 `.deps.json` 的依赖边。资产依赖范围指向选中的库，`.deps.json` 边须对应这些库的解析版本。按同轮 SDK 冲突处理后的复制列表核对 NuGet 运行资产、RID 与资源路径，并保留 SDK 编译专用引用。框架和 SQL Server Provider 运行 DLL 校验实际输出及包资产的 SHA-256。定向负例覆盖缺少框架依赖边、保留 DLL 时缺少 SQL Server Provider 声明、以及保留 `.deps.json` 时只移走 `Abp.Castle.Log4Net.dll`。进程加载验证留待运行阶段。
- 缺失或错误的固定输入、六个直接 ABP 声明无法在相应项目解析、五项目的目标证据不齐、Host 的必要产物缺失或零匹配、维护版 ABP 混入、框架资产无法归属或存在多个所有者时，返回非零。框架源码预期图和原版实测图的包边、版本及归属差异须逐项归因后才能接受。对第三方保留版本、边和用途的实际差异，无固定总量断言。警告或诊断登记原文和影响，涉及证据不完整或构建失败时按对应阶段报告。
- 每轮留存机器可读 `report.json`、逐项目的 `assets-inventory.json`、`host-output.json`、`package-gaps.json` 以及引用的有效源配置、原始资产、构建输出、命令日志和摘要。阶段包括预检/物化、还原、资产、构建、产物/缺口核对，记录实际状态及后续未执行原因。运行证据留在独立目录，主仓新增 `docs/maintenance/r3-web-host-baseline.md`，登记可复跑命令、执行身份、摘要、证据路径、已执行与未执行范围及补包准入，并由 `docs/README.md` 索引。
- 从首次通过验收的 `assets-inventory.json` 与 `host-output.json` 提取精简 JSON，随验收文档保存为 `docs/maintenance/r3-web-host-baseline.json`。按项目和目标保存相对项目引用、直接包声明与解析结果、应用包 ID、版本及包间依赖边。SDK 构建输入单列。每个框架运行 DLL 保存输出相对路径、所属包、包内资产路径及 SHA-256。验收时逐项回读核对。清单使用稳定顺序及相对标识，在另一工作站可直接与新结果比较。日常复跑将新清单写入当轮证据目录，保留首次验收的对照。

### 按闭包次序推进后续补包和迁移

| 后续分组 | 依赖与准入条件 |
| --- | --- |
| 独立组件 | SignalR 与 Log4Net 均只引用核心 `Abp`，可独立推进。核对各自 `net9.0` nuspec、框架/第三方依赖、程序集和定向消费。 |
| Module Zero | 按 `Abp.Zero.Common → Abp.ZeroCore → Abp.ZeroCore.EntityFrameworkCore` 顺序补齐，最后一个还需 `Abp.EntityFrameworkCore`。保留已验核心行为，并在该组验收核对原 `net9.0` Module Zero 调用与 SQLite 回归覆盖。 |
| 映射 | `Abp.AutoMapper` 仅依赖核心项目，但其候选有独立兼容前提。以 MIT AutoMapper v14 `bf76a5819e1bad7af7db5382bf0f3a0178048a15` 和 Collection v11 `eafbf005becf73f989e1b1c0d52e8699439f837c` 为维护参考，回读实际来源和许可证，核对引擎唯一性及依赖范围，完成已识别安全修复与配置、对象更新、集合映射、`ProjectTo` 对照。目前两组件 gitlink 分别是不同维护线。 |
| 同批候选 | 用已归因的原版基线和上述通过的组件输入产出所需核心与新增包的同批候选，清点实际包、目标、依赖边、程序集身份及来源。在独立源和空缓存验证闭包无原版 ABP 混入及重复程序集。 |
| 迁移与运行 | 先验证同一 Host 的候选还原与 Release 构建并对照原版差异，再使用隔离 SQL Server 进行启动、登录、租户和授权等关键路径验证。若涉及 schema 或数据变换，先核对旧版本回退所需的备份、恢复或逆向迁移条件。Angular 组合和多平台实跑按各自范围补证。 |

[维护计划](../../../../docs/maintenance/du-abp-maintenance-plan.md#73-r3-先选择模板-webhost-入口) · [兼容维护指南](../../../../docs/compatibility/automapper.md) · [R3 迁移及回退路线](../../../../docs/maintenance/fork-roadmap.md#r3验证升级路径和实际消费者)

## Risks / Trade-offs

- 固定源码与 SDK 能约束输入，公网包源和依赖范围仍可能发生可观察差异。记录精确版本、有效源、包哈希和警告，失败时保留日志并在新目录复验。对不同运行按资产逐项比较，Release 文件的哈希用于标识所测产物。
- SQL Server Provider 的还原和编译证据覆盖选中资产，实际服务兼容性由后续运行验证。模板 Host 的初始化包含种子流程，当前命令止于构建与证据核对。
- 框架静态引用图和原版实际包图可能有版本与传播差异。将框架包未知项和关键依赖差异逐项归因后，再以确认的闭包组织下一包。
