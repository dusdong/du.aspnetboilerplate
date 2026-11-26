# R5 内建集合映射上下文补丁候选

## Why

首轮维护审查在 `Du.AutoMapper 14.0.0` 的发行源码中发现，内建集合映射检查元素映射的上下文，却按包含该成员的类型映射判断深度。上游已修正同类问题，普通应用在已发行维护包上的实际表现仍待对照。[维护决定](../../../docs/maintenance/r5-first-maintenance-review.md#本轮决定) · [上游修复](https://github.com/LuckyPennySoftware/AutoMapper/pull/4651)

## What Changes

- 在固定 MIT 14 维护线上独立修正内建集合映射。分析和探索性构建可先行，正式冻结及交接前须用相同的有界普通 `Map` 用例，实测公开 `Du.AutoMapper 14.0.0` 至少一个可重复的顺序偏差及候选的预期结果，并核对两侧实际加载的 DLL。差异未建立时保留待验证状态，回到维护评估。
- 为引擎、Collection 和 ABP 适配器制备三对本地候选，逐条更新精确依赖，复用其余十个公开维护包。引擎保留原版 `AutoMapper 13.0.0` 的 API 比较，另与公开 R4 引擎作实包 API 比较。凭独立登记的引擎摘要先复验三则公告，冻结三包时核对同一实物，再验证经典 ABP 的对象更新、按键集合及关系型投影。
- 在固定模板验证 `net10.0` 新库安装、`net9.0` 至 `net10.0` 同库接续，并在固定 `net10.0` 与同一隔离 SQL Server 库上实测完整 R4、候选组合、完整 R4 三阶段，以授权查询核对同一业务记录。通过后交付候选清单、独立登记的摘要和消费者结果，供单独的公开发行决定使用。

## Capabilities

### New Capabilities

### Modified Capabilities

- `automapper-package-consumption` 新增普通集合映射的顺序一致性和三包补丁组合的消费者验收条件，沿用已稳定的映射业务契约。

## Impact

行为修复归属 `AutoMapper`。另外两个生产仓 `AutoMapper.Collection` 和 `aspnetboilerplate` 调整对应包的版本与依赖。主仓负责三包组合和跨仓验收，固定免费模板用于消费验证。运行范围沿用 R4 的 macOS ARM64、SQL Server 和冻结 Angular 客户端，`net9.0` 仅用于存量迁移对照。[稳定消费规范](../../specs/automapper-package-consumption/spec.md) · [已有运行证据](../../../docs/maintenance/r4-release-candidate.md#公开源模板消费)
