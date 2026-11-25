"""还原、构建并核对固定模板的原版 Web.Host。"""

from base64 import b64encode
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import xml.etree.ElementTree as ET

from r1_restore_inventory import NUGET_SOURCE
from verify import ROOT, R0Run, VerificationError, make_run_directory, read_json, require, sha256


BASE_COMMIT = "105b1263160d049c97a975ee088b79982f1c547d"
BASE_TREE = "eae117e6926381b1558d6d25e113869e11804968"
TEMPLATE, FRAMEWORK = "module-zero-core-template", "aspnetboilerplate"
INPUTS = {
    TEMPLATE: ("2e9536872673a7ff1986a19e798c51684d16afe5",
               "b6a9e7386e3073e820eed83fe418d6c6096468bc"),
    FRAMEWORK: ("457be917b46c4fb6237831baac5abb848ffe1c4b",
                "fb0abb6be5cb69b0e5ff395f4b010cf28511f9c8"),
}
SDK, TFM, RID, ABP_VERSION = "10.0.404", "net9.0", "osx-arm64", "10.2.0"
DEPS_TARGET = ".NETCoreApp,Version=v9.0"
PREFIX = "AbpCompanyName.AbpProjectName."
PROJECTS = {
    "Web.Host": ("Web.Core",),
    "Web.Core": ("Application", "EntityFrameworkCore"),
    "Application": ("Core",),
    "EntityFrameworkCore": ("Core",),
    "Core": (),
}
DIRECT_ABP = {
    "Web.Host": {"Abp.Castle.Log4Net"},
    "Web.Core": {"Abp.AspNetCore", "Abp.ZeroCore", "Abp.AspNetCore.SignalR"},
    "Core": {"Abp.AutoMapper", "Abp.ZeroCore.EntityFrameworkCore"},
}
STAGES = ("preflight", "materialize", "sdk", "restore", "assets", "build", "output", "package_gaps")
MACHINE_BASELINE = "r3-web-host-baseline.json"
PROVIDER = "Microsoft.EntityFrameworkCore.SqlServer"
NOT_RUN = ["宿主启动与登录", "数据库连接、种子、迁移与业务操作", "Angular 构建",
           "维护包打包与消费", "其他模板入口、目标和平台", "CI 与部署"]
NUGET_CONFIG = f"""<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="nuget.org" value="{NUGET_SOURCE}" />
  </packageSources>
  <fallbackPackageFolders>
    <clear />
  </fallbackPackageFolders>
</configuration>
"""


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def project_path(name):
    return Path("src") / (PREFIX + name) / (PREFIX + name + ".csproj")


def is_abp(name):
    return name.casefold() == "abp" or name.casefold().startswith("abp.")


def is_maintained(name):
    return name.casefold() == "du.abp" or name.casefold().startswith("du.abp.")


def references(xml, tag):
    return [(item.attrib["Include"], item) for item in xml.iter(tag)]


def inside(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root), f"证据路径越界：{path}")
    return path


def artifact(path, root):
    return {"path": path.relative_to(root).as_posix(), "sha256": sha256(path)}


def package_hashes(cache, key, relative, expected_source=NUGET_SOURCE):
    name, version = key.split("/")
    directory = inside(cache, relative)
    require(directory.is_dir(), f"{key} 缺少缓存目录：{directory}")
    metadata = read_json(directory / ".nupkg.metadata")
    require(metadata.get("source") == expected_source,
            f"{key} 缓存来源与 {expected_source} 不符：{metadata.get('source')}")
    content = metadata.get("contentHash")
    require(bool(content), f"{key} 缺少 NuGet 内容 SHA-512")
    archive = directory / f"{name.lower()}.{version.lower()}.nupkg"
    digest = hashlib.sha512()
    with archive.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    archive_sha512 = b64encode(digest.digest()).decode("ascii")
    require(archive.with_suffix(".nupkg.sha512").read_text().strip() == archive_sha512,
            f"{key} 归档与 .nupkg.sha512 记录不符")
    return {"source": metadata["source"], "contentSha512": content, "archiveSha512": archive_sha512,
            "archive": artifact(archive, cache), "cachePath": relative}


def expected_projects(name, topology=PROJECTS):
    projects = set()
    pending = list(topology[name])
    while pending:
        referenced = pending.pop()
        if referenced not in projects:
            projects.add(referenced)
            pending.extend(topology[referenced])
    return {project_path(name).as_posix() for name in projects}


def download_records(framework, cache, lookup, graph_ids):
    downloads = {}
    for declared in framework.get("downloadDependencies", []):
        name = declared["name"]
        match = re.fullmatch(r"\[([^,]+), \1\]", declared["version"])
        require(match is not None, f"{name} SDK 下载版本未固定：{declared['version']}")
        version = match[1]
        key = f"{name}/{version}"
        require(name.casefold() not in graph_ids and key.casefold() not in downloads,
                f"{key} SDK 下载与应用图混入或重复")
        hashes = lookup(key, f"{name.lower()}/{version.lower()}")
        downloads[key.casefold()] = {"id": name, "version": version, "declaredRange": declared["version"], **hashes}
    return downloads


