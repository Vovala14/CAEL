"""Bounded integer CA planner, local entity memory and trained grammar.

Does not import the curriculum/teacher or load training examples at inference.
The authored schema and template-like regular grammar are explicitly scoped.
"""
import json,re,hashlib
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
def words(s):return re.findall(r"[A-Za-z]+|[,\.!?]",s.casefold())
def choose(choices,seed):
 total=sum(int(c) for _,c in choices);r=int.from_bytes(hashlib.blake2b(str(seed).encode(),digest_size=8).digest(),'little')%total
 for value,count in choices:
  if r<int(count):return value
  r-=int(count)
 raise AssertionError('bad integer sampling')
class Unsupported(ValueError):pass
class CAEL:
 def __init__(self,path=P/'models'/'cael-story-0.1'/'model.json'):
  self.path=Path(path);self.model=json.loads(self.path.read_text(encoding='utf8'));self.events=self.model['event_names'];self.eid={e:i for i,e in enumerate(self.events)};self.intents=self.model['intents'];self.iid={n:i for i,n in enumerate(self.intents)};self.plan_rules={(self.iid[r['intent']],-2 if r['previous']=='START' else self.eid[r['previous']],r['step']):[(self.eid[e] if e!='END' else -1,n) for e,n in r['choices'].items()] for r in self.model['plan_rules']};self.update_rules={(self.eid[r['event']],r['kind'],r['relation']):r['ops'] for r in self.model['update_rules']};self.grammar=self.model['grammar'];self.starts={self.eid[e]:v for e,v in self.model['grammar_starts'].items()};self.lex={s:max(n,key=n.get) for s,n in self.model['lexicon'].items()};self.world=self.initial_world();self.last_frame=None
 def initial_world(self):return np.array([[j+1,1,0,0,0,0,0] for j in range(len(self.model['actors']))]+[[101+j,2,0,0,0,0,0] for j in range(len(self.model['objects']))],np.int32)
 def lex_matches(self,text):
  seq=words(text);matches=[]
  for i in range(len(seq)):
   for n in range(1,4):
    phrase=' '.join(seq[i:i+n])
    if phrase in self.lex:matches.append((i,self.lex[phrase],n))
  return seq,matches
 def parse_story(self,text):
  seq,matches=self.lex_matches(text)
  if not any(tag=='story' for _,tag,_ in matches):raise Unsupported('Outside the current simple-story scope.')
  # Explicit closed interface grammar: do not silently discard unknown goals.
  # This parser schema is authored, not a learned general English interpreter.
  controls=set('tell write create make up me please short little quiet gentle about a an the of to who in on at near beside with for her his and once can you could would i like want now something'.split())
  known={t for phrase in self.lex for t in words(phrase)}|controls
  unknown=[t for t in seq if t.isalpha() and t not in known]
  if unknown:raise Unsupported('Unsupported request terms: '+', '.join(dict.fromkeys(unknown)))
  actors=[(pos,int(tag.split(':')[1])) for pos,tag,n in matches if tag.startswith('actor:')];objects=[int(tag.split(':')[1]) for _,tag,n in matches if tag.startswith('object:')];places=[int(tag.split(':')[1]) for _,tag,n in matches if tag.startswith('place:')];skills=[int(tag.split(':')[1]) for _,tag,n in matches if tag.startswith('skill:')]
  if not actors:raise Unsupported('No supported character identified; not a general chat model.')
  a=actors[0][1];b=next((actor for _,actor in actors[1:] if actor!=a),(a+1)%len(self.model['actors']));intent_tags=[(pos,tag.split(':')[1],n) for pos,tag,n in matches if tag.startswith('intent:') and pos>actors[0][0]]
  if not intent_tags:raise Unsupported('A supported find/share/help/lose/visit/rest/learn/comfort goal is required.')
  intent=min(intent_tags,key=lambda r:(r[0],-r[2]))[1]
  if intent=='help' and any(tag=='comfort' for _,tag,_ in intent_tags):intent='comfort'
  # Defaults are transparent fixed interface values, not inferred knowledge.
  i=objects[0] if objects else (a%len(self.model['objects']));p=places[0] if places else 2;s=skills[0] if skills else 1 if self.model['actors'][a]=='bird' else 2 if self.model['actors'][a]=='duck' else 0
  return dict(a=a,b=b,i=i,p=p,s=s,intent=intent)
 def parameters(self,f):return np.array([f['a']+1,f['b']+1,f['i']+101,f['p']+201,f['s'],self.iid[f['intent']]],np.int32)
 def plan_step(self,grid,seed):
  """Synchronous radius-one copy; only a site's own channels select its output."""
  nxt=np.zeros_like(grid);emitted=np.full(len(grid),-3,np.int32)
  for j in np.flatnonzero(grid[:,0]):
   old=grid[j];intent,prev,step=map(int,old[1:4]);choices=self.plan_rules.get((intent,prev,step))
   if not choices:raise Unsupported('No learned plan transition for this state.')
   event=choose(choices,(seed,intent,prev,step));emitted[j]=event
   if event>=0 and j+1<len(grid):nxt[j+1]=old;nxt[j+1,2]=event;nxt[j+1,3]=step+1
  return nxt,emitted
 def plan(self,frame,seed=0):
  grid=np.zeros((16,10),np.int32);grid[0,:4]=[1,self.iid[frame['intent']],-2,0];grid[0,4:]=self.parameters(frame);out=[]
  for _ in range(16):
   grid,emitted=self.plan_step(grid,seed)
   for event in emitted[emitted>=-1]:
    if event<0:return out
    out.append(int(event))
  raise Unsupported('Bounded plan did not finish.')
 def memory_step(self,rows,carriers):
  """Local row plus local packet only; packets copy from immediate left."""
  out=rows.copy();following=np.full_like(carriers,-1);following[1:]=carriers[:-1]
  for j in np.flatnonzero(carriers[:,0]>=0):
   event=int(carriers[j,0]);a,b,item,place=map(int,carriers[j,1:5]);row=rows[j];rel=int(row[0]==a)|(int(row[0]==b)<<1)|(int(row[0]==item)<<2)|(int(row[2]==a)<<3);ops=self.update_rules.get((event,int(row[1]),rel))
   if ops is None:raise Unsupported('No learned local entity transition.')
   for field,op in enumerate(ops):out[j,field+2]=[int(row[field+2]),0,a,b,item,place,201,1][op]
  return out,following
 def apply(self,event,frame):
  carrier=np.full((len(self.world),5),-1,np.int32);carrier[0]=[event,*self.parameters(frame)[:4]]
  for _ in range(len(self.world)):self.world,carrier=self.memory_step(self.world,carrier)
 def grammar_step(self,grid,seed):
  nxt=np.zeros_like(grid);emitted=np.full(len(grid),-1,np.int32)
  for j in np.flatnonzero(grid[:,0]):
   old=grid[j];state=int(old[1]);choices=self.grammar[state]
   if not choices:raise Unsupported('Grammar ended without a learned boundary.')
   symbol,next_state=choose([((int(t),int(nxt)),int(c)) for t,nxt,c in choices],(seed,int(old[8]),state));emitted[j]=symbol
   if self.model['symbols'][symbol]!='<END>' and j+1<len(grid):nxt[j+1]=old;nxt[j+1,1]=next_state;nxt[j+1,8]=old[8]+1
  return nxt,emitted
 def render(self,event,frame,seed):
  grid=np.zeros((128,9),np.int32);grid[0,0]=1;grid[0,1]=self.starts[event];grid[0,2:8]=self.parameters(frame);out=[]
  item=self.model['objects'][frame['i']];place=self.model['places'][frame['p']];location='at home' if place=='home' else 'at school' if place=='school' else 'in the '+place
  slots={'<A>':'the '+self.model['actors'][frame['a']],'<B>':'the '+self.model['actors'][frame['b']],'<I>':item,'<J>':('some ' if item in ('bread','cheese') else 'an ' if item[:1] in 'aeiou' else 'a ')+item,'<P>':place,'<L>':location,'<S>':self.model['skills'][frame['s']]}
  for _ in range(128):
   grid,symbols=self.grammar_step(grid,seed)
   for symbol in symbols[symbols>=0]:
    token=self.model['symbols'][int(symbol)]
    if token=='<END>':
     text=' '.join(out);text=re.sub(r'\s+([,.!?])',r'\1',text);return text[:1].upper()+text[1:]
    out.append(slots.get(token,token))
  raise Unsupported('Bounded grammar did not finish.')
 def story(self,prompt,seed=0):
  f=self.parse_story(prompt);return self.story_frame(f,seed)
 def story_frame(self,frame,seed=0,reset=True):
  if reset:self.world=self.initial_world()
  self.last_frame=dict(frame);plan=self.plan(frame,seed);sentences=[]
  for k,event in enumerate(plan):self.apply(event,frame);sentences.append(self.render(event,frame,(seed,k)))
  return dict(response=' '.join(sentences),frame=dict(frame),events=[self.events[e] for e in plan],world=self.world.tolist(),constrained=True)
 def ask(self,text):
  if self.last_frame is None:raise Unsupported('No story is loaded in this session.')
  normalized=' '.join(text.casefold().strip().rstrip('?.!').split())
  allowed={f'where is {article}{a}' for a in self.model['actors'] for article in ('','the ')}
  allowed|={f'who helped {article}{a}' for a in self.model['actors'] for article in ('','the ')}
  allowed|={f'who {verb} {article}{i}' for i in self.model['objects'] for verb in ('has','holds','owns','got','found') for article in ('','the ')}
  if normalized not in allowed:raise Unsupported('Question is outside the exact supported ownership/location/finder/helper forms.')
  seq,matches=self.lex_matches(text);actor=next((int(tag.split(':')[1]) for _,tag,n in matches if tag.startswith('actor:')),None);item=next((int(tag.split(':')[1]) for _,tag,n in matches if tag.startswith('object:')),None);frame=dict(self.last_frame)
  if 'where' in seq and actor is not None:
   row=self.world[self.world[:,0]==actor+1][0];value=int(row[3]);event='ANSWER_PLACE';frame['a']=actor;frame['p']=value-201
  elif 'who' in seq and 'helped' in seq and actor is not None:
   row=self.world[self.world[:,0]==actor+1][0];value=int(row[5]);event='ANSWER_HELPER';frame['b']=actor;frame['a']=value-1
  elif 'who' in seq and 'found' in seq and item is not None:
   row=self.world[self.world[:,0]==item+101][0];value=int(row[4]);event='ANSWER_FINDER';frame['i']=item;frame['a']=value-1
  elif 'who' in seq and any(t in seq for t in ['has','holds','owns','got']) and item is not None:
   row=self.world[self.world[:,0]==item+101][0];value=int(row[2]);event='ANSWER_OWNER';frame['i']=item;frame['a']=value-1
  else:raise Unsupported('Question is outside the current ownership/location/finder/helper scope.')
  if value<=0:raise Unsupported('The story state does not establish that fact.')
  return dict(response=self.render(self.eid[event],frame,('answer',text)),value=value,event=event)
 def fork(self):
  out=object.__new__(CAEL);out.__dict__=dict(self.__dict__);out.world=self.world.copy();out.last_frame=dict(self.last_frame) if self.last_frame is not None else None;return out
