"""原版回退冻结文件和登录行比较的定向回归。"""

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_template_browser import USERS
from r3_template_original_rollback import (PLAN, RollbackRun, verify_checkpoint_logins, verify_path_login_start,
                                           verify_query_target, verify_release_files)
from r3_template_runtime import inventory
from verify import VerificationError, read_json, sha256


class OriginalRollbackInputTests(unittest.TestCase):
    def test_same_name_release_dll_with_different_digest_is_rejected(self):
        with TemporaryDirectory() as directory:
            output = Path(directory).resolve()
            dll = output / "Abp.dll"
            dll.write_bytes(b"original assembly")
            expected = inventory(output)
            dll.write_bytes(b"maintenance assembly")
            with self.assertRaisesRegex(VerificationError, r"Release 来源不符：Abp\.dll"):
                verify_release_files(output, expected, "Web.Host")

    def test_only_known_migrator_runtime_log_is_ignored(self):
        with TemporaryDirectory() as directory:
            output = Path(directory).resolve()
            (output / "Abp.dll").write_bytes(b"original assembly")
            expected = inventory(output)
            logs = output / "Logs"
            logs.mkdir()
            (logs / "Logs.txt").write_text("Migrator log\n", encoding="utf-8")
            verify_release_files(output, expected, "Migrator")
            (logs / "Abp.dll").write_bytes(b"unexpected assembly")
            with self.assertRaisesRegex(VerificationError, r"Release 来源不符：Logs/Abp\.dll"):
                verify_release_files(output, expected, "Migrator")

    def test_login_checkpoint_requires_every_field_and_seventh_fractional_digit(self):
        row = {"id": 3, "creationTime": "2026-01-01T12:00:00.1234567", "result": 1, "tenantId": 1,
               "userId": 2, "tenancyName": "Default", "loginName": "admin"}
        verify_checkpoint_logins("after_upgrade", [row], [dict(row)])
        changes = {"id": 4, "creationTime": "2026-01-01T12:00:00.1234568", "result": 2,
                   "tenantId": 2, "userId": 3, "tenancyName": "Other", "loginName": "other"}
        for field, value in changes.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(VerificationError, "after_upgrade 的成功登录行"):
                    verify_checkpoint_logins("after_upgrade", [row], [row | {field: value}])
        with self.assertRaisesRegex(VerificationError, "before_upgrade 的成功登录行"):
            verify_checkpoint_logins("before_upgrade", [], [row])


class OriginalRollbackBusinessTests(unittest.TestCase):
    def setUp(self):
        self.original = {"id": 3, "creationTime": "2026-11-25T21:55:58.3636350", "result": 1,
                         "tenantId": 1, "userId": 2, "tenancyName": "Default", "loginName": "admin"}
        self.retained = [self.original | {"id": 1}, self.original | {"id": 2}]
        self.new = self.original | {"creationTime": "2026-11-25T22:55:58.3636350"}
        self.approved = {"before": self.retained, "after": self.retained + [self.original]}

    def readback(self, read):
        db = Mock()
        db.successful_logins.side_effect = read
        run = SimpleNamespace(db=db, databases={"before_upgrade": "before", "after_upgrade": "after"},
                              role="before_upgrade", business={}, redact=lambda message: message)
        record = {"authenticationMayHaveStarted": True, "beforeLoginRows": self.approved, "subsequentErrors": []}
        RollbackRun.capture_login_end(run, record, "before", "after", self.original)
        return record

    def test_pre_authentication_snapshot_rejects_original_upgrade_row(self):
        verify_path_login_start(self.approved, self.approved, "before", self.original)
        affected = self.approved | {"before": self.retained + [self.original]}
        with self.assertRaisesRegex(VerificationError, "认证前含升级轮原行 3"):
            verify_path_login_start(self.approved, affected, "before", self.original)

    def test_readback_accepts_reused_id_with_different_creation_time(self):
        result = self.readback([self.retained + [self.new], self.retained + [self.original]])
        self.assertEqual(result["addedLogin"], self.new)
        self.assertEqual(result["subsequentErrors"], [])
        self.assertEqual(result["loginDifferences"]["after"], {"status": "known", "added": [], "removed": []})

    def test_readback_does_not_claim_unchanged_control_if_query_fails(self):
        result = self.readback([self.retained + [self.new], OSError("readback failed")])
        self.assertIsNone(result["afterLoginRows"]["after"])
        self.assertEqual(result["loginDifferences"], {
            "before": {"status": "known", "added": [self.new], "removed": []},
            "after": {"status": "unknown"},
        })
        self.assertEqual(result["subsequentErrors"], [
            {"phase": "login_readback", "database": "after", "reason": "readback failed"}])
        self.assertNotIn("addedLogin", result)

    def test_query_evidence_requires_successful_execution_of_the_same_command(self):
        keyword = "fixture"
        keys = {"pid": 102, "requestId": "correlation", "activityId": "activity"}
        search = {"requestId": "correlation", "path": USERS, "keyword": [keyword], "method": "GET", "status": 200}
        events = [keys | {"kind": "request", "keyword": keyword, "method": "GET", "path": USERS}]
        for step in ("count", "list"):
            events.extend([
                keys | {"kind": "connection", "step": step, "serverName": "server", "database": "db",
                        "commandId": step, "connectionId": "connection", "clientConnectionId": "client",
                        "sessionId": 93, "context": "context"},
                keys | {"kind": "completed", "step": step, "commandId": step},
            ])
        events.append(keys | {"kind": "response", "status": 200})
        verify_query_target(events, 102, "server", "db", search, "correlation", keyword)
        events[-2]["commandId"] = "unrelated-command"
        with self.assertRaisesRegex(VerificationError, "list 缺少同命令成功证据"):
            verify_query_target(events, 102, "server", "db", search, "correlation", keyword)


