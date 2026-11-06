"""Fitted compositional property/expression/action grammar for general memory.

Role ontology, finite expression algebra and ambiguity gates are architectural
priors. Frame words/operation choices and a comment classifier are supervised.
No benchmark name, task header, variable vocabulary or renderer is used here.
"""
from collections import Counter
from fractions import Fraction
from functools import lru_cache
import json,math,re
from pathlib import Path

MODEL=Path(__file__).with_name('state_language_model.json')
NUMBER=r'-?\d+(?:/\d+|\.\d+)?'
NEGATIVE=r'\b(?:if|unless|might|maybe|could|said|says|claimed|claims|not|never)\b'

def clean(text):
    text=re.sub(r'\s+',' ',str(text).replace('\u2019',"'").strip()).strip(' .!?;:')
    return re.sub(r'^(?:the|a|an)\s+','',text,flags=re.I)

@lru_cache(maxsize=4096)
def compile_frame(frame,aliases=(),length_role='',length=0):
    used=set();parts=[];pos=0
    for match in re.finditer(r'\{\{([A-Z]+)\}\}|\^([^\^]+)\^',frame):
        parts.append(re.escape(frame[pos:match.start()]).replace(r'\ ',r'\s+'))
        role,anchor=match.groups()
        if anchor:
            words=sorted(set([anchor,*aliases]),key=lambda s:-len(s))
            parts.append('(?:'+'|'.join(re.escape(s).replace(r'\ ',r'\s+') for s in words)+')')
        elif role in used:parts.append('(?P='+role+')')
        else:
            content=NUMBER if role in ('D','M') else r'[^;\n!?]{1,240}?'
            if role==length_role:content=r'[^;\n!?]{'+str(length)+'}'
            parts.append('(?P<'+role+'>'+content+')');used.add(role)
        pos=match.end()
    parts.append(re.escape(frame[pos:]).replace(r'\ ',r'\s+'))
    return re.compile(''.join(parts),re.I)

def features(text):
    words=re.findall(r"[a-z]+|\d+",text.casefold())
    return set('w:'+('#' if w.isdigit() else w) for w in words)

def prepare(data):
    for kind in ('property','expression','event','question'):
        entries=[]
        for row in data[kind]:
            row=dict(row);row['compiled']=compile_frame(row['frame'],tuple(row.get('aliases',())))
            # Each fixed literal token must occur in a matching clause. This
            # cheap exact gate changes no accepted language and saves regex work.
            literal=re.sub(r'\{\{[A-Z]+\}\}|\^[^\^]+\^',' ',row['frame'])
            row['required']=set(re.findall(r'[a-z]+',literal.casefold()))
            anchors=re.findall(r'\^([^\^]+)\^',row['frame'])
            row['anchor_tokens']=set(re.findall(r'[a-z]+',' '.join([*anchors,*row.get('aliases',())]).casefold()))
            entries.append(row)
        data['_'+kind]=entries
    return data

@lru_cache(maxsize=1)
def model():return prepare(json.loads(MODEL.read_text(encoding='utf-8')))

def matches(kind,text,data=None):
    data=data or model();tokens=set(re.findall(r'[a-z]+',text.casefold()));out=[]
    for row in data['_'+kind]:
        if not row['required']<=tokens:continue
        if row['anchor_tokens'] and not row['anchor_tokens'] & tokens:continue
        matched=row['compiled'].fullmatch(text)
        if matched:
            candidates=[matched]
            roles=set(matched.groupdict())
            split_roles=[]
            for left,right in re.findall(r'\{\{([A-Z]+)\}\}\s+\{\{([A-Z]+)\}\}',row['frame']):
                if left in ('E','X','T'):split_roles.append(left)
            after=re.search(r'\{\{T\}\}([^{}]+)\{\{X\}\}',row['frame'])
            if after and text.casefold().count(after[1].casefold())>1:split_roles.append('T')
            for role in set(split_roles):
                start=matched.start(role)
                ends=[i for i in range(start+1,min(len(text),start+240)) if text[i].isspace()]
                for end in ends:
                    alternative=compile_frame(row['frame'],tuple(row.get('aliases',())),role,end-start).fullmatch(text)
                    if alternative:candidates.append(alternative)
            seen=set()
            for found in candidates:
                slots={k:v.strip() for k,v in found.groupdict().items() if v is not None}
                signature=json.dumps(slots,sort_keys=True)
                if signature not in seen:out.append((row,slots));seen.add(signature)
    return out

