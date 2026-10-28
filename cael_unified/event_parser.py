"""Bounded, authored shallow event grammar; no neural or statistical tagger.

Extracts explicit local roles, reference candidates, polarity and temporal
edges. Unknown syntax/references remain unknown. Textual event order is not
claimed to be chronological when before/after/while says otherwise.
"""
from dataclasses import asdict, dataclass, field
import re

TOKEN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|[0-9]+|[.,;:!?]")
LEXICON = '''
take:took,taken,taking give:gave,given go:went,gone come:came
hold:held put:putting get:got,gotten stand:stood sit:sat,sitting
run:ran,running walk:walked move:moved turn:turned lift:lifted place:placed
pick:picked drop:dropped,dropping carry:carried hand:handed pass:passed
receive:received send:sent bring:brought leave:left return:returned
open:opened close:closed shut:shutting lock:locked unlock:unlocked
push:pushed pull:pulled tip:tipped,tipping pour:poured fill:filled
empty:emptied spill:spilled,spilt mix:mixed stir:stirred,stirring
cut:cutting slice:sliced chop:chopped,chopping peel:peeled
cook:cooked heat:heated cool:cooled boil:boiled bake:baked fry:fried
eat:ate,eaten drink:drank,drunk bite:bit,bitten swallow:swallowed
wash:washed rinse:rinsed dry:dried clean:cleaned wipe:wiped
brush:brushed scrape:scraped scrub:scrubbed,scrubbing shave:shaved
wear:wore,worn dress:dressed undress:undressed remove:removed
attach:attached detach:detached connect:connected disconnect:disconnected
insert:inserted wrap:wrapped,wrapping fold:folded unfold:unfolded
spread:spread throw:threw,thrown catch:caught kick:kicked hit:hitting
roll:rolled bounce:bounced jump:jumped climb:climbed fall:fell,fallen
ride:rode,ridden drive:drove,driven park:parked stop:stopped,stopping
start:started finish:finished begin:began,begun continue:continued
use:used operate:operated press:pressed touch:touched reach:reached apply:applied
look:looked watch:watched see:saw,seen show:showed,shown
read:reading write:wrote,written draw:drew,drawn paint:painted
build:built break:broke,broken repair:repaired fix:fixed drill:drilled
hammer:hammered screw:screwed unscrew:unscrewed tie:tied,tying
untie:untied,untying stretch:stretched bend:bent straighten:straightened
shake:shook,shaken squeeze:squeezed rub:rubbed,rubbing
help:helped teach:taught learn:learned,learnt talk:talked speak:spoke,spoken
tell:told ask:asked answer:answered smile:smiled laugh:laughed
point:pointed wave:waved dance:danced sing:sang,sung play:played
swim:swam,swum,swimming float:floated sink:sank,sunk
follow:followed chase:chased lead:led approach:approached enter:entered exit:exited
buy:bought sell:sold pay:paid wait:waited sleep:slept wake:woke,woken deliver:delivered prepare:prepared
want:wanted try:tried need:needed decide:decided
'''


def _forms(base):
    yield base
    yield base+'es' if base.endswith(('s','sh','ch','x','o')) else base[:-1]+'ies' if base.endswith('y') and base[-2] not in 'aeiou' else base+'s'
    yield base+'d' if base.endswith('e') else base[:-1]+'ied' if base.endswith('y') and base[-2] not in 'aeiou' else base+'ed'
    yield base[:-1]+'ing' if base.endswith('e') and not base.endswith('ee') else base+'ing'


VERBS={}
PAST_PARTICIPLES=set()
for _entry in LEXICON.split():
    _base,_extra=_entry.split(':')
    for _surface in (*_forms(_base),*_extra.split(',')):
        VERBS[_surface]=_base
        if _surface.endswith('ed') or _surface in _extra.split(',') and not _surface.endswith('ing'):
            PAST_PARTICIPLES.add(_surface)
PHRASES={('pick','up'):'take',('put','down'):'drop',('hand','over'):'give',
         ('give','back'):'give',('stand','up'):'stand',('sit','down'):'sit',
         ('get','up'):'stand',('take','off'):'remove',('put','on'):'wear',
         ('turn','on'):'switch_on',('turn','off'):'switch_off',('look','at'):'look'}
