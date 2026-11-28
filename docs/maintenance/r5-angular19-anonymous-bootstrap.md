# R5 Angular 19 匿名首次启动

2026-11-28，在 macOS ARM64 上用双包 production 和全公开冻结前端分别从根路径启动固定 Angular `19.2.1` 模板。两侧共用同一公开 R5 `v10.5.2` Web.Host 和一个专用 SQL Server 新库，各自使用新的 Chrome 上下文。双侧独立通过，跨侧比较一致，总入口退出 `0`。这次实测覆盖 BOOT-01 匿名首次访问及 CONF-01 的部分初始化字段，停在可见的空登录表单。验收要求已同步至稳定规范，四项任务已归档。[验收设计](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-anonymous-bootstrap/design.md) · [稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-固定-angular-19-模板可对照双包候选的匿名首次启动) · [归档任务](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-anonymous-bootstrap/tasks.md)

## 固定输入与共享环境

- 固定模板提交为 `2e9536872673a7ff1986a19e798c51684d16afe5`。双包的两份封存 tarball 与全量实装逐文件吻合。复算的适配器及资源包 SHA-256 分别为 `b8939f43e0c05afafcbfb8371c99646006565dc4a613698fd39b6c6b4aa3a2bd` 和 `93c66026539a1c22740b893f4ff8b6213b80e5a9ccbee247c79f651e2648a126`，登记的 SRI 和冻结锁均吻合。双包的同次构建统计 SHA-256 为 `4ce5ece50131399eb9b187707361d8878bf58da2def6b60f628a204a8110bda6`。适配器 FESM 为实收 `chunk-N46DCMOX.js` 贡献 8985 字节。已核对同次读取的九个全局脚本、实际资源包字节及全局脚本输出。复用登记的 Node `22.22.0`、Yarn `1.22.22` 构建实物。[双包来源与构建回执](r5-angular19-package-pair.md#冻结锁与同次来源)
- 双包和公开冻结前端分别核验 1193 个生产文件。双包原始整表摘要为 `b728ead007ff14397d4fe31bfbd160790ab5d7e8d33a22047bef0830c3af6955`，公开冻结整表摘要为 `59203802dd274be9c00c041d1529238d72bd7ddc914a8f84224fbd84923bce37`。静态服务副本各自只改应用配置中的两个 URL，原件在运行前后核验一致。V7 离线入口接收登记公开冻结件，拒绝借用公开清单的双包副本，退出码依次为 `0`、`1`。[公开冻结件及核验](r5-public-angular-rebuild.md#准备和离线核验) · [V7 输入与角色编辑](r5-angular-user-role-edit.md#复跑与证据)
- 先按报告 SHA-256 `c6c629df263afe0d8454aeea514b2b9c2688ab208d02ddfcc2d41576c0d0fe4b` 核对 R5 的两个 Release 入口、文件和还原证据。正式运行 SDK 为 `10.0.404`，两个 .NET 进程实际共享运行时均为 `10.0.15`。Host 回执保留程序集的实际加载路径、摘要和映射组件身份。Migrator 的实际连接指向 Developer `16.0.4236.2` 实例 `r5-role-7641c8871b2266b2`，库 `r5_role_7641c8871b2266b2_r5`，数据库 ID `5`、GUID `C8965783-57ED-43BB-9B4C-38B2EC979F49`。从零业务表完成 30 个 EF Core `10.0.15` 标准迁移并读回必要种子。两侧实际服务均由 PID `32939` 的 Host 提供，库身份在两侧启动前及完成后相同。[R5 公开准备](r5-template-user-role-update-plan.md#复跑公开模板准备)

## 浏览器实测

| 观测 | 全公开冻结前端 | 双包候选 |
| --- | --- | --- |
| 新 Chrome `158.0.8127.37` 上下文 | `127.0.0.1:52462`，初始 Cookie 0 | `127.0.0.1:52463`，初始 Cookie 0 |
| 首个主文档 | 根路径直接 HTTP 200，实收 index 匹配；同一文档到 `/account/login` | 根路径直接 HTTP 200，实收 index 匹配；同一文档到 `/account/login` |
| 静态脚本 | 12 个实收 JS 均匹配，包括 `main-PZGEMKYC.js`、`scripts-4V6IZ3AB.js` | 12 个实收 JS 均匹配，包括同名入口、全局脚本及候选适配器 chunk |
| 初始化 | 应用配置 → `GetAll` → `GetCurrentLoginInformations`，各一次 HTTP 200 | 同顺序，各一次 HTTP 200 |
| Host 和 CORS | `127.0.0.1:52461`，两次 OPTIONS 204，两个 GET 均允许公开前端来源 | 同一 Host，两次 OPTIONS 204，两个 GET 均允许双包前端来源 |
| 匿名与界面 | 宿主侧，无用户或租户；空表单，三项本地化值对应 | 宿主侧，无用户或租户；空表单，三项本地化值对应 |

两个实收 index 的 SHA-256 都是 `eb6d4967b6520d53928c759b849e553f77d9073d459973f23983aa0fd5bdb065`，双包候选 chunk 的实收摘要为 `1c93d0ac4d0337ff2cccb659140cb73e762c662ee90c9f3f1baa8e7e61363fa0`。观测窗口在登录表单可见、主文档和所需脚本及初始化回执到齐后截取。两侧截取时各有三个字体请求仍在进行。两端均无未捕获页面异常、认证提交、租户可用性查询、角色操作或 SignalR 协商与连接。

两侧实际业务成功响应均保留显式 `null` 的用户与租户，`GetAll` 的当前语言是 `en`，时钟为 `unspecifiedClockProvider`。本地化值 `Log in`、`User name or email` 和 `Password` 对应标题、提交按钮及占位文本。Session 应用版本均为 `9.3.0`，`releaseDate` 均为 `2026-11-27T17:15:15.9744467+08:00`，`features` 均为 `{}`。应用配置的 `localeMappings` 跨侧相同，URL 按各侧服务和同一 Host 核对。

## 从普通克隆复跑

从主仓根目录使用 macOS ARM64、Python 3、`playwright`、`pymssql`、本机 Chrome、已登记的 .NET 安装及本机 Docker。实测为 Python `3.14.7`、Playwright `1.59.0` 和 pymssql `2.3.13`。按冻结指南准备 `PUBLIC_SOURCE`，按双包指南复跑并登记 `PAIR_ANGULAR`、`PAIR_INPUTS` 和 `PAIR_READS`，三者分别为 `pair-frozen/source/angular`、两份归档所在的 `inputs` 和本次 `pair-frozen/global-reads.jsonl`。使用双包指南引用的新版观测代码直接产生读取记录。从公开准备步骤取得 `PREPARED` 和独立登记的 `REPORT_SHA256`。将 `CHROME` 指向本机 Chrome 可执行文件，三个示例端口须为空闲环回端口。[公开前端准备](r5-public-angular-rebuild.md#准备和离线核验) · [双包重建](r5-angular19-package-pair.md#从普通克隆复跑) · [后端准备](r5-template-user-role-update-plan.md#复跑公开模板准备)

```sh
docker pull --platform linux/amd64 \
  mcr.microsoft.com/mssql/server@sha256:0ec7739e1c5ec2f57861facbe1f2b74f1d3e147c7c97edf91eeea920c5944d9c
WORK="$(mktemp -d "${TMPDIR:-/tmp}/r5-angular-anonymous.XXXXXXXX")"
python -B eng/r5_angular_anonymous_bootstrap.py \
  --prepared "$PREPARED" --report-sha256 "$REPORT_SHA256" \
  --public-source "$PUBLIC_SOURCE" --pair-build "$PAIR_ANGULAR" \
  --pair-inputs "$PAIR_INPUTS" --global-reads "$PAIR_READS" \
  --chrome "$CHROME" --host-port 52461 --public-port 52462 --pair-port 52463 \
  --output "$WORK/formal"
```

重建双包时，原始产物继续匹配登记整表。归档包装摘要变化时，入口核对登记的逐文件内容，并按实际归档 SHA-1 校验对应锁定位，再比对其余冻结锁。实测沿用登记的同次统计摘要。独立重建如果统计文件摘要变化，按双包指南核对同次构建及脚本来源后，通过 `--stats-sha256` 传入当次已登记的摘要。入口仍核对 FESM、实际全局脚本读取及相应浏览器字节。若某侧输入不可核验或前端端口无法绑定，满足自身和共享前提的另一侧继续，整体退出非零。收尾核对本轮实际绑定的监听。报告用各侧状态和跨侧比较结果区分缺少前置输入、启动失败和两侧观测差异。

## 证据与收尾

正式实跑记录在验收机的 `.git/plan-r5-angular19-anonymous/implementation/revision/formal/`。其中 `report.json` 的 SHA-256 为 `b7b8975621708a4a355e9dbf91c0be39aecb4ee5a071b0a0876e775552cdfa49`。目录内保留两侧服务清单、白名单浏览器证据、两个进程及 SQL 读回。初版实跑证据与复审修订的报告均已保留。两端静态服务、Chrome、Host 和 Migrator 已关闭。专用 SQL 容器及库已移除，未产生匿名卷。四个本轮环回端口均已释放，临时服务目录及进程环境目录已清理。

分别传入错误的双包统计摘要和缺失的公开输入，各次仅受阻侧不启动，合格侧实际通过，整体均退出 `1`。用正式报告回放错误脚本字节、缺少回执、非匿名、HTTP 跳转、单侧受阻和两侧局部自洽但值不同，均被拒绝。复审修订中，用公开观测代码调用固定 Angular 实装中的全局脚本构建器，生成的九条读取记录均原样通过来源核验。独立占用公开前端端口时，双包侧实际通过，占用者的监听仍可连接。定向判定和全套 Python 回归分别通过 11 项和 96 项。

本轮未执行登录、租户切换、角色业务、SignalR、其他平台或发行。前端和后端构建沿用经核验的封存输入。

### 封存归档身份复审

2026-11-28 离线复核两份封存 tarball 的 SHA-256、SRI、锁定位 SHA-1 和全部实装文件，适配器 25 个文件、资源包 42 个文件均逐字节吻合。适配器原件的 64 位 SHA-256 已在上文更正。正式报告原样保留，`sides.pair.input.packages.abp-ng2-module` 的实际 `sha256` 一直正确。入口登记的封存摘要漏写 `fb`，因此报告将适配器的 `matchesSealedArchive` 记为 `false`，资源包记为 `true`。[双包原件登记](r5-angular19-package-pair.md#固定输入)

该字段描述归档与封存原件的字节匹配。原报告的内容、实装、锁和构建核验均通过，双侧浏览器结果仍为 `passed`，跨侧为 `equal`。本次离线修复沿用原始浏览器和 SQL 证据，Chrome 和 SQL Server 均未重跑。稳定规范已同步，三项修复任务已归档。[稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-匿名启动双包输入报告准确标记封存归档) · [封存身份修复归档](../../openspec/changes/archive/2026-11-28-fix-r5-angular19-sealed-archive-identity/tasks.md)

修正后的 `verify_pair` 直接读取双包证据目录 `.git/plan-r5-angular19-pair/implementation/` 中的 `inputs/`、`frozen/source/angular/` 及 `frozen/global-reads.jsonl`。两份原件、原实装的 25/42 个文件、同次统计、九条全局脚本读取及 1193 个 production 文件均核验通过。历史正式报告仍为上述 SHA-256 `b7b8975621708a4a355e9dbf91c0be39aecb4ee5a071b0a0876e775552cdfa49`。完整的 `sides.pair.input` 中唯一变化是适配器的 `matchesSealedArchive` 从 JSON `false` 变为 JSON `true`。资源包始终为 `true`，其他字段、类型及结构均一致。[回放判定](../../openspec/changes/archive/2026-11-28-fix-r5-angular19-sealed-archive-identity/design.md#decisions)

验收机从主仓根目录执行 `python3 -B .git/review-r5-sealed-archive/implementation/replay-formal.py`，退出 `0`。同目录的 `formal-replay.json` 保存完整双包输入和逐文件证据，SHA-256 为 `617025c06aac25fa2e6d67a62f34611756217e83779f94866df368e98578f6cb`。

按双包指南的独立摘要，旧登记值在定向回归中仅适配器断言失败，修正后 17 项全部通过。同一份重包装适配器和原样资源包在旧锁下被拒绝，仅更新适配器的 `resolved` SHA-1 后通过，两包分别标记为 `false` 和 `true`。归档内容、实际安装或其余冻结锁偏离的独立反例分别在对应校验处被拒绝。[独立摘要](r5-angular19-package-pair.md#固定输入)

主仓 Python 回归通过 102 项。定向、全仓 16 项和历史归档 31 项 OpenSpec 严格校验、文档相对链接及锚点和差异检查均通过。

## TENANT-01 匿名租户切换

2026-11-28，两侧在 macOS ARM64 上分别用新 Chrome 上下文通过真实模板弹窗完成宿主 → `Default` → 宿主。两侧与跨侧分别为 `passed`、`passed` 和 `equal`，命令退出 `0`。BOOT-01 原有入口仍在首次到达未选择租户的空登录表单时结束。[验收设计](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-anonymous-tenant-switch/design.md) · [实施任务](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-anonymous-tenant-switch/tasks.md)

| 阶段 | 双侧实际浏览器及 API 证据 |
| --- | --- |
| 初始宿主 | 根路径直接收到本侧 production index（HTTP 200），在同一文档进入登录页。当前租户未选择，真实弹窗输入为空，租户 Cookie 缺省，GetAll 为宿主（2），Session 无租户。 |
| 选中 `Default` | 唯一一条租户可用性 POST 实收 HTTP 200、业务成功及 `Available`，租户 ID 为 SQL 种子的 `1`，随后进入新主文档。GetAll 为租户（1），Session 租户 ID、租户名和显示名与 SQL 一致，Cookie 匹配种子，真实弹窗预填 `Default`。 |
| 返回宿主 | 清空后由保存动作进入第三个主文档，仍到达 `/account/login`。该窗口无额外选择 POST，租户 Cookie 已移除，本阶段实收 GetAll 和 Session 恢复宿主语义。 |

三阶段均显示同一本地化的空登录表单。每个文档独立取得本侧应用配置、GetAll 和 Session 各一次，用户和模拟身份持续为空。两个宿主阶段的连字符头缺省，已选租户的三条 GET 均实际携带该头且匹配种子。点号头在应用配置和 GetAll 随阶段变化，Session 实测缺省。每侧七条 OPTIONS 预检独立记录。报告使用主框架 `loaderId` 和请求 `requestId` 核对每次响应，并把 Chrome 实读的 `PerformanceNavigationTiming.type` 绑定到对应主文档。两侧三阶段原值均为 `navigate → reload → reload`，再用清空后的文档独立核对宿主回执。

Chrome 为 `158.0.8127.37`，.NET SDK 为 `10.0.404`，运行时为 `10.0.15`。标准 Migrator 在本轮独占 SQL Server Developer `16.0.4236.2` 实例中迁移新库。实际服务端为 `r5-role-649cb3332b603b18`，库为 `r5_role_649cb3332b603b18_r5`，数据库 ID 为 `5`，GUID 为 `3FA9E509-2EA0-46C9-AC17-10FDC4E5E063`。库身份、30 条迁移及启用的共享库租户种子 `(1, Default, Default)` 前后读回一致。SQL 会话按 PID 对账到同一实际 Web.Host。三个应用环回监听分别为全公开前端 `52462`、双包前端 `52463` 和 Web.Host `52461`，另有容器分配的独占 SQL 环回端口。

### 复跑 TENANT-01

沿用本文[普通克隆准备说明](#从普通克隆复跑)的公开冻结前端、双包实物及独立登记的后端准备报告。正式运行使用两份封存 tarball，两个 `matchesSealedArchive` 均为 `true`，对应前端各有 1193 个冻结文件。实际环境为 Python `3.14.7`、Playwright `1.59.0` 和 pymssql `2.3.13`。先按准备说明取得登记的 SQL 镜像和所需工具，再从主仓根目录执行。

```sh
WORK="$(mktemp -d "${TMPDIR:-/tmp}/r5-angular-tenant-switch.XXXXXXXX")"
python -B eng/r5_angular_anonymous_tenant_switch.py \
  --prepared "$PREPARED" --report-sha256 "$REPORT_SHA256" \
  --public-source "$PUBLIC_SOURCE" --pair-build "$PAIR_ANGULAR" \
  --pair-inputs "$PAIR_INPUTS" --global-reads "$PAIR_READS" \
  --chrome "$CHROME" --host-port 52461 --public-port 52462 --pair-port 52463 \
  --output "$WORK/formal"
```

正式证据位于验收机的 `.git/plan-r5-angular19-tenant-switch/implementation/formal-v3/`。其中 `report.json` 的 SHA-256 为 `6b9d7fb77c8af3904a9dcf3c1c1366eac5be277b5f9435b573707b20f9a140ae`。报告记录原始白名单网络事件、DOM 实读、SQL 前后回执及进程退出状态，并随附两份服务清单。两侧上下文、Chrome、静态服务、Web.Host 和 Migrator 均已退出，独占容器及新库已移除，四个端口已释放，无卷或临时服务目录残留。两侧原前端、两份 tarball 及后端准备输入复核通过。实测范围到返回宿主空表单为止，登录提交、已鉴权切换、失效租户、角色业务、SignalR、其他平台与发行仍属各自验收范围。

错误的双包构建统计摘要使该侧在输入核验时受阻，全公开侧仍实测通过。占用全公开侧端口时，双包侧仍实测通过，原监听可连接。两次命令均按预期退出 `1`。从正式回执用同内容的初始宿主 GetAll 替换返回宿主回执，两侧均拒绝。旧 BOOT-01 独立复跑退出 `0`，两侧均只有首次启动的一个主文档。同 URL 的 Chrome 对照中，普通链接加载了新文档且返回 `navigate`。将该实读值代入任一次保存后的正式回执时，两侧均判失败。主仓匿名场景定向回归 39 项、全套 Python 回归 124 项通过。

### TENANT-01 归档与交付核对

2026-11-28，本地归档前已按最终清单核对 11 份候选文件及上列正式报告摘要。一条要求及五个场景已同步至稳定规范，四项实施任务已归档。39 项定向回归、124 项全套 Python 回归、双侧 Chrome / SQL Server 实跑和 12 次离线反例回放均为本地证据。[稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-固定-angular-19-模板可对照双包候选的匿名租户切换) · [归档任务](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-anonymous-tenant-switch/tasks.md)

截至本次本地归档，Git 交付及远端 CI 回执待办。单独交付 TENANT-01 时，在待提交树中检查归档、稳定规范及指南的相对链接。新增的租户回归文件命中 `main` 推送的 `eng/tests/**` 过滤条件。推送后按该提交 SHA 回读 `verify-r0` 的运行链接和结论，登记为 R0 基线复验。其 Python 步骤只发现 `test_verify_r0.py`。[工作流](../../.github/workflows/verify-r0.yml) · [CI 测试入口](../../eng/tests/run_verify_r0_tests.py)
