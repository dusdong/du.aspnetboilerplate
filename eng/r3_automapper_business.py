"""从固定模板和原版 NuGet 实包复验映射业务基线。"""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from zipfile import ZipFile

from r2_packages import NUGET_SOURCE, SDK, write_json
from r2_verify import environment
from r3_leaf_packages import bytes_sha256, TFM
from verify import ROOT, R0Run, VerificationError, make_run_directory, read_json, require, sha256


PROFILE = "r3-automapper-business-original"
TEMPLATE_COMMIT = "2e9536872673a7ff1986a19e798c51684d16afe5"
TEMPLATE_PROJECTS = "aspnet-core/src"
APP = "AutoMapperProbe"
APP_PROJECT = "AbpCompanyName.AbpProjectName.Application"
CORE_PROJECT = "AbpCompanyName.AbpProjectName.Core"
APPLICATION_MODULE = f"{APP_PROJECT}/AbpProjectNameApplicationModule.cs"
TEMPLATE_FILES = (
    *(f"{APP_PROJECT}/Users/Dto/{name}.cs" for name in ("UserMapProfile", "UserDto", "CreateUserDto")),
    f"{CORE_PROJECT}/Authorization/Users/User.cs",
    f"{CORE_PROJECT}/Authorization/Roles/Role.cs",
)
CONSUMER_FILES = (f"{APP}.csproj", "global.json", "ProbeModule.cs", "Program.cs", "Projection.cs",
                  "projection-columns.json")
STAGES = ("inputs", "restore", "packages", "build", "process", "acceptance")
DIRECT = {"Abp.AutoMapper": "10.2.0", "Abp.ZeroCore": "10.2.0", "Microsoft.EntityFrameworkCore.Sqlite": "9.0.18"}
ORIGINAL = DIRECT | {"Abp": "10.2.0", "Abp.Zero.Common": "10.2.0", "AutoMapper": "14.0.0",
                     "AutoMapper.Collection": "11.0.0", "Microsoft.EntityFrameworkCore.Sqlite.Core": "9.0.18"}
EDGES = {
    "Abp.AutoMapper": {"Abp": "10.2.0", "AutoMapper": "14.0.0", "AutoMapper.Collection": "11.0.0"},
    "AutoMapper.Collection": {"AutoMapper": "[14.0.0, 15.0.0)"},
    "Abp.ZeroCore": {"Abp.Zero.Common": "10.2.0"},
    "Abp.Zero.Common": {"Abp": "10.2.0"},
}


def prepare_business_project(run, directory):
    """为原版和候选分别使用 Git 固定模板对象与同一套消费者文件。"""
    directory.mkdir()
    template_path = directory / "template"
    template_path.mkdir()
    repository = ROOT / "module-zero-core-template"
    evidence = {"templateCommit": TEMPLATE_COMMIT, "templateFiles": {}, "consumerFiles": {}}
    for index, relative in enumerate((*TEMPLATE_FILES, APPLICATION_MODULE)):
        git_path = f"{TEMPLATE_PROJECTS}/{relative}"
        args = ["git", "-C", repository, "show", f"{TEMPLATE_COMMIT}:{git_path}"]
        compiled = relative != APPLICATION_MODULE
        # 保留真实模块配置原件，同时让独立进程只初始化映射所需的框架模块。
        output = str((template_path / Path(relative).name).relative_to(run.evidence)) if compiled else "template-application-module.cs"
        run.command(args, ROOT, f"template-{index}.log", output=output)
        file = run.evidence / output
        evidence["templateFiles"][git_path] = {"sha256": sha256(file), "compiled": compiled}
    module_text = (run.evidence / "template-application-module.cs").read_text(encoding="utf-8-sig")
    require("Configuration.Modules.AbpAutoMapper().Configurators.Add(" in module_text and
            "cfg => cfg.AddMaps(thisAssembly)" in module_text, "固定模板未使用预期的 Configurators/AddMaps")
    for name in CONSUMER_FILES:
        source = ROOT / "validation/automapper" / name
        copied = Path(shutil.copyfile(source, directory / name))
        evidence["consumerFiles"][name] = sha256(copied)
    return evidence


