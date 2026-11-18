"""The Listener: a reply to something hard the user has just said, and to plain things they tell CAEL.

"Everyone else I know passed first time. I feel like giving up."
"They gave it to someone who joined eight months ago. I don't even know if I want to stay now."
"We've seen each other every week for ten years. I don't know what I'll do without her."

A reply to these has three parts: it takes the feeling seriously, it says the one thing that is true of that kind of
moment (being compared with others, being passed over, someone leaving, wanting to give up), and it asks an open
question. Nothing of the user's wording is pasted into the reply, so it cannot come back garbled. No advice is given
unless asked for.

`companion` is the plain reply to something told that no other agent took ("I just got back from my first ever yoga
class."). Authored text and patterns; no model.
"""
import re

LOW = re.compile(r"(?i)\b(?:feel(?:s|ing)? like giving up|want(?:ed)? to give up|i give up|ready to give up|don'?t know what i(?:'ll| will) do|don'?t know what to do|"
                 r"don'?t (?:even )?know if i (?:want|can|should)|can'?t cope|can'?t do this|can'?t face|heartbroken|devastated|gutted|"
                 r"i feel (?:like (?:a failure|an idiot|a fraud|such a failure)|useless|stupid|awful|terrible|lost|so alone|alone|hopeless|worthless|empty|numb)|"
                 r"hate myself|what'?s the point|i (?:just |really |honestly )?feel (?:so )?(?:overwhelmed|scared|terrified|anxious|panicked)|"
                 r"i (?:really )?miss (?:him|her|them)|been crying|can'?t stop crying|i feel like (?:crying|quitting)|it'?s not fair|so unfair|"
                 r"i'?m not good enough|never be good enough|i(?:'ll| will) never|(?:i'?ve|i have|i) (?:really )?let (?:him|her|them|you|everyone|my \w+) down|"
                 r"i feel like i(?:'ve| have)? (?:failed|let))\b")
NERVES = re.compile(r"(?i)\b(?:i'?m|i am|i feel|feeling|i get|get)\s+(?:really |so |very |quite |a bit |a little )?(?:dreading|nervous|anxious|scared|terrified|"
                    r"petrified|worried)\b|\bi'?m dreading\b|\bdreading (?:it|the|my|this|that|giving|doing|going)\b|\bwhen i'?m (?:nervous|anxious|scared)\b|"
                    r"\bi'?m scared (?:that )?(?:everyone|people|they|i'll|i will)\b")
LET_DOWN = re.compile(r"(?i)\blet (?:him|her|them|you|everyone|my \w+) down\b")
COMPARE = re.compile(r"(?i)\b(?:everyone else|everybody else|all my (?:friends|classmates|colleagues)|other people|all the others|my (?:friends|siblings) all)\b")
PASSED_OVER = re.compile(r"(?i)\b(?:gave it to|they (?:chose|picked|hired|promoted)|went to someone|someone (?:who|that) (?:joined|started|has)|less experience|"
                         r"after (?:all )?(?:the|my|those) (?:work|years|effort))\b")
LEAVING = re.compile(r"(?i)\bwithout (?:her|him|them)\b|\b(?:moving|moved|going|leaving) (?:away|abroad|overseas|out|to (?-i:[A-Z]))|\bwon'?t (?:get to )?see\b|\bmiss (?:her|him|them)\b")
GIVE_UP = re.compile(r"(?i)\b(?:giving up|give up|quit(?:ting)?|pack it in|throw in the towel)\b")
STAY = re.compile(r"(?i)\b(?:if i (?:even )?want to stay|whether (?:i want )?to stay|want to stay|thinking (?:of|about) (?:leaving|quitting|resigning)|hand in my notice)\b")
FAIL = re.compile(r"(?i)\b(?:failed|(?:didn'?t|did not) (?:pass|get|make)|rejected|turned down|lost|(?:wasn'?t|was not) (?:accepted|chosen|selected|picked))\b")
NEWS_LEAVING = re.compile(r"(?i)\bmy (best friend|friend|sister|brother|mum|mom|dad|mother|father|partner|girlfriend|boyfriend|daughter|son|flatmate|"
                          r"housemate|closest friend|oldest friend|neighbou?r|colleague|manager)\b[^.?!]{0,20}\b(?:is|are|'s) (?:moving|leaving|going|emigrating|relocating)\b")
PENDING = re.compile(r"(?i)\b(?:don'?t|do not) know (?:the result|yet|if i (?:got|passed|made)|whether)|waiting to (?:hear|find out)|haven'?t heard (?:back|anything)|"
                     r"find out (?:next week|tomorrow|on \w+day|soon)|results? (?:come|are) out")
