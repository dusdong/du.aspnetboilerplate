"""验收固定模板中的 R5 三包、两代运行时与公开 R4 同库回退。"""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
from xml.etree import ElementTree as ET

from r3_automapper_packages import stack_package
from r3_template_net10_runtime import PATCH_VERSION, verify_migrator_assemblies
from r3_template_net10_upgrade import UpgradeBuildRun
from r3_template_net9_packages import CandidateRun, normalized_range, selected_archive
from r3_template_net9_runtime import check_migration_target, verify_host_assemblies
from r3_template_runtime import inventory, shared_runtime_trace
from r3_web_host import artifact, project_path, write_json
from r4_release_candidate import MANIFEST
from r4_template_assets import ENTRY_LABELS, verify_build_directory, verify_process
from r4_template_consumer import (BUILD_BINDINGS, R4_RUNTIME_PATCH_PREIMAGES, FrozenPackages, Net10Build,
                                  TemplateUpgrade, planning_artifacts)
from r5_candidate_batch import EDGES, VERSIONS, load_frozen_batch
from r5_public_release import load_release, verified_downloads
from verify import ROOT, make_run_directory, read_json, require, sha256


CHANGE = Path("openspec/changes/fix-r5-automapper-collection-context")
PUBLIC_CHANGE = Path("openspec/changes/prepare-r5-mapping-patch-release")
PROFILE = "r5-template"
R5_RUNTIME_PATCH_PREIMAGES = R4_RUNTIME_PATCH_PREIMAGES | {"Core": "435e51ad8d36b884afc86916c3ec21ab73b45f5c"}
USER_FIELDS = ("name", "surname", "emailAddress", "isActive")
SWITCH_PHASES = ("public", "candidate", "rollback")


@dataclass(frozen=True)
class PublicReleaseInputs:
    manifest: Path
    manifest_sha: str
    downloads: Path
    downloads_sha: str
    source_config: Path | None


