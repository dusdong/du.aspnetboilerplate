# R3 Module Zero 候选验收

2026-11-25，本机独立消费者从冻结的 `10.5.1-r3.3` 与 R2 `10.5.1-r2.1` 原包还原，在 `net9.0` 使用真实 ABP 角色存储和 SQLite。两笔租户角色写入各自提交后，两个新工作单元各读回本租户角色，并对另一租户角色的 ID 返回 `null`。两轮严格验收均使用 macOS 27.2.1 ARM64（`26B131`）、SDK `10.0.404` 和实际加载的两项 `9.0.23` 共享运行时。 [稳定消费规范](../../openspec/specs/module-zero-package-consumption/spec.md) · [OpenSpec 归档](../../openspec/changes/archive/2026-11-25-add-r3-module-zero-candidates/)

## 复跑冻结批次

从主仓根目录运行以下命令。首次验收机上的 `R3` 和 `R2` 路径指向两批原件。迁移到另一位置时，将路径改为原件目录。R3 目录保留 `manifest.json`、`source.patch`、`du-r3-candidate-source.json`、`feed/`、`symbols/` 和清单登记的生产日志。R2 目录保留其原清单、补丁、源码证明和 `feed/`。本机已登记 R3 生产清单 SHA-256 为 `308e95aa52e3d58958987f2c82631b98ae12d1276449576a8d509080d1080193`。 [冻结登记](../../eng/r3_module_zero_reference.json) · [R2 实包登记](../../eng/r3_r2_reference.json)

```sh
R3="$PWD/.git/r3-module-zero/package-1/10.5.1-r3.3"
R2="$PWD/.git/r2-core-consumption/package-1/10.5.1-r2.1"
DOTNET="$PWD/.git/r2-core-consumption/package-2/toolchain/overlay/dotnet"
EVIDENCE="$PWD/.git/r3-module-zero/local-consumption"

python3 -B eng/verify.py --profile r3-module-zero \
  --dotnet "$DOTNET" --candidate-feed "$R3/feed" \
  --candidate-manifest "$R3/manifest.json" --candidate-symbols "$R3/symbols" \
  --r2-feed "$R2/feed" --evidence-root "$EVIDENCE" --strict-runtime-baseline
```

每次调用在证据父目录创建唯一运行目录，从独立空包缓存与 HTTP 缓存还原，映射 R2、R3 和 nuget.org 三个源，再执行 Release `build --no-restore`。严格复现要求所选 ARM64 `dotnet` 实际加载 `Microsoft.NETCore.App` 和 `Microsoft.AspNetCore.App` 的 `9.0.23`。本机普通复验可指定 `/usr/local/share/dotnet/dotnet` 并省略 `--strict-runtime-baseline`，仍要求 SDK `10.0.404`，两项共享运行时按实际加载位置和 `9.0.x` 版本判定。

## 源码生产新批

生产使用框架检出的 `nupkg/pack-r3-module-zero-candidates.sh`。R3 生产者共用框架 Git 公共目录的 `du-r3-leaf-candidate-versions/`，在输入预检后原子占用序号。`10.5.1-r3.1` 已分配给 SignalR 与 Log4Net，`10.5.1-r3.2` 的生产在首个 restore 之后失败并保留占号，`10.5.1-r3.3` 已冻结。截至本机验收，下一可用序号为 `10.5.1-r3.4`。执行时用下列命令核对分配目录，再使用新的输出目录。 [框架生产说明](../../aspnetboilerplate/nupkg/README.r3-module-zero.md)

```sh
ROOT="$PWD"
R2="$ROOT/.git/r2-core-consumption/package-1/10.5.1-r2.1"
SDK_DIR="$ROOT/.git/r2-core-consumption/package-2/toolchain/overlay"
version=10.5.1-r3.4
(
  cd "$ROOT/aspnetboilerplate" &&
  allocations="$(git rev-parse --path-format=absolute --git-common-dir)/du-r3-leaf-candidate-versions" &&
  test ! -e "$allocations/$version" &&
  PATH="$SDK_DIR:$PATH" bash nupkg/pack-r3-module-zero-candidates.sh \
    --version "$version" --r2-feed "$R2/feed" \
    --output "$ROOT/.git/r3-module-zero/local-candidates/$version"
)
```

生成后的新批按自己的生产清单、补丁和实包核验。登记清单及独立来源证明摘要、实际框架检出、固定模板和严格运行时，再用该批的原件执行消费。当前登记保留 `r3.3` 的原始实物标识。

## 消费闭包与运行