GOOD = re.compile(r"(?i)\b(?:i got (?:the|it|in|a)|got the job|passed|i won|accepted|offered me|got an offer|got in)\b")
COMPLAINT = re.compile(r"(?i)(?:\b(?:keeps?|never|always|won'?t stop|constantly|every (?:day|night|morning|time)|hasn'?t (?:mentioned|paid|said|returned|given)|"
                       r"still hasn'?t|borrowed|owes? me)\b)[^.?!]*[.!]\s*(?:but )?i (?:really )?don'?t want to "
                       r"(?:start|cause|fall out|upset|make|have|be|ruin|lose|create|seem|sound|offend)\b")


def out(text, kind):
    return dict(route='chat/talk-feelings', response=text, sources=[], details=f'A reply to what the user shared ({kind}; empath.py).')


def respond(messages):
    """A reply to a low or loaded statement; None for anything else (questions included, unless they are a cry, not a query)."""
    users = [m['content'] for m in messages if m.get('role') == 'user']
    if not users:
        return None
    last = users[-1].strip()
    asked = [s for s in re.split(r'(?<=[.!?])\s+', last) if s.strip().endswith('?')]
    if asked and not re.search(r"(?i)\bwhat'?s the point\b|\bwhy (?:do i|does (?:this|it)) (?:even |always )?(?:bother|happen)", last):
        return None
    if len(last.split()) > 70:
        return None
    if any(re.search(r"(?i)\b(?:no advice|not? (?:give|giving) (?:me )?advice|don'?t advise|just (?:listen|want to vent)|no (?:questions|suggestions|solutions)|"
                     r"don'?t ask|not looking for (?:advice|solutions)|don'?t try to fix)\b", t) for t in users[-4:]):
        return None                 # the user has said how they want to be answered: the conversation rules keep that (chat_skills)
    if re.search(r"(?i)\b(?:congratulat|good news|happy for)", last) and re.search(r"(?i)\b(?:scared|terrified|overwhelmed|anxious|worried|not ready|freaking out|panick)", last):
        return out("That's completely understandable. Big news can bring fear as well as joy, and it's okay if it doesn't feel like pure excitement "
                   "right now, whatever everyone else says. You don't have to have it all worked out today. What feels most overwhelming at the moment?",
                   'news that frightens')
    if NERVES.search(last) and re.search(r"(?i)\bresults?\b[^.?!]*\b(?:out|come|coming|due)\b|\bwaiting (?:for|to hear)\b|\b(?:scared|worried|afraid) (?:that )?i (?:failed|didn'?t)\b", last):
        return None                 # waiting for a result, not nerves before an event: the Supporter's "waiting" situation
    if NERVES.search(last):
        recent = ' '.join(users[-3:]).lower()
        event = re.search(r"\b(presentation|speech|talk|interview|exam|test|audition|performance|recital|meeting|toast|first day|driving test|date)\b", recent)
        what = event[1] if event else 'it'
        body = re.search(r"(?i)\b(?:voice|hands?|legs?|knees?) (?:shakes?|shaking|trembles?|wobbles?)|\bshak(?:e|ing|y)\b|\bblush|\bsweat|\bgo(?:es)? blank|"
                         r"\bmind (?:goes|went) blank|\bforget (?:my|what)|\bheart (?:races|pounds)|\bfeel sick\b", last)
        if body:
            return out("That's really common, and it's much less visible from the audience than it feels from the inside: people rarely notice a "
                       "shaky voice unless you point it out. A few things that help: breathe out slowly before you start (a long out-breath calms "
                       "the shake), speak a little slower than feels natural, rest your hands on the lectern or hold your notes with both hands, "
                       "have water nearby, and learn your first two sentences by heart so the start is automatic. Practising it out loud two or "
                       "three times, ideally in front of one person, takes the edge off more than anything else. Would it help to plan your opening?",
                       'nerves with a symptom')
        art = 'an' if what[:1] in 'aeiou' else 'a'
        thing = f'{art} {what}' if what != 'it' else 'it'
        return out(f"Dreading {thing} is completely normal, and it usually feels worse in the days before than on the day itself. Nerves are "
                   f"mostly energy your body is getting ready with, and some of it will actually help you. What worries you most about it: "
                   f"the content, being looked at, or something going wrong?" if what != 'it' else
                   "That kind of nervousness is completely normal, and it usually feels worse beforehand than in the moment. What worries you most about it?",
                   'nerves')
    if LOW.search(last):
        middle = []
        let = LET_DOWN.search(last)
        if COMPARE.search(last) and let:
            middle.append("And other people's results only feel like a verdict on you; they aren't one.")
        elif COMPARE.search(last):
            middle.append("Measuring yourself against people for whom it went smoothly makes it sting more, but how long something takes says very little "
                          "about how well you'll do it in the end.")
        if PASSED_OVER.search(last) or (STAY.search(last) and not middle):
            middle.append("Being passed over after putting in that much would make anyone question things, and it's fair to feel let down.")
        if LEAVING.search(last):
            middle.append("When someone has been part of your life for that long, their going is a real loss, even if you stay close.")
        if GIVE_UP.search(last):
            middle.append("Wanting to give up right after a knock is very human; it's usually the disappointment talking, not a verdict on you.")
        if STAY.search(last):
            middle.append("You don't have to decide anything today. That kind of decision is better made once the sting has eased a little.")
        if let:
            who = re.search(r"(?i)\blet (him|her|them|you|everyone|my \w+) down", last)[1].lower()
            obj = {'him': 'him', 'her': 'her', 'you': 'them', 'everyone': 'anyone'}.get(who, 'them')
            subj = {'him': "he'll", 'her': "she'll"}.get(who, "they'll")
            middle.insert(0, f"But this isn't something you did to {obj}: outcomes like this come down to rules, numbers and luck, not to how much you care, "
                             f"and the care you're showing now is what {subj} actually remember.")
        if not middle:
            middle.append("It makes sense that you feel this way, and you don't have to have it figured out right now.")
        opener = "I'm sorry, that's a lot to carry." if (PASSED_OVER.search(last) or LEAVING.search(last)) else "That sounds really hard, and I'm sorry you're going through it."
        close = ("Do you want to talk about what happened, or think through what you might do next?" if (GIVE_UP.search(last) or STAY.search(last) or FAIL.search(last))
                 else "What's weighing on you most right now?")
        return out(f"{opener} {' '.join(middle[:2])} {close}", 'low mood')
    if GOOD.search(last) and not FAIL.search(last) and not asked and re.search(r"(?i)\b(?:job|offer|exam|test|interview|place|university|uni|college|promotion)\b", last):
        return out("Congratulations, that's brilliant news! All that preparation paid off. How are you feeling, and when do you start?"
                   if re.search(r"(?i)\b(?:job|offer|promotion|place)\b", last) else "Congratulations, that's brilliant news! How are you going to celebrate?",
                   'good news')
    if PENDING.search(last) and re.search(r"(?i)\b(?:biopsy|scan|mri|x-?ray|mammogram|smear|blood (?:test|work)|lump|cancer|consultant|hospital|clinic|gp)\b", last):
        return None                 # medical results: the Supporter's "health_wait" situation, never "especially when it went well"
    if PENDING.search(last):
        return out("Fingers crossed for you. Waiting to hear is often the hardest part, especially when it went well. Do you know when they'll "
                   "let you know?", 'waiting for a result')
    if FAIL.search(last) and not GOOD.search(last) and not re.search(r"(?i)\b(?:if|whether|what if|might|may|could)\b", last):
        long = re.search(r"(?i)\bfor ((?:\d+|two|three|four|five|six|several|many|a few|a couple of) (?:years|months|weeks))\b|\b(second|third|fourth) time\b", last)
        extra = (f", especially after {long[1]} of working towards it" if long and long[1] else ", and all the more for it not being the first time" if long else '')
        kind = "That must sting, particularly when you felt it had gone well" if re.search(r"(?i)\bwent (?:well|great|fine)\b", last) else \
            "I'm sorry, that's a real disappointment"
        return out(f"{kind}{extra}. It's fair to feel flat about it. Do you want to talk about what happened, or think about what to do next?", 'a setback')
    m = NEWS_LEAVING.search(last)
    if m and re.search(r"(?i)\band (?:i|me)\b|\bwe(?:'re| are)\b", m.group(0) + last[m.end():m.end() + 12]):
        m = None            # "My partner and I are moving": the user is moving too
    if m and not re.search(r"(?i)\b(?:excited|happy|thrilled|can'?t wait|great news|good news)\b", last):
        who = m[1].lower()
        return out(f"Oh, that's big news. I'd guess it brings mixed feelings: glad for your {who}, and sad to see them go. How are you feeling about it?", 'someone leaving')
    got = strong(messages)
    if got:
        return got
    if COMPLAINT.search(last):
        return out("That sounds frustrating, and it makes sense that you want to sort it out without making things worse between you. "
                   "Would it help to work out how to raise it, so it comes across as a request rather than a complaint?", 'a complaint with a worry')
    return None


