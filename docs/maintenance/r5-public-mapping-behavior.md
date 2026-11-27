# 公开 R4 与 R5 映射业务实测

2026-11-27，公开 R4 `v10.5.1` 与 R5 `v10.5.2` 在同一 macOS ARM64、.NET 10 和 SQLite 组合上分别通过已有用户更新、按键集合更新和查询投影。两侧输入校验通过，总入口、两侧入口和探针均退出 0。两张还原图各有 46 个包，只有三个映射包的版本不同。两侧业务记录，以及实际 SQL、参数、取列顺序、投影表达式和物化行，逐项相同。

## 公开复跑

在包含本报告配套入口的主仓检出根目录执行。准备 Git、Python 3、macOS ARM64 下的 .NET SDK `10.0.404` 和运行时 `10.0.15`，以及可访问 GitHub 和 nuget.org 的网络。固定模板由主仓子模块提供。

```sh
git submodule update --init -- module-zero-core-template
INPUT_DIR="$(mktemp -d "$(git rev-parse --absolute-git-dir)/public-mapping.XXXXXX")"
curl -fL https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json \
  -o "$INPUT_DIR/R4-PACKAGE-CHECKSUMS.json"
curl -fL https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.2/R5-PACKAGE-CHECKSUMS.json \
  -o "$INPUT_DIR/R5-PACKAGE-CHECKSUMS.json"
python3 -B eng/r5_public_mapping_consumer.py \
  --r4-checksums "$INPUT_DIR/R4-PACKAGE-CHECKSUMS.json" \
  --r5-checksums "$INPUT_DIR/R5-PACKAGE-CHECKSUMS.json" \
  --output "$INPUT_DIR/r4-r5"
```

输出目录须尚不存在。可用 `--dotnet /绝对路径/dotnet` 指定宿主。脚本为每侧建立独立消费目录、包和 HTTP 缓存、临时目录及 Release 输出，随后在两个独立进程里运行各自的 SQLite 内存库。若一侧输入校验失败或业务断言未通过，入口返回非零，保留已取得的原始输出、预期和实测，另一侧独立执行。总报告字段 `comparison.usableForVersionConclusion` 标明本轮能否用于版本比较。[探针用法与定向反例](../../validation/automapper/README.md)

## 实测输入与包身份

正式运行时间为 2026-11-27 07:54:09 至 07:55:00 UTC。主仓基点为 `3b0b21ce6665d3f05681780340c6bf69370a1697`，使用含本次入口的工作树候选。两侧从模板 gitlink `2e9536872673a7ff1986a19e798c51684d16afe5` 提取同一份 `User`、`Role`、`UserDto`、`CreateUserDto` 和 `UserMapProfile` 编译，并另外保存该提交的应用模块供核对扫描配置。探针通过经典 ABP 配置启动模块，从 Castle 解析 `IObjectMapper` 和 `MapperConfiguration`。模板文件及消费者的 SHA-256 记录在每侧 `report.json` 的 `inputs` 下。[探针模块](../../validation/automapper/ProbeModule.cs) · [对象与集合断言](../../validation/automapper/Program.cs) · [投影与种子](../../validation/automapper/Projection.cs)

两侧使用 macOS `27.2.1` ARM64、宿主 `/usr/local/share/dotnet/dotnet`、SDK `10.0.404`、目标 `net10.0`、Release 和实际加载的 `.NET 10.0.15`。每侧的 Provider 为 `Microsoft.EntityFrameworkCore.Sqlite` `10.0.15`，已加载程序集版本为 `10.0.15.0`，通过实际连接取得的原生 SQLite 版本为 `3.53.3`。还原使用仅含 `https://api.nuget.org/v3/index.json` 的配置、`--no-http-cache --force` 和空回退目录。构建使用 `-c Release --no-restore`，探针进程以 `DOTNET_ROLL_FORWARD=Disable` 执行。

| 公开输入 | 发行提交 | 附件 SHA-256 |
| --- | --- | --- |
| `v10.5.1`，`R4-PACKAGE-CHECKSUMS.json` | `5758c8186b68dcc42ecc90164cf9d3f53cf3345e` | `c3a905b6a6373a59236214f94fce953abb530fc61c80a7fe94ff99f028f534b0` |
| `v10.5.2`，`R5-PACKAGE-CHECKSUMS.json` | `cebc3e38a511783092963893bf5ad3161d0f0a19` | `be08d2d354d71dcb09802f8161496f213ebdd257826ed5adbf6af77fe9000dd5` |

