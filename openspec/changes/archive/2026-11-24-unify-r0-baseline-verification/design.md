# R0 统一复验设计

## Context

| 字段 | 本轮规划所见 | 运行时来源 |
| --- | --- | --- |
| 调用者主仓提交 | `dfe1a2f6be6d1d714e37b408d411842cfc01e250` | 运行时的主仓 `HEAD` 与相关输入工作树状态 |
| 调用者框架 gitlink | `d08617b51bb7c7e5d0bea942e7e10b2677240c35`，R1 首项补丁 | 运行时的主仓 Git 树，另记工作树中框架检出 SHA |
| 历史 R0 主仓输入 | `cf1420d6dc967fe2b34b52c0409e8407140e917e` | 基线的 `superprojectInputCommit` |
| 实际复验的框架输入 | `6c4580c5e7ea41154696c071a53fd200059a768b`，上游 `v10.5.1` | 基线的 `frameworkInputCommit` 与子模块 Git 对象 |

已接受的实测环境是 macOS 27.2.1 ARM64、SDK `9.0.306`、.NET 与 ASP.NET Core `9.0.10`、`net9.0` 及 SQLite。历史还原清单的项目目标均未指定 RID，宿主 RID 为 `osx-arm64`。现有 `primary` 还原后直接继续身份求值、Release 构建和三套测试，`repeat` 使用另一份干净源码和缓存并在还原后结束。基线另记录过换目录完整复跑及其 API、DLL 摘要与测试计数。[结构化基线](../../../../docs/maintenance/release-baseline.json) · [复验手册](../../../../docs/maintenance/baseline-evidence/README.md) · [R1 记录](../../../../docs/maintenance/r1-efcore-query-filter.md)

## Goals / Non-Goals

- 复用经过验收的执行与比较工具，以同一报告关联实际结果和可复核输入。已接受的基线文件继续承载历史证据。
- API 门限覆盖当前提取器记录的 PE 元数据。自定义特性、类型转发、资源内容和完整二进制兼容认证属于后续验收范围。
- 当前框架 gitlink 继续代表维护候选的版本组合。R1 / R2 将针对各自候选制定差异与消费者验收口径。

## Decisions

### 入口、输入与环境

在主仓根目录用 Python 3.10 或以上运行 `python3 eng/verify.py --profile r0`。入口读取 `docs/maintenance/release-baseline.json`、其中引用的还原清单和五份 API 清单。从结构化记录取框架提交、项目范围、预期身份、SDK 和测试预期。现有工具内置的 R0 SHA、五个框架项目和三个测试入口应与这些输入核对。报告同时记录实际 `HEAD`、gitlink、框架当前检出、有无影响复验的未提交输入，以及实际使用的工具和基线文件摘要，便于还原主仓输入身份。历史主仓输入 SHA 只用于溯源，在浅克隆中登记其记录值即可。

首期严格复验环境采用 `macOS ARM64` 和 SDK `9.0.306`，以 `net9.0` 及 SQLite 执行。以实际命令工作目录中的 `dotnet --version` 判定 SDK，记录 .NET / ASP.NET Core 运行时、VSTest、宿主 OS 版本、架构及宿主 RID。框架固定源码的 `global.json` 使用 .NET 9 RC 版本和 `latestFeature`，实际选中的 SDK 必须满足本 profile。OS 版本记录为实测环境。缺少 Git、zsh、tar、Python、SDK、运行时或固定框架对象时给出定位信息，其他平台按独立验收结果确定范围。CI 需要取得可归档的完整 R0 Git 对象及其目录树，检出历史深度由实施时验证。入口仅在独立目录物化固定源码，保持主仓和子模块检出状态。[现有复验脚本](../../../../docs/maintenance/baseline-tools/reproduce.zsh)

### 单次调用与独立完整复跑

每次调用创建唯一工作和证据目录，按顺序组织以下步骤。目录名可在运行控制台定位，CI 可将证据根设置在工作流临时目录。

