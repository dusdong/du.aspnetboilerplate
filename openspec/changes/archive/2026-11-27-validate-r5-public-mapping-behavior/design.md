# 公开映射包消费对照设计

## Context

现有业务探针用固定模板的五份源码编译，另保存应用模块源码以核对配置扫描。探针项目默认使用 `net9.0`、SQLite Provider `9.0.18` 和原版包。历史 R5 消费入口还需要本地冻结批次及其摘要。新对照需要能够从公开检出和公开主包独立运行。[固定模板提取](../../../../eng/r3_automapper_business.py) · [探针项目](../../../../validation/automapper/AutoMapperProbe.csproj) · [冻结批次消费入口](../../../../eng/r5_automapper_consumer.py)

## Goals / Non-Goals

用真实的签后主包分别运行一次 R4 和 R5，向应用维护者交付可复跑的命令、每个版本的业务断言和适用范围。已有完整模板的 SQL Server、Angular、迁移和回退实测沿用各自报告。历史共享集合计划的顺序差异有独立记录，本轮结论限于独立消费者的映射调用。模板应用服务在更新映射后还会按 `RoleNames` 设置角色，用户列表则先物化实体再逐项映射。[公开回退](../../../../docs/maintenance/r5-automapper-template.md#独立消费者验收) · [已知集合差异](../2026-11-26-fix-r5-automapper-collection-context/shared-collection-plan-observation.md)

## Decisions

1. **只切换三份映射包。** 在 macOS ARM64 使用 SDK `10.0.404`、`net10.0`、.NET 运行时 `10.0.15`，两侧直接引用相同的 `Du.Abp.ZeroCore [10.5.1]` 和 `Microsoft.EntityFrameworkCore.Sqlite [10.0.15]`。唯一直接映射包是 `Du.Abp.AutoMapper`。R4 取适配器、引擎、Collection 版本 `10.5.1 / 14.0.0 / 11.0.0`，R5 取 `10.5.2 / 14.0.1 / 11.0.1`。逐项核对适配器到内核、引擎和 Collection，以及 Collection 到引擎的四条精确依赖。内核两侧均为 `Du.Abp [10.5.1]`。
2. **每侧独立还原和执行。** 为两版各建消费目录、空包缓存、Release 输出与进程，唯一配置源为 nuget.org。用公开校验清单核对该侧实际消费的维护主包归档，R5 的沿用包使用清单内的沿用记录。对三份映射 DLL 按还原图所选运行资产比较包内、Release 输出及进程加载路径上的 SHA-256。记录实际 SDK、运行时、Provider、SQLite 引擎及加载上下文，比较两侧包图。引用资产由还原图确定，同一 `net10.0` 应用可以合法选中 `lib/net8.0`。[公开签后摘要依据](../../../../docs/maintenance/r5-public-patch-review.md#主包与签后实物)
3. **复用同一业务源码和期望。** 从固定模板 `2e9536872673a7ff1986a19e798c51684d16afe5` 提取源码，两侧使用相同的模块注册、用户与角色、按键集合、SQLite 种子和查询。用户更新显式将目标 `User.IsActive` 设为 `false`，输入 `UserDto.IsActive` 设为 `true`，断言返回的原用户变为活跃，同时保留角色集合、成员和创建时间。每个进程执行自己的 SQLite 内存数据库，保留实际命令、参数、返回列、投影表达式与物化结果。历史入口保留原默认参数。[用户与按键集合断言](../../../../validation/automapper/Program.cs) · [投影与 SQL 断言](../../../../validation/automapper/Projection.cs)
4. **每版独立判定，再比较差异。** 即使两版结果相同，两侧也须分别命中事先固定的期望。用单独副本故意给出错误的包摘要，验证入口能在采信业务结果前返回非零并指出包名。正式输入及发行清单保留原件。
5. **业务断言失败时保留现场。** 当前探针在三项业务均通过后才写报告，旧入口遇到首个失败进程就退出。新入口按侧记录已完成的业务结果，投影在物化后、校验前保存实际 SQL、参数、返回列、投影表达式和结果行。一侧断言失败时记录预期、实测和未执行项，继续完成另一侧，再汇总退出码。在独立反例中只改第一侧的预期列顺序，两侧仍走真实进程和 SQLite 查询。复核第一侧前两项通过、投影失败且原始结果可回读，第二侧三项通过，总入口返回非零。正式记录集中在 `docs/maintenance/r5-public-mapping-behavior.md`，给出公开复跑命令、原始报告定位和两侧逐项结果。

## Risks / Trade-offs

历史投影在 EF Core 9 上执行。若 EF Core 10 改变取列、排序或 `FullName` 的计算位置，保存两侧 SQL 与表达式，先区分两版共同变化和单侧变化。包图多出版本差异、实际运行时不符或 DLL 对不上时，先修正消费环境并复测。业务差异持续存在时保留最小业务输入与失败阶段，由维护者判断是否另立修复。
