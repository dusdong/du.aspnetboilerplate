"""在隔离副本上核对 R5 部分受理和直接依赖 gate。"""

import argparse
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3_automapper_packages import ADAPTER, COLLECTION, CORE, ENGINE
import r5_oidc
from r4_public_release import GALLERY, SIGNATURE, SYMBOLS
from r5_public_release import ReleaseProgress, load_release, verified_downloads
from verify import ROOT, VerificationError, read_json, require, sha256


DEBUG_GUID = "0123456789ABCDEF0123456789ABCDEF"


class IsolatedProtocol:
    def __init__(self):
        self.responses = {}
        self.requests = []
        self.nupkg_verifications = []

    def get(self, url, headers=None):
        self.requests.append(url)
        data = self.responses.get(url)
        return {"url": url, "httpStatus": 404 if data is None else 200}, data

    def certificates(self, work):
        return {"隔离样本指纹"}

    def owners(self, name):
        return {"owners": ["sample-owner"]}

    def signature(self, package, fingerprints, directory):
        with ZipFile(package) as file:
            require(file.read(SIGNATURE) == b"isolated signature fixture", "隔离签名标记不符")
        self.nupkg_verifications.append(package.name)
        log = directory / "signature.log"
        log.write_text("隔离协议样本，签名验证由真实 R4 实物单独覆盖。\n", encoding="utf-8")
        return {"owners": ["sample-owner"], "logSha256": sha256(log)}

    def symbol(self, directory, dll, pdb=None):
        return {"name": f"{dll.stem}.pdb", "guid": DEBUG_GUID,
                "checksum": "SHA256:isolated-fixture"}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.case = self.evidence / self._testMethodName
        self.case.mkdir()
        self.root = self.case / "frozen"
        shutil.copytree(self.batch, self.root)
        self.work = self.case / "progress"
        self.work.mkdir()
        self.protocol = IsolatedProtocol()
        self.proof_count = 0

    def open_progress(self):
        manifest, _, handoff = load_release(self.root, self.batch_sha, self.manifest, self.manifest_sha,
                                            verify_carried=False)
        return ReleaseProgress(manifest, self.manifest_sha, self.root, self.batch_sha, handoff, self.work,
                               self.protocol, self.protocol)

    def assert_gate(self, progress, name, code, *, own, blocked, kind="main"):
        with redirect_stdout(log := StringIO()):
            actual = progress.symbol_gate(name) if kind == "symbols" else progress.gate(name)
        output = log.getvalue()
        with (self.case / "gate-results.log").open("a", encoding="utf-8") as stream:
            stream.write(f"gate {name} {kind} exitCode={actual}\n{output}")
        self.assertEqual(code, actual, output)
        result = json.loads(output.strip().splitlines()[-1])
        self.assertEqual(code == 0, result["ready"])
        self.assertEqual(own, result["main"])
        if kind == "main":
            self.assertEqual(blocked, result["blockedBy"])
        return result

    def archive(self, progress, name, kind="archive"):
        row = progress.manifest["packages"][name][kind]
        return self.root / row["path"], row["sha256"]

    def url(self, progress, name):
        return f"{GALLERY}/{name}/{progress.manifest['packages'][name]['version']}"

    def sample_main(self, progress, name, *, extra=False, omit_dependency=False):
        archive, _ = self.archive(progress, name)
        out = BytesIO()
        with ZipFile(archive) as original, ZipFile(out, "w") as sample:
            for member in original.namelist():
                content = original.read(member)
                if omit_dependency and member.endswith(".nuspec"):
                    tree = ET.fromstring(content)
                    group = tree.find(".//{*}dependencies/{*}group")
                    dependency = next(item for item in group if item.get("id") == ENGINE)
                    group.remove(dependency)
                    content = ET.tostring(tree)
                sample.writestr(member, content)
            sample.writestr(SIGNATURE, b"isolated signature fixture")
            if extra:
                sample.writestr("unexpected.txt", b"extra member")
        self.protocol.responses[self.url(progress, name)] = out.getvalue()

    def accept_main(self, progress, name):
        _, digest = self.archive(progress, name)
        progress.record("main", name, "accepted", "隔离样本主包受理", ["sample-owner"], digest)

    def prepare_upload_cli(self):
        self.protocol_root = self.case / "protocol"
        self.protocol_root.mkdir()
        doc = (ROOT / "docs/maintenance/r5-automapper-template.md").read_text(encoding="utf-8")
        section = doc.split("#### 执行待发交接手册", 1)[1]
        self.publisher = section.split("```sh\n", 1)[1].split("```", 1)[0]
        (self.protocol_root / "sitecustomize.py").write_text(
            """import json
import os
from pathlib import Path
import subprocess
from verify_r5_public_release import IsolatedProtocol
import r4_public_release

case = Path(os.environ["R5_TEST_CASE"])
protocol = IsolatedProtocol()
for url, file in json.loads((case / "responses.json").read_text()).items():
    protocol.responses[url] = Path(file).read_bytes()
r4_public_release.NuGet = lambda timeout: protocol
r4_public_release.Dotnet = lambda work: protocol
action = os.getenv("R5_TEST_ACTION")
if action == "wrong-owner":
    protocol.owners = lambda name: {"owners": ["other-owner"]}
if action == "not-started":
    def cannot_start(*args, **kwargs):
        raise FileNotFoundError("隔离样本无法启动 dotnet")

    subprocess.Popen = cannot_start
if action in ("fail-intent", "fail-run-binding", "fail-result"):
    real_replace = os.replace

    def replace(source, destination):
        if Path(destination).name == "progress.json":
            intents = json.loads(Path(source).read_text()).get("uploadIntents", {})
            if action == "fail-intent" and intents:
                raise OSError("隔离样本意向持久化失败")
            if action == "fail-run-binding" and any("runId" in rows[-1].get("workflow", {})
                                                     for rows in intents.values()):
                raise OSError("隔离样本托管运行 ID 持久化失败")
            if action == "fail-result" and any("result" in rows[-1] for rows in intents.values()):
                raise OSError("隔离样本结果持久化失败")
        real_replace(source, destination)

    os.replace = replace
""", encoding="utf-8")
        dotnet = self.protocol_root / "dotnet"
        dotnet.write_text(
            """#!/bin/sh
printf '%s\\n' "$*" >> "$R5_TEST_CASE/uploads.log"
case "$R5_TEST_ACTION" in
  interrupt) kill -KILL "$PPID" ;;
  hold)
    kill -KILL "$PPID"
    while [ ! -f "$R5_TEST_CASE/release-child" ]; do sleep 0.05; done
    ;;
  nonzero) exit 17 ;;
  oidc-main-forbidden)
    printf '  GET https://api.nuget.org/v3/index.json\n  OK https://api.nuget.org/v3/index.json 5ms\n'
    printf '  PUT https://www.nuget.org/api/v2/package/\n  Forbidden https://www.nuget.org/api/v2/package/ 8ms\n'
    printf '上游原始失败详情 %s\n' "$NUGET_API_KEY"
    printf '  InternalServerError https://www.nuget.org/api/v2/package 8ms\n%s\n' "$NUGET_API_KEY" >&2
    exit 17
    ;;
  oidc-symbol-failure)
    printf '  PUT https://untrusted.example/v2/symbolpackage\n'
    printf '  PUT https://www.nuget.org/api/v2/symbolpackage\n'
    printf '  471 https://www.nuget.org/api/v2/symbolpackage 7ms (retry after: 1.5s)\n'
    printf '  Forbidden https://www.nuget.org/api/v2/symbolpackage 8ms %s\n' "$NUGET_SYMBOL_API_KEY"
    exit 19
    ;;
esac
exit 0
""", encoding="utf-8")
        dotnet.chmod(0o755)

    def upload_cli(self, verb, *arguments, action="success", concurrent=False):
        responses = {}
        for index, (url, data) in enumerate(self.protocol.responses.items()):
            path = self.protocol_root / f"response-{index}"
            path.write_bytes(data)
            responses[url] = str(path)
        (self.case / "responses.json").write_text(json.dumps(responses), encoding="utf-8")
        env = os.environ | {
            "PATH": f"{self.protocol_root}:{os.environ['PATH']}",
            "PYTHONPATH": os.pathsep.join(map(str, (self.protocol_root, ROOT / "eng", ROOT / "eng/tests"))),
            "PYTHONDONTWRITEBYTECODE": "1", "R5_TEST_CASE": str(self.case), "R5_TEST_ACTION": action,
            "R5_BATCH": str(self.root), "R5_MANIFEST": str(self.manifest), "R5_RELEASE_WORK": str(self.work),
        }
        for secret in ("NUGET_API_KEY", "NUGET_SYMBOL_API_KEY"):
            env.pop(secret, None)
        command = ["/bin/sh", "-c", self.publisher + f'\n{verb} "$@"\n', "r5-test", *arguments]
        if concurrent:
            return subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True)
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        with (self.case / "cli.log").open("a", encoding="utf-8") as log:
            log.write(f"{verb} {arguments} 模式={action} exit={result.returncode}\n{result.stdout}{result.stderr}")
        return result

    def assert_cli(self, code, verb, *args, **options):
        result = self.upload_cli(verb, *args, **options)
        self.assertEqual(code, result.returncode, result.stdout + result.stderr)
        return result

    def upload_count(self):
        log = self.case / "uploads.log"
        return len(log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0

    def intent(self, kind):
        intent = read_json(self.work / "progress.json")["uploadIntents"][f"{kind}/{ENGINE}"][-1]
        progress = self.open_progress()
        row = progress.manifest["packages"][ENGINE]
        self.assertEqual((self.batch_sha, ENGINE, row["version"], kind,
                          row["archive" if kind == "main" else "symbols"]["sha256"]),
                         tuple(intent[key] for key in ("batchSha256", "package", "version", "kind", "uploadSha256")))
        self.assertTrue(intent["receipt"].startswith("push-"))
        return intent

    def prepare_oidc_cli(self):
        self.prepare_upload_cli()
        with (self.protocol_root / "sitecustomize.py").open("a", encoding="utf-8") as stream:
            stream.write('''
import r5_oidc
from unittest.mock import patch

protocol.owners = lambda name: {"owners": ["dusdong"]}
workflow = case / "workflow"
workflow.mkdir(exist_ok=True)
head = "a" * 40
archive = "Du.AutoMapper.14.0.1.nupkg"
real_github = r5_oidc.github

def github(endpoint, *, data=None, method="GET", download=None, timeout=45, include_status=False):
    with (workflow / "calls.log").open("a") as out:
        out.write(f"{method} {endpoint}\\n")
    if endpoint == "git/ref/heads/main":
        return {"object": {"sha": head}}
    if endpoint == "git/ref/tags/v10.5.2":
        return {"object": {"type": "tag", "sha": "b" * 40}}
    if endpoint == "git/tags/" + "b" * 40:
        return {"tag": r5_oidc.TAG, "object": {"type": "commit", "sha": r5_oidc.TAG_COMMIT}}
    if endpoint == "releases/700":
        return {"id": 700, "tag_name": r5_oidc.TAG, "draft": action != "published-draft",
                "assets": [{"name": name, "id": 800 + index, "state": "uploaded", "digest": f"sha256:{digest}"}
                           for index, (name, digest) in enumerate(r5_oidc.ARCHIVES.items())]}
    if endpoint.endswith("/dispatches"):
        (workflow / "dispatch.json").write_text(json.dumps(data))
        intent = json.loads((case / "progress/progress.json").read_text())["uploadIntents"]["main/Du.AutoMapper"][-1]
        assert intent["receipt"] == "push-" + data["inputs"]["intent"] + ".json"
        assert "runId" not in intent["workflow"]
        return {} if action == "unbound" else {"workflow_run_id": 901}
    if endpoint == "releases/assets/800":
        assert method == "PATCH"
        intent = json.loads((case / "progress/progress.json").read_text())["uploadIntents"]["main/Du.AutoMapper"][-1]
        assert intent["workflow"]["runId"] == "901"
        (workflow / "label").write_text(data["label"])
        return {"id": 800} | data
    if endpoint.endswith("/attempts/1"):
        login = endpoint.split("/")[2] == "900"
        inputs = {} if login else json.loads((workflow / "dispatch.json").read_text())["inputs"]
        run = {"id": 900 if login else 901, "run_attempt": 1, "event": "workflow_dispatch",
                "head_branch": "main", "path": r5_oidc.WORKFLOW_PATH, "display_title":
                r5_oidc.run_title("login-only") if login else r5_oidc.run_title("publish", inputs["intent"]),
                "head_sha": "c" * 40 if login and action == "wrong-login-head" else head,
                "repository": {"full_name": r5_oidc.REPO}, "head_repository": {"full_name": r5_oidc.REPO},
                "status": "in_progress" if not login and action == "running" else "completed",
                "conclusion": "success"}
        if not login and action in ("settling-run", "wrong-publish-run", "settling-http",
                                    "run-404", "run-403", "non-http-error", "receipt-404"):
            gets = (workflow / "calls.log").read_text().count("GET actions/runs/901/attempts/1\\n")
            intent = json.loads((case / "progress/progress.json").read_text())["uploadIntents"]["main/Du.AutoMapper"][-1]
            assert intent["workflow"]["runId"] == "901"
            if action == "receipt-404":
                assert not include_status and timeout == 45
            else:
                assert include_status and timeout == 4
            if (gets == 1 and action == "settling-run") or (gets == 3 and action == "settling-http"):
                run.update(head_repository=None, display_title="")
            elif action == "wrong-publish-run":
                run.update(head_sha="wrong-head-fixture", display_title="private-title-fixture")
            if action in ("settling-http", "run-404", "run-403", "non-http-error", "receipt-404"):
                status = 404 if action in ("run-404", "receipt-404") or (action == "settling-http" and gets == 1) else 200
                if action == "run-403":
                    status = 403
                body = json.dumps(run if status == 200 else {"status": "404", "message": "private-body-fixture"})
                response = f"HTTP/2.0 {status}\\r\\nContent-Type: application/json\\r\\n\\r\\n{body}"

                def gh_request(command, **options):
                    assert ("--include" in command) == include_status
                    assert options["stderr"] == (subprocess.DEVNULL if include_status else None)
                    if action == "settling-http" and gets == 2:
                        raise subprocess.TimeoutExpired(command, timeout, stderr=b"private-timeout-fixture")
                    if action == "non-http-error":
                        return subprocess.CompletedProcess(command, 1, b'{"status":"404"}',
                                                           b"private-non-http-fixture (HTTP 404)")
                    return subprocess.CompletedProcess(command, 0 if status == 200 else 1,
                                                       (response if include_status else body).encode(),
                                                       b"private-stderr-fixture (HTTP 404)")

                with patch.object(r5_oidc.subprocess, "run", side_effect=gh_request):
                    return real_github(endpoint, timeout=timeout, include_status=include_status)
        return run
    if endpoint.endswith("/attempts/1/jobs"):
        login = endpoint.split("/")[2] == "900"
        conclusion = "skipped" if login or action == "skipped" else ("failure" if action == "ambiguous" else "success")
        return {"jobs": [{"name": r5_oidc.JOB, "status": "completed", "steps": [
            {"name": r5_oidc.CHECK_STEP, "conclusion": "success"},
            {"name": r5_oidc.PUSH_STEP, "conclusion": conclusion}]}]}
    raise AssertionError(endpoint)

r5_oidc.github = github
r5_oidc.time.sleep = lambda seconds: None
''')

    def test_oidc_cli_binds_only_one_run_to_persisted_intent_and_reads_success(self):
        self.prepare_oidc_cli()
        arguments = (ENGINE, "--owner", "dusdong", "--oidc", "700", "900")
        for action in ("wrong-login-head", "published-draft", "fail-intent"):
            self.assert_cli(1, "r5_publish_main", *arguments, action=action)
            self.assertFalse((self.case / "workflow/dispatch.json").exists())
        result = self.assert_cli(0, "r5_publish_main", *arguments, action="settling-run")
        self.assertIn("读取 1/5", result.stderr)
        self.assertIn("display_title=missing, head_repository.full_name=missing", result.stderr)
        first = self.intent("main")
        self.assertEqual(r5_oidc.permit_label(901, Path(first["receipt"]).stem.removeprefix("push-"), 900),
                         (self.case / "workflow/label").read_text())
        calls = (self.case / "workflow/calls.log").read_text()
        self.assertEqual(2, calls.count("GET actions/runs/901/attempts/1\n"))
        self.assertTrue(calls.endswith("GET actions/runs/901/attempts/1\nPATCH releases/assets/800\n"), calls)
        self.assert_cli(2, "r5_publish_main", *arguments)
        for action in ("running", "ambiguous"):
            self.assert_cli(1, "r5_readback", "workflow-receipt", "--kind", "main", "--package", ENGINE, action=action)
            self.assertFalse((self.work / first["receipt"]).exists())
        self.assert_cli(1, "r5_readback", "workflow-receipt", "--kind", "main", "--package", ENGINE, action="fail-result")
        receipt = read_json(self.work / first["receipt"])
        self.assertEqual(("push-succeeded", 0), (receipt["phase"], receipt["exitCode"]))
        self.assert_cli(0, "r5_readback", "workflow-receipt", "--kind", "main", "--package", ENGINE)
        self.assertEqual("accepted", self.intent("main")["result"]["outcome"])
        self.assert_cli(2, "r5_publish_main", *arguments)
        self.assertEqual(1, (self.case / "workflow/calls.log").read_text().count("/dispatches\n"))
        self.assertEqual(0, self.upload_count())

    def test_oidc_cli_keeps_pending_intent_after_persistently_wrong_run_identity(self):
        self.prepare_oidc_cli()
        arguments = (ENGINE, "--owner", "dusdong", "--oidc", "700", "900")
        result = self.assert_cli(1, "r5_publish_main", *arguments, action="wrong-publish-run")
        self.assertIn("读取 4/5", result.stderr)
        self.assertIn("head_sha=mismatch, display_title=mismatch", result.stderr)
        self.assertNotIn("fixture", result.stderr)
        first = self.intent("main")
        self.assertEqual("901", first["workflow"]["runId"])
        self.assertNotIn("result", first)
        self.assertFalse((self.case / "workflow/label").exists())
        self.assert_cli(2, "r5_publish_main", *arguments)
        calls = (self.case / "workflow/calls.log").read_text()
        self.assertEqual(5, calls.count("GET actions/runs/901/attempts/1\n"))
        self.assertEqual(1, calls.count("/dispatches\n"))
        self.assertNotIn("PATCH", calls)
        self.assertEqual(0, self.upload_count())

    def test_oidc_cli_waits_for_unavailable_run_and_then_checks_all_identity_fields(self):
        self.prepare_oidc_cli()
        arguments = (ENGINE, "--owner", "dusdong", "--oidc", "700", "900")
        result = self.assert_cli(0, "r5_publish_main", *arguments, action="settling-http")
        self.assertIn("读取 1/5）：HTTP 404", result.stderr)
        self.assertIn("读取 2/5）：GET 超时", result.stderr)
        self.assertIn("读取 3/5）：display_title=missing, head_repository.full_name=missing", result.stderr)
        self.assertNotIn("fixture", result.stderr + result.stdout)
        calls = (self.case / "workflow/calls.log").read_text().splitlines()
        get_run = "GET actions/runs/901/attempts/1"
        self.assertEqual([get_run] * 4 + ["PATCH releases/assets/800"], calls[-5:])
        self.assertEqual(1, sum(call.endswith("/dispatches") for call in calls))
        self.assertTrue((self.case / "workflow/label").exists())
        first = self.intent("main")
        result = self.assert_cli(1, "r5_readback", "workflow-receipt", "--kind", "main", "--package", ENGINE,
                                 action="receipt-404")
        self.assertNotIn("读取", result.stderr)
        self.assertEqual(5, (self.case / "workflow/calls.log").read_text().splitlines().count(get_run))
        self.assertFalse((self.work / first["receipt"]).exists())
        self.assertEqual(0, self.upload_count())

    def test_oidc_cli_refuses_unavailable_or_unauthorized_run_without_new_dispatch(self):
        case = self.case
        for action, tries, diagnostic in (
            ("run-404", 5, "HTTP 404"), ("run-403", 1, "HTTP 403"),
            ("non-http-error", 1, "缺少有效 HTTP 响应"),
        ):
            with self.subTest(action=action):
                self.case = case / action
                self.work = self.case / "progress"
                self.work.mkdir(parents=True)
                self.prepare_oidc_cli()
                arguments = (ENGINE, "--owner", "dusdong", "--oidc", "700", "900")
                result = self.assert_cli(1, "r5_publish_main", *arguments, action=action)
                self.assertIn(diagnostic, result.stderr)
                self.assertNotIn("fixture", result.stderr + result.stdout)
                if tries == 1:
                    self.assertNotIn("HTTP 404", result.stderr)
                    self.assertNotIn("读取", result.stderr)
                first = self.intent("main")
                self.assertEqual("901", first["workflow"]["runId"])
                self.assertNotIn("result", first)
                self.assertFalse((self.case / "workflow/label").exists())
                self.assert_cli(2, "r5_publish_main", *arguments)
                calls = (self.case / "workflow/calls.log").read_text().splitlines()
                self.assertEqual(tries, calls.count("GET actions/runs/901/attempts/1"))
                self.assertEqual(1, sum(call.endswith("/dispatches") for call in calls))
                self.assertFalse(any(call.startswith("PATCH") for call in calls))
                self.assertEqual(0, self.upload_count())

    def test_oidc_cli_can_resolve_only_proven_unstarted_push(self):
        self.prepare_oidc_cli()
        arguments = (ENGINE, "--owner", "dusdong", "--oidc", "700", "900")
        self.assert_cli(1, "r5_publish_main", *arguments, action="unbound")
        for action in ("unbound", "fail-run-binding", "skipped"):
            if action != "unbound":
                self.assert_cli(0 if action == "skipped" else 1, "r5_publish_main", *arguments, action=action)
            phase = "push-skipped" if action == "skipped" else "dispatch-unbound"
            self.assertEqual(action == "skipped", (self.case / "workflow/label").exists())
            first = self.intent("main")
            self.assert_cli(2, "r5_publish_main", *arguments)
            self.assert_cli(2, "r5_readback", "workflow-receipt", "--kind", "main", "--package", ENGINE, action="skipped")
            proof = self.work / first["receipt"]
            self.assertEqual(phase, read_json(proof)["phase"])
            self.resolve_upload(0, "main", first["receipt"], "not-accepted", proof)
        self.assertEqual("retry", self.intent("main")["result"]["outcome"])
        self.assertEqual(0, self.upload_count())

    def test_oidc_runner_requires_exact_binding_and_bytes_and_pushes_one_archive(self):
        self.prepare_upload_cli()
        manifest = self.open_progress().manifest
        self.assertEqual(r5_oidc.ARCHIVES, {Path(row[kind]["path"]).name: row[kind]["sha256"]
                                           for row in manifest["packages"].values()
                                           for kind in ("archive", "symbols")})
        env = {"GITHUB_REPOSITORY": r5_oidc.REPO, "GITHUB_REF": "refs/heads/main",
               "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "901",
               "GITHUB_SHA": "a" * 40, "RUNNER_TEMP": str(self.case), "R5_LOGIN_RUN": "900", "R5_ASSET_ID": "800",
               "R5_DRAFT_ID": "700", "R5_INTENT": "b" * 32, "NUGET_API_KEY": "test-value",
               "NUGET_SYMBOL_API_KEY": "test-value", "PATH": f"{self.protocol_root}:{os.environ['PATH']}",
               "R5_TEST_CASE": str(self.case)}
        for kind in ("archive", "symbols"):
            original = self.root / manifest["packages"][ENGINE][kind]["path"]
            env["R5_ARCHIVE"] = original.name
            label = r5_oidc.permit_label(901, env["R5_INTENT"], 900)
            assets = {original.name: {"id": 800, "label": label}}

            def download(endpoint, *, download):
                self.assertEqual("releases/assets/800", endpoint)
                shutil.copyfile(original, download)

            with patch.dict(os.environ, env, clear=True), patch.object(r5_oidc, "require_login"), \
                    patch.object(r5_oidc, "check_tag"), patch.object(r5_oidc, "draft_assets", return_value=assets), \
                    patch.object(r5_oidc, "github", side_effect=download) as released, patch.object(r5_oidc.time, "sleep"):
                with patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "2"}):
                    with self.assertRaisesRegex(VerificationError, "首次手动运行"):
                        r5_oidc.prepare_runner()
                with patch.dict(os.environ, {"GITHUB_RUN_ID": "902"}):
                    with self.assertRaisesRegex(VerificationError, "未获当前 GitHub 运行"):
                        r5_oidc.prepare_runner()
                released.assert_not_called()
                r5_oidc.prepare_runner()
                path = r5_oidc.runner_archive()
                path.write_bytes(b"wrong")
                with self.assertRaisesRegex(VerificationError, "上传前归档 SHA-256 不匹配"):
                    r5_oidc.push_runner()
                shutil.copyfile(original, path)
                self.assertEqual(0, r5_oidc.push_runner())
                shutil.rmtree(path.parent)
        main, symbols = (self.case / "uploads.log").read_text().splitlines()
        self.assertIn("--source https://api.nuget.org/v3/index.json", main)
        self.assertIn("--source https://api.nuget.org/v3/index.json", symbols)
        self.assertIn("--no-symbols", main)
        self.assertNotIn("--no-symbols", symbols)
        self.assertNotIn("test-value", main + symbols)

    def test_oidc_runner_keeps_only_known_request_stages_and_http_codes(self):
        self.prepare_upload_cli()
        manifest = self.open_progress().manifest["packages"][ENGINE]
        env = {"GITHUB_REPOSITORY": r5_oidc.REPO, "GITHUB_REF": "refs/heads/main",
               "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ATTEMPT": "1",
               "RUNNER_TEMP": str(self.case), "NUGET_API_KEY": "main-SECRET-fixture",
               "NUGET_SYMBOL_API_KEY": "symbols-SECRET-fixture",
               "PATH": f"{self.protocol_root}:{os.environ['PATH']}", "R5_TEST_CASE": str(self.case)}
        control = self.case / "r5-publish"
        control.mkdir()
        cases = (
            ("archive", "oidc-main-forbidden", 17,
             ["NuGet 请求阶段 service-index", "NuGet HTTP 200 阶段 service-index",
              "NuGet 请求阶段 package-push", "NuGet HTTP 403 阶段 package-push"]),
            ("symbols", "oidc-symbol-failure", 19,
             ["NuGet 请求阶段 symbol-push", "NuGet HTTP 471 阶段 symbol-push"]),
        )
        for kind, action, code, diagnostics in cases:
            original = self.root / manifest[kind]["path"]
            shutil.copyfile(original, control / original.name)
            with patch.dict(os.environ, env | {"R5_ARCHIVE": original.name, "R5_TEST_ACTION": action}, clear=True), \
                    redirect_stdout(output := StringIO()):
                self.assertEqual(code, r5_oidc.push_runner())
            lines = output.getvalue().splitlines()
            self.assertEqual([f"开始 NuGet 提交 {original.name} SHA-256 {manifest[kind]['sha256']}",
                              *diagnostics, f"NuGet CLI 退出 {code}"], lines)
        commands = (self.case / "uploads.log").read_text()
        self.assertEqual(2, commands.count("--force-english-output"))
        self.assertNotIn("SECRET", commands)

    def proof(self, receipt, outcome, source, original=None, digest=None):
        if original is None:
            original = self.case / f"{receipt}.source.txt"
            original.write_text(f"隔离 NuGet {source}：{receipt} {outcome}\n", encoding="utf-8")
        self.proof_count += 1
        path = self.case / f"proof-{self.proof_count}.json"
        path.write_text(json.dumps({"receipt": receipt, "outcome": outcome, "source": source,
                                    "reference": original.name, "referenceSha256": digest or sha256(original)}),
                        encoding="utf-8")
        return path

    def check_non_acceptance_evidence(self, kind, receipt):
        original = self.case / "support-response.txt"
        response = f"隔离支持响应：{kind} {receipt} 未受理\n"
        original.write_text(response, encoding="utf-8")
        proof = self.proof(receipt, "not-accepted", "nuget.org-support", original)
        digest = sha256(original)
        statement = read_json(proof)
        proof.write_text(json.dumps(statement | {"referenceSha256": None}), encoding="utf-8")
        rejected = self.resolve_upload(1, kind, receipt, "not-accepted", proof)
        self.assertIn("需要脱敏原始证据的文件路径与独立 SHA-256", rejected.stderr)
        proof.write_text(json.dumps(statement), encoding="utf-8")
        original.unlink()
        rejected = self.resolve_upload(1, kind, receipt, "not-accepted", proof)
        self.assertIn("缺少独立的脱敏原始证据文件", rejected.stderr)
        original.write_text(" \n", encoding="utf-8")
        empty = self.proof(receipt, "not-accepted", "nuget.org-support", original)
        rejected = self.resolve_upload(1, kind, receipt, "not-accepted", empty)
        self.assertIn("为空或 SHA-256 不符", rejected.stderr)
        original.write_text(response + "原件变化\n", encoding="utf-8")
        mismatched = self.proof(receipt, "not-accepted", "nuget.org-support", original, digest)
        rejected = self.resolve_upload(1, kind, receipt, "not-accepted", mismatched)
        self.assertIn("为空或 SHA-256 不符", rejected.stderr)
        self.assertNotIn("result", self.intent(kind))
        original.write_text(response, encoding="utf-8")
        proof = self.proof(receipt, "not-accepted", "nuget.org-support", original, digest)
        self.resolve_upload(0, kind, receipt, "not-accepted", proof)
        result = self.intent(kind)["result"]
        self.assertEqual(("retry", str(original), digest, sha256(proof)), (
            result["outcome"], result["reference"], result["referenceSha256"], result["evidenceSha256"]))
        return proof, original

    def assert_original_reuse_rejected(self, kind, receipt, original):
        copied = self.case / "renamed-support-response.txt"
        shutil.copyfile(original, copied)
        rewritten = self.proof(receipt, "not-accepted", "nuget.org-support", copied)
        rejected = self.resolve_upload(1, kind, receipt, "not-accepted", rewritten)
        self.assertIn("该脱敏原始证据已用于较早的上传", rejected.stderr)
        self.assertNotIn("result", self.intent(kind))

    def resolve_upload(self, code, kind, receipt, outcome, proof, **options):
        return self.assert_cli(code, "r5_readback", "resolve", "--package", ENGINE, "--kind", kind,
                               "--receipt", receipt, "--outcome", outcome, "--evidence", str(proof), **options)

    def setup_symbol_upload(self):
        progress = self.open_progress()
        self.sample_main(progress, ENGINE)
        self.accept_main(progress, ENGINE)
        return progress

    def test_main_upload_survives_interruption_before_receipt_and_verifies_public_ownership(self):
        self.prepare_upload_cli()
        self.assert_cli(137, "r5_publish_main", ENGINE, "--owner", "sample-owner", action="interrupt")
        intent = self.intent("main")
        receipt = intent["receipt"]
        self.assertNotIn("result", intent)
        self.assertFalse((self.work / receipt).exists())
        self.assertIn("--no-symbols", (self.case / "uploads.log").read_text())
        self.assert_cli(2, "r5_publish_main", ENGINE, "--owner", "sample-owner")
        self.assert_cli(2, "r5_readback", "gate", "--package", ENGINE)
        self.assert_cli(1, "r5_readback", "record", "--package", ENGINE, "--kind", "main",
                        "--outcome", "retry", "--evidence", "隔离样本")
        self.assertEqual(1, self.upload_count())
        proof = self.proof(receipt, "confirmed", "nuget.org-publisher")
        self.resolve_upload(1, "main", receipt, "confirmed", proof)
        progress = self.open_progress()
        self.sample_main(progress, ENGINE, extra=True)
        self.resolve_upload(1, "main", receipt, "confirmed", proof)
        self.sample_main(progress, ENGINE)
        self.resolve_upload(1, "main", receipt, "confirmed", proof, action="wrong-owner")
        self.resolve_upload(0, "main", receipt, "confirmed", proof)
        self.assertEqual("confirmed", self.intent("main")["result"]["outcome"])
        self.assert_cli(0, "r5_readback", "verify", "--package", ENGINE, "--main-only")
        self.assert_cli(0, "r5_readback", "gate", "--package", COLLECTION)
        self.assertEqual(1, self.upload_count())

    def test_symbol_upload_survives_interruption_before_receipt_and_requires_matching_pdb(self):
        self.prepare_upload_cli()
        progress = self.setup_symbol_upload()
        self.assert_cli(137, "r5_publish_symbols", ENGINE, action="interrupt")
        intent = self.intent("symbols")
        receipt = intent["receipt"]
        self.assertNotIn("result", intent)
        self.assertFalse((self.work / receipt).exists())
        self.assertIn(".snupkg --source", (self.case / "uploads.log").read_text())
        self.assert_cli(2, "r5_publish_symbols", ENGINE)
        self.assert_cli(2, "r5_readback", "gate", "--package", ENGINE, "--symbols")
        self.assert_cli(1, "r5_readback", "record", "--package", ENGINE, "--kind", "symbols",
                        "--outcome", "retry", "--evidence", "隔离样本")
        self.assertEqual(1, self.upload_count())
        proof = self.proof(receipt, "confirmed", "nuget.org-publisher")
        self.resolve_upload(1, "symbols", receipt, "confirmed", proof)
        symbol = f"{SYMBOLS}/AutoMapper.pdb/{DEBUG_GUID}FFFFFFFF/AutoMapper.pdb"
        self.protocol.responses[symbol] = b"wrong pdb"
        self.resolve_upload(1, "symbols", receipt, "confirmed", proof)
        with ZipFile(self.archive(progress, ENGINE, "symbols")[0]) as frozen:
            self.protocol.responses[symbol] = frozen.read("lib/net8.0/AutoMapper.pdb")
        self.resolve_upload(0, "symbols", receipt, "confirmed", proof)
        self.assertEqual("confirmed", self.intent("symbols")["result"]["outcome"])
        self.assert_cli(0, "r5_readback", "verify", "--package", ENGINE)
        self.assertEqual(1, self.upload_count())

    def test_intent_write_failure_never_invokes_main_or_symbol_upload(self):
        self.prepare_upload_cli()
        failed_main = self.assert_cli(1, "r5_publish_main", ENGINE, "--owner", "sample-owner", action="fail-intent")
        self.assertIn("隔离样本意向持久化失败", failed_main.stderr)
        self.setup_symbol_upload()
        failed_symbols = self.assert_cli(1, "r5_publish_symbols", ENGINE, action="fail-intent")
        self.assertIn("隔离样本意向持久化失败", failed_symbols.stderr)
        self.assertEqual(0, self.upload_count())
        self.assertNotIn("uploadIntents", read_json(self.work / "progress.json"))

    def test_retry_requires_current_explicit_non_acceptance_and_consumes_the_permission(self):
        self.prepare_upload_cli()
        publish = ("r5_publish_main", ENGINE, "--owner", "sample-owner")
        self.assert_cli(17, *publish, action="nonzero")
        original = self.intent("main")["receipt"]
        self.resolve_upload(1, "main", original, "not-accepted", self.work / original)
        proof = self.proof(original, "not-accepted", "anonymous-404")
        self.resolve_upload(1, "main", original, "not-accepted", proof)
        self.assert_cli(2, *publish)
        proof, reference = self.check_non_acceptance_evidence("main", original)
        self.assert_cli(17, *publish, action="nonzero")
        current = self.intent("main")["receipt"]
        self.assertNotEqual(original, current)
        self.resolve_upload(1, "main", original, "not-accepted", proof)
        self.resolve_upload(1, "main", current, "not-accepted", proof)
        self.assert_original_reuse_rejected("main", current, reference)
        self.assert_cli(2, *publish)
        self.assertEqual(2, self.upload_count())

    def test_symbol_retry_requires_explicit_non_acceptance_and_still_checks_the_index(self):
        self.prepare_upload_cli()
        progress = self.setup_symbol_upload()
        self.assert_cli(17, "r5_publish_symbols", ENGINE, action="nonzero")
        original = self.intent("symbols")["receipt"]
        self.resolve_upload(1, "symbols", original, "not-accepted", self.work / original)
        _, reference = self.check_non_acceptance_evidence("symbols", original)
        symbol = f"{SYMBOLS}/AutoMapper.pdb/{DEBUG_GUID}FFFFFFFF/AutoMapper.pdb"
        self.protocol.responses[symbol] = b"visible PDB blocks another upload"
        self.assert_cli(2, "r5_publish_symbols", ENGINE)
        self.assertEqual(1, self.upload_count())
        del self.protocol.responses[symbol]
        self.assert_cli(17, "r5_publish_symbols", ENGINE, action="nonzero")
        latest = self.intent("symbols")
        self.assertNotEqual(original, latest["receipt"])
        self.assert_original_reuse_rejected("symbols", latest["receipt"], reference)
        self.assert_cli(2, "r5_publish_symbols", ENGINE)
        self.assertEqual(2, self.upload_count())

    def test_local_receipt_allows_retry_when_dotnet_could_not_start(self):
        self.prepare_upload_cli()
        publish = ("r5_publish_main", ENGINE, "--owner", "sample-owner")
        rejected = self.assert_cli(1, *publish, action="not-started")
        self.assertIn("隔离样本无法启动 dotnet", rejected.stderr)
        self.assertEqual(0, self.upload_count())
        prior = self.intent("main")["receipt"]
        local = self.work / prior
        self.assertIs(read_json(local)["started"], False)
        self.assert_cli(2, *publish)
        self.resolve_upload(0, "main", prior, "not-accepted", local)
        self.assert_cli(0, *publish)
        self.assertNotEqual(prior, self.intent("main")["receipt"])
        self.assertEqual("accepted", self.intent("main")["result"]["outcome"])
        self.assertEqual(1, self.upload_count())

    def test_success_receipt_recovers_if_result_write_fails_and_blocks_retry(self):
        self.prepare_upload_cli()
        publish = ("r5_publish_main", ENGINE, "--owner", "sample-owner")
        self.assert_cli(1, *publish, action="fail-result")
        intent = self.intent("main")
        receipt = intent["receipt"]
        self.assertNotIn("result", intent)
        local = self.work / receipt
        self.assertEqual(0, read_json(local)["exitCode"])
        proof = self.proof(receipt, "not-accepted", "nuget.org-support")
        self.resolve_upload(1, "main", receipt, "not-accepted", proof)
        self.assert_cli(2, *publish)
        self.sample_main(self.open_progress(), ENGINE)
        self.resolve_upload(0, "main", receipt, "confirmed", local)
        self.assertEqual(1, self.upload_count())

    def test_in_flight_child_keeps_the_progress_lock_after_publisher_interruption(self):
        self.prepare_upload_cli()
        process = self.upload_cli("r5_publish_main", ENGINE, "--owner", "sample-owner", action="hold", concurrent=True)
        try:
            deadline = time.monotonic() + 10
            while self.upload_count() == 0 and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(1, self.upload_count())
            blocked = self.assert_cli(1, "r5_readback", "gate", "--package", ENGINE)
            self.assertIn("temporarily unavailable", blocked.stderr.lower())
        finally:
            (self.case / "release-child").touch()
            stdout, stderr = process.communicate(timeout=15)
            (self.case / "interrupted.log").write_text(f"exit={process.returncode}\n{stdout}{stderr}", encoding="utf-8")
        self.assertEqual(137, process.returncode)
        # A new invocation continues to honor the intent after the inherited lock is released.
        deadline = time.monotonic() + 10
        while True:
            result = self.upload_cli("r5_publish_main", ENGINE, "--owner", "sample-owner")
            if result.returncode != 1 or time.monotonic() >= deadline:
                break
            time.sleep(0.02)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertEqual(1, self.upload_count())

    def test_adapter_waits_only_for_missing_or_changed_core_evidence_and_resumes(self):
        progress = self.open_progress()
        for name in (ENGINE, COLLECTION):
            self.sample_main(progress, name)
            self.accept_main(progress, name)
            self.assertEqual("verified", progress.check_main(name)["status"])
        predecessor_state = {name: progress.state["packages"][name]["main"][:] for name in (ENGINE, COLLECTION)}
        signature = self.root / progress.carried[CORE]["publicEvidence"]["signatureLog"]["path"]
        original = signature.read_bytes()
        for issue in ("missing", "changed"):
            with self.subTest(issue=issue):
                if issue == "missing":
                    signature.unlink()
                else:
                    signature.write_bytes(original + b"wrong SHA-256\n")
                progress = self.open_progress()
                self.assert_gate(progress, ADAPTER, 2, own="notVisible",
                                 blocked={CORE: {"version": "[10.5.1]", "status": "failed"}})
                core = progress.state["carried"][CORE][-1]
                try:
                    (self.case / f"core-{issue}.json").write_text(json.dumps(core, indent=2, ensure_ascii=False))
                    self.assertEqual("failed", core["status"])
                    self.assertIn({"missing": "缺少实物", "changed": "SHA-256"}[issue], core["reason"])
                    self.assertNotIn(CORE, read_json(progress.downloads)["packages"])
                finally:
                    signature.write_bytes(original)
                progress = self.open_progress()
                self.assert_gate(progress, ADAPTER, 0, own="notVisible", blocked={})
                self.assertEqual("verified", progress.state["carried"][CORE][-1]["status"])
                self.assertIn(CORE, read_json(progress.downloads)["packages"])
                self.assertEqual(predecessor_state, {name: progress.state["packages"][name]["main"]
                                                     for name in (ENGINE, COLLECTION)})
                self.assertEqual(1, self.protocol.requests.count(self.url(progress, ENGINE)))
                self.assertEqual(1, self.protocol.requests.count(self.url(progress, COLLECTION)))
        self.assertEqual([ENGINE, COLLECTION, ADAPTER], progress.manifest["publishOrder"])
        self.assertEqual(10, len(progress.carried))

    def test_content_conflict_extra_file_or_missing_dependency_rejects_version(self):
        progress = self.open_progress()
        self.sample_main(progress, ENGINE, extra=True)
        self.accept_main(progress, ENGINE)
        main = progress.check_main(ENGINE)
        self.assertEqual("failed", main["status"])
        self.assertIn('"extra": ["unexpected.txt"]', main["reason"])
        self.sample_main(progress, COLLECTION, omit_dependency=True)
        self.accept_main(progress, COLLECTION)
        collection = progress.check_main(COLLECTION)
        self.assertEqual("failed", collection["status"])
        self.assertIn('"changed": {"Du.AutoMapper.Collection.nuspec":', collection["reason"])
        self.assertNotIn(ENGINE, read_json(progress.downloads)["packages"])
        self.assertNotIn(COLLECTION, read_json(progress.downloads)["packages"])

    def test_visible_version_conflicts_until_ownership_and_content_match(self):
        progress = self.open_progress()
        self.sample_main(progress, ENGINE)
        progress.record("main", ENGINE, "duplicate", "隔离样本重复版本响应", None)
        self.assert_gate(progress, ENGINE, 2, own="conflict", blocked={})
        _, digest = self.archive(progress, ENGINE)
        with self.assertRaisesRegex(VerificationError, "实传主包 SHA-256"):
            progress.record("main", ENGINE, "confirmed", "隔离样本错误摘要", ["sample-owner"], "0" * 64)
        progress.record("main", ENGINE, "confirmed", "隔离样本确认版本归属", ["sample-owner"], digest)
        self.assert_gate(progress, ENGINE, 2, own="verified", blocked={})
        self.assert_gate(progress, COLLECTION, 0, own="notVisible", blocked={})

    def test_resume_after_acceptance_waits_for_main_and_exact_pdb_without_resubmission(self):
        progress = self.open_progress()
        self.accept_main(progress, ENGINE)
        self.assert_gate(progress, COLLECTION, 2, own="notVisible",
                         blocked={ENGINE: {"version": "[14.0.1]", "status": "pending"}})
        self.sample_main(progress, ENGINE)
        progress = self.open_progress()
        self.assert_gate(progress, COLLECTION, 0, own="notVisible", blocked={})
        self.assert_gate(progress, ENGINE, 2, own="verified", blocked={})
        self.assert_gate(progress, ENGINE, 0, own="verified", blocked=None, kind="symbols")
        _, digest = self.archive(progress, ENGINE, "symbols")
        progress.record("symbols", ENGINE, "accepted", "隔离样本符号受理", None, digest)
        self.assertEqual(2, progress.verify((ENGINE,), False))
        self.assert_gate(progress, ENGINE, 2, own="verified", blocked=None, kind="symbols")
        symbol_url = next(url for url in self.protocol.requests if url.startswith(SYMBOLS))
        self.protocol.responses[symbol_url] = b"wrong PDB bytes"
        progress = self.open_progress()
        self.assertEqual(1, progress.verify((ENGINE,), False))
        archive, _ = self.archive(progress, ENGINE, "symbols")
        with ZipFile(archive) as source:
            self.protocol.responses[symbol_url] = source.read("lib/net8.0/AutoMapper.pdb")
        progress = self.open_progress()
        self.assertEqual(0, progress.verify((ENGINE,), False))
        package = progress.state["packages"][ENGINE]
        self.assertEqual(["pending", "verified"], [row["status"] for row in package["main"]])
        symbols = package["symbols"]["lib/net8.0/AutoMapper.dll"]
        self.assertEqual(["pending", "pending", "pending", "failed", "verified"],
                         [row["status"] for row in symbols])
        self.assertIn("SHA-256 不符", symbols[-2]["reason"])
        self.assertEqual(symbols[-1]["frozenPdbSha256"], symbols[-1]["downloadSha256"])
        self.assertEqual(1, len(progress.state["external"][f"main/{ENGINE}"]))
        self.assertEqual(1, len(progress.state["external"][f"symbols/{ENGINE}"]))
        self.assertEqual(2, self.protocol.requests.count(self.url(progress, ENGINE)))
        self.assertEqual(1, len(self.protocol.nupkg_verifications))

    def test_visible_exact_pdb_prevents_symbol_push_without_a_receipt(self):
        progress = self.open_progress()
        self.sample_main(progress, ENGINE)
        self.accept_main(progress, ENGINE)
        archive, _ = self.archive(progress, ENGINE, "symbols")
        symbol_url = f"{SYMBOLS}/AutoMapper.pdb/{DEBUG_GUID}FFFFFFFF/AutoMapper.pdb"
        with ZipFile(archive) as symbols:
            self.protocol.responses[symbol_url] = symbols.read("lib/net8.0/AutoMapper.pdb")
        result = self.assert_gate(progress, ENGINE, 2, own="verified", blocked=None, kind="symbols")
        self.assertIsNone(result["symbolReceipt"])
        self.assertEqual({"lib/net8.0/AutoMapper.dll": "verified"}, result["symbols"])

    def test_queue_contains_only_three_pairs_and_three_pdb_targets(self):
        command = [sys.executable, "-B", "eng/r5_public_release.py", "--batch-root", str(self.root),
                   "--batch-sha256", self.batch_sha, "--manifest", str(self.manifest),
                   "--manifest-sha256", self.manifest_sha, "--work", str(self.work)]
        result = subprocess.run([*command, "queue"], cwd=ROOT, capture_output=True, text=True)
        (self.case / "queue.json").write_text(result.stdout)
        self.assertEqual(0, result.returncode, result.stderr)
        queue = json.loads(result.stdout)
        self.assertEqual([ENGINE, COLLECTION, ADAPTER], queue["uploadOrder"])
        self.assertEqual({ENGINE, COLLECTION, ADAPTER}, queue["archives"].keys())
        self.assertEqual(10, len(set(queue["carried"])))
        self.assertIn(CORE, queue["carried"])
        pairs = [row[kind] for row in queue["archives"].values() for kind in ("archive", "symbols")]
        self.assertEqual(6, len({row["sha256"] for row in pairs}))
        self.assertEqual(3, sum(len(row["targets"]) for row in queue["archives"].values()))
        self.assertEqual(3, len({target["pdb"] for row in queue["archives"].values()
                                for target in row["targets"].values()}))
        rejected = subprocess.run([*command, "record", "--kind", "main", "--package", CORE, "--outcome",
                                   "accepted", "--evidence", "隔离样本", "--owner", "sample-owner"], cwd=ROOT,
                                  capture_output=True, text=True)
        self.assertEqual(1, rejected.returncode)
        self.assertIn("命令所选包超出适用清单", rejected.stderr)

    def test_new_registration_requires_all_packages_and_independent_batch_identity(self):
        progress = self.open_progress()
        for name in (ENGINE, COLLECTION):
            self.sample_main(progress, name)
            self.accept_main(progress, name)
            self.assertEqual("verified", progress.check_main(name)["status"])
        digest = sha256(progress.downloads)
        with self.assertRaisesRegex(VerificationError, "缺少维护包"):
            verified_downloads(progress.downloads, digest, progress.manifest, self.manifest_sha, self.batch_sha)
        self.sample_main(progress, ADAPTER)
        self.accept_main(progress, ADAPTER)
        self.assertEqual("verified", progress.check_main(ADAPTER)["status"])
        digest = sha256(progress.downloads)
        rows = verified_downloads(progress.downloads, digest, progress.manifest, self.manifest_sha, self.batch_sha)
        self.assertEqual(13, len(rows))
        with self.assertRaisesRegex(VerificationError, "发行或冻结批次不符"):
            verified_downloads(progress.downloads, digest, progress.manifest, self.manifest_sha, "0" * 64)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--batch-sha", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args, unit_args = parser.parse_known_args()
    for key, value in vars(args).items():
        setattr(ReleaseTests, key, value.resolve() if isinstance(value, Path) else value)
    ReleaseTests.evidence.mkdir()
    unittest.main(argv=[sys.argv[0], *unit_args])
