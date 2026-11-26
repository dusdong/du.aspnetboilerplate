#!/usr/bin/env python3
"""用正式通过轮的独立观测副本核对 R4 资产对账的拒绝条件。"""

import argparse
from copy import deepcopy
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r4_candidate_batch import load_frozen_batch
from r4_template_assets import verify_build_entry, verify_process
from r4_template_consumer import PLAN, planning_inputs
from r3_web_host import write_json
from verify import ROOT, VerificationError, read_json, require, sha256


def reject(case, fragment, action):
    try:
        action()
    except VerificationError as error:
        require(fragment in str(error), f"{case} 的拒绝阶段不符：{error}")
        print(f"{case}：按预期拒绝", flush=True)
        return {"outcome": "rejected", "reason": str(error)}
    raise AssertionError(f"{case} 未被拒绝")


def execute(args):
    run = args.upgrade_run
    inputs = read_json(run / "report.json")
    batch = load_frozen_batch(args.batch_root)
    inspection = read_json(args.batch_root / batch["inspection"]["path"])
    graphs = read_json(run / "assets-inventory.json")
    planned = read_json(run / "launch-manifest.json")
    evidence = read_json(args.entry_assets)
    require(evidence["batchSha256"] == sha256(args.batch_root / "batch.json")
            and evidence["originalReports"]["upgrade"]["sha256"] == sha256(run / "report.json"),
            "专项诊断需要同批已核对通过的正式升级报告")
    builds = evidence["entryPoints"]["net10"]
    cases = {}

    def with_rows(label, name, **changes):
        path = run / f"net10-{label}-loaded.json"
        data = read_json(path)
        rows = data["assemblies"]
        row, = (row for row in rows if row["name"] == name)
        if changes:
            row.update(changes)
        else:
            rows.remove(row)
        return data

    migrator = inputs["sql"]["migrations"]["net10"]["launch"]
    host = inputs["rounds"]["net10"]["host"]
    cases["migrator-wrong-loaded-path"] = reject(
        "migrator-wrong-loaded-path", "Du.Abp 实际加载 DLL 来源不符",
        lambda: verify_process(builds["Migrator"], migrator,
                               with_rows("migrator", "Abp", path="/different/Abp.dll")))
    cases["migrator-wrong-loaded-digest"] = reject(
        "migrator-wrong-loaded-digest", "Du.Abp 实际加载 DLL 摘要不符",
        lambda: verify_process(builds["Migrator"], migrator, with_rows("migrator", "Abp", sha256="0" * 64)))
    cases["migrator-required-assembly-missing"] = reject(
        "migrator-required-assembly-missing", "Abp.ZeroCore 加载记录应唯一，实际 []",
        lambda: verify_process(builds["Migrator"], migrator, with_rows("migrator", "Abp.ZeroCore")))
    cases["host-required-assembly-missing"] = reject(
        "host-required-assembly-missing", "AutoMapper 加载记录应唯一，实际 []",
        lambda: verify_process(builds["Web.Host"], host, with_rows("host", "AutoMapper")))

    graph = deepcopy(graphs["Migrator"])
    graph["compileReferences"]["Abp.dll"][0]["path"] = "/different/Abp.dll"
    cases["migrator-wrong-compile-origin"] = reject(
        "migrator-wrong-compile-origin", "编译或输出 DLL 来源不符",
        lambda: verify_build_entry(run, inputs["inputs"], "Migrator", args.batch_root, batch, inspection,
                                   graph, planned["Migrator"]))
    graph = deepcopy(graphs["Migrator"])
    graph["compileReferences"]["Abp.dll"][0]["sha256"] = "0" * 64
    cases["migrator-wrong-compile-digest"] = reject(
        "migrator-wrong-compile-digest", "编译或输出 DLL 摘要不符",
        lambda: verify_build_entry(run, inputs["inputs"], "Migrator", args.batch_root, batch, inspection,
                                   graph, planned["Migrator"]))

    expected_optional = {
        "Migrator": {"Du.AutoMapper", "Du.AutoMapper.Collection", "Du.Abp.AutoMapper"},
        "Web.Host": {"Du.AutoMapper.Collection"},
    }
    for phase, entries in evidence["entryPoints"].items():
        for entry, result in entries.items():
            output_only = {name for name, row in result["packages"].items() if row["state"] == "output_only"}
            require(output_only == expected_optional[entry] and
                    all(row["loadRequired"] or name in expected_optional[entry]
                        for name, row in result["packages"].items()), f"{phase} {entry} 的仅输出边界不符")
    cases["optional-assembly-recorded-output-only"] = {"outcome": "passed"}

    observed = inputs["inputs"]
    current = planning_inputs(ROOT, observed["executionCommit"], observed["executionTree"])
    require(current["change"] == PLAN.name and current["execution"]["commit"] == observed["executionCommit"]
            and current["coordinator"]["commit"] == batch["gitlinkCommit"],
            "正常入口的规划、协调提交和执行提交归属不符")
    cases["r4-plan-and-execution-origin"] = {"outcome": "passed"}
    cases["wrong-execution-tree"] = reject(
        "wrong-execution-tree", "R4 规划或执行 Git 树不符",
        lambda: planning_inputs(ROOT, observed["executionCommit"], "0" * 40))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    require(not args.output.exists(), "诊断输出已存在")
    write_json(args.output, {"batchSha256": evidence["batchSha256"],
                             "entryAssetsSha256": sha256(args.entry_assets), "cases": cases})
    print(f"{len(cases)} 项 R4 资产与规划来源诊断通过")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("batch-root", "upgrade-run", "entry-assets", "output"):
        parser.add_argument("--" + name, required=True, type=lambda value: Path(value).resolve())
    execute(parser.parse_args())


if __name__ == "__main__":
    main()