[独立项目](../../validation/module-zero/ModuleZeroProbe.csproj) 的唯一直接框架引用为 `Du.Abp.ZeroCore.EntityFrameworkCore [10.5.1-r3.3]`。另外直接引用 EF Core SQLite `9.0.18` 和将 ASP.NET Core Identity 服务装配桥接到 Windsor 的 `Castle.Windsor.MsDependencyInjection 4.1.0`。冻结批次的框架包图有六个包、六条边。

| 依赖包 | 直接声明的框架边 |
| --- | --- |
| `Du.Abp.ZeroCore.EntityFrameworkCore` | `Du.Abp.ZeroCore [10.5.1-r3.3]`、`Du.Abp.EntityFrameworkCore [10.5.1-r2.1]` |
| `Du.Abp.ZeroCore` | `Du.Abp.Zero.Common [10.5.1-r3.3]` |
| `Du.Abp.Zero.Common` | `Du.Abp [10.5.1-r2.1]` |
| `Du.Abp.EntityFrameworkCore` | `Du.Abp.EntityFramework.Common 10.5.1-r2.1` |
| `Du.Abp.EntityFramework.Common` | `Du.Abp 10.5.1-r2.1` |
| `Du.Abp` | 无 |

两个 R2 传递声明为普通最低版本，受控源解析到固定的三份 `10.5.1-r2.1` 原包。实际还原共 49 个应用包，另记录 SDK 获取的两个 `9.0.23` 参考包。SDK 对可由共享框架提供的资产和编译期分析器分别处理，`output.json` 保存 `.deps.json` 省略的包、选中的参考路径和实际复制项。六份框架 DLL 的 `net9.0` 归档资产、缓存、编译引用、Release 输出和实际加载位置均可逐项核对。实际 Provider 为 `Microsoft.EntityFrameworkCore.Sqlite`，EF Core、Relational、SQLite Provider 和 Microsoft.Data.Sqlite 均加载 `9.0.18`。SQLitePCLRaw `2.1.10` 的 `runtimes/osx-arm64/native/libe_sqlite3.dylib` 与进程实际加载路径和字节一致，SQLite 连接报告 `3.46.1`。

验证程序在同一新 SQLite 文件中建立两个不同且启用的租户。通过 Windsor 解析实际角色存储，在两组独立事务性 ABP 工作单元各写一个角色。EF Core 事务提交事件、仓储 DbContext ID 及 ABP 完成事件相互对应。两个写入作用域释放后，每个租户使用新的作用域、工作单元和 DbContext，启用 `MayHaveTenant`，只传角色 ID 进行正反查询。两次命中均核对 ID、名称、租户归属，两次跨租户查询均明确返回 `null`。进程正常退出后，验证器从该 SQLite 文件只读核对物理租户和角色记录。

## 验收记录

生产时的框架基提交与生产清单所记录的主仓框架 gitlink 均为 `b329282a6ab4429b0cc724a2649e7a446e2c1a6a`，基树为 `6920f9d927c6a4a787d93d6e1052368a9a5e50d4`。应用 R3 自身补丁得到候选源树 `68a09980ff8fb1f8225483dfe200124eb051ef49`。R2 从其自身的 `d497cba3d3feec093168697e81adb64ea5544087` 重放到 `fb0abb6be5cb69b0e5ff395f4b010cf28511f9c8`，后者也是普通对照提交 `457be917b46c4fb6237831baac5abb848ffe1c4b` 的树。`candidate.json` 登记各批生产来源、三个 R3 主包、三个符号包和三个 R2 原包身份。`inputs-after.json` 回读整批实物及生产证据，核对两轮工作文件独立与实物字节一致。

下表路径相对验证机主仓下的 `.git/r3-module-zero/package-2/`。每份 `report.json` 保存命令、工作目录、阶段退出码、实际 SDK 和运行时及消费进程状态。

| 验收 | 实际运行时和结果 | 原始报告 | SHA-256 |
| --- | --- | --- | --- |
| 初验 | 两项 `9.0.23`，退出 0 | `accepted-initial/r3-module-zero-69k0yf_q/report.json` | `e85317c59dc6fe43dc4321814f0329065a64db66627e12229c7ef21d8e8c0829` |
| 同批严格复现 | 两项 `9.0.23`，退出 0 | `accepted-repeat/r3-module-zero-19up700w/report.json` | `17a377d045423d37bb80d4d3e247692aa7505678c5c049e902f7f6837f59a567` |
| 系统工具普通消费 | 两项 `9.0.10`，退出 0 | `ordinary/r3-module-zero-p44ljaiu/report.json` | `43435ce25ffb15818e99248b0940150e29cb33db8706454eea28e533e938238f` |
| 系统工具严格模式 | 两项 `9.0.10`，消费进程退出 0，整体严格对照退出 1 | `alternate-strict/r3-module-zero-80us0in6/report.json` | `f45406eadf554ff56fa97b6209ec223ca622a0b47990f4a85a71793e62f1db78` |

