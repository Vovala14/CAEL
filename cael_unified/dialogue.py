"""Visible-history task continuity, clarification and actual answer reconsideration.

Non-neural act counts select short follow-ups; bounded task readers supply their
referents. No inferred session ID, hidden task cache or cross-user history.
Unsupported transformations ask rather than substitute an unrelated corpus hit.
"""
import re
from . import dialogue_policy

RESET=re.compile(r'(?i)^\s*(?:(?:never mind|nevermind|anyway)[.!,:]?\s*)?(?:new topic|different topic|change (?:the )?subject|start over)\s*[:.!-]?\s*')
FORGET=re.compile(r"(?i)^\s*(?:forget (?:everything|all (?:of )?that)|ignore (?:our|the) (?:earlier|previous) conversation)\b")
PRIVATE=re.compile(r'(?i)\b(?:my|our|mine|password|secret|account|appointment)\b|[\w.+-]+@[\w.-]+\.[a-z]{2,}')
SENSITIVE=re.compile(r'(?i)\b(?:suicid|self.harm|abuse|medicat|diagnos|chest pain|lawsuit|invest my|legal advice)')
ACTS={'shorter','simpler','example','expand','source','recheck','subject','bullets','one_step','casual','formal','number'}
WORDS={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'fifteen':15,'twenty':20,'thirty':30}

def answer(body,kind,**metadata):
    return {'route':'chat/dialogue-'+kind,'response':body,'sources':[],
            'details':'Bounded task/act reader reconstructed from visible role/content history; no hidden conversation state or neural model.',**metadata}

def clean(text):return text.strip().rstrip('.!? ')
def sentence(text):
    text=clean(text)
    return text[:1].upper()+text[1:]+'.' if text else ''
def users(messages):return [m['content'] for m in messages if m['role']=='user']

def active_messages(messages):
    """A visible reset is also respected by delegated old tools, not only us."""
    start=0;replacement=None
    for i,m in enumerate(messages):
        if m['role']!='user':continue
        reset=RESET.search(m['content']);forget=FORGET.search(m['content'])
        if reset or forget:
            start=i
            if reset:replacement=(i,m['content'][reset.end():].strip())
            else:replacement=(i,m['content'][forget.end():].lstrip(' .:!'))
    result=[m for m in messages[:start] if m['role']=='system']+[dict(m) for m in messages[start:]]
    if replacement:
        index=next(i for i,m in enumerate(result) if m['role']=='user')
        result[index]['content']=replacement[1]
    return result,start>0 or replacement is not None

def act(text):
    fitted=dialogue_policy.read(text)
    from .turn_instructions import read
    explicit=read(text)
    if explicit:return explicit,fitted
    # A complete new task is not an editing act just because its vocabulary
    # overlaps a heading, example or number request in the count model.
    from .dialogue_state import read_writing,goal_task
    if read_writing(text) or goal_task(text) or re.match(r'(?i)^(?:please\s+)?(?:write|implement|create|build)\b.*\b(?:function|program|code|script)\b',text):return None,fitted
    # A new question about a user's named relative/attribute is owned by the
    # personal-memory reader, not an inferred editing/source act.
    if re.match(r'(?i)^(?:who|what|where|when|which|how)\b',text) and re.search(r'(?i)\b(?:my|our)\b',text) and not re.match(r'(?i)^(?:how do you know|how did you learn|what is your source)',text):return None,fitted
    # Compound follow-ups often carry both content and style. Explicit bounded
    # style syntax can coexist with a correction, but never removes its words.
    if re.search(r'(?i)\b(?:less formal|more casually|casual tone)\b',text):return 'casual',fitted
    if re.search(r'(?i)\b(?:more formal|more polite|professional tone)\b',text):return 'formal',fitted
    if re.search(r'(?i)\b(?:are you sure|check (?:it|that|your answer) again|double.check|how do you know|source other than|not just wiki)\b',text):
        return ('source' if re.search(r'(?i)know|source|wiki',text) else 'recheck'),fitted
    # Concrete new information questions belong to the normal factual/context
    # readers. Count evidence alone cannot invent an earlier referent for them.
    if re.match(r'(?i)^(?:who|where|when|what|which|why|how)\b',text) and not re.search(r'(?i)\b(?:it|this|that|previous|above|your answer|your source|you know|you mean|you learn|did you learn)\b',text):return None,fitted
    return (fitted['act'],fitted) if fitted else (None,None)

