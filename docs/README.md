# du.aspnetboilerplate 文档

本项目面向经典 ASP.NET Boilerplate 的独立维护与发行。首次阅读可以从维护路线开始，再按所涉及的依赖或验收场景查阅专题。

## 文档索引

| 目录 | 文档 | 内容 |
| --- | --- | --- |
| `maintenance/` | [维护型 fork 路线](maintenance/fork-roadmap.md) | 兼容性约束、上游基线、维护范围和发布门禁 |
| `maintenance/` | [ASP.NET Boilerplate fork 调研](maintenance/fork-references.md) | .NET 迁移、上游补丁与独立发包的参考实现 |
| `compatibility/` | [AutoMapper 兼容维护](compatibility/automapper.md) | 映射行为、Collection 依赖、安全修复和消费项目回归 |
| `compatibility/` | [Angular 生态维护](compatibility/angular-ecosystem.md) | Angular 适配器、Web Resources、免费模板的版本组合和集成验证 |
| `validation/` | [Samples 取舍与兼容验收](validation/samples.md) | 多 DbContext、拦截器等专项验收场景 |

## 子模块分工

截至 2026-11-24，主仓已接入以下 6 个 Git 子模块。仓库地址见 [`.gitmodules`](../.gitmodules)，主仓固定的提交可用 `git submodule status --cached` 查看。

| 子模块 | 用途 |
| --- | --- |
| `aspnetboilerplate` | 框架、Module Zero、AutoMapper 适配器和经典 Web Resources 源码 |
| `abp-ng2-module` | 经典 ABP 的 Angular 适配层 |
| `module-zero-core-template` | 免费启动模板与完整应用集成验收 |
| `aspnetboilerplate-samples` | 上游示例参考与精选专项验收 |
| `AutoMapper` | 映射引擎兼容维护 |
| `AutoMapper.Collection` | 集合映射扩展及其依赖闭包 |

各专题保留原调研日期和证据范围。后续的兼容组合、构建、发包与真实应用验收进度以实际执行记录为准。
