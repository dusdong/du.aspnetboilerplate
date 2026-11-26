# 首轮维护审查设计

## Context

`v10.5.1` 标记主仓 `5758c8186b68dcc42ecc90164cf9d3f53cf3345e`，`ed0e156150403874e776ca2a4a19128e9c72a0f3` 提供首发验收工具和归档。包的生产提交取自 tag 中的 gitlink。维护者可以使用公开发行校验清单核对 13 个 ID、版本、生产仓及下载摘要。[发行校验清单](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json) · [组合清单](../../../../eng/r4_release_candidate.json)

首发在 macOS ARM64 验证了固定模板 `2e9536872673a7ff1986a19e798c51684d16afe5`。两代 Web.Host 各还原 13 个维护包，Migrator 各还原 10 个。归档后的 `net10.0` 构建共有 307 条 C# 警告，按 MSBuild 最终汇总分为 CS1591 301 条、CS1570 4 条、CS8632 和 CS0162 各 1 条。依赖公告另有查询来源。

## Goals / Non-Goals

首轮在主仓形成一份真实、带截止时间的维护记录，供使用者判断是否需要采取行动，也供下一位维护者接续。跨平台验收、修改依赖、回补代码和发行新版本各有独立的验收范围。优先执行本轮可以决定的问题，可避免把平台扩测或一个未经证实的告警直接排成补丁。

## Decisions

### 用发行记录固定检查对象

从 tag 的 gitlink 定位经典框架 `bed57726b`、引擎 `f646d492` 和 Collection `306b49d7`。三仓分别记录生产提交、上游比较基点及完整 SHA（框架 `v10.5.1`、引擎 v14、Collection v11），再登记实际检索的分支或发行引用及其截止完整 SHA。[引擎兼容基线](../../../../docs/compatibility/automapper.md)

### 按 TFM 和入口保留完整依赖图

以首发公开源通过轮的四个 `project.assets.json` 为基准。从各入口 `targets` 中的实际 TFM 目标选取 `type=package` 的条目，覆盖直接与传递包。根据入口的直接包声明及项目引用、包依赖边标明引入路径，保留入口和解析版本。nuspec 另用于核对允许范围。

R4 使用 SDK `10.0.404` 处理 `net9.0` 与 `net10.0`。若用 NuGet 包列表命令交叉核对，显式传入 `--include-transitive`。若依据 `dotnet restore` 的审计输出，两种目标都显式传入 `-p:NuGetAuditMode=all`，尤其是 `net9.0`。

| TFM | 入口 | 实际解析包数 | 维护包数 | `Microsoft.IdentityModel.JsonWebTokens` |
| --- | --- | --- | --- | --- |
| `net9.0` | Web.Host | 116 | 13 | `8.0.1` |
| `net9.0` | Migrator | 81 | 10 | `6.35.0` |
| `net10.0` | Web.Host | 94 | 13 | `8.19.2` |
| `net10.0` | Migrator | 66 | 10 | `7.7.1` |

