"""公开回退入口的隔离测试，使用合成发行文件和合成业务证据。"""

from contextlib import ExitStack, nullcontext, redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import r5_template_consumer as consumer
import r5_public_switch_assets as assets
from r3_template_browser import USERS
from r3_template_net9_packages import STAGES as BUILD_STAGES
from r3_web_host import NUGET_SOURCE, artifact, write_json
from verify import ROOT, VerificationError, read_json, sha256


class PublicSwitchTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.args = ["--batch-root", str(self.directory), "--batch-sha256", "0" * 64,
                     "--frozen-root", str(self.directory), "--evidence-root", str(self.directory),
                     "--r4-batch-root", str(self.directory), "--runtime-config", str(self.directory / "runtime.json")]
        self.addCleanup(patch.stopall)
        self.enterContext(redirect_stdout(StringIO()))
        self.stderr = self.enterContext(redirect_stderr(StringIO()))

    def published_inputs(self):
        inputs, lock = {}, {}
        for release, (tag, commit, _) in assets.RELEASES.items():
            paths = [self.directory / f"{release}-{name}.json" for name in ("attachment", "manifest", "downloads")]
            attachment, manifest, downloads = paths
            package_rows, evidence_rows = {}, {}
            for i in range(13):
                name = f"Du.Package{i}"
                package = {"version": tag[1:], "uploadSha256": "1" * 64, "downloadSha256": f"{i:064x}"}
                package_rows[name] = package
                evidence_rows[name] = {"version": package["version"], "mainPackage": {
                    "uploadSha256": package["uploadSha256"], "anonymousDownloadSha256": package["downloadSha256"]}}
            write_json(manifest, {"release": {"tag": tag, "repository": assets.REPOSITORY,
                                              "commit": commit if release == "r4" else None},
                                  "nugetSource": NUGET_SOURCE, "template": {"baseCommit": assets.TEMPLATE}})
            write_json(downloads, {"nugetSource": NUGET_SOURCE, "manifestSha256": sha256(manifest),
                                   "packages": package_rows})
            write_json(attachment, {"repository": assets.REPOSITORY, "tag": tag, "commit": commit,
                                    "template": {"commit": assets.TEMPLATE}, "nugetSource": NUGET_SOURCE,
                                    "releaseManifestSha256": sha256(manifest),
                                    "verifiedDownloadsSha256": sha256(downloads), "packages": evidence_rows})
            inputs[release] = assets.PublishedInputs(*paths, self.directory)
            lock[release] = tag, commit, sha256(attachment)
        self.enterContext(patch.dict(assets.RELEASES, lock))
        return inputs

    def published_args(self, releases):
        return [arg for release, data in releases.items()
                for field, path in zip(("checksums", "release-manifest", "verified-downloads", "baseline"),
                                       (data.attachment, data.manifest, data.downloads, data.baseline), strict=True)
                for arg in (f"--{release}-{field}", str(path))]

    def run_cli(self, action, extra):
        with patch.object(sys, "argv", ["r5_template_consumer.py", action, *self.args, *extra]):
            return consumer.main()

    def runtime(self):
        run = consumer.PublicSwitchRuntime(ROOT, self.directory, self.directory, self.directory,
                                           self.directory / "runtime.json", batch_sha="0" * 64,
                                           r4_batch_root=self.directory, releases={}, source_config_path=None)
        run.stage = run.report["stages"]["r4"]
        run.cleanup = Mock()
        run.frozen_inputs_after = Mock()
        return run

    def test_public_cli_binds_separate_inputs_and_historical_switch_keeps_its_argument_pair(self):
        releases = self.published_inputs()
        with patch.object(consumer, "PublicSwitchRuntime") as public, patch.object(consumer, "PatchNet10Runtime") as old:
            public.return_value.execute_full.return_value = 0
            old.return_value.execute_full.return_value = 0
            self.assertEqual(self.run_cli("switch-public", self.published_args(releases)), 0)
            self.assertEqual(public.call_args.kwargs["releases"], releases)
            self.assertEqual(self.run_cli("switch", ["--release-manifest", str(releases["r4"].manifest),
                                                     "--verified-downloads", str(releases["r4"].downloads)]), 0)
            self.assertEqual(old.call_args.kwargs["public_inputs"], (releases["r4"].manifest, releases["r4"].downloads))
            self.assertIsNone(old.call_args.kwargs["public_release"])
            with self.assertRaises(SystemExit) as failure:
                self.run_cli("switch-public", self.published_args(releases) + ["--tfm", "net9.0"])
            self.assertEqual(failure.exception.code, 2)
            public.assert_called_once()
            old.assert_called_once()

    def test_bound_release_rejects_swapped_attachment_manifest_and_downloads_before_sql(self):
        releases = self.published_inputs()
        r4, r5 = releases.values()
        correct = assets.PublishedInputs(r4.attachment, r4.manifest, r4.downloads, self.directory)
        evidence = self.directory / "copied"
        evidence.mkdir()
        files, proof, rows = correct.qualify("r4", evidence)
        self.assertEqual(proof["tag"], "v10.5.1")
        self.assertEqual(len(rows), 13)
        self.assertEqual([sha256(path) for path in files], [sha256(path) for path in
                         (r4.attachment, r4.manifest, r4.downloads)])
        for field in ("attachment", "manifest", "downloads"):
            with self.subTest(field=field), patch.object(consumer.PublicSwitchRuntime, "sql_preflight") as sql:
                swapped = vars(r4) | {field: getattr(r5, field)}
                args = self.published_args(releases | {"r4": assets.PublishedInputs(**swapped)})
                self.assertEqual(self.run_cli("switch-public", args), 1)
                sql.assert_not_called()
                report = self.latest_report()
                self.assertEqual(report["stages"]["public_inputs"]["status"], "failed")
                self.assertIn("r4 公开发行输入", report["reason"])
                self.assertEqual(report["stages"]["sql_preflight"]["status"], "not_run")

    def test_local_source_and_legacy_arguments_are_rejected_before_sql(self):
        releases = self.published_inputs()
        config = self.directory / "mixed.config"
        config.write_text('<configuration><packageSources><add key="local" value="/tmp/feed" />'
                          '</packageSources></configuration>')
        with patch.object(consumer.PublicSwitchRuntime, "sql_preflight") as sql:
            args = self.published_args(releases)
            self.assertEqual(self.run_cli("switch-public", [*args, "--nuget-config", str(config)]), 1)
            report = self.latest_report()
            self.assertIn("仅接受 nuget.org", report["reason"])
            self.assertEqual(report["stages"]["sql_preflight"]["status"], "not_run")
            sql.assert_not_called()
            with self.assertRaises(SystemExit):
                self.run_cli("switch-public", [*args, "--release-manifest", str(releases["r4"].manifest)])

    def latest_report(self):
        return read_json(max(self.directory.glob("r5-template-switch-public-*/report.json"),
                             key=lambda path: path.stat().st_mtime_ns))

    def fixtures(self):
        run = self.runtime()
        run.db = SimpleNamespace(source="isolated", identity={"serverName": "test-sql"}, commands=[])
        run.report["sql"] = {"databaseIdentity": {"database": "isolated"}}
        run.launch_host = Mock(return_value=nullcontext({"pid": 17}))
        run.verify_loaded = Mock(return_value={"path": "assets.json", "sha256": "mock"})
        run.api = Mock()
        run.user_rows = Mock()
        seed = {"tenant": {"tenantId": 1, "tenancyName": "Default"},
                "account": {"userId": 2, "userName": "admin"}, "migrations": []}
        return run, seed

    def create(self, run, seed, phase, person, id_, *, lookup_fails=False):
        name = f"r5{person.lower()}{run.run_id}"
        run.api.side_effect = [{"userId": 2, "accessToken": "synthetic"}, {"id": id_, "userName": name}]
        fixture = {"id": id_, "userName": name, "tenantId": 1, "creatorUserId": 2, "creationTime": "created",
                   "name": "Runtime", "surname": "Fixture", "emailAddress": f"{name}@example.invalid",
                   "isActive": True}
        run.admin_password = "synthetic"

        def read_created(tenant, keyword):
            receipt = read_json(self.directory / f"{phase}-{person}-creation.json")
            self.assertEqual(receipt, {"phase": phase, "tenantId": tenant, "id": id_, "userName": keyword})
            if lookup_fails:
                raise VerificationError("合成数据库读回失败")
            return [fixture]

        run.user_rows.side_effect = read_created
        run.create_switch_user(phase, seed, person, {})

    def browser(self, run, database, label, *, searches, wrong=None):
        host = {"pid": 18}
        steps = {"session": {"userId": 8 if wrong == "user" else 2, "tenantId": 9 if wrong == "tenant" else 1,
                             "userName": "admin"}, "authorization": {"granted": True}, "searches": {}}
        run.report.setdefault("rounds", {})[label] = {"host": host, "steps": steps}
        events = []
        for person, (baseline, request_id) in searches.items():
            keyword = baseline["keyword"]
            response = {"path": USERS, "method": "GET", "status": 403 if wrong == "http" else 200,
                        "keyword": [keyword], "requestId": request_id, "totalCount": 1,
                        "items": (run.people["A"]["search"]["matches"] if wrong == "A" else baseline["matches"]),
                        "userNameCells": [keyword]}
            steps["searches"][person] = response
            base = {"pid": 18, "requestId": request_id, "activityId": f"activity-{person}"}
            events.extend((base | {"kind": "request", "method": "GET", "path": USERS, "keyword": keyword},
                           base | {"kind": "response", "status": response["status"]}))
            for operation in ("count", "list"):
                context = {"step": operation, "commandId": operation}
                events.extend((base | context | {"kind": "connection", "serverName": "test-sql", "sessionId": 1,
                                                 "database": "other" if wrong == "database" else database,
                                                 "connectionId": "connection", "clientConnectionId": "client",
                                                 "context": "db"},
                               base | context | {"kind": "completed"}))
        run.request_log.write_text("".join(json.dumps(event) + "\n" for event in events))
        if wrong == "http":
            raise VerificationError("授权查询 HTTP 403")

    def test_r5_failure_keeps_b_creation_receipt_readback_and_marks_rollback_unexecuted(self):
        run, seed = self.fixtures()
        rollback = Mock()

        def r4():
            self.create(run, seed, "r4", "A", 3)

        def r5():
            self.create(run, seed, "r5", "B", 4)
            run.read_switch_users("r5", "r5-B", ("B",), {})

        with patch.object(consumer.RuntimeSupport, "round", lambda *a, **k: self.browser(*a, **k, wrong="http")):
            self.assertEqual(run.execute_steps((("r4", r4), ("r5", r5), ("rollback", rollback))), 1)
        rollback.assert_not_called()
        report = read_json(run.report_path)
        proof = report["sql"]["creations"]["B"]
        self.assertEqual(read_json(self.directory / proof["receiptFile"]["path"]),
                         {"phase": "r5", "tenantId": 1, "id": 4, "userName": proof["keyword"]})
        self.assertEqual(proof["databaseRead"]["rows"][0]["id"], 4)
        self.assertEqual(report["businessReads"]["r5"]["B"]["status"], "failed")
        self.assertEqual(report["businessReads"]["r5"]["B"]["response"]["status"], 403)
        self.assertEqual(report["stages"]["rollback"]["status"], "not_run")
        self.assertTrue(all(result["status"] == "not_run" for result in report["businessReads"]["rollback"].values()))

    def test_db_read_failure_after_create_keeps_receipt_and_marks_database_read_missing(self):
        run, seed = self.fixtures()
        with self.assertRaisesRegex(VerificationError, "数据库读回失败"):
            self.create(run, seed, "r5", "B", 4, lookup_fails=True)
        proof = read_json(run.report_path)["sql"]["creations"]["B"]
        self.assertEqual(proof["receipt"]["id"], 4)
        self.assertEqual(proof["databaseRead"]["status"], "missing")

    def test_rollback_one_round_produces_distinct_user_evidence_and_rejects_wrong_user_tenant_or_database(self):
        for wrong in (None, "A", "user", "tenant", "database"):
            with self.subTest(wrong=wrong):
                run, seed = self.fixtures()
                self.create(run, seed, "r4", "A", 3)
                self.create(run, seed, "r5", "B", 4)
                verify = lambda *a, **k: self.browser(*a, **k, wrong=wrong)
                with patch.object(consumer.RuntimeSupport, "round", autospec=True, side_effect=verify) as browser:
                    if wrong:
                        with self.assertRaises(VerificationError):
                            run.read_switch_users("rollback", "rollback-AB", ("A", "B"), {})
                    else:
                        run.read_switch_users("rollback", "rollback-AB", ("A", "B"), {})
                    browser.assert_called_once()
                a, b = run.report["businessReads"]["rollback"].values()
                self.assertNotEqual(a["requestId"], b["requestId"])
                self.assertNotEqual(a["evidence"]["path"], b["evidence"]["path"])
                self.assertEqual(a["pid"], b["pid"])
                self.assertEqual(b["status"], "failed" if wrong else "passed")
                self.assertEqual(b["expected"][0]["id"], 4)
                if wrong == "A":
                    self.assertEqual(b["response"]["items"][0]["id"], 3)

    def test_public_entry_restores_r4_r5_rollback_before_sql_while_root_report_is_running(self):
        releases = self.published_inputs()
        restore_order = []
        at_sql = Mock()
        signed_r5 = {"signed": "r5"}

        def qualify(run):
            run.release_downloads = {"r4": {"signed": "r4"}, "r5": {"signed": "r5"}}

        def r4_build(build):
            phase = "rollback" if build.evidence.name == "rollback-build" else "r4"
            self.assertEqual(restore_order, ["r4", "r5"] if phase == "rollback" else [])
            build.downloads = {"signed": "r4"}
            restore_order.append(phase)
            return 0

        def r5_packages(run):
            run.downloads = signed_r5.copy()

        def r5_restore(run):
            restore_order.append("r5")

        def compare(run):
            report = read_json(run.report_path)
            self.assertEqual((report["status"], report["exitCode"]), ("running", None))
            self.assertEqual(restore_order, ["r4", "r5", "rollback"])
            self.assertEqual([report["stages"][name]["status"] for name in BUILD_STAGES], ["passed"] * len(BUILD_STAGES))
            self.assertEqual(report["stages"]["sql_preflight"]["status"], "not_run")

        with ExitStack() as mocks:
            for method in ("preflight", "materialize", "toolchain", "inventory", "build", "inspect_output",
                           "inputs_after", "inputs", "build_observer", "angular", "frozen_inputs_after", "run_phase"):
                mocks.enter_context(patch.object(consumer.PublicSwitchRuntime, method, return_value=None))
            mocks.enter_context(patch.object(consumer.PublicSwitchRuntime, "qualify_releases", qualify))
            mocks.enter_context(patch.object(consumer.PatchPackages, "packages", r5_packages))
            mocks.enter_context(patch.object(consumer.PublicSwitchRuntime, "restore", r5_restore))
            mocks.enter_context(patch.object(consumer.Net10Build, "execute_build", r4_build))
            mocks.enter_context(patch.object(consumer.PublicSwitchRuntime, "public_graphs", compare))
            mocks.enter_context(patch.object(consumer.PublicSwitchRuntime, "sql_preflight", at_sql))
            self.assertEqual(self.run_cli("switch-public", self.published_args(releases)), 0)
            at_sql.assert_called_once()
            self.assertEqual(self.latest_report()["status"], "passed")
            at_sql.reset_mock()
            restore_order.clear()
            signed_r5["signed"] = "different"
            self.assertEqual(self.run_cli("switch-public", self.published_args(releases)), 1)
            failed = self.latest_report()
            self.assertIn("R5 签后登记不符", failed["reason"])
            self.assertEqual(restore_order, ["r4"])
            self.assertEqual(failed["stages"]["build_rollback"]["status"], "not_run")
            at_sql.assert_not_called()

    def test_graph_gate_accepts_a_running_parent_only_with_all_r5_build_steps_passed(self):
        labels = ("r4", "r5", "rollback", "baseline-r4", "baseline-r5")
        builds = {label: self.directory / label for label in labels}
        releases = {release: {"verifiedDownloadsSha256": release, "releaseManifestSha256": f"{release}-manifest"}
                    for release in ("r4", "r5")}
        child_refs, history = {}, {}
        for label, directory in builds.items():
            directory.mkdir()
            release = "r5" if label.endswith("r5") else "r4"
            inputs = {"targetFramework": "net10.0", "nuget": {"effectiveSources": [NUGET_SOURCE]},
                      "publicDownloads": {"verified-downloads.json": {"sha256": release},
                                          "release-manifest.json": {"sha256": f"{release}-manifest"}}}
            report = {"status": "passed" if label.startswith("baseline-") else "build_verified",
                      "exitCode": 0, "inputs": inputs}
            write_json(directory / "assets-inventory.json", {entry: {} for entry in assets.COUNTS})
            output = {entry: {"outputVerification": {"path": f"{entry}-output.json", "sha256": "synthetic"}}
                      for entry in assets.COUNTS}
            write_json(directory / "launch-manifest.json", output)
            write_json(directory / "report.json", report)
            if label.startswith("baseline-"):
                history[release] = sha256(directory / "report.json"), sha256(directory / "assets-inventory.json")
            elif label == "r5":
                parent = report
            else:
                child_refs[label] = artifact(directory / "report.json", self.directory) | {"exitCode": 0}
        parent.update(status="running", exitCode=None,
                      stages={name: {"status": "passed", "exitCode": 0} for name in BUILD_STAGES})
        parent["inputs"]["publicBuilds"] = child_refs

        def compare(report):
            write_json(builds["r5"] / "report.json", report)
            return assets.compare_public_builds(builds, releases, self.directory)

        with patch.dict(assets.HISTORICAL, history), patch.object(
                assets, "entry_graph", return_value=({"nodes": {}, "edges": {}, "assets": {}}, {})) as graph, \
                patch.object(assets, "verify_patch"):
            outputs = compare(parent)
            for label in ("r4", "r5", "rollback"):
                self.assertEqual(outputs[label]["Web.Host"],
                                 {"path": f"{label}/Web.Host-output.json", "sha256": "synthetic"})
            self.assertEqual(graph.call_count, 2 * len(labels))
            self.assertEqual(read_json(builds["r5"] / "report.json"), parent)
            for invalid in (None, {"status": "failed", "exitCode": 1}, {"status": "passed", "exitCode": 1}):
                with self.subTest(invalid=invalid):
                    report = deepcopy(parent)
                    if invalid is None:
                        report["stages"].pop("output")
                    else:
                        report["stages"]["output"] = invalid
                    with self.assertRaisesRegex(VerificationError, "r5.*output"):
                        compare(report)
            child = builds["r4"] / "report.json"
            report = deepcopy(parent)
            child_contents = read_json(child)
            write_json(child, child_contents | {"status": "running", "exitCode": None})
            with self.assertRaisesRegex(VerificationError, "r4.*报告.*不符"):
                compare(report)
            report["inputs"]["publicBuilds"]["r4"] = artifact(child, self.directory) | {"exitCode": 0}
            with self.assertRaisesRegex(VerificationError, "r4 公开构建未通过"):
                compare(report)
            write_json(child, child_contents)
            historical = builds["baseline-r5"] / "report.json"
            write_json(historical, read_json(historical) | {"status": "failed", "exitCode": 1})
            with patch.dict(assets.HISTORICAL, {"r5": (sha256(historical), history["r5"][1])}), \
                    self.assertRaisesRegex(VerificationError, "baseline-r5 未通过"):
                compare(parent)
            self.assertEqual(graph.call_count, 2 * len(labels))

    def test_runtime_rejects_output_manifest_that_changed_after_graph_comparison(self):
        run = self.runtime()
        original = {"r5": {"Web.Host": {"path": "Web.Host-output.json", "sha256": "known"}}}
        run.public_entry_outputs = original
        run.report["inputs"]["entryOutputs"] = deepcopy(original)
        with patch.object(consumer.PatchNet10Runtime, "inputs"):
            run.inputs()
            run.report["inputs"]["entryOutputs"]["r5"]["Web.Host"]["sha256"] = "different"
            with self.assertRaisesRegex(VerificationError, "入口清单与已对账的公开构建不符"):
                run.inputs()

    def test_full_graph_normalizes_cache_roots_and_binds_historical_archive_sha256(self):
        def assemble(directory):
            archive = directory / "packages/du.example/1.0.0/du.example.1.0.0.nupkg"
            archive.parent.mkdir(parents=True)
            with ZipFile(archive, "w") as package:
                package.writestr("lib/net10.0/example.dll", b"fixture")
            key = "Du.Example/1.0.0"
            raw = {
                "targets": {"net10.0": {key: {"type": "package", "compile": {"lib/net10.0/example.dll": {}}}}},
                "libraries": {key: {"sha512": "synthetic"}},
                "packageFolders": {str(directory / "packages"): {}},
                "project": {"restore": {"sources": {NUGET_SOURCE: {}}, "projectName": "Web.Host",
                                       "frameworks": {"net10.0": {"projectReferences": {}}}},
                            "frameworks": {"net10.0": {"dependencies": {"Du.Example": {"version": "[1.0.0]"}}}}},
            }
            write_json(directory / "raw.json", raw)
            write_json(directory / "output.json", {"packageCopies": {}})
            report = {"rawAssets": {"Web.Host": artifact(directory / "raw.json", directory)},
                      "inputs": {"entryOutputs": {"net10": {"Web.Host": artifact(directory / "output.json", directory)}},
                                 "nuget": {"effectiveSources": [NUGET_SOURCE], "cachesInitiallyEmpty": True}}}
            inventory = {"packages": {key: {"source": NUGET_SOURCE, "contentSha512": "synthetic",
                                           "archive": artifact(archive, directory / "packages")}},
                         "compileReferences": {}, "selectedPackageAnalyzers": []}
            return report, inventory, archive

        before = self.directory / "original"
        after = self.directory / "current"
        old_report, old_inventory, old_archive = assemble(before)
        new_report, new_inventory, new_archive = assemble(after)
        new_archive.write_bytes(old_archive.read_bytes())
        new_inventory["packages"]["Du.Example/1.0.0"]["archive"]["sha256"] = sha256(new_archive)
        old_archive.unlink()
        with patch.dict(assets.COUNTS, {"Web.Host": (1, 1, 1)}):
            old, paths = assets.entry_graph(before, old_report, old_inventory, "Web.Host", historical=True,
                                            archive_directory=after)
            new, current = assets.entry_graph(after, new_report, new_inventory, "Web.Host", historical=False)
            self.assertNotEqual(paths["restoreCacheRoots"], current["restoreCacheRoots"])
            self.assertEqual(paths["checkedArchives"], current["checkedArchives"])
            self.assertEqual(assets.compare_graphs(old, new), {"nodes": {}, "edges": {}, "assets": {}})
            new_archive.write_bytes(b"swapped")
            with self.assertRaisesRegex(VerificationError, "SHA-256"):
                assets.entry_graph(before, old_report, old_inventory, "Web.Host", historical=True,
                                   archive_directory=after)

    def test_extra_edge_or_unrelated_asset_drift_rejects_public_patch(self):
        old = {"nodes": {name: {"version": version} for name, version in assets.R4_VERSIONS.items()},
               "edges": {edge: assets.normalized_range(f"[{assets.R4_VERSIONS[edge[1]]}]")
                         for edge in assets.PATCH_EDGES},
               "assets": ({(name, role, f"{name}.dll"): "r4" for name in assets.VERSIONS
                           for role in ("compiled", "output")} | {("Other", "compiled", "other.dll"): "same"})}
        new = deepcopy(old)
        new["assets"] = {key: "r5" if key[0] in assets.VERSIONS else value for key, value in old["assets"].items()}
        new["nodes"] = {name: {"version": version} for name, version in assets.VERSIONS.items()}
        new["edges"] = {edge: assets.normalized_range(f"[{assets.VERSIONS[edge[1]]}]") for edge in assets.PATCH_EDGES}
        assets.verify_patch(old, new, assets.compare_graphs(old, new))
        drift = deepcopy(new)
        drift["edges"][("Other", "Unknown")] = "1.0"
        with self.assertRaisesRegex(VerificationError, "四条"):
            assets.verify_patch(old, drift, assets.compare_graphs(old, drift))
        new["assets"][("Other", "compiled", "other.dll")] = "different"
        with self.assertRaisesRegex(VerificationError, "未登记变化"):
            assets.verify_patch(old, new, assets.compare_graphs(old, new))


if __name__ == "__main__":
    unittest.main()
