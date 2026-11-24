# Du ASP.NET Boilerplate：文档组织与治理规范建议

> 整理日期：2026-11-24（Asia/Shanghai）。\
> 适用仓库：`dusdong/du.aspnetboilerplate`，经典 ASP.NET Boilerplate 维护发行工作区。\
> 审查基准：主仓固定提交 `92a31c2974edcfccb1c00817abeb93a23b16c059`。\
> 文档角色：根据本轮“文档如何组织”的讨论整理的建议方案，尚不表示已完成仓库调整。\
> 配套文档：[主仓改进建议与实施路线](du-abp-maintenance-plan.md)。本文负责文档结构与更新方式；配套文档负责工程改进、检查与发行顺序。

## 1. 组织目标与总体选择

建议采用“两个根入口、现有三类专题文档、OpenSpec 正式变更、版本化验收证据”的组织方式。保留已经合理的目录与固定链接，让维护者能够区分四件事：项目必须满足什么、当前准备做什么、已经验证了什么、某次发行实际交付了什么。

本项目的长期约束继续有效：既有 `Abp` / `Abp.*` 代码命名空间永久保持不变；`Du.` 只用于 NuGet PackageId，不进入代码命名空间，也不自动成为 npm 命名规则。正常 AutoMapper 业务行为、Angular 支持目标和三平台原生运行要求，仍按已确定的范围推进。文档整理不能改变这些约束。[现有项目上下文][S03]

固定提交中已经有 `docs/maintenance/`、`docs/compatibility/`、`docs/validation/`、五篇专题指南和 R0 的 OpenSpec 规范、归档与证据。这些是本方案的基础。[文档入口][S02] [稳定规范][S04]

## 2. 根入口和目录职责

### 2.1 根目录增加两个入口

| 文件 | 面向读者 | 主要职责 |
| --- | --- | --- |
| `README.md` | 首次进入仓库的人 | 项目定位、协调仓角色、克隆方法、当前阶段、文档入口 |
| `AGENTS.md` | 参与修改的人与自动化助手 | 硬约束、修改归属、规范入口、验证要求、文档更新规则 |

根 README 建议控制在一页左右，说明这里维护的是经典 ASP.NET Boilerplate，源码由子模块承载，主仓负责组合与验收；提供初始化子模块的方法；用一句话说明阶段，再链接详细记录。完整路线和测试结果继续放在各自权威位置。

根 AGENTS 保留醒目的命名约束，并说明哪些变更属于主仓、哪些属于子仓，怎样验证和更新 gitlink。其余规则链接稳定规范和专题指南。已有 `.agents/skills/` 提供工作流能力，根 AGENTS 提供本项目工作入口，两者职责不同。固定提交中尚无这两个根文件。[固定根目录][S01]

现阶段无需再增加独立的根 `STATUS.md`、`CONTRACT.md`、`ROADMAP.md`；现有索引、稳定规范和维护路线已经可以分别承担这些职责。

### 2.2 保留现有三类文档

| 路径 | 回答的问题 | 典型内容 |
| --- | --- | --- |
| `docs/README.md` | 应从哪里阅读，信息以哪里为准 | 按任务导航、组件职责、权威来源表 |
| `docs/maintenance/` | 维护什么、如何推进维护与发行 | 路线、参考研究、基线与复验入口 |
| `docs/compatibility/` | 组件怎样配合，迁移须保留什么 | AutoMapper、Angular 整链兼容说明 |
| `docs/validation/` | 验证什么、怎样执行和判断结果 | 场景选择、验收方法、覆盖范围说明 |

`docs/README.md` 可以按读者任务组织入口：了解维护路线、修改 AutoMapper、验证 Angular、复验 R0、查看当前变更、核对发行结果。每个入口用一两句说明即可，正文继续留在专题中。

### 2.3 后续路径随实际内容出现

| 路径 | 增加时机 | 用途 |
| --- | --- | --- |
| `docs/releases/<version>.md` | 准备候选或正式发行说明时 | 变化、适用组合、迁移、限制、证据入口 |
| `validation/minimal-backend/` | 实施 R2 时 | 真正消费候选 NuGet 包的可执行项目 |
| `eng/` | 实施通用检查程序时 | 跨仓检查、包验证、报告生成程序 |
| `artifacts/` | 工具开始产生运行结果时 | 本地日志、测试结果和候选包，加入忽略规则 |

