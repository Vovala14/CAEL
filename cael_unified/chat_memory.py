"""Long-chat memory and a consistent persona: answer from what was said in this conversation.

Non-neural. Every request carries the whole conversation; this module re-reads it on each turn:

1. Recall ("do you remember my cat's name?", "what did I study?", "where am I hiking?", "summarise what you know about
   me"): the user's own earlier statements are the only evidence. Common slots get a direct answer (name, named pets
   and family, job, where they live: the latest statement wins, so "I moved to Lyon" updates it). Anything else is
   answered with the user's best-matching earlier sentence, turned to "you" form ("You said your tomato leaves are
   turning yellow, and you think you've been overwatering them."). Nothing matching: an honest "you haven't told me".
   A pronoun question whose answer only the user's words hold ("What role is it for?" after "It's for a data analyst
   role at a bank") is answered the same way.
2. Persona: CAEL's own preferences ("what's your favourite sci-fi book?", "do you like science fiction?") come from a
   fixed list, and anything CAEL already said in this conversation is repeated, never contradicted.
3. Talk: when the user tells CAEL something and the reply from the other routes is generic or off the point, the reply
   is rebuilt from what they said (a move, a job, a pet, family visiting, something watched or read, a trip), with
   a one-line fact about a named film, book or place from Wikipedia's short description when the web is reachable.

Assistant statements are never evidence about the user; quoted or hypothetical text is not biography.
"""
import re

from .chat_core import you

STOP = set('''a an the and or but if of to in on at for with from by about as is are was were be been being am do does did
have has had i me my mine we us our you your he him his she her it its they them their this that these those what which who
whom whose why how when where can could should would will just really also too so very again now then still ever any some
say said tell told mention mentioned remember remind recall know name names called please ok okay well yes no not there
here thing things one ones like get got back earlier before already'''.split())
REL = r'(?:cat|dog|puppy|kitten|pet|rabbit|hamster|parrot|bird|fish|horse|sister|brother|mum|mom|mother|dad|father|wife|husband|' \
      r'partner|girlfriend|boyfriend|friend|best friend|son|daughter|boss|colleague|coworker|roommate|flatmate|neighbour|neighbor|' \
      r'grandma|grandmother|grandpa|grandfather|aunt|uncle|cousin|baby|kid|child|teacher|manager)'
NAME = r"([A-Z][a-zà-ÿ'-]+(?: [A-Z][a-zà-ÿ'-]+)?)"
NOT_NAMES = {'I', 'The', 'A', 'An', 'It', 'This', 'That', 'My', 'And', 'But', 'So', 'Yes', 'No', 'Hi', 'Hey', 'Hello', 'Thanks', 'Actually',
             'Anyway', 'Well', 'Oh', 'Ok', 'Okay', 'Cool', 'Great', 'Sorry', 'Just', 'Really', 'Not', 'Very', 'Here', 'There'}


def user_messages(messages):
    return [(i, m['content']) for i, m in enumerate(messages) if m.get('role') == 'user' and isinstance(m.get('content'), str)]


def statements(messages, include_last=False):
    """(message index, sentence) for every sentence the user stated (not asked) before the last turn."""
    out = []
    turns = user_messages(messages)
    for i, text in (turns if include_last else turns[:-1]):
        for s in re.split(r'(?<=[.!?])\s+', text.strip()):
            s = s.strip()
            if s and not s.endswith('?') and len(s.split()) >= 2 and not re.search(r'(?i)\b(?:if i|suppose|imagine|pretend|hypothetically)\b|["“”]', s):
                out.append((i, s))
    return out


def stem(w):
    from .web_check import stem as s
    return s(w)


def words(text):
    from .web_check import plain
    return [w for w in re.findall(r"[a-z][a-z'-]*", plain(text).lower().replace('’', "'")) if w not in STOP and len(w) > 1]


def weight(w):
    from .web_check import weight as wt
    return wt(w)


# ----------------------------------------------------------------------------------------------- the profile

def profile(messages, include_last=False):
    """Slots read from the user's statements; later statements replace earlier ones."""
    p = {'name': None, 'live': None, 'job': None, 'named': {}, 'favourite': {}, 'from': None}
    for i, s in statements(messages, include_last):
        m = re.search(r"(?i)\b(?:my name is|i'm called|i am called|call me)\s+(?-i:" + NAME + ")", s) or \
            re.search(r"^(?:hi|hey|hello)?[!,. ]*(?:i'm|i am)\s+(?-i:([A-Z][a-z'-]+))[.!]*$", s, re.I)
        if m and m[1] not in NOT_NAMES:
            p['name'] = m[1]
        m = re.search(r"(?i)\bi(?:'ve| have)? (?:just |recently )?(?:moved|relocated) to (?-i:" + NAME + r")", s) or \
            re.search(r"(?i)\bi (?:now |currently )?live in (?:a \w+ in )?(?-i:" + NAME + r")", s) or \
            re.search(r"(?i)\bi(?:'m| am) (?:now )?(?:living|based) in (?-i:" + NAME + r")", s)
        if m:
            p['live'] = m[1]
        m = re.search(r"(?i)\bi(?:'m| am) (?:originally )?from (?-i:" + NAME + r")", s)
        if m:
            p['from'] = m[1]
        m = re.search(r"(?i)\bi work as (an? [\w' -]+?)(?=[.,!;]|$| and | but )", s) or \
            re.search(r"(?i)\bi(?:'m| am) (an? (?:\w+ ){0,2}(?:nurse|doctor|teacher|engineer|developer|programmer|designer|student|"
                      r"lawyer|accountant|chef|cook|writer|artist|manager|analyst|scientist|researcher|driver|electrician|plumber|"
                      r"mechanic|pharmacist|dentist|vet|architect|consultant|journalist|photographer|musician|baker|barista|"
                      r"cashier|librarian|carpenter|farmer|pilot|firefighter|police officer|officer|therapist|psychologist|"
                      r"translator|programmer|intern|freelancer|waiter|waitress|clerk|technician|soldier|professor|tutor)"
                      r"(?: (?:at|in|for|with) [\w' -]+?)?)(?=[.,!;]|$| and | but )", s) or \
            re.search(r"(?i)\bmy job is (?:as )?(an? [\w' -]+?)(?=[.,!;]|$)", s)
        if m:
            p['job'] = m[1]
        for m in re.finditer(r"(?i)\b(?:my|a|an|our) (?:little |new |old |pet |younger |older |big |baby )?(" + REL + r")(?:,)? (?:is )?(?:called|named) (?-i:" + NAME + r")", s):
            p['named'][m[1].lower()] = m[2]
        for m in re.finditer(r"(?i)\b(?:a|an|my|our) (?:puppy|dog|kitten|cat),? (?:a |an )?(?:[\w-]+ ){1,2}(?:called|named) (?-i:" + NAME + r")", s):
            p['named'][re.search(r'(?i)puppy|dog|kitten|cat', m[0])[0].lower()] = m[1]
        for m in re.finditer(r"(?i)\bmy (?:little |younger |older |big |baby |best )?(" + REL + r"),? (?-i:" + NAME + r")\b", s):
            if m[2].split()[0] not in NOT_NAMES and not re.match(r"(?i)(?:is|was|and|has|had|who|will)$", m[2].split()[0]):
                p['named'][m[1].lower()] = m[2].split()[0] if m[2].split()[-1].lower() in ('is', 'was') else m[2]
        for m in re.finditer(r"(?-i:" + NAME + r") is my (?:little |younger |older |big |best )?(" + REL + r")\b", s, re.I):
            if m[1] not in NOT_NAMES:
                p['named'][m[2].lower()] = m[1]
        for m in re.finditer(r"(?i)\bmy (?:all-time )?favou?rite(?: ([\w -]+?))? (?:is|are|was|would be) ([^.,!;]+)", s):
            p['favourite'][(m[1] or 'thing').strip().lower()] = m[2].strip()
    return p


