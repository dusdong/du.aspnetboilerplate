# R3 AutoMapper 原版基线

2026-11-25，原版独立消费者在 macOS 27.2.1 ARM64（`26B131`）使用 SDK `10.0.404` 和实际运行时 `9.0.23`。固定模板的用户配置可由 Castle 启动，经 `IObjectMapper` 更新已有用户。独立集合用例保留匹配项引用，SQLite 查询过滤、排序后读取 29 列，再从已物化的用户实体计算 `FullName`。[原版 Web.Host 依赖](r3-web-host-baseline.md) · [OpenSpec 归档](../../openspec/changes/archive/2026-11-25-add-r3-automapper-candidates/)

## 固定输入

| 源码 | 主仓 `d54f782fe91cbf0230680c94256913ce46b0581d` 的 gitlink | 验证基点 |
| --- | --- | --- |
| AutoMapper | `79d10deec5881a617c38e7373f354694044bf83d` | `bf76a5819e1bad7af7db5382bf0f3a0178048a15`，`v14.0.0`，`LICENSE.txt` |
| AutoMapper.Collection | `5301edbc689a9696bdd7c396452669434e75989a` | `eafbf005becf73f989e1b1c0d52e8699439f837c`，`v11.0.0`，`LICENSE` |
| aspnetboilerplate | `819c64cf527b6918a5eafbf42550c93400f1fb75` | 同 gitlink，普通项目版本 `10.5.1` |
| 模板 | `2e9536872673a7ff1986a19e798c51684d16afe5` | 同 gitlink |

