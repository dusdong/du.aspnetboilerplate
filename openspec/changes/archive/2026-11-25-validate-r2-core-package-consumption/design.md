# R2 首批核心候选包设计

## Context

[提案](proposal.md)以主仓 `0780c8c55a964b2c561b1126f2a2f98048b1c100` 固定的框架 `d497cba3d3feec093168697e81adb64ea5544087` 为起点。其树 `097820f84c1c20d09e5158c4a2723ed530098266` 与 R1 已验候选 `7a47504c17b32f0111473c97dd2f8377fe06171b` 相同。五个项目均已双目标化。R1 记录了十份 DLL 的身份和 API 对照，现有版本为 `10.5.1`，程序集版本为 `10.5.1.0`。[R1 运行时迁移验收](../../../../docs/maintenance/r1-dotnet10-runtime-migration.md) · [R1 归档](../2026-11-25-migrate-r1-core-to-dotnet10/)

框架 `common.props` 提供原版仓库 URL、包版本、许可证及图标，Release 默认启用自动打包，五个项目单独将 `GeneratePackageOnBuild` 设为 `False`。现有 `nupkg/pack.ps1` 遍历较广项目集并按原包名收集包。主仓的 R0 复验和 R1 还原清单以源码为输入，现有证据入口见[维护基线](../../../specs/maintenance-baseline/spec.md)与[运行时迁移规范](../../../specs/runtime-migration/spec.md)。

## Goals / Non-Goals

每批候选在一个本地源中形成可检查的双目标依赖闭包。主仓用同一批包独立执行两个目标的编译和运行验证，建立源码、包、还原图、DLL 与业务结果之间的对应关系。验收范围为本机 macOS ARM64、ASP.NET Core 和 SQLite 的两种目标组合。完整范围见[提案](proposal.md)与[规范增量](specs/core-package-consumption/spec.md)。

## Decisions

### 框架子仓使用显式候选打包入口

在框架 `nupkg/` 增加独立于现有脚本的 macOS 可调用入口，计划为 `bash nupkg/pack-r2-candidates.sh --version <版本> --output <空目录>`。实现只遍历下表五个项目，并在这五个项目的原有声明之后导入同一候选属性文件。用显式 `DuCoreCandidatePack=true` 和独立输入 `DuCoreCandidatePackageVersion` 触发，确保项目引用图上的 MSBuild 求值，包括 NuGet 读取的包身份，使用同一组候选属性。改造整个上游打包入口会把其他组件的发行行为纳入本轮。保持普通模式的求值和构建行为，可用显式开关关闭候选模式。

| 框架源码项目 | 原 PackageId 与 AssemblyName | 候选 PackageId | RootNamespace | 内部依赖 |
| --- | --- | --- | --- | --- |
| `src/Abp/Abp.csproj` | `Abp` | `Du.Abp` | `Abp` | 无 |
| `src/Abp.Web.Common/Abp.Web.Common.csproj` | `Abp.Web.Common` | `Du.Abp.Web.Common` | `Abp` | `Du.Abp` |
| `src/Abp.AspNetCore/Abp.AspNetCore.csproj` | `Abp.AspNetCore` | `Du.Abp.AspNetCore` | `Abp` | `Du.Abp.Web.Common` |
| `src/Abp.EntityFramework.Common/Abp.EntityFramework.Common.csproj` | `Abp.EntityFramework.Common` | `Du.Abp.EntityFramework.Common` | `Abp.EntityFramework` | `Du.Abp` |
| `src/Abp.EntityFrameworkCore/Abp.EntityFrameworkCore.csproj` | `Abp.EntityFrameworkCore` | `Du.Abp.EntityFrameworkCore` | `Abp` | `Du.Abp.EntityFramework.Common` |

