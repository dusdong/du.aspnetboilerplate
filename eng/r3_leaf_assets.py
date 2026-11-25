"""核对消费资产、Release 输出及独立宿主回读的证据。"""

from pathlib import Path
import re
from zipfile import ZipFile

from r2_assets import asset_owners, check_reachable
from r2_packages import NUGET_SOURCE, framework_package, nuspec_metadata, version_range
from r3_leaf_packages import (ASP_NET, CASTLE, CLIENT, CLIENT_VERSION, CORE, CORE_RANGE, LOG4NET, R2_VERSION,
                              SIGNALR, TFM, bytes_sha256)
from r3_web_host import check_runtime_declarations, inside, package_hashes
from verify import read_json, require, sha256


TARGET = ".NETCoreApp,Version=v9.0"
APP = "SignalRLog4Net"
NOTIFIER = "Abp.AspNetCore.SignalR.Notifications.SignalRRealTimeNotifier"
SHARED = {"Microsoft.NETCore.App": "System.Private.CoreLib.dll",
          "Microsoft.AspNetCore.App": "Microsoft.AspNetCore.SignalR.Core.dll"}


def check_assets(data, project, cache, feeds, inputs, satisfies_range):
    restore = data["project"]["restore"]
    require(Path(restore["projectPath"]).resolve() == project and Path(restore["packagesPath"]).resolve() == cache and
            {Path(folder).resolve() for folder in data["packageFolders"]} == {cache}, "还原项目或独立包缓存不符")
    require(set(restore["sources"]) == {*map(str, feeds.values()), NUGET_SOURCE} and
            restore["configFilePaths"] == [str(project.parent / "NuGet.Config")], "有效 NuGet 配置或源不符")
    require(set(data["targets"]) == {TFM} and restore["originalTargetFrameworks"] == [TFM],
            f"还原目标预期 {TFM}，实际 {list(data['targets'])}")
    require(not restore["frameworks"][TFM]["projectReferences"], "消费者出现源码项目引用")
    require(not any(log.get("code") == "NU1605" or log.get("level") == "Error" for log in data.get("logs", [])),
            "消费者还原报告存在错误或降级")
    declared = data["project"]["frameworks"][TFM]["dependencies"]
    direct = {name: inputs[name]["version"] for name in (ASP_NET, SIGNALR, CASTLE)}
    direct[CLIENT] = CLIENT_VERSION
    require({name: row["version"].replace(" ", "") for name, row in declared.items() if row["target"] == "Package"}
            == {name: f"[{version},{version}]" for name, version in direct.items()},
            f"消费根引用及版本不符：{declared}")

    graph = data["targets"][TFM]
    expected = {f"{name}/{entry['version']}" for name, entry in inputs.items()}
    actual = {key for key in graph if framework_package(key.split("/")[0])}
    require(actual == expected, f"消费闭包缺失或混装框架包，预期 {sorted(expected)}，实际 {sorted(actual)}")
    require(set(data["libraries"]) == graph.keys(), "还原图存在未选中或无关资产库")
    check_reachable(graph, direct, TFM)

    records = {}
    for key, entry in graph.items():
        name, version = key.split("/")
        library = data["libraries"][key]
        require(entry["type"] == library["type"] == "package", f"{key} 不是独立包引用")
        package = inputs.get(name)
        source = str(feeds[version]) if package else NUGET_SOURCE
        hashes = package_hashes(cache, key, library["path"], source)
        require(hashes["contentSha512"] == library["sha512"], f"{key} 缓存内容哈希与还原图不符")
        deps = entry.get("dependencies", {})
        records[key] = {"id": name, "version": version, "direct": name in direct,
                        "dependencies": deps, **hashes,
                        "assets": {section: entries for section, entries in entry.items()
                                   if section not in ("type", "dependencies")}}
        if package:
            require(hashes["archive"]["sha256"] == package["archiveSha256"], f"{key} 还原归档 SHA-256 不符")
            check_framework_package(key, graph, package, cache, hashes["cachePath"])

    castle_key = f"{CASTLE}/{inputs[CASTLE]['version']}"
    log4net = check_log4net_assets(graph, records, cache, castle_key, satisfies_range)
    client_key = f"{CLIENT}/{CLIENT_VERSION}"
    require(client_key in records and records[client_key]["assets"].get("compile") and
            records[client_key]["assets"].get("runtime"), f"{client_key} 缺少实际编译或运行资产")
    runtime_dlls = {f"{entry['assembly']}.dll": {"package": f"{name}/{entry['version']}", "asset": entry["asset"],
                                             "sha256": entry["assetSha256"]} for name, entry in inputs.items()}
    runtime_dlls["log4net.dll"] = {**log4net["selectedAssets"]["runtime"], "package": log4net["package"]}
    return {"direct": declared, "packages": records, "runtimeDlls": runtime_dlls, "log4net": log4net}


