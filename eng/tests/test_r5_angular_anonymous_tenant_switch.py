import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r5_angular_anonymous_tenant_switch import (
    APP_CONFIG, INIT, LOGIN, PHASES, SELECT, SESSION, TENANT_TEXTS, USER_CONFIG,
    check_database_state, check_host_target, check_switch, finish_switch, request_identity,
)
from verify import VerificationError


FRONTEND = "http://127.0.0.1:3001"
HOST = "http://127.0.0.1:3000"
SEED = {"id": 11, "tenancyName": "Default", "name": "Default tenant"}
FILES = {"index.html": "index", "main.js": "main", APP_CONFIG.lstrip("/"): "config"}
CONFIG = {"appBaseUrl": FRONTEND, "remoteServiceBaseUrl": HOST, "localeMappings": []}
TEXTS = {key: key for key in ("LogIn", "Password", "UserNameOrEmail", *TENANT_TEXTS)}


def request_row(loader, path, sequence, *, kind="Fetch", host=False, selected=False, method="GET", **body):
    identifier = str(sequence)
    return {"loaderId": loader, "requestId": identifier, "kind": kind, "path": path,
            "origin": HOST if host else FRONTEND, "method": method, "sequence": sequence, "redirected": False,
            "failed": False, "finishedSequence": sequence + 2, "wireHeadersObserved": True,
            "headers": {"dot": "omitted" if path == SESSION else "seed" if selected else "empty",
                        "dash": "seed" if selected else "omitted", "authorization": False, "authCookie": False},
            "responses": [{"loaderId": loader, "requestId": identifier, "sequence": sequence + 1, "status": 200,
                           "cors": FRONTEND if host else None, "success": True, **body}]}


def evidence_fixture():
    evidence = {"initialCookieCount": 0, "unexpected": 0, "pageErrors": 0, "webSockets": 0,
                "phases": [], "preflight": [], "requests": [], "commits": [],
                "sameDocumentRoutes": [{"loaderId": "doc-0", "route": FRONTEND + LOGIN}],
                "actions": [{"kind": "select", "sequence": 50}, {"kind": "clear", "sequence": 250}]}
    for index, name in enumerate(PHASES):
        selected = name == "tenant"
        loader, seq = f"doc-{index}", index * 200
        evidence["commits"].append({"loaderId": loader, "origin": FRONTEND})
        evidence["requests"].extend([
            request_row(loader, "/" if not index else LOGIN, seq + 1, kind="Document", sha256="index"),
            request_row(loader, "/main.js", seq + 5, kind="Script", sha256="main"),
            request_row(loader, APP_CONFIG, seq + 10, selected=selected, sha256="config", config=CONFIG),
            request_row(loader, USER_CONFIG, seq + 15, host=True, selected=selected, userConfig={
                "identity": {"userId": "null", "tenantId": "non-null" if selected else "null",
                             "impersonatorUserId": "omitted", "impersonatorTenantId": "null"},
                "side": 1 if selected else 2, "tenantMatchesSeed": selected,
                "clockProvider": "unspecifiedClockProvider", "language": "en", "texts": TEXTS,
            }),
            request_row(loader, SESSION, seq + 20, host=True, selected=selected, session={
                "identity": {"user": "null", "tenant": "non-null" if selected else "null"},
                "tenant": SEED.copy() if selected else None,
                "application": {"version": "9.3.0", "features": {}, "releaseDate": "2026-11-28T10:00:00"},
            }),
        ])
        label = SEED["tenancyName"] if selected else "NotSelected"
        phase = {"name": name, "loaderId": loader, "route": FRONTEND + LOGIN,
                 "navigationLoaderId": loader, "navigationType": "reload" if index else "navigate",
                 "tenantCookie": "seed" if selected else "omitted", "authCookie": False,
                 "form": {"visible": {key: True for key in ("title", "button", "username", "password")},
                          "empty": True, "texts": {"title": "LogIn", "button": "LogIn",
                                                   "username": "UserNameOrEmail", "password": "Password"}},
                 "tenantUi": {"label": f"CurrentTenant: {label} (Change)", "change": "Change",
                              "strong": SEED["tenancyName"] if selected else None,
                              "title": SEED["name"] if selected else None}}
        if name != "returnHost":
            phase["dialog"] = {"input": SEED["tenancyName"] if selected else "",
                               "texts": {key: key for key in TENANT_TEXTS[3:]}}
        evidence["phases"].append(phase)
    post = request_row("doc-0", SELECT, 60, host=True, method="POST", availability=1, tenantMatchesSeed=True)
    post["tenancyNameMatchesSeed"] = True
    evidence["requests"].insert(5, post)
    return evidence


