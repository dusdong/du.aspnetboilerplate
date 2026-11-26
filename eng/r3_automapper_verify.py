"""从冻结的 R3 映射和 Module Zero 实物复验独立消费及模板映射。"""

from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import sys
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from r2_packages import NUGET_SOURCE, write_json
from r2_verify import ERRORS
from r3_automapper_business import (APP, CONSUMER_FILES, OriginalBusinessRun, STAGES, prepare_business_project)
from r3_automapper_packages import (ADAPTER, ADAPTER_MANIFEST, COLLECTION, CORE, ENGINE, ENGINE_MANIFEST,
                                   SQLITE, SQLITE_VERSION, ZERO, check_archive, check_assets, check_loaded,
                                   mapping_packages, record, zero_packages)
from r3_leaf_assets import verify_selected_owners
from r3_leaf_packages import TFM, checked_file
from verify import ROOT, R0Run, VerificationError, make_run_directory, read_json, require, sha256


PROFILE = "r3-automapper"
RUNTIME = ".NET 9.0.23"
PROFILE_STAGES = ("inputs", "minimal", "original", "candidate", "compare", "diagnostics")
MINIMAL = "AutoMapperMinimal"


class CandidateRun(OriginalBusinessRun):
    public_packages = ()

    def __init__(self, evidence, dotnet, frozen, edges, *, minimal=False, omit=()):
        self.app = MINIMAL if minimal else APP
        self.profile = f"{PROFILE}-{self.app}"
        self.frozen, self.edges, self.omit = frozen, edges, omit
        self.feed = evidence / "feed"
        self.direct = {ADAPTER: frozen[ADAPTER]["version"]}
        self.properties = [f"-p:AdapterVersion={self.direct[ADAPTER]}"]
        if not minimal:
            self.direct.update({ZERO: frozen[ZERO]["version"], SQLITE: SQLITE_VERSION})
            self.properties.extend([f"-p:AdapterPackage={ADAPTER}", f"-p:ZeroPackage={ZERO}",
                                    f"-p:ZeroVersion={self.direct[ZERO]}"])
        super().__init__(evidence, dotnet)
        self.cache = Path(self.env["NUGET_PACKAGES"])

    def prepare_project(self):
        if self.app != MINIMAL:
            return prepare_business_project(self, self.work)
        self.work.mkdir()
        sources = [ROOT / "validation/automapper-minimal" / name for name in (self.project.name, "Program.cs")]
        sources.extend(ROOT / "validation/automapper" / name for name in ("global.json", "ProbeModule.cs"))
        return {"consumerFiles": {source.name: sha256(Path(shutil.copyfile(source, self.work / source.name)))
                                  for source in sources}}

    def write_nuget_config(self):
        self.feed.mkdir()
        for name, package in self.frozen.items():
            if name not in self.omit and name not in self.public_packages:
                path = Path(package["archive"])
                copied = Path(shutil.copyfile(path, self.feed / path.name))
                require(sha256(copied) == package["archiveSha256"], f"{name} 受控源复制摘要不符")
        config = ET.Element("configuration")
        sources = ET.SubElement(config, "packageSources")
        ET.SubElement(sources, "clear")
        ET.SubElement(sources, "add", key="frozen", value=str(self.feed))
        ET.SubElement(sources, "add", key="nuget.org", value=NUGET_SOURCE)
        ET.SubElement(ET.SubElement(config, "fallbackPackageFolders"), "clear")
        mapping = ET.SubElement(config, "packageSourceMapping")
        ET.SubElement(mapping, "clear")
        frozen = ET.SubElement(mapping, "packageSource", key="frozen")
        for name in self.frozen:
            if name not in self.public_packages:
                ET.SubElement(frozen, "package", pattern=name)
        public = ET.SubElement(mapping, "packageSource", key="nuget.org")
        ET.SubElement(public, "package", pattern="*")
        ET.indent(config, space="  ")
        ET.ElementTree(config).write(self.evidence_file("consumer/NuGet.Config"), encoding="utf-8")

    def packages(self):
        self.graph = check_assets(read_json(self.assets), self.project, self.cache, self.feed, self.frozen,
                                  self.direct, self.edges, public_packages=self.public_packages)
        write_json(self.evidence_file("package-graph.json"), self.graph)

    def acceptance(self):
        environment = self.probe["environment"]
        require(environment["RuntimeIdentifier"] == "osx-arm64" and environment["FrameworkDescription"] == RUNTIME,
                f"实际运行环境不符：{environment}")
        self.report["environment"]["process"] = environment
        write_json(self.evidence_file("assemblies-verified.json"),
                   check_loaded(self.probe, self.output, self.cache, self.app, self.frozen, self.graph["packages"]))
        if self.app == MINIMAL:
            mapping = self.probe["mapping"]
            require(mapping["castle"] == "Abp.AutoMapper.AutoMapperObjectMapper" and
                    mapping["staticMapped"] == {"Key": 10, "Value": "updated"} and
                    mapping["collection"] == [{"Key": 10, "Value": "updated"}, {"Key": 30, "Value": "inserted"}],
                    "缺少完整 Castle、静态映射或按键集合结果")
        else:
            require(set(row["Name"] for row in self.probe["assemblies"]) >= {SQLITE, "Microsoft.Data.Sqlite"},
                    "实际运行缺少 SQLite Provider 或驱动")
            result = {key: self.probe[key] for key in ("configuration", "user", "collection", "projection")}
            require(all(result.values()), "候选缺少业务断言结果")
            write_json(self.evidence_file("business-result.json"), result)


