#!/usr/bin/env bash
# One run on the independent 300-question set (written by a separate evaluator after the 0.3.5 freeze, commit f8cfdb9).
#   bash run_independent.sh <python> <cael-0.3.4 checkout> <cael-0.3.5 checkout>
set -e
PY=$1; OLD=$2; NEW=$3
cd "$(dirname "$0")"
$PY run_cael.py --root "$NEW" --split independent --tag cael-0.3.5 > /dev/null
$PY run_cael.py --root "$OLD" --split independent --tag cael-0.3.4 > /dev/null
$PY run_llm.py --model Qwen/Qwen2.5-0.5B-Instruct --split independent --tag qwen2.5-0.5b-instruct --threads=8 > /dev/null
$PY run_llm.py --model Qwen/Qwen3-0.6B --split independent --tag qwen3-0.6b --threads=8 > /dev/null
$PY run_llm.py --model HuggingFaceTB/SmolLM2-360M-Instruct --split independent --tag smollm2-360m-instruct --threads=8 > /dev/null
echo done
