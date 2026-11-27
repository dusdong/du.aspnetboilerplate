# R5 映射补丁公开发行验收

GitHub Release `460000507` 于 2026-11-27 09:31:09（北京时间）公开，沿用原草稿。附注标签 `v10.5.2` 的对象为 `b08cd8ae03cb47bc6f01fa0a0d0065efc3c78b43`，指向协调提交 `cebc3e38a511783092963893bf5ad3161d0f0a19`。该提交的 R0 基线复验通过。[发行说明](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.2) · [协调提交](https://github.com/dusdong/du.aspnetboilerplate/commit/cebc3e38a511783092963893bf5ad3161d0f0a19) · [R0 基线运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45846709281)

发行前移除了六份暂存归档。公开 Release 的唯一上传附件为 `R5-PACKAGE-CHECKSUMS.json`，匿名下载的 SHA-256 为 `be08d2d354d71dcb09802f8161496f213ebdd257826ed5adbf6af77fe9000dd5`。匿名回读确认标签、Release 正文和附件与已核定输入一致。[公开校验附件](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.2/R5-PACKAGE-CHECKSUMS.json)

| 新包 | 精确版本 | 生产提交 |
| --- | --- | --- |
| `Du.AutoMapper` | `[14.0.1]` | `54f6277af80783e5d07e896f75df0dcc0c4b4502` |
| `Du.AutoMapper.Collection` | `[11.0.1]` | `d22aaf58469d760502864fbb6f575b6505dd8334` |
| `Du.Abp.AutoMapper` | `[10.5.2]` | `7933e71f5646d2447af3502ecbea9a3f1aba8184` |

三个主包通过匿名下载、nuget.org 仓库验签和冻结成员对账，公开包新增仓库签名成员。三个符号归档分别获受理，公开符号服务读回的三个 Portable PDB 与签后 DLL 的调试标识和冻结符号实物一致。十个沿用包均为 R4 的 `10.5.1`，签后摘要逐项与 R4 公开清单一致。[R4 校验附件](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json) · [冻结批次与来源](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/source-and-engine-validation.md#三包待发批次)

## 公开消费与回退证据

R5 在 macOS ARM64、SQL Server 2022 Developer `16.0.4236.2` 与固定模板上通过三项公开源消费。发布者新装验证 `net10.0` 新库迁移和冻结 Angular 的业务登录及授权查询。同库接续实测 `net9.0` 到 `net10.0` 的 Web.Host 和 Migrator 四入口，以及升级前后两个恢复点。.NET 与 ASP.NET Core 实测运行时分别为 `9.0.10` 和 `10.0.15`。微软已于 2026-11-10 结束 .NET 9 支持。独立消费者使用已实跑的固定公开指南安装 `net10.0`，Migrator 退出 0，写入 30 条迁移记录，Swagger 返回 HTTP 200。[三项消费验收汇总](https://github.com/dusdong/du.aspnetboilerplate/blob/91ca2348261ab5050d6f5e913896f35853f75cb9/openspec/changes/publish-r5-mapping-patch/consumption-validation.md) · [已实跑的固定指南](https://github.com/dusdong/du.aspnetboilerplate/blob/ab4957bb0326a3754ffc5b50cdbdf1244f411dfd/docs/maintenance/r5-public-install.md) · [.NET 支持周期](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core)

R4 首发有独立的公开源验收。包回退沿用 R5 发行前在固定 `net10.0` 运行时验证的历史同库切换，从公开 R4 切至三个本地 R5 待发包和十个公开沿用包，再回退到完整 R4。实测覆盖 R4 阶段创建的业务用户和后续登录记录。回退涉及候选阶段新增业务实体时，应验证对应场景。[R4 首发公开源验收](r4-release-candidate.md#公开源模板消费) · [R5 历史同库切换](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/consumption-validation.md#固定运行时的公开-r4-同库切换)
