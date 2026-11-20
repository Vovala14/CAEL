"""'I parked on level 3.' + 'Where did I park?' -> On level 3 (0.4.4).

A question about something the user did, answered only from a sentence in which the user said they did it. The verb
must match (past forms of common verbs are listed), and the reply quotes the user's own words, so nothing is invented.
When no such sentence exists, this desk stays silent and the evidence check says the user never mentioned it.
No model is involved.
"""
import re

ASK = re.compile(r"(?i)^\s*(?:so\s+|and\s+|hey,?\s+|ok,?\s+)?(?P<ask>where|when|what time|what day|what|who|which \w+|how much|how many \w+)\s+"
                 r"did\s+(?P<who>i|we)\s+(?P<verb>[a-z]+)(?P<rest>[^?]*)\?\s*$")
PAST = {'leave': 'left', 'put': 'put', 'meet': 'met', 'go': 'went', 'buy': 'bought', 'eat': 'ate', 'see': 'saw', 'have': 'had',
        'sleep': 'slept', 'get': 'got', 'lose': 'lost', 'find': 'found', 'hide': 'hid', 'keep': 'kept', 'pay': 'paid', 'sit': 'sat',
        'read': 'read', 'write': 'wrote', 'drive': 'drove', 'ride': 'rode', 'take': 'took', 'give': 'gave', 'send': 'sent',
        'spend': 'spent', 'wake': 'woke', 'hang': 'hung', 'lend': 'lent', 'drink': 'drank', 'fly': 'flew', 'swim': 'swam',
        'run': 'ran', 'sell': 'sold', 'tell': 'told', 'think': 'thought', 'bring': 'brought', 'catch': 'caught', 'win': 'won',
        'make': 'made', 'do': 'did', 'come': 'came', 'stand': 'stood', 'set': 'set', 'store': 'stored', 'say': 'said'}
PLACE = re.compile(r"(?i)\b((?:on|in|at|by|under|underneath|near|behind|beside|next to|outside|inside|on top of|in front of|into|onto)\s+"
                   r"[^,.;!?]+)")
WHEN = re.compile(r"(?i)\b((?:at|on|around|about|by|before|after)\s+(?:\d{1,2}(?::\d\d)?\s*(?:am|pm)?|noon|midnight|(?:mon|tues|wednes|thurs|"
                  r"fri|satur|sun)day\b[^,.;!?]*|the\s+\w+)|(?:yesterday|last night|this morning|today|last week)\b[^,.;!?]*)")


def past(verb):
    v = verb.lower()
    if v in PAST:
        return {PAST[v]}
    forms = {v + 'ed', v + 'd'}
    if v.endswith('y') and len(v) > 2 and v[-2] not in 'aeiou':
        forms.add(v[:-1] + 'ied')
    if re.search(r'[^aeiou][aeiou][bdgklmnprt]$', v):
        forms.add(v + v[-1] + 'ed')
    return forms


def respond(messages):
    users = [m.get('content') or '' for m in messages if m.get('role') == 'user']
    if len(users) < 2:
        return None
    q = ASK.match(users[-1].strip())
    if not q:
        return None
    forms = past(q['verb'])
    subject = r'(?:i|we)' if q['who'].lower() == 'i' else r'we'
    rest = [w for w in re.findall(r'[a-z]+', q['rest'].lower()) if w not in ('the', 'a', 'an', 'my', 'our', 'it', 'them', 'up', 'last', 'yesterday', 'today')]
    for text in reversed(users[:-1]):
        for s in reversed([x.strip() for x in re.split(r'(?<=[.!?])\s+', text) if x.strip() and not x.strip().endswith('?')]):
            m = re.search(r'(?i)\b' + subject + r'\s+(?:just\s+|already\s+|then\s+|also\s+)?(' + '|'.join(map(re.escape, forms)) + r')\b(.*)$', s)
            if not m:
                continue
            after = m[2].strip().rstrip('.!')
            if rest and not all(re.search(r'(?i)\b' + re.escape(w[:max(3, len(w) - 1)]), after) for w in rest):
                continue
            ask = q['ask'].lower()
            part = None
            if ask == 'where':
                p = PLACE.search(after)
                part = p[1].strip() if p else None
            elif ask in ('when', 'what time', 'what day'):
                p = WHEN.search(after)
                part = p[1].strip() if p else None
            if part is None and ask in ('where', 'when', 'what time', 'what day'):
                return None
            said = s.rstrip('.!')
            if part:
                return dict(route='chat/recall-did', sources=[], reasoning=True,
                            response=f'**{part[:1].upper() + part[1:]}**, as you told me ("{said}").',
                            details='The user said they did this; the answer is their own words (recall_did.py).')
            return dict(route='chat/recall-did', sources=[], reasoning=True, response=f'You told me: "{said}."',
                        details='The user said they did this; the answer is their own words (recall_did.py).')
    return None
