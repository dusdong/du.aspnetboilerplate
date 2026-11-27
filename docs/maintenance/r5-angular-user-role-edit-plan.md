# R5 固定 Angular 用户角色编辑对照计划

2026-11-27 制定，主仓基线为 `06fab1d15733c2972f7d8a0ffe31f4d82ea39398`。验收使用同一冻结 Angular production 构建，在公开 R4 和 R5 上分别用真实用户编辑窗口验证直接角色的保留、替换和清空。2026-11-27 两侧均通过，验收要求已同步至稳定规范，OpenSpec 已归档。[实测结果与复跑](r5-angular-user-role-edit.md) · [归档提案](../../openspec/changes/archive/2026-11-27-validate-r5-angular-user-role-edit/proposal.md) · [技术设计](../../openspec/changes/archive/2026-11-27-validate-r5-angular-user-role-edit/design.md) · [归档任务](../../openspec/changes/archive/2026-11-27-validate-r5-angular-user-role-edit/tasks.md)

## 上一轮复核

- GitHub 已交付基线提交，`verify-r0` 运行成功。20 个候选文件与提交逐一匹配。稳定规范新增一条要求、八个场景，归档任务 7/7。复核重跑 74 项 Python 回归通过，选题前稳定规范和归档任务严格校验分别为 15/15 和 25/25。[交付提交](https://github.com/dusdong/du.aspnetboilerplate/commit/06fab1d15733c2972f7d8a0ffe31f4d82ea39398) · [CI 运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45980583486) · [归档任务](../../openspec/changes/archive/2026-11-27-validate-r5-template-user-role-update/tasks.md)
- 离线回读 `formal-v5` 和准备报告，复核两侧独立库 GUID、四份封存入口以及每侧三步真实 PUT、独立 GET 和 SQL。上轮输入为显式 `null`、仅含小写 `du-role-b` 的数组、空数组，分别保留 A、改为 B、清空，普通字段按输入更新，创建时间保持各侧原值。本次复核沿用原正式运行证据，未启动数据库。[上轮实测及原报告摘要](r5-template-user-role-update.md)
- 54 个登记的清理目标均已缺失，原收尾记录显示 `du -sk` 减少 `954368 KiB`（932 MiB）。四份封存入口仍可核对，48 项历史链接检查是原收尾记录。

## 固定输入

| 项目 | 验收输入 |
| --- | --- |
| 模板与平台 | `module-zero-core-template` 提交 `2e9536872673a7ff1986a19e798c51684d16afe5`，macOS ARM64，SDK `10.0.404`，`net10.0`。实际 .NET、ASP.NET Core 和 EF Core SQL Server Provider 均为 `10.0.15`。沿用已登记镜像的 SQL Server Developer `16.0.4236.2`。 |
| 公开后端 | R4 `v10.5.1` 的 `Du.Abp.AutoMapper`、`Du.AutoMapper`、`Du.AutoMapper.Collection` 分别为 `10.5.1`、`14.0.0`、`11.0.0`，R5 `v10.5.2` 分别为 `10.5.2`、`14.0.1`、`11.0.1`。沿用四份封存 Release 输出，Web.Host 各核对 13 个、Migrator 各核对 10 个维护包，对应图只允许已登记的三包、资产与四条依赖边差异。 |
| 前端与会话 | 原版返修轮 1193 文件的 Angular production 构建，同一实测 Chromium 版本加两个独立会话。各侧有独立环回前端地址和 Host 地址。 |
| 库与种子 | 同一专用 SQL Server 实例内两座空库，各由对应 Migrator 迁移并核对 30 条迁移。每侧通过现有应用种子创建 `Default` 租户下两枚无业务授权的普通角色和一个初始仅有 A 的普通用户。浏览器由该侧授权管理员操作。 |

封存准备目录为 `.git/validate-r5-template-user-role-update/preparation/formal/`，报告 SHA-256 为 `c6c629df263afe0d8454aeea514b2b9c2688ab208d02ddfcc2d41576c0d0fe4b`。用既有 `r5_template_role_prepare.py verify` 核对报告和四份输出。封存实物缺失时，沿公开准备入口从独立空缓存重建并独立登记及校验新报告摘要。运行时核对实际 Host 和 Migrator 进程及加载证据。[公开准备命令](r5-template-user-role-update-plan.md#复跑公开模板准备) · [SQL 镜像与复跑条件](r5-template-user-role-update.md#复跑与回读)

Angular 原件为 `.git/r3-template-runtime/revision-1/runs/r3-template-runtime-89igcw5r/` 下的 `angular-production-files.json` 和 `source/angular/dist/browser/`。清单文件字节的 SHA-256 为 `99a2520978f5917fdc98545dc043b90ff5f9f2ed83872b52dbb8e273fa71c12b`，清单内部整表 `sha256` 为 `59203802dd274be9c00c041d1529238d72bd7ddc914a8f84224fbd84923bce37`。核验 1193 个路径和逐文件摘要后，各侧仅在静态服务副本的 `assets/appconfig.production.json` 覆盖 `remoteServiceBaseUrl`、`appBaseUrl`，Host 的 `App:CorsOrigins` 允许实际前端 origin。记录服务副本清单、地址及浏览器实际加载的 `index.html`、`main-PZGEMKYC.js` 与配置。各侧从首次导航起监听该侧前端的资源响应，首次编辑前取得含角色编辑逻辑的 `chunk-PPIUHYWS.js`。记录实际 URL 和成功响应体的 SHA-256，并与冻结清单同名条目的 `67ec845c7dea216c0c54c8a0012a2518baf4247ca5f2c7e587aa4721a39f4e4a` 对账。[Angular 冻结和端口复验](r3-template-net9-packages.md#运行复验) · [清单文件摘要登记](../../eng/r3_template_net9_runtime.py)

## 页面动作与预期

编辑窗口读取 `User/Get` 与 `User/GetRoles`，以 `normalizedName` 管理勾选，标签显示 `name`。保存总会生成完整数组并经代理提交 `PUT User/Update`。用户服务映射普通字段后处理角色数组，返回当前标准化角色名。`SetRolesAsync` 可能移除再补加同一角色，验收以最终业务角色集合为准，关联行主键可作为观察记录。[窗口逻辑](../../module-zero-core-template/angular/src/app/users/edit-user/edit-user-dialog.component.ts) · [窗口模板](../../module-zero-core-template/angular/src/app/users/edit-user/edit-user-dialog.component.html) · [保存后列表刷新](../../module-zero-core-template/angular/src/app/users/users.component.ts) · [HTTP 代理](../../module-zero-core-template/angular/src/shared/service-proxies/service-proxies.ts) · [用户服务](../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.Application/Users/UserAppService.cs) · [角色管理器](../../aspnetboilerplate/src/Abp.ZeroCore/Authorization/Users/AbpUserManager.cs)

各侧以授权管理员经模板页面选中 `Default` 并登录。核对服务端会话、实际权限、API 来源与 CORS。从用户列表搜索唯一的种子账号 `durolecheck`，打开编辑，核对 `Get`、`GetRoles`、全体勾选、独立 SQL，确认 `Name` 初始为 `Seed`、仅 `du-role-a`（`DU-ROLE-A`）勾选，且 `du-role-b`（`DU-ROLE-B`）可选。记录该侧管理员、租户、用户、角色 ID 与数据库实例、库名、ID、GUID。[既有浏览器登录及搜索](../../eng/r3_template_browser.py) · [既有种子与 SQL 读回](../../eng/r5_template_role_update.py)

| 步骤 | 在窗口执行的动作 | 实发 `roleNames` | 重开窗口和 SQL 的直接角色 |
| --- | --- | --- | --- |
| 保留 | `Name` 改为 `Angular Keep`，勾选保持原样，点击保存 | `["DU-ROLE-A"]` | 仅 A |
| 替换 | `Name` 改为 `Angular Replace`，取消 A 并勾选 B，点击保存 | `["DU-ROLE-B"]` | 仅 B |
| 清空 | `Name` 改为 `Angular Clear`，取消 B 并确认全未勾选，点击保存 | `[]` | 无直接关联，A、B 角色定义仍在 |

每步核对页面实发的目标 ID、姓名、完整数组及成功回执。在点击保存前监听本侧 Host，核对本次保存触发的 `GET User/GetAll` 携带 `Keyword=durolecheck`，成功响应的 `totalCount` 为 1，`items` 仅含本侧目标用户，ID 正确。响应的 `fullName` 与列表唯一数据行显示的全名逐步为 `Angular Keep User`、`Angular Replace User`、`Angular Clear User`。待窗口关闭且该行显示账号 `durolecheck` 和本步新全名，从该行打开同一用户，读取新发的 `GET User/Get`、`GET User/GetRoles`，对照姓名、角色及全体实际勾选，留存脱敏的请求和响应。PUT 及重开的用户 GET 关联到该侧实际 Host 和业务库连接，GetRoles 关联到该侧会话与服务响应。可复用已有测试侧请求标记或等价关联，业务参数、请求体和响应原样流转。[现有请求观测](../../eng/r3-template-observer/RoleRequestObserver.cs)

每步经独立只读 SQL 在同库核对用户字段及 `AbpUserRoles` 的全量直接关系。`Name` 取该步新值，`UserName`、`Surname`、`EmailAddress`、`IsActive` 保持各侧种子值。创建时间按 SQL `datetime2(7)` 核对各库原值，与原始服务端回执和 GET 对账。单独记载浏览器代理 `Moment.toISOString()` 的 UTC 转换和毫秒精度。`fullName` 按服务端派生值读取。每步通过才使用重开的窗口进入下一步。

## 通过与停止条件

- 两侧分别完成三次保存，且输入可比、实际载荷、回执、列表查询与渲染、重新打开、同库 SQL 全部符合预期时，登记本组合通过。
- 输入、实收编辑脚本或会话握手无法核实，该侧输入不可比。握手通过后，每次已发出的 PUT 和详情 GET 仍须取得目标用户对应的业务连接身份。缺少该身份，或业务连接、独立 SQL 读回的库身份失配，都优先判该侧不可比，包括同时缺失回执的情况。
- 若 PUT 可能写入另一侧库，另一侧在下次编辑写入前，用独立只读 SQL 核实库身份，并将目标用户字段、原创建时间和全部直接角色与该侧本步预期起点对账。首步以登记的种子初态为准，后两步以上一步已通过的状态为准。相符才继续，失配或无法核实则该侧也不可比，停止后续写入。
- 身份可信时出现业务证据缺失或结果偏差，判阶段失败。缺 PUT 回执且该请求的业务库身份已核实时，可进行本侧只读诊断，即使数据符合预期仍记失败。若该 PUT 的业务库错配或无法核实，本侧诊断 SQL 标为未执行，保留已取得的请求证据，并按上一条门控另一侧写入。记录该侧、步骤、实测和后续未执行项，停止该侧写入，已发送的 PUT 不重发。满足前提的另一侧独立执行，共同前提缺失则结束本次对照。
- 运行后登记环境、证据摘要和资源终态，复核封存输入，清理本轮专用进程和容器。结果范围限于本组合与直接角色编辑。组织单元继承、最终权限、其他平台和 Provider、发行及部署沿用各自证据范围。[稳定规范中的验收要求](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-两代公开包可通过固定-angular-模板对照用户角色编辑)
