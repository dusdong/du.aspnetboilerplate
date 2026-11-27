# Proposal

## Why

公开 R4、R5 的固定模板已通过直接调用用户更新 API 的对照。固定 Angular 客户端会从全体角色勾选状态生成完整数组，仍需验证用户经真实编辑窗口保存后，页面、HTTP 与数据库所见是否一致。[上一轮 API 实测](../../../../docs/maintenance/r5-template-user-role-update.md)

## What Changes

- 使用同一份冻结 Angular production 构建，分别连接公开 R4 `v10.5.1` 和 R5 `v10.5.2` 的固定 `net10.0` 模板。在独立新库和浏览器会话中，从同一业务种子出发，依次经页面保留 A、改选 B、取消全部角色，并在每步修改姓名。
- 核验两侧浏览器实收的编辑脚本。每次保存对照实际 PUT、成功回执、列表查询与页面新全名、重开窗口的 GET、GetRoles 和勾选状态，以及独立 SQL 读回。逐侧区分错库与业务失败。若写入可能影响另一侧，先只读核对其当前步骤的起点。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `template-maintenance-package-consumption`：新增两代公开包在固定 Angular 客户端上的真实用户角色编辑验收要求。

## Impact

实施涉及主仓验收入口和文档。消费对象是 `module-zero-core-template` 的 Angular、Web.Host 与 Migrator，发行输入沿用公开签后包，运行范围限于既有 macOS ARM64、.NET 10 与 SQL Server 组合。执行前核实两版封存输出和前端实物，结果仅用于本组合的直接角色编辑。[固定输入与验收范围](../../../../docs/maintenance/r5-angular-user-role-edit-plan.md)
