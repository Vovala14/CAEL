"""Retrieval chat: answer open-ended requests with a human-written reply to the closest matching request.

Corpus: models/cael-chat-corpus-v1/corpus.sqlite (research/chat_corpus/build.py), about 19,000 prompt -> reply
pairs written by people: OpenAssistant oasst1/oasst2 volunteers (Apache 2.0) and Databricks' dolly-15k
(CC BY-SA 3.0). Nothing is generated: CAEL finds the request that means the same as yours and shows the reply
that was written for it. A reply is only used when the match is close in both directions (your important words
are in the stored request, and its important words are in yours), so a question about rice never gets the answer
written for pasta. The source and licence are shown with every reply.
"""
from functools import lru_cache
import re
import sqlite3

from .bundle import ROOT

PATH = ROOT / 'models' / 'cael-chat-corpus-v1' / 'corpus.sqlite'
STOP = set('a an the and or but if of to in on at for with from by about as is are was were be been being am do does did done have has '
           'had having i me my mine myself you your yours yourself we us our they them their he him his she her it its this that these '
           'those there here what which who whom whose when where why how can could would should will shall may might must just '
           'really very so too also some any all each every no not nor only own same than then such into over under again further '
           'once more most other up down out off both few s t don now please tell give know want need like get got make let lets '
           'thing things something anything way ways good best one ok okay hi hello hey thanks thank yes'.split())
SOURCES = {'oasst2': ('OpenAssistant Conversations (oasst2)', 'Apache 2.0'), 'oasst1': ('OpenAssistant Conversations (oasst1)', 'Apache 2.0'),
           'dolly': ('databricks-dolly-15k', 'CC BY-SA 3.0')}
OPEN_ENDED = re.compile(r"(?i)^\s*(?:how (?:do|can|should|would|could) (?:i|you|we|one)\b|how to\b|what (?:should|can|could) i\b|"
                        r"what(?:'s| is| are) (?:the best|some good|a good|good|some)\b|what are some\b|give me\b|can you (?:help|give|write|explain|suggest|tell me how|recommend)\b|"
                        r"could you (?:help|give|write|explain|suggest)\b|write (?:me )?(?:a|an|some)\b|help me\b|any (?:ideas|advice|tips)\b|"
                        r"i need (?:help|advice|ideas)\b|is it (?:ok|okay|good|bad|normal|healthy|safe|possible)\b|should i\b|"
                        r"why do (?:i|people|we)\b|explain\b|recommend\b|suggest\b|what do you (?:think|recommend|suggest)\b|"
                        r"do you have any\b|what would you\b|tips (?:for|on)\b|ideas for\b|what(?:'s| is) the difference between\b)")


@lru_cache(maxsize=1)
def db():
    if not PATH.exists():
        return None
    return sqlite3.connect(f'file:{PATH}?mode=ro', uri=True, check_same_thread=False)


def stem(word):
    word = word.replace("'", '')
    for suffix in ('ingly', 'edly', 'ings', 'ing', 'ied', 'ies', 'ed', 'es', 's', 'ly', 'er', 'est'):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[:-len(suffix)]
            break
    return word[:-1] if word.endswith('e') and len(word) > 3 else word      # procrastinate / procrastinating -> procrastinat


def content(text):
    return [w for w in re.findall(r"[a-z][a-z0-9']+", text.lower()) if w not in STOP and len(w) > 1]


KINDS = [
    ('preference', r"\b(?:do you (?:like|prefer|enjoy)|which do you prefer|your favou?rite)\b|\w+ or \w+\?\s*$"),
    ('about-you', r"\b(?:are you|do you (?!know)|can you (?:feel|think|see)|how (?:confident|smart|old) are you|your (?:name|opinion))\b"),
    ('why', r"^\s*(?:why|how come)\b"),
    ('list', r"\b(?:ideas?|list|some (?:good|great|fun|nice)?\s*\w+|names?|suggestions?|recommend\w*|examples?|options|ways to)\b"),
    ('write', r"^\s*(?:(?:can|could) you |please )?(?:write|compose|draft|create|generate)\b|\bhelp me (?:write|draft)\b"),
    ('how', r"\bhow (?:do|can|should|would|could|to|does|did)\b|\bwhat(?:'s| is) the best way\b|\bsteps? to\b|\btips?\b|\badvice\b|\bwhat can i do\b"),
    ('should', r"^\s*(?:should|is it (?:ok|okay|good|bad|normal|safe|healthy|wise|better))\b"),
    ('explain', r"^\s*(?:(?:can you |please )?explain|what (?:is|are|does)|describe|tell me about|how does)\b"),
]


def kind(text):
    lower = text.lower().strip()
    for name, pattern in KINDS:
        if re.search(pattern, lower):
            return name
    return 'other'


