# Proposal

## Why

固定 Angular `19.2.1` 模板已有全公开包和两种单独换包的实测。两轮候选分别搭配另一份公开包，下一轮要补齐两份本地候选在同一次冻结安装和 production 构建中共同消费的证据。[公开冷构建](../../../../docs/maintenance/r5-public-angular-rebuild.md#实测结果) · [适配器实测](../../../../docs/maintenance/r5-angular19-adapter-package-plan.md#实测结果) · [资源包实测](../../../../docs/maintenance/r5-angular19-web-resources-plan.md#实测结果)

## What Changes

- 使用两份已验本地 tarball，在固定模板的隔离副本中同时替换两个直接依赖。用原锁生成临时锁，从另一空目录及独立空缓存冻结复装，核对实装来源与其余依赖图。
- 实际执行一次双候选 production 构建，证明适配器 FESM 进入具体浏览器 JS，资源包的声明、全局脚本和两份静态资产来自同次安装。与仅换资源的实测逐路径比较同阶段的完整浏览器产物，按设计条件决定是否可引用历史静态浏览器观察。[设计](design.md)
- 在主仓记录实际输入、构建和比较结果，以及静态浏览器证据是历史引用还是本次执行。验收停在固定模板的实包消费和限定的静态观察。

## Capabilities

### New Capabilities

### Modified Capabilities

- `template-maintenance-package-consumption` 增加同一固定 Angular 19 模板同时消费两份已登记本地 npm 候选的验收要求。

## Impact

消费入口为 `module-zero-core-template` 的 `2e953687`，目标平台为 macOS ARM64。实包输入为适配器 `a8ca4b3` 制成的 `abp-ng2-module 12.1.0` 和经典框架 `7933e71` 制成的 `abp-web-resources 6.1.0`。实际归档身份、可比对照与结果在执行时核验。现有 V7 角色编辑继续使用原公开冻结前端及原有校验。候选应用登录、SignalR 连接、后端和数据库业务，以及自有 npm 包与发行支持均超出本次验证范围。[固定身份与验收边界](design.md)
