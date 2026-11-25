# R3 Module Zero 候选消费提案

## Why

固定模板的原版 Web.Host 依赖闭包曾有六个维护版候选缺口。SignalR 与 Log4Net 已通过本机实包验收，框架提交和主仓 gitlink 已推送，上一批 OpenSpec 已同步并归档。余下四项中，Module Zero 的三个项目可以沿用已验 R2 实包按依赖顺序生产同批候选，并用独立 SQLite 消费者验证角色持久化与租户隔离。 [模板基线](../../../../docs/maintenance/r3-web-host-baseline.md) · [上一批本机验收](../../../../docs/maintenance/r3-signalr-log4net-candidates.md)

## What Changes

- 为 `Abp.Zero.Common`、`Abp.ZeroCore`、`Abp.ZeroCore.EntityFrameworkCore` 增加显式 `net9.0` 候选生产入口。三包使用同一未分配的 `10.5.1-r3.N` 预发布版本，拟从 `10.5.1-r3.2` 起核对可用序号。每份主包均有对应符号包以及可复核的实际编译来源。
- 在主仓从冻结的三个新候选与三个已验 R2 原包干净还原一个独立消费者。消费者仅直接引用 `Du.Abp.ZeroCore.EntityFrameworkCore` 这一个框架包，并在真实 ABP 工作单元中使用角色存储写入 SQLite，提交后在独立工作单元读回两个租户各自的角色并核对租户隔离。
- 为普通 `net9.0` 源码构建及打包取得对照，复验原项目引用、包身份及可观察行为，并按资源名称核对两个 Zero 组件嵌入的本地化 XML 内容摘要。验收登记说明如何生产新批和用同一批实物复跑，以及当前选用的 SDK、实际运行时、SQLite Provider 和目标范围。

## Capabilities

### New Capabilities

- `module-zero-package-consumption` 规定经典 Module Zero 候选的生产来源、独立包闭包、程序集兼容和跨工作单元的租户角色读回。

### Modified Capabilities

## Impact

- 框架子仓负责三个目标项目、候选生产入口与普通源码回归。主仓负责独立消费者、统一验证入口、冻结批次登记和维护文档。R2 输入为 `Du.Abp`、`Du.Abp.EntityFramework.Common`、`Du.Abp.EntityFrameworkCore` 的 `10.5.1-r2.1` 原包。SignalR、Log4Net 是模板对照中的独立组件，本轮框架闭包仅含上述 R2 三包与 Module Zero 三包。 [R2 原包登记](../../../../eng/r3_r2_reference.json)
- 首次验收拟使用 macOS ARM64、SDK `10.0.404`、`net9.0` 共享运行时和 EF Core SQLite `9.0.18`。普通源码、实包消费和固定模板 `10.2.0` 原版构建各使用自己的证据。候选实际生产源码与预发布序号在实施时锁定。 [设计](design.md)
- 三包通过后，固定模板的候选缺口预计只余 `Abp.AutoMapper`。映射兼容维护、完整模板集成、真实登录与 SQL Server、Angular、其他平台、`net10.0`、公开发行与部署留待相应阶段。 [映射兼容指南](../../../../docs/compatibility/automapper.md)