# ----------------------------------------------------------------------------------------------- 1. recall

RECALL = re.compile(r"(?i)\b(?:do|did) you (?:still )?remember\b|\bremind me\b|\bwhat (?:did|do) i (?:say|tell|mention)\b|"
                    r"\bwhat (?:did|have) i (?:just )?(?:told|said|mentioned)\b|\b(?:what|which|where|when|who|how)\b[^?]{0,40}\bdid i (?:say|tell|mention)\b|"
                    r"\bwhat(?:'s| is| was| were| are) (?:the name of )?my\b|\bwhat do i do (?:for (?:work|a living)|for my job)\b|"
                    r"\bwhere (?:am i|do i) (?:living|live|staying|from|hiking|going|work|working|based|travel+ing|moving)\b|"
                    r"\b(?:what|which) (?!should|can|could|would)\w+(?: \w+)? did i\b|\bwhat did i (?:study|watch|read|buy|have|eat|make|see|do)\b|"
                    r"\b(?:summari[sz]e|recap)\b.*\b(?:me|so far|i (?:told|said))\b|\bwhat (?:do|did) you know about me\b|\bwhat have i told you\b|"
                    r"\bwho (?:is|was) my\b|\bwhat(?:'s| is) my name\b|\bwhere (?:am i|i am) (?:now|from)\b|"
                    r"\bi (?:said|told you|mentioned) (?:i'?m|i was|i am|i have|i had|that|my)\b")
NOT_RECALL = re.compile(r"(?i)\bwhat (?:should|can|could|would) i\b|\bhow (?:do|can|should) i\b|\bwhat do i need\b|\bwhat am i doing wrong\b")


def turned(s):
    s = re.sub(r'^(?:(?:so|well|anyway|actually|also|and|but|oh|ok|okay|yeah|by the way|not much|nothing much|hey|hi|hmm|um|cool|good|great|'
               r'just so you know|just to let you know|fyi|honestly|to be honest|quick update|update|oh and|and also|for the record|'
               r'in case you need it|guess what|funny thing)[,.:!— -]+)+', '', s.strip(), flags=re.I)
    if re.match(r"(?i)(?:just|finished|been|got|going|started|watching|reading|thinking)\b", s):
        s = 'I ' + s            # "just finished watching Oppenheimer" -> "you just finished watching Oppenheimer"
    s = you(s).rstrip(' .!')
    return s[0].lower() + s[1:] if s and not re.match(r"[A-Z][a-z]+ [A-Z]|I\b|[A-Z]{2}", s) else s


def is_recall(q):
    return bool(RECALL.search(q)) and not NOT_RECALL.search(q)


def multi_part(q):
    return q.count('?') > 1 or bool(re.search(r"(?i)[,;]?\s\b(?:and|also|plus|but)\b,?\s+(?:also\s+)?(?:what|where|when|who|which|how|do|does|did|"
                                             r"is|are|can|could|will|would|should|have|has)\b", q))


def recall(messages, late=False):
    """Early (before other routes): direct answers about the profile. Late (after them): the best-matching thing the
    user said, used only when CAEL's own memory routes did not answer."""
    turns = user_messages(messages)
    if not turns:
        return None
    q = turns[-1][1].strip()
    low = q.lower()
    if not late and multi_part(q):
        return None             # "What's my name, and do you know what colour I want?": the main routes answer every part
    if not is_recall(q):
        return None if late else pronoun_recall(messages)
    p = profile(messages)
    said = statements(messages)
    if re.search(r'\b(?:summari[sz]e|recap|what (?:do|did) you know about me|what have i told you)\b', low):
        return summary(p, said)
    m = re.search(r'\b(?:my )?(' + REL + r")(?:'s)? name\b|\bname of my (" + REL + r')\b|\bwho (?:is|was) my (' + REL + r')\b', low)
    if m:
        rel = next(g for g in m.groups() if g)
        if rel in p['named']:
            return reply(f"Yes, your {rel} is called {p['named'][rel]}." if 'remember' in low else f"Your {rel} is called {p['named'][rel]}.", 'name')
        if not late:
            return None         # the main routes give their own "you didn't mention it" answer
        return reply(f"I don't think you've told me your {rel}'s name in this chat. What is it?", 'unknown')
    if re.search(r"\bwhat(?:'s| is) my name\b|\bwho am i\b|\bremember my name\b", low):
        if p['name']:
            return reply(f"You're {p['name']}.", 'name')
        if not late:
            return None
        return reply("You haven't told me your name in this chat. What should I call you?", 'name')
    if re.search(r'\b(?:work|job|living|profession|occupation)\b', low) and re.search(r'\bwhat\b', low) and p['job']:
        return reply(f"You told me you're {you(p['job'])}.", 'job')
    if re.search(r'\bwhere\b.*\b(?:live|living|staying|based|moved|move)\b|\bwhere am i (?:now|living)\b', low) and p['live']:
        return reply(f"You live in {p['live']}." + (f" (You're originally from {p['from']}.)" if p['from'] else ''), 'live')
    if re.search(r'\bwhere\b.*\bfrom\b', low) and p['from']:
        return reply(f"You're from {p['from']}.", 'from')
    m = re.search(r'\bfavou?rite(?: ([\w -]+?))?\b(?:\?|$| again)', low)
    if m and p['favourite']:
        want = (m[1] or '').strip()
        for thing, value in p['favourite'].items():
            if not want or thing == 'thing' or set(want.split()) & set(thing.split()):
                return reply(f"You said your favourite{' ' + thing if thing != 'thing' else ''} is {value}.", 'favourite')
    if not late:
        return None
    best = matches(q, said)
    if best:
        return reply('You said ' + ', and '.join(turned(s) for s in best) + '.', 'said')
    return reply("I don't think you've told me that in this chat, or I missed it. Could you remind me?", 'unknown')


