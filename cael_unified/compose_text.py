"""Everyday writing: one-sentence summaries, short emails, name ideas, simple explanations and comparisons.

All non-neural: summaries pick the sentence that carries the most of the text's content words and resolve its
pronouns from the opening sentence; emails fill written templates with the details the request gives; names
combine words related to the business from WordNet with naming patterns; explanations and comparisons are built
from dictionary definitions and Wikipedia opening sentences (CC BY-SA, linked). Nothing is invented: if a step
has nothing to work with, it returns None and another engine (or "not sure") answers.
"""
import random
import re

DETAILS = 'Written by CAEL from rules and templates (no neural model).'
STOP = set('a an the and or but of to in on at for with by from as is are was were be been it its this that these those '
           'they them their he she his her we our you your i my me there here so very also then than about into after '
           'before over more most some any all no not will would can could should said says'.split())


def out(response, route, details=DETAILS, sources=()):
    return dict(response=response, route='chat/write-' + route, sources=list(sources), details=details)


# ---------------------------------------------------------------- summaries

ASK_SUMMARY = re.compile(r'(?is)^\s*(?:please\s+|can you\s+|could you\s+)?(?:summari[sz]e|sum up|give me (?:a|the) (?:summary|gist|tl;?dr) of|tl;?dr)'
                         r'(?:\s+(?:this|that|the following|the text|it))?(?:\s+(?:in|into)\s+(?:one|1|a single|two|2|a)\s+(sentence|sentences|line|lines))?'
                         r'(?:\s+(?:briefly|for me))?\s*[:\-]\s*(.{80,})$')


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"“])', text.strip()) if s.strip()]


def content(text):
    return [w for w in re.findall(r"[a-z][a-z'-]+", text.lower()) if w not in STOP and len(w) > 2]


def subject_of(sentence):
    """The opening noun phrase of a sentence: "The city council met ..." -> "The city council"."""
    m = re.match(r'((?:The|A|An|Our|My|This|[A-Z][a-z]+)(?:\s+[a-z]+|\s+[A-Z][a-z]+){0,4}?)\s+(?:is|are|was|were|has|have|had|held|met|said|says|will|won|opened|announced|[a-z]+ed)\b', sentence)
    return m[1] if m else None


def object_of(sentence):
    m = re.search(r'\b(?:discuss|about|for|on|of|build|open|launch|plan|study|review)\s+((?:the|a|an|its|their)\s+(?:[a-z-]+\s+){0,2}[a-z-]+)', sentence)
    return m[1] if m else None


def summary(text, count):
    parts = sentences(text)
    if len(parts) < 2:
        return None
    words = content(text)
    freq = {w: words.count(w) for w in set(words)}
    scores = []
    for i, s in enumerate(parts):
        mine = set(content(s))
        score = sum(freq[w] for w in mine) / (1 + len(content(s)) ** 0.5) + (0.6 if i == 0 else 0)
        # Outcomes and decisions carry the news: voted, won, decided, agreed, approved, will.
        score += 1.5 * bool(re.search(r'\b(?:voted|won|decided|agreed|approved|announced|found|will|result|concluded|chose|elected|awarded)\b', s, re.I))
        scores.append(score)
    order = sorted(range(len(parts)), key=lambda i: -scores[i])[:max(1, count)]
    picked = [parts[i] for i in sorted(order)]
    subject, thing = subject_of(parts[0]), object_of(parts[0])
    fixed = []
    for s in picked:
        if s is not parts[0]:
            s = re.sub(r'^(?:After [^,]+,\s*|Then,?\s*|However,?\s*|In the end,?\s*)', '', s)
            if subject:
                s = re.sub(r'(?i)^(?:they|it|he|she)\b', subject, s)
            if thing:
                s = re.sub(r'\b(to (?:fund|build|approve|support|open|buy|sell|close|keep)) it\b', r'\1 ' + thing, s)
            s = s[0].upper() + s[1:]
        fixed.append(s)
    body = ' '.join(fixed)
    if count == 1 and len(fixed) == 1 and subject and not re.search(re.escape(subject.split()[-1]), fixed[0], re.I):
        body = parts[0].rstrip('.') + '; ' + fixed[0][0].lower() + fixed[0][1:]
    return body


