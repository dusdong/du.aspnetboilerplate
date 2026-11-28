"""用真实模板弹窗对照固定 Angular 19 双包前端和全公开前端的匿名租户切换。"""

import base64
from http.server import ThreadingHTTPServer
from itertools import count
import json
import os
import re
import sys
import time

from r3_template_browser import APP_CONFIG, SESSION, USER_CONFIG
from r5_angular_anonymous_bootstrap import (
    BROWSER_OPTIONS, CHUNK, GLOBAL, INIT, LABELS, LOGIN, BootstrapRun, EntryScripts,
    check_asset, digest, endpoint, observed_session, observed_user_config,
    parse_arguments, read_form,
)
from verify import require


SELECT = "/api/services/app/Account/IsTenantAvailable"
PHASES = ("initialHost", "tenant", "returnHost")
NAVIGATION_TYPES = {"navigate", "reload", "back_forward", "prerender"}
TENANT_TEXTS = ("CurrentTenant", "NotSelected", "Change", "ChangeTenant",
                "TenancyName", "LeaveEmptyToSwitchToHost", "Save")
AUTH_COOKIES = {"abp.authtoken", "abp.authrefreshtoken", "abp.encrauthtoken",
                "enc_auth_token", ".aspnetcore.identity.application", ".aspnetcore.identity.external"}
EMPTY = ("null", "omitted")


def value_state(value, expected):
    if value is None:
        return "omitted"
    if value in ("", "null"):
        return "empty"
    return "seed" if value == str(expected) else "other"


def request_identity(headers, seed):
    headers = {key.lower(): str(value) for key, value in headers.items()}
    cookies = {item.partition("=")[0].strip().lower() for item in headers.get("cookie", "").split(";")}
    return {"dot": value_state(headers.get("abp.tenantid"), seed["id"]),
            "dash": value_state(headers.get("abp-tenantid"), seed["id"]),
            "authorization": "authorization" in headers or "proxy-authorization" in headers,
            "authCookie": has_auth_cookie(cookies)}


def has_auth_cookie(names):
    return any(re.sub(r"c[0-9]+$", "", name.lower()) in AUTH_COOKIES for name in names)


def observed_config(result, seed):
    row = observed_user_config(result)
    session = result["session"]
    row["side"] = session["multiTenancySide"] if type(session["multiTenancySide"]) is int else "invalid"
    row["tenantMatchesSeed"] = type(session.get("tenantId")) is int and session["tenantId"] == seed["id"]
    if row["tenantMatchesSeed"]:
        row["tenantId"] = session["tenantId"]
    row["texts"].update({key: result["localization"]["values"]["AbpProjectName"][key] for key in TENANT_TEXTS})
    return row


def observed_identity(result, seed):
    row = observed_session(result)
    tenant = result.get("tenant")
    row["tenant"] = ({key: tenant.get(key) if type(tenant.get(key)) is type(value)
                       and tenant.get(key) == value else "other" for key, value in seed.items()}
                     if isinstance(tenant, dict) else None)
    return row


def one_request(rows, path, method):
    candidates = [row for row in rows if row["path"] == path and row["method"] == method]
    require(len(candidates) == 1, f"{method} {path} 请求缺失或重复")
    return candidates[0]


def response_for(row):
    responses = row["responses"]
    require(len(responses) == 1, f"{row['path']} 响应缺失或重复")
    response, = responses
    require(response["requestId"] == row["requestId"] and response["loaderId"] == row["loaderId"],
            f"{row['path']} 响应的请求或文档身份不符")
    require(response["sequence"] > row["sequence"] and row["finishedSequence"] > response["sequence"]
            and not row["failed"] and not row["redirected"], f"{row['path']} 请求未正常完成")
    return row | response | {"finished": True}


