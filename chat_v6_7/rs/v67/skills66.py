# v6.6 task skills: small rule / integer engines. Each returns None when unsure. All hand-written rules.
import re,os,sqlite3,subprocess,tempfile,json
from fractions import Fraction as F
import addons64 as A64
HERE=os.path.dirname(os.path.abspath(__file__))
# ---------- safety ----------
HARM=re.compile(r"\b(?:curse|hex|jinx|put a spell on)\s+(?:a |an |some|my |the |that )?(?:person|someone|somebody|him|her|them|neighbou?r|ex|enemy|boss|people|man|woman|guy|girl)|\bcurse (?:a|on a) person|\b(?:make|build|create|assemble|construct)\w*\s+(?:an? |the )?(?:improvised explosive|ied|pipe bomb|bomb|explosive|molotov|nerve agent|bioweapon|chemical weapon|ghost gun|meth(?:amphetamine)?)\b|\b(?:improvised explosive device|pipe bomb|molotov)\b|\bpoison (?:someone|somebody|a person|my|him|her|them)\b|\b(?:kill|murder|hurt|stab) (?:someone|somebody|a person|my \w+|him|her|them)\b|\bhack (?:into )?(?:someone|somebody|my ex|her|his|their)\b",re.I)
HARM_REPLY="I can't help with that. It could be used to harm someone, so I won't give materials or instructions for it. If you're in a conflict with someone, I'm happy to talk through safer ways to handle it."
DISTRESS=re.compile(r"\b(depress(?:ed|ion|ing)?|suicid\w*|kill myself|end my life|want to die|self[- ]harm\w*|cutting myself|hopeless|worthless|can'?t go on|no reason to live|panic attacks?|feel(?:ing)? (?:so |very |really |terribly )?(?:alone|empty|lonely|miserable))\b",re.I)
FIRSTP=re.compile(r"\b(i|i'm|i've|im|me|my)\b",re.I)
DISTRESS_REPLY=("I'm really sorry you're feeling this way. You don't have to deal with it alone. "
 "Talking to someone you trust, and to a doctor or mental-health professional, really can help: depression is common and treatable. "
 "Small steps can also help a little: regular sleep, some daily movement or time outside, and staying in touch with people. "
 "If you ever feel unsafe or think about hurting yourself, please contact your local emergency number right away, or a crisis line "
 "(for example 988 in the US, 116 123 Samaritans in the UK/Ireland, or findahelpline.com for other countries).")
def safety(text):
    if HARM.search(text): return HARM_REPLY,'harm_refusal'
    if DISTRESS.search(text) and FIRSTP.search(text) and not re.search(r"\b(the great depression|economic depression|depression era|tropical depression|write|essay|story|poem)\b",text,re.I):
        return DISTRESS_REPLY,'distress_support'
    return None
# ---------- request detector (no small-talk templates on tasks) ----------
REQ=re.compile(r"\b(ideas?|recipe|recipes|explain\w*|describe|define|tell me|want to know|i need|need (?:a|an|some|to know|help)|list|how|what|why|which|where|when|who|give|write|make|create|generate|help|tips?|recommend\w*|suggest\w*|instructions?|steps?|logo|outline|summar\w*|translate|calculate|convert|compare|difference|trend|mechanism|plan|guide|show|teach|find|example|examples|please|can you|could you|would you)\b|\?",re.I)
NARR=re.compile(r"^\W*(i|i'm|i am|i was|i've|i had|i just|i feel|my|we|our|today|yesterday|last \w+|this morning|so i|well,? i)\b",re.I)
def is_request(text):
    t=text.strip()
    if not REQ.search(t) and NARR.match(t): return False
    if NARR.match(t) and re.search(r"\b(was|were|had|went|got|did|felt|feel|am|'m)\b",t,re.I) and not re.search(r"\b(want to know|need|explain|recipe|ideas?|help|tell me|list|how (?:do|can|should) i|instructions|steps|please|can you|could you)\b",t,re.I): return False
    return True
# ---------- maths ----------
NUMW={'zero':0,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12,'twenty':20,'hundred':100}
def fmt(v):
    v=F(v)
    if v.denominator==1: return str(v.numerator)
    s=f"{float(v):.4f}".rstrip('0').rstrip('.');return s
