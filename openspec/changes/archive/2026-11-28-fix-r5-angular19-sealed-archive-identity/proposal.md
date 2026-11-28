# Proposal

## Why

匿名首次启动报告记录了正确的适配器归档 SHA-256，但主仓入口登记的封存摘要缺少 `fb`，把已验收的原件标成了 `matchesSealedArchive: false`。报告下次生成时应准确识别封存原件，同时继续接受仅包装字节变化、实际内容及消费证据均吻合的归档。[离线复审勘误](../../../../docs/maintenance/r5-angular19-anonymous-bootstrap.md#封存归档身份复审)

## What Changes

- 更正双包输入校验使用的适配器封存摘要，让报告分别反映两份实收归档是否与各自封存原件字节一致。
- 用独立登记的封存摘要覆盖本次错录，并回归同内容重包装及错配输入的判定。
- 离线回放既有实包和构建证据，独立保存重放结果并保留原始正式报告。

## Capabilities

### New Capabilities

### Modified Capabilities

- `template-maintenance-package-consumption` 增补匿名启动双包输入的封存原件标记与内容验收规则。

## Impact

涉及主仓的 `verify_pair`、其 Python 回归及报告证据。适用对象为固定模板 `2e9536872673a7ff1986a19e798c51684d16afe5` 的 Angular `19.2.1` 双包 production 组合，使用已验收的 `abp-ng2-module 12.1.0` 和 `abp-web-resources 6.1.0`。实包离线回放沿用 macOS ARM64 验收机的封存输入。组件源码、模板和发行均在本项范围之外。[双包原件与构建证据](../../../../docs/maintenance/r5-angular19-package-pair.md)
