# 首次公开发行设计

## Context

这次发行使用已归档的本地候选批次。主仓交付点、实际跑过模板的协调提交和各包的生产提交各有用途。首发清单逐项保留这些身份。[候选手册](../../../../docs/maintenance/r4-release-candidate.md) · [批次登记](../../../../eng/r4_candidate_batch_reference.json)

| 对象 | 固定身份 |
| --- | --- |
| 主仓发行 tag | 拟在 `dusdong/du.aspnetboilerplate` 建立附注 tag `v10.5.1`，目标为 `5758c8186b68dcc42ecc90164cf9d3f53cf3345e` |
| 已实测的协调提交 | `19101266923a6422543a17e0963e3475c24923f2`，三个生产 gitlink 与主仓发行目标相同 |
| 11 个 `Du.Abp*`，版本 `10.5.1` | `aspnetboilerplate` 的 `bed57726b56f6f9de5c2d82e8dbe55e0130bddd0` |
| `Du.AutoMapper 14.0.0` | `AutoMapper` 的 `f646d492df918d27b9ac96c086933570965efef3` |
| `Du.AutoMapper.Collection 11.0.0` | `AutoMapper.Collection` 的 `306b49d7a59b7335a61d8116e1ab2f623a04740e` |
| 模板 | `2e9536872673a7ff1986a19e798c51684d16afe5` |
| 发布者输入 | `publish-handoff-v2/SHA256SUMS` 的 SHA-256 为 `097e0eee66420797c7f77dc52a593990311ebe6ebc120c81a17bbac2255fc86f`。其中 `frozen/batch.json` 的 SHA-256 为 `4d25f237938d04aeb985c2057a6287ba0f18425b94d73e9c494e313684470757` |

## Goals / Non-Goals

