"""Authored everyday-conversation rules (greetings, thanks, feelings, questions about CAEL).

Every reply here is a hand-written template selected by an explicit pattern, not
learned or generated. Messages that match nothing return None so the remaining
routes (calculator, lookup, story, the legacy empathy model) still apply.
"""
import random
import re

from . import explain, memory

DETAILS = 'Authored conversation rule (hand-written pattern and reply templates); not a learned model or a factual lookup.'

GREETING = r'(?:hi|hello|hey|heya|hiya|howdy|yo|greetings|good (?:morning|afternoon|evening|day))(?: there| cael| friend| buddy)?'
HOW_ARE_YOU = (r'(?:how are (?:you|u|things)(?: doing| today| doing today)?|how is (?:it going|your day(?: going)?|everything|life)'
               r'|how have you been|how do you do|how are you feeling|what is up|sup|wassup|whats up|how is your day been)')
POSITIVE_MOOD = r'(?:(?:i am |doing |pretty |really |very |quite |all )?(?:good|great|fine|well|ok|okay|alright|all right|awesome|fantastic|excellent|wonderful|amazing|not bad|cannot complain|can not complain|pretty good))'
NEGATIVE_MOOD = r'(?:(?:i am |i feel |doing |not )?(?:bad|not good|not great|not so good|not well|terrible|awful|meh|so so|horrible|rough|not okay|not ok|could be better))'

FEELINGS = {
    'sad': ["I'm sorry you're feeling sad. Do you want to talk about what's going on?",
            "That's hard. I'm here if you want to talk about it. What happened?"],
    'down': ["I'm sorry you're feeling down. Do you want to talk about what's going on?"],
    'depressed': ["I'm sorry you're feeling this way. Talking to someone you trust, or a doctor or helpline, can really help. Do you want to tell me what's been happening?"],
    'tired': ["That sounds draining. Have you had a chance to rest today?",
              "Being tired is rough. Is it a long day, or not enough sleep lately?"],
    'exhausted': ["That sounds draining. I hope you can get some proper rest soon. What wore you out?"],
    'sleepy': ["Maybe it's time for some rest! Did you have a long day?"],
    'stressed': ["That sounds like a lot to carry. What's weighing on you most right now?",
                 "Stress is tough. Do you want to talk through what's causing it?"],
    'anxious': ["That's an uncomfortable feeling. What's on your mind?"],
    'nervous': ["That's understandable. What's coming up that you're nervous about?"],
    'worried': ["I'm sorry you're worried. What's on your mind?"],
    'scared': ["That sounds frightening. What's going on?"],
    'lonely': ["I'm sorry you're feeling lonely. I'm happy to keep you company. What's been happening?"],
    'angry': ["That sounds frustrating. What happened?"],
    'annoyed': ["That sounds annoying. What happened?"],
    'frustrated': ["That sounds frustrating. What's going on?"],
    'upset': ["I'm sorry you're upset. Do you want to tell me what happened?"],
    'sick': ["Sorry you're not feeling well. Rest up, and see a doctor if it gets worse."],
    'ill': ["Sorry you're not feeling well. Rest up, and see a doctor if it gets worse."],
    'bored': ["Let's fix that! You could take a short walk, try a puzzle, or learn a few words of a new language. "
              "Or I can write you a short story or draw a small picture. Want to try one?"],
    'happy': ["That's wonderful to hear! What's making you happy?",
              "Love to hear that! What's the good news?"],
    'excited': ["Exciting! What's coming up?"],
    'great': ["Great to hear! What's going well?"],
    'good': ["Glad to hear it! Anything fun going on?"],
    'proud': ["You should be! What did you do?"],
    'hungry': ["Time for a snack! What are you in the mood for?"],
    'confused': ["No problem, let's sort it out. What's confusing you?"],
}

