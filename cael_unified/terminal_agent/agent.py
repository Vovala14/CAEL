"""Run a plan in an environment: look first, then each step's tries until one works and its check passes.

The environment only needs `async exec(command, timeout_sec=None) -> result` with stdout, stderr and
return_code (Harbor's BaseEnvironment has this; local_env.LocalEnvironment imitates it).
"""
import time

from . import planner

LOOK = 'pwd; ls -la 2>/dev/null | head -50'


def _text(result):
    return ((getattr(result, 'stdout', '') or '') + (getattr(result, 'stderr', '') or ''))[-2000:]


async def solve(instruction, environment, timeout_sec=120, log=None):
    """Returns a trajectory dict: what was seen, planned, run and checked."""
    started = time.time()
    trail = dict(instruction=instruction, steps=[], looked=None, planned=0, done=0, failed=0)

    async def run(command):
        try:
            r = await environment.exec(command, timeout_sec=timeout_sec)
            return r.return_code, _text(r)
        except Exception as exc:          # a timeout or a broken environment is a failed try, not a crash
            return -1, repr(exc)[:500]

    trail['looked'] = (await run(LOOK))[1]
    steps = planner.plan(instruction, dict(listing=trail['looked']))
    trail['planned'] = len(steps)
    for st in steps:
        record = dict(why=st['why'], recipe=st['recipe'], tries=[], ok=False)
        for command in st['tries']:
            code, out = await run(command)
            entry = dict(command=command, code=code, output=out[-600:])
            if code == 0 and st.get('check'):
                ccode, cout = await run(st['check'])
                entry.update(check=st['check'], check_code=ccode)
                code = ccode
            record['tries'].append(entry)
            if code == 0:
                record['ok'] = True
                break
        trail['steps'].append(record)
        trail['done' if record['ok'] else 'failed'] += 1
        if log:
            log(record)
    trail['seconds'] = round(time.time() - started, 2)
    trail['understood'] = bool(steps)
    return trail
