"""Follow-ups in a chat (0.4.4 fix after release, 2026-11-22). Non-neural: the conversation is rewritten by rules and the
usual pipeline answers the rewritten version.

Written on development probes (research/chat_followups_dev_20261122), not a test set.

- Corrections: "Sorry, it was 5 notebooks, not 3" or "Actually it leaves at 09:10" is applied to the earlier turn. A
  corrected question is answered again, and a corrected statement is acknowledged. Later questions see the corrected
  conversation.
- What-if: "And for 14 people?", "What about 9 students?", "And 20%?" or "And if she pays another £5?" reworks the
  previous question with the new value, or with the new event added.
- About the last answer: "How did you get that?" gives the working; "Are you sure?" works it out again; "In one
  sentence", "Shorter" and "More simply" shorten it.
- About the chat: "What was my first question?" and "What did you say to my first question?".
- Small talk: thanks get a reply that fits the conversation; "Any tips?" after "I've got a big presentation today"
  means tips for the presentation; "By the way, ..." is read without the lead-in.
- Statements: a plain fact the user tells CAEL ("I live in Leeds", "We booked table 12 for 7 pm") gets "Got it: ..."
  instead of a generic "How are you feeling about it?".

Every rewrite falls back to the usual pipeline when the rewritten question doesn't get a real answer.
Turn it off with CAEL_FOLLOWUPS=0.
"""
import os
import re

from . import everyday_exact as ee
from . import word_math as wm

DAY = r'(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
MONTH = ee.MON
CUR = r'[$€£]\s?\d+(?:\.\d+)?'
NUMW = r'(?:\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|hundred)'
WEAK = re.compile(r'guard-unsure|talk-unsure|answer-not-found|team-last-resort|evidence-missing|clarify|web-not-found|web-ambiguous|local-smalltalk|'
                  r'dialogue-|unknown|insufficient|cannot|talk-feelings|core-open')
LEAD = re.compile(r"(?i)^\s*(?:by the way|btw|also|oh,? and|oh|ok(?:ay)?(?:,? so)?|so|right|well|anyway|one more thing|quick question|hey)\s*[,:;.!-]+\s*")
EMOTION = re.compile(r"(?i)\b(?:sad|upset|worried|anxious|stress\w*|scared|afraid|angry|furious|lonely|depress\w*|hurt|cry\w*|died|dead|passed away|"
                     r"failed|fail|lost|miss(?:ing)?|grief|grieving|broke up|dumped|fired|sick|ill|pain|hate|love|excited|nervous|overwhelm\w*|"
                     r"exhausted|tired|burn\w* out|feel\w*|happy|glad|proud|terrible|awful|horrible)\b")
PROBLEM = re.compile(r"(?i)\b(?:broken|broke|not working|won'?t|doesn'?t work|keeps|error|problem|issue|crash\w*|stuck|leak\w*|fault)\b")


def users_of(messages):
    return [i for i, m in enumerate(messages) if m.get('role') == 'user']


def bold(text):
    m = re.search(r'\*\*(.+?)\*\*', text or '')
    return m[1].strip() if m else None


def weak(reply):
    return not reply or WEAK.search(str(reply.get('route', ''))) or not str(reply.get('response', '')).strip()


# ------------------------------------------------------------------ typed values
def values(text):
    """[(kind, start, end, text, extra)] for clock times, weekdays, dates, money, percentages, counted things, numbers."""
    got, taken = [], []

    def add(kind, m, extra=None, g=0):
        s, e = m.span(g)
        if any(a < e and s < b for a, b in taken):
            return
        taken.append((s, e))
        got.append((kind, s, e, m[g], extra))
    for m in re.finditer(r'(?i)\b(?:\d{1,2}\s+' + MONTH + r'|' + MONTH + r'\s+\d{1,2})(?:st|nd|rd|th)?(?:,?\s+\d{4})?\b', text):
        add('date', m)
    for m in re.finditer(r'(?i)\b' + ee.CLOCK + r'(?![\w])', text):
        add('clock', m)
    for m in re.finditer(r'(?i)\b' + DAY + r'\b', text):
        add('day', m)
    for m in re.finditer(CUR, text):
        add('money', m)
    for m in re.finditer(r'\b\d+(?:\.\d+)?\s*%', text):
        add('pct', m)
    for m in re.finditer(r'(?i)\b(' + NUMW + r')\s+(?:more\s+|extra\s+|other\s+)?([a-z]{3,})\b', text):
        noun = m[2].lower()
        if noun in ('and', 'or', 'of', 'the', 'to', 'for', 'per', 'each', 'instead', 'more', 'than', 'times', 'percent'):
            continue
        add('qty', m, _stem(noun), 1)
    for m in re.finditer(r'(?i)\b' + NUMW + r'\b', text):
        add('num', m)
    return sorted(got, key=lambda v: v[1])


def _stem(w):
    w = w.lower()
    if w.endswith('ies') and len(w) > 4:
        return w[:-3] + 'y'
    if re.search(r'(?:ss|x|ch|sh)es$', w):
        return w[:-2]
    if w.endswith('s') and not w.endswith('ss') and len(w) > 3:
        return w[:-1]
    return w


def _before(text, start, k=2):
    return [w.lower() for w in re.findall(r"[A-Za-z']+", text[:start])[-k:]]


