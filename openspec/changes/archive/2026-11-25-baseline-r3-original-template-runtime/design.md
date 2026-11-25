# R3 原版模板运行对照设计

## Context

主仓基点为 `ecb1c88aaa02aba61a47cfed0fb3db8362cb31ac`，模板固定在 `2e9536872673a7ff1986a19e798c51684d16afe5`。此前 `r3-web-host` 已核对五个项目的还原图、11 个 `10.2.0` ABP 包的运行资产及 SQL Server Provider `9.0.5`。该 profile 的完成点是构建产物。新 profile 继续验证同一 Host 的运行结果。既有维护报告中“候选构建后进入 SQL Server 验收”的顺序适用于维护包 Host。本轮运行的是原版 Host。[原版构建基线](../../../../docs/maintenance/r3-web-host-baseline.md) · [四步迁移顺序](../../../../docs/maintenance/fork-roadmap.md#r3验证升级路径和实际消费者)

## Goals / Non-Goals

第一轮输出原版用户可观察的结果，第二轮证明另一个库可以恢复到同一业务起点。两轮都运行固定模板、原版包与同一前端构建。备份供后续同目标换包复用。整套升级后的回退能力要在实际换包和升级后再验证。首次的主机、浏览器和数据库组合按实测登记。

## Decisions

1. **沿用构建基线，增加单独的运行入口。** 拟在 `eng/verify.py` 增加 `r3-template-runtime`。复用 `r3-web-host` 的固定源码、隔离还原和产物核对逻辑，保留原 profile 的行为和历史六缺口记录。优先直接使用本轮通过核对的 Host 输出，并登记实际启动路径、摘要和进程。Migrator 是额外的 `net9.0` 入口，从同一提交独立还原并构建，记录其项目、包和输出。首选沿用 macOS ARM64 与 SDK `10.0.404`，另记实际加载的 .NET 9 共享运行时。[构建验证器](../../../../eng/r3_web_host.py)

   固定模板在 `Production` 启动时会拒绝内置加密口令及默认 JWT 签名密钥。准备数据和两轮验收都显式设置 `ASPNETCORE_ENVIRONMENT=Development`，直接启动同一 Release Host。在启动记录中核对 Host 实际报告的环境名，交给下一轮换包时沿用该环境。Angular 继续使用 production 构建。[模板启动配置](../../../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.Web.Host/Properties/launchSettings.json) · [Host 初始化检查](../../../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.Web.Core/AbpProjectNameWebCoreModule.cs)

2. **按锁文件构建真正提供页面的客户端。** 在隔离模板目录用 Yarn Classic 执行 `yarn install --frozen-lockfile`，使用项目内 CLI 执行 `yarn ng build --configuration production`。锁文件将 Angular Core 和 CLI 解析为 `19.2.1`，适配器和资源包分别为 `12.1.0`、`6.1.0`。记录实际 Node、Yarn、安装结果及构建摘要。以支持 SPA 路由回退的本地服务提供这份输出。在隔离副本中配置实际加载的 `assets/appconfig.production.json`，对齐 `remoteServiceBaseUrl`、`appBaseUrl` 和 Host 的 `App:CorsOrigins`。记录运行配置差异，不修改模板 gitlink。[Angular 构建入口](../../../../module-zero-core-template/angular/angular.json) · [客户端初始化](../../../../module-zero-core-template/angular/src/app-initializer.ts)
3. **SQL Server 建立一个可核对的登录前起点。** 执行时选用允许为本轮创建数据库、备份并恢复到新库的测试实例，核对服务端身份、版本、目标库名和备份位置。为源库与恢复库分配本次运行独占的名称。预检不能确定目标或权限不足时，在写入前报告缺项。让模板 Migrator 与待启动的 Host 使用同一 `ConnectionStrings:Default`，运行 `Migrator -q`，核对退出码、实际迁移历史及默认租户种子。首次采用共享库租户，不使用租户自有连接串。经模板正常用户管理入口创建合成用户，以其用户名为搜索关键词。按模板的包含匹配规则，核对该词在本租户可见用户的用户名、姓名和邮箱中仅命中目标用户。另以具备 `Pages.Users` 的租户账号登录。用数据库独立读回租户 ID、登录用户 ID、目标用户 ID 与用户名。准备数据可使用独立会话。结束准备进程后备份，再开始两轮计入验收的登录。[迁移入口](../../../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.Migrator/Program.cs) · [模板种子](../../../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.EntityFrameworkCore/EntityFrameworkCore/Seed/SeedHelper.cs)
4. **一次浏览器操作绑定三层结果。** 用全新浏览器上下文、真实模板登录页及租户选择入口发起 `/api/TokenAuth/Authenticate`，读回 `Session/GetCurrentLoginInformations` 返回的身份。进入受 `Pages.Users` 保护的用户列表，待初次加载完成后提交搜索。捕获此次提交触发且 `Keyword` 等于合成用户名的 `User/GetAll` 请求，核对对应响应的 `result.totalCount` 为 1、`result.items` 只有一项，且其 `(id, userName)` 与数据库记录一致。渲染后，结果表格应只有一条数据行，其用户名单元格文本与预期用户名精确相等。验收保存路径、状态和需要比对的业务字段。认证材料不进入命令行、日志或原始网络转储。[用户路由](../../../../module-zero-core-template/angular/src/app/app-routing.module.ts) · [用户列表](../../../../module-zero-core-template/angular/src/app/users/users.component.ts) · [查询过滤条件](../../../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.Application/Users/UserAppService.cs)
5. **实际恢复后重跑。** 首轮使用源库。第二轮把登录前的同一备份还原到另一新库，比较迁移历史与业务数据，再用同一 Host 构建重新启动、切换数据库，使用新的浏览器上下文。恢复轮提交登录前，分别直连两库，在 `AbpUserLoginAttempts` 中按预期租户 ID、登录账号 ID 和成功结果计数。该专用账号在此期间只由本轮浏览器登录一次。登录请求完成后用相同条件复查，恢复库计数须增加 1，源库计数须保持原值。每个库都与自身登录前的计数比较，以排除准备会话和首轮登录的影响。[登录记录模型](../../../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.EntityFrameworkCore/Migrations/AbpProjectNameDbContextModelSnapshot.cs)

   报告登记两库标识及各自的登录前后计数、备份摘要、两轮运行输入及预期值。数据库原件和备份保存在受控测试位置，主仓记录标识和恢复步骤。SQL Server 的备份路径按服务端可访问位置解析。

## Risks / Trade-offs

- 数据库实例、备份位置及可用权限是实施时的环境输入。缺少其中一项，仍可完成构建和前端输入核对，SQL Server 与浏览器阶段不能记为通过。
- 模板 Migrator 可处理多个租户连接，Host 启动也会执行种子逻辑。启动前核对本轮共享库的身份。两库恢复后的用户 ID 和用户名相同，恢复轮须用成功登录记录的增量识别 Host 误连源库。
- 登录会产生会话与审计数据。预期相等的字段限定为迁移历史和指定业务记录，比较不依赖时间戳、请求 ID 或令牌字节。

## Migration Plan

确认原版两轮通过后，向同目标换包变更交接备份、数据库期望值、模板与客户端摘要、比较字段和复跑命令。失败时保留已取得的脱敏证据，释放本轮启动的进程和端口，使用新运行目录重试。清理仅涉及本轮明确创建的资源，并保留后续对照需要的数据恢复点。
