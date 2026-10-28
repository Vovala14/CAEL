"""Authored emotional vocabulary + clause/perspective-aware conversation.

This is a finite symbolic composer, not sentiment inference about a person's
inner life. It reflects what the user states, can express uncertainty, and
remembers listening preferences only inside the supplied conversation.
"""
import random
import re

DETAILS = ('Authored non-neural emotional lexicon, explicit speaker/negation rules and '
           'composed responses. Reflects stated feelings without diagnosing, inventing '
           'motives or claiming human experience. Context is this conversation only.')
GROUPS = {
    'overwhelmed': ('overwhelmed overloaded swamped frazzled stressed strained pressured burnt-out burned-out',
        ['That sounds like a lot to carry at once.', 'It sounds as though too much is landing on you at the same time.'],
        'Which part feels most pressing?',
        'If you want a practical next step, choose one small task and let the rest wait for a moment.'),
    'anxious': ('anxious nervous worried apprehensive uneasy tense uncertain scared afraid frightened panicked',
        ['There seems to be a lot of uncertainty in this for you.', 'Facing something uncertain can feel unsettling.'],
        'Is there a particular part you are worried about?',
        'We could separate what you know from what you are predicting, then choose one thing you can prepare.'),
    'sad': ('sad down disappointed discouraged disheartened heartbroken grieving devastated miserable unhappy low dejected',
        ['That sounds painful.', 'It sounds as though this has left you feeling low.'],
        'Would you like to say more about the part that hurts?',
        'You could give yourself some room before deciding what to do next, or talk with someone you trust.'),
    'lonely': ('lonely isolated disconnected excluded homesick unseen left-out',
        ['Feeling disconnected can be hard, even when people are around.', 'It sounds as though you are missing a sense of connection.'],
        'Are you missing someone in particular, or feeling more generally alone?',
        'If it feels manageable, you could send one person a simple message rather than trying to solve everything at once.'),
    'angry': ('angry frustrated irritated annoyed furious resentful upset bitter fed-up',
        ['Something about this has really bothered you.', 'It sounds frustrating to be in that position.'],
        'What part felt unfair or most upsetting?',
        'You could pause before replying, then describe the specific action and what you need to be different.'),
    'embarrassed': ('embarrassed ashamed guilty regretful awkward mortified humiliated',
        ['That sounds uncomfortable to sit with.', 'It sounds as though you are being quite hard on yourself about this.'],
        'Is the hardest part what happened, or what you think others may be thinking?',
        'If there is something to repair, you could name that one action without turning it into a judgment about your whole self.'),
    'tired': ('tired exhausted drained weary depleted worn-out fatigued',
        ['That sounds draining.', 'It sounds as though you have very little energy left right now.'],
        'Has this been building up, or was today particularly demanding?',
        'If you can, make the next step smaller and give yourself a pause before taking on more.'),
    'happy': ('happy glad delighted thrilled joyful elated excited enthusiastic cheerful hopeful optimistic ecstatic',
        ['That sounds like a moment worth enjoying.', 'There is a lot of energy and happiness in what you described.'],
        'What part are you most looking forward to?',
        'You could take a moment to mark what went well, in whatever way feels right to you.'),
    'proud': ('proud accomplished fulfilled satisfied confident encouraged',
        ['That sounds meaningful to you.', 'It sounds as though you can see the effort you put into this.'],
        'What part of it means the most to you?',
        'You could note what helped you get here so you can draw on it again.'),
    'relieved': ('relieved reassured calmer calm peaceful grateful thankful content',
        ['It sounds as though some of the pressure has lifted.', 'There seems to be a sense of relief in that.'],
        'What feels different now?',
        'You could give yourself a little time to settle before deciding what comes next.'),
}
WORDS = {word: category for category, (words, *_) in GROUPS.items() for word in words.split()}
POSITIVE = {'happy', 'proud', 'relieved'}
EMOTION = '|'.join(sorted(map(re.escape, WORDS), key=len, reverse=True))
TECHNICAL = re.compile(r'(?i)```|\b(?:python|javascript|function|variable|regex|code|script|prompt|translate|grammar|define|meaning of)\b')
QUESTION = re.compile(r'(?i)^(?:what|who|which|where|when|how|why|explain|write|generate|draw|calculate|compute|solve)\b')
LISTEN = re.compile(r"(?i)\b(?:just (?:listen|needed to say it|want(?:ed)? to vent)|no advice|(?:do not|don't) (?:want|give(?: me)?) (?:any )?advice|not looking for (?:advice|solutions))\b")
NO_QUESTIONS = re.compile(r"(?i)\b(?:no questions|(?:do not|don't|stop) ask(?:ing)?(?: me)? questions)\b")
ADVICE = re.compile(r'(?i)\b(?:what (?:can|should) i do|how (?:can|do) i (?:cope|handle|deal)|(?:can you )?(?:give|offer) (?:me )?(?:some )?advice|i want advice|help me (?:cope|handle|deal))\b')
SELF_FRAME = re.compile(r"(?i)^(?:(?:honestly|lately|today|right now|sometimes)[, ]+)?(?:i (?:am|feel|have been|was)(?: feeling)?|i'm(?: feeling)?|i've been(?: feeling)?|i felt|feeling)\s+")


def normalize(text):
    return text.replace('’', "'").replace('—', ', ').replace('–', '-').strip()


