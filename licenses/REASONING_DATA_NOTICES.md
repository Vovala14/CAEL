# Reasoning training and evaluation sources

All new data used in this update permits commercial use without a licence fee.

## PrOntoQA / PrOntoQA-OOD

Copyright Abulhair Saparov and contributors. Licensed under Apache License 2.0.
The full upstream licence is retained in `LICENSE-PrOntoQA-Apache-2.0.txt`.

Source: https://github.com/asaparov/prontoqa
Licence: https://github.com/asaparov/prontoqa/blob/main/LICENSE

Public text was converted into grammatical-category counts and context hashes.
No neural model or upstream experiment runner was used. The local proof
automaton and surface parser are CAEL implementations, not copies of upstream
model code. These transformations are modifications by CAEL.

Cite: Abulhair Saparov and He He, *Language Models Are Greedy Reasoners: A
Systematic Formal Analysis of Chain-of-Thought*, ICLR 2023; and Saparov et al.,
*Testing the General Deductive Reasoning Capacity of Large Language Models
Using OOD Examples*, NeurIPS 2023.

## Facebook / Meta bAbI question-answering tasks

Credit Jason Weston, Antoine Bordes, Sumit Chopra, Tomas Mikolov, Alexander M.
Rush and the Facebook/Meta bAbI contributors. Data licensed under Creative
Commons Attribution 3.0 Unported. Commercial reuse is permitted with
attribution and the licence link:
https://creativecommons.org/licenses/by/3.0/

Publisher licence statement:
https://huggingface.co/datasets/facebook/babi_qa/blob/main/README.md

The public archive was retrieved from the mirror referenced by the official
Keras example, after the original Facebook download returned HTTP 403:
https://github.com/keras-team/keras/blob/2.2.4/examples/babi_memnn.py

Archive: https://s3.amazonaws.com/text-datasets/babi_tasks_1-20_v1-2.tar.gz

Source text was converted into event-word counts, irregular noun mappings and
task statistics by CAEL. The runtime model stores these counts rather than
copies of the benchmark stories. The source text is synthetic and describes
hypothetical worlds; it is not a source of real-world facts.

Cite: Weston et al., *Towards AI-Complete Question Answering: A Set of
Prerequisite Toy Tasks*, 2015.

## BIG-bench logical deduction — evaluation only

Copyright BIG-bench contributors; Apache License 2.0 as supplied in the
repository. Authors of the logical-deduction task: James Simon and Chandan
Singh. Full upstream licence retained in `LICENSE-BIG-bench-Apache-2.0.txt`.

https://github.com/google/BIG-bench/tree/main/bigbench/benchmark_tasks/logical_deduction

Benchmark examples and answer labels were not used for training. The public
task schema and examples were inspected while implementing the authored
constraint solver, so this is not a blinded evaluation of language
understanding. The benchmark canary is retained in downloaded source files.

These data permissions do not change the existing CAEL software licence.