def property_phrase(text,focus=(),data=None):
    text=re.sub(r'\s+',' ',str(text).replace('\u2019',"'").strip()).strip(' .!?;:');possessives={'its','his','her','their'}
    choices=[]
    for row,slots in matches('property',text,data):
        entity=slots.get('E');attribute=slots.get('A',row.get('attribute','value'))
        if 'P' in slots:
            if slots['P'].casefold() not in possessives:continue
            if len(set(focus))!=1:raise ValueError('A pronoun has no unique stated antecedent')
            entity=next(iter(focus))
        if not entity:continue
        entity=clean(entity);attribute=clean(attribute)
        if re.search(r'\b(?:and|or|if|unless)\b',entity,re.I):continue
        if len(entity)>120 or len(attribute)>100:continue
        if re.search(r'\b(?:plus|minus|modulo|and|less than)\b',attribute+' '+entity,re.I):continue
        choices.append((row['specificity'],entity,attribute))
    if not choices:
        if not re.fullmatch(r'[\w -]{1,80}',text):raise ValueError('Unsupported complete property phrase')
        if text.casefold() in ('it','he','she','they'):
            if len(set(focus))!=1:raise ValueError('A pronoun has no unique stated antecedent')
            return next(iter(focus)),'value'
        return text,'value'
    best=max(c[0] for c in choices)
    selected={(clean(e),clean(a)) for s,e,a in choices if s==best}
    if len(selected)!=1:raise ValueError('Ambiguous complete property phrase')
    return next(iter(selected))

def expression(text,focus=(),data=None,depth=0):
    if depth>8:raise ValueError('Expression nesting bound')
    text=text.strip()
    if text.startswith('"') and text.endswith('"'):
        value=json.loads(text)
        if not isinstance(value,str):raise ValueError('Quoted state value must be text')
        return {'op':'literal','value':value}
    if text.startswith("'") and text.endswith("'") and text.count("'")==2:return {'op':'literal','value':text[1:-1]}
    if re.fullmatch(NUMBER,text):return {'op':'literal','value':str(Fraction(text))}
    outcomes=[]
    for row,slots in matches('expression',text,data):
        op=row['operation']
        if op=='reference':
            if 'T' in slots:e,a=property_phrase(slots['T'],focus,data)
            else:e,a=clean(slots['S']),clean(slots.get('A',row.get('attribute','value')))
            # A reference must consume one property, rather than swallowing
            # a surrounding arithmetic expression into its attribute name.
            if re.search(r'\b(?:plus|minus|modulo|and|less than)\b',a+' '+e,re.I):continue
            node={'op':'reference','entity':e,'attribute':a}
        else:
            child=expression(slots['X'],focus,data,depth+1)
            node={'op':op,'child':child}
            if 'D' in slots:node['delta']=str(Fraction(slots['D']))
            if 'M' in slots:node['modulus']=str(Fraction(slots['M']))
        outcomes.append((row['specificity'],node))
    if outcomes:
        best=max(v[0] for v in outcomes)
        selected={json.dumps(node,sort_keys=True) for score,node in outcomes if score==best}
        if len(selected)!=1:raise ValueError('Ambiguous complete value expression')
        return json.loads(selected.pop())
    if re.fullmatch(r'[\w-]{1,120}',text) and text.casefold() not in {'unknown','same','current','missing','either','the','a','an'}:
        return {'op':'literal','value':text}
    raise ValueError('Unsupported complete value expression')

def evaluate(node,state,resolver,key):
    op=node['op']
    if op=='literal':return node['value']
    if op=='reference':return resolver(state,key(node['entity'],node['attribute']))
    value=Fraction(evaluate(node['child'],state,resolver,key))
    if op=='add':return str(value+Fraction(node['delta']))
    if op=='subtract':return str(value-Fraction(node['delta']))
    if op=='modulo':
        m=Fraction(node['modulus'])
        if m<=0:raise ValueError('A cycle length must be positive')
        return str(value%m)
    raise ValueError('Unsupported fitted expression operation')

