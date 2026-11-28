## ADDED Requirements

### Requirement: 固定 Angular 19 模板可对照双包候选的匿名租户切换

验收 SHALL 使用已核验的固定 Angular `19.2.1` 双包候选和全公开冻结 production 前端，在同一个公开 `v10.5.2` Web.Host 及专用 SQL Server 新库上对照匿名租户切换。每侧 SHALL 从独立新 Chrome 上下文出发，在同一页面和上下文内通过真实租户弹窗走完宿主、已启用的 `Default`、返回宿主。

#### Scenario: 首次访问时处于匿名宿主

- **WHEN** 该侧全新上下文从登记前端根路径直接取得本侧 production 主文档并在同一文档内进入登录页
- **THEN** 可见空登录表单与本地化的当前租户未选择状态，打开租户弹窗时租户名为空。浏览器没有 `Abp-TenantId` Cookie。该文档的实际 `GetAll` 报告宿主侧且无租户，实际 Session 响应无租户。提交选择前未发出租户可用性 POST

#### Scenario: 在真实弹窗选中已启用的 Default

- **WHEN** 在该侧初始弹窗输入 SQL 读回的种子租户名 `Default` 并保存
- **THEN** 浏览器向登记 Host 发出一次 `POST /api/services/app/Account/IsTenantAvailable`。实收业务成功响应的状态为 `Available`，租户 ID 等于种子 ID。随后发生一次真正的主文档重载，新文档采用同侧 production 产物，最终路由为该侧 `/account/login`，浏览器租户 Cookie 有效值等于种子 ID
- **AND** 新文档的实际 `GetAll` 报告租户侧及该 ID，实际 Session 响应的租户 ID、租户名和显示名等于种子。空登录表单仍可见，当前租户展示相同的租户名及显示名。再次打开真实弹窗时输入框已预填该租户名

#### Scenario: 清空预填租户名并返回匿名宿主

- **WHEN** 在该侧预填弹窗清空租户名并保存
- **THEN** 该操作及随后初始化未发出租户可用性 POST，浏览器又发生一次真正的主文档重载，仍采用同侧 production 产物，最终路由为该侧 `/account/login`。浏览器租户 Cookie 已移除，该文档的实际 `GetAll` 恢复宿主侧且无租户，实际 Session 响应无租户。空登录表单与本地化的当前租户未选择状态重新可见

#### Scenario: 各阶段的网络证据对应实际文档和匿名身份

- **WHEN** 每侧初始化首个主文档和两个重载文档
- **THEN** 用主框架 `loaderId` 或等价身份区分三个主文档，用 `requestId` 或等价身份配对请求及实收响应。重载前后 URL 可以相同。每个文档按顺序取得本侧应用配置和登记 Host 的实际 `GET /AbpUserConfiguration/GetAll`、`GET /api/services/app/Session/GetCurrentLoginInformations` 成功响应，各一次。按请求发出时所属文档判定，即使 URL 或响应内容相同，跨文档补齐仍失败
- **AND** 从首次导航前连续统计请求发出事件，直到返回宿主的表单和两条后端 GET 成功回执均齐备。每侧全程仅非空选择时发出一次租户可用性 POST，该请求的业务成功响应先于重载。预检 `OPTIONS` 单列。额外发出 POST 即失败，响应取消、失败或缺失时亦然
- **AND** 对三条 GET 分别记录 `Abp.TenantId` 和 `Abp-TenantId` 的存在及值状态。宿主阶段两头均无有效租户，应用配置和 GetAll 的点号头允许字面量 `"null"`，连字符头允许缺省。已选租户阶段应用配置和 GetAll 的点号头及三条 GET 的连字符头均须匹配 SQL 种子 ID，该阶段连字符头缺失或错误时判失败，即使另一头、Cookie 和响应正确。Session 点号头允许缺省，出现时须符合所在阶段
- **AND** 独立判定租户 Cookie 和认证状态。各阶段 `GetAll` 无用户及模拟身份，Session 无用户。保留响应字段的 `null` 或省略形式。界面文案按本阶段 `GetAll` 的实际本地化值核对。全程无登录提交、鉴权凭据、角色操作、SignalR 连接或未捕获的页面异常

#### Scenario: 单侧偏离或两侧不可比

- **WHEN** 输入或共享身份无法核实、任一侧阶段缺失或偏离、两侧结果不同，或者专用资源收尾无证据
- **THEN** 记录受影响侧、阶段、原因、可用回执及未执行项。满足自身及共享前提的另一侧独立运行。整体通过须有两侧独立通过、对应阶段语义一致及资源终态核验。报告保留输入、各阶段白名单观测和对照结果，适用范围为本次固定组合的匿名切换
