"""Harbor adapter for Terminal-Bench 2.0.

    harbor run -d terminal-bench@2.0 --agent-import-path cael_unified.terminal_agent.harbor_agent:CaelAgent

Interface as in harbor/agents/base.py (checked 2026-11-18): static name(), version(), async setup(environment),
async run(instruction, environment, context). CAEL runs on the harness side and only sends shell commands into the
container through environment.exec; nothing is installed in the container and no model is called.
"""
import json
from pathlib import Path

from .agent import solve

try:
    from harbor.agents.base import BaseAgent
except ImportError:            # lets the module load (and be tested) where Harbor is not installed
    class BaseAgent:
        def __init__(self, logs_dir=None, model_name=None, logger=None, *args, **kwargs):
            self.logs_dir = Path(logs_dir) if logs_dir else None


VERSION = '0.4.3-dev'


class CaelAgent(BaseAgent):
    @staticmethod
    def name():
        return 'cael'

    def version(self):
        return VERSION

    async def setup(self, environment):
        return None

    async def run(self, instruction, environment, context):
        trail = await solve(instruction, environment)
        logs = getattr(self, 'logs_dir', None)
        if logs:
            Path(logs).mkdir(parents=True, exist_ok=True)
            (Path(logs) / 'cael_trajectory.json').write_text(json.dumps(trail, indent=1), encoding='utf-8')
        try:
            context.metadata = dict(getattr(context, 'metadata', None) or {}, cael=dict(
                understood=trail['understood'], planned=trail['planned'], done=trail['done'], failed=trail['failed']))
        except Exception:
            pass
        return None
