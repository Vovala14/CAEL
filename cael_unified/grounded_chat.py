"""Literal user identity, event reflection and closure before fuzzy edit acts.

No profile store or factual inference: evidence is the supplied user messages.
"""
import re

NAME = r"[\w][\w'’.-]*(?:[ -][\w][\w'’.-]*){0,3}"
INTRO = re.compile(r"(?is)^(?:(?:hi|hey|hello)[,! ]+)?(?:(actually|correction|sorry|instead)[,: ]+)?(?:my (?:name|nickname) is|i go by|(?:please )?call me|you can call me)\s+(.+?)[.!]?$", re.I)
NAME_QUESTION = re.compile(r"(?i)^(?:what(?:'s| is) my name|(?:do|can) you remember my name|who am i|what (?:did|do) i (?:ask|tell) you to call me|what should you call me|what name did i (?:give|tell) you|what did i say my name was|do you remember what i (?:asked|wanted) (?:you )?to call me)[?.!]*$")
FORGET = re.compile(r"(?i)^(?:please )?(?:forget|clear|delete) (?:my name|what i (?:said|told you) about my name)[.!?]*$")
RESET = re.compile(r"(?i)^(?:start over|reset (?:the |this )?(?:chat|conversation)|forget this conversation)[.!?]*$")
CLOSE = re.compile(r"(?i)^(?:(?:ok|okay|great)[,!. ]+)?(?:thanks(?: (?:a lot|so much))?(?: for (?:listening|the (?:help|chat)|your (?:help|time)|helping(?: me)?))?|thank you(?: for (?:listening|helping(?: me)?|your (?:help|time)))?|that(?:'s| is) (?:all|enough)(?: for now)?|i(?:'m| am) done(?: for now)?|talk (?:to you )?later|goodbye|bye)[.!]*$")
PREFERENCE = re.compile(r"(?i)^(?:please )?(?:no (?:more )?(?:questions|advice|plans|solutions)(?:\s*(?:or|and)\s*(?:questions|advice|plans|solutions))?(?: please)?|just listen|i (?:just |only )?(?:want|wanted) (?:you )?to listen|(?:don't|do not) (?:ask(?: me)? (?:any )?questions|give(?: me)? (?:any )?advice))[.!]*$")
EVENT = re.compile(r"(?is)^I\s+(?:(?:just|finally|recently|already)\s+)?(finished|completed|fixed|repaired|made|built|started|enjoyed|liked|loved|practiced|practised|managed to finish|spent (?:the )?(?:morning|afternoon|evening|day))\s+(.+?)[.!]?$", re.I)
WORK = re.compile(r"(?is)^I(?: am|'m| have been|'ve been) (working on|learning|practicing|practising)\s+(.+?)[.!]?$", re.I)
PART = re.compile(r"(?is)^(?:the )?(best|worst|satisfying|satisfying|frustrating|difficult|hard|easy|rewarding|interesting|fun|disappointing) part(?: for me)? was (.+?)[.!]?$", re.I)
PART2 = re.compile(r"(?is)^(?:the )?part I (liked|loved|enjoyed|disliked)(?: most| least)? was (.+?)[.!]?$", re.I)
RECALL = re.compile(r"(?i)^(?:what (?:was|am) i (?:working on|learning|practicing|practising)|what did i (?:say i )?(?:finish|complete|enjoy|like|build|make|mention|share)|what (?:was|is) the (?:best|worst|satisfying|rewarding|interesting|fun) part(?: i (?:mentioned|described))?|what did i (?:like|enjoy)(?: most| about (?:it|that))?)[?!\.]*$")


def name_value(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1]
    if not 1 <= len(text) <= 64 or not re.fullmatch(NAME, text):
        return None
    if re.search(r"(?i)\b(?:not|never|unless|because|when|tomorrow|later|and|or|instead|if|please)\b", text):
        return None
    return text


def identity(messages):
    names = []; preferred = None; last = None
    for i, m in enumerate(messages):
        if m['role'] != 'user':
            continue
        text = m['content'].strip()
        if FORGET.fullmatch(text) or RESET.fullmatch(text):
            names = []; preferred = None; last = ('forget', i, None)
            continue
        if text.startswith(('"',"'",'`')) or re.search(r'(?i)\b(?:imagine|suppose|hypothetical|translate|quote|quoted|fictional)\b',text):continue
        clauses=re.split(r'(?<=[.!?])\s+|\n+',text)
        for clause in clauses:
            match = INTRO.fullmatch(clause.strip())
            implicit = None if match else re.fullmatch(r"(?i)(?:(?:hi|hello|hey)[,! ]+)?I(?: am|'m) (.+?)[.!]?",clause.strip())
            if not match and not implicit:continue
            value = name_value(match[2] if match else implicit[1])
            if value is None:continue
            if implicit:
                from .emotional_chat import WORDS
                blocked=set(WORDS)|set('good fine okay alright lost confused hungry bored human teacher student doctor engineer person robot assistant happy sad suicidal'.split())
                if value.casefold() in blocked or not value[0].isupper():continue
            address = bool(match and re.search(r"(?i)\b(?:call me|go by|nickname)\b", clause))
            if address:preferred = (value, i)
            else:
                if match and match[1]:names = []
                if not any(n[0] == value for n in names):names.append((value, i))
            last = ('address' if address else 'name', i, value)
    return names, preferred, last


