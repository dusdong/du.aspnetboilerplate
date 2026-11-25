"""验证 .NET 10 运行诊断保存原始观测并读取搬移后的实物。"""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_template_net9_runtime import HOST_LIBRARIES, SHARED
from r3_web_host import PREFIX, artifact, project_path, write_json
from verify import VerificationError, read_json, sha256
from verify_r3_template_net10_runtime import PATCH_VERSION, fixture_cases


class RelocatedRuntimeEvidenceTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name).resolve()
        self.passed = root / "copied"
        self.evidence = root / "diagnostics"
        self.evidence.mkdir()
        relative = Path("source/aspnet-core") / project_path("Web.Host").parent / "bin/Release/net10.0"
        self.output = self.passed / relative
        self.original_output = root / "unavailable" / relative
        self.output.mkdir(parents=True)
        self.observed = {"pid": 123, "assemblies": []}

        def add_file(path, *, observed=None):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(path.name.encode())
            digest = sha256(path)
            if observed is not None:
                identity = f"{path.stem}, Version=1.0.0.0"
                self.observed["assemblies"].append({
                    "name": path.stem, "fullName": identity, "diskFullName": identity,
                    "moduleVersionId": "fixture", "isDefaultContext": True, "context": "Default", "contextId": 1,
                    "path": str(observed), "sha256": digest,
                })
            return digest

        def add_output(relative, *, loads=True):
            return add_file(self.output / relative, observed=self.original_output / relative if loads else None)

        trace = {}
        for shared, anchor in SHARED.items():
            framework = root / "shared" / shared / PATCH_VERSION
            path = framework / f"{anchor}.dll"
            add_file(path, observed=path)
            trace[shared] = {"path": str(framework), "version": PATCH_VERSION}

        frameworks = ("Abp", *(f"Abp.Fixture{index}" for index in range(10)))
        names = (*frameworks, *HOST_LIBRARIES, "AutoMapper.Collection")
        copies = {}
        for name in names:
            relative_dll = f"{name}.dll"
            if name == "Microsoft.Data.SqlClient":
                relative_dll = f"runtimes/unix/{relative_dll}"
            copies[relative_dll] = {"package": f"Du.{name}" if name in frameworks else name,
                                    "sha256": add_output(relative_dll, loads=name != "AutoMapper.Collection")}
        entry = f"{PREFIX}Web.Host.dll"
        digest = add_output(entry)
        manifest = self.passed / "Web.Host-output.json"
        write_json(manifest, {
            "entry": {"path": entry, "sha256": digest}, "packageCopies": copies,
            "maintenanceDlls": {f"{name}.dll": copies[f"{name}.dll"] for name in frameworks},
            "files": {"files": {entry: digest, **{file: row["sha256"] for file, row in copies.items()}}},
        })
        self.observed_path = self.passed / "net10-host-loaded.json"
        write_json(self.observed_path, self.observed)
        self.base = {
            "inputs": {"entryOutputs": {"net10": {"Web.Host": artifact(manifest, self.passed)}}},
            "rounds": {"net10": {
                "inputs": {"path": (relative / entry).as_posix(), "sha256": digest},
                "host": {"pid": self.observed["pid"], "cwd": str(self.original_output), "entrySha256": digest,
                         "argv": ["dotnet", str(self.original_output / entry)], "sharedRuntime": trace},
            }},
        }

    def test_relocated_output_verifies_original_observation_and_four_rejections(self):
        self.assertFalse(self.original_output.exists())
        raw = self.observed_path.read_bytes()
        results = fixture_cases(self.passed, self.base, self.evidence)
        self.assertEqual([item["case"] for item in results], [
            "wrong_runtime_major", "wrong_runtime_patch", "wrong_framework_origin", "wrong_provider_digest",
        ])
        self.assertTrue(all(item["assertionRejected"] for item in results))
        self.assertEqual(self.observed_path.read_bytes(), raw)
        baseline = read_json(self.evidence / "fixture-baseline.json")
        self.assertEqual(baseline["originalOutput"], str(self.original_output))
        self.assertEqual(baseline["suppliedOutput"], str(self.output))
        self.assertEqual(baseline["pid"], self.observed["pid"])

    def test_missing_or_mismatched_supplied_output_stops_before_fixture_generation(self):
        path = self.output / "Abp.dll"
        path.unlink()
        with self.assertRaisesRegex(VerificationError, r"缺少实物 .*Abp\.dll"):
            fixture_cases(self.passed, self.base, self.evidence)
        path.write_bytes(b"other assembly")
        with self.assertRaisesRegex(VerificationError, r"Abp\.dll SHA-256 不符"):
            fixture_cases(self.passed, self.base, self.evidence)
        self.assertEqual(list(self.evidence.iterdir()), [])

    def test_observation_of_supplied_dll_is_rejected_when_outside_recorded_output(self):
        abp = next(row for row in self.observed["assemblies"] if row["name"] == "Abp")
        abp["path"] = str(self.output / "Abp.dll")
        write_json(self.observed_path, self.observed)
        with self.assertRaisesRegex(VerificationError, "Abp 从本轮输出之外加载"):
            fixture_cases(self.passed, self.base, self.evidence)
        self.assertEqual(list(self.evidence.iterdir()), [])
