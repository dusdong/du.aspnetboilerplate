"""用固定 Angular production 页面验收公开 R4、R5 的直接用户角色编辑。"""

import argparse
from contextlib import ExitStack, contextmanager, suppress
from datetime import datetime, timezone
from functools import partial
import hashlib
from http.server import ThreadingHTTPServer
from importlib.metadata import version
from itertools import count
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

from r3_template_browser import APP_CONFIG, AUTH, SESSION, TENANT_API, USER_CONFIG, USERS, browser_session, keyword_for, matches
from r3_template_net9_runtime import ANGULAR_MANIFEST, ORIGINAL
from r3_template_runtime import SpaHandler, available, inventory
from r3_web_host import artifact, write_json
from r5_public_switch_assets import COUNTS, bound_json, compare_graphs, verify_patch
from r5_template_role_update import (
    APP, CHECK_ERRORS, DB_KEYS, RELEASES, SEED_FIELDS, LiveRun, LiveSide, SqlIdentityMismatch,
    check, check_dto, check_fields, check_sql, result, time_value,
)
from verify import ROOT, VerificationError, read_json, require, sha256


MAIN = "main-PZGEMKYC.js"
EDIT_CHUNK = "chunk-PPIUHYWS.js"
EDIT_SHA256 = "67ec845c7dea216c0c54c8a0012a2518baf4247ca5f2c7e587aa4721a39f4e4a"
ANGULAR_INVENTORY = "59203802dd274be9c00c041d1529238d72bd7ddc914a8f84224fbd84923bce37"
GET = APP + "User/Get"
ROLES = APP + "User/GetRoles"
PUT = APP + "User/Update"
RELEVANT = {GET: "get", ROLES: "roles", PUT: "put", USERS: "list"}
STEPS = (("keep", "Angular Keep", "A"), ("replace", "Angular Replace", "B"),
         ("clear", "Angular Clear", None))


def empty_phases():
    return {key: {"status": "not_run", "reason": "依赖的输入或前一步未通过"} for key, _, _ in STEPS}


def frozen_angular(source):
    manifest = source / "angular-production-files.json"
    require(sha256(manifest) == ANGULAR_MANIFEST, "冻结 Angular 清单文件摘要不符")
    original = source / "source/angular/dist/browser"
    expected = read_json(manifest)
    require(expected["sha256"] == ANGULAR_INVENTORY and len(expected["files"]) == 1193
            and expected["files"][EDIT_CHUNK] == EDIT_SHA256,
            "冻结 Angular 清单内容不符")
    require(not any(path.is_symlink() for path in original.rglob("*"))
            and inventory(original, include_app_data=True) == expected, "Angular production 实物与冻结清单不符")
    return original, expected


def serve_copy(original, expected, target, frontend, host):
    shutil.copytree(original, target)
    path = target / APP_CONFIG.lstrip("/")
    before = read_json(path)
    overrides = {"remoteServiceBaseUrl": host, "appBaseUrl": frontend}
    require(overrides.keys() <= before.keys(), "冻结应用配置缺少 URL 字段")
    write_json(path, before | overrides)
    require(read_json(path) == before | overrides, "服务副本的配置字段与预期不符")
    files = inventory(target, include_app_data=True)
    require(files["files"] == expected["files"] | {APP_CONFIG.lstrip("/"): sha256(path)},
            "Angular 服务副本出现未登记文件变化")
    return files, {key: {"before": before[key], "after": value} for key, value in overrides.items()}


