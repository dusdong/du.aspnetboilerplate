"""从公开固定模板准备并离线核验 R5 使用的冻结 Angular 前端。"""

import argparse
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

from r3_template_runtime import ANGULAR_PACKAGES, LOCK_SHA, check_lock, inventory
from r3_web_host import INPUTS, TEMPLATE, write_json
from r5_angular_role_edit import (
    ANGULAR_INVENTORY, ANGULAR_MANIFEST, APP_CONFIG, EDIT_CHUNK, EDIT_SHA256, frozen_angular,
)
from verify import VerificationError, read_json, require, sha256


TEMPLATE_COMMIT = INPUTS[TEMPLATE][0]
NODE_VERSION = "v22.22.0"
YARN_VERSION = "1.22.22"
FONT_URL = "https://fonts.googleapis.com/css?family=Source+Sans+Pro:300,400,400i,700"
FONT_SHA256 = "21b1e561f61902ab22e99701e8e4b0ef2b2ca24a1589cdf6208c04295f80f2a9"
INDEX_SHA256 = "eb6d4967b6520d53928c759b849e553f77d9073d459973f23983aa0fd5bdb065"
FROZEN_URLS = {"remoteServiceBaseUrl": "http://127.0.0.1:14436", "appBaseUrl": "http://127.0.0.1:14236"}
MANIFEST = "angular-production-files.json"
BROWSER = "source/angular/dist/browser"
CHECK_ERRORS = (VerificationError, OSError, ValueError, KeyError)

# 识别内联字体样式中的规则和声明，跳过字符串、注释和来源函数内的分隔符。
CSS_COMMENT = rb"/\*(?:[^*]|\*(?!/))*\*/"
CSS_LITERAL = CSS_COMMENT + rb"""|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\\."""
CSS_FUNCTION = rb"\((?:" + CSS_LITERAL + rb"""|[^)'"/\\]|/(?!\*))*\)"""
CSS_ATOM = CSS_LITERAL + rb"|" + CSS_FUNCTION + rb"|/(?!\*)"
CSS_GAP = rb"(?:[ \t\r\n\f]|" + CSS_COMMENT + rb")"
FONT_FACE_RULE = re.compile(
    rb"(?<![\w-])@font-face" + CSS_GAP + rb"*\{(?P<body>(?:"
    + CSS_ATOM + rb"""|[^{}'"/\\(])*)\}|""" + CSS_ATOM,
    re.IGNORECASE | re.DOTALL,
)
FONT_FACE_DECLARATION = re.compile(rb"(?:" + CSS_ATOM + rb"""|[^;'"/\\(])+""", re.DOTALL)
TARGET_FONT_FAMILY = re.compile(
    CSS_GAP + rb"*font-family" + CSS_GAP + rb"*:" + CSS_GAP
    + rb"""*(?:"Source Sans Pro"|'Source Sans Pro'|Source""" + CSS_GAP + rb"+Sans" + CSS_GAP
    + rb"+Pro)" + CSS_GAP + rb"*",
    re.IGNORECASE | re.DOTALL,
)


def command(report, output, label, argv, cwd, env, *, failure_context=""):
    argv = [os.fspath(arg) for arg in argv]
    log = output / f"{label}.log"
    receipt = {"argv": argv, "cwd": str(cwd), "log": log.name}
    report["commands"][label] = receipt
    with log.open("xb") as stream:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, check=False)
    receipt["exitCode"] = result.returncode
    require(result.returncode == 0, f"{label} 退出 {result.returncode}，原始结果见 {log}{failure_context}")
    return log


def locked_digest(path, report, phase):
    report["lock"]["observed"][phase] = sha256(path)
    check_lock(path)


def production_identity(files, manifest, browser):
    font = {"url": FONT_URL, "expected": FONT_SHA256, "actual": None, "bytes": 0, "fontFaces": 0}
    if "index.html" in files["files"]:
        try:
            html = (browser / "index.html").read_bytes()
        except OSError as error:
            font["readError"] = str(error)
        else:
            for match in re.finditer(rb"<style\b[^>]*>(.*?)</style>", html, re.DOTALL):
                css = match.group(1)
                rules = [token.group("body") for token in FONT_FACE_RULE.finditer(css)
                         if token.group("body") is not None]
                if any(TARGET_FONT_FAMILY.fullmatch(declaration.group())
                       for rule in rules for declaration in FONT_FACE_DECLARATION.finditer(rule)):
                    font.update(actual=hashlib.sha256(css).hexdigest(), bytes=len(css),
                                fontFaces=len(rules))
                    break
    return {
        "manifest": {"expected": ANGULAR_MANIFEST, "actual": sha256(manifest)},
        "inventory": {"expected": ANGULAR_INVENTORY, "actual": files["sha256"]},
        "fileCount": len(files["files"]),
        "editChunk": {"path": EDIT_CHUNK, "expected": EDIT_SHA256, "actual": files["files"].get(EDIT_CHUNK)},
        "index": {"expected": INDEX_SHA256, "actual": files["files"].get("index.html")},
        "font": font,
    }


