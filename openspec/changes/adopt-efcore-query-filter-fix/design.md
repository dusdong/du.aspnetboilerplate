# R1 首项补丁的来源与验收设计

## Context

| 对照项 | 固定输入 |
| --- | --- |
| 主仓 R0 归档 | `92a31c2974edcfccb1c00817abeb93a23b16c059` |
| 框架 R0 | `6c4580c5e7ea41154696c071a53fd200059a768b`，上游 `v10.5.1` |
| 上游 #7219 | 目标分支 `dev`，PR 基底 `b01027b37d2fcd69b754335f73047ce4f2ffa8c0`，合并提交 `21f57d282f542aa4221fc5cd5a4ac76346d8f5c7` |
| 执行环境对照 | R0 的 macOS ARM64、SDK 9.0.306、EF Core 与 SQLite 9.0.18 |

本地 Git 对象显示，PR 基底是 R0 框架提交的第二父提交，两棵树仅有一处网站文档差异。上游 PR 涉及 EF Core 运行时代码、测试项目及自定义过滤器文档；这使补丁范围可独立于整条上游开发分支核对。[上游 PR](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7219) · [R0 复验手册](../../../docs/maintenance/baseline-evidence/README.md)

## Goals / Non-Goals

首个候选只回答一个问题：在现有 EF Core 9 消费环境中能否交付上游约定的结果与异常行为。沿用 `Abp.EntityFrameworkCore` 包、程序集和 `Abp` 根命名空间，以及 `Abp.EntityFramework.Common → Abp` 内部依赖链。运行时迁移、包改名与消费者升级各自有独立的验收输入。

## Decisions

1. **按固定上游差异吸收。** 比较上游合并提交相对其 PR 基底的变更与本地候选源码。已有等价实现时保留其出处和证据；存在缺口时移植相关运行时代码、配套测试与使用说明，记录原作者、上游提交和本地适配。直接将子模块推进到上游分支头会引入无关改动。
2. **在候选上区分默认路径与启用扩展后的行为。** 默认的 `UseAbpQueryCompiler = false` 沿用 R0 的普通查询、同步和异步显式编译查询结果。启用后，嵌套显式编译查询依据自身的过滤上下文决定结果。单列候选上的嵌套回归用例及其 TRX 结果，确认缺少所需上下文时抛出 `AbpException`。天然无需上下文过滤的查询继续正常返回。[上游过滤器使用说明](https://github.com/aspnetboilerplate/aspnetboilerplate/blob/21f57d282f542aa4221fc5cd5a4ac76346d8f5c7/doc/WebSite/Articles/How-To/add-custom-data-filter-ef-core.md)
3. **分别核对测试依赖与运行时依赖。** 关系型结果由现有 SQLite 套件验证。保留上游新增回归需要的 `Microsoft.EntityFrameworkCore.InMemory 9.0.18` 时，将其限定在测试项目；检查实际还原图，列出它新增的依赖，确认首批五包的运行时图未受影响。[上游测试项目](https://github.com/aspnetboilerplate/aspnetboilerplate/blob/21f57d282f542aa4221fc5cd5a4ac76346d8f5c7/test/Abp.EntityFrameworkCore.Tests/Abp.EntityFrameworkCore.Tests.csproj)
4. **把验收绑定到候选。** R0 的 `reproduce.zsh` 内置历史提交。实施时从候选源码构建、还原和测试，复用 R0 的 API 提取和还原图比较工具。候选尚无提交时记录基础 SHA 和完整补丁的内容摘要；交付到 Git 时再核对已提交的源码树与验收输入一致。对 API 逐项说明差异，重点核实既有公开调用方式及程序集身份。[基线工具](../../../docs/maintenance/baseline-tools/) · [五包记录](../../../docs/maintenance/release-baseline.json)

## Risks / Trade-offs

- 只运行新用例可能遗漏默认查询路径的变化。在候选上运行完整 EF Core 套件，再与同次构建的核心、ASP.NET Core 套件一起核对。R0 原有的两项跳过和重复发现记录按原口径列明，新增或缺失用例按名称和结果核对。
- SQLite 软删除回归使用 `ValueConverter`，将活动与已删除状态存成两个不同的整数，且活动值选用非零值。同一查询断言实际返回的记录标识与预期活动集合一致，使错误的列值映射能被检出。
- 移植后若出现未解释的公开 API 变化、运行时依赖差异或已有用例退化，保留候选与失败记录，先修正本包。后续 .NET 10 验收使用本包最终通过的行为合同，并独立核对 EF Core 10 对该合同的支持。

## Migration Plan

自定义过滤器的 `HasTranslation` 示例从直接读取 `AbpEfCoreCurrentDbContext.Context` 迁移到 `GetRequiredContext()`。以更新后的示例验证上下文缺失时的 `AbpException`。使用旧访问方式的自定义过滤器须单独核实其行为。

R0 的选项扩展未校验服务替换。候选启用 `AbpDbContextOptionsExtension` 时，分别核对 `ReplaceService` 替换 `IDatabase` 和 `ICompiledQueryCacheKeyGenerator` 两种配置，均应在 DbContext 初始化时收到指出冲突的 `AbpException`。将该兼容性变化写入使用说明，供已自定义 EF Core 服务的应用在升级前核对配置。[上游选项校验](https://github.com/aspnetboilerplate/aspnetboilerplate/blob/21f57d282f542aa4221fc5cd5a4ac76346d8f5c7/src/Abp.EntityFrameworkCore/EntityFrameworkCore/AbpDbContextOptionsExtension.cs)

本阶段交付源码维护候选。主仓在维护路线的 R1 段链接补丁结论，登记固定来源、候选身份、实际 Provider、测试结果及差异；R0 清单继续作为历史对照。子模块提交可获取且内容与验收一致后，主仓才可记录对应 gitlink。候选验收失败时，维护线继续指向原有已知提交。此包不涉及生产数据库迁移。
