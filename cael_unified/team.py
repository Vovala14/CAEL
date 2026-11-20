"""Mr. Meesix is the team: every role below is a Mr. Meesix agent, working on one message together.

Before, each Mr. Meesix answered alone and the first reply stood. Now each one is given a single job on the task
(plan it, solve it, look it up, check it, write it up), does that job, hands its result to the shared board and is
gone. A task's agents are numbered in the order they are called (Meesix-1 is always the Planner); a message with
several tasks gets one such team per task, six tasks at a time (meesix.py). The jobs:

  Planner      cuts the message into tasks (meesix.tasks_of), turns a follow-up into a full question
               ("And which one is the hottest?" -> "Which planet is the hottest?") and notes what kind of answer is
               wanted (a number, a name, a date, advice, a reply to something told).
  Specialists  each takes only what is its own: the Diary (schedule_agent), the Calculator for sums that run over
               several turns (calc_agent), the Writer (writer_agent), the Logician (logic_agent), the Rememberer
               (recall_agent) and the Listener (empath).
  Solver       the exact solvers for arithmetic word problems and logic (meesix.specialists).
  Generalist   the full CAEL pipeline: memory, skills, knowledge, conversation.
  Researcher   two of them. One looks for the exact value on Wikidata and Wikipedia (exact_web.py) and starts at the
               same time as the Generalist, so its finding is ready when needed. The other reads pages and quotes the
               best checked passage (web_check.py).
  Critic       reads every draft against the Planner's note and sends it back with a reason when it is a dead end, has
               no number where one was asked for, answers yes/no to a "how many", repeats the user's own first-person
               words back, or is empty. A rejected draft is never shown.
  Counsellor   general guidance for the common shapes of an everyday question (counsel.py), asked only when the others
               had nothing.
  Editor       picks the draft the Critic accepted, or writes the honest last resort: what was tried, and one question
               that would let the team answer.

Each Mr. Meesix is a plain function call that holds nothing after its job; while it works its name is in
meesix.ALIVE. The board (which Meesix did what, and why a draft was sent back) is returned with the reply as `team`
and kept in meesix.LAST, so a reply can be traced. No model is involved.
"""
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import meesix
from . import web_check as wc

POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix='meesix-research')
TRUSTED = re.compile(r'^(?:helper/|chat/native-|chat/solve-|chat/skill|chat/reasoning-|chat/world-fact|chat/local-knowledge|chat/fixture|'
                     r'chat/plus-(?:appointment|what-if|share|writing|follow-up|schedule)|chat/everyday-|chat/story)')
DEAD_ROUTE = re.compile(r'web-checked-none|web-evidence-|core-fallback|temporal-clarify|recall-unknown|meesix-failed|problem-clarify')
# Drafts the Editor may replace with its own last resort. Any other reply that was sent back (a helper asking "whole items
# or fractions?", a refusal to state an unverified fact, a news range it cannot serve) is a deliberate, specific reply: when
# no other Mr. Meesix has something better, it stands as written.
REPLACEABLE = re.compile(r'core-fallback|temporal-clarify|recall-unknown|web-checked-none|web-evidence-|meesix-failed|corpus$|core-open$|context-reasoning$|memory-recall-said|problem-clarify')
CAREFUL = re.compile(r'^(?:helper/|chat/native-|chat/news|chat/factual|chat/web-unsupported|chat/quantity|chat/semantic|chat/task|chat/source)')
DEAD_TEXT = re.compile(r"(?i)^\s*(?:i looked this up, but i couldn'?t find|i searched the web for .* but could not|i found pages, but could not|"
                       r"i do not have a reliable answer|i have not interpreted|i don'?t think you'?ve told me|i could not (?:verify|find)|"
                       r"i see\. tell me a bit more|hello! i am here to help)")
NUMERIC_Q = re.compile(r"(?i)\bhow (?:many|much)\b|\bwhat(?:'s| is| are| was| will be) (?:the |my |our )?(?:total|cost|price|sum|difference|average|change|"
                       r"area|bill|answer|result)\b|\bwhat (?:does|do|did|will|would) (?:each|it|that|i|we|they) (?:pay|cost|owe|get|have left)\b|"
                       r"\bwhat time\b|\bwhen (?:do|does|will|did|would) (?:i|we|it|he|she|they|the \w+) (?:finish|arrive|land|get|end|leave|be done)\b|"
                       r"\bhow long (?:will|does|did|would) (?:it|that|the)\b")
FIRST_PERSON = re.compile(r"(?i)\b(?:my|i'd|i'm|i've|i'll|me|myself|we|our|i)\b")


DESK = (('the Diary', 'schedule_agent'), ('the Calculator', 'calc_agent'), ('the Writer', 'writer_agent'), ('the Storyteller', 'story_agent'), ('the Logician', 'logic_agent'),
        ('the Rememberer', 'recall_agent'), ('the Listener', 'empath'), ('the Advisor', 'advice_library'))
QUOTED = re.compile(r'^chat/(?:core-open|open-retrieval|corpus|local-other|local-unknown|web-single|web-closest|web-checked$|plus-view|core-talk-trip|core-knowledge)')


class Board:
    """What the agents of one task share."""

    def __init__(self, messages):
        self.messages = messages
        self.turns = wc.user_turns(messages)
        self.last = self.turns[-1].strip()
        self.started = time.perf_counter()
        self.log = []                       # (agent, what it did)
        self.agents = {}                    # job -> the Mr. Meesix doing it on this task
        asked = [s for s in re.split(r'(?<=[.!?])\s+', self.last) if s.strip().endswith('?')]
        self.asked = asked[-1].strip() if asked else ''
        self.is_question = bool(self.asked) or bool(wc.ASKS.search(self.last))
        self.question = self.last
        self.fact = False
        self.advice = None                  # the Counsellor's reply, when the question has one of its shapes
        self.searched = False               # a page search has been made for this task
        self.search = None                  # the Planner's search plan (search_plan)
        self.numeric = bool(self.asked and NUMERIC_Q.search(self.asked) and re.search(r'\d', ' '.join(self.turns[-4:])))
        counted = re.search(r"(?i)\bhow many ([a-z]+)", self.asked or '')
        if self.numeric and counted and not re.search(r'\d', self.last) and \
                wc.stem(counted[1].lower()) not in {wc.stem(w) for w in wc.words(' '.join(self.turns[-4:-1]))}:
            self.numeric = False            # "How many planets are in the Solar System?" after a sum about apples: a fact, not a sum

    def meesix(self, role):
        """The Mr. Meesix that has this job on this task: 'Meesix-3 (Researcher)'. One agent per job, numbered as called."""
        role = re.sub(r'^(?:the|a) ', '', role)
        role = role[:1].upper() + role[1:]
        if role not in self.agents:
            self.agents[role] = f'Meesix-{len(self.agents) + 1} ({role})'
        return self.agents[role]

    def do(self, role, job, *args, **kwargs):
        """Run one job as its Mr. Meesix: alive while it works, gone when it returns."""
        role = re.sub(r'^(?:the|a) ', '', role)
        name = self.agents.get(role[:1].upper() + role[1:]) or f'Meesix ({role})'     # numbered once it has something to report
        if getattr(meesix.INSIDE, 'task', False):
            return job(*args, **kwargs)     # one of six task agents is doing this job itself: no further agent is alive for it
        with meesix._COUNT:
            meesix.ALIVE.add(name)
        try:
            return job(*args, **kwargs)
        finally:
            with meesix._COUNT:
                meesix.ALIVE.discard(name)

    def note(self, agent, what):
        self.log.append((self.meesix(agent), what, round(time.perf_counter() - self.started, 2)))


def plan(board):
    """The Planner: the full question and the kind of answer wanted."""
    try:
        from . import exact_web
        board.question = exact_web.standalone(board.messages)
        board.question = re.sub(r"(?i)^\s*(?:roughly|approximately|about|around)\s+(?=how\b)", '', board.question)
        board.question = board.question[:1].upper() + board.question[1:]
        plain = re.sub(r"(?i)^\s*(?:(?:can|could|would) you (?:please )?(?:tell me|explain)(?: to me)?|please)\b", '', board.question)
        plain = re.sub(r"(?i)\bcan you (?:usually |only |ever )*(?:see|find|get)\b", 'is it seen', plain)     # the generic "you"
        if board.is_question and not board.numeric and not re.search(r"(?i)\b(?:i|my|me|we|our|you|your)\b", plain):
            kind = exact_web.asks(board.question)[0]
            relation = any(p.match(board.question) for p, _, _ in exact_web.RELATIONS)
            board.fact = bool(kind or relation or exact_web.ABOUT.match(board.question))
    except Exception:
        pass
    wants = 'a number' if board.numeric else 'a fact' if board.fact else 'an answer' if board.is_question else 'a reply'
    board.note('Planner', f'{wants}' + (f'; full question: "{board.question}"' if board.question != board.asked and board.asked else ''))
    if board.is_question and not board.numeric:
        try:
            board.search = search_plan(board)
            p = board.search
            board.note('Planner', f'search plan: a "{p["shape"]}" answer about "{p["subject"] or "?"}"; queries {p["queries"][:3]}; sites {p["sites"]}')
            # a follow-up that leans on the chat ("What's the easiest thing to try first?", "Is it anything to worry about?") is not
            # an encyclopedia question, whatever its first word
            if board.fact and len(board.turns) > 1 and (p.get('own_from') != 'question' or not p.get('ask')) and re.search(
                    r"(?i)\b(?:it|its|that|this|they|them|thing|first|one|he|she|him|her|myself|ourselves)\b", board.asked or board.last):
                board.fact = False
                board.note('Planner', 'a follow-up about this chat, not a fact to look up')
        except Exception:
            board.search = None


