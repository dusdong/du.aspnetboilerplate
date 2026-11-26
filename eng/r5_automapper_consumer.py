"""从独立登记的 R5 三包批次启动经典 ABP 并复验映射业务。"""

import argparse
import os
from pathlib import Path
import re
import shutil
import sys
from tempfile import gettempdir
from zipfile import BadZipFile, ZipFile
from xml.etree.ElementTree import ParseError

from r2_packages import metadata_groups, nuspec_metadata, write_json
from r3_automapper_business import OriginalBusinessRun
from r3_automapper_packages import ADAPTER, CORE, ENGINE, ZERO, check_archive, check_edges
from r3_automapper_verify import CandidateRun, compare_business, compare_projection
from r4_candidate_batch import verify_fingerprint
from r5_candidate_batch import EDGES, load_frozen_batch
from verify import VerificationError, require, sha256


ZERO_COMMON = "Du.Abp.Zero.Common"


def consumers(batch, root):
    packages = {}
    for name, row in (batch["packages"] | batch["publicPackages"]).items():
        if name not in {*batch["packages"], CORE, ZERO, ZERO_COMMON}:
            continue
        is_candidate = name in batch["packages"]
        tfm = next(iter(row["targets"])) if is_candidate else "net9.0"
        target = row["targets"][tfm]
        identity = target["assembly"]
        full_name = (f"{identity['name']}, Version={identity['version']}, Culture={identity['culture']}, "
                     f"PublicKeyToken={identity['publicKeyToken'] or 'null'}")
        path = verify_fingerprint(root, row["archive"])
        packages[name] = {
            "id": name, "version": row["version"], "target": tfm,
            "archive": str(path), "archiveSha256": row["archive"]["sha256"],
            "asset": target["asset"], "assetSha256": target["assetSha256"],
            "assembly": identity["name"], "fullName": full_name,
        }
        edges = EDGES.get(name, {})
        if is_candidate:
            deps = check_archive(path, packages[name], edges)
        else:
            with ZipFile(path) as archive:
                metadata = nuspec_metadata(archive)
                require((metadata.findtext("id"), metadata.findtext("version")) == (name, row["version"]),
                        f"{name} 公开 nuspec 身份不符")
                group = metadata_groups(metadata, "dependencies", "id")[tfm]
                deps = {dep: value["version"] for dep, value in group.items()}
            edges = {dep: f"[{row['version']}]" for dep in deps if dep in (CORE, ZERO_COMMON)}
            check_edges(name, deps, edges)
        packages[name]["dependencies"] = deps
    return packages


class PatchRun(CandidateRun):
    def __init__(self, evidence, dotnet, packages, minimal):
        self.public_packages = tuple(name for name in (CORE, ZERO, ZERO_COMMON) if name in packages)
        edges = {name: {dep: expected for dep, expected in row["dependencies"].items() if dep in packages}
                 for name, row in packages.items()}
        super().__init__(evidence, dotnet, packages, edges, minimal=minimal)
        self.report["profile"] = f"r5-automapper-{self.app}"
        self.save()

    def run_dotnet(self, command, log):
        if command[0] == "build":
            command += ["--verbosity", "normal"]
        return super().run_dotnet(command, log)

    def build(self):
        super().build()
        references = {}
        compiler = re.compile(rb'/csc(?:\.dll)?[" ]')
        with self.evidence_file("build.log").open("rb") as log:
            csc = [line for line in log if compiler.search(line)]
        for name, row in self.frozen.items():
            library = read_graph_library(self.graph, name, row["version"])
            reference = self.cache / library / row["asset"]
            flags = (f'/reference:"{reference}"'.encode(), f"/reference:{reference} ".encode())
            require(any(any(flag in line for flag in flags) for line in csc)
                    and sha256(reference) == row["assetSha256"], f"{name} 缺少已登记的实际 Csc 引用")
            references[name] = {"path": str(reference), "sha256": sha256(reference)}
        write_json(self.evidence_file("compile-references.json"), references)


def read_graph_library(graph, name, version):
    path = Path(graph["packages"][name]["archive"]["path"]).parent
    require(path == Path(name.lower()) / version, f"{name} 缓存目录不符：{path}")
    return path


def prepare_run(output, label):
    path = output / label
    path.mkdir()
    volumes = [path, Path(gettempdir())]
    require(all(os.access(volume, os.W_OK) and shutil.disk_usage(volume).free >= 2 * 1024**3
                for volume in volumes), f"{label} 缓存或证据卷不可写或可用空间不足")
    write_json(path / "capacity.json", {str(volume): shutil.disk_usage(volume).free for volume in volumes})
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--batch-sha256", required=True)
    parser.add_argument("--dotnet", type=Path, default=shutil.which("dotnet"))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    stage = "冻结批次摘要、归档与 nuspec"
    try:
        root = args.batch_root.resolve()
        batch = load_frozen_batch(root, args.batch_sha256)
        packages = consumers(batch, root)
        if args.verify_only:
            return 0
        output = args.output.resolve()
        output.mkdir()
        for label in ("minimal", "candidate", "original"):
            stage = label
            path = prepare_run(output, label)
            if label == "original":
                run = OriginalBusinessRun(path, args.dotnet.resolve())
                original = run
            else:
                minimal = label == "minimal"
                selected = {name: row for name, row in packages.items()
                            if not minimal or name not in (ZERO, ZERO_COMMON)}
                run = PatchRun(path, args.dotnet.resolve(), selected, minimal)
                if not minimal:
                    candidate = run
            require(run.execute() == 0, f"{label} 消费失败，见 {run.report_path}")
        stage = "已有对象及 SQLite 对照"
        compare_business(original.report, candidate.report)
        for key in ("configuration", "user", "collection"):
            require(original.probe[key] == candidate.probe[key], f"{key} 原版与候选结果不同")
        sql = compare_projection(original.probe["projection"], candidate.probe["projection"])
        write_json(output / "report.json", {
            "status": "passed", "exitCode": 0, "batchSha256": args.batch_sha256,
            "runs": {label: sha256(output / label / "report.json")
                     for label in ("minimal", "candidate", "original")},
            "projection": sql,
        })
        return 0
    except (VerificationError, OSError, ValueError, KeyError, BadZipFile, ParseError) as error:
        print(f"{stage}：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
