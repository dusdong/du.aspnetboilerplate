"""核对 Module Zero 实际还原、编译、复制和运行的包资产。"""

from pathlib import Path
import re
from zipfile import ZipFile

from r2_assets import asset_owners, check_reachable
from r2_packages import NUGET_SOURCE, framework_package, version_range
from r3_leaf_assets import verify_selected_owners
from r3_leaf_packages import TFM, bytes_sha256
from r3_module_zero_packages import ASP_NET, TOP_PACKAGE, expected_edges
from r3_web_host import check_runtime_declarations, download_records, inside, package_hashes, runtime_selection
from verify import read_json, require, sha256


APP = "ModuleZeroProbe"
TARGET = ".NETCoreApp,Version=v9.0"
SQLITE = "Microsoft.EntityFrameworkCore.Sqlite"
SQLITE_VERSION = "9.0.18"
BRIDGE = "Castle.Windsor.MsDependencyInjection"
SHARED = {"Microsoft.NETCore.App": "System.Private.CoreLib.dll",
          ASP_NET: "Microsoft.Extensions.Identity.Core.dll"}
SQLITE_ASSEMBLIES = {
    "Microsoft.EntityFrameworkCore": "Microsoft.EntityFrameworkCore/9.0.18",
    "Microsoft.EntityFrameworkCore.Relational": "Microsoft.EntityFrameworkCore.Relational/9.0.18",
    SQLITE: "Microsoft.EntityFrameworkCore.Sqlite.Core/9.0.18",
    "Microsoft.Data.Sqlite": "Microsoft.Data.Sqlite.Core/9.0.18",
    "SQLitePCLRaw.core": "SQLitePCLRaw.core/2.1.10",
    "SQLitePCLRaw.provider.e_sqlite3": "SQLitePCLRaw.provider.e_sqlite3/2.1.10",
    "SQLitePCLRaw.batteries_v2": "SQLitePCLRaw.bundle_e_sqlite3/2.1.10",
}
SQLITE_NATIVE = "libe_sqlite3.dylib"
SQLITE_NATIVE_PACKAGE = "SQLitePCLRaw.lib.e_sqlite3/2.1.10"
SQLITE_NATIVE_ASSET = f"runtimes/osx-arm64/native/{SQLITE_NATIVE}"


def exact_ranges(version):
    return {f"[{version}]", f"[{version},{version}]"}


