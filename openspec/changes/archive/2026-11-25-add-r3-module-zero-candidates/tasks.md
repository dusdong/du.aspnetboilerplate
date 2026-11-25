# R3 Module Zero 候选实施任务

## 1. 框架子仓生产与源码回归

- [x] 1.1 为三个项目接入显式候选模式。核对普通与候选模式的 MSBuild 属性及引用，从 `457be917` 构建固定普通 Release 对照，留存该对照与实现后普通 Release 的 DLL 及产物。验证默认 Release 自动打包、普通 `pack` 与实际 nuspec 的三份原包 ID、原依赖组及 `Microsoft.AspNetCore.App` 引用。
- [x] 1.2 实现按依赖顺序的打包入口及生产说明。核对可用序号，登记框架实施起点 `b329282`，按本批证明核验实际生产基树和源树。另按 R2 登记核验三份原包的来源树、归档与 DLL 摘要。以独立配置和空缓存执行三次真实还原及打包，逐步将已验证的正式同批主包提供给下一项目。回读四条精确框架边，并保留每步所用原归档、实际编译引用和摘要。校验三份主包与三份符号包的来源、目标、许可、图标及 PDB。将三份候选 DLL 的程序集、根命名空间、公开及受保护 API、清单资源与 1.1 对照，从 1.1 的两组普通 DLL 和候选主包 DLL 读取 Zero.Common 与 ZeroCore 各自的嵌入本地化 XML。逐程序集核对三组非空资源名集合，按完整名称比对每项原始字节的 SHA-256。冻结获准批次的实际归档、符号、清单、证明及日志。
- [x] 1.3 用普通项目引用运行 `Abp.ZeroCore.Tests` 的实际 `net9.0` SQLite 回归，保留命令、Provider 和 TRX。按全名核对 `Abp.Zero.Roles.RoleStore_Tests.Should_Get_Role_Claims` 及 `Abp.Zero.EFPlus.AbpEntityFrameworkCoreBulkRepositoryExtensions_Tests` 中以下四项均实际通过。
  - `Should_Update_All_Tenant_Roles_When_Using_BatchUpdate`
  - `Should_Update_Filtered_Entities_Using_BatchUpdate`
  - `Should_Use_MayHaveTenant_Filter_When_Updating_Entities_Using_BatchUpdate`
  - `Should_Update_All_Roles_When_MayHaveTenant_Filter_Is_Disabled_When_Using_BatchUpdate`

## 2. 主仓独立实包消费

- [x] 2.1 新增独立 `net9.0` 项目、冻结实物登记和 `r3-module-zero` 验证入口。用 1.2 的三份主包、符号和生产证据及 R2 三份原包，从独立空缓存真实还原并 Release 构建。核对唯一直接框架引用、六包六边、六份目标资产归属及实际编译和运行输出。分别记录选用的 EF Core SQLite `9.0.18`、第三方包与共享框架输入。
- [x] 2.2 实现真实 ABP 模块、Zero 实体、角色存储和 SQLite DbContext 装配。在实际消费进程中为两个有效租户各写一条角色并提交，留存事务和工作单元证据。两笔提交完成后，各租户在新的作用域、工作单元和 DbContext 中调用 `FindByIdAsync` 查询两个角色 ID。记录两次本租户命中的 ID、名称和归属，以及两次跨租户返回的 `null`。核对实际 Provider、共享运行时和六份框架 DLL 的归档、还原、输出和加载对应关系。
- [x] 2.3 集中验证可执行诊断。用受控源缺少传递包触发真实还原失败，用独立副本验证已登记 R2 或 R3 归档同版本错字节、错误框架范围或资产归属，以及成功退出但提交、独立读回或租户对照证据缺失，各自得到可定位的非零结果。验证严格复现与普通消费的运行时判据，并核对既有 R0、R2、R3 入口参数与原件仍可按各自规则使用。

## 3. 同批集成证据与维护文档

- [x] 3.1 编写维护文档和索引，分别给出从源码生产新批及使用冻结实物消费的命令，标注唯一直接框架引用与实际闭包、普通源码范围、原模板对照和后续缺口。文档可以从原始路径定位生产清单、本机证据和复验用输入。
- [x] 3.2 在 macOS ARM64 用显式 ARM64 SDK `10.0.404` 对冻结实物执行完整严格复现，实际加载 `Microsoft.NETCore.App` 和 `Microsoft.AspNetCore.App` `9.0.23`。在新目录复跑并核对期间候选字节一致，核对出参、阶段退出码、两个租户的 SQLite 读回、最终报告和进程结束状态。在维护记录登记实际版本、输入树、工具与环境、原始证据路径、摘要及未执行范围。运行单变更与全量 OpenSpec 严格校验，核对任务及工作树差异。
