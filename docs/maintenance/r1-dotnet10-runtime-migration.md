# R1 核心源码迁移至 .NET 10

2026-11-24 在 macOS 27.2.1 ARM64（`26B131`）完成 Release 本地验收。三套 .NET 10 回归合计 **1341 通过、0 失败、2 项既有跳过**。六个 .NET 9 调用方按项目默认目标构建成功，适用的测试全部通过。相同源码树在本机 UTM Windows ARM64 与 GitHub 托管 Windows x64 均通过默认解决方案验收，两边各 **2805 通过、0 失败、9 项既有跳过**。2026-11-25，原样通过验收的源码树已合入框架 `dev` 并由主仓 gitlink 固定。

## 候选输入

| 项目 | 记录 |
| --- | --- |
| 主仓基线与分支 | `5cea65ca538623e0a1049a872a9ea52a1c1da464`，`main` |
| 框架基线与分支 | `d08617b51bb7c7e5d0bea942e7e10b2677240c35`，`dev` |
| 框架基线树 | `24c938b8d020469537cf69e794478df6436eb28d` |
| 草稿 PR 候选提交 | `7a47504c17b32f0111473c97dd2f8377fe06171b`，`codex/r1-dotnet10-windows` |
| 最终实测框架树 | `097820f84c1c20d09e5158c4a2723ed530098266`，包含 Windows 工作流及新增测试文件 |
| 相对框架基线的完整补丁 SHA-256 | `8ad41b01a7e79efc149a6a328643b1c4c6320f31ee116844b84dbfd3203fa9d1`，由独立索引执行 `git diff --cached --full-index --binary` |
| SDK、MSBuild、NuGet、VSTest | `10.0.404`、`18.9.15+2ab285486`、`7.9.0-rc.3019`、`18.7.1-hotfix-26529-119`（ARM64） |
| 测试运行器 | Microsoft.NET.Test.Sdk/TestHost `18.8.1`，xUnit `2.9.3`，VSTest 适配器 `3.1.5` |
| 实际共享运行时 | 三套核心测试加载 `Microsoft.NETCore.App 10.0.15`，ASP.NET Core 套件另加载 `Microsoft.AspNetCore.App 10.0.15`。三套兼容测试加载 `Microsoft.NETCore.App 9.0.23`，Module Zero 套件另加载 `Microsoft.AspNetCore.App 9.0.23` |

本节的主仓与框架基线仅用于测试对照。测试对照使用该基线的已接受 R1 证据 `.git/r1-query-filter-evidence-2026-11-24.tar.gz` 中的 `revision-2/`。历史 R0 使用固定框架 `6c4580c5e7ea41154696c071a53fd200059a768b`，本轮校验现有输入和原始证据的 SHA-256。[R1 首项补丁验收记录](r1-efcore-query-filter.md) · [R0 基线](release-baseline.json)

## 还原与程序集

核心解用 11 个入口还原出 20 个无 RID 目标，其中 11 个为 `net10.0`、9 个为 `net9.0`。兼容解由五个核心项目与六个原调用方还原出 26 个 `net9.0` 项目的闭包。两条路径使用独立包缓存和工件目录，包来源为 nuget.org。第一包在各自空缓存上完成两次还原。加入 Razor 测试资源后，最终树再次还原并执行 [R1 清单入口](../../eng/r1_restore_inventory.py)，两份输出各自与第一包逐字节相同。清单含实际项目引用、版本、包路径、来源与内容哈希。

- .NET 10 的 EF Core、Relational、SQLite、InMemory、Microsoft.Data.Sqlite、ASP.NET Core TestHost、Mvc.NewtonsoftJson 和 Razor.RuntimeCompilation 使用 `10.0.15`。私有 Web CodeGeneration Design 为 `10.0.3`，其 EF Core Design 通过条件引用统一为 `10.0.15`。关系型回归使用内存 SQLite，候选测试产物中的 `SQLitePCLRaw.lib.e_sqlite3 2.1.13` 为 SQLite `3.53.3`。InMemory 用于验证非关系型服务注册。
- .NET 9 的运行路径保留 EF Core 与 SQLite Provider `9.0.18`。ASP.NET Core Demo 使用 `9.0.18` 的 MVC JSON 和 Razor 包。`Abp` 的私有代码生成链仍使用 EF Core `9.0.12`。`SQLitePCLRaw.lib.e_sqlite3 2.1.10` 对应 SQLite `3.46.1`。SDK 默认包裁剪使候选保留的九个 .NET 9 目标共少 315 条传递包记录，关闭裁剪的对照与历史 R1 清单一致。
- 还原保留 SourceLink 重复声明 `NU1504` 与部分可裁剪直接引用提示 `NU1510`。ASP.NET Core 的 Razor 运行时编译 `ASPDEPR003` 在原注册处和定向用例局部抑制。框架构建保留 `ASPDEPR006`，测试基座保留 `ASPDEPR004`、`ASPDEPR008`，对应现有 MVC 和 WebHost/TestServer 入口。框架 .NET 10 Release 构建为零错误。

