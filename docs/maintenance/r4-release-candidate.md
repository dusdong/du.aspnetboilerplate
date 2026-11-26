# R4 首发候选与本地验收

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

本轮状态为本地待发。验证机的 `.git/r4-first-release-candidate/package-4/work-root.txt` 记录保留目录。其子目录 `publish-handoff-v2/` 为当前可整体搬移的交接。原版 `publish-handoff/` 随原报告保留。v2 目录的 `packages.tsv` 列出 26 份实物及生产提交，`SHA256SUMS` 覆盖交接文件，`evidence/recheck/` 保存规划来源和四入口只读复核，`RELEASE-NOTES.md` 为发布说明草案，实际的主包、符号包、发布候选证据和恢复介质分别可从 `frozen/feed/`、`frozen/symbols/`、`evidence/` 和 `sql-media/` 取得。验收日志中的绝对路径定位验证机的原始记录，复跑使用本机路径。

原始生产与冻结复验材料分别保存在同一保留目录的 `producer-evidence/` 和 `freeze-evidence/`。验证机上的旧临时路径通过符号链接供按绝对路径登记的历史记录读回。迁存记录及历史组件绑定复跑命令见 `.git/r4-first-release-candidate/closeout/README.md`。

- 发布前核对目标公共源、13 个包名和版本、账号权限和元数据。随后按授权发布对应提交的 tag 与说明。
- 按内部依赖顺序使用交接归档上传主包与符号。发生签名或重新生产导致归档字节变化时，绑定变化后的摘要并完成受影响的来源、符号和消费者复验。
- 从公开源独立空缓存回装已发布版本，复核实际下载的版本、摘要、符号、依赖闭包和正常消费者入口，记录公开源结果、发布标识与提交。

本批应用实测覆盖上述 macOS ARM64 组合。Windows、Linux，本轮 CI，MySQL/PostgreSQL 等其他 Provider，其他数据库或运行时补丁、生产或分布式部署以及新 Angular 版本仍待验。早期版本的跨平台源码验证作为历史证据。公开发行及公开源回装待后续发行变更。
