"""绑定公开发行附件，对照固定模板的完整公开包图。"""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
from zipfile import ZipFile

from r3_leaf_packages import checked_file
from r3_template_net9_packages import STAGES as BUILD_STAGES, normalized_range
from r3_web_host import NUGET_SOURCE, artifact, write_json
from r5_candidate_batch import VERSIONS
from verify import read_json, require


TFM = "net10.0"
REPOSITORY = "https://github.com/dusdong/du.aspnetboilerplate"
TEMPLATE = "2e9536872673a7ff1986a19e798c51684d16afe5"
RELEASES = {
    "r4": ("v10.5.1", "5758c8186b68dcc42ecc90164cf9d3f53cf3345e",
           "c3a905b6a6373a59236214f94fce953abb530fc61c80a7fe94ff99f028f534b0"),
    "r5": ("v10.5.2", "cebc3e38a511783092963893bf5ad3161d0f0a19",
           "be08d2d354d71dcb09802f8161496f213ebdd257826ed5adbf6af77fe9000dd5"),
}
TAG_OBJECTS = {"r4": "338cc2c83bc61c06047f4f98298aec629c8ca781",
               "r5": "b08cd8ae03cb47bc6f01fa0a0d0065efc3c78b43"}
HISTORICAL = {
    "r4": ("ef4a2787d6cc840d25584ea2232415289a3d1eeb625db776db98f5e5187287f9",
           "54660e9d299ad961e12efff426b32c356556295a41b5c5030187444eebc708fd"),
    "r5": ("52d456199c6baf76a6ed27941a5b6bdd24ffe58eeeef868bc7e94f24bd339de8",
           "7f79ab2d50a53cb148f0d11c079e32e79172b374d2abde37546f67eac415083a"),
}
COUNTS = {"Web.Host": (94, 13, 163), "Migrator": (66, 10, 115)}
R4_VERSIONS = {"Du.AutoMapper": "14.0.0", "Du.AutoMapper.Collection": "11.0.0", "Du.Abp.AutoMapper": "10.5.1"}
PATCH_EDGES = (
    ("AbpCompanyName.AbpProjectName.Core", "Du.Abp.AutoMapper"),
    ("Du.Abp.AutoMapper", "Du.AutoMapper"),
    ("Du.Abp.AutoMapper", "Du.AutoMapper.Collection"),
    ("Du.AutoMapper.Collection", "Du.AutoMapper"),
)


@dataclass(frozen=True)
class PublishedInputs:
    attachment: Path
    manifest: Path
    downloads: Path
    baseline: Path

    def qualify(self, release, evidence):
        tag, commit, digest = RELEASES[release]
        attachment = checked_file(self.attachment.parent, self.attachment.name, digest)
        proof = read_json(attachment)
        require((proof["repository"], proof["tag"], proof["commit"], proof["nugetSource"],
                 proof["template"]["commit"]) == (REPOSITORY, tag, commit, NUGET_SOURCE, TEMPLATE),
                f"{release} 公开附件的仓库、标签、协调提交、NuGet 源或模板不符")
        expected_files = (("checksums.json", attachment, digest),
                          ("manifest.json", self.manifest, proof["releaseManifestSha256"]),
                          ("downloads.json", self.downloads, proof["verifiedDownloadsSha256"]))
        bundle = []
        for name, source, expected in expected_files:
            source = checked_file(source.parent, source.name, expected)
            copy = evidence / f"{release}-{name}"
            shutil.copyfile(source, copy)
            bundle.append(checked_file(evidence, copy.name, expected))
        manifest, downloads = map(read_json, bundle[1:])
        identity = manifest["release"]
        # R5 的签前发行清单没有最终 tag 目标，公开附件为该协调提交及清单摘要背书。
        manifest_commit = identity["commit"] if release == "r4" else proof["commit"]
        require((identity["repository"], identity["tag"], manifest_commit, manifest["nugetSource"],
                 manifest["template"]["baseCommit"], downloads["nugetSource"], downloads["manifestSha256"]) ==
                (REPOSITORY, tag, commit, NUGET_SOURCE, TEMPLATE, NUGET_SOURCE, proof["releaseManifestSha256"]),
                f"{release} 公开发行清单与签后下载登记身份不符")
        rows = downloads["packages"]
        carried = proof.get("carriedPackages", {})
        require(len(rows) == 13 and rows.keys() == proof["packages"].keys() | carried.keys(),
                f"{release} 附件与登记的 13 个维护包不一致")
        for name, pkg in (proof["packages"] | carried).items():
            main = pkg.get("mainPackage", pkg)
            actual = rows[name]
            require((actual["version"], actual["uploadSha256"], actual["downloadSha256"]) ==
                    (pkg["version"], (main["r4UploadSha256"] if name in carried else main["uploadSha256"]),
                     main["anonymousDownloadSha256"]),
                    f"{release} {name} 版本、签前或签后摘要与附件不符")
        return bundle, proof, rows


def bound_json(directory, ref):
    return read_json(checked_file(directory, ref["path"], ref["sha256"]))


