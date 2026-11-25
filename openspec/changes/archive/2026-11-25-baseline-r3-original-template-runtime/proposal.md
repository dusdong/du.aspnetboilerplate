# R3 原版模板运行对照

## Why

固定模板的 11 个 ABP 包已有对应的独立维护候选，原版 Web.Host 也已完成还原和 Release 构建。开始同目标换包之前，还缺一组可重放的原版结果，用于判断登录、租户用户查询或数据恢复的差异来自哪一步。[当前路线](../../../../docs/maintenance/fork-roadmap.md#r3验证升级路径和实际消费者) · [原版构建证据](../../../../docs/maintenance/r3-web-host-baseline.md)

## What Changes

- 从固定模板提交构建原版 `net9.0` Web.Host、Migrator 和锁文件指定的 Angular 客户端，在隔离测试环境中以 `Development` 启动 Release Host，配合 Angular production 产物和独立 SQL Server 测试库运行。
- 通过真实浏览器选择租户并登录，打开受 `Pages.Users` 保护的用户列表。用唯一关键词搜索合成用户，将带该关键词的列表响应和页面用户名与 SQL Server 中的预期用户核对，并核对服务端会话身份。
- 保存登录前的数据恢复点，恢复到另一空库，从新浏览器会话复跑同一路径，并用两库的成功登录记录确认本轮登录写入恢复库。交付冻结输入、恢复介质标识、复跑命令和两轮结果，供下一轮在同一目标框架替换维护包时对照。

## Capabilities

### New Capabilities

- `template-runtime-baseline` 规定固定原版模板在真实客户端、Web.Host 和 SQL Server 之间可复现的运行行为及数据起点。

### Modified Capabilities

## Impact

主仓负责复用构建验证入口、编排运行和记录证据。`module-zero-core-template` 提供固定的源码、迁移、种子和 Angular 锁文件。首次计划使用 macOS ARM64 应用进程和一个允许创建并恢复本轮测试库的 SQL Server 实例，执行时登记实际环境。

通过本轮后进入 `net9.0` 同目标换包。.NET 10 / EF Core 10 升级、升级后切回旧应用及公开发行分别沿用后续阶段。原版构建基线和各独立候选的验收报告继续保留各自的输入与结论。[模板构建稳定规范](../../../specs/template-host-baseline/spec.md)
