# v6.5 answer gate: decides answer vs refuse. Thresholds tuned on panel_v2 only (see TWEAKS.log).
import re,os,json
import ret65 as R
TH=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'thresholds65.json')))
INFO=re.compile(r"^\W*(?:hi|hello|hey)?[\s,!.]*(?:(?:can|could) you (?:please )?(?:tell me|explain)\s*)?(what(?:'s| is| are| was| were| does| did)?|who(?:'s| is| was| were)?|when (?:is|was|did|were|does)|where (?:is|was|are|does|did|do)|which|why (?:is|are|do|does|did|was)|how (?:does|do|did|is|are|was|many|much|far|long|old|big|tall|fast)|explain|describe|tell me about|define)\b",re.I)
BAD=re.compile(r"\b(you|your|yourself|i|i'm|me|my|mine|we|our|should i|best|recommend|opinion|think|feel|write|poem|story|joke|code|python|script|function|program|list|ideas?|steps|step-by-step|essay|compare|difference between|vs|versus|pros and cons|future|will|would|if)\b",re.I)
SUBJ=re.compile(r"^\W*(?:(?:can|could) you (?:please )?(?:tell me|explain)\s*)?(?:what|who)(?:'s| is| are| was| were)\s+(?:an?\s+|the\s+)?([a-z0-9 .'-]{2,40}?)\s*\??$",re.I)
PRE=r"^\W*(?:hi|hello|hey)?[\s,!.]*(?:(?:can|could|would) you (?:please )?(?:tell me|explain(?: to me)?|describe)\s*|please\s+)?"
SUBJ2=[re.compile(PRE+r"(?:what|who)(?:'s| is| are| was| were)\s+(?:an?\s+|the\s+)?([a-z0-9][a-z0-9 .'&-]{1,45}?)(?:\s+and\s+.*)?\s*[?.!]*$",re.I),
       re.compile(PRE+r"(?:explain|describe|define|tell me about|what do you know about)\s+(?:what\s+(?:an?\s+|the\s+)?)?(?:an?\s+|the\s+)?([a-z0-9][a-z0-9 .'&-]{1,45}?)(?:\s+(?:is|are))?\s*[?.!]*$",re.I),
       re.compile(r"^\W*(?:hi|hello|hey)?[\s,!.]*(?:(?:can|could|would) you (?:please )?)?(?:explain|describe|define|tell me about)\s+(?:an?\s+|the\s+)?([a-z0-9][a-z0-9 .'&-]{1,45}?)\s*[?.!]*$",re.I),
       re.compile(PRE+r"how (?:does|do) (?:an?\s+|the\s+)?([a-z0-9][a-z0-9 .'&-]{1,45}?) work\s*[?.!]*$",re.I)]
PRON=re.compile(r"\b(you|your|yourself|i|me|my|we|our|it|this|that|he|she|they|them|meaning of life|best|good|bad|wrong|right|difference|point|purpose|current|latest)\b",re.I)
STRIP=re.compile(r"^(?:the )?(?:logic|idea|concept|theory|basics|history|meaning|definition|principle|science) (?:behind|of) |\s+(?:in simple (?:terms|language|words)|simply|briefly|in a few sentences|to me|to a (?:child|5 year old|five year old))$",re.I)
def subject(t):
    m=re.match(r"^([^?\n]{3,120}\?)\s",t+' ')
    if m and m.group(1)!=t: t=m.group(1)   # first question only
    for r in SUBJ2:
        m=r.match(t)
        if m:
            x=m.group(1).strip(" .'")
            for _ in range(2): x=re.sub(r"^(?:an?|the) ","",STRIP.sub('',x).strip(" .'"),flags=re.I)
            if 1<=len(x.split())<=5 and not PRON.search(x): return x
    return None
DATED=re.compile(r"\b(current(?:ly)?|now|today|this year|last year|latest|recent(?:ly)?|20[12]\d|right now|still)\b",re.I)
def answer(text,typ):
    t=text.strip()
    if len(t)>200 or '\n' in t: return None
    x=subject(t)
    if x:
        p=R.lead(x)
        y=x
        while p is None and re.search(r"\s(?:in|on|for|during|at|with|from)\s",y):
            y=re.split(r"\s(?:in|on|for|during|at|with|from)\s(?!.*\s(?:in|on|for|during|at|with|from)\s)",y)[0];p=R.lead(y)
        if p: return (p['ans'].strip()+f"\n\n[From the Wikipedia article \"{p['title']}\" ({p['tag']}, CC BY-SA 4.0, text unchanged): {p['url']}]",'wiki_lead',1000)
    b=R.qa_best(t)
    if b and b['f']>=TH['qa_f'][b['r']['k']] and not DATED.search(t) and not re.search(r"\b(you|your|yourself)\b",re.sub(r"\b(can|could|would) you\b","",t.lower())):
        r=b['r'];a=r['a'].strip()
        if r['k']=='nq': a=a[0].upper()+a[1:]+('' if a.endswith('.') else '.')
        if len(a)<=1500:
            return (a+f"\n\n[Retrieved human-written answer to a similar question: \"{r['q'][:120]}\" | Source: {r['src']}]",'qa_'+r['k'],b['f'])
    return None
