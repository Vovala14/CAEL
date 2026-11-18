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
import os
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
            tp = thing_and_problem([t])
            parts = parts or tp[0]
            trouble = {w.lower() for w in (tp[1] or [])} if len(tp) > 1 and isinstance(tp[1], (list, tuple, set)) else set()
            # "My car brakes squeak": the thing is the brakes, the squeak is the trouble
            parts = [w for w in parts if w.lower() not in trouble and not re.fullmatch(r"(?i)(?:squeak|squeal|smell|leak|drip|rattl|creak|buzz|hum|click|"
                                                                                        r"grind|stick|ach|hurt|itch|bark|bit|scratch)\w*", w)] or parts
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


# kinds that share words but not answers: a car's brakes are not a bike's rim brakes, a cat is not a dog
KINDS = [(re.compile(r"(?i)\b(?:car|van|truck|lorry|suv|vehicle|motorbike|motorcycle)\b"), re.compile(r"(?i)\b(?:bicycles?|bikes?|rims?|cyclists?|mtb|mountain ?bikes?)\b")),
         (re.compile(r"(?i)\b(?:bicycles?|bikes?|cycling)\b"), re.compile(r"(?i)\b(?:car|vehicle|engine|ignition|clutch|gearbox|steering wheel|mot)\b")),
         (re.compile(r"(?i)\b(?:cat|cats|kitten|kitty)\b"), re.compile(r"(?i)\b(?:dog|dogs|puppy|pup|canine)\b")),
         (re.compile(r"(?i)\b(?:dog|dogs|puppy|pup)\b"), re.compile(r"(?i)\b(?:cat|cats|kitten|feline)\b"))]
SITE_TALK = re.compile(r"(?i)\b(?:stack exchange|stackexchange|stack overflow|wikipedia|reddit|quora) (?:is|was) (?:a|an|the)\b|question-and-answer \(q&a\) websites")
EXPLAINING = re.compile(r'^chat/(?:core-explain|explain)$')


def wrong_kind(turns, body):
    said = ' '.join(turns)
    for mine, other in KINDS:
        if mine.search(said) and not other.search(said) and other.search(body[:900]):
            return other.search(body[:900])[0]
    return None


def repeated(messages, reply):
    said = [str(m.get('content') or '') for m in messages[:-1] if m.get('role') == 'assistant']
    head = reply.strip()[:120]
    return bool(head) and any(s.strip()[:120] == head for s in said)


def off_topic(messages, draft):
    """Why a reply leaves the conversation's thing, or None."""
    route = str(draft.get('route', ''))
    reply = str(draft.get('response', ''))
    turns = wc.user_turns(messages)
    if len(turns) < 2:
        return None
    if SITE_TALK.search(reply) and not re.search(r"(?i)stack|wikipedia|reddit|quora", ' '.join(turns)):
        return 'a passage about the website the answer came from, not an answer'
    if EXPLAINING.match(route) and told_first(turns) and not re.search(r"(?i)^\s*(?:what (?:is|are|does)|why|how (?:does|do) (?:\w+ )?work)\b", turns[-1]):
        if repeated(messages, reply):
            return 'the same explanation again, not an answer to the follow-up'
        if re.search(r"(?i)^\s*(?:is|are|can|could|should|do|does|will|how (?:can|do|should) i)\b", turns[-1]):
            return 'a general explanation, not an answer to the follow-up'
    if not (QUOTING.match(route) or route == 'chat/advice-schema'):
        return None
    if repeated(messages, reply) and len(turns) >= 3:
        return 'the same answer as before, for a different question'
    kind = wrong_kind(turns, reply.split('\n\nSource:')[0])
    if kind:
        return f'advice about a {kind.lower()}, not what the user has'
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


def told_first(turns):
    """The conversation opened by telling a problem ("My bread always comes out flat")."""
    try:
        from .team import told_problem
        return bool(told_problem(turns[0]))
    except Exception:
        return False


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


def named_thing(turns):
    """The thing as the user named it, with its owner words: "my car brakes" -> "my car brakes", "the brakes on my bicycle"
    -> "my bicycle brakes", "our kitchen sink drain" -> "our kitchen sink drain"."""
    first = turns[0]
    m = re.search(r"(?i)\bthe ([a-z]+) on (my|our) ([a-z]+)\b", first)
    if m:
        return f'{m[2].lower()} {m[3].lower()} {m[1].lower()}'
    m = re.search(r"(?i)\b(my|our)\s+((?:[a-z]+\s+){0,2}[a-z]+?)(?=\s+(?:is|are|has|have|keeps?|won'?t|doesn'?t|don'?t|always|(?:squeak|squeal|smell|leak|drip|rattle|creak)s?|"
                  r"make|makes|stopped|started|get|gets|look|looks|turn|turned|went|came|comes|come)\b)", first)
    if m:
        return f'{m[1].lower()} {m[2].lower()}'
    return None


