"""Conversation memory: facts the user stated in the open chat window.

Nothing is stored on the server. Every request carries the whole conversation,
and these authored patterns re-read the user's own messages to answer recall
questions ("where do I live?", "what do you know about me?").
"""
import re

DETAILS = 'Recalled from your earlier messages in this chat window by authored patterns; nothing is stored after the window closes.'
ARTICLE = r'(?:an? |the )?'
VALUE = r"([a-z0-9][a-z0-9 '\-]{0,60}?)"
END = r'(?: too| as well| now| right now| currently| lately)?'


def clean(text):
    text = text.lower().replace('’', "'")
    for short, full in (("what's", 'what is'), ("i'm", 'i am'), ("don't", 'do not'), ("i've", 'i have'), ("where's", 'where is')):
        text = text.replace(short, full)
    return ' '.join(re.sub(r"[^a-z0-9' \-]+", ' ', text).split())


def you(text):
    swaps = {'my': 'your', 'me': 'you', 'i': 'you', 'mine': 'yours', 'am': 'are', 'myself': 'yourself', 'our': 'your', 'we': 'you'}
    return ' '.join(swaps.get(word, word) for word in text.split())


def clauses(text):
    # "and" starts a new clause only before a new subject: "I live in Paris and I like jazz".
    parts = re.split(r'[.!?;]+|,\s*(?=(?:i|my|but|and)\b)|\b(?:and|but|also|so) (?=(?:i|my)\b)|\bbut\b', clean(text))
    filler = r'^(?:(?:actually|well|oh|ok|okay|so|btw|by the way|also|now|anyway|in fact|just so you know|fyi)\s+)+'
    return [re.sub(filler, '', c.strip()) for c in parts if c.strip()]


def cased(value, original):
    """The user's own capitalisation of a value found in the lower-cased text."""
    pattern = r'\s+'.join(re.escape(word) for word in value.split())
    match = re.search(r'(?<![A-Za-z])' + pattern + r'(?![A-Za-z])', original.replace('’', "'"), re.I)
    return match[0] if match else value


def place(value):
    """'a shity country named israel' -> 'Israel': keep the name, not the description."""
    named = re.search(r"(?i)\b(?:named|called)\s+(.+)$", value)
    if named:
        value = named[1]
    value = value.strip()
    return value.title() if value == value.lower() else value


def items(value):
    return [item.strip() for item in re.split(r',\s*|\s+and\s+|\s+or\s+', value) if item.strip()]


