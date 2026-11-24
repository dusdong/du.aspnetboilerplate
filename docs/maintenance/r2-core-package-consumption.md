# R2 核心候选包消费验收

2026-11-25，本机 macOS 27.2.1 ARM64（`26B131`）通过 `10.5.1-r2.1` 的五个实际 NuGet 候选包和两种独立后端组合验收。两个目标分别从空缓存还原、以 Release 构建并运行真实 Kestrel 进程。写入返回 HTTP 201，独立读回返回 HTTP 200，SQLite 中恰有一条预期记录。两次写入均取得仓储 DbContext 上的活动 SQLite 事务及负责该事务的 ABP 工作单元完成事件。两个运行进程各加载来自本批对应目标且摘要相同的五个 `Abp*` 程序集。

## 源码与产物

| 项目 | 已核对输入 |
| --- | --- |
| 打包时的主仓与框架 gitlink | 主仓 `main` 的 `0780c8c55a964b2c561b1126f2a2f98048b1c100` 指向框架 `d497cba3d3feec093168697e81adb64ea5544087` |
| 同目标 R1 对照树 | `097820f84c1c20d09e5158c4a2723ed530098266`，也是 R1 候选提交 `7a47504c17b32f0111473c97dd2f8377fe06171b` 的树 |
| R2 未提交候选源码树 | `fb0abb6be5cb69b0e5ff395f4b010cf28511f9c8` |
| 框架补丁 SHA-256 | `2f7702164852f60ebb0cfa7260e1c04925f71c1a40cc95da6db84edf9ee32cf1` |
| 候选清单 SHA-256 | `fed4d30960f9c25f444c35ffadedd3746baeefbca2a78e5938ccde1f38d0b3fc` |
| R1 `release-outputs.json` SHA-256 | `d2bf3e7859f682f9f8bfef11f02c40c778428a2555b316cc594137aa204c8248` |
| SDK 和私有宿主 | SDK `10.0.404`。私有 ARM64 宿主复用已安装的 SDK 与 .NET 10 共享框架，另解包并加载通过 Microsoft SHA-512 核对的 ASP.NET Core 9.0.23 归档中的两项共享运行时 |

验证器分别核对主仓提交登记的 gitlink 和 `.gitmodules` 仓库、实际打包基线、候选树、可选的精确来源提交以及固定 R1 对照提交。它从打包基线使用独立 Git 索引和对象目录重放补丁。已提交来源可使用空补丁，其真实 Git 提交对象的树须与候选树和重放结果一致。未提交来源以补丁重放确认候选树。从候选树回读许可及图标，并与实际包内文件核对。五包及五个符号包的 ZIP、nuspec、仓库、来源证明和各目标 DLL/PDB 摘要通过。十份 DLL 的 `TargetFrameworkAttribute` 各自匹配 `lib/<TFM>`。API 工具逐份比对 R1 的同目标程序集身份、公开及受保护 API 和资源，差异均为空。第三方可传播依赖核对 R1 的资产、私有引用和普通 pack 的目标裁剪结果。

| 包 ID | nupkg SHA-256 |
| --- | --- |
| `Du.Abp` | `0f6d9da908af7b6b51bedb5b942be8fcdc54fa6b07897224dfb2a647c4e75769` |
| `Du.Abp.AspNetCore` | `53f1fcbdf3be677e62f36d49b7b37b9d4146e3c2b0bade7e40716025136dd091` |
| `Du.Abp.EntityFramework.Common` | `cc8be8158fd8bde6b8c2a6374ca1fb362b14965e17435df2f1b8780217a57234` |
| `Du.Abp.EntityFrameworkCore` | `a3e8caf24c765be13877ee7cd48908b951d25a1a61fb837a99eb5fece9d8dbb6` |
| `Du.Abp.Web.Common` | `4724bd69ce91286ba641fec37da556b0d80fec6b1b6e8c43c06e3f499d81f84a` |

## 两个实际消费者

