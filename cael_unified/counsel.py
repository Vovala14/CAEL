"""The Counsellor: general guidance for the common shapes of an everyday question, when nothing better was found.

"Is that normal for a beginner?", "Should I be worried?", "Is that realistic?", "How can I help him?", "Any tricks
for the first night?", "Will it smell?": each of these has a sensible general answer that does not depend on a source.
The Counsellor recognises the shape, fills in what the conversation is about, and says plainly that this is general
guidance. It never states a fact about the specific subject (no numbers, no named products), so it cannot be wrong
about one; it is used only after the exact solvers and the web researchers had nothing (team.py).

Authored text and patterns only; no model.
"""
import re

from . import web_check as wc

PET = re.compile(r"(?i)\b(?:dog|puppy|cat|kitten|rabbit|hamster|greyhound|parrot|pet|pony|horse|guinea pig|budgie|fish)\b")
CHILD = re.compile(r"(?i)\b(?:kid|kids|child|children|son|daughter|toddler|baby|teen|teenager|\d+[- ]year[- ]old)\b")
BODY = re.compile(r"(?i)\b(?:hurt|hurts|pain|sore|ache|aches|dizzy|tired|sleep|headache|knee|back|wrist|fingertips?|fingers?|stomach|rash|cough)\b")
THING = re.compile(r"(?i)\b(?:car|engine|laptop|phone|boiler|washing machine|bike|fridge|router|printer|tap|heating)\b")
LEARN = re.compile(r"(?i)\b(?:learning|learn|beginner|first (?:ever )?(?:class|lesson|time|week)|just started|new to|started|practi[sc]e|practi[sc]ing|lessons?|course)\b")


def expert(text):
    if PET.search(text):
        return 'a vet'
    if CHILD.search(text):
        return 'your GP or health visitor'
    if BODY.search(text):
        return 'a doctor or pharmacist'
    if THING.search(text):
        return 'a qualified repairer'
    return 'someone qualified'


def who(text, names):
    """How to refer to the one the question is about: a name told earlier, or 'them'."""
    m = re.search(r'(?i)\b(him|her|them|he|she|they)\b', text)
    if names:
        return names[-1]
    if m:
        return {'he': 'him', 'she': 'her', 'they': 'them'}.get(m[1].lower(), m[1].lower())
    return 'them'


def activity(turns):
    """What the user is learning or doing ("yoga", "the ukulele"), from the turns before."""
    for t in reversed(turns):
        m = re.search(r"(?i)\b(?:learning|practi[sc]ing|studying|taking up|started|starting|doing|trying)(?: to (?:play|speak|do|learn))?"
                      r"(?: the| a| an| my)? ([a-z]+(?: [a-z]+)?)\b", t)
        if m and m[1].split()[0].lower() not in wc.STOP:
            words = m[1].split()
            keep = words[:1] if len(words) > 1 and (words[-1].lower() in wc.STOP or not words[-1][:1].islower() or words[-1].lower() in ('i', 'every', 'for')) else words
            return ' '.join(w if w[:1].isupper() else w.lower() for w in keep)
        m = re.search(r"(?i)\bmy first (?:ever )?([a-z]+) (?:class|lesson|session)\b", t)
        if m:
            return m[1].lower()
    return None


