# 让存量应用维护者独立演练公开映射包回退

## Why

公开 R4 → R5 → R4 已在固定模板上实测，但复跑命令需要发布者留存的两版冻结目录、历史报告和 Angular 构建产物。现有公开安装指南止于新库迁移和 Swagger 检查。使用 R4 的应用维护者还需要一条只靠公开材料，就能验证“升级后写入的数据可由旧版读回”的路径。[发布者复跑入口](../../../../docs/maintenance/r5-automapper-template.md#公开包切换复跑) · [R5 安装指南](../../../../docs/maintenance/r5-public-install.md)

## What Changes

- 给出一条可从头执行的路径。读者用固定模板和公开 R4 在自己的专用空库建立 `net10.0` 基线，保留两个入口的运行产物，再用公开 R5 接续同库。
- R4 创建用户 A。R5 查回 A，创建并查回 B。切回先前保存的 R4 产物后，同一租户管理员用一次新登录分别查回 A、B。
- 在无发布者工作目录的环境中按指南原文实跑，记录指南摘要、输入和逐阶段结果。三阶段及输入错误时的停止检查均通过后，登记独立消费者验收通过。

## Capabilities

### New Capabilities

### Modified Capabilities

- `automapper-package-consumption` 增加普通消费者按公开输入独立验证已发布映射补丁回退的要求。

## Impact

交付在主仓的消费者文档与实跑记录。使用 `aspnetboilerplate`、`AutoMapper` 和 `AutoMapper.Collection` 已发行的 R4、R5 包，以及 `module-zero-core-template@2e953687`。拟验组合为 macOS ARM64、.NET 与 ASP.NET Core `10.0.15`、SQL Server Developer `16.0.4236.2` 和该模板的后端 API。维护包处置沿用现有决定。[维护决定](../../../../docs/maintenance/r5-public-patch-review.md#本轮维护决定)
