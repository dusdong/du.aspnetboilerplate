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

截至 2026-11-24，上游 `v10.5.1` 的 R0 基线与 .NET 9 上的 R1 首项 EF Core 查询过滤补丁均已验收并归档。R1 的 .NET 10 / EF Core 10 迁移和 R2 的首批 `Du.Abp*` 候选包消费验收仍待实施。[维护路线](docs/maintenance/fork-roadmap.md) · [R1 首项验收记录](docs/maintenance/r1-efcore-query-filter.md)

在主仓根目录运行 `python3 eng/verify.py --profile r0` 可复验固定 R0 源码。统一复验已完成本地与 GitHub Actions 的配对验收并归档。[复验手册](docs/maintenance/baseline-evidence/README.md#统一入口) · [配对验收记录](docs/maintenance/baseline-evidence/README.md#统一入口验收记录) · [统一复验归档](openspec/changes/archive/2026-11-24-unify-r0-baseline-verification/)

参与维护时先阅读[项目协作约定](AGENTS.md)。
