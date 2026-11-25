#!/usr/bin/env python3
"""回读 R3 当轮实证，并在独立副本中执行诊断用例。"""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch
import xml.etree.ElementTree as ET
from zipfile import ZipFile


sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import r3_web_host as r3
import verify


HOST = r3.PREFIX + "Web.Host"
LOG_DLL = "Abp.Castle.Log4Net.dll"
CASES = {
    "missing-fixed-object": ("preflight", r3.TEMPLATE, r3.INPUTS[r3.TEMPLATE][0]),
    "missing-assets": (r3.project_path("Application").as_posix(), r3.TFM, "Application.project.assets.json"),
    "zero-target": (r3.project_path("Web.Core").as_posix(), r3.TFM, "目标无匹配"),
    "missing-deps": ("缺少 Host .deps.json", HOST + ".deps.json"),
    "owner-conflict": ("来源冲突", "Abp.Castle.Log4Net/10.2.0", "log4net/3.1.0"),
    "missing-dll": ("缺少应复制的", LOG_DLL, "output/" + LOG_DLL),
    "missing-framework-edge": ("依赖边不符", "Abp.ZeroCore.EntityFrameworkCore/10.2.0", "Abp.EntityFrameworkCore/10.2.0"),
    "missing-sql-provider": ("缺少还原图的包或项目", r3.PROVIDER + "/9.0.5"),
    "missing-host-edge": ("依赖边不符", HOST + "/1.0.0", r3.PREFIX + "Web.Core/1.0.0"),
    "extra-runtime": ("多出", "AutoMapper/14.0.0", "lib/net8.0/Unregistered.dll"),
    "abp-version-drift": ("原版框架与维护源码存在待归因差异", "package-gaps.json"),
}
GIT_ENV = os.environ | {"GIT_OPTIONAL_LOCKS": "0"}


def git(repo, *args):
    return subprocess.check_output(["git", "-C", repo, *args], env=GIT_ENV, text=True)


def checkout_state():
    repo = verify.ROOT
    modules = git(repo, "config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$")
    paths = [Path(line.split(maxsplit=1)[1]) for line in modules.splitlines()]
    return {
        "index": git(repo, "ls-files", "--stage"),
        "status": git(repo, "status", "--porcelain", "--branch", "-uall"),
        "head": git(repo, "rev-parse", "HEAD", "HEAD^{tree}"),
        "children": {path.as_posix(): {
            "head": git(repo / path, "rev-parse", "HEAD", "HEAD^{tree}"),
            "status": git(repo / path, "status", "--porcelain", "-uall"),
        } for path in paths},
    }


def tree_hashes(root):
    return {file.relative_to(root).as_posix(): verify.sha256(file) for file in root.rglob("*") if file.is_file()}


def locations(run):
    report = verify.read_json(run / "report.json")
    return run / "source/aspnet-core", run / "packages", run / report["hostOutputRoot"]


def run_case(case, fixture, run):
    root, cache, _ = locations(run)
    if case == "missing-fixed-object":
        missing_template_repo = fixture / "repo"
        report = fixture / "failure-report"
        report.mkdir()
        return r3.R3Run(missing_template_repo, report).execute_r3()
    if case == "abp-version-drift":
        verify_version_drift(run, fixture, "Abp.Castle.Log4Net", "10.2.0", "10.2.1")
        return 0
    if case in ("missing-assets", "zero-target"):
        assets = {name: fixture / f"{name}.project.assets.json" for name in r3.PROJECTS}
        r3.read_assets(root, assets, cache, run / "NuGet.Config")
    else:
        inventory = verify.read_json(run / "assets-inventory.json")
        host = inventory[r3.project_path("Web.Host").as_posix()]
        r3.check_host(fixture / "output", cache, host)
    return 0


