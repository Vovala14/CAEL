"""The evidence check (0.4.4, after an outside blind test): a looked-up passage or an advice template may answer a
question only when it supplies what was asked about the thing named.

In the blind test, retrieval matched the noun and missed the requested fact: "How many sides does a hexagon have?" got a
sentence about the length of one side, "Where are the keys?" (keys the user had placed) got relationship advice, and
"What is the serial number on my kitchen clock?" got medical advice. Each of these is caught here and replaced by a
reply that says which fact is missing. Exact desks (solvers, the swarm desk, memory) are never second-guessed.

Three checks, in order:
  1. Something only the user can know: a property of the user's own object ("the serial number on my clock", "the
     word on my label") that the user never stated cannot come from the web or an advice template.
  2. Something the user told: a question about a thing the user mentioned earlier in the chat (where it is, its colour,
     when it is) needs an answer from the conversation, not a quoted thread.
  3. A count: "how many X" needs a reply that states a number of X.
No model is involved.
"""
import re

LOOKED_UP = re.compile(r'^chat/(?:web-single|web-checked|web-closest|core-open|core-knowledge|open-retrieval|corpus|local-|threads|'
                       r'web-evidence|advice|counsel|plus-talk|context-memory|talk-|core-talk|smalltalk-(?!joke))|^chat/team-last-resort')
OWN_THING = re.compile(r"(?i)\b(?:what(?:'s| is| was)|tell me|read me)\s+(?:the|my)\s+([a-z]+(?: [a-z]+){0,2}?)\s+(?:on|of|in|inside|from)\s+"
                       r"(?:the (?:back|front|side|bottom|top|base|label) of\s+)?(?:my|our)\s+([a-z]+(?: [a-z]+){0,2})\b")
OWN_HIDDEN = re.compile(r"(?i)\b(?:serial|model|part|product|code|password|pin|number|word|name|text|writing|message|price|date|barcode|"
                        r"reading|colour|color|size|label|setting)\b")
ASKED = [
    (re.compile(r"(?i)^\s*(?:so\s+|and\s+|ok\s+)?where\s+(?!(?:did|do|have|had)\s+(?:i|we)\b)(?:is|are|was|were|did|do|does|has|have)\s+(?:the\s+|my\s+|our\s+|that\s+)?([a-z][a-z' -]{1,40}?)"
                r"(?:\s+(?:go|gone|end up|now|kept|left|put))?\s*\?\s*$"), 'where it is'),
    (re.compile(r"(?i)^\s*(?:so\s+|and\s+)?what (?:colou?r) (?:is|are|was|were) (?:the\s+|my\s+|our\s+)?([a-z][a-z' -]{1,40}?)\s*\?\s*$"), 'its colour'),
    (re.compile(r"(?i)^\s*(?:so\s+|and\s+)?when (?:is|are|was|were|does|do) (?:the\s+|my\s+|our\s+)?([a-z][a-z' -]{1,40}?)(?:\s+\w+)?\s*\?\s*$"), 'when it is'),
]
NEVER_TOLD = re.compile(r"(?i)^\s*(?:so\s+|and\s+|hey,?\s+|ok,?\s+)?(?P<ask>when|where|what colou?r|how old|what)(?:\s+(?:is|are|was|were)|'s)\s+"
                        r"(?:my|our)\s+(?P<thing>[a-z]+(?:'s)?(?:\s+[a-z]+){0,2}?)(?:\s+(?:now|today|again|called|named))?\s*\?\s*$")
MIND = re.compile(r"(?i)\b(?:what|which)\s+(?:[a-z]+\s+){0,2}?"
                  r"am\s+i\s+(?:thinking|imagining|picturing|holding|wearing|eating|drinking|looking at|hiding|carrying|pointing at|listening to)\b|"
                  r"\bread my mind\b|\bguess what i(?:'m| am) (?:thinking|holding|hiding)\b")
DID_I = re.compile(r"(?i)^\s*(?:so\s+|and\s+|hey,?\s+)?(?P<ask>where|what|when|who|which|how many|how much|why)\s+(?P<skip>\w+\s+)?did\s+(?:i|we)\s+"
                   r"(?P<verb>[a-z]+)\s*(?P<rest>[^?]*)\?\s*$")
DID_MY = re.compile(r"(?i)^\s*(?:so\s+|and\s+|hey,?\s+)?(?:what time|when|where|why|how long|how late|how much|what)\s+(?:\w+\s+)?"
                    r"(?:did|does|was|were)\s+(?:my|our)\s+(?P<thing>[a-z]+(?:\s+[a-z]+)?)\s+(?:leave|arrive|start|finish|end|land|cost|go|come|"
                    r"open|close|happen|take|break|stop|get|run|depart)\b[^?]*\?\s*$")