def reply(messages):
    """A dict reply, or None when the last question has none of the known shapes."""
    turns = wc.user_turns(messages)
    if not turns:
        return None
    last = turns[-1].strip()
    q = [s for s in re.split(r'(?<=[.!?])\s+', last) if s.strip().endswith('?')]
    q = q[-1] if q else last
    low = q.lower()
    recent = ' '.join(turns[-4:])
    names = [n for t in turns[-6:] for n in re.findall(r"\b(?:called|named|name is|name's) ([A-Z][a-z]+)\b", t)]
    if not names:
        names = [w for w in re.findall(r"\b([A-Z][a-z]{2,})\b(?= is (?:scared|afraid|nervous|worried|shy|upset|anxious))", last)]
    doing = activity(turns)
    pro = expert(recent)
    text = None
    if re.search(r"\bis (?:that|this|it) (?:normal|common|usual)\b|\bnormal for\b|\bdoes (?:that|this|it) (?:happen|go away|get (?:better|easier))\b|"
                 r"\bwill (?:that|this|it) (?:go away|get (?:better|easier)|pass|stop)\b", low):
        if LEARN.search(recent):
            what = f' with {doing}' if doing else ''
            physical = re.search(r"(?i)\b(?:yoga|gym|run|running|stretch|pilates|swim|climb|dance|football|tennis|cycling|workout|exercise|guitar|ukulele|"
                                 r"violin|piano|fingers?|fingertips?|muscles?|sore|ache|hurt|toes|knees?|back)\b", recent)
            tail = ("The one thing to respect is sharp pain: discomfort from effort is fine, pain is a signal to ease off and ask your teacher."
                    if physical else "If the same thing is still not sticking after a few weeks, change the method rather than just pushing harder.")
            text = (f"Yes, that's completely normal when you're starting out{what}. Almost everyone finds the first weeks awkward, and the people "
                    f"who look effortless have usually been at it for years. It gets easier with regular practice, in small steps rather than all "
                    f"at once, so compare yourself with where you were last week, not with them. {tail}")
        else:
            text = (f"It's common, yes, and on its own it's usually nothing to worry about. What matters more is whether it's changing: if it gets "
                    f"worse, lasts longer than you'd expect, or comes with other signs, it's worth checking with {pro}.")
    elif re.search(r"\bis (?:that|this|it) (?:any good|good|ok|okay|alright|all right|decent|bad|slow|fast|normal|respectable|average)\b", low) and re.search(
            r"(?i)\b(?:my first|first (?:one|time|go|attempt|try)|beginner|just started|new to)\b", recent):
        text = ("For a first go, yes, that's a perfectly respectable result. Finishing at all is the milestone; most people's early results improve "
                "quickly over the first few months of regular practice. Treat this one as your baseline to beat, rather than something to judge "
                "yourself by.")
    elif re.search(r"\bshould i (?:be )?(?:worried|concerned)\b|\bis (?:that|this|it) (?:bad|a problem|dangerous|unhealthy|something to worry)\b", low) or (
            re.search(r"\bis (?:that|this|it) (?:ok|okay|safe|too much|too little|healthy)\b", low) and (PET.search(recent) or CHILD.search(recent) or BODY.search(recent))):
        subject = who(q, names)
        whom = 'you' if re.search(r'\b(?:i|my|me)\b', low) and subject == 'them' and not PET.search(recent) else subject
        text = (f"On its own, probably not. What's worth watching is change rather than the number itself: if it's new for {whom}, or it comes "
                f"with other signs (eating less, low energy, pain, a change in mood), have it checked by {pro}. If {whom if whom != 'you' else 'you'} "
                f"otherwise seem{'s' if whom not in ('you', 'them') else ''} well and it has always been this way, it's most likely just "
                f"{'your' if whom == 'you' else 'their' if whom == 'them' else whom + chr(39) + 's'} normal.")
    elif re.search(r"\bis (?:that|this|it) (?:realistic|possible|doable|achievable|feasible|too late|too soon|too ambitious)\b|"
                   r"\b(?:can|could) i (?:really |actually |still )?(?:do|manage|make|learn|pull) (?:it|that|this)\b|\bam i (?:too old|too late)\b", low):
        month = re.search(r"(?i)\b(?:in|by|next|this) (january|february|march|april|may|june|july|august|september|october|november|december|"
                          r"spring|summer|autumn|winter|week|month|year)\b", recent)
        when = f" by {month[1].capitalize() if len(month[1]) > 5 or month[1].lower() in ('may', 'june', 'july', 'march', 'april') else month[1]}" if month else ''
        text = (f"Yes, it's realistic{when} if you keep the goal small and specific. Pick one simple piece of it and aim to do that well, rather "
                f"than everything adequately. Work backwards from the date: something easy you can already nearly do, practised a little every "
                f"day, beats a hard thing crammed at the end. Do a couple of trial runs in front of a friend before the day, so the real "
                f"thing isn't the first time. If it's tight a few weeks out, simplify the piece, not the plan.")
    elif re.search(r"\b(?:(?:tips|advice|tricks|ideas) (?:for|on|to) (?:not (?:getting|being|feeling)|being less|feeling less|dealing with|calming|stop(?:ping)? being) "
                   r"(?:so |too )?(?:nervous|nerves|anxious|scared|stressed|stage fright)|how (?:can|do|could|should) i (?:not get|stop (?:being|getting|feeling)|"
                   r"avoid (?:being|getting)|deal with (?:being|getting|my)|calm my) (?:so |too )?(?:nervous|nerves|anxious|scared|stressed))\b", low):
        text = ("Nerves mostly shrink with preparation and practice in front of people:\n\n"
                "- Know your opening cold. The first thirty seconds are the hardest, and a solid start carries you.\n"
                "- Rehearse in front of one person, then a few, before the real thing.\n"
                "- Slow down, and breathe out for longer than you breathe in just before you begin.\n"
                "- Expect a mistake and plan to keep going; almost nobody notices the ones you don't react to.\n"
                "- Remember that the people watching want it to go well.")
    elif re.search(r"\bwill it be (?:very |really |too )?(?:cold|warm|hot|wet|rainy|chilly|freezing|mild)\b|\bhow (?:cold|warm|hot) (?:will|does|is) it (?:be|get|going to be)\b", low):
        outdoors = re.search(r"(?i)\b(?:camp|camping|hik|trek|tent|outdoors|festival|beach)", recent)
        text = ("That depends on where you'll be, and I can't see a forecast from here, so check one for the place a few days before you go. "
                + ("As a rule for nights outdoors, plan for it to be colder than the daytime suggests: temperatures drop quickly after dark, even "
                   "after a mild day. A warm layer and a hat each, proper sleeping bags and something insulating to lie on cover most of it."
                   if outdoors else "As a rule, pack one more layer than you expect to need and something waterproof; it's easier to take a layer "
                                    "off than to wish you had one."))
    elif re.search(r"\b(?:scared|afraid|frightened|terrified|nervous|anxious)\b", recent[-400:].lower()) and (
            names or re.search(r"(?i)\b(?:him|her|them|he|she|my (?:son|daughter|dog|cat|kid|child|friend|partner|mum|dad|brother|sister))\b", last)) and re.search(
            r"\bhow (?:can|do|could|should) i (?:help|calm|reassure|get|make)\b|\b(?:any|some|got any) (?:tricks|tips|ideas|advice|suggestions)\b|"
            r"\bwhat (?:can|should|could) (?:i|we) do\b", low):
        subject = who(last, names)
        fear = re.search(r"(?i)\b(?:scared|afraid|frightened|terrified|nervous|anxious) (?:of|about|around|on|with) ((?:the |a |an )?[a-z]+(?: [a-z]+)?)", recent)
        what = f' {fear[1].lower()}' if fear else ''
        about = f" with{what}" if what else ''
        text = (f"A few things that usually help{about}:\n\n"
                f"- Go at {subject if subject in ('him', 'her', 'them') else subject + chr(39) + 's'} pace. Break it into very small steps and "
                f"let {'him' if subject == 'him' else 'her' if subject == 'her' else 'them'} get used to each one before the next.\n"
                f"- Make it familiar while things are calm and there's no pressure, and stay close at first.\n"
                f"- Give a bit of control: something of their own to hold or to switch on, and a clear way to stop.\n"
                f"- Notice and praise each brave moment, and never force it, since being pushed makes the fear stick.\n"
                f"- Keep sessions short and end on a small success.\n\n"
                f"If it isn't easing after a couple of weeks, or it's getting worse, it's worth asking {pro}.")
    elif re.search(r"\bhow (?:can|do|could|should) i (?:not get|stop (?:being|getting)|avoid (?:being|getting)|deal with (?:being|getting)) "
                   r"(?:so |too )?(?:nervous|anxious|scared|stressed)\b|\b(?:tips|advice) for (?:not getting|being less|dealing with) "
                   r"(?:nervous|nerves|anxious|stage fright)\b", low):
        text = ("Nerves mostly shrink with preparation and practice in front of people:\n\n"
                "- Know your opening cold. The first thirty seconds are the hardest, and a solid start carries you.\n"
                "- Rehearse in front of one person, then a few, before the real thing.\n"
                "- Slow down and breathe out longer than you breathe in just before you begin.\n"
                "- Expect a mistake and plan to keep going; almost nobody notices the ones you don't react to.\n"
                "- Remember the people watching want it to go well.")
    elif re.search(r"\b(?:silly|stupid|crazy|mad|a mistake|a bad idea|dumb) (?:of me )?to (?:do|have done|try|tackle) (?:it|this|that|everything|the whole thing|all)\b", low):
        text = ("Not silly at all. Doing it yourself saves money and you end up with something you did with your own hands, which is worth "
                "being pleased about. The aches are just the price of two hard days' work: rest, a warm shower and some gentle stretching help, "
                "and they usually fade in a day or two. Next time, splitting it into shorter sessions or roping in a friend makes it easier going.")
    elif re.search(r"\bask(?:ing)? (?:for it|for the money|(?:him|her|them) for (?:it|the money)) back\b|\bget (?:my|the) money back\b|\bpay (?:me )?back\b", low) and re.search(
            r"(?i)\b(?:borrow|lent|lend|owe|money|loan|paid)", recent):
        text = ("Keep it private, friendly and specific, and make it easy to say yes:\n\n"
                "- Pick a relaxed moment, one to one, rather than in front of others.\n"
                "- Mention it plainly instead of hinting: people genuinely forget.\n"
                "- Give a reason or a plan, so it isn't about trust.\n"
                "- Offer a way to do it in parts if that's easier.\n\n"
                "Something like: \"Hey, about the money I lent you a while back: would you be able to pay it back by the end of the month? "
                "I'm trying to sort out my budget. Happy for you to do it in a couple of goes if that's easier.\"")
    elif re.search(r"\bhow (?:should|do|can|could|would) i (?:best )?(?:bring (?:it|this|that) up|raise (?:it|this|that)|tell (?:him|her|them)|say (?:it|this|that)|"
                   r"approach (?:him|her|them|it|this)|talk to (?:him|her|them)|ask (?:him|her|them)|put it|word it|mention it)\b|"
                   r"\b(?:polite|nice|good|best|tactful|gentle|kind|friendly|diplomatic) way (?:to|of) (?:bring(?:ing)? (?:it|this|that) up|rais(?:e|ing)|say(?:ing)?|"
                   r"tell(?:ing)?|ask(?:ing)?|mention(?:ing)?|put(?:ting)? it|approach(?:ing)?)\b", low):
        text = ("A calm, specific request usually lands best:\n\n"
                "- Pick a quiet moment, not right after it has happened while you're still annoyed.\n"
                "- Describe the one thing that's the problem, without \"always\" or \"never\".\n"
                "- Say how it affects you, then ask for one concrete change.\n"
                "- Assume they haven't noticed, and leave room for their side.\n\n"
                "Something like: \"Have you got a minute? There's a small thing I'd like to sort out. When that happens it makes things awkward for me. "
                "Could we agree on a way round it?\" Said in a friendly tone, that reads as a request, not a complaint.")
    elif (re.search(r"\bhow (?:should|do|can|could) i (?:begin|start|get started|get going|get into it|ease into it)\b|\bwhere do i (?:start|begin)\b", low)
          or (re.search(r"\bhow often should i\b", low) and LEARN.search(recent))) \
            and not re.search(r"\bfeed\b|\bwater\b|\bwash\b|\bclean\b|\breplace\b|\bchange\b|\bdescale\b|\bservice\b|\bcharge\b", low):
        fit = re.search(r"(?i)\b(?:run|running|jog|jogging|gym|exercise|workout|swim|swimming|cycling|cycle|fitness|5k|10k|marathon|out of breath|training)\b", recent)
        if fit:
            run = re.search(r"(?i)\b(?:run|running|jog|jogging|5k|10k)\b", recent)
            how = ("Alternate short easy jogs with walking, for example one minute jogging and two minutes walking, repeated for about twenty minutes."
                   if run else "Keep the first sessions short and easy, around twenty minutes, and stop while you still feel you could do more.")
            text = (f"Start easier than you think you need to:\n\n- {how}\n"
                    f"- Three times a week, with a rest day in between, is plenty at first; the body adapts on the rest days.\n"
                    f"- Keep to a pace at which you could still talk. Getting out of breath quickly usually just means going too fast.\n"
                    f"- Add a little each week, not each session.\n\n"
                    f"If you have a health condition, or you get chest pain or dizziness, check with a doctor before pushing on.")
        else:
            text = ("Start small and regular:\n\n- Short sessions most days (ten to twenty minutes) beat one long session a week.\n"
                    "- Fix it to something you already do, such as straight after breakfast, so you don't rely on motivation.\n"
                    "- Begin with the easiest useful piece, and add to it only when that feels comfortable.\n"
                    "- Keep a simple tally of the days you did it; a visible streak is surprisingly motivating.")
    elif re.search(r"\bwhat (?:should|do|shall|would) (?:we|i) (?:absolutely |really |definitely )?(?:pack|bring|take|not forget|need to (?:pack|bring|take))\b|"
                   r"\bwhat (?:to|should (?:we|i)) pack\b|\bpacking list\b|\bwhat (?:are|were) the essentials\b", low) and re.search(
            r"(?i)\b(?:camp|camping|hike|hiking|trek|trip|holiday|vacation|travel|weekend|festival|beach|backpacking|walk)\b", recent):
        camp = re.search(r"(?i)\bcamp", recent)
        hike = re.search(r"(?i)\b(?:hik|trek|walk|backpack)", recent)
        kids = CHILD.search(recent)
        lines = []
        if camp:
            lines.append("Sleep and shelter: tent with all its pegs and poles, a sleeping bag and mat each, and a warm layer for the night.")
        lines.append("Weather: a waterproof, one more warm layer than you expect to need, and spare socks.")
        lines.append("Light: a torch or head torch each, with spare batteries.")
        lines.append("Food and water: more water than you think, simple meals, snacks" + (", and a way to boil water." if camp or hike else "."))
        lines.append("Safety: a small first-aid kit, any medication, sun cream, insect repellent, a charged phone and a power bank" + (", and a paper map." if hike or camp else "."))
        if hike:
            lines.append("On your feet: shoes you have already worn in, and blister plasters.")
        if kids:
            lines.append("For the children: a familiar toy or blanket, and something to do if it rains.")
        text = "The things people most often regret leaving behind:\n\n" + '\n'.join('- ' + x for x in lines) + \
               "\n\nLay it all out the night before and tick it off as it goes into the bag."
    elif re.search(r"\bhow (?:can|do|could|should) i (?:stop|get) (?:her|him|them|it|my \w+)\b", low) and (PET.search(recent) or CHILD.search(recent)):
        text = ("The approach that usually works is to redirect rather than punish:\n\n"
                "- Give an allowed outlet for the same urge, right beside the problem spot.\n"
                "- Make the unwanted option less appealing or harder to reach for a while.\n"
                "- Reward the behaviour you want the moment it happens.\n"
                "- Be consistent, and give it a couple of weeks.\n\n"
                "Telling off after the event doesn't help, because the connection isn't made. "
                f"If it's sudden or comes with other changes, check with {pro}.")
    if text is None:
        return None
    return dict(route='chat/counsel', response=text, sources=[],
                details='General guidance for this kind of question (counsel.py): nothing specific was found by the solvers or the web researchers.')