def budget(text):
    matches=list(re.finditer(r'(?i)\b(\d{1,3}|'+ '|'.join(WORDS)+r')\s*(?:minutes?|mins?)\b',text))
    if not matches:return None
    # "three minutes, not ten" keeps three; explicit replacement on the next
    # turn supersedes the earlier budget.
    chosen=matches[-1]
    for m in matches:
        if not re.search(r'(?i)\bnot\s*$',text[max(0,m.start()-6):m.start()]):chosen=m
    value=WORDS.get(chosen[1].casefold()) or int(chosen[1])
    return value if 1<=value<=180 else None

def writing_task(text):
    match=re.search(r'(?is)^\s*(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:rewrite|reword|rephrase|make (?:this|the following) (?:message|text) (?:polite|clearer|friendlier))\b([^:]*):\s*(.+)$',text)
    if match:return {'kind':'rewrite','body':match[2].strip(),'polite':bool(re.search(r'(?i)polit|formal',match[1])),'source':text}
    match=re.search(r'(?is)^\s*(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:draft|write|compose) (?:an? |the )?email\b(.*)$',text)
    if not match:return None
    tail=match[1].strip();to=re.search(r'(?i)^to\s+([A-Z][\w -]{0,60}?)(?=\s+(?:asking|requesting|about|to ask|to request)|[:,]|$)',tail)
    recipient=to[1].strip() if to else None
    purpose=tail[to.end():].strip(' ,:') if to else tail
    purpose=re.sub(r'(?i)^(?:asking|to ask)(?:\s+(?:them|him|her))?\s+(?:to\s+)?','',purpose)
    if purpose.startswith('about '):purpose=purpose[6:]
    if not purpose:return {'kind':'email','missing':True,'to':recipient,'source':text}
    return {'kind':'email','body':clean(purpose),'to':recipient,'source':text}

def options(text):
    hits=list(re.finditer(r'(?:^|[\s;:])([1-4])[.)]\s*([^;\n]+?)(?=\s*[;\n]|\s+[1-4][.)]\s|$)',text))
    return [clean(m[2]) for m in hits] if 2<=len(hits)<=4 and [int(m[1]) for m in hits]==list(range(1,len(hits)+1)) else []

def frame(messages):
    current=None
    for m in messages:
        if m['role']!='user':continue
        text=m['content'];task=writing_task(text)
        if task:current=task;continue
        if current and act(text)[0] is None and re.match(r'(?i)^(?:what|who|when|where|how|why|calculate|compute|explain)\b',text):
            current=None  # a substantive new request ends the old draft/plan
        opts=options(text)
        if opts and re.search(r'(?i)\b(?:decide|choose|ideas|options|between)\b',text):current={'kind':'choice','options':opts,'source':text};continue
        if re.search(r'(?i)\b(?:presentation|talk|speech)\b',text) and re.search(r'(?i)\b(?:prepare|preparing|plan|need help|give|make|help)\b',text):
            current={'kind':'presentation','source':text,'topic':None,'audience':None};
            about=re.search(r'(?i)\babout (.+?)(?:[.!?]|$)',text)
            if about:current['topic']=clean(about[1])
        elif re.search(r'(?i)\b(?:want to learn|want to practice|make (?:me |a )?(?:a )?plan|help me plan|organize (?:the |my )?\w+ tasks)\b',text):
            goal=re.search(r'(?i)\b(?:want to|help me) (learn|practice|plan|organize)\s+(.+?)(?=,|\bbut\b|[.!?]|$)',text)
            if goal:current={'kind':'goal','goal':goal[1].lower()+' '+clean(goal[2]),'source':text}
        if current:
            if (value:=budget(text)) is not None:current['minutes']=value
            if current['kind']=='presentation':
                about=re.search(r'(?i)\babout (.+?)(?:[.!?]|$)',text)
                audience=re.search(r'(?i)\bfor (.+?)(?=\s+about\b|[.!?]|$)',text)
                if about:current['topic']=clean(about[1])
                if audience:current['audience']=clean(audience[1])
            if current['kind']=='choice':
                selection=re.search(r'(?i)\b(?:choose|pick|select|go with|use|take)\s+(?:the\s+)?(first|second|third|fourth|[1-4])\b',text)
                if selection:
                    key=selection[1].lower();index=int(key)-1 if key.isdigit() else ['first','second','third','fourth'].index(key)
                    if index<len(current['options']):current['selected']=current['options'][index]
            if current['kind'] in ('email','rewrite'):
                # Only explicit old-to-new replacement; no dropped unknown clause.
                correction=re.fullmatch(r'(?is)(?:actually[, ]+)?(?:change|replace)\s+["\']?(.+?)["\']?\s+(?:to|with)\s+["\']?(.+?)["\']?[.!]?',text.strip())
                if correction and correction[1] in current.get('body',''):
                    current['body']=current['body'].replace(correction[1],clean(correction[2]))
                chosen,_=act(text)
                if chosen in ('formal','casual','shorter','bullets') and not task:
                    current[chosen]=True
                    if chosen in ('formal','casual'):current['casual' if chosen=='formal' else 'formal']=False
            if act(text)[0]=='one_step':current['one_step']=True
            elif act(text)[0]=='expand':current['one_step']=False
    return current

