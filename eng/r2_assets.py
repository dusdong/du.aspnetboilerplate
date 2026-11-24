"""核对独立消费者的还原图、输出资产和 HTTP 证据。"""

from base64 import b64encode
from collections import deque
import hashlib
from pathlib import Path
import re

from r2_packages import NUGET_SOURCE, SQLITE, TARGETS, framework_package
from verify import read_json, require, sha256


def asset_owners(graph, sections, assembly):
    return sorted((key, path) for key, library in graph.items() for section in sections
                  for path in library.get(section, {}) if Path(path).name.casefold() == assembly.casefold())


def check_reachable(graph, direct, tfm):
    keys = {key.split("/")[0].casefold(): key for key in graph}
    require(len(keys) == len(graph), f"{tfm} 依赖图解析到同一包的多个版本")
    pending = deque(keys[name.casefold()] for name in direct)
    reachable = set()
    while pending:
        key = pending.popleft()
        if key not in reachable:
            reachable.add(key)
            pending.extend(keys[name.casefold()] for name in graph[key].get("dependencies", {})
                           if name.casefold() in keys)
    require(reachable == graph.keys(), f"{tfm} 无关依赖：{sorted(graph.keys() - reachable)}")


def check_assets(data, tfm, project, cache, feed, report, sqlite_version, check_dependency_ranges):
    restore = data["project"]["restore"]
    require(Path(restore["projectPath"]).resolve() == project.resolve(), "还原图项目路径不符")
    require(Path(restore["packagesPath"]).resolve() == cache and
            {Path(path).resolve() for path in data["packageFolders"]} == {cache}, "还原图包缓存不符")
    require(set(restore["sources"]) == {str(feed), NUGET_SOURCE}, "还原图软件包源或回退源不符")
    require(set(data["targets"]) == {tfm} and restore["originalTargetFrameworks"] == [tfm],
            f"只应还原 {tfm}，实际为 {list(data['targets'])}")
    require(not restore["frameworks"][tfm]["projectReferences"], f"{tfm} 存在源码项目引用")
    require(not any(log["code"] == "NU1605" or log.get("level") == "Error" for log in data.get("logs", [])),
            f"{tfm} 还原日志包含错误或包降级")
    version = report["version"]
    direct = data["project"]["frameworks"][tfm]["dependencies"]
    expected_direct = {name: f"[{version}, {version}]" for name in report["entries"]}
    expected_direct[SQLITE] = f"[{sqlite_version}, {sqlite_version}]"
    require({name: info["version"] for name, info in direct.items() if info["target"] == "Package"} ==
            expected_direct and set(direct) == expected_direct.keys(), f"{tfm} 直接引用不符：{direct}")

    graph = data["targets"][tfm]
    package_records = {}
    internal_ranges = {}
    framework = report["packages"]
    expected_framework = {f"{name}/{version}" for name in framework}
    actual_framework = {key for key in graph if framework_package(key.split("/")[0])}
    require(actual_framework == expected_framework, f"{tfm} 框架包混装或缺失：{sorted(actual_framework)}")
    require(set(data["libraries"]) == graph.keys(), f"{tfm} 存在未选中或无关资产库")
    check_reachable(graph, direct, tfm)
    for provider in (SQLITE, "Microsoft.EntityFrameworkCore.Sqlite.Core", "Microsoft.EntityFrameworkCore",
                     "Microsoft.EntityFrameworkCore.Relational", "Microsoft.Data.Sqlite.Core",
                     "Microsoft.AspNetCore.Mvc.NewtonsoftJson", "Microsoft.AspNetCore.Mvc.Razor.RuntimeCompilation"):
        require(f"{provider}/{sqlite_version}" in graph,
                f"{tfm} {provider} 未解析到本目标要求的 {sqlite_version}")
    for key, library in graph.items():
        name, actual_version = key.split("/")
        require(library["type"] == data["libraries"][key]["type"] == "package",
                f"{tfm} {key} 不是包引用")
        declared = data["libraries"][key]
        local = (cache / declared["path"]).resolve()
        require(local.is_relative_to(cache), f"{tfm} {key} 缓存路径越界：{local}")
        metadata = read_json(local / ".nupkg.metadata")
        expected_source = str(feed) if name in framework else NUGET_SOURCE
        require(metadata["source"] == expected_source,
                f"{tfm} {key} 包来源预期 {expected_source}，实际 {metadata['source']}")
        require(metadata["contentHash"] and metadata["contentHash"] == declared["sha512"],
                f"{tfm} {key} 内容哈希与资产不符")
        package = local / f"{name.lower()}.{actual_version.lower()}.nupkg"
        archive_hash = hashlib.sha512()
        with package.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                archive_hash.update(block)
        archive_sha512 = b64encode(archive_hash.digest()).decode("ascii")
        require(package.with_suffix(".nupkg.sha512").read_text().strip() == archive_sha512,
                f"{tfm} {key} NuGet 缓存摘要记录不符")
        package_sha256 = sha256(package)
        if name in framework:
            expected = framework[name]["targets"][tfm]
            require(package_sha256 == framework[name]["package"]["sha256"],
                    f"{tfm} {key} 实际缓存包 SHA-256 与候选不符")
            dependencies = library.get("dependencies", {})
            require({dependency for dependency in dependencies if framework_package(dependency)} ==
                    set(framework[name]["internalDependencies"]), f"{tfm} {key} 实际内部依赖边不符")
            internal_ranges.update({f"{tfm} {key} → {dependency}": dependencies[dependency]
                                    for dependency in framework[name]["internalDependencies"]})
            dll = framework[name]["assemblyName"] + ".dll"
            for section in ("compile", "runtime"):
                owners = asset_owners(graph, (section,), dll)
                require(owners == [(key, expected["path"])],
                        f"{tfm} {dll} {section} 错目标或多来源，预期 {key} {expected['path']}，实际 {owners}")
                require(set(library.get(section, {})) == {expected["path"]},
                        f"{tfm} {key} 含无关 {section} 资产")
            require(not asset_owners(graph, ("runtimeTargets",), dll),
                    f"{tfm} {dll} 有额外的 RID 运行资产来源")
            require(sha256(local / expected["path"]) == expected["sha256"],
                    f"{tfm} {key} 实际编译或运行 DLL 摘要不符")
        package_records[key] = {
            "id": name, "version": actual_version, "dependency": "direct" if name in direct else "transitive",
            "source": metadata["source"], "contentHash": metadata["contentHash"],
            "sha256": package_sha256, "archiveSha512": archive_sha512,
            "path": str(local), "dependencies": library.get("dependencies", {}),
            "assets": {section: library[section] for section in ("compile", "runtime", "runtimeTargets",
                       "native", "frameworkReferences", "build", "buildMultiTargeting", "resource")
                       if section in library},
        }
    check_dependency_ranges(version, internal_ranges, f"{tfm}-assets")
    return package_records


