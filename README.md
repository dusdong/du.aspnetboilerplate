# Du ASP.NET Boilerplate

本仓是经典 ASP.NET Boilerplate 的独立维护与发行协调仓。六个 Git 子模块分别承载框架、Angular 适配器、免费启动模板、示例、AutoMapper 和 AutoMapper.Collection。主仓固定源码组合，维护 OpenSpec、兼容指南和跨仓验收证据。各组件的开发与测试入口由子仓维护。

## 公开发行

首个稳定版 `v10.5.1` 已发布。nuget.org 提供 11 个 `Du.Abp*` 框架包 `10.5.1`、`Du.AutoMapper 14.0.0` 和 `Du.AutoMapper.Collection 11.0.0`。`net10.0` 新库示例使用实测运行时 `10.0.15`。存量 `net9.0` 迁移已在 `9.0.10` 实测，微软于 2026-11-10 结束 .NET 9 支持。[发行说明与包链接](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1) · [新库安装指南](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-INSTALL-net10.md) · [包与符号校验清单](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json)

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

R3 首包和第二包均已归档。首包记录固定模板原版 Web.Host 的包图及六个维护包缺口。第二包用 `10.5.1-r3.1` 在 macOS ARM64 的独立 `net9.0` 宿主验证 SignalR 通知和 Log4Net 日志。框架 `dev` 已交付同树实现，主仓 gitlink 记录相应提交。[原版 Web.Host 基线](docs/maintenance/r3-web-host-baseline.md) · [第二包验收](docs/maintenance/r3-signalr-log4net-candidates.md) · [集成候选包消费规范](openspec/specs/web-host-integration-package-consumption/spec.md) · [第二包归档](openspec/changes/archive/2026-11-25-add-r3-signalr-log4net-candidates/)

Module Zero 的三个候选包 `10.5.1-r3.3` 已通过 macOS ARM64 上的独立 `net9.0` 实包验收，覆盖 SQLite 角色提交和双向租户隔离。框架 `dev` 已交付通过验收的源码树，主仓 gitlink 固定对应提交，OpenSpec 已同步并归档。[Module Zero 候选验收](docs/maintenance/r3-module-zero-candidates.md) · [稳定消费规范](openspec/specs/module-zero-package-consumption/spec.md)

R3.4 AutoMapper 的引擎、Collection 和 ABP 适配器候选已通过本机独立 `net9.0` 实包验收，覆盖单一引擎加载、已有用户更新、按键集合和 SQLite 投影。三个子仓的源码均已交付，主仓固定相应 gitlink，OpenSpec 已同步并归档。固定模板 Web.Host 的六个缺口均已取得独立候选。[AutoMapper 本机验收](docs/maintenance/r3-automapper-downstream.md#消费验收记录) · [Git 交付](docs/maintenance/r3-automapper-downstream.md#git-交付) · [稳定消费规范](openspec/specs/automapper-package-consumption/spec.md)

R3 原版模板的 SQL Server 恢复、Angular 租户登录和授权查询已通过两轮本机验收，OpenSpec 已同步并归档。[运行对照与恢复点](docs/maintenance/r3-template-runtime-baseline.md#交接数据恢复点) · [稳定规范](openspec/specs/template-runtime-baseline/spec.md)

R3 固定模板 `net9.0` 同目标换包已验收并归档。13 个冻结维护包在 macOS ARM64、.NET 9.0.10、SQL Server 和原版 Angular production 客户端组合下复现租户登录与授权查询。候选库新增一条成功登录记录，独立对照库计数未变。[验收与复跑](docs/maintenance/r3-template-net9-packages.md) · [稳定规范](openspec/specs/template-maintenance-package-consumption/spec.md) · [归档](openspec/changes/archive/2026-11-25-validate-r3-net9-template-package-migration/)

R3 固定维护版模板的 .NET 10 / EF Core 10 升级已通过本机实测，OpenSpec 已同步并归档。在同一候选库完成两代迁移、租户登录与权限查询，两库成功登录计数从 `1/1` 经 `2/1` 到 `3/1`。升级前后备份均已恢复至独立新库。[正式运行与恢复点](docs/maintenance/r3-template-net10-upgrade.md#2026-11-25-正式运行验收) · [稳定规范](openspec/specs/template-runtime-upgrade/spec.md) · [归档](openspec/changes/archive/2026-11-25-validate-r3-net10-template-runtime-upgrade/)

R3 固定原版模板已在升级前后两个 SQL Server 恢复点通过本机回退实测，OpenSpec 已同步并归档。原版 Migrator 保留 30 条迁移与已核对的表结构，原版 Host 完成 Angular 租户登录和授权查询。直接在升级后状态切回应用会保留 .NET 10 成功登录行。恢复到升级前状态会舍弃该写入。[回退步骤与正式证据](docs/maintenance/r3-original-template-rollback.md#正式运行结果) · [稳定规范](openspec/specs/template-application-rollback/spec.md) · [归档](openspec/changes/archive/2026-11-26-validate-r3-original-template-rollback/)

在主仓根目录运行 `python3 eng/verify.py --profile r0` 可复验固定 R0 源码。统一复验已完成本地与 GitHub Actions 的配对验收并归档。[复验手册](docs/maintenance/baseline-evidence/README.md#统一入口) · [配对验收记录](docs/maintenance/baseline-evidence/README.md#统一入口验收记录) · [统一复验归档](openspec/changes/archive/2026-11-24-unify-r0-baseline-verification/)

参与维护时先阅读[项目协作约定](AGENTS.md)。
