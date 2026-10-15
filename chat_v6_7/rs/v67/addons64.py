# v6.4 add-ons: exact arithmetic/unit conversion, dated-fact guard, Wikipedia exact-title definition lookup. Non-CA, disclosed.
import re,json,os,urllib.request,urllib.parse
from fractions import Fraction as F
HERE=os.path.dirname(os.path.abspath(__file__))
# ---------- (a) arithmetic ----------
WORDOP={' plus ':'+',' minus ':'-',' times ':'*',' multiplied by ':'*',' divided by ':'/',' over ':'/','x':'*'}
def _tok(e):
    return re.findall(r"\d+(?:\.\d+)?|[-+*/^()]",e)
def _num(t): return F(t)
def eval_rd(ts):   # recursive descent
    pos=[0]
    def peek(): return ts[pos[0]] if pos[0]<len(ts) else None
    def eat(): pos[0]+=1;return ts[pos[0]-1]
    def atom():
        t=peek()
        if t=='(':
            eat();v=expr()
            if eat()!=')': raise ValueError
            return v
        if t=='-': eat();return -atom()
        if t is None or not re.fullmatch(r"\d+(?:\.\d+)?",t): raise ValueError
        return _num(eat())
    def power():
        b=atom()
        if peek()=='^':
            eat();e=power()
            if e.denominator!=1 or abs(e)>64: raise ValueError
            return b**int(e)
        return b
    def term():
        v=power()
        while peek() in('*','/'):
            o=eat();r=power()
            if o=='/' and r==0: raise ZeroDivisionError
            v=v*r if o=='*' else v/r
        return v
    def expr():
        v=term()
        while peek() in('+','-'):
            o=eat();r=term();v=v+r if o=='+' else v-r
        return v
    v=expr()
    if pos[0]!=len(ts): raise ValueError
    return v
def eval_shunt(ts):   # independent second path: shunting-yard to RPN
    prec={'+':1,'-':1,'*':2,'/':2,'^':3,'u':4};out=[];st=[];prev=None
    for t in ts:
        if re.fullmatch(r"\d+(?:\.\d+)?",t): out.append(F(t))
        elif t=='(': st.append(t)
        elif t==')':
            while st and st[-1]!='(': out.append(st.pop())
            if not st: raise ValueError
            st.pop()
        else:
            if t=='-' and (prev is None or prev in prec or prev=='('): t='u'
            while st and st[-1]!='(' and (prec[st[-1]]>prec[t] or (prec[st[-1]]==prec[t] and t not in('^','u'))): out.append(st.pop())
            st.append(t)
        prev=t
    while st:
        o=st.pop()
        if o=='(': raise ValueError
        out.append(o)
    s=[]
    for x in out:
        if isinstance(x,F): s.append(x)
        elif x=='u': s.append(-s.pop())
        else:
            b=s.pop();a=s.pop()
            if x=='^':
                if b.denominator!=1 or abs(b)>64: raise ValueError
                s.append(a**int(b))
            elif x=='/':
                if b==0: raise ZeroDivisionError
                s.append(a/b)
            else: s.append(a+b if x=='+' else a-b if x=='-' else a*b)
    if len(s)!=1: raise ValueError
    return s[0]
def fmt(v):
    if v.denominator==1: return f"{v.numerator:,}" if abs(v.numerator)>=10000 else str(v.numerator)
    d=float(v)
    return f"{v.numerator}/{v.denominator} (about {d:.6g})"
def arithmetic(text):
    tl=text.lower().strip()
    m=re.fullmatch(r"\W*(?:what(?:'s| is)|calculate|compute|evaluate|how much is|solve)?\s*([0-9.\s+\-*/^()x]+|[0-9.]+(?:\s+(?:plus|minus|times|multiplied by|divided by|over)\s+[0-9.]+)+)\s*(?:=\s*)?\??\s*",tl)
    if not m: return None
    e=' '+m.group(1)+' '
    for k,v in WORDOP.items():
        if k!='x': e=e.replace(k,v)
    e=re.sub(r"(?<=\d)\s*x\s*(?=\d)","*",e)
    if re.search(r"[a-z]",e): return None
    ts=_tok(e)
    if len([t for t in ts if t in '+-*/^'])<1 or len(ts)<3: return None
    try: a=eval_rd(ts);b=eval_shunt(ts)
    except Exception: return None
    if a!=b: return None
    return f"{' '.join(ts)} = {fmt(a)}"
