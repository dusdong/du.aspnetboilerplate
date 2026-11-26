# R5 三包冻结与独立消费

2026-11-26 在 macOS ARM64 制备三对 Release 归档。引擎沿用 1.3 的实物，独立复核主包、符号包、DLL 和 PDB。冻结沿用第二包的业务对照，公开旧引擎仅交换预热顺序时正式调用分别为 3/6 和 6/6，候选为 6/6 和 6/6。NuGet V3 版本索引在制备时未列出三个补丁版本，13 个旧版主包匿名下载的摘要均与 R4 公开校验清单和原验签登记一致。[引擎登记](engine-package-validation.md) · [共享执行计划对照](shared-collection-plan-observation.md) · [R4 公开验签记录](../../../../docs/maintenance/r4-release-candidate.md#公开主包符号与进度核验) · [NuGet V3 版本索引文档](https://learn.microsoft.com/en-us/nuget/api/package-base-address-resource)

## 批次交接

本机原件目录为 `.git/review-r5-runtime-migration-readiness/package/`。模板验收使用 `frozen/` 的六份候选、十份 R4 公开包登记和同一份 `batch.json`。批次 SHA-256 为 `8d0d4dc762a3582327d8829e5952fadbd55b7448d7c2de85c32e6a76d6a3cf40`。模板还原时将三个候选 ID 映射至 `frozen/feed/`，其余十个维护包及第三方依赖由 nuget.org 提供，逐项对账实际还原归档和资产。固定模板提交为 `2e9536872673a7ff1986a19e798c51684d16afe5`。[批次读取入口](../../../../eng/r5_candidate_batch.py)

| 候选版本 | 主包 SHA-256 | 符号包 SHA-256 |
| --- | --- | --- |
| `Du.AutoMapper 14.0.1` | `8c780d4d46c4c15879d7e6596e24279285b32079a28cebe3f7316d7e623781b5` | `d0429c659f2fd0a59ef274e822723aa595efa7b8ef0feb1a1642cc579826de7d` |
| `Du.AutoMapper.Collection 11.0.1` | `b6229b0cfde5d96024541a146483b0b30875b6002acef02d6c1852d35d38a7a1` | `d22d7377514910dd1bcc4aeb70ad453552fd0485bfd50d607cc3c15dee1bf066` |
| `Du.Abp.AutoMapper 10.5.2` | `095ecde6a4db3bb7f48fb777f06c258cbc14a4c1c6b6a6de0affafa05b2cc683` | `4c93ce73e07b345159b8c83a1e6b80b847353082c2eef23be72c5ae67b57592b` |

| 源码仓 | 编译源码基点 | 实际生产源码树 | 主仓交付的 gitlink |
| --- | --- | --- | --- |
| `AutoMapper` | `d264ff75831f12e935df8d4703bb05df99eaa000` | `90d6080e4960a7005d29b29bb08eaac2aeca4b7e` | `d264ff75831f12e935df8d4703bb05df99eaa000` |
| `AutoMapper.Collection` | `306b49d7a59b7335a61d8116e1ab2f623a04740e` | `0131ed22f1de1fbd8f05115e6e7da8cc1a3d59ed` | `d22aaf58469d760502864fbb6f575b6505dd8334` |
| `aspnetboilerplate` | `bed57726b56f6f9de5c2d82e8dbe55e0130bddd0` | `8b93fc58f7a8a4ba3d8f79870af270dba0707bc9` | `7933e71f5646d2447af3502ecbea9a3f1aba8184` |

2026-11-26 交付前从登记的 GitHub 子仓回读了 Collection 的 `maintenance/v11` 和经典框架的 `dev`。两项交付提交各以表中的编译源码基点为父提交，Git 树分别与对应的冻结生产源码树完全一致。冻结清单、包内 Source Link、nuspec 和六份归档保留原制备记录及摘要。模板 gitlink 仍为固定的 `2e9536872673a7ff1986a19e798c51684d16afe5`。

后两仓的生产输入为基点加上批次 `sources/` 下的对应补丁。两份补丁仅改变打包属性、入口和说明，Source Link 与 nuspec 的 Git 提交定位各自实际编译的原有源码。回放时在子仓用临时索引将基点 `git read-tree`，执行 `git apply --cached`，再以 `git write-tree` 核对上表。在对应基点的生产源码应用同一补丁后运行仓内 R5 打包入口。生产记录包括原始命令、还原图、构建日志和 TRX。重新生成的归档按新摘要复验。[Collection 打包入口](../../../../AutoMapper.Collection/README.r4.md) · [适配器打包入口](../../../../aspnetboilerplate/nupkg/README.r4.md)

## 生产验证

- Collection 以冻结引擎为输入，Release 组件测试 27/27 通过，随后用同一 DLL 打包。适配器的组件 fixture 从固定提交导出，将三个项目引用改为对应的精确包引用，从各自配置源空缓存还原。原有映射测试 16/16 通过，实际还原和输出 DLL 与冻结归档一致。SDK 为 `10.0.404`。
- 对三个公开 R4 主包逐一比对程序集完整身份、公开与受保护 API，分别核对 166、11、14 个类型及成员。目标为 `net8.0`、`net8.0`、`net9.0`。逐份核对项目命名空间、包内 MIT 许可和署名、两份 nuspec、PDB 与 DLL 的 CodeView 及调试校验和。PDB 引用的编译源码以各提交的文件对账。详细资料在批次的 `packages.*.targets` 及 `staged-02/logs/`。
- 引擎主包和 DLL 分别与 1.3 独立登记的 `8c780d4d…781b5`、`5ae7cbd5…6d82d` 完全一致。组件产物的 DLL SHA-256 在冻结清单逐目标登记。
- 实际 nuspec 为 `Du.AutoMapper.Collection → Du.AutoMapper [14.0.1]`，以及 `Du.Abp.AutoMapper → Du.AutoMapper [14.0.1]`、`Du.AutoMapper.Collection [11.0.1]`、`Du.Abp [10.5.1]`。R4 固定批次摘要 `4d25f237938d04aeb985c2057a6287ba0f18425b94d73e9c494e313684470757` 继续通过原 `verify`、`recheck` 和 R4 组合清单检查，共检查 18 个目标组。[R4 复验入口](../../../../eng/r4_candidate_batch.py)

## 消费复跑

在主仓执行下列命令。`BATCH_ROOT` 指向交接的 `frozen/`，`BATCH_SHA256` 使用验收另行提供的摘要，`DOTNET` 指向包含 SDK `10.0.404` 和两套 `9.0.23` 共享运行时的宿主，`CONSUMER_OUT` 指向一个新目录。[独立消费命令](../../../../eng/r5_automapper_consumer.py)

```sh
python3 -B eng/r5_automapper_consumer.py --batch-root "$BATCH_ROOT" \
  --batch-sha256 "$BATCH_SHA256" --dotnet "$DOTNET" --output "$CONSUMER_OUT"
```

适配器是最小消费者唯一的直接包引用。固定模板 DTO 和 SQLite 对照复用已有项目，以候选适配器作为唯一直接映射包，并额外引用公开 `Du.Abp.ZeroCore [10.5.1]` 和 SQLite Provider `[9.0.18]`。两路独立还原和启动经典 ABP。原版对照用同一组模板源码、SQLite 种子和查询。清单预检可单独用 `--verify-only` 执行。

## 消费结果

独立最小消费者的四条依赖均按 nuspec 命中，还原图中的映射和框架包均来自相应候选或 R4 公开源。Castle 返回 `Abp.AutoMapper.AutoMapperObjectMapper`，静态入口得到键 10 和 `updated`。按键集合保留集合和键 10 的对象，更新键 10、删除键 20、插入一份键 30。完成调用后，所有加载上下文中只有 `Default` 加载一个 `AutoMapper, Version=14.0.0.0, Culture=neutral, PublicKeyToken=be96cd2c38ef1005` 实例。三份映射 DLL 及内核的归档、Csc 引用、Release 输出和加载路径逐项对账。

固定模板 DTO 的原版和候选均更新原用户实例，保留角色集合、角色成员和创建时间。SQLite 3.46.1 使用 EF Core SQLite 9.0.18 执行带租户 6 参数的筛选和排序，物化用户 ID 依次为 12、13、11。两侧 SQL 的取列、参数和排序一致，`FullName` 均通过用户实体成员在客户端计算。应用和依赖来源、逐次输出、真实 SQL 与参数保存在 `consumer-02/`。

首轮在系统宿主实际加载 .NET 9.0.10，因未达到既有 .NET 9.0.23 比较环境而在验收步骤退出 1。第二轮使用 1.3 已采用的隔离宿主，从新缓存复跑，三路均退出 0。总报告 `consumer-02/report.json` 的 SHA-256 为 `2cae6f309870997e9f70fd200137d3f22c133040b33b670edda94dfe3a30634f`。

两个负向副本让适配器或 Collection 的 nuspec 各指回 `Du.AutoMapper [14.0.0]`，命令均在依赖阶段退出 1，并报告预期与实际边。用旧引擎字节冒用候选的归档文件名，按正式登记摘要执行时在还原前退出 1，并报告归档 SHA-256 不符。原件和各反例日志见 `rejections/`。

同一批次也用于固定模板的新库安装、两代同库接续及固定运行时的三阶段包切换。各入口实物、业务记录及发行交接条件见[固定模板验收](../../../../docs/maintenance/r5-automapper-template.md)。
