# R5 公开映射包消费对照计划

制定日期为 2026-11-27，基线为主仓 `3b0b21c`。本轮在 .NET 10 上对照公开 R4 与 R5。独立消费者使用固定模板的 DTO、实体和 Profile，验证 `IObjectMapper` 更新已有用户、按键更新集合，以及在 SQLite 上执行 `ProjectTo<UserDto>` 的结果。2026-11-27，两侧分别通过三项断言，完成逐项证据复核，同步稳定规范并归档。[实测报告与公开复跑](r5-public-mapping-behavior.md) · [任务归档](../../openspec/changes/archive/2026-11-27-validate-r5-public-mapping-behavior/tasks.md)

## 选择这一轮的依据

上一轮已用公开包完成 R4 → R5 → R4 同库切换，回退后管理员能分别查回两段创建的用户。对象引用、集合元素身份和投影 SQL 已有专项断言，但当时对照的是原版与本地候选，使用 `net9.0` 和 EF Core SQLite `9.0.18`。本轮复用这些断言，补齐两代**公开包**在同一 .NET 10 环境下的业务证据。[公开回退实测](r5-automapper-template.md#独立消费者验收) · [候选业务实测](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md#消费结果)

## 对照输入

| 独立消费者实际使用的包 | R4（`v10.5.1`） | R5（`v10.5.2`） |
| --- | --- | --- |
| `Du.Abp.AutoMapper`，唯一直接引用的映射包 | `10.5.1` | `10.5.2` |
| `Du.AutoMapper`，传递依赖 | `14.0.0` | `14.0.1` |
| `Du.AutoMapper.Collection`，传递依赖 | `11.0.0` | `11.0.1` |
| `Du.Abp.ZeroCore` 与 `Du.Abp` 内核 | 均为 `10.5.1` | 均为 `10.5.1` |
| `Microsoft.EntityFrameworkCore.Sqlite` | `10.0.15` | `10.0.15` |

两侧固定 macOS ARM64、SDK `10.0.404`、目标 `net10.0`、实际运行时 `10.0.15` 和模板提交 `2e9536872673a7ff1986a19e798c51684d16afe5`。使用相同的模板 Profile、DTO、实体、种子和查询。每侧独立从 nuget.org 空缓存还原，独立构建和运行。核验依据为各版的签后主包摘要、该消费者自己的还原图及进程加载文件。[公开签后摘要](r5-public-patch-review.md#主包与签后实物) · [固定模板来源](r5-public-install.md) · [SQLite Provider 10.0.15](https://www.nuget.org/packages/Microsoft.EntityFrameworkCore.Sqlite/10.0.15)

## 工作顺序和完成条件

| 顺序 | 要交付的成果 | 如何判定完成 |
| --- | --- | --- |
| 1. 准备消费入口 | 从公开检出可执行的两版命令、包校验和原始报告位置 | 历史入口的默认用法仍可复跑。新的入口能在包摘要错误时报告具体版本和包，并返回非零。 |
| 2. 固定业务预期 | 两侧共用的探针、输入和三项断言 | 比较逻辑能识别缺项和两侧同错。单侧投影断言失败的反例须保留已取得的业务与查询结果，另一侧独立完成，总入口返回非零。 |
| 3. 实跑 R4 和 R5 | 两组独立还原、构建、加载和业务执行记录 | 实际包图仅有上述三个映射包的版本差异，每侧只加载一个引擎。下表三项须逐版有实际结果。 |
| 4. 发布验收记录到项目文档 | 一份含复跑命令、两侧结果和适用范围的报告 | 从原始结果可核对每项判定，兼容指南与文档索引可达，相关回归和 OpenSpec 严格校验通过。 |

| 业务 | 两版分别需要满足的预期 |
| --- | --- |
| 已有用户更新 | 通过经典 ABP 的 `IObjectMapper` 更新同一个 `User`，`IsActive` 从 `false` 更新为 DTO 的 `true`，其他普通字段取 DTO 的值，原角色集合、角色成员对象及创建时间得到保留。 |
| 按键集合更新 | 保留目标集合和键 10 的原对象，更新其值，删除键 20，新增一个键 30，最终依次为 `10:updated`、`30:inserted`。 |
| SQLite 查询投影 | 对租户 6 的活跃用户执行并物化 `ProjectTo<UserDto>`。核对实际 SQL 的参数、筛选、排序、读取列及顺序，结果 ID 依次为 `12、13、11`，字段命中种子预期，`FullName` 通过客户端的实体属性计算。 |

现有探针给出了对象引用断言、集合输入、投影种子和 SQL 断言。实测对应的长期验收条件已纳入稳定规范，技术设计及当时的增量保存在归档。[对象与集合探针](../../validation/automapper/Program.cs) · [投影探针](../../validation/automapper/Projection.cs) · [对照验收规范](../../openspec/specs/automapper-package-consumption/spec.md#requirement-消费者可在同一-net-10-环境对照两代公开映射包) · [技术设计](../../openspec/changes/archive/2026-11-27-validate-r5-public-mapping-behavior/design.md) · [增量规范归档](../../openspec/changes/archive/2026-11-27-validate-r5-public-mapping-behavior/specs/automapper-package-consumption/spec.md)

## 验收后的决定

- 两版分别命中全部预期，实测范围已登记。此前维护审查对固定消费组合的决定仍为无需补丁。[对照范围](r5-public-mapping-behavior.md#适用范围) · [维护决定](r5-public-patch-review.md#本轮维护决定)
- 包来源、运行时或其他依赖有差异时，先修正对应输入再重跑。输入可比而业务仍有偏差时，分别记录单侧偏差或两版共同偏差，保留最小业务输入与原始输出，再判断应调整探针、说明 Provider 差异，还是另立兼容修复。
- 既有共享集合执行计划的顺序差异继续按专项结果解释。SQL Server、Angular 和同库回退沿用已验组合。上游与公告按既有检查点续查，其中包括 `CVE-2026-56158` 的现代 .NET 组件范围。[共享集合专项](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/shared-collection-plan-observation.md) · [完整模板验收](r5-automapper-template.md) · [维护检查点](r5-public-patch-review.md#下轮检查点与验证边界)