CATEGORY = {
    'month': r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b',
    'day': r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|tonight|weekend)\b',
    'when': r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|tonight|weekend|morning|afternoon|evening|'
            r'nights?|evenings?|mornings?|afternoons?|weekends?|january|february|march|april|may|june|july|august|september|october|november|december|next (?:week|month|year)|'
            r'\d{1,2}(?::\d\d)? ?(?:am|pm)|in \d+ (?:days|weeks))',
    'time': r'\b(?:mornings?|afternoons?|evenings?|nights?|weekends?|lunch(?:time)?|before work|after work)\b',
    'diet': r'\b(?:vegetarian|vegan|pescatarian|gluten[- ]free|dairy[- ]free|halal|kosher|keto|paleo|allergic)\b',
    'flavour': r'\b(?:lemon|chocolate|vanilla|strawberry|mint|coffee|caramel|orange|lime|raspberry|cinnamon|spicy|sweet)\b',
    'flavor': r'\b(?:lemon|chocolate|vanilla|strawberry|mint|coffee|caramel|orange|lime|raspberry|cinnamon|spicy|sweet)\b',
    'breed': r'\b(?:collie|retriever|labrador|terrier|spaniel|poodle|beagle|bulldog|shepherd|husky|dachshund|pug|chihuahua|boxer|'
             r'corgi|doodle|rottweiler|greyhound|whippet|schnauzer|siamese|persian|tabby|maine coon|ragdoll|sphynx|mixed breed)\b',
    'colour': r'\b(?:red|blue|green|yellow|black|white|grey|gray|brown|pink|purple|orange|ginger)\b',
    'age': r'\b(?:\d{1,3}|(?:twenty|thirty|forty|fifty|sixty|seventy)(?:-\w+)?)(?: years? old)?\b',
    'budget': r'(?:[$£€]\s?\d|\b\d[\d,.]* ?(?:dollars|pounds|euros|usd|gbp|eur|k)\b)',
    'job': r'\b(?:work|job|nurse|teacher|accountant|engineer|developer|student|doctor|analyst|manager|designer|chef)\b',
}
WHO_ANSWER = r"\b(?:my|our) (?:" + REL + r")\b|\b[A-Z][a-z]+\b(?<!\bI)"


def category_hits(question, sentence):
    """Category words in the question ("month", "diet") that the sentence answers ("April", "vegetarian")."""
    asked = {w for w in words(question)}
    return {c for c, pattern in CATEGORY.items() if c in asked and re.search(pattern, sentence, re.I)}


def situation_recall(messages):
    """'Who works night shifts?', 'When is the anniversary dinner?', 'What flavour does my mum like?': questions whose
    answer is in what the user told CAEL, without saying "did I say". The user's sentence must cover most of the
    question's words (or answer its category word) and give the kind of answer asked for: a person for "who", a time
    for "when". How / why / should questions, and anything the sentence does not answer, go on to the other routes."""
    q = user_messages(messages)[-1][1].strip()
    last = re.split(r'(?<=[.!])\s+', q)[-1]
    low = last.lower()
    if is_recall(q):
        return None             # "what did I say ..." questions go to CAEL's memory routes first, then to recall(late=True)
    if '?' not in last or len(last.split()) > 14 or not re.match(r"(?i)\s*(?:and |so |ok,? )?(?:who|when|where|what|which)\b", last) \
            or re.search(r"(?i)\b(?:should|could|would|best|good|recommend|usually|normally|typically|in general)\b", last):
        return None
    wh = re.match(r"(?i)\s*(?:and |so |ok,? )?(\w+)", last)[1].lower()
    asked = {stem(w): weight(w) for w in words(last) if w not in ('like', 'have', 'does', 'did', 'is', 'are')}
    if not asked:
        return None
    best = None
    for i, s in statements(messages):
        have = {stem(w) for w in words(s)}
        hits = category_hits(last, s)
        covered = sum(v for w, v in asked.items() if w in have or w in {stem(c) for c in hits})
        share = covered / sum(asked.values())
        if wh == 'who' and not re.search(WHO_ANSWER, s):
            continue
        if wh == 'when' and not re.search(CATEGORY['when'], s, re.I):
            continue
        if wh == 'where' and not re.search(r'\b(?:in|at|to|from) (?:the )?[A-Z][a-z]+', s):
            continue
        rare = any(w in have and v >= 7 for w, v in asked.items())       # "anniversary", "night shifts"
        mine = re.search(r"(?i)\b(?:i|my|me|we|our)\b", last)
        if (share >= 0.6 or (share >= 0.5 and (rare or hits)) or (hits and mine and share >= 0.15)) and (best is None or share > best[0]):
            best = (share, s)
    if not best:
        return None
    return reply('You said ' + turned(best[1]) + '.', 'situation')


