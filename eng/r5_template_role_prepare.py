"""从公开发行准备固定模板的两代 Release 入口。"""

import argparse
import ast
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from r2_packages import metadata_groups, nuspec_metadata
from r3_automapper_packages import check_edges, stack_package
from r3_leaf_packages import bytes_sha256, checked_file
from r3_template_net10_upgrade import (
    DEPS_TARGET, PATCH_VERSION, migrator_pkcs_platform_runtime, sql_server_chain, verify_resolved_versions,
)
from r3_template_net9_packages import REPLACEMENTS, TOPOLOGY, check_entry_output, compile_records, original_package
from r3_web_host import (
    NUGET_CONFIG, NUGET_SOURCE, SDK, artifact, package_hashes, project_path, read_project, read_sdk_packs, write_json,
)
from r5_candidate_batch import VERSIONS
from r5_public_mapping_consumer import release_rows
from r5_public_switch_assets import (
    COUNTS, R4_VERSIONS, RELEASES, TEMPLATE, TFM, bound_json, compare_graphs, entry_graph, verify_patch,
)
from verify import ROOT, VerificationError, read_json, require, sha256


GUIDE = ROOT / "docs/maintenance/r5-consumer-package-rollback.md"
GUIDE_SCRIPT_SHA = "3eca781f8cf1c44a762da0d8a1b713c09e2756cca44149ff211c951851bfd8c1"
TEMPLATE_ARCHIVE_SHA = "f553ce8ece1871c84d3466d7eb2eedfce23fe3c59d0342e51abcb5847b811300"
CORE = project_path("Core")
SHARED = ("Microsoft.AspNetCore.App", "Microsoft.NETCore.App")
STAGES = ("attachments", "toolchain", "template", "R4", "R5", "comparison")


def load_guide(path):
    # 原指南继续可独立执行。这里只加载同一冻结脚本的准备函数。
    body = path.read_text(encoding="utf-8").split("\n```python\n", 1)[1].split("\n```\n", 1)[0] + "\n"
    require(bytes_sha256(body.encode()) == GUIDE_SCRIPT_SHA, f"{path} 的公开演练脚本 SHA-256 不符")
    tree = ast.parse(body, filename=str(path))
    functions = {"require", "sha256", "read_json", "save", "command", "download", "project",
                 "change_project", "prepare", "expected_packages", "verify_entry", "inventory", "build"}
    tree.body = [node for node in tree.body if
                 (isinstance(node, (ast.Import, ast.ImportFrom))
                  and all(alias.name != "pymssql" for alias in node.names)) or
                 (isinstance(node, ast.Assign) and node.targets[0].id in {
                     "ATTACHMENTS", "BUILD_ENV", "ENTRIES", "MAPPING", "NUGET", "PREFIX",
                     "RELEASE_ASSETS", "RUNTIME", "SDK", "TEMPLATE", "TFM",
                 }) or (isinstance(node, ast.FunctionDef) and node.name in functions)]
    namespace = {}
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace


def validate_source(r4, r5, inventory):
    left, right = inventory(r4), inventory(r5)
    adapter = CORE.as_posix()
    require(left.keys() == right.keys()
            and {path for path, digest in left.items() if right[path] != digest} == {adapter},
            "两代准备源码差异须限于 Core 的映射适配器")
    old, new = (f'Include="Du.Abp.AutoMapper" Version="[{versions["Du.Abp.AutoMapper"]}]"'.encode()
                for versions in (R4_VERSIONS, VERSIONS))
    before = (r4 / CORE).read_bytes()
    require(before.count(old) == 1 and before.replace(old, new) == (r5 / CORE).read_bytes(),
            "两代 Core 项目唯一差异须为适配器的精确版本")
    return {"R4": left, "R5": right}


