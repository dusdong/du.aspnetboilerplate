# R3 完整模板 .NET 10 / EF Core 10 运行时升级

## Why

主仓 `a4ffcaa` 已证明固定模板在 .NET 9 上更换维护包后仍能登录并查询同一租户的用户。维护者接下来需要知道，已经运行过这套维护包的应用和 SQL Server 数据库，能否一起升级到 .NET 10 / EF Core 10，并保留已有权限、数据与登录记录。[同目标换包正式结果](../../../../docs/maintenance/r3-template-net9-packages.md#正式运行结果) · [R3 验收顺序](../../../../docs/maintenance/fork-roadmap.md#r3验证升级路径和实际消费者)

## What Changes

- 在维护包版模板上提供可复跑的升级步骤，覆盖 Web.Host 与独立 Migrator 的六个可达工程。从干净输入还原、构建 Release，并逐入口核实 13 份冻结包的适用资产、SQL Server Provider 及传递依赖。
- 在专用 SQL Server 重建已验收的 .NET 9 应用状态，在同一候选库执行 .NET 10 Migrator。将实际迁移连接与该进程的入口、运行时和 SQL Server Provider 关联，核对迁移历史、业务表结构差异和既有数据。
- 用同一份 Angular production 产物向 .NET 10 Host 提交相同的租户登录、授权和用户查询，核对处理请求的程序集与两库登录记录。将升级前后备份分别恢复到独立临时库，按迁移历史和登录记录核实两个恢复点。

## Capabilities

### New Capabilities

- `template-runtime-upgrade` 规定维护包版完整模板跨运行时升级时，消费者可核实的包资产、数据库连续性、业务行为和复跑证据。

### Modified Capabilities

## Impact

主仓维护跨仓验证入口、升级步骤和结果。模板固定在 `module-zero-core-template@2e953687`，框架与两个映射子仓提供已经冻结的候选。拟验组合为 macOS ARM64 的 .NET 10 应用进程、EF Core 10 SQL Server Provider、专用 SQL Server Developer 和现有 Angular 客户端。基线的 .NET 9 实包复验仍可独立运行。后续回退变更将使用本轮保存的恢复点验证原版应用，R4 再处理公开发行。[冻结包登记](../../../../eng/r3_template_net9_reference.json) · [同目标换包规范](../../../specs/template-maintenance-package-consumption/spec.md)
