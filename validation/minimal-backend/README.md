# 最小后端候选包消费者

此项目用 Kestrel、ABP 模块与仓储、SQLite 验证同一批 `Du.Abp*` 候选包。项目仅直接引用 `Du.Abp.AspNetCore`、`Du.Abp.EntityFrameworkCore` 及对应目标的 `Microsoft.EntityFrameworkCore.Sqlite`。两个目标各在新的项目副本、空 NuGet 缓存和独立进程中运行。

在主仓根目录执行。将变量设为本机的候选、R1 原始证据和工件目录。其中候选目录含 `feed/`、`symbols/`、`manifest.json` 和 `source.patch`。R1 原始证据目录为 `final-v2`。

```sh
python3 eng/verify.py --profile r2 \
  --dotnet "$R2_DOTNET" \
  --candidate-feed "$R2_CANDIDATE/feed" \
  --candidate-manifest "$R2_CANDIDATE/manifest.json" \
  --r1-evidence "$R1_EVIDENCE" \
  --evidence-root "$R2_EVIDENCE"
```

验收使用 macOS ARM64 SDK `10.0.404`。同一个 `dotnet` 须能找到 `Microsoft.NETCore.App` 和 `Microsoft.AspNetCore.App` 的 `9.0.23` 与 `10.0.15`。每轮生成一个新的 `r2-*` 目录，保留命令、NuGet 配置、还原图、Release 输出、SQLite 文件、HTTP 响应和负例报告。两目标及全部必需检查通过时返回 0。

启动时由 `UseAbp` 初始化模块。通用 Host 使用 Windsor 服务容器工厂和 `AddAbpWithoutCreatingServiceProvider`。验证器从宿主日志取得回环动态端口，先向 `POST /records` 写入固定记录，再从 `GET /records` 读取。两次请求使用不同的 DI 作用域、工作单元与仓储 DbContext。验收检查写入时仓储使用的 SQLite 事务、同一个 ABP 工作单元的 `Completed` 事件，以及新请求中的唯一读回。验证器收集已加载的五个框架 DLL 和 dyld 实际选中的原生 SQLite 库，再关闭宿主。

本机已验组合、精确输入和原始证据位置见 [R2 核心候选包消费验收](../../docs/maintenance/r2-core-package-consumption.md)。