def entry_graph(directory, report, inventory, entry, *, historical, archive_directory=None):
    raw = bound_json(directory, report["rawAssets"][entry])
    output = bound_json(directory, report["inputs"]["entryOutputs"]["net10"][entry])
    cache = (archive_directory or directory) / "packages"
    selected = raw["targets"][TFM]
    framework = raw["project"]["frameworks"][TFM]
    require(set(raw["targets"]) == {TFM}
            and set(raw["project"]["restore"]["sources"]) == {NUGET_SOURCE}
            and report["inputs"]["nuget"]["effectiveSources"] == [NUGET_SOURCE]
            and report["inputs"]["nuget"]["cachesInitiallyEmpty"],
            f"{directory.name} {entry} 目标框架或空缓存来源不符")
    archive_paths = {}
    nodes, edges, assets = {}, {}, {}
    for key, item in selected.items():
        name, version = key.split("/")
        package = item["type"] == "package"
        library = raw["libraries"][key]
        nodes[name] = {"type": item["type"], "version": version, "contentSha512": library.get("sha512")}
        edges.update({(name, dep): normalized_range(value) for dep, value in item.get("dependencies", {}).items()})
        if package:
            nodes[name]["frameworkReferences"] = item.get("frameworkReferences", [])
            record = inventory["packages"][key]
            require(record["source"] == NUGET_SOURCE and record["contentSha512"] == library["sha512"],
                    f"{directory.name} {entry} {key} 的包源或摘要登记不符")
            nodes[name]["archiveSha256"] = record["archive"]["sha256"]
            # 历史目录可只保留清单。用本轮同版且归档摘要相同的实物补全成员字节。
            digests = {}
            if not historical or archive_directory is not None:
                archive = checked_file(cache, record["archive"]["path"], record["archive"]["sha256"])
                archive_paths[name] = str(archive)
                with ZipFile(archive) as content:
                    digests = {path: hashlib.sha256(content.read(path)).hexdigest()
                               for role, paths in item.items() if role not in ("type", "dependencies", "frameworkReferences")
                               for path in paths if Path(path).name != "_._"}
            for role, paths in item.items():
                if role in ("type", "dependencies", "frameworkReferences"):
                    continue
                for path, metadata in paths.items():
                    assets[name, role, path] = {"sha256": digests.get(path), "metadata": metadata}
    root = raw["project"]["restore"]["projectName"]
    edges.update({(root, name): normalized_range(dep["version"])
                  for name, dep in framework.get("dependencies", {}).items()})
    edges.update({(root, Path(path).stem): "project"
                  for path in raw["project"]["restore"]["frameworks"][TFM]["projectReferences"]})
    for records in inventory["compileReferences"].values():
        for record in records:
            if "package" in record:
                name = record["package"].split("/")[0]
                path = record["packageAsset"]
                require(assets[name, "compile", path]["sha256"] in (None, record["sha256"]),
                        f"{directory.name} {entry} {name} 编译引用摘要与所选包成员不符")
                assets[name, "compiled", path] = record["sha256"]
    for destination, record in output["packageCopies"].items():
        name = record["package"].split("/")[0]
        assets[name, "output", record["packageAsset"], destination] = record["sha256"]
    for analyzer in inventory["selectedPackageAnalyzers"]:
        id_, _, path = analyzer["path"].split("/", 2)
        name, = (name for name, row in nodes.items() if row["type"] == "package" and name.casefold() == id_.casefold())
        assets[name, "analyzer", path] = analyzer["sha256"]
    packages = {name for name, row in nodes.items() if row["type"] == "package"}
    counts = len(packages), len({name for name in packages if name.startswith("Du.")}), len(edges)
    require(counts == COUNTS[entry], f"{directory.name} {entry} 包数、维护包数、边数预期 {COUNTS[entry]}，实际 {counts}")
    return {"nodes": nodes, "edges": edges, "assets": assets}, {
        "restoreCacheRoots": sorted(raw["packageFolders"]), "checkedArchives": archive_paths,
    }


def changed(before, after):
    return {" → ".join(key) if isinstance(key, tuple) else key: {"r4": before.get(key), "r5": after.get(key)}
            for key in sorted(before.keys() | after.keys()) if before.get(key) != after.get(key)}


def compare_graphs(r4, r5):
    return {kind: changed(r4[kind], r5[kind]) for kind in r4}