def check_headers(row, tenant):
    headers = row["headers"]
    require(row["wireHeadersObserved"], f"{row['path']} 缺少实际发送的请求头")
    require(not headers["authorization"] and not headers["authCookie"], f"{row['path']} 带有认证标记")
    require(headers["dash"] in (("seed",) if tenant else ("empty", "omitted")),
            f"{row['path']} 的 Abp-TenantId 与当前阶段不符")
    dot = ("seed",) if tenant else ("empty",)
    if row["path"] == SESSION:
        dot += ("omitted",)
    require(headers["dot"] in dot, f"{row['path']} 的 Abp.TenantId 与当前阶段不符")


def check_business(row, frontend, host):
    require(row["origin"] == host and row["status"] == 200 and row["cors"] == frontend
            and row.get("success") is True, f"{row['path']} 缺少登记 Host、CORS 或业务成功证据")


def check_ui(phase, texts, seed, selected):
    form = phase["form"]
    require(all(form["visible"].values()) and form["empty"] and
            form["texts"] == {"title": texts["LogIn"], "button": texts["LogIn"],
                              "username": texts["UserNameOrEmail"], "password": texts["Password"]},
            "登录页的可见空表单或本地化不符")
    expected_tenant = seed["tenancyName"] if selected else texts["NotSelected"]
    label = f'{texts["CurrentTenant"]}: {expected_tenant} ( {texts["Change"]} )'
    label = label.replace("( ", "(").replace(" )", ")")
    ui = phase["tenantUi"]
    require(ui["label"].replace("( ", "(").replace(" )", ")") == label
            and ui["change"] == texts["Change"]
            and ui["strong"] == (seed["tenancyName"] if selected else None)
            and ui["title"] == (seed["name"] if selected else None), "当前租户展示与 GetAll 或种子不符")
    if phase["name"] != PHASES[-1]:
        modal = phase["dialog"]
        require(modal["input"] == (seed["tenancyName"] if selected else "")
                and modal["texts"] == {key: texts[key] for key in TENANT_TEXTS[3:]},
                "租户弹窗的预填值或本地化不符")


def check_phase(phase, evidence, files, scripts, config, frontend, host, seed):
    name, loader = phase["name"], phase["loaderId"]
    selected = name == "tenant"
    require(phase["route"] == frontend + LOGIN, f"{name} 未到达登录路由")
    expected_navigation = "navigate" if name == PHASES[0] else "reload"
    require(phase.get("navigationLoaderId") == loader and phase.get("navigationType") == expected_navigation,
            f"{name} 的实际主文档导航类型须为 {expected_navigation}")
    rows = [row for row in evidence["requests"] if row["loaderId"] == loader]
    documents = [row for row in rows if row["kind"] == "Document"]
    require(len(documents) == 1, f"{name} 主文档缺失或重复")
    document, = documents
    path = "/" if name == PHASES[0] else LOGIN
    require(document["path"] == path, f"{name} 的主文档路径不符")
    check_asset(response_for(document), files["index.html"], frontend, path)
    assets = [row for row in rows if row["kind"] == "Script"]
    require(set(scripts) <= {row["path"] for row in assets}, f"{name} 缺少 production 入口或候选 chunk")
    for row in assets:
        check_asset(response_for(row), files.get(row["path"].lstrip("/")), frontend, row["path"])
    calls = [one_request(rows, target, "GET") for target in INIT]
    replies = [response_for(row) for row in calls]
    ordering = [document["responses"][0]["sequence"]]
    for row, reply in zip(calls, replies):
        # Chrome 的 loadingFinished 通知可晚于回调触发的下一条请求。
        ordering.extend((row["sequence"], reply["sequence"]))
        check_headers(row, selected)
    require(all(a < b for a, b in zip(ordering, ordering[1:])), f"{name} 初始化实收顺序不符")
    check_asset(replies[0], files[APP_CONFIG.lstrip("/")], frontend, APP_CONFIG)
    require(replies[0]["config"] == config, f"{name} 应用配置与服务副本不符")
    for row in replies[1:]:
        check_business(row, frontend, host)
    user, session = replies[1]["userConfig"], replies[2]["session"]
    require(all(user["identity"][key] in EMPTY for key in ("userId", "impersonatorUserId", "impersonatorTenantId"))
            and session["identity"]["user"] in EMPTY and not phase["authCookie"],
            f"{name} 响应或浏览器带有认证身份")
    if selected:
        require(user["side"] == 1 and user["tenantMatchesSeed"]
                and session["identity"]["tenant"] == "non-null" and session["tenant"] == seed
                and phase["tenantCookie"] == "seed", "已选阶段 Cookie、GetAll 或 Session 与种子不符")
    else:
        require(user["side"] == 2 and user["identity"]["tenantId"] in EMPTY
                and session["identity"]["tenant"] in EMPTY and phase["tenantCookie"] == "omitted",
                f"{name} 仍有租户上下文")
    check_ui(phase, user["texts"], seed, selected)
    phase["semantics"] = {"side": user["side"], "tenant": session["tenant"], "anonymous": True,
                          "clockProvider": user["clockProvider"], "ianaTimeZone": user.get("ianaTimeZone"),
                          "language": user["language"], "texts": user["texts"], "form": phase["form"],
                          "tenantUi": phase["tenantUi"], "dialog": phase.get("dialog"),
                          "application": session["application"], "localeMappings": config["localeMappings"]}


