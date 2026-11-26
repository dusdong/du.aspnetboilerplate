#!/usr/bin/env python3
"""生产、冻结或核对一组 R4 主包与符号包。"""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from r2_packages import write_json
from r3_leaf_packages import checked_file
from r4_candidate_inspection import ArchiveInspection, R4_INSPECTION, producer_git
from r4_release_candidate import MANIFEST, verify_equal, verify_gitlinks, verify_manifest
from verify import ROOT, VerificationError, read_json, require, sha256


BATCH_REFERENCE = ROOT / "eng/r4_candidate_batch_reference.json"
BATCH = "batch.json"
PRODUCTION_PHASES = ("framework", "engine", "collection", "adapter")
PHASE_LOGS = {
    "framework": ("commands.log", "logs/sdk.log"),
    "engine": ("pack.log", "apicompat/environment.txt", "apicompat/comparison.log",
               "apicompat/release-sha256.txt", "apicompat/exit-code.txt"),
    "collection": ("commands.log", "logs/sdk.log", "tests/collection.trx"),
    "adapter": ("commands.log", "logs/sdk.log", "inputs.sha256"),
}
DIGEST = re.compile("[0-9a-f]{64}")
ENGINE_REFERENCE_SHA = "8ac567aa1ef2ecb44d02583432754e1a57cb64ac2bea3ef01966d25c27c7d621"


def phase_for(name, row):
    return "adapter" if name == "Du.Abp.AutoMapper" else row["producer"]


def archive_paths(name, row):
    stem = f"{name}.{row['version']}"
    return {"archive": f"feed/{stem}.nupkg", "symbols": f"symbols/{stem}.snupkg"}


def validate_checkout(manifest):
    verify_gitlinks(manifest)
    for producer, source in manifest["producers"].items():
        verify_equal(source["finalCommit"], producer_git(source, "rev-parse", "HEAD").decode().strip(),
                     f"{producer}/HEAD")
        verify_equal("", producer_git(source, "status", "--porcelain=v1", "--untracked-files=all").decode().strip(),
                     f"{producer}/工作树")


def run_logged(argv, cwd, label, log_root, env):
    log = log_root / f"{label}.log"
    with log.open("wb") as output:
        output.write((json.dumps({"cwd": str(cwd), "command": shlex.join(map(str, argv))}, ensure_ascii=False)
                      + "\n").encode())
        output.flush()
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output.write(result.stdout)
        output.write(result.stderr)
        output.write(f"\n退出码 {result.returncode}\n".encode())
    require(result.returncode == 0, f"{label} 退出 {result.returncode}，见 {log}")
    return result.stdout


def produce(manifest, output, reference, dotnet):
    validate_checkout(manifest)
    verify_equal(ENGINE_REFERENCE_SHA, sha256(reference), "AutoMapper 13.0.0 ApiCompat 参考/SHA-256")
    output.mkdir()
    packages = manifest["packages"]
    engine = output / "engine" / archive_paths("Du.AutoMapper", packages["Du.AutoMapper"])["archive"]
    collection = (output / "collection" /
                  archive_paths("Du.AutoMapper.Collection", packages["Du.AutoMapper.Collection"])["archive"])
    core = output / "framework" / archive_paths("Du.Abp", packages["Du.Abp"])["archive"]
    env = os.environ | {"DOTNET": dotnet, "API_COMPAT_DOTNET": dotnet}
    for phase in PRODUCTION_PHASES:
        repo = ROOT / manifest["producers"]["framework" if phase == "adapter" else phase]["path"]
        directory = output / phase
        if phase in ("framework", "adapter"):
            args = ["bash", "nupkg/pack-r4.sh", "automapper" if phase == "adapter" else phase, directory]
            if phase == "adapter":
                args.extend((core, engine, collection))
        elif phase == "engine":
            args = ["sh", "src/AutoMapper/ApiCompat/pack-r3-engine.sh", "--r4", reference, directory]
        else:
            args = ["bash", "pack-r3-candidate.sh", "--r4", engine, sha256(engine), directory]
        run_logged(args, repo, phase, output, env)
    validate_checkout(manifest)


