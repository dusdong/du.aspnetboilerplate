#!/usr/bin/env python3
"""制备或离线核验 R5 三包待发批次。"""

import argparse
from base64 import b64encode
from copy import deepcopy
from hashlib import sha512
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from r2_packages import NUGET_SOURCE, nuspec_metadata, package_archive, write_json
from r3_automapper_packages import ADAPTER, COLLECTION, CORE, ENGINE, check_archive
from r3_leaf_packages import bytes_sha256, checked_file
from r4_candidate_batch import archive_paths, copy_checked, fingerprint, receipt_hashes, run_logged, verify_fingerprint
from r4_candidate_inspection import ATTRIBUTION, R4_INSPECTION, check_readme, check_sources, producer_git, source_object
from r4_public_release import CONFIG, compare_packages
from r4_release_candidate import source_at, verify_equal
from r5_automapper_consumer import consumers
from r5_candidate_batch import EDGES, VERSIONS, load_frozen_batch
from verify import ROOT, VerificationError, read_json, require, sha256


PRODUCERS = {ENGINE: "engine", COLLECTION: "collection", ADAPTER: "framework"}
RELEASE_DLLS = {
    ENGINE: "apicompat/artifacts/bin/AutoMapper/release/AutoMapper.dll",
    COLLECTION: "artifacts/bin/AutoMapper.Collection/release_net8.0/AutoMapper.Collection.dll",
    ADAPTER: "artifacts/bin/Abp.AutoMapper/release/Abp.AutoMapper.dll",
}
ENGINE_README = "src/AutoMapper/ApiCompat/README.r5-package.md"


def copy_evidence(root, source, relative, digest=None):
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    copy_checked(source, target, digest or sha256(source))
    return fingerprint(target, root)


