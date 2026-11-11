"""Source-linked count relations and events, solved with exact linear algebra.

The language layer is bounded. A checked equation system does not prove that
arbitrary English has been interpreted. No native generated expression runs.
"""
from fractions import Fraction
import copy
import re


class Unclear(ValueError):pass


WORDS=dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(),range(21)))
NUMBER=r'(?:-?\d+(?:\.\d+)?(?:/\d+)?|'+'|'.join(WORDS)+r')'
ENTITY=r"[\w][\w'’ -]{0,60}?"
UNIT=r'[A-Za-z][A-Za-z -]{0,45}?'


def number(text):
    text=text.casefold().strip()
    try:v=Fraction(WORDS[text]) if text in WORDS else Fraction(text)
    except (ValueError,ZeroDivisionError):raise Unclear('A quantity is not a complete exact number.')
    if abs(v)>10**9 or v.denominator>10**6:raise Unclear('A number exceeds the exact quantity bound.')
    return v


def fmt(value):
    return str(value.numerator) if value.denominator==1 else str(value.numerator)+'/'+str(value.denominator)


def owner(text):
    text=re.sub(r'(?i)^(?:the|a|an)\s+','',text.strip())
    if not re.fullmatch(r"[\w][\w'’-]*(?: [\w][\w'’-]*){0,3}",text) or re.search(r'(?i)\b(?:if|unless|and|or|not|every|some|each|maybe|perhaps)\b',text):
        raise Unclear('The owner reference is not a single complete declared entity.')
    return 'i' if text.casefold() in ('i','me','myself') else text.casefold()


def unit(text):
    text=' '.join(text.casefold().split())
    if re.search(r'(?i)\b(?:if|unless|per|each|except|without|but|when|than|more|fewer|less|as|has|have|gets|gives|to|from|and|or|not|twice)\b',text):
        raise Unclear('A unit slot contains an unconsumed relation, condition or event.')
    words=text.split();last=words[-1]
    if last.endswith('ies'):last=last[:-3]+'y'
    elif re.search(r'(?:ches|shes|sses|xes)$',last):last=last[:-2]
    elif last.endswith('s') and not last.endswith('ss'):last=last[:-1]
    return ' '.join(words[:-1]+[last])


def names(text):
    result=[s.strip() for s in re.split(r'\s*,\s*|\s+and\s+',text) if s.strip()]
    if not 1<=len(result)<=8 or len({owner(n) for n in result})!=len(result):raise Unclear('Name each owner once, without an ambiguous group.')
    return result


def empty():
    return dict(kind='quantities',variables=[],rows=[],current={},display={},units={},facts=[],bindings=[],unresolved_money_owners=[],query=None,last_units=None,last_group=None)


def variable(model,label,u):
    who=owner(label)
    if who in ('he','she','it','they'):
        if len(model['display'])!=1 or who=='they':raise Unclear('The factual pronoun has multiple or no explicit antecedents; name the owner.')
        resolved=next(iter(model['display']));model['bindings'].append(dict(reference=label,owner=resolved));who=resolved;label=model['display'][who]
    key=who+'|'+unit(u)
    if key not in model['current']:
        if len(model['variables'])>=48:raise Unclear('The relation graph exceeds48 variables.')
        name='q'+str(len(model['variables']));model['variables'].append(name);model['current'][key]=name
    model['display'][who]=label.strip();model['units'][unit(u)]=u.strip()
    return model['current'][key]


def row(model,coefficients,value,text,at):
    if len(model['rows'])>=64:raise Unclear('The relation graph exceeds64 equations.')
    coefficients={n:Fraction(v) for n,v in coefficients.items() if v}
    model['rows'].append(dict(coefficients={n:fmt(v) for n,v in coefficients.items()},value=fmt(Fraction(value)),message=at,text=text))
    model['facts'].append(dict(message=at,text=text))


