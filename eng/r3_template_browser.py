"""用真实浏览器验收固定 Angular 产物的租户登录与授权搜索。"""

import hashlib
from urllib.parse import parse_qs, urlsplit

from r3_template_sql import PERMISSION
from verify import VerificationError, require, sha256


APP_CONFIG = "/assets/appconfig.production.json"
USER_CONFIG = "/AbpUserConfiguration/GetAll"
TENANT_API = "/api/services/app/Account/IsTenantAvailable"
AUTH = "/api/TokenAuth/Authenticate"
SESSION = "/api/services/app/Session/GetCurrentLoginInformations"
USERS = "/api/services/app/User/GetAll"


def matches(response, origin, path, method="GET"):
    url = urlsplit(response.url)
    return (f"{url.scheme}://{url.netloc}", url.path, response.request.method) == (origin, path, method)


def keyword_for(url):
    return parse_qs(urlsplit(url).query, keep_blank_values=True).get("Keyword", [])


def check_session(identity, baseline):
    expected = {"tenantId": baseline["tenant"]["tenantId"], "userId": baseline["account"]["userId"],
                "userName": baseline["account"]["userName"]}
    require(identity == expected, f"服务端会话身份不符，预期 {expected}，实际 {identity}")


def check_query(request_keyword, total, items, baseline):
    keyword = baseline["keyword"]
    require(request_keyword == [keyword], f"搜索请求 Keyword 不符，预期 {keyword}，实际 {request_keyword}")
    require(total == 1 and items == baseline["matches"],
            f"搜索响应不符，总数 {total}，结果 {items}，预期 {baseline['matches']}")


def check_search(request_keyword, total, items, row_names, baseline):
    check_query(request_keyword, total, items, baseline)
    keyword = baseline["keyword"]
    require(row_names == [keyword], f"用户名列不符，预期唯一结果 {keyword}，实际 {row_names}")


def response_json(response, origin=None, *, wrapped=True):
    path = urlsplit(response.url).path
    require(response.ok, f"{path} HTTP {response.status}")
    if origin:
        allow_origin = response.header_value("Access-Control-Allow-Origin")
        require(allow_origin == origin, f"{path} CORS 允许来源不符：{allow_origin}")
    data = response.json()
    if wrapped:
        require(data.get("success") is True and isinstance(data.get("result"), dict),
                f"{path} 未取得成功响应")
        return data["result"]
    return data


