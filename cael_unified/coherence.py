"""Conversation coherence: a follow-up answer stays on the thing the conversation is about.

People talk about one thing over several turns ("Our holly bush has yellow leaves" ... "Should I feed it?" ... "When is the
best time to prune it?"). Each follow-up is short and names nothing, so a search on its own words drifts: "How much liquid
should I add?" finds a Le Creuset thread, "Would boiling water work?" finds pasta, "How do I make them hold together?"
finds a cartoon character called Flapjack. A person keeps the subject in mind. This module does the same, as a last step
on every reply the team gives:

  1. the conversation's thing: the first noun phrase the user told something about (retrieval.thing_and_problem), with
     its other spellings; a new thing named in the follow-up itself ("Would a pizza stone help?") is allowed too;
  2. a reply that quotes a source must be about it: the source's title names the thing (a thread or an article), or for an
     unsourced stored answer, the answer itself does; an encyclopedia passage about a film, series, character or band is
     never about an everyday thing unless the user is talking about one;
  3. a reply that fails is replaced: first the local index again, searched with the thing required in the thread (the
     follow-up asked about the thing, as a person would mean it), then the advice schema for the thing's class, then an
     honest short answer that keeps the subject.
No model; word matching on the index's own vocabulary.
"""
import re

from . import web_check as wc

QUOTING = re.compile(r'^chat/(?:web-single|web-checked|threads|core-open|core-knowledge|local-knowledge|web-evidence-insufficient)$')
MEDIA = re.compile(r"(?i)\b(?:episode|episodes|series|sitcom|cartoon|animated|television|tv show|film|movie|album|single by|band|novel|"
                   r"video game|character|characters|season \d|starring|directed by|broadcast|aired|network|comic|manga|anime|franchise)\b")
MEDIA_TALK = re.compile(r"(?i)\b(?:film|movie|show|series|episode|cartoon|book|novel|song|album|band|game|character|tv|television|watch|watched)\b")
NEW_THING = re.compile(r"(?i)\b(?:a|an|the|my|our|some)\s+((?:[a-z][a-z'-]+\s+)?[a-z][a-z'-]+)\s*(?:help|work|be|do|fix|stop|make|need|\?|$)")


def stems_of(text):
    from .retrieval import toks
    return set(toks(text))


def thing_forms(messages):
    """(thing words, stems with their other forms) of the conversation, or (None, set())."""
    from .retrieval import thing_and_problem, other_forms, _stem
    turns = wc.user_turns(messages)
    for t in turns[:-1] or turns:
        there = re.match(r"(?i)\s*there(?:'s| is| are)\s+(?:a |an |some |lots of |loads of |little |tiny )?([a-z]+)\b", t)
        if there:
            parts = [there[1].lower()]          # "There are ants nesting in our beds": the ants
        else:
            try:
                from .team import thing_of
                parts = (thing_of(t) or '').split()     # the whole named phrase ("holly bush")
            except Exception:
                parts = []
            parts = parts or thing_and_problem([t])[0]
        if parts:
            # the most telling word of the thing: "holly" in "holly bush" (not "bush", which bush beans share)
            from .retrieval import idf
            words = [w for w in parts if len(w) >= 3]
            if not words:
                continue
            key = max(words, key=lambda w: idf(_stem(w))) if len(words) > 1 else words[0]
            forms = {_stem(key)} | {_stem(f) for f in other_forms(key)}
            # the other things the user named as theirs in the same telling ("the beef ... in my slow cooker")
            for m in re.finditer(r"(?i)\b(?:my|our)\s+((?:[a-z]+\s+){0,2}[a-z]+)", t):
                ws = [w for w in m[1].lower().split() if len(w) >= 4 and w not in wc.STOP and idf(_stem(w)) >= 4.5]
                if ws:
                    k2 = max(ws, key=lambda w: idf(_stem(w)))
                    forms |= {_stem(k2)} | {_stem(f) for f in other_forms(k2)}
            return parts, forms
    return None, set()


def mentions(text_stems, forms):
    return any(f in text_stems or any(s.startswith(f) for s in text_stems if len(f) >= 4) for f in forms)