def facts(messages):
    """Facts from user messages, oldest first; later statements replace earlier ones."""
    found = dict(attributes={}, likes=[], dislikes=[], has=[])
    for message in messages:
        if message.get('role') != 'user':
            continue
        original = message['content']
        for c in clauses(original):
            if re.match(r'(?:what|where|who|when|how|do|does|did|is|are|can|could|would)\b', c):
                continue
            match = re.fullmatch(r"my (?:favorite|favourite) ([a-z ]{2,30}?) (?:is|are) " + VALUE + END, c)
            if match:
                found['attributes']['favorite ' + match[1]] = you(cased(match[2], original))
                continue
            match = re.fullmatch(r"my ([a-z' ]{2,30}?)(?:'s name| name)? (?:is|are|was) (?:called |named )?" + VALUE + END, c) \
                or re.fullmatch(r"my ([a-z' ]{2,30}?) (?:is |are )?(?:called|named) " + VALUE + END, c)
            if match and match[1] not in ('name',) and not re.match(r'(?:not|so|very|really|too)\b', match[2]):
                found['attributes'][match[1].replace("'s", '')] = you(cased(match[2], original))
                continue
            match = re.fullmatch(r'i (?:live|am living|stay) in ' + VALUE + END, c)
            if match:
                found['attributes']['home'] = place(cased(match[1], original))
                continue
            match = re.fullmatch(r'i am (?:originally )?from ' + VALUE, c)
            if match:
                found['attributes']['origin'] = place(cased(match[1], original))
                continue
            match = re.fullmatch(r'i am (\d{1,3})(?: years old| years| yo)?', c)
            if match:
                found['attributes']['age'] = match[1]
                continue
            match = re.fullmatch(r'i (?:work as|am working as) ' + ARTICLE + VALUE, c) \
                or re.fullmatch(r'i am an? ((?:[a-z]+ )?(?:student|teacher|doctor|nurse|engineer|developer|programmer|designer|artist|writer|lawyer|chef|cook|driver|manager|scientist|researcher|farmer|musician|accountant|pilot|mechanic|electrician|builder|cleaner|waiter|waitress|cashier|retiree|pensioner))', c)
            if match:
                found['attributes']['job'] = match[1]
                continue
            match = re.fullmatch(r'i (?:really |also )?(?:like|love|enjoy|adore) ' + VALUE + END, c)
            if match and match[1] not in ('you', 'it', 'that', 'this'):
                for thing in items(you(cased(match[1], original))):
                    found['dislikes'] = [d for d in found['dislikes'] if d.lower() != thing.lower()]
                    found['likes'] = [l for l in found['likes'] if l.lower() != thing.lower()] + [thing]
                continue
            match = re.fullmatch(r'i (?:do not like|dislike|hate|can not stand|cannot stand) ' + VALUE + END, c)
            if match and match[1] not in ('you', 'it', 'that', 'this'):
                for thing in items(you(cased(match[1], original))):
                    found['likes'] = [l for l in found['likes'] if l.lower() != thing.lower()]
                    found['dislikes'] = [d for d in found['dislikes'] if d.lower() != thing.lower()] + [thing]
                continue
            match = re.fullmatch(r'i (?:have|have got|own) ((?:an?|one|two|three|four|five|\d+) ' + VALUE[1:-1] + ')', c)
            if match:
                found['has'].append(you(cased(match[1], original)))
    return found


def listing(items):
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


def summary(known):
    parts = []
    attributes = known['attributes']
    labels = dict(home='you live in {}', origin='you are from {}', age='you are {} years old', job='you are {}')
    for key, value in attributes.items():
        if key in labels:
            job = value if key != 'job' else ('an ' if value[0] in 'aeiou' else 'a ') + value
            parts.append(labels[key].format(job))
        else:
            parts.append(f'your {key} is {value}')
    if known['likes']:
        parts.append('you like ' + listing(known['likes']))
    if known['dislikes']:
        parts.append("you don't like " + listing(known['dislikes']))
    if known['has']:
        parts.append('you have ' + listing(known['has']))
    return parts


