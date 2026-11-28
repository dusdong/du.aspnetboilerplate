"""Angular 匿名启动的证据判定与跨侧比较回归。"""

from copy import deepcopy
import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import r5_angular_anonymous_bootstrap as bootstrap
from r5_angular_anonymous_bootstrap import (
    APP_CONFIG, INIT, LABELS, LOGIN, SESSION, USER_CONFIG, StartupTraffic,
    check_bootstrap, finish_bootstrap, observed_session, observed_user_config,
)
from verify import VerificationError, sha256


FRONT = "http://127.0.0.1:52462"
HOST = "http://127.0.0.1:52461"
SCRIPTS = ["/main-x.js", "/scripts-x.js", "/chunk-x.js"]
FILES = {"index.html": "index", APP_CONFIG.lstrip("/"): "config",
         **{path.lstrip("/"): path for path in SCRIPTS}}
CONFIG = {"appBaseUrl": FRONT, "remoteServiceBaseUrl": HOST, "localeMappings": []}


class PairInputTest(unittest.TestCase):
    def test_sealed_digests_match_published_pair_guide(self):
        # 独立期望来自双包指南的「固定输入」表。
        expected = {
            "abp-ng2-module": "b8939f43e0c05afafcbfb8371c99646006565dc4a613698fd39b6c6b4aa3a2bd",
            "abp-web-resources": "93c66026539a1c22740b893f4ff8b6213b80e5a9ccbee247c79f651e2648a126",
        }
        for name, digest in expected.items():
            with self.subTest(package=name):
                self.assertEqual(bootstrap.PACKAGES[name][3], digest)


