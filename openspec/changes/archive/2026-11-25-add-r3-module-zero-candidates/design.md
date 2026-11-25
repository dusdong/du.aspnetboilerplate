# R3 Module Zero 候选设计

## Context

| 输入 | 实施起点与验收用途 |
| --- | --- |
| 主仓交付基线 | `main` 提交 `4b00d40d3b5023a9c1bd32a75400b6b97979f0a7` 已交付上一批，记录下行框架 gitlink |
| 本轮框架实施起点 | 主仓 gitlink 指向已推送的框架 `dev` 提交 `b329282a6ab4429b0cc724a2649e7a446e2c1a6a`，树 `6920f9d927c6a4a787d93d6e1052368a9a5e50d4` |
| 固定普通 Release 对照 | 框架提交 `457be917b46c4fb6237831baac5abb848ffe1c4b`，树 `fb0abb6be5cb69b0e5ff395f4b010cf28511f9c8`。从此提交构建三个项目的历史 `net9.0` 对照 |
| 上一批 SignalR 与 Log4Net | `10.5.1-r3.1` 的已验源码树与 `b329282` 的树相同。实测覆盖五个框架 DLL 和第三方 `log4net.dll`，证据用于核对模板剩余缺口 |
| 固定模板 | `2e9536872673a7ff1986a19e798c51684d16afe5`。原版 Web.Host 还原实测三个 Module Zero 包均为 `10.2.0`。Web.Core 直接声明 `Abp.ZeroCore`，Core 直接声明 `Abp.ZeroCore.EntityFrameworkCore` |
| R2 原包 | `10.5.1-r2.1`，只取已登记的 `Du.Abp`、`Du.Abp.EntityFramework.Common`、`Du.Abp.EntityFrameworkCore`。这三份原归档及 `net9.0` DLL 摘要已按登记进行只读核对 |

三个项目的普通目标均为 `net9.0`，根命名空间均为 `Abp`，程序集名与原包 ID 同名。仅 `Abp.ZeroCore` 使用 Web SDK 提供的 `Microsoft.AspNetCore.App` 框架引用。三者导入的 `common.props` 在 Release 设置 `GeneratePackageOnBuild=True`。模板定义了真实 `Tenant`、`Role`、`User` 和 `AbpZeroDbContext` 派生类，EF 模块通过 `Configuration.Modules.AbpEfCore().AddDbContext` 负责注册。 [Zero.Common 项目](../../../../aspnetboilerplate/src/Abp.Zero.Common/Abp.Zero.Common.csproj) · [ZeroCore 项目](../../../../aspnetboilerplate/src/Abp.ZeroCore/Abp.ZeroCore.csproj) · [ZeroCore EF 项目](../../../../aspnetboilerplate/src/Abp.ZeroCore.EntityFrameworkCore/Abp.ZeroCore.EntityFrameworkCore.csproj) · [普通打包属性](../../../../aspnetboilerplate/common.props) · [模板 EF 模块](../../../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.EntityFrameworkCore/EntityFrameworkCore/AbpProjectNameEntityFrameworkModule.cs) · [模板实际图](../../../../docs/maintenance/r3-web-host-baseline.json)

## Goals / Non-Goals

三包生产与消费共用一份冻结实物登记。普通源码兼容以对应目标的产物及既有 SQLite 测试为对照，独立消费者负责验证实际包图、程序集加载和关系数据库行为。模板仅提供引用与接入对照，剩余范围见[提案](proposal.md)与[验收契约](specs/module-zero-package-consumption/spec.md)。

## Decisions

### 以实际归档按拓扑生产三个新包

在框架子仓新增 `nupkg/pack-r3-module-zero-candidates.sh --version <10.5.1-r3.N> --r2-feed <R2源目录> --output <空目录>`。候选属性限于这三个项目及显式模式。MSBuild 求值、还原和 Release 打包使用相同属性。仅候选模式关闭自动打包，设置 `Du.` 前缀、候选 `PackageVersion` 和 `.snupkg`，并将四条原项目引用替换为以下可传播的框架包引用。保留普通模式的 `Version`、`GeneratePackageOnBuild`、原包 ID、原项目引用和既有构建配置，候选模式保留程序集、命名空间、目标、共享框架及私有工具等其他有效设置。

