"""核对 R3 定向消费使用的生产证据和封装资产。"""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from r2_packages import NUGET_SOURCE, framework_package, metadata_groups, nuspec_metadata, package_archive, version_range
from r3_web_host import inside
from verify import read_json, require, sha256


TFM = "net9.0"
R2_VERSION = "10.5.1-r2.1"
CORE = "Du.Abp"
ASP_NET = "Du.Abp.AspNetCore"
WEB_COMMON = "Du.Abp.Web.Common"
SIGNALR = "Du.Abp.AspNetCore.SignalR"
CASTLE = "Du.Abp.Castle.Log4Net"
CLIENT = "Microsoft.AspNetCore.SignalR.Client"
CLIENT_VERSION = "9.0.18"
LOG4NET = "log4net"
PRODUCED_LOG4NET_VERSION = "3.3.2"
PRODUCED_LOG4NET_ASSET = "lib/netstandard2.0/log4net.dll"
R2_IDS = (CORE, WEB_COMMON, ASP_NET)
R3_IDS = (SIGNALR, CASTLE)
SOURCE_PROOF = "du-r3-candidate-source.json"
CORE_RANGE = f"[{R2_VERSION}]"
PRODUCTION_FILES = ("evaluation", "assets", "r2Core", "r2CacheMetadata", "compiler", "packLog", "restoreLog", "nuspec")


def bytes_sha256(data):
    return hashlib.sha256(data).hexdigest()


def checked_file(root, relative, expected):
    file = inside(root, relative)
    require(file.is_file(), f"缺少实物 {file}")
    actual = sha256(file)
    require(actual == expected, f"{file} SHA-256 不符，预期 {expected}，实际 {actual}")
    return file


def package_details(archive, name, version):
    metadata = nuspec_metadata(archive)
    require((metadata.findtext("id"), metadata.findtext("version")) == (name, version),
            f"{archive.filename} nuspec 包 ID 或版本不符")
    groups = metadata_groups(metadata, "dependencies", "id")
    require(TFM in groups and not metadata.findall("dependencies/dependency"),
            f"{name} nuspec 缺少 {TFM} 依赖组或有未分组依赖")
    frameworks = metadata_groups(metadata, "frameworkReferences", "name")
    return metadata, groups, frameworks


def verify_repository(metadata, archive, source, proof):
    expected = {"type": "git", "url": source["repositoryUrl"]}
    committed = "commit" in proof
    require(source["mode"] == ("committed" if committed else "uncommitted"),
            f"{archive} 源码证明与已验证来源模式不符")
    if committed:
        expected["commit"] = proof["commit"]
    repository = metadata.find("repository")
    actual = repository.attrib if repository is not None else {}
    require(actual == expected, f"{archive} nuspec repository 来源不符，预期 {expected}，实际 {actual}")


