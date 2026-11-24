#!/usr/bin/env python3
from pathlib import Path
import sys
import unittest


def result_exit_code(result):
    effective = result.testsRun - len(result.skipped)
    print(f"R0 Python self-check: ran={result.testsRun} skipped={len(result.skipped)} effective={effective}")
    return 0 if result.wasSuccessful() and effective > 0 else 1


def main():
    sys.dont_write_bytecode = True
    tests = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(tests), pattern="test_verify_r0.py")
    return result_exit_code(unittest.TextTestRunner(verbosity=2).run(suite))


if __name__ == "__main__":
    raise SystemExit(main())
