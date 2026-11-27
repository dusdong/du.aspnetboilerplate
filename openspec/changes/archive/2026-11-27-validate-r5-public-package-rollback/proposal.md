# 验证公开 R5 映射补丁的同库回退

## Why

固定模板已分别验证 R4、R5 公开包，也用 R5 本地候选做过一次同库回退。存量应用在公开 `v10.5.2` 上新增业务用户后，切回公开 `v10.5.1` 的管理员能否在同一租户查到该用户，仍需实际验证。[发行消费与回退证据](../../../../docs/maintenance/r5-public-release.md#公开消费与回退证据) · [历史同库切换](../../../../docs/maintenance/r5-automapper-template.md#支持范围与公开发行交接)

## What Changes

- 在主仓模板验收入口增加公开 R4 → 公开 R5 → 公开 R4 的三阶段路径，固定运行时、前端和隔离测试库，每段从独立空缓存还原对应发行的签后包，并逐入口比较完整依赖图。
- R4 创建用户 A，R5 查回 A 并创建、查回用户 B。验证回退后的 R4 能在同一租户独立查回两人，使每次查询可追溯到创建回执、页面和实际数据库连接。若创建成功后查询失败，报告保留已取得的证据和未执行阶段。
- 在现有模板手册登记消费步骤、写入边界、实际组合和结果，使存量维护者能判断自己的回退路径。

## Capabilities

### New Capabilities

### Modified Capabilities

- `automapper-package-consumption` 为“固定模板的补丁结论绑定同批实包”补充两个公开版本间切换、回退后读取新版写入及失败判定场景。

## Impact

实现和证据集中在主仓。三个生产子仓为 `aspnetboilerplate`、`AutoMapper`、`AutoMapper.Collection`，消费项目为固定的 `module-zero-core-template`。验收对象是两个已发行组合中的 Web.Host 和 Migrator，仅拟验证 macOS ARM64、固定 .NET 10 服务版本、SQL Server 和冻结 Angular 客户端。该组合的维护包决定及服务公告续查仍以上轮归档为准。[维护决定](../../../../docs/maintenance/r5-public-patch-review.md#本轮维护决定)