def prepare_case(case, fixture, run, output):
    fixture.mkdir()
    if case == "abp-version-drift":
        return
    if case == "missing-fixed-object":
        repo = fixture / "repo"
        subprocess.run(["git", "clone", "--shared", "--no-checkout", str(verify.ROOT), str(repo)],
                       check=True, capture_output=True, env=GIT_ENV)
        subprocess.run(["git", "init", str(repo / r3.TEMPLATE)],
                       check=True, capture_output=True, env=GIT_ENV)
    elif case in ("missing-assets", "zero-target"):
        for path in (run / "raw-assets").iterdir():
            shutil.copyfile(path, fixture / path.name)
        if case == "missing-assets":
            (fixture / "Application.project.assets.json").unlink()
        else:
            path = fixture / "Web.Core.project.assets.json"
            data = verify.read_json(path)
            data["targets"][r3.TFM] = {}
            r3.write_json(path, data)
    else:
        copied = fixture / "output"
        shutil.copytree(output, copied)
        deps = copied / (HOST + ".deps.json")
        if case == "missing-deps":
            deps.unlink()
        elif case == "missing-dll":
            (copied / LOG_DLL).unlink()
            original = tree_hashes(output)
            changed = tree_hashes(copied)
            removed = original.pop(LOG_DLL)
            verify.require(original == changed, "缺 DLL 的用例改动了其他输出")
            r3.write_json(fixture / "fixture-difference.json", {
                "removed": {"path": LOG_DLL, "sha256": removed}, "preservedFileCount": len(changed),
                "preservedDepsSha256": changed[HOST + ".deps.json"],
            })
        else:
            data = verify.read_json(deps)
            graph = data["targets"][r3.DEPS_TARGET]
            if case == "owner-conflict":
                extra = "lib/net9.0/" + LOG_DLL
                graph["log4net/3.1.0"]["runtime"][extra] = graph["Abp.Castle.Log4Net/10.2.0"]["runtime"][extra]
            elif case == "missing-framework-edge":
                graph["Abp.ZeroCore.EntityFrameworkCore/10.2.0"]["dependencies"].pop("Abp.EntityFrameworkCore")
            elif case == "missing-sql-provider":
                provider = r3.PROVIDER + "/9.0.5"
                graph.pop(provider)
                data["libraries"].pop(provider)
                dll = r3.PROVIDER + ".dll"
                assert verify.sha256(copied / dll) == verify.sha256(output / dll)
            elif case == "missing-host-edge":
                graph[HOST + "/1.0.0"]["dependencies"].pop(r3.PREFIX + "Web.Core")
            else:
                graph["AutoMapper/14.0.0"]["runtime"]["lib/net8.0/Unregistered.dll"] = {}
            r3.write_json(deps, data)


