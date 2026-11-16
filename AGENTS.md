# AGENTS.md

Guidance for coding agents working in this repository.

## What this is

minipy is a Harbor agent harness. The model under test gets exactly one tool, `run_python`, and nothing else. That constraint is the point of the project, so changes must keep it.

## Layout

- `minipy_agent.py`: the whole harness (`MiniPyAgent`, a Harbor `BaseAgent`).
- `examples/svg-compare/`: a four-harness comparison on one SVG task.
  - `task/`: the Harbor task (instruction, environment, checker).
  - `pi_bearer.py`: Harbor's Pi agent with OAuth-token auth that keeps Pi in its normal mode.
  - `run.sh`: runs all four harnesses in parallel.
  - `results/`: rendered outputs from the published run.

## Rules for changes to the harness

- **Keep one tool.** Do not add tools, shell access, file editors or a persistent interpreter for the model. Setup work the harness does itself (like installing `python3`) is fine, as long as the model never sees it as a tool.
- **Keep the history append-only.** Append each assistant response's `content` unchanged and never edit or drop earlier turns. Thinking blocks must be passed back as received.
- **Keep the model's view honest.** Tool results report the real exit code, stdout and stderr. When clipping, keep the head and tail and say how much was cut.
- **Keep it small.** The harness should stay readable in one sitting. Prefer removing code to adding options.
- **Use the Anthropic SDK** (`anthropic`), not raw HTTP. Keep streaming on, since responses can be long.

## Secrets

Never commit API keys, OAuth tokens or `.env` files. Pass credentials through environment variables, as `run.sh` does.

## Checking a change

There is no unit test suite. Check changes by running real tasks:

```bash
uv venv && uv pip install -e .
python -c "import minipy_agent"
harbor run -p examples/svg-compare/task -a minipy_agent:MiniPyAgent \
  -m anthropic/claude-opus-5-5 --ak effort=low --ak fallbacks=none -n 1 -y
```

A passing run writes `verifier/reward.txt` with `1` and `agent/trajectory.jsonl` in the trial folder under `jobs/`. Each run costs real API money, so use one task at low effort for quick checks.
