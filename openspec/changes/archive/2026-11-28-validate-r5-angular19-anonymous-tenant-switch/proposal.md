# Proposal

## Why

BOOT-01 已用双包候选和全公开冻结前端验证匿名首次启动，实测止于空登录表单。TENANT-01 的匿名租户切换需要新的真实浏览器证据，确认通过模板弹窗选中租户和清空返回宿主后，浏览器、服务端及登录页都采用了本次的租户上下文。[BOOT-01 实测](../../../../docs/maintenance/r5-angular19-anonymous-bootstrap.md) · [TENANT-01 验收入口](../../../../docs/compatibility/angular-ecosystem.md#72-首轮验收用例)

## What Changes

- 新增主仓匿名租户切换验收。两个已登记的 production 前端共用一套 R5 后端及一个专用 SQL Server 新库，各自在独立的新 Chrome 上下文通过真实弹窗走完宿主 → 已启用的 `Default` → 宿主。
- 逐阶段核对可见页面和弹窗、租户 Cookie、由相应文档发出的真实初始化请求及匿名响应，并关联选择请求和两次真正的主文档重载。单侧独立判定，再比较两侧的同阶段结果和资源终态。

## Capabilities

### New Capabilities

### Modified Capabilities

- `template-maintenance-package-consumption` 增加固定 Angular 19 模板双包候选与全公开冻结前端的匿名租户双向切换对照。

## Impact

计划输入沿用 `module-zero-core-template` `2e9536872673a7ff1986a19e798c51684d16afe5`、Angular `19.2.1`、登记的本地 `abp-ng2-module 12.1.0` 和经典框架 Git 制成的 `abp-web-resources 6.1.0`，以相同版本的公开 npm 包所构建的冻结前端作对照。后端使用公开 `v10.5.2` Web.Host 和标准 Migrator，运行组合为 macOS ARM64、Chrome、SQL Server。变更涉及主仓验收入口、回归及结果文档，正式运行需重新核对固定实物和 SQL 种子。验收范围限 TENANT-01 的匿名切换，登录提交、已鉴权切换、失效租户业务、其他平台和发行各自验收。BOOT-01 继续在未选租户时结束。[双包输入](../../../../docs/maintenance/r5-angular19-package-pair.md#固定输入) · [公开冻结前端](../../../../docs/maintenance/r5-public-angular-rebuild.md#准备和离线核验)