def substitute(text, new_text, new_val):
    """Put new_val (from new_text) in place of the matching value in text, or None when it isn't clear which one."""
    kind, s, e, raw, extra = new_val
    cands = [v for v in values(text) if v[0] == kind or (kind == 'num' and v[0] == 'qty') or (kind == 'qty' and v[0] == 'num')]
    if kind == 'qty':
        same = [v for v in cands if v[0] == 'qty' and v[4] == extra]
        if not same:
            return None
        cands = same
    if not cands:
        return None
    if len(cands) > 1:
        qs = [m.span() for m in re.finditer(r'[^.!?]*\?', text)]
        in_q = [v for v in cands if qs and qs[-1][0] <= v[1] < qs[-1][1]]
        if len(in_q) == 1 and kind == 'qty':
            cands = in_q            # "for 4 people ... for 10 people?": the question's own value
    if len(cands) > 1:
        ctx = set(_before(new_text, s, 3))
        if kind == 'date' and ctx & {'until', 'till', 'to', 'by'}:
            cands = cands[-1:]
        elif kind == 'date' and ctx & {'from', 'since'}:
            cands = cands[:1]
        else:
            near = [v for v in cands if set(_before(text, v[1], 3)) & ctx - {'the', 'a', 'an', 'and', 'it', 'i', 'if'}]
            if len(near) != 1:
                return None
            cands = near
    k, a, b, old, _ = cands[0]
    if kind in ('num', 'qty') and k in ('num', 'qty'):
        num_new = re.match(NUMW, raw, re.I)[0]
        return text[:a] + num_new + text[b:]
    if kind == 'date' and not re.search(r'\d{4}', raw):
        year = re.search(r'\d{4}', old)
        if year:
            raw = raw + ' ' + year[0]
    return text[:a] + raw + text[b:]


# ------------------------------------------------------------------ corrections
CORR = re.compile(r"(?i)^\s*(?:sorry|oops|whoops|actually|wait|correction|my (?:mistake|bad)|no,|i meant|i mean|make (?:that|it)|scratch that|typo)\b")


def correction_of(text):
    """(old_text or None, new value) when the message corrects something said before."""
    t = text.strip()
    m = re.search(r'(?i)\b(?:it was|it\'s|it is|make (?:that|it)|i meant|i mean|there (?:were|are|was|is)|should be|it should be)?\s*(?P<new>[^,.;!?]+?),?\s+not\s+(?P<old>[^,.;!?]+?)\s*[.!]?$', t)
    if m and (CORR.search(t) or re.search(r'(?i)\bnot\b', t)):
        nv = values(m['new'])
        if nv:
            return m['old'].strip(), nv[-1], m['new']
    if CORR.search(t) and '?' not in t:
        body = CORR.sub('', t).strip(' ,:-')
        nv = values(body)
        if len(nv) == 1 or (nv and len({v[0] for v in nv}) == 1 and len(nv) <= 2):
            return None, nv[0], body
    return None


def corrected_view(messages):
    """The conversation with every correction applied to the earlier user turns, the correction turns themselves (and
    CAEL's replies to them) left out. Also returns what the last correction changed, when the last turn is one."""
    msgs = [dict(m) for m in messages]
    changed = False
    last_change = None
    i = 0
    out = []
    for idx, m in enumerate(msgs):
        if m.get('role') == 'user':
            c = correction_of(m['content'])
            prior = [j for j, x in enumerate(out) if x.get('role') == 'user']
            if c and prior:
                old, nv, new_text = c
                done = False
                for j in reversed(prior[-3:]):
                    t = out[j]['content']
                    if old:
                        pat = re.compile(r'(?i)\b' + re.escape(old) + r'\b')
                        if pat.search(t):
                            num_old = re.match(NUMW, old, re.I)
                            rest = re.match(r'(?i)' + NUMW + r'\s+(\w+)', new_text.strip())
                            if num_old and rest and num_old[0] == old.strip():
                                new_t = re.sub(r'(?i)\b' + re.escape(old) + r'(?=\s+' + re.escape(rest[1][:4]) + r')', re.match(NUMW, new_text.strip(), re.I)[0], t, count=1)
                                if new_t == t:
                                    new_t = pat.sub(re.match(NUMW, new_text.strip(), re.I)[0], t, count=1)
                            else:
                                new_t = pat.sub(new_text.strip(), t, count=1)
                            out[j] = dict(out[j], content=new_t)
                            done = True
                    else:
                        new_t = substitute(t, new_text, values(new_text)[0] if values(new_text) else nv)
                        if new_t and new_t != t:
                            out[j] = dict(out[j], content=new_t)
                            done = True
                    if done:
                        last_change = (j, t, new_t, nv[3], old)
                        break
                if done:
                    changed = True
                    if idx == len(msgs) - 1:
                        return out, last_change, True
                    if idx + 1 < len(msgs) and msgs[idx + 1].get('role') == 'assistant':
                        msgs[idx + 1] = dict(msgs[idx + 1], role='skip')
                    continue
        if m.get('role') == 'skip':
            continue
        out.append(m)
    return out, (last_change if changed else None), False


# ------------------------------------------------------------------ follow-ups about the last answer
def last_qa(messages):
    """(index of the user turn that asked the last real question, its text, CAEL's reply) before the last message."""
    for i in range(len(messages) - 2, -1, -1):
        m = messages[i]
        if m.get('role') == 'user' and m['content'].strip().endswith('?'):
            reply = messages[i + 1]['content'] if i + 1 < len(messages) and messages[i + 1].get('role') == 'assistant' else ''
            return i, m['content'], reply
    return None


WORKING_Q = re.compile(r"(?i)^\s*(?:how did you (?:get|work out|calculate|figure out|come up with) (?:that|this|it)|how(?:'d| did) you get that|"
                       r"show (?:me )?(?:the |your )?(?:working|workings|steps|maths|math)|can you show (?:your |the )?(?:working|steps)|"
                       r"how so|explain (?:that|your answer|how)|where (?:did|does) (?:that|it) come from|why(?: is that)?|why\?)\s*[?!.]*\s*$")
SURE_Q = re.compile(r"(?i)^\s*(?:are you sure|are you certain|is that (?:right|correct|true)|really|double[- ]check(?: that| it)?|"
                    r"can you check(?: that| it)?|you sure)\s*[?!.]*\s*$")
SHORT_Q = re.compile(r"(?i)^\s*(?:(?:can you |could you |please )?(?:say|put|explain|tell me|give me|sum(?:marise|marize)) (?:that|it|this)? ?(?:again )?"
                     r"(?:in one sentence|in a sentence|more simply|simpler|in simple(?:r)? (?:terms|words)|briefly|more briefly|shorter|in short)|"
                     r"(?:in )?one sentence(?:,? please)?|shorter(?:,? please)?|simpler(?:,? please)?|tl;?dr|too long|"
                     r"(?:explain it |say it )?like i'?m (?:five|5)|eli5|(?:can you )?simplify (?:that|it)|make it (?:shorter|simpler))\s*[?!.]*\s*$")


