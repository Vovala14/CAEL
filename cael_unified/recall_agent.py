"""The Rememberer: pointed questions about what the user said earlier in the conversation.

"What was my dog's name again, and how old is he?"   (told: "a rescue greyhound called Biscuit. He's four years old.")
"Remind me, how old did I say Mila is?"               (told: "Mila is 9 and Jonas is 6.")
"Which of my friends is vegetarian?"                  (told: "Dana is vegetarian.")

chat_memory.py answers most recall questions. These three shapes need a little more: a greyhound is a dog, an age
belongs to the name before it, and "which of my friends" wants the name, not the whole sentence. The answer is always
taken from the user's own turns; when it is not there, None (the other agents answer).
"""
import re

KINDS = {
    'dog': 'dog puppy greyhound labrador lab spaniel terrier poodle collie retriever bulldog beagle husky pug dachshund whippet corgi mongrel hound '
           'sheepdog shepherd rottweiler doberman chihuahua cockapoo labradoodle staffy lurcher pup',
    'cat': 'cat kitten tabby siamese persian moggy tomcat ragdoll',
    'pet': 'pet dog puppy cat kitten rabbit hamster parrot budgie tortoise guinea goldfish fish pony horse gerbil ferret lizard snake greyhound',
    'horse': 'horse pony mare stallion foal',
    'bird': 'bird parrot budgie canary cockatiel',
}
NUM = r'(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)'
AGE = NUM + r'(?:[- ](?:and a half[- ])?(?:years?|months?|weeks?|days?))?(?:[- ]old)?'
NOT_NAME = {'I', 'The', 'A', 'An', 'He', 'She', 'It', 'They', 'We', 'My', 'Hi', 'Hello', 'Hey', 'On', 'In', 'And', 'But', 'So', 'Monday', 'Tuesday',
            'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'Remind', 'What', 'Which', 'How', 'When', 'Where', 'Who', 'Is', 'Any', 'Thanks'}


def user_turns(messages):
    return [m['content'] for m in messages if m.get('role') == 'user']


def told(messages):
    """The statement sentences of the earlier user turns, newest last."""
    out = []
    for t in user_turns(messages)[:-1]:
        out += [s.strip() for s in re.split(r'(?<=[.!?])\s+', t) if s.strip() and not s.strip().endswith('?')]
    return out


def reply(text):
    return dict(route='chat/memory-recall-told', response=text, sources=[], details='From what the user said earlier in this conversation (recall_agent.py).')


def kinds_for(noun):
    noun = noun.lower()
    words = set(KINDS.get(noun, noun).split()) | {noun}
    if noun in ('plant', 'houseplant', 'flower'):
        words |= set('plant houseplant monstera cactus succulent fern orchid pothos ivy palm bonsai'.split())
    return words


def name_and_age(messages):
    last = user_turns(messages)[-1]
    m = re.search(r"(?i)\bwhat(?:'s| is| was)? (?:the name of )?my ([a-z]+)(?:'s)? name\b|\bwhat(?:'s| is| was| did i say)? my ([a-z]+)(?:'s| is| was)? called\b|"
                  r"\bwhat did i (?:call|name) my ([a-z]+)\b|\bwhat(?:'s| is| was) the name of my ([a-z]+)\b", last)
    if not m:
        return None
    noun = next(g for g in m.groups() if g).lower()
    kinds = kinds_for(noun)
    sents = told(messages)
    name, at = None, None
    for i, s in enumerate(sents):
        if not any(re.search(r'(?i)\b' + k + r's?\b', s) for k in kinds):
            # "I bought a fiddle leaf fig and named it Frank" for "my plant": a thing that is a kind of the noun asked about
            things = re.findall(r"(?i)\b(?:a|an|my|our|the)\s+(?:[a-z]+\s+){0,2}?([a-z]+)\s+(?:and |which |that )?(?:i(?:'ve)? |we(?:'ve)? )?(?:named|called)\b", s)
            if not any(is_a(t.lower(), noun) or is_a(t.lower(), noun.rstrip('s')) for t in things):
                continue
        if i + 1 < len(sents) and re.match(r"(?i)\s*(?:i'?ve |i have |we'?ve |i )?(?:named|called) (?:it|him|her|them) ", sents[i + 1]):
            s = s + ' ' + sents[i + 1]          # "I bought a monstera. I've named it Gerald."
        hit = re.search(r"\b(?:called|named|name is|name's)\s+(?:(?:it|him|her|them)\s+)?([A-Z][a-z]+)\b", s) or re.search(r"(?i)\bmy (?:" + '|'.join(kinds) + r"),? (?-i:([A-Z][a-z]+))\b", s) \
            or re.search(r"\b([A-Z][a-z]+),? my (?:" + '|'.join(kinds) + r")\b", s)
        if hit and hit[1] not in NOT_NAME:
            name, at = hit[1], i
    if not name:
        return None
    text = f"Your {noun} is called **{name}**"
    if re.search(r'(?i)\bwhat (?:kind|type|sort|breed)\b', last):
        generic = {'plant', 'houseplant', 'flower', 'pet', 'dog', 'cat', 'bird', 'horse'}
        found_kinds = [k for k in kinds if k != noun and re.search(r'(?i)\b' + k + r'\b', ' '.join(sents[at:at + 2]))]
        kind = next((k for k in found_kinds if k not in generic), None) or next(iter(found_kinds), None)
        if kind:
            text += f", and {'it' if noun in ('plant', 'houseplant', 'flower') else 'he or she'}'s a {kind}"
    if re.search(r'(?i)\bhow old\b|\bage\b', last):
        age = None
        for s in sents[at:at + 3]:
            a = re.search(r"(?i)\b(?:he|she|it|" + name + r")(?:'s| is| was)(?: about| around| nearly| almost| just)? (" + AGE + r")\b", s) \
                or re.search(r"(?i)\b(" + NUM + r"[- ](?:years?|months?|weeks?)[- ]old)\b", s)
            if a:
                age = a[1]
                break
        pronoun = re.search(r'(?i)\b(he|she)\b', last)
        who = pronoun[1].lower() if pronoun else name
        if age:
            age = age if re.search(r'old|year|month|week', age) else age + ' years old'
            text += f", and you said {who}'s {age}"
        else:
            text += f", but you haven't told me how old {who} is"
    return reply(text + '.')


def how_old(messages):
    last = user_turns(messages)[-1]
    m = re.search(r"(?i)\bhow old (?:did i (?:say|tell you|mention) (?:that )?|is |was |did you say )(?-i:([A-Z][a-z]+))\b", last)
    if not m or m[1] in NOT_NAME:
        return None
    name = m[1]
    for s in reversed(told(messages)):
        a = re.search(r"\b" + name + r"(?:'s| is| was| turned| has just turned| just turned| will be)(?: about| around| nearly| almost| now)? (" + AGE + r")\b", s) \
            or re.search(r"\b" + name + r",? (?:who is |who's |aged? )?\(?(" + NUM + r")\)?(?=[,.)]|\s+and\b|$)", s) \
            or re.search(r"(?i)\b(" + NUM + r")[- ](?:year|month)[- ]old,? (?:\w+ )?(?-i:" + name + r")\b", s) \
            or re.search(r"\b" + name + r",? (?:our|my|the|a) (" + NUM + r")[- ](?:year|month)[- ]old\b", s)
        if a:
            age = a[1]
            unit = 'months old' if re.search(r'(?i)month[- ]old', s) else 'years old' if re.search(r'(?i)year[- ]old', s) else ''
            shown = f'{age} {unit}' if unit and not re.search(r'old', age) else age
            return reply(f"You said {name} is **{shown}**.")
    return None


def which_of(messages):
    last = user_turns(messages)[-1]
    m = re.search(r"(?i)\bwhich (?:one )?of (?:my|the|our) ([a-z]+)(?: did i say)? ((?:is|was|has|had|does|did|can|can't|cannot|likes?|loves?|hates?|plays?|works?|lives?|"
                  r"eats?|drinks?|wants?|needs?|speaks?|drives?)\b.*?)\??\s*$", last) \
        or re.search(r"(?i)\bwho(?: did i say)? (?:is|was) (?:the one (?:who|that) (?:is |was )?|the )?(.+?)\??\s*$", last)
    if not m:
        return None
    pred = m[m.lastindex]
    stop = {'is', 'was', 'a', 'an', 'the', 'has', 'had', 'does', 'did', 'again', 'one', 'who', 'that', 'my', 'of', 'to', 'in'}
    want = {w.rstrip('s') for w in re.findall(r"[a-z']+", pred.lower())} - stop
    if not want:
        return None
    for s in reversed(told(messages)):
        for clause in re.split(r"(?i),\s*(?:and\s+)?|\s+and\s+|;\s*|\s+but\s+|\s+while\s+", s):
            have = {w.rstrip('s') for w in re.findall(r"[a-z']+", clause.lower())}
            if not want <= have:
                continue
            names = [n for n in re.findall(r"\b([A-Z][a-z]+)\b", clause) if n not in NOT_NAME]
            if len(names) == 1:
                said = clause.strip(' .')
                said = re.sub(r"(?i)\bmy\b", 'your', said)
                return reply(f"**{names[0]}**. You said {said[:1].lower() + said[1:] if not said.startswith(names[0]) else said}.")
    return None


def is_a(word, cls, depth=4):
    """Is `word` a kind of `cls` in WordNet ('kitchen' is a room, 'Tuesday' a day)? First sense, a few levels up."""
    try:
        from . import open_chat as oc
        import json
        wn = oc.wordnet()
        if wn is None:
            return False
        frontier = [word.lower()]
        for _ in range(depth):
            nxt = []
            for w in frontier:
                for (ups,) in wn.execute('SELECT s.hypernyms FROM lemma l JOIN synset s ON s.id = l.synset WHERE lower(l.word) = ? AND l.pos = "noun" '
                                         'ORDER BY l.rank LIMIT 2', (w,)).fetchall():
                    for u in json.loads(ups or '[]'):
                        u = u.lower()
                        if u == cls or u.split('.')[0] == cls:
                            return True
                        nxt.append(u)
            frontier = nxt[:6]
        return False
    except Exception:
        return False


def which_value(messages):
    """'Remind me, which floor did I say the flat is on?' -> the sentence where the user said it, in the second person."""
    last = user_turns(messages)[-1]
    m = re.search(r"(?i)\b(?:which|what) ([a-z]+)\b(?: (?:did|have) i (?:say|said|tell you|mention))", last)
    if not m or m[1].lower() in ('day', 'time', 'one', 'name'):
        return None
    noun = m[1].lower()
    rest = {w.lower().rstrip('s') for w in re.findall(r"[A-Za-z]{4,}", last[m.end():])} - {'that', 'this', 'have', 'with', 'what', 'which'}

    def kind_in(s):
        for w in re.findall(r"[A-Za-z]+", s):
            lw = w.lower()
            if lw != noun and lw.endswith(noun) and len(lw) > len(noun) + 2:
                return True
            if len(lw) > 3 and is_a(lw, noun):
                return True
        return False
    for s in reversed(told(messages)):
        shares = rest & {w.lower().rstrip('s') for w in re.findall(r"[A-Za-z]{4,}", s)}
        if re.search(r'(?i)\b' + noun + r's?\b', s) or (shares and kind_in(s)):     # "the radiator in our kitchen" for "which room"
            said = s.strip().rstrip('.!')
            said = re.sub(r"(?i)\bI'm\b", "you're", said)
            said = re.sub(r"(?i)\bI am\b", "you are", said)
            said = re.sub(r"(?i)\bI\b", "you", said)
            said = re.sub(r"(?i)\bmy\b", "your", said)
            said = re.sub(r"(?i)\bwe\b", "you", said)
            said = re.sub(r"(?i)\bour\b", "your", said)
            # the value is the word that is a kind of the noun asked ("bedroom" for "which room"), else the noun's phrase
            kind = None
            for w in re.findall(r"[A-Za-z]+", said):
                lw = w.lower()
                if lw == noun or lw in ('your', 'the', 'a', 'an'):
                    continue
                is_kind = lw.endswith(noun) and len(lw) > len(noun) + 2
                if not is_kind:
                    is_kind = len(lw) > 3 and is_a(lw, noun)
                if is_kind:
                    kind = w
                    break
            if kind:
                return reply(f"The **{kind.lower()}**. You said {said[:1].lower() + said[1:]}.")
            v = re.search(r"(?i)\b((?:the |a |an )?(?:(?!and\b|or\b|but\b)\w+ ){0,2}" + noun + r")\b", said)
            return reply(f"You said {said[:1].lower() + said[1:]}" + (f": **{v[1]}**." if v and v[1].lower() not in ('the ' + noun, noun) else '.'))
    return None


MEASURE = {
    'long': r"(?:\d+(?:\.\d+)?|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fourteen|fifteen|twenty|thirty|a couple of|a few)[- ](?:and a half[- ])?"
            r"(?:hours?|minutes?|mins?|days?|weeks?|months?|years?|nights?)(?:[- ]long)?",
    'old': r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|twenty)[- ](?:years?|months?|weeks?)[- ]old|"
           r"(?:about|around|nearly|almost) (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten) years? old",
    'much': r"(?:\$|£|€)\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)? (?:dollars|pounds|euros)",
    'many': r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty)\b(?: times?)?",
    'far': r"\d+(?:\.\d+)?\s?(?:km|kilomet(?:re|er)s?|miles?|m\b|metres?)",
}


