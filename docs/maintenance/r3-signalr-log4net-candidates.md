# R3 SignalR 与 Log4Net 候选消费

本轮通过独立 `net9.0` Kestrel 回环宿主验收两个维护候选。原版参照为模板 `2e9536872673a7ff1986a19e798c51684d16afe5` 的 Web.Host 构建记录，其中框架包解析到 `10.2.0`，Log4Net 链解析到 `log4net 3.1.0`。维护源码声明 `log4net 3.3.2`。报告分别登记 nuspec 范围、还原边、实际选中版本、资产及运行加载位置。[原版 Host 对照](r3-web-host-baseline.md) · [R2 已验实物](r2-core-package-consumption.md) · [稳定消费规范](../../openspec/specs/web-host-integration-package-consumption/spec.md) · [OpenSpec 归档](../../openspec/changes/archive/2026-11-25-add-r3-signalr-log4net-candidates/)

## 从源码生产新候选

在主仓根目录设置路径，再从框架子仓运行打包入口。为每一批选择未分配的 `10.5.1-r3.N` 版本和新目录。完整生产检查、来源证明及失败诊断见框架说明。[候选打包说明](../../aspnetboilerplate/nupkg/README.r3.md)

```sh
R2_FEED="$PWD/.git/r2-core-consumption/package-1/10.5.1-r2.1/feed"
DOTNET_DIR="$PWD/.git/r2-core-consumption/package-2/toolchain/overlay"
NEW_VERSION=10.5.1-r3.2
NEW_BATCH="$PWD/.git/r3-signalr-log4net/production/$NEW_VERSION"
(
  cd aspnetboilerplate
  PATH="$DOTNET_DIR:$PATH" bash nupkg/pack-r3-leaf-candidates.sh \
    --version "$NEW_VERSION" --r2-feed "$R2_FEED" --output "$NEW_BATCH"
)
```

生产者从登记的 R2 原归档编译两个候选。保留输出目录中的 `manifest.json`、`feed/`、`symbols/`、`source.patch`、源码来源证明和生产日志。批次变更需更新 `eng/r3_leaf_reference.json` 的交验清单及源码来源证明摘要，并按变更影响重做普通模式对照和消费验收。

## 用已锁定实物复验消费

在主仓根目录运行。首次验收的私有 `dotnet` 使用 ARM64 SDK `10.0.404`。用 `--strict-runtime-baseline` 复现首次验收的运行时组合时，要求宿主的 `Microsoft.NETCore.App` 和 `Microsoft.AspNetCore.App` 实际加载版本均为 `9.0.23`。证据父目录下每次生成一个新运行目录，内部缓存初始为空。读取生产实物时保留原始字节。

```sh
R2_FEED="$PWD/.git/r2-core-consumption/package-1/10.5.1-r2.1/feed"
DOTNET="$PWD/.git/r2-core-consumption/package-2/toolchain/overlay/dotnet"
BATCH="$PWD/.git/r3-signalr-log4net/package-1/10.5.1-r3.1"
EVIDENCE="$PWD/.git/r3-signalr-log4net/package-2/runs"

python3 -B eng/verify.py --profile r3-signalr-log4net --dotnet "$DOTNET" --strict-runtime-baseline \
  --candidate-feed "$BATCH/feed" --candidate-manifest "$BATCH/manifest.json" \
  --candidate-symbols "$BATCH/symbols" --r2-feed "$R2_FEED" --evidence-root "$EVIDENCE"
```

日常消费复验可选用另一套显式的 ARM64 `dotnet`，沿用上述命令并去掉 `--strict-runtime-baseline`。SDK 仍使用 `10.0.404`。报告分别核对并记录两个实际加载的 `9.0.x` 运行时的路径、来源和版本。若要重现首次验收的运行时组合，使用上述带严格参数的命令。

报告记录两个本地映射源、第三方来源、包图、原始资产、Release 输出、运行加载位置、客户端负载、日志文件、停机和退出码。R2 的三个原包及本轮两个候选解析成唯一的五包闭包。`Microsoft.AspNetCore.SignalR.Client 9.0.18` 由独立验证项目使用。可在失败报告中按首个失败阶段查看命令、日志和后续阶段状态。

生产清单保留生产所用的 Log4Net 包版本与资产。消费验证读取实际解析版本，用 NuGet 范围规则核对候选包的依赖边，再对照包内元数据、实际编译引用、运行复制项和加载程序集。出现包版本或资产变化时，报告保留原生产值、消费选择及验收所覆盖的组合。

两个候选使固定模板的维护包缺口从六个减为四个。本轮验收范围限于本机 macOS ARM64、独立 `net9.0` 消费者、内存测试身份和回环连接。完整模板、真实登录、数据库、Angular、其他平台和目标、公开发包、CI 及部署留待对应阶段。

## 本机验收记录

2026-11-25，macOS 27.2.1 ARM64（`26B131`）从独立空缓存还原并构建 `10.5.1-r3.1`。验收命令、NuGet 还原、Release 构建和宿主均退出 0。宿主实际使用 `Microsoft.NETCore.App 9.0.23` 和 `Microsoft.AspNetCore.App 9.0.23`。还原图共有 64 个应用包。五个框架包、四条框架依赖边、实际选中资产与 Release 输出均可从同轮证据核对。