def draft(task,chosen):
    if task.get('missing'):return answer('What should the email ask or tell the recipient?','writing-clarify')
    body=task['body'].strip()
    polite=task.get('polite') or task.get('formal');casual=task.get('casual')
    if task['kind']=='email':
        move=re.match(r'(?i)^move (.+?) (?:to|until) (.+)$',body)
        if chosen=='subject':
            if move:return answer('Reschedule: '+move[1]+' → '+move[2],'email-subject')
            return answer('Request: '+body[:100],'email-subject')
        request=('Could we move '+move[1]+' to '+move[2]+'?' if move else 'Could you '+body[:1].lower()+body[1:]+'?')
        if task.get('bullets') or chosen=='bullets':return answer('- '+request,'email-bullets')
        name=task.get('to') or '[Name]'
        greeting=('Dear ' if polite and not casual else 'Hi ')+name+','
        closing='Thanks,\n[Your name]'
        if task.get('shorter'):closing='Thanks!'
        return answer(greeting+'\n\n'+request+'\n\n'+closing,'email')
    # Literal transforms keep numbers, names, conditions, deadlines and negation.
    if polite and not casual and not re.match(r'(?i)please|could|would|do not|don.t|never',body):body='Please '+body[:1].lower()+body[1:]
    if casual:body=re.sub(r'(?i)^I would be grateful if you could\s+','Please ',body)
    if task.get('shorter'):body=re.sub(r'(?i)^I (?:just )?wanted to (?:ask|say) (?:that )?','',body)
    if task.get('bullets') or chosen=='bullets':body='\n'.join('- '+sentence(part) for part in re.split(r'(?<=[.!?])\s+',body) if part.strip())
    else:body=sentence(body)
    return answer(body,'rewrite',preserved_input=task['body'])

def plan(task,chosen):
    minutes=task.get('minutes');limit=(str(minutes)+' minutes' if minutes else 'a short session')
    one=chosen=='one_step' or task.get('one_step')
    if task['kind']=='presentation':
        if not task.get('topic'):return answer('What is the presentation about, and who is it for?','presentation-clarify')
        title=task['topic'];audience=(' for '+task['audience']) if task.get('audience') else ''
        first='Write one sentence stating what you want your audience to understand about '+title+'.'
        if one:return answer(first,'presentation-step')
        audience=audience.replace(' for my ',' for your ')
        return answer('Presentation about '+title+audience+' ('+limit+'):\n\n1. '+first+'\n2. Choose one concrete example to explain that sentence.\n3. Rehearse aloud, time it, and cut details until it fits.','presentation')
    if task['kind']=='choice':
        if not task.get('selected'):return answer('Your options are '+ ' or '.join(task['options'])+'. Which matters more for this choice: what you would enjoy or what is easiest to arrange?','decision-clarify')
        selected=task['selected'];first='For '+selected+', write down who it is for and one possible time.'
        return answer(first if one else 'Let’s use '+selected+'. '+first+' Then check whether that time works before arranging the details.','selected-option')
    goal=task['goal']
    if re.match(r'(?i)learn |practice ',goal):
        first='For '+limit+', practice one small part of '+goal.split(' ',1)[1]+': pick three words or one basic exercise, try it, then repeat without looking.'
        if one:return answer(first,'goal-step')
        return answer('Keep the goal to '+goal+', within '+limit+':\n\n1. Pick one small exercise or three words.\n2. Practice, then try again without looking.\n3. Note the one part to revisit next time.','goal-plan')
    return answer('To '+goal+', first write down the smallest observable result you need. Then list what is required for that result'+(' within '+limit if minutes else '')+'.','goal-plan')

