"""对照固定 Angular 19 模板的双包前端与全公开前端匿名首次启动。"""

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime
from functools import partial
import hashlib
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
from importlib.metadata import version
from itertools import count
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import tarfile
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlsplit

from r3_template_browser import APP_CONFIG, SESSION, USER_CONFIG, response_json
from r3_template_runtime import SpaHandler, available, inventory
from r3_web_host import artifact, write_json
from r5_angular_role_edit import ANGULAR_INVENTORY, frozen_angular, serve_copy
from r5_template_role_prepare import verify_prepared
from r5_template_role_update import CHECK_ERRORS, RUNTIME, SDK, LiveRun, LiveSide
from verify import ROOT, read_json, require, sha256


TEMPLATE = "2e9536872673a7ff1986a19e798c51684d16afe5"
PAIR_FILES = "b728ead007ff14397d4fe31bfbd160790ab5d7e8d33a22047bef0830c3af6955"
PAIR_LOCK = "7de1c23211a5e91ff9c337102feba00905192fe74735a1150ddbaf62418fd096"
PAIR_STATS = "4ce5ece50131399eb9b187707361d8878bf58da2def6b60f628a204a8110bda6"
ADAPTER = "abp-ng2-module"
RESOURCES = "abp-web-resources"
FESM = f"node_modules/{ADAPTER}/fesm2022/{ADAPTER}.mjs"
CHUNK = "chunk-N46DCMOX.js"
GLOBAL = "scripts-4V6IZ3AB.js"
PACKAGES = {
    ADAPTER: ("12.1.0", "e7f2c37f8604742720f58484fb51b018291f08db",
              "c583e5e383987b2120acab39f263664c3ffa3376930dd4c29b99fea9791b7b24",
              "b8939f43e0c05afafcbfb8371c99646006565dc4a613698fd39b6c6b4aa3a2bd"),
    RESOURCES: ("6.1.0", "23775b92f2c6dd01b7402adcc0cbf5d2b92fa39b",
                "65cc604418a9dd2867676114ca39ced8edd4a0382deea207aa55f0940ddfe4a4",
                "93c66026539a1c22740b893f4ff8b6213b80e5a9ccbee247c79f651e2648a126"),
}
INIT = (APP_CONFIG, USER_CONFIG, SESSION)
LOGIN = "/account/login"
TEXT_KEYS = ("LogIn", "UserNameOrEmail", "Password")
BROWSER_OPTIONS = {"locale": "en-US", "timezone_id": "Asia/Shanghai"}
LABELS = ("public", "pair")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def manifest_digest(rows):
    return digest("".join(f"{key}\t{size}\t{hashed}\n"
                          for key, (size, hashed) in sorted(rows.items())).encode())


def file_rows(root):
    require(root.is_dir() and root.resolve() == root, f"产物目录无效：{root}")
    rows = {}
    for path in root.rglob("*"):
        require(not path.is_symlink(), f"产物含符号链接：{path}")
        if path.is_file():
            rows[path.relative_to(root).as_posix()] = (path.stat().st_size, sha256(path))
        else:
            require(path.is_dir(), f"产物含特殊文件：{path}")
    return rows


def verify_archive(path, package, expected_content):
    with tarfile.open(path, "r:gz") as archive:
        rows = {}
        for item in archive:
            member = PurePosixPath(item.name)
            require(member.parts[:1] == ("package",) and ".." not in member.parts
                    and (item.isfile() or item.isdir()), f"归档条目无效：{path.name}")
            if item.isfile():
                relative = PurePosixPath(*member.parts[1:]).as_posix()
                require(relative != "." and relative not in rows, f"归档内文件路径重复或无效：{path.name}")
                rows[relative] = (item.size, digest(archive.extractfile(item).read()))
    require(manifest_digest(rows) == expected_content, f"归档内容与登记候选不符：{path.name}")
    require(file_rows(package) == rows, f"实际安装与归档不符：{path.name}")
    return rows


