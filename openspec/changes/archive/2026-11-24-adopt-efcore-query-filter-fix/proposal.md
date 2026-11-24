# 在 .NET 9 维护线上吸收 EF Core 查询过滤修复

## Why

R0 已为上游 `v10.5.1` 的五个后端包建立对照，其中 EF Core 的 SQLite 套件有 58 项通过。上游在该标签之后合入了涉及查询过滤的 #7219。先在相同运行时、依赖和 Provider 上核实并吸收修复，能给 .NET 10 迁移提供经过验证的行为起点。[R0 基线](../../../../docs/maintenance/release-baseline.json) · [上游 PR #7219](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7219)

## What Changes

- 在 `aspnetboilerplate` 子模块核对上游修复与维护线的等价性，补齐缺失的实现及回归覆盖，保留上游来源。
- 普通查询遵守当前工作单元的租户及软删除过滤设置，包括通过 `ValueConverter` 存储 `IsDeleted` 的实体。默认配置继续支持带过滤的同步和异步显式编译查询。
- 启用 `UseAbpQueryCompiler` 后，嵌套显式编译查询独立检查自身所需的过滤上下文。内置租户或软删除过滤器、调用 `GetRequiredContext()` 的自定义过滤器缺少该上下文时抛出 `AbpException`。
- 在升级说明中记录服务替换的兼容边界。启用 ABP 查询选项扩展并通过 `ReplaceService` 替换 `IDatabase` 或 `ICompiledQueryCacheKeyGenerator` 时，初始化 DbContext 会抛出 `AbpException`。
- 将候选的查询行为、依赖和公共 API 与 R0 比较，把补丁结论和适用范围写入主仓。该结论作为 R1 后续运行时迁移的输入。

## Capabilities

### New Capabilities

- `efcore-query-filters`：规定使用经典 ABP 的 EF Core 消费者在普通查询和编译查询中应看到的数据范围。

### Modified Capabilities

## Impact

运行时代码涉及 `Abp.EntityFrameworkCore`。直接验收消费者是 `Abp.EntityFrameworkCore.Tests`，主仓复用 R0 的五包清单和三套回归。候选目标为 `net9.0`、EF Core 9.0.18 和 SQLite；上游另有测试专用 InMemory 依赖。包发行、模板、Angular、AutoMapper 和其他数据库的消费验证按维护路线进入后续变更。
