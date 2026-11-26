"""核对 R4 实际归档、程序集和 Portable PDB。"""

from functools import cache
from hashlib import sha1
import json
from pathlib import Path
import re
import shutil
import subprocess
from zipfile import ZipFile

from r2_packages import metadata_groups, nuspec_metadata, package_archive, write_json
from r3_leaf_packages import bytes_sha256, checked_file
from r4_release_candidate import REFERENCE, normalized_range, verify_equal
from verify import ROOT, TOOLS, read_json, require, sha256


ATTRIBUTION = {
    "framework": ("LICENSE.md", "Volosoft", "https://github.com/aspnetboilerplate/aspnetboilerplate"),
    "engine": ("LICENSE.txt", "Jimmy Bogard", "https://github.com/AutoMapper/AutoMapper"),
    "collection": ("LICENSE", "Tyler Carlson", "https://github.com/AutoMapper/AutoMapper.Collection"),
}
DOCUMENT_HASHES = {
    "8829d00f-11b8-4213-878b-770e8597ac16": bytes_sha256,
    "ff1816ec-aa5e-4d10-87f7-6f4963833460": lambda data: sha1(data).hexdigest(),
}
R4_INSPECTION = ROOT / "eng/r4-inspection"


def check_readme(archive, metadata, name, version, project_url, attribution):
    path = metadata.findtext("readme")
    verify_equal("README.md", path, f"{name}/nuspec/readme")
    readme = archive.read(path).decode("utf-8-sig")
    field = f"{name}/{path}"
    for command, option in (("dotnet add package", "--version"), ("Install-Package", "-Version")):
        actual = re.findall(rf"^[ \t]*({re.escape(command)}[^\n]*)$", readme, re.M | re.I)
        verify_equal([f"{command} {name} {option} {version}"], [line.strip() for line in actual], f"{field}/{command}")
    links = re.findall(r"https://www\.nuget\.org/packages/([^\s)]+)", readme)
    verify_equal([f"{name}/"], links, f"{field}/安装链接")
    verify_equal([project_url + "/issues"], re.findall(r"https://github\.com/[^\s)]+/issues\b", readme),
                 f"{field}/维护入口")
    license_file, author, upstream = attribution
    for phrase in (author, upstream, f"`{license_file}`", "MIT", "版权"):
        require(phrase in readme, f"{field}/上游署名与许可：预期包含 {phrase!r}，实际缺失")
    return {"path": path, "sha256": bytes_sha256(archive.read(path)), "installId": name,
            "version": version, "nugetUrl": f"https://www.nuget.org/packages/{name}/",
            "issuesUrl": project_url + "/issues", "credit": author, "upstream": upstream}


def producer_git(source, *args):
    repo = ROOT / source["path"]
    return subprocess.check_output(["git", "-C", repo, *args], stderr=subprocess.PIPE)


@cache
def source_object(path, commit, relative):
    return producer_git({"path": path}, "show", f"{commit}:{relative}")


def project_identity(name, row, tfm, source, work, dotnet, run):
    assembly = name.removeprefix("Du.")
    project = ROOT / source["path"] / "src" / assembly / f"{assembly}.csproj"
    properties = {"Configuration": "Release", "TargetFramework": tfm, "ArtifactsPath": str(work / "properties")}
    candidate = {
        "framework": {"DuR4Pack": "true"},
        "engine": {"DuAutoMapperCandidate": "true", "DuR4Pack": "true"},
        "collection": {"DuR3CollectionCandidate": "true", "DuR4Pack": "true"},
    }[row["producer"]]
    expected_namespace = {"Abp.EntityFramework.Common": "Abp.EntityFramework"}.get(
        assembly, "Abp" if row["producer"] == "framework" else assembly)
    field = f"{name}/{tfm}/项目属性"
    actual = {}
    for mode, settings in (("ordinary", properties), ("r4", properties | candidate)):
        result = run([dotnet, "msbuild", project, "-nologo", "-getProperty:PackageId,AssemblyName,RootNamespace",
                      *[f"-p:{key}={value}" for key, value in settings.items()]], work,
                     f"{name}-{tfm}-{mode}-properties")
        actual[mode] = json.loads(result)["Properties"]
        verify_equal({"PackageId": name if mode == "r4" else assembly, "AssemblyName": assembly,
                      "RootNamespace": expected_namespace}, actual[mode], f"{field}/{mode}")
    return actual