def check_log4net_assets(graph, records, cache, castle_key, satisfies_range):
    owners = [key for key in graph if key.split("/")[0].casefold() == LOG4NET]
    require(len(owners) == 1, f"{castle_key} 需要唯一的 {LOG4NET} 解析版本，实际 {owners}")
    key = owners[0]
    log = records[key]
    edge = graph[castle_key].get("dependencies", {}).get(LOG4NET)
    constraint = version_range(edge) if edge else None
    require(constraint and satisfies_range(log["version"], constraint),
            f"{castle_key} → {LOG4NET} 依赖范围 {constraint} 不接受实选版本 {log['version']}")
    archive_path = inside(cache, log["archive"]["path"])
    selected = {}
    with ZipFile(archive_path) as archive:
        metadata = nuspec_metadata(archive)
        require((metadata.findtext("id"), metadata.findtext("version")) == (log["id"], log["version"]),
                f"{key} 实际缓存归档的 nuspec 包 ID 或版本不符：{archive_path}")
        for section in ("compile", "runtime"):
            sources = asset_owners(graph, (section,), "log4net.dll")
            require(len(sources) == 1 and sources[0][0] == key,
                    f"{key} 的 log4net.dll {section} 缺失或多来源：{sources}")
            asset = sources[0][1]
            require(archive.namelist().count(asset) == 1, f"{key} 归档缺少唯一的 {section} 资产 {asset}")
            digest = bytes_sha256(archive.read(asset))
            cached = inside(cache, Path(log["cachePath"]) / asset)
            require(cached.is_file() and sha256(cached) == digest, f"{key} {section} {asset} 缓存与归档 SHA-256 不符")
            selected[section] = {"asset": asset, "sha256": digest}
    require(not asset_owners(graph, ("runtimeTargets",), "log4net.dll"), f"{key} 存在额外 RID 运行来源")
    return {"from": castle_key, "dependency": LOG4NET, "declaredRange": constraint,
            "package": key, "version": log["version"], "selectedAssets": selected}


def check_log4net_compile(items, assets, cache):
    log4net = assets["log4net"]
    expected = log4net["selectedAssets"]["compile"]
    package = assets["packages"][log4net["package"]]
    path = inside(cache, Path(package["cachePath"]) / expected["asset"])
    references = [item["FullPath"] for item in items["ReferencePath"]
                  if Path(item["FullPath"]).name.casefold() == "log4net.dll"]
    require(len(references) == 1 and Path(references[0]).resolve() == path and
            sha256(path) == expected["sha256"],
            f"MSBuild log4net.dll 编译来源不符，预期 {path}，实际 {references}")
    return {"path": str(path), **expected}


def check_framework_package(key, graph, package, cache, relative_package):
    entry = graph[key]
    deps = entry.get("dependencies", {})
    expected = {name: version_range(value) for name, value in package["dependencies"].items()}
    name = package["id"]
    if name in (SIGNALR, CASTLE):
        core = deps.get(CORE, "").replace(" ", "")
        require(core in (CORE_RANGE, f"[{R2_VERSION},{R2_VERSION}]"),
                f"{key} 实际核心边的范围不符：{core}")
        if core:
            deps = {**deps, CORE: CORE_RANGE}
    require({name: version_range(value) for name, value in deps.items()} == expected,
            f"{key} 还原依赖声明与归档 nuspec 不符：{deps}，预期 {expected}")
    require(sorted(entry.get("frameworkReferences", [])) == package["frameworkReferences"],
            f"{key} 还原的共享框架引用不符")
    asset = package["asset"]
    verify_selected_owners(graph, key, asset)
    require(all(set(entry.get(section, {})) == {asset} for section in ("compile", "runtime")),
            f"{key} 存在额外编译或运行资产")
    require(sha256(inside(cache, Path(relative_package) / asset)) == package["assetSha256"],
            f"{key} 还原的 {asset} SHA-256 不符")


def verify_selected_owners(graph, package, asset):
    assembly = Path(asset).name
    for section in ("compile", "runtime"):
        owners = asset_owners(graph, (section,), assembly)
        require(owners == [(package, asset)],
                f"{assembly} {section} 错目标、缺失或多来源，预期 {package} {asset}，实际 {owners}")
    require(not asset_owners(graph, ("runtimeTargets",), assembly), f"{assembly} 存在额外 RID 运行来源")