1. 将 `reproduce.zsh` 的执行步骤分成可单独调用的物化及还原阶段，以及沿用已还原 `primary` 的续跑阶段。统一入口先为 `primary` 和 `repeat` 各调用一次物化及还原，从同一 R0 对象物化源码，各用首次为空的 `NUGET_PACKAGES`、仅启用 `nuget.org` 的配置和 `--no-http-cache`。用 `inventory.py` 的实际资产解析，三方对照主轮还原、第二次还原和基线清单，按项目与目标核实包 ID、直接或传递关系、版本、来源与内容哈希。项目图须与清单匹配，覆盖 11 个项目、11 个 `net9.0` 目标。通过比较后，续跑使用原 `primary` 工作目录、包目录和还原产物。出现依赖漂移时保存差异、返回非零，构建、API 和 .NET 回归均不启动并标为未执行。
2. 在主轮对五个框架项目核对 Release MSBuild 求值结果，包括原 `PackageId`、包版本、`AssemblyName`、`RootNamespace`、目标框架和内部 `ProjectReference`。例如 `Abp.EntityFramework.Common` 的根命名空间为 `Abp.EntityFramework`。复用主轮还原执行 Release 构建 `--no-restore`，由该轮的 `TargetPath` 定位五个 DLL。主轮续跑的构建与回归步骤可分别调用，供统一入口在两者之间核对 API。使用已核对的 .NET SDK 在独立工具目录构建 `ApiInventory.csproj`，复用 `Program.cs` 对同一个 DLL 提取两次并核对清单一致。记录每个实际 DLL 的 SHA-256、提取器版本和提取命令，用 `inventory.py compare-api` 比较程序集身份、完整类型名、公开和受保护签名、资源名。内容摘要用于标识证据，跨独立构建的同一性以 API 语义为准。R0 的身份预期来自原版字段，`plannedPackageId` 留给 R2 的实际包验收。[清单比较器](../../../../docs/maintenance/baseline-tools/inventory.py) · [API 提取器](../../../../docs/maintenance/baseline-tools/Program.cs) · [提取器项目](../../../../docs/maintenance/baseline-tools/ApiInventory.csproj)
3. 用同一主轮构建运行三套回归，沿用 `--no-build --no-restore`，收集当次日志和三份 TRX。兼容 XML 命名空间，从 `UnitTestResult` 明细统计结果，以 `outcome=NotExecuted` 计跳过，并将两项跳过的完整 `testName` 与基线精确匹配。按套件要求 `1105/0/2`、`150/0/0`、`58/0/0`，以汇总 `total`、`executed`、`passed`、`failed` 与明细交叉核对。

   两份实际 R0 核心 TRX 的汇总均为 `total=1107`、`executed=1105`、`passed=1105`、`failed=0`、`notExecuted=0`，明细各有 1105 个 `Passed` 和两个具名 `NotExecuted`。汇总 `notExecuted` 通常应与明细一致。当这组关键计数和两项完整测试名全部与基线相符时，记录汇总 `notExecuted=0` 与实际跳过 2 项的差异并接受结果。缺失明细、意外跳过或其他计数矛盾仍须失败。定向正例用可在仓库内生成的夹具重现这组汇总、明细及完整测试名，CI 可直接运行该夹具。

   报告记录既有跳过的名称及可从测试记录或日志取得的原因、EF Core SQLite 测试配置、实际还原的 Provider 版本及适用的本机资产。42 个重复发现 ID 是基线诊断信息，不计入 TRX 结果。测试命令的退出码和证据校验均须通过。

默认调用每次执行一次完整主轮，另用 `repeat` 独立复验还原。两次独立完整执行以两次完整命令调用计数，各自使用新物化源码、空 NuGet 包目录和新结果目录。

实施验收保留本地实跑和真实 CI 实跑。两次执行可以分别来自本地和 CI。配对时，从各自记录的实际主仓输入核对同一验收候选，包括复验入口及所用脚本和工具、已接受基线及清单、固定框架对象。核对两次环境均满足 profile，记录 SDK、实际运行时、VSTest、架构、RID 和 SQLite 等可能影响比较的环境差异。两次环境可比且证据均可读、覆盖同一口径时，比较项目身份、还原图、API 和三套 TRX 结果，并分别留存各自构建的 DLL 摘要。第二次执行证据不足或需定位差异时，才另外在本地完整复跑。补充本地结果可用于检验可复跑性，真实 CI 验收仍须读取该次远端记录与产物。

