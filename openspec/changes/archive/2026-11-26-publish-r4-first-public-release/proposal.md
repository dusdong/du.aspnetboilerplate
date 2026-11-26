# R4 首次公开发行与公开源消费验收

## Why

主仓 `5758c81` 已交付本地待发的 13 对包，固定模板已用该批次完成安装、升级和回退。首次公开发行需要证明上传的文件来自这批归档，并让普通消费者仅凭公开源就能安装、运行和取得匹配的符号。[发布者交接](../../../../docs/maintenance/r4-release-candidate.md#发布者交接) · [R4 路线](../../../../docs/maintenance/fork-roadmap.md#r4发布绑定精确提交和最终产物)

## What Changes

- 建立首发清单。用已交付的源码、主仓 tag、冻结批次摘要及 `publish-handoff-v2` 的 26 份归档确定发行身份，登记公开源、发布者、包名可用性和授权范围。
- 在取得对应外部操作授权后，为主仓建立发行 tag，按冻结 nuspec 发布到 nuget.org。内部依赖的主包经匿名下载、验签并与冻结内容核对后，才能上传依赖它的主包。分别记录主包与符号的进度，支持从部分完成、超时和版本冲突中续作。
- 从独立空缓存运行固定模板的两代业务回归，将还原的主包绑定到已验签的公开下载摘要，将编译、输出及实际加载的 DLL 绑定到冻结资产摘要，并核验公共调试符号。
- 发布 GitHub Release 前，从公开模板按发行说明草案在新库完成一次 `net10.0` 安装。发行说明以 `net10.0` 为新安装示例，单列 `net9.0` 存量应用迁移兼容性实测，附版本矩阵和校验清单。

## Capabilities

### New Capabilities

- `public-package-release` 规定已通过本地验收的发行批次如何获得公开身份，如何逐项确认发布结果，以及消费者如何从公开源独立核验和使用该版本。

### Modified Capabilities

无。沿用已归档的本地候选核验结果。

## Impact

发行对象是 11 个 `Du.Abp*` 包 `10.5.1`、`Du.AutoMapper 14.0.0` 和 `Du.AutoMapper.Collection 11.0.0`。三个生产仓沿用冻结提交，主仓负责 tag、说明和跨仓验收。固定免费模板的 Web.Host 与 Migrator 是公开源消费者，应用测试范围承接已验证的 macOS ARM64、SQL Server 和冻结 Angular 组合。准备和只读预检可以先行。实际公开写入须依据发布者对本批次的授权执行。[本地候选规范](../../../specs/release-candidate-verification/spec.md) · [精确版本与生产提交](../../../../eng/r4_release_candidate.json)
