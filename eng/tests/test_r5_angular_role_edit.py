"""固定 Angular 验收的判定回归与基于正式报告的负向回放。"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_web_host import artifact
from r5_angular_role_edit import BrowserTraffic, EDIT_CHUNK, STEPS, empty_phases, run_stages, stage_result
from r5_template_role_update import DB_KEYS, RELEASES, check_connection, finish
from verify import ROOT, VerificationError, read_json, require, sha256


CASES = {
    "clean": ("passed", (3, 3)),
    "single-deviation": ("one_side_failed", (1, 3)),
    "same-deviation": ("both_failed", (1, 1)),
    "stale-list": ("one_side_failed", (1, 3)),
    "stale-row": ("one_side_failed", (1, 3)),
    "wrong-keyword": ("one_side_failed", (1, 3)),
    "missing-receipt": ("one_side_failed", (1, 3)),
    "other-business-connection": ("input_incomparable", (1, 3)),
    "missing-get-connection": ("input_incomparable", (1, 3)),
    "other-sql-connection": ("input_incomparable", (1, 3)),
    "other-sql-connection-missing-receipt": ("input_incomparable", (1, 3)),
    "other-business-connection-missing-receipt": ("input_incomparable", (1, 3)),
    "cross-side-diverged": ("input_incomparable", (1, 0)),
    "cross-side-unavailable": ("input_incomparable", (1, 0)),
    "cross-side-after-keep": ("input_incomparable", (3, 1)),
    "cross-side-after-keep-diverged": ("input_incomparable", (1, 1)),
}
OTHER_BUSINESS = {
    "other-business-connection", "other-business-connection-missing-receipt",
    "cross-side-diverged", "cross-side-unavailable", "cross-side-after-keep", "cross-side-after-keep-diverged",
}
MISSING_RECEIPT = {"missing-receipt", "other-sql-connection-missing-receipt",
                   "other-business-connection-missing-receipt"}


class RecordedSide:
    def __init__(self, label, original, other, case):
        self.original = original
        self.identity = original["preflight"]
        self.other_identity = other["preflight"]
        self.initial_expected = original["initial"]["expected"]
        self.roles = {key: {field: row["sql"][0][field] for field in ("id", "name", "normalizedName")}
                      for key, row in original["seed"]["roles"].items()}
        self.pid = original["processes"]["Web.Host"]["pid"]
        self.case = case
        self.affected = label == ("r5" if "after-keep" in case else "r4") or case == "same-deviation"
        self.run = SimpleNamespace(redact=lambda value: value)
        self.commands = []
        self.evidence = {}
        self.step = "initial"
        self.sql_needed = False

    def expected(self, values, role):
        return self.initial_expected | {"fields": values, "roles": [self.roles[role]] if role else []}

    def capture(self, step, expected):
        self.step = step
        original = self.original["phases"][step] if step != "initial" else self.original["initial"]
        self.sql_needed = True
        require(original["expected"] == expected, "实际请求的回放预期不同")
        capture = deepcopy({key: original[key] for key in ("host", "frontend", "catalog", "form")})
        if step != "initial":
            capture.update(deepcopy({key: original[key] for key in ("save", "clientCreationTime")}))
        for area in (capture.get("save", {}), capture["form"]):
            for kind in ("put", "get", "list", "roles"):
                for call in area.get(kind, []):
                    self.commands.append([kind, step])
                    if kind in ("put", "get"):
                        self.evidence[call["request"]["id"]] = call.pop("connection")
        if step == "keep" and self.affected:
            self.inject(capture)
        return capture

    def inject(self, capture):
        saved, form = capture["save"], capture["form"]
        put, = saved["put"]
        get, = form["get"]
        listing, = saved["list"]
        if self.case in OTHER_BUSINESS:
            for row in self.evidence[put["request"]["id"]]["events"]:
                if row["kind"] == "connection":
                    row.update(self.other_identity)
        if self.case == "missing-get-connection":
            binding = self.evidence[get["request"]["id"]]
            binding["events"] = [row for row in binding["events"] if row["kind"] != "connection"]
        if self.case in MISSING_RECEIPT:
            put.update(status=None, rawBody="", body=None, error="回放屏蔽浏览器收到的 PUT 回执")
        if self.case in ("single-deviation", "same-deviation"):
            get["body"]["result"]["roleNames"] = ["DU-ROLE-B"]
        if self.case == "stale-list":
            listing["body"]["result"]["items"][0]["fullName"] = "Seed User"
        if self.case == "stale-row":
            saved["rows"][0][1] = "Seed User"
        if self.case == "wrong-keyword":
            listing["request"]["url"] = listing["request"]["url"].replace("Keyword=durolecheck", "Keyword=wrong")

    def bind(self, call, record, complete):
        record.update(self.evidence[call["request"]["id"]])
        require(record["currentIdentity"] == self.identity, "回放前的库身份不符")
        check_connection(call, record["events"], self.pid, self.initial_expected["id"], self.identity, complete=complete)

    def sql(self):
        gate = not self.sql_needed
        self.sql_needed = False
        self.commands.append(["sql-gate" if gate else "sql", self.step])
        source = self.original["initial"] if self.step == "initial" else self.original["phases"][self.step]
        read = deepcopy(source["sql"]["observed"])
        if gate and self.case == "cross-side-unavailable":
            raise VerificationError("回放门控查询无法建立连接")
        if gate and self.case in ("cross-side-diverged", "cross-side-after-keep-diverged"):
            read["users"][0]["name"] = "Cross-side overwrite"
        if not gate and self.step == "keep" and self.affected and self.case.startswith("other-sql-connection"):
            read["identity"] = self.other_identity
        return read


def write_replay(output, report):
    contents = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with output.open("x", encoding="utf-8") as handle:
        handle.write(contents)


def replay(source, case, output):
    actual = read_json(source)
    require(actual["source"] == "live" and actual["workflow"] == "angular-user-role-edit"
            and actual["status"] == "passed", "回放需要本轮真实双侧通过的报告")
    sources = ("eng/r5_angular_role_edit.py", "eng/r5_template_role_update.py",
               "eng/tests/test_r5_angular_role_edit.py")
    report = {"source": "recorded_replay", "scenario": case, "formalReport": str(source),
              "formalReportSha256": sha256(source),
              "replaySources": [artifact(ROOT / name, ROOT) for name in sources], "sides": {}}
    sides = {}
    for label, other in zip(RELEASES, reversed(RELEASES)):
        side = sides[label] = RecordedSide(label, actual["sides"][label], actual["sides"][other], case)
        report["sides"][label] = record = {"status": "ready", "phases": empty_phases(), "commands": side.commands}
        expected = side.initial_expected
        record["initial"] = initial = side.capture("initial", expected) | {"expected": expected}
        require(stage_result(side, initial, initial=True) == "passed", "实际初态回放未通过")
    run_stages(sides, report)
    exit_code = finish(report)
    expected_status, expected_counts = CASES[case]
    require(report["status"] == expected_status and exit_code == (0 if case == "clean" else 1),
            f"回放汇总不符：{report['status']} / {exit_code}")
    for (label, side), count in zip(sides.items(), expected_counts):
        record = report["sides"][label]
        puts = [name for kind, name in side.commands if kind == "put"]
        require(puts == [key for key, _, _ in STEPS[:count]], f"{label} 有重复 PUT、漏跑或意外后续 PUT：{puts}")
        require(all(record["phases"][key]["status"] == "not_run" for key, _, _ in STEPS[count:]),
                f"{label} 未执行的后续阶段状态不符")
        if case in MISSING_RECEIPT and side.affected:
            stage = record["phases"]["keep"]
            require(stage["receiptAvailability"] == "missing" and stage["sql"]["diagnostic"],
                    "须登记缺回执及诊断判定")
            sql_count = side.commands.count(["sql", "keep"])
            put, = stage["save"]["put"]
            if case == "other-business-connection-missing-receipt":
                require(stage["status"] == "input_incomparable" and put["connection"]["status"] == "failed"
                        and put["connection"]["events"] and stage["sql"]["status"] == "not_run"
                        and sql_count == 0 and "observed" not in stage["sql"],
                        "业务库不可信且丢回执时应保留原请求并跳过本侧诊断 SQL")
            else:
                require(put["connection"]["status"] == "passed" and sql_count == 1,
                        "业务库可信且丢回执时须执行一次本侧诊断 SQL")
            if case == "missing-receipt":
                require(stage["status"] == "failed" and stage["sql"]["status"] == "passed",
                        "可信库上的正确诊断不能抵消缺回执")
        if case.startswith("other-sql-connection") and side.affected:
            stage = record["phases"]["keep"]
            require(stage["sql"]["status"] == stage["status"] == "input_incomparable"
                    and stage["save"]["put"][0]["connection"]["status"] == "passed",
                    "独立 SQL 换库必须优先于可信 PUT 和回执可用性")
        if case in OTHER_BUSINESS and not side.affected:
            gate_step = "replace" if "after-keep" in case else "keep"
            read = record["phases"][gate_step]["crossSideGate"]
            stops = case.endswith(("diverged", "unavailable"))
            require(read["status"] == ("input_incomparable" if stops else "passed"),
                    "跨侧门控状态与当前步骤只读结果不符")
            expected_start = "Angular Keep" if gate_step == "replace" else "Seed"
            require(read["expectedStart"]["fields"]["name"] == expected_start, "跨侧门控使用了错误的阶段起点")
            if stops:
                require(record["status"] == "input_incomparable", "门控失败须标记另一侧不可比")
            else:
                gate_index = next(i for i, (kind, _) in enumerate(side.commands) if kind == "sql-gate")
                require(side.commands[gate_index + 1] == ["put", gate_step], "独立只读门控必须发生在另一侧写入之前")
    write_replay(output, report)
    print(f"{case}: {report['status']}")
    return exit_code


class AngularAssetTests(unittest.TestCase):
    def test_browser_requires_actual_good_chunk_before_edit(self):
        frontend = "http://127.0.0.1:12345"
        path = "/" + EDIT_CHUNK
        body = b"synthetic JS response"
        response = SimpleNamespace(url=frontend + path, status=200, ok=True,
                                   request=SimpleNamespace(method="GET"), body=lambda: body)
        page = SimpleNamespace(on=lambda *args: None, route=lambda *args: None)
        traffic = BrowserTraffic(page, "http://127.0.0.1:12346", frontend, 5, str)
        expected = hashlib.sha256(body).hexdigest()
        with self.assertRaisesRegex(VerificationError, "未实收"):
            traffic.observed_asset(path, expected, [])
        traffic.on_response(response)
        rows = []
        with self.assertRaisesRegex(VerificationError, "与冻结产物不符"):
            traffic.observed_asset(path, "0" * 64, rows)
        self.assertEqual(rows, [{"url": frontend + path, "status": 200, "sha256": expected}])
        traffic.observed_asset(path, expected, [])


class ReplayOutputTests(unittest.TestCase):
    def test_creates_a_new_report(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "replay.json"
            report = {"source": "recorded_replay", "status": "passed"}
            write_replay(output, report)
            self.assertEqual(read_json(output), report)

    def test_existing_reports_and_aliases_keep_their_original_bytes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "formal.json"
            original = b'{"source":"live"}\n'
            source.write_bytes(original)
            symbolic = root / "symbolic.json"
            symbolic.symlink_to(source)
            hardlink = root / "hardlink.json"
            hardlink.hardlink_to(source)
            dangling = root / "dangling.json"
            missing = root / "missing.json"
            dangling.symlink_to(missing)

            for kind, output in (("source", source), ("symlink", symbolic), ("hardlink", hardlink),
                                 ("dangling", dangling)):
                with self.subTest(kind=kind), self.assertRaises(FileExistsError):
                    write_replay(output, {"source": "recorded_replay"})
            for existing in (source, symbolic, hardlink):
                self.assertEqual(existing.read_bytes(), original)
            self.assertEqual(dangling.readlink(), missing)
            self.assertFalse(missing.exists())


if __name__ == "__main__":
    if "--replay" in sys.argv:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--replay", type=Path, required=True)
        parser.add_argument("--case", choices=CASES, required=True)
        parser.add_argument("--output", type=Path, required=True)
        args = parser.parse_args()
        try:
            sys.exit(replay(args.replay, args.case, args.output))
        except FileExistsError:
            parser.error(f"回放输出已存在：{args.output}")
    unittest.main()
