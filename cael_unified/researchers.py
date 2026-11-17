"""Two more Mr. Meesix researchers for open questions the authored library does not cover (round 10, 2026-11-15).

Thread Researcher. Many everyday questions have been asked before, word for word, on Stack Exchange ("How does one
descale an espresso machine, and how often?"). The researcher:
  1. writes the question out in full, with the conversation's subject in place of "it" / "them" / "there"
     ("How can I keep them alive while I'm gone?" -> "How can I keep my houseplants alive while I'm gone?");
  2. asks Stack Exchange's documented, keyless API for similar questions on the one or two sites the subject belongs
     to, and looks in CAEL's local index (285k answers) as well;
  3. accepts a stored question only when it is close to a paraphrase: it must name the subject (or its class) and carry
     most of the weight of the question's own words, and not name a different thing of the same kind (applicability);
  4. replies with the accepted or best-voted answer, cleaned of forum talk and trimmed, and says where it is from.

Destination Researcher. "What should I make sure not to miss in Tokyo?" is answered from the "See" and "Do" sections
of the Wikivoyage article on the place (CC BY-SA), the travel guide's own first recommendations.

Page and answer text is data: it is quoted and trimmed, never followed. No model.
"""
import html
import re

from . import open_chat as oc
from . import web_check as wc
from .network import NETWORK, LookupUnavailable
from urllib.parse import urlencode

PRON = re.compile(r"(?i)\b(it|them|they|these|those|there|its|their)\b")


LEADING = set('first new old little small big nice ten two three four five six seven eight nine about some few couple very really whole own '
              'brand second third last next lovely beautiful huge tiny cheap expensive good bad'.split())
TIME_WORDS = set('month week year day time hour minute way lot bit job today weekend morning evening night moment while plan idea'.split())


def scene_subject(messages):
    """The thing the conversation is about, as the user wrote it ('houseplants', 'espresso machine', 'laptop', 'flight')."""
    turns = oc.user_turns(messages)
    for t in reversed(turns[:-1][-4:]):
        cands = []
        for m in re.finditer(r"(?i)\b(?:my|our|a|an|the|about|some|of|these|those|selling|making|bought|got)\s+((?:[a-z0-9-]+\s+){0,3}[a-z]+)\b", t):
            words = [w for w in m[1].lower().split() if not re.match(r'^\d', w) and '-' not in w]
            while words and (words[0] in LEADING or words[0] in wc.STOP):
                words = words[1:]
            words = [w for w in words if w not in wc.STOP]
            if not words or not oc.is_noun(words[-1]) or oc.idf(oc.stem(words[-1])) < 3.0 or words[-1] in TIME_WORDS:
                continue
            words = words[-3:]
            while len(words) > 1 and not oc.is_noun(words[0]):
                words = words[1:]
            if len(words) == 2 and not (oc.is_noun(words[0]) or words[0] in ('handmade', 'electric', 'solar', 'hard', 'washing')):
                words = words[1:]
            cands.append(' '.join(words))
        # a plural subject at the start of a sentence: "Pigeons keep sitting on my balcony"
        for m in re.finditer(r"(?:^|[.!?]\s+)([A-Z][a-z]+s)\s+(?:keep|are|have|always|never|often|won'?t|don'?t|just|still)\b", t):
            w = m[1].lower()
            if oc.is_noun(w) and oc.idf(oc.stem(w)) > 3.5:
                return w
        if cands:
            return max(cands, key=lambda c: (len(c.split()), oc.idf(oc.stem(c.split()[-1]))))
    return None


def bound_question(messages):
    """The last question written out in full, with the conversation's subject in place of a pronoun."""
    turns = oc.user_turns(messages)
    last = turns[-1].strip()
    asked = [s for s in re.split(r'(?<=[.!?])\s+', last) if s.strip().endswith('?')]
    q = asked[-1] if asked else last
    told = ' '.join(s for s in re.split(r'(?<=[.!?])\s+', last) if not s.strip().endswith('?'))
    q = re.sub(r"(?i)^\s*(?:and|so|ok(?:ay)?|right|also|but)[,]?\s+", '', q)
    subject = scene_subject(messages)
    if subject and not re.search(r'(?i)\b' + re.escape(subject.split()[-1]) + r'', q):
        if PRON.search(q):
            plural = subject.endswith('s')
            def swap(m):
                w = m[1].lower()
                if w in ('its', 'their'):
                    return f"my {subject}'s" if not plural else f"my {subject}'"
                if w == 'there':
                    return f'in {subject}' if subject[:1].isupper() else 'there'
                return f'my {subject}'
            q = PRON.sub(swap, q, count=1)
        else:
            q = q.rstrip('?') + f' ({subject})?'
    if told and len(told.split()) <= 20:
        q = told + ' ' + q
    return q, subject