def read_project(root, name, path, cache, config, lookup, *, topology=PROJECTS,
                 sources=(NUGET_SOURCE,), managed=is_abp, managed_versions=None, forbidden=is_maintained,
                 tfm=TFM, deps_target=DEPS_TARGET):
    relative = project_path(name)
    data = read_json(path)
    project = data["project"]
    restore = project["restore"]
    require(Path(restore["projectPath"]).resolve() == root / relative, "资产登记的项目路径不符")
    require(Path(restore["packagesPath"]).resolve() == cache
            and {Path(p).resolve() for p in data["packageFolders"]} == {cache}, "资产登记的缓存不符")
    require(set(restore["sources"]) == set(sources) and not restore.get("fallbackFolders")
            and [Path(p).resolve() for p in restore["configFilePaths"]] == [config],
            "资产登记的有效配置或包源不符")
    require(set(data["targets"]) == {tfm} and restore["originalTargetFrameworks"] == [tfm],
            f"预期唯一目标 {tfm}，实际 {list(data['targets'])}")
    require(not any(log.get("level") == "Error" or log.get("code") == "NU1605"
                    for log in data.get("logs", [])), f"还原资产含错误或包降级：{data.get('logs')}")
    graph = data["targets"][tfm]
    require(bool(graph), "目标无匹配的包或项目")
    require(graph.keys() == data["libraries"].keys(), "目标与库的集合不符")
    keys_by_id = {key.split("/")[0].casefold(): key for key in graph}
    require(len(keys_by_id) == len(graph), "同一 ID 匹配了多个包版本或项目")
    framework = project["frameworks"][tfm]
    raw_direct = framework.get("dependencies", {})
    direct = {name: info for name, info in raw_direct.items() if info["target"] == "Package"}
    if managed_versions is None:
        managed_versions = {package: ABP_VERSION for package in DIRECT_ABP.get(name, ())}
    require({package for package in direct if managed(package)} == managed_versions.keys(),
            f"直接框架与映射引用不符：{sorted(direct)}")
    xml = ET.parse(root / relative)
    declarations = {id_: {"version": item.get("Version"),
                          **{child.tag: child.text for child in item}}
                    for id_, item in references(xml, "PackageReference")}
    require(declarations.keys() == direct.keys(), f"源码和还原的直接包声明不符：{sorted(direct)}")
    require(not (missing := set(map(str.casefold, direct)) - keys_by_id.keys()),
            f"直接引用未解析：{sorted(missing)}")
    require(all(graph[keys_by_id[package.casefold()]]["type"] == "package" for package in direct),
            "直接包引用被解析为非 NuGet 项")
    for package, version in managed_versions.items():
        require(declarations[package]["version"] == version,
                f"{package} 源码声明并非固定版本 {version}")

    refs = restore["frameworks"][tfm]["projectReferences"]
    ref_paths = {Path(ref["projectPath"]).resolve().relative_to(root).as_posix() for ref in refs.values()}
    require(ref_paths == {project_path(ref).as_posix() for ref in topology[name]},
            f"直接项目引用不符：{sorted(ref_paths)}")
    root_ids = {name.casefold() for name in direct} | {Path(ref).stem.casefold() for ref in ref_paths}
    require(not (missing := root_ids - keys_by_id.keys()), f"找不到直接引用的目标节点：{sorted(missing)}")
    reachable = set()
    pending = [keys_by_id[key] for key in root_ids]
    while pending:
        key = pending.pop()
        if key not in reachable:
            reachable.add(key)
            for dependency in graph[key].get("dependencies", {}):
                require(dependency.casefold() in keys_by_id, f"{key} 未解析的依赖边：{dependency}")
                pending.append(keys_by_id[dependency.casefold()])
    require(reachable == graph.keys(), f"图包含入口不可达的目标：{sorted(graph.keys() - reachable)}")
    packages, projects = {}, {}
    for key, selected in graph.items():
        id_, version = key.split("/")
        library = data["libraries"][key]
        require(selected["type"] == library["type"], f"{key} 目标与库类型不符")
        require(not forbidden(id_), f"还原混入不允许的包：{key}")
        dependencies = selected.get("dependencies", {})
        if library["type"] == "project":
            source = inside(root, relative.parent / library["msbuildProject"])
            require(selected["framework"] == deps_target, f"{key} 项目目标不符：{selected['framework']}")
            projects[key] = {"project": source.relative_to(root).as_posix(), "dependencies": dependencies}
            continue
        require(library["type"] == "package", f"{key} 的库类型不可识别：{library['type']}")
        hashes = lookup(key, library["path"])
        require(hashes["contentSha512"] == library["sha512"], f"{key} 内容 SHA-512 与目标资产不符")
        assets = {section: value for section, value in selected.items() if section not in ("type", "dependencies")}
        archive_only = [p for p in library["files"] if p.startswith(("analyzers/", "tools/"))]
        packages[key] = {"id": id_, "version": version, "dependencies": dependencies, "assets": assets,
                         "direct": id_ in direct, "archiveAnalyzerAndToolPaths": archive_only, **hashes}
    require({item["project"] for item in projects.values()} == expected_projects(name, topology),
            f"传递项目闭包不符：{projects}")
    require(restore["projectName"] == relative.stem, f"还原的入口项目名不符：{restore['projectName']}")
    return {"targetFramework": tfm, "runtimeIdentifier": None, "projectReferences": sorted(ref_paths),
            "entryProject": f"{restore['projectName']}/{project['version']}",
            "projects": projects,
            "directPackages": {key: {**direct[key], "declaration": value,
                                     "resolvedVersion": packages[keys_by_id[key.casefold()]]["version"]}
                               for key, value in declarations.items()},
            "packages": packages, "frameworkReferences": framework.get("frameworkReferences", {}),
            "sdkDownloads": download_records(framework, cache, lookup, keys_by_id), "sdkUsedPacks": {},
            "diagnostics": data.get("logs", [])}


def read_assets(root, raw_assets, cache, config):
    checked = {}

    def lookup(key, path):
        if (key, path) not in checked:
            checked[key, path] = package_hashes(cache, key, path)
        return checked[key, path]

    results = {}
    for name in PROJECTS:
        try:
            results[project_path(name).as_posix()] = read_project(root, name, raw_assets[name], cache, config, lookup)
        except (OSError, ValueError, TypeError, KeyError, ET.ParseError, VerificationError) as error:
            raise VerificationError(f"{project_path(name)} {TFM}：{error}") from error
    return results


def selected_pack(item, kind, target, cache, pack_root):
    id_, version = item["NuGetPackageId"], item["NuGetPackageVersion"]
    path = Path(item["Path"]).resolve()
    key = f"{id_}/{version}"
    require(path.is_file() if kind == "apphost" else path.is_dir(), f"{key} SDK pack 路径无效：{path}")
    downloaded = target["sdkDownloads"].get(key.casefold())
    root = path.parents[len(Path(item["PathInPackage"]).parts) - 1] if kind == "apphost" else path
    representative = path if kind == "apphost" else path / "data/FrameworkList.xml"
    if root.is_relative_to(cache):
        require(downloaded is not None and root == cache / downloaded["cachePath"],
                f"{key} 已解析 SDK pack 与下载清单不符：{path}")
        origin = "nuget-download"
        source, content = downloaded["source"], downloaded["contentSha512"]
        missing = None
    else:
        expected = pack_root / id_ / version
        require(root == expected.resolve() and downloaded is None, f"{key} 未识别的 SDK pack 位置：{path}")
        origin = "preinstalled"
        source, content = None, None
        missing = "SDK 安装目录仅有已展开的 pack，未提供下载来源和 NuGet 包内容哈希"
    result = {"id": id_, "version": version, "kind": kind, "origin": origin, "source": source,
              "contentSha512": content, "location": str(path), "file": artifact(representative, root)}
    if missing:
        result["missingPackageEvidence"] = missing
    return result


