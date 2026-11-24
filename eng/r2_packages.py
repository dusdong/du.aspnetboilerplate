"""核对实际 R2 包、PE 元数据和 R1 同目标产物。"""

import hashlib
import json
from pathlib import Path
import re
import tarfile
import xml.etree.ElementTree as ET
import zipfile
import zlib

from r1_restore_inventory import NUGET_SOURCE
from inventory import compare_api
from verify import BASELINE, VerificationError, read_json, require, sha256


TARGETS = {
    "net9.0": ("9.0.23", "9.0.18", "compat"),
    "net10.0": ("10.0.15", "10.0.15", "core"),
}
SDK = "10.0.404"
SQLITE = "Microsoft.EntityFrameworkCore.Sqlite"
R1_COMMIT = "7a47504c17b32f0111473c97dd2f8377fe06171b"
R1_TREE = "097820f84c1c20d09e5158c4a2723ed530098266"
SOURCE_ASSETS = {"LICENSE.md": "LICENSE.md", "abp_nupkg.png": "nupkg/abp_nupkg.png"}
# R1 普通 pack 中由 SDK 从 Abp 的包依赖组裁剪的直接引用。
PACK_PRUNED = {
    "System.Collections.Immutable", "System.Data.Common", "System.Linq.Queryable",
    "System.Security.Claims", "System.Text.Json", "System.Text.RegularExpressions", "System.Threading",
}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def nuspec_metadata(archive):
    files = [file for file in archive.namelist() if file.endswith(".nuspec")]
    require(len(files) == 1, "应存在唯一 nuspec")
    root = ET.fromstring(archive.read(files[0]))
    for node in root.iter():
        node.tag = node.tag.rsplit("}", 1)[-1]
    return root.find("metadata")


def metadata_groups(metadata, group_name, field):
    groups = {}
    for node in metadata.findall(f"{group_name}/group"):
        tfm = node.attrib["targetFramework"]
        require(tfm not in groups, f"{group_name} 重复的 TFM 组 {tfm}")
        groups[tfm] = {entry.attrib[field]: dict(entry.attrib) for entry in node}
        require(len(groups[tfm]) == len(node), f"{group_name} {tfm} 有重复项")
    return groups


def package_archive(archive, expected_files):
    files = archive.namelist()
    require(len(files) == len({file.casefold() for file in files}), "ZIP 路径重名")
    require(archive.testzip() is None, "ZIP CRC 错误")
    require({file for file in files if file.lower().endswith((".dll", ".pdb"))} == expected_files,
            f"包内程序集或符号资产与预期不符：{files}")


def open_r1_tar(path):
    try:
        return tarfile.open(path)
    except (tarfile.TarError, EOFError, OSError, zlib.error) as error:
        raise VerificationError(f"无法打开 R1 归档 {path}：{error}") from error


def read_r1_member(archive, member):
    try:
        stream = archive.extractfile(member)
        require(stream is not None, f"R1 归档 {archive.name} 缺少常规文件 {member}")
        with stream:
            return stream.read()
    except (tarfile.TarError, EOFError, OSError, KeyError, zlib.error) as error:
        raise VerificationError(f"无法读取 R1 归档 {archive.name} 中的 {member}：{error}") from error


