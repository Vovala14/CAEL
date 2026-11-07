"""Native typed interpretation -> bounded symbolic operations -> checked answer.

This is part of Assistant inference, not an evaluator adapter. No benchmark IDs,
gold answers, external models, network calls, weight changes or code execution.
"""
from fractions import Fraction
from .interpretation_common import Result,TaskError,clean,display

TRUTH={'true':'true','yes':'true','false':'false','no':'false','unknown':'unknown','undetermined':'unknown',
       'not enough information':'unknown','inconsistent':'conflicting','conflicting':'conflicting','both true and false':'conflicting'}

def answer(result,options):
    value=display(result.value)
    proof={'family':result.family,'program':result.program,'value':value,'complete_source':True,
           'architecture':'bounded symbolic interpreter / relation and state automata','internet_used':False}
    if options is not None:
        matches=[]
        for i,opt in enumerate(options):
            if result.numeric:
                try:equal=Fraction(opt.strip())==result.value
                except (ValueError,ZeroDivisionError):equal=False
            elif result.family=='logic':equal=TRUTH.get(clean(opt))==value
            elif result.exact_text:equal=opt==value
            else:equal=clean(opt)==clean(value)
            if equal:matches.append(i)
        if len(matches)!=1:raise TaskError('The checked result does not identify exactly one option; please clarify the answer choices.')
        i=matches[0];response=f'{"ABCDEFGH"[i]}. {options[i]}'
    else:
        i=None;response=value if value else '""'
    out={'route':'chat/native-'+result.family,'response':response,'sources':[],'reasoning':proof,
         'verification':{'status':'verified','check':'Complete typed source compiled to bounded '+result.family+' operations; all declared dependencies retained.'},
         'details':'Native non-neural interpretation of the full supplied task. '+str(result.program)}
    if i is not None:out['choice']=i
    return out

def reply(text,options=None,reasoner=None):
    if not isinstance(text,str) or not 0<len(text)<=40000:return None
    if options is not None and (not 2<=len(options)<=8 or any(not isinstance(x,str) for x in options)):return None
    from . import interpretation_data as data,interpretation_relations as relations,interpretation_arithmetic as arithmetic
    cached=[reasoner]
    def get_reasoner():
        if cached[0] is None:
            from .reasoning import Reasoner
            cached[0]=Reasoner()
        return cached[0]
    for compile in (data.tables,data.strings,relations.order,lambda t:relations.state(t,get_reasoner),lambda t:relations.logic(t,get_reasoner),arithmetic.compile):
        try:
            result=compile(text)
            if result is not None:return answer(result,options)
        except TaskError as exc:
            return {'route':'chat/native-task-clarify','response':'Please clarify: '+str(exc),'sources':[],
                    'reasoning':{'complete_source':False,'unsupported_reason':str(exc),'internet_used':False},
                    'details':'The complete task remains owned by its symbolic interpretation path; no unsupported clause is discarded for a statistical guess.'}
    return None