def verify_saved(run, frozen):
    root, cache, output = locations(run)
    report = verify.read_json(run / "report.json")
    verify.require(report["status"] == "passed" and report["exitCode"] == 0
                   and set(report["stages"]) == set(r3.STAGES), "R3 正式报告未通过")
    verify.require(all(step["status"] == "passed" and step["exitCode"] == 0
                       and all(cmd["exitCode"] == 0 for cmd in step["commands"])
                       for step in report["stages"].values()), "正式报告阶段或命令失败")
    for evidence in [*report["rawAssets"].values(), *report["inventories"].values()]:
        verify.require(verify.sha256(run / evidence["path"]) == evidence["sha256"], f"摘要不符：{evidence}")
    actual = verify.read_json(run / r3.MACHINE_BASELINE)
    verify.require(actual == verify.read_json(frozen), "首次基线与当轮清单有差异")
    assert actual["schemaVersion"] == 2
    assets = verify.read_json(run / "assets-inventory.json")
    verify.require(len(actual["projects"]) == len(assets) == len(r3.PROJECTS), "五项目不齐")
    count = 0
    for name in r3.PROJECTS:
        relative = r3.project_path(name).as_posix()
        target = actual["projects"]["aspnet-core/" + relative][r3.TFM]
        raw = verify.read_json(run / "raw-assets" / f"{name}.project.assets.json")
        packages = {key: value.get("dependencies", {}) for key, value in raw["targets"][r3.TFM].items()
                    if value["type"] == "package"}
        items = {f"{item['id']}/{item['version']}": item["dependencies"] for item in target["packages"]}
        verify.require(packages == items and len(items) == len(target["packages"]), f"{relative} 包图与原始资产不符")
        restore = raw["project"]["restore"]["frameworks"][r3.TFM]
        project_references = sorted(Path(ref["projectPath"]).relative_to(root.parent).as_posix()
                                    for ref in restore["projectReferences"].values())
        assert target["projectReferences"] == project_references, relative
        declared = {item.attrib["Include"]: item.attrib["Version"]
                    for item in ET.parse(root / relative).iter("PackageReference")}
        ranges = raw["project"]["frameworks"][r3.TFM].get("dependencies", {})
        versions = dict(key.split("/") for key in packages)
        expected_direct = {id_: {"declaredVersion": version, "declaredRange": ranges[id_]["version"],
                                 "resolvedVersion": versions[id_]} for id_, version in declared.items()}
        assert target["directPackages"] == expected_direct, relative
        count += len(items)
        original = raw["project"]["frameworks"][r3.TFM].get("downloadDependencies", [])
        verify.require({(d["name"], d["version"]) for d in original}
                       == {(d["id"], d["declaredRange"]) for d in target["sdkDownloads"]},
                       f"{relative} SDK 下载声明不符")
        inventory = assets[relative]
        for download in target["sdkDownloads"]:
            seen = inventory["sdkDownloads"][f"{download['id']}/{download['version']}".casefold()]
            verify.require(download["source"] == seen["source"]
                           and download["contentSha512"] == seen["contentSha512"], f"{relative} SDK 下载不符")
        pack_fields = [{key: value for key, value in item.items() if key != "location"}
                       for _, item in sorted(inventory["sdkUsedPacks"].items())]
        verify.require(target["sdkUsedPacks"] == pack_fields, f"{relative} 实际 SDK pack 不符")
    host = verify.read_json(run / "host-output.json")
    verify.require(actual["frameworkRuntimeDlls"] == host["frameworkRuntimeDlls"], "框架 DLL 清单与输出证据不符")
    deps = verify.read_json(output / (HOST + ".deps.json"))["targets"][r3.DEPS_TARGET]
    host_assets = assets[r3.project_path("Web.Host").as_posix()]
    host_packages = host_assets["packages"]
    positive = r3.check_host(output, cache, host_assets)
    assert positive["verifiedRuntimeOutputPaths"] == host["verifiedRuntimeOutputPaths"]
    assert positive["sqlServerProvider"] == host["sqlServerProvider"]
    provider = host["sqlServerProvider"]
    assert provider["packageAsset"] in deps[provider["package"]]["runtime"]
    assert verify.sha256(output / provider["path"]) == provider["sha256"]
    with ZipFile(cache / host_packages[provider["package"]]["archive"]["path"]) as archive:
        assert hashlib.sha256(archive.read(provider["packageAsset"])).hexdigest() == provider["sha256"]
    range_graph = deepcopy(host_assets)
    range_graph["packages"]["Abp.ZeroCore.EntityFrameworkCore/10.2.0"]["dependencies"][
        "Abp.EntityFrameworkCore"] = "[10.2.0, 11.0.0)"
    assert r3.check_host(output, cache, range_graph)["frameworkRuntimeDlls"] == host["frameworkRuntimeDlls"]
    for item in actual["frameworkRuntimeDlls"]:
        key = f"{item['packageId']}/{item['version']}"
        assert item["packageAsset"] in deps[key]["runtime"]
        assert not Path(item["path"]).is_absolute() and not Path(item["packageAsset"]).is_absolute()
        assert verify.sha256(output / item["path"]) == item["sha256"]
        with ZipFile(cache / host_packages[key]["archive"]["path"]) as archive:
            assert hashlib.sha256(archive.read(item["packageAsset"])).hexdigest() == item["sha256"]
    print(f"正例：{len(actual['projects'])} 项目，{count} 个逐项目包解析，"
          f"{len(positive['verifiedRuntimeOutputPaths'])} 个运行文件，"
          f"{len(actual['frameworkRuntimeDlls'])} 个框架 DLL 与原始证据逐项一致")
    print(f"正例：{provider['package']} 对应依赖库及实际 DLL，资产声明范围与 deps 的解析版本分别核对")


