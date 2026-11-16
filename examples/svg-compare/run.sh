#!/usr/bin/env bash
# Run the 3D-SVG task with four harnesses in parallel, all on the same model and effort.
#
# Needs: Docker, `harbor` on PATH, this repo's deps installed, and credentials:
#   ANTHROPIC_API_KEY      an Anthropic API key, used by all four harnesses, or
#   ANTHROPIC_AUTH_TOKEN   an OAuth access token (e.g. `ant auth print-credentials --access-token`)
# Optional:
#   MODEL (default anthropic/claude-opus-5-5), EFFORT (default medium),
#   OUT (default ./jobs/svg-compare), EXTRA_COMPOSE (a Docker Compose overlay to add).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
MODEL="${MODEL:-anthropic/claude-opus-5-5}"
EFFORT="${EFFORT:-medium}"
OUT="${OUT:-$ROOT/jobs/svg-compare}"
export PYTHONPATH="$ROOT:$HERE${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$OUT"

common=(-p "$HERE/task" -m "$MODEL" -n 1 -y)
if [[ -n "${EXTRA_COMPOSE:-}" ]]; then common+=(--extra-docker-compose "$EXTRA_COMPOSE"); fi

if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  cc_auth=(--ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY")
  swe_auth=(--ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY")
  pi_auth=(--ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY")
  pi_agent=pi
elif [[ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
  cc_auth=(--ae ANTHROPIC_AUTH_TOKEN="$ANTHROPIC_AUTH_TOKEN")
  swe_auth=(--ae ANTHROPIC_API_KEY="$ANTHROPIC_AUTH_TOKEN")  # LiteLLM sends OAuth tokens as Bearer
  # Pi changes its behavior when its API key is an OAuth token, so it gets a dummy key
  # and the token as a header. See pi_bearer.py.
  pi_auth=(--ae ANTHROPIC_API_KEY=dummy-key --ae PI_ANTHROPIC_BEARER="Bearer $ANTHROPIC_AUTH_TOKEN")
  pi_agent=pi_bearer:PiBearer
else
  echo "Set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN." >&2
  exit 1
fi

harbor run "${common[@]}" -o "$OUT/minipy" -a minipy_agent:MiniPyAgent \
  --ak effort="$EFFORT" --ak fallbacks=none > "$OUT/minipy.log" 2>&1 &
harbor run "${common[@]}" -o "$OUT/claude-code" -a claude-code \
  --ak reasoning_effort="$EFFORT" "${cc_auth[@]}" > "$OUT/claude-code.log" 2>&1 &
harbor run "${common[@]}" -o "$OUT/mini-swe-agent" -a mini-swe-agent \
  --ak reasoning_effort="$EFFORT" "${swe_auth[@]}" > "$OUT/mini-swe-agent.log" 2>&1 &
harbor run "${common[@]}" -o "$OUT/pi" -a "$pi_agent" \
  --ak reasoning_effort="$EFFORT" "${pi_auth[@]}" > "$OUT/pi.log" 2>&1 &
wait

for h in minipy claude-code mini-swe-agent pi; do
  svg=$(ls "$OUT/$h"/*/*/verifier/scene.svg 2>/dev/null | tail -1 || true)
  echo "$h: ${svg:-no scene.svg (see $OUT/$h.log)}"
done