def check_switch(evidence, files, scripts, config, frontend, host, seed):
    check_scope(evidence)
    require(evidence["initialCookieCount"] == 0, "新上下文带有 Cookie")
    requests = evidence["requests"]
    require(len({row["requestId"] for row in requests}) == len(requests), "请求 ID 重复")
    documents = [row for row in requests if row["kind"] == "Document"]
    loaders = [row["loaderId"] for row in documents]
    phases = evidence["phases"]
    require([row["name"] for row in phases] == list(PHASES) and len(set(loaders)) == 3 and all(loaders)
            and [row["loaderId"] for row in phases] == loaders
            and [row["loaderId"] for row in evidence["commits"]] == loaders
            and [row["origin"] for row in evidence["commits"]] == [frontend] * 3,
            "缺少三个独立且已提交的主文档")
    require(any(row["loaderId"] == loaders[0] and row["route"] == frontend + LOGIN
                for row in evidence["sameDocumentRoutes"]), "首次登录路由未在根文档内完成")
    require(all(row["loaderId"] in loaders for row in requests if row["path"] in (*INIT, SELECT)),
            "存在无法关联验收文档的初始化或租户选择请求")
    post, reply = check_selection(evidence, frontend, host)
    select, clear = evidence["actions"]
    require(select["kind"] == "select" and clear["kind"] == "clear" and post["loaderId"] == loaders[0]
            and select["sequence"] < post["sequence"] < reply["sequence"]
            < documents[1]["sequence"] < clear["sequence"] < documents[2]["sequence"],
            "选择成功、清空及重载顺序不符")
    for row in evidence["preflight"]:
        require(row["origin"] == host and row["path"] in (*INIT[1:], SELECT) and row["status"] == 204,
                "CORS 预检来源、路径或状态不符")
    for phase in phases:
        check_phase(phase, evidence, files, scripts, config, frontend, host, seed)


def check_scope(evidence):
    require(not evidence["unexpected"] and not evidence["pageErrors"] and not evidence["webSockets"],
            "出现页面异常、WebSocket 或超出匿名范围的请求")
    require(not evidence.get("otherAuthMarker")
            and not any(row["headers"]["authorization"] or row["headers"]["authCookie"] for row in evidence["requests"]),
            "浏览器网络出现认证标记")


def check_selection(evidence, frontend, host):
    post = one_request(evidence["requests"], SELECT, "POST")
    reply = response_for(post)
    check_business(reply, frontend, host)
    require(reply["availability"] == 1 and reply["tenantMatchesSeed"] and post["tenancyNameMatchesSeed"]
            and post["wireHeadersObserved"] and not post["headers"]["authorization"] and not post["headers"]["authCookie"],
            "非空选择请求、Available 响应或匿名状态不符")
    return post, reply


