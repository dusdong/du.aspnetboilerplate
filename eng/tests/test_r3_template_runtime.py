"""针对原版模板运行入口的失败诊断回归。"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_template_browser import check_search, check_session
from r3_template_runtime import CREDENTIALS, RuntimeRun, check_lock, check_login_deltas
from r3_template_sql import RuntimeDatabase
from r3_web_host import write_json
from verify import ROOT, read_json


BASELINE = {"tenant": {"tenantId": 1, "tenancyName": "Default"},
            "account": {"userId": 2, "userName": "admin"},
            "keyword": "r3userabcdef", "matches": [{"id": 3, "userName": "r3userabcdef"}]}
APP_INPUTS = {"hostPort": 14436, "frontendPort": 14236}
SQL_INPUTS = {"sqlPort": 15436, "sqlServerName": "r3-template-fixture",
              "sqlBackupDirectory": "/var/opt/mssql/r3-backup"}


class RuntimeFailureTests(unittest.TestCase):
    def verify_failure(self, stage, message, exercise):
        # 缩小运行到一个真实阶段断言。其余构建、SQL 和浏览器交互由正式实跑覆盖。
        with TemporaryDirectory() as directory:
            root = Path(directory)
            run = RuntimeRun(ROOT, root, root / "runtime.json")
            step = run.step

            def focus(name, action):
                if name in (stage, "cleanup"):
                    step(name, exercise(run) if name == stage else action)

            run.step = focus
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as diagnostics:
                self.assertEqual(run.execute_runtime(), 1)
            report = read_json(root / "report.json")
            self.assertEqual(report["exitCode"], 1)
            self.assertEqual(report["stages"][stage]["status"], "failed")
            self.assertIn(message, report["stages"][stage]["reason"])
            self.assertIn(message, diagnostics.getvalue())
            self.assertEqual(report["stages"]["cleanup"]["status"], "passed")
            for name, item in report["stages"].items():
                if name not in (stage, "cleanup"):
                    self.assertEqual((item["status"], item["commands"]), ("not_run", []))
                    self.assertIn(stage, item["reason"])

    def test_wrong_template_gitlink_stops_before_materializing(self):
        def exercise(run):
            run.git = Mock(return_value="160000 commit " + "0" * 40 + "\tmodule-zero-core-template")
            return run.preflight

        self.verify_failure("preflight", "模板 gitlink 不符", exercise)

    def test_changed_yarn_lock_points_to_input(self):
        def exercise(run):
            lock = run.evidence / "yarn.lock"
            lock.write_text("# 已变化的锁文件\n")
            return lambda: check_lock(lock)

        self.verify_failure("angular_build", "Angular yarn.lock 摘要不符", exercise)

    def test_inaccessible_existing_restore_database_blocks_writes(self):
        def exercise(run):
            database = object.__new__(RuntimeDatabase)
            database.query = Mock(return_value=[{"targetAccess": 0}])
            return lambda: database.require_new_database("r3_template_fixture_restore")

        self.verify_failure("sql_preflight", "目标已存在：r3_template_fixture_restore", exercise)

    def test_missing_sql_inputs_fail_after_independent_build_steps(self):
        with TemporaryDirectory() as folder, patch.dict(os.environ, {key: "" for key in CREDENTIALS}):
            root = Path(folder)
            config = root / "runtime.json"
            write_json(config, APP_INPUTS)
            run = RuntimeRun(ROOT, root, config)
            step = run.step
            built = []

            def focus(name, action):
                if name in ("runtime_inputs", "sql_preflight", "cleanup"):
                    step(name, action)
                elif name in ("migrator_build", "angular_build"):
                    step(name, built.append, name)

            run.step = focus
            with patch("r3_template_runtime.available", return_value=True):
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    self.assertEqual(run.execute_runtime(), 1)
            self.assertEqual(built, ["migrator_build", "angular_build"])
            stages = read_json(root / "report.json")["stages"]
            for name in ("runtime_inputs", *built):
                self.assertEqual(stages[name]["status"], "passed")
            self.assertEqual(stages["sql_preflight"]["status"], "failed")
            self.assertIn("sqlServerName", stages["sql_preflight"]["reason"])
            self.assertIn("R3_TEMPLATE_SQL_PASSWORD", stages["sql_preflight"]["reason"])
            for name in ("migrate_and_seed", "prepare_and_backup", "source_browser", "restore_database",
                         "restore_browser"):
                self.assertEqual(stages[name]["status"], "not_run")

    def test_missing_local_backup_directory_is_diagnosed_at_sql_preflight(self):
        def exercise(run):
            write_json(run.config_file, APP_INPUTS | SQL_INPUTS |
                       {"localBackupDirectory": str(run.evidence / "absent")})
            run.credentials = ("fixture", "fixture", "fixture")
            with patch("r3_template_runtime.available", return_value=True):
                run.inputs()
            return run.sql_preflight

        self.verify_failure("sql_preflight", "localBackupDirectory", exercise)

    def test_missing_sql_password_is_diagnosed_at_sql_preflight(self):
        def exercise(run):
            write_json(run.config_file, APP_INPUTS | SQL_INPUTS |
                       {"localBackupDirectory": str(run.evidence)})
            run.credentials = ("fixture", None, "fixture")
            with patch("r3_template_runtime.available", return_value=True):
                run.inputs()
            return run.sql_preflight

        self.verify_failure("sql_preflight", "缺少 SQL Server 或登录输入：R3_TEMPLATE_SQL_PASSWORD", exercise)

    def test_missing_sql_client_is_diagnosed_at_sql_preflight(self):
        def exercise(run):
            write_json(run.config_file, APP_INPUTS | SQL_INPUTS |
                       {"localBackupDirectory": str(run.evidence)})
            run.credentials = ("fixture", "fixture", "fixture")
            with patch("r3_template_runtime.available", return_value=True):
                run.inputs()

            def sql_without_client():
                with patch("r3_template_runtime.RuntimeDatabase", side_effect=ModuleNotFoundError("pymssql")):
                    run.sql_preflight()

            return sql_without_client

        self.verify_failure("sql_preflight", "SQL Server 客户端 pymssql 不可用", exercise)

    def test_create_database_capability_allows_non_developer_edition(self):
        with TemporaryDirectory() as folder:
            database = object.__new__(RuntimeDatabase)
            database.config = SQL_INPUTS
            database.source, database.restored = "source", "restore"
            database.name = "fixture.bak"
            database.local_backup = Path(folder) / database.name
            database.server_backup = "/var/opt/mssql/r3-backup/fixture.bak"
            identity = {"database": "master", "serverName": SQL_INPUTS["sqlServerName"],
                        "edition": "Standard Edition", "dataPath": "/var/opt/mssql/data",
                        "logPath": "/var/opt/mssql/data", "createDatabase": 1,
                        "createAnyDatabase": 0, "alterAnyDatabase": 0}
            absent_db = [{"targetAccess": None}]
            absent_file = [{"file_exists": 0, "file_is_a_directory": 0, "parent_directory_exists": 1}]
            database.query = Mock(side_effect=[[identity], absent_db, absent_db, [{"file_is_a_directory": 1}],
                                               absent_file, absent_file, absent_file])
            evidence = database.preflight()
            self.assertEqual((evidence["edition"], evidence["createDatabase"]), ("Standard Edition", 1))

    def test_missing_create_capability_is_diagnosed_before_database_operations(self):
        def exercise(run):
            database = object.__new__(RuntimeDatabase)
            database.config = SQL_INPUTS
            database.query = Mock(return_value=[{"database": "master", "serverName": SQL_INPUTS["sqlServerName"],
                                                 "edition": "Developer Edition", "createDatabase": 0,
                                                 "createAnyDatabase": 0, "alterAnyDatabase": 0}])

            def preflight():
                try:
                    database.preflight()
                finally:
                    database.query.assert_called_once()

            return preflight

        self.verify_failure("sql_preflight", "缺少 CREATE DATABASE", exercise)

    def test_missing_default_tenant_seed_fails_before_browser(self):
        def exercise(run):
            database = object.__new__(RuntimeDatabase)
            database.query = Mock(side_effect=[[{"migrationId": "fixture"}], []])
            return lambda: database.seed("fixture", ["fixture"])

        self.verify_failure("migrate_and_seed", "共享库租户种子", exercise)

    def test_wrong_session_tenant_fails_round(self):
        identity = {"tenantId": 9, "userId": 2, "userName": "admin"}
        self.verify_failure("source_browser", "服务端会话身份不符",
                            lambda _: lambda: check_session(identity, BASELINE))

    def test_initial_list_without_keyword_cannot_pass(self):
        self.verify_failure("source_browser", "搜索请求 Keyword 不符",
                            lambda _: lambda: check_search([], 1, BASELINE["matches"], [BASELINE["keyword"]],
                                                          BASELINE))

    def test_search_with_incorrect_total_cannot_pass(self):
        self.verify_failure("source_browser", "搜索响应不符",
                            lambda _: lambda: check_search([BASELINE["keyword"]], 2, BASELINE["matches"],
                                                          [BASELINE["keyword"]], BASELINE))

    def test_search_with_wrong_result_id_cannot_pass(self):
        items = [{"id": 4, "userName": BASELINE["keyword"]}]
        self.verify_failure("source_browser", "搜索响应不符",
                            lambda _: lambda: check_search([BASELINE["keyword"]], 1, items,
                                                          [BASELINE["keyword"]], BASELINE))

    def test_missing_username_cell_fails_even_with_correct_api(self):
        self.verify_failure("source_browser", "用户名列不符",
                            lambda _: lambda: check_search([BASELINE["keyword"]], 1, BASELINE["matches"], [],
                                                          BASELINE))

    def test_restored_round_login_written_to_source_fails(self):
        before, after = {"source": 2, "restore": 1}, {"source": 3, "restore": 1}
        self.verify_failure("restore_browser", "实际 {'source': 1, 'restore': 0}",
                            lambda _: lambda: check_login_deltas(before, after, "source", "restore"))


if __name__ == "__main__":
    unittest.main()
