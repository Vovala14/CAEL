# CellARC attribution and licence discrepancy

Dataset author: Miroslav Lzicar (Miroslav Lžičař).

Source: https://huggingface.co/datasets/mireklzicar/cellarc_100k at revision 76040e6aef0edc4982e53c13a85ef227378ed171.

The dataset card's metadata says MIT, but the actual pinned `LICENSE` file says Creative Commons Attribution 4.0 International (CC BY 4.0). The original file is retained at `upstream/LICENSE`; use its attribution requirements here rather than silently relying on the card's tag. CC BY 4.0 permits commercial use with attribution. The pre-inference sealed protocol's MIT description is retained as historical evidence and corrected by this note; no data, model, predictions or score changed.

Licence link: https://creativecommons.org/licenses/by/4.0/

Changes: original test JSONL files are byte-preserved. `inputs.jsonl` maps the five demonstration pairs to `examples` and copies the query, with no solutions or metadata. `gold.jsonl` retains only episode IDs, split names and solution arrays for separate scoring. Prediction, grade and summary files are evaluation additions, not the author's results or endorsement.

Official code/documentation: https://github.com/mireklzicar/cellarc at 2a317a6f78025f67d0666e0ce7ad10436a18a807, Apache-2.0, original licence retained in `upstream/github/LICENSE`. The candidate solver is independently authored, not copied from CellARC's symbolic baselines. Upstream generation/neural code was inspected for protocol only and is not part of CAEL runtime.

No benchmark training or validation examples were fitted. Public TRAIN preview rows were visible while reading the dataset card. All actual fitting during test inference uses only each episode's five supplied demonstration pairs; no persistent cross-episode learning occurs.