class TenantTraffic:
    def __init__(self, page, evidence, frontend, host, files, seed, font_urls):
        self.page, self.evidence = page, evidence
        self.frontend, self.host, self.files, self.seed, self.font_urls = frontend, host, files, seed, font_urls
        self.sequence = count(1)
        self.requests, self.options, self.extras = {}, {}, {}
        self.loader = None
        evidence.update(requests=[], preflight=[], commits=[], sameDocumentRoutes=[], phases=[], actions=[],
                        pageErrors=0, webSockets=0, unexpected=0, unexpectedTypes={}, otherAuthMarker=False)
        page.on("pageerror", lambda _error: self.increment("pageErrors"))
        page.on("websocket", lambda _socket: self.increment("webSockets"))
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.send("Page.enable")
        self.frame = self.cdp.send("Page.getFrameTree")["frameTree"]["frame"]["id"]
        self.cdp.on("Page.frameNavigated", self.commit)
        self.cdp.on("Page.navigatedWithinDocument", self.same_document)
        self.cdp.on("Network.requestWillBeSent", self.request)
        self.cdp.on("Network.requestWillBeSentExtraInfo", self.extra)
        self.cdp.on("Network.responseReceived", self.response)
        self.cdp.on("Network.loadingFinished", self.finished)
        self.cdp.on("Network.loadingFailed", self.failed)
        self.cdp.send("Network.enable", {"maxTotalBufferSize": 32 * 1024 * 1024,
                                          "maxResourceBufferSize": 8 * 1024 * 1024,
                                          "maxPostDataSize": 4096,
                                          "enableDurableMessages": True})
        self.cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})

    def increment(self, name):
        self.evidence[name] += 1

    def unexpected(self, kind):
        self.increment("unexpected")
        types = self.evidence["unexpectedTypes"]
        types[kind] = types.get(kind, 0) + 1

    def commit(self, event):
        frame = event["frame"]
        if frame["id"] == self.frame:
            self.loader = frame["loaderId"]
            origin, path = endpoint(frame["url"])
            self.evidence["commits"].append({"loaderId": self.loader, "origin": origin, "path": path,
                                             "sequence": next(self.sequence)})

    def same_document(self, event):
        if event["frameId"] == self.frame:
            self.evidence["sameDocumentRoutes"].append({"loaderId": self.loader, "route": "".join(endpoint(event["url"])),
                                                        "sequence": next(self.sequence)})

    def request(self, event):
        request = event["request"]
        origin, path = endpoint(request["url"])
        request_id = event["requestId"]
        method, kind = request["method"], event.get("type")
        main_document = kind == "Document" and event.get("frameId") == self.frame
        if request_id in self.requests or request_id in self.options:
            self.unexpected("redirect-or-duplicate")
            if request_id in self.requests:
                self.requests[request_id]["redirected"] = True
            return
        if method == "OPTIONS":
            if origin != self.host or path not in (*INIT[1:], SELECT):
                self.unexpected("preflight")
                return
            row = {"requestId": request_id, "initiatorRequestId": event["initiator"].get("requestId"),
                   "origin": origin, "path": path, "method": method, "status": None, "sequence": next(self.sequence)}
            self.options[request_id] = row
            self.evidence["preflight"].append(row)
            return
        embedded = request["url"].startswith("data:") and kind in ("Image", "Font", "Stylesheet")
        font = kind == "Font" and request["url"] in self.font_urls
        local_asset = origin == self.frontend and path.lstrip("/") in self.files
        allowed_static = method == "GET" and (embedded or font or local_asset and kind not in ("Fetch", "XHR", "EventSource"))
        interested = main_document or kind == "Script" or path in (*INIT, SELECT)
        allowed = (allowed_static or main_document and origin == self.frontend and method == "GET" and path in ("/", LOGIN)
                   or origin == self.frontend and path == APP_CONFIG and method == "GET"
                   or origin == self.host and (path in INIT[1:] and method == "GET" or path == SELECT and method == "POST"))
        if not allowed:
            self.unexpected(kind or "unclassified")
        headers = request_identity(request["headers"], self.seed)
        if not interested or not allowed:
            self.observe_other_auth(headers)
            return
        row = {"requestId": request_id, "loaderId": event["loaderId"], "origin": origin, "path": path,
               "kind": kind, "method": method, "sequence": next(self.sequence), "responses": [],
               "redirected": "redirectResponse" in event, "failed": False, "finishedSequence": 0,
               "wireHeadersObserved": False, "headers": headers}
        if path == SELECT:
            try:
                payload = json.loads(request.get("postData", "null"))
            except ValueError:
                payload = None
            row["tenancyNameMatchesSeed"] = payload == {"tenancyName": self.seed["tenancyName"]}
            if row["tenancyNameMatchesSeed"]:
                row["tenancyName"] = payload["tenancyName"]
        self.requests[request_id] = row
        self.evidence["requests"].append(row)
        if request_id in self.extras:
            self.apply_wire_headers(row, self.extras.pop(request_id))

    def extra(self, event):
        request_id = event["requestId"]
        headers = request_identity(event["headers"], self.seed)
        if request_id in self.requests:
            self.apply_wire_headers(self.requests[request_id], headers)
        else:
            self.extras[request_id] = headers
            self.observe_other_auth(headers)

    def observe_other_auth(self, headers):
        if headers["authorization"] or headers["authCookie"]:
            self.evidence["otherAuthMarker"] = True

    @staticmethod
    def apply_wire_headers(row, headers):
        row["wireHeadersObserved"] = True
        # 认证标记取两份观测的并集，租户头状态使用实发头。
        row["headers"] = headers | {key: headers[key] or row["headers"][key]
                                    for key in ("authorization", "authCookie")}

    def response(self, event):
        request_id = event["requestId"]
        response = event["response"]
        if request_id in self.options:
            self.options[request_id]["status"] = response["status"]
        if row := self.requests.get(request_id):
            origin, path = endpoint(response["url"])
            headers = {key.lower(): value for key, value in response["headers"].items()}
            cors = headers.get("access-control-allow-origin")
            row["responses"].append({"requestId": request_id, "loaderId": event["loaderId"],
                                     "sequence": next(self.sequence), "status": response["status"],
                                     "cors": cors if cors in (None, self.frontend, "*") else "other"})
            if (origin, path) != (row["origin"], row["path"]):
                row["redirected"] = True

    def finished(self, event):
        if row := self.requests.get(event["requestId"]):
            row["finishedSequence"] = next(self.sequence)

    def failed(self, event):
        if row := self.requests.get(event["requestId"]):
            row["failed"] = "canceled" if event.get("canceled") else "failed"
            error = event.get("errorText", "")
            if re.fullmatch(r"net::ERR_[A-Z0-9_]+", error):
                row["networkError"] = error

    def read_body(self, row):
        reply = response_for(row)
        body = self.cdp.send("Network.getResponseBody", {"requestId": row["requestId"]})
        data = base64.b64decode(body["body"]) if body["base64Encoded"] else body["body"].encode()
        result = row["responses"][0]
        if row["origin"] == self.frontend:
            result["sha256"] = digest(data)
            if row["path"] == APP_CONFIG:
                parsed = json.loads(data)
                result["config"] = {key: parsed[key] for key in ("appBaseUrl", "remoteServiceBaseUrl", "localeMappings")}
        else:
            payload = json.loads(data)
            result["success"] = (isinstance(payload, dict) and payload.get("success") is True
                                 and isinstance(payload.get("result"), dict))
            check_business(reply | {"success": result["success"]}, self.frontend, self.host)
            payload = payload["result"]
            if row["path"] == USER_CONFIG:
                result["userConfig"] = observed_config(payload, self.seed)
            elif row["path"] == SESSION:
                result["session"] = observed_identity(payload, self.seed)
            elif row["path"] == SELECT:
                state = payload.get("state")
                result["availability"] = state if type(state) is int else "invalid"
                result["tenantMatchesSeed"] = type(payload.get("tenantId")) is int and payload["tenantId"] == self.seed["id"]
                if result["tenantMatchesSeed"]:
                    result["tenantId"] = payload["tenantId"]

    def wait_for_phase(self, index, scripts):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            document = [row for row in self.requests.values() if row["kind"] == "Document"]
            if len(document) > index:
                loader = document[index]["loaderId"]
                rows = [row for row in self.requests.values() if row["loaderId"] == loader]
                finished = {row["path"] for row in rows if row["finishedSequence"]}
                complete = all(row["finishedSequence"] or row["failed"] for row in rows if row["kind"] == "Script")
                if {document[index]["path"], *INIT, *scripts} <= finished and complete:
                    return loader
            self.page.wait_for_timeout(40)
        require(False, f"{PHASES[index]} 未收到本阶段的必要回执")

    def navigation_timing(self):
        def main_loader():
            return self.cdp.send("Page.getFrameTree")["frameTree"]["frame"]["loaderId"]

        loader = main_loader()
        navigation = self.page.evaluate("""() => {
            const entries = performance.getEntriesByType('navigation');
            return entries.length === 1 ? entries[0].type : null;
        }""")
        # 前后读同一主框架，确保导航类型属于取值时的文档。
        return {"navigationLoaderId": loader if loader == main_loader() else None,
                "navigationType": navigation if isinstance(navigation, str) and navigation in NAVIGATION_TYPES else None}

    def read_phase(self, phase, loader):
        for row in tuple(self.requests.values()):
            path = row["path"]
            if row["loaderId"] == loader and (row["kind"] in ("Document", "Script") or path in INIT):
                self.read_body(row)
            if phase == "tenant" and path == SELECT and row["method"] == "POST":
                self.read_body(row)

    def action(self, kind):
        self.evidence["actions"].append({"kind": kind, "sequence": next(self.sequence)})