def r1_inputs(r1, mapping):
    outputs = read_json(r1 / "release-outputs.json")
    result = {}
    with open_r1_tar(r1 / "final-raw-assets.tar.gz") as assets_archive, \
            open_r1_tar(r1 / "release-dlls.tar.gz") as dll_archive:
        for row in mapping.values():
            assembly = row["assemblyName"]
            for tfm, (_, _, lane) in TARGETS.items():
                entry = outputs[f"{assembly}/{tfm}"]
                path = f"{lane}/api-a/{assembly}.json"
                api = read_json(r1 / path)
                properties = read_json(r1 / lane / "identity" / f"{assembly}.json")["Properties"]
                require(properties["PackageId"] == row["originalPackageId"] and
                        properties["AssemblyName"] == assembly and properties["RootNamespace"] == row["rootNamespace"] and
                        properties["TargetFramework"] == tfm and properties["TargetPath"] == entry["path"] and
                        properties["ProjectAssetsFile"] == entry["assets"],
                        f"{assembly} {tfm} R1 求值身份与基线或工件记录不同")
                asset_key = entry["assets"].split(f"/{lane}-final/", 1)[1]
                asset_bytes = read_r1_member(assets_archive, f"{lane}-final/{asset_key}")
                dll_key = entry["path"].split(f"/{lane}-final/", 1)[1]
                dll_bytes = read_r1_member(dll_archive, f"{lane}-final/{dll_key}")
                require(hashlib.sha256(asset_bytes).hexdigest() == entry["assetsSha256"] and
                        hashlib.sha256(dll_bytes).hexdigest() == entry["sha256"] == api["sha256"],
                        f"{assembly} {tfm} R1 API、DLL 或还原资产摘要不一致")
                assets = json.loads(asset_bytes)["project"]["frameworks"][tfm]
                deps = {name: info["version"] for name, info in assets.get("dependencies", {}).items()
                        if info.get("target") == "Package" and info.get("suppressParent") != "All"}
                pruned = PACK_PRUNED.copy() if assembly == "Abp" else set()
                if assembly == "Abp" and tfm == "net9.0":
                    pruned.add("System.ComponentModel.Annotations")
                require(pruned <= deps.keys() & assets.get("packagesToPrune", {}).keys(),
                        f"{assembly} {tfm} R1 裁剪基线不一致")
                refs = {name for name, info in assets.get("frameworkReferences", {}).items()
                        if info["privateAssets"].casefold() != "all"}
                result[assembly, tfm] = {
                    "api": api, "apiPath": path, "apiSha256": sha256(r1 / path),
                    "assetsSha256": entry["assetsSha256"], "pruned": sorted(pruned),
                    "dependencies": {key: val for key, val in deps.items() if key not in pruned},
                    "frameworkReferences": refs,
                }
    return result


def version_range(version):
    """把 NuGet 的裸版本写法规范化为含下界的范围。"""
    return version.replace(" ", "") if version.startswith(("[", "(")) else f"[{version},)"


def framework_package(name):
    return bool(re.match(r"^(?:(?:du\.|volo\.)?abp|abplts)(?:\.|$)", name, re.IGNORECASE))


def commit_tree(run, repository, commit, label):
    require(re.fullmatch(r"[0-9a-f]{40}", commit or ""), f"{label} 必须是完整 Git 提交 ID")
    kind = run.git(repository, f"{label}-type.log", "cat-file", "-t", commit)
    require(kind == "commit", f"{label} {commit} 的 Git 对象类型为 {kind}，预期 commit")
    return run.git(repository, f"{label}-tree.log", "rev-parse", f"{commit}^{{tree}}")


def verify_source(run, manifest_path, declared):
    proof = declared["sourceProof"]
    patch = manifest_path.parent / "source.patch"
    require(sha256(patch) == proof["patchSha256"], f"候选源码补丁摘要不一致：{patch}")
    commit = declared["superproject"]["commit"]
    gitlink = declared["superproject"]["frameworkGitlink"]
    commit_tree(run, run.repo, commit, "candidate-superproject")
    mapping = run.git(run.repo, "candidate-gitlink.log", "ls-tree", commit, "--", "aspnetboilerplate")
    require(mapping == f"160000 commit {gitlink}\taspnetboilerplate",
            f"主仓 {commit} 的框架 gitlink 与候选来源不同")
    repository_url = run.git(run.repo, "candidate-repository-url.log", "config",
                             "--blob", f"{commit}:.gitmodules", "--get", "submodule.aspnetboilerplate.url")
    require(repository_url == declared["repositoryUrl"], "候选源码与主仓登记的框架仓库 URL 不同")
    source = run.repo / "aspnetboilerplate"
    gitlink_tree = commit_tree(run, source, gitlink, "candidate-gitlink")
    base = proof["baseCommit"]
    base_tree = commit_tree(run, source, base, "candidate-base")
    committed = "commit" in proof
    if committed:
        source_commit = proof["commit"]
        committed_tree = commit_tree(run, source, source_commit, "candidate-source-commit")
        require(committed_tree == proof["tree"],
                f"候选来源提交 {source_commit} 的树为 {committed_tree}，与候选树 {proof['tree']} 不同")
    else:
        require(proof["tree"] != base_tree, f"候选源码树与打包基线 {base} 一致，来源证明缺少精确 commit")
    # 以独立对象目录和索引重放补丁，保留真实仓库的索引和对象库。
    scratch = run.evidence / "source-replay"
    scratch.mkdir()
    (scratch / "objects").mkdir()
    _, objects = run.command(["git", "rev-parse", "--path-format=absolute", "--git-path", "objects"],
                             source, "candidate-objects.log")
    env = {
        "GIT_INDEX_FILE": str(scratch / "index"),
        "GIT_OBJECT_DIRECTORY": str(scratch / "objects"),
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": objects.read_text().strip(),
        "GIT_OPTIONAL_LOCKS": "0",
    }
    run.command(["git", "read-tree", base], source, "candidate-replay-base.log", extra_env=env)
    patch_size = patch.stat().st_size
    if patch_size:
        run.command(["git", "apply", "--cached", patch], source, "candidate-replay-patch.log", extra_env=env)
    _, log = run.command(["git", "write-tree"], source, "candidate-replay-tree.log", extra_env=env)
    tree = log.read_text().strip()
    require(tree == proof["tree"], "补丁重放树与候选源码身份不同")
    assets = {}
    for file, relative_source in SOURCE_ASSETS.items():
        output = f"candidate-source-{file}"
        run.command(["git", "show", f"{tree}:{relative_source}"], source,
                    f"{output}.log", output=output, extra_env=env)
        assets[file] = sha256(run.evidence / output)
    return {**proof, "mode": "committed" if committed else "uncommitted", "patch": str(patch),
            "patchBytes": patch_size, "repositoryUrl": repository_url,
            "baseTree": base_tree, "gitlinkTree": gitlink_tree, "assets": assets}


