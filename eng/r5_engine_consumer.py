"""复验验收端独立登记的 R5 引擎主包。"""

import argparse
from hashlib import sha256 as sha256_bytes
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
from zipfile import BadZipFile, ZipFile

from r2_packages import nuspec_metadata
from r3_template_net9_packages import source_config
from r3_web_host import NUGET_SOURCE, SDK, artifact, inside, package_hashes, write_json
from r4_candidate_batch import run_logged
from r4_engine_consumer import CONTRACT
from verify import ROOT, VerificationError, read_json, require, sha256


PACKAGE = "Du.AutoMapper"
VERSION = "14.0.1"
ASSET = "lib/net8.0/AutoMapper.dll"
ASSEMBLY = "AutoMapper, Version=14.0.0.0, Culture=neutral, PublicKeyToken=be96cd2c38ef1005"
ADVISORIES = {
    "GHSA-rvv3-g6hj-g44x": ("reference-graph",),
    "GHSA-6vhm-j9h7-f9gh": ("constructor-depth",),
    "GHSA-gpwp-5797-mjff": ("runtime-dispatch", "application-exception"),
}


def verify_input(path, expected):
    require(re.fullmatch(r"[0-9a-f]{64}", expected) and sha256(path) == expected, "独立登记文件 SHA-256 不符")
    record = read_json(path)
    require((record["id"], record["version"], record["assetPath"]) == (PACKAGE, VERSION, ASSET),
            "独立登记的包 ID、版本或资产路径不符")
    require(re.fullmatch(r"[0-9a-f]{40}", record["producerCommit"]), "生产提交格式不符")
    archive = inside(path.parent, record["archivePath"])
    require(archive.name == f"{PACKAGE}.{VERSION}.nupkg" and archive.is_file(), "候选主包名称不符或缺失")
    require(sha256(archive) == record["archiveSha256"], "登记的候选主包 SHA-256 不符")
    with ZipFile(archive) as package:
        require(package.namelist().count(ASSET) == 1, "主包缺少唯一引擎 DLL")
        require(sha256_bytes(package.read(ASSET)).hexdigest() == record["assetSha256"], "登记的包内 DLL SHA-256 不符")
        spec = nuspec_metadata(package)
        require((spec.findtext("id"), spec.findtext("version")) == (PACKAGE, VERSION), "候选主包 nuspec 身份不符")
        repository = read_json(ROOT / "eng/r4_release_candidate.json")["producers"]["engine"]["repository"]
        require(spec.find("repository").attrib ==
                {"type": "git", "url": repository, "commit": record["producerCommit"]}, "候选主包生产仓或提交不符")
    return record, archive


def verify_restored(work, cache, tfm, feed, record, public_dependencies):
    assets = work / "obj/project.assets.json"
    graph = read_json(assets)
    restore = graph["project"]["restore"]
    require(set(restore["sources"]) == {str(feed), NUGET_SOURCE}, f"{tfm} 还原来源不符")
    require(not restore["frameworks"][tfm]["projectReferences"], f"{tfm} 不允许项目引用")
    require([Path(path) for path in graph["packageFolders"]] == [cache], f"{tfm} 还原缓存不是独立缓存")
    direct = graph["project"]["frameworks"][tfm]["dependencies"]
    require(set(direct) == {PACKAGE} and direct[PACKAGE]["version"] == f"[{VERSION}, {VERSION}]",
            f"{tfm} 必须精确直接引用 {PACKAGE} [{VERSION}]")
    key = f"{PACKAGE}/{VERSION}"
    target = graph["targets"][tfm]
    require(set(graph["libraries"]) == set(target), f"{tfm} 还原图与库条目不一致")
    require(set(target) == public_dependencies | {key},
            f"{tfm} 实际还原闭包与公开引擎对照不符：{sorted(target)}")
    restored = {}
    for package, node in target.items():
        require(node["type"] == graph["libraries"][package]["type"] == "package", f"{package} 不是包资产")
        relative = graph["libraries"][package]["path"]
        restored[package] = package_hashes(cache, package, relative, str(feed) if package == key else NUGET_SOURCE)
    require(list(target[key]["compile"]) == list(target[key]["runtime"]) == [ASSET], f"{tfm} 引擎资产不符")
    engine = restored[key]
    require(engine["archive"]["sha256"] == record["archiveSha256"], f"{tfm} 还原的候选归档 SHA-256 不符")
    dll = inside(cache, Path(engine["cachePath"]) / ASSET)
    require(sha256(dll) == record["assetSha256"], f"{tfm} 缓存引擎 DLL SHA-256 不符")
    return assets, restored, dll


