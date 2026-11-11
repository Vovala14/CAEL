"""Finite symbolic action models, trace induction and checked domain-free plans.

The interpreter accepts data, never Python. A trace-induced model is a bounded
hypothesis: replay proves a plan relative to that model, not to an unseen world.
"""
from collections import defaultdict
import hashlib
import heapq
import itertools
import json
import time


class Unclear(ValueError):pass


def scalar(x):
    return type(x) is bool or type(x) is int and abs(x)<=1000000 or type(x) is str and 0<len(x)<=120


def state(value):
    if type(value) is not dict or not 1<=len(value)<=64:raise Unclear('State needs 1 to 64 explicit variables.')
    if any(type(k) is not str or not k or len(k)>80 or not scalar(v) for k,v in value.items()):raise Unclear('State variables must be bounded literal values.')
    return dict(value)


def expected(value,s):
    if type(value) is dict and set(value)=={'var'}:
        if value['var'] not in s:raise Unclear('Unknown referenced variable.')
        return s[value['var']]
    if not scalar(value):raise Unclear('Comparison needs a literal or variable reference.')
    return value


def condition(spec,s):
    if type(spec) is not dict or len(spec)>64:raise Unclear('Conditions must be explicit variable constraints.')
    matched=True
    for name,wanted in spec.items():
        if name not in s:raise Unclear('Condition references an unknown variable.')
        op='eq';value=wanted
        if type(wanted) is dict and set(wanted)=={'op','value'}:op=wanted['op'];value=wanted['value']
        value=expected(value,s);actual=s[name]
        if op in ('eq','ne'):
            equal=type(actual) is type(value) and actual==value
            if (op=='eq')!=equal:matched=False
        elif op in ('lt','le','gt','ge'):
            if type(actual) is not int or type(value) is not int:raise Unclear('Ordered comparisons require integers.')
            if not {'lt':actual<value,'le':actual<=value,'gt':actual>value,'ge':actual>=value}[op]:matched=False
        else:raise Unclear('Unknown comparison operator.')
    return matched


def expression(expr,s,name):
    if scalar(expr):return expr
    if type(expr) is not dict or len(expr)!=1:raise Unclear('Effect must be one bounded primitive.')
    op,value=next(iter(expr.items()))
    if op=='set':return expected(value,s)
    if op=='copy':
        if type(value) is not str or value not in s:raise Unclear('Unknown copied variable.')
        return s[value]
    if op=='toggle' and value is True and type(s[name]) is bool:return not s[name]
    if op in ('add','xor','multiply','mod') and type(value) is int and type(s[name]) is int:
        if op=='add':return s[name]+value
        if op=='xor':return s[name]^value
        if op=='multiply':return s[name]*value
        if op=='mod' and value>0:return s[name]%value
    raise Unclear('Effect operand/type is unsupported.')


def execute(s,action,bounds):
    if not condition(action.get('pre',{}),s):return None
    effects=action.get('effects',{})
    if type(effects) is not dict or any(n not in s for n in effects):raise Unclear('Unknown effect variable.')
    result=dict(s)
    for name,expr in effects.items():result[name]=expression(expr,s,name)
    if any(not scalar(v) or type(v) is not type(s[n]) for n,v in result.items()):return None
    for name,domain in bounds.items():
        if type(domain) is dict:
            if set(domain)!={'min','max'} or type(domain['min']) is not int or type(domain['max']) is not int or domain['min']>domain['max']:raise Unclear('Invalid integer range.')
            if type(result[name]) is not int or not domain['min']<=result[name]<=domain['max']:return None
        elif type(domain) is list:
            if not 1<=len(domain)<=256 or any(not scalar(v) for v in domain):raise Unclear('Invalid finite domain.')
            if not any(type(result[name]) is type(v) and result[name]==v for v in domain):return None
        else:raise Unclear('Bounds need an integer range or finite literal list.')
    return result


