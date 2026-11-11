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


# Native lattice-stream extension. The original 1-D functions above keep their
# exact behaviour. State is an integer stream [height,width,cells...]; spatial
# topology changes the read addresses, not the non-neural transition mechanism.
LATTICE_VOID=32
LATTICE_SIDE=64
LATTICE_CELLS=4096


class LatticeAmbiguous(OutsideDomain):pass


def lattice_stream(value):
    if type(value) not in (list,tuple) or len(value)<3 or any(type(v) is not int for v in value):
        raise OutsideDomain('A lattice stream needs integer height,width and every cell.')
    h,w=value[:2]
    if not 1<=h<=LATTICE_SIDE or not 1<=w<=LATTICE_SIDE or h*w>LATTICE_CELLS or len(value)!=2+h*w:
        raise OutsideDomain('Lattice dimensions/cell count are outside the exact stream bounds.')
    if any(not 0<=v<=MAX_SYMBOL for v in value[2:]):raise OutsideDomain('Invalid lattice cell symbol.')
    return tuple(value)


def lattice_read(source,y,x):
    h,w=source[:2]
    return source[2+y*w+x] if 0<=y<h and 0<=x<w else LATTICE_VOID


def lattice_background(source,mode):
    if type(mode) is int and 0<=mode<=MAX_SYMBOL:return mode
    if mode!='modal':raise OutsideDomain('Unknown background binding.')
    counts=Counter(source[2:]);most=max(counts.values());choices=[v for v,n in counts.items() if n==most]
    if len(choices)!=1:raise OutsideDomain('The modal background role is tied.')
    return choices[0]


def lattice_roles(source,palette):
    if palette=='literal':return source,None
    bg=lattice_background(source,palette);fg=sorted(set(source[2:])-{bg})
    if len(fg)>1:raise OutsideDomain('Binary role transition has more than one foreground symbol.')
    return source[:2]+tuple(int(v!=bg) for v in source[2:]),(bg,fg[0] if fg else None)


def lattice_unroles(source,binding):
    if binding is None:return source
    bg,fg=binding
    if any(v not in (0,1) for v in source[2:]) or fg is None and 1 in source[2:]:
        raise OutsideDomain('The output requires an unknown foreground color role.')
    return source[:2]+tuple(bg if v==0 else fg for v in source[2:])


