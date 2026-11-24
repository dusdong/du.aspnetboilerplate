# Du ASP.NET Boilerplate 项目协作约定

## 兼容约束

- 保留既有 `Abp` / `Abp.*` 命名空间。`Du.` 仅用于 NuGet `PackageId`，包改名时保留原 `AssemblyName`、`RootNamespace` 与公共类型全名。npm 包身份按对应组件和变更确定。[OpenSpec 项目上下文](openspec/config.yaml)
- 保留存量应用的正常业务行为。涉及 AutoMapper 时核对映射配置、对象更新、集合映射和查询投影，记录并验证安全修复引起的可观察差异。[AutoMapper 兼容指南](docs/compatibility/automapper.md)
- Windows、Linux、macOS 原生运行和 Angular 兼容是维护目标。按变更影响选择环境、数据库 Provider 和消费项目，支持范围以实测组合为准。[维护路线](docs/maintenance/fork-roadmap.md) · [Angular 兼容指南](docs/compatibility/angular-ecosystem.md)

## 主仓与子仓

- 主仓维护版本组合、OpenSpec、跨仓兼容指南与验收证据。源码、组件内回归和组件构建说明放在对应子仓。Web Resources 源码与经典框架同仓。各组件入口见[项目文档](docs/README.md)。
- 涉及子模块交付时，先核对子仓改动、验收输入及提交身份。按授权交付子仓提交，确认该提交可从 `.gitmodules` 指定的仓库取得，再交付指向它的主仓 gitlink。记录主仓提交和子仓提交，用 `git ls-tree` 核对指定主仓提交实际记录的 gitlink。[维护基线规范](openspec/specs/maintenance-baseline/spec.md) · [R1 gitlink 交付实例](docs/maintenance/r1-efcore-query-filter.md#git-接入)

## 变更验证与文档

- 新能力、重大行为变化或跨子仓架构调整，先查稳定规范与活动变更。涉及 OpenSpec 的变更在主仓执行 `openspec-cn validate --all --strict --no-interactive`。[规范与变更入口](docs/README.md#openspec)
- 组件行为在子仓验证，跨仓组合在对应消费项目验证。涉及发包时，用实际候选包从干净环境还原并验证代表性场景，核对依赖闭包和程序集。记录输入提交、产物、环境、实际结果及未执行项。[维护基线规范](openspec/specs/maintenance-baseline/spec.md)
- 支持范围、包身份、操作命令、兼容行为或验收结论发生变化时，同步相关指南和证据入口。历史基线按原输入保留，新的候选结果随相应变更记录。[证据与文档入口](docs/README.md#权威来源)