def audit_entry(root, release, entry, command, env, dotnet, checksums, lookup):
    source = root / f"source-{release}/aspnet-core"
    cache = root / f"packages-{release}"
    version = R4_VERSIONS if release == "R4" else VERSIONS
    label = f"{release}-{entry}"
    raw_assets = root / f"{label}-assets.json"
    raw = read_json(raw_assets)
    verify_resolved_versions(entry, raw["targets"][TFM])
    target = read_project(source, entry, raw_assets, cache, root / "NuGet.Config", lookup, topology=TOPOLOGY,
                          managed=stack_package, forbidden=original_package, tfm=TFM, deps_target=DEPS_TARGET,
                          managed_versions={f"Du.{name}": "[10.5.1]" for name in REPLACEMENTS[entry]})
    for name in target["projects"]:
        if name.split("/")[0] == CORE.stem:
            dependencies = target["projects"][name]["dependencies"]
            check_edges(CORE.stem, dependencies, {"Du.Abp.AutoMapper": f'[{version["Du.Abp.AutoMapper"]}]',
                                                  "Du.Abp.ZeroCore.EntityFrameworkCore": "[10.5.1]"}, assets=True)

    packages = read_json(root / f"{label}-packages.json")
    frozen = {name: {"asset": row["member"], "assetSha256": row["dllSha256"]}
              for name, row in packages.items() if name in version}
    for name, expected_edges in (
        ("Du.Abp.AutoMapper", {"Du.Abp": "[10.5.1]", "Du.AutoMapper": f'[{version["Du.AutoMapper"]}]',
                              "Du.AutoMapper.Collection": f'[{version["Du.AutoMapper.Collection"]}]'}),
        ("Du.AutoMapper.Collection", {"Du.AutoMapper": f'[{version["Du.AutoMapper"]}]'}),
    ):
        key = f"{name}/{version[name]}"
        item = target["packages"][key]
        require(item["archive"]["sha256"] == checksums[name], f"{label} {key} 签后归档已改变")
        with ZipFile(cache / item["archive"]["path"]) as archive:
            metadata = nuspec_metadata(archive)
            require((metadata.findtext("id"), metadata.findtext("version")) == (name, version[name]),
                    f"{label} {key} 的 nuspec 包身份不符")
            framework = Path(frozen[name]["asset"]).parts[1]
            dependencies = metadata_groups(metadata, "dependencies", "id")[framework]
            check_edges(key, {id_: row["version"] for id_, row in dependencies.items()}, expected_edges)
        check_edges(key, item["dependencies"], expected_edges, assets=True)

    def msbuild(name, targets, *queries):
        args = [str(dotnet), "msbuild", str(project_path(entry)), "-nologo", "-p:Configuration=Release",
                f"-target:{targets}", *queries]
        return json.loads(command(args, source, root / f"{label}-{name}.log", env))

    env = env | {"NUGET_PACKAGES": str(cache), "NUGET_HTTP_CACHE_PATH": str(root / f"http-cache-{release}")}
    sdk = msbuild("sdk-assets", "ResolveTargetingPackAssets;_GetAppHostPaths",
                  "-getItem:FrameworkReference,ResolvedTargetingPack,ResolvedAppHostPack,ResolvedAnalyzers",
                  "-getProperty:AppHostSourcePath,NetCoreTargetingPackRoot")
    target["sdkUsedPacks"] = read_sdk_packs(sdk, target, cache, dotnet.parent / "packs", True, tfm=TFM)
    target["selectedPackageAnalyzers"] = [artifact(Path(item["FullPath"]).resolve(), cache)
                                          for item in sdk["Items"]["ResolvedAnalyzers"]]
    items = msbuild("compile", "ResolveReferences;FindReferenceAssembliesForReferences",
                    "-getItem:ReferencePath,ReferencePathWithRefAssemblies")["Items"]
    target["compileReferences"] = compile_records(items, target, frozen, cache, source, tfm=TFM)
    items.update(msbuild("runtime", "ResolveLockFileCopyLocalFiles;_HandlePackageFileConflicts",
                         "-getItem:ReferenceCopyLocalPaths,_ConflictPackageFiles,PackageConflictPlatformManifests")["Items"])
    directory = root / "output" / release / entry
    platform_runtime = migrator_pkcs_platform_runtime(target, items, cache) if entry == "Migrator" else None
    output = check_entry_output(entry, directory, target, items, frozen, cache, tfm=TFM, deps_target=DEPS_TARGET,
                                platform_runtime=platform_runtime)
    options = output["runtimeOptions"]
    require(options["rollForward"] == "Disable" and
            {item["name"]: item["version"] for item in options["frameworks"]} == dict.fromkeys(SHARED, PATCH_VERSION),
            f"{label} 的固定共享框架声明不符")
    require(output["files"]["files"] == read_json(root / f"{label}-manifest.json"),
            f"{label} 的 Release 文件与指南封存清单不符")
    output["sqlServerChain"] = sql_server_chain(entry, target, output, cache)
    output_file = root / f"{label}-output.json"
    write_json(output_file, output)
    write_json(root / f"{label}-inventory.json", target)
    usage = {"cwd": directory.relative_to(root).as_posix(), "entry": output["entry"],
             "outputVerification": artifact(output_file, root),
             "signedPackages": artifact(root / f"{label}-packages.json", root),
             "rawAssets": artifact(raw_assets, root)}
    return usage, target