COMPATIBLE = {('how', 'list'), ('list', 'how'), ('explain', 'how'), ('how', 'explain'),
              ('list', 'write'), ('write', 'list'), ('other', 'how'), ('other', 'list'), ('other', 'explain')}


def best_match(text, previous=''):
    """(score, row) of the closest stored request, or (0, None)."""
    connection = db()
    words = content(text)
    if not connection or not words or len(words) > 14:
        return 0.0, None
    query = ' OR '.join(f'{stem(w)}*' if len(stem(w)) >= 4 else f'"{w}"' for w in dict.fromkeys(words))
    try:
        rows = connection.execute('SELECT p.id, p.prompt, p.reply, p.previous, p.source, p.quality, bm25(prompt_index) '
                                  'FROM prompt_index JOIN pair p ON p.id = prompt_index.rowid WHERE prompt_index MATCH ? '
                                  'ORDER BY bm25(prompt_index) LIMIT 60', (query,)).fetchall()
    except sqlite3.OperationalError:
        return 0.0, None
    asked = {stem(w) for w in words}
    context = {stem(w) for w in content(previous)}
    best, best_score = None, 0.0
    wanted = kind(text)
    for row in rows:
        stored = {stem(w) for w in content(row[1])}
        if not stored:
            continue
        found_kind = kind(row[1])
        if found_kind != wanted and (wanted, found_kind) not in COMPATIBLE:
            continue                                         # "how do I make pancakes?" is not "pancakes or waffles?"
        mine = len(asked & stored) / len(asked)              # how much of the request the stored one covers
        theirs = len(asked & stored) / len(stored)           # how much of the stored request is about what was asked
        # Every important word of a short request must be there; longer ones may miss a quarter. The stored request may add
        # detail (it is then shown as "a similar request"), but at least 40% of it must be about what was asked.
        if mine < (1.0 if len(asked) <= 3 else 0.75) or theirs < (0.8 if len(asked) == 1 else 0.4):
            continue                                         # one shared word ("day") is not a match for "What day is Halloween?"
        follow = 0.1 if row[3] and context and len(context & {stem(w) for w in content(row[3])}) >= 2 else 0.0
        standalone = 0.05 if not row[3] else 0.0            # a first message reads well without its conversation
        score = mine + theirs + 0.15 * (row[5] or 0.5) + follow + standalone + (0.05 if row[4] != 'dolly' else 0)
        if score > best_score:
            best, best_score = row, score
    return best_score, best


def shorten(reply, limit=1100):
    """The reply, trimmed at a paragraph (or sentence) boundary when it is long."""
    reply = reply.strip()
    if len(reply) <= limit:
        return reply
    paragraphs = re.split(r'\n\s*\n', reply)
    out = ''
    for p in paragraphs:
        if len(out) + len(p) > limit and out:
            # A long list after an intro: keep as many whole lines (list items) as fit, not just the intro.
            lines = p.split('\n')
            kept = []
            for line in lines:
                if len(out) + sum(len(k) + 1 for k in kept) + len(line) > limit:
                    break
                kept.append(line)
            if len(kept) >= 2:
                out += '\n\n' + '\n'.join(kept)
            break
        out += ('\n\n' if out else '') + p
    if len(out) > limit:
        sentences = re.split(r'(?<=[.!?])\s+', out)
        out = ''
        for s in sentences:
            if len(out) + len(s) > limit and out:
                break
            out += (' ' if out else '') + s
    if out.count('```') % 2:
        out += '\n```'
    return out.rstrip() + '\n\n(Shortened; ask me for more.)' if len(out) < len(reply) else out


def reply(text, messages=(), open_ended_only=True):
    """A retrieved human-written reply, or None when nothing matches closely enough."""
    if not db() or len(text) > 400:
        return None
    if open_ended_only and not OPEN_ENDED.search(text):
        return None
    if re.search(r'(?i)\b(?:it|this|that|they|them|its|these|those)\b', text) and len(content(text)) <= 2:
        return None              # "Explain how it works": a follow-up about the conversation's topic, not a new request
    previous = next((m['content'] for m in reversed(list(messages)[:-1]) if m.get('role') == 'assistant'), '') if messages else ''
    score, row = best_match(text, previous)
    if row is None:
        return None
    name, licence = SOURCES.get(row[4], (row[4], ''))
    asked = {stem(w) for w in content(text)}
    stored = {stem(w) for w in content(row[1])}
    exact = len(asked & stored) / max(1, len(stored)) >= 0.85
    body = shorten(row[2])
    if not exact:
        # The stored request says more than yours did: say which request this answer was written for.
        body = f'I found a similar request: "{row[1].strip()[:200]}". Here is the answer written for it:\n\n{body}'
    return dict(response=body, route='chat/corpus', sources=[],
                details=(f'A human-written reply from {name} ({licence}), chosen because its original request closely matches '
                         f'yours: "{row[1][:160]}". Retrieved, not generated; no neural model. Match score {score:.2f}.'),
                matched=row[1])
