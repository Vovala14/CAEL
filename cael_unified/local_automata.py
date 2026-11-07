"""Example-induced finite local transition models, without neural inference.

The inductive bias is explicit: stationary 1-D discrete updates, a bounded
neighbourhood, exact lookup consistency and aggregate/symmetry hypotheses.
Example-pair cross-validation ranks hypotheses. Query answers never enter fit.
Unseen neighbourhoods use labelled empirical guesses, never claimed proofs.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import math

MAX_RADIUS = 3
MAX_EXAMPLES = 32
MAX_WIDTH = 512
MAX_SYMBOL = 31


class OutsideDomain(ValueError):
    pass


def row(value):
    if type(value) is not list or not 1 <= len(value) <= MAX_WIDTH:
        raise OutsideDomain('Expected a nonempty discrete row of at most 512 cells')
    if any(type(v) is not int or not 0 <= v <= MAX_SYMBOL for v in value):
        raise OutsideDomain('Cells must be integer symbols from 0 through 31')
    return tuple(value)


def neighbourhood(source, position, radius, boundary):
    if boundary == 'wrap':
        return tuple(source[(position+d) % len(source)] for d in range(-radius, radius+1))
    if boundary == 'zero':
        return tuple(source[position+d] if 0 <= position+d < len(source) else 0
                     for d in range(-radius, radius+1))
    raise OutsideDomain('Boundary must be wrap or zero')


def signature(window, radius, kind):
    if kind == 'left': return (window[0],)
    if kind == 'right': return (window[-1],)
    if kind == 'ordered': return window
    if kind == 'multiset': return tuple(sorted(window))
    if kind == 'sum': return (sum(window),)
    outside = window[:radius] + window[radius+1:]
    if kind == 'center_sum': return window[radius], sum(outside)
    if kind == 'center_multiset': return window[radius], tuple(sorted(outside))
    if kind == 'outer_sum': return (sum(outside),)
    raise OutsideDomain('Unknown feature family')


@dataclass
class Hypothesis:
    radius: int
    kind: str
    table: dict
    counts: dict
    validation_lnp: float
    validation_seen: int
    validation_cells: int
    cost: float


def fit_map(pairs, radius, kind, boundary):
    table = {}; counts = Counter()
    for source, target in pairs:
        for position, value in enumerate(target):
            key = signature(neighbourhood(source, position, radius, boundary), radius, kind)
            if key in table and table[key] != value: return None
            table[key] = value; counts[key] += 1
    return table, counts


def learn_transition(examples, query, boundary='wrap'):
    """Predict a new row from demonstration pairs, retaining coverage/ambiguity.

    All fitting is ephemeral and episode-local. This function accepts only
    demonstrations and query, never a rule-table/family/label metadata object.
    """
    if type(examples) is not list or not 2 <= len(examples) <= MAX_EXAMPLES:
        raise OutsideDomain('Provide 2 to 32 independent example pairs')
    pairs = []
    for example in examples:
        if type(example) is not dict or set(example) != {'input', 'output'}:
            raise OutsideDomain('Each example needs only input and output')
        source, target = row(example['input']), row(example['output'])
        if len(source) != len(target): raise OutsideDomain('Input/output widths must match')
        pairs.append((source, target))
    query = row(query)
    if sum(len(x) for x, _ in pairs) > 16384:
        raise OutsideDomain('Demonstration cell budget reached')
    if boundary not in ('wrap', 'zero'): raise OutsideDomain('Unknown boundary')
    # Contradictory full-row evidence is invalid even if a larger neighbourhood
    # could hide a collision. Retain ambiguity instead of fitting the last row.
    seen_rows = {}
    for source, target in pairs:
        if source in seen_rows and seen_rows[source] != target:
            raise OutsideDomain('The demonstrations give conflicting outputs for the same input')
        seen_rows[source] = target
    symbols = max([*query, *(v for x, y in pairs for v in (*x, *y))]) + 1
    symbols = max(2, symbols)
    global_counts = Counter(v for _, target in pairs for v in target)
    fallback = max(range(symbols), key=lambda v: (global_counts[v], -v))
    models = []
    families = [(0, 'ordered')]
    families += [(r, kind) for r in range(1, MAX_RADIUS+1)
                 for kind in ('left', 'right', 'sum', 'outer_sum', 'center_sum', 'multiset', 'center_multiset', 'ordered')]
    for radius, kind in families:
        fitted = fit_map(pairs, radius, kind, boundary)
        if fitted is None: continue
        table, counts = fitted
        lnp = 0.0; covered = 0; total = 0
        # Hold out entire pairs, not individual neighbouring cells, to avoid
        # scoring an example against its own transitions.
        for excluded, (source, target) in enumerate(pairs):
            rest = pairs[:excluded] + pairs[excluded+1:]
            partial, witnesses = fit_map(rest, radius, kind, boundary)
            prior = Counter(v for _, output in rest for v in output)
            prior_total = sum(prior.values())
            for position, value in enumerate(target):
                key = signature(neighbourhood(source, position, radius, boundary), radius, kind)
                if key in partial:
                    covered += 1
                    probability = (witnesses[key] + 0.5) / (witnesses[key] + 0.5*symbols)
                else:
                    probability = (prior[value]+0.5) / (prior_total+0.5*symbols)
                lnp += math.log(probability); total += 1
        description = (2*radius+1 if kind == 'ordered' else radius+2 if 'multiset' in kind else 2)
        cost = math.log2(2+len(table)) + 0.25*description
        models.append(Hypothesis(radius, kind, table, counts, lnp, covered, total, cost))
    models.sort(key=lambda m: (-(m.validation_lnp-0.10*m.cost), m.cost, m.radius, m.kind))
    # No silent switch to an external model or query-label-derived rule. If
    # local stationarity cannot fit, emit an explicit empirical-only result.
    if not models:
        return dict(prediction=[fallback]*len(query), supported=[False]*len(query),
                    alternatives=[list(range(symbols)) for _ in query],
                    status='empirical-only', fitted_hypotheses=0, selected=None,
                    coverage=0.0, neural=False, persistent_learning=False)
    selected = models[0]
    prediction = []; supported = []; alternatives = []
    for position in range(len(query)):
        key = signature(neighbourhood(query, position, selected.radius, boundary), selected.radius, selected.kind)
        known = key in selected.table
        # Back off through independently consistent hypotheses when the chosen
        # compressed representation lacks a query signature.
        choices = []
        for model in models:
            signature_key = signature(neighbourhood(query, position, model.radius, boundary), model.radius, model.kind)
            if signature_key in model.table: choices.append(model.table[signature_key])
        value = selected.table[key] if known else choices[0] if choices else fallback
        prediction.append(value); supported.append(known)
        alternatives.append(sorted(set(choices)) if choices else list(range(symbols)))
    return dict(prediction=prediction, supported=supported, alternatives=alternatives,
                status='inferred' if all(supported) else 'partially-supported',
                coverage=sum(supported)/len(query), fitted_hypotheses=len(models),
                selected=dict(radius=selected.radius, features=selected.kind,
                              observed_signatures=len(selected.table),
                              held_pair_coverage=selected.validation_seen/max(1, selected.validation_cells),
                              held_pair_log_likelihood=selected.validation_lnp),
                disagreeing_cells=sum(len(v)>1 for v in alternatives),
                neural=False, persistent_learning=False,
                guarantee='Prediction under an inferred finite local hypothesis, not a uniquely identified general rule')


def reply(text):
    prefix = 'Infer discrete transition:'
    if not isinstance(text, str) or not text.lstrip().startswith(prefix): return None
    payload = text.lstrip()[len(prefix):].strip()
    try:
        if len(payload) > 200000: raise OutsideDomain('Structured task length limit')
        task = json.loads(payload)
        if type(task) is not dict or not {'examples', 'query'} <= set(task) or set(task)-{'examples','query','boundary'}:
            raise OutsideDomain('Use examples, query, and optional boundary only')
        result = learn_transition(task['examples'], task['query'], task.get('boundary', 'wrap'))
    except (ValueError, TypeError, RecursionError) as exc:
        return dict(route='chat/automaton-clarify', response='Please clarify the transition task: '+str(exc),
                    sources=[], automaton={'status':'invalid-or-unsupported', 'neural':False})
    return dict(route='chat/automaton-induction', response=json.dumps(result['prediction']), sources=[],
                automaton=result, details='Example-induced discrete local transitions. '+result.get('guarantee',
                    'Only an empirical output-frequency guess; no supported local rule was found.'))
