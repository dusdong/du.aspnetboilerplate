# Design

## Context

模板通过 `angular.json` 的 build 入口引入全局脚本和复制资产，通过 `angular/src/typings.d.ts` 显式引用两份声明。`SignalRAspNetCoreHelper.ts` 构造动态脚本地址 `/assets/abp/abp.signalr-client.js`。已验证的公开构建和适配器候选各有独立证据。[固定模板入口](https://github.com/dusdong/module-zero-core-template/blob/2e9536872673a7ff1986a19e798c51684d16afe5/angular/angular.json) · [当前计划](../../../../docs/maintenance/r5-angular19-web-resources-plan.md)

## Goals / Non-Goals

**Goals**

- 用路径和摘要连起 Git 原件、归档、安装文件、构建产物与浏览器响应。
- 以同一模板和工具记录资源包单变量替换后的静态消费结果。

**Non-Goals**

- 应用登录、SignalR 握手、后端和 SQL Server 验收属于其他场景。
- 此试验只形成临时包及消费证据。持久化工具、子仓修改、升级、分发仓、npm 命名和发行各自另行决策。

## Decisions

### 1. 以框架 Git 子树为资源输入

在隔离 staging 中，用 `git ls-tree` 枚举框架生产 gitlink `7933e71f5646d2447af3502ecbea9a3f1aba8184` 下的 `src/Abp.Web.Resources/Abp/Framework`，核对 tree `780977463dbf0eb599765ff553000a631a70b35d`，直接从各 Git blob 写入同名 `Abp/Framework` 路径。登记路径、Git 对象、字节数及 SHA-256。这样可绕开工作树换行转换。公开 tarball 只用于对照。旧分发 `packages.config` 的 `Abp.Web.Resources 5.1.0`／`net461` 和 Windows 提取脚本留作历史参考。[资源来源说明](../../../../docs/compatibility/angular-ecosystem.md#五abp-web-resources源码资源与分发维护说明)

包装采用分发仓库 `fb79b7d44bc9dfce0ae600c8170961f182b05e76` 的 `package.json` 与 `LICENSE`。预检中，两份 manifest 解析结果只有版本不同，两份许可文本仅换行不同。实施时登记包装输入的 Git 身份与原始摘要，显式将源 manifest 中的 `6.0.1` 改为 `6.1.0` 后记录新摘要。保留 `main` 指向 `Abp/Framework/scripts/abp.js`，实际运行依赖为空。公开 tarball 自带的 manifest 无 `types` 或 `typings`，registry 元数据另列 `types: ./Abp/Framework/scripts/abp.d.ts`。候选保留真实归档的字段契约并核对 types 目标实体，模板的消费证据以两条显式声明引用的实际解析为准。[固定分发 manifest](https://raw.githubusercontent.com/aspnetboilerplate/bower-abp-resources/fb79b7d44bc9dfce0ae600c8170961f182b05e76/package.json) · [npm 版本元数据](https://registry.npmjs.org/abp-web-resources/6.1.0) · [公开归档](https://registry.npmjs.org/abp-web-resources/-/abp-web-resources-6.1.0.tgz)

用登记的 npm 在仅含 40 个资源和两个包装文件的 staging 执行 `npm pack`，保存命令回执、归档 SHA-256、SHA-512 SRI、包内路径和文件摘要。先核对打包后的资源逐个匹配原 blob，再与已验摘要的公开 tarball 对照。对同路径资源按原字节比较，CRLF 到 LF 的归一仅用于说明差异。包装单列双方路径和摘要，记录 `package.json` 与 `LICENSE` 的实测差异，并标出公开侧额外的 README、Bower、Gulp 和 NuGet 历史文件。两份归档的整体摘要仅作各自身份。

### 2. 在固定模板隔离安装与构建

从模板提交 `2e9536872673a7ff1986a19e798c51684d16afe5` 导出，使用 macOS ARM64、Node.js `22.22.0`、Yarn Classic `1.22.22` 和 npm `10.9.4`。用公开侧原锁与候选侧临时锁作对照。原 `angular/yarn.lock` 的 SHA-256 为 `3e55c44022c5c15bf2c474eb483f8161945151261f06d00218fffbdb86c0d14f`。候选仅改 `abp-web-resources` 为本地 `file:` tarball。用一份副本更新临时锁，另在干净副本冻结安装，隔离 HOME、下载缓存、Angular 缓存和输出。核对 `file:` 解析、实际归档摘要、安装包逐文件摘要、非目标锁选择器及实际依赖图，包括公开适配器 `12.1.0`。安装前后及构建后校验使用的锁。

公开 production 证据可沿用 2026-11-27 冷构建，前提是模板提交及锁、工具、公开包和构建选项可回查，其他输入可比。比较静态产物时记录字体样式输入与配置阶段，使用同一处理阶段的产物。公开侧证据不足时补做冻结对照。候选使用原 production 配置生成新输出，保留真实构建回执和原始产物。[公开生产构建](../../../../docs/maintenance/r5-public-angular-rebuild.md#实测结果)

### 3. 核对实际声明、全局脚本和静态响应

- 用模板 TypeScript 文件解析清单或等效编译证据确认 `scripts/abp.d.ts` 和 `scripts/libs/abp.signalr.d.ts` 的实测路径及摘要。
- 在同次构建中记录构建器实际读取的九个脚本的路径、顺序及原字节摘要。用构建统计中的全局入口与生成的 `index.html` 关联实际加载的全局脚本产物，确认 `abp.js` 及 `scripts/libs/abp.moment.js` 进入该产物。保留 `angular.json` 真实顺序，包括中间的模板 SweetAlert 与 Freeze UI 适配、前置的 Moment 与其他依赖。核对从包内复制的两份 SignalR JS 在 `dist/browser/assets/abp/` 的字节。
- 用仅监听回环的静态服务提供本次 production 文件。最小运行页只引用原 production HTML 所用的全局脚本及其加载顺序，核对浏览器以脚本请求实际收到的字节与产物一致，断言规范指定的 `window.abp.utils.formatString` 结果并检查加载期间的未捕获异常。用浏览器请求两条静态 URL，分别核对 HTTP 200 和 `arrayBuffer()` 原始字节摘要，逐项对照 Git、归档、实装及静态产物。模板的全局脚本仅加载普通 Moment，时区转换行为另行验证。标记客户端脚本在模板中的动态引用位置，浏览器实测范围为全局函数与静态 URL，不执行连接流程。

## Risks / Trade-offs

- 同名同版本可能命中公开缓存。以独立缓存、归档解析、逐文件身份和非目标依赖图共同确认实际安装。
- 远端 registry 或字体样式不可用时，保留原错误、URL 与失败阶段。静态冒烟依赖已经核对身份的新 production 输出。
- 公开包可能与候选仅在资源换行或包装上不同。采用各自原字节追踪，记录实际构建和运行结果，不要求候选输出命中历史冻结摘要。

## Migration Plan

回退试验时用模板提交的原始 manifest 与锁重新冻结安装公开资源包。候选的 staging、临时锁与输出留在隔离目录，原公开冻结产物继续按已登记身份复验。
