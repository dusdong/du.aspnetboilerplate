# R5 公开补丁后的首轮维护审查

## Why

消费者已能安装 `v10.5.2`，而上次公告审查对应 `v10.5.1`。三个映射包的发行版本发生了变化，需要用本次公开消费的依赖图重新判断旧公告和新修订对实际应用的影响。[公开发行验收](../../../../docs/maintenance/r5-public-release.md) · [上次审查](../../../../docs/maintenance/r5-runtime-migration-review.md)

## What Changes

- 以发行标签、公开校验附件和固定模板的四个入口为依据，逐项说明三份新包与十份沿用包的来源、上游身份及依赖变化。
- 按实际包 ID 和解析版本匹配新图，对维护包另按上游原名及源码基点版本匹配公告。接续六条上游分支和共享运行时公告，并逐项核对上轮暂缓或待核实事项的复查条件及其对本轮决定的影响。
- 在主仓交付本版维护审查记录，给出包补丁决定，以及模板、运行环境和应用维护者各自需要采取的行动。

## Capabilities

### New Capabilities

### Modified Capabilities

- `maintenance-release-review` 增加跨公开版本接续审查的验收场景，规定局部补丁中更新包与沿用包可复用哪些证据。

## Impact

审查对象为 `aspnetboilerplate`、`AutoMapper`、`AutoMapper.Collection` 三个生产仓发行的 13 个包。消费者为固定的 `module-zero-core-template`，覆盖 `net9.0` 和 `net10.0` 的 Web.Host、Migrator。业务证据沿用已验的 macOS ARM64、SQL Server 和固定 Angular 组合。上游的新终点、公告覆盖和下一次补丁决定均待本轮实施时核定。
