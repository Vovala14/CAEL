"""Swarm compute: several CAEL agents work on one message at once, each with a different reading of it, and fixed
rules pick the reply.

One CAEL reads a message one way. Small things can send it down the wrong path: a greeting or "thanks!" in front of the
question, filler like "quick question" or "ok so", or a follow-up whose "it" points back to an earlier message. The
swarm gives each reading its own agent:

  as asked     the message as written (always run; it is what a single CAEL does)
  core         the same message without greetings, thanks and filler around the question
  standalone   a follow-up with its "it" or "them" replaced by the thing named earlier (coherence.resolved_question)

The agents run in parallel threads, so the extra readings mostly cost waiting time only where they look something up.
A reading that is the same as the message is not run twice, and most messages have only one reading.

The pick is by rules, never by votes:
  1. The kind of evidence behind each reply ranks first. Exact work (solvers, the swarm desk, memory, authored
     situations) beats a checked lookup, which beats general advice, which beats a single quoted thread, which beats
     a fallback ("I couldn't work that out", "Thanks for telling me").
  2. A reply that leaves the conversation's subject (coherence.off_topic) drops one class.
  3. Two independent readings that reach the same answer are corroborated: that breaks a tie within a class.
  4. Otherwise the reply to the message as asked wins a tie. Another reading must be strictly better to replace it.

No model is involved. Turn it off with CAEL_SWARM_COMPUTE=0 to get a single CAEL.
"""
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

LIMIT = 4
NESTED = threading.local()     # .active inside a reading: no swarm within a swarm

EXACT = re.compile(r'^chat/(?:reason|solve-|swarm-|about-|memory-|plus-appointment|plus-schedule|joke|myth|situation$|event-memory|'
                   r'calc|convert|time|date|unit|smalltalk-joke|recall|stated-rate|helper)|^helper/')
CHECKED = re.compile(r'^chat/(?:web-exact|web-checked|concept|core-(?!open|talk|knowledge)|dictionary|definition|wikidata|weather)')
GUIDANCE = re.compile(r'^chat/(?:advice|support|situation-followup|recipe-step|plus-|smalltalk|counsel|listen|emotional|program|code|'
                      r'story|poem|writing|ideas|explain)')
QUOTE = re.compile(r'^chat/(?:web-single|web-closest|core-open|core-knowledge|open-retrieval|corpus|local-|threads|web-evidence)')
WEAK = re.compile(r'fallback|unknown|clarify|unsupported|insufficient|failed|last-resort|talk-feelings|no-repeat|why-no-source|evidence-missing')

GREETING = re.compile(r"(?i)^\s*(?:(?:hi|hello|hey|hiya|yo|good (?:morning|afternoon|evening)|thanks|thank you|thx|cheers|ok|okay|"
                      r"so|well|um+|uh+|right|alright|quick question|one (?:more )?question|question|sorry(?: to bother you)?|"
                      r"i (?:have|got) a (?:quick )?question|can i ask (?:you )?something|just wondering|out of curiosity|"
                      r"by the way|btw)(?:\s+(?:there|cael|again|so much|a lot))?\s*[!,.:;?-]*\s+)+")
POLITE = re.compile(r"(?i)^\s*(?:(?:can|could|would|will) you(?: please)?|please|i'?d like you to|i want you to|i need you to)\s+|"
                    r"[,\s]+(?:please|pls|for me)(?=\s*[?.!]*\s*$)")
HOW_MANY_IN = re.compile(r"(?i)^\s*how many ([a-z]+)\s+(?:is|are|in|make|equals?|is there in|are there in)\s+(\d+(?:\.\d+)?)\s*([a-z]+)\s*\??\s*$")
TRAILING = re.compile(r"(?i)(?:\s*[,.!]?\s*(?:thanks|thank you|thx|cheers|please|pls|in advance|thanks in advance|if you can|"
                      r"if you don't mind)\s*[!.]*)+\s*$")


def rank(reply, messages):
    """The class of a reply's evidence (higher is better), after the off-topic check."""
    route = str((reply or {}).get('route') or '')
    if not reply or not str(reply.get('response') or '').strip():
        return 0
    if WEAK.search(route):
        level = 1
    elif EXACT.search(route):
        level = 5
    elif CHECKED.search(route):
        level = 4
    elif GUIDANCE.search(route):
        level = 3
    elif QUOTE.search(route):
        level = 2
    else:
        level = 3
    try:
        from . import coherence
        if level > 1 and coherence.off_topic(messages, reply):
            level -= 1
    except Exception:
        pass
    return level


def gist(reply):
    """What a reply says, for comparing two readings: its first bold value, or its first words."""
    text = str((reply or {}).get('response') or '')
    bold = re.search(r'\*\*(.+?)\*\*', text)
    if bold:
        return bold[1].strip().casefold()
    return ' '.join(re.findall(r'[a-z0-9]+', text.casefold())[:12])


OPERATION = re.compile(r"(?i)\b(?:more|left|remaining|remain|need|needed|reach|still|difference|than|less|fewer|total|each|per|"
                       r"after|before|altogether|short|away|until|times|percent|half|double|twice|average|between|instead|"
                       r"not|without|except|only|minus|plus|divided|split|share)\b|%")


