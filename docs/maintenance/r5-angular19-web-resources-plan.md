# R5 Angular 19 Web Resources 单包验证计划

2026-11-28，在 macOS ARM64 从经典框架固定 Git 对象制成 `abp-web-resources 6.1.0`，在固定免费模板和公开 `abp-ng2-module 12.1.0` 上完成空缓存冻结安装、Angular `19.2.1` production 构建以及浏览器静态验收。验收要求已同步到稳定规范，六项任务已归档。[实测结果](#实测结果) · [从普通克隆复跑](#从普通克隆复跑) · [稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-固定-angular-19-模板可验收从经典框架-git-制成的资源包) · [归档提案](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-web-resources/proposal.md) · [归档任务](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-web-resources/tasks.md)

## 前置验收

- **已交付基线。** 2026-11-27 交付收尾时，GitHub `main` 回读为 `b2d2da6`，对应 `verify-r0` 成功。14 个交付文件与 Git 对象一致，归档任务 7/7，稳定规范中的一项要求及七个场景与增量原文一致。本轮在 Python `3.12.14` 和 `3.14.7` 各重跑 85 项回归并通过。11-27 冷构建及构建后四个样本的回放报告已复核，本轮未重复执行。全仓 15/15、归档 27/27 和 347 个本地链接、125 个锚点是当时收尾的记录。[交付提交](https://github.com/dusdong/du.aspnetboilerplate/commit/b2d2da65e0ce0fce6d55c27a16ac1375ed97b60a) · [工作流](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/46017922338) · [冷构建与修订回放](r5-public-angular-rebuild.md#字体诊断修正实测)
- **适配器已交付。** 2026-11-28 适配器交付收尾时，GitHub `main` 回读为 `fbf3a4740e2a432409e14298ae292f43e6aed88a`，五项任务已归档，相关验收要求已同步到稳定规范。该轮本地候选与公开适配器各有 25 个文件，仅 README 和 source map 不同。模板构建确认候选 FESM 贡献 8985 字节，两个适配器对照的 1175 个浏览器 JS 逐项一致。本轮资源包试验使用公开适配器。[交付提交](https://github.com/dusdong/du.aspnetboilerplate/commit/fbf3a4740e2a432409e14298ae292f43e6aed88a) · [适配器实测](r5-angular19-adapter-package-plan.md#实测结果)

## 固定输入

| 输入 | 固定身份 |
| --- | --- |
| 权威资源 | 框架生产 gitlink `7933e71f5646d2447af3502ecbea9a3f1aba8184` 的 `src/Abp.Web.Resources/Abp/Framework`，tree `780977463dbf0eb599765ff553000a631a70b35d` |
| 分发包装参考 | `aspnetboilerplate/bower-abp-resources` 的 npm `gitHead` `fb79b7d44bc9dfce0ae600c8170961f182b05e76`，用于核对包装。兼容指南另采用固定快照 `8084a375`。旧 `packages.config` 登记 `Abp.Web.Resources 5.1.0`／`net461`。 |
| 公开对照 `abp-web-resources 6.1.0` | [npm tarball](https://registry.npmjs.org/abp-web-resources/-/abp-web-resources-6.1.0.tgz)，SHA-256 `febc9b3cbc1809c7bc12235fff92b31157521ca8177289c3864e6db17bc39400`，SRI 与模板锁相符 |
| 消费组合 | 免费模板 `2e9536872673a7ff1986a19e798c51684d16afe5`，Angular `19.2.1`，公开 `abp-ng2-module 12.1.0` |
| 工具链 | macOS 27.2.1 ARM64，Node.js `22.22.0`，Yarn Classic `1.22.22`，npm `10.9.4` |

## 实测结果

### 候选归档与包契约

| 制品 | 文件数 | 归档字节 | SHA-256 |
| --- | ---: | ---: | --- |
| 本地候选 | 42 | 26241 | `93c66026539a1c22740b893f4ff8b6213b80e5a9ccbee247c79f651e2648a126` |
| 公开对照 | 48 | 29448 | `febc9b3cbc1809c7bc12235fff92b31157521ca8177289c3864e6db17bc39400` |

候选 SRI 为 `sha512-JZrqADIH07g+AdQncWG5fByfsG6mt95A9BlG2chZoV3Zls4a06s1kgWNS6Z1t0bZwcHtyYm48jvUMcwNUzWtDg==`。公开 SRI 为 `sha512-YIifjOSbLMznza1W94HMb4zz/kAGRTHvikd2i2DLIYkyLc5El0ai/3/oVQfeIQselXUVcfy+942r6kZqcO3Rrg==`，与 registry 版本元数据及模板锁相符。[npm 版本元数据](https://registry.npmjs.org/abp-web-resources/6.1.0)

40 个框架资源的路径与原字节均贯通 Git blob、staging、候选归档及实际安装。与公开包对照，18 个资源原字节一致，其余 22 个仅有 CRLF/LF 差异。候选加入固定分发包装的两份文件。分发 `package.json` blob 为 `761c9769b3bca9150f7744cfbd936346e346ded0`，只改版本 `6.0.1` 为 `6.1.0`。分发 `LICENSE` blob 为 `b6d2fece810bbb5896733f349b7de4173ae1e251`，原字节保持一致，与公开许可文本的差异仅为换行。两份实包 manifest 解析出的字段一致。包名和版本均为 `abp-web-resources 6.1.0`，`main` 为 `Abp/Framework/scripts/abp.js`，运行依赖为空，两份实包 manifest 均没有 `types` 或 `typings`。registry 单列 `types: ./Abp/Framework/scripts/abp.d.ts`，包内路径实际存在。公开额外有 `.nuget/NuGet.Config`、`.nuget/NuGet.targets`、`README.md`、`bower.json`、`gulpfile.js`、`packages.config`。历史公开包的生产过程仍未确认。[分发 Git 提交](https://github.com/aspnetboilerplate/bower-abp-resources/commit/fb79b7d44bc9dfce0ae600c8170961f182b05e76) · [包装方案](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-web-resources/design.md#1-以框架-git-子树为资源输入)

### 冻结安装与 Production

两个隔离副本源于同一模板 Git 归档，核对 164 个源文件。以原锁生成临时锁的安装和另一个空目录、另一份空 Yarn 缓存的冻结实装均退出 `0`。原锁 SHA-256 为 `3e55c44022c5c15bf2c474eb483f8161945151261f06d00218fffbdb86c0d14f`。临时锁 SHA-256 为 `b2180a0068d31ebc8c47a39655577cf88f6e05490709bb563ba8c109bbad9849`，冻结安装前后与构建后完全相同。资源解析指向 `file:../../../packages/candidate/abp-web-resources-6.1.0.tgz`，锁内 SHA-1 `23775b92f2c6dd01b7402adcc0cbf5d2b92fa39b` 与候选实包相符。其他 1370 个锁段逐段相同。实装图核对了 1472 个根和嵌套 manifest 项及其解析边，差异仅涉及资源包来源和对应的 manifest 摘要，公开适配器的 25 个实装文件均与公开归档相符。

公开对照复用原锁、同模板、同工具的 production 冷构建，复验静态清单退出 `0`。公开实装图从适配器轮的独立公开冻结安装目录重新读取。候选以原 production 配置及 `--stats-json` 冷建，退出 `0`。两侧 Source Sans Pro 内联块均为 8665 字节、28 个规则，SHA-256 为 `21b1e561f61902ab22e99701e8e4b0ef2b2ca24a1589cdf6208c04295f80f2a9`。1193 个静态路径相同。公开历史清单在冻结 URL 之后生成，与候选原始构建相差两份 SignalR 资产及 `assets/appconfig.production.json`。候选原配置逐字节匹配模板 Git。对配置副本应用历史冻结命令所用的两个 URL 字段后，副本逐字节匹配历史冻结配置，两侧同阶段仅有两份 SignalR 资产字节差异。[公开冷构建](r5-public-angular-rebuild.md#实测结果)

按模板 `src/typings.d.ts` 的显式引用，TypeScript `5.8.2` 的实际 program 解析到已安装候选内的两份声明。

| 相对于 `node_modules/abp-web-resources/Abp/Framework` | SHA-256 |
| --- | --- |
| `scripts/abp.d.ts` | `a75f5109fd2d8b9b57693e85625a727dda859731fbeb181a53160b7d5515407e` |
| `scripts/libs/abp.signalr.d.ts` | `7bc6b940446e66593cacc8e74725b32acfd9b583516bf2c29a2bcff6c2651e92` |

同次 production 构建由以下顺序读取九个全局脚本，路径均相对隔离的模板 Angular 根目录。构建统计使用虚拟入口 `angular:script/global:scripts.js`。统计的输出文件与原 `index.html` 的 `<script src="scripts-4V6IZ3AB.js" defer>` 指向同一实物。

| 读取顺序 | 输入路径 | 字节 | SHA-256 |
| ---: | --- | ---: | --- |
| 1 | `node_modules/moment/min/moment.min.js` | 58890 | `845c524969edd5b3af9aa6d8718d29fe92e8dbe25b955214a8e064a05a9a5027` |
| 2 | `node_modules/@microsoft/signalr/dist/browser/signalr.min.js` | 47647 | `e28a720a359b37cb015758d543f908730ed5bbe478db09506bb6887f18313538` |
| 3 | `node_modules/sweetalert2/dist/sweetalert2.js` | 142284 | `1b23ca86f78a391082b323f2024e50a6815fb2c700d81a985b197d84ae718913` |
| 4 | `src/assets/freeze-ui/freeze-ui.js` | 2783 | `1ddee4fd67fb07788e0c2f63a56d1e826c0efadab789d57b19060ca0ff34f112` |
| 5 | `node_modules/push.js/bin/push.min.js` | 12894 | `4f30991c2ed5e702c881e4a3c4c700b8e9f18f8bd0ded6b95d17404130bc72ef` |
| 6 | `node_modules/abp-web-resources/Abp/Framework/scripts/abp.js` | 29412 | `16ef4dfbc69b9f0b8e4c8df2d8713f8d51be9f9e8256ccbab9867b8726e3a26b` |
| 7 | `src/assets/abp-web-resources/abp.sweet-alert.js` | 4673 | `faea20390351dd9c009b876994f537eb1973ef71524b438c903ba7003e296452` |
| 8 | `src/assets/abp-web-resources/abp.freeze-ui.js` | 465 | `28bf4cf938f723e4350bf42b9e24e9984b16b4686434468841e17feeed3c6154` |
| 9 | `node_modules/abp-web-resources/Abp/Framework/scripts/libs/abp.moment.js` | 494 | `a2da40e2412a83289ff544c1ee8d8b8b33afbdc6ee9d54f2c5e499b12e6e916d` |

### 浏览器静态验收

Chrome `158.0.8127.37` 由 Playwright `1.59.0` 启动独立上下文。回环静态服务使用本次 dist 文件，最小页引用原 production 全局脚本标签。脚本请求返回 HTTP 200，响应与产物同为 184232 字节、SHA-256 `83a95a9a94af35f1f81a86314c06e54c6033efbb6c93417548450d8fab110422`，加载期间未捕获的页面异常为零。实测 `window.abp.utils.formatString('ABP {0} / {1}', 'R5', '资源')` 返回 `ABP R5 / 资源`。全局 Moment 是 `2.30.1`，`typeof window.moment.tz` 为 `undefined`。本次覆盖 `abp.moment.js` 的构建输入及此全局组合的加载，时区转换未执行。

| 浏览器 URL | HTTP | 正文原字节 | SHA-256 |
| --- | ---: | ---: | --- |
| `/assets/abp/abp.signalr.js` | 200 | 1561，含 UTF-8 BOM | `0c3ef2330db670afe9a2b53a2c8d37442b4284b289a2af2b582a6c1b8b7f16be` |
| `/assets/abp/abp.signalr-client.js` | 200 | 4848 | `4364cacde790e61f7f7d261f6cbf1a4c380ee39acdc6f07cc273b4f1ed734fa1` |

两条响应均由浏览器 `arrayBuffer()` 取原字节，逐项匹配框架 Git、实包、实装和 `dist/browser/assets/abp/`。模板 `SignalRAspNetCoreHelper.ts` 动态使用客户端 URL。验收后关闭了本轮浏览器及回环服务。后端、数据库、应用登录、SignalR 连接、部署和 npm 发行均未执行。[固定模板 helper](https://github.com/dusdong/module-zero-core-template/blob/2e9536872673a7ff1986a19e798c51684d16afe5/angular/src/shared/helpers/SignalRAspNetCoreHelper.ts)

### 失败及回执

首次包装下载在 raw URL 等待约 60 秒后终止，`curl` 记录 `-15`。改取固定提交 Git 树中的 blob API，逐项核对 Git 对象和预检 SHA-256 后制包成功。首次公开对照回读仍假设历史解包目录存在，遇到文件缺失。改从已登记的工具链归档读取 Node 和 Yarn 成员并核对当前可执行文件，复验通过。首次浏览器最小页遗漏 `</script>`，脚本请求返回 200 但探针读不到 `window.abp`。补齐结束标签，从新上下文复跑，脚本及两个资产检查全部通过。

本轮私有证据根目录为 `.git/plan-r5-web-resources/implementation/`。 `packages/input.json` 和 `packages/comparison.json` 保存固定输入及双包逐项记录。 `lock/`、`frozen/` 保留命令、cwd、退出码、锁与安装图，`frozen/global-reads.jsonl`、`frozen/build-result.json` 关联实际读取、构建统计与 dist，`browser/smoke-result.json` 及 `browser/received-*` 保存浏览器回执与字节。 `packages-first-attempt/`、`frozen/accept-install-first.log` 和 `browser/first-attempt/` 保存首次尝试。常规复验包括 Python `3.12.14` 与 `3.14.7` 各 85 项回归、定向和全仓 OpenSpec 严格校验、归档任务严格校验、链接与差异检查。文档的制包命令独立复跑得到同一候选摘要。

## 从普通克隆复跑

在主仓根目录使用已包含两个固定 Git 对象的框架和模板子模块。按上表准备固定版本的 Node.js、npm、Yarn Classic，用 `node -p 'process.version + " " + process.platform + "/" + process.arch'`、`npm --version` 和 `yarn --no-default-rc --version` 检查。以下命令假设三者已在 PATH 中，并使用 Python 3 和 Bash。公开对照可按既有入口另建，核对锁、工具、模板输入与构建阶段。下文中的公开产物比较按未冻结 URL 的原始 production 层理解，历史报告中的冻结配置单独比较。[公开对照复跑](r5-public-angular-rebuild.md#准备和离线核验)

### 制包与归档对照

```bash
set -euo pipefail
repo=$(pwd -P)
work=$(mktemp -d "${TMPDIR:-/tmp}/du-web-resources.XXXXXX")
mkdir -p "$work/staging" "$work/packages/candidate" "$work/packages/public" "$work/pack-cache"
framework=7933e71f5646d2447af3502ecbea9a3f1aba8184
tree=780977463dbf0eb599765ff553000a631a70b35d
template=2e9536872673a7ff1986a19e798c51684d16afe5
test "$(git -C aspnetboilerplate rev-parse "$framework:src/Abp.Web.Resources/Abp/Framework")" = "$tree"
blob_api=https://api.github.com/repos/aspnetboilerplate/bower-abp-resources/git/blobs
wrapper_files=(package.json LICENSE)
wrapper_blobs=(761c9769b3bca9150f7744cfbd936346e346ded0 b6d2fece810bbb5896733f349b7de4173ae1e251)
for i in 0 1; do
  curl -fsSL "$blob_api/${wrapper_blobs[$i]}" -o "$work/${wrapper_files[$i]}.blob.json"
done
curl -fsSL https://registry.npmjs.org/abp-web-resources/6.1.0 -o "$work/packages/public/registry.json"
curl -fsSL https://registry.npmjs.org/abp-web-resources/-/abp-web-resources-6.1.0.tgz \
  -o "$work/packages/public/abp-web-resources-6.1.0.tgz"
python3 - "$repo/aspnetboilerplate" "$tree" "$work" <<'PY'
from pathlib import Path
import base64, hashlib, json, re, subprocess, sys

repo, tree, work_path = sys.argv[1:]
work = Path(work_path)
staging = work / 'staging'
entries = subprocess.check_output(['git','ls-tree','-rz',tree], cwd=repo).split(b'\0')[:-1]
assert len(entries) == 40
for entry in entries:
    header, path = entry.decode().split('\t', 1)
    mode, kind, blob = header.split()
    assert mode == '100644' and kind == 'blob'
    target = staging / 'Abp/Framework' / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(subprocess.check_output(['git','cat-file','blob',blob], cwd=repo))
for name, sha in [
    ('package.json','07ad30f9fbc9b9fb79fbd7ff9f3e2b0d29f7f0475fd12d0867fe2d79f405fdf5'),
    ('LICENSE','cdca8e1cd2ec89468af979ce118aa2123ace139c76174fe6a8e30192bba1adc0'),
]:
    entry = json.loads((work / f'{name}.blob.json').read_text())
    data = base64.b64decode(entry['content'])
    assert hashlib.sha256(data).hexdigest() == sha
    assert hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest() == entry['sha']
    if name == 'package.json':
        data, count = re.subn(rb'("version"\s*:\s*")6\.0\.1(")', rb'\g<1>6.1.0\2', data)
        assert count == 1
    (staging / name).write_bytes(data)
PY
(cd "$work/staging" && npm pack --cache "$work/pack-cache" --json \
  --pack-destination "$work/packages/candidate") > "$work/pack.json"
shasum -a 256 "$work"/packages/{public,candidate}/abp-web-resources-6.1.0.tgz
```

用 `tar -tzf` 核对两包完整路径。将各 tarball 分别解到独立目录后，按相对路径比较 `package/Abp/Framework`，用 `cmp` 或 SHA-256 对照候选和 staging，并对公开侧同时记下原字节和仅 CRLF→LF 后的比较结果。对照 `package/package.json`、`LICENSE` 及 registry 元数据中的 `types`。候选的归档 SRI 可用 `openssl dgst -sha512 -binary` 后接 `openssl base64 -A` 计算，与 `pack.json` 核对。公开 SRI 还须与固定模板锁的资源行相同。

### 冻结安装

```bash
for stage in lock frozen; do
  mkdir -p "$work/$stage"/{source,home,tmp,yarn-cache}
  git -C "$repo/module-zero-core-template" archive --format=tar "$template" angular \
    > "$work/$stage/source.tar"
  tar -xf "$work/$stage/source.tar" -C "$work/$stage/source"
  python3 - "$work/$stage/source/angular/package.json" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
before = path.read_bytes()
old = b'"abp-web-resources": "^6.1.0"'
new = b'"abp-web-resources": "file:../../../packages/candidate/abp-web-resources-6.1.0.tgz"'
assert before.count(old) == 1
path.write_bytes(before.replace(old, new))
PY
done
run_yarn() (
  stage=$1
  shift
  cd "$work/$stage/source/angular"
  env -i PATH="$PATH" HOME="$work/$stage/home" TMPDIR="$work/$stage/tmp" \
    YARN_IGNORE_PATH=1 yarn --no-default-rc "$@"
)
run_yarn lock install --non-interactive --no-progress --cache-folder "$work/lock/yarn-cache"
cp "$work/lock/source/angular/yarn.lock" "$work/frozen/source/angular/yarn.lock"
run_yarn frozen install --non-interactive --no-progress --cache-folder "$work/frozen/yarn-cache" --frozen-lockfile
cmp "$work/lock/source/angular/yarn.lock" "$work/frozen/source/angular/yarn.lock"
git -C "$repo/module-zero-core-template" show "$template:angular/yarn.lock" > "$work/original.lock"
diff -u "$work/original.lock" "$work/frozen/source/angular/yarn.lock" || test "$?" -eq 1
```

对照锁差异后，比较候选归档与 `node_modules/abp-web-resources` 全部文件。公开模板以原锁另装到空目录和空缓存。对比两份实装中根与嵌套的 `node_modules/**/package.json` 路径、版本、manifest 摘要和按各请求包位置解析的依赖边。记录根 manifest 的资源选择器与目标资源自身的已知差异。候选中 `abp-ng2-module` 实装须与公开实包逐项一致。

### Production 与浏览器

在冻结目录下从固定 `src/tsconfig.json` 创建 TypeScript program，核对 `getSourceFile` 里 `src/typings.d.ts` 引用的两份声明均来自已安装包，并记录实际文件摘要。生产构建使用 `yarn --no-default-rc ng build --configuration production --stats-json`。事先确认 `dist` 和 `.angular/cache` 均不存在，构建后复核锁。为验证同次读取，可将以下观测放进隔离目录的 `observe.cjs`，只应用于该构建进程。观测记录同一真实读取的原始 Buffer，并向构建器返回原 UTF-8 解码。

```javascript
const fs = require('node:fs');
const files = require('node:fs/promises');
const crypto = require('node:crypto');
const path = require('node:path');
const read = files.readFile;
files.readFile = async function (file, encoding, ...rest) {
  const caller = new Error().stack.split('\n')[2];
  if (encoding !== 'utf-8' || !caller.includes('/tools/esbuild/global-scripts.js:')) {
    return read.call(this, file, encoding, ...rest);
  }
  const bytes = await read.call(this, file, undefined, ...rest);
  const cwd = process.cwd();
  const realpath = fs.realpathSync(file);
  fs.appendFileSync(process.env.ABP_GLOBAL_READS, JSON.stringify({
    pid: process.pid, cwd, path: path.relative(cwd, file), realpath,
    file: realpath, bytes: bytes.length,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex'), caller
  }) + '\n');
  return bytes.toString('utf-8');
};
```

```bash
(
  cd "$work/frozen/source/angular"
  env -i PATH="$PATH" HOME="$work/frozen/home" TMPDIR="$work/frozen/tmp" YARN_IGNORE_PATH=1 \
    ABP_GLOBAL_READS="$work/global-reads.jsonl" NODE_OPTIONS="--require \"$work/observe.cjs\"" \
    yarn --no-default-rc ng build --configuration production --stats-json
)
cmp "$work/lock/source/angular/yarn.lock" "$work/frozen/source/angular/yarn.lock"
```

按 `global-reads.jsonl` 的真实顺序逐项对照 `angular.json` 与输入文件原字节。在 `dist/stats.json` 中定位 `entryPoint` 为 `angular:script/global:scripts.js` 的产物，再核对 `dist/browser/index.html` 的实际全局脚本标签及对应文件摘要。用只引用该原始标签的最小 HTML（保留结束标签 `</script>`）和 `dist/browser` 文件启动回环静态服务，例如从该输出目录运行 `python3 -m http.server 8765 --bind 127.0.0.1`。在独立浏览器上下文保留加载期间的页面异常，取得该脚本网络响应原字节，与产物比较。在最小页面的开发者工具控制台执行完整代码块，核对通过提示。保留两份原字节响应并用候选归档、实装和实际文件交叉核对。完成后关闭浏览器上下文与该静态服务。

```javascript
const result = window.abp.utils.formatString('ABP {0} / {1}', 'R5', '资源');
if (result !== 'ABP R5 / 资源') {
  throw new Error('formatString 应返回 ABP R5 / 资源，实际返回 ' + String(result));
}

const expectedHashes = {
  '/assets/abp/abp.signalr.js': '0c3ef2330db670afe9a2b53a2c8d37442b4284b289a2af2b582a6c1b8b7f16be',
  '/assets/abp/abp.signalr-client.js': '4364cacde790e61f7f7d261f6cbf1a4c380ee39acdc6f07cc273b4f1ed734fa1',
};
for (const [path, expectedHash] of Object.entries(expectedHashes)) {
  const response = await fetch(path, {cache: 'no-store'});
  if (response.status !== 200) {
    throw new Error(path + ' 应返回 HTTP 200，实际为 ' + response.status);
  }
  const bytes = await response.arrayBuffer();
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  const actualHash = Array.from(new Uint8Array(hash), x => x.toString(16).padStart(2, '0')).join('');
  if (actualHash !== expectedHash) {
    throw new Error(path + ' 的 SHA-256 应为 ' + expectedHash + '，实际为 ' + actualHash);
  }
}
console.info('浏览器验收通过，formatString 和两份 SignalR 静态资源均符合预期。');
```
