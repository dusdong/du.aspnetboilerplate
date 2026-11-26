# R5 引擎实包验收

2026-11-26 完成 1.3 的引擎局部验收。以 R4 生产提交 `f646d492df918d27b9ac96c086933570965efef3` 为基点，从 AutoMapper 子仓的干净提交 `d264ff75831f12e935df8d4703bb05df99eaa000` 制备 `Du.AutoMapper 14.0.1` 主包及符号包。阶段收尾时将候选源码推送至 `maintenance/v14`，由主仓 gitlink 固定。两份包保存在本机。[引擎源码提交](https://github.com/dusdong/AutoMapper/commit/d264ff75831f12e935df8d4703bb05df99eaa000)

验收端检查生产原件后独立登记主包与包内 DLL 的摘要，再由消费入口显式读取这份登记。

| 验收输入 | SHA-256 |
| --- | --- |
| 验收端独立登记 `acceptance-input.json` | `6e7a4833f9144fa8da077a63d06b11541af373c135ccdc94bb9e148b5da54ad5` |
| `Du.AutoMapper.14.0.1.nupkg` | `8c780d4d46c4c15879d7e6596e24279285b32079a28cebe3f7316d7e623781b5` |
| 主包内 `lib/net8.0/AutoMapper.dll` | `5ae7cbd55d61bb1848a3223d1f7d33eae5cc6c27ed17ee5509c84f62c506d82d` |
| `Du.AutoMapper.14.0.1.snupkg` | `d0429c659f2fd0a59ef274e822723aa595efa7b8ef0feb1a1642cc579826de7d` |
| 符号包内 `lib/net8.0/AutoMapper.pdb` | `fc7e9ca5535f553457490286c8b56eb037629bb51cd0131fdb4eb370cfc3c834` |

macOS ARM64、SDK `10.0.404` 下，普通 Release 与候选 Release 分别对原版 `AutoMapper 13.0.0` 的 `lib/net6.0/AutoMapper.dll` 实际执行 ApiCompat，两次均报告 0 项问题。参考包及 DLL 的 SHA-256 分别为 `8ac567aa1ef2ecb44d02583432754e1a57cb64ac2bea3ef01966d25c27c7d621` 与 `61f544f9574b415832fb4130c8bde2e3370214a35acc75ce1e89f2032a04abe5`。随后以公开 R4 `Du.AutoMapper 14.0.0` 主包中的 `lib/net8.0/AutoMapper.dll` 为左侧、以表中候选主包的对应 DLL 为右侧执行 ApiCompat，同样报告 0 项问题。公开 R4 归档及 DLL 的完整摘要见 1.1 记录。[生产复跑入口](../../../AutoMapper/src/AutoMapper/ApiCompat/README.r5.md) · [R4 公开实物对账](old-package-observation.md)

程序集仍为 `AutoMapper, Version=14.0.0.0, Culture=neutral, PublicKeyToken=be96cd2c38ef1005`，根命名空间为 `AutoMapper`，目标为 `net8.0`。公开及受保护 API 清单的 166 个类型及其成员与 R4 一致。程序集沿用 macOS 的 `PublicSign`，两份 NuGet 归档为本地制品。符号包的 Portable PDB 与包内 DLL 的 CodeView 标识和校验和一致。两份 nuspec 与 SourceLink 都指向实际生产提交，并以本地 Git 核对 78 份源码文档。包内 README 标明本地候选身份，MIT 许可与 Jimmy Bogard 署名沿用固定基点。[许可证](../../../AutoMapper/LICENSE.txt) · [本次补丁来源](local-engine-validation.md)

## 消费与公告复验

两个独立 Release 消费者从各自的空缓存精确还原 `Du.AutoMapper [14.0.1]`。本地源只提供登记摘要对应的引擎主包。两路从 nuget.org 还原的第三方包与已验公开 `14.0.0` 还原图中的标识和解析版本一致，本次均为三个 Microsoft.Extensions 传递包。两路的实际还原归档均与独立登记一致。包内 DLL、NuGet 缓存资产、Csc 实际引用、Release 输出及进程加载的 `AutoMapper.dll` 都以表中同一 DLL SHA-256 对账，程序集身份一致。

普通 `Map` 运行在与 P1 相同的 ARM64 .NET `10.0.15` 上。沿用同一份业务源码、订单和发票的数据、初始目标及预期，逐项比较冷启动注册顺序、固定注册的预热顺序和每次重复调用。候选 24 次待测调用、12 次预热均符合预期，逐次业务字段、目标身份和明细顺序与本轮公开旧包观测一致。旧包的顺序影响仍待证，2.1 的正式冻结条件尚未达到。[旧包观测](old-package-observation.md)

公告复验使用已验证候选的同一 DLL，在 ARM64 .NET `9.0.23` 运行四个独立子进程，均退出 0 且无超时。三则公告继续沿用 R4 对上游 14 系列的适用性判断和从 MIT 基线独立编写的处置，补丁来源、既有保护和边界见维护记录。[R4 处置登记](../../../docs/maintenance/r5-first-maintenance-review.md#映射引擎公告与实包) · [保护源码与许可来源](../../../docs/maintenance/r3-automapper-engine.md#公告处置与行为证据)

| 公告 | 本轮实包观测 |
| --- | --- |
| GHSA-rvv3-g6hj-g44x | `reference-graph` 的两种引用保持配置均返回 64 层，保留自引用身份和已有目标更新。 |
| GHSA-6vhm-j9h7-f9gh | `constructor-depth` 的两种显式构造均得到 2 层，默认位置记录为 64 层。常规构造异常后同一上下文得到 21，同一个 Mapper 后续得到 34。 |
| GHSA-gpwp-5797-mjff | `runtime-dispatch` 的派生显式和默认深度分别为 2 和 64。接口、`object`、字典和动态类型返回原预期，转换器以深度 2 执行并在常规异常后恢复到 55。CLR 分支另见下文。 |

同一候选 DLL 的 `Mapper.MapCore` IL 包含 `RuntimeHelpers.EnsureSufficientExecutionStack` 调用。2026-11-26 用 Microsoft Learn 的 .NET 9 页面复核了契约，运行时判断剩余栈空间不足以运行一般 .NET 方法时会抛出 `InsufficientExecutionStackException`。在独立的 `application-exception` 进程中，测试受控注入一次该异常，应用收到含同一对象的 `AutoMapperMappingException` 包装链，同一个 Mapper 随后返回 55。异常来源为 `test-injection`，实际 CLR 低栈触发未观测。[Microsoft Learn .NET 9 契约](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices.runtimehelpers.ensuresufficientexecutionstack?view=net-9.0)

## 复跑与原始证据

从主仓运行。将 `ENGINE_RECEIPT` 指向验收端独立登记文件，将 `ENGINE_RECEIPT_SHA256` 设为验收端另行提供的预期摘要。登记包含 `id`、`version`、`producerCommit`、相对登记文件目录的 `archivePath`、`archiveSha256`、`assetPath` 和 `assetSha256`。源码和探针从本地子仓的登记提交读取。准备合适的 `DOTNET`、`ILSPY` 和一个尚未创建的 `ENGINE_OUTPUT` 目录。

`R4_OBSERVATION` 指向 1.1 已通过的独立观测目录，包含还原原件、产物和逐次结果。可沿用本机 `p1/run-03`，也可用任意新目录重做 1.1。新运行读取公开 R4 校验附件和原 R4 验签留存的 `verified-downloads.json`。只需这两份公开版本校验记录和 1.1 还原的引擎。两侧普通观测使用相同的 .NET 运行时。[1.1 复跑](old-package-observation.md) · [公开校验附件](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json) · [R4 验签记录入口](../../../docs/maintenance/r4-release-candidate.md#公开主包符号与进度核验)

```sh
python3 -B eng/r5_engine_consumer.py \
  --input "$ENGINE_RECEIPT" --input-sha256 "$ENGINE_RECEIPT_SHA256" \
  --public-observation "$R4_OBSERVATION" --output "$ENGINE_OUTPUT" \
  --dotnet "$DOTNET" --ilspy "$ILSPY"
```

本机生产、制品检查、消费者日志及三次 ApiCompat 原件保存在 `.git/fix-r5-automapper-collection-context/p3/`。其中 `handoff.md` 关联生产记录，`acceptance-run-04/report.json` 保存最新的双消费者实包复跑及所用公开还原图，SHA-256 为 `61bc1d9799af38033dd21df06f5a5f6514e0db0e6626f534a82d643e593826a2`。此前通过的 `acceptance-run-03/report.json` 保留在原位。最初两次运行分别在公开证据路径规范化与 Csc 日志识别处退出 1，修正后从新空缓存复跑退出 0。负向验证在还原前拒绝缺少登记摘要、登记摘要错误、包内 DLL 摘要错误、主包缺失及同名归档替换。R4 冻结批次仍有原专项入口。[R5 实包复跑入口](../../../eng/r5_engine_consumer.py) · [R4 固定批次入口](../../../eng/r4_engine_consumer.py)
