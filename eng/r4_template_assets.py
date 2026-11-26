"""核对 R4 模板入口的冻结归档、构建资产和实际程序集。"""

from pathlib import Path
from zipfile import ZipFile

from r3_automapper_packages import stack_package
from r3_leaf_packages import bytes_sha256
from r3_template_net9_runtime import unique_loaded
from r3_web_host import NUGET_SOURCE, artifact, project_path
from verify import read_json, require, sha256


ENTRY_LABELS = {"Web.Host": "host", "Migrator": "migrator"}
WEB_ONLY = {"Du.Abp.AspNetCore", "Du.Abp.AspNetCore.SignalR", "Du.Abp.Web.Common"}
OPTIONAL = {
    "Web.Host": {"Du.AutoMapper.Collection"},
    "Migrator": {"Du.Abp.AutoMapper", "Du.AutoMapper", "Du.AutoMapper.Collection"},
}


def public_downloads(manifest_file, downloads_file, batch_root, batch):
    # 发布核验入口的清单读取链也会导入历史资产复核。
    from r4_public_release import HEX_SHA256, MANIFEST_SHA256

    require(sha256(manifest_file) == MANIFEST_SHA256, "公开消费的首发清单 SHA-256 不符")
    manifest = read_json(manifest_file)
    packages = manifest["packages"]
    require(manifest["handoff"]["batchSha256"] == sha256(batch_root / "batch.json")
            and manifest["template"] == batch["template"]
            and packages.keys() == batch["packages"].keys(), "首发清单的冻结批次、模板或包集合不符")
    downloads = read_json(downloads_file)
    require(isinstance(downloads, dict) and downloads.get("schemaVersion") == 1
            and downloads.get("nugetSource") == NUGET_SOURCE
            and downloads.get("manifestSha256") == MANIFEST_SHA256, "公开下载登记的 schema、包源或首发清单摘要不符")
    rows = downloads["packages"]
    require(isinstance(rows, dict), "公开下载登记的 packages 须为按包 ID 索引的对象")
    missing, extra = sorted(packages.keys() - rows.keys()), sorted(rows.keys() - packages.keys())
    require(not missing and not extra, f"公开下载登记的包集合不符，缺少 {missing}，多出 {extra}")
    for name, registered in packages.items():
        row = rows[name]
        version = registered["version"]
        frozen = batch["packages"][name]
        upload = registered["archive"]["sha256"]
        require(isinstance(row, dict) and row.get("version") == version == frozen["version"]
                and row.get("uploadSha256") == upload == frozen["archive"]["sha256"],
                f"{name}/{version} 公开下载登记的版本或上传摘要不符")
        digest = row.get("downloadSha256")
        require(isinstance(digest, str) and HEX_SHA256.fullmatch(digest) and digest != upload,
                f"{name}/{version} 缺少仓库签名后的公开下载摘要")
    return rows


