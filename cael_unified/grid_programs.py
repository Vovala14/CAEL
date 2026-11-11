"""Compositional object/grid programs with request-local checked synthesis.

Operators are generic geometry, topology, objects and relations. No task IDs,
held-out answers, benchmark examples or neural/ranked answer store are used.
"""
from collections import Counter,deque
import json,time
from .grid_induction import grid,components,crop,rotate,scale,Unsupported


def background(g,kind):
    if kind=='modal':return Counter(v for r in g for v in r).most_common(1)[0][0]
    counts=Counter([g[0][0],g[0][-1],g[-1][0],g[-1][-1]])
    best=max(counts.values());values=[v for v,n in counts.items() if n==best]
    if len(values)!=1:raise Unsupported('Background corners are ambiguous.')
    return values[0]


def draw(g,points,color):
    rows=[list(r) for r in g]
    for y,x in points:rows[y][x]=color
    return tuple(map(tuple,rows))


def selector(g,bg,kind):
    parts=components(g,bg)
    if not parts:raise Unsupported('No foreground object.')
    score=lambda p:(len(p) if kind in ('largest','smallest') else min(x for y,x in p) if kind in ('leftmost','rightmost') else min(y for y,x in p))
    extreme=(min if kind in ('smallest','leftmost','topmost') else max)(map(score,parts))
    found=[p for p in parts if score(p)==extreme]
    if len(found)!=1:raise Unsupported('Object selector is tied.')
    return found[0]


def holes(g,bg):
    h=len(g);w=len(g[0]);blank={(y,x) for y in range(h) for x in range(w) if g[y][x]==bg}
    result=g
    while blank:
        p=min(blank);todo=[p];blank.remove(p);inside={p};boundary=set();edge=False
        while todo:
            y,x=todo.pop()
            if y in (0,h-1) or x in (0,w-1):edge=True
            for ny,nx in [(y-1,x),(y+1,x),(y,x-1),(y,x+1)]:
                if 0<=ny<h and 0<=nx<w:
                    if (ny,nx) in blank:blank.remove((ny,nx));inside.add((ny,nx));todo.append((ny,nx))
                    elif g[ny][nx]!=bg:boundary.add(g[ny][nx])
        if not edge:
            if len(boundary)!=1:raise Unsupported('An enclosed region has several boundary colors.')
            result=draw(result,inside,next(iter(boundary)))
    return result