def verify_pair(angular, archives, reads_path, stats_sha):
    original = angular / "dist/browser"
    rows = file_rows(original)
    require(len(rows) == 1193 and manifest_digest(rows) == PAIR_FILES, "双包 production 文件清单不符")
    lock_path = angular / "yarn.lock"
    lock = lock_path.read_bytes()
    package_manifest, angular_config = angular / "package.json", angular / "angular.json"
    require(sha256(package_manifest) == "790d231431c8f1f9b52fc3213a1d3dc7251fc75485c4b19bad813442173f719f"
            and sha256(angular_config) == "cf94a2532bab3a223f957ad71ee7446d269545698037d52560b7be830d7c9a92",
            "双包构建入口或模板包声明不符")
    dependencies = read_json(package_manifest)["dependencies"]
    packages = {}
    for name, (package_version, original_sha1, content_sha, sealed_sha) in PACKAGES.items():
        filename = f"{name}-{package_version}.tgz"
        path = archives / filename
        package = angular / "node_modules" / name
        members = verify_archive(path, package, content_sha)
        body = path.read_bytes()
        sha1 = hashlib.sha1(body).hexdigest()
        spec = f"file:../../../inputs/{filename}"
        require(dependencies.get(name) == spec and (spec + "#" + sha1).encode() in lock,
                f"冻结锁或模板声明未指向实际归档：{name}")
        lock = lock.replace((spec + "#" + sha1).encode(), (spec + "#" + original_sha1).encode())
        packages[name] = {"archive": str(path), "sha256": digest(body), "matchesSealedArchive": digest(body) == sealed_sha,
                          "integrity": "sha512-" + base64.b64encode(hashlib.sha512(body).digest()).decode(),
                          "files": len(members), "contentsSha256": content_sha,
                          "installed": str(package), "lockSha1": sha1}
    require(digest(lock) == PAIR_LOCK, "双包冻结锁与登记组合不符")
    build = angular / "dist/stats.json"
    require(sha256(build) == stats_sha, "双包同次构建 stats.json 摘要不符")
    stats = read_json(build)["outputs"]
    require(stats[CHUNK]["inputs"][FESM]["bytesInOutput"] == 8985
            and stats[CHUNK]["bytes"] == rows[CHUNK][0], "候选 FESM 未进入已登记的适配器 chunk")
    require(stats[GLOBAL]["entryPoint"] == "angular:script/global:scripts.js"
            and stats[GLOBAL]["bytes"] == rows[GLOBAL][0], "全局脚本与同次构建统计不符")
    build_options = read_json(angular_config)["projects"]["AbpProjectName"]["architect"]["build"]["options"]
    reads = [json.loads(line) for line in reads_path.read_text().splitlines()]
    require([row["path"] for row in reads] == build_options["scripts"], "全局脚本实际读取顺序与模板入口不符")
    require(len({row["pid"] for row in reads}) == 1
            and all(Path(row["cwd"]).resolve() == angular
                    and "/tools/esbuild/global-scripts.js:" in row["caller"] for row in reads),
            "全局脚本读取记录不属于本次双包构建器")
    read_evidence = []
    for row in reads:
        path = angular / row["path"]
        require(path.resolve() == path == Path(row["realpath"]).resolve()
                and (row["bytes"], row["sha256"]) == (path.stat().st_size, sha256(path)),
                f"同次全局脚本读取与实装不符：{row['path']}")
        read_evidence.append({key: row[key] for key in ("path", "bytes", "sha256")})
    evidence = {"packages": packages, "lock": artifact(lock_path, angular), "buildStats": artifact(build, angular),
                "globalReadsEvidenceSha256": sha256(reads_path),
                "angularConfig": artifact(angular_config, angular), "packageManifest": artifact(package_manifest, angular), "globalReads": read_evidence,
                "productionSha256": PAIR_FILES, "productionFiles": len(rows),
                "adapter": {"input": FESM, "inputSha256": sha256(angular / FESM), "chunk": CHUNK,
                            "sha256": rows[CHUNK][1], "bytesInOutput": 8985}}
    return original, {"files": {key: item[1] for key, item in rows.items()}}, evidence


class EntryScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and (source := dict(attrs).get("src")):
            self.paths.append("/" + source.lstrip("/"))


def endpoint(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}", parts.path


def init_headers(request):
    headers = request.all_headers()
    tenant = [headers[key] for key in ("abp.tenantid", "abp-tenantid") if key in headers]
    cookies = {part.partition("=")[0].strip().lower() for part in headers.get("cookie", "").split(";")}
    return {"authorization": "authorization" in headers, "cookie": "cookie" in headers,
            "identityCookie": bool(cookies & {"abp.authtoken", "abp.authrefreshtoken", "abp-tenantid",
                                             ".aspnetcore.identity.application"}),
            "tenant": "absent" if not tenant else "empty" if all(item in ("", "null") for item in tenant) else "set"}