FUTURE = re.compile(r"(?i)\b(?:lottery|lotto|winning|jackpot)\s+numbers?\b.*\b(?:will|next|tomorrow|tonight|this week|be)\b|"
                    r"\bwhat\s+will\s+(?:the\s+)?(?:lottery|lotto)\b|\bwhich (?:number|side) will (?:the )?(?:dice|die|coin|roulette)\b|"
                    r"\bwill (?:the )?(?:coin|dice|die) (?:land|come up|show)\b|\bwhat will i roll\b|"
                    r"\bwho will win (?:the )?(?:lottery|next (?:lottery|draw|raffle))\b")
STOP = {'the', 'a', 'an', 'my', 'our', 'this', 'that', 'today', 'yesterday', 'morning', 'evening', 'night', 'tonight', 'week', 'last', 'at',
        'in', 'on', 'for', 'to', 'of', 'with', 'it', 'me', 'up', 'out'}
COUNT = re.compile(r"(?i)\bhow many ([a-z]+)\b")
NUMBER_WORDS = r'(?:\d+(?:[.,]\d+)?|zero|no|none|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|' \
               r'sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|dozen)'
PRONOUN = {'it', 'they', 'them', 'he', 'she', 'this', 'that', 'these', 'those'}


def stem(w):
    w = w.lower()
    for end in ('ies', 'ied', 'ing', 'ed', 'es', 's'):
        if w.endswith(end) and len(w) - len(end) >= 3:
            return w[:-len(end)] + ('y' if end in ('ies', 'ied') else '')
    return w


def told(messages):
    """Statements the user made (not questions), oldest first, including the parts of the last message before its question."""
    users = [m.get('content') or '' for m in messages if m.get('role') == 'user']
    out = []
    for i, text in enumerate(users):
        for s in re.split(r'(?<=[.!?])\s+|\n+', text):
            s = s.strip()
            if s and not s.endswith('?'):
                out.append(s)
    return out


def missing(draft, text, why):
    return dict(route='chat/evidence-missing', sources=[], response=text, replaced_route=draft.get('route'),
                details='The looked-up reply did not supply what was asked (' + why + '; evidence.py).')