def factual_question(messages):
    from . import web_search
    for m in reversed(messages):
        if m['role']!='user':continue
        text=m['content'];chosen,_=act(text)
        if chosen in ACTS or len(text)>500:continue
        if web_search.should_search(text) or re.fullmatch(r'[\d\s+*/().^%-]+',clean(text)):return text
        return None  # do not search an older public question for a new private one
    return None

def arithmetic(question):
    from .helper_chat import reply
    from .verify import check
    found=reply(question)
    if found and found.get('route')=='helper/arithmetic':return dict(found,verification=check(question,found))
    return None

def project(messages):
    rows=[]
    for index,m in enumerate(messages):
        if m['role']!='user':continue
        if re.match(r'(?i)^\s*forget (?:my |the )?(?:project|project name)\b',m['content']):rows=[];continue
        hit=re.match(r'(?i)^\s*(?:(actually|correction|update)[:, ]+)?my project (?:is (?:called|named)|name is)\s+["\']?([^.!?\n"\']{1,80})',m['content'])
        if hit:
            if hit[1]:rows=[]
            if hit[2].strip() not in [value for value,origin in rows]:rows.append((hit[2].strip(),index))
    return rows

# The inherited readers remain above for comparison/history. The new automaton
# owns transitions and literal transform contracts; no task cache is introduced.
from .dialogue_state import read_frame as frame,read_writing as writing_task
from .text_contract import render as draft

