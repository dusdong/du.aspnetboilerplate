# Proposal

## Why

固定 Angular `19.2.1` 模板的双包验收已证明两份 npm 候选的实装、production 构建和最小页静态观察。BOOT-01 及与之直接相关的匿名初始化仍需要真实模板首次访问的证据。使用全公开冻结前端在同一个 R5 后端上做对照，可以判断替换两份包后这条路径是否成立。[双包实测](../../../../docs/maintenance/r5-angular19-package-pair.md) · [首轮验收用例](../../../../docs/compatibility/angular-ecosystem.md#72-首轮验收用例)

## What Changes

- 分别用双包 production 产物和全公开冻结 production 产物，在全新浏览器上下文从模板根路径直接加载 production index，在同一文档内到达登录页。两侧共享已核验的公开 `v10.5.2` Web.Host、专用 SQL Server 测试库及服务条件。
- 记录每侧的入口和脚本来源、应用配置、两条真实匿名初始化 API、登录页路由与可见控件，并核对本地化文案来自本次用户配置。对照两侧匿名身份、当前语言、登录文案和应用元数据，独立记录可复验的结果和资源终态。[验收设计](design.md)

## Capabilities

### New Capabilities

### Modified Capabilities

- `template-maintenance-package-consumption` 增加固定 Angular 19 模板双包候选与全公开前端的真实匿名首次启动验证。

## Impact

计划在 macOS ARM64 使用固定 `module-zero-core-template` `2e953687`、本地 `abp-ng2-module 12.1.0` 与经典框架 Git 制成的 `abp-web-resources 6.1.0`。后端复用同一固定模板的 R5 公开包 Web.Host 和标准 Migrator 准备。变更预计只涉及主仓验收入口和结果文档。范围限 BOOT-01 匿名首次访问与 CONF-01 的可观察子集。V7 的角色编辑输入校验继续使用登记的公开冻结产物。登录提交、租户选择、角色业务、SignalR、其他平台及 npm 发行各有独立验收范围。[公开冻结前端](../../../../docs/maintenance/r5-public-angular-rebuild.md) · [V7 实测](../../../../docs/maintenance/r5-angular-user-role-edit.md)
