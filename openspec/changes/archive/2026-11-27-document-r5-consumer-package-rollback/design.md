# 公开回退指南的输入与验收

## Context

独立验收从固定模板、公开发行物、读者的工具和一座新建的专用空库开始。按 R4 安装步骤完成首次初始化，即得到演练所需的存量应用基线。R5 和回退阶段继续使用这一座库。公开安装指南中为新装创建数据库的步骤只执行一次。[R4 安装](../../../../docs/maintenance/r4-public-install.md) · [R5 安装](../../../../docs/maintenance/r5-public-install.md) · [发布者复跑](../../../../docs/maintenance/r5-automapper-template.md#公开包切换复跑)

## Goals / Non-Goals

在主仓 `docs/maintenance/r5-consumer-package-rollback.md` 写一条普通读者可以逐步执行的同库路径。验收对象是固定模板后端的包、进程和经授权的应用数据。Angular 的浏览器结果、从 SQL 备份恢复的写入边界分别引用其既有报告。两个已发布版本、生产子模块和发布者验收入口沿用原实现。

## Decisions

**两次构建，一次回退。** 固定 `module-zero-core-template@2e9536872673a7ff1986a19e798c51684d16afe5`、SDK `10.0.404` 和两套 `10.0.15` 共享框架。先按 R4 安装指南把原模板改成 `net10.0` 和 R4 引用。复制该源码到独立构建目录，从这个基线切 R5 时，只改 Core 的 `Du.Abp.AutoMapper` 直接引用。引擎、Collection、适配器由 R4 的 `14.0.0 / 11.0.0 / 10.5.1` 变为 R5 的 `14.0.1 / 11.0.1 / 10.5.2`，其余十包沿用 `10.5.1`。两次构建各用空 NuGet 缓存和仅含 nuget.org 的配置。

按各入口的 `project.assets.json` 核实 Web.Host 的 13 个、Migrator 的 10 个维护包。缓存中实际还原的 `.nupkg` 按 ID、版本、签后 SHA-256 对照公开 Release 附件。R4 的 13 包和 R5 的三个新包读取 `packages[id].mainPackage.anonymousDownloadSha256`。R5 的十个沿用包读取 `carriedPackages[id].anonymousDownloadSha256`，并与 R4 同包核对。三个映射 DLL 分别比较 Release 输出与包图选中成员的字节。包、输出文件和进程加载各按实际观测记载。[公开包与 DLL 对照](../../../../docs/maintenance/r5-public-patch-review.md#主包与签后实物)

保留 R4 的两套完整运行目录。初次启动前对构建交付的文件生成清单，覆盖入口、DLL、配置、`.deps.json` 和 `.runtimeconfig.json`。运行产生的日志单独记录。回退时先停止 R5 Host，核对保存的 R4 清单，再直接从该目录依次运行 Migrator 和 Web.Host。记录启动路径、PID、迁移退出码及实际监听地址，末段沿用首段构建，不再还原或编译。[公开版适用范围](../../../../docs/maintenance/r5-public-release.md#公开消费与回退证据)

**同一数据库的三个阶段。** 初次运行前以只读 SQL 核实隔离实例、库名、数据库 GUID 和空库状态。R4 首次迁移后记录有序的 30 个迁移 ID，R5 与末段 R4 分别在迁移前后逐项比对。每次启动前核实两个入口的有效连接。在已有表的阶段，预检模板租户没有指向其他库的独立连接，实例或库身份不符就停止。[连接预检](../../../../docs/maintenance/r5-r4-net10-migration.md#在迁移或登录前核对连接)

| 阶段 | 操作与可回读的业务证据 |
| --- | --- |
| R4 | 以 `Default` 租户管理员创建本轮唯一的 A。收到成功响应时即保存阶段、租户、用户名和返回的 ID。 |
| R5 | 以相同租户查回 A，再创建 B，立即保存 B 的创建回执，随后单独查询 B。任何一步失败即记录该阶段及尚未执行的步骤。 |
| 保存的 R4 | 管理员重新认证一次，使用同一令牌分别按 A、B 的唯一用户名调用 `User/GetAll`，逐人留存脱敏响应。 |

从 `Session/GetCurrentLoginInformations` 取得已认证的租户和管理员身份。每次 `User/GetAll` 须返回 HTTP 200、`success=true`、`result.totalCount=1` 且 `result.items` 只有一项。ID 和用户名对照创建回执，姓名、邮箱及启用状态对照创建时提交的值，再按租户及用户 ID 核对 `AbpUsers` 中的记录。登录行按本轮实际认证次数核对，证据中去除密码和令牌。[授权查询与会话](../../../../eng/r3_template_browser.py) · [实际创建调用](../../../../eng/r3_template_runtime.py)

**独立验收。** 冻结待验指南的 SHA-256，在干净目录只用指南列明的公开或本轮生成的输入执行。另取保存的 R4 输出副本，替换其中一个映射 DLL，检查启动前的清单核对报告预期与实际差异，且未启动 Migrator 或写入数据库。记录命令、退出码和结果。若须补充命令或修改指南，以新摘要从干净起点复验。仅对全部通过的指南版本登记支持范围。

## Risks / Trade-offs

- 复用相同输出路径可能把 R5 程序误当作 R4。指南需要在运行 Migrator 前给出可执行的版本和文件核对，并能指出哪份输出已改变。
- 切回 R4 会恢复其原有集合映射行为。本次用例验证用户的创建与读取，集合映射差异见[模板手册](../../../../docs/maintenance/r5-automapper-template.md#公开-r4r5-同库回退实测)。
- 同库换包会保留本轮已经提交的业务写入。恢复到较早备份会舍弃其后的写入。将备份恢复作为另有证据的操作说明，单列本轮实际验证的同库路径。
