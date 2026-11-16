#!/usr/bin/env bash
# Run the 3D-SVG task with all four harnesses. Settings and credentials: see
# scripts/run-harnesses.sh. Prints where each harness's scene.svg was saved.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="${OUT:-$ROOT/jobs/svg-compare}"

"$ROOT/scripts/run-harnesses.sh" "$HERE/task" "$OUT" "$@"

for log in "$OUT"/*.log; do
  harness="$(basename "$log" .log)"
  svg=$(ls "$OUT/$harness"/*/*/verifier/scene.svg 2>/dev/null | tail -1 || true)
  echo "$harness: ${svg:-no scene.svg (see $log)}"
done