def weights(text):
    return {oc.stem(w): oc.idf(oc.stem(w)) for w in oc.content(text) if oc.idf(oc.stem(w)) > 1.0}


def match(q_w, subject_stems, title):
    """(coverage, precision) of a stored title against the question's weighted words."""
    t = {oc.stem(w) for w in oc.content(title)}
    total = sum(q_w.values()) or 1
    cov = sum(v for s, v in q_w.items() if s in t) / total
    tw = {s: oc.idf(s) for s in t if oc.idf(s) > 1.0}
    prec = sum(v for s, v in tw.items() if s in q_w) / (sum(tw.values()) or 1)
    has_subject = bool(subject_stems & t) if subject_stems else True
    return cov, prec, has_subject


def own_cov(q_w, subject_stems, title):
    """How much of what is asked about the subject (not the subject itself) the stored title covers."""
    t = {oc.stem(w) for w in oc.content(title)}
    own = {k: v for k, v in q_w.items() if k not in subject_stems}
    return sum(v for k, v in own.items() if k in t) / (sum(own.values()) or 1)


def se_answer(site, qid):
    from . import stack_source as ss
    got = ss.call(f'questions/{qid}/answers', None, site=site, filter='withbody', sort='votes', order='desc', pagesize=5)
    best = None
    for a in got:
        rank = (bool(a.get('is_accepted')), a.get('score', 0))
        if a.get('score', 0) >= 1 and (best is None or rank > best[0]):
            best = (rank, a)
    return best[1]['body'] if best else None


def threads(messages):
    """A reply from a stored question that is a close paraphrase of this one, or None."""
    if not oc.db():
        return None
    q, subject = bound_question(messages)
    q_w = weights(q)
    if len(q_w) < 2:
        return None
    subject_stems = {oc.stem(w) for w in (subject or '').split()} & set(q_w)
    own = {k: v for k, v in q_w.items() if k not in subject_stems}
    if sum(1 for v in own.values() if v > 2.5) < 2:
        # a vague follow-up ("What should I check first?"): the turn that set the scene says what it is about ("slow", "Windows")
        turns = oc.user_turns(messages)
        if len(turns) > 1:
            extra = {k: v * 0.7 for k, v in weights(turns[-2]).items() if k not in q_w and v > 2.5}
            if not extra:
                return None
            q_w.update(extra)
            q = q.rstrip('?') + ' ' + ' '.join(w for w in oc.content(turns[-2]) if oc.stem(w) in extra)[:80] + '?'
        else:
            return None
    from .advisor import general
    for w in (subject or '').split()[-1:]:
        subject_stems |= {oc.stem(g) for g in general(w)}
    convo = ' '.join(oc.user_turns(messages)[-6:])
    from .applicability import conflict
    cands = []
    # local index first (no network)
    for row in oc.candidates({s: v for s, v in q_w.items()}, {}, limit=120):
        cov, prec, ok = match(q_w, subject_stems, row[1])
        if ok and cov >= 0.62 and prec >= 0.5 and own_cov(q_w, subject_stems, row[1]) >= 0.5 and not conflict(convo, row[1]):
            cands.append((0.6 * cov + 0.4 * prec + 0.04 * oc.answer_quality(row[3]), 'local', row[1], row[3], row[4], row[5], None))
    # Stack Exchange's live similar-question search
    if not cands or max(c[0] for c in cands) < 0.8:
        try:
            from . import stack_source as ss
            import os
            if os.environ.get('CAEL_STACKEXCHANGE', '1') != '0' and os.environ.get('CAEL_WEB_SEARCH', '1') != '0':
                for site in ((wc.STATE.get('plan') or {}).get('sites') or ss.sites_for(q + ' ' + convo, limit=2)):
                    for it in ss.call('similar', None, site=site, title=q[:200], sort='relevance', order='desc', pagesize=6):
                        title = html.unescape(it.get('title', ''))
                        if not it.get('answer_count'):
                            continue
                        cov, prec, ok = match(q_w, subject_stems, title)
                        if ok and cov >= 0.62 and prec >= 0.5 and own_cov(q_w, subject_stems, title) >= 0.5 and not conflict(convo, title):
                            cands.append((0.6 * cov + 0.4 * prec + 0.02 * min(10, it.get('score', 0)) / 10, 'se', title, None, 'se', site,
                                          it['question_id']))
        except LookupUnavailable:
            pass
        except Exception:
            pass
    if not cands:
        return None
    cands.sort(key=lambda c: -c[0])
    for score, where, title, body, source, site, qid in cands[:2]:
        if body is None:
            try:
                body = se_answer(site, qid)
            except Exception:
                body = None
        if not body:
            continue
        text = oc._clean(re.sub(r'<[^>]+>', lambda m: '\n' if m[0].lower() in ('</p>', '<br>', '<br/>', '</li>') else '', html.unescape(body)), limit=750)
        if len(text) < 80 or oc.answer_quality(text) < 0.45 or conflict(convo, text):
            continue
        src = oc.SOURCE_NAMES.get(source, 'Stack Exchange ({site}.stackexchange.com, CC BY-SA 4.0)').format(site=site)
        return dict(route='chat/threads', response=f"From people who've asked the same thing (\"{title}\"):\n\n{text}",
                    sources=[dict(source=src, title=title, url='', licence='CC BY-SA 4.0')],
                    details=f'Question written out as "{q}"; stored question "{title}" (match {score:.2f}) from {src}; answer quoted and trimmed (researchers.py).')
    return None


