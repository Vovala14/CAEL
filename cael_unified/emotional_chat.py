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
    text = text.replace('’', "'").replace('—', ', ').replace('–', '-').strip()
    # "burned out" and "burned-out" are the same feeling word (John6666 forum report, 0.3.8).
    return re.sub(r"(?i)\b(burn(?:ed|t)|worn|fed|left|stressed|freaked|tired|maxed|wiped|stretched)\s+(out|up|thin)\b",
                  lambda m: m[1]+'-'+m[2] if (m[1]+'-'+m[2]).lower() in WORDS else m[0], text)


# ---- Conversation constraints (0.3.8) ------------------------------------------------------------
# A request such as "Please do not give me advice or ask questions" is read clause by clause: a
# negator scopes over everything after it in its clause, so it distributes over coordinated objects
# ("advice or questions", "advise me, quiz me or ask me anything"). "but", "however", "instead",
# "though" and sentence punctuation close the scope. A positive request only counts outside a
# negated scope, so "do not give me advice" never reads as "give me advice".
NEGATOR = re.compile(r"(?i)\b(?:(?:please )?(?:do not|don't|dont)(?! (?:know|think|understand|remember|feel|mind|matter|worry|care|get)\b)|"
                     r"(?:does not|doesn't) (?:have|need) to|"
                     r"(?:no|nor|never|without|stop|quit|avoid|skip|spare me(?: the)?|hold off(?: on)?|refrain from)"
                     r"(?= (?:more |further |any |the |unsolicited |giving |asking |offering |telling |suggesting |trying |with |me )*"
                     r"(?:advi[cs]\w*|questions?|ask\w*|tips?|suggest\w*|solutions?|solv\w*|fix\w*|lectur\w*|quiz\w*|recommend\w*|tell\w* me what|follow[- ]ups?|prob\w*|help\w*))|"
                     r"not (?:looking|here|asking) for|not after|not interested in|no need (?:for|to)|rather you didn't|rather not)\b")
SCOPE_BREAK = re.compile(r"(?i)[.;!?\n]|\b(?:but|however|instead|though|although|except|rather than)\b|\b(?:and|so|because) (?=i\b)|"
                         r",(?!\s*(?:or|and|nor|no|any|advice|questions?|tips|suggestions|solutions|ask\w*|quiz\w*|lectur\w*|fix\w*|solv\w*|recommend\w*|tell me|advise\w*|try\w*)\b)")
ADVICE_OBJECT = re.compile(r"(?i)\b(?:advice|advise|advising|suggest\w*|tips?|solutions?|solv\w*|fix(?:ing|es)?|recommend\w*|"
                           r"tell(?:ing)? me what (?:to|i should) do|lectur\w*|problem[- ]solving|coping strateg\w+|strateg\w+|"
                           r"(?:try|trying) to help|steps? to take|next steps?|what (?:to|i should) do)\b")
QUESTION_OBJECT = re.compile(r"(?i)\b(?:questions?|ask(?:s|ed|ing)?|quiz\w*|interrogat\w*|follow[- ]ups?|prob(?:e|ing)|pry\w*)\b")
ADVICE_REQUEST = re.compile(r"(?i)\b(?:what (?:can|should|could) i do|what do i do|how (?:can|do|should) i (?:cope|handle|deal|manage|fix|get through)|"
                            r"(?:give|offer|share|have|got)(?: me)?(?: some| any| a few)? (?:advice|tips|suggestions|ideas)|"
                            r"(?:i (?:want|need|would like|'d like)|looking for|any|some) (?:some )?(?:advice|tips|suggestions)|"
                            r"advice,? please|tell me what (?:to|i should) do|help me (?:cope|handle|deal|figure)|"
                            r"what would you (?:do|suggest|recommend)|(?:do|can|could) you (?:suggest|recommend|advise))\b")
QUESTIONS_OK = re.compile(r"(?i)\b(?:(?:you can|you may|feel free to|it's (?:ok|okay|fine) to|go ahead and) ask(?: me)?(?: questions| anything)?|"
                          r"questions are (?:ok|okay|fine|welcome)|ask me anything)\b")
LISTEN_ONLY = re.compile(r"(?i)\b(?:just (?:listen|needed to say it|want(?:ed)? to vent|need(?:ed)? to vent|want(?:ed)? to be heard|need(?:ed)? to talk)|"
                         r"(?:only|simply) listen|(?:need|want) (?:you|someone) to (?:just )?listen|hear me out|let me vent|"
                         r"(?:i )?(?:just )?(?:need|want) to (?:vent|rant))\b")


TOPICS = {'burnout': 'overwhelmed', 'overwhelm': 'overwhelmed', 'stress': 'overwhelmed', 'anxiety': 'anxious', 'worry': 'anxious',
          'worries': 'anxious', 'nerves': 'anxious', 'sadness': 'sad', 'grief': 'sad', 'heartbreak': 'sad', 'loneliness': 'lonely',
          'isolation': 'lonely', 'anger': 'angry', 'frustration': 'angry', 'shame': 'embarrassed', 'guilt': 'embarrassed',
          'exhaustion': 'tired', 'fatigue': 'tired', 'tiredness': 'tired'}