LOSS = re.compile(r"(?i)\b(?:died|passed away|put (?:him|her|them) (?:down|to sleep)|lost (?:my|our) (?:dog|cat|mum|mom|dad|mother|father|grandma|grandad|grandmother|"
                  r"grandfather|husband|wife|partner|friend|brother|sister|pet|baby)|funeral|bereave)")
GRIEF_NOW = re.compile(r"(?i)\b(?:feels? (?:so )?empty|keep (?:expecting|looking|thinking)|miss (?:him|her|them)|can'?t stop (?:crying|thinking)|so quiet|"
                       r"don'?t know what to do with myself|everything reminds me|still (?:can'?t|cannot) believe)")
FOLLOW_UP = {
    'moving': "Exciting, and a lot of work too. How are you feeling about it, and would it help to plan what to sort out first?",
    'travel': "How exciting! Have you planned what you'd like to do there yet?",
    'cycling': "That's a great way to build exercise into your day. Have you got a bike sorted, or are you still looking?",
    'bread': "Bread's a lovely thing to learn, and simpler than it looks. Would you like a recipe for an easy first loaf?",
    'houseplant': "Lovely! Plants are good company. Would you like a few tips on keeping it happy?",
    'dog': "How lovely! How is {name} settling in so far?",
    'cat': "How lovely! How is {name} settling in so far?",
    'swimming': "Good for you, it takes courage to start as an adult. How are the first sessions going?",
    'dance': "Fun! How did you find it?",
    'instrument': "Lovely! What made you choose it, and how is it going so far?",
    'language': "Great! What's your reason for learning it, and how is it going so far?",
    'money': "Good plan. Would you like a few ideas to make it easier?",
    'sugar': "Good plan. Would you like a few ideas to make it easier without missing it too much?",
    'compost': "Great idea, and very doable in a small space. Would you like to know what you'd need?",
    'school': "That's a big step for them. How are they feeling about it?",
}


