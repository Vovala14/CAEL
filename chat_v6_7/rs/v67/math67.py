# v6.7 maths solver: rule-based extraction -> SymPy; every answer is verified (substitution / independent recomputation). Refuses when unsure.
import re
from fractions import Fraction as F
import sympy as sp
from sympy.parsing.sympy_parser import parse_expr,standard_transformations,implicit_multiplication_application,convert_xor
TR=standard_transformations+(implicit_multiplication_application,convert_xor)
OKCH=re.compile(r"^[0-9a-z+\-*/^=()., ]+$")
FUN={'sin','cos','tan','log','ln','exp','sqrt','pi','e'}
def P(s):
    s=s.replace('ln(','log(').replace('×','*').replace('÷','/').replace('−','-')
    return parse_expr(s,transformations=TR,local_dict={n:sp.Symbol(n) for n in 'abcdfghjkmnpqrstuvwxyz'})
def fmt(v):
    v=sp.nsimplify(v) if v.is_number else v
    if v.is_Integer: return str(v)
    if v.is_Rational: return f"{v} (about {float(v):.4g})"
    if v.is_number:
        try: return f"{sp.simplify(v)} (about {complex(v).real:.4g})" if v.is_real else str(v)
        except Exception: return str(v)
    return sp.sstr(v)
def _pretty(x): return x.replace('**','^')
def algebra(text):
    r=_algebra(text)
    return (_pretty(r[0]),r[1]) if r else None
def _algebra(text):
    t=text.strip();tl=t.lower().rstrip('?.! ')
    m=re.match(r"^(?:please\s+)?(?:solve|find (?:x|y|the value of \w)\s*(?:if|when|in|:)?|what is (?:x|y) (?:if|when|in))\s*:?\s*(?:for \w\s*:?\s*)?(.+)$",tl)
    if m:
        body=re.sub(r"\bfor (\w)$","",m.group(1)).strip()
        eqs=[e.strip() for e in re.split(r",| and |;",body) if '=' in e]
        if not eqs or not all(OKCH.match(e) and e.count('=')==1 for e in eqs): return None
        try:
            E=[sp.Eq(P(a),P(b)) for a,b in (e.split('=') for e in eqs)]
            syms=sorted(set().union(*[x.free_symbols for x in E]),key=str)
            if not syms or len(syms)>len(E) or len(syms)>3: return None
            sol=sp.solve(E,syms,dict=True)
        except Exception: return None
        if not sol or len(sol)>6: return None
        for s_ in sol:   # verify
            for x in E:
                if sp.simplify(x.lhs.subs(s_)-x.rhs.subs(s_))!=0: return None
        txt='; '.join(', '.join(f"{k} = {fmt(v)}" for k,v in s_.items()) for s_ in sol)
        return f"The solution is {txt}. (Checked by substituting back into the equation.)",'math_solve'
    m=re.match(r"^(?:what is |find |compute |calculate )?(?:the )?(derivative|integral|antiderivative|factori[sz]ation|expansion|simplification)s? of\s*(.+?)(?:\s+with respect to (\w))?$",tl) or \
      re.match(r"^(differentiate|integrate|factor|factori[sz]e|expand|simplify)\s*:?\s*(.+?)(?:\s+with respect to (\w)|\s+d(\w))?$",tl)
    if m:
        op=m.group(1);ex=m.group(2).strip()
        if not OKCH.match(ex) or '=' in ex: return None
        try:
            e=P(ex);syms=sorted(e.free_symbols,key=str)
            v=sp.Symbol(m.group(3)) if m.lastindex>=3 and m.group(3) else (syms[0] if len(syms)==1 else None)
            if op.startswith(('deriv','differ')):
                if v is None: return None
                r=sp.diff(e,v);chk=sp.simplify(sp.integrate(r,v)-e).diff(v)==0;name=f"The derivative of {sp.sstr(e)} with respect to {v} is"
            elif op.startswith(('integ','antider')):
                if v is None: return None
                r=sp.integrate(e,v)
                if r.has(sp.Integral): return None
                chk=sp.simplify(sp.diff(r,v)-e)==0;name=f"An antiderivative of {sp.sstr(e)} is";r=sp.sstr(r)+" + C"
            elif op.startswith('fact'): r=sp.factor(e);chk=sp.expand(r-e)==0;name=f"{sp.sstr(e)} factors as"
            elif op.startswith('expan'): r=sp.expand(e);chk=sp.simplify(r-e)==0;name=f"{sp.sstr(e)} expands to"
            else: r=sp.simplify(e);chk=sp.simplify(r-e)==0;name=f"{sp.sstr(e)} simplifies to"
        except Exception: return None
        if not chk: return None
        return f"{name} {r if isinstance(r,str) else sp.sstr(r)}. (Checked with SymPy.)",'math_calculus' if op.startswith(('deriv','differ','integ','antider')) else 'math_algebra'
    return None
