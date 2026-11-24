# 有参考价值的 ASP.NET Boilerplate Fork 项目

> 核查日期：2026-11-21。研究对象是经典 ASP.NET Boilerplate（`aspnetboilerplate/aspnetboilerplate`），不是使用 `Volo.Abp.*` 的新 ABP Framework。
>
> 本文用于为用户自己的维护型 fork 选择补丁、工程实践和研究方向。参考项目的名称、版本和维护承诺均属于各自维护者；`Du.Abp.*` 是用户未来发行的包身份，不是这些项目的名称。
>
> 配套路线：[参考 Silo：一条适合维护型 fork 的路线](fork-roadmap.md)。

## 1. 兼容性硬约束：先于任何参考方案

**原有 `Abp` 及 `Abp.*` 代码命名空间永久保持不变。`Du.` 前缀只用于 NuGet 包名，不进入代码命名空间。该约束适用于后续代码修改、依赖升级、生成代码、迁移文档和发布审查。**

| 身份 | 用户发行版的规则 | 示例 |
| --- | --- | --- |
| 根 NuGet PackageId | 增加 `Du.` 前缀 | `Abp` → `Du.Abp` |
| 模块 NuGet PackageId | 增加 `Du.` 前缀 | `Abp.EntityFrameworkCore` → `Du.Abp.EntityFrameworkCore` |
| 原有代码命名空间 | 永久保留 | `Abp.Domain.Entities`、`Abp.Application.Services` |
| 原有程序集名称 | 建议继续保留，作为兼容性基线 | `Abp.dll`、`Abp.EntityFrameworkCore.dll` |
| 新增框架模块命名空间 | 沿用 `Abp.*` 体系 | 包为 `Du.Abp.Mapperly` 时，代码仍使用 `Abp.Mapperly` |

包名变化不等于完全的源码或二进制兼容。目标框架、公开 API、程序集版本、序列化类型标识、传递依赖和数据库行为仍应分别验证。保留原程序集名称时，应检查整个 NuGet 依赖图，避免应用同时引入原 `Abp.*` 包和提供相同程序集的 `Du.Abp.*` 包。

这项约束针对本 fork 的框架代码与发行身份，不要求业务应用或第三方库重命名。参考项目若修改了程序集名或公共类型，应只借鉴所需实现，不原样带入这些身份变化。

## 2. 筛选方法与证据边界

本次通过最近一年推送记录、项目名称和描述检索了 100 余个候选，对同源仓库比较默认分支，并检查有线索的专题分支、提交、上游 PR、Release、NuGet 包及 CI 运行。GitHub Forks 页面未能返回完整列表，故不宣称遍历全部约 3,800 个 fork。

筛选采用以下原则：

- **有最近推送不等于有独立开发。** 同步上游、修改 README 或只改 SDK 配置，不能据此列为持续维护发行版。
- **默认分支没有独有提交，也不等于仓库没有价值。** `antheus-s` 的新工作位于专题分支。
- **ahead/behind 是提交图统计。** 合并提交和 cherry-pick 会影响计数，不能直接换算为原创功能或遗漏缺陷。
- **配置、运行记录和产物分别核对。** 存在 workflow 不代表已经运行；依赖提交成功不等于构建测试通过；源码项目存在不代表已经正式发包。
- 本次是源码与公开记录审查，**未在本地重新还原、编译或执行测试**。文中的维护者测试报告与独立查到的 CI 结果分别标注。

## 3. 参考项目总览