TOPIC = re.compile(r"(?i)\b(?:on|about|for|with|dealing with|handle|handling|cope with|coping with|manage|managing)\s+(?:my\s+|the\s+|this\s+)?("
                   + '|'.join(TOPICS) + r")\b")


def _segments(text):
    return [part for part in SCOPE_BREAK.split(normalize(text)) if part and part.strip()]


def constraints(text):
    """{'no_advice', 'no_questions', 'wants_advice', 'questions_ok', 'listen'} flags stated in one message."""
    found = dict(no_advice=False, no_questions=False, wants_advice=False, questions_ok=False, listen=False)
    for segment in _segments(text):                 # in order: a later clause overrides an earlier one
        negated = NEGATOR.search(segment)
        cut = negated.start() if negated else len(segment)
        before, scoped = segment[:cut], segment[cut:]
        if negated and ADVICE_OBJECT.search(scoped):
            found.update(no_advice=True, wants_advice=False, listen=True)
        if negated and QUESTION_OBJECT.search(scoped):
            found.update(no_questions=True, questions_ok=False)
        if ADVICE_REQUEST.search(before):
            found.update(wants_advice=True, no_advice=False, listen=False)
        if QUESTIONS_OK.search(before):
            found.update(questions_ok=True, no_questions=False)
        if LISTEN_ONLY.search(segment) and not found['wants_advice']:
            found['listen'] = True
    return found


def wants_advice(text):
    """A positive advice request that is not inside a negated scope."""
    return constraints(text)['wants_advice']


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


def preferences(messages, current=None):
    """(listen, questions_allowed) from this conversation; a later explicit request overrides an earlier one."""
    listen, questions = False, True
    for message in messages[-30:]:
        if message.get('role') != 'user':
            continue
        stated = constraints(message.get('content', ''))
        if stated['listen']:
            listen = True
        if stated['wants_advice']:
            listen = False
        if stated['no_questions']:
            questions = False
        if stated['questions_ok']:
            questions = True
    return listen, questions


def drop_questions(response):
    """The response without its own question sentences (used when the user asked for no questions)."""
    if '?' not in response or '```' in response:
        return response
    sentences = re.split(r'(?<=[.!?])\s+', response.strip())
    kept = [s for s in sentences if not s.rstrip(' )"\'').endswith('?')]
    text = ' '.join(kept).strip()
    return text if text else 'I am here, and I am listening.'


def enforce(messages, answer):
    """Honour a stated no-questions request on every conversational route, not only this one."""
    if not isinstance(answer, dict) or not isinstance(answer.get('response'), str) or '?' not in answer['response']:
        return answer
    route = answer.get('route', '')
    if not route.startswith('chat/') or route in ('chat/format-clarify',):
        return answer
    if not isinstance(messages, list) or not all(isinstance(m, dict) for m in messages):
        return answer
    if preferences(messages)[1]:
        return answer
    fixed = drop_questions(answer['response'])
    if fixed == answer['response']:
        return answer
    return dict(answer, response=fixed, constraint='no-questions')


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
    asked_advice = wants_advice(text)
    if re.search(r'(?i)[.;!?]\s*(?:what|who|where|when|how|why|write|calculate|compute|solve|generate)\b', text) and not asked_advice:
        return None
    found = emotions(text)
    stated = constraints(text)
    if not found and asked_advice and len(text) <= 200:
        # "I changed my mind, can you give me some advice?" after a stated feeling: advice about that feeling.
        for previous in reversed(messages[-7:-1]):
            if previous.get('role') == 'user':
                earlier = emotions(previous['content'])
                if earlier:
                    category = earlier[-1][1]
                    return out('Since you asked: '+GROUPS[category][3], 'reflection', emotional_terms=[w for w, _ in earlier])
                break
        topic = TOPIC.search(text)
        if topic:                                    # "Please give me some advice on burnout."
            category = next(c for word, c in TOPICS.items() if topic[1].lower().startswith(word))
            return out('Since you asked: '+GROUPS[category][3], 'reflection', emotional_terms=[topic[1].lower()])
    if not found and (stated['listen'] or stated['no_questions'] or LISTEN.search(text) or NO_QUESTIONS.search(text)):
        for previous in reversed(messages[-7:-1]):
            if previous.get('role') == 'user':
                found = emotions(previous['content'])
                break
        if found:
            return out('You do not have to turn this into a task or explain more than you want to. I can listen.',
                       'listening', emotional_terms=[w for w, _ in found])
    if not found:
        return None
    if QUESTION.search(text) and not asked_advice:
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
    elif asked_advice:
        tail = GROUPS[categories[-1]][3]
    elif questions:
        tail = GROUPS[categories[-1]][2]
        # Do not ask the same question after the user has already responded.
        if any(m.get('role')=='assistant' and tail in m.get('content','') for m in messages[-7:-1]):
            tail = 'Would it help to stay with that feeling, or think through a next step?'
    else:
        tail = 'You can take your time with this; there is no need to answer a question.'
    response = lead+' '+tail
    if not questions and '?' in response:          # backstop: a stated no-questions request always wins
        response = lead+' You can take your time with this; there is no need to answer a question.'
    return out(response, 'reflection', emotional_terms=words)
