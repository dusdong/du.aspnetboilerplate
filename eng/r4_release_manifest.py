#!/usr/bin/env python3
"""从 R4 固定交接原件生成首次公开发行清单。"""

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from r2_packages import NUGET_SOURCE, metadata_groups, nuspec_metadata
from r3_leaf_packages import checked_file
from r3_template_net9_packages import normalized_range
from r4_candidate_batch import load_frozen_batch
from r4_release_candidate import MANIFEST, source_at, verify_equal, verify_gitlinks
from r4_template_recheck import read_receipt
from verify import VerificationError, read_json, require


RELEASE = {
    "repository": "https://github.com/dusdong/du.aspnetboilerplate",
    "tag": "v10.5.1",
    "commit": "5758c8186b68dcc42ecc90164cf9d3f53cf3345e",
}
HANDOFF_SHA256 = "097e0eee66420797c7f77dc52a593990311ebe6ebc120c81a17bbac2255fc86f"
BATCH_SHA256 = "4d25f237938d04aeb985c2057a6287ba0f18425b94d73e9c494e313684470757"
HANDOFF_FILES = 209
PACKAGE_TABLE = ("id", "version", "targets", "kind", "bytes", "sha256", "commit", "path")


def verify_handoff(root):
    receipt = read_receipt(root, HANDOFF_SHA256)
    verify_equal(HANDOFF_FILES, len(receipt), "SHA256SUMS/条目数")
    verify_equal(BATCH_SHA256, receipt.get("frozen/batch.json"), "SHA256SUMS/frozen/batch.json")
    require("packages.tsv" in receipt, "SHA256SUMS 缺少 packages.tsv")
    for member, digest in receipt.items():
        path = checked_file(root, member, digest)
        verify_equal(root / member, path, f"SHA256SUMS/{member}/原件路径")
    return receipt


def verify_package_table(root, receipt, packages, producers):
    expected = {}
    for name, row in packages.items():
        targets = sorted(row["targets"])
        for kind in ("archive", "symbols"):
            record = row[kind]
            path = record["path"]
            verify_equal(record["sha256"], receipt.get(path), f"SHA256SUMS/{path}")
            expected[name, kind] = (
                row["version"], targets, str(record["bytes"]), record["sha256"],
                producers[row["producer"]]["finalCommit"], path,
            )

    actual = {}
    with (root / "packages.tsv").open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        verify_equal(list(PACKAGE_TABLE), next(reader, []), "packages.tsv/表头")
        for line, values in enumerate(reader, 2):
            verify_equal(len(PACKAGE_TABLE), len(values), f"packages.tsv/第 {line} 行/字段数")
            name, version, targets, kind, size, digest, commit, path = values
            require((name, kind) not in actual, f"packages.tsv/{name}/{kind} 重复")
            actual[name, kind] = (version, sorted(targets.split(",")), size, digest, commit, path)

    verify_equal(sorted(expected), sorted(actual), "packages.tsv/归档清单")
    for name, kind in expected:
        for field, value, listed in zip(
            ("version", "targets", "bytes", "sha256", "commit", "path"),
            expected[name, kind], actual[name, kind],
        ):
            verify_equal(value, listed, f"packages.tsv/{name}/{kind}/{field}")


def verify_release_sources(manifest):
    verify_gitlinks(manifest)
    for source in manifest["producers"].values():
        path = source["path"]
        tag_source = source_at(RELEASE["commit"], path)
        verify_equal(source["finalCommit"], tag_source["baseCommit"], f"{RELEASE['tag']}/{path}/gitlink")
        verify_equal(source["repository"], tag_source["repository"], f"{RELEASE['tag']}/{path}/repository")
    template = manifest["template"]
    verify_equal(template, source_at(RELEASE["commit"], template["path"]), f"{RELEASE['tag']}/template")


