# R3 原版 Web.Host 依赖与构建基线

2026-11-25 在 macOS 27.2.1 ARM64（`26B131`）使用 SDK `10.0.404` 从空缓存还原 Angular 配套的原版 Web.Host，随后以相同的五项目和 `net9.0` 还原图完成 Release 构建。Host 使用 SQL Server Provider。还原退出 0，0 警告、0 错误。构建退出 0，307 条编译警告、0 错误。11 个原版 ABP 运行 DLL 均可在还原图、Host `.deps.json`、实际输出和对应 NuGet 包之间双向核对。

本轮覆盖源码、还原、构建和产物核对。宿主启动和登录、SQL Server 连接及数据库操作、Angular 构建、其他模板入口、.NET 10 迁移、维护包打包与消费、其他平台、CI 和部署均未执行。[模板 Web.Host 基线规范](../../openspec/specs/template-host-baseline/spec.md) · [R3 首包归档](../../openspec/changes/archive/2026-11-25-baseline-r3-web-host-dependencies/)

## 固定输入与复跑

| 输入 | Git 提交 | Git 树 |
| --- | --- | --- |
| 主仓登记 | `105b1263160d049c97a975ee088b79982f1c547d` | `eae117e6926381b1558d6d25e113869e11804968` |
| 原版模板 | `2e9536872673a7ff1986a19e798c51684d16afe5` | `b6a9e7386e3073e820eed83fe418d6c6096468bc` |
| 维护框架的静态项目图 | `457be917b46c4fb6237831baac5abb848ffe1c4b` | `fb0abb6be5cb69b0e5ff395f4b010cf28511f9c8` |

在有上述 Git 对象和 ARM64 SDK `10.0.404` 的 macOS 主仓根目录运行。证据父目录须可写并能容纳隔离源码、原始日志、NuGet 缓存和 Release 工件。核对包内容可访问 nuget.org。框架子仓提供对照项目文件，复跑所需的 R2 身份与摘要登记随主仓保存。[子模块登记](../../.gitmodules) · [R2 验收](r2-core-package-consumption.md) · [R2 实物引用清单](../../eng/r3_r2_reference.json)

```sh
python3 -B eng/verify.py --profile r3-web-host --evidence-root "$R3_EVIDENCE_ROOT"
```

工具在新目录下用 `git archive` 导出固定模板的 `aspnet-core/`，在父层通过 `global.json` 禁止 SDK 前滚。从导出的 `aspnet-core/` 执行以下命令。报告保存展开后的项目、配置、缓存和日志路径，及每条命令的工作目录、退出码和各阶段状态。[验证入口](../../eng/r3_web_host.py)

```sh
dotnet restore "$HOST_PROJECT" --configfile "$RUN/NuGet.Config" --no-http-cache --force -p:Configuration=Release --verbosity normal
dotnet build "$HOST_PROJECT" --configuration Release --no-restore --disable-build-servers -p:UseSharedCompilation=false --verbosity minimal
```

模板原配置同时登记 nuget.org 和旧的 MyGet `ABP Nightly Source`。还原使用显式生成且清除继承包源的 `NuGet.Config`，唯一包源为 `https://api.nuget.org/v3/index.json`，使用独立空全局包目录与 HTTP 缓存。五份原始资产的实际配置、包目录和包源一致。缓存元数据的 `source` 与内容 SHA-512 对照资产记录，归档的 SHA-512 单独对照 `.nupkg.sha512`，并保存归档 SHA-256。构建前后五份资产摘要一致。307 条构建警告为固定源码的不可达代码、XML 注释和可空注解警告（`CS0162`、`CS1570`、`CS1591`、`CS8632`）。

每轮在自己的证据目录内生成 `r3-web-host-baseline.json`。用 `diff -u` 与本仓的[首次通过清单](r3-web-host-baseline.json)比较，可逐项核对相对项目引用、直接包声明、NuGet 范围、解析版本、包间依赖边，以及框架 DLL 的相对路径、所属包、包内资产和 SHA-256。Web.Core 对 `Abp.ZeroCore` 的直接声明在清单中有单独记录。清单内的 SDK pack 文件路径相对相应 pack，SDK 安装内容可能影响 pack 的取用方式。Host 自身的 DLL 摘要标识当次构建工件。

## 实际还原与产物