def verify_build_entry(directory, inputs, entry, batch_root, batch, inspection, graph, launch, *, downloads=None,
                       local_ids=None):
    tfm = inputs["targetFramework"]
    label = f"{tfm} {entry}"
    feed = directory / "frozen-feed"
    cache = directory / "packages"
    registered = batch["packages"]
    if local_ids is None:
        local_ids = registered.keys() if downloads is None else ()
    require(set(local_ids) <= registered.keys(), f"{label} 的本地包 ID 超出维护包集合")
    sources = {str(feed), NUGET_SOURCE} if local_ids else {NUGET_SOURCE}
    mode = "frozen" if set(local_ids) == registered.keys() else "mixed" if local_ids else "public"
    require(inputs.get("packageSourceMode", "frozen") == mode and inputs["nuget"]["cachesInitiallyEmpty"]
            and set(inputs["nuget"]["effectiveSources"]) == sources and (local_ids or not feed.exists()),
            f"{label} 的空缓存或维护包源不符")
    batch_record = "r5Batch" if "r5Batch" in inputs else "r4Batch"
    require(inputs[batch_record]["sha256"] == sha256(batch_root / "batch.json"), f"{label} 的冻结批次不符")
    output = directory / "source/aspnet-core" / project_path(entry).parent / "bin/Release" / tfm
    manifest_file = directory / f"{entry}-output.json"
    manifest = read_json(manifest_file)
    require(Path(launch["cwd"]) == output
            and artifact(manifest_file, directory) == launch["outputVerification"], f"{label} 的输出清单不符")
    entry_asset = manifest["entry"]
    require(Path(launch["argv"][1]) == output / entry_asset["path"]
            and sha256(output / entry_asset["path"]) == entry_asset["sha256"], f"{label} 的 Release 入口不符")

    expected = set(registered) if entry == "Web.Host" else set(registered) - WEB_ONLY
    candidates = [(key, row) for key, row in graph["packages"].items() if stack_package(row["id"])]
    packages = {row["id"]: (key, row) for key, row in candidates}
    require(set(packages) == expected and len(candidates) == len(expected), f"{label} 的维护包闭包不符：{sorted(packages)}")
    origins = {}
    for name, (key, item) in sorted(packages.items()):
        package = registered[name]
        targets = inspection[name]["targets"]
        target = targets.get(tfm)
        if target is None:
            target, = targets.values()
        asset = target["asset"]
        filename = Path(asset).name
        digest = target["assetSha256"]
        archive = package["archive"]
        source = str(feed) if name in local_ids else NUGET_SOURCE
        restored = archive["sha256"] if name in local_ids else downloads[name]["downloadSha256"]
        version = package["version"]
        cached_package = cache / name.lower() / version.lower()
        cached_archive = cached_package / f"{name.lower()}.{version.lower()}.nupkg"
        require(key == f"{name}/{version}" and item["source"] == source
                and cache / item["cachePath"] == cached_package
                and cache / item["archive"]["path"] == cached_archive
                and cached_archive.resolve() == cached_archive
                and read_json(cached_package / ".nupkg.metadata")["source"] == source,
                f"{label} 的 {key} 还原来源或版本不符")
        require(restored == item["archive"]["sha256"] == sha256(cached_archive),
                f"{label} 的 {key} 缓存归档 SHA-256 不符，预期 {restored}")
        with ZipFile(batch_root / archive["path"]) as file:
            require(file.namelist().count(asset) == 1 and bytes_sha256(file.read(asset)) == digest,
                    f"{label} 的 {key} 冻结包内 DLL 缺失、重名或摘要不符")
        references = graph["compileReferences"].get(filename, [])
        require(len(references) == 1, f"{label} 的 {key} 缺少唯一的编译 DLL")
        reference, = references
        copied = manifest["packageCopies"].get(filename, {})
        expected_reference = cached_package / asset
        require(reference["package"] == copied.get("package") == key
                and reference["packageAsset"] == copied.get("packageAsset") == asset
                and Path(reference["path"]) == expected_reference == Path(copied.get("cachePath", ".")),
                f"{label} 的 {key} 编译或输出 DLL 来源不符")
        output_file = output / filename
        require(reference["sha256"] == copied["sha256"] == sha256(expected_reference) == sha256(output_file)
                == manifest["files"]["files"][filename] == digest, f"{label} 的 {key} 编译或输出 DLL 摘要不符")
        origins[name] = {"archive": archive, "asset": asset, "assetSha256": digest,
                         "assembly": target["assembly"]["name"], "outputName": filename,
                         "loadRequired": name not in OPTIONAL[entry],
                         "restoredArchive": {"source": source, **item["archive"]}}
    return {"tfm": tfm, "entry": entry, "output": str(output), "entryAsset": entry_asset,
            "packageCount": len(origins), "packages": origins,
            "packageSourceMode": mode,
            "prunedMaintenanceDependencies": graph.get("prunedMaintenanceDependencies", {}),
            "releaseOutput": artifact(manifest_file, directory)}


def verify_build_directory(directory, inputs, batch_root, batch, inspection, *, downloads=None, local_ids=None):
    graph = read_json(directory / "assets-inventory.json")
    launch = read_json(directory / "launch-manifest.json")
    return {entry: verify_build_entry(directory, inputs, entry, batch_root, batch, inspection,
                                      graph[entry], launch[entry], downloads=downloads, local_ids=local_ids)
            for entry in ENTRY_LABELS}


def verify_process(build, launch, observed):
    entry = build["entry"]
    output = Path(build["output"])
    pid = launch.get("pid")
    label = f"{build['tfm']} {entry} PID {pid}"
    entry_asset = build["entryAsset"]
    entry_dll = output / entry_asset["path"]
    require(pid and observed.get("pid") == pid and launch["exitCode"] == 0
            and Path(launch["cwd"]) == output and Path(launch["argv"][1]) == entry_dll,
            f"{label} 的观察进程、退出状态或启动入口不符")
    rows = observed["assemblies"]
    entry_loaded = unique_loaded(rows, entry_dll.stem, pid, process_name=entry)
    require(Path(entry_loaded["path"]) == entry_dll
            and launch["entrySha256"] == entry_loaded["sha256"] == entry_asset["sha256"] == sha256(entry_dll),
            f"{label} 的实际入口 DLL 来源或摘要不符")
    packages = {}
    for name, origin in build["packages"].items():
        loaded = unique_loaded(rows, origin["assembly"], pid, optional=not origin["loadRequired"],
                               process_name=entry)
        dll = output / origin["outputName"]
        require(sha256(dll) == origin["assetSha256"], f"{label} 的 {name} 输出 DLL 摘要不符")
        if loaded:
            require(Path(loaded["path"]) == dll and loaded["contextId"] == entry_loaded["contextId"],
                    f"{label} 的 {name} 实际加载 DLL 来源不符：{loaded['path']}")
            require(loaded["sha256"] == origin["assetSha256"], f"{label} 的 {name} 实际加载 DLL 摘要不符")
        packages[name] = origin | {"state": "loaded" if loaded else "output_only", "processAssembly": loaded}
    return build | {"pid": pid, "entryAssembly": entry_loaded, "sharedRuntime": launch["sharedRuntime"],
                    "packages": packages}