class BrowserTraffic:
    def __init__(self, page, host, frontend, user_id, redact):
        self.host, self.frontend, self.user_id, self.redact = host, frontend, user_id, redact
        self.requests, self.responses, self.markers = [], {}, {}
        self.original_request = {}
        self.network_order = count(1)
        self.finished, self.assets = set(), []
        self.search_auth = None
        page.on("request", self.on_request)
        page.on("response", self.on_response)
        page.on("requestfinished", lambda request: self.finished.add(request))
        page.route(lambda url: urlsplit(url).path in (PUT, GET), self.tag)

    def on_request(self, request):
        if urlsplit(request.url).path in RELEVANT and request.method in ("GET", "PUT"):
            self.requests.append(request)
            self.original_request[request] = (request.url, next(self.network_order))

    def on_response(self, response):
        if urlsplit(response.url).path in RELEVANT:
            self.responses[response.request] = (response, next(self.network_order))
        path = urlsplit(response.url).path
        if matches(response, self.frontend, "/" + EDIT_CHUNK):
            self.assets.append(response)

    def tag(self, route):
        request = route.request
        url = urlsplit(request.url)
        if request.method not in ("GET", "PUT"):
            route.continue_()
            return
        if f"{url.scheme}://{url.netloc}" != self.host:
            route.abort()
            return
        marker = secrets.token_hex(16)
        params = {"r5RoleRequest": marker}
        if request.method == "PUT":
            params["r5RoleUser"] = self.user_id
        wire_url = request.url + ("&" if url.query else "?") + urlencode(params)
        # 仅附加观测参数，浏览器仍负责实际 HTTP 传输和响应处理。
        self.markers[request] = (marker, wire_url)
        route.continue_(url=wire_url)

    @staticmethod
    def verify_asset(response, path, digest, evidence):
        seen = {"url": response.url, "status": response.status}
        evidence.append(seen)
        seen["sha256"] = hashlib.sha256(response.body()).hexdigest() if response.ok else None
        require(seen["sha256"] == digest, f"浏览器实际加载的 {path} 与冻结产物不符：{seen}")

    def observed_asset(self, path, digest, evidence):
        received = [response for response in self.assets if matches(response, self.frontend, path)]
        require(received, f"浏览器未实收 {path}")
        for item in received:
            self.verify_asset(item, path, digest, evidence)

    def read(self, start, stop=None):
        from playwright.sync_api import Error

        calls = {key: [] for key in RELEVANT.values()}
        for request in self.requests[start:stop]:
            original_url, sequence = self.original_request[request]
            url = urlsplit(original_url)
            path = url.path
            trace = {"url": original_url, "sequence": sequence, "path": path, "method": request.method,
                     "query": parse_qs(url.query, keep_blank_values=True)}
            if request in self.markers:
                trace["id"], trace["wireUrl"] = self.markers[request]
            response, response_sequence = self.responses.get(request, (None, None))
            row = {"request": trace, "status": response.status if response else None,
                   "responseSequence": response_sequence}
            calls[RELEVANT[path]].append(row)
            try:
                headers = request.all_headers()
                trace["tenant"] = headers.get("abp.tenantid") or headers.get("abp-tenantid")
                trace["authMatchesSearch"] = bool(self.search_auth and headers.get("authorization") == self.search_auth)
                if request.method == "PUT" and request.post_data is not None:
                    trace["rawBody"] = self.redact(request.post_data)
                    trace["json"] = json.loads(trace["rawBody"])
                if response:
                    row["responseUrl"] = response.url
                    row["cors"] = response.header_value("Access-Control-Allow-Origin")
                require(response and request in self.finished, request.failure or "浏览器未取得完整 HTTP 回执")
                row["rawBody"] = self.redact(response.text())
                row["body"] = json.loads(row["rawBody"])
            except (Error, *CHECK_ERRORS) as failure:
                row["error"] = self.redact(str(failure))
        return calls


def browser_result(call, evidence, method):
    request = call["request"]
    url = urlsplit(request["url"])
    check_fields(request, {"method": method, "tenant": str(evidence["expected"]["tenantId"]),
                           "authMatchesSearch": True})
    require(f"{url.scheme}://{url.netloc}" == evidence["host"] and not url.fragment,
            f"业务请求 Host 不符：{request['url']}")
    require(call.get("responseUrl") == request.get("wireUrl", request["url"]), "浏览器响应地址与实发请求不同")
    require(call.get("cors") == evidence["frontend"], f"业务响应 CORS 不符：{call.get('cors')}")
    return result(call)


