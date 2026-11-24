# R1 核心源码运行时迁移设计

## Context

动机见[提案](proposal.md)。规划输入为主仓 `5cea65ca538623e0a1049a872a9ea52a1c1da464`，其框架 gitlink 与框架 `dev` 均为 `d08617b51bb7c7e5d0bea942e7e10b2677240c35`，框架树为 `24c938b8d020469537cf69e794478df6436eb28d`。

R1 对照是该框架树的已接受结果。五份 Release DLL 的 API 已包含查询过滤补丁增量，三套回归为 `1105/0/2`、`150/0/0`、`80/0/0`（通过/失败/跳过），合计 `1335/0/2`。EF 套件包含 22 项新增用例。R0 的 `6c4580c5e7ea41154696c071a53fd200059a768b` 与 `1313/0/2` 用于历史追溯。原始 R1 证据见验收记录所列 `.git/r1-query-filter-evidence-2026-11-24.tar.gz` 的 `revision-2/`。优先复用可读、身份可核对的 API 清单、依赖清单和 TRX。证据缺失时，用独立目录按记录重建 `d08617b` 的缺项，记录实际输入与工具，不用 R0 输出填补。 [R1 验收记录](../../../../docs/maintenance/r1-efcore-query-filter.md) · [R0 复验手册](../../../../docs/maintenance/baseline-evidence/README.md)

## Goals / Non-Goals

核心 Release 候选可以逐项复核，保留当前源码使用路径和已接受的查询过滤契约。.NET 9 兼容范围限于同仓源码调用方，.NET 10 行为验证限于已执行的环境与 Provider。包身份、包消费、发布和全仓迁移按[提案](proposal.md)所列范围分期。

## Decisions

### 固定项目闭包与现有源码入口

以下路径相对 `aspnetboilerplate/`。项目依赖列为当前跟踪的项目文件中的直接边。

| 项目 | 直接项目引用 | 目标 |
| --- | --- | --- |
| `src/Abp/Abp.csproj` | 无 | 9、10 |
| `src/Abp.AspNetCore/Abp.AspNetCore.csproj` | `Abp.Web.Common` | 9、10 |
| `src/Abp.EntityFramework.Common/Abp.EntityFramework.Common.csproj` | `Abp` | 9、10 |
| `src/Abp.EntityFrameworkCore/Abp.EntityFrameworkCore.csproj` | `Abp.EntityFramework.Common` | 9、10 |
| `src/Abp.Web.Common/Abp.Web.Common.csproj` | `Abp` | 9、10 |
| `src/Abp.TestBase/Abp.TestBase.csproj` | `Abp` | 9、10 |
| `src/Abp.AspNetCore.TestBase/Abp.AspNetCore.TestBase.csproj` | `Abp.AspNetCore`、`Abp.TestBase` | 9、10 |
| `src/Abp.FluentValidation/Abp.FluentValidation.csproj` | `Abp` | 9、10 |
| `test/Abp.Tests/Abp.Tests.csproj` | `Abp`、`Abp.TestBase` | 9、10 |
| `test/Abp.AspNetCore.Tests/Abp.AspNetCore.Tests.csproj` | `Abp.AspNetCore.TestBase`、`Abp.FluentValidation`、`Abp.Tests` | 10 |
| `test/Abp.EntityFrameworkCore.Tests/Abp.EntityFrameworkCore.Tests.csproj` | `Abp.EntityFrameworkCore`、`Abp.TestBase`、`Abp.Tests` | 10 |

从框架 63 个跟踪的 `.csproj` 解析字面 `ProjectReference`，闭包外 36 个项目共有 47 条直接边。当前直接引用方如下，跨行重复表示单个项目引用多个闭包成员。实施时用实际 MSBuild/NuGet 求值核对目标选择。