映射以冻结的 R0 `release-baseline.json` 为准，当前两个目标和项目求值以 R1 为准。从隔离源码和空 NuGet 包目录还原，框架还原只启用 nuget.org。按依赖顺序用 SDK 生成 Release 包，保留普通项目引用，使用同一组输入还原与执行 `dotnet pack --no-restore -c Release`。每次 pack 保留两个目标，统一使用候选 `PackageVersion`，统一关闭自动打包并输出 `.nupkg` 与 `.snupkg` 到当轮目录。入口捕获项目、目标、命令、日志和退出码。目录内仅五个 `.nupkg` 作为消费者源，符号包独立留存并核对两目标 PDB 与 DLL 对应关系。[R0 包映射](../../../../docs/maintenance/release-baseline.json)

首个拟定版本为 `10.5.1-r2.1`。每次正式生成下一批候选将十进制序号递增，五包同步，内容变化的候选使用新版本与新目录。每轮记录精确版本和输出摘要，避免旧缓存或同版本不同文件混淆。打包只设 `PackageVersion`，保留 R1 的 `Version`、原程序集名、程序集版本 `10.5.1.0`、公共密钥标识和程序集元数据的既有兼容语义。

候选 `.nuspec` 的仓库 URL 指向 `.gitmodules` 登记的 `https://github.com/dusdong/aspnetboilerplate.git`。包内的 `LICENSE.md` 和 `abp_nupkg.png` 对应源码原件。若有精确源码提交，在仓库元数据登记该提交并核对其树。若实施时以未提交候选取证，从独立物化的确切源码打包，记录已提交基线、完整候选树与可重建补丁摘要，在包中附可和外部清单逐项比对的最小来源记录，仓库元数据的 commit 字段不可误填基线为实际候选。外部清单关联主仓输入、框架 gitlink、实际打包源码、SDK、版本、五包和符号包的 SHA-256、各目标 DLL 摘要及还原入口，区分已验 R1 和本轮 R2。候选覆盖只作用于显式模式。[子模块登记](../../../../.gitmodules)

### 主仓从候选实物核对身份、依赖与资产

计划扩展现有入口为 `python3 eng/verify.py --profile r2 --candidate-feed <本地包目录> --candidate-manifest <候选清单> --r1-evidence <同目标对照目录> --evidence-root <证据父目录>`。R2 独立读入包并生成自己的报告，复用已有摘要、证据目录、还原资产和 API 提取能力。R0 profile、固定输入、历史证据和 R1 已验记录保持原状。R1 的资产提取规则可以借用，独立消费者另有双包源和零项目引用约束。仅检查源码项目引用不能发现打包依赖组或资产路径的偏差。[统一验证入口](../../../../eng/verify.py) · [R1 还原清单入口](../../../../eng/r1_restore_inventory.py)