def maths(text):
    t=text.strip();tl=t.lower()
    if len(t)>220: return None
    m=re.search(r"\b(\d+(?:\.\d+)?)\s*(?:%|percent) of (\d+(?:\.\d+)?)\b",tl)
    if m and len(re.findall(r"\d+(?:\.\d+)?",tl))==2:
        a,b=F(m.group(1)),F(m.group(2));return f"{fmt(a)}% of {fmt(b)} is {fmt(a*b/100)}.",'math_percent'
    m=re.search(r"\b(?:average|mean) of ([\d.,\s and-]+)",tl)
    if m:
        xs=[F(x) for x in re.findall(r"-?\d+(?:\.\d+)?",m.group(1))]
        if len(xs)>=2: return f"The average of {', '.join(fmt(x) for x in xs)} is {fmt(sum(xs)/len(xs))} (sum {fmt(sum(xs))} divided by {len(xs)}).",'math_average'
    m=re.search(r"(?:next (?:number|term)|comes next|continue)[^\d\[]*[\[(]?\s*(-?\d+(?:\s*,\s*-?\d+){3,})",tl) or re.search(r"(-?\d+(?:\s*,\s*-?\d+){3,})\s*,?\s*(?:\.\.\.|…|,\s*\?|\?)",tl)
    if m:
        xs=[int(x) for x in re.findall(r"-?\d+",m.group(1))]
        d=[b-a for a,b in zip(xs,xs[1:])]
        if len(set(d))==1: return f"The sequence goes up by {d[0]} each time, so the next number is {xs[-1]+d[0]}.",'math_sequence'
        if all(a!=0 for a in xs) and len({F(b,a) for a,b in zip(xs,xs[1:])})==1:
            r=F(xs[1],xs[0]);return f"Each number is {fmt(r)} times the one before, so the next number is {fmt(xs[-1]*r)}.",'math_sequence'
        return None
    # one-step word problems: exactly two numbers, one unambiguous operation keyword
    if re.search(r"\b(how many|how much|what is the total|in total|altogether|left|remain)\b",tl) and not re.search(r"[=^]",tl):
        ns=[F(x) for x in re.findall(r"\b\d+(?:\.\d+)?\b",tl)]
        if len(ns)!=2: return None
        a,b=ns
        ops=[]
        if re.search(r"\b(gives? away|gave away|ate|eats|spent|spends|loses|lost|sold|sells|left|remain\w*|takes? away|took away)\b",tl): ops.append(('-',a-b))
        if re.search(r"\b(more|another|additional|altogether|in total|total|buys? \d+ more|gets? \d+ more|plus)\b",tl) and not re.search(r"\beach\b|\bper\b",tl): ops.append(('+',a+b))
        if re.search(r"\b(each|per|every)\b",tl) and not re.search(r"\b(share|split|divide|equally)\b",tl): ops.append(('*',a*b))
        if re.search(r"\b(share\w*|split|divided? (?:equally|among|between)|equally)\b",tl) and b: ops.append(('/',a/b))
        if len(ops)!=1: return None
        o,v=ops[0]
        if v<0: return None
        return f"{fmt(a)} {o} {fmt(b)} = {fmt(v)}, so the answer is {fmt(v)}.",'math_word'
    return None
# ---------- logic: substitution puzzles ----------
def logic(text):
    tl=text.lower()
    m=re.match(r"\W*if (.+?)[.?,]\s*(?:then\s*)?what (?:colou?r|word|\w+)? ?(?:is|are|would be) (.+?)\??\s*$",tl)
    if not m: return None
    pairs=re.findall(r"([a-z]+) (?:is|means|=|equals) ([a-z]+)",m.group(1))
    if len(pairs)<2: return None
    mp=dict(pairs);qs=re.findall(r"[a-z]+",m.group(2));qs=[q for q in qs if q not in('and','the','a')]
    if not qs or any(q not in mp for q in qs): return None
    ans=[f"{q} is {mp[q]}" for q in qs]
    return "Using only the rules you gave: "+' and '.join(ans)+".",'logic_substitution'
# ---------- list / format ----------
def payload(text):
    m=re.search(r"[\"“']([^\"”']{1,400})[\"”']",text) or re.search(r":\s*(.+)$",text,re.S)
    return m.group(1).strip() if m else None
