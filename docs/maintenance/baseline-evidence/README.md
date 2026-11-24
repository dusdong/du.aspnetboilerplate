# R0 维护基线复验

[维护基线记录](../release-baseline.json) 固定主仓输入、框架提交、五个计划包的闭包、模板的源码声明和实测结果。复验使用 .NET SDK `9.0.306`、.NET 9 和 ASP.NET Core 9 运行时、Python 3.10 或以上、zsh、Git、tar、cmp 和 `shasum`。本次在 macOS ARM64 上实测，环境版本见基线记录。

## 统一入口

在主仓根目录运行。框架子模块须已检出，且其 Git 对象库能读取基线指定的 R0 提交和对应源码树。入口在独立物化的 R0 源码目录用 `dotnet --version` 核对实际 SDK。

```sh
python3 eng/tests/run_verify_r0_tests.py
python3 eng/verify.py --profile r0
```

每次完整调用以两个独立的空 NuGet 包目录分别还原 `primary` 和 `repeat`。第二轮覆盖还原复验。与基线三方一致后，主轮沿用自己的源码和还原产物，依次核对项目身份、构建 Release、比较五个 DLL 的 API 并执行三套回归。需要一次独立完整复跑时，再执行同一个完整命令即可取得新的源码、缓存和结果目录。

控制台以 `R0 report:` 显示当次 `report.json` 的绝对路径。报告记录主仓 `HEAD`、框架 gitlink、当前框架检出、固定 R0 提交、输入摘要及每阶段状态。报告目录同时包含两份还原清单、三方对照、MSBuild 求值、五组 API 清单与 DLL 摘要、原始日志和当次 TRX。失败时查看报告中的原因、已取得的证据及标记为 `not_run` 的阶段。

可用 `--evidence-root <父目录>` 和 `--work-root <父目录>` 指定两个输出位置。默认由系统临时目录分别分配。可归档证据位于证据父目录下当次唯一的 `r0-*` 目录，临时源码、Release 产物、提取器构建和 NuGet 缓存位于工作父目录下当次唯一的 `r0-work-*` 目录。分开指定这两个父目录可让 CI 直接上传当次证据目录。

## 统一入口验收记录

2026-11-24，本地与 GitHub Actions 各完成一次 `python3 eng/verify.py --profile r0`，退出码均为 0，报告的 12 个阶段全部通过。GitHub 执行来自 `main` 的 push，检出并验证了主仓提交 `2196d8653f1612a8b646dd6be99194876fc4eb2d`。第 1 次尝试的 `macos-26` 作业 `138302714838` 先通过 Python 自检（17 个有效、0 跳过），随后获取框架历史、安装 SDK、执行完整复验并上传产物。[GitHub Actions 运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45352670125) · [作业及步骤](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45352670125/job/138302714838)

本地成功报告的 `HEAD` 为 `dfe1a2f6be6d1d714e37b408d411842cfc01e250`，执行时包含新文件 `eng/verify.py` 和已修改的 `reproduce.zsh`、`inventory.py`。两份报告在执行前后记录的 13 项复验输入 SHA-256 均相同，并与 CI 提交中的 13 个 Git blob 内容核对一致。输入涵盖 `.gitmodules`、复验入口、四个脚本及 API 工具文件、发行基线、NuGet 清单和五份 API 基线。两次运行的框架 gitlink 与子模块实际检出均为 `d08617b51bb7c7e5d0bea942e7e10b2677240c35`。参与还原、构建和测试的固定 R0 框架对象均为 `6c4580c5e7ea41154696c071a53fd200059a768b`，源码树为 `77ebbd3dbd293fff4c57b5e741919407995579e8`。历史主仓输入 `cf1420d6dc967fe2b34b52c0409e8407140e917e` 继续用于追溯原始基线。

| 实测项 | 本地 | GitHub Actions |
| --- | --- | --- |
| macOS、Python | 27.2.1、3.14.7 | 26.7.2、3.12.10 |
| 架构、宿主 RID | ARM64、`osx-arm64` | ARM64、`osx-arm64` |
| .NET SDK、MSBuild | `9.0.306`、`17.14.28+09c1be848` | `9.0.306`、`17.14.28+09c1be848` |
| `dotnet --info` 的 Host | `10.0.15` | `9.0.10` |
| 回归目标、.NET 与 ASP.NET Core 运行时、VSTest | `net9.0`、均为 `9.0.10`、`17.14.1 (arm64)` | `net9.0`、均为 `9.0.10`、`17.14.1 (arm64)` |

