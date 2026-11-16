"""Summarize tally benchmark runs: quality score and efficiency for each harness.

    python report.py JOBS_DIR [--json OUT.json]

JOBS_DIR holds one folder per harness, as written by scripts/run-harnesses.sh.
Prints a Markdown report. Cost is computed the same way for every harness from
its token counts, at the list price of the model the run used (input not read
from cache is priced as a cache write, which is what nearly all of it is in these
agents). Claude Haiku 5.5 is priced at its rate for prompts up to 100K tokens; a
run whose prompts grow past that pays up to 5x more, so treat it as a lower bound.
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path

# USD per million tokens. Cache writes are 5-minute writes (1.25x input).
PRICES = {
    "claude-opus-5-5": {"cache_write": 5.00, "cache_read": 0.20, "output": 20.00},
    "claude-sonnet-5-5": {"cache_write": 2.50, "cache_read": 0.10, "output": 10.00},
    "claude-haiku-5-5": {"cache_write": 0.125, "cache_read": 0.01, "output": 0.50},
}
PARTS = ["feature", "bug", "regressions", "performance", "tests", "hygiene"]


def seconds_between(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
    return (parse(end) - parse(start)).total_seconds()


def turns_and_calls(agent_dir: Path, result: dict) -> tuple[int | None, int | None]:
    atif = agent_dir / "trajectory.json"
    if atif.exists():
        steps = json.loads(atif.read_text()).get("steps", [])
        turns = sum(1 for s in steps if s.get("source") == "agent")
        calls = sum(len(s.get("tool_calls") or []) for s in steps)
        return turns, calls
    jsonl = agent_dir / "trajectory.jsonl"  # minipy
    if jsonl.exists():
        records = [json.loads(line) for line in jsonl.read_text().splitlines() if line.strip()]
        return len(records), sum(len(r.get("calls", [])) for r in records)
    steps = ((result.get("agent_result") or {}).get("metadata") or {}).get("steps")
    return steps, None


def trial(path: Path) -> dict:
    result = json.loads((path / "result.json").read_text())
    agent = result.get("agent_result") or {}
    execution = result.get("agent_execution") or {}
    tokens_in = agent.get("n_input_tokens") or 0
    cached = agent.get("n_cache_tokens") or 0
    tokens_out = agent.get("n_output_tokens") or 0
    model = ((result.get("agent_info") or {}).get("model_info") or {}).get("name") or ""
    price = PRICES.get(model)
    cost = (
        (
            (tokens_in - cached) * price["cache_write"]
            + cached * price["cache_read"]
            + tokens_out * price["output"]
        )
        / 1e6
        if price
        else None
    )
    score_path = path / "verifier" / "score.json"
    score = json.loads(score_path.read_text()) if score_path.exists() else None
    turns, calls = turns_and_calls(path / "agent", result)
    return {
        "trial": path.name,
        "score": score["score"] if score else 0.0,
        "parts": {k: score["parts"][k]["points"] for k in PARTS} if score else {},
        "details": score["parts"] if score else {},
        "diff": score.get("diff") if score else {},
        "agent_seconds": seconds_between(execution.get("started_at"), execution.get("finished_at")),
        "turns": turns,
        "tool_calls": calls,
        "input_tokens": tokens_in,
        "cached_tokens": cached,
        "output_tokens": tokens_out,
        "model": model,
        "cost_usd": None if cost is None else round(cost, 4),
        "error": bool(result.get("exception_info")),
    }


def collect(jobs: Path) -> dict[str, list[dict]]:
    runs: dict[str, list[dict]] = {}
    for harness_dir in sorted(p for p in jobs.iterdir() if p.is_dir()):
        trials = [
            trial(p)
            for p in sorted(harness_dir.glob("*/*/"))
            if (p / "result.json").exists() and (p / "agent").exists()
        ]
        if trials:
            runs[harness_dir.name] = trials
    return runs


def mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def fmt(value, spec: str = ".1f", unit: str = "") -> str:
    return "–" if value is None else f"{value:{spec}}{unit}"


def summary(name: str, trials: list[dict]) -> dict:
    scores = [t["score"] for t in trials]
    return {
        "harness": name,
        "model": ", ".join(sorted({t["model"] for t in trials})),
        "attempts": len(trials),
        "score": mean(scores),
        "score_min": min(scores),
        "score_max": max(scores),
        "parts": {k: mean([t["parts"].get(k) for t in trials]) for k in PARTS},
        "minutes": (mean([t["agent_seconds"] for t in trials]) or 0) / 60,
        "turns": mean([t["turns"] for t in trials]),
        "tool_calls": mean([t["tool_calls"] for t in trials]),
        "input_tokens": mean([t["input_tokens"] for t in trials]),
        "output_tokens": mean([t["output_tokens"] for t in trials]),
        "cost_usd": mean([t["cost_usd"] for t in trials]),
    }


def markdown(rows: list[dict], runs: dict[str, list[dict]]) -> str:
    lines = [
        "## Score (out of 100)",
        "",
        f"Model: {', '.join(sorted({r['model'] for r in rows}))}",
        "",
        "| Harness | Runs | Score | Range | Feature /35 | Bug /15 | Regr. /10 | Perf /15 | Tests /15 | Hygiene /10 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        p = r["parts"]
        lines.append(
            f"| {r['harness']} | {r['attempts']} | **{fmt(r['score'])}** | "
            f"{r['score_min']:.1f}–{r['score_max']:.1f} | "
            + " | ".join(fmt(p[k]) for k in PARTS)
            + " |"
        )
    lines += [
        "",
        "## Efficiency (mean per run)",
        "",
        "| Harness | Minutes | Turns | Tool calls | Input tokens | Output tokens | Cost | Points per $ |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        per_dollar = r["score"] / r["cost_usd"] if r["cost_usd"] else None
        lines.append(
            f"| {r['harness']} | {fmt(r['minutes'])} | {fmt(r['turns'], '.0f')} | "
            f"{fmt(r['tool_calls'], '.0f')} | {fmt(r['input_tokens'], ',.0f')} | "
            f"{fmt(r['output_tokens'], ',.0f')} | ${fmt(r['cost_usd'], '.3f')} | "
            f"{fmt(per_dollar, '.0f')} |"
        )
    lines += ["", "## Per run", ""]
    for name, trials in runs.items():
        for t in trials:
            d = t["details"]
            perf = d.get("performance", {})
            tests = d.get("tests", {})
            hyg = d.get("hygiene", {})
            notes = []
            if d.get("feature", {}).get("failed"):
                notes.append(f"feature fails: {', '.join(d['feature']['failed'][:4])}")
            if d.get("bug", {}).get("failed"):
                notes.append(f"bug fails: {', '.join(d['bug']['failed'][:4])}")
            if perf:
                notes.append(f"perf {fmt(perf.get('agent_seconds'), '.1f', 's')} vs ref {perf.get('reference_seconds')}s"
                             + (f" ({perf['note']})" if perf.get("note") else ""))
            if tests:
                notes.append(f"tests {tests.get('valid', 0)}/{tests.get('total', 0)} valid, "
                             f"mutants {tests.get('mutants_killed', 0)}/{tests.get('mutants_total', 0)}")
            for key in ("lint", "clean_tree", "protected_tests"):
                items = hyg.get(key, {}).get("issues") or hyg.get(key, {}).get("stray") or hyg.get(key, {}).get("changed")
                if items:
                    notes.append(f"{key}: {', '.join(items[:3])}")
            lines.append(f"- **{name}** {t['trial']}: {t['score']:.1f} — " + "; ".join(notes))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("jobs", type=Path)
    parser.add_argument("--json", type=Path, help="also write the full data here")
    args = parser.parse_args()
    runs = collect(args.jobs)
    if not runs:
        raise SystemExit(f"no trials found under {args.jobs}")
    rows = sorted((summary(n, t) for n, t in runs.items()), key=lambda r: -(r["score"] or 0))
    print(markdown(rows, runs))
    if args.json:
        args.json.write_text(json.dumps({"summary": rows, "runs": runs}, indent=2))


if __name__ == "__main__":
    main()