def check_assets(data, project, cache, feeds, packages):
    restore = data["project"]["restore"]
    require(Path(restore["projectPath"]).resolve() == project and Path(restore["packagesPath"]).resolve() == cache and
            {Path(folder).resolve() for folder in data["packageFolders"]} == {cache}, "还原项目或独立包缓存不符")
    require(set(restore["sources"]) == {*map(str, feeds.values()), NUGET_SOURCE} and
            restore["configFilePaths"] == [str(project.parent / "NuGet.Config")] and not restore.get("fallbackFolders"),
            "实际 NuGet 配置、来源或回退目录不符")
    require(set(data["targets"]) == {TFM} and restore["originalTargetFrameworks"] == [TFM],
            f"只应还原 {TFM}，实际 {list(data['targets'])}")
    require(not restore["frameworks"][TFM]["projectReferences"], "独立消费者出现源码项目引用")
    require(not any(log.get("code") == "NU1605" or log.get("level") == "Error" for log in data.get("logs", [])),
            "还原资产存在错误或降级")

    version = packages[TOP_PACKAGE]["version"]
    framework = data["project"]["frameworks"][TFM]
    direct = framework["dependencies"]
    expected = {TOP_PACKAGE: version, SQLITE: SQLITE_VERSION, BRIDGE: "4.1.0"}
    require(direct.keys() == expected.keys() and all(
        item["target"] == "Package" and item["version"].replace(" ", "") in exact_ranges(expected[name])
        for name, item in direct.items()), f"消费根引用及范围不符：{direct}")
    graph = data["targets"][TFM]
    framework_keys = {key for key in graph if framework_package(key.split("/")[0])}
    expected_keys = {f"{name}/{item['version']}" for name, item in packages.items()}
    require(framework_keys == expected_keys, f"六包闭包不符，预期 {sorted(expected_keys)}，实际 {sorted(framework_keys)}")
    require(graph.keys() == data["libraries"].keys(), "还原图出现未选中或无关资产库")
    require({f"{name}/{value}" for name, value in expected.items()} <= graph.keys(), "直接包未实选固定版本")
    check_reachable(graph, direct, TFM)

    records, edges, dlls = {}, {}, {}
    expected_framework_edges = expected_edges(version)
    for key, entry in graph.items():
        name, version = key.split("/")
        library = data["libraries"][key]
        require(entry["type"] == library["type"] == "package", f"{key} 非独立包引用")
        package = packages.get(name)
        source = str(feeds[version]) if package else NUGET_SOURCE
        hashes = package_hashes(cache, key, library["path"], source)
        require(hashes["contentSha512"] == library["sha512"], f"{key} NuGet 内容哈希与还原图不符")
        dependencies = entry.get("dependencies", {})
        records[key] = {"id": name, "version": version, "direct": name in direct, **hashes,
                        "dependencies": dependencies, "assets": {section: values for section, values in entry.items()
                                                                  if section not in ("type", "dependencies")}}
        if package:
            require(hashes["archive"]["sha256"] == package["archiveSha256"], f"{key} 还原归档 SHA-256 不符")
            expected_deps = package["dependencies"]
            require(dependencies.keys() == expected_deps.keys(), f"{key} 实选依赖 ID 与 nuspec 不符：{dependencies}")
            for dependency, value in dependencies.items():
                declared = expected_deps[dependency]
                if re.fullmatch(r"\[[^,]+\]", declared):
                    allowed = exact_ranges(declared[1:-1])
                    normalized = value.replace(" ", "")
                else:
                    allowed = {version_range(declared)}
                    normalized = version_range(value)
                require(normalized in allowed, f"{key} → {dependency} 依赖范围不符，预期 {declared}，实际 {value}")
            internal = {dep: expected_deps[dep] for dep in dependencies if framework_package(dep)}
            require(internal == expected_framework_edges[name],
                    f"{key} 框架边不符，预期 {expected_framework_edges[name]}，实际 {internal}")
            edges[name] = internal
            require(sorted(entry.get("frameworkReferences", [])) == package["frameworkReferences"],
                    f"{key} 共享框架引用不符")
            asset = package["asset"]
            verify_selected_owners(graph, key, asset)
            require(all(set(entry.get(section, {})) == {asset} for section in ("compile", "runtime")),
                    f"{key} 存在额外编译或运行资产")
            path = inside(cache, Path(hashes["cachePath"]) / asset)
            require(sha256(path) == package["assetSha256"], f"{key} 还原 DLL 与归档 SHA-256 不符")
            dlls[Path(asset).name] = {"package": key, "asset": asset, "archive": package["archive"],
                                     "restored": str(path), "sha256": package["assetSha256"]}
    source = lambda key, relative: package_hashes(cache, key, relative)
    downloads = download_records(framework, cache, source, {key.casefold() for key in graph})
    return {"directPackages": direct, "packages": records, "frameworkEdges": edges, "frameworkDlls": dlls,
            "restoreFrameworkReferences": framework["frameworkReferences"], "sdkDownloads": downloads}


