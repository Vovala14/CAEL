"""Explanatory requests ("explain the rules of chess", "how do I make bread", "how does a jet engine work").

A definition is the wrong answer to these: the user asked to be taught something.
This module recognises the request, reads the whole Wikipedia article, picks the
sections whose headings match what was asked (rules, method, mechanism, ...) and
composes an extractive, multi-point explanation from their paragraphs and lists.
All text is quoted from the article (CC BY-SA 4.0); nothing is invented.
"""
import re

# What each kind of request needs, as words to look for in section headings.
FOCUS = {
    'rules': 'rule rules setup set initial basic basics move moves movement moving play playing gameplay game turn turns objective object '
             'aim goal scoring score points win winning winner check checkmate castling promotion passant capture end ending draw draws '
             'equipment pieces board court field players overview how',
    'method': 'method methods preparation prepare preparing ingredients recipe procedure process steps step technique techniques making '
              'production produce cooking baking instructions directions how basic basics overview materials tools',
    'mechanism': 'principle principles mechanism mechanisms functioning working works physical '
                 'operation operating function functions design '
                 'how theory process structure components parts overview physics chemistry biology',
    'learn': 'basic basics fundamentals overview introduction principles rules technique techniques how getting started learning',
    'overview': 'overview description characteristics features basic basics types structure',
}
# Core concepts count triple: a beginner needs "Check" before "Moving the pieces".
CORE = set('setup initial basic basics objective object aim goal gameplay scoring win winning check checkmate overview principle '
           'principles mechanism mechanisms preparation ingredients steps procedure method fundamentals how'.split())
NOT_ASKED = re.compile(r'(?i)history|etymology|origin|culture|popular|in fiction|media|records|notable|competitive|tournament|'
                       r'organization|governing|variants|computer|software|literature|see also|references|notes|gallery|economics|legal|'
                       r'controvers|criticism|statistics|world championship|professional|industrial|commercial|trade|market|'
                       r'production statistics|economy|regulation|safety record|recording|timing|conduct|adjournment|illegal|'
                       r'irregular|penalt|arbiter|incorrect|displacement|touch-move|moving the pieces')

VERBS = r'play|make|cook|bake|brew|build|grow|use|do|draw|write|solve|start|tie|fix|clean|train|plant|knit|paint|speak|swim|ride|drive|code|program'


def _learning(m):
    verb = (m[1] or '').lower()
    return ('rules' if verb == 'play' else 'method' if verb and verb not in ('speak', 'code', 'program') else 'learn', m[2], None)


REQUEST = [
    # I want to learn how to play chess / help me learn Spanish / how can I learn to swim
    (re.compile(r"(?i)^(?:i\s+(?:really\s+)?(?:want|would like|wanna|need|'d like|hope|am trying)\s+to\s+learn|(?:can you\s+|please\s+)?help me(?:\s+to)?\s+learn|how\s+(?:can|do|should)\s+i\s+learn)"
                r"\s+(?:how\s+to\s+|to\s+)?(?:(" + VERBS + r")\s+)?(?:about\s+)?(?:the\s+|a\s+|an\s+)?(.+?)[?.!]*$"), _learning),
    # teach me how to play chess / teach me to cook pasta
    (re.compile(r'(?i)^(?:please\s+)?(?:(?:can|could|would) you\s+)?teach me\s+(?:how\s+)?to\s+(' + VERBS + r')\s+(?:a\s+|an\s+|the\s+|some\s+)?(.+?)[?.!]*$'),
     _learning),
    # explain the rules of chess / what are the rules of tennis / rules of poker
    (re.compile(r'(?i)^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:explain|tell me|teach me|describe|show me|give me|what are|list)?\s*'
                r'(?:to me\s+)?(?:the\s+|all\s+the\s+)?(?:basic\s+)?(rules|basics|fundamentals|steps|stages)\s+(?:of|for|in|to)\s+(?:playing\s+|making\s+|a\s+|an\s+|the\s+)?(.+?)[?.!]*$'),
     lambda m: ('rules' if m[1].lower() == 'rules' else 'learn', m[2], f'{m[1].lower()} of {m[2]}')),
    # how do I play chess / how to make bread / how can I bake a cake
    (re.compile(r'(?i)^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:explain\s+|tell me\s+|teach me\s+|show me\s+)?(?:how\s+(?:do|can|should|would)\s+(?:i|you|we|one)\s+|how\s+to\s+)'
                r'(play|make|cook|bake|brew|build|grow|use|do|draw|write|solve|start|learn|tie|fix|clean|train|plant|knit|paint)\s+(?:a\s+|an\s+|the\s+|some\s+)?(.+?)[?.!]*$'),
     lambda m: ('rules' if m[1].lower() == 'play' else 'learn' if m[1].lower() == 'learn' else 'method', m[2], None)),
    # how does a jet engine work / explain how photosynthesis works
    (re.compile(r'(?i)^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:explain\s+|tell me\s+|describe\s+)?how\s+(?:does|do|did)?\s*(?:a\s+|an\s+|the\s+)?(.+?)\s+(?:work|works|function|operate|happen)[?.!]*$'),
     lambda m: ('mechanism', m[1], None)),
    # teach me chess / explain chess to me / I want to learn about volcanoes
    (re.compile(r'(?i)^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:teach me(?:\s+about)?|walk me through)\s+(?:a\s+|an\s+|the\s+)?(.+?)(?:\s+to me)?(?:\s+in detail|\s+step by step)?[?.!]*$'),
     lambda m: ('learn', m[1], None)),
]


