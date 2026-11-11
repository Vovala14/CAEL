"""Request-local, source-linked conversation facts; no generated code or profile.

Finite first-person clause readers compose literal observations, goals, choices,
preferences and explicit reasons. Quoted/hypothetical content is not biography.
Unknown clauses stay visible, and assistant prose is never evidence.
"""
import re

from . import grounded_chat as gc

MAX_TURNS = 256
MAX_RECORDS = 160
RESET = re.compile(r"(?i)^(?:start over|new topic|reset (?:the |this )?(?:chat|conversation)|forget this conversation)[.!?]*$")
FORGET = re.compile(r"(?i)^(?:please )?forget (?:what I (?:said|told you) about )?(?:my )?(goals?|plans?|preferences?|choices?|activities|events?|reasons?)[.!?]*$")
EXCLUDED = re.compile(r"(?i)```|\b(?:suppose|imagine|hypothetical|translate|quote|fictional|suicid\w*|kill myself|hurt myself|self[- ]harm|overdose|cannot breathe|can't breathe|chest pain)\b")
REQUEST = re.compile(r"(?i)^(?:what|why|who|when|where|how|which|can you|could you|do you|please (?:explain|summari[sz]e|remind)|explain|summari[sz]e|remind me)\b")
REPAIR = re.compile(r"(?i)^(?:actually|correction|to correct that|instead)[,: ]+")
PATTERNS = [
    ('activity', r"I(?: am|'m| have been|'ve been) (working on|learning|practicing|practising|building|making) (.+)"),
    ('goal', r"I (want|need|hope|plan|intend|am trying|'m trying|would like|'d like) to (.+)"),
    ('need', r"I (need|require) (.+)"),
    ('choice', r"I (chose|choose|picked|selected|decided on|settled on) (.+)"),
    ('preference', r"I (prefer) (.+)"),
    ('event', r"I (?:(?:just|finally|recently|already) )?(finished|completed|fixed|repaired|made|built|started|enjoyed|liked|loved|painted|visited|bought|read|watched|learned|noticed|found|lost|forgot) (.+)"),
    ('part', r"(?:The |the )?(best|worst|rewarding|interesting|difficult|hardest|fun|satisfying) part(?: for me)? was (.+)"),
]
PATTERNS = [(kind, re.compile('(?:'+pattern+')[.!]?', re.I)) for kind, pattern in PATTERNS]


def clauses(text):
    """Preserve text offsets; split only complete sentences/explicit I-clauses."""
    result = []
    pattern = r"(?<=[.!?;])\s+|\n+|;\s*|,?\s+and\s+(?=I(?:\s|'m\b|'ve\b|'d\b))"
    begin = 0
    for match in re.finditer(pattern, text):
        if text[begin:match.start()].strip():
            result.append((text[begin:match.start()].strip(), begin, match.start()))
        begin = match.end()
    if text[begin:].strip():
        result.append((text[begin:].strip(), begin, len(text)))
    return result


def words(text):
    return set(re.findall(r"[\w'-]+", text.casefold())) - set('a an the my your me i it that this about did do say said tell told you to of on for am was is are'.split())


