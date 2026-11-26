# R5 首轮维护审查

审查截止为 `2026-11-26T05:39:07Z`（北京时间 2026-11-26 13:39:07）。本轮固定公开发行 `v10.5.1` 和 R4 首发两代固定模板的四个入口。发行输入在 2026-11-26 通过公开资料和本地留存原件复核。依赖和进程版本取自历史观测。

## 本轮决定

**维护包需补丁。** 第一优先项是修复 `Du.AutoMapper 14.0.0` 的内建集合映射上下文。发行源码计算深度时使用包含成员的 `TypeMap`，而集合映射只按元素映射发出上下文检查。上游 #4651 和 15.x 回补 #4676 修正了这一不一致，#4675 增加了注册顺序相关回归。证据来自发行源码与上游修复，本轮未作新的动态业务复现。已有三则 AutoMapper 安全公告的回补仍由 R4 实包证据支持。[源码及回补对照](#较新映射维护线的其他修复) · [三则公告证据](#映射引擎公告与实包)

| 负责方 | 行动 |
| --- | --- |
| 维护包 | 在 `dusdong/AutoMapper` 首发提交上准备内建集合映射的最小修复。发行组合另核对适配器与 Collection 扩展的精确依赖。 |
| 模板 | 继续以固定模板为消费基线。模板的直接和传递包图目前没有支持单独发补丁的证据。后续用相容的新包组合在空缓存还原，并复验 `net10.0` Web.Host、Migrator、新库安装和同库接续。 |
| 运行环境 | `.NET 9` 已于 2026-11-10 停止支持，`9.0.23` 是末版共享运行时。以两套 .NET 和 ASP.NET Core 共享框架都达到受支持的补丁版本为目标。截止时 .NET 10 两套共享框架的服务基线均为 `10.0.15`。 |
| 使用者 | 存量 `net9.0` 应用按公开路径迁移到仍受支持的 `net10.0` 组合，并确认部署进程实际加载的两套共享框架。使用内建集合和 `MaxDepth` 的应用，在采用候选前用自身配置核对映射结果。自定义包图和已生成的 Identity 代码按实际依赖及用途复查。 |

