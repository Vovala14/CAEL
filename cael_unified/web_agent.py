"""Mr. Meesix on a web page: a small team that carries out an instruction in a browser, one action at a time.

The other Mr. Meesix agents answer a message (team.py). These act: given an instruction ("Search the catalogue for
"neural", then use the Year dropdown to show papers since 2018 and tell me how many there are") and what is on the
page right now, they say what to do next (click this, type that, choose this option) until the job is done, and then
give the answer if one was asked for. The jobs, each a plain function that keeps nothing but the board:

  Planner    cuts the instruction into steps in the order they are asked (sign in, search, filter, sort, open, switch
             something on, fill a form, delete, export, report) and pulls out what each step names: quoted text,
             field/value pairs, dates, times, numbers, credentials.
  Scout      reads the page it is handed: the visible controls with their labels, the listed records, the tables.
  Navigator  finds the control a step needs by the words on it. An option or chip whose text the instruction mentions
             is the one to choose; a link is followed when its words are the step's words. When nothing on the page
             fits, it opens the menu entry that does, once.
  Clerk      fills forms: each value goes to the field whose label names it, then the form is submitted.
  Reader     answers "how many", "what is the X of Y", "which is first" from the records, tables and labelled values
             on the page.
  Critic     keeps count: no action is repeated on the same page, a step that cannot move on is given up, and the run
             ends when the steps are done or the budget is spent.

There is no model here: words are matched after stemming, with a table of everyday synonyms (SAME) and, optionally, a
table of word pairs counted from recorded demonstrations (`lexicon`: instruction word -> control word). The page is
data: its text is matched and quoted, never followed as an instruction.

The agent does not drive a browser itself. The caller gives `act(observation)` a dict (see `Scout`) and carries out the
returned action: {'op': 'click'|'fill'|'type'|'select'|'check'|'range'|'press'|'scroll'|'goto'|'done', 'id': ...}.
"""
import calendar
import datetime
import re

STOP = set('''a an the of to in on at for by with from and or then also please my your our their his her its this that these those
i you we me it is are was were be been do does did can could should would will so as if into onto up out about using use
via through over under after before again all any each every both some there here just only not no yes than too very
tell report give show find get let make sure me us them he she they what which who whom whose where when how many much
s t ll re ve d m site website page app'''.split())
SAME = {                        # everyday synonyms: a step's word -> words a control may carry
    'search': 'search find query lookup q keyword', 'login': 'login signin sign log username password', 'sign': 'sign login signin log',
    'delete': 'delete remove trash discard erase', 'remove': 'remove delete trash', 'create': 'create new add compose start post',
    'new': 'new create add compose', 'add': 'add new create plus', 'post': 'post publish submit create share', 'publish': 'publish post submit',
    'save': 'save bookmark keep library store', 'star': 'star favorite favourite', 'favorite': 'favorite favourite star heart',
    'like': 'like heart love', 'upvote': 'upvote up vote', 'downvote': 'downvote down vote', 'follow': 'follow', 'subscribe': 'subscribe follow notify',
    'join': 'join', 'pin': 'pin', 'install': 'install get', 'cart': 'cart basket bag', 'wishlist': 'wishlist wish', 'watchlist': 'watchlist watch',
    'export': 'export download csv', 'download': 'download export save', 'email': 'email mail compose message', 'send': 'send submit post',
    'message': 'message chat send reply', 'reply': 'reply respond answer', 'comment': 'comment reply', 'book': 'book schedule reserve appointment',
    'schedule': 'schedule book new create', 'pay': 'pay payment', 'buy': 'buy purchase order cart', 'cancel': 'cancel', 'edit': 'edit update change modify rename',
    'rename': 'rename edit title name', 'update': 'update edit save change', 'change': 'change edit update', 'apply': 'apply submit', 'share': 'share',
    'setting': 'setting settings preferences options account profile', 'newest': 'newest latest recent new date', 'latest': 'latest newest recent date',
    'recent': 'recent newest latest date', 'oldest': 'oldest old date earliest', 'cheapest': 'cheapest price low lowest', 'expensive': 'expensive price high highest',
    'lowest': 'lowest low ascending asc', 'highest': 'highest high descending desc top', 'rated': 'rated rating top best', 'rating': 'rating rated stars',
    'popular': 'popular top most', 'alphabetically': 'alphabetically alphabetical name title az', 'log': 'log add record new', 'play': 'play start listen watch',
    'open': 'open view details', 'copy': 'copy', 'upload': 'upload attach file choose', 'home': 'home homepage', 'dashboard': 'dashboard home overview',
}
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTH_RE = '(?:' + '|'.join(sorted(MONTHS, key=len, reverse=True)) + r')\.?'
VERBS = ('tell|report|open|click|leave|save|follow|sort|filter|search|delete|export|post|publish|send|email|set|select|choose|add|upvote|like|star|'
         'play|share|copy|submit|log|sign|go|use|create|return|answer|give|pay|book|join|cancel|update|change|rename|install|subscribe|message|'
         'reply|comment|find|show|remove|download|upload|attach|buy|schedule|apply|invite|pin|note|count|check|get|start|turn|enable|disable|write|edit')
KINDS = (
    ('login', r'^(?:sign|log) ?in\b|^login\b'),
    ('search', r'^search\b|^look up\b|^use .{0,60}\bsearch\b'),
    ('sort', r'^sort\b|\bsorted by\b'),
    ('filter', r'^filter\b|^show only\b|^use .{0,50}\b(?:dropdown|slider|filter)|^set the (?:minimum|maximum)|^restrict|^narrow|^show .{0,60}\b(?:tagged|marked|priced|from|only)\b'),
    ('delete', r'^(?:delete|remove)\b'),
    ('export', r'^(?:export|download)\b'),
    ('toggle', r'^(?:follow|unfollow|subscribe|star|save(?!\s+(?:(?:the|your|my|all|a|an|these|those)\s+)?(?:\w+\s+)?(?:settings?|changes?|results?|designs?|drafts?|configuration|grid|spreadsheet|notes?|policy|document|file|filter)\b|\s+it\b|\s+and\b|\s*$)|like|upvote|downvote|join|pin|bookmark|install|favorite|block)\b|'
               r'^add\b.{0,120}\bto (?:my |your |the )?(?:[\w&-]+ ){0,3}(?:cart|wishlist|watchlist|favorites|favourites|library|bookmarks|playlist)\b'),
    ('report', r'^(?:tell me|report|how many|how much|what|which|who|where|when|is |are |does |do |did |answer|according to|give me|provide|include|count)\b'),
    ('open', r'^(?:open|go to|view|visit|navigate|show|display|return to|find and open|check)\b'),
    ('form', r'^(?:create|add|post|publish|apply|book|schedule|set|change|update|rename|edit|pay|send|email|log|write|compose|submit|register|invite|reply|comment|'
             r'give|move|enable|disable|turn|buy|cancel|start|message|ask|file|enter|complete|share|upload|select|choose)\b'),
    ('find', r'^(?:find|locate|identify|note)\b'),
)
AFFIRM = re.compile(r'(?i)^(?:ok|okay|yes|confirm|delete|remove|save|continue|proceed|submit|apply|done|export|download|got it|yes, delete|i agree|agree|accept)\b')
SUBMIT = re.compile(r'(?i)\b(?:save|submit|create|post|send|apply|book|pay|confirm|publish|update|add|sign in|log in|login|continue|next|schedule|register|sign up|place order|done|go|search|filter|join|share|invite|rename|ok)\b')
DEFAULT_OPTION = re.compile(r'(?i)^(?:all|any|none|select|choose|--|default|sort by|all \w+|any \w+|select \w+.*)$')


def norm(text):
    t = str(text or '').replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('–', '-').replace('—', '-')
    return re.sub(r"(?<![\w'])'([^'\n]{2,80}?)'(?![\w'])", r'"\1"', t)           # 'name' used as a quotation


def stem(w):
    """A word's stem, the same for 'setting', 'settings', 'saved', 'save', 'saving'."""
    w = w.lower()
    if len(w) > 4 and w.endswith('ies'):
        w = w[:-3] + 'y'
    elif len(w) > 3 and w.endswith('s') and not w.endswith(('ss', 'us', 'is')):
        w = w[:-1]
    for suf in ('ion', 'ing', 'ed'):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[:-len(suf)]
            break
    if len(w) > 3 and w.endswith('e'):
        w = w[:-1]
    return w


