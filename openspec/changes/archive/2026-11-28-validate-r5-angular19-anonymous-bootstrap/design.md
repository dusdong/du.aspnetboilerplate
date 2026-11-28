# Design

## Context

双包报告提供候选来源、production 构建统计和最小页响应。V7 有真实浏览器和后端证据，但使用公开冻结前端并直接打开登录路由。本次对照观察根路径启动、匿名配置和会话初始化。[双包证据](../../../../docs/maintenance/r5-angular19-package-pair.md#实测结果) · [V7 证据](../../../../docs/maintenance/r5-angular-user-role-edit.md#复跑与证据)

## Goals / Non-Goals

为固定组合提供一条可从普通克隆执行的本机验证入口。通过条件覆盖同一次新页面启动中的产物加载、两条真实匿名 API、路由及其可见结果。验收停在登录表单可见。权限全集、设置全集、语言切换、登录行为和其后的业务各有独立用例。

## Decisions

### 1. 固定两侧输入

| 输入 | 核验与缺项处理 |
| --- | --- |
| 双包前端 | 优先复用双包报告所登记的封存 tarball、实装与同次构建回执、统计和原始 production 目录。锁及来源链核对到 `a8ca4b37800565357f201e83d19333a9a7008887` 的 `abp-ng2-module 12.1.0`，框架 `7933e71f5646d2447af3502ecbea9a3f1aba8184` 与包装 `fb79b7d44bc9dfce0ae600c8170961f182b05e76` 的 `abp-web-resources 6.1.0`。双包报告列有两份归档的 SHA-256、SRI、锁摘要及构建工具。验收输入包括同次构建的 `stats.json` 或足以证明具体 chunk 来自实装候选 FESM 的等效证据。 |
| 全公开前端 | 优先复用已登记的 1193 文件冻结件，经 `eng/r5_angular_prepare.py verify --angular-source` 或同一 `frozen_angular` 核验。缺失时用公开准备指南的 `prepare` 重建，再执行同一离线核验。公开清单的文件摘要为 `99a2520978f5917fdc98545dc043b90ff5f9f2ed83872b52dbb8e273fa71c12b`，整表摘要为 `59203802dd274be9c00c041d1529238d72bd7ddc914a8f84224fbd84923bce37`。 |
| 共用后端 | 使用模板 `2e9536872673a7ff1986a19e798c51684d16afe5` 的 R5 公开 `v10.5.2` Release Web.Host 和 Migrator。优先复用封存准备输出并用独立登记的报告 SHA-256 校验。普通克隆可按公开模板准备指南取得公开附件，从空缓存重建并登记报告摘要。可复用 `eng/r5_template_role_prepare.py` 的 `verify_prepared(..., only_release="r5")` 核对 R5；公开准备命令可能生成两代输出，运行阶段只启动 R5。 |

双包原始 production 清单格式为 `相对路径 → {bytes, sha256}`。从静态实物取 POSIX 相对路径、文件字节数和原字节 SHA-256，按路径排序，每个条目以制表符分隔三列并以 LF 结尾，UTF-8 编码。封存产物的该清单含 1193 项，整表 SHA-256 为 `b728ead007ff14397d4fe31bfbd160790ab5d7e8d33a22047bef0830c3af6955`。拒绝符号链接并校验全部路径、字节数和摘要。封存产物的候选适配器输出为 `chunk-N46DCMOX.js`，SHA-256 为 `1c93d0ac4d0337ff2cccb659140cb73e762c662ee90c9f3f1baa8e7e61363fa0`，同次统计记录候选 FESM 对该输出贡献 8985 字节。

双包封存输入缺失时按双包指南从普通克隆重取固定 Git 对象和依赖，复跑制包、冻结实装和 production 构建，登记归档、锁、工具、同次统计及产物的实际身份。重新制包若仅归档摘要不同，须按双包指南确认归档内部逐项一致并说明包装差异。重建产物须匹配上一段固定清单，且应取得两份包的消费来源。使用双包指南的公开观测代码直接取得九条全局脚本读取记录，核对同次构建器 PID、目录、相对与实际路径及原字节。输入无法取得或无法核实为登记组合时，记录发生阶段、具体差异并判双包侧输入受阻。历史 `.git` 证据可供取得已有实物，公开复跑无需它。候选侧不使用公开冻结清单来证明自身来源。[双包固定输入及复跑](../../../../docs/maintenance/r5-angular19-package-pair.md#从普通克隆复跑) · [公开前端准备与离线核验](../../../../docs/maintenance/r5-public-angular-rebuild.md#准备和离线核验) · [公开后端准备](../../../../docs/maintenance/r5-template-user-role-update-plan.md#复跑公开模板准备)

### 2. 共享一个实际 Host 和已准备的测试库

沿用公开准备所登记的 macOS ARM64、.NET SDK `10.0.404`、共享运行时和 EF Core SQL Server Provider `10.0.15`。在独占环回 SQL Server 实例内准备一个专用空库，采用模板 Migrator 的标准迁移和必要种子。记录实际 SQL 实例、库名、数据库 ID 和 GUID，核对迁移器实际连接、退出码、迁移状态，以及运行 Host 的连接目标。可复用 `eng/r5_template_role_update.py` 的准备、进程与身份观测做法，调用范围停在数据库和 Host 就绪；角色测试的业务种子及鉴权步骤不纳入本次。记录同一 Host PID 与入口文件摘要、实际监听地址、实际共享运行时和已加载的维护组件身份。匿名 Session 可能不发业务 SQL，使用已核验的 Host 连接目标与独立 SQL 读回建立库身份，无须为每个匿名 GET 强制制造 SQL 命令。[R5 运行组合](../../../../docs/maintenance/r5-template-user-role-update.md#固定输入与运行身份) · [现有运行入口](../../../../eng/r5_template_role_update.py)

为两侧建立环回静态服务副本。两侧共用相同 SPA 回退、缓存策略和 Host 配置。Host 的 CORS 同时允许两侧准确的环回来源，并保持固定 `Development` Host 的 API 静态资产配置。以 `serve_copy` 为例核对重写前后 JSON 与全部静态实物，仅 `assets/appconfig.production.json` 的 `appBaseUrl`、`remoteServiceBaseUrl` 取本轮地址。公开清单自身仍用 V7 的严格格式和身份校验；双包原始清单核验后可转换为服务副本检查所需的文件摘要映射。用两个全新、无 `storage_state` 的同版本 Chrome 上下文依次打开各自根路径，保持相同语言、时区与服务条件。保留同一 Host、库与两侧实际 CORS 响应的证据。运行停止在匿名表单可见，不填表单、不选择租户。服务可复用 `SpaHandler`；静态缺文件得到的 HTML 回退不能满足脚本摘要检查。[公开输入与服务副本](../../../../eng/r5_angular_role_edit.py) · [V7 服务条件](../../../../docs/maintenance/r5-angular-user-role-edit.md#复跑与证据)

### 3. 观察真实启动及其可见结果

监听器在导航前注册，记录页面未捕获异常、目标请求与实收响应、失败请求和导航。沿用 `eng/r3_template_browser.py` 的按来源、方法和路由匹配及响应体摘要做法。其 `browser_session` 会选择租户并登录，本次入口使用独立的匿名步骤。仅接受当前上下文在实际加载 `index.html` 后发出的请求，候选与对照分别读取各自入口引用和清单；静态响应体摘要匹配该侧实物。双包侧核对候选 chunk 和资源包进入的全局脚本，公开侧记录实际加载的入口、全局脚本及其摘要。真实页面不使用路由拦截注入、模拟 API、最小页或 V7 历史浏览器结果。[已有浏览器观测方式](../../../../eng/r3_template_browser.py)

| 观测 | 验收依据 |
| --- | --- |
| 应用配置 | `app-initializer.ts` 从 `assets/appconfig.production.json` 取得应用与服务 URL 以及 `localeMappings`。校验实际响应摘要与服务副本一致，URL 指向登记前后端，本轮地址之外的配置字段与原件一致。 |
| 用户配置 | 实际 `GET /AbpUserConfiguration/GetAll` 来自指定 Host，记录状态、允许的来源和成功包装。核对 `session` 中的 `userId`、`tenantId` 是 `null` 或按序列化契约省略，`multiTenancySide` 对应源码 `Host`，无模拟登录身份。记录 `clock.provider`、`localization.currentLanguage.name` 及源 `AbpProjectName` 的三个登录文案键。时钟支持多时区时保留初始化实际读取的 `timing.timeZoneInfo.iana.timeZoneId`。 |
| 当前登录信息 | `main.ts` 注册初始化器与拦截器。初始化器合并配置后调用 `app-session.service.ts`，由生成代理发出实际 `GET /api/services/app/Session/GetCurrentLoginInformations`。核对该响应成功包装及 `application` 实际所含的模板版本、发布日期和功能字典，并与固定 `SessionAppService.cs` 及 `ApplicationInfoDto` 契约对应。`user` 与 `tenant` 分别记录省略或显式 `null`，两种表示均表示匿名、无当前租户；空对象或实际身份不通过。 |
| 调用和路由 | 记录三个初始化 GET 各自的请求次数与先后顺序，CORS 预检单独识别。从根路径经 `root-routing.module.ts` 的 `/app/about` 路由规则，由 `AppRouteGuard` 根据匿名会话转到 `/account/login`。首个主文档请求必须直接从根路径取得 HTTP 200 和本侧 index 字节，随后在该文档内转到登录页。记录主文档请求、重定向链与最终 URL。服务端 302 送登录页或第二次加载主文档均判失败。按 Angular 前端导航判断最终路由，无需发出 /app/about 主文档请求。页面至少有一次真实启动，当前观测窗口内不得有重复初始化请求、缺失脚本或未捕获页面异常。 |
| 登录表单 | 以 `login.component.html` 的实际 `input[name=userNameOrEmailAddress]`、`input[type=password][name=password]` 及提交按钮为可见性断言。`LogIn` 对应标题与提交按钮，`UserNameOrEmail`、`Password` 对应两个占位文本。比较实际文字与该侧 `GetAll` 返回的 `localization.values.AbpProjectName`，保留语言和实际取值，勿用写死的英文替代。 |

初始化 GET 的记录包含服务来源、方法、路径、状态、顺序、CORS 及认证或租户标记是否出现。空租户请求头可由模板字符串化产生，应按实际契约判定有效租户是否存在。只记录需要比较的匿名状态、应用元数据、本地化及配置字段。不得把 Cookie、Authorization、`Set-Cookie`、令牌、连接串、原始响应全集、浏览器存储或无过滤的请求日志写入证据。观测窗口从导航开始，到表单可见及所需主文档、脚本和初始化回执到齐。采集时固定该窗口的事件快照。无关的字体或图片请求可以仍在进行。确认窗口内无认证提交、租户可用性查询、角色或 SignalR 协商／连接。按侧核对前端和 Host URL。跨侧比较同义的匿名身份、当前语言、三个登录文案、初始化配置字段及 application 元数据。两份白名单回执原样保留可接受的 `null`／省略区别。模板版本固定为 `9.3.0`，发布日期源于同一 Host 的固定模板程序集，只在本轮跨侧比较。[增量规范](specs/template-maintenance-package-consumption/spec.md)

### 4. 判定与收尾

逐侧记录通过、失败或输入受阻，并记明前置条件和未执行项。共享的 Host、库或运行身份无法核实时，两侧均为输入受阻。只有一侧的前端输入、环回监听或运行偏离时，在共同条件仍可核验的情况下执行另一侧。收尾统计本次实际绑定的监听。双侧均通过且可比才记整体通过。同样的异常仍分别记录。保留运行机器、源码及静态清单摘要、登记输入与命令回执、各侧白名单观测及终态，足以从结果定位到各自同次的浏览器和后端。确认用过的两个上下文、浏览器、静态服务、Host 和本轮专用库或容器按本轮建立范围关闭或清理，复核端口释放、原产物摘要及明示保留的脱敏证据。运行失败也走同一收尾。对照通过时只登记固定组合的匿名首次启动和有限配置消费结果。

## Risks / Trade-offs

- 公共 registry、字体响应或旧工具不再可用时，优先核验已有封存实物。缺项无法重建时记录证据缺口及实际失败阶段。
- 这两侧的入口文件名可能相同。分别校验来源、产物摘要与浏览器实收内容，才能证明每条结果对应当次指定输入。
- Host 数据及证据目录复用容易污染首访条件。使用独占库、独立的新浏览器上下文和新证据目录，原封存输入只读。V7 按原校验继续拒绝携带公开清单的双包产物。发行、分发参考和六个子模块各按其已登记入口维护。[V7 冻结校验记录](../../../../docs/maintenance/r5-angular19-package-pair.md#原始证据及边界) · [分发维护登记](../../../../docs/compatibility/angular-ecosystem.md#web-resources-分发维护登记)