def expected_roles(expected):
    return [role["normalizedName"] for role in expected["roles"]]


def role_state(options, catalog, selected):
    check_fields({"options": [item["name"] for item in options]}, {"options": catalog})
    require(all(type(item["checked"]) is bool for item in options), "缺少实际复选框状态")
    check_fields({"checked": [item["name"] for item in options if item["checked"]]},
                 {"checked": [name for name in catalog if name in selected]})


def verify_form(form, evidence):
    expected = evidence["expected"]
    require(len(form["get"]) == len(form["roles"]) == 1 and not form["put"] and not form["list"],
            "重开窗口未各发出一次独立的 User/Get 与 User/GetRoles")
    detail, = form["get"]
    roles, = form["roles"]
    check_fields(detail["request"], {"query": {"Id": [str(expected["id"])]}})
    check_user(browser_result(detail, evidence, "GET"), expected)
    check_fields(form["observedFields"], expected["fields"])
    catalog = browser_result(roles, evidence, "GET")["items"]
    require(detail["responseSequence"] < roles["request"]["sequence"], "GetRoles 不是本次重开详情成功后发出的请求")
    if "save" in evidence:
        refreshed, = evidence["save"]["list"]
        require(refreshed["responseSequence"] < detail["request"]["sequence"],
                "重开窗口的详情请求早于保存后的列表响应")
    actual = sorted([{key: item[key] for key in ("id", "name", "normalizedName", "displayName")}
                     for item in catalog], key=lambda item: item["id"])
    require(actual == evidence["catalog"], f"GetRoles 与租户角色目录不符：{actual}")
    role_state(form["options"], [item["name"] for item in catalog],
               [item["name"] for item in catalog if item["normalizedName"] in expected_roles(expected)])


def check_user(user, expected):
    check_dto(user, expected)
    fields = expected["fields"]
    check_fields(user, {"fullName": fields["name"] + " " + fields["surname"]})


def verify_save(saved, evidence):
    expected = evidence["expected"]
    require(len(saved["put"]) == 1, "一次保存没有恰好一笔 PUT")
    receipt, = saved["put"]
    check_user(browser_result(receipt, evidence, "PUT"), expected)
    require(len(saved["list"]) == 1 and not saved["get"] and not saved["roles"], "没有收到保存触发的唯一列表刷新")
    refreshed, = saved["list"]
    check_fields(receipt["request"]["json"], {"id": expected["id"], **expected["fields"],
                                             "roleNames": expected_roles(expected)})
    check_fields(receipt["request"]["json"], {"creationTime": evidence["clientCreationTime"]["isoUtc"]})
    require(keyword_for(refreshed["request"]["url"]) == [SEED_FIELDS["userName"]], "保存后的列表 Keyword 不符")
    listed = browser_result(refreshed, evidence, "GET")
    require(receipt["responseSequence"] < refreshed["request"]["sequence"], "列表刷新早于保存回执")
    require(listed["totalCount"] == 1 and len(listed["items"]) == 1, "保存后的列表查询须返回唯一用户")
    item, = listed["items"]
    fields = expected["fields"]
    full_name = fields["name"] + " " + fields["surname"]
    check_fields(item, {"id": expected["id"], "userName": fields["userName"], "fullName": full_name})
    require(saved["rows"] == [[fields["userName"], full_name]], "保存后的实际列表数据行不符")
    require(saved["closed"], "保存后编辑窗口未关闭")
    verify_selection(saved["optionsBeforeSave"], evidence["catalog"], expected)


def verify_selection(options, catalog, expected):
    names = [item["name"] for item in options]
    require(sorted(names) == sorted(item["name"] for item in catalog), "保存前的角色选项缺项或重复")
    role_state(options, names, [role["name"] for role in expected["roles"]])


