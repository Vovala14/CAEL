"""A stand-in for a Terminal-Bench container: bash in one sandbox folder, for local tests without Docker.

This is not isolation. Use it only for CAEL's own test tasks in a temporary folder.
"""
import asyncio
import os
import subprocess
from dataclasses import dataclass


@dataclass
class Result:
    stdout: str
    stderr: str
    return_code: int


class LocalEnvironment:
    def __init__(self, root, bash='bash'):
        self.root = str(root)
        self.bash = bash

    def _run(self, command, timeout_sec):
        try:
            p = subprocess.run([self.bash, '-c', command], cwd=self.root, capture_output=True, text=True,
                               timeout=timeout_sec or 120, env=dict(os.environ, HOME=self.root))
            return Result(p.stdout, p.stderr, p.returncode)
        except subprocess.TimeoutExpired as exc:
            return Result(exc.stdout or '', 'timeout', 124)

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        return await asyncio.to_thread(self._run, command if not cwd else f'cd {cwd} && {command}', timeout_sec)
