"""Harbor's Pi agent, authenticated with an OAuth bearer token on Pi's normal API-key path.

Pi switches into a "Claude Code" mode (identity prompt, renamed tools, Claude Code
headers) when its API key is an OAuth token. To keep Pi's own behavior, Pi gets a dummy
API key and the real token goes in an Authorization header through a models.json
provider override. The API uses the bearer token and ignores the dummy x-api-key.
Pi's code, prompts, models and thinking settings are otherwise unchanged.
"""

import json
import shlex

from harbor.agents.installed.pi import Pi

# `$NAME` is Pi's syntax for reading an environment variable in models.json.
_MODELS_JSON = {"providers": {"anthropic": {"headers": {"Authorization": "$PI_ANTHROPIC_BEARER"}}}}


class PiBearer(Pi):
    @staticmethod
    def name() -> str:
        return "pi"

    async def run(self, instruction, environment, context):
        body = shlex.quote(json.dumps(_MODELS_JSON))
        # Write as the agent user so it lands in the same $HOME that pi reads.
        await self.exec_as_agent(
            environment,
            command=f"mkdir -p ~/.pi/agent && printf %s {body} > ~/.pi/agent/models.json",
        )
        return await super().run(instruction, environment, context)
