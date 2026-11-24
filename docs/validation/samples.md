# ASP.NET Boilerplate Samples：Fork 取舍与兼容验收样例规划

## 当前状态（2026-11-24）

主仓已接入 Samples 参考 fork，固定源码为 `e53d60895d354eb066c39d73c9e38c0c133fc69b`。首批候选是 `MultipleDbContextEfCoreDemo` 与 `InterceptionDemo`，维护范围以选定并验收的场景为准。[子模块地址](../../.gitmodules) · [R0 样例参考和状态](../maintenance/release-baseline.json)

已核对多 DbContext 示例的两个上下文注册，以及拦截器示例的同步与异步实现。迁移精选样例、还原和运行候选 `Du.Abp.*` 包、验证多个上下文和拦截器的行为仍待执行。[上下文注册源码][R06] · [拦截器注册源码][R08] · [R0 验证范围](../maintenance/release-baseline.json)

**下文保留原调研建议和当时的实施状态。**

> 更新日期：2026-11-23（Asia/Shanghai）。  
> 对象：aspnetboilerplate/aspnetboilerplate-samples。  
> 适用目标：长期维护和发行经典 ASP.NET Boilerplate，同时控制支持范围。  
> 当前状态：静态调研与实施建议；尚未还原、构建、运行、升级或发布这些样例。

## 一、建议结论

**当前不建议将整个 samples 仓库纳入长期维护承诺。建议保留固定上游参考，首批选择 MultipleDbContextEfCoreDemo 与 InterceptionDemo，改造成维护发行版的专项验收项目。**

如果希望保留完整历史、方便比较上游，可以创建仅供参考的 fork；但应明确哪些目录经过维护、哪些仅为历史材料。是否在 GitHub 上执行 fork，与是否承诺持续维护全部项目，是两个不同决定。

| 处理方式 | 建议 | 目的 |
| --- | --- | --- |
| 保存固定提交链接或源码快照 | 当前即可采用 | 可追溯阅读、比较与提取 |
| fork 整仓，明确标注参考用途 | 可选 | 保留历史与上游对应关系 |
| 精选少量样例并持续验收 | 优先推荐 | 为自己的框架发行提供兼容性证据 |
| 升级整仓并承诺全部样例可运行 | 当前不推荐 | 会显著扩大目标框架、平台、前端及数据库支持范围 |

本仓库是“使用框架的示例集合”，不是 ASP.NET Zero 运行时还必须引入的一项基础库。README 说明各示例在自己的目录中提供说明。[R01]

### 1.1 本次推荐的维护定位

建议将仓库记录为：

> 参考仓库，暂不整仓接管。固定上游提交 e53d60895d354eb066c39d73c9e38c0c133fc69b；首批评估多 DbContext 与拦截器样例，按实际需要增加插件或特定数据库场景。

这里是建议记录的决策，不表示已经创建了远程 fork 或完成了样例移植。

### 1.2 必须继承的用户约束

- 经典 ABP 的 `Abp` / `Abp.*` 命名空间长期保持不变。
- `Du.` 前缀只用于 NuGet PackageId，不进入框架代码命名空间。
- 以存量正常业务行为兼容为核心，不能只证明新代码可以编译。
- 应用原生运行于 Windows、Linux、macOS；不引入 Docker、Kubernetes 或虚拟机前提。
- AutoMapper 兼容验证仍以真实业务配置、集合映射与查询投影为依据。
- 样例接管不阻塞既定 Parquet 首包及其他无关模块的发行。

## 二、核实的源码基线与仓库状态

| 项目 | 本次核实结果 |
| --- | --- |
| 仓库 | `aspnetboilerplate/aspnetboilerplate-samples` |
| 主分支 | `master` |
| 固定 commit | `e53d60895d354eb066c39d73c9e38c0c133fc69b` |
| 该提交日期 | 2024-08-14（北京时间） |
| 该提交主题 | 将 MultipleDbContextEfCoreDemo 更新到 ABP 9.3 |
| 归档状态 | 核实时未标记为 archived |
| 仓库许可证 | MIT |
| 验证范围 | 公开仓库元数据、README、项目与包声明、少量关键源码 |

