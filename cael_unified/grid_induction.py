"""Finite, request-local 2D program induction; no benchmark names or answers.

Every admitted program matches every demonstration exactly. Prediction remains
an inductive hypothesis, not proof that a hidden rule is uniquely determined.
"""
from collections import Counter, deque
import json


class Unsupported(ValueError):
    pass


def grid(value, limit=30, colors=10):
    if (type(value) is not list or not 1 <= len(value) <= limit
            or any(type(row) is not list or not 1 <= len(row) <= limit for row in value)
            or len({len(row) for row in value}) != 1
            or any(type(v) is not int or not 0 <= v < colors for row in value for v in row)):
        raise Unsupported('Expected a rectangular integer-color grid within the declared size and palette.')
    return tuple(tuple(row) for row in value)


def rotate(g):
    return tuple(zip(*g[::-1]))


def geometries(g):
    for flip in (False, True):
        current = tuple(row[::-1] for row in g) if flip else g
        for turns in range(4):
            yield ('reflect-horizontal+' if flip else '') + 'rotate-' + str(90*turns), current
            current = rotate(current)


def components(g, background=0):
    cells = {(y,x) for y,row in enumerate(g) for x,v in enumerate(row) if v != background}
    result=[]
    while cells:
        root=min(cells);cells.remove(root);todo=[root];found={root}
        while todo:
            y,x=todo.pop()
            for p in [(y-1,x),(y+1,x),(y,x-1),(y,x+1)]:
                if p in cells and g[p[0]][p[1]] == g[y][x]:
                    cells.remove(p);found.add(p);todo.append(p)
        result.append(found)
    return result


def crop(g, cells):
    if not cells:raise Unsupported('There is no non-background object to crop.')
    ys=[p[0] for p in cells];xs=[p[1] for p in cells]
    return tuple(tuple(row[min(xs):max(xs)+1]) for row in g[min(ys):max(ys)+1])


def preprocess(g, kind):
    if kind == 'whole':return g
    if kind == 'nonzero-bounds':
        return crop(g,[(y,x) for y,row in enumerate(g) for x,v in enumerate(row) if v != 0])
    parts=components(g)
    if not parts:raise Unsupported('No foreground component.')
    size=(max if kind == 'largest-component' else min)(len(p) for p in parts)
    selected=[p for p in parts if len(p)==size]
    if len(selected)!=1:raise Unsupported('Component size is tied.')
    chosen=selected[0];masked=tuple(tuple(v if (y,x) in chosen else 0 for x,v in enumerate(row)) for y,row in enumerate(g))
    return crop(masked,chosen)


def scale(g, factor):
    return tuple(tuple(v for v in row for _ in range(factor)) for row in g for _ in range(factor))


def solve(examples, query):
    if type(examples) is not list or not 2 <= len(examples) <= 12:
        raise Unsupported('Provide 2 to 12 complete input/output demonstrations.')
    pairs=[]
    for item in examples:
        if type(item) is not dict or set(item) != {'input','output'}:
            raise Unsupported('Every demonstration must contain only input and output.')
        pairs.append((grid(item['input']),grid(item['output'])))
    q=grid(query)
    if sum(len(a)*len(a[0])+len(b)*len(b[0]) for a,b in pairs)>12000:
        raise Unsupported('Demonstration cell budget exceeded.')
    seen={}
    for a,b in pairs:
        if a in seen and seen[a] != b:raise Unsupported('Identical demonstration inputs have conflicting outputs.')
        seen[a]=b
    candidates=[];attempts=0
    for prep in ['whole','nonzero-bounds','largest-component','smallest-component']:
        try:prepared=[preprocess(a,prep) for a,b in pairs];pq=preprocess(q,prep)
        except Unsupported:continue
        for index in range(8):
            name=next(v[0] for i,v in enumerate(geometries(pq)) if i==index)
            transformed=[next(v[1] for i,v in enumerate(geometries(a)) if i==index) for a in prepared]
            transformed_q=next(v[1] for i,v in enumerate(geometries(pq)) if i==index)
            for factor in (1,2,3):
                attempts+=1
                adjusted=[scale(g,factor) for g in transformed]
                if any(len(g)!=len(b) or len(g[0])!=len(b[0]) for g,(_,b) in zip(adjusted,pairs)):continue
                mapping={};consistent=True
                for g,(_,b) in zip(adjusted,pairs):
                    for row,target in zip(g,b):
                        for old,new in zip(row,target):
                            if old in mapping and mapping[old] != new:consistent=False;break
                            mapping[old]=new
                if not consistent:continue
                candidate_q=scale(transformed_q,factor)
                if len(candidate_q)>30 or len(candidate_q[0])>30:continue
                if any(v not in mapping for row in candidate_q for v in row):continue
                prediction=tuple(tuple(mapping[v] for v in row) for row in candidate_q)
                assert all(tuple(tuple(mapping[v] for v in row) for row in g)==b for g,(_,b) in zip(adjusted,pairs))
                changed=any(a!=b for a,b in mapping.items())
                complexity=(prep!='whole')*2+(index!=0)+(factor!=1)+changed
                candidates.append(dict(prediction=prediction,cost=complexity,
                    program=dict(select=prep,geometry=name,scale=factor,color_map=mapping)))
    if not candidates:raise Unsupported('No supported, fully checked 2D program predicts this query. The rule or unseen colors need more evidence.')
    # Compare all admitted query predictions, not merely the first convenient
    # fit. Identical demonstrations never justify an arbitrary orientation.
    predictions={x['prediction'] for x in candidates}
    if len(predictions)!=1:raise Unsupported('The demonstrations support different query grids; more distinguishing examples are needed.')
    selected=min(candidates,key=lambda x:(x['cost'],json.dumps(x['program'],sort_keys=True)))
    return dict(prediction=[list(row) for row in selected['prediction']],program=selected['program'],
                demonstrations_checked=len(pairs),consistent_hypotheses=len(candidates),searched_programs=attempts,
                status='inferred-within-finite-language',neural=False,persistent_learning=False)


def reply(task):
    try:
        if set(task) != {'examples','query'}:raise Unsupported('Use only examples and query; extra conditions cannot be silently ignored.')
        result=solve(task['examples'],task['query'])
    except (Unsupported,RecursionError) as exc:
        return dict(route='chat/grid-clarify',response='Please clarify the grid task: '+str(exc),sources=[],
                    grid_reasoning=dict(status='unsupported-or-ambiguous',neural=False))
    return dict(route='chat/grid-induction',response=json.dumps(result['prediction']),sources=[],grid_reasoning=result,
                verification=dict(status='examples-checked',check='All complete demonstrations match; prediction remains an inductive hypothesis.'))
