#!/usr/bin/env python3
"""从 MSBuild 求值后的资产中提取 R1 依赖清单。"""

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "docs/maintenance/baseline-tools"))
sys.dont_write_bytecode = True
from inventory import PACKAGE_NAMES, TEST_NAMES, json_text, read_json


NUGET_SOURCE = "https://api.nuget.org/v3/index.json"
CORE_PACKAGES = {f"src/{name}/{name}.csproj" for name in PACKAGE_NAMES}
CORE_TESTS = {f"test/{name}/{name}.csproj" for name in TEST_NAMES}
SUPPORT_PROJECTS = {
    f"src/{name}/{name}.csproj"
    for name in ("Abp.AspNetCore.TestBase", "Abp.FluentValidation", "Abp.TestBase")
}
CORE_PROJECTS = CORE_PACKAGES | CORE_TESTS | SUPPORT_PROJECTS
NET10_ONLY = {
    "test/Abp.AspNetCore.Tests/Abp.AspNetCore.Tests.csproj",
    "test/Abp.EntityFrameworkCore.Tests/Abp.EntityFrameworkCore.Tests.csproj",
}
COMPAT_CALLERS = {
    "src/Abp.EntityFramework/Abp.EntityFramework.csproj",
    "src/Abp.ZeroCore.EntityFrameworkCore/Abp.ZeroCore.EntityFrameworkCore.csproj",
    "test/Abp.EntityFrameworkCore.Dapper.Tests/Abp.EntityFrameworkCore.Dapper.Tests.csproj",
    "test/Abp.Web.Common.Tests/Abp.Web.Common.Tests.csproj",
    "test/Abp.ZeroCore.Tests/Abp.ZeroCore.Tests.csproj",
    "test/aspnet-core-demo/AbpAspNetCoreDemo/AbpAspNetCoreDemo.csproj",
}


def read_project_assets(root, artifacts, packages_root, relative):
    project_path = root / relative
    command = [
        "dotnet", "msbuild", str(project_path), "-nologo",
        "-p:Configuration=Release", f"-p:ArtifactsPath={artifacts}",
        "-p:GeneratePackageOnBuild=false", "-getProperty:MSBuildProjectFullPath,ProjectAssetsFile",
    ]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    if result.returncode:
        raise ValueError(
            f"MSBuild 求值失败（exitCode={result.returncode}）："
            f"{result.stdout}{result.stderr}"
        )
    properties = json.loads(result.stdout)["Properties"]
    if Path(properties["MSBuildProjectFullPath"]).resolve() != project_path:
        raise ValueError("MSBuild 求值的项目路径不一致")
    if not properties["ProjectAssetsFile"]:
        raise ValueError("MSBuild 未返回 ProjectAssetsFile")
    path = Path(properties["ProjectAssetsFile"]).resolve()
    if not path.is_relative_to(artifacts):
        raise ValueError(f"资产文件不在当前工件目录下：{path}")
    data = read_json(path)
    restore = data["project"]["restore"]
    if Path(restore["projectPath"]).resolve() != project_path:
        raise ValueError(f"资产文件的项目路径不一致：{path}")
    if Path(restore["packagesPath"]).resolve() != packages_root or {
        Path(folder).resolve() for folder in data["packageFolders"]
    } != {packages_root}:
        raise ValueError(f"资产文件的包目录与指定缓存不一致：{path}")
    if set(restore["sources"]) != {NUGET_SOURCE}:
        raise ValueError(f"资产文件的还原源与 nuget.org 不一致：{path}")
    return data