- 检查实际 ZIP 和 nuspec，核对 ID、版本、仓库和源码证明、许可和图标。每包须有各目标的依赖组与该包自己的 `lib/<TFM>/<AssemblyName>.dll`。从包内十份 DLL 的程序集元数据读取 `TargetFrameworkAttribute`，`lib/net9.0` 应为 `.NETCoreApp,Version=v9.0`，`lib/net10.0` 应为 `.NETCoreApp,Version=v10.0`。属性缺失或值不符时，报告包内路径、预期值和实读结果。检查文件内容能定位到候选包及同批构建 DLL，避免将引用项目的 DLL 一并打入包。
- 每个目标以四条内部边核对两个三级链。`Du.Abp.AspNetCore → Du.Abp.Web.Common → Du.Abp` 及 `Du.Abp.EntityFrameworkCore → Du.Abp.EntityFramework.Common → Du.Abp`。nuspec 的内部范围须以本批预发布版本为约束下界且允许该版本，可使用该版本的精确范围，实际还原必须五包均精确命中该版本。检查第三方 nuspec 声明与 R1 同目标可传播的项目依赖一致，`net9.0` 的公开 EF Core、Relational、ASP.NET Core MVC JSON 和 Razor 依赖沿用 `9.0.18`，`net10.0` 沿用 `10.0.15`。按实际求值比较其余声明、框架引用和私有依赖可见性。源码用 SourceLink、Fody 和私有代码生成依赖各有原有资产规则，消费闭包按实际传播规则核对。
- 用 MSBuild 分别求值两目标的 `PackageId,PackageVersion,AssemblyName,RootNamespace,TargetFramework,TargetPath`，在 R1 树核对普通模式的对照值，在候选树核对普通及显式两种模式。保留一次代表性同仓 `net9.0` 源码调用方的 Release 构建证据。用已有 `ApiInventory` 提取包内共十份 DLL 的身份、公共及受保护 API 和资源，与 R1 `core/api-a`（`net10.0`）及 `compat/api-a`（`net9.0`）对应清单逐项比较，并以 `release-outputs.json` 关联来源。证据缺失时从精确 R1 树在隔离目录按照历史入口重建所需目标，记录输入和结果。独立构建的哈希用于标识各自产物，结构比较采用 API 清单。[API 提取及比较工具](../../../../docs/maintenance/baseline-tools/) · [R1 复现命令与证据](../../../../docs/maintenance/r1-dotnet10-runtime-migration.md#复验与原始证据)

### 两个目标分别还原与运行独立消费者

主仓 `validation/minimal-backend/` 使用 `Microsoft.NET.Sdk.Web`，声明两目标，以精确范围 `[<候选版本>]` 直接引用两个入口包。只额外显式引用对应目标的 `Microsoft.EntityFrameworkCore.Sqlite`，版本分别为 `9.0.18` 和 `10.0.15`。项目引用、框架 DLL 文件引用和依赖源码均不进入消费者，使通过结果能够归因于候选包。

消费者副本携带 `global.json`，固定 SDK `10.0.404` 并设置 `rollForward` 为 `disable`。在隔离框架源码目录和各消费者副本的根目录分别执行 `dotnet --version`，核对后再还原。启动前用将要运行消费者的 ARM64 `dotnet` 核对 `Microsoft.NETCore.App` 和 `Microsoft.AspNetCore.App`。本轮沿用 R1 的运行时组合，`net9.0` 存量兼容验证使用 `9.0.23`，`net10.0` 使用 `10.0.15`。报告记录 SDK、宿主路径及进程实际加载的两项共享运行时版本，预检失败时记录原因并将对应后续阶段标为未执行。

- 对每个目标另建消费者副本、证据、工件和空 `NUGET_PACKAGES` 目录，各用独立 HTTP 缓存并执行 `dotnet restore --configfile <配置> --no-http-cache -p:TargetFrameworks=<目标>`。同一轮将候选版本属性、Release 配置和目标传给 restore 与 build，使用 `dotnet build --no-restore -c Release -f <目标> -p:TargetFrameworks=<目标>`，再直接运行对应输出 DLL。用绝对候选源路径与 NuGet `packageSourceMapping` 将 `Du.Abp` 和 `Du.Abp.*` 限于候选源，将其余包交给唯一登记第三方源 `https://api.nuget.org/v3/index.json`。配置清除继承的源与回退目录。核对资产中的实际源及包目录与当轮配置一致。
- 如需保留同批候选的还原锁文件，首次还原加 `--use-lock-file`，将通过验收的 `packages.lock.json` 按目标保存。复跑时把对应锁文件放入新的消费者副本，使用相同候选版本、目标、源配置和空缓存，以 `--locked-mode` 还原。
- 按 `project.assets.json` 核对两个直接入口及 SQLite 声明、四条边、五个包的选中版本，以及各包编译和运行资产。用提取目录的 `.nupkg.metadata` 与资产的内容哈希核对每个包的实际来源和内容，再对缓存中的五个 `.nupkg` 复算 SHA-256，与指定本地源和清单比对。核对完整包图与运行输出，发现原版或其他框架发行线包、隐藏的项目或文件引用、同名框架程序集多源、错目标 DLL、版本降级或缺件即失败。
- 用候选的 ABP ASP.NET Core 与 EF Core 模块初始化宿主，沿用 `AddAbp` / `UseAbp` 入口，通过模块注册最小 `AbpDbContext` 和可由 DI 解析的业务服务。应用用每轮独立的 SQLite 文件初始化表，监听回环动态端口。验证器发起两个真实 HTTP 请求。写入请求通过 ABP 仓储写入固定标识和值。写入期间从该仓储实际使用的 `DbContext` 的 `Database.CurrentTransaction` 取得并记录事务标识。记录负责该事务的 ABP 工作单元成功完成提交的事件（例如 `Completed`），用同一写入请求标识关联两项证据，提交成功后才返回预期状态码和记录标识。读请求在另一 DI 作用域和工作单元中通过 ABP 仓储从 SQLite 读取，断言 HTTP 成功、标识和值及行数为一。记录模块初始化状态、业务服务解析、EF Provider 名称和 SQLite 版本。取证完成后正常关闭宿主，用临时数据库避免累积数据干扰复跑。
- 在运行进程中记录五个已加载框架程序集的完整身份、位置及 SHA-256，以 `.deps.json`、`.runtimeconfig.json`、实际进程架构及共享运行时、资产选中路径和包内 DLL 建立对应。记录 SQLite 实际解析的原生依赖及相应平台资产。每个目标均需有真实 HTTP 和数据库结果及五份 DLL 证据，运行退出码仅作为其中一项判据。

### 本地验收证据

按上述环境预检结果核对每个宿主的实际架构及共享运行时版本。报告输出 JSON、原始日志、具体命令及退出码、资产和 API 对照、宿主和响应记录、两个目标的通过或失败状态与未执行原因。负例在各自临时目录执行。保留原清单验证同版本包替换被摘要门禁拦截。以单独的隔离还原复用正式配置，验证从专用源移走一个传递包后无法取得该包，以便即使入口在还原前有缺包预检也能覆盖包源约束。依赖 ID 变异和错目标 DLL 各用单独的候选副本与重算的摘要输入。错目标用例保留 `lib/net10.0/Abp.Web.Common.dll` 路径，将内容替换成同包的 `net9.0` DLL。要求诊断指明该路径及元数据中的 `v9.0` 与预期 `v10.0`，确认失败来自目标框架检查。保留各负例的实际非零结果和失败阶段。

完成实施验收后把简要结论、复跑命令、原始证据定位与摘要记入计划新增的 `docs/maintenance/r2-core-package-consumption.md`，由 `docs/README.md` 和路线文档指向该记录。包、缓存、临时项目与日志留在显式指定的本机工件目录，记录可取得的证据路径。实施后的 R2 本地结论限于 macOS ARM64 下的两种实测组合，Windows、Linux、其他 Provider、R3 完整模板和公开包源均待各自验证。

## Risks / Trade-offs

- MSBuild 属性求值或 SDK 对项目引用版本的传播可能生成原版依赖，或者仅打包其中一个目标。按真实 nuspec、消费者资产和加载的 DLL 三处核对。
- 版本相同的旧包可被暖缓存隐藏，或者第三方传递包引入冲突 DLL。每目标使用独立空缓存，检查包来源、五包原始摘要以及程序集归属。
- R1 源码依赖图包含私有工具链与 SDK 裁剪记录。消费图会因场景和目标有所差异，比较依据是同目标可传播声明和实际资产，对新增、缺失或解析版本差异逐项记录原因。
- 私有候选源码仍在迭代时，包字节和 Git 最终提交可能分离。用来源清单固定已验树与补丁。若确认的交付树有变化，重新生成下一批并复验。若原包元数据或签入后的重新打包改变了字节，也按新候选复验。

## Migration Plan

本轮候选仅安装在独立验证工程，回退时切回先前已验证的候选版本及对应源并在新缓存复验，或停止使用显式打包入口。若取得 Git 交付授权，先验框架改动及候选树，交付框架子仓并从 `.gitmodules` 指定的仓库验证提交可取得。随后交付主仓 gitlink、消费者、验证入口及证据记录，用 `git ls-tree <主仓提交> aspnetboilerplate` 回读指向的提交。候选验收与 Git 交付各自记录。
