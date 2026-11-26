"""用同一 R4 冻结主包运行有界的映射回归，并核对低栈保护的 IL。"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from r3_template_net9_packages import source_config
from r3_web_host import SDK, artifact, package_hashes, write_json
from r4_candidate_batch import load_frozen_batch
from verify import ROOT, read_json, require, sha256


CONTRACT = ("https://learn.microsoft.com/en-us/dotnet/api/system.runtime.compilerservices."
            "runtimehelpers.ensuresufficientexecutionstack?view=net-9.0")


def execute(batch_root, output, dotnet, ilspy):
    batch = load_frozen_batch(batch_root)
    archive = batch["packages"]["Du.AutoMapper"]["archive"]
    version = batch["packages"]["Du.AutoMapper"]["version"]
    target = read_json(batch_root / "inspection.json")["Du.AutoMapper"]["targets"]["net8.0"]
    digest = target["assetSha256"]

    source = ROOT / batch["producers"]["engine"]["path"]
    revision = batch["producers"]["engine"]["finalCommit"]
    output.mkdir()
    git = ["git", "-C", source, "archive", revision, "Directory.Build.props", "src/RecursionProbe"]
    archive_path = output / "probe-source.tar"
    with archive_path.open("wb") as destination:
        subprocess.run(git, stdout=destination, check=True)
    commands = [{"argv": list(map(str, git)), "cwd": str(Path.cwd()), "exitCode": 0}]
    env = os.environ | {
        "NUGET_PACKAGES": str(output / "packages"),
        "NUGET_HTTP_CACHE_PATH": str(output / "http-cache"),
        "NUGET_PLUGINS_CACHE_PATH": str(output / "plugins-cache"),
        "MSBUILDDISABLENODEREUSE": "1",
    }

    def command(label, args):
        args = list(map(str, args))
        log = output / label
        with log.open("wb") as stream:
            result = subprocess.run(args, cwd=output, env=env, stdout=stream, stderr=subprocess.STDOUT)
        commands.append({"argv": args, "cwd": str(output), "exitCode": result.returncode,
                         "log": artifact(log, output)})
        write_json(output / "commands.json", commands)
        require(result.returncode == 0, f"{label} 退出 {result.returncode}")

    command("source-extract.log", ["tar", "-xf", archive_path])
    config = output / "NuGet.Config"
    feed = batch_root / "feed"
    source_config(config, feed, ("Du.AutoMapper",))
    write_json(output / "global.json", {"sdk": {"version": SDK, "rollForward": "disable"}})
    probe = output / "src/RecursionProbe"
    project = probe / "RecursionProbe.csproj"
    selection = f"-p:CandidateVersion={version}"
    command("sdk.log", [dotnet, "--info"])
    command("restore.log", [dotnet, "restore", project, "--configfile", config, "--no-http-cache", selection])
    cache = Path(env["NUGET_PACKAGES"])
    key = f"Du.AutoMapper/{version}"
    graph = read_json(probe / "obj/project.assets.json")
    selected = graph["targets"]["net9.0"][key]
    require({*selected["compile"]} == {*selected["runtime"]} == {target["asset"]}, "映射引擎资产不符")
    restored = package_hashes(cache, key, graph["libraries"][key]["path"], str(feed))
    require(restored["archive"]["sha256"] == archive["sha256"], "空缓存还原后的映射引擎主包摘要不符")
    command("build.log", [dotnet, "build", project, "-c", "Release", "--no-restore",
                          "--disable-build-servers", selection])
    program = probe / "bin/Release/net9.0/RecursionProbe.dll"
    dll = program.with_name("AutoMapper.dll")
    require(sha256(dll) == digest, "映射引擎运行输出与包内 DLL 摘要不符")
    common = [sys.executable, "-B", probe / "run-probes.py", "--dotnet", dotnet, "--program", program,
              "--dll-sha256", digest]
    command("behavior.log", [*common, "--output", output / "behavior"])
    command("exception.log", [*common, "--scenario", "application-exception", "--output", output / "exception"])
    il = output / "mapper.il"
    command(il.name, [ilspy, "--ilcode", "--type", "AutoMapper.Mapper", dll])
    require(re.search(r"(?ms)^\s*\).*?\bRuntimeHelpers::EnsureSufficientExecutionStack\(\)"
                      r"(?:(?!end of method).)*end of method Mapper::MapCore\b", il.read_text()),
            "MapCore 中缺少 CLR 栈检查")
    groups = {"GHSA-rvv3-g6hj-g44x": ("reference-graph",),
              "GHSA-6vhm-j9h7-f9gh": ("constructor-depth",),
              "GHSA-gpwp-5797-mjff": ("runtime-dispatch", "application-exception")}
    observed = {}
    for folder in ("behavior", "exception"):
        report = output / folder / "report.json"
        for case in read_json(report):
            require(case["passed"] and case["actual"]["sha256"] == digest
                    and Path(case["actual"]["location"]) == dll, f"{case['scenario']} 实际加载字节不符")
            observed[case["scenario"]] = {
                "loadedSha256": case["actual"]["sha256"], "report": artifact(report, output),
                "stdout": artifact(report.parent / f"{case['scenario']}.stdout", output),
            }
    write_json(output / "report.json", {
        "batch": artifact(batch_root / "batch.json", batch_root), "producerCommit": revision,
        "sourceArchive": artifact(archive_path, output), "status": "passed", "exitCode": 0,
        "results": {key: {"archive": archive, "asset": target["asset"], "assetSha256": digest,
                          "scenarios": {case: observed[case] for case in cases}}
                    for key, cases in groups.items()},
        "clrLowStack": {"mapCoreIl": artifact(il, output), "contract": CONTRACT,
                        "exceptionSource": "test-injection", "actualClrLowStackObserved": False},
    })
    load_frozen_batch(batch_root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dotnet", type=Path, default=shutil.which("dotnet"))
    parser.add_argument("--ilspy", type=Path, required=True)
    args = parser.parse_args()
    execute(args.batch_root.resolve(), args.output.resolve(), args.dotnet.resolve(), args.ilspy.resolve())


if __name__ == "__main__":
    main()