def browser_round(config, browser_output, baseline, password, report, *, before_login=None, search_request_id=None):
    from playwright.sync_api import Error, TimeoutError, expect, sync_playwright

    frontend, host = config["frontend"], config["host"]
    action = "启动全新浏览器上下文"
    report["steps"] = {}
    steps = report["steps"]
    try:
        with sync_playwright() as playwright:
            launch_config = {"headless": True}
            if config["chrome"]:
                launch_config["executable_path"] = config["chrome"]
            browser = playwright.chromium.launch(**launch_config)
            try:
                report["browser"] = {"engine": "chromium", "version": browser.version,
                                     "executable": config["chrome"] or playwright.chromium.executable_path}
                with browser.new_context() as context:
                    page = context.new_page()
                    page.set_default_timeout(20000)
                    main_script = next(browser_output.glob("main-*.js"))
                    action = "加载当轮 Angular production 页面与应用配置"
                    with page.expect_response(lambda r: matches(r, frontend, APP_CONFIG)) as asset, \
                            page.expect_response(lambda r: matches(r, frontend, "/" + main_script.name)) as script, \
                            page.expect_response(lambda r: matches(r, host, USER_CONFIG)) as config_response:
                        index = page.goto(frontend + "/account/login")
                    require(index and index.ok and
                            hashlib.sha256(index.body()).hexdigest() == sha256(browser_output / "index.html") and
                            script.value.ok and
                            hashlib.sha256(script.value.body()).hexdigest() == sha256(main_script),
                            "浏览器加载的 index.html 或入口脚本与 production 产物不同")
                    client_config = response_json(asset.value, wrapped=False)
                    require(client_config.get("remoteServiceBaseUrl") == host
                            and client_config.get("appBaseUrl") == frontend,
                            "浏览器取得的 production 配置与本轮前后端地址不符")
                    response_json(config_response.value, frontend)
                    steps["client"] = {"entryPath": "/account/login", "status": index.status,
                                       "script": main_script.name, "scriptSha256": sha256(main_script),
                                       "configPath": APP_CONFIG, "configStatus": asset.value.status,
                                       "hostConfigPath": USER_CONFIG, "hostConfigStatus": config_response.value.status}

                    action = "通过模板租户选择入口选择默认租户"
                    page.locator("tenant-change a").click()
                    tenancy = baseline["tenant"]["tenancyName"]
                    page.locator("input[name=tenancyName]").fill(tenancy)
                    with page.expect_response(lambda r: matches(r, host, TENANT_API, "POST")) as chosen, \
                            page.expect_response(lambda r: matches(r, host, SESSION)) as selected_session:
                        page.locator("form:has(input[name=tenancyName]) button[type=submit]").click()
                    # 租户选择会整页重载，从新页面已经建立的会话读取服务端租户标识。
                    require(chosen.value.ok, f"{TENANT_API} HTTP {chosen.value.status}")
                    selected = response_json(selected_session.value, frontend)
                    tenant_id = (selected.get("tenant") or {}).get("id")
                    require(tenant_id == baseline["tenant"]["tenantId"] and selected.get("user") is None,
                            f"登录前会话不是选定租户，实际租户 ID {tenant_id}")
                    tenant_label = page.locator("tenant-change strong")
                    expect(tenant_label).to_have_text(tenancy, timeout=20000)
                    steps["tenant"] = {"path": TENANT_API, "status": chosen.value.status,
                                       "sessionPath": SESSION, "sessionStatus": selected_session.value.status,
                                       "tenancyName": tenancy, "tenantId": tenant_id}

                    action = "填写并提交真实租户登录表单"
                    page.locator("input[name=userNameOrEmailAddress]").fill(baseline["account"]["userName"])
                    page.locator("input[name=password]").fill(password)
                    if before_login:
                        before_login()
                    with page.expect_response(lambda r: matches(r, host, AUTH, "POST")) as auth, \
                            page.expect_response(lambda r: matches(r, host, USER_CONFIG)) as granted, \
                            page.expect_response(lambda r: matches(r, host, SESSION)) as session:
                        page.locator("input[name=password]").locator("xpath=ancestor::form").locator(
                            "button[type=submit]").click()
                    # 登录会立即整页跳转。认证响应状态与跳转后的会话一起证明登录完成。
                    require(auth.value.ok, f"{AUTH} HTTP {auth.value.status}")
                    steps["authentication"] = {"path": AUTH, "status": auth.value.status}
                    action = "核对登录后的服务端会话和 Pages.Users 权限"
                    session_result = response_json(session.value, frontend)
                    user, tenant = session_result.get("user") or {}, session_result.get("tenant") or {}
                    identity = {"tenantId": tenant.get("id"), "userId": user.get("id"), "userName": user.get("userName")}
                    steps["session"] = {"path": SESSION, "status": session.value.status, **identity}
                    check_session(identity, baseline)
                    steps["authentication"].update(success=True, userId=identity["userId"])
                    permissions = response_json(granted.value, frontend)["auth"]["grantedPermissions"]
                    granted_in_browser = page.evaluate("permission => abp.auth.isGranted(permission)", PERMISSION)
                    server_value = permissions.get(PERMISSION)
                    require(server_value in ("true", True) and granted_in_browser is True,
                            f"登录会话缺少 {PERMISSION}，服务端 {server_value!r}，客户端 {granted_in_browser!r}")
                    steps["authorization"] = {"path": USER_CONFIG, "status": granted.value.status,
                                              "permission": PERMISSION, "serverValue": server_value, "granted": True}

                    action = "从授权菜单进入用户列表并等候初始查询"
                    with page.expect_response(lambda r: matches(r, host, USERS) and
                                              all(not item for item in keyword_for(r.url))) as initial:
                        page.locator("a[href='/app/users']").click()
                    before = response_json(initial.value, frontend)
                    rows = page.locator("p-table tbody tr").filter(has=page.locator("td:nth-child(2)"))
                    require(before.get("totalCount", 0) >= 2, "初始用户列表缺少租户管理员和合成用户")
                    expect(rows).to_have_count(len(before["items"]), timeout=20000)
                    route = urlsplit(page.url).path
                    require(route == "/app/users", f"浏览器没有进入授权用户路由：{route}")
                    steps["initialList"] = {"path": USERS, "status": initial.value.status,
                                            "route": route, "totalCount": before["totalCount"]}

                    action = f"提交搜索并等候 Keyword={baseline['keyword']} 的列表响应"
                    search = page.locator("input[name=keyword]")
                    search.fill(baseline["keyword"])
                    tagged = []
                    if search_request_id:
                        def tag_search(route):
                            request = route.request
                            url = urlsplit(request.url)
                            if (f"{url.scheme}://{url.netloc}", url.path, request.method,
                                    keyword_for(request.url)) == (host, USERS, "GET", [baseline["keyword"]]):
                                tagged.append(request)
                                route.continue_(url=request.url + "&r3RollbackRequest=" + search_request_id)
                            else:
                                route.continue_()

                        page.route(host + USERS + "?*", tag_search)
                    with page.expect_response(lambda r: matches(r, host, USERS) and
                                              keyword_for(r.url) == [baseline["keyword"]]) as result:
                        search.press("Enter")
                    response = result.value
                    step = steps["search"] = {"path": USERS, "method": response.request.method,
                                              "keyword": keyword_for(response.url), "status": response.status}
                    if search_request_id:
                        require(tagged == [response.request], "浏览器搜索响应与本轮标记请求不一致")
                        step["requestId"] = search_request_id
                    payload = response_json(response, frontend)
                    fields = ("id", "userName", *baseline.get("searchFields", ()))
                    items = [{field: item.get(field) for field in fields}
                             for item in payload.get("items", [])]
                    step.update(totalCount=payload.get("totalCount"), items=items)
                    check_query(step["keyword"], step["totalCount"], items, baseline)
                    action = "等待搜索渲染并核对唯一行的用户名列"
                    expect(rows).to_have_count(1, timeout=20000)
                    expect(rows.locator("td").first).to_have_text(baseline["keyword"], timeout=20000)
                    step["userNameCells"] = [name.strip() for name in rows.locator("td:first-child").all_text_contents()]
                    check_search(step["keyword"], step["totalCount"], items, step["userNameCells"], baseline)
            finally:
                browser.close()
    except (TimeoutError, AssertionError) as error:
        raise VerificationError(f"浏览器未完成「{action}」") from error
    except Error as error:
        raise VerificationError(f"浏览器操作失败「{action}」") from error