def read_leaf(path, symbol, name, version, entry, source, proof):
    assembly = name.removeprefix("Du.")
    dll = f"lib/{TFM}/{assembly}.dll"
    pdb = f"lib/{TFM}/{assembly}.pdb"
    with ZipFile(path) as archive, ZipFile(symbol) as symbols:
        metadata, groups, frameworks = package_details(archive, name, version)
        dependencies = {dep: record["version"] for dep, record in groups[TFM].items()}
        internal = {dep: value for dep, value in dependencies.items() if framework_package(dep)}
        require(internal == {CORE: CORE_RANGE},
                f"{name} nuspec 核心依赖 ID 或范围不符，预期 {CORE} {CORE_RANGE}，实际 {internal}")
        third_party = {dep: value for dep, value in dependencies.items() if dep not in internal}
        expected_third_party = {LOG4NET: f"[{PRODUCED_LOG4NET_VERSION},)"} if name == CASTLE else {}
        require({dep: version_range(value) for dep, value in third_party.items()} == expected_third_party,
                f"{name} nuspec 第三方依赖范围不符：{third_party}")
        expected_frameworks = {TFM: {"Microsoft.AspNetCore.App"}} if name == SIGNALR else {}
        require(set(groups) == {TFM} and {tfm: set(refs) for tfm, refs in frameworks.items()} == expected_frameworks,
                f"{name} nuspec 目标组或共享框架不符")
        require({member.split("/")[1] for member in archive.namelist() if member.startswith(("lib/", "ref/"))} == {TFM},
                f"{name} 包内库资产目标不是唯一 {TFM}")
        package_archive(archive, {dll})
        package_archive(symbols, {pdb})
        symbol_metadata, _, _ = package_details(symbols, name, version)
        target = entry["targets"][TFM]
        require(set(entry["targets"]) == {TFM} and
                (entry["assemblyName"], entry["rootNamespace"], target["path"], target["pdbPath"]) ==
                (assembly, "Abp", dll, pdb), f"{name} 清单目标或程序集身份不符")
        require(bytes_sha256(archive.read(dll)) == target["sha256"], f"{name} {dll} SHA-256 不符")
        require(bytes_sha256(symbols.read(pdb)) == target["pdbSha256"], f"{name} {pdb} SHA-256 不符")
        require(json.loads(archive.read(SOURCE_PROOF)) == proof, f"{name} 包内完整源码证明与已验证清单不符")
        verify_repository(metadata, path, source, proof)
        verify_repository(symbol_metadata, symbol, source, proof)
        require(metadata.findtext("license") == "LICENSE.md" and metadata.findtext("icon") == "abp_nupkg.png",
                f"{name} 许可证或图标声明不符")
        for file, expected in source["assets"].items():
            require(bytes_sha256(archive.read(file)) == expected, f"{name} {file} 与候选源码不符")
        return {"id": name, "version": version, "archive": str(path), "archiveSha256": entry["package"]["sha256"],
                "symbol": str(symbol), "symbolSha256": entry["symbols"]["sha256"], "pdbSha256": target["pdbSha256"],
                "assembly": assembly, "asset": dll, "assetSha256": target["sha256"], "dependencies": dependencies,
                "frameworkReferences": sorted(frameworks.get(TFM, {}))}


def read_r2(feed, reference, name):
    entry = reference["packages"][name]
    target = entry["targets"][TFM]
    path = checked_file(feed, f"{name}.{R2_VERSION}.nupkg", entry["nupkgSha256"])
    with ZipFile(path) as archive:
        metadata, groups, frameworks = package_details(archive, name, R2_VERSION)
        asset = target["assetPath"]
        require(bytes_sha256(archive.read(asset)) == target["assetSha256"], f"{name} {asset} 与 R2 原件不符")
        proof = json.loads(archive.read("du-core-candidate-source.json"))
        require(proof["tree"] == reference["frameworkTree"], f"{name} 包内 R2 框架树不符")
        dependencies = {dep: row["version"] for dep, row in groups[TFM].items()}
        require({dep: value for dep, value in dependencies.items() if framework_package(dep)} ==
                target["internalDependencies"], f"{name} R2 核心依赖边不符")
    return {"id": name, "version": R2_VERSION, "archive": str(path), "archiveSha256": entry["nupkgSha256"],
            "assembly": entry["assemblyName"], "asset": asset, "assetSha256": target["assetSha256"],
            "dependencies": dependencies, "frameworkReferences": sorted(frameworks.get(TFM, {})), "sourceProof": proof}