# The shape of answer a question needs, which decides what the Researcher looks for in what it reads.
SHAPES = [
    ('steps', r"\bwhat(?:'s| is| are) the (?:easiest|best|quickest|simplest|cheapest|safest|right|proper) ways?\b|\bwhat can (?:i|we) do\b|"
              r"\bany (?:ideas|tips|suggestions|advice)\b|\bcan (?:they|it|she|he) be (?:saved|fixed|rescued|repaired)\b"),
    ('often', r"\bhow (?:often|frequently|regularly)\b|\bhow many times (?:a|per|each)\b|\bevery how\b"),
    ('normal', r"\b(?:is (?:that|this|it) (?:normal|common|usual|ok|okay)|does (?:everyone|everybody)|is it just me|do (?:most|other) people)\b"),
    ('why', r"^\s*(?:and |so |but )?why\b|\bwhat causes\b|\bhow come\b"),
    ('amount', r"\bhow (?:much|many|long|far|big|old|hot|cold|early|late)\b"),
    ('choose', r"\bwhich (?:is|one|should)\b|\bwhat(?:'s| is) the best\b|\bshould (?:i|we)\b.*\bor\b|\bis it (?:worth|better)\b|\bshould (?:i|we)\b"),
    ('steps', r"\bhow (?:do|can|should|could|would) (?:i|we|you)\b|\bhow to\b|\bwhat (?:should|can|could|do) (?:i|we) (?:do|use|try|bring|pack|buy)\b|\btips?\b|\bideas?\b|"
              r"\badvice\b|\bwhere (?:should|can|could|do) (?:i|we)\b|\bwhat (?:do|should) i need\b|\bwhat (?:happens|do (?:i|we) do|should (?:i|we) do) if\b|"
              r"\bwhat am i doing wrong\b"),
    ('fact', r"^\s*(?:who|when|where|what|which)\b"),
]
# Everyday wording that search pages phrase differently ("while I'm gone" is "while on holiday" on most pages).
REPHRASE = [(r"\bwhile i'?m (?:gone|away)\b|\bwhen i'?m (?:gone|away)\b", 'while on holiday'), (r"\bstop (?:coming|landing|sitting)\b", 'deter'),
            (r"\bget rid of\b", 'remove'), (r"\bkeep (?:them|it) alive\b", 'care'), (r"\bhurt less\b", 'relieve pain'), (r"\bgo up my nose\b", 'in nose'),
            (r"\bfussy\b", 'picky'), (r"\bfood bill\b", 'grocery budget'), (r"\bsinking\b", 'sinking legs'), (r"\bjug\b", 'pitcher')]


def search_plan(board):
    """The Planner's search plan: answer shape, subject, the question written out, query wordings, and where to look."""
    from . import researchers, stack_source
    q = board.question or board.asked or board.last
    shape = next((name for name, pat in SHAPES if re.search('(?i)' + pat, q)), 'steps')
    bound, subject = researchers.bound_question(board.messages)
    if not subject and board.question and board.question != board.asked:
        bound = board.question
    words = [w for w in wc.content(bound) if w not in wc.GENERIC]
    key = sorted(dict.fromkeys(words), key=lambda w: -wc.weight(w))[:5]
    queries = [bound.rstrip('?') + '?']
    if key:
        queries.append(' '.join(key))
    plain = bound.lower()
    for pat, rep in REPHRASE:
        plain = re.sub('(?i)' + pat, rep, plain)
    if plain != bound.lower():
        queries.append(' '.join(w for w in wc.content(plain) if w not in wc.GENERIC)[:120])
    if subject and key and subject.split()[-1] not in ' '.join(key):
        queries.append(subject + ' ' + ' '.join(key[:3]))
    scene = ' '.join(board.turns[-4:])
    # The short search a person would type: what the question itself is about ("puncture", "nose", "food bill"), with the
    # activity or thing the conversation is about ("cycling", "backstroke", "pigeons"). Places and people ("pool",
    # "family", "nowhere") make poor search words.
    weak = {'pool', 'family', 'nowhere', 'middle', 'home', 'house', 'place', 'people', 'person', 'everyone', 'someone', 'thing', 'things', 'time',
            'day', 'week', 'month', 'year', 'one', 'us', 'kids', 'wife', 'husband', 'partner', 'friend', 'friends', 'way', 'lot', 'bit', 'itself',
            'super', 'quite', 'pretty', 'very', 'local', 'whole', 'own', 'kg', 'kgs', 'kilo', 'kilos', 'cm', 'mm', 'lb', 'lbs', 'am', 'pm', 'single',
            'nights', 'night', 'morning', 'mornings', 'days', 'weeks', 'hours', 'minutes', 'about', 'around', 'roughly', 'started', 'tried'}
    verbs = {'change', 'clean', 'get', 'gets', 'stop', 'keep', 'going', 'happens', 'doing', 'make', 'need', 'want', 'try', 'use', 'start', 'feel', 'come',
             'coming', 'hurt', 'hurting', 'learn', 'cook', 'buy', 'pay', 'work', 'help', 'handle', 'plan', 'without', 'wrong', 'actually', 'really', 'even',
             'explain', 'tell', 'works', 'saved', 'save', 'usually', 'walk', 'talk', 'show', 'guide', 'worth', 'next', 'put', 'giving', 'keeps',
             'think', 'anything', 'something', 'never', 'always', 'today', 'yesterday', 'tomorrow'}
    def keys_of(text):
        found = [x for x in dict.fromkeys(wc.content(text)) if x not in wc.GENERIC and x not in weak and x not in verbs and wc.weight(x) > 3.5]
        return sorted(found, key=lambda w: -wc.weight(w))
    # the question sentence says what is asked ("train", "nose"); the sentence told with it only fills in when it says
    # nothing searchable ("I keep sinking at the hips. What am I doing wrong?")
    own = keys_of(board.asked or '')
    own_from = 'question'
    if not own:
        own, own_from = keys_of(board.last), 'turn'
    if not own and len(board.turns) > 1:
        own, own_from = keys_of(board.turns[-2]), 'context'     # "What am I doing wrong?" after "My tomato plants have yellow leaves."
    own = own[:2]
    scene_words = [w for w in wc.nouns(list(dict.fromkeys(wc.content(' '.join(board.turns[:-1][-3:]))))) if w not in weak and w not in own and wc.weight(w) > 4]
    from . import stack_source as _ss
    domain = {w for _, words in _ss.SITES.values() for w in words.split()}
    scene_all = [w for w in dict.fromkeys(wc.content(' '.join(board.turns[:-1][-3:]))) if w not in weak and w not in own]
    vague = {'learn', 'learning', 'start', 'started', 'starting', 'practice', 'practise', 'play', 'playing', 'game', 'games', 'trip', 'going', 'job',
             'work', 'help', 'make', 'season', 'friend', 'fit', 'super', 'ideas', 'word', 'words'}
    activity = [w for w in scene_all if w not in vague and (w in domain or _ss.stem(w) in {_ss.stem(d) for d in domain})]
    # the activity the conversation is about ("cycling", "swim") says where to look; otherwise its rarest noun
    # the thing the conversation is about is usually the first thing named with "my", "the", "a" ("a heavy mirror", "my
    # kitchen knives", "the window"), which beats the rarest noun ("hallway")
    thing = thing_of(' '.join(board.turns[:-1][-3:]) if len(board.turns) > 1 else board.last, weak)
    # an activity is a site word as such ("cycling", "camping", "swim"); not a verb that only shares a stem with one ("leaving" ~ "leaves")
    doing = [w for w in activity if (w.endswith('ing') and w in domain) or w in ('swim', 'run', 'cycle', 'bike', 'hike', 'camp', 'cook', 'bake', 'knit', 'sew', 'dance', 'jog')]
    if thing and not doing:
        anchor = thing                      # both words of "tomato plants", "kitchen knives"
    else:
        anchor = activity[0] if activity else max(scene_words, key=wc.weight) if scene_words else (subject.split()[-1] if subject else None)
    bad_subject = not subject or subject.split()[-1].lower() in weak or len(subject) < 4 or "'" in subject or not wc.nouns([subject.split()[-1].lower()])
    if bad_subject:
        subject = thing or anchor
    if own_from == 'context':
        own = []                            # the question says nothing of its own: the scene is the search
    # the problem the conversation is about is said by its rarest describing word ("draughty", "snores", "blunt", "meowing"),
    # which is often not a noun: it goes with the thing ("draughty window") when the question leans on the earlier turns
    problem = []
    if len(board.turns) > 1:
        told = [x for x in keys_of(' '.join(board.turns[:-1][-3:])) if x not in own and not re.search(r'\d', x) and not x.endswith('ly')]
        told = [x for x in told if x not in (anchor or '').split() and x not in (thing or '').split() and x not in doing]
        # describing words first ("draughty", "blunt", "overwatered"); "-ing" words count ("meowing", "waking")
        describing = [x for x in told if not wc.nouns([x]) or x.endswith(('ing', 'ed'))]
        # what the problem consists of is often a noun too ("brown marks", "a red rash", "a cigarette burn"): after the describing
        # words, the rarest other nouns told with the thing
        named = [x for x in told if x not in describing and len(x) > 3]
        # the other thing in the told sentence is often what the problem is about ("hates the car", "bringing mice into the house")
        first_told = re.split(r'(?<=[.!?])\s+', board.turns[0])[0] if board.turns else ''
        obj = [m.lower() for m in re.findall(r"(?i)\b(?:the|a|an|my|our|his|her|their|some)\s+([a-z]{3,})\b", first_told)[1:3]]
        obj = [o for o in obj if o in told and o not in (thing or '').split() and o not in weak]
        named = obj[:1] + [x for x in named if x not in obj[:1]]
        # what the thing "has" or "got" is the problem itself ("has a red rash", "has a cigarette burn", "got a flat tyre")
        has = re.findall(r"(?i)\b(?:has|have|had|got|with|developed)\s+(?:a|an|some|this|these|lots of|a lot of)?\s*(?:[a-z]+\s+)?([a-z]{4,})\b", ' '.join(board.turns[:-1][-3:]))
        named = [h.lower() for h in has if h.lower() in told and h.lower() not in describing][:1] + [x for x in named if x not in [h.lower() for h in has[:1]]]
        problem = (describing[:2] + named[:2])[:3] if thing else (describing[:2] or told[:1])
    leans = not own or own_from != 'question' or re.search(r"(?i)\b(?:it|them|they|this|that|these|those|her|him|she|he|one)\b", board.asked or '')
    parts = (problem[:1] if leans else []) + ((anchor or '').split()) + [w for w in own[:2] if w not in (anchor or '').split()]
    core = ' '.join(list(dict.fromkeys(parts))[:4]) or None
    if core and anchor and not subject:
        subject = anchor
    # what a thread must be about (the thing's rarest word, "knives" of "kitchen knives", or the problem when no thing is named:
    # "snores"), and what it should also speak to (the problem and the question's own words)
    head = max((anchor or '').split(), key=wc.weight) if anchor else None
    if not thing and problem and not doing:
        need = problem[:1]
    else:
        need = [head] if head else []
    asked_words = [y for x in own[:2] for y in x.split('-')]
    told_words = (problem if leans else problem[:1]) + [x for x in (anchor or '').split() if x != head]
    # the question's own words are searched first when it has some ("pull-through sharpener"), else the told problem
    want = [w for w in dict.fromkeys((asked_words + told_words) if own_from == 'question' else (told_words + asked_words)) if w not in need]
    person = re.match(r"(?i)\s*(?:my|our)\s+(partner|husband|wife|boyfriend|girlfriend|flatmate|roommate|housemate|neighbou?r|boss|colleague|friend|mum|mom|dad)\b",
                      board.turns[0] if board.turns else '')
    # the question's own named things ("whetstone", "curtains", "landlord") must be in a thread; plain words ("fall") need not
    ask = [y for x in own[:2] for y in x.split('-') if y not in need and wc.nouns([y]) and wc.weight(y) >= 5.5 and not y.endswith('est')] \
        if own_from == 'question' else []
    # a young child said by age ("our two-year-old") is what parenting threads call a toddler, baby or child
    age = re.search(r"(?i)\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|\d{1,2})[- ](?:year|month)[- ]old\b|"
                    r"\b(toddler|baby|newborn|infant|preschooler|teenager|teen)s?\b", scene)
    if age:
        n = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
             'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16}.get((age[1] or '').lower()) or (int(age[1]) if age[1] and age[1].isdigit() else None)
        kid = (age[2] or '').lower() or ('baby' if 'month' in age[0].lower() or (n is not None and n < 1) else 'toddler' if n and n <= 3 else
                                         'child' if n and n <= 12 else 'teenager')
        kid = {'newborn': 'baby', 'infant': 'baby', 'teen': 'teenager', 'preschooler': 'toddler'}.get(kid, kid)
        if kid not in need:
            need = [kid] + [w for w in need if w not in weak][:1]
    return dict(shape=shape, subject=subject, bound=bound, core=core, own_from=own_from, need=need, want=want, ask=ask, queries=list(dict.fromkeys(queries))[:4],
                sites=sites_for(bound + ' ' + (core or ''), scene))


