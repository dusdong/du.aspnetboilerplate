# du.aspnetboilerplate 文档

本项目面向经典 ASP.NET Boilerplate 的独立维护与发行。克隆和初始化子模块见[项目首页](../README.md)，参与维护见[项目协作约定](../AGENTS.md)。

## 按任务查阅

| 任务 | 入口 |
| --- | --- |
| 查看各阶段目标、当前进度与发行条件 | [维护型 fork 路线](maintenance/fork-roadmap.md) |
| 用 `python3 eng/verify.py --profile r0` 复验 R0 的还原、Release 构建、公共 API 与回归 | [统一复验入口](maintenance/baseline-evidence/README.md#统一入口) · [本地与 GitHub Actions 配对验收](maintenance/baseline-evidence/README.md#统一入口验收记录) |
| 核对 EF Core 查询过滤补丁的提交、兼容行为与回归结果 | [R1 首项补丁验收记录](maintenance/r1-efcore-query-filter.md) |
| 核对 R1 运行时迁移的 Git 交付、.NET 9 源码兼容和 Windows 验收 | [R1 运行时迁移验收](maintenance/r1-dotnet10-runtime-migration.md) |
| 复验首批五个核心候选包的实际还原、程序集加载和 SQLite HTTP 请求 | [R2 候选包消费验收](maintenance/r2-core-package-consumption.md) |
| 比较第三方 fork 的迁移、补丁与独立发包实践 | [ASP.NET Boilerplate fork 调研](maintenance/fork-references.md) |
| 维护映射行为、Collection 依赖或消费项目回归 | [AutoMapper 兼容维护](compatibility/automapper.md) |
| 核对 Angular 适配器、Web Resources 与模板的版本组合 | [Angular 生态维护](compatibility/angular-ecosystem.md) |
| 选择多 DbContext、拦截器等专项消费验收场景 | [Samples 取舍与兼容验收](validation/samples.md) |

## 权威来源

| 要核对的事实 | 查阅位置 |
| --- | --- |
| 子模块仓库地址和路径 | [`.gitmodules`](../.gitmodules) |
| 指定主仓提交固定的子模块版本 | 该提交树中的 gitlink，见下文命令 |
| 长期可验收的要求 | [维护基线规范](../openspec/specs/maintenance-baseline/spec.md) · [EF Core 查询过滤规范](../openspec/specs/efcore-query-filters/spec.md) · [运行时迁移规范](../openspec/specs/runtime-migration/spec.md) · [核心候选包消费规范](../openspec/specs/core-package-consumption/spec.md) |
| 正在推进的提案、设计、任务与验收条件 | 主仓根目录执行 `openspec-cn list`，按列表查阅[变更目录](../openspec/changes/) |
| 已完成变更的历史方案及当时的验收范围 | [OpenSpec 归档](../openspec/changes/archive/) |
| R0 的固定来源、五包映射、依赖闭包、环境和实测结果 | [R0 维护基线](maintenance/release-baseline.json) |
| 某次验收实际执行的项目、环境和结果 | [R1 首项补丁验收记录](maintenance/r1-efcore-query-filter.md) · [R1 运行时迁移验收](maintenance/r1-dotnet10-runtime-migration.md) · [R2 候选包消费验收](maintenance/r2-core-package-consumption.md) |
| 当时的组织和实施建议 | [文档组织与治理建议稿](maintenance/du-abp-documentation-governance.md) · [主仓改进建议与实施路线](maintenance/du-abp-maintenance-plan.md)，两稿均基于 R0 快照 `92a31c2` |
| 某一版本实际交付的源码、包与支持范围 | 对应版本的发行清单和验收证据，由该次发行记录 |

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

截至 2026-11-25，R0 基线、R0 统一复验、R1 首项 .NET 9 查询过滤补丁、R1 首批核心源码运行时迁移及 R2 首批核心候选包的本机双目标消费验收均已归档。[R0 基线归档](../openspec/changes/archive/2026-11-24-establish-maintenance-baseline/) · [R0 统一复验归档](../openspec/changes/archive/2026-11-24-unify-r0-baseline-verification/) · [R1 首项归档](../openspec/changes/archive/2026-11-24-adopt-efcore-query-filter-fix/) · [R1 运行时迁移归档](../openspec/changes/archive/2026-11-25-migrate-r1-core-to-dotnet10/) · [R2 归档](../openspec/changes/archive/2026-11-25-validate-r2-core-package-consumption/) · [维护路线](maintenance/fork-roadmap.md)

- 新能力、重大行为变化或跨子模块架构调整，先核对 `openspec/specs/` 和 `openspec/changes/`。可用 `openspec-cn list --specs` 和 `openspec-cn list` 查看。
- 用 `openspec-cn new change <name>` 创建变更，在 `openspec/changes/<name>/` 中完成提案、增量规范、设计和任务清单。
- 实施后记录子模块提交、实际验证结果及适用的兼容范围。运行 `openspec-cn validate --all --strict --no-interactive`，完成的变更使用 `openspec-cn archive <name>` 归档。
