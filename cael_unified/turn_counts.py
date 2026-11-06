"""Non-neural multinomial count evidence for conversational turn acts.

Word/bigram/character counts; no embeddings, hidden layers or model service.
Task readers gate the acts. Score/margin is evidence, not probability.
"""
from collections import Counter
from functools import lru_cache
import json,re
from pathlib import Path
STOP=set('please kindly could would can you me it that this the a an to for of as be i want like just now then'.split())
def words(text):
 text=text.casefold().replace('’',"'")
 text=re.sub(r"\b(?:don't|doesn't|isn't|won't|can't)\b",lambda m:{"don't":'do not',"doesn't":'does not',"isn't":'is not',"won't":'will not',"can't":'cannot'}[m[0]],text)
 return re.findall(r'[a-z]+|\d+',text)
def features(text):
 tokens=[w for w in words(text) if w not in STOP];out=Counter()
 for w in tokens:
  out['w:'+('NUMBER' if w.isdigit() else w)]=1
  if not w.isdigit():
   for size in (3,4):
    for i in range(len(w)-size+1):out['c:'+w[i:i+size]]+=.06
 for a,b in zip(tokens,tokens[1:]):out['b:'+a+' '+b]+=.45
 return out
@lru_cache(maxsize=1)
def model():return json.loads(Path(__file__).with_name('dialogue_policy.json').read_text(encoding='utf-8'))
def read(text):
 if not isinstance(text,str) or len(text)>240 or len(text.split())>40 or '```' in text:return None
 data=model();f=features(text);mass=sum(v for k,v in f.items() if k in data['vocabulary'])
 if not mass:return None
 coverage=sum('w:'+w in data['vocabulary'] for w in words(text))/max(1,len(words(text)))
 scores={label:sum(v*weight.get(k,0) for k,v in f.items())/mass for label,weight in data['weights'].items()}
 ranked=sorted(scores.items(),key=lambda kv:-kv[1]);label,score=ranked[0];margin=score-ranked[1][1]
 if label=='unknown' or score<data['minimum_score'] or margin<data['minimum_margin'] or coverage<.3:return None
 return {'act':label,'score':round(score,5),'margin':round(margin,5),'method':'multinomial count log-evidence'}