# ---------- unit conversion ----------
U={'km':('len',F(1000)),'kilometer':('len',F(1000)),'kilometre':('len',F(1000)),'m':('len',F(1)),'meter':('len',F(1)),'metre':('len',F(1)),
   'cm':('len',F(1,100)),'centimeter':('len',F(1,100)),'mm':('len',F(1,1000)),'mile':('len',F(1609344,1000)),'mi':('len',F(1609344,1000)),
   'foot':('len',F(3048,10000)),'feet':('len',F(3048,10000)),'ft':('len',F(3048,10000)),'inch':('len',F(254,10000)),'inches':('len',F(254,10000)),'in':('len',F(254,10000)),
   'yard':('len',F(9144,10000)),'yd':('len',F(9144,10000)),
   'kg':('mass',F(1)),'kilogram':('mass',F(1)),'g':('mass',F(1,1000)),'gram':('mass',F(1,1000)),'lb':('mass',F(45359237,100000000)),'lbs':('mass',F(45359237,100000000)),'pound':('mass',F(45359237,100000000)),
   'ounce':('mass',F(28349523125,1000000000000)),'oz':('mass',F(28349523125,1000000000000)),'ton':('mass',F(1000)),'tonne':('mass',F(1000)),
   'l':('vol',F(1)),'liter':('vol',F(1)),'litre':('vol',F(1)),'ml':('vol',F(1,1000)),'milliliter':('vol',F(1,1000)),'gallon':('vol',F(3785411784,1000000000)),'gal':('vol',F(3785411784,1000000000)),
   'cup':('vol',F(2365882365,10000000000))}
TEMP={'c':'C','celsius':'C','f':'F','fahrenheit':'F','k':'K','kelvin':'K'}
def _unit(w):
    w=w.lower().strip('.').replace('degrees ','').replace('degree ','')
    if w in TEMP: return ('temp',TEMP[w])
    if w in U: return U[w]
    if w.endswith('es') and w[:-2] in U: return U[w[:-2]]
    if w.endswith('s') and w[:-1] in U: return U[w[:-1]]
    return None
def tempconv(v,a,b):
    k={'C':lambda x:x+F(27315,100),'F':lambda x:(x-32)*F(5,9)+F(27315,100),'K':lambda x:x}[a](v)
    return {'C':lambda x:x-F(27315,100),'F':lambda x:(x-F(27315,100))*F(9,5)+32,'K':lambda x:x}[b](k)
def convert(text):
    tl=text.lower()
    m=re.search(r"(?:convert |how many |what is |what's )?(-?\d+(?:\.\d+)?)\s*(?:degrees? )?([a-z]+)\s+(?:to|in|into)\s+(?:degrees? )?([a-z]+)\b",tl)
    if not m:
        m2=re.search(r"how many ([a-z]+) (?:are )?in (?:a |an |one )?(-?\d+(?:\.\d+)?)?\s*([a-z]+)\b",tl)
        if not m2: return None
        v=F(m2.group(2) or '1');ua,ub=_unit(m2.group(3)),_unit(m2.group(1));sa,sb=m2.group(3),m2.group(1)
    else:
        v=F(m.group(1));ua,ub=_unit(m.group(2)),_unit(m.group(3));sa,sb=m.group(2),m.group(3)
    if not ua or not ub or ua[0]!=ub[0]: return None
    r=tempconv(v,ua[1],ub[1]) if ua[0]=='temp' else v*ua[1]/ub[1]
    r2=(tempconv(r,ub[1],ua[1]) if ua[0]=='temp' else r*ub[1]/ua[1])  # verification: convert back
    if r2!=v: return None
    d=float(r);out=f"{d:.4g}" if abs(d)<1e6 else f"{d:,.0f}"
    return f"{fmt(v) if v.denominator!=1 else v.numerator} {sa} is about {out} {sb}."
