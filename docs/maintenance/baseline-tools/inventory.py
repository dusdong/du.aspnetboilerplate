#!/usr/bin/env python3
import argparse
import difflib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

PACKAGE_NAMES = (
    "Abp", "Abp.AspNetCore", "Abp.EntityFrameworkCore",
    "Abp.Web.Common", "Abp.EntityFramework.Common",
)
TEST_NAMES = ("Abp.Tests", "Abp.AspNetCore.Tests", "Abp.EntityFrameworkCore.Tests")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def source_label(value):
    if value == "https://api.nuget.org/v3/index.json":
        return value
    url = urlsplit(value)
    if url.scheme not in {"https", "http"} or not url.hostname:
        return "<本地或自定义包源>"
    return urlunsplit((url.scheme, url.hostname, "/[已脱敏]", "", ""))


def restore_inventory(root):
    root = root.resolve()
    starting_paths = [f"src/{name}/{name}.csproj" for name in PACKAGE_NAMES]
    starting_paths += [f"test/{name}/{name}.csproj" for name in TEST_NAMES]
    pending = starting_paths.copy()
    projects = {}
    while pending:
        relative = pending.pop()
        if relative in projects:
            continue
        data = read_json((root / relative).parent / "obj/project.assets.json")
        project = data["project"]
        restore = project["restore"]
        if Path(restore["projectPath"]).resolve() != root / relative:
            raise ValueError(f"资产文件的项目路径不一致：{relative}")
        package_root = Path(restore["packagesPath"])
        sources = sorted(source_label(source) for source in restore["sources"])
        targets = []
        for target, libraries in sorted(data["targets"].items()):
            framework, _, rid = target.partition("/")
            refs = restore["frameworks"][framework]["projectReferences"]
            project_paths = sorted(
                Path(ref["projectPath"]).resolve().relative_to(root).as_posix()
                for ref in refs.values()
            )
            pending.extend(project_paths)
            direct_ids = {
                name.casefold()
                for name, info in project["frameworks"][framework].get("dependencies", {}).items()
                if info.get("target") == "Package"
            }
            resolved_ids = set()
            packages = []
            for key, library in sorted(libraries.items(), key=lambda entry: entry[0].casefold()):
                if library["type"] != "package":
                    continue
                name, version = key.split("/")
                resolved_ids.add(name.casefold())
                path = data["libraries"][key]["path"]
                metadata = read_json(package_root / path / ".nupkg.metadata")
                packages.append({
                    "id": name,
                    "version": version,
                    "dependency": "direct" if name.casefold() in direct_ids else "transitive",
                    "source": source_label(metadata["source"]),
                    "contentHash": metadata["contentHash"],
                })
            if missing := direct_ids - resolved_ids:
                raise ValueError(f"{relative}/{target} 缺失直接依赖：{sorted(missing)}")
            targets.append({
                "targetFramework": framework, "runtimeIdentifier": rid or None,
                "projectReferences": project_paths, "packages": packages,
            })
        if not targets:
            raise ValueError(f"缺少还原目标：{relative}")
        projects[relative] = {"effectiveSources": sources, "targets": targets}

    return {
        "inventoryVersion": 1,
        "entryProjects": sorted(starting_paths),
        "projects": dict(sorted(projects.items())),
    }


def compare_api(before, after):
    changes = {}
    for key in ("assembly", "resources"):
        if before[key] != after[key]:
            changes[key] = {"before": before[key], "after": after[key]}
    type_changes = {}
    for name in sorted(before["types"].keys() | after["types"].keys()):
        earlier = before["types"].get(name, [])
        later = after["types"].get(name, [])
        if earlier != later:
            type_changes[name] = {
                "removed": sorted(set(earlier) - set(later)),
                "added": sorted(set(later) - set(earlier)),
            }
    if type_changes:
        changes["types"] = type_changes
    return changes


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("root", type=Path)
    for command in ("compare-restore", "compare-api"):
        diff = commands.add_parser(command)
        diff.add_argument("before", type=Path)
        diff.add_argument("after", type=Path)
    args = parser.parse_args()

    if args.command == "restore":
        print(json_text(restore_inventory(args.root)), end="")
        return 0

    before, after = read_json(args.before), read_json(args.after)
    if args.command == "compare-api":
        changes = compare_api(before, after)
        print(json_text({"assembly": before["assembly"]["name"], "changes": changes}), end="")
        return int(bool(changes))
    if before != after:
        print("".join(difflib.unified_diff(
            json_text(before).splitlines(keepends=True),
            json_text(after).splitlines(keepends=True),
            fromfile=str(args.before), tofile=str(args.after),
        )), end="")
        return 1

    print(json_text({
        "identical": True,
        "projects": len(before["projects"]),
        "projectTargets": sum(len(project["targets"]) for project in before["projects"].values()),
    }), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