def null_fields(values, keys):
    return {key: "omitted" if key not in values else "null" if values[key] is None else "non-null" for key in keys}


def observed_user_config(user_config):
    config_session = user_config["session"]
    provider = user_config["clock"]["provider"]
    require(provider in ("unspecifiedClockProvider", "utcClockProvider", "localClockProvider"), "GetAll 时钟类型不符")
    localized = user_config["localization"]
    language = localized["currentLanguage"]["name"]
    require(isinstance(language, str) and re.fullmatch(r"[a-zA-Z0-9-]+", language), "GetAll 未提供有效当前语言")
    source = localized["values"]["AbpProjectName"]
    texts = {key: source[key] for key in TEXT_KEYS}
    require(all(isinstance(text, str) and text.strip() for text in texts.values()), "GetAll 登录本地化值缺失")
    user = {"identity": null_fields(config_session, ("userId", "tenantId", "impersonatorUserId", "impersonatorTenantId")),
            "side": "Host" if type(config_session["multiTenancySide"]) is int
            and config_session["multiTenancySide"] == 2 else "unexpected",
            "clockProvider": provider, "language": language, "texts": texts}
    if provider == "utcClockProvider":
        zone = user_config["timing"]["timeZoneInfo"]["iana"]["timeZoneId"]
        require(isinstance(zone, str) and zone.strip(), "GetAll 缺少实际读取的 IANA 时区")
        user["ianaTimeZone"] = zone
    return user


def observed_session(session):
    app = session["application"]
    release = app["releaseDate"]
    require(isinstance(release, str) and "T" in release and datetime.fromisoformat(release),
            "Session 未提供有效 application.releaseDate")
    require(app["version"] == "9.3.0" and app["features"] == {}, "Session 不符合固定模板应用元数据")
    return {"identity": null_fields(session, ("user", "tenant")),
            "application": {key: app[key] for key in ("version", "releaseDate", "features")}}


def check_asset(row, expected, origin, path):
    require(expected is not None and row["origin"] == origin and row["method"] == "GET" and row["status"] == 200
            and row["finished"] and not row["redirected"] and row.get("sha256") == expected,
            f"浏览器实收静态字节、来源或状态不符：{path}")


def check_bootstrap(evidence, files, scripts, config, frontend, host):
    require(not evidence["pageErrors"] and not evidence["webSockets"] and not evidence["unexpectedRequests"],
            "出现页面异常、WebSocket 或超出匿名范围的请求")
    documents = evidence["documents"]
    require(len(documents) == 1 and documents[0]["path"] == "/" and not documents[0]["redirected"],
            "根路径须直接加载唯一的主文档，禁止 HTTP 重定向或第二次文档加载")
    document = documents[0]
    check_asset(document, files["index.html"], frontend, "/")
    require(evidence["navigations"] and evidence["navigations"][0] == frontend + "/"
            and evidence["exactFinalRoute"] and evidence["finalUrl"] == frontend + LOGIN
            and evidence["navigations"][-1] == frontend + LOGIN,
            "浏览器未从根路径在原文档内到达登录页")
    seen = evidence["scripts"]
    require(set(scripts) <= {row["path"] for row in seen}, "浏览器缺少 production 入口、全局脚本或候选 chunk")
    for row in seen:
        path = row["path"]
        check_asset(row, files.get(path.lstrip("/")), frontend, path)
    calls = evidence["initialization"]
    require([row["path"] for row in calls] == list(INIT), "三个初始化 GET 缺失、重复或顺序不符")
    order = [document["responseSequence"]]
    for row in calls:
        order.extend((row["sequence"], row["responseSequence"]))
    require(all(type(item) is int for item in order)
            and all(before < after for before, after in zip(order, order[1:])), "初始化请求未按实际响应顺序衔接")
    check_asset(calls[0], files[APP_CONFIG.lstrip("/")], frontend, APP_CONFIG)
    require(evidence["config"] == config and config["appBaseUrl"] == frontend
            and config["remoteServiceBaseUrl"] == host, "浏览器应用配置与服务副本不符")
    for call in calls:
        headers = call["headers"]
        require(not headers["authorization"] and not headers["identityCookie"] and headers["tenant"] != "set",
                f"匿名请求携带有效身份标记：{call['path']}")
    for call in calls[1:]:
        require(call["origin"] == host and call["method"] == "GET" and call["status"] == 200
                and call["finished"] and not call["redirected"] and call["cors"] == frontend and call.get("success"),
                f"未收到成功的 R5 匿名响应：{call['path']}")
    require(all(row["origin"] == host and row["path"] in INIT[1:] and row["status"] == 204
                for row in evidence["preflight"]), "CORS 预检来源、路径或状态不符")
    user, session = evidence["userConfig"], evidence["session"]
    require(user["side"] == "Host" and all(state in ("null", "omitted") for state in
            (*user["identity"].values(), *session["identity"].values())), "实际响应带有用户、租户或模拟身份")
    form = evidence["form"]
    texts = user["texts"]
    require(all(form["visible"].values()) and form["empty"] and
            form["texts"] == {"title": texts["LogIn"], "button": texts["LogIn"],
                              "username": texts["UserNameOrEmail"], "password": texts["Password"]},
            "登录页可见控件、空表单或文字与实际 GetAll 不符")