def prepare(args):
    output = args.output.resolve()
    args.output.mkdir()
    angular = output / "source/angular"
    cache, home, temp = (output / name for name in ("yarn-cache", "home", "tmp"))
    report = {
        "status": "failed", "stage": "工具链", "templateRepo": str(args.template_repo.resolve()),
        "templateCommit": TEMPLATE_COMMIT, "fontUrl": FONT_URL, "commands": {},
        "lockRegistryHosts": ["registry.npmjs.org", "registry.yarnpkg.com"],
        "lock": {"expected": LOCK_SHA, "observed": {}},
        "tools": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
    }
    try:
        require(sys.platform == "darwin" and platform.machine() == "arm64", "需要 macOS ARM64")
        node = shutil.which(args.node)
        yarn = shutil.which(args.yarn)
        require(node and yarn, "找不到 Node.js 或 Yarn Classic 可执行文件")
        node, yarn = Path(node).resolve(), Path(yarn).resolve()
        for path in (cache, home, temp, angular.parent):
            path.mkdir()
        env = {
            "HOME": str(home), "TMPDIR": str(temp),
            "PATH": f"{node.parent}:/usr/bin:/bin:/usr/sbin:/sbin",
            "LANG": "en_US.UTF-8", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "YARN_IGNORE_PATH": "1", "YARN_CACHE_FOLDER": str(cache),
            "npm_config_userconfig": os.devnull, "npm_config_globalconfig": os.devnull,
        }
        run = partial(command, report, output, env=env)

        report["stage"] = "模板导出"
        archive = output / "angular-source.tar"
        run("angular-archive", ["git", "archive", "--format=tar", f"--output={archive}", TEMPLATE_COMMIT, "angular"],
            args.template_repo.resolve())
        run("angular-extract", ["tar", "-xf", archive, "-C", angular.parent], output)
        report["archiveSha256"] = sha256(archive)

        report["stage"] = "工具链"
        node_log = run("node-version", [node, "-p", "process.version + ' ' + process.platform + '/' + process.arch"], angular)
        yarn_command = [yarn, "--no-default-rc"]
        yarn_log = run("yarn-version", [*yarn_command, "--version"], angular)
        node_version = node_log.read_text(encoding="utf-8").strip()
        yarn_version = yarn_log.read_text(encoding="utf-8").strip()
        report["tools"].update(node=node_version, yarn=yarn_version)
        require(node_version == f"{NODE_VERSION} darwin/arm64" and yarn_version == YARN_VERSION,
                f"需要 Node.js {NODE_VERSION} darwin/arm64 和 Yarn Classic {YARN_VERSION}，"
                f"实际 {node_version} / {yarn_version}")

        report["stage"] = "锁校验"
        lock = angular / "yarn.lock"
        locked_digest(lock, report, "beforeInstall")
        require(FONT_URL in (angular / "src/index.html").read_text(encoding="utf-8"), "模板字体样式表 URL 不符")
        absent = not (angular / "node_modules").exists()
        empty = not any(cache.iterdir())
        report.update(nodeModulesInitiallyAbsent=absent, yarnCache={"path": str(cache), "initiallyEmpty": empty})
        require(absent and empty, "需要全空的依赖安装目录与 Yarn 下载缓存")

        report["stage"] = "依赖安装"
        run("angular-install", [*yarn_command, "install", "--frozen-lockfile", "--non-interactive",
                                "--no-progress", "--cache-folder", cache], angular)
        locked_digest(lock, report, "afterInstall")
        modules = angular / "node_modules"
        versions = {name: read_json(modules / name / "package.json")["version"] for name in ANGULAR_PACKAGES}
        report["packageVersions"] = versions
        require(versions == ANGULAR_PACKAGES, f"依赖版本不符，预期 {ANGULAR_PACKAGES}，实际 {versions}")

        report["stage"] = "production 构建"
        angular_cache = angular / ".angular/cache"
        empty = not angular_cache.exists() or not any(angular_cache.iterdir())
        report["angularCache"] = {"path": str(angular_cache), "existed": angular_cache.exists(), "initiallyEmpty": empty}
        require(empty and not (angular / "dist").exists(), "需要全空的 Angular 构建缓存（含字体）与输出目录")
        run("angular-build", [*yarn_command, "ng", "build", "--configuration", "production"], angular,
            failure_context=f"。模板字体样式表 {FONT_URL}")
        locked_digest(lock, report, "afterBuild")

        report["stage"] = "冻结配置与清单生成"
        browser = output / BROWSER
        config = browser / APP_CONFIG.lstrip("/")
        before = read_json(config)
        require(FROZEN_URLS.keys() <= before.keys(), "应用配置缺少 URL 字段")
        write_json(config, before | FROZEN_URLS)
        files = inventory(browser, include_app_data=True)
        manifest = output / MANIFEST
        write_json(manifest, files)

        report["stage"] = "生成清单与静态实物核验"
        report["production"] = production_identity(files, manifest, browser)
        frozen_angular(output)
        report.update(status="passed", stage="完成")
    except CHECK_ERRORS as error:
        report["error"] = str(error)
    finally:
        write_json(output / "report.json", report)
    if report["status"] == "failed":
        if "production" in report:
            print(json.dumps(report["production"], ensure_ascii=False), file=sys.stderr)
        raise VerificationError(f"{report['stage']}：{report['error']}。报告见 {output / 'report.json'}")
    print(f"冻结 Angular 前端已核验。报告见 {output / 'report.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    build = subparsers.add_parser("prepare", help="从固定 Git 对象和公开构建输入生成冻结前端")
    build.add_argument("--template-repo", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--node", default="node", help="Node.js 22.22.0 可执行文件")
    build.add_argument("--yarn", default="yarn", help="Yarn Classic 1.22.22 可执行文件")
    verify = subparsers.add_parser("verify", help="离线核验冻结清单与静态文件")
    verify.add_argument("--angular-source", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            prepare(args)
        else:
            _, files = frozen_angular(args.angular_source.resolve())
            print(json.dumps({"files": len(files["files"]), "inventory": files["sha256"]}))
    except CHECK_ERRORS as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
