# R5 首轮维护审查

## Why

`v10.5.1` 已有公开包、源码和真实模板的验收记录。项目需要用这些输入回答首个发行后的维护问题：截至本轮检查日，哪些上游修复或依赖公告影响实际消费者，是否需要准备补丁。[R5 维护路线](../../../../docs/maintenance/fork-roadmap.md#r5把持续维护控制在可承担的规模内)

## What Changes

- 在主仓为单条公开发行线建立可复查的维护记录，完成一次有截止时间的真实审查，给出下一次检查的起点。
- 从 13 个公开包的生产提交与固定模板四个实际还原图出发，逐仓核对上游修复，逐入口核对完整的直接与传递 NuGet 依赖公告，并查询实测 .NET 和 ASP.NET Core 共享运行时的服务公告。按原包名查找适用于改名 fork 的事项。
- 随维护记录交付可复查的依赖清单和逐项处置，明确维护包本轮需补丁、无需补丁或暂不能判定。另列模板、运行环境与消费者行动，给影响决定的缺证留下补查条件。
- 已确认需要修复的事项可单独立项。后续补丁若采用主仓 OIDC 受信任发布，按现有手册交接待演练的发布准备。[受信任发布接入建议](../../../../docs/maintenance/r4-release-candidate.md#github-actions-受信任发布接入建议)

## Capabilities

### New Capabilities

- `maintenance-release-review` 规定维护者如何从已发行版本和真实消费者出发核对上游变化、记录影响，并作出可追溯的补丁决定。

### Modified Capabilities

## Impact

主仓负责维护记录。框架、AutoMapper 和 AutoMapper.Collection 三个生产仓提供源码对照，固定免费模板提供 Web.Host 和 Migrator 的消费图。首轮沿用已发行的 11 个 `Du.Abp*` 包 `10.5.1`、`Du.AutoMapper 14.0.0` 和 `Du.AutoMapper.Collection 11.0.0`。受影响时再针对对应组件立项修复。Windows、Linux、其他 Provider 和新的 Angular 组合留在支持矩阵的待验栏。[发行组合](../../../../eng/r4_release_candidate.json) · [公开发行规范](../../../specs/public-package-release/spec.md)
