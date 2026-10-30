"""Personal facts are only ever recalled, never supplied (0.3.8).

CAEL knows a person's birthplace, age, job, family or other biographical details only when the user stated
them in this conversation. Recall routes (conversation_memory, memory, session_profile) answer what was said;
this module recognises a question about the user (or a person introduced as "my sister", "my boss") so that,
when no recall route answered, the question gets an honest abstention instead of falling through to retrieval
(chat_corpus), encyclopedic lookup or the legacy chat model, any of which could assert a stranger's fact
("She was born in Paris"). It also lets retrieval reject a stored reply written about a different person.
Authored patterns only; no model.
"""
import re

RELATIVE = (r"(?:best friend|friend|boyfriend|girlfriend|partner|wife|husband|spouse|fianc[eé]e?|mother|mom|mum|father|dad|"
            r"parents?|sister|brother|siblings?|son|daughter|kids?|children|child|baby|grandmother|grandma|grandfather|grandpa|"
            r"grandparents?|aunt|uncle|cousin|niece|nephew|boss|manager|colleague|coworker|co-worker|roommate|flatmate|"
            r"neighbou?r|teacher|doctor|pet|dog|cat)")
OWNER = r"(?:i|me|my(?: own)?|myself|my " + RELATIVE + r")"
ATTRIBUTES = [
    ('born', r"\b(?:born|birth ?place|place of birth|home ?town|grow up|grew up|native)\b"),
    ('birthday', r"\b(?:birthday|birth ?date|date of birth|what year was|when was)\b"),
    ('age', r"\b(?:how old|age)\b"),
    ('name', r"\b(?:name|called)\b"),
    ('job', r"\b(?:job|work(?:s)? as|occupation|profession|career|employer|do for (?:a )?(?:living|work)|work for|work at)\b"),
    ('home', r"\b(?:live|lives|living|address|reside)\b"),
    ('origin', r"\b(?:where (?:am|is|are) .{0,25}\bfrom|nationality|come from|comes from|ethnicity|citizenship)\b"),
    ('family', r"\b(?:married|single|divorced|kids|children|siblings|brothers?|sisters?|wife|husband|partner)\b"),
    ('other', r"\b(?:religion|phone(?: number)?|email|school|university|college|degree|height|weight|blood type|eye colou?r|hair colou?r|favou?rite)\b"),
]
ASK = re.compile(r"(?i)^\s*(?:(?:and|so|ok|okay|then|also|well|but|now|hey)[, ]+)*(?:what|where|when|which|who|how|do|does|did|am|is|are|was|were|have|has|can you (?:tell|remind)|tell me|remind me|guess)\b")
SELF = re.compile(r"(?i)\b(?:was i|were i|am i|do i|did i|have i|i was|i am|i'm|my|me|myself)\b")
ADVICE_LIKE = re.compile(r"(?i)\b(?:should|could|can|would|might|must|to|best|good|better|ideas?|tips?|ways?|how (?:do|can|should|could) i|help)\b")


def _clean(text):
    return ' '.join(text.replace('’', "'").split())


def attribute(text):
    low = _clean(text).lower()
    for name, cue in ATTRIBUTES:
        if re.search(cue, low):
            return name
    return None


def subject(text):
    """'you' for the speaker, 'your sister' for a person introduced by relation, or None."""
    low = _clean(text).lower()
    rel = re.search(r"\bmy ((?:best |older |younger |little |big )?" + RELATIVE + r")\b", low)
    if rel and not re.search(r"\bmy (?:own )?(?:name|age|birthday|job|birth ?place|home ?town)\b", low.split(rel[0])[0] + ' '):
        return 'your ' + rel[1]
    if SELF.search(low):
        return 'you'
    return None


def personal_question(text):
    """(subject, attribute) when the message asks a biographical question about the user or their people."""
    text = _clean(text)
    if not text or len(text) > 160 or '\n' in text:
        return None
    if not (text.rstrip().endswith('?') or ASK.match(text)):
        return None
    if not ASK.match(text):
        return None
    low = text.lower()
    who = subject(low)
    what = attribute(low)
    if who is None or what is None:
        return None
    # "How do I find out where I was born?" / "What should I name my dog?" are requests, not recall questions.
    if re.search(r"(?i)\b(?:how (?:do|can|should|could) i|should i|could i|can i|what should|ideas?|tips?|suggest|recommend|good name|name for|calculate|find out)\b", low):
        return None
    if what == 'name' and who == 'you':
        return None          # the user's own name has its own greeting/profile route
    if what == 'other' and re.search(r"(?i)\bfavou?rite\b", low) and who == 'you' and not re.search(r"(?i)\bmy favou?rite\b", low):
        return None
    return who, what


PHRASE = dict(born='where {w} {was} born', birthday="{ws} birthday", age="{ws} age", name="{ws} name", job="{ws} job",
              home='where {w} {live}', origin='where {w} {be} from', family="that about {wo}", other="that about {wo}")


def abstain(text):
    """An honest 'you have not told me' reply, or None when the message is not a personal question."""
    found = personal_question(text)
    if not found:
        return None
    who, what = found
    you = who == 'you'
    phrase = PHRASE[what].format(w=who, ws='your' if you else who + "'s", wo='yourself' if you else who,
                                 was='were' if you else 'was', live='live' if you else 'lives', be='are' if you else 'is')
    return dict(route='chat/personal-unknown', sources=[],
                response=f"You haven't told me {phrase} in this chat, so I don't know. "
                         f"I only know personal details that you tell me, and I won't guess them.",
                details='Personal and biographical facts are only recalled from what you said in this conversation; '
                        'retrieved text about other people is never used for them (personal_facts.py, authored rules).')


THIRD = re.compile(r"(?i)\b(?:she|he|her|his|him|hers|herself|himself)\b")
FIRST = re.compile(r"(?i)\b(?:i|me|my|mine|myself)\b")
BIOGRAPHY = re.compile(r"(?i)\b(?:born|birth\w*|age|years? old|grew up|married|died|lives? in|from)\b")


def foreign_person(request, stored):
    """True when a stored corpus request is about a different person than the user's request."""
    request, stored = _clean(request), _clean(stored)
    if THIRD.search(stored) and not THIRD.search(request):
        return True                     # "What city was she born in?" is not "What city was I born in?"
    if FIRST.search(request) and BIOGRAPHY.search(request) and BIOGRAPHY.search(stored) and not FIRST.search(stored):
        return True
    return False