def lattice_layout(source,layout):
    """One bounded read-head transduction of the immutable integer stream."""
    source=lattice_stream(source)
    if type(layout) is not dict or set(layout)!={'turns','flip','crop','repeat','tile_h','tile_v'}:raise OutsideDomain('Incomplete native read-head program.')
    turns,flip,crop_mode,k,th,tv=(layout[n] for n in ['turns','flip','crop','repeat','tile_h','tile_v'])
    if type(turns) is not int or not 0<=turns<=3 or type(flip) is not bool or any(type(v) is not int or not 1<=v<=3 for v in (k,th,tv)):
        raise OutsideDomain('Invalid read-head transform or dimension factor.')
    h,w=source[:2];y0=x0=0;ch,cw=h,w
    if crop_mode is not None:
        bg=lattice_background(source,crop_mode);ys=[];xs=[]
        for p,v in enumerate(source[2:]):
            if v!=bg:y,x=divmod(p,w);ys.append(y);xs.append(x)
        if not ys:raise OutsideDomain('No supported non-background extent.')
        y0,x0=min(ys),min(xs);ch,cw=max(ys)-y0+1,max(xs)-x0+1
    oh,ow=(cw,ch) if turns%2 else (ch,cw);nh,nw=oh*k*tv,ow*k*th
    if nh>LATTICE_SIDE or nw>LATTICE_SIDE or nh*nw>LATTICE_CELLS:raise OutsideDomain('Output stream dimensions exceed bounds.')
    cells=[]
    for p in range(nh*nw):
        r,c=divmod(p,nw);u,v=(r//k)%oh,(c//k)%ow
        if turns==0:y,x=u,v
        elif turns==1:y,x=ch-1-v,u
        elif turns==2:y,x=ch-1-u,cw-1-v
        else:y,x=v,cw-1-u
        if flip:x=cw-1-x
        cells.append(source[2+(y+y0)*w+x+x0])
    return (nh,nw,*cells)


def lattice_key(source,position,offsets,kind):
    y,x=divmod(position,source[1]);window=tuple(lattice_read(source,y+dy,x+dx) for dy,dx in offsets)
    if kind=='masked_center_sum':
        # A separate explicit aggregate hypothesis: absent neighbours contribute
        # zero, rather than becoming a colored cell or wrapping across rows.
        # The ordered/unmasked schemas still distinguish outside from color0.
        window=tuple(0 if v==LATTICE_VOID else v for v in window);kind='center_sum'
    # Reuse the core's original integer-feature signature operator. Offset
    # lists put the center at the middle, with no row-wrap adjacency.
    key=signature(window,len(window)//2,kind)
    # Flat integer keys survive a JSON save/load exactly, including the old
    # center/multiset operator's nested tuple representation.
    return tuple(v for part in key for v in (part if type(part) is tuple else (part,)))


def lattice_rule(rule):
    """Validate a bounded declarative rule, including hostile saved programs."""
    if type(rule) is not dict:raise OutsideDomain('A native rule must be a declarative object.')
    kind=rule.get('kind')
    if kind=='projection':
        if set(rule)!={'kind','offset','fill'}:raise OutsideDomain('Unknown projection fields.')
        offset=rule['offset'];fill=rule['fill']
        if type(offset) not in (list,tuple) or len(offset)!=2 or any(type(v) is not int for v in offset) or sum(abs(v) for v in offset)>1:
            raise OutsideDomain('Projection reads only the center or one orthogonal neighbour per tick.')
        if fill is not None and (type(fill) is not int or not 0<=fill<=MAX_SYMBOL):raise OutsideDomain('Invalid outside fill symbol.')
    elif kind=='table':
        if set(rule)!={'kind','offsets','features','entries'}:raise OutsideDomain('Unknown transition-table fields.')
        offsets=rule['offsets'];features=rule['features'];entries=rule['entries']
        if type(offsets) not in (list,tuple) or not 1<=len(offsets)<=25 or len(offsets)%2!=1:
            raise OutsideDomain('Use an odd bounded neighbourhood with an explicit center.')
        if any(type(v) not in (list,tuple) or len(v)!=2 or any(type(c) is not int or not -3<=c<=3 for c in v) for v in offsets):
            raise OutsideDomain('Invalid spatial read offset.')
        if len(set(map(tuple,offsets)))!=len(offsets) or tuple(offsets[len(offsets)//2])!=(0,0):raise OutsideDomain('Unique read offsets must put the center in the middle.')
        if features not in ('ordered','center_sum','masked_center_sum','center_multiset'):raise OutsideDomain('Unsupported native feature family.')
        if type(entries) not in (list,tuple) or not 1<=len(entries)<=LATTICE_CELLS:raise OutsideDomain('Transition-table size exceeds bounds.')
        size=2 if features in ('center_sum','masked_center_sum') else len(offsets);seen=set()
        for entry in entries:
            if type(entry) not in (list,tuple) or len(entry)!=2:raise OutsideDomain('Invalid transition entry.')
            key,value=entry
            if type(key) not in (list,tuple) or len(key)!=size or any(type(v) is not int or v<0 for v in key):raise OutsideDomain('Invalid finite transition key.')
            if any(v>(LATTICE_VOID*(len(offsets)-1) if features in ('center_sum','masked_center_sum') and i==1 else LATTICE_VOID) for i,v in enumerate(key)):
                raise OutsideDomain('Transition key exceeds the admitted symbol/sum bounds.')
            if type(value) is not int or not 0<=value<=MAX_SYMBOL or tuple(key) in seen:raise OutsideDomain('Invalid or duplicated transition entry.')
            seen.add(tuple(key))
    else:raise OutsideDomain('Unknown native finite transition rule.')
    return rule


def lattice_step(source,rule):
    """Synchronous CA tick: every new cell reads the same old snapshot."""
    source=lattice_stream(source);rule=lattice_rule(rule);h,w=source[:2]
    if rule['kind']=='projection':
        dy,dx=rule['offset'];fill=rule['fill'];cells=[]
        for p in range(h*w):
            y,x=divmod(p,w);v=lattice_read(source,y+dy,x+dx)
            if v==LATTICE_VOID:
                if fill is None:raise OutsideDomain('A boundary read has no learned fill value.')
                v=fill
            cells.append(v)
    elif rule['kind']=='table':
        offsets=rule['offsets'];kind=rule['features'];table={tuple(k):v for k,v in rule['entries']};cells=[]
        for p in range(h*w):
            key=lattice_key(source,p,offsets,kind)
            if key not in table:raise OutsideDomain('An unobserved neighbourhood has no supported transition; no guessed cell was emitted.')
            cells.append(table[key])
    else:raise OutsideDomain('Unknown native finite transition rule.')
    return lattice_stream((h,w,*cells))


def lattice_run(source,program):
    """Execute only declarative shipped operators; no native generated code."""
    source=lattice_stream(source)
    if type(program) is not dict or set(program)!={'format','layout','palette','rule','ticks'} or program['format']!='cael-lattice-stream-v1':
        raise OutsideDomain('Invalid native stream program.')
    ticks=program['ticks']
    if type(ticks) is not int or not 1<=ticks<=8:raise OutsideDomain('Use 1 to 8 synchronous ticks.')
    value=lattice_layout(source,program['layout']);value,binding=lattice_roles(value,program['palette'])
    for _ in range(ticks):value=lattice_step(value,program['rule'])
    return lattice_unroles(value,binding)


def _lattice_layouts():
    for crop in (None,0,'modal'):
        for flip in (False,True):
            for turns in range(4):
                yield dict(turns=turns,flip=flip,crop=crop,repeat=1,tile_h=1,tile_v=1)
    for repeat,th,tv in [(2,1,1),(3,1,1),(1,2,1),(1,1,2)]:
        yield dict(turns=0,flip=False,crop=None,repeat=repeat,tile_h=th,tile_v=tv)


def _lattice_schemas():
    yield [(0,0)],'ordered'
    cross=[(-1,0),(0,-1),(0,0),(0,1),(1,0)]
    square=[(y,x) for y in range(-1,2) for x in range(-1,2)]
    wide=[(-2,0),(-1,0),(0,-2),(0,-1),(0,0),(0,1),(0,2),(1,0),(2,0)]
    for offsets in [cross,square,[(0,x) for x in range(-2,3)],[(y,0) for y in range(-2,3)],wide]:
        for kind in ['masked_center_sum','center_sum','center_multiset','ordered']:yield offsets,kind


def lattice_fit(examples,query,max_models=384,max_cell_visits=1500000):
    """Infer finite integer-stream programs; only demos/query are admitted.

    Learned lookup tables must transfer with full coverage in every held-out
    complete demonstration pair. Unsupported query keys never use the older
    empirical guess fallback. Minimum-cost consensus is an inductive prior.
    """
    if type(max_models) is not int or not 1<=max_models<=4096 or type(max_cell_visits) is not int or not 1<=max_cell_visits<=12000000:raise OutsideDomain('Invalid native fitting bounds.')
    if type(examples) is not list or not 2<=len(examples)<=12:raise OutsideDomain('Supply 2 to 12 complete stream demonstrations.')
    pairs=[]
    for e in examples:
        if type(e) is not dict or set(e)!={'input','output'}:raise OutsideDomain('Stream examples need exactly input/output.')
        pairs.append((lattice_stream(e['input']),lattice_stream(e['output'])))
    q=lattice_stream(query)
    if sum(len(a)+len(b)-4 for a,b in pairs)>12000:raise OutsideDomain('Stream demonstration cell budget exceeded.')
    seen={}
    for a,b in pairs:
        if a in seen and seen[a]!=b:raise OutsideDomain('Identical stream inputs have conflicting outputs.')
        seen[a]=b
    models=[];work=0;tested=0;limited=False
    def charge(n):
        nonlocal work
        work+=n
        if work>max_cell_visits:raise OverflowError('Native stream fitting cell-work budget')
    def append(program,cost,validation):
        try:prediction=lattice_run(q,program)
        except OutsideDomain:return
        models.append(dict(program=program,prediction=prediction,cost=cost,validation=validation))
    try:
        for layout in _lattice_layouts():
            try:states=[lattice_layout(a,layout) for a,b in pairs]
            except OutsideDomain:continue
            if any(a[:2]!=b[:2] for a,(_,b) in zip(states,pairs)):continue
            targets=[b for a,b in pairs]
            base_cost=2*int(layout['turns']!=0 or layout['flip'])+3*int(layout['crop'] is not None)+2*(layout['repeat']-1)+2*(layout['tile_h']+layout['tile_v']-2)
            # Pure read-head copying generalizes to previously unseen colors;
            # only outside fill is learned, never a flattened row-wrap value.
            for dy,dx in [(0,0),(-1,0),(1,0),(0,-1),(0,1)]:
                for ticks in ([1] if (dy,dx)==(0,0) else [1,2,3]):
                    fills=set();fit=True;fill_inputs=set()
                    for a,b in zip(states,targets):
                        found=False;copied=0;h,w=a[:2];charge(h*w)
                        for p,target in enumerate(b[2:]):
                            y,x=divmod(p,w);v=lattice_read(a,y+dy*ticks,x+dx*ticks)
                            if v==LATTICE_VOID:fills.add(target);found=True
                            elif v!=target:fit=False;break
                            else:copied+=1
                        if found:fill_inputs.add(a)
                        # A read-head displacement must actually transport
                        # observed material; a wholly outside constant fill is
                        # not evidence of a spatial transition.
                        if not copied:fit=False
                        if not fit or len(fills)>1:fit=False;break
                    fill_pairs=len(fill_inputs)
                    if not fit or fills and fill_pairs<2:continue
                    program=dict(format='cael-lattice-stream-v1',layout=layout,palette='literal',rule=dict(kind='projection',offset=[dy,dx],fill=next(iter(fills)) if fills else None),ticks=ticks)
                    append(program,(base_cost+abs(dy*ticks)+abs(dx*ticks),0,0),dict(kind='structural-read-head',all_examples_exact=True,fill_pair_support=fill_pairs))
            # Local integer state transition induction, with optional dynamic
            # binary roles for color-permutation transfer.
            for palette in ['literal',0,'modal']:
                role_pairs=[]
                try:
                    for a,b in zip(states,targets):
                        aa,binding=lattice_roles(a,palette)
                        if binding is None:bb=b
                        else:
                            bg,fg=binding
                            if any(v not in (bg,fg) for v in b[2:]):raise OutsideDomain('Output has an unbound binary role.')
                            bb=b[:2]+tuple(int(v!=bg) for v in b[2:])
                        role_pairs.append((aa,bb))
                except OutsideDomain:continue
                for offsets,kind in _lattice_schemas():
                    tested+=1
                    if tested>max_models:limited=True;break
                    table={};counts=Counter();by_pair=[];consistent=True
                    for a,b in role_pairs:
                        local={};charge((len(a)-2)*len(offsets))
                        for p,v in enumerate(b[2:]):
                            key=lattice_key(a,p,offsets,kind)
                            if key in table and table[key]!=v:consistent=False;break
                            table[key]=v;local[key]=v;counts[key]+=1
                        by_pair.append(local)
                        if not consistent:break
                    if not consistent:continue
                    transferred=True
                    for i,local in enumerate(by_pair):
                        rest={k:v for j,record in enumerate(by_pair) if j!=i for k,v in record.items()}
                        if any(k not in rest or rest[k]!=v for k,v in local.items()):transferred=False;break
                    if not transferred:continue
                    rule=dict(kind='table',offsets=[list(v) for v in offsets],features=kind,entries=[[list(k),v] for k,v in sorted(table.items())])
                    program=dict(format='cael-lattice-stream-v1',layout=layout,palette=palette,rule=rule,ticks=1)
                    feature_cost=0 if len(offsets)==1 else 2 if kind in ('center_sum','masked_center_sum') else 3 if kind=='center_multiset' else 4
                    cost=(base_cost+1+feature_cost+int(palette!='literal'),len(table),len(offsets))
                    append(program,cost,dict(kind='held-complete-pair-transfer',pairs=len(pairs),coverage=1.0,correct_cells=sum(len(b)-2 for a,b in pairs),observed_signatures=len(table)))
                if limited:break
            if limited:break
    except OverflowError:limited=True
    if not models:raise OutsideDomain('No fully supported native stream rule found within the declared model/work bounds.')
    best=min(m['cost'] for m in models);fits=[m for m in models if m['cost']==best]
    predictions={m['prediction'] for m in fits}
    if len(predictions)!=1:raise LatticeAmbiguous('Equally simple supported stream rules disagree on this query.')
    selected=min(fits,key=lambda m:json.dumps(m['program'],sort_keys=True))
    # Exact orientation ambiguity stays explicit even when identity has the
    # cheaper description. Do not infer an orientation from symmetric demos.
    p=selected['program'];lay=p['layout'];r=p['rule']
    if not lay['turns'] and not lay['flip'] and lay['crop'] is None and lay['repeat']==lay['tile_h']==lay['tile_v']==1 and (r['kind']=='projection' and r['offset']==[0,0] or r['kind']=='table' and r['offsets']==[[0,0]]):
        for m in models:
            alt=m['program'];al=alt['layout'];ar=alt['rule']
            if (al['turns'] or al['flip']) and al['crop'] is None and al['repeat']==al['tile_h']==al['tile_v']==1 and (ar['kind']=='projection' and ar['offset']==[0,0] or ar['kind']=='table' and ar['offsets']==[[0,0]]) and m['prediction']!=selected['prediction']:
                raise LatticeAmbiguous('The stream examples do not distinguish orientation on this query.')
    for a,b in pairs:
        if lattice_run(a,selected['program'])!=b:raise OutsideDomain('Selected stream program did not replay every demonstration.')
    return dict(prediction=list(selected['prediction']),program=selected['program'],selected_cost=list(best),validation=selected['validation'],
        demonstrations_replayed=len(pairs),fitted_supported_hypotheses=len(models),minimum_cost_hypotheses=len(fits),tested_table_models=tested,cell_feature_visits=work,search_limited=limited,
        kernel='cael_unified.local_automata.lattice_run',synchronous=True,masked_row_boundaries=True,query_fully_supported=True,persistent_learning=False,neural=False,
        assumptions='Minimum-description-length consensus within a bounded spatial stream/read-head and local-rule language. Full demonstration fit/held-pair transfer does not identify arbitrary hidden rules.')
