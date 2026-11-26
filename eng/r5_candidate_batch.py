"""核对 R5 三包批次及保留的 R4 公开输入。"""

import re
from pathlib import Path

from r3_automapper_packages import ADAPTER, COLLECTION, CORE, ENGINE
from r3_leaf_packages import checked_file
from r4_candidate_batch import verify_fingerprint
from r4_release_candidate import MANIFEST
from verify import read_json, require, sha256


VERSIONS = {ENGINE: "14.0.1", COLLECTION: "11.0.1", ADAPTER: "10.5.2"}
EDGES = {
    ADAPTER: {ENGINE: "[14.0.1]", COLLECTION: "[11.0.1]", CORE: "[10.5.1]"},
    COLLECTION: {ENGINE: "[14.0.1]"},
}
PUBLIC_REGISTRY = "public/R4-PACKAGE-CHECKSUMS.json"


def load_frozen_batch(root, expected_digest):
    root = Path(root).resolve()
    require(re.fullmatch(r"[0-9a-f]{64}", expected_digest), "需要独立登记的 R5 批次 SHA-256")
    batch = read_json(checked_file(root, "batch.json", expected_digest))
    r4 = read_json(MANIFEST)
    require(batch["schemaVersion"] == 1 and batch["template"] == r4["template"],
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
        verify_fingerprint(root, row["archive"])
    for record in batch["records"].values():
        verify_fingerprint(root, record)
    return batch
