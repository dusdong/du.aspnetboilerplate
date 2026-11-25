"""核对 Module Zero 冻结候选的独立源码证明、包及生产证据。"""

import json
from pathlib import Path
from zipfile import ZipFile

from r2_packages import NUGET_SOURCE, SDK, commit_tree, framework_package, package_archive, verify_source
from r3_leaf_packages import (R2_VERSION, SOURCE_PROOF, TFM, bytes_sha256, checked_file, package_details,
                              read_r2, verify_repository)
from verify import read_json, require, sha256


R2_IDS = ("Du.Abp", "Du.Abp.EntityFramework.Common", "Du.Abp.EntityFrameworkCore")
R3_IDS = ("Du.Abp.Zero.Common", "Du.Abp.ZeroCore", "Du.Abp.ZeroCore.EntityFrameworkCore")
TOP_PACKAGE = R3_IDS[-1]
ASP_NET = "Microsoft.AspNetCore.App"


def expected_edges(version):
    core, common, ef = R2_IDS
    zero, zero_core, zero_ef = R3_IDS
    return {core: {}, common: {core: R2_VERSION}, ef: {common: R2_VERSION},
            zero: {core: f"[{R2_VERSION}]"}, zero_core: {zero: f"[{version}]"},
            zero_ef: {zero_core: f"[{version}]", ef: f"[{R2_VERSION}]"}}


def read_r3(feed, symbols, name, version, entry, source, edges):
    assembly = name.removeprefix("Du.")
    asset, pdb = f"lib/{TFM}/{assembly}.dll", f"lib/{TFM}/{assembly}.pdb"
    path = checked_file(feed, f"{name}.{version}.nupkg", entry["package"]["sha256"])
    symbol = checked_file(symbols, f"{name}.{version}.snupkg", entry["symbols"]["sha256"])
    bundle = entry["targets"][TFM]
    require((entry["package"]["file"], entry["symbols"]["file"]) == (path.name, symbol.name) and
            set(entry["targets"]) == {TFM} and
            (entry["assemblyName"], entry["rootNamespace"], bundle["path"], bundle["pdbPath"]) ==
            (assembly, "Abp", asset, pdb), f"{name} 清单包名、目标或程序集身份不符")
    with ZipFile(path) as archive, ZipFile(symbol) as debug:
        metadata, groups, frameworks = package_details(archive, name, version)
        symbol_metadata, _, _ = package_details(debug, name, version)
        package_archive(archive, {asset})
        package_archive(debug, {pdb})
        dependencies = {dep: item["version"] for dep, item in groups[TFM].items()}
        internal = {dep: value for dep, value in dependencies.items() if framework_package(dep)}
        require(internal == entry["dependencies"] == edges,
                f"{name} nuspec 框架依赖 ID 或范围不符，预期 {edges}，实际 {internal}")
        expected_frameworks = {TFM: {ASP_NET}} if name == R3_IDS[1] else {}
        require(set(groups) == {TFM} and {tfm: set(refs) for tfm, refs in frameworks.items()} == expected_frameworks,
                f"{name} nuspec 目标组或共享框架不符")
        proof = {key: source[key] for key in ("baseCommit", "baseTree", "tree", "patchSha256")}
        if source["mode"] == "committed":
            proof["commit"] = source["commit"]
        verify_repository(metadata, path, source, proof)
        verify_repository(symbol_metadata, symbol, source, proof)
        require(json.loads(archive.read(SOURCE_PROOF)) == proof, f"{name} 包内源码证明不符")
        require(metadata.findtext("license") == "LICENSE.md" and metadata.findtext("icon") == "abp_nupkg.png",
                f"{name} 许可证或图标声明不符")
        for file, digest in source["assets"].items():
            require(bytes_sha256(archive.read(file)) == digest, f"{name} {file} 与候选源码不符")
        require(bytes_sha256(archive.read(asset)) == bundle["sha256"], f"{name} {asset} SHA-256 不符")
        require(bytes_sha256(debug.read(pdb)) == bundle["pdbSha256"], f"{name} {pdb} SHA-256 不符")
    return {"id": name, "version": version, "archive": str(path), "archiveSha256": entry["package"]["sha256"],
            "symbol": str(symbol), "symbolSha256": entry["symbols"]["sha256"], "pdbSha256": bundle["pdbSha256"],
            "assembly": assembly, "asset": asset, "assetSha256": bundle["sha256"], "dependencies": dependencies,
            "frameworkReferences": sorted(frameworks.get(TFM, {}))}