上游标签分别指向表中的两个映射基点。两份许可证均为 MIT。引擎许可摘要为 `dff9366748df4c70e36fe6fd289f5f87010e74d1d16c06ff11f97ea2c72c75f1`，Collection 许可摘要为 `16af44b5a3fd6962f904e2932c9c7c923c44988843fb825b37da7882a194dc74`。[引擎参考许可](https://github.com/LuckyPennySoftware/AutoMapper/blob/v14.0.0/LICENSE.txt) · [Collection 参考许可](https://github.com/AutoMapper/AutoMapper.Collection/blob/v11.0.0/LICENSE)

框架公共 Git 目录的分配记录已存在 R3.1、R3.2、R3.3。R3.2 首次生产失败后保留占号，核对时下一可用序号为 R3.4。下表候选版本为计划输入，实际占号以打包时分配记录为准。

| 项目 | 目标 · 程序集 · 根命名空间 | 普通源码包和直接运行依赖 | 计划候选和直接运行依赖 |
| --- | --- | --- | --- |
| 映射引擎 | `net8.0` · `AutoMapper` · `AutoMapper` | `AutoMapper 14.0.0` → `Microsoft.Extensions.Options 8.0.0` | `Du.AutoMapper 14.0.0-r3.4` → `Microsoft.Extensions.Options 8.0.0` |
| 集合扩展 | `net8.0` · `AutoMapper.Collection` · `AutoMapper.Collection` | `AutoMapper.Collection 11.0.0` → `AutoMapper [14.0.0, 15.0.0)` | `Du.AutoMapper.Collection 11.0.0-r3.4` → `Du.AutoMapper [14.0.0-r3.4]` |
| 适配器 | `net9.0` · `Abp.AutoMapper` · `Abp` | `Abp.AutoMapper 10.5.1` → `Abp` 项目引用、`AutoMapper 14.0.0`、`AutoMapper.Collection 11.0.0` | `Du.Abp.AutoMapper 10.5.1-r3.4` → `Du.Abp [10.5.1-r2.1]`、`Du.AutoMapper [14.0.0-r3.4]`、`Du.AutoMapper.Collection [11.0.0-r3.4]` |

回读 R2 冻结的五个原包、各自两个目标的 DLL 摘要和四份登记证据。使用 Module Zero 原验收器的输入及包阶段回读三个 R3.3 主包、符号包、包内 DLL/PDB、生产文件和对应的三份 R2 依赖。原件的冻结摘要见登记；本次回读结果在验收机的 `.git/r3-automapper/package-1/frozen/`。[R2 实包登记](../../eng/r3_r2_reference.json) · [Module Zero 冻结登记](../../eng/r3_module_zero_reference.json) · [Module Zero 消费闭包](r3-module-zero-candidates.md#消费闭包与运行)

## 普通引擎 Release 与 ApiCompat

上游 Unix 脚本的 Git 模式为 `100644`，固定源码直接执行时以 `MSB3073` 退出 1，脚本退出 126。脚本还使用本机 Bash 3.2 缺少的 `readarray` 和历史包中不存在的 DLL 路径。修复后的普通 Release 通过显式 `/bin/sh` 准备历史参考，并实际执行原项目已引用的 `Microsoft.DotNet.ApiCompat 7.0.0-beta.22074.1`。启用固定源码已登记的 13→14 差异基线，比较结果为 `Total Issues: 0`。已登记的差异基线 SHA-256 为 `a696e37e72dbca86321719b721eb599d56a9828a0bc49a755bf39419f22189dc`。引擎普通 Release 的程序集版本为 `14.0.0.0`，公钥标记为 `be96cd2c38ef1005`。[引擎复跑入口](../../AutoMapper/src/AutoMapper/ApiCompat/README.r3.md)

| 历史参考 | 固定值 |
| --- | --- |
| NuGet 包 | `AutoMapper 13.0.0` |
| 包内资产 | `lib/net6.0/AutoMapper.dll` |
| 归档 SHA-256 | `8ac567aa1ef2ecb44d02583432754e1a57cb64ac2bea3ef01966d25c27c7d621` |
| DLL SHA-256 | `61f544f9574b415832fb4130c8bde2e3370214a35acc75ce1e89f2032a04abe5` |

如需在干净导出中重建普通 Release，可从主仓根目录执行以下命令。验收入口在证据目录固定 SDK `10.0.404`。

```sh
mkdir "$CLEAN_SOURCE"
git -C AutoMapper archive bf76a5819e1bad7af7db5382bf0f3a0178048a15 | tar -xf - -C "$CLEAN_SOURCE"
cp AutoMapper/src/AutoMapper/AutoMapper.csproj "$CLEAN_SOURCE/src/AutoMapper/"
cp AutoMapper/src/AutoMapper/ApiCompat/PreBuild.sh AutoMapper/src/AutoMapper/ApiCompat/verify-release.sh \
  "$CLEAN_SOURCE/src/AutoMapper/ApiCompat/"
sh "$CLEAN_SOURCE/src/AutoMapper/ApiCompat/verify-release.sh" "$NEW_EVIDENCE" "$REFERENCE_NUPKG"
```

也可省略包路径从 nuget.org 获取同摘要的参考。入口保存真实工具调用、比较响应文件、二进制日志和普通 DLL 摘要。[历史参考包](https://www.nuget.org/packages/AutoMapper/13.0.0)

本机 `.git/r3-automapper/package-1/api-accepted/` 使用冻结包原件，`api-pinned/` 从 nuget.org 获取参考。两轮均退出 0，实际比较均为 0 个差异；两份 `ordinary-api-identity.json` 的程序集身份、公开 API、资源一致。各轮 Release DLL 的单独摘要在 `release-sha256.txt`。定向证据 `api-diagnostics/` 中，缺包与错误摘要均退出 1，使用空差异基线的真实 MSBuild 比较报告 71 项历史差异并退出 1。

## 原版消费者

从主仓根目录运行一次初验和一次复验。每轮创建新项目、NuGet 缓存和实际进程临时目录。两组输出的 `business-result.json` 可直接用 `cmp` 比较。

```sh
DOTNET="$PWD/.git/r2-core-consumption/package-2/toolchain/overlay/dotnet"
python3 -B eng/r3_automapper_business.py --dotnet "$DOTNET" --evidence-root "$NEW_INITIAL_EVIDENCE"
python3 -B eng/r3_automapper_business.py --dotnet "$DOTNET" --evidence-root "$NEW_REPEAT_EVIDENCE"
```

固定模板 Git 对象提供 `UserMapProfile`、`CreateUserDto`、`UserDto`、`User` 和 `Role` 的未改原文件。报告另外保存模板 ApplicationModule 的原件摘要。独立模块沿用该配置的 `Configurators` 与 `AddMaps` 扫描入口，并启用 `AddCollectionMappers`。独立消费者只从 nuget.org 直接还原 `Abp.AutoMapper 10.2.0`、`Abp.ZeroCore 10.2.0` 与 EF Core SQLite `9.0.18`，传递取得 `Abp 10.2.0`、`Abp.Zero.Common 10.2.0`、`AutoMapper 14.0.0` 和 `AutoMapper.Collection 11.0.0`。[消费者源码](../../validation/automapper/) · [复跑入口](../../eng/r3_automapper_business.py)

- 用户更新通过原配置的重复 `CreateMap`。目标实例、角色集合及原成员引用均保持，创建时间保留，姓名、用户名、邮箱和启用标志更新。另执行固定 `CreateUserDto` 的重复映射并检查 `Roles` 忽略行为。
- 集合按独立 DTO 上的 `AutoMapKey` 更新。保留目标集合和键 `10` 的原对象并更新值，移除键 `20`，仅新增一个键 `30` 对象。此用例经过 ABP 对 Collection 扩展程序集的反射加载。
- SQLite Provider `9.0.18`、原生 SQLite `3.46.1` 执行带标签的查询。命令截获器记录实际 SQL、参数、读取列以及结果。SQLite 使用整型租户参数 `6` 和活跃条件过滤，以用户名降序、ID 升序排序，返回 ID `12, 13, 11` 对应 `Zoe Zulu`、`Bea Beta`、`Ada Alpha`。投影表达式访问标为 `NotMapped` 的 `AbpUserBase.FullName`。实际 SQL 选择了 29 个实体标量列，客户端从实体属性得到姓名。后续候选使用同一组断言判定列集、顺序和计算位置。

本机两轮最终验收均退出 0。以下路径相对 `.git/r3-automapper/package-1/`。

| 验收报告 | SHA-256 |
| --- | --- |
| `business-accepted-1/original-3sk5osok/report.json` | `6960b93c9bfa9ca7f8d7fe090596c26a528935dbcf7e5689c65e84735ca89fbc` |
| `business-accepted-2/original-a4lb0y3a/report.json` | `17c1f3a4ad65440d37079a7493da6fae9b96d516c9f8af5e784537ef8576cf76` |

两轮分别在独立进程执行。五个原样编译的模板源文件和 ApplicationModule 原件的摘要相同；76 个包的解析版本、边、资产与归档摘要一致；实际加载程序集与各自 Release 输出和包内 DLL 逐一同摘要。业务结果文件逐字节相同，SHA-256 为 `01309fd171e6e66d47b68affe4aad0b80ac43d96d1d69d165078ed661780077b`。报告保存实际进程退出码、工作目录、原始 `project.assets.json` 和对照证据。较早的 SQLite 夹具因用户审计导航关系缺少配置在模型构建阶段失败，修正了独立夹具的导航映射后，两轮从空缓存重新还原、构建并执行。模板源码和包未因夹具调整而改变。

适用范围为独立消费者的普通映射行为。本基线使用隔离的新建内存 SQLite，完整模板宿主、真实登录、SQL Server、候选包、安全公告处置、发包与部署由后续验收阶段覆盖。