def add(model,text,at):
    """Consume one complete factual clause, returning whether this grammar owns it."""
    t=text.strip(' .!')
    literal=re.fullmatch('('+ENTITY+r')\s+(?:has|have|holds|owns|carries|starts with)\s+('+NUMBER+r')\s+('+UNIT+r')',t,re.I)
    relative=re.fullmatch('('+ENTITY+r')\s+(?:has|have|holds)\s+('+NUMBER+r')\s+(more|fewer|less)\s+('+UNIT+r')\s+than\s+('+ENTITY+')',t,re.I)
    relative2=re.fullmatch('('+ENTITY+r')\s+(?:has|have|holds)\s+('+NUMBER+r')\s+('+UNIT+r')\s+(more|fewer|less)\s+than\s+('+ENTITY+')',t,re.I)
    ratio=re.fullmatch('('+ENTITY+r')\s+(?:has|have)\s+('+NUMBER+r')\s+times as many\s+('+UNIT+r')\s+as\s+('+ENTITY+')',t,re.I)
    same=re.fullmatch('('+ENTITY+r')\s+(?:has|have)\s+(?:the same number of|as many)\s+('+UNIT+r')\s+as\s+('+ENTITY+')',t,re.I)
    total=re.fullmatch(r'(?:together,?\s+)?(.+?)\s+(?:have|hold)\s+('+NUMBER+r')\s+('+UNIT+r')(?:\s+(?:altogether|in total|between them))',t,re.I)
    if relative or relative2:
        if relative:a,n,op,u,b=relative.groups()
        else:a,n,u,op,b=relative2.groups()
        amount=number(n)
        if amount<0:raise Unclear('Use a nonnegative difference and an explicit more/fewer direction.')
        av,bv=variable(model,a,u),variable(model,b,u)
        coeff={av:Fraction(1)};coeff[bv]=coeff.get(bv,0)-1
        row(model,coeff,amount if op.lower()=='more' else -amount,text,at)
        model['last_units']=unit(u);model['last_group']=[owner(a),owner(b)];return True
    if ratio:
        a,n,u,b=ratio.groups();factor=number(n)
        if factor<0:raise Unclear('The multiplicative quantity factor is negative.')
        av,bv=variable(model,a,u),variable(model,b,u)
        coeff={av:Fraction(1)};coeff[bv]=coeff.get(bv,0)-factor
        row(model,coeff,0,text,at);model['last_units']=unit(u);model['last_group']=[owner(a),owner(b)];return True
    if same:
        a,u,b=same.groups();av,bv=variable(model,a,u),variable(model,b,u)
        coeff={av:Fraction(1)};coeff[bv]=coeff.get(bv,0)-1
        row(model,coeff,0,text,at);model['last_units']=unit(u);model['last_group']=[owner(a),owner(b)];return True
    if total:
        people,n,u=total.groups();people=names(people)
        if len(people)<2:raise Unclear('An altogether relation needs the explicit group.')
        coefficients={variable(model,p,u):1 for p in people};amount=number(n)
        if amount<0:raise Unclear('A combined stock cannot be negative.')
        row(model,coefficients,amount,text,at);model['last_units']=unit(u);model['last_group']=[owner(p) for p in people];return True
    if literal:
        a,n,u=literal.groups();amount=number(n)
        if amount<0:raise Unclear('A supplied stock is negative; clarify the quantity semantics.')
        v=variable(model,a,u);row(model,{v:1},amount,text,at)
        model['last_units']=unit(u);return True
    # Current-time events retain the earlier values as separate variables.
    change=re.fullmatch(r'(?i)(?:now\s+|then\s+)?('+ENTITY+r')\s+(get|gets|receive|receives|gain|gains|buy|buys|purchase|purchases|lose|loses|spend|spends)\s+('+NUMBER+r')\s+('+UNIT+r')',t)
    transfer=re.fullmatch(r'(?i)(?:now\s+|then\s+)?('+ENTITY+r')\s+give(?:s)?\s+('+NUMBER+r')\s+('+UNIT+r')\s+to\s+('+ENTITY+')',t)
    if change or transfer:
        if change:a,verb,n,u=change.groups();changes=[(a,1 if verb.lower() in ('get','gets','receive','receives','gain','gains','buy','buys','purchase','purchases') else -1)]
        else:a,n,u,b=transfer.groups();changes=[(a,-1),(b,1)]
        amount=number(n)
        if amount<0:raise Unclear('A quantity event needs a nonnegative amount and explicit direction.')
        for a,sign in changes:
            old=variable(model,a,u)
            if len(model['variables'])>=48:raise Unclear('The event graph exceeds48 variables.')
            keys=[k for k,v in model['current'].items() if v==old]
            new='q'+str(len(model['variables']));model['variables'].append(new);model['current'][keys[0]]=new
            row(model,{new:1,old:-1},sign*amount,text,at)
            if change and verb.lower() in ('buy','buys','purchase','purchases'):
                who=keys[0].split('|')[0]
                if who not in model['unresolved_money_owners']:model['unresolved_money_owners'].append(who)
        model['last_units']=unit(u);return True
    return False


def question(model,text):
    t=text.strip(' ?. !')
    match=re.fullmatch(r'(?i)how (?:many|much)\s+(.+?)\s+(?:does|do)\s+(.+?)\s+(?:have|hold|own|carry)(?:\s+(altogether|together|in total))?',t)
    short=re.fullmatch(r'(?i)how (?:many|much)\s+(?:does|do)\s+(.+?)\s+(?:have|hold|own|carry)(?:\s+(altogether|together|in total))?',t)
    if match:u,people,total=match.groups();u=unit(u)
    elif short:people,total=short.groups();u=model.get('last_units')
    else:return None
    if not u or u not in model['units']:raise Unclear('The requested item/unit is not established. Name it explicitly.')
    if people.casefold() in ('they','them','both of them'):
        group=model.get('last_group')
        if not group:
            group=sorted({k.split('|')[0] for k in model['current'] if k.endswith('|'+u)})
            if len(group)!=2:raise Unclear('The plural reference has no unique two-owner/group antecedent.')
        people=[model['display'][p] for p in group]
    elif people.casefold() in ('he','she','it'):
        choices={k.split('|')[0] for k in model['current'] if k.endswith('|'+u)}
        if len(choices)!=1:raise Unclear('The pronoun has multiple or no explicit owner antecedents.')
        people=[model['display'][next(iter(choices))]]
    else:people=names(people)
    if len(people)>1 and not total:
        raise Unclear('Specify whether to return each amount or a combined total.')
    coefficients={}
    for p in people:
        key=owner(p)+'|'+u
        if u in ('dollar','euro','pound','usd','eur','gbp','money','cash') and owner(p) in model['unresolved_money_owners']:
            raise Unclear('A purchase has no stated price; the remaining money is not determined.')
        if key not in model['current']:raise Unclear('The question names an owner/unit without supplied facts.')
        n=model['current'][key];coefficients[n]=coefficients.get(n,0)+1
    return dict(kind='quantity',coefficients=coefficients,owners=people,unit=u,question=text)