| 被引用项目 | 闭包外直接引用方 |
| --- | --- |
| `Abp` | `Abp.AspNetCore.OData`、`Abp.AspNetCore.SignalR`、`Abp.AutoMapper`、`Abp.BlobStoring`、`Abp.Castle.Log4Net`、`Abp.Dapper`、`Abp.EntityFramework`、`Abp.FluentMigrator`、`Abp.HangFire.AspNetCore`、`Abp.HangFire`、`Abp.HtmlSanitizer`、`Abp.MailKit`、`Abp.MemoryDb`、`Abp.MongoDB`、`Abp.NHibernate`、`Abp.Quartz`、`Abp.RedisCache`、`Abp.Zero.Common`、`Abp.EntityFrameworkCore.Dapper.Tests` |
| `Abp.AspNetCore` | `Abp.AspNetCore.OData`、`Abp.AspNetCore.OpenIddict`、`Abp.HtmlSanitizer`、`AbpAspNetCoreDemo.PlugIn`、`AbpAspNetCoreDemo` |
| `Abp.EntityFramework.Common` | `Abp.EntityFramework` |
| `Abp.EntityFrameworkCore` | `Abp.ZeroCore.EntityFrameworkCore`、`Abp.EntityFrameworkCore.Dapper.Tests`、`AbpAspNetCoreDemo` |
| `Abp.Web.Common` | `Abp.Web.Common.Tests` |
| `Abp.TestBase` | `Abp.Dapper.Tests`、`Abp.EntityFrameworkCore.Dapper.Tests`、`Abp.Quartz.Tests`、`Abp.TestBase.Tests`、`Abp.Web.Common.Tests`、`Abp.ZeroCore.Tests` |
| `Abp.Tests` | `Abp.AutoMapper.Tests`、`Abp.BlobStoring.Azure.Tests`、`Abp.BlobStoring.FileSystem.Tests`、`Abp.BlobStoring.Tests`、`Abp.Castle.Log4Net.Tests`、`Abp.Dapper.Tests`、`Abp.MailKit.Tests`、`Abp.MemoryDb.Tests`、`Abp.Quartz.Tests`、`Abp.RedisCache.Tests`、`Abp.TestBase.Tests`、`Abp.Web.Common.Tests` |

一次性迁移反向闭包会涉及 Module Zero、EF6、Demo 及其他适配层。本轮采用多目标保留其现有引用。无闭包外直接边的 `Abp.AspNetCore.TestBase`、`Abp.FluentValidation` 也是既有公共源码项目，和其余源码一起保留 9 目标。仅两套无外部调用方的测试工程使用单一 10 目标，缩小双目标维护面。默认解 `Abp.sln` 的项目成员关系保持有效。

### 锁定候选工具链与依赖

