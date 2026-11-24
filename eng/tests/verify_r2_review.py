#!/usr/bin/env python3
"""使用正式 R2 输入及已构建的取证工具复验来源、内部版本范围和 R1 归档失败路径。"""

import argparse
import copy
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r2_assets import check_assets
from r2_diagnostics import edited_zip
from r2_packages import R1_COMMIT, R1_TREE, SDK, verify_packages, verify_source, write_json
from r2_verify import R2Run
from verify import ROOT, VerificationError, read_json, sha256


class ReviewChecks(unittest.TestCase):
    def case_run(self, label):
        directory = self.output / label
        directory.mkdir()
        run = R2Run(directory, self.dotnet)
        run.metadata_tool = self.formal / "tools/metadata/bin/Release/net10.0/R2Metadata.dll"
        run.api_tool = self.formal / "tools/api/bin/Release/net9.0/ApiInventory.dll"
        run.report["inputs"] = self.inputs
        return run

    def source_case(self, label, change, patch):
        run = self.case_run(label)
        declared = copy.deepcopy(self.manifest)
        change(declared)
        declared["sourceProof"]["patchSha256"] = hashlib.sha256(patch).hexdigest()
        (run.evidence / "source.patch").write_bytes(patch)
        manifest = run.evidence / "manifest.json"
        write_json(manifest, declared)
        source = run.step("preflight", verify_source, run, manifest, declared)
        write_json(run.evidence / "source-result.json", source)
        return source

    def test_committed_empty_patch_with_independent_base(self):
        base = "6c4580c5e7ea41154696c071a53fd200059a768b"
        tree = subprocess.check_output(
            ["git", "-C", ROOT / "aspnetboilerplate", "rev-parse", f"{base}^{{tree}}"], text=True).strip()
        for label, commit, candidate_tree in (
            ("committed-empty", self.manifest["superproject"]["frameworkGitlink"],
             self.inputs["source"]["gitlinkTree"]),
            ("committed-independent-base", base, tree),
        ):
            with self.subTest(label=label):
                def clean(declared):
                    declared["sourceProof"].update(baseCommit=commit, commit=commit, tree=candidate_tree)

                source = self.source_case(label, clean, b"")
                self.assertEqual(source["mode"], "committed")
                self.assertEqual(source["tree"], candidate_tree)
                self.assertEqual(source["commit"], commit)
        self.assertNotEqual(source["baseTree"], source["gitlinkTree"])

    def test_committed_candidate_can_replay_from_separate_base(self):
        base = "6c4580c5e7ea41154696c071a53fd200059a768b"
        patch = subprocess.check_output(
            ["git", "-C", ROOT / "aspnetboilerplate", "diff", "--full-index", "--binary", base, R1_COMMIT])

        def committed(declared):
            declared["sourceProof"].update(baseCommit=base, commit=R1_COMMIT, tree=R1_TREE)

        source = self.source_case("committed-replayed", committed, patch)
        self.assertEqual(source["commit"], R1_COMMIT)
        self.assertEqual(source["mode"], "committed")
        self.assertNotEqual(source["baseTree"], source["gitlinkTree"])
        self.assertNotEqual(source["commit"], self.manifest["superproject"]["frameworkGitlink"])

    def test_wrong_commit_and_tree_object_are_rejected(self):
        patch = (self.manifest_path.parent / "source.patch").read_bytes()
        for label, commit, diagnostic in (
            ("misattributed-commit", self.manifest["sourceProof"]["baseCommit"], "与候选树"),
            ("non-commit-object", self.inputs["source"]["gitlinkTree"], "预期 commit"),
        ):
            with self.subTest(label=label):
                def claim(declared):
                    declared["sourceProof"]["commit"] = commit

                with self.assertRaisesRegex(VerificationError, diagnostic):
                    self.source_case(label, claim, patch)
                failed = read_json(self.output / label / "report.json")["stages"]["preflight"]
                self.assertEqual((failed["status"], failed["exitCode"]), ("failed", 1))

    def package_case(self, run, range_text):
        declared = copy.deepcopy(self.manifest)
        name = "Du.Abp.Web.Common"
        original = f'id="Du.Abp" version="{declared["version"]}"'.encode()
        modified = f'id="Du.Abp" version="{range_text}"'.encode()

        def replace(archive):
            nuspec = next(name for name in archive.namelist() if name.endswith(".nuspec"))
            content = archive.read(nuspec)
            self.assertEqual(content.count(original), 2)
            return {nuspec: content.replace(original, modified)}

        for folder, kind in (("feed", "package"), ("symbols", "symbols")):
            target = run.evidence / folder
            shutil.copytree(self.manifest_path.parent / folder, target)
            entry = declared["packages"][name][kind]
            path = target / entry["file"]
            edited_zip(path, replace)
            entry["sha256"] = sha256(path)
        manifest = run.evidence / "manifest.json"
        write_json(manifest, declared)
        return run.step("packages", verify_packages, run, run.evidence / "feed", manifest,
                        run.evidence / "symbols", self.r1)

    def test_bounded_range_in_package_and_real_restore(self):
        run = self.case_run("bounded-range")
        version = self.manifest["version"]
        bound = f"[{version},10.5.1)"
        candidate = self.package_case(run, bound)
        write_json(run.evidence / "candidate.json", candidate)
        tfm = "net10.0"
        feed = run.evidence / "feed"
        root, env, restore, _ = run.consumer(tfm, feed, version, "consumer")
        run.step(f"{tfm}/restore", run.restore, tfm, root, env, restore)
        assets = read_json(root / "obj/project.assets.json")
        edge = assets["targets"][tfm][f"Du.Abp.Web.Common/{version}"]["dependencies"]["Du.Abp"]
        self.assertEqual(edge.replace(" ", ""), bound)
        args = (tfm, root / "MinimalBackend.csproj", Path(env["NUGET_PACKAGES"]), feed, candidate,
                "10.0.15", run.check_dependency_ranges)
        verified = run.step(f"{tfm}/assets", check_assets, assets, *args)
        self.assertEqual(verified[f"Du.Abp/{version}"]["version"], version)
        for label, value in (("exclusive-lower", f"({version},10.5.1)"),
                             ("lower-too-low", "[10.5.0,10.5.1)"),
                             ("exclusive-upper-equal", f"[{version},{version})"),
                             ("floating", "10.5.1-*")):
            with self.subTest(label=label):
                fixture = copy.deepcopy(assets)
                fixture["targets"][tfm][f"Du.Abp.Web.Common/{version}"]["dependencies"]["Du.Abp"] = value
                write_json(run.evidence / f"{label}.json", fixture)
                with self.assertRaisesRegex(VerificationError, "内部依赖范围须包含"):
                    check_assets(fixture, *args)
                shutil.copy2(run.evidence / f"{tfm}-assets-internal-ranges.log",
                             run.evidence / f"{label}.log")
        version_fixture = copy.deepcopy(assets)
        graph = version_fixture["targets"][tfm]
        graph["Du.Abp/10.5.1-r2.2"] = graph.pop(f"Du.Abp/{version}")
        write_json(run.evidence / "wrong-resolved-version.json", version_fixture)
        with self.assertRaisesRegex(VerificationError, "框架包混装"):
            check_assets(version_fixture, *args)

    def test_package_rejects_excluded_candidate(self):
        version = self.manifest["version"]
        run = self.case_run("package-excluded-candidate")
        with self.assertRaisesRegex(VerificationError, "内部依赖范围须包含"):
            self.package_case(run, f"({version},10.5.1)")
        stage = read_json(run.report_path)["stages"]["packages"]
        self.assertEqual((stage["status"], stage["exitCode"]), ("failed", 1))

    def test_corrupt_archives_fail_the_profile_and_leave_later_stages_not_run(self):
        for file in ("final-raw-assets.tar.gz", "release-dlls.tar.gz"):
            with self.subTest(file=file):
                fixture = self.output / f"invalid-{file}"
                fixture.mkdir()
                (fixture / file).write_bytes(b"not a tar.gz")
                for source in self.r1.iterdir():
                    if source.name != file:
                        (fixture / source.name).symlink_to(source)
                results = fixture / "runs"
                cmd = [sys.executable, "-B", ROOT / "eng/verify.py", "--profile", "r2", "--dotnet", self.dotnet,
                       "--candidate-feed", self.manifest_path.parent / "feed",
                       "--candidate-manifest", self.manifest_path, "--r1-evidence", fixture,
                       "--evidence-root", results]
                write_json(fixture / "command.json", [str(arg) for arg in cmd])
                with (fixture / "profile.log").open("wb") as stream:
                    execution = subprocess.run(cmd, stdout=stream, stderr=subprocess.STDOUT)
                self.assertEqual(execution.returncode, 1)
                report = read_json(next(results.glob("r2-*/report.json")))
                self.assertEqual((report["status"], report["exitCode"]), ("failed", 1))
                self.assertIn(file, report["stages"]["packages"]["reason"])
                self.assertEqual(report["stages"]["packages"]["status"], "failed")
                for stage in ("negative_packages", "net9.0/restore", "net10.0/restore"):
                    self.assertEqual(report["stages"][stage]["status"], "not_run")
                    self.assertIn(file, report["stages"][stage]["reason"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("formal_run", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    ReviewChecks.formal = args.formal_run.resolve()
    ReviewChecks.output = args.output.resolve()
    ReviewChecks.output.mkdir()
    formal_report = read_json(ReviewChecks.formal / "report.json")
    ReviewChecks.inputs = formal_report["inputs"]
    ReviewChecks.manifest_path = Path(ReviewChecks.inputs["manifest"])
    ReviewChecks.manifest = read_json(ReviewChecks.manifest_path)
    if ReviewChecks.manifest["sdk"] != SDK:
        parser.error(f"夹具需使用 SDK {SDK}")
    ReviewChecks.r1 = Path(ReviewChecks.inputs["r1Evidence"])
    ReviewChecks.dotnet = Path(formal_report["environment"]["dotnet"])
    unittest.main(argv=[sys.argv[0]], verbosity=2)
