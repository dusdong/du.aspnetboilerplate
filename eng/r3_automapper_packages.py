"""检查 R3 AutoMapper 冻结原包与消费者选择的依赖、资产。"""

from pathlib import Path
import re
from zipfile import ZipFile

from r2_assets import asset_owners, check_reachable
from r2_packages import NUGET_SOURCE, framework_package, metadata_groups, nuspec_metadata, verify_source, version_range
from r3_leaf_assets import verify_selected_owners
from r3_leaf_packages import TFM, bytes_sha256, checked_file, read_r2
from r3_module_zero_packages import R3_IDS, expected_edges, read_r3
from r3_web_host import package_hashes
from verify import ROOT, read_json, require, sha256


ADAPTER = "Du.Abp.AutoMapper"
COLLECTION = "Du.AutoMapper.Collection"
ENGINE = "Du.AutoMapper"
CORE = "Du.Abp"
ZERO = "Du.Abp.ZeroCore"
SQLITE = "Microsoft.EntityFrameworkCore.Sqlite"
SQLITE_VERSION = "9.0.18"
ENGINE_MANIFEST = "62c8becad5836bab7da0fd26e10d8cbfcef53a4e06a6c6dca1ae45c4a167f52f"
ADAPTER_MANIFEST = "a442aa64237cc425fb9a9372bbb24314fdeabf4f4800e89562b3ad55ca3c9818"
ZERO_VERSION = "10.5.1-r3.3"
DEPS_TARGET = ".NETCoreApp,Version=v9.0"


def stack_package(name):
    return (framework_package(name) or
            re.match(r"^(?:du\.)?automapper(?:\.|$)", name, re.IGNORECASE) is not None)


def record(path, digest):
    return {"path": str(path), "sha256": digest}


def mapping_packages(engine_manifest, candidate_manifest, r2_feed):
    engine = read_json(checked_file(engine_manifest.parent, engine_manifest.name, ENGINE_MANIFEST))
    candidate = read_json(checked_file(candidate_manifest.parent, candidate_manifest.name, ADAPTER_MANIFEST))
    require(candidate["engineManifest"]["sha256"] == ENGINE_MANIFEST and candidate["engineSource"] == engine["source"],
            "下游清单引用的引擎清单或源码身份不符")

    upstream = engine["package"]
    old_engine_root = Path(upstream["archive"]).parents[2]
    build_relative = Path(upstream["buildDll"]).relative_to(old_engine_root)
    packages = {
        ENGINE: mapping_package(
            upstream, engine_manifest.parent / upstream["nupkgPath"], upstream["archiveSHA256"],
            upstream["dll"], upstream["dllSHA256"], engine_manifest.parent.parent / build_relative,
            engine["assembly"], engine["source"],
        ),
    }
    for key in ("collection", "framework"):
        entry = candidate[key]
        package = entry["mainPackage"]
        base = Path(package["path"]).parents[2]
        archive = candidate_manifest.parent / Path(package["path"]).relative_to(base)
        release = candidate_manifest.parent / Path(entry["releaseDll"]["path"]).relative_to(base)
        require(entry["releaseDll"]["sha256"] == entry["dllSHA256"], f"{entry['id']} 生产 Release 登记不符")
        packages[entry["id"]] = mapping_package(entry, archive, package["sha256"], entry["dllAsset"],
                                                 entry["dllSHA256"], release, entry["assembly"], entry["source"])

    reference = read_json(ROOT / "eng/r3_r2_reference.json")
    digest = reference["evidenceSha256"]["manifest"]
    require(candidate["r2Manifest"]["sha256"] == digest, "下游清单引用的 R2 清单不符")
    checked_file(r2_feed.parent, "manifest.json", digest)
    packages[CORE] = read_r2(r2_feed, reference, CORE)
    return packages


def mapping_package(entry, archive, archive_digest, asset, asset_digest, release, identity, source):
    # 固定生产清单的原包、原 Release 和身份逐一传递给两种消费者。
    checked_file(archive.parent, archive.name, archive_digest)
    checked_file(release.parent, release.name, asset_digest)
    name, version, target = (entry[key] for key in ("id", "version", "target"))
    public_key = identity["publicKeyToken"] or "null"
    full_name = (f"{identity['name']}, Version={identity['version']}, Culture={identity['culture']}, "
                 f"PublicKeyToken={public_key}")
    return {"id": name, "version": version, "target": target, "archive": str(archive), "archiveSha256": archive_digest,
            "asset": asset, "assetSha256": asset_digest, "release": record(release, asset_digest),
            "assembly": identity["name"], "fullName": full_name, "source": source}


