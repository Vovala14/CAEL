"""Exact, bounded chat helpers; authored algorithms, no neural inference or eval."""
import ast
from fractions import Fraction
import re

from .helper import calculate

NUMBER=r'-?\d+(?:\.\d+)?'
WHY=re.compile(r'(?i)^(?:why|explain(?: that| this| your answer| the answer| the calculation)?|show(?: me)? (?:the )?(?:steps|working)|how did you (?:get|calculate|work out) that)[?.!]*$')


def render(value):
    return str(value.numerator) if value.denominator==1 else str(value)


def clean_request(text):
    text=re.sub(r'(?i)^\s*(?:please\s+|(?:can|could|would) you\s+(?:please\s+)?)(?=(?:calculate|compute|convert|solve|explain|work out)\b)', '',text.strip())
    return re.sub(r"(?i)^\s*(?:how much is|what['’]s)\s+",'what is ',text)


def previous_calculation(messages):
    if not messages or len(messages)<3 or messages[-2].get('role')!='assistant':return None
    response=messages[-2].get('content','')
    # Only our bounded expression/result shape qualifies, never an arbitrary
    # number appearing in ordinary conversation or a citation.
    match=re.match(r'^([0-9eE+*/%(). \-]+) = (-?\d+(?:/\d+)?)(?:\n|$)',response)
    if not match:return None
    checked=calculate(match[1])
    if not checked or checked['response']!=match[1]+' = '+match[2]:return None
    return match[1],Fraction(match[2])


def arithmetic_steps(expression):
    try:tree=ast.parse(expression,mode='eval')
    except SyntaxError:return []
    steps=[]
    def visit(node):
        for child in ast.iter_child_nodes(node):visit(child)
        if isinstance(node,ast.BinOp):
            part=ast.unparse(node)
            answer=calculate(part)
            if answer and answer['response'] not in steps:steps.append(answer['response'])
    visit(tree)
    return steps[:8]


def result(expression,steps=None,explain=False):
    answer=calculate(expression)
    if not answer:return None
    expression=answer['response'].split(' = ',1)[0]
    steps=steps or arithmetic_steps(expression)
    answer.update(sources=[],details='Exact rational arithmetic from an authored bounded parser. No neural model or internet request.\n'+ '\n'.join(steps),
                  helper_reasoning=dict(expression=expression,steps=steps,exact=True))
    if explain and steps:answer['response']+='\n\nSteps:\n'+'\n'.join(f'{i+1}. {step}' for i,step in enumerate(steps))
    return answer


