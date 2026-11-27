# R5 公开补丁后的首轮维护审查

2026-11-27，公开 `v10.5.2` 的四个入口均选用三份新映射包，十份沿用包与 R4 签后实物逐字节一致。与 `v10.5.1` 相比，每个入口有三个解析版本、四条精确版本约束和三个所选 DLL 的摘要变化。**本轮维护包无需补丁。** 存量 .NET 9 部署仍需迁移到受支持的 .NET 10 组合，CVE-2026-56158 的精确组件和版本范围待核实。[R5 发行验收](r5-public-release.md) · [上轮审查及续查位置](r5-runtime-migration-review.md)

## 公开发行与源码

2026-11-27 02:52–02:53 UTC，从 `dusdong/du.aspnetboilerplate` 的 Git 引用及匿名 GitHub API 回读标签、发行记录和源码树。附注 tag 和解引用对象与本地 Git 一致。R5 Release `460000507` 于 `2026-11-27T01:31:09Z` 公开，唯一上传附件 `R5-PACKAGE-CHECKSUMS.json` 的实际字节与 Release API 摘要一致。R4 的 Release `458933029` 及其校验附件也重新读回。固定安装指南的提交为 `ab4957bb0326a3754ffc5b50cdbdf1244f411dfd`，文件 SHA-256 为 `6d2ede2a0cfa55040319cee9a31740d9b0c7e3cab07eaeb17d50b9fd9920265d`。R5 的主仓收尾提交为 `0d42db5eb4ff620863b5f58c7eb9c675c2f67d87`。[R5 Release](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.2) · [R5 公开附件](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.2/R5-PACKAGE-CHECKSUMS.json) · [R4 公开附件](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json) · [固定安装指南](https://github.com/dusdong/du.aspnetboilerplate/blob/ab4957bb0326a3754ffc5b50cdbdf1244f411dfd/docs/maintenance/r5-public-install.md)

| 发行 | 附注 tag 对象 | 解引用提交 | 校验附件 SHA-256 |
| --- | --- | --- | --- |
| `v10.5.1` | `338cc2c83bc61c06047f4f98298aec629c8ca781` | `5758c8186b68dcc42ecc90164cf9d3f53cf3345e` | `c3a905b6a6373a59236214f94fce953abb530fc61c80a7fe94ff99f028f534b0` |
| `v10.5.2` | `b08cd8ae03cb47bc6f01fa0a0d0065efc3c78b43` | `cebc3e38a511783092963893bf5ad3161d0f0a19` | `be08d2d354d71dcb09802f8161496f213ebdd257826ed5adbf6af77fe9000dd5` |

发行树中三个生产 gitlink 和固定模板均与公开附件一致。R5 的四个远端源对象与本地相同提交的 Git 树对账通过。三仓 R5 源码均包含表中的原上游基点。包公告按清单中的发行 ID/版本和原上游 ID/版本分别匹配。[上游基点登记](release-baseline.json) · [原包 ID 说明](r5-first-maintenance-review.md#发行版本和上游基点)

| 组件 | R4 gitlink | R5 gitlink | R5 Git 树 | 原上游版本和基点 |
| --- | --- | --- | --- | --- |
| `aspnetboilerplate` | `bed57726b56f6f9de5c2d82e8dbe55e0130bddd0` | `7933e71f5646d2447af3502ecbea9a3f1aba8184` | `8b93fc58f7a8a4ba3d8f79870af270dba0707bc9` | `v10.5.1` · `6c4580c5e7ea41154696c071a53fd200059a768b` |
| `AutoMapper` | `f646d492df918d27b9ac96c086933570965efef3` | `54f6277af80783e5d07e896f75df0dcc0c4b4502` | `fd695a05ec9f7039ecddebc8f18875dd5c57f795` | `v14.0.0` · `bf76a5819e1bad7af7db5382bf0f3a0178048a15` |
| `AutoMapper.Collection` | `306b49d7a59b7335a61d8116e1ab2f623a04740e` | `d22aaf58469d760502864fbb6f575b6505dd8334` | `0131ed22f1de1fbd8f05115e6e7da8cc1a3d59ed` | `v11.0.0` · `eafbf005becf73f989e1b1c0d52e8699439f837c` |
| `module-zero-core-template` | `2e9536872673a7ff1986a19e798c51684d16afe5` | `2e9536872673a7ff1986a19e798c51684d16afe5` | `b6a9e7386e3073e820eed83fe418d6c6096468bc` | 固定消费提交 |

## 主包与签后实物

按公开附件列出的精确 ID 和版本，从 nuget.org V3 匿名下载两版合计 16 个不同主包，验证网络将内容请求转到 `nuget.azure.cn`。签后 SHA-256 与公开附件、原下载登记及各入口缓存一致。实包 nuspec 的 ID、版本、仓库和提交逐项对账。原仓库签名与时间戳验签证据通过相同归档摘要沿用，本轮回读签名成员并比对已登记的成员摘要。三份新主包与冻结上传件的逐成员差异仅为仓库签名成员。三个公开 PDB 的验收沿用发行记录。[发行实物与符号验收](r5-public-release.md) · [冻结批次及生产来源](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/source-and-engine-validation.md#三包待发批次)

| 发行 ID | R4 → R5 | R5 签后 SHA-256 | R4 签后 SHA-256 |
| --- | --- | --- | --- |
| `Du.Abp` | `10.5.1`（沿用） | `25f28a24f254242062dd2f3832137fc32c4196237a22e693afb987af578d3141` | 同 R5 |
| `Du.Abp.AspNetCore` | `10.5.1`（沿用） | `3d96f4a90472e9f627b761a99f1ef38a84c14cf20a33432d362aabafb2226a22` | 同 R5 |
| `Du.Abp.AspNetCore.SignalR` | `10.5.1`（沿用） | `37cc883ba582f327dc9e8b0c1038a5ce72b847da99ca9fcdc546be16dbcf3ac5` | 同 R5 |
| `Du.Abp.AutoMapper` | `10.5.1` → `10.5.2` | `0dff890160a7d7acfdea7a45fb642fdb8f753185810abd28f5c53599b33a660a` | `e66ee4cf3dd053c478ddbdb5bf227b7ee55d43bcc67694d5ed245ab9d4842a24` |
| `Du.Abp.Castle.Log4Net` | `10.5.1`（沿用） | `c39cc82003dad710176a3a11d550e6f7243787b6e4486ca04f0507952e24b114` | 同 R5 |
| `Du.Abp.EntityFramework.Common` | `10.5.1`（沿用） | `14c3269f6151cc795290beb8d94b0e781d47c9621f5850049ca5f78b6db748c6` | 同 R5 |
| `Du.Abp.EntityFrameworkCore` | `10.5.1`（沿用） | `4c5d0d45bd2b32d364463942e077013f6cdc54c078d075edfda947fb5ea493d8` | 同 R5 |
| `Du.Abp.Web.Common` | `10.5.1`（沿用） | `355b22c605d4cc425a3971286e210885d46a2f581e6f9b64d6cd0e49c915f587` | 同 R5 |
| `Du.Abp.Zero.Common` | `10.5.1`（沿用） | `33b2293af780bcaa2184c7fd7e6d49efd0f614be74ce82fbe5f69ba6d2ba3d8e` | 同 R5 |
| `Du.Abp.ZeroCore` | `10.5.1`（沿用） | `9d6813a02d146f7e8606b706fb5ee27904a29ea8f983accccab149e194257742` | 同 R5 |
| `Du.Abp.ZeroCore.EntityFrameworkCore` | `10.5.1`（沿用） | `f7cd57d79039cd4f07368bbde08afd7efa7be1adc1e1a042628790c71e4c7285` | 同 R5 |
| `Du.AutoMapper` | `14.0.0` → `14.0.1` | `e93025f85ccbf1c68738fd2a14a741ec62b482ea8f9a825b019b7b13d1345bd4` | `9edf3c6163f6d27c7a7c2805c1915a3762bf44ad2ab186ab9a406d7e9925b253` |
| `Du.AutoMapper.Collection` | `11.0.0` → `11.0.1` | `1a18668579da5051d6df46d7c7b00afd3186ab50a41df3bd5a91a64db2532004` | `e7428f19a8960806c39fe624601ebb7ebb7462c9a1c7e2de6801af7aa59e8d19` |

在 R5 的三份新实物中，引擎 nuspec 直接登记生产提交 `54f6277a`。Collection 和适配器的 nuspec 分别登记编译基点 `306b49d7` 和 `bed57726`，归档中的可重放补丁与其生产 gitlink 树相同，冻结批次复核通过。十个沿用包继续绑定 R4 的 `bed57726`。相对 R4，引擎的 `CollectionMapper.CheckContext` 优先尝试成员 `TypeMap` 的上下文，再回落至元素映射。Collection 和适配器的源码差异在打包属性、清单说明及精确依赖约束。适配器对 `Du.Abp [10.5.1]` 的边保持原版本。[引擎生产代码](https://github.com/dusdong/AutoMapper/blob/54f6277af80783e5d07e896f75df0dcc0c4b4502/src/AutoMapper/Mappers/CollectionMapper.cs) · [Collection 生产项目](https://github.com/dusdong/AutoMapper.Collection/blob/d22aaf58469d760502864fbb6f575b6505dd8334/src/AutoMapper.Collection/AutoMapper.Collection.csproj) · [适配器打包属性](https://github.com/dusdong/aspnetboilerplate/blob/7933e71f5646d2447af3502ecbea9a3f1aba8184/nupkg/r4-candidate.props) · [冻结补丁与编译基点](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/source-and-engine-validation.md#三包待发批次)

## 四入口的原始还原图

R5 四张图取自 2026-11-27 `01:11:09–01:13:50Z` 同一次公开源同库升级。原始目录为验证机主仓的 `.git/publish-r5-mapping-patch/publisher-consumption/runs/r5-template-upgrade-h1h2hp6e/`。父 `report.json` 的 SHA-256 为 `52d456199c6baf76a6ed27941a5b6bdd24ffe58eeeef868bc7e94f24bd339de8`，与公开附件及消费归档一致，26 个阶段通过且退出 0。它引用的 `net9-build/report.json` 的 SHA-256 为 `747664b613d6885f69cb4ad3c39836d08070c0405a579fe5bc02f26b1faf6256`，9 个阶段通过且退出 0。两代均使用固定模板、SDK `10.0.404`、macOS ARM64、SQL Server 2022 Developer `16.0.4236.2` 与同一套冻结 Angular production 产物。发布者新装和独立新装的报告也与公开附件对账，四入口差异以同库升级的原图计算。[R5 发布者与独立消费者验收](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/consumption-validation.md)

R4 对照使用 2026-11-26 `03:42:45–03:45:36Z` 的原公开升级，验证机主仓的 `.git/publish-r4-first-public-release/package-6/upgrade/runs/r4-template-upgrade-public-vjc1kvc3/`。其 `report.json` 的 SHA-256 为 `ef4a2787d6cc840d25584ea2232415289a3d1eeb625db776db98f5e5187287f9`，26 个阶段通过且退出 0。表中原图位置相对各自通过轮目录。八张原图均匹配各自原报告登记的摘要。[R4 原图及历史实测](r5-runtime-migration-review.md#公开发行和历史证据)

| TFM / 入口 | 原图相对路径 | R4 SHA-256 | R5 SHA-256 |
| --- | --- | --- | --- |
| `net9.0` Web.Host | `net9-build/raw-assets/Web.Host.project.assets.json` | `f5f82d02bd0aa299355492c98c34bda407197ac1ef94bb1f247bb7441d705b1f` | `91148034cf51ceb01517f2c50d12a4ed973d93a78dcbd5492837de0264b53b72` |
| `net9.0` Migrator | `net9-build/raw-assets/Migrator.project.assets.json` | `e6bd8aa48ea2b0fdabb25ee0d73a5bbddcb45212c2def80e6f59d31ab1fc1f53` | `2c755b7c853bdcc8079b54e1f3c69075f3509a71aafe1db1f243ca159f0abafb` |
| `net10.0` Web.Host | `raw-assets/Web.Host.project.assets.json` | `cca797926ef2ed31631d7d10f07e9b52d74e7c84042191681d2d1c45a8bd9321` | `7f6a2423465beca5de2fe2176509c0c04d245e49fc18ba42a238184e3dc22a54` |
| `net10.0` Migrator | `raw-assets/Migrator.project.assets.json` | `ebd39927a4102e1ccaf0fa4c1c3073c96182bad68733d49136d7da9b827e7b86` | `fb01882114f88ca0f4f3ba32217ab24bb8defb854258c839fb2eca4f3db45c69` |

### 解析版本、依赖边和所选资产

R5 清单共 357 条入口记录及 194 个不同的发行 ID/解析版本组合，维护包各行也包含原上游 ID、版本和完整基点 SHA。按 `tfm`、`entry`、`reference` 可分别列出每个入口的直接和传递依赖。每包给出应用或 EF Core Design 工具链的最短引入路径，并标出所选 analyzer 和 Release 输出是否含该包资产。直接依赖取入口工程的 `project.frameworks[TFM].dependencies`，跨项目引入属于入口的传递依赖。[R5 四入口清单](r5-public-patch-dependencies.tsv) · [R4 四入口清单](r5-first-maintenance-dependencies.tsv)

| TFM / 入口 | 包数（直接 / 传递，其中维护包） | 图的边数 | R4 → R5 变化（包版本 / 边 / 编译 DLL / 输出 DLL） |
| --- | --- | ---: | --- |
| `net9.0` Web.Host | 116（2 / 114，其中 13） | 216 | 3 / 4 / 3 / 3 |
| `net9.0` Migrator | 81（1 / 80，其中 10） | 148 | 3 / 4 / 3 / 3 |
| `net10.0` Web.Host | 94（2 / 92，其中 13） | 163 | 3 / 4 / 3 / 3 |
| `net10.0` Migrator | 66（1 / 65，其中 10） | 115 | 3 / 4 / 3 / 3 |

复算时分别读取各图的 `targets[TFM]`，按 ID 忽略大小写关联已解析键。边按父节点 ID、子节点 ID 对齐，比较声明区间和解析版本，包含入口的直接包及项目引用边。用 `assets-inventory.json` 与各入口的 `*-output.json` 比较实际编译引用、analyzer 及输出资产的归属包 ID、包内路径和 SHA-256。R4 提取结果与既有清单逐行一致。四个入口的包 ID 集和边的父子关系均相同，新增、移除各为 0。其余包解析版本及图中内容 SHA-512 均一致。构建所选 analyzer、项目所需共享框架声明和 SDK 编译包相同。`net9.0` 的 targeting packs 和 macOS ARM64 apphost 的 `9.0.23` 只用于构建，R4、R5 的缓存路径不同而版本与摘要一致。[资产与构建核对实现](../../eng/r3_web_host.py) · [维护包输出及进程核对实现](../../eng/r4_template_assets.py)

三份新包在两代两入口都经 `Core` 进入，属于入口的传递依赖。最短路径分别经 `Web.Host > Web.Core > Application > Core` 和 `Migrator > Core` 到达适配器。引擎可由适配器直接引入，也可经 Collection 引入。四张图的精确声明与解析变化如下。

| 父节点 → 子包 | R4 请求 / 解析 | R5 请求 / 解析 |
| --- | --- | --- |
| `Core` → `Du.Abp.AutoMapper` | `[10.5.1]` / `10.5.1` | `[10.5.2]` / `10.5.2` |
| `Du.Abp.AutoMapper` → `Du.AutoMapper` | `[14.0.0]` / `14.0.0` | `[14.0.1]` / `14.0.1` |
| `Du.Abp.AutoMapper` → `Du.AutoMapper.Collection` | `[11.0.0]` / `11.0.0` | `[11.0.1]` / `11.0.1` |
| `Du.AutoMapper.Collection` → `Du.AutoMapper` | `[14.0.0]` / `14.0.0` | `[14.0.1]` / `14.0.1` |

引擎 nuspec 继续声明 `Microsoft.Extensions.Options 8.0.0`。两代的对应处理与 R4 一致。`net9.0` 由现有包图解析该依赖，`net10.0` 的 NuGet 裁剪后由 `Microsoft.AspNetCore.App.Ref` 提供同名编译引用。两代四入口中的映射包资产路径和角色一致，下表列出编译引用与 Release 输出中改变的全部包 DLL。新摘要以签后主包成员、冻结成员、构建记录和 Release 文件对账。

| 两代四入口的编译 / 输出 DLL | 选择的包内路径 | R4 SHA-256 | R5 SHA-256 |
| --- | --- | --- | --- |
| `Abp.AutoMapper.dll` | `lib/net9.0/Abp.AutoMapper.dll` | `87e3cbbe1a600adb8b4cd51feb638ef0271d75a7126b6d7f7a85c8f96cadf07f` | `82bb376e405ba42dbbe2bd7caab4590691a0374bb4e0772797cbf3e24cb95137` |
| `AutoMapper.Collection.dll` | `lib/net8.0/AutoMapper.Collection.dll` | `8f64b1194121a7dd5be23d6bffa7456765590905f2ae5dff5414bcc9f5adfd58` | `0d942343005bb358f381fb9d09543a04d66affd7a90029cb4a8ef33ad457ca2e` |
| `AutoMapper.dll` | `lib/net8.0/AutoMapper.dll` | `12fcba523f7f7199215764b29c5d330aa363c433fa14d4e72257ce835a87e5e1` | `1d752c32c70cff281afc3bee951abdf763b0910ba74be6a4772854149fe75bd0` |

### 历史进程实际加载

本节取原运行的启动选择、`*-loaded.json` 与进程资产回执。共享框架分别用 `System.Private.CoreLib` 与 Web.Host 的 `Microsoft.AspNetCore.Hosting`、Migrator 的 `Microsoft.AspNetCore.Identity` 核对实际加载路径。EF Core 和 SQL Server Provider 则按各入口加载 DLL 与其 Release 包资产对账。四入口所用共享框架及这两项应用资产版本均与各自 R4 进程一致。[R4 历史进程](r5-runtime-migration-review.md#公开发行和历史证据) · [R5 消费报告](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/consumption-validation.md)

| TFM / 入口 | R5 历史 PID / 退出码 | 实际 .NET / ASP.NET Core | 实际 EF Core / SQL Server Provider | 三个映射 DLL 的实际证据 |
| --- | --- | --- | --- | --- |
| `net9.0` Web.Host | 75217 / 0 | `9.0.10 / 9.0.10` | `9.0.18 / 9.0.5` | 加载引擎及适配器，Collection 出现在输出中 |
| `net9.0` Migrator | 75158 / 0 | `9.0.10 / 9.0.10` | `9.0.18 / 9.0.5` | 三份均出现在输出中 |
| `net10.0` Web.Host | 75529 / 0 | `10.0.15 / 10.0.15` | `10.0.15 / 10.0.15` | 加载引擎及适配器，Collection 出现在输出中 |
| `net10.0` Migrator | 75503 / 0 | `10.0.15 / 10.0.15` | `10.0.15 / 10.0.15` | 三份均出现在输出中 |

本轮依据同输入的历史通过轮核对资产与进程证据。两代各自的支持范围、同库迁移和恢复点适用条件见发行验收。校验附件、公开主包、报告摘要、八张原图、按入口的可复算差异和实际命令记录保存在验证机主仓的 `.git/review-r5-public-patch-baseline/package-1/`。

## 三仓六分支与上轮未决项

2026-11-27 `03:08:32–03:09:27Z` 回读公开 GitHub API，起点为上轮六个完整 SHA。Git HTTPS 查询连接超时，已通过官方精确 Git 引用接口和完整标签分页补足。六条分支均新增 0 个提交。相关标签与上轮登记的解引用对象一致。三仓 Release 页分别返回 `100+100+51 / 58 / 15` 条，发行时间、说明和记录无新增、移除或修订。标签页分别为 `100+100+55 / 72 / 29` 条。仓库公告页分别为 `0 / 3 / 0` 条，三条 AutoMapper 公告的范围、修订和撤回状态均与上轮一致。[上轮截止](r5-runtime-migration-review.md#三仓六分支续查) · [经典框架发行与标签](https://github.com/aspnetboilerplate/aspnetboilerplate/releases) · [AutoMapper 发行与标签](https://github.com/LuckyPennySoftware/AutoMapper/releases) · [Collection 发行与标签](https://github.com/AutoMapper/AutoMapper.Collection/releases)

| 官方仓库 / 分支 | 上轮完整 SHA | 本轮完整 SHA | 相关发行 |
| --- | --- | --- | --- |
| aspnetboilerplate/aspnetboilerplate · `master` | `6c4580c5e7ea41154696c071a53fd200059a768b` | `6c4580c5e7ea41154696c071a53fd200059a768b` | `v10.5.1` |
| aspnetboilerplate/aspnetboilerplate · `dev` | `21f57d282f542aa4221fc5cd5a4ac76346d8f5c7` | `21f57d282f542aa4221fc5cd5a4ac76346d8f5c7` | 相对 `v10.5.1` 的 #7219 |
| LuckyPennySoftware/AutoMapper · `release/15.x` | `c73acdd92eb1b57a4a152ed678bea68321aac895` | `c73acdd92eb1b57a4a152ed678bea68321aac895` | `v15.1.4` |
| LuckyPennySoftware/AutoMapper · `release/16.x` | `c121622bb1644728ea50e8f35ff1488145db187a` | `c121622bb1644728ea50e8f35ff1488145db187a` | `v16.3.0` · `9c31182a3eb99d5191ccc71ee90105846830917f` |
| LuckyPennySoftware/AutoMapper · `main` | `79d10deec5881a617c38e7373f354694044bf83d` | `79d10deec5881a617c38e7373f354694044bf83d` | `v17.0.0` · `d14380da2e1a6f39395aa9816c73479ec6863162` |
| AutoMapper/AutoMapper.Collection · `master` | `5301edbc689a9696bdd7c396452669434e75989a` | `5301edbc689a9696bdd7c396452669434e75989a` | `v13.0.0`，前一版 `v12.0.0` · `a35cd38fe6c3db44b3a70fc67b7bc6bf9c0e2051` |

- **集合映射上下文已有修复。** #4651、#4676 及 #4675 的问题由引擎生产树 `54f6277a` 的 `CollectionMapper.CheckContext` 处理，成员映射的上下文优先，随后仍可检查元素映射。候选验收加载的引擎 DLL 与四入口使用的公开件同摘要，冷态注册和暖态预热四组各 6/6，12 次预热通过。旧公开引擎的相关顺序中观察到缺口。适配器与 Collection 的精确依赖同时接续至新引擎。该项已随 `v10.5.2` 发行。[#4651](https://github.com/LuckyPennySoftware/AutoMapper/pull/4651) · [#4676](https://github.com/LuckyPennySoftware/AutoMapper/pull/4676) · [#4675](https://github.com/LuckyPennySoftware/AutoMapper/pull/4675) · [本版引擎同实物验收](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/consumption-validation.md#独立消费与引擎)
- **经典框架 #7219 已有修复。** 回补 `d08617b51bb7c7e5d0bea942e7e10b2677240c35` 仍是 `7933e71f` 的祖先，R5 与 R4 的框架运行和测试源码一致。两代四入口使用的 `Du.Abp.EntityFrameworkCore 10.5.1` 是 R4 的同一签后实物。原 .NET 9 / SQLite 隔离作用域回归 4 项通过，R5 SQL Server 升级报告用于固定业务验收。更换 Provider、EF Core 或查询编译路径后复验对应行为。[#7219](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7219) · [R5 生产源码](https://github.com/dusdong/aspnetboilerplate/blob/7933e71f5646d2447af3502ecbea9a3f1aba8184/src/Abp.EntityFrameworkCore/EntityFrameworkCore/AbpEfCoreDatabase.cs) · [R1 回归](r1-efcore-query-filter.md#回归结果)
- 较新引擎的许可依赖修订 #4576、#4582、#4606、#4645 仍不适用于 14 基线。#4681 与 Collection #192、#196 对应后续 TFM 和引擎大版本，本版仍选用固定的 14/11。其适用条件随以后采用的引擎、Collection 与消费 TFM 重查。[上轮源码归类](r5-first-maintenance-review.md#较新映射维护线的其他修复)

| 上轮事项 | 原触发条件与本轮证据 | 本轮处置及后续触发 |
| --- | --- | --- |
| #4604 | 固定 14 基线需证明可空扩展方法与 `MapAtRuntime` 的组合。条件尚未满足，`ExpressionBuilder.ContextMap` 仍传原源表达式，既有实包验收未覆盖该组合。 | **待核实。** 出现该组合的消费者故障或得到固定 14 的定向回归时复查，现有证据未建立本轮补丁需求。[#4604](https://github.com/LuckyPennySoftware/AutoMapper/pull/4604) · [本版源码](https://github.com/dusdong/AutoMapper/blob/54f6277af80783e5d07e896f75df0dcc0c4b4502/src/AutoMapper/Execution/ExpressionBuilder.cs#L168) |
| #4607 / #4567 | 固定 14 组合需证明失败，并覆盖旧开放泛型注册顺序与继承。条件尚未满足，`ProfileMap.Configure` 仍读 `typeMapConfiguration.TypeMap`。本版集合注册顺序验收覆盖 #4651，开放泛型继承待单独验收。 | **暂缓，单独评估。** 上游已报告 14.0.0 的案例，取得本版的定向结果及旧注册兼容对照后再决定回补。当前发行决定沿用已验配置。[#4607](https://github.com/LuckyPennySoftware/AutoMapper/pull/4607) · [#4567](https://github.com/LuckyPennySoftware/AutoMapper/issues/4567) · [本版源码](https://github.com/dusdong/AutoMapper/blob/54f6277af80783e5d07e896f75df0dcc0c4b4502/src/AutoMapper/ProfileMap.cs#L169) |
| #4605 | 需要实际消费者故障及旧命名配置对照。条件尚未满足，R5 仍按单个大写字母切分，改变切分会影响既有成员匹配。 | **暂缓。** 出现消费者故障并可同时验证旧命名配置时复查，本轮继续保留现行匹配行为。[#4605](https://github.com/LuckyPennySoftware/AutoMapper/pull/4605) · [本版源码](https://github.com/dusdong/AutoMapper/blob/54f6277af80783e5d07e896f75df0dcc0c4b4502/src/AutoMapper/Configuration/INamingConvention.cs#L27) |
| #4655 | 需要 14 版旧条件委托的具体场景和兼容对照。条件尚未满足，`TypeMapPlanBuilder` 仍把映射后值传给旧条件委托。 | **暂缓。** 取得场景及兼容对照后复查，后续的 DI 条件 API 在本版不适用。本轮继续保留旧委托行为。[#4655](https://github.com/LuckyPennySoftware/AutoMapper/pull/4655) · [本版源码](https://github.com/dusdong/AutoMapper/blob/54f6277af80783e5d07e896f75df0dcc0c4b4502/src/AutoMapper/Execution/TypeMapPlanBuilder.cs#L346) |

## 四入口包公告复核

2026-11-27 `03:08:30–03:12:54Z` 从 nuget.org 服务索引发现 `VulnerabilityInfo`。环境将默认地址重定向至返回 2023 年索引的地区镜像，索引中全球页的原域名路径也经重定向后返回 404。用 NuGet 全球 CDN 读回当前索引及所列全部两页，HTTP 均为 200。新索引推进了 `update` 的路径和时间，两页的实际解压字节均与上轮一致，内容集合无新增、修订或清除。匹配采用两页合并后的有效范围。[NuGet VulnerabilityInfo](https://learn.microsoft.com/en-us/nuget/api/vulnerability-info) · [全球索引](https://apiprod-mscdn.azureedge.net/v3/vulnerabilities/index.json)

| NuGet 数据 | 本轮水位 | 解压内容 SHA-256 |
| --- | --- | --- |
| 全球索引 | 2026-11-27 读取，完整列出以下两页 | `a403b43cfeb7661933d2e6365f9e1d0f5378e7b746fc1979f188f8fd61af0f3a` |
| `base`（666 个 ID） | `2026-11-20T05:34:20.7684268Z` | `1eb8e70c6f384340d6033fc3c48fd9e5dbc5750d1dcd00d1463df4385637ae9a` |
| `update`（1 个 ID） | `2026-11-26T23:35:03.9791635Z` | `4bea167a58dcd05bff4210a96618a9b284267c77f9159655582fb6879ee8d302` |

GitHub Advisory Database 于 `03:08:35–03:09:09Z` 按 `ecosystem=nuget` 对 140 个 ID 分 12 批查存量。每批按已审查、未审查、恶意包分类全量查询，并各自显式补查已撤回，共 72 个查询。每个查询均成功读到分页终点，单页返回，允许空页。去重后 35 条已审查公告与上轮相同，未审查和恶意包两类均为空。已撤回的历史记录为 `GHSA-8g9c-28fc-mcx2` 和 `GHSA-8rfx-6mr3-5jh3`，均无区间匹配。从上轮 `2026-11-26T10:08:06Z` 起重叠查 `modified`，三个分类各含独立撤回查询，六个分页结果均为空。上述两源及分页范围成功覆盖，组件范围缺证的 Microsoft 单独条目见下一节。[GitHub Advisory API](https://docs.github.com/en/rest/security-advisories/global-advisories) · [历史撤回一](https://github.com/advisories/GHSA-8g9c-28fc-mcx2) · [历史撤回二](https://github.com/advisories/GHSA-8rfx-6mr3-5jh3)

按四图 357 条实际 ID 与解析版本，另对 46 条维护包记录取 TSV 的 `upstreamId`、`upstreamVersion`、`upstreamCommit`。逐入口共比较 403 行，去重为 194 个实际身份/版本加 13 个原上游身份/基点版本，即 207 个组合。按 ID 忽略大小写，用 SDK `10.0.404` 的 `NuGet.Versioning` 处理 NuGet 区间及 GitHub 比较符。两源各只有原 `AutoMapper 14.0.0` 命中三条，有效结果覆盖全部 194 个实际身份/版本的零命中，其余 12 个原身份/版本也为零。包身份、引入链、所选资产和上游完整基点逐行见 TSV。应用修改 JWT、SQL Server、EF Core Design 或其他依赖时用实际图重算。[四入口依赖 TSV](r5-public-patch-dependencies.tsv)

| 入口 | 实际身份检查 / 原身份检查 | 三条原名命中的对应实物 |
| --- | --- | --- |
| `net9.0` Web.Host | 116 / 13 | `Du.AutoMapper 14.0.1`，经 `Web.Core > Application > Core > Du.Abp.AutoMapper 10.5.2` 引入并加载 |
| `net9.0` Migrator | 81 / 10 | 同 ID 和版本，经 `Core > Du.Abp.AutoMapper 10.5.2` 引入，进入输出 |
| `net10.0` Web.Host | 94 / 13 | 同 ID、版本和 Web.Host 路径，实际加载 |
| `net10.0` Migrator | 66 / 10 | 同 ID、版本和 Migrator 路径，进入输出 |

四个入口均以上游 tag `v14.0.0`（`bf76a5819e1bad7af7db5382bf0f3a0178048a15`）匹配原 ID，回读实际发行源码 `54f6277af80783e5d07e896f75df0dcc0c4b4502`，确认防护实现仍在。相对 R4，运行时源码新增集合上下文处理，深度、计划和运行时调用防护所在文件与 R4 相同。签后主包内 DLL、发行前专项实际加载 DLL、两代公开 Web.Host 加载与两代 Migrator 输出均为上文登记的 `1d752c32…75bd0`。引擎专项报告 SHA-256 为 `a43b1a3d1a4321e93be1bb6997ba1b041d71ec20651ba8576aba0dfc4cd3ba69`，四个防护用例均退出 0。以下处置针对该生产树及公开实物。[本版生产源码](https://github.com/dusdong/AutoMapper/tree/54f6277af80783e5d07e896f75df0dcc0c4b4502/src/AutoMapper) · [防护来源](r3-automapper-engine.md#公告处置与行为证据) · [同摘要实包报告](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/consumption-validation.md#独立消费与引擎)

| 原名命中（NuGet 区间 / GitHub 约束） | 本版防护证据和处置 |
| --- | --- |
| CVE-2026-32933 · `(,15.1.1)` / `< 15.1.1` | **已有修复。** 默认深度与引用身份路径在 `TypeMap`、`TypeMapPlanBuilder` 及 `ResolutionContext` 保留。同 DLL 的 `reference-graph` 验证深度有界、自引用身份和既有对象更新。上游原版另说明 15.1.1、15.1.2 发版分支有误，15.x 应用参照上游 15.1.3 或以上的处置。[原仓公告](https://github.com/LuckyPennySoftware/AutoMapper/security/advisories/GHSA-rvv3-g6hj-g44x) · [上游 v15.1.3](https://github.com/LuckyPennySoftware/AutoMapper/releases/tag/v15.1.3) |
| CVE-2026-128082 · `(,15.1.4)` / `< 15.1.4` | **已有修复。** `TypeMapPlanBuilder` 保留构造路径的深度保护及异常恢复。同 DLL 的 `constructor-depth` 验证显式与默认深度和常规异常后的恢复。[原仓公告](https://github.com/LuckyPennySoftware/AutoMapper/security/advisories/GHSA-6vhm-j9h7-f9gh) |
| CVE-2026-128081 · `(,15.1.4)` / `< 15.1.4` | **已有修复。** 运行时分派的深度计算与 `Mapper.MapCore` 的运行栈检查仍在。同 DLL 通过 `runtime-dispatch` 和 `application-exception`，后者验证受控异常传播及恢复。运行栈的保护证据为同 DLL 的 IL 与官方 API 契约，实际 CLR 低栈触发未观测。[原仓公告](https://github.com/LuckyPennySoftware/AutoMapper/security/advisories/GHSA-gpwp-5797-mjff) · [.NET API 契约](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices.runtimehelpers.ensuresufficientexecutionstack?view=net-9.0) |

## 共享运行时与 CVE-2026-56158

按上轮的 `2026-11-26T10:08:04Z` 重叠续查，2026-11-27 `03:08:30–03:12:54Z` 读回 Microsoft 支持政策、正式索引、两代发行元数据与 CVE 页。两代发行明细与 CVE 页均同上轮。110 个已登记原公告逐条回读，范围、发布时间、修订与撤回状态无变化。公告仓的 `since` 查询到空页。Runtime、ASP.NET Core、SDK、EF Core 的仓库公告分页分别返回 96、56、14、0 条，重叠窗口内均无新发表或修订项。两代最新 SDK 分别是 `9.0.321`、`10.0.404`。原 .NET 9 两个共享框架末版均为 `9.0.23`，已于 2026-11-10 结束支持。.NET 10 LTS 两套服务基线均为 `10.0.15`，支持期限登记至 2028-11-14。[支持政策](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core) · [正式发行索引](https://builds.dotnet.microsoft.com/dotnet/release-metadata/releases-index.json) · [.NET 9 明细](https://builds.dotnet.microsoft.com/dotnet/release-metadata/9.0/releases.json) · [.NET 10 明细](https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json) · [既有服务公告逐条清单](r5-first-maintenance-runtime-servicing.tsv)

| macOS ARM64 实测入口 | 本轮适用性及责任 |
| --- | --- |
| `net9.0` Web.Host、Migrator（两套均为 `9.0.10`） | 两个入口的 `Microsoft.NETCore.App` 已知落入运行时 CVE-2026-109475 所列版本范围，`Microsoft.AspNetCore.App` 已知落入 CVE-2026-70175 和 11 月 ASP.NET Core 公告的受影响版本范围。具体功能暴露要按入口使用路径判断。部署方与应用维护者迁向受支持的 `net10.0`，并分别核对两个进程实际加载的 .NET 与 ASP.NET Core 补丁。`9.0.23` 是末版及历史迁移参考，9.0 线已结束服务。[运行时原公告](https://github.com/dotnet/runtime/security/advisories/GHSA-3g4v-f5gv-c7xf) · [ASP.NET Core 10 月公告](https://github.com/dotnet/announcements/issues/457) · [ASP.NET Core 11 月公告](https://github.com/dotnet/announcements/issues/504) |
| `net10.0` Web.Host、Migrator（两套均为 `10.0.15`） | 两个入口实际加载的两套共享框架均达到本轮服务基线，覆盖截至该版已明确的同期修复。部署方维持两套受支持补丁，更新后核验实际进程版本。已看过的 Windows 和 Linux 带外项范围与历史 macOS ARM64 组合不同，其他部署按当地平台查公告。[.NET 10.0.15 发行](https://github.com/dotnet/core/blob/main/release-notes/10.0/10.0.15/10.0.15.md) · [上轮分组件判断](r5-first-maintenance-review.md#microsoft-共享运行时服务公告) |
| 四入口的工具、独立包和生成代码 | CVE-2026-105544 对应 SDK/VSTest，实测 SDK `10.0.404` 已达公告修复版本。CVE-2026-118747 对应独立 Cbor 包，图中无此包。CVE-2026-118741 对应 Identity 生成工具及生成代码，图中无该工具包，固定模板使用自己的 `UserAppService.ResetPassword`。派生应用按实际工具、包图和生成代码分别判断。[VSTest 公告](https://github.com/dotnet/announcements/issues/517) · [Cbor 公告](https://github.com/dotnet/runtime/security/advisories/GHSA-vmv3-wvjp-wqpj) · [Identity 公告](https://github.com/dotnet/announcements/issues/525) |

**CVE-2026-56158 的精确组件与版本区间仍待核实。** 于 `03:13:32–03:13:33Z` 补查 Framework 文档修订。Microsoft 的发行元数据和正式发行说明同时把该 ID 列在 2026-07-14 的 `.NET 9.0.18` 和 `.NET 10.0.10` 的安全修复清单，标题只给出 .NET 远程代码执行。两份说明的 Git 历史均登记于 `2026-07-14T18:03:03Z`。Microsoft 在 `2026-08-14T20:45:56Z` 合并 #55445，从 **Windows .NET Framework** 的 7 月累积更新说明移除此条，PR 说明事件曾降级。该英文文档标明修订于 2026-08-17。此证据确认的是 Framework 文档的更正日期。现代 .NET 两代发行说明仍保留该 ID。[.NET 9.0.18](https://github.com/dotnet/core/blob/main/release-notes/9.0/9.0.18/9.0.18.md) · [.NET 10.0.10](https://github.com/dotnet/core/blob/main/release-notes/10.0/10.0.10/10.0.10.md) · [Microsoft 文档修订 PR](https://github.com/dotnet/docs/pull/55445) · [修订后的 Microsoft Learn 公告](https://learn.microsoft.com/en-us/dotnet/framework/release-notes/2026/07-14-july-cumulative-update)

MSRC 单条 UI 返回前端壳，MSRC API、CVE Program API、官方 CVEProject 文件及其内容 API 均返回 404。7 月和 11 月 CVRF 均 HTTP 200，未列此 ID。NVD 精确查询成功返回 0 条，GitHub 的 NuGet 分类六个精确查询亦均为空。缺少按子组件、版本区间和 RID 表述的官方范围，单条公告的修订日期及现代 .NET 是否另有撤回也缺直接证据。两套 `9.0.10` 早于 7 月登记版本，两套 `10.0.15` 晚于同期登记版本，现有材料只允许按发行时间排序。四入口对该 ID 的精确适用性待 MSRC、CVRF 或 CVE Program 提供产品矩阵后复核。此缺项落在服务公告的组件映射，已确认的 9.0 停止支持、10.0 服务基线及两源维护包核查各有独立依据。应用按已确认的服务基线行动，若后续公告指向独立包，再按四图精确匹配。[MSRC 单条](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2026-56158) · [7 月 CVRF](https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Jul) · [11 月 CVRF](https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Nov) · [CVE Program 单条](https://www.cve.org/CVERecord?id=CVE-2026-56158) · [NVD 精确查询](https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2026-56158)

## 本轮维护决定

**维护包无需补丁。** 本轮审查以公开 `v10.5.2` 的固定输入为限。上轮要求补丁的内建集合映射问题已随本版引擎修复，三个原名命中项都有本版同摘要 DLL 和对应生产源码的回补证据。四入口的实际包身份无有效公告匹配。未决的 14 基线兼容项尚未达到各自回补条件。CVE-2026-56158 缺现代 .NET 的组件矩阵，影响该 ID 的部署适用性判断，目前没有指向四图中维护包的独立证据。[上游处置](#三仓六分支与上轮未决项) · [两源匹配及实包](#四入口包公告复核) · [共享运行时](#共享运行时与-cve-2026-56158)

| 负责方 | 行动 | 下次启动条件 |
| --- | --- | --- |
| 维护包 | 继续采用公开组合中的三份精确映射版本及十份沿用包。收到表内具体兼容场景或已确认适用的上游修复后，再确定负责子仓和定向实包验收。 | 三仓六分支、标签、发行或仓库公告变化，或收到本版复现。重新制包时以实际 DLL 重验三项防护与集合顺序。 |
| 模板 | 继续以 `2e953687` 和四份公开消费图为基线，保持现有包约束。模板派生、更换依赖或 Identity 相关代码后，以实际入口重新还原并检查生成代码。 | 新模板提交、包更新或收到工具链公告。分别复核 Web.Host、Migrator 的图及新库安装与同库接续。 |
| 运行环境 | 把仍运行两套 `.NET 9.0.10` 的部署迁至支持中的 .NET 10 LTS。本轮目标为两套 `10.0.15`，上线时按官方最新服务版确认实际加载路径和版本。 | 官方服务版、配置或部署平台变化，或 MSRC、CVRF、CVE Program 给出 CVE-2026-56158 的组件范围。 |
| 应用 | 在公开版本上按自身配置复验内建及按键集合、`MaxDepth` 和已有对象更新。存量应用先将自己的备份恢复到隔离库，验证迁移与回退点，并检查两个入口的部署运行时。R4 迁移指南的源端和目标端均固定为同一批 `v10.5.1` 公开包。采用 `v10.5.2` 时，按 R5 四图核对三份新映射包，参照 R5 同一公开包组合从 `net9.0` 到 `net10.0` 的同库接续，以及升级前后两份备份实际恢复的验收记录。[R4 迁移指南及版本](r5-r4-net10-migration.md#核对源与目标) · [R4 恢复点操作](r5-r4-net10-migration.md#创建恢复点并用目标版回读) · [R5 公开同库升级及双恢复点](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/consumption-validation.md#sql-server-与租户业务) | 切换维护组合、调整映射配置、升级数据库 Provider 或 Angular，或遇到上表列出的兼容条件。按实际组合核对包图、进程、生成的 Identity 代码和平台。 |

## 下轮检查点与验证边界

- 上游按本轮六条完整 SHA、Release、标签及仓库公告的分页终点接续，逐个保留四项兼容问题的触发条件。
- NuGet 用本轮 `base` 和 `update` 水位做对照，读取新索引中的全部页。GitHub 包公告从本轮最早读取 `2026-11-27T03:08:35Z` 起重叠检查，版本图变化时重做存量匹配。
- Microsoft 从 `2026-11-27T03:08:30Z` 起重叠读服务源，按 `9.0.23` 末版、`10.0.15` 服务版和已读公告接续。CVE-2026-56158 另保留 7 月两代发行记录、8 月 Framework 文档修订及 MSRC/CVE 单条入口。
- 回读了公开附件、生产 gitlink、R5 新引擎专项、四入口原图、历史进程回执和依赖清单。OpenSpec 严格验证 16 项通过。原始命令、UTC 时间、分页响应、退出码、匹配清单和候选摘要保存在验证机主仓的 `.git/review-r5-public-patch-baseline/package-2/`。
- 业务与加载结论取同一签后实物或同 DLL 摘要的既有通过轮。本轮未重新运行 SQL Server、浏览器或专项进程。精确 CVE 组件和现代 .NET 单条修订、CLR 实际低栈，以及 Windows、Linux、其他数据库 Provider 和 Angular 组合均保留为未验证范围。