def verify_version_drift(run, fixture, package_id, existing, version):
    # 模拟 NuGet 在相同原始声明下选中较高版本。来源与哈希借用既有证据，范围限于解析后验收。
    root, cache, _ = locations(run)
    simulated = r3.R3Run(verify.ROOT, fixture)
    simulated.root, simulated.cache, simulated.config = root, cache, run / "NuGet.Config"
    old_key, new_key = f"{package_id}/{existing}", f"{package_id}/{version}"
    fixed = verify.read_json(run / "assets-inventory.json")
    selected = {key: item for target in fixed.values() for key, item in target["packages"].items()}
    selected.update({f"{item['id']}/{item['version']}": item
                     for target in fixed.values() for item in target["sdkDownloads"].values()})

    def recorded_hashes(key, _):
        package = selected[old_key if key == new_key else key]
        return {field: package[field] for field in ("source", "contentSha512", "archiveSha512", "archive", "cachePath")}

    def simulated_assets(source, raw, packages, config):
        result = {}
        for name, path in raw.items():
            data = verify.read_json(path)
            for table in (data["targets"][r3.TFM], data["libraries"]):
                if old_key in table:
                    table[new_key] = table.pop(old_key)
            overlay = fixture / f"simulated-{name}.project.assets.json"
            r3.write_json(overlay, data)
            result[r3.project_path(name).as_posix()] = r3.read_project(
                source, name, overlay, packages, config, recorded_hashes,
            )
        return result

    with patch.object(r3, "read_assets", simulated_assets):
        simulated.step("assets", simulated.inventory)
    declarations = {path: target["directPackages"][package_id] for path, target in simulated.assets.items()
                    if package_id in target["directPackages"]}
    assert declarations and all(item["declaration"]["version"] == existing and item["resolvedVersion"] == version
                                for item in declarations.values())
    simulated.host = verify.read_json(run / "host-output.json")
    for dll in simulated.host["frameworkRuntimeDlls"]:
        if dll["packageId"] == package_id:
            dll["version"] = version
    r3.write_json(fixture / "host-output.json", simulated.host)
    simulated.step("package_gaps", simulated.gaps)
    gaps = verify.read_json(fixture / "package-gaps.json")
    assert not gaps["frameworkDifferencesRequiringAttribution"]
    picks = gaps["criticalDependencyComparison"][package_id]["originalProjects"]
    assert picks and all(item["version"] == version for item in picks.values())
    print(f"模拟正例：{package_id} 声明 {existing}，选中 {version}，第三方差异如实记录")


def verify_preinstalled_fixture(evidence):
    directory = evidence / "preinstalled" / "packs"
    id_, version = "Microsoft.NETCore.App.Ref", "9.0.23"
    pack = directory / id_ / version
    sample = pack / "data/FrameworkList.xml"
    sample.parent.mkdir(parents=True)
    sample.write_text("<FileList />", encoding="utf-8")
    framework = {"Identity": "Microsoft.NETCore.App"}
    resolved = {**framework, "NuGetPackageId": id_, "NuGetPackageVersion": version,
                "Path": str(pack), "TargetFramework": r3.TFM}
    data = {"Properties": {"NetCoreTargetingPackRoot": str(directory)},
            "Items": {"FrameworkReference": [framework], "ResolvedTargetingPack": [resolved]}}
    seen = r3.read_sdk_packs(data, {"sdkDownloads": {}}, evidence / "packages", directory, False)[framework["Identity"]]
    assert seen["origin"] == "preinstalled" and seen["version"] == version
    assert not seen["source"] and not seen["contentSha512"] and seen["missingPackageEvidence"]
    assert seen["file"]["sha256"] == verify.sha256(sample)
    r3.write_json(evidence / "preinstalled" / "simulated-resolution.json", {"input": data, "result": seen})
    print("模拟正例：预装 pack 保存选用文件摘要及缺少包来源、内容摘要的原因")