def how_measure(messages):
    """'How long did I say the flight is?', 'How old did I say the laptop is?', 'How much did I say I have saved?'"""
    last = user_turns(messages)[-1]
    m = re.search(r"(?i)\bhow (long|old|much|many|far)\b(?: [a-z]+){0,2}? (?:did i|have i) (?:say|said|tell you|mention)\b(.*)$", last)
    if not m:
        return None
    kind, rest = m[1].lower(), m[2]
    if kind == 'old' and re.search(r"\b[A-Z][a-z]+\b", rest):
        return None                         # a person's age: how_old() answers that
    keys = [w for w in re.findall(r"[a-z]+", rest.lower()) if w not in ('the', 'my', 'is', 'was', 'i', 'it', 'be', 'll', 'will', 'am', 'a', 'an', 'again',
                                                                         'have', 'had', 'did', 'say', 'each', 'every', 'per', 'that', 'this', 'there')]
    best = None
    for s in reversed(told(messages)):
        hits = [x for x in re.finditer(r"(?i)" + MEASURE[kind], s)]
        if not hits:
            continue
        overlap = sum(1 for k in keys if re.search(r'(?i)\b' + k[:5], s))
        if best is None or overlap > best[0]:
            best = (overlap, s, hits[0][0])
    if not best or (keys and best[0] == 0 and len(keys) > 1):
        return None
    said = best[1].strip().rstrip('.!')
    for a, b in ((r"\bI'm\b", "you're"), (r"\bI am\b", 'you are'), (r"\bI've\b", "you've"), (r"\bI'll\b", "you'll"), (r"\bI\b", 'you'),
                 (r"\bmy\b", 'your'), (r"\bwe're\b", "you're"), (r"\bwe\b", 'you'), (r"\bour\b", 'your')):
        said = re.sub(r"(?i)" + a, b, said)
    value = re.sub(r"(?i)^(\d+)-(hour|minute|day|week|month|year|night)$", lambda x: f"{x[1]} {x[2]}s", best[2])
    return reply(f"**{value}**. You said: \"{said[:1].upper() + said[1:]}.\"")


