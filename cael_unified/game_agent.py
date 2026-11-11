"""Compact visible-object dynamics and planning, with explicit request memory.

No game names, action meanings, color roles, source, target files or neural
answers occur here. Navigation is one learned model class, not a universal
physics claim. Unknown goals use a disclosed landmark exploration prior.
"""
from collections import Counter,defaultdict,deque
import hashlib,heapq,json
from .grid_induction import grid,components,Unsupported
from . import scene_objects

MAX_FRAMES=256
MAX_CELLS=262144
MAX_MEMORY=180000


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def pack(g):
    runs=[]
    for row in g:
        for v in row:
            if runs and runs[-1][0]==v:runs[-1][1]+=1
            else:runs.append([v,1])
    return [len(g),len(g[0]),runs]
def unpack(value):
    if type(value) is not list or len(value)!=3:raise Unsupported('Invalid compact visible frame.')
    h,w,runs=value
    if type(h) is not int or type(w) is not int or not 1<=h<=64 or not 1<=w<=64 or type(runs) is not list or len(runs)>4096:raise Unsupported('Invalid compact frame dimensions.')
    cells=[]
    for run in runs:
        if type(run) is not list or len(run)!=2 or any(type(x) is not int for x in run) or not 0<=run[0]<256 or not 1<=run[1]<=4096:raise Unsupported('Invalid run encoding.')
        if len(cells)+run[1]>h*w:raise Unsupported('Compact frame overflow.')
        cells.extend([run[0]]*run[1])
    if len(cells)!=h*w:raise Unsupported('Incomplete compact frame.')
    return tuple(tuple(cells[y*w:(y+1)*w]) for y in range(h))


def objects(g):return scene_objects.objects(g)


def read(task):
    if type(task) is not dict or set(task)-{'frames','state','levels_completed','available_actions','agent_state','goal','episode'}:raise Unsupported('Only visible observations, optional explicit goal/episode and caller-carried agent_state are admitted.')
    if not {'frames','state','levels_completed','available_actions'}<=set(task):raise Unsupported('Incomplete environment observation.')
    fs=task['frames']
    if type(fs) is not list or not 1<=len(fs)<=MAX_FRAMES:raise Unsupported('Provide 1 to 256 complete visible frames.')
    frames=[grid(x,64,256) for x in fs]
    if sum(len(g)*len(g[0]) for g in frames)>MAX_CELLS:raise Unsupported('Streaming observation cell budget exceeded.')
    if len({(len(g),len(g[0])) for g in frames})!=1:raise Unsupported('Frame dimensions changed inside one observation.')
    if type(task['state']) is not str or type(task['levels_completed']) is not int or task['levels_completed']<0:raise Unsupported('Invalid visible status.')
    actions=task['available_actions'];names=set()
    if type(actions) is not list or not 1<=len(actions)<=16:raise Unsupported('Expected a bounded visible action list.')
    for a in actions:
        if type(a) is not dict or set(a)!={'action','complex'} or type(a['action']) is not str or not a['action'] or len(a['action'])>48 or type(a['complex']) is not bool or a['action'] in names:raise Unsupported('Actions need unique exact names and Boolean coordinate requirements.')
        names.add(a['action'])
    if 'episode' in task and (type(task['episode']) is not str or not 1<=len(task['episode'])<=100):raise Unsupported('Episode is an explicit bounded caller label, not inferred text identity.')
    goal=task.get('goal')
    if goal is not None:
        if type(goal) is not dict or set(goal)!={'subject','target'} or type(goal['subject']) is not dict or set(goal['subject'])!={'color'}:raise Unsupported('A visible spatial goal needs subject color and target color or coordinates.')
        if type(goal['subject']['color']) is not int or not 0<=goal['subject']['color']<256:raise Unsupported('Invalid subject selector.')
        target=goal['target']
        if type(target) is not dict or set(target) not in ({'color'},{'x','y'}):raise Unsupported('Invalid spatial goal target.')
        if any(type(v) is not int for v in target.values()):raise Unsupported('Goal values must be integers.')
        if 'color' in target and not 0<=target['color']<256:raise Unsupported('Invalid target color.')
        if 'x' in target and not(0<=target['x']<len(frames[-1][0]) and 0<=target['y']<len(frames[-1])):raise Unsupported('Goal coordinate outside the frame.')
    return frames,actions,goal