def simple_text(locator):
    locator.wait_for(state="visible")
    return " ".join(locator.inner_text().split())


def read_tenant_ui(page):
    root = page.locator("tenant-change .tenant-change-component")
    link = root.locator("a")
    selected = root.locator("strong")
    return {"label": simple_text(root), "change": simple_text(link),
            "strong": simple_text(selected) if selected.count() else None,
            "title": root.locator("span[title]").get_attribute("title") if selected.count() else None}, link


def read_dialog(page, link, expected):
    link.click()
    modal = page.locator(".modal-dialog:visible")
    input_box = modal.locator("input[name=tenancyName]")
    input_box.wait_for(state="visible")
    # 动态组件显示后，Angular 的 ngModel 才把预填值写入 DOM。
    page.wait_for_function("(text) => document.querySelector('.modal-dialog input[name=tenancyName]')?.value === text",
                           arg=expected)
    save = modal.locator("button[type=submit]")
    return {"input": input_box.input_value(),
            "texts": {"ChangeTenant": simple_text(modal.locator(".modal-title")),
                      "TenancyName": simple_text(modal.locator("label[for=tenancyName]")),
                      "LeaveEmptyToSwitchToHost": simple_text(modal.locator(".modal-body > span")),
                      "Save": simple_text(save)}}, input_box, save


