# R5 映射三包待发交接

**状态为本地待发。** 三包实物和候选业务已经复验，发布流程及纯公开源入口已经演练，发行准备已归档。维护者决定发行后，从归档对应的主仓协调提交核定 tag 目标，再按下文接续。公开发行基线为 `v10.5.1`。[实物与版本预检](source-and-engine-validation.md) · [R5 候选业务](consumption-validation.md) · [回读与续作演练](release-rehearsal.md)

## 实物清单

验证机待发目录为 `.git/prepare-r5-mapping-patch-release/batch/frozen/`，独立登记的 `batch.json` SHA-256 为 `b914f5669c504a3a85cd7120fb63ff0d14667924d6dd0ff1f92fea9a1a76eaf1`。从该批次导出的 `r5-release-manifest.json` SHA-256 为 `2f4ba12a0752739eaafb522d5c9e0a20abd241176646ae31d4748e5102a3fa02`。主包在 `feed/`，符号包在 `symbols/`。

| 包 | 主包 SHA-256 | 符号包 SHA-256 | 公开符号回读目标 |
| --- | --- | --- | --- |
| `Du.AutoMapper 14.0.1` | `32bbe536dcb588e45257e9d3be5f5f62d7bbeeb642cc15cce857066b2b8d8993` | `0f2afb02a61541679282471c2ac7b642ab21c0385f30da224ef94ba651531886` | `lib/net8.0/AutoMapper.pdb` |
| `Du.AutoMapper.Collection 11.0.1` | `b6229b0cfde5d96024541a146483b0b30875b6002acef02d6c1852d35d38a7a1` | `d22d7377514910dd1bcc4aeb70ad453552fd0485bfd50d607cc3c15dee1bf066` | `lib/net8.0/AutoMapper.Collection.pdb` |
| `Du.Abp.AutoMapper 10.5.2` | `095ecde6a4db3bb7f48fb777f06c258cbc14a4c1c6b6a6de0affafa05b2cc683` | `4c93ce73e07b345159b8c83a1e6b80b847353082c2eef23be72c5ae67b57592b` | `lib/net9.0/Abp.AutoMapper.pdb` |

