# Proposal

## Why

公开 R4、R5 的角色编辑验收已验证同一套冻结 Angular production 前端，但复跑需要原验证机保存在 `.git` 中的构建和清单。固定模板后端已有公开准备路径，普通公开检出还需要独立生成并核验前端输入。

## What Changes

- 从固定模板的 `angular/` Git 对象和锁定的公开 npm 依赖重建 production 前端，在新目录生成 `--angular-source` 所需的静态目录和清单。模板引用的 Google Fonts 样式表是额外的在线构建输入，须记录其来源并核对生成的 `index.html`。
- 提供离线读回，调用 R5 角色编辑验收使用的同一个 `frozen_angular` 校验函数。正式验收覆盖 Yarn 与 Angular 缓存均为空的构建、从公开检出启动新 Python 进程的断网读回，以及清单保持原样时对单个静态文件的篡改反例。
- 首次验收限定 macOS ARM64、Node.js `22.22.0`、Yarn Classic `1.22.22`。公开冷构建已复现登记的产物字节，隔离离线读回已通过。补齐构建后清单失配诊断中的字体识别，区分 Source Sans Pro 字体定义与普通样式中的同名字体引用。[原验收](../../../../docs/maintenance/r5-public-angular-rebuild.md#实测结果) · [诊断修正计划](../../../../docs/maintenance/r5-angular-font-diagnostics-plan.md)

## Capabilities

### New Capabilities

### Modified Capabilities

- `template-maintenance-package-consumption` 增加从公开输入独立准备和核验冻结 Angular 客户端的要求。

## Impact

主仓维护独立准备及证据指引，消费项目为 `module-zero-core-template` 提交 `2e9536872673a7ff1986a19e798c51684d16afe5` 的 Angular 应用。公开 R4 `v10.5.1` 与 R5 `v10.5.2` 仍使用现有角色验收入口。交付范围是前端准备和离线校验，后端还原、SQL Server、浏览器业务、子模块变更和发行附件均在范围之外。
