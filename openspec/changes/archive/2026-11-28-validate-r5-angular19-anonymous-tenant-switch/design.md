# Design

## Context

`TenantChangeComponent` 从 Session 租户构造当前租户文案，并为弹窗预填已有的租户名。`TenantChangeDialogComponent` 在非空输入取得 `Available` 后设置 Cookie 并调用 `location.reload()`，空输入则清除 Cookie、关闭弹窗并重载。`SessionAppService` 分别按租户 ID 和用户 ID 是否存在填充两个对象，匿名租户阶段可以有租户对象。[租户组件](../../../../module-zero-core-template/angular/src/account/tenant/) · [Session 服务](../../../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.Application/Sessions/SessionAppService.cs) · [提案](proposal.md)

## Goals / Non-Goals

提供可从普通克隆执行的验收入口，使用真实用户操作及其后续请求验证固定组合的匿名切换。复用可共享的输入、运行资源和观测方法，保持 BOOT-01 在不选租户的单文档首次启动验收语义。

## Decisions

### 1. 固定输入与共享种子

| 输入 | 核验 |
| --- | --- |
| 双包 production | 复用封存 tarball、冻结实装、同次构建统计、全局脚本读取和 1193 项目录清单，沿用修正后的 `verify_pair`。登记实际摘要、封存标记、锁和候选 chunk 来源。同一版本号或文件名不足以识别输入。缺项按普通克隆指南重建并按已登记规则核对。 |
| 全公开冻结 production | 沿用公开前端冻结清单及原始字节校验，缺项按公开准备指南重建。两侧分别核对实收 index、入口和全局脚本，双包侧另核对实际候选 chunk。 |
| R5 后端 | 按独立登记的准备报告 SHA-256 核验固定模板的公开 `v10.5.2` Release Web.Host 和 Migrator。记录同一实际 Host 的 PID、入口及已加载组件摘要、运行时和数据库目标。沿用已登记的运行组合及公开准备方法。 |