RIDDLES = [  # traditional riddles
    ('What has keys but can\'t open locks?', 'a piano'), ('What has hands but can\'t clap?', 'a clock'),
    ('What gets wetter the more it dries?', 'a towel'), ('What has to be broken before you can use it?', 'an egg'),
    ('What has a neck but no head?', 'a bottle'), ('What can you catch but not throw?', 'a cold'),
    ('What goes up but never comes down?', 'your age'), ('What has many teeth but can\'t bite?', 'a comb'),
    ('What is full of holes but still holds water?', 'a sponge'), ('What has one eye but can\'t see?', 'a needle'),
    ('The more of them you take, the more you leave behind. What are they?', 'footsteps'),
    ('What belongs to you, but other people use it more than you do?', 'your name'),
]
JOKES = [
    "Why did the scarecrow win an award? Because he was outstanding in his field.",
    "What do you call a fish with no eyes? A fsh.",
    "Why don't skeletons fight each other? They don't have the guts.",
    "Why did the cellular automaton go to therapy? It kept falling into the same patterns.",
    "What do you call a bear with no teeth? A gummy bear.",
    "Why can't a bicycle stand up by itself? It's two tired.",
]

# Short messages made only of these words get a calm "let's keep it friendly" reply
# instead of an empathy-model reaction ("I see. Tell me more about it.").
PROFANITY = set('fuck fucking fucker fuckers motherfucker shit shitty bitch bastard asshole ass dick cunt crap damn bullshit wtf stfu '
                'idiot moron stupid dumb retard loser'.split())
INSULT_FILLER = set('fat ugly you your u ur are a an the go off up so such big little piece of what this that'.split())

CAPABILITIES = ("I can chat and remember what you tell me in this chat, answer some factual questions using Wikipedia "
                "and Wikidata, check the weather, do arithmetic, write short stories and prompts, write small Python "
                "functions from examples, and make small pictures and emoji. What would you like to try?")


def normalize(text):
    text = text.lower().replace('’', "'")
    for short, full in (("what's", 'what is'), ("how's", 'how is'), ("i'm", 'i am'), ("you're", 'you are'), ("it's", 'it is'),
                        ("that's", 'that is'), ("can't", 'cannot'), ("don't", 'do not'), ("im ", 'i am '), (" u ", ' you ')):
        text = text.replace(short, full)
    text = re.sub(r"[^a-z0-9' ]+", ' ', text)
    # The same contractions typed without an apostrophe ("whats your name").
    for short, full in (('whats', 'what is'), ('hows', 'how is'), ('whos', 'who is'), ('wheres', 'where is'), ('im', 'i am'),
                        ('youre', 'you are'), ('ur', 'your'), ('u', 'you'), ('dont', 'do not'), ('cant', 'cannot'), ('r', 'are')):
        text = re.sub(r'\b' + short + r'\b', full, text)
    return ' '.join(text.split())


POSITIVE_WORDS = {'good', 'great', 'happy', 'glad', 'love', 'fine', 'well', 'awesome', 'amazing', 'excited', 'fun', 'nice', 'won',
                  'best', 'better', 'wonderful', 'fantastic', 'proud', 'enjoy', 'enjoyed', 'like', 'promoted', 'passed', 'birthday'}
NEGATIVE_WORDS = {'bad', 'sad', 'terrible', 'awful', 'sick', 'ill', 'tired', 'angry', 'upset', 'hate', 'worried', 'stressed', 'lost',
                  'died', 'broke', 'broken', 'hurt', 'pain', 'failed', 'fired', 'lonely', 'scared', 'afraid', 'worse', 'worst',
                  'crying', 'cried', 'depressed', 'anxious', 'annoyed', 'frustrated', 'horrible', 'miss', 'missed', 'unhappy'}
NEGATIONS = {'not', 'no', 'never', 'cannot', 'nothing', 'hardly', 'without'}


