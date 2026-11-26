"""对照公开与本地引擎实包的普通运行时集合映射。"""

from r3_web_host import artifact, write_json
from r5_invoice_consumer import PACKAGE, compare_packages, main, read_observations
from verify import ROOT, require


SOURCES = ROOT / "eng/r5-runtime-collection-probe"
PROJECT = "RuntimeCollectionProbe"
SHIPMENT_FIRST = ["shipment", "return"]
RETURN_FIRST = ["return", "shipment"]
CASES = {
    "cold-shipment-first": (SHIPMENT_FIRST, []),
    "cold-return-first": (RETURN_FIRST, []),
    "warm-shipment-first": (SHIPMENT_FIRST, SHIPMENT_FIRST),
    "warm-return-first": (SHIPMENT_FIRST, RETURN_FIRST),
}
SOURCE_TYPES = {"shipment": "ShipmentDraft", "return": "ReturnDraft"}
COLLECTION = "System.Collections.Generic.List`1[ItemDraft] -> System.Collections.Generic.List`1[ItemView]"


def summarize_plans(plan, row):
    calls = [("initial", None)]
    calls.extend(("warmup", key) for key in row["WarmupOrder"])
    calls.extend(("measurement", key) for key in SHIPMENT_FIRST)
    cache = plan["Cache"]
    require([(snapshot["Stage"], snapshot["Parent"]) for snapshot in cache] == calls,
            "缓存采样和实际调用顺序不符")
    require(not cache[0]["Entries"], "新配置的缓存应为空")
    require(all("MapInternal" in plan[key] for key in ("ShipmentExpression", "ReturnExpression")),
            "两处父类型映射均应通过 MapInternal 进入集合计划")
    entries = [[entry for entry in snapshot["Entries"] if entry["RequestedTypes"] == COLLECTION]
               for snapshot in cache[1:]]
    if any(len(match) != 1 for match in entries):
        return False
    collection_entries = [match[0] for match in entries]
    first = collection_entries[0]
    return (first["Delegate"] is not None and bool(first["Method"])
            and first["RuntimeTypes"] == COLLECTION and first["MatchesShipmentRequest"]
            and first["MatchesReturnRequest"] and first["PopulatedByMember"] == "Lines"
            and first["PopulatedBySourceType"] == SOURCE_TYPES[calls[1][1]]
            and all(entry == first for entry in collection_entries[1:]))


def observe(work, command, dotnet, program, identity, _checks):
    measured, audited = read_observations(work, command, dotnet, program, identity)
    require(measured["measurementOrder"] == SHIPMENT_FIRST, "正式调用顺序不符")
    results = {}
    plan_coverage = {}
    warmup_deviations = []
    for row, plan in zip(measured["observations"], audited["plans"], strict=True):
        case, repeat = row["Case"], row["Repeat"]
        require((case, repeat) not in results and (case, repeat) == (plan["Case"], plan["Repeat"]),
                "独立观测缺项或重复")
        require((row["Registration"], row["WarmupOrder"]) == CASES[case], "注册或预热顺序不符")
        for label, order, expected in (
            ("Warmups", row["WarmupOrder"], measured["warmupExpected"]),
            ("Measurements", SHIPMENT_FIRST, measured["expected"]),
        ):
            for key, outcome in zip(order, row[label], strict=True):
                matches = outcome["Actual"] == expected[key] and not outcome["Exceptions"]
                require(outcome["MatchesExpected"] == matches, "业务断言与逐次实际结果不符")
                if label == "Warmups" and not matches:
                    warmup_deviations.append({"case": case, "repeat": repeat, "parent": key})
        plan_coverage.setdefault(case, []).append(summarize_plans(plan, row))
        results[case, repeat] = row
    require(set(results) == {(case, repeat) for case in CASES for repeat in range(1, 4)},
            "每种顺序应有三份独立配置")

    cases = {}
    for case in CASES:
        runs = [results[case, index] for index in range(1, 4)]
        cases[case] = {
            "stable": all(run["Warmups"] == runs[0]["Warmups"]
                          and run["Measurements"] == runs[0]["Measurements"] for run in runs[1:]),
            "matched": sum(outcome["MatchesExpected"] for run in runs for outcome in run["Measurements"]),
            "sharedPlans": sum(plan_coverage[case]),
        }

    pairs = {}
    for stage in ("cold", "warm"):
        left, right = f"{stage}-shipment-first", f"{stage}-return-first"
        if not all(cases[case]["stable"] for case in (left, right)):
            pairs[stage] = "unstable"
        elif all(cases[case]["matched"] == 6 for case in (left, right)):
            pairs[stage] = "as-expected"
        elif results[left, 1]["Measurements"] == results[right, 1]["Measurements"]:
            pairs[stage] = "same-deviation"
        else:
            pairs[stage] = "order-difference"
    return measured, {
        "cases": cases,
        "pairs": pairs,
        "warmupDeviations": warmup_deviations,
        "loaded": measured["assemblies"][0],
        "archiveSha256": identity["archive"]["sha256"],
        "dependencyArchives": {key: value["archive"]["sha256"] for key, value in identity["packages"].items()
                                if not key.startswith(f"{PACKAGE}/")},
        "raw": artifact(work / "measurements.json", work.parent),
        "plans": artifact(work / "plan-observations.json", work.parent),
        "identity": artifact(work / "identity.json", work.parent),
    }


