"""核对 R5 三包批次及保留的 R4 公开输入。"""

import re
from pathlib import Path
from zipfile import ZipFile

from r2_packages import NUGET_SOURCE
from r3_automapper_packages import ADAPTER, COLLECTION, CORE, ENGINE
from r3_leaf_packages import bytes_sha256, checked_file
from r4_candidate_batch import verify_fingerprint
from r4_release_candidate import MANIFEST
from verify import read_json, require, sha256


VERSIONS = {ENGINE: "14.0.1", COLLECTION: "11.0.1", ADAPTER: "10.5.2"}
EDGES = {
    ADAPTER: {ENGINE: "[14.0.1]", COLLECTION: "[11.0.1]", CORE: "[10.5.1]"},
    COLLECTION: {ENGINE: "[14.0.1]"},
}
PUBLIC_REGISTRY = "public/R4-PACKAGE-CHECKSUMS.json"


def load_frozen_batch(root, expected_digest, *, verify_carried=True):
    root = Path(root).resolve()
    require(expected_digest and re.fullmatch(r"[0-9a-f]{64}", expected_digest),
            "需要独立登记的 R5 批次 SHA-256")
    batch = read_json(checked_file(root, "batch.json", expected_digest))
    r4 = read_json(MANIFEST)
    require(batch["schemaVersion"] in (1, 2) and batch["template"] == r4["template"],
            "R5 批次格式或固定模板不符")
    require(batch["packages"].keys() == VERSIONS.keys() and
            batch["publicPackages"].keys() == r4["packages"].keys() - VERSIONS.keys(),
            "R5 三包或复用的十个 R4 公开包不完整")
    for name, version in VERSIONS.items():
        row = batch["packages"][name]
        stem = f"{name}.{version}"
        require(row["version"] == version, f"{name} 候选版本不符")
        for kind, expected in (("archive", f"feed/{stem}.nupkg"), ("symbols", f"symbols/{stem}.snupkg")):
            require(row[kind]["path"] == expected, f"{name} {kind} 路径不符")
            verify_fingerprint(root, row[kind])
    for folder, kind in (("feed", "archive"), ("symbols", "symbols")):
        require({path.name for path in (root / folder).iterdir()} ==
                {Path(row[kind]["path"]).name for row in batch["packages"].values()},
                f"R5 {folder} 含未登记的成员")
    registry = verify_fingerprint(root, batch["publicRegistry"])
    downloads = verify_fingerprint(root, batch["verifiedDownloads"])
    require(batch["publicRegistry"]["path"] == PUBLIC_REGISTRY, "公开校验清单路径不符")
    release, verified = read_json(registry), read_json(downloads)
    require(release["verifiedDownloadsSha256"] == sha256(downloads)
            and release["releaseManifestSha256"] == verified["manifestSha256"],
            "R4 公开校验清单与验签下载登记不符")
    for name, row in batch["publicPackages"].items():
        version = r4["packages"][name]["version"]
        require(row["version"] == release["packages"][name]["version"] == verified["packages"][name]["version"]
                == version and row["archive"]["path"] == f"public/{name}.{version}.nupkg"
                and row["archive"]["sha256"] == verified["packages"][name]["downloadSha256"]
                == release["packages"][name]["mainPackage"]["anonymousDownloadSha256"],
                f"{name} R4 公开版本或验签下载摘要不符")
        if verify_carried:
            verify_fingerprint(root, row["archive"])
    for record in batch["records"].values():
        verify_fingerprint(root, record)
    if batch["schemaVersion"] == 2:
        verify_release_batch(root, batch, verified["packages"], verify_carried=verify_carried)
    return batch


def verify_release_batch(root, batch, verified, *, verify_carried):
    release = batch["release"]
    require(release["uploadOrder"] == list(VERSIONS), "R5 上传队列必须为引擎、Collection、适配器")
    for name, row in batch["packages"].items():
        require(row["directInternalDependencies"] == EDGES.get(name, {}), f"{name} 待发精确依赖不符")
        if "patch" in row["source"]:
            verify_fingerprint(root, row["source"]["patch"])
    if verify_carried:
        for name, row in batch["publicPackages"].items():
            verify_carried_package(root, name, row, verified[name])


def verify_carried_package(root, name, row, verified):
    evidence = row["publicEvidence"]
    log = verify_fingerprint(root, evidence["signatureLog"])
    archive = verify_fingerprint(root, row["archive"])
    require(evidence["downloadSha256"] == verified["downloadSha256"] == row["archive"]["sha256"]
            and evidence["uploadSha256"] == verified["uploadSha256"]
            and evidence["signature"]["repository"] == NUGET_SOURCE
            and evidence["signature"]["logSha256"] == sha256(log),
            f"{name} R4 公开验签证据与下载或原日志不符")
    with ZipFile(archive) as package:
        require(package.namelist().count(".signature.p7s") == 1
                and bytes_sha256(package.read(".signature.p7s")) == evidence["signatureMemberSha256"],
                f"{name} R4 公开包签名成员不符")