NOT_NAMES = {'I', 'My', 'The', 'And', 'Hi', 'Hello', 'Hey', 'We', 'He', 'She', 'They', 'Is', 'It'}


def strong(messages):
    """A reply to news, plans, a loss or a first step: shapes where a generic acknowledgement loses the moment."""
    users = [m['content'] for m in messages if m.get('role') == 'user']
    last = users[-1].strip()
    if '?' in last or len(last.split()) > 45:
        return None
    if re.search(r"(?i)\b(?:at|on) (?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?|noon|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", last):
        return None                 # appointments and schedules belong to the diary and the memory
    recent = ' '.join(users[-3:])
    if LOSS.search(recent) and (LOSS.search(last) or GRIEF_NOW.search(last)):
        if LOSS.search(last) and not GRIEF_NOW.search(last):
            years = re.search(r"(?i)\b(?:for|had (?:him|her|them) for) ((?:\d+|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
                              r"seventeen|eighteen|nineteen|twenty) years)\b", last)
            span = f"After {years[1]} together, losing" if years else "Losing"
            return out(f"I'm so sorry. {span} someone who has been part of every day is a real loss, and it's natural to feel it everywhere. "
                       f"Would you like to tell me about them?", 'a loss')
        return out("That emptiness is one of the hardest parts: the routines and sounds you were used to are suddenly missing, and it can catch you "
                   "off guard for a while. It does soften with time. Some people find it helps to put away a few things for now, or to do something "
                   "to remember them. What do you miss most?", 'grief')
    if re.search(r"(?i)\b(?:we'?re|we are|i'?m|i am) (?:having|expecting) (?:a baby|twins|triplets|a boy|a girl)\b|\b(?:i'?m|i am|she'?s) pregnant\b|\bgot engaged\b", last):
        return out("Oh, that's huge news! How are you feeling about it?", 'big news')
    problem = re.search(r"(?i)\b(?:has become|is|got|keeps?|has been|have been|are|went|is getting) (?:really |very |so |quite |bright |super )?(?:slow|broken|red|sore|"
                        r"swollen|stuck|leaking|blocked|cracked|dead|flat|noisy|smelly|sick|ill|itchy)\b|\bstopped working\b|\bwon'?t (?:start|turn on|work)\b", last)
    if problem and not FAIL.search(last):
        return out("Oh no, that's annoying. Let's see if we can sort it out: do you want some suggestions on what to try first?"
                   if not re.search(r"(?i)\b(?:red|sore|swollen|sick|ill|itchy)\b", last) else
                   "Ouch, that sounds sore. Do you want a few tips to make it more comfortable?", 'a problem told')
    family = re.search(r"(?i)\bi (?:have|'ve got) (?:two|three|four|\d+|a|an) (?:children|kids|sons?|daughters?|grandchildren|brothers?|sisters?)\b", last)
    if family:
        names = list(dict.fromkeys(n for n in re.findall(r"\b([A-Z][a-z]+)\b", last) if n not in NOT_NAMES))
        who = ' and '.join(names[:3]) if names else 'them'
        return out(f"Lovely, thanks for telling me about {who}. What's on your mind with them at the moment?", 'family')
    news = re.search(r"(?i)\b(?:i'm|i am|we're|we are|i've|i have|we've|we have|i just|we just|i'll be|we'll be|i've decided|i decided|we decided|and i are|and me are|"
                     r"i'd like to|i would like to|i want to|we want to)\b.{0,30}?"
                     r"\b(?:moving|going to|starting|started|adopted|bought|got (?:a|my|our)|decided|learning|learn|planning|trying|taking up|signed up|start|bake|try)\b", last)
    if not news:
        return None
    from . import advice_library
    found = advice_library.topics_in([last])
    hello = re.match(r"(?i)\s*(good morning|morning|good evening|evening|hi|hello|hey|hiya)\b[!,. ]*", last)
    greet = ''
    if hello:
        w = hello[1].lower()
        greet = ('Good ' + w + '! ') if w in ('morning', 'evening') else w.capitalize() + '! '
    name = re.findall(r"\b(?:called|named|name is|name's)\s+([A-Z][a-z]+)\b", last)
    for t in found:
        if t.key in FOLLOW_UP:
            text = FOLLOW_UP[t.key].replace('{name}', name[-1] if name else ('your new dog' if t.key == 'dog' else 'your new cat'))
            return out(greet + text, 'news: ' + t.key)
    return None


