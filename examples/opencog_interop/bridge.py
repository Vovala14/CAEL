"""Optional data-only CAEL 0.4 -> AtomSpace research bridge.

CAEL is an external, separately licensed dependency. No CAEL/OpenCog engine
source or model is distributed here. No model/Atomese-generated code runs.
"""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys

FORMAT='cael-atomspace-data-v1'
NODES={'ConceptNode','PredicateNode','NumberNode'}
LINKS={'ListLink','EvaluationLink'}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def engines(root):
    root=Path(root).resolve()
    for name in ['cael_unified/reasoning_world.py','cael_unified/reasoning_logic.py','models/cael-reasoning-v1/model.json']:
        if not (root/name).is_file():raise ValueError('Missing CAEL 0.4 dependency file: '+name)
    existing=sys.modules.get('cael_unified')
    if existing and Path(existing.__file__).resolve().parent!=root/'cael_unified':raise ValueError('A different CAEL runtime is already imported.')
    sys.path.insert(0,str(root))
    package=importlib.import_module('cael_unified')
    if package.__version__!='0.4.0':raise ValueError('This prototype targets CAEL 0.4.0.')
    world=importlib.import_module('cael_unified.reasoning_world')
    logic=importlib.import_module('cael_unified.reasoning_logic')
    path=root/'models/cael-reasoning-v1/model.json'
    model=json.loads(path.read_text(encoding='utf-8'))
    return world.WorldCA,logic.LogicCA,logic.Unparsed,model,dict(version=package.__version__,model_sha256=digest(path),source_sha256={n:digest(root/n) for n in ['cael_unified/reasoning_world.py','cael_unified/reasoning_logic.py']})


def text(value):
    if type(value) is not str or not 1<=len(value)<=40000 or any(ord(c)<32 and c not in '\n\r\t' for c in value):raise ValueError('Expected bounded literal text.')
    return value


