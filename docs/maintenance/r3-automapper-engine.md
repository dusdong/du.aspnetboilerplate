# R3 AutoMapper 引擎候选

2026-11-25，本机冻结 `Du.AutoMapper 14.0.0-r3.4` 主包及符号包。候选 ApiCompat 通过，独立消费者在 macOS 27.2.1 ARM64、SDK `10.0.404`、.NET `9.0.23` 中从空缓存安装并通过三个有界映射用例。OpenSpec 2.1 和 2.2 已通过。GHSA-gpwp-5797-mjff 的 CLR 低栈分支按获准的组合证据验收，实际 CLR 低栈触发未观测。[原版基线](r3-automapper-baseline.md) · [OpenSpec 归档](../../openspec/changes/archive/2026-11-25-add-r3-automapper-candidates/)

## 产物与复跑

框架共用序号为 `10.5.1-r3.4`。本机原件目录为 `.git/r3-automapper/package-2/14.0.0-r3.4/`，`manifest.json` 保存批次、源码与包、实际还原图和加载结果。源码从 `bf76a5819e1bad7af7db5382bf0f3a0178048a15` 导出并应用 `source/source.patch` 物化，已在新目录复放，并与 `source/source-tree.json` 逐个核对内容摘要和执行位。物化树保留原始 MIT 许可。Git 归档的 SourceLink 为空，源码来源以基点、补丁与已复验的文件清单回溯。[组件生产与验证命令](../../AutoMapper/src/AutoMapper/ApiCompat/README.r3-engine.md) · [R3 序号分配规则](r3-module-zero-candidates.md#源码生产新批)

| 文件 | SHA-256 |
| --- | --- |
| `manifest.json` | `62c8becad5836bab7da0fd26e10d8cbfcef53a4e06a6c6dca1ae45c4a167f52f` |
| `feed/Du.AutoMapper.14.0.0-r3.4.nupkg` | `7b3d0cc1df220454ad66d34ad4e9ec01699afc4410082698a392aa9db94bd86b` |
| `symbols/Du.AutoMapper.14.0.0-r3.4.snupkg` | `0248d70050425428a33be9f94edc1727525e8b7a474b6d273625b24882804009` |
| 主包 `lib/net8.0/AutoMapper.dll` | `aee0719706bb3d909550832dc7aafb276253e8bf0718151480ad8f76badde72b` |
| 符号包 `lib/net8.0/AutoMapper.pdb` | `7c185642885a91cbaa7be51074be234856a7983abbb9ee19fca9433a525b5d45` |
| 主包 `LICENSE.txt` | `dff9366748df4c70e36fe6fd289f5f87010e74d1d16c06ff11f97ea2c72c75f1` |

普通版和候选的历史参考均为 `AutoMapper 13.0.0/lib/net6.0/AutoMapper.dll`，参考包及包内 DLL 摘要均通过校验，两个 ApiCompat 实际比较结果均为 0 项问题。普通版和候选的公开 API 枚举比较无差异，覆盖 166 个类型及其成员和资源。候选保留 `net8.0`、程序集 `AutoMapper, Version=14.0.0.0, Culture=neutral, PublicKeyToken=be96cd2c38ef1005` 和根命名空间 `AutoMapper`。nuspec 依赖为 `Microsoft.Extensions.Options 8.0.0`。用实际 Release DLL 的 CodeView 标识核对了符号包中的 Portable PDB，主包内许可与固定 MIT 基点逐字节相同。同一维护源码亦可直接生成普通包名 `AutoMapper` 的主包和符号包。[v14.0.0 上游许可](https://github.com/LuckyPennySoftware/AutoMapper/blob/v14.0.0/LICENSE.txt)

## 公告处置与行为证据

三则官方公告的受影响范围都包括固定的 `14.0.0`。维护补丁在固定 MIT 源码上独立编写，以官方公告和 .NET API 文档为行为依据，适用同一 MIT 许可。源代码路径以下均相对引擎的 `src/AutoMapper/`。

| 公告 | 处置与可观察变化 | 源码与实包证据 |
| --- | --- | --- |
| [GHSA-rvv3-g6hj-g44x](https://github.com/advisories/GHSA-rvv3-g6hj-g44x) | `Execution/TypeMapPlanBuilder.cs`、`TypeMap.cs`、`ResolutionContext.cs` 为可静态识别的递归引用映射加入默认运行时深度 64，保留显式正深度和当前引用缓存。超过深度时返回目标默认值，已缓存的引用仍复用。 | `reference-graph` 在自动与显式保持引用两种配置下均得到 64 个节点，自引用指向同一个目标，普通映射更新同一个已有目标对象。 |
| [GHSA-6vhm-j9h7-f9gh](https://github.com/advisories/GHSA-6vhm-j9h7-f9gh) | `Execution/TypeMapPlanBuilder.cs` 在构造开始前计数，并在异常退出时归还计数。超限的构造分支返回默认值。 | `constructor-depth` 中位置记录和 `ConstructUsing` 显式限制均得到 2 层，位置记录的默认限制得到 64 层。捕捉例行的 `ArgumentOutOfRangeException` 后，同一映射上下文得到 21，同一 Mapper 的下一调用得到 34。 |
| [GHSA-gpwp-5797-mjff](https://github.com/advisories/GHSA-gpwp-5797-mjff) | `TypeMap.cs` 让派生映射继承有效运行时深度，`Execution/TypeMapPlanBuilder.cs` 让已配置深度的转换器使用同一计数，`Mapper.cs` 在运行时映射入口检查剩余栈空间。 | `runtime-dispatch` 实测派生映射继承显式深度 2 和默认深度 64，接口、`object`、字典、动态对象、`ExpandoObject` 均保留普通映射结果，转换器在深度 2 截断并在例行参数异常后用同一 Mapper 得到 55。CLR 低栈分支按下节所列的三项组合证据通过。 |

普通引擎全套单测 1183 通过，包含开放泛型父子回指、共享对象身份、普通集合与查询投影。历史的三个有界用例在源码和实包中的断言结果逐项相同，三个实包进程均退出 0 且未超时。实包 DLL、独立 NuGet 缓存中的资产、Release 输出和实际加载位置的 SHA-256 均一致。

## CLR 低栈分支的组合证据

1. 冻结主包内的 `AutoMapper.dll` 在 `AutoMapper.Mapper.MapCore` 的 `IL_0000` 调用 `RuntimeHelpers.EnsureSufficientExecutionStack`。原件目录的 `inspection/runtime-protection-map-core.il` 保存该方法的 IL。
2. 2026-11-25 核对 .NET 9 官方异常契约。运行时判定可用栈空间不足以执行一般 .NET 方法时，该 API 抛出 `InsufficientExecutionStackException`。[Microsoft Learn .NET 9](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices.runtimehelpers.ensuresufficientexecutionstack?view=net-9.0)
3. 独立消费者从同一冻结主包安装并加载同摘要 DLL，运行 `application-exception`。测试转换器在普通标量输入 21 时注入一次带标记的异常，调用方收到 `AutoMapperMappingException`，其包装链包含同一个注入的 `InsufficientExecutionStackException` 对象。同一进程中的同一 Mapper 随后处理普通输入并返回 55。初测 PID 为 38026，独立复审 PID 为 39796，两次均在 ARM64 .NET `9.0.23` 运行并退出 0、无超时。异常来源为 `test-injection`。

该组合覆盖本变更要求的调用存在性、运行时异常契约和应用层恢复。实际 CLR 低栈触发未观测。原件上一级的 `application-exception/evidence.json` 把补充运行、同一主包及加载 DLL、IL 和原清单关联起来，SHA-256 为 `db0b64ddf2822a6ad5801d94d41bd3c7decc8f949e61f42835a04158f9383a22`。同目录下的 `process/report.json` 保存进程命令、PID、工作目录、运行时和断言结果。

从新空目录按子仓说明复跑了全部四个独立场景，均退出 0 且未超时。应用层场景 PID 42876，再次确认注入对象身份并恢复到 55。重新提取的 `Mapper.MapCore` IL 与冻结记录相同。`application-exception/acceptance-close/index.json` 为本次验收索引，SHA-256 为 `323b7e7e78ef1f17480e3f10d6790d9a83bbf1d2943f2e0f01531d8208fe44b5`。[完整复跑命令](../../AutoMapper/src/AutoMapper/ApiCompat/README.r3-engine.md#完整实包行为复验)

冻结时生成的 `manifest.json` 保留当时的 `openValidation`，它记录了尚未取得实际 CLR 低栈异常及同一 Mapper 恢复的动态证据。后续应用层补充证据、独立复审和组合验收结论由本页与补充索引承载，原清单及原件摘要保持不变。

## 验证记录

原件目录的 `apicompat/` 保留参考校验、Release binlog 和比较响应文件，`pack.binlog` 记录同一次构建产物的打包。`inspection/` 保留 Nuspec、PE/PDB 匹配、公开 API 前后比较和运行时保护的 IL。`consumer/` 保留实际还原配置、资产图、编译 binlog、进程命令、工作目录、结果和原始输出。上一层的 `identity-review/` 保留固定基点与修正后的两个具名测试、全套 TRX 及真实退出码。
