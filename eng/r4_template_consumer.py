"""从 R4 冻结源或已验签的公开源验收固定模板，并支持原版回退。"""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess

from r3_template_net9_packages import CandidateRun, selected_archive
from r3_template_net10_runtime import UpgradeRuntime
from r3_template_net10_upgrade import RUNTIME_PATCH_PREIMAGES, UpgradeBuildRun
from r3_template_original_rollback import ROLES, RollbackRun, verify_query_target
from r3_web_host import NUGET_SOURCE, artifact, write_json
from r4_candidate_batch import BATCH_REFERENCE, load_frozen_batch
from r4_release_candidate import MANIFEST
from r4_template_assets import ENTRY_LABELS, public_downloads, verify_build_directory, verify_process
from verify import ROOT, make_run_directory, read_json, require, sha256


BUILD = "r4-template-build"
UPGRADE = "r4-template-upgrade"
ROLLBACK = "r4-template-original-rollback"
CHECKPOINTS = "rollback-inputs.json"
PLAN = Path("openspec/changes/prepare-r4-first-release-candidate")
PLAN_BASE = "bd5f29f8a02ffcc8868deb2c8e60f49306d6668a"
PLAN_TREE = "c26dcfb0afcca4626c4ded3ca2a512b1809bfe1a"
PUBLIC_PLAN = Path("openspec/changes/publish-r4-first-public-release")
BUILD_BINDINGS = "r4-build-assets.json"
PUBLIC_INPUT_NAMES = ("release-manifest.json", "verified-downloads.json")
R4_RUNTIME_PATCH_PREIMAGES = RUNTIME_PATCH_PREIMAGES | {
    "Web.Host": "4beac5678eff346851a5977e76ba5bb7599e8d93",
    "Web.Core": "0087c2900fe67e72f01a7a43db2e796541779695",
    "Core": "752826bdcccb6b6c9251e7ca7fb94707f34a4cbd",
    "Migrator": "7a8fec9aadeb6cacbeb2d800c071d2ae9b6e3b3f",
}


def planning_artifacts(repo, plan, specification):
    change = plan.name
    state = "active"
    if not (repo / plan).is_dir():
        archives = sorted((repo / plan.parent / "archive").glob(f"*-{change}"))
        require(len(archives) == 1, f"找不到唯一的 {change} OpenSpec 制品目录")
        plan = archives[0].relative_to(repo)
        state = "archived"
    files = sorted(path for path in (repo / plan).rglob("*") if path.is_file())
    require(all((repo / plan / name) in files for name in (
        "proposal.md", "design.md", "tasks.md", f"specs/{specification}/spec.md")),
        f"{change} OpenSpec 规划制品不完整")
    status = subprocess.check_output(
        ["git", "-C", repo, "status", "--porcelain=v1", "--untracked-files=all", "--", plan], text=True)
    return {"change": change, "changePath": plan.as_posix(), "changeState": state, "artifactSource": "working_tree",
            "gitStatus": status.splitlines(), "artifacts": [artifact(path, repo) for path in files]}


def planning_inputs(repo, current_commit, current_tree):
    def git(*args):
        return subprocess.check_output(["git", "-C", repo, *args], text=True).strip()

    manifest = read_json(repo / MANIFEST.relative_to(ROOT))
    coordinator = manifest["gitlinkCommit"]
    coordinator_tree = git("rev-parse", f"{coordinator}^{{tree}}")
    require(git("rev-parse", f"{PLAN_BASE}^{{tree}}") == PLAN_TREE
            and git("rev-parse", f"{current_commit}^{{tree}}") == current_tree, "R4 规划或执行 Git 树不符")
    for record in (*manifest["producers"].values(), manifest["template"]):
        path = record["path"]
        commit = record.get("finalCommit", record["baseCommit"])
        expected = ["160000", "commit", commit, path]
        for revision in dict.fromkeys((coordinator, current_commit)):
            require(git("ls-tree", revision, "--", path).split() == expected, f"{revision} 的 R4 gitlink {path} 不符")
    return {**planning_artifacts(repo, PLAN, "release-candidate-verification"),
            "baseCommit": PLAN_BASE, "baseTree": PLAN_TREE,
            "coordinator": {"commit": coordinator, "tree": coordinator_tree},
            "execution": {"commit": current_commit, "tree": current_tree}}