固定提交与许可证见 [R02][R03]。以上状态截至调研日期，后续分支可能变化。

“未归档”不能作为持续更新所有样例的证明；仓库页面或元数据发生更新时间变化，也不等于主分支新增了代码。本指南以实际提交与项目内容作为依据。

### 2.1 技术基线抽查

| 样例 | 项目源码声明 | 建议用途 |
| --- | --- | --- |
| MultipleDbContextEfCoreDemo | `net8.0`；ABP 9.3.0 | 首批专项集成候选 |
| InterceptionDemo | `net8.0`；ABP 9.0.0 | 首批精简拦截器候选 |
| SimpleTaskSystem | `net8.0`；ABP 9.1.0；Angular `^17.0.4` | 按业务场景参考，避免重复维护完整模板 |
| SimpleTaskSystem-Core | `netcoreapp2.0`；ABP 3.4.0 | 历史参考 |
| PlugInDemo | `.NET Framework 4.6.1`；ABP 3.4.0 | 按需提取插件机制 |
| SqliteDemo | `netcoreapp2.0`；EF Core SQLite 2.0.1 | 有真实 Provider 需求时再处理 |
| AbpWpfDemo | `.NET Framework 4.6.1`；ABP 2.2.2 | 不纳入首批跨平台维护范围 |
| AbpCoreEf7JsonColumnDemo | `net7.0`；EF Core SQL Server 7.0.0 | 使用 JSON 列时再参考 |

来源：[R04][R07][R09][R10][R11][R12][R13][R14][R17]。

这些都是源码声明，**不是实际还原或运行结果**。本次没有证明对应样例可在当前 SDK、数据库和操作系统上直接运行，也没有仅凭旧版本号认定某个具体漏洞。

目录名称也不能作为新旧判断依据：本次快照中的 `SimpleTaskSystem` 已使用 .NET 8，而名称含 Core 的 `SimpleTaskSystem-Core` 仍是 .NET Core 2.0。[R09][R11]

## 三、为什么不优先维护整个仓库？

### 3.1 它不构成新增运行时依赖

框架和适配器被应用消费，samples 则展示怎样消费框架。维护型 fork 的首要责任是发行包、依赖关系与业务兼容，而不是让所有历史示例同时跟上新版本。

这个仓库可以提供场景和代码参考，但没有必要先接管整个仓库，才能发布 `Du.Abp.*`。

### 3.2 各目录不是统一升级的一套产品

抽查显示，样例跨越多个 .NET、ABP、EF 与前端版本。升级其中一个目录，不代表其他目录已经兼容；也不能简单统一所有版本号后就宣布完成。

整仓维护可能涉及：

- 旧式与现代项目系统。
- 不同的认证、宿主与依赖注入接入方式。
- 不同数据库 Provider 与迁移策略。
- 多套前端依赖、静态资源和界面。
- 与当前平台目标不一致的桌面或旧 Web 技术。

这属于根据已核实版本差异作出的工程判断，不是对每个目录都完成了升级成本估算。

### 3.3 示例展示与验收测试的职责不同

多 DbContext 的 README 展示两个上下文各自的迁移及 Migrator 使用方式。[R05]

但“有一个双 DbContext 示例”并不证明以下事项已经验证：

- 仓储总能解析到正确上下文。
- 异常后能够按约定回滚。
- 两个上下文共享事务时具备预期原子性。
- 租户、连接与工作单元不会互相污染。
- 新发行包的程序集和依赖关系仍然兼容。

需要把这些要求写成针对真实承诺的用例。测试应证明约定行为，不应只重复实现细节。

### 3.4 完整样例可能与启动模板重复

`SimpleTaskSystem` 自带后端和 Angular 应用，其依赖仍有自己的版本组合。[R09][R10]

如果只是验证启动、认证、基础 CRUD 和前后端接线，已有的 `module-zero-core-template` 更适合承担统一应用基线。samples 应补充专项能力，减少多套完整后台同时维护的负担。

## 四、首批候选一：MultipleDbContextEfCoreDemo

### 4.1 已确认的参考价值

该示例的 Core 项目声明 .NET 8、ABP 9.3.0。EF 模块注册了两个 DbContext，分别处理已有连接与连接字符串两条配置路径；README 描述了分别建立迁移及运行 Migrator 的流程。[R04][R05][R06]

