# R1 首项补丁：EF Core 查询过滤

## 固定来源

| 项目 | 核对结果 |
| --- | --- |
| 主仓 `main` | `92a31c2974edcfccb1c00817abeb93a23b16c059` |
| 主仓 gitlink 与框架 `dev` 检出 | 均为 `6c4580c5e7ea41154696c071a53fd200059a768b`，对应 R0 的 `v10.5.1` 对照 |
| 上游 #7219 | 基底及合并第一父提交为 `b01027b37d2fcd69b754335f73047ce4f2ffa8c0`，合并提交为 `21f57d282f542aa4221fc5cd5a4ac76346d8f5c7` |
| 上游补丁作者 | maliming，提交 `84eff20013a694f9ed3f6f0ddbb9fb87f620b597` |

上游 PR 基底是框架 R0 的第二父提交。对比两棵 Git 树，差异仅在 `doc/WebSite/Zero/Identity-Server-vNext.md`。R0 已有查询选项扩展、查询提供程序和缓存键装饰，以及显式编译缺少上下文时的保护。#7219 新增关系型 `IDatabase` 装饰和与查询绑定的编译授权，校验服务替换冲突，使解析器按开关注册扩展，并修正软删除列值映射。候选采用上游八个运行时文件和自定义过滤器文档，保留既有回归名称，按上游的新异常消息调整断言，并用本地验收覆盖新增行为。[上游 PR #7219](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7219) · [R0 基线](release-baseline.json)

## 升级时的查询配置

