# Spec Delta

## ADDED Requirements

### Requirement: 固定 Angular 19 模板可验收从经典框架 Git 制成的资源包

验收 SHALL 以公开 `abp-web-resources 6.1.0` 为对照，核实由登记的经典框架 Git 资源制成的同名同版本本地 tarball，并在固定免费模板、Angular `19.2.1` 和公开 `abp-ng2-module 12.1.0` 组合中核实资源实际消费。

#### Scenario: 资源归档可追溯到登记的 Git 对象

- **WHEN** 从固定经典框架 Git 子树制成 npm 候选包
- **THEN** 包内每个 `Abp/Framework` 文件的相对路径和字节摘要逐项匹配 Git blob，包装文件各有登记的来源和改动，归档有独立摘要及逐文件清单
- **AND** 对公开归档记录资源的路径、原始字节比较和换行差异，以及两侧各自的包装清单。仅用于解释差异的换行归一化不会进入打包输入或替代原始字节核验

#### Scenario: 模板实际安装候选且只有资源包发生替换

- **WHEN** 以公开资源包和本地 tarball 对照同一固定模板
- **THEN** 候选解析指向本次本地归档，实际安装树按相对路径和字节摘要逐项匹配该归档，其他锁解析和实际安装依赖图等价，模板与工具链身份一致
- **AND** 实测归档 manifest 的包名、版本、`main` 和依赖与登记契约相符。分别记录 registry 的 `types` 值和实际归档 `package.json` 未声明 `types` 或 `typings` 的结果。按模板两条显式引用核实已安装候选的 `abp.d.ts` 和 `abp.signalr.d.ts`，记录实际解析路径和摘要

#### Scenario: Production 构建使用候选全局脚本并复制资产

- **WHEN** 从已确认候选身份的隔离模板运行原 production 配置
- **THEN** 新构建成功，产物证据表明全局脚本使用已安装候选的 `abp.js` 和 `abp.moment.js`，保持模板的真实加载顺序及本地 SweetAlert 和 Freeze UI 脚本来源。生成的 `/assets/abp/abp.signalr.js` 与 `/assets/abp/abp.signalr-client.js` 分别按字节匹配候选包内对应文件

#### Scenario: 浏览器从本轮静态输出运行全局脚本

- **WHEN** 在本机浏览器从本次 production 输出加载实际全局脚本，并请求两条静态资源 URL
- **THEN** `window.abp.utils.formatString('ABP {0} / {1}', 'R5', '资源')` 返回 `ABP R5 / 资源`，两条 URL 均返回成功且响应正文摘要分别匹配本次产物与候选包。浏览器结果仅覆盖已观察到的全局脚本行为和静态服务

#### Scenario: 归档身份、可比性或消费证据缺失

- **WHEN** 冻结输入或网络依赖不可用，归档、实装文件或其他依赖身份偏离，或声明解析、构建、脚本归属、浏览器结果及静态响应证据缺失或偏离
- **THEN** 保留实际失败阶段、命令退出码或浏览器断言、预期值和实测值。记录输入阻塞、身份或可比性失配、构建失败及运行验收失败的实际原因。依赖失败条件的后续步骤记为未执行，完整验收结果不得判为通过
