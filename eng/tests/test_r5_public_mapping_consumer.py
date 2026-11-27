"""验证公开映射消费者按单侧预期判定业务结果。"""

from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import r5_public_mapping_consumer as consumer
from r5_public_mapping_consumer import (COLUMNS, COLLECTION_RESULT, FULL_NAME, PROJECTION_ROWS, SCENARIOS, SQLITE,
                                        SQLITE_VERSION, USER, accepted_business, assess_business)
from r2_packages import write_json
from verify import VerificationError, read_json


class PublicMappingBusinessTests(unittest.TestCase):
    def setUp(self):
        self.columns = read_json(COLUMNS)
        self.probe = {
            "scenarios": dict.fromkeys(SCENARIOS, "passed"),
            "user": deepcopy(USER),
            "collection": deepcopy(COLLECTION_RESULT),
            "projection": {
                "provider": SQLITE, "providerVersion": SQLITE_VERSION + ".0", "sqliteVersion": "3.50.4",
                "expression": "Select(User.FullName)", "fullName": FULL_NAME,
                "executed": {"Sql": "SELECT ...", "Columns": self.columns,
                             "Parameters": [{"DbType": "Int32", "Value": 6}]},
                "result": PROJECTION_ROWS,
            },
        }
        self.assertTrue(accepted_business(assess_business(self.probe, self.columns)))

    def test_rejects_missing_projection_even_when_probe_reports_it_passed(self):
        del self.probe["projection"]
        assessment = assess_business(self.probe, self.columns)
        self.assertEqual("failed", assessment["projection"]["status"])
        self.assertIsNone(assessment["projection"]["actual"])
        self.assertEqual("passed", assessment["collection"]["status"])
        self.assertFalse(accepted_business(assessment))

    def test_rejects_identical_wrong_user_update_on_both_releases(self):
        self.probe["user"]["IsActive"] = False
        for release in ("r4", "r5"):
            with self.subTest(release=release):
                assessment = assess_business(deepcopy(self.probe), self.columns)
                self.assertEqual({"expected": True, "actual": False, "missing": False},
                                 assessment["user"]["mismatches"]["IsActive"])
                self.assertEqual("passed", assessment["projection"]["status"])
                self.assertFalse(accepted_business(assessment))

    def run_entry_with_probe_results(self, *, change_r4=None, loaded_failure=None, comparison_failure=None):
        directory = Path(self.enterContext(TemporaryDirectory())) / "report"
        args = ["r5_public_mapping_consumer.py", "--r4-checksums", "r4.json", "--r5-checksums", "r5.json",
                "--dotnet", "/dotnet", "--output", str(directory)]
        base = self.probe | {"assemblies": [], "environment": {
            "RuntimeIdentifier": "osx-arm64", "FrameworkDescription": consumer.RUNTIME,
            "ProcessArchitecture": 3, "processArchitectureName": "Arm64", "processId": 7001,
        }}

        def inputs(run):
            run.columns = self.columns

        def packages(run):
            run.mapping_assets = {}
            run.graph = {"release": run.release}

        def run_probe(run, **kwargs):
            path = run.evidence / "probe.json"
            probe = deepcopy(base)
            if run.release == "r4" and change_r4:
                change_r4(probe)
            write_json(path, probe)
            return 0, path, path.with_suffix(".log")

        def verify_loaded(probe, graph, output):
            if graph["release"] == "r4" and loaded_failure:
                raise VerificationError(loaded_failure)
            return {}

        for method, replacement in (("inputs", inputs), ("restore", lambda run: None), ("packages", packages),
                                    ("build", lambda run: None), ("run_probe", run_probe)):
            self.enterContext(patch.object(consumer.PublicRun, method, replacement))
        self.enterContext(patch.object(consumer, "verify_loaded_assemblies", verify_loaded))
        compare = self.enterContext(patch.object(consumer, "compare_runs", side_effect=comparison_failure))
        with patch.object(sys, "argv", args), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(1, consumer.main())
        return directory, read_json(directory / "report.json"), compare

    def assert_r4_observed_but_excluded(self, directory, summary, message):
        side = read_json(directory / "r4/report.json")
        self.assertEqual("failed", side["inputQualification"]["status"])
        self.assertEqual("acceptance", side["inputQualification"]["stage"])
        self.assertIn(message, side["inputQualification"]["reason"])
        self.assertEqual(side["inputQualification"], summary["releases"]["r4"]["inputQualification"])
        self.assertEqual(dict.fromkeys(SCENARIOS, "unqualified"), summary["releases"]["r4"]["business"])
        self.assertEqual(dict.fromkeys(SCENARIOS, "passed"), summary["releases"]["r5"]["business"])
        self.assertEqual(0, summary["releases"]["r4"]["probeExitCode"])
        self.assertEqual("not_run", summary["comparison"]["status"])
        self.assertIs(False, summary["comparison"]["usableForVersionConclusion"])
        for name in SCENARIOS:
            with self.subTest(name=name):
                self.assertEqual("unqualified", side["business"][name]["status"])
                self.assertEqual("passed", side["business"][name]["observedStatus"])
                self.assertIsNotNone(side["business"][name]["actual"])

    def test_runtime_mismatch_excludes_passed_observations_from_side_and_summary(self):
        def wrong_runtime(probe):
            probe["environment"]["FrameworkDescription"] = ".NET 10.0.14"

        directory, summary, compare = self.run_entry_with_probe_results(change_r4=wrong_runtime)
        self.assert_r4_observed_but_excluded(directory, summary, ".NET 10.0.14")
        self.assertEqual(".NET 10.0.14", read_json(directory / "r4/probe.json")["environment"]["FrameworkDescription"])
        compare.assert_not_called()

    def test_loaded_dll_mismatch_excludes_passed_observations_from_side_and_summary(self):
        message = "AutoMapper.dll 实际加载位置或字节与 Release 输出不符"
        directory, summary, compare = self.run_entry_with_probe_results(loaded_failure=message)
        self.assert_r4_observed_but_excluded(directory, summary, message)
        compare.assert_not_called()

    def test_graph_mismatch_invalidates_version_conclusion_with_two_qualified_sides(self):
        message = "两侧包图的包版本差异或资产选择超出约定"
        _, summary, compare = self.run_entry_with_probe_results(comparison_failure=VerificationError(message))
        self.assertEqual({"status": "failed", "usableForVersionConclusion": False, "reason": message},
                         summary["comparison"])
        for release in ("r4", "r5"):
            self.assertEqual({"status": "passed"}, summary["releases"][release]["inputQualification"])
            self.assertEqual(dict.fromkeys(SCENARIOS, "passed"), summary["releases"][release]["business"])
        compare.assert_called_once()


if __name__ == "__main__":
    unittest.main()