def compare_r1_graph(r1, tfm, data, packages):
    """记录源码验证环境和最小消费者之间的第三方包差异。"""
    lane = TARGETS[tfm][2]
    reference = read_json(r1 / lane / "restore-inventory.json")["projects"]
    earlier = {}
    for project, value in reference.items():
        for target in value["targets"]:
            if target["targetFramework"] == tfm:
                for package in target["packages"]:
                    earlier.setdefault(package["id"], {}).setdefault(package["version"], []).append(project)
    actual = {row["id"]: row["version"] for row in packages.values() if not framework_package(row["id"])}
    pruned = data["project"]["frameworks"][tfm].get("packagesToPrune", {})
    differences = {}
    for name in sorted(earlier.keys() | actual.keys(), key=str.casefold):
        before, selected = earlier.get(name, {}), actual.get(name)
        if selected and set(before) == {selected}:
            continue
        constraint = pruned.get(name)
        if not selected:
            reason = "R1 源码、测试或历史调用方使用，独立消费图未选中"
        elif not before:
            reason = "独立消费图新增"
        else:
            reason = "独立消费图按候选、Web SDK 和目标 SQLite Provider 的依赖解析版本"
        differences[name] = {"r1VersionsAndProjects": before, "r2Version": selected,
                             "consumerSdkPruneConstraint": constraint, "reason": reason}
    return differences