def S(text):
    return {stem(w) for w in text.split()}


def words(text):
    return re.findall(r"[a-z0-9]+(?:[.'][a-z0-9]+)*", norm(text).lower().replace('&', ' and '))


def content(text):
    return [stem(w) for w in words(text) if w not in STOP]


def quotes(text):
    return [q.strip().rstrip('.,') for q in re.findall(r'"([^"]{1,300})"', norm(text))]


def numbers(text):
    return [float(x.replace(',', '')) for x in re.findall(r'(?<![\w.])\$?(\d[\d,]*(?:\.\d+)?)(?![\w/:])', norm(text))]


def dates(text):
    """Dates named in a text, in order: 'January 1 through March 31, 2025' -> [2025-01-01, 2025-03-31]; 'June 22-28, 2026' -> two;
    'January 2026' -> first and last day; 'in 2023' -> the year's ends."""
    t = norm(text).lower()
    found = []
    for m in re.finditer(rf'\b({MONTH_RE})\s+(\d{{1,2}})(?!\d)(?:st|nd|rd|th)?(?:\s*-\s*(\d{{1,2}}))?(?:,?\s+(\d{{4}}))?', t):
        found.append((m.start(), MONTHS[m[1].rstrip('.')], int(m[2]), int(m[4]) if m[4] else None, int(m[3]) if m[3] else None))
    years = [x[3] for x in found if x[3]]
    out = []
    for i, (pos, month, day, year, day2) in enumerate(found):
        year = year or next((x[3] for x in found[i + 1:] if x[3]), None) or (years[-1] if years else datetime.date.today().year)
        for d in (day, day2):
            if d:
                try:
                    out.append((pos, datetime.date(year, month, d)))
                except ValueError:
                    pass
    if not out:
        for m in re.finditer(rf'\b({MONTH_RE})\s+(\d{{4}})\b', t):
            y, mo = int(m[2]), MONTHS[m[1].rstrip('.')]
            out += [(m.start(), datetime.date(y, mo, 1)), (m.start(), datetime.date(y, mo, calendar.monthrange(y, mo)[1]))]
    if not out:
        m = re.search(r'\b(?:in|during|for|of|submitted in) ((?:19|20)\d{2})\b', t)
        if m:
            out = [(0, datetime.date(int(m[1]), 1, 1)), (0, datetime.date(int(m[1]), 12, 31))]
    return [d for _, d in sorted(out, key=lambda x: x[0])]


def times(text):
    """'9:30 AM', '10 a.m.', '7:00 PM' -> ['09:30', '10:00', '19:00']."""
    out = []
    for m in re.finditer(r'\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)(?![a-z])', norm(text).lower()):
        h, mi, pm = int(m[1]) % 12, int(m[2] or 0), m[3].startswith('p')
        out.append(f'{h + (12 if pm else 0):02d}:{mi:02d}')
    return out


SAME_STEM = {stem(k): S(v) for k, v in SAME.items()}


class Step:
    def __init__(self, kind, text):
        self.kind, self.text = kind, text
        self.quotes = quotes(text)
        self.words = content(text)
        self.fields = fields(text) if kind in ('form', 'login') else []
        self.state = {}
        self.spent = 0

    def __repr__(self):
        return f'<{self.kind}: {self.text[:60]}>'


def clauses(instruction):
    """The instruction as separate requests, in order. Quoted text is never cut."""
    text = norm(instruction).strip()
    held = []

    def hold(m):
        held.append(m[0])
        return f'\x00{len(held) - 1}\x00'
    text = re.sub(r'"[^"]*"', hold, text)
    text = re.sub(r'(?i)\bfind and open\b', 'open', text)
    text = re.sub(r'\b(e\.g|i\.e|vs|dr|mr|mrs|ms|st|a\.m|p\.m)\.', lambda m: m[0].replace('.', '\x01'), text, flags=re.I)
    parts = []
    for sent in re.split(r'(?<=[.?!])\s+(?=[A-Z\x00])', text):
        sent = '\x02' + sent
        parts += re.split(rf'\s*[,;]?\s*\b(?:and then|then|and|after that,?|next,?|finally,?)\s+(?=(?:{VERBS})\b)|\s*;\s*|,\s+(?=(?:{VERBS})\b)', sent, flags=re.I)
    out = []
    for p in parts:
        p = re.sub(r'\x00(\d+)\x00', lambda m: held[int(m[1])], p or '').replace('\x01', '.').strip(' ,')
        if len(p) > 2:
            out.append(p)
    return out


def kind_of(clause):
    low = re.sub(r'^(?:please|can you|could you|then|first|next|finally|after that|also|now|in [A-Z]\w+(?: \w+)?,)\s*,?\s*', '', clause.strip(), flags=re.I).lower()
    low = re.sub(r"^(?:in|on|from|under|for|during) [^,]{2,60},\s*", '', low)
    for kind, pattern in KINDS:
        if re.search(pattern, low):
            return kind
    return 'report' if clause.strip().endswith('?') else 'other'