def what_wrong(messages):
    """'What did I say was wrong with my knives?' -> the sentence where the user said what the matter with them was."""
    last = user_turns(messages)[-1]
    m = re.search(r"(?i)\bwhat (?:did|have) i (?:say|said|tell you|mention)(?: was| is)? (?:wrong|the (?:problem|matter|issue|trouble)) with (?:my |the |our )?([a-z ]+?)\s*\??\s*$", last) \
        or re.search(r"(?i)\bwhat(?:'s| is| was) (?:wrong|the (?:problem|matter|issue)) with (?:my |the |our )?([a-z ]+?),? (?:again|did i say)\s*\??\s*$", last)
    if not m:
        return None
    words = [w for w in m[1].lower().split() if len(w) > 2]
    if not words:
        return None
    head = words[-1]
    forms = {head, head.rstrip('s'), re.sub(r'ves$', 'fe', head), re.sub(r'ves$', 'f', head), re.sub(r'ies$', 'y', head)}
    for s in told(messages):
        if any(re.search(r'(?i)\b' + re.escape(f) + r'(?:s|es)?\b', s) for f in forms if f):
            said = s.strip().rstrip('.!')
            for a, b in ((r"\bI'm\b", "you're"), (r"\bI am\b", 'you are'), (r"\bI've\b", "you've"), (r"\bI\b", 'you'), (r"\bmy\b", 'your'),
                         (r"\bwe're\b", "you're"), (r"\bwe\b", 'you'), (r"\bour\b", 'your')):
                said = re.sub(r"(?i)" + a, b, said)
            return reply(f"You said {said[:1].lower() + said[1:]}.")
    return None


def respond(messages):
    if not messages or messages[-1].get('role') != 'user' or len(user_turns(messages)) < 2:
        return None
    for find in (what_wrong, name_and_age, how_old, which_of, which_value, how_measure):
        try:
            got = find(messages)
        except Exception:
            got = None
        if got:
            return got
    return None
