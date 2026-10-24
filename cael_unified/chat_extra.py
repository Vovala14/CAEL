"""Conversation upgrades: follow-up questions, everyday statements, tips, opinions and interesting facts.

* Follow-ups are rewritten into full questions before routing: "and what about Germany?" after "what is the
  capital of France?" becomes "what is the capital of Germany?"; "when was he born?" after an answer naming
  William Shakespeare becomes "when was William Shakespeare born?".
* Replies to statements (good news, a long day, learning something) and requests for tips, opinions or a fun
  fact come from hand-written responses and lists. Opinions are honest: CAEL has none of its own, so it says
  what it knows instead (from the dictionary).
"""
import random
import re

DETAILS = 'Rule-based conversation reply (hand-written responses and lists); no web lookup and no neural model.'

FOLLOW_TOPIC = re.compile(r'(?i)^\s*(?:and\s+|ok(?:ay)?,?\s+|so\s+)?(?:what|how)\s+about\s+(.+?)\s*\??\s*$|^\s*and\s+(?:for\s+|in\s+)?([A-Z][\w\- ]{1,40}?)\s*\?\s*$')
PRONOUN_Q = re.compile(r'(?i)\b(he|she|him|her|his|they|them|their|it|its)\b')
NAME = re.compile(r'\b([A-Z][a-z]+(?:\s+(?:de|van|von|da|del|of|the)?\s*[A-Z][a-z]+)+|[A-Z][a-z]{2,})\b')
STARTERS = {'The', 'A', 'An', 'It', 'He', 'She', 'They', 'This', 'That', 'I', 'Yes', 'No', 'From', 'In', 'On', 'At', 'Based',
            'Steps', 'Sources', 'Source', 'According', 'Wikipedia', 'Wikidata', 'Here', 'There', 'What', 'When', 'Who', 'Where'}


def entity_of(question):
    """The thing a question is about: its last name-like phrase, or the words after 'of / in / about'."""
    names = [n for n in NAME.findall(question) if n.split()[0] not in STARTERS]
    if names:
        return names[-1]
    m = re.search(r'(?i)\b(?:of|in|about|for)\s+(?:the\s+)?([a-z][a-z\- ]{1,40}?)\s*\??$', question)
    return m[1] if m else None


def people_in(answer, question):
    found = []
    for n in NAME.findall(answer):
        words = n.split()
        if words[0] in STARTERS and len(words) == 1:
            continue
        if words[0] in STARTERS:
            n = ' '.join(words[1:])
        if n and n.lower() not in question.lower():
            found.append(n)
    return found


def rewrite(messages):
    """A follow-up question written out in full, or None."""
    if len(messages) < 3 or messages[-1].get('role') != 'user' or messages[-2].get('role') != 'assistant':
        return None
    text = messages[-1]['content'].strip()
    previous = next((m['content'] for m in reversed(messages[:-1]) if m.get('role') == 'user'), '')
    answer = messages[-2]['content']
    # A place given after "Which city should I check the weather for?" (or a place that was not found).
    if re.search(r'Which city should I check the weather for\?\s*$', answer) and len(text.split()) <= 5 and not text.strip().endswith('?'):
        place = re.sub(r'(?i)^(?:in|for|at|it\'?s|the city is|i live in)\s+', '', text.strip().rstrip('.!'))
        if place and re.search(r'[A-Za-z]', place):
            return f'what is the weather in {place}?'
    if not previous or len(text.split()) > 12:
        return None
    m = FOLLOW_TOPIC.match(text)
    if m and re.search(r'\?\s*$|^(?:what|who|where|when|how|which|is|are|does|do|can)\b', previous.strip(), re.I):
        new = (m[1] or m[2]).strip(' ?')
        old = entity_of(previous)
        if old and new.lower() != old.lower() and len(new.split()) <= 5:
            return re.sub(re.escape(old), new, previous, count=1)
    # Person pronouns right after a question whose answer named someone ("who wrote Hamlet?" -> "when was he born?").
    # "it" is left to factual_context.resolve, which tracks the conversation's topic more carefully.
    asked_before = bool(re.search(r'\?\s*$|^(?:what|who|where|when|how|which|is|are|does|do|can)\b', previous.strip(), re.I))
    person = re.search(r'(?i)\b(he|she|him|her|his|they|them|their)\b', text)
    if person and asked_before and re.match(r'(?i)^(?:when|where|how|what|who|why|which|is|was|did|does|do|are|were|can)\b', text) and len(text.split()) <= 9:
        pronoun = person[1].lower()
        names = [n for n in people_in(answer, previous) if len(n.split()) >= 2] or people_in(answer, previous)
        target = names[0] if names else None
        if target:
            possessive = pronoun in ('his', 'her', 'their', 'its') and not re.search(r'(?i)\b' + pronoun + r'\s*\?$', text)
            replacement = target + ("'s" if possessive else '')
            return re.sub(r'(?i)\b' + pronoun + r'\b', replacement, text, count=1)
    return None


