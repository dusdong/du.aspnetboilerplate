# R5 集合映射补丁的固定模板验收

正式补丁已于 2026-11-27 公开。新装可按公开指南从 nuget.org 还原。已有 R4 的应用维护者可以按消费者指南，在专用测试库演练切至 R5 再切回 R4，核对两版各自写入的数据。发布者留存的输入用于历史 Angular 复跑。[R5 新库安装指南](r5-public-install.md) · [独立消费者指南](r5-consumer-package-rollback.md) · [独立消费者验收](#独立消费者验收) · [历史 Angular 实测](#公开-r4r5-同库回退实测) · [公开发行与验收记录](r5-public-release.md)

本轮候选由 `Du.AutoMapper 14.0.1`、`Du.AutoMapper.Collection 11.0.1`、`Du.Abp.AutoMapper 10.5.2` 和十个 R4 公开维护包组成。三包冻结批次 SHA-256 是 `8d0d4dc762a3582327d8829e5952fadbd55b7448d7c2de85c32e6a76d6a3cf40`，模板固定在 `2e9536872673a7ff1986a19e798c51684d16afe5`。三个子仓的编译提交、实际生产树、冻结补丁、主包及符号包摘要见批次交接记录。[三包冻结与独立消费](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md#批次交接)

公开旧引擎在有界普通 `Map` 用例中仅因预热顺序变化，就出现 3/6 与 6/6 的正式调用通过数。候选两侧均为 6/6。固定模板验收覆盖真实启动、迁移、租户授权与用户业务；回到完整 R4 时，仍须按独立映射对照评估旧引擎的集合限制。[共享集合计划对照](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/shared-collection-plan-observation.md)

## 复跑

使用 macOS ARM64、SDK `10.0.404`、两项 `9.0.10` 和两项 `10.0.15` 共享框架。两代使用同一份固定 Angular production 原件。准备带 `pymssql`、Playwright 的 Python 和 Chrome 或 Playwright Chromium，以及只监听环回的专用 SQL Server Developer。按历史入口提供无凭据运行配置和三个凭据环境变量。升级轮沿用已验的 R3 登录前备份副本。运行需可访问 nuget.org；每个干净构建使用独立的源码和 NuGet 缓存。[运行配置与凭据变量](r3-template-runtime-baseline.md#复跑) · [固定 Angular 与登录前备份](r3-template-net10-upgrade.md#完整运行复验)

从主仓根目录执行。将 `R5_BATCH_ROOT`、`R5_BATCH_SHA256` 分别指向交接的 `frozen/` 和验收端独立登记的摘要，`R3_FROZEN_ROOT` 指向历史原件根目录。验证机的历史原件根是 `.git/`。将 `R5_TEMPLATE_EVIDENCE` 指向证据目录，`R5_RUNTIME_CONFIG` 指向专用实例的配置。三个动作可依次复用同一实例及环回端口，每次产生独立证据目录和隔离库名。

```sh
python -B eng/r5_template_consumer.py install \
  --batch-root "$R5_BATCH_ROOT" --batch-sha256 "$R5_BATCH_SHA256" \
  --frozen-root "$R3_FROZEN_ROOT" --runtime-config "$R5_RUNTIME_CONFIG" \
  --evidence-root "$R5_TEMPLATE_EVIDENCE"

python -B eng/r5_template_consumer.py upgrade \
  --batch-root "$R5_BATCH_ROOT" --batch-sha256 "$R5_BATCH_SHA256" \
  --frozen-root "$R3_FROZEN_ROOT" --runtime-config "$R5_RUNTIME_CONFIG" \
  --evidence-root "$R5_TEMPLATE_EVIDENCE"

python -B eng/r5_template_consumer.py switch \
  --batch-root "$R5_BATCH_ROOT" --batch-sha256 "$R5_BATCH_SHA256" \
  --frozen-root "$R3_FROZEN_ROOT" --runtime-config "$R5_RUNTIME_CONFIG" \
  --evidence-root "$R5_TEMPLATE_EVIDENCE" \
  --r4-batch-root "$R4_BATCH_ROOT" --release-manifest "$R4_RELEASE_MANIFEST" \
  --verified-downloads "$R4_VERIFIED_DOWNLOADS"
```

`switch` 另外需要 R4 交接冻结目录、固定首发清单和完整的已验签下载登记。两个 R4 阶段各自通过原 R4 入口在空缓存从 nuget.org 还原全部公开包。候选阶段仅将三个精确 ID 映射到单独的本地源，其他包从 nuget.org 还原。两代均核对实际 nuspec、还原图、Release 编译引用和输出 DLL，再核对实际加载路径及摘要。R4 候选制备和公开发行的 OpenSpec 均已归档时，公开源复跑从原协调提交核对生产 gitlink，并在当前执行提交核对固定模板。活动制备、活动公开发行和冻结源模式仍核对当前提交的生产 gitlink。[入口](../../eng/r5_template_consumer.py) · [R4 公开源复跑](r4-release-candidate.md#公开源模板消费)

### 公开包切换复跑

按公开输入运行后端 API 演练见[独立消费者指南](r5-consumer-package-rollback.md)。本节用于复跑发布者的固定 Angular 验收。

在主仓根目录执行 `switch-public`。使用固定模板 `2e9536872673a7ff1986a19e798c51684d16afe5`、SDK `10.0.404`、macOS ARM64、.NET 和 ASP.NET Core `10.0.15`、专用环回 SQL Server Developer `16.0.4236.2` 与冻结 Angular production 客户端。准备带 `pymssql` 和 Playwright 的 Python、Chrome 或 Playwright Chromium，按运行基线的环境变量约定注入测试实例和模板管理员凭据。入口每轮生成新库名，从空库开始接续三段。[运行配置与凭据变量](r3-template-runtime-baseline.md#复跑)

`R4_BATCH_ROOT` 和 `R5_BATCH_ROOT` 分别指向两版发行冻结目录。实跑使用的 `batch.json` SHA-256 分别为 `4d25f237938d04aeb985c2057a6287ba0f18425b94d73e9c494e313684470757` 和 `b914f5669c504a3a85cd7120fb63ff0d14667924d6dd0ff1f92fea9a1a76eaf1`。每个版本分别使用公开校验附件、附件绑定的发行清单和签后下载登记，以及对应的历史公开升级通过轮目录。历史目录需保留父报告、原始还原图、资产清单与输出清单。两版公开附件和历史报告身份见审查记录。[公开发行与源码](r5-public-patch-review.md#公开发行与源码) · [四入口的原始还原图](r5-public-patch-review.md#四入口的原始还原图)

```sh
python -B eng/r5_template_consumer.py switch-public --tfm net10.0 \
  --batch-root "$R5_BATCH_ROOT" --batch-sha256 "$R5_BATCH_SHA256" \
  --r4-batch-root "$R4_BATCH_ROOT" --frozen-root "$R3_FROZEN_ROOT" \
  --r4-checksums "$R4_CHECKSUMS" --r4-release-manifest "$R4_MANIFEST" \
  --r4-verified-downloads "$R4_DOWNLOADS" --r4-baseline "$R4_BASELINE" \
  --r5-checksums "$R5_CHECKSUMS" --r5-release-manifest "$R5_MANIFEST" \
  --r5-verified-downloads "$R5_DOWNLOADS" --r5-baseline "$R5_BASELINE" \
  --runtime-config "$R5_RUNTIME_CONFIG" --evidence-root "$R5_TEMPLATE_EVIDENCE"
```

每段从独立空缓存，仅用 nuget.org 源还原。入口先核对发行证据和两个完整包图，再建库执行业务。公开输入或包图偏离时先定位报告的失败阶段。业务读回失败时，从 `report.json` 的 `sql.creations` 核对已有创建回执与数据库读回状态，从 `businessReads` 查看每次授权查询和未执行阶段。复跑生成另一个独立目录和新库。

## 本机验收结果

本轮在 macOS ARM64 `27.2.1`（`26B131`）运行原生 Release 应用，SQL Server Developer `16.0.4236.2` 在专用实例 `r5-template-20261126` 供测试，浏览器为 Chrome `158.0.8127.37`。冻结 Angular 客户端有 1,193 个文件，服务副本只改前后端两个环回地址，实载脚本为 `main-PZGEMKYC.js`。本机证据根为 `.git/review-r5-runtime-migration-readiness/template/`。

每个 Web.Host 还原、编译和输出均核对 13 个维护包，实际加载 11 个 ABP DLL 和唯一 AutoMapper 引擎。每个 Migrator 核对 10 个维护包，实际加载七个 ABP DLL。两类入口均记录 Collection 仅在输出，Migrator 的引擎和适配器也仅在输出。启动观测绑定本轮 PID、Release 路径、共享框架和 DLL 摘要。

### 候选的新库安装与两代接续

`install` 退出 0。在新建 SQL Server 库 `r3_template_e48627926219e466_source`（数据库 GUID `2917696B-ED19-490E-A4B1-8B400AA45345`）中，Migrator PID `58647` 的 33 条迁移命令均绑定本库，读回 30 条迁移历史。Host PID `59253` 经认证调用 `User/Create` 写入租户 1 的用户 `r5usere48627926219e466`（ID 3）。用 Host PID `59497` 和冻结 Angular 登录 `Default/admin`（租户 1，账号 2），取得 `Pages.Users`，从同库返回唯一用户及实际页面行。查询及配置为 HTTP 200。成功登录行从 0 增至 1，再增至 2。报告 `runs/r5-template-install-890xg2dq/report.json` SHA-256 为 `1dcc6297cb20b1ea5f02ba51330a1238f90321302cbbb49cc643876f9cf6e07e`。

`upgrade` 退出 0，26 个阶段均通过。由同一冻结备份恢复的候选库为 `r3_template_3bff0c453159f995_candidate`（GUID `D6CC6BA6-B3EC-4E8D-A88F-222DED5AEC14`），独立对照库为 `r3_template_3bff0c453159f995_control`。两代 Migrator 各有三条实际迁移命令绑定候选库。30 条迁移 ID 和版本及 SQL Server 目录保持一致。两代 Host 的授权查询都在候选库返回用户 ID 3、`r3usercf4314cdfe038c35`，并在冻结 Angular 页面显示唯一结果。

| 阶段 | 实际 .NET／ASP.NET Core 共享框架 | Migrator／Host PID | 候选库／对照库成功登录行总数 |
| --- | --- | --- | --- |
| `net9.0` | `9.0.10`／`9.0.10` | `63443`／`63683` | 1／1 → 2／1 |
| `net10.0` | `10.0.15`／`10.0.15` | `64472`／`64724` | 2／1 → 3／1 |

升级前后各自备份并实际恢复至独立 SQL 库。恢复后分别读回成功登录行 ID 1、2 和 1、2、3，以及相同租户授权和查询用户。报告 `runs/r5-template-upgrade-py7e249f/report.json` SHA-256 为 `61cf55ef86d8b0db9f71ea0ec54fe3c6f9b83818ef440f302ecd3341870ac178`。

### 固定 .NET 10 的三阶段同库切换

`switch` 退出 0，20 个阶段均通过。三个阶段的 Web.Host 与 Migrator 均使用 `net10.0`、.NET 和 ASP.NET Core `10.0.15`。每阶段从独立空缓存还原 94 个 Host 包和 66 个 Migrator 包，分别包含 13 和 10 个维护包。回退阶段与首阶段的全部维护包版本、公开还原归档和 DLL 摘要逐项一致。候选阶段恰好替换三份映射包。

| 包 | 公共 R4 版本及 DLL SHA-256 | 本地候选版本及 DLL SHA-256 |
| --- | --- | --- |
| `Du.AutoMapper`，`lib/net8.0/AutoMapper.dll` | `14.0.0` · `12fcba523f7f7199215764b29c5d330aa363c433fa14d4e72257ce835a87e5e1` | `14.0.1` · `5ae7cbd55d61bb1848a3223d1f7d33eae5cc6c27ed17ee5509c84f62c506d82d` |
| `Du.AutoMapper.Collection`，`lib/net8.0/AutoMapper.Collection.dll` | `11.0.0` · `8f64b1194121a7dd5be23d6bffa7456765590905f2ae5dff5414bcc9f5adfd58` | `11.0.1` · `0d942343005bb358f381fb9d09543a04d66affd7a90029cb4a8ef33ad457ca2e` |
| `Du.Abp.AutoMapper`，`lib/net9.0/Abp.AutoMapper.dll` | `10.5.1` · `87e3cbbe1a600adb8b4cd51feb638ef0271d75a7126b6d7f7a85c8f96cadf07f` | `10.5.2` · `82bb376e405ba42dbbe2bd7caab4590691a0374bb4e0772797cbf3e24cb95137` |

三阶段使用 `r3_template_40b9a3576cd6e80d_source`，数据库 ID 12、GUID `7DC26ADE-DD56-4C04-B0B2-83A28EC1A1BB` 和物理文件路径持续一致。首阶段写入 Host PID `64769` 通过认证及 `User/Create` 创建 `r5user40b9a3576cd6e80d`，用户 ID 3、租户 ID 1、创建者 ID 2。三轮各在全新浏览器上下文登录 `Default/admin`，取得 `Pages.Users`，用同一关键字返回唯一用户及实际页面行，HTTP 200。观察器将每次查询的计数和列表 SQL 绑定到该阶段实际 Host PID 和同一 SQL 库。SQL 复核用户名、姓名 `Runtime Fixture`、邮件、启用状态、创建者和创建时间逐项一致。

| 阶段 | Migrator／查询 Host PID | 迁移与写入 |
| --- | --- | --- |
| 完整公开 R4 | `64426`／`64951` | 33 条实际命令建成含 30 条迁移记录的空库。应用创建用户，认证及浏览器登录分别新增成功行 1 和 2。 |
| 三候选＋十公开包 | `65475`／`65635` | 三条实际迁移命令，迁移历史、已核对目录、业务用户与先前登录行一致。浏览器新增成功行 3。 |
| 回退完整公开 R4 | `66125`／`66194` | 三条实际迁移命令，保留用户及成功行 1、2、3。浏览器新增成功行 4。 |

报告 `runs/r5-template-switch-j16yrlho/report.json` SHA-256 为 `ed39277503e576f52d34823eb467b22479a38ed3a373ba84dec2cdba9ed58e61`。证据目录中的 `evidence-index.json` 汇总各轮入参、程序集、数据库、用户、权限和备份摘要。各轮保留实际命令、退出码、原始还原图、迁移连接、查询观测和浏览器结果。首轮升级读取了错误的候选字段，在还原前退出 1。修正后一次运行已完成真实升级，在最终登记时误用 R4 冻结分支，外层退出 1。修正登记条件后从空缓存及独立恢复库复跑，正式结果退出 0；原尝试及其备份保留。

### 公开 R4、R5 同库回退实测

三段的 Web.Host 各还原 94 个包（13 个维护包），Migrator 各还原 66 个包（10 个维护包）。首末 R4 的包图一致，各版均匹配对应历史公开 `net10.0` 入口。中段三个映射包依次使用 `14.0.1 / 11.0.1 / 10.5.2`，首末为 `14.0.0 / 11.0.0 / 10.5.1`。每个入口只改变四条精确依赖约束和三个 DLL 的摘要，资产路径及角色保持一致。每个 DLL 在所选编译、所选运行、实际编译引用和 Release 输出各留一条摘要对照。两版十个沿用包的签后归档摘要一致，三段均从实际缓存逐入口对账。[四条约束与三个 DLL](r5-public-patch-review.md#解析版本依赖边和所选资产)

2026-11-27，`switch-public` 在上述固定组合退出 0，22 个阶段通过。各进程实际使用 .NET 和 ASP.NET Core `10.0.15`。Web.Host 加载适配器与唯一引擎，Collection 在 Release 输出中。Migrator 的三个映射 DLL 均只在 Release 输出中。Chrome `158.0.8127.37` 实际加载冻结的 `main-PZGEMKYC.js`，1,193 个前端文件中仅配置文件的两个环回地址按本轮调整。

数据库为 `r3_template_61b4e4c2c5237070_source`，数据库 ID 5、GUID `0D4FFD6F-8FAD-4D12-B7A7-E73744251CD8`，三段的实例、物理文件和数据库身份一致。首次迁移写入 30 条历史记录，后两段保持这些迁移 ID 和版本及已核对的表结构。A、B 的独立应用创建回执对应 ID 3、4，直接 SQL 读取核对租户 1、创建者 2、创建时间、姓名、邮件和启用状态。

| 包阶段 | Migrator PID／实际迁移连接观测 | 写入和浏览器授权读回 | 成功登录行总数 |
| --- | --- | --- | --- |
| 公开 R4 `v10.5.1` | `34649`／33 条 | Host `34863` 创建 A，Host `34945` 查回 A。 | 0 → 2 |
| 公开 R5 `v10.5.2` | `35273`／3 条 | Host `35438` 查回 A，Host `35651` 创建 B，Host `35725` 查回 B。 | 2 → 5 |
| 回退公开 R4 `v10.5.1` | `35906`／3 条 | 同一 Host `35945`、同一管理员登录，分别用两个关键词查回 A、B。 | 5 → 6 |

每次关键词查询均由 `Default/admin`（租户 1、账号 2）获 `Pages.Users`，返回 HTTP 200、总数 1，响应 ID、业务字段和页面用户名与各自创建、SQL 读回结果相符。末段 A、B 的请求标识分别为 `2db70389aff965a8534d5681e43d471b`、`b13b1100d6ccc28b0c65f05195d7cc80`。两个请求的各自计数和列表均从同一隔离库实际执行。登录增量分别来自 1 次写入会话加 1 次浏览器登录、1 次写入会话加 2 次浏览器登录、1 次浏览器登录。三段 Migrator 均保持成功登录行。

本机证据根为 `.git/validate-r5-public-package-rollback/package-2/attempt-1/`。实际命令、工作目录及退出码见上一级的 `attempt-1-wrapper.log`，`evidence-index.json` 关联三段的原始还原图、签后输入、迁移及逐人授权证据。正式运行目录为 `runs/r5-template-switch-public-ufbvqw2v/`，`report.json` 的 SHA-256 为 `3c2471e58d509bf3b5484a5a3b46f86d77a959ec3aafae0c9aed5f4deb928673`，`public-graph-comparison.json` 的 SHA-256 为 `539b69f6c0c5218aab201dcfa669707117ed40c34b4491bb82461278ff8a26ea`。回退两次授权读回分别保存在 `rollback-AB-A-read.json`、`rollback-AB-B-read.json`。

收尾移除了 13 个临时缓存目录及回退阶段的 2,729 个重复解包文件，正式运行目录占用减少约 430 MiB。清理后逐项核对了 6 张入口还原图、39 份签后维护包归档及 1,683 个实际 Release DLL，A、B 的创建回执与授权查询证据均保留。清单和核对日志位于验证机 Git 目录下的 `validate-r5-public-package-rollback/closeout/`，见其中的 `交接.md`。复跑时使用新的证据目录和独立空缓存。

同库切换保留了两版各自创建的业务用户和上述登录写入。切回 R4 同时恢复旧集合映射行为，本轮业务覆盖为用户创建和查询。历史 `switch` 切换使用本地候选，验证的是首段 R4 创建的一个用户和后续登录行。

备份恢复另有历史实测。公开 R5 接续轮分别恢复升级前后备份，读回同一业务用户和 2、3 条成功登录行。原版应用回退实测也对照了两个恢复点，选择较早恢复点会舍弃其后的写入。本轮公开包切换全程使用同一库状态，A、B 和 6 条成功登录行属于这次同库实测。Windows、Linux 原生应用、其他运行时、Provider、客户端、集合业务及生产环境仍按各自组合验证。[公开 R5 接续及恢复实测](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/consumption-validation.md) · [原版双恢复点实测](r3-original-template-rollback.md#正式运行结果)

### 独立消费者验收

2026-11-27，从干净目录按指南原文执行成功，退出码为 `0`。指南 SHA-256 为 `ae9ac3abc6def77b0b0e35039656de8227c993bfe1e6c3b6de9518c592c8cdb1`，从中提取的脚本 SHA-256 为 `3eca781f8cf1c44a762da0d8a1b713c09e2756cca44149ff211c951851bfd8c1`。[已验指南与完整步骤](r5-consumer-package-rollback.md)

实际环境为 macOS ARM64 `27.2.1`（`26B131`）、Python `3.14.7`、pymssql `2.4.6`、SDK `10.0.404`、SQL Server Developer `16.0.4236.2`。六个 `net10.0` 入口进程均选择 .NET 和 ASP.NET Core `10.0.15`。两版分别从空缓存经 nuget.org 还原模板 `2e9536872673a7ff1986a19e798c51684d16afe5` 的对应引用。Web.Host 各 13 个、Migrator 各 10 个维护包的版本、来源和实际还原归档的签后 SHA-256 分别匹配公开附件。每个入口的三份映射 DLL 与包图选中的归档成员字节一致。

实际执行的演练命令如下。`guide` 为冻结的原文快照，`work` 为该次新建的工作根。凭据由执行进程注入。四个入口的 `dotnet restore`、`dotnet build` 均退出 `0`。各阶段在对应 Release 目录运行 `dotnet AbpCompanyName.AbpProjectName.Migrator.dll -q` 与 `dotnet AbpCompanyName.AbpProjectName.Web.Host.dll`。

```bash
"$work/venv/bin/python" "$work/exercise.py" --guide "$guide" --output-parent "$work" \
  --sql-port 60223 --sql-login sa --server-name du-consumer-rollback-b128a22a --http-port 60222
```

| 阶段 | Migrator / Web.Host PID | 同库观察 | 新增成功认证行 ID |
| --- | --- | --- | --- |
| R4 | `33745` / `34150` | 空库迁移后有 30 个迁移 ID，创建 A `durollbacka49e981230fc2`（ID 3）并从 SQL 回读。 | 1 |
| R5 | `35220` / `35390` | 迁移前后历史均与首段一致，查回 A，创建并单独查回 B `durollbackb49e981230fc2`（ID 4）。 | 2 |
| 封存的 R4 | `36255` / `36335` | 原目录的两套完整输出通过清单核对，迁移历史仍一致。一次新登录后分别查回 A 和 B。 | 3 |

六个进程均退出 `0`。数据库为 `DuRollback_49e981230fc2`，ID `5`，GUID `53772F67-193E-48D3-98A5-8C6C775C7A5E`。四次逐人授权查询均由 `Default/admin`（租户 1、账号 2）发起，获 `Pages.Users`，返回 HTTP 200、总数 1，ID、用户名、姓名、邮箱和启用状态与创建回执、直接 SQL 读回对应。末段的两个请求标识为 `9656cbcc2b46dd21` 与 `ccd7df291be72b9c`。

在 R4 产物副本中替换 Migrator 的 `AutoMapper.dll` 后，清单校验报告该文件预期与实际摘要不同。该次切换在连接预检前即被拒绝，未启动 Migrator 或 Host。库身份、迁移、用户和认证记录的前后快照相同。另以两个定向模拟确认 R5 创建 B 后查询返回 403 时仍可读回创建回执及 SQL 行，以及回退阶段 B 返回多条时仍分别保留 A、B 的结果。

验证机 Git 目录下的 `document-r5-consumer-package-rollback/package-1/` 保留五轮命令和初次错误、`handoff.md` 与独立回读。正式结果目录为 `attempt-5/du-package-rollback.V2BQWdY9/run-6kv7gbrm/`，含四张入口包图、签后摘要、封存清单、三段进程和 SQL、逐人回执及替换 DLL 的前后快照。

本次支持结论限于上述模板、运行时、平台和 SQL Server 组合的用户创建与授权查询 API。Angular 和恢复点行为继续引用其独立实测。[历史 Angular 实测](#公开-r4r5-同库回退实测) · [历史备份恢复实测](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/consumption-validation.md#sql-server-与租户业务)

### 支持范围与公开发行交接

历史候选验收适用于上表的 macOS ARM64、固定模板、SQL Server Developer、指定共享运行时及同一冻结 Angular 产物。`net9.0` 用于存量接续对照。历史三阶段切换实测了首阶段创建的业务用户和后续登录行的保留，最终备份执行了 `RESTORE VERIFYONLY WITH CHECKSUM`。两个公开发行之间的回退范围见[公开 R4、R5 同库回退实测](#公开-r4r5-同库回退实测)。[运行时迁移指引](r5-r4-net10-migration.md) · [R4 实测支持范围](r4-release-candidate.md#实测支持矩阵)

2026-11-26，主仓 `99f44b7` 固定了上述原冻结批次的三个生产提交。公开发行准备从新引擎 `54f6277a` 制备含公开安装说明的主包，独立登记新批次与受影响的复验。新引擎已交付到子仓，本次归档的协调提交固定了对应 gitlink。上述本地验收结果仍对应原冻结批次。[原批次源码树与编译提交](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md#批次交接) · [新批次实物与来源](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/source-and-engine-validation.md#三包待发批次) · [新批次模板验收](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/consumption-validation.md#固定模板与同库业务)

发行准备交接记录六份冻结归档、三个 PDB、十个沿用包、依赖放行和续作条件。正式发行在公开源上复验了两轮发布者消费与独立消费者新装。[公开发行与验收记录](r5-public-release.md) · [待发交接](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md) · [发行前演练](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-rehearsal.md) · [公开发行规范](../../openspec/specs/public-package-release/spec.md) · [R4 发布者交接](r4-release-candidate.md#发布者交接)

#### 执行待发交接手册

本节保存 `v10.5.2` 已执行的发行者命令。附注标签绑定 `cebc3e38a511783092963893bf5ad3161d0f0a19`。复核正式发行可用归档手册的 `r5_publish_release resume`。原 NuGet 上传、续作和同一草稿交付命令从主仓根目录启动 `/bin/sh`，在同一会话中定义。[公开发行与验收记录](r5-public-release.md) · [tag 核定](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md#发行前核定-tag) · [已归档的正式发行任务](../../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/tasks.md)

2026-11-27 用隔离命令替身复核了归档手册的 Shell 行为。`/bin/sh` 在本地 tag 缺失时进入预期分支，归档上传函数模拟失败时返回原退出码 17 并给出凭证路径。在 zsh 中，这两个分支给只读变量 `status` 赋值时均退出 1。[归档命令](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md#发行前核定-tag)

```sh
: "${R5_RELEASE_WORK:?请先设置本次实际发行唯一的进度目录}"
R5_BATCH=${R5_BATCH:-.git/prepare-r5-mapping-patch-release/batch/frozen}
R5_BATCH_SHA=b914f5669c504a3a85cd7120fb63ff0d14667924d6dd0ff1f92fea9a1a76eaf1
R5_MANIFEST=${R5_MANIFEST:-.git/prepare-r5-mapping-patch-release/rehearsal/r5-release-manifest.json}
R5_MANIFEST_SHA=2f4ba12a0752739eaafb522d5c9e0a20abd241176646ae31d4748e5102a3fa02

r5_readback() {
  python3 -B eng/r5_public_release.py --batch-root "$R5_BATCH" --batch-sha256 "$R5_BATCH_SHA" \
    --manifest "$R5_MANIFEST" --manifest-sha256 "$R5_MANIFEST_SHA" --work "$R5_RELEASE_WORK" "$@"
}

r5_publish_main() {
  r5_readback upload --kind main --package "$@"
}

r5_publish_symbols() {
  r5_readback upload --kind symbols --package "$@"
}
```

执行 `python3 -B eng/r5_release_batch.py verify --batch-root "$R5_BATCH" --batch-sha256 "$R5_BATCH_SHA"` 核对冻结实物，执行 `r5_readback queue` 核对两份独立身份和上传队列。用 `r5_readback verify --main-only` 匿名预检。三包尚不可见且沿用包通过时退出 2。[冻结实物清单](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md#实物清单)

在工作流已进入 GitHub `main` 后，用账号 `dusdong` 运行仅登录验证。保留命令输出的运行 ID，等待成功，回读同一个运行中登录核对成功及上传步骤跳过的状态。发布必须沿用该次登录实际使用的主仓提交。若 `main` 有新提交，先完成新提交的登录验证。环境 `nuget-r5` 只允许 `main` 分支。短期凭据由 `NuGet/login` 交换并由对应 runner 的步骤使用。[NuGet Trusted Publishing](https://learn.microsoft.com/en-us/nuget/nuget-org/trusted-publishing)

```sh
R5_REPO=github.com/dusdong/du.aspnetboilerplate
gh workflow run publish-r5-mapping.yml --repo "$R5_REPO" --ref main -f mode=login-only
R5_LOGIN_RUN_ID= # 填入上一行返回的运行 ID
gh run watch "${R5_LOGIN_RUN_ID:?}" --repo "$R5_REPO" --exit-status
gh run view "$R5_LOGIN_RUN_ID" --repo "$R5_REPO" --attempt 1 \
  --json headSha,event,url,conclusion,jobs
```

核定并登记远端附注 tag 后，查找 `v10.5.2` 的现有草稿。首次使用时执行下列创建命令，已存在时核对并使用同一草稿。逐项暂存六份原件；若部分暂存命令中断，先回读已登记附件的 ID 和摘要，再仅上传缺少的原件。整批字节与草稿状态的回读必须通过。

```sh
gh release create v10.5.2 --repo "$R5_REPO" --draft --verify-tag \
  --title 'v10.5.2 映射集合上下文修复' --notes 'R5 待公开验收'
gh release upload v10.5.2 --repo "$R5_REPO" \
  "$R5_BATCH/feed/Du.AutoMapper.14.0.1.nupkg" \
  "$R5_BATCH/symbols/Du.AutoMapper.14.0.1.snupkg" \
  "$R5_BATCH/feed/Du.AutoMapper.Collection.11.0.1.nupkg" \
  "$R5_BATCH/symbols/Du.AutoMapper.Collection.11.0.1.snupkg" \
  "$R5_BATCH/feed/Du.Abp.AutoMapper.10.5.2.nupkg" \
  "$R5_BATCH/symbols/Du.Abp.AutoMapper.10.5.2.snupkg"
R5_DRAFT_ID=$(gh release view v10.5.2 --repo "$R5_REPO" --json databaseId,isDraft \
  --jq 'select(.isDraft) | .databaseId')
python3 -B eng/r5_oidc.py check-draft "${R5_DRAFT_ID:?}"
```

按 `Du.AutoMapper 14.0.1`、`Du.AutoMapper.Collection 11.0.1`、`Du.Abp.AutoMapper 10.5.2` 的主包依赖顺序过 gate。以下以引擎为例。两种归档分别以命令返回的 URL 识别运行，将其数字尾段填入 `RUN_ID`，等待该次运行结束并回读收据。主包必须公开验签和比对通过，才能发该包的符号或推进依赖它的主包。索引未就绪时继续执行相应的 `verify`。

```sh
ID=Du.AutoMapper
KIND=main
r5_publish_main "$ID" --owner dusdong --oidc "$R5_DRAFT_ID" "$R5_LOGIN_RUN_ID"
RUN_ID= # 填入本次主包运行的 ID
gh run watch "${RUN_ID:?}" --repo "$R5_REPO" --exit-status
r5_readback workflow-receipt --kind "$KIND" --package "$ID"
r5_readback verify --package "$ID" --main-only
```

```sh
KIND=symbols
r5_publish_symbols "$ID" --oidc "$R5_DRAFT_ID" "$R5_LOGIN_RUN_ID"
RUN_ID= # 填入本次符号包运行的 ID
gh run watch "${RUN_ID:?}" --repo "$R5_REPO" --exit-status
r5_readback workflow-receipt --kind "$KIND" --package "$ID"
r5_readback verify --package "$ID"
```

本地上传入口持有进度锁时检查依赖、目标及实物，持久化意向后才触发工作流。收到 GitHub 返回的运行 ID 并落盘后，最多读取该次首次尝试的身份五次，读取间隔两秒。这个窗口内，同一查询返回 HTTP 404、读取超时或身份字段暂未匹配时可以再读。日志只记录 HTTP 状态、超时或缺失与不匹配的字段名。身份完全匹配后，将运行 ID、意向和同提交登录验证 ID 写到目标附件的 label 作为单次放行。读取预算耗尽或遇到权限错误时，留存原意向与运行 ID，按下文回读。

托管 runner 只能处理对应 ID 的首次尝试。它下载一份指定归档，复核摘要，仅向官方 NuGet 源提交。主包使用 `--no-symbols`。上传步骤日志记录归档摘要、可识别的官方请求阶段、可识别的 HTTP 数值状态和 CLI 退出码。HTTP 状态用于定位失败，是否可继续仍以收据与服务查证为准。工作流触发退出 0 表示已登记放行，随后用 `workflow-receipt` 读取该次首次尝试的实际上传结果。该命令退出 0 表示已登记上传成功，仍须继续公开回读。退出 2 表示收据证实未启动，须先按下述方法登记未受理。其他退出保留意向查证。可用 `gh run view "$RUN_ID" --repo "$R5_REPO" --attempt 1 --json headSha,event,url,conclusion,jobs` 取回作业阶段和结论。

发布进程中断、运行异常或索引延迟时，保留并复用原 `R5_RELEASE_WORK`。同一项的收据文件名和已落盘的 GitHub 运行 ID 可从 `progress.json` 的 `uploadIntents` 取回。先重新执行 `workflow-receipt` 查询现有意向。匿名 404、暂无 PDB 和缺失收据均继续等待查证。GitHub 中重新触发同样的参数会取得不同运行 ID，Actions 的重新运行也无法通过首次尝试检查。

有该次上传的成功本地收据时，将 `PROOF` 指向该收据。否则由发布者从 nuget.org 发布者后台或支持渠道核定该次操作，核对包 ID、版本、归档种类、操作归属及响应所确认的结果，保存原始脱敏响应或支持记录。用 `shasum -a 256 "$ORIGINAL"` 独立计算原件摘要，为 `resolve` 另写一份 JSON。将 `receipt` 设为当前意向的收据文件名，`outcome` 设为 `confirmed`，`source` 设为 `nuget.org-publisher` 或 `nuget.org-support`，`reference` 设为原件路径（绝对路径或相对 JSON 所在目录），`referenceSha256` 填入独立计算的摘要。入口核对原件及摘要。符号必须回读正确的 PDB，主包必须通过归属、验签及内容核对。

```sh
r5_readback resolve --kind "$KIND" --package "$ID" --receipt "$RECEIPT" \
  --outcome confirmed --evidence "$PROOF"
```

恢复主包后运行 `r5_readback verify --package "$ID" --main-only`，恢复符号包后运行 `r5_readback verify --package "$ID"`。

只有本地收据证实 CLI 未启动，或发布者从 nuget.org 支持原始记录核实该次提交明确未获受理，才可登记 `not-accepted`。前者使用本地收据作为 `PROOF`。后者使用上述 JSON 格式，将 `source` 设为 `nuget.org-support`、`outcome` 设为 `not-accepted`，并附原始证据的路径与摘要。登记后使用同一发布函数重新过 gate，生成新意向和新收据。每次新意向都需要该次操作的独立证据，改名或复制已用原件仍会被拒绝。带有意向的归档使用 `resolve` 续作。

```sh
r5_readback resolve --kind "$KIND" --package "$ID" --receipt "$RECEIPT" \
  --outcome not-accepted --evidence "$PROOF"
```

三个主包、符号及十个沿用包均通过 `r5_readback verify` 后，独立登记 `verified-downloads.json` 的 SHA-256，再按归档手册执行真实公开消费验收。[正式公开后的验收](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md#正式公开后的验收)

正式公开 GitHub Release 前，保留草稿并先移除本次暂存附件。用 `python3 -B eng/r5_oidc.py check-draft "$R5_DRAFT_ID"` 回读六个精确名称、已登记 ID 和摘要，逐个以 `gh release delete-asset v10.5.2 "$ASSET_NAME" --repo "$R5_REPO" --yes` 移除对应附件并回读，确认草稿及 tag 未改变。三项公开消费通过后，按发行计划生成 `R5-PACKAGE-CHECKSUMS.json` 和发行说明。用 `gh release upload` 附上校验文件，用 `gh release edit v10.5.2 --repo "$R5_REPO" --notes-file "$R5_NOTES" --draft=false` 公开同一草稿。最后用归档手册的 `r5_publish_release resume` 回读外部状态和实际公开附件。[发行说明与校验附件](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md#正式公开后的验收)
