# R5 运行时迁移交接设计

## Context

R4 的 `v10.5.1` 对应主仓 `5758c81` 和模板 `2e953687`。在 macOS ARM64、SQL Server Developer `16.0.4236.2` 和冻结 Angular 客户端上，两代 Web.Host 各还原 13 个公开维护包，Migrator 各还原 10 个。R4 报告中，.NET 9 两入口实际加载的 .NET 与 ASP.NET Core 均为 `9.0.10`，.NET 10 两入口均为 `10.0.15`。首轮 R5 已登记四张包图、三个上游仓库六条分支各自的截止提交和各公告来源的查询截止点。[公开源实测](../../../../docs/maintenance/r4-release-candidate.md#公开源模板消费) · [首轮检查点](../../../../docs/maintenance/r5-first-maintenance-review.md#下轮检查点)

## Goals / Non-Goals

本轮交付日期明确的增量审查记录，以及存量维护包版应用从 `net9.0` 到 `net10.0` 的迁移指引。参考环境使用隔离测试库。消费者现场切换、其他 Provider 和新增平台由相应部署单独验收。集合映射变更独立决定三包冻结和候选交接。

## Decisions

1. **沿用首轮输入逐源续查。** 沿用首轮上游表，分别核对经典框架的 `master`、`dev`，AutoMapper 的 `release/15.x`、`release/16.x`、`main`，以及 AutoMapper.Collection 的 `master`。每条分支登记上轮截止与本轮终点的完整 SHA、相关发行标签及其提交，包含无变化的分支。NuGet 公告索引页、GitHub Advisory Database、Microsoft 服务记录及待核实条目按各自截止点续查，记录查询时间与终点。官方索引重新分页时按新索引核对。重查首轮未取得组件范围的 CVE-2026-56158，若仍缺证，保留原始来源和重查条件。四张图有变化时，按入口和 TFM 重新匹配全部解析版本及维护包原名。[首轮上游分支与发行表](../../../../docs/maintenance/r5-first-maintenance-review.md#上游源码与回补) · [依赖数据](../../../../docs/maintenance/r5-first-maintenance-dependencies.tsv) · [运行时服务记录](../../../../docs/maintenance/r5-first-maintenance-runtime-servicing.tsv)
2. **分开登记官方服务版本和应用实际加载版本。** 实施时核对 Microsoft 的 .NET 支持周期和发行元数据，按日期选择受支持的 .NET 10 服务补丁。用各代 Web.Host 与 Migrator 的进程记录分别取 `Microsoft.NETCore.App`、`Microsoft.AspNetCore.App`。SDK 清单可用于准备机器。包图单列 EF Core、SQL Server Provider 等 NuGet 资产。[Microsoft 支持周期](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core) · [Microsoft 发行索引](https://builds.dotnet.microsoft.com/dotnet/release-metadata/releases-index.json)
3. **按输入差异决定复验。** 若选择的输入全部匹配，核对 R4 原报告、摘要和公开归档来源，引用其同库结果。输入变化或原证据无法核对时，登记差异并在目标组合补验证据。R4 的 `upgrade` 入口已绑定历史版本，包含两代空缓存还原和业务核验。若仅更换 .NET 10 共享运行时补丁，沿用 R4 两代各自的 NuGet 包图，显式提供目标共享框架版本。以启动记录及同一进程加载的程序集路径核对两套共享框架，另以对应入口还原图中选定的 EF Core、SQL Server Provider 版本及 DLL 核对实际加载。现有 Migrator 断言用 `MIGRATOR_EF[runtime_version]` 查包版本，补验入口需将这两项判断解耦，并保留 R4 固定输入的复跑能力。[公开消费命令与输入](../../../../docs/maintenance/r4-release-candidate.md#公开源模板消费) · [现有版本断言](../../../../eng/r3_template_net10_runtime.py)

## Risks / Trade-offs

- 同一天重查可能没有新增公告。注明成功覆盖的时间和范围；未取得来源时保留缺项，下一轮从最后完整位置继续。
- 仅凭 Host 启动或 HTTP 200 可能漏掉 Migrator 连错库、租户或记录不一致。用进程、数据库身份、迁移历史以及授权查询返回的业务标识逐项核对。[模板升级规范](../../../specs/template-runtime-upgrade/spec.md)

## Migration Plan

指引从维护者自己的 R4 应用源码、公开包源和测试库备份出发。给出可替换项目路径的还原与 Release 构建命令，保留两代 Migrator 和 Web.Host 输出。以固定模板为例，Core、Application、EntityFrameworkCore、Web.Core、Web.Host 和 Migrator 六个工程均改为 `net10.0`。按工程列出 SQL Server Provider、EF Core Design、Tools 和 JwtBearer 的直接引用调整，保留原有引用元数据。派生应用按自己的引用图选择要改的工程。R4 冻结目录与 `upgrade` 命令供维护者追溯历史证据。[固定模板的工程与依赖改动](../../../../docs/maintenance/r3-template-net10-upgrade.md)

从自己的备份恢复到隔离库，用源版本 Migrator 和 Web.Host 确认迁移历史、租户授权和一条已有业务记录，保存升级前恢复点。再从目标版本的 Release 输出启动两入口，用同一客户端在同一库复查迁移历史、权限和记录。固定模板另对账 30 条迁移、`Pages.Users` 和唯一用户查询。指引给出应用版本与备份的对应关系，注明恢复到升级前会丢弃恢复点之后的写入。对原版包迁入和恢复原版应用分别链接已验路径。[原版换包](../../../../docs/maintenance/r3-template-net9-packages.md) · [恢复点与写入边界](../../../../docs/maintenance/r3-template-net10-upgrade.md#恢复点与写入边界)