def parse(text):
    """{'focus', 'subject', 'title'} for an explanatory request, else None."""
    clean = ' '.join(text.strip().split())
    for pattern, build in REQUEST:
        match = pattern.match(clean)
        if match:
            focus, subject, title = build(match)
            subject = re.sub(r'(?i)\s+(?:please|for me|for beginners|step by step|in detail|properly|correctly|well)$', '', subject.strip(' ?.!,'))
            personal = re.search(r"(?i)\b(?:my|mine|your|yours|me|i|our|we|you)\b", subject)
            if not subject or personal or re.fullmatch(r'(?i)it|this|that|them|things|stuff|something', subject) or len(subject) > 80:
                return None
            return dict(focus=focus, subject=subject, title=title)
    return None


def sentences(text, limit):
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z"(])', text.strip())
    return ' '.join(parts[:limit])


def first_sentence(text):
    text = re.sub(r'\s*\([^()]{0,120}\)', '', text).strip()        # drop parenthetical asides
    return re.split(r'(?<=[.!?;:])\s+(?=[A-Z"(])', text)[0].strip()


def compose(title, sections, focus, max_words=380):
    """An extractive explanation from the sections that match the request."""
    words = set(FOCUS[focus].split())

    def score(section):
        heading = section['heading'].lower()
        if heading == 'introduction':
            return 0
        if NOT_ASKED.search(heading):
            return -1
        return sum((3 if w in CORE or w.rstrip('s') in CORE else 1)
                   for w in re.findall(r'[a-z]+', heading) if w in words or w.rstrip('s') in words)

    def block(section):
        """A section in at most ~70 words: its key sentence, then its list items as bullets."""
        parts = [section['heading'] + ':']
        lead = first_sentence(section['paragraphs'][0]) if section['paragraphs'] else ''
        if lead and len(lead.split()) <= 45:
            parts.append(lead)
        for item in section.get('items', []):
            point = first_sentence(item)
            if len(point.split()) >= 4 and sum(len(p.split()) for p in parts) + len(point.split()) <= section_words:
                parts.append('• ' + point)
        return '\n'.join(parts) if len(parts) > 1 else None

    section_words = 75
    intro = next((s for s in sections if s['heading'] == 'Introduction'), None)
    ranked = sorted((s for s in sections if score(s) > 0), key=lambda s: -score(s))
    if not ranked:  # headings say nothing useful: use the first content sections in article order
        ranked = [s for s in sections if s['heading'] != 'Introduction' and score(s) == 0][:4]
    picked, used = [], 0
    for section in ranked:                       # most relevant sections first, within the word budget
        text = block(section)
        if text and used + len(text.split()) <= max_words:
            picked.append((sections.index(section), text))
            used += len(text.split())
    lines = []
    if intro and intro['paragraphs']:
        lines.append(sentences(intro['paragraphs'][0], 2))
    lines += [text for _, text in sorted(picked)]   # but shown in the article's own order
    if len(lines) < 2:
        return None
    return '\n\n'.join(lines)