def working(reply_text):
    head = bold(reply_text)
    if not head:
        return None
    text = re.split(r'\n\s*(?:\*\*Source|Source:)', reply_text)[0]
    rest = text.split('**' + head + '**', 1)[1] if '**' + head + '**' in text else ''
    rest = re.sub(r'^\s*[:.,]?\s*', '', rest).strip()
    if rest.startswith('(') and re.search(r'\)\.?$', rest):
        rest = re.sub(r'\)\.?$', '', rest[1:]).strip()
    rest = re.sub(r'(?i)^working:\s*', '', rest)
    pre = text.split('**' + head + '**', 1)[0].strip()
    if len(rest) < 8:
        return None
    return head, pre, rest


def sentences(text):
    text = re.split(r'\n\s*(?:\*\*Source|Source:)', text)[0]
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'\s*\n+\s*[-•]\s*', '. ', text)
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z"])', text) if s.strip()]


def shorten(reply_text, simple):
    ss = sentences(reply_text)
    if not ss:
        return None
    if not simple:
        first = ss[0]
        if len(first.split()) < 6 and len(ss) > 1:
            first = first.rstrip('.!') + ': ' + ss[1][0].lower() + ss[1][1:]
        return first
    keep = []
    for s in ss:
        s2 = re.sub(r'\s*\([^)]*\)', '', s)
        s2 = re.sub(r'(?i)[:;,]\s*(?:this is|that is|called|known as)\s+[^.]*', '', s2)
        if re.search(r'(?i)\b(?:wavelengths?|molecules?|coefficient|equation|frequency|algorithm|function|asymptot)\w*', s2) and keep:
            continue
        keep.append(s2.strip())
        if len(' '.join(keep).split()) > 28 or len(keep) == 2:
            break
    return ' '.join(keep)


RECALL_Q = re.compile(r"(?i)\bwhat (?:was|were) (?:my|the) (?P<which>first|last|previous|earlier|second)\s+(?:question|thing i asked)|"
                      r"what did i (?:first )?ask (?:you )?(?:first|before that|earlier|at the start)|what was the first thing i asked")
ANSWER_RECALL_Q = re.compile(r"(?i)\bwhat (?:was|did you say|did you answer|did you tell me)\s+(?:the answer\s+|as the answer\s+)?(?:to|for)\s+my\s+(?P<which>first|last|previous|earlier|second)\s+question")


def recall(messages):
    last = messages[-1]['content']
    qs = [(i, m['content']) for i, m in enumerate(messages[:-1]) if m.get('role') == 'user' and '?' in m['content']]
    m = ANSWER_RECALL_Q.search(last)
    if m and qs:
        i, q = qs[0] if m['which'] in ('first',) else qs[1] if m['which'] == 'second' and len(qs) > 1 else qs[-1]
        a = messages[i + 1]['content'] if i + 1 < len(messages) and messages[i + 1].get('role') == 'assistant' else ''
        head = bold(a) or (sentences(a)[0] if sentences(a) else '')
        if head:
            return dict(route='chat/followup-recall', sources=[], response=f'Your {m["which"]} question was "{q.strip()}", and I answered **{head}**.')
    m = RECALL_Q.search(last)
    if m and qs:
        which = (m['which'] or 'first').lower() if m.groupdict().get('which') else 'first'
        i, q = qs[0] if which == 'first' else qs[1] if which == 'second' and len(qs) > 1 else qs[-1]
        return dict(route='chat/followup-recall', sources=[], response=f'Your {which} question was: "{q.strip()}"')
    return None


# ------------------------------------------------------------------ small talk
THANKS = re.compile(r"(?i)^\s*(?:(?:ok(?:ay)?|great|perfect|cool|nice|brilliant|lovely|awesome)[,!.]?\s+)?(?:thanks|thank you|thank u|thx|ty|cheers|ta|many thanks|"
                    r"much appreciated|that(?:'s| is| was) (?:helpful|great|useful|perfect|brilliant|really helpful|very helpful|lovely|kind))\b[^?]{0,60}$")
TIPS_Q = re.compile(r"(?i)^\s*(?:do you have |have you got |got )?(?:any|some|a few)?\s*(?:last[- ]minute|quick|good|useful|practical)?\s*"
                    r"(?:tips|advice|ideas|suggestions|pointers)(?:\s+(?:for me|please))?\s*[?!.]*\s*$|^\s*(?:any (?:tips|advice))\s*[?!.]*$")
EVENT = re.compile(r"(?i)\b(?:i(?:'ve| have)? got|i have|i've|there'?s|i'?m (?:doing|giving|having|preparing for|starting|sitting|taking|running|hosting))\s+"
                   r"(?P<art>a|an|my|the|our)\s+(?P<t>(?:[a-z-]+\s){0,3}?(?:presentation|interview|exam|test|meeting|date|speech|talk|match|race|"
                   r"game|audition|appointment|party|wedding|trip|flight|deadline|shift|class|lesson|performance|recital|pitch|review|"
                   r"first day|surgery|operation|driving test|marathon|competition))\b(?P<when>\s+(?:today|tomorrow|tonight|this (?:morning|afternoon|evening|week)|"
                   r"next week|on \w+))?")


GUILT = re.compile(r"(?i)\b(?:should(?:'ve| have) (?:[a-z]+ed|known|seen|done|been|gone|taken|spent|kept|told|said|stayed|left)\b|i wish i(?:'d| had)|"
                   r"(?:it'?s|it was|this is) (?:all )?my fault|i blame myself|if only i(?:'d| had)?|could(?:'ve| have) (?:done|saved|stopped|prevented)|"
                   r"i (?:let (?:her|him|them|everyone) down|failed (?:her|him|them))|why didn'?t i)\b")