def comparable(evidence):
    user = evidence["userConfig"]
    return {"identity": {"side": user["side"], **{key: None for key in
                        (*user["identity"], *evidence["session"]["identity"])}},
            "clockProvider": user["clockProvider"], "ianaTimeZone": user.get("ianaTimeZone"),
            "language": user["language"], "texts": user["texts"], "application": evidence["session"]["application"],
            "localeMappings": evidence["config"]["localeMappings"]}


def finish_bootstrap(report):
    sides = report["sides"]
    states = [record["status"] for record in sides.values()]
    if report.get("inputError") or "input_incomparable" in states:
        status = "input_incomparable"
    elif report.get("cleanupError"):
        status = "cleanup_failed"
    elif states == ["passed", "passed"]:
        public, pair = (comparable(sides[label]["observation"]) for label in LABELS)
        differences = [key for key in public if public[key] != pair[key]]
        report["comparison"] = {"status": "different" if differences else "equal", "differentFields": differences}
        status = "cross_side_difference" if differences else "passed"
    else:
        status = "both_failed" if states.count("failed") == 2 else "one_side_failed"
    report.setdefault("comparison", {"status": "not_run", "reason": "需要两侧独立通过和完整的共享运行证据"})
    report.update(status=status, exitCode=0 if status == "passed" else 1)
    return report["exitCode"]


