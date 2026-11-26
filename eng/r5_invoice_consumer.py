"""从独立空缓存对照公开和本地引擎包的默认发票映射。"""

import argparse
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from zipfile import BadZipFile

from r3_template_net9_packages import source_config
from r3_web_host import NUGET_SOURCE, SDK, artifact, inside, package_hashes, write_json
from r4_candidate_batch import run_logged
from r5_engine_consumer import ASSEMBLY, ASSET, PACKAGE, VERSION, verify_input, verify_restored
from verify import ROOT, VerificationError, read_json, require, sha256


TFM = "net10.0"
PROJECT = "InvoiceProbe"
SOURCES = ROOT / "eng/r5-invoice-probe"


def build(work, dotnet, feed, version, verify_graph, project_name, sources):
    work.mkdir()
    cache, temp, scratch = (work / name for name in ("packages", "temp", "nuget-scratch"))
    for path in (cache, temp, scratch):
        path.mkdir()
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

    def command(label, *argv):
        return run_logged(argv, work, label, work, env)

    for source in sorted(sources.glob("*.cs")):
        shutil.copyfile(source, work / source.name)
    template = ROOT / "AutoMapper/src/CollectionOrderProbe/CollectionOrderProbe.csproj"
    project = work / f"{project_name}.csproj"
    project.write_text(template.read_text().replace("[14.0.0]", f"[{version}]"), encoding="utf-8")
    config = work / "NuGet.Config"
    source_config(config, feed, (PACKAGE,))
    command("resources", "df", "-h", work, cache, temp, scratch)
    command("sdk", dotnet, "--info")
    command("restore", dotnet, "restore", project, "--configfile", config,
            "--no-http-cache", "--disable-build-servers", "--verbosity", "normal")
    asset_hash, packages = verify_graph(cache)
    key = f"{PACKAGE}/{version}"
    archive = inside(cache, packages[key]["archive"]["path"])
    dll = inside(cache, Path(packages[key]["cachePath"]) / ASSET)
    require(sha256(dll) == asset_hash, f"{version} 缓存 DLL 与归档不符")
    command("build", dotnet, "build", project, "-c", "Release", "--no-restore", "--disable-build-servers")
    program = work / "bin/Release" / TFM / f"{project_name}.dll"
    identity = {
        "graph": artifact(work / "obj/project.assets.json", work),
        "nugetConfig": artifact(config, work),
        "packages": packages,
        "archive": {"path": str(archive), "sha256": sha256(archive)},
        "packageAsset": ASSET,
        "assetSha256": asset_hash,
        "cacheAsset": {"path": str(dll), "sha256": sha256(dll)},
        "releaseAsset": artifact(program.with_name("AutoMapper.dll"), work),
    }
    write_json(work / "identity.json", identity)
    return command, program, identity


def read_observations(work, command, dotnet, program, identity):
    measured = json.loads(command("measurements", dotnet, program))
    audited = json.loads(command("plan-observations", dotnet, program, "--inspect-plans"))
    write_json(work / "measurements.json", measured)
    write_json(work / "plan-observations.json", audited)
    dll = program.with_name("AutoMapper.dll")
    require(len(measured["assemblies"]) == 1, "进程应只加载一份 AutoMapper")
    loaded = measured["assemblies"][0]
    require(loaded["name"] == ASSEMBLY and loaded["context"] == "Default"
            and Path(loaded["path"]).resolve() == dll.resolve()
            and loaded["sha256"] == sha256(dll) == identity["assetSha256"],
            "实际加载程序集、路径或摘要不符")
    require(not measured["plans"] and {key: value for key, value in audited.items() if key != "plans"}
            == {key: value for key, value in measured.items() if key != "plans"},
            "独立计划观察的运行条件或业务结果与正式测量不符")
    return measured, audited


def observe(work, command, dotnet, program, identity, checks):
    measured, audited = read_observations(work, command, dotnet, program, identity)
    summary = checks["verify_observations"](measured, program.with_name("AutoMapper.dll"), identity)
    rows = measured["observations"]
    require([(plan["Case"], plan["Repeat"]) for plan in audited["plans"]]
            == [(row["Case"], row["Repeat"]) for row in rows], "计划观察覆盖不足")
    for row in rows:
        expected = measured["expected"]
        warmup = measured["warmup"]
        warm_expected = [{"SameDestination": True, "Number": warmup[f"{name}Number"], "Lines": [warmup["line"]]}
                         for name in row["WarmupOrder"]]
        for result, target in zip(row["Warmups"] + row["Measurements"], warm_expected + [expected] * 2, strict=True):
            matches = result["Actual"] == target and not result["Exceptions"]
            require(result["MatchesExpected"] == matches, "业务断言与逐次实际结果不符")
    return measured, summary | {
        "measurements": sum(len(row["Measurements"]) for row in rows),
        "warmupCalls": sum(len(row["Warmups"]) for row in rows),
        "coldFirstCalls": sum(not row["WarmupOrder"] for row in rows),
        "loaded": measured["assemblies"][0],
        "raw": artifact(work / "measurements.json", work.parent),
        "plans": artifact(work / "plan-observations.json", work.parent),
        "identity": artifact(work / "identity.json", work.parent),
    }


