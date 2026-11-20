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


def check(messages, draft):
    if os.environ.get('CAEL_ANSWER_GUARD', '1') == '0' or not isinstance(draft, dict):
        return draft
    try:
        route = str(draft.get('route', ''))
        said = str(draft.get('response', ''))
        users = [(m.get('content') or '') for m in messages if m.get('role') == 'user']
        if not users or not users[-1].strip().endswith('?'):
            return draft
        q = question(messages)
        told = ' '.join(users[-6:]).lower()
        situation = self_contained(messages)
        if LOOSE.match(route):
            if route == 'chat/team-last-resort':
                return refuse(messages, draft, 'nothing answered') if situation else draft
            templated = re.match(r'^chat/(?:advice|advice-schema|counsel)', route)
            if re.match(r'^chat/(?:smalltalk|talk-|plus-talk)', route) and not (situation and definite(q)):
                return draft                    # small talk to small talk is fine
            if not situation and not templated:
                return draft                    # a looked-up passage for a plain question: the evidence check already ran
            # a loose reply must be about what the user said: two distinctive words in common (stems)
            stem = lambda w: re.sub(r'(?:ies|es|s|ing|ed)$', '', w)
            mine = {stem(w) for w in content_words(told) if len(w) >= 4}
            body = re.split(r'\n\s*Source:', said)[0][:600]
            theirs = {stem(w) for w in content_words(body) if len(w) >= 4}
            shared = mine & theirs
            if len(shared) < 2:
                return refuse(messages, draft, f'a {route} reply that shares {len(shared)} distinctive word(s) with the conversation')
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
