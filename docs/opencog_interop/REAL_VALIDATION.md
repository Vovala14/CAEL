# Real AtomSpace integration validation

The optional CAEL 0.4 data bridge was built and checked against actual pinned
AtomSpace C++/Python bindings on Ubuntu 24.04. The successful [Linux run](https://github.com/Vovala14/CAEL/actions/runs/42692943714)
tested source commit `ee2a58ba8a983f3e0f6f23418057a486fd21bcf1` on 2026-11-09 UTC. This document reports that
execution; it does not turn the bridge into a CAEL reasoning or chat upgrade.

## Results

- All **16 bridge unit tests pass with zero skips**, including the real import test.
- All **18 graph round-trips** (nine original episodes, each encoded with
  `EdgeLink` and `EvaluationLink`) reproduce their complete structures and exact
  unique-atom counts. Repeated import is idempotent for both representations.
- Fixed native `MeetLink` queries retrieve first/latest snapshots in a shared
  AtomSpace, keep two inputs with the same human label separate, and return no
  invented state for a missing snapshot. Explicit positive/negative claims both
  survive; a missing claim remains unknown. Executable input is rejected before
  mutation of the shared space.
- All **96 runner assertions pass**, including 30 diagnostic query checks.
  These overlap the integration checks; they are not 96 capability cases.
- The actual compiled `atomspace.so` SHA256 is
  `7883858a21872e970c5d399c8c7b2aa830e0440426c18caf1312b435e4a6d06c`. A test double cannot satisfy the real-run gate.
- Original CAEL behavior is retained: **15/17 intended answers across nine
  authored episodes**, with two parser failures in the `rule-chain` episode.
  `Nika is glimmering` plus the declared glimmering -> amber -> visible chain
  still yields `unknown` for both visibility queries instead of the intended
  `true`/`false`. The bridge preserves the reported answers; it does not fix them.

The [unaltered native receipt](REAL_VALIDATION_RECEIPT.json) records every
assertion, model/source hash, graph count and individual timing sample. The
[unit-test log](REAL_VALIDATION_UNIT_TESTS.log) includes the real binding test.
The successful run's `real-atomspace-evidence` artifact contains the nine
original episodes' full inputs/outputs/graphs, the shared-scope fixtures,
build logs and dependency licences; the receipt hashes all
39 generated evidence files. Receipt SHA256:
`1886c3f6d1385f96c3e9351d9230fb845c660331cd37aa53290f8311a4483db4`.

## Representation decision and measured diagnostics

The pinned upstream [graph-edge example](https://github.com/opencog/atomspace/blob/c8d633bf272b838c2132c21b7c8ddf169a18dd22/examples/python/graph_edges.py)
uses `EdgeLink(PredicateNode, ListLink(...))` for ordinary data relations. The
bridge now defaults to that form and retains the original `EvaluationLink`
encoding as an explicit comparison. These are distinct native types in this
build, and both retain the same payload and atom counts. Immutable scoped
Atoms fit queryable historical snapshots; mutable Values would fit a latest
view but need a history policy, and Frames need a separate lifecycle design.
The [source investigation](../../examples/opencog_interop/REPRESENTATION.md)
records those choices and limits.

Same synthetic payload, one entity, 32/64/128 event histories; five fresh
AtomSpaces per row. Timings below are medians in milliseconds.

| Events | Representation | Root relations | Unique atoms before query | Insert ms | Query ms |
| --- | --- | --- | --- | --- | --- |
| 32 | EdgeLink | 193 | 431 | 3.836 | 1.171 |
| 32 | EvaluationLink | 193 | 431 | 3.894 | 1.164 |
| 64 | EdgeLink | 385 | 847 | 7.624 | 1.352 |
| 64 | EvaluationLink | 385 | 847 | 7.723 | 1.477 |
| 128 | EdgeLink | 769 | 1679 | 15.335 | 1.632 |
| 128 | EvaluationLink | 769 | 1679 | 15.417 | 1.605 |

Insertion includes Python validation and native insertion. Query includes
construction/execution of one fixed native pattern and reading its result.
These tiny, sequential, same-runner diagnostics do not establish a general
performance winner. There is no consistent query-speed advantage, no measured
RAM saving, no optimized representation search and no model benchmark here.
Native queries retrieve stored CAEL reports; they do not test OpenCog inference.

## Sensory investigation

The pinned [Sensory architecture](https://github.com/opencog/sensory/blob/fd367dc330b7ab82607a8622569adb609ad91a4a/Architecture.md)
and [file-reading example](https://github.com/opencog/sensory/blob/fd367dc330b7ab82607a8622569adb609ad91a4a/examples/file-read.scm)
were examined: devices declare typed open/read/stream messages. The relevant
CAEL boundary is literal record -> schema/size validation -> request-local
evaluation -> reported graph with provenance. **Sensory was not built or
integrated**, and no file-device, IRC or Ollama execution is claimed. No
untrusted text is evaluated as Scheme or accepted as executable Atom types.

## Exact reproduction and retained failed attempt

The [workflow](../../.github/workflows/atomspace.yml),
[build script](../../examples/opencog_interop/build_atomspace.sh) and
[real validator](../../examples/opencog_interop/validate_atomspace.py) are
versioned with the bridge. Check out validated commit `ee2a58ba8a983f3e0f6f23418057a486fd21bcf1` and use the
workflow's Ubuntu dependencies, environment variables and exact commands, or
the isolated-Linux commands in the representation document. Pins:

- AtomSpace: `c8d633bf272b838c2132c21b7c8ddf169a18dd22`
- CogUtil: `776aaf9c4987259545beacf633d097181c79bc83`
- Examined Sensory: `fd367dc330b7ab82607a8622569adb609ad91a4a`
- Released CAEL: `49359eae9aa197d5b92631c16efb74085180a27c`
- Released reasoning model SHA256: `a7f52da1f5afc6776af91d451a7273a269593642cd5f6d8a2883c4e34fab0bd4`

The [first real build](https://github.com/Vovala14/CAEL/actions/runs/42692623418) failed during CogUtil installation because
its installer writes a loader configuration under `/etc` even with a custom
prefix. It did not reach bridge validation. The follow-up uses installation
privileges and `ldconfig` only inside the disposable runner; the failed log
and artifact remain available. No source pins, original fixtures, intended
answers or acceptance criteria were changed to obtain the passing result.

CAEL stays an optional external dependency under its existing non-commercial
personal/research licence. Upstream licences are retained, and compatibility
or upstream acceptance is not asserted. No weights, protected solvers, live
worker, release version or HF publication changed. Historical CI notes about
the unavailable local binding remain accurate for those earlier runs; this
receipt supplies the later native validation.
