# R3 AutoMapper 候选设计

## Context

主仓规划基点为 `d54f782fe91cbf0230680c94256913ce46b0581d`。生产适配器使用维护框架，业务对照使用固定模板实际选择的原版 ABP `10.2.0`。两组引用独立还原、编译并在独立进程中运行，避免同名程序集和静态 Mapper 跨组共享。[提案](proposal.md) · [原版依赖图](../../../../docs/maintenance/r3-web-host-baseline.md)

| 组件 | 主仓 gitlink | 本轮源码起点与用途 |
| --- | --- | --- |
| AutoMapper | `79d10deec5881a617c38e7373f354694044bf83d` | 从 v14.0.0 的 `bf76a5819e1bad7af7db5382bf0f3a0178048a15` 派生维护源码。参考项目目标为 `net8.0`，根目录含 `LICENSE.txt`。 |
| AutoMapper.Collection | `5301edbc689a9696bdd7c396452669434e75989a` | 从 v11.0.0 的 `eafbf005becf73f989e1b1c0d52e8699439f837c` 派生维护源码。参考项目目标为 `net8.0`，含 `LICENSE`，原版依赖范围为 `AutoMapper [14.0.0, 15.0.0)`。 |
| aspnetboilerplate | `819c64cf527b6918a5eafbf42550c93400f1fb75` | `Abp.AutoMapper` 的普通项目为 `net9.0`，直接依赖内核、引擎和 Collection。 |
| module-zero-core-template | `2e9536872673a7ff1986a19e798c51684d16afe5` | 从该提交取 `UserMapProfile`、`UserDto`、`CreateUserDto`、`User` 的原文件，并记录文件摘要。 |

## Goals / Non-Goals

交付物是本地冻结的映射候选、可重复的单一包闭包和原版/候选业务结果。范围限定在 macOS ARM64 的独立消费者。完整 Web.Host、SQL Server、Angular、运行时升级与整套应用回退由后续模板变更验收。数据库投影直接依赖 EF Core SQLite，无需增加映射器的 EF 专用扩展包。

## Decisions

1. **源码按参考提交派生。** 引擎和 Collection 各以表中固定参考提交开始维护。当前默认分支的引擎许可声明和 Collection 依赖范围已与参考线不同。为拟带入的每项补丁保留来源、适用许可、受影响组件和验证结果。为兼容指南登记的 GHSA-rvv3-g6hj-g44x、GHSA-6vhm-j9h7-f9gh、GHSA-gpwp-5797-mjff 分别给出修复或不受影响的证据，记录正常映射及有意改变的异常契约。按增量规范用冻结 `Du.AutoMapper` 主包加载的 DLL 在隔离子进程复验约定行为，记录包与加载 DLL 的 SHA-256、结果、退出状态和超时情况。对于约定可恢复的失败，在同一子进程复用同一个 Mapper 完成下一次正常映射。来源、许可、实包证据或处置结论缺失时，该项验收失败。[参考版本登记](../../../../docs/maintenance/release-baseline.json) · [映射维护指南](../../../../docs/compatibility/automapper.md)

   GHSA-gpwp-5797-mjff 的 CLR 低栈分支采用三项组合证据。检查冻结主包中 `Mapper.MapCore` 的 IL 调用，核对该调用在 .NET 9 官方文档中的异常契约，并用加载同一冻结 DLL 的子进程验证应用层收到测试注入的同类型异常对象或含该对象的包装链，随后复用同一 Mapper 得到预期值。实际 CLR 低栈触发未观测，须在记录中注明。该分支的任一证据缺失、断言失败、非预期退出或超时均导致验收失败。其余行为与异常按各自约定动态复验。[.NET 9 官方异常契约](https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices.runtimehelpers.ensuresufficientexecutionstack?view=net-9.0)