def verify_packages(run, feed, manifest, symbols, r1):
    paths = run.evidence
    declared = read_json(manifest)
    version = declared["version"]
    require(declared["schemaVersion"] == 1 and re.fullmatch(r"10\.5\.1-r2\.[1-9][0-9]*", version)
            and declared["sdk"] == SDK and declared["restore"]["source"] == NUGET_SOURCE,
            f"候选清单格式、版本、SDK 或还原源不符：{manifest}")
    baseline = read_json(run.repo / BASELINE)
    repository = run.report["inputs"]["source"]["repositoryUrl"]
    require(declared["repositoryUrl"] == repository, "候选仓库与登记仓库不一致")
    closure = baseline["initialPackageClosure"]
    mapping = {entry["plannedPackageId"]: entry for entry in closure["packages"]}
    require(set(declared["packages"]) == mapping.keys(), "候选五包映射与已冻结 R0 基线不一致")
    require({path.name for path in feed.glob("*.nupkg")} == {f"{name}.{version}.nupkg" for name in mapping},
            "候选源需包含本批五个 nupkg")
    require({path.name for path in symbols.glob("*.snupkg")} == {f"{name}.{version}.snupkg" for name in mapping},
            "符号目录需包含本批五个 snupkg")

    references = r1_inputs(r1, mapping)
    internal_ranges = {}
    result = {"version": version, "manifest": str(manifest), "manifestSha256": sha256(manifest),
              "feed": str(feed), "symbols": str(symbols), "r1Evidence": str(r1),
              "sourceProof": declared["sourceProof"],
              "entries": ["Du." + name for name in closure["entryOriginalPackageIds"]], "packages": {}}
    for name, row in mapping.items():
        assembly = row["assemblyName"]
        candidate = declared["packages"][name]
        require(candidate["assemblyName"] == assembly and set(candidate["targets"]) == TARGETS.keys(),
                f"{name} 清单程序集或目标不符")
        package = feed / f"{name}.{version}.nupkg"
        symbol = symbols / f"{name}.{version}.snupkg"
        for spec, path in ((candidate["package"], package), (candidate["symbols"], symbol)):
            require(spec["file"] == path.name and sha256(path) == spec["sha256"],
                    f"{name} 摘要不符：{path}")
        dlls = {f"lib/{tfm}/{assembly}.dll" for tfm in TARGETS}
        pdbs = {f"lib/{tfm}/{assembly}.pdb" for tfm in TARGETS}
        with zipfile.ZipFile(package) as archive, zipfile.ZipFile(symbol) as debug:
            package_archive(archive, dlls)
            package_archive(debug, pdbs)
            metadata = nuspec_metadata(archive)
            debug_metadata = nuspec_metadata(debug)
            for spec in (metadata, debug_metadata):
                require((spec.findtext("id"), spec.findtext("version")) == (name, version),
                        f"{name} nuspec 身份不符")
                repo = spec.find("repository")
                require(repo.get("url") == repository and repo.get("type") == "git" and
                        repo.get("commit") == declared["sourceProof"].get("commit"),
                        f"{name} nuspec 源码仓库不符")
            require(json.loads(archive.read("du-core-candidate-source.json")) == declared["sourceProof"],
                    f"{name} 包内来源证明不符")
            require(metadata.find("license").attrib == {"type": "file"} and
                    metadata.findtext("license") == "LICENSE.md" and metadata.findtext("icon") == "abp_nupkg.png",
                    f"{name} 包内许可或图标声明不符")
            for file in SOURCE_ASSETS:
                expected_hash = run.report["inputs"]["source"]["assets"][file]
                require(hashlib.sha256(archive.read(file)).hexdigest() == expected_hash,
                        f"{name} 包内文件 {file} 与框架原件不同")

            deps = metadata_groups(metadata, "dependencies", "id")
            frameworks = metadata_groups(metadata, "frameworkReferences", "name")
            require(set(deps) == TARGETS.keys(), f"{name} 缺失 TFM 依赖组")
            target_evidence = {}
            for tfm in TARGETS:
                ref = references[assembly, tfm]
                selected = deps[tfm]
                internal = {key: item["version"] for key, item in selected.items() if framework_package(key)}
                require(internal.keys() == set(row["internalDependencies"]),
                        f"{name} {tfm} 内部依赖 ID 错误，预期 {row['internalDependencies']}，实际 {sorted(internal)}")
                internal_ranges.update({f"{name} {tfm} → {key}": value for key, value in internal.items()})
                third_party = {key: version_range(item["version"]) for key, item in selected.items()
                               if key not in internal}
                require(third_party == {key: version_range(val) for key, val in ref["dependencies"].items()} and
                        set(frameworks.get(tfm, {})) == ref["frameworkReferences"],
                        f"{name} {tfm} 第三方或共享框架依赖与 R1 可传播声明不同：{third_party}")
                require(all(item.get("exclude") == "Build,Analyzers" and "include" not in item
                            for item in selected.values()), f"{name} {tfm} 依赖资产可见性不符")
                dll_path = f"lib/{tfm}/{assembly}.dll"
                pdb_path = f"lib/{tfm}/{assembly}.pdb"
                local = paths / f"{name}.{tfm}.dll"
                local.write_bytes(archive.read(dll_path))
                # 摘要更新后的错目标夹具必须在 PE 目标框架门禁失败。
                stem = f"{name}-{tfm}"
                _, log = run.command([run.dotnet, run.metadata_tool, local], paths, f"{stem}-tfm.log")
                target = json.loads(log.read_text())["targets"]
                expected = f".NETCoreApp,Version=v{tfm.removeprefix('net')}"
                require(target == [expected],
                        f"{name} {dll_path} TargetFrameworkAttribute 预期 {expected}，实读 {target}")
                asset = candidate["targets"][tfm]
                require(asset["path"] == dll_path and asset["sha256"] == sha256(local) and
                        asset["pdbPath"] == pdb_path and asset["pdbSha256"] == hashlib.sha256(debug.read(pdb_path)).hexdigest(),
                        f"{name} {tfm} 包内 DLL 或 PDB 摘要与清单不同")
                run.command([run.dotnet, run.api_tool, local], paths,
                            f"{stem}-api.log", output=f"{stem}-api.json")
                api = read_json(run.evidence / f"{stem}-api.json")
                differences = compare_api(ref["api"], api)
                require(not differences, f"{name} {tfm} R1 API 差异：{differences}")
                target_evidence[tfm] = {
                    **asset, "targetFrameworkAttribute": expected, "identity": api["assembly"],
                    "dependencies": selected, "frameworkReferences": sorted(ref["frameworkReferences"]),
                    "r1Api": ref["apiPath"], "r1ApiSha256": ref["apiSha256"],
                    "r1DllSha256": ref["api"]["sha256"], "r1AssetsSha256": ref["assetsSha256"],
                    "r1PackPruned": ref["pruned"], "apiDiff": differences,
                }
            require(metadata_groups(debug_metadata, "dependencies", "id") == deps and
                    metadata_groups(debug_metadata, "frameworkReferences", "name") == frameworks,
                    f"{name} 符号包依赖组不同")
        result["packages"][name] = {
            "assemblyName": assembly, "rootNamespace": row["rootNamespace"],
            "internalDependencies": row["internalDependencies"],
            "package": candidate["package"], "symbols": candidate["symbols"], "targets": target_evidence,
        }
    run.check_dependency_ranges(version, internal_ranges, "packages")
    return result
