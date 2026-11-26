"""约束 R5 托管发行的运行身份、冻结输入和收据阶段。"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from r1_restore_inventory import NUGET_SOURCE
from verify import VerificationError, require, sha256

REPO = "dusdong/du.aspnetboilerplate"
OWNER = "dusdong"
WORKFLOW = "publish-r5-mapping.yml"
WORKFLOW_PATH = f".github/workflows/{WORKFLOW}"
TAG = "v10.5.2"
TAG_COMMIT = "cebc3e38a511783092963893bf5ad3161d0f0a19"
BATCH_SHA = "b914f5669c504a3a85cd7120fb63ff0d14667924d6dd0ff1f92fea9a1a76eaf1"
MANIFEST_SHA = "2f4ba12a0752739eaafb522d5c9e0a20abd241176646ae31d4748e5102a3fa02"
ARCHIVES = {
    "Du.AutoMapper.14.0.1.nupkg": "32bbe536dcb588e45257e9d3be5f5f62d7bbeeb642cc15cce857066b2b8d8993",
    "Du.AutoMapper.14.0.1.snupkg": "0f2afb02a61541679282471c2ac7b642ab21c0385f30da224ef94ba651531886",
    "Du.AutoMapper.Collection.11.0.1.nupkg": "b6229b0cfde5d96024541a146483b0b30875b6002acef02d6c1852d35d38a7a1",
    "Du.AutoMapper.Collection.11.0.1.snupkg": "d22d7377514910dd1bcc4aeb70ad453552fd0485bfd50d607cc3c15dee1bf066",
    "Du.Abp.AutoMapper.10.5.2.nupkg": "095ecde6a4db3bb7f48fb777f06c258cbc14a4c1c6b6a6de0affafa05b2cc683",
    "Du.Abp.AutoMapper.10.5.2.snupkg": "4c93ce73e07b345159b8c83a1e6b80b847353082c2eef23be72c5ae67b57592b",
}
JOB = "publish"
CHECK_STEP = "核对 OIDC 登录"
PUSH_STEP = "上传单个冻结归档"


def github(endpoint, *, data=None, method="GET", download=None):
    command = ["gh", "api", "--hostname", "github.com", "--method", method,
               "-H", "X-GitHub-Api-Version: 2026-03-10", f"repos/{REPO}/{endpoint}"]
    if data is not None:
        command += ["--input", "-"]
    if download is None:
        result = subprocess.run(command, input=None if data is None else json.dumps(data).encode(),
                                stdout=subprocess.PIPE, timeout=45)
        require(result.returncode == 0, f"GitHub API 操作失败 {method} {endpoint}")
        return json.loads(result.stdout)
    command += ["-H", "Accept: application/octet-stream"]
    with download.open("xb") as output:
        result = subprocess.run(command, stdout=output, timeout=90)
    require(result.returncode == 0, f"草稿附件下载失败 {endpoint}")


def github_id(value):
    value = str(value)
    require(re.fullmatch(r"[1-9][0-9]*", value), "需要 GitHub 数字 ID")
    return value


def check_tag():
    ref = github(f"git/ref/tags/{TAG}")["object"]
    require(ref["type"] == "tag", f"{TAG} 须为附注 tag")
    tag = github(f"git/tags/{ref['sha']}")
    require(tag["tag"] == TAG and tag["object"]["type"] == "commit" and tag["object"]["sha"] == TAG_COMMIT,
            f"{TAG} 未指向已核定的协调提交")


def draft_assets(draft_id):
    draft_id = github_id(draft_id)
    release = github(f"releases/{draft_id}")
    require(str(release.get("id")) == draft_id and release.get("tag_name") == TAG and release.get("draft") is True,
            f"需要目标仓库 {TAG} 的 Release 草稿")
    assets = {row["name"]: row for row in release["assets"]}
    require(len(release["assets"]) == len(ARCHIVES) and assets.keys() == ARCHIVES.keys(),
            "草稿附件须恰好包含六份冻结归档")
    for name, digest in ARCHIVES.items():
        row = assets[name]
        github_id(row["id"])
        require(row["state"] == "uploaded" and row["digest"] == f"sha256:{digest}",
                f"GitHub 草稿附件状态或 SHA-256 不匹配：{name}")
    return assets


def run_title(mode, intent=""):
    return f"R5 NuGet {mode} {intent}".rstrip()


def run_attempt(run_id, title, head):
    run_id = github_id(run_id)
    run = github(f"actions/runs/{run_id}/attempts/1")
    require(str(run.get("id")) == run_id and run.get("run_attempt") == 1
            and run.get("event") == "workflow_dispatch" and run.get("head_branch") == "main"
            and run.get("path") == WORKFLOW_PATH and run.get("head_sha") == head
            and run.get("display_title") == title
            and run.get("repository", {}).get("full_name") == REPO
            and run.get("head_repository", {}).get("full_name") == REPO,
            "GitHub 运行与固定工作流、主仓提交或上传意向不匹配")
    return run


def job_steps(run_id):
    jobs = github(f"actions/runs/{github_id(run_id)}/attempts/1/jobs")["jobs"]
    require(len(jobs) == 1 and jobs[0]["name"] == JOB and jobs[0]["status"] == "completed",
            "GitHub 发布作业尚未取得唯一的终态记录")
    return {step["name"]: step for step in jobs[0]["steps"]}


def require_login(run_id, head):
    run = run_attempt(run_id, run_title("login-only"), head)
    require(run["status"] == "completed" and run["conclusion"] == "success", "指定提交尚无成功的 OIDC 验证")
    steps = job_steps(run_id)
    require(steps.get(CHECK_STEP, {}).get("conclusion") == "success"
            and steps.get(PUSH_STEP, {}).get("conclusion") == "skipped", "登录验证须完成交换且跳过上传")


def permit_label(run_id, intent, login_run):
    return f"r5:{github_id(run_id)}:{intent}:{github_id(login_run)}"


def dispatch(archive, remote, ticket):
    inputs = {"mode": "publish", "archive": archive, "draft_id": remote["draftId"],
              "asset_id": remote["assetId"], "intent": ticket, "login_run": remote["loginRun"]}
    result = github(f"actions/workflows/{WORKFLOW}/dispatches", method="POST", data={"ref": "main", "inputs": inputs})
    return github_id(result.get("workflow_run_id"))


def authorize(remote, ticket):
    label = permit_label(remote["runId"], ticket, remote["loginRun"])
    asset_id = github_id(remote["assetId"])
    got = github(f"releases/assets/{asset_id}", method="PATCH", data={"label": label})
    require(got.get("label") == label and str(got.get("id")) == asset_id, "GitHub 附件放行回读不符")


def runner_archive():
    archive = os.environ["R5_ARCHIVE"]
    require(archive in ARCHIVES, "只允许上传本轮固定归档")
    require(os.environ["GITHUB_REPOSITORY"] == REPO and os.environ["GITHUB_REF"] == "refs/heads/main"
            and os.environ["GITHUB_EVENT_NAME"] == "workflow_dispatch" and os.environ["GITHUB_RUN_ATTEMPT"] == "1",
            "只允许目标仓库 main 的首次手动运行")
    return Path(os.environ["RUNNER_TEMP"]) / "r5-publish" / archive


def prepare_runner():
    path = runner_archive()
    run_id = github_id(os.environ["GITHUB_RUN_ID"])
    login_run = github_id(os.environ["R5_LOGIN_RUN"])
    ticket = os.environ["R5_INTENT"]
    require(re.fullmatch(r"[a-f0-9]{32}", ticket), "无效的上传意向 ID")
    asset_id = github_id(os.environ["R5_ASSET_ID"])
    draft_id = github_id(os.environ["R5_DRAFT_ID"])
    label = permit_label(run_id, ticket, login_run)
    head = os.environ["GITHUB_SHA"]
    require_login(login_run, head)
    check_tag()
    # 先返回 dispatch 运行 ID，本地持久化后才写附件 label。作业可能在这一小段窗口内已启动。
    for attempt in range(16):
        asset = draft_assets(draft_id)[path.name]
        require(str(asset["id"]) == asset_id, "固定草稿附件 ID 已改变")
        if asset.get("label") == label:
            break
        if attempt < 15:
            time.sleep(3)
    else:
        raise VerificationError("草稿附件未获当前 GitHub 运行的单次放行")
    path.parent.mkdir()
    github(f"releases/assets/{asset_id}", download=path)
    require(sha256(path) == ARCHIVES[path.name], "托管 runner 下载件 SHA-256 不匹配")
    print(f"{path.name} SHA-256 {ARCHIVES[path.name]}，与本轮冻结归档一致")


def push_runner():
    path = runner_archive()
    require(os.getenv("NUGET_API_KEY") and os.getenv("NUGET_SYMBOL_API_KEY"), "缺少临时 NuGet 凭据")
    require(sha256(path) == ARCHIVES[path.name], "上传前归档 SHA-256 不匹配")
    config = path.parent / "NuGet.Config"
    config.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n', encoding="utf-8")
    command = ["dotnet", "nuget", "push", str(path), "--source", NUGET_SOURCE, "--configfile", str(config)]
    if path.suffix == ".nupkg":
        command.append("--no-symbols")
    print(f"开始 NuGet 提交 {path.name} SHA-256 {ARCHIVES[path.name]}", flush=True)
    result = subprocess.run(command, cwd=path.parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"NuGet CLI 退出 {result.returncode}", flush=True)
    return result.returncode


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "check-draft":
            check_tag()
            print(json.dumps({name: {"id": row["id"], "digest": row["digest"]}
                              for name, row in draft_assets(sys.argv[2]).items()}, indent=2))
            sys.exit(0)
        if sys.argv[1:] == ["prepare"]:
            sys.exit(prepare_runner())
        if sys.argv[1:] == ["push"]:
            sys.exit(push_runner())
        sys.exit("用法：r5_oidc.py prepare|push|check-draft DRAFT_ID")
    except (KeyError, OSError, ValueError, VerificationError, subprocess.TimeoutExpired) as error:
        sys.exit(f"R5 托管发行失败：{error}")