def sources_of(reply):
    titles = re.findall(r'\nSource: (.+?) \((?:Stack Exchange|Wikipedia|Simple English|OpenAssistant|Dolly|[A-Za-z .-]+\.[a-z]{2,})', reply)
    titles += re.findall(r'; also "(.+?)" \(', reply)
    return titles


def off_topic(messages, draft):
    """Why a reply leaves the conversation's thing, or None."""
    route = str(draft.get('route', ''))
    reply = str(draft.get('response', ''))
    turns = wc.user_turns(messages)
    if len(turns) < 2 or not (QUOTING.match(route) or route == 'chat/advice-schema'):
        return None
    parts, forms = thing_forms(messages)
    if not forms:
        return None
    if route == 'chat/advice-schema':
        # general advice for another kind of thing (a washing machine's seals for a sourdough starter that smells)
        expected, got = expected_class(messages), schema_class(draft)
        if expected and got and expected != got:
            return f'advice for a {got} problem, but the conversation is about a {expected} one'
        return None
    last = turns[-1]
    m = NEW_THING.search(last)
    if m:
        forms = forms | stems_of(m[1]) - stems_of('it them that this')
    body = reply.split('\n\nSource:')[0]
    if MEDIA.search(body[:600]) and not MEDIA_TALK.search(' '.join(turns)):
        return f'an encyclopedia passage about a film, series or character, not the {parts[-1]}'
    titles = sources_of(reply)
    wiki = re.findall(r'\nSource: (.+?) \(Wikipedia\)', reply)
    said = ' '.join(turns)
    for t in wiki:
        # the name of a work or a person ("The Marvelous Misadventures of Flapjack"): capitalised words the user never wrote
        caps = [w for w in re.findall(r"\b[A-Z][a-z'’]+\b", t)[1:] if w.lower() not in said.lower()]
        if len(caps) >= 2:
            return f'an encyclopedia article about a named work or person ("{t[:50]}"), not the {parts[-1]}'
    if titles:
        if not any(mentions(stems_of(t), forms) for t in titles):
            return f'the source ("{titles[0][:50]}") is not about the {parts[-1]}'
        return None
    if route in ('chat/core-open', 'chat/core-knowledge', 'chat/local-knowledge', 'chat/web-evidence-insufficient'):
        if not mentions(stems_of(body), forms):
            return f'the answer does not mention the {parts[-1]}'
    return None


def expected_class(messages):
    """The advice class the conversation is about, from what the user first told ("sourdough starter" -> food)."""
    parts, _ = thing_forms(messages)
    try:
        from . import advice_schemas
        return advice_schemas.best_class(list(parts or []), wc.user_turns(messages)[:1])
    except Exception:
        return None


def schema_class(draft):
    m = re.search(r'class "([a-z]+)"', str(draft.get('details', '')))
    return m[1] if m else None


def question_forms(text):
    """The follow-up's own content stems with their other spellings ("prune" -> prun; "boiling water" -> boil, water)."""
    from .retrieval import QSTOP, PARTICLES, other_forms, _stem
    out = set()
    for w in wc.words(text):
        if w in QSTOP or w in wc.STOP or w in PARTICLES or len(w) < 3 or w in ('it', 'them', 'they', 'this', 'that'):
            continue
        out.add(_stem(w))
        out |= {_stem(f) for f in other_forms(w) + SAME_ASK.get(w, [])}
        from .retrieval import associates
        out |= {_stem(o) for o, sc in associates(w, 'bt', 4) if sc >= 0.45 and o[:3] == w[:3]}     # pruning, pruned
    return out