- 两次执行各有独立的工作和结果目录。每次将固定 R0 源码分别物化到 `primary` 和 `repeat`，使用各自新建的空 NuGet 包目录、仅启用 nuget.org 的独立配置以及 `--no-http-cache`。四份实际还原清单均与基线一致，覆盖 11 个项目和 11 个未设置 RID 的 `net9.0` 目标，包括项目引用、直接及传递包版本、来源和内容哈希。每次三方比较通过后，沿用该次 `primary` 还原做 Release 构建、API 和回归，`repeat` 仅复验还原。
- 两次实际 MSBuild 求值中，五个 `PackageId` 与对应的 `AssemblyName` 均保持原版名称，包版本均为 `10.5.1`。根命名空间、目标框架和内部引用均与基线一致，其中 `Abp.EntityFramework.Common` 的根命名空间为 `Abp.EntityFramework`。在各次 `TargetPath` 定位 DLL，使用版本 1 的提取器分别提取两次，每个 DLL 的两份清单逐字节一致。两次构建的程序集身份、可见类型及成员签名、清单资源名与基线一致。
- 六份原始 TRX 逐套件核对，1315 条用例的名称与结果逐项一致。两次各为 **1313 通过、0 失败、2 跳过**，套件分别为 `1105/0/2`、`150/0/0`、`58/0/0`。核心套件的 2 条 `NotExecuted` 明细与基线完整测试名及原因相符，汇总仍为 `notExecuted=0`，与原始 R0 两份核心 TRX 的已知差异一致。另有 42 个重复发现 ID。两次 EF Core 测试均使用内存 SQLite，实际 Provider 为 `Microsoft.EntityFrameworkCore.Sqlite 9.0.18`、`Microsoft.Data.Sqlite 9.0.18`、`SQLitePCLRaw.lib.e_sqlite3 2.1.10`。两次报告的 `runtimes/osx-arm64/native/libe_sqlite3.dylib` SHA-256 均为 `86fbe7c2ffce12292d243301f6be5c9e51270aa07f36db5f8f0c731817e16970`。

| Release DLL | 本地 SHA-256 | GitHub Actions SHA-256 |
| --- | --- | --- |
| `Abp.dll` | `d573111e265ed4bf086c34b4c61050d6434417a0591eb22d30789bf2cbc642d3` | `f272ab4aaf49338062643debbc75da6311cda26960a71cee5ae267cf360c897e` |
| `Abp.AspNetCore.dll` | `42ba3da3206fd74693c4aaa2d3b062f34143cdd312327d806e3bd1cd356dcdf1` | `3049d554b383452fadc977238af22eeb919581ab67b82a2849a6ab0a3c81de7b` |
| `Abp.EntityFramework.Common.dll` | `2d7084eff2438633af4252ed1cea99e2c532fd78958049b928ba1faa59c23022` | `0c75dd1f50203b4869c96dc5493c60cde6125a9310fc9b539c3160bbff0f540c` |
| `Abp.EntityFrameworkCore.dll` | `43cf073e30168b0795f86fc7980634b6c3f0ebb10986a9c2fadf5eb361c155a5` | `772324c907cc29db81350124191a714eca3eaa8ea3483ab55d6db81672f2669a` |
| `Abp.Web.Common.dll` | `89ec0cf930df529346e71b8fe0c3b16bef4b76d303bfe806c0d8db7c3464cbb4` | `74d15068fb01cefed171b429791812d39e59a9f6d124605cb524ac6fbd1304a6` |

五个 DLL 的摘要在两次独立构建间均有差异。摘要标识各自产物，结构对照以 API 清单为准。上表可在两次报告的 `stages.api_compare.assemblies` 及对应 `api/<程序集>.json` 回查，本地还从五个实际 DLL 重新算得相同摘要。CI 证据包 `verify-r0-1`（产物 ID `14900783289`）的原始 ZIP SHA-256 为 `e27eb5205440d7e9501985c37c203c242c6bb5bc3b8232ba38d5e3b4b56eef77`，下载后与远端登记的摘要一致。[GitHub Actions 产物下载](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45352670125)