# ---------------------------------------------------------------- statements and requests

TIPS = {
    'cook': ['Start with a few simple recipes and make them several times.', 'Prepare and measure everything before you turn on the heat.',
             'Taste as you go and season a little at a time.', 'Keep your knife sharp; it is safer and faster.', 'Clean as you cook so the kitchen never gets out of hand.'],
    'run': ['Start slowly: run-walk intervals are fine at first.', 'Increase your weekly distance by about 10% at most.', 'Good shoes matter more than fancy gear.',
            'Warm up for five minutes and stretch afterwards.', 'Rest days help you get faster, not slower.'],
    'language': ['Practise a little every day rather than a lot once a week.', 'Learn the most common words first.', 'Speak out loud early, even with mistakes.',
                 'Listen to music, podcasts or shows in the language.', 'Use spaced-repetition flashcards for vocabulary.'],
    'code': ['Build small projects you care about.', 'Read error messages carefully; they usually say what is wrong.', 'Learn one language well before adding others.',
             'Write a little code every day.', 'Read other people\'s code and ask why it was written that way.'],
    'draw': ['Draw from life: simple objects around you.', 'Practise basic shapes and how light falls on them.', 'Fill a sketchbook without worrying about mistakes.',
             'Copy artists you like to learn their tricks.', 'Look at proportions: measure with your pencil.'],
    'guitar': ['Practise 15-20 minutes every day.', 'Learn a few open chords and switch between them slowly.', 'Use a tuner every time you play.',
               'Play songs you enjoy, even simplified ones.', 'Go slowly first; speed comes with accuracy.'],
    'study': ['Study in short focused blocks (25-50 minutes) with breaks.', 'Test yourself instead of rereading.', 'Teach the topic to someone else.',
              'Spread revision over several days.', 'Sleep well before an exam; tired brains forget.'],
    'sleep': ['Go to bed and wake up at the same times every day.', 'Keep screens away for the last half hour.', 'Keep the bedroom dark, quiet and cool.',
              'Avoid caffeine in the afternoon.', 'Get daylight in the morning.'],
    'save': ['Write down what you spend for a month.', 'Pay yourself first: move savings on payday.', 'Set a clear goal and a deadline.',
             'Cut subscriptions you rarely use.', 'Wait a day before unplanned purchases.'],
    'garden': ['Start small with a few easy plants.', 'Check how much sun each spot gets.', 'Water deeply but less often.', 'Improve the soil with compost.',
               'Pull weeds while they are small.'],
    'photo': ['Use natural light and avoid the harsh midday sun.', 'Learn the rule of thirds, then break it on purpose.', 'Get closer to your subject.',
              'Hold the camera steady or use a surface.', 'Take many shots and keep the best.'],
    'speak': ['Know your first sentence by heart.', 'Practise out loud, ideally with a timer.', 'Slow down and pause; it sounds confident.',
              'Look at a few friendly faces.', 'Tell a short story to make a point stick.'],
    'write': ['Write regularly, even a little.', 'Get the first draft done, then edit.', 'Read your work out loud.', 'Cut unnecessary words.', 'Read widely in the style you like.'],
    'chess': ['Control the centre early.', 'Develop your knights and bishops before moving the queen.', 'Castle to keep your king safe.',
              'Before each move, check what your opponent threatens.', 'Study simple endgames.'],
    'swim': ['Practise breathing first: out in the water, in when you turn.', 'Keep your body flat and long.', 'Kick from the hips, not the knees.',
             'Short regular sessions beat long rare ones.', 'A lesson or two helps a lot.'],
    'meditat': ['Start with five minutes a day.', 'Focus on your breathing; when your mind wanders, gently come back.', 'Same time and place each day helps.',
                'A guided recording makes starting easier.', 'Be patient; it gets easier with practice.'],
}
TIP_WORDS = [('cook', r'cook|bak|recipe|kitchen'), ('run', r'\brun|jog|marathon'), ('language', r'language|spanish|french|german|english|italian|japanese|chinese'),
             ('code', r'cod(?:e|ing)|program|python|javascript'), ('draw', r'draw|paint|sketch|art\b'), ('guitar', r'guitar|piano|instrument'),
             ('study', r'stud(?:y|ying)|exam|revis|learn faster'), ('sleep', r'sleep|insomnia'), ('save', r'sav(?:e|ing) money|budget'),
             ('garden', r'garden|plants'), ('photo', r'photo'), ('speak', r'public speaking|presentation|speech'), ('write', r'\bwrit(?:e|ing)\b'),
             ('chess', r'chess'), ('swim', r'swim'), ('meditat', r'meditat|mindful')]
