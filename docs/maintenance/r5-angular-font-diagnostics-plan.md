# R5 Angular 内联字体诊断修正计划

2026-11-27。公开冷构建和隔离离线产物核验已通过。首次冷构建使用公开主仓基线叠加的初版脚本，随后对修订脚本进行了构建后回放。复审重跑 Python `3.14.7`、`3.12.14` 回归，各 81 项通过。隔离读回按有效搬移件、静态文件变更、清单变更、有效件复验的顺序再次得到 `0 / 1 / 1 / 0`。上轮 5 项验收记录继续有效。诊断修正及四份实物回放已通过独立复核，并随原五项任务归档。后端、SQL Server 和浏览器业务未重跑。[本轮实测与证据](r5-public-angular-rebuild.md#字体诊断修正实测) · [首次实测](r5-public-angular-rebuild.md#实测结果) · [归档任务](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/tasks.md)

## 已复现的问题

在冻结 `index.html` 的隔离副本中只移除 Source Sans Pro 的 `<style>`。仍存在的块含 3 条 Font Awesome 6 的 `@font-face` 及普通样式对 Source Sans Pro 的引用。修正前的 `production_identity` 按同一块内的两个关键词判定，误报该块的 5741 字节、3 条规则和摘要 `97e1c0392aac21961910216bd1cde482589afd46c07747405ac20aed00cd470e`。HTML 与两级清单均偏离，共用校验正确拒绝。问题局限于 `prepare` 构建后的诊断。[诊断实现](../../eng/r5_angular_prepare.py) · [共用校验](../../eng/r5_angular_role_edit.py)

## 实施与验收

1. 在 `production_identity` 中以同一条 `@font-face` 规则内的 `font-family` 声明识别 Source Sans Pro。用 Python 标准库完成规则识别，命中后摘要完整 `<style>` 内容的原始字节。冻结摘要用于比对。CSS 注释在首个 `*/` 结束，保留注释间的字体名称标识符。合成单测同时覆盖普通样式中的字体引用与 `@font-face{font-family:"Other";src:local("Source Sans Pro")}`。后者声明的字体是 `Other`。缺少其他目标定义时，两个样本均应报告目标缺失。用带注释的完整目标名称和多余标识符反例核对注释边界，保留既有非法 UTF-8 诊断回归。[定向回归入口](../../eng/tests/test_r5_angular_prepare.py)
2. 四种样本均取真实冻结产物的独立副本，通过 `prepare` 离线回放构建后的配置写入、清单生成、`production_identity` 诊断及 `frozen_angular` 核验。逐份读取 `report.json`，对照下表的独立期望，并记录输入身份、实际与预期摘要、阶段和进程退出码。只在副本变更 `index.html`，沿用冻结基线与公开包。使用已有构建产物和前轮非法 UTF-8 样本即可回放，无需重新下载、运行 production 构建、启动后端、SQL 或浏览器。

| 样本 | 通过条件 |
| --- | --- |
| 合格原件 | 共用核验退出 `0`。目标块仍为 8665 字节、28 条规则，SHA-256 为 `21b1e561f61902ab22e99701e8e4b0ef2b2ca24a1589cdf6208c04295f80f2a9`。 |
| 仅移除目标块 | 保留 Font Awesome 定义与普通 Source Sans Pro 引用。报告字体块缺失，`actual` 为 `null`，`bytes` 与 `fontFaces` 均为 `0`。 |
| 目标块末尾追加一个空格 | 在目标块的 `</style>` 前插入一个字节 `0x20`。整块应为 8666 字节、28 条规则，SHA-256 为 `b9d251ef096eb4744625c0cc45448503132f6d79175ae450aaa76af4e7ccecba`。 |
| 非法 UTF-8 样本 | 保留前轮样本的字体缺失诊断和完整产物身份。 |

对照冻结清单逐项核对三个反例。每个副本仅 `index.html` 的字节偏离，其余 1192 个静态文件均匹配。`prepare` 的报告须保留 HTML、清单文件和清单整表的实际及预期 SHA-256，三个反例均在“生成清单与静态实物核验”阶段退出 `1`。归档前已更新指南，并完成定向回归、独立复核、链接和 Git 差异检查及 OpenSpec 严格校验。[设计](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/design.md#decisions) · [稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-公开消费者可独立准备冻结-angular-前端) · [归档增量](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/specs/template-maintenance-package-consumption/spec.md)