| 顺序 | 原 `PackageId` 和 `AssemblyName` | 候选 `PackageId` | 候选 `net9.0` nuspec 的直接框架依赖 |
| --- | --- | --- | --- |
| 1 | `Abp.Zero.Common` | `Du.Abp.Zero.Common` | `Du.Abp [10.5.1-r2.1]` |
| 2 | `Abp.ZeroCore` | `Du.Abp.ZeroCore` | `Du.Abp.Zero.Common [当轮版本]` |
| 3 | `Abp.ZeroCore.EntityFrameworkCore` | `Du.Abp.ZeroCore.EntityFrameworkCore` | `Du.Abp.ZeroCore [当轮版本]`、`Du.Abp.EntityFrameworkCore [10.5.1-r2.1]` |

首次拟选 `10.5.1-r3.2`，实施时核对现有分配和归档，以 R3 现有分配记录为共同占用范围原子保留实际版本。保留序号、生产源码树、对应的证明和归档位置。每批在新目录物化确定的框架输入，登记主仓 gitlink、本轮框架实施起点、实际生产基树与源树、普通构建对照提交。R2 三份原包的来源树、归档和 DLL 摘要按 `eng/r3_r2_reference.json` 核验。本轮候选的基树与源树按自己的生产证明核验。已提交源码核对提交及树，未提交源码沿用临时索引和对象库形成可重放补丁并重算源树。验证静态产物、还原及运行阶段前可以使用可重放的本地源码证明。 [R3 前批生产入口](../../../../aspnetboilerplate/nupkg/pack-r3-leaf-candidates.sh) · [候选生产说明](../../../../aspnetboilerplate/nupkg/README.r3.md)

每批从空 NuGet 包缓存和独立 HTTP 缓存开始，在框架源码以外准备工作目录，显式隔离配置及 fallback。R2 临时源仅放三份通过登记 SHA-256 核对的原归档，并逐项核对其 `net9.0` DLL。另设同批临时源，初始为空。每一步执行真实 restore 和 Release `pack --no-restore`，回读资产、缓存来源、编译器实际引用及其摘要。核对该步产出的 nuspec、目标、符号及来源证明后，将正式 `.nupkg` 原字节放入同批源供下一步还原。按实际资产图核对全部已选框架资产及直接边，包含传递的 R2 和同批包。编译器引用必须对应资产中的归档 DLL，源码项目输出或只修改 nuspec 无法满足该判据。第三方包由 nuget.org 提供，私有构建依赖按用途登记。三项目共用这一生产顺序和取证逻辑。 [R2 原包登记](../../../../eng/r3_r2_reference.json) · [R2 验收](../../../../docs/maintenance/r2-core-package-consumption.md)

### 用普通源码和实际普通归档对照

以 `457be917b46c4fb6237831baac5abb848ffe1c4b` 隔离构建三个普通 `net9.0` Release 对照。在实现后的三个原项目关闭候选属性，各用实际 Release 构建和普通 `pack` 核对默认生成行为、原包 ID、现有框架依赖组、共享框架引用、程序集和现有工具引用。对照普通与候选求值、普通与候选 nuspec，以及固定普通和两种实际 DLL 的 `TargetFrameworkAttribute`、程序集名与版本、根命名空间、公开及受保护 API、清单资源名称。保留包内许可、图标与匹配目标的 PDB 证据。各独立构建的 DLL 分别记录 SHA-256。冻结的候选 DLL 才在生产、还原、输出及运行环节要求字节一致。 [元数据工具](../../../../eng/r2-metadata/Program.cs) · [维护基线](../../../specs/maintenance-baseline/spec.md)

从固定普通 Release、修改后的普通 Release 和候选主包的 `net9.0` DLL 中读取嵌入资源。对 `Abp.Zero.Common` 的 `Abp.Zero.Localization.Source.*.xml` 和 `Abp.ZeroCore` 的 `Abp.Zero.Localization.SourceExt.*.xml`，分别以固定对照中的非空资源名集合为准，按完整资源名计算原始字节的 SHA-256。三份产物中的名称集合及每项摘要均须一致。发现缺项、多项或内容变化时，报告程序集与具体资源名，判定该批未通过。

