# 公开 R4 与 R5 的固定 Angular 用户角色编辑实测

2026-11-27，公开 R4 `v10.5.1` 与 R5 `v10.5.2` 在两套独立的浏览器会话和 SQL Server 新库中各完成三次真实页面保存。两侧均保留 A、改选 B、再清空直接角色。每步的 PUT、保存触发的列表查询与数据行、重新打开的窗口和同库 SQL 均符合预期。正式入口退出 `0`。验收要求已同步至稳定规范，OpenSpec 已归档。[固定输入与验收点](r5-angular-user-role-edit-plan.md) · [稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-两代公开包可通过固定-angular-模板对照用户角色编辑) · [OpenSpec 归档任务](../../openspec/changes/archive/2026-11-27-validate-r5-angular-user-role-edit/tasks.md)

## 输入和进程身份

- 主仓基线 `06fab1d15733c2972f7d8a0ffe31f4d82ea39398`，模板 `2e9536872673a7ff1986a19e798c51684d16afe5`，框架 gitlink `7933e71f5646d2447af3502ecbea9a3f1aba8184`。实测环境为 macOS 27.2.1（26B131）ARM64、.NET SDK `10.0.404`、Python `3.12.14`、pymssql `2.3.13`、Playwright `1.59.0`、Chrome `158.0.8127.37`。四个入口的目标为 `net10.0`，实际 .NET、ASP.NET Core 和 EF Core SQL Server Provider 均为 `10.0.15`。
- 使用同一份准备报告核验四个封存的 Release 输出，报告 SHA-256 为 `c6c629df263afe0d8454aeea514b2b9c2688ab208d02ddfcc2d41576c0d0fe4b`。Web.Host 各核对 13 个维护包，Migrator 各核对 10 个。重新验算对应包图，只见三份映射包、对应 DLL 资产与四条精确依赖边的差异。两侧 Host 在默认加载上下文实测从各自 Release 输出加载适配器和唯一映射引擎，Collection 均见于输出。两侧 Migrator 输出含三份映射 DLL，迁移期间均未加载它们。[公开准备及运行身份](r5-template-user-role-update.md#固定输入与运行身份)
- 每侧实跑 30 条迁移，Migrator 各记录 33 条连接事件。两侧均在本库 `Default` 租户中创建无业务授权的 `du-role-a`、`du-role-b`，对应角色 ID 为 3、4。目标用户 `durolecheck` 的 ID 为 3，初态均为 `Seed User` 且仅 A。每个新浏览器会话经模板选择租户并使用管理员登录，核对租户 ID 1、管理员 ID 2、`Pages.Users`、CORS 及本库唯一新增的成功登录记录。

| 装载的公开版本 | 本轮 PID 与端口 | 独立 SQL 库名、ID、GUID |
| --- | --- | --- |
| R4 | Migrator `76326`，Host `76414` / `52361`，Chrome `76510`，前端端口 `52362` | `r5_role_97ac72046016bf3d_r4`，`5`，`18A0B182-AE33-4AE2-BA00-886BBE41EE27` |
| R5 | Migrator `76614`，Host `76732` / `52371`，Chrome `76821`，前端端口 `52372` | `r5_role_97ac72046016bf3d_r5`，`6`，`EA9F665D-44E0-4E05-8558-99FBE99DF3E1` |

实际 SQL 实例为 `r5-role-97ac72046016bf3d`，Developer `16.0.4236.2`。浏览器服务副本均匹配冻结清单的 1,193 个路径，各自只覆盖应用配置里的两个环回 URL。两侧实际入口响应均为 HTTP 200，`index.html` 与 `main-PZGEMKYC.js` 响应体摘要分别为 `eb6d4967b6520d53928c759b849e553f77d9073d459973f23983aa0fd5bdb065`、`f76c6a23c8417503365d36f645f0adb6c6fef806f80b565d64067cc75d5855b6`。首次打开编辑窗口前，两侧浏览器从各自前端收到 `chunk-PPIUHYWS.js` HTTP 200，SHA-256 均为 `67ec845c7dea216c0c54c8a0012a2518baf4247ca5f2c7e587aa4721a39f4e4a`，与冻结清单一致。[前端冻结清单身份](r5-angular-user-role-edit-plan.md#固定输入)

## 分步结果

| 每侧步骤 | 浏览器实际 PUT `roleNames` | 保存触发的列表响应及实际唯一数据行 `fullName` | 重开勾选和同库直接关系 |
| --- | --- | --- | --- |
| 保留 | `["DU-ROLE-A"]` | `Angular Keep User` | 仅 A，1 行 |
| 替换 | `["DU-ROLE-B"]` | `Angular Replace User` | 仅 B，1 行 |
| 清空 | `[]` | `Angular Clear User` | 全部未勾选，0 行，A、B 定义仍在 |

每次保存返回 HTTP 200 和成功的 ABP 回执。该次回执之后，新发的 `GET User/GetAll` 带 `Keyword=durolecheck`，`totalCount` 为 1，唯一条目的 ID 和页面用户名属于目标用户。窗口关闭并显示本步新全名后，从该行重开，随后发出独立的 `User/Get` 和 `User/GetRoles`，并逐项核对 Admin、A、B 的实际选项与勾选。

两侧共 14 次浏览器目标请求（初态详情、逐步 PUT 与重开详情）分别关联唯一请求标记、对应 Host PID、目标用户 ID、EF 业务命令及其实测数据库身份。各步独立 SQL 以同库实测身份读取目标用户、完整直接角色关系及 A、B 角色定义。用户名、姓氏、邮件和激活状态保持种子值，姓名按本步输入更新。

R4 的 SQL `datetime2(7)` 原值为 `2026-11-27T19:24:06.5637530`，R5 为 `2026-11-27T19:24:19.6387880`。各自 PUT 回执和 GET 的原始时间表示，与 SQL 的七位小数值一致。浏览器实测时区为 `Asia/Shanghai`，Moment 代理分别发送 `2026-11-27T11:24:06.563Z` 和 `2026-11-27T11:24:19.638Z`，创建时间仍保留各库的七位小数原值。[窗口、代理和 SQL 验收口径](r5-angular-user-role-edit-plan.md#页面动作与预期)

## 失败路径与停止边界

实际入口分别拒绝错误的公开准备报告摘要和冻结 Angular 清单摘要，两次退出 `1`，均未启动进程或容器。定向测试另外核对编辑脚本响应缺失及实收响应体摘要错误。

使用上述正式报告的脱敏证据跑过一次无注入回放和 15 个负向回放。无注入回放退出 `0`，负向回放入口均退出 `1`。回放报告保留每侧的停止位置、SQL 诊断与各阶段 PUT 次数。

| 回放变化 | 判定和写入边界 |
| --- | --- |
| 一侧或两侧详情角色均偏离，或一侧列表响应、实际行、关键词偏离 | 单侧或两侧各自失败。失败侧没有第二次 PUT。 |
| 业务连接错库、详情请求缺失连接或独立 SQL 错库 | 该侧输入不可比，原 PUT 各发送一次。 |
| PUT 业务库错配且缺回执 | 该侧输入不可比，保留已取得的请求证据，本侧诊断 SQL 标为未执行。另一侧在下一次写入前通过独立 SQL 复核其起点。 |
| PUT 业务库可信、缺回执且本侧独立 SQL 返回错库 | 执行一次诊断 SQL，依据实际读回的库身份将该侧判为不可比。 |
| PUT 业务库可信且仅屏蔽成功回执 | 该侧失败。执行一次独立 SQL 诊断并核对通过，该侧停止写入。 |
| PUT 可能写到另一侧，另一侧在首步或成功保留 A 后通过 SQL 跟起点对账 | 另一侧通过门控后继续，触发门控的侧停止。 |
| 另一侧起点偏离或无法建立查询连接 | 另一侧输入不可比。该步及后续依赖写入均未执行。 |

## 复跑与证据

从主仓根目录运行，使用安装了 `pymssql` 和 `playwright` 的 Python 环境、本机 Chrome、固定 .NET 安装和本机 Docker。准备目录缺失时按公开准备步骤从独立空缓存重建并独立登记报告摘要。`WORK` 为新建证据父目录，四个示例端口应为空闲环回端口。[公开准备入口](r5-template-user-role-update-plan.md#复跑公开模板准备) · [冻结前端来源](r5-angular-user-role-edit-plan.md#固定输入)

```sh
docker pull --platform linux/amd64 \
  mcr.microsoft.com/mssql/server@sha256:0ec7739e1c5ec2f57861facbe1f2b74f1d3e147c7c97edf91eeea920c5944d9c

python -B eng/r5_angular_role_edit.py \
  --prepared .git/validate-r5-template-user-role-update/preparation/formal \
  --report-sha256 c6c629df263afe0d8454aeea514b2b9c2688ab208d02ddfcc2d41576c0d0fe4b \
  --chrome '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  --r4-port 52361 --r4-frontend-port 52362 --r5-port 52371 --r5-frontend-port 52372 \
  --output "$WORK/formal"

python3 -B eng/tests/test_r5_angular_role_edit.py --replay "$WORK/formal/report.json" \
  --case other-business-connection --output "$WORK/other-business-connection.json"
```

冻结生产构建默认读取原版返修轮，允许用 `--angular-source` 指向同一已登记实物的单独路径，仍核对固定清单文件和完整内容。封存 Development Host 的静态资产清单引用上一轮已清理的 `obj`。本轮传入 API Host 专用的空静态资产清单，冻结 Angular 页面由各侧独立的环回静态服务提供。两个 Host 的实际 CORS 和运行程序集在报告中单独核对。

回放的 `--output` 必须指向新文件。已有文件、符号链接和硬链接会被拒绝，入口退出 `2`，已有内容保留。

正式报告在 `.git/validate-r5-angular-user-role-edit/implementation-01/formal-v7/report.json`，SHA-256 为 `85d3e3107e834c6c9a5b966430219c5096d591d9b35721e2c184a15fc77fe417`。报告保留逐侧服务清单、实际 HTTP、窗口读数和 SQL 状态。逐侧 `user-requests.jsonl`、`Migrator-target.jsonl` 与程序集 JSON 保留原始观测，`sql-commands.json` 记录独立 SQL 查询及退出结果。同级保留命令、退出码、回放以及前序尝试。前四次分别定位历史静态清单路径、Playwright 监听回调、导航后读取旧资源响应体和观测标记导致 Playwright 请求 URL 更新的问题。第五轮两侧通过。第六轮 R5 租户选择响应等待超时，该侧未尝试编辑，R4 三步通过。最后一轮保留握手响应顺序，使用两座新空库完成两侧验收。

四个 .NET 进程均退出 `0`，两个 Chrome 进程和静态服务均终止，环回端口释放，本轮容器已移除且未产生匿名卷。封存输出和源前端复核一致。75 项 Python 回归、39 个本地文档链接和 OpenSpec 全仓严格校验 16 项均通过。本轮覆盖上述平台和组合的直接角色编辑。组织单元继承、最终权限、其他平台与 Provider，以及发行和部署使用各自的证据范围。

复审修订沿用 V7 正式实测，使用当前判定重跑无注入及 15 项负向回放。V7 报告的 `profileSources` 记录正式运行源码，修订回放的 `formalReportSha256` 和 `replaySources` 分别记录 V7 证据与当前判定源码。77 项 Python 回归、39 个本地链接及 OpenSpec 严格校验 16 项通过。修订前后报告、资源终态复查及候选文件清单位于 `.git/validate-r5-angular-user-role-edit/review-fix-01/`。
