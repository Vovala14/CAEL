"""The last check before a reply leaves (0.4.4, after an outside blind test; test-informed).

When the user sets up a situation in the chat (statements, then a question about them) and asks for one definite thing
(a number, a time, a day, a yes or no, which one, who), the answer has to come from that situation. A web thread, a
general advice template, or a sum about something else can't be right there, and in an outside blind test such replies were common.
This guard replaces them with an honest "I can't work this out" that says what was asked. It never touches exact
solvers, memory, authored explanations, or plain questions about the world ("What is the capital of France?").
Turn it off with CAEL_ANSWER_GUARD=0.
"""
import os
import re

LOOSE = re.compile(r'^chat/(?:web-single|web-closest|web-checked|web-wikipedia|core-open|core-knowledge|advice|advice-schema|counsel|threads|'
                   r'corpus|local-|open-retrieval|plus-talk|talk-|smalltalk|team-last-resort)')
EXACT_WEB = re.compile(r'^chat/web-exact')
SUMS = re.compile(r'^chat/(?:solve-math|calc|reason)')
ADVICE_ASK = re.compile(r"(?i)\b(?:how (?:do|can|should|could) (?:i|we|you)|what should (?:i|we)|any (?:tips|advice|ideas)|recommend|suggest|"
                        r"is it (?:safe|ok|okay|worth)|should i\b|help me (?:with|to|choose|decide|plan|write)|ideas? for|write|draft|explain)")
GENERAL_ASK = re.compile(r"(?i)^\s*(?:why|how does|how do|how is|how are|what (?:is|are) (?:a|an|the)\b(?! (?:total|sum|answer|time|date|day|price|cost|number|code|order))|"
                         r"who (?:is|was|were|invented|wrote|discovered)|when (?:was|were|did) (?!i\b|we\b|my\b|our\b)|define|tell me about)")


def statements(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    text = ' '.join(users[-6:])
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]
    return [s for s in sents if not s.endswith('?')], [s for s in sents if s.endswith('?')]


def question(messages):
    last = [(m.get('content') or '') for m in messages if m.get('role') == 'user'][-1]
    qs = re.findall(r'(?:[^.!?\n]|\.(?=\d))*\?', last)
    q = (qs[-1] if qs else last).strip()
    return re.split(r',\s*(?=(?:who|what|which|when|where|how|is|are|do|does|did|can|could|should)\b)', q)[-1].strip()


def definite(q):
    q = q.lower()
    if re.match(r'(?:which|who|whose|where|when|what time|what day|what date|how many|how much|how long|how old|how far|what(?:\'s| is| was| are)? the|'
                r'what (?:code|number|order|colou?r|price|total)|is|are|was|were|does|do|did|can|could|will|would|must|should (?:i go by|we use))\b', q):
        return True
    return False


def self_contained(messages):
    said, asked = statements(messages)
    words = sum(len(s.split()) for s in said)
    return len(said) >= 2 or words >= 14


def content_words(s):
    stop = set('the a an and or of to in on at for with is are was were be been it its this that these those i you we they he she my our your their '
               'what which who whom when where how why do does did can could should would will there here not no yes if then than so as by from '
               'up down out about into over after before one two three'.split())
    return {w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in stop}


def refuse(messages, draft, why):
    q = question(messages)
    text = ("I can't work this one out reliably from what you've told me, so I won't guess. "
            f"You're asking: \"{q}\" — if you can restate the key facts as short separate sentences, I'll try again.")
    return dict(route='chat/guard-unsure', response=text, sources=[], replaced_route=draft.get('route'),
                details=f'answer guard: {why} (answer_guard.py)')


# ------------------------------------------------------------------ does the reply fit the request at all? (2026-11-23)
TEMPLATE = re.compile(r'^chat/(?:advice|advice-schema|counsel|problem-ask|python-topic-match|core-open|core-knowledge|corpus|threads|open-retrieval|'
                      r'plus-view|local-other)')
REALTIME = re.compile(r'^chat/local-realtime')
LIVE_ASK = re.compile(r"(?i)\b(?:weather|forecast|news|headline|price|prices|stock|share|exchange\s+rate|rate\s+today|score|scores|traffic|open\s+now|"
                      r"right\s+now|currently\s+(?:open|available)|today'?s?|tonight|this\s+(?:week|weekend)|latest|live|current(?:ly)?|now)\b")
