# 公开旧包的普通集合顺序对照

2026-11-26 完成任务 1.1 的公开旧包观测。订单和发票共享单层明细集合，订单映射配置 `MaxDepth(2)`，发票和明细采用默认配置。预热组固定注册顺序，仅交换带一行明细的订单和发票的预热调用。冷启动组无预热，仅交换订单和发票映射的注册顺序。每侧新建配置三次，每次对等价的来源和已有目标执行同一个普通订单 `Map` 两次。24 次待测调用均返回原目标，编号从 `UNSET` 更新为 `ORD-301`，原明细 `999×1` 由有序的 `42×3、17×2` 替换。12 次预热也符合预期。该有限、无环输入未观察到业务偏差或顺序影响，顺序影响仍待维护评估，正式冻结条件未达。[固定输入与观测入口](../../../AutoMapper/src/CollectionOrderProbe/Program.cs) · [冻结前判定](specs/automapper-package-consumption/spec.md#scenario-正式冻结前验证顺序影响及候选结果)

实测使用 macOS ARM64、SDK `10.0.404` 和运行时 .NET `10.0.15`。隔离空缓存唯一包源是 nuget.org，解析到引擎和三项 Microsoft.Extensions 传递依赖。还原的 `Du.AutoMapper 14.0.0` SHA-256 为 `9edf3c6163f6d27c7a7c2805c1915a3762bf44ad2ab186ab9a406d7e9925b253`，与 R4 验签下载登记一致。进程从独立消费者的 Release 输出加载唯一引擎，加载 DLL 与包内 `lib/net8.0/AutoMapper.dll` 的 SHA-256 均为 `12fcba523f7f7199215764b29c5d330aa363c433fa14d4e72257ce835a87e5e1`。[R4 公开下载登记](../../../docs/maintenance/r5-first-maintenance-review.md#发行版本和上游基点)

在主仓根目录运行以下命令，传入公开校验清单和 R4 验签下载登记。每轮新建证据目录，运行前按当轮用量检查该目录、隔离缓存和实际临时目录。

```bash
python3 AutoMapper/src/CollectionOrderProbe/verify.py "$R5_PROBE_OUTPUT" \
  --public-manifest "$R4_PUBLIC_CHECKSUMS" \
  --verified-downloads "$R4_VERIFIED_DOWNLOADS"
```

`observations.json` 保留逐次业务结果和常规异常，`result.json` 汇总待测结果及预热偏差。两侧重复结果稳定、可观测结果不同且至少一侧偏离预期时，才登记顺序影响。预热偏差单独记录，导致预热组的结果差异无法归因于顺序。程序退出 0 表示观测完整、准备条件符合预期且结果稳定。退出 2 表示存在预热偏差或待测结果不稳定。冻结仍需旧包的 `stableOrderDifference` 为真及实际候选在同组条件下通过。

本机原始证据位于 `.git/fix-r5-automapper-collection-context/p1/`。首次还原成功后，验证器因缓存路径尾斜杠的文本比较退出 1。修正后 `run-02` 完成还原、构建、运行与核验。最终验证器用独立空缓存复跑 `run-03`，同样退出 0，`stableOrderDifference` 为假。后续使用相同订单用例完成了[候选引擎实包验收](engine-package-validation.md)，默认发票的独立对照见[冻结前补测](invoice-package-observation.md)。
