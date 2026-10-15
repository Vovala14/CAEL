# v6.7 rule-based semantic parser + Wikidata (CC0) integer-ID knowledge graph engine. Hand-written grammar; no NN.
import re,os,duckdb,datetime
HERE=os.path.dirname(os.path.abspath(__file__))
DB=duckdb.connect(os.path.join(HERE,'kg67.duckdb'),read_only=True)
def q1(sql,a): return DB.execute(sql,a).fetchall()
def out(s,p): return q1('select oq,olit from fact where s=? and p=?',[s,p])
def label(q):
    r=q1('select name from lbl where q=?',[q]);return r[0][0] if r else f"Q{q}"
def deg(q):
    r=q1('select n from pop where q=?',[q]);return r[0][0] if r else 0
def classes(q): return {o for o,_ in out(q,31) if o}
HUMAN=5
PLACE_CLS={6256,3624078,515,5119,1549591,515,7275,35657,10864048,107390,3336843,1637706,532,486972,23442,82794,8502,46831,4022,23397,1048835,15284,3957,200250,123705,5084,13218630}
def cands(name):
    n=re.sub(r"\s+"," ",name.strip().lower().strip(" ?.!\"'"))
    n=re.sub(r"^(the|a|an) ","",n)
    r=q1('select distinct q from lab where name=?',[n])
    if not r and not name.lower().startswith('the '): r=q1('select distinct q from lab where name=?',['the '+n])
    return [x[0] for x in r]
class Amb(Exception): pass
def resolve(name,want=None):
    C=cands(name)
    if not C: return None
    if want: 
        C2=[c for c in C if want(c)]
        C=C2 or []
        if not C: return None
    C=sorted(C,key=lambda c:-deg(c))
    if len(C)>1 and (deg(C[0])<3*deg(C[1]) or (deg(C[1])>=20 and deg(C[0])<5*deg(C[1]))): raise Amb(name)
    return C[0]
def is_human(q): return HUMAN in classes(q)
def is_placeish(q): return bool(out(q,17)) or bool(out(q,625)) or bool(classes(q)&PLACE_CLS)
def is_country(q): return bool(classes(q)&{6256,3624078,7275,3024240,1763527})
def is_work(q): return bool(out(q,50) or out(q,57) or out(q,170) or out(q,86) or out(q,175) or out(q,577))
# ---- literals
def date(lit):
    m=re.match(r'"([+-]?\d{1,4})-(\d\d)-(\d\d)T',lit or '')
    if not m: return None
    y,mo,d=int(m.group(1)),int(m.group(2)),int(m.group(3));return (y,mo,d)
MON=['January','February','March','April','May','June','July','August','September','October','November','December']
def fdate(t):
    y,m,d=t
    if y<0: return f"{-y} BC"
    if m==0: return str(y)
    if d==0: return f"{MON[m-1]} {y}"
    return f"{d} {MON[m-1]} {y}"
def num(lit):
    m=re.match(r'"([+-]?\d+(?:\.\d+)?)"',lit or '');return float(m.group(1)) if m else None
def fnum(v): return f"{int(v):,}" if v==int(v) else f"{v:,.2f}"
# ---- relations (noun phrase -> property, domain check, value kind)
REL={'capital':(36,None,'ent'),'capital city':(36,None,'ent'),'currency':(38,None,'ent'),'official language':(37,None,'ent'),'official languages':(37,None,'ent'),
 'population':(1082,None,'num'),'author':(50,is_work,'ent'),'writer':(50,is_work,'ent'),'director':(57,is_work,'ent'),'composer':(86,None,'ent'),'creator':(170,None,'ent'),'painter':(170,None,'ent'),
 'birthplace':(19,is_human,'ent'),'place of birth':(19,is_human,'ent'),'place of death':(20,is_human,'ent'),'date of birth':(569,is_human,'date'),'birthday':(569,is_human,'date'),'date of death':(570,is_human,'date'),
 'country':(17,None,'ent'),'continent':(30,None,'ent'),'mother':(25,is_human,'ent'),'father':(22,is_human,'ent'),'spouse':(26,is_human,'ent'),'wife':(26,is_human,'ent'),'husband':(26,is_human,'ent'),
 'founder':(112,None,'ent'),'headquarters':(159,None,'ent'),'performer':(175,None,'ent'),'highest point':(610,None,'ent'),'mouth':(403,None,'ent'),'nationality':(27,is_human,'ent'),'country of citizenship':(27,is_human,'ent'),
 'religion':(140,None,'ent'),'occupation':(106,is_human,'ent'),'architect':(84,None,'ent'),'manufacturer':(176,None,'ent'),'country of origin':(495,None,'ent'),'genre':(136,None,'ent'),
 'inception':(571,None,'date'),'founding date':(571,None,'date'),'publication date':(577,None,'date'),'release date':(577,None,'date')}
