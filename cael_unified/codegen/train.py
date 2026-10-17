"""Learn which operations a task description calls for (counted, non-neural).

For every training task, the reference solution is parsed (never executed) into
the set of operation tags it uses. A Bernoulli naive-Bayes count model then
estimates P(tag | description words). At synthesis time the probabilities set
each operation's search cost, so likely operations are tried first. The model
stores only counts per word and tag, not any solution text.
"""
from collections import Counter
import ast
import warnings
import json
import math
import re

from .synth import CONSTANT_POOL, HIGHER, OPS, OP_TAGS, const_token

STOP = set('a an the to of in for and or is are be by with from given write function python program find check whether that this it its as on at all using which into list string number numbers'.split())

BUILTIN_TAGS = {'len', 'sum', 'max', 'min', 'sorted', 'set', 'list', 'tuple', 'str', 'int', 'float', 'abs', 'round', 'bool', 'ord',
                'chr', 'bin', 'zip', 'range', 'any', 'all'}
METHOD_TAGS = {'upper', 'lower', 'title', 'capitalize', 'swapcase', 'strip', 'split', 'join', 'count', 'replace', 'startswith',
               'endswith', 'find', 'index', 'items', 'keys', 'values', 'isdigit', 'isalpha', 'isupper', 'islower', 'isspace',
               'sqrt', 'floor', 'ceil', 'factorial', 'gcd', 'lcm', 'pow'}
