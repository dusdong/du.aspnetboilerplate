# 首次发行候选设计

## Context

主仓基点为 `bd5f29f8a02ffcc8868deb2c8e60f49306d6668a`，模板 gitlink 为 `2e953687`。生产子仓的当前 gitlink 分别为框架 `806a9c7c`、AutoMapper `d249ed3a`、Collection `cab138e2`。R3 的包能通过生产清单、基点和源码树追溯。逐包读回后，13 份 nuspec 的 repository 元数据都没有生产 commit 值。部分打包入口还会物化工作树或按 `-r3.N` 推导相依版本。R4 要让接收方能从包本身定位到已验源码。[冻结输入](../../../../eng/r3_template_net9_reference.json) · [映射引擎生产记录](../../../../docs/maintenance/r3-automapper-engine.md)

## Goals / Non-Goals

本轮交付采用拟发行版本的本地实物、可复跑的制备和消费步骤、逐文件摘要及发布说明草案。应用验收沿用既有模板、SQL Server 和前端组合。Angular 适配器、Web Resources、Samples 等继续作为各自的组件管理。公开源名称与权限、正式发布授权、tag、上传和公开源回装属于后续发行步骤。

## Decisions

### 为三个包系列分别定版本，保留既有内部范围语义

| 包组 | 既有候选 | 本轮拟用版本 | 包内目标 |
| --- | --- | --- | --- |
| Du.Abp、Du.Abp.Web.Common、Du.Abp.AspNetCore、Du.Abp.EntityFramework.Common、Du.Abp.EntityFrameworkCore | `10.5.1-r2.1` | `10.5.1` | `net9.0`、`net10.0` |
| Du.Abp.AspNetCore.SignalR、Du.Abp.Castle.Log4Net | `10.5.1-r3.1` | `10.5.1` | `net9.0` |
| Du.Abp.Zero.Common、Du.Abp.ZeroCore、Du.Abp.ZeroCore.EntityFrameworkCore | `10.5.1-r3.3` | `10.5.1` | `net9.0` |
| Du.Abp.AutoMapper | `10.5.1-r3.4` | `10.5.1` | `net9.0` |
| Du.AutoMapper | `14.0.0-r3.4` | `14.0.0` | `net8.0` |
| Du.AutoMapper.Collection | `11.0.0-r3.4` | `11.0.0` | `net8.0` |

