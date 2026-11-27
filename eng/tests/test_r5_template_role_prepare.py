"""固定模板准备与交接的定向回归，使用合成摘要失配。"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import r5_template_role_prepare as prepare
from verify import VerificationError, read_json, sha256


class RolePreparationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.stdout = self.enterContext(redirect_stdout(StringIO()))
        self.stderr = self.enterContext(redirect_stderr(StringIO()))

    def run_cli(self, args):
        with patch.object(sys, "argv", ["r5_template_role_prepare.py", *map(str, args)]):
            return prepare.main()

    def test_bad_attachment_stops_before_toolchain_and_builds(self):
        corrupted = self.root / "corrupted.json"
        corrupted.write_text("{}\n", encoding="utf-8")
        dest = self.root / "evidence"
        with patch.object(prepare.subprocess, "run") as command:
            result = self.run_cli(["prepare", "--output", dest, "--r4-checksums", corrupted,
                                   "--r5-checksums", self.root / "unused.json"])
        self.assertEqual(result, 1)
        command.assert_not_called()
        report = read_json(dest / "report.json")
        self.assertEqual((report["status"], report["exitCode"]), ("failed", 1))
        self.assertEqual(report["stages"], {**dict.fromkeys(prepare.STAGES, "not_run"), "attachments": "failed"})
        self.assertEqual(report["attachments"]["r4"]["sha256"], sha256(corrupted))
        self.assertIn(prepare.RELEASES["r4"][2], report["reason"])
        self.assertIn(sha256(corrupted), report["reason"])
        self.assertFalse((dest / "output").exists())

    def write_report(self):
        common = self.root / "evidence.json"
        prepare.write_json(common, {})
        reference = prepare.artifact(common, self.root)
        entries = {}
        for release in prepare.RELEASES:
            entries[release] = {}
            for entry in prepare.COUNTS:
                folder = self.root / "output" / release.upper() / entry
                folder.mkdir(parents=True)
                dll = folder / (prepare.project_path(entry).stem + ".dll")
                dll.write_bytes(f"{release} {entry}".encode())
                output = self.root / f"{release}-{entry}.json"
                assembly = prepare.artifact(dll, folder)
                prepare.write_json(output, {"entry": assembly, "files": {"files": {dll.name: sha256(dll)}}})
                entries[release][entry] = {
                    "cwd": folder.relative_to(self.root).as_posix(), "entry": assembly,
                    "outputVerification": prepare.artifact(output, self.root),
                    **dict.fromkeys(("graph", "rawAssets", "signedPackages"), reference),
                }
        report = self.root / "report.json"
        prepare.write_json(report, {"schemaVersion": 1, "status": "passed", "exitCode": 0, "entries": entries,
                                    "graphComparison": reference, "toolchain": {"dotnet": "/test/dotnet"}})
        return report

    def test_good_report_exports_independent_launches_without_starting_processes(self):
        report = self.write_report()
        with patch.object(prepare.subprocess, "run") as command:
            launches = prepare.verify_prepared(self.root, sha256(report))
        command.assert_not_called()
        self.assertEqual({value["cwd"] for side in launches.values() for value in side.values()},
                         {str(self.root / "output" / release.upper() / entry)
                          for release in prepare.RELEASES for entry in prepare.COUNTS})
        self.assertEqual(launches["r5"]["Migrator"]["argv"][-1], "-q")
        self.assertEqual(launches["r4"]["Web.Host"]["argv"][0], "/test/dotnet")
        self.assertEqual(launches["r4"]["Web.Host"]["entrySha256"],
                         sha256(Path(launches["r4"]["Web.Host"]["argv"][1])))

    def test_other_release_can_be_qualified_when_one_sealed_output_changes(self):
        report = self.write_report()
        bad = next((self.root / "output/R4/Migrator").glob("*.dll"))
        bad.write_bytes(b"replaced")
        digest = sha256(report)
        with self.assertRaises(VerificationError):
            prepare.verify_prepared(self.root, digest, only_release="r4")
        launches = prepare.verify_prepared(self.root, digest, only_release="r5")
        self.assertEqual(set(launches), {"r5"})
        self.assertEqual(set(launches["r5"]), {"Web.Host", "Migrator"})

    def test_wrong_report_digest_produces_no_launch_commands(self):
        report = self.write_report()
        result = self.run_cli(["verify", "--prepared", self.root, "--report-sha256", "0" * 64])
        self.assertEqual(result, 1)
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertIn("report.json SHA-256", self.stderr.getvalue())
        self.assertIn(sha256(report), self.stderr.getvalue())

    def test_changed_release_file_produces_no_launch_commands(self):
        report = self.write_report()
        release = self.root / "output/R5/Migrator"
        dll = next(release.glob("*.dll"))
        expected = sha256(dll)
        dll.write_bytes(b"replaced")
        result = self.run_cli(["verify", "--prepared", self.root, "--report-sha256", sha256(report)])
        self.assertEqual(result, 1)
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertIn(str(dll), self.stderr.getvalue())
        self.assertIn(expected, self.stderr.getvalue())
        self.assertIn(sha256(dll), self.stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
