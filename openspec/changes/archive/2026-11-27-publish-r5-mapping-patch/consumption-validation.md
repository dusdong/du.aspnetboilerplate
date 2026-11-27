# R5 固定模板公开消费验收

2026-11-27，发布者在主仓 `ab4957bb0326a3754ffc5b50cdbdf1244f411dfd`、固定模板 `2e9536872673a7ff1986a19e798c51684d16afe5` 上通过正式验收入口执行 `install` 和 `upgrade`。两轮使用 macOS ARM64 `27.2.1`（`26B131`）、.NET SDK `10.0.404`、独占 SQL Server 2022 Developer `16.0.4236.2` 和 Chrome `158.0.8127.37`。两代应用使用同一 Angular production 产物，1,193 个冻结文件对账通过，仅修改服务副本的两个环回地址。[正式复跑入口](../2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md#正式公开后的验收)

## 实际包与入口

新装 `net10.0` 与接续的两个 TFM 分别使用独立空 NuGet 缓存，唯一配置源为 `https://api.nuget.org/v3/index.json`。该网络的服务入口实际返回 302，经 `https://nuget.azure.cn/v3/index.json` 返回 200。每个 Web.Host 的 13 个维护包和每个 Migrator 的 10 个维护包均逐包核对实际还原归档。签后 SHA-256 匹配本轮公开下载登记 `41701309f7fb423864b1eeb8c890b25487e1800f662045570bef5751426c3126`，并比对 nuspec、编译引用、Release 输出 DLL 及实际加载证据。三个映射包为 `Du.AutoMapper 14.0.1`、`Du.AutoMapper.Collection 11.0.1`、`Du.Abp.AutoMapper 10.5.2`，其余十个维护包为沿用的 `10.5.1`。

| 验收 | 目标 | 实际 .NET／ASP.NET Core | Web.Host 包数（维护包） | Migrator 包数（维护包） |
| --- | --- | --- | --- | --- |
| 发布者新装 | `net10.0` | `10.0.15`／`10.0.15` | 94（13） | 66（10） |
| 发布者接续起点 | `net9.0` | `9.0.10`／`9.0.10` | 116（13） | 81（10） |
| 发布者接续终点 | `net10.0` | `10.0.15`／`10.0.15` | 94（13） | 66（10） |

Web.Host 实际加载 11 个 ABP DLL 和 `AutoMapper.dll`，`AutoMapper.Collection.dll` 在输出中。Migrator 实际加载七个 ABP DLL，三个映射 DLL 在输出中。实际入口和加载文件的路径与摘要、运行时版本均绑定到本轮进程。

## SQL Server 与租户业务

- `install` 退出 0，16 个阶段通过。Migrator 在新库执行 33 条迁移相关 SQL 命令并写入 30 条迁移历史。租户 `Default` 的用户 `admin` 经应用认证后创建一个业务用户，随后通过冻结 Angular 登录且获得 `Pages.Users` 权限，查询返回 HTTP 200 并在页面显示该唯一用户。成功登录行从 0 增至 1 再增至 2，最终备份通过 `RESTORE VERIFYONLY WITH CHECKSUM`。
- `upgrade` 退出 0，26 个阶段通过，内层 `net9.0` 构建的 9 个阶段全部通过。由同一已验测试备份恢复接续库和独立对照库。接续的两代各在同一数据库执行三条迁移相关 SQL 命令，数据库 ID、GUID、物理文件路径、30 条迁移历史和既有业务用户保持一致。`net10.0` 迁移前后的 SQL Server 目录也一致。两代都经 `Default/admin` 登录和 `Pages.Users` 授权，查询返回 HTTP 200 并在页面显示同一个用户。接续库成功登录行从 1 增至 2 再增至 3，对照库始终为 1。接续前后分别备份并实际恢复至独立库，读回对应的业务数据、迁移历史及 2 条、3 条成功登录行。
- 独立消费者已从匿名公开的固定指南执行全新 `net10.0` 安装。空库起始为 0 张用户表，Migrator 退出 0 后有 30 条迁移记录，Web.Host 的 `/swagger/v1/swagger.json` 返回 HTTP 200。还原归档和构建输出已对账。指南固定版本为 `ab4957bb0326a3754ffc5b50cdbdf1244f411dfd`，文件 SHA-256 为 `6d2ede2a0cfa55040319cee9a31740d9b0c7e3cab07eaeb17d50b9fd9920265d`。[已实跑的固定指南](https://github.com/dusdong/du.aspnetboilerplate/blob/ab4957bb0326a3754ffc5b50cdbdf1244f411dfd/docs/maintenance/r5-public-install.md)

| 发布者报告 | SHA-256 |
| --- | --- |
| `install` | `f636e66f04f57c14da54b5ca8b8e3ad8010c3fcdf98a3e4ca98950a389f0fdab` |
| `upgrade` | `52d456199c6baf76a6ed27941a5b6bdd24ffe58eeeef868bc7e94f24bd339de8` |

结论适用于上述 macOS ARM64、固定模板、SQL Server Developer 和 Angular 产物。`net9.0` 用于存量应用接续验证，新装使用 `net10.0`。本轮实际恢复升级前后备份。三包回退沿用此前固定 .NET 10 的本地候选同库切换证据，公开 R4 验证见其首发记录。[本地 R5 同库切换](../2026-11-26-prepare-r5-mapping-patch-release/consumption-validation.md#固定运行时的公开-r4-同库切换) · [公开 R4 固定模板](../../../../docs/maintenance/r4-release-candidate.md#公开源模板消费)
