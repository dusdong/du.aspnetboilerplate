# R5 集合映射的本地修正与验证

任务 1.2 在引擎 `maintenance/v14` 的 `f646d492df918d27b9ac96c086933570965efef3` 上完成本地改动。内建集合映射生成计划时，先按包含该成员的类型映射判断是否需要初始化上下文，再按集合元素的类型映射判断。任一映射有要求时，按既有机制在集合操作和深度判断前执行一次上下文检查。两方均无要求时，计划不增加该检查。对于没有包含类型映射的字典成员，仍按元素配置判断。深度上限的判定条件与 R4 的其他保护沿用现有实现。[集合映射](../../../../AutoMapper/src/AutoMapper/Mappers/CollectionMapper.cs) · [上下文表达式](../../../../AutoMapper/src/AutoMapper/Execution/ExpressionBuilder.cs)

补丁和测试从上述固定 MIT 树的集合映射、计划和上下文接口独立编写。补丁与测试的来源为本次本地工作树改动，保留仓库的 `Copyright (c) 2010 Jimmy Bogard` 与 MIT 许可证。[许可证](../../../../AutoMapper/LICENSE.txt) · [补丁许可指南](../../../../docs/compatibility/automapper.md#43-不能直接把新版本代码搬回去并继续统一标记为-mit)

## 本地实测

2026-11-26 在 macOS ARM64 用 SDK `10.0.404` 构建本地 `net8.0` Release，退出 0，零警告和零错误。沿用组件的 ApiCompat 构建目标对原版 `AutoMapper 13.0.0` 的固定 `lib/net6.0/AutoMapper.dll` 检查，报告 0 项问题。用 `LangVersion=13.0` 进行本轮构建和测试，避免 SDK 默认语言版本在既有并发测试源码中选中不同的 `Enumerable.Reverse` 重载。探索性构建以 `14.0.0-r5.p2` 标识，来源是包含未提交改动的本地工作树。[组件 API 比较入口](../../../../AutoMapper/src/AutoMapper/ApiCompat/verify-release.sh)

`net9.0` 组件定向测试 25 项全部通过，其中新增 9 项，既有集合、深度、目标实例更新和内存查询投影 16 项。构建、测试和 TRX 核验均退出 0。[定向测试](../../../../AutoMapper/src/UnitTests/CollectionMappingContext.cs)

| 新增测试 | 实测行为 |
| --- | --- |
| `Collection_plan_checks_context_when_the_member_or_element_requires_it` | 包含成员单独配置深度、元素单独保持引用、两方均有要求时，均在集合块第一条语句执行一次检查。两方均无要求时无该检查。 |
| `Collection_update_reuses_destination_and_preserves_shared_elements` | 从强类型文档或字典更新已有文档，均保留目标和目标集合引用，替换有序明细，并让同一来源明细的两个位置共享目标对象。 |
| `Section_collection_follows_configured_depth` | 无环两级目录中，默认配置和 `MaxDepth(2)` 输出预期的两个子节。 `MaxDepth(1)` 返回空的子节集合。 |

本地对照用 `ProjectReference` 构建 1.1 的同一份订单和发票观测源码，SHA-256 为 `90e8b19728fb46143f75a23771d8de9e644cb2d55335c4dd6591d0a4a1f7754b`。沿用 1.1 已对账的公开旧包结果和同一 `.NET 10.0.15` 运行时。本地一侧的还原图中，引擎解析为项目引用。进程只加载一份 `AutoMapper`，其 SHA-256 为 `2a907ecc367ee92cb0f6718d5353856fbf211618c871c3c90ef3e6ba5d07184e`，与本地 Release 及单元测试输出中的引擎字节一致。公开旧包侧加载 DLL 的 SHA-256 为 `12fcba523f7f7199215764b29c5d330aa363c433fa14d4e72257ce835a87e5e1`。[公开旧包的输入、身份与结果](old-package-observation.md)

两侧逐项核对了输入、配置顺序、预热、参考结果和实际结果。两侧每轮 24 次待测和 12 次预热均符合预期。已试的注册和预热条件下未观测到旧包偏差，旧包顺序影响待维护评估，正式冻结条件未达。后续任务 1.3 已完成[实际候选、双基线 API 比较及公告复验](engine-package-validation.md)。当时下游与模板验收待 2.1 提供顺序差异证据。后续在共享执行计划用例中确认了差异。[后续对照](shared-collection-plan-observation.md) · [冻结前判定](specs/automapper-package-consumption/spec.md#scenario-正式冻结前验证顺序影响及候选结果)

## 复跑记录

本机原始证据位于 `.git/fix-r5-automapper-collection-context/p2/run-03/`。其中 `commands.log` 记录命令及退出码，`comparison.log` 记录 API 比较，`unit.trx` 保留测试结果，`observations.log` 和 `verify.log` 分别保留逐次观测和身份、结果核验。主仓根目录的复跑命令使用新的证据目录，读取 1.1 的 `run-03` 及 R3 已验的参考包。

```bash
bash .git/fix-r5-automapper-collection-context/p2/run-local.sh "$R5_LOCAL_OUTPUT"
```