def effect_candidates(name,traces):
    values=[t['after'][name] for t in traces];before=[t['before'][name] for t in traces]
    candidates=[]
    if all(type(a) is type(b) and a==b for a,b in zip(before,values)):return [dict(copy=name)]
    if all(type(v) is type(values[0]) and v==values[0] for v in values):candidates.append(dict(set=values[0]))
    if all(type(v) is int for v in before+values):
        deltas={b-a for a,b in zip(before,values)};xors={a^b for a,b in zip(before,values)}
        if len(deltas)==1:candidates.append(dict(add=next(iter(deltas))))
        if len(xors)==1:candidates.append(dict(xor=next(iter(xors))))
    if all(type(v) is bool for v in before+values) and all(a!=b for a,b in zip(before,values)):candidates.append(dict(toggle=True))
    for other in traces[0]['before']:
        if all(type(t['before'][other]) is type(t['after'][name]) and t['before'][other]==t['after'][name] for t in traces):candidates.append(dict(copy=other))
    return candidates


def learned(traces,names,keys):
    if type(traces) is not list or not 1<=len(traces)<=512:raise Unclear('Supply at most 512 complete visible transitions.')
    grouped=defaultdict(list)
    for row in traces:
        if type(row) is not dict or set(row) not in ({'before','action','after'},{'before','action','after','accepted'}):raise Unclear('A transition needs before/action/after and optional accepted.')
        a=state(row['before']);b=state(row['after'])
        if set(a)!=keys or set(b)!=keys or row['action'] not in names:raise Unclear('Transition variables/action do not match this world.')
        if 'accepted' in row and type(row['accepted']) is not bool:raise Unclear('Accepted is a literal Boolean.')
        grouped[row['action']].append(row)
    models={};diagnostics={}
    for name,rows in grouped.items():
        positive=[r for r in rows if r.get('accepted',True)]
        if not positive:continue
        effects={};ambiguous=[]
        for variable in sorted(keys):
            options=effect_candidates(variable,positive)
            if not options:raise Unclear('No admitted effect explains every transition of '+name+'.')
            effects[variable]=options
            if len(options)>1:ambiguous.append(variable)
        # Preconditions are not invented from correlations. Explicit provided
        # preconditions can be combined with learned effects; otherwise action
        # availability outside observed contexts remains an assumption.
        models[name]=effects
        diagnostics[name]=dict(observed_successes=len(positive),ambiguous_effects=ambiguous,
            rejected_contexts=[r['before'] for r in rows if not r.get('accepted',True)],preconditions_unlearned=True)
    return models,diagnostics


def successor(s,action,bounds,models,rejected):
    if action['name'] not in models:return execute(s,action,bounds)
    if any(s==x for x in rejected[action['name']]['rejected_contexts']):return None
    effects={}
    for name,options in models[action['name']].items():
        values=[expression(e,s,name) for e in options]
        if any(type(v) is not type(values[0]) or v!=values[0] for v in values[1:]):return None
        effects[name]=dict(set=values[0])
    return execute(s,dict(action,effects=effects),bounds)