def read(messages):
    records = []
    unknown = []
    focus = []
    revision = 0
    for i, message in enumerate(messages):
        if message['role'] != 'user':
            continue
        text = message['content'].strip().replace('’', "'")
        if RESET.fullmatch(text):
            records = []; unknown = []; focus = []; revision += 1
            continue
        forget = FORGET.fullmatch(text)
        if forget:
            key = forget[1].casefold().rstrip('s')
            if key == 'activitie':key = 'activity'
            if key == 'plan':key = 'goal'
            for record in records:
                if key == 'reason':
                    record['reason'] = None
                    record['reason_forgotten'] = True
                    # Retain only the original statement prefix in exported
                    # evidence; a forgotten reason must not return via quotes.
                    statement=record['statement']
                    offset=record['text'].find(statement)
                    if offset>=0:
                        record['span']=[record['span'][0]+offset,record['span'][0]+offset+len(statement)]
                    record['text']=statement
                elif record['kind'] == key:
                    record['active'] = False
            focus = []
            continue
        if len(text) > 3000 or EXCLUDED.search(text):
            continue
        current_objects = []
        for raw, start, stop in clauses(text):
            body = raw.strip()
            if not body or body.startswith(('"', "'", '`', '“')):
                continue
            correction = bool(REPAIR.match(body))
            body = REPAIR.sub('', body).strip()
            if gc.PREFERENCE.fullmatch(body) or gc.CLOSE.fullmatch(body) or gc.INTRO.fullmatch(body):
                continue
            # Never interpret a question or its embedded I-clause as a fact.
            if '?' in body or REQUEST.match(body):
                continue
            reason_parts = re.split(r'\s+because\s+', body, maxsplit=1, flags=re.I)
            statement = reason_parts[0].rstrip('.!')
            reason = reason_parts[1].rstrip('.!') if len(reason_parts) == 2 else None
            found = None
            from .surface_grammar import read as surface_decode
            decoded=surface_decode(statement)
            if decoded and decoded['intent']=='ambiguous':
                unknown.append(dict(message=i,text=raw,span=[start,stop],reason='conflicting learned surface interpretations'))
                continue
            if decoded and decoded['intent'] in ('preference','choice'):
                obj=decoded['slots']['selected']
                found=dict(kind=decoded['intent'],verb='prefer' if decoded['intent']=='preference' else 'chose',
                    object=obj,alternative=decoded['slots']['rejected'],stance=decoded['stance'],
                    reason=reason,text=raw,message=i,span=[start,stop],active=True,correction=correction,
                    revision=revision,surface_object=obj,statement=statement,reason_forgotten=False,surface_model=decoded)
            for kind, pattern in PATTERNS:
                if found:break
                match = pattern.fullmatch(statement)
                if match:
                    verb, obj = match.groups()
                    obj = obj.strip().rstrip('.!')
                    if len(obj) > 400 or not obj or re.search(r'(?i)\b(?:if|unless|except|maybe|perhaps|might)\b', obj):
                        break
                    surface_object = obj
                    if obj.casefold() in ('it', 'this', 'that'):
                        antecedents = current_objects or focus
                        if len(antecedents) != 1:break
                        obj = antecedents[0]
                    found = dict(kind=kind, verb=verb, object=obj, reason=reason,
                                 text=raw, message=i, span=[start, stop], active=True,
                                 correction=correction, revision=revision, surface_object=surface_object,
                                 statement=statement,reason_forgotten=False)
                    break
            if found:
                if correction:
                    for earlier in records:
                        if earlier['kind'] == found['kind']:
                            earlier['active'] = False
                records.append(found)
                if found['object'] not in current_objects:current_objects.append(found['object'])
            elif re.match(r"(?i)^I(?:\s|'m\b|'ve\b)", body):
                unknown.append(dict(message=i, text=raw, span=[start, stop]))
            if len(records) + len(unknown) > MAX_RECORDS:
                return None
        # Do not carry a stale antecedent through an unrelated user statement.
        focus = current_objects
    return dict(records=records, unknown=unknown)


def answer(text, kind, records=(), **extra):
    return dict(route='chat/ledger-'+kind, response=text, sources=[],
        conversation_grounding=dict(evidence=list(records), user_claims_only=True,
            assistant_text_as_evidence=False, persistent_profile=False,
            finite_clause_reader=True), **extra)


def missing(kind):
    return answer('You have not stated '+kind+' in the messages I can use here. I won’t guess it.', 'unknown')


