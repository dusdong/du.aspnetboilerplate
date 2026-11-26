#!/usr/bin/env python3
"""从 R3 冻结实包核对 R4 组合清单。"""

import argparse
from pathlib import Path
import re
import subprocess
import sys
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from r2_packages import metadata_groups, nuspec_metadata, package_archive
from r3_automapper_packages import stack_package
from r3_leaf_packages import bytes_sha256, checked_file
from r3_template_net9_packages import normalized_range
from verify import ROOT, VerificationError, read_json, require, sha256


MANIFEST = ROOT / "eng/r4_release_candidate.json"
REFERENCE = ROOT / "eng/r3_template_net9_reference.json"
PRODUCERS = {"framework": "aspnetboilerplate", "engine": "AutoMapper", "collection": "AutoMapper.Collection"}
TEMPLATE = "module-zero-core-template"
MAPPING_PRODUCERS = {"Du.AutoMapper": "engine", "Du.AutoMapper.Collection": "collection"}
COMMIT = re.compile(r"[0-9a-f]{40}")
MISSING = object()


def verify_equal(expected, actual, field):
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(expected.keys() | actual.keys()):
            verify_equal(expected.get(key, MISSING), actual.get(key, MISSING), f"{field}/{key}")
        return

    require(expected == actual,
            f"{field}：预期 {'缺失' if expected is MISSING else expected!s}，"
            f"实际 {'缺失' if actual is MISSING else actual!s}")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout.strip()


def source_at(base, path):
    entry = git("ls-tree", base, "--", path).split(maxsplit=3)
    require(len(entry) == 4 and entry[:2] == ["160000", "commit"] and
            COMMIT.fullmatch(entry[2]) and entry[3] == path,
            f"{base} / {path}：预期固定的子模块 gitlink，实际 {entry}")
    return {
        "path": path,
        "repository": git("config", "--blob", f"{base}:.gitmodules", "--get", f"submodule.{path}.url"),
        "baseCommit": entry[2],
    }


def verify_gitlinks(manifest):
    anchor = manifest["gitlinkCommit"]
    require(COMMIT.fullmatch(anchor), f"gitlinkCommit：预期完整 Git SHA，实际 {anchor}")
    for producer, path in PRODUCERS.items():
        actual = source_at(anchor, path)
        declared = manifest["producers"][producer]
        verify_equal(declared["finalCommit"], actual["baseCommit"], f"{producer}/gitlink")
        verify_equal(declared["repository"], actual["repository"], f"{producer}/gitlink/repository")
    verify_equal(manifest["template"], source_at(anchor, TEMPLATE), "template/gitlink")


def frozen_packages(frozen_root, producers):
    rows = {}
    for batch, registration in read_json(REFERENCE)["batches"].items():
        for record in registration["manifests"].values():
            checked_file(frozen_root, record["path"], record["sha256"])
        for row in registration["packages"]:
            name = row["id"]
            require(name not in rows, f"冻结包登记重复：{name}")
            producer = MAPPING_PRODUCERS.get(name, "framework")
            repository = registration["sources"][producer]
            verify_equal(producers[producer]["repository"], repository, f"{name}/baseline/repository")
            rows[name] = {**row, "batch": batch, "producer": producer, "repository": repository}

    require(len(rows) == 13 and sum(name.startswith("Du.Abp") for name in rows) == 11 and
            MAPPING_PRODUCERS.keys() <= rows.keys(),
            f"冻结包登记的 ID 集合不符：{sorted(rows)}")
    return {name: expected_package(frozen_root, rows, row) for name, row in sorted(rows.items())}


