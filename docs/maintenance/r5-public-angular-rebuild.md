# 公开重建 R5 冻结 Angular 前端

准备入口从固定模板的 Git 对象、锁定的公开 npm 依赖和构建时取得的 Google Fonts 样式表生成冻结前端。核验入口在离线环境检查产物，可将通过核验的根目录传给 R5 角色编辑验收的 `--angular-source`。[冻结基线](r5-public-angular-rebuild-plan.md#固定输入和产物身份) · [角色编辑复跑](r5-angular-user-role-edit.md#复跑与证据) · [输入验收稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-公开消费者可独立准备冻结-angular-前端) · [OpenSpec 归档](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/)

## 准备和离线核验

从包含准备脚本的主仓检出运行。准备需要 macOS ARM64、Python 3.10 以上、Git、Node.js `22.22.0`、Yarn Classic `1.22.22`，以及访问两个 npm 包源和模板字体样式表的网络。将 `NODE22`、`YARN1` 设为所登记版本的可执行文件绝对路径。`WORK` 为新建的空目录，以下模板检出与候选目录均在其中。模板 Git 仓需包含固定提交 `2e9536872673a7ff1986a19e798c51684d16afe5`。[模板提交](https://github.com/dusdong/module-zero-core-template/commit/2e9536872673a7ff1986a19e798c51684d16afe5) · [Node.js 发行归档](https://nodejs.org/dist/v22.22.0/) · [Yarn Classic 包](https://registry.npmjs.org/yarn/1.22.22)

```sh
git clone --no-checkout https://github.com/dusdong/module-zero-core-template.git "$WORK/template"
CANDIDATE="$WORK/candidate"
python3 -B -S eng/r5_angular_prepare.py prepare \
  --template-repo "$WORK/template" --output "$CANDIDATE" \
  --node "$NODE22" --yarn "$YARN1"
```

`prepare` 通过 `git archive` 从固定提交提取 Angular 源码。它使用本轮空 HOME、临时目录和 Yarn 下载缓存，以 `YARN_IGNORE_PATH=1` 和 `--no-default-rc` 隔离 Yarn 路径重定向和外部 Yarn/npm 配置，并运行冻结锁安装和 production 构建。构建前核对 `.angular/cache` 的初态。生成冻结配置时，脚本只覆盖 `remoteServiceBaseUrl` 和 `appBaseUrl` 这两个历史地址字段。这一步无需监听地址中的端口。

搬移时复制清单和静态目录。离线 `verify` 需要主仓检出的 Python 脚本和 Python 标准库。角色编辑入口使用同一核验函数，并在创建服务副本后写入本轮地址。[共用核验及服务副本](../../eng/r5_angular_role_edit.py)

```sh
MOVED="$WORK/relocated"
mkdir -p "$MOVED/source/angular/dist"
cp "$CANDIDATE/angular-production-files.json" "$MOVED/"
cp -R "$CANDIDATE/source/angular/dist/browser" "$MOVED/source/angular/dist/"
python3 -B -S eng/r5_angular_prepare.py verify --angular-source "$MOVED"
```

准备和离线核验通过时退出 `0`。准备目录的 `report.json` 记录失败阶段、执行命令、工作目录、子进程退出码及原始日志位置，可据此区分工具身份、依赖安装和 production 构建失败。构建错误会附模板字体 URL，实际失败原因见相应构建日志。如果构建成功而清单失配，入口退出 `1`，保留新清单并记录清单文件、整表及已登记单文件的预期和实算摘要。字体项按同一条 `@font-face` 规则的 `font-family` 声明值定位 Source Sans Pro。报告记录整个内联 `<style>` 原始内容的 SHA-256、字节数和块内规则数，包含闭标签前的空白。若页面只有普通样式或 `src:local(...)` 的同名引用，字体摘要为 `null`，字节数和规则数均为 `0`。读取错误保存在 `font.readError`。离线 `verify` 返回 `1` 时，可按错误区分清单文件摘要和静态实物失配。[字体诊断修正实测](#字体诊断修正实测)

## 实测结果

2026-11-27 在 macOS `27.2.1`（`26B131`）ARM64 完成公开空缓存重建。主仓基线为 `e11bebb5b94f227ea8adc5e64fc1559399057dce`，唯一叠加的文件为首次冷构建使用的 `eng/r5_angular_prepare.py`，SHA-256 为 `6f4728abb601da3dc4059317f4bf8d8fad5f20d60a4b68d3d3ae89346895a33c`。GitHub Git HTTPS 两轮超时后，从其公开 Git API 与源码归档重建两份 Git 检出。逐个校验主仓的 348 个 blob、134 个 tree，模板的 1343 个 blob、258 个 tree，以及两份固定 commit 的对象 ID。准备脚本从模板检出运行 `git archive`，归档 SHA-256 为 `de2cc9bbae0bdcee7d42270ae8bdeaae7de6449d7242ed89b3da08e16d2cbbc1`。[主仓提交](https://github.com/dusdong/du.aspnetboilerplate/commit/e11bebb5b94f227ea8adc5e64fc1559399057dce) · [模板提交](https://github.com/dusdong/module-zero-core-template/commit/2e9536872673a7ff1986a19e798c51684d16afe5)

实际工具为 Python `3.14.7`、Node.js `v22.22.0 darwin/arm64` 和 Yarn Classic `1.22.22`。安装前 `node_modules` 不存在，候选根目录的 `yarn-cache/` 为空。构建前 `source/angular/.angular/cache/` 尚不存在，字体缓存随之为空。Yarn 按冻结锁从 `registry.npmjs.org` 和 `registry.yarnpkg.com` 安装，退出 `0`。production 构建退出 `0`，准备入口退出 `0`。Yarn 记录了 peer dependency 警告，Angular 记录了 CommonJS 警告。另行指定本机 Corepack shim 时，工具阶段拒绝其版本输出，未进入安装。

安装前、安装后、构建后三次锁文件 SHA-256 均为 `3e55c44022c5c15bf2c474eb483f8161945151261f06d00218fffbdb86c0d14f`。实际安装版本为 `@angular/core` 和 `@angular/cli` 各 `19.2.1`、`abp-ng2-module` `12.1.0`、`abp-web-resources` `6.1.0`。

| 核对对象 | 实算 SHA-256，均匹配登记值 |
| --- | --- |
| 清单文件 `angular-production-files.json` | `99a2520978f5917fdc98545dc043b90ff5f9f2ed83872b52dbb8e273fa71c12b` |
| 清单内部整表，1193 个文件 | `59203802dd274be9c00c041d1529238d72bd7ddc914a8f84224fbd84923bce37` |
| 角色编辑脚本 `chunk-PPIUHYWS.js` | `67ec845c7dea216c0c54c8a0012a2518baf4247ca5f2c7e587aa4721a39f4e4a` |
| `index.html` | `eb6d4967b6520d53928c759b849e553f77d9073d459973f23983aa0fd5bdb065` |
| Source Sans Pro 内联块，8665 字节、28 条 `@font-face` | `21b1e561f61902ab22e99701e8e4b0ef2b2ca24a1589cdf6208c04295f80f2a9` |

模板的字体输入为 `https://fonts.googleapis.com/css?family=Source+Sans+Pro:300,400,400i,700`。内联样式按 `<style>` 内原始 UTF-8 字节核对。冻结配置在新的构建输出上写入，完整清单由本轮重新计算。[HTML 与字体基线](r5-public-angular-rebuild-plan.md#固定输入和产物身份)

### 隔离搬移验收

在公开主仓检出中启动新的 Python `3.14.7` 进程。命令使用 `env -i` 清空继承环境、独立 HOME、`-B -S` 和 macOS Seatbelt。只向搬移目录复制清单和静态实体目录。隔离探针实际确认外部网络连接、原构建目录中的 `index.html` 和历史 `.git` 清单均返回权限拒绝，公开检出的脚本可读。

| 输入 | 退出码 | 实测结果 |
| --- | --- | --- |
| `offline/relocated` | `0` | 搬移清单及 1193 个文件均通过共用校验。 |
| `offline/tampered-file` | `1` | 保留原清单，只调整 `assets/img/user.png`。在生产静态实物阶段拒绝。 |
| `offline/wrong-manifest` | `1` | 实物全部保持原样，仅向清单追加换行。在清单文件摘要阶段拒绝。 |
| `offline/relocated` 复验 | `0` | 再次通过共用校验，独立快照确认原候选和搬移正例的清单及 1193 个实物全部相同。 |

静态反例的清单仍为 `99a2520978f5917fdc98545dc043b90ff5f9f2ed83872b52dbb8e273fa71c12b`。清单登记的图片 SHA-256 为 `1424999a34e24835229fd13f16b34de95841f2e7abdeaa5aa9a678bf8ed7f6f4`，反例实算为 `74623d28e57f01453d76037b0ec39a2c3ae871327366c5b5758c0d522b91e0dd`。错误清单实算为 `5eae543c031de29cf449ab1fba1e6d90e488191d217415d22cff47aa086337fd`。

### 清单失配诊断复验

上轮修订的 `eng/r5_angular_prepare.py` SHA-256 为 `556f1dd0894960228010ac9a9416127d7a2cb805c1c7c55066ccdc3fcd0cc1dd`。该版本直接读取 HTML 字节，查找同时包含 `@font-face` 和 `Source Sans Pro` 的内联样式。无匹配项时记录空摘要，读取失败时保留错误，清单和静态实物仍交由共用校验函数核对。

复验在隔离的公开主仓检出中启动新 Python 进程，以冻结源码归档和静态实物替代外部安装与构建步骤。两版脚本均对含非法 UTF-8 的 `index.html` 生成了清单。首次冷构建的脚本在解码诊断时退出 `1`，报告缺少产物身份。修订版保留以下两级预期与实算摘要、1193 个文件的清单及 HTML 和编辑脚本身份，将字体块记为缺失，并在生成清单核验阶段退出 `1`。两个负向样本只有 `index.html` 的字节偏离有效产物。修订版对有效产物计算的身份与首次冷构建报告一致。隔离读回复验依次返回 `0`、`1`、`1`、`0`，分别对应有效搬移件、单文件变更、清单变更和有效搬移件复验。

| 摘要 | 预期 SHA-256 | 复验样本 SHA-256 |
| --- | --- | --- |
| 清单文件 | `99a2520978f5917fdc98545dc043b90ff5f9f2ed83872b52dbb8e273fa71c12b` | `a0cc2f08444491646cb292693a91c3d00494b2b41993783c522321d605d7232e` |
| 清单内部整表 | `59203802dd274be9c00c041d1529238d72bd7ddc914a8f84224fbd84923bce37` | `bf09ad1313b73c95c49623522018911d06e07195f31d9b22e499e9e0595a016f` |

### 证据和验收范围

本轮原始证据位于验收机 `.git/prepare-r5-public-angular-rebuild/`。首次冷构建目录为 `candidate-01/`，其 `report.json` SHA-256 为 `52363d18cf486614cf875c62b12776ea3eb832d795e8e7b47e99ccc772e21075`。同目录保留逐文件清单、源码归档、构建原始日志和静态实物。证据根的 `receipts/` 保存输入取得、准备和独立读回的 argv、工作目录、退出码及原始结果。修订回放保存在 `revision-01/`，其中 `repro-after-final/report.json` 的 SHA-256 为 `3582d32f865caa548d0bd411cbd96cfd10c4f9ff5a0629d6feed7cda1db9689e`，`receipts/` 保留修订前后脚本身份、隔离探针、两次回放和四次独立读回的回执。

上轮用 Python `3.14.7` 与 `3.12.14` 各运行 81 项回归，均通过。检查覆盖历史默认来源、显式 `--angular-source`、错误清单拒绝及非法 UTF-8 等已有产物诊断样本。315 个本地链接、107 个锚点及 Git 差异检查通过。OpenSpec 定向校验通过，全仓 16/16，归档 26/26。上轮 5 项验收任务全部完成，范围为 macOS ARM64 准备与离线产物核验。后端、SQL Server 和浏览器业务未实跑，六次真实角色保存沿用 V7 实测。该轮结果以首次验收候选的源码身份登记。[V7 业务证据](r5-angular-user-role-edit.md#复跑与证据)

### 已知诊断限制

2026-11-27 复审在真实冻结 HTML 的隔离副本中只移除了 Source Sans Pro 内联块。剩余样式的 3 条 `@font-face` 均定义 Font Awesome 6 字体，普通样式中仍引用 Source Sans Pro。上轮 `prepare` 的构建后诊断把剩余样式的 5741 字节和 SHA-256 `97e1c0392aac21961910216bd1cde482589afd46c07747405ac20aed00cd470e` 误归给 Source Sans Pro。HTML 及两级清单仍检测到失配，共用校验仍拒绝该产物。上轮非法 UTF-8 回放覆盖的是另一种输入。

复审中独立离线读回再次得到 `0 / 1 / 1 / 0`。误判限定在上轮诊断源码，修正结果见下节。[修正计划](r5-angular-font-diagnostics-plan.md) · [归档任务](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/tasks.md)

### 字体诊断修正实测

2026-11-27，使用主仓基线 `e11bebb5b94f227ea8adc5e64fc1559399057dce` 与本地修正的 `eng/r5_angular_prepare.py` 回放，脚本 SHA-256 为 `b2aa4a2ed295280171f0a54a362f771668fa78b385ea07e5134db766923c1199`。独立复核后收紧了 CSS 注释识别，每条注释在首个 `*/` 结束，保留其后的字体名标识符。Python `3.14.7` 进程由 macOS Seatbelt 禁用网络，并与原冷构建和历史回放目录隔离。以冷构建归档、工具回执、安装版本和静态副本替代相应外部步骤，由当前 `prepare` 实际解包、写入冻结配置、重算清单、运行诊断和共用核验并落盘报告。

| 副本 | 退出码 | 字体块字节 / 规则数 | 字体块 SHA-256 |
| --- | --- | --- | --- |
| 冻结原件 | `0` | 8665 / 28 | `21b1e561f61902ab22e99701e8e4b0ef2b2ca24a1589cdf6208c04295f80f2a9` |
| 仅移除目标块，保留 Font Awesome 定义和普通 Source Sans Pro 引用 | `1` | 0 / 0 | `null` |
| 仅在目标块闭标签前追加 `0x20` | `1` | 8666 / 28 | `b9d251ef096eb4744625c0cc45448503132f6d79175ae450aaa76af4e7ccecba` |
| 沿用上轮非法 UTF-8 HTML | `1` | 0 / 0 | `null` |

冻结副本的 1193 个实物与清单均匹配。三个反例各有 1192 个静态文件匹配，均只改变 `index.html`，在“生成清单与静态实物核验”阶段拒绝。报告逐份列出 HTML、清单文件和清单整表的预期与实际 SHA-256。原冷构建和上轮非法 UTF-8 原件复算一致。

本轮证据位于验收机的 `.git/plan-r5-angular-font-diagnostics/implementation/comment-fix/`，包括 `replay/runs/{frozen,removed,trailing-space,invalid-utf8}/report.json`、`replay-audit.json` 和 `receipts/` 中的原始回执。定向回归 8 项通过，涵盖合法注释之间存在额外字词的反例及带注释的真实目标正例。Python `3.14.7` 和 `3.12.14` 全套回归各 85 项通过。沿用首次真实冷构建和隔离搬移验收。本轮未重新下载、安装或构建，后端、SQL Server 和浏览器业务沿用现有记录。独立复核逐份复算四个副本的静态文件及两级清单，并复验了合法注释的正反用例。验收机的 `.git/plan-r5-angular-font-diagnostics/implementation/primary-review/` 保留独立回执及验收候选的逐文件摘要。稳定规范已同步，七项任务已归档。[归档任务](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/tasks.md)
