# 建立首条维护线基线

## Why

主仓已固定六个子模块的检出提交，框架现状仍是 `net9.0`，映射和 Angular 组件的检出版本与存量消费组合存在差异。先取得可复现的框架基线和明确的包边界，后续才能分别判断上游补丁、.NET 10 迁移和独立发行对消费者的影响。

## What Changes

- 以框架上游 `v10.5.1` 对应提交为首条维护线的比较基准，记录各相关子模块的来源、用途及待验证的兼容组合。
- 将首批后端候选收敛为 `Abp`、`Abp.AspNetCore`、`Abp.EntityFrameworkCore` 及其内部依赖 `Abp.Web.Common`、`Abp.EntityFramework.Common`，建立原包与 `Du.Abp*` 的映射清单。
- 从五个 Release 程序集提取可比较的公共 API 和资源清单，记录本次构建与回归实际使用的 NuGet 包版本、有效包源和复现命令。
- 登记免费模板已声明的后端依赖及首批五包尚未覆盖的部分，为独立最小消费者和完整模板分别指定后续验收范围。

## Capabilities

### New Capabilities

- `maintenance-baseline`: 记录维护来源、候选包依赖闭包和可复现的基线验证证据。

### Modified Capabilities

## Impact

主仓增加维护基线记录及验证入口。首轮在固定框架源码上取得构建和 SQLite 回归证据。映射、前端与样例子模块提供兼容参考。基线阶段登记模板缺口，独立发包阶段由最小消费者验证五个候选包，模板依赖闭合后再做整体验收。其他数据库 Provider 和真实业务消费者按实际应用确定。
