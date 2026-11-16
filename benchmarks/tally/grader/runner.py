"""Run unittest test files against one project tree and record each test's outcome.

Usage (run with the project directory as the working directory):
    python runner.py --project DIR --out RESULTS.json [--only IDS.json] TEST_FILE...

RESULTS.json maps each test id (module.Class.method) to "pass", "fail", "error"
or "skip". A test file that cannot be imported is recorded as
"<module>.__import__": "error".
"""

import argparse
import importlib.util
import json
import sys
import unittest
from pathlib import Path


class Recorder(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.outcomes: dict[str, str] = {}

    def addSuccess(self, test):
        self.outcomes.setdefault(test.id(), "pass")

    def addFailure(self, test, err):
        self.outcomes[test.id()] = "fail"

    def addError(self, test, err):
        self.outcomes[test.id()] = "error"

    def addSkip(self, test, reason):
        self.outcomes[test.id()] = "skip"

    def addExpectedFailure(self, test, err):
        self.outcomes[test.id()] = "pass"

    def addUnexpectedSuccess(self, test):
        self.outcomes[test.id()] = "fail"

    def addSubTest(self, test, subtest, err):
        if err is not None:
            failed = issubclass(err[0], test.failureException)
            self.outcomes[test.id()] = "fail" if failed else "error"


def load(path: Path) -> unittest.TestSuite:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return unittest.defaultTestLoader.loadTestsFromModule(module)


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--only")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(args.project).resolve()))
    only = set(json.loads(Path(args.only).read_text())) if args.only else None
    result = Recorder()
    for name in args.files:
        path = Path(name).resolve()
        try:
            tests = list(flatten(load(path)))
        except BaseException:  # noqa: BLE001 - any import failure counts as an error
            result.outcomes[f"{path.stem}.__import__"] = "error"
            continue
        for test in tests:
            if only is None or test.id() in only:
                test(result)
        Path(args.out).write_text(json.dumps(result.outcomes))
    Path(args.out).write_text(json.dumps(result.outcomes))


if __name__ == "__main__":
    main()