def read_target(root, packages_root, relative, data, framework):
    project = data["project"]
    refs = project["restore"]["frameworks"][framework]["projectReferences"]
    project_paths = sorted(
        Path(ref["projectPath"]).resolve().relative_to(root).as_posix()
        for ref in refs.values()
    )
    direct_ids = {
        name.casefold()
        for name, info in project["frameworks"][framework].get("dependencies", {}).items()
        if info.get("target") == "Package"
    }
    packages = []
    resolved_projects = set()
    resolved_ids = set()
    for key, library in sorted(data["targets"][framework].items(), key=lambda entry: entry[0].casefold()):
        resolved = data["libraries"][key]
        if library["type"] == "project":
            target_project = (root / relative).parent / resolved["msbuildProject"]
            resolved_projects.add(target_project.resolve().relative_to(root).as_posix())
            expected = f".NETCoreApp,Version=v{framework.removeprefix('net')}"
            if library["framework"] != expected:
                raise ValueError(f"项目 {target_project.name} 实际选用 {library['framework']}，预期为 {expected}")
        elif library["type"] == "package":
            name, version = key.split("/")
            resolved_ids.add(name.casefold())
            package_path = (packages_root / resolved["path"]).resolve()
            if not package_path.is_relative_to(packages_root):
                raise ValueError(f"包 {key} 不在指定缓存下")
            metadata = read_json(package_path / ".nupkg.metadata")
            if metadata["source"] != NUGET_SOURCE:
                raise ValueError(f"包 {key} 的缓存来源与 nuget.org 不一致")
            content_hash = metadata["contentHash"]
            if not content_hash or content_hash != resolved["sha512"]:
                raise ValueError(f"包 {key} 的缓存内容哈希与资产记录不一致")
            packages.append({
                "id": name,
                "version": version,
                "dependency": "direct" if name.casefold() in direct_ids else "transitive",
                "source": metadata["source"],
                "contentHash": content_hash,
            })
    if missing := direct_ids - resolved_ids:
        raise ValueError(f"缺失直接依赖：{sorted(missing)}")
    if missing := set(project_paths) - resolved_projects:
        raise ValueError(f"缺失直接项目引用：{sorted(missing)}")
    return {
        "targetFramework": framework, "runtimeIdentifier": None,
        "projectReferences": project_paths, "packages": packages,
    }


def restore_inventory(root, artifacts, packages_root, scope):
    entry_projects = sorted(CORE_PROJECTS if scope == "core" else CORE_PACKAGES | COMPAT_CALLERS)
    pending = entry_projects.copy()
    projects = {}
    while pending:
        relative = pending.pop()
        if relative in projects:
            continue
        try:
            data = read_project_assets(root, artifacts, packages_root, relative)
            frameworks = {"net9.0"} if scope == "compat" else {"net10.0"}
            if scope == "core" and relative not in NET10_ONLY:
                frameworks.add("net9.0")
            available = set(data["targets"])
            if not frameworks <= available or (scope == "core" and available != frameworks):
                raise ValueError(f"实际目标为 {sorted(available)}，预期包含 {sorted(frameworks)}")
            declared = data["project"]["restore"]["originalTargetFrameworks"]
            if relative in COMPAT_CALLERS and declared != ["net9.0"]:
                raise ValueError(f"兼容调用方的默认项目目标为 {declared}，预期为 net9.0")
            targets = []
            for framework in sorted(frameworks):
                try:
                    target = read_target(root, packages_root, relative, data, framework)
                except (KeyError, OSError, TypeError, ValueError) as error:
                    raise ValueError(f"{framework}：{error}") from error
                targets.append(target)
                pending.extend(target["projectReferences"])
            projects[relative] = {"effectiveSources": [NUGET_SOURCE], "targets": targets}
        except (KeyError, OSError, TypeError, ValueError) as error:
            raise ValueError(f"{relative}：{error}") from error
    if scope == "core" and set(projects) != CORE_PROJECTS:
        raise ValueError(f"核心闭包包含计划外的项目：{sorted(projects.keys() - CORE_PROJECTS)}")
    return {
        "inventoryVersion": 1,
        "entryProjects": entry_projects,
        "projects": dict(sorted(projects.items())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework-root", type=Path, required=True)
    parser.add_argument("--artifacts-path", type=Path, required=True)
    parser.add_argument("--packages-root", type=Path, required=True)
    parser.add_argument("--scope", choices=("core", "compat"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = restore_inventory(
            args.framework_root.resolve(), args.artifacts_path.resolve(),
            args.packages_root.resolve(), args.scope,
        )
        args.output.write_text(json_text(result), encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"R1 依赖清单生成失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