def fmt_task(text):
    tl=text.lower()
    m=re.search(r"how many (?:times (?:does|is) )?(?:the )?(?:letters? )?['\"]?([a-z])['\"]?(?:'?s)? (?:are |is |does )?(?:there )?(?:in|appear in)\s+(?:the word\s+)?['\"]?([a-z]+)",tl)
    if m: c=m.group(2).count(m.group(1));return f"There {'is' if c==1 else 'are'} {c} \"{m.group(1)}\" in \"{m.group(2)}\".",'count_letters'
    p=payload(text)
    if p is None: return None
    if re.search(r"\b(sort|alphabeti[sz]e|put .* in (?:alphabetical|ascending|descending) order|order)\b",tl):
        items=[x.strip() for x in re.split(r",|\n|;",p) if x.strip()]
        if len(items)<2: return None
        if all(re.fullmatch(r"-?\d+(?:\.\d+)?",x) for x in items): s=sorted(items,key=float,reverse='descend' in tl)
        else: s=sorted(items,key=str.lower,reverse='descend' in tl)
        return ', '.join(s),'list_sort'
    m=re.search(r"how many (?:times (?:does|is) )?(?:the )?(?:letter )?['\"]?([a-z])['\"]?s? (?:are )?(?:in|appear in|does)",tl)
    if m:
        w=re.search(r"\b(?:in|appear in)\s+(?:the word\s+)?['\"]?([A-Za-z]+)",text[m.start():])
        if w: c=w.group(1).lower().count(m.group(1));return f"There {'is' if c==1 else 'are'} {c} \"{m.group(1)}\" in \"{w.group(1)}\".",'count_letters'
    if re.search(r"\bcount (?:the )?(?:number of )?words\b|\bhow many words\b",tl): n=len(p.split());return f"That text has {n} word{'s' if n!=1 else ''}.",'count_words'
    if re.search(r"\bcount (?:the )?(?:number of )?(?:characters|letters)\b|\bhow many (?:characters|letters)\b",tl): return f"That text has {len(p)} characters (including spaces).",'count_chars'
    if re.search(r"\b(upper ?case|all caps|capital letters)\b",tl): return p.upper(),'case_upper'
    if re.search(r"\blower ?case\b",tl): return p.lower(),'case_lower'
    if re.search(r"\btitle case\b",tl): return p.title(),'case_title'
    if re.search(r"\breverse\b",tl): return p[::-1],'reverse'
    return None
# ---------- spreadsheet formula ----------
def sheet(text):
    tl=text.lower()
    if not re.search(r"\b(excel|spreadsheet|google sheets|sheets) formula\b|\bformula (?:in|for) (?:excel|google sheets)\b",tl): return None
    m=re.search(r"\bcolumn ([a-z]{1,2})\b",tl)
    ops=[(r"\baverage|\bmean",'AVERAGE'),(r"\bsum\b|\btotal\b",'SUM'),(r"\bmax(?:imum)?\b|\blargest|\bhighest",'MAX'),(r"\bmin(?:imum)?\b|\bsmallest|\blowest",'MIN'),(r"\bcount\b|\bhow many",'COUNT')]
    f=[o for r,o in ops if re.search(r,tl)]
    if not m or len(f)!=1: return None
    c=m.group(1).upper()
    return f"=" f"{f[0]}({c}:{c})\n\nThis {('averages','adds up','finds the largest value in','finds the smallest value in','counts the numbers in')[['AVERAGE','SUM','MAX','MIN','COUNT'][::1].index(f[0])]} column {c}. If the column has a header row, use a range like {f[0]}({c}2:{c}1000) instead.",'sheet_formula'
# ---------- translation (Tatoeba exact phrase table) ----------
LANG={'german':'deu','french':'fra','spanish':'spa','italian':'ita','portuguese':'por','dutch':'nld','russian':'rus'}
TDB=sqlite3.connect(os.path.join(HERE,'tatoeba66.sqlite'),check_same_thread=False)
def translate(text):
    t=text.strip();tl=t.lower()
    if not re.search(r"\btranslat\w*\b|\bhow (?:do|would) (?:you|i) say\b",tl): return None
    lm=re.search(r"\b(?:in|into|to)\s+("+'|'.join(LANG)+r")\b",tl)
    src=re.search(r"\bfrom\s+([a-z]+)",tl)
    if src and src.group(1)!='english':
        return f"Sorry, I can only translate short English phrases into a few languages using a licensed phrase table, not from {src.group(1).capitalize()}.",'translate_refuse'
    if not lm: return None
    p=payload(re.sub(r"\b(?:in|into|to)\s+\w+\s*:?\s*$","",t)) or payload(t)
    if not p:
        m=re.search(r"say ['\"]?(.+?)['\"]? in \w+",t,re.I);p=m and m.group(1)
    if not p: return None
    if len(p.split())>12: return "Sorry, that's too long for me to translate reliably. I can only translate short phrases that appear in my licensed phrase table.",'translate_refuse'
    key=re.sub(r'[^\w\s]','',p.lower()).strip()
    r=TDB.execute('select tx,sid,tid from tr where en=? and lang=? limit 1',(key,LANG[lm.group(1)])).fetchone()
    if not r: return f"Sorry, I don't have a reliable {lm.group(1).capitalize()} translation for \"{p}\". I only translate phrases that appear in my licensed phrase table, and I'd rather not guess.",'translate_refuse'
    return f"In {lm.group(1).capitalize()}: {r[0]}\n\n[Human translation from Tatoeba (CC BY 2.0 FR), sentences #{r[1]} -> #{r[2]}]",'translate'
