#!/usr/bin/env bash
# Run one Harbor task with several harnesses in parallel, all on the same model and effort.
#
#   scripts/run-harnesses.sh TASK_DIR OUT_DIR [HARNESS...]
#
# HARNESS is any of: minipy claude-code mini-swe-agent pi (default: all four).
# Results go to OUT_DIR/<harness>/, logs to OUT_DIR/<harness>.log.
#
# Needs Docker, `harbor` on PATH, and one credential:
#   ANTHROPIC_API_KEY      an Anthropic API key, or
#   ANTHROPIC_AUTH_TOKEN   an OAuth access token (e.g. `ant auth print-credentials --access-token`)
# Optional:
#   MODEL          default anthropic/claude-opus-5-5
#   EFFORT         default medium
#   ATTEMPTS       attempts per harness, default 1 (run one after another)
#   EXTRA_COMPOSE  a Docker Compose overlay to add to every container
set -euo pipefail

if [[ $# -lt 2 ]]; then
  sed -n '2,16p' "$0" >&2
  exit 2
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK="$(cd "$1" && pwd)"
OUT="$2"
shift 2
if [[ $# -eq 0 ]]; then set -- minipy claude-code mini-swe-agent pi; fi

MODEL="${MODEL:-anthropic/claude-opus-5-5}"
EFFORT="${EFFORT:-medium}"
ATTEMPTS="${ATTEMPTS:-1}"
export PYTHONPATH="$ROOT:$ROOT/harnesses${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$OUT"

if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  key_env=(--ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY")
  cc_auth=("${key_env[@]}") swe_auth=("${key_env[@]}") pi_auth=("${key_env[@]}")
  pi_agent=pi
elif [[ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
  cc_auth=(--ae ANTHROPIC_AUTH_TOKEN="$ANTHROPIC_AUTH_TOKEN")
  # LiteLLM sends OAuth tokens as a bearer token.
  swe_auth=(--ae ANTHROPIC_API_KEY="$ANTHROPIC_AUTH_TOKEN")
  # Pi changes its behavior when its API key is an OAuth token, so it gets a dummy
  # key and the token as a header. See harnesses/pi_bearer.py.
  pi_auth=(--ae ANTHROPIC_API_KEY=dummy-key --ae PI_ANTHROPIC_BEARER="Bearer $ANTHROPIC_AUTH_TOKEN")
  pi_agent=pi_bearer:PiBearer
else
  echo "Set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN." >&2
  exit 1
fi

common=(-p "$TASK" -m "$MODEL" -k "$ATTEMPTS" -n 1 -y)
if [[ -n "${EXTRA_COMPOSE:-}" ]]; then common+=(--extra-docker-compose "$EXTRA_COMPOSE"); fi

for harness in "$@"; do
  case "$harness" in
    minipy)
      args=(-a minipy_agent:MiniPyAgent --ak effort="$EFFORT" --ak fallbacks=none) ;;
    claude-code)
      args=(-a claude-code --ak reasoning_effort="$EFFORT" "${cc_auth[@]}") ;;
    mini-swe-agent)
      args=(-a mini-swe-agent --ak reasoning_effort="$EFFORT" "${swe_auth[@]}") ;;
    pi)
      args=(-a "$pi_agent" --ak reasoning_effort="$EFFORT" "${pi_auth[@]}") ;;
    *)
      echo "unknown harness: $harness" >&2
      exit 2 ;;
  esac
  echo "running $harness ($ATTEMPTS attempt(s)) -> $OUT/$harness"
  harbor run "${common[@]}" -o "$OUT/$harness" "${args[@]}" > "$OUT/$harness.log" 2>&1 &
done
wait
echo "done: $OUT"