def linear(text,explain=False):
    text=re.sub(r'(?i)^(?:solve(?: for [a-z])?\s*:?\s*|find [a-z](?: in)?\s*:?\s*)','',text).strip().rstrip(' ?.');text=text.replace('−','-').replace('×','*').replace('÷','/')
    if text.count('=')!=1 or len(text)>200 or not re.fullmatch(r'[\d\sa-z+*/().=\-]+',text,re.I):return None
    names=set(re.findall(r'[a-z]',text.lower()))
    if len(names)!=1:return None
    name=next(iter(names));text=text.lower()
    text=re.sub(r'(\d|\))\s*(?='+name+r'\b)',r'\1*',text)
    text=re.sub(r'\b'+name+r'\s*(?=\()',name+'*',text)
    text=re.sub(r'(\d|\))\s*(?=\()',r'\1*',text)

    def pair(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return Fraction(0),Fraction(str(node.value))
        if isinstance(node,ast.Name) and node.id==name:return Fraction(1),Fraction(0)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            a,b=pair(node.operand);return (a,b) if isinstance(node.op,ast.UAdd) else (-a,-b)
        if isinstance(node,ast.BinOp):
            a,b=pair(node.left);c,d=pair(node.right)
            if max(v.numerator.bit_length()+v.denominator.bit_length() for v in (a,b,c,d))>4096:raise ValueError('Too large')
            if isinstance(node.op,ast.Add):return a+c,b+d
            if isinstance(node.op,ast.Sub):return a-c,b-d
            if isinstance(node.op,ast.Mult) and not (a and c):return a*d+c*b,b*d
            if isinstance(node.op,ast.Div) and not c and d:return a/d,b/d
        raise ValueError('Nonlinear or unsupported')

    try:
        left,right=[ast.parse(s.strip(),mode='eval') for s in text.split('=')]
        if sum(1 for _ in ast.walk(left))+sum(1 for _ in ast.walk(right))>80:raise ValueError('Too large')
        a,b=pair(left.body);c,d=pair(right.body)
        coefficient=a-c;constant=d-b
        if not coefficient:
            response='Every value of '+name+' satisfies this equation.' if not constant else 'This equation has no solution.'
            steps=[f'Combining both sides gives 0 = {render(constant)}.']
        else:
            value=constant/coefficient
            if value.numerator.bit_length()+value.denominator.bit_length()>4096:raise ValueError('Too large')
            response=f'{name} = {render(value)}'
            steps=[f'Collect terms: ({render(coefficient)}) * {name} = {render(constant)}.',f'Divide by {render(coefficient)}: {name} = {render(value)}.']
    except (ValueError,SyntaxError,ZeroDivisionError,OverflowError):
        return dict(route='helper/unsupported',response='I can solve linear equations with one unknown, such as 2*x + 3 = 11. This equation is outside that parser.',sources=[])
    return dict(route='helper/equation',response=response+ ('\n\n'+'\n'.join(steps) if explain else ''),sources=[],exact=True,
                details='Authored exact linear-equation parser; no code execution.\n'+'\n'.join(steps),helper_reasoning=dict(steps=steps,exact=True))


def reply(text,messages=None):
    text=clean_request(text)
    explain=bool(re.match(r'(?i)^(?:explain(?: how to calculate)?|show(?: me)? (?:the )?(?:steps|working)(?: for)?)\s*:?\s+',text))
    if explain:text=re.sub(r'(?i)^(?:explain(?: how to calculate)?|show(?: me)? (?:the )?(?:steps|working)(?: for)?)\s*:?\s+','',text)
    if len(text)>1000:return None
    from .helper_rates import reply as rates_reply
    rated=rates_reply(text,messages,explain)
    if rated:return rated
    from .helper_groups import reply as groups_reply
    grouped=groups_reply(text,messages,explain)
    if grouped:return grouped
    previous=previous_calculation(messages)
    if WHY.fullmatch(text.strip()) and previous:
        return result(previous[0],explain=True)
    if WHY.fullmatch(text.strip()) and messages:
        from .reasoning_chat import context_from_history
        context,question=context_from_history(messages)
        if context and question:
            from .helper_quantities import reply as quantities_reply
            explanation=quantities_reply('Given: '+context+'. '+question,None,explain=True)
            if explanation:return explanation
    if WHY.fullmatch(text.strip()) and messages and len(messages)>=3:
        prior=messages[-3]
        if prior.get('role')=='user' and not WHY.fullmatch(prior['content'].strip()):
            # Reconstruct only this user's preceding helper request, not a
            # number found incidentally in a factual or social reply.
            return reply('Explain '+clean_request(prior['content']),messages[:-2])
    followup=re.fullmatch(r'(?i)(?:(?:and|then|now)\s+)?(?:(add|subtract)\s+('+NUMBER+r')(?:\s+(?:to|from)\s+(?:that|it|the result))?|(multiply|divide)\s+(?:that|it|the result)\s+by\s+('+NUMBER+r'))[?.!]*',text)
    if followup:
        if not previous:
            return dict(route='helper/clarify',response='Which starting value should I use?',sources=[])
        operation=followup[1] or followup[3];number=followup[2] or followup[4]
        symbol={'add':'+','subtract':'-','multiply':'*','divide':'/'}[operation.lower()]
        return result(f'({render(previous[1])}) {symbol} ({number})',explain=explain) or dict(route='helper/undefined',response='That operation is undefined, such as division by zero.',sources=[])
    from .helper_math import reply as math_reply
    extended=math_reply(text)
    if extended:return extended
    equation=linear(text,explain)
    if equation:return equation
    bare=text.strip().rstrip(' ?.').lower()
    percent=re.fullmatch(r'(?:what (?:percent|percentage) (?:is )?)('+NUMBER+r')\s+(?:of|out of)\s+('+NUMBER+r')',bare)
    if percent:
        if not Fraction(percent[2]):return dict(route='helper/undefined',response='A percentage of a zero base is undefined.',sources=[])
        answer=result(f'({percent[1]}) / ({percent[2]}) * 100',steps=[f'Percentage = part / whole * 100.'],explain=explain)
        value=calculate(f'({percent[1]}) / ({percent[2]}) * 100')['response'].split(' = ')[1]
        answer['response']=f'{percent[1]} is {value}% of {percent[2]}.'+ ('\n\n'+answer['response'] if explain else '')
        return answer
    percent_of=re.fullmatch(r'(?:what is |calculate |compute )?('+NUMBER+r')\s*(?:percent|%)\s+of\s+('+NUMBER+r')',bare)
    if percent_of:return result(f'({percent_of[1]}) / 100 * ({percent_of[2]})',explain=explain)
    adjustment=re.fullmatch(r'(increase|decrease)\s+('+NUMBER+r')\s+by\s+('+NUMBER+r')\s*(?:percent|%)',bare)
    if adjustment:
        symbol='+' if adjustment[1]=='increase' else '-'
        return result(f'({adjustment[2]}) * (1 {symbol} ({adjustment[3]}) / 100)',explain=explain)
    discount=re.fullmatch(r'('+NUMBER+r')\s*%\s+(?:off|discount (?:on|from))\s+\$?('+NUMBER+r')',bare)
    if discount:return result(f'({discount[2]}) * (1 - ({discount[1]}) / 100)',explain=explain)
    change=re.fullmatch(r'(?:what is (?:the )?)?(?:percent|percentage) (?:change|increase|decrease) from ('+NUMBER+r') to ('+NUMBER+r')',bare)
    if change:
        if not Fraction(change[1]):return dict(route='helper/undefined',response='Percentage change from zero is undefined.',sources=[])
        answer=result(f'(({change[2]}) - ({change[1]})) / ({change[1]}) * 100',explain=explain)
        value=calculate(f'(({change[2]}) - ({change[1]})) / ({change[1]}) * 100')['response'].split(' = ')[1]
        answer['response']='Percentage change: '+value+'%.'+ ('\n\n'+answer['response'] if explain else '')
        return answer
    conversion=re.fullmatch(r'how many ([a-z]+) (?:are )?(?:in|is) ('+NUMBER+r') ([a-z]+)',bare)
    if conversion:text=f'{conversion[2]} {conversion[3]} to {conversion[1]}'
    direct=calculate(text)
    if direct:
        if direct['route']=='helper/arithmetic':return result(direct['response'].split(' = ',1)[0],explain=explain)
        direct.update(sources=[],details='Exact conversion between compatible units using rational conversion factors. No internet request.')
        return direct
    bare=re.sub(r'^(?:what is|calculate|compute|solve)\s+','',bare)
    if re.fullmatch(r'[\d\s()+*/%.\-]+',bare) and re.search(r'\d',bare):
        return dict(route='helper/undefined',response='I could not evaluate that expression. Check the syntax, division by zero and arithmetic limits.',sources=[])
    from .helper_quantities import reply as quantities_reply
    return quantities_reply(text,messages,explain)