def matches(question, said):
    """The user's earlier sentence(s) that best match the question's own words; a short follow-up sentence with a
    pronoun ("I think I've been overwatering them.") is kept with the sentence it continues."""
    asked = {stem(w): weight(w) for w in words(question) if w not in ('say', 'tell', 'want')}
    asked = {k: v for k, v in asked.items() if k not in {stem(x) for x in ('say', 'tell', 'mention', 'remember', 'remind', 'what', 'problem', 'thing')}}
    if not asked:
        return []
    scored = []
    for k, (i, s) in enumerate(said):
        have = {stem(w) for w in words(s)} | {stem(c) for c in category_hits(question, s)}
        score = sum(v for w, v in asked.items() if w in have)
        if score:
            scored.append((score, -k, k))
    if not scored:
        return []
    scored.sort(reverse=True)
    top = scored[0]
    if top[0] < 2.5:
        return []
    k = top[2]
    out = [said[k][1]]
    # "I think I've been overwatering them." right after "My tomato leaves are turning yellow." continues it; an
    # unrelated aside in a later message ("Honestly, I tried to draw a horse and it looked like a table.") does not.
    if k + 1 < len(said) and said[k][0] < said[k + 1][0] <= said[k][0] + 2 and \
            re.search(r"(?i)\b(?:them|they|those|these)\b|^(?:i think|maybe|probably)\b", said[k + 1][1]) and len(said[k + 1][1].split()) <= 10:
        out.append(said[k + 1][1])
    return out


def pronoun_recall(messages):
    """'What role is it for?' after 'It's for a data analyst role at a bank.': every content word of the question is
    in one earlier user statement, and no reply of CAEL's had it, so the user's own words are the answer."""
    q = user_messages(messages)[-1][1]
    if '?' not in q or not re.search(r"(?i)\b(?:it|this|that|they|them|she|he)\b", q) or len(q.split()) > 10:
        return None
    asked = [w for w in words(q) if weight(w) > 4.5]
    if not asked:
        return None
    for i, s in reversed(statements(messages)):
        have = {stem(w) for w in words(s)}
        if all(stem(w) in have for w in asked):
            return reply('You said ' + turned(s) + '.', 'said')
    return None


