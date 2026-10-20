"""Everyday chat requests the other routes got wrong: the clock, planning a day, meal and book ideas,
translating common phrases, short poems and a few well-known distances.

Everything here is rule-based. Suggestions and phrases come from short hand-written lists and say so; the
time is this computer's clock; a phrase or figure that is not in the lists is never guessed.
"""
from datetime import datetime
import random
import re

from . import phrases

DETAILS = 'Rule-based everyday reply from short hand-written lists (no web lookup, no neural model).'


def out(response, route, details=DETAILS):
    return dict(response=response, route='chat/everyday-' + route, sources=[], details=details)


# Clock ------------------------------------------------------------------------------------------
TIME_ASK = re.compile(r"(?i)^\s*(?:(?:what(?:'s| is) the (?:current )?time|what time is it|tell me the time|do you know (?:what )?(?:the )?time(?: it is)?)"
                      r"(?: now| right now)?|time\??)\s*(?:please)?\s*[?.!]*\s*$")
DATE_ASK = re.compile(r"(?i)^\s*(?:what(?:'s| is) (?:the |today'?s )?date(?: today)?|what day is (?:it|today)(?: today)?|what is today|which day is it|today'?s date)"
                      r"\s*(?:please)?\s*[?.!]*\s*$")


def clock(text, now=None):
    now = now or datetime.now().astimezone()
    offset = now.strftime('%z')
    zone = f'UTC{offset[:3]}:{offset[3:]}' if offset else 'local time'
    if TIME_ASK.match(text):
        return out(f'It is {now.strftime("%H:%M")} ({zone}) on this computer\'s clock, {now.strftime("%A %d %B %Y").replace(" 0", " ")}.',
                   'time', 'Read from the clock of the computer CAEL runs on; your own time zone may differ.')
    if DATE_ASK.match(text):
        return out(f'Today is {now.strftime("%A %d %B %Y").replace(" 0", " ")} (this computer\'s clock, {zone}).',
                   'date', 'Read from the clock of the computer CAEL runs on; your own time zone may differ.')
    return None


# Planning ---------------------------------------------------------------------------------------
PLAN_ASK = re.compile(r'(?i)\b(?:help me |can you help me |could you help me |let\'?s )?(?:plan|organi[sz]e|schedule|structure)\s+(?:my|the|a|our)\s+'
                      r'(day|morning|afternoon|evening|week|weekend|today|tomorrow)\b')
TASK_LIST = re.compile(r'(?i)(?:i (?:need|have|want) to|tasks?:|to ?do:)\s*(.+)$')


def plan(text):
    match = PLAN_ASK.search(text)
    if not match:
        return None
    span = match[1].lower()
    tasks = TASK_LIST.search(text)
    if tasks:
        items = [t.strip(' .') for t in re.split(r',|;|\band\b|\n', tasks[1]) if t.strip(' .')]
        if items:
            slots = ['9:00', '10:30', '12:00 (lunch first)', '13:30', '15:00', '16:30', '18:00']
            lines = [f'- **{slots[i] if i < len(slots) else "later"}:** {item}' for i, item in enumerate(items[:7])]
            return out(f'Here is a simple plan for your {span}, hardest task first while energy is high:\n\n' + '\n'.join(lines)
                       + '\n\nLeave 10-minute breaks between blocks. Want me to move anything to a fixed time?', 'plan')
    return out(f"Sure, let's plan your {span}. Tell me:\n\n"
               '1. The things you need to get done (and any with a fixed time, like a meeting).\n'
               '2. When you start and when you want to finish.\n'
               '3. Which task matters most.\n\n'
               'A simple shape that works for many people: the most important task first, short breaks every hour or so, '
               'small errands grouped together after lunch, and 10 minutes at the end to set up tomorrow.', 'plan')


# Suggestions ------------------------------------------------------------------------------------
DINNER = ['a vegetable stir-fry with rice or noodles (about 20 minutes)', 'pasta with tomato sauce, garlic and whatever greens you have',
          'tacos or wraps with beans, chicken or fish', 'a big omelette or frittata with cheese and vegetables',
          'a quick soup: onion, carrot, lentils and stock, simmered for 25 minutes', 'baked potatoes or sweet potatoes with toppings',
          'a grain bowl: rice, a protein, raw vegetables and a simple dressing', 'homemade pizza on flatbread']
