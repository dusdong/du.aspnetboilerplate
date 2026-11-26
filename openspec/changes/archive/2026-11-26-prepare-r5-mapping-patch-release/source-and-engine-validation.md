# R5 发行身份与引擎制备记录

## 版本与原批次核对

2026-11-26 21:14（Asia/Shanghai）核定拟用主仓 tag 为 `v10.5.2`，沿用 R4 的 `v10.5.1` 命名规则。`v10.5.1` 的附注 tag 指向 `5758c8186b68dcc42ecc90164cf9d3f53cf3345e`。本地 Git 无 `v10.5.2` 引用，GitHub 精确 tag 引用查询返回 HTTP 404。拟发 `Du.AutoMapper 14.0.1`、`Du.AutoMapper.Collection 11.0.1`、`Du.Abp.AutoMapper 10.5.2` 均未出现在 NuGet V3 版本索引，nuget.org 三个指定版本的匿名下载也均返回 HTTP 404。V3 请求在验证机重定向到镜像，精确下载以 nuget.org 的 CDN 响应为准。[R4 公开发行](https://github.com/dusdong/du.aspnetboilerplate/releases/tag/v10.5.1) · [NuGet V3 版本与内容接口](https://learn.microsoft.com/en-us/nuget/api/package-base-address-resource)

从 nuget.org 重新匿名下载十个沿用的 `10.5.1` 主包。各自的 SHA-256 与 R4 公开清单、原仓库验签下载登记及 R5 原批次留存实物一致，下载包内均有 `.signature.p7s`。将这些字节相同的实物与原验签日志逐包对账。`r4-signature-evidence.json` 登记公开下载摘要、签名成员摘要、仓库签名指纹、时间戳指纹及原始日志摘要。签名来源为 nuget.org，原验签登记的所有者均为 `dusdong`。[R4 公开校验附件](https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json) · [原 R4 仓库验签记录](../../../../docs/maintenance/r4-release-candidate.md#公开主包符号与进度核验)

| 生产仓 | 主仓 `99f44b730458ecacbc086b4ffc5dfc0ace367015` 的 gitlink | Git 树 |
| --- | --- | --- |
| `AutoMapper` | `d264ff75831f12e935df8d4703bb05df99eaa000` | `90d6080e4960a7005d29b29bb08eaac2aeca4b7e` |
| `AutoMapper.Collection` | `d22aaf58469d760502864fbb6f575b6505dd8334` | `0131ed22f1de1fbd8f05115e6e7da8cc1a3d59ed` |
| `aspnetboilerplate` | `7933e71f5646d2447af3502ecbea9a3f1aba8184` | `8b93fc58f7a8a4ba3d8f79870af270dba0707bc9` |

`.gitmodules` 对应 GitHub 仓库的 `maintenance/v14`、`maintenance/v11` 和 `dev` 分支当次回读均指向上表提交。从主仓根目录以原件执行下列离线核验，退出 0。原批次、生产树与编译基点的对应关系仍以归档报告为准。[原批次交接](../2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md#批次交接) · [离线核验入口](../../../../eng/r5_automapper_consumer.py)

```sh
python3 -B eng/r5_automapper_consumer.py --verify-only \
  --batch-root .git/review-r5-runtime-migration-readiness/package/frozen \
  --batch-sha256 8d0d4dc762a3582327d8829e5952fadbd55b7448d7c2de85c32e6a76d6a3cf40
```

本机原始证据在 `.git/prepare-r5-mapping-patch-release/engine/`。`preflight-03/report.json` SHA-256 为 `e5bd0f6e44fcaaa8a00a1bf3fe36097786b3f3cebaf0dcf913bb517d62407c75`。首次查询的 Git `ls-remote` 超时。改用 GitHub 精确引用接口后，第二轮脚本读取批次记录时误把包 ID 当作内部字段。第三轮从清单键读取 ID，完成全部只读查询和离线核验，退出 0。

## 引擎制备与归档差异

以干净的 `maintenance/v14` 本地提交 `54f6277af80783e5d07e896f75df0dcc0c4b4502` 制备，Git 树为 `fd695a05ec9f7039ecddebc8f18875dd5c57f795`。相对于原引擎提交，唯一改动是 `README.r5-package.md` 的标题、安装源及两条安装命令，共四行替换。新主包将 CLI 与 Visual Studio 安装源均显式指向 nuget.org，给出精确版本的包页面，并保留维护 Issue、上游链接、Jimmy Bogard 署名和 MIT 许可。主包内 README 与该 Git 对象逐字节匹配。还原、编译、打包所用 `RepositoryCommit`、`source-commit.txt` 和两份 nuspec 的 `repository/@commit` 均为上述提交。[包内说明源文件](../../../../AutoMapper/src/AutoMapper/ApiCompat/README.r5-package.md) · [生产入口说明](../../../../AutoMapper/src/AutoMapper/ApiCompat/README.r5.md)

在 macOS ARM64 `27.2.1`（`26B131`）使用 SDK `10.0.404`。从子仓根目录执行下列入口，`REFERENCE_NUPKG` 指向固定原版 `AutoMapper 13.0.0`，归档 SHA-256 为 `8ac567aa1ef2ecb44d02583432754e1a57cb64ac2bea3ef01966d25c27c7d621`，`ENGINE_OUT` 指向新的输出目录。生产入口首跑退出 0，同一次 Release Rebuild 的 ApiCompat 报告 0 项问题。

```sh
API_COMPAT_DOTNET=/usr/local/share/dotnet/dotnet \
  sh src/AutoMapper/ApiCompat/pack-r3-engine.sh --r5 "$REFERENCE_NUPKG" "$ENGINE_OUT"
```

| 新实物，路径相对于证据目录的 `production-01/` | 字节数 | SHA-256 |
| --- | ---: | --- |
| `feed/Du.AutoMapper.14.0.1.nupkg` | 135925 | `32bbe536dcb588e45257e9d3be5f5f62d7bbeeb642cc15cce857066b2b8d8993` |
| `symbols/Du.AutoMapper.14.0.1.snupkg` | 49392 | `0f2afb02a61541679282471c2ac7b642ab21c0385f30da224ef94ba651531886` |
| 主包内 `lib/net8.0/AutoMapper.dll` | 284672 | `1d752c32c70cff281afc3bee951abdf763b0910ba74be6a4772854149fe75bd0` |
| 符号包内 `lib/net8.0/AutoMapper.pdb` | 96340 | `7d861e56f77e30a769a5d985db7d75a4560a5d8e64dc2aed54f138145a6af71d` |

- 主包原件和新件均有九个成员，符号包均有五个成员。成员路径、排列及压缩方法一致。主包的 README、nuspec、DLL 和符号包的 nuspec、PDB 内容有差异。两份 nuspec 的内容只更换仓库提交。其余成员内容摘要一致，包括封装关系和内容类型、核心属性、MIT 文本、图标与 XML 文档。ZIP 成员时间戳有变化，变动成员的压缩后大小逐项登记。两份新件均为本地未签名归档。
- DLL 字节变化。程序集身份为 `AutoMapper, Version=14.0.0.0, Culture=neutral, PublicKeyToken=be96cd2c38ef1005`，目标为 `net8.0`，文件版本为 `14.0.1.0`，继续使用 `PublicSign`。新旧两份 DLL 的 ILSpy IL 输出逐字节一致，166 个公开及受保护类型和成员一致。生成的 `AssemblyInfo` 仅更换提交，实际 `ProductVersion` 跟随新提交。下轮消费者复验使用新 DLL 摘要。
- Portable PDB 的 GUID 从 `965cfff0-6dda-4adf-aa4f-c14e82cd1837` 变为 `97b439df-4508-4bf8-8a83-e306925ad486`。新旧各自通过 DLL CodeView 的 GUID、stamp、age 及调试校验和比对。新件 Source Link 指向 `54f6277a`，78 份源码核对到对应 Git 对象，三个生成文档随 PDB 内嵌。符号包的 PDB 与打包前编译输出同摘要。

实物核验的 `inspection-03/report.json` SHA-256 为 `c178c7e98b55ffc6685cf6d97cb7a2cbcfcebcbab319ffe74d0148e920841728`，包括原件与新件的逐成员字节和 ZIP 元数据。第一次检查脚本名 `inspect.py` 遮蔽 Python 同名标准库。改名后，第二次检查误要求符号 nuspec 也声明 `authors`。按 NuGet 实际格式在主包核对署名，第三次检查复用同一对新制品并退出 0。

本轮制包验收时，拟用 `v10.5.2` 的目标提交尚未确定。主仓 `99f44b7` 的引擎 gitlink 当时为 `d264ff75`，新引擎提交当时只在本地。后续源码交付及 tag 目标的核对入口见待发交接。[发行前核定 tag](release-handoff.md#发行前核定-tag)

## 三包待发批次

2026-11-26 制备的本地待发目录为 `.git/prepare-r5-mapping-patch-release/batch/frozen/`。独立登记的 `batch.json` SHA-256 为 `b914f5669c504a3a85cd7120fb63ff0d14667924d6dd0ff1f92fea9a1a76eaf1`。模板仍固定在 `2e9536872673a7ff1986a19e798c51684d16afe5`。以下表格按上传顺序登记六份归档，三份主包在 `feed/`，对应符号包在 `symbols/`。

| 待发包 | 主包 SHA-256 | 符号包 SHA-256 |
| --- | --- | --- |
| `Du.AutoMapper 14.0.1` | `32bbe536dcb588e45257e9d3be5f5f62d7bbeeb642cc15cce857066b2b8d8993` | `0f2afb02a61541679282471c2ac7b642ab21c0385f30da224ef94ba651531886` |
| `Du.AutoMapper.Collection 11.0.1` | `b6229b0cfde5d96024541a146483b0b30875b6002acef02d6c1852d35d38a7a1` | `d22d7377514910dd1bcc4aeb70ad453552fd0485bfd50d607cc3c15dee1bf066` |
| `Du.Abp.AutoMapper 10.5.2` | `095ecde6a4db3bb7f48fb777f06c258cbc14a4c1c6b6a6de0affafa05b2cc683` | `4c93ce73e07b345159b8c83a1e6b80b847353082c2eef23be72c5ae67b57592b` |

| 待发包 | 编译及包内仓库提交 | 生产提交 | 生产 Git 树 |
| --- | --- | --- | --- |
| `Du.AutoMapper` | `54f6277af80783e5d07e896f75df0dcc0c4b4502` | `54f6277af80783e5d07e896f75df0dcc0c4b4502` | `fd695a05ec9f7039ecddebc8f18875dd5c57f795` |
| `Du.AutoMapper.Collection` | `306b49d7a59b7335a61d8116e1ab2f623a04740e` | `d22aaf58469d760502864fbb6f575b6505dd8334` | `0131ed22f1de1fbd8f05115e6e7da8cc1a3d59ed` |
| `Du.Abp.AutoMapper` | `bed57726b56f6f9de5c2d82e8dbe55e0130bddd0` | `7933e71f5646d2447af3502ecbea9a3f1aba8184` | `8b93fc58f7a8a4ba3d8f79870af270dba0707bc9` |

Collection 和适配器沿用原候选的两对归档。各自的冻结补丁在隔离 Git 索引和对象目录从表中编译基点回放，两棵树分别等于相应主仓 gitlink 的子仓提交树。符号包的 19 和 13 份 Source Link 源文档逐一匹配编译基点及已交付生产提交。两包 README 分别与生产树的打包模板展开结果字节一致，包含相应精确版本的两条安装命令、nuget.org 包页面、维护入口及 MIT 署名。三个包内 DLL/PDB 分别与各自的原生产输出核对，CodeView 的 PDB 文件名、GUID、stamp、age 和确定性 SHA-256 校验和均匹配。

实际 nuspec 声明四条内部精确边。Collection 使用 `Du.AutoMapper [14.0.1]`。适配器使用 `Du.AutoMapper [14.0.1]`、`Du.AutoMapper.Collection [11.0.1]` 和 `Du.Abp [10.5.1]`。清单的 `compiledWith` 字段登记两包历史生产还原图选择的版本、编译路径与输入包和 DLL 摘要。当时两包均使用原候选引擎归档 `8c780d4d…781b5` 和原 DLL `5ae7cbd5…6d82d`。适配器的原生产输入是带仓库签名的 R4 内核，原还原图记录的 SHA-512 与 R4 签名前归档一致。签前和签后归档逐成员复核通过，区别为仓库签名成员。两份历史还原图、原生产命令和该内核的签前对照归档均随批交接。

清单的 `publicPackages` 逐项绑定十个 R4 `10.5.1` 公开包的签前与签后摘要、匿名下载来源、签名成员及原验签日志。随批的 `public/R4-PACKAGE-CHECKSUMS.json` 和 `public/verified-downloads.json` 保留完整 R4 对照登记。新引擎的实物检查使用本轮 `records/engine-archive-inspection.json` 和生产记录。旧引擎的专项及旧组合的运行证据按 `release.historicalBatchSha256` 留在原冻结批次。待发组合的独立消费、引擎专项、四入口和受影响的业务复验在 2.2 登记。[原批次及运行报告](../2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md)

从主仓根目录使用独立登记的摘要核验。该步骤只读，无须还原或执行应用。用同一摘要和目录可调用现有独立消费和混合源模板入口。[批次制备与核验入口](../../../../eng/r5_release_batch.py) · [独立消费入口](../../../../eng/r5_automapper_consumer.py) · [模板入口](../../../../eng/r5_template_consumer.py)

```sh
python3 -B eng/r5_release_batch.py verify \
  --batch-root .git/prepare-r5-mapping-patch-release/batch/frozen \
  --batch-sha256 b914f5669c504a3a85cd7120fb63ff0d14667924d6dd0ff1f92fea9a1a76eaf1
```

本机证据在 `.git/prepare-r5-mapping-patch-release/batch/`。从根目录运行 `sh .git/prepare-r5-mapping-patch-release/batch/prepare.sh "$NEW_BATCH_ROOT" "$NEW_LOG_ROOT"` 可用相同输入向两处新目录制备。正式制备和独立重跑均退出 0，`batch.json` 字节一致。现有消费者 `--verify-only` 对新、旧 R5 批次分别退出 0，R4 固定批次通过原入口核验。将独立副本的同名主包替换成旧引擎时退出 1，报告 `feed/Du.AutoMapper.14.0.1.nupkg` 的实际和预期 SHA-256。对原批次传入新摘要时退出 1，报告 `batch.json` 摘要不符。原始日志和退出码见 `prepare.log`、`replay.log` 与 `verify/`。
