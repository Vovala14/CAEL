"""The Advisor: practical advice put together from several human-written answers to the same question.

open_chat.py returns the single best stored answer, or nothing. For advice and how-to questions ("How often should I
water it?" about a monstera, "What should we sort out first?" before a move, "Any tips for not feeling embarrassed at
the pool?") one forum answer is often long, about a slightly different situation, or missing; Qwen-sized models win
these turns by always saying a few sensible things. The Advisor does what a careful person with a stack of forum
threads would do, with counting and rules only:

1. Subject: what the question is about, with the conversation bound in ("it" = the monstera told two turns ago; "the
   first night" = the camping trip). The subject words are the question's own nouns plus the scene's.
2. Threads: stored questions (285k Stack Exchange / OpenAssistant / Dolly answers, open_chat's index) whose titles are
   about the same subject: the main subject noun must be in the title and most of the question's weight covered.
   Titles about a different named thing (guitar for a piano question) are vetoed.
3. Points: sentences of those answers that give advice (an instruction, "try", "make sure", "you can", "it's best"),
   self-contained (no "this", "as above"), short, and without forum talk.
4. Agreement: a point counts more when other threads say something with the same content words; the top points from
   different threads are kept, near-duplicates dropped.
5. Reply: a short lead, three to five points, and where the threads differ or the subject is personal, one line on
   what would change the advice.

Every point is a quotation of a human-written sentence (lightly trimmed); nothing is invented. No neural model.
"""
import math
import re
from collections import Counter

from . import open_chat as oc

ADVICE = re.compile(r"(?i)^(?:(?:just |also |then |first(?:ly)?,? |finally,? |and )?(?:try|use|keep|make|put|start|avoid|don'?t|do not|never|always|let|give|"
                    r"add|take|check|get|buy|choose|pick|look|set|wait|water|feed|place|move|stop|remember|consider|practi[sc]e|focus|ask|bring|pack|"
                    r"plan|book|label|wrap|leave|clean|wash|cut|mix|bake|cover|fill|go|walk|hold|breathe|relax|rest|drink|eat|reduce|replace|switch|"
                    r"swap|limit|write|tell|talk|say|find|learn|watch|listen|read|wear|sleep|aim|repot|prune|mist|rotate|allow|lower|raise|increase|"
                    r"decrease|keep|schedule|budget|track|save|compare|measure|stretch|warm|cool|soak|store|freeze|layer|sit|stand|spend|count)\b|"
                    r"(?:you (?:can|could|should|might|may want to|will want to|need to|'ll want to|have to)|it(?:'s| is) (?:best|better|a good idea|worth|important|"
                    r"usually (?:best|better|fine|enough))|the (?:best|easiest|simplest|key|trick|main thing) (?:way|thing|is)|a good (?:way|idea|rule|start)|"
                    r"make sure|be sure|i(?:'d| would) (?:recommend|suggest|start)|i recommend|i suggest|one (?:option|thing|way) is|another (?:option|thing|way) is|"
                    r"if you (?:can|want|have|are|need|do)|most (?:people|beginners|plants|dogs|cats)|in general|generally|as a rule|a rule of thumb))")
NOT_SELF = re.compile(r"(?i)^(?:this|that|these|those|it|they|he|she|which|so|but|also,? this|as (?:above|mentioned|i said|others)|the (?:above|former|latter)|"
                      r"same (?:here|for)|yes|no|edit|update|thanks|good luck|welcome)\b|\b(?:above|below|link|this answer|op\b|the op|your question|"
                      r"your photo|your picture|in the picture|the picture|in your case|your (?:post|setup|example))\b")
FIRST_PERSON = re.compile(r"(?i)\b(?:i|i've|i'm|i'd|my|me|we|our|us)\b")
CONTRARY = re.compile(r"(?i)\b(?:however|on the other hand|it depends|depends on|unless|alternatively|but if)\b")
VETO = [set(x.split()) for x in ('guitar ukulele violin cello piano bass drum flute trumpet saxophone harp banjo mandolin',
                                  'dog puppy cat kitten rabbit hamster horse parrot fish bird',
                                  'car bike bicycle motorcycle scooter train bus plane',
                                  'windows mac linux iphone android',
                                  'baby toddler teenager')]


