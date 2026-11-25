#!/usr/bin/env python3
"""从已验运行和生产实物构造独立的诊断证据。"""

import argparse
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import r3_web_host
import verify
from r2_diagnostics import edited_zip
from r2_packages import verify_source, write_json
from r3_leaf_assets import APP, check_assets, check_log4net_assets, check_log4net_compile
from r3_leaf_packages import CASTLE, CORE, LOG4NET, R2_VERSION, SIGNALR, SOURCE_PROOF, TFM, read_leaf
from r3_leaf_verify import IntegrationRun, compare_log4net
from verify import read_json, require, sha256


def diagnose(root, dotnet, stage, action, expected, *, kind="证据夹具", prepare=None):
    root.mkdir()
    run = IntegrationRun(root, dotnet)
    stages = prepare(run) if prepare else []
    exit_code = run.run_stages([*stages, (stage, action, (run,))])
    report = read_json(run.report_path)
    reason = report["reason"]
    require(exit_code == report["exitCode"] == 1 and report["stages"][stage]["status"] == "failed" and
            all(text in reason for text in expected), f"{root.name} 未触发预期的 {stage} 诊断：{reason}")
    names = list(report["stages"])
    require(all(report["stages"][name]["status"] == "not_run" and report["stages"][name].get("reason")
                and not report["stages"][name]["commands"] for name in names[names.index(stage) + 1:]),
            f"{root.name} 未执行阶段证据不符")
    print(f"{kind} {root.name}：exit=1，{reason}")
    return report


def edit_nuspec(package, before, after):
    def replace(archive):
        name, = (file for file in archive.namelist() if file.endswith(".nuspec"))
        original = archive.read(name)
        require(before in original, f"诊断未找到预期原始值 {package} {before}")
        return {name: original.replace(before, after, 1)}

    edited_zip(package, replace)


def bad_packages(evidence, dotnet, same_batch, r2_feed, inputs):
    feed = evidence / "r2-replaced"
    shutil.copytree(r2_feed, feed)
    core = feed / Path(inputs["packages"][CORE]["archive"]).name
    edited_zip(core, lambda _: {"r3-diagnostic-marker.txt": b"distinct archive bytes"})

    args = (*same_batch, feed)
    diagnose(evidence / "same-version-r2-replaced", dotnet, "packages", lambda run: run.verify_packages(*args),
             (core.name, "SHA-256 不符"), prepare=lambda run: [("preflight", run.preflight, args)])

    manifest_path = same_batch[1]
    manifest = read_json(manifest_path)
    version = manifest["version"]
    original = inputs["packages"][SIGNALR]
    cases = {
        "wrong-exact-core-range": (b'version="[10.5.1-r2.1]"', b'version="10.5.1-r2.1"', "范围"),
        "original-id-in-nuspec": (b'id="Du.Abp"', b'id="Abp"', "Abp"),
        "missing-net9-group": (b'targetFramework="net9.0"', b'targetFramework="net10.0"', "缺少 net9.0"),
    }
    for name, (before, after, reason) in cases.items():
        def mutated_leaf(run):
            package = Path(shutil.copy2(original["archive"], run.evidence))
            symbol = Path(shutil.copy2(original["symbol"], run.evidence))
            edit_nuspec(package, before, after)
            entry = deepcopy(manifest["packages"][SIGNALR])
            entry["package"]["sha256"] = sha256(package)
            write_json(run.evidence / "mutated-input.json", entry)
            read_leaf(package, symbol, SIGNALR, version, entry, inputs["source"], manifest["sourceProof"])

        diagnose(evidence / name, dotnet, "packages", mutated_leaf, (SIGNALR, reason))