class FrozenPackages:
    planning_commit = PLAN_BASE
    planning_tree = PLAN_TREE

    def __init__(self, repo, evidence, frozen_root, batch_root, *args, public_inputs=None):
        self.batch_root = batch_root
        self.public_inputs = public_inputs
        self.downloads = None
        if public_inputs:
            self.profile += "-public"
        super().__init__(repo, evidence, frozen_root, *args)
        self.report["inputs"]["packageSourceMode"] = "public" if public_inputs else "frozen"
        self.save()

    @property
    def local_package_feed(self):
        return None if self.public_inputs else self.feed

    def materialize(self):
        super().materialize()
        if self.public_inputs:
            scratch = self.evidence / "nuget-scratch"
            scratch.mkdir()
            self.env["NUGET_SCRATCH"] = str(scratch)
            self.report["inputs"]["nuget"]["scratch"] = str(scratch)

    def restore_options(self):
        if not self.public_inputs:
            return super().restore_options()
        return ["--source", NUGET_SOURCE, "--packages", self.cache,
                "-p:RestoreFallbackFolders=", "-p:RestoreAdditionalProjectFallbackFolders=",
                "-p:RestoreAdditionalProjectSources=", "-p:DisableImplicitNuGetFallbackFolder=true"]

    def run_dotnet(self, args, log):
        if not self.public_inputs:
            return super().run_dotnet(args, log)
        unset = []
        for name in sorted(os.environ):
            key = name.casefold()
            is_restore_variable = (key.startswith(("nuget_", "nugetpackagesourcecredentials_", "restore"))
                                   or key in {"disableimplicitnugetfallbackfolder", "forceevaluate"})
            if is_restore_variable and name not in self.env:
                unset.extend(("-u", name))
        command = ["env", *unset, self.dotnet, *args] if unset else [self.dotnet, *args]
        return self.command(command, self.root, log, extra_env=self.env)[1]

    def preflight(self):
        super().preflight()
        inputs = self.report["inputs"]
        candidate = planning_inputs(self.repo, inputs["executionCommit"], inputs["executionTree"])
        if self.public_inputs:
            inputs["planning"] = planning_artifacts(self.repo, PUBLIC_PLAN, "public-package-release") | {
                "execution": candidate["execution"],
            }
            inputs["frozenCandidatePlanning"] = candidate | {"purpose": "frozen_batch_qualification"}
            del inputs["planningCommit"], inputs["planningTree"]
        else:
            inputs["planning"] = candidate

    def packages(self):
        batch = self.batch = load_frozen_batch(self.batch_root)
        self.report["inputs"]["r4Batch"] = artifact(self.batch_root / "batch.json", self.batch_root) | {
            "gitlinkCommit": batch["gitlinkCommit"], "template": batch["template"]}
        self.report["inputs"]["r4Consumer"] = artifact(Path(__file__), self.repo)
        self.original_assets = read_json(self.repo / "eng/r3_template_net9_reference.json")["originalAssets"]
        inspection = self.inspection = read_json(self.batch_root / batch["inspection"]["path"])
        if self.public_inputs:
            self.public_evidence = tuple(self.evidence_file(name) for name in PUBLIC_INPUT_NAMES)
            for source, copy in zip(self.public_inputs, self.public_evidence, strict=True):
                shutil.copyfile(source, copy)
            self.report["inputs"]["publicDownloads"] = {
                name: artifact(path, self.evidence) for name, path in zip(PUBLIC_INPUT_NAMES, self.public_evidence, strict=True)}
            self.downloads = public_downloads(*self.public_evidence, self.batch_root, batch)
        else:
            self.feed.mkdir()
        for name, item in batch["packages"].items():
            record = item["archive"]
            targets = inspection[name]["targets"]
            target = targets[self.tfm] if self.tfm in targets else next(iter(targets.values()))
            row = {"id": name, "version": item["version"], "repository": batch["producers"][item["producer"]]["repository"],
                   "archive": record["path"], "archiveSha256": record["sha256"],
                   "asset": target["asset"], "assetSha256": target["assetSha256"]}
            source, row, dependencies = selected_archive(row, self.batch_root)
            require(dependencies == target["dependencies"], f"{name} 的实际依赖与 R4 冻结复核不符")
            self.frozen[name] = {**row, "original": str(source),
                                 "dependencies": dependencies, "assembly": Path(row["asset"]).stem}
            if self.downloads is not None:
                self.frozen[name]["publicDownloadSha256"] = self.downloads[name]["downloadSha256"]
            else:
                copy = self.feed / source.name
                shutil.copyfile(source, copy)
                self.frozen[name]["feedCopy"] = str(copy)
        write_json(self.evidence_file("frozen-packages.json"), self.frozen)

    def inspect_output(self):
        super().inspect_output()
        result = verify_build_directory(self.evidence, self.report["inputs"], self.batch_root,
                                        self.batch, self.inspection, downloads=self.downloads)
        path = self.evidence_file(BUILD_BINDINGS)
        write_json(path, result)
        self.report["inputs"]["r4BuildAssets"] = artifact(path, self.evidence)

    def inputs_after(self):
        if "r4Batch" in self.report["inputs"]:
            load_frozen_batch(self.batch_root)
        if self.public_inputs:
            inputs = self.report["inputs"]
            if nuget := inputs.get("nuget"):
                require(artifact(self.config, self.evidence) == nuget["effective"], "公开包源配置已改变")
            if downloads := inputs.get("publicDownloads"):
                require(all(artifact(path, self.evidence) == downloads[path.name] for path in self.public_evidence),
                        "固定下载登记已改变")
        super().inputs_after()