class StartupTraffic:
    def __init__(self, page, evidence):
        self.page, self.evidence = page, evidence
        self.sequence = count(1)
        self.requests, self.responses, self.finished, self.failed = {}, {}, set(), set()
        self.events = {"preflight": [], "navigations": [], "pageErrors": [], "webSockets": []}
        page.on("request", lambda request: self.requests.update({request: next(self.sequence)}))
        page.on("response", lambda response: self.responses.update({response.request: (response, next(self.sequence))}))
        page.on("requestfinished", lambda request: self.finished.add(request))
        page.on("requestfailed", lambda request: self.failed.add(request))
        page.on("framenavigated", self.navigation)
        page.on("pageerror", lambda error: self.events["pageErrors"].append(
            {"type": getattr(error, "name", type(error).__name__)}))
        page.on("websocket", lambda socket: self.events["webSockets"].append(endpoint(socket.url)))
        self.cdp = page.context.new_cdp_session(page)
        self.options = {}
        self.cdp.on("Network.requestWillBeSent", self.preflight)
        self.cdp.on("Network.responseReceived", self.preflight_response)
        self.cdp.send("Network.enable")

    def preflight(self, event):
        request = event["request"]
        if request["method"] == "OPTIONS":
            origin, path = endpoint(request["url"])
            row = {"origin": origin, "path": path, "method": "OPTIONS", "status": None}
            self.options[event["requestId"]] = row
            self.events["preflight"].append(row)

    def preflight_response(self, event):
        if row := self.options.get(event["requestId"]):
            response = event["response"]
            row["status"] = response["status"]

    def navigation(self, frame):
        if frame == self.page.main_frame:
            origin, path = endpoint(frame.url)
            self.events["navigations"].append(origin + path)

    def wait_for_required(self, frontend, host, scripts):
        required = {(frontend, "/"), (frontend, APP_CONFIG), (host, USER_CONFIG), (host, SESSION),
                    *((frontend, script) for script in scripts)}

        def ready(_request=None):
            completed = {endpoint(request.url) for request in self.finished if request.method == "GET"}
            return required <= completed and all(
                request.resource_type != "script" or request in self.finished or request in self.failed
                for request in self.requests)

        if not ready():
            self.page.wait_for_event("requestfinished", predicate=ready, timeout=8000)

    def collect(self, frontend, host):
        from playwright.sync_api import Error

        # 读取 Playwright 响应正文时，新网络事件仍可能送达。证据以开始读取前的窗口为准。
        requests, responses = tuple(self.requests.items()), self.responses.copy()
        finished, failed = self.finished.copy(), self.failed.copy()
        evidence = self.evidence
        evidence.update(documents=[], scripts=[], initialization=[], unexpectedRequests=[],
                        preflight=[row.copy() for row in self.events["preflight"]],
                        navigations=list(self.events["navigations"]), pageErrors=list(self.events["pageErrors"]),
                        webSockets=list(self.events["webSockets"]))
        evidence["pendingResourceTypes"] = sorted(
            request.resource_type for request, _ in requests if request not in finished and request not in failed)
        bodies = {}
        for request, order in requests:
            origin, path = endpoint(request.url)
            response, response_order = responses.get(request, (None, None))
            documented = request.is_navigation_request() and request.frame == self.page.main_frame
            script = request.resource_type == "script"
            row = {"origin": origin, "path": path, "method": request.method, "sequence": order,
                   "responseSequence": response_order, "status": response.status if response else None,
                   "finished": request in finished, "redirected": request.redirected_from is not None}
            if documented:
                evidence["documents"].append(row)
            if script:
                evidence["scripts"].append(row)
            if request.method != "OPTIONS" and path in INIT:
                evidence["initialization"].append(row)
            elif (origin == host and (path not in INIT or request.method != "OPTIONS")
                  or request.method not in ("GET", "OPTIONS", "HEAD")
                  or request.resource_type in ("xhr", "fetch", "eventsource", "websocket") and path not in INIT
                  or re.search(r"(?i)(?:^|/)(?:signalr|negotiate)(?:/|$)", path) and not script):
                evidence["unexpectedRequests"].append(row)
            if not (documented or script or path in INIT) or request.method == "OPTIONS":
                continue
            try:
                if path in INIT:
                    row["headers"] = init_headers(request)
                if response and response.ok and row["finished"]:
                    if path in INIT[1:]:
                        row["cors"] = response.header_value("Access-Control-Allow-Origin")
                        bodies[path] = response_json(response, frontend)
                        row["success"] = True
                    else:
                        row["sha256"] = digest(response.body())
                        if path == APP_CONFIG:
                            bodies[path] = response_json(response, wrapped=False)
            except (Error, *CHECK_ERRORS) as failure:
                row["captureError"] = type(failure).__name__
            if request in failed:
                row["failedRequest"] = True
        if APP_CONFIG in bodies:
            config = bodies[APP_CONFIG]
            evidence["config"] = {key: config[key] for key in ("appBaseUrl", "remoteServiceBaseUrl", "localeMappings")}
        if USER_CONFIG in bodies:
            evidence["userConfig"] = observed_user_config(bodies[USER_CONFIG])
        if SESSION in bodies:
            evidence["session"] = observed_session(bodies[SESSION])


def read_form(page):
    form = page.locator(".login-card-body")
    locators = {"title": form.locator("h4"), "button": form.locator("button[type=submit]"),
                "username": form.locator("input[name=userNameOrEmailAddress]"),
                "password": form.locator("input[type=password][name=password]")}
    for locator in locators.values():
        locator.wait_for(state="visible")
    return {"visible": {key: locator.is_visible() for key, locator in locators.items()},
            "empty": not locators["username"].input_value() and not locators["password"].input_value(),
            "texts": {key: locator.get_attribute("placeholder") if key in ("username", "password")
                      else locator.inner_text().strip() for key, locator in locators.items()}}