- 默认 `UseAbpQueryCompiler = false`。由框架解析的 DbContext 沿用 EF Core 的参数化过滤，普通 LINQ、`EF.CompileQuery` 和 `EF.CompileAsyncQuery` 都可用于带租户及软删除过滤的查询。
- 启用此选项后，依赖 DbContext 的内置过滤器和通过 `GetRequiredContext()` 读取 DbContext 的自定义过滤器，在缺少该次编译所需上下文时抛出 `AbpException`。这类查询可改用普通 LINQ，也可将该选项设为 `false`。自定义 `HasTranslation` 回调使用 `AbpEfCoreCurrentDbContext.GetRequiredContext()` 取得上下文。使用原 `Context` 属性的自定义过滤器需要逐个核对取值和异常处理。
- `AbpDbContextOptionsExtension` 应在数据库 Provider 之后注册。自建 EF Core 内部服务提供程序时，在 Provider 的服务之后调用 `new AbpDbContextOptionsExtension().ApplyServices(services)`。启用扩展时，使用 `ReplaceService` 替换 `IDatabase` 或 `ICompiledQueryCacheKeyGenerator` 会在 DbContext 初始化时抛出 `AbpException`。应用可移除冲突的替换，或关闭查询编译选项并移除手工注册的扩展。[上游使用说明](https://github.com/aspnetboilerplate/aspnetboilerplate/blob/21f57d282f542aa4221fc5cd5a4ac76346d8f5c7/doc/WebSite/Articles/How-To/add-custom-data-filter-ef-core.md)

## 候选与验证输入

2026-11-24 在 macOS 27.2.1 ARM64（`26B131`）执行。SDK 为 `9.0.306`，测试使用 .NET 和 ASP.NET Core `9.0.10`、VSTest `17.14.1` 与 xUnit。EF Core 关系型查询使用 EF Core SQLite 和 Microsoft.Data.Sqlite `9.0.18`，连接为 `Data Source=:memory:`。候选基础为上表的框架 R0，完整候选树（含新增源码）为 `24c938b8d020469537cf69e794478df6436eb28d`。相对该基础的 `git diff --cached --full-index --binary` SHA-256 为 `db331974895c01f8a149d56b8ed74a80213c48b0430a532cf65ed03d0bf21190`，树和补丁由独立 Git 索引生成。相对首轮候选 `b54a61652c3fbcf4a33249e9a204d83a75711c96`，第二轮仅在 `CompiledQueryFilter_Tests.cs` 补充 SQLite 同步与异步显式编译用例。

在框架目录中，以五个清单项目及三套回归项目为入口生成临时 `R1.sln`。首次还原用空的独立 NuGet 包目录，配置中只启用 `nuget.org`。第二轮沿用独立包目录，在新的 `ArtifactsPath` 还原并构建，三套回归均使用该轮构建产物。其中 `evidence` 指向本地证据目录中的 `revision-2/`，`suite` 依次为 `Abp.Tests`、`Abp.AspNetCore.Tests` 和 `Abp.EntityFrameworkCore.Tests`。

```sh
dotnet restore "$evidence/../R1.sln" --configfile "$evidence/../NuGet.Config" \
  --no-http-cache --force -p:Configuration=Release -p:ArtifactsPath="$evidence/artifacts" --disable-build-servers
dotnet build "$evidence/../R1.sln" --configuration Release --no-restore \
  -p:ArtifactsPath="$evidence/artifacts" --disable-build-servers
dotnet test "test/$suite/$suite.csproj" --configuration Release --no-build --no-restore \
  -p:ArtifactsPath="$evidence/artifacts" --disable-build-servers \
  --logger "trx;LogFileName=$suite.trx" --results-directory "$evidence/trx"
```

用 R0 的 `inventory.py` 比较 11 项目、11 个 `net9.0` 目标的实际依赖图和包内容哈希。适配脚本只调整了 `project.assets.json` 的读取路径。两轮候选的实际还原清单相同。与 R0 的唯一差异是 `Abp.EntityFrameworkCore.Tests` 直接引入 `Microsoft.EntityFrameworkCore.InMemory 9.0.18`，新增传递依赖为零。五个候选项目的包标识、包版本、程序集名、根命名空间及项目引用与 R0 一致，构建产出的程序集身份和资源清单也一致。本轮对每个新 DLL 做了两次 API 提取，单个 DLL 的两次提取逐字节一致，两轮的程序集身份、API 和资源清单一致。构建记录包含已有的 `NU1504` 和过时 API 警告。

API 增量限于 `Abp.EntityFrameworkCore`，既有可见成员没有移除或签名变更。

| 类型 | 可见 API 增量 |
| --- | --- |
| `AbpEfCoreCurrentDbContext` | 公开虚方法 `GetRequiredContext()` |
| `AbpEfCoreDatabase` | 公开 `IDatabase` 实现。含构造函数、`SaveChanges`、`SaveChangesAsync`、`CompileQuery<TResult>`、`CompileQueryExpression<TResult>`，以及三项受保护属性 `InnerDatabase`、`AbpEfCoreCurrentDbContext` 和 `CurrentDbContext` |
| `AbpEntityQueryProvider` | 受保护虚方法 `CheckQueryServices()` |
| `DefaultDbContextResolver` | 受保护虚方法 `UseAbpQueryCompiler()` |

## 回归结果

| 套件 | 通过 | 失败 | 跳过 | 相对 R0 新增通过 |
| --- | ---: | ---: | ---: | ---: |
| `Abp.Tests` | 1105 | 0 | 2 | 0 |
| `Abp.AspNetCore.Tests` | 150 | 0 | 0 | 0 |
| `Abp.EntityFrameworkCore.Tests` | 80 | 0 | 0 | 22 |

按 TRX 测试名和结果逐项核对。R0 的两项跳过仍为 `Castle_Should_Register_Unicode_Names_In_Conventions` 和 `Test_GetAllStrings`。核心套件发现阶段的 42 个重复 ID 与 R0 一致，VSTest 报告的 1107 项不包含这些重复条目。三套测试均以退出码 0 完成。

下表用例均来自 `Abp.EntityFrameworkCore.Tests.trx`，名称省略 `Abp.EntityFrameworkCore.Tests.Tests` 命名空间前缀。八个场景涉及的用例均通过。

| 场景 | 用例 | 执行边界 |
| --- | --- | --- |
| 租户与软删除过滤，含缓存重用 | `CompiledQueryCache_WithAbpQueryCompiler_Tests.Should_Apply_Filters_Correctly_When_Queries_Run_For_Different_Tenants_And_Filter_States` 和同类的 `Should_Compile_MayHaveTenant_Query_Once_For_Different_Tenants` | SQLite 与工作单元 |
| `ValueConverter` 软删除 | `SoftDeleteValueConverter_WithAbpQueryCompiler_Tests.Should_Apply_SoftDelete_Filter_To_Converted_Column`，`SoftDeleteValueConverter_WithoutAbpQueryCompiler_Tests.Should_Apply_SoftDelete_Filter_To_Converted_Column` | SQLite 存储值为 5、5、9，过滤开启返回 ID 10、20，关闭后返回 ID 10、20、30 |
| 默认查询选项 | `CompiledQueryFilter_WithoutAbpQueryCompiler_Tests.Should_Apply_Filters_With_Default_Configuration` | SQLite，普通、同步与异步显式编译查询返回同一活动记录 |
| 显式编译查询缺少内置过滤上下文 | `CompiledQueryFilter_WithAbpQueryCompiler_Tests` 的 `Should_Not_Run_Compiled_Query_Without_SoftDelete_Filter`、`Should_Not_Run_Compiled_Query_Without_MayHaveTenant_Filter`、`Should_Not_Run_Compiled_Query_Without_MustHaveTenant_Filter` 和 `Should_Not_Run_Compiled_Async_Query_Without_Filters` | SQLite，调用抛出 `AbpException` |
| 嵌套编译上下文隔离 | `CompiledQueryFilter_WithAbpQueryCompiler_Tests.Should_Reject_Sqlite_Compiled_Query_Within_Authorized_Outer_Scope`、`CompiledQueryFilter_WithAbpQueryCompiler_Tests.Should_Reject_Sqlite_Compiled_Async_Query_Within_Authorized_Outer_Scope` | 用修复引入的框架作用域和实际缓存键生成器建立外层状态。内层分别经过真实 SQLite 的 `EF.CompileQuery` 和 `EF.CompileAsyncQuery`，过滤翻译抛出 `AbpException`，枚举未取得记录。异常前后外层上下文均可用，作用域退出后的普通 SQLite 查询仍返回预期记录 |
| 自定义过滤调用 `GetRequiredContext()` | `CompiledQueryFilter_WithAbpQueryCompiler_Tests.Should_Require_Context_For_Custom_Filter_Translation` | SQLite，普通查询只返回本组织记录，同步与异步显式编译调用抛出 `AbpException` |
| 实体天然无需上下文过滤 | `CompiledQueryFilter_WithAbpQueryCompiler_Tests.Should_Run_Compiled_Queries_Without_A_Configured_Filter` | SQLite，启用选项时同步及异步显式编译查询均按条件返回记录 |
| `ReplaceService` 服务冲突 | `QueryOptionsExtension_Tests.Should_Reject_Database_Replacement_When_Extension_Is_Enabled`、`QueryOptionsExtension_Tests.Should_Reject_Cache_Key_Replacement_When_Extension_Is_Enabled` | SQLite 配置下的 DbContext 初始化，抛出含 `ReplaceService` 的 `AbpException` |

嵌套用例的外层证据覆盖框架的查询和编译作用域，内层证据覆盖 SQLite 的真实显式编译。保留两个 `QueryCompilationScope_Tests.Should_Require_Independent_Filter_Context_For_Nested_Compilation` 组件用例，以 Provider 替身验证装饰器的上下文隔离和恢复。

显式关闭选项的 SQLite 用例 `CompiledQueryFilter_WithExplicitlyDisabledCompiler_Tests.Should_Keep_Custom_Database_And_Apply_Filters_When_Compiler_Is_Disabled` 验证替换的数据库服务仍生效。测试专用 Provider 的 `QueryOptionsExtension_Tests.Should_Keep_InMemory_Provider_Database_Service` 验证 InMemory 保留原数据库服务及创建、删除行为。新增的其余用例验证服务装饰的注册、生命周期和释放。

首轮两次定向构建分别遇到测试夹具引用内部类型的 `CS0246` 和缺少扩展命名空间的 `CS1061`。修正后首轮定向回归通过 34 项。第二轮重新构建后，两项 SQLite 用例及两项组件用例的定向回归通过 4 项，随后完成三套完整回归。

原始证据位于主仓 `.git/r1-query-filter-evidence/`，其中 `upstream-objects.log` 保存上游对象核对，`revision-2/` 保存最终候选补丁、构建和测试命令日志、11 份资产文件、五个 DLL 及其摘要、`api/` 中的逐项对照、`trx/` 和 `trx-comparison.json`。本记录对应已完成本机构建和回归的 .NET 9 源码候选。Git 交付、运行时迁移、其他数据库及消费包验证按维护路线开展。