LOSS = re.compile(r"(?i)\b(?:died|dead|passed away|put (?:to sleep|down)|lost (?:my|our)|death|funeral|gone now)\b")
SETBACK = re.compile(r"(?i)\b(?:failed|didn'?t pass|rejected|didn'?t get (?:the|in)|got fired|lost my job|broke up|dumped|messed up)\b")


def guilt_reply(view):
    last = view[-1]['content']
    if not GUILT.search(last) or '?' in last and not re.search(r'(?i)\bmy fault\b', last):
        return None
    before = ' '.join(m['content'] for m in view[:-1] if m.get('role') == 'user')
    if LOSS.search(before + ' ' + last):
        text = ("That thought is one of the most common parts of grief, and it's usually unfair to yourself. Animals and people often "
                "hide illness until it's far along, and things look obvious only with hindsight you didn't have at the time. "
                "Feeling this guilty is a sign of how much you cared. Would it help to talk about her, or about what happened?")
        if not re.search(r'(?i)\b(?:noticed|ill|illness|sick|symptoms?|signs?|vet|doctor)\b', last):
            text = ("Almost everyone who loses someone ends up with a list of things they wish they'd done more of. It's a sign of "
                    "how much they mattered to you, not proof that you let them down: you were living an ordinary life without "
                    "knowing how little time was left. Would it help to talk about them, or about a good memory?")
        him = re.search(r'(?i)\b(?:he|him|his|grandad|grandpa|dad|father|brother|son|husband|uncle)\b', before + last)
        her = re.search(r'(?i)\b(?:she|her|gran|grandma|nan|mum|mom|mother|sister|daughter|wife|aunt)\b', before + last)
        word = 'him' if him and not her else 'her' if her and not him else 'them'
        text = text.replace('talk about her,', f'talk about {word},').replace('talk about them,', f'talk about {word},')
        return dict(route='chat/followup-guilt', sources=[], response=text)
    if SETBACK.search(before + ' ' + last):
        return dict(route='chat/followup-guilt', sources=[], response=(
            "It's easy to replay it and see everything you could have done differently, but you're judging the old you with "
            "information you only have now. One setback says little about what you're capable of. If you like, we can turn "
            "what you'd do differently into a short plan for next time."))
    return None


def thanks_reply(messages):
    told = ' '.join(m['content'] for m in messages if m.get('role') == 'user')
    earlier = told[:-len(messages[-1]['content'])] if len(told) > len(messages[-1]['content']) else ''
    if EMOTION.search(earlier) or SETBACK.search(earlier) or LOSS.search(earlier):
        text = ("You're welcome. I'm glad it helped, even a little. Go easy on yourself, and come back any time you want to "
                "talk it through.")
    elif EVENT.search(told):
        ev = EVENT.search(told)
        text = f"You're welcome, and good luck with the {ev['t']}!"
    else:
        text = "You're welcome! Is there anything else I can help with?"
    return dict(route='chat/followup-thanks', sources=[], response=text)


# ------------------------------------------------------------------ statements
YOU = [(r"\bI'm\b", "you're"), (r"\bI am\b", 'you are'), (r"\bI've\b", "you've"), (r"\bI'd\b", "you'd"), (r"\bI'll\b", "you'll"), (r'\bI\b', 'you'),
       (r'\bmy\b', 'your'), (r'\bMy\b', 'Your'), (r'\bme\b', 'you'), (r'\bmine\b', 'yours'), (r'\bmyself\b', 'yourself'),
       (r"\bwe're\b", "you're"), (r'\bwe\b', 'you'), (r'\bWe\b', 'You'), (r'\bour\b', 'your'), (r'\bOur\b', 'Your'), (r'\bus\b', 'you')]
GENERIC = re.compile(r"(?i)^(?:thanks for telling me\. how are you feeling about it\?|tell me more about that\.|sounds like there's a bit to think about there\.|"
                     r"that sounds annoying, but it's usually fixable)")
FACT = re.compile(r"(?i)^(?:my\s+[\w' -]+?\s+(?:is|are|was|were)\b|i\s+(?:live|work|study|am|'m|have|'ve|was born|grew up|lent|borrowed|booked|bought|paid|owe|"
                  r"moved|use|drive|play|speak)\b|i'm\s+(?:a|an|from|allergic|vegetarian|vegan|meeting|seeing|going|flying|staying|\d)|we\s+(?:booked|have|live|reserved|moved|are|'re)\b|"
                  r"(?:[A-Z][a-z]+)\s+(?:is|are|was|lives|works|paid|owes|wants|likes|has|said|booked|moved)\b|they\s+(?:moved|changed|said|called)\b|"
                  r"(?:she|he|they)\s+(?:paid|owes|gave|moved|said|lives|works)\b|[\w -]+\s+list\s*:|(?:the|our|my)\s+\w+\s+(?:is|was|starts|leaves|opens|closes)\b)")
EDIT = re.compile(r"(?i)^(?:please\s+)?(?:cross|take|tick|strike)\s+(?:off\s+)?\w|^(?:please\s+)?(?:add|remove|drop|delete)\s+\w")


def you_form(text):
    t = text.strip().rstrip('.!')
    for a, b in YOU:
        t = re.sub(a, b, t)
    if t and re.match(r"(?:You|Your|They|She|He|It|The|A|An|There|Packing|Shopping|To-do)\b", t):
        t = t[0].lower() + t[1:]
    return t


