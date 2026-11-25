# R3 AutoMapper 候选包与映射兼容验收

## Why

主仓 `d54f782` 已固定 Module Zero 框架提交 `819c64cf`。固定模板 Web.Host 的六个维护候选缺口只余 `Abp.AutoMapper`，它同时依赖映射引擎、Collection 和 ABP 内核，补齐适配器需要验证三份映射包能共同还原并保持原有业务行为。[模板依赖图](../../../../docs/maintenance/r3-web-host-baseline.md) · [Module Zero 交付](../../../../docs/maintenance/r3-module-zero-candidates.md#git-交付)

## What Changes

- 在 macOS ARM64 干净检出上验证引擎的 ApiCompat 入口，再以固定的 AutoMapper 14、Collection 11 和经典框架源码生产三个候选及符号包。逐项登记三则公告的处置依据、补丁来源与许可，用冻结引擎包复验约定行为。GHSA-gpwp-5797-mjff 的 CLR 低栈分支按增量规范约定的组合证据验收。
- 用独立 `net9.0` 消费者从空缓存只安装 `Du.Abp.AutoMapper`，核对四条精确依赖，并确认映射完成后进程中只有一个引擎程序集实例。业务消费者对照固定模板的用户更新、SQLite 用户投影和独立 `AutoMapKey` 集合用例。
- 为冻结批次提供可复跑的验证入口和验收记录。通过后把固定 Host 的六个缺口登记为已取得独立候选，随后在单独变更中验证整套模板的安装、登录、升级与回退。

## Capabilities

### New Capabilities

- `automapper-package-consumption` 规定经典 ABP 映射候选的来源、唯一依赖闭包和消费者可观察的映射行为。

### Modified Capabilities

## Impact

- `AutoMapper`、`AutoMapper.Collection` 子仓分别维护引擎与集合扩展，`aspnetboilerplate` 子仓维护适配器。主仓维护跨仓组合、验收入口及报告。固定模板提供原版 Profile 和类型，R2 内核与 R3 Module Zero 冻结原包提供候选侧依赖。
- 首次目标为 macOS ARM64、`net9.0` 和 EF Core SQLite。模板 SQL Server、Angular 与 .NET 10 整体验收沿用后续 R3 排期。公开包版本在 R4 确定。[映射兼容指南](../../../../docs/compatibility/automapper.md) · [维护路线](../../../../docs/maintenance/fork-roadmap.md)
