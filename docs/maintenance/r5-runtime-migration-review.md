# R5 运行时迁移与增量维护审查

2026-11-26，从首轮截止 `05:39:07Z` 接续，官方来源查询至 `10:12:55Z`。公开 `v10.5.1`、固定模板和两代四张包图的输入一致。微软两套 .NET 10 共享框架的目标仍为 `10.0.15`。本轮验证了迁移指引的公开源还原和四个 Release 构建，并回读 R4 的同库业务实测。存量 .NET 9 应用应以隔离备份验证部署目标后迁移。本轮续查未发现额外维护包处置项，独立映射补丁的验收与交接见其归档任务。[迁移指引](r5-r4-net10-migration.md) · [首轮检查点](r5-first-maintenance-review.md#下轮检查点) · [映射补丁归档任务](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/tasks.md)

## 公开发行和历史证据

GitHub Release `458933029` 发布于 `2026-11-26T03:59:33Z`。2026-11-26 再次从远端读得附注 tag 对象 `338cc2c83bc61c06047f4f98298aec629c8ca781`，解引用提交 `5758c8186b68dcc42ecc90164cf9d3f53cf3345e`。公开附件 SHA-256 为 `c3a905b6a6373a59236214f94fce953abb530fc61c80a7fe94ff99f028f534b0`，本轮下载字节与 Release API 附件摘要一致。发行 Git 树和公开清单的三个生产提交及模板提交逐项相同。[公开发行](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1) · [公开清单](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json)

| 路径 | `v10.5.1` gitlink |
| --- | --- |
| `aspnetboilerplate` | `bed57726b56f6f9de5c2d82e8dbe55e0130bddd0` |
| `AutoMapper` | `f646d492df918d27b9ac96c086933570965efef3` |
| `AutoMapper.Collection` | `306b49d7a59b7335a61d8116e1ab2f623a04740e` |
| `module-zero-core-template` | `2e9536872673a7ff1986a19e798c51684d16afe5`（树 `b6a9e7386e3073e820eed83fe418d6c6096468bc`） |

历史实测位于验证机主仓的 `.git/publish-r4-first-public-release/package-6/upgrade/runs/r4-template-upgrade-public-vjc1kvc3/`。2026-11-26 `03:42:45–03:45:36Z` 在发行提交运行，26 个阶段通过，退出 0。`report.json` SHA-256 为 `ef4a2787d6cc840d25584ea2232415289a3d1eeb625db776db98f5e5187287f9`。同目录内的 `release-manifest.json` 和 `verified-downloads.json` 摘要分别为 `cfe2a70f27c662edcf22424d202cbf3c6116c4510263146705bb0f721c7c670a`、`2547c7a4373f778026ab7207417b04aeef832b9b210798016aa9ecc5acde522b`，均与公开清单相符。四张原图路径相对通过轮目录，摘要已重新计算。[R4 公开源实测与复跑命令](r4-release-candidate.md#公开源模板消费)

| TFM / 入口 | 包总数 / 维护包 | 原图 | SHA-256 |
| --- | --- | --- | --- |
| `net9.0` Web.Host | 116 / 13 | `net9-build/raw-assets/Web.Host.project.assets.json` | `f5f82d02bd0aa299355492c98c34bda407197ac1ef94bb1f247bb7441d705b1f` |
| `net9.0` Migrator | 81 / 10 | `net9-build/raw-assets/Migrator.project.assets.json` | `e6bd8aa48ea2b0fdabb25ee0d73a5bbddcb45212c2def80e6f59d31ab1fc1f53` |
| `net10.0` Web.Host | 94 / 13 | `raw-assets/Web.Host.project.assets.json` | `cca797926ef2ed31631d7d10f07e9b52d74e7c84042191681d2d1c45a8bd9321` |
| `net10.0` Migrator | 66 / 10 | `raw-assets/Migrator.project.assets.json` | `ebd39927a4102e1ccaf0fa4c1c3073c96182bad68733d49136d7da9b827e7b86` |

| TFM / 入口 | 历史 PID | 实际加载的 .NET / ASP.NET Core | 实际 EF Core / SQL Server Provider |
| --- | ---: | --- | --- |
| `net9.0` Web.Host | 33957 | `9.0.10 / 9.0.10` | `9.0.18 / 9.0.5` |
| `net9.0` Migrator | 33943 | `9.0.10 / 9.0.10` | `9.0.18 / 9.0.5` |
| `net10.0` Web.Host | 34173 | `10.0.15 / 10.0.15` | `10.0.15 / 10.0.15` |
| `net10.0` Migrator | 34140 | `10.0.15 / 10.0.15` | `10.0.15 / 10.0.15` |

本轮从原 `*-loaded.json`、启动记录及构建输出重新核对四个 PID 与两套共享框架，分别用对应入口的包图、Release DLL 路径及摘要复核 EF Core 和 SQL Server Provider。46 个维护包入口实例的缓存归档、编译和输出 DLL 均通过 R4 对账。两代 Web.Host 加载的映射引擎均为公开 `Du.AutoMapper 14.0.0`，Migrator 的该 DLL 出现在输出中。两代四图均使用公开的 `Du.AutoMapper.Collection 11.0.0`；本地映射候选未进入这些图。[R4 资产核验代码](../../eng/r4_template_assets.py) · [四入口的原版名及解析版本](r5-first-maintenance-dependencies.tsv)

历史同库实测使用 macOS ARM64、SQL Server Developer `16.0.4236.2` 及冻结 Angular production 客户端。两代两入口退出均为 0。两个 Migrator 各三条迁移连接均关联所在 PID 和同一实例、候选库。30 条迁移 ID 及 `ProductVersion` 保持一致，`net10-catalog-before.json` 与 `net10-catalog-after.json` SHA-256 均为 `c2d3d201947f3590b87e1498555936e7a20cd72fa2b5b3b88305ef368066a01f`。两代 Host 的请求标识和实际 count/list 连接也与该库对应。租户 `Default`（ID `1`，账号 `2`）两次均有 `Pages.Users`。相同关键词查询 HTTP 200、总数 `1`、唯一用户 ID `3`，浏览器页面与数据库身份一致。候选、对照库登录数依次为 `1/1 → 2/1 → 3/1`。[业务及恢复点验收要求](../../openspec/specs/template-runtime-upgrade/spec.md)

| R4 恢复点 | 备份集 ID / 实际恢复并读回的登录行 ID | 介质 SHA-256 |
| --- | --- | --- |
| 升级前 | `70ea31d9-0bcc-44f4-85eb-143a26c8bc90` / `1, 2` | `a1d99243e3a1e8fe4936291181f591fa5d11a43d38e05b3f857af6205c9ccd87` |
| 升级后 | `d6547606-5ddf-4202-8f9c-b243174bd02a` / `1, 2, 3` | `972a81e7fd1ca355209cb6f5aa6dd213fa30ead35c01143264d35e1b15a158da` |

两份介质本轮重新计算摘要，原报告记录两次各自独立恢复、读回迁移历史和业务身份。选升级前恢复点会舍弃其后写入，历史例中包括目标端的登录行 `3`。固定输入可复用该历史结果。原版应用回退见另一个冻结源实测入口。[R4 实测支持矩阵](r4-release-candidate.md#实测支持矩阵) · [原版回退](r3-original-template-rollback.md#切回步骤与数据边界)

## 三仓六分支续查

2026-11-26 `10:08:09–10:08:13Z`，通过公开 Git 引用读出分支和发行 tag，分页查询三个仓的公开 Release 和仓库级公告。各分支终点与首轮逐字一致，范围内新增提交均为 0。三个仓的 Release 记录均无首轮截止后发布项。仓库级公告分别为 0、3、0 条，内容和修订状态一致。

| 仓库 / 分支 | 首轮截止完整 SHA | 本轮终点完整 SHA | 相关发行与提交 |
| --- | --- | --- | --- |
| aspnetboilerplate/aspnetboilerplate · `master` | `6c4580c5e7ea41154696c071a53fd200059a768b` | `6c4580c5e7ea41154696c071a53fd200059a768b` | [v10.5.1](https://github.com/aspnetboilerplate/aspnetboilerplate/releases/tag/v10.5.1) · `6c4580c5e7ea41154696c071a53fd200059a768b` |
| aspnetboilerplate/aspnetboilerplate · `dev` | `21f57d282f542aa4221fc5cd5a4ac76346d8f5c7` | `21f57d282f542aa4221fc5cd5a4ac76346d8f5c7` | [v10.5.1 比较基点](https://github.com/aspnetboilerplate/aspnetboilerplate/compare/6c4580c5e7ea41154696c071a53fd200059a768b...21f57d282f542aa4221fc5cd5a4ac76346d8f5c7) · `6c4580c5e7ea41154696c071a53fd200059a768b` |
| LuckyPennySoftware/AutoMapper · `release/15.x` | `c73acdd92eb1b57a4a152ed678bea68321aac895` | `c73acdd92eb1b57a4a152ed678bea68321aac895` | [v15.1.4](https://github.com/LuckyPennySoftware/AutoMapper/releases/tag/v15.1.4) · `c73acdd92eb1b57a4a152ed678bea68321aac895` |
| LuckyPennySoftware/AutoMapper · `release/16.x` | `c121622bb1644728ea50e8f35ff1488145db187a` | `c121622bb1644728ea50e8f35ff1488145db187a` | [v16.3.0](https://github.com/LuckyPennySoftware/AutoMapper/releases/tag/v16.3.0) · `9c31182a3eb99d5191ccc71ee90105846830917f` |
| LuckyPennySoftware/AutoMapper · `main` | `79d10deec5881a617c38e7373f354694044bf83d` | `79d10deec5881a617c38e7373f354694044bf83d` | [v17.0.0](https://github.com/LuckyPennySoftware/AutoMapper/releases/tag/v17.0.0) · `d14380da2e1a6f39395aa9816c73479ec6863162` |
| AutoMapper/AutoMapper.Collection · `master` | `5301edbc689a9696bdd7c396452669434e75989a` | `5301edbc689a9696bdd7c396452669434e75989a` | [v12.0.0](https://github.com/AutoMapper/AutoMapper.Collection/releases/tag/v12.0.0) · `a35cd38fe6c3db44b3a70fc67b7bc6bf9c0e2051`，[v13.0.0](https://github.com/AutoMapper/AutoMapper.Collection/releases/tag/v13.0.0) · `5301edbc689a9696bdd7c396452669434e75989a` |

首轮已归类的回补、兼容差异和待决项沿用各项证据。经典框架 #7219 已回补至发行树，集合映射仍按独立变更的冻结条件判断。[上游回补对照](r5-first-maintenance-review.md#上游源码与回补)

## 包公告续查

NuGet 全球索引及指向的两页解压字节与首轮一致。直接请求索引内 `api.nuget.org` 页在验证网络重定向后返回 404，同一索引路径改由官方全球 CDN 回读，两页均为 HTTP 200 并匹配首轮摘要。三处覆盖位置如下。[NuGet VulnerabilityInfo](https://learn.microsoft.com/en-us/nuget/api/vulnerability-info) · [全球索引](https://apiprod-mscdn.azureedge.net/v3/vulnerabilities/index.json)

| 数据 | 最后完整水位 | SHA-256 |
| --- | --- | --- |
| 全球索引，2026-11-26 `10:08:04Z` 后读回 | 同时列出下述两页 | `3e639b32ea0fb978e26a66ffe1a2ef8391aac97c38bc6e960f4fc01c98c15d64` |
| `base` | `2026-11-20T05:34:20.7684268Z` | `1eb8e70c6f384340d6033fc3c48fd9e5dbc5750d1dcd00d1463df4385637ae9a` |
| `update` | `2026-11-26T05:34:57.7265357Z` | `4bea167a58dcd05bff4210a96618a9b284267c77f9159655582fb6879ee8d302` |

GitHub Advisory Database 在 `10:08:06–10:08:10Z` 完成 12 批 `ecosystem=nuget`、`affects` 分页查询。按四图实际解析版本和 13 个维护包对应原名覆盖 140 个 ID、207 个 ID/版本组合，其中 194 个发行身份/版本组合来自四图共 357 条记录。35 条去重的已审查公告与首轮逐条相同，新增、修订、撤回均为 0。四图的包版本、边及所选资产也相同，因此沿用首轮按 NuGet 版本区间计算的两源匹配结果。两源仍只命中原名 `AutoMapper 14.0.0` 的三则公告，公开 `Du.AutoMapper 14.0.0` 的处置仍依据已回补的同一发行 DLL 及历史实包验证。其余 206 个组合在上述两源范围内无命中，派生应用变更图后重新匹配。[GitHub Advisory API](https://docs.github.com/en/rest/security-advisories/global-advisories) · [包 ID 对应表](r5-first-maintenance-review.md#发行版本和上游基点) · [依赖 TSV](r5-first-maintenance-dependencies.tsv) · [三则公告与实包结论](r5-first-maintenance-review.md#映射引擎公告与实包)

## 共享运行时与下轮检查点

Microsoft 支持政策、正式发行索引及两条线的发行明细确认如下。两套共享框架的末版或目标依据各自明细项，SDK 列供构建准备。本轮核对的 .NET 9、10 发行明细及 CVE 页与首轮字节一致，逐项回读首轮 110 个可访问的公告源，发表、修订、撤回及范围内容无变化。另按首轮截止查询 `dotnet/announcements` 的已更新项，返回空页。服务版本以发行明细为准，应用运行版本取自上述四个历史进程。[支持周期](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core) · [发行索引](https://builds.dotnet.microsoft.com/dotnet/release-metadata/releases-index.json) · [.NET 9 明细](https://builds.dotnet.microsoft.com/dotnet/release-metadata/9.0/releases.json) · [.NET 10 明细](https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json) · [首轮逐公告清单](r5-first-maintenance-runtime-servicing.tsv)

| 频道 | `Microsoft.NETCore.App` | `Microsoft.AspNetCore.App` | 最新 SDK | 服务状态 |
| --- | --- | --- | --- | --- |
| .NET 9 | `9.0.23` | `9.0.23` | `9.0.321` | 2026-11-10 结束支持 |
| .NET 10 | `10.0.15` | `10.0.15` | `10.0.404` | LTS，支持至 2028-11-14 |

**CVE-2026-56158 组件范围仍待核实。** Microsoft 的 `9.0.18` 发行明细继续列出该 ID，MSRC 用户界面仅返回前端壳。MSRC 单条 API、CVE Program API 和 CVEProject 单条查询均为 404。Microsoft 7 月 CVRF 返回 200，未列该 ID。保留首轮版本登记，等待原公告或 CVE 记录公开组件、受影响版本和修订时间后再判断适用范围。[MSRC 原条目](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2026-56158) · [Microsoft 2026 年 7 月 CVRF](https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Jul) · [CVE Program](https://www.cve.org/CVERecord?id=CVE-2026-56158)

| 对象 | 行动和续查入口 |
| --- | --- |
| 上游源码 | 按本页登记的六条 SHA 续查分支、发布标签和仓库公告。 |
| NuGet | 新索引出现时重新读取列出的全页，与上述 `base`、`update` 水位比较，并复核新增、修订和撤回。 |
| GitHub 包公告 | 从最早批次开始 `2026-11-26T10:08:06Z` 作为重叠查询起点。新包图按每入口解析版本、维护 ID 与原名重新匹配。 |
| Microsoft | 从 `9.0.23` 末版和 `10.0.15` 服务版及本轮公告快照继续。官方来源读回区间为 `10:08:04–10:12:55Z`，跨来源接续从区间开头重叠检查。继续跟踪 CVE-2026-56158；现有记录的范围见首轮明细。 |
| 实际部署 | 源端 .NET 9 用自己的实际部署补丁建立隔离基线，目标部署安装受支持的 .NET 与 ASP.NET Core 两套补丁并逐入口实测。目标共享框架补丁变化时，独立核对四图以及 EF Core、Provider 的加载资产。其他平台、数据库 Provider、Angular 和应用变体仍按各自组合验收。 |

## 本轮复验命令与范围

本轮构建使用固定模板的两份归档源码，依次应用历史报告中的换包和运行时补丁，只在目标副本应用第二份。SDK `10.0.404`，macOS ARM64，按[迁移指引](r5-r4-net10-migration.md#修改并构建两代源码)的 Bash 片段从 nuget.org 独立还原两个 TFM，各运行两次 `dotnet build --configuration Release --no-restore`。四次构建均 0 错误。同一 TFM 中按 Migrator、Web.Host 顺序构建，分别为 2、305 条编译警告。四张新图的所选包节点、直接引用、版本和依赖边与历史对应图相同，缓存主包逐份与公开 SHA-256 对账。新图的整文件摘要随路径变化。本轮实测覆盖构建、启动配置隔离与实际 SQL 预检。共享框架选择、同库迁移、浏览器及两个恢复点来自上述固定输入的 R4 历史通过轮。

历史 R4 通过轮以 `Development` 启动，从受控变量构造子进程环境，`HOME` 指向新建的专用 `runtime-home`，测试连接按进程注入。消费者指引沿用 `Development`，在两套 .NET 的配置探针中验证了 `APPDATA` 指向每次新建的空目录时，两代两入口均采用显式的测试连接。合成对照在两代 Host 均观察到同名 User Secrets 可覆盖环境变量，本轮验证使用的目录和数据均为测试输入。[R4 运行环境的实现](../../eng/r3_template_runtime.py) · [消费者启动命令](r5-r4-net10-migration.md#在迁移或登录前核对连接)

SQL 预检在临时 SQL Server Developer `16.0.4236.2` 实例用 macOS ARM64 上的微软 Go `sqlcmd v1.10.0` 实跑。首次运行发现空环境下 CLI 的启动提示与查询结果同写标准输出，改用 `-o` 单列查询结果后，实际文件返回 `du-r5-guide-db|DuR4UpgradeCheck` 和换行。四入口预检均能通过并进入配置探针。错实例、错库、活跃独立租户连接和 SQL 错误四种实际预检均退出 1，对应应用启动次数均为 0。该次验收使用合成表和局部配置探针，同库业务仍引用上述 R4 完整通过轮。[微软 sqlcmd v1.10.0 发行](https://github.com/microsoft/go-sqlcmd/releases/tag/v1.10.0)

在验证机主仓的 `.git/review-r5-runtime-migration-readiness/runtime/` 保存原始响应、各次查询的 UTC 时间及实际参数、四张新还原图和复核脚本。以下是本轮关键回读入口，历史通过轮的证据读取保持原路径。

| 命令或入口 | 范围和结果 |
| --- | --- |
| `git ls-remote <官方 GitHub 仓库> <refs/heads/...> <refs/tags/...>`、`git ls-tree v10.5.1 aspnetboilerplate AutoMapper AutoMapper.Collection module-zero-core-template` | 退出 0，官方当前引用及本地发行树与 GitHub API 发行树、公开清单交叉核对。 |
| `gh api --hostname github.com --paginate --slurp`、`curl --compressed -sSL` | 原始只读调用保存在 `raw/*.run.json`。GitHub 分页用于指定三个上游和 NuGet 公告，Microsoft 和 NuGet 全球索引保留原页面；CVE 缺项与 CDN 恢复见上文。 |
| `python3 -B <证据目录>/recheck-r4.py` | 退出 0，`recheck-r4.json` 记录发行清单、四图、四入口进程、同库查询及两份原备份的摘要回读。 |
| `bash <证据目录>/guide-build/build.sh`、`python3 -B <证据目录>/recheck-guide-build.py` | 均退出 0，`guide-build.log` 与 `recheck-guide-build.json` 记录四张新图及包来源对账。 |
| `python3 -B <证据目录>/recheck-official.py` | 退出 0，`recheck-official.json` 登记分支、公开公告及服务水位对账。 |
| `python3 -B <证据目录>/development-correction/verify-guide-isolation.py` | 退出 0，`isolation-results.json` 登记旧配置对照和两代四入口配置探针。 |
| `python3 -B <证据目录>/development-correction/live-sql-preflight.py` | 退出 0，`live-sql-results.json` 记录真实 SQL 查询格式、四入口预检、四个拒绝结果及资源终态。 |

R4 配套 Python 入口中，现行工作树的引擎 gitlink 已指向本地候选。原套件依赖 R4 gitlink 的规划夹具以该条件拒绝现行 HEAD，另一个冻结模式用例需传入冻结通过轮。用原冻结轮重新执行七个适用用例均通过。四入口公开源资产另用上面的历史回读脚本逐项核验。历史报告与新构建结果仅覆盖表中的组合。[R4 定向 verifier](../../eng/tests/verify_r4_public_consumer.py)