def empty(domain):
    return dict(format='cael-visible-agent-v3',domain=domain,turn=0,last=None,pending=None,chain='0'*64,
        motors={},controller=None,passable=[],collisions={},blocked_edges=[],visits={},edges={},goals_visited={},
        pruned_states=0,observations_processed=0,frames_processed=0,last_level=0,animation_events={},context_revision=0,dynamics={},poses={},
        tracks=[],support_evidence={},probe_visits={},last_probe_key=None,intent=None,goal_revisions=0,no_effects={},probe_edges={},last_probe_actor=None)


def restore(task,domain):
    value=task.get('agent_state')
    if value is None:return empty(domain)
    if type(value) is not dict or set(value)!=set(empty(domain))|{'checksum'} or value.get('format')!='cael-visible-agent-v3':raise Unsupported('Unknown or incomplete explicit agent memory; reset an older-format episode.')
    raw=dict(value);checksum=raw.pop('checksum')
    if len(json.dumps(value))>MAX_MEMORY or digest(raw)!=checksum:raise Unsupported('Agent memory size/checksum mismatch.')
    if raw['domain']!=domain:raise Unsupported('Agent memory belongs to a different explicit episode/geometry/goal; reset it.')
    # Deserialized memory is untrusted data, never instructions or code.
    for field in ['turn','pruned_states','observations_processed','frames_processed','last_level','context_revision','goal_revisions']:
        if type(raw[field]) is not int or not 0<=raw[field]<=10000000:raise Unsupported('Invalid memory counter.')
    for field,limit in [('motors',128),('collisions',256),('visits',512),('edges',512),('goals_visited',512),('animation_events',64),('dynamics',128),('poses',128)]:
        if type(raw[field]) is not dict or len(raw[field])>limit:raise Unsupported('Invalid bounded memory table.')
    if type(raw['passable']) is not list or len(raw['passable'])>256 or type(raw['blocked_edges']) is not list or len(raw['blocked_edges'])>1024:raise Unsupported('Invalid learned passability memory.')
    if raw['last'] is not None:unpack(raw['last'])
    if raw['pending'] is not None and (type(raw['pending']) is not dict or set(raw['pending'])!={'action','data'}):raise Unsupported('Invalid pending action.')
    for key,mapping in raw['motors'].items():
        if type(key) is not str or type(mapping) is not dict or len(mapping)>16:raise Unsupported('Invalid motion hypothesis table.')
        for name,counts in mapping.items():
            if type(name) is not str or type(counts) is not dict or len(counts)>8 or any(type(k) is not str or len(k)>20 or type(v) is not int or not 1<=v<=10000000 for k,v in counts.items()):raise Unsupported('Invalid displacement evidence.')
    for mapping in raw['visits'].values():
        if type(mapping) is not dict or len(mapping)>256 or any(type(v) is not int or not 0<=v<=10000000 for v in mapping.values()):raise Unsupported('Invalid visit evidence.')
    for key,poses in raw['dynamics'].items():
        if type(key) is not str or type(poses) is not dict or len(poses)>16:raise Unsupported('Invalid pose dynamics.')
        for pose,acts in poses.items():
            if type(pose) is not str or type(acts) is not dict or len(acts)>16:raise Unsupported('Invalid conditional controls.')
            for name,counts in acts.items():
                if type(counts) is not dict or len(counts)>16 or any(type(k) is not str or len(k)>100 or type(v) is not int or not 1<=v<=10000000 for k,v in counts.items()):raise Unsupported('Invalid effect evidence.')
    scene_objects.validate_tracks(raw['tracks'])
    if type(raw['no_effects']) is not dict or len(raw['no_effects'])>128:raise Unsupported('Invalid no-effect evidence.')
    for by_pose in raw['no_effects'].values():
        if type(by_pose) is not dict or len(by_pose)>16:raise Unsupported('Invalid no-effect pose table.')
        for counts in by_pose.values():
            if type(counts) is not dict or len(counts)>16:raise Unsupported('Invalid no-effect counts.')
            for item in counts.values():
                if type(item) is not dict or set(item)!={'count','contexts'} or type(item['count']) is not int or not 1<=item['count']<=10000000 or type(item['contexts']) is not dict or len(item['contexts'])>16 or any(type(v) is not int or not 0<=v<=10000000 for v in item['contexts'].values()):raise Unsupported('Invalid no-effect context evidence.')
    if type(raw['support_evidence']) is not dict or len(raw['support_evidence'])>128:raise Unsupported('Invalid causal support table.')
    for v in raw['support_evidence'].values():
        if type(v) is not list or len(v)!=3 or any(type(x) is not int or not 0<=x<=10000000000 for x in v):raise Unsupported('Invalid causal support counts.')
    if type(raw['probe_visits']) is not dict or len(raw['probe_visits'])>512:raise Unsupported('Invalid abstract probe table.')
    for v in raw['probe_visits'].values():
        if type(v) is not dict or len(v)>16 or any(type(n) is not int or not 0<=n<=10000000 for n in v.values()):raise Unsupported('Invalid probe counts.')
    if type(raw['probe_edges']) is not dict or len(raw['probe_edges'])>512:raise Unsupported('Invalid exploratory control graph.')
    for arcs in raw['probe_edges'].values():
        if type(arcs) is not dict or len(arcs)>16:raise Unsupported('Invalid control transitions.')
        for ends in arcs.values():
            if type(ends) is not list or len(ends)>16 or any(type(k) is not str or len(k)>64 for k in ends):raise Unsupported('Invalid observed exploratory endpoints.')
    if raw['last_probe_actor'] is not None and (type(raw['last_probe_actor']) is not str or len(raw['last_probe_actor'])>64):raise Unsupported('Invalid last control identity.')
    if raw['last_probe_key'] is not None and (type(raw['last_probe_key']) is not str or len(raw['last_probe_key'])>64):raise Unsupported('Invalid last probe context.')
    if raw['intent'] is not None:
        intent=raw['intent']
        if type(intent) is not dict or set(intent)!={'target','kind','visits'} or type(intent['target']) is not list or len(intent['target'])!=2 or any(type(x) is not int or not 0<=x<64 for x in intent['target']) or intent['kind'] not in ['landmark-hypothesis','explicit-coordinate','explicit-object'] or type(intent['visits']) is not dict or len(intent['visits'])>256:raise Unsupported('Invalid explicit goal hypothesis.')
        if any(type(v) is not int or not 0<=v<=10000000 for v in intent['visits'].values()):raise Unsupported('Invalid intent evidence.')
    return raw