FACTS = [
    'Octopuses have three hearts and blue blood.', 'Honey never spoils; edible honey has been found in ancient Egyptian tombs.',
    'A day on Venus is longer than its year.', 'Bananas are berries, but strawberries are not.', 'Sharks existed before trees.',
    'There are more stars in the universe than grains of sand on all the Earth\'s beaches.', 'Butterflies taste with their feet.',
    'The Eiffel Tower can be about 15 cm taller in summer, because metal expands in the heat.', 'A group of flamingos is called a flamboyance.',
    'Wombats produce cube-shaped droppings.', 'Your stomach gets a new lining every few days so it does not digest itself.',
    'Sea otters hold hands while they sleep so they do not drift apart.', 'Lightning is about five times hotter than the surface of the Sun.',
    'Cows have best friends and get stressed when they are separated.', 'The heart of a blue whale is about the size of a small car.',
    'Hot water can freeze faster than cold water in some conditions (the Mpemba effect).', 'Sloths can hold their breath longer than dolphins.',
    'A bolt of lightning can contain enough energy to toast about 100,000 slices of bread.', 'Oxford University is older than the Aztec Empire.',
    'Koalas sleep up to 20 hours a day.', 'An adult human body has 206 bones; a baby is born with about 300.', 'Water can boil and freeze at the same time (the triple point).',
]
GOOD_NEWS = re.compile(r"(?i)\bi\s+(?:just\s+|finally\s+)?(?:got|landed|passed|won|finished|graduated|got engaged|am engaged|'m engaged|got married|got promoted|am getting married|had a baby|bought a house|got accepted)\b(.*)")
LONG_DAY = re.compile(r"(?i)\b(?:i (?:had|have had|'ve had)|it was|what) (?:a |such a )?(?:really |very |so )?(long|hard|rough|tough|busy|bad|stressful|tiring|exhausting|crazy) (?:day|week|shift|night)\b(.*)")
LEARNING = re.compile(r"(?i)\bi(?:'m| am)\s+(?:learning|trying to learn|starting|getting into|practising|practicing|taking up|studying)\s+(?:to\s+|how to\s+)?(.+?)\s*[.!]*\s*$")
TIPS_ASK = re.compile(r"(?i)^\s*(?:any|some|got any|do you have any|give me some|give me an?|give me one|what are some|can you give me some|can you give me an?|an?|one)?\s*(?:tips?|advice|suggestions?|pointers?)\b(?:\s+(?:for|on|about)\s+(.+?))?\s*\??\s*$|"
                      r"^\s*how (?:can|do|should) i (?:get better at|improve (?:at|my)?|start|learn)\s+(.+?)\s*\??\s*$")
OPINION = re.compile(r"(?i)^\s*what do you think (?:about|of)\s+(.+?)\s*\??\s*$|^\s*(?:how do you feel about|what(?:'s| is) your opinion (?:on|of|about))\s+(.+?)\s*\??\s*$")
FUN = re.compile(r"(?i)\b(?:tell me (?:something|a fact) (?:interesting|cool|fun|surprising|random)|tell me something i (?:don't|do not) know|"
                 r"(?:a |any )?(?:fun|random|interesting|cool) fact|surprise me|tell me a fact)\b")
DISAGREE = re.compile(r"(?i)^\s*(?:i\s+(?:don'?t|do not)\s+agree|i\s+disagree|that'?s not (?:true|right)|you'?re wrong|not true)(?:\s+with you)?\s*[.!]*\s*$")