每轮目录保留 `consumer/obj/project.assets.json`、Release `.deps.json`、`build.binlog`、编译与运行复制项、`probe/roles.sqlite`、`probe/probe.json` 及 `probe/process.log`。`roles-verified.json` 和 `runtime-verified.json` 分别记录物理读回及程序集、共享运行时、SQLite 资产的校验结果。

定向诊断从已通过的运行与独立副本构造。实际移除受控源的 `Du.Abp.Zero.Common` 后，NuGet 退出 1 并报告 `NU1101`。对同版本 R2 和 R3 改字节副本分别执行真实入口，两例都在冻结包摘要阶段退出 1。错误依赖范围、重复资产归属、事务或完成事件缺失、重用 DbContext、缺少本租户读回及跨租户 `null` 异常均通过定向证据夹具获得非零诊断。定向入口及报告摘要见 `diagnostics-final/`。 [诊断代码](../../eng/tests/verify_r3_module_zero.py)

```sh
RUN="$PWD/.git/r3-module-zero/package-2/accepted-initial/r3-module-zero-69k0yf_q"
python3 -B eng/tests/verify_r3_module_zero.py "$RUN" "$PWD/.git/r3-module-zero/local-diagnostics"
```

## 普通源码与模板对照

普通源码沿用三个原项目的 `net9.0` Release 构建、包 ID、项目引用、依赖边、自动打包和既有工具。第一包五个具名角色 SQLite 回归各有一个通过、零失败、零跳过，原始命令和 TRX 在 `.git/r3-module-zero/package-1/ordinary-test/`。固定普通、变更后普通与候选的程序集名称、版本、公开及受保护 API 和资源名称均一致。`Abp.Zero.Common` 的 15 个和 `Abp.ZeroCore` 的 16 个嵌入本地化 XML 逐项同摘要，证据在同级 `comparison/`。

固定模板 `2e9536872673a7ff1986a19e798c51684d16afe5` 的原版 Web.Host 图中，三个 Module Zero 包均解析到 `10.2.0`。Web.Core 直接声明 `Abp.ZeroCore`，Core 直接声明 `Abp.ZeroCore.EntityFrameworkCore`。计入本轮三个候选和上一批 SignalR、Log4Net 后，原版基线登记的六个候选缺口中尚余 `Abp.AutoMapper`。本轮覆盖独立 macOS ARM64、`net9.0`、SQLite 消费及第一包普通源码对照。完整模板集成、真实登录、SQL Server、Angular、其他平台或目标、公开发包和部署留待相应阶段。 [模板基线](r3-web-host-baseline.md) · [前批实包验收](r3-signalr-log4net-candidates.md) · [AutoMapper 兼容维护](../compatibility/automapper.md)

## Git 交付

2026-11-25，框架 `dev` 提交 `819c64cf527b6918a5eafbf42550c93400f1fb75` 已推送至 `.gitmodules` 登记的框架 fork。其父提交为 `b329282a6ab4429b0cc724a2649e7a446e2c1a6a`，提交树 `68a09980ff8fb1f8225483dfe200124eb051ef49` 与本机验收所用的生产树一致，完整提交补丁与冻结批次的 `source.patch` 逐字节相同。冻结候选保留生产时的源码证明及归档摘要。 [框架交付提交](https://github.com/dusdong/aspnetboilerplate/commit/819c64cf527b6918a5eafbf42550c93400f1fb75)

主仓本次交付将框架 gitlink 固定到 `819c64cf527b6918a5eafbf42550c93400f1fb75`，并同步稳定规范、归档变更。检出本版后可用 `git ls-tree HEAD -- aspnetboilerplate module-zero-core-template` 核对这两个输入。框架应为该提交，模板仍为 `2e9536872673a7ff1986a19e798c51684d16afe5`。以上验收记录对应本机独立消费者，主仓 GitHub Actions 的 R0 基线复验另按其工作流记录。 [稳定消费规范](../../openspec/specs/module-zero-package-consumption/spec.md) · [OpenSpec 归档](../../openspec/changes/archive/2026-11-25-add-r3-module-zero-candidates/)