BOOKS = [('To Kill a Mockingbird', 'Harper Lee', 'classic fiction'), ('The Hobbit', 'J. R. R. Tolkien', 'fantasy adventure'),
         ('Project Hail Mary', 'Andy Weir', 'science fiction'), ('Sapiens', 'Yuval Noah Harari', 'history, non-fiction'),
         ('1984', 'George Orwell', 'classic dystopia'), ('The Martian', 'Andy Weir', 'science fiction'),
         ('Pride and Prejudice', 'Jane Austen', 'classic romance'), ('Atomic Habits', 'James Clear', 'self-improvement'),
         ('The Name of the Wind', 'Patrick Rothfuss', 'fantasy'), ('Educated', 'Tara Westover', 'memoir')]
MOVIES = [('The Shawshank Redemption', 'drama'), ('Spirited Away', 'animation'), ('Inception', 'science fiction thriller'),
          ('Paddington 2', 'family comedy'), ('The Grand Budapest Hotel', 'comedy'), ('Interstellar', 'science fiction'),
          ('Toy Story', 'animation'), ('Knives Out', 'mystery')]
SUGGEST = re.compile(r'(?i)\b(?:what should i (?:eat|cook|make|have)|(?:suggest|recommend)\w*|any (?:ideas|suggestions)|give me (?:an? |some )?(?:ideas?|suggestions?)'
                     r'|what (?:book|movie|film)s? should i|ideas? for|i don\'?t know what to (?:eat|cook|read|watch))\b')


def suggest(text, seed=0):
    if not SUGGEST.search(text):
        return None
    lower = text.lower()
    rng = random.Random(seed)
    if re.search(r'\b(?:dinner|lunch|supper|eat|cook|meal|food)\b', lower):
        ideas = rng.sample(DINNER, 3)
        return out('A few easy ideas:\n\n' + '\n'.join(f'- {i[0].upper() + i[1:]}' for i in ideas)
                   + '\n\nTell me what you have in the fridge, or any diet you follow, and I can narrow it down.', 'suggest',
                   'Ideas from a short hand-written list, not a personalised recommendation.')
    if re.search(r'\b(?:book|novel|read)\b', lower):
        picks = rng.sample(BOOKS, 3)
        return out('Some widely loved books:\n\n' + '\n'.join(f'- *{t}* by {a} ({g})' for t, a, g in picks)
                   + '\n\nWhat kinds of books do you usually enjoy? I can suggest others in that style.', 'suggest',
                   'Picks from a short hand-written list of popular books, not a personalised recommendation.')
    if re.search(r'\b(?:movie|film|watch)\b', lower):
        picks = rng.sample(MOVIES, 3)
        return out('Some popular films:\n\n' + '\n'.join(f'- *{t}* ({g})' for t, g in picks)
                   + '\n\nWhat mood are you in? Funny, exciting or something calm?', 'suggest',
                   'Picks from a short hand-written list of popular films, not a personalised recommendation.')
    return None


# Translation ------------------------------------------------------------------------------------
TRANSLATE = re.compile(r"(?i)^\s*(?:(?:please |can you |could you )?translate\s+[\"']?(.+?)[\"']?\s+(?:in)?to\s+([a-z]+(?: [a-z]+)?)"
                       r"|how (?:do (?:you|i)|to|would you|can i) say\s+[\"']?(.+?)[\"']?\s+in\s+([a-z]+(?: [a-z]+)?)"
                       r"|what(?:'s| is)\s+[\"']?(.+?)[\"']?\s+in\s+([a-z]+(?: [a-z]+)?))\s*[?.!]*\s*$")
ALL_LANGUAGES = re.compile(r"(?i)^\s*(?:(?:say|translate)\s+[\"']?(.+?)[\"']?\s+in\s+(?:all|every|many|different|other) (?:the )?languages"
                           r"|how (?:do (?:you|i)|to) say\s+[\"']?(.+?)[\"']?\s+in\s+(?:all|every|many|different|other) (?:the )?languages)\s*[?.!]*\s*$")
MEANING = re.compile(r"(?i)^\s*(?:what does\s+[\"']?(.+?)[\"']?\s+mean(?: in english)?|what(?:'s| is) the meaning of\s+[\"']?(.+?)[\"']?"
                     r"|translate\s+[\"']?(.+?)[\"']?\s+(?:in)?to english)\s*[?.!]*\s*$")
