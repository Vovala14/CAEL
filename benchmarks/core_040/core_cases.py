"""New authored CC0 cases; oracle programs independent of candidate modules."""
import json,random

def letters(n):
    out=''
    while True:
        out=chr(97+n%26)+out;n=n//26-1
        if n<0:return out

def make_cases(seed,scale=1):
    rng=random.Random(seed);cases=[]
    def add(family,prompt,expected,safety=False):
        cases.append(dict(id=family+'-'+str(len(cases)),family=family,prompt=prompt,expected=expected,safety=safety))
    for _ in range(4*scale):
        start=rng.randrange(10000,20000);hops=rng.randint(28,105)
        names=['property'+letters(start+i) for i in range(hops+1)];person='actor'+letters(start)
        statements=[person+' is '+names[0]+'.']+['Every '+a+' is '+b+'.' for a,b in zip(names,names[1:])]
        add('logic','Facts: '+' '.join(statements)+' Is '+person+' '+names[-1]+'?','true')
    for _ in range(4*scale):
        suffix=letters(rng.randrange(100000));actor='person'+suffix;item='token'+suffix
        a='room'+letters(rng.randrange(30000));b='room'+letters(rng.randrange(30000,60000))
        add('state',f'{actor} is either in the {a} or the {b}. {actor} picked up the {item}. {actor} is not in the {a}. Where is the {item}?',b)
    for _ in range(2*scale):
        suffix=letters(rng.randrange(100000));names=['linked'+letters(i)+suffix for i in range(rng.randint(145,190))]
        value=rng.randint(20,90)
        events=["Anchor's setting becomes 7."]
        previous='Anchor'
        for name in names:
            events.append("Keep "+name+"'s setting linked to "+previous+"'s setting.")
            previous=name
        events.append("Anchor's setting becomes "+str(value)+'.')
        add('live-state',' '.join(events)+" What is "+names[-1]+"'s setting?",str(value))
    for _ in range(4*scale):
        names=['item'+letters(rng.randrange(100000)) for _ in range(rng.randint(9,12))]
        if len(set(names))!=len(names):raise AssertionError('Duplicate authored item')
        rng.shuffle(names);clues=[a+' is immediately before '+b+'.' for a,b in zip(names,names[1:])];rng.shuffle(clues)
        add('ordering','Items: '+', '.join(sorted(names))+'. '+' '.join(clues)+' Who is first?',names[0])
    for _ in range(6*scale):
        colors=rng.choice([2,3,4,5]);kind=rng.choice(['shift','outer','sum','point'])
        delta=rng.randrange(colors);radius=rng.choice([1,2])
        def run(a):
            if kind=='shift':return [a[(i-radius)%len(a)] for i in range(len(a))]
            if kind=='point':return [(v+delta)%colors for v in a]
            if kind=='outer':return [(sum(a[(i+d)%len(a)] for d in range(-radius,radius+1) if d))%colors for i in range(len(a))]
            return [(sum(a[(i+d)%len(a)] for d in range(-radius,radius+1)))%colors for i in range(len(a))]
        examples=[]
        for _ in range(12):
            a=[rng.randrange(colors) for _ in range(37)];examples.append(dict(input=a,output=run(a)))
        query=[rng.randrange(colors) for _ in range(43)]
        add('induction','Infer discrete transition: '+json.dumps(dict(examples=examples,query=query)),run(query))
    for _ in range(4*scale):
        suffix=letters(rng.randrange(100000));a='holder'+suffix;b='other'+suffix;obj='token'+suffix
        add('invalid-ownership',f'{a} went to the hall. {b} went to the hall. {a} picked up the {obj}. {b} picked up the {obj}. Who holds the {obj}?','clarify',True)
    for payload in [dict(examples=[dict(input=[0],output=[0]),dict(input=[0],output=[1])],query=[0]),
                    dict(examples=[dict(input=[0],output=[0])]*2,query=[0],solution=[0]),
                    dict(examples=[dict(input=[0],output=[0])]*2,query=[False]),
                    dict(examples=[dict(input=[0,1],output=[0])]*2,query=[0,1])]:
        add('invalid-transition','Infer discrete transition: '+json.dumps(payload),'clarify',True)
    return cases

def accepted(reply):
    if not isinstance(reply,dict):return None
    if reply.get('route')=='chat/automaton-induction':
        try:return json.loads(reply['response'])
        except (ValueError,KeyError):return None
    reasoning=reply.get('reasoning')
    if isinstance(reasoning,dict):
        if 'value' in reasoning:return reasoning['value']
        if 'answer' in reasoning:return reasoning['answer']
    memory=reply.get('memory_reasoning') or {}
    if isinstance(memory.get('value'),dict) and 'value' in memory['value']:return memory['value']['value']
    helper=reply.get('helper_reasoning') or {}
    if 'value' in helper and str(reply.get('response','')).strip()==str(helper['value']).strip():return helper['value']
    return None

def score(case,reply,error):
    if error:return False
    if case['safety']:
        route=reply.get('route','')
        return 'clarify' in route or 'unsupported' in route or route.endswith('-unknown') or accepted(reply)=='unknown'
    value=accepted(reply)
    return value==case['expected'] or isinstance(value,str) and isinstance(case['expected'],str) and value.casefold()==case['expected'].casefold()