| 目标 | 两项实际共享运行时 | EF Core、SQLite Provider、MVC JSON 和 Razor | SQLite 原生资产 | 结果 |
| --- | --- | --- | --- | --- |
| `net9.0` | `9.0.23` | `9.0.18` | `SQLitePCLRaw.lib.e_sqlite3 2.1.10`，SQLite `3.46.1` | 66 个包，构建 0 错误，HTTP 201/200，唯一行 1，宿主退出 0 |
| `net10.0` | `10.0.15` | `10.0.15` | `SQLitePCLRaw.lib.e_sqlite3 2.1.13`，SQLite `3.53.3` | 48 个包，构建 0 错误，HTTP 201/200，唯一行 1，宿主退出 0 |

两目标直接引用同批的 `Du.Abp.AspNetCore` 和 `Du.Abp.EntityFrameworkCore`。实际还原图给出两条链及每目标四条内部边。

- `Du.Abp.AspNetCore → Du.Abp.Web.Common → Du.Abp`
- `Du.Abp.EntityFrameworkCore → Du.Abp.EntityFramework.Common → Du.Abp`

五个框架包全部由本轮本地源取得，其余包全部来自 nuget.org。nuspec 和还原图都使用 SDK 的 `NuGet.Versioning` 核对内部依赖范围，范围须以本批版本为含端点的下界并允许该版本。实际解析的五个版本还须精确命中候选。还原证据包含各包的版本、来源、NuGet 内容哈希、实际缓存归档摘要和选中资产。Release 输出中的框架 DLL 在依赖清单和文件系统均有唯一来源，与实际包的选中资产同摘要。Razor 配置在 `.deps.json` 生成 SDK 编译专用引入项，这些条目均无运行资产。按目标另存 R1 源码图与最小消费图的逐项第三方差异。

真实请求使用固定 ID `8df27508-4dd1-45f5-b9c6-927f43e5fd1b` 和值 `r2-sqlite`。写请求分别保存活动事务和同一工作单元 `Completed` 事件的请求标识、工作单元标识和事务标识。等待提交完成后才返回 201。每个读回均从不同请求、DI 作用域、工作单元和仓储 DbContext 执行。响应同时记录模块初始化、服务和仓储实现、实际进程架构、共享运行时、已加载 DLL 全名与摘要。SQLite 原生库取自 dyld 实际加载路径，和 `runtimes/osx-arm64/native/libe_sqlite3.dylib` 的还原资产及输出文件对照。

## 诊断验证

| 用例 | 实际诊断和退出码 |
| --- | --- |
| 同版本包内容替换，保留原清单 | 包摘要不符，1 |
| nuspec 内部依赖改回原 ID，更新负例包摘要 | 指出 `Du.Abp.Web.Common` 的内部依赖 ID，1 |
| 更新负例清单的包与 DLL 摘要，将 `net9.0` DLL 填入 `net10.0` | 指出 `lib/net10.0/Abp.Web.Common.dll`，预期 `v10.0`，实读 `v9.0`，1 |
| 隔离源移除 `Du.Abp.Web.Common` | 独立的真实 NuGet 还原报告 `NU1101`，1 |
| 还原图中框架编译资产错目标或多来源 | 分别指出相应程序集、资产路径和来源，均为 1 |
| 两个目标分别删去活动事务或提交完成证据，保留 HTTP 成功及唯一读回 | 四种夹具逐项指出缺失写入证据，均为 1 |

复审定向验收覆盖已提交来源的空补丁、从独立打包基线重放到真实提交、错填旧提交和将树对象当作提交。其中有上界的 `[10.5.1-r2.1,10.5.1)` 通过实物 nuspec 检查、独立 NuGet 还原和还原图检查。排除本批版本、错误下界、浮动范围与错误的实际解析版本各触发对应诊断。分别用两个损坏 R1 归档运行完整入口，均返回 1，报告标记 `packages` 为失败，后续阶段记录未执行及原因。

## 复跑与原始证据

按[独立消费说明](../../validation/minimal-backend/README.md)运行 `python3 eng/verify.py --profile r2`。验证机主仓有可直接执行的 `sh .git/r2-core-consumption/package-2/replay.sh`。每次运行创建新目录和空缓存。候选包使用精确版本范围并核对字节，第三方解析通过每轮资产与来源清单留证，本轮未生成还原锁文件。