LANGUAGE_LIST = re.compile(r'(?i)\b(?:what|which) languages (?:do you|can you) (?:know|speak|translate)|\bhow many languages\b')
TRANSLATE_DETAILS = 'From a hand-written table of common phrases in about 55 languages; no translation model or web lookup was used.'


def covered():
    return sorted(name.title() for name in phrases.TABLE if name != 'english')


def translate(text):
    if LANGUAGE_LIST.search(text):
        names = covered()
        return out(f'I know about {len(phrases.PHRASES)} common phrases (greetings, thanks, yes/no, sorry and a few words) in '
                   f'{len(names)} languages: {", ".join(names)}.', 'translate-list', TRANSLATE_DETAILS)
    match = ALL_LANGUAGES.match(text)
    if match:
        key = phrases.phrase(match[1] or match[2])
        if key is None:
            return None
        rows = [f'- **{lang.title()}:** {table[key]}' for lang, table in sorted(phrases.TABLE.items()) if key in table and lang != 'english']
        return out(f'"{key}" in {len(rows)} languages:\n\n' + '\n'.join(rows), 'translate-all', TRANSLATE_DETAILS)
    match = MEANING.match(text)
    if match:
        word = match[1] or match[2] or match[3]
        found = phrases.meaning(word)
        if not found:
            return None if match[1] or match[2] else out(f'"{word}" is not in my phrase table, so I would rather not guess what it means.',
                                                         'translate-unknown', TRANSLATE_DETAILS)
        senses = {}
        for lang, english in found:
            senses.setdefault(english, []).append(lang.title())
        parts = [f'"{english}" in {", ".join(langs[:6])}{" and others" if len(langs) > 6 else ""}' for english, langs in senses.items()]
        return out(f'"{word}" means ' + '; or '.join(parts) + '.', 'translate-meaning', TRANSLATE_DETAILS)
    match = TRANSLATE.match(text)
    if not match:
        return None
    said, name = next((match[i], match[i + 1]) for i in (1, 3, 5) if match[i])
    lang = phrases.language(name)
    key = phrases.phrase(said)
    if lang is None:
        # "what is X in Y" is usually not about languages at all ("what is 5 in binary"); stay out of it.
        if match[5] or name.lower() in ('python', 'math', 'numbers', 'total', 'words', 'binary', 'celsius', 'fahrenheit', 'km', 'miles'):
            return None
        return out(f'{name.title()} is not among the {len(covered())} languages in my phrase table, so I would rather not guess. '
                   'Ask "which languages do you know?" for the list.', 'translate-unknown', TRANSLATE_DETAILS)
    if key is None:
        if match[5]:
            return None
        return out(f'"{said}" is not in my short phrase list, so I would rather not guess a {lang.title()} translation. '
                   f'I know: {", ".join(phrases.PHRASES)}.', 'translate-unknown', TRANSLATE_DETAILS)
    word = phrases.TABLE[lang].get(key)
    if word is None:
        return out(f'I do not have "{key}" in {lang.title()} in my table, so I would rather not guess.', 'translate-unknown',
                   TRANSLATE_DETAILS)
    return out(f'"{said.strip()}" in {lang.title()} is **{word}**.', 'translate', TRANSLATE_DETAILS)


# Poems ------------------------------------------------------------------------------------------
POEM_ASK = re.compile(r'(?i)\b(?:write|compose|make|give)\b.{0,20}\b(?:poem|haiku|rhyme|verse)\b(?:.*?\b(?:about|on|for)\s+(?:a |an |the |my )?([a-z][a-z \-]{1,30}?))?\s*[?.!]*\s*$')
FEELING = {
    'rain': ('soft', 'grey', 'falls', 'window', 'rooftops'), 'sun': ('warm', 'golden', 'rises', 'morning', 'fields'),
    'sea': ('deep', 'blue', 'rolls', 'harbour', 'shore'), 'ocean': ('deep', 'blue', 'rolls', 'harbour', 'shore'),
    'snow': ('quiet', 'white', 'drifts', 'garden', 'hills'), 'night': ('still', 'dark', 'settles', 'window', 'streets'),
    'moon': ('pale', 'silver', 'climbs', 'window', 'trees'), 'cat': ('sleek', 'curious', 'wanders', 'doorway', 'walls'),
    'dog': ('loyal', 'happy', 'bounds', 'doorway', 'park'), 'love': ('gentle', 'bright', 'grows', 'heart', 'days'),
    'autumn': ('crisp', 'amber', 'falls', 'garden', 'paths'), 'spring': ('fresh', 'green', 'wakes', 'garden', 'hedges'),
    'coffee': ('dark', 'warm', 'steams', 'kitchen', 'mornings'), 'friendship': ('steady', 'kind', 'stays', 'heart', 'years'),
}
POEMS = [
    ('The {topic} {verb} {adj} and slow,\n{Adj2} on the {place} below.\nIt asks for nothing, only stays,\n'
     'and fills the {plural} of quiet days.'),
    ('{Adj} {topic}, you come again,\nto the {place}, through the lane.\nYou {verb_base} and pass, but leave behind\n'
     'a {adj2} calm upon the mind.'),
    ('Over the {plural} the {topic} {verb},\n{adj} as a lullaby the evening learns.\nI watch from the {place} and let it be:\n'
     'a {adj2} small world, just the {topic} and me.'),
]


