# R3 第二包：SignalR 与 Log4Net 候选

## Why

R3 首包已实测原版 Web.Host 的依赖与构建，查明六个维护版包缺口。SignalR 和 Log4Net 均只直接依赖核心 `Abp`，可以先用已验 R2 实包补齐这两个缺口，分别验证真实连接、通知送达和日志落盘。两项通过后，原版 Web.Host 所需组件中仍缺本地候选实包的数量从六个减至四个。[R3 首包证据](../../../../docs/maintenance/r3-web-host-baseline.md) · [R2 消费验收](../../../../docs/maintenance/r2-core-package-consumption.md)

## What Changes

- 为两个现有组件增加独立的本地候选打包入口，首选批次 `10.5.1-r3.1`。每个包只含 `net9.0` 资产并附符号包，保留普通源码入口、程序集身份、命名空间、API 和资源。另以普通模式实际打包，核对原包身份及依赖。
- 两个候选均直接依赖确切的 `Du.Abp 10.5.1-r2.1` 实包。轻量独立消费者另用 R2 的 `Du.Abp.AspNetCore` 及其传递的 `Du.Abp.Web.Common` 接入 ABP 宿主。
- 在主仓统一验证器添加定向入口，以已锁定的同一实际批次和 R2 原包完成干净还原、Release 构建及本机 macOS ARM64 上的 Kestrel 运行。首次验收显式使用 R2 的 ARM64 `dotnet`，记录宿主实际加载的共享运行时。核对包与程序集来源、SignalR 在线生命周期、经宿主通知配置选取的通知器送达的负载、Log4Net 文件内容以及原版与维护版的依赖差异。

## Capabilities

### New Capabilities

- `web-host-integration-package-consumption` 约定 SignalR 与 Log4Net 维护候选的打包、实际消费和运行证据。

### Modified Capabilities

## Impact

- 框架子仓涉及 `Abp.AspNetCore.SignalR`、`Abp.Castle.Log4Net` 及独立打包入口。普通构建对照固定在 `457be917b46c4fb6237831baac5abb848ffe1c4b`。模板子仓 `2e9536872673a7ff1986a19e798c51684d16afe5` 提供接入方式及原版依赖参照。[设计](design.md) · [原版依赖清单](../../../../docs/maintenance/r3-web-host-baseline.json)
- 主仓新增最小消费项目、验证入口和本轮验收文档，沿用 R2 实物摘要登记。R2 核心候选和原版 Host 基线继续适用各自的验证入口和已验范围。[R2 规范](../../../specs/core-package-consumption/spec.md) · [模板基线规范](../../../specs/template-host-baseline/spec.md)
- 其余四个缺口、完整模板同批闭包与迁移、真实登录和数据库、Angular、其他平台、`net10.0`、公开发包、部署和 CI 扩展留待后续阶段。
