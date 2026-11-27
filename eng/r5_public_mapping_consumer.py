"""从独立空缓存验证公开 R4 与 R5 的映射业务。"""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
from zipfile import ZipFile

from r2_packages import NUGET_SOURCE, metadata_groups, nuspec_metadata, write_json
from r2_verify import ERRORS
from r3_automapper_business import APP, OriginalBusinessRun, verify_loaded_assemblies
from r3_automapper_packages import ADAPTER, COLLECTION, CORE, ENGINE, SQLITE, ZERO, check_edges, stack_package
from r3_automapper_verify import sql_semantics
from r3_leaf_packages import bytes_sha256
from r3_template_net9_packages import normalized_range
from r5_candidate_batch import VERSIONS
from r5_public_switch_assets import RELEASES, REPOSITORY, R4_VERSIONS, TAG_OBJECTS, TEMPLATE, TFM, compare_graphs
from verify import ROOT, read_json, require, sha256


SQLITE_VERSION = "10.0.15"
RUNTIME = ".NET 10.0.15"
ADAPTER_ASSEMBLIES = {ADAPTER: "Abp.AutoMapper", ENGINE: "AutoMapper", COLLECTION: "AutoMapper.Collection"}
COLUMNS = ROOT / "validation/automapper/projection-columns.json"
USER = {
    "targetRetained": True, "rolesRetained": True, "roleMemberRetained": True,
    "initialIsActive": False, "requestedIsActive": True, "IsActive": True,
    "Id": 27, "Name": "New", "Surname": "User", "UserName": "newuser", "EmailAddress": "new@example.invalid",
    "CreationTime": "2020-12-31T23:57:00Z", "requestedCreationTime": "2022-12-31T23:57:00Z",
    "requestedRoles": ["DifferentRole"],
    "roles": [{"Id": 46, "UserId": 27, "RoleId": 37, "TenantId": 4}],
    "createUser": {"UserName": "created", "IsActive": True, "ignoresRoles": True},
}
COLLECTION_RESULT = {
    "targetRetained": True, "matchingItemRetained": True, "newItemCreated": True, "oldItemRemoved": True,
    "items": [{"Key": 10, "Value": "updated"}, {"Key": 30, "Value": "inserted"}],
}
PROJECTION_ROWS = [
    {"Id": id_, "UserName": username, "Name": name, "Surname": surname, "FullName": f"{name} {surname}",
     "CreationTime": "2022-04-13T12:00:00", "IsActive": True, "EmailAddress": f"{username}@example.invalid",
     "RoleNames": None, "LastLoginTime": None}
    for id_, username, name, surname in ((12, "zulu", "Zoe", "Zulu"), (13, "beta", "Bea", "Beta"),
                                         (11, "alpha", "Ada", "Alpha"))
]
FULL_NAME = {"location": "client", "entityMember": "Abp.Authorization.Users.AbpUserBase.FullName",
             "mappedColumn": False}
SCENARIOS = ("user", "collection", "projection")
ASSET_METADATA = {"type", "dependencies", "frameworkReferences"}


def projection_result(actual):
    executed = actual.get("executed") or {}
    result = actual.get("result")
    rows = [{key: row[key] for key in PROJECTION_ROWS[0] if key in row} for row in result] if result else result
    parameters = executed.get("Parameters")
    return {
        "provider": actual.get("provider"), "providerVersion": actual.get("providerVersion"),
        "sqliteVersionRecorded": bool(actual.get("sqliteVersion")),
        "expressionRecorded": bool(actual.get("expression")),
        "sqlRecorded": bool(executed.get("Sql")), "fullName": actual.get("fullName"),
        "columns": executed.get("Columns"),
        "parameters": [[p.get("DbType"), p.get("Value")] for p in parameters] if parameters else parameters,
        "rows": rows,
    }


