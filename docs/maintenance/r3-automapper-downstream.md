# R3 AutoMapper 下游候选

2026-11-25，使用已分配的框架序号 `10.5.1-r3.4`，依次生产 `Du.AutoMapper.Collection 11.0.0-r3.4` 和 `Du.Abp.AutoMapper 10.5.1-r3.4`。两份主包和符号包已在本机冻结。真实编译、普通构建及组件回归覆盖 OpenSpec 2.3 与 2.4。引擎 2.2 已按批准的组合证据通过。应用层受控异常实测确认同一 Mapper 恢复，实际 CLR 低栈触发未观测。[引擎组合证据](r3-automapper-engine.md#clr-低栈分支的组合证据) · [OpenSpec 任务](../../openspec/changes/archive/2026-11-25-add-r3-automapper-candidates/tasks.md)

## 冻结产物

文件路径相对本机 `.git/r3-automapper/package-3/`。批次 `manifest.json` 的 SHA-256 为 `a442aa64237cc425fb9a9372bbb24314fdeabf4f4800e89562b3ad55ca3c9818`，包含共用序号归属、R2 原包、引擎清单及两份下游清单。包内 DLL/PDB 与同次 Release 产物的摘要一致。已核对两个 Portable PDB 的标识与各自 DLL 内的 CodeView 记录。

| 文件 | SHA-256 |
| --- | --- |
| `collection/feed/Du.AutoMapper.Collection.11.0.0-r3.4.nupkg` | `ce6b4e822203a6e6c3cdca2e93c4b19f4268a58cbdda4dd78750d5f077b12931` |
| `collection/symbols/Du.AutoMapper.Collection.11.0.0-r3.4.snupkg` | `0773946f6028bc69b6019d73df42ec5f7fb0909795bedc7d10bcb9ea95e04370` |
| Collection 主包 `lib/net8.0/AutoMapper.Collection.dll` | `2b40c0b711cd0a8c32b96a4c3f14f2fea1937da1e9587f407833a9c279001d26` |
| `framework/feed/Du.Abp.AutoMapper.10.5.1-r3.4.nupkg` | `bef6ab4305110de967d334fd0db71ace4a83a5247939f94235086bf9da641b0a` |
| `framework/symbols/Du.Abp.AutoMapper.10.5.1-r3.4.snupkg` | `c43d93d6d06884ea43f532e0f5545866f2751e1f7b32e568c867dc8e5a9bbfba` |
| 适配器主包 `lib/net9.0/Abp.AutoMapper.dll` | `10200fe03a1a7965d27b7eadc7539bc476d8c19c40ef749d6a863724ad6cc4b3` |

Collection 主包 nuspec 精确依赖 `Du.AutoMapper [14.0.0-r3.4]`，适配器主包精确依赖同一引擎、`Du.AutoMapper.Collection [11.0.0-r3.4]` 和 `Du.Abp [10.5.1-r2.1]`。生产记录保存指定本地源、隔离缓存及完整 `project.assets.json`。两次 Csc 实际传入的引用路径与 NuGet 选择一致，所有上游编译 DLL 均与原归档中同路径 DLL 同摘要。Collection 测试输出随附的引擎 DLL 也与引擎原包同摘要。[R2 内核登记](../../eng/r3_r2_reference.json)

## 普通构建对照

| 组件 | 普通包与依赖 | 普通与候选程序集 |
| --- | --- | --- |
| Collection | `AutoMapper.Collection 11.0.0`，`AutoMapper [14.0.0, 15.0.0)` | `net8.0`，`AutoMapper.Collection, Version=11.0.0.0, Culture=neutral, PublicKeyToken=e57c3f0a3d6646db`，根命名空间 `AutoMapper.Collection` |
| 适配器 | `Abp.AutoMapper 10.5.1`，沿用 `Abp` 项目引用、`AutoMapper 14.0.0` 和 `AutoMapper.Collection 11.0.0` | `net9.0`，`Abp.AutoMapper, Version=10.5.1.0, Culture=neutral, PublicKeyToken=null`，根命名空间 `Abp` |

普通 Release 都实际打包。同源普通与候选的程序集身份、公有和受保护 API、资源清单一致，分别覆盖 11 个和 14 个类型。两组件均无嵌入资源，主包图标与源码字节一致。Collection 候选保留 SPDX `MIT`，并随包携带固定基点的 `LICENSE`。适配器随包携带普通包同一 `LICENSE.md`。

本机 macOS ARM64 的 SDK 为 `10.0.404`。Collection 普通基点及候选各自实际运行 27 项测试，全部通过，VSTest 记录 .NET `8.0.22`。包括 `Should_Keep_Existing_List`、`Should_Update_Existing_Item` 和两项继承映射保留元素引用。普通框架 Release 的 Build、Pack 和 `Abp.AutoMapper.Tests` 分别退出 0，测试 16 项全部通过，VSTest 记录 .NET `9.0.10`。用固定运行时覆盖目录复跑，VSTest 仍报告 `9.0.10`。框架构建保留既有的重复 SourceLink 引用 `NU1504` 和导出源码缺少 SCM 信息的 SourceLink 警告。

## 来源与复跑

Collection 从 `eafbf005becf73f989e1b1c0d52e8699439f837c` 派生，框架从 `819c64cf527b6918a5eafbf42550c93400f1fb75` 派生。两份生产目录分别在证据根的 `collection-production/` 和 `framework-production/`。用基点执行 `git archive`，应用 `source.patch`，再按 `source-tree.json` 核对文件摘要和执行位，分别复验了 60 和 2896 个文件的重放结果。修改由各子仓独立维护，候选构建使用经核对的源码导出和冻结依赖。[Collection 生产入口](../../AutoMapper.Collection/README.r3.md) · [框架生产入口](../../aspnetboilerplate/nupkg/README.r3-automapper.md)

```sh
ROOT="$PWD"
EVIDENCE="$ROOT/.git/r3-automapper/package-3"
ENGINE="$ROOT/.git/r3-automapper/package-2/14.0.0-r3.4/feed/Du.AutoMapper.14.0.0-r3.4.nupkg"
ENGINE_SHA=7b3d0cc1df220454ad66d34ad4e9ec01699afc4410082698a392aa9db94bd86b
COLLECTION="$EVIDENCE/collection/feed/Du.AutoMapper.Collection.11.0.0-r3.4.nupkg"
COLLECTION_SHA=ce6b4e822203a6e6c3cdca2e93c4b19f4268a58cbdda4dd78750d5f077b12931
R2_CORE="$ROOT/.git/r2-core-consumption/package-1/10.5.1-r2.1/feed/Du.Abp.10.5.1-r2.1.nupkg"
bash "$EVIDENCE/collection-production/source/pack-r3-candidate.sh" \
  11.0.0-r3.4 "$ENGINE" "$ENGINE_SHA" "$NEW_COLLECTION_OUTPUT"
bash "$EVIDENCE/framework-production/source/nupkg/pack-r3-automapper-candidate.sh" \
  10.5.1-r3.4 "$ENGINE" "$ENGINE_SHA" "$COLLECTION" "$COLLECTION_SHA" "$R2_CORE" "$NEW_FRAMEWORK_OUTPUT"
```

两个输出目录须尚未创建。适配器复跑沿用已冻结的 Collection 原件。各候选目录的 `commands.log`、`logs/`、`inspection/` 和 `exit-code.txt` 保留实际命令、退出码、资产与编译检查。Collection TRX 位于 `collection/tests/collection.trx`，普通适配器 TRX 位于 `framework-ordinary/tests/abp-automapper.trx`。生产和核验使用本批共用序号登记，未重占号。

## 主仓实包消费与复验

独立最小消费者只直接引用 `Du.Abp.AutoMapper [10.5.1-r3.4]`。其余维护包全部经传递获得。两个映射 nuspec 的四条内部边及 `project.assets.json` 的选择逐项一致。

| 来源 | 精确声明 | 实际解析 |
| --- | --- | --- |
| `Du.Abp.AutoMapper 10.5.1-r3.4` | `Du.Abp [10.5.1-r2.1]` | `Du.Abp/10.5.1-r2.1` |
| `Du.Abp.AutoMapper 10.5.1-r3.4` | `Du.AutoMapper [14.0.0-r3.4]` | `Du.AutoMapper/14.0.0-r3.4` |
| `Du.Abp.AutoMapper 10.5.1-r3.4` | `Du.AutoMapper.Collection [11.0.0-r3.4]` | `Du.AutoMapper.Collection/11.0.0-r3.4` |
| `Du.AutoMapper.Collection 11.0.0-r3.4` | `Du.AutoMapper [14.0.0-r3.4]` | `Du.AutoMapper/14.0.0-r3.4` |

本地冻结源只供登记的精确包 ID，第三方使用 nuget.org。还原前检查独立包、HTTP 和插件缓存为空。最小消费者实际通过 Castle 依赖解析、旧静态 Mapper 和 `AutoMapKey` 更新。在三项调用结束后，枚举全部加载上下文并按引用计算程序集实例数，得到唯一的 `AutoMapper, Version=14.0.0.0, Culture=neutral, PublicKeyToken=be96cd2c38ef1005`，上下文为 `Default`。引擎、Collection、适配器和 ABP 内核各只有一份编译、运行和加载来源，三个映射 DLL 与各自生产 Release、归档和加载文件同摘要。[最小消费者](../../validation/automapper-minimal/AutoMapperMinimal.csproj) · [冻结引擎与生产 Release](r3-automapper-engine.md#产物与复跑)

模板业务消费者复用 1.2 已验的同一项目和五份固定模板源码，保留 `Configurators`、`AddMaps` 和重复 `CreateMap`。另存固定模板 ApplicationModule 原件用于核对配置入口。每轮重新还原并执行原版 ABP `10.2.0`、AutoMapper `14.0.0`、Collection `11.0.0`。同轮在不同进程执行映射候选，附加冻结 `Du.Abp.ZeroCore` 和传递得到的 `Du.Abp.Zero.Common`，两者均为 `10.5.1-r3.3`。[原版输入及做法](r3-automapper-baseline.md#原版消费者) · [Module Zero 冻结原件](r3-module-zero-candidates.md#复跑冻结批次)

| 必需行为 | 原版和候选实测结果 |
| --- | --- |
| 更新已有模板用户 | 返回原 `User`，普通字段取得 DTO 值。保留原 `Roles` 集合和原角色成员引用、角色键及原 `CreationTime`。`CreateUserDto` 仍映射普通字段并忽略角色。 |
| 独立键集合 | 保留集合及键 `10` 的对象引用，更新为 `updated`。键 `20` 删除，键 `30` 新增一次且值为 `inserted`，实际顺序为 `10, 30`。 |
| SQLite 用户投影 | SQLite 使用 `Int32` 租户参数 `6`，在数据库筛选活跃用户，按 `UserName DESC`、`Id ASC` 排序。两边实际读取相同的 29 列，返回 ID `12, 13, 11`，对应 `Zoe Zulu`、`Bea Beta`、`Ada Alpha`。投影表达式访问实体的 `[NotMapped]` 属性，`FullName` 由客户端计算。实际 SQL、参数、取列和返回行保留在报告。 |

| 定向诊断 | 执行方式 | 预期及实际拒绝阶段 |
| --- | --- | --- |
| 冻结传递引擎缺包 | 诊断源省略引擎归档，实际空缓存还原 | `restore`，NuGet 报告缺少 `Du.AutoMapper` |
| 冻结包 SHA-256 错误 | 修改归档副本，独立进程执行同一摘要检查 | `inputs`，列出预期和实际摘要 |
| 同名资产来源冲突 | 从实际还原图构造诊断副本，独立进程执行资产归属检查 | `packages/assets`，同时指出真实引擎包和夹具来源 |
| Collection 改用最低版本依赖 | 只修改诊断归档副本的 nuspec，独立进程执行同一依赖检查 | `inputs/nuspec`，`[14.0.0-r3.4]` 与裸版本 `14.0.0-r3.4` 不符 |
| 同一引擎 DLL 加载两次 | 正向构建的同一程序另启进程，把同一路径和字节载入第二个 `AssemblyLoadContext` | `process/程序集加载`，实际为两个实例，逐个列出 `Default`、`diagnostic-duplicate`、全名、路径和摘要 |

### 消费复跑

从主仓根目录运行。每次调用建立新的消费、证据与缓存目录。保留冻结包目录及相对布局，包括引擎与下游生产 Release；Module Zero 目录另需已登记的符号包和来源证明。命令使用 macOS ARM64 的 SDK `10.0.404`，消费者要求实际运行 `.NET 9.0.23`。

```sh
BASE="$PWD/.git"
for RUN in review-1 review-2; do
  python3 -B eng/verify.py --profile r3-automapper \
    --dotnet "$BASE/r2-core-consumption/package-2/toolchain/overlay/dotnet" \
    --engine-manifest "$BASE/r3-automapper/package-2/14.0.0-r3.4/manifest.json" \
    --candidate-manifest "$BASE/r3-automapper/package-3/manifest.json" \
    --r2-feed "$BASE/r2-core-consumption/package-1/10.5.1-r2.1/feed" \
    --module-zero-feed "$BASE/r3-module-zero/package-1/10.5.1-r3.3/feed" \
    --evidence-root "$BASE/r3-automapper/package-4/$RUN" || break
done
```

### 消费验收记录

2026-11-25 在 macOS 27.2.1 ARM64（`26B131`）执行两轮，Python `3.14.7`、SDK `10.0.404`、实测 `.NET 9.0.23`、目标 `net9.0`。模板两侧的 EF Core SQLite 包为 `9.0.18`，实际 Provider 程序集版本为 `9.0.18.0`，SQLite 引擎为 `3.46.1`。每轮三个正向进程均退出 `0`，未超时。五个诊断均在预期阶段实际返回 `1`，缺引擎时 NuGet 返回 `NU1101` 并报告源映射未选用 nuget.org。

两个消费目录分别解析最小端 35、原版业务 76、候选业务 48 个 `net9.0` 包。按各组比较，两次实际归档摘要一致。复审修订了消费者的 `Projection.cs`，最终两轮的原版与候选共四次执行采用相同的最终源码。与任务 1.2 比较，五份模板编译输入、ApplicationModule 原件和其余四份消费者文件的摘要一致。最终四份结果与任务 1.2 的两份原版结果逐字节一致，六份文件的 SHA-256 为 `01309fd171e6e66d47b68affe4aad0b80ac43d96d1d69d165078ed661780077b`。复审前第四包的四份业务结果也与该摘要一致，原验收保存在 `accepted-1/`、`accepted-2/` 和 `repeat-equivalence.json`。

业务比较允许 SQL 表别名、空白和末级排序显式 `ASC` 的等价表示。原始投影表达式仍随业务报告保存。验收检查实际 `Select` 的 `FullName` 成员绑定、未映射状态及客户端结果。使用首轮捕获的真实 SQL 运行 C# 和 Python 定向用例，别名、空白及换行变化通过，缺少租户或活跃筛选、排序方向错误、SQL 或读取器列错误均失败。Python 额外核对表达式形参改名可通过，`FullName` 计算位置变化会失败。

下表路径相对本机 `.git/r3-automapper/package-4/`。每轮的子报告记录实际命令、退出码和缓存位置。子目录保留原始 `project.assets.json`、`.deps.json`、构建日志、进程原始结果与程序集核对结果。`business-comparison.json` 保存输入文件、规范化后的执行 SQL 及业务差异。`diagnostics/results.json` 逐项记录实际阶段、退出码及来源。

| 证据 | SHA-256 |
| --- | --- |
| `sql-accepted-1/r3-automapper-ih0ek_1x/report.json` | `cb25858c2579b905b538dc3e2e46873dc2d07166c5e730550a94de0838b677a5` |
| `sql-accepted-2/r3-automapper-oje0rkaj/report.json` | `3984687276d8a076a4b20c505e53ae9665381c3af252757a6406839a628efa62` |
| `sql-review/repeat-equivalence.json` | `d8805afbe77f3db2b6406123528c2e7eea440bc733cab9cce79bf98f0a12eeb8` |
| `sql-review/python-cases.json` | `1857bd0ef531a534c94ad19dc67bdd88baf8c23fe9fa366acb8c5c0deb77b445` |
| `sql-review/csharp-cases.json` | `175e2debb6c3b88e46f4787d99d19a9bbb200657ffc36535619559b3b7d47d0c` |

两轮核对冻结引擎及本页下游清单，还核对 R2 清单 `fed4d30960f9c25f444c35ffadedd3746baeefbca2a78e5938ccde1f38d0b3fc` 与 Module Zero 清单 `308e95aa52e3d58958987f2c82631b98ae12d1276449576a8d509080d1080193`。实际输入的 R2 `Du.Abp` 原包摘要为 `0f6d9da908af7b6b51bedb5b942be8fcdc54fa6b07897224dfb2a647c4e75769`。额外的 `Du.Abp.ZeroCore` 与 `Du.Abp.Zero.Common` 原包摘要分别为 `d31388aa0dce09f714ab9ffcd6cf1d1a013079f6a416a7f0685647a236444739` 与 `f714811c53f9e5544e168fbf32971612652c0c5e5ede4d72f9942d076d4d3e93`。报告 `inputs` 栏给出每个归档、实际生产源码或补丁证明，以及主仓验证文件的完整摘要。

上述两轮原始报告的 `scope.engineGate` 保留当时的“2.2 待验”。3.3 收口时重新核对了两轮各 26 份结果文件、验收时的验证源码、固定模板 Git 对象、四份冻结清单及实际包和加载 DLL。两轮输入与已通过 2.2 的冻结引擎一致。引擎独立验收索引 SHA-256 为 `323b7e7e78ef1f17480e3f10d6790d9a83bbf1d2943f2e0f01531d8208fe44b5`。本机 `close-3.3/current-evidence.json` 保存收口核对结果，SHA-256 为 `3b4a000756d5024b75ed322ae66075d75cae4bac64362d5ab368ce3851a85c8d`。[引擎验收记录](r3-automapper-engine.md#clr-低栈分支的组合证据)

收口后，消费入口只更新了新报告的 `scope` 文字。新报告通过 `scope.engineGate` 指向独立引擎验收，用 `scope.excluded` 标明引擎准入、Web.Host 候选缺口统计和完整模板验收在本轮消费范围之外。候选覆盖和后续模板验收以维护路线为准。原报告与收口索引仍按验收时的脚本摘要复核。本机 `report-scope-review/scope-verification.json` 保存新输出的定向复核，SHA-256 为 `f9498f17bd77a8bb5464025f605221d763f8c56f8cfc1cc1364ec18b97df0c88`。[引擎验收记录](r3-automapper-engine.md#clr-低栈分支的组合证据) · [维护路线](fork-roadmap.md#r3验证升级路径和实际消费者)

OpenSpec 3.1 至 3.3 已通过。本次本地验收补齐最后一项，固定 Web.Host 的六项均已取得独立候选，剩余缺口为 **0**。公开发行留待 R4。完整 Web.Host、真实登录、SQL Server、Angular、.NET 10、Windows 和 Linux、整套升级与回退及部署的验收属于后续阶段。[维护路线](fork-roadmap.md#r3验证升级路径和实际消费者) · [OpenSpec 任务](../../openspec/changes/archive/2026-11-25-add-r3-automapper-candidates/tasks.md)

## Git 交付

下表记录 2026-11-25 推送至 `.gitmodules` 登记仓库的组件提交。按候选生产时的导出口径，以 `git archive` 提取对应提交，与冻结 `source-tree.json` 逐文件核对内容 SHA-256 和执行位。各包及原始清单仍使用生产当时的来源证明与摘要。[子模块地址](../../.gitmodules) · [冻结引擎产物](r3-automapper-engine.md#产物与复跑) · [下游冻结产物](#冻结产物)

| 组件及分支 | 冻结生产源码提交 | 主仓 gitlink | 冻结清单文件数 |
| --- | --- | --- | ---: |
| AutoMapper · `maintenance/v14` | `f9fc56aeedd64d3f5e992f2b22fd9260d906fd05` | [`d249ed3a1c99470f42aaff648045acbc89e79dbb`](https://github.com/dusdong/AutoMapper/commit/d249ed3a1c99470f42aaff648045acbc89e79dbb) | 577 |
| AutoMapper.Collection · `maintenance/v11` | `cab138e2b86c7ea890fc242bab015a6dbbb3c8c5` | [`cab138e2b86c7ea890fc242bab015a6dbbb3c8c5`](https://github.com/dusdong/AutoMapper.Collection/commit/cab138e2b86c7ea890fc242bab015a6dbbb3c8c5) | 60 |
| aspnetboilerplate · `dev` | `806a9c7c87ccfd9740b4ec49d60577dadfb02af9` | [`806a9c7c87ccfd9740b4ec49d60577dadfb02af9`](https://github.com/dusdong/aspnetboilerplate/commit/806a9c7c87ccfd9740b4ec49d60577dadfb02af9) | 2896 |

引擎 gitlink 比冻结生产源码多一笔提交，仅用于补充应用层异常恢复的复跑入口和说明。实际 CLR 低栈触发未观测。[引擎冻结源码提交](https://github.com/dusdong/AutoMapper/commit/f9fc56aeedd64d3f5e992f2b22fd9260d906fd05) · [引擎组合验收](r3-automapper-engine.md#clr-低栈分支的组合证据)

从交付版主仓根目录运行 `git ls-tree HEAD -- AutoMapper AutoMapper.Collection aspnetboilerplate` 可核对上述 gitlink。固定模板仍为 `2e9536872673a7ff1986a19e798c51684d16afe5`。[稳定消费规范](../../openspec/specs/automapper-package-consumption/spec.md) · [OpenSpec 归档](../../openspec/changes/archive/2026-11-25-add-r3-automapper-candidates/)

主仓 GitHub Actions 的「R0 基线复验」验证固定的原版 R0 源码。R3.4 的冻结映射包与业务结果来自本页和引擎维护页的本机实测。[R0 工作流](../../.github/workflows/verify-r0.yml) · [R3.4 消费验收](#消费验收记录)
