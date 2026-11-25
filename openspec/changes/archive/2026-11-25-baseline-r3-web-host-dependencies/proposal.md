# R3 首包：固定模板 Web.Host 依赖与构建基线

## Why

R2 的 `10.5.1-r2.1` 五包已在 macOS ARM64 上通过独立最小后端的两目标 SQLite 消费验收。下一步需要对固定模板的实际后端入口建立原版还原和构建对照，才能确定整套包迁移的缺口、补包顺序和后续验收输入。[R2 验收](../../../../docs/maintenance/r2-core-package-consumption.md) · [维护计划](../../../../docs/maintenance/du-abp-maintenance-plan.md#73-r3-先选择模板-webhost-入口)

## What Changes

- 在主仓增加可复跑的验证入口，从已登记的 `module-zero-core-template` 提交隔离物化源码，在 macOS ARM64 上干净还原 Angular 配套 `Web.Host` 及其引用闭包，再构建同一 `net9.0` 输入的 Release 产物。
- 从五个模板项目的还原结果记录应用依赖和 SDK 构建输入，逐项核对 Host 应复制与实际输出的框架运行 DLL。将首次验收的精简 JSON 清单随主仓验收文档保存，供后续迁移逐项比较。
- 对照当前框架的项目引用、目标框架及 R2 实物映射，分别列出可独立补齐的包、Module Zero 的依赖次序及 AutoMapper 兼容维护的前提，给后续同批候选和模板迁移提供准入条件。
- 本包验收限于固定原版后端的还原、构建及依赖核对。后续变更处理框架补包、模板迁移、SQL Server 实跑与登录、Angular 构建、其他模板入口、.NET 10 迁移、Mapper 改造、公开发包、CI 和部署。

## Capabilities

### New Capabilities

- `template-host-baseline` — 固定模板 Web.Host 的独立还原与 Release 构建、依赖证据及候选包缺口核对。

### Modified Capabilities

## Impact

- 涉及主仓验证工具和 R3 证据文档。模板子仓是原版消费输入，框架子仓提供静态候选映射，R2 五包实物提供已验包身份。依据为主仓 `105b1263160d049c97a975ee088b79982f1c547d`、模板 `2e9536872673a7ff1986a19e798c51684d16afe5` 和框架 `457be917b46c4fb6237831baac5abb848ffe1c4b`。[设计](design.md)
- R0 冻结登记保留全模板声明口径，R1 与 R2 归档保留各自的历史候选与受测组合。R3 首包单独登记单入口的实际解析版本、资产与构建结果。[R0 基线](../../../../docs/maintenance/release-baseline.json) · [维护基线规范](../../../specs/maintenance-baseline/spec.md) · [运行时迁移规范](../../../specs/runtime-migration/spec.md) · [核心候选包消费规范](../../../specs/core-package-consumption/spec.md)