def poem(text, seed=0):
    match = POEM_ASK.search(text)
    if not match:
        return None
    topic = (match[1] or 'the evening').strip().lower()
    topic = re.sub(r'^(?:the|a|an|my)\s+', '', topic)
    adj, adj2, verb, place, plural = FEELING.get(topic, ('quiet', 'gentle', 'waits', 'window', 'hours'))
    template = random.Random(seed).choice(POEMS)
    verb_base = {'falls': 'fall', 'rises': 'rise', 'rolls': 'roll', 'drifts': 'drift', 'settles': 'settle', 'climbs': 'climb',
                 'wanders': 'wander', 'bounds': 'bound', 'grows': 'grow', 'wakes': 'wake', 'steams': 'steam', 'stays': 'stay',
                 'waits': 'wait'}.get(verb, verb)
    lines = template.format(topic=topic, Topic=topic.title(), adj=adj, Adj=adj.title(), adj2=adj2, Adj2=adj2.title(),
                            verb=verb, verb_base=verb_base, place=place, plural=plural)
    return out(f'*{topic.title()}*\n\n{lines}\n\n(A short poem from my verse patterns. Ask again for a different one.)', 'poem',
               'Written by filling hand-written verse patterns with words that suit the topic; not a language model.')


# Figures ----------------------------------------------------------------------------------------
FIGURES = [
    (r'\bhow far (?:away )?is the moon\b|\bdistance (?:to|from \w+ to) the moon\b', 'The Moon is about **384,400 km** (238,900 miles) from Earth on average.'),
    (r'\bhow far (?:away )?is the sun\b|\bdistance (?:to|from \w+ to) the sun\b', 'The Sun is about **149.6 million km** (93 million miles) from Earth on average: one astronomical unit.'),
    (r'\bhow far (?:away )?is mars\b', 'Mars is between about **55 million km** and **400 million km** from Earth, depending on where both planets are in their orbits.'),
    (r'\bhow (?:big|large) is (?:the )?earth\b|\bcircumference of (?:the )?earth\b', 'Earth is about **12,742 km** across, and about **40,075 km** around the equator.'),
    (r'\bhow tall is (?:mount )?everest\b|\bheight of (?:mount )?everest\b', 'Mount Everest is **8,849 m** (29,032 ft) tall, by the 2020 survey.'),
    (r'\bhow fast is (?:the speed of )?light\b|\bspeed of light\b', 'Light travels at **299,792 km per second** in a vacuum.'),
    (r'\bhow fast is (?:the speed of )?sound\b|\bspeed of sound\b', 'Sound travels at about **343 m per second** in air at 20 °C.'),
    (r'\bhow old is the (?:earth|planet)\b|\bage of the earth\b', 'Earth is about **4.54 billion years** old.'),
    (r'\bhow old is the universe\b|\bage of the universe\b', 'The universe is about **13.8 billion years** old.'),
    (r'\bhow many (?:days are )?(?:days )?in a (?:leap )?year\b', 'A year has **365 days**, or **366** in a leap year.'),
    (r'\bboiling point of water\b|\bat what temperature does water boil\b', 'Water boils at **100 °C** (212 °F) at sea-level pressure.'),
]


def figure(text):
    lower = text.lower()
    for pattern, answer in FIGURES:
        if re.search(pattern, lower):
            return out(answer, 'figure', 'A standard reference figure from a short hand-written list.')
    return None


def reply(text, seed=0):
    for handler in (clock, translate, figure, plan, poem):
        answer = handler(text)
        if answer is not None:
            return answer
    return suggest(text, seed)
