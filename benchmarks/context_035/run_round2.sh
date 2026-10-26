#!/usr/bin/env bash
# Round 2: CAEL runs on every split with the round-2 parser (clean timing, nothing else on the CPU), the before/after
# ladder, and the two LLMs on the round-2 blind set.   bash run_round2.sh <python> <cael-0.3.4 checkout> <cael-0.3.5 checkout>
set -e
PY=$1; OLD=$2; NEW=$3
cd "$(dirname "$0")"
for split in dev test fresh fresh2; do
  $PY run_cael.py --root "$OLD" --split $split --tag cael-0.3.4 > /dev/null
  CAEL_CONTEXT_FEATURES=none $PY run_cael.py --root "$NEW" --split $split --tag cael-0.3.5-stage1-memory > /dev/null
  CAEL_CONTEXT_FEATURES=references $PY run_cael.py --root "$NEW" --split $split --tag cael-0.3.5-stage2-references > /dev/null
  CAEL_CONTEXT_FEATURES=references,updates $PY run_cael.py --root "$NEW" --split $split --tag cael-0.3.5-stage3-updates > /dev/null
  CAEL_CONTEXT_FEATURES=references,updates,conflicts $PY run_cael.py --root "$NEW" --split $split --tag cael-0.3.5-stage4-conflicts > /dev/null
  $PY run_cael.py --root "$NEW" --split $split --tag cael-0.3.5 > /dev/null
done
$PY run_llm.py --model Qwen/Qwen2.5-0.5B-Instruct --split fresh2 --tag qwen2.5-0.5b-instruct --threads=8 > /dev/null
$PY run_llm.py --model HuggingFaceTB/SmolLM2-360M-Instruct --split fresh2 --tag smollm2-360m-instruct --threads=8 > /dev/null
echo done
