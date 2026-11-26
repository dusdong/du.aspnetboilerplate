#!/usr/bin/env python3
"""用独立清单副本复验 R4 内部依赖差异的诊断。"""

import argparse
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r2_packages import write_json
from r4_release_candidate import MANIFEST
from verify import ROOT, read_json, require


CASES = {
    "old-exact-range": ("Du.Abp.AutoMapper", "Du.AutoMapper", "[14.0.0-r3.4]", "[14.0.0]"),
    "missing-internal-edge": ("Du.Abp.ZeroCore.EntityFrameworkCore", "Du.Abp.ZeroCore", None, "[10.5.1]"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-root", type=Path, required=True)
    args = parser.parse_args()
    frozen = args.frozen_root.resolve()
    with TemporaryDirectory(prefix="r4-manifest-tests-") as temp:
        for case, (name, dependency, mutation, expected) in CASES.items():
            manifest = read_json(MANIFEST)
            internal = manifest["packages"][name]["targets"]["net9.0"]["internalDependencies"]
            if mutation is None:
                del internal[dependency]
            else:
                internal[dependency] = mutation
            fixture = Path(temp) / f"{case}.json"
            write_json(fixture, manifest)
            command = [sys.executable, "-B", "eng/r4_release_candidate.py", "--frozen-root", str(frozen),
                       "--manifest", str(fixture)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            actual = mutation if mutation is not None else "缺失"
            diagnostic = (f"packages/{name}/targets/net9.0/internalDependencies/{dependency}"
                          f"：预期 {expected}，实际 {actual}")
            print(f"{case}：cwd={ROOT} argv={command}，退出 {result.returncode}", flush=True)
            print(result.stderr, end="", flush=True)
            require(result.returncode == 1 and diagnostic in result.stderr,
                    f"{case} 未给出预期诊断：{diagnostic}，实际 {result.stdout}{result.stderr}")
    print(f"{len(CASES)} 项定向负例通过。")


if __name__ == "__main__":
    main()