def check_output(output, assets, selection):
    deps = read_json(output / f"{APP}.deps.json")
    config = read_json(output / f"{APP}.runtimeconfig.json")["runtimeOptions"]
    require(deps["runtimeTarget"]["name"] == TARGET and config["tfm"] == TFM and
            {entry["name"] for entry in config["frameworks"]} == SHARED.keys(), "输出目标或共享框架不符")
    graph = deps["targets"][TARGET]
    libraries = deps["libraries"]
    packages = assets["packages"]
    app = f"{APP}/1.0.0"
    require({key for key, entry in libraries.items() if entry["type"] == "package"} == packages.keys(),
            ".deps.json 包集合与还原不符")
    target = {"entryProject": app, "projects": {}, "projectReferences": [], "directPackages": assets["direct"],
              "packages": packages, "sdkRuntimeSelection": selection}
    check_runtime_declarations(output, output.rglob("*.dll"), graph, libraries, target)

    expected_files = assets["runtimeDlls"]
    files = sorted(path.relative_to(output).as_posix() for path in output.rglob("*.dll")
                   if framework_package(path.stem) or path.name.lower() == "log4net.dll")
    require(files == sorted(expected_files), f"Release 输出框架或 log4net DLL 重名、缺失或多来源：{files}")
    for dll, record in expected_files.items():
        asset, key = record["asset"], record["package"]
        require(asset_owners(graph, ("runtime", "runtimeTargets"), dll) == [(key, asset)],
                f".deps.json {dll} 的运行来源或目标不符")
        chosen = selection.get(key, {}).get("runtime", {}).get(asset)
        require(chosen == {"outputPath": dll}, f"MSBuild 复制项中的 {dll} 来源或目标不符：{chosen}")
        require(sha256(output / dll) == record["sha256"], f"Release 输出 {dll} SHA-256 不符")
    return expected_files


def check_signalr(evidence):
    signalr = evidence.get("signalr", {})
    connection = signalr.get("connectionId")
    expected = signalr.get("expected", {})
    require(connection and signalr.get("online") ==
            {"connectionId": connection, "userId": 17025, "tenantId": None}, "缺少实际连接的在线登记或身份不符")
    require(signalr.get("register") is True, "缺少 Register 调用证据")
    require(signalr.get("configuredNotifier") == signalr.get("resolvedNotifier") == NOTIFIER,
            f"通知配置缺少 {NOTIFIER} 或实际解析类型不符")
    received = signalr.get("received")
    require(received, "客户端缺少 getNotification 负载")
    notification = received.get("notification", {})
    observed = {"userId": received.get("userId"), "notificationId": notification.get("id"),
                "name": notification.get("notificationName"),
                "marker": notification.get("data", {}).get("properties", {}).get("marker")}
    require(observed == expected and observed["userId"] == 17025 and observed["name"] == "Du.Abp.R3.SignalR" and
            all(re.fullmatch(r"[0-9a-f-]{36}", observed[field] or "") for field in ("notificationId", "marker")),
            f"getNotification 负载与当轮通知不符：{observed}")
    require(signalr.get("removed") == {"connectionId": connection, "absent": True},
            f"OnDisconnectedAsync 未移除连接 {connection}")
    return observed


def check_log4net(evidence, host_dir):
    marker = evidence["signalr"]["expected"]["marker"]
    line = f"INFO|Du.Abp.R3.Castle|R3 Castle {marker}"
    log = evidence.get("log4net", {})
    path = host_dir / "castle.log"
    require(log.get("path") == str(path) and path.is_file(), f"缺少 Castle 日志文件 {path}")
    matches = [row for row in path.read_text(encoding="utf-8").splitlines() if marker in row]
    require(matches == [line] and log.get("expectedLine") == log.get("actualLine") == line,
            f"Castle 日志完整等级、类别或消息不符：{matches}")
    return {"path": str(path), "sha256": sha256(path), "line": line}


def check_runtime(evidence, output, dlls, dotnet, pid):
    runtime = evidence["runtime"]
    require(runtime["architecture"] == "Arm64" and runtime["rid"] == "osx-arm64" and runtime["pid"] == pid and
            Path(runtime["dotnet"]).resolve() == dotnet, f"宿主实际进程、dotnet 或架构不符：{runtime}")
    require(runtime["shared"].keys() == SHARED.keys(), "宿主缺少两个共享框架的实际加载证据")
    shared = {}
    for name, assembly in SHARED.items():
        path = Path(runtime["shared"][name])
        version = path.parent.name
        require(re.fullmatch(r"9\.0\.(?:0|[1-9][0-9]*)", version),
                f"宿主 {name} 实际加载的运行时版本与 {TFM} 不符：{path}")
        root = dotnet.parent / "shared" / name / version
        expected = root / assembly
        require(path.is_absolute() and path.is_file() and path.resolve() == expected.resolve(),
                f"宿主 {name} 实际加载位置不属于所选 dotnet，预期 {expected}，实际 {path}")
        shared[name] = {"path": str(path), "version": version, "source": str(root), "sha256": sha256(path)}
    require(runtime["assemblies"].keys() == {Path(dll).stem for dll in dlls}, "宿主实际程序集集合不符")
    for dll, entry in dlls.items():
        loaded = runtime["assemblies"][Path(dll).stem]
        path = Path(loaded["path"])
        require(path.resolve() == (output / dll).resolve() and sha256(path) == loaded["sha256"] == entry["sha256"]
                and loaded["identity"] == entry["identity"] and loaded["target"] == entry["target"],
                f"宿主实际加载 {dll} 的位置、摘要、程序集身份或目标不符：{loaded}")
    return {"pid": pid, "architecture": runtime["architecture"], "rid": runtime["rid"],
            "dotnet": runtime["dotnet"], "shared": shared, "assemblies": runtime["assemblies"]}
