#!/usr/bin/env python3
"""用通过轮证据的独立副本核对 net10.0 构建入口的失败诊断。"""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_leaf_packages import checked_file
from r3_template_net10_upgrade import PATCH_VERSION, PROFILE, TFM, UpgradeBuildRun
from r3_web_host import PROVIDER, project_path, write_json
from verify import ROOT, VerificationError, read_json, require, sha256


CASES = {
    "net9-core-dll-in-output": ("output", "Migrator", "Du.Abp/10.5.1-r2.1", "Abp.dll", "SHA-256 不符"),
    "net9-provider-in-assets": ("assets", "Web.Host", PROVIDER, f"预期 {PATCH_VERSION}", "实际 9.0.5"),
}


def inspect_fixture(run, source, case):
    stage, project, *_ = CASES[case]
    if stage == "assets":
        registration = read_json(ROOT / "eng/r3_template_net9_reference.json")["originalAssets"][project]
        old = read_json(checked_file(run.frozen_root, registration["path"], registration["sha256"]))
        raw = read_json(source / f"raw-assets/{project}.project.assets.json")
        current, previous = f"{PROVIDER}/{PATCH_VERSION}", f"{PROVIDER}/9.0.5"
        for graph, before in ((raw["targets"][TFM], old["targets"]["net9.0"]),
                              (raw["libraries"], old["libraries"])):
            del graph[current]
            graph[previous] = before[previous]
        copied = run.evidence / f"{project}.project.assets.json"
        write_json(copied, raw)
        # 版本检查应在访问旧包缓存前拒绝。
        def unexpected_lookup(*args):
            raise AssertionError(f"版本不符时访问了包缓存：{args}")

        run.read_target(project, copied, unexpected_lookup)
        return

    verified_output = Path(read_json(source / "launch-manifest.json")[project]["cwd"])
    copied = run.evidence / "output"
    shutil.copytree(verified_output, copied)
    core = run.frozen["Du.Abp"]
    archive_path = checked_file(source / "frozen-feed", core["feedCopy"], core["archiveSha256"])
    with ZipFile(archive_path) as archive:
        (copied / "Abp.dll").write_bytes(archive.read("lib/net9.0/Abp.dll"))
    require(sha256(copied / "Abp.dll") != core["assetSha256"], "负例未置换为不同的核心 DLL")
    items = read_json(source / f"{project}-compile-selection.log")["Items"]
    items.update(read_json(source / f"{project}-runtime-selection.log")["Items"])
    target = read_json(source / "assets-inventory.json")[project]
    run.read_output(project, copied, target, items)


def reject_fixture(source, evidence, frozen_root, case):
    stage, project, *_ = CASES[case]
    run = UpgradeBuildRun(ROOT, evidence, frozen_root)
    run.root = source / "source/aspnet-core"
    run.cache = source / "packages"
    run.frozen = read_json(source / "frozen-packages.json")
    try:
        run.step(stage, inspect_fixture, run, source, case)
    except VerificationError as error:
        run.report.update(status="failed", exitCode=1, reason=str(error), project=project)
        run.save()
        print(f"{project_path(project)} {TFM}：{error}", file=sys.stderr)
        return 1
    raise AssertionError(f"{case} 未被拒绝")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("frozen_root", type=Path)
    parser.add_argument("--fixture", choices=CASES)
    args = parser.parse_args()
    source, evidence, frozen = args.source.resolve(), args.evidence.resolve(), args.frozen_root.resolve()
    passed = read_json(source / "report.json")
    require(passed["status"] == "build_verified" and passed["profile"] == PROFILE, f"需要已通过的构建轮：{source}")
    evidence.mkdir(parents=True)
    if args.fixture:
        return reject_fixture(source, evidence, frozen, args.fixture)
    results = {}
    for case, (stage, project, *expectations) in CASES.items():
        target = evidence / case
        command = [sys.executable, "-B", str(Path(__file__).resolve()), str(source), str(target), str(frozen),
                   "--fixture", case]
        result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        log = target / "result.log"
        log.write_text(result.stdout, encoding="utf-8")
        report = read_json(target / "report.json")
        results[case] = {"argv": command, "cwd": str(ROOT), "exitCode": result.returncode,
                         "report": str(target / "report.json"), "log": str(log)}
        write_json(evidence / "diagnostics.json", results)
        require(report["status"] == "failed" and report["project"] == project
                and result.returncode == report["exitCode"] == report["stages"][stage]["exitCode"] == 1
                and all(value in result.stdout for value in (stage, project, *expectations))
                and all(row["status"] == "not_run" for step, row in report["stages"].items() if step != stage),
                f"{case} 的失败证据不符：{log}")
        print(f"{case}：退出 1，命中 {stage} / {project} / {expectations[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