def browser_switch(browser, frontend, host, original, files, config, label, evidence, seed):
    from playwright.sync_api import Error

    entry = EntryScripts()
    html = (original / "index.html").read_text()
    entry.feed(html)
    font_urls = set(re.findall(r"https://fonts\.gstatic\.com/s/sourcesanspro/[A-Za-z0-9_./-]+\.woff2", html))
    require(sum(path.startswith("/main-") for path in entry.paths) == 1
            and sum(path.startswith("/scripts-") for path in entry.paths) == 1,
            "每侧 index 须引用一个主入口和一个全局脚本")
    if label == "pair":
        require("/" + GLOBAL in entry.paths, "双包 index 缺少候选全局脚本")
        entry.paths.append("/" + CHUNK)
    with browser.new_context(**BROWSER_OPTIONS) as context:
        evidence["initialCookieCount"] = len(context.cookies())
        require(evidence["initialCookieCount"] == 0, "新匿名上下文存在 Cookie")
        page = context.new_page()
        page.set_default_timeout(16000)
        traffic = TenantTraffic(page, evidence, frontend, host, files, seed, font_urls)
        try:
            evidence["activePhase"] = PHASES[0]
            page.goto(frontend + "/", wait_until="domcontentloaded")
            for index, name in enumerate(PHASES):
                evidence["activePhase"] = name
                loader = traffic.wait_for_phase(index, entry.paths)
                page.wait_for_url(frontend + LOGIN, wait_until="domcontentloaded")
                phase = {"name": name, "loaderId": loader, "route": page.url if page.url == frontend + LOGIN else "other"}
                evidence["phases"].append(phase)
                phase.update(traffic.navigation_timing())
                traffic.read_phase(name, loader)
                phase["form"] = read_form(page)
                phase["tenantUi"], link = read_tenant_ui(page)
                cookies = context.cookies(frontend + LOGIN)
                tenant_cookies = [cookie["value"] for cookie in cookies if cookie["name"] == "Abp-TenantId"]
                phase["tenantCookie"] = ("omitted" if not tenant_cookies else
                                         value_state(tenant_cookies[0], seed["id"]) if len(tenant_cookies) == 1 else "multiple")
                phase["authCookie"] = has_auth_cookie(cookie["name"] for cookie in cookies)
                if name != PHASES[-1]:
                    phase["dialog"], input_box, save = read_dialog(page, link, seed["tenancyName"] if index else "")
                check_scope(evidence)
                check_phase(phase, evidence, files, entry.paths, config, frontend, host, seed)
                if index == 0:
                    require(not any(row["path"] == SELECT for row in evidence["requests"]), "初始宿主已发出租户选择请求")
                elif index == 1:
                    post, reply = check_selection(evidence, frontend, host)
                    document = next(row for row in evidence["requests"] if row["loaderId"] == loader and row["kind"] == "Document")
                    require(evidence["actions"][0]["sequence"] < post["sequence"] < reply["sequence"] < document["sequence"],
                            "选择请求成功响应须先于租户文档重载")
                if name != PHASES[-1]:
                    input_box.fill(seed["tenancyName"] if index == 0 else "")
                    traffic.action("select" if index == 0 else "clear")
                    save.click()
            check_switch(evidence, files, entry.paths, config, frontend, host, seed)
            evidence["activePhase"] = "complete"
        except Error as failure:
            evidence["browserError"] = type(failure).__name__
            raise
        finally:
            evidence["selectionPostCount"] = sum(row["path"] == SELECT and row["method"] == "POST" for row in evidence["requests"])
            evidence["preflightCount"] = len(evidence["preflight"])