def original_graph(assets, cache):
    require([Path(path) for path in assets["packageFolders"]] == [cache], "还原图使用了额外的包缓存")
    project = assets["project"]
    require(list(project["restore"]["sources"]) == [NUGET_SOURCE], "还原图使用了未指定的包源")
    direct = project["frameworks"][TFM]["dependencies"]
    require(direct == {name: {"target": "Package", "version": f"[{version}, {version}]"}
                       for name, version in DIRECT.items()}, "原版消费者直接包声明有变化")
    target = assets["targets"][TFM]
    require(set(target) == set(assets["libraries"]), "目标包图与 NuGet libraries 不相符")
    packages = {}
    for identity, node in sorted(target.items()):
        name, version = identity.split("/")
        library = assets["libraries"][identity]
        require(node["type"] == library["type"] == "package" and name not in packages,
                f"{identity} 包记录不唯一")
        directory = cache / library["path"]
        archive = directory / f"{name.lower()}.{version}.nupkg"
        metadata = read_json(directory / ".nupkg.metadata")
        require(metadata["source"].rstrip("/") == NUGET_SOURCE.rstrip("/") and
                metadata["contentHash"] == library["sha512"], f"{identity} 的缓存元数据来源或摘要不符")
        packages[name] = node | {"version": version, "archive": str(archive), "sha256": sha256(archive)}
    for name, version in ORIGINAL.items():
        require(name in packages and packages[name]["version"] == version, f"原版包图缺少 {name}/{version}")
    require({name for name in packages if name.startswith(("Abp", "AutoMapper", "Du."))} ==
            {name for name in ORIGINAL if name.startswith(("Abp", "AutoMapper"))}, "映射栈或 ABP 闭包中存在额外包")
    for name, dependencies in EDGES.items():
        require(packages[name].get("dependencies") == dependencies, f"{name} 原版依赖边有变化")
    return {"direct": direct, "packages": packages}


def verify_loaded_assemblies(probe, packages, output):
    rows = {info["Name"]: info for info in probe["assemblies"]}
    expected = set(ORIGINAL) - {"Microsoft.EntityFrameworkCore.Sqlite.Core"}
    require(len(rows) == len(probe["assemblies"]) and expected <= rows.keys(),
        "原版运行加载的框架或映射程序集缺失或重复")
    evidence = {}
    for name, info in rows.items():
        file_name = name + ".dll"
        candidates = [(package, asset) for package in packages.values() for asset in package.get("runtime", {})
                      if Path(asset).name == file_name]
        require(len(candidates) == 1, f"包图中的 {file_name} 运行资产归属不唯一")
        package, asset = candidates[0]
        path = output / file_name
        require(Path(info["Path"]) == path and info["Sha256"] == sha256(path),
                f"{file_name} 实际加载位置或字节与 Release 输出不符")
        with ZipFile(package["archive"]) as archive:
            require(bytes_sha256(archive.read(asset)) == info["Sha256"], f"{file_name} 与归档资产不符")
        evidence[name] = info | {"archive": package["archive"], "asset": asset}
    return evidence