def source_proof_cases(evidence, dotnet, manifest_path, inputs):
    manifest = read_json(manifest_path)
    entry = manifest["packages"][SIGNALR]
    original = inputs["packages"][SIGNALR]
    base_commit = manifest["sourceProof"]["baseCommit"]
    committed = deepcopy(manifest)
    folder = evidence / "committed-source-proof"
    folder.mkdir()
    manifest_copy = folder / "manifest.json"
    source_patch = folder / "source.patch"
    source_patch.write_bytes(b"")
    committed["sourceProof"] = {"baseCommit": base_commit, "commit": base_commit, "tree": inputs["source"]["baseTree"],
                                "patchSha256": sha256(source_patch)}
    write_json(manifest_copy, committed)
    commitment = f'<repository commit="{base_commit}"'.encode()
    committed_source = {}
    committed_files = {}

    def verify_committed(run):
        committed_source.update(verify_source(run, manifest_copy, committed))
        for item in ("archive", "symbol"):
            target = Path(shutil.copy2(original[item], folder))
            edit_nuspec(target, b"<repository ", commitment + b" ")
            committed_files[item] = target
        proof = committed["sourceProof"]
        edited_zip(committed_files["archive"], lambda _: {SOURCE_PROOF: json.dumps(proof).encode()})
        fixture_entry = deepcopy(entry)
        fixture_entry["package"]["sha256"] = sha256(committed_files["archive"])
        fixture_entry["symbols"]["sha256"] = sha256(committed_files["symbol"])
        attestations = read_leaf(committed_files["archive"], committed_files["symbol"], SIGNALR, manifest["version"],
                                 fixture_entry, committed_source, proof)
        write_json(folder / "verified.json", {"source": committed_source, "checkedPackage": attestations,
                                               "kind": "仅来源元数据夹具"})

    run = IntegrationRun(folder, dotnet)
    require(run.run_stages([("packages", verify_committed, (run,))]) == 0, f"已提交来源夹具未通过：{run.report_path}")
    uncommitted = read_leaf(Path(original["archive"]), Path(original["symbol"]), SIGNALR, manifest["version"],
                            entry, inputs["source"], manifest["sourceProof"])
    write_json(evidence / "uncommitted-source-proof.json", uncommitted)
    print("来源正例：未提交实际原件，以及使用实际 Git 对象核对的已提交元数据夹具")

    def committed_negative(run, mutate):
        archive = Path(shutil.copy2(committed_files["archive"], run.evidence))
        symbol = Path(shutil.copy2(committed_files["symbol"], run.evidence))
        proof = committed["sourceProof"]
        if mutate == "missing-proof-commit":
            edited_zip(archive, lambda _: {SOURCE_PROOF: json.dumps(
                {key: value for key, value in proof.items() if key != "commit"}).encode()})
        elif mutate == "missing-symbol-repository-commit":
            edit_nuspec(symbol, commitment, b"<repository")
        else:
            wrong = manifest["superproject"]["commit"]
            edit_nuspec(archive, commitment, f'<repository commit="{wrong}"'.encode())
        read_leaf(archive, symbol, SIGNALR, manifest["version"], entry, committed_source, proof)

    diagnose(evidence / "missing-proof-commit", dotnet, "packages",
             lambda run: committed_negative(run, "missing-proof-commit"), ("完整源码证明",))
    diagnose(evidence / "missing-symbol-repository-commit", dotnet, "packages",
             lambda run: committed_negative(run, "missing-symbol-repository-commit"), (".snupkg", "repository"))

    diagnose(evidence / "wrong-package-repository-commit", dotnet, "packages",
             lambda run: committed_negative(run, "wrong-package-repository-commit"), (".nupkg", "repository"))

    def unexpected_commit(run):
        archive = Path(shutil.copy2(original["archive"], run.evidence))
        edit_nuspec(archive, b"<repository ", commitment + b" ")
        read_leaf(archive, Path(original["symbol"]), SIGNALR, manifest["version"],
                  entry, inputs["source"], manifest["sourceProof"])

    diagnose(evidence / "unexpected-uncommitted-repository-commit", dotnet, "packages",
             unexpected_commit, (".nupkg", "repository"))