def apply(g,operation):
    name,arg=operation;h=len(g);w=len(g[0])
    if name=='rotate':
        for _ in range(arg):g=rotate(g)
        return g
    if name=='reflect-h':return tuple(r[::-1] for r in g)
    if name=='reflect-v':return g[::-1]
    if name=='scale':return grid([list(r) for r in scale(g,arg)])
    if name=='tile-h':return grid([list(r)*arg for r in g])
    if name=='tile-v':return grid([list(r) for r in g]*arg)
    if name=='compress':
        rows=[r for i,r in enumerate(g) if i==0 or r!=g[i-1]]
        keep=[x for x in range(w) if x==0 or any(row[x]!=row[x-1] for row in rows)]
        return tuple(tuple(r[x] for x in keep) for r in rows)
    bg=background(g,arg)
    if name=='crop':return crop(g,[(y,x) for y,r in enumerate(g) for x,v in enumerate(r) if v!=bg])
    if name.startswith('select-'):
        selected=selector(g,bg,name[7:]);color=g[min(selected)[0]][min(selected)[1]]
        return crop(draw(tuple(tuple(bg for _ in range(w)) for _ in range(h)),selected,color),selected)
    if name=='fill-holes':return holes(g,bg)
    if name in ('fill-boxes','outline-boxes'):
        result=g
        for part in components(g,bg):
            y0=min(y for y,x in part);y1=max(y for y,x in part);x0=min(x for y,x in part);x1=max(x for y,x in part);c=g[y0][next(x for y,x in part if y==y0)]
            coords={(y,x) for y in range(y0,y1+1) for x in range(x0,x1+1) if name=='fill-boxes' or y in (y0,y1) or x in (x0,x1)}
            if any(g[y][x] not in (bg,c) for y,x in coords):raise Unsupported('Object boxes overlap different colors.')
            result=draw(result,coords,c)
        return result
    if name in ('connect-h','connect-v'):
        result=[list(r) for r in g]
        lines=g if name=='connect-h' else tuple(zip(*g))
        for j,line in enumerate(lines):
            colors={v for v in line if v!=bg}
            for c in colors:
                positions=[i for i,v in enumerate(line) if v==c]
                for a,b in zip(positions,positions[1:]):
                    if all(v==bg for v in line[a+1:b]):
                        for k in range(a+1,b):
                            y,x=(j,k) if name=='connect-h' else (k,j);result[y][x]=c
        return tuple(map(tuple,result))
    if name.startswith('settle-'):
        direction=name[7:];vertical=direction in ('north','south');lines=tuple(zip(*g)) if vertical else g;out=[]
        for row in lines:
            filled=[v for v in row if v!=bg];empty=[bg]*(len(row)-len(filled))
            out.append(tuple((empty+filled) if direction in ('south','east') else (filled+empty)))
        return tuple(zip(*out)) if vertical else tuple(out)
    if name in ('complete-h','complete-v'):
        other=tuple(r[::-1] for r in g) if name=='complete-h' else g[::-1]
        if any(a!=bg and b!=bg and a!=b for r,s in zip(g,other) for a,b in zip(r,s)):raise Unsupported('Mirror overlay has conflicting colors.')
        return tuple(tuple(b if a==bg else a for a,b in zip(r,s)) for r,s in zip(g,other))
    if name in ('pack-ascending','pack-descending'):
        parts=components(g,bg);sizes=[len(p) for p in parts]
        if len(set(sizes))!=len(sizes) or not parts:raise Unsupported('Object size ordering is ambiguous.')
        ordered=sorted(parts,key=len,reverse=name=='pack-descending')
        images=[crop(tuple(tuple(v if (y,x) in p else bg for x,v in enumerate(row)) for y,row in enumerate(g)),p) for p in ordered]
        height=max(map(len,images));width=sum(len(im[0]) for im in images)
        if height>30 or width>30:raise Unsupported('Packed grid too large.')
        out=[[bg]*width for _ in range(height)];offset=0
        for im in images:
            for y,row in enumerate(im):out[y][offset:offset+len(row)]=row
            offset+=len(im[0])
        return tuple(map(tuple,out))
    if name=='object-count':
        parts=components(g,bg)
        if not 1<=len(parts)<=30:raise Unsupported('Object count is outside output dimensions.')
        counts=Counter(g[y][x] for p in parts for y,x in p);m=max(counts.values());colors=[c for c,n in counts.items() if n==m]
        if len(colors)!=1:raise Unsupported('Counting marker color is ambiguous.')
        return (tuple([colors[0]]*len(parts)),)
    raise Unsupported('Unknown grid primitive.')


def grammar():
    ops=[('rotate',i) for i in (1,2,3)]+[('reflect-h',None),('reflect-v',None),('scale',2),('scale',3),('tile-h',2),('tile-v',2),('compress',None)]
    for bg in ('corners','modal'):
        ops += [(name,bg) for name in ['crop','select-largest','select-smallest','select-leftmost','select-rightmost','select-topmost','select-bottommost',
            'fill-holes','fill-boxes','outline-boxes','connect-h','connect-v','settle-north','settle-south','settle-east','settle-west',
            'complete-h','complete-v','pack-ascending','pack-descending','object-count']]
    return ops


def recolor(inputs,targets,query):
    if any((len(a),len(a[0]))!=(len(b),len(b[0])) for a,b in zip(inputs,targets)):return None
    mapping={}
    for a,b in zip(inputs,targets):
        for r,s in zip(a,b):
            for old,new in zip(r,s):
                if old in mapping and mapping[old]!=new:return None
                mapping[old]=new
    identity=all(a==b for a,b in mapping.items())
    if not identity and any(v not in mapping for row in query for v in row):return None
    result=tuple(tuple(mapping.get(v,v) for v in row) for row in query)
    return result,dict(kind='identity' if identity else 'demonstration-color-map',mapping=mapping),int(not identity)


