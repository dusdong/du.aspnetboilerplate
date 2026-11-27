# du.aspnetboilerplate 文档

本项目面向经典 ASP.NET Boilerplate 的独立维护与发行。克隆和初始化子模块见[项目首页](../README.md)，参与维护见[项目协作约定](../AGENTS.md)。

## 按任务查阅

| 任务 | 入口 |
| --- | --- |
| 安装 R5 映射补丁，在新 SQL Server 测试库运行 `net10.0` 模板 | [R5 新库安装指南](maintenance/r5-public-install.md) · [发行说明](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.2) · [校验清单](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.2/R5-PACKAGE-CHECKSUMS.json) |
| 安装 R4 稳定维护包，在新 SQL Server 测试库运行 `net10.0` 模板 | [发行说明与包链接](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1) · [已实跑安装指南](maintenance/r4-public-install.md) · [公开包与符号校验清单](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json) |
| 查看各阶段目标、当前进度与发行条件 | [维护型 fork 路线](maintenance/fork-roadmap.md) |
| 核对 R5 发行验收、交付和缓存处置 | [公开发行验收记录](maintenance/r5-public-release.md) · [收尾交付](maintenance/fork-roadmap.md#2026-11-27-公开发行收尾) · [52 项缓存处置](maintenance/fork-roadmap.md#本轮缓存处置) |
| 核对首发证据、R5 的补丁决定和消费者行动 | [R4 归档后复核](maintenance/r4-release-candidate.md#首发归档后复核) · [R5 首轮维护审查](maintenance/r5-first-maintenance-review.md#本轮决定) · [下轮检查点](maintenance/r5-first-maintenance-review.md#下轮检查点) |
| 核对 `v10.5.2` 维护决定、四入口包图及公告续查 | [本轮决定](maintenance/r5-public-patch-review.md#本轮维护决定) · [四入口依赖清单](maintenance/r5-public-patch-dependencies.tsv) · [后续检查点](maintenance/r5-public-patch-review.md#下轮检查点与验证边界) |
| 准备存量 R4 应用迁往 `net10.0`，接续上游与公告审查 | [存量迁移指引](maintenance/r5-r4-net10-migration.md) · [增量审查与续查水位](maintenance/r5-runtime-migration-review.md) · [迁移与审查归档](../openspec/changes/archive/2026-11-26-review-r5-runtime-migration-readiness/) · [R4 公开包同库实测](maintenance/r4-release-candidate.md#公开源模板消费) |
| 复验 R5 集合补丁、冻结三包及独立消费者 | [固定模板安装、迁移与同库回退](maintenance/r5-automapper-template.md) · [引擎实包验收与复跑](../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/engine-package-validation.md) · [共享集合计划对照](../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/shared-collection-plan-observation.md) · [三包冻结与消费](../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md) · [补丁提案](../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/proposal.md) · [候选设计](../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/design.md) · [归档任务清单](../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/tasks.md) |
| 用 `python3 eng/verify.py --profile r0` 复验 R0 的还原、Release 构建、公共 API 与回归 | [统一复验入口](maintenance/baseline-evidence/README.md#统一入口) · [本地与 GitHub Actions 配对验收](maintenance/baseline-evidence/README.md#统一入口验收记录) |
| 核对 EF Core 查询过滤补丁的提交、兼容行为与回归结果 | [R1 首项补丁验收记录](maintenance/r1-efcore-query-filter.md) |
| 核对 R1 运行时迁移的 Git 交付、.NET 9 源码兼容和 Windows 验收 | [R1 运行时迁移验收](maintenance/r1-dotnet10-runtime-migration.md) |
| 复验首批五个核心候选包的实际还原、程序集加载和 SQLite HTTP 请求 | [R2 候选包消费验收](maintenance/r2-core-package-consumption.md) |
| 复跑原版 Web.Host 的还原与 Release 构建，核对迁移前的包图和候选缺口 | [R3 Web.Host 基线](maintenance/r3-web-host-baseline.md) · [首次通过清单](maintenance/r3-web-host-baseline.json) |
| 复跑原版模板的 SQL Server 种子、Angular 租户登录、用户搜索和备份恢复 | [R3 原版模板运行对照](maintenance/r3-template-runtime-baseline.md) · [同目标换包恢复点](maintenance/r3-template-runtime-baseline.md#交接数据恢复点) |
| 复跑固定 net9.0 模板的维护包构建及 SQL Server、Angular 业务对照 | [R3 模板换包验收](maintenance/r3-template-net9-packages.md#正式运行结果) · [运行复验](maintenance/r3-template-net9-packages.md#运行复验) |
| 复跑固定维护版模板的 .NET 10 升级，核对同库迁移、Angular 业务和两个恢复点 | [升级构建与完整运行入口](maintenance/r3-template-net10-upgrade.md#完整运行复验) · [稳定规范](../openspec/specs/template-runtime-upgrade/spec.md) · [归档](../openspec/changes/archive/2026-11-25-validate-r3-net10-template-runtime-upgrade/) |
| 从升级前后两份介质复跑固定原版应用回退，核对查询和成功登录的实际目标库 | [复跑与正式结果](maintenance/r3-original-template-rollback.md) · [稳定规范](../openspec/specs/template-application-rollback/spec.md) · [归档](../openspec/changes/archive/2026-11-26-validate-r3-original-template-rollback/) |
| 生成或复验 SignalR 与 Log4Net 本地候选，核对独立宿主的通知和日志 | [R3 SignalR 与 Log4Net 候选验收](maintenance/r3-signalr-log4net-candidates.md) · [Git 交付](maintenance/r3-signalr-log4net-candidates.md#git-交付) |
| 生成或复验 Module Zero 本地候选，核对 SQLite 角色提交及双向租户隔离 | [R3 Module Zero 候选验收](maintenance/r3-module-zero-candidates.md) |
| 核对 R4 首发冻结归档、公开源模板与历史回退 | [R4 组合与复验](maintenance/r4-release-candidate.md) · [公开源模板消费](maintenance/r4-release-candidate.md#公开源模板消费) · [发布者交接](maintenance/r4-release-candidate.md#发布者交接) |
| 核对 GitHub Actions 向 NuGet 发布补丁的权限和实际运行 | [R5 受信任发布与续作记录](maintenance/r5-public-release.md#nuget-受信任发布) · [发行手册](maintenance/r5-automapper-template.md#执行待发交接手册) |
| 比较第三方 fork 的迁移、补丁与独立发包实践 | [ASP.NET Boilerplate fork 调研](maintenance/fork-references.md) |
| 复验 R3 映射候选、Collection 依赖与模板业务投影 | [AutoMapper 兼容维护](compatibility/automapper.md) · [原版基线](maintenance/r3-automapper-baseline.md) · [引擎验收](maintenance/r3-automapper-engine.md) · [独立消费者验收与复跑](maintenance/r3-automapper-downstream.md#主仓实包消费与复验) · [Git 交付](maintenance/r3-automapper-downstream.md#git-交付) |
| 核对 Angular 适配器、Web Resources 与模板的版本组合 | [Angular 生态维护](compatibility/angular-ecosystem.md) |
| 选择多 DbContext、拦截器等专项消费验收场景 | [Samples 取舍与兼容验收](validation/samples.md) |

## 权威来源

| 要核对的事实 | 查阅位置 |
| --- | --- |
| 子模块仓库地址和路径 | [`.gitmodules`](../.gitmodules) |
| 指定主仓提交固定的子模块版本 | 该提交树中的 gitlink，见下文命令 |
| 长期可验收的要求 | [维护基线规范](../openspec/specs/maintenance-baseline/spec.md) · [EF Core 查询过滤规范](../openspec/specs/efcore-query-filters/spec.md) · [运行时迁移规范](../openspec/specs/runtime-migration/spec.md) · [核心候选包消费规范](../openspec/specs/core-package-consumption/spec.md) · [模板 Web.Host 基线规范](../openspec/specs/template-host-baseline/spec.md) · [原版模板运行规范](../openspec/specs/template-runtime-baseline/spec.md) · [集成候选包消费规范](../openspec/specs/web-host-integration-package-consumption/spec.md) · [Module Zero 候选包消费规范](../openspec/specs/module-zero-package-consumption/spec.md) · [AutoMapper 候选包消费规范](../openspec/specs/automapper-package-consumption/spec.md) · [模板维护包消费规范](../openspec/specs/template-maintenance-package-consumption/spec.md) · [模板运行时升级规范](../openspec/specs/template-runtime-upgrade/spec.md) |
| 正在推进的提案、设计、任务与验收条件 | 主仓根目录执行 `openspec-cn list`，按列表查阅[变更目录](../openspec/changes/) |
| 已完成变更的历史方案及当时的验收范围 | [OpenSpec 归档](../openspec/changes/archive/) |
| R0 的固定来源、五包映射、依赖闭包、环境和实测结果 | [R0 维护基线](maintenance/release-baseline.json) |
| 某次验收实际执行的项目、环境和结果 | [R1 首项补丁验收记录](maintenance/r1-efcore-query-filter.md) · [R1 运行时迁移验收](maintenance/r1-dotnet10-runtime-migration.md) · [R2 候选包消费验收](maintenance/r2-core-package-consumption.md) · [R3 首包验收](maintenance/r3-web-host-baseline.md) · [R3 第二包验收](maintenance/r3-signalr-log4net-candidates.md) · [R3 Module Zero 验收](maintenance/r3-module-zero-candidates.md) · [R3 AutoMapper 验收](maintenance/r3-automapper-downstream.md#消费验收记录) · [R3 原版模板运行返修验收](maintenance/r3-template-runtime-baseline.md#2026-11-25-返修复验) · [R3 模板换包正式验收](maintenance/r3-template-net9-packages.md#正式运行结果) · [R3 模板升级正式验收](maintenance/r3-template-net10-upgrade.md#2026-11-25-正式运行验收) |
| 当时的组织和实施建议 | [文档组织与治理建议稿](maintenance/du-abp-documentation-governance.md) · [主仓改进建议与实施路线](maintenance/du-abp-maintenance-plan.md)，两稿均基于 R0 快照 `92a31c2` |
| 某一版本实际交付的源码、包与支持范围 | 对应版本的发行清单和验收证据，由该次发行记录 |
| R4 首发与 R5 局部补丁的公开交付条件和复验范围 | [公开发行稳定规范](../openspec/specs/public-package-release/spec.md) · [R4 首发归档](../openspec/changes/archive/2026-11-26-publish-r4-first-public-release/) · [R4 发行说明](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1) · [R5 发行归档](../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/) |
| 发行后的维护审查规则、历史工作制品及本次处置 | [维护审查稳定规范](../openspec/specs/maintenance-release-review/spec.md) · [R5 首轮归档](../openspec/changes/archive/2026-11-26-review-r5-first-maintenance-cycle/) · [首轮审查记录](maintenance/r5-first-maintenance-review.md) · [增量审查记录](maintenance/r5-runtime-migration-review.md) |

## 子模块分工

| 子模块 | 用途 |
| --- | --- |
| `aspnetboilerplate` | 框架、Module Zero、AutoMapper 适配器和经典 Web Resources 源码 |
| `abp-ng2-module` | 经典 ABP 的 Angular 适配层 |
| `module-zero-core-template` | 免费启动模板与完整应用集成验收 |
| `aspnetboilerplate-samples` | 上游示例参考与精选专项验收 |
| `AutoMapper` | 映射引擎兼容维护 |
| `AutoMapper.Collection` | 集合映射扩展及其依赖闭包 |

在主仓根目录执行以下命令。查阅历史版本时，把第一条中的 `HEAD` 换成指定的主仓提交。第二条读取主仓索引中的 gitlink，第三条显示本地子模块检出状态。

```sh
git ls-tree HEAD -- aspnetboilerplate abp-ng2-module module-zero-core-template aspnetboilerplate-samples AutoMapper AutoMapper.Collection
git submodule status --cached
git submodule status
```

历史基线可为兼容研究选用另一参考提交。各专题页首注明当前使用的参考、源码核对与消费验收范围。

## OpenSpec

主仓使用 `openspec-cn` 的 `spec-driven` 工作流。项目约束和制品规则见 [OpenSpec 配置](../openspec/config.yaml)。

截至 2026-11-25，R0 基线、R0 统一复验、R1 首项 .NET 9 查询过滤补丁、R1 首批核心源码运行时迁移、R2 首批核心候选包的本机双目标消费验收，以及 R3 原版 Web.Host 基线、SignalR 与 Log4Net 候选验收、Module Zero 候选验收、AutoMapper 候选验收、原版模板运行对照、固定模板 `net9.0` 同目标换包和维护版模板 .NET 10 运行时升级均已归档。[R0 基线归档](../openspec/changes/archive/2026-11-24-establish-maintenance-baseline/) · [R0 统一复验归档](../openspec/changes/archive/2026-11-24-unify-r0-baseline-verification/) · [R1 首项归档](../openspec/changes/archive/2026-11-24-adopt-efcore-query-filter-fix/) · [R1 运行时迁移归档](../openspec/changes/archive/2026-11-25-migrate-r1-core-to-dotnet10/) · [R2 归档](../openspec/changes/archive/2026-11-25-validate-r2-core-package-consumption/) · [R3 首包归档](../openspec/changes/archive/2026-11-25-baseline-r3-web-host-dependencies/) · [R3 第二包归档](../openspec/changes/archive/2026-11-25-add-r3-signalr-log4net-candidates/) · [R3 Module Zero 归档](../openspec/changes/archive/2026-11-25-add-r3-module-zero-candidates/) · [R3 AutoMapper 归档](../openspec/changes/archive/2026-11-25-add-r3-automapper-candidates/) · [R3 原版模板运行归档](../openspec/changes/archive/2026-11-25-baseline-r3-original-template-runtime/) · [R3 模板换包归档](../openspec/changes/archive/2026-11-25-validate-r3-net9-template-package-migration/) · [R3 模板升级归档](../openspec/changes/archive/2026-11-25-validate-r3-net10-template-runtime-upgrade/) · [维护路线](maintenance/fork-roadmap.md)

2026-11-26，R3 固定模板原版应用回退同步了稳定规范并归档。[回退稳定规范](../openspec/specs/template-application-rollback/spec.md) · [回退归档](../openspec/changes/archive/2026-11-26-validate-r3-original-template-rollback/)

2026-11-26，R4 首次发行候选完成本地制备、消费者验收和发布者交接，稳定规范已同步，变更已归档。[首发候选验收稳定规范](../openspec/specs/release-candidate-verification/spec.md) · [R4 候选归档](../openspec/changes/archive/2026-11-26-prepare-r4-first-release-candidate/)

同批 13 个包及其符号已公开，两代公开源消费者和 `net10.0` 新库安装验收通过。首次公开发行的稳定规范已同步，变更已归档。[公开发行规范](../openspec/specs/public-package-release/spec.md) · [首发归档](../openspec/changes/archive/2026-11-26-publish-r4-first-public-release/) · [R4 首次公开发行](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1)

2026-11-26，R5 的存量迁移与增量审查、集合映射补丁候选均已同步规范并归档。[维护审查稳定规范](../openspec/specs/maintenance-release-review/spec.md) · [迁移与审查归档](../openspec/changes/archive/2026-11-26-review-r5-runtime-migration-readiness/) · [映射消费稳定规范](../openspec/specs/automapper-package-consumption/spec.md) · [集合补丁归档](../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/)

三包发行准备已同步候选验收规范并归档。2026-11-27，R5 包、符号和三项公开消费验收通过，`v10.5.2` 已公开并读回，公开发行规范已同步，发行变更已归档。[公开发行验收记录](maintenance/r5-public-release.md) · [正式发行任务清单](../openspec/changes/archive/2026-11-27-publish-r5-mapping-patch/tasks.md) · [公开发行稳定规范](../openspec/specs/public-package-release/spec.md) · [局部补丁候选验收规范](../openspec/specs/release-candidate-verification/spec.md#requirement-局部补丁可从已验候选交接为本地待发批次) · [发行准备归档](../openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/)

2026-11-27，`v10.5.2` 补丁后的维护审查已同步稳定规范并归档，覆盖跨公开版本的包图对照、上游未决事项和公告适用性。[跨公开补丁的审查要求](../openspec/specs/maintenance-release-review/spec.md#requirement-跨公开补丁的审查能说明既有结论的适用范围) · [审查任务归档](../openspec/changes/archive/2026-11-27-review-r5-public-patch-baseline/tasks.md)

- 新能力、重大行为变化或跨子模块架构调整，先核对 `openspec/specs/` 和 `openspec/changes/`。可用 `openspec-cn list --specs` 和 `openspec-cn list` 查看。
- 用 `openspec-cn new change <name>` 创建变更，在 `openspec/changes/<name>/` 中完成提案、增量规范、设计和任务清单。
- 实施后记录子模块提交、实际验证结果及适用的兼容范围。运行 `openspec-cn validate --all --strict --no-interactive`，完成的变更使用 `openspec-cn archive <name>` 归档。