将已有脚本、比较器与提取器编排在一个入口，可减少两套实现之间的差异。现有 `zsh reproduce.zsh <证据目录> primary|repeat` 接口、产物相对路径与手册命令均继续可用。旧 `primary` 串接物化及还原与主轮续跑，旧 `repeat` 在物化及还原后退出。

### 证据、失败与 CI

以 `report.json` 记录整体状态和每个必要阶段的命令、工作目录、退出码、结论、原因与关联证据。输出目录建立后即开始保存运行信息，任何阶段失败时输出已取得的证据并标记由于失败未执行的步骤。证据目录保留两份还原清单及实际差异、MSBuild 求值、五个 DLL 的摘要及 API 对照、原始分步日志和三份 TRX。必需输入或产物缺失、依赖或 API 漂移、测试失败、结果零匹配、计数不符和非预期跳过均传播非零状态。保存有效包源的脱敏记录，遵循 `inventory.py` 的现有脱敏口径。证据目录包含本次运行数据，既有基线只读。

拟新增 `.github/workflows/verify-r0.yml`，通过 `main` 的 `push` 事件覆盖现行直接推送交付路径。触发路径包括复验入口及定向用例、基线及其工具和清单、框架 gitlink、`.gitmodules` 和工作流本身。工作流准备主仓检出、固定框架对象和 R0 环境，先运行 Python 轻量定向验证，再执行 `python3 eng/verify.py --profile r0`。镜像选择、SDK 安装、Shell/工具可用性、仓库权限及产物上传路径以实施期间在目标仓库核对的能力为准。

本地与 CI 通过 `python3 eng/tests/run_verify_r0_tests.py` 执行同一组定向用例。用 Python 3.10 即可使用的 `unittest` 发现 `eng/tests/test_verify_r0.py` 中的用例并执行 `TextTestRunner`，显式检查返回的 `TestResult`。仅在 `wasSuccessful()` 且 `testsRun` 大于跳过数时返回零，日志记录实际计数及失败诊断。定向用例通过夹具验证正反例，不调用 .NET 回归。发现或执行失败、有效执行数为零时，工作流失败并跳过完整命令，留存自检诊断。完整命令开始后，工作流保留其退出状态，并在失败时仍尝试上传该命令已经生成的证据。

本地验收和 CI 定义检查可在入口与证据约定就绪后并行开展。真实远端验收须记录 GitHub Actions run URL 或 ID、该次工作流实际检出的 `HEAD`、固定框架 SHA、runner / SDK、自检执行计数与结果及完整命令结果，并回读本次报告及三份 TRX。用报告中的主仓输入与实际检出的 SHA 核对证据归属，比较时以实际执行所用的候选输入为准。[组件现有工作流](../../../../aspnetboilerplate/.github/workflows/build-and-test.yml) · [主仓维护计划](../../../../docs/maintenance/du-abp-maintenance-plan.md#9-ci-与发行证据)

## Risks / Trade-offs

- 每次执行有两次干净还原的网络与磁盘开销。只在主轮执行构建、API 与回归，完整独立复跑留作实施验收。包源不可用或解析漂移时保留日志和差异，基线更新作为独立审查处理。
- 历史 DLL 会因绝对构建路径等输入而具有不同摘要。保存各自产物摘要和提取器版本，按实际程序集身份、类型、成员与资源判断结构一致性。
- CI 是否能取得与 R0 匹配的 runner 和 SDK 尚待核对。如果环境或远端执行授权尚未就绪，记录阻塞项与已完成的本地或定义验证，保留真实 CI 验收为待办。

## Migration Plan

实现并完成本地回归后，从 R0 手册增加统一入口、环境要求和报告位置的说明。主仓 CI 接入单独验收，可通过回退新增工作流恢复原先的 CI 状态，历史手册命令可继续用于复验。维护路线随后在已验收的 R1 补丁上推进 .NET 10 / EF Core 10 迁移，再以五个实际 `Du.Abp*` 候选包做 R2 独立消费者验收。[维护路线](../../../../docs/maintenance/fork-roadmap.md)
