# 统一 R0 基线复验入口与主仓 CI

## Why

R0 已取得独立还原、Release 构建、公共 API 和三套回归的验收证据。当前复验需要串联脚本和手册中的命令，主仓也没有调用同一检查入口的 CI，导致 R1 运行时迁移前难以用一次可追溯的执行重取完整对照。[R0 复验手册](../../../../docs/maintenance/baseline-evidence/README.md) · [主仓维护计划](../../../../docs/maintenance/du-abp-maintenance-plan.md#5-最高优先级建立完整共同的检查入口)

## What Changes

- 在主仓增加 `python3 eng/verify.py --profile r0`，从已接受基线取得固定框架提交与预期清单。两次独立还原与基线比对一致后，沿用主轮还原结果进行 Release 构建、身份与 API 核对及三套真实回归。
- 将本次主仓输入、当前框架 gitlink、实际 R0 框架源码、运行环境及分步结果写入可追溯报告，保留实际依赖清单、程序集摘要、日志及 TRX。按 TRX 用例明细确认原有跳过，并交叉核对关键汇总计数。必需证据缺失或出现预期之外的差异时退出非零。
- 新增主仓 CI 工作流，先执行轻量 Python 定向验证，通过后运行同一完整命令。留存自检诊断和当次实际生成的复验证据。现有复验手册、`primary` / `repeat` 调用和历史证据路径继续可用。[R0 基线](../../../../docs/maintenance/release-baseline.json)

## Capabilities

### New Capabilities

### Modified Capabilities

- `maintenance-baseline`：维护者可在本地和主仓 CI 通过同一命令复验固定 R0，获得可核查的结果与失败证据。

## Impact

实施落点为主仓 `eng/`、主仓 GitHub Actions 工作流和 R0 手册入口。运行输入是 `aspnetboilerplate` 子模块中的固定 R0 提交，覆盖 `Abp`、`Abp.AspNetCore`、`Abp.EntityFrameworkCore`、`Abp.Web.Common`、`Abp.EntityFramework.Common` 五个原版 Release DLL 和三套源码回归。其余五个子模块及独立消费者无实施任务。已接受实测参考为 macOS ARM64、SDK `9.0.306`、`net9.0` 与 SQLite，首个 CI runner 的执行环境及结果在实施时取得并单独登记。[R0 归档](../2026-11-24-establish-maintenance-baseline/) · [R1 验收记录](../../../../docs/maintenance/r1-efcore-query-filter.md)

本变更限于已接受 R0 的原版源码复验和主仓工作流。完成后，维护路线依次推进 R1 的 .NET 10 / EF Core 10 迁移、R2 的五个 `Du.Abp*` 候选包及独立消费者。[维护路线](../../../../docs/maintenance/fork-roadmap.md)