[双包复跑](../../../../docs/maintenance/r5-angular19-package-pair.md#从普通克隆复跑) · [封存身份复审](../../../../docs/maintenance/r5-angular19-anonymous-bootstrap.md#封存归档身份复审) · [公开前端准备](../../../../docs/maintenance/r5-public-angular-rebuild.md#准备和离线核验) · [公开后端准备](../../../../docs/maintenance/r5-template-user-role-update-plan.md#复跑公开模板准备)

用标准 Migrator 在本轮独占 SQL Server 实例准备专用空库。读回实际实例、库名、数据库 ID、GUID、标准迁移和唯一已启用、未删除、使用共享库的 `Default` 种子。登记 SQL 实读的 `Id`、`TenancyName`、`Name`，作为两侧独立判定的共同预期。正式运行前核对 Migrator 和 Host 的实际连接目标，运行后再读回库与租户种子。两份环回静态服务副本仅覆盖本轮应用配置中的两个 URL。采用等价 SPA 回退和缓存策略，Host 的 CORS 允许各侧实际来源。前端地址使用无租户子域名、无租户查询参数的环回地址，使弹窗成为租户选择入口。[既有验收入口](../../../../eng/r5_angular_anonymous_bootstrap.py) · [SQL 种子读回](../../../../eng/r3_template_sql.py) · [模板初始化](../../../../module-zero-core-template/angular/src/app-initializer.ts)

### 2. 用实际文档关联操作与阶段

单侧只创建一个此前无认证、租户和语言状态的 Chrome 上下文。两侧的 Chrome 版本、语言、时区和服务条件相同。从根路径打开同侧 production 页面，用 `tenant-change` 中的真实链接打开弹窗，按可见 `input[name=tenancyName]` 和弹窗表单提交按钮操作。只进行首次根路径导航，两个后续重载均由页面保存动作触发。复用已有的来源、路径和方法匹配、业务成功响应及 CORS 检查。既有 `browser_session` 包含登录，本入口只复用独立观测方法。[浏览器观测方法](../../../../eng/r3_template_browser.py)

用主框架的 `loaderId` 或等价文档身份区分三个主文档，按 `requestId` 或等价请求身份配对每条请求与实收响应。首个文档须从根路径直接取得 HTTP 200，再在同一文档进入登录路由。两次保存各触发一次真实主文档重载，分别取得有新文档身份的该侧 production index，并最终到达该侧 `/account/login`。重载前后 URL 可以相同。按请求发出时所属的文档分别核对应用配置 → GetAll → Session 各一次、实收响应顺序、静态字节与脚本来源。跨文档按 URL 或路径补齐一律失败，包括用内容完全相同的初始宿主 GetAll 补返回宿主的回执。自动化仅操作模板可见控件。

从首次导航前连续观测至返回宿主的表单和两条后端 GET 成功回执均齐备。以请求发出事件统计 `IsTenantAvailable` POST，每侧全程恰好一次，由非空保存触发，且其业务成功响应先于租户文档重载。额外 POST 一经发出即判失败，包括清空时发出后被取消、失败或无响应的请求。CORS 预检 `OPTIONS` 单列，其数量允许受 Chrome 预检缓存影响。

| 阶段 | 操作及界面 | 浏览器和后端 |
| --- | --- | --- |
| 初始宿主 | 空登录表单、当前租户未选择，打开弹窗可见空输入 | `Abp-TenantId` Cookie 不存在，GetAll 为 Host（2）且无租户 ID，Session 无租户。 |
| 已选租户 | 保存 SQL 实读的 `Default`。重载后空登录表单可见，当前租户的 `strong` 显示 `TenancyName`，外层 `title` 对应 `Name`。重新打开弹窗输入已预填 `TenancyName` | 向登记 Host 发出的选择请求的 JSON `tenancyName` 匹配种子，实收 HTTP 200、业务成功、`Available`（1）及种子 ID。重载后租户 Cookie 匹配种子 ID，GetAll 为 Tenant（1）且同 ID，Session 的 `tenant.id`、`tenancyName`、`name` 与 SQL 一致。 |
| 返回宿主 | 清空预填输入并保存。重载后空登录表单和未选择文案重新可见 | 租户 Cookie 已移除，GetAll 回到 Host 且无租户 ID，Session 无租户。 |

三条初始化 GET 分别观察实际 `Abp.TenantId` 和 `Abp-TenantId` 的存在及值状态，记录缺省、无有效值、匹配种子或不匹配。固定模板为应用配置和 GetAll 显式设置点号头，Session 代理生成的请求仅声明 `Accept`。适配器（公开包源码 `afbd23e`）按租户 Cookie 补充连字符头。

| 请求头 | 初始宿主、返回宿主 | 已选租户 |
| --- | --- | --- |
| `Abp.TenantId` | 应用配置和 GetAll 按模板发送无有效租户的值，含字面量 `"null"`。Session 可缺省，出现时须无有效值。 | 应用配置和 GetAll 须匹配种子 ID。Session 可缺省，出现时须匹配种子 ID。 |
| `Abp-TenantId` | 三条 GET 均无有效租户，允许缺省。 | 三条 GET 均须实际携带种子 ID。任一请求缺头或值错误均失败，即使另一头、Cookie 和回包正确。 |

分别核对当前前端作用域的租户 Cookie、请求中的认证标记和实收响应的匿名身份。种子租户 Cookie 和正确租户头可与匿名身份同时成立。全程须无认证凭据、模拟身份及登录提交。Session 和 GetAll 中无身份的字段可为 JSON `null` 或省略，空对象表示无 Session 租户时判失败。按各阶段实际本地化源 `AbpProjectName` 的 `CurrentTenant`、`NotSelected`、`Change` 与登录文案检查可见文本，弹窗的 `ChangeTenant`、`TenancyName`、`LeaveEmptyToSwitchToHost` 和 `Save` 依打开时对应阶段核对。[`IsTenantAvailable` 服务](../../../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.Application/Authorization/Accounts/AccountAppService.cs) · [租户 Cookie 实现](../../../../aspnetboilerplate/src/Abp.Web.Resources/Abp/Framework/scripts/abp.js)

### 3. 独立判定与收尾

对两侧各自核验阶段和种子，满足前提的一侧独立运行。共同 Host 或库身份不明时两侧均输入受阻。某阶段失败时停止该侧依赖步骤并保留已取得的证据。两侧均通过后，比较对应三阶段的匿名身份、有效租户、切换顺序及请求次数、实际当前语言与界面文案、应用元数据和配置字段。监听地址、构建产物摘要按侧核对。报告记录命令和退出码、固定输入、运行身份和 SQL 前后读回、各阶段直接观测、差异、未执行项及清理状态。证据只落白名单字段，包括文档和请求标识、事件顺序、请求来源、方法及路径、HTTP／业务结果、两个租户头各自的存在及值状态、种子 ID、租户 Cookie 存在及匹配状态、认证标记有无、文案和摘要。认证值、令牌、连接串、完整 Cookie、浏览器存储及未过滤网络日志均排除。

成功及异常均收尾退出两侧上下文、Chrome、本轮静态服务、Host、Migrator 和专用 SQL 库及容器，复查本轮监听、卷和临时服务路径及原始输入摘要，保留脱敏证据。在普通克隆中记录复跑所需输入、实测命令及结果。对应场景见[增量规范](specs/template-maintenance-package-consumption/spec.md)。

## Risks / Trade-offs

- 环回端口不同仍可能共享同一主机的浏览器 Cookie 作用域。两侧以新上下文隔离，同一侧则保留 Cookie 的真实生命周期。
- URL 和本地化文字可能在切换过程中保持相同。用触发顺序、文档身份、真实响应、Cookie 及可见租户状态联合验证。在每阶段必要回执齐备后截取证据，允许无关字体资源仍在加载。