def read_sdk_packs(data, target, cache, pack_root, is_host, *, tfm=TFM):
    props, items = data["Properties"], data["Items"]
    require(Path(props["NetCoreTargetingPackRoot"]).resolve() == pack_root, "SDK pack 根目录不符")
    targeting = items["ResolvedTargetingPack"]
    references = {item["Identity"] for item in items["FrameworkReference"]}
    require(references and references == {item["Identity"] for item in targeting},
            f"FrameworkReference 与已解析 targeting pack 集合不符：{references}")
    require(all(item["TargetFramework"] == tfm for item in targeting), "SDK targeting pack 目标不符")
    result = {item["Identity"]: selected_pack(item, "targeting", target, cache, pack_root)
              for item in targeting}
    apphosts = items.get("ResolvedAppHostPack", [])
    require(len(apphosts) == int(is_host), f"apphost pack 数量不符：{apphosts}")
    if apphosts:
        item = apphosts[0]
        path = Path(item["Path"]).resolve()
        require(item["RuntimeIdentifier"] == RID and path == Path(props["AppHostSourcePath"]).resolve(),
                "实际 AppHostSourcePath 或 RID 不符")
        if tfm == "net10.0" and not (item.get("NuGetPackageId") or item.get("NuGetPackageVersion")):
            package_dir = Path(item["PackageDirectory"]).resolve()
            package_id = f"Microsoft.NETCore.App.Host.{RID}"
            require(package_dir.parent == pack_root / package_id
                    and path == package_dir / item["PathInPackage"],
                    f"已安装的 apphost 路径与 SDK pack 目录不符：{path}")
            item = {**item, "NuGetPackageId": package_id, "NuGetPackageVersion": package_dir.name}
        result["apphost"] = selected_pack(item, "apphost", target, cache, pack_root)
    return result


def framework_owners(graph, deps_libraries=None):
    owners = {}
    for key, entry in graph.items():
        name, _ = key.split("/")
        assets = entry["assets"] if deps_libraries is None else entry
        require(not is_maintained(name), f"Host 运行目标混入维护包：{key}")
        for section in ("runtime", "runtimeTargets", "native"):
            for asset in assets.get(section, {}):
                dll = Path(asset).name
                if not (is_abp(name) or is_abp(Path(dll).stem)) or not dll.lower().endswith(".dll"):
                    continue
                require(section == "runtime", f"{dll} 出现未登记的 {section} 框架资产：{key} {asset}")
                if deps_libraries is not None:
                    require(deps_libraries[key]["type"] == "package",
                            f"{dll} 在 Host .deps.json 的来源不是 NuGet 包：{key} {asset}")
                owners.setdefault(dll.casefold(), []).append((key, asset))
    for dll, sources in owners.items():
        require(len(sources) == 1, f"{dll} 框架运行 DLL 来源冲突：{sources}")
    require(bool(owners), f"Host {TFM} 零个框架运行 DLL 匹配")
    return {dll: sources[0] for dll, sources in owners.items()}


RUNTIME_SECTIONS = {"runtime": "runtime", "native": "native", "resources": "resource",
                    "runtimeTargets": "runtimeTargets"}


def runtime_selection(items, target, cache):
    """从 SDK 冲突处理后的复制列表定位 NuGet 运行资产。"""
    selected, destinations = {}, {}
    for item in items["ReferenceCopyLocalPaths"]:
        require(all(item.get(field) for field in
                    ("NuGetPackageId", "NuGetPackageVersion", "PathInPackage", "AssetType", "DestinationSubPath")),
                f"SDK 复制项缺少 NuGet 运行来源：{item['Identity']}")
        package = f"{item['NuGetPackageId']}/{item['NuGetPackageVersion']}"
        asset = item["PathInPackage"]
        details = target["packages"].get(package)
        section = "runtimeTargets" if item.get("RuntimeIdentifier") else item["AssetType"]
        require(details and section in RUNTIME_SECTIONS
                and asset in details["assets"].get(RUNTIME_SECTIONS[section], {}),
                f"SDK 运行复制项无对应还原资产：{package} {section} {asset}")
        source = inside(cache, Path(details["cachePath"]) / asset)
        require(source.is_file() and source == Path(item["FullPath"]).resolve(),
                f"SDK 运行复制项来源与资产不符：{package} {asset}")
        destination = Path(item["DestinationSubPath"])
        require(not destination.is_absolute() and ".." not in destination.parts,
                f"SDK 运行输出路径无效：{destination}")
        output_path = destination.as_posix()
        require(output_path not in destinations,
                f"SDK 运行输出路径来源冲突：{output_path}，{destinations.get(output_path)} 与 {package} {asset}")
        destinations[output_path] = (package, asset)
        record = {"outputPath": output_path}
        if section == "runtimeTargets":
            record.update(rid=item["RuntimeIdentifier"], assetType=item["AssetType"])
        if section == "resources":
            record["locale"] = item["Culture"]
        selected.setdefault(package, {}).setdefault(section, {})[asset] = record
    return selected


def check_runtime_declarations(output, dlls, graph, libraries, target):
    """核对模板根项目、实际解析边及 SDK 应复制的运行文件。"""
    packages, projects = target["packages"], target["projects"]
    entry = target["entryProject"]
    nodes = packages.keys() | projects.keys() | {entry}
    require(nodes <= graph.keys(), f"Host .deps.json 缺少还原图的包或项目：{sorted(nodes - graph.keys())}")

    sdk_references = graph.keys() - nodes
    for key in sorted(sdk_references):
        reference = graph[key]
        require(libraries[key]["type"] == "referenceassembly" and reference.get("compileOnly")
                and reference.get("compile") and not reference.get("dependencies")
                and not any(reference.get(section) for section in RUNTIME_SECTIONS),
                f"Host .deps.json 有无法归属的库或运行声明：{key}")
        for asset in reference["compile"]:
            require((output / "refs" / Path(asset).name).is_file(),
                    f"SDK 编译参考 {key} 缺少 refs/{Path(asset).name}")

    roots = list(target["directPackages"]) + [Path(path).stem for path in target["projectReferences"]]
    by_id = {key.split("/")[0].casefold(): key for key in nodes}
    project_and_package_edges = {key: item["dependencies"] for key, item in (projects | packages).items()}
    project_and_package_edges[entry] = roots
    package_selection = target["sdkRuntimeSelection"]
    expected_outputs = set()
    for key, edges in project_and_package_edges.items():
        entry_graph = graph[key]
        resolved_edges = {by_id[dependency.casefold()] for dependency in edges}
        if key == entry:
            resolved_edges |= sdk_references
        actual_edges = {f"{dependency}/{version}" for dependency, version in entry_graph.get("dependencies", {}).items()}
        require(actual_edges == resolved_edges,
                f"Host .deps.json {key} 依赖边不符："
                f"缺少 {sorted(resolved_edges - actual_edges)}，多出 {sorted(actual_edges - resolved_edges)}")

        if key in packages:
            package, library = packages[key], libraries[key]
            require(library.get("type") == "package" and library.get("path") == package["cachePath"]
                    and library.get("sha512") == f"sha512-{package['contentSha512']}",
                    f"Host .deps.json 包来源与还原证据不符：{key}")
            expected = package_selection.get(key, {})
        else:
            require(libraries[key]["type"] == "project", f"Host .deps.json 项目库类型不符：{key}")
            dll = key.split("/")[0] + ".dll"
            expected = {"runtime": {dll: {"outputPath": dll}}}
        for section in RUNTIME_SECTIONS:
            assets = expected.get(section, {})
            declared = entry_graph.get(section, {})
            require(assets.keys() == declared.keys(),
                    f"Host .deps.json {key} 的 {section} 声明不符："
                    f"缺少 {sorted(assets.keys() - declared.keys())}，多出 {sorted(declared.keys() - assets.keys())}")
            for asset, expected_info in assets.items():
                path = expected_info["outputPath"]
                require(all(declared[asset].get(field) == value for field, value in expected_info.items()
                            if field != "outputPath"), f"Host .deps.json {key} 资产 {asset} 的 RID 或区域属性不符")
                require((output / path).is_file(),
                        f"缺少应复制的 {Path(path).name}：{output / path}，来源 {key} {asset}")
                require(path not in expected_outputs, f"Host 运行路径存在多个来源：{path}，包括 {key} {asset}")
                expected_outputs.add(path)

    actual_outputs = {file.relative_to(output).as_posix() for file in dlls}
    actual_outputs |= {file.relative_to(output).as_posix() for file in (output / "runtimes").rglob("*")
                       if file.is_file()}
    actual_outputs |= {file.relative_to(output).as_posix() for file in output.iterdir()
                       if file.is_file() and file.suffix.casefold() in (".dylib", ".so")}
    missing_owners = {path for path in actual_outputs - expected_outputs if Path(path).parts[0] != "refs"}
    require(not missing_owners, f"Host 实际输出有未登记的运行文件：{sorted(missing_owners)}")
    return sorted(expected_outputs)