def compare_packages(args, project_name, sources, observe_package):
    record, archive = verify_input(args.input, args.input_sha256)
    output = args.output
    output.mkdir()
    shutil.copyfile(args.input, output / "acceptance-input.json")
    write_json(output / "global.json", {"sdk": {"version": SDK, "rollForward": "disable"}})
    checks = runpy.run_path(str(ROOT / "AutoMapper/src/CollectionOrderProbe/verify.py"))
    public_version = checks["VERSION"]
    public_digest = checks["get_expected_package"](output, args.public_manifest, args.verified_downloads)
    public = output / "public"

    def public_graph(cache):
        graph = read_json(public / "obj/project.assets.json")
        identity = checks["verify_restored_package"](cache, graph, public_digest)
        packages = {key: package_hashes(cache, key, entry["path"], NUGET_SOURCE)
                    for key, entry in graph["libraries"].items()}
        return identity["assetSha256"], packages

    command, program, identity = build(public, args.dotnet, None, public_version, public_graph,
                                       project_name, sources)
    old, old_summary = observe_package(public, command, args.dotnet, program, identity, checks)

    candidate = output / "candidate"
    dependencies = set(identity["packages"]) - {f"{PACKAGE}/{public_version}"}
    feed = archive.parent

    def candidate_graph(cache):
        _, packages, _ = verify_restored(candidate, cache, TFM, feed, record, dependencies)
        return record["assetSha256"], packages

    command, program, identity = build(candidate, args.dotnet, feed, VERSION, candidate_graph,
                                       project_name, sources)
    new, new_summary = observe_package(candidate, command, args.dotnet, program, identity, checks)
    return record, old, old_summary, new, new_summary


def execute(args):
    record, old, old_summary, new, new_summary = compare_packages(args, PROJECT, SOURCES, observe)
    output = args.output

    fields = ("runtime", "architecture", "runtimePath", "input", "initial", "warmup", "expected")
    require(all(old[key] == new[key] for key in fields), "运行环境或业务输入不同")
    differences = []
    for left, right in zip(old["observations"], new["observations"], strict=True):
        for key in ("Case", "Repeat", "Registration", "WarmupOrder"):
            require(left[key] == right[key], f"对照顺序不同：{key}")
        for label in ("Warmups", "Measurements"):
            for index, (before, after) in enumerate(zip(left[label], right[label], strict=True), 1):
                if before != after:
                    differences.append({"case": left["Case"], "repeat": left["Repeat"], "field": label,
                                        "call": index, "public": before, "candidate": after})
    candidate_expected = (set(new_summary["pairs"].values()) == {"as-expected"}
                          and not new_summary["warmupDeviations"])
    stable = all(not summary["warmupDeviations"] and "unstable" not in summary["pairs"].values()
                 for summary in (old_summary, new_summary))
    exit_code = 0 if stable and candidate_expected else 2
    write_json(output / "report.json", {
        "exitCode": exit_code,
        "environmentAndInput": {key: old[key] for key in fields},
        "publicManifest": artifact(output / "R4-PACKAGE-CHECKSUMS.json", output),
        "verifiedPublicDownloads": artifact(output / "verified-downloads.json", output),
        "candidateInput": artifact(output / "acceptance-input.json", output),
        "candidateProducerCommit": record["producerCommit"],
        "public": old_summary,
        "candidate": new_summary,
        "differences": differences,
        "invoiceFreezeEvidence": old_summary["stableOrderDifference"] and candidate_expected,
    })
    print(f"默认发票实包观测见 {output / 'report.json'}")
    return exit_code


def main(execute_consumer=execute, description=__doc__, failure_label="默认发票对照"):
    parser = argparse.ArgumentParser(description=description)
    for name in ("public-manifest", "verified-downloads", "input", "dotnet", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    args = parser.parse_args()
    for name in ("public_manifest", "verified_downloads", "input", "output"):
        setattr(args, name, getattr(args, name).resolve())
    args.dotnet = args.dotnet.absolute()
    try:
        return execute_consumer(args)
    except (BadZipFile, KeyError, OSError, TypeError, ValueError, VerificationError,
            subprocess.CalledProcessError) as error:
        print(f"{failure_label}失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
