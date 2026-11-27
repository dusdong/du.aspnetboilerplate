# R5 固定模板用户角色更新验收计划

2026-11-27 制定，主仓基线为 `aa593eb2732ed1a898eec0431a4a1b1e9497efd1`。本轮在公开 R4 `v10.5.1`、R5 `v10.5.2` 上分别运行同一固定模板，使用真实用户更新 API 对照直接分配角色的保留、替换和清空。三步预期来自源码，正式提交结果见[实测报告](r5-template-user-role-update.md)。[OpenSpec 归档任务](../../openspec/changes/archive/2026-11-27-validate-r5-template-user-role-update/tasks.md)

## 上一轮复核

- GitHub `main` 已交付基线提交，其 `verify-r0` 通过。19 个候选文件与提交字节一致，本机登记的 77 处临时项已清。映射对照归档包含一条要求、五个场景和四项已完成任务，稳定规范严格校验 15/15、归档检查 24/24。[交付提交](https://github.com/dusdong/du.aspnetboilerplate/commit/aa593eb2732ed1a898eec0431a4a1b1e9497efd1) · [CI](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/45965173588) · [任务归档](../../openspec/changes/archive/2026-11-27-validate-r5-public-mapping-behavior/tasks.md)
- 离线回读原正式运行。两侧各还原 46 个包，版本差异限于三个映射包。三份映射 DLL 的所选归档成员、构建输出和该侧进程加载摘要逐一一致。已有用户映射、按键集合和 SQLite 投影各自通过，读取 29 列，物化 ID 为 `12、13、11`。[包身份](r5-public-mapping-behavior.md#实测输入与包身份) · [逐项结果](r5-public-mapping-behavior.md#逐项业务结果)
- 回读真实错误摘要、单侧换列和双侧换列三个反例，三次总入口均退出 1。本次复核重跑 16 项本地定向测试，全部通过。原正式运行与其证据按原报告留存。[反例、原始证据与公开复跑](r5-public-mapping-behavior.md#原始证据与失败判定)

独立映射调用验证了角色对象与创建时间的保留，固定模板历史回退验证了用户创建与查询。本轮补齐了应用服务在映射之后处理角色及提交的证据。同库回退、SQLite 投影和按键集合继续使用既有结果。[映射适用范围](r5-public-mapping-behavior.md#适用范围) · [公开回退独立验收](r5-automapper-template.md#独立消费者验收)

## 固定输入与种子

| 项目 | 验收固定值 |
| --- | --- |
| 模板 | 两侧均使用 `module-zero-core-template` 提交 `2e9536872673a7ff1986a19e798c51684d16afe5` 的 Web.Host 与 Migrator |
| 运行条件 | macOS ARM64，SDK `10.0.404`，目标 `net10.0`，实际 .NET 与 ASP.NET Core `10.0.15`，EF Core SQL Server `10.0.15`，SQL Server Developer `16.0.4236.2` |
| R4 的适配器、引擎和 Collection | `Du.Abp.AutoMapper 10.5.1`、`Du.AutoMapper 14.0.0`、`Du.AutoMapper.Collection 11.0.0` |
| R5 的适配器、引擎和 Collection | `Du.Abp.AutoMapper 10.5.2`、`Du.AutoMapper 14.0.1`、`Du.AutoMapper.Collection 11.0.1`。其余十个维护包沿用 R4，包含 `Du.Abp.ZeroCore 10.5.1` |
| 隔离 | 各侧独立空缓存、Release 目录、Migrator、环回 Host 和新建的专用 SQL Server 库，各侧记录实际进程、实例、库名、数据库 ID、GUID 和迁移清单 |

复用消费者指南的模板准备、公开校验附件、nuget.org 空缓存还原和 Release 构建。按历史同一入口核验 Web.Host 各 13 个、Migrator 各 10 个维护包的签后归档和所选资产，逐入口核对完整包图的差异仅涉及三包及已登记的四条精确依赖约束。核对本轮 Host 实际加载的适配器、唯一映射引擎、运行时及 Provider，三份映射 DLL 都对账包内资产与输出，Collection 的加载状态按实记录。[公开消费者准备步骤](r5-consumer-package-rollback.md#演练脚本) · [已登记的依赖和资产差异](r5-public-patch-review.md#解析版本依赖边和所选资产)

各侧新库完成同一套迁移后，认证目标租户 `Default` 的种子管理员，核对会话身份及实际数据库。管理员只作操作人。通过 `POST /api/services/app/Role/Create` 创建角色 A、B。A 提交 `name: "du-role-a"`、`displayName: "Role Check A"`，B 提交 `name: "du-role-b"`、`displayName: "Role Check B"`，两者均提交 `grantedPermissions: []`。核对其租户、名称、非静态和非默认身份及无授权记录。

再通过 `POST /api/services/app/User/Create` 创建普通用户，指定 `roleNames: ["du-role-a"]`，并沿用消费者指南的测试密码生成和脱敏方式。每侧在进程中随机生成临时密码，通过必填的 `password` 字段提交，留存的请求、回执和日志均脱敏。通过创建回执、同租户独立 GET 和 SQL 确认各侧目标 ID、等价普通字段、唯一角色 A 以及创建时间原值。

## 复跑公开模板准备

在主仓根目录使用 Git、curl、tar、Python 3 和上表的 ARM64 .NET 工具链。准备入口下载固定模板归档并核对 SHA-256，使用消费者指南中已验脚本的准备函数。安装了多套宿主时，可通过 `--dotnet /绝对路径/dotnet` 指定宿主。输出目录须尚不存在。

```sh
WORK="$(mktemp -d "$(git rev-parse --absolute-git-dir)/role-prepare.XXXXXX")"
curl -fL https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json \
  -o "$WORK/R4-PACKAGE-CHECKSUMS.json"
curl -fL https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.2/R5-PACKAGE-CHECKSUMS.json \
  -o "$WORK/R5-PACKAGE-CHECKSUMS.json"
python3 -B eng/r5_template_role_prepare.py prepare --output "$WORK/prepared" \
  --r4-checksums "$WORK/R4-PACKAGE-CHECKSUMS.json" --r5-checksums "$WORK/R5-PACKAGE-CHECKSUMS.json"
shasum -a 256 "$WORK/prepared/report.json"
```

准备命令退出 0 后，独立登记 `report.json` 的 SHA-256。交接时用该已登记值执行下列命令。它核对报告、图与封存文件，全部通过才输出 `r4`、`r5` 各自的 `Web.Host` 和 `Migrator` 启动参数、工作目录、入口摘要和证据清单。Python 调用方可复用 `verify_prepared(root, report_sha256)`。固定输出路径为 `output/{R4,R5}/{Web.Host,Migrator}`。下一阶段启动时为 `CONSUMER_ROLLBACK_APP_LOG` 指定各进程在封存目录外的日志文件，连接、端口及运行身份由业务验收入口设置。

```sh
python3 -B eng/r5_template_role_prepare.py verify --prepared "$WORK/prepared" \
  --report-sha256 "$REPORT_SHA256"
```

`report.json` 登记阶段、输入与四个入口证据。`source-inventory.json` 保留两份准备源码的逐文件摘要，`{R4,R5}-{Web.Host,Migrator}-assets.json` 和同名前缀的 `-graph.json` 分别是原始还原图和标准化对照图。`-packages.json` 记录维护包签后归档及选中的映射 DLL，`-output.json` 记录 Release 文件、程序集来源和 SQL Server Provider 链。`graph-comparison.json` 记录逐入口允许的变化。命令日志首行登记参数、工作目录和退出码。

附件 SHA-256 错误时，`prepare` 在工具链检查、还原和构建前返回 1，报告保留预期与实际摘要。交接摘要或封存文件错误时，`verify` 返回 1 并报告文件与摘要差异。两个命令只执行准备和核验，进程实际加载、迁移及数据库写入在后续业务验收取证。使用附件副本或输出副本复验失败路径可保留合格原件。

## 三步真实更新

各侧对自身创建回执中的同一用户 ID 请求 `PUT /api/services/app/User/Update`。初态用户名设为 `durolecheck`，名、姓分别为 `Seed`、`User`，启用状态为 `true`。初态及每步的邮箱均为当步的用户名加 `@example.invalid`。两侧使用相同的阶段输入，按表依次验证。每步均提交 `creationTime: "2000-02-03T04:05:06"`，并在首步前确认该值有别于两侧原值。

| 顺序 | `userName`、`name`、`surname`、`isActive` | 请求 JSON 的 `roleNames` | 预期直接分配的角色 |
| --- | --- | --- | --- |
| 1 | `durolekeep`、`Keep`、`First`、`false` | `null`，请求体含该键 | 保留且只有 A |
| 2 | `durolereplace`、`Replace`、`Second`、`true` | `["du-role-b"]` | 只有 B，A 的关联已移除 |
| 3 | `duroleclear`、`Clear`、`Third`、`false` | `[]` | 角色数组为空，SQL 零关联行 |

模板更新先映射普通字段，Profile 忽略实体上的 `Roles` 和 `CreationTime`。更新方法在 `RoleNames` 非 null 时调用框架的 `SetRolesAsync`，后者移除输入未列出的角色并添加缺少的角色。生成的 Angular 代理仅在属性为数组时向 JSON 写入该键，验收使用原始 HTTP JSON 保留显式 `null`。[模板更新](../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.Application/Users/UserAppService.cs) · [模板映射](../../module-zero-core-template/aspnet-core/src/AbpCompanyName.AbpProjectName.Application/Users/Dto/UserMapProfile.cs) · [框架角色更新](../../aspnetboilerplate/src/Abp.ZeroCore/Authorization/Users/AbpUserManager.cs) · [生成代理](../../module-zero-core-template/angular/src/shared/service-proxies/service-proxies.ts)

初态 GET、每步 PUT 和独立 GET 分别使用唯一请求标识。逐请求记录实际 Host PID、目标用户 ID，以及处理该用户的业务命令在其连接上实测的 SQL Server 实例和库名。按实测实例与库名核对当前数据库 ID、GUID 与该侧预检记录一致。业务连接缺证或库身份不符时，停止该侧后续写入。每步还须保留以下三份证据。

1. **请求及更新回执**须保留实际 JSON 形状、HTTP 200、ABP 成功回执及 DTO。回执须对应原 ID，普通字段取该步输入，创建时间为该侧原值。
2. **独立 API 读回**须在更新返回后，用同一已核验的租户会话发出新的 `GET /api/services/app/User/Get?Id=<目标 ID>`，核对成功状态和同一组 DTO 字段。两个 DTO 的 `roleNames` 均须为数组。请求使用角色的 `Name`，响应则按同库角色的 `NormalizedName` 精确对账。
3. **独立 SQL 读回**须使用只读 SELECT 核对实际库身份，按租户和用户 ID 从 `dbo.AbpUsers` 读取唯一用户及普通字段、原创建时间，从 `dbo.AbpUserRoles` 读取直接分配给目标用户的全部角色关联并左连接 `dbo.AbpRoles` 核对租户、角色 ID、名称和删除状态。额外、重复、错租户以及指向缺失或已删除角色的关联都要显示并判失败。API DTO 的租户由会话和 SQL 用户行核实。保留原始时间值，按序列化语义和 SQL `datetime2` 精度核对，避免把无偏移值当成 UTC 或截掉小数秒。跨库对照对应的业务身份与创建时间保留这一不变量，各库的自增 ID 和创建时间初值按各自记录核对。

## 验收与范围

两侧包身份、环境、进程、数据库与初态均合格，且各自三步分别符合预期，才登记固定组合通过。保存可复跑命令、两侧还原与加载证据、逐阶段请求和读回、总报告及实际退出码。凭据、认证头和令牌仅在进程内使用。

| 结果 | 判定 |
| --- | --- |
| 输入不可比 | 包、运行时、实际数据库或等价初态偏离时，记录预期与实测并停止该侧后续写入，总入口返回非零 |
| 单侧失败 | 记录具体阶段、预期和偏差，保留已取得回执与可安全读取的提交证据，依赖该阶段的后续步骤标记未执行。另一侧独立完成，总入口返回非零 |
| 两侧失败 | 分别记录各侧偏差。同一错误也须分别判失败，总入口返回非零 |

PUT 已发出但因超时、断连或解析错误缺少可用回执时，该步失败。保留脱敏请求、错误和可用响应，停止该侧写入，不重发 PUT。若可核实目标库身份，用已知用户 ID 另发 GET 并执行只读 SQL，分别记录值或无法取得的原因。即使读回符合预期，仍报告回执缺失及后续步骤未执行，另一侧继续，总入口返回非零。定向回归分别换入另一侧的业务连接记录、屏蔽首步成功 PUT 的回执，核对停止写入和报告判定。

本轮按模板 `user.Roles` 和 SQL `dbo.AbpUserRoles` 验收直接分配的角色，同时验证普通字段更新。组织单元继承角色、最终权限、Angular、其他平台与 Provider、生产环境由各自验收覆盖。出现产品差异时保留证据，按另行立项决定是否修复。[提案](../../openspec/changes/archive/2026-11-27-validate-r5-template-user-role-update/proposal.md) · [技术设计](../../openspec/changes/archive/2026-11-27-validate-r5-template-user-role-update/design.md) · [增量规范](../../openspec/changes/archive/2026-11-27-validate-r5-template-user-role-update/specs/automapper-package-consumption/spec.md)
