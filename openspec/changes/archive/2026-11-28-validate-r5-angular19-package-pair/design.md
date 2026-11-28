# Design

## Context

模板的 `angular/package.json` 直接声明两个包，原锁分别解析到公开 `12.1.0` 和 `6.1.0`。`src/main.ts` 注册适配器的 `AbpHttpInterceptor`，`src/typings.d.ts` 显式引用两份资源声明。`angular.json` 的 application builder 将全局脚本按顺序合入产物，另复制两份 SignalR 脚本。production 配置启用优化和输出哈希，关闭 source map。[既有验收规范](../../../specs/template-maintenance-package-consumption/spec.md) · [双包提案](proposal.md)

## Goals / Non-Goals

**Goals**

在同次实际冻结安装和 production 构建中把两份 tarball 分别追溯到声明及浏览器产物。复用已核验的单包输入和可比对照，补齐下表的最后一格。

| 适配器 `12.1.0` | 资源包 `6.1.0` | 证据范围 |
| --- | --- | --- |
| 公开 | 公开 | 固定模板冷构建匹配 1193 个冻结文件。V7 另在该公开冻结前端下对照 R4 和 R5 的角色编辑。[公开冷构建](../../../../docs/maintenance/r5-public-angular-rebuild.md#实测结果) · [V7 角色编辑](../../../../docs/maintenance/r5-angular-user-role-edit.md) |
| 本地候选 | 公开 | 适配器已制包、冻结安装并进入新 production 浏览器 JS。1175 个 JS 与公开对照逐项相同。[适配器实测](../../../../docs/maintenance/r5-angular19-adapter-package-plan.md#实测结果) |
| 公开 | 本地候选 | 资源包已制包、冻结安装并进入新 production 输出。浏览器观察为 `formatString`、全局脚本实收和两份 SignalR 静态响应。本次以这格作为产物对照。[资源包实测](../../../../docs/maintenance/r5-angular19-web-resources-plan.md#实测结果) |
| 本地候选 | 本地候选 | 待验证本提案约定的组合。 |

**Non-Goals**

支持范围限于本表第四格的固定 macOS ARM64 模板消费和静态检查。候选登录、完整页面运行、拦截器运行行为、SignalR 握手与时区转换、后端、数据库、其他平台及 npm 发布均有独立验收范围。执行使用隔离目录和现有复跑入口。

## Decisions

### 1. 核对已有实包及可比对照

| 输入 | 固定身份 |
| --- | --- |
| 免费模板 | `2e9536872673a7ff1986a19e798c51684d16afe5` 的 `angular/`，原锁 SHA-256 `3e55c44022c5c15bf2c474eb483f8161945151261f06d00218fffbdb86c0d14f`，实装 Angular `19.2.1`、TypeScript `5.8.2` |
| 工具链 | macOS ARM64，Node.js `22.22.0`、Yarn Classic `1.22.22`、npm `10.9.4`。记录实际系统版本、可执行身份和安装的 Angular 构建工具，对照须有相同的有效构建条件 |
| 适配器候选 | Git `a8ca4b37800565357f201e83d19333a9a7008887`，根锁 SHA-256 `079f1ab5293ce20975d8acf2370b820fafd7aa6e8ee829a437bcddd8fa6ed7da`。`abp-ng2-module 12.1.0`，25 个文件，tarball SHA-256 `b8939f43e0c05afafcbfb8371c99646006565dc4a613698fd39b6c6b4aa3a2bd`。公开参考 `afbd23e` 的冻结失败属于其原根锁。主仓适配器 gitlink 属于 Angular 21。 |
| 资源候选 | 框架 Git `7933e71f5646d2447af3502ecbea9a3f1aba8184`，资源 tree `780977463dbf0eb599765ff553000a631a70b35d`，实际包装取自上游 Git `fb79b7d44bc9dfce0ae600c8170961f182b05e76`。`abp-web-resources 6.1.0`，40 个 Git 原字节文件和两份包装，tarball SHA-256 `93c66026539a1c22740b893f4ff8b6213b80e5a9ccbee247c79f651e2648a126`。 |

优先从两轮封存实物取只读副本，复算归档 SHA-256、SRI 及逐文件路径和原字节摘要。普通克隆按两个已交付指南的固定提交及工具取得真实 tarball。若重新打包的归档摘要不同，记录两套归档身份和差异原因。只有经旧逐文件清单逐项证实内容与入口契约等价、差异可归于打包容器时，才可按复包装载并如实登记新摘要、SRI 和本轮锁定位。包内任一原字节变化须视作不同候选。缺少旧逐项证据时身份待查。资源的 CRLF/LF 差异只用于解释公开对照。[适配器复跑](../../../../docs/maintenance/r5-angular19-adapter-package-plan.md#从普通克隆复跑) · [资源包复跑](../../../../docs/maintenance/r5-angular19-web-resources-plan.md#从普通克隆复跑)

复跑资源包时，框架 Git blob 提供资源，按表中包装提交核对 `package.json` 与 `LICENSE` 两份 blob。可使用已核验的本地包装原件，也可从上游或分发 fork 读取同一提交中的等同原件。已封存实物通过身份核验即可用于双包安装。[资源来源与分发参考登记](../../../../docs/compatibility/angular-ecosystem.md#web-resources-分发维护登记)

只换资源的留存锁、实装图、原始浏览器目录或可信逐文件清单，须能绑定到同一实测的固定模板、公开适配器及资源候选、工具和构建回执。若缺少相应对照，用原模板锁、锁内 SRI 所指的公开适配器及已登记资源候选，按资源单包指南从隔离环境补做缺项。重建产物只提供本轮对照。关联历史浏览器响应仍须核对原始探针输入和实收正文。[资源单包安装和构建](../../../../docs/maintenance/r5-angular19-web-resources-plan.md#冻结安装与-production)

### 2. 双归档解析与冻结实装

从同一 Git 对象导出更新锁与冻结安装的两个副本。源码和生产配置按原字节核对。只将根 manifest 的两个目标声明改为登记 tarball 的 `file:` 路径，用原锁作种子产生临时锁。将临时锁复制到另一副本，以隔离 HOME、TMPDIR 和独立空 Yarn 下载缓存执行 `yarn --no-default-rc install --frozen-lockfile --non-interactive`，设置 `YARN_IGNORE_PATH=1`。记录两条 `file:` 实际解析到的归档绝对路径、Yarn 锁中的校验值与归档复算值，以及实装的真实路径、完整文件清单和逐文件 SHA-256。比较冻结前、安装后和构建后的临时锁字节。

将合并选择器展开后比对临时锁与原锁的非目标记录，包括版本、来源、完整性和依赖边。同时从实际 `node_modules` 读取根与嵌套包的相对路径、版本、manifest 摘要和普通、开发、可选、peer 依赖的解析目标。与可比的资源单包实装图对照，本轮相对于该对照只应新增适配器替换的预期差异。核对 `tslib`、Angular peers、独立声明的资源依赖及其他解析项；保存 peer 警告和实际解析。两个包的版本字符串与路径均相似，归档定位、文件比对和依赖图三者共同确立实物身份。

### 3. 从同次构建取得两条来源链

确认无 `dist` 和 Angular 缓存后，从已验实装运行 `yarn --no-default-rc ng build --configuration production --stats-json`。记录实际命令、工作目录、退出码、统计、构建日志及输出。用已安装的 TypeScript 与模板 `src/tsconfig.json` 核对 `src/main.ts` 对适配器 `index.d.ts` 的解析，并确认 `src/typings.d.ts` 引用的 `abp.d.ts` 和 `abp.signalr.d.ts` 均由实装资源包提供，记录三份真实路径与原字节摘要。

- **适配器。** 从同次 `stats.json` 的 `outputs[*].inputs` 将实装 `fesm2022/abp-ng2-module.mjs` 关联到有非零 `bytesInOutput` 的实际浏览器 JS。核对输入归档、实装及输出三者摘要，报告释明贡献到哪个文件。统计格式变化时可用同次构建的等效归属证据。[适配器 production 复跑](../../../../docs/maintenance/r5-angular19-adapter-package-plan.md#从普通克隆复跑)
- **Web Resources。** 复用单包指南的实际读取观测，记录九个脚本的读取顺序、真实路径及原字节 SHA-256，并将 `abp.js`、`abp.moment.js` 和模板本地 SweetAlert、Freeze UI 适配追到 `angular:script/global:scripts.js` 的输出与原 `index.html` 的实际标签。两份 SignalR 文件分别核对框架 Git、tarball、实装和同次 `dist/browser/assets/abp/`，按原字节包含 BOM 和换行。[资源 production 复跑](../../../../docs/maintenance/r5-angular19-web-resources-plan.md#production-与浏览器)

### 4. 比较完整产物并决定静态浏览器证据来源

两侧比较同一配置阶段的完整 `dist/browser/`，生成按相对路径排序的文件摘要表。对每项新增、缺失和字节变化记录成因、影响和可核验的接受依据。优先比较双方原始 production 输出，分别将 `assets/appconfig.production.json` 与模板 Git 原件对照。若两侧都需使用冻结 URL，则只在各自隔离副本上应用同样字段值和序列化步骤，记录前后摘要。用模板配置实际拉取同一 Source Sans Pro 样式表，记录 URL、实际获取结果、原 HTML 中内联块原字节摘要与规则数。旧结果的 1193 个路径是可核对的对照数据，当前目录需现场重新清点。[公开字体及冻结配置](../../../../docs/maintenance/r5-public-angular-rebuild.md#实测结果) · [V7 输入校验](../../../../eng/r5_angular_role_edit.py)

仅当同阶段完整目录的路径集合和各文件原字节逐项相同，且模板、实装资源、全局脚本输入和顺序、构建与静态服务条件等价，历史最小页和三条浏览器回执及实收原件均与本轮产物吻合，才可引用资源单包的静态观察。否则，验收通过所需的静态证据须使用本轮 `dist/browser/` 在回环静态服务和独立浏览器上下文重跑最小页取得。

两种证据均须证明 `window.abp.utils.formatString('ABP {0} / {1}', 'R5', '资源')` 精确返回 `ABP R5 / 资源`，页面未捕获异常为零，本轮 `index.html` 全局脚本标签所指的 URL 及 `/assets/abp/abp.signalr.js`、`/assets/abp/abp.signalr-client.js` 均返回 HTTP 200，三份浏览器响应原字节分别匹配本轮 `dist/browser/` 对应文件并保留 BOM。记录历史引用或本轮实跑及其证据位置。最小页通过仅证明上述静态观察，其他产物差异仍按逐项证据判定。[浏览器探针与实测范围](../../../../docs/maintenance/r5-angular19-web-resources-plan.md#浏览器静态验收)

### 5. 验收判定和停点

- **通过**要求双包身份和依赖图可核对、同次 production 构建成功并证明双重来源、完整产物对照中每项差异均有可核验的接受依据、静态观察满足上述断言。记录每阶段实测与来源。
- **待查**适用于工具或网络输入不可用、所需证据尚未补齐、环境不可比或产物差异缺少可核验的接受依据，包括候选代码所在的 chunk 或资产差异。保留原错误、命令和退出码、预期与实测摘要及补证条件。下游依赖步骤标为未执行。
- **失败**适用于确认产物差异违反验收要求、身份可信的实际安装、构建或观察违背预期，以及确认的归档、实装或非目标依赖身份失配。保留失败现场和差异。停止依赖该结果的步骤。独立结果可留存，整体结论按欠缺的验收条件登记。

验收停在保存隔离输入和实物证据、记录结果及复核文档。V7 的 `frozen_angular` 继续校验公开冻结清单文件摘要、整表摘要、1193 个文件、角色编辑 chunk 摘要及静态实物，服务地址改写仍限副本。候选证据使用自身清单。需要复原公开组合时，从固定模板 Git 对象和原锁在干净隔离目录重新安装。[公开冻结与角色验收](../../../../docs/maintenance/r5-angular-user-role-edit.md)

## Risks / Trade-offs

- 同名同版本可能命中旧缓存。将生成锁和冻结实装隔离，核对实际归档及包内原字节。
- 动态字体响应和应用配置阶段可能造成可定位的文件差异。对照双方使用可回查的构建条件，保存路径及字节差异，避免以单个总摘要代替归因。
- 单包浏览器只运行全局脚本与静态探针。其可复用范围由原始请求和响应决定，双候选的实际编译来源仍必须由新构建得出。