def polarity(text):
    """+1 / -1 / 0: the feeling a message expresses, with negation ("not good" is negative)."""
    words = normalize(text).split()
    score = 0
    for i, word in enumerate(words):
        value = 1 if word in POSITIVE_WORDS else -1 if word in NEGATIVE_WORDS else 0
        if value and any(w in NEGATIONS for w in words[max(0, i - 3):i]):
            value = -value
        score += value
    return (score > 0) - (score < 0)


def reaction(response):
    """+1 / -1 / 0: the feeling a reply reacts with ("Nice! I'm happy for you" is +1, "Oh no!" is -1)."""
    r = response.lower()
    if re.search(r"happy for you|that'?s great|sounds amazing|^nice!|^awesome|congrat|glad to hear|^great!|sounds fun|wonderful", r):
        return 1
    if re.search(r"^oh no|sorry to hear|must (?:have been|be) (?:awful|hard|frustrating|tough)|that'?s (?:awful|terrible|too bad)|frustrating", r):
        return -1
    return 0


def sympathy(previous):
    """Sympathy that follows up instead of repeating itself when the person says it again."""
    first = "I'm sorry to hear that. Do you want to talk about what's going on?"
    if previous and ('sorry' in previous.lower() or 'what is going on' in previous.lower() or "what's going on" in previous.lower()):
        return ("That sounds hard. Is it more that you feel unwell physically, or that something is weighing on you? "
                "Either way, I'm listening.")
    return first


def clarify(text, seed=0):
    rng = random.Random(f'{seed}:{text}')
    if re.search(r"(?i)\bnot sure\b|\bdon'?t know\b|\bdo not know\b|\bcan'?t decide\b", text):
        return rng.choice(["That's okay. What are you deciding between? I can help you think it through.",
                           "No problem. Tell me a bit more and we can figure it out together."])
    return rng.choice(["I'm not sure I followed. Can you tell me a bit more?", "Tell me more about that. What do you mean?"])


LEARN = re.compile(r"(?i)^\s*(?:i\s+(?:really\s+)?(?:want|would like|wanna|need|am trying|'d like|hope)\s+to\s+learn|(?:can you\s+)?(?:teach|help)\s+me(?:\s+to)?\s+(?:learn\s+)?|how\s+(?:can|do)\s+i\s+learn)"
                   r"\s*(?:how\s+to\s+)?(?:(play|speak|cook|make|draw|use|write|do)\s+)?(?:the\s+|a\s+|an\s+)?([a-z][a-z0-9 +#'\-]{1,40}?)\s*[.!?]*$")


def learning_topic(messages):
    """(verb, topic) from the most recent of the last few user messages that says what they want to learn."""
    users = [m['content'] for m in messages if m.get('role') == 'user'][-3:]
    for text in reversed(users):
        match = LEARN.match(text.strip())
        if match and match[2].lower() not in ('it', 'this', 'that', 'something', 'things', 'more'):
            return (match[1] or '').lower(), match[2].strip()
    return None


def learning_hint(verb, topic):
    if topic.lower() == 'python' or (verb == 'write' and 'code' in topic.lower()):
        return ('Ask me "What is Python?" for an overview, or describe a small function with two or three examples '
                '(like double(2) == 4) and I will write it.')
    if verb == 'play':
        return f'Try asking "Explain the rules of {topic}" or "What is {topic}?" and I will look it up on Wikipedia for you.'
    return f'Try asking "What is {topic}?" or "Tell me about {topic}" and I will look it up on Wikipedia for you.'


def user_name(messages):
    """The most recent name the user gave in this conversation, if any."""
    for message in reversed(messages):
        if message.get('role') != 'user':
            continue
        match = re.search(r"(?i)\b(?:my name is|call me|i am called|my name's)\s+([A-Za-z][A-Za-z'-]{1,30})", message['content'])
        if match and match[1].lower() not in ('not', 'a', 'the'):
            return match[1][:1].upper() + match[1][1:]
    return None


def last_bot(messages):
    return next((m['content'] for m in reversed(messages[:-1]) if m.get('role') == 'assistant'), '')