在最终树取得 11 个 `net10.0` Release 工件。对 `Abp`、`Abp.AspNetCore`、`Abp.EntityFramework.Common`、`Abp.EntityFrameworkCore`、`Abp.Web.Common` 各核对两个目标的 MSBuild 属性、DLL SHA-256、PE 程序集身份、可见类型和成员、嵌入资源名。十个 DLL 各提取两次，每个 DLL 的两份清单逐字节相同。五个程序集版本均为 `10.5.1.0`，PackageVersion 为 `10.5.1`。程序集名、PackageId、根命名空间与历史相同，其中 `Abp.EntityFramework.Common` 的根命名空间仍为 `Abp.EntityFramework`。

| 目标 | 公共及受保护 API 与嵌入资源对照 |
| --- | --- |
| `net9.0` | 五个 DLL 与已接受 R1 清单逐项一致 |
| `net10.0` | 五个 DLL 的类型全名、程序集身份与嵌入资源名一致。可见成员签名差异限于 `Abp.EntityFrameworkCore` 的三处方法 |

`net10.0` 的 `AbpEfCoreDatabase.CompileQueryExpression<TResult>` 跟随 EF Core 10 使用两参数签名。覆写该方法的调用方需要适配新签名。`EfCoreRepositoryExtensions.BatchUpdateAsync` 的两个重载将更新参数改为 `Action<UpdateSettersBuilder<TEntity>>`。常见的内联 `setters => setters.SetProperty(...)` 形态可继续使用，显式声明的旧表达式类型或按旧签名绑定的方法组需要迁移。谓词、ABP 过滤逻辑和行数语义保持一致。项目从 `net9.0` 构建时使用原签名。[变更设计](../../openspec/changes/archive/2026-11-25-migrate-r1-core-to-dotnet10/design.md)

## 本地行为结果

统计顺序为通过、失败、跳过。以 TRX 的测试全名、用例定义和结果明细核对，多参数用例包含完整显示参数。

| `net10.0` 测试工程 | 历史 R1 | 本次候选 | 本次新增 |
| --- | ---: | ---: | ---: |
| `Abp.Tests` | 1105/0/2 | 1105/0/2 | 0 |
| `Abp.AspNetCore.Tests` | 150/0/0 | 151/0/0 | 1 |
| `Abp.EntityFrameworkCore.Tests` | 80/0/0 | 85/0/0 | 5 |

原 R1 的 1335 项通过及 2 项跳过逐名一致，22 项 EF 查询过滤增量均通过。核心套件发现阶段的 42 个重复 ID 与已接受 R1 完全相同。TRX 明细有六组共享 TRX ID 的用例，组内测试全名互异且分组与历史一致。两项跳过的 `NotExecuted` 明细及原因与历史一致，VSTest 汇总仍记 `notExecuted=0`。

- `Abp.Tests.Dependency.Unicode_Naming_Tests.Castle_Should_Register_Unicode_Names_In_Conventions` 因 Castle Windsor 支持限制跳过。
- `Abp.Tests.Localization.ResourceFileLocalizationSource_Tests.Test_GetAllStrings` 因待上游处理资源本地化问题 #1995 跳过。[上游问题](https://github.com/aspnetboilerplate/aspnetboilerplate/issues/1995)

