import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from run_verify_r0_tests import result_exit_code


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify


BASELINE = verify.read_json(verify.ROOT / verify.BASELINE)
VALIDATION = BASELINE["validation"]
CORE, ASPNET, EFCORE = VALIDATION["tests"]["suites"]


def trx_fixture(path, suite, counters=None, namespace=True, rows=True):
    prefix = "{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}" if namespace else ""
    root = ET.Element(prefix + "TestRun")
    results = ET.SubElement(root, prefix + "Results")
    if rows:
        for i in range(suite["passed"]):
            ET.SubElement(results, prefix + "UnitTestResult", testName=f"Fixture.Tests.Passing_{i}", outcome="Passed")
        for skip in suite["skippedTests"]:
            ET.SubElement(results, prefix + "UnitTestResult", testName=skip["test"], outcome="NotExecuted")
    summary = ET.SubElement(root, prefix + "ResultSummary")
    counts = dict(total=suite["totalReported"], executed=suite["passed"], passed=suite["passed"],
                  failed=suite["failed"], notExecuted=0)
    counts.update(counters or {})
    ET.SubElement(summary, prefix + "Counters", {key: str(value) for key, value in counts.items()})
    ET.ElementTree(root).write(path, encoding="utf-8")


class RunFixture(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        self.run = verify.R0Run(verify.ROOT, self.evidence)
        self.run.baseline = BASELINE

    def assert_stopped(self, at, reason):
        report = verify.read_json(self.run.report_path)
        self.assertEqual(report["exitCode"], 1)
        self.assertEqual(report["stages"][at]["status"], "failed")
        self.assertIn(reason, report["stages"][at]["reason"])
        following = verify.STAGES[verify.STAGES.index(at) + 1:]
        for stage in following:
            self.assertEqual(report["stages"][stage]["status"], "not_run")
            self.assertEqual(report["stages"][stage]["commands"], [])

    def fake_pipeline(self, *, through):
        actions = {
            "preflight": "preflight", "primary_materialize": "shell", "sdk": "sdk",
            "primary_restore": "restore", "repeat_materialize": "shell", "repeat_restore": "restore",
            "restore_compare": "compare_restore", "project_identity": "identity",
            "release_build": "shell", "api_compare": "api", "dotnet_tests": "tests",
        }
        for name in set(actions.values()) - {actions[through]}:
            if name in {actions[s] for s in verify.STAGES[:verify.STAGES.index(through)]}:
                patcher = patch.object(self.run, name)
                patcher.start()
                self.addCleanup(patcher.stop)


class TrxTests(RunFixture):
    def test_vstest_console_version_in_english_and_chinese(self):
        self.assertEqual(verify.vstest_version("\nVSTest version 17.14.1 (arm64)\n"),
                         "17.14.1 (arm64)")
        self.assertEqual(verify.vstest_version("\nVSTest 版本 17.14.1 (arm64)\n"),
                         "17.14.1 (arm64)")

    def check(self, suite, path, reason):
        self.run.suites = [suite]
        self.fake_pipeline(through="dotnet_tests")
        with patch.object(self.run, "sqlite"), patch.object(self.run, "shell"):
            target = self.evidence / "trx" / f"{suite['suite']}.trx"
            target.parent.mkdir()
            if path.exists():
                shutil.copyfile(path, target)
            self.assertEqual(self.run.execute(self.root), 1)
        self.assert_stopped("dotnet_tests", reason)
        record = verify.read_json(self.run.report_path)["stages"]["dotnet_tests"]["suites"][0]
        self.assertEqual(record["suite"], suite["suite"])
        self.assertIn(str(target), record["reason"])

    def test_known_core_summary_exception_with_full_names(self):
        path = self.root / "core.trx"
        trx_fixture(path, CORE)
        result = verify.read_trx(path, CORE)
        self.assertEqual((result["passed"], result["failed"], result["skipped"]), (1105, 0, 2))
        self.assertEqual(result["knownSummaryDifference"], {"notExecuted": {"summary": 0, "details": 2}})
        self.assertEqual({s["test"] for s in result["skippedTests"]},
                         {s["test"] for s in CORE["skippedTests"]})

    def test_regular_summary_with_and_without_namespace(self):
        for suite, namespace in ((CORE, False), (ASPNET, True), (EFCORE, False)):
            with self.subTest(suite=suite["suite"]):
                path = self.root / "suite.trx"
                trx_fixture(path, suite, {"notExecuted": suite["skipped"]}, namespace)
                self.assertIsNone(verify.read_trx(path, suite)["knownSummaryDifference"])

    def test_missing_trx_stops_pipeline(self):
        self.check(ASPNET, self.root / "missing.trx", "No such file")

    def test_unreadable_trx_stops_pipeline(self):
        path = self.root / "bad.trx"
        path.write_text("<TestRun><broken", encoding="utf-8")
        self.check(EFCORE, path, "unclosed token")

    def test_no_details_stops_pipeline(self):
        path = self.root / "no-results.trx"
        trx_fixture(path, CORE, rows=False)
        self.check(CORE, path, "匹配数为零")

    def test_zero_matching_result_elements(self):
        path = self.root / "no-results.trx"
        trx_fixture(path, CORE)
        text = path.read_text(encoding="utf-8").replace("UnitTestResult", "OtherResult")
        path.write_text(text, encoding="utf-8")
        self.check(CORE, path, "匹配数为零")

    def test_unexpected_skip_matches_suffix_only(self):
        path = self.root / "unexpected.trx"
        fixture = copy.deepcopy(CORE)
        name = fixture["skippedTests"][0]["test"]
        fixture["skippedTests"][0]["test"] = "Unexpected." + name.split(".", 1)[1]
        trx_fixture(path, fixture)
        self.check(CORE, path, "Unexpected.")

    def test_contradictory_key_counts_stop_pipeline(self):
        path = self.root / "counts.trx"
        trx_fixture(path, CORE, {"executed": 1104})
        self.check(CORE, path, "汇总计数应为")

    def test_incorrect_skipped_summary_other_than_known_case(self):
        path = self.root / "counts.trx"
        trx_fixture(path, CORE, {"notExecuted": 1})
        self.check(CORE, path, "汇总计数应为")


class PreflightTests(RunFixture):
    def test_missing_fixed_object(self):
        # Git 对象查询用夹具模拟，预检及报告仍走统一入口。
        git = self.run.git

        def missing(repo, log, *args):
            if args[:1] == ("cat-file",):
                return "missing"
            if args[:1] == ("status",):
                return ""
            return git(repo, log, *args)

        with (
            patch.object(verify.shutil, "which", return_value="fixture"),
            patch.object(self.run, "git_inputs", return_value={"head": "fixture"}),
            patch.object(self.run, "git", side_effect=missing),
        ):
            self.run.report["environment"].update(platform="Darwin", architecture="arm64")
            self.assertEqual(self.run.execute(self.root), 1)
        self.assert_stopped("preflight", BASELINE["frameworkInputCommit"])

    def test_sdk_measured_in_primary_and_rejects_mismatch(self):
        self.fake_pipeline(through="sdk")
        seen = []

        def fake_dotnet(argv, cwd, log):
            seen.append(cwd)
            if log == "dotnet-version.log":
                return "10.0.100"
            if log == "dotnet-info.log":
                return "RID: osx-arm64"
            return "Microsoft.NETCore.App 9.0.10 [/sdk]"

        with patch.object(self.run, "read_command", side_effect=fake_dotnet):
            self.assertEqual(self.run.execute(self.root), 1)
        self.assertEqual(seen, [self.run.work / "primary"] * 3)
        self.assert_stopped("sdk", "10.0.100")


class ComparisonTests(RunFixture):
    def test_transitive_drift_prevents_build_api_and_dotnet_tests(self):
        self.fake_pipeline(through="restore_compare")
        self.run.restore_baseline = verify.MAINTENANCE / VALIDATION["restore"]["inventory"]
        manifest = verify.read_json(verify.ROOT / self.run.restore_baseline)
        (self.evidence / "primary-restore-inventory.json").write_text(json.dumps(manifest), encoding="utf-8")
        project, info = next(iter(manifest["projects"].items()))
        target = info["targets"][0]
        package = next(p for p in target["packages"] if p["dependency"] == "transitive")
        original = package["version"]
        package["version"] = "99.98.97"
        (self.evidence / "repeat-restore-inventory.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(self.run.execute(self.root), 1)
        self.assert_stopped("restore_compare", "restore-baseline-repeat.log")
        diff = (self.evidence / "restore-baseline-repeat.log").read_text(encoding="utf-8")
        for detail in (project, "[net9.0]", package["id"], original, "99.98.97"):
            self.assertIn(detail, diff)

    def test_api_parameter_mutation_propagates(self):
        self.fake_pipeline(through="api_compare")
        p = BASELINE["initialPackageClosure"]["packages"][0]
        path = verify.ROOT / verify.MAINTENANCE / p["apiInventory"]
        self.run.packages = [p]
        dll = self.root / "Abp.dll"
        dll.touch()
        self.run.dlls = {p["assemblyName"]: dll}
        manifest = verify.read_json(path)
        members = manifest["types"]["Abp.Application.Features.Feature"]
        signature = "method [Public, HideBySig] RemoveChildFeature(System.String name) -> System.Void [Default]"
        members[members.index(signature)] = signature.replace("System.String name", "System.Int32 name")
        manifest["sha256"] = verify.sha256(dll)
        command = self.run.command

        def extract_fixture(args, cwd, log, **kwargs):
            if args[0] == "dotnet":
                if output := kwargs.get("output"):
                    self.run.evidence_file(output).write_text(json.dumps(manifest), encoding="utf-8")
                return 0, self.run.evidence_file(log)
            return command(args, cwd, log, **kwargs)

        with patch.object(self.run, "command", side_effect=extract_fixture):
            self.assertEqual(self.run.execute(self.root), 1)
        self.assert_stopped("api_compare", "Abp.comparison.json")
        diff = verify.read_json(self.evidence / "api/Abp.comparison.json")
        self.assertEqual(diff["assembly"], "Abp")
        changes = diff["changes"]["types"]["Abp.Application.Features.Feature"]
        self.assertEqual(changes["removed"], [signature])
        self.assertIn("System.Int32 name", changes["added"][0])

    def test_missing_dll_points_to_project_and_evidence(self):
        self.fake_pipeline(through="api_compare")
        self.run.packages = [BASELINE["initialPackageClosure"]["packages"][0]]
        self.run.dlls = {"Abp": self.root / "missing.dll"}
        self.assertEqual(self.run.execute(self.root), 1)
        self.assert_stopped("api_compare", "src/Abp/Abp.csproj 缺少 Release DLL")
        self.assertIn("Abp-msbuild.json.log", self.run.report["reason"])

    def test_missing_evaluated_properties_points_to_project_and_evidence(self):
        self.fake_pipeline(through="project_identity")
        self.run.packages = [BASELINE["initialPackageClosure"]["packages"][0]]
        msbuild = self.evidence / "Abp-msbuild.json.log"
        msbuild.write_text("cwd=fixture\n{\n  \"Properties\": {}\n}\nexitCode=0\n", encoding="utf-8")
        self.assertEqual(self.run.execute(self.root), 1)
        self.assert_stopped("project_identity", "Abp-msbuild.json.log")
        self.assertIn("src/Abp/Abp.csproj", self.run.report["reason"])


class SelfCheckExitTests(unittest.TestCase):
    def test_result_exit_requires_success_and_nonzero_effective_count(self):
        class Cases(unittest.TestCase):
            def passing(self):
                pass

            def failing(self):
                self.fail("fixture")

            @unittest.skip("fixture")
            def skipping(self):
                pass

        for cases, expected in (([], 1), (["skipping"], 1), (["failing"], 1), (["passing"], 0)):
            with self.subTest(cases=cases):
                suite = unittest.TestSuite(Cases(name) for name in cases)
                result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
                self.assertEqual(result_exit_code(result), expected)