这些内容很适合转成框架集成回归的起点。

### 4.2 建议保留的内容

- 两个上下文及其必要实体。
- 各自仓储与依赖注入关系。
- 连接选择与配置。
- 两套迁移及必要种子数据。
- 能够展示读取、写入与失败情况的最小应用入口。

完整管理后台不是首轮验收的必要条件。可以保留有用界面，也可以将核心逻辑接入精简宿主，以减少无关前端维护。

### 4.3 建议新增的验收用例

| 编号 | 场景 | 要证明的结果 |
| --- | --- | --- |
| DB-01 | 两个 DbContext 注册与解析 | 各实体、仓储和上下文关联正确 |
| DB-02 | 连接字符串配置 | 使用预期数据库与连接 |
| DB-03 | 已有连接接入 | 按约定复用连接，并正确处理其生命周期 |
| DB-04 | 两套迁移与初始化 | 迁移作用于正确上下文，重复初始化符合预期 |
| DB-05 | 正常提交与异常回滚 | 数据结果符合明确的工作单元边界 |
| DB-06 | 如果承诺跨上下文事务 | 在选定 Provider 与配置下，验证所承诺的原子性 |
| DB-07 | 如果启用多租户与数据过滤 | 查询和写入保持目标应用的隔离规则 |

DB-05 至 DB-07 是建议补充的要求。**现有样例与本次调研均没有证明所有这些行为已经成立。**

应使用实际支持的数据库 Provider 验证相应行为；将全部测试改成内存数据库，不能替代对真实连接、迁移和事务的验证。

### 4.4 首轮验收边界

首轮只承诺一个已选定的 .NET 与数据库组合。确认价值后，再扩大版本或 Provider 范围。

应用应在目标操作系统原生运行；数据库使用符合实际部署方式的原生服务或现有测试实例。不要为了跑这个样例额外引入容器前提。

## 五、首批候选二：InterceptionDemo

### 5.1 已确认的参考价值

Core 项目声明 .NET 8、ABP 9.0.0。关键注册器监听 Castle 的组件注册事件，筛选 `IApplicationService` 实现，并添加 `AbpAsyncDeterminationInterceptor` 对应的拦截器。[R07][R08]

参考价值主要集中在少量拦截器与注册代码，适合迁入精简测试宿主。

### 5.2 建议保留的内容

- 拦截器注册过程。
- 用于展示同步与异步调用的最小应用服务。
- 能检查执行顺序、返回值和异常的记录方式。
- 当前维护版所需的依赖注入与模块启动代码。

不要因为原目录来自完整模板，就把其中的账户页面、主题及所有前端依赖一起升级。

### 5.3 建议验收用例

| 编号 | 场景 | 要证明的结果 |
| --- | --- | --- |
| INT-01 | 服务注册 | 目标服务得到预期拦截，非目标服务符合约定 |
| INT-02 | 同步调用 | 返回值和前后执行顺序正确 |
| INT-03 | 返回 Task | 异步完成与后置动作顺序正确 |
| INT-04 | 返回 Task&lt;T&gt; | 结果正确传播，无额外阻塞 |
| INT-05 | 同步或异步异常 | 异常按约定传播，必要清理仍执行 |
| INT-06 | 取消路径 | 如果接口支持取消，取消行为符合约定 |
| INT-07 | 与工作单元或审计组合 | 多个实际启用的拦截器按预期协同 |
| INT-08 | 并发请求 | 不共享或污染应属于单次调用的状态 |

这张表是维护版拟议的验收范围。不能把示例代码中存在异步拦截器，直接写成上述所有场景已经通过。

## 六、其他样例怎样取舍？

### 6.1 PlugInDemo：按需重建现代宿主

旧样例采用 `Global.asax` / `AbpWebApplication`，通过插件目录加载模块；插件项目目标为 .NET Framework 4.6.1，并使用 Windows `copy /Y` 构建后命令复制 DLL。[R14][R15]

建议保留其机制参考：

- 无直接项目引用时的插件发现。
- 模块初始化与依赖注入。
- 必要的后台服务注册。
- 插件与宿主的程序集加载关系。