十个沿用包均为公开 R4 的 `10.5.1`。依次为 `Du.Abp`、`Du.Abp.AspNetCore`、`Du.Abp.AspNetCore.SignalR`、`Du.Abp.Castle.Log4Net`、`Du.Abp.EntityFramework.Common`、`Du.Abp.EntityFrameworkCore`、`Du.Abp.Web.Common`、`Du.Abp.Zero.Common`、`Du.Abp.ZeroCore`、`Du.Abp.ZeroCore.EntityFrameworkCore`。全部公开下载摘要和验签日志已关联到待发批次，上传队列只含表中三包。[沿用包证据](source-and-engine-validation.md#版本与原批次核对)

## 安装与发行说明草案

本版修复共享集合映射执行计划在不同注册和预热顺序下的上下文偏差。经典 ASP.NET Boilerplate 应用将适配器升至 `Du.Abp.AutoMapper 10.5.2`，其精确传递依赖为 `Du.AutoMapper [14.0.1]`、`Du.AutoMapper.Collection [11.0.1]` 以及 `Du.Abp [10.5.1]`。Collection 也固定引擎 `[14.0.1]`。已有直接引用时一并对齐。只使用引擎或只使用 Collection 的项目按其直接依赖选择对应安装命令。

三个版本在 nuget.org 全部核验通过后，在项目目录执行适用命令。示例使用 .NET 10 SDK。使用 .NET 9 SDK 时，命令形式为 `dotnet add package`，其余参数相同。使用 Central Package Management 的项目在 `Directory.Packages.props` 固定对应版本。需要限制为精确版本时使用方括号，例如 `Version="[10.5.2]"`。[NuGet CLI 安装命令](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-package-add)

```sh
source_url=https://api.nuget.org/v3/index.json
dotnet package add Du.Abp.AutoMapper --version 10.5.2 --source "$source_url"
dotnet package add Du.AutoMapper --version 14.0.1 --source "$source_url"
dotnet package add Du.AutoMapper.Collection --version 11.0.1 --source "$source_url"
```

新安装示例以 `net10.0` 为目标。这里的 R5 本地实测覆盖 macOS ARM64、固定模板、SQL Server Developer 和冻结 Angular，运行时为 .NET 与 ASP.NET Core `10.0.15`。另有存量 `net9.0` 从 `9.0.10` 接续同库的证据。发布时以公开源运行报告补齐版本、环境、实际进程和业务结果。其他操作系统、数据库 Provider、客户端或生产部署的兼容性需按实际应用验证。[R5 待发实测](consumption-validation.md#固定模板与同库业务)

如果需要切回公开 R4，在同一组应用引用中一起恢复 `Du.Abp.AutoMapper 10.5.1`、`Du.AutoMapper.Collection 11.0.0` 和 `Du.AutoMapper 14.0.0`，并在独立空缓存还原、重建。R5 候选阶段的同库回退验证覆盖 R4 阶段写入的租户用户和后续成功登录行。候选阶段新增的其他业务实体需要单独核验。升级前保留与回退目标对应的可恢复介质。[同库切换观测](consumption-validation.md#固定运行时的公开-r4-同库切换)

## 发行前核定 tag

拟用 tag 为 `v10.5.2`。制包验收时的主仓为 `99f44b730458ecacbc086b4ffc5dfc0ace367015`，Git 树为 `cdb2c5d481f29b2e6584f80de5d1ea4bb038f8de`。下表保留当时用 `git ls-tree` 读出的三个生产 gitlink。新制包引擎已从登记的 `dusdong/AutoMapper` 仓库 `maintenance/v14` 回读。本次归档对应的主仓协调提交固定该引擎和两项沿用的生产提交。[新引擎交付](https://github.com/dusdong/AutoMapper/commit/54f6277af80783e5d07e896f75df0dcc0c4b4502)

| 子仓 | 验收时主仓树中的 gitlink | 验收时 gitlink 的生产树 | 本次协调提交应固定的生产提交与树 |
| --- | --- | --- | --- |
| `AutoMapper` | `d264ff75831f12e935df8d4703bb05df99eaa000` | `90d6080e4960a7005d29b29bb08eaac2aeca4b7e` | `54f6277af80783e5d07e896f75df0dcc0c4b4502` · `fd695a05ec9f7039ecddebc8f18875dd5c57f795` |
| `AutoMapper.Collection` | `d22aaf58469d760502864fbb6f575b6505dd8334` | `0131ed22f1de1fbd8f05115e6e7da8cc1a3d59ed` | 沿用验收时的提交与树 |
| `aspnetboilerplate` | `7933e71f5646d2447af3502ecbea9a3f1aba8184` | `8b93fc58f7a8a4ba3d8f79870af270dba0707bc9` | 沿用验收时的提交与树 |

打 tag 前依次完成以下事项。

1. 在从 `https://github.com/dusdong/du.aspnetboilerplate.git` 取得的主仓 `main` 历史中，用 `git log -1 --diff-filter=A --format=%H main -- openspec/changes/archive/2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md` 找到首次引入本交接的协调提交。将结果设为 `R5_TARGET` 并运行下方的 `r5_target_links` 核对三个生产 gitlink 和固定模板 gitlink。
2. 用 `git config --blob "$R5_TARGET:.gitmodules" --get-regexp '^submodule\..*\.url$'` 核对三仓来源，从登记仓库取得相应提交并用 `git rev-parse '<生产提交>^{tree}'` 逐一与上表对账。Collection 与适配器的 nuspec 编译基点分别是 `306b49d7a59b7335a61d8116e1ab2f623a04740e` 和 `bed57726b56f6f9de5c2d82e8dbe55e0130bddd0`，两份补丁回放树已与各自生产提交对账。[编译基点证据](source-and-engine-validation.md#三包待发批次)
3. 在登记的目标仓库复核 tag 指针和 NuGet 三个实际版本，确认授权、包所有者和归属凭证。若名称已占用，只有来源与该目标提交或同批实物均可查证时接续。不同归属或内容的占用须暂停并重新决定版本、精确边与复验范围。[第一次版本查证](source-and-engine-validation.md#版本与原批次核对)

先定义以下函数，用 `r5_target_links` 核对 `R5_TARGET` 的完整提交 SHA 和四项 gitlink。完成三项核对、下一节的本地准备并取得发行授权后，再单独执行 `r5_publish_tag`。

```sh
R5_TAG=v10.5.2
R5_TAG_REF="refs/tags/$R5_TAG"
R5_GITHUB_URL=https://github.com/dusdong/du.aspnetboilerplate.git

r5_target_links() (
  target=$(git rev-parse --verify "${R5_TARGET:?}^{commit}") || exit "$?"
  test "$target" = "$R5_TARGET" || exit 1
  links=$(git ls-tree "$target" -- AutoMapper AutoMapper.Collection aspnetboilerplate module-zero-core-template) || exit "$?"
  expected=$(printf '160000 commit %s\t%s\n' \
    54f6277af80783e5d07e896f75df0dcc0c4b4502 AutoMapper \
    d22aaf58469d760502864fbb6f575b6505dd8334 AutoMapper.Collection \
    7933e71f5646d2447af3502ecbea9a3f1aba8184 aspnetboilerplate \
    2e9536872673a7ff1986a19e798c51684d16afe5 module-zero-core-template)
  if [ "$links" != "$expected" ]; then
    printf '目标提交的 gitlink 不匹配\n%s\n' "$links" >&2
    exit 1
  fi
  printf '%s\n' "$links"
)

r5_remote_tag() {
  git ls-remote "$R5_GITHUB_URL" "$R5_TAG_REF" "${R5_TAG_REF}^{}"
}

r5_check_tag() {
  printf '%s\n' "$1" | awk -v ref="$R5_TAG_REF" -v target="$R5_TARGET" '
    NF == 2 && $2 == ref && length($1) == 40 && $1 ~ /^[0-9a-f]+$/ { tag++; oid=$1; next }
    NF == 2 && $2 == ref "^{}" && $1 == target { peeled++; next }
    { bad=1 }
    END { if (!bad && tag == 1 && peeled == 1) print oid; else exit 1 }
  '
}

r5_publish_tag() (
  links=$(r5_target_links) || exit "$?"
  tree=$(git rev-parse --verify "${R5_TARGET}^{tree}") || exit "$?"
  listing=$(r5_remote_tag) || exit "$?"
  if [ -z "$listing" ]; then
    if git show-ref --verify --quiet "$R5_TAG_REF"; then
      local_target=$(git rev-parse --verify "${R5_TAG_REF}^{commit}") || exit "$?"
      if [ "$local_target" != "$R5_TARGET" ]; then
        printf '本地同名 tag 指向其他提交\n' >&2
        exit 1
      fi
    else
      status=$?
      test "$status" -eq 1 || exit "$status"
      git tag -a "$R5_TAG" "$R5_TARGET" -m 'v10.5.2 映射集合上下文修复' || exit "$?"
    fi
    local_tag=$(git rev-parse --verify "${R5_TAG_REF}^{tag}") || exit "$?"
    git push --no-follow-tags --recurse-submodules=no "$R5_GITHUB_URL" "$local_tag:$R5_TAG_REF" || exit "$?"
    listing=$(r5_remote_tag) || exit "$?"
    remote_tag=$(r5_check_tag "$listing") || exit "$?"
    test "$remote_tag" = "$local_tag" || exit 1
  else
    r5_check_tag "$listing" >/dev/null || {
      printf '远端同名 tag 与已核定目标不符\n' >&2
      exit 1
    }
  fi
  receipt=$(mktemp "${R5_RELEASE_WORK:?}/tag.XXXXXXXX") || exit "$?"
  printf 'target %s\ntree %s\n%s\n%s\n' "$R5_TARGET" "$tree" "$links" "$listing" >"$receipt" || exit "$?"
  r5_readback record --kind tag --outcome confirmed --evidence "$receipt"
)
```

远端查询成功且返回空结果时才进入首次推送分支。本地同名附注 tag 若已指向已核定提交，可接续该对象。远端已有匹配附注 tag 时只回读并登记。若任一查询失败、指针冲突或推送结果不确定，先查明状态再重跑 `r5_publish_tag`。发行清单的 `release.commit` 保持冻结时的 `null`，实际目标由远端 tag 回读凭证和最终发行附件绑定。

## 发布与回读命令

以下从主仓根目录执行。先在本地完成清单导出和六份实物复核。`R5_RELEASE_WORK` 指向本次实际发行的进度目录，位于冻结目录外，并应在所有回读、登记和续作中复用。

```sh
R5_BATCH=.git/prepare-r5-mapping-patch-release/batch/frozen
R5_BATCH_SHA=b914f5669c504a3a85cd7120fb63ff0d14667924d6dd0ff1f92fea9a1a76eaf1
R5_MANIFEST="$R5_RELEASE_WORK/r5-release-manifest.json"
R5_MANIFEST_SHA=2f4ba12a0752739eaafb522d5c9e0a20abd241176646ae31d4748e5102a3fa02

r5_readback() {
  python3 -B eng/r5_public_release.py --batch-root "$R5_BATCH" --batch-sha256 "$R5_BATCH_SHA" \
    --manifest "$R5_MANIFEST" --manifest-sha256 "$R5_MANIFEST_SHA" --work "$R5_RELEASE_WORK" "$@"
}

r5_prepare() (
  mkdir -p "${R5_RELEASE_WORK:?}" || exit "$?"
  python3 -B eng/r5_release_batch.py verify --batch-root "$R5_BATCH" --batch-sha256 "$R5_BATCH_SHA" || exit "$?"
  python3 -B eng/r5_public_release.py --batch-root "$R5_BATCH" --batch-sha256 "$R5_BATCH_SHA" \
    --manifest "$R5_MANIFEST" manifest || exit "$?"
  r5_readback queue
)
```

先运行 `r5_prepare`，退出 0 后单独运行 `r5_readback verify --main-only` 做匿名预检。新版本尚不可见时退出 `2`。沿用包需要逐一通过，尤其 `Du.Abp [10.5.1]`。若证据损坏，使用原留存的对应文件补齐并在同一进度目录重跑。取得授权且完成 tag 核定时，单独执行 `r5_publish_tag`。

按表中顺序逐包进行。将 `ID`、`VERSION`、`MAIN_SHA`、`SYMBOL_SHA` 设为该行列出的精确值，将 `NUGET_OWNER` 设为已核对的所有者。引擎通过公开主包回读后 Collection 才可上传，两者都通过且 `Du.Abp [10.5.1]` 的沿用证据完整时适配器才可上传。以下命令仅在取得相应授权后执行。使用支持 `NUGET_API_KEY` 和 `NUGET_SYMBOL_API_KEY` 的 NuGet CLI 从环境接收临时凭据。[NuGet CLI 上传](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-nuget-push) · [符号包上传](https://learn.microsoft.com/en-us/nuget/create-packages/symbol-packages-snupkg)

```sh
r5_push_archive() (
  archive=$1
  expected=$2
  shift 2
  actual=$(shasum -a 256 "$archive") || exit "$?"
  if [ "${actual%% *}" != "$expected" ]; then
    printf '上传归档 SHA-256 不符：%s\n' "$archive" >&2
    exit 1
  fi
  receipt=$(mktemp "${R5_RELEASE_WORK:?}/push.XXXXXXXX") || exit "$?"
  if dotnet nuget push "$archive" --source https://api.nuget.org/v3/index.json "$@" >"$receipt" 2>&1; then
    printf '%s\n' "$receipt"
  else
    status=$?
    printf '上传退出 %s，凭证：%s\n' "$status" "$receipt" >&2
    exit "$status"
  fi
)

r5_publish_main() (
  : "${ID:?}" "${VERSION:?}" "${MAIN_SHA:?}" "${NUGET_OWNER:?}"
  r5_readback gate --package "$ID" || exit "$?"
  receipt=$(r5_push_archive "$R5_BATCH/feed/$ID.$VERSION.nupkg" "$MAIN_SHA" --no-symbols) || exit "$?"
  printf '主包上传凭证：%s\n' "$receipt"
  r5_readback record --kind main --package "$ID" --outcome accepted --owner "$NUGET_OWNER" \
    --upload-sha256 "$MAIN_SHA" --evidence "$receipt" || exit "$?"
  r5_readback verify --package "$ID" --main-only
)

r5_publish_symbols() (
  : "${ID:?}" "${VERSION:?}" "${SYMBOL_SHA:?}"
  r5_readback gate --package "$ID" --symbols || exit "$?"
  receipt=$(r5_push_archive "$R5_BATCH/symbols/$ID.$VERSION.snupkg" "$SYMBOL_SHA") || exit "$?"
  printf '符号包上传凭证：%s\n' "$receipt"
  r5_readback record --kind symbols --package "$ID" --outcome accepted \
    --upload-sha256 "$SYMBOL_SHA" --evidence "$receipt" || exit "$?"
  r5_readback verify --package "$ID"
)
```

首次上传主包执行 `r5_publish_main`。主包已验签并对账时，可直接用 `r5_publish_symbols` 接续，每个动作独立过 gate。gate 返回非零便停止该动作。NuGet CLI 不跳过重复版本，只有实际上传退出 0 才登记 `accepted`。上传失败时检查打印的脱敏凭证，按实际结果通过 `r5_readback record --kind "$KIND" --package "$ID" --outcome "$OUTCOME" --evidence "$RECEIPT"` 登记，其中 `KIND` 为 `main` 或 `symbols`，`OUTCOME` 为 `timeout`、`duplicate` 或 `failed`，再运行 `verify`。确认已公开的是本批次才登记 `confirmed`。确认上次未受理且公开服务状态允许补交才登记 `retry`，随后重新过对应 gate。主包的 `confirmed` 须提供上传 SHA-256 和所有者，符号的 `confirmed` 须提供上传 SHA-256。需要登记多个所有者时，为每位所有者提供一个 `--owner`。

核验退出 `2` 时继续读回等待索引，退出 `1` 时查看证据及失败原因。归属或内容冲突应保留原证据。已验项复用原记录。候选和隔离演练各自使用独立进度目录。

## 正式公开后的验收

1. 用实际发行进度执行 `r5_readback verify`。要求三个新主包的匿名下载、仓库验签和逐成员对账通过；签前、签后摘要和签名成员可逐一回溯；三个 Portable PDB 均按包、TFM 和相应公开 DLL 的调试标识从符号服务读回，且与冻结符号同摘要；十个沿用包的公开证据全部可读。将 `verified-downloads.json` 的 SHA-256 独立登记为 `R5_DOWNLOADS_SHA`。
2. 用已验签的下载登记执行下列同一条纯 nuget.org 入口。每个动作使用独立新目录和空缓存。为维护者验证配置专用 SQL Server、三个环回端口、SQL 和模板测试凭据、冻结 Angular 和历史验证备份，按固定模板复跑指南准备。两代使用 SDK `10.0.404` 及对应共享框架。[隔离实例、凭据和复跑配置](../../../../docs/maintenance/r5-automapper-template.md#复跑)
3. 用 `install` 核对新库迁移、租户授权和真实应用写入与查询。用 `upgrade` 核对 `net9.0`、`net10.0` 的 Web.Host、Migrator 四入口，验证归档来源、编译、输出和实际加载，验证同库接续、授权查询和恢复点。将公开用户安装草案在干净目录用实际公开包执行一遍，按结果更新说明。

```sh
r5_public_template() {
  "$R5_PYTHON" -B eng/r5_template_consumer.py "$1" \
    --batch-root "$R5_BATCH" --batch-sha256 "$R5_BATCH_SHA" \
    --release-manifest "$R5_MANIFEST" --manifest-sha256 "$R5_MANIFEST_SHA" \
    --verified-downloads "$R5_RELEASE_WORK/verified-downloads.json" \
    --downloads-sha256 "$R5_DOWNLOADS_SHA" --frozen-root .git \
    --runtime-config "$R5_RUNTIME_CONFIG" --evidence-root "$R5_TEMPLATE_EVIDENCE"
}

r5_public_template install
r5_public_template upgrade
```

`R5_PYTHON` 指向含 `pymssql` 与 `playwright` 的验收 Python。公开模式生成只含 nuget.org 的 NuGet 配置并从还原所得缓存验证实际归档；可选的 `--nuget-config` 必须与生成配置等价。两个 TFM 的 `r4-build-assets.json` 及报告中的 `r4ProcessAssets` 保留四入口的实物及进程对账。新库安装另在报告 `sql.phases.install` 登记入口资产、数据库及浏览器观测。[包源映射说明](https://learn.microsoft.com/en-us/nuget/consume-packages/package-source-mapping)

核对公开结果并获授权后，整理消费者可用的发行说明及公开校验附件。将 `R5_NOTES` 指向最终发行说明，将 `R5_CHECKSUMS` 指向名为 `R5-PACKAGE-CHECKSUMS.json` 的已核对附件，其中登记 tag 实际提交、三个生产 gitlink、版本、上传和签后下载摘要及 PDB 结果。确认 GitHub 账号、仓库权限和批准的目标后，首次发行执行 `r5_publish_release create`。已有 Release 或创建结果不确定时，查明服务状态后用 `r5_publish_release resume` 专门回读。仅在实际发布状态、tag 对象和公开附件均匹配时登记确认。

```sh
r5_publish_release() (
  case "${1-}" in
    create|resume) ;;
    *) exit 1 ;;
  esac
  repo=github.com/dusdong/du.aspnetboilerplate
  asset=R5-PACKAGE-CHECKSUMS.json
  test -f "${R5_CHECKSUMS:?}" && test "${R5_CHECKSUMS##*/}" = "$asset" || exit 1
  r5_target_links >/dev/null || exit "$?"
  listing=$(r5_remote_tag) || exit "$?"
  tag=$(r5_check_tag "$listing") || exit "$?"
  gh auth status --hostname github.com || exit "$?"
  receipt=$(mktemp -d "${R5_RELEASE_WORK:?}/release.XXXXXXXX") || exit "$?"
  if [ "$1" = create ]; then
    gh release create "$R5_TAG" "$R5_CHECKSUMS" --repo "$repo" \
      --title 'v10.5.2 映射集合上下文修复' --notes-file "${R5_NOTES:?}" --verify-tag || exit "$?"
  fi
  url=$(gh release view "$R5_TAG" --repo "$repo" --json tagName,isDraft,url \
    --jq 'select(.tagName == "v10.5.2" and (.isDraft | not)) | .url') || exit "$?"
  test "$url" = "https://$repo/releases/tag/$R5_TAG" || exit 1
  gh release download "$R5_TAG" --repo "$repo" --pattern "$asset" --dir "$receipt" || exit "$?"
  if ! cmp -s "$R5_CHECKSUMS" "$receipt/$asset"; then
    printf '公开发行校验附件与批准文件不符\n' >&2
    exit 1
  fi
  listing=$(r5_remote_tag) || exit "$?"
  readback_tag=$(r5_check_tag "$listing") || exit "$?"
  test "$tag" = "$readback_tag" || exit 1
  printf '%s\n%s\n' "$url" "$listing" >"$receipt/readback.txt" || exit "$?"
  shasum -a 256 "$receipt/$asset" >>"$receipt/readback.txt" || exit "$?"
  r5_readback record --kind release --outcome confirmed --evidence "$receipt/readback.txt"
)
```

[GitHub CLI 创建发行](https://cli.github.com/manual/gh_release_create) · [读取发行](https://cli.github.com/manual/gh_release_view) · [下载附件](https://cli.github.com/manual/gh_release_download)