def sql_semantics(query):
    sql = query["Sql"].partition("\n")[2]
    source = re.search(r'\bFROM\s+"Users"\s+AS\s+("(?:[^"]|"")+")', sql, re.IGNORECASE)
    require(source is not None, "SQLite 执行 SQL 缺少 Users 表及其别名")
    alias = source[1]
    sql = sql[:source.start(1)] + '"u"' + sql[source.end(1):]
    sql = re.sub(rf'{re.escape(alias)}\s*\.', '"u".', sql, flags=re.IGNORECASE)
    parameters = []
    for index, row in enumerate(query["Parameters"]):
        sql = sql.replace(row["Name"], f":parameter{index}")
        parameters.append((row["DbType"], row["Value"]))
    sql = re.sub(r'\s*([,.=])\s*', r'\1', " ".join(sql.split()))
    sql = re.sub(r'("u"\."Id")\s+ASC\Z', r'\1', sql, flags=re.IGNORECASE)
    return {"sql": sql, "parameters": parameters, "columns": query["Columns"]}


def compare_projection(original, candidate):
    required = {"provider", "providerVersion", "sqliteVersion", "expression", "fullName", "executed", "result"}
    require(set(original) == set(candidate) == required, "SQLite 证据缺失")
    # 表达式文本供回看。C# 已检查 Select 和 FullName 的真实成员绑定。
    require(all(isinstance(row["expression"], str) and row["expression"].strip() for row in (original, candidate)),
            "缺少 SQLite 原始投影表达式")
    for name in sorted(required - {"executed", "expression"}):
        require(original[name] and original[name] == candidate[name], f"SQLite {name} 原版和候选不同")
    require(candidate["provider"] == SQLITE and candidate["providerVersion"] == SQLITE_VERSION + ".0",
            "实际 SQLite Provider 或程序集版本不符")
    sql = sql_semantics(candidate["executed"])
    require(sql_semantics(original["executed"]) == sql, "SQLite 实际 SQL 的筛选、排序、取列或参数与原版不同")
    return sql