def stage_result(side, stage, *, initial=False):
    # 已发出的每一笔写请求与详情请求，即使没有 HTTP 回执，也要独立核对业务连接。
    form = stage.get("form", {})
    saved = stage.get("save", {})
    writes = saved.get("put", []) + form.get("put", [])
    details = saved.get("get", []) + form.get("get", [])
    missing_receipt = any(call.get("status") is None or call.get("error") for call in writes)
    if missing_receipt:
        stage["receiptAvailability"] = "missing"
    for method, calls in (("put", writes), ("get", details)):
        for call in calls:
            binding = call["connection"] = {}
            success = call.get("status") == 200 and not call.get("error")
            check(binding, side.bind, call, binding, success)
            connections = [row for row in binding.get("events", []) if row["kind"] == "connection"]
            if method == "put" and (binding["status"] != "passed"
                                    or not any(row["operation"] == "write" for row in connections)):
                targets = [{key: row.get(key) for key in DB_KEYS} for row in connections]
                stage.setdefault("uncertainWrite", []).append({"requestId": call["request"].get("id"),
                                                              "observedTargets": targets})
    sql_read = stage["sql"] = {"diagnostic": missing_receipt}
    if missing_receipt:
        untrusted = next((call["connection"] for call in writes if call["connection"]["status"] != "passed"), None)
        if untrusted:
            sql_read.update(status="not_run", reason="PUT 回执缺失且无法核实其业务库，跳过本侧只读诊断")
            stage.update(status="input_incomparable", reason=untrusted["reason"])
            return stage["status"]

    def verify_sql():
        sql_read["observed"] = side.sql()
        check_sql(sql_read["observed"], stage["expected"], side.identity)
    check(sql_read, verify_sql)
    failed_connections = [call["connection"] for call in writes + details if call["connection"]["status"] != "passed"]
    if failed_connections or sql_read["status"] == "input_incomparable":
        stage.update(status="input_incomparable",
                     reason=sql_read.get("reason") if sql_read["status"] == "input_incomparable"
                     else failed_connections[0]["reason"])
        return stage["status"]
    observed = stage["business"] = {}
    try:
        if not initial:
            verify_save(saved, stage)
        verify_form(form, stage)
        require(not stage.get("browserError"), stage.get("browserError", ""))
    except CHECK_ERRORS as failure:
        observed.update(status="failed", reason=side.run.redact(str(failure)))
    else:
        observed["status"] = "passed"
    for evidence in (observed, sql_read):
        if evidence["status"] != "passed":
            stage.update(status="failed", reason=evidence["reason"])
            return stage["status"]
    stage["status"] = "passed"
    return "passed"


def gate_next_write(side, stage, start, prior):
    reviewed = stage["crossSideGate"] = {"from": prior, "expectedStart": start, "operation": "read-only SQL"}

    def verify():
        reviewed["observed"] = side.sql()
        check_sql(reviewed["observed"], start, side.identity)
    if check(reviewed, verify):
        return True
    reviewed["status"] = "input_incomparable"
    stage["reason"] = reviewed["reason"]
    return False


def run_stages(sides, report):
    starts = {label: report["sides"][label]["initial"]["expected"] for label in sides}
    pending = {label: [] for label in sides}
    for name, updated_name, role in STEPS:
        for label, side in sides.items():
            record = report["sides"][label]
            if record["status"] != "ready":
                continue
            stage = record["phases"][name]
            if pending[label] and not gate_next_write(side, stage, starts[label], pending[label]):
                record.update(status="input_incomparable", reason=stage["reason"])
                continue
            pending[label] = []
            expected = side.expected(SEED_FIELDS | {"name": updated_name}, role)
            stage.update(side.capture(name, expected), expected=expected)
            stage.pop("reason", None)
            outcome = stage_result(side, stage)
            if outcome == "passed":
                starts[label] = expected
            else:
                record.update(status=outcome, reason=stage["reason"])
            if stage.get("uncertainWrite"):
                for peer in pending.keys() - {label}:
                    pending[peer].append({"side": label, "step": name, "writes": stage["uncertainWrite"]})
    for label in sides:
        if report["sides"][label]["status"] == "ready":
            report["sides"][label]["status"] = "passed"