# ---------- word problems: quantity chain ----------
NW={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12,'fifteen':15,'twenty':20,'thirty':30,'forty':40,'fifty':50,'hundred':100,'a dozen':12,'dozen':12}
def nums(s):
    s=re.sub(r"(?<=\d),(?=\d{3})","",s.lower())
    for w,n in NW.items(): s=re.sub(rf"\b{w}\b",str(n),s)
    return s
REL=[(r"\bhalf as (?:many|much)\b",lambda p:p/2),(r"\btwice as (?:many|much)\b|\bdouble\b",lambda p:p*2),(r"\bthree times as (?:many|much)\b|\b3 times as (?:many|much)\b",lambda p:p*3),
     (r"\b(\d+(?:\.\d+)?) times as (?:many|much)\b",None),(r"\b(\d+(?:\.\d+)?) (?:more|extra)\b[^.]*\bthan\b",'+'),(r"\b(\d+(?:\.\d+)?) (?:fewer|less)\b[^.]*\bthan\b",'-'),(r"\ba third as (?:many|much)\b",lambda p:p/3),(r"\ba quarter as (?:many|much)\b",lambda p:p/4)]
def wordprob(text):
    t=nums(text)
    if len(t)>600: return None
    sents=[s for s in re.split(r"(?<=[.!?])\s+|,? and then\b|, then\b|, while\b",t) if s and s.strip()]
    q=sents[-1]
    if not re.search(r"\bhow (?:many|much)\b",q): return None
    body=sents[:-1]
    if not body or re.search(r"\d",q): return None
    risky=re.search(r"\b(each|every|per|percent|fourth|third|quarter|fifth|donat\w*|costs?|price|\$|if|after|left|remain\w*|returns?|spread|equally|weeks?|last|ounces?|pounds?|meters?|kilometers?|miles?|grams?|share|tips?|hour|hours|minutes?)\b|%|/|\$",' '.join(body))
    vals=[];used=0
    allnums=len(re.findall(r"\d+(?:\.\d+)?",' '.join(body)))
    # pattern A: rate * time   ("earns $12 an hour ... 50 minutes")
    rm=re.search(r"\$?(\d+(?:\.\d+)?) (?:an|per|each|a) (hour|minute|day|week)",t)
    if rm and allnums==2:
        rate=F(rm.group(1));unit=rm.group(2)
        tm=re.search(r"(\d+(?:\.\d+)?) (hours?|minutes?|days?|weeks?)\b",t[:rm.start()]+t[rm.end():])
        if tm:
            amt=F(tm.group(1));u=tm.group(2).rstrip('s')
            conv={('hour','minute'):F(1,60),('hour','hour'):1,('minute','minute'):1,('day','day'):1,('week','week'):1,('minute','hour'):60,('day','week'):7,('week','day'):F(1,7)}.get((unit,u))
            if conv is not None:
                v=rate*amt*conv;return v,f"{rate} per {unit} x {amt} {tm.group(2)} = {v}"
    if risky: return None
    # pattern B: chain of quantities with relative phrases; question asks total / last
    hist=[]   # (clause words, value)
    body=[c for x in body for c in re.split(r",? and (?=there|she|he|they|it)",x) if c.strip()]
    for s in body:
        ns=re.findall(r"\d+(?:\.\d+)?",s);hit=False
        for pat,fn in REL:
            m=re.search(pat,s)
            if m:
                th=re.search(r"\bthan (?:the |her |his |their )?(\w+)",s)
                if th: ref=[v for w,v in reversed(hist) if th.group(1) in w]
                else: ref=[hist[-1][1]] if hist else []
                if not ref: return None
                base=ref[0]
                if fn=='+': v=base+F(m.group(1))
                elif fn=='-': v=base-F(m.group(1))
                elif fn is None: v=base*F(m.group(1))
                else: v=fn(base)
                vals.append(v);hist.append((set(re.findall(r"[a-z]+",s.split(' than ')[0])),v));used+=len(ns);hit=True;break
        if not hit:
            if re.search(r"\b(times|twice|half|more|less|fewer|than|heavier|longer|older|younger|that long)\b",s): return None
            if len(ns)==1: vals.append(F(ns[0]));hist.append((set(re.findall(r"[a-z]+",s)),F(ns[0])));used+=1
            elif len(ns)>1: return None
    if used!=allnums or len(vals)<2: return None
    if re.search(r"\b(altogether|in total|total|combined|in all|both)\b",q): v=sum(vals);return v,' + '.join(str(x) for x in vals)+f" = {v}"
    return None
def word(text):
    r=wordprob(text)
    if not r: return None
    v,work=r
    if v<0 or (v.denominator!=1 and v.denominator>100): return None
    vs=str(v.numerator) if v.denominator==1 else f"{float(v):g}"
    return f"{work}, so the answer is {vs}.",'math_word2'
def solve(text):
    return algebra(text) or word(text)
