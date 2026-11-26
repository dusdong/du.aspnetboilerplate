#!/usr/bin/env python3
"""用正式交接和隔离副本复跑 R4 首发清单预检。"""

import argparse
import re
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import r4_release_manifest as release
from verify import VerificationError, read_json
from verify_r4_candidate_batch import replace_member


class ReleaseManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = release.preflight(cls.handoff)

    def run_preflight(self, handoff, output):
        return subprocess.run(
            [sys.executable, "-B", release.__file__, "--handoff", handoff, "--output", output],
            check=False, capture_output=True, text=True,
        )

    def test_frozen_handoff_generates_repeatable_manifest(self):
        with TemporaryDirectory(prefix="r4-release-manifest-") as directory:
            output = Path(directory) / "release-manifest.json"
            first = self.run_preflight(self.handoff, output)
            self.assertEqual(0, first.returncode, first.stderr)
            original = output.read_bytes()
            again = self.run_preflight(self.handoff, output)
            self.assertEqual(0, again.returncode, again.stderr)
            self.assertEqual(original, output.read_bytes())
            report = read_json(output)

        self.assertEqual("v10.5.1", report["release"]["tag"])
        self.assertEqual("5758c8186b68dcc42ecc90164cf9d3f53cf3345e", report["release"]["commit"])
        self.assertEqual("19101266923a6422543a17e0963e3475c24923f2", report["qualificationCommit"])
        self.assertEqual(209, report["handoff"]["files"])
        self.assertEqual({
            "aspnetboilerplate": "bed57726b56f6f9de5c2d82e8dbe55e0130bddd0",
            "AutoMapper": "f646d492df918d27b9ac96c086933570965efef3",
            "AutoMapper.Collection": "306b49d7a59b7335a61d8116e1ab2f623a04740e",
        }, {source["path"]: source["finalCommit"] for source in report["producers"].values()})
        packages = report["packages"]
        self.assertEqual(13, len(packages))
        self.assertEqual(11, sum(name.startswith("Du.Abp") and row["version"] == "10.5.1"
                                 for name, row in packages.items()))
        self.assertEqual("14.0.0", packages["Du.AutoMapper"]["version"])
        self.assertEqual("11.0.0", packages["Du.AutoMapper.Collection"]["version"])
        self.assertEqual(18, sum(len(row["targets"]) for row in packages.values()))

    def test_orders_every_internal_dependency_before_its_consumer(self):
        packages = self.manifest["packages"]
        order = self.manifest["publishOrder"]
        self.assertCountEqual(packages.keys(), order)
        for name, row in packages.items():
            from_groups = {dep for target in row["targets"].values() for dep in target["internalDependencies"]}
            self.assertEqual({dep: packages[dep]["version"] for dep in from_groups}, row["directInternalDependencies"])
            for dep in from_groups:
                self.assertLess(order.index(dep), order.index(name), f"{dep} → {name}")

        self.assertEqual({"Du.AutoMapper": "[14.0.0]"},
                         packages["Du.AutoMapper.Collection"]["targets"]["net8.0"]["internalDependencies"])
        self.assertEqual({
            "net10.0": {"internalDependencies": {"Du.Abp.Web.Common": "10.5.1"}},
            "net9.0": {"internalDependencies": {"Du.Abp.Web.Common": "10.5.1"}},
        }, packages["Du.Abp.AspNetCore"]["targets"])

    def test_rejects_replacement_for_each_of_the_26_archives(self):
        records = [row[kind] for row in self.manifest["packages"].values() for kind in ("archive", "symbols")]
        self.assertEqual(26, len({record["path"] for record in records}))
        with TemporaryDirectory(prefix="r4-release-archives-") as directory:
            temp = Path(directory)
            copy = shutil.copytree(self.handoff, temp / "handoff")
            rejected = temp / "rejected.json"
            for record in records:
                path = copy / record["path"]
                original = path.read_bytes()
                self.assertEqual(record["bytes"], len(original))
                path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
                try:
                    result = self.run_preflight(copy, rejected)
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertIn(record["path"] + " SHA-256 不符", result.stderr)
                    self.assertIn(record["sha256"], result.stderr)
                    self.assertFalse(rejected.exists())
                finally:
                    path.write_bytes(original)

    def test_rejects_rewritten_checksum_table(self):
        with TemporaryDirectory(prefix="r4-release-checksums-") as directory:
            copy = Path(directory)
            (copy / "SHA256SUMS").write_bytes((self.handoff / "SHA256SUMS").read_bytes() + b"\n")
            with self.assertRaisesRegex(VerificationError, "SHA256SUMS SHA-256 不符"):
                release.preflight(copy)

    def test_rejects_table_row_mismatched_with_frozen_archive(self):
        with TemporaryDirectory(prefix="r4-release-table-") as directory:
            copy = Path(directory)
            table = (self.handoff / "packages.tsv").read_text(encoding="utf-8")
            digest = self.manifest["packages"]["Du.Abp"]["archive"]["sha256"]
            (copy / "packages.tsv").write_text(table.replace(digest, "0" * 64, 1), encoding="utf-8")
            receipt = release.verify_handoff(self.handoff)
            with self.assertRaisesRegex(VerificationError, r"packages.tsv/Du\.Abp/archive/sha256"):
                release.verify_package_table(copy, receipt, self.manifest["packages"], self.manifest["producers"])

    def test_rejects_dependency_drift_in_only_one_target_group(self):
        name = "Du.Abp.AspNetCore"
        manifest = read_json(release.MANIFEST)
        row = manifest["packages"][name]
        path = self.handoff / self.manifest["packages"][name]["archive"]["path"]
        with ZipFile(path) as archive:
            member = next(member for member in archive.namelist() if member.endswith(".nuspec"))

        def change_net10_dependency(payload):
            document = ET.fromstring(payload)
            dependency = document.find(".//{*}group[@targetFramework='net10.0']/{*}dependency[@id='Du.Abp.Web.Common']")
            self.assertIsNotNone(dependency)
            dependency.set("version", "[99.0.0]")
            return ET.tostring(document)

        with TemporaryDirectory(prefix="r4-release-nuspec-") as directory:
            changed = Path(directory) / path.name
            replace_member(path, changed, member, change_net10_dependency)
            diagnostic = r"nuspec/net10\.0/dependencies/Du\.Abp\.Web\.Common"
            with self.assertRaisesRegex(VerificationError, diagnostic):
                release.verify_nuspec(changed, name, row, manifest["producers"]["framework"], manifest["packages"].keys())

    def test_rejects_wrong_release_commit_gitlink(self):
        different_commit = read_json(release.MANIFEST)["baseCommit"]
        with patch.dict(release.RELEASE, {"commit": different_commit}):
            tag = re.escape(release.RELEASE["tag"])
            with self.assertRaisesRegex(VerificationError, rf"{tag}/aspnetboilerplate/gitlink"):
                release.verify_release_sources(read_json(release.MANIFEST))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    args, unittest_args = parser.parse_known_args()
    ReleaseManifestTests.handoff = args.handoff.resolve()
    unittest.main(argv=[sys.argv[0], *unittest_args])
