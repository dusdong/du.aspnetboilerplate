# AutoMapper：兼容维护 Fork 评估与实施路线

## 当前状态（2026-11-26）

公开版 `v10.5.1` 使用 `Du.AutoMapper 14.0.0`、`Du.AutoMapper.Collection 11.0.0` 和 `Du.Abp.AutoMapper 10.5.1`。在共享集合执行计划的用例中，公开旧引擎仅交换预热顺序便得到不同结果，候选在两种顺序下均符合预期。本地补丁组合冻结为 `Du.AutoMapper 14.0.1`、`Du.AutoMapper.Collection 11.0.1` 和 `Du.Abp.AutoMapper 10.5.2`，内核仍为公开 `Du.Abp [10.5.1]`。独立消费者已验证已有对象更新、按键集合和 SQLite 投影。固定模板已通过 SQL Server 新库安装、两代同库接续及固定 `net10.0` 的公开 R4 → 候选 → 公开 R4 同库切换。候选结论适用于已记录的组合，公开发行需独立交接。[固定模板验收](../maintenance/r5-automapper-template.md) · [共享集合计划对照](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/shared-collection-plan-observation.md) · [三包冻结与消费](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md)

### R3 兼容基线（2026-11-25）

R3.4 规划基点 `d54f782` 固定了下表的两个 fork。当时经典框架声明 AutoMapper `14.0.0` 和 Collection `11.0.0`，固定模板原版 Web.Host 的还原图也实际选中了这两个版本。[子模块地址](../../.gitmodules) · [参考提交登记](../maintenance/release-baseline.json) · [原版 Host 依赖对照](../maintenance/r3-web-host-baseline.md)

| 组件 | `d54f782` 的 gitlink | 已选兼容参考 |
| --- | --- | --- |
| AutoMapper | `79d10deec5881a617c38e7373f354694044bf83d` | `v14.0.0`，`bf76a5819e1bad7af7db5382bf0f3a0178048a15` |
| AutoMapper.Collection | `5301edbc689a9696bdd7c396452669434e75989a` | `v11.0.0`，`eafbf005becf73f989e1b1c0d52e8699439f837c` |

### R3 独立候选验收