# ---------------------------------------------------------------- emails

ASK_EMAIL = re.compile(r'(?is)^\s*(?:please\s+|can you\s+|could you\s+|help me\s+)?(?:write|draft|compose|create)\s+(?:me\s+)?(?:an?\s+)?'
                       r'(?:(?:short|quick|polite|formal|friendly|professional|brief|nice|simple)[,\s]+(?:and\s+)?)*(?:e-?mail|message|note|letter)\b(.*)$')
PURPOSES = [
    ('decline', r'\b(?:declin\w*|turn(?:ing)? down|say(?:ing)? no|can\'?t (?:make|attend|come)|unable to (?:attend|come|make))\b'),
    ('accept', r'\b(?:accept\w*|say(?:ing)? yes|confirm(?:ing)? (?:my|our) (?:attendance|place))\b'),
    ('thank', r'\b(?:thank\w*|gratitude|appreciat\w*)\b'),
    ('apologise', r'\b(?:apolog\w*|sorry|say(?:ing)? sorry)\b'),
    ('follow up', r'\b(?:follow(?:ing)?[- ]up|chas(?:e|ing)|remind\w*)\b'),
    ('cancel', r'\b(?:cancel\w*|call(?:ing)? off)\b'),
    ('reschedule', r'\b(?:reschedul\w*|move (?:the|our) (?:meeting|call)|postpon\w*)\b'),
    ('request', r'\b(?:ask(?:ing)? for|request\w*|asking (?:if|whether)|ask (?:my|the|a))\b'),
    ('invite', r'\b(?:invit\w*)\b'),
    ('resign', r'\b(?:resign\w*|quit(?:ting)? my job|leaving (?:my|the) (?:job|role|company))\b'),
    ('complain', r'\b(?:complain\w*|complaint)\b'),
    ('congratulate', r'\b(?:congratulat\w*)\b'),
]
DAYS = r'(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today|yesterday|next week|this week|last week)'