def movement(before,after):
    old=defaultdict(list);new=defaultdict(list)
    for x in before:old[x['signature']].append(x)
    for x in after:new[x['signature']].append(x)
    result=[]
    for key,values in old.items():
        if len(values)==len(new.get(key,[]))==1:
            a=values[0];b=new[key][0];result.append((key,a,b,b['x']-a['x'],b['y']-a['y']))
    return result

def local_context(g,item,memory):
    radius=max(item['w'],item['h'],1)
    for poses in memory['dynamics'].get(item['signature'],{}).values():
        for counts in poses.values():
            for value in counts:
                dx,dy,_=json.loads(value);radius=max(radius,abs(dx),abs(dy))
    radius=min(12,radius);cx=item['cx'];cy=item['cy']
    support={(item['y']+py,item['x']+px) for py,px in item['shape']}
    patch=[[(-1 if (y,x) in support else g[y][x]) if 0<=y<len(g) and 0<=x<len(g[0]) else -2
        for x in range(cx-radius,cx+radius+1)] for y in range(cy-radius,cy+radius+1)]
    return digest([patch,memory['context_revision']])[:24]


def learn(memory,g,items,level,animated,before_items=None):
    if memory['last'] is None or memory['pending'] is None:return
    old=unpack(memory['last']);before=before_items if before_items is not None else objects(old)[1];action=memory['pending'];name=action['action']
    moves=movement(before,items)
    ignored=set(memory['passable'])|{c for o in before if o['signature']==memory['controller'] for c in o.get('colors',[o['color']])}
    old_counts=Counter(v for row in old for v in row if v not in ignored)
    new_counts=Counter(v for row in g for v in row if v not in ignored)
    if any(new_counts[k]<v for k,v in old_counts.items()):
        # A disappearance/occlusion may change action preconditions. Revoke a
        # material-wide collision assumption instead of inventing a key rule.
        memory['collisions']={};memory['blocked_edges']=[];memory['context_revision']+=1
    # A level boundary is explicit context, not a globally learned wall rule.
    if level!=memory['last_level']:
        memory['collisions']={};memory['blocked_edges']=[];memory['goals_visited']={};memory['visits']={};memory['edges']={};memory['intent']=None;memory['probe_visits']={};memory['probe_edges']={}
    for key,a,b,dx,dy in moves:
        if action['data'] or a.get('kind')=='material-layer':continue
        evidence=memory['support_evidence'].setdefault(key,[0,0,0])
        if dx or dy or a['orientation']!=b['orientation']:
            evidence[0]+=scene_objects.motion_signal(a,b);evidence[1]+=1;evidence[2]+=int(bool(dx or dy))
        changed=dx or dy or a['orientation']!=b['orientation']
        if changed and abs(dx)<=16 and abs(dy)<=16:
            poses=memory['dynamics'].setdefault(key,{})
            if a['orientation'] not in poses and len(poses)>=16:
                memory['pruned_states']+=1;continue
            counts=poses.setdefault(a['orientation'],{}).setdefault(name,{})
            outcome=json.dumps([dx,dy,b['orientation']],separators=(',',':'));counts[outcome]=counts.get(outcome,0)+1
            if len(counts)>16:poses[a['orientation']].pop(name,None)
        elif not changed:
            by_pose=memory['no_effects'].setdefault(key,{})
            if a['orientation'] in by_pose or len(by_pose)<16:
                counts=by_pose.setdefault(a['orientation'],{});record=counts.setdefault(name,dict(count=0,contexts={}))
                record['count']+=1;record['contexts'][local_context(old,a,memory)]=memory['turn']
                while len(record['contexts'])>16:record['contexts'].pop(next(iter(record['contexts'])))
        if dx or dy:
            if abs(dx)>16 or abs(dy)>16:continue
            motor=memory['motors'].setdefault(key,{});counts=motor.setdefault(name,{})
            encoded=str(dx)+','+str(dy);counts[encoded]=counts.get(encoded,0)+1
            if len(counts)>8:memory['motors'].pop(key,None)
        if key==memory['controller']:
            if dx or dy:
                # The old occupied cell is now visible; its revealed material
                # can be admitted as passable. Never assume a particular color.
                new_support={(b['y']+py,b['x']+px) for py,px in b['shape']}
                for py,px in a['shape']:
                    y=a['y']+py;x=a['x']+px
                    if (y,x) not in new_support and 0<=y<len(g) and 0<=x<len(g[0]):
                        c=g[y][x]
                        if c not in memory['passable']:memory['passable'].append(c)
            elif key not in animated:
                mapping=memory['dynamics'].get(key,{}).get(a['orientation'],{}).get(name,{})
                if len(mapping)==1:
                    sx,sy,_=json.loads(next(iter(mapping)));x=a['cx']+sx;y=a['cy']+sy
                    if sx==sy==0:continue
                    if 0<=x<len(old[0]) and 0<=y<len(old):
                        color=old[y][x];locations=memory['collisions'].setdefault(str(color),[])
                        if [x,y] not in locations:locations.append([x,y])
                        edge=[a['x'],a['y'],a['orientation'],name]
                        if edge not in memory['blocked_edges']:memory['blocked_edges'].append(edge)
    # A disputed effect remains a version space; only uniquely observed
    # displacement models can be used for simulated motion.
    if len(memory['motors'])>128:memory['motors']={k:memory['motors'][k] for k in sorted(memory['motors'])[:128]}
    if len(memory['dynamics'])>128:memory['dynamics']={k:memory['dynamics'][k] for k in sorted(memory['dynamics'])[:128]}
    if len(memory['support_evidence'])>128:memory['support_evidence']={k:memory['support_evidence'][k] for k in sorted(memory['support_evidence'])[:128]}
    if len(memory['no_effects'])>128:memory['no_effects']={k:memory['no_effects'][k] for k in sorted(memory['no_effects'])[:128]}


