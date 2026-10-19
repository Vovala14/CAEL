"""Conservative noisy-channel repair of chat control words, never a neural model."""
from collections import Counter
from functools import lru_cache
import json
import math
from pathlib import Path
import re
from .bundle import ROOT,digest

TOKENS=re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?|\d+(?:\.\d+)?|[.!?:]")
FIRST=set('hello hi hey please can could would what who where when why how calculate compute convert solve explain tell write help remember facts given premises add also increase decrease show'.split())
NEVER=set('no not nor neither never except without unless only before after left right more less fewer above below'.split())
PROTECTED=re.compile(r"```|`[^`]*`|[\"“][^\"”]*[\"”]|(?<!\w)'[^'\n]*'(?!\w)|https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+|[A-Za-z]:[\\/]\S+|\b(?:def|class|import|from)\s+[A-Za-z_]|\b[A-Za-z_]\w*\s*\(")


def tokens(text):
    return ['<number>' if t[0].isdigit() else t.lower().replace('’',"'") for t in TOKENS.findall(text)]


def distance_one(a,b):
    if a==b:return False
    if abs(len(a)-len(b))>1:return False
    if len(a)==len(b):
        differences=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
        return len(differences)==1 or (len(differences)==2 and differences[1]==differences[0]+1 and a[differences[0]]==b[differences[1]] and a[differences[1]]==b[differences[0]])
    short,long=(a,b) if len(a)<len(b) else (b,a)
    i=0
    while i<len(short) and short[i]==long[i]:i+=1
    return short[i:]==long[i+1:]


def distance_two(a,b):
    """Bounded Damerau edit check, used only for an explicit weather-time slot."""
    if abs(len(a)-len(b))>2:return False
    rows=[list(range(len(b)+1))]
    for i,x in enumerate(a,1):
        row=[i]
        for j,y in enumerate(b,1):
            value=min(row[-1]+1,rows[-1][j]+1,rows[-1][j-1]+(x!=y))
            if i>1 and j>1 and x==b[j-2] and a[i-2]==y:value=min(value,rows[-2][j-2]+1)
            row.append(value)
        rows.append(row)
    return rows[-1][-1]<=2