def compare_business(original, candidate):
    require(original["inputs"] == candidate["inputs"], "原版与候选编译的模板或验收源码不一致")
    expected_stages = {stage: ("passed", 0) for stage in STAGES}
    for report in (original, candidate):
        require({name: (stage["status"], stage["exitCode"]) for name, stage in report["stages"].items()} ==
                expected_stages and report["exitCode"] == 0, "原版或候选存在未执行或失败阶段")
    process = [report["environment"]["process"] for report in (original, candidate)]
    require(all(row["RuntimeIdentifier"] == "osx-arm64" and row["FrameworkDescription"] == RUNTIME for row in process)
            and process[0]["processId"] != process[1]["processId"], "原版与候选的运行时或进程隔离不符")


def diagnose_fixture(case, path):
    fixture = read_json(path)
    try:
        if case == "digest":
            phase = "inputs"
            archive = Path(fixture["path"])
            checked_file(archive.parent, archive.name, fixture["sha256"])
        elif case == "minimum-version":
            phase = "inputs/nuspec"
            check_archive(fixture["path"], fixture["package"], fixture["edges"])
        elif case == "asset-conflict":
            phase = "packages/assets"
            verify_selected_owners(read_json(Path(fixture["graph"])), fixture["owner"], fixture["asset"])
        else:
            return 2
    except VerificationError as error:
        print(f"{phase}: {error}", file=sys.stderr)
        return 1
    return 0