class Net9Build(FrozenPackages, CandidateRun):
    profile = BUILD


class Net10Build(FrozenPackages, UpgradeBuildRun):
    profile = BUILD
    runtime_patch_preimages = R4_RUNTIME_PATCH_PREIMAGES


class TemplateUpgrade(FrozenPackages, UpgradeRuntime):
    profile = UPGRADE
    runtime_patch_preimages = R4_RUNTIME_PATCH_PREIMAGES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report["profile"] = self.profile
        self.save()

    def build_net9(self):
        directory = self.builds["net9"]
        directory.mkdir()
        build = Net9Build(self.repo, directory, self.frozen_root, self.batch_root, self.dotnet,
                          public_inputs=self.public_evidence if self.public_inputs else None)
        result = build.execute_build()
        self.report["inputs"]["net9Build"] = artifact(build.report_path, self.evidence) | {"exitCode": result}
        require(result == 0, f".NET 9 R4 干净构建退出 {result}，详见 {build.report_path}")
        if self.public_inputs:
            require(build.report["inputs"]["publicDownloads"] == self.report["inputs"]["publicDownloads"],
                    "两代公开消费使用的首发清单或下载登记不一致")

    def verify_process_assets(self, phase, entry, launch):
        build = self.builds[phase]
        reference = (self.report if phase == "net10" else read_json(build / "report.json"))["inputs"]["r4BuildAssets"]
        path = build / reference["path"]
        require(sha256(path) == reference["sha256"], f"{phase} {entry} 的 R4 构建对账已改变")
        label = ENTRY_LABELS[entry]
        observed = self.evidence / f"{phase}-{label}-loaded.json"
        result = verify_process(read_json(path)[entry], launch, read_json(observed))
        record = self.evidence_file(f"{phase}-{label}-r4-assets.json")
        write_json(record, result | {"observation": artifact(observed, self.evidence)})
        self.report.setdefault("r4ProcessAssets", {}).setdefault(phase, {})[entry] = artifact(record, self.evidence)

    def run_migrator(self, phase, count, expected_logins):
        super().run_migrator(phase, count, expected_logins)
        self.verify_process_assets(phase, "Migrator", self.report["sql"]["migrations"][phase]["launch"])

    def loaded(self):
        super().loaded()
        self.verify_process_assets(self.phase, "Web.Host", self.report["rounds"][self.phase]["host"])

    def process_environment(self, entry):
        result = super().process_environment(entry)
        if entry == "Web.Host":
            result.update(R3_TEMPLATE_OBSERVER_REQUESTS=str(self.request_log),
                          R3_TEMPLATE_OBSERVER_REQUEST_ID=self.request_id,
                          R3_TEMPLATE_OBSERVER_KEYWORD=self.business["keyword"])
        return result

    def round(self, database, label, **kwargs):
        self.request_id = secrets.token_hex(16)
        self.request_log = self.evidence_file(f"{label}-host-search.jsonl")
        outcome = super().round(database, label, **kwargs, search_request_id=self.request_id)
        events = [json.loads(line) for line in self.request_log.read_text(encoding="utf-8").splitlines()]
        pid = outcome["host"]["pid"]
        server = self.db.identity["serverName"]
        verify_query_target(events, pid, server, database, outcome["steps"]["search"],
                            self.request_id, self.business["keyword"])
        self.report["sql"].setdefault("readTargets", {})[label] = {
            "pid": pid, "serverName": server, "database": database,
            "requestId": self.request_id, "evidence": artifact(self.request_log, self.evidence)}
        return outcome

    def comparable_steps(self, outcome):
        steps = outcome["steps"]
        search = {name: value for name, value in steps["search"].items() if name != "requestId"}
        return steps | {"search": search}

    def execute_full(self):
        result = super().execute_full()
        if result == 0 and not self.public_inputs:
            sql = self.report["sql"]
            checkpoints = {}
            for role in ROLES:
                medium = sql["checkpoints"][role]["media"]
                catalog = self.evidence / f"net10-catalog-{role.split('_')[0]}.json"
                checkpoints[role] = {
                    "name": Path(medium["serverPath"]).name, "sha256": medium["sha256"],
                    "size": medium["size"], "backupSetId": medium["backupSetId"],
                    "catalogSha256": sha256(catalog),
                }
            write_json(self.evidence_file(CHECKPOINTS), {
                "batchSha256": self.report["inputs"]["r4Batch"]["sha256"],
                "runId": self.run_id, "reportSha256": sha256(self.report_path), "checkpoints": checkpoints})
        return result


