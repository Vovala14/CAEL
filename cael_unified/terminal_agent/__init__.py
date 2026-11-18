"""CAEL's terminal agent: non-neural task solving in a shell, for Terminal-Bench style checks.

planner.py   reads the instruction (paths, quoted text, verbs) into steps, from authored recipes
agent.py     looks around, runs the steps, checks each result, and tries the next recipe on failure
local_env.py a stand-in environment (bash in a sandbox folder) for tests without Docker
harbor_agent.py the Harbor adapter: `--agent-import-path cael_unified.terminal_agent.harbor_agent:CaelAgent`

No model is involved: the instruction is parsed with patterns, commands come from recipes, and
success is judged by exit codes and by re-reading what the task asked for.
"""