_NOUNISH = {}


def nounish(w):
    """Has a noun sense at all (after "our", "tap" and "puddle" are things), and is a content word ("has" is not)."""
    if w in _NOUNISH:
        return _NOUNISH[w]
    ok = False
    if w in wc.content(w) and w not in wc.GENERIC and not w.endswith('ly'):
        try:
            from . import open_chat as oc
            wn = oc.wordnet()
            bases = {w}
            for cut, add in (('ies', 'y'), ('ves', 'fe'), ('ves', 'f'), ('es', ''), ('s', '')):
                if w.endswith(cut) and len(w) - len(cut) >= 3:
                    bases.add(w[:-len(cut)] + add)
            ok = wn is None or any(wn.execute('SELECT 1 FROM lemma WHERE word = ? AND pos = "noun" LIMIT 1', (b,)).fetchone() for b in bases)
        except Exception:
            ok = bool(wc.nouns([w]))
    _NOUNISH[w] = ok
    return ok


def thing_of(text, weak=()):
    """The first thing named with a determiner: 'a heavy mirror' -> 'mirror', 'My kitchen knives' -> 'kitchen knives',
    'The window in our bedroom' -> 'window'. People and places in `weak` are passed over."""
    for i, m in enumerate(re.finditer(r"(?i)\b(?:my|our|the|a|an|his|her|their|your|those|these)\s+((?:[a-z][a-z'-]*\s+){0,3}[a-z][a-z'-]*)", text)):
        words = m[1].lower().split()
        if i == 0 and words and words[0] in weak and m.start() < 3:
            return None                     # "My partner snores": a person, so the problem is the subject, not "the sofa"
        out = []
        for w in words:
            noun = nounish(w) and not re.search(r'(?:ing|ed|ous|ful|ive|able|y)$', w) or (w.endswith('y') and bool(wc.nouns([w])))
            if noun:
                out.append(w)
            elif out:
                break
        while out and (out[-1] in weak or out[-1] in ('one', 'lot', 'bit', 'kind', 'sort', 'couple', 'few')):
            out.pop()
        if out and out[-1] not in weak and len(out[-1]) > 2:
            return ' '.join(out[-2:])
    return None


def sites_for(bound, scene):
    """Stack Exchange sites to search: the subject words' own sites, then the local index's site classifier, which has
    seen 265,000 questions from 19 everyday sites ("pigeons on the balcony" -> lifehacks)."""
    from . import stack_source, open_chat
    named = list(stack_source.sites_for(bound + ' ' + scene, limit=1))      # a site whose own words were used ("swim" -> sports)
    guessed = []
    try:
        probs = open_chat.site_probs(open_chat.weights(bound + ' ' + scene))
        guessed = [s for s, p in sorted(probs.items(), key=lambda x: -x[1]) if p >= 0.1 and s in stack_source.SITES]
    except Exception:
        pass
    try:
        if guessed and probs.get(guessed[0], 0) >= 0.5 and named and named[0] in probs and named[0] not in guessed[:3]:
            named = []                          # the classifier is sure and disagrees with a single keyword ("filter" is not a car part here)
    except Exception:
        pass
    sites = list(dict.fromkeys(named + guessed))
    return sites[:2] or ['lifehacks']           # everyday questions with no clearer home


