"""Conversation-scoped premise handling for the existing non-neural reasoner."""
import re

HEADER=re.compile(r'(?i)^\s*(facts|premises|given|suppose|scenario|context|add|also|update)\s*:\s*')
WHY=re.compile(r'(?i)^\s*(?:why|why is that|explain(?: that| this| your answer| the answer)?|how did you (?:get|deduce|conclude) that|which (?:facts|premises) did you use)[?.!]*\s*$')
RESET=re.compile(r'(?i)^\s*(?:forget|clear|reset) (?:the |these |those )?(?:premises|scenario|reasoning context)[?.!]*\s*$')


def reasoning_response(text):
    return (text.startswith(('Premises saved.','The stated premises do not determine','The stated premises conflict'))
            or '\n\nBased on:\n' in text or text.startswith(('Yes, that follows from the premises.','No—the premises establish its opposite.')))


def quantity_exchange(context,question,text,response):
    """Keep quantity premises only when a bounded replay reproduces the reply.

    The replay has no conversation, so it cannot recurse through this history
    reconstruction or learn state from an incidental number in a response.
    """
    from .helper_chat import clean_request,reply
    from .reasoning import split_problem
    prepared=clean_request(text)
    explained=bool(re.match(r'(?i)^(?:explain(?: how to calculate)?|show(?: me)? (?:the )?(?:steps|working)(?: for)?)\s*:?\s+',prepared))
    if explained:prepared=re.sub(r'(?i)^(?:explain(?: how to calculate)?|show(?: me)? (?:the )?(?:steps|working)(?: for)?)\s*:?\s+','',prepared)
    head=HEADER.match(prepared)
    payload=prepared[head.end():] if head else prepared
    if WHY.fullmatch(prepared):
        if not context or not question:return None
        prompt='Explain Given: '+context+'. '+question
    else:
        problem=split_problem(payload)
        if problem:
            addition,query,_=problem
            context=context+'. '+addition if head and head[1].lower() in ('add','also','update') and context else addition
            question=query
        elif context and re.match(r'(?i)^how (?:many|much)\b',prepared):question=prepared
        else:return None
        prompt=('Explain ' if explained else '')+'Given: '+context+'. '+question
    if len(prompt)>5000:return None
    expected=reply(prompt,None)
    if (expected and expected['route'] in ('helper/quantity','helper/quantity-clarify')
            and expected['response']==response):return context,question
    return None


def context_from_history(messages):
    from .reasoning import split_problem
    context='';question=None
    for i in range(max(0,len(messages)-81),len(messages)-1):
        entry=messages[i]
        if entry.get('role')!='user' or i+1>=len(messages)-1:continue
        response=messages[i+1]
        if response.get('role')!='assistant':continue
        text=entry['content'].strip()
        if WHY.fullmatch(text) and response['content'].startswith('What conclusion should I explain'):
            continue
        if not reasoning_response(response['content']):
            quantity=quantity_exchange(context,question,text,response['content'])
            if quantity is not None:
                context,question=quantity;continue
            context='';question=None;continue
        head=HEADER.match(text)
        payload=text[head.end():] if head else text
        problem=split_problem(payload)
        if problem:
            addition,question,_=problem
            context=(context+'. '+addition) if head and head[1].lower() in ('add','also','update') and context else addition
        elif head:
            context=(context+'. '+payload) if head[1].lower() in ('add','also','update') and context else payload
            if head[1].lower() not in ('add','also','update'):question=None
        elif not WHY.fullmatch(text):
            question=text
    return context.strip(' .\n'),question


def respond(engine,text,messages=None):
    from .reasoning import split_problem
    from .reasoning_logic import sentences
    if not engine.model:return None
    history=messages or []
    context,last_question=context_from_history(history)
    if RESET.fullmatch(text):
        return dict(route='chat/reasoning-context',response='Premises cleared. Start a new scenario with “Facts:”.',sources=[])
    head=HEADER.match(text)
    if head:
        payload=text[head.end():].strip()
        problem=split_problem(payload)
        if head[1].lower() in ('add','also','update'):
            if not context:
                return dict(route='chat/reasoning-clarify',response='Which scenario should I add that to? Start with “Facts:” and the premises.',sources=[])
            if problem:
                addition,question,_=problem
                return engine._respond('Given: '+context+'. '+addition+'. Question: '+question,None)
            context=context+'. '+payload
        elif problem:
            return engine._respond(text,None)
        else:context=payload
        if not context or len(context)>40000 or len(sentences(context))>400:
            return dict(route='chat/reasoning-unsupported',response='Use between 1 and 400 premises, within 40,000 characters.',sources=[])
        return dict(route='chat/reasoning-context',response='Premises saved. Ask your question, or use “Add:” for another premise.',sources=[],
                    details='Premises are reconstructed from this conversation only. They have not yet been checked for consistency or parseability; no internet request or training storage.')
    if context and WHY.fullmatch(text):
        if not last_question:
            return dict(route='chat/reasoning-clarify',response='What conclusion should I explain from those premises?',sources=[])
        return engine._respond('Given: '+context+'. '+last_question,None)
    if context and re.match(r'(?i)^(?:is|are|does|do|where|who|what|how|which|why|can|must)\b',text):
        # Only a contiguous reasoning exchange carries premises forward.
        ignored=set('is are was were does do did where who what how which why can must will would the a an of to in from for that it we you true false prove conclude follow'.split())
        relevant=(set(re.findall(r'\w+',context.lower())) & set(re.findall(r'\w+',text.lower()))) - ignored
        if relevant:
            answer=engine._respond('Given: '+context+'. '+text,None)
            if answer and answer['route']!='chat/reasoning-unsupported':return answer
        # Unrelated factual questions must reach the ordinary lookup route.
        return engine._respond(text,None)
    return engine._respond(text,messages)
