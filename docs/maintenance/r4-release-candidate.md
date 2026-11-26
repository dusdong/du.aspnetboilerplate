# R4 首发候选与本地验收

R4 已于 2026-11-26 公开发行。GitHub Release `458933029` 发布于 `2026-11-26T03:59:33Z`，以附注标签 `v10.5.1` 绑定主仓提交 `5758c8186b68dcc42ecc90164cf9d3f53cf3345e`。13 个主包及其符号来自本文登记的冻结批次，18 个公开 PDB 与冻结符号一致。[发行说明](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1) · [新库安装指南](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-INSTALL-net10.md) · [公开校验清单](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json)

[R4 组合清单](../../eng/r4_release_candidate.json)固定 11 个 `Du.Abp*` 包的 `10.5.1`、`Du.AutoMapper` 的 `14.0.0` 和 `Du.AutoMapper.Collection` 的 `11.0.0`。每个包登记生产仓、维护主页、旧包摘要，以及各目标 DLL 的路径和旧摘要。依赖和共享框架引用按 nuspec 目标组登记。裸版本表示包含该版本的下限，单个方括号版本表示精确约束。[验收稳定规范](../../openspec/specs/release-candidate-verification/spec.md) · [归档设计](../../openspec/changes/archive/2026-11-26-prepare-r4-first-release-candidate/design.md)

生产仓的 `baseCommit` 取自历史比较基点的 gitlink。`gitlinkCommit` 固定本轮协调仓的 Git 树，生产仓的 `finalCommit` 与该树中的三个 gitlink 一致。模板固定在 `2e9536872673a7ff1986a19e798c51684d16afe5`。R3 归档的相对路径和生产清单摘要来自[历史冻结登记](../../eng/r3_template_net9_reference.json)。

## 复验清单

在主仓根目录执行。归档存放在其他位置时，将 `--frozen-root` 指向保留历史冻结登记相对路径的根目录。

```sh
python3 -B eng/r4_release_candidate.py --frozen-root .git
python3 -B eng/tests/verify_r4_release_candidate.py --frozen-root .git
```

第一条命令读取并校验 5 份历史生产清单和 13 份主包，从实际 nuspec 及 DLL 导出逐目标对照。第二条命令用清单副本复验旧精确范围及缺失内部边，检查包、目标、依赖及预期和实际值的诊断。

## 生产与冻结

三个生产子仓须检出组合清单登记的干净提交。正式生产使用 macOS ARM64、.NET SDK `10.0.404` 和 .NET 8 运行时。归档复核还使用 .NET 9 运行既有 API 提取器。将 `REFERENCE` 指向固定的 AutoMapper 13.0.0 原版参考包，当前工作区的文件为 `.git/r3-automapper/package-1/references/automapper.13.0.0.nupkg`，入口会校验其摘要。[框架入口](../../aspnetboilerplate/nupkg/README.r4.md) · [映射引擎入口](../../AutoMapper/src/AutoMapper/ApiCompat/README.r4.md) · [Collection 入口](../../AutoMapper.Collection/README.r4.md)

```sh
python3 -B eng/r4_candidate_batch.py produce --engine-reference "$REFERENCE" --output "$PRODUCTION"
python3 -B eng/r4_candidate_batch.py freeze --production "$PRODUCTION" --baseline-root .git \
  --output "$BATCH_ROOT" --logs "$INSPECTION_LOGS"
```

`PRODUCTION`、`BATCH_ROOT` 和 `INSPECTION_LOGS` 使用尚未创建的目录。已有四阶段生产目录也可直接作为 `PRODUCTION` 复核。冻结核对生产提交和输入摘要，复制并验证实际归档，逐目标比对 Release 输出、程序集身份、公共及受保护 API、项目身份、Portable PDB 和提交源码。主包还须通过许可、署名、主页和安装说明核对。记录完整时生成 `batch.json`，其中 26 条归档记录及复核报告均用批次内相对路径、字节长度和 SHA-256 关联。独立生成的新归档需要按自己的摘要复验并绑定消费结果。

## 消费前验收

交接时完整复制冻结目录，消费前执行下列第一条命令。它使用[主仓固定的批次摘要](../../eng/r4_candidate_batch_reference.json)核对清单、主包、符号包和报告。只有校验成功后才将 `$BATCH_ROOT/feed` 映射为本轮维护包源。Python 消费入口可调用 `load_frozen_batch(batch_root)`，并在还原结果中继续比对归档摘要和实际使用的 DLL。复核需要 Git 中登记的生产对象与原 R3 对照输入。