def review(board, draft):
    """The Critic: (accepted, reason)."""
    if not isinstance(draft, dict):
        return False, 'no reply'
    said = str(draft.get('response', '')).strip()
    route = str(draft.get('route', ''))
    if not said:
        return False, 'empty reply'
    from .applicability import conflict
    clash = conflict(' '.join(board.turns[-6:]), said)
    if clash and not route.startswith(('chat/solve-', 'chat/calc', 'chat/plus-schedule', 'chat/memory-')):
        return False, f'the reply is about {clash[0]}, the user about {clash[1]}'
    if route.startswith('chat/web-') and route != 'chat/web-exact':
        source = re.search(r'\nSource: (.+?) \(', said)
        if source:
            time_words = r'(?:january|february|march|april|may|june|july|august|september|october|november|december|monday|tuesday|wednesday|thursday|'
            time_words += r'friday|saturday|sunday|today|tomorrow|week|month|year|morning|evening|night)'
            title = {wc.stem(w) for w in wc.content(source[1]) if not re.fullmatch(time_words, w)}
            asked = {wc.stem(w) for t in board.turns[-3:] for w in wc.content(t) if not re.fullmatch(time_words, w)}
            if title and not title & asked:
                return False, f'the source ("{source[1][:40]}") is about something else'
            # the passage must be about what the (written-out) question is about: two of its three rarest nouns, in the title or the passage
            q = board.question or board.last
            pool = [w for w in wc.content(q) if not re.fullmatch(time_words, w) and w not in wc.GENERIC and w not in ('near', 'far', 'usually', 'often')]
            rare = sorted({wc.stem(w) for w in wc.nouns(pool) if wc.weight(w) > 3.0}, key=lambda s: -wc.weight(s))[:3]
            if len(rare) < 2:
                rare = sorted({wc.stem(w) for w in pool if wc.weight(w) > 3.5}, key=lambda s: -wc.weight(s))[:3]
            body = {wc.stem(w) for w in wc.words(said.split('\n\nSource:')[0])}
            # a thread the Researcher matched to the plan (what it must be about in its title, the question's own named things
            # in it) has passed a stricter subject test than this one
            planned = bool(board.search and board.search.get('need')) and route == 'chat/web-single' and 'One thread with an answer' in said
            if planned and any(wc.spelled_stems(n) & (title | body) for n in board.search['need']):
                rare = []
            if len(rare) >= 2 and len(set(rare) & title) < 2 and len(set(rare) & body) < 2:
                return False, f'the passage is not about {" / ".join(rare)}'
    if CAREFUL.search(route) or draft.get('helper_reasoning'):
        return True, 'accepted (a checked helper\'s own reply)'
    if DEAD_ROUTE.search(route) or DEAD_TEXT.search(said) or wc.OLD_WEB_DEAD_END.search(said):
        return False, 'dead end'
    low = said.lower()
    if len(board.turns) > 1 and re.search(r'web-checked|web-closest|web-wikipedia|web-single', route) and 'Stack Exchange' not in said \
            and board.search and board.search.get('need'):
        body = {wc.stem(w) for w in wc.words(said.split('\n\nSource:')[0])}
        if not any(wc.spelled_stems(n) & body for n in board.search['need']):
            return False, f'an encyclopedia passage not about the {" ".join(board.search["need"])} this chat is about'
    if re.search(r'core-decision|core-compare', route) and len(board.turns) > 1 and re.search(r'(?i)\bhere is a simple way to compare\b', said):
        return False, 'a template for weighing choices, not an answer about this'
    if said.count('\u2022') >= 4 and re.search(r'(?m)^[A-Z][a-z ]+:\s*$', said):
        return False, 'an encyclopedia list of meanings, not an answer'
    if route == 'chat/web-exact' and re.match(r"\*\*(?:several|many|some|few|a few|various|numerous|most|all|none)\.?\*\*", said, re.I):
        return False, 'a quantifier word is not an answer'
    # a follow-up about the thing the chat is about ("I already changed the battery and it's still doing it", "Do I need to
    # turn off the water first?") is not answered by an authored note about something else (batteries in general, drinking water)
    if board.is_question and len(board.turns) > 1 and re.search(r'core-knowledge|core-open$|counsel|core-talk', route) and board.search \
            and board.search.get('need') and re.search(r"(?i)\b(?:it|its|he|him|his|she|her|they|them|this|that|first|myself|ourselves)\b", board.asked or board.last):
        need = board.search['need']
        have = {wc.stem(w) for w in wc.words(said)}
        now = {wc.stem(w) for w in wc.words(board.last)}
        told = [w for w in (board.search.get('want') or []) if w not in (board.search.get('ask') or []) and wc.stem(w) not in now]
        if not any(wc.spelled_stems(n) & have for n in need + told):
            return False, f'not about the {" ".join(need)} the chat is about'
    if re.search(r'core-knowledge|core-open|chat/advice|counsel|web-single|web-closest|plus-talk|local-knowledge', route) and \
            re.match(r"(?i)\s*(?:and |so )?(?:roughly |about |approximately |around |so )?how (?:many|much)\b", board.asked or '') and not re.search(
            r"\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|twelve|twenty|thirty|forty|fifty|hundreds|thousands|millions|billions|dozen|none|no one)\b", low):
        return False, 'no figure for a "how many" question'
    counted = re.search(r"(?i)\bhow many ([a-z]+)\b", board.asked)
    if route == 'chat/solve-math' and counted and counted[1].lower() not in ('more', 'times', 'people', 'days', 'hours', 'minutes', 'weeks', 'months', 'years', 'items', 'things'):
        stated = ' '.join(s for s in re.split(r'(?<=[.!?])\s+', ' '.join(board.turns[-3:])) if not s.strip().endswith('?')).lower()
        if stated and wc.stem(counted[1].lower()) not in {wc.stem(w) for w in wc.words(stated)}:
            return False, f'nothing was said about {counted[1].lower()}'
    whose = re.search(r"\bdoes ([A-Z][a-z]+) (?:have|own|hold)\b", board.asked)
    if route == 'chat/solve-math' and whose:
        told = ' '.join(x for x in re.split(r'(?<=[.!?])\s+', board.last) if not x.strip().endswith('?'))
        if re.search(r'\bto ' + whose[1] + r'\b', told) and not re.search(r'\b' + whose[1] + r' (?:has|had|have|owns|starts)\b', told):
            return False, f'what {whose[1]} started with was never said'
    if board.numeric:
        head = said[:400]
        if not re.search(r'\d', head) and not re.search(r'(?i)\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|none|zero|half)\b', head):
            return False, 'a number was asked for and the reply has none'
        if re.match(r"(?i)\s*\**(?:not necessarily|yes|no)\b", said) and re.match(r"(?i)\s*(?:and |so |ok,? |okay,? )?(?:how|what|when|which)\b", board.asked):
            return False, 'yes/no given to a question that asks for a value'
        if QUOTED.search(route) or route.startswith('chat/web-'):
            return False, 'a calculation was asked for and a quotation was given'
    if re.match(r"(?i)\s*\**not necessarily", said) and re.match(r"(?i)\s*(?:how|what|when|which|who|where)\b", board.asked):
        return False, 'yes/no given to a question that asks for a value'
    # the user's own first-person words handed back as CAEL's ("Your back from my first ever yoga class is a big deal")
    user_words = board.last.lower().replace('’', "'").split()
    spans = {' '.join(user_words[i:i + 4]) for i in range(len(user_words) - 3)}
    for span in spans:
        if FIRST_PERSON.search(span) and span in low.replace('’', "'") and not re.search(r'(?i)\byou said\b|\byou told me\b|["“]', said):
            if not re.search(r"(?i)\b(?:here'?s|text|message|email|note|draft|version)\b", said[:160]):
                return False, 'the reply repeats the user\'s own words in the first person'
    if not board.is_question and (re.match(r"(?i)\s*(?:got it|noted)[:,] ", said) and route in ('chat/plus-talk', 'chat/memory-talk-noted')
                                  and not re.search(r"(?i)\b(?:at|on|by) (?:\d|noon|monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|tonight)|"
                                                    r"\b(?:is|are) (?:called|named)|\bappointment|\bmeeting|\bflight|\binterview\b", board.last)):
        return False, 'an echo of the user\'s words instead of a reply'
    if not board.is_question and re.match(r"(?i)\s*(?:sounds nice|nice)!? how is it going", said):
        return False, 'a stock reply'
    if route == 'chat/plus-talk' and re.match(r"(?i)\s*that'?s a good goal", said) and not re.search(
            r"(?i)\b(?:want to|trying to|goal|plan to|hoping to|aim|going to|decided to|would like to|i'd like to)\b", board.last):
        return False, 'a reply about goals to something that is not one'
    if len(said.split()) <= 4 and not re.search(r'\d', said) and re.match(
            r"(?i)\s*(?:and |so |ok,? )?(?:how (?:often|should|can|do|could|would)|why|should|what should|what can|what could|is it|are there|any)\b", board.asked):
        return False, 'a few words to a question that asks for an explanation or advice'
    planned_thread = bool(board.search and board.search.get('need')) and route == 'chat/web-single' and 'One thread with an answer' in said and \
        any(wc.spelled_stems(n) & {wc.stem(w) for w in wc.words(said)} for n in board.search['need'])
    if board.is_question and QUOTED.search(route) and not planned_thread and not on_topic(board, said):
        return False, 'not about what was asked'
    if board.is_question and len(said.split()) <= 2 and not re.search(r'\d', said) and len(board.asked.split()) > 5 and re.search(
            r'(?i)\band\b', board.asked):
        return False, 'one word to a question with two parts'
    return True, 'accepted'


def trusted(draft):
    """A reply from an exact or authored source of CAEL's own, which no search or general guidance should replace."""
    route = str(draft.get('route', ''))
    said = str(draft.get('response', ''))
    from .chat_memory import TRUSTED_MEMORY
    return bool((TRUSTED.search(route) or TRUSTED_MEMORY.search(route)) and not wc.DEAD_END.search(said) and not DEAD_ROUTE.search(route))