class OriginalBusinessRun(R0Run):
    profile = PROFILE
    app = APP
    properties = ()
    target_framework = TFM

    def __init__(self, evidence, dotnet):
        self.repo, self.evidence, self.dotnet = ROOT, evidence, dotnet
        self.report_path = evidence / "report.json"
        self.work = evidence / "consumer"
        self.project = self.work / f"{self.app}.csproj"
        self.assets = self.work / "obj/project.assets.json"
        self.output = self.work / "bin/Release" / self.target_framework
        self.env = {**environment(self.work, dotnet), "MSBUILDDISABLENODEREUSE": "1",
                    "NUGET_SCRATCH": str(self.work / "nuget-scratch")}
        self.report = {
            "profile": self.profile, "status": "running", "exitCode": None, "command": [sys.executable, *sys.argv],
            "cwd": str(Path.cwd()), "startedAt": datetime.now(timezone.utc).isoformat(),
            "environment": {"os": platform.system(), "macOS": platform.mac_ver()[0],
                            "architecture": platform.machine(), "dotnet": str(dotnet)},
            "stages": {name: {"status": "not_run", "exitCode": None, "commands": [], "evidence": []} for name in STAGES},
        }
        self.save()

    def run_dotnet(self, command, log):
        return self.command([self.dotnet, *command], self.work, log, extra_env=self.env)

    def inputs(self):
        require((platform.system(), platform.machine()) == ("Darwin", "arm64"), "映射消费验收需要 macOS ARM64")
        self.report["inputs"] = self.prepare_project()
        self.run_dotnet(["--info"], "dotnet-info.log")
        self.run_dotnet(["--version"], "sdk.log")
        sdk = (self.evidence / "sdk.log").read_text().strip()
        require(sdk == SDK, f"映射消费验收要求 SDK {SDK}，实际 {sdk}")
        self.report["environment"]["sdk"] = sdk
        self.write_nuget_config()

    def prepare_project(self):
        return prepare_business_project(self, self.work)

    def write_nuget_config(self):
        config = self.evidence_file("consumer/NuGet.Config")
        config.write_text(f'''<configuration>
  <packageSources><clear /><add key="nuget.org" value="{NUGET_SOURCE}" /></packageSources>
  <fallbackPackageFolders><clear /></fallbackPackageFolders>
</configuration>
''', encoding="utf-8")

    def restore(self):
        caches = {name: self.env[name] for name in ("NUGET_PACKAGES", "NUGET_HTTP_CACHE_PATH", "NUGET_PLUGINS_CACHE_PATH")}
        require(all(not Path(path).exists() or not any(Path(path).iterdir()) for path in caches.values()),
                "还原前需要独立空缓存")
        self.report["emptyCachesBeforeRestore"] = caches
        self.run_dotnet(["restore", self.project, "--configfile", self.work / "NuGet.Config", "--no-http-cache",
                         "--force", "-p:Configuration=Release", "-p:RestoreFallbackFolders=", "--verbosity", "normal",
                         *self.properties],
                        "restore.log")
        self.assets_sha = sha256(self.evidence_file("consumer/obj/project.assets.json"))

    def packages(self):
        self.graph = original_graph(read_json(self.assets), Path(self.env["NUGET_PACKAGES"]))
        write_json(self.evidence_file("package-graph.json"), self.graph)

    def build(self):
        self.run_dotnet(["build", self.project, "-c", "Release", "--no-restore", "--disable-build-servers",
                         "-p:UseSharedCompilation=false", f"-bl:{self.evidence_file('build.binlog')}",
                         *self.properties], "build.log")
        require(sha256(self.assets) == self.assets_sha, "Release 构建改写了原始还原图")
        self.evidence_file(f"consumer/bin/Release/{self.target_framework}/{self.app}.deps.json")

    def run_probe(self, folder="process", arguments=(), reporter=None):
        reporter = reporter or self
        directory = reporter.evidence / folder
        directory.mkdir()
        result = reporter.evidence_file(f"{folder}/probe.json")
        log = reporter.evidence_file(f"{folder}/process.log")
        argv = [str(arg) for arg in (self.dotnet, self.output / f"{self.app}.dll", result, *arguments)]
        record = {"argv": argv, "cwd": str(directory), "log": str(log), "timeoutSeconds": 60,
                  "exitCode": None, "timedOut": False, "environmentOverrides": self.env}
        reporter.stage["commands"].append(record)
        reporter.save()
        with log.open("wb") as stream:
            try:
                completed = subprocess.run(argv, cwd=directory, env=os.environ | self.env, stdout=stream,
                                           stderr=subprocess.STDOUT, timeout=record["timeoutSeconds"])
                record["exitCode"] = completed.returncode
            except subprocess.TimeoutExpired as error:
                record["timedOut"] = True
                raise VerificationError(f"消费者进程超时，详见 {log}") from error
        return completed.returncode, result, log

    def process(self):
        status, result, log = self.run_probe()
        require(status == 0 and result.is_file(),
                f"消费者进程退出 {status} 或缺少业务报告，详见 {log}")
        self.probe = read_json(result)

    def acceptance(self):
        runtime = self.probe["environment"]
        require(runtime["RuntimeIdentifier"] == "osx-arm64", f"实际运行环境不符：{runtime}")
        self.report["environment"]["process"] = runtime
        write_json(self.evidence_file("assemblies-verified.json"),
                   verify_loaded_assemblies(self.probe, self.graph["packages"], self.output))
        report = {key: self.probe[key] for key in ("configuration", "user", "collection", "projection")}
        require(all(report.values()), "缺少业务断言结果")
        write_json(self.evidence_file("business-result.json"), report)

    def execute(self):
        try:
            for name in STAGES:
                self.step(name, getattr(self, name))
        except VerificationError as error:
            print(error, file=sys.stderr)
            self.report.update(status="failed", exitCode=1, reason=str(error))
        else:
            self.report.update(status="passed", exitCode=0)
        self.report["finishedAt"] = datetime.now(timezone.utc).isoformat()
        self.save()
        print(self.report_path)
        return self.report["exitCode"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dotnet", default=shutil.which("dotnet"), type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    args = parser.parse_args()
    sys.exit(OriginalBusinessRun(make_run_directory(args.evidence_root, "original-"), args.dotnet.resolve()).execute())
