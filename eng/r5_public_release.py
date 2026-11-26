#!/usr/bin/env python3
"""从冻结批次生成公开发行清单，匿名回读包和符号并登记可续作进度。"""

import argparse
import fcntl
import json
from pathlib import Path
import sys
from zipfile import BadZipFile

from r2_packages import NUGET_SOURCE
from r3_leaf_packages import checked_file
from r4_candidate_batch import load_frozen_batch as load_r4_batch
from r4_public_release import MANIFEST_SHA256, HEX_SHA256, Dotnet, NuGet, Progress, timestamp, write_json
from r4_release_manifest import BATCH_SHA256, RELEASE
from r5_candidate_batch import load_frozen_batch, verify_carried_package
from verify import VerificationError, read_json, require, sha256


READBACK_ERRORS = (BadZipFile, KeyError, OSError, ValueError, VerificationError)


def release_manifest(root, batch_sha, *, verify_carried=True):
    batch = load_frozen_batch(root, batch_sha, verify_carried=verify_carried)
    require(batch["schemaVersion"] == 2, "公开发行需要 R5 待发批次")
    release = batch["release"]
    return {
        "schemaVersion": 2,
        "release": {"repository": RELEASE["repository"], "tag": release["proposedTag"],
                    "qualificationCommit": release["mainCommit"], "commit": release["tagTarget"]},
        "nugetSource": NUGET_SOURCE, "batchSha256": batch_sha, "template": batch["template"],
        "publishOrder": release["uploadOrder"], "packages": batch["packages"], "carried": batch["publicPackages"],
    }, batch


def load_release(root, batch_sha, path, expected, *, verify_carried=True):
    require(HEX_SHA256.fullmatch(expected), "需要独立登记的发行清单 SHA-256")
    manifest = read_json(checked_file(path.parent, path.name, expected))
    if expected == MANIFEST_SHA256:
        require(batch_sha == BATCH_SHA256, "R4 首发清单与独立批次摘要不符")
        batch = load_r4_batch(root, batch_sha)
        require(manifest["release"] == RELEASE and manifest["nugetSource"] == NUGET_SOURCE
                and manifest["handoff"]["batchSha256"] == batch_sha and manifest["template"] == batch["template"]
                and manifest["packages"].keys() == batch["packages"].keys(), "R4 发行输入不一致")
        return manifest, batch, root.parent
    derived, batch = release_manifest(root, batch_sha, verify_carried=verify_carried)
    require(manifest == derived, "R5 发行清单与指定冻结批次不一致")
    return manifest, batch, root


def verified_downloads(path, expected, manifest, manifest_sha, batch_sha):
    require(HEX_SHA256.fullmatch(expected), "需要独立登记的公开下载登记 SHA-256")
    report = read_json(checked_file(path.parent, path.name, expected))
    require(report.get("schemaVersion") == 2 and report.get("nugetSource") == NUGET_SOURCE
            and report.get("manifestSha256") == manifest_sha and report.get("batchSha256") == batch_sha,
            "公开下载登记的来源、发行或冻结批次不符")
    carried = manifest.get("carried", {})
    rows = report["packages"]
    require(rows.keys() == manifest["packages"].keys() | carried.keys(), "公开下载登记缺少维护包或含额外包")
    for name, row in rows.items():
        uploaded = manifest["packages"].get(name)
        proof = carried.get(name, {}).get("publicEvidence")
        upload = uploaded["archive"] if uploaded else {"sha256": proof["uploadSha256"]}
        expected_version = (uploaded or carried[name])["version"]
        require(row.get("version") == expected_version and row.get("uploadSha256") == upload["sha256"]
                and HEX_SHA256.fullmatch(row.get("downloadSha256", ""))
                and row["downloadSha256"] != upload["sha256"]
                and (not proof or row["downloadSha256"] == proof["downloadSha256"]),
                f"{name}/{expected_version} 公开下载摘要或版本不符")
    return rows