def research(board, messages, draft, exact, search=True):
    """The Researchers, called by the Generalist where it used to search alone: the exact finding if there is one, else
    the checked-passage search. No page search when the Counsellor already has an answer of the right shape, or when an
    earlier search in this task found nothing (the same pages would be read again)."""
    route = str(draft.get('route', ''))
    if exact is not None and not trusted(draft):
        try:
            found = exact.result(timeout=14)
        except Exception:
            found = None
        if found:
            board.note('Researcher (exact)', f'{found.get("details", "")[:140]}')
            return dict(found, replaced_route=route, replaced_because='exact value found')
        board.note('Researcher (exact)', 'no certain value')
    if board.advice is not None or not search or board.searched:
        return draft
    looked_up = messages
    if board.is_question and board.question and board.asked and board.question.rstrip('?').lower() != board.asked.rstrip('?').lower() \
            and messages is board.messages:
        looked_up = messages[:-1] + [dict(role='user', content=board.question)]     # "them" written out: "the northern lights"
    wc.STATE['plan'] = board.search          # the Planner's search plan: shape, subject, wordings, sites
    try:
        improved = wc.improve(looked_up, draft)
    finally:
        wc.STATE['plan'] = None
    if improved is not draft:
        board.searched = True
        board.note('Researcher (pages)', f'{improved.get("route")}')
        if improved.get('route') in ('chat/web-single', 'chat/web-closest') and re.match(r'chat/(?:core-knowledge|local-knowledge)', route) and on_topic(
                board, str(draft.get('response', ''))) and not DEAD_TEXT.search(str(draft.get('response', ''))):
            board.note('Critic', 'kept the authored answer: the passage found was unconfirmed')
            return draft
    return improved


def on_topic(board, said):
    """Does a reply share a weighty word with what was asked? (a quoted or stock reply about something else does not)"""
    asked = {wc.stem(w) for w in wc.content(board.asked or board.last) if wc.weight(w) > 4 and w not in wc.GENERIC}
    if not asked:
        asked = {wc.stem(w) for w in wc.content(board.last) if w not in wc.GENERIC}
    have = {wc.stem(w) for w in wc.words(said)}
    return not asked or bool(asked & have)


def last_resort(board, reason):
    """The Editor's honest reply when no agent had an answer: what was tried, and what would help."""
    if board.numeric:
        text = (f"I couldn't work that out reliably from what I have, and I'd rather not give you a wrong figure. Could you give me the numbers "
                f"in one line (for example the amounts, and what to do with them)? Then I'll calculate it step by step.")
    elif board.is_question:
        text = ("I don't have a reliable answer to that: my own notes don't cover it and I couldn't find a source that answers it directly, "
                "so I won't guess. If you tell me a bit more about your situation, or ask about one part of it, I can be more useful.")
    else:
        text = "Thanks for telling me. What would you like to do with that: talk it through, or get some practical suggestions?"
    return dict(route='chat/team-last-resort', response=text, sources=[], details=f'No agent produced an acceptable reply ({reason}).')


SURE_THREAD = 0.85


def prefer_schema(board, messages, got):
    """A stored thread the ranker is not sure of gives way to a specific advice sub-schema for this problem ("a friend who
    always cancels", "a child who wants to quit piano"): general advice on the point beats a quote on the side of it."""
    if not got or got.get('route') != 'chat/web-single' or got.get('rank_prob', 1.0) >= SURE_THREAD or board.numeric:
        return got
    try:
        from . import advice_schemas
        sch = advice_schemas.respond(messages)
    except Exception:
        sch = None
    if sch and sch.get('specific'):
        board.note('Advisor', f'a specific sub-schema instead of a thread the ranker was unsure of ({got.get("rank_prob", 0):.2f})')
        return dict(sch, replaced_route='chat/web-single')
    return got


def sign(board, result, agent):
    board.note('Editor', f'took the reply of {board.meesix(agent)}')
    out = dict(result)
    out['team'] = [dict(agent=a, did=w, at=t) for a, w, t in board.log]
    if threading.current_thread() is threading.main_thread() or not meesix.LAST:
        meesix.LAST[:] = [(a, board.last, w, t) for a, w, t in board.log]
    out.setdefault('agents', len({a for a, _, _ in board.log}))
    return out


PROBLEM_TOLD = re.compile(
    r"(?i)\b(?:won'?t|wont|doesn'?t|don'?t|isn'?t|aren'?t|can'?t|cannot|keeps?|refuses?|has started|have started|started|stopped|"
    r"(?:is|are|'s|'re|got|getting|gone|going|seems?|looks?)\s+(?:really |very |so |quite |a bit |too |all )?"
    r"(?:blunt|draughty|drafty|freezing|cold|damp|mouldy|moldy|wobbly|squeaky|stuck|loose|leaking|leaky|dripping|blocked|clogged|cracked|broken|"
    r"slow|noisy|smelly|dirty|stained|soft|mushy|yellow|brown|droopy|wilting|dying|dead|flat|sticky|rusty|faded|tight|itchy|sore|"
    r"(?:\w+ )?(?:and )?see-through)|snores?|snoring|overwatered|underwatered|takes? (?:about |over |nearly )?(?:\d+|an?|one|two|three|four|five) hours?|"
    r"(?:has|have|had) been (?:\w+ )?\w+ing|(?:has|have) (?:gone|turned|got|become) (?:\w+ ){0,2}?(?:black|mouldy|moldy|brown|yellow|green|white|grey|"
    r"rusty|stiff|loose|bad|worse)|keeps? \w+ing|(?:is|are) \w+ing (?:all the time|constantly|every \w+)|constantly|all the time|for (?:weeks|months|days|ages)|"
    r"every (?:night|morning|day|time)|awful|terrible|horrible|a nightmare|driving (?:me|us) (?:mad|crazy|nuts|up the wall)|fight(?:s|ing)?|argu(?:e|es|ing)|"
    r"plucking|chirping|beeping|biting|barking|scratching|leaking|dripping|peeling|flickering|rattling|tripping)\b")
TOLD_THING = re.compile(r"(?i)^\s*(?:(?:ugh|help|oh no|so|well|hi|hey|argh|right)[,!.]*\s+)*(?:i think\s+|i'?m pretty sure\s+|it seems\s+)?"
                        r"(?:my|our|the|one of (?:the|our|my)|both (?:of )?(?:the|our|my))\s+(?:[a-z'-]+\s+){0,6}?"
                        r"(?:is|are|has|have|keeps?|won'?t|doesn'?t|don'?t|isn'?t|aren'?t|can'?t|never|always|seems?|looks?|smells?|sounds?|feels?|gets?|got|"
                        r"went|goes|started|stopped|turned|takes?|makes?|leaves?|comes?|runs?|drips?|leaks?|sticks?|rattles?|squeaks?|"
                        r"[a-z]+(?:s|ed))\b")
NEUTRAL_TOLD = re.compile(r"(?i)\b(?:is|are) (?:called|named|coming|visiting|arriving|due|booked|on (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b|"
                          r"\b(?:is|are|turned|turns) (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)(?: years?| months?)?(?: old)?\s*[.!]?\s*$|"
                          r"(?<!smells )(?<!smell )(?<!looks )(?<!sounds )(?<!feels )(?<!tastes )\b(?:loves?|likes?|adores?|enjoys?)\b|\bis my (?:favou?rite|best)\b|\b(?:arrived|came|got here|passed|won(?!'|’)|is (?:a|an) (?:boy|girl))\b|"
                          r"\b(?:starts?|begins?|opens?|finishes?) (?:on|at|in|next|tomorrow)\b|\bmoved (?:in|to)\b|"
                          r"\b(?:is|are|turned|turns) (?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)(?: years?| months?)?(?: old)? (?:today|yesterday|last \w+|on \w+)\b|"
                          r"^\s*(?:my|our|the) [a-z'-]+(?: [a-z'-]+)? (?:is|are|was) (?:at|in) (?:[A-Z]|the |a |my |our |\w+'s)")


SITUATION = re.compile(r"(?i)^\s*(?:(?:we|i)(?:'ve| have) got|(?:we|i) have|we'?re (?:having|doing|going on|taking)|i'?m (?:having|doing|going on|taking))\s+"
                       r"(?:a|an|our|my|two|three|\w+-(?:hour|day|week))\b|^\s*(?:a|an)\s+[a-z]+(?:\s+[a-z]+)?\s+(?:came|fell|broke|has|is|keeps|won'?t|got)\b|"
                       r"^\s*there(?:'s| is| are)\s+(?:a |an |some |lots of |loads of |little |tiny )?[a-z]+(?:\s+[a-z]+)?\s+"
                       r"(?:\w+ing|in|on|under|all over|coming|growing)\b(?=.*\b(?:my|our|the)\b)")


def told_problem(text):
    """A statement about one of the user's things or people that says how it is behaving ("Our shower has really low pressure",
    "One of the tiles has cracked", "The kitchen sink is draining slowly"), not a plain fact about it ("My cat is called Tom")."""
    if '?' in text or len(text.split()) > 60:
        return False
    first = re.split(r'(?<=[.!])\s+', text.strip())[0]
    return bool((TOLD_THING.search(first) or PROBLEM_TOLD.search(text) or SITUATION.search(first)) and not NEUTRAL_TOLD.search(first))