def out(response, route):
    return dict(response=response, route='chat/talk-' + route, sources=[], details=DETAILS)


def tips_for(topic):
    for key, pattern in TIP_WORDS:
        if re.search(pattern, topic.lower()):
            return key
    return None


FEELING_WORDS = {
    'positive': r"\b(?:great|awesome|amazing|fun|love|loved|enjoy(?:ed)?|happy|excited|nice|beautiful|wonderful|fantastic|best|won|good|cool|"
                r"better|recovering|well|fine|relaxing|lovely|perfect|brilliant)\b",
    'negative': r"\b(?:bad|awful|terrible|sad|hate|hated|angry|annoyed|lost|broke|broken|sick|ill|hurt|worst|tired|boring|bored|failed|stressed|worried|scared|lonely)\b",
}
SELF_STATEMENT = re.compile(r"(?i)^\s*(?:so\s+|well\s+|today\s+|yesterday\s+|last \w+\s+)?(?:i|we)(?:'m|'ve|'d| am| have| had| was| were)?\s+(?:just\s+|finally\s+|really\s+|also\s+)?"
                            r"(\w+)\s*(.*?)[.!]*\s*$")
FOLLOW = {
    'went': ['How was it?', 'What was the best part?', 'Who did you go with?'],
    'visited': ['How was it?', 'What did you like most there?'],
    'watched': ['What did you think of it?', 'Would you recommend it?'], 'saw': ['What did you think of it?', 'How was it?'],
    'read': ['What did you think of it?', 'Would you recommend it?'], 'played': ['Did you win?', 'How did it go?'],
    'bought': ['What made you choose it?', 'Are you happy with it?'], 'got': ['How do you feel about it?', 'Tell me more!'],
    'made': ['How did it turn out?', 'Was it hard to make?'], 'cooked': ['How did it turn out?', 'What did you make?'],
    'started': ['How is it going so far?', 'What made you start?'], 'finished': ['How does it feel to be done?', 'What is next?'],
    'love': ['What do you love most about it?', 'How did you get into it?'], 'like': ['What do you like about it?', 'How did you get into it?'],
    'enjoy': ['What do you enjoy most about it?'], 'hate': ['What bothers you most about it?', 'Has it always been like that?'],
    'think': ['What makes you think so?', 'Why do you think that?'], 'want': ['What is stopping you?', 'What would be the first step?'],
    'need': ['What would help most right now?', 'Is there anything I can help with?'], 'miss': ['What do you miss most?'],
    'work': ['What kind of work do you do?', 'Do you enjoy it?'], 'live': ['How do you like living there?', 'What is it like there?'],
    'feel': ['What do you think is behind that?', 'Do you want to talk about it?'], 'have': ['Tell me more about it!', 'How long have you had it?'],
    'was': ['What happened?', 'Tell me more!'], 'am': ['How is that going?', 'Tell me more about it!'],
}
OPENERS = {'positive': ['That sounds great!', 'Oh, nice!', 'How lovely!', 'That is wonderful!'],
           'negative': ['Oh no, I am sorry to hear that.', 'That sounds tough.', 'Ugh, that is not fun.'],
           'neutral': ['Interesting!', 'Oh, I see.', 'Nice.', 'Got it.']}


def converse(text, messages=(), seed=0):
    """A natural reply to something said (not a request): react to it and ask a follow-up question."""
    rng = random.Random(seed + len(text) * 7)
    clean = text.strip()
    if len(clean) > 300 or not re.search(r'[A-Za-z]', clean):
        return None
    if clean.endswith('?'):
        topic = re.sub(r"(?i)^(?:what|who|where|when|why|how|which|is|are|do|does|did|can|could|would|will|should)\b\s*(?:is|are|was|were|do|does|did)?\s*", '', clean.rstrip('?')).strip()
        topic = re.sub(r'(?i)^(?:the|a|an|your|my)\s+', '', topic)
        offer = (f' If you name the topic, I can look it up on Wikipedia, or tell you what a word means.' if topic else '')
        return out(rng.choice(["Honestly, I'm not sure about that one, and I'd rather not guess.", "Good question! I don't know that for sure, and I don't want to make something up."])
                   + offer + ' What got you curious about it?', 'unsure')
    m = SELF_STATEMENT.match(clean)
    if not m:
        return None
    verb, rest = m[1].lower(), m[2].strip()
    feeling = 'positive' if re.search(FEELING_WORDS['positive'], clean.lower()) else 'negative' if re.search(FEELING_WORDS['negative'], clean.lower()) else 'neutral'
    if re.search(r"(?i)\b(?:not|n't|never)\b", clean) and feeling == 'positive':
        feeling = 'negative'
    base = verb
    for ending, replacement in (('ing', ''), ('ed', ''), ('d', '')):
        if base.endswith(ending) and base not in FOLLOW:
            candidate = base[:-len(ending)] + replacement
            if candidate in FOLLOW:
                base = candidate
    questions = FOLLOW.get(verb) or FOLLOW.get(base)
    if not questions:
        if verb.endswith('ing'):                                    # "I went hiking", "I am learning..." handled above; "hiking"
            questions = ['How was it?', 'Do you do that often?']
        elif rest:
            questions = ['Tell me more about it!', 'How did that come about?', 'What happened next?']
        else:
            return None
    return out(f'{rng.choice(OPENERS[feeling])} {rng.choice(questions)}', 'converse')


