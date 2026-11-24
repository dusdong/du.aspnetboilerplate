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