def controller(memory,items,goal):
    candidates=[];fit_by_key={}
    for item in items:
        if item.get('kind')=='material-layer':continue
        motor=memory['motors'].get(item['signature'],{})
        dynamics=memory['dynamics'].get(item['signature'],{})
        if goal and goal['subject']['color'] not in item.get('colors',[item['color']]):continue
        confidence=sum(sum(v.values()) for acts in dynamics.values() for v in acts.values() if len(v)==1)
        supported=sum(len(v)==1 for acts in dynamics.values() for v in acts.values())
        directions={d for acts in dynamics.values() for v in acts.values() if len(v)==1 for d in v}
        # Motion identical under every offered control can be exogenous (a
        # clock/camera), not evidence that the object is controlled.
        if not goal:
            effects=[]
            nulls=memory['no_effects'].get(item['signature'],{})
            for pose in set(dynamics)|set(nulls):
                acts=dynamics.get(pose,{})
                for name in set(acts)|set(nulls.get(pose,{})):
                    counts=acts.get(name,{})
                    effects.append(max(counts,key=counts.get) if counts else json.dumps([0,0,pose],separators=(',',':')))
            if len(effects)>=3 and Counter(effects).most_common(1)[0][1]>=max(3,len(effects)*.8):continue
        signal,samples,translations=memory['support_evidence'].get(item['signature'],[0,0,0])
        active=consistent=0
        for pose,acts in dynamics.items():
            for counts in acts.values():
                moving=any((lambda e:e[0]!=0 or e[1]!=0 or e[2]!=pose)(json.loads(e)) for e in counts)
                if moving:
                    active+=sum(counts.values())
                    if len(counts)==1:consistent+=sum(counts.values())
        # A point on a rotating body may appear to move strongly while its
        # pose-free action model contradicts itself. Prefer predictive support
        # over the magnitude of such fragment motion.
        quality=(signal/max(1,samples))*(consistent/max(1,active))**2
        fit_by_key[item['signature']]=(consistent/max(1,active),active)
        mass=sum(o['area'] for o in items if o['color']==item['color'] and o.get('kind')!='compound')
        whole_color=mass==item['area']
        if supported and samples and quality>0:candidates.append(((quality,whole_color,len(directions),supported,confidence),item))
    if not candidates:return None
    # A predictively adequate complete support explains its own fragments too.
    # Keeping the larger rigid hypothesis avoids oscillating between equivalent
    # moving pixels and forgetting pose geometry on each switch.
    admitted=[]
    for score,item in candidates:
        support={(item['y']+y,item['x']+x) for y,x in item['shape']};dominated=False
        for other_score,other in candidates:
            fit,n=fit_by_key[other['signature']]
            if other['kind']!='compound' or other['area']<=item['area'] or fit<.85 or n<4:continue
            whole={(other['y']+y,other['x']+x) for y,x in other['shape']}
            if support<whole:dominated=True;break
        if not dominated:admitted.append((score,item))
    candidates=admitted
    if not candidates:return None
    candidates.sort(key=lambda x:x[0],reverse=True)
    prior=next((pair for pair in candidates if pair[1]['signature']==memory['controller']),None)
    if prior and fit_by_key[prior[1]['signature']][0]>=.7 and prior[0][0]>=candidates[0][0][0]*.5:
        if sum(o['signature']==prior[1]['signature'] for o in items)==1:return prior[1]
    if len(candidates)>1 and candidates[0][0]==candidates[1][0]:return None
    chosen=candidates[0][1]
    if sum(x['signature']==chosen['signature'] for x in items)!=1:return None
    return chosen