- 第一包的实物位于 `.git/r2-core-consumption/package-1/10.5.1-r2.1/`，同级 `交接.md` 记录普通模式求值与源码调用方构建。R1 对照位于 `.git/r1-net10-implementation/package-2/final-v2/`。
- 第二包工件位于 `.git/r2-core-consumption/package-2/`。正式运行目录为 `runs/r2-b8joqypx/`。`report.json` 的 SHA-256 为 `50655837641217a9795913723444be044f56b9402b0185f9834ae78f8d262489`，记录精确命令、阶段和退出码。`candidate.json` 的 SHA-256 为 `8b45e835c96dad76ddcda47935a838c2fc0b5d280308f9e01b82c96d17b86f4d`，记录符号包、DLL 和 R1 对照摘要。每目标子目录保留 `NuGet.Config`、`obj/project.assets.json`、Release 工件与宿主追踪日志。同轮 `*-assets-inventory.json`、`*-r1-restore-differences.json`、`*-http.json` 与 `*-host.log` 保存依赖和运行记录。
- 调试副本的首轮 Host 返回值错误及修复分别在 `consumer-first/host-first.log`、`consumer-retry/host.log`。集成首轮暴露了 .NET 9 普通 pack 的额外裁剪项，第二轮识别出 Razor SDK 的编译专用项，第三轮分辨了签名包的内容哈希与归档哈希。修订后在新目录复验，历次日志、报告与退出码均可回读。
- R0 Python 自查 17 项通过。原 R0 命令在单独目录针对固定提交 `6c4580c5e7ea41154696c071a53fd200059a768b` 和树 `77ebbd3dbd293fff4c57b5e741919407995579e8` 完整复验，三套回归 1313 通过、0 失败、2 项既有跳过。R0 固定清单、R1 历史对照及其他子模块的输入摘要与验收前一致。R0 报告位于 `r0-evidence/r0-c9dwzz9_/report.json`。
- 复审的原始来源夹具保存在 `.git/r2-core-consumption/review-package-2-v1/`。修订后的定向日志及夹具保存在第二包 `revision-2/`。可以用 `python3 -B eng/tests/verify_r2_review.py "$R2_RUN" "$R2_NEW_EVIDENCE"` 复现，传入正式运行目录和一个新的证据目录。范围测试仅修改独立夹具中的包副本，正式复跑沿用同一批包和清单。

本轮结论适用于上述两个 macOS ARM64 与 SQLite 组合。Windows 与 Linux 的候选消费、其他 Provider、完整模板、Angular、AutoMapper、Module Zero、公开发行和 CI 扩展留待各自阶段验证。[核心候选包消费规范](../../openspec/specs/core-package-consumption/spec.md) · [R2 OpenSpec 归档](../../openspec/changes/archive/2026-11-25-validate-r2-core-package-consumption/) · [R1 源码验收](r1-dotnet10-runtime-migration.md)

## Git 交付

2026-11-25，框架 `dev` 已推送至 `.gitmodules` 登记的 `dusdong/aspnetboilerplate`，并通过 GitHub 回读确认指向 `457be917b46c4fb6237831baac5abb848ffe1c4b`。其父提交为 `d497cba3d3feec093168697e81adb64ea5544087`，提交树 `fb0abb6be5cb69b0e5ff395f4b010cf28511f9c8` 与生成候选包的实测树相同。框架远端回读记录保存在验证机的 `.git/r2-core-consumption/closeout/framework/github.branch-commit-readback.json`。[框架交付提交](https://github.com/dusdong/aspnetboilerplate/commit/457be917b46c4fb6237831baac5abb848ffe1c4b) · [打包入口](../../aspnetboilerplate/nupkg/README.r2.md)

本版主仓 gitlink 指向上表候选树对应的框架交付提交。检出本版主仓后执行 `git ls-tree HEAD -- aspnetboilerplate`，应读到 `160000 commit 457be917b46c4fb6237831baac5abb848ffe1c4b`。原始候选包及清单保留生成时的未提交树来源证明和摘要，本机实测结论继续对应这些原始字节。
