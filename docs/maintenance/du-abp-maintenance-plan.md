# Du ASP.NET Boilerplate 主仓改进建议与实施路线

> 文档角色：固定仓库审查结果与后续实施建议。\
> 整理日期：2026-11-24（Asia/Shanghai）。\
> 项目：[`dusdong/du.aspnetboilerplate`](https://github.com/dusdong/du.aspnetboilerplate)。\
> 审查基线：主仓提交 `92a31c2974edcfccb1c00817abeb93a23b16c059`。\
> 证据范围：前两次对话中对固定源码、文档、OpenSpec、基线工具和工作流定义的只读审查。测试数字引用仓库已提交记录，本次文档整理未重新执行构建、测试、发包或修改远程仓库。\
> 配套文档：[Du ASP.NET Boilerplate 文档组织与治理规范](du-abp-documentation-governance.md)。

## 1. 建议结论

继续将主仓定位为**经典 ASP.NET Boilerplate 维护发行版的协调仓**。保留六个子模块、现有文档分组和 OpenSpec，以已完成的 R0 为对照，推进 R1 核心维护和 R2 独立包交付。

下一个明确里程碑是：

> 首批五个 `Du.Abp*` 候选包能够被干净消费者正确还原和运行；命名空间、程序集身份、内部依赖和关键行为由同一套检查验证；结论能够追溯到实际源码提交与最终包产物。

参考 Silo，优先迁移三项工程做法：明确各仓职责、将兼容要求转为可执行检查、将发行结论绑定到精确输入和产物。Silo 的目录名称、Go 工具链和容器化测试设施不作为本项目的实施要求。[S1] [S2]

本项目可继续使用 `abpframework` 作为工作区称呼；对外说明应明确维护对象是**经典 ASP.NET Boilerplate**，并保留 `Abp.*` 代码身份。

## 2. 已确定的约束

| 事项 | 本项目规则 |
| --- | --- |
| 既有代码命名空间 | `Abp` / `Abp.*` 永久保持不变 |
| NuGet 包前缀 | `Du.` 仅用于 NuGet PackageId，不进入代码命名空间 |
| 程序集与根命名空间 | 按各项目原值保留，不随 PackageId 批量改名 |
| 程序集版本 | 与包版本、文件版本分别制定政策；名称不变不等于版本号永久不变 |
| AutoMapper | 存量应用正常业务映射行为必须保留；安全修复的可观察差异需要记录和验证 |
| Angular | 纳入长期支持目标，具体版本组合以实际验收为准 |
| 平台 | Windows、Linux、macOS 原生运行；不引入 Docker、Kubernetes 或虚拟机作为应用运行前提 |
| 维护范围 | 当前围绕经典 ABP 及相关官方开源组件；本路线不将 Abp.Parquet 纳入首批工作 |
| 变更方式 | 必要维护、依赖与运行时升级优先；架构重构单独评估 |

这些约束已在现有路线和 OpenSpec 项目上下文中体现。后续工作应将其转为具体检查，不重复建立相互独立的政策副本。[R2] [R3]

## 3. 当前基线与完成状态

### 3.1 六个固定子模块

以下为审查时主仓 gitlink，不能用各子仓后来变化的默认分支代替。

| 组件 | 固定提交 |
| --- | --- |
| `aspnetboilerplate` | `6c4580c5e7ea41154696c071a53fd200059a768b` |
| `AutoMapper` | `79d10deec5881a617c38e7373f354694044bf83d` |
| `AutoMapper.Collection` | `5301edbc689a9696bdd7c396452669434e75989a` |
| `abp-ng2-module` | `24adbe2222c0965c3957cc6b45a59f8eb1dd6001` |
| `module-zero-core-template` | `2e9536872673a7ff1986a19e798c51684d16afe5` |
| `aspnetboilerplate-samples` | `e53d60895d354eb066c39d73c9e38c0c133fc69b` |

六个 gitlink 与基线记录一致。基线已经区分当前检出、兼容参考及各自用途。[R1] [R4]

### 3.2 R0 已完成的范围

| 范围 | 仓库已记录状态 |
| --- | --- |
| 原版框架来源 | 官方 `v10.5.1` 固定提交 |
| 首批包范围 | 五个框架项目的身份、依赖和 API 基线 |
| 运行环境 | macOS ARM64、.NET SDK 9.0.306、.NET 9 |
| 数据库验证 | EF Core SQLite |
| 三套回归 | 1,313 通过、0 失败、2 跳过 |
| 依赖复验 | 独立还原清单和比较结果 |
| API 复验 | 同 DLL 重复提取、独立重建比较和签名变异比较 |
| OpenSpec | R0 已验收、同步稳定规范并归档 |

测试明细为：`Abp.Tests` 1,105 通过、2 跳过；`Abp.AspNetCore.Tests` 150 通过；`Abp.EntityFrameworkCore.Tests` 58 通过。以上均为已有记录，不代表此次整理重新执行。[R4] [R5] [R8]

### 3.3 后续仍待完成的范围

| 范围 | 审查快照中的状态 |
| --- | --- |
| `Du.Abp*` 实际包身份 | `packageIdStatus: planned` |
| 候选包最小消费者 | R2，pending |
| 完整模板所选入口 | R3，pending |
| Windows、Linux | pending |
| SQLite 以外 Provider | pending |
| AutoMapper、Angular 消费组合 | pending |
| Samples 精选场景 | pending |

R0 已完成其明确范围。上述待办属于后续阶段，不能用原版测试通过推导维护版已发行、全部平台已支持或完整模板已兼容。[R4]

## 4. 仓库结构与职责

### 4.1 保留“协调主仓＋组件子仓”

| 位置 | 应承担的职责 |
| --- | --- |
| 主仓 | 组件提交选择、共同兼容要求、跨仓验证、发行组合与证据 |
| 框架子仓 | 框架与模块实现、组件测试、NuGet 打包 |
| 两个映射子仓 | 引擎与集合映射补丁、组件回归和独立包 |
| Angular 适配器子仓 | 适配层实现、本地构建和包发行 |
| 模板子仓 | 完整应用消费验收，随后按需要发行模板 |
| Samples 子仓 | 固定参考与选定的专项验证 |

修改顺序应为：所属子仓完成实现与必要验证，形成可获取的提交；主仓更新 gitlink，验证新组合并记录影响。主仓已有组件分工可以继续使用。[R6]

保持子仓原有目录布局，有利于比较上游和挑选补丁。未来补丁应记录上游来源、采用理由、受影响行为与回归证据；默认分支的最新提交不自动成为发行输入。

### 4.2 补两个根入口

新增根 `README.md`：说明项目定位、克隆与子模块初始化、当前阶段和文档入口。

新增根 `AGENTS.md`：说明永久约束、修改归属、读取规范、验证方法与文档更新规则。现有 `.agents/skills/` 提供工作流能力，根 AGENTS 提供本项目的具体操作规则。

当前快照没有这两个根入口，也没有主仓 `.github/workflows/`。[R1]

### 4.3 后续按需增加执行目录

| 路径 | 建议用途 |
| --- | --- |
| `eng/` | 新增的通用检查、候选包验证和报告程序 |
| `validation/minimal-backend/` | 真正消费候选 NuGet 包的跨仓验收项目 |
| `.github/workflows/` | 调用共同检查入口的 CI 编排 |
| `artifacts/` | 本地日志、TRX 和候选包等运行产物，加入忽略规则 |

**现有 R0 基线、证据、工具及归档路径先保持稳定。** 后续若确需迁移工具，应作为独立整理处理，同时更新链接并保持历史复验能力。文档组织规则详见配套文档。

## 5. 最高优先级：建立完整、共同的检查入口

### 5.1 已有工具值得保留

`inventory.py` 的 API 比较和还原比较会返回失败退出码；`reproduce.zsh` 已启用错误传播，并汇总测试结果。

依赖清单来自真实 `project.assets.json`，递归访问项目引用，并读取包来源与内容哈希。API 提取器覆盖程序集身份、对外可见类型与成员、参数、返回类型、泛型约束、继承关系和资源名称。[R9] [R10] [R11]

### 5.2 已核实的改进点

| 位置 | 当前行为 | 建议 |
| --- | --- | --- |
| `reproduce.zsh primary` | 还原、构建和三套回归 | 接入身份断言、API 提取与比较、总报告 |
| `reproduce.zsh repeat` | 还原完成后退出 | 明确区分重复还原与完整复跑 |
| API 检查 | 由复验 README 中的命令块组织 | 转为统一入口中的必要步骤 |
| 输入清单 | SHA、包名单和测试名单多处维护 | 从指定结构化记录读取并交叉核对 |
| SDK | 输出 `dotnet --info` | 检查实际 SDK 是否符合此次验证策略 |
| 根仓 CI | 尚无工作流 | 调用同一程序，统一传播失败 |

当前脚本模式尚不能一条命令重演 README 中全部完整复验过程；这不否定已有历史记录。[R5] [R9] [R10]

### 5.3 拟议入口

以下是建议接口，不是仓库已有命令：

```sh
python eng/verify.py --profile r0
```

统一入口应依次完成：

1. 读取基线，核对源码、SDK、工具版本和验证范围。
2. 物化干净源码，使用独立包缓存和明确包源还原。
3. 比较真实依赖图。
4. 构建并运行必要测试。
5. 断言项目身份，提取和比较 API。
6. 输出机器可读总报告、步骤退出码与证据路径。

Python 可复用仓库已有能力，并承担跨平台文件与命令编排。CI 直接调用同一入口，避免在 YAML 中重新实现判断。

R0 严格复验以其声明环境为准；R1 的 .NET 10 迁移应记录和审查合理差异，不能要求新旧依赖图逐字相等。各平台与 Provider 的结果分别记录。

### 5.4 检查、更新基线与证据绑定

日常验证读取已接受基线并输出差异；更新基线应产生独立、可审查的修改，不能在验证过程中自动覆盖预期结果。

总报告至少关联：

- 实际主仓输入与组件提交。
- SDK、操作系统、TFM、适用 RID 和数据库 Provider。
- 提取器版本、输入清单摘要、实际 DLL 摘要。
- 执行步骤、退出码、结果路径。
- 候选包阶段的最终 nupkg 摘要。

`superprojectInputCommit` 指向生成 R0 基线时的输入提交，并不需要等于后来提交证据文档的 HEAD。当前基线也明确记录独立重建 DLL 字节不同而 API 相同；文件摘要负责识别具体产物，API 比较负责判断结构差异，两者分开处理。[R4]

## 6. 将命名和兼容要求落实到实际产物

### 6.1 身份检查

| 对象 | 检查要求 |
| --- | --- |
| PackageId | 按明确映射转换为 `Du.Abp*` |
| AssemblyName | 保留各项目原值 |
| RootNamespace | 保留各项目原值 |
| 代码类型 | 不因包改名将 `Abp.*` 改为 `Du.Abp.*` |
| 公共 API | 对照基线检查类型与成员变化 |
| 资源及反射契约 | 检查资源名、程序集加载字符串等 |
| 内部依赖 | 维护版包正确指向维护版内部包 |
| 版本号 | 分别制定包版本、程序集版本与文件版本政策 |

例如，`Abp.EntityFramework.Common` 的原始 RootNamespace 是 `Abp.EntityFramework`，不能批量统一成 `Abp`。[R4]

ABP 集合映射代码实际使用 `Assembly.Load("AutoMapper.Collection")`。将来即使 NuGet 包改名，也应保留这一运行契约。[R12]

### 6.2 API 清单的证明范围

现有提取器是有价值的 API 结构基线，但未提取 CustomAttributes、类型转发等全部兼容信息；资源主要比较名称。目前变异演练修改的是 JSON 清单中的签名。[R5] [R11]

建议：

- 保留当前清单，明确其证明范围。
- 增加少量真实 DLL 变异夹具，验证“程序集变化—提取—比较”的完整链。
- 对模块初始化、DI、工作单元、EF 查询、序列化和映射行为继续执行消费者回归。
- 对有意改变的 API 或安全边界，记录理由、影响及验收证据。

API 相同不能单独证明完整业务行为相同。

## 7. R2：首批五包和真实消费者

### 7.1 明确首批闭包

| 包 | 主要作用 |
| --- | --- |
| `Du.Abp` | 核心框架 |
| `Du.Abp.Web.Common` | Web 公共依赖 |
| `Du.Abp.AspNetCore` | ASP.NET Core 集成入口 |
| `Du.Abp.EntityFramework.Common` | EF 公共依赖 |
| `Du.Abp.EntityFrameworkCore` | EF Core 集成入口 |

这些是已登记的计划映射，不代表现有源码已经改名或对应包已经发布。[R4]

### 7.2 独立最小消费者

实施 R2 时创建 `validation/minimal-backend/`，直接使用 `Du.Abp.AspNetCore` 和 `Du.Abp.EntityFrameworkCore`，由传递依赖覆盖另外三个包。

通过标准：

1. 使用实际候选 nupkg；五个维护版包来自指定候选源，第三方依赖来自登记包源。
2. 使用 PackageReference，避免框架 ProjectReference 绕过发行物。
3. 检查最终 nuspec 与消费者 project.assets.json。
4. 验证内部框架依赖闭合、程序集来源唯一。
5. 验证候选包内 DLL 与产物证据对应。
6. 启动应用并执行必要的模块、DI、工作单元和数据库行为验证。

现有真实还原图提取能力可以复用，后续需要面向独立消费者扩展。

### 7.3 R3 先选择模板 Web.Host 入口

建议优先使用 Angular 对应的 Web.Host 作为完整模板验收入口。

固定模板仍声明 ABP 10.2.0，并额外使用 AutoMapper、ZeroCore、SignalR、Log4Net 等包；MVC 和测试入口还有其他依赖。应按所选入口计算完整闭包，随后安排相应包维护，不能用五包替换直接宣布整个模板迁移完成。[R4] [R7]

## 8. 组件维护线的具体选择

### 8.1 AutoMapper 与 Collection

| 组件 | 当前 gitlink 源码 | 已选兼容参考 |
| --- | --- | --- |
| AutoMapper | `79d10dee…`；LICENSE.md 指向 RPL-1.5／商业许可 | `bf76a5819e1bad7af7db5382bf0f3a0178048a15`，v14.0.0，MIT |
| Collection | `5301edbc…`；依赖 AutoMapper `[15.0.1,17.0.0)` | `eafbf005becf73f989e1b1c0d52e8699439f837c`，v11.0.0，依赖 `[14.0.0,15.0.0)` |

差异已经由 R0 记录，源码与记录一致。[R4] [R13] [R14] [R15] [R16]

建议从选定参考建立明确维护分支，完成来源审查、补丁和回归后更新主仓 gitlink。候选构建核对实际提交、许可证文件和依赖范围，不能把当前检出产物当作 MIT 14 维护产物。

建立 fork 和选定 MIT 原版都不等于安全修复已完成。后续仍需逐项处理已识别问题，并保留正常映射、对象更新、集合映射与查询投影行为。

映射维护可与首批五包并行；首批五包不包含 Abp.AutoMapper。

### 8.2 Angular 组合

2026-11-28 更新。固定免费模板已用公开适配器和资源包完成 Angular `19.2.1` production 冷构建，公开 R4 和 R5 已用该冻结前端完成角色编辑验收。[公开冷构建](r5-public-angular-rebuild.md#实测结果) · [角色编辑实测](r5-angular-user-role-edit.md)

| 来源 | 声明 |
| --- | --- |
| 主仓适配器 gitlink `24adbe2` | 13.0.0，Angular peer `^21.0.0` |
| Angular 19 适配器实包 | 12.1.0，Angular peer `^19.1.7` |
| 固定免费模板 | 声明 Angular `^19.2.1`、适配器 12.1.0 和资源 `^6.1.0`，锁定 Angular 19.2.1 和资源 6.1.0 |

适配器本地候选已通过编译消费，五项任务已归档，稳定规范已同步。GitHub `main` 已回读交付提交 `fbf3a4740e2a432409e14298ae292f43e6aed88a`。正式升级组合另行评估。[适配器验收](r5-angular19-adapter-package-plan.md#实测结果) · [交付提交](https://github.com/dusdong/du.aspnetboilerplate/commit/fbf3a4740e2a432409e14298ae292f43e6aed88a)

同一固定模板已在 macOS ARM64 同时冻结安装适配器与资源候选，两份包均可追溯至同次 production 输出。对照完整浏览器目录及本轮静态观察通过。验收要求已同步到稳定规范，六项任务已归档。[双包实测与复跑](r5-angular19-package-pair.md) · [稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-固定-angular-19-模板可同时验收两份本地-npm-候选) · [归档任务](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-package-pair/tasks.md)

双包候选和全公开冻结前端已在同一 R5 Web.Host 与专用 SQL 新库实测匿名首次启动。两侧从根路径直接加载 production index，在同一文档内到达空登录表单，匿名初始化与可见文案一致。四项任务已归档。[实测与复跑](r5-angular19-anonymous-bootstrap.md) · [稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-固定-angular-19-模板可对照双包候选的匿名首次启动) · [归档任务](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-anonymous-bootstrap/tasks.md)

组合证据记录 Node、包管理器、锁文件、Angular、适配器及资源包版本、源码提交和实际结果。

### 8.3 Web Resources

2026-11-28，从框架生产 gitlink `7933e71` 的 40 个资源原字节制成 `abp-web-resources 6.1.0` 本地候选，包装源自 `aspnetboilerplate/bower-abp-resources` 固定提交。在 Angular `19.2.1` 免费模板和公开适配器 `12.1.0` 环境中，仅替换资源包即通过冻结安装、声明解析和 production 新构建。浏览器验证了实收全局脚本、`formatString` 返回值与两个 SignalR 静态 URL 的原字节。验收要求已同步到稳定规范，六项任务已归档。候选供本地复验。[Web Resources 实测](r5-angular19-web-resources-plan.md#实测结果) · [稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-固定-angular-19-模板可验收从经典框架-git-制成的资源包) · [归档任务](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-web-resources/tasks.md)

分发 fork 的固定快照、候选包装身份及第七子模块的接入条件见 Angular 指南。`Du.` 前缀只约束 NuGet，npm 包名另行确定。[Web Resources 分发维护登记](../compatibility/angular-ecosystem.md#web-resources-分发维护登记)

### 8.4 Samples

继续将 Samples 作为参考仓与精选验收来源。首批关注多 DbContext 与拦截器场景，按实际实现扩大维护范围；保留完整 fork 不构成整仓全部样例可运行的承诺。[R19]

## 9. CI 与发行证据

### 9.1 分层职责

| 层次 | 负责内容 |
| --- | --- |
| 子仓 CI | 组件构建、测试、打包 |
| 主仓 CI | 选定提交、身份规则、候选包闭包、跨仓消费组合 |
| 发行流程 | 最终输入、产物摘要、验证结果与发布记录 |

根仓已有文件树没有工作流，但子仓存在 CI 定义，不能据此宣称全项目没有 CI。[R1] [R17]

### 9.2 已核实的工作流调整点

- ABP 工作流使用 Windows 和 .NET 9 RC SDK；PR 路径过滤未覆盖 common.props、global.json 等构建输入。R1 应同步更新 SDK 策略和触发范围。[R17]
- 当前 AutoMapper 工作流包含 .NET 10/11、上游 Azure 签名和 Feedz 发布配置；Collection 工作流包含上游 MyGet 发布配置。自己的维护线应明确包名、目标源和发布职责。[R20] [R21]
- 上述结论来自工作流文件，未核实这些任务是否启用或成功运行。
- 复用组件 CI 结果必须绑定主仓实际选择的 SHA，默认分支绿色标记不能代替。
- 三平台支持以对应原生执行结果为准。

### 9.3 每次发行记录什么

生成并长期保留版本专属发行清单：

- 主仓与实际组件提交。
- SDK、系统、TFM、适用 RID 和 Provider。
- 包 ID、版本、最终文件摘要。
- 验证任务、结果与证据。
- 已通过、未执行和已知限制的消费组合。
- 升级和回退说明。

最终结论应对应最终产物。临时 CI 日志可以过期，但支撑正式发行的关键清单与证据需要明确保留策略。

## 10. 文档治理的实施原则

详细规则见[配套治理文档](du-abp-documentation-governance.md)。本路线采用以下一致决定：

1. 根 README 作为用户入口，AGENTS 作为工作入口。
2. 保留现有 maintenance、compatibility、validation 分组。
3. 稳定要求进入 OpenSpec specs；具体任务进入 active change；历史决策保留归档。
4. R0 JSON 和证据继续表达历史事实，后续状态使用新变更和新证据。
5. 五篇指南保留研究日期，更新当前状态说明。
6. 正式 API 基线、规范和设计记录进入 Git；每次运行日志、缓存和包产物分开保存。
7. 根仓自写脚本、文档应明确许可证范围；子仓保留自身许可证与来源。
8. 新增通用工具可放 eng，现有 R0 路径先保持稳定。

## 11. 建议的实施顺序

| 顺序 | 工作包 | 完成标准 |
| --- | --- | --- |
| 1 | 根入口、文档索引与共同检查入口 | 本地与 CI 调用同一程序，能够发现未批准的身份和基线差异 |
| 2 | R1 核心维护 | 按现有路线推进 .NET 10、必要补丁和依赖调整；核心、Web、EF 行为与 R0 有可审查对照 |
| 3 | R2 五包交付 | 实际候选包在干净消费者中还原、启动并通过验证 |
| 4 | 映射与 Angular 组合 | 维护线、集合映射、资源产物和模板 Web.Host 通过实际消费验收 |
| 5 | R4 发行整理 | 最终制品、源码、支持矩阵、升级回退与证据能够逐项关联 |

映射维护和 Angular 准备可与核心主线并行。每个工作包分别形成 OpenSpec change；R0 继续作为已接受的历史对照。

### 首轮最小任务清单

- [ ] 补根 README、AGENTS，完善 docs/README 的导航和权威来源表。
- [ ] 统一五篇指南的角色、日期和当前状态说明。
- [ ] 将现有比较能力接入共同入口，明确重复还原与完整复跑。
- [ ] 将 PackageId、AssemblyName、RootNamespace 和实际类型检查转为断言。
- [ ] 接入根仓 CI，绑定实际组件 SHA。
- [ ] 通过后续 R1/R2 变更交付真实五包消费者。

以上复选框表示拟议工作，不表示本次文档整理已经执行。

## 12. 参考来源

以下仓库链接固定到审查提交；分支和发布状态可能在此后变化。Silo 来源用于工程实践比较，不构成本项目已实现相同能力的证明。

### 主仓与既有文档

- [R1：主仓固定目录][R1]
- [R2：OpenSpec 项目上下文][R2]
- [R3：维护型 fork 路线][R3]
- [R4：R0 维护基线][R4]
- [R5：R0 复验说明][R5]
- [R6：现有文档索引与子模块分工][R6]
- [R7：R0 设计][R7]
- [R8：R0 已完成任务][R8]
- [R18：Angular 生态指南][R18]
- [R19：Samples 规划][R19]

### 工具与组件源码

- [R9：复验脚本][R9]
- [R10：依赖与 API 比较器][R10]
- [R11：API 提取器][R11]
- [R12：Collection 反射加载代码][R12]
- [R13：当前 AutoMapper 许可证][R13]
- [R14：AutoMapper 14 参考项目][R14]
- [R15：当前 Collection 依赖][R15]
- [R16：Collection 11 参考项目][R16]
- [R17：ABP 构建工作流][R17]
- [R20：当前 AutoMapper 工作流][R20]
- [R21：Collection 工作流][R21]

### Silo 工程实践

- [S1：Silo 项目规则][S1]
- [S2：Silo 统一检查入口][S2]

[R1]: https://github.com/dusdong/du.aspnetboilerplate/tree/92a31c2974edcfccb1c00817abeb93a23b16c059
[R2]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/openspec/config.yaml
[R3]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/maintenance/fork-roadmap.md
[R4]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/maintenance/release-baseline.json
[R5]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/maintenance/baseline-evidence/README.md
[R6]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/README.md
[R7]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/openspec/changes/archive/2026-11-24-establish-maintenance-baseline/design.md
[R8]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/openspec/changes/archive/2026-11-24-establish-maintenance-baseline/tasks.md
[R9]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/maintenance/baseline-tools/reproduce.zsh
[R10]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/maintenance/baseline-tools/inventory.py
[R11]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/maintenance/baseline-tools/Program.cs
[R12]: https://github.com/dusdong/aspnetboilerplate/blob/6c4580c5e7ea41154696c071a53fd200059a768b/src/Abp.AutoMapper/AutoMapper/AutoMapperConfigurationExtensions.cs
[R13]: https://github.com/dusdong/AutoMapper/blob/79d10deec5881a617c38e7373f354694044bf83d/LICENSE.md
[R14]: https://github.com/dusdong/AutoMapper/blob/bf76a5819e1bad7af7db5382bf0f3a0178048a15/src/AutoMapper/AutoMapper.csproj
[R15]: https://github.com/dusdong/AutoMapper.Collection/blob/5301edbc689a9696bdd7c396452669434e75989a/src/AutoMapper.Collection/AutoMapper.Collection.csproj
[R16]: https://github.com/dusdong/AutoMapper.Collection/blob/eafbf005becf73f989e1b1c0d52e8699439f837c/src/AutoMapper.Collection/AutoMapper.Collection.csproj
[R17]: https://github.com/dusdong/aspnetboilerplate/blob/6c4580c5e7ea41154696c071a53fd200059a768b/.github/workflows/build-and-test.yml
[R18]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/compatibility/angular-ecosystem.md
[R19]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/validation/samples.md
[R20]: https://github.com/dusdong/AutoMapper/blob/79d10deec5881a617c38e7373f354694044bf83d/.github/workflows/ci.yml
[R21]: https://github.com/dusdong/AutoMapper.Collection/blob/5301edbc689a9696bdd7c396452669434e75989a/.github/workflows/ci.yml
[S1]: https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/AGENTS.md
[S2]: https://github.com/pgsty/silo/blob/d66020003cb20f07c765f71c0a060c9ef986f545/Makefile