def acknowledge(messages, reply):
    last = messages[-1]['content'].strip()
    if '?' in last or EMOTION.search(last) or len(last) > 240:
        return None
    said = str(reply.get('response', '')).strip()
    web_on_statement = str(reply.get('route', '')).startswith(('chat/web-', 'chat/local-realtime')) and \
        not re.search(r'(?i)\b(?:weather|forecast|news|look\s+up|search|find|check|latest|today\'s)\b', last) and \
        re.search(r"(?i)\b(?:[a-z]+ed|gave|lent|handed|passed|went|got|took|bought|sold|made|told|said|left|came|ran|is|are|was|were|has|have|had)\b", last)
    if web_on_statement:
        said = 'Tell me more about that.'     # a statement is not a lookup: "...because hers got soaked in the rain" (2026-11-23)
    hello = re.match(r'(?i)^(good (?:morning|afternoon|evening)|hi|hello|hey)\b[!,. ]*', last)
    if str(reply.get('route', '')) == 'chat/followup-event' and hello and not said.lower().startswith(hello[1].lower()):
        # the task split answered "I've got an interview" on its own: give the greeting back
        return dict(reply, response=hello[1].capitalize() + '! ' + said)
    if len(last.split()) <= 8 and FACT.match(last) and str(reply.get('route', '')).startswith(('chat/advice', 'chat/plus-view', 'chat/talk-')):
        said = 'Tell me more about that.'   # "I'm vegetarian." is a fact about the user, not a request for recipes (2026-11-22)
    ev = EVENT.search(last)
    plain_ack = said.startswith(('Got it', 'Noted', 'OK, noted'))
    if not GENERIC.match(said) and not (str(reply.get('route', '')).startswith('chat/problem-ask') and not PROBLEM.search(last)) \
            and not (ev and plain_ack):
        return None
    hello = re.match(r'(?i)^(good (?:morning|afternoon|evening)|hi|hello|hey)\b[!,. ]*', last)
    if ev:
        when = (ev['when'] or '').strip()
        art = 'your' if ev['art'].lower() in ('my', 'a', 'an') else ev['art'].lower()
        lead = (hello[1].capitalize() + '! ') if hello else ''
        return dict(route='chat/followup-event', sources=[], response=f'{lead}Good luck with {art} {ev["t"]}{" " + when if when else ""}! '
                    f'Would you like a few quick tips for it?')
    if EDIT.match(last):
        try:
            from . import everyday_hard
            users = [m['content'] for m in messages if m.get('role') == 'user'] + ["What's left?"]
            got = everyday_hard.list_edits('\n'.join(users), "What's left?", users)
        except Exception:
            got = None
        if got:
            return dict(route='chat/followup-list', sources=[], response=f'Done. The list is now: {bold(got["response"]) or got["response"]}')
        return dict(route='chat/followup-noted', sources=[], response='Done.')
    sents = [s for s in re.split(r'(?<=[.!])\s+', last) if s.strip()]
    setting = re.match(r"(?i)^(?:please\s+)?(?:scratch\s+that[-—–,:\s]*|actually[,\s]+)?(set|change|update|make|switch)\s+my\s+([\w' -]+?)\s+to\s+(.+?)(?:\s+instead)?[.!]?$", last)
    if setting:         # "Set my preferred pickup location to North Terminal." (2026-11-23)
        what, val = setting[2].strip(), setting[3].strip()
        verb = 'Done' if setting[1].lower() == 'set' else 'Updated'
        return dict(route='chat/followup-noted', sources=[], response=f'{verb}: your {what} is {"now " if verb == "Updated" else ""}{val}.')
    if sents and len(sents) <= 3 and len(last.split()) <= 45 and GENERIC.match(said) and not EDIT.match(last) and \
            not all(FACT.match(s.strip()) for s in sents) and not re.match(r'(?i)^(?:please\s+)?(?:summari[sz]e|write|tell|give|show|explain|help)\b', last):
        # any plain statement of facts gets a short acknowledgement, not "Tell me more about that." (2026-11-23)
        return dict(route='chat/followup-noted', sources=[], response='Got it: ' + '. '.join(you_form(s) for s in sents) + '.')
    if not sents or not all(FACT.match(s.strip()) for s in sents):
        return None
    name = re.match(r"(?i)my name is (?P<n>[A-Z][a-z]+)(?:\s+and\s+(?P<rest>.+))?$", last.rstrip('.!'))
    if name:
        rest = name['rest']
        told = you_form('I ' + rest if rest and not re.match(r'(?i)i\b', rest) else rest) if rest else ''
        return dict(route='chat/followup-noted', sources=[], response=f'Nice to meet you, {name["n"]}!' + (f' Got it: {told}.' if rest else ''))
    keep = ' I\'ll keep that in mind.' if re.search(r'(?i)allergic|vegetarian|vegan|intoleran|can\'t eat|don\'t eat', last) else ''
    return dict(route='chat/followup-noted', sources=[], response='Got it: ' + '. '.join(you_form(s) for s in sents) + '.' + keep)


# ------------------------------------------------------------------ what-if
WHATIF = re.compile(r"(?i)^\s*(?:(?:and|but|ok(?:ay)?|so|now)[,]?\s+)?(?:(?:what|how)\s+about|what\s+if|and\s+if|if|for|with|at|until|till|to|from|"
                    r"same (?:thing |question )?(?:for|with)|instead of that,?|now (?:for|with)|what (?:would|will) it be (?:for|with)|and)\s+(?P<v>.+?)\s*\??\s*$")


