# Proposal

## Why

公开 R4 与 R5 的独立映射探针已验证固定模板的用户映射保留角色对象和创建时间。模板 `UserAppService.UpdateAsync` 在映射后还会处理角色关系并提交，现有固定模板实测覆盖用户创建和读回，本轮需要确认用户更新的真实提交结果。[映射实测范围](../../../../docs/maintenance/r5-public-mapping-behavior.md#适用范围) · [模板独立验收](../../../../docs/maintenance/r5-automapper-template.md#独立消费者验收)

## What Changes

- 在同一固定模板的两份独立副本上使用公开 `v10.5.1` 与 `v10.5.2`，从干净还原到真实 SQL Server 提交分别保留证据。
- 从等价的测试用户和角色初态，通过模板 `PUT User/Update` 依次提交 `roleNames` 为 `null`、单个角色数组、空数组。每步用各自的请求标识核对 PUT 和独立 GET 实际访问的数据库，再对照更新回执、GET 和只读 SQL，验证直接角色的保留、替换和清空，以及普通字段更新和创建时间保留。
- 逐版对照独立预期，记录单侧失败、两侧失败或输入不可比的证据。PUT 已发出但缺少可用回执时，该步失败，停止该侧写入，只在目标库可核实时读回现状。结果仅用于本次固定的后端组合，发现需要修复的产品行为另行立项。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `automapper-package-consumption` 增加两代公开映射包的固定模板角色更新提交对照，覆盖应用 API 与数据库的可观察行为。

## Impact

消费项目为 `module-zero-core-template` 的 Web.Host 与 Migrator，冻结在 `2e9536872673a7ff1986a19e798c51684d16afe5`。涉及 `aspnetboilerplate` 的 `Du.Abp.AutoMapper` 与 `Du.Abp.ZeroCore`，及 `AutoMapper`、`AutoMapper.Collection` 对应公开包。实现范围为主仓的验收入口、定向回归和复跑说明，子仓源码与公开发行物作为验收输入。

目标为 macOS ARM64、SDK `10.0.404`、`net10.0`、两套共享运行时 `10.0.15` 和专用 SQL Server Developer `16.0.4236.2`。公开包图、进程实际加载、各侧种子及三步结果待实施时确认。已完成的 SQLite 映射和同库回退继续引用原报告。其他平台、Provider、客户端、权限矩阵和生产环境由各自验收覆盖。[维护计划](../../../../docs/maintenance/r5-template-user-role-update-plan.md)
