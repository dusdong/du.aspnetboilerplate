# Design

## Context

现有 `r5_angular_role_edit.py` 默认读 R3 返修原件，`--angular-source` 可替换输入根。R3 的 `RuntimeRun.angular_build` 已实现从固定 Git 对象构建，但其入口同时依赖后端准备，历史正式轮使用预热的 Yarn 下载缓存。准备入口的目标和范围见 [Proposal](proposal.md) 与 [增量规范](specs/template-maintenance-package-consumption/spec.md)。[R3 原版运行对照](../../../../docs/maintenance/r3-template-runtime-baseline.md#2026-11-25-本机验收)

## Goals / Non-Goals

- 从公开固定模板生成与 R5 校验兼容、可单独搬移的产物，保留首次空缓存实建和独立读回证据。
- 新入口仅处理前端准备及离线校验，历史原件继续用于原复跑入口。该变更无需迁移、部署或改变后端运行方式。

## Decisions

1. 在主仓提供一个独立的准备脚本，拟采用 `eng/r5_angular_prepare.py`，提供 `prepare --template-repo <公开模板检出> --output <新目录>` 和 `verify --angular-source <产物根>`。直接用 `git archive` 从固定提交导出 `angular/` 到本次新目录的 `source/`。准备工作从 Git 对象取得，不读取模板工作树中的文件，也无需原验证机的 `.git` 实物。离线入口直接调用现有 `frozen_angular`，同一校验用于最后的产物核对和后续角色验收。旧 `--angular-source` 用法及默认值按现有 CLI 提供。[固定模板 Git 对象](https://github.com/dusdong/module-zero-core-template/tree/2e9536872673a7ff1986a19e798c51684d16afe5/angular) · [R5 输入校验](../../../../eng/r5_angular_role_edit.py)
2. 在 macOS ARM64 核实实际执行的 Node.js `22.22.0` 和 Yarn Classic `1.22.22`。在导出的目录内确认 `node_modules` 不存在，显式指定本轮新建的空 Yarn 缓存及 Classic 可执行文件，用 `YARN_IGNORE_PATH=1` 隔离项目级 Yarn 重定向，并在同一路径下检查真实 Yarn 版本，遇到 Yarn 4 接管时在安装前报错。隔离继承的缓存、离线镜像和私有源配置，按 `yarn.lock` 的公开解析地址（`registry.npmjs.org`、`registry.yarnpkg.com`）与完整性信息安装。沿用 R3 的 `yarn install --frozen-lockfile --non-interactive --no-progress --cache-folder <空目录>` 和 `yarn ng build --configuration production`。复用 `check_lock`，在安装前、安装后和构建后均核对锁文件 SHA-256 `3e55c44022c5c15bf2c474eb483f8161945151261f06d00218fffbdb86c0d14f`。在启动 production 构建前确认本次 Angular 构建缓存（含字体缓存）为空或尚不存在，记录缓存实际路径与初态。安装后回读 `ANGULAR_PACKAGES` 约束的 `@angular/core`、`@angular/cli`（均为 `19.2.1`）、`abp-ng2-module` `12.1.0` 和 `abp-web-resources` `6.1.0`。[R3 构建与工具校验](../../../../eng/r3_template_runtime.py)
3. 模板在 `src/index.html` 引用 Google Fonts 的 Source Sans Pro 样式表，production 优化将 CSS 内联到 HTML。Yarn 锁文件覆盖 npm 安装，字体 CSS 由构建时的公开服务提供。记录模板 URL 和产出 `index.html` 的摘要，冻结的 HTML 与内联样式块摘要见[产物身份表](../../../../docs/maintenance/r5-public-angular-rebuild-plan.md#固定输入和产物身份)。完成构建后，在新生成的 `source/angular/dist/browser/assets/appconfig.production.json` 写入冻结地址 `remoteServiceBaseUrl=http://127.0.0.1:14436`、`appBaseUrl=http://127.0.0.1:14236`，保留其余配置值。沿用 `write_json` 的 UTF-8、键排序、两空格缩进和尾部换行。冻结地址是静态配置的字节输入，不要求监听。核验后如果用于完整角色验收，由已有 `serve_copy` 在服务副本改写本轮地址。[R3 构建顺序](../../../../eng/r3_template_runtime.py) · [JSON 序列化](../../../../eng/r3_web_host.py) · [R5 服务副本](../../../../eng/r5_angular_role_edit.py)
4. 使用既有 `inventory` 从新构建重新生成相对路径与文件 SHA-256 整表，用 `write_json` 写出根目录下的 `angular-production-files.json`。以 `frozen_angular` 核对清单文件字节 `ANGULAR_MANIFEST`、整表摘要 `ANGULAR_INVENTORY`、1193 个逐文件摘要和编辑脚本 `EDIT_CHUNK` 的 `EDIT_SHA256`。期望值来自公开主仓源码中已有的常量，清单由本轮计算。验收身份见 [固定输入和产物身份](../../../../docs/maintenance/r5-public-angular-rebuild-plan.md#固定输入和产物身份)。[清单文件摘要](../../../../eng/r3_template_net9_runtime.py) · [清单内容与实物校验](../../../../eng/r5_angular_role_edit.py)
5. 在 `production_identity` 中按原始 HTML 字节查找内联 `<style>`。以同一条 `@font-face` 规则的 `font-family` 声明值识别 Source Sans Pro。普通样式引用和 `src:local(...)` 只提供字体名称引用。命中后对起止 `<style>` 标签之间的全部原始字节（含尾部空白）计算长度与 SHA-256，并记录块内 `@font-face` 规则数。冻结 SHA-256 仅用于比对，修改后的目标块仍须能定位并报告新摘要。缺失时使用 `actual: null`、`bytes: 0`、`fontFaces: 0`。保留读取失败信息、HTML 及两级清单的实际和预期摘要，继续由 `frozen_angular` 决定产物是否合法。用标准库完成有限的规则识别。用合成单测区分字体定义与来源引用。四份冻结产物副本均通过 `prepare` 离线回放构建后的步骤，重新生成清单并执行共用核验，从 `report.json` 读取本次诊断。按修正计划中独立计算的固定值检查报告与退出码。`verify` 的离线读回覆盖清单和实物校验。[诊断修正计划](../../../../docs/maintenance/r5-angular-font-diagnostics-plan.md)

## Risks / Trade-offs

- 空缓存安装可能受公开地址、宿主配置或工具身份影响。记录失败阶段、可公开的来源和实际工具版本，保留锁文件摘要与退出码。依赖未能从空缓存安装时，记录环境阻塞。
- 字体样式表获取失败时，记录 production 构建阶段、URL、错误和退出码。若构建成功而清单失配，保留本轮生成的清单，并列出清单文件与整表的预期、实际 SHA-256。公开检出只有登记的摘要，没有历史 1193 行清单。对有公开单文件基线的产物逐项核对，其余差异路径只有取得逐文件证据时才报告。HTML 偏离时，取对应字体 `<style>` 标签之间未经重排的 UTF-8 字节，对照样式块摘要并记录一致、失配或缺失；HTML 其余部分仍可能有差异。
- 将清单和 `source/angular/dist/browser/` 实体文件复制到另一绝对路径。在隔离环境中只提供公开主仓脚本、Python 标准库及搬移件，禁止网络访问，原构建目录与历史证据对该环境不可见。以新 Python 进程执行 `verify --angular-source`，记录解释器版本、隔离方式与结果。用合格搬移件另制副本，只改一个非入口资产，核对清单摘要仍正确，再用同一入口验证静态实物失配；以有效清单取出该路径的预期摘要，与副本文件实算摘要对账。最后读回未修改的搬移件。V7 业务实测继续作为六次保存的证据。