每份原图登记文件位置、SHA-256、选定目标和提取方式。随维护记录交付精简清单，包含 TFM、入口、包 ID、解析版本、来源、直接或传递类别及引入路径。两种共享运行时分别引用实际进程的 .NET 和 ASP.NET Core 版本记录。若重新公开还原，另记时间、输入与摘要，并对照原图说明各入口的差异。[模板消费手册](../../../../docs/maintenance/r4-release-candidate.md#公开源模板消费)

### 把上游代码和依赖公告对回发行物

- 对三个生产组件查原上游发行、已合并修复和安全公告，包括较新维护线上仍适用于发行基点的修复。逐项把上游结论与发行源码或实包证据对应。框架以已回补的 #7219 对照发行源码和原 SQLite 回归范围。引擎逐项核对 `GHSA-rvv3-g6hj-g44x`、`GHSA-6vhm-j9h7-f9gh`、`GHSA-gpwp-5797-mjff`，关联 R4 同一已加载 DLL 的摘要及各项测试。CLR 低栈分支沿用原组合证据，实际触发仍待观测。[框架补丁](../../../../docs/maintenance/r1-efcore-query-filter.md) · [R4 实包证据](../../../../docs/maintenance/r4-release-candidate.md#实测支持矩阵) · [引擎公告与行为证据](../../../../docs/maintenance/r3-automapper-engine.md#公告处置与行为证据)
- 从 nuget.org 公布的漏洞信息按原 ID 和实际解析版本核对直接与传递依赖，对命中项回读原公告。框架和映射库同时核对原 ID 与 `Du.*` ID，保留 fork 回补造成的差异。另查 Microsoft 对实测 .NET 与 ASP.NET Core 版本的服务公告，区分消费者运行时更新、模板依赖更新和维护包修复。[NuGet 审计](https://learn.microsoft.com/en-us/nuget/concepts/auditing-packages) · [NuGet 公告数据](https://learn.microsoft.com/en-us/nuget/api/vulnerability-info)
- 首次检查覆盖仍适用于这些版本的既有公告和截至检查日的修订。后续可从本轮检查点增量核对新增或更新的公告、上游提交和待查项。结果为空要列明成功查询的范围；查询失败则留下未覆盖的来源和重查入口。

### 用一份维护记录交接结论

在主仓 `docs/maintenance/r5-first-maintenance-review.md` 记录实际审查日期、输入、来源和范围。逐项列出来源、版本或提交、消费者路径、影响和证据，可由同一公告关联多个入口。处置分为需处理、已有修复、不适用、暂缓和待核实。暂缓注明理由及恢复处理的触发条件。分别写明维护包、模板、运行环境和消费者所需的行动。

有证据确认维护包需要修复时，整轮判为「需补丁」。列出优先项、目标仓、兼容和回退边界、定向回归及实包验收入口，已明确的修复可先立项，其他待核实项继续登记。证据支持维护包继续使用现有版本时，判为「无需补丁」，仅涉及模板、运行环境或消费者的行动另列，并记录依据、截止点和下次触发条件。尚未确认维护包需要修复且缺证妨碍判断时，判为「暂不能判定」，写明影响范围、补查条件和入口。[候选验收规范](../../../specs/release-candidate-verification/spec.md)

### 向单独补丁变更交接发行准备

已确认的修复需求决定是否立项。若单独补丁变更选择主仓 OIDC 受信任发布，按手册分别交接待演练的只读 job（含替换包反例），以及另获授权后的凭据兑换和真实上传验收。[受信任发布接入建议](../../../../docs/maintenance/r4-release-candidate.md#github-actions-受信任发布接入建议)

补丁进入发行准备时，由验收端独立登记该批补丁清单 SHA-256。`eng/r4_public_release.py` 的公开回读与 `eng/r4_template_assets.py` 的下载登记和消费核对须使用同一可信摘要，并保留 R4 固定批次复验。按手册的冻结清单及逐包依赖 gate 操作，在公开符号、公开消费及新库安装均通过后发 Release。[公开发行规范](../../../specs/public-package-release/spec.md)

## Risks / Trade-offs

- 一个 `Abp.*` 或 `AutoMapper` 公告可能漏过改名包，也可能命中已经回补的代码。用原始身份和发行源码双向对照，并保留已有行为证据的边界。
- 数据源可能变动、截断或暂不可用。留存查询条件、分页完成情况、具体版本或数据时间戳和必要摘要，便于复核当时决定。
- 同一模板在新库、迁移和不同平台上的证据不同。以 R4 记录为支持矩阵基线，`net9.0` 标注为存量迁移。补丁建议随影响面列出实际需要重跑的入口。[R5 交接范围](../../../../docs/maintenance/fork-roadmap.md#r5把持续维护控制在可承担的规模内)
