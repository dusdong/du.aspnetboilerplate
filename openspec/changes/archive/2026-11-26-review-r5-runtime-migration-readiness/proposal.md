# R5 存量模板迁移与增量维护审查

## Why

.NET 9 已于 2026-11-10 结束支持。R4 已验证公开包在固定模板上的同库升级，存量应用维护者还需要知道怎样核对自己的部署与该基线是否一致，以及哪些差异需要重新验证。[首轮维护审查](../../../../docs/maintenance/r5-first-maintenance-review.md#下轮检查点) · [R4 公开源验收](../../../../docs/maintenance/r4-release-candidate.md#公开源模板消费)

## What Changes

- 按分支从首轮截止提交续查三个上游仓库，并按各来源的截止点复核包公告与 Microsoft 共享运行时服务记录，给出本轮涉及的维护包、运行环境及消费者行动。
- 给存量 `net9.0` 应用维护者一份以公开 `v10.5.1` 为输入的迁移指引，说明如何核对源环境、选择受支持的 .NET 10 服务版本、从自己的源码调整项目引用并构建两入口、用自己的备份在隔离库验证升级，以及如何按恢复点判断写入影响。
- 对输入一致的固定组合复核并引用 R4 原报告；目标运行时或消费输入变化时，用对应组合补验，再将结果列入实测范围。集合映射候选单独按其冻结条件处理。

## Capabilities

### New Capabilities

### Modified Capabilities

- `maintenance-release-review` 增加后续审查的接续条件，以及将运行时服务结论转化为存量消费者迁移指引的验收要求。

## Impact

主仓维护审查记录、迁移指引和证据索引。参考消费者为固定的 `module-zero-core-template`、macOS ARM64、SQL Server 与冻结 Angular 客户端。包输入为经典框架、AutoMapper 与 AutoMapper.Collection 三个生产子仓对应的 13 个 R4 公开包。本轮的目标运行时补丁号和公告截止点在实施时核定。生产部署、扩展平台和发行新包分别按实际需求安排。