def canonical(row,slots,focus=(),data=None):
    if 'T' in slots:e,a=property_phrase(slots['T'],focus,data)
    else:e,a=clean(slots['E']),clean(slots.get('A',row.get('attribute','value')))
    if e.casefold() in {'it','he','she','they'}:
        if len(set(focus))!=1:raise ValueError('A pronoun has no unique stated antecedent')
        e=next(iter(focus))
    out={'E':e,'A':a}
    if not re.fullmatch(r'[\w -]{1,120}',e) or not re.fullmatch(r'[\w -]{1,100}',a):raise ValueError('Unsupported owner or property')
    if re.search(r'\b(?:of|for|belonging|recorded|plus|minus|modulo|and)\b',a,re.I):raise ValueError('Unresolved property boundary')
    if re.search(r'\b(?:if|unless|and|or)\b',e,re.I):raise ValueError('Unresolved compound owner')
    if 'X' in slots:out['EXPR']=expression(slots['X'],focus,data)
    for role in ('D','M'):
        if role in slots:out[role]=slots[role]
    return row['operation'],out

def event(text,focus=(),data=None,state=None):
    data=data or model();text=text.strip()
    text=re.sub(r'^(?:then|afterward|afterwards|subsequently|next|later|please)[,:]?\s+','',text,flags=re.I)
    outside=re.sub(r'"[^"\n]*"','',text)
    if re.search(NEGATIVE,outside,re.I):return None
    outcomes=[]
    for row,slots in matches('event',text,data):
        try:op,values=canonical(row,slots,focus,data)
        except (ValueError,KeyError,ZeroDivisionError):continue
        binding=0
        if state is not None:
            known_entities={k.split('\x1f')[0] for k in state}
            binding+=int(clean(values['E']).casefold() in known_entities)
            binding+=int(clean(values['E']).casefold()+'\x1f'+clean(values['A']).casefold() in state)
            node=values.get('EXPR',{})
            while node:
                if node.get('op')=='reference':binding+=int(clean(node['entity']).casefold()+'\x1f'+clean(node['attribute']).casefold() in state)
                node=node.get('child')
        outcomes.append(((row['specificity'],binding),op,values))
    if not outcomes:return None
    best=max(x[0] for x in outcomes)
    selected={(op,json.dumps(values,sort_keys=True)) for score,op,values in outcomes if score==best}
    if len(selected)!=1:raise ValueError('Ambiguous fitted action')
    op,values=selected.pop();return op,json.loads(values)

def question(text,data=None):
    text=clean(text)
    options=[]
    for row,slots in matches('question',text,data):
        if row['operation']=='all':q={'kind':'all','past':False}
        elif 'T' in slots:q={'kind':'one_phrase','phrase':slots['T'],'past':False}
        else:q={'kind':'one','E':clean(slots['E']),'A':row.get('attribute','value'),'past':False}
        options.append((row['specificity'],q))
    if not options:return None
    best=max(v[0] for v in options);choices={json.dumps(v,sort_keys=True) for score,v in options if score==best}
    if len(choices)!=1:return None
    return json.loads(choices.pop())

def comment(text,names=(),data=None):
    data=data or model();classifier=data['comment_classifier'];f=features(text)
    # A discourse score cannot erase an apparent action, condition or quoted
    # assertion. Alias phrases come from teaching, not from test vocabulary.
    if re.search(NEGATIVE,text,re.I) or "'s" in text or '"' in text:return False
    lowered=text.casefold()
    for row in data['event']:
        for anchor in [*re.findall(r'\^([^\^]+)\^',row['frame']),*row.get('aliases',())]:
            if re.search(r'\b'+re.escape(anchor)+r'\b',lowered):return False
    known={w.casefold() for name in names for w in re.findall(r'\w+',name) if len(w)>2}
    tokens={w[2:] for w in f}
    if known & tokens:return False
    # Only learned positive discourse cues can authorize omission. Absence of
    # a recognized action never makes an unknown sentence a harmless comment.
    cue=f & set(classifier['positive_cues'])
    if not cue:return False
    margin=classifier['bias']+sum(classifier['weights'].get(x,0) for x in f)
    return margin>=classifier['threshold']
