"""Conservative multiple-choice bridge to CAEL's existing symbolic engines.

Only questions about explicit premises are eligible. A narrative continuation
is not a claim that must already be true. Unsupported/ambiguous input falls
through to the selected count/evidence chooser without changing its scores.
No benchmark names, answer memories, web calls or new model architecture.
"""
import re

from .reasoning import Reasoner, split_problem
from .reasoning_logic import LogicCA, Unparsed, sentences
from .reasoning_world import WorldCA

NAME = r'[a-z][a-z-]{0,30}'
THING = r'(?:the |an? )?[a-z][a-z-]*(?: [a-z][a-z-]*){0,3}'


def key(text):
    return re.sub(r'^(?:the|a|an)\s+', '', text.lower().strip(' .?!'))


def state_context(context, model):
    """Lossless narrow surface aliases; require every premise to parse.

    Resolve no pronouns here: the general rewrite helper's latest-person
    heuristic is insufficient for a verified multiple-choice override.
    """
    if re.search(r'(?i)\b(?:he|she|they|it|his|her|their|someone|perhaps|maybe|might|could|would|if|unless|not|never)\b',context):
        raise Unparsed('Ambiguous reference, uncertainty or unsupported condition')
    context=re.sub(r'(?i)^(?:facts|premises|given|scenario|context)\s*:\s*','',context)
    world=WorldCA(model)
    normalized=[]
    for index,statement in enumerate(sentences(context),1):
        text=re.sub(r'(?i)^(?:then|next|afterwards|later)\s*,?\s*','',statement).lower()
        held=re.fullmatch(rf'({NAME}) (?:holds|has|is carrying) ({THING})',text)
        passive=re.fullmatch(rf'({THING}) is (?:held|carried) by ({NAME})',text)
        receive=re.fullmatch(rf'({NAME}) (?:receives|received) ({THING}) from ({NAME})',text)
        give=re.fullmatch(rf'({NAME}) (?:gives|hands|passes) ({THING}) to ({NAME})',text)
        if held:
            text=f'{held[1]} picked up {held[2]}'
        elif passive:
            text=f'{passive[2]} picked up {passive[1]}'
        elif receive:
            text=f'{receive[3]} gave {receive[2]} to {receive[1]}'
        elif give:
            text=f'{give[1]} gave {give[2]} to {give[3]}'
        event=world.event(text)
        if event[0]=='give':
            obj=world.cells.get(event[2])
            if event[1]==event[3] or obj and obj.owner and obj.owner!=event[1]:
                raise Unparsed('Conflicting transfer ownership')
        world.apply(event,index)
        normalized.append(text)
    if not normalized or len(normalized)>100:
        raise Unparsed('Keep explicit state questions within 100 premises')
    return '. '.join(normalized),world


def answer_options(question, answer, endings):
    """Match whole answer propositions, never substrings or stripped negation."""
    q=question.lower().strip(' ?.').replace(' now','')
    allowed={key(answer)}
    located=re.fullmatch(r'where is (?:the )?(.+)',q)
    holding=re.fullmatch(r'who (?:has|holds|owns|is carrying) (?:the )?(.+)',q)
    giver=re.fullmatch(r'who (?:gave|handed) (?:the )?(.+?) to (.+)',q)
    receiver=re.fullmatch(r'who received (?:the )?(.+)',q)
    if located:
        allowed.add(key(f'{located[1]} is in the {answer}'))
    if holding:
        for verb in ('has','holds','is carrying'):
            allowed.add(key(f'{answer} {verb} the {holding[1]}'))
    if giver:
        allowed.add(key(f'{answer} gave the {giver[1]} to {giver[2]}'))
    if receiver:
        allowed.add(key(f'{answer} received the {receiver[1]}'))
    if answer in ('true','yes'):
        allowed|={'yes','true'}
    if answer in ('false','no'):
        allowed|={'no','false'}
    matches=[i for i,ending in enumerate(endings) if key(ending) in allowed]
    return matches[0] if len(matches)==1 else None


def reply(context, endings, reasoner=None):
    if not isinstance(context,str) or len(context)>12000 or not 2<=len(endings)<=4:
        return None
    if not all(isinstance(e,str) and 0<len(e)<=500 for e in endings):
        return None
    problem=split_problem(context)
    if not problem:
        return None
    premises,question,_=problem
    question=question.strip()
    proof_question=bool(re.fullmatch(r'(?i)which (?:statement|conclusion|option) (?:follows(?: from (?:these|the) premises)?|must be true)\s*[?:.]?',question))
    state_question=bool(re.fullmatch(r'(?i)(?:where is .+|who (?:has|holds|owns|is carrying|gave|handed|received) .+|who did .+ give .+ to|what did .+ give to .+|how many objects is .+ carrying|is .+ in .+)\??',question))
    if not (proof_question or state_question):
        return None
    reasoner=reasoner or Reasoner()
    if not reasoner.model:
        return None
    try:
        if proof_question:
            # Horn proofs are checked against the existing exhaustive-case
            # engine by Reasoner.solve, including conflicting premises.
            results=[reasoner.solve(premises,ending.strip()) for ending in endings]
            if any(r.get('inferred') or r.get('family') not in ('logic','logic-cases') or r['answer']=='conflicting' for r in results):
                return None
            proved=[i for i,r in enumerate(results) if r['answer']=='true']
            if len(proved)!=1:
                return None
            best=proved[0]
            result=results[best]
        else:
            normalized,_=state_context(premises,reasoner.model)
            q=re.sub(r'(?i)\s+now\b','',question)
            result=WorldCA(reasoner.model).query(normalized,q)
            result['family']='state'
            if result['answer'] in ('unknown','conflicting','maybe'):
                return None
            best=answer_options(q,result['answer'],endings)
            if best is None:
                return None
    except Unparsed:
        return None
    result=dict(result,internet_used=False)
    return dict(route='chat/choice-symbolic',response=f'{"ABCD"[best]}. {endings[best].strip()}',
                sources=[],choice=best,reasoning=result,
                details='Chosen from explicit premises by the existing '+result['family']+
                        ' solver. Unsupported or ambiguous scenarios fall back to the count/evidence chooser. No internet or neural model.')
