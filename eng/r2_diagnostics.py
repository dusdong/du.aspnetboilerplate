"""使用真实候选、还原与 HTTP 证据构建 R2 定向诊断用例。"""

import copy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import sys
import zipfile

from r2_assets import check_assets, check_http
from r2_packages import TARGETS, verify_packages, write_json
from r2_verify import ERRORS, RECORD, R2Run
from verify import read_json, require, sha256


def edited_zip(path, change):
    temp = path.with_suffix(".tmp")
    with zipfile.ZipFile(path) as original, zipfile.ZipFile(temp, "w") as edited:
        names = original.namelist()
        updates = change(original)
        for name in names:
            edited.writestr(original.getinfo(name), updates.pop(name, original.read(name)))
        for name, value in updates.items():
            edited.writestr(name, value, compress_type=zipfile.ZIP_DEFLATED)
    temp.replace(path)


def case_exit(run, label, folder, kind, expected_text):
    _, log = run.command([sys.executable, "-B", Path(__file__).resolve(), kind, run.evidence, folder],
                         folder, f"{label}.log", accepted=(1,))
    output = log.read_text()
    require(all(text in output for text in expected_text), f"{label} 没有得到预期失败阶段，详见 {log}")
    run.report["negativeCases"][label] = {"status": "passed", "diagnosticExitCode": 1,
                                          "log": log.name, "diagnostic": output.strip()}


def negative_packages(run, feed, manifest, symbols, r1):
    cases = [
        ("negative-package-digest", ["packages", "Du.Abp.Web.Common", "摘要不符"]),
        ("negative-dependency-id", ["packages", "Du.Abp.Web.Common", "内部依赖 ID 错误", "Abp"]),
        ("negative-wrong-dll-tfm", ["packages", "lib/net10.0/Abp.Web.Common.dll", "v9.0", "v10.0"]),
    ]
    declared = read_json(manifest)
    name = "Du.Abp.Web.Common"
    for label, expected in cases:
        root = run.evidence / label
        shutil.copytree(feed, root / "feed")
        modified = copy.deepcopy(declared)
        package = root / "feed" / modified["packages"][name]["package"]["file"]
        if label == "negative-package-digest":
            edited_zip(package, lambda _: {"r2-diagnostic-marker.txt": b"digest mismatch"})
        elif label == "negative-dependency-id":
            def replace(archive):
                file = next(name for name in archive.namelist() if name.endswith(".nuspec"))
                before = archive.read(file)
                after = before.replace(b'id="Du.Abp"', b'id="Abp"')
                require(after != before, "诊断夹具未修改 nuspec ID")
                return {file: after}

            edited_zip(package, replace)
        else:
            expected_file = "lib/net10.0/Abp.Web.Common.dll"
            with zipfile.ZipFile(package) as archive:
                wrong_dll = archive.read("lib/net9.0/Abp.Web.Common.dll")
            edited_zip(package, lambda _: {expected_file: wrong_dll})
            modified["packages"][name]["targets"]["net10.0"]["sha256"] = hashlib.sha256(wrong_dll).hexdigest()
        if label != "negative-package-digest":
            modified["packages"][name]["package"]["sha256"] = sha256(package)
        write_json(root / "manifest.json", modified)
        write_json(root / "inputs.json", {"symbols": str(symbols), "r1": str(r1)})
        case_exit(run, label, root, "packages", expected)


def negative_restore(run, feed, candidate):
    label = "negative-missing-transitive"
    target = "net10.0"
    missing = "Du.Abp.Web.Common"
    root = run.evidence / label
    missing_file = candidate["packages"][missing]["package"]["file"]
    shutil.copytree(feed, root / "feed", ignore=shutil.ignore_patterns(missing_file))
    work, env, restore, _ = run.consumer(target, root / "feed", candidate["version"], f"{label}/consumer")
    code, log = run.restore(target, work, env, restore, expected=(1,), prefix=f"{label}-")
    output = log.read_text()
    require("NU1101" in output and missing in output and "nuget.org" in output,
            f"隔离还原没有报告缺失的传递包 {missing}，详见 {log}")
    require(not any(Path(env["NUGET_PACKAGES"]).glob(f"{missing.lower()}/*")),
            f"传递包 {missing} 出现在缺包还原的隔离缓存")
    run.report["negativeCases"][label] = {"status": "passed", "diagnosticExitCode": code,
                                          "log": log.name, "missing": missing}