def fields(text):
    """Named values in a request: 'titled "X"', 'username "u" and password "p"', 'as u with password p', 'set K to V'."""
    t = norm(text)
    out = []
    m = re.search(r'(?i)\b(?:as|username|user name|user)\s+"?([^\s",]+)"?\s+(?:and|with)\s+(?:the\s+)?password\s+"?(\S+?)"?(?=[\s,;]|\.?$|\.\s)', t)
    if m:
        out += [('username', m[1]), ('password', m[2].rstrip('.'))] if not m[2].endswith('..') else []
    for m in re.finditer(r'((?:[A-Za-z][\w-]*\s+){1,3})"([^"]+)"', t):
        key = [w for w in words(m[1]) if w not in STOP and w not in ('titled', 'named', 'called', 'saying', 'says', 'reads', 'entitled')]
        lead = words(m[1])
        if lead and lead[-1] in ('titled', 'entitled'):
            key = ['title']
        elif lead and lead[-1] in ('named', 'called'):
            key = ['name']
        elif lead and lead[-1] in ('saying', 'says', 'message', 'text', 'body', 'that', 'comment', 'sentence'):
            key = ['message']
        if m[2] not in [v for _, v in out]:
            out.append((' '.join(key[-2:]) or 'text', m[2].strip()))
    for m in re.finditer(r'(?i)\b(?:set|change|update|switch)\s+(?:the\s+|my\s+|your\s+)?([\w\' -]{2,50}?)\s+(?:from .{1,40}?\s+)?to\s+("[^"]+"|[\w$%.,:/ -]{1,60}?)(?=,|\.|;|$|\s+and\s|\s+then\s)', t):
        out.append((m[1].strip(), m[2].strip('" ')))
    for m in re.finditer(r'(?i)\b(email|subject|password|username|display name|title|name|location|caption|description|amount|phone|address|reason)\s+(?:of\s+|is\s+)?([\w.+-]+@[\w.-]+\w|\$?\d[\d,.]*)', t):
        out.append((m[1], m[2]))
    em = re.search(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', t)
    if em and em[0] not in [v for _, v in out]:
        out.append(('email', em[0]))
    return out


def plan(instruction):
    """The Planner: the instruction as ordered steps."""
    steps = []
    for c in clauses(instruction):
        fresh_sentence = c.startswith('\x02')
        c = c.lstrip('\x02').strip()
        kind = kind_of(c)
        if kind == 'other' and steps and fresh_sentence and steps[-1].kind not in ('form', 'report'):
            continue                                # a remark of its own, not a detail of the step before
        if kind == 'other' and not steps and re.match(r'(?i)^(?:use|convert|generate|calculate|translate|draw|type|copy|play|listen|watch|block|mute|rate|review|share|upload|attach|sign|get|make|log|record|reply|comment|move|drag|reschedule)\b', c):
            kind = 'form'
        if kind == 'other' and steps:
            steps[-1] = Step(steps[-1].kind, steps[-1].text + ', ' + c)      # a trailing detail of the step before
            continue
        if kind == 'other':
            continue
        steps.append(Step(kind, c))
    for a, b in zip(steps, steps[1:]):
        # "Use the search bar to find | and open the permit information ...": the search is for what the next step names
        if a.kind == 'search' and not a.quotes and re.search(r'(?i)\b(?:to find|to look|to locate|search(?: bar| box)?)\s*$', a.text):
            a.state['query'] = re.sub(r'(?i)^(?:and\s+)?(?:open|view|find|tell me|report|check)\s+(?:and open\s+)?(?:the\s+|a\s+|an\s+)?', '', b.text).strip(' .')
    whole = norm(instruction)
    if not any(s.kind == 'report' for s in steps) and re.search(r'(?i)\?\s*$|\b(?:tell me|report|answer|how many|respond with)\b', whole):
        steps.append(Step('report', whole))
    return steps


def direction(text):
    """+1 for a descending order ('highest first', 'High to Low', 'newest'), -1 for ascending, 0 when it does not say."""
    t = norm(text).lower().replace('_', ' ')
    first = re.search(r'low(?:est)? to high|high(?:est)? to low|a\s*(?:-|to)\s*z|z\s*(?:-|to)\s*a', t)
    if first:
        return 1 if first[0].startswith(('high', 'z')) else -1
    if re.search(r'\b(?:desc|descending|highest|newest|latest|most|top|longest|largest|expensive|recent|best)\b', t):
        return 1
    if re.search(r'\b(?:asc|ascending|lowest|oldest|least|shortest|smallest|cheapest|earliest|alphabetical\w*)\b', t):
        return -1
    return 0


class Scout:
    """What is on the page, as the agent uses it. An observation is a dict:
    url, title, text, modal (bool), elements [{id, tag, type, role, text, label, name, dom_id, value, checked, disabled, options
    [{value, text, selected}], href, form, group, row, in_nav, min, max, x, y}], records [{lines, text, ids}], tables [{head, rows}]."""

    def __init__(self, obs):
        self.obs = obs or {}
        self.url = self.obs.get('url', '')
        self.text = norm(self.obs.get('text', ''))
        self.elements = [e for e in self.obs.get('elements', []) if not e.get('disabled')]
        self.by_id = {e['id']: e for e in self.elements}
        self.records = self.obs.get('records', [])
        self.tables = self.obs.get('tables', [])
        self.modal = bool(self.obs.get('modal'))

    @staticmethod
    def said(e):
        """Every word a control shows or is labelled with."""
        return ' '.join(str(e.get(k) or '') for k in ('text', 'label', 'value' if e.get('tag') in ('button',) or e.get('type') in ('submit', 'button') else '_', 'name', 'dom_id')).replace('_', ' ').replace('-', ' ')

    def inputs(self):
        return [e for e in self.elements if (e['tag'] == 'input' and e.get('type') not in ('submit', 'button', 'checkbox', 'radio', 'file', 'range', 'image', 'reset', 'color'))
                or e['tag'] == 'textarea' or (e.get('role') == 'textbox') or (e['tag'] not in ('input', 'select', 'textarea', 'button', 'a') and 'contenteditable' in str(e.get('cls', '')))]

    def selects(self):
        return [e for e in self.elements if e['tag'] == 'select']

    def clickables(self):
        return [e for e in self.elements if e['tag'] in ('a', 'button', 'summary', 'label', 'div', 'span', 'li', 'td', 'tr', 'i', 'svg', 'img', 'p', 'h3', 'h4', 'th')
                or e.get('type') in ('submit', 'button', 'checkbox', 'radio') or e.get('role') in ('button', 'link', 'tab', 'menuitem', 'checkbox', 'radio', 'switch', 'option')]


class WebAgent:
    """One instruction on one browser page. `act(observation)` returns the next action; {'op': 'done', 'answer': ...} ends it."""

    def __init__(self, instruction, lexicon=None, budget=30):
        whole = norm(instruction)
        self.apps = [(m[1].strip(), m[2].strip()) for m in re.finditer(r'(?m)^- (.+?): (https?://\S+)\s*$', whole)]
        instruction = re.split(r'\n\s*Apps for this task', whole)[0].strip()
        self.instruction = instruction
        self.steps = plan(instruction)
        self.lexicon = lexicon or {}
        self.budget = budget
        self.i = 0
        self.count = 0
        self.done_sigs = set()
        self.answer = None
        self.log = []                   # (job, what) as on the team board
        self.all_words = set(content(self.instruction))
        self.brand = None               # the site's own name words, read from the first page (never a target)
        self.note('Planner', '; '.join(f'{s.kind}: {s.text[:50]}' for s in self.steps) or 'no step recognised')

    def note(self, job, what):
        self.log.append((f'Meesix ({job})', what))

    # ---- matching -------------------------------------------------------------------------------------------------------------
    def expand(self, toks):
        toks = {stem(t) for t in toks}
        out = set(toks)
        for t in toks:
            out.update(SAME_STEM.get(t, ()))
            out.update(self.lexicon.get(t, ()))
        return out

    def score(self, want, e, exact=()):
        """How well a control's words fit the wanted words (0..1+)."""
        have = content(Scout.said(e))
        if not have or not want:
            return 0.0
        want = [stem(w) for w in want]
        wide = self.expand(want)
        hit = [h for h in have if h in wide]
        direct = [h for h in have if h in want]
        s = (len(set(hit)) + len(set(direct))) / (2.0 * max(1, min(len(set(have)), len(set(want)))))
        s *= min(1.0, 4.0 / max(4, len(have))) ** 0.5            # a long blurb that happens to contain the word is a weaker match
        shown = norm(e.get('text') or e.get('label') or '').strip().lower()
        for x in exact:
            if x and shown == x.lower():
                s += 1.0
            elif x and len(x) > 3 and x.lower() in norm(Scout.said(e)).lower():
                s += 0.5
        return s

    def mentioned(self, text, clause_tokens, clause_text):
        """Is this option/chip text named by the request? All of its words must be there."""
        toks = content(text)
        if not toks or DEFAULT_OPTION.match(text.strip()) or (self.brand and all(t in self.brand for t in toks)):
            return 0.0
        every = [stem(w) for w in words(text) if w not in ('a', 'an', 'the', 'and', 'of', 'by', 'to')]
        if all(t in clause_tokens for t in every):
            phrase = norm(text).strip().lower()
            return len(toks) + (0.5 if phrase in clause_text.lower() else 0.0)
        return 0.0

    def fresh(self, scout, action):
        sig = (self.i, scout.url.split('#')[0], action.get('op'), self.sig_of(scout, action), str(action.get('value', ''))[:40])
        if sig in self.done_sigs:
            return False
        self.done_sigs.add(sig)
        return True

    @staticmethod
    def sig_of(scout, action):
        e = scout.by_id.get(action.get('id'))
        return (e.get('tag'), e.get('name'), e.get('dom_id'), (e.get('text') or '')[:40], (e.get('label') or '')[:40], e.get('href')) if e else action.get('id')

    # ---- the loop -------------------------------------------------------------------------------------------------------------
    def act(self, obs):
        scout = Scout(obs)
        self.count += 1
        if self.brand is None:
            named = ' '.join(m[1] for m in re.finditer(r"(?:\b(?:in|on|to|from|of|using|through|into|at)\s+(?:the\s+|my\s+|your\s+)?|^)((?:[A-Z][\w&-]*\s?){1,4})", self.instruction))
            named += ' ' + ' '.join(re.findall(r"((?:[A-Z][\w&-]*\s?){1,3})'s?\b", self.instruction))
            shown = set(content(str(scout.obs.get('title', '')) + ' ' + str(scout.obs.get('brand', ''))))
            self.brand = ({t for t in content(named) if t in shown} | set(content(str(scout.obs.get('brand', ''))))) - S('search home login sign page welcome dashboard')
        while self.i < len(self.steps) and self.count <= self.budget:
            step = self.steps[self.i]
            step.spent += 1
            action = None
            if step.spent == 1 and self.apps:
                url = self.app_for(step, scout)
                if url:
                    self.note('Navigator', f'this step is in another app: {url}')
                    return {'op': 'goto', 'url': url, 'job': 'Navigator', 'why': 'switch app'}
            if step.spent <= 12:
                action = getattr(self, 'do_' + step.kind)(step, scout)
                if action is None and scout.modal and not step.state.get('modal_closed'):
                    action = self.confirm(step, scout)
            if action is not None:
                return action
            self.note('Critic', f'step {self.i + 1} ({step.kind}) finished or given up after {step.spent - 1} actions')
            self.i += 1
        return {'op': 'done', 'answer': self.answer, 'why': 'all steps done' if self.i >= len(self.steps) else 'budget spent'}

    def app_for(self, step, scout):
        """A task over several apps: the address of the app this step names, when the page is not in it already."""
        low = step.text.lower()
        best = None
        for name, url in self.apps:
            keys = [w for w in words(name) if w not in STOP and w not in ('online', 'platform', 'corp', 'hub', 'services', 'portal')] or words(name)
            pos = min([low.find(k) for k in keys if k in low] or [-1])
            if pos < 0 and re.search(r'\bmail\b', name.lower().replace('webmail', 'mail')) and re.search(r'(?i)\be-?mail\b|\bdraft\b', low):
                pos = low.find('mail')
            if pos < 0 and re.search(r'chat', name.lower()) and re.search(r'(?i)\bmessage\b|\bsend\b .* in quickchat', low):
                continue
            if pos >= 0 and (best is None or pos < best[0]):
                best = (pos, url)
        if best is None:
            if self.i == 0 and re.search(r'/$', scout.url) and '/sites/' not in scout.url:
                best = (0, self.apps[0][1])          # still on the portal: start in the first app listed
            else:
                return None
        return None if scout.url.startswith(best[1]) else best[1]

    def confirm(self, step, scout):
        """A dialog is open and the step has nothing more to do in it: accept it."""
        for e in scout.clickables():
            if AFFIRM.match((e.get('text') or e.get('value') or '').strip()) and self.fresh(scout, {'op': 'click', 'id': e['id'], 'value': 'confirm'}):
                return {'op': 'click', 'id': e['id'], 'why': 'confirm the dialog', 'job': 'Navigator'}
        step.state['modal_closed'] = True
        return None

    # ---- steps ----------------------------------------------------------------------------------------------------------------
    def search_box(self, scout):
        best, top = None, 0.0
        for e in scout.inputs():
            said = Scout.said(e).lower()
            s = 0.0
            if e.get('type') == 'search' or e.get('role') == 'searchbox':
                s = 2.0
            if re.search(r'\bsearch|\bfind\b|\bquery\b|\blook ?up|\bkeyword', said):
                s = max(s, 2.0)
            if e.get('name') in ('q', 'query', 'search', 's', 'keyword', 'keywords', 'term'):
                s = max(s, 1.5)
            if e.get('type') in ('password', 'email', 'date', 'number', 'time'):
                s = 0.0
            if s > top:
                best, top = e, s
        return best

    def query_of(self, step):
        if step.quotes:
            return step.quotes[0]
        if step.state.get('query'):
            return self.keywords(step.state['query'])
        m = re.search(r'(?i)\bsearch(?: bar| box| field)?\s+to\s+(?:find|check|see|look for|locate)(?: and open)?(?: whether)?\s+(.+)$', step.text)
        if m:
            return self.keywords(m[1])
        t = re.sub(r'(?i)^.*?\b(?:search(?:es)?|look up|find|locate)\b', '', step.text, count=1)
        m = re.search(r'(?i)\bfor\s+(.+)$', t) or re.search(r'(?i)\b(?:to (?:find|check|see)(?: and open)?(?: whether)?|about|containing|matching|named|called)\s+(.+)$', step.text)
        q = (m[1] if m else t).strip()
        q = re.sub(r'(?i)\s+(?:in|on|from|using|with)\s+(?:the\s+)?[A-Z][\w\' ]+$', '', q)       # "... on ShopHub"
        q = re.sub(r'(?i)^(?:the|a|an|all|any|books?|articles?|papers?|videos?|posts?|products?|items?|players?|apps?) (?:about|on|for|whose \w+ (?:is|are|contain\w*)) ', '', q)
        q = re.sub(r'(?i)\b(?:and leave .*|leave .*|\. .*)$', '', q).strip(' .,"')
        return q

    def keywords(self, phrase):
        """A described thing as a search query: a proper name as it stands, else its weighty words."""
        phrase = phrase.strip(' .?')
        m = re.match(r"^((?:[A-Z][\w'.-]*\s*){1,4})(?:\s+and\b.*)?$", phrase)
        if m:
            return m[1].strip()
        generic = S('information info article page detail city offer service product video company role whether available one host thing item us open matching match')
        keep = [w for w in words(phrase) if w not in STOP and stem(w) not in generic and stem(w) not in (self.brand or ())]
        return ' '.join(keep[:3]) if keep else phrase

    def do_search(self, step, scout):
        if step.state.get('searched'):
            return None
        box = self.search_box(scout)
        query = self.query_of(step)
        if box is not None and query:
            step.state['searched'] = True
            self.last_query = query
            self.note('Navigator', f'search for "{query}"')
            return {'op': 'fill', 'id': box['id'], 'value': query, 'enter': True, 'why': 'search', 'job': 'Navigator'}
        if not step.state.get('nav'):
            step.state['nav'] = True
            link = self.best_click(scout, ['search'], step, floor=0.6)
            if link is not None:
                return link
        return None

    def do_find(self, step, scout):
        """'Find X' with nothing else said: search for it when the page has a search box, then open it if it is listed."""
        target = step.quotes[0] if step.quotes else ''
        if target and target.lower() in scout.text.lower():
            return self.do_open(step, scout)
        if not step.state.get('searched'):
            got = self.do_search(step, scout)
            if got:
                return got
        return self.do_open(step, scout) if target else None

    def do_login(self, step, scout):
        creds = dict(step.fields)
        user, pw = creds.get('username'), creds.get('password')
        if not pw:
            qs = step.quotes
            if len(qs) >= 2:
                user, pw = qs[0], qs[1]
            else:
                return None
        pwd = next((e for e in scout.elements if e['tag'] == 'input' and e.get('type') == 'password'), None)
        if pwd is None:
            if step.state.get('submitted') or step.state.get('opened', 0) >= 2:
                return None
            step.state['opened'] = step.state.get('opened', 0) + 1
            return self.best_click(scout, ['login', 'sign', 'signin', 'log'], step, floor=0.3)
        if step.state.get('submitted'):
            return None
        mates = [e for e in scout.inputs() if e.get('form') == pwd.get('form') and e.get('type') in ('', 'text', 'email')]
        name = mates[0] if mates else None
        if name is not None and not step.state.get('user'):
            step.state['user'] = True
            return {'op': 'fill', 'id': name['id'], 'value': user, 'why': 'username', 'job': 'Clerk'}
        if not step.state.get('pw'):
            step.state['pw'] = True
            return {'op': 'fill', 'id': pwd['id'], 'value': pw, 'why': 'password', 'job': 'Clerk'}
        step.state['submitted'] = True
        button = self.submit_button(scout, pwd.get('form'), ['login', 'sign', 'log'])
        if button is not None:
            return {'op': 'click', 'id': button['id'], 'why': 'submit sign-in', 'job': 'Clerk'}
        return {'op': 'press', 'key': 'Enter', 'why': 'submit sign-in', 'job': 'Clerk'}

    def submit_button(self, scout, form, want):
        best, top = None, 0.0
        for e in scout.clickables():
            if e['tag'] == 'a' and e.get('in_nav'):
                continue
            if e['tag'] not in ('button', 'input', 'a') and e.get('role') != 'button':
                continue
            said = (e.get('text') or e.get('value') or e.get('label') or '').strip()
            s = self.score(want, e) + (0.6 if e.get('type') == 'submit' else 0.0) + (0.5 if SUBMIT.search(said) else 0.0)
            if form and e.get('form') == form:
                s += 1.0
            elif form and e.get('form'):
                s -= 1.0
            if re.search(r'(?i)\b(?:cancel|close|back|reset|clear|discard|delete|remove)\b', said):
                s -= 2.0
            if s > top:
                best, top = e, s
        return best if top >= 1.0 else None

    def best_click(self, scout, want, step, floor=0.5, exact=(), avoid_nav=False, pool=None):
        best, top = None, floor
        for e in (pool if pool is not None else scout.clickables()):
            if e.get('type') in ('checkbox', 'radio') and not exact:
                continue
            if avoid_nav and e.get('in_nav'):
                continue
            mine = content(e.get('text') or e.get('label') or '')
            if self.brand and mine and all(t in self.brand for t in mine) and not exact:
                continue
            s = self.score(want, e, exact)
            if e['tag'] in ('a', 'button') or e.get('role') in ('button', 'link', 'tab', 'menuitem'):
                s += 0.05
            if s > top and (step is None or self.fresh(scout, {'op': 'click', 'id': e['id']})):
                best, top = e, s
        if best is None:
            return None
        self.note('Navigator', f'click "{(best.get("text") or best.get("label") or best.get("name") or "")[:40]}" ({top:.2f})')
        return {'op': 'click', 'id': best['id'], 'why': 'best match', 'job': 'Navigator', 'score': round(top, 2)}

    def choose(self, step, scout, only_sort=False):
        """The Navigator's main move: an option, chip, checkbox or tab whose words the request names."""
        toks, text = {stem(w) for w in words(step.text)}, step.text
        if only_sort:
            toks |= self.expand(step.words)
        best, top = None, 0.0
        for e in scout.selects():
            label = content((e.get('label') or '') + ' ' + (e.get('name') or '').replace('_', ' '))
            named = sum(1 for t in label if t in step.words)
            if only_sort and not (re.search(r'(?i)sort|order', Scout.said(e)) or any(re.search(r'(?i)newest|oldest|low|high|a-z|recent|rated|popular', o['text']) for o in e.get('options', []))):
                continue
            for o in e.get('options', []):
                m = self.mentioned(o['text'], toks, text)
                if only_sort:
                    ow = content(o['text'] + ' ' + str(o.get('value', '')).replace('_', ' '))
                    part = 0.8 * sum(1 for t in set(ow) if t in toks) / max(1, len(set(ow))) if ow else 0.0
                    m = max(m, part)
                    if m:
                        m += 0.6 * direction(text) * direction(o['text'] + ' ' + str(o.get('value', '')))
                if m and not o.get('selected'):
                    s = m + 0.6 * named
                    if s > top and norm(o['text']).strip().lower() not in step.state.setdefault('chosen', set()):
                        best, top = ({'op': 'select', 'id': e['id'], 'value': o['value'], 'text': o['text'], 'job': 'Navigator', 'why': f'option "{o["text"]}" is named'},
                                     norm(o['text']).strip().lower()), s
        for e in scout.clickables():
            shown = (e.get('text') or e.get('label') or '').strip()
            if not shown or len(shown) > 60 or (e.get('in_nav') and e['tag'] == 'a' and e.get('role') != 'tab'):
                continue
            m = self.mentioned(shown, toks, text)
            if only_sort and e['tag'] in ('a', 'th', 'button') and (re.search(r'(?i)sort|order', str(e.get('href') or '') + ' ' + str(e.get('cls') or '') + ' ' + str(e.get('group') or '')) or e['tag'] == 'th'):
                st = content(shown)
                part = sum(1 for t in set(st) if t in toks) / max(1, len(set(st))) if st else 0.0
                m = max(m, 0.9 * part + (0.3 * direction(text) * direction(shown) if part else 0.0))
            elif only_sort and e['tag'] == 'a':
                m = 0.0
            if not m:
                continue
            if e.get('type') in ('checkbox', 'radio') or e.get('role') in ('checkbox', 'radio', 'switch'):
                if e.get('checked'):
                    continue
                m += 0.4
            group = content(e.get('group') or '')
            m += 0.3 * sum(1 for t in group if t in step.words)
            key = norm(shown).lower()
            if m > top and key not in step.state.setdefault('chosen', set()):
                best, top = ({'op': 'click', 'id': e['id'], 'job': 'Navigator', 'why': f'"{shown}" is named'}, key), m
        if best is None:
            return None
        action, key = best
        step.state['chosen'].add(key)
        self.note('Navigator', action['why'])
        return action

    def apply_button(self, step, scout):
        """The control did not reload the page by itself: press the button of its own form (Apply, Filter, Go)."""
        if step.state.get('applied'):
            return None
        form = step.state.get('form')
        best, top = None, 0.0
        for e in scout.clickables():
            if e['tag'] not in ('button', 'input') and e.get('role') != 'button':
                continue
            said = (e.get('text') or e.get('value') or '').strip()
            named = bool(re.match(r'(?i)^(?:apply|filter|apply filters?|go|update|show results?|submit|apply filter|refine|done)\b', said))
            if form and e.get('form') == form:
                s = 2.0 + named + (0.5 if e.get('type') == 'submit' else 0.0)
            elif not e.get('form') and named:
                s = 1.0
            else:
                continue
            if re.search(r'(?i)\b(?:clear|reset|cancel)\b', said):
                continue
            if s > top:
                best, top = e, s
        if best is None:
            return None
        step.state['applied'] = True
        return {'op': 'click', 'id': best['id'], 'job': 'Navigator', 'why': 'apply the filter'}

    def set_dates(self, step, scout):
        ds = dates(step.text)
        if not ds or step.state.get('dates_done'):
            return None
        boxes = [e for e in scout.inputs() if e.get('type') in ('date', 'datetime-local', 'month') or re.search(r'(?i)\bdate\b|\bfrom\b|\bto\b|\bstart\b|\bend\b|\bsince\b|\buntil\b|\bafter\b|\bbefore\b', Scout.said(e))]
        boxes = [e for e in boxes if e.get('type') not in ('password', 'email', 'search')]
        if not boxes:
            return None
        k = step.state.get('date_i', 0)
        if re.search(r'(?i)\bbefore\b|\buntil\b|\bup to\b', step.text) and len(ds) == 1 and len(boxes) >= 2 and k == 0:
            k = 1                                   # only an end date was given
            step.state['date_i'] = 1
        if k >= min(len(boxes), 2) or k >= len(ds) + (1 if len(ds) == 1 and step.state.get('date_i') else 0):
            step.state['dates_done'] = True
            return None
        d = ds[min(k, len(ds) - 1)] if not (len(ds) == 1 and k == 1) else ds[0]
        step.state['date_i'] = k + 1
        e = boxes[k]
        value = d.isoformat()
        if e.get('type') == 'datetime-local':
            value += 'T00:00' if k == 0 else 'T23:59'
        elif e.get('type') == 'month':
            value = value[:7]
        elif e.get('type') != 'date' and re.search(r'(?i)mm/dd', e.get('label') or ''):
            value = d.strftime('%m/%d/%Y')
        self.note('Clerk', f'date {value}')
        return {'op': 'fill', 'id': e['id'], 'value': value, 'job': 'Clerk', 'why': 'date range'}

    def set_slider(self, step, scout):
        nums = numbers(re.sub(r'"[^"]*"', ' ', step.text))
        sliders = [e for e in scout.elements if e.get('type') == 'range']
        if not nums or not sliders or step.state.get('slid'):
            return None
        if not re.search(r'(?i)slider|price|rating|rated|minimum|maximum|below|above|at least|at most|or less|or more|under|over|\$|stars?\b|wins', step.text):
            return None
        best = max(sliders, key=lambda e: self.score(step.words, e))
        if len(sliders) > 1 and re.search(r'(?i)\bmax|\bbelow\b|\bor less\b|\bunder\b|\bat most\b|\bup to\b', step.text):
            hi = [e for e in sliders if re.search(r'(?i)max|high|upper|to\b', Scout.said(e))]
            best = hi[0] if hi else best
        try:
            lo, hi = float(best.get('min') or 0), float(best.get('max') or 100)
        except ValueError:
            lo, hi = 0.0, 100.0
        step.state['slid'] = True
        value = nums[0]
        self.note('Navigator', f'slider to {value}')
        return {'op': 'range', 'id': best['id'], 'fraction': (value - lo) / (hi - lo) if hi > lo else 0.5, 'target': value, 'job': 'Navigator', 'why': 'slider'}

    def do_filter(self, step, scout):
        got = self.set_slider(step, scout) or self.set_dates(step, scout) or self.choose(step, scout)
        return self.chosen(step, scout, got)

    def chosen(self, step, scout, got):
        if got:
            e = scout.by_id.get(got.get('id'), {})
            step.state['acted'] = True
            step.state['needs_apply'] = got['op'] != 'click' or e.get('type') in ('checkbox', 'radio')
            step.state['form'] = e.get('form') or step.state.get('form')
            step.state['url'] = scout.url
            return got
        if step.state.get('acted'):
            if step.state.get('needs_apply') and step.state.get('url') == scout.url:    # nothing reloaded: the form may want its button
                return self.apply_button(step, scout)
            return None
        return self.detour(step, scout)

    def do_sort(self, step, scout):
        if step.state.get('sorted'):
            return self.chosen(step, scout, None)
        got = self.choose(step, scout, only_sort=True)
        if got and scout.by_id.get(got.get('id'), {}).get('tag') != 'a':
            step.state['sorted'] = True
        return self.chosen(step, scout, got)

    def detour(self, step, scout):
        """Nothing on this page fits the step: follow the menu entry that shares its words, once or twice."""
        if step.state.get('detours', 0) >= 2:
            return None
        step.state['detours'] = step.state.get('detours', 0) + 1
        pool = [e for e in scout.clickables() if e['tag'] == 'a' or e.get('role') in ('tab', 'link', 'menuitem')]
        return self.best_click(scout, [w for w in step.words], step, floor=0.45, pool=pool)

    def target_of(self, step):
        if step.quotes:
            return step.quotes[0]
        if 'target' in step.state:
            return step.state['target']
        found = []
        for m in re.finditer(r'(?:[A-Z#@][\w\'.&:-]*)(?:\s+(?:[A-Z#@0-9][\w\'.&:-]*|of|the|and|vs))*', step.text[1:]):
            phrase = re.sub(r"'s$", '', m[0].strip(" .,'"))
            toks = content(phrase)
            if len(phrase) < 3 or not toks:
                continue
            own = sum(1 for t in toks if t in (self.brand or ()))
            if re.fullmatch(r'(?i)(?:my |your )?(?:favorites|favourites|cart|wishlist|watchlist|library|bookmarks|messages|settings|explore|standings|contacts)', phrase):
                continue
            if own * 2 >= len(toks):
                continue                            # the site's own name is where, not what
            before = step.text[:m.start() + 1].rstrip().split(' ')[-1].lower()
            found.append((before in ('in', 'on', 'from', 'through', 'via', 'at', 'using'), m.start(), phrase))
        found.sort()
        step.state['target'] = found[0][2] if found and not found[0][0] else ''
        return step.state['target']

    def holder(self, scout, target):
        """The listed record (card, row) that shows the target, if any."""
        low = target.lower()
        for r in scout.records:
            if low and low in norm(r.get('text', '')).lower():
                return r
        return None

    def do_open(self, step, scout):
        if step.state.get('opened', 0) >= 2:
            return None
        target = self.target_of(step)
        want = content(target) or [w for w in step.words if w not in S('open go view visit navigate show display return check find detail page first full')]
        ordinal = re.search(r'(?i)\b(first|top|last)\b (?:\w+ ){0,3}?(?:result|post|book|item|listing|article|product|stream|video|question|template|one|entry|claim|email|message)', step.text)
        if ordinal and not step.quotes and scout.records:
            r = scout.records[-1 if ordinal[1].lower() == 'last' else 0]
            links = [scout.by_id[i] for i in r.get('ids', []) if i in scout.by_id and scout.by_id[i]['tag'] == 'a'] or [scout.by_id[i] for i in r.get('ids', []) if i in scout.by_id]
            if links and self.fresh(scout, {'op': 'click', 'id': links[0]['id']}):
                step.state['opened'] = step.state.get('opened', 0) + 1
                self.note('Navigator', f'open the {ordinal[1].lower()} listed record')
                return {'op': 'click', 'id': links[0]['id'], 'job': 'Navigator', 'why': 'ordinal record'}
        got = self.best_click(scout, want, step, floor=0.55, exact=(target,) if target else ())
        if got:
            step.state['opened'] = step.state.get('opened', 0) + 1
            return got
        if not step.state.get('searched'):
            step.state['searched'] = True
            box = self.search_box(scout)
            about = re.sub(r'(?i)^(?:open|view|go to|visit|show|display|check)\s+(?:the\s+|its\s+|a\s+)?', '', step.text)
            query = target or self.keywords(about)
            if box is not None and query and len(query) > 2:
                self.last_query = query
                step.state['after_search'] = True
                self.note('Navigator', f'search for "{query}" to find what to open')
                return {'op': 'fill', 'id': box['id'], 'value': query, 'enter': True, 'job': 'Navigator', 'why': 'search before opening'}
        elif step.state.pop('after_search', False) and scout.records:
            links = [scout.by_id[i] for i in scout.records[0].get('ids', []) if i in scout.by_id and scout.by_id[i]['tag'] == 'a']
            if links:
                step.state['opened'] = 2
                return {'op': 'click', 'id': links[0]['id'], 'job': 'Navigator', 'why': 'first search result'}
        return None

    def verb_button(self, step, scout, verbs, pool, target=''):
        best, top = None, 0.0
        wide = self.expand(verbs)
        about = set(content(target))
        for e in pool:
            have = content(Scout.said(e) + ' ' + str(e.get('cls') or '').replace('-', ' ').replace('_', ' '))
            s = sum(1.0 for h in set(have) if h in wide) / max(1.0, len(set(have) - about) ** 0.5)
            if s and about:
                s += 0.5 * sum(1 for h in set(have) if h in about) / len(about)       # "Subscribe #film-photography", not "#analog"
            if re.search(r'(?i)^(?:un|remove|leave|cancel)', (e.get('text') or '').strip()) and not re.search(r'(?i)^(?:un|remove|leave|delete)', step.text):
                s = 0.0                                                             # already on: leave it
            if s > top:
                best, top = e, s
        return best if top >= 0.45 else None

    def do_toggle(self, step, scout, verbs=None):
        if step.state.get('toggled'):
            return None
        lead = words(step.text)[:1]
        verbs = verbs or [stem(w) for w in lead] + [stem(w) for w in re.findall(r'(?i)\b(cart|wishlist|watchlist|favorites|favourites|library|bookmarks|playlist)\b', step.text)]
        verbs = [{'favourit': 'favorit', 'bookmark': 'sav', 'add': ''}.get(v, v) for v in verbs]
        verbs = [v for v in verbs if v] or ['add']
        target = self.target_of(step)
        holder = self.holder(scout, target) if target else None
        ordinal = re.search(r'(?i)\b(first|top)\b', step.text)
        if holder is None and ordinal and scout.records and not target:
            holder = scout.records[0]
        if holder is not None:
            pool = [scout.by_id[i] for i in holder.get('ids', []) if i in scout.by_id]
            button = self.verb_button(step, scout, verbs, pool)
            if button is not None:
                step.state['toggled'] = True
                self.note('Navigator', f'{verbs[0]} in the record of "{target or "first"}"')
                return {'op': 'click', 'id': button['id'], 'job': 'Navigator', 'why': 'toggle in record'}
            if not step.state.get('opened'):
                step.state['opened'] = True
                links = [e for e in pool if e['tag'] == 'a'] or pool
                named = [e for e in links if target and target.lower() in norm(e.get('text', '')).lower()] or links
                if named:
                    return {'op': 'click', 'id': named[0]['id'], 'job': 'Navigator', 'why': 'open the record to find its control'}
        on_page = bool(target) and target.lower() in scout.text.lower()
        if (on_page or not target or step.state.get('opened')) and not step.state.get('page_try'):
            pool = [e for e in scout.clickables() if not (e.get('in_nav') and e['tag'] == 'a')]
            button = self.verb_button(step, scout, verbs, pool, target)
            if button is not None and (step.state.get('opened') or not target or len(scout.records) < 2 or on_page):
                step.state['toggled'] = step.state['page_try'] = True
                self.note('Navigator', f'{verbs[0]} on the page')
                return {'op': 'click', 'id': button['id'], 'job': 'Navigator', 'why': 'toggle on page'}
        if target and not on_page and not step.state.get('searched'):
            step.state['searched'] = True
            box = self.search_box(scout)
            if box is not None:
                return {'op': 'fill', 'id': box['id'], 'value': target, 'enter': True, 'job': 'Navigator', 'why': 'search for the target'}
        if target and on_page and not step.state.get('opened'):
            step.state['opened'] = True
            return self.best_click(scout, content(target), step, floor=0.5, exact=(target,))
        if not step.state.get('detour'):
            step.state['detour'] = True
            return self.detour(step, scout)
        return None

    def do_delete(self, step, scout):
        if step.state.get('toggled') and scout.modal:
            return None                              # the generic confirmation takes the dialog
        return self.do_toggle(step, scout, verbs=['delete', 'remove', 'trash'])

    def do_export(self, step, scout):
        if step.state.get('clicked', 0) >= 2:
            return None
        got = self.choose(step, scout) if not step.state.get('chose') else None
        if got:
            step.state['chose'] = True
            return got
        fmt = re.findall(r'(?i)\b(csv|pdf|json|xlsx|excel|svg|png|xml|txt)\b', step.text)
        want = ['export', 'download'] + [f.lower() for f in fmt]
        step.state['clicked'] = step.state.get('clicked', 0) + 1
        return self.best_click(scout, want, step, floor=0.4) or self.detour(step, scout)

    # ---- forms ----------------------------------------------------------------------------------------------------------------
    def field_for(self, key, value, boxes, used):
        best, top = None, 0.34
        kt = content(key)
        for e in boxes:
            if e['id'] in used:
                continue
            s = self.score(kt, e) if kt else 0.0
            typ = e.get('type') or ''
            if '@' in value and (typ == 'email' or re.search(r'(?i)e-?mail|recipient|\bto\b', Scout.said(e))):
                s += 0.6
            if kt and kt[0] in S('message text body comment description review caption note') and e['tag'] == 'textarea':
                s += 0.5
            if typ in ('date', 'time', 'datetime-local', 'password') and not re.search(r'(?i)date|time|password', key):
                s -= 1.0
            if s > top:
                best, top = e, s
        return best

    def do_form(self, step, scout):
        st = step.state
        used = st.setdefault('used', set())
        box = self.search_box(scout)
        boxes = [e for e in scout.inputs() if box is None or e['id'] != box['id']]       # the site search is never a form field
        clause = step.text
        # values with a named field
        pending = [(k, v) for k, v in step.fields if (k, v) not in st.setdefault('filled', set())]
        for k, v in pending:
            e = self.field_for(k, v, boxes, used)
            if e is not None:
                st['filled'].add((k, v))
                used.add(e['id'])
                st['touched_form'] = e.get('form') or st.get('touched_form')
                self.note('Clerk', f'{k} = "{v[:30]}"')
                return {'op': 'fill', 'id': e['id'], 'value': v, 'job': 'Clerk', 'why': f'field {k}'}
        # options and switches the request names
        if st.get('choices', 0) < 6:
            got = self.choose(step, scout)
            if got:
                st['choices'] = st.get('choices', 0) + 1
                e = scout.by_id.get(got['id'], {})
                if e.get('tag') == 'select' or e.get('type') in ('checkbox', 'radio'):
                    st['touched_form'] = e.get('form') or st.get('touched_form')
                    st['set_any'] = True
                else:
                    st['opened'] = st.get('opened', 0) + 1
                return got
        # dates and times
        if not st.get('dated'):
            ds, ts = dates(clause), times(clause)
            for e in boxes:
                if e['id'] in used:
                    continue
                typ = e.get('type')
                value = None
                if typ == 'date' and ds:
                    value = ds[min(st.get('d_i', 0), len(ds) - 1)].isoformat()
                    st['d_i'] = st.get('d_i', 0) + 1
                elif typ == 'time' and ts:
                    value = ts[min(st.get('t_i', 0), len(ts) - 1)]
                    st['t_i'] = st.get('t_i', 0) + 1
                elif typ == 'datetime-local' and ds:
                    value = ds[0].isoformat() + 'T' + (ts[min(st.get('t_i', 0), len(ts) - 1)] if ts else '09:00')
                    st['t_i'] = st.get('t_i', 0) + 1
                if value:
                    used.add(e['id'])
                    st['touched_form'] = e.get('form') or st.get('touched_form')
                    st['set_any'] = True
                    return {'op': 'fill', 'id': e['id'], 'value': value, 'job': 'Clerk', 'why': 'date/time'}
            st['dated'] = True
        # a value nothing claimed goes to the free-text box, if exactly this kind of step wants one
        if pending and not st.get('loose'):
            st['loose'] = True
            free = [e for e in boxes if e['id'] not in used and not e.get('value') and (e['tag'] == 'textarea' or e.get('type') in ('', 'text'))]
            free = [e for e in free if not re.search(r'(?i)search', Scout.said(e))]
            if free and (st.get('filled') or st.get('opened') or len(free) <= 3):
                k, v = pending[0]
                long_text = len(v.split()) > 6 or content(k)[:1] and content(k)[0] in S('message text body comment description review caption note post reply')
                named = [x for x in free if re.search(r'(?i)title|name|subject|topic|headline', Scout.said(x))]
                e = next((x for x in free if x['tag'] == 'textarea'), None) if long_text else (named[0] if named else None)
                e = e or free[0]
                st['loose'] = len(pending) <= 1     # the next unclaimed value gets the next free box
                st['filled'].add((k, v))
                used.add(e['id'])
                st['touched_form'] = e.get('form') or st.get('touched_form')
                return {'op': 'fill', 'id': e['id'], 'value': v, 'job': 'Clerk', 'why': f'free text for {k}'}
        if st.get('filled') or st.get('set_any'):
            if st.get('submitted'):
                return None
            st['submitted'] = True
            button = self.submit_button(scout, st.get('touched_form'), [w for w in step.words[:3]])
            if button is not None and box is not None and button.get('form') and button.get('form') == box.get('form'):
                button = None                       # that is the search button
            if button is not None:
                self.note('Clerk', f'submit with "{(button.get("text") or button.get("value") or "")[:30]}"')
                return {'op': 'click', 'id': button['id'], 'job': 'Clerk', 'why': 'submit the form'}
            return None
        # nothing to fill here yet: open what the request talks about (New, Compose, Settings, the named record)
        if st.get('opened', 0) < (3 if step.fields or dates(clause) else 1):
            st['opened'] = st.get('opened', 0) + 1
            target = self.target_of(step)
            lead = [stem(w) for w in words(clause)[:1]]
            got = None
            if target and target.lower() in scout.text.lower() and st['opened'] == 1:
                got = self.best_click(scout, content(target), step, floor=0.5, exact=(target,))
            got = got or self.best_click(scout, lead + [w for w in step.words if w not in lead and w not in (self.brand or ())], step, floor=0.42)
            if got:
                return got
        return None

    # ---- reading --------------------------------------------------------------------------------------------------------------
    def do_report(self, step, scout):
        st = step.state
        q = step.text
        target = step.quotes[0] if step.quotes else ''
        low = scout.text.lower()
        if target and target.lower() not in low and not st.get('searched') and self.i == 0:
            st['searched'] = True
            box = self.search_box(scout)
            if box is not None:
                return {'op': 'fill', 'id': box['id'], 'value': target, 'enter': True, 'job': 'Navigator', 'why': 'look for what the question names'}
        if target and not st.get('opened') and self.i == 0 and not re.search(r'(?i)\bhow many\b.*\b(?:found|match|result)', q):
            st['opened'] = True
            got = self.best_click(scout, content(target), step, floor=0.7, exact=(target,), avoid_nav=True)
            if got:
                return got
        if not target and self.i == 0 and not st.get('nav'):
            st['nav'] = True
            m = re.search(r"(?i)\b(?:on|in|from) (?:the |my |your )?(?:[\w']+ ){0,3}?([\w-]+) (?:page|tab|section|dashboard|list|folder)\b", q)
            if m and m[1].lower() not in ('home', 'this', 'that'):
                pool = [e for e in scout.clickables() if e['tag'] == 'a' or e.get('role') in ('tab', 'link')]
                got = self.best_click(scout, content(m[1]), step, floor=0.8, pool=pool)
                if got:
                    return got
        self.answer = self.read(q, scout)
        self.note('Reader', f'answer: {str(self.answer)[:80]}')
        return None

    def read(self, q, scout):
        """The Reader: one short answer from what the page shows, or None."""
        low_q = norm(q).lower()
        text = scout.text
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        m = re.search(r'\bhow many ([a-z-]+(?: [a-z-]+)?)', low_q) or re.search(r'\b(?:number|count) of ([a-z-]+)', low_q) or re.search(r'\bcount (?:my |the |your )?([a-z-]+(?: [a-z-]+)?)', low_q)
        if m:
            noun = [stem(w) for w in m[1].split() if w not in STOP]
            scored = []
            for l in lines:
                if len(l) > 120:
                    continue
                for n in re.finditer(r'(?<![\w.$#-])(\d[\d,]*)\b(?!\s*(?:-|to|–)\s*\d)(?![.:/]\d)', l):
                    toks = content(l)
                    s = 0.0
                    if re.search(r'(?i)\b(?:result|found|match|total|showing|listing|item|entr)', l):
                        s += 1.5 if len(l) < 60 else 1.0
                    s += 1.5 * sum(1 for t in noun if t in toks)
                    of = re.search(r'(?i)\bof\s+(\d[\d,]*)\b', l)
                    value = of[1] if of and re.search(r'(?i)showing|\d\s*-\s*\d', l) else n[1]
                    after = l[n.end():n.end() + 25].lower()
                    if noun and any(t in content(after)[:2] for t in noun):
                        s += 1.0
                    if len(toks) > 9:
                        s -= 0.5
                    if s >= 1.5:
                        scored.append((s, value))
                    break
            if scored:
                return max(scored, key=lambda x: x[0])[1].replace(',', '')
            rows = sum(len(t.get('rows', [])) for t in scout.tables[:1])
            if rows and rows < 100:
                return str(rows)
            if scout.records and len(scout.records) < 100:
                return str(len(scout.records))
            if re.search(r'(?i)\bno (?:results|matches|\w+ found)\b|\bnothing found\b|\b0 results\b', text):
                return '0'
            return None
        got = self.superlative(low_q, scout)
        if got:
            return got
        if re.search(r'\b(?:first|top|last)\b', low_q) and scout.records and re.search(r'\b(?:title|name|which|what|who|streamer|author)\b', low_q):
            first = scout.records[-1 if re.search(r'\blast\b', low_q) else 0]
            attr = re.search(r'\b(author|streamer|price|date|like count|rating|views?)\b', low_q)
            if attr and attr[1] not in ('title', 'name'):
                got = self.labelled(attr[1], first.get('lines', []), [])
                if got:
                    return got
            return first['lines'][0] if first.get('lines') else None
        ask = re.sub(r'(?i)^(?:tell me|report|what is|what are|what\'s|give me|provide|find)\s+', '', low_q)
        ask = re.sub(r'"[^"]*"', ' ', ask)
        entity = (quotes(q) or [getattr(self, 'last_query', '')])[0]
        if entity:
            for r in scout.records:                 # the listed record of the thing asked about: what stands next to its name
                rl = r.get('lines') or []
                if rl and entity.lower() in rl[0].lower() and len(rl) > 1:
                    return self.labelled(ask, rl[1:], []) or rl[1]
        got = self.labelled(ask, lines, scout.tables)
        if got:
            return got
        if re.search(r'(?i)\byes or no\b|^(?:is|are|does|do|did|has|have)\b|\bwhether\b', low_q):
            hit = [w for w in content(ask) if len(w) > 3]
            seen = sum(1 for w in set(hit) if w in set(content(text)))
            return 'Yes' if hit and seen >= max(1, int(0.6 * len(set(hit)))) and not re.search(r'(?i)\bno (?:results|matches)\b|\bnothing found\b', text) else 'No'
        return None

    def superlative(self, low_q, scout):
        """'Which X has the most Y', 'the Z of the X with the highest Y': the table row (or listed record) that wins on Y."""
        m = re.search(r'\b(most|highest|largest|biggest|maximum|greatest|longest|least|lowest|smallest|fewest|cheapest|minimum|shortest|oldest|newest|latest|earliest|most recent|most expensive)\b\s*((?:[a-z-]+\s*){0,3})', low_q)
        if not m:
            return None
        down = m[1] in ('least', 'lowest', 'smallest', 'fewest', 'cheapest', 'minimum', 'shortest', 'oldest', 'earliest')
        by = [w for w in content(m[2])][:2] or {'cheapest': ['price'], 'most expensive': ['price'], 'oldest': ['date'], 'newest': ['date'], 'latest': ['date'], 'most recent': ['date'], 'earliest': ['date']}.get(m[1], [])
        if m[1] in ('cheapest', 'most expensive'):
            by = ['price', 'cost']
        if m[1] in ('oldest', 'newest', 'latest', 'most recent', 'earliest'):
            by = by + ['date', 'updat', 'creat', 'tim']
        wide = self.expand(by)

        def value(cell):
            c = cell.replace(',', '')
            d = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', c)
            if d:
                return float(d[1] + d[2] + d[3])
            n = re.search(r'-?\$?(\d+(?:\.\d+)?)\s*([kmbt])?\b', c, re.I)
            if not n:
                return None
            return float(n[1]) * {'k': 1e3, 'm': 1e6, 'b': 1e9, 't': 1e12}.get((n[2] or '').lower(), 1.0)
        for t in scout.tables:
            head = t.get('head') or []
            col = max(range(len(head)), key=lambda i: sum(1 for w in content(head[i]) if w in wide), default=None) if head else None
            if col is None or not any(w in wide for w in content(head[col])):
                continue
            rows = [(value(r[col]), r) for r in t.get('rows', []) if len(r) > col]
            rows = [(v, r) for v, r in rows if v is not None]
            if len(rows) < 2:
                continue
            win = (min if down else max)(rows, key=lambda x: x[0])[1]
            asked = low_q[:m.start()]
            ask_toks = self.expand([w for w in content(asked) if w not in S('what which who report tell name')])
            out = max(range(len(head)), key=lambda i: (sum(1 for w in content(head[i]) if w in ask_toks), -i))
            if not any(w in ask_toks for w in content(head[out])) or out == col:
                out = 0
            return win[out]
        return None

    def labelled(self, ask, lines, tables):
        """A value that sits next to a label the question names: 'Phone: 555-0100', a label line over a value line, a table column."""
        want = [w for w in content(ask) if w not in S('report her his their it number list listed')] or content(ask)
        if not want:
            return None
        wide = self.expand(want)
        best, top = None, 0.0
        pairs = []
        for i, l in enumerate(lines):
            m = re.match(r'^([^:]{2,40}):\s*(.{1,200})$', l)
            if m:
                pairs.append((m[1], m[2]))
            elif len(l) < 32 and i + 1 < len(lines) and len(lines[i + 1]) < 120 and not l[-1:].isdigit():
                pairs.append((l, lines[i + 1]))
            m = re.match(r'^(\$?\d[\d,.]*%?)\s+([A-Za-z][A-Za-z ]{2,30})$', l)
            if m:
                pairs.append((m[2], m[1]))
        for t in tables:
            head = t.get('head') or []
            for row in t.get('rows', [])[:1]:
                pairs += list(zip(head, row))
        for label, value in pairs:
            lt = content(label)
            if not lt or len(value.strip()) < 2 or len(label.strip()) < 3:
                continue
            s = sum(1 for t in set(lt) if t in wide) / len(set(lt)) ** 0.5
            if s > top and value.strip():
                best, top = value.strip(), s
        return best if top >= 0.7 else None


def run(instruction, page, lexicon=None, budget=30, on_step=None):
    """Drive `page` (an object with observe() -> dict and do(action) -> error text) until the agent is done.
    Returns {'answer', 'steps', 'team'}."""
    agent = WebAgent(instruction, lexicon=lexicon, budget=budget)
    trail = []
    while True:
        action = agent.act(page.observe())
        if action['op'] == 'done':
            break
        error = page.do(action)
        trail.append(dict(action, error=error) if error else action)
        if on_step:
            on_step(action, error)
    return dict(answer=agent.answer, steps=trail, team=[dict(agent=a, did=w) for a, w in agent.log])
