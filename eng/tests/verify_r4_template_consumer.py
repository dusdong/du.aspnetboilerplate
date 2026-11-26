#!/usr/bin/env python3
"""用独立输入副本验证 R4 消费入口能拒绝缺包、混装与串批回退。"""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_leaf_packages import checked_file
from r3_template_net9_runtime import ORIGINAL, ORIGINAL_REPORT
from r3_template_original_rollback import RollbackRun
from r3_web_host import artifact, write_json
from r4_candidate_batch import load_frozen_batch
from r4_template_consumer import CHECKPOINTS
from verify import ROOT, read_json, require, sha256
from verify_r3_template_net9_packages import reject_original_package


def command(case, stage, diagnostic, argv, output, cases):
    argv = [sys.executable, "-B", *map(str, argv)]
    log = output / case / "result.log"
    log.parent.mkdir(exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    report, = (log.parent / "runs").glob("*/report.json")
    state = read_json(report)
    require(result.returncode == state["exitCode"] == 1 and state["status"] == "failed"
            and state["stages"][stage]["status"] == "failed" and diagnostic in state["reason"],
            f"{case} 缺少预期拒绝证据：{log}")
    require(all(state["stages"].get(name, {}).get("status", "not_run") == "not_run"
                for name in ("restore", "build", "output", "restore_pair", "observer_build", "after_upgrade")),
            f"{case} 继续执行了后续还原、构建或运行")
    cases[case] = {"argv": argv, "cwd": str(ROOT), "exitCode": result.returncode,
                   "stage": stage, "diagnostic": diagnostic, "log": artifact(log, output),
                   "report": artifact(report, output)}
    print(f"{case}：退出 1，命中 {stage} / {diagnostic}", flush=True)


def execute(args):
    output = args.evidence_root
    output.mkdir()
    cases = {}
    batch = load_frozen_batch(args.batch_root)
    core = batch["packages"]["Du.Abp"]["archive"]["path"]
    reference = read_json(ROOT / "eng/r3_template_net9_reference.json")
    old = next(row for group in reference["batches"].values() for row in group["packages"] if row["id"] == "Du.Abp")
    old_archive = checked_file(args.frozen_root, old["archive"], old["archiveSha256"])
    entry = ROOT / "eng/r4_template_consumer.py"

    for case, diagnostic in (
        ("missing-package", Path(core).name),
        ("old-candidate-extra", old_archive.name),
        ("old-candidate-replacement", "SHA-256 不符"),
    ):
        fixture = output / case / "frozen"
        shutil.copytree(args.batch_root, fixture)
        if case == "missing-package":
            (fixture / core).unlink()
        elif case == "old-candidate-extra":
            shutil.copyfile(old_archive, fixture / "feed" / old_archive.name)
        else:
            shutil.copyfile(old_archive, fixture / core)
        command(case, "packages", diagnostic,
                [entry, "build", "--tfm", "net9.0", "--batch-root", fixture, "--frozen-root", args.frozen_root,
                 "--evidence-root", fixture.parent / "runs"], output, cases)

    case = "original-package-in-assets"
    fixture = output / case
    fixture.mkdir()
    code = reject_original_package(args.upgrade_run / "net9-build", fixture)
    report = fixture / "report.json"
    state = read_json(report)
    require(code == state["exitCode"] == 1 and state["stages"]["assets"]["status"] == "failed"
            and "还原混入不允许的包：Abp/10.2.0" in state["reason"], "原版包没有在资产阶段被拒绝")
    cases[case] = {"exitCode": code, "stage": "assets", "report": artifact(report, output)}

    registration = args.upgrade_run / CHECKPOINTS
    lock = read_json(registration)
    settings = read_json(args.runtime_config)
    for case, stage, fragment in (
        ("historical-upgrade-report", "upgrade_inputs", "report.json SHA-256 不符"),
        ("foreign-batch-registration", "upgrade_inputs", "升级登记与 R4 冻结批次摘要不符"),
        ("swapped-backup", "sql_preflight", "SHA-256 不符"),
    ):
        fixture = output / case
        fixture.mkdir()
        upgrade_run = args.upgrade_run
        config_file = args.runtime_config
        lock_sha = sha256(registration)
        if case == "historical-upgrade-report":
            upgrade_run = fixture
            shutil.copyfile(registration, fixture / CHECKPOINTS)
            shutil.copyfile(args.historical_upgrade / "report.json", fixture / "report.json")
        elif case == "foreign-batch-registration":
            upgrade_run = fixture
            counterfeit = lock | {"batchSha256": sha256(args.historical_upgrade / "report.json")}
            write_json(fixture / CHECKPOINTS, counterfeit)
            lock_sha = sha256(fixture / CHECKPOINTS)
        else:
            media = Path(settings["localBackupDirectory"])
            swapped = fixture / "media"
            swapped.mkdir()
            after, before = (lock["checkpoints"][role]["name"] for role in ("after_upgrade", "before_upgrade"))
            shutil.copyfile(media / before, swapped / after)
            shutil.copyfile(media / after, swapped / before)
            config_file = fixture / "config.json"
            write_json(config_file, settings | {"localBackupDirectory": str(swapped)})
        command(case, stage, fragment,
                [entry, "rollback", "--batch-root", args.batch_root, "--frozen-root", args.frozen_root,
                 "--evidence-root", fixture / "runs", "--runtime-config", config_file,
                 "--upgrade-run", upgrade_run, "--rollback-inputs-sha256", lock_sha], output, cases)

    case = "historical-rollback-inputs"
    fixture = output / case
    fixture.mkdir()
    historical = RollbackRun(ROOT, fixture, args.frozen_root, args.historical_upgrade, args.runtime_config)
    original = checked_file(args.frozen_root, ORIGINAL / "report.json", ORIGINAL_REPORT)
    historical.business = read_json(original)["sql"]["expected"]
    historical.step("upgrade_inputs", historical.upgrade_inputs)
    require(historical.report["stages"]["upgrade_inputs"]["status"] == "passed", "R3 固定升级输入无法读取")
    cases[case] = {"exitCode": 0, "stage": "upgrade_inputs", "report": artifact(historical.report_path, output)}
    load_frozen_batch(args.batch_root)
    write_json(output / "diagnostics.json", {"batchSha256": sha256(args.batch_root / "batch.json"), "cases": cases})
    print(f"{len(cases)} 项 R4 与历史输入诊断通过", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("batch-root", "frozen-root", "upgrade-run", "historical-upgrade", "runtime-config", "evidence-root"):
        parser.add_argument(f"--{name}", required=True, type=lambda value: Path(value).resolve())
    execute(parser.parse_args())


if __name__ == "__main__":
    main()