这些是拟议职责，不代表当前已经存在。先产生真实内容，再建立对应目录；不需要预建一套空的文档站或占位目录。

## 3. 明确信息的权威来源

建议把下表加入 `docs/README.md`，使同一事实只有一个主要维护位置。

| 信息 | 权威来源 | 其他位置怎样使用 |
| --- | --- | --- |
| 子模块仓库地址 | `.gitmodules` | 引用或生成展示 |
| 当前选中的组件提交 | 主仓提交中的 gitlink | 展示时注明主仓提交 |
| 长期、可验收的要求 | `openspec/specs/` | 指南解释，AGENTS 提供入口 |
| 当前变更、任务和验收 | `openspec/changes/<change>/` | 路线图链接对应变更 |
| 历史设计理由 | `openspec/changes/archive/` | 新设计引用当时决定 |
| R0 的来源、身份、环境和结果 | `docs/maintenance/release-baseline.json` | 索引展示摘要并链接 |
| 如何复验 R0 | `docs/maintenance/baseline-evidence/README.md` | 其他页面链接复验手册 |
| 维护方向与专题背景 | 现有五篇指南 | 支持理解、选型和操作 |
| 某次发行交付了什么 | 该版本发行清单与验收证据 | 发行说明概括结论 |

“当前检出”与“历史基线”允许不同。以后子模块向前推进，R0 参考提交和历史测试结果仍然保留。现有 R0 设计已经明确这一划分。[R0 设计][S05]

“支持目标”与“验证结果”也要分开。Angular 和三平台原生运行可以是维护目标；某个具体组合是否通过，需要对应证据。现有 R0 清单明确区分了实际执行结果与 R2、R3 等待验证项目，应继续保持这种表达。[R0 基线][S06]

`openspec/config.yaml` 保持为项目上下文摘要和规范入口。长期要求通过变更进入稳定规范后，同步摘要和指南；发现冲突时依据用户硬约束及已接受规范修正，不能仅凭文件修改时间决定规则。

## 4. 五篇现有指南的处理方式

第一轮保留原文件和主要内容，通过页首状态、章节顺序和链接澄清用途。随后随 R1、R2、R3 的实施逐步增加操作说明。

| 现有文件 | 长期定位 | 当前调整 |
| --- | --- | --- |
| `maintenance/fork-roadmap.md` | 整体维护路线 | 保留阶段目标，具体任务链接 OpenSpec |
| `maintenance/fork-references.md` | 有日期和来源的研究 | 标明证据范围，关联实际采用的变更 |
| `compatibility/automapper.md` | 映射兼容维护指南 | 区分已 fork、已选参考、已修复与已验收 |
| `compatibility/angular-ecosystem.md` | Angular 整条消费链指南 | 维护适配器、资源、模板和后端的组合关系 |
| `validation/samples.md` | 精选场景验收说明 | 区分参考源码与可执行、已验证场景 |

### 4.1 路线图维护阶段，任务清单留在变更中

路线图回答为什么维护、维护范围、R0—R5 各交付什么、当前阶段与下一阶段前提。具体项目改动、任务勾选和运行结果放在对应 change 中，避免两个任务清单逐渐不同步。[现有维护路线][S08]

### 4.2 参考研究保留时间语义

参考研究记录的是某个时点核实的实现、补丁和工程方式。它不承担这些项目今天仍然活跃或可以直接替换生产组件的承诺。实际采用一项实践时，增加实施变更和验证记录链接即可。[参考 fork 研究][S09]

### 4.3 兼容指南逐步增加可执行说明

AutoMapper 与 Angular 指南可以按“当前范围与方案、已验证组合、操作步骤、兼容差异、验证方法、历史研究、参考来源”组织。尚未完成的内容明确保留为计划。

AutoMapper 原文“尚未实施 fork”描述原调研时点。后续页首可补充：已建立参考 fork，维护补丁、候选包和业务行为兼容按对应变更验收。保留原调研日期，不能因仓库创建就改写为维护发行版已经通过。[AutoMapper 指南][S10]

Angular 继续保留一篇综合指南。适配器、Web Resources、模板之间的关系正是其核心价值；各组件自己的开发命令由子仓维护。[Angular 指南][S11]

