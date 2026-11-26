# R5 集合映射补丁的固定模板验收

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

### 支持范围与公开发行交接

本轮结论适用于上表的 macOS ARM64、固定模板、SQL Server Developer、指定共享运行时及同一冻结 Angular 产物。`net9.0` 只用于存量接续对照。三阶段包回退实测了首阶段创建的业务用户和后续登录行的保留。候选阶段未新增业务用户。包切换始终使用同一个库，三阶段最终备份执行了 `RESTORE VERIFYONLY WITH CHECKSUM`。Windows、Linux 原生应用、其他 SQL Server 版本或 Provider、其他客户端组合、候选阶段业务实体新增后的回退及生产部署待各自实测。[运行时迁移指引](r5-r4-net10-migration.md) · [R4 实测支持范围](r4-release-candidate.md#实测支持矩阵)

2026-11-26，主仓 `99f44b7` 固定了上述原冻结批次的三个生产提交。公开发行准备从新引擎 `54f6277a` 制备含公开安装说明的主包，独立登记新批次与受影响的复验。新引擎已交付到子仓，本次归档的协调提交固定了对应 gitlink。上述本地验收结果仍对应原冻结批次。[原批次源码树与编译提交](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md#批次交接) · [新批次实物与来源](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/source-and-engine-validation.md#三包待发批次) · [新批次模板验收](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/consumption-validation.md#固定模板与同库业务)

三包发行目前为本地待发，由维护者另行决定。交接记录六份归档、三个 PDB、十个沿用包、依赖放行和续作条件，并提供已演练的纯 nuget.org 消费命令。实际发行时按该交接补齐新包的公开下载、符号和业务验收。[待发交接](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md) · [发行前演练](../../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-rehearsal.md) · [公开发行规范](../../openspec/specs/public-package-release/spec.md) · [R4 发布者交接](r4-release-candidate.md#发布者交接)