框架统一到其上游基线版本，两个映射包沿用各自维护线。2026-11-26 对 13 个 ID 的 NuGet 公共版本索引逐项 GET 均返回 404，发布前仍需核实当时的可用版本、目标源及该账号的发布权限。若版本或身份需要调整，先更新组合清单，再生成和验证相关归档。[NuGet 版本索引与 404 的含义](https://learn.microsoft.com/en-us/nuget/api/package-base-address-resource#enumerate-package-versions)

五个核心包的内部依赖继续使用稳定版本下限。其余包现有的精确约束继续使用方括号，例如 `Du.Abp.ZeroCore.EntityFrameworkCore` 的两条内部边均指向 `[10.5.1]`，`Du.Abp.AutoMapper` 分别指向 `[10.5.1]`、`[14.0.0]` 和 `[11.0.0]`，Collection 精确引用 `[14.0.0]`。按包和 TFM 完整比对实际依赖边与范围，防止只改顶层版本或引入额外依赖。第三方依赖沿用同目标 R3 基线。包版本与 CLR 程序集版本分别核对。[Module Zero 包关系](../../../../docs/maintenance/r3-module-zero-candidates.md) · [现有适配器引用](../../../../aspnetboilerplate/src/Abp.AutoMapper/Abp.AutoMapper.csproj)

### 按最终提交打包，按具体字节交接

主仓保存可机器读取的一份 R4 组合清单，由原 R3 登记导出比较输入。最终生产提交在三个子仓的打包改动完成后确定。对照主仓固定的 gitlink 从干净检出生产，记录 SDK、配置、命令、提交及其仓库地址。按依赖顺序产出核心包和映射引擎，再构建依赖它们的包。使用显式 R4 模式复用已有 pack 逻辑，历史批次校验和普通源码构建各有原入口。直接解压改 nuspec 或重命名旧文件会丢失编译依赖、符号和生产提交之间的关系。[核心打包入口](../../../../aspnetboilerplate/nupkg/pack-r2-candidates.sh) · [引擎入口](../../../../AutoMapper/src/AutoMapper/ApiCompat/pack-r3-engine.sh) · [集合入口](../../../../AutoMapper.Collection/pack-r3-candidate.sh)

从实际归档核对每个 DLL 的目标、程序集名、程序集版本、公钥标识和公共 API，对照 PDB 的 CodeView 标识和可定位的源码，核对许可、版权及仓库元数据。每次生产使用独立暂存目录，检查齐备后才冻结整套主包与符号包。冻结清单记录 SHA-256、大小和对应验证报告。中断后可在新目录重做，已冻结批次不被覆盖。若采用发布者签名，消费验收以签名后的文件为输入，变动包须更新摘要和相关消费结果。

R3 的 13 份主包均沿用上游 `projectUrl`，其中 `Du.AutoMapper` 的随包 README 还引导安装 `AutoMapper`。R4 在组合清单中逐包登记维护版主页。冻结前，从 nupkg 读回 nuspec 的 `id` 和 `projectUrl`，并检查随包 README 的安装命令、安装链接及维护联系入口。例如，引擎 README 中的 CLI 和包管理器示例都应安装 `Du.AutoMapper`。核对时区分安装指引与上游来源说明，保留原作者署名、版权和许可。

### 用冻结的引擎包复验三项安全修复

从冻结源安装 `Du.AutoMapper`，复用既有隔离子进程用例，按稳定规范逐项复验三则公告。每项结果记录本轮主包和实际加载的 `AutoMapper.dll` 的 SHA-256，并核对加载文件与主包内 DLL 的摘要一致。CLR 低栈分支沿用既定的三项组合证据，报告区分受控异常下已实测的传播与恢复，以及实际 CLR 低栈触发的观测状态。逐项结果齐备且通过后，才交接该批归档。[映射包稳定规范](../../../specs/automapper-package-consumption/spec.md#scenario-判断安全修复能否纳入候选) · [既有实包复验入口](../../../../AutoMapper/src/AutoMapper/ApiCompat/README.r3-engine.md#完整实包行为复验)

### 用本轮归档重演固定模板的升级与回退

将 13 个维护 ID 精确映射到本地目录源，第三方依赖仍可从登记的公共源还原。为 `net9.0` 与 `net10.0` 使用独立空缓存，重放固定模板的七处包引用替换及相应目标补丁。逐入口核对声明、解析闭包、产物及实际进程加载，防止安装的是新包而运行的是旧输出。Mac ARM64 的模板对照沿用 SDK `10.0.404`、共享框架 `9.0.10` 和 `10.0.15`、SQL Server Developer `16.0.4236.2` 及冻结 Angular production 客户端。[换包结果](../../../../docs/maintenance/r3-template-net9-packages.md#正式运行结果) · [同库升级](../../../../docs/maintenance/r3-template-net10-upgrade.md)

复用已核实的登录前备份与原版程序。维护版两代在同一候选库完成登录，登录计数按候选库/对照库为 `1/1 → 2/1 → 3/1`。用本轮产生的两个新恢复点执行原版回退，按升级后库/升级前库为 `3/2 → 4/2 → 4/3`。核对 `Default`、账号 2、`Pages.Users`、关键词 `r3usercf4314cdfe038c35`、唯一用户 3、请求关联的实际查询库及登录行差异。恢复点、行身份和创建时间取自本轮报告。历史回退入口绑定 R3 升级报告的固定摘要。R4 单独传入经清单验证的新升级报告与备份摘要，保留 R3 的严格输入约束。[回退入口](../../../../eng/r3_template_original_rollback.py) · [正式运行结果](../../../../docs/maintenance/r3-original-template-rollback.md#正式运行结果)

## Risks / Trade-offs

- 仅运行模板登录无法覆盖集合映射等按需加载的功能。按拟声明的能力，将既有映射更新、集合、关系型投影、SignalR、日志、Module Zero 隔离和核心 SQLite 定向回归绑定到本轮归档。源码回归关联最终生产 SHA。某项目尚未实测时，在支持矩阵列明证据层次。
- R1 的 Windows ARM64、x64 结果覆盖当时的框架源码。发布说明按应用所在平台、架构、TFM、Provider 及客户端列出结果，将历史源码测试与本轮待发包、完整模板的证据分别登记。
- 发布者依清单交接准确字节和已知限制，随后在独立发行步骤核验注册源、发布权限和公开下载结果。任何公开源重签名等字节变化须能解释并验证，公开发行仍需从公共源重新消费。