Samples 文档明确“已保留参考仓、精选场景逐项验收”，不承诺整仓移植或全部样例可运行。[Samples 指南][S12]

## 5. OpenSpec、指南与历史记录如何配合

| 内容 | 位置 | 作用 |
| --- | --- | --- |
| 稳定规范 | `openspec/specs/<capability>/spec.md` | 定义可验收要求 |
| 一次变更 | `openspec/changes/<change>/` | 目的、设计、任务和验收 |
| 操作与维护指南 | `docs/` | 帮助读者理解、执行和排查 |

例如维护 AutoMapper：稳定规范规定必须保留的行为与安全边界；change 记录起始提交、修复方案和验收；指南说明消费者采用哪组包、如何迁移、有哪些差异。

建议每次变更按以下顺序回写：

1. 在 change 中明确范围和验收条件。
2. 实施并取得实际结果。
3. 更新相关指南的操作、组合和限制。
4. 将已接受的长期要求合入稳定规范。
5. 完成校验并归档变更。

归档后的 proposal、design、tasks 保留当时决策和验收语义。下一阶段新建 change，不持续向已验收的 R0 归档追加新计划。现有稳定规范与 R0 归档继续使用。[维护基线规范][S04] [R0 归档][S13]

## 6. 基线、说明与运行产物分层

| 类型 | 例子 | 存放方式 |
| --- | --- | --- |
| 人读说明 | 前置条件、命令、通过标准、限制 | `docs/`，进入 Git |
| 已接受基线 | SHA、包身份、API 清单、依赖清单 | 版本化，进入 Git |
| 正式变更记录 | proposal、design、tasks、spec | `openspec/`，进入 Git |
| 每次运行产物 | 日志、TRX、DLL、nupkg、浏览器 trace | 本地忽略目录或 CI artifacts |
| 发行证据 | 最终摘要、环境、来源、结果索引 | 随发行长期保存 |
| 临时材料 | 草稿、调查中间结果、原始会话记录 | 临时目录 |

### 6.1 R0 路径保持稳定

第一轮保留 `release-baseline.json`、`baseline-evidence/`、`baseline-tools/` 及 R0 归档原路径。这些文件已被复验说明和归档引用。通用工具以后可以放入 `eng/`，但本轮不为目录整齐迁移 R0 工具。[复验手册][S07]

出现第二份正式基线时，再增加按阶段或版本命名的记录，由索引链接新旧位置。R0 的历史结果不随后续进展改写。纠正历史记录中的明确错误时，应说明更正原因和证据。

API JSON 是经过接受的比较基准，有版本管理价值；每次运行的临时 DLL 和完整日志则不必全部提交。正式发行依赖的关键证据需要明确保留方式，不能只留下可能过期的运行链接。

### 6.2 区分说明目录和可执行项目

| 路径 | 内容 |
| --- | --- |
| `docs/validation/` | 为什么验证、怎样执行、如何判断通过 |
| 根 `validation/` | 能够还原、构建和运行的跨仓消费者 |
| 子仓 `test/` 或 `tests/` | 组件内部单元测试与回归 |

因此，验收说明可以先形成；只有对应实现真正执行并留下证据后，才将场景标记为已验证。

## 7. 主仓与子仓的文档边界

| 主题 | 主仓负责 | 子仓负责 |
| --- | --- | --- |
| 定位 | 整个维护发行版的范围 | 组件职责与来源 |
| 构建 | 跨仓验收入口 | 本组件开发与构建命令 |
| 测试 | 版本组合和包消费验收 | 单元测试、组件回归 |
| 兼容 | ABP、映射、前端和模板之间的关系 | 本组件 API、行为和差异 |
| 发行 | 组合、来源和整体支持范围 | 组件打包与发布方式 |
| 上游维护 | 整体选择原则 | 补丁来源和同步记录 |

例如，AutoMapper 与 ABP 的配合放主仓，引擎编译命令放 AutoMapper 子仓；Angular 整链规则放主仓，适配器本地开发放 ng2 子仓；Samples 的维护范围放主仓，具体样例启动说明放样例目录。

子仓 README 增加主仓入口，主仓链接组件说明。保留上游来源和必要开发资料，避免把五篇综合指南复制到每个子仓。

## 8. 轻量写作与更新规则

### 8.1 页首模板与状态维度

可采用以下格式，并按文档性质精简：

