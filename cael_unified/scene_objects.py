"""Bounded geometric object hypotheses, including raster pose variation.

No color names, game names, action meanings or renderer implementations. The
matching rule is an explicit appearance prior, not proof of physical identity.
"""
from collections import Counter,defaultdict
import hashlib,json
from .grid_induction import components,Unsupported

MAX_OBJECTS=96

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def variants(shape):
    result=[]
    for flip in (1,-1):
        points=[(y,x*flip) for y,x in shape]
        for _ in range(4):
            my=min(y for y,x in points);mx=min(x for y,x in points)
            result.append(tuple(sorted((y-my,x-mx) for y,x in points)))
            points=[(x,-y) for y,x in points]
    return result

def objects(g):
    background=Counter(v for row in g for v in row).most_common(1)[0][0];found=[]
    for part in components(g,background):
        ys=[p[0] for p in part];xs=[p[1] for p in part];y=min(ys);x=min(xs)
        # A bounding-box corner may be empty for a rotated/sparse object. Its
        # material is defined by actual occupied support, never that corner.
        shape=tuple(sorted((py-y,px-x) for py,px in part));py,px=min(part);color=g[py][px]
        found.append(dict(signature=digest([color,min(variants(shape))])[:20],orientation=digest(shape)[:12],shape=[list(p) for p in shape],color=color,x=x,y=y,
            w=max(xs)-x+1,h=max(ys)-y+1,area=len(part),cx=(min(xs)+max(xs))//2,cy=(min(ys)+max(ys))//2))
    return background,found

def compound_candidates(g,parts):
    """Additional rare-material connected hypotheses, never replacements.

    A multi-color region is tracked as one body only if its *colored* shape
    persists. Touching an unrelated goal can form a candidate but cannot supply
    persistent motion evidence once those parts separate.
    """
    mass=Counter(v for row in g for v in row);cap=max(4,len(g)*len(g[0])//8)
    eligible=[p for p in parts if mass[p['color']]<=cap and p.get('kind')!='material-layer']
    occupied={}
    for i,p in enumerate(eligible):
        for y,x in p['shape']:occupied[p['y']+y,p['x']+x]=i
    neighbors={i:set() for i in range(len(eligible))}
    for (y,x),i in occupied.items():
        for dy,dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            j=occupied.get((y+dy,x+dx))
            if j is not None and j!=i:neighbors[i].add(j)
    seen=set();result=[];clusters=[]
    for i in neighbors:
        if i in seen:continue
        todo=[i];seen.add(i);cluster=[]
        while todo:
            j=todo.pop();cluster.append(eligible[j])
            for k in neighbors[j]-seen:seen.add(k);todo.append(k)
        clusters.append(cluster)
    # Raster silhouettes can contain disconnected islands. A compact full
    # color-support hypothesis retains their relative geometry and must itself
    # earn stable action-prediction evidence; parts are still retained too.
    by=defaultdict(list)
    for p in eligible:by[p['color']].append(p)
    for group in by.values():
        if not 2<=len(group)<=8:continue
        y0=min(p['y'] for p in group);x0=min(p['x'] for p in group)
        y1=max(p['y']+p['h'] for p in group);x1=max(p['x']+p['w'] for p in group)
        if sum(p['area'] for p in group)/((y1-y0)*(x1-x0))<.15:continue
        cluster=list(group)
        cluster.extend(p for p in eligible if p not in group and p['x']>=x0 and p['y']>=y0 and p['x']+p['w']<=x1 and p['y']+p['h']<=y1)
        clusters.append(cluster)
    identifiers=set()
    for cluster in clusters:
        colors=sorted({p['color'] for p in cluster});area=sum(p['area'] for p in cluster)
        if len(cluster)<2 or len(colors)>8 or area>cap:continue
        y=min(p['y'] for p in cluster);x=min(p['x'] for p in cluster)
        colored=[(p['y']+py-y,p['x']+px-x,p['color']) for p in cluster for py,px in p['shape']]
        versions=[]
        for flip in [1,-1]:
            points=[(py,px*flip,c) for py,px,c in colored]
            for _ in range(4):
                my=min(py for py,px,c in points);mx=min(px for py,px,c in points)
                versions.append(tuple(sorted((py-my,px-mx,c) for py,px,c in points)));points=[(px,-py,c) for py,px,c in points]
        h=max(py for py,px,c in colored)+1;w=max(px for py,px,c in colored)+1
        dominant=Counter(c for py,px,c in colored).most_common(1)[0][0]
        support=tuple((py,px) for py,px,c in colored)
        histogram=sorted(Counter(c for py,px,c in colored).items())
        # Shape and material mass identify a body hypothesis; the full colored
        # appearance still distinguishes its pose. A lighting highlight moving
        # across the same support must not create an unrelated physical body.
        signature=digest(['compound-support',histogram,min(variants(support))])[:20]
        if signature in identifiers:continue
        identifiers.add(signature)
        result.append(dict(signature=signature,orientation=digest(sorted(colored))[:12],shape=[list(p) for p in sorted((py,px) for py,px,c in colored)],
            colors=colors,kind='compound',color=dominant,x=x,y=y,w=w,h=h,area=area,cx=x+(w-1)//2,cy=y+(h-1)//2))
    return result

def material_layers(parts):
    """Retain a repeated palette material as one explicit support layer.

    The raw pixels and the number of original connected parts are preserved.
    The layer is not asserted to be an independently controllable body.
    """
    by=defaultdict(list)
    for p in parts:by[p['color']].append(p)
    result=[]
    for color,group in by.items():
        if len(group)<=8:
            for p in group:p.update(colors=[color],kind='single-material',parts_count=1)
            result.extend(group);continue
        y=min(p['y'] for p in group);x=min(p['x'] for p in group)
        shape=sorted((p['y']+py-y,p['x']+px-x) for p in group for py,px in p['shape'])
        h=max(py for py,px in shape)+1;w=max(px for py,px in shape)+1
        result.append(dict(signature=digest(['material',color,min(variants(shape))])[:20],orientation=digest(shape)[:12],shape=[list(p) for p in shape],
            color=color,colors=[color],kind='material-layer',parts_count=len(group),x=x,y=y,w=w,h=h,area=len(shape),cx=x+(w-1)//2,cy=y+(h-1)//2))
    return result

def normalized(shape):
    # Coarse shape comparison is used only for an unambiguous adjacent-frame
    # match. Exact masks, orientations and all observations remain retained.
    h=max(y for y,x in shape)+1;w=max(x for y,x in shape)+1
    return {(min(11,y*12//h),min(11,x*12//w)) for y,x in shape}

def similarity(a,b):
    if a['color']!=b['color'] or a.get('colors',[a['color']])!=b.get('colors',[b['color']]):return 0.0
    if a.get('kind')!=b.get('kind') or a.get('kind')=='compound':return 0.0
    if max(a['area'],b['area'])>min(a['area'],b['area'])*1.45:return 0.0
    if max(a['w'],a['h'])>max(b['w'],b['h'])*1.6 or max(b['w'],b['h'])>max(a['w'],a['h'])*1.6:return 0.0
    first=normalized(a['shape']);best=0.
    for other in variants(b['shape']):
        second=normalized(other);best=max(best,len(first&second)/len(first|second))
    return best

def track(g,previous):
    background,current=objects(g)
    current=material_layers(current)
    compounds=compound_candidates(g,current)
    for item in compounds:item['parts_count']=1
    current+=compounds
    if len(current)>MAX_OBJECTS:raise Unsupported('Scene object-candidate limit reached; no objects were silently discarded.')
    old=defaultdict(list);new=defaultdict(list)
    for i,item in enumerate(previous):old[item['color']].append(i)
    for i,item in enumerate(current):new[item['color']].append(i)
    used=set();matches={}
    # Preserve exact unique appearances before considering raster tolerance.
    for i,item in enumerate(current):
        same=[j for j,prior in enumerate(previous) if prior.get('raw_signature',prior['signature'])==item['signature']]
        duplicate=sum(x['signature']==item['signature'] for x in current)
        if len(same)==duplicate==1:matches[i]=(same[0],1.0);used.add(same[0])
    for color,indices in new.items():
        for i in indices:
            if i in matches:continue
            scores=sorted([(similarity(previous[j],current[i]),j) for j in old[color] if j not in used],reverse=True)
            if not scores or scores[0][0]<.58:continue
            score,j=scores[0]
            if len(scores)>1 and score-scores[1][0]<.15:continue
            competitors=[similarity(previous[j],current[k]) for k in indices if k!=i and k not in matches]
            if competitors and score-max(competitors)<.15:continue
            matches[i]=(j,score);used.add(j)
    for i,item in enumerate(current):
        item['raw_signature']=item['signature']
        if i in matches:
            j,confidence=matches[i];item['signature']=previous[j]['signature'];item['appearance_match_milli']=round(confidence*1000)
        else:item['appearance_match_milli']=1000
    return background,current

def validate_tracks(items):
    if type(items) is not list or len(items)>MAX_OBJECTS:raise Unsupported('Invalid explicit scene tracks.')
    fields={'signature','orientation','shape','color','x','y','w','h','area','cx','cy','raw_signature','appearance_match_milli','colors','kind','parts_count'}
    for item in items:
        if type(item) is not dict or set(item)!=fields:raise Unsupported('Incomplete scene track.')
        if any(type(item[k]) is not str or len(item[k])>64 for k in ['signature','orientation','raw_signature']):raise Unsupported('Invalid scene identity.')
        if item['kind'] not in ['single-material','compound','material-layer'] or type(item['colors']) is not list or not 1<=len(item['colors'])<=8 or any(type(c) is not int or not 0<=c<256 for c in item['colors']):raise Unsupported('Invalid compound materials.')
        if any(type(item[k]) is not int or not 0<=item[k]<=4096 for k in fields-{'signature','orientation','raw_signature','shape','colors','kind'}):raise Unsupported('Invalid scene geometry.')
        if not 0<=item['color']<256 or not 1<=item['area']<=4096 or not 1<=item['w']<=64 or not 1<=item['h']<=64:raise Unsupported('Invalid scene size/color.')
        shape=item['shape']
        if type(shape) is not list or len(shape)!=item['area'] or any(type(p) is not list or len(p)!=2 or any(type(v) is not int or not 0<=v<64 for v in p) for p in shape):raise Unsupported('Invalid scene support.')
        if len({tuple(p) for p in shape})!=len(shape) or any(y>=item['h'] or x>=item['w'] for y,x in shape) or item['x']+item['w']>64 or item['y']+item['h']>64 or item['appearance_match_milli']>1000:raise Unsupported('Invalid scene bounds/identity confidence.')

def motion_signal(a,b):
    before={(a['y']+y,a['x']+x) for y,x in a['shape']}
    after={(b['y']+y,b['x']+x) for y,x in b['shape']}
    return round(1000*len(before^after)/max(1,len(before)+len(after)))
