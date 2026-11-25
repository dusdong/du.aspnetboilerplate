# R3 固定模板 net9.0 同目标换包

## Why

主仓 `148bda5` 的原版模板已能从冻结的登录前备份恢复，在 SQL Server、Release Web.Host 和真实 Angular 客户端之间重现同一租户的用户查询。下一步是在固定的 `net9.0`、前端和数据起点上，将此前分别验收的维护包组合到同一个应用中，判断换包是否改变运行行为。[原版运行交接](../../../../docs/maintenance/r3-template-runtime-baseline.md#交接数据恢复点) · [R3 路线](../../../../docs/maintenance/fork-roadmap.md#r3验证升级路径和实际消费者)

## What Changes

- 为模板提交 `2e953687` 提供可重复应用的包引用变更，涵盖 Web.Host 的可达项目和独立 Migrator。安装四个已冻结批次的 11 个 `Du.Abp*` 包及两份维护版映射包，从空 NuGet 缓存还原并完成 Release 构建。
- 核对各项目实际依赖图、输出和 Host 进程加载的程序集。正式换包对照要求 Host 实际加载的 `Microsoft.NETCore.App` 和 `Microsoft.AspNetCore.App` 均与原版一致，为 `9.0.10`。将第三方依赖差异逐项归因，特别是原版 SQL Server Provider 与维护版 EF Core 的 9.0 补丁版本组合。
- 在由原版最终返修备份恢复的新库运行维护版 Migrator 和 Web.Host，复用同一 Angular production 产物、租户、授权账号及搜索词。从 Migrator 执行迁移的 SQL 连接确认目标实例和候选库。浏览器提交登录前及完成业务流程后，核对同一账号在候选库的成功登录记录为 `1 → 2`、对照库为 `1 → 1`，并比较搜索结果。

## Capabilities

### New Capabilities

- `template-maintenance-package-consumption` 规定完整模板安装维护版包的依赖闭包、运行资产归属，以及与原版数据和业务行为的对照。

### Modified Capabilities

## Impact

主仓交付模板引用变更、独立验证入口和迁移说明。模板提供固定的真实应用源码，框架及两个映射子仓提供已验实包。首轮支持结论限定在实际验证的 macOS ARM64 应用进程、.NET 9、SQL Server 与 Angular 组合。通过后才进入 .NET 10 / EF Core 10 运行时升级。升级后回退与公开发行沿用既有排期。[原版构建基线](../../../../docs/maintenance/r3-web-host-baseline.md) · [候选包批次](../../../../docs/maintenance/fork-roadmap.md#r3验证升级路径和实际消费者)