def run_browser(browser, frontend, host, original, files, expected, label, evidence):
    from playwright.sync_api import Error

    entry = EntryScripts()
    entry.feed((original / "index.html").read_text())
    require(sum(path.startswith("/main-") for path in entry.paths) == 1
            and sum(path.startswith("/scripts-") for path in entry.paths) == 1,
            "每侧 index 须引用一个主入口和一个全局脚本")
    if label == "pair":
        require("/" + GLOBAL in entry.paths, "双包 index 缺少资源包生成的全局脚本")
        entry.paths.append("/" + CHUNK)
    with browser.new_context(**BROWSER_OPTIONS) as context:
        evidence["initialCookieCount"] = len(context.cookies())
        require(not evidence["initialCookieCount"], "新匿名上下文存在 Cookie")
        page = context.new_page()
        page.set_default_timeout(16000)
        traffic = StartupTraffic(page, evidence)
        try:
            page.goto(frontend + "/", wait_until="domcontentloaded")
            page.wait_for_url(frontend + LOGIN, wait_until="domcontentloaded")
            evidence["form"] = read_form(page)
            traffic.wait_for_required(frontend, host, entry.paths)
        except Error as failure:
            evidence["browserError"] = type(failure).__name__
        finally:
            origin, path = endpoint(page.url)
            evidence["finalUrl"] = origin + path
            evidence["exactFinalRoute"] = page.url == frontend + LOGIN
            traffic.collect(frontend, host)
    check_bootstrap(evidence, files, entry.paths, expected, frontend, host)
    require("browserError" not in evidence, "浏览器导航或登录表单观察未完成")