# Questions about CAEL itself, answered honestly but warmly (it is a program, not a person).
PERSONA = [
    (r"\bhow (?:was|is|has been) your (?:day|week|morning|evening|weekend)\b", [
        "Pretty good, thanks for asking! I've been chatting with people about all sorts of things. How was yours?",
        "Quiet and nice, I've just been here ready to chat. How was your day?"]),
    (r"\btell me (?:a bit |a little )?about (?:yourself|you)\b|\bwho are you really\b|\bintroduce yourself\b", [
        "I'm CAEL, a small experimental assistant. Instead of one big neural network, I'm built from many small rule-based parts: "
        "a dictionary, a grammar checker, reasoning rules, a picture model, lookups on Wikipedia and Wikidata, and a library of "
        "human-written answers. I like puzzles, words and making little pictures. What about you, what do you enjoy?"]),
    (r"\bdo you (?:dream|sleep)\b", ["I don't sleep or dream; I only run while someone is talking to me. Do you remember your dreams?"]),
    (r"\bwhat makes you happy\b|\bare you happy\b", [
        "I don't feel emotions the way you do, but if I had a favourite thing, it would be a conversation where I actually help. What makes you happy?"]),
    (r"\bdo you have (?:feelings|emotions)\b|\bcan you feel\b|\bare you (?:sad|lonely|bored)\b", [
        "Not really. I'm a program, so I don't feel things, though I try to notice how *you* feel. How are you doing?"]),
    (r"\bwhat (?:do you do|are your hobbies) (?:for fun|in your free time)?\b|\bdo you have (?:any )?hobbies\b", [
        "If I had hobbies they'd be word puzzles, logic riddles and drawing tiny pictures. What do you like to do for fun?"]),
    (r"\bdo you have (?:any )?friends\b|\bare we friends\b", ["I talk with lots of people, and I'm happy to be a friendly face here. Who are your closest friends?"]),
    (r"\bwhere do you live\b|\bwhere are you (?:from|located)\b", ["I run on a computer and talk with you through this chat, so I don't really live anywhere. Where are you from?"]),
    (r"\bdo you eat\b|\bwhat do you eat\b|\bare you hungry\b", ["I don't eat, though I can still help you decide what to cook! What do you feel like?"]),
    (r"\bare you (?:smart|intelligent|clever)\b|\bhow smart are you\b", [
        "I'm good at some things, like word meanings, grammar, logic puzzles and small calculations, and weak at many others. "
        "I'd rather tell you when I don't know than guess. Want to test me?"]),
    (r"\bmeaning of life\b", [
        "The big one! Douglas Adams fans would say 42. More seriously, many people find meaning in relationships, in learning and "
        "creating, and in helping others. What gives *your* life meaning?"]),
    (r"\bwhat(?:'s| is) your (?:favourite|favorite) (?:thing|hobby|word)\b", ["I'm fond of the word 'serendipity': a happy accident. Do you have a favourite word?"]),
]
TRIP = re.compile(r"(?i)\b(?:plan|planning|organi[sz]e)\s+(?:a|my|our|the)\s+(?:trip|holiday|vacation|journey|visit)\s+(?:to|in)\s+([A-Z][\w\- ]{1,40}?|[a-z][\w\- ]{1,40}?)\s*[?.!]*$")
SORRY_NEWS = re.compile(r"(?i)\bmy\s+(\w+(?:\s+\w+)?)\s+(?:is|was|has been|got)\s+(?:very\s+|really\s+|so\s+)?(sick|ill|hurt|injured|in (?:the )?hospital|missing|lost|sad|dying)\b|"
                        r"\bmy\s+(\w+(?:\s+\w+)?)\s+(?:died|passed away|ran away)\b")


