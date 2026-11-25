"""从冻结维护包还原、构建并核对固定 net9.0 模板。"""

from datetime import datetime, timezone
from difflib import unified_diff
import hashlib
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from r2_packages import metadata_groups, nuspec_metadata, version_range
from r3_automapper_packages import stack_package
from r3_leaf_packages import bytes_sha256, checked_file
from r3_module_zero_assets import runtime_packages
from r3_template_runtime import inventory
from r3_web_host import (
    ABP_VERSION, DEPS_TARGET, DIRECT_ABP, INPUTS, NUGET_SOURCE, PROJECTS, PROVIDER, R3Run, TEMPLATE, TFM,
    artifact, check_runtime_declarations, expected_projects, inside, package_hashes, project_path,
    read_project, read_sdk_packs, runtime_selection, write_json,
)
from verify import ROOT, VerificationError, make_run_directory, read_json, require, sha256


PROFILE = "r3-template-net9-packages"
PLANNING_COMMIT = "148bda55d9fea121a66fa2445388fb0cf552643b"
PLANNING_TREE = "49a886ca76231c51521327cd85a3581f24adcefe"
ENTRIES = ("Web.Host", "Migrator")
TOPOLOGY = {**PROJECTS, "Migrator": ("Core", "EntityFrameworkCore")}
REPLACEMENTS = {**DIRECT_ABP, "Migrator": {"Abp.Castle.Log4Net"}}
PREIMAGES = {
    "Web.Host": "e044651c24aad5691fe65e682db547c50e0dcd66",
    "Web.Core": "a7be79e8a57e525cba6c13c3efd7d4d9b875dfa1",
    "Core": "be28ccded3ea0b37367cb54fa88e0afd3c911cb0",
    "Migrator": "c91c58b199dbcc742b360dbf0a0c401e9aa5a8e4",
}
STAGES = ("preflight", "packages", "materialize", "sdk", "restore", "assets", "build", "output", "inputs_after")


def selected_archive(row, root, *, upgrade_core=False):
    path = checked_file(root, row["archive"], row["archiveSha256"])
    with ZipFile(path) as archive:
        metadata = nuspec_metadata(archive)
        require((metadata.findtext("id"), metadata.findtext("version")) == (row["id"], row["version"]),
                f"{path} nuspec ID 或版本不符")
        require(metadata.find("repository").get("url") == row["repository"],
                f"{path} nuspec 仓库不符")
        asset = row["asset"]
        require(archive.namelist().count(asset) == 1 and bytes_sha256(archive.read(asset)) == row["assetSha256"],
                f"{path} 选中资产 {asset} 缺失、重名或摘要不符")
        if upgrade_core and row["batch"] == "r2":
            asset = f"lib/net10.0/{Path(asset).name}"
            require(archive.namelist().count(asset) == 1, f"{path} 缺少唯一的升级资产 {asset}")
            row = {**row, "asset": asset, "assetSha256": bytes_sha256(archive.read(asset))}
        require(not metadata.findall("dependencies/dependency"), f"{path} nuspec 有未分组依赖")
        group = metadata_groups(metadata, "dependencies", "id")[Path(asset).parts[1]]
        return path, row, {id_: item["version"] for id_, item in group.items()}


def normalized_range(value):
    value = version_range(value)
    if value.startswith("[") and value.endswith("]") and "," not in value:
        return f"[{value[1:-1]},{value[1:-1]}]"
    return value


def original_package(name):
    return stack_package(name) and not name.casefold().startswith("du.")


