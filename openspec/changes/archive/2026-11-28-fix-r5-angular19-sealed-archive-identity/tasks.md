# Tasks

## 1. 主仓输入核验与回归

- [x] 1.1 修正 `verify_pair` 使用的适配器封存 SHA-256。分别用已交付双包指南的两份原件摘要做独立断言，测试期望独立于被测 `PACKAGES`，确认旧值会失败且更正后通过。用定向 Python 测试核对入口对两份原件均标记 `true`，并验证同一个仅改变包装字节的适配器 `.tgz` 与原样资源包在旧锁下被拒绝，只更新适配器 `resolved` 项的归档 SHA-1 后通过，分别标记 `false` 和 `true`。单独构造归档内容和实装反例，各自令其余条件匹配并验证命中的检查，同时验证其余冻结锁不符即拒绝。

## 2. 实包离线回放与验收记录

- [x] 2.1 核对历史正式报告 SHA-256 `b7b8975621708a4a355e9dbf91c0be39aecb4ee5a071b0a0876e775552cdfa49`。在验收机使用修复后的入口离线核验两份封存原件、原实装及同次构建输入，另存正式回执。完整比较 `sides.pair.input`，仅接受 `packages.abp-ng2-module.matchesSealedArchive` 从 JSON `false` 变为 JSON `true`，资源包持续为 `true`，其余字段增加、缺失或变化均拒绝。比较仅覆盖输入段，封套时间等在范围之外。在匿名启动指南登记输入、实测及历史报告摘要，保留原报告并注明 Chrome 和 SQL Server 未重跑。
- [x] 2.2 运行主仓全套 Python 回归、定向与全仓 OpenSpec 严格校验及 `git diff --check`，核对文档链接、原始报告及输入摘要，记录实际结果。

## 本地验收结果

- 适配器旧摘要使定向回归退出 `1`，更正后 17 项全部通过。主仓 Python 回归 102 项通过。
- `verify_pair` 离线回放退出 `0`。两份原件与实装的 25/42 个文件逐字节核对，通过完整输入比较。正式回执保存在验收机 `.git/review-r5-sealed-archive/implementation/formal-replay.json`。Chrome 和 SQL Server 沿用历史证据。
- 本变更、全仓 16 项及历史归档 31 项 OpenSpec 严格校验通过。相对链接、锚点及差异检查通过。[匿名启动指南的回放记录](../../../../docs/maintenance/r5-angular19-anonymous-bootstrap.md#封存归档身份复审)