def companion(messages):
    """A plain, warm reply to something told that nobody else took."""
    users = [m['content'] for m in messages if m.get('role') == 'user']
    last = users[-1].strip()
    hello = re.match(r"(?i)\s*(good morning|morning|good evening|evening|good afternoon|afternoon|hi|hello|hey|hiya)\b[!,. ]*", last)
    greet = ''
    if hello:
        word = hello[1].lower()
        greet = ('Good ' + word + '! ') if word in ('morning', 'evening', 'afternoon') else word.capitalize() + '! '
    if FAIL.search(last) and not re.search(r"(?i)\b(?:weight|keys|way|track)\b", last):
        long = re.search(r"(?i)\bfor ((?:\d+|two|three|four|five|six|several|many|a few|a couple of) (?:years|months|weeks))\b|\b(second|third|fourth) time\b", last)
        extra = (f", especially after {long[1]} of working towards it" if long and long[1] else ", and all the more for it not being the first time" if long else '')
        return out(f"{greet}I'm sorry, that's a real disappointment{extra}. It's fair to feel flat about it. "
                   f"Do you want to talk about what happened, or think about what to do next?", 'a setback')
    first = re.search(r"(?i)\bmy (?:very )?first (?:ever )?([a-z0-9]+(?: [a-z]+)?)\b", last)
    if first:
        thing = first[1].lower()
        return out(f"{greet}Your first {thing}, well done for doing it. How did it go?", 'a first')
    goal = re.search(r"(?i)\bi(?:'d| would)? (?:want|like|love|plan|am hoping|'m hoping|hope|'m trying|am trying|'ve decided|have decided) to (?:start |begin |try |learn |take up )?([a-z]+(?:ing)?)\b", last)
    if goal and re.search(r"(?i)\bbut\b", last):
        return out(f"{greet}That's a good thing to want, and the snag you mention is a common one, so it needn't stop you. "
                   f"What would help most first: how to get started, or how to keep it going?", 'a goal with an obstacle')
    if goal:
        return out(f"{greet}That sounds like a good plan. What would you like help with first?", 'a goal')
    if greet:
        return out(f"{greet}Thanks for telling me. How did it go?" if re.search(r"(?i)\b(?:just|today|this morning|yesterday|last night)\b", last)
                   else f"{greet}How are you doing today?", 'a greeting')
    try:
        from . import advice_library
        if advice_library.topics_in([last]):
            return out(f"{greet}Sounds like there's a bit to think about there. Would you like a few practical tips for it?", 'something to plan')
    except Exception:
        pass
    return out(f"{greet}Thanks for telling me. How are you feeling about it?", 'something told')