可在运行页下载归档，或运行 `gh run download 45352670125 --repo dusdong/du.aspnetboilerplate --name verify-r0-1 --dir r0-ci-evidence` 下载并解包。归档根目录含 `python-self-check.log`、`framework-checkout.log` 和 `verify-r0.log`，`r0-f0_rh43g/` 内含 `report.json`、`{primary,repeat}-restore-inventory.json`、`restore-*.log`、MSBuild 求值、`api/` 和 `trx/`。本地成功原件的报告标识为 `r0-bspud948/report.json`。新克隆可先用 `git submodule update --init --no-recommend-shallow -- aspnetboilerplate` 取得框架历史，再按[统一入口](#统一入口)生成自己的配对证据。可用下方的 `compare-restore`、`compare-api` 命令核对两份归档中的原始清单。

本地首次完整调用因中文 VSTest 版本行未被解析而退出 1，虽然三条测试命令均完成并生成 TRX。修正版本行解析并通过中英文定向用例后，本地第二次调用成功。针对实际清单副本的传递包版本变异在三方比较处退出 1，构建、API 和回归显示为未执行。API 参数变异定位到 `Abp.Application.Features.Feature.RemoveChildFeature` 的 `System.String` 到 `System.Int32` 签名变化并退出 1。Python 夹具另覆盖对象或 SDK 不符、产物缺失、TRX 异常和有效测试数门禁。工作流定义模拟验证了自检失败、零用例和全部跳过会阻断完整命令并留存自检日志，以及完整命令失败时传播退出状态并留存部分证据。真实 GitHub 作业验证的是成功路径。

本次覆盖 macOS ARM64、原版 R0 源码和内存 SQLite。未执行 Windows、Linux、其他数据库 Provider、AutoMapper 或 Angular 消费组合、Samples 专项、候选包还原与发布，以及 R1 补丁和完整模板的验收。

## 来源与还原

在主仓根目录执行。先从主仓提交查询 gitlink，再用子模块对象核对引用。三个上游标签可直接查询，Angular 参考版本以库清单的 Git 对象为准。

```sh
git ls-tree cf1420d6dc967fe2b34b52c0409e8407140e917e
git submodule status --cached
git ls-remote https://github.com/aspnetboilerplate/aspnetboilerplate.git refs/tags/v10.5.1
git ls-remote https://github.com/AutoMapper/AutoMapper.git refs/tags/v14.0.0
git ls-remote https://github.com/AutoMapper/AutoMapper.Collection.git refs/tags/v11.0.0
git -C abp-ng2-module show afbd23ea9711e9d94259d0f0b6afcbab9a0617fc:projects/abp-ng2-module/package.json
git -C module-zero-core-template ls-tree -r --name-only 2e9536872673a7ff1986a19e798c51684d16afe5 aspnet-core
git -C module-zero-core-template grep -n -E 'PackageReference Include="Abp|ProjectReference' \
  2e9536872673a7ff1986a19e798c51684d16afe5 -- 'aspnet-core/*.csproj'
```

[复验脚本](../baseline-tools/reproduce.zsh) 用 `git archive` 从固定框架提交分别物化两个独立源码目录，并在各自目录为五个框架项目和三个回归套件生成临时解法 `R0.sln`。两次都使用空的独立包目录及 `--no-http-cache`，配置文件仅启用公开的 nuget.org。脚本保留工作目录、命令、退出码、SDK 信息和控制台原始输出。主轮还求值五个项目的 MSBuild 身份，并以该轮的还原结果构建 Release 和运行三套测试。

```sh
repo=$(git rev-parse --show-toplevel)
evidence=$(mktemp -d "${TMPDIR:-/tmp}/aspnetboilerplate-r0.XXXXXXXX")
baseline="$repo/docs/maintenance/baseline-evidence"
tools="$repo/docs/maintenance/baseline-tools"
zsh "$tools/reproduce.zsh" "$evidence" primary
zsh "$tools/reproduce.zsh" "$evidence" repeat
python3 "$tools/inventory.py" compare-restore \
  "$evidence/primary-restore-inventory.json" "$evidence/repeat-restore-inventory.json"
python3 "$tools/inventory.py" compare-restore \
  "$baseline/nuget-restore.json" "$evidence/primary-restore-inventory.json"
```

[实际还原清单](nuget-restore.json) 递归遍历入口和实际 `ProjectReference`，从每个 `project.assets.json` 提取按目标分组的包 ID 和版本，并根据同一目标的直接依赖声明标记直接或传递依赖。包目录的 `.nupkg.metadata` 提供实际包来源和内容哈希。宿主 RID 是 `osx-arm64`，此次还原目标均为 `net9.0`，`runtimeIdentifier` 为 `null`。两次还原比较覆盖 11 个项目和 11 个目标，结果一致。[还原比较结果](nuget-comparison.json)

框架源码的 `Directory.Build.props` 和 `common.props` 分别为 `Microsoft.SourceLink.GitHub` 声明了两个版本，两轮还原各报告 8 个 `NU1504`。图中实际解析到的版本以清单为准。Release 同时记录了过时 API 及源码归档缺少 Git 工作目录导致的 SourceLink 警告。

## 公共 API 和程序集

用同一 SDK 生成 [API 提取工具](../baseline-tools/ApiInventory.csproj)。该工具直接读取 PE 元数据，包含完整类型名、公开和受保护成员、可见属性与事件访问器、重载参数、返回类型、泛型约束和清单资源名。类型继承的成员记录于各自声明类型中。基线记录中的 SHA-256 对应各次生成的具体 DLL。

```sh
cp -R "$tools" "$evidence/tools"
cd "$evidence/primary"
dotnet build "$evidence/tools/ApiInventory.csproj" --configuration Release \
  -p:RestoreConfigFile="$evidence/primary.NuGet.Config"
extractor="$evidence/tools/bin/Release/net9.0/ApiInventory.dll"
for name in Abp Abp.AspNetCore Abp.EntityFrameworkCore Abp.Web.Common Abp.EntityFramework.Common; do
  dll="src/$name/bin/Release/net9.0/$name.dll"
  shasum -a 256 "$dll"
  dotnet "$extractor" "$dll" > "$evidence/$name.json"
  dotnet "$extractor" "$dll" > "$evidence/$name.repeat.json"
  cmp "$evidence/$name.json" "$evidence/$name.repeat.json"
  python3 "$tools/inventory.py" compare-api "$baseline/api/$name.json" "$evidence/$name.json"
done
```

同一个 DLL 提取两次，清单逐字节一致。换目录执行完整复跑后，五个程序集的身份、类型、成员和资源均相同。两次构建的 DLL 摘要分别登记在基线中。两个 `Abp.dll` 内含的 PDB 路径各自指向其绝对构建目录。

以下只修改清单副本中的一个公开方法参数。比较器预期退出码为 1，并报告程序集、类型及变化前后的签名。[实际变异比较结果](api-mutation-comparison.json)

```sh
python3 - "$baseline/api/Abp.json" "$evidence/Abp.mutation.json" <<'PY'
import json
import sys
from pathlib import Path

original, mutation = map(Path, sys.argv[1:])
manifest = json.loads(original.read_text())
members = manifest["types"]["Abp.Application.Features.Feature"]
signature = "method [Public, HideBySig] RemoveChildFeature(System.String name) -> System.Void [Default]"
members[members.index(signature)] = signature.replace("System.String name", "System.Int32 name")
mutation.write_text(json.dumps(manifest, indent=2) + "\n")
PY
python3 "$tools/inventory.py" compare-api "$baseline/api/Abp.json" "$evidence/Abp.mutation.json"
```

## 三套回归

脚本为各套件保留 TRX 和控制台记录，三套均运行了实际测试。两次独立完整运行的计数相同。

| 套件 | 通过 | 失败 | 跳过 |
| --- | ---: | ---: | ---: |
| `Abp.Tests` | 1105 | 0 | 2 |
| `Abp.AspNetCore.Tests` | 150 | 0 | 0 |
| `Abp.EntityFrameworkCore.Tests` | 58 | 0 | 0 |

`Abp.Tests` 的 2 个跳过各有对应的 TRX `NotExecuted` 项，名称和原因详见基线记录。xUnit 在发现阶段另外去重了 42 条重复 ID，运行器报告的 1107 项总数未计入这些重复条目。

统一入口按 `UnitTestResult` 明细和完整测试名核对跳过项，并交叉校验汇总。核心套件的原始 TRX 明细为 1105 个 `Passed`、两个基线中具名的 `NotExecuted`，汇总为 `total=1107`、`executed=1105`、`passed=1105`、`failed=0`、`notExecuted=0`。仅在本套件的完整测试名及其余关键计数均匹配时，报告接受这组 `notExecuted` 差异并单独登记。

`Abp.EntityFrameworkCore.Tests` 的 `BloggingDbContext` 和 `SupportDbContext` 均由 `EntityFrameworkCoreTestModule` 通过 `UseSqlite` 接入已打开的 `Data Source=:memory:` 连接。实际资产包括 `Microsoft.EntityFrameworkCore.Sqlite 9.0.18`、`Microsoft.Data.Sqlite 9.0.18` 和 ARM64 SQLite 原生库。完整模板及候选包消费者的实际状态见基线中的 R2、R3 记录。
