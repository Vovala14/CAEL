"""General arithmetic request boundary -> existing exact helper and checker."""
from fractions import Fraction
import re
from .interpretation_common import Result,TaskError,boundary,strip_request,NUMBER
from .helper import calculate
from .verify import check_arithmetic,Unchecked

# Function words describe the value/operation request, never extra operands or
# conditions. Unknown content is not deleted to expose a convenient expression.
WRAPPER=set('''what which number value result answer expression equation does do is are the a an this that it its of for from to in using with use obey follow usual standard ordinary integer exact arithmetic mathematical mathematics order operations parentheses have their meaning produce produces yield yields obtain obtained get evaluate evaluated calculate calculated compute computed work out find determine give select choose return tell me please resolve simplify amounts evaluates'''.split())

def checked(expression):
    answer=calculate('Calculate '+expression)
    if not answer or answer.get('route')!='helper/arithmetic':raise TaskError('The complete expression is outside the bounded arithmetic interpreter.')
    try:proof=check_arithmetic(expression,answer)
    except (Unchecked,ValueError,ZeroDivisionError):raise TaskError('The arithmetic result could not be checked independently.')
    if proof.get('status')!='verified':raise TaskError('The independent arithmetic check disagrees.')
    return Fraction(answer['response'].split(' = ',1)[1].split(' (about',1)[0]),proof

def compile(text):
    t=strip_request(text)
    # The established whole-expression reader retains percentages and supported
    # word operators; no changes to its solver or protected kernels.
    old=calculate(t)
    if old and old.get('route')=='helper/arithmetic':
        try:
            p=check_arithmetic(t,old)
            if p['status']=='verified':return Result(Fraction(old['response'].split(' = ',1)[1].split(' (about',1)[0]),'arithmetic',{'source_span':[0,len(text)],'operation':old['response'],'check':p},True)
        except (Unchecked,ValueError,ZeroDivisionError):pass
    intent=bool(re.search(r'(?i)\b(?:arithmetic|expression|calculate|compute|evaluate|work out|simplify|numeric value|number does|value of)\b',t) or re.match(r'(?i)(?:what|which|find|give|return|determine)\b.{0,35}\b(?:number|value|result)\b',t))
    if not intent:return None
    boundary(t)
    # Convert lexical operators before finding a full numeric expression.
    normalized=t
    for phrase,op in [('multiplied by','*'),('divided by','/'),('times','*'),('plus','+'),('minus','-')]:
        normalized=re.sub(r'(?i)\b'+phrase+r'\b',op,normalized)
    normalized=normalized.replace('×','*').replace('÷','/').replace('−','-')
    matches=list(re.finditer(r'(?<![\w])[+\-(.\s]*\d[\d\s()+*/%^.\-]*',normalized))
    matches=[m for m in matches if re.search(r'\d',m[0])]
    if not matches:
        if re.search(r'__|\b(?:import|exec|eval|open)\s*\(',t):raise TaskError('Only bounded literal arithmetic is accepted; code and imports are not arithmetic values.')
        return None
    if len(matches)!=1:raise TaskError('Several numeric fragments need an explicit supported operation connecting them.')
    m=matches[0];expression=m[0].strip().rstrip(' .?=')
    wrapper=normalized[:m.start()]+' '+normalized[m.end():]
    words=re.findall(r'[A-Za-z]+',wrapper.casefold())
    if any(w not in WRAPPER for w in words) or re.search(r'[^A-Za-z\s,.:?!=\'"-]',wrapper):
        raise TaskError('The expression has an additional clause or qualifier outside the checked arithmetic request grammar.')
    value,proof=checked(expression)
    return Result(value,'arithmetic',{'source_span':[0,len(text)],'expression':expression,'checked_wrapper_words':words,'check':proof},True)