def negative_evidence(run, feed, candidate):
    target = "net10.0"
    data = read_json(run.evidence / target / "obj/project.assets.json")
    project = run.evidence / target / "MinimalBackend.csproj"
    asset_cases = [("negative-asset-target", "lib/net9.0/Abp.Web.Common.dll"),
                   ("negative-asset-owner", "lib/net10.0/Abp.Web.Common.dll")]
    for label, path in asset_cases:
        root = run.evidence / label
        root.mkdir()
        fixture = copy.deepcopy(data)
        graph = fixture["targets"][target]
        key = f"Du.Abp.Web.Common/{candidate['version']}"
        if label == "negative-asset-target":
            graph[key]["compile"] = {path: {}}
        else:
            third_party = next(entry for entry in graph if entry.startswith("NUglify/"))
            graph[third_party].setdefault("compile", {})[path] = {}
        write_json(root / "assets.json", fixture)
        write_json(root / "inputs.json", {"target": target, "project": str(project), "feed": str(feed)})
        case_exit(run, label, root, "assets", ["assets", "Abp.Web.Common.dll", "错目标或多来源", path])

    for target in TARGETS:
        http = read_json(run.evidence / f"{target}-http.json")
        for field, message in (("active", "缺少仓储 SQLite 活动事务"), ("committed", "缺少同一 ABP 工作单元提交完成")):
            label = f"negative-http-{target}-{field}"
            root = run.evidence / label
            root.mkdir()
            fixture = copy.deepcopy(http)
            del fixture["post"]["body"][field]
            write_json(root / "http.json", fixture)
            case_exit(run, label, root, "http", ["http", message])


def diagnose(kind, evidence, folder):
    if kind in {"packages", "assets"}:
        report = read_json(evidence / "report.json")
        run = R2Run(folder, Path(report["environment"]["dotnet"]))
        run.report["inputs"] = report["inputs"]
        run.metadata_tool = evidence / "tools/metadata/bin/Release/net10.0/R2Metadata.dll"
        run.api_tool = evidence / "tools/api/bin/Release/net9.0/ApiInventory.dll"
        inputs = read_json(folder / "inputs.json")
        try:
            if kind == "packages":
                run.step("packages", verify_packages, run, folder / "feed", folder / "manifest.json",
                         Path(inputs["symbols"]), Path(inputs["r1"]))
            else:
                tfm = inputs["target"]
                project = Path(inputs["project"])
                run.step(f"{tfm}/assets", check_assets, read_json(folder / "assets.json"), tfm, project,
                         project.parent / "packages", Path(inputs["feed"]), read_json(evidence / "candidate.json"),
                         TARGETS[tfm][1], run.check_dependency_ranges)
        except ERRORS as error:
            run.report.update(status="failed", exitCode=1, reason=str(error))
            for step in run.report["stages"].values():
                if step["status"] == "not_run":
                    step["reason"] = f"诊断仅复用 {kind} 检查阶段"
            raise
        else:
            run.report.update(status="passed", exitCode=0)
        finally:
            run.report["finishedAt"] = datetime.now(timezone.utc).isoformat()
            run.save()
    elif kind == "http":
        check_http(read_json(folder / "http.json"), RECORD)
    else:
        return 2
    return 0


if __name__ == "__main__":
    stage, parent, work = sys.argv[1:]
    try:
        raise SystemExit(diagnose(stage, Path(parent), Path(work)))
    except ERRORS as error:
        print(f"{stage}：{error}", file=sys.stderr)
        raise SystemExit(1) from error