def check_output(output, tfm, candidate, packages):
    manifest = read_json(output / "MinimalBackend.deps.json")
    config = read_json(output / "MinimalBackend.runtimeconfig.json")
    version = candidate["version"]
    expected_framework = {f"{name}/{version}" for name in candidate["packages"]}
    runtime_target = f".NETCoreApp,Version=v{tfm.removeprefix('net')}"
    require(manifest["runtimeTarget"]["name"] == runtime_target, f"{tfm} deps.json 目标不符")
    require({framework["name"] for framework in config["runtimeOptions"]["frameworks"]} ==
            {"Microsoft.NETCore.App", "Microsoft.AspNetCore.App"} and config["runtimeOptions"]["tfm"] == tfm,
            f"{tfm} runtimeconfig 目标或共享框架不符")
    graph = manifest["targets"][runtime_target]
    require({key for key in graph if framework_package(key.split("/")[0])} == expected_framework,
            f"{tfm} deps.json 框架包混装或缺失")
    libraries = manifest["libraries"]
    package_keys = {key for key in graph if libraries[key]["type"] == "package"}
    require(package_keys == packages.keys() and libraries["MinimalBackend/1.0.0"]["type"] == "project",
            f"{tfm} deps.json 包图与还原图不符")
    references = graph.keys() - package_keys - {"MinimalBackend/1.0.0"}
    require(all(libraries[key]["type"] == "referenceassembly" and graph[key].get("compileOnly") and
                set(graph[key]) == {"compile", "compileOnly"} for key in references),
            f"{tfm} deps.json 出现无关引用或额外运行资产")
    files = [path for path in output.rglob("*.dll")
             if path.name.casefold() == "abp.dll" or path.name.casefold().startswith("abp.")]
    require({file.name for file in files} == {entry["assemblyName"] + ".dll"
            for entry in candidate["packages"].values()} and len(files) == len(expected_framework),
            f"{tfm} 输出框架程序集重名、缺失或多来源：{files}")
    for name, entry in candidate["packages"].items():
        key = f"{name}/{version}"
        asset = entry["targets"][tfm]
        dll = entry["assemblyName"] + ".dll"
        require(asset_owners(graph, ("runtime", "runtimeTargets"), dll) == [(key, asset["path"])],
                f"{tfm} deps.json {dll} 运行资产路径或来源不符")
        require(manifest["libraries"][key]["sha512"] == "sha512-" + packages[key]["contentHash"],
                f"{tfm} deps.json {key} 内容哈希不符")
        require(sha256(output / dll) == asset["sha256"], f"{tfm} 输出 {dll} SHA-256 不符")
    return graph


def check_http(evidence, expected_record):
    write = evidence["post"]
    read = evidence["get"]
    require(write["status"] == 201 and read["status"] == 200,
            f"HTTP 状态不符：POST {write['status']}，GET {read['status']}")
    inserted, queried = write["body"], read["body"]
    require({key: inserted.get(key) for key in expected_record} == expected_record and
            queried.get("records") == [expected_record], "SQLite 唯一行、记录 ID 或值不符")
    for key in ("request", "scope", "unitId", "contextId"):
        require(inserted.get(key) and queried.get(key) and inserted[key] != queried[key],
                f"读任务缺少独立 {key} 证据")
    active, committed = inserted.get("active"), inserted.get("committed")
    require(active and active.get("transactional") and active.get("connectionOpen") and
            active.get("providerTransaction") == "Microsoft.Data.Sqlite.SqliteTransaction" and
            active.get("transactionId") and active.get("request") == inserted["request"] and
            active.get("unitId") == inserted["unitId"], "写入请求缺少仓储 SQLite 活动事务证据")
    require(committed and committed.get("eventName") == "Completed" and committed.get("transactionCleared") and
            all(committed.get(key) == active[key] for key in ("request", "unitId", "transactionId")),
            "写入请求缺少同一 ABP 工作单元提交完成证据")
    require(queried.get("moduleInitialized") and set(queried["modules"]) ==
            {"ConsumerModule", "Abp.AspNetCore.AbpAspNetCoreModule", "Abp.EntityFrameworkCore.AbpEntityFrameworkCoreModule"}
            and queried["service"] == "RecordService" and
            "EfCoreRepositoryBase" in queried["repository"] and
            queried.get("provider") == SQLITE and re.fullmatch(r"\d+\.\d+\.\d+", queried.get("sqliteVersion", "")),
            "ABP 模块、DI 或 SQLite Provider 运行证据不符")
    return queried