class TemplateRollback(RollbackRun):
    def __init__(self, repo, evidence, frozen_root, batch_root, upgrade_run, lock_sha, config, dotnet):
        self.batch_root = batch_root
        self.lock_sha = lock_sha
        super().__init__(repo, evidence, frozen_root, upgrade_run, config, dotnet)
        self.report["profile"] = ROLLBACK
        self.save()

    def execution_inputs(self):
        inputs = self.report["inputs"]
        inputs["executionCommit"] = self.git(self.repo, "main-current-head.log", "rev-parse", "HEAD")
        inputs["executionTree"] = self.git(self.repo, "main-current-tree.log", "rev-parse", "HEAD^{tree}")
        inputs["planning"] = planning_inputs(self.repo, inputs["executionCommit"], inputs["executionTree"])
        inputs["r4Consumer"] = artifact(Path(__file__), self.repo)

    def upgrade_registration(self):
        batch = load_frozen_batch(self.batch_root)
        batch_id = read_json(BATCH_REFERENCE)["sha256"]
        self.report["inputs"]["r4Batch"] = artifact(self.batch_root / "batch.json", self.batch_root) | {
            "gitlinkCommit": batch["gitlinkCommit"], "template": batch["template"]}
        lock = self.frozen_file(self.upgrade_run, CHECKPOINTS, self.lock_sha)
        registration = read_json(lock)
        require(registration["batchSha256"] == batch_id, "升级登记与 R4 冻结批次摘要不符")
        return UPGRADE, registration["runId"], registration["reportSha256"], registration["checkpoints"]

    def check_upgrade_provenance(self, upgrade):
        inputs = upgrade["inputs"]
        require(inputs["r4Batch"] == self.report["inputs"]["r4Batch"], "升级报告使用了不同的 R4 批次")
        require(inputs.get("planning", {}).get("change") == PLAN.name, "升级报告缺少 R4 规划来源")
        process = upgrade.get("r4ProcessAssets", {})
        require(process.keys() == {"net9", "net10"} and all(rows.keys() == ENTRY_LABELS.keys() for rows in process.values()),
                "升级报告缺少四个 R4 入口的运行资产对账")
        for rows in process.values():
            for record in rows.values():
                self.frozen_file(self.upgrade_run, record["path"], record["sha256"])
        require(upgrade["sql"]["readTargets"].keys() == {"net9", "net10"}, "升级报告缺少两代请求读库证据")
        for name in ("net9_loaded", "net10_loaded", "recover_backups", "cleanup", "frozen_inputs_after"):
            require(upgrade["stages"][name]["exitCode"] == 0, f"升级报告的 {name} 阶段未通过")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "upgrade", "rollback"))
    parser.add_argument("--batch-root", required=True, type=Path)
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--dotnet", type=Path)
    parser.add_argument("--tfm", choices=("net9.0", "net10.0"))
    parser.add_argument("--runtime-config", type=Path)
    parser.add_argument("--upgrade-run", type=Path)
    parser.add_argument("--rollback-inputs-sha256")
    parser.add_argument("--release-manifest", type=Path, help="公开源模式的固定首发清单")
    parser.add_argument("--verified-downloads", type=Path, help="公开源模式的已验签主包下载登记")
    args = parser.parse_args()
    if args.action == "build" and args.tfm is None:
        parser.error("build 需要 --tfm")
    if args.action != "build" and args.runtime_config is None:
        parser.error("upgrade 和 rollback 需要 --runtime-config")
    if args.action == "rollback" and (args.upgrade_run is None or args.rollback_inputs_sha256 is None):
        parser.error("rollback 需要 --upgrade-run 与 --rollback-inputs-sha256")
    if bool(args.release_manifest) != bool(args.verified_downloads):
        parser.error("公开源模式需要同时指定 --release-manifest 和 --verified-downloads")
    if args.action == "rollback" and args.release_manifest:
        parser.error("公开源模式支持 build 和 upgrade")
    for name in ("DEBUG", "PWDEBUG"):
        os.environ.pop(name, None)
    profile = {"build": BUILD, "upgrade": UPGRADE, "rollback": ROLLBACK}[args.action]
    public_inputs = None
    if args.release_manifest:
        public_inputs = (args.release_manifest.resolve(), args.verified_downloads.resolve())
        profile += "-public"
    directory = make_run_directory(args.evidence_root.resolve(), profile + "-")
    inputs = ROOT, directory, args.frozen_root.resolve(), args.batch_root.resolve()
    if args.action == "build":
        runner = Net9Build if args.tfm == "net9.0" else Net10Build
        run = runner(*inputs, args.dotnet, public_inputs=public_inputs)
    elif args.action == "upgrade":
        run = TemplateUpgrade(*inputs, args.runtime_config.resolve(), args.dotnet, public_inputs=public_inputs)
    else:
        run = TemplateRollback(*inputs, args.upgrade_run.resolve(), args.rollback_inputs_sha256,
                               args.runtime_config.resolve(), args.dotnet)
    print(f"{profile} report: {run.report_path}", flush=True)
    return run.execute_build() if args.action == "build" else run.execute_full()


if __name__ == "__main__":
    raise SystemExit(main())