如果业务确实使用插件，应在当前支持的 .NET 宿主中重建小型验证项目。先明确“支持哪些已经编译的消费者”，再测试 `Du.Abp.*` 发行包及其程序集能否满足这个范围。

**不承诺所有 ABP 3.4 时代的历史插件都能在新维护版中直接运行。** PackageId、命名空间与程序集身份是不同层面的兼容事项。

### 6.2 SimpleTaskSystem：需要业务场景时再采用

该项目可提供真实业务交互的参考，但自带的 Angular 与后端依赖形成另一套维护组合。[R09][R10]

只有它的任务业务流程能补足当前验收项目时，才有必要提取或升级。基本框架接线已经由启动模板覆盖的部分，可共用现有验收基础。

### 6.3 SqliteDemo、JSON 列等数据库样例：由实际需求决定

`SqliteDemo` 的项目声明仍处于 .NET Core 2.0、EF Core 2.0.1；JSON 列示例则基于 .NET 7、EF Core 7，并展示租户实体的 JSON 元数据。[R12][R16][R17]

它们可以提供思路，但应在真实使用对应数据库能力时再建立现代验证场景。不必为了示例目录齐全而新增多个数据库支持承诺。

这也不改变独立 SQLite 库项目不使用 ABP 的既定边界。

### 6.4 AbpWpfDemo：保留参考，不列入首批支持

该示例采用 .NET Framework 4.6.1，并引用旧版 ABP、WPF 相关程序集。[R13]

本维护计划的首批目标是原生跨 Windows、Linux、macOS 的当前技术路线，因此不将这个历史桌面示例纳入必须升级的项目。若以后需要桌面宿主，可单独参考其框架启动和依赖注入思路。

### 6.5 没有深入检查的目录

仓库还有后台任务、消息、GraphQL、身份认证、其他数据库等示例。本次没有对全部目录完成逐项审计。

不能将本文的抽查结论扩大成“其他样例全部无用”，也不能据此宣称它们已经适合当前生产版本。后续只为实际使用或承诺支持的能力选择样例。

## 七、与现有维护项目的分工

| 对象 | 主要验收职责 |
| --- | --- |
| 经典 ABP 主仓库及其测试 | 框架实现与局部行为 |
| abp-ng2-module 与 Web Resources | Angular 适配、脚本、类型和前后端协议 |
| module-zero-core-template | 完整应用主链：启动、登录、权限、租户、本地化、资源加载 |
| 精选 samples | 多 DbContext、拦截器、插件等专项能力 |
| 真实业务项目 | 实际配置、数据模型、定制行为与端到端结果 |

免费启动模板的定位与源码说明见 [R18]。

这几层应互相补充：

- 样例中出现框架缺陷时，将最小复现与必要回归放到合适位置。
- 不必让每个样例携带一份完整账户管理界面。
- 不要求所有样例随每次无关补丁全量运行；根据变更影响和发布承诺选择验证。
- 最终发行仍要有真实应用消费结果，不能仅依赖演示项目。

AutoMapper 的完整行为兼容，需要使用真实业务 Profile、集合更新和查询投影配置。samples 仓库本身不是这一要求的替代证明。

## 八、如果 fork，怎样保持维护范围可控？

### 8.1 参考 fork 的职责

如果创建整仓 fork，建议在首页明确：

- 固定的上游仓库与提交。
- 仓库主要用途。
- 哪些目录已维护、哪些只是原样保留的历史示例。
- 每个维护样例已验证的版本与环境。
- 上游参考目录不代表对外支持承诺。

无需仅为了表示“已接管”，就给全部历史样例创建升级任务。

### 8.2 精选样例的职责

正式进入维护范围的样例，应同时具备：

1. 明确的框架能力或用户场景。
2. 简短、准确的运行说明。
3. 固定、可还原的依赖组合。
4. 可观察的成功与失败结果。
5. 可自动验证的关键行为。
6. 与当前发行包对应的验收记录。

无法说明它验证了什么、服务于哪个消费者的样例，先保留为参考。

### 8.3 保留来源与许可证

仓库 MIT 许可允许使用和修改，并要求保留相关版权和许可文本。[R03]

