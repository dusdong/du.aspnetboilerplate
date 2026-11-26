"""用冻结维护包核对 net10.0 模板的两个 Release 入口。"""

from pathlib import Path

from r3_leaf_packages import bytes_sha256
from r3_template_net9_packages import CandidateRun, ENTRIES, TOPOLOGY, archive_asset, git_blob, project_diff
from r3_web_host import PROVIDER, artifact, project_path, write_json
from verify import ROOT, make_run_directory, read_json, require


PROFILE = "r3-template-net10-upgrade"
TFM = "net10.0"
DEPS_TARGET = ".NETCoreApp,Version=v10.0"
PATCH_VERSION = "10.0.15"
EF = "Microsoft.EntityFrameworkCore"
DESIGN, TOOLS = f"{EF}.Design", f"{EF}.Tools"
JWT = "Microsoft.AspNetCore.Authentication.JwtBearer"
SQL_CLIENT = "Microsoft.Data.SqlClient"
SQL_CLIENT_VERSIONS = {SQL_CLIENT: "6.1.7", f"{SQL_CLIENT}.SNI.runtime": "6.0.3"}
PRUNED_MAINTENANCE_EDGES = {
    "Du.Abp": {"Microsoft.Extensions.Caching.Memory": "10.0.15", "Microsoft.Extensions.Options": "10.0.15"},
    "Du.AutoMapper": {"Microsoft.Extensions.Options": "8.0.0"},
}
PRUNE_MAXIMUM = "10.0.32767"
PKCS = "System.Security.Cryptography.Pkcs"
EF_RUNTIME = (EF, f"{EF}.Abstractions", f"{EF}.Relational", PROVIDER)
DIRECT_MICROSOFT = {
    "EntityFrameworkCore": (PROVIDER, DESIGN, TOOLS),
    "Web.Core": (JWT,),
    "Web.Host": (DESIGN,),
}
RUNTIME_PATCH_PREIMAGES = {
    "Web.Host": "9dc4012119389372efce0cc968792eaec2258f4e",
    "Web.Core": "b5cee78f297a01db4906155b7d0c25a0ca04b768",
    "Application": "833a7c98ae9c2450ff0d51c7698c75848d6896e1",
    "EntityFrameworkCore": "0db02503a7fb2616bd839ab8fec79eb63099a8d9",
    "Core": "77391fdb5bfc50838867d7daf6b3211b45323303",
    "Migrator": "c5fc624b5e8c70dc19a1180e50c7008e4512acd2",
}


def runtime_patch(root, preimages=RUNTIME_PATCH_PREIMAGES):
    patches, projects = [], {}
    for name in TOPOLOGY:
        relative = project_path(name)
        before = (root / relative).read_bytes()
        blob = git_blob(before)
        require(blob == preimages[name], f"{relative} 换包后 Git blob 不符：{blob}")
        old = b"<TargetFramework>net9.0</TargetFramework>"
        require(before.count(old) == 1, f"{relative} 缺少唯一的 net9.0 声明")
        after = before.replace(old, f"<TargetFramework>{TFM}</TargetFramework>".encode())
        references = DIRECT_MICROSOFT.get(name, ())
        for package in references:
            old = f'Include="{package}" Version="9.0.5"'.encode()
            new = f'Include="{package}" Version="{PATCH_VERSION}"'.encode()
            require(after.count(old) == 1, f"{relative} 缺少唯一的 {package}/9.0.5 声明")
            after = after.replace(old, new)
        patches.append(project_diff(relative, before, after))
        projects[relative.as_posix()] = {
            "beforeGitBlob": blob, "beforeSha256": bytes_sha256(before),
            "afterGitBlob": git_blob(after), "afterSha256": bytes_sha256(after), "targetFramework": TFM,
            "microsoftReferences": {package: PATCH_VERSION for package in references},
        }
    return "".join(patches), projects


def verify_resolved_versions(name, graph):
    versions = {key.split("/")[0]: key.split("/")[1] for key, row in graph.items() if row["type"] == "package"}
    required = set(DIRECT_MICROSOFT.get(name, ()))
    if name in (*ENTRIES, "EntityFrameworkCore"):
        required.update(EF_RUNTIME)
    expected = {package: PATCH_VERSION
                for package in (*EF_RUNTIME, f"{EF}.Analyzers", DESIGN, TOOLS, JWT,
                                "Microsoft.AspNetCore.Mvc.NewtonsoftJson",
                                "Microsoft.AspNetCore.Mvc.Razor.RuntimeCompilation")}
    expected.update(SQL_CLIENT_VERSIONS)
    if PROVIDER in versions:
        required.update(SQL_CLIENT_VERSIONS)
    for package, version in expected.items():
        if package in required or package in versions:
            actual = versions.get(package)
            require(actual == version, f"{name} {package} 预期 {version}，实际 {actual}")