DET=set('a an the this that these those his her its their my your our some any another one two three four several'.split())
AUX=set("is are was were be been being am do does did has have had can could may might must should would will shall to".split())
ADVERBS=set('then next later afterwards again now still slowly quickly carefully gently suddenly finally already just also away back up down only really very together around over'.split())
PREPS=set('to from with in on at into onto over under beside near by behind towards toward through across out off of for about between'.split())
CONNECT=set('and but while before after as then next afterwards'.split())
BREAK=set('. ; : ! ? ,'.split())
PERSON=set('man woman boy girl child person adult guy lady kid baby infant people men women children boys girls adults guys ladies kids worker chef cook painter teacher student mechanic driver player performer dancer musician singer officer nurse doctor firefighter athlete runner rider swimmer customer visitor friend mother father parent daughter son brother sister husband wife'.split())
OBJECTS=set('water milk oil flour sugar salt food bread rice meal meat fruit vegetable paper wood metal stone sand air fire smoke light sound cup kettle bottle bucket bowl plate glass pan pot knife spoon fork scissors drill hammer saw screw nail brush razor towel shirt coat hat shoe ball book notebook parcel box bag basket table chair bed door window wall floor roof board car truck bicycle bike motorcycle boat train bus room hall garden kitchen workshop road street hill field pool river sea lake tree plant flower leaf rock rope cable wire phone camera pencil pen guitar piano violin drum hose soap cream paint glue'.split())
MALE=set('man men boy boys guy guys father son brother husband'.split())
FEMALE=set('woman women girl girls lady ladies mother daughter sister wife'.split())
SINGULAR={'men':'man','women':'woman','children':'child','people':'person','mice':'mouse','feet':'foot','teeth':'tooth','knives':'knife','leaves':'leaf'}
PRONOUNS={'he':'male','him':'male','she':'female','her':'female','it':'object','they':'plural','them':'plural','who':'relative'}
ASPECT={'start','begin','continue','try','want','need','decide'}
NEGATIVE={'not','never','without'}
PAST_PARTICIPLES.update({'put','cut','read','hit','shut','spread'})


@dataclass
class Entity:
    identity: str
    head: str
    description: str
    kind: str
    gender: str | None
    plural: bool
    mentions: list = field(default_factory=list)


@dataclass
class Event:
    action: str
    actor: str | None
    patient: str | None
    recipient: str | None
    instrument: str | None
    location: str | None
    destination: str | None
    source: str | None
    negated: bool
    modality: str
    voice: str
    start: int
    end: int
    action_start: int
    order: int
    unresolved: list = field(default_factory=list)


@dataclass
class Document:
    entities: list = field(default_factory=list)
    events: list = field(default_factory=list)
    before: list = field(default_factory=list)
    simultaneous: list = field(default_factory=list)
    skipped_actions: int = 0
    truncated: bool = False

    def as_dict(self):
        return asdict(self)


def singular(word):
    if word in SINGULAR:
        return SINGULAR[word]
    if word.endswith('ies') and len(word)>4:
        return word[:-3]+'y'
    if word.endswith('s') and not word.endswith(('ss','us','is','ous')) and len(word)>3:
        return word[:-1]
    return word


