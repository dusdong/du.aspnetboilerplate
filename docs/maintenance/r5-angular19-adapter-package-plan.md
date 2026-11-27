# R5 Angular 19 适配器源码制包与模板消费

在 macOS ARM64 上，npm 发布参考提交 `afbd23e` 的根锁冻结安装失败。同一库源码从后续提交 `a8ca4b3` 成功制成 `abp-ng2-module 12.1.0` 本地包。固定 Angular `19.2.1` 免费模板完成候选包的 production 编译，构建统计确认候选 FESM 进入浏览器 JS。适配器验收的五项任务已归档，验收要求已同步到稳定规范。[实测结果](#实测结果) · [从普通克隆复跑](#从普通克隆复跑) · [OpenSpec 提案](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-adapter-package/proposal.md) · [设计](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-adapter-package/design.md) · [稳定规范](../../openspec/specs/template-maintenance-package-consumption/spec.md#requirement-固定-angular-19-模板可验收源码制成的适配器包) · [归档任务](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-adapter-package/tasks.md)

## 上轮交付复审

2026-11-27 回读 GitHub `main` 的 `b2d2da65e0ce0fce6d55c27a16ac1375ed97b60a`，上轮 14 个文件与提交对象一致，`verify-r0` 成功。原变更 7/7 任务已归档，稳定规范增量为 1 项要求、7 个场景。Python `3.12.14`、`3.14.7` 回归各 85 项通过，原基线的全仓严格校验 15/15、归档检查 27/27。[交付提交](https://github.com/dusdong/du.aspnetboilerplate/commit/b2d2da65e0ce0fce6d55c27a16ac1375ed97b60a) · [GitHub Actions 运行](https://github.com/dusdong/du.aspnetboilerplate/actions/runs/46017922338) · [归档任务](../../openspec/changes/archive/2026-11-27-prepare-r5-public-angular-rebuild/tasks.md)

离线复核逐套读取首次冷构建及四套构建后回放，每套核对 1193 个静态文件与对应清单。冻结、移除字体块、末尾加空格及非法 UTF-8 四份回放退出 `0 / 1 / 1 / 1`，三个反例各只有 `index.html` 偏离冻结清单。首次实建使用公开模板、公开 npm 包和初版脚本。修订后的脚本（SHA-256 前缀 `b2aa4a2e`）由构建后回放验证。两侧各三次页面角色保存沿用 V7 业务实测。本次复审使用留存报告和实物，适配器源码制包进入下一轮任务。[冷构建实测](r5-public-angular-rebuild.md#实测结果) · [字体修订实测](r5-public-angular-rebuild.md#字体诊断修正实测) · [角色编辑业务证据](r5-angular-user-role-edit.md#分步结果)

## 固定输入

| 输入 | 固定身份与已核对的事实 |
| --- | --- |
| 免费模板 | `2e9536872673a7ff1986a19e798c51684d16afe5`。`angular/yarn.lock` 的 SHA-256 为 `3e55c44022c5c15bf2c474eb483f8161945151261f06d00218fffbdb86c0d14f`，解析到 Angular `19.2.1`、`abp-ng2-module 12.1.0` 与 `abp-web-resources 6.1.0`。[模板锁](https://github.com/dusdong/module-zero-core-template/blob/2e9536872673a7ff1986a19e798c51684d16afe5/angular/yarn.lock) |
| 已公开 `abp-ng2-module 12.1.0` | 2026-11-27 从 npm registry 读回，元数据 `gitHead` 为 `afbd23ea9711e9d94259d0f0b6afcbab9a0617fc`。tarball 为 14751 字节、25 个文件，SHA-512 与模板锁一致。包内 Angular common/core peer 均为 `^19.1.7`，主导出含 `types` → `./index.d.ts` 与 `default` → `./fesm2022/abp-ng2-module.mjs`。该 FESM 的 Angular 部分编译声明记录的编译器版本为 `19.1.7`，供候选比较。[版本元数据](https://registry.npmjs.org/abp-ng2-module/12.1.0) · [公开实包](https://registry.npmjs.org/abp-ng2-module/-/abp-ng2-module-12.1.0.tgz) |
| 首次制包输入 | `afbd23ea9711e9d94259d0f0b6afcbab9a0617fc`，根锁 SHA-256 `a5f5ad1fb5398f794632cb6c8a02ae2f5bb9aaa0dde6b266802778febe91f4b2`。按根 `package.json` 的包名和声明范围逐项查根锁，33 个直接依赖选择器中有 24 个缺少对应条目（`dependencies` 12/12 缺失，`devDependencies` 12/21 缺失），包括 `@angular/core@~19.1.7`、`@angular/cli@~19.1.8` 和 `ng-packagr@^19.1.2`。冻结安装结果以实跑为准。[发布参考提交](https://github.com/aspnetboilerplate/abp-ng2-module/commit/afbd23ea9711e9d94259d0f0b6afcbab9a0617fc) |
| 可独立试验的后续锁 | `a8ca4b37800565357f201e83d19333a9a7008887` 直接接续上一个提交，仅改 `README.MD` 与根 `yarn.lock`。两套 `projects/abp-ng2-module/src` 树对象均为 `3fa781c9f5bf27cf0063a53fd0a43ba88079b585`。后续根锁 SHA-256 `079f1ab5293ce20975d8acf2370b820fafd7aa6e8ee829a437bcddd8fa6ed7da`，覆盖相同的 33/33 个直接依赖选择器。结果按此提交独立登记。[后续锁提交](https://github.com/aspnetboilerplate/abp-ng2-module/commit/a8ca4b37800565357f201e83d19333a9a7008887) |

主仓适配器 gitlink `24adbe2222c0965c3957cc6b45a59f8eb1dd6001` 属于 `13.0.0` / Angular 21。Angular 19 试验通过 Git 对象导出到新目录，构建和模板安装各用独立目录、锁及缓存。候选从库 production 输出 `dist/abp-ng2-module` 执行 `npm pack`，记录归档与包内每个文件的摘要。[主仓基线登记](release-baseline.json) · [制包设计](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-adapter-package/design.md#decisions)

## 对照和验收判断

1. **公开包对照。** 复用上轮成功的 production 编译需核对同一模板 Git 对象、锁及公开 tarball 完整性、实装版本、构建工具与配置、成功日志和冻结产物。上轮记录缺少本次依赖对照所需的安装实物或信息时，在独立目录按原锁补一次冻结安装核对。工具、源码或编译配置无法确认可比时，才在与候选相同的条件下重跑公开 production 编译。角色页面和 SQL 仍引用各自的历史验收。[公开冷构建](r5-public-angular-rebuild.md#实测结果)
2. **候选包验收。** 模板副本只把 `abp-ng2-module` 指向本轮 tarball。确认非适配器的锁与实际解析图等价，检查归档完整性及 `node_modules` 中候选包的逐文件摘要。用模板的 TypeScript 解析记录确认 `src/main.ts` 导入 `AbpHttpInterceptor` 时使用候选 `index.d.ts`。用 production 构建统计或等效证据指出候选 FESM 的代码进入了哪个新生成的浏览器 JS 文件。[对照设计](../../openspec/changes/archive/2026-11-28-validate-r5-angular19-adapter-package/design.md#decisions)
3. **结论。** 若 `afbd23e` 冻结安装失败，而 `a8ca4b3` 成功制包并通过模板消费验收，分别登记原锁安装失败、后续提交制包通过、模板消费后续候选通过。归档、包内文件、应用 bundle 和实际存在的 source map 的字节差异另记。若比较整个浏览器输出目录，两侧的 `assets/appconfig.production.json` 须取相同处理阶段，上轮清单使用写入冻结 URL 后的文件。只有候选来源、其余输入的可比性和新编译均有证据时，才可确认该组合的编译消费兼容。缺项时标为待定，保留实际命令、阶段、退出码和原始日志。运行行为需有相应实测。[冻结配置步骤](../../eng/r5_angular_prepare.py)

## 仓库分工

主仓维护固定输入、跨仓模板消费验收、结果与兼容指南。后续若实测表明需要修订适配器 README、构建配置或组件内测试，应在 `abp-ng2-module` 对应 Angular 19 维护线另行定范围。若涉及模板源码的持久化修订，归模板子仓。当前规划仅涵盖临时导出、打包与消费，持久化分支、gitlink、包身份、上游修改和发布按各自交付授权处理。[子模块分工](../README.md#子模块分工)

## 实测结果

2026-11-28，在 macOS `27.2.1`（`26B131`）ARM64 使用 Node.js `22.22.0`、Yarn Classic `1.22.22`、npm `10.9.4`。工具来自官方归档并校验完整性。各次安装隔离 HOME、临时目录和下载缓存，从无 `node_modules`、`dist` 和 `.angular/cache` 的 Git 导出目录起步。[Node.js 发行归档](https://nodejs.org/dist/v22.22.0/) · [Yarn Classic 包](https://registry.npmjs.org/yarn/1.22.22)

| 参考提交 | 根锁冻结安装 | 库 production 构建 | 本地 npm 制包 |
| --- | --- | --- | --- |
| `afbd23e`，发布参考 | 退出 `1`。Yarn 在解析阶段报告 `Your lockfile needs to be updated`，33 个直接选择器缺 24 个，锁摘要未变。 | 未执行 | 未执行 |
| `a8ca4b3`，相同库源码与后续根锁 | 退出 `0`，33 个直接选择器齐全。安装、构建和制包后锁摘要均等于[固定输入](#固定输入)登记值。 | 退出 `0`，Ivy 部分编译 | 退出 `0`，从 `dist/abp-ng2-module` 生成归档 |

`a8ca4b3` 实装 Angular core/compiler-cli `19.1.7`、CLI 与 `@angular-devkit/build-angular` `19.1.8`、`@angular-devkit/build-ng-packagr` `0.1002.0`、`ng-packagr` `19.1.2`、TypeScript `5.7.3`、RxJS `7.8.2`、`tslib` `2.8.1`、资源包 `6.1.0`。安装日志保留旧构建插件要求 `ng-packagr ^10.0.0` 以及 codelyzer 的 Angular peer 等警告。

| 包归档 | 字节数 | SHA-256 | SHA-512 SRI |
| --- | ---: | --- | --- |
| npm 公开 `12.1.0` | 14751 | `f41d5dcfaa09101c8b616f38726a4b11a844d9990f03994e3bd75c9a3c159684` | `sha512-be8ZJI/7/S+Ur3lQTnIAcA2efZJ9a5f4ZAp/m8HsbJQ75DeMuuiS+K1/56pcW9A8C2GCNYyi1cHjVKqCeGOodQ==` |
| `a8ca4b3` 本地 `12.1.0` | 14714 | `b8939f43e0c05afafcbfb8371c99646006565dc4a613698fd39b6c6b4aa3a2bd` | `sha512-9zbkwFe/wILuSlxIRxJm6CTX0NIDACF574PwBjm161KN4EFaJD0W9CyJsFNqPbsCrhupS6C7qHfRJ3QTmi2TXQ==` |

两套归档均有 25 个文件。包内 `package.json`、全部类型声明和 `fesm2022/abp-ng2-module.mjs` 字节一致。根导出指向 `./index.d.ts` 和 `./fesm2022/abp-ng2-module.mjs`，两个 Angular peer 都为 `^19.1.7`，普通依赖为 `tslib ^2.8.1`。两份 FESM 的 Angular 部分编译版本均为 `19.1.7`，声明的最低链接器版本为 `12.0.0` 或 `14.0.0`。

| 逐文件差异 | 公开包字节数 / SHA-256 | 本地候选字节数 / SHA-256 |
| --- | --- | --- |
| `README.md` | 1074 / `97c77ddd51b6d970e363a7237f1df80c349f96401f65998d47f1f2a062c4751d` | 1050 / `95431aca9f975d0c1b1a7c1004d03daf720776829cd63926e6b0e55bac6a826f` |
| `fesm2022/abp-ng2-module.mjs.map` | 43915 / `fd5f5f78d318db1d3e9aef7962cb558295c78711eafe46317a173c82c9e141fe` | 42519 / `a45efe9f1036238b15c8dfd0d9c3a45f6dd63b200348d8f0f8b28bd49255bddd` |

库 source map 的差异全部位于 `sourcesContent`。公开包中 17 个内嵌源文件共含 698 处 CRLF，候选使用 LF。换行归一化后内嵌源码一致，源路径、名称表及映射编码一致。


### 固定模板对照

公开侧沿用 2026-11-27 的真实冷构建。重新核对了同一模板源码归档、原始构建回执和冻结锁，并由现有离线入口复核 1193 个静态文件。本轮在新目录用相同原锁和工具独立冻结安装，退出 `0`。安装的公开适配器 25 个文件与 registry tarball 逐项一致。模板生产配置为 `@angular-devkit/build-angular:application`、`optimization: true`、`sourceMap: false`，引用 Source Sans Pro 线上样式表。[公开冷构建原始记录](r5-public-angular-rebuild.md#实测结果)

候选模板副本只把 `abp-ng2-module` 改为本地归档的 `file:` 声明。以模板原锁生成临时锁，再从另一个空目录和独立缓存冻结安装，两次均退出 `0`。临时锁的 SHA-256 为 `64a7eab309483f9d429a7825a7a3c31533cda8a1d486d105973eb875f7d39277`，包含本轮相对归档 URI，冻结安装和构建后摘要未变。展开合并条目后，1674 个非适配器选择器的解析记录逐项一致。实际安装的 1471 个包按相对路径、版本、manifest 及解析依赖边比较等价。两侧均装入 Angular core、compiler-cli、CLI、`@angular-devkit/build-angular` 及其嵌套 `@angular/build` `19.2.1`，TypeScript `5.8.2`、资源包 `6.1.0`。两侧 Yarn 保留相同的 peer 警告。

- 候选锁中的归档 URI 解析到实测 tarball，其 SHA-1 片段为 `e7f2c37f8604742720f58484fb51b018291f08db`。实际 `node_modules/abp-ng2-module` 的 25 个文件均匹配候选归档。
- TypeScript 按模板 `src/tsconfig.json` 从真实 `src/main.ts` 解析 `AbpHttpInterceptor` 导入。入口真实路径落在候选安装目录的 `index.d.ts`，SHA-256 为 `c64460d92d9f0662d0e431aea0dbd5fbe55a25a226a2e6c1ac5847edd07d7b9a`。类型符号指向同包的 `lib/interceptors/abpHttpInterceptor.d.ts`。
- `ng build --configuration production --stats-json` 退出 `0`。候选 FESM 的 SHA-256 为 `ba8cbe2796be3dd058029d8c70041881054d5b3551db68698ed254b9fc1662ec`。同次构建 `stats.json` 显示它向 `dist/browser/chunk-N46DCMOX.js` 贡献 `8985` 字节。该输出为 `1131609` 字节、SHA-256 为 `1c93d0ac4d0337ff2cccb659140cb73e762c662ee90c9f3f1baa8e7e61363fa0`。构建保留与公开侧相同的 CommonJS 警告。

两侧浏览器目录中的 1175 个 JS 文件逐项字节一致，包括 1170 个顶层 JS 和 5 个资产 JS。`main-PZGEMKYC.js` 的 SHA-256 为 `f76c6a23c8417503365d36f645f0adb6c6fef806f80b565d64067cc75d5855b6`。production 配置关闭 source map，两侧浏览器目录均无 `.map`。本次字节对比限定为 JS 和 map。公开产物的 `assets/appconfig.production.json` 已写入冻结 URL，候选保留原始构建配置。编译消费结论适用于本次模板与工具组合。候选包的应用运行、拦截行为、数据库与页面业务未执行。

验收机原始证据保存于主仓 `.git/plan-r5-angular19-adapter/implementation/`。两份 tarball 位于 `packages/`，`package-{public,candidate,difference}.json` 保留归档和逐文件摘要。阶段日志、解析回执、stats 和浏览器 JS 位于对应的 `adapter-*/`、`template-*/`。候选清单 `candidate.sha256` 可核对主要证据和实物。公开冷构建继续保留在原验收目录。[公开冷构建证据位置](r5-public-angular-rebuild.md#实测结果)

## 从普通克隆复跑

在主仓根启动 Bash。先取得[两个适配器 Git 对象和模板提交](#固定输入)，准备 Node.js `22.22.0` 及其随附的 npm，以及 Yarn Classic `1.22.22`。在该 Bash 会话中设置 `NODE22` 和 `YARN1` 为 Node.js 与 Yarn Classic 可执行文件的绝对路径，再按顺序执行下方两段命令。第一段会创建新的临时目录。样式表与包源的网络条件见[公开冷构建说明](r5-public-angular-rebuild.md#准备和离线核验)。

```bash
set -euo pipefail
repo=$PWD
work=$(mktemp -d)
template=2e9536872673a7ff1986a19e798c51684d16afe5
published=afbd23ea9711e9d94259d0f0b6afcbab9a0617fc
patched=a8ca4b37800565357f201e83d19333a9a7008887

isolated() {
  local stage=$1
  shift
  mkdir -p "$work/$stage/"{home,tmp,yarn-cache,npm-cache}
  env -i PATH="$(dirname "$NODE22"):/usr/bin:/bin:/usr/sbin:/sbin" \
    HOME="$work/$stage/home" TMPDIR="$work/$stage/tmp" YARN_IGNORE_PATH=1 \
    npm_config_cache="$work/$stage/npm-cache" \
    npm_config_userconfig="$work/$stage/home/.npmrc" \
    npm_config_globalconfig="$work/$stage/home/npm-globalrc" "$@"
}

install() {
  local stage=$1
  shift
  isolated "$stage" "$YARN1" --no-default-rc install --non-interactive \
    --no-progress --cache-folder "$work/$stage/yarn-cache" "$@"
}

for entry in "published:$published" "patched:$patched"; do
  stage=${entry%%:*}
  commit=${entry#*:}
  mkdir -p "$work/$stage/source"
  git -C "$repo/abp-ng2-module" archive "$commit" | tar -x -C "$work/$stage/source"
  cd "$work/$stage/source"
  isolated "$stage" "$NODE22" -p 'process.version + " " + process.platform + "/" + process.arch'
  isolated "$stage" "$YARN1" --no-default-rc --version
  isolated "$stage" "$(dirname "$NODE22")/npm" --version
  shasum -a 256 yarn.lock
  if install "$stage" --frozen-lockfile >"$work/$stage/install.log" 2>&1; then
    shasum -a 256 yarn.lock
    isolated "$stage" "$YARN1" --no-default-rc ng build abp-ng2-module \
      --configuration production >"$work/$stage/build.log" 2>&1
    shasum -a 256 yarn.lock
    mkdir -p "$work/$stage/package"
    (cd dist/abp-ng2-module &&
      isolated "$stage" "$(dirname "$NODE22")/npm" pack --json \
        --pack-destination "$work/$stage/package" >"$work/$stage/pack.json")
  else
    status=$?
    shasum -a 256 yarn.lock
    printf '%s 冻结安装退出 %s，日志 %s\n' "$commit" "$status" "$work/$stage/install.log"
    [[ "$stage" == published ]] && grep -q 'Your lockfile needs to be updated' "$work/$stage/install.log" || exit "$status"
  fi
done
```

验证归档使用 `shasum -a 256`、`shasum -a 512` 和 `tar -tzf`，解包后在各 `package/` 目录用相对路径逐项对比。公开归档可从 npm registry 下载后按表校验。在同一个 Bash 会话中接着执行下方命令，沿用上段创建的目录、候选归档和函数。等深的三个模板目录共用候选的相对 URI。复跑布局的 URI 与验收机布局不同，临时锁的总体摘要随 URI 改变。两套冻结安装与临时锁生成各使用自己的缓存。[公开归档](https://registry.npmjs.org/abp-ng2-module/-/abp-ng2-module-12.1.0.tgz) · [Yarn Classic 冻结选项](https://classic.yarnpkg.com/lang/en/docs/cli/install/#toc-yarn-install-frozen-lockfile)

```bash
archive=../../patched/package/abp-ng2-module-12.1.0.tgz
for stage in public seed candidate; do
  mkdir "$work/$stage"
  git -C "$repo/module-zero-core-template" archive "$template" angular | tar -x -C "$work/$stage"
  cd "$work/$stage/angular"
  if [[ "$stage" != public ]]; then
    "$NODE22" --input-type=commonjs - "$archive" <<'JS'
const fs = require('node:fs');
const manifest = fs.readFileSync('package.json', 'utf8');
const original = '"abp-ng2-module": "12.1.0"';
if (manifest.split(original).length !== 2) process.exit(1);
fs.writeFileSync('package.json', manifest.replace(original, '"abp-ng2-module": "file:' + process.argv[2] + '"'));
JS
  fi
  if [[ "$stage" == seed ]]; then
    install "$stage" >"$work/$stage/install.log" 2>&1
  else
    if [[ "$stage" == candidate ]]; then
      cp "$work/seed/angular/yarn.lock" yarn.lock
    fi
    shasum -a 256 yarn.lock
    install "$stage" --frozen-lockfile >"$work/$stage/install.log" 2>&1
    shasum -a 256 yarn.lock
  fi
done

diff -u "$work/public/angular/yarn.lock" "$work/candidate/angular/yarn.lock" || test "$?" -eq 1
(cd "$work/public/angular" &&
  isolated public "$YARN1" --no-default-rc ng build --configuration production >"$work/public/build.log" 2>&1)
(cd "$work/candidate/angular" &&
  isolated candidate "$YARN1" --no-default-rc ng build --configuration production \
    --stats-json >"$work/candidate/build.log" 2>&1)
```

比较两套锁时，将每个合并选择器展开并核对整条记录，包括依赖边。比较安装图时，从实际 `node_modules` 读取包相对路径、版本、manifest 摘要、普通／可选／peer 依赖的解析目标，并核对根项目的开发依赖。候选适配器目录逐文件比对 tarball。类型证据以模板 `src/main.ts` 中真实 import 为起点，用已安装 TypeScript 读取 `src/tsconfig.json` 并解析模块，核对入口真实路径和 SHA-256。用 `dist/stats.json` 的 `outputs[*].inputs` 定位 `node_modules/abp-ng2-module/fesm2022/abp-ng2-module.mjs` 对该次构建实际浏览器 JS 的 `bytesInOutput`，并复算输入和输出摘要。[Angular CLI 构建参考](https://angular.dev/cli/build)