class AutoMapperRun(R0Run):
    def __init__(self, evidence, args):
        super().__init__(ROOT, evidence)
        self.args = args
        self.dotnet = args.dotnet.resolve()
        self.report.update(profile=PROFILE, stages={name: {"status": "not_run", "exitCode": None, "commands": [],
                                                           "evidence": []} for name in PROFILE_STAGES},
                           scope={"result": "下游冻结实包消费",
                                  "engineGate": "OpenSpec 2.2 以独立引擎验收记录为准（docs/maintenance/r3-automapper-engine.md）",
                                  "excluded": ["OpenSpec 2.2 引擎准入验收",
                                               "固定 Web.Host 候选缺口统计（docs/maintenance/fork-roadmap.md）",
                                               "完整 Web.Host", "真实登录", "SQL Server", "Angular",
                                               ".NET 10", "其他平台", "升级与回退", "公开发行与部署"]})
        self.save()

    def inputs(self):
        args = self.args
        self.mapping = mapping_packages(args.engine_manifest.resolve(), args.candidate_manifest.resolve(),
                                        args.r2_feed.resolve())
        self.business = self.mapping | zero_packages(self, args.module_zero_feed.resolve())
        all_edges = {ADAPTER: {name: f"[{self.mapping[name]['version']}]" for name in (COLLECTION, ENGINE, CORE)},
                     COLLECTION: {ENGINE: f"[{self.mapping[ENGINE]['version']}]"}}
        self.edges = all_edges | {name: {dep: value for dep, value in package.get("dependencies", {}).items()
                                         if dep in self.business}
                                  for name, package in self.business.items() if name not in all_edges}
        for name in (ADAPTER, COLLECTION, ENGINE):
            package = self.mapping[name]
            package["dependencies"] = check_archive(package["archive"], package, self.edges[name])
        files = [Path(__file__), ROOT / "eng/r3_automapper_packages.py", ROOT / "eng/r3_automapper_business.py",
                 ROOT / "eng/verify.py", *(ROOT / "validation/automapper" / file for file in CONSUMER_FILES),
                 *(ROOT / "validation/automapper-minimal" / file for file in (f"{MINIMAL}.csproj", "Program.cs"))]
        manifests = (("engine", args.engine_manifest.resolve(), ENGINE_MANIFEST),
                     ("downstream", args.candidate_manifest.resolve(), ADAPTER_MANIFEST),
                     ("r2", args.r2_feed.resolve().parent / "manifest.json", None),
                     ("moduleZero", args.module_zero_feed.resolve().parent / "manifest.json", None))
        self.report["inputs"].update(
            manifests={name: record(path, digest or sha256(path)) for name, path, digest in manifests},
            packages=self.business, edges=self.edges, verificationFiles={str(file.relative_to(ROOT)): sha256(file) for file in files},
            git=self.git(ROOT, "head.log", "rev-parse", "HEAD"),
        )

    def run_consumer(self, runner):
        child = runner.report_path.relative_to(self.evidence).as_posix()
        self.evidence_file(child)
        require(runner.execute() == 0, f"消费者失败，详见 {runner.report_path}")
        self.stage["consumerReport"] = record(runner.report_path, sha256(runner.report_path))

    def minimal(self):
        self.minimal_run = CandidateRun(make_run_directory(self.evidence, "minimal-"), self.dotnet, self.mapping,
                                        self.edges, minimal=True)
        self.run_consumer(self.minimal_run)

    def original(self):
        self.original_run = OriginalBusinessRun(make_run_directory(self.evidence, "original-"), self.dotnet)
        self.run_consumer(self.original_run)

    def candidate(self):
        self.candidate_run = CandidateRun(make_run_directory(self.evidence, "candidate-"), self.dotnet,
                                          self.business, self.edges)
        self.run_consumer(self.candidate_run)

    def compare(self):
        original, candidate = self.original_run, self.candidate_run
        compare_business(original.report, candidate.report)
        paths = [run.evidence / "business-result.json" for run in (original, candidate)]
        a, b = map(read_json, paths)
        require(a.keys() == b.keys() == {"configuration", "user", "collection", "projection"}, "缺少业务验证组")
        for name in ("configuration", "user", "collection"):
            require(a[name] == b[name] and a[name], f"{name} 原版和候选的原始结果不同")
        left, right = a["projection"], b["projection"]
        write_json(self.evidence_file("business-comparison.json"), {
            "original": record(paths[0], sha256(paths[0])), "candidate": record(paths[1], sha256(paths[1])),
            "inputs": original.report["inputs"], "matched": sorted(a), "projectionSql": compare_projection(left, right),
            "projectionFullName": right["fullName"], "projectionExpressionTextEqual": left["expression"] == right["expression"],
            "differences": [],
        })

    def diagnostics(self):
        directory = self.evidence / "diagnostics"
        directory.mkdir()
        results = {}

        def fails(name, phase, kind, inputs, fragments):
            fixture = self.evidence_file(f"diagnostics/{name}-inputs.json")
            write_json(fixture, inputs)
            code, log = self.command([sys.executable, "-B", Path(__file__).resolve(), name, fixture],
                                     directory, f"diagnostics/{name}.log", accepted=(1,))
            actual_stage, _, message = log.read_text().strip().partition(": ")
            require(actual_stage == phase and all(part in message for part in fragments),
                    f"{name} 错误诊断阶段或内容不符，详见 {log}")
            results[name] = {"kind": kind, "expectedStage": phase, "actualStage": actual_stage,
                             "expectedMessage": fragments, "actualMessage": message, "exitCode": code}

        engine = self.mapping[ENGINE]
        altered = directory / Path(engine["archive"]).name
        altered.write_bytes(Path(engine["archive"]).read_bytes() + b"diagnostic")
        fails("digest", "inputs", "摘要验证夹具",
              record(altered, engine["archiveSha256"]),
              (altered.name, "SHA-256 不符", engine["archiveSha256"], sha256(altered)))

        collection = self.mapping[COLLECTION]
        lowered = directory / Path(collection["archive"]).name
        exact = self.edges[COLLECTION][ENGINE]
        with ZipFile(collection["archive"]) as original, ZipFile(lowered, "w") as fixture:
            for item in original.infolist():
                contents = original.read(item)
                if item.filename.endswith(".nuspec"):
                    old, new = f'version="{exact}"', f'version="{engine["version"]}"'
                    require(contents.count(old.encode()) == 1, "最低版本夹具的原始声明不唯一")
                    contents = contents.replace(old.encode(), new.encode())
                fixture.writestr(item, contents)
        fails("minimum-version", "inputs/nuspec", "归档声明夹具",
              {"path": str(lowered), "package": collection, "edges": self.edges[COLLECTION]},
              (f"{COLLECTION} → {ENGINE}", exact, f"实际 {engine['version']}"))

        key = f"{ENGINE}/{engine['version']}"
        graph = read_json(self.minimal_run.assets)["targets"][TFM]
        graph["Diagnostic.OtherMapper/1.0.0"] = {"compile": {engine["asset"]: {}}, "runtime": {engine["asset"]: {}}}
        fixture_path = self.evidence_file("diagnostics/duplicate-assets.json")
        write_json(fixture_path, graph)
        fails("asset-conflict", "packages/assets", "还原图夹具",
              {"graph": str(fixture_path), "owner": key, "asset": engine["asset"]},
              ("AutoMapper.dll", "多来源", "Diagnostic.OtherMapper/1.0.0", key))

        missing = CandidateRun(make_run_directory(directory, "missing-"), self.dotnet, self.mapping, self.edges,
                               minimal=True, omit=(ENGINE,))
        missing.step("inputs", missing.inputs)
        try:
            missing.step("restore", missing.restore)
        except VerificationError as error:
            log = (missing.evidence / "restore.log").read_text()
            command = missing.report["stages"]["restore"]["commands"][-1]
            require(command["exitCode"] != 0 and re.search(r"NU110[12]:.*Du\.AutoMapper(?![.\w])", log),
                    f"缺包用例未得到预期 NuGet 否决，详见 {missing.evidence}")
            require(not (missing.cache / ENGINE.lower()).exists(), "缺包还原缓存已含引擎")
            missing.report.update(status="failed", exitCode=1, reason=str(error))
            missing.save()
            results["missing-engine"] = {"kind": "实际 restore", "expectedStage": "restore",
                                         "actualStage": "restore", "exitCode": command["exitCode"],
                                         "report": record(missing.report_path, sha256(missing.report_path))}
        else:
            raise VerificationError("实际还原在冻结传递引擎缺失时应失败")

        run = self.minimal_run
        # 复用正向构建的同一个 DLL，在新进程的第二个上下文加载相同字节。
        status, path, log = run.run_probe("diagnostics/duplicate-context", ("--duplicate-context",), reporter=self)
        info = read_json(path)
        rows = [row for row in info["assemblies"] if row["Name"] == "AutoMapper"]
        require(status == 1 and {row["LoadContext"] for row in rows} == {"Default", "diagnostic-duplicate"} and
                len(rows) == 2 and {row["Sha256"] for row in rows} == {engine["assetSha256"]} and
                {row["Path"] for row in rows} == {str(run.output / "AutoMapper.dll")} and
                "程序集加载失败" in log.read_text() and "实例数预期 1，实际 2" in log.read_text(),
                "跨上下文用例应由运行程序集实例检查在相同 DLL 字节下拒绝")
        results["duplicate-context"] = {"kind": "实际独立进程", "expectedStage": "process/程序集加载",
                                        "actualStage": "process/程序集加载", "exitCode": status,
                                        "probe": record(path, sha256(path)), "log": record(log, sha256(log)),
                                        "assemblies": rows}
        write_json(self.evidence_file("diagnostics/results.json"), results)

    def execute(self):
        try:
            for name in PROFILE_STAGES:
                self.step(name, getattr(self, name))
        except ERRORS as error:
            print(error, file=sys.stderr)
            self.report.update(status="failed", exitCode=1, reason=str(error))
        else:
            self.report.update(status="passed", exitCode=0)
        self.report["finishedAt"] = datetime.now(timezone.utc).isoformat()
        self.save()
        print(self.report_path)
        return self.report["exitCode"]


def execute(args):
    return AutoMapperRun(make_run_directory(args.evidence_root, "r3-automapper-"), args).execute()


if __name__ == "__main__":
    case, inputs = sys.argv[1:]
    raise SystemExit(diagnose_fixture(case, Path(inputs)))
