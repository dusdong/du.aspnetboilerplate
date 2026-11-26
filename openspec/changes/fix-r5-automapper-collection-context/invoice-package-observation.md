# 冻结前的默认发票实包对照

2026-11-26，公开 `Du.AutoMapper 14.0.0` 和本地候选 `14.0.1` 的默认发票映射各完成 24 次正式调用和 12 次预热，逐次结果一致。两包均返回原发票目标，将编号 `UNSET` 更新为 `INV-301`，将原明细 `999×1` 替换为依次排列的 `42×3`、`17×2`，全部调用均无异常。对这组输入，旧包的注册和预热顺序影响仍未证实。

## 业务条件与结果

沿用订单对照中的有限、无环 DTO 和映射配置。订单配置 `MaxDepth(2)`，发票和明细使用默认配置。两包均使用普通 `Map(source, target)`，每个顺序创建三份新配置，各向等价的已有发票目标正式调用两次。预热用 `ORD-WARM`、`INV-WARM` 和单行 `12×1`，每个目标和输入独立构造。[原订单探针](../../../AutoMapper/src/CollectionOrderProbe/Program.cs) · [发票探针](../../../eng/r5-invoice-probe/Program.cs)

| 每包的对照组 | 固定条件与所交换因素 | 正式发票调用 | 预热 |
| --- | --- | --- | --- |
| 冷启动 | 明细映射固定先注册，只交换订单和发票映射的注册顺序 | 12/12 符合预期，其中 6 次为新配置的首次 `Map` | 0 次 |
| 预热 | 固定明细、订单、发票的注册顺序，只交换订单和发票的预热顺序 | 12/12 符合预期 | 12/12 符合预期 |

已有订单证据使用同一组明细及目标初值，正式待测是配置深度的订单 `Map`，发票仅参与预热。公开旧包和本地实包各有 24 次订单待测和 12 次预热，均符合预期。两包逐次一致，订单目标身份保留，编号更新为 `ORD-301`。发票补测为默认配置补齐了正式调用以及真正的无预热首次调用。[公开旧包订单观测](old-package-observation.md) · [本地引擎实包验收](engine-package-validation.md)

## 集合执行计划

正式测量进程只执行业务映射，另一个进程在相同调用间只读现有计划缓存的键，并在调用完成后检查已封装的订单和发票表达式。两包每个顺序的独立观察均重现正式业务结果。两成员的集合类型均为 `List<LineInput> → List<LineView>`。订单和发票分别持有自己的父级 Lambda 及内联集合表达式块，两个集合块的对象引用不同。结构也不同，两包的订单集合块均含 `OverTypeDepth`，候选的订单集合块另含 `CheckContext`，两包的发票集合块均没有这两个调用。[计划观察入口](../../../eng/r5-invoice-probe/CollectionPlans.cs)

每份新配置的执行计划缓存开始为空。冷启动首次正式调用后只有发票父类型键，预热完成后有订单和发票两个独立的父类型键，所有采样点均无集合类型的缓存键。结合表达式证据，该有限用例的两个成员各自内联集合逻辑。复用同种集合类型没有导致两成员在自然调用中复用同一个集合执行计划。[表达式构造](../../../AutoMapper/src/AutoMapper/Execution/ExpressionBuilder.cs) · [执行计划缓存](../../../AutoMapper/src/AutoMapper/Configuration/MapperConfiguration.cs)

## 实包身份和复跑