| 项目 / 应看分支 | 最近核实的实质工作 | 主要参考价值 | 定位 |
| --- | --- | --- | --- |
| [yopichy/aspnetboilerplate](https://github.com/yopichy/aspnetboilerplate)，`main` | 2026-09-10 | .NET 10、独立包身份、真实发包、Mapperly、依赖维护 | 独立发行的首要参考 |
| [antheus-s/aspnetboilerplate](https://github.com/antheus-s/aspnetboilerplate/tree/bugs/11195-webhook-ssrf-protection)，Webhook 安全分支 | 2026-11-11 | Webhook 安全、租户隔离、回归测试和上游协作 | 近期活跃的补丁来源 |
| [neominky/aspnetboilerplate](https://github.com/neominky/aspnetboilerplate/tree/Replace-Castle-DynamicProxy)，`Replace-Castle-DynamicProxy` | 2026-06-30 | 拦截抽象、源码生成器、并发语义、迁移说明 | 架构实验参考 |
| [DeploySolutionsSandbox/aspnetboilerplate](https://github.com/DeploySolutionsSandbox/aspnetboilerplate)，`dev` | 2026-02-19 | 中央包版本管理、Serilog、部分 ORM 范围裁剪 | 工程整理参考；近期持续维护证据不足 |
| [totpero/aspnetboilerplate](https://github.com/totpero/aspnetboilerplate/tree/net10)，`net10` | 2025-11-13 | 较早的 .NET 10 / EF Core 10 适配 | 历史迁移补丁参考 |
| [yoyoboot/Yoyo.Abp](https://github.com/yoyoboot/Yoyo.Abp)，派生项目 | NuGet 页面标注 2026-10-29 更新；公开源码另行核对 | 独立包体系、默认主键策略、产品化 | 包仍在更新；最新发行源码对应关系未确认 |

“值得参考”是针对某项工作作出的判断，不代表这些项目已经证明多年治理成功，也不代表建议直接选其 HEAD 作为生产发行基线。下载数、Star 和 fork 数不能直接换算为真实生产用户或维护质量。

## 4. yopichy：最直接的独立发行实践

### 4.1 固定研究快照

- 默认分支：`main`。
- HEAD：[`0e5b06ce33471403da0804d6a948b5794ee31739`](https://github.com/yopichy/aspnetboilerplate/commit/0e5b06ce33471403da0804d6a948b5794ee31739)，2026-09-10。
- 与本次上游 `dev`（`21f57d282f542aa4221fc5cd5a4ac76346d8f5c7`）比较：28 ahead / 34 behind。
- 共同祖先：`c727b75bfc694cddea1ccb2235720a842df6f58d`，2026-01-27。
- 从共同祖先到 fork HEAD，累计改变 148 个文件，包含目标框架、包名、文档及实现修改。
- 已有 GitHub `v10.5.0` 至 `v10.5.3` 四轮 Release；NuGet 维护者页面列出 40 个 `AbpLts` 系列包，当前核心包为 10.5.3、目标框架为 .NET 10。[Y1]、[Y2]、[Y3]

28 个 fork 独有提交包含合并提交和两条保留上游作者的 cherry-pick。不能把“28 ahead”解释为 28 项原创功能，也不能把“34 behind”解释为遗漏 34 个缺陷。

### 4.2 已落实的主要工作

| 工作 | 核实到的变化 | 对用户 fork 的价值 |
| --- | --- | --- |
| .NET 10 迁移 | 当前 41 个 `src` 项目统一 `net10.0`；SDK 与工作流更新；EF Core API、Redis 调用、测试宿主和插件路径同步调整 | 可直接研究真实迁移差异 |
| 独立包身份 | PackageId 改为 `AbpLts` / `AbpLts.*`，保留原 `Abp.*` 程序集和命名空间 | 与用户的 `Du.Abp.*` 包名方案高度相关 |
| 打包修复 | 使用 `$PSScriptRoot` 定位，按实际 `.nupkg` / `.snupkg` 收集产物 | 避免源码项目名与包名分离后脚本失效 |
| Mapperly 模块 | `IObjectMapper` 适配、双向映射、集合、前后钩子、DI 和多组测试 | 可作为可选映射模块的起点 |
| 行为修复 | 日期区域设置处理、跨平台 Blob 文件名归一化 | 可改善跨平台一致性；需验证已有数据 |
| 多轮依赖维护 | 6、7、9 月更新依赖，记录升级理由、暂缓项和测试范围 | 值得借鉴维护记录方式 |
| 上游修复移植 | owned entity 删除历史（#7202）、UTC offset 映射（#7206） | 保留作者与原提交来源，便于追溯 |

主要代码入口是 [.NET 10 迁移提交][Y4]、[核心项目文件][Y5]和[打包脚本][Y6]。

这里的 .NET 10 迁移涉及公共 API。例如，EF Core 的 `BatchUpdateAsync` 参数从旧的 `SetPropertyCalls<TEntity>` 表达式改为 `Action<UpdateSettersBuilder<TEntity>>`。因此，README 中“替换包名和版本即可”的描述不能覆盖所有消费者，仍需检查公开 API 和外部模块。[Y4]

41 个源码项目与 40 个发包项目的差异是遗留的 `Abp.ZeroCore.IdentityServer4.vNext.EntityFrameworkCore`：它仍在源码中，但不在打包清单里。这是继承上游的范围，不能将其写成已经发行的支持能力。当前框架依旧保留 Castle Windsor 等核心架构；没有完成核心 DI 替换。[Y5]、[Y6]

### 4.3 版本号不能代替上游修复清单

**`AbpLts 10.5.3` 不表示包含上游 `Abp 10.5.1` 的全部修复。** 两条发行线已经分叉。除已移植的 #7202、#7206 外，下列上游工作需要逐项审查；本次代码比较没有发现其已被完整吸收。[Y1]、[Y3]

| 上游 PR | 内容 | 维护优先级 |
| --- | --- | --- |
| [#7197](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7197) | EF Core 级联软删除 | 检查删除语义和数据一致性 |
| [#7208](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7208) | Webhook subscription 租户隔离 | 使用多租户 Webhook 时优先 |
| [#7214](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7214) | 避免每个租户重复编译查询 | 检查缓存与租户上下文 |
| [#7216](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7216) | OpenIddict 创建实体时的保存 / UoW 处理 | 检查认证存储行为 |
| [#7218](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7218) | 查询过滤应用失败时拒绝继续执行 | 防止过滤失效后继续返回数据 |
| [#7219](https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7219) | 嵌套 compiled query 的过滤状态修复 | 检查租户与软删除过滤正确性 |

前五项已进入上游 v10.5.1；#7219 在该版本之后合入 `dev`。移植到 EF Core 10 时应复核接口及执行路径，并带上回归测试，不能只复制上游 EF Core 9 的实现后便宣布问题解决。[U1]

### 4.4 Mapperly 的真实兼容边界

| 已看到的代码事实 | 采用时的要求 |
| --- | --- |
| `IObjectMapper.ProjectTo<T>()` 直接抛出 `NotSupportedException` | 为现有投影调用提供迁移方案 |
| 使用 `MakeGenericType`、`GetMethod`、`Activator.CreateInstance` 和 `Expression.Compile()` | 不宣传集成层“零运行时反射”；AOT / 裁剪需独立发布验证 |
| `PreInitialize()` 全局替换 `IObjectMapper` | 与 AutoMapper 渐进共存需明确委派、注册和调用策略 |
| Queryable 测试使用 `List<T>.AsQueryable()` | 增加真实 EF 查询提供程序的 SQL 翻译与执行测试 |
| `Riok.Mapperly` 设置 `PrivateAssets="all"` | 消费者编写 `[Mapper]` 时须显式引用源生成器包 |

这些结论分别来自[映射实现][Y7]、[模块注册][Y8]、[项目依赖][Y9]和[Queryable 测试][Y10]。模块提供有价值的迁移起点，但不能按“完整无缝替换”或“已完整支持 NativeAOT”采用。

README 将 AutoMapper 许可变化起点写成 v14，也需要纠正：官方 15.0 升级指南明确列出新增许可证要求。依赖许可应按具体版本的官方资料核对，不能从 fork README 直接推定。[Y11]

### 4.5 公开 CI 与当前安全状态

当前构建工作流只在 PR 上触发，路径限定 `.cs`、`.cshtml`、`.csproj`、`.razor`，只运行 Windows。单独修改 `.props`、`global.json`、工作流或发布脚本，不在该路径触发范围内。[Y12]

本次查到最近一次公开 `build and test` 成功是 **2026-05-01**。9 月 HEAD 的绿色运行是 **Automatic Dependency Submission**，不能据此认定发布提交已通过构建和测试。9 月发布说明报告了 Debug / Release 构建及若干测试通过，这是维护者的验证报告；本次没有独立复现，也没有核到该 HEAD 的公开 build/test 运行。[Y3]、[Y13]、[Y14]

截至核查日，源码仍声明 `AutoMapper 16.2.0`。11 月两项公开公告将 `>=16.0.0, <16.3.0` 列为受影响范围，涉及特定映射路径对深嵌套对象的无界递归；修复版本包括 16.3.0。[Y15]、[Y16]、[Y17]

这不等于所有 AbpLts 应用均存在相同可利用问题：要核对最终还原版本、是否使用该模块，以及是否映射外部可影响的深嵌套输入。它说明发布时的“零剩余漏洞”有时间边界，维护版需要持续跟踪依赖公告。

**采纳建议：**优先研究 .NET 10 适配、包身份、打包和测试宿主修复；补齐上游修复与发布提交验证。Mapperly、日期解析和 Blob 名称变化单独评估，保留明确的迁移边界。

## 5. antheus-s：近期活跃的安全与多租户补丁来源

- 重点分支：`bugs/11195-webhook-ssrf-protection`。
- HEAD：[`6dda30236218dfd699aaaf6837948ebca433c8f4`](https://github.com/antheus-s/aspnetboilerplate/commit/6dda30236218dfd699aaaf6837948ebca433c8f4)，2026-11-11。
- 对本次上游 `dev`：1 ahead / 21 behind。
- 上游 PR：[#7221][A1]，截至核查日开放、未合并。
- 本次未查到该 fork 的独立 GitHub Release；对应构建运行在上游 PR，而非该 fork 自身的发行流水线。

补丁在 Webhook 建立连接时检查解析地址，拒绝回环、私网、链路本地等地址，然后连接到已经检查的地址，避免只在保存 URL 时验证留下的空隙。它覆盖 `DefaultWebhookSender` 和 ASP.NET Core 的发送路径，新增开关、文档和 32 个测试用例。精确 HEAD 的上游 `build` check 已通过。[A1]、[A2]

这个作者此前的 Webhook subscription 租户隔离 PR #7208 已合并，并进入上游 v10.5.1，说明其工作不止一次。[U1]

**值得借鉴：**围绕真实场景提交实现、回归测试和行为变化说明。新保护默认开启，对有意发送到内网的应用及代理使用有影响，移植时应同时交付配置迁移说明。

**使用边界：**把 #7221 作为需要审查的候选补丁；上游 CI 通过不等于完成全面安全审计，也不代表可以承诺所有 SSRF 路径都已解决。它适合加入补丁与贡献者观察名单，尚无证据表明其接管整套框架发行。

## 6. neominky：编译期拦截与 Castle 解耦实验

- 默认分支：`Replace-Castle-DynamicProxy`。
- HEAD：[`81b26585e9b2da5e352db77996fc6375ebdc4aeb`](https://github.com/neominky/aspnetboilerplate/commit/81b26585e9b2da5e352db77996fc6375ebdc4aeb)，2026-06-30。
- 自有开发集中于 2026-06-23 至 06-30；14 ahead / 27 behind。
- 本次未查到 GitHub Release 或自身 Actions 运行，不能作为已验证的持续发行项目。

已实现的主要方向包括 `Abp.Interception.Castle`、`IAbpInvocation` 等抽象、`Abp.SourceGenerators` 和运行时支持模块，生成注册与拦截代码，处理同步、Task 和 ValueTask 路径，并增加宿主、测试、benchmark 和迁移文档。[N1]

特别值得阅读 [2026-06-29 的线程安全与重入修复][N2]：它处理调用状态隔离、对象池、AsyncLocal scope 和拦截器选项，展示了替换动态代理时容易遗漏的语义问题。

迁移指南明确说明，当前显式启用后替换的是服务拦截路径，IoC 仍为 Castle Windsor，完整 AOT 运行尚未支持，手工检查仍使用 JIT。核心项目仍面向 net9.0；移除 Windsor 和映射库调整属于后续路线，不能写成已经完成。[N1]

**采纳建议：**研究公共抽象、兼容路径和并发测试，作为后续架构演进参考。第一版维护发行应避免把整套拦截重构与运行时升级同时引入。样例中的 `PublishAot=true` 不是框架整体 AOT 能力的证明。

## 7. DeploySolutionsSandbox：降低多项目维护成本

- 默认分支：`dev`。
- HEAD：[`a1d259da7ecb27dafaab91bccc1e90143d2beea6`](https://github.com/DeploySolutionsSandbox/aspnetboilerplate/commit/a1d259da7ecb27dafaab91bccc1e90143d2beea6)，2026-02-19。
- 对本次上游 `dev`：12 ahead / 34 behind。
- 本次未查到 GitHub Release；仍沿用 `Abp.*` 包身份，未核到独立发行产品的完整证据。

主要工作是 .NET 10 迁移、`.slnx`、中央包版本管理、Serilog 集成，以及部分 ORM 支持范围的收窄。对用户最直接的参考是 [`Directory.Packages.props`][D1]：集中声明版本可以减少几十个项目分别升级时的遗漏和版本漂移。日志方面可阅读 [Serilog 模块][D2]。

裁剪需要具体阅读代码。其提交标题虽然提及移除 NHibernate 和旧 EF 引用，但不能概括为“彻底删除 EF6”：部分 EF6 项目仍在解决方案中，Dapper 集成逻辑则收窄为 EF Core 路径，其他路径抛出异常。[D3]

**采纳建议：**中央包管理可以单独移植；Serilog 按实际日志需求评估；ORM 裁剪须先写明用户发行版的支持矩阵，再删除或停止发行对应路径。该仓库近九个月未见新的默认分支提交，应列为工程参考，不宣传为近期活跃的长期维护发行。

## 8. totpero 与 jerrytang67：交叉核对 .NET 10 必要迁移项

### 8.1 totpero

- 重点分支：`net10`。
- HEAD：[`0ef45151f97979190fd84ac56f162f75d9e1e2fc`][T1]，2025-11-13。
- 两个主要自有提交，2 ahead / 39 behind；共同基线较旧。
- [上游 PR #7179][T2] 于 2026-03-25 关闭，未合并；本次未查到独立 GitHub Release。

它将目标框架集中到公共配置，并调整 SDK、依赖、EF Core 10 批量更新 API 和 RedisValue 字符串转换。与 yopichy 交叉比较，有助于区分运行时升级的必要改动和某个 fork 的额外选择。仓库后来出现推送，不能据此认定 `net10` 分支持续开发。[T1]、[T2]

### 8.2 jerrytang67

- 默认分支：`dev`。
- HEAD：[`44050865953b9ec1ea81a90885b8134fc6165934`][J1]，2025-11-23。
- 2 ahead / 39 behind；包含 .NET 10、Npgsql、EF 批量更新 API 和 Redis 适配。
- 本次未查到独立 GitHub Release；自定义版本号不能代替公开发包证据。

该仓库更适合补充比对迁移差异，不作为持续维护发行的首选。[J1]

## 9. Yoyo.Abp：产品化可观察，源码对应关系须先确认

这是声明派生自经典 ASP.NET Boilerplate 的项目，但当前 GitHub 元数据不将其列为同一 fork 网络内的 fork。

- 默认分支：`7.3.0-pk`。
- 本次重点检查：`release/10.3`。
- 该分支固定 HEAD：[`762fe45283a1ebd628ac3b7ecb833ea95eeb33fc`](https://github.com/yoyoboot/Yoyo.Abp/commit/762fe45283a1ebd628ac3b7ecb833ea95eeb33fc)，2026-04-27。
- NuGet 页面显示 `Yoyo.Abp 10.5.10`、目标 .NET 10，最近更新日标注为 2026-10-29。[Q1]

公开源码中的变化包括：非泛型 `Entity` 默认继承 `Entity<string>`、独立 `Yoyo.Abp` 包和程序集名、多条版本分支、OpenIddict 调整，以及标签触发打包发布工作流。[Q2]、[Q3]、[Q4]

这里存在必须保留的证据缺口：上述公开 `release/10.3` 分支核心项目仍是 net9.0；最新 NuGet 包的 Source repository 指向 `https://github.com/yoyoboot/YoyoBoot`，本次访问返回 404。因此尚未确认最新 .NET 10 包对应的公开源码提交和可重建路径。不能据此断言源码不存在或项目停止维护，也不能将旧公开分支当作最新包的源码。[Q1]、[Q3]

**采纳建议：**观察产品定位和独立包体系，先要求明确最新包与源码的对应关系。默认主键改变属于业务和数据模型决策；旧 ABP 已有泛型实体主键支持，不需要为借鉴产品化而复制默认主键变化。它改了程序集名，也不应原样带入用户的兼容方案。

## 10. 面向用户发行版的借鉴顺序

| 优先级 | 工作 | 主要参考 | 验收要点 |
| --- | --- | --- | --- |
| P0 | 建立官方基线和上游补丁台账 | 上游 v10.5.1、后续修复、antheus-s | 每项修复有采用状态、原提交与回归结果 |
| P0 | .NET 10 与独立包发行 | yopichy，交叉参考 totpero | `Du.Abp.*` 包依赖一致，代码仍为 `Abp.*` |
| P0 | 发布提交与真实包消费者验证 | 从 yopichy 现有缺口补齐 | 最终提交通过测试；干净项目从实际包安装并运行 |
| P1 | 集中依赖和明确支持范围 | DeploySolutionsSandbox | 版本声明统一；裁剪范围有迁移说明 |
| P1 | 日期、Blob 等行为修复 | yopichy | 旧数据与跨平台行为通过回归 |
| P2 | Mapperly 可选模块 | yopichy | 投影、共存、生成器、真实 EF 查询有明确边界 |
| P2 | 编译期拦截与 AOT 研究 | neominky | 授权、UoW、审计、异步、并发语义均被验证 |

**每次合入和发布都应检查：**

- [ ] 原有 `Abp` / `Abp.*` 命名空间未改变；未引入 `Du.Abp.*` 代码命名空间。
- [ ] `Du.` 仅用于用户 NuGet 包身份；原程序集名称保持既定基线。
- [ ] 传递依赖没有同时引入提供相同程序集的新旧框架包。
- [ ] 公开 API、目标框架、数据和配置变化已记录；未把包名兼容等同于所有行为兼容。
- [ ] 采用的外部补丁保留作者、原 SHA、许可证及适用范围。
- [ ] 最新上游修复和依赖公告已逐项处理；未沿用过时的“零漏洞”结论。
- [ ] 当前发布提交、实际产物和测试结果能够对应。

推荐的组合是：以官方版本保留清晰来源，用 yopichy 降低 .NET 10 和发包成本，跟踪上游与 antheus-s 的具体修复，按需引入中央包管理；将 Mapperly 和编译期拦截安排为独立演进事项。

## 11. 来源索引

所有活动状态均是 2026-11-21 的研究快照；动态页面后续可能变化。固定 SHA 链接用于复核当时代码。

| 编号 | 来源与用途 |
| --- | --- |
| U1 | [上游 v10.5.1 发布记录][U1]：确认已发行修复；#7219 另见正文 PR |
| Y1 | [yopichy 从共同祖先到固定 HEAD 的差异][Y1] |
| Y2 | [yopichy NuGet 维护者页面][Y2]：真实包清单 |
| Y3 | [yopichy v10.5.3 发布说明][Y3]：升级、移植和维护者测试报告 |
| Y4 | [yopichy .NET 10 迁移提交][Y4] |
| Y5 | [yopichy 固定 HEAD 的核心项目配置][Y5] |
| Y6 | [yopichy 固定 HEAD 的打包脚本][Y6] |
| Y7–Y10 | [Mapperly 实现][Y7]、[模块注册][Y8]、[项目依赖][Y9]、[Queryable 测试][Y10] |
| Y11 | [AutoMapper 官方 15.0 升级指南][Y11] |
| Y12–Y14 | [构建工作流][Y12]、[最近公开成功构建测试][Y13]、[9 月依赖提交运行][Y14] |
| Y15–Y17 | [AutoMapper 依赖声明][Y15]、[构造参数递归公告][Y16]、[其他递归路径公告][Y17] |
| A1–A2 | [Webhook 私网保护 PR][A1]、[对应提交的上游 CI][A2] |
| N1–N2 | [编译期拦截迁移指南][N1]、[线程安全与重入修复][N2] |
| D1–D3 | [中央包管理][D1]、[Serilog 模块][D2]、[Dapper 支持范围][D3] |
| T1–T2 | [totpero net10 固定提交][T1]、[上游升级 PR][T2] |
| J1 | [jerrytang67 固定提交][J1] |
| Q1–Q4 | [Yoyo.Abp NuGet 包][Q1]、[默认 Entity][Q2]、[公开核心项目][Q3]、[打包发布工作流][Q4] |

[U1]: https://github.com/aspnetboilerplate/aspnetboilerplate/releases/tag/v10.5.1
[Y1]: https://github.com/yopichy/aspnetboilerplate/compare/c727b75bfc694cddea1ccb2235720a842df6f58d...0e5b06ce33471403da0804d6a948b5794ee31739
[Y2]: https://www.nuget.org/profiles/yopichy
[Y3]: https://github.com/yopichy/aspnetboilerplate/releases/tag/v10.5.3
[Y4]: https://github.com/yopichy/aspnetboilerplate/commit/a5d37de73ff91b40ccaa86db4a2737d60dba2dcf
[Y5]: https://github.com/yopichy/aspnetboilerplate/blob/0e5b06ce33471403da0804d6a948b5794ee31739/src/Abp/Abp.csproj
[Y6]: https://github.com/yopichy/aspnetboilerplate/blob/0e5b06ce33471403da0804d6a948b5794ee31739/nupkg/pack.ps1
[Y7]: https://github.com/yopichy/aspnetboilerplate/blob/0e5b06ce33471403da0804d6a948b5794ee31739/src/Abp.Mapperly/Mapperly/MapperlyObjectMapper.cs
[Y8]: https://github.com/yopichy/aspnetboilerplate/blob/0e5b06ce33471403da0804d6a948b5794ee31739/src/Abp.Mapperly/Mapperly/AbpMapperlyModule.cs
[Y9]: https://github.com/yopichy/aspnetboilerplate/blob/0e5b06ce33471403da0804d6a948b5794ee31739/src/Abp.Mapperly/Abp.Mapperly.csproj
[Y10]: https://github.com/yopichy/aspnetboilerplate/blob/0e5b06ce33471403da0804d6a948b5794ee31739/test/Abp.Mapperly.Tests/QueryableMapper_Tests.cs
[Y11]: https://docs.automapper.io/en/stable/15.0-Upgrade-Guide.html
[Y12]: https://github.com/yopichy/aspnetboilerplate/blob/0e5b06ce33471403da0804d6a948b5794ee31739/.github/workflows/build-and-test.yml
[Y13]: https://github.com/yopichy/aspnetboilerplate/actions/runs/25204704656
[Y14]: https://github.com/yopichy/aspnetboilerplate/actions/runs/34498929020
[Y15]: https://github.com/yopichy/aspnetboilerplate/blob/0e5b06ce33471403da0804d6a948b5794ee31739/src/Abp.AutoMapper/Abp.AutoMapper.csproj
[Y16]: https://github.com/advisories/GHSA-6vhm-j9h7-f9gh
[Y17]: https://github.com/advisories/GHSA-gpwp-5797-mjff
[A1]: https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7221
[A2]: https://github.com/aspnetboilerplate/aspnetboilerplate/actions/runs/43021367659/job/130525099105
[N1]: https://github.com/neominky/aspnetboilerplate/blob/81b26585e9b2da5e352db77996fc6375ebdc4aeb/fork-doc/compile-time-interception-migration.md
[N2]: https://github.com/neominky/aspnetboilerplate/commit/beb0310390ce4b2cf2110f3b6be51095df779079
[D1]: https://github.com/DeploySolutionsSandbox/aspnetboilerplate/blob/a1d259da7ecb27dafaab91bccc1e90143d2beea6/Directory.Packages.props
[D2]: https://github.com/DeploySolutionsSandbox/aspnetboilerplate/blob/a1d259da7ecb27dafaab91bccc1e90143d2beea6/src/Abp.Castle.Serilog/Abp.Logging.Serilog.csproj
[D3]: https://github.com/DeploySolutionsSandbox/aspnetboilerplate/blob/a1d259da7ecb27dafaab91bccc1e90143d2beea6/src/Abp.Dapper/Dapper/AbpDapperModule.cs
[T1]: https://github.com/totpero/aspnetboilerplate/commit/0ef45151f97979190fd84ac56f162f75d9e1e2fc
[T2]: https://github.com/aspnetboilerplate/aspnetboilerplate/pull/7179
[J1]: https://github.com/jerrytang67/aspnetboilerplate/commit/44050865953b9ec1ea81a90885b8134fc6165934
[Q1]: https://www.nuget.org/packages/Yoyo.Abp/10.5.10
[Q2]: https://github.com/yoyoboot/Yoyo.Abp/blob/762fe45283a1ebd628ac3b7ecb833ea95eeb33fc/src/Abp/Domain/Entities/Entity.cs
[Q3]: https://github.com/yoyoboot/Yoyo.Abp/blob/762fe45283a1ebd628ac3b7ecb833ea95eeb33fc/src/Abp/Abp.csproj
[Q4]: https://github.com/yoyoboot/Yoyo.Abp/blob/762fe45283a1ebd628ac3b7ecb833ea95eeb33fc/.github/workflows/pack-and-publish.yml