class AngularSide(LiveSide):
    @contextmanager
    def browser(self, driver, frontend_port):
        starts = self.db.successful_logins(self.name, self.seed)
        baseline = self.seed | {"keyword": SEED_FIELDS["userName"], "searchFields": ("fullName",),
                                "matches": [{"id": self.user_id, "userName": SEED_FIELDS["userName"],
                                             "fullName": "Seed User"}]}
        frontend = f"http://127.0.0.1:{frontend_port}"
        self.runtime = {"host": self.base, "frontend": frontend, "chrome": str(self.run.args.chrome)}
        self.record["addresses"] = self.runtime
        with TemporaryDirectory(prefix="angular-", dir=self.root) as workspace:
            output = Path(workspace) / "browser"
            files, overrides = serve_copy(self.run.original, self.run.angular_inventory, output, frontend, self.base)
            approved = self.root / "angular-served-files.json"
            write_json(approved, files)
            self.record["frontend"] = {"inventory": artifact(approved, self.root), "inventorySha256": files["sha256"],
                                       "configChanges": overrides, "config": read_json(output / APP_CONFIG.lstrip("/"))}
            require(available(frontend_port), f"前端环回端口已被使用：{frontend_port}")
            with ThreadingHTTPServer(("127.0.0.1", frontend_port), partial(SpaHandler, directory=str(output))) as server:
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    evidence = self.record["browserSession"] = {"actualAssets": {}}
                    def on_client(index, main, config):
                        for name, response in (("index.html", index), (MAIN, main), (APP_CONFIG.lstrip("/"), config)):
                            observations = evidence["actualAssets"][name] = []
                            self.traffic.verify_asset(response, name, files["files"][name], observations)

                    with browser_session(self.runtime, output, baseline, self.admin_password, evidence,
                                         driver=driver, on_page=self.on_page, on_client=on_client) as (self.page, self.rows):
                        after = self.db.successful_logins(self.name, self.seed)
                        evidence["loginRows"] = {"before": starts, "after": after}
                        require(after[:-1] == starts and len(after) == len(starts) + 1,
                                "浏览器未在预期库形成唯一新增管理员成功登录记录")
                        self.verify_browser(files["files"])
                        yield
                        require(inventory(output, include_app_data=True) == files, "Angular 服务副本在运行期间改变")
                finally:
                    server.shutdown()
                    thread.join()

    def on_page(self, page, browser):
        cdp = browser.new_browser_cdp_session()
        processes = cdp.send("SystemInfo.getProcessInfo")["processInfo"]
        cdp.detach()
        pid, = [item["id"] for item in processes if item["type"] == "browser"]
        evidence = self.record["browserSession"]
        evidence["pid"] = pid
        handshake = evidence["handshakeResponses"] = []

        def record_response(response):
            url = urlsplit(response.url)
            if f"{url.scheme}://{url.netloc}" == self.base and url.path in (AUTH, SESSION, TENANT_API, USER_CONFIG):
                handshake.append({"path": url.path, "method": response.request.method, "status": response.status})
        page.on("response", record_response)
        self.traffic = BrowserTraffic(page, self.base, self.runtime["frontend"], self.user_id, self.run.redact)

    def verify_browser(self, files):
        evidence = self.record["browserSession"]
        observed = evidence["actualAssets"][EDIT_CHUNK] = []
        self.traffic.observed_asset("/" + EDIT_CHUNK, files[EDIT_CHUNK], observed)
        search, = [request for request in self.traffic.requests if urlsplit(request.url).path == USERS
                   and keyword_for(request.url) == [SEED_FIELDS["userName"]]]
        self.traffic.search_auth = search.header_value("authorization")
        require(self.traffic.search_auth and self.traffic.search_auth.startswith("Bearer "),
                "授权搜索请求缺少浏览器会话 Bearer")
        self.catalog = self.db.query(self.name, """
SELECT Id AS id, Name AS name, NormalizedName AS normalizedName, DisplayName AS displayName
FROM dbo.AbpRoles WHERE TenantId = %s AND IsDeleted = 0 ORDER BY Id
""", (self.tenant_id,))
        require(len(self.catalog) > len(self.roles), "租户角色目录缺少 A、B 之外的角色")
        self.modal = self.page.locator("modal-container:has(abp-modal-footer)")
        self.role_input = self.modal.locator("input[id^='role_']")
        self.timezone = self.page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone")

    def form_options(self):
        return self.role_input.evaluate_all("""boxes => boxes.map(box => ({
            id: box.id, name: box.labels[0].textContent.trim(), checked: box.checked
        }))""")

    def role_tab(self):
        self.modal.locator("tabset .nav-link").nth(1).click()

    def open_editor(self, form):
        from playwright.sync_api import expect

        start = len(self.traffic.requests)
        try:
            with self.page.expect_response(lambda r: matches(r, self.base, ROLES)):
                self.rows.locator("button:has(.fa-pencil-alt)").click()
            expect(self.modal).to_be_visible()
            self.role_tab()
            expect(self.role_input).to_have_count(len(self.catalog))
            form["options"] = self.form_options()
            self.modal.locator("tabset .nav-link").first.click()
            form["observedFields"] = {key: self.modal.locator(f"input[name={key}]").input_value()
                                      for key in ("name", "surname", "userName", "emailAddress")}
            form["observedFields"]["isActive"] = self.modal.locator("input[name=isActive]").is_checked()
        finally:
            form.update(self.traffic.read(start))

    def capture(self, step, expected):
        from playwright.sync_api import Error, expect

        record = {"host": self.base, "frontend": self.runtime["frontend"], "catalog": self.catalog, "form": {}}
        if step == "initial":
            try:
                self.open_editor(record["form"])
            except (Error, AssertionError, *CHECK_ERRORS) as failure:
                record["browserError"] = self.run.redact(str(failure))
            return record
        saved = record["save"] = {}
        start = len(self.traffic.requests)
        try:
            self.modal.locator("input[name=name]").fill(expected["fields"]["name"])
            self.role_tab()
            if step == "replace":
                self.modal.locator("label", has_text=self.roles["A"]["name"]).click()
                self.modal.locator("label", has_text=self.roles["B"]["name"]).click()
            elif step == "clear":
                self.modal.locator("label", has_text=self.roles["B"]["name"]).click()
            options = saved["optionsBeforeSave"] = self.form_options()
            verify_selection(options, self.catalog, expected)
            base_time, fraction = time_value(expected["creationTime"])
            local_time = datetime.fromisoformat(base_time + "." + fraction[:3]).replace(tzinfo=ZoneInfo(self.timezone))
            record["clientCreationTime"] = {"browserZone": self.timezone, "sql": expected["creationTime"],
                                            "isoUtc": local_time.astimezone(timezone.utc).isoformat(
                                                timespec="milliseconds").replace("+00:00", "Z")}
            # 从新的保存动作开始监听。列表由窗口的 onSave 触发，不另发刷新。
            with self.page.expect_response(lambda response: matches(response, self.base, USERS)):
                self.modal.locator("abp-modal-footer button[type=submit]").click()
            expect(self.modal).to_have_count(0)
            saved["closed"] = True
            expect(self.rows).to_have_count(1)
            expect(self.rows.locator("td").nth(0)).to_have_text(SEED_FIELDS["userName"])
            expect(self.rows.locator("td").nth(1)).to_have_text(expected["fields"]["name"] + " User")
            saved["rows"] = [[cell.strip() for cell in self.rows.locator("td").all_text_contents()[:2]]]
        except (Error, AssertionError, *CHECK_ERRORS) as failure:
            record["browserError"] = self.run.redact(str(failure))
        finally:
            saved.update(self.traffic.read(start))
        if not record.get("browserError"):
            try:
                self.open_editor(record["form"])
            except (Error, AssertionError, *CHECK_ERRORS) as failure:
                record["browserError"] = self.run.redact(str(failure))
        return record