DATED_P={35,6,1082,54,108,39,26,169,1128,1308}
NP_REL=re.compile(r"^(?:the )?("+'|'.join(sorted(map(re.escape,REL),key=len,reverse=True))+r") of (.+)$",re.I)
NP_WHERE=re.compile(r"^(?:the )?(country|city|place|town) (?:where|in which) (.+?) (?:was born|died)$",re.I)
class Q:   # structured query
    def __init__(s,kind,**k): s.kind=kind;s.__dict__.update(k)
def parse_np(np_):
    np_=np_.strip().strip('?.! ')
    m=NP_WHERE.match(np_)
    if m:
        inner=parse_np(m.group(2));p=19 if 'born' in np_.lower() else 20
        chain=('rel',p,inner)
        return ('rel',17,chain) if m.group(1).lower()=='country' else chain
    m=NP_REL.match(np_)
    if m: return ('rel',REL[m.group(1).lower()][0],parse_np(m.group(2)))
    return ('ent',np_)
WH=[ # (pattern, builder) - hand-written grammar
 (r"^(?:what|which) (?:is|was|are|were) (?:the )?(.+? of .+?)$",lambda m:parse_np(m.group(1))),
 (r"^(?:what|which) (?:is|was) (.+?)'s (capital|currency|population|official language|birthday|birthplace|place of birth|date of birth|highest point)$",lambda m:('rel',REL[m.group(2)][0],parse_np(m.group(1)))),
 (r"^who (?:is|was) (?:the )?(author|writer|director|composer|creator|painter|founder|architect|mother|father|spouse|wife|husband|performer) of (.+)$",lambda m:('rel',REL[m.group(1)][0],parse_np(m.group(2)))),
 (r"^who (?:wrote|authored) (.+)$",lambda m:('rel',50,parse_np(m.group(1)))),
 (r"^who directed (.+)$",lambda m:('rel',57,parse_np(m.group(1)))),
 (r"^who (?:painted|created|sculpted) (.+)$",lambda m:('rel',170,parse_np(m.group(1)))),
 (r"^who (?:composed) (.+)$",lambda m:('rel',86,parse_np(m.group(1)))),
 (r"^who (?:founded) (.+)$",lambda m:('rel',112,parse_np(m.group(1)))),
 (r"^who (?:designed) (.+)$",lambda m:('rel',84,parse_np(m.group(1)))),
 (r"^where (?:was|is) (.+?) born$",lambda m:('rel',19,parse_np(m.group(1)))),
 (r"^where did (.+?) die$",lambda m:('rel',20,parse_np(m.group(1)))),
 (r"^when (?:was|is) (.+?) born$",lambda m:('rel',569,parse_np(m.group(1)))),
 (r"^when did (.+?) die$",lambda m:('rel',570,parse_np(m.group(1)))),
 (r"^when (?:was|were) (.+?) (?:founded|established|formed|created|built)$",lambda m:('rel',571,parse_np(m.group(1)))),
 (r"^when (?:was|were) (.+?) (?:published|released)$",lambda m:('rel',577,parse_np(m.group(1)))),
 (r"^(?:what|which) (?:currency does|money does) (.+?) use$",lambda m:('rel',38,parse_np(m.group(1)))),
 (r"^(?:what|which) (?:language|languages) (?:is|are) (?:spoken|used) in (.+)$",lambda m:('rel',37,parse_np(m.group(1)))),
 (r"^(?:what|which) continent is (.+?) (?:in|on|located in|part of)$",lambda m:('rel',30,parse_np(m.group(1)))),
 (r"^(?:what|which) country is (.+?) (?:in|located in|part of)$",lambda m:('rel',17,parse_np(m.group(1)))),
 (r"^(?:in )?(?:what|which) country (?:is|was) (.+?) (?:located|situated)?$",lambda m:('rel',17,parse_np(m.group(1)))),
 (r"^how many people live in (.+)$",lambda m:('rel',1082,parse_np(m.group(1)))),
 (r"^how old was (.+?) when (?:he|she|they) died$",lambda m:('age_death',parse_np(m.group(1)))),
 (r"^how many children did (.+?) have$",lambda m:('count',40,parse_np(m.group(1)))),
 (r"^how many (?:countries|nations) (?:border|share a border with) (.+)$",lambda m:('count',47,parse_np(m.group(1)))),
 (r"^how many official languages does (.+?) have$",lambda m:('count',37,parse_np(m.group(1)))),
 (r"^who (?:is|was) older,? (.+?) or (.+)$",lambda m:('cmp',569,'older',parse_np(m.group(1)),parse_np(m.group(2)))),
 (r"^who (?:is|was) younger,? (.+?) or (.+)$",lambda m:('cmp',569,'younger',parse_np(m.group(1)),parse_np(m.group(2)))),
 (r"^(?:which|what) (?:\w+ )?(?:is|has) (?:more populous|a (?:bigger|larger) population|more people),? (.+?) or (.+)$",lambda m:('cmp',1082,'more populous',parse_np(m.group(1)),parse_np(m.group(2)))),
 (r"^(?:which|what) (?:\w+ )?is (?:taller|higher),? (.+?) or (.+)$",lambda m:('cmp',2044,'higher',parse_np(m.group(1)),parse_np(m.group(2)))),
 (r"^(?:which|what) (?:\w+ )?is (?:bigger|larger),? (.+?) or (.+)$",lambda m:('cmp',2046,'larger (by area)',parse_np(m.group(1)),parse_np(m.group(2)))),
 (r"^(?:which|what) (?:\w+ )?is longer,? (.+?) or (.+)$",lambda m:('cmp',2043,'longer',parse_np(m.group(1)),parse_np(m.group(2)))),
]
WH=[(re.compile(a,re.I),b) for a,b in WH]
def parse(text):
    t=text.strip()
    if len(t)>160 or '\n' in t: return None
    t=re.sub(r"^\W*(?:hi|hello|hey)[,!.]*\s*","",t,flags=re.I)
    t=re.sub(r"^(?:(?:can|could) you (?:please )?tell me|do you know|please tell me|tell me)\s*,?\s*","",t,flags=re.I).strip().rstrip('?.! ')
    for r,b in WH:
        m=r.match(t)
        if m: return b(m)
    return None
