# R1 首批核心源码迁移至 .NET 10

## Why

R1 已在 .NET 9 接入并验收查询过滤修复 #7219。现在需要在同一修复基线上验证首批核心源码的 .NET 10、ASP.NET Core 10 和 EF Core 10 组合，为 R2 构建独立候选包提供已验收的源码输入。

## What Changes

- 以框架提交 `d08617b51bb7c7e5d0bea942e7e10b2677240c35` 为起点，迁移五个核心项目、三个源码支持项目和三套测试，共 11 个项目。保留八个源码项目及被其他测试引用的 `Abp.Tests` 的 `net9.0` 目标，增加 `net10.0`。其余两套核心回归工程使用 `net10.0`。
- 按目标框架选择依赖，适配 EF 查询服务和 ASP.NET Core 宿主，按已验收 R1 的程序集、公共 API、资源、依赖图和正常业务回归进行对照。
- 用闭包外仍为 `net9.0` 的同仓调用方按原项目默认目标验证源码引用。沿用框架 Windows PR 工作流，分别记录默认解决方案的实际 Windows 验证和 GitHub 工作流结果。以实际执行的环境、SQLite Provider 和候选输入界定结论。
- R2 负责包身份转换、独立包和包消费验证。完整模板、示例仓、前端、其他数据库 Provider 和其他项目的运行时升级分阶段处理。

## Capabilities

### New Capabilities

- `runtime-migration` — 维护线核心源码在新运行时上的可构建性、既有调用方兼容性及候选验收。

### Modified Capabilities

## Impact

- 框架子模块 `aspnetboilerplate` 的首批产物为 `Abp`、`Abp.AspNetCore`、`Abp.EntityFramework.Common`、`Abp.EntityFrameworkCore` 和 `Abp.Web.Common` 的 Release DLL。现有 `PackageId`、程序集名、根命名空间和 `Abp.*` 类型身份沿用当前契约。
- 同仓源码调用方包括 EF6、Module Zero 的 EF Core 适配层、ASP.NET Core Demo 和测试基座调用方。项目清单、.NET 9 定向验收和 Windows PR CI 验收范围见[设计](design.md)。
- 主仓维护候选证据和集成记录。原版 R0 的 [基线](../../../../docs/maintenance/release-baseline.json)、历史 SHA、复验入口及原始证据保持固定。迁移的主要对照为 [R1 首项补丁验收记录](../../../../docs/maintenance/r1-efcore-query-filter.md)。