def finish_switch(report):
    sides = report["sides"]
    states = [sides[label]["status"] for label in LABELS]
    if report.get("cleanupError"):
        status = "cleanup_failed"
    elif report.get("inputError") or "input_incomparable" in states:
        status = "input_incomparable"
    elif states == ["passed", "passed"]:
        left, right = (sides[label]["observation"]["phases"] for label in LABELS)
        differences = [{"phase": a["name"], "fields": sorted(key for key in a["semantics"]
                                                            if a["semantics"][key] != b["semantics"][key])}
                       for a, b in zip(left, right) if a["semantics"] != b["semantics"]]
        report["comparison"] = {"status": "different" if differences else "equal", "differences": differences}
        status = "cross_side_difference" if differences else "passed"
    else:
        status = "both_failed" if states.count("failed") == 2 else "one_side_failed"
    report.setdefault("comparison", {"status": "not_run", "reason": "需要两侧独立通过和完整的共享运行证据"})
    for record in sides.values():
        evidence = record.get("observation", {})
        attempted = {row["name"] for row in evidence.get("phases", [])}
        if evidence.get("activePhase"):
            attempted.add(evidence["activePhase"])
        record["notRun"] = [phase for phase in PHASES if phase not in attempted]
    report.update(status=status, exitCode=0 if status == "passed" else 1)
    return report["exitCode"]