| 项目后缀 | 直接项目引用 | 直接 ABP 包，均解析到 `10.2.0` | 应用包数 |
| --- | --- | --- | ---: |
| Web.Host | Web.Core | `Abp.Castle.Log4Net` | 144 |
| Web.Core | Application、EntityFrameworkCore | `Abp.AspNetCore`、`Abp.AspNetCore.SignalR`、`Abp.ZeroCore` | 125 |
| Application | Core | | 76 |
| EntityFrameworkCore | Core | | 124 |
| Core | | `Abp.AutoMapper`、`Abp.ZeroCore.EntityFrameworkCore` | 76 |

五项目均由 MSBuild 实际解析并使用 `Microsoft.AspNetCore.App.Ref` 和 `Microsoft.NETCore.App.Ref` 的 `9.0.23`。Host 另用 `Microsoft.NETCore.App.Host.osx-arm64 9.0.23` 创建应用宿主。三个包均从 nuget.org 下载，分项目登记在 `downloadDependencies` 及解析结果中。机器同时安装了 `9.0.10` pack，MSBuild 本轮选中的路径均位于本轮独立缓存。预装 pack 路径的模拟用例另验选用文件 SHA-256，以及下载来源和内容哈希缺失时的说明。SDK 构建输入单列于应用包图之外。

Host 启用了 `PreserveCompilationContext`。`refs/` 中共有 301 个编译参考 DLL，`.deps.json` 中另有 48 个标为 `compileOnly` 的包条目。工具、分析器和被共享框架承接的包条目可以只有占位资产或构建用途。资产清单区分包内工具、分析器和 MSBuild 实际选用项。实际复制的 11 个 ABP 运行 DLL 均来自各自的 `lib/net9.0/`，与包内文件同 SHA-256。Host 的可移植 `.deps.json` 保留第三方的各 RID 候选，应用宿主工具的 `osx-arm64` 属于 SDK 构建输入。

依据同轮 Host 的还原图逐项核对 `.deps.json` 的入口、五个项目及全部包的库条目和依赖边。还原边所写的范围与 `.deps.json` 的实际解析版本分别记录。通过同一 SDK 解析 `ReferenceCopyLocalPaths` 的冲突处理结果，对照 168 个 NuGet 运行复制项和五个项目输出，含资源和 RID 资产。原版 Provider `Microsoft.EntityFrameworkCore.SqlServer/9.0.5` 的运行 DLL来自包内 `lib/net8.0/Microsoft.EntityFrameworkCore.SqlServer.dll`，运行产物与归档内文件的 SHA-256为 `dba57329b3be97a596b1dae7f3ca3f10344a562b44439e9b2ab28ba4f77912d4`。

## 闭包与迁移准入

