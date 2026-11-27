# 用公开 R4 与 R5 对照经典 ABP 的映射业务

## Why

在主仓 `3b0b21c`，应用维护者已经能用公开包完成同库回退，并查回两版各自写入的用户。按键更新能否保留原对象、`ProjectTo` 会向数据库发送什么查询，仍要查阅 `net9.0` 本地候选的专项报告。为采用公开 R5 的应用提供同一 `net10.0` 环境下可重跑的 R4 对照，可以把包切换的影响与 Provider、模板、运行时变化分别判断。[公开回退范围](../../../../docs/maintenance/r5-automapper-template.md#独立消费者验收) · [候选专项结果](../2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md#消费结果)

## What Changes

- 在主仓复用已有业务探针，从仅含 nuget.org 的空缓存分别构建、运行 R4 与 R5 消费者，并核对实际加载的映射程序集。
- 独立消费者使用固定模板的 DTO、实体和 Profile，通过 `IObjectMapper` 更新已有用户、按键映射集合，并对 SQLite 查询执行 `ProjectTo<UserDto>`。逐项给出两版的预期和实测。一侧业务断言失败时保留已取得的证据，另一侧继续独立执行。
- 将读者可复跑的命令、证据和适用范围接入 AutoMapper 兼容指南。输入对不上或业务有偏差时保留失败项，供维护者决定是否另立修复。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `automapper-package-consumption` 增加使用两个公开发行组合，在相同环境独立比对映射业务的验收要求。

## Impact

验收使用 `aspnetboilerplate`、`AutoMapper`、`AutoMapper.Collection` 已发行的包和 `module-zero-core-template@2e953687` 的 DTO、实体及映射配置。拟验范围为 macOS ARM64、SDK `10.0.404`、`net10.0` 与 EF Core SQLite `10.0.15`。交付在主仓的验证入口和兼容文档。完整模板的 SQL Server、Angular、迁移与恢复结论沿用对应实测记录。