def dependency_drift_cases(evidence, run, dotnet, inputs):
    inventory = read_json(run / "assets-inventory.json")
    graph = read_json(run / "consumer/obj/project.assets.json")["targets"][TFM]
    actual = inventory["log4net"]
    actual_asset = actual["selectedAssets"]["runtime"]["asset"]
    actual_cache = run / "consumer/packages"
    actual_archive = actual_cache / inventory["packages"][actual["package"]]["archive"]["path"]
    with ZipFile(actual_archive) as archive:
        dll = archive.read(actual_asset)

    def fixture(test, version):
        test.metadata_tool = run / "tools/metadata/bin/Release/net10.0/R2Metadata.dll"
        test.work = test.evidence
        cache = test.evidence / "packages"
        relative = Path(LOG4NET) / version
        key = f"{LOG4NET}/{version}"
        archive = relative / f"{LOG4NET}.{version}.nupkg"
        assets = {"compile": "ref/net9.0/log4net.dll", "runtime": "lib/net9.0/log4net.dll"}
        (cache / relative).mkdir(parents=True)
        with ZipFile(cache / archive, "w") as package:
            package.writestr("log4net.nuspec", f"<package><metadata><id>log4net</id><version>{version}</version></metadata></package>")
            for asset in assets.values():
                package.writestr(asset, dll)
                target = cache / relative / asset
                target.parent.mkdir(parents=True)
                target.write_bytes(dll)
        castle_key = actual["from"]
        selected = {castle_key: graph[castle_key], key: {section: {path: {}} for section, path in assets.items()}}
        records = {key: {"id": LOG4NET, "version": version, "archive": {"path": archive.as_posix()},
                         "cachePath": relative.as_posix()}}
        write_json(test.evidence / "fixture.json", {"kind": "模拟资产与包元数据", "graph": selected, "packages": records})
        return selected, records, cache, castle_key

    def verify_later_version(test):
        selected, packages, cache, castle_key = fixture(test, "3.3.9")
        asset = check_log4net_assets(selected, packages, cache, castle_key, test.satisfies_range)
        comparison = compare_log4net(inputs["production"][CASTLE]["log4net"], {"log4net": asset, "packages": packages})
        require(asset["declaredRange"] == "[3.3.2,)" and asset["version"] == "3.3.9" and
                set(comparison["differences"]) == {"version", "compile", "runtime"} and comparison["impact"],
                f"消费差异未完整登记：{comparison}")
        compile_path = cache / "log4net/3.3.9/ref/net9.0/log4net.dll"
        check_log4net_compile({"ReferencePath": [{"FullPath": str(compile_path)}]},
                              {"log4net": asset, "packages": packages}, cache)
        write_json(test.evidence / "comparison.json", comparison)

    folder = evidence / "later-version-and-distinct-assets"
    folder.mkdir()
    fixture_run = IntegrationRun(folder, dotnet)
    require(fixture_run.run_stages([("assets", verify_later_version, (fixture_run,))]) == 0,
            f"范围内消费选择夹具未通过：{fixture_run.report_path}")
    print("模拟正例 later-version-and-distinct-assets：接受范围内版本和不同编译、运行资产，登记差异")

    def verify_below_range(test):
        selected, packages, cache, castle_key = fixture(test, "3.3.1")
        check_log4net_assets(selected, packages, cache, castle_key, test.satisfies_range)

    diagnose(evidence / "version-below-declared-range", dotnet, "assets", verify_below_range,
             ("[3.3.2,)", "不接受实选版本 3.3.1"))


def missing_package(evidence, dotnet, same_batch, r2_feed):
    def restore_without_required_package(run):
        source = run.feeds[R2_VERSION]
        original = source / f"Du.Abp.Web.Common.{R2_VERSION}.nupkg"
        removed = run.evidence / original.name
        original.rename(removed)
        run.report["removedArchive"] = {"path": str(original), "retainedCopy": str(removed), "sha256": sha256(removed)}
        run.restore()

    root = evidence / "missing-package-in-mapped-source"
    # 前置阶段仍使用原件，移走的仅是本例受控源副本。
    args = (*same_batch, r2_feed)
    report = diagnose(root, dotnet, "restore", restore_without_required_package, ("restore.log",), kind="真实还原",
                      prepare=lambda run: [("preflight", run.preflight, args), ("packages", run.verify_packages, args)])
    reason = (root / "restore.log").read_text()
    require("NU1101" in reason and "Du.Abp.Web.Common" in reason and
            report["stages"]["restore"]["commands"][-1]["exitCode"] == 1 and
            not list((root / "consumer/packages").glob("du.abp.web.common/*")),
            "缺包真实还原没有给出实际 NuGet 诊断或出现被移走的包")