def stem(w):
    return oc.stem(w.lower().replace("'", ''))


def nouns_of(text):
    return [w for w in oc.content(text) if oc.is_noun(w)]


# Class words a specific subject may be generalised to when nothing is stored about it ("monstera" -> "houseplant").
CLASSES = {'plant', 'houseplant', 'vine', 'flower', 'vegetable', 'herb', 'tree', 'shrub', 'succulent', 'dog', 'cat', 'puppy', 'kitten', 'bird',
           'fish', 'rabbit', 'horse', 'guitar', 'coffee', 'tea', 'bread', 'cake', 'pasta', 'sport', 'bicycle', 'car', 'instrument'}
EXTRA_CLASS = {'kitten': ['cat'], 'puppy': ['dog'], 'plant': ['houseplant'], 'vine': ['houseplant', 'plant'], 'houseplant': ['plant'],
               'uke': ['ukulele', 'guitar'], 'ukulele': ['guitar'], 'cycling': ['bike', 'bicycle'], 'bike': ['bicycle'], 'jogging': ['running'],
               'flat': ['apartment', 'house'], 'apartment': ['house'], 'loaf': ['bread'], 'swimming': ['swim'], 'salsa': ['dance', 'dancing']}


def general(word, depth=3):
    """Class words above a noun in WordNet, nearest first, kept only when useful for advice."""
    out = list(EXTRA_CLASS.get(word, []))
    wn = oc.wordnet()
    if wn is None:
        return out
    import json
    w = word
    for _ in range(depth):
        row = wn.execute('SELECT s.hypernyms FROM lemma l JOIN synset s ON s.id = l.synset WHERE lower(l.word) = ? AND l.pos = "noun" '
                         'ORDER BY l.rank LIMIT 1', (w,)).fetchone()
        if not row:
            break
        ups = json.loads(row[0] or '[]')
        if not ups:
            break
        w = ups[0].lower()
        for x in [w] + EXTRA_CLASS.get(w, []):
            if (x in CLASSES or x in EXTRA_CLASS) and x not in out and x != word:
                out.append(x)
    return out


INTENT_STOP = set('wrong right start started thing stuff way actually really need get first much many often long early'.split())


def subject(messages):
    """(intent weights, subject levels [[stems], ...], named things, question): what the last question asks and about what."""
    turns = oc.user_turns(messages)
    last = turns[-1]
    asked = [x for x in re.split(r'(?<=[.!?])\s+', last) if x.strip().endswith('?')]
    q_text = asked[-1] if asked else last
    told = ' '.join(x for x in re.split(r'(?<=[.!?])\s+', last) if not x.strip().endswith('?'))
    intent = {stem(w): oc.idf(stem(w)) for w in oc.content(q_text + ' ' + told) if w.lower() not in INTENT_STOP and oc.idf(stem(w)) > 1.2}
    own = [w.lower() for w in nouns_of(q_text) if oc.idf(stem(w)) > 3.5]
    scene = []
    for t in reversed(turns[:-1][-5:]):
        for w in nouns_of(t):
            w = w.lower()
            if stem(w) not in intent and w not in scene and oc.idf(stem(w)) > 3.0 and not re.match(r'^(?:year|month|week|day|minute|hour|time|name)s?$', w):
                scene.append(w)
    pronoun = re.search(r"(?i)\b(?:it|him|her|them|they|there|this|that|its|his)\b", q_text)
    specific = []
    if own and not (pronoun and len(own) == 1 and oc.idf(stem(own[0])) < 5):
        specific = sorted(own, key=lambda w: -oc.idf(stem(w)))[:2]
    if (pronoun or not specific) and scene:
        specific += sorted(scene[:4], key=lambda w: -oc.idf(stem(w)))[:2]
    specific = list(dict.fromkeys(specific))[:3]
    levels = [[stem(w) for w in specific]]
    gen = []
    for w in specific:
        gen += [g for g in general(w) if g not in specific and g not in gen]
    if gen:
        levels.append([stem(g) for g in gen[:4]])
    for lvl in levels:
        for x in lvl:
            intent.pop(x, None)
    words = {w.lower() for t in turns[-6:] for w in re.findall(r"[A-Za-z]+", t)}
    named = set().union(*[g & words for g in VETO])
    return intent, levels, named, q_text