八个 [历史过滤场景](r1-efcore-query-filter.md#回归结果) 均由本次同名用例复验，包括默认配置、上下文授权、缓存隔离、软删除转换、显式编译、服务装饰及替换冲突。新用例如下。

| 用例 | 实际验证 |
| --- | --- |
| `QueryCompilationScope_Tests.Should_Restore_Context_After_Compiling_Query_Expression`，四组同步/异步与成功/异常组合 | 直接调用两参数重载，确认传入表达式和标志、授权 DbContext 可见、嵌套未授权查询失败、返回表达式或异常原样传播，以及恢复不同的先前 DbContext |
| `Repository_Filtering_Tests.Should_Update_Only_Matching_Active_Posts_In_Current_Tenant` | SQLite 实际更新一行，通过四行回读确认调用方谓词、软删除和租户限制 |
| `EmbeddedRazorView_Tests.Should_Read_Embedded_View_From_Registered_Razor_File_Provider` | 从 TestServer 的选项解析实际注册的提供程序，读取程序集嵌入的 `.cshtml` 内容 |

六个原调用方均使用项目默认目标执行 Release 构建。项目资产、`.deps.json`、`.runtimeconfig.json` 和采用的本地框架 DLL 摘要用于复核目标与引用。

| 项目 | `net9.0` Release | 测试 |
| --- | --- | --- |
| `Abp.EntityFramework` | 成功 | 构建验证 |
| `Abp.ZeroCore.EntityFrameworkCore` | 成功 | 构建验证 |
| `AbpAspNetCoreDemo` | 成功 | 构建验证 |
| `Abp.Web.Common.Tests` | 成功 | 全套 15/0/0 |
| `Abp.EntityFrameworkCore.Dapper.Tests` | 成功 | 全套 18/0/0 |
| `Abp.ZeroCore.Tests` | 成功 | 定向 4/0/0 |

Module Zero 的 TRX 按类全名 `Abp.Zero.EFPlus.AbpEntityFrameworkCoreBulkRepositoryExtensions_Tests` 核对，以下四项均为 `Passed`。

- `Should_Update_All_Tenant_Roles_When_Using_BatchUpdate`
- `Should_Update_Filtered_Entities_Using_BatchUpdate`
- `Should_Use_MayHaveTenant_Filter_When_Updating_Entities_Using_BatchUpdate`
- `Should_Update_All_Roles_When_MayHaveTenant_Filter_Is_Disabled_When_Using_BatchUpdate`

## Windows、GitHub 与交付

| 验收项 | 当前结果 |
| --- | --- |
| Windows PR 工作流定义 | 已对齐并通过 actionlint `1.7.12`、PowerShell 语法检查及 Windows x64 SDK 发行元数据核对。入口为 `aspnetboilerplate/.github/workflows/build-and-test.yml` |
| GitHub Windows x64 默认 `Abp.sln` | 61 个项目全部还原。Release 构建通过，0 错误。五个核心项目的两种目标均取得 DLL 与 SHA-256。全解测试通过，详见下表 |
| 本机 UTM Windows ARM64 默认 `Abp.sln` | 独立还原 61 个项目，Release 构建与十份双目标 DLL 查验通过。全解测试及同工件的全解重跑均返回 0 |
| GitHub PR 工作流 | 框架 PR #1 在草稿阶段触发 run `45419764351`、attempt `1`、job `138535746526`，结论 `success`。 [框架 PR](https://github.com/dusdong/aspnetboilerplate/pull/1) · [实际运行](https://github.com/dusdong/aspnetboilerplate/actions/runs/45419764351/attempts/1) |
| Git 交付 | 框架已合入 `dev`，主仓已记录实际合并提交 |

GitHub 托管运行器 `windows-latest` 实际使用 Windows Server 2025 `10.0.26100`，镜像 `windows-2025-vs2026` `20261116.315.1`，架构 x64、RID `win-x64`。PR head 为上表候选提交，checkout 为 GitHub 生成的合并提交 `db779d809ca4de98052d79bb79ab12678cb82da6`，其树与候选树一致。SDK `10.0.404`、MSBuild `18.9.15+2ab285486`，由 SDK `9.0.321` 提供 .NET 9 共享运行时。`Microsoft.NETCore.App` 和 `Microsoft.AspNetCore.App` 的 `9.0.23`、`10.0.15` 均已核对。xUnit 日志记录 64 位测试进程，分别使用 .NET `9.0.23` 和 `10.0.15`。

本机 `win11-arm64-shared` 为 Windows 11 Pro `10.0.26300`，RID `win-arm64`。以候选 Git 树的 Git 归档 SHA-256 `62602bca42bf1a2e3366f5873e64198c4fcc3b005ea3ab172d5f190fd34ad720` 核对客体输入。客体的 ARM64 SDK `10.0.404` 和 `Microsoft.NETCore.App`、`Microsoft.AspNetCore.App` 的 `9.0.23` 与 `10.0.15` 从 Microsoft 官方归档校验后放入任务私有目录。首轮测试通过，PowerShell 5.1 的类型别名导致进程采样失败。复用同一 Release 工件全量重跑，通过 `IsWow64Process2` 确认 19 个测试进程均为原生 ARM64，其中 `net9.0` 16 个、`net10.0` 3 个。

| 每个 Windows 环境的 TRX 明细 | 通过 | 失败 | 跳过 |
| --- | ---: | ---: | ---: |
| `net9.0`，16 份报告 | 1464 | 0 | 7 |
| `net10.0`，3 份报告 | 1341 | 0 | 2 |
| 合计 | **2805** | **0** | **9** |

两种 Windows 环境的 19 个项目目标的用例全名与结果逐项一致，三套 `net10.0` 同样与 macOS 最终候选一致。`Abp.Tests` 的两项既有跳过分别在两个目标出现，Demo 的五项既有 OData 跳过计入 `net9.0`。`Abp.MailKit.Tests` 在候选与基线均无启用的 `[Fact]`，其 `net9.0` TRX 记录 0 项。其余 18 份 TRX 均有实际运行结果。

本地证据支持核心还原与构建（2.1、2.4）、同仓 9 目标兼容（2.6），以及新运行时的行为回归（2.2、2.3、2.5）。Windows 默认解与 GitHub 运行证据对应 3.2，环境、差异和未执行范围对应 4.1。包消费、打包发布、外部模板和其他数据库 Provider 的运行验收留待相应阶段。[迁移规范](../../openspec/specs/runtime-migration/spec.md) · [实施任务](../../openspec/changes/archive/2026-11-25-migrate-r1-core-to-dotnet10/tasks.md)

## Git 交付

2026-11-25，GitHub PR #1 合入 `dev`，框架合并提交为 `d497cba3d3feec093168697e81adb64ea5544087`。其两个父提交为框架基线 `d08617b51bb7c7e5d0bea942e7e10b2677240c35` 和已验收候选 `7a47504c17b32f0111473c97dd2f8377fe06171b`，树为本报告上表所列的 `097820f84c1c20d09e5158c4a2723ed530098266`。合并提交已从 `.gitmodules` 指定的仓库取回核对。[框架 PR #1](https://github.com/dusdong/aspnetboilerplate/pull/1)

主仓接入提交为 `7f969af7a1e0f75bf1ca4b0a77d296aa7cdd79a2`。在主仓执行 `git ls-tree 7f969af7a1e0f75bf1ca4b0a77d296aa7cdd79a2 aspnetboilerplate`，应读到 `160000 commit d497cba3d3feec093168697e81adb64ea5544087`。该框架提交、依赖图、API 差异和实际测试结果构成 R2 包验收的源码输入。R0 工作流继续使用自己的固定历史框架输入。[主仓接入提交](https://github.com/dusdong/du.aspnetboilerplate/commit/7f969af7a1e0f75bf1ca4b0a77d296aa7cdd79a2) · [OpenSpec 归档](../../openspec/changes/archive/2026-11-25-migrate-r1-core-to-dotnet10/)

## 复验与原始证据

从框架候选根执行。使用两个新的绝对工件目录，按设计的项目清单通过 `dotnet new sln --format sln`、`dotnet sln add` 创建各自的 `R1.sln`。设置 `DOTNET_ROOT` 和 `PATH` 选中指定 SDK，用独立配置仅启用 nuget.org。`round` 分别指向核心和兼容目录，`NUGET_PACKAGES` 指向各自隔离的 `packages/`。

```sh
dotnet restore "$round/R1.sln" --configfile "$R1_NUGET_CONFIG" --no-http-cache --force \
  -p:Configuration=Release -p:ArtifactsPath="$round/artifacts" \
  -p:GeneratePackageOnBuild=false --disable-build-servers
dotnet build "$round/R1.sln" -c Release -f net10.0 --no-restore --no-incremental \
  -p:ArtifactsPath="$round/artifacts" -p:GeneratePackageOnBuild=false --disable-build-servers
dotnet test "test/$suite/$suite.csproj" -c Release -f net10.0 --no-build --no-restore \
  -p:ArtifactsPath="$round/artifacts" -p:GeneratePackageOnBuild=false --disable-build-servers \
  --logger "trx;LogFileName=$suite.trx" --results-directory "$round/trx"
```

核心测试逐个使用上表项目名。兼容构建逐个使用原项目路径，构建与测试均省略 `-f`。Module Zero 按设计附加 `--filter 'FullyQualifiedName~Abp.Zero.EFPlus.AbpEntityFrameworkCoreBulkRepositoryExtensions_Tests&FullyQualifiedName~BatchUpdate'`。从主仓根运行 `eng/r1_restore_inventory.py`，分别传入框架根、工件目录、包缓存、`--scope core` 或 `--scope compat` 和输出路径。用 `dotnet msbuild` 求值 `TargetPath`，以 [API 提取工具](baseline-tools/ApiInventory.csproj) 针对每个实际 DLL 提取两份清单，再调用 `baseline-tools/inventory.py compare-api` 与历史同名清单比较。[完整命令与项目清单](../../openspec/changes/archive/2026-11-25-migrate-r1-core-to-dotnet10/design.md#本地候选取证)

原始证据在验证机主仓 `.git/r1-net10-implementation/package-2/`，需单独取得。此目录中的 `framework-candidate.tree` 与 `framework-candidate.diff` 固定源码输入。`final-v2/core/` 和 `final-v2/compat/` 保存还原与构建日志、实际依赖清单、三份当次核心及三份兼容 TRX、运行时追踪、MSBuild 身份、双次 API 提取与逐项差异。`final-v2/release-outputs.json` 和 `final-v2/trx-comparison.json` 列出实际产物摘要、TRX 全名和逐项结果。`final-v2/` 另存归档后的实际还原图与 22 份 Release DLL，并从归档逐文件回读核对。保留 `run-local.sh`、`api-and-outputs.py` 与 `verify-trx.py` 查看本机精确命令。第一包目录保留历史 R1 输入、空缓存还原及跨 TFM 依赖差异。初次 EF 签名编译失败与工作流静态校验失败保存于第二包目录，最终结果与两轮候选的树和日志可以分别追溯。

Windows 验收沿用框架 `.github/workflows/build-and-test.yml`。从候选源根目录依次执行下列命令，复用同一批 Release 还原、构建和测试产物。用 `dotnet msbuild` 按 `net9.0`、`net10.0` 求值五个核心项目的 `TargetPath`，分别核对 DLL 文件和 SHA-256。

```powershell
dotnet restore Abp.sln -p:Configuration=Release -p:GeneratePackageOnBuild=false
dotnet build Abp.sln -c Release --no-restore -p:GeneratePackageOnBuild=false
dotnet test Abp.sln -c Release --no-build --no-restore -p:GeneratePackageOnBuild=false --logger "trx;LogFilePrefix=results" --verbosity normal
```

Windows 原始证据在验证机主仓 `.git/r1-net10-implementation/package-3/`。GitHub 的 `github-windows-release-1.zip` 与 Actions API 公布的 SHA-256 一致，解包目录 `github-attempt-1/` 包含实际检出及运行时、还原、构建、测试、DLL 摘要和原始 TRX。`github-final-run.json`、`github-final-job.json`、`github-merge-checkout.json`、`github-job-138535746526.log` 和 `github-trx-audit.json` 记录实际接单、结果、树与用例对照。[当次 GitHub 工件](https://github.com/dusdong/aspnetboilerplate/actions/runs/45419764351/artifacts/14933029930)

本机证据归档 `utm-initial.zip` 与 `utm-retest.zip` 对应首轮和重跑。解包目录 `utm-arm64/evidence/` 的 `commands.log`、`assemblies.log`、`dotnet-info.log` 与 `trx/` 保存实际命令、退出码、运行环境、DLL 身份和首轮结果，`utm-arm64-retest/retest/` 另存测试进程架构、重跑日志及 TRX。`guest-run.ps1` 和 `guest-retest.ps1` 保存执行入口，UTM 使用独立 nuget.org 配置与空包缓存。`windows-trx-cross-platform.json` 保存逐项目结果对照。