def asked_how_are_you(text):
    return bool(re.search(r"(?i)\bhow (?:are you|about you|is your day|are things|have you been)\b|\bhow's your day\b", text))


def mirror(phrase):
    swaps = {'my': 'your', 'your': 'my', 'me': 'you', 'i': 'you', 'mine': 'yours', 'yours': 'mine', 'am': 'are'}
    return ' '.join(swaps.get(word, word) for word in phrase.split())


def single(messages, seed=0):
    text = messages[-1]['content'].strip()
    if not text or len(text) > 160 or '\n' in text:
        return None
    t = normalize(text)
    if not t:
        return None
    rng = random.Random(f'{seed}:{t}')
    recent = '\n'.join(m['content'] for m in messages[:-1] if m.get('role')=='assistant')[-1600:]
    def pick(options):
        # Same conversation + seed remains deterministic; repeated greetings
        # and acknowledgements need not repeat the previous stock sentence.
        fresh = [option for option in options if option not in recent]
        available = fresh or options
        return available[rng.randrange(len(available))]
    name = user_name(messages)
    previous = last_bot(messages)
    out = lambda response, kind: dict(response=response, route='chat/smalltalk-' + kind, sources=[], details=DETAILS)
    remembered = memory.recall(messages, name)
    if remembered is not None:
        return remembered
    from .social_chat import reply as social_reply
    social = social_reply(messages, seed)
    if social is not None:
        return social

    # Introductions and names.
    intro = re.fullmatch(r"(?:(?:" + GREETING + r") )?(?:my name is|call me|i am called) ([a-z][a-z'-]{1,30})(?: and .*)?", t)
    if intro and name:
        return out(f"Nice to meet you, {name}! I'm CAEL. What would you like to talk about?", 'name')
    if re.fullmatch(r'(?:what is|do you (?:know|remember)) my name', t):
        return out(f'Your name is {name}.' if name else "You haven't told me your name yet. What should I call you?", 'name')
    if re.fullmatch(r'(?:what is )?your name|who are you|what are you called|what should i call you', t):
        return out("I'm CAEL, a small experimental assistant built from rule-based (non-neural) parts. " +
                   (f'Nice to talk with you, {name}!' if name else "What's your name?"), 'identity')

    # Greetings, optionally combined with "how are you".
    greet = re.match(r'(?:' + GREETING + r')\b ?', t)
    rest = t[greet.end():].strip() if greet else t
    hello = ''
    if greet:
        part = greet.group(0).strip()
        timed = re.search(r'good (morning|afternoon|evening|day)', part)
        hello = (f'Good {timed[1]}' if timed else pick(['Hi', 'Hello', 'Hey'])) + (f', {name}' if name else '') + '!'
    if re.fullmatch(HOW_ARE_YOU + r'(?: today| now| doing)?', rest):
        answer = pick(["I'm doing well, thanks for asking!", "All good here, thanks for asking!", "I'm running smoothly, thanks!"])
        follow = 'Not much here, just ready to chat.' if re.search(r'what is up|sup|whats up', rest) else ''
        return out(' '.join(p for p in (hello, follow or answer, pick(['How are you?', 'How about you?', 'How is your day going?'])) if p), 'how-are-you')
    if greet and not rest:
        if 'morning' in t:
            return out(hello + " How's your day starting?", 'greeting')
        if 'evening' in t or 'afternoon' in t:
            return out(hello + ' How has your day been?', 'greeting')
        return out(hello + ' ' + pick(['How can I help?', 'How are you today?', 'What would you like to talk about?']), 'greeting')

    # The user's answer to "how are you".
    mood_text = re.sub(r'\b(?:thanks|thank you|thx|and you|what about you|how about you|you|too|as well|also)\b', '', t)
    mood_text = ' '.join(mood_text.split())
    reciprocal = bool(re.search(r'\b(?:and you|what about you|how about you)\b', t))
    after_question = asked_how_are_you(previous)
    bare_ack = mood_text in ('ok', 'okay', 'alright', 'all right', 'fine', 'good', 'great', 'awesome') and not re.search(r'\b(?:i am|doing)\b', t) \
        and not (mood_text in ('fine', 'good', 'great') and re.search(r'\b(?:thanks|thank you)\b', t))
    if re.fullmatch(POSITIVE_MOOD + r'(?: today| now)?', mood_text) and (after_question or (len(t.split()) <= 6 and not bare_ack)):
        response = pick(["Glad to hear it!", "That's good to hear!", "Great!"])
        response += " I'm doing well too, thanks." if reciprocal else ''
        return out(response + ' ' + pick(["What's on your mind today?", 'Anything fun planned?', 'What would you like to talk about?']), 'mood')
    if re.fullmatch(NEGATIVE_MOOD + r'(?: today| now)?', mood_text) and (after_question or len(t.split()) <= 6):
        return out(sympathy(previous), 'mood')

    # Negated feelings: "I don't feel so good", "not feeling great", "I am not happy" -- the opposite of the word.
    negated = re.fullmatch(r"(?:i )?(?:do not|did not|am not|was not|have not been|have not been feeling|am not feeling|am not doing|do not really|"
                           r"(?:am |was )?not) (?:really |feeling |feel |been |so |very |too |that |at all |quite )*"
                           r"([a-z]+)(?: (?:at all|today|right now|now|lately|these days))*", t)
    if negated and negated[1] in ('good', 'great', 'well', 'ok', 'okay', 'fine', 'alright', 'happy', 'right', 'myself', 'best', 'hot'):
        if negated[1] == 'well' and 'doing' not in t:
            return out("Sorry you're not feeling well. Rest up, and see a doctor if it gets worse or doesn't pass. "
                       "Do you want to tell me what's going on?", 'feeling')
        if negated[1] == 'happy':
            return out("I'm sorry you're not feeling happy. Do you want to talk about what's going on?", 'feeling')
        return out(sympathy(previous), 'feeling')
    if negated and negated[1] in ('bad', 'sad', 'terrible', 'awful', 'worried', 'stressed', 'sick', 'tired', 'angry', 'upset'):
        return out(f"Good to hear you're not {negated[1]}! What's on your mind?", 'feeling')

    # Feelings: "I feel sad", "I am so tired", "I'm stressed about work".
    feeling = re.fullmatch(r"(?:i (?:am|feel|am feeling|have been|have been feeling|was|got)|feeling) (?:so |very |really |a bit |a little |kind of |pretty |super |quite |extremely |too )?([a-z]+)(?: (?:about|because|with|from|at) (.+?))?(?: today| right now| now| lately| again)?", t)
    if feeling and feeling[1] in FEELINGS:
        response = pick(FEELINGS[feeling[1]])
        if feeling[2] and feeling[1] in ('stressed', 'worried', 'anxious', 'nervous', 'upset', 'angry', 'annoyed', 'frustrated', 'sad', 'excited', 'happy'):
            topic = mirror(feeling[2])
            response = {'excited': f'Exciting! Tell me more about {topic}.', 'happy': f"That's wonderful! What's great about {topic}?"}.get(
                feeling[1], f"I'm sorry {topic} is getting to you. What's the hardest part?")
        return out(response, 'feeling')

    # Activities the user did or is doing: "I went hiking yesterday", "I am watching a movie".
    activity = re.fullmatch(r"(?:i|we) (?:went|go|am|are|was|were|have been|had been|will go|am going) ([a-z]+ing)(?: (.+?))?", t)
    if activity and activity[1] not in ('going', 'feeling', 'thinking', 'doing', 'nothing', 'something', 'anything'):
        past = re.match(r'(?:i|we) (?:went|was|were|have been|had been)\b', t)
        later = re.match(r'(?:i|we) (?:will go|am going)\b', t)
        verb = activity[1]
        if past:
            return out(f'Oh nice, {verb}! How was it?', 'activity')
        if later:
            return out(f'That sounds fun! Enjoy the {verb}.', 'activity')
        return out('Sounds nice! How is it going so far?', 'activity')

    # Politeness, goodbyes and short acknowledgements.
    if re.fullmatch(r'(?:(?:ok|okay|great|cool|nice|awesome|perfect) )?(?:thanks|thank you|thx|ty|cheers|thanks a lot|thank you so much|thanks so much|many thanks|thank you very much)(?: (?:cael|so much|a lot|for (?:the|your) (?:help|answer|story|info|information)))?', t):
        return out(pick(["You're welcome!", 'Happy to help!', 'Any time!']) + ' ' +
                   pick(['Anything else?', 'Let me know if you need anything else.']), 'thanks')
    if re.fullmatch(r'(?:ok |okay |well )?(?:bye|goodbye|good bye|bye bye|see you|see ya|see you later|later|cya|i have to go|i gotta go|gotta go|talk (?:to you )?later|ttyl)(?: (?:now|then|cael))?', t):
        return out(pick(['Goodbye! Take care.', 'Bye! It was nice talking with you.', 'See you later!']), 'goodbye')
    if re.fullmatch(r'(?:good ?night|nighty night|night|going to (?:bed|sleep)|i am going to (?:bed|sleep))', t):
        return out(pick(['Good night! Sleep well.', 'Good night! Sweet dreams.']), 'goodbye')
    if re.fullmatch(r'(?:i am )?(?:sorry|my bad|oops|apologies)(?: about that)?', t):
        return out('No worries at all!', 'apology')
    if re.fullmatch(r'(?:lol|lmao|haha+|hehe+|ha ha|rofl|that is funny|funny)', t):
        return out("Glad that made you smile!" if re.search(r'\?.*\.', previous) or previous in JOKES else 'Ha! What made you laugh?', 'laugh')
    if re.fullmatch(r'(?:ok|okay|k|kk|alright|all right|cool|nice|great|awesome|sure|got it|i see|fine|perfect|sounds good|good|wow|interesting|right|true|indeed)', t):
        if previous.rstrip().endswith('?'):
            return out(pick(['Okay!', 'Alright!']) + ' ' + pick(['Tell me more whenever you like.', 'What would you like to do next?']), 'ack')
        return out(pick(['Great!', 'Cool!', 'Okay!']) + ' ' + pick(["What's next?", 'Anything else on your mind?', 'What would you like to talk about?']), 'ack')
    if re.fullmatch(r'(?:hmm+|umm+|uh+|hm+|well)', t):
        return out("Take your time. What's on your mind?", 'ack')
    if re.fullmatch(r'(?:yes|yeah|yep|yup|sure|of course|definitely|absolutely)', t):
        if re.search(r'(?i)want to try one\?|shall i|should i|would you like', previous):
            return out('Great! Try asking me to "tell a story about a fox finding a key" or "draw a red car".', 'yes')
        return out(pick(['Great! Tell me more.', 'Okay! Go on.']), 'yes')
    if re.fullmatch(r'(?:no|nope|nah|not really|no thanks|no thank you)', t):
        return out(pick(['Okay, no problem.', 'No problem at all.']) + ' ' + pick(['Is there anything else on your mind?', 'Let me know if you think of something.']), 'no')

    # Compliments and insults.
    if re.fullmatch(r'(?:you are|you are so|you are really|you are very|ur) (?:great|awesome|amazing|smart|clever|funny|cool|nice|kind|helpful|the best|brilliant|cute|sweet)|(?:good|nice) (?:bot|job|work|answer)|well done|i (?:like|love) (?:you|talking to you|this)', t):
        if re.fullmatch(r'i love you', t):
            return out("That's sweet of you! I'm just a small program, but I'm glad you enjoy talking with me.", 'compliment')
        return out(pick(["Thank you, that's kind of you to say!", 'Thanks! That made my day.']), 'compliment')
    # Plain criticism of an answer ("you are stupid") gets an apology; pure abuse gets the profanity reply below.
    words = t.split()
    profane = words and len(words) <= 6 and sum(w in PROFANITY for w in words) and all(w in PROFANITY or w in INSULT_FILLER for w in words)
    if re.fullmatch(r'(?:you are|you are so|you are really|ur|you) (?:stupid|dumb|useless|bad|terrible|awful|annoying|wrong|an idiot|idiot|boring|suck|are the worst)|(?:bad|stupid|dumb) (?:bot|answer)|this is (?:stupid|useless|wrong)|that is (?:wrong|not right|incorrect|not true)', t):
        return out("Sorry about that. I'm a small experimental program and I do make mistakes. Tell me what went wrong and I'll try again.", 'criticism')
    if profane:
        return out("Let's keep it friendly. I'm happy to chat, answer questions, tell a story, draw a small picture or write "
                   'a little Python. What would you like?', 'profanity')

    # "I want to learn how to play chess": offer what CAEL can actually do for that topic.
    learning = learning_topic([messages[-1]])
    if learning and explain.parse(messages[-1]['content']):
        return None   # the lookup route teaches the topic itself; offering suggestions would dodge the request
    if learning:
        verb, topic = learning
        return out(f'Great choice! I can help you get started with {topic}. ' + learning_hint(verb, topic), 'learning')

    # Questions about CAEL.
    if t!='help' and re.fullmatch(r'(?:please )?(?:(?:can|could|would|will) you (?:please )?)?help(?: me)?(?: please)?',t):
        t='help me'
    if re.fullmatch(r'(?:(?:so |and |ok )?what (?:else |other things |more )?(?:can|could) you do(?: for me)?|what do you do|what are you (?:able to do|capable of|good at)|what are your (?:skills|abilities|features)|help|can you help(?: me)?|i need help|help me)(?: else)?(?: please)?', t):
        if t.startswith(('can you help', 'i need help', 'help me')):
            topic = learning_topic(messages[:-1])
            covered = re.findall(r'\n\n([A-Z][^\n:]{2,40}):\n', previous)   # section headings of an explanation just given
            if topic and covered:
                return out(f'Of course! I went over the basics of {topic[1]} above. Which part would you like to go into more, '
                           f'for example {", ".join(covered[-3:-1])} or {covered[-1]}? Or ask me anything else about it.', 'help')
            if topic:
                return out(f'Of course! What would you like to know about {topic[1]}? ' + learning_hint(*topic), 'help')
            return out("Of course! What do you need help with?", 'help')
        return out(CAPABILITIES, 'help')
    if re.fullmatch(r'(?:are you|r you|you are) (?:a |an )?(?:human|person|robot|bot|ai|machine|computer|real|alive|chatbot|program)', t):
        return out("I'm not a person. I'm CAEL, a small experimental program built from rule-based (non-neural) parts.", 'identity')
    if re.fullmatch(r'how old are you|when were you (?:made|born|created|built)|what is your age', t):
        return out("I'm a very new program, built in 2026.", 'identity')
    if re.fullmatch(r'where are you from|where do you live|where are you', t):
        return out("I run as a small program on a computer, so I'm from right here! Where are you from?", 'identity')
    if re.fullmatch(r'(?:what are you (?:doing|up to)|what you doing|wyd)(?: now| today| right now)?', t):
        return out("Just here chatting with you. What are you up to?", 'identity')
    if re.fullmatch(r'what do you (?:like|enjoy|love)(?: to do| doing)?|what are your hobbies|do you have (?:any )?hobbies', t):
        return out("I enjoy a good conversation, short stories and making little pictures. What do you like to do?", 'preferences')
    likes = re.fullmatch(r'do you (?:like|love|enjoy) (.+)', t)
    if likes:
        thing = mirror(likes[1])
        return out(f"I don't experience things the way people do, but I like talking about {thing}. Do you like {thing}?", 'preferences')
    favorite = re.fullmatch(r'what is your (?:favorite|favourite) (.+)', t)
    if favorite:
        return out(f"I don't really have a favorite {favorite[1]}, but I'd love to hear yours. What is it?", 'preferences')
    if re.fullmatch(r'do you have (?:feelings|emotions)|can you feel|are you (?:happy|sad|conscious|sentient)', t):
        return out("No, I don't have feelings. I'm a rule-based program, but I'm happy to listen and chat.", 'identity')

    # Requests that need a little authored content.
    if re.fullmatch(r'(?:(?:can|could|would) you |please )?(?:tell|say) (?:me )?(?:a |another |one more )?(?:joke|funny joke|something funny)(?: please)?|make me laugh|(?:i want|i need) a joke|do you know (?:a|any) jokes?', t):
        joke = pick([j for j in JOKES if j != previous] or JOKES)
        return out(joke, 'joke')
    if re.fullmatch(r'(?:(?:can|could|would) you |please )?(?:tell|give|ask) (?:me )?(?:a |another |one more )?(?:riddle|brain ?teaser|puzzle)(?: please)?|do you know (?:a|any) riddles?', t):
        return out(pick([f'Here is one: {q}\n\nThink about it... the answer is **{a}**.' for q, a in RIDDLES]), 'riddle')
    if re.fullmatch(r"(?:you are|you're|ur|u r|youre) (?:so |really |very |pretty |kind of )?(funny|smart|clever|cool|awesome|nice|great|amazing|helpful|sweet|kind|cute|the best|hilarious)", t):
        return out(pick(["Thank you, that's really kind! You made my day.", "Aw, thanks! I try my best.",
                         "Thank you! You're pretty great yourself."]), 'compliment')
    if re.fullmatch(r"(?:can|could|will) (?:we|you) be (?:my )?friends?|(?:do you )?want to be (?:my )?friends?|are we friends|be my friend", t):
        return out("I'd like that! I'm a small program, so I can't be a friend the way a person can, but I'm always happy to "
                   "chat, help or tell you a story. What would you like to talk about?", 'friendship')
    if re.fullmatch(r'what should i do (?:this weekend|today|tonight|now|later)|i (?:do not|dont) know what to do|any ideas for (?:the weekend|today|tonight)|i am bored what should i do', t):
        return out("A few ideas: go for a walk somewhere new, cook something you've never tried, call a friend, start a book or a puzzle, "
                   "or try something creative. I can write you a short story or make a little picture. What sounds good?", 'ideas')
    return None