| 核对项 | 实测结果 |
| --- | --- |
| SignalR | 实际回环连接通过 WebSocket，在线记录与测试身份一致。`Register` 调用通过，从宿主通知配置选取的 `SignalRRealTimeNotifier` 送达 `getNotification`。客户端核对用户、通知 ID、名称和标识。断开后同一连接 ID 从在线记录移除 |
| Castle 日志 | 按预期完整读回 `INFO\|Du.Abp.R3.Castle\|R3 Castle <当轮标识>`。五个框架 DLL 与 `log4net.dll` 在还原、Release 输出及运行中路径、身份与 SHA-256 一致 |
| Log4Net 对照 | 原版框架包 `10.2.0` 解析 `log4net 3.1.0`。维护项目声明 `3.3.2`，现有 nuspec 范围为 `[3.3.2,)`，实际解析 `3.3.2`，编译和运行选中 `lib/netstandard2.0/log4net.dll`，进程加载程序集版本为 `3.3.2.0` |
| 停机 | 成功与实际通知配置缺失的宿主均报告客户端和 Kestrel 停止。超时路径发送 `SIGTERM` 并等候宿主退出，保留退出状态和停机报告 |

生产实物的清单 SHA-256 为 `579443f73fecb9ebce47fb3efe7645cef6970b24ac603b130fb4d64a2e97dea5`，框架候选树为 `6920f9d927c6a4a787d93d6e1052368a9a5e50d4`。两份 `.nupkg`、两份 `.snupkg`、独立源码证明、编译引用和实际生产资产日志随生产批次保存在验证机的 `.git/r3-signalr-log4net/package-1/10.5.1-r3.1/`。初版正式消费报告位于 `.git/r3-signalr-log4net/package-2/runs/r3-signalr-log4net-uxveekzp/report.json`，SHA-256 为 `9fe04771fe03ef4b2f3b5811d7f50f99ec2a66a992fef331a42d359fde667c8d`。同目录的 `candidate.json`、`assets-inventory.json`、`runtime-selection.json`、`output.json`、`runtime.json`、`notification.json`、`logging.json` 和 `host/` 保留各阶段证据。第一次通过的同批运行保存在 `runs/r3-signalr-log4net-9vt12ecx/`。

对已通过的运行执行以下命令可复验定向诊断。传入新的证据目录。缺包用例在受控源副本移走 `Du.Abp.Web.Common` 并执行真实还原，得到 `NU1101`。缺失通知配置和超时在独立回环宿主执行。另用独立包或证据副本检查摘要、范围、原版 ID、目标、重复资产、通知、断开、日志和加载诊断。原 R0、R2、R3 首包参数分派用夹具复验，R0 Python 自检另有 17 项通过。

```sh
REVISION="$PWD/.git/r3-signalr-log4net/package-2/revision-1"
RUN="$REVISION/strict-final/r3-signalr-log4net-_hkc8ai_"
NEW_DIAGNOSTICS="$REVISION/diagnostics-replay"
python3 -B eng/tests/verify_r3_leaf.py "$RUN" "$NEW_DIAGNOSTICS"
```

## 消费验证器复验记录

修订版核对候选包内的完整源码证明，并检查主包及符号包 nuspec 的仓库信息。已提交来源须与经过 Git 提交及树核对的 `commit` 一致，未提交来源使用补丁与树证明。来源夹具覆盖两种模式，以及遗漏和冲突的提交声明。

以下三次均使用原 `10.5.1-r3.1` 实物、独立缓存及 ARM64 SDK `10.0.404`。运行目录相对于验证机的 `.git/r3-signalr-log4net/package-2/revision-1/`。

| 入口 | 实际加载的两项共享框架 | 退出码 | 报告 |
| --- | --- | --- | --- |
| R2 私有 `dotnet` 严格复现 | 两项均为 `9.0.23` | 0 | `strict-final/r3-signalr-log4net-_hkc8ai_/report.json` |
| 系统 ARM64 `dotnet` 普通消费复验 | 两项均为 `9.0.10` | 0 | `alternate/r3-signalr-log4net-3q6gtvsm/report.json` |
| 系统 ARM64 `dotnet` 严格复现 | 两项均为 `9.0.10` | 1，运行时基线比对失败 | `alternate-strict/r3-signalr-log4net-9zs48bef/report.json` |

三个回环宿主均完成通知、日志及停机。修订版正式报告 SHA-256 为 `5b22b476130f560406cac9a4d5c0d3fcaad420100281c795b2661c7b26ae2819`。实际消费仍解析 `log4net 3.3.2`，原生产和消费的编译及运行资产路径一致。范围内不同版本和资产路径只在局部夹具模拟，未下载、构建或运行其他 Log4Net 包版本。

## Git 交付

2026-11-25，框架 `dev` 提交 `b329282a6ab4429b0cc724a2649e7a446e2c1a6a` 已推送至 `.gitmodules` 登记的框架 fork。其父提交为 `457be917b46c4fb6237831baac5abb848ffe1c4b`，提交树 `6920f9d927c6a4a787d93d6e1052368a9a5e50d4` 与生成候选的已验源码树一致。原包及符号保留生成时的未提交树证明与原始摘要。[框架交付提交](https://github.com/dusdong/aspnetboilerplate/commit/b329282a6ab4429b0cc724a2649e7a446e2c1a6a)

本次主仓交付的 gitlink 指向该框架提交。检出本版后可通过以下命令核对框架和模板的输入。第一行的框架 SHA 应为 `b329282a6ab4429b0cc724a2649e7a446e2c1a6a`，模板 SHA 仍为 `2e9536872673a7ff1986a19e798c51684d16afe5`。

```sh
git ls-tree HEAD -- aspnetboilerplate module-zero-core-template
```