def email(details):
    lower = details.lower()
    purpose = next((p for p, pattern in PURPOSES if re.search(pattern, lower)), None)
    if not purpose:
        return None
    to = re.search(r'\bto (?:my |our |the )?((?:boss|manager|colleague|team|teacher|landlord|client|customer|friend|neighbour|neighbor|'
                   r'professor|coworker|co-worker|hr|recruiter|doctor|coach|mum|mom|dad|parents?|supplier|company)\b)', lower)
    greeting = {'boss': 'Hi [Name],', 'manager': 'Hi [Name],', 'team': 'Hi team,', 'teacher': 'Dear [Teacher\'s name],',
                'professor': 'Dear Professor [Name],', 'landlord': 'Dear [Name],', 'client': 'Dear [Name],', 'customer': 'Dear [Name],',
                'recruiter': 'Dear [Name],', 'hr': 'Dear HR team,', 'company': 'Dear Sir or Madam,', 'supplier': 'Dear [Name],',
                'mum': 'Hi Mum,', 'mom': 'Hi Mom,', 'dad': 'Hi Dad,', 'parents': 'Hi Mum and Dad,'}.get(to[1] if to else '', 'Hi [Name],')
    event = re.search(r'\b(?:the |a |an |my |our |your )((?:[a-z]+ ){0,2}(?:meeting|invitation|invite|interview|event|party|call|dinner|lunch|'
                      r'wedding|offer|job offer|appointment|conference|workshop|presentation|report|project|order|delivery|class|lesson|game))\b', lower)
    thing = event[1] if event else None
    thing = re.sub(r'^(?:meeting )?invit(?:ation|e) (?:to |for )?', '', thing) if thing and 'invit' in thing and thing.split()[-1] not in ('invitation', 'invite') else thing
    when = re.search(r'\b(?:on |for |this |next )?(' + DAYS + r')\b', lower)
    day = f' on {when[1].capitalize()}' if when and when[1] not in ('tomorrow', 'today', 'yesterday', 'next week', 'this week', 'last week') else f' {when[1]}' if when else ''
    what = thing or 'the meeting'
    # "a meeting invitation" -> "the meeting"; the email thanks for the invitation itself.
    what = re.sub(r'\s*\binvit(?:ation|e)\b', '', what).strip() or 'event'
    what = 'the ' + what if not what.startswith(('the ', 'my ', 'our ')) else what
    help_with = re.search(r'\b(?:for|with) (?:helping|help)(?: me)?(?: with| on)? (?:the |my |our )?([a-z ]{3,30}?)(?:[.,!]|$| yesterday| today| last)', lower)
    # "thanking my neighbour for watching my cat" -> "for watching my cat"; "asking for a day off next week".
    doing = re.search(r'\bfor ((?!helping\b)[a-z]+ing\b[^.!?]{0,60})', lower)
    asked = re.search(r'\bask(?:ing)? (?:for|about|if|whether) ([^.!?]{3,80})', lower)
    reason = re.search(r'\b(?:because|as|since) (.{5,80}?)(?:[.!]|$)', lower)
    bodies = {
        'decline': f'Thank you for inviting me to {what}{day}. Unfortunately, I won\'t be able to attend' + (f' because {reason[1]}' if reason else ' due to a prior commitment') +
                   '. I\'m sorry to miss it, and I\'d be glad to catch up afterwards or join a future one.',
        'accept': f'Thank you for the invitation to {what}{day}. I\'m happy to confirm that I\'ll be there, and I\'m looking forward to it.',
        'thank': f'I just wanted to say a big thank you for ' + (f'helping me with the {help_with[1].strip()}' if help_with else doing[1].strip() if doing
                                                                  else f'your help with {what}' if thing else 'everything you did') +
                 '. Your support made a real difference, and I really appreciate the time you gave.',
        'apologise': f'I\'m sorry about {re.sub(r"^the ", "the ", what) if thing else "what happened"}' +
                     (f'{day}' if day else '') + (f'. It happened because {reason[1]}' if reason else '') +
                     '. I take responsibility, and I\'ll make sure it doesn\'t happen again. Please let me know if there is anything I can do to make up for it.',
        'follow up': f'I\'m following up on {what}. Could you let me know if there are any updates, or if you need anything else from me?',
        'cancel': f'I\'m afraid I need to cancel {what}{day}' + (f' because {reason[1]}' if reason else '') + '. I\'m sorry for any inconvenience, and I\'d be happy to arrange another time.',
        'reschedule': f'Would it be possible to move {what}{day} to another time? I\'m sorry for the change. Please let me know which times work for you.',
        'request': (f'I\'m writing to ask {asked[0].split(" ", 1)[1].strip() if asked else "about " + (what if thing else "something")}. '
                    'Please let me know if that works for you. Thank you in advance.'),
        'invite': f'I\'d love to invite you to {what}{day}. It would be great to see you there. Please let me know if you can come.',
        'resign': 'Please accept this email as formal notice of my resignation. My last working day will be [date], in line with my notice period. '
                  'Thank you for the opportunities and support during my time here; I\'ll do everything I can to make the handover smooth.',
        'complain': f'I\'m writing about a problem with {what}. [Describe what happened and when.] I would appreciate it if you could look into this and let me know how it will be resolved.',
        'congratulate': f'Congratulations on {what if thing else "your great news"}! It\'s really well deserved, and I\'m very happy for you.',
    }
    subjects = {'decline': f'Re: {what.capitalize()}', 'accept': f'Re: {what.capitalize()}', 'thank': 'Thank you',
                'apologise': 'Apology', 'follow up': f'Following up: {what}', 'cancel': f'Cancelling {what}',
                'reschedule': f'Rescheduling {what}', 'request': 'A quick request', 'invite': f'Invitation: {what}',
                'resign': 'Resignation', 'complain': f'Problem with {what}', 'congratulate': 'Congratulations!'}
    closing = 'Kind regards,\n[Your name]' if purpose in ('resign', 'complain', 'request') or greeting.startswith('Dear') else 'Best wishes,\n[Your name]'
    text = f'**Subject:** {subjects[purpose]}\n\n{greeting}\n\n{bodies[purpose]}\n\n{closing}'
    return out(text, 'email', 'An email from CAEL\'s written templates, filled with the details you gave. Edit the [bracketed] parts. No neural model.')


