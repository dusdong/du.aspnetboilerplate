#!/usr/bin/env python3
"""以已接受归档的独立副本验证 R4 的拒绝路径。"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r4_candidate_batch import archive_paths, load_frozen_batch, run_logged
from r4_candidate_inspection import ArchiveInspection
from r4_release_candidate import MANIFEST
from verify import ROOT, VerificationError, read_json, require


ENGINE = "Du.AutoMapper"
COLLECTION = "Du.AutoMapper.Collection"


def replace_member(source, destination, member, transform):
    with ZipFile(source) as original, ZipFile(destination, "w") as changed:
        for entry in original.infolist():
            data = original.read(entry)
            changed.writestr(entry, transform(data) if entry.filename == member else data)


def must_fail(case, operation, *expected):
    try:
        operation()
    except VerificationError as error:
        require(all(text in str(error) for text in expected), f"{case}：诊断错误 {error}")
        print(f"{case}：{error}", flush=True)
    else:
        raise VerificationError(f"{case}：预期拒绝，实际通过")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    args = parser.parse_args()
    batch_root = args.batch_root.resolve()
    args.logs.mkdir()
    logs = args.logs.resolve()
    before = load_frozen_batch(batch_root)
    manifest = read_json(MANIFEST)
    row = manifest["packages"][ENGINE]
    paths = archive_paths(ENGINE, row)
    original = batch_root / paths["archive"]
    original_symbols = batch_root / paths["symbols"]
    with TemporaryDirectory(prefix="r4-batch-tests-") as directory:
        temp = Path(directory)
        work = temp / "inspect"
        work.mkdir()
        env = os.environ | {"DOTNET_CLI_HOME": str(work / "dotnet-home"), "DOTNET_NOLOGO": "1"}
        run = lambda argv, cwd, label: run_logged(argv, cwd, label, logs, env)
        inspection = ArchiveInspection(manifest, args.baseline_root.resolve(), work, "dotnet", run)
        commit = manifest["producers"]["engine"]["finalCommit"]
        wrong_commit = manifest["producers"]["engine"]["baseCommit"]
        cases = (
            ("wrong-commit", f"{ENGINE}.nuspec", commit, wrong_commit, "/nuspec/repository/commit"),
            ("upstream-homepage", f"{ENGINE}.nuspec", row["projectUrl"], "https://automapper.org", "/nuspec/projectUrl"),
            ("original-install-id", "README.md", "dotnet add package Du.AutoMapper ", "dotnet add package AutoMapper ",
             "/README.md/dotnet add package"),
        )
        for case, member, old, new, field in cases:
            changed = temp / f"{case}.nupkg"
            replace_member(original, changed, member, lambda data: data.replace(old.encode(), new.encode()))
            must_fail(case, lambda: inspection.inspect_package(ENGINE, row, changed, original_symbols, False),
                      ENGINE + field, "预期", "实际", new.strip().split()[-1])

        other = batch_root / archive_paths(COLLECTION, manifest["packages"][COLLECTION])["symbols"]
        with ZipFile(other) as zip_file:
            wrong_pdb = zip_file.read("lib/net8.0/AutoMapper.Collection.pdb")
        changed = temp / "wrong-symbol.snupkg"
        replace_member(original_symbols, changed, "lib/net8.0/AutoMapper.pdb", lambda _: wrong_pdb)
        must_fail("mismatched-portable-pdb",
                  lambda: inspection.inspect_package(ENGINE, row, original, changed, False),
                  f"{ENGINE}/net8.0/lib/net8.0/AutoMapper.pdb/CodeView", "预期", "实际")

        relocated = temp / "relocated"
        shutil.copytree(batch_root, relocated)
        require(load_frozen_batch(relocated) == before, "搬移后的冻结批次不一致")
        replaced = relocated / paths["archive"]
        data = bytearray(replaced.read_bytes())
        data[-1] ^= 1
        replaced.write_bytes(data)
        command = [sys.executable, "-B", "eng/r4_candidate_batch.py", "verify", "--batch-root", str(relocated)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        require(result.returncode == 1 and f"{replaced} SHA-256 不符" in result.stderr,
                f"同版本字节变化未被拒绝：{result.stdout}{result.stderr}")
        print(f"replaced-same-version-bytes：cwd={ROOT} argv={command}，退出 {result.returncode}\n{result.stderr}",
              end="", flush=True)
    require(load_frozen_batch(batch_root) == before, "原批次发生变化")
    print("5 项定向负例和搬移复验通过。")


if __name__ == "__main__":
    main()
