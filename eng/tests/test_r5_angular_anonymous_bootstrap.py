"""Angular 匿名启动的证据判定与跨侧比较回归。"""

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r5_angular_anonymous_bootstrap import (
    APP_CONFIG, INIT, LABELS, LOGIN, SESSION, USER_CONFIG, StartupTraffic,
    check_bootstrap, finish_bootstrap, observed_session, observed_user_config,
)
from verify import VerificationError


FRONT = "http://127.0.0.1:52462"
HOST = "http://127.0.0.1:52461"
SCRIPTS = ["/main-x.js", "/scripts-x.js", "/chunk-x.js"]
FILES = {"index.html": "index", APP_CONFIG.lstrip("/"): "config",
         **{path.lstrip("/"): path for path in SCRIPTS}}
CONFIG = {"appBaseUrl": FRONT, "remoteServiceBaseUrl": HOST, "localeMappings": []}


def observation():
    def asset(path, hashed, sequence=1):
        return {"path": path, "method": "GET", "origin": FRONT, "status": 200, "finished": True,
                "redirected": False, "sequence": sequence, "responseSequence": sequence + 1,
                "sha256": hashed}

    texts = {"LogIn": "Log in", "UserNameOrEmail": "Username or email", "Password": "Password"}
    headers = {"authorization": False, "identityCookie": False, "tenant": "empty"}
    calls = [asset(APP_CONFIG, "config", 3) | {"headers": headers}]
    for sequence, path in enumerate(INIT[1:], start=3):
        calls.append(asset(path, None, sequence * 2 - 1) | {
            "headers": headers, "origin": HOST, "cors": FRONT, "success": True})
    getall = observed_user_config(
        {"session": {"multiTenancySide": 2, "userId": None}, "clock": {"provider": "localClockProvider"},
         "localization": {"currentLanguage": {"name": "en"}, "values": {"AbpProjectName": texts}}})
    session = observed_session(
        {"application": {"version": "9.3.0", "releaseDate": "2026-11-28T13:00:00+08:00", "features": {}},
         "tenant": None})
    return {"documents": [asset("/", "index")], "scripts": [asset(path, path) for path in SCRIPTS],
            "navigations": [FRONT + "/", FRONT + LOGIN], "finalUrl": FRONT + LOGIN, "exactFinalRoute": True,
            "pageErrors": [], "webSockets": [], "unexpectedRequests": [], "preflight": [], "initialization": calls,
            "config": deepcopy(CONFIG), "userConfig": getall, "session": session,
            "form": {"visible": {key: True for key in ("title", "button", "username", "password")},
                     "empty": True, "texts": {"title": texts["LogIn"], "button": texts["LogIn"],
                                             "username": texts["UserNameOrEmail"], "password": texts["Password"]}}}


def compare_report(public, pair):
    return {"sides": {label: {"status": "passed", "observation": evidence}
                      for label, evidence in zip(LABELS, (public, pair))}}


