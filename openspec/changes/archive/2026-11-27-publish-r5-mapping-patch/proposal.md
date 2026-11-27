# R5 映射补丁公开发行计划

## Why

三个映射包已完成本地验收，主仓 `cebc3e38` 已交付待发实物的生产来源和发行手册。消费者仍只能从 nuget.org 取得 R4 版本，R5 的仓库签名、公开符号和真实公开安装需在维护者决定发行后取得。[待发交接](../2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md)

## What Changes

- 获得对应发行授权后，将主仓附注 tag `v10.5.2` 绑定到已核实的协调提交。首次 NuGet 上传前完成同提交的 GitHub OIDC 登录验证，完善单件放行、收据和续作手册。按冻结清单分步发行三个主包和三个符号包，核对十个沿用的 R4 包。
- 用公开下载件验签、比对归档内容并读回三个 PDB，在独立空缓存和隔离 SQL Server 上完成固定模板公开源 `install`、`upgrade`，再用面向消费者的 R5 安装指南完成独立公开新装。
- 三项真实公开消费验收通过后发布 GitHub Release、公开校验清单和实测支持范围，并提供已按公开版本实跑的安装指南。

## Capabilities

### New Capabilities

### Modified Capabilities

- `public-package-release` 补充局部升版的公开交付条件，覆盖新增包、沿用包和真实公开源的证据。

## Impact

三个生产仓分别提供 `Du.AutoMapper 14.0.1`、`Du.AutoMapper.Collection 11.0.1`、`Du.Abp.AutoMapper 10.5.2`。主仓负责发行与公开回装，固定免费模板用于验收。支持结论沿用已测 macOS ARM64、SQL Server 与 Angular 组合，并在发行记录中注明本轮实测。缓存处置与部署各自决定。