def build(work, project, tfm, dotnet, feed, record, public_dependencies, selection=()):
    cache = work / "packages"
    cache.mkdir()
    scratch = work / "nuget-scratch"
    scratch.mkdir()
    temp = work / "temp"
    temp.mkdir()
    for path in (work, cache, temp, scratch):
        require(os.access(path, os.W_OK), f"目录不可写：{path}")
    env = os.environ | {
        "DOTNET_CLI_HOME": str(work / "dotnet-home"),
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_NOLOGO": "1",
        "DOTNET_CLI_UI_LANGUAGE": "en",
        "DOTNET_ROOT": str(dotnet.parent),
        "TMPDIR": str(temp),
        "NUGET_PACKAGES": str(cache),
        "NUGET_HTTP_CACHE_PATH": str(work / "http-cache"),
        "NUGET_PLUGINS_CACHE_PATH": str(work / "plugins-cache"),
        "NUGET_SCRATCH": str(scratch),
        "MSBUILDDISABLENODEREUSE": "1",
    }

    def command(label, args):
        return run_logged(args, work, label, work, env)

    command("resources", ["df", "-h", work, cache, temp, scratch])
    command("sdk", [dotnet, "--info"])
    config = work / "NuGet.Config"
    source_config(config, feed, (PACKAGE,))
    common = ["--disable-build-servers", *selection]
    command("restore", [dotnet, "restore", project, "--configfile", config, "--no-http-cache", *common])
    assets, restored, compile_dll = verify_restored(work, cache, tfm, feed, record, public_dependencies)
    command("build", [dotnet, "build", project, "-c", "Release", "--no-restore", "-v:diag",
                      f"-bl:{work / 'build.binlog'}", *common])
    # Csc 的真实编译命令须使用已验明的缓存 DLL。
    references = (f"/reference:{compile_dll}".encode(), f'/reference:"{compile_dll}"'.encode())
    compiler = re.compile(rb'/csc(?:\.dll)?[" ]')
    with (work / "build.log").open("rb") as log:
        require(any(compiler.search(line) and any(ref in line for ref in references) for line in log),
                f"{tfm} 编译命令未引用已登记引擎")
    program = project.parent / "bin/Release" / tfm / f"{project.stem}.dll"
    runtime_dll = program.with_name("AutoMapper.dll")
    require(sha256(runtime_dll) == record["assetSha256"], f"{tfm} Release 输出的引擎 SHA-256 不符")
    identity = {
        "assets": artifact(assets, work),
        "archiveSources": restored,
        "archivePath": str(inside(cache, restored[f"{PACKAGE}/{VERSION}"]["archive"]["path"])),
        "compileAsset": {"path": str(compile_dll), "sha256": sha256(compile_dll)},
        "releaseAsset": {"path": str(runtime_dll), "sha256": sha256(runtime_dll)},
        "archiveSha256": record["archiveSha256"],
        "asset": ASSET, "assetSha256": record["assetSha256"],
    }
    write_json(work / "identity.json", identity)
    return command, program, identity


def verify_public_observation(public, probe, evidence):
    # P1 的校验器负责固定公开清单、实际还原图及逐次观测。
    require(sha256(public / "Program.cs") == sha256(probe / "Program.cs"), "公开 R4 与候选的业务源码不同")
    checks = runpy.run_path(str(probe / "verify.py"))
    evidence.mkdir()
    expected = checks["get_expected_package"](evidence, public / "R4-PACKAGE-CHECKSUMS.json",
                                              public / "verified-downloads.json")
    identity = checks["verify_restored_package"](public / "packages",
                                                 read_json(public / "obj/project.assets.json"), expected)
    report = read_json(public / "observations.json")
    summary = checks["verify_observations"](report, public / "bin/Release/net10.0/AutoMapper.dll", identity)
    return checks, identity, report, summary


