# R2 首批核心候选包与独立消费验收

## Why

R1 已验证首批核心源码的 `net9.0` 和 `net10.0` 产物及运行行为。R2 需要验证同一源码基线生成的五个维护版候选包，确认独立应用只依赖 NuGet 包就能干净还原、加载相应目标的框架程序集并完成实际数据操作。

## What Changes

- 在框架子仓为五个核心项目增加显式本地候选打包入口。每个包包含 `net9.0` 与 `net10.0` 的 Release 资产，统一使用首个拟定预发布版本 `10.5.1-r2.1`，保留 R1 同目标的程序集身份、根命名空间、公共 API、内嵌资源和第三方依赖约定。普通构建、现有项目引用和原打包入口沿用既有行为。
- 在主仓核对实际 `.nupkg`、消费者资产及加载的程序集。两个直接入口构成的两条三级框架依赖链使用同批候选包，并能在各目标中追溯第三方包来源、版本和资产。
- 在主仓 `validation/minimal-backend/` 增加独立 ASP.NET Core 消费者，只直接引用 `Du.Abp.AspNetCore` 和 `Du.Abp.EntityFrameworkCore` 两个框架包。分别在本机 macOS ARM64 的两个目标上运行真实 HTTP、ABP 模块和 DI、SQLite 工作单元提交及独立读回。
- 记录候选源码、包版本与摘要、还原与运行证据，并在验收后更新现有文档入口。首批候选限本地，公开发布、完整模板、Angular、AutoMapper、Module Zero、其他 Provider、依赖升级与 CI 扩展分阶段处理。

## Capabilities

### New Capabilities

- `core-package-consumption` — 核心候选包的产物契约、干净还原及可复核的真实消费。

### Modified Capabilities

## Impact

- 框架子仓 `aspnetboilerplate` 的五个候选包为 `Du.Abp`、`Du.Abp.Web.Common`、`Du.Abp.AspNetCore`、`Du.Abp.EntityFramework.Common` 与 `Du.Abp.EntityFrameworkCore`。具体映射、依赖及验收入口见[设计](design.md)。
- 规划依据为主仓 `0780c8c55a964b2c561b1126f2a2f98048b1c100` 与框架 gitlink `d497cba3d3feec093168697e81adb64ea5544087`，该框架树与 R1 最终实测树一致。实施时固定实际 R2 源码和产物，复核 R1 同目标对照证据是否可取得。[R1 运行时迁移验收](../../../../docs/maintenance/r1-dotnet10-runtime-migration.md)
- 主仓维护跨仓验证入口、消费项目和当轮证据。R0 冻结输入继续提供五包映射，R1 验收为同目标兼容性对照。[R0 基线](../../../../docs/maintenance/release-baseline.json) · [维护计划](../../../../docs/maintenance/du-abp-maintenance-plan.md#7-r2首批五包和真实消费者)