本轮使用 macOS ARM64、SDK `10.0.404` 和 .NET `10.0.15`。两侧各自从空缓存还原，仅直接引用精确版本的 `Du.AutoMapper`。还原图均包含引擎及相同的三个 Microsoft.Extensions 传递依赖。公开引擎与传递依赖均来自 nuget.org，候选引擎来自独立登记指向的本地 feed。两进程均从各自的 Release 输出在 `Default` 上下文加载唯一的 `AutoMapper`，两侧分别核对了归档、包内资产、缓存 DLL、Release 输出和实际加载 DLL。[R4 公开登记](../../../docs/maintenance/r5-first-maintenance-review.md#发行版本和上游基点) · [候选独立登记口径](engine-package-validation.md)

| 精确包引用 | 主包 SHA-256 | 包内 `lib/net8.0/AutoMapper.dll` 和实际加载 DLL 的 SHA-256 |
| --- | --- | --- |
| `Du.AutoMapper [14.0.0]` | `9edf3c6163f6d27c7a7c2805c1915a3762bf44ad2ab186ab9a406d7e9925b253` | `12fcba523f7f7199215764b29c5d330aa363c433fa14d4e72257ce835a87e5e1` |
| `Du.AutoMapper [14.0.1]` | `8c780d4d46c4c15879d7e6596e24279285b32079a28cebe3f7316d7e623781b5` | `5ae7cbd55d61bb1848a3223d1f7d33eae5cc6c27ed17ee5509c84f62c506d82d` |

在主仓根目录运行下列入口。输入为 R4 已验公开校验清单、验签下载记录和 1.3 的候选独立登记。候选主包要位于登记相对于其所在目录给出的路径。指定 SDK `10.0.404` 对应的 `dotnet` 和一个待新建的输出目录。[复跑入口](../../../eng/r5_invoice_consumer.py)

```bash
python3 -B eng/r5_invoice_consumer.py \
  --dotnet "$R5_DOTNET" --output "$R5_INVOICE_OUTPUT" \
  --public-manifest "$R4_PUBLIC_CHECKSUMS" --verified-downloads "$R4_VERIFIED_DOWNLOADS" \
  --input "$R5_ENGINE_ACCEPTANCE_INPUT" \
  --input-sha256 6e7a4833f9144fa8da077a63d06b11541af373c135ccdc94bb9e148b5da54ad5
```

本机首次运行退出 0，证据在 `.git/fix-r5-automapper-collection-context/p4/run-01/`。其中 `report.json` 记录两包结果及逐次差异，SHA-256 为 `46fe431e319698d07a16e67e30d3671e62937066fdb37567610f1785477788c5`。每侧目录的 `measurements.json`、`plan-observations.json`、`identity.json` 和 `obj/project.assets.json` 分别保留正式结果、独立计划观察、实际包来源及摘要、还原图。退出 0 表示观察完整、结果稳定且候选符合预期，冻结证据单独由 `invoiceFreezeEvidence` 记录，本轮为 `false`。

阶段收尾时又从两个新建空缓存分别还原公开包与本地候选，重新构建并运行 Release 消费者。两侧各 24 次正式发票映射（含 6 次冷启动首次调用）和 12 次预热均符合预期。复跑报告位于本机证据目录的 `closeout/invoice-replay/report.json`，SHA-256 为 `16ecfb664ebe0c87bff58c94d6ca381a0984bd1ebd97af884d86c7c8caa879f0`。

## 维护评估

主仓 `c14c5b9` 交付了当时进度为 0/7 的规划。原任务 1.1 要求确认至少一个可重复的旧包偏差，1.3 要求用实际候选在同等条件下复跑并确认所观测偏差已纠正。当前活动变更的 3/7 对应 1.1 的公开旧包业务观测、1.2 的源码修正及 1.3 的引擎实包验收。[活动任务](tasks.md)

2.1 正式冻结前仍须证实至少一对旧包运行仅因交换注册顺序或预热顺序而出现稳定差异，且至少一侧偏离预期，实际候选在同组两种顺序下均须符合预期。已测订单与默认发票均符合预期，顺序差异及候选对该差异的纠正仍待证实。保留已验的本地引擎候选，2.1 继续开放，暂缓三包制备和冻结。[正式冻结前判定](specs/automapper-package-consumption/spec.md#scenario-正式冻结前验证顺序影响及候选结果)