def expected_package(frozen_root, rows, row):
    name, version = row["id"], row["version"]
    repository = row["repository"]
    core = row["batch"] == "r2"
    if core:
        tfms = ("net9.0", "net10.0")
    else:
        tfms = ("net8.0",) if name in MAPPING_PRODUCERS else ("net9.0",)
    assets = {tfm: f"lib/{tfm}/{Path(row['asset']).name}" for tfm in tfms}
    path = checked_file(frozen_root, row["archive"], row["archiveSha256"])

    with ZipFile(path) as archive:
        try:
            package_archive(archive, set(assets.values()))
            metadata = nuspec_metadata(archive)
            verify_equal(name, metadata.findtext("id"), "nuspec/id")
            verify_equal(version, metadata.findtext("version"), "nuspec/version")
            verify_equal(repository, metadata.find("repository").get("url"), "nuspec/repository")
            require(not metadata.findall("dependencies/dependency"), "nuspec 含未分组的包依赖")
            require(not metadata.findall("frameworkReferences/frameworkReference") and
                    not metadata.findall("frameworkAssemblies/frameworkAssembly"),
                    "nuspec 含未登记的框架引用声明")
            groups = metadata_groups(metadata, "dependencies", "id")
            frameworks = metadata_groups(metadata, "frameworkReferences", "name")
            verify_equal(sorted(tfms), sorted(groups), "nuspec/依赖目标组")
            require(frameworks.keys() <= groups.keys(), f"nuspec 含额外的框架引用目标组：{sorted(frameworks)}")

            targets = {}
            for tfm, asset in assets.items():
                internal, third_party = {}, {}
                for dependency, record in sorted(groups[tfm].items()):
                    declared = record["version"]
                    if not stack_package(dependency):
                        third_party[dependency] = declared
                        continue

                    field = f"{tfm}/baseline/internalDependencies/{dependency}"
                    require(dependency in rows, f"{field}：预期有冻结包登记，实际缺失")
                    prior = rows[dependency]["version"]
                    expected = prior if core else f"[{prior}]"
                    verify_equal(normalized_range(expected), normalized_range(declared), field)
                    stable = prior.split("-", 1)[0]
                    internal[dependency] = stable if core else f"[{stable}]"

                digest = bytes_sha256(archive.read(asset))
                if asset == row["asset"]:
                    verify_equal(row["assetSha256"], digest, f"{tfm}/baselineAssetSha256")
                targets[tfm] = {
                    "asset": asset,
                    "baselineAssetSha256": digest,
                    "internalDependencies": internal,
                    "thirdPartyDependencies": third_party,
                    "frameworkReferences": sorted(frameworks.get(tfm, {})),
                }
        except (AttributeError, KeyError, ParseError, VerificationError) as error:
            raise VerificationError(f"{name}（{path}）：{error}") from error

    return {
        "version": version.split("-", 1)[0],
        "producer": row["producer"],
        "projectUrl": repository.removesuffix(".git"),
        "baseline": {"id": name, "version": version, "archiveSha256": row["archiveSha256"]},
        "targets": targets,
    }


def verify_manifest(manifest, frozen_root):
    verify_equal(1, manifest["schemaVersion"], "schemaVersion")
    base = manifest["baseCommit"]
    require(COMMIT.fullmatch(base), f"baseCommit：预期完整 Git SHA，实际 {base}")
    verify_equal({"path": REFERENCE.relative_to(ROOT).as_posix(), "sha256": sha256(REFERENCE)},
                 manifest["baselineReference"], "baselineReference")
    verify_equal(sorted(PRODUCERS), sorted(manifest["producers"]), "producers")

    producers = {}
    for name, path in PRODUCERS.items():
        source = source_at(base, path)
        declared = manifest["producers"][name]
        final = declared["finalCommit"]
        require(isinstance(final, str) and COMMIT.fullmatch(final),
                f"producers/{name}/finalCommit：预期完整 Git SHA，实际 {final}")
        verify_equal({**source, "finalCommit": final}, declared, f"producers/{name}")
        producers[name] = source

    verify_equal(source_at(base, TEMPLATE), manifest["template"], "template")
    verify_gitlinks(manifest)
    packages = frozen_packages(frozen_root, producers)
    verify_equal(packages, manifest["packages"], "packages")
    return packages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-root", type=Path, required=True, help="R3 登记中所有归档与生产清单的共同根目录")
    parser.add_argument("--manifest", type=Path, default=MANIFEST, help="待核对的 R4 组合清单")
    args = parser.parse_args()
    try:
        packages = verify_manifest(read_json(args.manifest), args.frozen_root.resolve())
    except subprocess.CalledProcessError as error:
        print(f"R4 组合清单核对失败：{error.stderr.strip()}", file=sys.stderr)
        return 1
    except (VerificationError, OSError, ValueError, KeyError, TypeError, BadZipFile) as error:
        print(f"R4 组合清单核对失败：{error}", file=sys.stderr)
        return 1

    targets = [target for package in packages.values() for target in package["targets"].values()]
    internal = sum(len(target["internalDependencies"]) for target in targets)
    third_party = sum(len(target["thirdPartyDependencies"]) for target in targets)
    frameworks = sum(len(target["frameworkReferences"]) for target in targets)
    print(f"R4 组合清单核对通过。{len(packages)} 个冻结主包，{len(targets)} 个目标组，"
          f"{internal} 条内部依赖，{third_party} 条第三方依赖，{frameworks} 条框架引用。")
    print(f"{args.manifest} SHA-256 {sha256(args.manifest)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