def reduce_rows(model):
    """RREF with exact fractions; retain free variables and contradictions."""
    variables=model['variables'];columns={n:i for i,n in enumerate(variables)};matrix=[]
    for record in model['rows']:
        a=[Fraction(0)]*(len(variables)+1)
        for n,c in record['coefficients'].items():a[columns[n]]=Fraction(c)
        a[-1]=Fraction(record['value']);matrix.append(a)
    combinations=[[Fraction(int(i==j)) for j in range(len(matrix))] for i in range(len(matrix))]
    pivots=[];r=0
    for c in range(len(variables)):
        pivot=next((i for i in range(r,len(matrix)) if matrix[i][c]),None)
        if pivot is None:continue
        matrix[r],matrix[pivot]=matrix[pivot],matrix[r];combinations[r],combinations[pivot]=combinations[pivot],combinations[r];amount=matrix[r][c]
        matrix[r]=[v/amount for v in matrix[r]]
        combinations[r]=[v/amount for v in combinations[r]]
        for i in range(len(matrix)):
            if i!=r and matrix[i][c]:
                amount=matrix[i][c];matrix[i]=[v-amount*w for v,w in zip(matrix[i],matrix[r])]
                combinations[i]=[v-amount*w for v,w in zip(combinations[i],combinations[r])]
        if any(abs(v.numerator)>10**30 or v.denominator>10**15 for line in matrix for v in line):raise Unclear('Exact elimination exceeded its rational size bound.')
        pivots.append(c);r+=1
        if r==len(matrix):break
    if any(all(v==0 for v in line[:-1]) and line[-1]!=0 for line in matrix):
        raise Unclear('The supplied quantitative facts conflict; a repeated stock was not silently overwritten.')
    return variables,matrix,pivots,combinations


def solve(model,q):
    variables,matrix,pivots,combinations=reduce_rows(model);columns={n:i for i,n in enumerate(variables)}
    target=[Fraction(q['coefficients'].get(n,0)) for n in variables];answer=Fraction(0);weights=[Fraction(0)]*len(matrix)
    for line,c,combo in zip(matrix,pivots,combinations):
        amount=target[c]
        answer+=amount*line[-1];target=[v-amount*w for v,w in zip(target,line[:-1])];weights=[v+amount*w for v,w in zip(weights,combo)]
    if any(target):raise Unclear('The complete relations do not determine the requested quantity; an initial amount/dependency is missing.')
    if answer<0:raise Unclear('The requested count/stock is negative under the supplied relations.')
    for n in model['variables']:
        c=columns[n]
        if c in pivots:
            line=matrix[pivots.index(c)]
            if all(v==0 for j,v in enumerate(line[:-1]) if j!=c) and line[-1]<0:
                raise Unclear('A derived current stock is negative; clarify the conflicting quantity/event model.')
    # A determined sum alone does not establish that the underlying stock
    # constraints admit nonnegative values. Certify an exact witness using
    # free variables set to zero; otherwise abstain conservatively. This is
    # deliberately not a claim that every rejected system is infeasible.
    witness={n:Fraction(0) for n in variables}
    for line,c in zip(matrix,pivots):witness[variables[c]]=line[-1]
    if any(v<0 for v in witness.values()):
        raise Unclear('The requested sum is fixed, but I cannot certify nonnegative stocks with the supplied dependencies; clarify the individual amounts.')
    if any(sum(Fraction(c)*witness[n] for n,c in r['coefficients'].items())!=Fraction(r['value']) for r in model['rows']):
        raise Unclear('The exact stock witness did not satisfy every supplied equation.')
    known={variables[c]:fmt(line[-1]) for line,c in zip(matrix,pivots) if all(v==0 for j,v in enumerate(line[:-1]) if j!=c)}
    return answer,dict(method='exact-rational-row-reduction',variables=variables,rows=model['rows'],rank=len(pivots),known_values=known,
        free_variables=[n for i,n in enumerate(variables) if i not in pivots],nonnegative_witness={n:fmt(v) for n,v in witness.items()},target=q['coefficients'],value=fmt(answer),
        row_combination=[fmt(v) for v in weights],all_clauses_consumed=True,native_generated_code=False)