# ---------- (b) dated-fact guard ----------
DATED=re.compile(r"\b(who is|who's|who are) (?:the )?(?:current |present |new )?(president|prime minister|pm|ceo|king|queen|pope|chancellor|governor|mayor|leader|head of state|richest|champion|world champion|owner)\b|\b(currently the|right now|nowadays|today|this year|latest|newest|most recent|as of now|at the moment|this week|this month|tonight|recently released|just released|up[- ]to[- ]date)\b|\b(stock price|exchange rate|score of the|who won the last|population of \w+ (?:now|today))\b",re.I)
def dated(text):
    t=text.strip();tl=t.lower()
    if len(t)>130 or not re.match(r"\W*(who|what|which|when|where|how|is|are|was|did|do|does)\b",tl): return False
    if re.search(r"\b(explain|describe|write|help me|list|tell me about|imagine)\b",tl): return False
    return bool(DATED.search(text))
DATED_REPLY="I don't have up-to-date information, so I can't reliably tell you anything current or recent. A current news source or official site would have the right answer."
# ---------- (c) Wikipedia exact-title definition ----------
CACHE_P=os.path.join(HERE,'wiki_cache.json')
CACHE=json.load(open(CACHE_P)) if os.path.exists(CACHE_P) else {}
OFFLINE=os.environ.get('WIKI_OFFLINE')=='1'
def norm(t): return re.sub(r"\s+"," ",t.replace('_',' ')).strip().lower()
def wiki_fetch(title):
    k=norm(title)
    if k in CACHE: return CACHE[k]
    if OFFLINE: return None
    u="https://en.wikipedia.org/api/rest_v1/page/summary/"+urllib.parse.quote(title.replace(' ','_'))+"?redirect=false"
    try:
        req=urllib.request.Request(u,headers={'User-Agent':'CAEL-research/0.1 (offline experiment)'})
        d=json.load(urllib.request.urlopen(req,timeout=15))
        rec=dict(title=d.get('title',''),type=d.get('type',''),extract=d.get('extract',''),url=d.get('content_urls',{}).get('desktop',{}).get('page',''))
    except Exception as e:
        rec=dict(title='',type='error',extract='',url='',err=str(e)[:80])
    CACHE[k]=rec;json.dump(CACHE,open(CACHE_P,'w'),indent=0);return rec
def first_sentence(x):
    m=re.match(r"(.+?[a-z0-9\)\]]{2}\.)(?:\s+[A-Z]|$)",x.strip(),re.S)
    return (m.group(1) if m else x.strip()).replace('\n',' ')
WHAT=re.compile(r"^\W*(?:hi|hello|hey)?[\s,!.]*(?:what|who)(?:\s+(?:is|are|was|were)|'s)\s+(?:an?\s+|the\s+)?([A-Za-z0-9][A-Za-z0-9 .+#'&-]{0,40}?)\s*\??\s*$",re.I)
BAD=set("you your yours yourself me my i it this that he she they them we us life love happiness going happening wrong best better worst good bad meaning point difference purpose".split())
def define(text):
    m=WHAT.match(text.strip())
    if not m: return None
    x=m.group(1).strip(" .'")
    ws=x.split()
    if not 1<=len(ws)<=4 or any(w.lower() in BAD for w in ws): return None
    cands=[x]+([x[0].upper()+x[1:]] if x[0].islower() else [])+([x.title()] if len(ws)>1 and x.title()!=x else [])
    for c in cands:
        rec=wiki_fetch(c)
        if not rec or rec['type']!='standard' or not rec['extract']: continue
        if norm(rec['title'])!=norm(x): continue
        s=first_sentence(rec['extract'])
        if len(s)<20 or len(s)>400: continue
        return s+f"\n\n[From Wikipedia, article \"{rec['title']}\" (CC BY-SA 4.0): {rec['url']}]"
    return None
