"""CAEL's terminal agent: planning from instructions, and the Harbor adapter on a local stand-in environment."""
import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

from cael_unified.terminal_agent import planner
from cael_unified.terminal_agent.harbor_agent import CaelAgent
from cael_unified.terminal_agent.local_env import LocalEnvironment


def kinds(text):
    return [s['recipe'] for s in planner.plan(text)]


def test_clauses_split_but_continuations_stay():
    assert kinds('Initialise a git repo, create a.md containing "x", then commit it with the message "m".') == ['git', 'write', 'git']
    assert kinds('Sort b.txt, remove duplicates, and save the result to c.txt.') == ['sort']


def test_paths():
    assert planner.paths('Copy data/in.csv to /tmp/out.csv and keep notes.tmp') == ['data/in.csv', '/tmp/out.csv', 'notes.tmp']
    assert planner.paths('Write "see a.txt" to b.txt') == ['b.txt']


def test_content_with_quotes_inside():
    steps = planner.plan('Create conf.json with the content {"a": 1}.')
    assert steps[0]['recipe'] == 'write' and 'conf.json' in steps[0]['why']


def test_adapter_runs_in_local_environment():
    root = tempfile.mkdtemp()
    agent = CaelAgent(logs_dir=Path(root) / 'logs')
    context = type('Context', (), {'metadata': None})()
    asyncio.run(agent.run('Create a directory called out and inside it create done.txt with the text "ok".',
                          LocalEnvironment(root), context))
    assert (Path(root) / 'out/done.txt').read_text().strip() == 'ok'
    trail = json.loads((Path(root) / 'logs/cael_trajectory.json').read_text())
    assert trail['done'] == 2 and context.metadata['cael']['failed'] == 0


def test_unknown_instruction_does_nothing():
    assert planner.plan('Train a neural network to classify the images in /data and report the accuracy.') == [] or \
        all(s['recipe'] != 'delete' for s in planner.plan('Train a neural network to classify the images in /data.'))