def check_host(output, cache, target):
    from zipfile import ZipFile

    host = output / (PREFIX + "Web.Host.dll")
    deps_file = host.with_suffix(".deps.json")
    require(host.is_file() and host.stat().st_size > 0, f"缺少或空的 Host DLL：{host}")
    require(deps_file.is_file(), f"缺少 Host .deps.json：{deps_file}")
    try:
        deps = read_json(deps_file)
        name = deps["runtimeTarget"]["name"]
        require(name == DEPS_TARGET and set(deps["targets"]) == {DEPS_TARGET},
                f"{deps_file.name} 运行目标预期 {DEPS_TARGET}，实际 {name}")
        graph, libraries = deps["targets"][name], deps["libraries"]
        require(isinstance(graph, dict) and isinstance(libraries, dict),
                f"{deps_file.name} 的运行目标或库表格式无效")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise VerificationError(f"无法读取 Host 依赖证据 {deps_file}：{error}") from error
    require(graph.keys() == libraries.keys(),
            f"{deps_file.name} 运行目标与库表不符："
            f"缺少库表 {sorted(graph.keys() - libraries.keys())}，缺少运行目标 {sorted(libraries.keys() - graph.keys())}")
    packages = target["packages"]
    expected = framework_owners(packages)
    in_deps = framework_owners(graph, libraries)
    require(in_deps == expected,
            f"{deps_file.name} 框架运行 DLL 与还原图归属不符："
            f"还原 {sorted(expected.items() - in_deps.items())}；deps {sorted(in_deps.items() - expected.items())}")

    dlls = sorted(file for file in output.rglob("*") if file.is_file() and file.suffix.casefold() == ".dll")
    actual = {}
    for file in dlls:
        relative = file.relative_to(output)
        if relative.parts[0] == "refs":
            continue
        if is_abp(file.stem) or file.name.casefold() in expected:
            actual.setdefault(file.name.casefold(), []).append(file)
    runtime = []
    for dll, (key, asset) in sorted(expected.items()):
        package = packages[key]
        file = output / Path(asset).name
        require(file.is_file(), f"缺少应复制的 {file.name}：{file}，来源 {key} {asset}")
        require(actual[dll] == [file], f"{file.name} 的实际输出路径重复：{actual[dll]}")
        require(is_abp(package["id"]) and Path(asset).stem == package["id"],
                f"{file.name} 的框架程序集与包 ID 不符：{key} {asset}")
        library = libraries[key]
        require(library["sha512"] == f"sha512-{package['contentSha512']}"
                and library["path"] == package["cachePath"], f"{file.name} 的 deps 来源与还原缓存不符：{key}")
        extracted = inside(cache, Path(package["cachePath"]) / asset)
        archive = inside(cache, package["archive"]["path"])
        with ZipFile(archive) as nupkg:
            package_digest = hashlib.sha256(nupkg.read(asset)).hexdigest()
        require(sha256(extracted) == package_digest == sha256(file),
                f"{file.name} SHA-256 不符：{file}，来源 {key} {asset}")
        runtime.append({"path": file.name, "packageId": package["id"], "version": package["version"],
                        "packageAsset": asset, "sha256": package_digest})
    require(actual.keys() == expected.keys(),
            f"实际输出含归属不明的框架运行 DLL：{sorted(actual.keys() - expected.keys())}")

    compile_only = {key: {"type": libraries[key]["type"], "compile": entry.get("compile", {})}
                    for key, entry in graph.items() if entry.get("compileOnly")}
    for key in compile_only:
        require(not any(graph[key].get(kind) for kind in RUNTIME_SECTIONS),
                f"{deps_file.name} 编译专用项包含运行资产：{key}")
    runtime_outputs = check_runtime_declarations(output, dlls, graph, libraries, target)
    providers = [key for key, item in packages.items() if item["id"] == PROVIDER]
    require(len(providers) == 1, f"Host 还原图须包含唯一 {PROVIDER}，实际 {providers}")
    provider = providers[0]
    sql_assets = target["sdkRuntimeSelection"].get(provider, {}).get("runtime", {})
    sql_paths = [asset for asset in sql_assets if Path(asset).name == PROVIDER + ".dll"]
    require(len(sql_paths) == 1, f"{provider} 缺少唯一的 SDK 运行复制项 {PROVIDER}.dll：{sql_paths}")
    sql_path = sql_paths[0]
    sql_source = inside(cache, Path(packages[provider]["cachePath"]) / sql_path)
    sql_output = output / sql_assets[sql_path]["outputPath"]
    require(sha256(sql_source) == sha256(sql_output), f"{provider} 的运行 DLL SHA-256 不符：{sql_output}")
    use = {}
    for key, item in packages.items():
        entry = graph.get(key, {})
        use[key] = {
            "compile": item["assets"].get("compile", {}),
            "runtime": entry.get("runtime", {}),
            "runtimeTargets": entry.get("runtimeTargets", {}),
            "native": entry.get("native", {}),
        }
    return {"runtimeTarget": name, "host": artifact(host, output), "deps": artifact(deps_file, output),
            "frameworkRuntimeDlls": runtime, "depsCompileOnly": compile_only, "packageUsage": use,
            "verifiedRuntimeOutputPaths": runtime_outputs,
            "sqlServerProvider": {"package": provider, "packageAsset": sql_path,
                                  **artifact(sql_output, output)},
            "outputReferenceDlls": [p.relative_to(output).as_posix() for p in dlls
                                    if p.relative_to(output).parts[0] == "refs"],
            "outputRuntimeDlls": [p.relative_to(output).as_posix() for p in dlls
                                  if p.relative_to(output).parts[0] != "refs"],
            "frameworkReferences": target["frameworkReferences"],
            "rootRuntimeIdentifier": None,
            "ridAssetNote": "可移植 Host 保留 .deps.json 的 RID 资产候选。运行时的 RID 选择与程序集加载尚未验证。",
            "assetUsageNote": "refs 下为编译参考。私有传播规则见直接引用；私有项仍可能为声明项目贡献运行资产。"
                              "包内工具与分析器路径仅表明包内容；实际选中资产和 Host 条目另列。"}