def recall(messages, name=None):
    """Answer a question about earlier messages, or acknowledge a new fact. None when not applicable."""
    text = messages[-1]['content']
    t = re.sub(r'^(?:and|so|ok|okay|then|also|well|but)\s+', '', clean(text).rstrip(' ?'))
    t = re.sub(r'^(what|where|how old|who) i (like|love|enjoy|live|am|do)\b', r'\1 do i \2', t)  # "what i like" -> "what do i like"
    t = t.replace('where do i am', 'where am i').replace('how old do i am', 'how old am i')
    history = messages[:-1]
    known = facts(history)
    attributes = known['attributes']
    users = [m['content'] for m in history if m.get('role') == 'user']
    answer = lambda response: dict(response=response, route='chat/memory', sources=[], details=DETAILS)
    unknown = lambda what: answer(f"You haven't told me {what} in this chat yet.")

    if re.fullmatch(r'what do you (?:know|remember) about me|what have i told you(?: about (?:me|myself))?|what did i tell you about (?:me|myself)|tell me what you know about me|do you remember (?:me|what i told you)', t):
        parts = ([f'your name is {name}'] if name else []) + summary(known)
        if not parts:
            return answer("You haven't told me anything about yourself in this chat yet. I'll remember what you share while this window is open.")
        return answer('From this chat, I know that ' + listing(parts) + '.')
    if re.fullmatch(r'what (?:was|is) my (?:first|1st) (?:message|question)|what did i (?:say|ask) first', t):
        return answer(f'Your first message was: "{users[0]}"' if users else 'This is your first message in this chat.')
    if re.fullmatch(r'what (?:was|is) my (?:last|previous) (?:message|question)|what did i (?:just )?(?:say|ask)(?: before| last| before that)?', t):
        return answer(f'Your previous message was: "{users[-1]}"' if users else 'This is your first message in this chat.')
    if re.fullmatch(r'what (?:did|have) we (?:talk|talked|been talking) about(?: so far)?|what have we discussed|summari[sz]e (?:our|this) (?:chat|conversation)', t):
        if not users:
            return answer("We haven't talked about anything yet. This is your first message.")
        recent = users[-6:]
        lead = f'You have sent {len(users)} messages so far. ' + ('The most recent were: ' if len(users) > 6 else 'You said: ')
        return answer(lead + ' / '.join(f'"{u[:80]}"' for u in recent))
    if re.fullmatch(r'how many (?:messages|questions) (?:have i|did i) (?:sent|send|asked|ask)(?: you)?', t):
        return answer(f'You have sent {len(users)} messages before this one in this chat.')
    if re.fullmatch(r'where do i live|where am i living|what (?:city|country|town) do i live in', t):
        return answer(f"You live in {attributes['home']}.") if 'home' in attributes else unknown('where you live')
    if re.fullmatch(r'where am i from|where do i come from|where was i born', t):
        return answer(f"You are from {attributes['origin']}.") if 'origin' in attributes else unknown("where you're from")
    if re.fullmatch(r'how old am i|what is my age', t):
        return answer(f"You are {attributes['age']} years old.") if 'age' in attributes else unknown('your age')
    if re.fullmatch(r'what (?:do i do(?: for (?:a )?(?:living|work))?|is my job|is my profession|is my work)', t):
        job = attributes.get('job')
        return answer(f"You are {'an' if job[0] in 'aeiou' else 'a'} {job}.") if job else unknown('what you do')
    if re.fullmatch(r'what do i (?:like|love|enjoy)(?: to do| doing)?|what are my (?:hobbies|interests|likes)|what (?:are|is) my hobby', t):
        return answer('You told me you like ' + listing(known['likes']) + '.') if known['likes'] else unknown('what you like')
    if re.fullmatch(r"what do i (?:not like|dislike|hate)|what do not i like", t):
        return answer("You told me you don't like " + listing(known['dislikes']) + '.') if known['dislikes'] else unknown("what you don't like")
    if re.fullmatch(r'what do i have|what do i own', t):
        return answer('You told me you have ' + listing(known['has']) + '.') if known['has'] else unknown('what you have')
    likes = re.fullmatch(r'do i (?:like|love|enjoy) ' + VALUE, t)
    if likes:
        thing = you(likes[1])
        if thing in [l.lower() for l in known['likes']]:
            return answer(f'Yes, you told me you like {thing}.')
        if thing in [d.lower() for d in known['dislikes']]:
            return answer(f"No, you told me you don't like {thing}.")
        return unknown(f'whether you like {thing}')
    asked = re.fullmatch(r"what is my ([a-z' ]{2,40}?)(?:'s name| name| called| named)?|what is the name of my ([a-z ]{2,30})|who is my ([a-z ]{2,30})|what did i call my ([a-z ]{2,30})", t)
    if asked:
        key = next(group for group in asked.groups() if group).replace("'s", '').replace('favourite', 'favorite').strip()
        if key == 'name':
            return None  # Names are handled with greetings.
        if key in attributes:
            return answer(f'Your {key} is {attributes[key]}.')
        named = re.search(r"(?:'s name| name| called| named)$", t) and not key.endswith('name')
        return unknown(f"your {key}'s name" if named else f'your {key}')

    # Acknowledge a clearly stated personal fact so the user knows it was understood.
    # A lone like/dislike ("I like pizza") is left to the chat model's follow-up question.
    if '?' not in text:
        current = facts([messages[-1]])
        added = summary(current)
        if current['attributes'] or len(added) > 1:
            return answer('Got it, ' + listing(added) + '. I will remember that while this chat is open.')
    return None