def sql_server_chain(name, target, output, cache):
    packages = {row["id"]: (key, row) for key, row in target["packages"].items()}
    provider_key, provider = packages[PROVIDER]
    dependencies = provider["dependencies"]
    require({SQL_CLIENT, f"{EF}.Relational"} <= dependencies.keys(),
            f"{name} {provider_key} 缺少 SqlClient 或 Relational 依赖边：{dependencies}")
    pending = [PROVIDER]
    chain = {}
    while pending:
        id_ = pending.pop()
        key, package = packages[id_]
        if key not in chain:
            chain[key] = package["dependencies"]
            pending.extend(package["dependencies"])

    runtime = output["packageCopies"]
    references = target["compileReferences"]
    assemblies = {}
    for id_ in (*EF_RUNTIME, SQL_CLIENT):
        key, package = packages[id_]
        filename = f"{id_}.dll"
        candidates = references.get(filename, [])
        require(len(candidates) == 1 and candidates[0].get("package") == key,
                f"{name} {key} 缺少唯一编译引用 {filename}：{candidates}")
        reference = candidates[0]
        _, digest = archive_asset(cache, package, reference["packageAsset"])
        require(digest == reference["sha256"], f"{name} {key} 编译引用摘要不符：{reference}")
        copies = {path: row for path, row in runtime.items() if Path(path).name == filename}
        require(filename in copies and all(row["package"] == key for row in copies.values()),
                f"{name} {key} 运行文件缺失或来源冲突：{copies}")
        assemblies[id_] = {"package": key, "compileReference": reference, "runtimeCopies": copies}

    return {"provider": provider_key, "resolvedDependencies": chain, "assemblies": assemblies,
            "dependencyRuntimeCopies": {path: row for path, row in runtime.items() if row["package"] in chain}}


def migrator_pkcs_platform_runtime(target, items, cache):
    # Pkcs 由 NuGet 提供编译 DLL，SDK 平台清单指向共享运行时的同名 DLL。
    package_key = f"{PKCS}/10.0.13"
    filename = f"{PKCS}.dll"
    package = target["packages"][package_key]
    references = target["compileReferences"].get(filename, [])
    require(len(references) == 1 and references[0].get("package") == package_key,
            f"Migrator {package_key} 的编译引用不符：{references}")
    reference = references[0]
    _, digest = archive_asset(cache, package, reference["packageAsset"])
    require(digest == reference["sha256"], f"Migrator {package_key} 编译引用摘要不符：{reference}")
    discarded = {asset: str(cache / package["cachePath"] / asset)
                 for section in ("runtime", "runtimeTargets") for asset in package["assets"].get(section, {})}
    conflicts = {item["FullPath"] for item in items["_ConflictPackageFiles"] if item.get("NuGetPackageId") == PKCS}
    require(reference["packageAsset"] in discarded and set(discarded.values()) == conflicts,
            f"Migrator {package_key} 无对应 SDK 运行复制剔除记录：{conflicts}")
    pack = target["sdkUsedPacks"]["Microsoft.AspNetCore.App"]
    manifest = Path(pack["location"]) / "data/PlatformManifest.txt"
    require(pack["version"] == PATCH_VERSION
            and str(manifest) in {item["FullPath"] for item in items["PackageConflictPlatformManifests"]},
            f"Migrator {package_key} 无对应 SDK 平台清单：{manifest}")
    entries = [line.split("|") for line in manifest.read_text().splitlines() if line.startswith(filename + "|")]
    require(len(entries) == 1 and entries[0][1] == pack["id"],
            f"Migrator {package_key} 在 SDK 平台清单中无唯一来源：{entries}")
    return {package_key: {filename: {
        "framework": "Microsoft.AspNetCore.App", "compileReference": reference,
        "platformManifest": artifact(manifest, Path(pack["location"])), "platformManifestPath": str(manifest),
        "platformEntry": entries[0], "discardedCopies": discarded,
    }}}