两侧直接引用各自精确版本的 `Du.Abp.AutoMapper`，并直接引用 `Du.Abp.ZeroCore [10.5.1]` 与 `Microsoft.EntityFrameworkCore.Sqlite [10.0.15]`。每侧实际还原的六个维护主包逐个匹配公开附件中的签后下载摘要。R5 的 `Du.Abp`、`Du.Abp.Zero.Common`、`Du.Abp.ZeroCore` 均为 `10.5.1`，通过 R5 附件的 R4 沿用记录核对。原始还原图中没有原版映射或上游 ABP 包回流。除三个映射包的版本与内容外，原始包图的其他包、归档摘要和资产选择均一致。两侧 nuspec 声明与实际还原图中的四条精确依赖如下。[公开签后实物登记](r5-public-patch-review.md#主包与签后实物)

| 依赖边 | R4 | R5 |
| --- | --- | --- |
| `Du.Abp.AutoMapper` → `Du.Abp` | `[10.5.1]` | `[10.5.1]` |
| `Du.Abp.AutoMapper` → `Du.AutoMapper` | `[14.0.0]` | `[14.0.1]` |
| `Du.Abp.AutoMapper` → `Du.AutoMapper.Collection` | `[11.0.0]` | `[11.0.1]` |
| `Du.AutoMapper.Collection` → `Du.AutoMapper` | `[14.0.0]` | `[14.0.1]` |

三份映射 DLL 按还原图选定，包内成员、Release 输出与进程加载路径的文件 SHA-256 逐一相同。探针在业务执行后枚举所有加载上下文，两侧各在 `Default` 中加载一份 `AutoMapper`。三个程序集的程序集版本分别为 `10.5.1.0`、`14.0.0.0` 和 `11.0.0.0`，两代均通过 NuGet 包版本和实际字节区分。

| 所选包内资产 | R4 包版本与 DLL SHA-256 | R5 包版本与 DLL SHA-256 |
| --- | --- | --- |
| `lib/net9.0/Abp.AutoMapper.dll` | `10.5.1` · `87e3cbbe1a600adb8b4cd51feb638ef0271d75a7126b6d7f7a85c8f96cadf07f` | `10.5.2` · `82bb376e405ba42dbbe2bd7caab4590691a0374bb4e0772797cbf3e24cb95137` |
| `lib/net8.0/AutoMapper.dll` | `14.0.0` · `12fcba523f7f7199215764b29c5d330aa363c433fa14d4e72257ce835a87e5e1` | `14.0.1` · `1d752c32c70cff281afc3bee951abdf763b0910ba74be6a4772854149fe75bd0` |
| `lib/net8.0/AutoMapper.Collection.dll` | `11.0.0` · `8f64b1194121a7dd5be23d6bffa7456765590905f2ae5dff5414bcc9f5adfd58` | `11.0.1` · `0d942343005bb358f381fb9d09543a04d66affd7a90029cb4a8ef33ad457ca2e` |

## 逐项业务结果

| 场景和预期 | R4 实测 | R5 实测 |
| --- | --- | --- |
| 已有用户保留目标、原角色集合和原角色对象引用，保留创建时间。活跃状态和普通字段取 DTO 的值。 | 通过。返回原用户 `27`，角色集合及原成员引用保留，创建时间仍为 `2020-12-31T23:57:00Z`。得到 `New`、`User`、`newuser`、`new@example.invalid`，`IsActive` 从 `false` 变为 `true`。 | 通过。返回原用户 `27`，角色集合及原成员引用保留，创建时间仍为 `2020-12-31T23:57:00Z`。得到 `New`、`User`、`newuser`、`new@example.invalid`，`IsActive` 从 `false` 变为 `true`。 |
| 按键集合保留目标集合和键 10 的原对象，更新键 10，删除键 20，只新增一个键 30。 | 通过。目标及键 10 保留原引用，键 20 移除，键 30 为新对象且只出现一次，依次为 `10:updated`、`30:inserted`。 | 通过。目标及键 10 保留原引用，键 20 移除，键 30 为新对象且只出现一次，依次为 `10:updated`、`30:inserted`。 |
| SQLite 查询按租户和活跃状态过滤，按用户名降序、ID 升序，取列和物化值满足预期，客户端计算 `FullName`。 | 通过。参数 `@tenantId` 为 `Int32` 6，筛选和排序命中，29 列顺序命中，物化 ID 为 `12、13、11`，`FullName` 来自客户端实体属性。 | 通过。参数 `@tenantId` 为 `Int32` 6，筛选和排序命中，29 列顺序命中，物化 ID 为 `12、13、11`，`FullName` 来自客户端实体属性。 |

两侧原角色成员均为 `Id=46, UserId=27, RoleId=37, TenantId=4`，输入角色名为 `DifferentRole`，输入创建时间为 `2022-12-31T23:57:00Z`。同一场景还验证 `CreateUserDto` 映射得到活跃用户 `created`，角色由映射配置忽略。

投影通过 `AsNoTracking`、`Where`、`OrderByDescending`、`ThenBy` 和 `Select(dtoUser => new UserDto { … })` 组合查询。SQLite 拦截器记录的筛选与排序如下。两侧的返回列按同一份 [固定列预期](../../validation/automapper/projection-columns.json) 顺序读取，从 `UserName` 开始、到 `TenantId` 结束。投影表达式中 `FullName = dtoUser.FullName` 绑定到继承的 `Abp.Authorization.Users.AbpUserBase.FullName`，实际 SQL 取回实体列，由客户端访问该属性计算全名。

```sql
FROM "Users" AS "u"
WHERE "u"."TenantId" = @tenantId AND "u"."IsActive"
ORDER BY "u"."UserName" DESC, "u"."Id"
```

| 两侧物化顺序 | `Id` | `UserName` | `Name` | `Surname` | `EmailAddress` | `FullName` |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 12 | `zulu` | `Zoe` | `Zulu` | `zulu@example.invalid` | `Zoe Zulu` |
| 2 | 13 | `beta` | `Bea` | `Beta` | `beta@example.invalid` | `Bea Beta` |
| 3 | 11 | `alpha` | `Ada` | `Alpha` | `alpha@example.invalid` | `Ada Alpha` |

三行的 `IsActive` 均为 `true`，`CreationTime` 均为 `2022-04-13T12:00:00`，`LastLoginTime` 和 `RoleNames` 均为 `null`。过滤掉的输入包含其他租户及非活跃用户。

## 原始证据与失败判定

本次本地证据保存在主仓 Git 目录的 `validate-r5-public-mapping-behavior/package-1/` 下。公开复跑会生成相同结构的报告，路径、进程号和时间随执行变化。

| 核对项 | 相对本地证据根的路径 |
| --- | --- |
| 正式命令、日志、总退出码与两侧比较 | `formal-qualified.command`、`formal-qualified.log`、`formal-qualified.exit`、`formal-qualified/report.json`、`formal-qualified/graph-difference.json` |
| 实际子命令、阶段退出码、运行时、输入摘要与逐项判定 | `formal-qualified/{r4,r5}/report.json`，命令的参数、工作目录及环境覆盖在 `stages.*.commands` |
| 两张原始还原图与 Release 日志 | `formal-qualified/{r4,r5}/consumer/obj/project.assets.json`、同侧的 `restore.log`、`build.log`、`build.binlog` |
| 签后包、包内所选资产、输出与最终加载 | `formal-qualified/{r4,r5}/verified-public-archives.json`、`mapping-assets.json`、`mapping-output.json`、`mapping-loaded.json` |
| 对象引用、实际 SQL、参数、列顺序、完整表达式和 DTO 行 | `formal-qualified/{r4,r5}/process/probe.json` 与同目录的 `process.log` |
| 公开附件和运行候选摘要 | `public-inputs/{R4,R5}-PACKAGE-CHECKSUMS.json`、`report-qualification/candidate-sha256.txt` |

正式总报告 `formal-qualified/report.json` 的 SHA-256 为 `ba1d2edab0e03c976de38f118c54813437d30cb9066d5181b1582dea84c3ed37`。独立复核直接读取原始还原图与进程文件，重算附件、模板输入、归档、Release 输出及实际加载文件的摘要，并将每侧业务与固定期望逐项比较。记录在同级 `package-2/audit-evidence.log`。

| 验收 | 实测或回放结果与证据 |
| --- | --- |
| 错误主包摘要，实际执行 | `wrong-package/report.json`。仅在 R4 附件副本中把 `Du.Abp.AutoMapper/10.5.1` 的签后摘要改为全零，使用反例入口。R4 还原成功，在核对实际归档时报告版本、包名和两个摘要，R4 构建、探针和三项业务均未执行。R5 独立通过，总入口退出 1。 |
| 仅 R4 换列，实际执行 | `wrong-r4-columns-qualified/report.json`。只把 R4 预期中的 `UserName, Name` 交换为 `Name, UserName`。两侧输入合格并真实执行查询。R4 用户和集合通过，物化后因列顺序不符退出 1，其 `r4/process/probe.json` 完整保留 SQL、参数、实际列、表达式与三行。R5 三项通过，退出 0。总入口退出 1。 |
| 两侧同时换列，实际执行 | `wrong-both-columns/report.json`。实际 SQL、返回列和三条物化行仍相同。两侧各自的用户、集合通过，投影分别失败，两个探针和总入口均退出 1。 |
| 受影响的历史入口，实际执行 | `historical-frozen-final/report.json` 和 `historical-r3/r3-automapper-es68z3i0/report.json`。使用 .NET `9.0.23` 隔离宿主保留历史 `net9.0`、EF Core SQLite `9.0.18` 的业务入口。冻结批次的最小、候选业务和原版业务通过。R3 的输入、最小入口、原版、候选、对照和既有负向诊断通过。两个入口均退出 0，各有同名 `.command`、`.log` 与 `.exit` 记录。 |
| 定向测试与报告回放 | `report-qualification/focused-tests.log` 的 16 项 Python 测试均通过，包括缺投影、两侧相同的错误状态值、失配输入和已有公开回退入口测试。另用已保存的报告形状分别改写 R4 运行时、R4 加载摘要及 R5 非映射包内容摘要，三份入口结果各退出 1，回放断言退出 0。前两份将 R4 已观测的三项业务标为 `unqualified`，包图失配时保留已核验的两侧观测并拒绝形成版本结论。这三份位于 `report-qualification/{runtime-mismatch,loaded-dll-mismatch,graph-mismatch}/report.json`，来自回放脚本，未在这些失配条件下启动真实 .NET 进程。 |

正式轮两份 GitHub 附件采用既有公开下载原件的副本，签后摘要清单与上表字节一致。首次直接获取附件遇到超时和 HTTP/2 错误，详见 `public-inputs/*.download.log`。首次消费曾因 R4 附件没有 `tagObject`，以及命令参数中的 `PosixPath` 无法序列化失败，随后按各代附件结构和字符串参数修正。第一次有完整业务输出时，外层把 `FullName` 的声明类型错记为模板 `User`，核对源码及表达式后改为继承的 `AbpUserBase`，从双空缓存重跑。旧输出分别保存在 `initial-public/`、`public-retry/`、`public-retry-2/`。历史冻结入口首次因系统临时卷只余 234 MiB 未通过容量检查，随后指定工作卷内的 `TMPDIR` 完成。正式轮的 NuGet 包仍从 nuget.org 独立取得。

## 适用范围

本轮结论适用于固定模板配置上这三种独立映射调用。模板 `UserAppService.UpdateAsync` 在对象映射和更新后还会在 `RoleNames` 有值时调用 `SetRolesAsync`，所以探针保留角色引用的结果只描述映射阶段。模板用户列表沿用先物化实体、再逐个映射 DTO 的流程，本轮 `ProjectTo<UserDto>` 的 SQL 来自独立 SQLite 查询。SQL Server、Angular、迁移和同库回退按既有完整模板报告的实测组合判断。共享集合执行计划的预热顺序差异按专项记录查阅。其他数据库 Provider、Windows 或 Linux 以及自定义 Profile 的适用范围需由相应消费结果确定。[固定模板验收](r5-automapper-template.md) · [共享集合计划专项](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/shared-collection-plan-observation.md)

这次固定组合的三项业务结果未出现未解释差异，沿用此前维护审查的无需补丁决定。遇到包来源、运行时或非映射依赖偏离，按公开命令重新固定输入再复测。每侧分别对照预期，以便识别两侧共同偏离。[维护决定与续查](r5-public-patch-review.md#本轮维护决定)
