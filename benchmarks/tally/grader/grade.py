"""Score an agent's work on the tally task.

Writes score.json (full breakdown), reward.json ({"reward": 0..1}) and diff.patch
to the output directory, and prints a summary. Standard library only.

Usage: python grade.py [--app /app] [--out /logs/verifier] [--work /tmp/tally-grade]
"""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mutants import MUTANTS  # noqa: E402

WEIGHTS = {
    "feature": 35,
    "bug": 15,
    "regressions": 10,
    "performance": 15,
    "tests": 15,
    "hygiene": 10,
}
CACHE_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git"}
BIG_ARGS = ["--as-of", "2026-06-30", "--currency", "EUR"]
PERF_TIMEOUT = 120
TEST_TIMEOUT = 300


def is_cache(rel: Path) -> bool:
    return (
        any(part in CACHE_PARTS or part.endswith(".egg-info") for part in rel.parts)
        or rel.suffix == ".pyc"
    )


def tree_files(root: Path) -> dict[str, Path]:
    found = {}
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_file() and not is_cache(rel):
            found[rel.as_posix()] = path
    return found


def copy_tree(src: Path, dst: Path) -> Path:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(*CACHE_PARTS, "*.pyc", "*.egg-info"),
        symlinks=False,
    )
    return dst


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def python_env(project: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env.update(PYTHONPATH=str(project), PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
    return env


# --- running tests --------------------------------------------------------------


def run_tests(
    project: Path,
    files: list[Path],
    work: Path,
    only: list[str] | None = None,
    timeout: int = TEST_TIMEOUT,
) -> dict[str, str] | None:
    """Run test files against ``project``. Returns {test id: outcome}, None on timeout."""
    out = work / f"results-{time.monotonic_ns()}.json"
    cmd = [sys.executable, str(HERE / "runner.py"), "--project", str(project), "--out", str(out)]
    if only is not None:
        ids = work / f"only-{time.monotonic_ns()}.json"
        ids.write_text(json.dumps(only))
        cmd += ["--only", str(ids)]
    cmd += [str(f) for f in files]
    try:
        subprocess.run(
            cmd,
            cwd=project,
            env=python_env(project),
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    try:
        return json.loads(out.read_text())
    except (OSError, ValueError):
        return {}


def run_known(
    project: Path, files: list[Path], work: Path, ids: list[str]
) -> dict[str, str]:
    """Run tests whose ids are known; if the run hangs, retry one test at a time."""
    results = run_tests(project, files, work, only=ids)
    if results is not None:
        return results
    results = {}
    for test_id in ids:
        one = run_tests(project, files, work, only=[test_id], timeout=30)
        results[test_id] = "timeout" if one is None else one.get(test_id, "error")
    return results


def pass_rate(results: dict[str, str], ids: list[str]) -> tuple[int, int]:
    return sum(results.get(i) == "pass" for i in ids), len(ids)


# --- scoring parts --------------------------------------------------------------


def score_hidden(agent: Path, reference: Path, work: Path, name: str) -> dict:
    test_file = HERE / "hidden" / f"test_hidden_{name}.py"
    ref = run_tests(reference, [test_file], work) or {}
    ids = sorted(i for i, outcome in ref.items() if outcome == "pass")
    results = run_known(agent, [test_file], work, ids)
    passed, total = pass_rate(results, ids)
    return {
        "points": WEIGHTS[name] * passed / total if total else 0.0,
        "passed": passed,
        "total": total,
        "failed": sorted(i.split(".", 1)[1] for i in ids if results.get(i) != "pass"),
        "grader_warning": sorted(i for i, o in ref.items() if o != "pass"),
    }


def score_regressions(agent: Path, reference: Path, work: Path) -> dict:
    files = sorted((HERE / "original" / "tests").glob("test_*.py"))
    ref = run_tests(reference, files, work) or {}
    ids = sorted(i for i, outcome in ref.items() if outcome == "pass")
    results = run_known(agent, files, work, ids)
    passed, total = pass_rate(results, ids)
    return {
        "points": WEIGHTS["regressions"] * passed / total if total else 0.0,
        "passed": passed,
        "total": total,
        "failed": sorted(i for i in ids if results.get(i) != "pass"),
    }


def time_balance(project: Path, journal: Path) -> tuple[float | None, str, int]:
    cmd = [sys.executable, "-m", "tally", "balance", str(journal), *BIG_ARGS]
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=project,
            env=python_env(project),
            capture_output=True,
            text=True,
            timeout=PERF_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "", -1
    return time.perf_counter() - start, proc.stdout, proc.returncode


def score_performance(agent: Path, reference: Path, work: Path) -> dict:
    journal = work / "big.journal"
    subprocess.run(
        [sys.executable, str(HERE / "original" / "scripts" / "make_big_journal.py"), str(journal)],
        check=True,
        capture_output=True,
    )
    ref_times, ref_out = [], ""
    for _ in range(2):
        seconds, ref_out, _ = time_balance(reference, journal)
        ref_times.append(seconds)
    ref_time = min(ref_times)

    seconds, out, code = time_balance(agent, journal)
    detail = {"reference_seconds": round(ref_time, 3), "agent_seconds": None}
    if seconds is None:
        return {**detail, "points": 0.0, "note": f"timed out after {PERF_TIMEOUT}s"}
    if code != 0 or out != ref_out:
        return {**detail, "agent_seconds": round(seconds, 3), "points": 0.0, "note": "wrong output"}
    if seconds < 30:
        again, out2, _ = time_balance(agent, journal)
        if again is not None and out2 == ref_out:
            seconds = min(seconds, again)
    ratio = seconds / ref_time
    if ratio <= 1.5:
        points = WEIGHTS["performance"]
    elif ratio >= 15:
        points = 0.0
    else:
        points = WEIGHTS["performance"] * (1 - math.log(ratio / 1.5) / math.log(10))
    return {**detail, "agent_seconds": round(seconds, 3), "ratio": round(ratio, 2), "points": points}


def apply_mutant(tree: Path, mutant: dict) -> None:
    path = tree / mutant["file"]
    text = path.read_text()
    path.write_text(text.replace(mutant["old"], mutant["new"], 1))


def score_tests(agent: Path, reference: Path, work: Path) -> dict:
    original_tests = set((HERE / "original" / "tests").glob("*.py"))
    original_names = {p.name for p in original_tests}
    target = agent / "tests" / "test_recurring.py"
    if not target.exists():
        return {"points": 0.0, "note": "tests/test_recurring.py missing", "valid": 0, "total": 0}

    # The agent's tests, on top of the reference implementation.
    base = copy_tree(reference, work / "ref-with-agent-tests")
    for path in (agent / "tests").glob("*.py"):
        if path.name not in original_names:
            shutil.copy2(path, base / "tests" / path.name)
    test_file = base / "tests" / "test_recurring.py"
    on_reference = run_tests(base, [test_file], work)
    if on_reference is None:
        return {"points": 0.0, "note": "tests hung on the reference", "valid": 0, "total": 0}
    total = len(on_reference)
    valid = sorted(i for i, outcome in on_reference.items() if outcome == "pass")
    validity = (
        WEIGHTS["tests"] / 3 * (len(valid) / total) * min(1.0, total / 5) if total else 0.0
    )

    killed, survived = [], []
    for mutant in MUTANTS:
        tree = copy_tree(base, work / "mutant")
        apply_mutant(tree, mutant)
        results = run_known(tree, [tree / "tests" / "test_recurring.py"], work, valid) if valid else {}
        if valid and any(results.get(i) != "pass" for i in valid):
            killed.append(mutant["name"])
        else:
            survived.append(mutant["name"])
    mutation = WEIGHTS["tests"] * 2 / 3 * len(killed) / len(MUTANTS)

    on_agent = run_tests(agent, [target], work) or {}
    return {
        "points": validity + mutation,
        "total": total,
        "valid": len(valid),
        "invalid": sorted(i for i in on_reference if i not in valid),
        "mutants_killed": len(killed),
        "mutants_total": len(MUTANTS),
        "survived": survived,
        "pass_on_own_code": sum(o == "pass" for o in on_agent.values()),
    }


def lint_issues(agent: Path, original: Path) -> list[str]:
    issues = []
    for path in sorted((agent / "tally").rglob("*.py")):
        rel = path.relative_to(agent).as_posix()
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            module = ast.parse(source)
        except SyntaxError as error:
            issues.append(f"{rel}:{error.lineno}: syntax error")
            continue
        used = {n.id for n in ast.walk(module) if isinstance(n, ast.Name)}
        exported = set()
        for node in ast.walk(module):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
            ):
                exported |= {
                    c.value for c in ast.walk(node.value) if isinstance(c, ast.Constant)
                }
        for node in ast.walk(module):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                    continue
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    if name in {"pdb", "ipdb"}:
                        issues.append(f"{rel}:{node.lineno}: debugger import")
                    elif (
                        name not in used
                        and name not in exported
                        and path.name != "__init__.py"
                        and alias.name != "*"
                    ):
                        issues.append(f"{rel}:{node.lineno}: unused import {name}")
            elif isinstance(node, ast.ExceptHandler) and node.type is None:
                issues.append(f"{rel}:{node.lineno}: bare except")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "breakpoint":
                    issues.append(f"{rel}:{node.lineno}: breakpoint()")
                elif node.func.id == "print" and path.name not in {"cli.py", "__main__.py"}:
                    issues.append(f"{rel}:{node.lineno}: print() in library code")
        before = original / "tally" / path.name
        old_marks = len(re.findall(r"\b(TODO|FIXME|XXX)\b", before.read_text())) if before.exists() else 0
        new_marks = len(re.findall(r"\b(TODO|FIXME|XXX)\b", source))
        if new_marks > old_marks:
            issues.append(f"{rel}: {new_marks - old_marks} new TODO/FIXME/XXX")
    return issues


def unreleased_bullets(text: str) -> list[str]:
    match = re.search(r"^## Unreleased\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        return []
    return [
        line.strip()
        for line in match[1].splitlines()
        if line.strip().startswith(("-", "*"))
    ]


def score_hygiene(app_files: dict[str, Path], agent: Path, original: Path) -> dict:
    original_files = tree_files(original)

    changed_tests = [
        rel
        for rel, path in original_files.items()
        if rel.startswith("tests/")
        and (rel not in app_files or digest(app_files[rel]) != digest(path))
    ]
    protected = max(0, 3 - len(changed_tests))

    def allowed(rel: str) -> bool:
        return (
            re.fullmatch(r"tests/test_\w+\.py", rel) is not None
            or re.fullmatch(r"tally/\w+\.py", rel) is not None
            or re.fullmatch(r"docs/[\w.-]+\.md", rel) is not None
        )

    stray = sorted(rel for rel in app_files if rel not in original_files and not allowed(rel))
    deleted = sorted(
        rel for rel in original_files if rel not in app_files and not rel.startswith("tests/")
    )
    tidy = max(0, 2 - len(stray) - len(deleted))

    issues = lint_issues(agent, original)
    lint = max(0, 3 - len(issues))

    changelog_path = agent / "CHANGELOG.md"
    old = set(unreleased_bullets((original / "CHANGELOG.md").read_text()))
    new = [
        b
        for b in unreleased_bullets(changelog_path.read_text() if changelog_path.exists() else "")
        if b not in old
    ]
    words = " ".join(new).lower()
    changelog = int("recurring" in words) + int(
        any(w in words for w in ("rate", "exchange", "conver", "price", "perf", "fast", "slow", "speed"))
    )
    return {
        "points": protected + tidy + lint + changelog,
        "protected_tests": {"points": protected, "changed": changed_tests},
        "clean_tree": {"points": tidy, "stray": stray, "deleted": deleted},
        "lint": {"points": lint, "issues": issues},
        "changelog": {"points": changelog, "new_entries": new},
    }


def write_diff(original: Path, agent: Path, out: Path) -> dict:
    old_files, new_files = tree_files(original), tree_files(agent)
    chunks, added, removed = [], 0, 0
    for rel in sorted(set(old_files) | set(new_files)):
        a = old_files[rel].read_text(errors="replace").splitlines(True) if rel in old_files else []
        b = new_files[rel].read_text(errors="replace").splitlines(True) if rel in new_files else []
        if a == b:
            continue
        diff = list(difflib.unified_diff(a, b, f"a/{rel}", f"b/{rel}"))
        added += sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        removed += sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
        chunks.extend(diff)
    (out / "diff.patch").write_text("".join(chunks))
    return {"lines_added": added, "lines_removed": removed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", default="/app")
    parser.add_argument("--out", default="/logs/verifier")
    parser.add_argument("--work", default="/tmp/tally-grade")
    args = parser.parse_args()

    app, out, work = Path(args.app), Path(args.out), Path(args.work)
    out.mkdir(parents=True, exist_ok=True)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    original = HERE / "original"

    app_files = tree_files(app)
    agent = copy_tree(app, work / "agent")
    reference = copy_tree(HERE / "reference", work / "reference")

    started = time.perf_counter()
    parts = {
        "feature": score_hidden(agent, reference, work, "feature"),
        "bug": score_hidden(agent, reference, work, "bug"),
        "regressions": score_regressions(agent, reference, work),
        "performance": score_performance(agent, reference, work),
        "tests": score_tests(agent, reference, work),
        "hygiene": score_hygiene(app_files, agent, original),
    }
    for part in parts.values():
        part["points"] = round(part["points"], 2)
    total = round(sum(part["points"] for part in parts.values()), 2)
    score = {
        "score": total,
        "max": sum(WEIGHTS.values()),
        "weights": WEIGHTS,
        "parts": parts,
        "diff": write_diff(original, agent, out),
        "grading_seconds": round(time.perf_counter() - started, 1),
    }
    (out / "score.json").write_text(json.dumps(score, indent=2))
    (out / "reward.json").write_text(json.dumps({"reward": round(total / 100, 4)}))

    print(f"score {total}/100")
    for name, part in parts.items():
        print(f"  {name:<12} {part['points']:>6.2f} / {WEIGHTS[name]}")
    print(json.dumps(score, indent=2))


if __name__ == "__main__":
    main()
