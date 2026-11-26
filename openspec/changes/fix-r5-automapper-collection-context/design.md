# 集合映射上下文补丁设计

## Context

R5 首轮已随主仓 `4d051e841ec1641a4ec0fcdc9540cb1f6327654d` 交付并归档。行为对照使用 R4 tag `v10.5.1` 所指的 `5758c8186b68dcc42ecc90164cf9d3f53cf3345e` 和相应公开包。发行引擎的 `CollectionMapper.MapCollectionCore` 读取包含成员的深度设置，而生成上下文检查时只查询元素映射。这里涉及两个不同的类型映射，即使元素本身没有深度设置，包含成员的映射也可能需要上下文。[发行源码](../../../AutoMapper/src/AutoMapper/Mappers/CollectionMapper.cs) · [首轮审查报告](../../../docs/maintenance/r5-first-maintenance-review.md#后续补丁的范围与验收)

## Goals / Non-Goals

本轮以可在本地安装、验收和回退的补丁组合作为交付点。开放泛型注册、其他上游修复、共享运行时服务公告的补查、扩展平台及公开发行沿用各自的维护记录。首轮三则映射公告的处置作为回归基线。

## Decisions

### 在公开实包上隔离顺序影响

旧版对照由独立消费者运行，引擎仅通过 `PackageReference` 精确引用 `Du.AutoMapper [14.0.0]`，在隔离空缓存从 nuget.org 还原。核对实际还原图的包身份、资产及来源，并将还原所得 `.nupkg` 的 SHA-256 与 R4 的已验公开下载记录对账。采用公开清单的 `mainPackage.anonymousDownloadSha256`，它与 `verified-downloads.json` 中的 `downloadSha256` 对应。登记进程报告的实际加载路径，核对该文件与这份归档内 `lib/net8.0/AutoMapper.dll` 的 SHA-256 一致。[R4 公开下载记录](../../../docs/maintenance/r5-first-maintenance-review.md#发行版本和上游基点) · [R4 公开包消费入口](../../../docs/maintenance/r4-release-candidate.md#公开源模板消费)

现有单元测试通过 `ProjectReference` 使用引擎源码，`RecursionProbe` 在 `CandidateVersion` 为空时也走源码路径。运行落入任一源码路径、还原了其他包，或来源及摘要不符时，修正输入后复测，发行包证据以重新对账通过的运行记录为准。[单元测试项目](../../../AutoMapper/src/UnitTests/AutoMapper.UnitTests.csproj) · [探针项目](../../../AutoMapper/src/RecursionProbe/RecursionProbe.csproj)

用两个复用同一集合类型的业务成员和少量固定 DTO 建立有界用例，事先确定预期。两侧均通过未启用 Collection 扩展的普通 `Map` 独立运行每种顺序，每次新建等价配置，使用等价输入、目标初始状态和同一待测调用。预热对照固定注册顺序，只交换预热调用顺序。冷启动对照无预热，只交换等价映射的注册顺序。按原条件重复以确认结果或异常稳定。另验元素自身需要上下文、默认与显式深度以及共享对象引用。[上游普通集合修复](https://github.com/LuckyPennySoftware/AutoMapper/pull/4651) · [注册顺序回归](https://github.com/LuckyPennySoftware/AutoMapper/pull/4675) · [后续维护线回补](https://github.com/LuckyPennySoftware/AutoMapper/pull/4676)

正式冻结及交接前，按增量规范判定并记录复现的是注册还是预热影响，保存两侧用例条件、结果或异常和实包对账。若各顺序出现相同错误，记录已证实的业务偏差和仍待证的顺序影响。若未观测到偏差，记录试过的条件。顺序影响待证时回到首轮维护评估，初步分析和探索性构建可先行。[冻结前判定](specs/automapper-package-consumption/spec.md#scenario-正式冻结前验证顺序影响及候选结果)

### 按 MIT 14 基线独立修正内建映射

在引擎 `maintenance/v14` 的 R4 生产提交上从既有上下文机制实现最小修正，使包含成员和元素各自的上下文要求都得到满足，并保留二者均无要求的普通路径。上游新版本用于确认可观察行为。实现和回归用例独立编写，记录来源、许可及署名。[兼容与许可指南](../../../docs/compatibility/automapper.md#四许可以固定-mit-基线维护另审查每个新补丁)

在 macOS ARM64 干净检出上保留普通 Release 和候选构建对原版 `AutoMapper 13.0.0` 的 ApiCompat。另从已验公开 `Du.AutoMapper 14.0.0` 主包提取 `lib/net8.0/AutoMapper.dll` 作为左侧，实际候选主包中的对应 DLL 作为右侧运行 ApiCompat。记录两项基线各自的比较结果、复跑入口、包 ID、版本、资产路径和包及 DLL 的 SHA-256，并核对程序集身份、强名称、公钥标记、公开 API、目标框架和 PDB。[既有 API 比较入口](../../../AutoMapper/src/AutoMapper/ApiCompat/verify-release.sh) · [引擎生产入口](../../../AutoMapper/src/AutoMapper/ApiCompat/README.r4.md)

先制备引擎主包及符号包，由验收端独立登记本轮引擎主包与包内 `net8.0` DLL 的 SHA-256。三包批次建立前，引擎验证入口显式消费这两个摘要，从隔离空缓存还原实际候选，对账归档、包内 DLL、Release 输出及进程实际加载的 DLL，执行普通集合对照和三则公告的既有回归。兼容历史 R4 固定批次的复验入口。公告范围和 CLR 低栈证据沿用稳定规范，报告分别标明测试注入与实际 CLR 低栈触发的观测结果。[稳定消费规范](../../specs/automapper-package-consumption/spec.md) · [R4 引擎消费入口](../../../eng/r4_engine_consumer.py)

### 仅为受精确依赖约束的三个包准备新版本

逐份核对 13 个首发公开包的 SHA-256 和各目标 nuspec 后，反向追踪涉及引擎的内部依赖，仅引擎、Collection、适配器需要新版本。下表是本地拟用的稳定格式版本，便于随后复用原封冻结的归档。2026-11-26 查询时三个拟用版本均未出现在 nuget.org 版本索引。正式冻结时再核对冲突，实际选用值随清单登记。

| 候选包 | R4 生产提交 | 拟用版本 | 本批内部依赖 |
| --- | --- | --- | --- |
| `Du.AutoMapper` | `f646d492df918d27b9ac96c086933570965efef3` | `14.0.1` | 无 |
| `Du.AutoMapper.Collection` | `306b49d7a59b7335a61d8116e1ab2f623a04740e` | `11.0.1` | 引擎 `[14.0.1]` |
| `Du.Abp.AutoMapper` | `bed57726b56f6f9de5c2d82e8dbe55e0130bddd0` | `10.5.2` | `Du.Abp [10.5.1]`、引擎 `[14.0.1]`、Collection `[11.0.1]` |

R4 的框架打包属性会把非核心包的框架依赖绑定到自身的 `PackageVersion`。适配器升版时须独立提供其内核依赖版本，否则将错误地要求尚未发行的 `Du.Abp [10.5.2]`。只在补丁打包路径上处理这项差异。按引擎、Collection、适配器顺序生成三份主包及相应符号包，核对实际 nuspec、PDB、API 和许可。保留普通构建和历史 R4 冻结入口。[框架打包属性](../../../aspnetboilerplate/nupkg/r4-candidate.props) · [Collection 打包入口](../../../AutoMapper.Collection/README.r4.md)

### 用独立清单组织混合包源的消费者验收

正式冻结时，将引擎归档及包内 DLL 逐项对账至已通过回归的实物及其独立登记的 SHA-256。有字节变化时，以新实物重新验证受影响的项目再冻结。由验收端独立登记候选清单 SHA-256。清单列出三个生产提交或可重放的源码树、六份归档和所选 DLL 摘要，并引用十个 R4 公开包的已验签下载摘要。[R4 冻结入口](../../../eng/r4_candidate_batch.py)

用精确包名指定三个候选的本地源，其他十个维护包与第三方依赖用 nuget.org。各侧使用独立空缓存，对照还原图、编译引用、输出与进程实际加载。每次空缓存还原前，检查实际临时目录、缓存和证据目录的可写性及所在卷的可用空间，按当轮用量准备。复用 R3 的独立 ABP 消费者和 R4 的模板资产断言，增加补丁输入方式，使历史固定清单仍能独立复验。单独验证只引用适配器时的四条边、已有对象更新、按键集合与 SQLite 投影，再验证整套模板。[下游消费入口](../../../eng/r3_automapper_verify.py) · [模板资产入口](../../../eng/r4_template_assets.py)

## Risks / Trade-offs

- 配置缓存可能让不同顺序相互影响。同一侧的每个独立顺序都从新 Mapper 配置开始，记录预热调用，不用偶发异常作为唯一通过条件。
- 模板某些入口只输出部分映射程序集。按入口记录“还原、编译、输出、实际加载”，按键集合由独立消费者实际执行，不能据模板输出目录推定已运行。
- 候选重新构建或改签会改变摘要。新的六件组合需重新关联受影响的消费证据。正式发行再用该批独立摘要验证公开下载、符号和消费者，OIDC 接入继续作为独立的待演练事项。[发行交接](../../../docs/maintenance/r5-first-maintenance-review.md#发行准备交接)

## Migration Plan

在固定模板 `2e9536872673a7ff1986a19e798c51684d16afe5` 上仅调整适配器直接引用，两个映射依赖按候选 nuspec 传递还原。用 R4 实测环境做同目标对照，`net10.0` 在新 SQL Server 测试库迁移并启动，另从存量 `net9.0` 到 `net10.0` 在同库接续。记录两套实际加载的共享运行时、30 条模板迁移、固定 Angular 客户端租户登录、`Pages.Users` 授权及唯一用户查询。[公开安装基线](../../../docs/maintenance/r4-public-install.md)

另在固定 `net10.0` 和同一个隔离 SQL Server 库中，依次实跑公开 R4 的完整 13 包组合、三个候选加十个 R4 包、完整 R4 三阶段。全程保留原库，以公开 R4 启动并在固定租户写入唯一可识别的业务记录，候选和切回 R4 后用同一授权入口查询，核对数据库、租户及同一记录身份和数据。逐阶段按既有范围核对 Web.Host 的 13 包和 Migrator 的 10 包，记录还原、编译、Release 输出及按需实际加载。复用其他用例的测试库时，明确标记切换三阶段的起始库状态和写入边界，包括登录等附带写入。数据库备份恢复如另行验证，独立记录恢复点及其后写入的影响。生产 tag、上传、公开回装和 Release 留给发行变更。[R4 公开消费基线](../../../docs/maintenance/r4-release-candidate.md#公开源模板消费) · [恢复点说明](../../../docs/maintenance/r3-template-net10-upgrade.md#恢复点与写入边界)