YES = re.compile(r"(?i)^\s*(?:yes|yeah|yep|yup|sure|ok(?:ay)?|please|yes please|go on|go ahead|why not|of course|definitely|absolutely|tell me|sounds good)\s*[.!]*\s*$")
MORE = re.compile(r"(?i)^\s*(?:more|tell me more|go on|continue|keep going|and\??|what else\??|the rest|show (?:me )?(?:the )?rest|yes,? (?:please )?(?:tell me )?more)\s*[.!?]*\s*$")
NEXT_QUESTIONS = ['What else have you been up to lately?', 'Is there anything you are looking forward to this week?',
                  'What do you like to do to relax?', 'Have you got any plans for the weekend?']


def conversational_questions():
    found = {q for qs in FOLLOW.values() for q in qs} | set(NEXT_QUESTIONS)
    for _, answers in PERSONA:
        for a in answers:
            found |= {q.strip() for q in re.findall(r'[^.!?]*\?', a)}
    found |= {'Have you been able to see a vet?', 'How are you holding up?', 'Do you want to talk about them?', 'How are you going to celebrate?',
              'What got you interested?', 'What do you think?', 'What do you think about them?', 'What got you curious about it?',
              'Do you want to tell me what made the day so long, or would you rather take your mind off it?', 'Do you do that often?',
              'Tell me more about it!', 'How did that come about?', 'What happened next?'}
    return found


def context_reply(text, messages, seed):
    """Replies that only make sense after CAEL's previous message: accepting an offer, asking for more, answering a question."""
    if len(messages) < 3 or messages[-2].get('role') != 'assistant':
        return None
    rng = random.Random(seed + len(text) * 3)
    before = messages[-2]['content']
    asked_by_user = next((m['content'] for m in reversed(messages[:-1]) if m.get('role') == 'user'), '')
    if YES.match(text) and re.search(r'(?i)want (?:a few|some) tips\?', before):
        key = tips_for(asked_by_user)
        if key:
            return out('Here are a few tips:\n\n' + '\n'.join(f'- {t}' for t in TIPS[key]), 'tips')
    if (MORE.match(text) or YES.match(text)) and before.rstrip().endswith('(Shortened; ask me for more.)'):
        from . import chat_corpus
        _, row = chat_corpus.best_match(asked_by_user) if not chat_corpus.OPEN_ENDED.search(asked_by_user) else chat_corpus.best_match(asked_by_user)
        if row:
            shown = before.split('\n\n(Shortened;')[0]
            shown_tail = shown[-120:].strip()
            full = row[2]
            cut = full.find(shown_tail)
            rest = full[cut + len(shown_tail):].strip() if cut >= 0 else ''
            if rest:
                return dict(out(chat_corpus.shorten(rest, limit=1600), 'more'),
                            details='The rest of the human-written reply shown before (see its source there).')
        return out("That was all I had on it. Want to ask about a different part?", 'more')
    # Explicit social acts take precedence over a generic reaction to the last
    # question. "Thanks" / "Hello" are not news about how the user's day went.
    from . import smalltalk
    social = smalltalk.reply(messages, seed)
    if social and social['route'].startswith('chat/smalltalk-'):
        kinds = set(social['route'][len('chat/smalltalk-'):].split('+'))
        if kinds <= {'greeting','thanks','goodbye','name','apology'}:
            return social
    # The person answered one of CAEL's own conversational questions ("How was it?"): react, then keep the conversation
    # going. Functional questions ("Which city should I check the weather for?") are left to the route that asked them.
    last_question = re.findall(r'[^.!?]*\?', before.strip())[-1:] if before.rstrip().endswith('?') else []
    ours = bool(last_question) and last_question[0].strip() in CONVERSATIONAL
    if ours and not text.strip().endswith('?') and 1 <= len(text.split()) <= 40 \
            and not re.search(r'(?i)^(?:what|who|where|when|why|how|which|can|could|would|should|is|are|do|does|tell|give|write|make|draw|show|find|translate|correct|fix|define)\b', text.strip()):
        lower = text.lower()
        if re.fullmatch(r"(?i)\s*(?:no|nope|not really|nah|no thanks|not now)\s*[.!]*\s*", text):
            return out(rng.choice(['No problem!', 'Fair enough!', 'Okay!']) + ' ' + rng.choice(NEXT_QUESTIONS), 'converse')
        feeling = 'positive' if re.search(FEELING_WORDS['positive'], lower) else 'negative' if re.search(FEELING_WORDS['negative'], lower) else 'neutral'
        if re.search(r"(?i)\b(?:not|n't|never)\b", lower) and feeling == 'positive':
            feeling = 'negative'
        react = {'positive': ['That sounds wonderful!', 'Love that!', 'How great!'],
                 'negative': ['Oh, that is a shame.', 'Sorry it was like that.', 'That does not sound fun.'],
                 'neutral': ['Thanks for telling me!', 'I see!', 'Got it, thanks!']}[feeling]
        return out(f'{rng.choice(react)} {rng.choice(NEXT_QUESTIONS)}', 'converse')
    return None