def runtime_packages(libraries, assets, selection, references, *, cache=None):
    resolved = assets["packages"]
    runtime = {key for key, entry in libraries.items() if entry["type"] == "package"}
    require(runtime <= resolved.keys(), f"Release .deps.json 出现未还原的包：{sorted(runtime - resolved.keys())}")
    omitted = {}
    for key in sorted(resolved.keys() - runtime):
        require(key not in selection and not framework_package(resolved[key]["id"]),
                f"Release .deps.json 缺少应复制的运行或框架包 {key}")
        selected = resolved[key]["assets"]
        require(not any(selected.get(section) for section in ("native", "resources")),
                f"Release .deps.json 遗漏 {key} 的原生或资源运行资产")
        rid_assets = selected.get("runtimeTargets", {})
        conflicts = {Path(row["FullPath"]).resolve() for row in references.get("_ConflictPackageFiles", [])}
        require(not rid_assets or cache is not None and
                all(info["assetType"] == "runtime" and Path(asset).suffix.casefold() == ".dll"
                    and inside(cache, Path(resolved[key]["cachePath"]) / asset) in conflicts
                    for asset, info in rid_assets.items()),
                f"Release .deps.json 遗漏 {key} 的 RID 运行资产，缺少 SDK 冲突剔除记录")
        omitted[key] = {}
        for filename in sorted({Path(asset).name for section in ("compile", "runtime", "runtimeTargets")
                                for asset in selected.get(section, {}) if asset.lower().endswith(".dll")}):
            matches = [item for item in references["ReferencePath"] if Path(item["FullPath"]).name == filename]
            require(len(matches) == 1 and matches[0].get("FrameworkReferenceName") in SHARED,
                    f"Release .deps.json 省略 {key} {filename}，缺少相应共享框架编译来源")
            path = Path(matches[0]["FullPath"])
            omitted[key][filename] = {"framework": matches[0]["FrameworkReferenceName"],
                                      "path": str(path), "sha256": sha256(path)}
            if discarded := [asset for asset in rid_assets if Path(asset).name == filename]:
                omitted[key][filename]["discardedRidCandidates"] = discarded
    excluded = {resolved[key]["id"] for key in omitted}
    retained = {key: {**resolved[key], "dependencies": {name: value for name, value in
                 resolved[key]["dependencies"].items() if name not in excluded}} for key in runtime}
    return retained, omitted


def check_output(output, assets, cache, references, copy_items):
    selection = runtime_selection(copy_items, assets, cache)
    deps = read_json(output / f"{APP}.deps.json")
    config = read_json(output / f"{APP}.runtimeconfig.json")["runtimeOptions"]
    require(deps["runtimeTarget"]["name"] == TARGET and config["tfm"] == TFM and
            {entry["name"] for entry in config["frameworks"]} == SHARED.keys(), "Release 输出目标或共享框架不符")
    graph = deps["targets"][TARGET]
    libraries = deps["libraries"]
    retained, omitted = runtime_packages(libraries, assets, selection, references)
    files = check_runtime_declarations(
        output, output.rglob("*.dll"), graph, libraries,
        {**assets, "packages": retained, "entryProject": f"{APP}/1.0.0", "projects": {}, "projectReferences": [],
         "sdkRuntimeSelection": selection})
    framework = assets["frameworkDlls"]
    actual = {path for path in files if framework_package(Path(path).stem)}
    require(actual == framework.keys(), f"Release 框架 DLL 缺失、重名或混装：{sorted(actual)}")
    verified = {}
    for dll, item in framework.items():
        key, asset = item["package"], item["asset"]
        require(asset_owners(graph, ("runtime", "runtimeTargets"), dll) == [(key, asset)] and
                selection[key]["runtime"][asset] == {"outputPath": dll},
                f"{dll} .deps.json 或 MSBuild 复制项的来源不符")
        compile_paths = [row["FullPath"] for row in references["ReferencePath"]
                         if Path(row["FullPath"]).name.casefold() == dll.casefold()]
        require(compile_paths == [item["restored"]] and sha256(output / dll) == item["sha256"],
                f"{dll} 实际编译引用或 Release DLL 摘要不符：{compile_paths}")
        verified[dll] = {**item, "compile": compile_paths[0], "output": str(output / dll)}
    return {"frameworkDlls": verified, "sdkRuntimeSelection": selection, "runtimeConfig": config,
            "omittedRuntimePackages": omitted}


