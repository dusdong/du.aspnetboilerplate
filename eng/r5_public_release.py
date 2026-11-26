#!/usr/bin/env python3
"""从冻结批次生成公开发行清单，匿名回读包和符号并登记可续作进度。"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import NamedTemporaryFile
from uuid import uuid4
from zipfile import BadZipFile

import r5_oidc
from r2_packages import NUGET_SOURCE
from r3_leaf_packages import bytes_sha256, checked_file
from r4_candidate_batch import load_frozen_batch as load_r4_batch
from r4_public_release import (MANIFEST_SHA256, HEX_SHA256, Dotnet, NuGet, Progress, normalized_owners, timestamp,
                               write_json)
from r4_release_manifest import BATCH_SHA256, RELEASE
from r5_candidate_batch import load_frozen_batch, verify_carried_package
from verify import VerificationError, read_json, require, sha256


READBACK_ERRORS = (BadZipFile, KeyError, OSError, ValueError, VerificationError, subprocess.TimeoutExpired)


def write_durable_json(path, record):
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        pending = Path(stream.name)
        try:
            json.dump(record, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
            pending.replace(path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            pending.unlink(missing_ok=True)


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
        self.confirming_main = None
        if self.carried:
            self.r4_downloads = read_json(batch_root / "public/verified-downloads.json")["packages"]
        super().__init__(manifest, manifest_sha, handoff, work, nuget, dotnet)
        self.check_state()

    def check_state(self):
        require(self.state.get("release") == self.manifest["release"] and self.state.get("nugetSource") == NUGET_SOURCE
                and self.state.get("batchSha256", self.batch_sha) == self.batch_sha,
                "进度记录的发行目标、来源或批次不符")

    def attempts(self, kind, name):
        return self.state.get("uploadIntents", {}).get(f"{kind}/{name}", [])

    def observation(self, kind, name):
        if self.confirming_main and (kind, name) == ("main", self.confirming_main["package"]):
            return self.confirming_main["observation"]
        attempts = self.attempts(kind, name)
        if not attempts:
            return super().observation(kind, name)
        intent = attempts[-1]
        return intent.get("result") or {
            "outcome": "pending", "version": intent["version"], "uploadSha256": intent["uploadSha256"],
            "evidence": intent["receipt"],
        }

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
        if self.confirming_main:
            return
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
        if self.state.get("uploadIntents"):
            write_durable_json(self.path, self.state)
        else:
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
        require(not self.attempts(kind, name), f"{name}/{kind} 已有上传意向，请使用 resolve 核对该次操作")
        if kind == "main" and outcome in ("accepted", "confirmed"):
            row = self.manifest["packages"][name]
            require(upload_sha == row["archive"]["sha256"], f"{name} 实传主包 SHA-256 与发行清单不符")
            checked_file(self.handoff, row["archive"]["path"], upload_sha)
        super().record(kind, name, outcome, reference, owners, upload_sha)

    def upload(self, kind, name, owners, lock, *, oidc=None):
        require(self.carried, "upload 仅适用于 R5 待发批次")
        gate = self.gate(name) if kind == "main" else self.symbol_gate(name)
        if gate != 0:
            return gate
        require(all(self.carried_evidence(carried)["status"] == "verified" for carried in self.carried),
                "应先核对全部十个沿用包")
        if kind == "symbols":
            owners = self.observation("main", name)["owners"]
        current = self.nuget.owners(name)["owners"]
        require(owners and normalized_owners(owners) == normalized_owners(current),
                f"{name} 登记所有者与 NuGet 公开回读不符")
        row = self.manifest["packages"][name]
        archive = row["archive" if kind == "main" else "symbols"]
        source = checked_file(self.handoff, archive["path"], archive["sha256"])
        receipt = self.work / f"push-{uuid4().hex}.json"
        intent = {"time": timestamp(), "batchSha256": self.batch_sha, "package": name, "version": row["version"],
                  "kind": kind, "uploadSha256": archive["sha256"], "receipt": receipt.name, "owners": owners}
        if oidc:
            draft_id, login_run = map(r5_oidc.github_id, oidc)
            require(self.batch_sha == r5_oidc.BATCH_SHA
                    and self.state["manifestSha256"] == r5_oidc.MANIFEST_SHA
                    and r5_oidc.ARCHIVES.get(source.name) == archive["sha256"]
                    and normalized_owners(owners) == {r5_oidc.OWNER},
                    "托管发行只接受本轮冻结归档和已核定的发布者")
            head = r5_oidc.github("git/ref/heads/main")["object"]["sha"]
            r5_oidc.require_login(login_run, head)
            r5_oidc.check_tag()
            asset = r5_oidc.draft_assets(draft_id)[source.name]
            intent["workflow"] = {"head": head, "draftId": draft_id, "assetId": str(asset["id"]),
                                  "loginRun": login_run}
        self.state.setdefault("uploadIntents", {}).setdefault(f"{kind}/{name}", []).append(intent)
        write_durable_json(self.path, self.state)
        print(f"{name}/{kind} 上传意向已登记，收据 {receipt}", flush=True)
        if oidc:
            ticket = receipt.stem.removeprefix("push-")
            remote = intent["workflow"]
            remote["runId"] = r5_oidc.dispatch(source.name, remote, ticket)
            write_durable_json(self.path, self.state)
            run_id = remote["runId"]
            print(f"https://github.com/{r5_oidc.REPO}/actions/runs/{run_id}", flush=True)
            r5_oidc.run_attempt(run_id, r5_oidc.run_title("publish", ticket), remote["head"])
            r5_oidc.authorize(remote, ticket)
            return 0
        command = ["dotnet", "nuget", "push", str(source), "--source", NUGET_SOURCE]
        if kind == "main":
            command.append("--no-symbols")
        try:
            # 保留子进程持有的进度锁，直到它退出。输出可能包含凭据，收据仅登记进程结果。
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       pass_fds=(lock.fileno(),))
        except OSError:
            write_durable_json(receipt, intent | {"started": False, "completedAt": timestamp()})
            raise
        with process:
            code = process.wait()
        write_durable_json(receipt, intent | {"exitCode": code, "completedAt": timestamp()})
        if code == 0:
            intent["result"] = {"outcome": "accepted", "evidence": receipt.name, "version": intent["version"],
                                "uploadSha256": intent["uploadSha256"], "owners": owners}
            self.save()
        else:
            print(f"{name}/{kind} 上传退出 {code}，请核对收据与服务受理状态", file=sys.stderr)
        return code if code >= 0 else 128 - code

    def workflow_receipt(self, kind, name):
        attempts = self.attempts(kind, name)
        require(attempts and "workflow" in attempts[-1], f"{name}/{kind} 没有可回读的托管上传意向")
        intent = attempts[-1]
        require("result" not in intent, "该次托管上传已有登记结果")
        remote = intent["workflow"]
        receipt = self.work / intent["receipt"]
        if "runId" not in remote:
            # 即使 GitHub 收到了触发请求，也没有可写入单次放行的运行 ID。
            result = {"started": False, "phase": "dispatch-unbound"}
        else:
            run_id = remote["runId"]
            ticket = receipt.stem.removeprefix("push-")
            run = r5_oidc.run_attempt(run_id, r5_oidc.run_title("publish", ticket), remote["head"])
            require(run["status"] == "completed", "GitHub 发布运行仍未结束")
            steps = r5_oidc.job_steps(run_id)
            push = steps.get(r5_oidc.PUSH_STEP, {})
            conclusion = push.get("conclusion")
            if conclusion == "success":
                require(steps.get(r5_oidc.CHECK_STEP, {}).get("conclusion") == "success",
                        "实际上传缺少此前的 OIDC 登录成功记录")
                result = {"exitCode": 0, "phase": "push-succeeded"}
            else:
                require(conclusion == "skipped", "证据无法确定 NuGet 是否受理，请保留意向并查证")
                result = {"started": False, "phase": "push-skipped"}
            result["pushStep"] = push
            result["runConclusion"] = run.get("conclusion")
        write_durable_json(receipt, intent | result | {"completedAt": timestamp()})
        print(receipt)
        if result.get("exitCode") == 0:
            intent["result"] = {"outcome": "accepted", "evidence": receipt.name, "version": intent["version"],
                                "uploadSha256": intent["uploadSha256"], "owners": intent["owners"]}
            self.save()
            return 0
        return 2

    def resolve(self, kind, name, outcome, receipt, evidence):
        attempts = self.attempts(kind, name)
        require(attempts, f"{name}/{kind} 没有待查证的上传意向")
        intent = attempts[-1]
        require(receipt == intent["receipt"] and "result" not in intent, "收据不属于当前待查证的上传")
        receipt_path = self.work / receipt
        require(evidence.is_file(), "需要本次上传的脱敏证据文件")
        evidence_bytes = evidence.read_bytes()
        proof = json.loads(evidence_bytes)
        require(isinstance(proof, dict), "需要结构化的上传查证凭证")
        result = {"outcome": "confirmed", "evidence": str(evidence), "evidenceSha256": bytes_sha256(evidence_bytes),
                  "version": intent["version"], "uploadSha256": intent["uploadSha256"], "owners": intent["owners"]}
        local = {}
        if receipt_path.is_file():
            local = proof if evidence == receipt_path else read_json(receipt_path)
            require(isinstance(local, dict) and all(local.get(key) == value for key, value in intent.items()),
                    "本地收据与当前上传意向不符")
        if outcome == "not-accepted":
            require(local.get("exitCode") != 0, "已有成功上传收据，须继续公开回读")
            result["outcome"] = "retry"
            local_proof = local.get("started") is False
            allowed_sources = ("nuget.org-support",)
        else:
            local_proof = local.get("exitCode") == 0
            allowed_sources = ("nuget.org-support", "nuget.org-publisher")
        if evidence == receipt_path:
            require(local_proof, "本地收据没有证实该次操作的结果")
        else:
            require(proof.get("receipt") == receipt and proof.get("outcome") == outcome
                    and proof.get("source") in allowed_sources, "外部凭证与当前收据、来源或操作结果不符")
            reference, reference_sha = proof.get("reference"), proof.get("referenceSha256")
            require(isinstance(reference, str) and reference.strip()
                    and isinstance(reference_sha, str) and HEX_SHA256.fullmatch(reference_sha),
                    "需要脱敏原始证据的文件路径与独立 SHA-256")
            original = (evidence.parent / reference).resolve()
            require(original not in (evidence, receipt_path) and original.is_file(), "缺少独立的脱敏原始证据文件")
            original_bytes = original.read_bytes()
            require(original_bytes.strip() and bytes_sha256(original_bytes) == reference_sha,
                    "脱敏原始证据为空或 SHA-256 不符")
            if outcome == "not-accepted":
                require(all(attempt.get("result", {}).get("referenceSha256") != reference_sha
                            for history in self.state["uploadIntents"].values() for attempt in history),
                        "该脱敏原始证据已用于较早的上传")
            result.update(source=proof["source"], reference=str(original), referenceSha256=reference_sha)
        if outcome == "confirmed" and kind == "main":
            self.confirming_main = {"package": name, "observation": result}
            try:
                verified = self.check_main(name)["status"] == "verified"
            finally:
                self.confirming_main = None
            require(verified, "公开主包的归属、签名或冻结内容尚未通过核对")
        if outcome == "confirmed" and kind == "symbols":
            main = self.check_main(name)
            require(main["status"] == "verified"
                    and normalized_owners(intent["owners"]) == normalized_owners(main["observation"]["owners"])
                    and normalized_owners(intent["owners"]) == normalized_owners(self.nuget.owners(name)["owners"]),
                    "符号包归属尚未通过核对")
            symbols = self.check_symbols(name, main)
            require(symbols and all(status == "verified" for status in symbols),
                    "公开符号的调试标识或内容尚未通过核对")
        intent["result"] = result
        self.save()

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
    upload = commands.add_parser("upload", help="登记上传意向并提交一个 R5 冻结归档")
    upload.add_argument("--kind", choices=("main", "symbols"), required=True)
    upload.add_argument("--package", required=True)
    upload.add_argument("--owner", action="append")
    upload.add_argument("--oidc", nargs=2, metavar=("DRAFT_ID", "LOGIN_RUN_ID"),
                        help="用草稿附件和同提交的成功登录运行发起 GitHub 托管上传")
    receipt = commands.add_parser("workflow-receipt", help="回读唯一托管运行并登记收据")
    receipt.add_argument("--kind", choices=("main", "symbols"), required=True)
    receipt.add_argument("--package", required=True)
    resolve = commands.add_parser("resolve", help="凭收据及证据核对待查证的 R5 上传")
    resolve.add_argument("--kind", choices=("main", "symbols"), required=True)
    resolve.add_argument("--package", required=True)
    resolve.add_argument("--receipt", required=True, help="上传意向中的收据文件名")
    resolve.add_argument("--outcome", choices=("confirmed", "not-accepted"), required=True)
    resolve.add_argument("--evidence", type=Path, required=True)
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
            if args.command == "upload":
                return progress.upload(args.kind, args.package, args.owner, lock, oidc=args.oidc)
            if args.command == "workflow-receipt":
                return progress.workflow_receipt(args.kind, args.package)
            if args.command == "resolve":
                progress.resolve(args.kind, args.package, args.outcome, args.receipt, args.evidence.resolve())
                return 0
            return progress.verify(names, args.main_only)
    except READBACK_ERRORS as error:
        print(f"公开发行核验失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
