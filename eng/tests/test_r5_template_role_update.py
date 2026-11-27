"""用户角色验收报告的定向断言，以及从正式双库记录执行的反例入口。"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_web_host import write_json
from r5_template_role_update import (APP, DB_KEYS, RELEASES, STEPS, LiveRun, LiveSide, check_connection, check_dto,
                                     check_sql, fields, finish, result, run_phases, side_report, time_value)
from verify import VerificationError, read_json, require, sha256


CASES = ("one-side", "same-error", "other-connection", "other-sql-connection",
         "missing-receipt", "missing-receipt-untrusted")


class RecordedSide:
    def __init__(self, original, other, mode):
        self.identity = original["preflight"]
        self.other_identity = other["preflight"]
        self.seed = original["seed"]["expected"]
        self.pid = original["processes"]["Web.Host"]["pid"]
        self.roles = {label: evidence["sql"][0] for label, evidence in original["seed"]["roles"].items()}
        self.phases = original["phases"]
        self.other_phases = other["phases"]
        self.mode = mode
        self.calls = []
        self.reads = {}

    def expected(self, values, role):
        return self.seed | {"fields": values, "roles": [{key: self.roles[role][key]
                            for key in ("id", "name", "normalizedName")}] if role else []}

    def put(self, step, payload):
        self.calls.append(["PUT", step])
        self.step = step
        response = deepcopy(self.phases[step]["put"]["http"])
        require(response["request"]["json"] == payload, "回放请求与正式实发输入不同")
        self.reads[response["request"]["id"]] = deepcopy(self.phases[step]["putConnection"])
        if step == "keep":
            if self.mode in ("other-connection", "missing-receipt-untrusted"):
                other_events = self.other_phases[step]["putConnection"]["events"]
                other_identity = next(row for row in other_events if row["kind"] == "connection")
                for row in self.reads[response["request"]["id"]]["events"]:
                    if row["kind"] == "connection":
                        row.update({key: other_identity[key] for key in DB_KEYS})
            if self.mode in ("missing-receipt", "missing-receipt-untrusted"):
                response.update(status=None, rawBody="", body=None,
                                error="回放注入：在接收边界屏蔽已成功的 PUT 回执")
        return response

    def get(self, step):
        self.calls.append(["GET", step])
        response = deepcopy(self.phases[step]["get"]["http"])
        self.reads[response["request"]["id"]] = self.phases[step]["getConnection"]
        if step == "keep" and self.mode in ("one-side", "same-error"):
            response["body"]["result"]["roleNames"] = ["DU-ROLE-B"]
            response["rawBody"] = "回放注入：把首步 GET 的角色 A 改为 B"
        return response

    def sql(self):
        self.calls.append(["SQL", self.step])
        observed = deepcopy(self.phases[self.step]["sql"]["observed"])
        if self.step == "keep" and self.mode == "other-sql-connection":
            observed["identity"] = self.other_identity
        return observed

    def bind(self, http, evidence, complete):
        evidence.update(self.reads[http["request"]["id"]])
        require(evidence["currentIdentity"] == self.identity, "回放预检库身份不符")
        check_connection(http, evidence["events"], self.pid, self.seed["id"], self.identity, complete=complete)


def replay(source, case, output):
    actual = read_json(source)
    require(actual["status"] == "passed" and actual["source"] == "live", "回放要求使用双侧真实通过的原报告")
    report = {"source": "recorded_replay", "scenario": case, "formalReport": str(source),
              "formalReportSha256": sha256(source), "sides": {label: side_report() for label in RELEASES}}
    expected_puts = [["PUT", step] for step, *_ in STEPS]
    for label, other in zip(RELEASES, reversed(RELEASES)):
        affected = label == "r4" or case == "same-error"
        side = RecordedSide(actual["sides"][label], actual["sides"][other], case if affected else None)
        item = report["sides"][label]
        item["status"] = run_phases(side, item)
        item["commands"] = side.calls
        puts = [call for call in side.calls if call[0] == "PUT"]
        require(puts == (expected_puts[:1] if affected else expected_puts),
                f"{label} 发生重发、后续写入或漏掉独立运行：{side.calls}")
        if affected:
            first = item["phases"]["keep"]
            require(first["status"] == "failed" and all(item["phases"][step]["status"] == "not_run"
                                                        for step in ("replace", "clear")), "后续依赖阶段未停止")
            if case == "other-connection":
                require(first["put"]["status"] == first["get"]["status"] == first["sql"]["status"] == "passed"
                        and first["putConnection"]["status"] == "failed",
                        "换库必须独立于回执、GET 和 SQL 数据判定")
            if case == "other-sql-connection":
                sql = first["sql"]
                original = actual["sides"][label]["phases"]["keep"]["sql"]["observed"]
                require(all(first[key]["status"] == "passed" for key in ("put", "putConnection", "get", "getConnection"))
                        and sql["status"] == "input_incomparable"
                        and sql["observed"] == original | {"identity": side.other_identity}
                        and side.calls == [["PUT", "keep"], ["GET", "keep"], ["SQL", "keep"]],
                        "独立 SQL 换库须保留原始库身份和正确业务数据，停止该侧后续写入")
            if case == "missing-receipt":
                require(first["put"]["availability"] == "missing" and
                        first["put"]["status"] == "failed" and
                        first["get"]["status"] == first["sql"]["status"] == "passed" and
                        first["get"]["diagnostic"] and first["sql"]["diagnostic"],
                        "丢回执但两份诊断正确时仍须失败")
            if case == "missing-receipt-untrusted":
                require(side.calls == [["PUT", "keep"]] and first["get"]["status"] == first["sql"]["status"] == "not_run",
                        "业务库不可信时仍进行了诊断")
        else:
            require(item["status"] == "passed", "合格另一侧未独立完成")
    expected = {"one-side": "one_side_failed", "same-error": "both_failed",
                "other-connection": "input_incomparable", "other-sql-connection": "input_incomparable",
                "missing-receipt": "one_side_failed",
                "missing-receipt-untrusted": "input_incomparable"}
    require(finish(report) == 1 and report["status"] == expected[case], "验收入口分类不符")
    write_json(output, report)
    print(report["status"])
    return report["exitCode"]


class RoleUpdateTests(unittest.TestCase):
    def setUp(self):
        self.identity = dict(zip(DB_KEYS, ("instance", "test", 9, "guid")))
        self.values = fields("durolekeep", "Keep", "First", False)
        self.role = {"id": 4, "name": "du-role-a", "normalizedName": "DU-ROLE-A"}
        self.expected = {"id": 3, "tenantId": 1, "creatorUserId": 2, "creationTime": "2026-11-27T11:12:13.0123456",
                         "fields": self.values, "roles": [self.role], "catalog": [self.role]}
        self.dto = {"id": 3, "creationTime": self.expected["creationTime"], "roleNames": ["DU-ROLE-A"], **self.values}
        row = {"userId": 3, "tenantId": 1, "roleId": 4, "joinedRoleId": 4, "roleName": "du-role-a",
               "normalizedName": "DU-ROLE-A", "roleTenantId": 1, "roleIsDeleted": False}
        user = {"id": 3, "tenantId": 1, "creatorUserId": 2, "creationTime": self.expected["creationTime"],
                "isDeleted": False, **self.values}
        self.sql = {"identity": self.identity, "users": [user], "relations": [row],
                    "catalog": [self.role | {"tenantId": 1, "isDeleted": False}]}

    def test_dto_roles_require_normalized_name_and_exact_array(self):
        check_dto(self.dto, self.expected)
        for invalid in (["du-role-a"], ["DU-ROLE-A", "DU-ROLE-A"], None):
            with self.subTest(), self.assertRaises(VerificationError):
                check_dto(self.dto | {"roleNames": invalid}, self.expected)

    def test_sql_rejects_extra_duplicate_or_unjoined_relations(self):
        check_sql(self.sql, self.expected, self.identity)
        row = self.sql["relations"][0]
        for invalid in ([row, row], [row | {"roleId": 99}], [row | {"roleTenantId": 2}],
                        [row | {"tenantId": 2}], [row | {"joinedRoleId": None}], [row | {"roleIsDeleted": True}]):
            with self.subTest(), self.assertRaises(VerificationError):
                check_sql(self.sql | {"relations": invalid}, self.expected, self.identity)

    def test_sql_clear_requires_zero_relations(self):
        expected = self.expected | {"roles": []}
        check_sql(self.sql | {"relations": []}, expected, self.identity)
        with self.assertRaises(VerificationError):
            check_sql(self.sql, expected, self.identity)
        with self.assertRaises(VerificationError):
            check_sql(self.sql | {"relations": [], "catalog": []}, expected, self.identity)

    def test_creation_time_compares_seventh_digit_and_preserves_wall_clock(self):
        self.assertEqual(time_value("2026-11-27T11:12:13.0123450"), time_value("2026-11-27T11:12:13.012345"))
        with self.assertRaises(VerificationError):
            check_dto(self.dto | {"creationTime": "2026-11-27T11:12:13.012345"}, self.expected)
        with self.assertRaises(VerificationError):
            check_sql(self.sql | {"users": [self.sql["users"][0] | {"creationTime": "2026-11-27T11:12:13.0123450"}]},
                      self.expected, self.identity)
        with self.assertRaises(VerificationError):
            time_value(self.expected["creationTime"] + "+08:00")

    def test_same_named_database_without_matching_guid_is_rejected(self):
        identity = {"pid": 4, "requestId": "request", "activityId": "activity", "method": "GET",
                    "path": APP + "User/Get", "userId": 3}
        call = {"request": {"id": "request", "method": "GET", "path": APP + "User/Get"}, "status": 200}
        command = {"commandId": "command", "operation": "lookup"}
        events = [{"kind": "request", "request": identity}, {"kind": "connection", "request": identity, **command,
                  **self.identity, "sessionId": 101, "connectionId": "a", "clientConnectionId": "b", "context": "db"},
                  {"kind": "completed", "request": identity, **command},
                  {"kind": "response", "request": identity, "status": 200}]
        check_connection(call, events, 4, 3, self.identity, complete=True)
        events[1]["databaseGuid"] = "different"
        with self.assertRaisesRegex(VerificationError, "实际"):
            check_connection(call, events, 4, 3, self.identity, complete=True)


class RoleUpdateHttpTests(unittest.TestCase):
    payload = {"id": 3, "roleNames": None}
    response = b'{"success":true,"result":{"id":3,"password":"test-redaction"}}'

    def exchange(self, headers, wire_body):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_PUT(self):
                requests.append((self.command, self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                self.send_response(200)
                self.send_header("Connection", "close")
                for name, value in headers:
                    self.send_header(name, str(value))
                self.end_headers()
                self.wfile.write(wire_body)
                self.close_connection = True

            def log_message(self, format, *args):
                pass

        with HTTPServer(("127.0.0.1", 0), Handler) as server, ThreadPoolExecutor(max_workers=1) as workers:
            server.timeout = 3
            pending = workers.submit(server.handle_request)
            side = object.__new__(LiveSide)
            side.run = object.__new__(LiveRun)
            side.run.secrets = []
            side.base, side.headers = f"http://127.0.0.1:{server.server_port}", {}
            row, _ = side.http(APP + "User/Update", method="PUT", body=self.payload)
            pending.result(timeout=5)
        self.assertEqual(requests, [("PUT", APP + "User/Update", self.payload)])
        return row

    def test_valid_abp_json_with_truncated_content_length_is_unusable(self):
        row = self.exchange([("Content-Length", len(self.response) + 12)], self.response)
        self.assertEqual(row["status"], 200)
        self.assertIn("还缺 12 字节", row["error"])
        self.assertEqual(json.loads(row["rawBody"]), {"success": True, "result": {"id": 3, "password": "[已脱敏]"}})
        self.assertIsNone(row["body"])
        with self.assertRaisesRegex(VerificationError, "HTTP 回执不可用"):
            result(row)

    def test_close_delimited_http_body_without_content_length_is_usable(self):
        row = self.exchange([], self.response)
        self.assertEqual(result(row), {"id": 3, "password": "[已脱敏]"})

    def test_complete_chunked_http_body_is_usable(self):
        chunk = lambda part: f"{len(part):X}\r\n".encode() + part + b"\r\n"
        wire_body = chunk(self.response[:9]) + chunk(self.response[9:]) + b"0\r\n\r\n"
        row = self.exchange([("Transfer-Encoding", "chunked")], wire_body)
        self.assertEqual(result(row), {"id": 3, "password": "[已脱敏]"})


if __name__ == "__main__":
    if "--replay" in sys.argv:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--replay", type=Path, required=True)
        parser.add_argument("--case", choices=CASES, required=True)
        parser.add_argument("--output", type=Path, required=True)
        args = parser.parse_args()
        raise SystemExit(replay(args.replay, args.case, args.output))
    unittest.main()