class Parser:
    def __init__(self):
        self.doc=Document()
        self.tokens=[]
        self.lower=[]
        self.last_actor=None
        self.last_objects=set()

    def ref(self, ids, unresolved, exclude=None):
        ids=list(ids)
        while ids and (self.lower[ids[0]] in AUX|ADVERBS or self.lower[ids[0]] in {'not','never','only'}):
            ids.pop(0)
        while ids and self.lower[ids[-1]] in AUX|ADVERBS:
            ids.pop()
        if not ids:
            return None
        words=[self.lower[i] for i in ids]
        if 'and' in words:
            split=words.index('and')
            members=[self.ref(ids[:split],unresolved,exclude),self.ref(ids[split+1:],unresolved,exclude)]
            if any(m is None for m in members):
                return None
            if members[0]==members[1]:
                return members[0]
            identity='group:'+','.join(sorted(members))
            group=next((e for e in self.doc.entities if e.identity==identity),None)
            if group is None:
                group=Entity(identity,'group',' '.join(words),'person' if all(next(e for e in self.doc.entities if e.identity==m).kind=='person' for m in members) else 'object',None,True)
                self.doc.entities.append(group)
            return group.identity
        if words[0] in PRONOUNS and (len(words)==1 or words[1] in AUX|ADVERBS):
            kind=PRONOUNS[words[0]]
            if kind=='relative':
                candidates=[e for e in self.doc.entities if e.identity in self.last_objects]
            elif kind=='object':
                candidates=[e for e in self.doc.entities if e.identity in self.last_objects and e.kind!='person']
                if not candidates:
                    candidates=[e for e in self.doc.entities if e.kind=='object']
            elif kind=='plural':
                candidates=[e for e in self.doc.entities if e.plural]
            else:
                candidates=[e for e in self.doc.entities if e.kind=='person' and e.gender in (None,kind) and not e.plural]
            candidates=[e for e in candidates if e.identity!=exclude]
            if len(candidates)==1:
                candidates[0].mentions.append([self.tokens[ids[0]].start(),self.tokens[ids[0]].end()])
                return candidates[0].identity
            unresolved.append(dict(reference=words[0],start=self.tokens[ids[0]].start(),candidates=[e.identity for e in candidates]))
            return None
        # The first preposition/relative marker closes the shallow NP. Do not
        # turn a whole relative clause into a new entity or guess its head.
        cut=next((j for j,w in enumerate(words) if w in PREPS|CONNECT|{'who','which','that'} and j>0),len(words))
        ids,words=ids[:cut],words[:cut]
        if not words or any(w in BREAK for w in words):
            return None
        content=[(i,w) for i,w in zip(ids,words) if w not in DET|AUX|ADVERBS|NEGATIVE|{'if','unless','before','after','while'} and not w.endswith("n't") and not w.isdigit()]
        if not content:
            return None
        head_i,raw_head=content[-1]
        if raw_head in CONNECT or raw_head in PREPS or raw_head in VERBS and words[0] not in DET:
            return None
        head=singular(raw_head.removesuffix("'s"))
        description=' '.join(w for _,w in content)
        proper=bool(re.fullmatch(r'[A-Z][a-z]+',self.tokens[head_i][0])) and raw_head not in OBJECTS or raw_head.startswith('person')
        person=raw_head in PERSON or head in PERSON or proper
        plural=raw_head in SINGULAR or raw_head.endswith('s') and raw_head!=head or any(w in {'two','three','four','several','those','these'} for w in words)
        gender='male' if raw_head in MALE or head in MALE else 'female' if raw_head in FEMALE or head in FEMALE else None
        definite=words[0] in {'the','this','that','these','those','his','her','its','their'} or proper
        candidates=[e for e in self.doc.entities if e.head==head and e.plural==plural]
        exact=[e for e in candidates if e.description==description]
        if definite and candidates:
            candidates=exact if exact else candidates
            if len(candidates)!=1:
                unresolved.append(dict(reference=' '.join(words),start=self.tokens[ids[0]].start(),candidates=[e.identity for e in candidates]))
                return None
            entity=candidates[0]
        else:
            identity=head+'#'+str(1+sum(e.head==head for e in self.doc.entities))
            entity=Entity(identity,head,description,'person' if person else 'object',gender,bool(plural))
            self.doc.entities.append(entity)
        entity.mentions.append([self.tokens[ids[0]].start(),self.tokens[ids[-1]].end()])
        return entity.identity

    def actions(self):
        out=[]
        for i,w in enumerate(self.lower):
            if w not in VERBS:
                continue
            if i and self.lower[i-1] in DET:
                continue
            action=VERBS[w]
            if w in {'open','empty','dry','clean','cool','close'} and i and i+1<len(self.lower):
                previous=self.lower[i-1]
                nominal=previous in PERSON|OBJECTS|set(PRONOUNS) or previous.endswith('s') or self.tokens[i-1][0][0].isupper()
                if not nominal and any(v in DET for v in self.lower[max(0,i-3):i]) and self.lower[i+1] not in PREPS|DET|AUX:
                    continue
            # Aspect verbs do not become separate physical events when they
            # introduce another action; their subject still belongs to it.
            later=self.lower[i+1:i+4]
            if action in ASPECT and any(v in VERBS for v in later) and not any(v in BREAK for v in later):
                continue
            if w=='seen' and any(v in VERBS for v in later) and not any(v in BREAK for v in later):
                continue
            end=i+1
            if end<len(self.lower) and (action,self.lower[end]) in PHRASES:
                action=PHRASES[action,self.lower[end]]
                end+=1
            out.append((i,end,action))
            if len(out)>=100:
                self.doc.truncated=True
                break
        return out

    def parse(self,text):
        if not isinstance(text,str) or len(text)>20000:
            raise ValueError('Event parser accepts at most 20,000 characters')
        self.__init__()
        raw_tokens=list(TOKEN.finditer(text))
        self.doc.truncated=len(raw_tokens)>3000
        self.tokens=raw_tokens[:3000]
        self.lower=[t[0].lower() for t in self.tokens]
        actions=self.actions()
        previous=None
        prefix_temporal=None
        for ordinal,(i,end,action) in enumerate(actions):
            sentence=max((j+1 for j in range(i) if self.lower[j] in {'.',';','!','?',':'}),default=0)
            same=previous is not None and previous[0]>=sentence
            lo=previous[1] if same else sentence
            between=self.lower[lo:i]
            separators=[lo+j for j,w in enumerate(between) if w in CONNECT or w in {',','who'}]
            subject_lo=(separators[-1]+1 if separators else i) if same else sentence
            front_comma=next((j for j in reversed(range(sentence,i)) if self.lower[j]==','),None) if not same else None
            if front_comma is not None:
                subject_lo=front_comma+1
            subject_ids=list(range(subject_lo,i))
            # Drop aspect material while preserving its explicit subject.
            aspect_pos=next((j for j in subject_ids if VERBS.get(self.lower[j]) in ASPECT or self.lower[j]=='seen'),None)
            if aspect_pos is not None:
                subject_ids=[j for j in subject_ids if j<aspect_pos]
            unresolved=[]
            actor=self.ref(subject_ids,unresolved)
            if actor is None and same and separators and self.lower[separators[-1]]=='who':
                actor=self.ref([separators[-1]],unresolved)
            explicit_subject=actor is not None or bool(unresolved)
            if actor is None and not unresolved and same:
                actor=self.last_actor
            prefix=self.lower[sentence:i]
            local=self.lower[subject_lo:i]
            negated=any(w in {'not','never','without'} or w.endswith("n't") for w in local)
            if same and not explicit_subject and self.doc.events and 'but' not in between:
                negated=negated or self.doc.events[-1].negated
            modal=next((w for w in local if w in {'may','might','could','would','should','can','must'}),None)
            intent=any(VERBS.get(w) in {'want','need','try','decide'} for w in local)
            interrogative=self.lower[sentence] in {'who','what','which','where','when','why','how'}
            modality='question' if interrogative else 'conditional' if 'if' in prefix or 'unless' in prefix else 'possible' if modal or intent else 'future' if 'will' in local or 'shall' in local else 'asserted'
            next_i=actions[ordinal+1][0] if ordinal+1<len(actions) else len(self.tokens)
            body=[]
            for j in range(end,next_i):
                if self.lower[j] in BREAK|CONNECT|{'who','which'}:
                    break
                body.append(j)
            chunks=[]
            beginning=0
            marker=None
            for k,j in enumerate(body):
                if self.lower[j] in PREPS:
                    chunks.append((marker,body[beginning:k]))
                    beginning=k+1
                    marker=self.lower[j]
            chunks.append((marker,body[beginning:]))
            roles={name:None for name in ('patient','recipient','instrument','location','destination','source')}
            if front_comma is not None and self.lower[sentence] in {'at','in','near','on'}:
                roles['location']=self.ref(range(sentence+1,front_comma),unresolved)
            agent=None
            passive=self.lower[i] in PAST_PARTICIPLES and any(w in {'is','are','was','were','been','being','be'} for w in local)
            for marker,ids in chunks:
                if marker is None and action in {'give','hand','send','show','tell','pass'} and len(ids)>=3:
                    dative=next((k for k in range(1,len(ids)) if self.lower[ids[k]] in {'a','an','the','this','that'}),None)
                    if dative is not None and (self.lower[ids[0]] in {'him','her','them'} or self.tokens[ids[0]][0][0].isupper()):
                        roles['recipient']=self.ref(ids[:dative],unresolved,exclude=actor)
                        ids=ids[dative:]
                ref=self.ref(ids,unresolved,exclude=actor)
                if marker is None:
                    roles['patient']=ref
                elif marker=='by' and passive:
                    agent=ref
                elif marker=='with':
                    roles['instrument']=ref
                elif marker=='from':
                    roles['source']=ref
                elif marker=='to' and action in {'give','send','tell','show','offer','hand','pass'}:
                    roles['recipient']=ref
                elif marker in {'to','into','onto','toward','towards','over'}:
                    roles['destination']=ref
                elif marker in {'in','on','at','under','beside','near','behind','by','through','across','between'}:
                    roles['location']=ref
            if passive:
                roles['patient']=actor
                actor=agent
            # Receiving reverses explicit source/recipient roles without
            # treating the receiver as the giver.
            if action=='receive' and roles['source']:
                roles['recipient']=actor
                actor=roles['source']
                roles['source']=None
                action='give'
            if action in {'hand','pass'} and roles['recipient']:
                action='give'
            event=Event(action=action,actor=actor,**roles,negated=negated,modality=modality,
                voice='passive' if passive else 'active',start=self.tokens[subject_lo if subject_lo<i else i].start(),
                end=self.tokens[body[-1] if body else end-1].end(),action_start=self.tokens[i].start(),order=len(self.doc.events),unresolved=unresolved)
            self.doc.events.append(event)
            marker=next((w for w in between if w in {'before','after','while'}),None)
            if ordinal and same:
                a,b=ordinal-1,ordinal
                if marker=='after' or prefix_temporal=='before':
                    self.doc.before.append([b,a])
                elif marker=='while' or prefix_temporal=='while':
                    self.doc.simultaneous.append([a,b])
                else:
                    self.doc.before.append([a,b])
            elif ordinal:
                self.doc.before.append([ordinal-1,ordinal])
            if not same:
                prefix_temporal=next((w for w in prefix if w in {'before','after','while'}),None)
            else:
                prefix_temporal=None
            self.last_actor=actor
            self.last_objects={value for role,value in roles.items() if value is not None}
            previous=(i,end)
        return self.doc


def parse(text):
    return Parser().parse(text)