def git_blob(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def project_diff(relative, before, after):
    label = f"aspnet-core/{relative.as_posix()}"
    lines = unified_diff(before.decode().splitlines(keepends=True), after.decode().splitlines(keepends=True),
                         f"a/{label}", f"b/{label}")
    return "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in lines)


def project_changes(root, frozen):
    differences = []
    for name, packages in REPLACEMENTS.items():
        relative = project_path(name)
        path = root / relative
        before = path.read_bytes()
        blob = git_blob(before)
        require(blob == PREIMAGES[name], f"{relative} 固定 Git blob 不符：{blob}")
        after = before
        for package in sorted(packages):
            old = f'Include="{package}" Version="{ABP_VERSION}"'.encode()
            new = f'Include="Du.{package}" Version="[{frozen[f"Du.{package}"]["version"]}]"'.encode()
            require(after.count(old) == 1, f"{relative} 预期唯一引用 {package} {ABP_VERSION}")
            after = after.replace(old, new)
        path.write_bytes(after)
        differences.append(project_diff(relative, before, after))
    return "".join(differences)


def source_config(path, feed, packages):
    document = ET.Element("configuration")
    sources = ET.SubElement(document, "packageSources")
    ET.SubElement(sources, "clear")
    ET.SubElement(sources, "add", key="frozen", value=str(feed))
    ET.SubElement(sources, "add", key="nuget.org", value=NUGET_SOURCE)
    mapping = ET.SubElement(document, "packageSourceMapping")
    ET.SubElement(mapping, "clear")
    local = ET.SubElement(mapping, "packageSource", key="frozen")
    public = ET.SubElement(mapping, "packageSource", key="nuget.org")
    for name in sorted(packages):
        ET.SubElement(local, "package", pattern=name)
    ET.SubElement(public, "package", pattern="*")
    ET.SubElement(ET.SubElement(document, "fallbackPackageFolders"), "clear")
    ET.indent(document, space="  ")
    ET.ElementTree(document).write(path, encoding="utf-8", xml_declaration=True)

def verify_project_packages(name, target, frozen, *, pruned_edges=None):
    projects = expected_projects(name, TOPOLOGY) | {project_path(name).as_posix()}
    expected = set()
    pending = [f"Du.{package}" for project, packages in REPLACEMENTS.items()
               if project_path(project).as_posix() in projects for package in packages]
    while pending:
        package = pending.pop()
        if package not in expected:
            expected.add(package)
            pending.extend(dep for dep in frozen[package]["dependencies"] if stack_package(dep))

    actual = {package["id"]: key for key, package in target["packages"].items() if stack_package(package["id"])}
    require(actual.keys() == expected,
            f"维护包闭包不符，缺少 {sorted(expected - actual.keys())}，多出 {sorted(actual.keys() - expected)}")
    for package, key in actual.items():
        registered, selected = frozen[package], target["packages"][key]
        require(key == f"{package}/{registered['version']}" and
                selected["archive"]["sha256"] == registered["archiveSha256"],
                f"{key} 缓存版本或归档 SHA-256 与冻结实物不符")
        declared = {dep: normalized_range(version) for dep, version in registered["dependencies"].items()}
        for dependency in (pruned_edges or {}).get(package, ()):
            del declared[dependency]
        resolved = {dep: normalized_range(version) for dep, version in selected["dependencies"].items()}
        require(declared == resolved, f"{key} 还原边与 nuspec 不符，预期 {declared}，实际 {resolved}")
        asset = registered["asset"]
        for section in ("compile", "runtime"):
            owners = [(entry, path) for entry, row in target["packages"].items()
                      for path in row["assets"].get(section, {}) if Path(path).name == Path(asset).name]
            require(owners == [(key, asset)] and set(selected["assets"].get(section, {})) == {asset},
                    f"{key} {section} 应唯一选中 {asset}，实际 {owners}")
    for package, declaration in target["directPackages"].items():
        if stack_package(package):
            version = frozen[package]["version"]
            require(normalized_range(declaration["version"]) == f"[{version},{version}]",
                    f"{package} 还原声明未锁到精确版本 {version}")


def project_package_changes(original, candidate):
    original_graph = original["targets"][TFM]
    candidate_graph = candidate["projects"] | candidate["packages"]
    original_keys = {key.split("/")[0].casefold(): key for key, item in original_graph.items()
                     if item["type"] == "package"}
    candidate_keys = {item["id"].casefold(): key for key, item in candidate["packages"].items()}

    original_framework = original["project"]["frameworks"][TFM].get("dependencies", {})
    original_entry = f"{original['project']['restore']['projectName']}/{original['project']['version']}"
    original_graph = {**original_graph, original_entry: {"dependencies": {
        name: row["version"] for name, row in original_framework.items() if row["target"] == "Package"
    }}}
    candidate_graph[candidate["entryProject"]] = {"dependencies": {
        name: row["version"] for name, row in candidate["directPackages"].items()
    }}

    def parents(graph, package):
        return {key: value for key, node in graph.items()
                for dep, value in node.get("dependencies", {}).items() if dep.casefold() == package}

    changes = {}
    for name in sorted(original_keys.keys() | candidate_keys.keys()):
        if name in ("abp", "du.abp") or name.startswith(("abp.", "du.abp.")):
            continue
        before, after = original_keys.get(name), candidate_keys.get(name)
        old_parents, new_parents = parents(original_graph, name), parents(candidate_graph, name)
        if before != after or old_parents != new_parents:
            changes[name] = {"original": before, "candidate": after,
                             "originalRequestedBy": old_parents, "candidateRequestedBy": new_parents}
    return changes


def archive_asset(cache, package, asset):
    restored = inside(cache, Path(package["cachePath"]) / asset)
    with ZipFile(inside(cache, package["archive"]["path"])) as archive:
        require(archive.namelist().count(asset) == 1, f"{package['id']} 归档缺少唯一 {asset}")
        digest = bytes_sha256(archive.read(asset))
    require(restored.is_file() and sha256(restored) == digest,
            f"{package['id']} 还原资产 {asset} 与归档 SHA-256 不符：{restored}")
    return restored, digest


def compile_records(items, target, frozen, cache, root, *, tfm=TFM):
    references = {}
    for item in items["ReferencePathWithRefAssemblies"]:
        path = Path(item["FullPath"]).resolve()
        require(path.is_file(), f"编译参考不存在：{path}")
        record = {"path": str(path), "sha256": sha256(path)}
        if framework := item.get("FrameworkReferenceName"):
            pack = target["sdkUsedPacks"].get(framework)
            require(pack and path.is_relative_to(Path(pack["location"]) / "ref" / tfm),
                    f"未登记的 SDK 编译参考：{framework} {path}")
            record["frameworkReference"] = framework
        elif item.get("ReferenceSourceTarget") == "ProjectReference":
            source = Path(item["MSBuildSourceProjectFile"]).resolve()
            require(source.relative_to(root).as_posix() in {row["project"] for row in target["projects"].values()}
                    and path.is_relative_to(source.parent), f"编译参考无对应项目：{source} {path}")
            record["projectReference"] = str(source)
        elif package := item.get("NuGetPackageId"):
            key = f"{package}/{item['NuGetPackageVersion']}"
            require(key in target["packages"], f"编译参考无对应还原包：{key} {path}")
            row = target["packages"][key]
            relative = path.relative_to(inside(cache, row["cachePath"])).as_posix()
            require(relative in row["assets"].get("compile", {}), f"{key} 未选中编译资产 {relative}")
            record.update(package=key, packageAsset=relative)
        else:
            raise VerificationError(f"编译参考没有可识别的来源：{path}")
        references.setdefault(path.name, []).append(record)

    for key, row in target["packages"].items():
        if row["id"] in frozen:
            expected = frozen[row["id"]]
            path, digest = archive_asset(cache, row, expected["asset"])
            want = {"path": str(path), "sha256": expected["assetSha256"], "package": key,
                    "packageAsset": expected["asset"]}
            require(digest == expected["assetSha256"] and references.get(path.name) == [want],
                    f"{key} 缺少唯一编译参考 {path.name}：{references.get(path.name)}")
    return references


def check_entry_output(name, output, target, items, frozen, cache, *, tfm=TFM, deps_target=DEPS_TARGET,
                       platform_runtime=None):
    dll = output / (project_path(name).stem + ".dll")
    deps_file = dll.with_suffix(".deps.json")
    runtime_config_file = dll.with_suffix(".runtimeconfig.json")
    deps = read_json(deps_file)
    require(deps["runtimeTarget"]["name"] == deps_target and set(deps["targets"]) == {deps_target},
            f"{deps_file} 运行目标不符")
    graph, libraries = deps["targets"][deps_target], deps["libraries"]
    require(graph.keys() == libraries.keys(), f"{deps_file} 目标与库表集合不符")
    config = read_json(runtime_config_file)["runtimeOptions"]
    require(config["tfm"] == tfm, f"{runtime_config_file} 运行目标不符")
    selection = runtime_selection(items, target, cache)
    retained, omitted = runtime_packages(libraries, target, selection, items, cache=cache,
                                         platform_runtime=platform_runtime)
    excluded = {key.split("/")[0] for key in omitted}
    deps_target = {**target, "packages": retained, "sdkRuntimeSelection": selection,
                   "directPackages": {key: node for key, node in target["directPackages"].items() if key not in excluded},
                   "projects": {key: {**row, "dependencies": {dep: value for dep, value in row["dependencies"].items()
                                                              if dep not in excluded}}
                                for key, row in target["projects"].items()}}
    for key, node in graph.items():
        if node.get("compileOnly"):
            require(not any(node.get(section) for section in ("runtime", "native", "resources", "runtimeTargets")),
                    f"{deps_file} 仅编译条目带运行资产：{key}")
    runtime_outputs = check_runtime_declarations(output, output.rglob("*.dll"), graph, libraries, deps_target)
    project_copies = {}
    for key, row in target["projects"].items():
        filename = key.split("/")[0] + ".dll"
        project = next((item for item in items["ReferencePath"]
                        if item.get("ReferenceSourceTarget") == "ProjectReference"
                        and Path(item["FullPath"]).name == filename), None)
        require(project is not None, f"{filename} 缺少已解析的项目输出引用")
        origin = Path(project["FullPath"]).resolve()
        require(filename in runtime_outputs and sha256(output / filename) == sha256(origin),
                f"{filename} 的入口复制结果与项目产物 SHA-256 不符：{origin}")
        project_copies[filename] = {"project": row["project"], "sourcePath": str(origin),
                                    **artifact(output / filename, output)}
    copies = {}
    for key, sections in selection.items():
        row = target["packages"][key]
        for section, assets in sections.items():
            for asset, selection_record in assets.items():
                path, digest = archive_asset(cache, row, asset)
                destination = inside(output, selection_record["outputPath"])
                actual = sha256(destination)
                require(actual == digest, f"{key} 的运行输出与归档 SHA-256 不符：{destination}，"
                        f"预期 {digest}，实际 {actual}")
                copies[selection_record["outputPath"]] = {**selection_record, "cachePath": str(path),
                                                           "package": key, "packageAsset": asset,
                                                           "sha256": digest, "section": section}
    maintenance = {}
    for key, row in target["packages"].items():
        if row["id"] in frozen:
            registered = frozen[row["id"]]
            filename = Path(registered["asset"]).name
            record = copies.get(filename)
            require(record and (record["package"], record["packageAsset"], record["sha256"]) ==
                    (key, registered["asset"], registered["assetSha256"]),
                    f"{key} 运行 DLL 来源或摘要不符：{filename} {record}")
            maintenance[filename] = record
    providers = [dest for dest, row in copies.items() if row["package"].split("/")[0] == PROVIDER
                 and Path(dest).name == PROVIDER + ".dll"]
    require(len(providers) == 1, f"{name} 缺少唯一的 SQL Server Provider 运行资产：{providers}")
    return {"entry": artifact(dll, output), "deps": artifact(deps_file, output),
            "runtimeConfig": artifact(runtime_config_file, output), "runtimeOptions": config,
            "files": inventory(output), "maintenanceDlls": maintenance, "packageCopies": copies,
            "projectCopies": project_copies,
            "sqlServerProvider": copies[providers[0]], "omittedRuntimePackages": omitted,
            "depsCompileOnly": sorted(key for key, node in graph.items() if node.get("compileOnly"))}


class CandidateRun(R3Run):
    profile = PROFILE
    tfm = TFM
    deps_target = DEPS_TARGET
    upgrade_core = False
    planning_commit = PLANNING_COMMIT
    planning_tree = PLANNING_TREE

    def __init__(self, repo, evidence, frozen_root, dotnet=None):
        super().__init__(repo, evidence)
        self.frozen_root = frozen_root
        self.feed = (evidence / "frozen-feed").resolve()
        self.original_hashes = {}
        self.frozen = {}
        if dotnet:
            self.dotnet = dotnet
        self.report.update(profile=self.profile, coverageNotRun=["共享运行时与实际加载", "数据库与浏览器业务验证"],
                           stages={stage: {"status": "not_run", "exitCode": None, "commands": [], "evidence": []}
                                   for stage in STAGES})
        self.output = self.root / self.entry.parent / f"bin/Release/{self.tfm}"
        self.report["inputs"].update(planningCommit=self.planning_commit, planningTree=self.planning_tree,
                                     targetFramework=self.tfm)
        self.save()

    def preflight(self):
        super().preflight()
        self.git_tree(self.repo, "candidate-planning", self.planning_commit, self.planning_tree)
        expected = ["160000", "commit", INPUTS[TEMPLATE][0], TEMPLATE]
        for revision in dict.fromkeys((self.planning_commit, self.report["inputs"]["executionCommit"])):
            actual = self.git(self.repo, f"template-gitlink-{revision[:12]}.log", "ls-tree", revision, "--", TEMPLATE)
            require(actual.split() == expected, f"{revision} 模板 gitlink 不符：{actual}")

    def packages(self):
        reference = self.repo / "eng/r3_template_net9_reference.json"
        self.report["inputs"]["frozenRegistration"] = {"path": str(reference), "sha256": sha256(reference)}
        registration_data = read_json(reference)
        self.original_assets = registration_data["originalAssets"]
        batches = registration_data["batches"]
        self.feed.mkdir()
        for batch, registration in batches.items():
            manifests = {}
            for label, record in registration["manifests"].items():
                path = checked_file(self.frozen_root, record["path"], record["sha256"])
                self.original_hashes[path] = record["sha256"]
                manifests[label] = {"path": str(path), "sha256": record["sha256"]}
            for row in registration["packages"]:
                name = row["id"]
                require(name not in self.frozen, f"{batch} 冻结包重复：{name}")
                label = {"Du.AutoMapper": "engine", "Du.AutoMapper.Collection": "collection"}.get(name, "framework")
                row = {**row, "batch": batch, "repository": registration["sources"][label], "manifests": manifests}
                path, row, dependencies = selected_archive(row, self.frozen_root, upgrade_core=self.upgrade_core)
                self.original_hashes[path] = row["archiveSha256"]
                target = self.feed / path.name
                shutil.copyfile(path, target)
                checked_file(self.feed, target.name, row["archiveSha256"])
                self.frozen[name] = {**row, "original": str(path), "feedCopy": str(target),
                                     "dependencies": dependencies, "assembly": Path(row["asset"]).stem}
        require(len(self.frozen) == 13 and sum(name.startswith("Du.Abp") for name in self.frozen) == 11,
                f"冻结包集合不符：{sorted(self.frozen)}")
        for name, row in self.frozen.items():
            for dependency, version in row["dependencies"].items():
                if stack_package(dependency):
                    require(dependency in self.frozen, f"{name} nuspec 引用了未登记的 {dependency}")
                    resolved = self.frozen[dependency]["version"]
                    expected = f"[{resolved},)" if row["batch"] == "r2" else f"[{resolved},{resolved}]"
                    require(normalized_range(version) == expected,
                            f"{name} → {dependency} 范围不符，预期 {expected}，实际 {version}")
        write_json(self.evidence_file("frozen-packages.json"), self.frozen)

    def materialize(self):
        super().materialize()
        inventory_path = self.evidence / "source-inventory.json"
        source_records = read_json(inventory_path)
        source_records["projects"].append(artifact(self.root / project_path("Migrator"), self.root.parent))
        write_json(inventory_path, source_records)
        patch = project_changes(self.root, self.frozen)
        patch_path = self.evidence_file("template-package-references.patch")
        patch_path.write_text(patch, encoding="utf-8")
        self.command(["git", "apply", "--no-index", "--check", "--reverse", patch_path],
                     self.root.parent, "template-patch-replay-check.log")
        source_config(self.config, self.feed, self.frozen)
        self.report["inputs"]["nuget"].update(effective=artifact(self.config, self.evidence),
                                             effectiveSources=[str(self.feed), NUGET_SOURCE])

    def restore(self):
        for name in ENTRIES:
            self.entry = project_path(name)
            try:
                self.run_dotnet(["restore", self.entry, "--configfile", self.config, "--no-http-cache",
                                 "--force", "-p:Configuration=Release", "--verbosity", "normal"], f"{name}-restore.log")
            finally:
                log = self.evidence / f"{name}-restore.log"
                if log.is_file():
                    self.record_diagnostics(log)
                    self.stage.setdefault("entries", {})[name] = self.stage.pop("diagnostics")

    def read_target(self, name, saved, lookup, *, pruned_edges=None):
        managed = {f"Du.{package}" for package in REPLACEMENTS.get(name, ())}
        target = read_project(self.root, name, saved, self.cache, self.config, lookup, topology=TOPOLOGY,
                              sources=(str(self.feed), NUGET_SOURCE), managed=stack_package,
                              managed_versions={package: f"[{self.frozen[package]['version']}]"
                                                for package in managed}, forbidden=original_package,
                              tfm=self.tfm, deps_target=self.deps_target)
        verify_project_packages(name, target, self.frozen, pruned_edges=pruned_edges)
        return target

    def inventory(self):
        raw_assets = self.evidence / "raw-assets"
        raw_assets.mkdir()
        self.asset_paths, self.assets = {}, {}
        differences, cache_records = {}, {}

        def lookup(key, relative):
            if (key, relative) not in cache_records:
                source = str(self.feed) if stack_package(key.split("/")[0]) else NUGET_SOURCE
                cache_records[key, relative] = package_hashes(self.cache, key, relative, source)
            return cache_records[key, relative]

        for name in TOPOLOGY:
            project = project_path(name)
            self.asset_paths[name] = path = self.root / project.parent / "obj/project.assets.json"
            saved = self.evidence_file(f"raw-assets/{name}.project.assets.json")
            try:
                shutil.copyfile(path, saved)
                self.report.setdefault("rawAssets", {})[name] = artifact(saved, self.evidence)
                target = self.read_target(name, saved, lookup)
                self.assets[name] = target
                original_record = self.original_assets[name]
                original = checked_file(self.frozen_root, original_record["path"], original_record["sha256"])
                self.original_hashes[original] = original_record["sha256"]
                original_data = read_json(original)
                original_packages = {key: value for key, value in original_data["targets"][TFM].items()
                                     if value["type"] == "package"}
                candidate_packages = target["packages"]
                differences[name] = {
                    "originalAsset": {"path": str(original), "sha256": original_record["sha256"]},
                    "packages": project_package_changes(original_data, target),
                    "versions": {
                        "original": {key.split("/")[0]: key.split("/")[1] for key in sorted(original_packages)},
                        "candidate": {value["id"]: value["version"] for value in candidate_packages.values()},
                    },
                }
            except (OSError, ValueError, KeyError, TypeError, VerificationError) as error:
                raise VerificationError(f"{project} {self.tfm}：{error}") from error
        write_json(self.evidence_file("assets-inventory.json"), self.assets)
        write_json(self.evidence_file("third-party-differences.json"), differences)

    def build(self):
        for name in ENTRIES:
            entry = project_path(name)
            self.run_dotnet(["build", entry, "--configuration", "Release", "--no-restore",
                             "--disable-build-servers", "-p:UseSharedCompilation=false", "--verbosity", "minimal",
                             f"-bl:{self.evidence_file(f'{name}-build.binlog')}"], f"{name}-build.log")
            self.record_diagnostics(self.evidence / f"{name}-build.log")
            self.stage.setdefault("entries", {})[name] = self.stage.pop("diagnostics")
            for project, path in self.asset_paths.items():
                require(sha256(path) == self.report["rawAssets"][project]["sha256"],
                        f"构建改写了 {project} 还原图：{path}")

    def read_output(self, name, output, target, items, *, platform_runtime=None):
        return check_entry_output(name, output, target, items, self.frozen, self.cache,
                                  tfm=self.tfm, deps_target=self.deps_target, platform_runtime=platform_runtime)

    def inspect_output(self):
        launch = {}
        for name in TOPOLOGY:
            project = project_path(name)
            target = self.assets[name]
            try:
                sdk_log = self.run_dotnet(
                    ["msbuild", project, "-nologo", "-p:Configuration=Release",
                     "-target:ResolveTargetingPackAssets;_GetAppHostPaths",
                     "-getItem:FrameworkReference,ResolvedTargetingPack,ResolvedAppHostPack,ResolvedAnalyzers",
                     "-getProperty:AppHostSourcePath,NetCoreTargetingPackRoot"], f"{name}-sdk-packs.log")
                sdk = read_json(sdk_log)
                target["sdkUsedPacks"] = read_sdk_packs(sdk, target, self.cache, self.pack_root, name in ENTRIES,
                                                        tfm=self.tfm)
                target["selectedPackageAnalyzers"] = [
                    artifact(Path(item["FullPath"]).resolve(), self.cache) for item in sdk["Items"]["ResolvedAnalyzers"]
                ]
                references = self.run_dotnet(
                    ["msbuild", project, "-nologo", "-p:Configuration=Release",
                     "-target:ResolveReferences;FindReferenceAssembliesForReferences",
                     "-getItem:ReferencePath,ReferencePathWithRefAssemblies"], f"{name}-compile-selection.log")
                items = read_json(references)["Items"]
                target["compileReferences"] = compile_records(
                    items, target, self.frozen, self.cache, self.root, tfm=self.tfm)
                if name in ENTRIES:
                    copies = self.run_dotnet(
                        ["msbuild", project, "-nologo", "-p:Configuration=Release",
                         "-target:ResolveLockFileCopyLocalFiles;_HandlePackageFileConflicts",
                         "-getItem:ReferenceCopyLocalPaths,_ConflictPackageFiles,PackageConflictPlatformManifests"],
                        f"{name}-runtime-selection.log")
                    items.update(read_json(copies)["Items"])
                    output = self.root / project.parent / f"bin/Release/{self.tfm}"
                    result = self.read_output(name, output, target, items)
                    result_file = self.evidence_file(f"{name}-output.json")
                    write_json(result_file, result)
                    command = [str(self.dotnet), str(output / result["entry"]["path"])]
                    if name == "Migrator":
                        command.append("-q")
                    launch[name] = {"cwd": str(output), "argv": command, "status": "not_run",
                                    "outputVerification": artifact(result_file, self.evidence)}
                    if name == "Web.Host":
                        launch[name]["environment"] = {"ASPNETCORE_ENVIRONMENT": "Development",
                                                       "DOTNET_ENVIRONMENT": "Development"}
            except (KeyError, ValueError, VerificationError, OSError) as error:
                raise VerificationError(f"{project} {self.tfm} 输出核对失败：{error}") from error
        write_json(self.evidence_file("assets-inventory.json"), self.assets)
        write_json(self.evidence_file("launch-manifest.json"), launch)

    def build_steps(self):
        return zip(STAGES, (self.preflight, self.packages, self.materialize, self.toolchain, self.restore,
                            self.inventory, self.build, self.inspect_output, self.inputs_after), strict=True)

    def execute_build(self):
        stage = STAGES[0]
        try:
            for stage, action in self.build_steps():
                self.step(stage, action)
        except (VerificationError, OSError, ValueError, KeyError, TypeError, ET.ParseError, BadZipFile) as error:
            self.report["stages"][stage].update(status="failed", exitCode=1, reason=str(error))
            self.report.update(status="failed", exitCode=1, reason=str(error))
            for step in self.report["stages"].values():
                if step["status"] == "not_run":
                    step["reason"] = f"{stage} 未通过"
            print(f"{self.profile} 构建核验失败：{error}", file=sys.stderr)
        else:
            self.report.update(status="build_verified", exitCode=0)
        self.report["finishedAt"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return self.report["exitCode"]

    def inputs_after(self):
        unchanged = {}
        for path, expected in self.original_hashes.items():
            checked_file(self.frozen_root, path, expected)
            unchanged[str(path)] = expected
        for package in self.frozen.values():
            path = checked_file(self.feed, package["feedCopy"], package["archiveSha256"])
            unchanged[str(path)] = package["archiveSha256"]
        write_json(self.evidence_file("inputs-after.json"), unchanged)


def execute(args):
    run = CandidateRun(ROOT, make_run_directory(args.evidence_root, PROFILE + "-"), args.frozen_root.resolve(),
                       args.dotnet)
    print(f"{PROFILE} report: {run.report_path}", flush=True)
    return run.execute_build()
