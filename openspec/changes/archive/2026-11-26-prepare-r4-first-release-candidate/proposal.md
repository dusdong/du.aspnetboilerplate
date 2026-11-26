# R4 首次发行候选的本地制备与验收

## Why

固定免费模板已在受测组合走完原版运行、同目标换包、.NET 10 同库升级及原版回退。现有 13 个包来自多个预发布批次，内部依赖仍引用这些批次。首发前需要确定一套稳定版本，从精确提交重打，用消费者实际安装的那批文件验证兼容性。[回退正式结果](../../../../docs/maintenance/r3-original-template-rollback.md#正式运行结果) · [R4 发行顺序](../../../../docs/maintenance/fork-roadmap.md#r4发布绑定精确提交和最终产物)

## What Changes

- 以 R3 实包为比较基线，为 11 个框架包和两个映射包登记本地待发版本、各目标框架的依赖范围、生产仓库与提交。在独立目录生成 13 个主包及其符号包。
- 对实际归档核对包身份、依赖、程序集与公共 API、许可、符号和来源。冻结前确认包主页和随包安装说明指向维护版，并保留上游署名与许可。
- 用冻结的 `Du.AutoMapper` 主包复验已登记的三项安全修复。用隔离源及空缓存构建固定模板的 Web.Host 和 Migrator，并在同一批 R4 包上复跑维护版安装、升级、登录、授权查询及原版回退。
- 形成可供发布者核验的版本清单、校验值、发布说明草案和实测支持矩阵。后续发行变更负责公共包源权限及身份确认、发布 tag、上传和公开源回装。

## Capabilities

### New Capabilities

- `release-candidate-verification` 规定一组待发包如何关联生产提交、稳定依赖闭包、符号和真实消费者结果，以及交给发布者的证据。

### Modified Capabilities

## Impact

主仓协调版本、证据和模板验收。实际生产者为 `aspnetboilerplate`、`AutoMapper`、`AutoMapper.Collection` 三个子仓。固定免费模板及冻结的 Angular production 客户端继续作为消费者。第一轮以已有 macOS ARM64、SQL Server 和原版前端组合界定模板支持范围。R0、R2、R3 的历史入口与冻结输入仍用于对照。拟用稳定版本仅用于本地待发物，公开发行身份及状态须在发布阶段另行确认。[R3 包登记](../../../../eng/r3_template_net9_reference.json) · [主仓与子仓职责](../../../../docs/README.md)
