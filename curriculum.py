"""Transparent authored world/grammar curriculum, not unrestricted chat data."""
import hashlib,json,re
ACTORS=['cat','dog','rabbit','mouse','fox','bear','bird','duck','girl','boy','robot','horse']
OBJECTS=['ball','hat','toy','book','apple','cake','bread','carrot','cheese','blanket','flower','letter','seed','basket']
PLACES=['home','forest','park','garden','school','bakery','pond','farm']
INTENTS=['find','share','help','lose','visit','rest','learn','comfort']
SKILLS=['read','fly','swim','ride a bicycle']
# These authored synonyms/slot annotations belong to the synthetic teacher.
FORMS={'find':['find','finding','finds','found','looking for','searching for'], 'share':['share','sharing','shares','give','giving'], 'help':['help','helping','helps'], 'lose':['lose','losing','loses','lost'], 'visit':['visit','visiting','visits','explore','exploring','walking'], 'rest':['rest','resting','sleep','sleeping','nap'], 'learn':['learn','learning','learns'], 'comfort':['comfort','comforting','frightened','scared','afraid']}
STORY_MARKERS=['story','tale','fable']
EVENTS={
'INTRO':['Once upon a time , <A> lived near the <P> .','One day , <A> was near the <P> .'],
'WANT':['<A> wanted to find the <I> .','<A> hoped to find the <I> .'],
'SEARCH':['<A> looked around the <P> for the <I> .','<A> searched the <P> carefully .'],
'FIND':['At last , <A> found the <I> .','After looking carefully , <A> found the <I> .'],
'HAPPY':['<A> felt happy and smiled .','<A> was glad that everything had worked out .'],
'HAVE':['<A> had <J> .','<A> carried <J> .'],
'MEET':['<A> met <B> near the <P> .','Near the <P> , <A> saw <B> .'],
'SHARE':['<A> decided to share the <I> and gave it to <B> .','<A> gave the <I> to <B> .'],
'THANK':['<B> thanked <A> for being kind .','<B> smiled and thanked <A> .'],
'TOGETHER':['The two friends were happy together .','They were glad to have each other .'],
'NEED':['<B> had lost <J> and needed help .','<B> could not find the <I> .'],
'RETURN':['<A> gave the <I> back to <B> .','<A> returned the <I> to <B> .'],
'LOSE':['<A> lost the <I> near the <P> .','The <I> slipped away from <A> .'],
'CAREFUL':['<A> decided to take better care of the <I> .','After that , <A> kept the <I> safe .'],
'GO':['<A> went to the <P> .','<A> walked to the <P> .'],
'SEE':['<A> saw a lovely <I> there .','There was <J> nearby .'],
'PLAY':['<A> and <B> played together .','The two friends spent a happy afternoon together .'],
'HOME':['After the visit , <A> went home .','Then <A> returned home feeling happy .'],
'TIRED':['<A> felt tired .','<A> needed a little rest .'],
'REST':['<A> settled down beside the <I> near the <P> and rested .','<A> rested peacefully beside the <I> near the <P> .'],
'TRY':['<A> wanted to learn to <S> .','<A> tried to <S> .'],
'FAIL':['It was difficult at first .','The first try did not go well .'],
'PRACTICE':['<A> practiced every day .','<A> kept trying patiently .'],
'SUCCESS':['At last , <A> learned to <S> .','With practice , <A> could <S> .'],
'AFRAID':['<B> felt frightened and alone .','<B> was scared .'],
'COMFORT':['<A> stayed beside <B> and spoke gently .','<A> helped <B> feel safe .'],
'CALM':['Soon , <B> felt calm again .','With a friend nearby , <B> was no longer afraid .'],
'ANSWER_OWNER':['<A> has the <I> .'],
'ANSWER_PLACE':['<A> is <L> .'],
'ANSWER_FINDER':['<A> found the <I> .'],
'ANSWER_HELPER':['<A> helped <B> .']}
PLANS={
'find':['INTRO','WANT','SEARCH','FIND','HAPPY'],
'share':['INTRO','HAVE','MEET','SHARE','THANK','TOGETHER'],
'help':['INTRO','MEET','NEED','SEARCH','FIND','RETURN','THANK'],
'lose':['INTRO','HAVE','LOSE','SEARCH','FIND','CAREFUL'],
'visit':['INTRO','GO','SEE','MEET','PLAY','HOME'],
'rest':['INTRO','TIRED','REST','HAPPY'],
'learn':['INTRO','TRY','FAIL','PRACTICE','SUCCESS','HAPPY'],
'comfort':['INTRO','MEET','AFRAID','COMFORT','CALM','TOGETHER']}
FIELDS=['owner','place','finder','helper','status']
def tokens(s):return re.findall(r'<[A-Z]>|[A-Za-z]+|[,\.!?]',s)
def canonical(f):
 out={k:f[k] for k in ['a','p','intent']}
 if f['intent'] in ['find','share','help','lose','visit','rest']:out['i']=f['i']
 if f['intent'] in ['share','help','visit','comfort']:out['b']=f['b']
 if f['intent']=='learn':out['s']=f['s']
 return out