def preserves(original, rewritten):
    """A rewrite may drop greetings and politeness, never what the question asks: every number, the unit after it and
    every operation word ("more", "left", "need", "per") must still be there. "How many more miles do I need to reach
    10 miles if I've walked 10 km?" may not become "Convert 10 km to miles.", whose exact answer is to another question."""
    def numbers(t):
        return sorted(re.findall(r'\d+(?:\.\d+)?', t))
    def units(t):
        return {w.casefold().rstrip('s') for w in re.findall(r'\d+(?:\.\d+)?\s*([a-zA-Z]{1,12})', t)}
    def operations(t):
        return {m.casefold() for m in OPERATION.findall(t)}
    if numbers(original) != numbers(rewritten):
        return False
    if not units(original) <= units(rewritten) | {u.casefold().rstrip('s') for u in re.findall(r'[a-zA-Z]+', rewritten)}:
        return False
    return operations(original) <= operations(rewritten)


def readings(messages):
    """[(name, messages)] — the message as asked first, then the other readings that differ from it."""
    last = messages[-1]
    text = str(last.get('content') or '')
    out = [('as asked', messages)]
    core = TRAILING.sub('', GREETING.sub('', text)).strip()
    if core and core != text.strip() and len(core.split()) >= 2:
        out.append(('core', messages[:-1] + [dict(last, content=core[:1].upper() + core[1:])]))
    # "Can you convert 10 kilometres to miles please?" -> "Convert 10 kilometres to miles."
    plain = POLITE.sub('', core or text).strip().rstrip('?').strip()
    if plain and plain != (core or text).strip() and re.match(r'(?i)(?:convert|calculate|work out|find|tell me|give me|list|explain|define|translate)\b', plain):
        out.append(('request', messages[:-1] + [dict(last, content=plain[:1].upper() + plain[1:] + '.')]))
    # "How many miles is 10 kilometers?" -> "Convert 10 kilometers to miles."
    m = HOW_MANY_IN.match(core or text)
    if m:
        out.append(('convert', messages[:-1] + [dict(last, content=f'Convert {m[2]} {m[3]} to {m[1]}.')]))
    try:
        from . import coherence
        alone = coherence.resolved_question(messages)
    except Exception:
        alone = None
    if alone and alone.strip() != text.strip():
        out.append(('standalone', messages[:-1] + [dict(last, content=alone)]))
    seen, unique = set(), []
    for name, msgs in out:
        key = str(msgs[-1].get('content') or '').strip().casefold()
        if name != 'as asked' and not preserves(text, msgs[-1].get('content') or ''):
            continue                                # a rewrite that lost a number, a unit or the operation is not run
        if key not in seen:
            seen.add(key)
            unique.append((name, msgs))
    return unique


def choose(results, messages):
    """The reply the rules pick from [(name, reply)], with the reason. results[0] is the message as asked."""
    scored = []
    for i, (name, reply) in enumerate(results):
        level = rank(reply, messages)
        agree = sum(1 for j, (_, other) in enumerate(results) if j != i and other and gist(other) == gist(reply) and gist(reply))
        scored.append((level, 1 if agree else 0, -i, name, reply))
    best = max(scored, key=lambda s: s[:3])
    level, agreed, _, name, reply = best
    first = scored[0]
    if name != 'as asked' and (level, agreed) <= first[:2]:
        best = first                                 # another reading must be strictly better to replace the message as asked
    return best[4], best[3], [dict(reading=s[3], level=s[0], corroborated=bool(s[1]), route=(s[4] or {}).get('route')) for s in scored]


def run(messages, single, engine, options):
    """Answer with a small swarm of readings when the message has more than one; None to leave it to a single CAEL."""
    if os.environ.get('CAEL_SWARM_COMPUTE', '1') == '0' or getattr(NESTED, 'active', False):
        return None
    found = readings(messages)
    if len(found) < 2:
        return None
    from . import meesix

    def work(item):
        # The message as asked goes through the team (the assistant's own entry checks already ran for it). Every other
        # reading is a new message to a whole CAEL, entry checks included ("Convert 10 kilometres to miles." is answered
        # by a helper there), with this layer switched off inside it so a reading never starts a swarm of its own.
        name, msgs = item
        meesix.INSIDE.task = False
        NESTED.active = name != 'as asked'
        try:
            if name == 'as asked':
                return name, single(msgs, engine, options)
            return name, engine.respond(msgs, **options)
        except Exception:
            return name, None
        finally:
            NESTED.active = False
    with ThreadPoolExecutor(max_workers=min(LIMIT, len(found))) as pool:
        results = list(pool.map(work, found))
    reply, picked, board = choose(results, messages)
    if reply is None:
        return None
    out = dict(reply)
    out['swarm_compute'] = dict(readings=[n for n, _ in found], picked=picked, scores=board)
    if picked != 'as asked':
        out['details'] = (str(reply.get('details') or '') + f' Swarm compute: the "{picked}" reading gave the better-grounded '
                          'reply (swarm_compute.py).').strip()
    return out