def receipt_hashes(path, phase):
    hashes = {}
    for line in path.read_text().splitlines():
        digest, member = line.split(maxsplit=1)
        listed = Path(member)
        # 引擎入口写绝对归档路径。迁移生产目录后，仍按原归档的阶段和相对路径核对。
        if listed.is_absolute():
            require(listed.parent.parent.name == phase, f"{path}：非 {phase} 阶段的归档 {listed}")
            member = Path(*listed.parts[-2:]).as_posix()
        require(DIGEST.fullmatch(digest) and member not in hashes, f"{path}：重复或无效的摘要 {line!r}")
        hashes[member] = digest
    return hashes


def fingerprint(path, root):
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def copy_checked(source, target, digest):
    require(source.is_file() and not source.is_symlink(), f"缺少常规文件 {source}")
    shutil.copyfile(source, target)
    verify_equal(digest, sha256(target), f"{source}/SHA-256")


def copy_production(manifest, production, output):
    packages = manifest["packages"]
    receipts = {}
    digests = {}
    for phase in PRODUCTION_PHASES:
        stage = production / phase
        source = manifest["producers"]["framework" if phase == "adapter" else phase]
        commit = (stage / "source-commit.txt").read_text().strip()
        verify_equal(source["finalCommit"], commit, f"{phase}/source-commit.txt")
        verify_equal("0", (stage / "exit-code.txt").read_text().strip(), f"{phase}/exit-code.txt")
        selected = {name: archive_paths(name, row) for name, row in packages.items() if phase_for(name, row) == phase}
        expected = {path for pair in selected.values() for path in pair.values()}
        actual = {path.relative_to(stage).as_posix() for kind in ("feed", "symbols")
                  for path in (stage / kind).iterdir()}
        verify_equal(sorted(expected), sorted(actual), f"{phase}/归档清单")
        checksums = receipt_hashes(stage / "packages.sha256", phase)
        inputs = []
        if phase == "collection":
            inputs = ["Du.AutoMapper"]
        elif phase == "adapter":
            inputs = ["Du.Abp", "Du.AutoMapper", "Du.AutoMapper.Collection"]
        expected_inputs = {f"inputs/{Path(archive_paths(name, packages[name])['archive']).name}": digests[name]
                           for name in inputs}
        if phase == "adapter":
            verify_equal(expected_inputs, receipt_hashes(stage / "inputs.sha256", phase), f"{phase}/记录的输入")
        verify_equal(sorted(expected | (expected_inputs.keys() if phase == "collection" else set())),
                     sorted(checksums), f"{phase}/packages.sha256")
        if phase == "collection":
            verify_equal(expected_inputs, {path: checksums[path] for path in expected_inputs}, f"{phase}/记录的输入")
        for path, digest in expected_inputs.items():
            verify_equal(digest, sha256(stage / path), f"{phase}/{path}/SHA-256")
        for name, pair in selected.items():
            for path in pair.values():
                copy_checked(stage / path, output / path, checksums[path])
            digests[name] = checksums[pair["archive"]]
        logs = []
        files = ("source-commit.txt", "exit-code.txt", "packages.sha256", *PHASE_LOGS[phase])
        for path in files:
            target = output / "production" / phase / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(stage / path, target)
            logs.append(fingerprint(target, output))
        if phase == "engine":
            verify_equal("0", (stage / "apicompat/exit-code.txt").read_text().strip(), "engine/ApiCompat/退出码")
            require("Total Issues: 0" in (stage / "apicompat/comparison.log").read_text(),
                    "engine/ApiCompat 缺少通过记录")
        receipts[phase] = {"commit": commit, "repository": source["repository"], "exitCode": 0,
                           "inputs": expected_inputs, "records": logs}
    return receipts


