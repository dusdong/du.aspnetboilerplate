# Spec Delta

## ADDED Requirements

### Requirement: 公开消费者可独立准备冻结 Angular 前端

消费者 SHALL 能从公开固定模板的 Git 对象、锁定的 npm 依赖和模板引用的公开字体样式表独立重建 R5 角色编辑验收使用的 Angular production 前端，并使用同一输入校验离线核对产物。准备使用 Python、Git 和登记的前端工具链。离线核验使用公开检出中的脚本、Python 标准库与搬移后的文件，可在未安装后端、浏览器和数据库客户端的环境中执行。

#### Scenario: 干净的 macOS ARM64 环境从公开输入重建

- **WHEN** 消费者从公开仓库取得指定的模板提交，在无 `node_modules`、无旧产物且 Yarn 下载缓存与 Angular 构建缓存均为空的环境中，使用登记的 Node.js 和 Yarn Classic 安装依赖并执行 production 构建
- **THEN** 入口核对锁文件的固定身份，生成包含 `angular-production-files.json` 和 `source/angular/dist/browser/` 的独立目录。清单文件字节、整表摘要、1193 个文件及角色编辑脚本符合冻结基线
- **AND** 报告记录模板引用的 Google Fonts 样式表 URL，以及新生成的 `index.html` 的实际 SHA-256 和冻结基线值
- **AND** 独立目录可传给既有验收的 `--angular-source`，现有验收使用该选项或其历史默认路径时执行同一输入校验。静态服务改写本轮地址时仅使用服务副本

#### Scenario: 搬移后在离线环境独立读回

- **WHEN** 只复制清单及静态目录到新的绝对路径，从公开主仓检出启动新的 Python 进程，指向该副本。进程禁用网络，且无法访问原构建目录与验证机的历史 `.git` 证据
- **THEN** `verify --angular-source` 通过与角色验收共用的 `frozen_angular` 核验并退出 0。记录实测 Python 版本、隔离条件、输入路径及退出码。若搬移件的清单自身偏离登记摘要，入口在清单校验阶段返回非零

#### Scenario: 工具或在线构建输入不可用

- **WHEN** 工具身份或锁文件偏离、Yarn 安装无法取得依赖，或 production 构建无法获取模板引用的字体样式表
- **THEN** 准备入口返回非零并报告失败阶段、错误与退出码。字体获取失败时注明构建阶段和样式表 URL

#### Scenario: 冷构建成功但新生成的清单偏离基线

- **WHEN** 安装与构建均退出 0，按冻结配置生成清单后，其文件字节或整表摘要与公开登记值不同
- **THEN** 准备入口返回非零，保留本轮清单，报告摘要的预期值与实际值。以公开登记了单文件摘要的产物定位差异。若 `index.html` 偏离，核对其中的 Source Sans Pro 内联样式块并记录摘要或缺失情况。仅有总摘要时，其他文件是否有差异记为未知

#### Scenario: 页面引用 Source Sans Pro 但缺少该字体的定义

- **WHEN** `prepare` 处理的 `index.html` 中没有 `font-family` 声明值为 Source Sans Pro 的 `@font-face` 规则，但普通样式仍引用该字体，或其他字体的 `src:local("Source Sans Pro")` 引用了该名称
- **THEN** `prepare` 的 `report.json` 将字体块记为缺失，`actual` 为 `null`，`bytes` 和 `fontFaces` 均为 `0`。三个产物摘要（HTML、清单文件和整表）均有实际值和预期值，共用核验拒绝偏离冻结基线的产物

#### Scenario: 内联字体定义仍存在但样式块字节偏离基线

- **WHEN** `index.html` 的内联 `<style>` 中仍有 `font-family` 为 Source Sans Pro 的 `@font-face` 规则，但该样式块的原始字节发生变化
- **THEN** `prepare` 的 `report.json` 记录整个样式块原始字节的 SHA-256、字节数和规则数，包括闭合 `</style>` 前的空白。报告保留 HTML 与两级清单的实际及预期 SHA-256，共用核验拒绝偏离冻结基线的产物
- **AND** 在冻结目标块末尾仅追加一个 ASCII 空格（`0x20`）时，块长为 8666 字节，仍有 28 条规则，块 SHA-256 为 `b9d251ef096eb4744625c0cc45448503132f6d79175ae450aaa76af4e7ccecba`。其余 1192 个静态文件与冻结清单一致，`prepare` 在“生成清单与静态实物核验”阶段退出 `1`

#### Scenario: 搬移副本的清单有效但静态文件被修改

- **WHEN** 从已通过离线核验的产物另取隔离副本，仅修改一个非入口静态文件，保留清单原字节
- **THEN** 同一离线入口在静态实物核验阶段返回非零。证据包含清单仍匹配冻结基线的摘要、修改文件的相对路径、清单登记的 SHA-256 及文件的实际 SHA-256。再次核验未修改的有效产物退出 0