```sh
python3 -B eng/r4_candidate_batch.py verify --batch-root "$BATCH_ROOT"
python3 -B eng/r4_candidate_batch.py recheck --batch-root "$BATCH_ROOT" \
  --baseline-root .git --logs "$RECHECK_LOGS"
python3 -B eng/tests/verify_r4_candidate_batch.py --batch-root "$BATCH_ROOT" \
  --baseline-root .git --logs "$NEGATIVE_LOGS"
```

本轮首份冻结目录在当前工作区的 `.git/r4-first-release-candidate/package-3/frozen/`，包与符号共 26 份。18 个目标的文件版本与对照一致，产品版本记录生产提交。1,692 条 PDB 文档摘要与生产 Git 对象一致，两个映射包的 5 个生成文档由 PDB 内嵌。六个已有实包探针与同批归档及实际加载的维护 DLL 的关联记录在同级 `bound-components/bindings.json`。模板和映射引擎的同批实测见下节。

## 2026-11-26 消费验收

模板验收使用协调提交 `19101266923a6422543a17e0963e3475c24923f2`、冻结批次 SHA-256 `4d25f237938d04aeb985c2057a6287ba0f18425b94d73e9c494e313684470757`，以及固定模板 `2e9536872673a7ff1986a19e798c51684d16afe5`。两代各用独立空 NuGet 缓存，13 个维护 ID 精确映射到冻结源的当轮副本，第三方依赖从 nuget.org 还原。两个 TFM 的 Web.Host 均编译及输出 13 个维护包的 DLL，Migrator 均为 10 个。两代 Host 实际加载 11 个框架 DLL 和唯一映射引擎。两代 Migrator 实际加载七个维护 DLL。其输出中的 `Abp.AutoMapper`、`AutoMapper` 和 `AutoMapper.Collection` 未被迁移路径加载。Host 的查询路径未加载 Collection。集合更新由本轮独立映射探针覆盖。

### 实测支持矩阵

| 场景 | 实测环境 | 结果 |
| --- | --- | --- |
| 固定模板换包及同目标运行 | macOS ARM64，SDK `10.0.404`，.NET 与 ASP.NET Core `9.0.10`，EF Core/Relational `9.0.18`，SQL Server Provider `9.0.5`，SqlClient `5.1.6` | Release 两入口通过，Migrator 和 Host 命中候选库。 |
| 同库接续升级 | macOS ARM64，SDK `10.0.404`，.NET 与 ASP.NET Core、EF Core/Relational 和 SQL Server Provider `10.0.15`，SqlClient `6.1.7` | Release 两入口通过。继续使用同一库和 30 条迁移，所核对的 36 张业务表结构一致。 |
| 原版应用从两份介质回退 | 同一 macOS ARM64 测试机，原版 .NET 与 ASP.NET Core `9.0.10`、ABP `10.2.0`、EF Core/Relational/Provider `9.0.5`、SqlClient `5.1.6` | 两份介质各自恢复、迁移、登录和查询均通过。 |
| SQLite、SignalR、日志、Module Zero 和映射定向消费 | macOS ARM64，核心 SQLite 分别使用 .NET `9.0.10`、`10.0.15`，其余探针使用 .NET `9.0.10` | 两代 HTTP 写入读取、SignalR 通知及断开、Log4Net 持久日志、SQLite 双租户角色写入及隔离、对象更新、按键集合与关系型投影通过。 |
| 引擎专项 | macOS ARM64，SDK `10.0.404`，独立 .NET `9.0.10` 进程加载 `lib/net8.0/AutoMapper.dll` | 三项定向回归通过。CLR 低栈分支按同一 DLL 的 IL、官方契约和注入异常的传播及恢复验收。实际 CLR 低栈触发未观测。 |

四个模板业务轮共用 SQL Server Developer `16.0.4236.2`、Chrome `158.0.8127.37` 和固定的 Angular production 客户端。维护版两代和原版两条回退路径均通过 `Default`（租户 1、账号 2）、`Pages.Users`、关键词 `r3usercf4314cdfe038c35` 的真实授权查询。响应 HTTP 200、总数 1、唯一用户 ID 3，页面唯一用户名单元格与关键词一致。每轮的用户计数和列表 SQL 连接都关联实际请求、Host PID 与选定数据库。