# ---------------------------------------------------------------- names

ASK_NAMES = re.compile(r'(?i)^\s*(?:please\s+)?(?:suggest|give me|come up with|brainstorm|list|think of|what are (?:some|good)|i need)\s+'
                       r'(?:some\s+|a few\s+)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)?\s*(?:good\s+|catchy\s+|creative\s+|cool\s+|fun\s+)?'
                       r'(?:names?|name ideas|business names|brand names)\s+(?:for\s+)?(?:an?\s+|my\s+|the\s+)?(.+?)\s*[?.!]*$')
THEMES = {
    'coffee': ['bean', 'brew', 'roast', 'cup', 'mug', 'grind', 'crema', 'espresso', 'steam', 'drip'],
    'cafe': ['bean', 'brew', 'cup', 'corner', 'table', 'saucer', 'steam', 'crumb'],
    'bakery': ['crumb', 'loaf', 'dough', 'flour', 'oven', 'crust', 'rise', 'butter', 'knead', 'batch'],
    'restaurant': ['table', 'spoon', 'fork', 'plate', 'kitchen', 'feast', 'hearth', 'salt'],
    'bar': ['tap', 'barrel', 'cork', 'glass', 'pint', 'still', 'hops'],
    'bookshop': ['page', 'chapter', 'spine', 'ink', 'shelf', 'margin', 'story'], 'bookstore': ['page', 'chapter', 'spine', 'ink', 'shelf', 'story'],
    'gym': ['iron', 'pulse', 'core', 'grit', 'stride', 'lift', 'forge'],
    'florist': ['petal', 'bloom', 'stem', 'bud', 'blossom', 'meadow'],
    'pet': ['paw', 'whisker', 'tail', 'bark', 'purr', 'snout'],
    'dog': ['paw', 'bark', 'tail', 'bone', 'fetch', 'wag'], 'cat': ['whisker', 'purr', 'paw', 'tail', 'velvet', 'mittens'],
    'band': ['echo', 'static', 'velvet', 'thunder', 'neon', 'riot', 'wolves'],
    'podcast': ['signal', 'echo', 'mic', 'wave', 'chatter', 'frequency'],
    'tech': ['byte', 'pixel', 'logic', 'spark', 'node', 'circuit', 'cloud'], 'startup': ['spark', 'launch', 'orbit', 'pivot', 'pixel', 'forge'],
    'shop': ['corner', 'market', 'shelf', 'basket', 'counter'], 'boat': ['tide', 'gull', 'wake', 'breeze', 'anchor', 'drift'],
}
STYLES = ['The {a} & {b}', '{A} House', 'Little {A}', 'The Daily {A}', '{A} and {B}', 'Golden {A}', '{A} Corner', 'The {A} Room',
          'Morning {A}', 'Wild {A}', '{A} Street', 'Copper {A}', '{A}works', 'Blue {A}', 'The Humble {A}']


def names(count, thing, seed=0):
    thing_word = re.sub(r'[^a-z ]', '', thing.lower()).strip()
    key = next((k for k in THEMES if re.search(r'\b' + k, thing_word)), None)
    pool = list(THEMES[key]) if key else []
    if len(pool) < 4:
        from . import dictionary
        found, _ = dictionary.senses(thing_word.split()[-1]) if thing_word else ([], None)
        for row in found[:3]:
            pool += [w.replace('_', ' ') for w in row[3] + row[5] if w.isalpha() and w.lower() not in thing_word]
        pool = list(dict.fromkeys(pool))
    if len(pool) < 2:
        return None
    rng = random.Random(seed + len(thing_word))
    rng.shuffle(pool)
    styles = list(STYLES)
    rng.shuffle(styles)
    made = []
    for i, style in enumerate(styles):
        a, b = pool[i % len(pool)], pool[(i + 1) % len(pool)]
        made.append(style.format(a=a, b=b, A=a.capitalize(), B=b.capitalize()))
        if len(made) >= count:
            break
    lines = '\n'.join(f'{i}. {n}' for i, n in enumerate(made, 1))
    return out(f'Here are {len(made)} name ideas for a {thing_word}:\n\n{lines}\n\nWant a different style: playful, elegant or short?', 'names',
               'Names combine words related to the subject (hand-written themes or WordNet) with naming patterns. Check that a name is not already taken. No neural model.')