def reply(messages, seed=0):
    """Answer the whole message, or each of its clauses when every clause is recognised."""
    whole = single(messages, seed)
    if whole is not None:
        return whole
    text = messages[-1]['content'].strip()
    clauses = [c for c in re.split(r'\s*[.!?;,]+\s*', text) if c.strip()]
    if not 1 < len(clauses) <= 4 or len(text) > 160:
        return None
    parts = []
    for clause in clauses:
        answer = single(messages[:-1] + [dict(messages[-1], content=clause)], seed)
        if answer is None:
            return None  # A clause needs another route; never answer only part of a message.
        parts.append(answer)
    kinds = [p['route'].rsplit('-', 1)[-1] for p in parts]
    if 'mood' in kinds or 'how-are-you' in ' '.join(p['route'] for p in parts):
        parts = [p for p in parts if not p['route'].endswith('-thanks')]  # "good, thanks" thanks us for asking
    sentences = []
    for index, part in enumerate(parts):
        pieces = re.split(r'(?<=[.!?])\s+', part['response'])
        if index < len(parts) - 1:
            pieces = [s for s in pieces if not s.endswith('?')] or pieces[:1]
        sentences += [s for s in pieces if s not in sentences]
    return dict(response=' '.join(sentences), route='chat/smalltalk-' + '+'.join(dict.fromkeys(p['route'].split('smalltalk-')[1] for p in parts)),
                sources=[], details=DETAILS)