class OriginalRollbackReportTests(unittest.TestCase):
    def test_report_tracks_worktree_planning_and_runtime_scope_separately(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            repo = Path(directory).resolve()
            evidence = repo / "evidence"
            evidence.mkdir()
            proposal = repo / PLAN / "proposal.md"
            proposal.parent.mkdir(parents=True)
            proposal.write_text("# 回退提案\n")
            digest = sha256(proposal)
            execution = ("a" * 40, "b" * 40)
            status = f"?? {proposal.relative_to(repo).as_posix()}"
            run = RollbackRun(repo, evidence, repo, repo / "upgrade", repo / "config.json")
            with patch.object(run, "git", side_effect=[*execution, status]):
                run.execution_inputs()
            run.save()
            report = read_json(run.report_path)

        inputs = report["inputs"]
        self.assertNotIn("planningCommit", inputs)
        self.assertNotIn("planningTree", inputs)
        self.assertEqual((inputs["executionCommit"], inputs["executionTree"]), execution)
        planning = inputs["planning"]
        self.assertEqual(planning["baseCommit"], "d731068b6c7d51ae3e4035d4b4620ec00d6e03ea")
        self.assertEqual(planning["baseTree"], "e1f982eaa5a7be89b5bb14959f85cfb8298cc022")
        self.assertEqual(planning["changePath"], PLAN.as_posix())
        self.assertEqual(planning["changeState"], "active")
        self.assertEqual(planning["artifactSource"], "working_tree")
        self.assertEqual(planning["gitStatus"], [status])
        self.assertEqual(planning["artifacts"][0]["path"], proposal.relative_to(repo).as_posix())
        self.assertEqual(planning["artifacts"][0]["sha256"], digest)
        self.assertEqual({path["status"] for path in report["paths"].values()}, {"not_run"})
        self.assertTrue(any("从空库初始化种子" in value for value in report["coverageNotRun"]))
        self.assertTrue(any("从源码还原和构建" in value for value in report["coverageNotRun"]))
        for obsolete in ("宿主启动与登录", "数据库连接、种子、迁移与业务操作"):
            self.assertNotIn(obsolete, report["coverageNotRun"])

    def test_report_reads_archived_planning_artifacts_and_status(self):
        archive = Path("openspec/changes/archive/2026-11-26-validate-r3-original-template-rollback")
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            repo = Path(directory).resolve()
            evidence = repo / "evidence"
            evidence.mkdir()
            spec = archive / "specs/template-application-rollback/spec.md"
            (repo / spec).parent.mkdir(parents=True)
            (repo / spec).write_text("# 回退规范\n", encoding="utf-8")
            status = f"?? {spec.as_posix()}"
            run = RollbackRun(repo, evidence, repo, repo / "upgrade", repo / "config.json")
            with patch.object(run, "git", side_effect=["a" * 40, "b" * 40, status]) as git:
                run.execution_inputs()
                git.assert_called_with(repo, "rollback-plan-status.log", "status", "--porcelain=v1",
                                       "--untracked-files=all", "--", archive)
            run.save()
            planning = read_json(run.report_path)["inputs"]["planning"]
            self.assertEqual(planning["change"], PLAN.name)
            self.assertEqual(planning["changePath"], archive.as_posix())
            self.assertEqual(planning["changeState"], "archived")
            self.assertEqual(planning["artifactSource"], "working_tree")
            self.assertEqual(planning["gitStatus"], [status])
            self.assertEqual(planning["artifacts"], [{"path": spec.as_posix(), "sha256": sha256(repo / spec)}])


if __name__ == "__main__":
    unittest.main()