WANT_TO = re.compile(r"(?i)^\s*(?:i|we)\s+(?:want|need|would like|'d like|am trying|'m trying|have|'ve got) to\s+((?!be\b|go\b|say\b|tell\b|talk\b|know\b)[a-z]+\b.{3,80}?)(?:[.!]|$)")


def problem_help(board, messages):
    """A problem told without a question ("My kitchen knives are really blunt", "I want to hang a heavy mirror") gets help
    straight away, the way a person would answer it: the Advisor's notes, or the best stored thread on it."""
    if board.is_question or len(board.last) > 400:
        return None
    from . import empath, advice_library
    felt = empath.respond(messages)
    if felt is not None and not re.search(r'a problem told|something (?:to plan|told)', str(felt.get('details', ''))):
        return None                         # something felt ("we didn't get the school"): the Listener answers that
    goal = WANT_TO.match(board.last)
    sticky = [t for t in advice_library.topics_in([board.last]) if t.key in advice_library.STICKY and t.words.search(board.last)]
    if sticky and not PROBLEM_TOLD.search(board.last):
        # a plan with a condition that shapes it ("a friend over for dinner, she's vegetarian"): ideas for it straight away
        got = board.do('Advisor', advice_library.respond, messages[:-1] + [dict(role='user', content=board.last + ' What could I make?')])
        if got and str(got.get('response', '')).strip():
            board.note('Planner', 'a plan told without a question: the Advisor offers ideas for it')
            return dict(got, response="That sounds lovely, and cooking vegetarian for a guest is easier than it sounds. " + str(got['response']))
    symptom = re.search(r"(?i)^\s*(?:i'?ve been|i have been|i keep|i'?m|i am|i)\s+(?:getting|having|waking up with|suffering from|got)\s+"
                        r"(?:a lot of |really bad |bad |awful |terrible |these |some )?(headaches?|migraines?|back ?ache|backache|stomach ?aches?|"
                        r"cramps?|nosebleeds?|heartburn|hiccups|nightmares|a sore \w+|a stiff \w+|sore \w+|pins and needles)\b", board.last)
    if not (told_problem(board.last) or goal or symptom):
        return None
    if re.search(r"(?i)\b(?:appointment|meeting|interview|flight|booked|birthday|party|open day|deadline)\b", board.last) or \
            re.search(r"(?i)\b(?:at|on|by) (?:\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|tonight)", board.last) and \
            not PROBLEM_TOLD.search(board.last):
        return None                         # a plan or a date: the diary and the memory take it
    if goal:
        asked = f"How do I {goal[1].strip()}?"
        opener = "Good project. Here's what people who have done it recommend."
    else:
        asked = board.last.rstrip('.!') + '. What can I do about it?'
        low = board.last.lower()
        # the opening line follows what the thing is (the subject of the sentence), not any word in it ("the kettle leaves bits")
        subj = (thing_of(board.last) or '').split()
        head = subj[-1] if subj else ''
        from .recall_agent import is_a
        kind = lambda *classes: bool(head) and any(is_a(head, c) or is_a(head.rstrip('s'), c) for c in classes)
        if re.search(r"\b(?:sore|itchy|hurts?|aches?|aching|headaches?|migraines?|cramps?|pains?|painful|stiff|sprain\w*|rash|nosebleeds?|"
                     r"heartburn|swollen|bruised?|backache)\b", low):
            opener = "Ouch, sorry to hear that."
        elif re.search(r"\b(?:toddler|baby|son|daughter|kids?|child|children|\w+-year-old|teen\w*)\b", ' '.join(subj) or low) or kind('child', 'juvenile'):
            opener = "That sounds exhausting, and it's very common at this age."
        elif re.search(r"\b(?:partner|husband|wife|boyfriend|girlfriend|flatmate|roommate|neighbou?r)\b", ' '.join(subj) or low):
            opener = "That sounds rough, especially night after night." if re.search(r"\bnights?\b|snor", low) else "That sounds frustrating."
        elif (kind('plant', 'herb', 'vegetable', 'flower', 'tree', 'shrub', 'grass') or re.search(r"\b(?:lawn|seedlings?|succulents?)\b", ' '.join(subj))) and \
                re.search(r"\b(?:plants?|leaf|leaves|lawn|grass|flowers?|trees?|bush|shrubs?|hedge|seedlings?|soil|garden|herbs?|succulents?|"
                          r"tomato\w*|courgettes?|roses?|basil|orchids?|cactus|fern|ivy|moss|weeds?)\b", low):
            opener = "Good that you've spotted it; plants often recover if you act early."
        elif kind('animal', 'pet', 'bird', 'rodent', 'dog', 'cat'):
            opener = "Poor thing. It's worth keeping an eye on." if re.search(r"\b(?:sick|ill|losing|not eating|isn'?t eating|limp|bleed|lump)\b", low) else \
                "That's a common one, and it can usually be trained out of them."
        else:
            opener = "That sounds annoying, but it's usually fixable."
    told = messages[:-1] + [dict(role='user', content=asked)]
    got = None
    try:
        got = board.do('Advisor', advice_library.respond, told)
    except Exception:
        got = None
    from .applicability import conflict
    if got and (not str(got.get('response', '')).strip() or conflict(' '.join(board.turns[-4:]), str(got.get('response', '')))):
        got = None                          # the Advisor's note is about something else ("phone battery" for a smoke alarm)
    if got is None:
        try:
            # searched as the follow-up a person would ask next, so the Planner reads the told problem as the scene
            told = messages + [dict(role='assistant', content='I see.'), dict(role='user', content='How do I do that?' if goal else 'What can I do about it?')]
            helper = Board(told)
            plan(helper)
            if helper.search:
                helper.search['strict'] = True      # unasked help must be about the told problem itself
            got = board.do('Researcher (pages)', wc.local_search, helper.search, told) if helper.search else None
            if not got and helper.search and os.environ.get('CAEL_WEB_SEARCH', '1') != '0':
                # nothing in CAEL's own index: the Researcher's full search (Stack Exchange, Wikimedia) with the same plan
                wc.STATE['plan'] = helper.search
                try:
                    near = board.do('Researcher (pages)', wc.answer, told)
                finally:
                    wc.STATE['plan'] = None
                if near and near.get('route') in ('chat/web-checked', 'chat/web-single', 'chat/threads'):
                    ok, _ = review(helper, near)
                    got = near if ok else None
        except Exception:
            got = None
    if got and conflict(' '.join(board.turns[-4:]), str(got.get('response', ''))):
        got = None
    if got and got.get('route') == 'chat/web-single':
        follow = messages + [dict(role='assistant', content='I see.'), dict(role='user', content='How do I do that?' if goal else 'What can I do about it?')]
        try:
            from . import advice_schemas
            sch = advice_schemas.respond(follow)
        except Exception:
            sch = None
        if sch and sch.get('specific'):
            board.note('Advisor', 'a specific sub-schema for the problem told, before any thread')
            got = dict(sch, replaced_route='chat/web-single')
    if not got:
        thing = thing_of(board.last)
        try:
            from .retrieval import thing_and_problem
            parts, _ = thing_and_problem([board.last])
            if thing and parts:
                thing = ' '.join(parts)         # "builder left" is not a thing: the index never titles it so
        except Exception:
            pass
        thing = thing or (symptom[1].lower() if symptom else None)       # "I've been getting headaches": the headaches
        if goal or not thing:
            return None
        try:
            from . import advice_schemas
            general = advice_schemas.respond(messages + [dict(role='assistant', content='I see.'), dict(role='user', content='What can I do about it?')], thing)
        except Exception:
            general = None
        if general:
            board.note('Planner', 'a problem told without a question: general advice for this class of thing')
            return dict(general, response=f"{opener} {general['response']}")
        # nothing reliable to suggest yet: what a person would ask next, about the thing itself, instead of a stock reply
        board.note('Planner', 'a problem told without a question, and no answer found yet: ask what would narrow it down')
        return dict(route='chat/problem-ask', sources=[], details='A told problem with no matching answer found; questions that narrow it down (team.py).',
                    response=f"{opener} To point you to the right fix for the {thing}: how long has it been happening, did anything change just "
                             f"before it started, and have you tried anything yet? Even a small detail helps me find what usually solves it.")
    board.note('Planner', f'a problem told without a question: answered as "{asked}"')
    text = str(got['response'])
    text = re.sub(r"^(?:From what I found, this is what usually works|From what I found|What I found, to help you weigh it up):\s*", 'From what I found: ', text)
    return dict(got, response=f'{opener} {text}', route=str(got.get('route', 'chat/advice')), details=str(got.get('details', '')) + ' (answered a problem told without a question)')


