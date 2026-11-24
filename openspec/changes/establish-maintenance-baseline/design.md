# 首条维护线基线设计

## Context

主仓当前固定的框架提交为 `6c4580c5e7ea41154696c071a53fd200059a768b`，对应上游 `v10.5.1`。首批后端源码项目均声明 `net9.0`，本机在框架目录解析到 .NET SDK `9.0.306`。SDK 解析规则见 [global.json](../../../aspnetboilerplate/global.json)，阶段范围见[首版维护路线](../../../docs/maintenance/fork-roadmap.md)。

按当前 `ProjectReference`，`Abp.AspNetCore` 经 `Abp.Web.Common` 依赖 `Abp`，`Abp.EntityFrameworkCore` 经 `Abp.EntityFramework.Common` 依赖 `Abp`。目标闭包因此包含这五个框架包。

| 组件 | 当前或参考来源 | 用途 |
| --- | --- | --- |
| AutoMapper | `v14.0.0` 对应 `bf76a5819e1bad7af7db5382bf0f3a0178048a15` | 现有适配器声明的 MIT 参考版本，保留映射行为的对照输入 |
| AutoMapper.Collection | `v11.0.0` 对应 `eafbf005becf73f989e1b1c0d52e8699439f837c` | 源码依赖范围为 `[14.0.0, 15.0.0)`，当前检出声明的范围为 `[15.0.1, 17.0.0)` |
| Angular 适配器 | `12.1.0` 对应 `afbd23ea9711e9d94259d0f0b6afcbab9a0617fc` | 引用 Angular `^19.1.7` 的参考提交，当前检出声明要求 Angular 21 |
| 免费模板 | `2e9536872673a7ff1986a19e798c51684d16afe5` | `angular/package.json` 声明 Angular 19、适配器 `12.1.0` 和 `abp-web-resources` `^6.1.0` |
| Samples | `e53d60895d354eb066c39d73c9e38c0c133fc69b` | 多 DbContext 与拦截器专项测试的参考源码 |

## Goals / Non-Goals

**Goals**

- 取到可用于迁移对照的原版框架构建、程序集身份和关键行为结果。
- 将候选包身份与直接内部依赖集中登记，供后续打包和干净消费验证复用。

**Non-Goals**

- .NET 10 迁移、映射修复、Angular 升级、生产消费验证及公开发包分别进入后续变更。
- Module Zero、额外数据库 Provider 和可选集成按消费方实际依赖纳入支持范围。

## Decisions

### 集中记录来源、包映射和验证证据

在 `docs/maintenance/release-baseline.json` 维护一份结构化记录。主仓 Git 子模块引用是当前提交的依据。基线记录固定比较用的历史框架提交和参考组件提交，并标注各自用途。包条目记录源码路径、原 `PackageId`、计划 `PackageId`、`AssemblyName`、`RootNamespace`、原目标框架和内部包依赖。隐式属性以 MSBuild 求值核对。

JSON 便于后续跨平台打包和依赖检查复用。现有文档引用这份记录承载的结论，版本和包映射在此处维护。

### 围绕五个框架包取得原版对照

在框架固定提交的独立检出中还原五个源码项目和三个回归套件所需的项目图。该提交的 `NuGet.Config` 未声明包源，源码树未提供 `packages.lock.json`。从实际还原生成的 `project.assets.json` 按项目、TFM 和适用的 RID 提取各目标的 `type: package` 条目，结合项目直接依赖标明直接或传递关系。记录本次还原采用的有效包源（脱敏）、SDK、相对工作目录及还原参数。清单按包 ID 排序，供另一检出核对解析结果。构建和测试沿用本次还原结果。

从五个 Release DLL 的元数据生成机器可读的公共 API 清单。按程序集记录名称、版本、区域性、公钥标记、对外可见的类型全名与成员签名（含公开和受保护成员、重载参数、返回类型及泛型约束），并收录清单资源名。按稳定顺序输出，保存提取工具版本、命令和输入 DLL 的 SHA-256。复验时先核对同一 DLL 两次提取的结果，再用仅修改一条公开签名的清单副本确认差异可定位。

将 API 与还原清单放在 `docs/maintenance/release-baseline.json` 旁，由基线记录按相对路径引用。在同一环境执行 `Abp.Tests`、`Abp.AspNetCore.Tests` 和 `Abp.EntityFrameworkCore.Tests`，记录实际命令、环境和结果。EF Core 套件使用 SQLite Provider。

### 按实际消费证据扩大支持范围

模板固定提交中的下列项目直接声明 ABP 包版本 `10.2.0`。实施时保留项目路径与声明版本，标明首批包覆盖情况。

| 模板后端项目 | 已有首批映射 | 首批范围外的直接引用 |
| --- | --- | --- |
| Core | 无 | `Abp.AutoMapper`、`Abp.ZeroCore.EntityFrameworkCore` |
| Web.Core | `Abp.AspNetCore` | `Abp.ZeroCore`、`Abp.AspNetCore.SignalR` |
| Web.Host、Migrator（各自引用） | 无 | `Abp.Castle.Log4Net` |
| Web.Mvc | 无 | `Abp.HangFire`、`Abp.RedisCache`、`Abp.Castle.Log4Net` |
| Tests | 无 | `Abp.TestBase` |
| Web.Tests | 无 | `Abp.AspNetCore.TestBase` |

Web.Host 通过 Web.Core 及其项目引用使用 Core。直接替换五包时，保留的上游模块仍可能传递引入原版框架包。基线阶段把这项依赖缺口标为待处理。独立发包阶段使用干净的最小消费项目，从候选包源引用 `Du.Abp.AspNetCore` 和 `Du.Abp.EntityFrameworkCore`，由传递依赖覆盖其余三个包，核对还原图只有预期的五个框架包及其程序集。完整模板留到所选入口的直接和传递框架依赖闭合后验收。多 DbContext 和拦截器样例继续用于专项回归。

## Risks / Trade-offs

- 固定上游仍可能遇到依赖源或环境差异。记录实际 SDK、还原来源、失败证据和复现条件，受影响项目保持待验证或失败状态。
- 当前两个映射子模块和适配器的检出版本与存量组合有差异。参考提交单独登记，在相应变更中核对应用的真实解析版本、许可证和回归结果。
- 现有 SQLite 测试能覆盖部分查询和工作单元行为。并行运行、其他数据库 Provider 和部署环境的支持范围由对应运行记录确认。