def verify_release_outputs(production, phase, name, details):
    project = name.removeprefix("Du.")
    stage = production / phase
    for tfm, target in details["targets"].items():
        lane = f"release_{tfm}" if phase == "collection" or len(details["targets"]) > 1 else "release"
        build = (stage / "apicompat" if phase == "engine" else stage) / "artifacts" / "bin" / project / lane
        dll, pdb = build / Path(target["asset"]).name, build / Path(target["pdb"]).name
        verify_equal(target["assetSha256"], sha256(dll), f"{name}/{tfm}/Release DLL")
        verify_equal(target["pdbSha256"], sha256(pdb), f"{name}/{tfm}/Release PDB")
        if phase == "engine":
            proof = (stage / "apicompat/release-sha256.txt").read_text().split(maxsplit=1)[0]
            verify_equal(target["assetSha256"], proof, f"{name}/{tfm}/ApiCompat DLL")
        if phase == "collection":
            tested = build.parent.parent / "AutoMapper.Collection.Tests" / lane / dll.name
            verify_equal(target["assetSha256"], sha256(tested), f"{name}/{tfm}/回归输出 DLL")


def inspect_batch(manifest, baseline, batch_root, work, log_root, dotnet, production=None):
    shutil.copyfile(R4_INSPECTION / "global.json", work / "global.json")
    env = os.environ | {"DOTNET_CLI_HOME": str(work / "dotnet-home"), "DOTNET_NOLOGO": "1",
                        "DOTNET_CLI_UI_LANGUAGE": "en"}
    run = lambda argv, cwd, label: run_logged(argv, cwd, label, log_root, env)
    run([dotnet, "--info"], work, "inspection-sdk")
    inspection = ArchiveInspection(manifest, baseline, work, dotnet, run)
    report = {}
    for name, row in manifest["packages"].items():
        paths = archive_paths(name, row)
        try:
            details = inspection.inspect_package(name, row, batch_root / paths["archive"], batch_root / paths["symbols"],
                                                 verify_project=production is not None)
            if production is not None:
                verify_release_outputs(production, phase_for(name, row), name, details)
        except (VerificationError, OSError, KeyError, TypeError, ValueError, ParseError, BadZipFile) as error:
            raise VerificationError(f"{name}：{error}") from error
        report[name] = details
        print(f"{name}：{len(details['targets'])} 个目标通过", flush=True)
    return report


def freeze(manifest, production, baseline, output, log_root, dotnet):
    verify_manifest(manifest, baseline)
    validate_checkout(manifest)
    output.mkdir()
    (output / "feed").mkdir()
    (output / "symbols").mkdir()
    receipts = copy_production(manifest, production, output)
    with TemporaryDirectory(prefix="r4-inspect-") as directory:
        report = inspect_batch(manifest, baseline, output, Path(directory), log_root, dotnet, production)
    validate_checkout(manifest)

    report_path = output / "inspection.json"
    write_json(report_path, report)
    packages = {}
    for name, row in manifest["packages"].items():
        archives = {key: fingerprint(output / path, output) for key, path in archive_paths(name, row).items()}
        packages[name] = {"version": row["version"], "producer": row["producer"], **archives}
    batch_file = output / BATCH
    write_json(batch_file, {"schemaVersion": 1, "combinationSha256": sha256(MANIFEST),
                            "gitlinkCommit": manifest["gitlinkCommit"], "template": manifest["template"],
                            "producers": manifest["producers"], "production": receipts,
                            "inspection": fingerprint(report_path, output), "packages": packages})
    print(f"冻结 13 个主包和 13 个符号包。{batch_file} SHA-256 {sha256(batch_file)}")


