# R5 Angular 19 双候选实包消费

2026-11-28，固定免费模板同时冻结安装两份本地候选，在 macOS ARM64 完成 Angular production 新构建。同阶段浏览器目录的 1193 个文件逐路径、逐字节匹配仅换资源的对照。限定的静态观察由本轮产物在独立 Chrome 上下文重新执行。验收要求已同步到稳定规范，六项任务已归档。验证范围为该模板的实包消费、产物比较和最小页观察。后端、数据库、登录、角色编辑、SignalR 握手、其他平台及 npm 发行均未执行。[验收设计](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-package-pair/design.md) · [稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-固定-angular-19-模板可同时验收两份本地-npm-候选) · [归档任务](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-package-pair/tasks.md)

## 固定输入

- 免费模板 `2e9536872673a7ff1986a19e798c51684d16afe5`，原锁 SHA-256 为 `3e55c44022c5c15bf2c474eb483f8161945151261f06d00218fffbdb86c0d14f`。完整 Angular Git 导出包含 164 个文件，与对照逐项匹配。
- macOS `27.2.1`（`26B131`）ARM64，Node.js `22.22.0`、Yarn Classic `1.22.22`、npm `10.9.4`。实装 Angular core、CLI 与 application builder 均为 `19.2.1`，TypeScript 为 `5.8.2`。核对三个可执行文件和对应构建工具文件的摘要。
- 使用两份归档的只读副本。适配器来自 `a8ca4b37800565357f201e83d19333a9a7008887`，资源来自框架 `7933e71f5646d2447af3502ecbea9a3f1aba8184` 的 40 个 Git 原字节文件，包装取自 `fb79b7d44bc9dfce0ae600c8170961f182b05e76`。两份归档均复算 SHA-256、SHA-512 SRI 和完整文件清单。[适配器原实测](r5-angular19-adapter-package-plan.md#实测结果) · [资源原实测](r5-angular19-web-resources-plan.md#实测结果)

| 归档 | 文件数 | SHA-256 | SHA-512 SRI |
| --- | ---: | --- | --- |
| `abp-ng2-module-12.1.0.tgz` | 25 | `b8939f43e0c05afafcbfb8371c99646006565dc4a613698fd39b6c6b4aa3a2bd` | `sha512-9zbkwFe/wILuSlxIRxJm6CTX0NIDACF574PwBjm161KN4EFaJD0W9CyJsFNqPbsCrhupS6C7qHfRJ3QTmi2TXQ==` |
| `abp-web-resources-6.1.0.tgz` | 42 | `93c66026539a1c22740b893f4ff8b6213b80e5a9ccbee247c79f651e2648a126` | `sha512-JZrqADIH07g+AdQncWG5fByfsG6mt95A9BlG2chZoV3Zls4a06s1kgWNS6Z1t0bZwcHtyYm48jvUMcwNUzWtDg==` |

## 实测结果

| 阶段 | 状态 | 结果与回执 |
| --- | --- | --- |
| 输入与对照 | 通过 | 两份封存归档及逐项文件核对通过。仅换资源对照使用同一资源候选和原锁 SRI 所指的公开适配器。复核了对照的实际实装、构建回执和原始浏览器目录。 |
| 临时锁和冻结实装 | 通过 | `yarn --no-default-rc install --non-interactive` 生成临时锁。另一 Git 导出用独立空缓存加 `--frozen-lockfile` 实际安装。两次退出码均为 `0`，完整日志及各自缓存、目录与 argv 见 `lock/install-input.json`、`frozen/install-input.json` 和同目录的 `install.json`。 |
| 同次 production 构建 | 通过 | 原模板 `yarn --no-default-rc ng build --configuration production --stats-json` 在无 `dist` 和 Angular 缓存的冻结实装目录退出 `0`。构建及 TypeScript 解析的原回执见 `frozen/build.json`、`frozen/*-declarations.json`。 |
| 完整产物对照 | 通过 | 同为未改应用配置的原始 production 阶段。1193 个文件的集合及原字节逐项一致，目录集合一致，无新增、缺失或字节差异。两份完整清单和比较在 `frozen/dist-*.json`。 |
| 最小页静态观察 | 通过 | 本轮 Chrome `158.0.8127.37`，三个 HTTP 200、三个响应正文精确匹配、`formatString` 返回 `ABP R5 / 资源`，页面未捕获异常为 0。回执和响应正文在 `browser/`。 |

### 冻结锁与同次来源

冻结安装前、安装后和构建后临时锁的 SHA-256 均为 `7de1c23211a5e91ff9c337102feba00905192fe74735a1150ddbaf62418fd096`。两条 `file:` 的锁定位分别包含归档 SHA-1 `e7f2c37f8604742720f58484fb51b018291f08db` 与 `23775b92f2c6dd01b7402adcc0cbf5d2b92fa39b`。Yarn 为这两条本地记录写入了 `resolved` 片段，两份独立复算的 SRI 见上表。包的真实安装路径及完整实装字节与归档逐项一致。展开后 1673 个非目标锁选择器与原锁和资源单包对照一致。对照和本轮实际读取 1472 份 manifest（含根项目）和 14590 条声明的解析结果，根的两条 `file:` 定位按本轮目录改变，其他记录一致。适配器解析 `tslib 2.8.1` 和 Angular `common/core 19.2.1`，资源仍由模板直接装入。既有 peer 警告和 production 的 CommonJS 警告保留在日志中。

- `src/main.ts` 的 `AbpHttpInterceptor` 对应已装适配器 `index.d.ts`，`src/typings.d.ts` 的显式引用对应已装资源 `abp.d.ts` 与 `abp.signalr.d.ts`。三份路径和摘要均见同次解析回执。
- 适配器 `fesm2022/abp-ng2-module.mjs` 匹配归档，SHA-256 为 `ba8cbe2796be3dd058029d8c70041881054d5b3551db68698ed254b9fc1662ec`。同次 stats 记录它对 `chunk-N46DCMOX.js` 贡献 8985 字节。该文件原字节 SHA-256 为 `1c93d0ac4d0337ff2cccb659140cb73e762c662ee90c9f3f1baa8e7e61363fa0`。
- 构建器实际读入九个全局脚本，顺序与 `angular.json` 及对照一致。资源候选的 `abp.js`、`abp.moment.js` 以及模板的 SweetAlert 和 Freeze UI 适配均按原字节核对。构建入口 `angular:script/global:scripts.js` 生成 `scripts-4V6IZ3AB.js`，由原始 `index.html` 中的 `<script src="scripts-4V6IZ3AB.js" defer>` 引用。
- 两份 SignalR 静态资产均匹配框架 Git、归档和实装，`abp.signalr.js` 保留 `EF BB BF`。完整字节链见 `frozen/build-result.json`，实际读取见 `frozen/global-reads.jsonl`。

### 同阶段字体及配置

两侧的 `assets/appconfig.production.json` 均匹配模板 Git 原件，SHA-256 为 `83ecc8366c445fd0b30404a739bc4aae114b541c73bba9361c7c2af82f7847ce`，未做冻结 URL 或服务地址改写。双包构建实际读取 `https://fonts.googleapis.com/css?family=Source+Sans+Pro:300,400,400i,700`，HTTP `200`，样式表 9737 字节，SHA-256 为 `4566eaeb829016da024f7eaf4292c589c0720669a43d3689d9801e6aec62657a`。按该版 Angular 的内联处理转换后匹配原 HTML 内的实际字节。两侧内联块各有 8665 字节、28 条 `@font-face`，SHA-256 同为 `21b1e561f61902ab22e99701e8e4b0ef2b2ca24a1589cdf6208c04295f80f2a9`。历史对照保留固定 URL 和内联结果，本轮另存了实际网络响应与两份 HTML 内联块。

### 本轮浏览器响应

| 路径 | HTTP | 浏览器实收 SHA-256 |
| --- | ---: | --- |
| `/scripts-4V6IZ3AB.js` | 200 | `83a95a9a94af35f1f81a86314c06e54c6033efbb6c93417548450d8fab110422` |
| `/assets/abp/abp.signalr.js` | 200 | `0c3ef2330db670afe9a2b53a2c8d37442b4284b289a2af2b582a6c1b8b7f16be` |
| `/assets/abp/abp.signalr-client.js` | 200 | `4364cacde790e61f7f7d261f6cbf1a4c380ee39acdc6f07cc273b4f1ed734fa1` |

回环静态服务仅开放最小页、实际全局脚本和两条静态资源。最小页沿用本轮 HTML 的脚本标签。对照原最小页及三个历史正文与本轮实物也逐字节相同，当前浏览器结论引用本轮重新取得的响应和异常记录。

### 原始证据及边界

验收机证据根为 `.git/plan-r5-angular19-pair/implementation/`。归档副本及逐文件清单在 `inputs/` 和 `archives.json`。构建、比较及实际安装保留在 `frozen/`，包括 `source/angular/node_modules/`、`source/angular/dist/stats.json` 及完整浏览器目录。两次安装和构建均使用实际在线输入，原始回执记录 argv、工作目录及退出码。正式 Yarn 和 Angular 阶段均退出 `0`。工具版本回执初命名为 `yarn.json`，Yarn 扫描祖先工作区时将它读作 manifest 并给出缺许可证警告。该回执没有工作区或依赖声明，已改用 `yarn-version.json`，实际冻结锁、实装图和构建产物均经对照核实。包装版本及 stats 原输入大小的辅助回读也曾修正，首次错误与后续结果均已留存。候选文件及关键证据有独立 SHA-256 清单。

V7 仍使用登记的公开冻结前端。共用离线入口验证了公开清单和实物，返回 `0`，同时拒绝了携带公开清单的独立双包产物副本，返回 `1`。相关定向 Python 测试 11 项通过。公开角色编辑的业务实测继续查阅 V7 记录。[V7 原冻结与角色编辑证据](r5-angular-user-role-edit.md) · [公开重建与离线核验](r5-public-angular-rebuild.md#准备和离线核验)

## 从普通克隆复跑

在主仓根目录打开 Bash，准备上述工具版本和固定 Git 对象。按两个单包指南制包，将候选文件的绝对路径分别设置为 `ADAPTER_TGZ`、`RESOURCES_TGZ`，将已核验的 Node.js、Yarn Classic 可执行文件的绝对路径设置为 `NODE22`、`YARN1`。先核对实际版本、归档 SHA-256、SHA-512 SRI 和逐文件原字节。如重新打包的摘要不同，逐项与封存清单核对，按设计登记实际归档身份后再安装。[适配器制包](r5-angular19-adapter-package-plan.md#从普通克隆复跑) · [资源制包](r5-angular19-web-resources-plan.md#制包与归档对照) · [输入验收设计](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-package-pair/design.md#1-核对已有实包及可比对照)

下列命令可在 macOS 自带的 Bash 3.2 执行，分别建立仅换资源对照和双包候选。每组从模板原锁生成临时锁，然后从另一份 Git 导出和独立空缓存冻结复装。在运行前将资源单包指南的脚本读取观测另存为 `OBSERVE_CJS` 指向的绝对路径。保留两组原始 production 产物及执行日志。在该观测文件末尾追加以下代码以保留 Angular 实际获取的字体响应。[脚本读取观测](r5-angular19-web-resources-plan.md#production-与浏览器)

```javascript
{
  const fetchCss = require('node:https');
  const output = require('node:fs');
  const get = fetchCss.get;
  fetchCss.get = function (url, options, done) {
    if (!(url instanceof URL) || url.hostname !== 'fonts.googleapis.com') return get.apply(this, arguments);
    return get.call(this, url, options, response => {
      const chunks = [];
      response.on('data', bytes => chunks.push(bytes));
      response.on('end', () => {
        const base = process.env.R5_FONT_CAPTURE;
        output.writeFileSync(base + '.css', Buffer.concat(chunks), {flag: 'wx'});
        output.writeFileSync(base + '.json', JSON.stringify({url: url.href, status: response.statusCode,
          userAgent: options.headers['user-agent']}), {flag: 'wx'});
      });
      done(response);
    });
  };
}
```

```bash
set -euo pipefail
repo=$PWD
work=$(mktemp -d "${TMPDIR:-/tmp}/r5-angular-pair.XXXXXXXX")
template=2e9536872673a7ff1986a19e798c51684d16afe5
mkdir "$work/inputs"
cp "$ADAPTER_TGZ" "$work/inputs/abp-ng2-module-12.1.0.tgz"
cp "$RESOURCES_TGZ" "$work/inputs/abp-web-resources-6.1.0.tgz"
chmod a-w "$work/inputs/"*.tgz
shasum -a 256 "$work/inputs/"*.tgz
shasum -a 512 "$work/inputs/"*.tgz

isolated() {
  local stage=$1
  shift
  env -i PATH="$(dirname "$NODE22"):/usr/bin:/bin:/usr/sbin:/sbin" \
    HOME="$work/$stage/home" TMPDIR="$work/$stage/tmp" YARN_IGNORE_PATH=1 \
    npm_config_cache="$work/$stage/npm-cache" \
    npm_config_userconfig="$work/$stage/home/.npmrc" \
    npm_config_globalconfig="$work/$stage/home/npm-globalrc" "$@"
}

require_absent() {
  local path
  for path in "$@"; do
    if [[ -e "$path" || -L "$path" ]]; then
      printf '预期路径不存在，实际已存在 %s\n' "$path" >&2
      return 1
    fi
  done
}

for combination in resources pair; do
  for phase in seed frozen; do
    stage="$combination-$phase"
    require_absent "$work/$stage"
    mkdir -p "$work/$stage/"{source,home,tmp,yarn-cache,npm-cache}
    git -C "$repo/module-zero-core-template" archive "$template" angular |
      tar -x -C "$work/$stage/source"
    (
      cd "$work/$stage/source/angular"
      require_absent node_modules dist .angular
      printf '%s  %s\n' \
        '3e55c44022c5c15bf2c474eb483f8161945151261f06d00218fffbdb86c0d14f' yarn.lock |
        shasum -a 256 -c
      "$NODE22" --input-type=commonjs - "$combination" <<'JS'
const fs = require('node:fs');
let manifest = fs.readFileSync('package.json', 'utf8');
const replacements = [['abp-web-resources', '^6.1.0', '6.1.0']];
if (process.argv[2] === 'pair') replacements.push(['abp-ng2-module', '12.1.0', '12.1.0']);
for (const [name, original, version] of replacements) {
    const key = `"${name}": "${original}"`;
    if (manifest.split(key).length !== 2) throw Error('模板声明失配 ' + name);
    manifest = manifest.replace(key, `"${name}": "file:../../../inputs/${name}-${version}.tgz"`);
}
fs.writeFileSync('package.json', manifest);
JS
      set -- --no-default-rc install --non-interactive --no-progress \
        --cache-folder "$work/$stage/yarn-cache"
      if [[ "$phase" == frozen ]]; then
        cp "$work/$combination-seed/source/angular/yarn.lock" yarn.lock
        set -- "$@" --frozen-lockfile
      fi
      cp yarn.lock "$work/$stage/before-install.yarn.lock"
      isolated "$stage" "$YARN1" "$@" >"$work/$stage/install.log" 2>&1
      cp yarn.lock "$work/$stage/after-install.yarn.lock"
      if [[ "$phase" == frozen ]]; then
        cmp "$work/$stage/before-install.yarn.lock" yarn.lock
        require_absent dist .angular
        isolated "$stage" env ABP_GLOBAL_READS="$work/$stage/global-reads.jsonl" \
          R5_FONT_CAPTURE="$work/$stage/font-response" \
          NODE_OPTIONS="--require \"$OBSERVE_CJS\"" \
          "$YARN1" --no-default-rc ng build --configuration production --stats-json \
          >"$work/$stage/build.log" 2>&1
        cmp "$work/$stage/after-install.yarn.lock" yarn.lock
      fi
    )
  done
done
printf '%s\n' "$work"
```

执行结束后，用两套冻结目录的锁与实装按双包设计核对全部非目标选择器及实际解析图。候选包要逐文件与归档核对，并用同次构建的 TypeScript 解析结果、九条脚本读取、`dist/stats.json`、`index.html` 和资产建立来源链。比较两侧原始 `dist/browser/` 的全部路径与字节，用模板 Git 原件核对应用配置，记录生产构建中实际收到的 Source Sans Pro 样式表 URL、状态与正文，并核对各自原 HTML 内联块摘要及规则数。从本轮双包目录按资源单包指南重跑最小页。保留全局脚本和两份 SignalR 资产的三份实际响应正文，用 `cmp` 与产物逐项核对，保存 HTTP 状态、函数返回和页面异常记录。[完整比较及静态判定](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-package-pair/design.md#4-比较完整产物并决定静态浏览器证据来源) · [静态浏览器复跑](r5-angular19-web-resources-plan.md#production-与浏览器)
