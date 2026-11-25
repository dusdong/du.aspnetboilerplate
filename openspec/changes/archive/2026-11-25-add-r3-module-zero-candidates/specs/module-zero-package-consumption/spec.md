# Module Zero 候选包消费

## Purpose

维护者可以用可追溯的 Module Zero 预发布包验证经典 ABP 角色持久化与租户隔离，并从实际使用的程序集追溯到该批候选及其核心依赖，为固定模板后续集成提供可复核的组件验收依据。

## ADDED Requirements

### Requirement: Module Zero 可生成同批维护候选

框架 SHALL 提供显式入口为三个 Module Zero 项目生成同版本的 `net9.0` 本地候选和配套符号包，并保留其普通项目引用、构建及打包契约。

#### Scenario: 按依赖顺序从锁定实物生产候选

- **WHEN** 维护者选择未分配的 `10.5.1-r3.N` 预发布版本和登记的 R2 原包，执行显式候选生产
- **THEN** `Du.Abp.Zero.Common` 精确依赖 `Du.Abp [10.5.1-r2.1]`，`Du.Abp.ZeroCore` 精确依赖同批 `Du.Abp.Zero.Common`，`Du.Abp.ZeroCore.EntityFrameworkCore` 精确依赖同批 `Du.Abp.ZeroCore` 和 `Du.Abp.EntityFrameworkCore [10.5.1-r2.1]`。这四条为新包中全部直接框架边，每个候选只有 `net9.0` 库目标
- **AND** 实际编译使用的框架资产可追溯到已核对摘要的 R2 原归档及前一步生成的同批正式主包。三份主包与三份符号包可核对摘要、源码与仓库身份，主包包含对应许可与图标。R2 原包的来源树与摘要按 R2 登记核验，本轮候选的生产基树及实际源树按本批源码证明核验
- **AND** 候选的程序集名、版本、根命名空间、公共及受保护 API 和清单资源名称与固定维护源码的同目标普通 Release 对照一致
- **AND** 对 `Abp.Zero.Common` 和 `Abp.ZeroCore` 各自的嵌入本地化 XML，固定普通 Release、修改后的普通 Release 和候选主包内的 `net9.0` DLL 均有相同的非空资源名集合。按完整名称读取的每项资源原始字节的 SHA-256 在三者中一致

#### Scenario: 沿用普通源码入口

- **WHEN** 源码调用方从三个原项目入口执行常规 `net9.0` Release 构建及打包
- **THEN** 三个项目继续使用原项目引用、原包 ID、原 `net9.0` 目标、既有程序集和普通 Release 自动打包属性，普通包依赖组沿用原框架依赖 ID 和原依赖声明
- **AND** 既有 Module Zero SQLite 具名源码回归实际执行并通过

### Requirement: 独立消费者还原唯一框架闭包

主仓 SHALL 从隔离空缓存与受控来源还原最小消费者，核对冻结实包的版本、来源、依赖边及实际选中资产。

#### Scenario: 从真实主包还原并构建

- **WHEN** 在新运行目录从冻结候选和已核对的 R2 实包还原，消费者只直接引用顶层 `Du.Abp.ZeroCore.EntityFrameworkCore` 这一框架包
- **THEN** 框架图恰有本轮三个 Module Zero 包和三个 R2 包，共六条框架依赖边。四条新包依赖边与候选说明一致，另外两条为 `Du.Abp.EntityFrameworkCore → Du.Abp.EntityFramework.Common → Du.Abp`，三个 R2 包均解析到 `10.5.1-r2.1`
- **AND** 六个框架包均由指定本地源提供并选中其 `net9.0` 资产。六份框架程序集各有唯一来源，消费者仅通过包取得框架引用
- **AND** EF Core SQLite `9.0.18`、实际第三方依赖与共享框架均可按各自来源、版本及所选资产核对

#### Scenario: 冻结输入或还原资产与登记不符

- **WHEN** 必需归档缺失或字节与登记不符、框架范围或闭包不符、混入原版框架包、目标错误或程序集归属不唯一
- **THEN** 验证返回非零，定位受影响的包、依赖边或资产，并记录已取得证据及未执行步骤

### Requirement: Module Zero 在 SQLite 中提交并按租户读回角色

维护候选 SHALL 支持独立 `net9.0` 进程正常初始化 ABP、Module Zero 及 EF Core，在 SQLite 中经角色存储和真实工作单元提交角色，并在新作用域读回当前租户结果。

#### Scenario: 两个已持久化的有效租户各有已提交角色

- **WHEN** 消费者在一份独立 SQLite 数据库中建立两个有效租户，并为每个租户通过 DI 取得真实角色存储，在启用租户过滤的 ABP 工作单元中写入角色。角色写入使用的关系型事务实际完成提交
- **THEN** 两笔事务都已提交后，两个租户各用新的作用域、工作单元和 DbContext，通过真实角色存储 `FindByIdAsync` 查询两个已提交的角色 ID。两次本租户查询均返回 ID、名称和归属正确的角色，两次跨租户查询均返回 `null`
- **AND** 运行记录可以核对实际 SQLite Provider、数据库标识、事务和工作单元完成顺序、写入值及以新 DbContext 查得的两组正反结果
- **AND** 运行中实际加载的六份框架 DLL 均能逐项追溯到同轮 Release 输出、还原选中资产及冻结主包中相应的 DLL 字节

### Requirement: Module Zero 的本地验收可按冻结批次复验

主仓 SHALL 提供针对同一批实物的消费复验入口和证据报告，全部必需检查通过时验收才返回零。

#### Scenario: 从冻结候选复验通过

- **WHEN** 使用指定 `dotnet` 从冻结主包和符号包在新目录复跑，包、资产、实际加载和角色工作单元检查均通过
- **THEN** 报告登记实际候选树、包与符号摘要、命令及退出码、SDK、操作系统及进程架构、实际共享运行时、Provider、资产和业务证据，并记录执行与未执行的范围
- **AND** 首次验收和严格复现使用 macOS ARM64、SDK `10.0.404`、`net9.0` 以及实际加载的 `Microsoft.NETCore.App` 和 `Microsoft.AspNetCore.App` `9.0.23`。普通消费复验按当轮实际加载的兼容 `9.0.x` 版本登记并限定结果范围

#### Scenario: 进程成功退出但持久化或隔离证据不足

- **WHEN** 消费进程成功退出，但缺少真实工作单元提交、独立上下文读回、任一租户的本租户角色读回、跨租户查询返回 `null` 的结果或必要加载证据
- **THEN** 整体验收返回非零，指出缺失或冲突的证据并保留可用结果