def whatif(messages, view, run):
    last = view[-1]['content'].strip()
    if len(last) > 90 or not WHATIF.match(last):
        return None
    qa = last_qa(view)
    if not qa:
        return None
    i, q, reply = qa
    if not bold(reply):
        return None
    v = WHATIF.match(last)['v']
    if re.search(r'(?i)\b(?:how|what|which|who|when|where|why)\b|\b(?:of|from|on) (?:that|it|this)\b', v):
        return None         # "If they refund 50% of that, how much do I get back?" asks its own question
    v = re.sub(r"(?i)^(?:it(?:'s| is| were| was)|there (?:are|were|is|was)|we (?:have|had|are|were)|i (?:have|had|order|ordered|buy|bought|use|used|do|did|want|need))\s+", '', v)
    v = re.sub(r'(?i)\s+instead$', '', v)
    vals = values(v)
    clause = re.match(r"(?i)^(?:if\s+)?(?P<who>she|he|they|i|we|[A-Z][a-z]+)\s+(?P<verb>[a-z]+)\s+(?P<rest>.*\b(?:another|more|again|also|a further|extra)\b.*)$",
                      re.sub(r'(?i)^(?:and\s+|but\s+)?(?:what\s+)?if\s+', '', last.rstrip('?').strip()))
    tries = []
    if clause:
        st = clause[0][0].upper() + clause[0][1:] + '.'
        tries.append(view[:i] + [dict(role='user', content=st), dict(role='assistant', content='Got it.'), dict(role='user', content=q)])
    off = last.find(v)
    vals = [x for x in values(last) if off < 0 or x[1] >= off] if vals else vals
    if len(vals) >= 1:
        nv = [x for x in vals if x[0] != 'num'] or vals
        v = last
        new_q = substitute(q, v, nv[0])
        if not new_q:
            for j in range(i - 1, -1, -1):          # the value may be in an earlier statement, not in the question
                if view[j].get('role') == 'user':
                    nt = substitute(view[j]['content'], v, nv[0])
                    if nt:
                        tries.append(view[:j] + [dict(view[j], content=nt)] + view[j + 1:i + 1])
                        break
        else:
            tries.append(view[:i] + [dict(role='user', content=new_q)])
    for msgs in tries:
        got = run(msgs)
        if not weak(got) and bold(str(got.get('response', ''))):
            return dict(got, route='chat/followup-whatif', replaced_route=got.get('route'), asked_as=msgs[-1]['content'])
    return None


def tips(messages, view, run):
    last = view[-1]['content']
    if not TIPS_Q.match(last):
        return None
    for m in reversed(view[:-1]):
        if m.get('role') == 'user':
            ev = EVENT.search(m['content'])
            if ev:
                q = f'Any tips for {ev["t"]}?' if ev['t'].startswith(('a ', 'an ')) else f'Any tips for a {ev["t"]}?'
                got = run(view[:-1] + [dict(role='user', content=q)])
                if not weak(got):
                    return dict(got, asked_as=q)
            break
    return None


def pronoun(messages, view, run):
    last = view[-1]['content']
    if not re.search(r'(?i)\b(?:she|he|her|his|him)\b', last) or len(last) > 120:
        return None
    qa = last_qa(view)
    if not qa:
        return None
    i, q, reply = qa
    if i != len(view) - 3:
        return None
    asked = set(re.findall(r'[A-Z][a-z]+', q))
    people = [p for p in re.findall(r'\b([A-Z][a-z]+(?:\s(?:van |de |von )?[A-Z][a-z]+)+)\b', re.split(r'\n\s*\*\*Source', reply)[0])
              if not set(p.split()) & asked and not re.match(r'(?:The|This|That|Source|Wikipedia|Wikidata)\b', p)]
    if len(set(people)) != 1:
        return None
    who = people[0]
    q2 = re.sub(r'(?i)\b(?:she|he)\b', who, last, count=1)
    q2 = re.sub(r'(?i)\b(?:his|her)\b', who + "'s", q2, count=1) if q2 == last else q2
    if q2 == last:
        return None
    got = run(view[:-1] + [dict(role='user', content=q2)])
    if weak(got):
        return None
    return dict(got, asked_as=q2)


# ------------------------------------------------------------------ the layer
def handle(messages, run):
    """The reply to the last message: a follow-up answered here, else the usual pipeline (`run`) on the conversation as
    corrected, with a plain acknowledgement for statements."""
    if os.environ.get('CAEL_FOLLOWUPS', '1') == '0':
        return run(messages)
    try:
        got = vent(messages) or next_message(messages) or setting_ack(messages)
        if got:
            return got
        got = _handle(messages, run)
    except Exception:
        got = run(messages)
    got = listen_only(messages, got)
    if isinstance(got, dict):       # "Oak Road instead." -> "Oak Road."
        got = dict(got, response=re.sub(r'^(\*{0,2}[^.\n]{1,60}?)\s+instead(\*{0,2}\.)', r'\1\2', str(got.get('response', ''))))
    return got


SETTING = re.compile(r"(?i)^(?:please\s+)?(?:(?:ok(?:ay)?|no|wait|sorry|scratch\s+that|actually|on\s+second\s+thought)[-—–,:;.!\s]+)*"
                     r"(set|change|update|make|switch|move)\s+my\s+([\w' -]+?)\s+to\s+(.+?)(?:\s+instead)?\s*[.!]?$")


def setting_ack(messages):
    """'Set my pickup location to North Terminal.' / 'Scratch that, change it to South Gate instead.' -> confirm it (2026-11-23)."""
    last = (messages[-1].get('content') or '').strip()
    m = SETTING.match(last)
    if not m and '?' not in last:      # "Update that, use alex@new.org as my backup contact email instead."
        u = re.match(r"(?i)^(?:please\s+)?(?:(?:update|change|replace|correct)\s+(?:that|it)|scratch\s+that|actually|instead)?[-—–,:;.!\s]*"
                     r"(?:please\s+)?use\s+(\S+(?:\s+\S+){0,3}?)\s+as\s+(?:my|our|the)\s+([\w' -]+?)(?:\s+instead)?(?:\s+from\s+now\s+on)?\s*[.!]?$", last)
        if u:
            return dict(route='chat/followup-noted', sources=[], response=f'Updated: your {u[2].strip()} is now {u[1].strip()}.')
    if not m or '?' in last:
        return None
    what, val = m[2].strip(), m[3].strip()
    verb = 'Done' if m[1].lower() == 'set' else 'Updated'
    return dict(route='chat/followup-noted', sources=[], response=f'{verb}: your {what} is {"now " if verb == "Updated" else ""}{val}.')


VENT = re.compile(r"(?i)\b(?:(?:just\s+)?need\s+to\s+(?:vent|rant|let\s+off\s+steam)|let\s+me\s+(?:vent|rant)|just\s+(?:listen|hear\s+me\s+out)|"
                  r"(?:don't|do\s+not|no)\s+(?:ask\s+(?:me\s+)?(?:any\s+)?questions|give\s+(?:me\s+)?(?:any\s+)?advice|advice|fix\s+it|solutions?))\b")


