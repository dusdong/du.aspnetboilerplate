# 公开 R4 与 R5 映射消费者

在 macOS ARM64 上准备 Git、Python 3、.NET SDK `10.0.404` 和 .NET 运行时 `10.0.15`。在包含本入口的主仓检出根目录执行。固定模板的五份编译源码和应用模块原件从 Git 对象 `2e9536872673a7ff1986a19e798c51684d16afe5` 提取。

```sh
git submodule update --init -- module-zero-core-template
INPUT_DIR="$(mktemp -d "$(git rev-parse --absolute-git-dir)/public-mapping.XXXXXX")"
curl -fL https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.1/R4-PACKAGE-CHECKSUMS.json \
  -o "$INPUT_DIR/R4-PACKAGE-CHECKSUMS.json"
curl -fL https://github.com/dusdong/du.aspnetboilerplate/releases/download/v10.5.2/R5-PACKAGE-CHECKSUMS.json \
  -o "$INPUT_DIR/R5-PACKAGE-CHECKSUMS.json"
python3 -B eng/r5_public_mapping_consumer.py \
  --r4-checksums "$INPUT_DIR/R4-PACKAGE-CHECKSUMS.json" \
  --r5-checksums "$INPUT_DIR/R5-PACKAGE-CHECKSUMS.json" \
  --output "$INPUT_DIR/r4-r5"
```

需要指定其他已安装的宿主时传入 `--dotnet /绝对路径/dotnet`。选择尚不存在、所在磁盘有空间的 `--output` 目录。入口分别复制源码和公开附件，只使用 nuget.org 从各自空缓存还原，独立 Release 构建和运行。每个探针开启自己的内存 SQLite 数据库并在退出时释放。

- 根 `report.json` 记录两侧阶段退出码和探针退出码，`graph-difference.json` 记录包图差异。
- 各侧 `report.json` 记录环境、命令和逐项预期与实测，`consumer/obj/project.assets.json` 为原始还原图，`verified-public-archives.json` 和 `mapping-loaded.json` 对账签后主包、所选资产、Release 输出和实际加载文件。
- 各侧 `process/probe.json` 记录对象身份、查询表达式、执行 SQL、参数、真实列顺序和物化行。入口在失败时返回非零，保留已获取的结果和未执行项。
- 各侧 `inputQualification` 记录输入校验状态并说明失败原因。标为 `unqualified` 的业务项保留观测值及其判定，但不计入验收。总报告的 `usableForVersionConclusion` 表明该轮能否用于版本结论。

定向投影反例可以复制 [取列预期](projection-columns.json)，仅在副本中交换首两列，再用新输出目录和 `--r4-projection-columns` 传入副本。两侧仍实际执行查询，R4 会在物化后报出列顺序差异。正式复跑使用默认取列预期。

历史原版及冻结批次入口的默认目标为 `net9.0` 和 EF Core SQLite `9.0.18`，按既有记录复跑。[原版业务基线](../../docs/maintenance/r3-automapper-baseline.md) · [冻结批次消费者](../../openspec/changes/archive/2026-11-26-fix-r5-automapper-collection-context/three-package-validation.md#消费复跑)
