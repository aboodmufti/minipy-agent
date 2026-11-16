# tally: one task that measures a harness from every side

A single Harbor task, built to compare coding-agent harnesses running the same model.
The agent gets a small, realistic Python repository and one ticket with three items,
like a pull request:

1. **Fix a bug.** Exchange rates are looked up for the wrong date (the next price
   instead of the one in effect). One existing test fails.
2. **Fix a performance problem.** `balance` re-sorts and linearly scans all prices for
   every transaction. On the 200,000-transaction journal from
   `scripts/make_big_journal.py` it takes about a minute; a good fix takes 1–2 seconds.
3. **Build a feature from a written spec, with tests.** Recurring transactions
   (`docs/recurring.md`): parsing, date arithmetic with real edge cases (January 31
   to February 28 or 29, February 29 in common years, intervals, inclusive end
   dates), and their effect on balances and registers.

The repository is standard library only, so the task needs no network and no package
installs, and grading is deterministic apart from timing.

## Scoring

A hidden grader (`grader/grade.py`) scores the final state of `/app` out of 100:

| Part | Points | How it is measured |
|---|---|---|
| Feature | 35 | 31 hidden tests of the spec: dates, parsing, errors, balances, registers, CLI output. |
| Bug | 15 | 10 hidden tests of rate lookups, including same-day prices, prices added out of order and after a lookup, and dates before the first price. |
| Regressions | 10 | The original tests, run from pristine copies, so editing them doesn't help. |
| Performance | 15 | `balance` on the big journal, timed against the reference solution in the same container. Full points up to 1.5× the reference, zero at 15× or slower, logarithmic in between. Output must match the reference exactly. |
| Test quality | 15 | Mutation testing of the agent's `tests/test_recurring.py`. 5 points: share of its tests that pass on the reference implementation (scaled down below 5 tests). 10 points: share of 13 deliberately broken implementations (`grader/mutants.py`) that its valid tests catch. |
| Hygiene | 10 | 3: original tests unchanged. 2: no stray or deleted files. 3: no lint issues in `tally/` (unused imports, bare `except`, `print` in library code, debugger calls, new TODOs). 2: changelog entries for the feature and the fix. |

The grader writes `score.json` (full breakdown), `reward.json` (score / 100, which
Harbor reports) and `diff.patch` (the agent's changes) to the trial's `verifier/`
folder.

Efficiency is measured for every run, separately from the score: agent time, turns,
tool calls, input and output tokens, and cost. `report.py` computes cost the same way
for every harness from its token counts.

Calibration, from `build.py --check` and Harbor runs of the built-in agents:

| Run | Score |
|---|---|
| Reference solution (Harbor `oracle` agent) | 100 |
| No changes (Harbor `nop` agent) | 21.3 |

## Running it

```bash
# Build the task into ./task and check the grader: reference ≈ 100, starting code low.
python benchmarks/tally/build.py --check

# Run harnesses and print the report. Credentials and settings: scripts/run-harnesses.sh.
ATTEMPTS=3 benchmarks/tally/run.sh minipy claude-code mini-swe-agent pi
```

Each attempt is one full agent run. Use several attempts per harness: single runs
of the same harness vary.

## Layout

- `src/original/`: the repository the agent starts from (`/app`).
- `src/reference/`: the files the reference solution changes or adds.
- `grader/`: `grade.py`, `runner.py`, `mutants.py` and the hidden tests.
- `template/`: `task.toml`, the agent's instructions, the Dockerfile, and the verifier and oracle entry points.
- `build.py`: assembles `task/` from the above and checks the mutants.
- `report.py`: turns a jobs folder into a Markdown report.
- `run.sh`: build, run, report.

`task/` is generated; don't edit it by hand.