NEXT = re.compile(r"(?i)\b(summari[sz]e|sum\s+up|shorten|rephrase|paraphrase|repeat|count\s+the\s+words\s+in|reverse|capitali[sz]e|uppercase)\s+(?:my|the)\s+"
                  r"next\s+(?:message|text|paragraph|sentence|reply)\b(.*)")


def _one_sentence(text):
    """An extractive one-sentence summary: the main sentence, with a second one joined in, in neutral voice."""
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    if not sents:
        return None
    s = sents[0].rstrip('.!?')
    if len(sents) > 1:
        rest = max(sents[1:], key=len).rstrip('.!?')
        s = f'{s}, and {rest[0].lower() + rest[1:]}'
    s = re.sub(r'^(?:Our|My)\s+', 'The ', s)
    s = re.sub(r'^(?:We|I)\s+', 'They ', s)
    s = re.sub(r'\b(?:forcing|making|causing|leading)\s+(?:us|me)\s+to\s+', lambda m: m[0].split()[0] + ' a need to ', s)
    return s[0].upper() + s[1:] + '.'


NEXT_POINT = re.compile(r"(?i)\b(?:state|give|name|identify|tell\s+me|describe|sum\s+up|pick\s+out|extract|what\s+is)\s+(?:me\s+)?(?:the\s+)?"
                        r"(?:main|key|core|central|biggest|real)?\s*(problem|issue|point|cause|idea|request|question|topic|takeaway|complaint)\s+"
                        r"(?:in|of|from)\s+(?:my|the)\s+next\s+(?:message|text|paragraph|reply)\b(.*)")
LIMITW = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'twelve': 12, 'fifteen': 15, 'twenty': 20}


def _word_limit(rules):
    m = re.search(r'(?i)\b(?:in|under|within|at\s+most|no\s+more\s+than|max(?:imum)?(?:\s+of)?)\s+(\d+|' + '|'.join(LIMITW) + r')\s+words?\b|\b(\d+|'
                  + '|'.join(LIMITW) + r')\s+words?\s+(?:or\s+(?:fewer|less)|max(?:imum)?)\b', rules)
    if not m:
        return None
    w = (m[1] or m[2]).lower()
    return int(w) if w.isdigit() else LIMITW[w]


DROP = {'the', 'a', 'an', 'our', 'my', 'their', 'his', 'her', 'its', 'your', 'this', 'that', 'overnight', 'yesterday', 'today', 'tonight', 'again',
        'suddenly', 'just', 'really', 'very', 'completely', 'totally', 'finally', 'now', 'last', 'night', 'morning', 'week'}
SOFT = {'main', 'new', 'old', 'big', 'small', 'whole', 'entire', 'primary', 'local', 'office', 'shared', 'only'}


def _main_point(text, limit):
    """The main clause of the message, squeezed under a word limit by dropping fillers, then soft modifiers."""
    first = re.split(r'(?<=[.!?])\s+', text.strip())[0]
    clause = re.split(r'(?i),|\s+(?:because|causing|which|so|and\s+then|forcing|leaving|after|when|while|since)\b', first)[0].strip().rstrip('.')
    m = re.match(r'(?i)(?:the\s+|our\s+|my\s+)?(.+?)\s+(?:on|of|in|for)\s+(?:the\s+|our\s+|my\s+)?(.+?)\s+(\w+ed|broke|died|stopped|failed|went\s+down|crashed)\b(.*)$', clause)
    if m:           # "the cooling fan on our main router failed" -> "main router cooling fan failed"
        clause = f'{m[2]} {m[1]} {m[3]}{m[4]}'
    words = [w for w in clause.split() if w.lower() not in DROP]
    if limit:
        for soft in list(SOFT):
            if len(words) <= limit:
                break
            words = [w for w in words if w.lower() != soft]
        words = words[:limit]
    if not words:
        return None
    s = ' '.join(words).rstrip(',;:')
    return s[0].upper() + s[1:] + '.'


def next_message(messages):
    """'Summarize my next message in exactly one sentence' -> wait for it, then do just that (2026-11-23)."""
    users = [m.get('content') or '' for m in messages if m.get('role') == 'user']
    if not users:
        return None
    if NEXT.search(users[-1]) or NEXT_POINT.search(users[-1]):
        return dict(route='chat/followup-next-wait', response='Okay, send it.', sources=[])
    if len(users) < 2:
        return None
    p = NEXT_POINT.search(users[-2])
    if p:
        got = _main_point(users[-1], _word_limit(p[2]))
        return got and dict(route='chat/followup-next-point', response=got, sources=[])
    m = NEXT.search(users[-2])
    if not m:
        return None
    verb, rules = m[1].lower(), m[2]
    text = users[-1].strip()
    if verb.startswith(('summar', 'sum', 'shorten')):
        out_text = _one_sentence(text)
        n = re.search(r'(?i)\b(?:in|under|at\s+most)\s+(\d+)\s+words\b', rules)
        if n and out_text and len(out_text.split()) > int(n[1]):
            out_text = ' '.join(out_text.split()[:int(n[1])]).rstrip(',;') + '.'
    elif verb.startswith('count'):
        n_words = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", text))
        out_text = f'{n_words} words.'
    elif verb.startswith(('repeat',)):
        out_text = text
    elif verb.startswith('reverse'):
        out_text = ' '.join(reversed(text.split()))
    elif verb.startswith(('capital', 'upper')):
        out_text = text.upper()
    else:
        return None         # rephrasing needs more than rules can do well
    if not out_text:
        return None
    return dict(route='chat/followup-next-' + verb.split()[0], response=out_text, sources=[])


def vent(messages):
    """'I just need to vent. Don't ask questions or give advice.' -> a short reply that only listens (2026-11-22)."""
    last = messages[-1].get('content') or ''
    if not VENT.search(last) or len(last) > 220:
        return None
    rest = VENT.sub(' ', last)
    rest = re.sub(r"(?i)\b(?:i|for\s+a\s+minute|please|and|me|any|ok(?:ay)?|just|to)\b|[.,!?;:]", ' ', rest)
    if len(rest.split()) > 6:
        return None         # the request comes with the story itself: the usual reply, filtered below
    return dict(route='chat/followup-vent', response="Okay. I'm listening, go ahead.", sources=[])


