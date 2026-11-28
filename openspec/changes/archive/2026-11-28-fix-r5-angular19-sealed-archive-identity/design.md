# Design

## Context

匿名启动通过 `BootstrapRun.frontend_input("pair")` 调用 `verify_pair`，成功则将输入证据写入 `sides.pair.input`。离线复审用现有入口还原了报告中的原始输入证据。需要修正的是适配器封存摘要和由它产生的报告字段。[问题与范围](proposal.md) · [复审勘误](../../../../docs/maintenance/r5-angular19-anonymous-bootstrap.md#封存归档身份复审)

## Goals / Non-Goals

目标是在既有双包输入入口准确报告归档身份，并延续已有验收。范围为主仓的摘要登记、判定回归和离线回执。

## Decisions

1. **沿用正常入口。** 在 `PACKAGES` 更正适配器的封存 SHA-256，保留资源包登记值及既有报告字段。继续由 `verify_archive` 核对归档的完整内容及实装，由 `verify_pair` 核对实际归档 SHA-1 对应的锁定位、其余冻结锁、production 清单及同次构建来源。匹配标记仍按实际归档 SHA-256 计算。两份包的登记摘要及实包身份见先前交付的双包指南。[已登记的封存归档](../../../../docs/maintenance/r5-angular19-package-pair.md#固定输入)
2. **用独立登记值和定向反例验证判定。** 在现有 Python 回归中，分别用双包指南已交付的两份原件 SHA-256 断言 `verify_pair` 使用的登记值，测试期望独立于被测 `PACKAGES`。确认原先漏写 `fb` 的值会使回归失败。用临时 tarball、对应实装和冻结锁覆盖以下判定。小型夹具可替换无关的 production 和构建前置输入，摘要、包内容、实装与锁判定走真实逻辑，普通克隆可离线运行。
   - 两份夹具原件及配套输入匹配时，两包标记均为 `true`。只改变适配器 `.tgz` 的包装字节，资源包保持原样。先用旧锁验证必须拒绝，再对同一对归档只更新适配器 `resolved` 项中的归档 SHA-1 为实值。其余锁、内容、实装和构建条件均吻合时，核验通过并记录实际摘要，适配器标记为 `false`，资源包为 `true`。
   - 分别构造归档内容偏离登记、实装偏离归档的反例。各反例令其余条件匹配，包括锁所指归档的实测 SHA-1，从而分别命中内容和实装检查。保留其余冻结锁不符即拒绝的约束。
3. **单独保存正式离线回执。** 核对历史正式报告 SHA-256 为 `b7b8975621708a4a355e9dbf91c0be39aecb4ee5a071b0a0876e775552cdfa49`。在验收机用修复后的 `verify_pair` 直接读取报告对应的两份封存归档、原实装及同次构建输入，沿用原双包 Angular 目录、全局脚本读取记录和统计摘要。单独保存完整输入核验结果，与历史报告的 `sides.pair.input` 完整对照。通过条件为 `packages.abp-ng2-module.matchesSealedArchive` 从 JSON `false` 变为 JSON `true`，资源包标记前后均为 `true`，其余字段逐层一致。任一其他字段新增、缺失或值改变均拒绝。比较范围限于 `sides.pair.input`，回执封套的生成时间等元数据在范围之外。保留原报告并注明 Chrome 和 SQL Server 未重跑。[历史正式报告登记](../../../../docs/maintenance/r5-angular19-anonymous-bootstrap.md#封存归档身份复审)

## Risks / Trade-offs

封存实物位于验收机，在普通克隆中以独立登记的摘要和临时夹具验证判定。实包回放承担对两个原件及配套构建输入的核验。