class ReleaseProgress(Progress):
    def __init__(self, manifest, manifest_sha, batch_root, batch_sha, handoff, work, nuget, dotnet):
        self.batch_root = batch_root
        self.batch_sha = batch_sha
        self.carried = manifest.get("carried", {})
        self.r4_downloads = {}
        if self.carried:
            self.r4_downloads = read_json(batch_root / "public/verified-downloads.json")["packages"]
        super().__init__(manifest, manifest_sha, handoff, work, nuget, dotnet)
        self.check_state()

    def check_state(self):
        require(self.state.get("release") == self.manifest["release"] and self.state.get("nugetSource") == NUGET_SOURCE
                and self.state.get("batchSha256", self.batch_sha) == self.batch_sha,
                "进度记录的发行目标、来源或批次不符")

    def reusable_main(self, name, record, observation):
        expected = self.manifest["packages"][name]
        return (bool(record) and record.get("version") == expected["version"]
                and record.get("uploadSha256") == expected["archive"]["sha256"]
                and super().reusable_main(name, record, observation))

    def carried_evidence(self, name):
        row = self.carried[name]
        try:
            independently_verified = self.r4_downloads[name]
            verify_carried_package(self.batch_root, name, row, independently_verified)
            return {"status": "verified", **independently_verified, "reason": "R4 匿名下载和仓库验签原证据匹配"}
        except READBACK_ERRORS as error:
            return {"version": row["version"], "status": "failed", "reason": str(error)}

    def check_carried(self, name):
        result = self.carried_evidence(name)
        history = self.state.setdefault("carried", {}).setdefault(name, [])
        if not history or {k: v for k, v in history[-1].items() if k != "time"} != result:
            history.append(result | {"time": timestamp()})
        print(f"{name}/{result['version']}/carried {result['status']} {result['reason']}")
        return result

    def save(self):
        self.check_state()
        self.state["batchSha256"] = self.batch_sha
        rows = {}
        for name, package in self.state["packages"].items():
            last = package.get("main", [None])[-1]
            if self.reusable_main(name, last, self.observation("main", name)):
                rows[name] = {key: last[key] for key in ("version", "uploadSha256", "downloadSha256")}
        for name in self.carried:
            result = self.carried_evidence(name)
            if result["status"] == "verified":
                rows[name] = {key: result[key] for key in ("version", "uploadSha256", "downloadSha256")}
        self.downloads.unlink(missing_ok=True)
        write_json(self.path, self.state)
        write_json(self.downloads, {
            "schemaVersion": 2, "nugetSource": NUGET_SOURCE, "manifestSha256": self.state["manifestSha256"],
            "batchSha256": self.batch_sha, "packages": rows,
        })

    def check_main(self, name):
        if name in self.carried:
            return self.check_carried(name)
        result = super().check_main(name)
        if result["status"] == "verified":
            print(f"{name}/{result['version']}/main verified：仓库签名、所有者、冻结内容和证据文件匹配")
        return result

    def verify(self, names, main_only):
        names = tuple(dict.fromkeys(names))
        carried = [self.check_carried(name) for name in names if name in self.carried]
        upload = [name for name in names if name not in self.carried]
        result = super().verify(upload, main_only)
        self.save()
        return 1 if any(row["status"] != "verified" for row in carried) else result

    def gate(self, name):
        code = super().gate(name)
        self.save()
        return code

    def record(self, kind, name, outcome, reference, owners, upload_sha=None):
        if kind == "main" and outcome in ("accepted", "confirmed"):
            row = self.manifest["packages"][name]
            require(upload_sha == row["archive"]["sha256"], f"{name} 实传主包 SHA-256 与发行清单不符")
            checked_file(self.handoff, row["archive"]["path"], upload_sha)
        super().record(kind, name, outcome, reference, owners, upload_sha)

    def symbol_gate(self, name):
        main = self.check_main(name)
        observation = self.observation("symbols", name)
        symbols = {}
        ready = False
        if main["status"] == "verified":
            self.check_symbols(name, main)
            histories = self.state["packages"][name]["symbols"]
            symbols = {asset: history[-1]["status"] for asset, history in histories.items()}
            unindexed = all(history[-1].get("readback", {}).get("httpStatus") == 404 and
                            history[-1]["status"] == "pending" for history in histories.values())
            ready = bool(symbols) and unindexed and (observation is None or observation["outcome"] == "retry")
        print(json.dumps({"package": name, "main": main["status"], "symbols": symbols,
                          "symbolReceipt": observation, "ready": ready}, ensure_ascii=False))
        return 0 if ready else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--batch-sha256", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--timeout", type=int, default=20)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("manifest", help="生成 R5 发行清单")
    commands.add_parser("queue", help="列出本次可上传件和只读核验包")
    verify = commands.add_parser("verify", help="匿名回读并验证包与符号")
    verify.add_argument("--package", action="append")
    verify.add_argument("--main-only", action="store_true")
    gate = commands.add_parser("gate", help="检查直接依赖和上传条件")
    gate.add_argument("--package", required=True)
    gate.add_argument("--symbols", action="store_true")
    record = commands.add_parser("record", help="登记已发生的外部操作凭证")
    record.add_argument("--kind", choices=("tag", "main", "symbols", "release"), required=True)
    record.add_argument("--package")
    record.add_argument("--outcome", choices=("accepted", "timeout", "duplicate", "confirmed", "failed", "retry"),
                        required=True)
    record.add_argument("--evidence", required=True)
    record.add_argument("--owner", action="append")
    record.add_argument("--upload-sha256")
    args = parser.parse_args()
    try:
        root, path = args.batch_root.resolve(), args.manifest.resolve()
        require(not path.is_relative_to(root), "发行清单须位于冻结批次之外")
        if args.command == "manifest":
            manifest, _ = release_manifest(root, args.batch_sha256)
            data = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
            if path.exists():
                require(path.read_text(encoding="utf-8") == data, "发行清单已存在且内容不同")
            else:
                with path.open("x", encoding="utf-8") as output:
                    output.write(data)
            print(f"{path} SHA-256 {sha256(path)}")
            return 0
        require(args.manifest_sha256, "需要 --manifest-sha256")
        manifest, _, handoff = load_release(root, args.batch_sha256, path, args.manifest_sha256, verify_carried=False)
        if args.command == "queue":
            print(json.dumps({"uploadOrder": manifest["publishOrder"],
                              "archives": {name: {key: row[key] for key in ("version", "archive", "symbols", "targets")}
                                           for name, row in manifest["packages"].items()},
                              "carried": list(manifest.get("carried", {}))}, indent=2, ensure_ascii=False))
            return 0
        require(args.work and 1 <= args.timeout <= 60, "需要 --work，超时须为 1 至 60 秒")
        if args.command == "verify":
            names = args.package or [*manifest["publishOrder"], *manifest.get("carried", {})]
        else:
            names = [args.package] if args.package else []
        allowed = manifest["packages"].keys()
        if args.command == "verify":
            allowed = allowed | manifest.get("carried", {}).keys()
        require(set(names) <= allowed, "命令所选包超出适用清单")
        work = args.work.resolve()
        require(not work.is_relative_to(handoff), "核验目录须位于冻结交接目录之外")
        work.mkdir(parents=True, exist_ok=True)
        with (work / "progress.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            progress = ReleaseProgress(manifest, args.manifest_sha256, root, args.batch_sha256,
                                       handoff, work, NuGet(args.timeout), Dotnet(work))
            if args.command == "record":
                progress.record(args.kind, args.package, args.outcome, args.evidence, args.owner, args.upload_sha256)
                return 0
            if args.command == "gate":
                return progress.symbol_gate(args.package) if args.symbols else progress.gate(args.package)
            return progress.verify(names, args.main_only)
    except READBACK_ERRORS as error:
        print(f"公开发行核验失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