提取源码时，建议记录：

| 来源字段 | 内容 |
| --- | --- |
| 上游仓库 | 原始 repository URL |
| 固定提交 | 完整 commit SHA |
| 原始目录或文件 | 被移植内容的位置 |
| 修改范围 | 升级、删除或重构的内容 |
| 许可证 | 保留的版权和许可文本 |
| 对应验收 | 用例、环境与结果 |

复制进样例的其他库、静态资源和依赖仍按各自许可处理；根目录 MIT 不自动覆盖所有第三方内容。

## 九、如何让样例真正验证 Du.Abp 发行包？

### 9.1 增加实际包消费路径

开发时可以使用源码引用，但最终发行验收应增加一条消费**实际打包产物**的路径：

- 使用候选 `Du.Abp.*` 包安装样例。
- 检查直接与传递依赖。
- 检查发布目录中的程序集。
- 在承诺支持的环境中运行。
- 将结果关联到具体源码和包版本。

原因是 NuGet 依赖按包标识与版本关系解析；源码引用跑通，不能证明改名后的包已形成正确的依赖闭包。[R19]

应特别检查：是否仍有其他包拉入原始 `Abp.*`，是否出现同名程序集资产，以及承诺支持的反射或插件加载路径是否正常。

### 9.2 对每个样例声明验证范围

| 维度 | 应记录什么 |
| --- | --- |
| 框架来源 | 上游基线、维护提交、候选包版本 |
| 运行环境 | .NET SDK、目标框架、操作系统 |
| 数据库 | Provider、版本与连接模式 |
| 前端 | 如果存在，记录 Angular、适配器、资源包及锁文件 |
| 用例 | 本样例具体证明的能力 |
| 限制 | 未验证、暂不支持或需额外条件的场景 |

运行成功后，只发布与证据一致的支持声明；不由一个 Provider 的通过结果推断所有 Provider，也不由源码编译成功推断所有已编译插件兼容。

### 9.3 测试数据与可重复执行

样例应使用专用测试数据和清楚的初始化、清理方式。失败后可以再次执行，且不会污染其他样例。

对数据库提交与回滚，应设置可验证的结果；对异步拦截，应观察执行顺序和结束状态。避免以“页面没有报错”作为唯一通过标准。

## 十、实施顺序与下一轮清单

### 10.1 建议顺序

| 阶段 | 工作 | 交付 |
| --- | --- | --- |
| 0：记录来源 | 固定本次上游提交与样例清单 | 来源说明与范围决策 |
| 1：确定目标 | 选择真实消费项目、运行版本与首个 Provider | 小范围支持矩阵 |
| 2：迁入两个候选 | 多 DbContext 与拦截器；保留必要代码 | 能构建的候选验收项目 |
| 3：消费候选包 | 使用实际 Du.Abp 包，核对依赖与程序集 | 包消费检查记录 |
| 4：补充行为验证 | 执行相应数据库、异步和错误路径用例 | 可重复的验收结果 |
| 5：形成维护规则 | 发布运行说明、来源、支持范围与限制 | 精选样例维护入口 |

首批候选数量建议控制为两个。插件或数据库专题应由真实需求触发，而不是为了覆盖原仓库所有目录。

### 10.2 可直接转为待办的清单

- [ ] 将上游固定到 `e53d60895d354eb066c39d73c9e38c0c133fc69b`。
- [ ] 记录当前不承诺整仓维护。
- [ ] 选择首个支持的 .NET、操作系统与数据库组合。
- [ ] 提取多 DbContext 示例必要部分。
- [ ] 提取拦截器示例必要部分。
- [ ] 保留 MIT 版权和来源信息。
- [ ] 消费候选 `Du.Abp.*` 包并检查依赖闭包。
- [ ] 为选定能力补充有明确结果的回归用例。
- [ ] 与启动模板、真实应用分工，减少重复界面维护。
- [ ] 发布说明中区分已验证范围与历史参考目录。

以上全部为拟议待办。当前交付仅为文档，没有执行 fork、代码迁移、构建、运行测试或包发布。

## 十一、决策摘要

**当前定位：参考来源。**

**首批候选：MultipleDbContextEfCoreDemo、InterceptionDemo。**