def verify_production(root, declared, inputs, name):
    files = declared["production"][name]
    require(set(files) == set(PRODUCTION_FILES), f"{name} 生产证据集合不符")
    paths = {kind: checked_file(root, info["path"], info["sha256"]) for kind, info in files.items()}
    actual_core = read_json(paths["r2Core"])
    core = inputs[CORE]
    comparisons = {"id": CORE, "version": R2_VERSION, "archiveSha256": core["archiveSha256"],
                   "assetPath": core["asset"], "assetSha256": core["assetSha256"]}
    require(all(actual_core.get(key) == value for key, value in comparisons.items()),
            f"{name} 生产所用核心与 R2 实物不符")
    read = read_json(paths["assets"])
    metadata = read_json(paths["r2CacheMetadata"])
    evaluation = read_json(paths["evaluation"])
    compiler = read_json(paths["compiler"])
    properties = evaluation["Properties"]
    assembly = inputs[name]["assembly"]
    require((properties["PackageId"], properties["PackageVersion"], properties["TargetFramework"],
             properties["AssemblyName"], properties["RootNamespace"], properties["RepositoryCommit"]) ==
            (name, declared["version"], TFM, assembly, "Abp", declared["sourceProof"].get("commit", "")),
            f"{name} 生产项目求值或 RepositoryCommit 与来源证明不符")
    restore = read["project"]["restore"]
    direct = read["project"]["frameworks"][TFM]["dependencies"]
    graph = read["targets"][TFM]
    key = f"{CORE}/{R2_VERSION}"
    exact = f"[{R2_VERSION},{R2_VERSION}]"
    package_path = Path(restore["packagesPath"]) / read["libraries"][key]["path"]
    evaluation_items = evaluation["Items"]
    relevant = {item["Identity"]: item["Version"] for item in evaluation_items["PackageReference"]
                if item.get("PrivateAssets", "").lower() != "all"}
    require(not evaluation_items["ProjectReference"] and relevant == inputs[name]["dependencies"],
            f"{name} 生产项目的直接包或源码项目引用不符：{relevant}")
    require(not restore["frameworks"][TFM]["projectReferences"] and
            {pkg for pkg in graph if framework_package(pkg.split("/")[0])} == {key} and
            direct[CORE]["version"].replace(" ", "") == exact and
            actual_core["declaredRange"].replace(" ", "") == exact and
            all(set(graph[key][section]) == {core["asset"]} for section in ("compile", "runtime")),
            f"{name} 生产还原图核心范围、来源或资产不符")
    require(set(restore["sources"]) == {actual_core["source"], NUGET_SOURCE} and
            metadata["source"] == actual_core["source"] and
            metadata["contentHash"] == actual_core["nugetContentSha512"] == read["libraries"][key]["sha512"] and
            package_path / Path(actual_core["archive"]).name == Path(actual_core["archive"]) and
            package_path.resolve() / core["asset"] == Path(compiler["reference"]) == Path(actual_core["asset"]) and
            compiler["sha256"] == core["assetSha256"] and compiler["project"] == assembly,
            f"{name} 编译资产、NuGet 内容哈希或生产缓存来源不符")
    log4net = None
    if name == CASTLE:
        selected = graph[f"{LOG4NET}/{PRODUCED_LOG4NET_VERSION}"]
        require(version_range(direct[LOG4NET]["version"]) == f"[{PRODUCED_LOG4NET_VERSION},)" and
                all(set(selected[section]) == {PRODUCED_LOG4NET_ASSET} for section in ("compile", "runtime")),
                f"{name} 生产 {LOG4NET} 范围或资产不符")
        log4net = {"declaredVersion": relevant[LOG4NET], "resolvedVersion": PRODUCED_LOG4NET_VERSION, "assets": selected}
    with ZipFile(inputs[name]["archive"]) as archive:
        nuspec = next(file for file in archive.namelist() if file.endswith(".nuspec"))
        require(paths["nuspec"].read_bytes() == archive.read(nuspec), f"{name} 生产 nuspec 与包内不符")
    return {"evidence": files, "core": actual_core, "compiler": compiler, "evaluation": properties, "log4net": log4net}


def verify_restore_config(root, declared, production):
    paths = {name: inside(root, relative) for name, relative in declared["restore"].items() if name != "source"}
    config = ET.parse(paths["config"])
    sources = {row.get("key"): row.get("value") for row in config.findall("packageSources/add")}
    require(sources == {"r2-core": production[SIGNALR]["core"]["source"], "nuget.org": NUGET_SOURCE} and
            config.find("packageSources/clear") is not None and
            config.find("fallbackPackageFolders/clear") is not None and
            config.find("packageSourceMapping/clear") is not None and
            [(source.get("key"), [package.get("pattern") for package in source])
             for source in config.findall("packageSourceMapping/packageSource")] ==
            [("r2-core", [CORE]), ("nuget.org", ["*"])] and declared["restore"]["source"] == NUGET_SOURCE,
            "生产 NuGet 配置来源或映射不符")
    return {name: {"path": str(path), "sha256": sha256(path)} for name, path in paths.items()}