# the words stored questions use for the same everyday follow-up ("prune" is asked as "trim" or "shape" just as often)
SAME_ASK = {'prune': ['trim', 'trimming', 'shape', 'cut', 'pruning'], 'pruning': ['trim', 'prune', 'cut'], 'trim': ['prune', 'cut'],
            'feed': ['fertilize', 'fertilizer', 'fertiliser', 'feeding'], 'fertilise': ['fertilize', 'fertilizer', 'feed'],
            'water': ['watering', 'overwatering', 'water'], 'oil': ['lubricate', 'lubricant', 'grease', 'wd'],
            'liquid': ['water', 'stock', 'broth', 'liquid'], 'outside': ['outdoors', 'transplant', 'harden', 'outdoor'],
            'ruined': ['dead', 'salvage', 'save', 'safe', 'bad'], 'ruin': ['dead', 'salvage', 'save'], 'save': ['salvage', 'rescue', 'revive'],
            'rid': ['kill', 'remove', 'eliminate', 'control', 'rid'], 'kill': ['rid', 'remove', 'eliminate'], 'replace': ['replacement', 'new', 'replacing'],
            'clean': ['cleaning', 'wash', 'remove'], 'fix': ['repair', 'fixing'], 'brown': ['sear', 'browning'], 'fridge': ['refrigerator', 'refrigerate'],
            'boiling': ['boil', 'boiled'], 'ignore': ['ignoring', 'ignored'], 'stop': ['prevent', 'stop'], 'last': ['durable', 'long', 'best'],
            'often': ['frequency', 'often'], 'safe': ['safety', 'dangerous', 'toxic'], 'cause': ['causes', 'why', 'reason']}


def thread_answer(messages, board, forms):
    """The index searched with the whole conversation; only threads whose title names the thing and one of the follow-up's
    own words are read, and their advice is put together (web_check.compose)."""
    from . import retrieval as rv
    turns = wc.user_turns(messages)
    asked = question_forms(turns[-1])
    if not asked:
        return None
    plan = dict(board.search or {})
    plan.setdefault('shape', 'steps')
    # what the user first told about the thing, and the follow-up itself: the turns in between would blur the search
    focus = [dict(role='user', content=turns[0]), dict(role='assistant', content='ok'), dict(role='user', content=turns[-1])]
    try:
        hits = rv.search(focus, plan, k=40)
    except Exception:
        return None
    from . import open_chat as oc
    kept = []
    for rank, h in enumerate(hits):
        title = h.doc['title']
        ts = stems_of(title)
        if not mentions(ts, forms) or not mentions(ts, asked):
            continue
        body = oc._clean(h.doc.get('raw_answer') or '', limit=1800)
        if len(body) < 80 or oc.answer_quality(body) < 0.4:
            continue
        site = h.doc.get('site') or ''
        name = f'Stack Exchange ({site})' if h.doc.get('source') == 'se' else {'oasst': 'OpenAssistant', 'dolly': 'Dolly'}.get(h.doc.get('source'), 'stored answer')
        kept.append((10.0 - 0.3 * len(kept), title, [], name, '', body))
        if len(kept) >= 3:
            break
    if not kept:
        return None
    got = wc.compose(kept, dict(plan, need=list(plan.get('need') or []) + sorted(forms)[:1], want=sorted(asked)[:3]), messages)
    if got and not off_topic(messages, got):
        return got
    return None


def replace(messages, board, why):
    """An on-topic reply for a follow-up whose first answer left the thing, or None."""
    parts, forms = thing_forms(messages)
    thing = ' '.join(parts or [])
    factual = re.search(r"(?i)^\s*(?:which|what) (?:country|year|language|century|word|name)|\bwhere (?:does|did) .* come from|\bwho (?:invented|discovered|made)|"
                        r"\bwhat is (?:a |an |the )?\w+ called\b|\bwhat does .* mean\b", wc.user_turns(messages)[-1])
    if getattr(board, 'fact', False) or factual:
        return None                         # a factual follow-up ("which country is the word from?") is not advice
    got = thread_answer(messages, board, forms)
    if got:
        return dict(got, coherence=f'threads about the {thing} that ask the same ({why})')
    try:
        from . import advice_schemas
        sch = advice_schemas.respond(messages, thing)
    except Exception:
        sch = None
    expected = expected_class(messages)
    if sch and str(sch.get('response', '')).strip() and not (expected and schema_class(sch) and schema_class(sch) != expected):
        return dict(sch, coherence=f'advice for the {thing} instead ({why})')
    return None


def keep_on_topic(messages, board, draft):
    why = off_topic(messages, draft)
    if not why:
        return draft
    better = replace(messages, board, why)
    if better:
        return dict(better, replaced_route=draft.get('route'), team=draft.get('team'))
    return draft