**按需扩展：插件、实际使用的数据库与业务专题。**

**暂不承诺：整仓升级、所有历史框架版本、全部 UI 与数据库组合。**

对长期维护发行版而言，这个仓库最有价值的部分，是可以转化为清晰兼容证据的少量场景。先让这些场景可靠地消费自己的发行包，再决定是否扩大样例维护范围。


---

## 参考资料

以下源码引用均固定到本次读取的提交；在线文档可能继续更新。

- [R01：仓库 README：示例集合的定位][R01]
- [R02：本次固定提交及更新主题][R02]
- [R03：根目录 MIT LICENSE][R03]
- [R04：多 DbContext 示例：Core 项目][R04]
- [R05：多 DbContext 示例：README 与迁移步骤][R05]
- [R06：多 DbContext 示例：上下文注册实现][R06]
- [R07：拦截器示例：Core 项目][R07]
- [R08：拦截器示例：注册实现][R08]
- [R09：SimpleTaskSystem：Core 项目][R09]
- [R10：SimpleTaskSystem：Angular 依赖][R10]
- [R11：SimpleTaskSystem-Core：旧 Core 项目][R11]
- [R12：SQLite 示例：EF Core 项目][R12]
- [R13：WPF 示例：UI 项目][R13]
- [R14：插件示例：插件项目与构建后事件][R14]
- [R15：插件示例：Global.asax 入口][R15]
- [R16：JSON 列示例：README][R16]
- [R17：JSON 列示例：EF Core 项目][R17]
- [R18：免费启动模板 README：用途与许可证][R18]
- [R19：Microsoft：NuGet 依赖解析][R19]

[R01]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/README.md
[R02]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/commit/e53d60895d354eb066c39d73c9e38c0c133fc69b
[R03]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/LICENSE
[R04]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/MultipleDbContextEfCoreDemo/aspnet-core/src/MultipleDbContextEfCoreDemo.Core/MultipleDbContextEfCoreDemo.Core.csproj
[R05]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/MultipleDbContextEfCoreDemo/README.md
[R06]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/MultipleDbContextEfCoreDemo/aspnet-core/src/MultipleDbContextEfCoreDemo.EntityFrameworkCore/EntityFrameworkCore/MultipleDbContextEfCoreDemoEntityFrameworkModule.cs
[R07]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/InterceptionDemo/aspnet-core/src/InterceptionDemo.Core/InterceptionDemo.Core.csproj
[R08]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/InterceptionDemo/aspnet-core/src/InterceptionDemo.Application/Interceptors/MeasureDurationInterceptorRegistrar.cs
[R09]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/SimpleTaskSystem/aspnet-core/src/SimpleTaskSystem.Core/SimpleTaskSystem.Core.csproj
[R10]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/SimpleTaskSystem/angular/package.json
[R11]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/SimpleTaskSystem-Core/src/Acme.SimpleTaskApp.Core/Acme.SimpleTaskApp.Core.csproj
[R12]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/SqliteDemo/aspnet-core/src/Volo.SqliteDemo.EntityFrameworkCore/Volo.SqliteDemo.EntityFrameworkCore.csproj
[R13]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/AbpWpfDemo/AbpWpfDemo.UI/AbpWpfDemo.UI.csproj
[R14]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/PlugInDemo/PlugIns/DatabaseMaintainer/DatabaseMaintainer.csproj
[R15]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/PlugInDemo/PlugInDemo.Web/Global.asax.cs
[R16]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/AbpCoreEf7JsonColumnDemo/README.md
[R17]: https://github.com/aspnetboilerplate/aspnetboilerplate-samples/blob/e53d60895d354eb066c39d73c9e38c0c133fc69b/AbpCoreEf7JsonColumnDemo/aspnet-core/src/AbpCoreEf7JsonColumnDemo.EntityFrameworkCore/AbpCoreEf7JsonColumnDemo.EntityFrameworkCore.csproj
[R18]: https://github.com/aspnetboilerplate/module-zero-core-template/blob/2e9536872673a7ff1986a19e798c51684d16afe5/README.md
[R19]: https://learn.microsoft.com/en-us/nuget/concepts/dependency-resolution

