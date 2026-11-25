#!/usr/bin/env python3
"""从一次通过的候选构建生成三条独立失败证据。"""

from pathlib import Path
import shutil
import subprocess
import sys


sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_automapper_packages import stack_package
from r3_template_net9_packages import CandidateRun, PROFILE, TFM
from r3_web_host import NUGET_SOURCE, package_hashes, project_path, write_json
from verify import ROOT, VerificationError, read_json, require


REFERENCE = ROOT / "eng/r3_template_net9_reference.json"
PACKAGE = "Du.Abp"
CASES = {
    "missing-frozen-package": ("packages", "缺少实物"),
    "archive-sha256-mismatch": ("packages", "SHA-256 不符"),
    "original-package-in-assets": ("assets", "还原混入不允许的包"),
}


def copy_inputs(root, fixture, diagnostic):
    rows = read_json(REFERENCE)["batches"].values()
    paths = [row["path"] for batch in rows for row in batch["manifests"].values()]
    packages = [row for batch in rows for row in batch["packages"]]
    for path in paths + [row["archive"] for row in packages if row["id"] != PACKAGE]:
        target = fixture / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / path, target)
    record = next(row for row in packages if row["id"] == PACKAGE)
    path = fixture / record["archive"]
    if diagnostic == "archive-sha256-mismatch":
        shutil.copyfile(root / record["archive"], path)
        with path.open("ab") as stream:
            stream.write(b"independent-diagnostic-copy")
    return path.name


def reject_original_package(run_dir, fixture_dir):
    run = CandidateRun(ROOT, fixture_dir, ROOT / ".git")
    run.root = run_dir / "source/aspnet-core"
    run.cache = run_dir / "packages"
    run.config = run_dir / "NuGet.Config"
    run.feed = run_dir / "frozen-feed"
    run.frozen = read_json(run_dir / "frozen-packages.json")
    project = "Core"
    assets = read_json(run_dir / f"raw-assets/{project}.project.assets.json")
    old_key = "Abp/10.2.0"
    current_key = f"{PACKAGE}/{run.frozen[PACKAGE]['version']}"
    graph = assets["targets"][TFM]
    graph[old_key] = graph.pop(current_key)
    assets["libraries"][old_key] = assets["libraries"].pop(current_key)
    for item in graph.values():
        dependencies = item.get("dependencies", {})
        if PACKAGE in dependencies:
            dependencies.pop(PACKAGE)
            dependencies["Abp"] = "10.2.0"
    copy = fixture_dir / f"{project}.project.assets.json"
    write_json(copy, assets)

    def lookup(key, relative):
        source = str(run.feed) if stack_package(key.split("/")[0]) else NUGET_SOURCE
        return package_hashes(run.cache, key, relative, source)

    try:
        run.step("assets", run.read_target, project, copy, lookup)
    except VerificationError as error:
        run.report.update(status="failed", exitCode=1, reason=str(error))
        run.save()
        print(f"{project_path(project)} {TFM}：{error}", file=sys.stderr)
        return 1
    raise AssertionError("原版包回流未被拒绝")


def main():
    if sys.argv[1] == "--original-fixture":
        return reject_original_package(*(Path(arg).resolve() for arg in sys.argv[2:]))
    run, evidence, frozen = (Path(arg).resolve() for arg in sys.argv[1:])
    require(read_json(run / "report.json")["status"] == "build_verified", f"候选构建证据未通过：{run}")
    evidence.mkdir(parents=True)
    records = {}
    for name, (stage, fragment) in CASES.items():
        fixture = evidence / name
        fixture.mkdir()
        if name == "original-package-in-assets":
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "--original-fixture", str(run), str(fixture)]
            identity = "Abp/10.2.0"
            mode = "mutated_asset_fixture"
        else:
            copies = fixture / "frozen"
            identity = copy_inputs(frozen, copies, name)
            command = [sys.executable, "-B", "eng/verify.py", "--profile", PROFILE,
                       "--evidence-root", str(fixture / "runs"), "--frozen-root", str(copies)]
            mode = "real_profile"
        result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        log = fixture / "result.log"
        log.write_text(result.stdout, encoding="utf-8")
        report_file = (fixture / "report.json" if mode == "mutated_asset_fixture"
                       else next((fixture / "runs").glob("*/report.json")))
        report = read_json(report_file)
        records[name] = {"mode": mode, "argv": command, "cwd": str(ROOT), "exitCode": result.returncode,
                         "report": str(report_file), "log": str(log), "diagnostics": [stage, fragment, identity]}
        write_json(evidence / "diagnostics.json", records)
        require(result.returncode == report["exitCode"] == 1 and report["status"] == "failed"
                and all(value in result.stdout for value in (stage, fragment, identity))
                and report["stages"][stage]["exitCode"] == 1
                and all(row["status"] == "not_run" for step, row in report["stages"].items()
                        if step in ("build", "output", "inputs_after")),
                f"{name} 的失败证据不符：{log}")
        print(f"{name}：退出 1，命中 {stage} / {fragment} / {identity}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