[公开安装和验证](r4-public-install.md) · [历史同库迁移复验](r3-template-net10-upgrade.md#完整运行复验) · [官方支持周期](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core)

## 逐项处置

| 对象 | 处置及复查条件 |
| --- | --- |
| AutoMapper #4651、#4676、#4675 | **需处理，第一优先。** 由引擎补齐包含成员的上下文检查，并用固定 14 基线的注册及预热顺序回归验收。[后续修复对照](#较新映射维护线的其他修复) |
| AutoMapper #4607 / #4567 | **暂缓，单独评估。** 上游明确记录 14.0.0 开放泛型注册顺序问题，发行源码仍有旧实现。修复会触及注册与继承配置，待固定 14 组合能证明失败并覆盖旧注册顺序时重新排序。 |
| AutoMapper #4604 | **待核实。** 发布树保留同一源表达式传递路径，尚需用 14 基线验证可空扩展方法与 `MapAtRuntime` 的组合后再决定回补。 |
| AutoMapper #4605 | **暂缓。** 修改连续大写字母拆分会影响现有成员匹配。出现实际消费者故障且能覆盖旧命名配置时复查。 |
| AutoMapper #4655 | **暂缓。** 源值与转换后值的差异会改变现有委托条件结果。待有 14 版旧委托的具体场景和兼容对照后，再决定是否调整。后续引入的 DI 条件 API 部分在本发行中不适用。 |
| AutoMapper #4576、#4582、#4606、#4645 | **不适用。** 涉及较新许可分支的依赖与验证。固定引擎没有该许可路径。模板中的 JSON 和令牌依赖按自己的来源与选择版本判断。[依赖公告核对](#依赖公告核对) |
| AutoMapper #4681、Collection #192、#196 | **不适用。** 涉及后续目标框架及引擎大版本兼容。当前比较基线是固定的 14/11；较新组合采用时重新对照源码、许可、依赖和实包消费。[上游截止提交](#上游源码与回补) |
| 经典框架 #7219 | **已有修复。** 发行树保留回补及历史 SQLite 回归。若更换 EF Core、查询编译路径或 Provider，定向复验。[框架证据](#经典框架-7219) |
| AutoMapper GHSA-rvv3-g6hj-g44x | **已有修复。** R4 引擎的 `reference-graph` 验证深度和引用身份。引擎重新制包时复验实际加载的候选 DLL。[实包证据](#映射引擎公告与实包) |
| AutoMapper GHSA-6vhm-j9h7-f9gh | **已有修复。** R4 的 `constructor-depth` 验证构造深度及异常后的上下文恢复。引擎重新制包时复验。[实包证据](#映射引擎公告与实包) |
| AutoMapper GHSA-gpwp-5797-mjff | **已有修复。** R4 的 `runtime-dispatch` 和低栈组合证据覆盖其已声明的范围，实际 CLR 低栈触发仍未观测。引擎重新制包时复验组合证据。[实包证据](#映射引擎公告与实包) |
| 其余已匹配的 NuGet / GitHub 包身份和版本 | **本轮无需包变更。** 206 个组合成功对照为空。更换直接或传递依赖、出现新增或修订公告时，重算实际消费图。[两源查询范围](#依赖公告核对) |
| 历史 `9.0.10` 两套共享运行时 | **需处理，运行环境与消费者。** 原公告已确认 .NET 和 ASP.NET Core 的 macOS ARM64 版本命中，.NET 9 已结束支持。实际功能适用性见服务明细，迁移应落到支持中的组合。[对应服务记录](#microsoft-共享运行时服务公告) |
| 历史 `10.0.15` 两套共享运行时 | **已达到截止时服务基线。** 发布后续服务更新或部署运行时改变时复查。 |
| Windows/Linux 特定带外公告、CVE-2026-105544 | **历史实测组合不适用或已有修复。** Windows 和 Linux 带外平台项不属于该 macOS ARM64 历史组合。VSTest 修复属于 SDK，已实测的 SDK `10.0.404` 达到公告版本。[产品范围对照](#microsoft-共享运行时服务公告) |
| CVE-2026-118747、CVE-2026-118741 | **固定输入不适用。** 受影响的独立 Cbor 或 Identity 代码生成包均未出现在四图。固定模板使用自己的重设密码流程。使用这些包或派生生成代码的消费者须单独检查。 |
| CVE-2026-56158 | **待核实，运行环境。** 已列于 Microsoft 9.0.18 服务元数据，单条公告的组件范围及修订时间仍缺证。在 MSRC 原条目或对应 CVRF 可读时，按实际加载版本、操作系统和公告组件范围复查。当前维护包补丁决定有独立的源代码证据。[MSRC 原条目](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2026-56158) · [补查记录](#microsoft-共享运行时服务公告) |

## 后续补丁的范围与验收

1. **实现范围。** 以 [AutoMapper 发行提交](https://github.com/dusdong/AutoMapper/commit/f646d492df918d27b9ac96c086933570965efef3)为起点，修正内建 `CollectionMapper` 对包含成员的类型映射的上下文检查。沿用固定 14 的 MIT 基线，保留许可与署名。根据公开行为和既有用例独立实现，分别审查后续代码的许可。保留 `Du.AutoMapper` 包身份、`net8.0` 资产、程序集身份、公开 API 和三则公告的既有行为边界。Collection 扩展的按键集合更新是兼容回归面。[许可与兼容指南](../compatibility/automapper.md#四许可以固定-mit-基线维护另审查每个新补丁)
2. **行为与实包复验。** 对初次使用、预热后及注册顺序变化的普通集合映射复验上下文，再覆盖默认和显式深度、元素映射、引用保持、已有对象更新、按键集合、关系型查询投影和三则旧公告。用 Release 主包从隔离空缓存安装，核对包内、编译、输出及进程实际加载的唯一引擎 DLL 摘要。沿用映射独立消费者和 R4 模板入口，并将已发布 `14.0.0` 用作对照。[引擎实包入口](../../AutoMapper/src/AutoMapper/ApiCompat/README.r3-engine.md#完整实包行为复验) · [下游实包复验](r3-automapper-downstream.md#主仓实包消费与复验) · [R4 消费验收](r4-release-candidate.md#公开源模板消费)
3. **发包与回退边界。** 已验签的 `Du.Abp.AutoMapper 10.5.1` 和 `Du.AutoMapper.Collection 11.0.0` 的 nuspec 都精确依赖 `Du.AutoMapper [14.0.0]`，前者也精确引用 `Du.AutoMapper.Collection [11.0.0]`。单独安装更新后的引擎无法满足这些约束。单独补丁的发行准备应按实际闭包决定所需适配器及 Collection 依赖元数据变更和发布版本，把引擎源码修复与依赖版本变更分别验收。应用出现兼容问题时，回退到上一套可还原的 R4 版本组合及其部署产物，可恢复旧映射行为，也会恢复本轮发现的引擎缺口。应用包回退只影响部署产物。若另有数据库变更，按独立验证过的恢复点处理，选择升级前备份会舍弃其后的写入。[冻结依赖与发布者交接](r4-release-candidate.md#发布者交接) · [R4 历史回退矩阵](r4-release-candidate.md#实测支持矩阵)

### 发行准备交接

补丁进入发行准备时，由验收端独立登记该批冻结清单的 SHA-256。公开回读 `eng/r4_public_release.py` 与消费侧 `eng/r4_template_assets.py` 使用同一可信摘要，并保留 R4 固定批次的复验入口。逐包检查直接内部依赖已匿名回读、验签且逐文件核对内容与冻结包一致后，再进入其依赖方上传。完成公开符号、干净公开源消费与新库安装验收后，再发布对应的 Release。[公开回读入口](../../eng/r4_public_release.py) · [消费对账入口](../../eng/r4_template_assets.py) · [公开发行规范](../../openspec/specs/public-package-release/spec.md)

主仓 GitHub Actions OIDC 是后续可选的待演练途径。若采用，第一轮用只读 job 复查 R4 固定批次、依赖顺序及公开回读结果，并替换独立副本中的一个包，确认摘要不符可定位且在上传前停止。凭据兑换与真实上传留给另获授权的发行步骤。[待演练手册](r4-release-candidate.md#github-actions-受信任发布接入建议)

## 本轮采用的支持范围

沿用 R4 的实际模板组合。运行环境为 macOS ARM64，SQL Server Developer `16.0.4236.2`，SDK `10.0.404`。公开 `net10.0` 新库安装验证 Migrator 与 Web.Host，.NET 与 ASP.NET Core 均为 `10.0.15`。公开同库接续验证两代 Web.Host、Migrator 及固定 Angular production 客户端的租户登录和授权查询。`net9.0` 的 `9.0.10` 仅作存量迁移历史证据。原版两条回退来自同批冻结源的本地验收。Windows、Linux 原生完整消费者、其他数据库 Provider 及不同 Angular 组合列为待验。已有 SQLite 及 Windows 源码验证的覆盖范围见各自记录。[R4 实测支持矩阵](r4-release-candidate.md#实测支持矩阵) · [公开源验收](r4-release-candidate.md#公开源模板消费) · [Windows 源码迁移验收](r1-dotnet10-runtime-migration.md)

## 下轮检查点

| 来源 | 接续条件及输入 |
| --- | --- |
| 三个原上游 | 以上游查询表中的完整 SHA 为起点，检查分支或发行新增提交、公开仓库公告、适用旧基点的回补及已列待核实项。每次查新发行也确认版本的目标框架和许可边界。[上游查询表](#上游源码与回补) |
| NuGet 和 GitHub Advisory Database | 从全球索引 `base` 2026-11-20T05:34:20.7684268Z、`update` 2026-11-26T05:34:57.7265357Z 起对比公告页，GitHub 从本轮截止时间复核新增、修订和撤回。图改变时用所有入口实际解析版本和两套维护包身份重新全量匹配。[依赖公告核对](#依赖公告核对) |
| Microsoft 服务记录 | 以 `9.0.23` 末版、`10.0.15` 截止版与对应公告修订为起点。出现新服务版、配置或平台变化时复查实际加载的两个共享框架。单条环境缺证按 [MSRC CVE-2026-56158](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2026-56158) 和 [Microsoft 2026 年 7 月 CVRF](https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Jul) 续查。 |
| 发行与消费者 | 出现新包、模板、Provider、Angular 或部署组合时，记录实际包图和进程，按相应入口形成新的支持证据。首发复查沿用本文固定的 tag、清单和原始四图。[发行输入](#发行版本和上游基点) · [模板原图](#固定模板的还原图) |

## 发行版本和上游基点

GitHub Release `458933029` 发布于 `2026-11-26T03:59:33Z`。匿名回读的附注 tag 对象为 `338cc2c83bc61c06047f4f98298aec629c8ca781`，解引用提交为 `5758c8186b68dcc42ecc90164cf9d3f53cf3345e`。本地 `git rev-parse v10.5.1^{}` 返回同一提交。主仓收尾及本轮工作基点为 `ed0e156150403874e776ca2a4a19128e9c72a0f3`。[公开发行](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1) · [收尾提交](https://github.com/dusdong/du.aspnetboilerplate/commit/ed0e156150403874e776ca2a4a19128e9c72a0f3)

实际下载的 `R4-PACKAGE-CHECKSUMS.json` SHA-256 为 `c3a905b6a6373a59236214f94fce953abb530fc61c80a7fe94ff99f028f534b0`，与 GitHub Release API 附件摘要一致。清单记录每个匿名下载主包、原始主包和符号包上传件，以及 18 个公开 PDB 的摘要。将其中的 13 个包逐项与 [R4 组合清单](../../eng/r4_release_candidate.json)和原轮 `verified-downloads.json` 对账，ID、版本、生产仓、上传及匿名下载摘要一致。原轮 `release-manifest.json` 和 `verified-downloads.json` 的文件 SHA-256 也与公开清单引用一致。验签与 PDB 核验沿用 R4 实际发行记录。[公开校验清单](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json) · [发行验收](r4-release-candidate.md)

从 `git ls-tree v10.5.1` 读取三个生产 gitlink，与公开清单和 R4 组合清单逐一核对。上游比较点由原上游 tag 的完整 SHA 确定，并与[历史基线登记](release-baseline.json)核对。在本地三个组件仓中，`git merge-base --is-ancestor <上游基点> <生产提交>` 均退出 0。R4 组合清单的 `producers.*.baseCommit` 是候选生产对照点。下表的上游比较点用于本轮审查。

| 生产仓 / 主仓路径 | 发行 gitlink | 上游比较点 |
| --- | --- | --- |
| [dusdong/aspnetboilerplate](https://github.com/dusdong/aspnetboilerplate) · `aspnetboilerplate` | `bed57726b56f6f9de5c2d82e8dbe55e0130bddd0` | [aspnetboilerplate/aspnetboilerplate · v10.5.1](https://github.com/aspnetboilerplate/aspnetboilerplate/tree/v10.5.1) · `6c4580c5e7ea41154696c071a53fd200059a768b` |
| [dusdong/AutoMapper](https://github.com/dusdong/AutoMapper) · `AutoMapper` | `f646d492df918d27b9ac96c086933570965efef3` | [LuckyPennySoftware/AutoMapper · v14.0.0](https://github.com/LuckyPennySoftware/AutoMapper/tree/v14.0.0) · `bf76a5819e1bad7af7db5382bf0f3a0178048a15` |
| [dusdong/AutoMapper.Collection](https://github.com/dusdong/AutoMapper.Collection) · `AutoMapper.Collection` | `306b49d7a59b7335a61d8116e1ab2f623a04740e` | [AutoMapper/AutoMapper.Collection · v11.0.0](https://github.com/AutoMapper/AutoMapper.Collection/tree/v11.0.0) · `eafbf005becf73f989e1b1c0d52e8699439f837c` |

下表原上游包 ID 逐一取自对应比较点的项目文件 `PackageId`。

| 发行包 ID | 版本 | 生产仓路径 | 原上游包 ID |
| --- | --- | --- | --- |
| `Du.Abp` | `10.5.1` | `aspnetboilerplate` | `Abp` |
| `Du.Abp.AspNetCore` | `10.5.1` | `aspnetboilerplate` | `Abp.AspNetCore` |
| `Du.Abp.AspNetCore.SignalR` | `10.5.1` | `aspnetboilerplate` | `Abp.AspNetCore.SignalR` |
| `Du.Abp.AutoMapper` | `10.5.1` | `aspnetboilerplate` | `Abp.AutoMapper` |
| `Du.Abp.Castle.Log4Net` | `10.5.1` | `aspnetboilerplate` | `Abp.Castle.Log4Net` |
| `Du.Abp.EntityFramework.Common` | `10.5.1` | `aspnetboilerplate` | `Abp.EntityFramework.Common` |
| `Du.Abp.EntityFrameworkCore` | `10.5.1` | `aspnetboilerplate` | `Abp.EntityFrameworkCore` |
| `Du.Abp.Web.Common` | `10.5.1` | `aspnetboilerplate` | `Abp.Web.Common` |
| `Du.Abp.Zero.Common` | `10.5.1` | `aspnetboilerplate` | `Abp.Zero.Common` |
| `Du.Abp.ZeroCore` | `10.5.1` | `aspnetboilerplate` | `Abp.ZeroCore` |
| `Du.Abp.ZeroCore.EntityFrameworkCore` | `10.5.1` | `aspnetboilerplate` | `Abp.ZeroCore.EntityFrameworkCore` |
| `Du.AutoMapper` | `14.0.0` | `AutoMapper` | `AutoMapper` |
| `Du.AutoMapper.Collection` | `11.0.0` | `AutoMapper.Collection` | `AutoMapper.Collection` |

## 固定模板的还原图

模板 gitlink 为 `2e9536872673a7ff1986a19e798c51684d16afe5`，树为 `b6a9e7386e3073e820eed83fe418d6c6096468bc`。R4 的 `r4-template-upgrade-public` 通过轮于 `2026-11-26T03:42:45Z` 至 `03:45:36Z` 在发行提交上运行，执行树为 `d3a87251d36e1bed4ddfbf8578ce62f5dc5c02eb`。模板应用了 R4 包引用和目标框架补丁，在 macOS ARM64 用 SDK `10.0.404`、隔离空缓存及仅含 nuget.org 的配置构建 Release。通过轮原件位于主仓下 `.git/publish-r4-first-public-release/package-6/upgrade/runs/r4-template-upgrade-public-vjc1kvc3/`，其 `report.json` SHA-256 为 `ef4a2787d6cc840d25584ea2232415289a3d1eeb625db776db98f5e5187287f9`。下表路径相对于该目录。每份文件的 SHA-256 均与各自构建报告的 `rawAssets` 登记一致。

| 目标键 | 入口 | 包数（直接 / 传递） | 维护包数 | `Microsoft.IdentityModel.JsonWebTokens` | 原图 | SHA-256 |
| --- | --- | ---: | ---: | --- | --- | --- |
| `net9.0` | Web.Host | 116（2 / 114） | 13 | `8.0.1` | `net9-build/raw-assets/Web.Host.project.assets.json` | `f5f82d02bd0aa299355492c98c34bda407197ac1ef94bb1f247bb7441d705b1f` |
| `net9.0` | Migrator | 81（1 / 80） | 10 | `6.35.0` | `net9-build/raw-assets/Migrator.project.assets.json` | `e6bd8aa48ea2b0fdabb25ee0d73a5bbddcb45212c2def80e6f59d31ab1fc1f53` |
| `net10.0` | Web.Host | 94（2 / 92） | 13 | `8.19.2` | `raw-assets/Web.Host.project.assets.json` | `cca797926ef2ed31631d7d10f07e9b52d74e7c84042191681d2d1c45a8bd9321` |
| `net10.0` | Migrator | 66（1 / 65） | 10 | `7.7.1` | `raw-assets/Migrator.project.assets.json` | `ebd39927a4102e1ccaf0fa4c1c3073c96182bad68733d49136d7da9b827e7b86` |

[依赖清单 TSV](r5-first-maintenance-dependencies.tsv)共 357 条，以 TFM、入口、ID、解析版本定位。所有条目与同轮 `assets-inventory.json` 对账，来源均为 `https://api.nuget.org/v3/index.json`。46 个维护包入口实例的缓存归档 SHA-256 均与公开清单的 `anonymousDownloadSha256` 一致。两代 Migrator 均少三个 Web 专用包 `Du.Abp.AspNetCore`、`Du.Abp.AspNetCore.SignalR` 和 `Du.Abp.Web.Common`。

### 提取及复查方法

1. 从主仓使用 `shasum -a 256` 核对四份原图。读取对应 `targets[TFM]` 的 `type=package` 节点，用节点键 `ID/版本` 获取实际解析版本。将带 SDK 下载登记的引用包与 `frameworkReferences` 保持在闭包之外。
2. 从 `project.frameworks[TFM].dependencies` 中的 `target=Package` 得到入口直接引用。以这些声明及 `project.restore.frameworks[TFM].projectReferences` 为起点，跟随目标图中项目和包节点的 `dependencies`，按 ID（忽略大小写）解析到选中的节点。依赖边上的版本表示所请求的约束，TSV 上的版本取自选中的节点。路径用 `>` 分隔，`-` 表示该列无对应记录。项目节点省略共同前缀 `AbpCompanyName.AbpProjectName.` 和模板内部版本 `1.0.0`。
3. `applicationPath` 从模板应用的包或项目引用出发，`toolPath` 从 EF Core Design 工具引用出发，按路径类别各保留一条最短证据链。编译选中的分析器可从应用链引入，见对应图旁 `assets-inventory.json` 的 `selectedPackageAnalyzers`。TSV 的 `selectedAnalyzer` 记录该观测，只有分析器资产的包记在工具路径。两个路径同时出现表示两条来源均成立。例：`net9.0` Web.Host 的 `System.Text.Json 9.0.5` 同时由 SQL Server 依赖与 EF Core Design 引入，也有生成器入选。
4. TSV 的 `releaseOutput` 取自入口的 `<入口>-output.json` 中的 `packageCopies`。该列记录有包资产进入历史 Release 输出。实际进程加载应查对应 `*-loaded.json`。例如 `net10.0` Web.Host 的 `Microsoft.Build.Framework 18.0.2` 由 EF Core Design 引入，其包资产进入了输出。其实际执行情形仍需具体证据。

两个 Web.Host 图也可沿 `Web.Host > Web.Core > Microsoft.AspNetCore.Authentication.JwtBearer > Microsoft.IdentityModel.Protocols.OpenIdConnect > System.IdentityModel.Tokens.Jwt > Microsoft.IdentityModel.JsonWebTokens` 追溯样例包。两代 Migrator 图沿 SQL Server 依赖引入。查看某条边时，区分边上的请求版本和入口最终选中的版本。例如 `net9.0` Web.Host 的 SQL 客户端请求 JsonWebTokens `6.35.0`，最终选中的是 `8.0.1`。

两代均额外使用 `Microsoft.NETCore.App.Ref`、`Microsoft.AspNetCore.App.Ref` 和 `Microsoft.NETCore.App.Host.osx-arm64`，对应 `assets-inventory.json` 的 `sdkUsedPacks`。两处 `net9.0` 入口使用 nuget.org 下载的 `9.0.23` packs，两处 `net10.0` 入口使用 SDK 安装目录中的 `10.0.15` packs。二者是构建输入。真实进程的共享运行时版本见下文。

### 与 R4 归档后构建复跑对照

本轮只读比较 R4 已有的 `net10.0` 公开源构建复跑。原件目录为 `.git/publish-r4-first-public-release/package-8/archived-build/r4-template-build-public-qkbvkyuh/`，执行时间 `2026-11-26T04:30:48Z` 至 `04:32:05Z`。该轮使用相同发行提交、首发清单与下载登记，退出 0，`report.json` SHA-256 为 `976ef7fa98bb1fdef8115487b5c7f8ecbf1ebce75edc1e60b524cfee28e06912`。两个 `targets[net10.0]` 的节点和依赖边均一致，直接引用与唯一包源一致。原图摘要与复跑摘要的差异见以下两个从复跑报告回读的文件。顶层差异位于 `packageFolders` 与 `project` 中的还原路径。该次复跑范围是 `net10.0` 还原和构建，本轮未另行还原或运行模板。

| 复跑原图 | SHA-256 |
| --- | --- |
| `raw-assets/Web.Host.project.assets.json` | `99e68965cd43789c25e6b43cb0dec425d355949d7675122d61312dd019f3e6a3` |
| `raw-assets/Migrator.project.assets.json` | `bd498a393962f5585cc86bddcac79a067524d3a11862974ee3ffa94b60f683c2` |

### 历史进程的共享运行时

从通过轮 `report.json` 的 `rounds.<phase>.host` 与 `sql.migrations.<phase>.launch` 读取相应 PID、退出码和启动路径。回读启动选择与观测器在同一 PID 采集的程序集路径和摘要。四个进程均记录退出 0。下表中的 .NET 由 `Microsoft.NETCore.App` 下加载的 `System.Private.CoreLib.dll` 确认。ASP.NET Core 由 `Microsoft.AspNetCore.App` 下加载的程序集独立确认，Web.Host 使用 `Microsoft.AspNetCore.Hosting.dll`，Migrator 使用 `Microsoft.AspNetCore.Identity.dll`。加载路径分别位于 `/usr/local/share/dotnet/shared/<framework>/<version>/`，与启动记录一致。[Web.Host 核验入口](../../eng/r3_template_net9_runtime.py) · [两代 Migrator 核验入口](../../eng/r3_template_net10_runtime.py) · [R4 实包对账入口](../../eng/r4_template_assets.py)

| TFM | 入口 | 历史 PID | .NET | ASP.NET Core | 通过轮的实际加载记录 |
| --- | --- | ---: | --- | --- | --- |
| `net9.0` | Web.Host | 33957 | `9.0.10` | `9.0.10` | `net9-host-loaded.json` |
| `net9.0` | Migrator | 33943 | `9.0.10` | `9.0.10` | `net9-migrator-loaded.json` |
| `net10.0` | Web.Host | 34173 | `10.0.15` | `10.0.15` | `net10-host-loaded.json` |
| `net10.0` | Migrator | 34140 | `10.0.15` | `10.0.15` | `net10-migrator-loaded.json` |

## 上游源码与回补

在 2026-11-26 回读原上游仓的分支、发行说明、compare API 及相关 PR。下表为本轮查询截止点。按包的上游比较基点起算，页数与 compare API 返回的提交总数一致。AutoMapper 三个分支有共同历史，各行提交数分别计数。同一分支未公开的补丁与其他产品线不在这些范围内。

| 原上游 | 检索范围和截止 SHA | 发行证据 |
| --- | --- | --- |
| aspnetboilerplate/aspnetboilerplate | `master` 与 `v10.5.1` 均为 `6c4580c5e7ea41154696c071a53fd200059a768b`。默认分支 `dev` 为 `21f57d282f542aa4221fc5cd5a4ac76346d8f5c7`，与基点的 compare 为分叉，dev 独有的两个提交均属 #7219。 | [提交对照](https://github.com/aspnetboilerplate/aspnetboilerplate/compare/6c4580c5e7ea41154696c071a53fd200059a768b...21f57d282f542aa4221fc5cd5a4ac76346d8f5c7) · [发行线](https://github.com/aspnetboilerplate/aspnetboilerplate/releases) |
| LuckyPennySoftware/AutoMapper | `release/15.x` 为 `c73acdd92eb1b57a4a152ed678bea68321aac895`，与 `v15.1.4` 相同，54 个提交。 | [提交对照](https://github.com/LuckyPennySoftware/AutoMapper/compare/bf76a5819e1bad7af7db5382bf0f3a0178048a15...c73acdd92eb1b57a4a152ed678bea68321aac895) · [v15.1.4](https://github.com/LuckyPennySoftware/AutoMapper/releases/tag/v15.1.4) |
| LuckyPennySoftware/AutoMapper | `release/16.x` 为 `c121622bb1644728ea50e8f35ff1488145db187a`，180 个提交。`v16.3.0` 为 `9c31182a3eb99d5191ccc71ee90105846830917f`。 | [提交对照](https://github.com/LuckyPennySoftware/AutoMapper/compare/bf76a5819e1bad7af7db5382bf0f3a0178048a15...c121622bb1644728ea50e8f35ff1488145db187a) · [v16.3.0](https://github.com/LuckyPennySoftware/AutoMapper/releases/tag/v16.3.0) |
| LuckyPennySoftware/AutoMapper | 默认分支 `main` 为 `79d10deec5881a617c38e7373f354694044bf83d`，180 个提交。 `v17.0.0` 为 `d14380da2e1a6f39395aa9816c73479ec6863162`，引入目标框架变化。 | [提交对照](https://github.com/LuckyPennySoftware/AutoMapper/compare/bf76a5819e1bad7af7db5382bf0f3a0178048a15...79d10deec5881a617c38e7373f354694044bf83d) · [v17.0.0](https://github.com/LuckyPennySoftware/AutoMapper/releases/tag/v17.0.0) |
| AutoMapper/AutoMapper.Collection | 默认分支 `master` 为 `5301edbc689a9696bdd7c396452669434e75989a`，与 `v13.0.0` 相同。6 个提交，覆盖 `v12.0.0` 的 `a35cd38fe6c3db44b3a70fc67b7bc6bf9c0e2051`。 | [提交对照](https://github.com/AutoMapper/AutoMapper.Collection/compare/eafbf005becf73f989e1b1c0d52e8699439f837c...5301edbc689a9696bdd7c396452669434e75989a) · [v12.0.0](https://github.com/AutoMapper/AutoMapper.Collection/releases/tag/v12.0.0) · [v13.0.0](https://github.com/AutoMapper/AutoMapper.Collection/releases/tag/v13.0.0) |

三个原仓的公开仓库级公告接口均返回 HTTP 200。经典框架和 Collection 各为 0 条，AutoMapper 为下文三条。这个空结果仅覆盖各仓公开仓库级公告。Collection 的 #192、#196 分别变更目标框架/AutoMapper 15 和适配 16；比较区间内无独立的 Collection 行为修复。AutoMapper 17 的 #4681 切换目标框架，本轮仍按固定 14 基点判定。后续每条线从上表完整 SHA 比较新增提交，并复看分支和新发行。[Collection #192](https://github.com/AutoMapper/AutoMapper.Collection/pull/192) · [Collection #196](https://github.com/AutoMapper/AutoMapper.Collection/pull/196) · [框架公告](https://github.com/aspnetboilerplate/aspnetboilerplate/security/advisories) · [Collection 公告](https://github.com/AutoMapper/AutoMapper.Collection/security/advisories)

### 经典框架 #7219

上游合并为 `21f57d282f542aa4221fc5cd5a4ac76346d8f5c7`，发布仓中的等效回补为 `d08617b51bb7c7e5d0bea942e7e10b2677240c35`，已核对是发行 gitlink 的祖先。逐一比对上游变更的 8 个运行时文件，7 个文件字节相同。`AbpEfCoreDatabase.cs` 的差异保留 EF Core 9 签名，在 .NET 10 附加对应的 `CompileQueryExpression` 签名，两个分支均进入 `BeginQueryCompilation` 作用域。发行树保留两项 SQLite 同步和异步嵌套回归；历史 R1 EF Core 套件 80 通过，隔离作用域定向复核 4 通过。历史证据对应 R1 .NET 9 与 SQLite，对其他 Provider 的相同行为仍待单独验证。[#7219](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7219) · [发行仓同文件](https://github.com/dusdong/aspnetboilerplate/blob/bed57726b56f6f9de5c2d82e8dbe55e0130bddd0/src/Abp.EntityFrameworkCore/EntityFrameworkCore/AbpEfCoreDatabase.cs) · [历史回归](r1-efcore-query-filter.md#回归结果)

### 映射引擎公告与实包

原版 `AutoMapper 14.0.0` 命中以下三则公告的 15.x 上界以下分段。发行 `Du.AutoMapper 14.0.0` 含独立实现的回补。本轮重读 R4 `evidence/engine/report.json`（SHA-256 `4ecacc317d22ddc15dbae85cc29bfecf976b3286971f50626416575e8fadfcdd`），逐项重算历史报告、输出及冻结主包内 DLL 的摘要。冻结主包为 `dd56c74c6088815b4bc5b7b09696c464849f8da43c5ba594e36ff010e6244e80`，三公告四个用例实际加载的 `lib/net8.0/AutoMapper.dll` 均为 `12fcba523f7f7199215764b29c5d330aa363c433fa14d4e72257ce835a87e5e1`。同摘要 DLL 在 R4 公开轮两个 Web.Host 中实际加载，两个 Migrator 中进入输出。应用通过 `Core > Du.Abp.AutoMapper/10.5.1 > Du.AutoMapper/14.0.0` 间接引入，两代的完整路径见依赖 TSV。[R4 验收](r4-release-candidate.md#实测支持矩阵) · [映射行为契约](r3-automapper-engine.md#公告处置与行为证据)

| 原仓公告 | 首发与修订（UTC） | 原版 14.0.0 命中区间 | 同一 DLL 的 R4 历史证据 |
| --- | --- | --- | --- |
| CVE-2026-32933 | 2026-03-13 15:35:18 / 2026-03-17 17:22:56 | `(,15.1.1)`。上游 15.x 发行说明指向 15.1.3 或以上，15.1.1 与 15.1.2 的发版分支有误。 | `reference-graph` 检查递归引用的深度、有界结果、引用身份及普通对象更新。[公告](https://github.com/LuckyPennySoftware/AutoMapper/security/advisories/GHSA-rvv3-g6hj-g44x) · [v15.1.3](https://github.com/LuckyPennySoftware/AutoMapper/releases/tag/v15.1.3) |
| CVE-2026-128082 | 2026-11-05 15:34:47 / 2026-11-13 18:36:50 | `(,15.1.4)` | `constructor-depth` 覆盖位置记录和自定义构造路径、默认或显式深度，以及普通异常后计数恢复。[公告](https://github.com/LuckyPennySoftware/AutoMapper/security/advisories/GHSA-6vhm-j9h7-f9gh) |
| CVE-2026-128081 | 2026-11-05 15:34:49 / 2026-11-13 18:34:45 | `(,15.1.4)` | `runtime-dispatch` 覆盖派生深度继承、接口等运行时映射及转换器。CLR 低栈分支由同 DLL 的 `MapCore` IL、官方契约和 `application-exception` 组合验收。历史应用探针受控注入异常，验证传播和恢复，CLR 低栈实际触发未观测。[公告](https://github.com/LuckyPennySoftware/AutoMapper/security/advisories/GHSA-gpwp-5797-mjff) · [.NET API 契约](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices.runtimehelpers.ensuresufficientexecutionstack?view=net-9.0) |

### 较新映射维护线的其他修复

| 上游来源 | 发行源码对照与适用范围 |
| --- | --- |
| #4651（`9b500d50afe327a66d9a0002208aee79b99651d5`）、15.x 回补 #4676（`fbe13adc89c2afc9a0669a7e25881df5db913f77`）和顺序回归 #4675 | **对发行引擎适用的独立缺口。** 发行 `CollectionMapper` 按包含集合成员的 `TypeMap` 判断深度，局部 `CheckContext` 仍只按元素映射判断。发行 `ExpressionBuilder` 还会把自引用的有效深度传到该路径。较新维护线补上包含成员的上下文检查，覆盖受注册与预热顺序影响的常规集合映射。改动归属引擎的内建集合映射，Web.Host 的 R4 业务记录及三公告探针没有覆盖该顺序回归。后续适合在 14 基线上验证上游回归，并保留默认和显式深度、引用身份、普通集合与按键集合更新。[#4651](https://github.com/LuckyPennySoftware/AutoMapper/pull/4651) · [#4676](https://github.com/LuckyPennySoftware/AutoMapper/pull/4676) · [#4675](https://github.com/LuckyPennySoftware/AutoMapper/pull/4675) · [发行源码](https://github.com/dusdong/AutoMapper/blob/f646d492df918d27b9ac96c086933570965efef3/src/AutoMapper/Mappers/CollectionMapper.cs#L65) |
| #4607（`ef2bba6f4508203fdb4bc5d85e5ad45d85cdc620`） | 开放泛型注册顺序问题由原仓 #4567 明确报告于 14.0.0。发行 `ProfileMap.Configure` 仍读取 `typeMapConfiguration.TypeMap`，上游改为按类型对查询全局注册表。适用的候选回补归属引擎，验证须覆盖旧应用注册顺序、继承及开放泛型组合。[#4567](https://github.com/LuckyPennySoftware/AutoMapper/issues/4567) · [#4607](https://github.com/LuckyPennySoftware/AutoMapper/pull/4607) · [发行源码](https://github.com/dusdong/AutoMapper/blob/f646d492df918d27b9ac96c086933570965efef3/src/AutoMapper/ProfileMap.cs#L169) |
| #4604（`d9c1fbb26af062520f06d5072b692e0497db6e06`） | `MapAtRuntime` 的可空成员与扩展方法组合。发行 `ExpressionBuilder.ContextMap` 直接传源表达式，上游对齐 `typePair.SourceType`。同一旧代码存在，定向回归应验证 14 的扩展和可空行为。[#4604](https://github.com/LuckyPennySoftware/AutoMapper/pull/4604) · [发行源码](https://github.com/dusdong/AutoMapper/blob/f646d492df918d27b9ac96c086933570965efef3/src/AutoMapper/Execution/ExpressionBuilder.cs#L168) |
| #4605（`eb80840fcaccf17dfe73b83e106649da14a831c8`）及 #4655（`6e8697bc44f02fb54ef6a556a7d134e63485299e`） | 发布树仍按单个大写字母分词，并向条件委托传映射后值。新行为会改变存量命名匹配或条件判断，需要分别评估契约。#4655 新版 DI 条件类型包装器属于后续 API，14 的旧委托路径需独立判断。[#4605](https://github.com/LuckyPennySoftware/AutoMapper/pull/4605) · [#4655](https://github.com/LuckyPennySoftware/AutoMapper/pull/4655) |
| #4576、#4582、#4606 和 #4645 | 这些项涉及 15+ 引擎的 JsonWebTokens 依赖、许可验证与诊断。发行 `Du.AutoMapper` 的包依赖为 `Microsoft.Extensions.Options 8.0.0`。固定模板中观测到的 JsonWebTokens 来源沿 JWT 或 SQL Server 路径，不能由回补许可相关 PR 解决。#4576 标题援引的 GHSA 实际列的是独立 `System.Text.Json` 版本，按所选包范围另行核对。[#4576](https://github.com/LuckyPennySoftware/AutoMapper/pull/4576) · [#4582](https://github.com/LuckyPennySoftware/AutoMapper/pull/4582) · [#4606](https://github.com/LuckyPennySoftware/AutoMapper/pull/4606) · [#4645](https://github.com/LuckyPennySoftware/AutoMapper/pull/4645) · [原公告](https://github.com/advisories/GHSA-8g4q-xg66-9fp4) |

## 依赖公告核对

2026-11-26 用 nuget.org 服务索引发现 `VulnerabilityInfo`。本机默认地址转去返回 2023 年索引的地区镜像。改由 NuGet 全球 CDN 取得同期索引及其中唯一的 `base`、`update` 两页，均 HTTP 200。更新时间分别为 `2026-11-20T05:34:20.7684268Z` 和 `2026-11-26T05:34:57.7265357Z`。全球索引和两页的解压 SHA-256 分别为 `3e639b32ea0fb978e26a66ffe1a2ef8391aac97c38bc6e960f4fc01c98c15d64`、`1eb8e70c6f384340d6033fc3c48fd9e5dbc5750d1dcd00d1463df4385637ae9a`、`4bea167a58dcd05bff4210a96618a9b284267c77f9159655582fb6879ee8d302`。下一轮从这两页的水位继续核对，索引换页时按新索引重读全页。[VulnerabilityInfo 接口](https://learn.microsoft.com/en-us/nuget/api/vulnerability-info) · [全球索引](https://apiprod-mscdn.azureedge.net/v3/vulnerabilities/index.json)

按四入口 357 条依赖覆盖 194 个不同发行 ID/解析版本组合，另加 13 个维护包的原 ID/版本，共 207 个。用 SDK `10.0.404` 附带的 `NuGet.Versioning` 按 ID 忽略大小写合并两页范围，使用 `VersionRange.Satisfies(NuGetVersion)` 对照解析版本。GitHub Advisory Database 的 NuGet 分类按所有实际 ID 和别名分 12 批查询，35 个去重的已审查公告返回，所有 127 个发行 ID 和 13 个原 ID 均进入查询，批次均无下一页。按截止时间、撤回状态和原始包区间复算，和 NuGet 均只命中上述 3 个 `AutoMapper 14.0.0` 原身份公告。其余 206 个组合在这两个来源和此次版本匹配中均为空。下一轮复核新增或修订公告，并用原作者范围核查别名命中。[GitHub Advisory API](https://docs.github.com/en/rest/security-advisories/global-advisories)

构建与应用同在闭包内，处理路径依实际引入证据。两代 Web.Host 的 `Microsoft.Build.Framework 17.8.3 / 18.0.2` 分别从 EF Core Design `9.0.5 / 10.0.15` 引入，只有后者记录包资产进入 Release 输出。 `net9.0` Web.Host 的 `System.Text.Json 9.0.5` 同有工具链和 SQL Server 链，且源生成器入选，当前不落入 #4576 援引的 `6.0.0–6.0.9` 或 `8.0.0–8.0.4`。四种 JsonWebTokens 版本亦各自核查，未匹配该两源公开记录中的相应区间。以上结论以固定输入为限，消费者更换设计工具、数据库依赖或 JWT 版本时须用自己的图重新匹配。[原公告](https://github.com/advisories/GHSA-8g4q-xg66-9fp4) · [逐入口路径](r5-first-maintenance-dependencies.tsv)

## Microsoft 共享运行时服务公告

2026-11-26 读取 Microsoft 的正式发行索引、两条线的发行元数据、CVE 明细及原始公告。已核对 `9.0.10–9.0.23`（从 2025-10-14 到 2026-11-10，共 14 个版本）及 `10.0.15`（2026-11-10；截至本轮无后续 10.0 正式版）。[服务明细 TSV](r5-first-maintenance-runtime-servicing.tsv)保留每次发行的两个共享运行时版本、CVE、原始链接、可取得的发表及修订时点和明确列出的 macOS ARM64 范围。其中 27 条条目显示 `9.0.10` 落入原公告明确提供的 macOS ARM64 版本区间。条目按发行分列，同一 CVE 可跨多次发行。版本元数据记录服务覆盖，具体适用性取决于对应原公告及应用实际使用的组件。[.NET 9 官方数据](https://builds.dotnet.microsoft.com/dotnet/release-metadata/9.0/releases.json) · [.NET 10 官方数据](https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json) · [.NET 9 CVE](https://github.com/dotnet/core/blob/main/release-notes/9.0/cve.md) · [.NET 10 CVE](https://github.com/dotnet/core/blob/main/release-notes/10.0/cve.md)

| 历史实际加载范围 | 证据和归属 |
| --- | --- |
| `net9.0` Web.Host、Migrator 的 `Microsoft.NETCore.App 9.0.10` | 例如 10 月带外 CVE-2026-111497 的 macOS ARM64 受影响区间为 `>=9.0.0, <9.0.22`，与应用是否使用相应 Brotli 解压有关。11 月 CVE-2026-109475 列出受影响到 9.0.22，9.0.23 修复，覆盖 macOS ARM64。固定运行时需由运行环境或消费者处置。[10 月 #494](https://github.com/dotnet/announcements/issues/494) · [11 月运行时公告](https://github.com/dotnet/runtime/security/advisories/GHSA-3g4v-f5gv-c7xf) |
| `net9.0` Web.Host、Migrator 的 `Microsoft.AspNetCore.App 9.0.10` | CVE-2026-70175 的 macOS ARM64 范围为 `9.0.0–9.0.20`，9.0.21 首修。11 月 CVE-2026-109476、114146、114147、114149 的 9.0 正式版范围截至 9.0.22，由 9.0.23 修复。两入口均加载此共享框架，各项实际功能适用性取决于使用路径。[10 月原公告](https://github.com/dotnet/announcements/issues/457) · [11 月 ASP.NET Core 公告](https://github.com/dotnet/announcements/issues/504) |
| `net10.0` 两入口的 `Microsoft.NETCore.App 10.0.15` 和 `Microsoft.AspNetCore.App 10.0.15` | 已达到两套共享框架的本轮服务基线，分别覆盖上列运行时和 ASP.NET Core 同期公告的修复版本。使用范围另查工具、独立包、生成代码及操作系统，不从 SDK 编号推断运行时补丁。[.NET 10.0.15 发行](https://github.com/dotnet/core/blob/main/release-notes/10.0/10.0.15/10.0.15.md) · [.NET Runtime 公告](https://github.com/dotnet/announcements/issues/498) |
| 其他产品范围 | 10 月带外 CVE-2026-70197 的 Windows 范围和 CVE-2026-114148 的 Linux tarball/源构建范围，与 R4 的 macOS ARM64 不同。CVE-2026-105544 属于 SDK/VSTest，R4 SDK `10.0.404` 已达到官方修复版本。CVE-2026-118747 属于独立 `System.Formats.Cbor`，四图均无该包。CVE-2026-118741 属于 Identity scaffolding 与其生成代码。固定模板采用自己的 `UserAppService.ResetPassword` 路径，两入口无相关 CodeGeneration 包。消费应用另查派生代码的邮件发送路径。[Windows 公告](https://github.com/dotnet/announcements/issues/493) · [Linux 公告](https://github.com/dotnet/announcements/issues/495) · [VSTest 公告](https://github.com/dotnet/announcements/issues/517) · [Cbor 公告](https://github.com/dotnet/runtime/security/advisories/GHSA-vmv3-wvjp-wqpj) · [Identity 公告](https://github.com/dotnet/announcements/issues/525) |

.NET 9 于 2026-11-10 结束支持，`9.0.23` 是最后的共享运行时版本，`9.0.10` 仅保留为历史迁移实测证据。.NET 10 为当前支持中的 LTS，官方索引的支持截止为 2028-11-14。后续从两个官方频道记录的最新版本与 11 月公告修订起点续查，并重新读取消费者实际加载的共享框架。历史 9.0 版本元数据列出的 CVE-2026-56158 有 MSRC 入口，MSRC 单 CVE 请求返回 HTTP 404，官方 2026 年 7 月 CVRF 请求成功但未列此 ID。本轮未取得组件明细与修订日期，应在 MSRC 原单条记录可读时补查。该缺证不改变已确认的 9.0.10 命中区间及结束支持状态。[官方支持周期](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core) · [发行索引](https://builds.dotnet.microsoft.com/dotnet/release-metadata/releases-index.json) · [MSRC 单条入口](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2026-56158)