def assess_business(probe, columns):
    expected = {
        "user": USER,
        "collection": COLLECTION_RESULT,
        "projection": {
            "provider": SQLITE, "providerVersion": SQLITE_VERSION + ".0", "sqliteVersionRecorded": True,
            "sqlRecorded": True, "expressionRecorded": True, "fullName": FULL_NAME, "columns": columns,
            "parameters": [["Int32", 6]], "rows": PROJECTION_ROWS,
        },
    }
    result = {}
    for name in SCENARIOS:
        probe_status = (probe.get("scenarios") or {}).get(name)
        actual = probe.get(name)
        if name == "projection" and actual:
            actual = projection_result(actual)
        mismatches = {}
        if name in probe:
            for field, wanted in expected[name].items():
                observed = (actual or {}).get(field)
                if field not in (actual or {}) or type(wanted) is not type(observed) or observed != wanted:
                    mismatches[field] = {"expected": wanted, "actual": observed,
                                         "missing": field not in (actual or {})}
        status = "passed" if probe_status == "passed" and actual and not mismatches else "failed"
        if probe_status in (None, "not_run") and name not in probe:
            status = "not_run"
        result[name] = {"status": status, "probeStatus": probe_status, "expected": expected[name],
                        "actual": actual, "mismatches": mismatches}
    return result


def accepted_business(assessments):
    return all(assessments.get(name, {}).get("status") == "passed" for name in SCENARIOS)


def release_rows(release, attachment):
    tag, commit, _ = RELEASES[release]
    proof = read_json(attachment)
    require((proof["schemaVersion"], proof["repository"], proof["tag"], proof["commit"],
             proof["nugetSource"], proof["template"]["commit"]) ==
            (1, REPOSITORY, tag, commit, NUGET_SOURCE, TEMPLATE)
            and (release == "r4" or proof.get("tagObject") == TAG_OBJECTS[release]),
            f"{tag} 公开校验附件身份不符")
    return proof["packages"], proof.get("carriedPackages", {})


def package_graph(raw, project, cache, direct):
    restore = raw["project"]["restore"]
    require(Path(restore["projectPath"]) == project and Path(restore["packagesPath"]) == cache
            and set(raw["packageFolders"]) == {str(cache)}
            and list(restore["sources"]) == [NUGET_SOURCE] and not restore.get("fallbackFolders")
            and restore["configFilePaths"] == [str(project.parent / "NuGet.Config")],
            "实际项目、包源、配置或独立包缓存不符")
    require(set(raw["targets"]) == {TFM} and restore["originalTargetFrameworks"] == [TFM]
            and not restore["frameworks"][TFM]["projectReferences"], "实际目标框架或项目引用不符")
    references = raw["project"]["frameworks"][TFM]["dependencies"]
    require(references == {name: {"target": "Package", "version": f"[{version}, {version}]"}
                           for name, version in direct.items()}, f"直接包声明不符：{references}")
    target = raw["targets"][TFM]
    require(set(target) == set(raw["libraries"]), "目标包图与 NuGet libraries 不相符")
    packages = {}
    for identity, node in sorted(target.items()):
        name, version = identity.split("/")
        library = raw["libraries"][identity]
        require(node["type"] == library["type"] == "package" and name not in packages
                and library["path"] == f"{name.lower()}/{version}", f"{identity} 包图记录不符")
        directory = cache / library["path"]
        archive = directory / f"{name.lower()}.{version}.nupkg"
        metadata = read_json(directory / ".nupkg.metadata")
        require(metadata["source"].rstrip("/") == NUGET_SOURCE.rstrip("/") and
                metadata["contentHash"] == library["sha512"], f"{identity} 的缓存元数据来源或摘要不符")
        packages[name] = node | {"version": version, "archive": str(archive), "sha256": sha256(archive),
                                 "contentSha512": library["sha512"], "source": metadata["source"]}
    return packages


def graph_for_comparison(packages, direct):
    return {
        "nodes": {name: {key: row[key] for key in ("version", "sha256", "contentSha512", "source")}
                  | {"frameworkReferences": row.get("frameworkReferences", [])}
                  for name, row in packages.items()},
        "edges": {(p, dep): normalized_range(value) for p, row in packages.items()
                  for dep, value in row.get("dependencies", {}).items()} |
                 {(APP, name): normalized_range(f"[{version}]") for name, version in direct.items()},
        "assets": {(name, role): selections for name, row in packages.items() for role, selections in row.items()
                   if role not in ASSET_METADATA | {"version", "archive", "sha256", "contentSha512", "source"}},
    }


