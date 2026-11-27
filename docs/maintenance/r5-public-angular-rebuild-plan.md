# R5 公开重建冻结 Angular 前端计划

2026-11-27 制定，审查基线为主仓 `e11bebb5b94f227ea8adc5e64fc1559399057dce`。本计划登记从普通公开检出和空缓存重建 R5 冻结 Angular production 前端的输入与验收条件。[归档提案](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/proposal.md) · [设计](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/design.md) · [归档任务](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/tasks.md) · [公开复跑和实测结果](r5-public-angular-rebuild.md)

## 上一轮审查

| 审查项 | 核对结果 |
| --- | --- |
| Git 与规范 | 主仓 `main` 与 GitHub `main` 对齐，交付的 14 个文件与该提交对象字节一致。GitHub Actions `verify-r0` 通过。稳定规范精确新增一条要求和七个场景，归档任务 5/5。[交付提交](https://github.com/dusdong/du.aspnetboilerplate/commit/e11bebb5b94f227ea8adc5e64fc1559399057dce) · [GitHub Actions 运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45993210180) · [稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-两代公开包可通过固定-angular-模板对照用户角色编辑) · [归档任务](../../openspec/changes/archive/2026-11-27-validate-r5-angular-user-role-edit/tasks.md) |
| 正式业务证据 | 离线核对 `formal-v7` 报告 SHA-256 `85d3e3107e834c6c9a5b966430219c5096d591d9b35721e2c184a15fc77fe417`，以及两侧六次真实 PUT、保存触发的列表 GET、重开窗口的详情 GET、同库角色 SQL。两侧均符合保留 A、替换为 B、清空直接角色的预期。本轮未重跑业务。[分步结果与原始证据位置](r5-angular-user-role-edit.md#复跑与证据) |
| 修订回放与收尾 | 离线核对无注入回放退出 `0`、15 个负向回放各退出 `1`，并核对正式报告所记源码与修订后回放源码身份。当前源码的 77 项 Python 回归重跑通过。新计划写入前，全仓严格校验 15/15、归档检查 26/26。上轮收尾记录了 44 个链接和 17 个锚点通过，清理了 5 份规划临时副本。[历史回放与源码身份](r5-angular-user-role-edit.md#复跑与证据) |

现有 `--angular-source` 只接受已符合冻结身份的目录，默认路径依赖原验证机 `.git` 内的 R3 构建和清单。后端缺少封存输出时已有公开准备路径。R3 能构建前端，但入口与 Web.Host、Migrator 和后续 SQL 及浏览器验证联动，历史正式轮用了预热的 Yarn 下载缓存。该背景促成了公开消费者独立取得前端输入的准备入口。[R5 复跑入口](r5-angular-user-role-edit.md#复跑与证据) · [后端公开准备入口](r5-template-user-role-update-plan.md#复跑公开模板准备) · [R3 构建实测](r3-template-runtime-baseline.md#2026-11-25-本机验收)

## 固定输入和产物身份

| 核对对象 | 固定要求 |
| --- | --- |
| 模板和工具链 | 从公开提交 `2e9536872673a7ff1986a19e798c51684d16afe5` 的 Git 对象提取 `angular/`，使用 macOS ARM64、Node.js `22.22.0`、Yarn Classic `1.22.22`。[固定模板](https://github.com/dusdong/module-zero-core-template/tree/2e9536872673a7ff1986a19e798c51684d16afe5/angular) |
| `angular/yarn.lock` SHA-256 | `3e55c44022c5c15bf2c474eb483f8161945151261f06d00218fffbdb86c0d14f` |
| 构建时字体样式表 | 模板链接 `https://fonts.googleapis.com/css?family=Source+Sans+Pro:300,400,400i,700`，production 构建时获取并内联。[模板 HTML](../../module-zero-core-template/angular/src/index.html) · [production 配置](../../module-zero-core-template/angular/angular.json) |
| `index.html` SHA-256 | `eb6d4967b6520d53928c759b849e553f77d9073d459973f23983aa0fd5bdb065`。[上轮实收记录](r5-angular-user-role-edit.md#输入和进程身份) |
| Source Sans Pro 内联样式块（诊断用） | 冻结 HTML 中，对应该样式表的 `<style>` 标签内原始 CSS 为 8665 个 UTF-8 字节，含 28 条 `@font-face`，SHA-256 为 `21b1e561f61902ab22e99701e8e4b0ef2b2ca24a1589cdf6208c04295f80f2a9`。 |
| 清单内部整表 SHA-256 | `59203802dd274be9c00c041d1529238d72bd7ddc914a8f84224fbd84923bce37`。按相对路径核对全部 1193 个文件。 |
| `angular-production-files.json` 文件字节 SHA-256 | `99a2520978f5917fdc98545dc043b90ff5f9f2ed83872b52dbb8e273fa71c12b` |
| `chunk-PPIUHYWS.js` SHA-256 | `67ec845c7dea216c0c54c8a0012a2518baf4247ca5f2c7e587aa4721a39f4e4a` |

准备脚本使用 Python 3、Git、Node.js 和 Yarn Classic，离线 `verify` 使用公开主仓的 Python 脚本与标准库。记录实际验证的 Python 版本。从无 `node_modules` 的导出目录、独立空 Yarn 缓存和空 Angular 构建缓存开始，按锁文件中的公开源安装，核对实际 Classic 版本，隔离 Yarn 4 接管及已有下载缓存。使用已安装的 Angular CLI 运行 production 构建。构建完成后在输出里的 `assets/appconfig.production.json` 写入冻结地址 `remoteServiceBaseUrl=http://127.0.0.1:14436` 和 `appBaseUrl=http://127.0.0.1:14236`，保留其余配置值，沿用 R3 的 JSON 排序及换行。这两个地址无需监听。以后运行角色编辑验收时，现有入口在服务副本分别写入当轮地址。[构建与交付设计](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/design.md#decisions) · [既有冻结输入](r5-angular-user-role-edit-plan.md#固定输入)

## 验收与完成条件

以下为公开冷构建和离线核验的首次验收口径，对应归档任务的前五项。后续两项完成字体诊断修正及四份实物的离线回放，并通过独立复核。全部七项任务已归档。[首次实测](r5-public-angular-rebuild.md#实测结果) · [修正实测](r5-public-angular-rebuild.md#字体诊断修正实测) · [归档任务](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/tasks.md) · [修正计划](r5-angular-font-diagnostics-plan.md)

1. 在仅有公开材料的新消费者目录，用登记工具链完成至少一次真实空缓存安装和 production 构建。产物根应包含新生成的 `angular-production-files.json` 和 `source/angular/dist/browser/`，能直接作为既有验收的 `--angular-source` 输入。记录主仓和模板提交、实际工具版本、两种缓存的路径与初态、安装和构建退出码、字体样式表 URL、锁文件和产物摘要。
2. 仅复制清单及静态目录到另一绝对路径。从公开主仓检出启动新 Python 进程，使其无法联网或访问原构建目录、历史 `.git` 证据。记录隔离方式，按文档运行 `verify --angular-source` 并确认退出 0。另取副本只改一个非入口静态文件，确认清单摘要仍匹配，记录改动相对路径以及文件的预期和实际摘要，确认入口在静态实物核验阶段返回非零。再读回有效搬移件，确认退出 0。
3. 分别记录工具检查、Yarn 安装或 production 构建的失败阶段、错误及退出码。字体获取失败时附样式表 URL。构建成功但清单失配时，保留本轮清单并报告清单文件和整表的预期、实际摘要。若 HTML 偏离，另核对内联字体样式块的摘要或记录其缺失。公开检出只有摘要，对缺少逐文件参照的路径保留未知结论。

完成条件为公开空缓存实建、搬移后的离线读回和篡改反例均达到预期。端口、后端还原、SQL Server、浏览器及发行都不属于本次前端验收，V7 六次业务保存沿用既有证据。[稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-公开消费者可独立准备冻结-angular-前端) · [执行任务](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/tasks.md)
