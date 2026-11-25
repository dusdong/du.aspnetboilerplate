# R3 首包实施任务

## 1. 主仓入口与隔离还原

- [x] 1.1 在 `eng/verify.py` 注册 `r3-web-host`，在 `eng/r3_web_host.py` 实现固定输入、预检、独立运行目录及阶段记录。核对主仓登记的模板和框架提交及树，隔离物化模板，锁定 SDK 和平台。用缺失固定对象的定向用例验证非零诊断、后续未执行状态及主仓和子仓检出保持一致。
- [x] 1.2 生成仅含 nuget.org 的独立配置和独立空缓存，执行固定 `net9.0` Host 的 Release 配置还原。检查实际运行日志、有效配置、原配置差异、包目录与退出码。在 R3 证据文档中记录复跑命令及环境要求。

## 2. 还原、构建与候选缺口

- [x] 2.1 从五份 `project.assets.json` 核对可达项目、项目引用、六个直接 ABP ID、应用包的版本、来源、哈希、资产及依赖边，生成 `assets-inventory.json`。按项目和目标单列 `downloadDependencies` 与实际使用的预装 SDK pack，记录身份、版本、可得的来源和哈希及缺项原因。用独立证据副本模拟遗漏项目资产和零匹配，验证非零退出并定位项目和目标。
- [x] 2.2 在同一模板副本上执行 `dotnet build --configuration Release --no-restore`，保存 Host DLL、`.deps.json` 和对应输出。生成 `host-output.json`，由还原图及 `.deps.json` 逐个核对应复制的框架运行 DLL、路径与 SHA-256，再由实际输出反查唯一包及资产，解释编译专用、工具和私有资产。在独立副本分别验证缺失 `.deps.json`、来源冲突、保留 `.deps.json` 仅移走 `Abp.Castle.Log4Net.dll`，各自须返回非零并点名对应文件或冲突来源。
  核对入口、各项目及包的实际解析边、SDK 选中的运行复制项和 SQL Server Provider 输出。验证删去框架依赖边或 SQL Server Provider 依赖声明，以及加入无来源的运行声明时的独立诊断。
- [x] 2.3 用 `package-gaps.json` 对照原版实测包图、框架十一项目及目标、R2 五包实物登记和六个候选缺口。核对原版和维护端关键依赖与资产差异，给出 SignalR/Log4Net、Module Zero、AutoMapper、同批候选和后续迁移的顺序及准入。归因超出预期的框架差异后，在 `docs/maintenance/r3-web-host-baseline.md` 记录范围和证据，并在 `docs/README.md` 核对入口。
  在相同源码声明下模拟不同解析版本，核对框架差异在拒绝通过前写入证据，以及第三方版本差异仍如实登记。

## 3. 首包集成验收

- [x] 3.1 在本机 macOS ARM64 的全新目录执行统一 R3 命令，回读 `report.json`、五份源资产、Host 依赖清单、输出摘要与缺口清单。核对实际命令和退出码、受测版本与 Provider、全部必需检查和上述负例的记录。证据明确列出未启动宿主、未执行数据库操作、未构建 Angular。
  首次验收通过后，从当轮证据提取 `docs/maintenance/r3-web-host-baseline.json` 并在验收文档中引用。逐项核对各项目与目标的项目引用、直接包声明和解析结果、应用包 ID、版本、依赖边、单列的 SDK 构建输入，以及输出 DLL 的相对路径、所属包、包内路径和 SHA-256。确认清单可脱离原工作站路径读取，复跑结果写到新的证据目录。
- [x] 3.2 检查主仓新增工具与文档范围，核对 R0、R1、R2 冻结证据及子仓输入身份，定向确认原有验证 profile 的参数分派。运行 `git diff --check` 和 `openspec-cn validate --all --strict --no-interactive`，记录实际结果。