class TextRepair:
    def __init__(self,path):
        self.model=json.loads(Path(path).read_text(encoding='utf-8'))
        if self.model.get('format')!='cael-text-repair-count-v1':raise ValueError('Unsupported text repair model')
        self.words=self.model['words'];self.pairs=self.model['bigrams']
        self.known=set(self.model.get('known_words',[]))

    def pair(self,a,b):return self.pairs.get(a+'|'+b,0)

    @lru_cache(maxsize=512)
    def candidates(self,word):
        return tuple(w for w in self.words if w not in NEVER and
                     (distance_one(word,w) or (w=='help' and len(word)==4 and sorted(word)==sorted(w))
                      or (w=='tomorrow' and word.startswith('tom') and distance_two(word,w))))

    def repair(self,text):
        if len(text)>1600:return text,[]
        protected=[]
        for match in PROTECTED.finditer(text):
            # A polite numeric calculation is not a user-defined Python call.
            name=match[0].rstrip(' (').lower()
            numeric_request=(re.fullmatch(r'[A-Za-z_]\w*\s*\(',match[0])
                             and any(distance_one(name,w) for w in ('calculate','compute'))
                             and re.search(r'(?i)(?:^please|(?:can|could|would) you(?: please)?)\s+$',text[:match.start()])
                             and re.fullmatch(r'[0-9eE+*/%().\s\-]+[?.!]*',text[match.end():]))
            if not numeric_request:protected.append(match.span())
        # A code block or executable Python statement protects its entire tail.
        code=re.search(r'```|\b(?:def|class|import)\s+[A-Za-z_]',text)
        if code:protected.append((code.start(),len(text)))
        matches=list(TOKENS.finditer(text))[:120]
        current=tokens(text)[:120]
        typed_rate=bool(re.search(r'(?i)\b(?:rate|speed)\s+of\b',text))
        changes=[]
        for i,match in enumerate(matches):
            word=current[i]
            if word in self.words or word in self.known or word in FIRST or word in NEVER or not word.isalpha() or not 3<=len(word)<=18:continue
            if typed_rate:
                # Units such as "mins" are data, not a misspelling of "minus".
                # Reuse the rate adapter's exact unit vocabulary, without
                # guessing a correction or changing its fitted word counts.
                from .helper_rates import unit as rate_unit
                try:rate_unit(word)
                except ValueError:pass
                else:continue
            if any(start<=match.start()<stop for start,stop in protected):continue
            boundary=max((j for j in range(i) if current[j] in ('.','?','!',':')),default=-1)
            sentence_start=(i==boundary+1)
            if not sentence_start and match[0].istitle():continue
            previous='<s>' if sentence_start else current[i-1]
            following=current[i+1] if i+1<len(current) else '</s>'
            if match[0].istitle() and following in ('has','had','have','owns','went','moved','buys','gives','receives','loses','share','shares','shared','split','splits','divide','divides','divided','travels','moves','runs','prints','produces','pumps','delivers','flows','processes','fills'):continue
            # Factual entities and arbitrary nouns remain the lookup system's job.
            prefix=current[boundary+1:i]
            subject=any(t in ('about','define','describe') for t in prefix)
            copula=any(t in ('is','are','was','were') for t in prefix)
            options=[]
            for candidate in self.candidates(word):
                if sentence_start and candidate not in FIRST:continue
                weather_control=(candidate=='weather' and following in ('today','tomorrow','tonight'))
                time_control=(candidate in ('today','tomorrow') and 'weather' in prefix[-4:] and previous in ('weather','for'))
                if not distance_one(word,candidate) and not ((candidate=='help' and previous=='please' and following=='me') or time_control):continue
                if not sentence_start and (subject or copula) and candidate not in ('formed','founded','started','invented','born'):
                    if previous!='<number>' and previous not in ('feel','feeling') and not weather_control and not time_control:continue
                before=self.pair(previous,candidate);after=self.pair(candidate,following)
                if not sentence_start and before+after==0 and not weather_control and not time_control:continue
                score=math.log1p(self.words[candidate])+.9*math.log1p(before)+.9*math.log1p(after)
                if sentence_start:score+=1.2*math.log1p(self.pair('<s>',candidate))
                options.append((score,candidate))
            options.sort(reverse=True)
            if not options or (len(options)>1 and options[0][0]-options[1][0]<.8):continue
            selected=options[0][1]
            if match[0].istitle():selected=selected.capitalize()
            changes.append(dict(start=match.start(),end=match.end(),original=match[0],replacement=selected))
            current[i]=selected.lower()
            if len(changes)>=4:break
        repaired=text
        for change in reversed(changes):repaired=repaired[:change['start']]+change['replacement']+repaired[change['end']:]
        return repaired,changes


@lru_cache(maxsize=3)
def load_checked(path,sha):
    if digest(Path(path))!=sha:raise ValueError('Active text repair model checksum changed')
    return TextRepair(path)


def active_repairer():
    path=ROOT/'research/active_models.json'
    entry=json.loads(path.read_text()).get('text_repair') if path.exists() else None
    return load_checked(entry['path'],entry['sha256']) if entry else None


def repair_messages(messages):
    if not isinstance(messages,list) or not messages or not all(isinstance(m,dict) and isinstance(m.get('content'),str) for m in messages):return messages,[]
    model=active_repairer()
    if model is None:return messages,[]
    output=[];last=[]
    for i,message in enumerate(messages):
        text=message['content'];changes=[]
        if message.get('role')=='user':text,changes=model.repair(text)
        output.append(dict(message,content=text))
        if i==len(messages)-1:last=changes
    return output,last