def verify_source(name, row, final, work, run, root):
    source = row["source"]
    commit = source["compiledSourceCommit"]
    repo = ROOT / source["path"]
    tree = producer_git(source, "rev-parse", f"{final}^{{tree}}").decode().strip()
    verify_equal(source["productionTree"], tree, f"{name}/生产 Git 树")
    if "patch" in source:
        verify_equal(source["baseCommit"], commit, f"{name}/编译基点")
        verify_equal(commit, producer_git(source, "rev-parse", f"{final}^").decode().strip(),
                     f"{name}/生产提交父节点")
        patch = verify_fingerprint(root, source["patch"])
        objects = work / name / "objects"
        objects.mkdir(parents=True)
        common = producer_git(source, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()
        env = {"GIT_INDEX_FILE": str(objects.parent / "index"), "GIT_OBJECT_DIRECTORY": str(objects),
               "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(Path(common) / "objects")}
        run(["git", "read-tree", commit], repo, f"{name}-read-tree", env)
        run(["git", "apply", "--cached", patch], repo, f"{name}-apply-patch", env)
        replay = run(["git", "write-tree"], repo, f"{name}-write-tree", env).decode().strip()
        verify_equal(tree, replay, f"{name}/归档补丁回放树")
    else:
        verify_equal(commit, final, f"{name}/打包与生产提交")
    source["productionCommit"] = final
    files = producer_git(source, "ls-tree", "-r", "--name-only", "-z", commit)
    return set(files.decode().split("\0"))


def inspect(name, row, tfm, root, stage, work, dotnet, inspector, run, files):
    target = row["targets"][tfm]
    commit = row["source"]["compiledSourceCommit"]
    production = row["source"]["productionCommit"]
    repository = {"type": "git", "url": row["source"]["repository"], "commit": commit}
    compare = RELEASE_DLLS[name]
    archive, symbols = (root / row[kind]["path"] for kind in ("archive", "symbols"))
    deps = check_archive(archive, {"id": name, "version": row["version"], "target": tfm,
                                  "asset": target["asset"], "assetSha256": target["assetSha256"]},
                         EDGES.get(name, {}))
    verify_equal(target["dependencies"], deps, f"{name}/nuspec/依赖")
    with ZipFile(archive) as main, ZipFile(symbols) as debug:
        for package, asset in ((main, target["asset"]), (debug, target["pdb"])):
            package_archive(package, {asset})
            require(".signature.p7s" not in package.namelist(), f"{package.filename} 已含签名")
            meta = nuspec_metadata(package)
            for key, expected in (("id", name), ("version", row["version"]), ("projectUrl", row["projectUrl"])):
                verify_equal(expected, meta.findtext(key), f"{package.filename}/nuspec/{key}")
            element = meta.find("repository")
            require(element is not None, f"{package.filename}/nuspec 缺少 repository")
            verify_equal(repository, {key: element.get(key) for key in repository},
                         f"{package.filename}/nuspec/repository")
        meta = nuspec_metadata(main)
        readme = check_readme(main, meta, name, row["version"], row["projectUrl"], ATTRIBUTION[PRODUCERS[name]],
                              source=NUGET_SOURCE if name == ENGINE else None)
        raw = main.read(readme["path"])
        if name == ENGINE:
            expected = source_object(row["source"]["path"], production, ENGINE_README)
            readme["source"] = NUGET_SOURCE
        elif name == COLLECTION:
            expected = source_object(row["source"]["path"], production, "README.package.md")
            expected = expected.replace(b"14.0.0", b"14.0.1").replace(b"11.0.0", b"11.0.1")
        else:
            expected = source_object(row["source"]["path"], production, "nupkg/README.r4-package.md")
            expected = expected.replace(b"@PACKAGE@", name.encode()).replace(b"10.5.1", b"10.5.2")
        verify_equal(bytes_sha256(expected), bytes_sha256(raw), f"{name}/README/生产 Git 对象")
        verify_equal(row["authors"], meta.findtext("authors"), f"{name}/nuspec/authors")
        license_entry = meta.find("license")
        license_record = row["license"]
        verify_equal((license_record["type"], license_record["value"]),
                     (license_entry.get("type"), license_entry.text), f"{name}/nuspec/license")
        license_name = license_record["path"]
        license_bytes = main.read(license_name)
        verify_equal(license_record["sha256"], bytes_sha256(license_bytes), f"{name}/许可摘要")
        verify_equal(license_bytes, source_object(row["source"]["path"], production, license_name),
                     f"{name}/许可 Git 对象")
        folder = work / name
        folder.mkdir(exist_ok=True)
        dll, pdb = (folder / Path(target[key]).name for key in ("asset", "pdb"))
        dll.write_bytes(main.read(target["asset"]))
        pdb.write_bytes(debug.read(target["pdb"]))
    verify_equal(target["pdbSha256"], sha256(pdb), f"{name}/归档 PDB")
    verify_equal(sha256(dll), sha256(stage / compare), f"{name}/生产 DLL")
    verify_equal(sha256(pdb), sha256(stage / Path(compare).with_suffix(".pdb")), f"{name}/生产 PDB")
    command = [dotnet, inspector]
    marker = json.loads(run([*command, "--symbol", dll, pdb], work, f"{name}-symbol"))
    verify_equal(target["pdbDebugChecksum"], marker, f"{name}/DLL 与 Portable PDB")
    verify_equal(pdb.name, marker["name"], f"{name}/CodeView PDB 文件名")
    info = json.loads(run([*command, dll, pdb], work, f"{name}-sources"))
    verify_equal(f".NETCoreApp,Version=v{tfm.removeprefix('net')}", info["targetFramework"], f"{name}/DLL/TFM")
    for key in ("sourceLink", "fileVersion", "pdbGuid", "pdbStamp"):
        verify_equal(target[key], info[key], f"{name}/{key}")
    count, generated = check_sources(info, row["source"] | {"finalCommit": commit}, files, name,
                                     production_commit=production)
    verify_equal((target["matchedSourceDocuments"], target["embeddedGeneratedDocuments"]), (count, generated),
                 f"{name}/PDB/源文档")
    row.update(readme=readme, repository=repository, directInternalDependencies=EDGES.get(name, {}))


def compile_inputs(name, stage, original, original_root, tfm, r4_feed, output, records):
    assembly = Path(RELEASE_DLLS[name]).stem
    path = stage / f"artifacts/obj/{assembly}/project.assets.json"
    graph = read_json(path)
    resolved = {}
    for dep in EDGES[name]:
        package = (original["packages"] | original["publicPackages"])[dep]
        archive = verify_fingerprint(original_root, package["archive"])
        key = f"{dep}/{package['version']}"
        entry = graph["libraries"][key]
        produced_input = stage / "inputs" / archive.name
        verify_equal(package["archive"]["sha256"], sha256(produced_input), f"{name}/原生产输入包/{key}/SHA-256")
        graph_archive = produced_input
        if dep == CORE:
            graph_archive = checked_file(r4_feed, archive.name, package["publicEvidence"]["uploadSha256"])
            compare_packages(graph_archive, produced_input)
            records["r4CoreUpload"] = copy_evidence(output, graph_archive, f"records/r4-core-upload/{archive.name}",
                                                     package["publicEvidence"]["uploadSha256"])
        verify_equal(b64encode(sha512(graph_archive.read_bytes()).digest()).decode(), entry["sha512"],
                     f"{name}/生产还原图/{key}/SHA-512")
        target = package["targets"].get(tfm) or next(iter(package["targets"].values()))
        build = graph["targets"][tfm][key]
        require(target["asset"] in build["compile"], f"{name}/生产还原图/{key}/编译资产")
        with ZipFile(produced_input) as package_file:
            verify_equal(target["assetSha256"], bytes_sha256(package_file.read(target["asset"])),
                         f"{name}/原生产输入 DLL/{key}/SHA-256")
        resolved[dep] = {"version": package["version"], "archiveSha256": package["archive"]["sha256"],
                         "graphPackageSha512": entry["sha512"], "graphArchiveSha256": sha256(graph_archive),
                         "asset": target["asset"], "assetSha256": target["assetSha256"]}
    records[f"{name}.productionAssets"] = copy_evidence(output, path, f"records/{name}/project.assets.json")
    return resolved


def public_packages(original, original_root, output, preflight, signatures, downloads):
    verify_equal(original["publicPackages"].keys(), signatures.keys(), "R4 签名交接包集合")
    for name, row in original["publicPackages"].items():
        observation = preflight["publicPackages"][name]
        signature = signatures[name]
        receipt = downloads[name]
        verify_equal(row["archive"]["sha256"], observation["downloadSha256"], f"{name}/本轮匿名下载")
        verify_equal(receipt["uploadSha256"], observation["uploadSha256"], f"{name}/R4 上传摘要")
        verify_equal(signature["downloadSha256"], observation["downloadSha256"], f"{name}/R4 验签下载")
        verify_equal(signature["signatureMemberSha256"], observation["signatureMemberSha256"], f"{name}/签名成员")
        row["archive"] = copy_evidence(output, verify_fingerprint(original_root, row["archive"]),
                                       row["archive"]["path"], row["archive"]["sha256"])
        log = copy_evidence(output, Path(signature["r4SignatureLog"]), f"public/signatures/{name}.log",
                            signature["r4Signature"]["logSha256"])
        row["publicEvidence"] = {
            "uploadSha256": observation["uploadSha256"], "downloadSha256": observation["downloadSha256"],
            "signatureMemberSha256": observation["signatureMemberSha256"], "readback": observation["readback"],
            "signature": signature["r4Signature"], "signatureLog": log,
        }
    return original["publicPackages"]


def prepare(args, work):
    original_root = args.original_root
    output = args.output
    original = load_frozen_batch(original_root, args.original_sha256)
    require(original["schemaVersion"] == 1, "续接来源须为已验的原 R5 候选")
    preflight_path = checked_file(args.engine_evidence, "preflight-03/report.json", args.preflight_sha256)
    inspection_path = checked_file(args.engine_evidence, "inspection-03/report.json", args.engine_inspection_sha256)
    preflight, inspection = (read_json(path) for path in (preflight_path, inspection_path))
    verify_equal(args.original_sha256, preflight["originalBatchSha256"], "版本预检/原批次")
    engine_source = inspection["source"]
    output.mkdir()
    env = os.environ | {"DOTNET_CLI_HOME": str(work / "dotnet-home"), "DOTNET_NOLOGO": "1",
                        "NUGET_PACKAGES": str(work / "packages")}

    def run(command, cwd, label, overrides=None):
        return run_logged(command, cwd, label, args.logs, env | (overrides or {}))

    for name in ("global.json", "InspectDll.csproj", "Program.cs"):
        shutil.copyfile(R4_INSPECTION / name, work / name)
    (work / "NuGet.Config").write_text(CONFIG, encoding="utf-8")
    run([args.dotnet, "build", "InspectDll.csproj", "-c", "Release", "--disable-build-servers"], work, "inspector")
    inspector = work / "bin/Release/net10.0/InspectDll.dll"
    records = {
        "engineArchiveInspection": copy_evidence(output, inspection_path, "records/engine-archive-inspection.json",
                                                 args.engine_inspection_sha256),
        "versionPreflight": copy_evidence(output, preflight_path, "records/version-preflight.json", args.preflight_sha256),
    }
    batch = {key: original[key] for key in ("template", "publicRegistry", "verifiedDownloads")}
    for key in ("publicRegistry", "verifiedDownloads"):
        record = original[key]
        copy_evidence(output, verify_fingerprint(original_root, record), record["path"], record["sha256"])
    downloads = read_json(output / batch["verifiedDownloads"]["path"])["packages"]
    signatures = read_json(args.engine_evidence / "r4-signature-evidence.json")
    batch["publicPackages"] = public_packages(original, original_root, output, preflight, signatures, downloads)
    production_dirs = {ENGINE: args.engine_evidence / "production-01",
                       COLLECTION: original_root.parent / "collection", ADAPTER: original_root.parent / "adapter-02"}
    packages = deepcopy(original["packages"])
    for name in VERSIONS:
        row, stage = packages[name], production_dirs[name]
        source = row["source"]
        index = source_at(args.main_commit, source["path"])
        at_preflight = preflight["productionGitlinks"][source["path"]]
        verify_equal((index["repository"], index["baseCommit"]), (at_preflight["remote"], at_preflight["commit"]),
                     f"{name}/主仓 gitlink 预检")
        tfm = next(iter(row["targets"]))
        if name == ENGINE:
            verify_equal((source["compiledSourceCommit"], source["productionTree"]),
                         (engine_source["previousCommit"], engine_source["previousTree"]), "原引擎来源")
            final = engine_source["finalCommit"]
            source.update(compiledSourceCommit=engine_source["repositoryCommit"], productionTree=engine_source["tree"])
            row["targets"][tfm] = inspection["actual"]["target"] | {
                "pdbDebugChecksum": inspection["portablePdbBinding"]["actual"],
            }
        else:
            final = index["baseCommit"]
            patch = source["patch"]
            copy_evidence(output, verify_fingerprint(original_root, patch), patch["path"], patch["sha256"])
            row["compiledWith"] = compile_inputs(name, stage, original, original_root, tfm, args.r4_feed,
                                                 output, records)
        require((stage / "exit-code.txt").read_text().strip() == "0", f"{name}/原生产退出码")
        verify_equal(source["compiledSourceCommit"], (stage / "source-commit.txt").read_text().strip(),
                     f"{name}/生产 source-commit.txt")
        files = verify_source(name, row, final, work, run, output)
        hashes = receipt_hashes(stage / "packages.sha256", stage.name)
        for kind, relative in archive_paths(name, row).items():
            digest = row[kind]["sha256"]
            if name == ENGINE:
                digest = getattr(args, f"engine_{kind}_sha256")
                matches = [item for item in inspection["actual"]["archives"]
                           if Path(item["path"]).name == Path(relative).name]
                verify_equal([digest], [item["sha256"] for item in matches], f"{name}/{kind}/实物检查")
            verify_equal(digest, hashes[relative], f"{name}/{kind}/生产登记")
            row[kind] = copy_evidence(output, stage / relative, relative, digest)
        inspect(name, row, tfm, output, stage, work, args.dotnet, inspector, run, files)
        row["productionEvidence"] = "rebuilt" if name == ENGINE else "reused"
        row["source"]["mainGitlink"] = index["baseCommit"]
        for member in ("source-commit.txt", "packages.sha256", "exit-code.txt",
                       "pack.log" if name == ENGINE else "commands.log"):
            records[f"{name}/{member}"] = copy_evidence(output, stage / member, f"records/{name}/{member}")
        print(f"{name} {row['productionEvidence']} {source['productionTree']} {row['archive']['sha256']}", flush=True)
    batch.update(schemaVersion=2, packages=packages, records=records, release={
        "mainCommit": args.main_commit, "proposedTag": preflight["tag"], "tagTarget": None,
        "historicalBatchSha256": args.original_sha256, "uploadOrder": list(VERSIONS),
    })
    write_json(output / "batch.json", batch)


def verify(root, expected):
    batch = load_frozen_batch(root, expected)
    consumers(batch, root)
    print(f"R5 批次校验通过。{root / 'batch.json'} SHA-256 {expected}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    prepare_mode = modes.add_parser("prepare", help="用已核定的原候选、新引擎实物和验签记录制备待发批次")
    for option in ("original-root", "engine-evidence", "r4-feed", "output", "logs"):
        prepare_mode.add_argument(f"--{option}", type=Path, required=True)
    for option in ("original-sha256", "preflight-sha256", "engine-inspection-sha256",
                   "engine-archive-sha256", "engine-symbols-sha256", "main-commit"):
        prepare_mode.add_argument(f"--{option}", required=True)
    prepare_mode.add_argument("--dotnet", default="dotnet")
    verify_mode = modes.add_parser("verify", help="用独立登记的摘要离线只读核验批次")
    verify_mode.add_argument("--batch-root", type=Path, required=True)
    verify_mode.add_argument("--batch-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.mode == "verify":
            verify(args.batch_root.resolve(), args.batch_sha256)
        else:
            for key in ("original_root", "engine_evidence", "r4_feed", "output", "logs"):
                setattr(args, key, getattr(args, key).resolve())
            args.logs.mkdir()
            with TemporaryDirectory(dir=args.logs) as scratch:
                prepare(args, Path(scratch))
            verify(args.output, sha256(args.output / "batch.json"))
    except subprocess.CalledProcessError as error:
        print(f"R5 待发批次失败：{error.stderr.decode(errors='replace').strip()}", file=sys.stderr)
        return 1
    except (VerificationError, OSError, ValueError, KeyError, TypeError, ParseError, BadZipFile) as error:
        print(f"R5 待发批次失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