# ---------- code (MBPP train/prompt, CC BY 4.0), tests run before answering ----------
import pyarrow.parquet as pq
MB=pq.read_table(os.path.join(HERE,'data/mbpp_train.parquet')).to_pylist()+pq.read_table(os.path.join(HERE,'data/mbpp_prompt.parquet')).to_pylist()
STOPC=set("write a an the to of in for and function program python code given that is from which list me please can you find check".split())
ct=lambda s:{w[:-1] if w.endswith('s') and len(w)>3 else w for w in re.findall(r"[a-z0-9]+",s.lower()) if w not in STOPC}
for r in MB: r['_t']=ct(r['text'])
OTHERL=re.compile(r"\b(c\+\+|c#|java|javascript|js|typescript|rust|go|golang|php|ruby|perl|kotlin|swift|bash|sql|excel|lua|delphi|unity)\b|\bin c\b",re.I)
def code(text,typ):
    tl=text.lower()
    if not re.search(r"\b(write|create|give me|show me|code|function|program|script|implement)\b",tl): return None
    if OTHERL.search(text): return None
    q=ct(text)
    if len(q)<2: return None
    best=None
    for r in MB:
        i=len(q&r['_t']);f=min(1000*i//len(q),1000*i//max(1,len(r['_t'])))
        if best is None or f>best[0]: best=(f,r)
    if best[0]<800: return None
    r=best[1];src=r['code'].replace('\r\n','\n').replace('\t','    ')
    prog=(r['test_setup_code'] or '')+'\n'+src+'\n'+'\n'.join(r['test_list'])+'\nprint("OK")\n'
    with tempfile.NamedTemporaryFile('w',suffix='.py',delete=False) as fh: fh.write(prog)
    try: ok=subprocess.run(['python3','-I',fh.name],capture_output=True,timeout=10,text=True).stdout.strip().endswith('OK')
    except Exception: ok=False
    os.unlink(fh.name)
    if not ok: return None
    return (f"Here is a Python version (it passes the {len(r['test_list'])} tests shown below):\n\n```python\n{src.strip()}\n\n"+'\n'.join(r['test_list'])+f"\n```\n\n[Human-written solution from MBPP task {r['task_id']} (CC BY 4.0), matched to: \"{r['text']}\"]",'code_mbpp')
def task(messages,typ):
    if len(messages)!=1: return None
    t=messages[-1]['content']
    for f in (translate,sheet,fmt_task,logic,maths):
        r=f(t)
        if r: return r
    return code(t,typ)
# ---------- odd one out (unit categories from the v6.4 unit table, hand-written) ----------
CAT={'inch':'length','inches':'length','foot':'length','feet':'length','yard':'length','mile':'length','meter':'length','metre':'length','centimeter':'length','centimetre':'length','millimeter':'length','kilometer':'length','kilometre':'length',
     'gram':'mass','kilogram':'mass','pound':'mass','ounce':'mass','ton':'mass','tonne':'mass','milligram':'mass',
     'liter':'volume','litre':'volume','gallon':'volume','pint':'volume','milliliter':'volume','quart':'volume',
     'second':'time','minute':'time','hour':'time','day':'time','week':'time','year':'time'}
def odd_one(text):
    tl=text.lower()
    if not re.search(r"\b(does not belong|doesn't belong|odd one out|which .* (?:is different|not like the others))\b",tl): return None
    ws=[w.rstrip('s') if w.rstrip('s') in CAT else w for w in re.findall(r"[a-z]+",tl)]
    ws=[w for w in ws if w in CAT]
    if len(ws)<3: return None
    from collections import Counter
    c=Counter(CAT[w] for w in ws)
    if len(c)!=2 or min(c.values())!=1: return None
    odd=[w for w in ws if c[CAT[w]]==1][0];maj=c.most_common(1)[0][0]
    return f"{odd.capitalize()} doesn't belong: it is a unit of {CAT[odd]}, while the others are units of {maj}.",'logic_odd_one'
_task=task
def task(messages,typ):
    if len(messages)==1:
        r=odd_one(messages[-1]['content'])
        if r: return r
    return _task(messages,typ)