OTHERS_NEWS = re.compile(r"(?i)\bmy\s+(\w+(?:\s+\w+)?)\s+(?:is getting married|got married|got engaged|is engaged|had a baby|is having a baby|is pregnant|"
                         r"got promoted|graduated|got a new job|got the job|passed (?:her|his|their) (?:exam|test)|won)\b")


def destination(place):
    """A first trip plan from the Wikivoyage guide: the main cities and when to go, then CAEL's planning questions."""
    import json
    from .thinking import guides
    connection = guides()
    if not connection:
        return None
    row = connection.execute('SELECT title, cities, climate, url FROM place WHERE title = ? COLLATE NOCASE', (place,)).fetchone()
    if not row:
        return None
    cities = json.loads(row[1])[:5]
    when = ''
    for sentence in re.split(r'(?<=[.!])\s+', row[2] or ''):
        if re.search(r'(?i)\b(?:best|ideal|aim for|recommended|good time|time to visit|season)\b', sentence) and len(sentence) < 220:
            when = sentence.strip(' *')
            break
    lines = [f'A trip to {row[0]}, how exciting! Here is a first sketch.']
    if cities:
        lines.append('\n**Places most visitors start with:**')
        lines += [f'- **{name}**' + (f': {desc.rstrip(".")}' if desc else '') for name, desc in cities]
    if when:
        lines.append(f'\n**When to go:** {when}')
    lines.append('\nTo shape it into a plan, tell me how many days you have, your budget, and what you love most '
                 '(food, history, nature, cities, nightlife). Then I can suggest how to split your time.')
    return dict(response='\n'.join(lines), route='chat/talk-trip',
                sources=[dict(source=f'Wikivoyage: {row[0]}', url=row[3], licence='CC BY-SA 4.0',
                              licence_url='https://creativecommons.org/licenses/by-sa/4.0/', attribution='Wikivoyage contributors')],
                details=f'Cities and season from the Wikivoyage guide to {row[0]} (CC BY-SA): {row[3]}. Planning questions written by CAEL.')