本轮交付可匿名安装的稳定包、可用的调试符号和可引用的 GitHub Release。实测范围沿用本轮的固定模板、SQL Server 和 Angular 客户端。两条原版回退路径及组件专项引用同批次的既有报告；R5 的持续维护策略另行立项。[本地实测矩阵](../../../../docs/maintenance/r4-release-candidate.md#实测支持矩阵)

## Decisions

### 以主仓 tag 标记整套发行

主仓提交用 gitlink 唯一确定三个生产仓。两个映射仓的版本 tag 会匹配带有 MyGet 和 NuGet 上传步骤的工作流，因此只在主仓建立本次 tag。发布前核对远端 URL、tag 是否存在、目标提交中的三个 gitlink、公开包 ID/版本及预期所有者。已有 tag 必须解引用到计划提交。2026-11-26 的只读检查中，主仓该 tag 和全部 13 个包 ID 的公开版本索引均返回 404。发布前重查名称前缀、账号的首发权限与实际授权范围，404 本身不能证明名称可注册。[引擎发版工作流](../../../../AutoMapper/.github/workflows/release.yml) · [Collection 发版工作流](../../../../AutoMapper.Collection/.github/workflows/release.yml)

### 从交接清单逐项上传并记录进度

先核验交接目录的 209 个条目、冻结批次和 `packages.tsv`，由实际 nuspec 的各目标依赖组生成 13 个主包的发行顺序。对外上传的包只取清单中 `frozen/feed/` 和 `frozen/symbols/` 的 26 份原件。先准备可公开的说明和清单，再在已有授权范围内创建主仓 tag，向 nuget.org 按依赖次序上传主包、随后上传匹配的符号包。明确区分 NuGet 服务索引中的主包与符号发布资源，避免客户端自动推符号与单独推送重叠。每项保留 ID、版本、类别、上传摘要、服务响应、时间及后续索引状态。凭据由已获授权的发布方式提供，记录中只列发布者身份和权限范围。[NuGet 发布协议](https://learn.microsoft.com/en-us/nuget/api/package-publish-resource) · [符号发布与索引](https://learn.microsoft.com/en-us/nuget/create-packages/symbol-packages-snupkg#symbol-package-validation-and-indexing)

上传每个主包之前，从冻结 nuspec 的全部目标组中列出该包的直接内部依赖。逐个按首发清单的版本匿名下载依赖主包，采用下节的签名和逐文件检查，记录公开下载 SHA-256。可复用本批次已通过的核验记录。例如 `Du.AutoMapper.Collection 11.0.0` 精确依赖 `Du.AutoMapper [14.0.0]`，因此引擎仍待索引或核验失败时，暂停 Collection 及依赖它的包。其他依赖均已满足的主包可继续上传。符号索引可独立推进，18 个目标全部读回是整套发行的完成条件。[NuGet 包验证与索引](https://learn.microsoft.com/en-us/nuget/nuget-org/publish-a-package#package-validation-and-indexing)

### 核对仓库签名以及签名前后的包内容

冻结的主包尚无仓库签名。按 nuget.org 服务索引公布的签名证书和信任链核验匿名下载的主包，包括签名时间戳。保留上传文件和下载文件各自的 SHA-256。逐路径对照归档内文件清单和解压内容摘要，只接受经验证的仓库签名项 `.signature.p7s` 及其产生的归档封装差异。DLL、nuspec、许可及说明等内容都必须匹配。若发布者需要预先签名、改元数据或重打包，将变化后的文件登记为新的候选输入，完成受影响的来源、符号和消费复验后再使用。[NuGet 仓库签名](https://learn.microsoft.com/en-us/nuget/api/repository-signatures-resource) · [签名验证命令](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-nuget-verify)

每个符号包分别保留上传原件摘要和服务受理结果。从公开主包取 DLL 的调试标识和 PDB 校验信息，向 `https://symbols.nuget.org/download/symbols` 获取 18 个目标所需的 Portable PDB，核对其标识、内容摘要与冻结符号一致。主包下载和符号读取各自留证。[nuget.org 符号服务](https://learn.microsoft.com/en-us/nuget/create-packages/symbol-packages-snupkg)

### 在固定模板中观察实际公开消费

现有模板入口会把冻结包复制进本地 feed。公开模式复用模板转换、DLL 校验、SQL 与浏览器断言，为两代运行时各建独立空缓存、空构建输出和显式 NuGet 配置。唯一包源是 `https://api.nuget.org/v3/index.json`，清除继承源、回退目录和旧 HTTP 缓存来源。模板自身的项目引用和已登记的 SDK/共享框架照常使用。逐入口按包 ID 和版本核对实际来源。对缓存中实际还原的 `.nupkg` 计算 SHA-256，与该版本已验签且逐文件核对通过的匿名下载摘要比对。按所选 TFM 和包内资产路径，把编译引用、Release 输出及进程实际加载的维护 DLL 逐一对照冻结 DLL 的 SHA-256。仅随包输出的 DLL 记录为按需加载。本地冻结源模式继续使用原有来源和整包摘要断言。[现有消费入口](../../../../eng/r4_template_consumer.py) · [四入口校验](../../../../eng/r4_template_assets.py)

在 macOS ARM64 上用固定 SDK 构建 `net9.0`、`net10.0` 两代的 Web.Host 与 Migrator。逐入口记录还原图、包源、所选 TFM 资产、输出以及实际加载 DLL，区分仅随包输出的按需依赖。复用隔离测试库和冻结 Angular 客户端，两个 Migrator 先后作用于同一候选库。两个 Host 各完成一次 `Default` 租户登录和有 `Pages.Users` 权限的用户查询。核对固定搜索词仅命中 ID 3、请求对应的 SQL 库，以及候选库登录计数依次增加、对照库计数不变。[参考版本与业务观察值](../../../../docs/maintenance/r4-release-candidate.md#实测支持矩阵)

### 按发行说明从新库安装

在单独的干净目录，从公开仓库匿名取得上表的模板提交。使用独立空 NuGet 缓存、nuget.org 和新的空 SQL Server 测试库，逐条执行发行说明草案中的 `net10.0` 命令。说明须包含前置环境、模板换包及目标框架调整、测试连接配置、Migrator 和 Web.Host 的运行步骤。若要用发行 tag 之后新增的脚本，给出脚本所在公开仓库的固定提交链接和取用命令。以 Migrator 成功退出、新库出现模板迁移记录、Web.Host 提供说明中约定的 HTTP 成功响应为通过条件。记录模板和脚本提交、实际命令及上述结果。所需输入限于公开材料、说明中列出的工具和消费者自行提供的测试数据库连接。历史报告、冻结 Angular 输出和备份用于上一节的维护者业务回归。

新安装示例列明本批实测的 .NET `10.0.15`。`net9.0` 在矩阵中标为“存量应用迁移兼容性实测”，列明运行时 `9.0.10` 和微软结束 .NET 9 支持的日期 `2026-11-10`。[本地实测矩阵](../../../../docs/maintenance/r4-release-candidate.md#实测支持矩阵) · [.NET 官方支持周期](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core)

## Risks / Trade-offs

- **服务超时、受理后待索引或出现重复版本。** 从最近一次记录续作，回读所有者、主包内容、符号和当前可见性。按服务提示限次轮询，保留待核实状态。可证明同批的项目继续后续步骤，冲突、验证失败或来源不明的项目停止；单凭重复响应无法认定成功。
- **公开后发现错误。** 保留既有版本与 tag 的记录、已上传清单和诊断。若已发布的内容需要更正，提出新版本，重新核对受影响的依赖范围与候选包。撤列或处置已公开版本按单独授权办理。
- **原始交接中带有验证机路径和数据库备份。** GitHub Release 使用从交接草案整理的公开说明及可公开的校验清单，只列公共 URL、版本、支持范围和必要摘要。数据库备份、原始日志和本机目录由发布者保管。

## Migration Plan

13 个主包和 18 个符号目标均可从公共服务读回并核验通过，且两代四个入口的业务回归和发行说明的新库安装均通过后，在已核实的 tag 上发布 GitHub Release。为消费者提供从原包名切换到精确维护版本的还原入口、版本矩阵、原版回退说明及两份恢复点的写入边界。公开说明明确标出公开源实测、同批历史回退结果和仍待验证的平台。回读已发布说明与包链接，更新主仓发行记录和路线图，作为进入 R5 的依据。[回退记录](../../../../docs/maintenance/r3-original-template-rollback.md#正式运行结果)
