# R5 发行前演练记录

2026-11-26 在 macOS ARM64 上完成。采用 SDK `10.0.404`、.NET 与 ASP.NET Core `9.0.10` 和 `10.0.15`、Chrome `158.0.8127.37`、固定模板 `2e9536872673a7ff1986a19e798c51684d16afe5`、已冻结的 Angular production 客户端和仅供本轮使用的 SQL Server Developer `16.0.4236.2`。R4 使用真实 nuget.org 下载及实际仓库签名。R5 部分受理等情形使用冻结批次的隔离副本、隔离协议响应与受理记录。[发行交接和正式验收顺序](release-handoff.md) · [R5 候选业务](consumption-validation.md)

本机原始证据目录为 `.git/prepare-r5-mapping-patch-release/rehearsal/`。各轮记录实际参数、输出、退出码及对应报告。`public-evidence-index.json` SHA-256 为 `c5f1079d6b84459686c38fb3d1439f741ea1c2a16ccc6b8715c8d99965e918a4`，索引中的下载、逐成员、验签日志、PDB 和模板资产均重新比对留存文件。

## R4 真实公开回读

由 `r4-readback.sh` 以 R4 发行清单 SHA-256 `cfe2a70f27c662edcf22424d202cbf3c6116c4510263146705bb0f721c7c670a` 和独立冻结批次 SHA-256 `4d25f237938d04aeb985c2057a6287ba0f18425b94d73e9c494e313684470757` 调用现行 `eng/r5_public_release.py`。按原 R4 主包、符号受理记录对账精确版本、上传 SHA-256 和所有者后，仅在新目录登记这些已有凭证。逐包匿名下载，SDK 对照 nuget.org 签名证书索引验证仓库签名和时间戳链。13 个主包签后摘要均异于上传件，去除签名成员后的文件集合与内容均匹配冻结主包。签名中的所有者和实际 NuGet 搜索结果一致，均为 `dusdong`。26 份归档输入和 18 个 Portable PDB 目标均保留。[R4 首发与实物](../../../../docs/maintenance/r4-release-candidate.md#公开主包符号与进度核验)

| 运行 | 退出码 | 观测 |
| --- | --- | --- |
| `r4-readback-01.log` | `1` | macOS 自带 Bash 在 `set -u` 下展开空数组失败，已登记首个主包的历史凭证。 |
| `r4-readback-02.log` | `2` | 修正脚本数组展开，沿用已有进度。13 个主包完成，17 个 PDB 完成，`Du.Abp.AspNetCore` 的 `net10.0` PDB 请求超时。 |
| `r4-readback-03.log` | `0` | 同一进度目录重跑，完成剩余 PDB，18 个均匹配 DLL 调试标识及冻结 PDB SHA-256。 |

`r4-readback/verified-downloads.json` SHA-256 为 `a5f57b2cf5d9cfe991b7c24e968048aa56c140918f2a03fa503147ecf2ae8f55`。13 条版本、上传与下载 SHA-256 也全部与既有 R4 公开登记一致。该文件用于下面的真实公开源消费演练。

## R5 队列和续作

待发 R5 清单固定三对归档、三个 PDB 目标和十个只读沿用包。三个新版本在匿名预检中分别返回未公开，先前 R5 预检记录另存。预检期间一次引擎 TLS 握手超时显示待核实，后续包保持阻塞。实际 R5 发布进度应使用独立目录，从本次发行的授权和外部凭证开始。[版本预检及清单](source-and-engine-validation.md) · [发布步骤](release-handoff.md#发布与回读命令)

隔离演练用 `eng/tests/verify_r5_public_release.py` 和同一冻结 R5 批次。初轮 `isolated-01.log` 退出 1，缺文件断言使用了不同错误文案。改为核对工具实际返回的“缺少实物”后复跑，并加入符号 gate 对索引的实查，最终 `r5-isolated-final.log` 七项通过，退出 0。入口打印每次 gate 的包、状态、依赖版本和失败项。每个用例的独立副本和进度保存在 `r5-isolated-final/`。

| 检查 | 结果 |
| --- | --- |
| 待发队列 | 引擎、Collection、适配器三项，六份归档，三个 PDB。将沿用的 `Du.Abp` 当作本次上传件登记被拒绝。 |
| 内容、版本与摘要冲突 | 同版本样本新增文件或删除一个 nuspec 精确依赖时，逐成员对账失败并保留冲突路径；错误实传摘要无法确认。已有版本仅在归属和内容证明匹配后接续。 |
| 部分受理及延迟 | 引擎受理后尚不可见，Collection 等待；引擎核验后 Collection 放行。符号未索引返回待核实，错误 PDB 摘要被拒绝，正确 PDB 续作通过。主包和符号受理各一条。无符号受理记录但索引已能读回时，符号 gate 也拒绝重复上传。 |
| 内核证据缺少或不符 | 引擎与 Collection 已验后，移走或改动 `Du.Abp [10.5.1]` 的 R4 验签原日志，适配器两次各自只被这一项阻塞。恢复原日志后各自放行，前两包状态及签后下载记录保持相同，每个前置主包仅查询一次。 |
| 公开下载登记 | 缺少适配器的部分登记被拒绝；13 条齐全通过摘要和批次关联检查；改用错误的独立批次摘要时拒绝。 |

隔离样本的三包回应、签名标志和受理均为本地测试输入。真实签名验证由上一节的 13 个 R4 实物覆盖。R5 三新包的公开签后下载、服务端三份 PDB 和真正公开源消费留给实际发行。

## 同一公开消费入口

在相同的 `eng/r5_template_consumer.py` 参数和校验条件下，用 R4 已验签公开下载登记完成真实 `upgrade` 和 `install`。两轮分别从空缓存仅经 nuget.org 还原，验证缓存中的实际 nupkg、编译引用、Release 输出和 CLR 实际加载。升级实跑 `net9.0` 与 `net10.0`。两代各自的 Web.Host 编译和输出 13 个维护包，且加载 11 个 ABP DLL 和唯一引擎。两代 Migrator 各自编译和输出 10 个维护包，加载七个 ABP DLL。按需 DLL 记录为仅输出。

| 同一入口动作 | 退出码 | 观测 |
| --- | --- | --- |
| `template-01/command.log`，`upgrade` | `0` | 两代 Migrator 实际迁移、Web.Host 的租户登录及授权查询、同库接续、两个恢复点复验均通过。四个 PID 为 `912`、`972`、`1172`、`1213`。 |
| `template-install-01/command.log`，`install` | `0` | `net10.0` 新库迁移、业务用户创建、重新登录及授权查询均通过。迁移 PID `3710`，查询 Host PID `3930`。 |
| `template-mixed-source/command.log`，`upgrade` | `1` | 传入 R5 候选实跑生成的含本地源的 `NuGet.Config`，在配置落地阶段拒绝，尚未还原。 |
| `template-wrong-batch/command.log`，`upgrade` | `1` | 维持 R4 独立登记的预期摘要，改用 R5 冻结目录，在读取输入阶段拒绝，尚未还原。 |

升级报告 SHA-256 为 `d328d24f98b08d10ad31f1387093ab7d62f9d8e4f9cb0121fbf6e3334f605f08`，新库安装报告为 `5eb7a6a2eba4b2d12c5f7444ae8e043a3f95019704a590db2aacd546c9042b9d`。四入口独立登记的还原、编译、输出和进程证据见索引。原 R5 组合的混合源构建和离线复核继续保留。待发 R5 本地组合的业务与回退边界沿用同批实测记录。[R5 候选同库业务](consumption-validation.md#固定模板与同库业务)

## 回归与工作区核对

R4 既有检查通过。组合清单负例 2/2、冻结包负例及搬移复验 5/5、首发清单 7/7、回读协议 9/9、公开消费 12/12、资产诊断 9/9、模板与历史输入诊断 8/8。对应命令、退出码与证据分别在 `r4-candidate-01.log`、`r4-batch-01.log`、`r4-manifest-01.log`、`r4-protocol-01.log`、`r4-consumer-01.log`、`r4-assets-01.log` 和 `r4-template-03.log`。R4 模板负例首轮按既有规则在当前 R5 主仓 gitlink 预检退出。第二轮用只读隔离 Git 元数据读取真实 R4 协调提交，推进至旧升级报告缺少 R4 规划与四入口字段处。用同一真实 R4 提交、空缓存与隔离数据库生成新的冻结升级报告后，第三轮 8 项全部通过。未登记额外 Git worktree。

Python 回归 45/45。新、旧 R5 批次各通过离线核验，原 R5 批次在混合源的 `net9.0` 两入口构建退出 0。可从 `r5-frozen-01.log`、`r5-original-01.log`、`template-old-r5-mixed.log` 和 `python-unit-01.log` 复核。主仓、子仓、暂存区、gitlink 及冻结实物的终态核对见 `scope-final.log`。本地文档链接、锚点、差异和 OpenSpec 严格检查在同目录留存。

真实 R4 新装中实际执行 33 条迁移命令，读到 30 条迁移历史。成功登录行由 0 增至 1，再增至 2。两代接续共通过 26 个阶段，两个恢复点均实际恢复并重查业务。测试运行的 Host、Migrator、浏览器和 SQL 容器均已清理，专用 SQL、Host 和 Angular 环回端口已释放，保留无凭据配置、日志和测试恢复介质。
