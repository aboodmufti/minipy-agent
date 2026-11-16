"""Assemble the Harbor task for the tally benchmark into ./task.

    python build.py           # build ./task
    python build.py --check   # build, then grade the reference and the starting code locally

Sources:
    template/        task.toml, instruction.md, Dockerfile, verifier and oracle entry points
    src/original/    the repository the agent starts from (/app)
    src/reference/   files the reference solution changes or adds
    grader/          grade.py, runner.py, mutants.py and the hidden tests
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASK = ROOT / "task"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def copy(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, ignore=IGNORE, dirs_exist_ok=True)


def build() -> None:
    if TASK.exists():
        shutil.rmtree(TASK)
    copy(ROOT / "template", TASK)
    copy(ROOT / "src" / "original", TASK / "environment" / "app")

    tests = TASK / "tests"
    copy(ROOT / "grader", tests)
    copy(ROOT / "src" / "original", tests / "original")
    copy(ROOT / "src" / "original", tests / "reference")
    copy(ROOT / "src" / "reference", tests / "reference")
    copy(ROOT / "src" / "reference", TASK / "solution" / "overlay")

    sys.path.insert(0, str(ROOT / "grader"))
    from mutants import MUTANTS

    for mutant in MUTANTS:
        text = (tests / "reference" / mutant["file"]).read_text()
        count = text.count(mutant["old"])
        if count != 1:
            raise SystemExit(f"mutant {mutant['name']}: 'old' occurs {count} times, expected 1")
    print(f"built {TASK.relative_to(ROOT.parent.parent)} ({len(MUTANTS)} mutants)")


def grade(app: Path, label: str) -> float:
    with tempfile.TemporaryDirectory() as tmp:
        out, work = Path(tmp) / "out", Path(tmp) / "work"
        subprocess.run(
            [sys.executable, str(TASK / "tests" / "grade.py"),
             "--app", str(app), "--out", str(out), "--work", str(work)],
            check=True,
            capture_output=True,
        )
        score = json.loads((out / "score.json").read_text())
    parts = ", ".join(f"{k} {v['points']:.1f}" for k, v in score["parts"].items())
    print(f"{label:<10} {score['score']:6.2f}/100  ({parts})")
    return score["score"]


def check() -> None:
    reference = grade(TASK / "tests" / "reference", "reference")
    original = grade(TASK / "environment" / "app", "original")
    if reference < 99:
        raise SystemExit("the reference solution should score about 100")
    if original > 25:
        raise SystemExit("the starting code should score low")
    print("check passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="grade reference and original locally")
    args = parser.parse_args()
    build()
    if args.check:
        check()