DOM={36:lambda q:not is_human(q),38:lambda q:not is_human(q),37:lambda q:not is_human(q),1082:lambda q:not is_human(q),19:is_human,20:is_human,569:is_human,570:is_human,22:is_human,25:is_human,26:is_human,27:is_human,40:is_human,
     50:is_work,57:is_work,30:lambda q:not is_human(q),17:lambda q:not is_human(q),47:lambda q:not is_human(q)}
class Refuse(Exception): pass
def ev(node,prov,want=None):
    """returns list of (oq,olit) values."""
    if node[0]=='ent':
        q=resolve(node[1],want)
        if q is None: raise Refuse(f"I couldn't find \"{node[1]}\" in my knowledge graph.")
        prov.append(f"Q{q} ({label(q)})");return [(q,None)]
    _,p,inner=node
    dom=DOM.get(p)
    if inner[0]=='ent' and dom is is_human and len(inner[1].split())==1: raise Refuse('single-name person')
    want=(lambda q,d=dom,p=p: bool(out(q,p)) and (d is None or d(q))) if inner[0]=='ent' else dom
    subj=ev(inner,prov,want)
    if len(subj)!=1 or subj[0][0] is None: raise Refuse("That chain doesn't lead to a single thing I can look up.")
    s=subj[0][0];vals=out(s,p)
    if not vals: raise Refuse(f"Wikidata has no {pname(p)} for {label(s)}.")
    prov.append(f"Q{s} P{p}");return vals