def solve(task,max_nodes=16000,max_depth=96,seconds=3.0):
    if type(task) is not dict or set(task)-{'initial','goal','actions','bounds','traces'}:raise Unclear('Use only initial, goal, actions, optional bounds and complete traces.')
    if not {'initial','goal','actions'}<=set(task):raise Unclear('A world needs initial, goal and actions.')
    initial=state(task['initial']);goal=task['goal'];condition(goal,initial)
    bounds=task.get('bounds',{})
    if type(bounds) is not dict or any(n not in initial for n in bounds):raise Unclear('Unknown bounded variable.')
    actions=task['actions']
    if type(actions) is not list or not 1<=len(actions)<=256:raise Unclear('Provide 1 to 256 finite actions.')
    names=set()
    for a in actions:
        if type(a) is not dict or set(a)-{'name','pre','effects','cost'} or not isinstance(a.get('name'),str) or not a['name'] or len(a['name'])>120 or a['name'] in names:raise Unclear('Actions need distinct names and only pre/effects/cost.')
        if type(a.get('cost',1)) is not int or not 1<=a.get('cost',1)<=1000:raise Unclear('Action costs must be positive bounded integers.')
        names.add(a['name']);condition(a.get('pre',{}),initial)
        execute(initial,dict(a,pre={}),bounds)
    models=diagnostics={}
    if 'traces' in task:
        models,diagnostics=learned(task['traces'],names,set(initial))
        for action in actions:
            if 'effects' not in action:continue
            for row in task['traces']:
                if row['action']!=action['name']:continue
                predicted=execute(row['before'],action,bounds)
                accepted=row.get('accepted',True)
                if accepted and predicted!=row['after'] or not accepted and predicted is not None:
                    raise Unclear('A declared action contradicts an observed transition.')
            # Observation learning cannot silently replace caller-supplied
            # effects or discard one of their constraints.
            models.pop(action['name'],None);diagnostics.pop(action['name'],None)
    if any('effects' not in a and a['name'] not in models for a in actions):raise Unclear('An action lacks both declared effects and learnable observations.')
    keys=sorted(initial);key=lambda s:tuple((type(s[n]).__name__,s[n]) for n in keys)
    first=key(initial);counter=itertools.count();queue=[(0,next(counter),0,first,initial)]
    best={first:0};parents={};expanded=0;started=time.monotonic();depth_limited=False;goal_key=None;final=None;status='exhausted'
    while queue:
        if expanded>=max_nodes or time.monotonic()-started>seconds:status='resource-limit';break
        cost,_,depth,k,s=heapq.heappop(queue)
        if best[k]!=cost:continue
        if condition(goal,s):goal_key=k;final=s;status='plan';break
        if depth>=max_depth:depth_limited=True;continue
        expanded+=1
        for a in actions:
            new=successor(s,a,bounds,models,diagnostics)
            if new is None:continue
            nk=key(new);nc=cost+a.get('cost',1)
            if nc<best.get(nk,10**30):
                best[nk]=nc;parents[nk]=(k,a['name']);heapq.heappush(queue,(nc,next(counter),depth+1,nk,new))
    if status=='exhausted' and depth_limited:status='depth-limit'
    plan=[]
    if goal_key is not None:
        while goal_key!=first:
            goal_key,name=parents[goal_key];plan.append(name)
        plan.reverse()
    replay=dict(initial);steps=[];index={a['name']:a for a in actions}
    if status=='plan':
        for name in plan:
            new=successor(replay,index[name],bounds,models,diagnostics)
            if new is None:raise AssertionError('Plan replay rejected an action')
            steps.append(dict(action=name,before=replay,after=new));replay=new
        assert replay==final and condition(goal,replay)
    return dict(status=status,plan=plan,final=final,expanded_states=expanded,visited_states=len(best),
        replay_checked=status=='plan',steps=steps,seconds=time.monotonic()-started,
        model='trace-induced-version-space' if models else 'declared-transition-model',learned_diagnostics=diagnostics,
        assumptions='Observed effect hypotheses agree on each planned step. Unobserved preconditions may still invalidate learned plans.' if models else 'Correct relative to the complete supplied bounded action model.',
        task_sha256=hashlib.sha256(json.dumps(task,sort_keys=True,separators=(',',':')).encode()).hexdigest(),neural=False)


def reply(task):
    try:result=solve(task)
    except (Unclear,KeyError,TypeError,RecursionError,OverflowError) as exc:
        return dict(route='chat/world-clarify',response='Please clarify the state/action task: '+str(exc),sources=[])
    if result['status']!='plan':
        text='No checked plan was found within the admitted model and limits ('+result['status']+'). This does not establish that the real puzzle is impossible.'
        return dict(route='chat/world-clarify',response=text,sources=[],world_reasoning=result)
    return dict(route='chat/world-plan',response=json.dumps(dict(plan=result['plan'],final=result['final'])),sources=[],world_reasoning=result,
        verification=dict(status='plan-replayed',check=result['assumptions']))
