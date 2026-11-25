# R3 第二包设计

## Context

| 输入 | 规划时核对的身份与用途 |
| --- | --- |
| 主仓 `main` | `9859ebf4ccde930fd17b4ddfed8f40d2ae534dab`，树 `b9d9037aa62eebb5549a021b71cc2cf8d6b0a501`。登记框架及模板 gitlink |
| 框架 `dev` | `457be917b46c4fb6237831baac5abb848ffe1c4b`，树 `fb0abb6be5cb69b0e5ff395f4b010cf28511f9c8`。同目标普通构建对照，与 R2 实包候选源码树相同 |
| 模板 `master` | `2e9536872673a7ff1986a19e798c51684d16afe5`。Web.Host 接入参照，已实测原版框架包均为 `10.2.0`，其 Log4Net 链解析 `log4net 3.1.0` |
| R2 实包 | `10.5.1-r2.1` 的归档使用原始实物字节，包与资产摘要依据主仓登记；原归档保留原打包来源证明 |

固定框架的两个组件均为 `net9.0`，根命名空间为 `Abp`，各直接引用 `Abp.csproj`。SignalR 使用 Web SDK 提供的 ASP.NET Core 框架引用。Log4Net 声明 `log4net 3.3.2`。R2 的打包入口和验收器分别限定五个双目标项目和 `10.5.1-r2.N` 版本。[SignalR 项目](../../../../aspnetboilerplate/src/Abp.AspNetCore.SignalR/Abp.AspNetCore.SignalR.csproj) · [Log4Net 项目](../../../../aspnetboilerplate/src/Abp.Castle.Log4Net/Abp.Castle.Log4Net.csproj) · [R2 打包](../../../../aspnetboilerplate/nupkg/pack-r2-candidates.sh) · [R2 实物登记](../../../../eng/r3_r2_reference.json) · [R3 首包归档](../2026-11-25-baseline-r3-web-host-dependencies/)

## Goals / Non-Goals

把两个候选从生产时的核心编译资产追溯到消费者实际加载的程序集，并为各自的关键行为取得独立断言。两个组件以独立最小宿主取证，完整迁移范围见[提案](proposal.md)，验收条件见[增量规范](specs/web-host-integration-package-consumption/spec.md)。

## Decisions

### 两个项目用显式候选模式引用已验核心

在框架子仓新增 `nupkg/pack-r3-leaf-candidates.sh --version <10.5.1-r3.N> --r2-feed <R2源目录> --output <空目录>`。从源码生产新候选时，使用未分配的版本，首选 `10.5.1-r3.1`，沿用 R2 的惯例在 Git 公共目录按独立的 R3 记录原子分配。任务 1.2 从隔离输出锁定 `feed/` 中的两份包、`symbols/` 中的两份符号包、清单、源码证明、实际生产资产和日志，并将这批实物及摘要交给主仓验收。

仅在这两个项目且显式设置 `DuR3CandidatePack=true` 时，移除原核心 `ProjectReference`，增加可传播的 `PackageReference Include="Du.Abp" Version="[10.5.1-r2.1]"`。同一候选属性贯穿求值、还原、构建和 pack。给原 `PackageId` 加 `Du.` 前缀，仅覆盖 `PackageVersion`，禁止 build 连带 pack，保留程序集相关属性、私有工具及第三方引用。普通模式仍使用原 `ProjectReference`、包 ID 及构建属性。两种模式分别保存项目求值，核对候选 `.nuspec` 的唯一框架边是 `Du.Abp [10.5.1-r2.1]`，并核对 SignalR 的 `Microsoft.AspNetCore.App` 框架引用和 Log4Net 的普通依赖范围。

在修订后的两个原项目上，各执行一次未设置候选属性的 `dotnet pack -c Release`，将普通产物写到候选源以外的目录。打开两份 `.nupkg` 中的 `.nuspec`，核对包 ID 分别为 `Abp.AspNetCore.SignalR`、`Abp.Castle.Log4Net`，`net9.0` 组的直接框架包依赖均仅为原 `Abp`。SignalR 须保留 `Microsoft.AspNetCore.App` 框架引用，Log4Net 须保留 `log4net` 自 `3.3.2` 起的原依赖范围。

生产者为 `Du.Abp` 单独准备本地源，只复制与登记 SHA-256 匹配的 `10.5.1-r2.1` 归档。其余包通过 nuget.org 获取。在每批新目录使用独立空全局包缓存、HTTP 缓存、显式源映射和清空的 fallback 目录，核对 `project.assets.json`、NuGet 缓存元数据、核心归档和选中 `lib/net9.0/Abp.dll` 的摘要。为该脚本在子仓登记核心归档和资产的预期摘要，主仓验证时与 R2 已验登记交叉核对。确认还原资产后，用同配置和缓存执行 Release `pack --no-restore`，核对实际编译引用的 `Abp.dll` 路径及摘要与该资产一致。