WRITE_ASK = re.compile(r"(?i)^\s*(?:please\s+|can\s+you\s+|could\s+you\s+)?(?:write|draft|compose|create|prepare)\s+(?:me\s+)?(?:a|an|the|two|three|one|short|quick)\b")
JSON_ASK = re.compile(r'(?i)\b(?:valid\s+)?json\b')
WRITTEN = re.compile(r'^chat/(?:everyday-poem|writing|compose|draft|email|letter|message|text|codegen|code|python-(?:write|code|script|generated))')
GENERIC_WORDS = set('keep keeps kept come comes coming came doing done make makes making made want wants need needs going know think help work '
                    'really much more also still wrong right good best better thing things stuff time times always never every something anything '
                    'just like very would could should might tell give take takes find show please thanks maybe sure okay what which '
                    'happen happens happened start started stop stopped tried trying keeps getting gets around'.split())


def STEM(w):
    w = w.lower()
    if len(w) > 4 and w.endswith('ies'):
        return w[:-3] + 'y'
    if len(w) > 4 and re.search(r'(?:sses|xes|ches|shes)$', w):
        return w[:-2]
    if len(w) > 5 and w.endswith('ing'):
        return w[:-3]
    if len(w) > 4 and w.endswith('ed'):
        return w[:-2]
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def distinctive(text):
    return {STEM(w) for w in content_words(text) if len(w) >= 3 and w not in GENERIC_WORDS}


def shares_enough(request, reply):
    mine = distinctive(request)
    theirs = distinctive(re.split(r'\n\s*Source:', reply)[0][:700])
    need = 2 if len(mine) >= 5 else 1
    return len(mine & theirs) >= need, len(mine & theirs)


def decline(messages, draft, why, text=None):
    q = question(messages)
    text = text or ("I can't do this one reliably, so I won't give you a made-up answer. "
                    f'You asked: "{q[:160]}". If you break it into a short, specific question, I can try again.')
    return dict(route='chat/guard-unsure', response=text, sources=[], replaced_route=draft.get('route'),
                details=f'answer guard: {why} (answer_guard.py)')


def fit(messages, draft):
    """A reply of the wrong kind or about something else is replaced by an honest decline, whatever the punctuation."""
    route = str(draft.get('route', ''))
    said = str(draft.get('response', ''))
    users = [(m.get('content') or '') for m in messages if m.get('role') == 'user']
    if not users:
        return None
    last = users[-1]
    if JSON_ASK.search(last) and re.search(r'(?i)\b(?:reply|respond|answer|return|output|give)\b.{0,40}\bjson\b|\bjson\s+object\b', last):
        body = re.sub(r'^```(?:json)?\s*|\s*```$', '', said.strip())
        try:
            import json as _j
            _j.loads(body)
        except Exception:
            return decline(messages, draft, f'a {route} reply to a request for JSON',
                           "I can't produce that JSON reliably, so I won't give you something that isn't what you asked for.")
    if WRITE_ASK.search(last) and TEMPLATE.match(route):
        return decline(messages, draft, f'a {route} template for a request to write something',
                       "I can't write that one well, so I won't hand you a template that doesn't fit. I can do short emails, letters "
                       'and poems from patterns; for this, a few key points from you would help me draft it.')
    asks = '?' in last or re.match(r'(?i)\s*(?:please\s+)?(?:explain|tell|show|give|list|describe|help|suggest|recommend|find|solve|calculate|'
                                    r'work\s+out|compare|summari[sz]e|translate|rewrite|fix|check)\b', last)
    if not asks:
        return None         # a plain statement: the follow-up layer acknowledges it
    if REALTIME.match(route) and not LIVE_ASK.search(last):
        return decline(messages, draft, 'a live-data refusal for a question that needs no live data')
    if TEMPLATE.match(route):
        code = ' '.join(re.findall(r'`([^`]+)`', last))
        names = set(re.findall(r'\b[A-Za-z_]\w*\b', code)) - {'print', 'len', 'list', 'dict', 'set', 'str', 'int', 'range', 'append', 'for', 'in', 'if',
                                                              'else', 'return', 'def', 'import', 'None', 'True', 'False', 'and', 'or', 'not', 'is'}
        if names and route.startswith('chat/python') and not any(re.search(r'\b' + re.escape(n) + r'\b', said) for n in names):
            return decline(messages, draft, f'a {route} snippet that uses none of the names in the question\'s code')
        ok, n = shares_enough(last, said)
        if not ok:
            return decline(messages, draft, f'a {route} reply sharing {n} distinctive word(s) with the request')
    return None