def threads(messages, limit=8):
    """Stored question/answer pairs about the same subject and asking the same thing, best first."""
    if not oc.db():
        return [], None
    intent, levels, named, q_text = subject(messages)
    if not intent or not levels or not levels[0]:
        return [], None
    itotal = sum(intent.values())
    out = []
    for depth, level in enumerate(levels):
        query = dict(intent)
        for x in level:
            query[x] = 6.0
        rows = oc.candidates(query, {}, limit=250)
        probs = oc.site_probs(query)
        for row in rows:
            title_words = {w.lower() for w in re.findall(r"[A-Za-z]+", row[1])}
            title = {stem(w) for w in re.findall(r"[A-Za-z']+", row[1])}
            extra = {stem(w) for w in oc.content(row[2] or '')} - title
            if not set(level) & title:
                continue
            if any((g & title_words) and not (g & title_words & named) for g in VETO if g & named):
                continue                # a guitar thread for a piano question
            cov = (sum(v for x, v in intent.items() if x in title) + 0.35 * sum(v for x, v in intent.items() if x in extra)) / itotal
            top = max(intent, key=intent.get)
            if cov < 0.4 or (top not in title and top not in extra and cov < 0.6):
                continue
            prec = sum(oc.idf(x) for x in title if x in intent or x in level) / (sum(oc.idf(x) for x in title if oc.idf(x) > 1.2) or 1)
            if prec < 0.3:
                continue
            site_p = probs.get(row[5] if row[4] == 'se' else 'general', 0)
            if site_p < 0.003:
                continue
            score = 0.55 * cov + 0.3 * prec + 0.1 * site_p + 0.03 * math.log1p(max(0, row[8] or 0)) + 0.06 * oc.answer_quality(row[3]) - 0.12 * depth
            if oc.PERSONAL.search(row[1]) and not oc.PERSONAL.search(' '.join(oc.user_turns(messages))):
                score -= 0.06
            out.append((score, row, depth))
        if len([o for o in out if o[2] == depth and o[0] > 0.6]) >= 2:
            break                       # enough about the subject itself: no need to generalise
    out.sort(key=lambda x: -x[0])
    seen, keep = set(), []
    for score, row, depth in out:
        key = row[1].lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        keep.append((score, row, depth))
        if len(keep) >= limit:
            break
    return keep, (intent, levels, q_text)


def points(text):
    """Self-contained sentences of one answer, in order, with whether each gives advice."""
    body = re.sub(r'(?m)^>.*$', '', text.replace('\r', ''))
    body = re.sub(r'https?://\S+|\[(\d+)\]|\*\*|__|`|<[^>]+>', '', body)
    out = []
    for line in re.split(r'\n+', body):
        listed = bool(re.match(r'^\s*(?:[-*•]|\d+[.)])\s', line))
        line = re.sub(r'^\s*(?:[-*•]|\d+[.)])\s*', '', line).strip()
        for x in re.split(r'(?<=[.!?])\s+(?=[A-Z"(])', line):
            x = x.strip().strip('"')
            n = len(x.split())
            if n < 4 or n > 38 or x.endswith(('?', ':')) or not x[:1].isupper():
                continue
            if oc.FORUM.search(x) or NOT_SELF.search(x):
                continue
            mine = FIRST_PERSON.search(x) and not re.match(r"(?i)i(?:'d| would) (?:recommend|suggest)|i recommend|i suggest", x)
            if not x.endswith(('.', '!')):
                x += '.'
            out.append(dict(text=x, advice=bool(ADVICE.search(x)) or listed, mine=bool(mine)))
    return out