def emotions(text):
    """Only affirmative feelings attached to the speaker, preserving clause order."""
    text = normalize(text)
    if '"' in text or '“' in text or '```' in text or len(text)>1400:
        return []
    results = []
    subject = False
    for clause in re.split(r'(?i)[.;!?]|\b(?:but|yet|although|however|and)\b', text):
        clause = clause.strip(' ,')
        frame = SELF_FRAME.match(clause)
        if frame:
            subject, body = True, clause[frame.end():]
        elif subject and re.match(r'(?i)^(?:also |still |really |a little |very |quite )*(?:not |no longer )?(?:'+EMOTION+r')\b', clause):
            body = clause
        else:
            subject = False
            continue
        # An emotional predicate must precede its cause. An anxious feeling
        # about a happy friend is not evidence that the speaker is happy.
        predicate = re.split(r'(?i)\b(?:about|because|that|after|over|since|with|at|for|when|to)\b', body, maxsplit=1)[0]
        for match in re.finditer(r'(?i)\b('+EMOTION+r')\b', predicate):
            before = predicate[:match.start()].lower()
            if re.search(r"\b(?:not|never|no longer|hardly)\b", before):
                continue
            word = match[1].lower()
            if word not in [w for w, _ in results]:
                results.append((word, WORDS[word]))
    return results[:4]


def preferences(messages, current):
    listen, questions = False, True
    for message in messages[-30:]:
        if message.get('role') != 'user':
            continue
        text = normalize(message['content'])
        if LISTEN.search(text):
            listen = True
        if NO_QUESTIONS.search(text):
            questions = False
        if ADVICE.search(text):
            listen = False
        if re.search(r'(?i)\b(?:you can ask questions|questions are okay)\b', text):
            questions = True
    return listen, questions


def reply(messages, seed=0):
    if not messages or messages[-1].get('role') != 'user':
        return None
    text = normalize(messages[-1]['content'])
    if not text or len(text)>1400 or '\n' in text or TECHNICAL.search(text):
        return None
    # Crisis/physical-health messages belong to the existing specialized routes.
    if re.search(r'(?i)\b(?:suicid\w*|kill myself|hurt myself|self[- ]harm|chest pain|cannot breathe|can\'t breathe|overdose|bleeding)\b', text):
        return None
    out = lambda response, kind, **extra: dict(response=response, route='chat/emotional-'+kind,
                                             sources=[], details=DETAILS, **extra)
    if re.fullmatch(r"(?i)(?:have you (?:ever )?felt (?:sad|lonely|happy|grief)|do you (?:really )?(?:have feelings|understand how i feel))[?.!]*", text):
        return out("I don't have feelings or lived experiences. I can listen to what you describe and try to respond thoughtfully, but you can tell me when I have misunderstood.", 'identity')
    support = re.fullmatch(r"(?i)my (friend|partner|sister|brother|colleague) feels ("+EMOTION+r") (.+?)\.\s*(?:how can i support (?:him|her|them)|what can i say)[?.!]*", text)
    if support:
        word = support[2].lower()
        return out('You could acknowledge that your '+support[1].lower()+' feels '+word+
                   ', and ask whether they want someone to listen or help thinking through a next step. '+
                   'For example: "I am here to listen. What would feel helpful right now?" Avoid assuming you know exactly how they feel.',
                   'support-other', emotional_terms=[word])
    if re.search(r'(?i)[.;!?]\s*(?:what|who|where|when|how|why|write|calculate|compute|solve|generate)\b', text) and not ADVICE.search(text):
        return None
    found = emotions(text)
    if not found and (LISTEN.search(text) or NO_QUESTIONS.search(text)):
        for previous in reversed(messages[-7:-1]):
            if previous.get('role') == 'user':
                found = emotions(previous['content'])
                break
        if found:
            return out('You do not have to turn this into a task or explain more than you want to. I can listen.',
                       'listening', emotional_terms=[w for w, _ in found])
    if not found:
        return None
    if QUESTION.search(text) and not ADVICE.search(text):
        return None
    listen, questions = preferences(messages, text)
    rng = random.Random(str(seed)+':'+text)
    words = [w for w, _ in found]
    categories = list(dict.fromkeys(c for _, c in found))
    named = ' and '.join(words[:2]) if len(words)<=2 else ', '.join(words[:-1])+' and '+words[-1]
    if len(categories)>1:
        lead = 'You described feeling '+named+'. '
        lead += ('Those feelings can coexist; you do not have to choose just one.' if
                 any(c in POSITIVE for c in categories) and any(c not in POSITIVE for c in categories)
                 else 'It sounds as though several feelings are arriving together.')
    else:
        lead = 'You mentioned feeling '+named+'. '+rng.choice(GROUPS[categories[0]][1])
    if listen:
        tail = 'You do not need to solve it right now or share more than you want to. I can listen.'
    elif ADVICE.search(text):
        tail = GROUPS[categories[-1]][3]
    elif questions:
        tail = GROUPS[categories[-1]][2]
        # Do not ask the same question after the user has already responded.
        if any(m.get('role')=='assistant' and tail in m.get('content','') for m in messages[-7:-1]):
            tail = 'Would it help to stay with that feeling, or think through a next step?'
    else:
        tail = 'You can take your time with this; there is no need to answer a question.'
    return out(lead+' '+tail, 'reflection', emotional_terms=words)