class ArchiveInspection:
    def __init__(self, manifest, baseline_root, work, dotnet, run):
        self.manifest = manifest
        self.baseline_root = baseline_root
        self.work = work
        self.dotnet = dotnet
        self.run = run
        self.baseline = {row["id"]: row for batch in read_json(REFERENCE)["batches"].values()
                         for row in batch["packages"]}
        self.source_files = {}
        for producer, source in manifest["producers"].items():
            files = producer_git(source, "ls-tree", "-r", "--name-only", "-z", source["finalCommit"])
            self.source_files[producer] = set(files.decode().split("\0"))
        self.api_tool = self.build_tool(ROOT / TOOLS, "ApiInventory", "net9.0")
        self.pdb_tool = self.build_tool(R4_INSPECTION, "InspectDll", "net10.0")

    def build_tool(self, source, name, tfm):
        work = self.work / name
        work.mkdir()
        project = f"{name}.csproj"
        for path in (source / project, source / "Program.cs", R4_INSPECTION / "global.json"):
            shutil.copyfile(path, work / path.name)
        self.run([self.dotnet, "build", project, "-c", "Release", "--disable-build-servers"], work, name)
        return work / "bin/Release" / tfm / f"{name}.dll"

    def check_sources(self, pdb, row, source, field):
        repo = source["repository"].removesuffix(".git").removeprefix("https://github.com/")
        commit = source["finalCommit"]
        prefix = f"https://raw.githubusercontent.com/{repo}/{commit}/"
        mapping = pdb["sourceLink"]["documents"]
        require(mapping, f"{field}/Source Link 缺少文档映射")
        for alias, target in mapping.items():
            require(alias.endswith("*") and target.startswith(prefix) and target.endswith("*"),
                    f"{field}/Source Link：预期 {prefix} 下的映射，实际 {alias} → {target}")
        tracked, generated = [], []
        for doc in pdb["documents"]:
            local = doc["path"]
            for alias, target in mapping.items():
                if not local.startswith(alias[:-1]):
                    continue
                path = target[len(prefix):-1] + local[len(alias)-1:]
                if path not in self.source_files[row["producer"]]:
                    continue
                blob = source_object(source["path"], commit, path)
                actual = DOCUMENT_HASHES[doc["hashAlgorithm"]](blob)
                verify_equal(actual, doc["hash"], f"{field}/PDB/源码/{path}")
                tracked.append(path)
                break
            else:
                require(doc["embedded"] and "/artifacts/obj/" in local,
                        f"{field}/PDB/源码：{local} 缺少提交级定位或嵌入的生成源码")
                generated.append(Path(local).name)
        require(tracked, f"{field}/PDB/源码 没有对应的生产 Git 对象")
        return len(tracked), sorted(generated)

    def inspect_target(self, name, row, source, tfm, target, archive, symbols, baseline, verify_project):
        field = f"{name}/{tfm}"
        asset = target["asset"]
        pdb_asset = asset.removesuffix(".dll") + ".pdb"
        temp = self.work / name / tfm
        temp.mkdir(parents=True)
        old, dll, pdb = (temp / path for path in ("baseline.dll", Path(asset).name, Path(pdb_asset).name))
        old.write_bytes(baseline.read(asset))
        dll.write_bytes(archive.read(asset))
        pdb.write_bytes(symbols.read(pdb_asset))
        verify_equal(target["baselineAssetSha256"], sha256(old), f"{field}/对照 DLL")
        old_api, api = (json.loads(self.run([self.dotnet, self.api_tool, file], self.work, f"{name}-{tfm}-{tag}-API"))
                        for tag, file in (("baseline", old), ("r4", dll)))
        for key in ("assembly", "types", "resources"):
            verify_equal(old_api[key], api[key], f"{field}/{key}")
        debug = json.loads(self.run([self.dotnet, self.pdb_tool, dll, pdb, old], self.work, f"{name}-{tfm}-PDB"))
        verify_equal({"guid": debug["dllGuid"], "stamp": debug["dllStamp"], "age": 1},
                     {"guid": debug["pdbGuid"], "stamp": debug["pdbStamp"], "age": debug["dllAge"]},
                     f"{field}/{pdb_asset}/CodeView")
        verify_equal(f".NETCoreApp,Version=v{tfm.removeprefix('net')}", debug["targetFramework"], f"{field}/DLL/TFM")
        verify_equal(f"{row['version']}+{source['finalCommit']}", debug["fileVersion"]["ProductVersion"],
                     f"{field}/DLL/ProductVersion")
        count, generated = self.check_sources(debug, row, source, field)
        result = {
            "asset": asset, "assetSha256": api["sha256"], "baselineAssetSha256": old_api["sha256"],
            "assembly": api["assembly"], "publicProtectedTypes": len(api["types"]),
            "resourceCount": len(api["resources"]), "fileVersion": debug["fileVersion"],
            "baselineFileVersion": debug["baselineFileVersion"], "pdb": pdb_asset, "pdbSha256": sha256(pdb),
            "pdbGuid": debug["pdbGuid"], "pdbStamp": debug["pdbStamp"], "sourceLink": debug["sourceLink"],
            "matchedSourceDocuments": count, "embeddedGeneratedDocuments": generated,
            "dependencies": target["internalDependencies"] | target["thirdPartyDependencies"],
            "frameworkReferences": target["frameworkReferences"],
        }
        if verify_project:
            result["projectIdentity"] = project_identity(name, row, tfm, source, self.work, self.dotnet, self.run)
        return result

    def inspect_package(self, name, row, archive_file, symbol_file, verify_project=True):
        producer = row["producer"]
        source = self.manifest["producers"][producer]
        reference = self.baseline[name]
        baseline_file = checked_file(self.baseline_root, reference["archive"], row["baseline"]["archiveSha256"])
        license_file, author, _ = ATTRIBUTION[producer]
        assets = {target["asset"] for target in row["targets"].values()}
        with ZipFile(archive_file) as archive, ZipFile(symbol_file) as symbols, ZipFile(baseline_file) as baseline:
            package_archive(archive, assets)
            package_archive(symbols, {asset.removesuffix(".dll") + ".pdb" for asset in assets})
            metadata = nuspec_metadata(archive)
            symbol_metadata = nuspec_metadata(symbols)
            repository = {"type": "git", "url": source["repository"], "commit": source["finalCommit"]}
            for kind, spec in (("nuspec", metadata), ("symbols/nuspec", symbol_metadata)):
                for key, expected in (("id", name), ("version", row["version"]), ("projectUrl", row["projectUrl"])):
                    verify_equal(expected, spec.findtext(key), f"{name}/{kind}/{key}")
                element = spec.find("repository")
                actual = {key: element.get(key) for key in repository} if element is not None else {}
                verify_equal(repository, actual, f"{name}/{kind}/repository")
            verify_equal(name.removeprefix("Du.") if producer == "framework" else author,
                         metadata.findtext("authors"), f"{name}/nuspec/authors")
            license_spec = metadata.find("license")
            expected_license = ("expression", "MIT") if producer == "collection" else ("file", license_file)
            verify_equal(expected_license,
                         (license_spec.get("type"), license_spec.text) if license_spec is not None else None,
                         f"{name}/nuspec/license")
            license_digest = bytes_sha256(archive.read(license_file))
            verify_equal(bytes_sha256(source_object(source["path"], source["finalCommit"], license_file)),
                         license_digest, f"{name}/{license_file}/SHA-256")
            readme = check_readme(archive, metadata, name, row["version"], row["projectUrl"], ATTRIBUTION[producer])
            require(not metadata.findall("dependencies/dependency") and
                    not metadata.findall("frameworkReferences/frameworkReference") and
                    not metadata.findall("frameworkAssemblies/frameworkAssembly"),
                    f"{name}/nuspec 含清单未登记的依赖或框架引用")
            dependencies = metadata_groups(metadata, "dependencies", "id")
            frameworks = metadata_groups(metadata, "frameworkReferences", "name")
            verify_equal(sorted(row["targets"]), sorted(dependencies), f"{name}/nuspec/依赖目标组")
            require(frameworks.keys() <= row["targets"].keys(), f"{name}/nuspec 框架引用含未登记的目标组")
            targets = {}
            for tfm, target in row["targets"].items():
                ranges = target["internalDependencies"] | target["thirdPartyDependencies"]
                verify_equal({key: normalized_range(value) for key, value in ranges.items()},
                             {key: normalized_range(dep["version"]) for key, dep in dependencies[tfm].items()},
                             f"{name}/{tfm}/dependencies")
                verify_equal(target["frameworkReferences"], sorted(frameworks.get(tfm, {})),
                             f"{name}/{tfm}/frameworkReferences")
                targets[tfm] = self.inspect_target(name, row, source, tfm, target, archive, symbols,
                                                   baseline, verify_project)
        return {"repository": repository, "projectUrl": row["projectUrl"], "authors": metadata.findtext("authors"),
                "readme": readme, "license": {"path": license_file, "sha256": license_digest,
                                             "type": expected_license[0], "value": expected_license[1]},
                "targets": targets}