# ---------------------------------------------------------------- simple explanations and comparisons

ASK_SIMPLE = re.compile(r'(?i)^\s*(?:please\s+|can you\s+|could you\s+)?(?:explain|describe|tell me about|what is|what are|what\'s)\s+'
                        r'(?:what\s+)?(?:an?\s+|the\s+)?(.+?)\s+(?:(?:is\s+|are\s+)?(?:to|for)\s+(?:a|an|my)\s+(?:\w+[- ]year[- ]old|child|kid|kids|children|five[- ]year[- ]old|beginner)'
                        r'|in (?:simple|plain|easy) (?:words|terms|english|language)|simply|like i\'?m (?:five|5|a child)|for (?:kids|children|beginners))\s*[?.!]*$')
ASK_DIFF = re.compile(r'(?i)^\s*(?:what(?:\'s| is| are)\s+)?(?:the\s+)?(?:main\s+)?differences?\s+between\s+(?:an?\s+|the\s+)?(.+?)\s+and\s+(?:an?\s+|the\s+)?(.+?)\s*[?.!]*$')
HARD = {'organism': 'living thing', 'organisms': 'living things', 'utilize': 'use', 'utilise': 'use', 'approximately': 'about',
        'numerous': 'many', 'consume': 'eat', 'consumes': 'eats', 'reside': 'live', 'resides': 'lives', 'obtain': 'get', 'obtains': 'gets',
        'commence': 'start', 'sufficient': 'enough', 'assist': 'help', 'construct': 'build', 'facilitate': 'help', 'transform': 'change',
        'transforms': 'changes', 'convert': 'turn', 'converts': 'turns', 'synthesize': 'make', 'synthesise': 'make', 'produce': 'make',
        'produces': 'makes', 'substance': 'stuff', 'substances': 'things', 'emit': 'give off',
        'emits': 'gives off', 'molten': 'melted', 'magnitude': 'size', 'velocity': 'speed', 'terrestrial': 'on land', 'aquatic': 'water'}


def simplify(text):
    """The clearest opening sentences in plainer words: no brackets or dashed asides, everyday words, short sentences."""
    text = re.sub(r'\s*\([^()]*\)', '', text)
    text = re.sub(r'\s*\[[^\]]*\]', '', text)
    text = re.sub(r'\s*[—–]\s*[^—–.]{1,80}[—–]\s*', ' ', text)            # "light energy—typically from sunlight—into"
    text = re.sub(r'\b[a-z]+-bearing\s+|\bautotrophic\s+', '', text)
    for hard, easy in HARD.items():
        text = re.sub(r'\b' + hard + r'\b', easy, text)
        text = re.sub(r'\b' + hard.capitalize() + r'\b', easy.capitalize(), text)
    parts = [p for p in sentences(text)[:4] if not re.match(r'(?i)^the term\b', p)]
    short = [p for p in parts if len(p.split()) <= 32]
    return ' '.join(short[:2]) if short else (parts[0] if parts else '')


def wiki_intro(subject):
    from urllib.parse import urlencode
    from .network import NETWORK
    found = NETWORK.json('https://en.wikipedia.org/w/api.php?' + urlencode(dict(action='query', format='json', list='search', srsearch=subject,
                                                                                 srlimit=3, srnamespace=0)), ttl=86400)
    for hit in found.get('query', {}).get('search', []):
        title = hit['title']
        if title.lower().startswith('list of'):
            continue
        pages = NETWORK.json('https://en.wikipedia.org/w/api.php?' + urlencode(dict(action='query', format='json', prop='extracts|info', exintro=1,
                                                                                     explaintext=1, inprop='url', redirects=1, titles=title)), ttl=86400)
        for page in pages.get('query', {}).get('pages', {}).values():
            extract = page.get('extract', '')
            if extract and 'may refer to' not in extract[:300]:
                return title, extract, page.get('fullurl', '')
    return None