def targets(memory,items,actor,goal,g):
    if goal:
        target=goal['target']
        if 'x' in target:return [(target['x'],target['y'],'explicit-coordinate')]
        return [(o['cx'],o['cy'],'explicit-object') for o in items if o['color']==target['color'] and o['signature']!=actor['signature']]
    # A disclosed prior, not an inferred semantic role: inspect small visible
    # landmarks rather than assigning meaning to named colors or action IDs.
    # A material with even one observed collision is a poor speculative
    # destination. This does not yet make every cell of that material a wall:
    # navigation still needs repeated evidence for that stronger assumption.
    blocked={int(k) for k,v in memory['collisions'].items() if v and int(k) not in memory['passable']}
    actor_support={(actor['y']+py,actor['x']+px) for py,px in actor['shape']}
    candidates=[o for o in items if o['signature']!=actor['signature'] and o['color'] not in blocked
        and o['color'] not in memory['passable'] and o['signature'] not in memory['motors']
        and o.get('kind')!='material-layer'
        and not {(o['y']+py,o['x']+px) for py,px in o['shape']}<=actor_support
        and o['area']<=max(1,len(g)*len(g[0])//8)]
    candidates.sort(key=lambda o:(memory['goals_visited'].get(str([o['cx'],o['cy']]),0),o['area'],abs(o['cx']-actor['cx'])+abs(o['cy']-actor['cy']),o['signature']))
    return [(o['cx'],o['cy'],'landmark-hypothesis') for o in candidates[:16]]


def goal_region(target,kind,items):
    gx,gy=target
    if kind=='explicit-coordinate':return {(gx,gy)}
    region={(o['x']+px,o['y']+py) for o in items if (o['cx'],o['cy'])==(gx,gy) for py,px in o['shape']}
    return region or {(gx,gy)}

def navigation(memory,g,actor,goals,actions,items=None):
    mappings=memory['dynamics'].get(actor['signature'],{});moves={}
    allowed={a['action'] for a in actions if not a['complex']}
    for pose,acts in mappings.items():
        moves[pose]=[]
        for name,counts in acts.items():
            if name not in allowed or len(counts)!=1:continue
            dx,dy,new_pose=json.loads(next(iter(counts)))
            if dx or dy or new_pose!=pose:moves[pose].append((name,dx,dy,new_pose))
    if not moves or not goals:return None
    blocked={int(k) for k,v in memory['collisions'].items() if len(v)>=2 and int(k) not in memory['passable']}
    banned={tuple(e) for e in memory['blocked_edges']};start=(actor['x'],actor['y'],actor['orientation']);best_plan=None
    shapes=memory['poses'].get(actor['signature'],{})
    for gx,gy,kind in goals:
        region=goal_region((gx,gy),kind,items or [])
        # Reaching an unconfirmed landmark does not mean winning the game.
        if any((start[0]+px,start[1]+py) in region for py,px in shapes.get(start[2],actor['shape'])):continue
        queue=[(0,0,start,[])];seen={start:0};expanded=0
        while queue and expanded<4096:
            _,cost,pos,path=heapq.heappop(queue);expanded+=1
            if any((pos[0]+px,pos[1]+py) in region for py,px in shapes.get(pos[2],actor['shape'])):
                penalty=memory['goals_visited'].get(str([gx,gy]),0)*1000 if kind=='landmark-hypothesis' else 0
                candidate=(cost+penalty,path,kind,(gx,gy))
                if best_plan is None or candidate[0]<best_plan[0]:best_plan=candidate
                break
            x,y,pose=pos
            for name,dx,dy,new_pose in moves.get(pose,[]):
                if new_pose not in shapes:continue
                nx=x+dx;ny=y+dy;footprint=[(ny+py,nx+px) for py,px in shapes.get(new_pose,actor['shape'])]
                if not all(0<=xx<len(g[0]) and 0<=yy<len(g) for yy,xx in footprint) or (x,y,pose,name) in banned:continue
                if any(g[yy][xx] in blocked and (xx,yy) not in region for yy,xx in footprint):continue
                penalty=1 if all(g[yy][xx] in memory['passable'] or g[yy][xx]==actor['color'] for yy,xx in footprint) else 3
                nc=cost+penalty
                if nc<seen.get((nx,ny,new_pose),10**9):
                    seen[nx,ny,new_pose]=nc;distance=min(abs(xx-nx)+abs(yy-ny) for xx,yy in region)
                    heapq.heappush(queue,(nc+distance,nc,(nx,ny,new_pose),path+[name]))
        if best_plan and kind!='landmark-hypothesis':break
    if best_plan and best_plan[1]:return best_plan[1][0],dict(plan=best_plan[1],target=list(best_plan[3]),goal_kind=best_plan[2],model='observed-object-translation-and-collisions')
    return None


def options(actions,items,g):
    result=[]
    for a in actions:
        if not a['complex']:result.append(dict(action=a['action'],data={}));continue
        points=set()
        for o in items[:96]:
            points.add((o['cx'],o['cy']))
            points.add((o['x'],o['y']))
        if not points:points.add((len(g[0])//2,len(g)//2))
        for x,y in sorted(points)[:128]:result.append(dict(action=a['action'],data=dict(x=x,y=y)))
    return result


def step(task):
    frames,actions,goal=read(task);g=frames[-1]
    domain=digest([len(g),len(g[0]),goal,task.get('episode')])
    memory=restore(task,domain);before_items=memory['tracks'];items=before_items
    previous=unpack(memory['last']) if memory['last'] is not None else frames[0]
    animated=set();motion_events=Counter();changed_cells=0
    for frame in frames:
        memory['chain']=digest([memory['chain'],pack(frame)])
        changed_cells+=sum(a!=b for r,s in zip(previous,frame) for a,b in zip(r,s))
        _,new_items=scene_objects.track(frame,items)
        for key,a,b,dx,dy in movement(items,new_items):
            if dx or dy or a['orientation']!=b['orientation']:animated.add(key);motion_events[key]+=1
        previous=frame;items=new_items
    memory['animation_events']=dict(changed_cells=changed_cells,moving_signatures=dict(motion_events),frames=len(frames))
    memory['frames_processed']+=len(frames);memory['observations_processed']+=1
    learn(memory,g,items,task['levels_completed'],animated,before_items)
    memory['tracks']=items
    actor=controller(memory,items,goal)
    if actor:
        if memory['controller']!=actor['signature']:
            # Traversability is relative to the controlled object. Evidence
            # gathered while a moving display was a candidate cannot transfer.
            memory['passable']=[];memory['collisions']={};memory['blocked_edges']=[];memory['intent']=None
        memory['controller']=actor['signature']
    # Cache geometry only for a currently selected body. Full current scene
    # support is still retained in tracks. Huge background masks at many poses
    # cannot consume all memory before useful object models are learned.
    selected_key=actor['signature'] if actor else memory['controller']
    for key in list(memory['poses']):
        if key!=selected_key:memory['poses'].pop(key);memory['pruned_states']+=1
    for o in before_items+items:
        if o['signature']!=selected_key:continue
        poses=memory['poses'].setdefault(o['signature'],{})
        if len(poses)<16 or o['orientation'] in poses:poses[o['orientation']]=o['shape']
    visible_key=digest([pack(g),task['levels_completed']])[:24]
    action_key=lambda a:json.dumps(a,sort_keys=True,separators=(',',':'))
    if memory['last'] is not None and memory['pending'] is not None:
        previous=digest([memory['last'],memory['last_level']])[:24];encoded=action_key(memory['pending'])
        memory['visits'].setdefault(previous,{})[encoded]=memory['visits'].get(previous,{}).get(encoded,0)+1
        values=memory['edges'].setdefault(previous,{}).setdefault(encoded,[])
        if visible_key not in values:values.append(visible_key)
        if memory['last_probe_key'] is not None and not memory['pending']['data']:
            counts=memory['probe_visits'].setdefault(memory['last_probe_key'],{});name=memory['pending']['action'];counts[name]=counts.get(name,0)+1
    probe_key=None
    if actor:
        # This abstraction governs repeated experimental probes only. The full
        # visible-state graph remains intact; it is not asserted to be a full
        # physical state representation. A moving display with constant mass
        # therefore cannot force endless identical control experiments.
        probe_key=digest([actor['signature'],actor['x'],actor['y'],actor['orientation'],
            sorted(Counter(v for row in g for v in row).items()),memory['context_revision'],task['levels_completed']])[:24]
        if memory['last_probe_key'] is not None and memory['last_probe_actor']==actor['signature'] and memory['pending'] is not None and not memory['pending']['data']:
            arcs=memory['probe_edges'].setdefault(memory['last_probe_key'],{});ends=arcs.setdefault(action_key(memory['pending']),[])
            if probe_key not in ends and len(ends)<16:ends.append(probe_key)
    if actor:
        location=str([actor['cx'],actor['cy']]);memory['goals_visited'][location]=memory['goals_visited'].get(location,0)+1
    choices=options(actions,items,g)
    if not choices:raise Unsupported('No supported visible action candidates.')
    visited=memory['visits'].get(visible_key,{})
    local_probes=memory['probe_visits'].get(probe_key,{})
    total=Counter()
    for counts in memory['visits'].values():total.update(counts)
    simple=[a for a in choices if not a['data']]
    context=local_context(g,actor,memory) if actor else None
    # First learn the meaning of the offered controls; their names carry no
    # directional semantics. Unknown reset/interaction actions are not assumed.
    untested=[a for a in simple if sum(n for k,n in total.items() if json.loads(k)['action']==a['action'])==0
        or actor is not None and a['action'] not in memory['dynamics'].get(actor['signature'],{}).get(actor['orientation'],{})
        and context not in memory['no_effects'].get(actor['signature'],{}).get(actor['orientation'],{}).get(a['action'],{}).get('contexts',{})
        and local_probes.get(a['action'],0)==0]
    selected=reason=proof=None
    if untested:selected=min(untested,key=action_key);reason='action-effect-probe'
    elif actor:
        goals=targets(memory,items,actor,goal,g);intent=memory['intent']
        if intent:
            position=str([actor['x'],actor['y'],actor['orientation']]);intent['visits'][position]=intent['visits'].get(position,0)+1
            if len(intent['visits'])>256:intent['visits'].pop(next(iter(intent['visits'])))
            matching=[t for t in goals if list(t[:2])==intent['target'] and t[2]==intent['kind']]
            region=goal_region(tuple(intent['target']),intent['kind'],items)
            reached=any((actor['x']+px,actor['y']+py) in region for py,px in actor['shape'])
            if not matching or reached or intent['visits'][position]>3:
                label=str(intent['target']);memory['goals_visited'][label]=memory['goals_visited'].get(label,0)+8
                memory['intent']=None;memory['goal_revisions']+=1
            else:goals=matching
        planned=navigation(memory,g,actor,goals,actions,items)
        if planned:
            selected=dict(action=planned[0],data={});reason='learned-model-plan';proof=planned[1]
            if memory['intent'] is None:memory['intent']=dict(target=proof['target'],kind=proof['goal_kind'],visits={})
    if selected is None:
        untried=[a for a in choices if (local_probes.get(a['action'],0) if probe_key and not a['data'] else visited.get(action_key(a),0))==0]
        if untried:selected=min(untried,key=lambda a:(total[action_key(a)],action_key(a)));reason='visible-state-exploration'
        else:
            abstract=probe_key is not None and all(not a['data'] for a in choices)
            start=probe_key if abstract else visible_key;graph=memory['probe_edges'] if abstract else memory['edges']
            todo=deque([(start,[])]);seen={start};path=None
            while todo and len(seen)<=512:
                node,route=todo.popleft()
                visited_actions=memory['probe_visits'].get(node,{}) if abstract else memory['visits'].get(node,{})
                if node!=start and len(visited_actions)<len(choices):path=route;break
                for encoded,ends in sorted(graph.get(node,{}).items()):
                    if len(ends)==1 and ends[0] not in seen:seen.add(ends[0]);todo.append((ends[0],route+[encoded]))
            if path:
                candidate=json.loads(path[0])
                if candidate in choices:selected=candidate;reason='observed-control-path-to-frontier' if abstract else 'observed-path-to-frontier'
            if selected is None:selected=min(choices,key=lambda a:((local_probes.get(a['action'],0) if probe_key and not a['data'] else visited.get(action_key(a),0)),total[action_key(a)],action_key(a)));reason='uncertain-revisit'
    ended=task['state'] in {'WIN','GAME_OVER'}
    if ended:selected=None;reason='terminal-visible-state'
    memory['pending']=selected;memory['last']=pack(g);memory['last_level']=task['levels_completed'];memory['turn']+=1;memory['last_probe_key']=probe_key;memory['last_probe_actor']=actor['signature'] if actor else None
    for field in ['visits','edges','goals_visited','probe_visits','probe_edges']:
        while len(memory[field])>512:memory[field].pop(next(iter(memory[field])));memory['pruned_states']+=1
    memory['blocked_edges']=memory['blocked_edges'][-1024:]
    exported=dict(memory,checksum=digest(memory))
    if len(json.dumps(exported))>MAX_MEMORY:raise Unsupported('Compact-memory limit reached; explicitly reset or choose a smaller observation model.')
    return selected,exported,dict(status='terminal' if ended else 'model-based-control',reason=reason,
        goal_known=goal is not None,goal_origin='explicit-caller' if goal else 'unconfirmed-visible-landmark-prior',
        controlled_object=actor,planning=proof,observations_processed=memory['observations_processed'],frames_processed=memory['frames_processed'],
        compact_memory_characters=len(json.dumps(exported)),raw_history_required=False,animation_digest=memory['chain'],
        animation_events=memory['animation_events'],neural=False,success_claimed=task['state']=='WIN',
        goal_hypothesis=memory['intent'],goal_revisions=memory['goal_revisions'],
        controllability_support=memory['support_evidence'].get(actor['signature']) if actor else None,
        assumptions='Appearance identities, controllability, translation effects, collisions and unknown landmark goals are empirical hypotheses, not a complete physics or goal model.')


def reply(task,history=None):
    try:
        if task.get('agent_state') is None and history:
            memory=None
            for role,old in history:
                if role=='assistant' and memory is not None:
                    if type(old) is dict and set(old)=={'action','data'}:
                        memory['pending']=old;raw=dict(memory);raw.pop('checksum');memory['checksum']=digest(raw)
                    continue
                if role!='user':continue
                _,memory,_=step(dict(old,agent_state=memory) if memory is not None else old)
            if memory is not None:task=dict(task,agent_state=memory)
        action,memory,proof=step(task)
    except (Unsupported,KeyError,TypeError,ValueError,AttributeError,IndexError,RecursionError,OverflowError) as exc:
        return dict(route='chat/environment-clarify',response='Please clarify the visible game task: '+str(exc),sources=[],environment_reasoning=dict(status='unsupported-or-uncertain',neural=False))
    if action is None:return dict(route='chat/environment-terminal',response='The visible environment has ended.',sources=[],agent_state=memory,environment_reasoning=proof)
    return dict(route='chat/environment-plan' if proof['planning'] else 'chat/environment-explore',response=json.dumps(action,separators=(',',':')),sources=[],agent_state=memory,
        environment_reasoning=proof,verification=dict(status='visible-action-checked',check='Action is offered and coordinates are within the visible grid; model-based plan is an empirical hypothesis.'))
