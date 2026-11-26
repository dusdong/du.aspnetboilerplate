# R5 映射三包公开发行准备

## Why

R5 在公开旧引擎上确认了集合映射随预热顺序变化的业务偏差，三个本地候选已通过独立消费者和固定模板验收。要把修复交给只使用 nuget.org 的用户，还需纠正引擎包内的本地源安装指引，并让发行核验按本次实际替换的三个包工作。[固定模板验收](../../../../docs/maintenance/r5-automapper-template.md) · [引擎包内说明来源](../../../../AutoMapper/src/AutoMapper/ApiCompat/README.r5-package.md)

## What Changes

- 从包含公开安装说明的干净引擎新提交制备待发件，对账原批次、最终源码、实际归档差异和独立登记的摘要。
- 登记三个新包的六份上传归档、三个 PDB 目标和十个沿用的 R4 公开包。演练 `Du.Abp [10.5.1]` 证据缺失或不符时暂停适配器，以及补证后续作。
- 用 R4 已签名实物和隔离样本演练将交付的同一条纯 nuget.org 消费命令。交付安装说明草案、拟用 tag 与目标提交及 gitlink 的核对结果、分步发行命令和待公开验证项，供维护者决定是否发行。

## Capabilities

### New Capabilities

### Modified Capabilities

- `release-candidate-verification` 增加部分包升版时的待发清单、实物复验和发布前演练要求。

## Impact

主仓负责清单、核验入口与发行交接。AutoMapper 子仓负责引擎包的公开安装说明。Collection 与经典框架适配器按实际产物差异复验。消费范围沿用固定模板、macOS ARM64、SQL Server 和冻结 Angular 客户端。本变更在本地待发交接处结束，主仓 tag、NuGet 上传和 GitHub Release 归入另行决定的发行工作。
