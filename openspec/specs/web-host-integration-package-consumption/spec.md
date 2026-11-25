# web-host-integration-package-consumption Specification

## Purpose

维护者能够从可追溯的 SignalR 与 Log4Net 候选实包复跑独立宿主，并核对候选身份、解析资产、实际程序集加载和用户可见的通知及日志行为。证据关联所测批次与环境，为后续完整 Web.Host 迁移提供组件对照。

## Requirements

### Requirement: 两个集成组件可生成独立的维护候选

框架 SHALL 通过显式入口生成同批 `Du.Abp.AspNetCore.SignalR`、`Du.Abp.Castle.Log4Net` 本地候选及配套符号包，保留两个组件的 `net9.0` 目标与普通源码入口。

#### Scenario: 从可追溯源码生成新候选批次

- **WHEN** 维护者选择未使用的 `10.5.1-r3.N` 版本和已验 `Du.Abp 10.5.1-r2.1` 归档
- **THEN** 两个候选各只有一个 `net9.0` 目标，且包的该目标依赖组各有一条直接框架边，精确依赖 `Du.Abp [10.5.1-r2.1]`
- **AND** 生产者实际编译所选的核心资产可追溯到该 R2 归档。候选与符号包的摘要及包内源码、仓库、许可和图标可核对
- **AND** 两个候选的程序集名、版本、根命名空间、公开及受保护 API 和清单资源与固定维护源码同目标普通 Release 对照一致

#### Scenario: 沿用普通构建和打包

- **WHEN** 源码调用方在未启用候选模式时从两个原项目入口构建，并各执行一次 Release `pack`
- **THEN** 两个项目保留原包 ID、核心项目引用、目标、程序集身份和普通第三方依赖声明。R2 五包及其入口沿用原有行为
- **AND** 两份实际 `.nupkg` 的 `.nuspec` 分别声明 `Abp.AspNetCore.SignalR` 和 `Abp.Castle.Log4Net`，`net9.0` 组各自仅依赖一个框架包 `Abp`。SignalR 保留 `Microsoft.AspNetCore.App` 框架引用，Log4Net 保留 `log4net` 自 `3.3.2` 起的原依赖范围

### Requirement: 消费者从受控来源解析唯一框架闭包

主仓 SHALL 用独立空缓存和受控源对当前两个候选及所需 R2 宿主包做实际 NuGet 还原，核对每个框架包的解析版本、内容与资产归属。

#### Scenario: 从同一批实际包干净还原并构建独立消费者

- **WHEN** 验证器在新运行目录使用已锁定的同一批两份候选、两份符号包及来源证据，并取得确切的 R2 实包子集
- **THEN** 消费者直接引用两个新增候选及 `Du.Abp.AspNetCore 10.5.1-r2.1`。四条内部边对应两个候选各自到核心的边，以及 `Du.Abp.AspNetCore → Du.Abp.Web.Common → Du.Abp`，共同解析到唯一的 `Du.Abp 10.5.1-r2.1`
- **AND** 五个包均来自其指定本地源及对应的实包字节，应用图中没有其他框架包或框架项目引用。第三方包来源、声明范围、选中版本和资产均可复核
- **AND** 实际使用的五个框架 DLL 和 `log4net.dll` 各自可从包内资产追溯至还原图、Release 输出及进程加载位置，摘要与归属一致

#### Scenario: 归档缺失或框架依赖和资产偏离

- **WHEN** 核心归档被同版本文件替换、候选缺失、核心依赖范围偏离，或出现原版框架包、错误目标或重复程序集来源
- **THEN** 验证返回非零并定位相关包、范围或资产，报告保留已取得的证据及未执行阶段

### Requirement: 独立宿主可建立连接并向在线用户发送通知

SignalR 候选 SHALL 支持独立 ABP 宿主在本机 macOS ARM64 的 `net9.0` Kestrel 回环端口通过 `/signalr` 处理连接、在线登记与移除，并向当前测试身份推送通知。

#### Scenario: 客户端连接后收到指定通知并断开

- **WHEN** 实际 SignalR 客户端使用仅当轮宿主识别的测试身份连接 `/signalr`。宿主在连接建立时登记实际连接 ID 和测试身份
- **THEN** 宿主可按连接 ID 查到该身份的在线记录，客户端另行调用 `Register` 成功
- **AND** 宿主从实际的 `INotificationConfiguration.Notifiers` 选出模块登记的 `SignalRRealTimeNotifier`，按该类型解析 `IRealTimeNotifier` 并向该身份发送通知。客户端收到 `getNotification` 并核对用户、通知 ID、通知名和当轮标识
- **AND** 客户端停止连接后，宿主查询同一连接 ID 得到已移除结果

### Requirement: 宿主通过 Castle 产生可核对的 Log4Net 日志

Log4Net 候选 SHALL 让独立 ABP 宿主通过 Castle 日志设施及专用 Log4Net 配置，把实际日志记录写入本轮的独立文件。

#### Scenario: 写入当轮唯一日志

- **WHEN** 宿主通过 Castle `ILogger` 以约定的等级和类别记录当轮唯一标识
- **THEN** 独立输出文件中存在该条记录，实际文本的标识、等级和类别均与预期相符，实际加载的 `log4net` 可追溯到同轮解析包

### Requirement: 验收结果关联实际批次与运行证据

主仓 SHALL 为每次定向验收保存可复核的输入、产物、阶段状态和范围。必需的资产和运行断言全部通过时，验收才返回零。

#### Scenario: 记录实际通过的独立宿主组合

- **WHEN** 包、资产、加载、SignalR 和 Log4Net 的必需检查通过且宿主已停止
- **THEN** 报告可核对主仓及框架输入、原版参照、两批实际包身份和摘要、环境、命令与退出码、资产、客户端证据和日志内容，并记录原版 Host 的 ABP `10.2.0`、`log4net 3.1.0` 与本轮选中版本的差异
- **AND** 复跑命令显式指定 `--dotnet`，报告登记可执行文件路径、SDK、进程架构及宿主实际加载的两项共享运行时版本。首次本机验收使用 R2 的 ARM64 `dotnet`，SDK 为 `10.0.404`，`Microsoft.NETCore.App` 和 `Microsoft.AspNetCore.App` 均为 `9.0.23`
- **AND** 结论限定在实测的本机 macOS ARM64 独立 `net9.0` 组合，明确列出留待后续的完整模板、真实登录与数据库、Angular、其他平台和目标

#### Scenario: 宿主启动成功但行为证据不足

- **WHEN** 宿主已启动，但通知配置缺少 `SignalRRealTimeNotifier`、客户端未收到正确的通知、连接未按期移除、日志文件缺少正确文本，或缺少必要的加载与来源证据
- **THEN** 验证返回非零并定位缺失项，保留已有的日志与证据，记录宿主停止结果及后续未执行的阶段