def check_database_state(state, identity, migrations):
    require(state["identity"] == identity, "SQL 实际库与专用新库身份不符")
    require([row["migrationId"] for row in state["migrations"]] == migrations, "SQL 迁移历史不符")
    rows = state["tenantRows"]
    require(len(rows) == 1 and type(rows[0]["id"]) is int and rows[0]["id"] > 0
            and rows[0]["tenancyName"] == "Default" and bool(rows[0]["name"]),
            "SQL 缺少唯一启用、未删除且使用共享库的 Default 种子")
    return {key: rows[0][key] for key in ("id", "tenancyName", "name")}


def check_host_target(rows, pid, identity):
    owned = [row for row in rows if row["clientPid"] == pid]
    require(owned and all(row["database"] == identity["database"] and row["databaseId"] == identity["databaseId"]
                          for row in owned), "SQL 实测 Host 进程连接目标与专用新库不符")
    return owned


class TenantStaticServer(ThreadingHTTPServer):
    # Chrome 重载时会同时请求入口和多个预加载模块，默认监听队列只有五项。
    request_queue_size = 32


class TenantSwitchRun(BootstrapRun):
    finish_report = staticmethod(finish_switch)
    static_server = TenantStaticServer

    def __init__(self, args):
        super().__init__(args)
        self.report.update(workflow="angular19-anonymous-tenant-switch", interpreter=sys.executable)
        self.report["notRun"] = ["登录提交", "已鉴权切换", "失效租户业务", "角色操作", "SignalR", "其他平台", "发行"]

    def observe_browser(self, browser, frontend, host, original, files, config, label, evidence):
        seed = self.report["shared"]["databaseBeforeBrowser"]["seed"]
        try:
            browser_switch(browser, frontend, host, original, files, config, label, evidence, seed)
        finally:
            evidence["contextClosed"] = not browser.contexts
        require(evidence["contextClosed"], "本侧 Chrome 上下文仍存在")

    def database_state(self, side):
        state = {
            "identity": self.database.identify(side.name),
            "migrations": self.database.query(side.name, """
SELECT MigrationId AS migrationId, ProductVersion AS productVersion
FROM dbo.__EFMigrationsHistory ORDER BY MigrationId
"""),
            "tenantRows": self.database.query(side.name, """
SELECT Id AS id, TenancyName AS tenancyName, Name AS [name]
FROM dbo.AbpTenants
WHERE TenancyName = N'Default' AND IsActive = 1 AND IsDeleted = 0
  AND NULLIF(ConnectionString, '') IS NULL
"""),
        }
        state["seed"] = check_database_state(state, side.identity, self.migration_ids)
        return state

    def verify_host_database(self, side, record):
        rows = self.database.query("master", """
SELECT host_process_id AS clientPid, database_id AS databaseId, DB_NAME(database_id) AS [database], session_id AS sessionId
FROM sys.dm_exec_sessions WHERE is_user_process = 1 AND program_name = N'R5RoleUpdate'
ORDER BY session_id
""")
        record["hostSqlSessions"] = check_host_target(rows, side.pid, side.identity)

    def cleanup(self):
        super().cleanup()
        process_status = {}
        self.report["cleanup"]["backendPidsStopped"] = process_status
        for name, record in self.report.get("shared", {}).get("processes", {}).items():
            if pid := record.get("pid"):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    process_status[name] = True
                else:
                    process_status[name] = False
        require(all(process_status.values()), "本轮后端仍有存活进程")


if __name__ == "__main__":
    raise SystemExit(TenantSwitchRun(parse_arguments(__doc__)).execute())