class PairArchiveTest(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.angular = root / "source" / "angular"
        self.archives = root / "inputs"
        self.archives.mkdir()
        fesm = "fesm2022/abp-ng2-module.mjs"
        self.adapter_installed = self.angular / bootstrap.FESM
        self.adapter_body = b"export const candidate = 'adapter';\n"
        script = "node_modules/abp-web-resources/abp.js"
        script_body = b"window.abp = {};\n"
        self.adapter_archive = self.archives / "abp-ng2-module-12.1.0.tgz"
        resources_archive = self.archives / "abp-web-resources-6.1.0.tgz"
        packages = {}
        dependencies = {}
        lock = []
        for name, version, member, body, archive in (
            (bootstrap.ADAPTER, "12.1.0", fesm, self.adapter_body, self.adapter_archive),
            (bootstrap.RESOURCES, "6.1.0", "abp.js", script_body, resources_archive),
        ):
            installed = self.angular / "node_modules" / name
            (installed / member).parent.mkdir(parents=True)
            (installed / member).write_bytes(body)
            self.write_archive(archive, member, body)
            spec = dependencies[name] = f"file:../../../inputs/{archive.name}"
            sha1 = hashlib.sha1(archive.read_bytes()).hexdigest()
            lock.append(f'{name}@{spec}:\n  version "{version}"\n  resolved "{spec}#{sha1}"\n')
            packages[name] = (version, sha1, bootstrap.manifest_digest(bootstrap.file_rows(installed)),
                              sha256(archive))
        self.original_adapter_sha1 = packages[bootstrap.ADAPTER][1]
        self.original_resource_sha256 = sha256(resources_archive)
        self.original_lock = "\n".join([*lock, 'tslib@^2.8.0:\n  version "2.8.1"\n']).encode()
        self.lock = self.angular / "yarn.lock"
        self.lock.write_bytes(self.original_lock)

        manifest = self.angular / "package.json"
        manifest.write_text(json.dumps({"dependencies": dependencies}))
        config = self.angular / "angular.json"
        config.write_text(json.dumps({"projects": {"AbpProjectName": {"architect": {
            "build": {"options": {"scripts": [script]}}}}}}))
        self.reads = root / "global-reads.jsonl"
        self.reads.write_text(json.dumps({"path": script, "realpath": str(self.angular / script),
                                          "pid": 123, "cwd": str(self.angular), "bytes": len(script_body),
                                          "sha256": sha256(self.angular / script),
                                          "caller": "/tools/esbuild/global-scripts.js:25"}) + "\n")
        browser = self.angular / "dist" / "browser"
        browser.mkdir(parents=True)
        (browser / bootstrap.CHUNK).write_bytes(self.adapter_body)
        (browser / bootstrap.GLOBAL).write_bytes(script_body)
        stats = browser.parent / "stats.json"
        stats.write_text(json.dumps({"outputs": {
            bootstrap.CHUNK: {"inputs": {bootstrap.FESM: {"bytesInOutput": 8985}},
                              "bytes": len(self.adapter_body)},
            bootstrap.GLOBAL: {"entryPoint": "angular:script/global:scripts.js", "bytes": len(script_body)},
        }}))
        self.stats_sha256 = sha256(stats)

        # 以小型清单和配置替代固定 production 输入，保留包、实装、锁和统计的检查逻辑。
        production_rows = bootstrap.file_rows(browser)
        production_rows.update({f"asset-{index}": (0, bootstrap.digest(b"")) for index in range(1191)})
        self.enterContext(patch.multiple(
            bootstrap, PACKAGES=packages, PAIR_LOCK=bootstrap.digest(self.original_lock),
            PAIR_FILES=bootstrap.manifest_digest(production_rows)))
        file_rows = bootstrap.file_rows
        self.enterContext(patch.object(bootstrap, "file_rows", side_effect=lambda path:
                                     production_rows if path == browser else file_rows(path)))
        config_digests = {
            manifest: "790d231431c8f1f9b52fc3213a1d3dc7251fc75485c4b19bad813442173f719f",
            config: "cf94a2532bab3a223f957ad71ee7446d269545698037d52560b7be830d7c9a92",
        }
        self.enterContext(patch.object(bootstrap, "sha256", side_effect=lambda path:
                                     config_digests[path] if path in config_digests else sha256(path)))

    @staticmethod
    def write_archive(path, relative, body, gzip_mtime=0):
        buffer = BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            member = tarfile.TarInfo(f"package/{relative}")
            member.size = len(body)
            archive.addfile(member, BytesIO(body))
        path.write_bytes(gzip.compress(buffer.getvalue(), mtime=gzip_mtime))

    def update_adapter_lock(self):
        actual_sha1 = hashlib.sha1(self.adapter_archive.read_bytes()).hexdigest()
        spec = f"file:../../../inputs/{self.adapter_archive.name}#"
        self.lock.write_bytes(self.original_lock.replace((spec + self.original_adapter_sha1).encode(),
                                                         (spec + actual_sha1).encode()))
        return actual_sha1

    def verify(self):
        _, _, evidence = bootstrap.verify_pair(self.angular, self.archives, self.reads, self.stats_sha256)
        return evidence["packages"]

    def test_original_archives_match_seals(self):
        packages = self.verify()
        self.assertIs(packages[bootstrap.ADAPTER]["matchesSealedArchive"], True)
        self.assertIs(packages[bootstrap.RESOURCES]["matchesSealedArchive"], True)

    def test_repacked_adapter_requires_actual_lock_sha1(self):
        original = self.adapter_archive.read_bytes()
        self.adapter_archive.write_bytes(gzip.compress(gzip.decompress(original), mtime=1))
        self.assertNotEqual(self.adapter_archive.read_bytes(), original)
        with self.assertRaisesRegex(VerificationError, "冻结锁或模板声明未指向实际归档：abp-ng2-module"):
            self.verify()

        actual_sha1 = self.update_adapter_lock()
        packages = self.verify()
        adapter, resources = packages[bootstrap.ADAPTER], packages[bootstrap.RESOURCES]
        self.assertEqual(adapter["lockSha1"], actual_sha1)
        self.assertEqual(adapter["sha256"], sha256(self.adapter_archive))
        self.assertIs(adapter["matchesSealedArchive"], False)
        self.assertEqual(resources["sha256"], self.original_resource_sha256)
        self.assertIs(resources["matchesSealedArchive"], True)

    def test_changed_archive_rejected_with_matching_install_and_lock(self):
        changed = b"export const candidate = 'different';\n"
        member = self.adapter_installed.relative_to(self.angular / "node_modules" / bootstrap.ADAPTER)
        self.write_archive(self.adapter_archive, member.as_posix(), changed)
        self.adapter_installed.write_bytes(changed)
        self.update_adapter_lock()
        with self.assertRaisesRegex(VerificationError, "归档内容与登记候选不符：abp-ng2-module"):
            self.verify()

    def test_changed_install_rejected_with_original_archive_and_lock(self):
        self.adapter_installed.write_bytes(b"export const candidate = 'different';\n")
        with self.assertRaisesRegex(VerificationError, "实际安装与归档不符：abp-ng2-module"):
            self.verify()

    def test_unrelated_lock_change_rejected_with_matching_archives_and_install(self):
        self.lock.write_bytes(self.original_lock.replace(b'  version "2.8.1"', b'  version "2.8.2"'))
        with self.assertRaisesRegex(VerificationError, "双包冻结锁与登记组合不符"):
            self.verify()


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