def zero_packages(run, feed):
    registration = read_json(ROOT / "eng/r3_module_zero_reference.json")[ZERO_VERSION]
    path = checked_file(feed.parent, "manifest.json", registration["manifestSha256"])
    manifest = read_json(path)
    proof = checked_file(feed.parent, "du-r3-candidate-source.json", registration["sourceProofSha256"])
    require(read_json(proof) == manifest["sourceProof"] and manifest["version"] == ZERO_VERSION,
            "Module Zero 独立来源证明或版本不符")
    source = verify_source(run, path, manifest, label="module-zero")
    edges = expected_edges(ZERO_VERSION)
    return {name: read_r3(feed, feed.parent / "symbols", name, ZERO_VERSION, manifest["packages"][name],
                          source, edges[name])
            for name in R3_IDS[:2]}


def check_archive(path, package, edges):
    name, version = package["id"], package["version"]
    with ZipFile(path) as archive:
        metadata = nuspec_metadata(archive)
        require((metadata.findtext("id"), metadata.findtext("version")) == (name, version),
                f"{path} 的 nuspec 身份不符")
        target = package["target"]
        groups = metadata_groups(metadata, "dependencies", "id")
        require(set(groups) == {target} and not metadata.findall("dependencies/dependency"),
                f"{name} nuspec 依赖组应唯一且为 {target}")
        deps = {dep: row["version"] for dep, row in groups[target].items()}
        check_edges(name, deps, edges)
        asset = package["asset"]
        require(archive.namelist().count(asset) == 1 and bytes_sha256(archive.read(asset)) == package["assetSha256"],
                f"{name} 归档 {asset} 缺失、重名或摘要不符")
    return deps


def check_edges(name, dependencies, edges, *, assets=False):
    actual = {dep: version for dep, version in dependencies.items() if stack_package(dep)}
    require(actual.keys() == edges.keys(), f"{name} 映射与框架直接依赖预期 {sorted(edges)}，实际 {sorted(actual)}")
    for dep, expected in edges.items():
        version = actual[dep]
        valid = version == expected or (assets and version.replace(" ", "") == f"[{expected[1:-1]},{expected[1:-1]}]")
        require(valid, f"{name} → {dep} 预期 {expected}，实际 {version}")