BINOPS = {ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul', ast.Div: 'div', ast.FloorDiv: 'floordiv', ast.Mod: 'mod', ast.Pow: 'pow'}
CMPOPS = {ast.Eq: 'eq', ast.NotEq: 'ne', ast.Lt: 'lt', ast.LtE: 'le', ast.Gt: 'gt', ast.GtE: 'ge', ast.In: 'in', ast.NotIn: 'in'}


def words(text):
    tokens = re.findall(r'[a-z]+', text.lower())
    out = set()
    for token in tokens:
        if token in STOP or len(token) < 3:
            continue
        for suffix in ('ies', 'es', 's', 'ing', 'ed'):
            if token.endswith(suffix) and len(token) - len(suffix) >= 3:
                token = token[:-len(suffix)] + ('y' if suffix == 'ies' else '')
                break
        out.add(token)
    return out


def tags_in_code(code):
    """Operation tags used by a solution, from its syntax tree only."""
    found = set()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', SyntaxWarning)
        tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name in BUILTIN_TAGS or name in METHOD_TAGS:
                found.add(name)
            if name == 'sorted' and any(k.arg == 'key' for k in node.keywords):
                found.add('sortkey')
            if name in ('max', 'min') and any(k.arg == 'key' for k in node.keywords):
                found.add(name + 'key')
            if name == 'reversed' or (name == 'reverse' and isinstance(func, ast.Attribute)):
                found.add('reverse')
        elif isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
            found.add(BINOPS[type(node.op)])
        elif isinstance(node, ast.Compare):
            found.update(CMPOPS[type(op)] for op in node.ops if type(op) in CMPOPS)
        elif isinstance(node, ast.BoolOp):
            found.add('and' if isinstance(node.op, ast.And) else 'or')
        elif isinstance(node, ast.UnaryOp):
            found.add('not' if isinstance(node.op, ast.Not) else 'neg' if isinstance(node.op, ast.USub) else 'unary')
        elif isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                step = node.slice.step
                found.add('reverse' if isinstance(step, ast.UnaryOp) and isinstance(step.op, ast.USub) else 'slice')
            else:
                found.add('index')
        elif isinstance(node, (ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp, ast.For)):
            found.add('comp')
            if getattr(node, 'generators', None) and any(g.ifs for g in node.generators):
                found.add('filter')
        elif isinstance(node, (ast.IfExp, ast.If)):
            found.add('cond')
            if isinstance(node, ast.If):
                found.add('filter')
    return found & set(OP_TAGS)


def fit(tasks, alpha=5.0, min_count=2):
    """tasks: iterable of (description, solution code). Returns the count model."""
    tag_count, word_count, joint = Counter(), Counter(), Counter()
    total = 0
    for description, code in tasks:
        try:
            tags = tags_in_code(code)
        except SyntaxError:
            continue
        ws = words(description)
        total += 1
        tag_count.update(tags)
        word_count.update(ws)
        joint.update((w, t) for w in ws for t in tags)
    vocabulary = sorted(w for w, n in word_count.items() if n >= min_count)
    return dict(total=total, alpha=alpha, tags={t: tag_count[t] for t in OP_TAGS}, words={w: word_count[w] for w in vocabulary},
                joint={f'{w}|{t}': n for (w, t), n in joint.items() if w in word_count and word_count[w] >= min_count})


def search_tokens():
    """Everything a self-trained model scores: operation and comprehension names,
    pool constants, description literals and loop sources (see synth.tokens_of)."""
    return ([name for name, *_ in OPS + HIGHER] + [const_token(v) for v in CONSTANT_POOL] + ['const:number', 'const:quoted'] +
            ['iter:' + k for k in ('each', 'positions', 'words', 'items', 'range', 'range1', 'digits')])


def fit_self(solutions, alpha=5.0, min_count=2):
    """Self-training: solutions are (description, tokens) of programs CAEL itself
    found for training tasks and checked on their tests. Unlike fit(), the tokens
    are exactly the search's own operations, so no mapping from human code is needed.
    A task with several solutions counts each with weight 1/k."""
    by_task = {}
    for task, description, tokens in solutions:
        by_task.setdefault(task, (description, []))[1].append(set(tokens))
    universe = search_tokens()
    tag_count, word_count, joint = Counter(), Counter(), Counter()
    for description, programs in by_task.values():
        weight = 1 / len(programs)
        ws = words(description)
        word_count.update(ws)
        for tokens in programs:
            for t in tokens & set(universe):
                tag_count[t] += weight
                for w in ws:
                    joint[(w, t)] += weight
    total = len(by_task)
    keep = {w for w, n in word_count.items() if n >= min_count}
    return dict(kind='self', total=total, alpha=alpha, tags={t: tag_count[t] for t in universe}, words={w: word_count[w] for w in sorted(keep)},
                joint={f'{w}|{t}': round(n, 4) for (w, t), n in joint.items() if w in keep})


def self_costs(model, description, scale=0.5, offset=1.0, use_words=True, low=1, high=6, word_weight=1.0):
    """Integer search costs from a self-trained model: offset + scale * bits, where
    bits = -log2 P(token used | description). use_words=False uses the prior alone,
    i.e. per-operation base costs learned from how often CAEL's solutions use them."""
    p = probabilities(model, description if use_words else '', word_weight)
    return {t: max(low, min(high, round(offset + scale * -math.log2(max(q, 1e-6))))) for t, q in p.items()}


def lift_costs(model, description, strength=1.0, word_weight=1.0):
    """Hand-set base costs shifted by how much the description raises or lowers each
    token's odds over its self-trained prior: shift = -strength * log2(P(t | words) / P(t))."""
    prior = probabilities(model, '')
    p = probabilities(model, description, word_weight)
    base = {name: rest[-1] for name, *rest in OPS + HIGHER}
    return {t: max(1, base[t] - round(strength * math.log2(max(p[t], 1e-6) / max(prior[t], 1e-6)))) for t in base}


def probabilities(model, description, word_weight=1.0):
    """P(tag used | description words), Bernoulli naive Bayes over present words.
    word_weight < 1 tempers the summed word evidence (naive Bayes over-counts
    correlated words)."""
    n, a = model['total'], model['alpha']
    ws = [w for w in words(description) if w in model['words']]
    out = {}
    for tag in model['tags'] if model.get('kind') == 'self' else OP_TAGS:
        with_tag = model['tags'].get(tag, 0)
        without = n - with_tag
        logit = math.log((with_tag + a) / (without + a))
        for w in ws:
            # m-estimates shrink toward the word's overall rate, so rare tags
            # are not driven to certainty by a single co-occurrence.
            base = model['words'][w] / n
            both = model['joint'].get(f'{w}|{tag}', 0)
            only_word = model['words'][w] - both
            logit += word_weight * (math.log((both + a * base) / (with_tag + a)) - math.log((only_word + a * base) / (without + a)))
        out[tag] = 1 / (1 + math.exp(-max(-30, min(30, logit))))
    return out


def costs(model, description, strength=1.0):
    """Integer search costs: each operation's base cost shifted by how likely its tag is."""
    if model is None:
        return {}
    p = probabilities(model, description)
    out = {}
    for name, tag, *rest in OPS + HIGHER:
        base = rest[-1]
        shift = 0
        if strength:
            q = p.get(tag, 0.0)
            shift = -2 if q > 0.6 else -1 if q > 0.3 else 0 if q > 0.08 else 1 if q > 0.02 else 2
        out[name] = max(1, base + round(shift * strength))
    return out


def ranker(model, description, weight=1.0):
    """Penalty for an expression whose operations the description makes unlikely."""
    if model is None:
        return None
    p = probabilities(model, description)

    def penalty(candidate):
        cost, _, src = candidate[:3]
        try:
            tags = tags_in_code(src)
        except SyntaxError:
            return cost
        return cost + weight * sum(-math.log(max(p.get(tag, 0.0), 0.02)) for tag in tags)
    return penalty


def save(model, path):
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(model, handle, sort_keys=True)


def load(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)