PN={36:'capital',38:'currency',37:'official language',1082:'population',50:'author',57:'director',86:'composer',170:'creator',19:'place of birth',20:'place of death',569:'date of birth',570:'date of death',
    17:'country',30:'continent',25:'mother',22:'father',26:'spouse',112:'founder',159:'headquarters',175:'performer',610:'highest point',403:'mouth',27:'country of citizenship',140:'religion',106:'occupation',
    84:'architect',176:'manufacturer',495:'country of origin',136:'genre',571:'founding date',577:'publication date',40:'children',47:'neighbouring countries',2044:'elevation',2046:'area',2043:'length'}
def pname(p): return PN.get(p,f"P{p}")
def render_vals(vals,p):
    out_=[]
    for oq,ol in vals[:6]:
        if oq: out_.append(label(oq))
        elif p in(569,570,571,577): d=date(ol);out_.append(fdate(d) if d else None)
        else: v=num(ol);out_.append(fnum(v) if v is not None else None)
    out_=list(dict.fromkeys(x for x in out_ if x))
    if not out_: raise Refuse("unrenderable")
    return out_[0] if len(out_)==1 else ', '.join(out_[:-1])+' and '+out_[-1]
def subj_text(node):
    if node[0]=='ent': return node[1].strip()
    return f"the {pname(node[1])} of {subj_text(node[2])}"
def answer(text):
    qy=parse(text)
    if qy is None: return None
    prov=[]
    try:
        if qy[0]=='rel':
            p=qy[1]
            if p in DATED_P and p!=1082: return None
            vals=ev(qy,prov);r=render_vals(vals,p)
            s=subj_text(qy[2])
            if p==1082: msg=f"Wikidata's most recent population figure for {s} is {r}. Populations change, so treat it as approximate."
            elif p in(569,570,571,577): msg=f"The {pname(p)} of {s} is {r}."
            else: msg=f"The {pname(p)} of {s} {'is' if len({v for v in vals})==1 else 'are'} {r}."
        elif qy[0]=='count':
            p=qy[1];vals=ev(('rel',p,qy[2]),prov);n=len({v for v in vals})
            msg=f"According to Wikidata, {subj_text(qy[2])} has {n} {pname(p) if n!=1 else pname(p).rstrip('s')}."
        elif qy[0]=='age_death':
            b=ev(('rel',569,qy[1]),prov);d=ev(('rel',570,qy[1]),prov)
            if len(b)!=1 or len(d)!=1: raise Refuse('x')
            b,d=date(b[0][1]),date(d[0][1])
            if not b or not d or b[1]==0 or d[1]==0 or b[0]<0: raise Refuse('x')
            age=d[0]-b[0]-((d[1],d[2])<(b[1],b[2]))
            msg=f"{subj_text(qy[1])} was {age} when they died (born {fdate(b)}, died {fdate(d)})."
        elif qy[0]=='cmp':
            _,p,word,a,b=qy;va=[];names=[]
            for x in (a,b):
                pv=[];v=ev(('rel',p,x),pv) if True else None;prov+=pv
                if len(v)!=1: raise Refuse('x')
                val=date(v[0][1]) if p==569 else num(v[0][1])
                if val is None: raise Refuse('x')
                va.append(val);names.append(subj_text(x))
            if p in(2044,2046,2043):   # units are not in the truthy dump: only compare same-class items
                qa=resolve(a[1]) if a[0]=='ent' else None;qb=resolve(b[1]) if b[0]=='ent' else None
                if not qa or not qb or not (classes(qa)&classes(qb)): raise Refuse('x')
            if va[0]==va[1]: raise Refuse('tie')
            if p==569: win=0 if (va[0]<va[1])==(word=='older') else 1;msg=f"{names[win]} is {word}: born {fdate(va[win])}, versus {fdate(va[1-win])} for {names[1-win]}."
            else: win=0 if va[0]>va[1] else 1;msg=f"{names[win]} is {word}, according to Wikidata's figures."
        else: return None
    except Amb as e:
        return (f"\"{e.args[0]}\" could mean more than one thing in my knowledge graph, so I'd rather not guess. Could you be more specific?",'kg_ambiguous')
    except Refuse:
        return None
    msg=msg[0].upper()+msg[1:]
    return (msg+f"\n\n[Source: Wikidata (CC0), facts {', '.join(dict.fromkeys(prov))}]",'kg_'+qy[0])
