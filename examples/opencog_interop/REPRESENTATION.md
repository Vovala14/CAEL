# Representation and sensory investigation

Examined exact upstream sources:

- [AtomSpace README](https://github.com/opencog/atomspace/blob/c8d633bf272b838c2132c21b7c8ddf169a18dd22/README.md), especially Atoms/Values, Frames and installation.
- [Canonical graph-edge example](https://github.com/opencog/atomspace/blob/c8d633bf272b838c2132c21b7c8ddf169a18dd22/examples/python/graph_edges.py) and [low-level Python API](https://github.com/opencog/atomspace/blob/c8d633bf272b838c2132c21b7c8ddf169a18dd22/examples/python/create_atoms_lowlevel.py).
- [Sensory architecture](https://github.com/opencog/sensory/blob/fd367dc330b7ab82607a8622569adb609ad91a4a/Architecture.md), [example overview](https://github.com/opencog/sensory/blob/fd367dc330b7ab82607a8622569adb609ad91a4a/examples/README.md) and [file-reading example](https://github.com/opencog/sensory/blob/fd367dc330b7ab82607a8622569adb609ad91a4a/examples/file-read.scm).

## Concrete storage decision

| Option | Appropriate role | Tradeoff for this bridge |
| --- | --- | --- |
| Immutable indexed Atoms with `EdgeLink(PredicateNode, ListLink(...))` | Reported relationships that must be searched and retain source/snapshot identity | More graph/index objects, but explicit historical queries and evidence links; selected default |
| Mutable typed Values on an Atom/key | Fast-changing vectors or a latest-state view | Small mutable payloads; overwriting alone loses historical provenance, and payloads are not the same indexed relational query structure |
| AtomSpace Frames/change sets | Branching histories and graph revisions | Could share history structurally, but requires a separate frame/lifecycle design; not implemented or performance-tested here |

The original exporter used `EvaluationLink` for all data. The upstream graph
example recommends `EdgeLink` for ordinary edges; the current default follows
that representation. The original style remains an explicit comparison/import
option. The real runner records whether the two names identify different
native types or aliases; it does not claim a performance difference if they are
aliases. The same semantic payload is used for both encodings.

Every reported state tuple keeps `(input-hash episode, step, entity, value)`.
Positive and negative logical claims are explicit polarity data, not asserted
probabilities. Unknown is neither false nor a fabricated negative relation.
Evidence relations point to a fully scoped fact and its original input index.
The implementation does not infer confidence values or implicitly mutate an
old snapshot when a later event arrives.

The real validation checks structural read-back and idempotent insertion, then
executes fixed authored `MeetLink` queries over these stored tuples. Those
queries retrieve CAEL reports; they do not establish that OpenCog derives the
underlying reasoning answers. Five fresh-space insertion/query repetitions at
32/64/128 synthetic events provide bounded diagnostic timings and unique atom
counts. These are same-host integration measurements, not model speed rankings
or a proof that this representation is optimal for other workloads.

## What the sensory examples contribute

The file-read example models a file as a device, with explicit open/read
messages and a declared output type. `*-read-*` requests one value, while a
stream operation advances a sequence. Its architecture describes sensors,
motors, message types and connectors rather than treating arbitrary text as
executable instructions.

For CAEL, that suggests a boundary of **literal input record -> schema/size
validation -> request-local CAEL evaluation -> reported graph**, with source
IDs retained at the transition. A future text-file/stream adapter could feed
that boundary. It must not execute the received text as Scheme or grant the
graph input access to file, network or executable Atom types. The existing
allowlisted loader remains data-only.

Sensory is not necessary for this in-process graph exchange. Its source and
examples were examined; the new CI job does not install Sensory and does not
claim a Sensory adapter, file-device execution, IRC connection or Ollama use.
No neural runtime is added to CAEL. That scope keeps the first interoperability
test focused on a reproducible real AtomSpace build and its data/query API.

## Reproduce the real check

On an isolated Ubuntu Linux environment with C++/CMake, Guile 3, Python 3
development headers and Cython installed, and installation privileges for the
upstream installer (which writes a loader configuration under `/etc`):

```sh
bash examples/opencog_interop/build_atomspace.sh /new/build/directory
export PYTHONPATH=/new/build/directory/install/lib/python-site
export LD_LIBRARY_PATH=/new/build/directory/install/lib/opencog:/new/build/directory/install/lib
export CAEL040_ROOT=/path/to/exact/released/CAEL-0.4.0
/usr/bin/python3 examples/opencog_interop/validate_atomspace.py --output /new/results/directory --upstream-root /new/build/directory
```

`UPSTREAM_PINS.json` fixes dependency and release revisions. The runner fails
when bindings are absent, a unit test is skipped, a native query disagrees or a
round-trip changes the stored data. Its receipt includes the actual extension
hash, source/model identity, all check outcomes and timing samples. The GitHub
workflow archives receipts, complete fixture outputs and build logs even on
failure. Absence of a receipt or a failed build is not integration success.