class PublicRun(OriginalBusinessRun):
    profile = "r5-public-mapping-consumer"
    target_framework = TFM

    def __init__(self, evidence, dotnet, release, attachment, columns):
        super().__init__(evidence, dotnet)
        self.release, self.attachment, self.columns_file = release, attachment, columns
        self.tag = RELEASES[release][0]
        self.versions = R4_VERSIONS if release == "r4" else VERSIONS
        self.direct = {ADAPTER: self.versions[ADAPTER], ZERO: "10.5.1", SQLITE: SQLITE_VERSION}
        self.properties = [f"-p:TargetFramework={TFM}", "-p:RuntimeFrameworkVersion=10.0.15",
                           f"-p:AdapterPackage={ADAPTER}", f"-p:AdapterVersion={self.direct[ADAPTER]}",
                           f"-p:ZeroPackage={ZERO}", f"-p:ZeroVersion={self.direct[ZERO]}",
                           f"-p:SqliteVersion={SQLITE_VERSION}"]
        self.probe = {}
        self.probe_exit = None
        self.report.update(release=self.release, tag=self.tag, probeExitCode=None,
                           inputQualification={"status": "not_run"}, business=assess_business({}, []))
        self.env.update(DOTNET_ROLL_FORWARD="Disable", TMPDIR=str(self.evidence / "tmp"))
        (self.evidence / "tmp").mkdir()
        self.save()

    def step(self, name, action, *args):
        try:
            super().step(name, action, *args)
        except ERRORS as error:
            if self.report["inputQualification"]["status"] != "passed":
                self.report["inputQualification"] = {"status": "failed", "stage": name, "reason": str(error)}
            raise

    def inputs(self):
        super().inputs()
        attachment = self.evidence_file("release-checksums.json")
        shutil.copyfile(self.attachment, attachment)
        self.release_packages, self.carried_packages = release_rows(self.release, attachment)
        self.report["inputs"]["releaseAttachment"] = {
            "path": str(attachment), "sha256": sha256(attachment), "expectedSha256": RELEASES[self.release][2],
        }
        target = self.evidence_file("expected-projection-columns.json")
        shutil.copyfile(self.columns_file, target)
        self.columns = read_json(target)
        require(isinstance(self.columns, list) and self.columns and
                all(isinstance(value, str) for value in self.columns), "预期 SQLite 取列须为非空字符串列表")
        self.report["inputs"]["expectedProjectionColumns"] = {"path": str(target), "sha256": sha256(target)}
        self.report["business"] = assess_business({}, self.columns)

    def packages(self):
        self.graph = package_graph(read_json(self.assets), self.project, Path(self.env["NUGET_PACKAGES"]), self.direct)
        write_json(self.evidence_file("package-graph.json"), {"direct": self.direct, "packages": self.graph})
        required = self.versions | {CORE: "10.5.1", ZERO: "10.5.1", "Du.Abp.Zero.Common": "10.5.1",
                                    SQLITE: SQLITE_VERSION, SQLITE + ".Core": SQLITE_VERSION}
        for name, version in required.items():
            require(self.graph.get(name, {}).get("version") == version,
                    f"{self.tag} {name} 期望解析 {version}，实际 {self.graph.get(name, {}).get('version')}")
        verified = {}
        for name, row in self.graph.items():
            if not stack_package(name):
                continue
            require(name.startswith("Du.") and name in self.release_packages.keys() | self.carried_packages.keys(),
                    f"{self.tag} {name} 不在公开维护包清单")
            carried = name in self.carried_packages
            disclosed = self.carried_packages[name] if carried else self.release_packages[name]
            expected = disclosed.get("mainPackage", disclosed)["anonymousDownloadSha256"]
            require((row["version"], row["sha256"]) == (disclosed["version"], expected),
                    f"{self.tag} {name}/{row['version']} 签后主包 SHA-256 不符，预期 "
                    f"{disclosed['version']} {expected}，实际 {row['sha256']}")
            verified[name] = {"version": row["version"], "sha256": expected, "carried": carried,
                              "archive": row["archive"]}
        # 先报告实际消费包的差异，校验附件原件绑定仍须在允许构建前通过。
        attachment = self.report["inputs"]["releaseAttachment"]
        require(attachment["sha256"] == attachment["expectedSha256"],
                f"{self.tag} 公开校验附件 SHA-256 不符，预期 {attachment['expectedSha256']}，实际 {attachment['sha256']}")
        write_json(self.evidence_file("verified-public-archives.json"), verified)

        self.mapping_assets = {}
        edges = {ADAPTER: {CORE: "[10.5.1]", ENGINE: f"[{self.versions[ENGINE]}]",
                           COLLECTION: f"[{self.versions[COLLECTION]}]"},
                 COLLECTION: {ENGINE: f"[{self.versions[ENGINE]}]"}}
        for name, assembly in ADAPTER_ASSEMBLIES.items():
            row = self.graph[name]
            asset, = [p for p in row["runtime"] if Path(p).name == f"{assembly}.dll"]
            archive_path = row["archive"]
            with ZipFile(archive_path) as archive:
                metadata = nuspec_metadata(archive)
                require((metadata.findtext("id"), metadata.findtext("version")) == (name, row["version"]),
                        f"{self.tag} {name} 主包内部身份不符")
                group = metadata_groups(metadata, "dependencies", "id").get(Path(asset).parts[1], {})
                nuspec_edges = {dep: entry["version"] for dep, entry in group.items()}
                check_edges(name, nuspec_edges, edges.get(name, {}))
                check_edges(name, row.get("dependencies", {}), edges.get(name, {}), assets=True)
                require(archive.namelist().count(asset) == 1, f"{self.tag} {name} 运行资产 {asset} 不唯一")
                digest = bytes_sha256(archive.read(asset))
            self.mapping_assets[assembly] = {"package": name, "version": row["version"], "archive": archive_path,
                                              "asset": asset, "archiveAssetSha256": digest,
                                              "nuspecDependencies": nuspec_edges,
                                              "graphDependencies": row.get("dependencies", {})}
        write_json(self.evidence_file("mapping-assets.json"), self.mapping_assets)

    def build(self):
        super().build()
        self.evidence_file(f"consumer/bin/Release/{TFM}/{APP}.runtimeconfig.json")
        for assembly, detail in self.mapping_assets.items():
            output = self.output / f"{assembly}.dll"
            digest = sha256(output)
            require(digest == detail["archiveAssetSha256"], f"{self.tag} {assembly} 的 Release 输出摘要不符")
            detail.update(output=str(output), outputSha256=digest)
        write_json(self.evidence_file("mapping-output.json"), self.mapping_assets)

    def process(self):
        self.probe_exit, path, log = self.run_probe(arguments=(self.evidence / "expected-projection-columns.json",))
        self.report["probeExitCode"] = self.probe_exit
        require(path.is_file(), f"{self.tag} 实际消费者缺少报告，退出 {self.probe_exit}，详见 {log}")
        self.probe = read_json(path)
        observations = assess_business(self.probe, self.columns)
        for row in observations.values():
            row["observedStatus"] = row["status"]
            if row["status"] != "not_run":
                row["status"] = "unqualified"
        self.report["business"] = observations
        self.report["environment"]["process"] = self.probe["environment"]

    def acceptance(self):
        environment = self.probe["environment"]
        require((environment["RuntimeIdentifier"], environment["FrameworkDescription"],
                 environment["processArchitectureName"]) == ("osx-arm64", RUNTIME, "Arm64"),
                f"{self.tag} 预期 osx-arm64、{RUNTIME}、Arm64，实际 {environment}")
        loaded = verify_loaded_assemblies(self.probe, self.graph, self.output)
        write_json(self.evidence_file("assemblies-verified.json"), loaded)
        for assembly, detail in self.mapping_assets.items():
            actual = loaded[assembly]
            require((actual["archive"], actual["asset"], actual["Sha256"]) ==
                    (detail["archive"], detail["asset"], detail["archiveAssetSha256"]),
                    f"{self.tag} {assembly} 实际加载资产不符：{actual}")
            detail["loaded"] = actual
        write_json(self.evidence_file("mapping-loaded.json"), self.mapping_assets)
        self.report["inputQualification"] = {"status": "passed"}
        assessment = self.report["business"]
        for row in assessment.values():
            row["status"] = row["observedStatus"]
        failed = {name: row["status"] for name, row in assessment.items() if row["status"] != "passed"}
        require(self.probe_exit == 0 and accepted_business(assessment),
                f"{self.tag} 消费者退出 {self.probe_exit}，业务未通过项 {failed}，详见进程报告")

    def execute(self):
        try:
            return super().execute()
        except ERRORS as error:
            self.report.update(status="failed", exitCode=1, reason=str(error),
                               finishedAt=datetime.now(timezone.utc).isoformat())
            self.save()
            print(f"{self.tag} {error}", file=sys.stderr)
            return 1