以固定框架提交隔离重建普通 Release 对照。在隔离目录物化候选源码，记录候选实际源树和相对固定基线的打包改动。未提交实现可沿用 R2 的单独 Git 索引和对象目录捕获、重放补丁并核对源树，已提交实现则核对提交、树和对应的基线差异。实现阶段的验收无需先提交。实际包内核对 fork 仓库、来源证明、与候选树一致的许可和图标，两份 `.nupkg` 各只有 `lib/net9.0` 一个库目标，相应 `.snupkg` 含该目标的 PDB。核对实际 DLL 的 `TargetFrameworkAttribute`，对照普通构建的 `AssemblyName`、`RootNamespace`、程序集版本、公共及受保护 API 和清单资源。对照允许不同构建的字节摘要有差异，候选字节在所有消费阶段须一致。[维护基线规范](../../../specs/maintenance-baseline/spec.md) · [现有程序集清单工具](../../../../docs/maintenance/baseline-tools/Program.cs)

复用 R2 核心实物能使本轮只验证新增边和两个组件。仅修改 nuspec 无法证明生产者编译时用过 R2 核心，扩展 R2 profile 会改变既有批次与目标约束。本轮采用单独入口和包引用，完整模板阶段再选择新版本重建同批闭包。R2 的实测结果继续绑定原包与原 SQLite 消费者，本轮结果以本轮真实加载和行为断言为准。[R2 证据](../../../../docs/maintenance/r2-core-package-consumption.md) · [完整迁移准入](../../../../docs/maintenance/r3-web-host-baseline.md#闭包与迁移准入)

### 从两批实际包运行新的最小消费者

新增 `validation/signalr-log4net/` 独立 `net9.0` Web 项目，根引用锁到本轮两包及 `Du.Abp.AspNetCore [10.5.1-r2.1]`。框架闭包正好五个包和四条内部边。

| 来源 | 框架依赖边 |
| --- | --- |
| 本轮 R3 两包 | `Du.Abp.AspNetCore.SignalR → Du.Abp`、`Du.Abp.Castle.Log4Net → Du.Abp` |
| 已验 R2 三包 | `Du.Abp.AspNetCore → Du.Abp.Web.Common → Du.Abp`，三包均精确解析到 `10.5.1-r2.1` |

新增 `python3 eng/verify.py --profile r3-signalr-log4net --dotnet <dotnet可执行文件> --candidate-feed <R3源> --candidate-manifest <R3清单> --candidate-symbols <R3符号目录> --r2-feed <R2源> --evidence-root <证据父目录>`。复用现有运行目录、命令和阶段报告及通用资产读取约定。R0、R2、R3 首包入口保留各自参数和输入。

任务 4.1 和同批后续消费复验均使用任务 1.2 锁定的两份 `.nupkg`、两份 `.snupkg`、原清单和生产来源证据。验证器核对上述 R3 原件的摘要，并依 R2 登记检查和复制确切的三份 R2 原包。每次消费复验创建新运行目录和空缓存，使用显式源映射，两批包各由自己的本地源独占提供，第三方源为 nuget.org。消费复验沿用已分配版本和实物。首次验收从主仓根目录传入 `--dotnet "$PWD/.git/r2-core-consumption/package-2/toolchain/overlay/dotnet"`，沿用 R2 的 SDK `10.0.404` 和 ARM64 运行环境。还原、构建和启动宿主均使用传入的可执行文件。报告记录该路径、所选 SDK 和宿主进程架构，并从进程加载的文件路径核对 `Microsoft.NETCore.App` 与 `Microsoft.AspNetCore.App` 的实际版本，首次验收两者均应为 `9.0.23`。后续复验同样显式传入所用路径，按当轮实测版本登记。

先实际 restore，再用该资产做 Release `build --no-restore`。从资产、`.deps.json`、选中的运行复制项及进程实读位置核对各框架 DLL 和 `log4net.dll` 的唯一归属及 SHA-256。分开登记 NuGet 内容哈希与实际归档字节摘要。SignalR 服务端由共享框架提供，独立验证项目使用 `Microsoft.AspNetCore.SignalR.Client` 作为客户端辅助包，拟固定 `9.0.18` 并记录实际包与解析资产，选择的客户端版本只属于验证项目。逐项登记原版 Host `10.2.0`、原版 log4net `3.1.0`、维护源码声明 `3.3.2` 对应的普通范围和本轮实际选中版本、资产、加载身份。遇到第三方解析差异时给出依赖边、范围、实际版本和影响，保留原项目依赖声明。[统一验证入口](../../../../eng/verify.py) · [R2 最小消费者](../../../../validation/minimal-backend/) · [原版对照](../../../../docs/maintenance/r3-web-host-baseline.json)

### 通过正常接入执行两条运行断言

沿用模板和 R2 消费者的 `UseCastleWindsor`、`AddAbpWithoutCreatingServiceProvider` 与 `UseAbp` 入口，启动模块依赖 `AbpAspNetCoreModule`、`AbpAspNetCoreSignalRModule` 和 `AbpCastleLog4NetModule`。每轮运行一个新进程，Kestrel 仅绑定 `127.0.0.1:0`，从服务器取实际端口。验证项目可在同一进程驱动真实客户端和宿主内探针，避免增加探针 HTTP API。

1. 通过 `AddSignalR`、`MapHub<AbpCommonHub>("/signalr")` 启用实际 Hub。仅在此验证项目中使用本轮内存票据与测试认证方案，为持票连接生成包含 `AbpClaimTypes.UserId` 的身份，按需包含测试租户声明。票据只在本轮回环客户端与验证宿主内使用。
2. 客户端先订阅 `getNotification`，再建立连接。在线登记由 `OnlineClientHubBase.OnConnectedAsync` 完成。用实际 `IOnlineClientManager` 有界等待并核对连接 ID 和测试身份，再调用 `Register` 验证 Hub 方法可调用。从宿主的 `INotificationConfiguration.Notifiers` 查找模块登记的 `SignalRRealTimeNotifier`。缺少该项时在发送前报告配置缺失并判定失败。找到后，使用集合返回的 `notifierType`，沿用 `DefaultNotificationDistributer` 的 `ResolveAsDisposable<IRealTimeNotifier>(notifierType)` 解析实例，调用 `SendNotificationsAsync` 向该用户发送含固定通知名、当轮通知 ID、用户 ID 与唯一标识的 `UserNotification`。客户端核对收到的 JSON 中的用户、通知 ID、名称和数据标识。主动停止连接后，按同一连接 ID 有界等待记录移除。
3. 同一宿主在 Windsor 上启用 `LoggingFacility` 的 `UseAbpLog4Net().WithConfig(...)`。生成独立 XML 配置，用专属 FileAppender 新文件输出 `%level|%logger|%message`，从 Castle `ILoggerFactory` 取得有固定类别的 `ILogger`，写入 `INFO` 和当轮唯一标识。实际文件读回须命中完整的等级、类别、标识行，核对插件和底层 log4net 的真实加载文件。现有源码 `Abp.Castle.Log4Net.Tests` 的定向用例只断言文件存在，单独保留为普通模式的回归证据。

固定模板通过 Web.Core 加载 SignalR 模块，Web.Host 注册 Hub 与 Log4Net。Angular 的 `SignalRAspNetCoreHelper` 使用 `/signalr` 和 `abp.signalr-client.js`，脚本有 `Register` 与 `getNotification` 路径。本轮以 .NET 客户端覆盖该服务端契约，模板真实认证、Angular 客户端和数据库留待完整迁移。[模板 Startup](../../../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.Web.Host/Startup/Startup.cs) · [Angular 入口](../../../../module-zero-core-template/angular/src/shared/helpers/SignalRAspNetCoreHelper.ts) · [通知器注册](../../../../aspnetboilerplate/src/Abp.AspNetCore.SignalR/AspNetCore/SignalR/AbpAspNetCoreSignalRModule.cs) · [分发器解析](../../../../aspnetboilerplate/src/Abp/Notifications/DefaultNotificationDistributer.cs) · [SignalR 通知器](../../../../aspnetboilerplate/src/Abp.AspNetCore.SignalR/AspNetCore/SignalR/Notifications/SignalRRealTimeNotifier.cs) · [日志源码测试](../../../../aspnetboilerplate/test/Abp.Castle.Log4Net.Tests/Castle_Log4Net_Tests.cs)

### 复跑报告与失败诊断

- 每轮报告关联主仓提交与 gitlink、基线及候选框架树、包与符号摘要、来源配置与缓存证据、SDK/运行时、命令/退出码、原始资产、Release 输出、实际加载摘要、SignalR 观察值及独立日志文件。注明打包、还原、构建、两条运行断言和停机的实际状态。客户端及宿主在成功、失败和超时路径均关闭，父进程超时须终止并等候子进程退出。票据不进入命令、日志或证据。
- 定向负例使用新目录和包或证据副本。用同版本改字节的 R2 核心验证生产者和验证器拒绝，另核对错误核心范围或原 ID 的实际 nuspec，以及受控源缺包导致的真实还原失败。用独立运行证据夹具保留宿主成功状态并检查通知缺失、连接未移除和日志文本错误的诊断。报告指明首个失败阶段和后续未执行项。
- 集成验收前编写 `docs/maintenance/r3-signalr-log4net-candidates.md`，建立索引，分别记录从源码生产新候选和使用已有实物复验消费的命令。任务 4.1 首次通过后补录该轮最终报告路径和摘要、对应的生产清单与实物摘要、执行与未执行范围。每次复验的日志和报告各自保存在新证据目录。沿用 R2 归档登记和 R3 首包对照。
- 已锁定批次需要改变生产源码、生产依赖或包字节时，递增候选版本，重做受影响的生产与消费验收，保存新旧两批实物和证据，记录换批原因及验证结果。同一批次的消费失败可在新目录用相同字节诊断和重试。

## Risks / Trade-offs

- SignalR 通知器内部记录异常后可能返回，验收以真实客户端收到并读回负载为准。在线生命周期使用有界等待，便于区分异步登记或移除与失败。
- R2 原包只在已验实物可取得时适用。缺失或摘要不符时记录输入失败，恢复同一实物后在新目录复跑。
- 该混合闭包仅为本机定向验收。需升级核心或迁移完整模板时分配新批次，重跑闭包与运行验收。回退可恢复原消费引用及其既有来源，并保留各批证据。