def check(evidence):
    check_switch(evidence, FILES, ["/main.js"], CONFIG, FRONTEND, HOST, SEED)


def find(evidence, path, index):
    return next(row for row in evidence["requests"] if row["path"] == path and row["loaderId"] == f"doc-{index}")


class TenantSwitchTests(unittest.TestCase):
    def invalid(self, change, message):
        evidence = evidence_fixture()
        change(evidence)
        with self.assertRaisesRegex(VerificationError, message):
            check(evidence)

    def test_complete_switch_with_host_header_omission_and_anonymous_tenant_passes(self):
        evidence = evidence_fixture()
        check(evidence)
        self.assertEqual([2, 1, 2], [phase["semantics"]["side"] for phase in evidence["phases"]])
        self.assertTrue(all(phase["semantics"]["anonymous"] for phase in evidence["phases"]))
        self.assertEqual(SEED, evidence["phases"][1]["semantics"]["tenant"])

    def test_initial_host_getall_cannot_fill_same_content_return_receipt(self):
        self.invalid(lambda ev: find(ev, USER_CONFIG, 2).update(responses=find(ev, USER_CONFIG, 0)["responses"]),
                     "请求或文档身份")

    def test_changed_response_request_id_fails(self):
        self.invalid(lambda ev: find(ev, SESSION, 2)["responses"][0].update(requestId="foreign"), "请求或文档身份")

    def test_same_document_transition_is_not_a_reload(self):
        self.invalid(lambda ev: ev["commits"].pop(), "三个独立")

    def test_ordinary_cross_document_navigation_cannot_replace_either_reload(self):
        for index in (1, 2):
            with self.subTest(phase=PHASES[index]):
                self.invalid(lambda ev: ev["phases"][index].update(navigationType="navigate"),
                             f"{PHASES[index]} 的实际主文档导航类型须为 reload")

    def test_initial_document_must_be_an_ordinary_navigation(self):
        self.invalid(lambda ev: ev["phases"][0].update(navigationType="reload"),
                     "initialHost 的实际主文档导航类型须为 navigate")

    def test_missing_navigation_type_and_wrong_document_binding_fail(self):
        for index in range(len(PHASES)):
            with self.subTest(phase=PHASES[index], evidence="missing"):
                self.invalid(lambda ev: ev["phases"][index].pop("navigationType"), "实际主文档导航类型")
            with self.subTest(phase=PHASES[index], evidence="other loader"):
                self.invalid(lambda ev: ev["phases"][index].update(navigationLoaderId="other-loader"),
                             "实际主文档导航类型")

    def test_missing_or_repeated_response_fails(self):
        for case in ("missing", "duplicate"):
            with self.subTest(case=case):
                self.invalid(lambda ev: find(ev, SESSION, 1).update(
                    responses=find(ev, SESSION, 1)["responses"] * (0 if case == "missing" else 2)),
                    "响应缺失或重复")

    def test_clear_post_count_includes_canceled_failed_and_pending(self):
        for case in ("canceled", "failed", "pending"):
            with self.subTest(case=case):
                def update(evidence):
                    row = request_row("doc-1", SELECT, 260, host=True, method="POST")
                    row.update(failed=case if case != "pending" else False, responses=[], finishedSequence=0)
                    evidence["requests"].append(row)
                self.invalid(update, "请求缺失或重复")

    def test_selection_post_is_required_once(self):
        self.invalid(lambda ev: ev["requests"].remove(find(ev, SELECT, 0)), "请求缺失或重复")

    def test_repeated_selection_post_rejected(self):
        def update(evidence):
            evidence["requests"].append(request_row("doc-0", SELECT, 70, host=True, method="POST"))
        self.invalid(update, "请求缺失或重复")

    def test_selection_response_must_precede_reload(self):
        def update(evidence):
            post = find(evidence, SELECT, 0)
            post["responses"][0]["sequence"] = 205
            post["finishedSequence"] = 206
        self.invalid(update, "重载顺序")

    def test_each_selected_get_requires_its_actual_adapter_header(self):
        for path in INIT:
            for state in ("omitted", "other"):
                with self.subTest(path=path, state=state):
                    self.invalid(lambda ev: find(ev, path, 1)["headers"].update(dash=state), "Abp-TenantId")

    def test_wrong_session_tenant_fails(self):
        self.invalid(lambda ev: find(ev, SESSION, 1)["responses"][0]["session"]["tenant"].update(id="other"),
                     "与种子不符")

    def test_cookie_retained_after_clear_fails(self):
        self.invalid(lambda ev: ev["phases"][2].update(tenantCookie="seed"), "仍有租户")

    def test_signed_in_response_and_auth_headers_rejected_independently(self):
        self.invalid(lambda ev: find(ev, USER_CONFIG, 1)["responses"][0]["userConfig"]["identity"].update(
            userId="non-null"), "认证身份")
        self.invalid(lambda ev: find(ev, SESSION, 1)["headers"].update(authorization=True), "认证标记")

    def test_authorization_and_tenant_headers_classified_independently(self):
        self.assertEqual({"dot": "seed", "dash": "seed", "authorization": False, "authCookie": False},
                         request_identity({"Abp.TenantId": "11", "Abp-TenantId": "11",
                                           "Cookie": "Abp-TenantId=11"}, SEED))
        self.assertTrue(request_identity({"Cookie": ".AspNetCore.Identity.Application=sample"}, SEED)["authCookie"])

    def test_wrong_production_bytes_fail(self):
        self.invalid(lambda ev: find(ev, "/main.js", 1)["responses"][0].update(sha256="changed"), "静态字节")

    def test_wrong_database_guid_and_wrong_host_target_fail(self):
        identity = {"database": "current", "databaseId": 5, "databaseGuid": "current", "serverName": "server"}
        observed = {"identity": identity, "migrations": [{"migrationId": "migration"}], "tenantRows": [SEED]}
        self.assertEqual(SEED, check_database_state(observed, identity, ["migration"]))
        with self.assertRaisesRegex(VerificationError, "专用新库"):
            check_database_state(observed | {"identity": identity | {"databaseGuid": "other"}}, identity, ["migration"])
        self.assertEqual(1, len(check_host_target([{"clientPid": 10, "databaseId": 5, "database": "current"}], 10, identity)))
        with self.assertRaisesRegex(VerificationError, "Host 进程连接目标"):
            check_host_target([{"clientPid": 10, "databaseId": 5, "database": "other"}], 10, identity)

    def test_blocked_side_keeps_independently_passed_other_observation(self):
        evidence = evidence_fixture()
        check(evidence)
        report = {"sides": {"pair": {"status": "input_incomparable"},
                            "public": {"status": "passed", "observation": evidence}}}
        self.assertEqual(1, finish_switch(report))
        self.assertEqual("input_incomparable", report["status"])
        self.assertIs(evidence, report["sides"]["public"]["observation"])
        self.assertEqual(list(PHASES), report["sides"]["pair"]["notRun"])

    def test_independently_valid_different_languages_fail_comparison(self):
        left, right = evidence_fixture(), copy.deepcopy(evidence_fixture())
        find(right, USER_CONFIG, 1)["responses"][0]["userConfig"]["language"] = "en-US"
        check(left)
        check(right)
        report = {"sides": {"public": {"status": "passed", "observation": left},
                            "pair": {"status": "passed", "observation": right}}}
        self.assertEqual(1, finish_switch(report))
        self.assertEqual("cross_side_difference", report["status"])
        self.assertEqual([{"phase": "tenant", "fields": ["language"]}], report["comparison"]["differences"])

    def test_equal_sides_require_cleanup_success(self):
        observation = evidence_fixture()
        check(observation)
        report = {"sides": {key: {"status": "passed", "observation": observation} for key in ("public", "pair")}}
        self.assertEqual(0, finish_switch(report))
        self.assertEqual("equal", report["comparison"]["status"])
        self.assertEqual(1, finish_switch(report | {"cleanupError": "container"}))
