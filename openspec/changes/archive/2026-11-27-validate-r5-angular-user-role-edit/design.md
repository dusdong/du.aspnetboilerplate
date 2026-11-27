# Design

## Context

固定模板的编辑窗口先请求 `User/Get` 读取目标用户，再请求 `User/GetRoles` 读取可选项。勾选使用 `normalizedName`，标签显示 `name`。保存用当前勾选生成完整数组，经 `UserServiceProxy.update` 发送 PUT。成功后窗口关闭，用户列表订阅 `onSave` 刷新。服务端在映射普通字段后处理提供的角色数组，并返回当前标准化角色名。源码与上轮 API 结果见[验收计划](../../../../docs/maintenance/r5-angular-user-role-edit-plan.md#页面动作与预期)。

## Goals / Non-Goals

- 用浏览器实际交互连接页面状态、真实 HTTP 与 SQL 提交证据，并把每步绑定到当轮的进程、会话、用户和库。
- 验收范围限于固定生产构建、既有运行组合、默认租户与直接角色编辑。组织单元继承、权限判定矩阵、其他运行组合、包和产品改动、部署由各自工作负责。

## Decisions

1. **复用封存的四套运行入口和前端构建。** 用 `r5_template_role_prepare.py verify` 核对公开包准备报告、两版的独立还原图和四份 Release 输出。封存目录不存在时走现有公开准备入口并登记新报告摘要。对应入口应只见三个映射包及已登记四条依赖边的差异。核验 1193 文件清单与前端实物，复用 `r3_template_runtime.py` 的服务副本和 `r3_template_browser.py` 的真实 Chromium 登录、授权和搜索路径。各侧复制同一份前端，仅覆盖 `remoteServiceBaseUrl` 与 `appBaseUrl` 两个环回值，对应 Host 的允许来源是该侧实际前端 origin。在各侧会话导航前开始监听静态资源，取该侧前端 `chunk-PPIUHYWS.js` 的成功响应体，记录 URL 与 SHA-256，对照冻结清单同名条目后才开始编辑。[固定输入](../../../../docs/maintenance/r5-angular-user-role-edit-plan.md#固定输入)
2. **隔离两侧写入并按页面操作推进。** 沿用 `r5_template_role_update.py` 的专用 SQL Server、迁移和应用 API 种子，分别登记实际实例、库名、ID、GUID、租户、管理员和目标用户。两侧按各自的角色 ID、标签和标准化名称核对角色，以唯一用户搜索结果发起编辑。每步只改姓名和约定的勾选，保存一次。在点击保存前监听本侧 Host 的 `User/GetAll`，捕获由这次保存触发、携带 `Keyword=durolecheck` 的 GET。核对响应 `totalCount` 为 1、`items` 仅一条且 ID 属于本侧目标，`fullName` 等于本步 `Name` 加空格和种子 `Surname`。待窗口关闭、唯一数据行显示该账号和本步新全名后，从该行重新打开，以新请求和全体勾选读取已提交状态。重新打开得到的窗口作为下一步起点。[页面动作与预期](../../../../docs/maintenance/r5-angular-user-role-edit-plan.md#页面动作与预期)
3. **观测真实流量和提交库。** 把页面请求及响应和 Host、授权会话及数据库身份相互对账。对 `User/Update` 和 `User/Get` 可复用 `RoleRequestObserver.cs` 已有的 `r5RoleRequest` 查询标记，PUT 另用 `r5RoleUser` 指定验收关联的目标 ID，也可用等价的测试侧关联机制。实际请求体、业务参数和响应原样流转。`GetRoles` 由同一会话真实发出，记录响应并核对角色清单与页面，使用独立同库只读 SQL 确认目标用户和直接关联。报告应保留脱敏的分步观测及数据库身份。复用现有的资源管理和错误脱敏，退出时停止当轮浏览器、静态服务、Host 并移除当轮专用容器及其匿名卷，复核封存输出。
4. **分别判定业务集合和时间。** `roleNames` 是浏览器实发的精确数组，页面角色集合包含全体实际勾选项，SQL 按直接关系及同库角色定义对照。`SetRolesAsync` 的移除与补加依赖角色名称处理，关联行增删可作为观测数据。创建时间以各侧 SQL `datetime2(7)` 初值为准，并对照服务端原始回执和 GET。记录客户端 `Moment.toISOString()` 的时区和精度，按各自表示核对，允许 HTTP 尾零省略。

## Risks / Trade-offs

- 冻结输入或浏览器握手缺失会使相应对照不可比。记录缺项，停止依赖该前提的写入，继续前提齐备的一侧。
- 每步先判数据库身份，再判业务结果。已发出的 PUT 或详情 GET 缺少对应目标用户的业务连接证据，或业务连接、独立 SQL 的库身份失配时，该侧输入不可比。若 PUT 可能写入另一侧库，下一次编辑写入前，用独立 SQL 对照另一侧登记的库身份以及初态或上一步已通过的快照（目标用户、普通字段、原创建时间和全部直接角色）。相符才继续，缺失或偏离则该侧也不可比。
- 目标库身份可信但 PUT 回执丢失时，保留脱敏证据，判阶段失败并停止该侧写入。只读诊断即使符合预期也维持失败结论，已发出的 PUT 不重发。两侧都满足预期才出具通过结论。[通过与停止条件](../../../../docs/maintenance/r5-angular-user-role-edit-plan.md#通过与停止条件)