def verify_patch(r4, r5, changes):
    require(set(changes["nodes"]) == VERSIONS.keys()
            and all((r4["nodes"][name]["version"], r5["nodes"][name]["version"]) ==
                    (R4_VERSIONS[name], VERSIONS[name]) for name in VERSIONS),
            "包解析差异不限于三个映射包的登记版本")
    for version, graph in ((R4_VERSIONS, r4), (VERSIONS, r5)):
        require(all(graph["edges"].get(edge) == normalized_range(f"[{version[edge[1]]}]")
                    for edge in PATCH_EDGES), "映射包的四条边须声明登记的精确版本")
    require(set(changes["edges"]) == {" → ".join(edge) for edge in PATCH_EDGES},
            "依赖边差异不限于四条精确版本约束")
    require(r4["assets"].keys() == r5["assets"].keys(), "R4 与 R5 所选包资产路径或用途改变")
    for role in ("compiled", "output"):
        names = [key[0] for key in r4["assets"] if key[0] in VERSIONS and key[1] == role and key[2].endswith(".dll")]
        require(sorted(names) == sorted(VERSIONS), f"{role} 缺少每个映射包的唯一 DLL")
    for key, before in r4["assets"].items():
        after = r5["assets"][key]
        if key[0] in VERSIONS and key[1] in ("compile", "runtime", "compiled", "output") and key[2].endswith(".dll"):
            if isinstance(before, dict):
                require(before["metadata"] == after["metadata"], f"{key} 资产元数据改变")
                if before["sha256"] is not None:
                    require(before["sha256"] != after["sha256"], f"{key} 映射 DLL 的摘要未改变")
            else:
                require(before != after, f"{key} 映射 DLL 的摘要未改变")
        else:
            require(before == after, f"{key} 的选用资产发生未登记变化")


def compare_public_builds(builds, releases, evidence):
    root_report = read_json(builds["r5"] / "report.json")
    require(root_report["status"] == "running" and root_report["exitCode"] is None,
            "r5 整轮报告须处于进行中")
    incomplete = [name for name in BUILD_STAGES
                  if (root_report["stages"].get(name, {}).get("status"),
                      root_report["stages"].get(name, {}).get("exitCode")) != ("passed", 0)]
    require(not incomplete, f"r5 公开构建阶段缺失或未通过：{', '.join(incomplete)}")
    reports = {}
    inventories = {}
    results = {}
    output_references = {}
    for label, directory in builds.items():
        release = "r5" if label == "r5" else "r4"
        if label.startswith("baseline-"):
            release = label.removeprefix("baseline-")
            report_sha, inventory_sha = HISTORICAL[release]
            report = read_json(checked_file(directory, "report.json", report_sha))
            inventory = read_json(checked_file(directory, "assets-inventory.json", inventory_sha))
            require((report["status"], report["exitCode"]) == ("passed", 0), f"{label} 未通过")
        else:
            report = root_report
            if label != "r5":
                path = directory / "report.json"
                reference = root_report["inputs"]["publicBuilds"][label]
                require(artifact(path, evidence) | {"exitCode": 0} == reference,
                        f"{label} 的公开构建报告与完成时登记不符")
                report = read_json(path)
                require((report["status"], report["exitCode"]) == ("build_verified", 0),
                        f"{label} 公开构建未通过")
            inventory = read_json(directory / "assets-inventory.json")
            launch = read_json(directory / "launch-manifest.json")
            outputs = {entry: launch[entry]["outputVerification"] for entry in COUNTS}
            report["inputs"]["entryOutputs"] = {"net10": outputs}
            output_references[label] = {entry: reference | {
                "path": (directory / reference["path"]).relative_to(evidence).as_posix()}
                for entry, reference in outputs.items()}
        inputs = report["inputs"]
        downloads = inputs["publicDownloads"]
        require(inputs["nuget"]["effectiveSources"] == [NUGET_SOURCE] and inputs["targetFramework"] == TFM
                and downloads["release-manifest.json"]["sha256"] == releases[release]["releaseManifestSha256"]
                and downloads["verified-downloads.json"]["sha256"] == releases[release]["verifiedDownloadsSha256"],
                f"{label} 的公开构建来源、发行清单或签后登记不符")
        reports[label] = report
        inventories[label] = inventory
    caches = {(builds[phase] / "packages").resolve() for phase in ("r4", "r5", "rollback")}
    require(len(caches) == 3, "三次公开构建须使用不同的 NuGet 缓存")
    for entry in COUNTS:
        graphs = {}
        for label, directory in builds.items():
            historical = label.startswith("baseline-")
            archives = builds[label.removeprefix("baseline-")] if historical else None
            graphs[label], paths = entry_graph(directory, reports[label], inventories[label][entry], entry,
                                               historical=historical, archive_directory=archives)
            graph_file = evidence / f"{label}-{entry}-graph.json"
            graph = graphs[label]
            write_json(graph_file, {"nodes": graph["nodes"],
                                   "edges": [(*key, value) for key, value in sorted(graph["edges"].items())],
                                   "assets": [(*key, value) for key, value in sorted(graph["assets"].items())],
                                   **paths})
        results[entry] = checks = {
            "firstR4AgainstBaseline": compare_graphs(graphs["baseline-r4"], graphs["r4"]),
            "R5AgainstBaseline": compare_graphs(graphs["baseline-r5"], graphs["r5"]),
            "rollbackAgainstFirstR4": compare_graphs(graphs["r4"], graphs["rollback"]),
            "R4ToR5": compare_graphs(graphs["r4"], graphs["r5"]),
        }
        write_json(evidence / "public-graph-comparison.json", results)
        for name in ("firstR4AgainstBaseline", "R5AgainstBaseline", "rollbackAgainstFirstR4"):
            require(not any(checks[name].values()), f"{entry} {name} 完整图或所选资产差异，详见公开图差异")
        verify_patch(graphs["r4"], graphs["r5"], checks["R4ToR5"])
    return output_references