def summary(p, said):
    parts = []
    if p['name']:
        parts.append(f"your name is {p['name']}")
    if p['live']:
        parts.append(f"you live in {p['live']}")
    if p['from']:
        parts.append(f"you're from {p['from']}")
    if p['job']:
        parts.append(f"you're {you(p['job'])}")
    for rel, name in p['named'].items():
        parts.append(f"your {rel} is called {name}")
    for thing, value in p['favourite'].items():
        parts.append(f"your favourite{' ' + thing if thing != 'thing' else ''} is {value}")
    known = {stem(w) for w in words(' '.join(parts))}
    extra = []
    for _, s in said:
        t = turned(s)
        mine = {stem(w) for w in words(s)}
        if len(extra) < 4 and len(s.split()) >= 4 and len(mine & known) < max(1, len(mine) // 2) and \
                re.search(r"(?i)\b(?:i|my|i'm|i've)\b", s) and not re.search(r'(?i)^(?:thanks|ok|cool|good|great|yeah|sounds)', s):
            extra.append(t)
    if not parts and not extra:
        return reply("You haven't told me much about yourself yet in this chat. I'd like to hear, though!", 'summary')
    text = 'Here is what you have told me: ' + '; '.join(parts + extra) + '.'
    return reply(text[0] + text[1:], 'summary')


def reply(text, kind):
    return dict(route='chat/memory-recall-' + kind, response=text, sources=[],
                details="Answered from the user's own statements earlier in this conversation (chat_memory.py); nothing inferred.")


# ----------------------------------------------------------------------------------------------- 2. persona

PERSONA = {   # CAEL's fixed preferences: the same answer every time, in every conversation
    'sci-fi book': ('"Hyperion" by Dan Simmons', 'Hyperion (Simmons novel)'),
    'science fiction book': ('"Hyperion" by Dan Simmons', 'Hyperion (Simmons novel)'),
    'book': ('"The Hobbit"', 'The Hobbit'),
    'novel': ('"The Hobbit"', 'The Hobbit'),
    'sci-fi film': ('"Arrival"', 'Arrival (film)'), 'sci-fi movie': ('"Arrival"', 'Arrival (film)'),
    'film': ('"Spirited Away"', 'Spirited Away'), 'movie': ('"Spirited Away"', 'Spirited Away'),
    'tv show': ('"Planet Earth"', 'Planet Earth (2006 TV series)'), 'show': ('"Planet Earth"', 'Planet Earth (2006 TV series)'),
    'series': ('"Planet Earth"', 'Planet Earth (2006 TV series)'),
    'song': ('"Here Comes the Sun"', 'Here Comes the Sun'), 'band': ('the Beatles', 'The Beatles'),
    'music': ('jazz, especially Miles Davis', 'Miles Davis'), 'genre': ('science fiction', None),
    'food': ('a good homemade pizza', None), 'dessert': ('pastel de nata', 'Pastel de nata'), 'drink': ('a cup of tea', None),
    'colour': ('deep blue', None), 'color': ('deep blue', None), 'season': ('autumn', None),
    'animal': ('the octopus, because it is so clever', 'Octopus'), 'sport': ('football, to watch', None),
    'game': ('chess', 'Chess'), 'board game': ('chess', 'Chess'), 'video game': ('"Minecraft"', 'Minecraft'),
    'city': ('Lisbon', 'Lisbon'), 'place': ('the seaside', None), 'country': ('Japan', 'Japan'),
    'subject': ('astronomy', 'Astronomy'), 'planet': ('Saturn, for the rings', 'Saturn'), 'number': ('seven', None),
    'flower': ('sunflowers', None), 'author': ('Ursula K. Le Guin', 'Ursula K. Le Guin'), 'writer': ('Ursula K. Le Guin', 'Ursula K. Le Guin'),
    'hobby': ('chatting about books and science', None), 'word': ('"serendipity"', None),
}
LIKES = {   # "do you like X?": topics CAEL is fond of, and a reason
    'science fiction': 'I love the big "what if" ideas', 'sci-fi': 'I love the big "what if" ideas', 'books': 'they are my favourite thing to talk about',
    'reading': 'books are my favourite thing to talk about', 'music': 'especially jazz', 'movies': 'especially animated films and good science fiction',
    'films': 'especially animated films and good science fiction', 'cats': 'they are wonderfully independent', 'dogs': 'they are so loyal',
    'cooking': 'I love hearing recipes', 'travel': 'I love hearing about places', 'history': 'there is always a good story in it',
    'science': 'astronomy most of all', 'space': 'I could talk about Saturn all day', 'art': 'I like how many ways people see the world',
    'games': 'chess especially', 'chess': 'it is my favourite game', 'nature': 'I love documentaries like "Planet Earth"',
    'poetry': 'short poems especially', 'maths': 'puzzles especially', 'math': 'puzzles especially', 'football': 'mostly to watch',
}
FAVOURITE_Q = re.compile(r"(?i)\b(?:what(?:'s| is| was)|tell me|do you have) your (?:all-time )?favou?rite ([\w -]+?)(?: again)?\s*\??$|"
                         r"\bdo you have a favou?rite ([\w -]+?)\s*\??$|\bwhat (?:is|was) your favou?rite ([\w -]+?) again\b")
LIKE_Q = re.compile(r"(?i)^\s*(?:and |so |mind blown\. |wow\. )?do you (?:like|love|enjoy) ([\w -]+?)\s*\??$")
READ_Q = re.compile(r"(?i)\bhave you (?:ever )?(read|seen|watched|heard of|played|been to) ((?-i:[A-Z])[\w'’:-]*(?: (?:of |the |and |a )?(?-i:[A-Z0-9])[\w'’:-]*)*|it|that one)\b")


def persona(messages):
    q = user_messages(messages)[-1][1].strip() if user_messages(messages) else ''
    q_first = re.split(r'(?<=[.!])\s+', q)[-1]
    m = FAVOURITE_Q.search(q_first)
    if m:
        thing = next(g for g in m.groups() if g).strip().lower()
        thing = re.sub(r'^(?:kind of |type of |sort of )', '', thing)
        earlier = said_before(messages, thing)
        if earlier:
            return persona_reply(f"Still {earlier}! I wouldn't change my answer.", 'favourite')
        pick = PERSONA.get(thing) or PERSONA.get(thing.split()[-1]) or next((v for k, v in PERSONA.items() if k in thing), None)
        if pick:
            again = ' again' if re.search(r'(?i)\bagain\b', q) else ''
            return persona_reply(f"My favourite {thing}{again}? I'd say {pick[0]}. I can't experience it the way you do, but it's the one "
                                 f"I most like talking about. What's yours?", 'favourite', title=pick[1])
        return persona_reply(f"I don't have a favourite {thing} the way people do, but I'd love to hear yours. What is it?", 'favourite')
    m = LIKE_Q.search(q_first)
    if m:
        topic = m[1].strip().lower()
        why = LIKES.get(topic) or LIKES.get(topic.rstrip('s')) or LIKES.get(topic + 's')
        if why:
            return persona_reply(f"I do! I can't experience it the way you do, but {topic} is something I really enjoy talking about; {why}. "
                                 f"What about you?", 'like')
        return None
    m = READ_Q.search(q)
    if m:
        verb, title = m[1].lower(), m[2]
        if title.lower() in ('it', 'that one'):
            here = re.findall(r"(?:\bis|\bwas|\bcalled|\bread|\bwatched|\bsaw) ((?-i:[A-Z])[\w'’:-]*(?: (?-i:[A-Z])[\w'’:-]*)*)", q)
            title = here[-1] if here else (last_title(messages) or '')
        if not title:
            return None
        fact = describe(title, kind_word(verb))
        lead = {'read': "I can't read for fun the way you do, but I know it", 'seen': "I can't watch films, but I know it",
                'watched': "I can't watch films, but I know it", 'played': "I can't play games, but I know it",
                'heard of': 'Yes, I have heard of it', 'been to': "I can't travel, but I know about it"}[verb]
        lead = lead.replace(' it', ' ' + title, 1) if not fact else lead
        text = f"{lead}: {title} is {fact}." if fact else f"{lead} by name, though I can't say much more about it without looking it up."
        return persona_reply(text + ' What do you like about it?', 'have-you')
    return None


def said_before(messages, thing):
    """What CAEL already called its favourite <thing> in this conversation, if it did."""
    for m in reversed(messages[:-1]):
        if m.get('role') == 'assistant' and isinstance(m.get('content'), str):
            hit = re.search(r"(?i)my favourite " + re.escape(thing) + r"(?: again)?\? I'd say (.+?)\. ", m['content'])
            if hit:
                return hit[1]
    return None


def last_title(messages):
    for m in reversed(messages[:-1]):
        hit = re.findall(r'"([A-Z][^"]{1,60})"', m.get('content') or '')
        if hit:
            return hit[-1]
        hit = re.findall(r'\b(?:watching|watched|read|reading|finished) ((?-i:[A-Z])[\w’\']+(?: (?-i:[A-Z])[\w’\']+)*)', m.get('content') or '', re.I)
        if hit and m.get('role') == 'user':
            return hit[-1]
    return None


def persona_reply(text, kind, title=None):
    return dict(route='chat/persona-' + kind, response=text, sources=[], persona_title=title,
                details='CAEL persona (chat_memory.py): fixed preferences, repeated consistently; no claim of experience.')


def about(messages):
    """'What is it about?' when 'it' is a title CAEL or the user just named: the work's short description and lead."""
    q = user_messages(messages)[-1][1].strip() if user_messages(messages) else ''
    tell = re.search(r"(?i)(?:^|[.!?]\s+)(?:can you |could you |please )?tell me (?:a bit |a little |more )?about (?:the )?"
                     r"((?-i:[A-Z])[\w'’-]*(?: (?:of |the |de |da |do )?(?-i:[A-Z])[\w'’-]*)*)[.?!]*\s*$", q)
    if tell:
        title = tell[1]
        page = wiki_page(title)
        if not page or not page[2]:
            return None
        lead = ' '.join(re.split(r'(?<=[.!?])\s+', re.sub(r'\s*\([^()]*\)', '', page[2]).replace('  ', ' '))[:2])
        return dict(route='chat/web-about', response=f'{lead}\n\nSource: {page[0]} (Wikipedia).',
                    sources=[dict(source='Wikipedia', title=page[0], licence='CC BY-SA 4.0')],
                    details='Lead of the Wikipedia article on what the user asked about (chat_memory.py).')
    if not re.search(r"(?i)^\s*(?:i've never (?:read|seen|heard of) it\.?\s*)?(?:so,? )?what(?:'s| is) (?:it|that) about\??\s*$|"
                     r"\bwhat(?:'s| is) (?:it|that) about\??$", q):
        return None
    title = last_title(messages)
    if not title:
        return None
    lead = lead_text(title)
    if not lead:
        return None
    return dict(route='chat/web-about', response=f'{lead}\n\nSource: {lead_title(title)} (Wikipedia).', sources=[
        dict(source='Wikipedia', title=lead_title(title), licence='CC BY-SA 4.0')],
        details='Lead of the Wikipedia article on the title named just before (chat_memory.py).')


# ----------------------------------------------------------------------------------------------- web: short descriptions

_PAGES = {}


def wiki_page(name, kind=None):
    """(title, short description, lead) of the Wikipedia article for a name, preferring one whose description fits the
    kind ("film", "novel", "city"...). None when offline or nothing fits."""
    import os
    if os.environ.get('CAEL_WEB_SEARCH', '1') == '0':
        return None             # web lookups switched off (benchmarks)
    key = (name.lower(), kind)
    if key in _PAGES:
        return _PAGES[key]
    from .network import NETWORK, LookupUnavailable
    from urllib.parse import urlencode
    found = None
    try:
        q = name + (' ' + kind.split('|')[0] if kind else '')
        hits = NETWORK.json('https://en.wikipedia.org/w/api.php?' + urlencode(dict(action='query', list='search', srsearch=q, srlimit=4,
                                                                                    format='json')), ttl=86400, timeout=8)
        titles = [h['title'] for h in hits.get('query', {}).get('search', [])]
        from .web_check import plain
        titles.sort(key=lambda t: plain(re.sub(r'\s*\([^)]*\)', '', t)).lower() != plain(name).lower())
        if titles:
            data = NETWORK.json('https://en.wikipedia.org/w/api.php?' + urlencode(dict(action='query', prop='description|extracts', exintro=1,
                                explaintext=1, exsentences=3, redirects=1, titles='|'.join(titles[:4]), format='json')), ttl=86400, timeout=8)
            pages = {p.get('title'): p for p in data.get('query', {}).get('pages', {}).values()}
            first = {stem(w) for w in words(name)}
            for t in titles[:4]:
                page = pages.get(t) or {}
                desc = page.get('description') or ''
                if not desc or 'disambiguation' in desc.lower() or not first <= {stem(w) for w in words(t)}:
                    continue
                if kind and not re.search(r'(?i)\b(?:' + kind + r')\b', desc):
                    continue
                if re.search(r'(?i)\b(?:school|company|band|album|song|film|novel|footballer|politician)\b', desc) and kind and \
                        not re.search(r'(?i)\b(?:school|company|band|album|song|film|novel|footballer|politician)\b', kind):
                    continue        # a place question is not answered by a school district or a band of the same name
                found = (t, desc, (page.get('extract') or '').strip())
                break
    except (LookupUnavailable, KeyError, TypeError, ValueError):
        found = None
    _PAGES[key] = found
    return found


def kind_word(verb):
    return {'read': 'novel|book|series|manga|comic', 'seen': 'film|series|play|musical|show', 'watched': 'film|series|show|documentary',
            'played': 'game', 'heard of': None, 'been to': 'city|town|country|region|island|park|district|village|capital'}.get(verb)


def describe(name, kind=None):
    page = wiki_page(name, kind)
    if not page:
        return None
    desc = page[1]
    return ('an ' if desc[:1].lower() in 'aeiou' else 'a ') + desc[0].lower() + desc[1:] if not re.match(r'(?i)(?:a|an|the)\b', desc) \
        and re.match(r'[a-z0-9]', desc) else desc


def lead_title(name):
    page = wiki_page(name, 'novel|book|film|series|game') or wiki_page(name)
    return page[0] if page else name


def lead_text(name):
    page = wiki_page(name, 'novel|book|film|series|game') or wiki_page(name)
    if not page or not page[2]:
        return None
    lead = re.sub(r'\s*\([^()]*\)', '', page[2]).replace('  ', ' ')
    return ' '.join(re.split(r'(?<=[.!?])\s+', lead)[:2])


# ----------------------------------------------------------------------------------------------- 3. talk

GENERIC_REPLY = re.compile(r"(?i)^\s*(?:interesting!|i see[.!]|nice[.!]|got it[,.!]|oh,? i see|thanks for (?:telling|sharing)|nice\. why do you think|"
                           r"a quiet moment|i do not have a reliable answer|i see\. tell me a bit more|good question|"
                           r"you (?:loved|liked|watched)\b.*\bwhat part stood out)")
TALK_ROUTES = re.compile(r'^chat/(?:talk-converse|core-fallback|smalltalk-quiet|dialogue-event-reflection|core-open|open-retrieval|corpus|'
                         r'context-reasoning|core-knowledge|core-plan|local-)')


def statement_reply(messages):
    """A reply built from what the user just told CAEL, or None when nothing specific was said."""
    q = user_messages(messages)[-1][1].strip()
    low = q.lower()
    p = profile(messages, include_last=True)
    out = []
    m = re.search(r"(?i)\b(?:just )?(?:finished |been )?(watching|watched|saw|seen|reading|read|finished reading|playing|played|listening to)\s+"
                  r"(?:the (?:film|movie|book|series|show|game) )?((?-i:[A-Z])[\w'’:-]*(?: (?:of |the |and |a |in )?(?-i:[A-Z0-9])[\w'’:-]*)*)", q)
    if m:
        verb = m[1].lower()
        kind = 'film|series|show|documentary' if verb.startswith(('watch', 'saw', 'seen')) else \
            'game|video game' if verb.startswith('play') else 'song|album|band|podcast|singer' if verb.startswith('listen') else 'novel|book|series'
        title = m[2]
        page = wiki_page(title, kind)
        if page:
            out.append(f"Oh, {title}: {('the ' if re.match(r'(?:19|20)\d\d', page[1]) else '') + page[1][0].lower() + page[1][1:]}, right?")
        else:
            out.append(f"Oh, {title}!")
        out.append('What did you think of it?' if verb in ('watched', 'saw', 'seen', 'read', 'played') or 'finished' in low or 'just' in low
                   else 'How are you finding it so far?')
        return talk(' '.join(out), 'title')
    m = re.search(r"(?i)\bi(?:'ve| have)? (?:just |recently )?(?:moved|relocated) to (?-i:" + NAME + r")(?: for (?:a |my )?(new job|work|university|uni|school|studies|love))?", q)
    if m:
        place, why = m[1], (m[2] or '').lower()
        page = wiki_page(place, 'city|town|capital|country|region|island|municipality|state|village')
        fact = f" {page[1][0].upper() + page[1][1:]}, if I'm right." if page else ''
        why_part = ' and starting a new job at the same time' if 'job' in why or 'work' in why else ''
        return talk(f"Moving to {place}{why_part} is a big change!{fact} How are you settling in so far?", 'move')
    m = re.search(r"(?i)\bi(?:'m| am) going (\w+ing) (?:this weekend |tomorrow |next week |on \w+ )?(?:in|to|at|around) (?:the )?(?-i:" + NAME + r")", q) or \
        re.search(r"(?i)\bi(?:'m| am) (?:going|travelling|traveling|flying|heading) to (?:the )?(?-i:" + NAME + r")", q)
    if m:
        place = m.groups()[-1]
        activity = m[1] if m.lastindex == 2 else None
        page = wiki_page(place, 'city|town|country|region|island|park|district|national park|area|mountain|lake|village|range')
        fact = f" {place} is {describe(place, 'city|town|country|region|island|park|district|national park|area|mountain|lake|village|range')}." if page else ''
        return talk(f"That sounds like a great plan!{fact} " + (f"Have you been {activity} there before?" if activity else "Is it your first time there?"),
                    'trip')
    job = re.search(r"(?i)\bi(?:'m| am) an? ", q) and p['job'] and p['job'].split()[1] in low
    if job:
        return talk(f"You're {you(p['job'])}? That's demanding but really meaningful work. How long have you been doing it?", 'job')
    m = re.search(r"(?i)\b(?:a|an|my) (?:little |new |old |pet )?(" + REL + r") (?:called|named) (?-i:" + NAME + r")", q) or \
        re.search(r"(?i)\b(?:a|an|my|our) ((?:[\w-]+ ){0,2}(?:collie|retriever|labrador|terrier|spaniel|poodle|beagle|bulldog|shepherd|"
                  r"husky|dachshund|pug|chihuahua|boxer|corgi|doodle|tabby|siamese|kitten|puppy)) (?:called|named) (?-i:" + NAME + r")", q)
    if m:
        rel, name = m[1].lower(), m[2]
        if rel not in ('cat', 'dog', 'kitten', 'puppy', 'rabbit', 'hamster', 'parrot', 'bird', 'pet', 'fish', 'horse') and \
                re.search(r'(?i)collie|retriever|labrador|terrier|spaniel|poodle|beagle|bulldog|shepherd|husky|dachshund|pug|chihuahua|boxer|corgi|doodle', rel):
            breed = rel
            return talk(f"{name} the {breed}, how lovely! {breed[0].upper() + breed[1:]}s are clever, energetic dogs. How is {name} settling in?", 'pet')
        if rel in ('cat', 'dog', 'kitten', 'puppy', 'rabbit', 'hamster', 'parrot', 'bird', 'pet', 'fish', 'horse'):
            rest = f' And with {name}, a pet-friendly place makes total sense.' if re.search(r'(?i)pet[- ]friendly', q) else ''
            return talk(f"{name} is a lovely name for a {rel}!{rest} "
                        f"How long have you had {name}?", 'pet')
        return talk(f"Nice to hear about {name}. Tell me more about your {rel}!", 'person')
    m = re.search(r"(?i)\bmy (" + REL + r"),? (?-i:" + NAME + r"),? (?:is )?(?:visiting|coming|staying)", q)
    if m:
        return talk(f"How nice that {m[2].split()[0]} is visiting! Have you got plans for what to do together?", 'visit')
    m = re.search(r"(?i)\bmy favou?rite(?: ([\w -]+?))? (?:is|are) ((?-i:[A-Z])[\w'’:-]*(?: (?-i:[A-Z])[\w'’:-]*)*)", q)
    if m:
        title = m[2]
        page = wiki_page(title, 'novel|book|film|series|game|band|song|album|city|country|food|dish')
        fact = f" {title}: {page[1][0].lower() + page[1][1:]}." if page else ''
        return talk(f"Great choice!{fact} What do you love most about it?", 'favourite')
    m = re.search(r"(?i)\bi (?:studied|study|am studying|majored in) ([\w ]+?)(?: and | at |[.,!]|$)", q)
    if m:
        return talk(f"{m[1].strip().capitalize()}, nice. That's a useful background. What made you choose it?", 'studied')
    return None


def acknowledge(messages):
    """'Got it: you live in a flat with a small balcony that gets afternoon sun.' for a plain detail, tied to the
    question the user asked before it when there was one."""
    q = user_messages(messages)[-1][1].strip()
    sents = [x for x in re.split(r'(?<=[.!])\s+', q) if x.strip() and len(x.split()) >= 3]
    if not sents or len(q.split()) > 40 or re.search(r'(?i)^(?:thanks|thank you|ok|okay|cool|great|bye|good night)\b', q):
        return None
    if re.match(r'(?i)\s*(?:please )?(?:make|write|rewrite|change|add|turn|use|give|try|do|show|tell|put|keep|remove|shorten|translate)\b', q):
        return None         # an instruction ("Make it rhyme more."), not news to acknowledge
    detail = turned(sents[-1])
    earlier = [t for _, t in user_messages(messages)[:-1]]
    goal = next((t for t in reversed(earlier[-3:]) if '?' in t or re.search(r"(?i)\b(?:i need|i want|i'm starting|i am starting|advice)\b", t)), None)
    if goal:
        return talk(f"Thanks, that helps: {detail}. Would you like me to adjust my suggestions with that in mind?", 'noted')
    if re.search(r"(?i)\d|\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|cancel+ed|changed|moved|code|password|pin|number|"
                 r"address|appointment|booking|reservation|deadline|schedule)\b", q):
        return talk(f"Noted: {detail}. I'll remember that.", 'noted')       # a fact to keep, not news to chat about
    if re.search(r"(?i)\b(?:don't know|wrong|failed|hard|hurt|upset|sad|worried|lost|bad|awful|terrible|can't|didn't)\b", q):
        return talk(f"That sounds hard. I'm here to listen: what happened, and how are you feeling about it?", 'noted')
    return talk(f"Oh, {detail}? Tell me more about it!", 'noted')


def reassure(messages):
    """'Do you think I'm ready?': encouragement built from what the user said they have done."""
    q = user_messages(messages)[-1][1].strip()
    if not re.search(r"(?i)\bdo you think (?:i'?m|i am|i will|i'll) (?:ready|able|good enough|going to (?:do|be) (?:ok|okay|fine|well))\b|"
                     r"\bdo you think i can\b|\bis it too late (?:for me )?to\b|\bam i too old\b|"
                     r"\bam i ready\b|\bcan i do (?:it|this)\b", q):
        return None
    said = [s for _, s in statements(messages) if re.search(r"(?i)\b(?:i (?:studied|worked|have|know|did|prepared|practised|practiced|learned|learnt)|i've)\b", s)]
    worry = [s for _, s in statements(messages) if re.search(r"(?i)\b(?:worried|nervous|stressed|scared|afraid|only know)\b", s)]
    strengths = '; '.join(turned(s) for s in said[:2])
    if re.search(r"(?i)\b(?:at my age|too old|too late|learn)\b", q):
        age = re.search(r"(?i)\bi(?:'m| am) (\d{2})\b", ' '.join(s for _, s in statements(messages)))
        text = (f"Yes, I really think so{', at ' + age[1] if age else ''}. People pick up new skills at every age, and what matters most is "
                f"steady practice, not when you start. Even short, regular sessions add up quickly.")
        busy = [s for _, s in statements(messages) if re.search(r"(?i)\bonly have\b|\bfree\b|\bbusy\b", s)]
        if busy:
            text += f" You said {turned(busy[-1])}, so fifteen or twenty focused minutes on those evenings is a great plan."
        return dict(route='chat/memory-reassure', response=text + ' What would you like to learn next?', sources=[],
                    details="Encouragement built from the user's own statements in this conversation (chat_memory.py).")
    text = "I can't know for sure, but from what you've told me you have a lot going for you"
    text += f": {strengths}." if strengths else '.'
    if worry:
        text += f" Feeling nervous is normal, and preparing for it ({turned(worry[-1])}) is exactly the right move."
    text += " Whatever happens, preparing like this already puts you in a good place. What part would you like to practise next?"
    return dict(route='chat/memory-reassure', response=text, sources=[],
                details="Encouragement built from the user's own statements in this conversation (chat_memory.py).")


def talk(text, kind):
    return dict(route='chat/memory-talk-' + kind, response=text, sources=[],
                details='Reply built from what the user just said (chat_memory.py); named films, books and places described from '
                        "Wikipedia's short description when reachable.")


# ----------------------------------------------------------------------------------------------- hooks

def before(messages):
    """Recall and persona questions are answered from the conversation itself before any other route."""
    try:
        if not user_messages(messages):
            return None
        return recall(messages) or persona(messages) or about(messages) or reassure(messages)
    except Exception:
        return None


# Routes that answer from an explicit state read from this conversation (chat_core skills, ledgers, event memory).
TRUSTED_MEMORY = re.compile(r'^chat/(?:context-memory|context-reasoning|memory$|memory-(?!clarify)|ledger-|event-memory|rules-memory|'
                            r'core-(?:recall|order|time|quantities|logic|availability|decision)|interval|temporal)')
REFUSAL = re.compile(r"(?i)^\s*(?:you (?:have not|haven't) told me|i do not have|i don't have|i cannot|i could not|"
                     r"i don't think you|you did not (?:say|tell))")


def from_conversation(messages, result):
    """After the main routes, before any web search: when no route answered from the conversation's own state, a
    question whose answer is in what the user said ("Who works night shifts?") is answered from it."""
    try:
        route = str(result.get('route', ''))
        if TRUSTED_MEMORY.search(route) and not REFUSAL.search(str(result.get('response', ''))):
            return result
        q = user_messages(messages)[-1][1]
        if re.search(r"(?i)\b(?:if|instead|would|longer|shorter|later|earlier|then|after|before)\b|\d", q):
            return result        # a what-if or a calculation belongs to the reasoning routes
        found = situation_recall(messages)
    except Exception:
        return result
    return dict(found, replaced_route=result.get('route')) if found else result


def after(messages, result):
    """A generic or off-the-point reply to something the user told CAEL is replaced by one built from what they said."""
    try:
        q = user_messages(messages)[-1][1].strip()
        if not isinstance(result, dict):
            return result
        said = str(result.get('response', ''))
        route = str(result.get('route', ''))
        if is_recall(q):
            # CAEL's own memory routes answer first; when they refuse or another route took the question, the user's
            # best-matching earlier sentence is the answer.
            if TRUSTED_MEMORY.search(route) and not REFUSAL.search(said):
                return result
            late = recall(messages, late=True)
            if late and late['route'] == 'chat/memory-recall-unknown' and (TRUSTED_MEMORY.search(route) or REFUSAL.search(said)):
                return result       # their abstention already says it was not mentioned
            return dict(late, replaced_route=route) if late else result
        from .web_check import ASKS
        if '?' in q or ASKS.search(re.split(r'(?<=[.!])\s+', q)[-1]):
            return result
        if not (GENERIC_REPLY.search(said) or TALK_ROUTES.search(route) or route == 'chat/web-checked-none'):
            return result
        better = statement_reply(messages)
        if better is None and (GENERIC_REPLY.search(said) or re.search(r'^chat/(?:core-open|open-retrieval|corpus|web-checked-none)', route)):
            better = acknowledge(messages)
    except Exception:
        return result
    return dict(better, replaced_route=result.get('route')) if better else result
