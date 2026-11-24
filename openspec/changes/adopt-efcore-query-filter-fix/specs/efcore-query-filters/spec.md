# EF Core 查询过滤

## Purpose

使用经典 ABP 的 EF Core 应用需要按当前工作单元确定可见记录，并能区分受支持的查询与缺少过滤上下文的查询。明确返回结果和异常两类契约，使维护者在修复框架和升级 EF Core 后可以对照同一预期。

## ADDED Requirements

### Requirement: 普通查询遵守当前数据过滤设置

框架 SHALL 在普通 EF Core 查询中根据当前有效的租户与软删除过滤设置返回记录，包括复用已缓存查询计划的情形。

#### Scenario: 租户查询活动记录

- **WHEN** 租户应用在启用租户和软删除过滤的工作单元中查询同时受这两类过滤约束的实体
- **THEN** 返回的集合与该租户符合查询条件的未删除记录集合一致

#### Scenario: 软删除列使用自定义存储值

- **WHEN** SQLite 上的实体通过 `ValueConverter` 将 `IsDeleted` 的真假值映射为自定义列值，应用在启用软删除过滤时查询这些实体
- **THEN** 返回所有符合查询条件的活动记录，并排除已删除记录

#### Scenario: 应用保留默认查询配置

- **WHEN** 应用沿用默认配置（`UseAbpQueryCompiler = false`），在 SQLite 上对受租户和软删除过滤的实体执行普通查询、同步和异步显式编译查询
- **THEN** 三种查询均成功，返回的记录符合当前工作单元的过滤条件，与 R0 的可见记录一致

### Requirement: 显式编译查询的失败行为可预期

启用 `UseAbpQueryCompiler` 后，显式编译查询使用依赖当前 DbContext 的内置租户或软删除过滤器，或使用通过 `AbpEfCoreCurrentDbContext.GetRequiredContext()` 取上下文的自定义过滤器时，框架 SHALL 在所需上下文不可用时抛出 `AbpException`。该契约同时适用于 `EF.CompileQuery` 和 `EF.CompileAsyncQuery`。

#### Scenario: 显式编译查询依赖内置过滤器

- **WHEN** 启用该选项的应用执行显式编译查询，内置租户或软删除过滤器缺少所需的当前 DbContext
- **THEN** 调用方观察到 `AbpException`，且没有返回业务记录

#### Scenario: 嵌套显式编译查询独立校验过滤上下文

- **WHEN** 启用该选项的应用执行依赖内置数据过滤器的嵌套显式编译查询，内层查询缺少自身所需的过滤上下文
- **THEN** 内层查询抛出 `AbpException`，即使外层查询有有效上下文也不会返回业务记录

#### Scenario: 自定义过滤器通过公开接口取得上下文

- **WHEN** 启用该选项的应用执行显式编译查询，自定义过滤器调用 `GetRequiredContext()` 时缺少所需上下文
- **THEN** 调用方观察到 `AbpException`，且没有返回业务记录

#### Scenario: 查询天然无需上下文过滤

- **WHEN** 应用对未配置数据过滤的实体执行原本受支持的显式编译查询
- **THEN** 查询继续返回符合条件的记录

### Requirement: 查询选项扩展报告服务替换冲突

启用 `AbpDbContextOptionsExtension` 时，框架 SHALL 在 DbContext 初始化期间校验应用通过 `ReplaceService` 替换的服务。

#### Scenario: 应用替换查询扩展需要包装的服务

- **WHEN** 已启用该扩展的应用通过 `ReplaceService` 替换 `IDatabase` 或 `ICompiledQueryCacheKeyGenerator`
- **THEN** DbContext 初始化抛出 `AbpException`，异常消息指出冲突来自 `ReplaceService`