def resolved_question(messages):
    """A follow-up question in a conversation about a told problem, with its 'it/them' replaced by the thing named:
    "How do I clean them?" after "My car brakes squeak" -> "How do I clean my car brakes?". None when nothing to resolve."""
    turns = wc.user_turns(messages)
    if len(turns) < 2 or not turns[-1].strip().endswith('?') or not told_first(turns):
        return None
    named = named_thing(turns)
    last = turns[-1].strip()
    if not named or len(last.split()) > 14:
        return None
    told = re.sub(r"(?i)^\s*(?:my|our)\b", lambda m: m[0].lower(), turns[0].strip().rstrip('.!'))
    told = told[:1].lower() + told[1:]
    m = re.match(r"(?i)^\s*(?:is|could|might|would) (?:it|that) (?:be )?(?:the|my|a|an) ([a-z]+(?: [a-z]+)?)\s*\?$", last)
    if m:
        return f"Is it the {m[1]} when {told}?"                # "Is it the pads?" -> "Is it the pads when my car brakes squeak…?"
    if re.match(r"(?i)^\s*what (?:causes|is causing|could cause|would cause) (?:it|that|this)\s*\?$", last):
        return f"What causes {told}?"
    if re.search(r"(?i)\b(?:them|it|they|these|those)\b", last):
        return re.sub(r"(?i)\b(?:them|it|they|these|those)\b", named, last, count=1)
    if re.search(r"(?i)^\s*(?:is|could|can|should|do|does|will)\b.*\b(?:the|my|our)\s+[a-z]+\s*\?$", last):
        return f"{last.rstrip('?')} on {named}?"              # "Is it the pads?" was caught above; "Could the filter be blocked?" stays
    return None


def thread_answer(messages, board, forms):
    """The index searched with the whole conversation; only threads whose title names the thing and one of the follow-up's
    own words are read, and their advice is put together (web_check.compose)."""
    from . import retrieval as rv
    turns = wc.user_turns(messages)
    asked = question_forms(turns[-1])
    if not asked:
        return None
    m = NEW_THING.search(turns[-1])
    if m:
        # "Is my yeast dead?" in a bread conversation: a thread about the yeast is about the conversation too
        new = {s for s in stems_of(m[1]) if s in asked} - stems_of('it them that this one ones')
        if new:
            forms = set(forms) | new
            asked = (asked - new) or asked
    plan = dict(board.search or {})
    plan.setdefault('shape', 'steps')
    # first the follow-up asked about the thing itself ("How do I clean them?" -> "How do I clean my car brakes?"), the way a
    # person would mean it; then what the user first told plus the follow-up (the turns in between would blur the search)
    hits, seen = [], set()
    queries = []
    named = named_thing(turns)
    if named:
        q = re.sub(r"(?i)\b(?:them|it|they|these|those|ones)\b", named, turns[-1], count=1)
        if q == turns[-1]:
            q = f'{turns[-1].rstrip("?")} {named}?'
        queries.append([dict(role='user', content=q)])
    queries.append([dict(role='user', content=turns[0]), dict(role='assistant', content='ok'), dict(role='user', content=turns[-1])])
    for focus in queries:
        try:
            for h in rv.search(focus, plan, k=40):
                key = h.doc.get('title')
                if key not in seen:
                    seen.add(key)
                    hits.append(h)
        except Exception:
            continue
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
        if wrong_kind(turns, f"{title} {site} {body}"):
            continue                        # a bicycle thread for a car's brakes
        if os.environ.get('CAEL_COHERENCE_DEBUG'):
            print('  kept:', title)
        name = f'Stack Exchange ({site})' if h.doc.get('source') == 'se' else {'oasst': 'OpenAssistant', 'dolly': 'Dolly'}.get(h.doc.get('source'), 'stored answer')
        kept.append((10.0 - 0.3 * len(kept), title, [], name, '', body))
        if len(kept) >= 3:
            break
    if not kept:
        return None
    got = wc.compose(kept, dict(plan, need=list(plan.get('need') or []) + sorted(forms)[:1], want=sorted(asked)[:3]), messages)
    if not got:
        # every kept title already names the thing and the follow-up's words: the answers need not repeat them
        got = wc.compose(kept, dict(plan, need=[], want=sorted(asked)[:3], title_asked=True), messages)
    if os.environ.get('CAEL_COHERENCE_DEBUG'):
        print('  composed:', bool(got), got and off_topic(messages, got), str((got or {}).get('response', ''))[:200])
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
    turns = wc.user_turns(messages)
    if not why and str(draft.get('route', '')) == 'chat/advice-schema' and len(turns) >= 2 and turns[-1].strip().endswith('?'):
        # a practical follow-up ("How do I clean them?"): people who asked the same about the same thing beat general advice
        try:
            _, forms = thing_forms(messages)
            got = thread_answer(messages, board, forms) if forms else None
        except Exception:
            got = None
        if got:
            return dict(got, coherence='threads about the thing that ask the same, before general advice', replaced_route=draft.get('route'), team=draft.get('team'))
        return draft
    if not why:
        return draft
    better = replace(messages, board, why)
    if better:
        return dict(better, replaced_route=draft.get('route'), team=draft.get('team'))
    return draft