def event(text, index):
    if len(text) > 900 or any(x in text for x in ('```', '"', '“', '?')):
        return None
    parts = re.split(r'(?<=[.!])\s+|\n+', text.strip())
    content = [p for p in parts if p.strip() and not PREFERENCE.fullmatch(p.strip())]
    if len(content) != 1:
        return None  # do not discard a second factual/emotional clause
    body = content[0].strip()
    if re.search(r"(?i)\b(?:suicid\w*|kill myself|hurt myself|self[- ]harm|chest pain|cannot breathe|can't breathe|overdose|bleeding)\b",body):return None
    if re.search(r"(?i)\b(?:suppose|imagine|hypothetical|if|unless|quote|translate)\b", body):
        return None
    for pattern, kind in [(WORK, 'activity'), (EVENT, 'event'), (PART, 'part'), (PART2, 'part')]:
        match = pattern.fullmatch(body)
        if match:
            verb, obj = match.groups()
            obj = obj.rstrip('.!')
            if not obj or len(obj) > 300:
                return None
            return dict(kind=kind, verb=verb, object=obj, text=body, message=index)
    return None


def answer(text, kind, evidence=None, **extra):
    return dict(route='chat/grounded-'+kind, response=text, sources=[],
                conversation_grounding=dict(evidence=evidence or [], user_claims_only=True,
                    assistant_text_as_evidence=False, persistent_profile=False), **extra)


def reply(messages):
    if not messages or len(messages) > 256 or sum(len(m['content']) for m in messages) > 400000:
        return None
    raw = messages[-1]['content'].strip()
    if not raw or len(raw) > 1200 or raw.startswith(('"', "'", '`')):
        return None
    names, preferred, last = identity(messages)
    if FORGET.fullmatch(raw):
        return answer('I will stop using the name from this conversation. I have not deleted the visible chat history.', 'identity-clear')
    if last and last[1] == len(messages)-1 and last[0] != 'forget' and not re.search(r'(?i)\?|\b(?:what|who|where|how|why|which|calculate|compute|write|solve)\b',raw):
        if len(names) > 1 and last[0] == 'name':
            return answer('You have given more than one name here: '+', '.join(n[0] for n in names)+'. Which should I use?', 'identity-conflict',
                          [dict(value=n, message=i) for n,i in names])
        return answer('I’ll call you '+last[2]+'.' if last[0] == 'address' else 'Nice to meet you, '+last[2]+'.', 'introduction',
                      [dict(message=last[1], value=last[2])])
    if NAME_QUESTION.fullmatch(raw.replace('’', "'")):
        if re.search(r'(?i)\bcall me|call you|call|ask|should\b', raw) and preferred:
            return answer('You asked me to call you '+preferred[0]+'.', 'identity-recall', [dict(message=preferred[1],value=preferred[0])])
        if len(names) == 1:
            return answer('You told me your name is '+names[0][0]+'.', 'identity-recall', [dict(message=names[0][1], value=names[0][0])])
        if len(names) > 1:
            return answer('You have used '+', '.join(n[0] for n in names)+'. I cannot tell which is current without a correction.', 'identity-conflict', [dict(message=i,value=n) for n,i in names])
        if preferred:
            return answer('You asked me to call you '+preferred[0]+'. You have not given a separate name.', 'identity-recall', [dict(message=preferred[1],value=preferred[0])])
        return answer('You have not given me a current name to use in this conversation.', 'identity-unknown')
    if CLOSE.fullmatch(raw.replace('’', "'")):
        return answer('You’re welcome. Thank you for sharing that with me.' if re.search(r'(?i)thank',raw) else 'Take care. We can leave it there for now.', 'closure')
    records = []
    for i,m in enumerate(messages):
        if m['role'] != 'user':
            continue
        if RESET.fullmatch(m['content'].strip()):
            records = []; continue
        found = event(m['content'], i)
        if found:
            records.append(found)
    if RECALL.fullmatch(raw):
        match_records = records
        if re.search(r'(?i)part|most|about', raw):
            match_records = [r for r in records if r['kind'] == 'part' or r['verb'].lower() in ('enjoyed','liked','loved')]
        elif re.search(r'(?i)working|learning|practic',raw):
            match_records = [r for r in records if r['kind']=='activity']
        elif re.search(r'(?i)finish|complete',raw):
            match_records = [r for r in records if r['verb'].lower() in ('finished','completed','managed to finish')]
        if not match_records:
            return answer('I do not have that detail in your messages here. I won’t invent it.', 'event-unknown')
        chosen = match_records[-1]
        return answer('You said: “'+chosen['text']+'”', 'event-recall', [chosen])
    found = records[-1] if records and records[-1]['message'] == len(messages)-1 else None
    if found:
        from .emotional_chat import preferences
        listen, questions = preferences(messages)
        obj = re.sub(r'(?i)\bmy\b', 'your', found['object'])
        if found['kind']=='part':
            lead = ('You '+found['verb'].lower()+' '+obj+'.' if found['verb'].lower() in ('liked','loved','enjoyed','disliked')
                    else 'The part you described as '+found['verb'].lower()+' was '+obj+'.')
        elif found['kind']=='activity':
            lead = 'You’re '+found['verb'].lower()+' '+obj+'.'
        else:
            lead = 'You '+found['verb'].lower()+' '+obj+'.'
        if not listen and questions:
            # One related invitation; avoid repeating the same question.
            previous = [m['content'] for m in messages[:-1] if m['role']=='assistant']
            tail = ' What stood out to you?' if not any('What stood out to you?' in t for t in previous[-4:]) else ' I’m following what you wanted to share.'
        else:
            tail = ' I can stay with that without turning it into advice or more questions.'
        return answer(lead+tail, 'reflection', [found])
    return None
