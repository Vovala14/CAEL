"""Finite-domain constraint propagation with exhaustive bounded witnesses.

Only explicit trusted predicates are called. No generated code, neural model,
training answers or benchmark-dependent rule selection.
"""
from itertools import product


class SearchLimit(ValueError):
    pass


def enumerate_orders(names, constraints, holds, max_nodes=250000, max_checks=3000000,
                     max_solutions=50000):
    names = tuple(names)
    if not 2 <= len(names) <= 12 or len(set(names)) != len(names):
        raise ValueError('Use 2 to 12 distinct items')
    scopes = [tuple(dict.fromkeys(c[1:2] + (() if c[0].removeprefix('not_') == 'at' else c[2:])))
              for c in constraints]
    if any(any(n not in names for n in scope) for scope in scopes):
        raise ValueError('A constraint references an unlisted item')
    stats = dict(nodes=0, predicate_checks=0, propagations=0, complete=False)
    solutions = []

    def propagate(domains):
        while True:
            before = tuple(tuple(sorted(domains[n])) for n in names)
            singles = [next(iter(v)) for v in domains.values() if len(v) == 1]
            if len(singles) != len(set(singles)):
                return False
            used = set(singles)
            for name, values in domains.items():
                if len(values) > 1: values.difference_update(used)
                if not values: return False
            # Hall's union necessary condition, alongside singleton all-different.
            if len(set().union(*domains.values())) < len(names): return False
            for constraint, scope in zip(constraints, scopes):
                supported = {name: set() for name in scope}
                for values in product(*(sorted(domains[n]) for n in scope)):
                    stats['predicate_checks'] += 1
                    if stats['predicate_checks'] > max_checks:
                        raise SearchLimit('Constraint propagation work budget reached')
                    if len(values) != len(set(values)): continue
                    if holds(constraint, dict(zip(scope, values))):
                        for name, value in zip(scope, values): supported[name].add(value)
                for name in scope:
                    domains[name].intersection_update(supported[name])
                    if not domains[name]: return False
            stats['propagations'] += 1
            if before == tuple(tuple(sorted(domains[n])) for n in names): return True

    def visit(domains):
        stats['nodes'] += 1
        if stats['nodes'] > max_nodes: raise SearchLimit('Ordering search node budget reached')
        if not propagate(domains): return
        pending = [n for n in names if len(domains[n]) > 1]
        if not pending:
            positions = {n: next(iter(domains[n])) for n in names}
            order = tuple(sorted(names, key=positions.get))
            solutions.append(order)
            if len(solutions) > max_solutions:
                raise SearchLimit('Too many valid orders for complete enumeration')
            return
        name = min(pending, key=lambda n: (len(domains[n]), names.index(n)))
        for value in sorted(domains[name]):
            child = {n: set(v) for n, v in domains.items()}
            child[name] = {value}
            visit(child)

    visit({name: set(range(len(names))) for name in names})
    # Preserve the old public ordering of witnesses, independent of MRV order.
    rank = {name: i for i, name in enumerate(names)}
    solutions.sort(key=lambda row: tuple(rank[n] for n in row))
    stats['complete'] = True
    stats['solutions'] = len(solutions)
    return tuple(solutions), stats