KEY_DEPENDENCIES = (
    "Microsoft.EntityFrameworkCore", "Microsoft.EntityFrameworkCore.Abstractions",
    "Microsoft.EntityFrameworkCore.Relational", PROVIDER, "Microsoft.EntityFrameworkCore.Design",
    "Microsoft.EntityFrameworkCore.Tools", "Microsoft.EntityFrameworkCore.Sqlite",
    "Microsoft.EntityFrameworkCore.Sqlite.Core", "Microsoft.Data.SqlClient", "Microsoft.Data.SqlClient.SNI.runtime",
    "Microsoft.Data.Sqlite.Core", "Microsoft.AspNetCore.Mvc.NewtonsoftJson",
    "Microsoft.AspNetCore.Mvc.Razor.RuntimeCompilation", "Microsoft.AspNetCore.Authentication.JwtBearer",
    "Swashbuckle.AspNetCore", "AutoMapper", "AutoMapper.Collection", "log4net", "Newtonsoft.Json", "NUglify",
    "JetBrains.Annotations", "System.Linq.Dynamic.Core", "TimeZoneConverter", "Castle.Windsor.MsDependencyInjection",
)


def framework_projects(run):
    pending = sorted(set().union(*DIRECT_ABP.values()), reverse=True)
    result = {}
    commit, _ = INPUTS[FRAMEWORK]
    common = run.git(run.repo / FRAMEWORK, "framework-common.props", "show", f"{commit}:common.props")
    common_props = ET.fromstring(common)
    while pending:
        id_ = pending.pop()
        if id_ in result:
            continue
        relative = f"src/{id_}/{id_}.csproj"
        data = run.git(run.repo / FRAMEWORK, f"framework-{id_}.csproj", "show", f"{commit}:{relative}")
        xml = ET.fromstring(data.lstrip("\ufeff"))
        refs = sorted(Path(path.replace("\\", "/")).stem for path, _ in references(xml, "ProjectReference"))
        target = xml.findtext(".//TargetFrameworks") or xml.findtext(".//TargetFramework")
        require(target and TFM in target.split(";"), f"{id_} 维护源码缺少 {TFM} 目标")
        require(xml.findtext(".//PackageId") == xml.findtext(".//AssemblyName") == id_,
                f"{id_} 维护源码普通包或程序集身份变化")
        packages = []
        for source, project in ((relative, xml), ("common.props", common_props)):
            for group in project.findall("ItemGroup"):
                for name, item in references(group, "PackageReference"):
                    packages.append({"id": name, "version": item.get("Version"),
                                     "condition": group.get("Condition"), "source": source,
                                     **{child.tag: child.text for child in item}})
        result[id_] = {"project": relative, "targets": target.split(";"), "projectReferences": refs,
                       "packageId": id_, "assemblyName": id_,
                       "rootNamespace": xml.findtext(".//RootNamespace") or id_, "packageReferences": packages}
        pending.extend(refs)
    require(len(result) == 11, f"维护框架源码闭包预期 11 个项目，实际 {sorted(result)}")
    return result