def check_assets(data, project, cache, feed, frozen, direct, edges):
    restore = data["project"]["restore"]
    require(Path(restore["projectPath"]) == project and Path(restore["packagesPath"]) == cache and
            {Path(folder) for folder in data["packageFolders"]} == {cache}, "还原项目或独立包缓存不符")
    require(set(restore["sources"]) == {str(feed), NUGET_SOURCE} and not restore.get("fallbackFolders") and
            restore["configFilePaths"] == [str(project.parent / "NuGet.Config")], "有效 NuGet 配置或源不符")
    require(set(data["targets"]) == {TFM} and restore["originalTargetFrameworks"] == [TFM] and
            not restore["frameworks"][TFM]["projectReferences"], "消费者目标或源码项目引用不符")
    require(not any(log.get("level") == "Error" or log.get("code") == "NU1605" for log in data.get("logs", [])),
            "还原图存在错误或包降级")
    declared = data["project"]["frameworks"][TFM]["dependencies"]
    require(declared == {name: {"target": "Package", "version": f"[{version}, {version}]"}
                         for name, version in direct.items()}, f"直接引用不符：{declared}")

    graph = data["targets"][TFM]
    expected = {f"{name}/{row['version']}" for name, row in frozen.items()}
    actual = {key for key in graph if stack_package(key.split("/")[0])}
    require(actual == expected, f"候选闭包缺失或混装，预期 {sorted(expected)}，实际 {sorted(actual)}")
    require(data["libraries"].keys() == graph.keys(), "存在无关资产库")
    check_reachable(graph, direct, TFM)
    packages = {}
    for key, entry in sorted(graph.items()):
        name, version = key.split("/")
        library = data["libraries"][key]
        require(entry["type"] == library["type"] == "package", f"{key} 不是独立包引用")
        package = frozen.get(name)
        hashes = package_hashes(cache, key, library["path"], str(feed) if package else NUGET_SOURCE)
        require(hashes["contentSha512"] == library["sha512"], f"{key} 缓存内容 SHA-512 与还原图不符")
        packages[name] = entry | {"version": version, **hashes}
        if package:
            deps = entry.get("dependencies", {})
            check_edges(name, deps, edges.get(name, {}), assets=True)
            for dep in edges.get(name, {}):
                require(f"{dep}/{frozen[dep]['version']}" in graph, f"{key} → {dep} 未解析到冻结版本")
            require({dep: version_range(v) for dep, v in deps.items() if dep not in frozen} ==
                    {dep: version_range(v) for dep, v in package["dependencies"].items() if dep not in frozen},
                    f"{key} 第三方依赖声明与原包不同")
            asset = package["asset"]
            require(hashes["archive"]["sha256"] == package["archiveSha256"], f"{key} 缓存归档 SHA-256 不符")
            verify_selected_owners(graph, key, asset)
            require(sha256(cache / library["path"] / asset) == package["assetSha256"],
                    f"{key} 缓存 {asset} SHA-256 不符")
    if SQLITE in direct:
        for name in (SQLITE, SQLITE + ".Core"):
            require(packages[name]["version"] == SQLITE_VERSION, f"{name} 版本不符")
    resolved = [{
        "from": f"{name}/{frozen[name]['version']}", "dependency": dep,
        "nuspecDeclaration": frozen[name]["dependencies"][dep],
        "restoredDeclaration": packages[name]["dependencies"][dep],
        "resolved": f"{dep}/{packages[dep]['version']}",
    } for name in frozen for dep in edges.get(name, {})]
    return {"direct": declared, "packages": packages, "internalEdges": resolved}


def check_loaded(probe, output, cache, app, frozen, packages):
    deps = read_json(output / f"{app}.deps.json")
    graph = deps["targets"][DEPS_TARGET]
    rows = {row["Name"]: row for row in probe["assemblies"]}
    expected = {package["assembly"]: package for package in frozen.values()}
    require(len(rows) == len(probe["assemblies"]) and expected.keys() <= rows.keys(), "程序集实例缺失或重复")
    graph_ids = {key for key, entry in deps["libraries"].items() if entry["type"] == "package"}
    frozen_ids = {f"{name}/{entry['version']}" for name, entry in frozen.items()}
    restored_ids = {f"{name}/{entry['version']}" for name, entry in packages.items()}
    require(deps["runtimeTarget"]["name"] == DEPS_TARGET and
            graph_ids <= restored_ids and {key for key in graph_ids if stack_package(key.split("/")[0])} == frozen_ids,
            "Release .deps.json 候选包集合、来源或目标与还原图不符")
    evidence = {}
    for name, row in rows.items():
        dll = name + ".dll"
        owners = asset_owners(graph, ("runtime", "runtimeTargets"), dll)
        require(len(owners) == 1, f"Release {dll} 运行来源应唯一，实际 {owners}")
        owner, asset = owners[0]
        owner_name, _ = owner.split("/")
        package = packages[owner_name]
        actual = output / dll
        copies = [file for file in output.rglob("*") if file.name.casefold() == dll.casefold()]
        require(copies == [actual] and Path(row["Path"]) == actual and
                row["Sha256"] == sha256(actual), f"{dll} Release 路径、加载路径或 SHA-256 不符")
        selected = package.get("runtime", {})
        archive_path = cache / package["archive"]["path"]
        require(asset in selected, f"{dll} 运行资产 {asset} 与还原图不符")
        with ZipFile(archive_path) as archive:
            require(bytes_sha256(archive.read(asset)) == row["Sha256"], f"{dll} 加载资产与归档不符")
        if name in expected:
            frozen_record = expected[name]
            require((owner_name, asset, row["Sha256"]) ==
                    (frozen_record["id"], frozen_record["asset"], frozen_record["assetSha256"]) and
                    row["FullName"] == frozen_record.get("fullName", row["FullName"]), f"{dll} 冻结资产或身份不符")
        evidence[name] = row | {"package": owner, "archive": str(archive_path), "asset": asset}
    return evidence