class BootstrapRun(LiveRun):
    observe_browser = staticmethod(run_browser)
    finish_report = staticmethod(finish_bootstrap)
    static_server = ThreadingHTTPServer

    def __init__(self, args):
        super().__init__(args, sides={label: {"status": "not_run"} for label in LABELS})
        self.report.update(workflow="angular19-anonymous-bootstrap", browserOptions=BROWSER_OPTIONS,
                           cwd=str(Path.cwd()), argv=sys.argv, python=sys.version.split()[0],
                           playwright=version("playwright"))
        self.frontends = {"public": args.public_port, "pair": args.pair_port}

    def backend_input(self):
        launches = verify_prepared(self.prepared, self.args.report_sha256, only_release="r5")["r5"]
        sealed = read_json(self.prepared / "report.json")
        toolchain, template = sealed["toolchain"], sealed["template"]
        require(platform.system() == "Darwin" and platform.machine() == "arm64"
                and toolchain["sdk"] == SDK and toolchain["runtimeConfigVersion"] == RUNTIME
                and toolchain["targetFramework"] == "net10.0" and template["commit"] == TEMPLATE,
                "R5 准备工具链、平台或模板身份不符")
        self.dotnet, self.migration_ids = toolchain["dotnet"], template["migrationIds"]
        self.report.update(platform=platform.platform(), toolchain=toolchain, template=template, preparations=launches)
        self.report["profileSources"] = [artifact(ROOT / "eng" / name, ROOT) for name in (
            "r5_angular_anonymous_bootstrap.py", "r5_angular_role_edit.py", "r5_angular_prepare.py",
            "r5_template_role_update.py", "r5_template_role_prepare.py", "r3_template_browser.py",
            "r3_template_runtime.py", "r3_template_net9_runtime.py", "r3_template_net10_runtime.py",
            "r3-template-observer/Observer.csproj", "r3-template-observer/StartupHook.cs")]
        return launches

    def frontend_input(self, label):
        args = self.args
        if label == "pair":
            return verify_pair(args.pair_build, args.pair_inputs, args.global_reads, args.stats_sha256)
        original, files = frozen_angular(args.public_source)
        return original, files, {
            "manifest": artifact(args.public_source / "angular-production-files.json", args.public_source),
            "productionSha256": ANGULAR_INVENTORY, "productionFiles": len(files["files"])}

    @contextmanager
    def dedicated_sql(self):
        with self.sql_server():
            resource = self.report["sqlResource"]
            _, mounts = self.command(["docker", "inspect", "--format", "{{json .Mounts}}", resource["containerId"]])
            resource["volumes"] = [item["Name"] for item in json.loads(mounts) if item["Type"] == "volume"]
            try:
                yield
            finally:
                resource["databaseBeforeRemoval"] = self.database.query("master", """
SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name
""")

    def observe_side(self, browser, label, source, host, record):
        original, input_files, _ = source
        port = self.frontends[label]
        frontend = f"http://127.0.0.1:{port}"
        with TemporaryDirectory(prefix=f"serve-{label}-", dir=self.root) as workspace:
            output = Path(workspace) / "browser"
            files, changes = serve_copy(original, input_files, output, frontend, host)
            config = read_json(output / APP_CONFIG.lstrip("/"))
            selected = {key: config[key] for key in ("appBaseUrl", "remoteServiceBaseUrl", "localeMappings")}
            manifest = self.root / f"{label}-served-files.json"
            write_json(manifest, files)
            record["frontend"] = {"address": frontend, "original": str(original), "served": artifact(manifest, self.root),
                                  "inventorySha256": files["sha256"], "configChanges": changes}
            with self.static_server(("127.0.0.1", port), partial(SpaHandler, directory=str(output))) as server:
                self.owned_ports.append(port)
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                record["phase"] = "browser"
                try:
                    self.observe_browser(browser, frontend, host, output, files["files"], selected, label,
                                         record.setdefault("observation", {}))
                    require(inventory(output, include_app_data=True) == files, "运行时服务副本改变")
                finally:
                    server.shutdown()
                    thread.join()

    def shared_runtime(self, launches, sources):
        from playwright.sync_api import Error, sync_playwright

        shared = self.report["shared"] = {}
        side = LiveSide(self, "r5", launches, shared)
        side.migrate()
        shared["databaseBeforeBrowser"] = self.database_state(side)
        shared["connectionTarget"] = {"endpoint": self.report["sqlResource"]["endpoint"], "database": side.name}
        static = side.root / "api-only.staticwebassets.runtime.json"
        write_json(static, {"ContentRoots": [], "Root": {"Children": {}}})
        shared["hostStaticAssets"] = artifact(static, side.root)
        origins = [f"http://127.0.0.1:{self.frontends[label]}" for label in LABELS]
        with side.host_process(self.args.host_port, origins[0], ",".join(origins),
                               ASPNETCORE_STATICWEBASSETS=str(static)):
            self.owned_ports.append(self.args.host_port)
            self.verify_host_database(side, shared)
            with sync_playwright() as driver:
                browser = driver.chromium.launch(executable_path=str(self.args.chrome), headless=True)
                try:
                    cdp = browser.new_browser_cdp_session()
                    processes = cdp.send("SystemInfo.getProcessInfo")["processInfo"]
                    cdp.detach()
                    pid = [item["id"] for item in processes if item["type"] == "browser"]
                    require(len(pid) == 1, "无法确认本轮 Chrome 进程")
                    self.report["browser"] = {"version": browser.version, "pid": pid[0],
                                              "executable": str(self.args.chrome)}
                    for label, source in sources.items():
                        current = self.database_state(side)
                        require(current == shared["databaseBeforeBrowser"], "浏览器启动前共享库状态改变")
                        record = self.report["sides"][label]
                        record.update(hostPid=side.pid, databaseIdentity=side.identity, phase="serve")
                        try:
                            self.observe_side(browser, label, source, side.base, record)
                            self.verify_host_database(side, record)
                            record.update(status="passed", phase="complete")
                        except (Error, *CHECK_ERRORS) as failure:
                            record.update(status="failed" if record["phase"] == "browser" else "input_incomparable",
                                          reason=(type(failure).__name__ if isinstance(failure, Error)
                                                  else self.redact(str(failure))))
                        self.save()
                finally:
                    browser.close()
            shared["finalIdentity"] = self.database.identify(side.name)
            require(shared["finalIdentity"] == side.identity, "浏览器运行后共享库身份改变")
            shared["databaseAfterBrowser"] = self.database_state(side)
            require(shared["databaseAfterBrowser"] == shared["databaseBeforeBrowser"], "浏览器运行后共享库状态改变")

    def database_state(self, side):
        return self.database.identify(side.name)

    def verify_host_database(self, side, record):
        pass

    def cleanup(self):
        resource = self.report.get("sqlResource", {})
        sql_endpoint = resource.get("endpoint")
        cleanup = self.report["cleanup"] = {
            "temporaryDirectoriesRemaining": [item.name for item in self.root.rglob("*") if item.is_dir()
                                              and item.name.startswith(("serve-", "home-"))],
            "portsReleased": {port: available(port) for port in self.owned_ports}}
        if sql_endpoint:
            cleanup["sqlPortReleased"] = available(int(sql_endpoint.rsplit(":", 1)[1]))
        if resource.get("containerId"):
            cleanup["sqlRemoved"] = resource.get("removed") is True
            _, remaining = self.command(["docker", "volume", "ls", "--format", "{{.Name}}"])
            cleanup["sqlVolumesRemoved"] = ("volumes" in resource
                                            and not set(resource["volumes"]) & set(remaining.splitlines()))
        browser = self.report.get("browser")
        if browser:
            cleanup["chromeStopped"] = False
            try:
                os.kill(browser["pid"], 0)
            except ProcessLookupError:
                cleanup["chromeStopped"] = True
        if "shared" in self.report:
            cleanup["processExitCodes"] = {entry: launch["exitCode"] for entry, launch
                                           in self.report["shared"].get("processes", {}).items()}
        require(not cleanup["temporaryDirectoriesRemaining"] and all(cleanup["portsReleased"].values())
                and all(value for key, value in cleanup.items() if key in ("sqlPortReleased", "sqlRemoved",
                                                                           "sqlVolumesRemoved", "chromeStopped"))
                and all(code is not None for code in cleanup.get("processExitCodes", {}).values()),
                "本轮资源清理读回未通过")

    def execute(self):
        from playwright.sync_api import Error
        import pymssql

        sources = {}
        self.owned_ports = []
        try:
            for label in LABELS:
                record = self.report["sides"][label]
                try:
                    sources[label] = self.frontend_input(label)
                    record.update(status="ready", input=sources[label][2])
                except (*CHECK_ERRORS, tarfile.TarError) as failure:
                    record.update(status="input_incomparable", reason=self.redact(str(failure)), phase="input")
            if sources:
                launches = self.backend_input()
                require(available(self.args.host_port), "本轮共享 Host 端口已被占用")
                self.build_observer()
                with self.dedicated_sql():
                    self.shared_runtime(launches, sources)
                require(self.report["sqlResource"]["databaseBeforeRemoval"] ==
                        [{"name": self.report["shared"]["database"]}], "专用实例应只包含本轮测试库")
                require(verify_prepared(self.prepared, self.args.report_sha256, only_release="r5")["r5"] == launches,
                        "本轮执行后封存 R5 入口改变")
                self.report["sealedOutputsUnchanged"] = True
        except (Error, pymssql.Error, *CHECK_ERRORS) as failure:
            self.report["inputError"] = (type(failure).__name__ if isinstance(failure, Error) else self.redact(str(failure)))
            for record in self.report["sides"].values():
                if record["status"] != "input_incomparable":
                    record.update(status="input_incomparable", reason=self.report["inputError"], phase="shared")
        finally:
            for label, source in sources.items():
                try:
                    require(self.frontend_input(label) == source, "本轮执行后原前端或输入证据改变")
                    self.report["sides"][label]["originalUnchanged"] = True
                except (*CHECK_ERRORS, tarfile.TarError) as failure:
                    self.report["sides"][label].update(status="input_incomparable", phase="recheck",
                                                       reason=self.redact(str(failure)))
            try:
                self.cleanup()
            except CHECK_ERRORS as failure:
                self.report["cleanupError"] = self.redact(str(failure))
            self.finish_report(self.report)
            self.save()
        print(f"{self.report['status']} · {self.root / 'report.json'}")
        return self.report["exitCode"]


def parse_arguments(description):
    parser = argparse.ArgumentParser(description=description)
    for name in ("output", "prepared", "chrome", "public-source", "pair-build", "pair-inputs", "global-reads"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("host-port", "public-port", "pair-port"):
        parser.add_argument(f"--{name}", type=int, required=True)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--stats-sha256", default=PAIR_STATS)
    args = parser.parse_args()
    ports = (args.host_port, args.public_port, args.pair_port)
    if len(set(ports)) != 3 or not all(1024 <= port <= 65535 for port in ports):
        parser.error("需要三个不同的非系统环回端口")
    inputs = ("prepared", "chrome", "public_source", "pair_build", "pair_inputs", "global_reads")
    for name in inputs:
        setattr(args, name, getattr(args, name).resolve())
    if args.output.exists() or args.output.is_symlink() or any(
            args.output.resolve().is_relative_to(getattr(args, name)) for name in inputs):
        parser.error("证据目录必须尚不存在且位于输入目录之外")
    return args


def main():
    return BootstrapRun(parse_arguments(__doc__)).execute()


if __name__ == "__main__":
    raise SystemExit(main())
