# Design

## Context

发布提交的库清单声明 12.1.0，Angular common/core peer 均为 `^19.1.7`。`angular.json` 声明 `@angular-devkit/build-ng-packagr:build`，production 配置选用 `tsconfig.lib.prod.json` 的 `partial` 编译模式，`ng-package.json` 从 `src/public-api.ts` 生成 `dist/abp-ng2-module`。模板通过 `src/main.ts` 将 `AbpHttpInterceptor` 注册为 `HTTP_INTERCEPTORS`。源码、锁和公开 tarball 的固定身份见计划。[提案](proposal.md) · [固定输入](../../../../docs/maintenance/r5-angular19-adapter-package-plan.md#固定输入) · [增量规范](specs/template-maintenance-package-consumption/spec.md)

## Goals / Non-Goals

**Goals**

取得可追溯的本地实包，并通过模板实际的类型检查、生产打包及新产物证明限定的消费兼容性。

**Non-Goals**

支持范围限定为 macOS ARM64 的固定 Angular 19 模板编译。应用启动、HTTP 拦截运行行为、后端、SQL Server、浏览器业务和发行验收各用对应的独立证据。

## Decisions

1. **按 Git 对象分开制包。** 用 `git archive` 导出每个输入到新目录。分别设置专用的 HOME、临时目录及 Yarn/npm 缓存，以 `YARN_IGNORE_PATH=1` 和 `--no-default-rc` 隔离主机配置。起点沿用模板冷构建的 Node.js `22.22.0`、Yarn Classic `1.22.22`，登记 `npm --version`、可执行路径和 macOS/架构。检查安装前无 `node_modules`、`dist`、`.angular/cache`，运行 `yarn --no-default-rc install --frozen-lockfile --non-interactive --cache-folder "$ADAPTER_CACHE"`，记录安装前后和构建后的根锁 SHA-256 及实际解析的 Angular core、compiler-cli、CLI、`@angular-devkit/build-ng-packagr`、`ng-packagr`、TypeScript、RxJS 和 `tslib`。安装成功才从同一工作区执行 `yarn --no-default-rc ng build abp-ng2-module --configuration production`。若 `afbd23e` 的冻结安装因根锁缺少条目失败，保存原始日志和退出码，将该提交的构建、制包登记为未执行，再在全新目录导出 `a8ca4b3` 及其根锁执行同一流程。其他失败按实际阶段定位，后续试验按各自的 Git 对象和锁摘要登记。
2. **从库构建目录制成 npm 实包。** 在新鲜的 `dist/abp-ng2-module` 中执行 `npm pack --json --pack-destination "$ADAPTER_PACKAGE_OUT"`，先记录输出 manifest，检查 tarball 文件清单、SHA-256、SHA-512、包名、版本、依赖、peers、根 `exports` 及对应类型声明和 FESM。保存归档内包文件逐项 SHA-256，比较同版公开 tarball 的内容和入口，包括 FESM 中 Angular 部分编译声明的版本，字节差异记录到文件层。上游 `publish` 脚本连带执行 registry 发布，验证只使用其 production 构建子命令及本地 `npm pack`。源码根目录与 `yarn link` 仅供定位来源，验收走可安装的 tarball。[上游制包说明](https://github.com/aspnetboilerplate/abp-ng2-module/blob/afbd23ea9711e9d94259d0f0b6afcbab9a0617fc/PUBLISH.MD)
3. **以模板锁为种子替换一个依赖。** 从同一模板 Git 对象分别导出两侧，候选副本仅改 `package.json` 中适配器声明为指向已核验归档的 `file:` 路径。以原锁为种子执行 `yarn --no-default-rc install --non-interactive --cache-folder "$CANDIDATE_LOCK_CACHE"` 生成候选临时锁，比较两侧清单及锁条目的解析版本、来源、完整性和依赖边。只接受适配器选择器、归档来源与自身实物引起的预期差异。再用候选临时锁及同一 tarball，在另一空目录和独立缓存执行冻结安装，复算锁和 tarball。核对两侧实际依赖树，比较包的路径、版本和清单，确保 Angular、资源包及其余解析依赖可比，记录 peer 警告和非预期差异。保留临时安装配置和锁作为证据。
4. **追溯模板实际编译所读入口。** 将 `node_modules/abp-ng2-module` 真实路径内的文件与候选 tarball 逐项匹配，并核对临时锁写入的 `file:` 来源。两侧均用模板真实 `yarn --no-default-rc ng build --configuration production`。用候选模板的 TypeScript 和 `src/tsconfig.json` 追踪 `src/main.ts` 导入 `AbpHttpInterceptor` 时解析到的 `index.d.ts`，按真实路径和摘要核对候选文件。候选 production 编译加 `--stats-json`，在 `stats.json` 的 `outputs` 中定位一个实际生成的浏览器 `.js` 文件，记录其 `inputs` 中候选 FESM 的路径及大于零的 `bytesInOutput`，并核对该输入对应的候选 `.mjs` 摘要。统计格式无法直接提供此项时，用同次构建的等效证据关联候选 FESM 与具体 JS 输出。证据不足时，编译退出码照实登记，候选消费结论为待定。记录模板构建配置、实际 Angular 构建工具和其他依赖图。候选环境从无 `dist`、`.angular/cache` 和 `node_modules` 起步。公开侧证据满足复用条件时可复用原 production 运行，否则同条件补跑最少的缺项。[对照复用条件](../../../../docs/maintenance/r5-angular19-adapter-package-plan.md#对照和验收判断)

## Risks / Trade-offs

- 发布参考提交的根锁缺少部分声明的选择器 → 冻结步骤以实际命令结果为准，保留锁前后摘要、失败阶段和原始退出码。后续锁通过时，以它的 Git 对象登记制包来源。
- 相同名称和版本、缓存内容或符号链接可能掩盖包来源 → 候选通过隔离缓存冻结安装，以 URI、真实路径、逐文件摘要及构建解析串成证据。两套归档逐项完全相同时仍保留其本地安装来源回执。
- production 内联的外部字体和包镜像可能导致环境差异 → 保留样式表来源及失败日志。包图或构建条件失配时先补齐可比证据。归档、FESM、bundle 与 source map 的逐项差异另记。若比较整个浏览器目录，两侧均取生产编译原始输出或均取同样写入冻结 URL 后的副本，并注明 `assets/appconfig.production.json` 的处理阶段。
