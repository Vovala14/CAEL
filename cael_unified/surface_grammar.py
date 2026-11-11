"""Learned, slot-preserving finite surface transducers with count support.

Induced from annotated authored examples, not neural embeddings or a model
service. A match covers the entire clause. Unknown conditions and conflicting
interpretations are retained as uncertainty, not a guessed semantic parse.
"""
from functools import lru_cache
from pathlib import Path
import hashlib,json,re


def normalized(text):return text.strip().replace('’',"'").rstrip('.!?').strip()


def fit(examples):
    patterns={}
    for example in examples:
        text=normalized(example['text']);spans=[]
        for name,value in example.get('slots',{}).items():
            hits=[m.span() for m in re.finditer(re.escape(value),text)]
            if len(hits)!=1:raise ValueError('An annotated training slot needs exactly one source span.')
            spans.append((hits[0][0],hits[0][1],name))
        spans.sort();parts=[];names=[];last=0
        for start,stop,name in spans:
            if start<last:raise ValueError('Training slots overlap.')
            parts.append(text[last:start].casefold());names.append(name);last=stop
        parts.append(text[last:].casefold())
        if sum(len(re.findall(r'\w+',p)) for p in parts)<2:raise ValueError('A surface needs at least two literal words.')
        row=dict(intent=example['intent'],stance=example.get('stance'),parts=parts,slots=names)
        key=json.dumps(row,sort_keys=True)
        if key not in patterns:patterns[key]=dict(row,support=0)
        patterns[key]['support']+=1
    return dict(schema=1,method='annotated finite-surface induction with empirical counts; no neural network',
                patterns=[dict(v,id='p'+str(i)) for i,(_,v) in enumerate(sorted(patterns.items()))])


def literal_regex(part):
    return r'\s+'.join(re.escape(p) for p in part.split()) if part.strip()==part else re.sub(r'\\\s+',r'\\s+',re.escape(part))


@lru_cache(maxsize=1)
def model():
    path=Path(__file__).with_name('discourse_surface.json');raw=path.read_bytes();data=json.loads(raw)
    compiled=[]
    for row in data['patterns']:
        pieces=[]
        for i,part in enumerate(row['parts']):
            pieces.append(re.sub(r'\s+',r'\\s+',re.escape(part).replace('\\ ', ' ')))
            if i<len(row['slots']):
                name=row['slots'][i]
                expression=r'\d{1,2}:\d{2}' if name in ('start','end') else r"[^.!?;\n]{1,160}?"
                pieces.append('(?P<'+name+'>'+expression+')')
        compiled.append((row,re.compile(''.join(pieces),re.I)))
    return compiled,hashlib.sha256(raw).hexdigest()


def read(text):
    if not isinstance(text,str) or len(text)>1200 or any(c in text for c in ('\n',';','`','“','"')):return None
    source=normalized(text)
    if re.search(r'(?i)\b(?:unless|provided|suppose|hypothetical|translate|quote)\b',source):return None
    matches=[]
    for row,pattern in model()[0]:
        m=pattern.fullmatch(source)
        if not m:continue
        slots={k:v.strip() for k,v in m.groupdict().items()}
        if any(not v or len(v)>160 for v in slots.values()):continue
        if any(re.search(r"(?i)\b(?:if|unless|except|but|not|never|maybe|perhaps|assuming|provided|might)\b",v) for k,v in slots.items() if k not in ('start','end')):continue
        matches.append(dict(intent=row['intent'],stance=row['stance'],slots=slots,
             spans={k:list(m.span(k)) for k in slots},pattern=row['id'],support=row['support']))
    if not matches:return None
    interpretations={json.dumps({k:v for k,v in m.items() if k in ('intent','stance','slots')},sort_keys=True) for m in matches}
    if len(interpretations)!=1:return dict(intent='ambiguous',source=source,interpretations=matches,model_sha256=model()[1])
    best=max(matches,key=lambda m:(m['support'],m['pattern']))
    return dict(best,source=source,model_sha256=model()[1],whole_clause_consumed=True,
                method='learned finite surface with open literal slots, count support; not arbitrary English semantics')
