# Proposal

## Why

固定 Angular 19 模板已用公开 `abp-ng2-module 12.1.0` 和 `abp-web-resources 6.1.0` 完成冷构建和业务验收。本轮拟验证维护者能否从登记的 12.1.0 源码制成本地 npm 包，并让同一个模板以它完成 production 编译。[已交付结果](../../../../docs/maintenance/r5-public-angular-rebuild.md#实测结果)

## What Changes

- 在 macOS ARM64 从 12.1.0 发布参考提交的根锁开始实测安装、production 构建与本地制包。原锁冻结安装因缺少条目失败时，再用相同库源码的后续提交及其根锁独立试验。按提交分别记录安装和制包结果。
- 用固定模板对照公开实包与本地候选，核对实际安装文件、其他依赖、模板解析到的候选类型声明及包含候选 FESM 代码的浏览器 JS 产物。分别记录制包与消费结论、字节差异及未验证范围。
- 在主仓记录跨仓消费结果及 Angular 兼容指南。现有运行验收继续使用其登记的公开包和冻结输入。[实测与复跑](../../../../docs/maintenance/r5-angular19-adapter-package-plan.md)

## Capabilities

### New Capabilities

### Modified Capabilities

- `template-maintenance-package-consumption` 增加从固定适配器源码制包、验证产物身份及同一 Angular 模板编译消费的要求。

## Impact

输入为 `abp-ng2-module` 的 Angular 19 历史 Git 对象、npm 公开实包及 `module-zero-core-template` 固定提交。模板消费范围为 Angular `19.2.1`、资源包 `6.1.0` 和候选适配器 `12.1.0`。本轮实施使用隔离目录内的临时 tarball 与模板副本。组件持久化修改、Git 指针更新、Angular 升级、公开发行和应用运行验收各需独立范围。
