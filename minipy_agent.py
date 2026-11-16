"""minipy: a minimal agent harness for Harbor where the model's only tool is Python.

The model has exactly one tool, `run_python`. Each call writes the given code to
a fresh script inside the task container and runs it with python3. Nothing else:
no shell tool, no file editor, no persistent interpreter. State carries over
between steps only through the filesystem (and whatever processes a script
leaves running).

Run it with:
    harbor run -d terminal-bench/terminal-bench@4.1.0 \
        -a minipy_agent:MiniPyAgent -m anthropic/claude-opus-5-5
"""

from __future__ import annotations

import json
import os
import shlex
import tempfile
import time
from pathlib import Path

from anthropic import AsyncAnthropic

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

SYSTEM_PROMPT = """\
You are an autonomous agent solving a task inside a Linux container. You cannot \
talk to a human; nobody will answer questions.

Your only way to act is the `run_python` tool. Each call saves your code to a new \
file and runs it with `python3` in the container, then shows you its exit code, \
stdout and stderr. Every call is a fresh process: variables do not survive \
between calls, but files you write do. Use `subprocess` from inside your script \
when you need to run other programs.

Work step by step: inspect, act, then check your result. When the task is fully \
done and verified, reply with a short summary and no tool call; that ends the run.\
"""

TOOL = {
    "name": "run_python",
    "description": (
        "Write a Python 3 script into the container and run it with python3. "
        "Returns the exit code, stdout and stderr. Each call is a separate process."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Full Python source to run."},
            "timeout_sec": {
                "type": "integer",
                "description": "Max seconds to let the script run (default 600).",
            },
        },
        "required": ["code"],
        "additionalProperties": False,
    },
    "strict": True,
}

SCRIPT_DIR = "/tmp/minipy"

# Installs python3 if the task image lacks it. This is harness setup, not a tool
# the model sees.
ENSURE_PYTHON = r"""
command -v python3 >/dev/null 2>&1 && exit 0
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && apt-get install -y -qq python3
elif command -v apk >/dev/null 2>&1; then apk add --no-cache python3
elif command -v dnf >/dev/null 2>&1; then dnf install -y python3
elif command -v yum >/dev/null 2>&1; then yum install -y python3
else echo "no package manager found" >&2; exit 1
fi
"""


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n... [{len(text) - limit} chars cut] ...\n{text[-half:]}"


class MiniPyAgent(BaseAgent):
    def __init__(
        self,
        *args,
        max_steps: int | str = 200,
        effort: str = "high",
        max_output_chars: int | str = 20000,
        fallbacks: str = "default",
        install_python: bool | str = True,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.max_steps = int(max_steps)
        self.effort = effort
        self.max_output_chars = int(max_output_chars)
        # "default" lets the API re-run a refused request on another model;
        # "none" turns that off so every step is answered by the model you named.
        self.fallbacks = fallbacks
        self.install_python = str(install_python).lower() not in ("0", "false", "no")

    @staticmethod
    def name() -> str:
        return "minipy"

    def version(self) -> str:
        return "0.1.0"

    @property
    def api_model(self) -> str:
        name = self.model_name or "anthropic/claude-opus-5-5"
        return name.split("/", 1)[-1]

    async def setup(self, environment: BaseEnvironment) -> None:
        if self.install_python:
            res = await environment.exec(
                f"sh -c {shlex.quote(ENSURE_PYTHON)}", timeout_sec=600
            )
            if res.return_code != 0:
                self.logger.warning("python3 install failed: %s", res.stderr)
        await environment.exec(f"mkdir -p {SCRIPT_DIR}", timeout_sec=30)

    async def _run_python(
        self, environment: BaseEnvironment, name: str, code: str, timeout: int
    ) -> tuple[str, bool]:
        remote = f"{SCRIPT_DIR}/{name}.py"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            local = f.name
        try:
            await environment.upload_file(local, remote)
        finally:
            os.unlink(local)
        try:
            res = await environment.exec(f"python3 {remote}", timeout_sec=timeout)
        except Exception as e:  # timeouts and transport errors go back to the model
            return f"Error running script: {type(e).__name__}: {e}", True
        out = _clip(res.stdout or "", self.max_output_chars)
        err = _clip(res.stderr or "", self.max_output_chars)
        return f"exit_code: {res.return_code}\n--- stdout ---\n{out}\n--- stderr ---\n{err}", False

    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        client = AsyncAnthropic()
        messages: list[dict] = [{"role": "user", "content": instruction}]
        traj_path = Path(self.logs_dir) / "trajectory.jsonl"
        traj_path.parent.mkdir(parents=True, exist_ok=True)
        totals = {"in": 0, "cache_read": 0, "cache_write": 0, "out": 0}

        extra: dict = {}
        if self.fallbacks != "none":
            extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": self.fallbacks}

        with traj_path.open("a") as traj:
            for step in range(1, self.max_steps + 1):
                t0 = time.time()
                async with client.beta.messages.stream(
                    model=self.api_model,
                    max_tokens=64000,
                    system=SYSTEM_PROMPT,
                    tools=[TOOL],
                    messages=messages,
                    thinking={"type": "adaptive"},
                    output_config={"effort": self.effort},
                    cache_control={"type": "ephemeral"},
                    **extra,
                ) as stream:
                    resp = await stream.get_final_message()

                u = resp.usage
                totals["in"] += u.input_tokens or 0
                totals["cache_read"] += u.cache_read_input_tokens or 0
                totals["cache_write"] += u.cache_creation_input_tokens or 0
                totals["out"] += u.output_tokens or 0

                # Append the assistant turn unchanged (keeps thinking blocks valid).
                messages.append({"role": "assistant", "content": resp.content})
                calls = [b for b in resp.content if b.type == "tool_use"]
                record = {
                    "step": step,
                    "model": resp.model,
                    "stop_reason": resp.stop_reason,
                    "text": [b.text for b in resp.content if b.type == "text"],
                    "calls": [],
                    "secs": round(time.time() - t0, 1),
                }

                if resp.stop_reason == "refusal":
                    details = getattr(resp, "stop_details", None)
                    record["refusal"] = str(details) if details else None
                    traj.write(json.dumps(record) + "\n")
                    break

                if not calls:
                    traj.write(json.dumps(record) + "\n")
                    if resp.stop_reason == "max_tokens":
                        messages.append({"role": "user", "content": "Your reply was cut off. Continue."})
                        continue
                    break  # end_turn with no tool call: the model says it is done

                results = []
                for i, c in enumerate(calls):
                    inp = c.input if isinstance(c.input, dict) else {}
                    code = inp.get("code")
                    if not isinstance(code, str):
                        out, is_err = "Error: run_python needs a 'code' string.", True
                    else:
                        timeout = int(inp.get("timeout_sec") or 600)
                        out, is_err = await self._run_python(
                            environment, f"step_{step:04d}_{i}", code, timeout
                        )
                    record["calls"].append({"code": code, "result": out})
                    results.append(
                        {"type": "tool_result", "tool_use_id": c.id, "content": out, "is_error": is_err}
                    )
                messages.append({"role": "user", "content": results})
                traj.write(json.dumps(record) + "\n")
                traj.flush()

        context.n_input_tokens = totals["in"] + totals["cache_read"] + totals["cache_write"]
        context.n_cache_tokens = totals["cache_read"]
        context.n_output_tokens = totals["out"]
        context.metadata = {"steps": step, "usage": totals}
