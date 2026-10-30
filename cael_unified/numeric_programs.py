"""Non-neural numeric program induction and lexical ranking primitives.

Experimental: checked arithmetic does not verify interpretation of prose. This
module alone is not installed as an authoritative chat-answer route.
"""
import ast
from collections import Counter,defaultdict
from fractions import Fraction
import math,re

SMALL=dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(),range(21)))
SMALL.update(thirty=30,forty=40,fifty=50,sixty=60,seventy=70,eighty=80,ninety=90,half=Fraction(1,2),quarter=Fraction(1,4),twice=2,double=2,thrice=3,dozen=12)
NUMBER=re.compile(r'(?<![\w.])(?:\d[\d,]*(?:\.\d+)?(?:/\d+)?|\.'+r'\d+)(?!\w)|\b(?:'+'|'.join(SMALL)+r')\b',re.I)
CONSTANTS={Fraction(v) for v in [0,1,2,3,4,5,7,10,12,24,60,100,365,1000]}
STOP=set('a an the of to is are was were be been will would could should can if and or in on at by for with from that this as it its his her their he she they them how many much what does do did has have had there then than into per'.split())
CAPITAL_COMMON={'how','what','if','after','before','each','every','there','the','a','an','in','on','at','first','last','when','twice','half','one','two','three','four','five','six','seven','eight','nine','ten'}

def numbers(text):
    values=[]
    for m in NUMBER.finditer(text):
        raw=m[0].casefold()
        try:value=Fraction(SMALL[raw]) if raw in SMALL else Fraction(raw.replace(',',''))
        except (ValueError,ZeroDivisionError):continue
        if abs(value)>10**12:raise ValueError('Question quantity exceeds bound')
        values.append(value)
    return values

def features(text):
    replaced=NUMBER.sub(' num ',text)
    words=[]
    for raw in re.findall(r'[A-Za-z]+',replaced):
        word=raw.casefold()
        if raw[0].isupper() and word not in CAPITAL_COMMON:word='entity'
        if word in STOP or word=='entity':continue
        if word.endswith('s') and len(word)>4 and not word.endswith(('ss','us')):word=word[:-1]
        words.append(word)
    return set(words)|{'~'.join(pair) for pair in zip(words,words[1:])}

def execute(program,values,budget=160):
    steps=[0]
    def run(node):
        steps[0]+=1
        if steps[0]>budget:raise ValueError('Program size bound')
        op=node[0]
        if op=='n':value=values[node[1]]
        elif op=='c':value=Fraction(node[1])
        else:
            left,right=run(node[1]),run(node[2])
            if op=='+':value=left+right
            elif op=='-':value=left-right
            elif op=='*':value=left*right
            elif op=='/':value=left/right
            elif op=='**' and right.denominator==1 and 0<=right<=6:value=left**int(right)
            else:raise ValueError('Unsupported arithmetic operator')
        if max(value.numerator.bit_length(),value.denominator.bit_length())>128:raise ValueError('Arithmetic magnitude bound')
        return value
    return run(program)

def inputs_used(program):
    if program[0]=='n':return {program[1]}
    if program[0]=='c':return set()
    return inputs_used(program[1])|inputs_used(program[2])

def compile_annotation(expression,known,source):
    expression=expression.replace(',','').replace('^','**').strip()
    tree=ast.parse(expression,mode='eval')
    if sum(1 for _ in ast.walk(tree))>70:raise ValueError('Annotation AST bound')
    def convert(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            value=Fraction(ast.get_source_segment(expression,node))
            if value in known:return known[value]
            if value in CONSTANTS:return ['c',str(value)]
            raise ValueError('Operand not grounded in question/prior arithmetic/unit constants')
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
            child=convert(node.operand)
            return ['-', ['c','0'],child] if isinstance(node.op,ast.USub) else child
        if isinstance(node,ast.BinOp):
            op={ast.Add:'+',ast.Sub:'-',ast.Mult:'*',ast.Div:'/',ast.Pow:'**'}.get(type(node.op))
            if op:return [op,convert(node.left),convert(node.right)]
        raise ValueError('Unsupported annotation syntax')
    result=convert(tree.body)
    execute(result,source)
    return result

def compile_record(question,answer):
    values=numbers(question)
    if not 1<=len(values)<=16:raise ValueError('Question number-count bound')
    known={}
    for i,value in enumerate(values):known.setdefault(value,['n',i])
    compiled=0
    for content in re.findall(r'<<([^<>]+)>>',answer):
        if '=' not in content:continue
        left,right=content.rsplit('=',1)
        try:
            expected=Fraction(right.replace(',','').strip())
            program=compile_annotation(left,known,values)
            if execute(program,values)!=expected:continue
            known[expected]=program;compiled+=1
        except (ValueError,ZeroDivisionError,SyntaxError,OverflowError,RecursionError,IndexError):continue
    target=Fraction(answer.rsplit('####',1)[1].strip().replace(',',''))
    program=known.get(target)
    if program is None or not inputs_used(program) or execute(program,values)!=target or compiled==0:
        raise ValueError('No grounded validated final program')
    return dict(number_count=len(values),program=program,tokens=sorted(features(question)),used_inputs=len(inputs_used(program)))

class Ranker:
    def __init__(self,rows):
        self.rows=rows;self.postings=defaultdict(list)
        counts=Counter(t for r in rows for t in r['tokens'])
        self.weights={t:(1+math.log((len(rows)+1)/(df+1)))**2 for t,df in counts.items()}
        self.norms=[]
        for i,row in enumerate(rows):
            self.norms.append(math.sqrt(sum(self.weights[t] for t in row['tokens'])))
            for token in row['tokens']:self.postings[(row['number_count'],token)].append(i)

    def alternatives(self,question,limit=8):
        values=numbers(question)
        if not 2<=len(values)<=16:return []
        tokens=features(question);scores=defaultdict(float)
        norm=math.sqrt(sum(self.weights.get(t,0) for t in tokens))
        if not norm:return []
        for token in tokens:
            for i in self.postings.get((len(values),token),()):scores[i]+=self.weights[token]
        ranked=sorted(((dot/(norm*self.norms[i]),i) for i,dot in scores.items()),reverse=True)[:max(40,limit)]
        out=[]
        for score,i in ranked:
            row=self.rows[i]
            try:value=execute(row['program'],values)
            except (ValueError,ZeroDivisionError,IndexError,OverflowError):continue
            out.append(dict(score=score,value=str(value),program=row['program'],source_id=row['source_id'],
                used_inputs=row['used_inputs'],input_count=len(values)))
            if len(out)==limit:break
        return out

def choose(alternatives,minimum=.35,support=2,margin=.03):
    if not alternatives or alternatives[0]['score']<minimum:return None
    best=alternatives[0]
    agreeing=[a for a in alternatives if a['value']==best['value'] and a['score']>=max(minimum,.8*best['score'])]
    other=next((a['score'] for a in alternatives if a['value']!=best['value']),0)
    if len(agreeing)<support or best['score']-other<margin:return None
    return dict(best,support=len(agreeing),margin=best['score']-other,
                limitation='Retrieved numeric program; arithmetic checked,prose interpretation not proven')