def verify_packages(run, manifest_path, declared, registration, r3_feed, symbols, r2_feed):
    version = declared["version"]
    manifest_root = manifest_path.parent
    require(declared["schemaVersion"] == 1 and declared["sdk"] == SDK, "R3 生产清单版本或 SDK 不符")
    proof = checked_file(manifest_root, SOURCE_PROOF, registration["sourceProofSha256"])
    require(read_json(proof) == declared["sourceProof"], "独立 R3 源码证明与生产清单不符")
    source = verify_source(run, manifest_path, declared)
    checkout = registration["frameworkCheckout"]
    checkout_tree = commit_tree(run, run.repo / "aspnetboilerplate", checkout, "r3-framework-checkout")
    require(declared["frameworkCheckout"] == {"commit": checkout, "tree": checkout_tree} and
            declared["superproject"]["frameworkGitlink"] == checkout and
            source["baseTree"] == declared["sourceProof"]["baseTree"],
            "R3 生产检出、主仓 gitlink 或实际基树不符")
    template = run.git(run.repo, "production-template-gitlink.log", "ls-tree",
                       declared["superproject"]["commit"], "--", "module-zero-core-template")
    require(template == f"160000 commit {registration['templateGitlink']}\tmodule-zero-core-template",
            "生产主仓缺少已登记的固定模板 gitlink")

    reference_path = run.repo / "eng/r3_r2_reference.json"
    reference = read_json(reference_path)
    r2_manifest = checked_file(r2_feed.parent, "manifest.json", reference["evidenceSha256"]["manifest"])
    r2_declared = read_json(r2_manifest)
    r2_source = verify_source(run, r2_manifest, r2_declared, label="r2-source")
    r2 = declared["r2"]
    ordinary = commit_tree(run, run.repo / "aspnetboilerplate", registration["ordinaryBaselineCommit"], "ordinary")
    require(ordinary == reference["frameworkTree"] == r2_source["tree"] and
            r2["sourceProof"] == r2_declared["sourceProof"] and
            r2["manifestSha256"] == sha256(r2_manifest), "R2 生产树、清单或普通 Release 对照不符")
    require(reference["version"] == r2_declared["version"] == R2_VERSION and set(r2["packages"]) == set(R2_IDS),
            "R2 生产版本或实物集合不符")
    r2_proof = r2_feed.parent / "du-core-candidate-source.json"
    require(read_json(r2_proof) == r2_declared["sourceProof"], "独立 R2 源码证明与生产清单不符")

    edges = expected_edges(version)
    packages = {}
    for name in R2_IDS:
        package = read_r2(r2_feed, reference, name)
        expected = r2["packages"][name]
        require(package["sourceProof"] == r2_declared["sourceProof"] and
                (package["archiveSha256"], package["asset"], package["assetSha256"], package["version"]) ==
                (expected["archiveSha256"], expected["assetPath"], expected["assetSha256"], expected["version"]) and
                edges[name] == expected["dependencies"], f"{name} R2 原包与两批生产登记不符")
        packages[name] = package
    require(set(declared["packages"]) == set(declared["production"]) == set(R3_IDS),
            "R3 候选包或生产证据集合不符")
    production = {}
    for name in R3_IDS:
        packages[name] = read_r3(r3_feed, symbols, name, version, declared["packages"][name], source, edges[name])
        proof_files = declared["production"][name]
        require({"evaluation.json", "project.assets.json", "compiler.json", "restore.log", "pack.log",
                 "nuspec", "symbols.nuspec", "restore-inputs.json"} <= proof_files.keys(),
                f"{name} 缺少独立生产阶段原始证据")
        production[name] = {kind: str(checked_file(manifest_root, item["path"], item["sha256"]))
                            for kind, item in proof_files.items()}
    require(declared["restore"]["source"] == NUGET_SOURCE, "R3 生产第三方 NuGet 源不符")
    production["restore"] = {
        kind: str(checked_file(manifest_root, declared["restore"][kind]["path"], declared["restore"][kind]["sha256"]))
        for kind in ("config", "commands")
    }
    return {"source": source, "r2Source": r2_source, "r2Manifest": str(r2_manifest),
            "r2ProofSha256": sha256(r2_proof),
            "r2ReferenceSha256": sha256(reference_path), "packages": packages, "production": production}