def listen_only(messages, got):
    """After a 'no questions, no advice' request, drop questions and advice from the reply."""
    users = [m.get('content') or '' for m in messages if m.get('role') == 'user']
    if not got or not any(VENT.search(u) for u in users[:-1] + [users[-1]] if u) or got.get('route') == 'chat/followup-vent':
        return got
    text = str(got.get('response', ''))
    if 'advice' in str(got.get('route', '')) or re.search(r'(?m)^\s*(?:\d+\.|[-*•])\s+', text):
        feel = users[-1].lower()
        line = ('That would make anyone angry.' if re.search(r'\b(?:angry|furious|mad|livid|annoyed|fuming)\b', feel) else
                'That sounds exhausting.' if re.search(r'\b(?:exhausted|tired|drained|worn\s+out|wiped)\b', feel) else
                "That's really hard." if re.search(r'\b(?:sad|upset|hurt|down|lonely|crying)\b', feel) else
                'That sounds really stressful.' if re.search(r'\b(?:stressed|anxious|overwhelmed|worried|panic)\b', feel) else
                'That sounds really frustrating.')
        return dict(got, response=f"{line} I'm here, keep going if you want.", route=str(got.get('route', '')) + '+listen-only')
    keep = [s for s in re.split(r'(?<=[.!?])\s+', text) if s.strip() and not s.strip().endswith('?') and
            not re.match(r"(?i)\s*(?:try|you\s+(?:should|could|might|may\s+want)|consider|maybe\s+you|make\s+sure|it\s+might\s+help|have\s+you|"
                         r"here\s+are|one\s+(?:thing|idea)|a\s+good\s+idea|tip|-|\d+\.)", s)]
    new = ' '.join(keep).strip() or "That sounds really hard. I'm here."
    if new == text:
        return got
    return dict(got, response=new, route=got.get('route', '') + '+listen-only')


def _handle(messages, run):
    last = messages[-1]['content']
    stripped = LEAD.sub('', last, count=1)
    if stripped != last and len(stripped) > 3:
        messages = messages[:-1] + [dict(messages[-1], content=stripped[0].upper() + stripped[1:])]
        last = messages[-1]['content']
    view, change, last_is_correction = corrected_view(messages)
    if last_is_correction and change:
        j, before_t, after_t, new_v, old = change
        if before_t.strip().endswith('?') or '?' in before_t:
            got = run(view[:j] + [dict(role='user', content=after_t)])
            if not weak(got):
                return dict(got, response='With that correction: ' + str(got.get('response', '')), route='chat/followup-correction',
                            replaced_route=got.get('route'), asked_as=after_t)
        else:
            # a later question in the corrected conversation may need answering again: the user's own last question
            later_q = [k for k in range(j + 1, len(view)) if view[k].get('role') == 'user' and '?' in view[k]['content']]
            if later_q:
                k = later_q[-1]
                got = run(view[:k + 1])
                if not weak(got):
                    return dict(got, response='With that correction: ' + str(got.get('response', '')), route='chat/followup-correction',
                                replaced_route=got.get('route'))
            was = f', not {old}' if old else ''
            return dict(route='chat/followup-correction', sources=[], response=f'Got it: **{new_v.strip()}**{was}. I\'ve updated that.')
    users = users_of(view)
    prev_reply = view[-2]['content'] if len(view) >= 2 and view[-2].get('role') == 'assistant' else ''
    if THANKS.match(last) and len(last) < 90:
        return thanks_reply(view)
    got = guilt_reply(view)
    if got:
        return got
    if prev_reply and WORKING_Q.match(last):
        w = working(prev_reply)
        if w:
            head, pre, rest = w
            return dict(route='chat/followup-working', sources=[], response=f'Here is how I got **{head.rstrip(".")}**: {rest}')
    if prev_reply and SURE_Q.match(last):
        qa = last_qa(view)
        head = bold(prev_reply) or (prev_reply.strip() if len(prev_reply.strip()) < 40 and '\n' not in prev_reply.strip() else None)
        if qa and head:
            i, q, _ = qa
            again = run(view[:i + 1])
            r2 = str(again.get('response', '')).strip()
            h2 = bold(r2) or (r2 if len(r2) < 40 and '\n' not in r2 else None)
            check = arithmetic_check(q, head)
            if h2 and h2 == head:
                return dict(route='chat/followup-sure', sources=[], response=f'Yes. I worked it out again from your numbers and got the same: **{head}**.' + (f' {check}' if check else ''))
            if h2 and not weak(again):
                return dict(again, route='chat/followup-sure', response='Working it out again, I get a different answer, so here is the corrected one: ' + str(again.get('response', '')))
    if prev_reply and SHORT_Q.match(last):
        simple = bool(re.search(r'(?i)simpl|five|5|eli5', last))
        s = shorten(prev_reply, simple)
        if s:
            return dict(route='chat/followup-shorter', sources=[], response=s)
    got = recall(view)
    if got:
        return got
    for fn in (whatif, tips):
        got = fn(messages, view, run)
        if got:
            return got
    reply = run(view)
    if weak(reply):
        got = pronoun(messages, view, run)      # "When was he born?" after "... by William Shakespeare": only when the plain reading fails
        if got:
            return got
    if '?' not in last:
        ack = acknowledge(view, reply)
        if ack:
            return dict(ack, replaced_route=reply.get('route'))
    return reply


def arithmetic_check(q, head):
    m = re.search(r'(-?\d+(?:\.\d+)?)\s*(?:[×x*]|times)\s*(-?\d+(?:\.\d+)?)', q)
    if m and re.fullmatch(r'-?\d+(?:\.\d+)?', head.replace(',', '')):
        a, b, c = float(m[1]), float(m[2]), float(head.replace(',', ''))
        if b and abs(c / b - a) < 1e-9:
            return f'Check: {head} ÷ {m[2]} = {m[1]}.'
    return None