def verify_prepared(root, report_sha256, *, only_release=None):
    root = root.resolve()
    report = read_json(checked_file(root, "report.json", report_sha256))
    require((report.get("schemaVersion"), report.get("status"), report.get("exitCode")) == (1, "passed", 0),
            "准备报告缺失有效的通过结论")
    require(set(report["entries"]) == set(RELEASES), "准备报告缺少独立的 R4/R5 入口")
    bound_json(root, report["graphComparison"])
    require(only_release is None or only_release in RELEASES, f"未知公开版本：{only_release}")
    launches = {}
    for release, entries in report["entries"].items():
        if only_release is not None and release != only_release:
            continue
        require(set(entries) == set(COUNTS), f"{release} 缺少 Web.Host 或 Migrator")
        launches[release] = {}
        for entry, record in entries.items():
            for key in ("graph", "rawAssets", "signedPackages"):
                ref = record[key]
                checked_file(root, ref["path"], ref["sha256"])
            output = bound_json(root, record["outputVerification"])
            directory = root / "output" / release.upper() / entry
            require(directory.resolve() == directory and record["cwd"] == directory.relative_to(root).as_posix()
                    and output["entry"] == record["entry"], f"{release} {entry} 输出目录或入口不符")
            files = output["files"]["files"]
            actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
            require(actual == files.keys(), f"{release} {entry} Release 文件集合不符，缺少 {sorted(files.keys() - actual)}，"
                    f"多出 {sorted(actual - files.keys())}")
            for path, digest in files.items():
                require(not (directory / path).is_symlink() and (directory / path).resolve() == directory / path,
                        f"{release} {entry} 输出文件来源不符：{path}")
                checked_file(directory, path, digest)
            dll = checked_file(directory, record["entry"]["path"], record["entry"]["sha256"])
            argv = [report["toolchain"]["dotnet"], str(dll)]
            if entry == "Migrator":
                argv.append("-q")
            launches[release][entry] = {"argv": argv, "cwd": str(directory),
                                       "entrySha256": record["entry"]["sha256"], **{
                                           name: record[name] for name in ("outputVerification", "signedPackages", "rawAssets")
                                       }}
    return launches