def compare_runs(r4, r5, evidence):
    comparison = compare_graphs(*(graph_for_comparison(run.graph, run.direct) for run in (r4, r5)))
    write_json(evidence / "graph-difference.json", comparison)
    require(set(comparison["nodes"]) == R4_VERSIONS.keys() and not comparison["assets"],
            "两侧包图的包版本差异或资产选择超出约定，详见 graph-difference.json")
    expected_edges = {(APP, ADAPTER), (ADAPTER, ENGINE), (ADAPTER, COLLECTION), (COLLECTION, ENGINE)}
    require(set(comparison["edges"]) == {" → ".join(edge) for edge in expected_edges},
            "两侧的依赖区间差异超出约定，详见 graph-difference.json")
    require(r4.report["inputs"]["templateFiles"] == r5.report["inputs"]["templateFiles"]
            and r4.report["inputs"]["consumerFiles"] == r5.report["inputs"]["consumerFiles"], "两侧源码不同")
    if r4.probe and r5.probe:
        require(r4.probe["environment"]["processId"] != r5.probe["environment"]["processId"], "两侧进程未隔离")
        projections = [run.probe.get("projection", {}) for run in (r4, r5)]
        if all(projection.get("executed") for projection in projections):
            before, after = projections
            require(before["sqliteVersion"] == after["sqliteVersion"], "两侧实际 SQLite 引擎不同")
            require(sql_semantics(before["executed"]) == sql_semantics(after["executed"]),
                    "两侧实际 SQL 的筛选、排序、取列或参数不同")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for release in RELEASES:
        parser.add_argument(f"--{release}-checksums", type=Path, required=True)
        parser.add_argument(f"--{release}-projection-columns", type=Path, default=COLUMNS,
                            help="定向反例使用的预期取列副本")
    parser.add_argument("--dotnet", type=Path, default=shutil.which("dotnet"))
    parser.add_argument("--output", type=Path, required=True, help="尚不存在的验收输出目录")
    args = parser.parse_args()
    evidence = args.output.resolve()
    evidence.mkdir()
    runs = {}
    summary = {"command": [sys.executable, *sys.argv], "cwd": str(Path.cwd()),
               "startedAt": datetime.now(timezone.utc).isoformat(), "releases": {}}
    for release in RELEASES:
        directory = evidence / release
        directory.mkdir()
        run = PublicRun(directory, args.dotnet.resolve(), release, getattr(args, f"{release}_checksums"),
                        getattr(args, f"{release}_projection_columns"))
        runs[release] = run
        code = run.execute()
        summary["releases"][release] = {"tag": run.tag, "exitCode": code, "probeExitCode": run.probe_exit,
                                        "report": str(run.report_path),
                                        "inputQualification": run.report["inputQualification"],
                                        "business": {name: row["status"] for name, row in run.report["business"].items()},
                                        "reason": run.report.get("reason")}
    status = 1
    comparison = {"status": "not_run", "usableForVersionConclusion": False,
                  "reason": "两版尚未全部通过独立输入校验"}
    if all(run.report["inputQualification"]["status"] == "passed" for run in runs.values()):
        try:
            compare_runs(runs["r4"], runs["r5"], evidence)
        except ERRORS as error:
            comparison.update(status="failed", reason=str(error))
        else:
            status = int(any(row["exitCode"] != 0 for row in summary["releases"].values()))
            comparison.update(status="passed", usableForVersionConclusion=status == 0,
                              reason="至少一侧业务未通过独立验收" if status else None)
    summary["comparison"] = comparison
    summary.update(status="passed" if status == 0 else "failed", exitCode=status,
                   finishedAt=datetime.now(timezone.utc).isoformat())
    report = evidence / "report.json"
    write_json(report, summary)
    print(report)
    return status


if __name__ == "__main__":
    sys.exit(main())
