#!/usr/bin/env bash
# Build the tally task, run harnesses on it and print the report.
#
#   benchmarks/tally/run.sh [HARNESS...]
#
# Settings and credentials: see scripts/run-harnesses.sh (ATTEMPTS=3 is a good start).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="${OUT:-$ROOT/jobs/tally-$(date +%Y%m%d-%H%M%S)}"

python3 "$HERE/build.py"
"$ROOT/scripts/run-harnesses.sh" "$HERE/task" "$OUT" "$@"
python3 "$HERE/report.py" "$OUT" --json "$OUT/report.json" | tee "$OUT/report.md"