def package_gaps(assets, host, source, r2):
    target = assets[project_path("Web.Host").as_posix()]
    original = {item["id"]: item for item in target["packages"].values() if is_abp(item["id"])}
    mismatches = {}
    missing = sorted(source.keys() - original.keys())
    unexpected = sorted(original.keys() - source.keys())
    if missing or unexpected:
        mismatches["packageSet"] = {"missing": missing, "unexpected": unexpected}
    comparison = {}
    for id_, item in original.items():
        deps = {name: version for name, version in item["dependencies"].items() if is_abp(name)}
        outputs = [dll for dll in host["frameworkRuntimeDlls"] if dll["packageId"] == id_]
        direct_from = [project for project, graph in assets.items() if id_ in graph["directPackages"]]
        comparison[id_] = {"version": item["version"], "internalDependencies": deps, "directFrom": direct_from,
                           "assets": item["assets"], "runtimeOutputs": outputs,
                           "packageContentSha512": item["contentSha512"], "nupkgSha256": item["archive"]["sha256"]}
        if (item["version"] != ABP_VERSION or deps != dict.fromkeys(source.get(id_, {}).get("projectReferences", []),
                                                                  ABP_VERSION)
                or [dll["packageAsset"] for dll in outputs] != [f"lib/{TFM}/{id_}.dll"]):
            mismatches[id_] = {"actual": comparison[id_], "baselineVersion": ABP_VERSION,
                               "sourceProjectReferences": source.get(id_, {}).get("projectReferences"),
                               "baselineRuntimeAsset": f"lib/{TFM}/{id_}.dll"}
    project_drift = {}
    for project, graph in assets.items():
        differences = []
        for item in graph["packages"].values():
            id_ = item["id"]
            if not is_abp(id_):
                continue
            deps = {name: version for name, version in item["dependencies"].items() if is_abp(name)}
            source_refs = source.get(id_, {}).get("projectReferences")
            if (item["version"] != ABP_VERSION or source_refs is None
                    or deps != dict.fromkeys(source_refs, ABP_VERSION)):
                differences.append({"id": id_, "actualVersion": item["version"], "baselineVersion": ABP_VERSION,
                                    "directDeclaration": graph["directPackages"].get(id_),
                                    "actualInternalDependencies": deps, "sourceProjectReferences": source_refs})
        if differences:
            project_drift[project] = differences
    if project_drift:
        mismatches["projectPackages"] = project_drift
    require(r2["frameworkTree"] == INPUTS[FRAMEWORK][1], "R2 五包证据与固定框架树不同")
    r2_mappings = {entry["assemblyName"]: id_ for id_, entry in r2["packages"].items()}
    require(len(r2_mappings) == 5 and r2_mappings.keys() <= source.keys(), "R2 的五包映射与框架源码不符")
    for id_, mapped in r2_mappings.items():
        verified = r2["packages"][mapped]
        project = source[id_]
        require(mapped == "Du." + id_ and verified["rootNamespace"] == project["rootNamespace"]
                and verified["targets"].keys() == set(project["targets"])
                and all(set(target["internalDependencies"]) == {"Du." + p for p in project["projectReferences"]}
                        for target in verified["targets"].values()), f"{mapped} R2 实物登记与固定源码映射不符")
    gaps = [{"source": id_, "candidatePackageId": f"Du.{id_}", "assemblyName": source[id_]["assemblyName"],
             "targets": source[id_]["targets"], "projectReferences": source[id_]["projectReferences"]}
            for id_ in sorted(source.keys() - r2_mappings.keys())]
    require(len(gaps) == 6, f"候选缺口预期 6 个，实际 {gaps}")
    critical = {}
    for name in KEY_DEPENDENCIES:
        key = name.casefold()
        original_picks = {project: {"version": package["version"], "dependencies": package["dependencies"],
                                    "assets": package["assets"], "declared": graph["directPackages"].get(name)}
                          for project, graph in assets.items() for package in graph["packages"].values()
                          if package["id"].casefold() == key}
        maintained = {id_: [item for item in project["packageReferences"] if item["id"].casefold() == key]
                      for id_, project in source.items()
                      if any(item["id"].casefold() == key for item in project["packageReferences"])}
        critical[name] = {"originalProjects": original_picks, "maintenanceSource": maintained,
                          "r2Net9Consumer": r2["keyNet9ConsumerPackages"].get(name)}
    return {"originalHostFramework": comparison, "maintenanceSource": source, "r2VerifiedReference": r2,
            "candidateGaps": gaps, "frameworkDifferencesRequiringAttribution": mismatches,
            "criticalDependencyComparison": critical,
            "followUp": [
                {"components": ["Abp.AspNetCore.SignalR", "Abp.Castle.Log4Net"],
                 "gate": "组件各自基于核心 Abp，核对 net9.0 nuspec、框架与第三方依赖、程序集及定向消费。"},
                {"components": ["Abp.Zero.Common", "Abp.ZeroCore", "Abp.ZeroCore.EntityFrameworkCore"],
                 "gate": "按此顺序消费上游候选，末项额外依赖 Abp.EntityFrameworkCore，复验 Module Zero net9.0 调用与 SQLite 回归。"},
                {"components": ["Abp.AutoMapper"],
                 "gate": "确认 MIT v14 与 Collection v11 的来源和许可证、单一引擎与依赖范围、安全修复和四类映射行为。"},
                {"gate": "同批候选从独立包源与空缓存核对程序集唯一、完整依赖闭包与来源，再做同一 Host 构建对照。"},
                {"gate": "在隔离 SQL Server 核对启动、登录、租户和授权。涉及 schema 或数据变更时先核对备份恢复或逆向迁移。"},
            ]}


def comparison_manifest(assets, host):
    projects = {}
    for project, target in assets.items():
        packages = [{"id": item["id"], "version": item["version"], "dependencies": item["dependencies"]}
                    for _, item in sorted(target["packages"].items(), key=lambda entry: entry[0].casefold())]
        downloads = [{key: item[key] for key in ("id", "version", "declaredRange", "source", "contentSha512")}
                     for _, item in sorted(target["sdkDownloads"].items())]
        packs = [{key: value for key, value in item.items() if key != "location"}
                 for _, item in sorted(target["sdkUsedPacks"].items())]
        versions = {item["id"].casefold(): item["version"] for item in packages}
        projects[f"aspnet-core/{project}"] = {
            target["targetFramework"]: {
                "projectReferences": [f"aspnet-core/{path}" for path in target["projectReferences"]],
                "directPackages": {id_: {"declaredVersion": declaration["declaration"]["version"],
                                         "declaredRange": declaration["version"],
                                         "resolvedVersion": versions[id_.casefold()]}
                                   for id_, declaration in target["directPackages"].items()},
                "packages": packages, "sdkDownloads": downloads, "sdkUsedPacks": packs,
            }
        }
    return {"schemaVersion": 2, "templateCommit": INPUTS[TEMPLATE][0], "inputsSDK": SDK,
            "projects": projects, "frameworkRuntimeDlls": host["frameworkRuntimeDlls"]}