class PatchPackages(FrozenPackages):
    def __init__(self, repo, evidence, frozen_root, batch_root, *args, batch_sha, public_release=None):
        self.batch_sha = batch_sha
        self.public_release = public_release
        super().__init__(repo, evidence, frozen_root, batch_root, *args, public_inputs=public_release)
        self.report["inputs"]["packageSourceMode"] = "public" if public_release else "mixed"
        self.save()

    @property
    def local_package_ids(self):
        return () if self.public_release else VERSIONS.keys()

    @property
    def isolated_restore(self):
        return True

    def preflight(self):
        CandidateRun.preflight(self)
        change, specification = ((PUBLIC_CHANGE, "release-candidate-verification") if self.public_release
                                 else (CHANGE, "automapper-package-consumption"))
        self.report["inputs"]["planning"] = planning_artifacts(self.repo, change, specification)

    def public_packages(self):
        public = self.public_release
        manifest, batch, _ = load_release(self.batch_root, self.batch_sha, public.manifest, public.manifest_sha)
        self.downloads = verified_downloads(public.downloads, public.downloads_sha, manifest,
                                            public.manifest_sha, self.batch_sha)
        inputs = self.report["inputs"]["publicDownloads"] = {}
        for name, source, digest in (("release-manifest.json", public.manifest, public.manifest_sha),
                                     ("verified-downloads.json", public.downloads, public.downloads_sha)):
            target = self.evidence_file(name)
            shutil.copyfile(source, target)
            require(sha256(target) == digest, f"复制期间公开输入已改变：{source}")
            inputs[name] = artifact(target, self.evidence)
        return batch

    def packages(self):
        batch = self.public_packages() if self.public_release else load_frozen_batch(self.batch_root, self.batch_sha)
        r4 = "producers" in batch
        self.batch = {"packages": batch["packages"] | batch.get("publicPackages", {})}
        if not self.public_release:
            self.downloads = read_json(self.batch_root / batch["verifiedDownloads"]["path"])["packages"]
        self.report["inputs"]["r5Batch"] = artifact(self.batch_root / "batch.json", self.batch_root) | {
            "root": str(self.batch_root), "template": batch["template"]}
        self.report["inputs"]["r5Consumer"] = artifact(Path(__file__), self.repo)
        self.original_assets = read_json(self.repo / "eng/r3_template_net9_reference.json")["originalAssets"]
        base = read_json(MANIFEST)
        self.inspection = (read_json(self.batch_root / batch["inspection"]["path"]) if r4 else
                           {name: {"targets": row["targets"]} for name, row in self.batch["packages"].items()})
        if self.local_package_ids:
            self.feed.mkdir()
        if r4:
            self.runtime_patch_preimages = R4_RUNTIME_PATCH_PREIMAGES
        for name, item in self.batch["packages"].items():
            local = name in self.local_package_ids
            archive = item["archive"]
            targets = self.inspection[name]["targets"]
            target = targets.get(self.tfm) or next(iter(targets.values()))
            producer = base["packages"][name]["producer"]
            repository = (item["source"]["repository"] if not r4 and name in batch["packages"]
                          else base["producers"][producer]["repository"])
            row = {"id": name, "version": item["version"], "repository": repository,
                   "archive": archive["path"], "archiveSha256": archive["sha256"],
                   "asset": target["asset"], "assetSha256": target["assetSha256"]}
            source, row, dependencies = selected_archive(row, self.batch_root)
            require(dependencies == target["dependencies"], f"{name} 的实际依赖与冻结复核不符")
            frozen = self.frozen[name] = {**row, "original": str(source), "dependencies": dependencies,
                                          "assembly": Path(row["asset"]).stem}
            if not r4 and name in EDGES:
                actual = {dep: normalized_range(version) for dep, version in dependencies.items() if stack_package(dep)}
                expected = {dep: normalized_range(version) for dep, version in EDGES[name].items()}
                require(actual == expected, f"{name} 的候选精确边不符：{actual}")
            if local:
                copy = self.feed / source.name
                shutil.copyfile(source, copy)
                frozen["feedCopy"] = str(copy)
            else:
                frozen["publicDownloadSha256"] = self.downloads[name]["downloadSha256"]
        write_json(self.evidence_file("frozen-packages.json"), self.frozen)

    def materialize(self):
        super().materialize()
        if self.public_release and self.public_release.source_config:
            source = self.public_release.source_config
            payload = source.read_bytes()
            require(ET.canonicalize(payload, strip_text=True) ==
                    ET.canonicalize(from_file=self.config, strip_text=True),
                    f"公开 NuGet 配置只接受 nuget.org、清空回退源和公开源映射：{source}")
            self.config.write_bytes(payload)
            self.report["inputs"]["nuget"]["effective"] = artifact(self.config, self.evidence)

    def inspect_output(self):
        CandidateRun.inspect_output(self)
        result = self.build_bindings()
        path = self.evidence_file(BUILD_BINDINGS)
        write_json(path, result)
        self.report["inputs"]["r4BuildAssets"] = artifact(path, self.evidence)

    def build_bindings(self):
        return verify_build_directory(self.evidence, self.report["inputs"], self.batch_root, self.batch,
                                      self.inspection, downloads=self.downloads, local_ids=self.local_package_ids)

    def inputs_after(self):
        inputs = self.report["inputs"]
        if "r5Batch" in inputs:
            if self.public_release:
                public = self.public_release
                manifest, _, _ = load_release(self.batch_root, self.batch_sha, public.manifest, public.manifest_sha)
                verified_downloads(public.downloads, public.downloads_sha, manifest, public.manifest_sha,
                                   self.batch_sha)
                for name, reference in inputs["publicDownloads"].items():
                    require(artifact(self.evidence / name, self.evidence) == reference, f"公开输入副本已改变：{name}")
                if nuget := inputs.get("nuget"):
                    require(artifact(self.config, self.evidence) == nuget["effective"], "公开包源配置已改变")
            else:
                load_frozen_batch(self.batch_root, self.batch_sha)
        CandidateRun.inputs_after(self)


class PatchNet9Build(PatchPackages, CandidateRun):
    profile = PROFILE + "-build"


class PatchNet10Build(PatchPackages, UpgradeBuildRun):
    profile = PROFILE + "-build"
    runtime_patch_preimages = R5_RUNTIME_PATCH_PREIMAGES


class PatchUpgrade(PatchPackages, TemplateUpgrade):
    profile = PROFILE
    runtime_patch_preimages = R5_RUNTIME_PATCH_PREIMAGES

    def build_net9(self):
        directory = self.builds["net9"]
        directory.mkdir()
        build = PatchNet9Build(self.repo, directory, self.frozen_root, self.batch_root, self.dotnet,
                               batch_sha=self.batch_sha, public_release=self.public_release)
        result = build.execute_build()
        self.report["inputs"]["net9Build"] = artifact(build.report_path, self.evidence) | {"exitCode": result}
        require(result == 0, f".NET 9 R5 干净构建退出 {result}，详见 {build.report_path}")