def single(messages, engine, options):
    """One task through the team, then the coherence check: a follow-up's answer stays on the conversation's thing."""
    board = Board(messages)
    plan(board)
    draft = _single(messages, engine, options, board)
    try:
        from . import coherence
        if os.environ.get('CAEL_COHERENCE', '1') != '0':
            draft = coherence.keep_on_topic(messages, board, draft)
            # still general advice (or still off the thing) for a practical follow-up: ask the follow-up on its own, about the
            # thing by name ("How do I clean them?" -> "How do I clean my car brakes?"), the way a person would look it up
            ask = coherence.resolved_question(messages)
            if ask and (str(draft.get('route', '')) in ('chat/advice-schema', 'chat/team-last-resort') or coherence.off_topic(messages, draft)
                        or coherence.repeated(messages, str(draft.get('response', '')))):
                alone = [m for m in messages if m.get('role') == 'system'] + [dict(role='user', content=ask)]
                b2 = Board(alone)
                plan(b2)
                again = _single(alone, engine, options, b2)
                if again and coherence.QUOTING.match(str(again.get('route', ''))) and not coherence.off_topic(messages, again) \
                        and not coherence.repeated(messages, str(again.get('response', ''))):
                    draft = dict(again, coherence=f'the follow-up asked on its own: "{ask}"', replaced_route=draft.get('route'))
    except Exception:
        pass
    try:
        # a looked-up passage or advice may answer only when it supplies what was asked about the thing named (evidence.py)
        from . import evidence
        if os.environ.get('CAEL_EVIDENCE_CHECK', '1') != '0':
            draft = evidence.check(messages, draft)
    except Exception:
        pass
    try:
        # never the same answer twice in a row: say so and ask which part to go into (a repeat reads as not listening)
        said = [m.get('content') or '' for m in messages[:-1] if m.get('role') == 'assistant']
        new = str(draft.get('response', '')).strip()
        route = str(draft.get('route', ''))
        looked_up = QUOTED.match(route) or route.startswith(('chat/concept', 'chat/core-', 'chat/web-', 'chat/local-', 'chat/advice-schema'))
        if looked_up and said and new and len(new) > 40 and new[:80] == said[-1].strip()[:80]:
            draft = dict(route='chat/no-repeat', sources=[], replaced_route=draft.get('route'),
                         details='The draft repeated the previous reply word for word (team.single).',
                         response="I don't have more on that than what I just said, and I'd rather not repeat it. "
                                  "Which part would you like me to go into, or is there a more specific question I can try?")
    except Exception:
        pass
    return draft


def _single(messages, engine, options, board):
    """One task through the team."""
    try:
        # questions about CAEL itself and the clock (about_me.py): true answers, never a definition of "internet" or "time"
        from . import about_me
        me = board.do('Host', about_me.respond, messages)
        if me is not None:
            return sign(board, me, 'the Host')
    except Exception:
        pass
    try:
        # jokes, a recipe step said on its own, and common myths (common_asks.py), before any page search
        from . import common_asks
        common = board.do('Host', common_asks.respond, messages)
        if common is not None:
            return sign(board, common, 'the Host')
    except Exception:
        pass
    try:
        # word problems, puzzles and rules about individuals worked out exactly (reasoner.py), and follow-ups on its last result
        from . import reasoner
        worked = board.do('Reasoner', reasoner.respond, messages)
        if worked is not None:
            return sign(board, worked, 'the Reasoner')
    except Exception:
        pass
    try:
        # an everyday situation and its short follow-ups, which keep their subject from the earlier turns (situations.py)
        from . import situations
        handled = board.do('Coach', situations.respond, messages)
        if handled is not None:
            return sign(board, handled, 'the Coach')
    except Exception:
        pass
    if not board.is_question:
        try:
            # "My phone contract is $38 a month." told without a question: the Calculator converts it (not a told problem)
            from . import calc_agent
            rated = calc_agent.stated_rate(messages)
            if rated is not None:
                return sign(board, rated, 'the Calculator')
        except Exception:
            pass
    if not board.is_question:
        # something felt ("I'm dreading it", "I feel like I've let him down") is answered as a feeling first, before the
        # diary notes the day it falls on
        try:
            # once the Supporter has taken a situation (it replied before), it carries the conversation on: the next thing
            # told is answered in that situation, not with a fresh generic acknowledgement
            from . import support as _support
            said = [m.get('content') or '' for m in messages[:-1] if m.get('role') == 'assistant']
            ours = said and any(said[-1].startswith(t[:40]) for d in (_support.ACK, _support.LEAD_DO) for t in d.values()) or \
                (said and any(said[-1].startswith(c['ack'][:30]) for c in _support.CHILD.values()))
            # ... and a situation it recognises in what was just told (a loved one's surgery, a pet put down, a builder who took the
            # money) is its from the first turn, before a generic acknowledgement or a diary note
            if ours or _support.claims(messages):
                held = board.do('Supporter', _support.respond, messages)
                if held is not None:
                    return sign(board, held, 'the Supporter')
        except Exception:
            pass
        try:
            from . import empath
            if empath.LOW.search(board.last) or empath.NERVES.search(board.last):
                felt = board.do('Listener', empath.respond, messages)
                said = [m.get('content') or '' for m in messages[:-1] if m.get('role') == 'assistant']
                if felt is not None and not (said and said[-1][:40] == str(felt.get('response', ''))[:40]):
                    return sign(board, felt, 'the Listener')    # (never the same words twice: the Supporter goes on from there)
        except Exception:
            pass
    try:
        # an emotional conversation over several turns (support.py): the situation the user is in, not each turn's words
        from . import support
        held = board.do('Supporter', support.respond, messages)
        if held is not None:
            return sign(board, held, 'the Supporter')
    except Exception:
        pass
    try:
        # Python questions, error messages and changes to code just written (python_answers.py): checked, authored answers,
        # before any search that would quote a forum thread on the question's few words
        from . import python_answers
        coded = board.do('Programmer', python_answers.respond, messages)
        if coded is not None:
            return sign(board, coded, 'the Programmer')
    except Exception:
        pass
    try:
        # "Give me three ideas for ...", "The second one sounds good, what would we need?", "Tell me a fun fact" (ideas.py)
        from . import ideas
        thought = board.do('Ideas', ideas.respond, messages)
        if thought is not None:
            return sign(board, thought, 'the Ideas desk')
    except Exception:
        pass
    try:
        # "Explain inflation in simple terms", "Why do onions make you cry?" and their follow-ups: the authored explanations
        # (concepts.py, chat_core.EXPLAIN) before a web search that quotes a forum thread on the question's few words
        from . import concepts, beginner, tips
        known = (board.do('Explainer', concepts.respond, messages) or board.do('Coach', tips.respond, messages)
                 or board.do('Coach', beginner.respond, messages))
        if known is not None:
            return sign(board, known, 'the Explainer' if str(known.get('route', '')).startswith('chat/concept') else 'the Coach')
        if board.is_question or re.search(r"(?i)^\s*(?:explain|tell me (?:about|why|how))\b", board.last):
            from .chat_core import explain_reply
            told = board.do('Explainer', explain_reply, messages)
            if told is not None and str(told.get('response', '')).strip():
                return sign(board, told, 'the Explainer')
    except Exception:
        pass
    try:
        # the next question about an everyday problem told earlier ("Is it the pads?", "How do I clean them?"): what a person who
        # knows the subject says (followup_kb.py), before a search on the follow-up's few words
        from . import followup_kb
        known = board.do('Advisor', followup_kb.respond, messages)
        if known is not None:
            return sign(board, known, 'the Advisor')
    except Exception:
        pass
    helped = problem_help(board, messages)
    if helped is not None:
        return sign(board, helped, 'the Advisor' if helped.get('route') == 'chat/advice' else 'Researcher (pages)')
    if re.search(r"(?i)\banswer only with\b|\b(?:reply|respond|answer) with (?:only|just)\b|\bonly (?:give|output|return)\b|\bjust (?:the|give) (?:number|answer)\b", board.last):
        board.note('Planner', 'an answer format was asked for: the pipeline that keeps output contracts answers')
        meesix.INSIDE.plain = True          # the pipeline's own nested calls must not bring the team back in
        try:
            draft = engine.respond(messages, _agents=False, **options)
        finally:
            meesix.INSIDE.plain = False
        return sign(board, draft, 'Generalist')
    for name, module in DESK:
        try:
            mine = board.do(name, __import__('cael_unified.' + module, fromlist=['respond']).respond, messages)
        except Exception:
            mine = None
        if mine is not None:
            ok, why = review(board, mine)
            board.note(name, f'{mine.get("route")}: {why}')
            if ok:
                return sign(board, mine, name)
    solved = None
    try:
        solved = board.do('Solver', meesix.specialists, messages)
    except Exception:
        solved = None
    if solved is not None:
        ok, why = review(board, solved)
        board.note('Solver', f'{solved.get("route")}: {why}')
        if ok:
            return sign(board, solved, 'the Solver')
    exact = None
    if board.fact and os.environ.get('CAEL_WEB_SEARCH', '1') != '0' and os.environ.get('CAEL_EXACT_WEB', '1') != '0':
        from . import exact_web
        inside = getattr(meesix.INSIDE, 'task', False)
        exact = POOL.submit(exact_web.answer, messages) if inside else POOL.submit(board.do, 'Researcher (exact)', exact_web.answer, messages)
    if board.is_question:
        try:
            from . import counsel
            board.advice = board.do('Counsellor', counsel.reply, messages)
            if board.advice is not None:
                fits, why_not = review(board, board.advice)
                if not fits:
                    board.note('Counsellor', f'general guidance set aside: {why_not}')
                    board.advice = None         # the Researchers look instead
        except Exception:
            board.advice = None

    def hook(msgs, draft):
        return research(board, msgs, draft, exact if msgs is messages else None)
    draft = board.do('Generalist', engine.respond, messages, _agents=False, _improve=hook, **options)
    ok, why = board.do('Critic', review, board, draft)
    board.note('Generalist', f'{draft.get("route")}: {why}')
    route = str(draft.get('route', ''))
    if board.advice is not None and route != 'chat/web-exact' and not trusted(draft) and not (
            ok and re.match(r'chat/(?:core-knowledge|local-knowledge|web-checked$)', route) and on_topic(board, str(draft.get('response', '')))):
        # the question has a known everyday shape and nothing exact or on the point came back: general guidance fits best
        board.note('Counsellor', 'general guidance for this kind of question')
        return sign(board, dict(board.advice, replaced_route=route), 'the Counsellor')
    if ok:
        draft = prefer_schema(board, messages, draft)
        return sign(board, draft, 'the Generalist' if not draft.get('replaced_route') else
                    'Researcher (exact)' if draft.get('route') == 'chat/web-exact' else 'Researcher (pages)')
    # statements and the question about them in one message: the question again, with the statements as an earlier turn
    told = meesix.unfold(messages)
    if told:
        try:
            again = meesix.specialists(told) or engine.respond(told, _agents=False, _improve=lambda m, d: research(board, m, d, None, search=False), **options)
            ok2, why2 = review(Board(told), again)
            board.note('Generalist (statements first)', f'{again.get("route")}: {why2}')
            if ok2 and trusted(again):
                return sign(board, dict(again, replaced_route=route), 'Generalist (statements first)')
        except Exception:
            pass
    # a follow-up put as a full question ("So why shouldn't you put metal in a microwave oven?")
    if board.is_question and board.question and board.question.rstrip('?').lower() not in board.last.lower() and time.perf_counter() - board.started < 14:
        full = messages[:-1] + [dict(role='user', content=board.question)]
        try:
            board.searched = False
            again = meesix.specialists(full) or engine.respond(full, _agents=False, _improve=lambda m, d: research(board, m, d, None), **options)
            again_board = Board(full)
            again_board.search = board.search        # the same plan: what the answer must be about
            ok2, why2 = review(again_board, again)
            board.note('Generalist (full question)', f'{again.get("route")}: {why2}')
            if ok2:
                again = prefer_schema(board, messages, again)
                return sign(board, dict(again, replaced_route=route), 'Generalist (full question)')
        except Exception:
            pass
    if board.is_question and not board.numeric and os.environ.get('CAEL_WEB_SEARCH', '1') != '0' and len(board.turns) > 1:
        try:
            from . import exact_web
            inside = board.do('Researcher (exact)', exact_web.within, messages)
        except Exception:
            inside = None
        if inside:
            ok2, why2 = review(board, inside)
            board.note('Researcher (exact)', f'{inside.get("details", "")[:120]}: {why2}')
            if ok2:
                return sign(board, dict(inside, replaced_route=route), 'Researcher (exact)')
    if board.is_question and not board.numeric and not board.searched and os.environ.get('CAEL_WEB_SEARCH', '1') != '0' \
            and (board.search or wc.wants_info(messages)) and time.perf_counter() - board.started < 20:
        # nothing has been looked up yet (the first reply came from memory and was sent back): one page search
        try:
            wc.STATE['plan'] = board.search
            near = board.do('Researcher (pages)', wc.answer, messages[:-1] + [dict(role='user', content=board.question)] if board.question else messages)
        except Exception:
            near = None
        finally:
            wc.STATE['plan'] = None
        if near and near.get('route') in ('chat/web-checked', 'chat/web-single', 'chat/web-exact', 'chat/threads', 'chat/destination'):
            board.note('Researcher (pages)', f'{near.get("route")} after the first reply was sent back')
            near = prefer_schema(board, messages, near)
            return sign(board, dict(near, replaced_route=route), 'Researcher (pages)')
    if not REPLACEABLE.search(route) and why in ('dead end', 'accepted') or (os.environ.get('CAEL_WEB_SEARCH', '1') == '0' and route.startswith('chat/web-')):
        board.note('Editor', 'nothing better was found: the first reply stands')
        return sign(board, draft, 'Generalist')
    if not board.is_question:
        try:
            from . import empath
            board.note('Listener', 'a plain reply to what was told')
            return sign(board, dict(empath.companion(messages), replaced_route=route), 'the Listener')
        except Exception:
            pass
    if board.is_question and len(board.turns) > 1:
        try:
            more = board.do('Researcher (pages)', wc.continue_thread, messages, board.search)
        except Exception:
            more = None
        if more:
            more = prefer_schema(board, messages, dict(more, rank_prob=0.5))
            board.note('Researcher (pages)', 'read on in the thread quoted before')
            return sign(board, dict(more, replaced_route=route), 'Researcher (pages)')
    try:
        # a story sum the quantity helpers could not read ("He gives 1 to Sue and buys 4 more"): the Reasoner follows it
        # step by step, only after every other desk, so their checked answers and explanations come first
        from . import reasoner
        told = board.do('Reasoner', reasoner.story_reply, messages)
    except Exception:
        told = None
    if told:
        return sign(board, dict(told, replaced_route=route), 'the Reasoner')
    if board.is_question and not board.numeric:
        try:
            from . import advice_schemas
            general = board.do('Advisor', advice_schemas.respond, messages)
        except Exception:
            general = None
        if general:
            board.note('Advisor', 'general advice for this class of thing')
            return sign(board, dict(general, replaced_route=route), 'the Advisor')
    final = last_resort(board, why)
    return sign(board, dict(final, replaced_route=route), 'Editor')