class R3Run(R0Run):
    def __init__(self, repo, evidence):
        self.repo = repo
        self.evidence = evidence
        self.report_path = evidence / "report.json"
        self.root = evidence / "source/aspnet-core"
        self.cache = evidence / "packages"
        self.config = evidence / "NuGet.Config"
        self.entry = project_path("Web.Host")
        self.output = self.root / self.entry.parent / f"bin/Release/{TFM}"
        self.dotnet = shutil.which("dotnet")
        self.env = {
            "DOTNET_CLI_HOME": str(evidence / "dotnet-home"), "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "DOTNET_NOLOGO": "1", "DOTNET_CLI_UI_LANGUAGE": "en",
            "NUGET_PACKAGES": str(self.cache), "NUGET_HTTP_CACHE_PATH": str(evidence / "http-cache"),
            "NUGET_PLUGINS_CACHE_PATH": str(evidence / "plugins-cache"), "MSBUILDDISABLENODEREUSE": "1",
        }
        self.report = {
            "profile": "r3-web-host", "status": "running", "exitCode": None,
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "command": [sys.executable, *sys.argv], "cwd": str(Path.cwd()),
            "inputs": {"repository": str(repo), "targetFramework": TFM, "configuration": "Release",
                       "entryProject": f"aspnet-core/{self.entry}", "declaredProvider": PROVIDER,
                       "planningCommit": BASE_COMMIT, "planningTree": BASE_TREE},
            "environment": {"platform": platform.system(), "architecture": platform.machine(),
                            "macOS": platform.mac_ver()[0], "python": platform.python_version()},
            "coverageNotRun": NOT_RUN,
            "stages": {stage: {"status": "not_run", "exitCode": None, "commands": [], "evidence": []}
                       for stage in STAGES},
        }
        self.save()

    def git(self, repo, log, *args):
        _, path = self.command(["git", "-C", repo, *args], self.repo, log,
                               extra_env={"GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1"})
        return path.read_text(encoding="utf-8").rstrip()

    def git_tree(self, repo, label, commit, tree):
        try:
            kind = self.git(repo, f"{label}-type.log", "cat-file", "-t", commit)
            actual = self.git(repo, f"{label}-tree.log", "rev-parse", f"{commit}^{{tree}}")
        except VerificationError as error:
            raise VerificationError(f"{label} 缺少可读的固定 Git 对象 {commit}，预期树 {tree}：{error}") from error
        require((kind, actual) == ("commit", tree), f"{label} {commit} 的 Git 类型或树不符：{kind} {actual}")

    def preflight(self):
        self.git_tree(self.repo, "main-planning", BASE_COMMIT, BASE_TREE)
        actual_main = self.git(self.repo, "main-current-head.log", "rev-parse", "HEAD")
        self.report["inputs"]["executionCommit"] = actual_main
        self.report["inputs"]["executionTree"] = self.git(
            self.repo, "main-current-tree.log", "rev-parse", "HEAD^{tree}")
        inputs = self.report["inputs"]["submodules"] = {}
        for module, (commit, tree) in INPUTS.items():
            check = self.git(self.repo, f"{module}-fixed-gitlink.log", "ls-tree", BASE_COMMIT, "--", module)
            require(check.split() == ["160000", "commit", commit, module], f"固定主仓 {module} gitlink 不符：{check}")
            current = self.git(self.repo, f"{module}-current-gitlink.log", "ls-tree", actual_main, "--", module)
            require(current.split()[:2] == ["160000", "commit"], f"执行主仓缺少 {module} gitlink")
            repository = self.git(self.repo, f"{module}-registration.log", "config", "--blob",
                                  f"{BASE_COMMIT}:.gitmodules", "--get", f"submodule.{module}.url")
            require(repository == f"https://github.com/dusdong/{module}.git",
                    f"{module} 固定主仓来源登记不符：{repository}")
            child = self.repo / module
            require(child.is_dir(), f"{module} 缺少有固定 Git 对象 {commit} 的子仓目录：{child}")
            top = self.git(child, f"{module}-root.log", "rev-parse", "--show-toplevel")
            require(Path(top).resolve() == child, f"{module} 缺少子仓的固定 Git 对象 {commit}")
            self.git_tree(child, module, commit, tree)
            inputs[module] = {"commit": commit, "tree": tree, "gitlinkAtExecutionCommit": current.split()[2],
                              "repository": repository, "checkout": self.git(
                                  child, f"{module}-checkout.log", "rev-parse", "HEAD")}
        require((platform.system(), platform.machine()) == ("Darwin", "arm64"), "受测环境为 macOS ARM64")
        require(self.dotnet is not None, "找不到 dotnet")
        self.dotnet = Path(self.dotnet).resolve()

    def materialize(self):
        self.root.parent.mkdir()
        archive = self.evidence_file("template-source.tar")
        self.git(self.repo / TEMPLATE, "template-archive.log", "archive", "--format=tar",
                 f"--output={archive}", INPUTS[TEMPLATE][0], "aspnet-core")
        self.command(["tar", "-xf", archive, "-C", self.root.parent], self.evidence, "template-extract.log")
        template_config = self.root / "NuGet.Config"
        source_records = {
            "archive": artifact(archive, self.evidence),
            "projects": [artifact(self.root / project_path(name), self.root.parent) for name in PROJECTS],
            "originalNuGetConfig": artifact(template_config, self.root.parent),
        }
        code = self.root / project_path("EntityFrameworkCore").parent / (
            "EntityFrameworkCore/AbpProjectNameDbContextConfigurer.cs")
        require("UseSqlServer(" in code.read_text(), f"找不到 SQL Server Provider 源码声明：{code}")
        source_records["providerDeclaration"] = artifact(code, self.root.parent)
        write_json(self.evidence_file("source-inventory.json"), source_records)
        write_json(self.evidence_file("global.json"), {"sdk": {"version": SDK, "rollForward": "disable"}})
        for path in (self.cache, self.evidence / "http-cache", self.evidence / "plugins-cache"):
            path.mkdir()
            require(not any(path.iterdir()), f"本轮缓存非空：{path}")
        self.config.write_text(NUGET_CONFIG, encoding="utf-8")
        self.evidence_file("NuGet.Config")
        original = {element.attrib["key"]: element.attrib["value"]
                    for element in ET.parse(template_config).findall("./packageSources/add")}
        require(original == {"nuget.org": NUGET_SOURCE,
                             "ABP Nightly Source": "https://www.myget.org/F/abp-nightly/api/v3/index.json"},
                f"固定模板原配置的源变化：{original}")
        self.report["inputs"]["nuget"] = {
            "original": source_records["originalNuGetConfig"], "originalSources": original,
            "effective": artifact(self.config, self.evidence), "effectiveSources": [NUGET_SOURCE],
            "removedSources": {"ABP Nightly Source": original["ABP Nightly Source"]},
            "globalPackages": str(self.cache), "httpCache": self.env["NUGET_HTTP_CACHE_PATH"],
            "cachesInitiallyEmpty": True,
        }

    def run_dotnet(self, args, log):
        return self.command([self.dotnet, *args], self.root, log, extra_env=self.env)[1]

    def toolchain(self):
        version = self.run_dotnet(["--version"], "dotnet-version.log").read_text().strip()
        require(version == SDK, f"SDK 预期 {SDK}，实际 {version}")
        info = self.run_dotnet(["--info"], "dotnet-info.log").read_text()
        sdk_path = re.search(r"^ Base Path:\s+(.+)$", info, re.MULTILINE)
        require(sdk_path is not None and re.search(r"^\s*Architecture:\s*arm64\s*$", info, re.MULTILINE)
                and re.search(rf"^\s*RID:\s*{RID}\s*$", info, re.MULTILINE),
                f"SDK 宿主应使用 {RID}，详见 dotnet-info.log")
        base = Path(sdk_path[1].strip()).resolve()
        require(base.name == SDK, f"SDK 安装路径不符：{base}")
        self.pack_root = (base.parent.parent / "packs").resolve()
        build = self.read_command(["sw_vers", "-buildVersion"], self.root, "sw-vers-build.log")
        self.report["environment"].update(sdk=version, dotnet=str(self.dotnet), sdkPath=str(base), rid=RID,
                                          macOSBuild=build, dotnetSha256=sha256(self.dotnet))

    def restore(self):
        log = self.run_dotnet(["restore", self.entry, "--configfile", self.config, "--no-http-cache",
                               "--force", "-p:Configuration=Release", "--verbosity", "normal"], "restore.log")
        self.record_diagnostics(log)
        output = log.read_text()
        require(str(self.config) in output and NUGET_SOURCE in output and "Installed " in output,
                "还原日志缺少独立配置、包源或实际安装记录")

    def record_diagnostics(self, log):
        output = log.read_text(encoding="utf-8")
        self.stage["diagnostics"] = {
            "warnings": [int(count) for count in re.findall(r"^\s*(\d+) Warning\(s\)", output, re.MULTILINE)],
            "errors": [int(count) for count in re.findall(r"^\s*(\d+) Error\(s\)", output, re.MULTILINE)],
            "codes": sorted(set(re.findall(r": (?:warning|error) (\w+):", output))),
        }

    def inventory(self):
        saved = self.evidence / "raw-assets"
        saved.mkdir()
        raw_assets = {}
        actual = {}
        for name in PROJECTS:
            actual[name] = self.root / project_path(name).parent / "obj/project.assets.json"
            raw_assets[name] = saved / f"{name}.project.assets.json"
            if actual[name].is_file():
                shutil.copyfile(actual[name], self.evidence_file(str(raw_assets[name].relative_to(self.evidence))))
        self.report["rawAssets"] = {name: artifact(path, self.evidence) for name, path in raw_assets.items()
                                    if path.is_file()}
        self.assets = read_assets(self.root, raw_assets, self.cache, self.config)
        ef_project = self.assets[project_path("EntityFrameworkCore").as_posix()]
        provider = ef_project["directPackages"].get(PROVIDER)
        require(provider and any(item["id"] == PROVIDER and item["assets"].get("runtime")
                                 for item in self.assets[self.entry.as_posix()]["packages"].values()),
                f"{TFM} Host 缺少由 EntityFrameworkCore 项目引用的 {PROVIDER} 或其运行资产")
        self.asset_paths = actual
        write_json(self.evidence_file("assets-inventory.json"), self.assets)

    def build(self):
        log = self.run_dotnet(["build", self.entry, "--configuration", "Release", "--no-restore",
                               "--disable-build-servers", "-p:UseSharedCompilation=false",
                               "--verbosity", "minimal"], "build.log")
        self.record_diagnostics(log)
        for name, path in self.asset_paths.items():
            require(sha256(path) == self.report["rawAssets"][name]["sha256"],
                    f"构建改写了还原图：{path}")

    def inspect_output(self):
        for name in PROJECTS:
            project = project_path(name)
            log = self.run_dotnet(["msbuild", project, "-nologo", "-p:Configuration=Release",
                                   "-target:ResolveTargetingPackAssets;_GetAppHostPaths",
                                   "-getItem:FrameworkReference,ResolvedTargetingPack,ResolvedAppHostPack,ResolvedAnalyzers",
                                   "-getProperty:AppHostSourcePath,NetCoreTargetingPackRoot"],
                                  f"{name}-sdk-packs.log")
            target = self.assets[project.as_posix()]
            try:
                resolved = read_json(log)
                target["sdkUsedPacks"] = read_sdk_packs(resolved, target, self.cache, self.pack_root, name == "Web.Host")
                analyzers = [Path(item["FullPath"]).resolve() for item in resolved["Items"]["ResolvedAnalyzers"]]
                target["selectedPackageAnalyzers"] = sorted(
                    path.relative_to(self.cache).as_posix() for path in analyzers)
            except (KeyError, ValueError, VerificationError, OSError) as error:
                raise VerificationError(f"{project} {TFM} SDK pack 核对失败：{error}") from error
        target = self.assets[self.entry.as_posix()]
        runtime_log = self.run_dotnet(
            ["msbuild", self.entry, "-nologo", "-p:Configuration=Release",
             "-target:ResolveLockFileCopyLocalFiles;_HandlePackageFileConflicts",
             "-getItem:ReferenceCopyLocalPaths,_ConflictPackageFiles,PackageConflictPlatformManifests"],
            "Web.Host-runtime-selection.log")
        target["sdkRuntimeSelection"] = runtime_selection(read_json(runtime_log)["Items"], target, self.cache)
        write_json(self.evidence_file("assets-inventory.json"), self.assets)
        for name in (PREFIX + "Web.Host.dll", PREFIX + "Web.Host.deps.json"):
            if (self.output / name).is_file():
                self.evidence_file(str((self.output / name).relative_to(self.evidence)))
        self.report["hostOutputRoot"] = self.output.relative_to(self.evidence).as_posix()
        self.host = check_host(self.output, self.cache, target)
        write_json(self.evidence_file("host-output.json"), self.host)

    def gaps(self):
        reference = self.repo / "eng/r3_r2_reference.json"
        result = package_gaps(self.assets, self.host, framework_projects(self), read_json(reference))
        write_json(self.evidence_file("package-gaps.json"), result)
        self.report["inventories"] = {"package-gaps.json": artifact(self.evidence / "package-gaps.json", self.evidence)}
        require(not result["frameworkDifferencesRequiringAttribution"],
                "原版框架与维护源码存在待归因差异，详见 package-gaps.json")
        require({dll["packageId"] for dll in self.host["frameworkRuntimeDlls"]}
                == result["originalHostFramework"].keys(), "Host 框架 DLL 与原版框架包闭包不符")
        write_json(self.evidence_file(MACHINE_BASELINE), comparison_manifest(self.assets, self.host))
        self.report["inventories"] = {
            name: artifact(self.evidence / name, self.evidence) for name in
            ("assets-inventory.json", "host-output.json", "package-gaps.json", MACHINE_BASELINE)
        }

    def execute_r3(self):
        from zipfile import BadZipFile

        actions = (self.preflight, self.materialize, self.toolchain, self.restore, self.inventory,
                   self.build, self.inspect_output, self.gaps)
        stage = STAGES[0]
        try:
            for stage, action in zip(STAGES, actions):
                self.step(stage, action)
        except (VerificationError, OSError, ValueError, KeyError, TypeError, AttributeError,
                IndexError, ET.ParseError, BadZipFile) as error:
            reason = str(error)
            step = self.report["stages"][stage]
            step.update(status="failed", exitCode=1, reason=step.get("reason", reason))
            self.report.update(status="failed", exitCode=1, reason=reason)
            for step in self.report["stages"].values():
                if step["status"] == "not_run":
                    step["reason"] = f"{stage} 未通过：{reason}"
            print(f"R3 Web.Host 验收失败：{reason}", file=sys.stderr)
        else:
            self.report.update(status="passed", exitCode=0)
        self.report["finishedAt"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return self.report["exitCode"]


def execute(args):
    run = R3Run(ROOT, make_run_directory(args.evidence_root, "r3-web-host-"))
    print(f"R3 Web.Host report: {run.report_path}", flush=True)
    return run.execute_r3()