`Du.Abp.AutoMapper 10.5.1-r3.4`、`Du.AutoMapper 14.0.0-r3.4` 和 `Du.AutoMapper.Collection 11.0.0-r3.4` 已在本机冻结并通过独立验收，补齐固定 Web.Host 的最后一个候选包缺口，剩余缺口为 **0**。冻结引擎对三则公告的处置和 ApiCompat 均有证据。CLR 低栈分支按获准的实包 IL、.NET 9 异常契约及受控异常传播和同一 Mapper 恢复实测验收。实际 CLR 低栈触发未观测。[引擎验收](../maintenance/r3-automapper-engine.md) · [维护路线](../maintenance/fork-roadmap.md#r3验证升级路径和实际消费者)

在两个独立空目录还原和运行 `net9.0` 消费者，四条精确依赖均命中，Castle、静态入口和按键集合映射完成后各加载一个引擎实例。固定模板的重复 `CreateMap`、已有用户更新、角色对象和创建时间保留、集合增删改及 SQLite `ProjectTo` 与原版结果一致。三个组件已在各自维护分支交付，主仓固定相应 gitlink。后续完整模板的 SQL Server、Angular 和升级验收见 R4 公开源记录，原版回退另有同批冻结包的本机记录。[消费验收与复跑](../maintenance/r3-automapper-downstream.md#主仓实包消费与复验) · [Git 交付](../maintenance/r3-automapper-downstream.md#git-交付) · [R4 公开源模板消费](../maintenance/r4-release-candidate.md#公开源模板消费)

**下文保留原调研方案和当时的实施状态。**

> 适用对象：需要长期维护、独立发行经典 ASP.NET Boilerplate 的维护者。  
> 调研截至：2026-11-23（Asia/Shanghai）。  
> 文档状态：技术决策建议与实施方案，尚未实施 fork、发布或生产验收。  
> 证据范围：官方安全公告、固定版本源码、公开发行记录、NuGet 元数据及维护者声明。本文没有执行候选包构建、漏洞复现或真实业务回归。

## 一、建议决策

**在“存量项目必须完整保留 AutoMapper 正常业务行为”的前提下，建议以原始 MIT 许可的 AutoMapper 14 为固定基线，建立范围受控、由你掌握发行权的维护线。**

现有社区 fork 可以缩短调研和实现过程，但目前核实的候选中，尚没有一个同时满足以下条件，足以直接认定为可替换的长期维护发行版：

- 保持原有公开 API、命名空间、程序集身份与业务映射语义。
- 对本文列出的三则递归安全公告给出完整、可追溯的修复。
- 同时处理 Collection 等实际依赖的包标识与程序集兼容。
- 有足够的持续维护记录、明确支持承诺和实际消费项目验收证据。

**“尚未找到同时满足条件的候选”不等于“没有成熟度较高或值得参考的 fork”。** MagicMapper 已有公开产品采用证据；AutoMapperMIT 整理了多个关联扩展；ForkForward.Mapper 提供了值得研究的独立安全实现。三者的优势不同，不宜把其中一个项目的全部变更直接并入你的维护线。详见第五节。

如果希望继续由上游承担引擎维护，另一条可行路线是使用已修复的官方版本，并完成许可与兼容性评估。对于本文列出的三则公告，官方共同修复落点为 **15.1.4 或 16.3.0**。这里表示公告对应的修复版本，不表示它们永久安全，也不表示适配器只改一个版本号即可升级。[R09][R10][R11]

### 1.1 已确认的用户硬约束

| 约束 | 文档中的落实方式 |
| --- | --- |
| 经典 ABP 的 `Abp` / `Abp.*` 命名空间长期不变 | 后续改动与发布审查将其作为兼容性硬约束 |
| `Du.` 前缀只用于 NuGet 包名 | 不把代码命名空间改成 `Du.Abp.*`，也不因包名变化自动重命名程序集 |
| 存量项目必须完整保留 AutoMapper 行为 | 不以 Mapperly、Mapster 或其他映射器替换作为本次主方案 |
| Parquet 首包按既定计划推进 | AutoMapper 的评估与维护独立进行，仅约束相关映射模块的发布 |

“完整保留”应覆盖现有业务配置、对象更新、集合行为、查询投影和调用方式。**安全修复必须有明确例外：恶意或过深对象图的处理可能由进程崩溃改为可捕获异常或受控终止。** 这属于需记录、需测试的行为变化，不能承诺连漏洞行为也原样保留。

### 1.2 尚不能下结论的事项

目前没有拿到生产应用的完整还原结果、锁文件及运行时程序集信息，因此不能确认其实际加载的 AutoMapper 版本，也不能确认安全问题在该应用中的可利用性。

本文的候选评估是静态研究，不构成以下结论：候选发布包已经独立验证、某 fork 完全安全、某 fork 与原版二进制完全兼容、或生产应用可以立即替换上线。

---

## 二、经典 ABP 的实际依赖与兼容边界

### 2.1 项目声明版本不等于生产最终解析版本

经典 ABP 的 `v10.5.1` 中，`Abp.AutoMapper.csproj` 声明：

```xml
<PackageReference Include="AutoMapper" Version="14.0.0" />
<PackageReference Include="AutoMapper.Collection" Version="11.0.0" />
```

该模块目标框架为 `net9.0`，程序集名为 `Abp.AutoMapper`，根命名空间为 `Abp`。[R01]

需要修正一种容易误导的说法：`Version="14.0.0"` **不是** NuGet 的精确版本锁定 `[14.0.0]`。实际还原结果还受到应用直接引用、中央包管理、锁文件、其他传递依赖及 NuGet 解析规则影响。[R02]

因此，后续基线调查应分别记录：

1. 框架和扩展包在项目文件中声明了什么。
2. 应用还原后实际选择了什么版本。
3. 发布目录最终携带了什么 DLL。
4. 进程运行时实际加载了什么程序集。

不能仅由框架源码推断生产必定使用 AutoMapper 14.0.0。

### 2.2 Collection 是必须一起分析的依赖

| Collection 版本 | NuGet 声明的 AutoMapper 依赖范围 | 对维护路线的影响 |
| --- | --- | --- |
| 11.0.0 | `[14.0.0, 15.0.0)` | 适合分析现有 14 系列依赖闭包 |
| 12.0.0 | `[15.0.1, 16.0.0)` | 不能继续搭配 14；评估 15 时应同时验证 |
| 13.0.0 | `[15.0.1, 17.0.0)` | 同时覆盖部分 15 与 16，不能描述为仅支持 16 |

以上是包声明允许的范围，不是完整的运行兼容性证明。[R06][R07][R08]

只发布 `Du.AutoMapper` 并不会自动满足 Collection 对包标识 `AutoMapper` 的依赖。NuGet 按 PackageId 解析依赖；“同一个 DLL 名称”不能替代这个关系。若不修改依赖闭包，应用可能同时还原原版与维护版，并遇到同名程序集资产冲突或错误版本被选中的问题。[R43]

### 2.3 经典 ABP 的接入方式决定了验收内容

经典 `AbpAutoMapperModule` 使用 Castle 注册及自身初始化流程：执行配置器、创建 `MapperConfiguration`、创建并注册 `IMapper`，并设置兼容旧调用方式的 `AbpEmulateAutoMapper.Mapper`。它不是简单调用现代 ASP.NET Core 示例中的 `services.AddAutoMapper()`。[R03]

此外，还有两处特别容易被忽略：

- 经典 `IObjectMapper` 暴露 `ProjectTo`。因此，只有普通对象映射测试通过，不能证明查询投影兼容。[R05]
- `AutoMapKey` 相关配置通过 `Assembly.Load("AutoMapper.Collection")` 加载扩展程序集，再反射查找集合比较方法。修改 Collection 的程序集名会直接影响这个路径。[R04]

公开的配置器、Profile、映射扩展及适配器还涉及 AutoMapper 类型。仅保留 `Abp.*` 命名空间，并不足以证明底层引擎可以被任意替换。

---

## 三、安全问题：应处理三则公告，不能只补一个深度值

### 3.1 公告与修复版本

| 公告 | 主要问题 | 官方列出的受影响范围 | 官方修复版本 |
| --- | --- | --- | --- |
| CVE-2026-32933 / GHSA-rvv3-g6hj-g44x | 无充分默认限制的自引用递归，可耗尽进程栈 | `<15.1.1`；`>=16.0.0, <16.1.1` | 15.1.1 / 16.1.1 |
| CVE-2026-128082 / GHSA-6vhm-j9h7-f9gh | 构造参数递归等路径在深度计数生效前创建目标，可能绕过限制 | `<15.1.4`；`>=16.0.0, <16.3.0` | 15.1.4 / 16.3.0 |
| CVE-2026-128081 / GHSA-gpwp-5797-mjff | 继承映射、动态类型及其他运行时递归路径的保护缺口 | `<15.1.4`；`>=16.0.0, <16.3.0` | 15.1.4 / 16.3.0 |

第一则公告发布于 2026 年 3 月；后两则为 2026 年 11 月公告。AutoMapper 14.0.0 落在上述公告列出的受影响版本范围内。[R09][R10][R11]

**15.1.1 是第一则公告列出的修复版本，不是本项目今天的综合升级建议。** 本文只将 15.1.4 / 16.3.0 作为覆盖这三则公告的官方版本落点；具体应用仍需核实最终解析版本与所用路径。

### 3.2 为什么单点缓解不够

默认 `MaxDepth = 64` 能覆盖部分递归路径，但不能独立解决所有问题。构造参数可能在深度增加之前继续递归；派生映射、对象或接口类型、字典与动态对象、转换器再次调用映射器等路径，也需要单独分析。[R10][R11]

同样：

- `PreserveReferences` 主要处理重复引用；不能把很深、每层均为不同实例的对象图当作同一问题。
- 关闭构造函数映射只能覆盖适用类型；对于依赖构造参数、记录类型或自定义构造行为的存量业务，既不通用，也可能破坏兼容。
- 只把异常包在更外层，无法证明已经避免了栈耗尽。

官方 15.1.4 的发布说明同时涉及构造路径的深度控制、派生映射深度继承、运行时栈保护，以及相关上下文处理。说明修复应覆盖多个相互关联的位置。[R12]

### 3.3 维护版应如何证明修复

建议建立逐项安全台账，而不是只写“已回移安全补丁”：

| 台账字段 | 应记录的内容 |
| --- | --- |
| 公告与路径 | 哪个 CVE、哪类映射会触发 |
| 基线状态 | 原始 14 及候选 fork 在该路径上的行为 |
| 实现来源 | 独立实现、已获授权的回移，或经核实的 MIT 补丁 |
| 代码与测试 | 修复提交、回归测试、异常传播和清理路径 |
| 发布覆盖 | 哪一个维护版包首次包含修复 |
| 兼容影响 | 正常深度、截断规则、异常类型、集合状态是否改变 |

危险深度测试应在独立子进程中执行，并检查退出码、输出及超时，避免把整个测试宿主一起带崩。对可恢复失败，还要验证失败后的映射上下文与后续正常映射没有被污染。

这是拟议的验收要求，**不是本报告已经完成的测试**。

### 3.4 风险如何落到实际应用

这些公告主要涉及拒绝服务风险：在相应映射路径上，递归可能导致栈耗尽和进程终止。实际风险取决于攻击者是否能够影响对象图的结构或深度，以及应用是否执行了相关映射。[R09][R10][R11]

“依赖位于受影响范围”和“生产已被证明可利用”必须分别表述。前者已有公告依据；后者目前没有证据。

---

## 四、许可：以固定 MIT 基线维护，另审查每个新补丁

### 4.1 原始 14 与后续版本的许可不同

原始 AutoMapper `v14.0.0` 的许可证为 MIT。该版本已授予的 MIT 权利不会因为后续版本改变许可而自动失效；发行时仍需保留相关版权与许可文本。[R13][R15]

AutoMapper `v15.1.4` 的许可证文件采用 RPL 1.5 或 Lucky Penny 商业许可路径。不能把这概括成“所有用户都必须付费”，也不能把“不设置许可证时未立即禁用功能”解释成已经取得授权。[R14][R15]

### 4.2 框架分发与终端应用使用应分别核对

你的目标包含独立发行维护版框架，因此许可分析不能只停留在“我的公司能否使用”。

需要分别确认：

- 自己的内部应用使用。
- 将引擎嵌入终端应用并交付。
- 面向第三方分发框架、包装层或开发者库。
- 下游使用者是否需要独立取得相应授权。

当前商业条款对独立框架、包装库等第三方分发另有约束，应针对实际发行方式核对。ABP 本身的许可、某个维护者的 Community 资格或许可证密钥，都不能直接推导出所有下游使用场景已被覆盖。[R16]

本文没有认定某个现有 ABP 适配器违反许可，也没有给出个案法律合规结论。

### 4.3 不能直接把新版本代码搬回去并继续统一标记为 MIT

旧基线是 MIT，并不意味着后来不同许可版本中的代码自动成为 MIT。

每个安全补丁应保留以下证据：

1. 具体来源仓库、固定提交和当时适用的许可证。
2. 是否独立实现，是否包含后续不同许可源码。
3. 作者或版权方的授权，以及贡献者声明。
4. 引入范围、保留的版权说明及审查记录。

现有 fork 声明 MIT 或声明独立实现，是有价值的调查起点；它本身并不替代完整的来源审查。建议将安全实现、测试用例和文档各自的来源也记录清楚。

### 4.4 若改走官方 15 路线，仍需代码适配

AutoMapper 15 调整了 `MapperConfiguration` 构造方式，需要提供 `ILoggerFactory`，并引入许可证配置。经典 ABP 当前的初始化代码不能仅通过修改 NuGet 版本号完成适配。[R03][R17]

同时要验证 Collection 版本范围、现有配置器、Castle 依赖解析、模块启动及真实集合映射。**官方版本路线可以降低自维护引擎的成本，但不会消除许可和兼容验证工作。**

---

## 五、有哪些值得参考的 AutoMapper fork？

### 5.1 结论总览

下表中的“版本”是本次核实的公开发行版本；“未覆盖”判断结合固定版本源码，不仅根据最后更新时间推断。

| 项目 | 已核实版本与时间 | 值得参考的部分 | 对当前目标的主要限制 | 建议定位 |
| --- | --- | --- | --- | --- |
| NET-Sorcery / MagicMapper | 14.0.1，2026-03 | 原有命名与程序集设计；公开产品采用证据 | 已含 3 月修复，但固定版本仍存在 11 月关键路径缺口 | 兼容发行与采用案例参考 |
| Shane32 / AutoMapperMIT | 14.0.3，2026-05 | Core 与多个扩展包的依赖整理 | 11 月覆盖不足；签名配置差异；无明确长期支持承诺 | 依赖闭包与扩展组织参考 |
| ForkForward / dotnet-mapper | ForkForward.Mapper 15.0.0，2026-11-20（北京时间） | 独立安全实现、异常处理、回归测试与迁移说明 | 项目很新；改命名空间、程序集与部分行为 | 安全设计参考，不作为直接替换包 |
| Klausmd5 / AutoMapper | Klausmd5.AutoMapperLegacy 14.2.0，2026-03 | 针对旧线的较小修复与发行实践 | 目标框架和维护范围有变化；未找到 11 月完整修复证据 | 补充源码参考 |
| zgabi / AutoMapper | zgabi.AutoMapper 14.0.0，2026-03 | 对 3 月问题的较小修补 | 发行与维护证据有限；未找到 11 月完整修复证据 | 单点补丁参考 |

公开仓库、NuGet 包及固定版本来源见本节与文末索引。[R21][R22][R27][R28][R34][R37][R39][R40][R41][R42]

下载量、星标数和仓库创建时间只能辅助判断。这里不把它们作为安全、二进制兼容或未来支持的证明。

### 5.2 MagicMapper：最值得参考其兼容发行与实际采用

仓库：[NET-Sorcery/MagicMapper][R21]  
包：[MagicMapper 14.0.1][R22]

其主要价值是保持 `AutoMapper` 命名空间及 `AutoMapper` 程序集名的设计。项目定位是延续原有 API 的 MIT 维护方向；但发布包的完整程序集身份以及你的消费项目是否可以直接替换，仍需独立验证。[R21]

**14.0.1 已经包含 3 月默认深度保护，不能误写成该修复只存在于发版后的分支。**

同时，固定标签中的映射计划仍显示先创建目标再增加相关深度计数，运行时映射核心没有覆盖后续公告所需的通用栈保护。这些静态证据支持“不能视作已经完整处理 11 月问题”的判断，而不是已经执行漏洞复现的结果。[R23][R24]

Veeam 的公开产品更新说明记录了将 AutoMapper 替换为 MagicMapper 14.0.1。这说明它有实际采用价值，但并不能证明该包覆盖了后来公布的安全问题。[R25]

另有 `MagicMapper.Collection` 包可参考，但它有独立维护来源。不要将存在同名前缀扩展包，等同于核心和全部扩展已有统一维护与支持保证。[R26]

**建议借鉴：** 包名与代码身份分离、迁移说明、真实消费场景。  
**不建议直接照搬：** 把当前 14.0.1 作为无需额外安全工作的最终维护发行版。

### 5.3 AutoMapperMIT：最值得参考其扩展包与依赖组织

仓库：[Shane32/AutoMapperMIT][R27]  
发行：[14.0.3][R28]

该项目将 Core、Collection、ExpressionMapping 和若干 EF 相关扩展放在统一维护结构中。对于“换了 Core 包名后，哪些扩展还会重新拉入原包”这一问题，它比只有核心仓库的 fork 更有参考价值。[R27]

但是，需要注意三点：

1. 固定版本源码包含 3 月深度相关修复，但构造路径与运行时入口仍有对应 11 月公告的关键缺口。[R29][R30]
2. 核心签名配置与原 AutoMapper 的配置存在差异。即使程序集名仍为 `AutoMapper`，也不能因此承诺对全部已编译组件直接二进制替换。[R31][R51]
3. 维护者曾公开说明没有新增功能或提供支持的计划，并对接收补丁的来源提出限制。2026-11-20 创建的 Issue #18 仍在询问三则公告的完整覆盖；截至本次核实，该问题未关闭且无回复。[R32][R33]

该项目还扩大了部分目标框架范围。你的第一版维护线不必因为参考它，就同时承接所有旧框架和全部 EF 适配。

**建议借鉴：** 扩展包集合、ProjectReference 与包依赖重定向、统一发行组织。  
**不建议直接接受：** “MIT 包名 + 相同 namespace = 无需验证的长期支持替代版”。

### 5.4 ForkForward.Mapper：最值得参考安全实现，不适合当前目标直接替换

仓库：[ForkForward/dotnet-mapper][R34]  
包：[ForkForward.Mapper 15.0.0][R37]

它基于 MIT 时期的 AutoMapper 源码，项目自己的版本号 15.0.0 **不代表直接采用商业许可的 AutoMapper 15 源码**。项目文档声明对公开安全问题进行了独立实现；该声明仍需要在正式采用前结合提交与许可记录审查。[R34][R35][R36]

主要可借鉴点包括：

- 在运行时映射递归入口检查剩余栈空间。
- 对过深对象图使用能够向外传播的特定异常，避免层层包装继续放大开销。
- 在构造映射前正确建立深度计数，并保证清理。
- 对派生映射继承深度限制建立明确规则。
- 将构造路径、继承路径、动态或嵌套对象图纳入回归测试。[R35][R36]

但该项目更改了代码命名空间、程序集名及签名，最新发行还改变了目标框架和部分公开行为。已有 `AutoMapper.IMapper` 消费方与官方 Collection 不能仅通过换一个 NuGet 引用就获得同一类型身份。[R34]

它的迁移说明也记录了正常行为差异，例如部分条件判断收到的值、计划构建异常的包装等。对本项目要求的存量兼容，这些都需要单独处理，而不能因为安全设计较完整就直接接受。[R34]

该项目于 2026 年 11 月创建，观察时间很短。15.0.0 的 GitHub 发布时间为 2026-11-19 21:25 UTC，对应北京时间 11 月 20 日。当前证据不足以称其已证明长期维护稳定性。[R49]

**测试证据也应准确描述：** 已提交的深度图标准测试使用同进程的小栈线程；不能把它写成已经具有完整逐案例子进程回归套件。本项目可以将更严格的子进程隔离作为新增验收要求。[R38]

**建议借鉴：** 逐路径安全设计、异常传播方式、深度与上下文清理测试。  
**不建议直接采用：** 当前整包替换，或退回早于相关修复的 preview 版本以回避命名变化。

### 5.5 另外两个项目为什么只作补充参考

**Klausmd5/AutoMapper** 提供 `Klausmd5.AutoMapperLegacy`，公开记录包含 3 月问题的修补，但目标框架等条件与原始 14 基线不同，持续维护和 11 月完整修复的证据不足。[R39][R40]

**zgabi/AutoMapper** 提供 `zgabi.AutoMapper`，可作为小范围旧线补丁参考。源码中的 PackageId 与实际发行包名之间也应核对打包方式，不能仅凭仓库存在便推断发行物可追溯性已经满足要求。[R41][R42]

两者均不应仅因为变更少，就自动被判断为更安全或更兼容。

### 5.6 最终取舍

推荐的组合不是同时依赖三个 fork，而是：

- 以原始 MIT 14 固定标签作为自己的来源基线。
- 从 MagicMapper 学习兼容发行和迁移表达。
- 从 AutoMapperMIT 学习实际扩展依赖的整理方式。
- 从 ForkForward 学习安全设计及对应测试思路。
- 逐项筛选、审查和实现必要变更，保持自己的补丁集合尽可能小。

是否直接复用某个补丁，要在来源许可与兼容性审查后决定。

---

## 六、新版 abp.io 的做法，对本项目意味着什么？

现代 ABP 与经典 ASP.NET Boilerplate 是不同的代码与模块体系。其路线可以作为决策参考，不能直接证明经典系统迁移后的行为等价。

在本次核实的现代 ABP 11.0.0 中，可以看到三条并存路径：[R18][R19][R48]

| 路径 | 方向 | 对当前项目的意义 |
| --- | --- | --- |
| Mapperly | 新版本默认模块与模板向源码生成映射迁移 | 可参考其减少框架依赖的长期思路；不满足本次存量行为保留目标 |
| 旧 AutoMapper 适配 | 保留 AutoMapper 14，并提供深度等缓解措施 | 能延续旧使用方式，但缓解措施不等于完整解决所有后续公告 |
| Lucky Penny AutoMapper 适配 | 支持新的许可版本；11.0.0 对应 16.3.0 | 表明官方升级路线可保留，但用户必须处理相应许可与迁移 |

ABP 团队公开讨论过保留兼容入口、支持新版本与调整默认映射器，并没有选择自己维护一个 AutoMapper 引擎 fork。[R20][R50]

对你最有价值的经验是：**把映射抽象、具体引擎、引擎升级与应用迁移分开管理。** 但在已经确认的“完整保留存量 AutoMapper 行为”要求下，本次文档不把 Mapperly 迁移作为替代方案，也不把新增抽象层作为发布维护版的前置工程。

---

## 七、建议维护什么，第一版不宜扩大到什么程度？

### 7.1 最小依赖范围

建议先确定以下三部分：

| 层级 | 拟议 NuGet PackageId，仅为命名示例 | 代码与程序集要求 |
| --- | --- | --- |
| 映射引擎 | `Du.AutoMapper` | 保留现有 `AutoMapper.*` 类型；保留 `AutoMapper` AssemblyName 的兼容目标 |
| 集合扩展 | `Du.AutoMapper.Collection` | 保留原有类型及 `AutoMapper.Collection` AssemblyName；改为依赖维护版引擎 |
| 经典 ABP 适配 | `Du.Abp.AutoMapper` | `Abp` / `Abp.*` 不变；保留 `Abp.AutoMapper` AssemblyName 的兼容目标 |

这些是待实施的命名建议，尚未注册、创建或发布任何新包。

Collection 11 的固定源码和许可可以作为该层审查的起点。[R45][R52]

只在实际消费项目使用时，再纳入：

- `AutoMapper.Extensions.ExpressionMapping`。
- `AutoMapper.Collection.EntityFrameworkCore`。
- EF6、LinqToSQL、Data、EnumMapping 等其他扩展。

例如，ExpressionMapping 8 的依赖范围面向 AutoMapper 14；Collection.EntityFrameworkCore 11 又依赖相应 Collection、ExpressionMapping 与 EF Core 版本。是否接管这些扩展，应由实际依赖图决定。[R46][R47]

### 7.2 包名、程序集名、强名称、版本必须分开管理

| 项目 | 建议原则 |
| --- | --- |
| PackageId | 可使用 `Du.` 区分发行者；所有依赖引用需保持闭合 |
| Namespace | 保留既有公共类型名称；`Abp.*` 是明确硬约束 |
| AssemblyName | 以兼容为目标保留，特别注意反射加载与已编译消费者 |
| 强名称与公钥 | 核对实际发布 DLL；不要只检查项目文件 |
| AssemblyVersion | 单独制定兼容策略，不未经分析承诺永久冻结 |
| NuGet 版本 | 使用清晰的维护版本规则，并记录对应上游基线 |
| 来源标识 | 保留版权、许可、仓库、提交、构建及补丁来源信息 |

现代 .NET 与 .NET Framework 对强名称、加载和绑定的处理存在差异。更换公钥不等于所有现代 .NET 应用必然失败，但也不能据此放弃验证已编译插件、反射加载和旧框架消费者。[R44]

### 7.3 第一版维护范围建议

首个维护版以安全修复和发行可用为中心：

- 处理三则公告对应的必要路径。
- 保留原有正常映射语义。
- 修正 NuGet 依赖闭包，避免混入原包或冲突 DLL。
- 补足实际消费项目需要的启动、集合和投影回归。
- 提供来源清单、兼容说明、变更记录及安全台账。

暂不默认承接新映射功能、全面改名、全生态扩展、所有历史 .NET 版本、Native AOT 或框架内部重构。新增支持应有独立需求和维护预算。

---

## 八、如何验收“完整保留 AutoMapper 行为”？

建议把它写成可执行的兼容合同。参照物应是生产实际使用的原版及其配置，不能仅以“可以编译”或“上游单元测试通过”作为验收标准。

### 8.1 必须验证的层次

| 验收层 | 重点场景 | 通过标准 |
| --- | --- | --- |
| 包还原 | 直接与传递引用、中央包管理、锁文件、发布资产 | 依赖闭包明确；无意外原包回流或同名 DLL 冲突 |
| 类型与加载 | 公共 API、程序集身份、反射、预编译插件 | 约定支持的消费者可以按原调用方式使用 |
| ABP 启动 | 模块依赖、配置器、属性扫描、Castle 解析、静态兼容入口 | 启动与依赖解析符合原有约定 |
| 对象映射 | Profile、构造参数、反向映射、继承、泛型、条件、转换器、解析器、空值 | 正常业务输出和可观察副作用与基线一致 |
| 集合更新 | 按键匹配、新增、删除、原对象更新、集合实例、跟踪实体 | 原有集合与对象身份语义得到保留 |
| 查询投影 | `ProjectTo`、表达式映射、真实 EF Provider、分页和关联 | 生成查询可翻译，结果与关键 SQL 行为符合基线 |
| 运行状态 | 复用、并发、异常后再次映射、上下文清理 | 无状态污染、泄漏或并发回归 |
| 安全例外 | 深层构造、继承、动态或字典、转换器、混合集合 | 子进程不因目标递归路径崩溃；失败受控且有记录 |

业务测试应来自实际项目的 Profile、DTO、实体和查询，而不是只为新实现编写一个相同逻辑的镜像测试。

### 8.2 推荐的对照方法

1. 固定生产基线、代表性输入和真实配置。
2. 原版与维护版在隔离进程中运行同一组业务场景。
3. 对比值、空值、集合顺序、对象引用身份、异常类型、数据库跟踪状态及查询结果。
4. 将每个差异分类为缺陷、安全例外或经确认的变更。
5. 只有已说明并验收的差异，才进入发行说明。

正常业务兼容没有通用的一次性证明。最终需要对明确的消费项目、框架版本和映射配置给出通过结果。

### 8.3 平台与测试范围

在计划支持的 Windows、Linux、macOS 组合上执行实际 .NET 构建和测试。可以使用原生环境，不将 Docker、Kubernetes 或虚拟机作为维护版使用前提。

“原生进程运行”不等于 Native AOT。若没有明确需求和单独验证，首版不应宣传 Native AOT 支持。目标框架升级也应与安全补丁分开审查，避免一次变更叠加过多兼容风险。

---

## 九、实施路线与发布门槛

### 阶段 0：确认生产基线

**工作：** 收集实际项目、依赖还原结果、锁文件、发布资产和运行时程序集身份；列出现用扩展、映射配置和 EF Provider。

**交付：** 一份依赖与行为基线清单。

**通过条件：** 能回答“现在实际运行什么”“哪些调用必须保持”“哪些扩展确实需要维护”。

### 阶段 1：建立固定来源与最小维护仓库

**工作：** 选择原始 MIT 14 固定提交；保留许可证和历史；建立明确的补丁与发布分支；确定候选 PackageId、程序集策略及最小依赖闭包。

**交付：** 可构建的基线、来源说明、包关系清单、兼容合同。

**通过条件：** 尚未引入安全修复时，基线可以复现既有消费方式；打包不会意外拉入重复引擎。

### 阶段 2：实现并验证安全补丁

**工作：** 为三则公告建立逐路径用例；选择可审计的实现；验证深度计数、栈保护、异常传播与上下文清理。

**交付：** 小规模补丁集合、安全台账、子进程回归结果。

**通过条件：** 已知路径得到处理；正常映射回归通过；所有行为变化有说明。来源不清楚的代码不得以“先合并再补手续”处理。

### 阶段 3：验证真实消费项目

**工作：** 在真实经典 ABP 应用中执行模块启动、对象映射、Collection 按键更新、ProjectTo 与真实数据库 Provider 回归。

**交付：** 兼容矩阵、差异清单、已知限制。

**通过条件：** 用户约定支持的项目通过；尚未验证的版本和场景不被宣传为已支持。

### 阶段 4：预发布与正式发行

**工作：** 先生成可审查的预发布包，核对 DLL、PDB、Source Link、依赖、版权许可及构建来源；建立回退办法后再正式发布。

**交付：** 包、变更记录、迁移说明、来源与安全说明、支持范围。

**通过条件：** 发布包与验收的源码提交一致；安装后实际依赖图符合预期；发布说明清楚写明安全例外与限制。

本路线不预设已经批准具体远程仓库变更或 NuGet 发布；当前交付只包括本文件。

---

## 十、长期维护规则：让发行工作可以持续

### 10.1 每次发布都必须回答的问题

- 对应哪个上游 MIT 基线和哪些维护提交？
- 改变了哪些 API、程序集身份或正常业务行为？
- 哪些安全公告已处理，哪些仍需评估？
- 测试覆盖了哪些真实消费项目和运行环境？
- 所有扩展依赖是否都指向预期维护包？
- 下游如何升级、识别异常并回退？

不要通过修改包名，让安全扫描“没有告警”就宣称问题已经解决。新 PackageId 可能没有原包的公告映射，因此应由自己的安全台账补足这一可见性缺口。

### 10.2 维护范围与责任

建议明确至少一位主维护者和一位可替补的审查者，列明支持版本、问题接收方式、安全报告渠道和停止支持的通知规则。

对新增功能采取谨慎准入：需要明确消费者、兼容收益和长期成本。维护线优先保证已有行为、安全响应、可重复发行和依赖关系可追溯。

### 10.3 不应写进宣传材料的承诺

在证据不足时，不使用以下表述：

- “100% 与所有 AutoMapper 14 应用二进制兼容”。
- “已修复所有安全问题”。
- “保持原 DLL 名称，因此无需任何验证”。
- “使用 MIT fork，下游任何发行方式都自动合规”。
- “支持所有 .NET、所有平台和 Native AOT”。
- “某公司已经采用，所以当前版本一定适合你的生产系统”。

可以改为明确的可验证声明，例如：“在列明的项目与运行环境中通过了指定兼容用例；已处理本文列出的公告；已知差异与未覆盖范围见发行说明。”

---

## 十一、建议记录的决策与未决事项

### 建议记录为本项目原则

1. `Abp` / `Abp.*` 命名空间不变，`Du.` 仅用于 NuGet 包名。
2. 存量正常业务映射行为是兼容基线；安全修复例外单独记录。
3. 以原始 MIT AutoMapper 14 为优先评估的维护来源。
4. 先覆盖 Core、实际使用的 Collection 及经典 ABP 适配器。
5. 不直接整包引入存在明显命名或行为差异的候选。
6. 每个安全修复都有来源、测试、发布覆盖与兼容影响记录。
7. 不因本模块调研而阻塞 Parquet 首包。

### 实施前仍需补齐

- 生产实际解析和加载的 AutoMapper、Collection 及其他扩展版本。
- 真实业务中构造映射、继承、动态对象、转换器、集合更新和 ProjectTo 的使用范围。
- 候选发布包的独立二进制身份与打包来源核验。
- 维护线的签名和程序集版本策略。
- 补丁许可与贡献来源的完整审核。
- 实际支持的 .NET 版本、操作系统、数据库 Provider 及回归项目。
- 主维护、替补审查与安全响应的投入能力。

**当前建议是建立可验证、范围受控的 AutoMapper 14 维护方案；当前尚未完成代码实现、运行测试或生产验收。**

---

## 参考资料

以下均为公开一手来源。仓库 README、在线文档、NuGet 页面和维护者声明可能继续变化；涉及关键代码判断时，优先采用已列出的固定版本链接。

### 经典 ABP 与依赖关系

- [R01：经典 ABP v10.5.1 — Abp.AutoMapper.csproj][R01]
- [R02：Microsoft — NuGet 版本范围规则][R02]
- [R03：经典 ABP v10.5.1 — AbpAutoMapperModule][R03]
- [R04：经典 ABP v10.5.1 — AutoMapperConfigurationExtensions][R04]
- [R05：经典 ABP v10.5.1 — IObjectMapper][R05]
- [R06：NuGet — AutoMapper.Collection 11.0.0][R06]
- [R07：NuGet — AutoMapper.Collection 12.0.0][R07]
- [R08：NuGet — AutoMapper.Collection 13.0.0][R08]
- [R43：Microsoft — NuGet 依赖解析][R43]
- [R44：Microsoft — .NET 强名称指导][R44]
- [R45：AutoMapper.Collection v11.0.0 — LICENSE][R45]
- [R46：NuGet — AutoMapper.Extensions.ExpressionMapping 8.0.0][R46]
- [R47：NuGet — AutoMapper.Collection.EntityFrameworkCore 11.0.0][R47]
- [R51：AutoMapper v14.0.0 — 项目与签名配置][R51]
- [R52：AutoMapper.Collection v11.0.0 — 项目配置][R52]

### 安全与许可

- [R09：GHSA-rvv3-g6hj-g44x / CVE-2026-32933][R09]
- [R10：GHSA-6vhm-j9h7-f9gh / CVE-2026-128082][R10]
- [R11：GHSA-gpwp-5797-mjff / CVE-2026-128081][R11]
- [R12：AutoMapper v15.1.4 — 官方发布说明][R12]
- [R13：AutoMapper v14.0.0 — MIT 许可证][R13]
- [R14：AutoMapper v15.1.4 — 许可证][R14]
- [R15：Lucky Penny Software — FAQ][R15]
- [R16：Lucky Penny Software — 当前许可协议][R16]
- [R17：AutoMapper — 15.0 升级指南][R17]

### 社区 fork

- [R21：MagicMapper — 项目说明][R21]
- [R22：NuGet — MagicMapper 14.0.1][R22]
- [R23：MagicMapper v14.0.1 — TypeMapPlanBuilder][R23]
- [R24：MagicMapper v14.0.1 — Mapper][R24]
- [R25：Veeam — 采用 MagicMapper 的产品更新说明][R25]
- [R26：NuGet — MagicMapper.Collection][R26]
- [R27：AutoMapperMIT — 项目与扩展说明][R27]
- [R28：AutoMapperMIT — 14.0.3 发布][R28]
- [R29：AutoMapperMIT 14.0.3 — TypeMapPlanBuilder][R29]
- [R30：AutoMapperMIT 14.0.3 — Mapper][R30]
- [R31：AutoMapperMIT 14.0.3 — Directory.Build.props][R31]
- [R32：AutoMapperMIT Issue #18 — 三则公告覆盖询问][R32]
- [R33：AutoMapper 官方讨论 — 社区维护者关于 fork 范围的说明][R33]
- [R34：ForkForward v15.0.0 — 从 AutoMapper 14 迁移][R34]
- [R35：ForkForward v15.0.0 — 两则 11 月公告的处理说明][R35]
- [R36：ForkForward v15.0.0 — CVE-2026-32933 处理说明][R36]
- [R37：NuGet — ForkForward.Mapper 15.0.0][R37]
- [R38：ForkForward v15.0.0 — 深度对象图测试][R38]
- [R39：Klausmd5/AutoMapper — 仓库][R39]
- [R40：NuGet — Klausmd5.AutoMapperLegacy][R40]
- [R41：zgabi/AutoMapper — 仓库][R41]
- [R42：NuGet — zgabi.AutoMapper 14.0.0][R42]
- [R49：ForkForward — v15.0.0 发布][R49]

### 现代 ABP 的处理方式

- [R18：ABP 11.0.0 — 中央包版本][R18]
- [R19：ABP 11.0 — 对象映射与安全说明][R19]
- [R20：ABP Issue #23243 — 映射器路线讨论][R20]
- [R48：ABP 11.0.0 — Lucky Penny AutoMapper 适配器依赖][R48]
- [R50：ABP Issue #22582 — 是否 fork AutoMapper 的讨论][R50]

[R01]: https://github.com/aspnetboilerplate/aspnetboilerplate/blob/v10.5.1/src/Abp.AutoMapper/Abp.AutoMapper.csproj
[R02]: https://learn.microsoft.com/en-us/nuget/concepts/package-versioning#version-ranges
[R03]: https://github.com/aspnetboilerplate/aspnetboilerplate/blob/v10.5.1/src/Abp.AutoMapper/AutoMapper/AbpAutoMapperModule.cs
[R04]: https://github.com/aspnetboilerplate/aspnetboilerplate/blob/v10.5.1/src/Abp.AutoMapper/AutoMapper/AutoMapperConfigurationExtensions.cs
[R05]: https://github.com/aspnetboilerplate/aspnetboilerplate/blob/v10.5.1/src/Abp/ObjectMapping/IObjectMapper.cs
[R06]: https://www.nuget.org/packages/AutoMapper.Collection/11.0.0
[R07]: https://www.nuget.org/packages/AutoMapper.Collection/12.0.0
[R08]: https://www.nuget.org/packages/AutoMapper.Collection/13.0.0
[R09]: https://github.com/advisories/GHSA-rvv3-g6hj-g44x
[R10]: https://github.com/advisories/GHSA-6vhm-j9h7-f9gh
[R11]: https://github.com/advisories/GHSA-gpwp-5797-mjff
[R12]: https://github.com/LuckyPennySoftware/AutoMapper/releases/tag/v15.1.4
[R13]: https://github.com/LuckyPennySoftware/AutoMapper/blob/v14.0.0/LICENSE.txt
[R14]: https://github.com/LuckyPennySoftware/AutoMapper/blob/v15.1.4/LICENSE.md
[R15]: https://luckypennysoftware.com/faq
[R16]: https://luckypennysoftware.com/license
[R17]: https://docs.automapper.io/en/stable/15.0-Upgrade-Guide.html
[R18]: https://github.com/abpframework/abp/blob/11.0.0/Directory.Packages.props
[R19]: https://abp.io/docs/11.0/framework/infrastructure/object-to-object-mapping
[R20]: https://github.com/abpframework/abp/issues/23243
[R21]: https://github.com/NET-Sorcery/MagicMapper/blob/main/README.md
[R22]: https://www.nuget.org/packages/MagicMapper/14.0.1
[R23]: https://github.com/NET-Sorcery/MagicMapper/blob/v14.0.1/src/AutoMapper/Execution/TypeMapPlanBuilder.cs
[R24]: https://github.com/NET-Sorcery/MagicMapper/blob/v14.0.1/src/AutoMapper/Mapper.cs
[R25]: https://www.veeam.com/kb4925
[R26]: https://www.nuget.org/packages/MagicMapper.Collection
[R27]: https://github.com/Shane32/AutoMapperMIT/blob/master/README.md
[R28]: https://github.com/Shane32/AutoMapperMIT/releases/tag/14.0.3
[R29]: https://github.com/Shane32/AutoMapperMIT/blob/14.0.3/src/AutoMapper/Execution/TypeMapPlanBuilder.cs
[R30]: https://github.com/Shane32/AutoMapperMIT/blob/14.0.3/src/AutoMapper/Mapper.cs
[R31]: https://github.com/Shane32/AutoMapperMIT/blob/14.0.3/Directory.Build.props
[R32]: https://github.com/Shane32/AutoMapperMIT/issues/18
[R33]: https://github.com/LuckyPennySoftware/AutoMapper/discussions/4624
[R34]: https://github.com/ForkForward/dotnet-mapper/blob/v15.0.0/docs/source/Moving-from-AutoMapper-14.md
[R35]: https://github.com/ForkForward/dotnet-mapper/blob/v15.0.0/docs/security/GHSA-6vhm-j9h7-f9gh-and-GHSA-gpwp-5797-mjff.md
[R36]: https://github.com/ForkForward/dotnet-mapper/blob/v15.0.0/docs/security/CVE-2026-32933.md
[R37]: https://www.nuget.org/packages/ForkForward.Mapper/15.0.0
[R38]: https://github.com/ForkForward/dotnet-mapper/blob/v15.0.0/src/UnitTests/DeeplyNestedSourceGraphs.cs
[R39]: https://github.com/Klausmd5/AutoMapper
[R40]: https://www.nuget.org/packages/Klausmd5.AutoMapperLegacy
[R41]: https://github.com/zgabi/AutoMapper
[R42]: https://www.nuget.org/packages/zgabi.AutoMapper/14.0.0
[R43]: https://learn.microsoft.com/en-us/nuget/concepts/dependency-resolution
[R44]: https://learn.microsoft.com/en-us/dotnet/standard/library-guidance/strong-naming
[R45]: https://github.com/AutoMapper/AutoMapper.Collection/blob/v11.0.0/LICENSE
[R46]: https://www.nuget.org/packages/AutoMapper.Extensions.ExpressionMapping/8.0.0
[R47]: https://www.nuget.org/packages/AutoMapper.Collection.EntityFrameworkCore/11.0.0
[R48]: https://github.com/abpframework/abp/blob/11.0.0/framework/src/Volo.Abp.LuckyPenny.AutoMapper/Volo.Abp.LuckyPenny.AutoMapper.csproj
[R49]: https://github.com/ForkForward/dotnet-mapper/releases/tag/v15.0.0
[R50]: https://github.com/abpframework/abp/issues/22582
[R51]: https://github.com/LuckyPennySoftware/AutoMapper/blob/v14.0.0/src/AutoMapper/AutoMapper.csproj
[R52]: https://github.com/AutoMapper/AutoMapper.Collection/blob/v11.0.0/src/AutoMapper.Collection/AutoMapper.Collection.csproj