def verify_dispatch(evidence):
    import r2_verify

    profiles = {}
    r0_args = ["verify.py", "--profile", "r0", "--evidence-root", str(evidence / "dispatch-r0"),
               "--work-root", str(evidence / "dispatch-work")]
    with patch.object(sys, "argv", r0_args), patch.object(verify.R0Run, "execute", return_value=39) as r0:
        assert verify.main() == 39
        r0.assert_called_once_with(evidence / "dispatch-work")
        profiles["r0"] = r0_args
    r2_args = ["verify.py", "--profile", "r2"]
    options = ("candidate-feed", "candidate-manifest", "candidate-symbols", "r1-evidence", "evidence-root", "dotnet")
    for option in options:
        r2_args.extend(("--" + option, str(evidence / option)))
    with patch.object(sys, "argv", r2_args), patch.object(r2_verify, "execute", return_value=43) as r2:
        assert verify.main() == 43
        args = r2.call_args.args[0]
        assert all(getattr(args, key.replace("-", "_")) == evidence / key for key in options)
        profiles["r2"] = r2_args
    r3.write_json(evidence / "legacy-dispatch.json", profiles)
    print("分派正例：R0 和 R2 的原参数均到达原执行器")


def main():
    if sys.argv[1] == "--child":
        try:
            return run_case(sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]))
        except verify.VerificationError as error:
            print(str(error), file=sys.stderr)
            return 1

    run, evidence, frozen = (Path(arg).resolve() for arg in sys.argv[1:])
    evidence.mkdir(parents=True)
    verify_saved(run, frozen)
    verify_preinstalled_fixture(evidence)
    verify_dispatch(evidence)
    provider_fixture = evidence / "provider-version-drift"
    provider_fixture.mkdir()
    verify_version_drift(run, provider_fixture, r3.PROVIDER, "9.0.5", "9.0.6")
    _, _, output = locations(run)
    snapshot = checkout_state()
    r3.write_json(evidence / "checkout-before.json", snapshot)
    records = {}
    for case, diagnostic in CASES.items():
        fixture = evidence / case
        prepare_case(case, fixture, run, output)
        command = [sys.executable, "-B", __file__, "--child", case, str(fixture), str(run)]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        log = fixture / "result.log"
        log.write_text(result.stdout, encoding="utf-8")
        records[case] = {"argv": command, "cwd": str(Path.cwd()), "exitCode": result.returncode,
                         "log": log.relative_to(evidence).as_posix(), "diagnostics": diagnostic}
        r3.write_json(evidence / "diagnostics.json", records)
        verify.require(result.returncode == 1 and all(item in result.stdout for item in diagnostic),
                       f"{case} 的诊断或退出码不符，详见 {log}")
        print(f"{case}：退出 1，命中 {', '.join(diagnostic)}")
        if case == "missing-fixed-object":
            report = verify.read_json(fixture / "failure-report/report.json")
            assert report["exitCode"] == 1 and report["stages"]["preflight"]["status"] == "failed"
            assert all(report["stages"][stage]["status"] == "not_run"
                       and report["stages"][stage]["reason"] and not report["stages"][stage]["commands"]
                       for stage in r3.STAGES[1:])
            assert checkout_state() == snapshot
        if case == "abp-version-drift":
            gaps = verify.read_json(fixture / "package-gaps.json")["frameworkDifferencesRequiringAttribution"]
            assert gaps["Abp.Castle.Log4Net"]["actual"]["version"] == "10.2.1"
            finding, = gaps["projectPackages"][r3.project_path("Web.Host").as_posix()]
            assert finding["directDeclaration"]["declaration"]["version"] == "10.2.0"
            assert finding["directDeclaration"]["resolvedVersion"] == "10.2.1"
    r3.write_json(evidence / "checkout-after.json", checkout_state())
    verify.require(checkout_state() == snapshot, "负例修改了主仓或子仓检出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
