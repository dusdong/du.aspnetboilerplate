"""在隔离目录用原始通过轮和已登记的交接校验和复核 R4 消费。"""

import argparse
from pathlib import Path
import re

from r3_leaf_packages import checked_file
from r3_template_net10_runtime import VERSIONS, verify_migrator_assemblies
from r3_template_net9_runtime import verify_host_assemblies
from r3_web_host import artifact, write_json
from r4_candidate_batch import load_frozen_batch
from r4_template_assets import ENTRY_LABELS, verify_build_directory, verify_process
from r4_template_consumer import planning_inputs
from verify import ROOT, read_json, require, sha256


def read_receipt(root, digest):
    receipt = checked_file(root, "SHA256SUMS", digest)
    files = {}
    for line in receipt.read_text(encoding="utf-8").splitlines():
        checksum, name = line.split("  ", 1)
        path = Path(name)
        require(re.fullmatch(r"[0-9a-f]{64}", checksum) and not path.is_absolute()
                and ".." not in path.parts and path.as_posix() not in files, f"原交接校验表路径或摘要不符：{name}")
        files[path.as_posix()] = checksum
    return files


def verify_original(root, receipt, path, original):
    recorded = checked_file(root, path, receipt[path])
    require(sha256(original) == sha256(recorded), f"{original} 与原交接摘要不符")
    return {"path": path, "sha256": receipt[path]}


def execute(args):
    batch = load_frozen_batch(args.batch_root)
    batch_sha = sha256(args.batch_root / "batch.json")
    inspection = read_json(args.batch_root / batch["inspection"]["path"])
    receipt = read_receipt(args.prior_handoff, args.prior_checksums_sha256)
    verify_original(args.prior_handoff, receipt, "frozen/batch.json", args.batch_root / "batch.json")
    run, rollback_run = args.upgrade_run, args.rollback_run
    paths = {"upgrade": ("evidence/upgrade/report.json", run / "report.json"),
             "net9Build": ("evidence/upgrade/net9-build/report.json", run / "net9-build/report.json"),
             "rollback": ("evidence/rollback/report.json", rollback_run / "report.json")}
    retained = {label: verify_original(args.prior_handoff, receipt, name, path)
                for label, (name, path) in paths.items()}
    reports = {label: read_json(path) for label, (_, path) in paths.items()}
    up, net9, back = (reports[name] for name in ("upgrade", "net9Build", "rollback"))
    require([item["profile"] for item in (up, net9, back)] ==
            ["r4-template-upgrade", "r4-template-build", "r4-template-original-rollback"]
            and [item["status"] for item in (up, net9, back)] == ["passed", "build_verified", "passed"]
            and all(item["exitCode"] == 0 and item["inputs"]["r4Batch"]["sha256"] == batch_sha
                    for item in reports.values()), "正式原报告的批次或通过状态不符")
    require(back["inputs"]["upgrade"]["sha256"] == retained["upgrade"]["sha256"]
            and back["inputs"]["upgrade"]["runId"] == up["runId"]
            and up["inputs"]["net9Build"]["sha256"] == retained["net9Build"]["sha256"]
            and up["inputs"]["nuget"]["globalPackages"] != net9["inputs"]["nuget"]["globalPackages"],
            "两个独立构建或回退报告与升级报告未绑定")
    execution = {(item["inputs"]["executionCommit"], item["inputs"]["executionTree"]) for item in reports.values()}
    require(len(execution) == 1, "三个正式报告的实际 Git 执行基点不一致")
    ((commit, tree),) = execution
    plan = planning_inputs(ROOT, commit, tree)

    build_outputs = {}
    for phase, prefix, directory, report in (("net9", "net9-build/", run / "net9-build", net9),
                                             ("net10", "", run, up)):
        for name in ("assets-inventory.json", "launch-manifest.json", *(f"{entry}-output.json" for entry in ENTRY_LABELS)):
            verify_original(args.prior_handoff, receipt, f"evidence/upgrade/{prefix}{name}", directory / name)
        outputs = verify_build_directory(directory, report["inputs"], args.batch_root, batch, inspection)
        for entry, build in outputs.items():
            observation = run / f"{phase}-{ENTRY_LABELS[entry]}-loaded.json"
            observed = read_json(observation)
            source = verify_original(args.prior_handoff, receipt, f"evidence/upgrade/{observation.name}", observation)
            manifest = read_json(directory / f"{entry}-output.json")
            output = Path(build["output"])
            if entry == "Web.Host":
                launch = up["rounds"][phase]["host"]
                verify_host_assemblies(observed, launch, output, manifest, {}, runtime_version=VERSIONS[phase])
            else:
                launch = up["sql"]["migrations"][phase]["launch"]
                verify_migrator_assemblies(observed, launch, output, manifest, {}, VERSIONS[phase])
            outputs[entry] = verify_process(build, launch, observed) | {"observation": source}
        build_outputs[phase] = outputs

    for role, checkpoint in up["sql"]["checkpoints"].items():
        name = Path(checkpoint["media"]["serverPath"]).name
        registered = back["inputs"]["upgrade"]["checkpoints"][role]
        path = checked_file(args.prior_handoff, f"sql-media/{name}", receipt[f"sql-media/{name}"])
        require(sha256(path) == registered["sha256"] == checkpoint["media"]["sha256"]
                and checkpoint["recovered"]["backupSetId"] == registered["backupSetId"]
                == checkpoint["media"]["backupSetId"]
                and back["paths"][role]["status"] == "passed"
                and back["paths"][role]["browser"]["readTarget"]["verified"], f"{role} 回退记录与恢复介质不符")

    args.output.mkdir()
    for item in plan["artifacts"]:
        copy = args.output / "planning" / Path(item["path"]).relative_to(plan["changePath"])
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(checked_file(ROOT, item["path"], item["sha256"]).read_bytes())
    write_json(args.output / "planning-provenance.json", {
        "mode": "read_only_correction", "batchSha256": batch_sha, "priorChecksumsSha256": args.prior_checksums_sha256,
        "originalReports": retained, "r4Planning": plan,
        "originalPlanningFields": {label: {key: report["inputs"][key] for key in
                                           ("planning", "planningCommit", "planningTree") if key in report["inputs"]}
                                   for label, report in reports.items()},
    })
    write_json(args.output / "template-entry-assets.json", {
        "mode": "read_only_recheck", "status": "passed", "exitCode": 0, "batchSha256": batch_sha,
        "originalReports": retained,
        "planningProvenance": artifact(args.output / "planning-provenance.json", args.output),
        "entryPoints": build_outputs,
    })
    print(f"R4 原始通过轮的四个入口通过只读复核：{args.output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("batch-root", "upgrade-run", "rollback-run", "prior-handoff", "output"):
        parser.add_argument("--" + name, required=True, type=lambda value: Path(value).resolve())
    parser.add_argument("--prior-checksums-sha256", required=True)
    execute(parser.parse_args())


if __name__ == "__main__":
    main()