def prepare(root, attachments, dotnet):
    root.mkdir()
    report = {"schemaVersion": 1, "status": "running", "exitCode": None,
              "stages": dict.fromkeys(STAGES, "not_run"), "entries": {}}
    path = root / "report.json"

    def stage(name):
        report["stages"][name] = "running"
        write_json(path, report)
        print(f"准备固定模板：{name}", flush=True)
        return name

    current = stage("attachments")
    try:
        guide = load_guide(GUIDE)
        report["guide"] = {"path": str(GUIDE.relative_to(ROOT)), "sha256": sha256(GUIDE),
                           "scriptSha256": GUIDE_SCRIPT_SHA}
        report["attachments"] = {}
        for release, input_file in attachments.items():
            target = root / f"{release.upper()}-PACKAGE-CHECKSUMS.json"
            shutil.copyfile(input_file, target)
            ref = artifact(target, root)
            _, _, digest = RELEASES[release]
            report["attachments"][release] = ref | {"input": str(input_file), "expectedSha256": digest}
            checked_file(root, ref["path"], digest)
            release_rows(release, target)

        original_download = guide["download"]

        def download(url, destination, env, headers=()):
            if destination.name == "template.tar.gz":
                original_download(url, destination, env, headers)
                checked_file(root, destination.name, TEMPLATE_ARCHIVE_SHA)
            else:
                checked_file(root, destination.name, RELEASES[destination.name[:2].lower()][2])

        original_command = guide["command"]

        def command(args, cwd, log, env):
            args = [str(dotnet) if arg == "dotnet" else str(arg) for arg in args]
            try:
                return original_command(args, cwd, log, env)
            except subprocess.TimeoutExpired as error:
                log.write_text(json.dumps({"argv": args, "cwd": str(cwd), "exitCode": None,
                                           "timeoutSeconds": error.timeout}) + "\n", encoding="utf-8")
                raise

        guide["download"] = download
        guide["command"] = command
        report["stages"][current] = "passed"
        current = stage("toolchain")
        require((platform.system(), platform.machine()) == ("Darwin", "arm64"), "需要 macOS ARM64")
        require(dotnet.is_file(), f"缺少 dotnet：{dotnet}")
        with TemporaryDirectory(prefix="du-dotnet-", dir="/tmp") as temp:
            home = root / "tools-home"
            home.mkdir()
            env = guide["BUILD_ENV"] | {"HOME": str(home), "DOTNET_CLI_HOME": str(home), "TMPDIR": temp,
                                        "DOTNET_NOLOGO": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                                        "MSBUILDDISABLENODEREUSE": "1", "DOTNET_CLI_USE_MSBUILD_SERVER": "0"}
            write_json(root / "global.json", {"sdk": {"version": SDK, "rollForward": "disable"}})
            config = root / "NuGet.Config"
            config.write_text(NUGET_CONFIG, encoding="utf-8")
            sdk = command(["dotnet", "--version"], root, root / "sdk.log", env).strip()
            require(sdk == SDK, f"SDK 预期 {SDK}，实际 {sdk}")
            runtimes = command(["dotnet", "--list-runtimes"], root, root / "runtimes.log", env).splitlines()
            for name in SHARED:
                require(any(line.startswith(f"{name} {PATCH_VERSION} ") for line in runtimes),
                        f"缺少 {name} {PATCH_VERSION}")
            report["toolchain"] = {"platform": platform.platform(), "sdk": sdk, "dotnet": str(dotnet),
                                   "targetFramework": TFM, "configuration": "Release",
                                   "runtimeConfigVersion": PATCH_VERSION, "nugetConfig": artifact(config, root)}
            report["stages"][current] = "passed"
            current = stage("template")
            checksums = guide["expected_packages"](root, env)
            migrations, _ = guide["prepare"](root, env)
            sources = validate_source(root / "source-R4/aspnet-core", root / "source-R5/aspnet-core", guide["inventory"])
            source_manifest = root / "source-inventory.json"
            write_json(source_manifest, sources)
            report["template"] = {"commit": TEMPLATE, "archive": artifact(root / "template.tar.gz", root),
                                  "preparedSources": artifact(source_manifest, root), "migrationIds": migrations}
            report["stages"][current] = "passed"
            graphs = {}
            report["nugetCaches"] = {}
            for release in ("R4", "R5"):
                current = stage(release)
                cache = root / f"packages-{release}"
                http_cache = root / f"http-cache-{release}"
                require(not cache.exists() and not http_cache.exists(), f"{release} 还原缓存必须从空目录开始")
                report["nugetCaches"][release.lower()] = {"packages": cache.name, "http": http_cache.name,
                                                            "initiallyEmpty": True, "sources": [NUGET_SOURCE]}
                guide["build"](root, release, checksums[release], env)
                report["entries"][release.lower()] = entries = {}
                graphs[release] = {}
                checked = {}

                def lookup(key, relative):
                    if (key, relative) not in checked:
                        checked[key, relative] = package_hashes(cache, key, relative)
                    return checked[key, relative]

                for entry in COUNTS:
                    usage, inventory = audit_entry(root, release, entry, command, env, dotnet,
                                                   checksums[release], lookup)
                    evidence = {"rawAssets": {entry: usage["rawAssets"]},
                                "inputs": {"entryOutputs": {"net10": {entry: usage["outputVerification"]}},
                                           "nuget": {"effectiveSources": [NUGET_SOURCE], "cachesInitiallyEmpty": True}}}
                    graph, paths = entry_graph(root, evidence, inventory, entry, historical=False, cache=cache)
                    graph_file = root / f"{release}-{entry}-graph.json"
                    write_json(graph_file, {"nodes": graph["nodes"], **paths,
                                            "edges": [(*key, value) for key, value in sorted(graph["edges"].items())],
                                            "assets": [(*key, value) for key, value in sorted(graph["assets"].items())]})
                    entries[entry] = usage | {"graph": artifact(graph_file, root)}
                    graphs[release][entry] = graph
                report["stages"][current] = "passed"
            current = stage("comparison")
            comparisons = {entry: compare_graphs(graphs["R4"][entry], graphs["R5"][entry]) for entry in COUNTS}
            differences = root / "graph-comparison.json"
            write_json(differences, comparisons)
            report["graphComparison"] = artifact(differences, root)
            for entry, difference in comparisons.items():
                verify_patch(graphs["R4"][entry], graphs["R5"][entry], difference)
            for release, files in sources.items():
                for name, digest in files.items():
                    checked_file(root / f"source-{release}/aspnet-core", name, digest)
            report["stages"][current] = "passed"
        report.update(status="passed", exitCode=0)
    except (VerificationError, OSError, RuntimeError, ValueError, KeyError, IndexError, TypeError, BadZipFile,
            ET.ParseError, subprocess.SubprocessError) as error:
        report["stages"][current] = "failed"
        report.update(status="failed", exitCode=1, reason=str(error))
        print(f"{current} 失败：{error}", file=sys.stderr)
    write_json(path, report)
    return report["exitCode"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    build = sub.add_parser("prepare")
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--r4-checksums", type=Path, required=True)
    build.add_argument("--r5-checksums", type=Path, required=True)
    build.add_argument("--dotnet", type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("--prepared", type=Path, required=True)
    verify.add_argument("--report-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.action == "verify":
            print(json.dumps(verify_prepared(args.prepared, args.report_sha256), ensure_ascii=False, indent=2))
            return 0
        dotnet = args.dotnet or Path(shutil.which("dotnet") or "dotnet")
        return prepare(args.output.resolve(),
                       {"r4": args.r4_checksums.resolve(), "r5": args.r5_checksums.resolve()}, dotnet.resolve())
    except (OSError, VerificationError, KeyError, TypeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