def export_episode(spec,backend):
    if type(spec) is not dict or set(spec)!={'id','events','logic','queries'}:raise ValueError('Use id, events, logic and queries only.')
    episode=text(spec['id'])
    if len(episode)>100:raise ValueError('Episode ID too long.')
    for key in ['events','queries']:
        if type(spec[key]) is not list or len(spec[key])>128:raise ValueError('Episode list exceeds bounds.')
    for event in spec['events']:text(event)
    context=text(spec['logic']) if spec['logic'] else ''
    World,Logic,Unparsed,model,identity=backend;world=World(model)
    result=dict(format=FORMAT,id=episode,engine=identity,events=[],snapshots=[],logic_claims=[],queries=[],limitations=['CAEL bounded premise grammar; no arbitrary English understanding.','Claims and proofs are relative to this declared episode, not verified external truth.','Bridge does not run OpenCog inference or train either engine.'])
    accepted=[]
    for index,event in enumerate(spec['events'],1):
        proposed=copy.deepcopy(world)
        try:proposed.apply(proposed.event(event),index)
        except Unparsed as exc:result['events'].append(dict(index=index,text=event,accepted=False,error=str(exc)))
        else:
            world=proposed;accepted.append((index,event));result['events'].append(dict(index=index,text=event,accepted=True,error=None))
        cells=[]
        for name,cell in sorted(world.cells.items()):
            locations=sorted(cell.locations)
            cells.append(dict(entity=name,kind=cell.kind,possible_locations=locations,location_status='known' if len(locations)==1 else 'one_of' if locations else 'unknown',excluded_locations=sorted(cell.excluded),holder=cell.owner,support=sorted(cell.support)))
        result['snapshots'].append(dict(step=index,accepted=result['events'][-1]['accepted'],cells=cells))
    if context:
        active,proofs,depths=Logic(model).close(context)
        for entity,prop,negative in sorted(active):
            atom=(entity,prop,negative)
            result['logic_claims'].append(dict(entity=entity,property=prop,polarity='negative' if negative else 'positive',support=sorted(proofs[atom]),depth=depths[atom]))
    for query in spec['queries']:
        if type(query) is not dict or set(query)!={'engine','text'} or query['engine'] not in ('world','logic'):raise ValueError('Query engine must be world or logic.')
        q=text(query['text'])
        try:
            if query['engine']=='world':
                reply=World(model).query('. '.join(e for _,e in accepted),q)
                reply=dict(reply,support=[accepted[n-1][0] for n in reply['support']])
            else:reply=Logic(model).query(context,q)
        except Unparsed as exc:result['queries'].append(dict(engine=query['engine'],text=q,status='unsupported',answer=None,support=[],error=str(exc)))
        else:
            answer=reply['answer'];status=reply.get('status') or ('unknown' if answer in ('unknown','maybe') else 'answered')
            result['queries'].append(dict(engine=query['engine'],text=q,status=status,answer=answer,support=reply['support'],depth=reply['depth']))
    result['input_sha256']=hashlib.sha256(json.dumps(spec,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return result


def node(kind,value):return dict(type=kind,name=str(value))
def link(kind,*outgoing):return dict(type=kind,outgoing=list(outgoing))
def concept(value):return node('ConceptNode',value)
def claim(predicate,*args):return link('EvaluationLink',node('PredicateNode','cael:'+predicate),link('ListLink',*args))


def atom_graph(result):
    if result.get('format')!=FORMAT:raise ValueError('Unsupported bridge format.')
    # A human-readable label can repeat; input-specific scope prevents two
    # different episodes with the same label from sharing mutable facts.
    episode=concept('cael:episode:'+result['input_sha256']);roots=[claim('episode-label',episode,concept(result['id']))]
    for snapshot in result['snapshots']:
        step=node('NumberNode',snapshot['step'])
        for cell in snapshot['cells']:
            entity=concept(cell['entity'])
            facts=[claim('location-status',episode,step,entity,concept(cell['location_status']))]
            facts += [claim('possible-location',episode,step,entity,concept(loc)) for loc in cell['possible_locations']]
            facts += [claim('excluded-location',episode,step,entity,concept(loc)) for loc in cell['excluded_locations']]
            # Null is an explicit engine-state marker, never converted to a
            # negated fact about any named owner.
            facts += [claim('holder',episode,step,entity,concept(cell['holder'] if cell['holder'] is not None else 'cael:no-recorded-holder'))]
            roots.extend(facts)
            roots += [claim('event-support',fact,node('NumberNode',source)) for fact in facts for source in cell['support']]
    for item in result['logic_claims']:
        fact=claim('logical-claim',episode,concept(item['entity']),concept(item['property']),concept(item['polarity']))
        roots.append(fact);roots += [claim('logic-support',fact,node('NumberNode',i)) for i in item['support']]
    for query in result['queries']:
        q=concept(query['text']);kind=concept(query['engine'])
        roots.append(claim('query-status',episode,kind,q,concept(query['status'])))
        if query['answer'] is not None:roots.append(claim('query-answer',episode,kind,q,concept(query['answer'])))
        roots += [claim('query-support',episode,kind,q,node('NumberNode',i)) for i in query['support']]
    graph=dict(format=FORMAT,episode_id=result['id'],roots=roots);validate_graph(graph);return graph


def validate_graph(graph):
    if type(graph) is not dict or set(graph)!={'format','episode_id','roots'} or graph['format']!=FORMAT:raise ValueError('Unknown graph envelope.')
    text(graph['episode_id'])
    if type(graph['roots']) is not list or len(graph['roots'])>20000:raise ValueError('Graph root limit.')
    count=0
    def visit(atom,depth):
        nonlocal count
        count+=1
        if count>200000 or depth>20 or type(atom) is not dict:raise ValueError('Graph depth/atom limit.')
        kind=atom.get('type')
        if type(kind) is not str:raise ValueError('Atom type must be literal text.')
        if kind in NODES:
            if set(atom)!={'type','name'}:raise ValueError('Unknown node fields.')
            text(atom['name'])
            if kind=='NumberNode' and not atom['name'].isdigit():raise ValueError('Only nonnegative index numbers are supported.')
        elif kind in LINKS:
            if set(atom)!={'type','outgoing'} or type(atom['outgoing']) is not list:raise ValueError('Unknown link fields.')
            if kind=='EvaluationLink' and (len(atom['outgoing'])!=2 or any(type(v) is not dict for v in atom['outgoing']) or atom['outgoing'][0].get('type')!='PredicateNode' or atom['outgoing'][1].get('type')!='ListLink'):raise ValueError('Invalid data evaluation shape.')
            if len(atom['outgoing'])>16:raise ValueError('Link arity limit.')
            for item in atom['outgoing']:visit(item,depth+1)
        else:raise ValueError('Only data node/link types are accepted; executable atom types are forbidden.')
    for atom in graph['roots']:visit(atom,0)
    return count


def scheme(graph):
    validate_graph(graph)
    def string(value):return '"'+value.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')+'"'
    def render(atom):return '('+atom['type']+' '+(string(atom['name']) if 'name' in atom else ' '.join(render(v) for v in atom['outgoing']))+')'
    return '; CAEL episode-scoped reported data. No evaluation, commands or truth-value claims.\n'+'\n'.join(render(a) for a in graph['roots'])+'\n'


def import_atomspace(graph):
    """Use the upstream low-level API, with no eval/load-file/execute calls."""
    validate_graph(graph)  # complete validation before any AtomSpace mutation
    from opencog.atomspace import AtomSpace,types
    space=AtomSpace()
    def build(atom):
        kind=getattr(types,atom['type'])
        return space.add_node(kind,atom['name']) if 'name' in atom else space.add_link(kind,[build(v) for v in atom['outgoing']])
    roots=[build(a) for a in graph['roots']]
    return space,roots