def explain_simply(subject):
    from . import dictionary
    found, base = dictionary.senses(subject.lower()) if len(subject.split()) <= 3 else ([], None)
    sources, text = [], ''
    try:
        page = wiki_intro(subject)
    except Exception:
        page = None
    if page and set(re.findall(r'[a-z]+', subject.lower())) & set(re.findall(r'[a-z]+', page[0].lower())):
        title, extract, url = page
        text = simplify(extract)
        sources = [dict(source=f'Wikipedia: {title}', url=url, licence='CC BY-SA 4.0',
                        licence_url='https://creativecommons.org/licenses/by-sa/4.0/', attribution='Wikipedia contributors')]
    elif found:
        text = f'{subject.capitalize()} means {found[0][1].rstrip(".")}.'
    if not text:
        return None
    lines = [f'Here is a simple way to think about **{subject}**:', '']
    if found and page:
        gloss = re.sub(r'^\([a-z ]+\)\s*', '', found[0][1].split(';')[0]).rstrip('.')
        lines += [f'**In short:** {gloss}.', '', f'**A bit more:** {text}']
    else:
        lines.append(text)
    lines += ['', 'Want me to go one step deeper, or give an everyday example?']
    return out('\n'.join(lines), 'simple', 'Explained from the Wikipedia opening paragraph and dictionary definition, with long words '
               'swapped for everyday ones and brackets removed. No neural model.', sources)


def compare(a, b):
    from . import dictionary
    defs = []
    for word in (a, b):
        found, base = dictionary.senses(word.lower()) if len(word.split()) <= 3 else ([], None)
        noun = [row for row in found if row[0] == 'noun'] or found
        if not noun:
            return None
        defs.append((word, re.sub(r'^\([a-z ]+\)\s*', '', noun[0][1]).rstrip('.'), noun[0][5]))
    (wa, da, ha), (wb, db, hb) = defs
    sources = []
    if da == db:
        # The dictionary does not tell them apart ("frog" / "toad"): use each Wikipedia opening sentence instead.
        wiki = []
        for word in (wa, wb):
            try:
                page = wiki_intro(word)
            except Exception:
                page = None
            if not page:
                return None
            wiki.append(simplify(page[1]).split('. ')[0].rstrip('.'))
            sources.append(dict(source=f'Wikipedia: {page[0]}', url=page[2], licence='CC BY-SA 4.0',
                                licence_url='https://creativecommons.org/licenses/by-sa/4.0/', attribution='Wikipedia contributors'))
        da, db = wiki
    lines = [f'**{wa.capitalize()}**: {da}.', f'**{wb.capitalize()}**: {db}.']
    shared = set(ha) & set(hb)
    if shared:
        lines += ['', f'Both are kinds of {sorted(shared)[0].replace("_", " ")}; the definitions above show how they differ.']
    return out('\n'.join(lines), 'compare', 'Compared from WordNet 3.0 definitions (licence in the bundle)'
               + (' and Wikipedia opening sentences (CC BY-SA 4.0)' if sources else '') + '. No neural model.', sources)


# ---------------------------------------------------------------- entry point

def reply(text, seed=0):
    if len(text) > 4000 or '```' in text:
        return None
    m = ASK_SUMMARY.match(text)
    if m:
        count = 2 if m[1] and m[1].startswith(('sentences', 'lines')) else 1
        body = summary(m[2], count)
        if body:
            return out(f'**Summary:** {body}', 'summary', 'Extractive summary: the sentence carrying most of the text\'s key words, '
                       'with pronouns replaced from the opening sentence. No neural model.')
    m = ASK_EMAIL.match(text)
    if m:
        answer = email(m[1])
        if answer:
            return answer
    m = ASK_NAMES.match(text)
    if m:
        count = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}.get((m[1] or '').lower())
        count = count or (int(m[1]) if m[1] and m[1].isdigit() else 5)
        answer = names(min(count, 12), m[2], seed)
        if answer:
            return answer
    m = ASK_DIFF.match(text)
    if m and len(m[1].split()) <= 3 and len(m[2].split()) <= 3:
        answer = compare(m[1], m[2])
        if answer:
            return answer
    m = ASK_SIMPLE.match(text)
    if m:
        return explain_simply(re.sub(r'\s+(?:is|are|means|works)$', '', m[1].strip()))
    return None