def reply(messages,delegate):
    if (not isinstance(messages,list) or not messages or len(messages)>1000 or
        not all(isinstance(m,dict) and m.get('role') in ('user','assistant','system') and isinstance(m.get('content'),str) for m in messages)
        or messages[-1]['role']!='user' or sum(len(m['content']) for m in messages)>64000 or len(messages[-1]['content'])>3000):return None
    messages,reset=active_messages(messages);text=messages[-1]['content'].strip();prior=messages[:-1]
    if not text:return answer('What would you like to talk about next?','reset') if reset else None
    if SENSITIVE.search(text):return delegate(messages) if reset else None
    from .grounded_compare import reply as comparison_reply
    compared=comparison_reply(text,delegate)
    if compared is not None:return compared
    chosen,fitted=act(text);task=frame(messages)
    from .request_reference import reply as reference_reply,anchor
    from .turn_instructions import is_code_update
    if is_code_update(text):
        target=anchor(prior)
        if target and target['kind']=='code':
            return answer('That adds a new requirement to the function. I can check pure-data operations in the bounded interpreter; restate the complete function contract and examples, including this requirement, so it is not silently omitted.','code-contract-update',pending_requirement=text,original_request=target['question'])
    referenced=reference_reply(messages,chosen)
    if referenced is not None:return referenced
    from .conversation_context import followup as structured_followup
    contextual=structured_followup(messages,None)
    if contextual is not None:return contextual
    from .conversation_context import workflow_reply
    workflow=workflow_reply(text)
    if workflow is not None:return workflow
    urls=re.findall(r'https?://[^\s<>"\']+',text)
    if urls and re.search(r'(?i)\b(?:check|read|source|verify)\b',text):
        from .web_evidence import answer as evidence,public_query
        remaining=clean(re.sub(r'https?://[^\s<>"\']+','',text))
        question=factual_question(prior)
        direct=re.search(r'(?i)\b(?:who|when|where|what|how|which)\b.+',remaining)
        if direct and public_query(direct[0]):question=direct[0]
        if question:
            found=evidence(question,force=True,source_urls=urls)
            if found:return found
        return answer('Which specific public claim should I check on that page?','source-clarify')
    # Explicit memory is attributed to the user, never public-search input.
    if re.search(r'(?i)\b(?:what do you (?:remember|recall|know) about (?:it|my project)|what(?:.s| is) my project(?: name)?|what did I (?:say|tell you).*(?:project|name))\b',text):
        rows=project(messages)
        body=('You told me your project is called '+rows[0][0]+'. I do not have other confirmed project details.' if rows else 'I do not have a project name you supplied in this visible conversation.')
        if len(rows)>1:body='You gave different project names: '+', '.join(value for value,index in rows)+'. Which one should I use?'
        return answer(body,'user-memory',user_evidence={'field':'project','statements':rows})
    if re.search(r'(?i)^forget (?:my |the )?(?:project|project name)',text):return answer('I will not use that project name in this conversation.','forget')
    rows=project(messages)
    if rows and re.match(r'(?i)^\s*(?:(?:actually|correction|update)[:, ]+)?my project (?:is (?:called|named)|name is)',text):
        if len(rows)>1:return answer('You gave different project names: '+', '.join(value for value,index in rows)+'. Which one should I use?','project-conflict',user_evidence=rows)
        value,index=rows[0]
        body='You’re calling the project '+value+'.'
        body+=(' For the launch, start by listing what must be ready and who owns each task.' if re.search(r'(?i)launch tasks',text) else ' What would you like help with on it?')
        return answer(body,'project-context',user_evidence={'message':index,'field':'project','value':value})
    # Existing attributed personal facts and emotional boundaries retain their
    # ownership. A nearest dialogue-act phrase cannot override these readers.
    if PRIVATE.search(text) and re.search(r'(?i)\bindependent(?:ly)?\b',text) and re.search(r'(?i)\b(?:verify|confirm|check)\b',text) and not writing_task(text):
        return answer('I can recall what you told me here, but I cannot independently confirm private facts. A statement in this chat is user-supplied evidence, not an external verification.','private-check',verification={'status':'unverifiable','check':'Private user details are not sent to search.'})
    from .session_profile import reply as profile_reply
    personal=profile_reply(messages)
    if personal is not None:return personal
    if writing_task(text) is None:
        from .emotional_chat import reply as emotional_reply
        feeling=emotional_reply(messages,137)
        if feeling is not None:return feeling
        from .conversation_context import reflection
        reflected=reflection(messages)
        if reflected is not None:return reflected
        from .emotional_chat import constraints
        constraint=constraints(text)
        explicit_listen=bool(re.fullmatch(r'(?is)(?:please\s+)?(?:just\s+)?listen(?:\s+(?:without|with no)\s+(?:advice|questions)(?:\s+or\s+(?:advice|questions))?)?[.!]?',text))
        if explicit_listen or (constraint['listen'] or constraint['no_questions']) and len(text)<180 and re.fullmatch(r'(?is)(?:please\s+)?(?:do not|don.t|no|just listen)\b[^?]*[.!]?',text):
            return answer('Understood. I can listen without giving advice'+(' or asking questions.' if constraint['no_questions'] or explicit_listen and re.search(r'(?i)questions',text) else '.'),'listening-preference')
    if prior and re.search(r'(?i)\b(?:he|she|they)\b',text) and re.match(r'(?i)(?:when|where|who|what|how)',text):
        previous_user=next((m['content'] for m in reversed(prior) if m['role']=='user'),'')
        names=re.search(r'\b([A-Z][a-z]+(?: [A-Z][a-z]+){0,2}) and ([A-Z][a-z]+(?: [A-Z][a-z]+){0,2})\b',previous_user)
        if names:return answer('Do you mean '+names[1]+' or '+names[2]+'?','antecedent-clarify',pending_question=text)
    comparing=re.match(r'(?i)^I am comparing (.+?) and (.+?)[.!]?$',text)
    if comparing:return answer('You’re comparing '+clean(comparing[1])+' and '+clean(comparing[2])+'. Which aspect would you like to compare?','comparison-clarify')
    # An answer to our clarification binds only an explicitly named option.
    if prior and prior[-1]['role']=='assistant':
        clarification=re.fullmatch(r'Do you mean (.+?) or (.+?)\?',prior[-1]['content'])
        if clarification and len(prior)>=2:
            selected=next((name for name in clarification.groups() if clean(text).casefold()==name.casefold()),None)
            if selected:
                original=prior[-2]['content']
                resolved=re.sub(r'(?i)\b(?:he|she|they)\b',selected,original)
                return dict(delegate(messages[:-1]+[{'role':'user','content':resolved}]),understood_as=resolved)
    if prior and chosen in ('source','recheck','number'):
        if chosen=='recheck' and prior[-1]['role']=='assistant' and '```python' in prior[-1]['content']:
            from .verify import check
            request=next((m['content'] for m in reversed(prior) if m['role']=='user' and act(m['content'])[0] not in ACTS),'')
            check_result=check(request,{'route':'chat/code-generated','response':prior[-1]['content']})
            if check_result['status']=='verified':body='I checked the visible code with the bounded interpreter: '+check_result['check']+'. This checks those cases, not every possible input.'
            elif check_result['status']=='failed':body='The code check found a problem: '+check_result['check']+'.'
            else:body='I could not establish correctness with the bounded checker: '+check_result['check']+'. Give me a concrete input and expected output to test.'
            return answer(body,'code-recheck',verification=check_result)
        question=factual_question(prior)
        if question:
            checked=arithmetic(question)
            if checked:
                if chosen=='number':
                    value=checked['response'].split('\n')[0].split(' = ')[-1]
                    return dict(checked,response=value,dialogue={'act':chosen,'original_request':question})
                return dict(checked,response=checked['response']+'\n\nI recalculated this with an independent exact arithmetic check.',dialogue={'act':chosen,'original_request':question})
            if chosen!='number':
                from .web_evidence import answer as evidence
                found=evidence(question,force=True,exclude_wikipedia=bool(re.search(r'(?i)wiki',text)))
                if found:return dict(found,dialogue={'act':chosen,'original_request':question})
        # Never leak a personal previous message to search just to answer "how
        # do you know". User history is evidence only of what the user said.
        if chosen in ('source','recheck'):
            return answer('Which specific claim should I check? I can recalculate arithmetic, use the bounded code checker, or read public sources; I cannot independently verify private details from your messages.','check-clarify')
    initial=writing_task(text)
    if task and (task.get('changed') or task.get('source')==text or initial or chosen in ACTS):
        if task['kind'] in ('email','rewrite'):return draft(task,None if initial else chosen)
        if task['kind'] in ('goal','presentation','choice'):
            from .dialogue_state import render_plan
            return render_plan(task,chosen)
    # An explicit concept is resolved once; subsequent examples/simpler requests
    # address it rather than matching an arbitrary unrelated corpus passage.
    context=' '.join(users(messages)[-6:])
    topic=next((t for t in reversed(users(messages)) if act(t)[0] not in ACTS),'')
    if re.search(r'(?i)\bpython\b',topic) and re.search(r'(?i)\blists?\b',topic) and re.search(r'(?i)\btuples?\b',topic):
        if len(users(messages))==1 or chosen in ('example','simpler','expand','shorter'):
            if chosen=='simpler':body='A list can be changed after you create it. A tuple cannot have its items replaced. Use square brackets for a list and parentheses for a tuple. A tuple can still contain a mutable object.'
            elif chosen=='example':body='```python\nitems = [1, 2]\nitems[0] = 9       # now [9, 2]\npair = (1, 2)\n# pair[0] = 9 would raise TypeError\n```\nThe assignment changes the list; the tuple does not allow replacing an item.'
            else:body='Lists and tuples both preserve item order. A list, like `[1, 2]`, allows adding, removing and replacing items. A tuple, like `(1, 2)`, does not allow replacing its items. A tuple can contain mutable objects; it can be a dictionary key only if all its elements are hashable.'
            return answer(body,'concept-followup')
    # Explicit public lookup also works without a previous question.
    if re.match(r'(?i)^(?:please )?(?:search(?: the web| online)? for|look up|check online(?: whether)?|find out)\b',text):
        from .web_evidence import answer as evidence
        return evidence(text,force=True)
    # Listening uses stated events, without a plan or invented personal facts.
    if re.search(r'(?i)\b(?:no advice|no questions|just (?:wanted to )?talk|just listen|no plan)\b',text) or (prior and re.search(r'(?i)\b(?:frustrat|nobody heard|not heard|ignored)\b',text)):
        if re.search(r'(?i)nobody heard|ignored|not heard',context):body='Feeling unheard sounds frustrating. I’m listening; you do not have to turn it into a plan.'
        elif re.search(r'(?i)frustrat',context):body='That sounds like a frustrating day. I’m listening; you do not have to turn it into a plan.'
        else:body='We can stay with what you wanted to share. I’m listening, without trying to turn it into advice.'
        return answer(body,'listening')
    activity=re.search(r'(?i)\bI spent (?:the )?(?:afternoon|morning|evening|day) (.+?)[.!]?(?:$)',text)
    if activity:return answer('You spent that time '+re.sub(r'(?i)\bmy\b','your',clean(activity[1]))+'. How did it go?','conversation')
    if prior and re.search(r'(?i)\b(?:part I enjoyed|working with my hands)\b',text):
        activity=next((m['content'] for m in reversed(prior) if m['role']=='user' and re.search(r'(?i)I spent .*\b(?:fixing|making|building|working)\b',m['content'])),None)
        if activity:return answer('The hands-on part was what you enjoyed. Was it the process itself or seeing the result?','conversation')
    if chosen and prior:
        from .conversation_context import followup
        related=followup(messages,chosen)
        if related is not None:return related
        return answer('I want to keep this connected to your request. Which part should I '+{'example':'illustrate','simpler':'explain more simply','shorter':'shorten','expand':'expand'}.get(chosen,'change')+'?','followup-clarify')
    if reset:return delegate(messages)
    return None