def verify_nuspec(path, name, row, source, internal_ids=None):
    try:
        with ZipFile(path) as archive:
            metadata = nuspec_metadata(archive)
        require(metadata is not None, "缺少 nuspec metadata")
        for key, value in (("id", name), ("version", row["version"]), ("projectUrl", row["projectUrl"])):
            verify_equal(value, metadata.findtext(key), f"nuspec/{key}")
        repository = metadata.find("repository")
        require(repository is not None, "缺少 nuspec repository")
        for key, value in (("type", "git"), ("url", source["repository"]), ("commit", source["finalCommit"])):
            verify_equal(value, repository.get(key), f"nuspec/repository/{key}")
        if internal_ids is None:
            return

        require(not metadata.findall("dependencies/dependency"), "nuspec 含未分组的包依赖")
        groups = metadata_groups(metadata, "dependencies", "id")
        verify_equal(sorted(row["targets"]), sorted(groups), "nuspec/依赖目标组")
        result = {}
        for tfm, deps in sorted(groups.items()):
            declared = row["targets"][tfm]
            expected = declared["internalDependencies"] | declared["thirdPartyDependencies"]
            ranges = {dep: spec["version"] for dep, spec in deps.items()}
            verify_equal({dep: normalized_range(value) for dep, value in expected.items()},
                         {dep: normalized_range(value) for dep, value in ranges.items()}, f"nuspec/{tfm}/dependencies")
            result[tfm] = {"internalDependencies": {dep: ranges[dep] for dep in sorted(ranges.keys() & internal_ids)}}
        return result
    except (BadZipFile, KeyError, ParseError, VerificationError) as error:
        raise VerificationError(f"{path.name}：{error}") from error


def dependency_order(packages):
    remaining = {name: set(row["directInternalDependencies"]) for name, row in packages.items()}
    order = []
    while remaining:
        ready = sorted(name for name, deps in remaining.items() if not deps)
        require(ready, f"内部依赖无法排序：{sorted(remaining)}")
        order.extend(ready)
        remaining = {name: deps.difference(ready) for name, deps in remaining.items() if name not in ready}
    return order


def preflight(root):
    root = root.resolve()
    receipt = verify_handoff(root)
    batch = load_frozen_batch(root / "frozen", BATCH_SHA256)
    manifest = read_json(MANIFEST)
    verify_release_sources(manifest)

    producers, registered = batch["producers"], manifest["packages"]
    packages = {}
    for name, frozen in batch["packages"].items():
        row = registered[name]
        source = producers[row["producer"]]
        archives = {
            kind: {**frozen[kind], "path": f"frozen/{frozen[kind]['path']}"}
            for kind in ("archive", "symbols")
        }
        targets = verify_nuspec(root / archives["archive"]["path"], name, row, source, registered.keys())
        verify_nuspec(root / archives["symbols"]["path"], name, row, source)
        dependencies = {dep for target in targets.values() for dep in target["internalDependencies"]}
        packages[name] = {
            "version": row["version"], "producer": row["producer"], **archives, "targets": targets,
            "directInternalDependencies": {dep: registered[dep]["version"] for dep in sorted(dependencies)},
        }

    verify_package_table(root, receipt, packages, producers)
    return {
        "schemaVersion": 1,
        "release": RELEASE,
        "nugetSource": NUGET_SOURCE,
        "qualificationCommit": batch["gitlinkCommit"],
        "handoff": {"checksumsSha256": HANDOFF_SHA256, "batchSha256": BATCH_SHA256, "files": len(receipt)},
        "producers": producers,
        "template": batch["template"],
        "publishOrder": dependency_order(packages),
        "packages": packages,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True, help="publish-handoff-v2 交接目录")
    parser.add_argument("--output", type=Path, required=True, help="交接目录外的首发清单 JSON 路径")
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        require(not output.is_relative_to(args.handoff.resolve()), "输出路径须位于交接目录之外")
        report = preflight(args.handoff)
        data = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if output.exists():
            require(output.read_bytes() == data, f"输出路径已存在且内容不同：{output}")
        else:
            with output.open("xb") as stream:
                stream.write(data)
        print(f"首发预检通过，核对 {len(report['packages'])} 个主包及其符号包。清单：{output}")
    except (BadZipFile, KeyError, OSError, subprocess.CalledProcessError, ValueError, VerificationError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(f"首发预检失败：{detail or error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