def load_frozen_batch(root, expected_digest=None):
    """还原前打开已接受的批次，校验相对路径、归档和复核报告的字节。"""
    root = Path(root).resolve()
    if expected_digest is None:
        reference = read_json(BATCH_REFERENCE)
        verify_equal(BATCH, reference["path"], "冻结批次引用/path")
        expected_digest = reference["sha256"]
    require(DIGEST.fullmatch(expected_digest), "批次须使用完整 SHA-256")
    batch = read_json(checked_file(root, BATCH, expected_digest))
    manifest = read_json(MANIFEST)
    for field in ("gitlinkCommit", "template", "producers"):
        verify_equal(manifest[field], batch[field], f"batch/{field}")
    verify_equal(1, batch["schemaVersion"], "batch/schemaVersion")
    verify_equal(sha256(MANIFEST), batch["combinationSha256"], "batch/combinationSha256")
    verify_equal(sorted(manifest["packages"]), sorted(batch["packages"]), "batch/packages")
    for name, row in manifest["packages"].items():
        record = batch["packages"][name]
        for key in ("version", "producer"):
            verify_equal(row[key], record[key], f"{name}/{key}")
        for kind, path in archive_paths(name, row).items():
            file = record[kind]
            verify_equal(path, file["path"], f"{name}/{kind}/path")
            verify_fingerprint(root, file)
    for kind in ("feed", "symbols"):
        expected = {Path(path).name for name, row in manifest["packages"].items()
                    for path in archive_paths(name, row).values() if path.startswith(kind + "/")}
        verify_equal(sorted(expected), sorted(path.name for path in (root / kind).iterdir()), f"batch/{kind}")
    verify_equal("inspection.json", batch["inspection"]["path"], "batch/inspection/path")
    verify_fingerprint(root, batch["inspection"])
    for phase in PRODUCTION_PHASES:
        for file in batch["production"][phase]["records"]:
            verify_fingerprint(root, file)
    return batch


def verify_fingerprint(root, record):
    relative = Path(record["path"])
    require(not relative.is_absolute() and ".." not in relative.parts, f"批次成员路径不符：{relative}")
    path = checked_file(root, record["path"], record["sha256"])
    require(path == root / record["path"], f"{record['path']}：批次成员须为归档目录内的常规文件")
    verify_equal(record["bytes"], path.stat().st_size, f"{record['path']}/bytes")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    producer = commands.add_parser("produce", help="按依赖顺序调用子仓入口")
    producer.add_argument("--output", type=Path, required=True)
    producer.add_argument("--engine-reference", type=Path, required=True)
    freezing = commands.add_parser("freeze", help="在新目录复制并复核生产归档")
    freezing.add_argument("--production", type=Path, required=True)
    freezing.add_argument("--output", type=Path, required=True)
    verifying = commands.add_parser("verify", help="核对已接受批次及其归档和报告摘要")
    rechecking = commands.add_parser("recheck", help="核对摘要后，重新检查归档、API 和符号")
    for command in (verifying, rechecking):
        command.add_argument("--batch-root", type=Path, required=True)
        command.add_argument("--batch-sha256", help="按交接中单独确认的批次清单摘要复核")
    for command in (freezing, rechecking):
        command.add_argument("--baseline-root", type=Path, required=True)
        command.add_argument("--logs", type=Path, required=True, help="尚未创建的复核日志目录")
    for command in (producer, freezing, rechecking):
        command.add_argument("--dotnet", default="dotnet")
    args = parser.parse_args()
    try:
        manifest = read_json(MANIFEST)
        if args.command == "produce":
            produce(manifest, args.output.resolve(), args.engine_reference.resolve(), args.dotnet)
        elif args.command == "freeze":
            args.logs.mkdir()
            freeze(manifest, args.production.resolve(), args.baseline_root.resolve(),
                   args.output.resolve(), args.logs.resolve(), args.dotnet)
        else:
            root = args.batch_root.resolve()
            batch = load_frozen_batch(root, args.batch_sha256)
            if args.command == "recheck":
                verify_manifest(manifest, args.baseline_root.resolve())
                args.logs.mkdir()
                with TemporaryDirectory(prefix="r4-inspect-") as directory:
                    report = inspect_batch(manifest, args.baseline_root.resolve(), root, Path(directory),
                                           args.logs.resolve(), args.dotnet)
                accepted = read_json(root / batch["inspection"]["path"])
                for details in accepted.values():
                    for target in details["targets"].values():
                        del target["projectIdentity"]
                verify_equal(accepted, report, "inspection/复核")
            print(f"冻结批次校验通过。{root / BATCH} SHA-256 {sha256(root / BATCH)}")
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr
        print(f"R4 批次校验失败：{detail.strip() if detail else error}", file=sys.stderr)
        return 1
    except (VerificationError, OSError, ValueError, KeyError, TypeError, ParseError, BadZipFile) as error:
        print(f"R4 批次校验失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