def execute(args):
    record, archive = verify_input(args.input, args.input_sha256)
    output = args.output
    output.mkdir()
    shutil.copyfile(args.input, output / "acceptance-input.json")
    feed = output / "feed"
    feed.mkdir()
    shutil.copyfile(archive, feed / archive.name)
    require(sha256(feed / archive.name) == record["archiveSha256"], "验收包源中的归档 SHA-256 不符")
    write_json(output / "global.json", {"sdk": {"version": SDK, "rollForward": "disable"}})

    revision = record["producerCommit"]
    source = read_json(ROOT / "eng/r4_release_candidate.json")["producers"]["engine"]
    repo = ROOT / source["path"]
    require(subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", source["finalCommit"], revision],
                           check=False).returncode == 0, "生产提交须继承已验证的 R4 引擎基线")
    source_archive = output / "probe-source.tar"
    export = ["git", "-C", repo, "archive", revision, "Directory.Build.props", "src/RecursionProbe", "src/CollectionOrderProbe"]
    with source_archive.open("wb") as stream:
        subprocess.run(export, stdout=stream, check=True)
    write_json(output / "source-command.json", {"argv": [str(arg) for arg in export], "cwd": str(Path.cwd()), "exitCode": 0})
    extracted = output / "source"
    extracted.mkdir()
    run_logged(["tar", "-xf", source_archive, "-C", extracted], output, "source-extract", output, os.environ)
    probe = extracted / "src/CollectionOrderProbe"
    checks, public_identity, public_report, public_summary = verify_public_observation(args.public_observation, probe,
                                                                                       output / "public-reference")
    public_dependencies = public_identity["packages"].keys() - {f"{PACKAGE}/{checks['VERSION']}"}
    ordinary = output / "ordinary"
    ordinary.mkdir()
    shutil.copyfile(probe / "Program.cs", ordinary / "Program.cs")
    project = ordinary / "CollectionOrderProbe.csproj"
    project.write_text((probe / project.name).read_text().replace("[14.0.0]", f"[{VERSION}]"), encoding="utf-8")
    command, program, identity = build(ordinary, project, "net10.0", args.dotnet, feed, record, public_dependencies)
    actual = json.loads(command("observations", [args.dotnet, program]))
    write_json(ordinary / "observations.json", actual)
    dll = program.with_name("AutoMapper.dll")
    summary = checks["verify_observations"](actual, dll, identity)
    require(actual["assemblies"][0]["name"] == ASSEMBLY and actual["assemblies"][0]["context"] == "Default",
            "普通 Map 进程加载的程序集身份不符")
    require(set(summary["pairs"].values()) == {"as-expected"} and not summary["warmupDeviations"],
            "候选普通 Map 的业务结果、顺序或预热不符")
    for key in ("runtime", "architecture", "input", "initial", "warmup", "expected"):
        require(actual[key] == public_report[key], f"候选与公开 R4 的对照条件不符：{key}")
    differences = []
    for current, previous in zip(actual["observations"], public_report["observations"], strict=True):
        for key in ("Case", "Repeat", "Registration", "WarmupOrder"):
            require(current[key] == previous[key], f"候选与公开 R4 的对照顺序不符：{key}")
        fields = [key for key in ("Warmups", "Measurements") if current[key] != previous[key]]
        if fields:
            differences.append({"case": current["Case"], "repeat": current["Repeat"], "fields": fields})

    advisory = extracted / "src/RecursionProbe"
    command, program, _ = build(advisory, advisory / "RecursionProbe.csproj", "net9.0",
                                args.dotnet, feed, record, public_dependencies,
                                selection=(f"-p:CandidateVersion={VERSION}",))
    dll = program.with_name("AutoMapper.dll")
    command("ilspy-version", [args.ilspy, "--version"])
    il = command("mapper-il", [args.ilspy, "--ilcode", "--type", "AutoMapper.Mapper", dll]).decode()
    require(re.search(r"(?ms)^\s*\).*?\bRuntimeHelpers::EnsureSufficientExecutionStack\(\)"
                      r"(?:(?!end of method).)*end of method Mapper::MapCore\b", il),
            "候选 DLL 的 MapCore 中缺少 CLR 栈检查")
    common = [sys.executable, "-B", advisory / "run-probes.py", "--dotnet", args.dotnet, "--program", program,
              "--dll-sha256", record["assetSha256"]]
    command("behavior", [*common, "--output", advisory / "behavior"])
    command("exception", [*common, "--scenario", "application-exception", "--output", advisory / "exception"])
    observed = {}
    for name in ("behavior", "exception"):
        path = advisory / name / "report.json"
        for row in read_json(path):
            loaded = row["actual"]
            require(row["passed"] and row["exitCode"] == 0 and not row["timedOut"]
                    and loaded["sha256"] == record["assetSha256"] and loaded["assembly"] == ASSEMBLY
                    and Path(loaded["location"]) == dll, f"{row['scenario']} 的加载身份或退出状态不符")
            require(row["scenario"] not in observed, "公告回归场景重复")
            observed[row["scenario"]] = row
    require(set(observed) == {case for cases in ADVISORIES.values() for case in cases}, "公告回归场景缺失")
    verify_input(args.input, args.input_sha256)
    require(sha256(feed / archive.name) == record["archiveSha256"], "验收包源中的候选归档已变化")
    public_assets = args.public_observation / "obj/project.assets.json"
    write_json(output / "report.json", {
        "status": "passed", "exitCode": 0, "producerCommit": revision,
        "independentInput": artifact(output / "acceptance-input.json", output),
        "sourceArchive": artifact(source_archive, output),
        "ordinary": summary | {"runtime": actual["runtime"], "architecture": actual["architecture"],
                               "runtimePath": actual["runtimePath"], "measurements": 24, "warmups": 12,
                               "loaded": actual["assemblies"], "differencesFromPublic": differences,
                               "observations": artifact(ordinary / "observations.json", output),
                               "identity": artifact(ordinary / "identity.json", output)},
        "publicR4": public_summary | {"archive": public_identity["archive"],
                                     "archiveSha256": public_identity["archiveSha256"],
                                     "restoreGraph": {"path": str(public_assets), "sha256": sha256(public_assets)},
                                     "thirdPartyPackages": sorted(public_dependencies),
                                     "loaded": public_report["assemblies"], "runtime": public_report["runtime"],
                                     "runtimePath": public_report["runtimePath"],
                                     "observations": str(args.public_observation / "observations.json")},
        "advisories": {key: {case: observed[case] for case in cases} for key, cases in ADVISORIES.items()},
        "advisoryIdentity": artifact(advisory / "identity.json", output),
        "clrLowStack": {"mapCoreIl": artifact(advisory / "mapper-il.log", output), "contract": CONTRACT,
                        "exceptionSource": "test-injection", "actualClrLowStackObserved": False},
    })
    print(f"引擎实包验收通过，见 {output / 'report.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="验收端独立登记文件")
    parser.add_argument("--input-sha256", required=True, help="独立登记文件的预期 SHA-256")
    parser.add_argument("--public-observation", type=Path, required=True, help="1.1 的已对账公开 R4 观测目录")
    parser.add_argument("--output", type=Path, required=True, help="待新建的证据目录")
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--ilspy", type=Path, required=True)
    args = parser.parse_args()
    for name in ("input", "public_observation", "output"):
        setattr(args, name, getattr(args, name).resolve())
    args.dotnet = args.dotnet.absolute()
    args.ilspy = args.ilspy.absolute()
    try:
        execute(args)
    except (BadZipFile, KeyError, OSError, TypeError, ValueError, VerificationError,
            subprocess.CalledProcessError) as error:
        print(f"引擎实包验收失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