def check_shared(runtime, dotnet, pid):
    require(runtime["pid"] == pid and runtime["rid"] == "osx-arm64" and runtime["architecture"] == "Arm64" and
            Path(runtime["dotnet"]).resolve() == dotnet, "消费进程 PID、可执行文件或实际架构不符")
    require(runtime["shared"].keys() == SHARED.keys(), "缺少两项实际共享框架加载证据")
    shared = {}
    for name, assembly in SHARED.items():
        path = Path(runtime["shared"][name])
        version = path.parent.name
        directory = dotnet.parent / "shared" / name / version
        require(re.fullmatch(r"9\.0\.(?:0|[1-9][0-9]*)", version) and path.is_absolute() and path.is_file() and
                path.resolve() == (directory / assembly).resolve(), f"{name} 实际共享框架版本或来源不符：{path}")
        shared[name] = {"version": version, "path": str(path), "source": str(directory), "sha256": sha256(path)}
    require(runtime["framework"] == f".NET {shared['Microsoft.NETCore.App']['version']}",
            "进程框架版本与实际 CoreLib 来源不符")
    return shared


def check_runtime(runtime, dotnet, pid, output, assets, outputs, cache):
    shared = check_shared(runtime, dotnet, pid)
    framework = outputs["frameworkDlls"]
    loaded = runtime["assemblies"]
    require(loaded.keys() == {Path(dll).stem for dll in framework} | SQLITE_ASSEMBLIES.keys(),
            "实际加载程序集缺失或集合不符")
    for dll, item in framework.items():
        name = Path(dll).stem
        record = loaded[name]
        require(Path(record["path"]) == output / dll and record["sha256"] == item["sha256"] == sha256(output / dll)
                and record["target"] == TARGET and record["identity"].split(", ")[:2] == [name, "Version=10.5.1.0"],
                f"{dll} 实际加载位置、目标、身份或字节不符")
    selected = outputs["sdkRuntimeSelection"]
    sqlite = {}
    for name, key in SQLITE_ASSEMBLIES.items():
        dll = f"{name}.dll"
        package = assets["packages"][key]
        choices = [entry for entry in selected[key]["runtime"].items() if Path(entry[0]).name == dll]
        require(len(choices) == 1, f"{key} {dll} 没有唯一的 Provider 或 EF Core 运行资产")
        asset, copied = choices[0]
        require(asset in package["assets"]["compile"], f"{key} {dll} 缺少对应编译资产")
        record = loaded[name]
        version = package["version"]
        require(record["informationalVersion"] == version and record["identity"].startswith(f"{name}, Version={version}."),
                f"{dll} 实际 SQLite/EF Core 版本与 {key} 不符")
        sqlite[name] = check_runtime_asset(cache, output, package, key, asset, copied["outputPath"], record)
    key, asset = SQLITE_NATIVE_PACKAGE, SQLITE_NATIVE_ASSET
    selected_native = selected[key]["runtimeTargets"][asset]
    require(selected_native["rid"] == runtime["rid"] and selected_native["assetType"] == "native",
            f"{key} SQLite 原生资产的 RID 或类型不符")
    native = check_runtime_asset(cache, output, assets["packages"][key], key, asset,
                                 selected_native["outputPath"], runtime["sqliteNative"])
    require(re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", runtime["sqliteVersion"]),
            "缺少 SQLite 连接报告的实际原生版本")
    return {"shared": shared, "assemblies": loaded, "sqliteManaged": sqlite, "sqliteNative": native,
            "sqliteVersion": runtime["sqliteVersion"], "pid": pid, "architecture": runtime["architecture"],
            "rid": runtime["rid"], "dotnet": runtime["dotnet"]}


def check_runtime_asset(cache, output, package, key, asset, destination, record):
    restored = inside(cache, Path(package["cachePath"]) / asset)
    archive = inside(cache, package["archive"]["path"])
    target = inside(output, destination)
    with ZipFile(archive) as package_zip:
        require(package_zip.namelist().count(asset) == 1, f"{key} 归档缺少唯一的 {asset}")
        digest = bytes_sha256(package_zip.read(asset))
    require(Path(record["path"]).resolve() == target and
            record["sha256"] == digest == sha256(restored) == sha256(target),
            f"{key} {asset} 的归档、还原、复制或实际加载字节及路径不符")
    return {"package": key, "asset": asset, "archive": str(archive), "restored": str(restored),
            "output": str(target), "loaded": record}
