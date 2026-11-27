# 公开 R4 与 R5 的固定模板用户角色更新实测

2026-11-27，公开 R4 `v10.5.1` 与 R5 `v10.5.2` 在两份固定模板和两个独立空库中各跑通三步。两侧均保留角色 A、将 A 替换为 B，再清空直接关联。各步的更新回执、独立 GET 和 SQL 提交数据一致，普通字段按输入更新，创建时间保持各库原值。正式入口退出 0。[验收计划与字段预期](r5-template-user-role-update-plan.md#三步真实更新) · [OpenSpec 归档任务](../../openspec/changes/archive/2026-11-27-validate-r5-template-user-role-update/tasks.md)

## 固定输入与运行身份

- 固定模板 `2e9536872673a7ff1986a19e798c51684d16afe5`，macOS ARM64，SDK `10.0.404`，`net10.0`。两个 Web.Host 与两个 Migrator 的实际 .NET、ASP.NET Core 共享运行时及 EF Core SQL Server Provider 均为 `10.0.15`。
- 两侧以独立空 NuGet 缓存从 nuget.org 还原。封存的 Web.Host 各核对 13 个、Migrator 各核对 10 个签后维护包。对应入口的差异限于三份映射包、其资产和四条精确依赖边。[准备与封存步骤](r5-template-user-role-update-plan.md#复跑公开模板准备)
- R4 的 `Du.Abp.AutoMapper`、`Du.AutoMapper`、`Du.AutoMapper.Collection` 分别为 `10.5.1`、`14.0.0`、`11.0.0`，R5 分别为 `10.5.2`、`14.0.1`、`11.0.1`。三份 DLL 均核对签后包内成员与 Release 输出。各 Web.Host 实际在默认上下文从本侧 Release 输出加载适配器与唯一映射引擎，摘要一致。两侧 Collection 仅见于输出。两个 Migrator 都保留三份映射 DLL 输出，迁移期间均未加载它们。
- 专用 SQL Server `r5-role-10dc52743abd10f8` 实测为 Developer `16.0.4236.2`。每库记录 30 条实际迁移和 33 条迁移连接事件。各侧在目标 `Default` 租户内认证管理员，经 API 建立两枚无业务授权的普通角色和一名只有 A 的普通用户。

| 版本 | Migrator PID | Web.Host PID、环回端口 | 数据库名、ID、GUID | SQL 创建时间原值 |
| --- | --- | --- | --- | --- |
| R4 | `79087` | `79177`、`52181` | `r5_role_10dc52743abd10f8_r4`、`5`、`EA5142AE-ECD0-467B-B76C-5156820E9CCE` | `2026-11-27T17:50:32.2511410` |
| R5 | `79261` | `79338`、`52182` | `r5_role_10dc52743abd10f8_r5`、`6`、`02DE291C-FFD5-4703-AD33-A73CB57EF7F5` | `2026-11-27T17:50:39.8613340` |

## 提交与失败判定

两侧初态 GET、三次 PUT 和三次独立 GET 共 14 个唯一请求标识。每次都将实际 HTTP 方法、Host PID、目标用户 ID、完成的 EF 命令和其连接实测的实例、库名、ID、GUID 对账到该侧预检记录。PUT 同时观测目标用户的读取及写入。SQL 用独立连接检查该库中的用户、全部直接关联和两枚角色定义。

| 步骤 | 实发 `roleNames` | 两侧 PUT、GET 的实际角色数组 | 两侧 SQL 直接关联 |
| --- | --- | --- | --- |
| 保留 | `null`，显式包含该键 | `["DU-ROLE-A"]` | 各 1 行，角色 A |
| 替换 | `["du-role-b"]` | `["DU-ROLE-B"]` | 各 1 行，角色 B |
| 清空 | `[]` | `[]` | 各 0 行，角色定义仍在 |

创建回执带宿主 `+08:00` 偏移，按宿主本地时间与 SQL 表盘值对账。独立 GET 和 PUT 回执的创建时间无偏移，SQL 使用 `datetime2(7)` 的 ISO 文本。按七位小数精度核对各库原值，HTTP 省略的尾零等价。每步提交的 `creationTime` 为 `2000-02-03T04:05:06`，两侧均未写入该值。

准备入口实际拒绝错误的公开附件摘要，运行入口也实际拒绝错误的封存报告摘要，均退出 1。后者在启动进程与容器前停止。以下使用成功实测记录，经同一阶段判定及汇总逻辑回放，六次入口均退出 1。

| 回放输入 | 结果及写入边界 |
| --- | --- |
| 仅 R4 首步 GET 改为 B | 单侧失败。R4 停在首步，R5 跑完三步。 |
| 两侧首步 GET 同时改为 B | 两侧失败。两侧均停在首步。 |
| R4 首步换入 R5 的命令连接库身份 | 输入不可比。回执、GET、SQL 仍正确，R4 不重发或继续写入，R5 跑完三步。 |
| 仅将 R4 首步独立 SQL 的实测库身份换成 R5 | 输入不可比。PUT、GET 和两者业务连接均正确，保留原样的 SQL 用户与关联读回及失配库身份，R4 停止写入，R5 跑完三步。 |
| 屏蔽 R4 首步成功 PUT 回执 | 单侧失败。R4 的诊断 GET 与 SQL 均正确，首步仍失败，无重发或后续 PUT，R5 跑完三步。 |
| 同时屏蔽回执并换库 | 输入不可比。R4 两份诊断均因缺少可信库身份标记未执行，无重发或后续 PUT，R5 跑完三步。 |

环回传输回归另发真实 PUT。HTTP 200 回执包含可解析的 ABP JSON，声明的 `Content-Length` 比实发多 12 字节时，入口保留脱敏响应并报告回执不可用。由连接关闭界定的合法响应和完整分块响应均通过。

## 复跑与回读

按[公开准备步骤](r5-template-user-role-update-plan.md#复跑公开模板准备)获取两份公开附件、从空缓存构建、封存并独立记下报告 SHA-256。从仓库根目录使用 macOS ARM64 的 Python 环境（本次为 Python `3.14.7` 与 `pymssql 2.4.6`）、固定 .NET 安装和本机 Docker，预先准备下列固定 SQL Server 镜像。选两个空闲的环回 Web.Host 端口。`WORK/prepared` 与 `REPORT_SHA256` 取自公开准备步骤。

```sh
docker pull --platform linux/amd64 \
  mcr.microsoft.com/mssql/server@sha256:0ec7739e1c5ec2f57861facbe1f2b74f1d3e147c7c97edf91eeea920c5944d9c
python3 -B eng/r5_template_role_update.py \
  --prepared "$WORK/prepared" --report-sha256 "$REPORT_SHA256" \
  --r4-port 52181 --r5-port 52182 --output "$WORK/verified"
python3 -B eng/tests/test_r5_template_role_update.py --replay "$WORK/verified/report.json" \
  --case missing-receipt --output "$WORK/missing-receipt.json"
```

验收入口只在新建的环回专用容器内创建库，进程退出时关闭 Host、清理临时用户配置并移除本轮容器及其匿名卷。HTTP 和控制台记录先脱敏再落盘。验收证据目录必须尚不存在，且在封存准备目录之外。

本轮本机证据在 `.git/validate-r5-template-user-role-update/integration/`。复审后正式目录 `review-fixes/formal-v5/` 的 `report.json` SHA-256 为 `f5059b72ee0a6e1ed46f2d8d4ec95c995f216ccc72a0118ccc31f98631acc648`，含实际请求、原始响应、退化状态及 SQL 行。逐侧 `user-requests.jsonl`、`Migrator-target.jsonl` 及程序集 JSON 保留独立原始观测，`sql-commands.json` 记录实际脚本、参数和退出状态。封存准备报告 SHA-256 为 `c6c629df263afe0d8454aeea514b2b9c2688ab208d02ddfcc2d41576c0d0fe4b`。各运行的命令、日志、退出码和失败记录保留在同级。前序尝试定位了观测器构建目标、SQL `DB_ID()` 类型、创建回执偏移以及 EF 写入批次前导语句，修正后以新空库复跑。正式四个应用进程均退出 0，专用容器已移除，封存输出复核一致。复审前交接的 `formal-v4/` 原报告及命令保留。复审后仍使用同一份准备输入，以两个新空库复跑，并在新报告中登记验收源码摘要。

本轮覆盖默认租户普通用户的直接角色和更新字段。组织单元继承角色、最终权限、Angular、其他平台或数据库 Provider、生产部署及同库回退沿用各自范围。本轮保留既有 `User/GetAll` 观测实现，旧模板运行和原版回退入口均登记 `RoleRequestObserver.cs`。用 SDK `9.0.306` 构建原 `net9.0` 观测器通过。74 项 Python 回归、归档前 OpenSpec 全仓严格校验 16/16、归档后稳定规范严格校验 15/15 和归档任务校验 25/25 均通过。[固定模板历史验收](r5-automapper-template.md) · [公开同库回退](r5-consumer-package-rollback.md)