维护版成功登录计数按候选库/对照库为 `1/1 → 2/1 → 3/1`。原版回退按升级后库/升级前库为 `3/2 → 4/2 → 4/3`。选择较早的恢复点会舍弃 .NET 10 阶段留下的登录行。其后的原版登录复用 ID 3，但创建时间与 .NET 10 的原行不同。

| 交接证据 | SHA-256 |
| --- | --- |
| 通过的升级报告 `evidence/upgrade/report.json` | `4fcbda0355888a89f3ebe5bc9d815b0c3bd129bbf868f130e852de5ebf09b67c` |
| 通过的原版回退报告 `evidence/rollback/report.json` | `6b62f447df30d1804000df84d2e28bc39f3104c77b73021800b43b830d887d69` |
| 引擎专项 `evidence/engine/report.json` | `4ecacc317d22ddc15dbae85cc29bfecf976b3286971f50626416575e8fadfcdd` |
| 组件、模板进程和恢复点的批次关联 `evidence/consumer-bindings.json` | `97016fa3a77d91c8c58fa24b1aa95bd97894a11f20d31e099b28dbe5a51c75e6` |
| 升级前备份集 `a6121207-7438-4b91-96d1-bc275fea30cf` | `9c0c038ad1f2257354a5635aa912285329e8f51e05d98ee755a109373dfbbbe9` |
| 升级后备份集 `87ebd3a3-fc96-422a-b1fe-a66d2eb955da` | `119363b1676a08b75fc8b37fd103474d558019786edd9c1ffe9f64bc4751e783` |

映射引擎专项覆盖 GHSA-rvv3-g6hj-g44x、GHSA-6vhm-j9h7-f9gh 和 GHSA-gpwp-5797-mjff。每项报告均关联主包 SHA-256 `dd56c74c6088815b4bc5b7b09696c464849f8da43c5ba594e36ff010e6244e80`，包内、输出目录和实际加载的引擎 DLL SHA-256 均为 `12fcba523f7f7199215764b29c5d330aa363c433fa14d4e72257ce835a87e5e1`。对于 CLR 低栈分支，同一 DLL 的 `Mapper.MapCore` 包含 `EnsureSufficientExecutionStack` 调用。示例映射中的带标记异常由测试转换器受控注入，调用方收到同一异常实例，再用同一个 Mapper 得到 55。[Microsoft .NET 9 API 契约](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices.runtimehelpers.ensuresufficientexecutionstack?view=net-9.0)

已验证缺包、旧候选额外混入、旧字节冒用稳定文件名和还原图混入原版包会被拒绝。冻结升级报告被换成历史报告、升级登记使用其他批次摘要、升级前后备份互换也会被拒绝。原 R3 验证入口仍接受其固定摘要登记的原输入。

## 重放消费者

