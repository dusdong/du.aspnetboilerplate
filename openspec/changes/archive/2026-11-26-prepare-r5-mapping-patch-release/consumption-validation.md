# 待发组合的独立消费与固定模板验收

## 本轮输入

本机验收使用 `.git/prepare-r5-mapping-patch-release/batch/frozen/`，独立登记的 `batch.json` SHA-256 为 `b914f5669c504a3a85cd7120fb63ff0d14667924d6dd0ff1f92fea9a1a76eaf1`。从空缓存还原时，三个替换包按精确 ID 映射到本地源，模板使用的其余十个 R4 维护包及第三方包由 nuget.org 提供。每个维护包的实际下载归档与冻结批次对账。新引擎主包摘要为 `32bbe536dcb588e45257e9d3be5f5f62d7bbeeb642cc15cce857066b2b8d8993`，包内 `lib/net8.0/AutoMapper.dll` 摘要为 `1d752c32c70cff281afc3bee951abdf763b0910ba74be6a4772854149fe75bd0`。[待发归档及来源](source-and-engine-validation.md#三包待发批次)

原 R5 批次 `8d0d4dc762a3582327d8829e5952fadbd55b7448d7c2de85c32e6a76d6a3cf40` 的两个组件主包、符号包和十个公开维护包与本轮留存版本均逐份同摘要。原引擎 DLL、原独立消费者和原模板运行报告仍归于该批次。新旧引擎之间的源码差异仅是包内安装说明。现有证据逐字节比对了两份 DLL 的 IL；本轮仍以新 DLL 重跑独立消费及受影响的模板业务。[引擎实物对账](source-and-engine-validation.md) · [原 R5 批次](../2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md) · [原 R5 模板运行](../../../../docs/maintenance/r5-automapper-template.md)

## 独立消费与引擎

在 macOS ARM64、SDK `10.0.404` 和隔离 .NET 运行时中，最小应用只直接引用 `Du.Abp.AutoMapper [10.5.2]`。真实 nuspec 和还原图确认适配器至引擎 `[14.0.1]`、Collection `[11.0.1]` 和内核 `[10.5.1]`，以及 Collection 至引擎 `[14.0.1]` 的四条边。候选业务应用另引用 `Du.Abp.ZeroCore [10.5.1]` 和 SQLite Provider `[9.0.18]`。两路都从空缓存还原并在 .NET `9.0.23` 启动经典 ABP。三份映射 DLL 的 NuGet 归档、Csc 引用、Release 输出和实际加载逐项匹配，全部加载上下文仅有一份引擎，位于 `Default`。

- Castle 返回 `Abp.AutoMapper.AutoMapperObjectMapper`，兼容静态入口映射出键 10 和 `updated`。按键集合保留原集合与键 10 对象，更新键 10、删除键 20、插入一条键 30。
- 原版与待发组合分别更新同一个模板用户实例，保留角色集合、原成员和创建时间。两路均对 SQLite `3.46.1` 实际执行筛选和排序，物化 ID 依次为 12、13、11。两路取列、租户参数 6、排序及 `FullName` 业务结果一致。
- 另以同摘要引擎在 .NET `10.0.15` 独立跑实际共享一个集合执行计划的发货和退货映射，交换冷态注册顺序与暖态预热顺序。每种顺序三份独立配置，待发件四组均为 6/6，12 次预热均通过。公开 R4 为冷态两组 3/6 和暖态 3/6、6/6。普通业务断言与独立计划读取分别保留。同样从空缓存运行既有普通订单映射，24 次正式调用、12 次预热均通过。

三项引擎防护使用相同归档、相同 DLL 的隔离子进程，在 ARM64 .NET `9.0.23` 上逐项核对有界行为。旧历史对照只复用了已核对身份的公开 R4 普通映射观测；下表的实际值来自本轮新件。[防护源码和许可沿革](../../../../docs/maintenance/r3-automapper-engine.md#公告处置与行为证据) · [原 R5 防护观测](../2026-11-26-fix-r5-automapper-collection-context/engine-package-validation.md#消费与公告复验)

| 既有登记 | 本轮观测 |
| --- | --- |
| GHSA-rvv3-g6hj-g44x | 两种引用保持配置下均按默认边界返回 64 层，保留自引用身份与已有目标更新。 |
| GHSA-6vhm-j9h7-f9gh | 两种显式构造深度均为 2，默认位置构造为 64。常规构造异常后同上下文返回 21，同一 Mapper 后续返回 34。 |
| GHSA-gpwp-5797-mjff | 派生映射继承显式深度 2 与默认深度 64，接口、`object`、字典、动态对象及转换器均返回预期值。常规转换异常后同一 Mapper 返回 55。 |

新 DLL 的 `Mapper.MapCore` IL 含 `RuntimeHelpers.EnsureSufficientExecutionStack` 调用。2026-11-26 查阅 Microsoft Learn 的 .NET 9 API 参考，确认运行时判断可用栈空间不足时抛出 `InsufficientExecutionStackException`。隔离进程以例行应用异常测试一次传播，断言包装链持有同一个注入对象，同一 Mapper 随后返回 55。异常来源登记为 `test-injection`，实际 CLR 低栈触发未观测。[.NET 9 API 契约](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices.runtimehelpers.ensuresufficientexecutionstack?view=net-9.0)

| 报告路径 | SHA-256 |
| --- | --- |
| `independent/report.json` | `f37783994b86dde93b72788572dc9dc68c429b17d042f3a1e060fd2ca26dc09e` |
| `engine/report.json` | `a43b1a3d1a4321e93be1bb6997ba1b041d71ec20651ba8576aba0dfc4cd3ba69` |
| `shared/report.json` | `80730659ca525311fbeeb741131ebd1e8c9488676f3ebde8b08d5aced3ceb726` |

## 固定模板与同库业务

固定模板提交为 `2e9536872673a7ff1986a19e798c51684d16afe5`。本轮在 macOS ARM64 `27.2.1`（`26B131`）上用 SDK `10.0.404` 运行原生 Release 应用。两代 .NET 与 ASP.NET Core 共享框架分别为 `9.0.10` 和 `10.0.15`。使用专用隔离 SQL Server Developer `16.0.4236.2` 与 Chrome `158.0.8127.37`。Angular production 原件的清单 SHA-256 为 `99a2520978f5917fdc98545dc043b90ff5f9f2ed83872b52dbb8e273fa71c12b`，共 1,193 个文件。三轮各自的服务副本仅调整前后端环回地址。

待发组合两代 Web.Host 均核对 13 个维护包，实际加载 11 个 ABP DLL 和唯一引擎。两代 Migrator 均核对 10 个维护包，实际加载七个 ABP DLL，两个入口的 Collection、Migrator 的适配器与引擎保留为输出资产。四入口逐包核对实际 nuspec、还原来源及归档、编译引用和 Release 输出。运行观测记录 PID、目标路径、TFM、共享框架和实际加载文件的 SHA-256。

### 新库安装

`install` 退出 0，16 阶段通过。原生 `net10.0` Migrator PID `74044` 向新库 `r3_template_33f56fce095665b8_source` 执行 33 条实际迁移命令，读回 30 条迁移历史，数据库 GUID 为 `9191C595-2519-4B9B-B2F6-92390E019841`。Host PID `74242` 经认证在租户 1 由用户 2 创建业务用户 `r5user33f56fce095665b8`（ID 3）。冻结 Angular 经 Host PID `74410` 登录 `Default/admin`，取得 `Pages.Users` 权限，HTTP 200 返回且实际页面显示唯一用户。成功登录记录从 0 增至 1 再增至 2。最终通过带校验和的 `RESTORE VERIFYONLY`，备份 SHA-256 为 `d08a631e820387ac065322bf46c699467bbf4d8a6a2b9d07ab1b02796a124a2b`。

### 两代同库接续与恢复点

`upgrade` 复跑退出 0，26 阶段通过。输入是 R3 已验的登录前备份副本，SHA-256 为 `93da0a5ceb9fd98821aa654fedcd13cc91c53ca25cb41f845115a7f05f81d988`。由该备份在本轮恢复待接续库 `r3_template_9cd336806c15b8cc_candidate`（GUID `5EB2AD72-1A06-4A9D-A394-5BC6C7618C4C`）和独立对照库 `r3_template_9cd336806c15b8cc_control`。两代各执行三条绑定候选库的迁移命令，保留 30 条迁移记录和已检查的 SQL Server 目录。两代经 `Default/admin` 登录和 `Pages.Users` 授权，各自的查询和页面均显示唯一用户 `r3usercf4314cdfe038c35`（ID 3）。

| 阶段 | Migrator／Host PID | 候选库／对照库成功登录行数 |
| --- | --- | --- |
| `net9.0` | `79783`／`79815` | 1／1 → 2／1 |
| `net10.0` | `79953`／`79987` | 2／1 → 3／1 |

接续前后分别备份并实际恢复至独立 SQL 库，确认迁移记录、租户授权查询用户及登录行，与对应备份前一致。恢复点分别读回成功登录行 ID 1、2 和 1、2、3。备份 SHA-256 分别为 `203f40b8337c11ffb2120033dbfa2cc6476e38ae7b2e4be4a8dc5cac26f44b16` 和 `a617bc2ffb67bb12e65b31f3103016aae8fa9a3f29e7dbfe23ee5220050a7fd9`。

初轮 `upgrade` 已完成两代构建，在 SQL 预检发现新实例挂载目录缺少上述备份，退出 1。按已验历史报告核对备份摘要并复制到本轮专属目录后，使用新证据目录、空缓存和隔离恢复库从头通过。首轮与复跑分别保留为 `upgrade.log` 和 `upgrade-2.log`。

### 固定运行时的公开 R4 同库切换

`switch` 退出 0，20 阶段通过。三阶段使用同一个 `net10.0` 运行时及 SQL 库 `r3_template_afb647a83831f4a9_source`。数据库 ID 10、GUID `832FBFFB-9F7A-4DFE-B961-98A9DFBF8CF9` 和物理文件路径持续匹配。每个阶段从独立空缓存还原 94 个 Host 包和 66 个 Migrator 包，其中分别有 13 个和 10 个维护包。首尾两阶段由纯 nuget.org 还原完整 R4，两阶段的维护包版本、签后归档和 DLL 摘要逐项一致。中间混合源阶段实际更换三份映射包，十份沿用包保持一致。

| 阶段 | Migrator／查询 Host PID | 实际迁移命令 | 当轮结束时成功登录行 ID |
| --- | --- | --- | --- |
| 完整公开 R4 | `83646`／`83849` | 33 | 1、2 |
| 本轮三包与十个公开包 | `84081`／`84154` | 3 | 1、2、3 |
| 回退完整公开 R4 | `84286`／`84319` | 3 | 1、2、3、4 |

首阶段写入 Host PID `83724` 经应用认证创建 `r5userafb647a83831f4a9`，业务用户 ID 3、租户 ID 1、创建者 ID 2。每轮重新登录 `Default/admin`，均取得 `Pages.Users`，HTTP 200 返回并在冻结 Angular 中实际显示唯一用户。对应 SQL 确认三阶段的用户身份、姓名、邮件、启用标志、创建者和创建时间相同，并将每次查询绑定到各阶段 Host PID 和同一数据库。回退后保留前序登录行，最终备份通过带校验和的 `RESTORE VERIFYONLY`，SHA-256 为 `35133ce33b8e35750bc9a1a35701637cbb0c4d76f4bdb09e2723b0e8b4245feb`。

| 报告路径 | SHA-256 |
| --- | --- |
| `runs/r5-template-install-nda4rtkr/report.json` | `b57ff470f28624014a269d31c3f003f6259d474a25c4deb94b07042e2a2aa6a2` |
| `runs/r5-template-upgrade-r6bsue2c/report.json` | `8217fb7fb5b6fc466ef554e09376d3d8a89d0066113452eab8d457b49845f29a` |
| `runs/r5-template-switch-myhrwzsn/report.json` | `032b477854299d5a6a19823dc0f0fa3f5ea8fb0d8b9d2992a3f1940fcbe7be3c` |
| `evidence-index.json` | `ba59a0cda3b197d1fb7d4d5445bb71884a8643c093fc56bb48a939900f3e2507` |

三轮均核对本轮 Host、Migrator 和网页服务的清理。专用 SQL Server 已停止并删除，进程、SQL 和 HTTP 环回端口检查通过。本轮凭据文件已移除，保留四份新备份、已验输入副本和无凭据运行配置。介质与报告摘要可由索引逐项核对。

## 复跑与证据定位

本机证据根为 `.git/prepare-r5-mapping-patch-release/consumption/`。独立消费各路保留 `package-graph.json`、`compile-references.json`、`assemblies-verified.json` 及实际命令。引擎两路保留原始业务结果、还原图、归档身份、进程结果和 IL。模板各轮保留 `assets-inventory.json`、`raw-assets/`、`r4-build-assets.json`、每个实际进程的加载清单与 SQL／浏览器证据。`evidence-index.json` 将正式通过的测试、各入口摘要、SQL 恢复点和保留介质串联，便于后续公开源演练定位。

在主仓根目录设置以下变量。独立消费者及引擎使用含 SDK `10.0.404`、.NET 与 ASP.NET Core `9.0.23` 及 .NET `10.0.15` 的隔离 `DOTNET`。两个引擎动作使用本轮独立登记 `acceptance-input.json` 及其同目录内的主包校验副本，并复用已核对的公开 R4 对照。模板动作使用配有 Python、Chrome、两代对应 .NET 共享框架的本机环境和新的证据目录。专用实例配置与凭据变量按已有运行指南准备，升级动作要预先把上述摘要对应的登录前备份副本放入实例的只服务本轮的挂载目录。[模板动作复跑及专用配置](../../../../docs/maintenance/r5-automapper-template.md#复跑) · [引擎独立验收命令](../2026-11-26-fix-r5-automapper-collection-context/engine-package-validation.md#复跑与原始证据)

```sh
base=.git/prepare-r5-mapping-patch-release
batch="$base/batch/frozen"
batch_sha=b914f5669c504a3a85cd7120fb63ff0d14667924d6dd0ff1f92fea9a1a76eaf1

python3 -B eng/r5_automapper_consumer.py --batch-root "$batch" \
  --batch-sha256 "$batch_sha" --dotnet "$DOTNET" --output "$NEW_CONSUMER_OUTPUT"

sh "$base/consumption/engine.sh" engine-replay
sh "$base/consumption/engine.sh" shared-replay

python -B eng/r5_template_consumer.py install \
  --batch-root "$batch" --batch-sha256 "$batch_sha" --frozen-root .git \
  --runtime-config "$R5_RUNTIME_CONFIG" --evidence-root "$NEW_RUNTIME_EVIDENCE"
python -B eng/r5_template_consumer.py upgrade \
  --batch-root "$batch" --batch-sha256 "$batch_sha" --frozen-root .git \
  --runtime-config "$R5_RUNTIME_CONFIG" --evidence-root "$NEW_RUNTIME_EVIDENCE"
python -B eng/r5_template_consumer.py switch \
  --batch-root "$batch" --batch-sha256 "$batch_sha" --frozen-root .git \
  --runtime-config "$R5_RUNTIME_CONFIG" --evidence-root "$NEW_RUNTIME_EVIDENCE" \
  --r4-batch-root "$R4_BATCH_ROOT" --release-manifest "$R4_RELEASE_MANIFEST" \
  --verified-downloads "$batch/public/verified-downloads.json"
```

`engine.sh` 是本机留存的复跑入口，依赖固定位置的隔离宿主与 ILSpy。它固定消费登记文件的 SHA-256 `70172d4104551e2e8245e8c8a286f6e07a9d171f071f12be71da85e4f50e802c`，两个动作都要求新输出目录。模板三轮的实际完整命令和退出码见同名日志。用 `python3 -B -m unittest discover -s eng/tests -p 'test_*.py'` 复跑 Python 回归，本轮 45/45 通过。用证据根的 `regression.sh` 复跑 R4 的公开消费及冻结资产校验，本轮分别为 12/12 和 9/9。

实测范围为上述 macOS ARM64、固定模板、SQL Server Developer、两代指定共享运行时和冻结 Angular。包切换复验完整公开 R4 写入的用户和后续登录行，候选阶段新增业务实体后的兼容性仍待验证。升级前后介质已实际恢复并用 SQL 复核，固定原版应用在这两个新恢复点的启动不在本轮范围内。其他平台、Provider、客户端产物、公开后纯 nuget.org 消费和生产部署需各自验证。[正式公开后的验收条件](design.md#migration-plan)