def run(messages, engine, **options):
    """Answer the last user message with the team. A message with several separate tasks gets one team per task, at most
    six tasks at a time (meesix.run)."""
    last = messages[-1]['content']
    if os.environ.get('CAEL_EXACT_FIRST', '1') != '0':
        try:
            # 0.4.4: exact readers for everyday reasoning over the whole conversation (pack
            # costs, tills, shares owed, rates, clock and calendar sums, labelled accounts with rules, corrections and
            # withdrawals, renamed things, hidden or future outcomes, false premises). Each reads one shape completely or
            # stays silent, so it goes first: before it, keywords sent these to advice templates or web pages.
            # Think first, as a swarm (think.py): every exact reader proposes an answer to several readings of the
            # question, each proposal is checked (answer type; a sum must be derivable from the stated numbers), and
            # the best-supported checked answer is given. Nothing checked: the usual pipeline answers.
            from . import think
            exact = think.run(messages)
            if exact is not None:
                board = Board(messages)
                for a in (exact.get('think') or {}).get('answers', [])[:3]:
                    board.note('Thinker', f'{a["answer"]!r}: support {a["support"]} from {", ".join(a["readers"])} ({a["check"]})')
                return sign(board, exact, 'the Thinker')
        except Exception:
            pass
    try:
        # "Why?" after "The capital of Italy is **Rome**." means "Why is Rome the capital of Italy?" (common_asks.py)
        from . import common_asks
        meant = common_asks.why_question(messages)
        if meant:
            answered = run(messages[:-1] + [dict(messages[-1], content=meant)], engine, **options)
            return dict(common_asks.why_checked(meant, answered), asked_as=meant)
    except Exception:
        pass
    try:
        # labelled accounts or parts and one question: one reader per part, merged by the swarm rules (swarm.py);
        # checked before the task split, which would read "Witness 1: ... Witness 2: ..." as separate tasks
        from . import swarm
        merged = swarm.chat_reply(messages) if os.environ.get('CAEL_SWARM_DESK', '1') != '0' else None
        if merged is not None:
            board = Board(messages)
            readers = (merged.get('swarm') or {}).get('readers') or []
            board.note('Swarm', f'had {len(readers)} readers ({", ".join(readers)}) each read one part, then merged their claims')
            return sign(board, merged, 'the Swarm')
    except Exception:
        pass
    if len(meesix.tasks_of(last)) > 1:
        done = meesix.run(messages, engine, **options)
        if done is not None:
            return done
    try:
        # several readings of one message worked on at once, the best-grounded reply picked by rules (swarm_compute.py)
        from . import swarm_compute
        combined = swarm_compute.run(messages, single, engine, options)
        if combined is not None:
            return combined
    except Exception:
        pass
    return single(messages, engine, options)


_WARM = threading.Lock()
_WARMED = []


def warm():
    """Load what every Mr. Meesix needs once, before agents start side by side (six agents loading the same modules and
    databases at once on the first message made each of them wait for the others)."""
    with _WARM:
        if _WARMED:
            return
        try:
            for _, module in DESK:
                __import__('cael_unified.' + module)
            from . import exact_web, researchers, stack_source, open_chat  # noqa: F401
            if open_chat.db():
                open_chat.site_sizes()
                open_chat.idf(open_chat.stem('water'))
                open_chat.is_noun('water')
        except Exception:
            pass
        _WARMED.append(True)
