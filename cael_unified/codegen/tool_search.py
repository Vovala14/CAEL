"""Bounded synthesis of ordered tool plans from examples and supplied helpers.

Search composes primitives, not completed algorithms. Expected outputs only
check candidates; they never become program literals or function bodies.
Observational pruning/beam budgets make this incomplete and cannot prove a
unique general solution. A found contrasting witness triggers clarification.
"""
import re
import time

from .task_tools import Step, interpret, outcome
from .workbench import same


def library(plan):
    ops=[Step('filter','x > 0'),Step('filter','x < 0'),Step('filter','x != 0'),
         Step('filter','x % 2 == 0'),Step('filter','x % 2 != 0'),Step('map','x * x'),
         Step('map','abs(x)'),Step('map','-x'),Step('map','x * 2'),Step('map','x + 1'),
         Step('scan','state + x'),Step('unique'),Step('sort'),Step('sort',reverse=True),Step('reverse'),
         Step('window',count=2),Step('window',count=3),Step('sum'),Step('count'),Step('product'),Step('min'),Step('max')]
    # Additional bounds must come from explicit request constants, never gold
    # answers. Default primitive window sizes 2/3 are part of the fixed grammar.
    for count in sorted({int(x) for x in re.findall(r'\b(?:size|first|last)\s+(\d{1,2})\b',plan.get('description',''),re.I)}):
        if 0<=count<=40:
            ops.extend([Step('first',count=count),Step('last',count=count)])
            if count:ops.append(Step('window',count=count))
    for name,fn in plan['functions'].items():
        total=len(fn.args.posonlyargs)+len(fn.args.args);required=total-len(fn.args.defaults)
        if required<=1<=total:ops.extend([Step('map',helper=name),Step('filter',helper=name)])
        if required<=2<=total:ops.extend([Step('scan',helper=name),Step('reduce',helper=name)])
    return ops


def describe(step):
    if step.kind=='window':return 'sum each full window of size '+str(step.count)
    if step.kind in {'first','last'}:return 'take the '+step.kind+' '+str(step.count)+' values'
    if step.kind=='sort':return 'sort descending' if step.reverse else 'sort ascending'
    if step.kind in {'map','filter','scan','reduce'}:
        text=step.kind+(' using '+step.helper if step.helper else ' '+step.expression)
        if step.kind in {'scan','reduce'}:text+=' starting at '+str(step.initial)
        return text
    return dict(unique='remove duplicates preserving order',reverse='reverse',count='count',sum='sum',
                product='product',min='minimum',max='maximum')[step.kind]


def synthesize(plan,seconds=2.5,max_plans=3000,max_depth=4,width=48):
    start=time.monotonic();ops=library(plan);cache={};stats=dict(plans=0,transitions=0,max_depth=max_depth,beam_width=width,budget_exhausted=False)
    inputs=[c['args'][0] for c in plan['cases']];expected=[c['expected'] for c in plan['cases']]
    frontier=[([],inputs)];matches=[];seen=set()
    terminal={'sum','count','product','min','max','reduce'}
    def exhausted():return stats['plans']>=max_plans or time.monotonic()-start>=seconds
    def apply(step,values):
        key=(step,tuple(values))
        if key not in cache:
            stats['transitions']+=1
            single={**plan,'steps':[step]}
            cache[key]=outcome(lambda:interpret(single,values,input_bound=10**12))
        return cache[key]
    for depth in range(1,max_depth+1):
        following=[]
        for prior,values in frontier:
            for op in ops:
                if exhausted():stats['budget_exhausted']=True;break
                stats['plans']+=1;observed=[]
                for value in values:
                    result=apply(op,value)
                    if result['status']!='value':break
                    observed.append(result['value'])
                if len(observed)!=len(inputs):continue
                stages=[*prior,op]
                if all(same(a,b) for a,b in zip(observed,expected)):
                    matches.append(stages)
                    # Keep searching through a bounded number of hypotheses.
                    if len(matches)>=16:break
                if op.kind in terminal or not all(type(v) is list for v in observed):continue
                signature=tuple(tuple(v) for v in observed)
                # Search pruning is incomplete; it is not a uniqueness claim.
                if signature in seen:continue
                seen.add(signature);following.append((stages,observed))
            if stats['budget_exhausted'] or len(matches)>=16:break
        if stats['budget_exhausted'] or len(matches)>=16:break
        # Prefer intermediate values that match parts of list-valued examples,
        # but never manufacture a program literal from an expected output.
        def priority(item):
            _,values=item
            return -sum(type(want) is list and same(value,want) for value,want in zip(values,expected))
        frontier=sorted(following,key=priority)[:width]
        if not frontier:break
    stats.update(seconds=time.monotonic()-start,matches=len(matches),cached_transitions=len(cache))
    if not matches:return dict(status='not-found',stats=stats)
    witnesses=[[],[0],[1],[-1],[1,1],[-2,0,3],[3,-1,3,2],[-4,-2],[2,0,1,-3,5],[5,4,3,2,1],[-1,2,-3,4,-5,6]]
    first=matches[0]
    for alternate in matches[1:]:
        for xs in witnesses:
            if xs in inputs:continue
            a=outcome(lambda:interpret({**plan,'steps':first},xs));b=outcome(lambda:interpret({**plan,'steps':alternate},xs))
            if a['status']=='value' and b['status']=='value' and not same(a['value'],b['value']):
                return dict(status='ambiguous',witness=xs,predictions=[a['value'],b['value']],stats=stats)
    return dict(status='planned',plan={**plan,'steps':first,'clauses':[describe(s) for s in first]},stats=stats)
