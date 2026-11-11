"""Visible-history state graph and bounded action exploration, without oracles.

Unknown goals remain unknown. A schema-valid exploratory action is never
reported as a proved solution. No hidden game source or global state is read.
"""
from collections import Counter, deque
import hashlib
import json
from .grid_induction import Unsupported, grid, components


def observation(value):
    if type(value) is not dict or set(value) != {'frames','state','levels_completed','available_actions'}:
        raise Unsupported('An observation needs only frames, state, levels_completed and available_actions.')
    frames=value['frames']
    if type(frames) is not list or not 1 <= len(frames) <= 4:raise Unsupported('Expected 1 to 4 visible grid frames.')
    frames=[grid(x,64,256) for x in frames]
    if type(value['state']) is not str or type(value['levels_completed']) is not int or value['levels_completed'] < 0:
        raise Unsupported('Invalid visible environment status.')
    actions=value['available_actions']
    if type(actions) is not list or not 1 <= len(actions) <= 16:raise Unsupported('Expected a finite available action list.')
    names=set()
    for a in actions:
        if (type(a) is not dict or set(a) != {'action','complex'} or type(a['action']) is not str
                or not a['action'] or len(a['action'])>48 or type(a['complex']) is not bool or a['action'] in names):
            raise Unsupported('Action names and coordinate requirements must be explicit and distinct.')
        names.add(a['action'])
    state_key=hashlib.sha256(json.dumps([frames,value['state'],value['levels_completed']],separators=(',',':')).encode()).hexdigest()
    choices=[]
    for a in actions:
        if not a['complex']:choices.append((a['action'],None,None));continue
        # Component centres are an explicit finite perceptual bias. This does
        # not assert that they include every meaningful click in every game.
        frame=frames[-1];background=Counter(v for row in frame for v in row).most_common(1)[0][0]
        parts=components(frame,background)
        for part in sorted(parts,key=lambda p:(min(p),len(p)))[:64]:
            ys=[p[0] for p in part];xs=[p[1] for p in part]
            choices.append((a['action'],(min(xs)+max(xs))//2,(min(ys)+max(ys))//2))
    if not choices:raise Unsupported('No supported simple action or visible component-centre click is available.')
    return state_key,tuple(choices)


def action_tuple(value):
    if type(value) is not dict or set(value) != {'action','data'} or type(value['data']) is not dict:return None
    if value['data']=={}:return value['action'],None,None
    if set(value['data'])=={'x','y'} and all(type(value['data'][k]) is int and 0<=value['data'][k]<=63 for k in ['x','y']):
        return value['action'],value['data']['x'],value['data']['y']
    return None


def choose(current, history):
    key,options=observation(current)
    if current['state'] in {'WIN','GAME_OVER'}:raise Unsupported('The environment has ended; reset explicitly before another action.')
    visits=Counter();global_visits=Counter();edges={};offered={};previous=None;pending=None;transition_count=0
    for role,value in history:
        if role=='user':
            old_key,old_options=observation(value);offered[old_key]=old_options
            if previous is not None and pending is not None:
                visits[previous,pending]+=1;global_visits[pending]+=1;transition_count+=1
                edges.setdefault(previous,{}).setdefault(pending,set()).add(old_key)
            previous=old_key;pending=None
        elif role=='assistant' and previous is not None:
            candidate=action_tuple(value)
            if candidate in offered.get(previous,()):pending=candidate
    untried=[a for a in options if visits[key,a]==0]
    plan=None
    if not untried:
        # Known deterministic paths can return to a state with unexplored
        # actions. Search is over observed edges, never an invented rule.
        todo=deque([(key,[])]);seen={key}
        while todo and len(seen)<=512:
            node,path=todo.popleft()
            if node!=key and any(visits[node,a]==0 for a in offered.get(node,())):
                plan=path;break
            for action,targets in sorted(edges.get(node,{}).items(),key=lambda x:str(x[0])):
                # Conflicting observed effects do not become a deterministic
                # path merely because the latest transition is convenient.
                if len(targets)!=1:continue
                target=next(iter(targets))
                if target not in seen:seen.add(target);todo.append((target,path+[action]))
    if plan:chosen=plan[0];reason='observed-path-to-unexplored-state'
    elif untried:chosen=min(untried,key=lambda a:(global_visits[a],str(a)));reason='untried-action-at-visible-state'
    else:raise Unsupported('The observed state graph has no supported unexplored action; a goal or additional action representation is needed.')
    name,x,y=chosen
    return dict(action=name,data={} if x is None else dict(x=x,y=y)),dict(
        status='exploration',reason=reason,observed_transitions=transition_count,known_states=len(offered),
        goal_known=False,coordinates='visible-component-centres-only',neural=False,persistent_learning=False)


def reply(task,history):
    try:action,record=choose(task,history)
    except (Unsupported,RecursionError) as exc:
        return dict(route='chat/environment-clarify',response='Please clarify the environment task: '+str(exc),sources=[],
                    environment_reasoning=dict(status='unsupported-or-complete',neural=False))
    return dict(route='chat/environment-explore',response=json.dumps(action,separators=(',',':')),sources=[],
                environment_reasoning=record,verification=dict(status='legal-action-checked',check='Exploration from visible observations; no success or optimality claim.'))