源码回归复用 `aspnetboilerplate/test/Abp.ZeroCore.Tests`，沿用普通项目引用和 `TestServiceCollectionRegistrar` 的实际 SQLite 注册。必测 `Abp.Zero.Roles.RoleStore_Tests.Should_Get_Role_Claims` 及 R1 已验的四个角色批量更新用例，按 TRX 具名明细记录真实通过数。该套件通过 SampleApp、TestBase 和其他源码项目供给测试服务，包含 Mapper、Redis、OpenIddict 等原测试输入。独立包消费者仅实现与本轮运行断言相关的领域类型和装配。 [已验四用例](../../../../docs/maintenance/r1-dotnet10-runtime-migration.md#本地行为结果) · [SQLite 测试注册](../../../../aspnetboilerplate/test/Abp.ZeroCore.Tests/Zero/TestServiceCollectionRegistrar.cs) · [SampleApp 注册](../../../../aspnetboilerplate/test/Abp.ZeroCore.SampleApp/Core/ServicesCollectionDependencyRegistrar.cs)

### 从冻结实物还原独立消费者

在主仓新增 `validation/module-zero/` 独立 `net9.0` 进程。唯一的直接框架依赖为 `Du.Abp.ZeroCore.EntityFrameworkCore [当轮版本]`。还原图的四条新边见上表，另外两条是 `Du.Abp.EntityFrameworkCore → Du.Abp.EntityFramework.Common → Du.Abp`。R2 原包的这两条 nuspec 声明使用普通最低版本 `10.5.1-r2.1`，三份 R2 实包由受控源及冻结清单共同约束到 `10.5.1-r2.1`。图中共六个框架包、六条框架包间边。独立项目直接选用 EF Core SQLite `9.0.18`。记录实际第三方包、来源、版本、编译和运行资产，单列 `Microsoft.NETCore.App` 与 `Microsoft.AspNetCore.App` 的实际来源和加载版本。 [核心候选规范](../../../specs/core-package-consumption/spec.md) · [模板依赖规范](../../../specs/template-host-baseline/spec.md)

提供 `python3 -B eng/verify.py --profile r3-module-zero --dotnet <dotnet可执行文件> --candidate-feed <R3源> --candidate-manifest <生产清单> --candidate-symbols <符号目录> --r2-feed <R2源> --evidence-root <证据父目录>`。复用已有的执行记录、包来源、元数据及还原资产读取逻辑，各旧 profile、旧命令与批次原件继续使用自己的输入。登记三份主包、符号包、生产清单、源码及证据的身份和摘要。每次接受验收或后续复跑时核对并使用该批冻结实物，在新目录使用独立空缓存、带包源映射的 NuGet 配置。两个本地源各自独占对应框架 ID，第三方源保留实际使用记录。R2 和前一批 R3 原件继续可供各自复验。 [统一验证入口](../../../../eng/verify.py) · [既有框架包检查](../../../../eng/r3_leaf_packages.py)

用实际 restore 的资产做 Release `build --no-restore`。核对 nuspec、缓存元数据、NuGet 内容哈希和归档 SHA-256，保留实际 `project.assets.json`、编译引用、`.deps.json`、运行复制项及 Release 输出。对六份框架 DLL 逐一比对包内资产、还原路径、构建输出、实际加载位置与 SHA-256，查明每份 DLL 的唯一出处。实际记录 Provider 名、EF Core 与 SQLite 版本、Provider 选中资产和运行加载路径，包括可核对的 SQLite 原生资产。生产与消费都使用同一批 R3 实物及同一 R2 子集。 [资产读取](../../../../eng/r3_leaf_assets.py) · [R2 独立消费者](../../../../validation/minimal-backend/)

首次和严格复现使用 macOS ARM64、SDK `10.0.404`，显式指定 R2 工具环境的 `.git/r2-core-consumption/package-2/toolchain/overlay/dotnet`，要求实际加载的两项共享框架均为 `9.0.23`。消费复验支持通过 `--strict-runtime-baseline` 选择这一复现条件。普通复验也显式指定 `dotnet`，检查平台、SDK、进程架构和实际两项 `9.0.x` 加载版本与来源，按当轮实测范围报告。工具安装清单只提供环境输入，运行记录以实际加载位置为准。 [上一批复验口径](../../../../docs/maintenance/r3-signalr-log4net-candidates.md#消费验证器复验记录)

### 在 SQLite 执行真实角色工作单元

独立进程使用核心的 `AbpBootstrapper` 启动本地模块，依赖 `AbpZeroCoreEntityFrameworkCoreModule`，经其加载 ZeroCore、Zero.Common、EF Core 及内核模块。以 Probe 的租户、角色、用户类型及 `AbpZeroDbContext<TTenant, TRole, TUser, TSelf>` 实现与模板相同的核心接入。将所需 `AddAbpIdentity<Tenant, User, Role>`、实际 `AbpRoleStore<Role, User>` 派生实现和相关 DI 装配桥接到 Windsor，用 ABP EF 模块的 `AddDbContext` 注册 SQLite 上下文。启用多租户，停用该独立验证项目用不到的后台任务。用实际 ABP 模块及仓储处理租户和角色，SQLite 连接由当轮独立数据库文件提供。 [模块入口](../../../../aspnetboilerplate/src/Abp.ZeroCore.EntityFrameworkCore/Zero/EntityFrameworkCore/AbpZeroCoreEntityFrameworkCoreModule.cs) · [Zero DbContext](../../../../aspnetboilerplate/src/Abp.ZeroCore.EntityFrameworkCore/Zero/EntityFrameworkCore/AbpZeroDbContext.cs) · [角色存储](../../../../aspnetboilerplate/src/Abp.ZeroCore/Authorization/Roles/AbpRoleStore.cs)

1. 初始化 SQLite schema，在 host 工作单元通过 Zero 仓储写入两个不同且启用的租户并提交。两租户使用同一个独立 SQLite 文件，使跨租户检查经过实际查询过滤。记录租户 ID、Provider 及当轮数据库标识。
2. 为每个实际租户开启事务性工作单元，在解析角色存储及首次取得上下文前设置当前租户，确认适用于角色实体的 `MayHaveTenant` 过滤器启用。通过真实角色存储的 `CreateAsync` 写入一条含当轮标识的角色。记录实际仓储使用的 DbContext、角色 ID、SQLite 活动事务和写入结果。在工作单元的 `CompleteAsync` 成功后记录完成，释放写入作用域。关联事务与工作单元的证据可以使用 EF Core 事务事件及工作单元完成事件。
3. 两笔事务均已提交后，为每个租户分别创建新的 DI 作用域、工作单元和 DbContext。使用真实角色存储 `FindByIdAsync` 查询两个已提交的角色 ID，调用侧只传角色 ID。查自己的角色时核对 ID、名称和归属，查另一租户的角色时必须返回 `null`。记录两次命中、两次 `null`、上下文标识及实际加载程序集。查询抛出异常时该项失败。

### 留存诊断和交验记录

报告给出输入、阶段、命令、工作目录、退出码、原始资产、业务读回以及进程退出情况。诊断集中在一套定向入口，以新目录或副本复验同版本错字节、错误依赖或归属、受控源缺少传递包导致的真实 NuGet 还原失败，以及即使进程退出零也缺少提交、独立读回或租户对照的情况。报告标出具体包、阶段或行为断言，并保留已采集证据。使用局部夹具验证报告边界时标明模拟范围。完整消费者进程结束后保留可复核的 SQLite 文件和同轮日志。

实施时在框架维护候选生产说明，在主仓建立 `docs/maintenance/r3-module-zero-candidates.md` 和文档入口。写明新批生产与冻结实物消费复跑各自的命令，登记成功轮的原始报告路径、摘要和实际覆盖。模板缺口按原版观察与当前候选验收进度登记。 [维护文档索引](../../../../docs/README.md)

## Risks / Trade-offs

- 角色存储在 ABP 工作单元中保存实体，可靠的提交与隔离证据需要关系型事务完成和独立上下文。两个租户共用独立 SQLite 文件，具名源码回归覆盖原项目引用及既有调用。
- 受控源缺少 R2 原件或任一冻结包时，该轮诊断记录输入失败。恢复与登记匹配的实物后，用新的运行目录复跑。已发布到本地冻结目录的一批如需改变生产源码、依赖或包字节，保留旧批及证据，选择新的 R3 序号并重新验收。

## Migration Plan

本轮建立并验收独立包消费输入。复验失败时保留当前使用的原引用及原源配置，后续模板迁移再核对完整同批依赖闭包。

上一批 `10.5.1-r3.1` 的规范已随主仓 `4b00d40` 同步并归档，原件与验收记录可独立复验。本轮以新批次登记三包的实际生产树和消费证据。 [上一批归档](../2026-11-25-add-r3-signalr-log4net-candidates/) · [稳定规范](../../../specs/web-host-integration-package-consumption/spec.md)