def check(messages, draft):
    """The draft, or an honest reply naming the missing fact."""
    if not isinstance(draft, dict):
        return draft
    users = [m.get('content') or '' for m in messages if m.get('role') == 'user']
    if not users:
        return draft
    last = users[-1].strip()
    asks = [s.strip() for s in re.split(r'(?<=[.!?])\s+', last) if s.strip().endswith('?')]
    if not asks:
        return draft
    question = asks[-1]
    reply = str(draft.get('response') or '')
    statements = told(messages)
    said = {stem(w) for s in statements for w in re.findall(r"[a-z]+", s.lower())}
    in_reply = {stem(w) for w in re.findall(r"[a-z]+", reply.lower()[:400])}

    # Rules that hold whichever desk drafted the reply: only the user can know these, and the draft is not about them.
    if MIND.search(question):
        return missing(draft, "I can't see or hear you, and nothing in our chat tells me, so I don't know. Tell me and I'll work with it.",
                       'a question about what the user is thinking')
    did = DID_I.match(question)
    if did:
        heads = {stem(w) for w in re.findall(r"[a-z]+", (did['rest'] + ' ' + (did['skip'] or '')).lower())
                 if w not in STOP and w not in ('time', 'day', 'total', 'all', 'much', 'many', 'kind', 'sort', 'type')} | {stem(did['verb'].lower())}
        objects = heads - {stem(did['verb'].lower())}
        # "What time did I wake up this morning?": nothing but the verb to go on; the verb itself must have been told
        about = objects or {stem(did['verb'].lower())}
        if (about and not about & said) and not (about & in_reply and not LOOKED_UP.search(str(draft.get('route') or ''))):
            return missing(draft, "You haven't told me that, so I don't know, and it isn't something I can look up. "
                                  "If you tell me, I'll remember it for the rest of this chat.",
                           'a question about something the user did that they never mentioned')
    mine = NEVER_TOLD.match(question)
    if mine:
        thing = re.sub(r"\s+", ' ', mine['thing']).strip()
        heads = {stem(w) for w in re.findall(r"[a-z]+", thing.lower()) if w not in ('s', 'the', 'my', 'our')}
        looked_up = LOOKED_UP.search(str(draft.get('route') or ''))
        if heads and not heads & said and (looked_up or not heads & in_reply):
            ask = {'when': 'when', 'where': 'where', 'what colour': 'the colour of', 'what color': 'the colour of',
                   'how old': 'how old', 'what': 'what'}.get(mine['ask'].lower(), 'about')
            verb = 'are' if thing.endswith('s') and not thing.endswith(("'s", 'ss')) else 'is'
            return missing(draft, f"You haven't told me {ask} your {thing} {verb if ask in ('when', 'where', 'how old', 'what') else ''}".rstrip()
                           + " yet, so I don't know. If you tell me, I'll remember it for the rest of this chat.",
                           'a question about the user\'s own life that they never mentioned')

    # "What time did my train leave yesterday?": an event in the user's own life that they never mentioned
    event = DID_MY.match(question)
    if event:
        heads = {stem(w) for w in re.findall(r"[a-z]+", event['thing'].lower()) if w not in STOP}
        looked_up = LOOKED_UP.search(str(draft.get('route') or ''))
        if heads and not heads & said and (looked_up or not heads & in_reply):
            return missing(draft, f"You haven't told me about your {event['thing'].strip()}, so I don't know, and it isn't something I can look up. "
                                  "If you tell me, I'll remember it for the rest of this chat.",
                           'a question about an event in the user\'s life that they never mentioned')

    # "Neighbour A: ... Neighbour B: ... When did it come?": the answer is in the accounts the user gave, never on a web page
    try:
        from . import swarm
        labels = {swarm.label_key(n) for n, _ in swarm.segments(last)}
    except Exception:
        labels = set()
    if len(labels) >= 2 and re.search(r'^chat/(?:web-|core-|advice|counsel|threads|corpus|local-|open-retrieval)|team-last-resort', str(draft.get('route') or '')):
        return missing(draft, "The answer has to come from the accounts you gave me, and I couldn't read them well enough to compare them. "
                              "Could you say what each one claims in a short sentence (for example \"Witness 1: the van was white\")?",
                       'a question about the accounts the user gave, answered from a looked-up page')

    if not LOOKED_UP.search(str(draft.get('route') or '')):
        return draft                        # the remaining checks are only for looked-up passages and advice

    # a chance outcome that has not happened yet: no page can know it
    if FUTURE.search(question):
        return missing(draft, "Nobody can know that in advance: it's down to chance, so any answer would be a guess. "
                              "If it's a draw or a game, the result is only known once it has happened.",
                       'a chance outcome in the future')

    # 1. a property of the user's own object, never stated
    own = OWN_THING.search(question)
    if own and OWN_HIDDEN.search(own[1]):
        thing = own[2]
        stated = any(re.search(r'(?i)\b' + re.escape(thing.split()[-1]) + r'\b', s) and re.search(r'(?i)\b' + re.escape(own[1].split()[-1]) + r'\b', s)
                     for s in statements)
        if not stated:
            return missing(draft, f"I can't see your {thing}, so I don't know the {own[1]} on it, and it isn't something I can look up. "
                                  f"If you read it out to me, I can help with what it means or what to do with it.", 'a property only the user can see')

    # 2. a thing the user told about earlier: the answer must come from what they said
    for pattern, what in ASKED:
        m = pattern.match(question)
        if not m:
            continue
        subject = m[1].strip()
        head = [w for w in re.findall(r"[a-z']+", subject.lower()) if w not in ('the', 'my', 'our', 'a', 'an')]
        if not head:
            break
        if head[-1] in PRONOUN and statements:
            # "it" is the thing a statement was about: the subject at the start of a sentence ("My radio was in the den.")
            subjects = [re.match(r'(?i)\s*(?:the|my|our)\s+(?:[a-z]+\s+)?([a-z]+)\s+(?:is|are|was|were|has|have)\b', s) for s in statements]
            subjects = [m[1].lower() for m in subjects if m]
            if not subjects:
                break
            head = [subjects[-1]]
        key = stem(head[-1])
        mentioned = [s for s in statements if key in {stem(w) for w in re.findall(r"[a-z]+", s.lower())}]
        if not mentioned:
            break
        from_memory = str(draft.get('route')).startswith('chat/context-memory') and \
            key in {stem(w) for w in re.findall(r"[a-z]+", reply.lower()[:300])}
        if not from_memory:                 # a quoted thread or an advice template cannot know where the user's keys are
            thing = ' '.join(head)
            if thing.endswith('s') and not thing.endswith('ss'):
                what = what.replace('it is', 'they are').replace('its ', 'their ')
            return missing(draft, f"You mentioned the {thing}, but from what you've told me I can't work out {what}. "
                                  f"What I have is: \"{mentioned[-1].rstrip('.!')}\". Could you tell me a bit more?",
                           'a question about something the user told')
        break

    # 3. a count needs a number of the counted thing
    c = COUNT.search(question)
    if c and not re.search(r'(?i)\b(?:my|our|i|we)\b', question):
        noun = stem(c[1])
        near = re.search(r'(?i)\b' + NUMBER_WORDS + r'(?:[\s-]+[a-z-]+){0,2}?[\s-]+(' + re.escape(c[1][:max(3, len(noun) - 1)]) + r'[a-z]*)', reply[:600]) \
            or re.search(r'(?i)\b' + NUMBER_WORDS + r'-' + re.escape(noun[:4]), reply[:600])
        if not near:
            subject = re.sub(r'(?i)^.*?\bhow many [a-z]+\s+(?:does|do|did|are there in|are in|is in|has|have)?\s*', '', question).rstrip('?').strip()
            subject = re.sub(r'(?i)\s+(?:have|has|got|contain|contains)$', '', subject)
            return missing(draft, f"I couldn't find a source that states how many {c[1]} {subject} {'has' if subject else 'there are'}, "
                                  "so I'd rather not guess.".replace('  ', ' '), 'a count with no number of the counted thing')
    return draft
