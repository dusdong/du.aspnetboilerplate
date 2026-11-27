# R5 映射补丁公开发行验收

GitHub Release `460000507` 于 2026-11-27 09:31:09（北京时间）公开，沿用原草稿。附注标签 `v10.5.2` 的对象为 `b08cd8ae03cb47bc6f01fa0a0d0065efc3c78b43`，指向协调提交 `cebc3e38a511783092963893bf5ad3161d0f0a19`。该提交的 R0 基线复验通过。[发行说明](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.2) · [协调提交](https://github.com/dusdong/du.aspnetboilerplate/commit/cebc3e38a511783092963893bf5ad3161d0f0a19) · [R0 基线运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45846709281)

发行前移除了六份暂存归档。公开 Release 的唯一上传附件为 `R5-PACKAGE-CHECKSUMS.json`，匿名下载的 SHA-256 为 `be08d2d354d71dcb09802f8161496f213ebdd257826ed5adbf6af77fe9000dd5`。匿名回读确认标签、Release 正文和附件与已核定输入一致。[公开校验附件](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.2/R5-PACKAGE-CHECKSUMS.json)

2026-11-27，公开发行规范已同步，发行的六项任务全部完成并归档。[公开发行稳定规范](../../openspec/specs/public-package-release/spec.md) · [归档任务清单](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/tasks.md) · [归档消费验收记录](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/consumption-validation.md)

| 新包 | 精确版本 | 生产提交 |
| --- | --- | --- |
| `Du.AutoMapper` | `[14.0.1]` | `54f6277af80783e5d07e896f75df0dcc0c4b4502` |
| `Du.AutoMapper.Collection` | `[11.0.1]` | `d22aaf58469d760502864fbb6f575b6505dd8334` |
| `Du.Abp.AutoMapper` | `[10.5.2]` | `7933e71f5646d2447af3502ecbea9a3f1aba8184` |

三个主包通过匿名下载、nuget.org 仓库验签和冻结成员对账，公开包新增仓库签名成员。三个符号归档分别获受理，公开符号服务读回的三个 Portable PDB 与签后 DLL 的调试标识和冻结符号实物一致。十个沿用包均为 R4 的 `10.5.1`，签后摘要逐项与 R4 公开清单一致。[R4 校验附件](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json) · [冻结批次与来源](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/source-and-engine-validation.md#三包待发批次)

## NuGet 受信任发布

发行时，NuGet 策略 `r5-mapping-patch` 将 `dusdong/du.aspnetboilerplate` 的 `publish-r5-mapping.yml` 绑定到 `nuget-r5`，授权范围为上表三个已有包的新版本。GitHub 环境仅允许 `main` 分支。工作流使用 OIDC 兑换短期凭据。运行 `45916029211` 的凭据交换和登录核对均成功，上传步骤按仅登录模式跳过。正式上传另有各包的成功运行和公开实物回读。[固定工作流](https://github.com/dusdong/du.aspnetboilerplate/blob/f5d708cc30e30369a4e8a6b5a7be4ebbfb5c2751/.github/workflows/publish-r5-mapping.yml) · [仅登录运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45916029211) · [引擎主包上传](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45913056384) · [适配器符号上传](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45916320721)

引擎主包与符号包各有一次运行因 GitHub 运行信息延迟而中止。两次均从原运行读到实际上传步骤为 `skipped`，并与本地收据 `started: false` 对账后，才重新放行该件。最终收据覆盖三个主包和三个符号包。[主包中止运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45911951268) · [符号中止运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45914895430)

## 公开消费与回退证据

R5 在 macOS ARM64、SQL Server 2022 Developer `16.0.4236.2` 与固定模板上通过三项公开源消费。发布者新装验证 `net10.0` 新库迁移和冻结 Angular 的业务登录及授权查询。同库接续实测 `net9.0` 到 `net10.0` 的 Web.Host 和 Migrator 四入口，以及升级前后两个恢复点。.NET 与 ASP.NET Core 实测运行时分别为 `9.0.10` 和 `10.0.15`。微软已于 2026-11-10 结束 .NET 9 支持。独立消费者使用已实跑的固定公开指南安装 `net10.0`，Migrator 退出 0，写入 30 条迁移记录，Swagger 返回 HTTP 200。[三项消费验收汇总](https://github.com/dusdong/du.aspnetboilerplate/blob/91ca2348261ab5050d6f5e913896f35853f75cb9/openspec/changes/publish-r5-mapping-patch/consumption-validation.md) · [已实跑的固定指南](https://github.com/dusdong/du.aspnetboilerplate/blob/ab4957bb0326a3754ffc5b50cdbdf1244f411dfd/docs/maintenance/r5-public-install.md) · [.NET 支持周期](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core)

公开 `v10.5.1 → v10.5.2 → v10.5.1` 已在固定模板的 `net10.0`、两项 `10.0.15` 共享运行时和上述 SQL Server、Angular 组合完成同库实测。独立空缓存的两个入口均对账公开签后包、完整包图和实际加载。回退后，管理员在同一浏览器会话查回 R4 创建的 A 和 R5 创建的 B。两人的创建回执、授权响应、页面和 SQL 连接对应。30 条迁移历史保持一致，成功登录行依次为 0 → 2 → 5 → 6。[正式三阶段结果与复跑](r5-automapper-template.md#公开-r4r5-同库回退实测) · [同库回退归档任务](../../openspec/changes/archive/2026-11-27-validate-r5-public-package-rollback/tasks.md)

同库换包保留本轮业务和登录写入，选择更早的备份恢复点会舍弃其后的写入。发行前本地候选切换只用首段 R4 创建的一个用户复验。备份恢复和原版回退各有独立实测。[R4 首发公开源验收](r4-release-candidate.md#公开源模板消费) · [R5 历史候选切换](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/consumption-validation.md#固定运行时的公开-r4-同库切换) · [原版双恢复点实测](r3-original-template-rollback.md#正式运行结果)