def hashframe(f):return hashlib.sha256(json.dumps(canonical(f),sort_keys=True).encode()).hexdigest()
def split(f):
 x=int(hashframe(f)[:8],16)%20;return 'development' if x==0 else 'confirmation' if x==1 else 'train'
def relations(row,p):return int(row[0]==p['a'])|(int(row[0]==p['b'])<<1)|(int(row[0]==p['i'])<<2)|(int(row[2]==p['a'])<<3)
def teacher(row,p,event):
 # Teacher only: never imported by runtime inference.
 r=list(row);id,kind,owner,place,finder,helper,status=r
 if kind==1:
  if id==p['a'] and event in ['INTRO','GO']:r[3]=p['p']
  if id==p['b'] and event=='MEET':r[3]=p['p']
  if id==p['a'] and event=='HOME':r[3]=201
  if id==p['b'] and event in ['RETURN','COMFORT']:r[5]=p['a']
  if id==p['a'] and event in ['HAPPY','CAREFUL','SUCCESS','HOME']:r[6]=1
  if id==p['b'] and event=='CALM':r[6]=1
 elif kind==2:
  if id==p['i'] and event in ['HAVE','FIND']:r[2]=p['a'];r[3]=p['p']
  if id==p['i'] and event=='FIND':r[4]=p['a']
  if id==p['i'] and event in ['SHARE','RETURN']:r[2]=p['b'];r[3]=p['p']
  if id==p['i'] and event=='LOSE':r[2]=0;r[3]=p['p']
  if id==p['i'] and event=='REST':r[3]=p['p']
  if owner==p['a'] and event=='HOME':r[3]=201
 return r
def initial_rows():return [[j+1,1,0,0,0,0,0] for j in range(len(ACTORS))]+[[101+j,2,0,0,0,0,0] for j in range(len(OBJECTS))]
def packet(frame):return dict(a=frame['a']+1,b=frame['b']+1,i=frame['i']+101,p=frame['p']+201,s=frame['s'],intent=frame['intent'])
def surface(text,frame):
 item=OBJECTS[frame['i']];place=PLACES[frame['p']];slots={'<A>':'the '+ACTORS[frame['a']],'<B>':'the '+ACTORS[frame['b']],'<I>':item,'<J>':('some ' if item in ('bread','cheese') else 'an ' if item[:1] in 'aeiou' else 'a ')+item,'<P>':place,'<L>':'at home' if place=='home' else 'at school' if place=='school' else 'in the '+place,'<S>':SKILLS[frame['s']]};out=' '.join(slots.get(t,t) for t in tokens(text));out=re.sub(r'\s+([,.!?])',r'\1',out);return out[:1].upper()+out[1:]