原版 Host 的 11 个框架包均解析到 `10.2.0`，十一条框架包内部边与维护框架的 11 个源码项目引用相符，框架包集合和运行资产归属均吻合。已验 R2 的五个 `Du.Abp*` 实物来自同一维护源码树，版本为 `10.5.1-r2.1`，各含 `net9.0` 与 `net10.0` DLL。R3 重新回读了原实物的归档摘要、两个目标的 DLL 和 nuspec 四条内部边。R2 的运行范围是 SQLite 独立最小后端。补齐六个缺口时仍以现有程序集名和命名空间为准。[R2 证据范围](r2-core-package-consumption.md#源码与产物)

| 依赖 | 原版 Host 实际解析及资产 | 维护端对照 |
| --- | --- | --- |
| EF Core、Abstractions、Relational | `9.0.5`，由模板 SQL Server 与原版 EF Core 链共同引入 | R2 `net9.0` 消费为 `9.0.18`。维护源码还声明独立的 `net10.0` 依赖组 |
| SQL Server、SqlClient、SNI | SQL Server `9.0.5` 引入 SqlClient `5.1.6`。编译使用 `ref/net6.0/`，运行记录含通用及 Unix/Windows DLL；SNI `5.1.1` 提供 Windows 原生候选 | R2 使用 SQLite `9.0.18`，后续在同模板核对 Provider 组合与实际加载 |
| EF Core Design、Tools | 均为 `9.0.5`。Design 由 EF 项目及 Host 分别私有声明，在 Host 保留运行 DLL。Tools 仅见于 EF 项目，包内工具资产留存于清单 | R2 的两个最小消费入口均无这些包 |
| MVC NewtonsoftJson、Razor RuntimeCompilation | 均为 `9.0.5`，由 `Abp.AspNetCore` 引入 | R2 `net9.0` 同位置解析到 `9.0.18` |
| JWT Bearer、Swashbuckle | Web.Core 直接引入 `9.0.5`、`8.1.2` | 由模板选择，未在 R2 最小消费者验收 |
| Log4Net、AutoMapper、Collection | log4net `3.1.0`；AutoMapper `14.0.0` 和 Collection `11.0.0` 两项均选用 `lib/net8.0/` | 固定源码声明 log4net `3.3.2` 及相同的两个 Mapper 版本，三项都需随相应组件验收 |
| 核心第三方依赖 | Newtonsoft.Json `13.0.3`、NUglify `1.21.15`、JetBrains.Annotations `2024.3.0`、System.Linq.Dynamic.Core `1.6.4`、TimeZoneConverter `7.0.0` | R2 `net9.0` 分别为 `13.0.4`、`1.22.0`、`2026.2.0`、`1.7.3`、`7.2.0`。实际选中的逐项资产见缺口清单 |

后续按以下依赖关系推进。

1. SignalR 与 Log4Net 各自只引用核心 `Abp`。可独立核对 `net9.0` nuspec、第三方与框架依赖、程序集和定向消费。
2. Module Zero 按 `Abp.Zero.Common → Abp.ZeroCore → Abp.ZeroCore.EntityFrameworkCore` 补齐，最后一个还需 `Abp.EntityFrameworkCore`。复验既有 `net9.0` 调用和 SQLite 回归。
3. `Abp.AutoMapper` 还需确认 MIT AutoMapper v14 与 Collection v11 的固定来源和许可证、单一映射引擎、依赖范围、已识别安全修复及配置、对象更新、集合映射和 `ProjectTo` 的兼容行为。[映射兼容指南](../compatibility/automapper.md)
4. 从独立源和空缓存验收同批核心与新增候选的实际目标、依赖闭包、程序集身份、唯一来源及完整还原。完成相同 Host 的候选构建和原版逐项对照后，才进入隔离 SQL Server 的启动、登录、租户与授权验收。若改变 schema 或数据，先核对备份恢复或逆向迁移条件。[维护路线](fork-roadmap.md#r3验证升级路径和实际消费者)

## 验收记录

首次通过的运行目录为验证机的 `.git/r3-web-host-baseline/package-1/runs/r3-web-host-wlnaoqvg/`。原始五份资产在 `raw-assets/`，`report.json` 给出其摘要及保存 Host DLL、`.deps.json` 和全部 Release 输出的目录。

| 当轮证据 | SHA-256 |
| --- | --- |
| `report.json` | `f3c65f1aef63edd8ad39a9d19c413f0e589297bb8896c8826251e8121b229d97` |
| `assets-inventory.json` | `ff82f4e7e5213b496fc4ed0246ed953ade63b6ff64a8721e981fd2b1ea7e988c` |
| `host-output.json` | `2aefc2ec35af00535cdd34be304cc0fbc5d7c07db122d87f90b2c14dea6136dd` |
| `package-gaps.json` | `1b5cb9c73b03ff5cf299cec03a2ef182070565562a604c815b80ad7468c3f5c8` |
| 首次原始清单，schema 1 | `8b39108056f34f55101af51c5b361f031461f4adb56e9129d9331e8b04027dc5` |
| [首次通过清单](r3-web-host-baseline.json)，schema 2 | `293838ec9c41886621498c25913cc85d23626ce31027d8c2116d5b1aca736452` |

首次通过报告及 schema 1 清单保留在上述当轮目录。复审从同一轮原始资产与 Host 输出清单重提取 schema 2，补入直接项目引用和直接包声明及解析边。原有包图、SDK 输入、框架 DLL 摘要均逐项核对一致。新版工具在独立空缓存重新还原和构建后生成同字节清单，主仓清单摘要经前后核对一致。

用以下命令核对新版工具生成的 `$RUN`，并在新目录保存独立诊断夹具。

```sh
python3 -B eng/tests/verify_r3_web_host.py "$RUN" "$NEW_DIAGNOSTIC_EVIDENCE" docs/maintenance/r3-web-host-baseline.json
```

故障夹具分别验证固定对象缺失、项目资产缺失、目标包图为空、缺 `.deps.json`、框架 DLL 来源冲突、单独移走 `Abp.Castle.Log4Net.dll`、缺入口项目边、缺框架包依赖边、保留 SQL Server DLL 时缺 Provider 依赖声明以及多余的运行资产声明，各自退出 1 且点名受影响项。

版本变化用例仅模拟还原结果。模拟 `Abp.Castle.Log4Net` 在固定 `10.2.0` 声明下解析为 `10.2.1`，资产核对通过，缺口核对写入具体差异后退出 1。模拟 SQL Server Provider 从 `9.0.5` 解析为 `9.0.6`，记录第三方差异并通过缺口核对。两个模拟版本未下载或构建。复审原始记录保存在验证机的 `.git/r3-web-host-baseline/package-1/revision-1/`。