def evaluate_results(public, candidate):
    reports = (public, candidate)
    complete = all(set(report["cases"]) == set(CASES)
                   and set(report["pairs"]) == {"cold", "warm"}
                   and all(case["sharedPlans"] == 3 for case in report["cases"].values())
                   for report in reports)
    stable_modes = {"as-expected", "same-deviation", "order-difference"}
    stable = all(set(report["pairs"].values()) <= stable_modes
                 and all(case["stable"] for case in report["cases"].values()) for report in reports)
    old_modes = set(public["pairs"].values())
    candidate_expected = (candidate["pairs"] == {"cold": "as-expected", "warm": "as-expected"}
                          and not candidate["warmupDeviations"])
    # 旧包的预热偏差属于可观察结果。比较仍要求调用完整且结果可稳定重复。
    if not complete or not stable or not candidate_expected:
        decision, exit_code = "hold", 2
    elif "order-difference" in old_modes:
        decision, exit_code = "freeze-condition-met", 0
    elif "same-deviation" in old_modes:
        decision, exit_code = "review-scope", 0
    else:
        decision, exit_code = "wait-for-new-evidence", 0
    return {
        "exitCode": exit_code,
        "decision": decision,
        "planCoverageComplete": complete,
        "candidateMatchesExpected": candidate_expected,
    }


def execute(args):
    record, old, public, new, candidate = compare_packages(args, PROJECT, SOURCES, observe)
    output = args.output
    fields = ("runtime", "architecture", "runtimePath", "inputs", "initial", "warmup",
              "warmupExpected", "expected", "measurementOrder")
    require(all(old[key] == new[key] for key in fields), "运行环境或业务输入不同")
    require(public["dependencyArchives"] == candidate["dependencyArchives"], "传递依赖归档不同")
    assessment = evaluate_results(public, candidate)
    differences = []
    for before, after in zip(old["observations"], new["observations"], strict=True):
        require(all(before[key] == after[key] for key in ("Case", "Repeat", "Registration", "WarmupOrder")),
                "两包的注册或调用顺序不同")
        for label in ("Warmups", "Measurements"):
            for call, (left, right) in enumerate(zip(before[label], after[label], strict=True), 1):
                if left != right:
                    differences.append({"case": before["Case"], "repeat": before["Repeat"], "phase": label,
                                        "call": call, "public": left, "candidate": right})
    write_json(output / "report.json", {
        **assessment,
        "environmentAndInput": {key: old[key] for key in fields},
        "publicManifest": artifact(output / "R4-PACKAGE-CHECKSUMS.json", output),
        "verifiedPublicDownloads": artifact(output / "verified-downloads.json", output),
        "candidateInput": artifact(output / "acceptance-input.json", output),
        "candidateProducerCommit": record["producerCommit"],
        "public": public,
        "candidate": candidate,
        "differences": differences,
    })
    print(f"运行时集合实包观测见 {output / 'report.json'}")
    return assessment["exitCode"]


if __name__ == "__main__":
    raise SystemExit(main(execute, __doc__, "运行时集合对照"))
