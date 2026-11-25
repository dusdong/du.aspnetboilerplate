# R3 固定模板原版应用回退

## Why

提交 `d731068` 已验证完整维护版模板升级到 .NET 10 后能继续使用原数据库。该轮 30 条迁移及已核对的业务表结构前后一致，升级后备份另含一条 .NET 10 成功登录记录。消费者仍需知道切回原版应用能否保留这条写入，以及选用升级前恢复点时可以恢复到什么状态。[正式升级结果与恢复点](../../../../docs/maintenance/r3-template-net10-upgrade.md#恢复点与写入边界) · [R3 路线](../../../../docs/maintenance/fork-roadmap.md#r3验证升级路径和实际消费者)

## What Changes

- 以固定免费模板的原版 `net9.0` Release Web.Host、Migrator 和冻结 Angular production 客户端为回退对象，核对原版 NuGet 来源、运行时和实际加载的程序集。
- 从同一次升级的 `after_upgrade`、`before_upgrade` 备份各恢复一个独立测试库。先让原版应用接手升级后的数据，再独立验证恢复升级前备份的路径。在两库中重放同一项租户登录和授权查询。
- 每条路径分别核实 Migrator 的迁移目标、登录实际写入的库和授权查询实际读取的库。按升级报告登记的七个字段比较历史登录行与本轮新增行。
- 登录成功后若查询失败，报告保留首错和两库的写入差异，升级前路径仍可从独立恢复点验收。迁移手册据此说明各路径的适用组合及恢复点之后的写入影响。

## Capabilities

### New Capabilities

- `template-application-rollback` 规定切回原版时如何确认应用身份、验证既有业务，并辨认所选恢复点保留了哪些写入。

### Modified Capabilities

## Impact

主仓交付回退验证入口、证据和迁移手册。消费项目为 `module-zero-core-template@2e953687` 的 Web.Host 与独立 Migrator。复用已冻结的原版 ABP、AutoMapper 和 Angular 产物，以及升级轮两份 SQL Server 备份。本轮支持结论限定于受测 macOS ARM64、.NET 9 原版进程、SQL Server Developer 和 Angular 路径。R4 的正式发行另行验收。[原版运行基线](../../../../docs/maintenance/r3-template-runtime-baseline.md) · [升级交接规范](../../../specs/template-runtime-upgrade/spec.md)