def identity_text(info):
    token = info["publicKeyToken"] or "null"
    return f"{info['name']}, Version={info['version']}, Culture={info['culture']}, PublicKeyToken={token}"


def verify_runtime(queried, output, tfm, candidate, packages, graph, runtime_version, dotnet, pid):
    runtime = queried["runtime"]
    require(runtime["architecture"] == "Arm64" and runtime["rid"] == "osx-arm64" and runtime["pid"] == pid and
            Path(runtime["process"]).resolve() == dotnet and runtime["framework"] == f".NET {runtime_version}",
            f"{tfm} 实际宿主、架构或运行时不符：{runtime}")
    for field, family in (("netCore", "Microsoft.NETCore.App"), ("aspNetCore", "Microsoft.AspNetCore.App")):
        found = Path(runtime[field]).parent
        expected = dotnet.parent / "shared" / family / runtime_version
        require(found.resolve() == expected.resolve(), f"{tfm} 实际共享框架预期 {expected}，取得 {found}")
    expected = candidate["packages"]
    actual = {Path(assembly["location"]).name.removesuffix(".dll"): assembly
              for assembly in queried["frameworkAssemblies"]}
    require(len(queried["frameworkAssemblies"]) == len(actual) == len(expected),
            f"{tfm} 进程未加载唯一的五份框架程序集")
    for package in expected.values():
        name = package["assemblyName"]
        asset = package["targets"][tfm]
        value = actual[name]
        path = output / (name + ".dll")
        require(Path(value["location"]) == path and value["sha256"] == sha256(path) == asset["sha256"] and
                value["fullName"] == identity_text(asset["identity"]), f"{tfm} 已加载的 {name} 来源或身份不符")

    sqlite = [("sqliteAssembly", "Microsoft.Data.Sqlite.dll", "Microsoft.Data.Sqlite.Core"),
              ("providerAssembly", "Microsoft.EntityFrameworkCore.Sqlite.dll", "Microsoft.EntityFrameworkCore.Sqlite.Core")]
    for field, dll, package in sqlite:
        value = queried[field]
        owners = asset_owners(graph, ("runtime",), dll)
        selected = [(key, path) for key, path in owners if key.startswith(package + "/")]
        require(len(selected) == 1 and selected == owners, f"{tfm} {dll} 运行来源不唯一：{owners}")
        key, asset = selected[0]
        require(Path(value["location"]) == output / dll and
                value["sha256"] == sha256(Path(packages[key]["path"]) / asset) == sha256(output / dll),
                f"{tfm} 已加载 {dll} 与还原资产不同")

    native = queried["nativeSqlite"]
    native_asset = "runtimes/osx-arm64/native/libe_sqlite3.dylib"
    owners = [(key, asset) for key, asset in asset_owners(graph, ("runtimeTargets",), "libe_sqlite3.dylib")
              if asset == native_asset and graph[key]["runtimeTargets"][asset].get("rid") == "osx-arm64"
              and graph[key]["runtimeTargets"][asset].get("assetType") == "native"]
    require(len(owners) == 1 and owners[0][0].startswith("SQLitePCLRaw.lib.e_sqlite3/"),
            f"{tfm} 原生 SQLite 的 ARM64 资产来源不唯一：{owners}")
    key, asset = owners[0]
    require(asset in packages[key]["assets"]["runtimeTargets"] and
            Path(native["path"]) == output / asset and
            native["sha256"] == sha256(output / asset) == sha256(Path(packages[key]["path"]) / asset),
            f"{tfm} dyld 的 SQLite 原生库与还原的 osx-arm64 资产不同")
