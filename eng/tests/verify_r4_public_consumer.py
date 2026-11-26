#!/usr/bin/env python3
"""从本地通过轮派生公开消费的隔离资产样本。"""

import argparse
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_web_host import NUGET_SOURCE, artifact, project_path, write_json
from r4_candidate_batch import load_frozen_batch
from r4_public_release import MANIFEST_SHA256, SIGNATURE, compare_packages
from r4_template_assets import public_downloads, verify_build_entry, verify_process
from r4_template_consumer import PLAN, PUBLIC_PLAN, Net10Build, planning_artifacts, planning_inputs
from verify import ROOT, VerificationError, read_json, sha256


R5_EXECUTION = "26737218c6157a348c10ad6492865a4e009ac8d4"


class PublicConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.batch = load_frozen_batch(cls.batch_root)
        cls.inspection = read_json(cls.batch_root / cls.batch["inspection"]["path"])
        cls.entries = read_json(cls.upgrade_run / "assets-inventory.json")
        cls.release = read_json(cls.upgrade_run / "report.json")

    def setUp(self):
        self.run = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.entry = "Migrator"
        self.graph = deepcopy(self.entries[self.entry])
        self.inputs = deepcopy(self.release["inputs"])
        self.inputs.update(packageSourceMode="public")
        self.inputs["nuget"]["effectiveSources"] = [NUGET_SOURCE]
        self.output = self.run / "source/aspnet-core" / project_path(self.entry).parent / "bin/Release/net10.0"
        self.output.mkdir(parents=True)
        self.launch = deepcopy(self.release["sql"]["migrations"]["net10"]["launch"])
        original = Path(self.launch["cwd"])
        self.launch.update(cwd=str(self.output))
        self.launch["argv"][1] = str(self.output / Path(self.launch["argv"][1]).name)
        self.observed = read_json(self.upgrade_run / "net10-migrator-loaded.json")
        for row in self.observed["assemblies"]:
            path = Path(row["path"])
            if path.is_relative_to(original):
                row["path"] = str(self.output / path.relative_to(original))
        path = self.run / f"{self.entry}-output.json"
        output_manifest = read_json(self.upgrade_run / path.name)
        shutil.copyfile(original / output_manifest["entry"]["path"], Path(self.launch["argv"][1]))
        self.downloads = {}
        for key, item in self.graph["packages"].items():
            name = item["id"]
            if name not in self.batch["packages"]:
                continue
            record = self.batch["packages"][name]["archive"]
            frozen = self.batch_root / record["path"]
            cached = self.run / "packages" / item["archive"]["path"]
            cached.parent.mkdir(parents=True)
            shutil.copyfile(frozen, cached)
            # 仅构造签名封装差异。真实仓库签名及缓存兼容由独立公开样本验证。
            with ZipFile(cached, "a") as archive:
                archive.writestr(SIGNATURE, b"isolated-consumer-fixture")
            digest = sha256(cached)
            self.assertNotEqual(digest, record["sha256"])
            self.assertTrue(compare_packages(frozen, cached))
            item["source"] = NUGET_SOURCE
            write_json(cached.parent / ".nupkg.metadata", {"source": NUGET_SOURCE})
            item["archive"]["sha256"] = digest
            self.downloads[name] = {"version": item["version"], "uploadSha256": record["sha256"],
                                    "downloadSha256": digest}

            asset, = item["assets"]["compile"]
            filename = Path(asset).name
            dll = cached.parent / asset
            dll.parent.mkdir(parents=True)
            shutil.copyfile(original / filename, dll)
            shutil.copyfile(dll, self.output / filename)
            self.graph["compileReferences"][filename][0]["path"] = str(dll)
            output_manifest["packageCopies"][filename]["cachePath"] = str(dll)
        write_json(path, output_manifest)
        self.launch["outputVerification"] = artifact(path, self.run)

    def verify(self):
        return verify_build_entry(self.run, self.inputs, self.entry, self.batch_root, self.batch,
                                  self.inspection, self.graph, self.launch, downloads=self.downloads)

    def test_signature_container_changes_archive_but_not_build_or_process_dll(self):
        build = self.verify()
        observed = verify_process(build, self.launch, self.observed)
        self.assertEqual(build["packageCount"], 10)
        self.assertEqual(observed["packageSourceMode"], "public")
        for name, origin in observed["packages"].items():
            self.assertEqual(origin["restoredArchive"]["sha256"], self.downloads[name]["downloadSha256"])
            self.assertNotEqual(origin["restoredArchive"]["sha256"], origin["archive"]["sha256"])
            self.assertEqual(origin["restoredArchive"]["source"], NUGET_SOURCE)
            if origin["state"] == "loaded":
                self.assertEqual(origin["processAssembly"]["sha256"], origin["assetSha256"])
        self.assertEqual({name for name, row in observed["packages"].items() if row["state"] == "output_only"},
                         {"Du.Abp.AutoMapper", "Du.AutoMapper", "Du.AutoMapper.Collection"})

    def test_rejects_replaced_cached_archive_even_with_same_id_and_version(self):
        record = self.graph["packages"]["Du.Abp/10.5.1"]["archive"]
        shutil.copyfile(self.batch_root / self.batch["packages"]["Du.Abp"]["archive"]["path"],
                        self.run / "packages" / record["path"])
        with self.assertRaisesRegex(VerificationError, "Du.Abp/10.5.1 缓存归档 SHA-256 不符"):
            self.verify()

    def test_rejects_wrong_compile_output_and_loaded_dll_hashes(self):
        record = self.graph["compileReferences"]["Abp.dll"][0]
        original, record["sha256"] = record["sha256"], "0" * 64
        with self.assertRaisesRegex(VerificationError, "Du.Abp/10.5.1 编译或输出 DLL 摘要不符"):
            self.verify()
        record["sha256"] = original
        build = self.verify()
        loaded, = (item for item in self.observed["assemblies"] if item["name"] == "Abp")
        loaded["sha256"] = "0" * 64
        with self.assertRaisesRegex(VerificationError, "Du.Abp 实际加载 DLL 摘要不符"):
            verify_process(build, self.launch, self.observed)
        (self.output / "Abp.dll").write_bytes(b"wrong DLL")
        with self.assertRaisesRegex(VerificationError, "Du.Abp/10.5.1 编译或输出 DLL 摘要不符"):
            self.verify()

    def test_rejects_mixed_sources_and_old_cache(self):
        nuget = self.inputs["nuget"]
        nuget["effectiveSources"].append(str(self.run / "other-feed"))
        with self.assertRaisesRegex(VerificationError, "空缓存或维护包源不符"):
            self.verify()
        nuget["effectiveSources"].pop()
        nuget["cachesInitiallyEmpty"] = False
        with self.assertRaisesRegex(VerificationError, "空缓存或维护包源不符"):
            self.verify()
        nuget["cachesInitiallyEmpty"] = True
        metadata = self.run / "packages/du.abp/10.5.1/.nupkg.metadata"
        write_json(metadata, {"source": str(self.run / "other-feed")})
        with self.assertRaisesRegex(VerificationError, "Du.Abp/10.5.1 还原来源或版本不符"):
            self.verify()

    def test_public_materialization_rejects_preexisting_cache(self):
        directory = self.run / "stale"
        directory.mkdir()
        app = Net10Build(ROOT, directory, ROOT / ".git", self.batch_root,
                         public_inputs=(self.manifest, self.manifest))
        # 模板 materialize 必须在创建本轮缓存时拒绝已存在的目录。
        app.cache.mkdir()
        (app.cache / "old-package").touch()
        with self.assertRaisesRegex(VerificationError, "materialize:") as failed:
            app.step("materialize", app.materialize)
        self.assertIsInstance(failed.exception.__cause__, FileExistsError)
        self.assertEqual(Path(failed.exception.__cause__.filename), app.cache)

    def test_release_table_must_match_manifest_batch_and_complete_downloads(self):
        path = self.run / "verified-downloads.json"
        rows = {name: {"version": record["version"], "uploadSha256": record["archive"]["sha256"],
                       "downloadSha256": "1" * 64} for name, record in self.batch["packages"].items()}
        table = {"schemaVersion": 1, "manifestSha256": MANIFEST_SHA256, "nugetSource": NUGET_SOURCE,
                 "packages": rows}

        def check():
            write_json(path, table)
            return public_downloads(self.manifest, path, self.batch_root, self.batch)

        self.assertEqual(check(), rows)
        record = rows.pop("Du.Abp")
        with self.assertRaisesRegex(VerificationError, "缺少 .*Du.Abp"):
            check()
        rows["Du.Abp"] = record
        record["downloadSha256"] = record["uploadSha256"]
        with self.assertRaisesRegex(VerificationError, "Du.Abp/10.5.1 缺少仓库签名后的公开下载摘要"):
            check()
        table["manifestSha256"] = "0" * 64
        with self.assertRaisesRegex(VerificationError, "首发清单摘要不符"):
            check()

    def test_frozen_build_and_historical_process_keep_local_binding(self):
        report = verify_build_entry(self.upgrade_run, self.release["inputs"], self.entry, self.batch_root,
                                    self.batch, self.inspection, self.entries[self.entry],
                                    read_json(self.upgrade_run / "launch-manifest.json")[self.entry])
        run = self.release["sql"]["migrations"]["net10"]["launch"]
        result = verify_process(report, run, read_json(self.upgrade_run / "net10-migrator-loaded.json"))
        self.assertEqual(result["packageSourceMode"], "frozen")
        self.assertEqual(result["packageCount"], 10)
        self.assertEqual(result["packages"]["Du.Abp"]["restoredArchive"]["sha256"],
                         self.batch["packages"]["Du.Abp"]["archive"]["sha256"])

    def test_reports_mode_specific_planning_and_keeps_frozen_qualification(self):
        coordinator = self.batch["gitlinkCommit"]
        git = Net10Build.git

        def git_at_coordinator(app, repo, log, *args):
            if args in (("rev-parse", "HEAD"), ("rev-parse", "HEAD^{tree}")):
                args = ("rev-parse", args[1].replace("HEAD", coordinator, 1))
            return git(app, repo, log, *args)

        reports = {}
        for mode, public_inputs in (("frozen", None), ("public", (self.manifest, self.manifest))):
            directory = self.run / mode
            directory.mkdir()
            app = Net10Build(ROOT, directory, ROOT / ".git", self.batch_root, public_inputs=public_inputs)
            with patch.object(Net10Build, "git", git_at_coordinator) if mode == "frozen" else nullcontext():
                app.step("preflight", app.preflight)
            reports[mode] = read_json(app.report_path)["inputs"]

        frozen, public = reports["frozen"], reports["public"]
        candidate = frozen["planning"]
        self.assertEqual(candidate["change"], "prepare-r4-first-release-candidate")
        self.assertEqual(candidate["baseCommit"], frozen["planningCommit"])
        self.assertEqual(candidate["baseTree"], frozen["planningTree"])
        self.assertNotIn("frozenCandidatePlanning", frozen)
        self.assertEqual(public["frozenCandidatePlanning"], candidate | {
            "execution": public["planning"]["execution"], "purpose": "frozen_batch_qualification",
        })

        plan = public["planning"]
        self.assertEqual(plan["change"], "publish-r4-first-public-release")
        self.assertEqual(plan["artifactSource"], "working_tree")
        self.assertEqual(plan["execution"], {"commit": public["executionCommit"], "tree": public["executionTree"]})
        self.assertNotIn("baseCommit", plan)
        self.assertNotIn("baseTree", plan)
        self.assertNotIn("planningCommit", public)
        self.assertNotIn("planningTree", public)
        change_path = Path(plan["changePath"])
        self.assertEqual(change_path.parent, Path("openspec/changes") if plan["changeState"] == "active"
                         else Path("openspec/changes/archive"))
        required = {change_path / name for name in
                    ("design.md", "proposal.md", "specs/public-package-release/spec.md", "tasks.md")}
        paths = {Path(record["path"]) for record in plan["artifacts"]}
        self.assertLessEqual(required, paths)
        for record in plan["artifacts"]:
            path = Path(record["path"])
            self.assertTrue(path.is_relative_to(change_path))
            self.assertEqual(record, artifact(ROOT / path, ROOT))

    def test_archived_public_replay_accepts_r5_and_frozen_preflight_rejects_producer_drift(self):
        tree = subprocess.check_output(["git", "-C", ROOT, "rev-parse", f"{R5_EXECUTION}^{{tree}}"], text=True).strip()
        public_plan = planning_artifacts(ROOT, PUBLIC_PLAN, "public-package-release")
        self.assertEqual(public_plan["changeState"], "archived")
        result = planning_inputs(ROOT, R5_EXECUTION, tree, public_plan=public_plan)
        self.assertEqual(result["execution"], {"commit": R5_EXECUTION, "tree": tree})
        self.assertEqual(result["coordinator"]["commit"], self.batch["gitlinkCommit"])
        with self.assertRaisesRegex(VerificationError, rf"{R5_EXECUTION} 的 R4 gitlink AutoMapper 不符"):
            planning_inputs(ROOT, R5_EXECUTION, tree)

    def test_active_r4_candidate_or_public_release_rejects_r5_producer_drift(self):
        tree = subprocess.check_output(["git", "-C", ROOT, "rev-parse", f"{R5_EXECUTION}^{{tree}}"], text=True).strip()
        archived_public = planning_artifacts(ROOT, PUBLIC_PLAN, "public-package-release")
        for change in (PLAN, PUBLIC_PLAN):
            def active_candidate(repo, path, specification):
                plan = planning_artifacts(repo, path, specification)
                return plan | {"changeState": "active"} if path == change else plan

            public = archived_public | {"changeState": "active"} if change == PUBLIC_PLAN else archived_public
            with self.subTest(change=change.name), patch(
                "r4_template_consumer.planning_artifacts", side_effect=active_candidate
            ), self.assertRaisesRegex(VerificationError, rf"{R5_EXECUTION} 的 R4 gitlink AutoMapper 不符"):
                planning_inputs(ROOT, R5_EXECUTION, tree, public_plan=public)

    def test_archived_public_replay_rejects_wrong_template_and_coordinator_producer(self):
        git = subprocess.check_output
        tree = git(["git", "-C", ROOT, "rev-parse", f"{R5_EXECUTION}^{{tree}}"], text=True).strip()
        public_plan = planning_artifacts(ROOT, PUBLIC_PLAN, "public-package-release")
        for revision, module in ((R5_EXECUTION, "module-zero-core-template"), (self.batch["gitlinkCommit"], "AutoMapper")):
            def wrong_gitlink(command, **kwargs):
                if command[3:] == ["ls-tree", revision, "--", module]:
                    return f"160000 commit {'0' * 40}\t{module}\n"
                return git(command, **kwargs)

            with self.subTest(revision=revision, module=module), patch(
                "r4_template_consumer.subprocess.check_output", side_effect=wrong_gitlink
            ), self.assertRaisesRegex(VerificationError, rf"{revision} 的 R4 gitlink {module} 不符"):
                planning_inputs(ROOT, R5_EXECUTION, tree, public_plan=public_plan)

    def test_archived_public_replay_rejects_wrong_release_manifest(self):
        release = self.run / "wrong-release-manifest.json"
        write_json(release, read_json(self.manifest) | {"template": {}})
        app = Net10Build(ROOT, self.run, ROOT / ".git", self.batch_root, public_inputs=(release, release))
        app.step("preflight", app.preflight)
        with self.assertRaisesRegex(VerificationError, "公开消费的首发清单 SHA-256 不符"):
            app.step("packages", app.packages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("batch-root", "upgrade-run", "manifest"):
        parser.add_argument(f"--{name}", required=True, type=lambda value: Path(value).resolve())
    args, unittest_args = parser.parse_known_args()
    for name in ("batch_root", "upgrade_run", "manifest"):
        setattr(PublicConsumerTests, name, getattr(args, name))
    unittest.main(argv=[sys.argv[0], *unittest_args])
