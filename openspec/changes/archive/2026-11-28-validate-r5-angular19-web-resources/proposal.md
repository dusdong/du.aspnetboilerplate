# Proposal

## Why

固定 Angular 19 模板已经用公开 `abp-web-resources 6.1.0` 完成 production 冷构建。下一轮要确认维护者能否直接从经典框架固定 Git 对象制成同名同版本的本地包，并由同一模板实际消费。[公开冷构建](../../../../docs/maintenance/r5-public-angular-rebuild.md#实测结果)

## What Changes

- 从经典框架资源子树的 Git blob 制作本地 tarball，登记分发包装的独立来源，并与公开归档逐文件对照。
- 在固定免费模板的隔离副本中只替换资源包，核对安装身份、声明解析、production 全局脚本及静态资产复制。用本机浏览器检查实际全局脚本行为和两条 SignalR 静态资源 URL。
- 将实际结果及适用范围写回维护计划和 Angular 兼容指南。[分轮计划](../../../../docs/maintenance/r5-angular19-web-resources-plan.md)

## Capabilities

### New Capabilities

### Modified Capabilities

- `template-maintenance-package-consumption` 增加 Web Resources 的 Git 来源、实包隔离消费及静态浏览器验收要求。

## Impact

资源输入为 `aspnetboilerplate` 的生产 gitlink。消费入口为 `module-zero-core-template` 的固定 Angular 子目录，运行组合为 macOS ARM64、Angular `19.2.1` 和公开 `abp-ng2-module 12.1.0`。候选 tarball 和锁差异位于临时目录。此项验收范围止于静态前端，后端、SQL Server、完整业务流程、子仓修改及 npm 发行各有独立范围。