class UpgradeBuildRun(CandidateRun):
    profile = PROFILE
    tfm = TFM
    deps_target = DEPS_TARGET
    upgrade_core = True
    runtime_patch_preimages = RUNTIME_PATCH_PREIMAGES
    planning_commit = "a4ffcaa83a48bb8c7684264ca6aad0d82faf63ae"
    planning_tree = "366e598c95b33f037be23b738895a335689fbfe2"

    def materialize(self):
        super().materialize()
        package_patch = self.evidence / "template-package-references.patch"
        apply = ["git", "apply", "--no-index"]
        self.command([*apply, "--reverse", package_patch], self.root.parent, "package-patch-rewind.log")
        self.command([*apply, "--check", package_patch], self.root.parent, "package-patch-check.log")
        self.command([*apply, package_patch], self.root.parent, "package-patch-replay.log")
        patch, projects = runtime_patch(self.root, self.runtime_patch_preimages)
        path = self.evidence_file("template-runtime-upgrade.patch")
        path.write_text(patch, encoding="utf-8")
        self.command([*apply, "--check", path], self.root.parent, "runtime-patch-check.log")
        self.command([*apply, path], self.root.parent, "runtime-patch-replay.log")
        for relative, row in projects.items():
            require(artifact(self.root / relative, self.root)["sha256"] == row["afterSha256"],
                    f"{relative} 重放运行时补丁后摘要不符")
        write_json(self.evidence_file("template-upgrade-projects.json"), {
            "projects": projects, "patches": [artifact(item, self.evidence) for item in (package_patch, path)],
        })

    def read_target(self, name, saved, lookup):
        raw = read_json(saved)
        graphs = raw["targets"]
        require(set(graphs) == {TFM}, f"{name} 预期唯一还原目标 {TFM}，实际 {list(graphs)}")
        verify_resolved_versions(name, graphs[TFM])
        pruned_edges = {}
        if name == "Web.Host":
            pruned = raw["project"]["frameworks"][TFM]["packagesToPrune"]
            for package, dependencies in PRUNED_MAINTENANCE_EDGES.items():
                for dependency, declared in dependencies.items():
                    require(self.frozen[package]["dependencies"][dependency] == declared
                            and pruned.get(dependency) == f"(,{PRUNE_MAXIMUM}]",
                            f"{name} {package} → {dependency} 的归档版本或 SDK 裁剪范围不符")
                pruned_edges[package] = {
                    dependency: {"declaredVersion": declared, "prunedRange": pruned[dependency]}
                    for dependency, declared in dependencies.items()
                }
        target = super().read_target(name, saved, lookup, pruned_edges=pruned_edges)
        target["prunedMaintenanceDependencies"] = pruned_edges
        require(all(target["directPackages"][package]["declaration"]["version"] == PATCH_VERSION
                    for package in DIRECT_MICROSOFT.get(name, ())), f"{name} Microsoft 直接声明版本不符")
        return target

    def read_output(self, name, output, target, items):
        platform_runtime = migrator_pkcs_platform_runtime(target, items, self.cache) if name == "Migrator" else None
        result = super().read_output(name, output, target, items, platform_runtime=platform_runtime)
        config = result["runtimeOptions"]
        expected = {"Microsoft.NETCore.App": "10.0.0", "Microsoft.AspNetCore.App": "10.0.0"}
        require({row["name"]: row["version"] for row in config["frameworks"]} == expected,
                f"{name} 共享框架起始版本预期 {expected}，实际 {config['frameworks']}")
        if pruned_edges := target["prunedMaintenanceDependencies"]:
            prune_log = self.run_dotnet(
                ["msbuild", project_path(name), "-nologo", "-p:Configuration=Release",
                 "-target:CollectPrunePackageReferences", "-getItem:PrunePackageReference"],
                f"{name}-pruning-selection.log")
            sdk = {item["Identity"]: item["Version"]
                   for item in read_json(prune_log)["Items"]["PrunePackageReference"]}
            for dependencies in pruned_edges.values():
                for dependency, details in dependencies.items():
                    references = target["compileReferences"].get(f"{dependency}.dll", [])
                    require(sdk.get(dependency) == PRUNE_MAXIMUM and len(references) == 1
                            and references[0].get("frameworkReference") == "Microsoft.AspNetCore.App",
                            f"{name} {dependency} 缺少 SDK 裁剪和共享框架编译来源：{references}")
                    details["compileReference"] = references[0]
        result["sqlServerChain"] = sql_server_chain(name, target, result, self.cache)
        return result


def execute(args):
    run = UpgradeBuildRun(ROOT, make_run_directory(args.evidence_root, PROFILE + "-"), args.frozen_root.resolve(),
                          args.dotnet)
    print(f"{PROFILE} report: {run.report_path}", flush=True)
    return run.execute_build()