从主仓根目录执行。将 `BATCH_ROOT` 指向 `publish-handoff-v2/frozen` 或本机冻结目录。将 `R3_FROZEN_ROOT` 指向保留 R3 原版报告、候选对照还原图、原版 Release 输出、Angular production 输出及登录前备份相对路径的原件目录。本机为 `.git`。用 `R4_EVIDENCE_ROOT` 保存隔离构建和运行结果，两个空 NuGet 缓存共需约 1.6 GiB。配置专用测试实例和环回端口。将 R3 登录前备份的副本放入配置内的备份映射目录，并使其可生成本轮备份。运行配置字段及三个凭据环境变量见[固定模板复跑手册](r3-template-runtime-baseline.md#复跑)与[升级复跑](r3-template-net10-upgrade.md#完整运行复验)。

```sh
python3 -B eng/r4_candidate_batch.py verify --batch-root "$BATCH_ROOT"

python3 -B eng/r4_engine_consumer.py --batch-root "$BATCH_ROOT" \
  --output "$R4_EVIDENCE_ROOT/engine" --ilspy "$ILSPY"

# 使用安装了 Playwright 与 pymssql 的 Python。
python -B eng/r4_template_consumer.py upgrade --batch-root "$BATCH_ROOT" \
  --frozen-root "$R3_FROZEN_ROOT" --evidence-root "$R4_EVIDENCE_ROOT" \
  --runtime-config "$R4_RUNTIME_CONFIG"

# 由本轮成功升级的 report 路径确定 UPGRADE_RUN，核对同目录的登记摘要。
R4_LOCK_SHA="$(shasum -a 256 "$UPGRADE_RUN/rollback-inputs.json" | cut -d ' ' -f 1)"
python -B eng/r4_template_consumer.py rollback --batch-root "$BATCH_ROOT" \
  --frozen-root "$R3_FROZEN_ROOT" --evidence-root "$R4_EVIDENCE_ROOT" \
  --runtime-config "$R4_RUNTIME_CONFIG" --upgrade-run "$UPGRADE_RUN" \
  --rollback-inputs-sha256 "$R4_LOCK_SHA"
```

仅复验包图及编译、输出资产时，用 `eng/r4_template_consumer.py build` 指定 `--tfm net9.0` 或 `--tfm net10.0`，保留其余构建参数并省去 `--runtime-config`。完整升级会自行重建两个 TFM。构建通过时在各自目录生成 `r4-build-assets.json`。维护版每次迁移和 Host 运行还读取该入口的构建对账，将实际进程、DLL 来源和摘要逐包纳入升级报告的 `r4ProcessAssets`。应加载的框架或引擎 DLL 缺失时该轮失败。仅允许已知按需加载的映射依赖在对应入口缺少加载记录。回退从本轮升级通过轮的 `rollback-inputs.json` 读取本轮报告与两份介质校验值，在各起点恢复到新库。复跑使用新的证据目录和备份文件名。定向诊断使用 `eng/tests/verify_r4_template_consumer.py`，另行传入历史 R3 升级报告目录，并在专用实例仍在线时执行。

## 从原始通过轮只读复核

原始通过报告在活跃 R4 变更下生成，继承的规划字段标成了历史 R3。新版入口记录 `prepare-r4-first-release-candidate`、实际读取的 OpenSpec 制品路径和摘要、规划基点 `bd5f29f8a02ffcc8868deb2c8e60f49306d6668a`、冻结批次协调提交以及实际执行树。正式消费通过轮的协调与执行提交同为 `19101266923a6422543a17e0963e3475c24923f2`。新版交接的 `evidence/recheck/planning-provenance.json` 保留三个原始报告的 SHA-256 和原规划字段，再关联本轮 R4 制品。旧报告原样保留。

`evidence/recheck/template-entry-assets.json` 用已登记的原交接校验清单确认原报告、构建清单和实际加载记录，并从保留的缓存、冻结包及 Release 产物重新核对四个入口的归档、编译、输出和进程加载。SQL 和浏览器沿用这些已校验的原始通过轮。给定原始交接目录、正式升级和回退目录及一个新的输出路径，从主仓执行：

```sh
python3 -B eng/r4_template_recheck.py --batch-root "$BATCH_ROOT" \
  --prior-handoff "$PRIOR_HANDOFF" \
  --prior-checksums-sha256 99331e8beb6b4387294f8f2614cd6da9cc0c19f60ea37655cfb4d054e18a6792 \
  --upgrade-run "$UPGRADE_RUN" --rollback-run "$ROLLBACK_RUN" --output "$RECHECK_OUT"

python3 -B eng/tests/verify_r4_template_assets.py --batch-root "$BATCH_ROOT" \
  --upgrade-run "$UPGRADE_RUN" --entry-assets "$RECHECK_OUT/template-entry-assets.json" \
  --output "$RECHECK_OUT/diagnostics.json"
```

其中 `PRIOR_HANDOFF` 为原版 `publish-handoff/`。本轮正式升级与回退原始目录分别是 `runs/r4-template-upgrade-_1drcs_1/` 与 `runs/r4-template-original-rollback-f1akkml_/`。专项诊断从原观测派生独立输入，确认错 DLL 路径或摘要、编译来源或摘要不符、必需加载缺失、错误执行树均被拒绝。

R4 归档后，复核入口从归档目录读取规划制品，新的规划来源报告将 `changeState` 记录为 `archived`。随 v2 保存的报告仍记录当时实际读取的活跃变更。验证机的归档后复核记录见 `.git/r4-first-release-candidate/closeout/`。[R4 归档](../../openspec/changes/archive/2026-11-26-prepare-r4-first-release-candidate/)

## 发布者交接

冻结交接时的状态为本地待发。验证机的 `.git/r4-first-release-candidate/package-4/work-root.txt` 记录保留目录。其子目录 `publish-handoff-v2/` 为当前可整体搬移的交接。原版 `publish-handoff/` 随原报告保留。v2 目录的 `packages.tsv` 列出 26 份实物及生产提交，`SHA256SUMS` 覆盖交接文件，`evidence/recheck/` 保存规划来源和四入口只读复核，`RELEASE-NOTES.md` 为发布说明草案，实际的主包、符号包、发布候选证据和恢复介质分别可从 `frozen/feed/`、`frozen/symbols/`、`evidence/` 和 `sql-media/` 取得。验收日志中的绝对路径定位验证机的原始记录，复跑使用本机路径。

原始生产与冻结复验材料分别保存在同一保留目录的 `producer-evidence/` 和 `freeze-evidence/`。验证机上的旧临时路径通过符号链接供按绝对路径登记的历史记录读回。迁存记录及历史组件绑定复跑命令见 `.git/r4-first-release-candidate/closeout/README.md`。

- 发布前核对目标公共源、13 个包名和版本、账号权限和元数据。随后按授权发布对应提交的 tag 与说明。
- 按内部依赖顺序使用交接归档上传主包与符号。发生签名或重新生产导致归档字节变化时，绑定变化后的摘要并完成受影响的来源、符号和消费者复验。
- 从公开源独立空缓存回装已发布版本，复核实际下载的版本、摘要、符号、依赖闭包和正常消费者入口，记录公开源结果、发布标识与提交。

本批应用实测覆盖上述 macOS ARM64 组合。Windows、Linux，本轮 CI，MySQL/PostgreSQL 等其他 Provider，其他数据库或运行时补丁、生产或分布式部署以及新 Angular 版本仍待验。早期版本的跨平台源码验证作为历史证据。同批公开源回装见[公开源模板消费](#公开源模板消费)。

### 首次公开发行清单预检

从主仓根目录运行下列命令。验证机可从 `work-root.txt` 定位交接目录。在其他机器使用完整移交的 `publish-handoff-v2/`，并确保主仓本地包含发行目标提交 `5758c8186b68dcc42ecc90164cf9d3f53cf3345e` 和实测协调提交 `19101266923a6422543a17e0963e3475c24923f2`。

```sh
R4_HANDOFF="$(cat .git/r4-first-release-candidate/package-4/work-root.txt)/publish-handoff-v2"
R4_RELEASE_EVIDENCE="$(git rev-parse --git-path publish-r4-first-public-release/package-1)"
mkdir -p "$R4_RELEASE_EVIDENCE"

python3 -B eng/r4_release_manifest.py --handoff "$R4_HANDOFF" \
  --output "$R4_RELEASE_EVIDENCE/release-manifest.json"
```

预检用固定摘要复核 `SHA256SUMS` 的 209 个条目，复用冻结批次的 `verify` 校验，并逐行把 `packages.tsv` 与 26 份归档的路径、大小、SHA-256、版本、目标框架和生产提交对账。清单标明拟用 tag、目标提交、三个生产 gitlink 和实测协调提交。归档路径相对于交接目录。每个主包记录实际 nuspec 各目标组的内部依赖范围。`directInternalDependencies` 将这些目标组的直接内部依赖合并为本批确切版本，`publishOrder` 将每个依赖排在使用者之前。

将输出放在交接目录外。使用同一输出路径复跑时，预检重新核对全部输入，并要求现有清单字节与本轮结果一致。输入差异会使预检退出 1，并报告出错字段或归档路径。后续发布步骤以本轮预检退出 0 为使用该清单的前提。发布权限、远端状态和公开源核验见[首发设计归档](../../openspec/changes/archive/2026-11-26-publish-r4-first-public-release/design.md)及[公开发行稳定规范](../../openspec/specs/public-package-release/spec.md)。

定向复跑会在独立临时副本中逐一替换 26 份归档，逐项验证退出码、摘要诊断和清单生成条件。

```sh
python3 -B eng/tests/verify_r4_release_manifest.py --handoff "$R4_HANDOFF" -v
```

### 公开主包、符号与进度核验

在同一终端使用上一节的 `R4_HANDOFF` 和 `R4_RELEASE_EVIDENCE`。入口读取固定首发清单，使用 Python 3 与 `.NET SDK 10.0.404`，并将所有核验产物写入交接目录外的 `R4_PUBLIC_WORK`。

```sh
R4_PUBLIC_WORK="$(git rev-parse --git-path publish-r4-first-public-release/package-4/public)"
r4_public() {
  python3 -B eng/r4_public_release.py \
    --manifest "$R4_RELEASE_EVIDENCE/release-manifest.json" \
    --handoff "$R4_HANDOFF" --work "$R4_PUBLIC_WORK" "$@"
}

r4_public verify --main-only
r4_public gate --package Du.AutoMapper.Collection
r4_public verify --package Du.AutoMapper
```

- `verify` 默认回读全批主包及符号。用重复的 `--package` 指定一组包。它向 NuGet Gallery 匿名下载精确版本，并用服务索引登记的指纹和固定 SDK 验证仓库主签名、签名证书链、时间戳和时间戳证书链。验签进程使用 .NET 固定区域性和 UTC，并保存完整日志。主包另保存冻结及下载归档 SHA-256 和逐文件校验表。将仓库签名的所有者、当前公开搜索返回的所有者及已核对的发布记录三方对账。
- 所有者查询依次使用服务索引列出的搜索节点。若服务索引转到地区镜像且其节点均未返回该包的所有者，继续查询 nuget.org 全球索引公布的主节点。逐项保存查询结果，本批签名、当前公开所有者和发布记录的核对要求相同。
- `verify` 从已经核验的公开 DLL 读取 CodeView 标识和签入的调试校验和。它向符号服务请求 Portable PDB，核对 PDB 标识、调试校验和及冻结符号的整文件 SHA-256。PDB 核验按包、TFM 和 DLL 保存。符号归档的上传受理在 `progress.json` 的 `external` 中单独登记。全项通过需要每包最新的 `accepted` 或有凭证的 `confirmed` 记录与冻结符号归档摘要一致，且全部登记目标的 PDB 均通过。遇到上传退回或重复版本时，通过的 PDB 证据保留，全项核验随最新上传记录重新判定。重新检查仍待索引的项目时使用同一工作目录，按服务的 `Retry-After` 或索引状态间隔重跑。
- `gate` 回读目标版本及其直接内部依赖的主包。退出 0 表明目标尚不可见且当前依赖均有已核验的公开下载记录。退出 2 时查看 JSON 的 `blockedBy` 和 `main`。目标已核验时可按已完成的主包接续到符号步骤。上传前仍须完成首次外部写入的授权、命名与权限预检。
- `verify` 退出 0 表示所选检查全部通过，退出 1 表示核验失败、冲突或输入错误，退出 2 表示仍有待索引、超时或不可见的项目。主包通过后，`verified-downloads.json` 按清单原样的 ID 导出 `version`、`uploadSha256` 和 `downloadSha256`，文件头包含 `schemaVersion`、`nugetSource` 和 `manifestSha256`。公开消费者须用本批清单及其所需的全体包版本与下载摘要核对缓存。

外部操作完成或结果不确定时，用 `record` 登记脱敏凭证引用。为主包使用 `--kind main --package ID`，为符号使用 `--kind symbols --package ID`，为 tag 或发行说明分别使用 `--kind tag` 和 `--kind release`。实际受理时登记 `--outcome accepted`，超时和重复版本分别登记 `timeout` 与 `duplicate`，并先回读。主包 `accepted` 和 `confirmed` 记录均需为每位已核对的所有者提供一个 `--owner`。符号归档的这两种记录均需用 `--upload-sha256` 提交实际上传件的 SHA-256。处理重复版本前，取得能证明同一发布批次及实际归属的凭证，再以 `confirmed` 和相应的 `--evidence` 续作。外部操作失败时用 `failed`。如已查明前次操作未受理且可以重新尝试，用 `retry` 记录调查证据，再执行 `gate`。

`progress.json` 保留各次外部观察和验证结果。每次重跑复用有完整留存证据的通过记录。用新核验目录做独立回读时，按原发布者凭证登记相关外部观察。符号仍待索引时，通过核验的主包已能为直接依赖放行。具体证据文件在各条记录的 `evidence` 路径下。[NuGet 仓库签名](https://learn.microsoft.com/en-us/nuget/api/repository-signatures-resource) · [符号发布与索引](https://learn.microsoft.com/en-us/nuget/create-packages/symbol-packages-snupkg#symbol-package-validation-and-indexing)

复跑隔离反例和全部 18 个冻结调试目标。另传入新的 `--online-evidence` 目录可对真实公开的 `Serilog 4.2.0` 测试仓库签名与符号回读。该样本从公开包和符号构造独立对照输入，主包及 PDB 核验通过，样本的符号归档上传记录缺失，全项核验会退出 2。样本证据目录与 R4 正式记录独立。

```sh
python3 -B eng/tests/verify_r4_public_release.py --handoff "$R4_HANDOFF" \
  --manifest "$R4_RELEASE_EVIDENCE/release-manifest.json" -v
```

### 公开源模板消费

在上文固定目标的 13 个主包均有已验签下载记录后，向模板入口同时传入首发清单和本次 `verified-downloads.json`。继续使用[重放消费者](#重放消费者)的受控 SQL Server 实例、历史业务输入和配置。仅需核对构建资产时用 `build --tfm net9.0` 或 `build --tfm net10.0`，省去运行配置。以下 `upgrade` 命令从两个独立空 NuGet 缓存构建两代入口并运行同库接续和业务。

```sh
python3 -B eng/r4_template_consumer.py upgrade \
  --batch-root "$R4_HANDOFF/frozen" --frozen-root "$R3_FROZEN_ROOT" \
  --evidence-root "$R4_EVIDENCE_ROOT" --runtime-config "$R4_RUNTIME_CONFIG" \
  --release-manifest "$R4_RELEASE_EVIDENCE/release-manifest.json" \
  --verified-downloads "$R4_PUBLIC_WORK/verified-downloads.json"
```

公开报告使用带 `-public` 的目录和 profile，保留本轮两份输入的副本及摘要。`inputs.planning` 记录 `publish-r4-first-public-release` 实际读取的工作树制品路径和摘要，并登记执行提交和 Git 树。本变更归档后的复跑读取[首发归档](../../openspec/changes/archive/2026-11-26-publish-r4-first-public-release/)，将 `changeState` 记录为 `archived`。`inputs.frozenCandidatePlanning` 标明冻结批次的候选验收来源。

每代显式配置 nuget.org，同时隔离全局包、HTTP、插件与临时缓存，清除环境继承的还原源与回退目录。固定模板和项目引用继续通过原有断言。每个维护 ID/版本的缓存主包核对实际来源和已验签公开下载的 SHA-256。编译与输出 DLL 对照冻结包内选中目标的 SHA-256。全部入口的实际加载在各阶段 `*-r4-assets.json` 登记。按需依赖同时记录输出和加载状态。两代报告共用同一快照的下载登记。缺少登记、来源偏离、任一摘要不符或业务断言失败，入口退出 1。

2026-11-26 的公开源复验在 macOS ARM64、SDK `10.0.404`、SQL Server Developer `16.0.4236.2` 和 Chrome `158.0.8127.37` 通过。两代 Host 和 Migrator 分别还原 13 和 10 个维护包，缓存主包与已验签下载件的摘要相同。两代 Host 各实际加载 12 个维护 DLL，Migrator 各加载 7 个，全部通过冻结 DLL 对账。`net9.0` 和 `net10.0` 各使用实测运行时 `9.0.10` 和 `10.0.15`，在同一候选库保留 30 条迁移记录。两轮 `Default` 租户均获 `Pages.Users` 权限，授权查询返回 HTTP 200，唯一用户 ID 为 3。候选库和对照库的成功登录计数依次为 `1/1 → 2/1 → 3/1`。

独立的新安装复验从公开固定模板和空缓存创建空库，`net10.0` Migrator 退出 0，SQL 读回 30 条迁移，Web.Host 的 Swagger JSON 返回 HTTP 200。复跑命令见[公开安装说明](r4-public-install.md)。冻结源模式和原版回退继续使用原命令，回退证据来自本地冻结源的候选验收。

可用已登记的本地通过轮复跑公开消费的隔离反例。测试内的签名封装样本仅验证消费侧的归档及 DLL 对账。公开验签独立执行。

```sh
python3 -B eng/tests/verify_r4_public_consumer.py \
  --batch-root "$R4_HANDOFF/frozen" --upgrade-run "$UPGRADE_RUN" \
  --manifest "$R4_RELEASE_EVIDENCE/release-manifest.json" -v
```
