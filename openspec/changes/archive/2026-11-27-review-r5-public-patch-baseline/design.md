# 公开版本审查的输入与判定

## Context

发行标签 `v10.5.2` 指向 `cebc3e38`，安装指南固定于 `ab4957bb`，归档与交付记录对应 `0d42db5`。发行附件 `R5-PACKAGE-CHECKSUMS.json` 分列三个新包、十个沿用包，并登记生产提交、签后下载摘要和公开消费报告。三包在模板中的实际解析位置见归档。[发行与附件](../../../../docs/maintenance/r5-public-release.md) · [消费报告及摘要](../2026-11-27-publish-r5-mapping-patch/consumption-validation.md)

## Goals / Non-Goals

本轮交付供存量应用维护者查阅的 `v10.5.2` 审查记录，涵盖发行身份、四入口依赖变化、公告适用性、消费者行动和续查起点。产品补丁、发布及平台扩展各自依据本轮发现另行决定。

## Decisions

1. **取同一次公开升级的四张图。** 验证机原始目录为主仓 Git 目录下的 `publish-r5-mapping-patch/publisher-consumption/runs/r5-template-upgrade-h1h2hp6e/`。先核对归档登记的 `upgrade` 报告摘要，再读 `net9-build/raw-assets/` 与 `raw-assets/` 下的 `Web.Host.project.assets.json` 和 `Migrator.project.assets.json`。登记各图摘要、直接与传递包、版本及引入路径。两代 Web.Host 原报告分别为 116、94 个包，两代 Migrator 为 81、66 个。相同总数也可能对应不同依赖，按入口逐条和 R4 对照。[R4 四图与输入](../../../../docs/maintenance/r5-runtime-migration-review.md#公开发行和历史证据)
2. **区分 fork 版本与上游比较点。** 将三份新签后包绑定到本版发行树，把十份沿用包对回 R4 签后摘要。四图中的每个包按实际 ID 和解析版本匹配。维护包另按上游原包 ID 收集公告，用对应上游 tag 的版本判定区间。例如，`Du.AutoMapper 14.0.1` 对应的原包查询为 `AutoMapper`，比较版本为 `14.0.0`。记录两组 ID 和版本、上游 tag 及提交，再用本版生产源码差异和实包证据判断命中项是否适用或已回补。分别记录图中存在、输出携带和进程实际加载的资产。[上游基点和别名](../../../../docs/maintenance/r5-first-maintenance-review.md#发行版本和上游基点)
3. **分别接续各来源。** 六条上游分支按上次终点 SHA 续查提交、发行和仓库公告。按 NuGet 全部有效公告页和 GitHub Advisory Database 完整匹配新图，包括早于本次发行的条目。GitHub 修订从 `2026-11-26T10:08:06Z` 重叠查询，Microsoft 从上次查询窗口起点 `10:08:04Z` 接续，结合实际加载的 .NET 与 ASP.NET Core 版本判断。单列 CVE-2026-56158 的原始组件、版本区间及修订证据。[各来源续查位置](../../../../docs/maintenance/r5-runtime-migration-review.md#共享运行时与下轮检查点)
4. **接续上轮未决项。** 从上轮逐项处置表带入 AutoMapper #4604、#4607 / #4567、#4605、#4655。即使六条分支均无新增提交，也按原复查条件核对本版证据。例如，#4604 关注可空扩展方法与 `MapAtRuntime` 的组合，#4607 / #4567 关注开放泛型注册顺序。每项注明条件是否满足、维持或变更处置的依据以及对本轮补丁决定的影响。仍暂缓或待核实的事项保留下次复查条件。[上轮逐项处置](../../../../docs/maintenance/r5-first-maintenance-review.md#逐项处置)
5. **按受影响对象给出行动。** 有维护包修复证据时，写明负责子仓、消费者影响与定向实包验收。行动仅涉及运行环境或模板时，说明适用组合及复查方法。结论归为需补丁、无需补丁或暂不能判定，附下次重查条件。发布者新装、同库接续和独立安装保留原运行日期及报告。

## Risks / Trade-offs

- 原图缺失或摘要失配时，登记受影响的 TFM、入口及缺项。需要补图时，沿用归档 `upgrade` 的固定模板、批次、发行清单、已验签下载登记和独立摘要，在新的证据目录运行下列公开源构建。按缺图目标将 `TFM` 设为 `net9.0` 或 `net10.0`。`net9.0` 使用原升级流程的 `PatchNet9Build`。从本次构建的 `raw-assets/` 取对应入口的图，单列新输入、摘要和可核对的差异，保留原升级报告的历史状态。[公开验收参数](../2026-11-26-prepare-r5-mapping-patch-release/release-handoff.md#正式公开后的验收) · [构建入口](../../../../eng/r5_template_consumer.py)

  ```sh
  "$R5_PYTHON" -B eng/r5_template_consumer.py build --tfm "$TFM" \
    --batch-root "$R5_BATCH" --batch-sha256 "$R5_BATCH_SHA" --frozen-root .git \
    --release-manifest "$R5_MANIFEST" --manifest-sha256 "$R5_MANIFEST_SHA" \
    --verified-downloads "$R5_RELEASE_WORK/verified-downloads.json" --downloads-sha256 "$R5_DOWNLOADS_SHA" \
    --evidence-root "$R5_TEMPLATE_EVIDENCE"
  ```

- 公告页缺失、分页未完或官方仍未披露组件范围时，保留该来源最后完整位置，说明对本轮判断的影响。目标环境变化时，仅在对应部署组合取得实测后更新支持范围。