def bad_assets(evidence, run, dotnet, inputs):
    consumer = run / "consumer"
    feeds = {R2_VERSION: consumer / "feed-r2", inputs["packages"][SIGNALR]["version"]: consumer / "feed-r3"}
    original = read_json(consumer / "obj/project.assets.json")
    cases = {"wrong-target-in-assets": "lib/net10.0/Abp.AspNetCore.SignalR.dll",
             "duplicate-framework-asset": "Microsoft.AspNetCore.SignalR.Client",
             "missing-framework-runtime-asset": "实际 []"}
    for name, reason in cases.items():
        def mutate_assets(diagnostic):
            data = deepcopy(original)
            graph = data["targets"][TFM]
            provider = next(key for key in graph if key.startswith(SIGNALR + "/"))
            asset = inputs["packages"][SIGNALR]["asset"]
            if name == "wrong-target-in-assets":
                graph[provider]["compile"] = {reason: {}}
            elif name == "duplicate-framework-asset":
                other = next(key for key in graph if key.startswith(reason + "/"))
                graph[other]["runtime"][asset] = {}
            else:
                graph[provider].pop("runtime")
            file = diagnostic.evidence / "project.assets.json"
            write_json(file, data)
            diagnostic.metadata_tool = run / "tools/metadata/bin/Release/net10.0/R2Metadata.dll"
            diagnostic.work = diagnostic.evidence
            check_assets(read_json(file), consumer / "SignalRLog4Net.csproj", consumer / "packages",
                         feeds, inputs["packages"], diagnostic.satisfies_range)

        diagnose(evidence / name, dotnet, "assets", mutate_assets, ("Abp.AspNetCore.SignalR.dll", reason))


def bad_behavior(evidence, run, dotnet):
    original = read_json(run / "host/host.json")
    for name, key, reason in (("missing-configured-notifier", "configuredNotifier", "通知配置缺少"),
                              ("missing-notification", "received", "缺少 getNotification"),
                              ("connection-not-removed", "removed", "OnDisconnectedAsync 未移除连接")):
        def mutate_signalr(diagnostic):
            diagnostic.host_evidence = deepcopy(original)
            diagnostic.host_evidence["signalr"].pop(key)
            write_json(diagnostic.evidence / "host.json", diagnostic.host_evidence)
            diagnostic.signalr()

        diagnose(evidence / name, dotnet, "signalr", mutate_signalr, (reason,))

    for name, reason in (("missing-log-file", "缺少 Castle 日志文件"), ("incorrect-log-line", "完整等级、类别或消息不符")):
        def mutate_log(diagnostic):
            diagnostic.host_evidence = deepcopy(original)
            host_dir = diagnostic.evidence / "host"
            host_dir.mkdir()
            log_file = host_dir / "castle.log"
            diagnostic.host_evidence["log4net"]["path"] = str(log_file)
            write_json(host_dir / "host.json", diagnostic.host_evidence)
            if name == "incorrect-log-line":
                source = (run / "host/castle.log").read_text()
                log_file.write_text(source.replace("INFO|Du.Abp.R3.Castle", "WARN|Du.Abp.R3.Castle"))
            diagnostic.log4net()

        diagnose(evidence / name, dotnet, "log4net", mutate_log, (reason,))

    def mutate_runtime(diagnostic):
        diagnostic.host_evidence = deepcopy(original)
        diagnostic.host_evidence["runtime"]["assemblies"]["log4net"]["sha256"] = "0" * 64
        write_json(diagnostic.evidence / "host.json", diagnostic.host_evidence)
        diagnostic.output = run / "consumer/bin/Release" / TFM
        diagnostic.output_dlls = read_json(run / "output.json")
        report = read_json(run / "report.json")
        diagnostic.report["hostProcess"] = report["hostProcess"]
        diagnostic.runtime()

    diagnose(evidence / "incorrect-loaded-log4net", dotnet, "runtime", mutate_runtime, ("实际加载 log4net.dll",))