2. **先编译上游包，再用其实物编译下游。** 本地包名采用 `Du.AutoMapper`、`Du.AutoMapper.Collection`、`Du.Abp.AutoMapper`。依次生产引擎、Collection、适配器及符号包。Collection 精确引用本批引擎，适配器精确引用本批两份映射包与冻结的 `Du.Abp [10.5.1-r2.1]`。本地候选版本分别沿用 `14.0.0-r3.N`、`11.0.0-r3.N`、`10.5.1-r3.N`，生产时按现有 R3 分配记录选择未使用序号，清单登记实际版本。适配器的三条内部依赖及 Collection 的一条引擎依赖在各自主包 nuspec 中均须声明为 `[精确版本]`，并与消费者还原图逐边对应。普通构建和打包继续可用。比较各组件同源普通 Release 和候选的程序集身份、强名称、公有 API、资源及默认依赖。将生产来源、补丁、包内许可和摘要登记在同一清单，并保留下游编译实际使用的引用路径和摘要。
3. **最小依赖验收和真实模板类型分别还原。** 最小消费者只直接引用适配器，用独立 NuGet 配置和空缓存验证 4 个维护包、4 条内部边，随后构建、启动经典 ABP 模块，解析 Castle 注册的服务，调用静态入口并完成按键集合映射。在这些调用完成后，枚举当前进程所有 `AssemblyLoadContext` 中简单名为 `AutoMapper` 的程序集，按程序集实例计数。要求恰好一个，并记录其实例所属加载上下文、全名、路径及文件 SHA-256。模板 `User` 派生自 Module Zero 的 `AbpUser<User>`。业务消费者额外引用原版 `Abp.ZeroCore 10.2.0` 或已验 `Du.Abp.ZeroCore 10.5.1-r3.3`，按各自包图提供其传递依赖。两个业务消费者均编译表中同一组模板文件，使用 `Configurators` 和 `AddMaps` 扫描，保留真实角色类型和重复的 `CreateMap`。候选侧的维护包全部来自登记实物。[模板配置](../../../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.Application/AbpProjectNameApplicationModule.cs) · [Module Zero 依赖表](../../../../docs/maintenance/r3-module-zero-candidates.md#消费闭包与运行)
4. **先固定原版的业务结果。** 两组使用相同输入和已知预期。若原版无法完成调用，记录失败并修订场景后重新建立原版基线。分别验证三种行为。
   - 使用模板 `UserMapProfile` 更新已有用户，检查目标引用、普通字段、原角色集合及创建时间。
   - 两组编译相同的独立集合测试类型，启用 `AddCollectionMappers`，由 ABP 扫描源类型的 `AutoMapKey`。用新增、移除和原地更新断言验证按键匹配及 Collection 扩展的反射加载。模板用户的 `Roles` 由前一项验证忽略更新。
   - 使用固定模板的 `User`、`UserDto` 和相同 SQLite 种子，先对实体查询筛选、排序，再调用 `IObjectMapper.ProjectTo<UserDto>` 并物化。原版报告保存实际执行的 SQL、参数、读取的列、返回值及顺序，确认筛选和排序落在 SQLite。结合投影表达式和执行 SQL 标明 `[NotMapped]` 属性 `FullName` 的值在哪里计算。候选须匹配原版取列、计算位置和已知结果，SQL 别名与空白允许差异。
5. **复用主仓验证入口。** 在 `eng/verify.py` 增加拟定的 `r3-automapper` profile，复用 R2/R3 已有的包摘要、还原资产及程序集核对逻辑。首次环境沿用 SDK `10.0.404` 和 EF Core SQLite `9.0.18`，记录实际加载的运行时、Provider 及本机架构。源码回归复用框架 `Abp.AutoMapper.Tests` 及两个映射组件受影响的测试。验证同一冻结批次在独立空目录的第二次消费。[R2 实包登记](../../../../eng/r3_r2_reference.json)

## Risks / Trade-offs

- **包名与程序集身份各自独立。** 两个映射参考项目都指定强名称签名，Collection 还按包名依赖引擎。单看 DLL 文件名会漏掉错误绑定。验收同时检查 nuspec、还原结果、最终程序集全名及加载文件摘要。
- **ApiCompat 在干净 macOS 检出上的执行条件。** v14 项目直接调用 `ApiCompat/PreBuild.sh`，固定提交中该文件的 Git 模式为 `100644`，脚本使用的 `readarray` 在本机 `/bin/bash` 3.2 中不可用。任务 1.1 先验证可从干净检出重复调用的入口，固定历史参考包的 ID、版本、包内 DLL 路径及两者的 SHA-256。普通 Release 和候选引擎构建均须实际运行 ApiCompat，记录比较输入和结果。参考 DLL 只用于 API 比较，与下游编译使用的候选包分别登记。
- **不同数据库的翻译能力各异。** SQLite 的实测结果可复用测试数据与断言。SQL Server 的查询翻译和真实登录由完整模板另行验证。

## Migration Plan

在隔离消费者切换两套包源和依赖版本，成功后保存冻结包及复跑命令。若候选失败，用原版输入在独立目录重跑相同场景，保留失败阶段和输入。交付时先记录各子仓已验源码树与可取得的对应提交，再由主仓固定 gitlink 和验收结果。模板本身的包引用、数据库及公开发行留待各自阶段。