- 框架 `global.json` 从 9.0 RC 起始值调整至稳定 SDK `10.0.404`，候选和 Windows 入口使用同一精确 SDK，设置 `rollForward: disable`、`allowPrerelease: false`。10 目标拟以 `Microsoft.NETCore.App` 与 `Microsoft.AspNetCore.App` `10.0.15` 验证。9 调用方用同一 10 SDK 构建。本机已有 .NET / ASP.NET Core `9.0.10`，实施时为 9 兼容验收准备 `9.0.23`，Windows 工作流用 SDK `9.0.321` 提供该运行时。9 兼容只作过渡验证。R0 继续使用其固定的 `9.0.306`，历史 R1 证据保留其原环境。 [微软 .NET 10 发行元数据](https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/10.0/releases.json) · [微软 .NET 9 发行元数据](https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/9.0/releases.json)
- 对 `net10.0` 将 EF Core、Relational、Sqlite、InMemory、Microsoft.Data.Sqlite、ASP.NET Core TestHost、Mvc.NewtonsoftJson 与 Razor.RuntimeCompilation 对齐至 `10.0.15`。随上述图需要对齐的 `Microsoft.Extensions`（如 Options 和 Caching.Memory）、`System.Text.Json` 等同版本族依赖使用该补丁线。多目标项目按内部构建的 `TargetFramework` 使用条件引用，保留 `net9.0` 的现有声明。对 `Abp` 已直接使用的 `Microsoft.VisualStudio.Web.CodeGeneration.Design`，10 目标采用独立版本 `10.0.3`，核对它引入的 ASP.NET Core、EF Core、Roslyn 与 scaffolding 依赖。只有在证据显示实际版本冲突或不兼容时调整其他包，并保留变更原因。 [EF Core Relational](https://www.nuget.org/packages/Microsoft.EntityFrameworkCore.Relational/10.0.15) · [TestHost](https://www.nuget.org/packages/Microsoft.AspNetCore.TestHost/10.0.15) · [Web CodeGeneration](https://www.nuget.org/packages/Microsoft.VisualStudio.Web.CodeGeneration.Design/10.0.3)
- 保留 Castle、FluentValidation、xUnit、测试 SDK、测试适配器及其他独立依赖的现有版本作为起点。 `common.props` 提供版本 `10.5.1` 和部分项目的 Release 自动打包，验收传入 `GeneratePackageOnBuild=false` 只生成程序集。它与 `Directory.Build.props` 的 SourceLink 重复声明已有 `NU1504` 记录，比较 SDK 10 下是否引发实际阻塞。跟踪直接引用的精确声明与选定工具版本，用实际 `project.assets.json` 和包内容哈希记录传递图。公共包当前沿用各自的 `PackageId`、`AssemblyName`、`RootNamespace`，其中 `Abp.EntityFramework.Common` 的根命名空间为 `Abp.EntityFramework`。

### 按边界适配代码

- `AbpEfCoreDatabase.cs` 在 EF 10 实现 `IDatabase.CompileQueryExpression<TResult>(Expression, bool)` 并向内部服务原样转发，保留开始和释放编译作用域的语义。9 目标保留带 `IReadOnlySet<string>` 的当前公开虚方法。两种目标保留 `CompileQuery`、`GetRequiredContext()` 等其余已接受调用路径。把 10 目标这一签名变化列入 API 对照。 [EF Core 10.0.15 IDatabase](https://raw.githubusercontent.com/dotnet/efcore/v10.0.15/src/EFCore/Storage/IDatabase.cs)
- 在 `net10.0` 的 `QueryCompilationScope_Tests` 中直接调用 `AbpEfCoreDatabase.CompileQueryExpression<TResult>(query, async)`。用现有 `IDatabase` 替身核对表达式对象和 `async` 值（`false`、`true`）原样传入，返回的表达式原样传出。让替身在已授权查询中读取绑定的 DbContext，在嵌套的未授权查询中确认该上下文不可见。分别覆盖内部服务正常返回和抛错，检查调用前的上下文在两条路径上都得到恢复，异常原样传出。把新增用例单列在 EF Core 套件的 TRX 对照中。
- 同步核对 `AbpEntityQueryProvider` / `IQueryCompiler`、`AbpCompiledQueryCacheKeyGenerator`、`AbpDbContextOptionsExtension`、`DefaultDbContextResolver` 和 `AbpDbContext`。保留默认关闭、关系型服务装饰、InMemory 自有服务、`ReplaceService` 冲突校验、查询绑定的上下文授权、软删除列映射。继续使用现有 R1 #7219 用例验证普通查询、默认和启用配置、同步与异步编译及上下文生命周期；测试数据沿用受控的 SQLite 与 InMemory 夹具。 [EF Core 查询过滤规范](../../../specs/efcore-query-filters/spec.md)
- `Repositories/EfCoreRepositoryExtensions.cs` 的两处 `BatchUpdateAsync` 目前接受 `SetPropertyCalls<T>` 表达式。10 目标随 EF 10 改用 `Action<UpdateSettersBuilder<T>>`，保留方法名、谓词合并、过滤和受影响行数语义。9 目标保留原参数类型。用现有 `Abp.ZeroCore.Tests` 的调用形态核对 9 源码，并在 10 的 EF Core 套件中检查 SQLite 上常用 lambda 的更新结果与过滤范围。若既有三套回归缺少这条路径，补一个定向用例。已有显式表达式类型、方法组或覆写的迁移差异随 API 报告记录。 [EF Core 10 破坏性变更](https://learn.microsoft.com/en-us/ef/core/what-is-new/ef-core-10.0/breaking-changes)
- `AbpServiceCollectionExtensions.cs` 的 Razor 注册将 `EmbeddedResourceViewFileProvider` 加入 `MvcRazorRuntimeCompilationOptions.FileProviders`。.NET 10 将该 API 标为过时，候选保留原提供程序与注册顺序，局部记录 `ASPDEPR003`。现有 ASP.NET Core 核心套件使用 TestServer、MVC、身份验证和 Razor Pages 路由。额外核实选项解析与嵌入式视图提供程序仍有效，如果既有回归未覆盖则在同一测试宿主补一个聚焦检查。保留现有 MVC JSON 和路由入口，单独记录实际触发的其他 .NET 10 行为变化。 [ASP.NET Core 迁移指南](https://learn.microsoft.com/en-us/aspnet/core/migration/90-to-100?view=aspnetcore-10.0) · [Razor 过时说明](https://learn.microsoft.com/en-us/aspnet/core/breaking-changes/10/razor-runtime-compilation-obsolete?view=aspnetcore-10.0)

### 本地候选取证

以 macOS ARM64 为本地验收环境，在获授权的框架候选目录执行。每轮先固定基础提交、候选树和补丁摘要，使还原、构建、API、回归在同一树上执行。记录实际 SDK、MSBuild、系统/RID、共享运行时、VSTest、xUnit 适配器、Provider 与 SQLite 版本。用新的绝对目录 `R1_NET10`、`R1_NET9` 隔离候选两条路径的资产、包缓存、日志及测试结果。历史对照若需重建，使用第三个目录和其独立工具链。

`R1_NUGET_CONFIG` 指向只启用 nuget.org 的独立配置。`R1_NET10/R1.sln` 由实施者临时用 `dotnet new sln --format sln -n R1 -o "$R1_NET10"` 生成，再用 `dotnet sln "$R1_NET10/R1.sln" add <项目路径>` 加入上表全部 11 个项目。保留 MSBuild 自己的项目引用解析。多目标还原会生成 20 个项目目标，其中 11 个 `net10.0`、9 个 `net9.0`，以实际无 RID 资产为准。以下命令在候选子仓根执行。

```sh
set -eu
export NUGET_PACKAGES="$R1_NET10/packages"
dotnet restore "$R1_NET10/R1.sln" --configfile "$R1_NUGET_CONFIG" \
  --no-http-cache --force -p:Configuration=Release -p:ArtifactsPath="$R1_NET10/artifacts" \
  -p:GeneratePackageOnBuild=false --disable-build-servers
dotnet build "$R1_NET10/R1.sln" -c Release -f net10.0 --no-restore \
  -p:ArtifactsPath="$R1_NET10/artifacts" -p:GeneratePackageOnBuild=false --disable-build-servers
for suite in Abp.Tests Abp.AspNetCore.Tests Abp.EntityFrameworkCore.Tests; do
  dotnet test "test/$suite/$suite.csproj" -c Release -f net10.0 --no-build --no-restore \
    -p:ArtifactsPath="$R1_NET10/artifacts" -p:GeneratePackageOnBuild=false --disable-build-servers \
    --logger "trx;LogFileName=$suite.trx" --results-directory "$R1_NET10/trx" || exit 1
done
```

- 实施时在主仓新增受版本控制的 R1 依赖清单入口 `eng/r1_restore_inventory.py`，随同本轮验收输入固定版本。它在候选框架根以相同 Release 和 `ArtifactsPath` 参数调用 `dotnet msbuild <项目> -p:Configuration=Release -p:ArtifactsPath=<目录> -getProperty:MSBuildProjectFullPath,ProjectAssetsFile`，读取实际资产路径及项目身份，核对资产内的 `project.restore.projectPath`、包缓存路径和 Restore 来源，沿相应目标的项目引用遍历。对每一目标读取直接和传递包、实际版本、来源及内容哈希。缺少资产、项目/目标不符或缺少包元数据时返回非零。输出沿用 `docs/maintenance/baseline-tools/inventory.py` 的字段，并复用其比较逻辑。R0 入口、历史工具及历史清单继续按原契约使用。
- 在主仓根执行拟新增命令 `python3 eng/r1_restore_inventory.py --framework-root "$R1_FRAMEWORK" --artifacts-path "$R1_NET10/artifacts" --packages-root "$R1_NET10/packages" --scope core --output "$R1_NET10/restore-inventory.json"`。其中 `R1_FRAMEWORK` 为候选框架根的绝对路径。用 9 工件目录和 `--scope compat` 记录五个核心项目、下列六个原调用方及其实际 9 闭包。两次还原后均直接运行同一入口。核心清单按项目比较候选 9 与历史 R1 9，同一项目的候选 10 明确标记 TFM 后与历史 R1 9 对照。记录版本、包路径、依赖提升和告警的实际差异及原因。
- 以 `dotnet msbuild <项目> -p:Configuration=Release -p:TargetFramework=net10.0 -p:ArtifactsPath=<目录> -getProperty:PackageId,PackageVersion,AssemblyName,RootNamespace,TargetFramework,TargetPath -getItem:ProjectReference` 定位五份实际候选 DLL。对其保存 SHA-256，使用主仓 `docs/maintenance/baseline-tools/ApiInventory.csproj`（元数据提取工具当前目标为 `net9.0`，单独构建与运行）各提取两次。通过 `python3 docs/maintenance/baseline-tools/inventory.py compare-api <R1清单> <候选清单>` 逐项比对程序集身份、公共及受保护类型/成员和嵌入资源，核对五个 9 目标的身份与公开 API 仍与 R1 相容。哈希用于定位产物，跨工具链 API 是否等价由清单判断。
- 核对三套真正的 10 目标运行、对应 DLL、`.runtimeconfig.json`、依赖文件、TRX 路径和退出码。以 TRX 的 `UnitTestResult`、测试定义及汇总计数对照 R1 测试完整名称与结果。迁移前预期 `1105/0/2 + 150/0/0 + 80/0/0`，包括 22 项 EF 新增用例。只允许两项已有具名跳过 `Castle_Should_Register_Unicode_Names_In_Conventions`、`Test_GetAllStrings`，实际按基线 TRX 全名和原因核对。旧运行器的 42 个重复 ID 和 `notExecuted` 汇总差异按当次明细解释，保留原始报告。对每项新增或重命名测试记录对应关系。缺失、零匹配、失败、额外跳过、无对应的回归用例或无法解释的汇总矛盾均阻断验收。
- 关系型测试使用内存 SQLite（`Data Source=:memory:`），InMemory 仅用于现有非关系服务验证。按 R1 报告的八个场景与其余补丁用例逐项核对，用例继续使用带修复的候选源码。若候选涉及上述批量更新或 Razor 的行为缺口，补充覆盖正常使用的少量回归，并把数量增量与基线区分。

在 `R1_NET9` 生成另一个临时解决方案。入口为五个核心项目以及以下六个闭包外入口，覆盖所有七处反向引用边界，也覆盖实际批量更新旧签名的调用。

| .NET 9 入口 | 验证 |
| --- | --- |
| `src/Abp.EntityFramework/Abp.EntityFramework.csproj` | 还原、Release 构建，覆盖 EF6 对 `Abp.EntityFramework.Common` 和 `Abp` 的引用 |
| `src/Abp.ZeroCore.EntityFrameworkCore/Abp.ZeroCore.EntityFrameworkCore.csproj` | 还原、Release 构建，覆盖 Module Zero 对 EF Core 的引用 |
| `test/aspnet-core-demo/AbpAspNetCoreDemo/AbpAspNetCoreDemo.csproj` | 还原、Release 构建，覆盖 MVC 和 EF Core 扩展的实际源码入口 |
| `test/Abp.Web.Common.Tests/Abp.Web.Common.Tests.csproj` | 还原、Release 构建、全套项目测试，覆盖 `Abp.Web.Common`、`Abp.TestBase`、`Abp.Tests` |
| `test/Abp.EntityFrameworkCore.Dapper.Tests/Abp.EntityFrameworkCore.Dapper.Tests.csproj` | 还原、Release 构建、全套项目测试，覆盖 9 目标的 EF Core SQLite 与 Dapper |
| `test/Abp.ZeroCore.Tests/Abp.ZeroCore.Tests.csproj` | 还原、Release 构建，运行 `--filter 'FullyQualifiedName~Abp.Zero.EFPlus.AbpEntityFrameworkCoreBulkRepositoryExtensions_Tests&FullyQualifiedName~BatchUpdate'` |

按上述类全名和下列方法名逐项核对本次 `net9.0` TRX，四项结果均须为 `Passed`。

- `Should_Update_All_Tenant_Roles_When_Using_BatchUpdate`
- `Should_Update_Filtered_Entities_Using_BatchUpdate`
- `Should_Use_MayHaveTenant_Filter_When_Updating_Entities_Using_BatchUpdate`
- `Should_Update_All_Roles_When_MayHaveTenant_Filter_Is_Disabled_When_Using_BatchUpdate`

在框架候选根用 9 目录及空包缓存还原该临时解决方案。随后逐个以原调用方项目路径执行 `dotnet build "$project" -c Release --no-restore -p:ArtifactsPath="$R1_NET9/artifacts" -p:GeneratePackageOnBuild=false --disable-build-servers`，让项目使用自身默认目标。对表中三个测试项目按同样参数执行 `dotnet test "$project" -c Release --no-build --no-restore`，按需附上表中的过滤器，沿用独立的 TRX 日志名和结果目录。构建和测试原调用方时省略 `-f` 与 `TargetFramework` 覆盖。五个双目标核心项目可单独用 `-f net9.0` 补齐 DLL 对照。

从六个调用方的实际还原目标、引用资产和 `.deps.json`（适用时）确认框架选择，同一项目的 `TargetPath` 及依赖图应指向该轮的 9 产物与相应依赖。Web 和 EF 路径分别核对 ASP.NET Core 9 与 EF Core 9。两份全套和一份定向 TRX 须有用例明细，测试前核实两类 9 共享框架。其他闭包外项目由 Windows 默认解覆盖到的范围另记。

### Windows PR 与主仓证据

- 现有 `.github/workflows/build-and-test.yml` 在 `windows-latest` 运行，`pull_request` 仅匹配 `*.cs`、`*.cshtml`、`*.csproj`、`*.razor`，使用 checkout v2、setup-dotnet v3 与 `9.0.100-rc.2.24474.11`，依次执行默认解 restore/build/test。实施时沿用该工作流，并补入自身路径、`global.json`、公共 props 和 `Abp.sln` 的触发路径。准备 10 SDK 与 9 共享运行时，核对 Windows 的实际 SDK、架构和 runtime。保留 `Abp.sln` 默认全解验证，使用 Release 与同一 restore/build/test 工件，避免整解强制一个 TFM。分别报告必要的 10 和 9 结果。
- 真实候选 CI 需在用户授权后以框架 PR 运行。记录 `head`、实际 checkout 或 PR 合并提交及其树、run/attempt、runner、工具链和日志/TRX。若 PR 合并树不同，单独标识其覆盖并为实际拟交付的候选树取得对应证据。工作流或实现代码出现普通错误时修正并重验，GitHub 平台或运行器异常则记录当次编号（若已分配）、失败原因、真实结果和已覆盖的步骤。
- GitHub 失败时可按治理库第 19 篇，在现有授权覆盖且与目标系统/架构匹配的本机环境补验对应项目。Linux/macOS Barn 实测仅计入各自系统的覆盖。Windows 默认解决方案须由实际 Windows CI 或获准的等价 Windows 节点验证同一候选及相同 restore、Release build、test 步骤。等价 Windows 节点全绿可记为该候选的 Windows 默认解决方案通过，GitHub 工作流接单与结果仍按真实记录独立列示。缺少 Windows 实测、工作流未实际接单或个别步骤未执行时，对应项目分别标记待验。每项结果以其实际产物为据，包括本地五 DLL 对照和三个 10 TRX。后备复验沿用已有设施。 [Barn 项目采用指南](https://git.hangjiadianzi.com/infra/git-forgejo/src/branch/main/docs/19-Barn能力发现与项目采用.md)
- 主仓 `.github/workflows/verify-r0.yml` 在 `main` push 且相关路径变动时运行，框架 gitlink 路径变化在触发条件内。其 `python3 eng/verify.py --profile r0` 固定运行 R0 历史源码，输出可独立反映 R0 复验状态。R1 采用本轮候选证据，复用已有 R0 历史证据时无需额外触发完整复跑。

## Risks / Trade-offs

- TFM 条件引用会引入两个解析图。以独立工件、实际资产及运行配置消除混用，并在候选报告中逐项记录版本和 API 差异。
- Razor 旧注册和 EF 10 查询内部接口有维护成本。仅在已有服务组合与正常行为范围内适配。若要求扩大到外部项目、改变未列出的公共契约、引入新的第三方包或承诺其他 Provider/平台，先评估影响并取得范围决定。
- 9 的兼容目标为同仓项目过渡服务。与其他 SDK、NuGet 消费、生产部署或未实测 Provider 有关的结果留给相应阶段。

## Migration Plan

1. 验证输入对象、证据及工作树边界后，在框架候选中完成项目、依赖、最小适配和 Windows 入口变更。候选失败时修正并以新候选树重验受影响证据，保存失败记录。必要时只回退本轮候选改动回 `d08617b`，保留独立改动和已接受的查询过滤补丁。本轮没有数据库迁移。
2. 完成本地证据并核对候选身份。按上述方式核对 Windows 默认解结果和 GitHub CI 状态后，若另获 Git 交付授权，先交付实测框架提交，确认该对象可从 `.gitmodules` 仓库取得，再提交主仓 gitlink，回读主仓提交树与子仓对象。交付后若需回退，另获授权并用可追溯的 revert 恢复框架和主仓组合。源码比对、真实 CI、Git 交付和运行时支持各有独立证据。
3. 在主仓候选记录列明实测结果、未执行项和 R2 输入。R2 以通过验收的精确源码树、五 DLL/API 与依赖闭包、测试证据和已审查差异为前置，另行确定包目标、版本与内部依赖映射，再用实际候选包验证干净消费者。