```markdown
# 文档标题

> 文档角色：组件维护指南，包含历史研究。
> 适用范围：经典 ASP.NET Boilerplate 维护发行版。
> 调研截至：YYYY-MM-DD。
> 最近状态核对：YYYY-MM-DD。
> 当前实施与验证记录：链接到对应变更及证据。
```

调研截止日与状态核对日分开；调整排版不表示重新核实全部外部资料。

| 状态维度 | 示例 |
| --- | --- |
| 文档状态 | 草案、有效、已被替代、归档 |
| 验证状态 | 仅核对源码、已构建、组件测试通过、包消费通过、应用场景通过 |

生效的规范可以提出尚未完成的目标。文档生效与实现验收是不同事实。

### 8.2 操作章节、命名与链接

操作说明依次给出适用范围、前置条件、执行步骤、通过标准、证据位置、限制及失败处理。命令注明运行目录，说明验证的是源码、候选包还是完整应用。

沿用中文正文、英文小写连字符文件名。同仓引用使用相对链接；跨仓研究证据优先使用固定提交链接。OpenSpec 的固定标题、关键字和任务格式按工具约定保留。移动文件时同步检查引用；必要时在旧路径保留短迁移说明。

### 8.3 与代码变更一起更新

建议在 AGENTS 中加入：修改影响支持范围、包身份、操作命令、兼容行为或验收结论时，同一次变更更新对应文档和证据入口。

文档检查首先覆盖内部链接、证据引用和 OpenSpec 校验。外部链接按变更需要或定期复核。验证程序只读已接受基线，基线更新应产生可审查差异。

## 9. 第一轮最小实施清单

| 顺序 | 调整 | 完成标准 |
| --- | --- | --- |
| 1 | 新增根 README 与 AGENTS | 项目入口和工作规则清楚 |
| 2 | 更新 `docs/README.md` | 按任务导航、权威来源表、阶段摘要完整 |
| 3 | 统一五篇指南页首 | 能区分历史研究、当前决定与实际验证 |
| 4 | 补齐相互链接 | 路线可进入变更，变更可进入规范与证据，证据可找到复验方法 |

本轮保持 R0 原路径和历史语义。R2 实施时增加真实消费者与验收说明，准备发行时创建对应版本文档。验收目标是：维护者从 `docs/README.md` 出发，能够迅速找到必须遵守的规则、正在进行的工作、验证方法及支撑结论的证据。

## 10. 参考来源与证据范围

下列来源均固定到本次审查提交。对仓库现状的说明以该快照为准；拟新增路径、更新流程和实施清单属于建议。本文整理已有对话证据，没有重新运行框架测试或执行仓库修改。

- [S01：主仓固定目录][S01]
- [S02：文档入口与组件分工][S02]
- [S03：OpenSpec 项目上下文][S03]
- [S04：维护基线稳定规范][S04]
- [S05：R0 设计与事实来源决策][S05]
- [S06：R0 结构化基线][S06]
- [S07：R0 复验手册][S07]
- [S08：维护型 fork 路线][S08]
- [S09：参考 fork 研究][S09]
- [S10：AutoMapper 兼容维护指南][S10]
- [S11：Angular 生态维护指南][S11]
- [S12：Samples 取舍与兼容验收][S12]
- [S13：R0 正式归档][S13]

[S01]: https://github.com/dusdong/du.aspnetboilerplate/tree/92a31c2974edcfccb1c00817abeb93a23b16c059
[S02]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/README.md
[S03]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/openspec/config.yaml
[S04]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/openspec/specs/maintenance-baseline/spec.md
[S05]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/openspec/changes/archive/2026-11-24-establish-maintenance-baseline/design.md
[S06]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/maintenance/release-baseline.json
[S07]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/maintenance/baseline-evidence/README.md
[S08]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/maintenance/fork-roadmap.md
[S09]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/maintenance/fork-references.md
[S10]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/compatibility/automapper.md
[S11]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/compatibility/angular-ecosystem.md
[S12]: https://github.com/dusdong/du.aspnetboilerplate/blob/92a31c2974edcfccb1c00817abeb93a23b16c059/docs/validation/samples.md
[S13]: https://github.com/dusdong/du.aspnetboilerplate/tree/92a31c2974edcfccb1c00817abeb93a23b16c059/openspec/changes/archive/2026-11-24-establish-maintenance-baseline
