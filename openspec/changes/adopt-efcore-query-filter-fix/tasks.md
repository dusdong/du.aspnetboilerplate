# R1 首项补丁实施任务

## 1. 固定补丁输入

- [x] 1.1 在主仓 R1 维护记录中登记框架检出、gitlink、PR 基底与合并 SHA，按固定 Git 对象核对涉及的源码、测试和文档。记录等价实现、需移植的差异及来源，保留 R0 原记录。

## 2. 在框架子模块验收查询行为

- [x] 2.1 在 `Abp.EntityFrameworkCore` 及其测试项目吸收缺失的上游修复，在候选上核对普通查询的租户与软删除过滤结果。运行 SQLite 的 `ValueConverter` 用例，验证以自定义列值存储 `IsDeleted` 时返回全部预期活动记录且排除已删除记录。登记用例名、Provider 和 TRX 结果。
- [x] 2.2 在启用 `UseAbpQueryCompiler` 的修复候选上验收同步、异步显式编译查询的异常契约和无需上下文过滤的正常结果。在有效外层编译作用域内，分别通过真实 SQLite 的 `EF.CompileQuery` 和 `EF.CompileAsyncQuery` 验证内层缺少所需上下文时抛出 `AbpException`、未返回记录且外层上下文仍可用。更新并验证采用 `GetRequiredContext()` 的自定义过滤器示例。将嵌套、自定义过滤器及正常路径对应到实际用例和 TRX，记录外层作用域建立方式及 Provider。
- [x] 2.3 启用查询选项扩展，核实通过 `ReplaceService` 分别替换 `IDatabase`、`ICompiledQueryCacheKeyGenerator` 时，DbContext 初始化均抛出 `AbpException` 且消息指出 `ReplaceService`。核实默认关闭 `UseAbpQueryCompiler` 时普通查询与带过滤的同步、异步显式编译查询均返回预期记录。将配置变化写入使用说明，并登记各用例、Provider 与 TRX 结果。

## 3. 将候选与 R0 对照

- [x] 3.1 从同一框架候选还原五个项目和三套测试的完整依赖图，构建五个 Release 程序集。用 R0 工具比较解析到的包、程序集身份、公共 API 与资源，解释每项差异，核实测试专用依赖的影响范围。
- [x] 3.2 使用上述还原和构建结果运行 `Abp.Tests`、`Abp.AspNetCore.Tests`、`Abp.EntityFrameworkCore.Tests`。核对三份 TRX 的通过、失败、跳过及测试发现差异。新增覆盖必须实际执行；原有用例须能逐项解释新增跳过、消失或结果变化。
- [x] 3.3 在主仓 R1 维护记录汇总候选身份、执行命令、测试环境、各套件结果、API 与依赖结论，并从维护路线链接到该记录。核对增量规范的每个场景和相关差异，执行 OpenSpec 全量严格校验及 Git 差异检查。
