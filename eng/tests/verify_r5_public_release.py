"""在隔离副本上核对 R5 部分受理和直接依赖 gate。"""

import argparse
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_automapper_packages import ADAPTER, COLLECTION, CORE, ENGINE
from r4_public_release import GALLERY, SIGNATURE, SYMBOLS
from r5_public_release import ReleaseProgress, load_release, verified_downloads
from verify import ROOT, VerificationError, read_json, require, sha256


DEBUG_GUID = "0123456789ABCDEF0123456789ABCDEF"


class IsolatedProtocol:
    def __init__(self):
        self.responses = {}
        self.requests = []
        self.nupkg_verifications = []

    def get(self, url, headers=None):
        self.requests.append(url)
        data = self.responses.get(url)
        return {"url": url, "httpStatus": 404 if data is None else 200}, data

    def certificates(self, work):
        return {"隔离样本指纹"}

    def owners(self, name):
        return {"owners": ["sample-owner"]}

    def signature(self, package, fingerprints, directory):
        with ZipFile(package) as file:
            require(file.read(SIGNATURE) == b"isolated signature fixture", "隔离签名标记不符")
        self.nupkg_verifications.append(package.name)
        log = directory / "signature.log"
        log.write_text("隔离协议样本，签名验证由真实 R4 实物单独覆盖。\n", encoding="utf-8")
        return {"owners": ["sample-owner"], "logSha256": sha256(log)}

    def symbol(self, directory, dll, pdb=None):
        return {"name": f"{dll.stem}.pdb", "guid": DEBUG_GUID,
                "checksum": "SHA256:isolated-fixture"}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.case = self.evidence / self._testMethodName
        self.case.mkdir()
        self.root = self.case / "frozen"
        shutil.copytree(self.batch, self.root)
        self.work = self.case / "progress"
        self.work.mkdir()
        self.protocol = IsolatedProtocol()

    def open_progress(self):
        manifest, _, handoff = load_release(self.root, self.batch_sha, self.manifest, self.manifest_sha,
                                            verify_carried=False)
        return ReleaseProgress(manifest, self.manifest_sha, self.root, self.batch_sha, handoff, self.work,
                               self.protocol, self.protocol)

    def assert_gate(self, progress, name, code, *, own, blocked, kind="main"):
        with redirect_stdout(log := StringIO()):
            actual = progress.symbol_gate(name) if kind == "symbols" else progress.gate(name)
        output = log.getvalue()
        with (self.case / "gate-results.log").open("a", encoding="utf-8") as stream:
            stream.write(f"gate {name} {kind} exitCode={actual}\n{output}")
        self.assertEqual(code, actual, output)
        result = json.loads(output.strip().splitlines()[-1])
        self.assertEqual(code == 0, result["ready"])
        self.assertEqual(own, result["main"])
        if kind == "main":
            self.assertEqual(blocked, result["blockedBy"])
        return result

    def archive(self, progress, name, kind="archive"):
        row = progress.manifest["packages"][name][kind]
        return self.root / row["path"], row["sha256"]

    def url(self, progress, name):
        return f"{GALLERY}/{name}/{progress.manifest['packages'][name]['version']}"

    def sample_main(self, progress, name, *, extra=False, omit_dependency=False):
        archive, _ = self.archive(progress, name)
        out = BytesIO()
        with ZipFile(archive) as original, ZipFile(out, "w") as sample:
            for member in original.namelist():
                content = original.read(member)
                if omit_dependency and member.endswith(".nuspec"):
                    tree = ET.fromstring(content)
                    group = tree.find(".//{*}dependencies/{*}group")
                    dependency = next(item for item in group if item.get("id") == ENGINE)
                    group.remove(dependency)
                    content = ET.tostring(tree)
                sample.writestr(member, content)
            sample.writestr(SIGNATURE, b"isolated signature fixture")
            if extra:
                sample.writestr("unexpected.txt", b"extra member")
        self.protocol.responses[self.url(progress, name)] = out.getvalue()

    def accept_main(self, progress, name):
        _, digest = self.archive(progress, name)
        progress.record("main", name, "accepted", "隔离样本主包受理", ["sample-owner"], digest)

    def test_adapter_waits_only_for_missing_or_changed_core_evidence_and_resumes(self):
        progress = self.open_progress()
        for name in (ENGINE, COLLECTION):
            self.sample_main(progress, name)
            self.accept_main(progress, name)
            self.assertEqual("verified", progress.check_main(name)["status"])
        predecessor_state = {name: progress.state["packages"][name]["main"][:] for name in (ENGINE, COLLECTION)}
        signature = self.root / progress.carried[CORE]["publicEvidence"]["signatureLog"]["path"]
        original = signature.read_bytes()
        for issue in ("missing", "changed"):
            with self.subTest(issue=issue):
                if issue == "missing":
                    signature.unlink()
                else:
                    signature.write_bytes(original + b"wrong SHA-256\n")
                progress = self.open_progress()
                self.assert_gate(progress, ADAPTER, 2, own="notVisible",
                                 blocked={CORE: {"version": "[10.5.1]", "status": "failed"}})
                core = progress.state["carried"][CORE][-1]
                try:
                    (self.case / f"core-{issue}.json").write_text(json.dumps(core, indent=2, ensure_ascii=False))
                    self.assertEqual("failed", core["status"])
                    self.assertIn({"missing": "缺少实物", "changed": "SHA-256"}[issue], core["reason"])
                    self.assertNotIn(CORE, read_json(progress.downloads)["packages"])
                finally:
                    signature.write_bytes(original)
                progress = self.open_progress()
                self.assert_gate(progress, ADAPTER, 0, own="notVisible", blocked={})
                self.assertEqual("verified", progress.state["carried"][CORE][-1]["status"])
                self.assertIn(CORE, read_json(progress.downloads)["packages"])
                self.assertEqual(predecessor_state, {name: progress.state["packages"][name]["main"]
                                                     for name in (ENGINE, COLLECTION)})
                self.assertEqual(1, self.protocol.requests.count(self.url(progress, ENGINE)))
                self.assertEqual(1, self.protocol.requests.count(self.url(progress, COLLECTION)))
        self.assertEqual([ENGINE, COLLECTION, ADAPTER], progress.manifest["publishOrder"])
        self.assertEqual(10, len(progress.carried))

    def test_content_conflict_extra_file_or_missing_dependency_rejects_version(self):
        progress = self.open_progress()
        self.sample_main(progress, ENGINE, extra=True)
        self.accept_main(progress, ENGINE)
        main = progress.check_main(ENGINE)
        self.assertEqual("failed", main["status"])
        self.assertIn('"extra": ["unexpected.txt"]', main["reason"])
        self.sample_main(progress, COLLECTION, omit_dependency=True)
        self.accept_main(progress, COLLECTION)
        collection = progress.check_main(COLLECTION)
        self.assertEqual("failed", collection["status"])
        self.assertIn('"changed": {"Du.AutoMapper.Collection.nuspec":', collection["reason"])
        self.assertNotIn(ENGINE, read_json(progress.downloads)["packages"])
        self.assertNotIn(COLLECTION, read_json(progress.downloads)["packages"])

    def test_visible_version_conflicts_until_ownership_and_content_match(self):
        progress = self.open_progress()
        self.sample_main(progress, ENGINE)
        progress.record("main", ENGINE, "duplicate", "隔离样本重复版本响应", None)
        self.assert_gate(progress, ENGINE, 2, own="conflict", blocked={})
        _, digest = self.archive(progress, ENGINE)
        with self.assertRaisesRegex(VerificationError, "实传主包 SHA-256"):
            progress.record("main", ENGINE, "confirmed", "隔离样本错误摘要", ["sample-owner"], "0" * 64)
        progress.record("main", ENGINE, "confirmed", "隔离样本确认版本归属", ["sample-owner"], digest)
        self.assert_gate(progress, ENGINE, 2, own="verified", blocked={})
        self.assert_gate(progress, COLLECTION, 0, own="notVisible", blocked={})

    def test_resume_after_acceptance_waits_for_main_and_exact_pdb_without_resubmission(self):
        progress = self.open_progress()
        self.accept_main(progress, ENGINE)
        self.assert_gate(progress, COLLECTION, 2, own="notVisible",
                         blocked={ENGINE: {"version": "[14.0.1]", "status": "pending"}})
        self.sample_main(progress, ENGINE)
        progress = self.open_progress()
        self.assert_gate(progress, COLLECTION, 0, own="notVisible", blocked={})
        self.assert_gate(progress, ENGINE, 2, own="verified", blocked={})
        self.assert_gate(progress, ENGINE, 0, own="verified", blocked=None, kind="symbols")
        _, digest = self.archive(progress, ENGINE, "symbols")
        progress.record("symbols", ENGINE, "accepted", "隔离样本符号受理", None, digest)
        self.assertEqual(2, progress.verify((ENGINE,), False))
        self.assert_gate(progress, ENGINE, 2, own="verified", blocked=None, kind="symbols")
        symbol_url = next(url for url in self.protocol.requests if url.startswith(SYMBOLS))
        self.protocol.responses[symbol_url] = b"wrong PDB bytes"
        progress = self.open_progress()
        self.assertEqual(1, progress.verify((ENGINE,), False))
        archive, _ = self.archive(progress, ENGINE, "symbols")
        with ZipFile(archive) as source:
            self.protocol.responses[symbol_url] = source.read("lib/net8.0/AutoMapper.pdb")
        progress = self.open_progress()
        self.assertEqual(0, progress.verify((ENGINE,), False))
        package = progress.state["packages"][ENGINE]
        self.assertEqual(["pending", "verified"], [row["status"] for row in package["main"]])
        symbols = package["symbols"]["lib/net8.0/AutoMapper.dll"]
        self.assertEqual(["pending", "pending", "pending", "failed", "verified"],
                         [row["status"] for row in symbols])
        self.assertIn("SHA-256 不符", symbols[-2]["reason"])
        self.assertEqual(symbols[-1]["frozenPdbSha256"], symbols[-1]["downloadSha256"])
        self.assertEqual(1, len(progress.state["external"][f"main/{ENGINE}"]))
        self.assertEqual(1, len(progress.state["external"][f"symbols/{ENGINE}"]))
        self.assertEqual(2, self.protocol.requests.count(self.url(progress, ENGINE)))
        self.assertEqual(1, len(self.protocol.nupkg_verifications))

    def test_visible_exact_pdb_prevents_symbol_push_without_a_receipt(self):
        progress = self.open_progress()
        self.sample_main(progress, ENGINE)
        self.accept_main(progress, ENGINE)
        archive, _ = self.archive(progress, ENGINE, "symbols")
        symbol_url = f"{SYMBOLS}/AutoMapper.pdb/{DEBUG_GUID}FFFFFFFF/AutoMapper.pdb"
        with ZipFile(archive) as symbols:
            self.protocol.responses[symbol_url] = symbols.read("lib/net8.0/AutoMapper.pdb")
        result = self.assert_gate(progress, ENGINE, 2, own="verified", blocked=None, kind="symbols")
        self.assertIsNone(result["symbolReceipt"])
        self.assertEqual({"lib/net8.0/AutoMapper.dll": "verified"}, result["symbols"])

    def test_queue_contains_only_three_pairs_and_three_pdb_targets(self):
        command = [sys.executable, "-B", "eng/r5_public_release.py", "--batch-root", str(self.root),
                   "--batch-sha256", self.batch_sha, "--manifest", str(self.manifest),
                   "--manifest-sha256", self.manifest_sha, "--work", str(self.work)]
        result = subprocess.run([*command, "queue"], cwd=ROOT, capture_output=True, text=True)
        (self.case / "queue.json").write_text(result.stdout)
        self.assertEqual(0, result.returncode, result.stderr)
        queue = json.loads(result.stdout)
        self.assertEqual([ENGINE, COLLECTION, ADAPTER], queue["uploadOrder"])
        self.assertEqual({ENGINE, COLLECTION, ADAPTER}, queue["archives"].keys())
        self.assertEqual(10, len(set(queue["carried"])))
        self.assertIn(CORE, queue["carried"])
        pairs = [row[kind] for row in queue["archives"].values() for kind in ("archive", "symbols")]
        self.assertEqual(6, len({row["sha256"] for row in pairs}))
        self.assertEqual(3, sum(len(row["targets"]) for row in queue["archives"].values()))
        self.assertEqual(3, len({target["pdb"] for row in queue["archives"].values()
                                for target in row["targets"].values()}))
        rejected = subprocess.run([*command, "record", "--kind", "main", "--package", CORE, "--outcome",
                                   "accepted", "--evidence", "隔离样本", "--owner", "sample-owner"], cwd=ROOT,
                                  capture_output=True, text=True)
        self.assertEqual(1, rejected.returncode)
        self.assertIn("命令所选包超出适用清单", rejected.stderr)

    def test_new_registration_requires_all_packages_and_independent_batch_identity(self):
        progress = self.open_progress()
        for name in (ENGINE, COLLECTION):
            self.sample_main(progress, name)
            self.accept_main(progress, name)
            self.assertEqual("verified", progress.check_main(name)["status"])
        digest = sha256(progress.downloads)
        with self.assertRaisesRegex(VerificationError, "缺少维护包"):
            verified_downloads(progress.downloads, digest, progress.manifest, self.manifest_sha, self.batch_sha)
        self.sample_main(progress, ADAPTER)
        self.accept_main(progress, ADAPTER)
        self.assertEqual("verified", progress.check_main(ADAPTER)["status"])
        digest = sha256(progress.downloads)
        rows = verified_downloads(progress.downloads, digest, progress.manifest, self.manifest_sha, self.batch_sha)
        self.assertEqual(13, len(rows))
        with self.assertRaisesRegex(VerificationError, "发行或冻结批次不符"):
            verified_downloads(progress.downloads, digest, progress.manifest, self.manifest_sha, "0" * 64)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--batch-sha", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args, unit_args = parser.parse_known_args()
    for key, value in vars(args).items():
        setattr(ReleaseTests, key, value.resolve() if isinstance(value, Path) else value)
    ReleaseTests.evidence.mkdir()
    unittest.main(argv=[sys.argv[0], *unit_args])