def check(messages, draft):
    if os.environ.get('CAEL_ANSWER_GUARD', '1') == '0' or not isinstance(draft, dict):
        return draft
    try:
        got = fit(messages, draft) if os.environ.get('CAEL_FIT_GUARD', '1') != '0' else None
        if got:
            return got
    except Exception:
        pass
    try:
        route = str(draft.get('route', ''))
        said = str(draft.get('response', ''))
        users = [(m.get('content') or '') for m in messages if m.get('role') == 'user']
        if not users or not users[-1].strip().endswith('?'):
            return draft
        q = question(messages)
        told = ' '.join(users[-6:]).lower()
        situation = self_contained(messages)
        # 2026-11-22, test-informed: with the web off, "I couldn't find that online" or a concept entry about something
        # else is no answer to a situation the user set out in the chat; nor is today's date to a question about another date
        if situation and definite(q) and not ADVICE_ASK.search(q) and not GENERAL_ASK.search(q):
            if re.match(r'^chat/(?:web-not-found|web-answer-not-found)', route):
                return refuse(messages, draft, f'a {route} reply to a question about the situation the user described')
            if route.startswith('chat/about-date') and not re.search(r"(?i)\b(?:today|now|current|this (?:week|month|year))\b|\btoday'?s\b", q):
                return refuse(messages, draft, "today's date for a question about another date")
            if route.startswith('chat/concept'):
                stem = lambda w: re.sub(r'(?:ies|es|s|ing|ed)$', '', w)
                body = {stem(w) for w in content_words(said[:600]) if len(w) >= 4}
                if len({stem(w) for w in content_words(q) if len(w) >= 4} & body) < 2:
                    return refuse(messages, draft, 'a concept explanation that does not match the question')
        if LOOSE.match(route):
            if route == 'chat/team-last-resort':
                return refuse(messages, draft, 'nothing answered') if situation else draft
            templated = re.match(r'^chat/(?:advice|advice-schema|counsel)', route)
            if re.match(r'^chat/(?:smalltalk|talk-|plus-talk)', route) and not (situation and definite(q)):
                return draft                    # small talk to small talk is fine
            passage = re.match(r'^chat/(?:core-open|core-knowledge|corpus|open-retrieval|threads)', route)
            if not situation and not templated and not passage:
                return draft                    # a looked-up passage for a plain question: the evidence check already ran
            if passage and not situation:       # 2026-11-23: a stored forum answer must be about the request
                ok, _ = shares_enough(' '.join(users[-3:]), said)
                if not ok or re.search(r'(?i)\b(?:who|whose)\b', q) and re.search(r'\b[A-Z][a-z]+\b', ' '.join(users[:-1])):
                    return refuse(messages, draft, f'a {route} passage that does not fit the conversation')
                return draft
            # a loose reply must be about what the user said (distinctive words in common, generic verbs left out)
            ok, n = shares_enough(told, said)
            if not ok:
                return refuse(messages, draft, f'a {route} reply that shares {n} distinctive word(s) with the conversation')
            if situation and definite(q) and not ADVICE_ASK.search(q) and not GENERAL_ASK.search(q):
                return refuse(messages, draft, f'a {route} reply to a question about the situation the user described')
            return draft
        if ADVICE_ASK.search(q) or GENERAL_ASK.search(q):
            return draft
        if EXACT_WEB.match(route) and situation:
            bold = re.search(r'\*\*(.+?)\*\*', said)
            if bold and bold[1].strip(' .').lower() not in told and not re.search(r'\d', bold[1]):
                return refuse(messages, draft, f'a looked-up "{bold[1]}" that the situation never mentions')
        if SUMS.match(route) and re.match(r'\s*\*\*[\d$€£]', said):
            if not re.search(r"(?i)how (?:many|much|long|far|old)|\btotal\b|\bsum\b|\bleft\b|\bcost\b|\bprice\b|\bpay\b|\bchange\b|\bper\b|"
                             r"\bpercent|%|\btimes\b|\bplus\b|\bminus\b|\bdivided\b|\baverage\b|\bwhat(?:'s| is)\s+[\d(]|\bnumber\b|\bcode\b|\bbalance\b|"
                             r"\bage\b|\bscore\b|\bwhen\b|\bwhat time\b|\bhow (?:fast|big|heavy|tall)|\bhalf\b|\bdouble\b|\btwice\b|\bsquared?\b|"
                             r"\bwork out\b|\bcalculate\b|\bcompute\b|\bconvert\b|\bin (?:cm|mm|m|km|kg|g|minutes|hours|seconds)\b|\bwhat(?:'s| is)\s+\w+\s+(?:of|in)\b|"
                             r"\bcheaper\b|\bbetter (?:deal|value)\b|\bmore\b|\bless\b|\bfewer\b", q):
                return refuse(messages, draft, 'a number for a question that does not ask for one')
        if SUMS.match(route):
            unit = re.search(r'\*\*[\d.,$€£]+ ?([a-z]+)[^*\n]*\*\*', said.lower())      # the unit inside the bold answer
            if unit and unit[1] not in told and unit[1].rstrip('s') not in told:
                return refuse(messages, draft, f'a sum about "{unit[1]}", which the conversation never mentions')
        return draft
    except Exception:
        return draft