class BootstrapTest(unittest.TestCase):
    def verify(self, evidence):
        check_bootstrap(evidence, FILES, SCRIPTS, CONFIG, FRONT, HOST)

    def test_direct_root_then_client_route_passes(self):
        self.verify(observation())

    def test_http_redirect_to_identical_login_document_fails(self):
        evidence = observation()
        original = evidence["documents"][0]
        evidence["documents"] = [original | {"status": 302}, original | {"path": LOGIN, "redirected": True}]
        with self.assertRaisesRegex(VerificationError, "HTTP 重定向"):
            self.verify(evidence)

    def test_wrong_adapter_body_fails(self):
        evidence = observation()
        evidence["scripts"][-1]["sha256"] = "wrong"
        with self.assertRaisesRegex(VerificationError, "静态字节"):
            self.verify(evidence)

    def test_missing_completed_session_response_fails(self):
        evidence = observation()
        evidence["initialization"][-1]["responseSequence"] = None
        with self.assertRaisesRegex(VerificationError, "初始化请求未按实际响应顺序"):
            self.verify(evidence)

    def test_actual_user_or_tenant_response_fails(self):
        for payload, field in (("userConfig", "userId"), ("session", "tenant")):
            with self.subTest(payload=payload):
                evidence = observation()
                evidence[payload]["identity"][field] = "non-null"
                with self.assertRaisesRegex(VerificationError, "实际响应带有"):
                    self.verify(evidence)

    def test_scope_excludes_tenant_or_signalr_request(self):
        evidence = observation()
        evidence["unexpectedRequests"].append({"path": "/signalr/negotiate"})
        with self.assertRaisesRegex(VerificationError, "超出匿名范围"):
            self.verify(evidence)

    def test_null_and_omitted_identity_compare_equal(self):
        public, pair = observation(), observation()
        pair["userConfig"]["identity"]["userId"] = "omitted"
        pair["session"]["identity"]["tenant"] = "omitted"
        report = compare_report(public, pair)
        self.assertEqual(finish_bootstrap(report), 0)
        self.assertEqual(report["comparison"], {"status": "equal", "differentFields": []})
        self.assertEqual(public["userConfig"]["identity"]["userId"], "null")

    def test_self_consistent_sides_still_require_same_language_texts_and_application(self):
        public, pair = observation(), observation()
        pair["userConfig"]["language"] = "fr"
        pair["userConfig"]["texts"]["LogIn"] = "Connexion"
        pair["form"]["texts"].update(title="Connexion", button="Connexion")
        pair["session"]["application"]["releaseDate"] = "2026-11-29T13:00:00+08:00"
        self.verify(public)
        self.verify(pair)
        report = compare_report(public, pair)
        self.assertEqual(finish_bootstrap(report), 1)
        self.assertEqual(report["status"], "cross_side_difference")
        self.assertEqual(report["comparison"]["differentFields"], ["language", "texts", "application"])

    def test_one_input_blocked_retains_other_pass(self):
        for blocked, passed in (LABELS, LABELS[::-1]):
            with self.subTest(blocked=blocked):
                report = compare_report(observation(), observation())
                report["sides"][blocked] = {"status": "input_incomparable"}
                self.assertEqual(finish_bootstrap(report), 1)
                self.assertEqual(report["comparison"]["status"], "not_run")
                self.assertEqual(report["sides"][passed]["status"], "passed")


class StartupTrafficTest(unittest.TestCase):
    def setUp(self):
        traffic = self.traffic = StartupTraffic.__new__(StartupTraffic)
        traffic.page = Mock()
        entries = [("/", "document"), (APP_CONFIG, "xhr"), *((path, "script") for path in SCRIPTS)]
        required = [Mock(url=FRONT + path, method="GET", resource_type=kind) for path, kind in entries]
        required.extend(Mock(url=HOST + path, method="GET", resource_type="xhr") for path in (USER_CONFIG, SESSION))
        image = Mock(url=FRONT + "/late-image", method="GET", resource_type="image")
        traffic.requests = dict.fromkeys([*required, image])
        traffic.finished = set(required)
        traffic.failed = set()

    def test_pending_image_does_not_hold_startup_window_open(self):
        self.traffic.wait_for_required(FRONT, HOST, SCRIPTS)
        self.traffic.page.wait_for_event.assert_not_called()

    def test_window_waits_until_required_script_finishes(self):
        traffic = self.traffic
        script = next(request for request in traffic.finished if request.url == FRONT + SCRIPTS[-1])
        traffic.finished.remove(script)

        def finish_script(event, *, predicate, timeout):
            self.assertEqual(event, "requestfinished")
            self.assertFalse(predicate())
            traffic.finished.add(script)
            self.assertTrue(predicate(script))

        traffic.page.wait_for_event.side_effect = finish_script
        traffic.wait_for_required(FRONT, HOST, SCRIPTS)
        traffic.page.wait_for_event.assert_called_once()


if __name__ == "__main__":
    unittest.main()