def advise(messages):
    """A reply built from the best-matching threads, or None."""
    found, info = threads(messages)
    if not found or found[0][0] < 0.55:
        return None
    intent, levels, q_text = info
    keys = set(intent) | set(levels[0]) | (set(levels[1]) if len(levels) > 1 else set())
    chosen = []
    for rank, (score, row, depth) in enumerate(found[:3]):
        if rank and score < found[0][0] - 0.15:
            break
        sents = points(row[3])
        scored = []
        for i, x in enumerate(sents):
            words = {stem(w) for w in oc.content(x['text'])}
            rel = sum(intent.get(w, 0) for w in words) / (sum(intent.values()) or 1) + 0.1 * len(words & keys)
            val = rel + (0.35 if x['advice'] else 0) - (0.5 if x['mine'] else 0) + 0.15 / (1 + i)
            scored.append((val, i, x, words))
        best = sorted(scored, key=lambda t: -t[0])[:4 if rank == 0 else 2]
        for val, i, x, words in sorted(best, key=lambda t: t[1]):
            if val < 0.35 or any(len(words & c[3]) >= 0.6 * max(1, min(len(words), len(c[3]))) for c in chosen):
                continue
            chosen.append((rank, i, x['text'], words))
        if len(chosen) >= 4:
            break
    if len(chosen) < 2:
        return None
    chosen = chosen[:5]
    lead = lead_line(q_text, levels, found[0][2])
    bullets = '\n'.join('- ' + tidy(c[2]) for c in chosen)
    used = sorted({c[0] for c in chosen})
    titles = [found[r][1][1] for r in used]
    sites = sorted({(found[r][1][4], found[r][1][5]) for r in used})
    src = ', '.join(oc.SOURCE_NAMES[a].format(site=b) for a, b in sites[:3])
    tail = ''
    if re.search(r"(?i)\b(?:ill|sick|pain|hurt|injur|symptom|bleed|vomit|limp|lump|pregnan|allerg|not eating|lethargic)", ' '.join(oc.user_turns(messages)[-2:])):
        tail = "\n\nIf it doesn't settle, or you're worried, it's worth having it looked at by someone qualified."
    return dict(route='chat/advice', response=f"{lead}\n\n{bullets}{tail}", sources=[],
                details=f'From human-written answers ({src}) to: ' + '; '.join(f'"{t[:90]}"' for t in titles)
                        + '. Sentences quoted and trimmed, not generated (advisor.py).')


def tidy(s):
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'(?i)^(?:also|and|then|so|just|finally|firstly|first),?\s+', '', s)
    s = re.sub(r"(?i)^(?:i(?:'d| would) (?:recommend|suggest)|i recommend|i suggest)\s+(?:that\s+)?(?:you\s+)?", '', s)
    return s[:1].upper() + s[1:]


def lead_line(q, levels, depth):
    low = q.lower()
    about = ''
    if depth and len(levels) > 1:
        about = f" (this is what's usually said about {oc.stem(levels[1][0]) and levels[1][0]}s in general, so it should apply)"
    if re.search(r"\bhow often\b|\bhow much\b|\bhow long\b|\bhow early\b|\bwhen should\b", low):
        return f"It varies, but the usual guidance{about}:"
    if re.search(r"\bwhat(?:'s| is) (?:the )?(?:easiest|best|simplest)\b|\bwhich\b", low):
        return f"What people who have done it usually suggest{about}:"
    if re.search(r"\bwrong\b|\bwhy (?:is|are|does|do)\b|\bturning\b", low):
        return f"The usual causes, and what to try{about}:"
    if re.search(r"\bshould (?:i|we)\b|\bis it (?:worth|better|okay|ok)\b|\bwhat do you think\b", low):
        return f"A few things worth weighing{about}:"
    return f"A few things that usually help{about}:"


def respond(messages):
    """The Advisor's reply for an advice or how-to question, or None."""
    turns = oc.user_turns(messages)
    if not turns:
        return None
    last = turns[-1]
    if not oc.ASKING.search(last) or re.search(r"(?i)\b(?:did i|what(?:'s| is) my|remind me|my name|how old (?:am|is|did))\b", last):
        return None
    if re.search(r'\d+\s*(?:[-+*/x×]|times|plus|minus)\s*\d+|\$\s?\d', last):
        return None
    try:
        return advise(messages)
    except Exception:
        return None