class AngularRun(LiveRun):
    def verify_inputs(self):
        for side in self.report["sides"].values():
            side["phases"] = empty_phases()
        self.report.update(workflow="angular-user-role-edit", python=sys.version.split()[0],
                           playwright=version("playwright"))
        launches = super().verify_inputs()
        sealed = read_json(self.prepared / "report.json")
        self.report["graphEvidence"] = {"comparison": sealed["graphComparison"], "entries": {
            label: {entry: evidence["graph"] for entry, evidence in sealed["entries"][label].items()}
            for label in launches}}
        graphs = {
            label: {entry: self.unpack_graph(bound_json(self.prepared, ref), COUNTS[entry])
                    for entry, ref in rows.items()}
            for label, rows in self.report["graphEvidence"]["entries"].items()
        }
        if len(graphs) == len(RELEASES):
            recorded = bound_json(self.prepared, sealed["graphComparison"])
            for entry in COUNTS:
                r4, r5 = (graphs[label][entry] for label in RELEASES)
                difference = compare_graphs(r4, r5)
                require(difference == recorded[entry], f"{entry} 实测包图与封存比较不符")
                verify_patch(r4, r5, difference)
        self.report["profileSources"] += [artifact(ROOT / "eng" / name, ROOT) for name in (
            "r5_angular_role_edit.py", "r3_template_browser.py", "r3_template_runtime.py")]
        self.original, self.angular_inventory = frozen_angular(self.args.angular_source)
        self.report["angular"] = {"manifest": artifact(self.args.angular_source / "angular-production-files.json",
                                                       self.args.angular_source),
                                  "source": str(self.args.angular_source), "inventorySha256": ANGULAR_INVENTORY,
                                  "files": len(self.angular_inventory["files"]), "editSha256": EDIT_SHA256}
        return launches

    @staticmethod
    def unpack_graph(data, counts):
        nodes = data["nodes"]
        edges = {tuple(row[:-1]): row[-1] for row in data["edges"]}
        assets = {tuple(row[:-1]): row[-1] for row in data["assets"]}
        packages = [name for name, node in nodes.items() if node["type"] == "package"]
        require((len(packages), sum(name.startswith("Du.") for name in packages), len(edges)) == counts,
                "封存图中的包、维护包或依赖边数量不符")
        return {"nodes": nodes, "edges": edges, "assets": assets}

    @contextmanager
    def sql_server(self):
        volumes = []
        with super().sql_server():
            resource = self.report["sqlResource"]
            _, mounts = self.command(["docker", "inspect", "--format", "{{json .Mounts}}", resource["containerId"]])
            volumes = resource["volumes"] = [item["Name"] for item in json.loads(mounts) if item["Type"] == "volume"]
            yield
        if volumes:
            _, remaining = self.command(["docker", "volume", "ls", "--format", "{{.Name}}"])
            present = set(volumes) & set(remaining.splitlines())
            resource["volumesRemoved"] = not present
            if present:
                self.report["cleanupError"] = "本轮专用卷仍存在"
        else:
            resource["volumesRemoved"] = True

    @contextmanager
    def side_resources(self, side, ports, driver):
        evidence = side.record
        try:
            side.migrate()
            # Development 的封存清单引用历史构建的 obj。此处的 API Host 使用本轮清单，
            # Angular 静态文件由单独的环回服务提供。
            static_assets = side.root / "api-only.staticwebassets.runtime.json"
            write_json(static_assets, {"ContentRoots": [], "Root": {"Children": {}}})
            evidence["hostStaticAssets"] = artifact(static_assets, side.root)
            with side.host(ports[0], f"http://127.0.0.1:{ports[1]}",
                           ASPNETCORE_STATICWEBASSETS=str(static_assets)), side.browser(driver, ports[1]):
                yield side
        finally:
            cleanup = evidence["cleanup"] = {
                "hostPortReleased": available(ports[0]), "frontendPortReleased": available(ports[1]),
                "temporaryDirectoriesRemaining": sorted(path.name for path in side.root.iterdir()
                                                        if path.is_dir() and path.name.startswith(("angular-", "home-"))),
                "processes": {name: item["exitCode"] for name, item in evidence["processes"].items()},
            }
            pid = evidence.get("browserSession", {}).get("pid")
            if pid:
                cleanup["browserStopped"] = True
                with suppress(ProcessLookupError):
                    os.kill(pid, 0)
                    cleanup["browserStopped"] = False
            if (not cleanup["hostPortReleased"] or not cleanup["frontendPortReleased"]
                    or cleanup["temporaryDirectoriesRemaining"] or cleanup.get("browserStopped") is False
                    or any(code is None for code in cleanup["processes"].values())):
                self.report["cleanupError"] = f"{side.label} 存在未清理的本轮资源"

    def input_failed(self, failure):
        super().input_failed(failure)
        for record in self.report["sides"].values():
            if record["status"] in ("not_run", "ready"):
                record.update(status="input_incomparable", reason=self.report["inputError"])

    def execute_sides(self, launches):
        from playwright.sync_api import Error, sync_playwright

        ports = {"r4": (self.args.r4_port, self.args.r4_frontend_port),
                 "r5": (self.args.r5_port, self.args.r5_frontend_port)}
        sides = {}
        try:
            with sync_playwright() as driver, ExitStack() as sessions:
                for label in launches:
                    record = self.report["sides"][label]
                    side = AngularSide(self, label, launches[label], record)
                    try:
                        sessions.enter_context(self.side_resources(side, ports[label], driver))
                        expected = side.expected(SEED_FIELDS, "A")
                        record["initial"] = initial = side.capture("initial", expected) | {"expected": expected}
                        status = stage_result(side, initial, initial=True)
                        record["status"] = "ready" if status == "passed" else status
                        if status == "passed":
                            sides[label] = side
                        else:
                            record["reason"] = initial["reason"]
                    except (Error, self.database.client.Error, *CHECK_ERRORS) as failure:
                        record.update(status="input_incomparable", reason=self.redact(str(failure)))
                        if failure.__cause__:
                            record["cause"] = self.redact(str(failure.__cause__))
                    self.save()
                if len(sides) == len(RELEASES):
                    browsers = [self.report["sides"][label]["browserSession"]["browser"] for label in sides]
                    require(browsers[0] == browsers[1], "两侧实际 Chromium 版本或入口不一致")
                run_stages(sides, self.report)
        finally:
            self.report["frozenAngularUnchanged"] = (
                frozen_angular(self.args.angular_source) == (self.original, self.angular_inventory))
            require(self.report["frozenAngularUnchanged"], "执行后的冻结前端发生改变")
            for label in RELEASES:
                record = self.report["sides"][label]
                print(f"{label} {record['status']}" + (f" · {record['reason']}" if record.get("reason") else ""), flush=True)
            self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--angular-source", type=Path, default=ROOT / ".git" / ORIGINAL)
    parser.add_argument("--chrome", type=Path, required=True)
    for label in RELEASES:
        parser.add_argument(f"--{label}-port", type=int, required=True)
        parser.add_argument(f"--{label}-frontend-port", type=int, required=True)
    args = parser.parse_args()
    args.angular_source = args.angular_source.resolve()
    args.chrome = args.chrome.resolve()
    ports = (args.r4_port, args.r5_port, args.r4_frontend_port, args.r5_frontend_port)
    if len(set(ports)) != 4 or not all(1024 <= port <= 65535 for port in ports):
        parser.error("需要四个不同的非系统环回端口")
    if (args.output.exists() or any(args.output.resolve().is_relative_to(path)
                                   for path in (args.prepared.resolve(), args.angular_source))):
        parser.error("证据目录必须尚不存在且位于两处封存目录之外")
    return AngularRun(args).execute()


if __name__ == "__main__":
    raise SystemExit(main())
