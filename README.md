# Du ASP.NET Boilerplate

本仓是经典 ASP.NET Boilerplate 的独立维护与发行协调仓。六个 Git 子模块分别承载框架、Angular 适配器、免费启动模板、示例、AutoMapper 和 AutoMapper.Collection。主仓固定源码组合，维护 OpenSpec、兼容指南和跨仓验收证据。各组件的开发与测试入口由子仓维护。

## 获取源码

首次克隆时，在准备存放仓库的目录执行：

```sh
git clone --recurse-submodules https://github.com/dusdong/du.aspnetboilerplate.git
cd du.aspnetboilerplate
```

已有主仓克隆时，在主仓根目录初始化并检出所选提交固定的子模块版本：

```sh
git submodule update --init --recursive
```

子模块地址见 [`.gitmodules`](.gitmodules)。各组件的职责及如何核对指定主仓提交的 gitlink，见[项目文档](docs/README.md)。

## 当前阶段

截至 2026-11-25，上游 `v10.5.1` 的 R0 基线、R1 首项 .NET 9 查询过滤补丁和 R1 首批 .NET 10 / EF Core 10 源码迁移均已验收并归档。R1 源码兼容证据覆盖 macOS ARM64 回归、.NET 9 调用方、UTM Windows ARM64 和 GitHub 托管 Windows x64。[维护路线](docs/maintenance/fork-roadmap.md) · [R1 首项验收记录](docs/maintenance/r1-efcore-query-filter.md) · [R1 运行时迁移验收](docs/maintenance/r1-dotnet10-runtime-migration.md)

R2 已归档。首批五个核心候选包 `10.5.1-r2.1` 已通过本机 macOS ARM64 上的 `net9.0`、`net10.0` 独立后端与 SQLite 验收。框架 `dev` 已交付同树的打包实现，主仓 gitlink 记录该框架提交。[R2 验收与复跑](docs/maintenance/r2-core-package-consumption.md) · [核心候选包消费规范](openspec/specs/core-package-consumption/spec.md)

在主仓根目录运行 `python3 eng/verify.py --profile r0` 可复验固定 R0 源码。统一复验已完成本地与 GitHub Actions 的配对验收并归档。[复验手册](docs/maintenance/baseline-evidence/README.md#统一入口) · [配对验收记录](docs/maintenance/baseline-evidence/README.md#统一入口验收记录) · [统一复验归档](openspec/changes/archive/2026-11-24-unify-r0-baseline-verification/)

参与维护时先阅读[项目协作约定](AGENTS.md)。