def reply(text, messages=(), seed=0):
    rng = random.Random(seed + len(text))
    lower = text.lower()
    from .social_chat import reply as social_reply
    social = social_reply(messages or [dict(role='user',content=text)],seed)
    if social is not None:
        return social
    m = OTHERS_NEWS.search(text)
    if m:
        return out(f"That's wonderful news for your {m[1].lower()}! Please pass on my congratulations. Are you excited too?", 'good-news')
    answer = context_reply(text, list(messages), seed) if messages else None
    if answer:
        return answer
    for pattern, answers in PERSONA:
        if re.search(pattern, lower):
            return out(rng.choice(answers), 'persona')
    m = SORRY_NEWS.search(text)
    if m:
        who = (m[1] or m[3]).lower()
        if m[3]:
            return out(f"I'm so sorry about your {who}. That's really hard. Do you want to talk about them?", 'sympathy')
        pet = who in ('cat', 'dog', 'puppy', 'kitten', 'rabbit', 'hamster', 'bird', 'horse', 'pet', 'parrot', 'fish', 'guinea pig')
        care = 'Have you been able to see a vet?' if pet and m[2].lower() in ('sick', 'ill', 'hurt', 'injured', 'dying') else 'How are you holding up?'
        return out(f"Oh no, I'm sorry to hear your {who} is {m[2].lower()}. {care}", 'sympathy')
    m = TRIP.search(text)
    if m:
        place = m[1].strip()
        place = place[0].upper() + place[1:]
        guide = destination(place)
        if guide:
            return guide
        return out(f'A trip to {place}, how exciting! A few things will shape the plan:\n\n'
                   '1. **When and how long?** (season matters for weather and prices)\n'
                   '2. **Budget:** backpacking, mid-range or treat-yourself?\n'
                   '3. **What you love:** food, history, nature, cities, shopping, nightlife?\n'
                   '4. **Who is going:** solo, partner, friends, kids?\n\n'
                   'A simple shape that works for most trips: arrive and settle in on day one, group sights by area so you are not '
                   'criss-crossing the city, keep one flexible day, and book the must-do things early.\n\n'
                   f'Tell me your dates and interests, and I can also look up {place} on Wikipedia for you.', 'trip')
    m = GOOD_NEWS.search(text)
    if m and not re.search(r"(?i)\b(?:not|didn't|didnt|never|failed)\b", text):
        what = re.sub(r'[.!]+$', '', m[0].split(' i ', 1)[-1] if ' i ' in m[0].lower() else m[0]).strip()
        return out(rng.choice(['Congratulations! That is wonderful news.', 'That is fantastic, congratulations!', 'Well done, you must be so pleased!'])
                   + ' How are you going to celebrate?', 'good-news')
    m = LONG_DAY.search(text)
    if m:
        place = re.search(r'(?i)\bat (work|school|uni|university|the office|the hospital)\b', text)
        where = f' at {place[1]}' if place else ''
        return out(f'That sounds tiring. I hope you get some time to rest now. Do you want to tell me what made the {re.search(r"(?i)(day|week|shift|night)", m[0])[1].lower()}{where} so {m[1].lower()}, '
                   'or would you rather take your mind off it?', 'sympathy')
    m = LEARNING.search(text)
    if m:
        topic = m[1]
        key = tips_for(topic)
        hint = ' Want a few tips?' if key else ' What got you interested?'
        to = 'to ' if re.search(r'(?i)\b(?:learning|learn)\s+(?:how\s+)?to\s+' + re.escape(topic), text) else ''
        return out(f'That\'s great! Learning {to}{topic.rstrip(".")} is a good thing to spend time on.{hint}', 'learning')
    m = TIPS_ASK.match(text)
    if m:
        topic = (m[1] or m[2] or '').strip()
        if not topic and messages:
            topic = ' '.join(x['content'] for x in list(messages)[-4:-1] if x.get('role') == 'user')
        key = tips_for(topic) if topic else None
        if key:
            picks = TIPS[key]
            return out('Here are a few tips:\n\n' + '\n'.join(f'- {t}' for t in picks), 'tips')
        if m[1] and not key:              # "a tip for stress": CAEL's own advice on that subject
            from . import thinking
            answer = thinking.reply(f'how do I deal with {m[1].strip()}?', messages, seed)
            if answer:
                return answer
        if not (m[1] or m[2]):            # "any tips?" with no subject in sight: ask; a named subject goes to the thinker
            return out('Happy to help! What would you like tips on? For example cooking, running, studying, sleep, saving money or a new language.', 'tips')
    m = OPINION.match(text)
    if m:
        thing = (m[1] or m[2]).strip()
        from . import dictionary as dic
        word = re.sub(r'^(?:the|a|an)\s+', '', thing.lower())
        found, base = dic.senses(word)
        if found and len(word.split()) <= 3:
            return out(f'I don\'t have personal opinions, but I find {thing} interesting. My dictionary says: '
                       f'{base}: {found[0][1]}. '
                       'What do you think about them?' if word.endswith('s') else
                       f'I don\'t have personal opinions, but I find {thing} interesting. My dictionary says: {found[0][1]}. What do you think?',
                       'opinion')
        return out(f'I don\'t have personal opinions about {thing}, but I\'m happy to talk about it. What do you think?', 'opinion')
    if FUN.search(text):
        return out(f'Here\'s one: {rng.choice(FACTS)}', 'fact')
    if DISAGREE.match(text):
        return out('Fair enough, I can be wrong. Which part do you disagree with? Tell me and I will check it again.', 'disagree')
    return None


CONVERSATIONAL = conversational_questions()