def solve(examples,query,max_states=4200,max_depth=3,seconds=3.0):
    if type(examples) is not list or not 2<=len(examples)<=12:raise Unsupported('Supply 2 to 12 complete demonstrations.')
    pairs=[]
    for item in examples:
        if type(item) is not dict or set(item)!={'input','output'}:raise Unsupported('Each demonstration needs exactly input/output.')
        pairs.append((grid(item['input']),grid(item['output'])))
    q=grid(query);inputs=tuple(a for a,b in pairs);outputs=tuple(b for a,b in pairs)
    if sum(len(g)*len(g[0]) for g in inputs+outputs)>12000:raise Unsupported('Demonstration cell budget exceeded.')
    known={}
    for a,b in pairs:
        if a in known and known[a]!=b:raise Unsupported('Identical inputs have conflicting outputs.')
        known[a]=b
    # Degenerate examples can leave orientation completely unidentified even
    # when identity is cheapest. Preserve that explicit uncertainty.
    initial_match=recolor(inputs,outputs,q)
    if initial_match:
        for op in [('rotate',1),('rotate',2),('rotate',3),('reflect-h',None),('reflect-v',None)]:
            transformed=tuple(apply(a,op) for a in inputs)
            alternative=recolor(transformed,outputs,apply(q,op))
            if alternative and alternative[0]!=initial_match[0]:raise Unsupported('The examples do not distinguish orientation on this query.')
    todo=deque([(inputs+(q,),[])]);seen={inputs+(q,)};fits=[];best_cost=None;tested=0;started=time.monotonic();limited=False
    ops=grammar()
    while todo:
        if tested>=max_states or time.monotonic()-started>seconds:limited=True;break
        values,program=todo.popleft();depth=len(program)
        if best_cost is not None and depth>best_cost:continue
        tested+=1;match=recolor(values[:-1],outputs,values[-1])
        if match:
            prediction,mapper,extra=match;cost=depth+extra
            if best_cost is None or cost<best_cost:best_cost=cost;fits=[]
            if cost==best_cost:fits.append(dict(prediction=prediction,operations=program,mapper=mapper,cost=cost))
        if depth>=max_depth or best_cost is not None and depth>=best_cost:continue
        for op in ops:
            try:new=tuple(grid([list(row) for row in apply(g,op)]) for g in values)
            except (Unsupported,IndexError,ValueError):continue
            if new not in seen:
                if len(seen)<max_states*3:seen.add(new);todo.append((new,program+[op]))
                else:limited=True
    if not fits:raise Unsupported('No checked compositional program found within the finite search budget.')
    predictions={f['prediction'] for f in fits}
    if len(predictions)!=1:raise Unsupported('Equally simple checked programs disagree on the query; distinguishing evidence is needed.')
    selected=min(fits,key=lambda f:json.dumps(f['operations'],sort_keys=True))
    # Independently replay the entire chosen program on every demonstration.
    for a,b in pairs:
        value=a
        for op in selected['operations']:value=apply(value,op)
        mapping=selected['mapper']['mapping'];value=tuple(tuple(mapping.get(v,v) for v in row) for row in value)
        assert value==b
    return dict(prediction=[list(row) for row in selected['prediction']],program=dict(operations=selected['operations'],mapper=selected['mapper']),
        demonstrations_checked=len(pairs),matching_minimum_cost_hypotheses=len(fits),searched_states=tested,
        candidate_states=len(seen),search_limited=limited,search_seconds=time.monotonic()-started,
        status='checked-inductive-hypothesis',assumptions='Minimum-description-length prior within the searched finite operator language; demonstration fit is not proof of hidden intent.',neural=False)


def reply(task):
    try:
        if type(task) is not dict or set(task)!={'examples','query'}:raise Unsupported('Use only complete examples and query.')
        from . import stream_grid,local_automata
        try:
            result=stream_grid.solve(task)
            return dict(route='chat/grid-induction',response=json.dumps(result['prediction']),sources=[],grid_reasoning=result,
                verification=dict(status='all-demonstrations-replayed',check=result['assumptions']))
        except local_automata.LatticeAmbiguous as exc:
            return dict(route='chat/grid-clarify',response='Please clarify the grid task: '+str(exc),sources=[],
                grid_reasoning=dict(engine='native-integer-stream',status='ambiguous',neural=False))
        except local_automata.OutsideDomain as exc:
            native_limit=str(exc)
        result=solve(task['examples'],task['query'])
        result.update(engine='legacy-compositional-grid',native_stream_unsupported=native_limit)
    except (Unsupported,KeyError,TypeError,RecursionError,OverflowError) as exc:
        return dict(route='chat/grid-clarify',response='Please clarify the grid task: '+str(exc),sources=[],
            grid_reasoning=dict(status='unsupported-or-ambiguous',neural=False,engine='legacy-compositional-grid',native_stream_unsupported=locals().get('native_limit')))
    return dict(route='chat/grid-induction',response=json.dumps(result['prediction']),sources=[],grid_reasoning=result,
        verification=dict(status='all-demonstrations-replayed',check=result['assumptions']))
