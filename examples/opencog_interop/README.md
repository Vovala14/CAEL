# CAEL 0.4 to AtomSpace: optional research prototype

This standalone example exports CAEL's reported symbolic states and reasoning
evidence as a data-only Atomese graph. It is an interoperability proposal, not
an OpenCog plugin, endorsed integration or chatbot/benchmark improvement.

CAEL 0.4.0 is an **external non-commercial dependency**, under the repository's
[CAEL license](https://github.com/Vovala14/CAEL/blob/v0.4.0/LICENSE). No CAEL engine
or weights are copied into OpenCog, and no OpenCog code is bundled here. This
example does not change either project's license. The maintainer proposal must
disclose these terms; optional integration does not imply upstream acceptance.

## Reproduce with released CAEL

Use Python 3.10+ and a local checkout of released CAEL at tag `v0.4.0`, commit
`49359eae9aa197d5b92631c16efb74085180a27c`. Its declared reasoning model resource
must be present at `models/cael-reasoning-v1/model.json`. Use CAEL's existing
installation/resource instructions; this example makes no network calls or
automatic downloads. Pass the checkout explicitly, not a model answer service.

From this example directory:

```sh
python run_demo.py --cael-root /path/to/CAEL-0.4.0 --output ./demo-output
CAEL040_ROOT=/path/to/CAEL-0.4.0 python -m unittest -v test_bridge
```

PowerShell test environment:

```powershell
$env:CAEL040_ROOT = 'C:/path/to/CAEL-0.4.0'
python -m unittest -v test_bridge
```

The output directory must be new. Each episode produces its full input, engine
output, graph JSON and readable `.scm` data, plus a receipt binding the exact
CAEL reasoning source/model hashes. These authored fixtures are CC0 input text;
the bridge code retains this repository's license.

## What the data means

- Every world-state claim includes an input-hash episode scope and snapshot
  number. Repeated human-readable episode names do not mix their states.
- Possible locations remain alternatives. They are not asserted as several
  simultaneous definite locations. Explicit exclusions are separate.
- Holder state and original source indices travel with each snapshot. Rejected
  transactions are recorded and do not commit partial world changes.
- Logical positive/negative facts, unknown, unsupported and conflicting answers
  remain distinct. Missing evidence never becomes a negative fact.
- The graph describes **what CAEL reports under supplied premises**. It does not
  assert externally verified truth or invent numeric confidence.

Only `ConceptNode`, `PredicateNode`, `NumberNode`, `ListLink` and
`EvaluationLink` are accepted by the loader. It validates the whole data graph
before calling the low-level `AtomSpace.add_node/add_link` API. There is no
`eval`, `load-file`, generated function execution or automatic Atomese inference.
Exported `.scm` strings are escaped literal data; input text cannot choose an
executable atom type. Use a fresh AtomSpace for experiments.

## Actual OpenCog check remains outstanding

The low-level binding API was checked against the upstream example at AtomSpace
commit `c8d633bf272b838c2132c21b7c8ddf169a18dd22`:
[create_atoms_lowlevel.py](https://github.com/opencog/atomspace/blob/c8d633bf272b838c2132c21b7c8ddf169a18dd22/examples/python/create_atoms_lowlevel.py).

Local tests cover CAEL execution, graph semantics/validation and an explicitly
labeled API test double. **Real AtomSpace bindings were unavailable on the
development machine, so the real integration test is skipped.** A test double
does not verify ABI/API compatibility or OpenCog reasoning. With real bindings:

```sh
python run_demo.py --cael-root /path/to/CAEL-0.4.0 --output ./atomspace-output --atomspace
```

That command constructs a new AtomSpace per episode and loads the data; it still
does not run an OpenCog reasoner or compare learning accuracy. Acceptance and
preferred graph vocabulary should be discussed with maintainers before an
upstream PR.

## Retained CAEL parsing failure

All nine examples remain visible. In `rule-chain`, the input says `Nika is
glimmering. Every glimmering thing is amber. Every amber thing is visible.`
The intended logical answers are true/false; released CAEL returns unknown for
both because its finite parser treats the modified categories differently.
Both incorrect answers are retained and flagged `known_parser_failure`; the
bridge does not repair or count them correct. A separate `bare-category-chain`
fixture demonstrates a chain that the declared parser handles. The demo receipt
reports **15/17 answers matching the authored expectations**, separately from
all nine valid export contracts. These are tiny development examples, not an
accuracy benchmark or a general language-understanding claim.

The current `opencog/learn` Version Two stream direction is experimental. This
prototype asks whether an optional external state/provenance exchange is useful
there, or belongs in AtomSpace examples instead. It adds no neural model and
does not require CAEL as a default dependency of either project.