def host_lifetime(evidence, dotnet, same_batch, r2_feed):
    folder = evidence / "lifecycles-build"
    folder.mkdir()
    build = IntegrationRun(folder, dotnet)
    original = None
    for kind, edit in (
        ("fail", "configuration.Object.Notifiers.Remove(typeof(SignalRRealTimeNotifier));"),
        ("timeout", "await Task.Delay(Timeout.InfiniteTimeSpan, token);"),
    ):
        output = folder / kind

        def build_variant():
            nonlocal original
            if original is None:
                original = (build.work / "Program.cs").read_text()
            anchor = ('var notifierType = configuration.Object.Notifiers.SingleOrDefault' if kind == "fail"
                      else 'using var configuration = ioc.ResolveAsDisposable<INotificationConfiguration>();')
            require(anchor in original, f"真实宿主夹具缺少注入点 {kind}")
            source = original.replace(anchor, edit + "\n            " + anchor, 1)
            (build.work / "Program.cs").write_text(source)
            (folder / f"{kind}.cs.fixture").write_text(source)
            build.run_dotnet(["build", build.project, "--no-restore", "--disable-build-servers", "-o", output,
                              *build.build_properties], f"{kind}-build.log")
            require((output / f"{APP}.dll").is_file(), f"{kind} 真实宿主夹具构建产物缺失")

        stages = []
        if original is None:
            args = (*same_batch, r2_feed)
            stages = [("preflight", build.preflight, args), ("packages", build.verify_packages, args),
                      ("restore", build.restore, ())]
        stages.append(("build", build_variant, ()))
        require(build.run_stages(stages) == 0, f"宿主夹具构建失败：{build.report_path}")
        seconds = 40 if kind == "fail" else 8
        expected = "通知配置缺少 SignalRRealTimeNotifier" if kind == "fail" else "Kestrel 宿主超时"
        root = evidence / f"real-host-{kind}"
        report = diagnose(root, dotnet, "host", lambda run: run.host(output, seconds), (expected,), kind="真实宿主")
        process = report["hostProcess"]
        observation = read_json(root / "host/host.json")
        require(process["exitCode"] == 1 and process["reaped"] is True and
                observation["signalr"]["register"] is True and
                process["shutdown"] == {"clientStopped": True, "hostStopped": True}, f"{kind} 实际停机证据不符")
        if kind == "timeout":
            require(process["timedOut"] and process["termination"] == "SIGTERM", "超时终止未生效")


def dispatch(evidence):
    from verify_r3_web_host import verify_dispatch

    evidence.mkdir()
    verify_dispatch(evidence)
    args = ["verify.py", "--profile", "r3-web-host", "--evidence-root", str(evidence / "r3-web-host")]
    with patch.object(sys, "argv", args), patch.object(r3_web_host, "execute", return_value=47) as execute:
        require(verify.main() == 47 and execute.call_args.args[0].evidence_root == evidence / "r3-web-host",
                "原版 Web.Host profile 参数分派失效")
    write_json(evidence / "r3-web-host.json", args)
    cases = {
        "r0": ["--dotnet", str(evidence)], "r2": ["--r2-feed", str(evidence)],
        "r3-web-host": ["--candidate-feed", str(evidence)],
        "r3-signalr-log4net": ["--evidence-root", str(evidence)],
    }
    for profile, options in cases.items():
        with patch.object(sys, "argv", ["verify.py", "--profile", profile, *options]), redirect_stderr(io.StringIO()) as log:
            try:
                verify.main()
            except SystemExit as error:
                require(error.code == 2, f"{profile} 参数拒绝退出码不是 2")
            else:
                raise verify.VerificationError(f"{profile} 错误接受参数 {options}")
        (evidence / f"{profile}-invalid-arguments.log").write_text(log.getvalue())
    print("参数分派夹具：R0、R2、原版 Web.Host 原有效分派保留，错误参数返回 2")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    run, evidence = args.run.resolve(), args.evidence.resolve()
    report = read_json(run / "report.json")
    require(report["exitCode"] == 0, f"诊断输入须为成功报告 {run}")
    evidence.mkdir(parents=True)
    candidate = read_json(run / "candidate.json")
    inputs = report["inputs"]
    dotnet = Path(report["environment"]["dotnet"])
    same_batch = tuple(Path(inputs[key]) for key in ("candidateFeed", "candidateManifest", "candidateSymbols"))
    r2_feed = Path(inputs["r2Feed"])
    dispatch(evidence / "dispatch")
    bad_packages(evidence, dotnet, same_batch, r2_feed, candidate)
    source_proof_cases(evidence, dotnet, same_batch[1], candidate)
    dependency_drift_cases(evidence, run, dotnet, candidate)
    bad_assets(evidence, run, dotnet, candidate)
    bad_behavior(evidence, run, dotnet)
    missing_package(evidence, dotnet, same_batch, r2_feed)
    host_lifetime(evidence, dotnet, same_batch, r2_feed)
    print("R3 SignalR 与 Log4Net 定向诊断全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