def render(records):
    result=[]
    for r in records:
        if r.get('alternative'):
            verb='lean toward' if r.get('stance')=='tentative' else 'prefer' if r['kind']=='preference' else 'chose'
            text='- You said you '+verb+' “'+r['object']+'” over “'+r['alternative']+'”.'
            if r.get('reason'):text+=' Your stated reason: “'+r['reason']+'”.'
        else:text='- You said: “'+r['text'].strip().rstrip(';')+'”'
        if r.get('surface_object',r['object']) != r['object']:
            text += ' Here “'+r['surface_object']+'” refers to “'+r['object']+'”.'
        result.append(text)
    return '\n'.join(result)


def reply(messages):
    if not messages or len(messages) > MAX_TURNS or sum(len(m['content']) for m in messages) > 400000:
        return None
    raw = messages[-1]['content'].strip().replace('’', "'")
    if not raw or len(raw) > 3000 or EXCLUDED.search(raw) or raw.startswith(('"', "'", '`', '“')):
        return None
    state = read(messages)
    if state is None:return None
    records = [r for r in state['records'] if r['active']]
    # Identity, safety, pure closure and task readers keep their established routes.
    if gc.NAME_QUESTION.fullmatch(raw) or gc.FORGET.fullmatch(raw) or gc.CLOSE.fullmatch(raw):
        return None
    if RESET.fullmatch(raw):
        return answer('Starting a new topic. I’ll use new details you give me; the visible chat history has not been deleted.', 'reset')
    if FORGET.fullmatch(raw):
        return answer('I’ll stop using that category of details here. The visible chat history has not been deleted.', 'forget')
    pieces=clauses(raw)
    query_text=raw
    if len(pieces)>1 and (REQUEST.match(pieces[-1][0]) or '?' in pieces[-1][0]):
        current=[r for r in records if r['message']==len(messages)-1]
        extra=[r for r in state['unknown'] if r['message']==len(messages)-1]
        if current and not extra:
            query_text=pieces[-1][0]
    t = query_text.strip(' .!?')
    from .surface_grammar import read as surface_decode
    query_frame=surface_decode(t)
    if query_frame and query_frame['intent']=='query_preference':t='What do I prefer'
    elif query_frame and query_frame['intent']=='query_choice':t='What did I choose'
    if re.fullmatch(r'(?i)(?:(?:can|could) you )?(?:summari[sz]e (?:what I (?:said|told you)|(?:our|this) conversation|my (?:situation|goals|plans))|what have (?:I|we) (?:discussed|talked about)|what do you (?:know|remember) about me)', t):
        selected = records
        if re.search(r'(?i)my (?:goals|plans)', t):selected = [r for r in records if r['kind']=='goal']
        if not selected:return missing('those details')
        selected = selected[-8:]
        text = 'From your messages:\n'+render(selected)
        if state['unknown']:
            text += '\nI also have these statements, which I have not interpreted: '+ ' '.join('“'+r['text']+'”' for r in state['unknown'][-3:])
        return answer(text, 'summary', selected, unparsed_statements=state['unknown'])
    reason = re.fullmatch(r'(?i)(?:why (?:did|do) I (?:choose|pick|select|prefer|want|need|start|build|make|decide on|work on)(?: (.+))?|(?:can you )?(?:remind me|explain) why(?: I (?:chose|picked|prefer|want|need|started|am working on) (.+))?)', t)
    bare_why = t.casefold() in ('why','why is that')
    if bare_why and records:
        # Bare follow-ups bind only to the immediately preceding user facts,
        # not to a new invented interpretation of the assistant's last reply.
        last_message=max(r['message'] for r in records)
        choices=[r for r in records if r['message']==last_message]
        if len(choices)!=1:
            return answer('You mentioned several things. Which statement do you want the reason for?', 'reason-ambiguous',choices)
        reason=re.fullmatch(r'(.*)?', '')
    if reason:
        topic = next((p for p in reason.groups() if p), None)
        if not bare_why:choices = records
        if re.search(r'(?i)\b(?:choose|chose|pick|picked|select|selected|decide on)\b', t):choices=[r for r in choices if r['kind']=='choice']
        elif re.search(r'(?i)\bprefer\b', t):choices=[r for r in choices if r['kind']=='preference']
        if topic and topic.casefold() not in ('it', 'that', 'this'):
            query = words(topic)
            choices = [r for r in records if query and query <= words(r['object'])]
        if not choices:return missing('a reason for that')
        chosen = choices[-1]
        if chosen.get('reason_forgotten'):
            return answer('You asked me not to use that reason. The statement I can still use is: “'+chosen['statement']+'”.', 'reason-forgotten', [chosen])
        if not chosen['reason']:
            return answer('You said “'+chosen['text']+'”, but you did not give a reason for that. I won’t invent one.', 'reason-unknown', [chosen])
        return answer('You said your reason was: “'+chosen['reason']+'”.', 'reason', [chosen])
    kind = None
    if re.fullmatch(r'(?i)what (?:am I (?:working on|learning|practicing|practising|building|making)|have I been working on)', t):kind='activity'
    elif re.fullmatch(r"(?i)what (?:am I trying to do|do I (?:want|hope|plan|intend) to do|(?:is|was) my goal|are my goals|did I (?:say I )?(?:want|plan|hope) to do)", t):kind='goal'
    elif re.fullmatch(r'(?i)(?:what do I prefer|what (?:is|was) my preference|which (?:option )?do I prefer)', t):kind='preference'
    elif re.fullmatch(r'(?i)(?:what did I (?:choose|pick|select|decide on)|which (?:one|option) did I (?:choose|pick|select))', t):kind='choice'
    elif re.fullmatch(r'(?i)what do I (?:need|require)', t):kind='need'
    elif re.fullmatch(r'(?i)what did I (?:say I )?(?:finish|complete|fix|repair|start|build|make|enjoy|like|love|visit|paint|buy|read|watch|learn|notice|find|lose|forget)', t):
        kind='event'
        verbs = dict(finish={'finished','completed'}, complete={'completed','finished'}, fix={'fixed','repaired'},repair={'repaired','fixed'},start={'started'},build={'built'}, make={'made'}, enjoy={'enjoyed','liked','loved'}, like={'liked','loved','enjoyed'},love={'loved','liked','enjoyed'},visit={'visited'}, paint={'painted'}, buy={'bought'}, read={'read'}, watch={'watched'}, learn={'learned'}, notice={'noticed'}, find={'found'}, lose={'lost'}, forget={'forgot'})
        verb=t.rsplit(' ',1)[-1].casefold(); records=[r for r in records if r['verb'].casefold() in verbs.get(verb,set())]
    topic = re.fullmatch(r'(?i)what did I (?:tell you|say|mention|share) about (.+)', t)
    if kind or topic:
        selected = [r for r in records if r['kind']==kind] if kind else [r for r in records if words(topic[1]) and words(topic[1]) <= words(r['text'])]
        if not selected:
            if kind=='event' and any(re.search(r'(?i)\b(?:it|this|that)\b',r['text']) for r in state['unknown']):
                return answer('The action was mentioned, but its object is ambiguous. Which object do you mean?', 'event-ambiguous')
            return missing('that detail')
        return answer(render(selected[-6:]), 'recall', selected[-6:])
    current = [r for r in records if r['message']==len(messages)-1]
    # No dropping an unanswered question or second unsupported factual clause.
    if current and not any(REQUEST.match(c[0]) or '?' in c[0] for c in clauses(raw)):
        extra = [r for r in state['unknown'] if r['message']==len(messages)-1]
        # Preserve simple inherited reflection/identity routes. The ledger owns
        # composition, goals/choices/preferences, reasons and explicit repairs.
        if len(current)==1 and not extra and current[0]['kind'] in ('event','activity','part') and not current[0]['reason'] and not current[0]['correction']:
            return None
        text='I’m following:\n'+render(current)
        if extra:text+='\nI have not interpreted this part: '+' '.join('“'+r['text']+'”' for r in extra)
        return answer(text, 'reflection', current, unparsed_statements=extra)
    return None