VISIT = re.compile(r"(?i)\b(?:what (?:should|could|must) (?:i|we) (?:see|do|visit|make sure (?:not to|to) (?:miss|see|do))|"
                   r"(?:must|best) (?:see|sees|things to do|places to visit)|not (?:to )?miss|worth (?:seeing|visiting)|top (?:sights|things))\b")


def place_of(messages):
    turns = oc.user_turns(messages)
    for t in reversed(turns[-8:]):
        for m in re.finditer(r"\b(?:to|in|visiting|visit|around|from|at)\s+((?-i:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?))\b", t):
            name = m[1]
            if name.split()[0] in ('I', 'My', 'The', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'January', 'February',
                                   'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'):
                continue
            return name
    return None


def destination(messages):
    last = oc.user_turns(messages)[-1]
    if not VISIT.search(last):
        return None
    place = place_of(messages)
    if not place:
        return None
    try:
        d = NETWORK.json('https://en.wikivoyage.org/w/api.php?' + urlencode(dict(action='query', prop='extracts', explaintext=1, exsectionformat='wiki',
                                                                                  redirects=1, titles=place, format='json')), ttl=86400, timeout=10)
    except LookupUnavailable:
        return None
    page = next(iter(d.get('query', {}).get('pages', {}).values()), {})
    text = page.get('extract') or ''
    picks = []
    for head in ('See', 'Do'):
        m = re.search(r'\n== ' + head + r' ==\n(.*?)(?=\n== [^=])', text, re.S)
        if not m:
            continue
        body = re.sub(r'\n=+ [^=]+ =+\n', '\n', m[1])
        sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', body)) if 40 <= len(s.strip()) <= 260]
        sents = [s for s in sents if not re.search(r'(?i)\b(?:see also|this article|below|listed|prices?|admission|¥|\$|open daily|tel\b|https?://)', s)]
        picks += sents[:2]
    if len(picks) < 2:
        return None
    days = re.search(r"(?i)\b(\d+|two|three|four|five|six|seven|ten)\s+days?\b", ' '.join(oc.user_turns(messages)[-3:]))
    lead = f"With {days[1]} days in {page.get('title', place)}, the travel guide's own first suggestions are a good backbone:" if days else \
        f"The travel guide's first suggestions for {page.get('title', place)}:"
    tip = ("\n\nPlan one area per day to save travel time, and leave a little slack for wandering; the neighbourhoods themselves are half the fun."
           if days else '')
    return dict(route='chat/destination', response=lead + '\n\n' + '\n'.join('- ' + p for p in picks[:4]) + tip,
                sources=[dict(source='Wikivoyage', title=page.get('title', place), url='https://en.wikivoyage.org/wiki/' + place.replace(' ', '_'),
                              licence='CC BY-SA 4.0')],
                details=f'The "See" and "Do" sections of the Wikivoyage article "{page.get("title", place)}" (researchers.py).')


def respond(messages):
    try:
        return destination(messages)
    except Exception:
        return None