class PatchNet10Runtime(PatchUpgrade):
    """在新库或固定运行时同库上复用构建、SQL、浏览器和进程核对。"""

    def __init__(self, *args, batch_sha, action, r4_batch_root, public_inputs, public_release=None):
        self.action = action
        self.r4_batch_root = r4_batch_root
        self.r4_public_inputs = public_inputs
        super().__init__(*args, batch_sha=batch_sha, public_release=public_release)
        self.phases = SWITCH_PHASES if action == "switch" else ("install",)
        self.builds = {phase: self.evidence / f"{phase}-build" if phase in ("public", "rollback") else self.evidence
                       for phase in self.phases}
        self.report.update(profile=f"{PROFILE}-{action}", coverageNotRun=[
            "备份恢复", "其他集合业务、平台、Provider、CI 和部署"])
        self.runtime_steps = [("runtime_inputs", self.inputs), ("observer_build", self.build_observer),
                              ("angular_freeze", self.angular), ("sql_preflight", self.sql_preflight)]
        for phase in self.phases:
            self.runtime_steps.append((phase, lambda phase=phase: self.run_phase(phase)))
        self.report["stages"] = {
            name: self.report["stages"].get(name, {"status": "not_run", "exitCode": None,
                                                  "commands": [], "evidence": []})
            for name in (*(name for name, _ in self.build_steps()), *("build_" + phase for phase in self.builds
                       if self.builds[phase] != self.evidence), *(name for name, _ in self.runtime_steps),
                       "cleanup", "frozen_inputs_after")
        }
        self.save()

    def execute_full(self):
        public_builds = [("build_" + phase, lambda phase=phase: self.build_public(phase))
                         for phase, directory in self.builds.items() if directory != self.evidence]
        return self.execute_steps((*self.build_steps(), *public_builds, *self.runtime_steps))

    def build_public(self, phase):
        directory = self.builds[phase]
        directory.mkdir()
        build = Net10Build(self.repo, directory, self.frozen_root, self.r4_batch_root, self.dotnet,
                           public_inputs=self.r4_public_inputs)
        code = build.execute_build()
        self.report["inputs"].setdefault("publicBuilds", {})[phase] = artifact(build.report_path, self.evidence) | {
            "exitCode": code}
        require(code == 0, f"{phase} R4 公开源构建退出 {code}，详见 {build.report_path}")
        require(build.downloads == self.downloads, f"{phase} R4 公开下载登记与 R5 十包输入不符")

    def sql_preflight(self):
        self.sql_inputs()
        sql = self.report["sql"] = self.db.preflight()
        sql["emptyDatabase"] = self.db.create_source()
        sql["databaseIdentity"] = self.db.state_identity(self.db.source)

    def entry_output(self, phase, entry):
        directory = self.builds[phase]
        manifest = directory / f"{entry}-output.json"
        reference = self.report["inputs"]["entryOutputs"][phase][entry]
        require(artifact(manifest, self.evidence) == reference, f"{phase} {entry} 构建清单已改变")
        output = directory / "source/aspnet-core" / project_path(entry).parent / "bin/Release/net10.0"
        return output, read_json(manifest)

    def verify_loaded(self, phase, label, entry, launch):
        directory = self.builds[phase]
        report = self.report if directory == self.evidence else read_json(directory / "report.json")
        reference = report["inputs"]["r4BuildAssets"]
        bindings = directory / reference["path"]
        require(artifact(bindings, directory) == reference, f"{phase} {entry} 构建对账已改变")
        observation = self.evidence / f"{label}-{ENTRY_LABELS[entry]}-loaded.json"
        observed = read_json(observation)
        result = verify_process(read_json(bindings)[entry], launch, observed)
        output, manifest = self.entry_output(phase, entry)
        loaded = {}
        if entry == "Web.Host":
            verify_host_assemblies(observed, launch, output, manifest, loaded, runtime_version=PATCH_VERSION)
        else:
            verify_migrator_assemblies(observed, launch, output, manifest, loaded, PATCH_VERSION)
        path = self.evidence_file(f"{label}-{ENTRY_LABELS[entry]}-assets.json")
        write_json(path, result | {"runtimeVerification": loaded, "observation": artifact(observation, self.evidence)})
        return artifact(path, self.evidence)

    def migrate_phase(self, phase, record):
        self.phase = phase
        launch, log = self.launch_migrator(phase, self.db.source)
        record["migrator"] = launch
        require(launch["exitCode"] == 0, f"{phase} Migrator 退出 {launch['exitCode']}，详见 {log}")
        launch["sharedRuntime"] = shared_runtime_trace(log, "Migrator")
        evidence = self.evidence / f"{phase}-migrator-target.jsonl"
        events = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines()]
        check_migration_target(events, launch["pid"], self.db.identity["serverName"], self.db.source)
        record["migrationTarget"] = {"events": len(events), "evidence": artifact(evidence, self.evidence)}
        record["migratorAssets"] = self.verify_loaded(phase, phase, "Migrator", launch)

    def read_user(self):
        user, = self.db.query(self.db.source, """
SELECT Id AS id, TenantId AS tenantId, UserName AS userName, Name AS name, Surname AS surname,
       EmailAddress AS emailAddress, IsActive AS isActive, CreatorUserId AS creatorUserId,
       CONVERT(nvarchar(33), CreationTime, 126) AS creationTime
FROM dbo.AbpUsers WHERE TenantId = %s AND UserName = %s AND IsDeleted = 0
""", (self.business["tenant"]["tenantId"], self.business["keyword"]))
        return user

    def add_user(self, phase, seed, record):
        self.phase = f"{phase}-write"
        self.request_id = ""
        self.request_log = self.evidence_file(f"{self.phase}-host-search.jsonl")
        keyword = "r5user" + self.run_id
        with self.launch_host(self.db.source, "host-" + self.phase) as writer:
            record["writer"] = writer
            expected = self.create_fixture_user(seed, keyword)
        record["writerAssets"] = self.verify_loaded(phase, self.phase, "Web.Host", writer)
        migrations = [row["migrationId"] for row in seed["migrations"]]
        self.business = self.db.business(self.db.source, migrations, keyword, expected)
        user = self.read_user()
        values = {"name": "Runtime", "surname": "Fixture", "emailAddress": f"{keyword}@example.invalid",
                  "isActive": True}
        require(user["id"] == expected["id"] and user["creatorUserId"] == seed["account"]["userId"]
                and user["creationTime"] and all(user[field] == value for field, value in values.items()),
                f"{phase} 数据库中的业务记录与创建请求不符")
        self.business.update(searchFields=USER_FIELDS, matches=[expected | values])
        self.fixture = user

    def run_phase(self, phase):
        sql = self.report["sql"]
        database = self.db.source
        record = sql.setdefault("phases", {})[phase] = {"databaseBefore": self.db.state_identity(database)}
        require(record["databaseBefore"] == sql["databaseIdentity"], f"{phase} 启动前数据库身份改变")
        first = phase == self.phases[0]
        if not first:
            require(self.read_user() == self.fixture, f"{phase} 迁移前业务记录改变")
            record["beforeMigration"] = self.db.successful_logins(database, self.business)
        self.migrate_phase(phase, record)
        migration_dir = self.root / project_path("EntityFrameworkCore").parent / "Migrations"
        migrations = sorted(path.stem for path in migration_dir.glob("[0-9]*.cs")
                            if not path.name.endswith(".Designer.cs"))
        require(len(migrations) == 30, "固定模板迁移数与 30 条基线不符")
        seed = record["seed"] = self.db.seed(database, migrations)
        self.output, self.host_output = self.entry_output(phase, "Web.Host")
        self.host_inventory = self.host_output["files"]
        self.report["inputs"]["host"] = {"entry": artifact(self.output / self.host_output["entry"]["path"],
                                                           self.evidence)}
        record["afterMigration"] = self.db.successful_logins(database, seed)
        if first:
            require(not record["afterMigration"], f"{phase} 新库在业务前已有成功登录行")
            self.catalog = self.db.catalog(database)
            self.add_user(phase, seed, record)
        else:
            require(record["beforeMigration"] == record["afterMigration"] and self.read_user() == self.fixture,
                    f"{phase} Migrator 改变登录记录或业务记录")
            require(seed == {key: self.business[key] for key in ("migrations", "tenant", "account")}
                    and self.db.catalog(database) == self.catalog, f"{phase} 迁移历史、授权或目录改变")
        record["catalog"] = {kind: len(rows) for kind, rows in self.catalog.items()}
        catalog_path = self.evidence_file(f"{phase}-catalog.json")
        write_json(catalog_path, self.catalog)
        record["catalogFile"] = artifact(catalog_path, self.evidence)
        record["beforeBrowser"] = self.db.successful_logins(database, self.business)
        require(len(record["beforeBrowser"]) == len(record["afterMigration"]) + int(first)
                and record["beforeBrowser"][:len(record["afterMigration"])] == record["afterMigration"],
                f"{phase} 业务创建的登录写入增量不符")
        self.phase = phase
        outcome = self.round(database, phase)
        record["hostAssets"] = self.verify_loaded(phase, phase, "Web.Host", outcome["host"])
        record["afterBrowser"] = self.db.successful_logins(database, self.business)
        require(record["afterBrowser"][:-1] == record["beforeBrowser"]
                and len(record["afterBrowser"]) == len(record["beforeBrowser"]) + 1,
                f"{phase} 浏览器登录写入增量不符")
        record["user"] = self.read_user()
        record["databaseAfter"] = self.db.state_identity(database)
        require(record["user"] == self.fixture and record["databaseAfter"] == sql["databaseIdentity"]
                and self.db.seed(database, migrations) == seed, f"{phase} 业务记录、权限、迁移或数据库身份改变")
        if phase == self.phases[-1]:
            sql["finalBackup"] = self.db.backup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "upgrade", "install", "switch"))
    parser.add_argument("--batch-root", required=True, type=Path)
    parser.add_argument("--batch-sha256", required=True)
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--dotnet", type=Path)
    parser.add_argument("--runtime-config", type=Path)
    parser.add_argument("--r4-batch-root", type=Path)
    parser.add_argument("--release-manifest", type=Path)
    parser.add_argument("--verified-downloads", type=Path)
    parser.add_argument("--manifest-sha256", help="启用纯 nuget.org 模式并固定发行清单")
    parser.add_argument("--downloads-sha256", help="独立登记的已验签公开下载摘要")
    parser.add_argument("--nuget-config", type=Path, help="可选的纯 nuget.org 配置，须和默认隔离配置等价")
    parser.add_argument("--tfm", choices=("net9.0", "net10.0"), default="net9.0")
    args = parser.parse_args()
    if args.action != "build" and args.runtime_config is None:
        parser.error(f"{args.action} 需要 --runtime-config")
    if args.action == "switch" and not all((args.r4_batch_root, args.release_manifest, args.verified_downloads)):
        parser.error("switch 需要 --r4-batch-root、--release-manifest 和 --verified-downloads")
    public_release = None
    if any((args.manifest_sha256, args.downloads_sha256, args.nuget_config)) or (
            args.action != "switch" and (args.release_manifest or args.verified_downloads)):
        if args.action == "switch" or not all((args.release_manifest, args.manifest_sha256,
                                               args.verified_downloads, args.downloads_sha256)):
            parser.error("纯 nuget.org 模式支持 build、install、upgrade，需要发行清单、下载登记及二者的独立 SHA-256")
        public_release = PublicReleaseInputs(args.release_manifest.resolve(), args.manifest_sha256,
                                            args.verified_downloads.resolve(), args.downloads_sha256,
                                            args.nuget_config.resolve() if args.nuget_config else None)
    for name in ("DEBUG", "PWDEBUG"):
        os.environ.pop(name, None)
    directory = make_run_directory(args.evidence_root.resolve(), f"{PROFILE}-{args.action}-")
    inputs = ROOT, directory, args.frozen_root.resolve(), args.batch_root.resolve()
    if args.action == "build":
        build = PatchNet9Build if args.tfm == "net9.0" else PatchNet10Build
        run = build(*inputs, args.dotnet, batch_sha=args.batch_sha256, public_release=public_release)
    elif args.action == "upgrade":
        run = PatchUpgrade(*inputs, args.runtime_config.resolve(), args.dotnet, batch_sha=args.batch_sha256,
                           public_release=public_release)
    else:
        public_inputs = None
        if args.action == "switch":
            public_inputs = (args.release_manifest.resolve(), args.verified_downloads.resolve())
        r4_batch_root = args.r4_batch_root.resolve() if args.r4_batch_root else None
        run = PatchNet10Runtime(*inputs, args.runtime_config.resolve(), args.dotnet, batch_sha=args.batch_sha256,
                                action=args.action, r4_batch_root=r4_batch_root, public_inputs=public_inputs,
                                public_release=public_release)
    print(f"{PROFILE} report: {run.report_path}", flush=True)
    return run.execute_build() if args.action == "build" else run.execute_full()


if __name__ == "__main__":
    raise SystemExit(main())
