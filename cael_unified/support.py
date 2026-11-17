"""The Supporter: an emotional conversation over several turns, not one reply.

The Listener (empath.py) answers one hard thing said. People then go on: "I just feel like I'm not good enough." "What
should I do next?" "Is it normal to feel this sad about a pet?" "How do people keep a friendship going over that
distance?" Those follow-ups were answered as if nothing had been said before (a search on their words). The Supporter
keeps the situation the user is in, a frame read from the last few turns, and answers each kind of turn in it:

  a feeling told     ->  it is taken seriously, the true thing about that kind of moment, and a gentle offer
  more told after    ->  the new detail reflected, and the first two things that help (never the same words again)
  "is it normal?"    ->  an honest yes with why
  "what can I do?"   ->  the few things that help most in that situation, warm and practical
  "how do I help him/her?" (someone else's feeling) -> what helps the other person

Frames: loneliness, grief, a setback (job, exam, place), a child who is upset (left out, or after a setback), self-doubt,
nerves before an event, someone moving away, stress over a dispute about money or work done, overwhelm, and anger with
someone. Authored text and patterns; no model.
"""
import re

FEEL = re.compile(r"(?i)\b(?:lonely|alone|isolated|sad|upset|crying|cried|heartbroken|devastated|gutted|miss (?:her|him|them|it)|going to miss|"
                  r"stressed|stress|anxious|nervous|scared|worried|dreading|overwhelmed|exhausted|angry|furious|fed up|hurt|ashamed|embarrassed|"
                  r"not good enough|stupid|useless|failure|worthless|empty|grief|grieving|died|passed away|rejected|didn'?t get|didn'?t pass|failed|"
                  r"left out|feel (?:like|so|really|awful|terrible|bad|low|down|flat))\b")

FRAMES = [
    # (name, pattern over the last few user turns), most specific first
    ('grief', re.compile(r"(?i)\b(?:died|passed away|put (?:him|her|them) (?:down|to sleep)|funeral|lost (?:my|our) (?:dog|cat|mum|mom|dad|mother|father|"
                         r"grandma|grandad|grandmother|grandfather|husband|wife|partner|friend|brother|sister|pet)|grieving|grief)\b")),
    ('leaving', re.compile(r"(?i)\b(?:is|are|'s) (?:moving|emigrating|relocating) (?:to|away|abroad)\b|\bmoving (?:to|abroad|away)\b.*\b(?:miss|friend)\b|"
                           r"\b(?:going to|will) miss (?:her|him|them)\b|\blong[- ]distance\b|\bover that distance\b")),
    ('nerves', re.compile(r"(?i)\b(?:nervous|anxious|dreading|scared|terrified|worried|panicking)\b.*\b(?:test|exam|interview|presentation|speech|audition|"
                          r"first day|appointment|operation|performance|match|race|driving)\b|\b(?:test|exam|interview|presentation|speech|audition|"
                          r"first day|driving test)\b.*\b(?:nervous|anxious|dreading|scared|terrified|worried|stall|panic)\b")),
    ('child_upset', re.compile(r"(?i)\b(?:my|our) (?:son|daughter|child|kid|boy|girl|little one|teenager)\b.*\b(?:upset|crying|cried|sad|says (?:he'?s|she'?s)|"
                               r"thinks (?:he'?s|she'?s)|left out|failed|bullied|anxious|worried)\b|\b(?:he|she) says (?:he'?s|she'?s) (?:just )?(?:stupid|useless|"
                               r"rubbish|thick|dumb|a failure|not good)\b")),
    ('setback', re.compile(r"(?i)\b(?:didn'?t get|did not get|didn'?t pass|failed|rejected|turned down|wasn'?t (?:chosen|picked|selected)|"
                           r"got (?:a |the )?(?:rejection|no)|lost (?:the|my) (?:job|place|match|competition))\b")),
    ('dispute', re.compile(r"(?i)\b(?:builder|plumber|landlord|garage|tradesman|contractor|company|shop|seller|electrician|roofer|decorator)\b.*\b(?:won'?t|hasn'?t|"
                           r"refuses|ignor\w*|left|kept|stopped|disappeared|answer)\b|\b(?:paid (?:him|her|them)|already paid|kept (?:our|my) (?:deposit|money))\b")),
    ('lonely', re.compile(r"(?i)\b(?:lonely|isolated|on my own all|don'?t (?:really )?see anyone|no one to talk to|nobody to talk to|don'?t know anyone|"
                          r"no friends|miss (?:having )?people)\b")),
    ('self_doubt', re.compile(r"(?i)\b(?:not good enough|i'?m (?:so |just )?(?:stupid|useless|a failure|rubbish|hopeless)|i feel (?:like )?(?:a failure|useless|"
                              r"stupid|a fraud|worthless)|i'?ll never)\b")),
    ('overwhelmed', re.compile(r"(?i)\b(?:overwhelmed|too much (?:on|going on)|can'?t cope|drowning|burn(?:ed|t)? out|exhausted|so stressed|stressed)\b")),
    ('angry', re.compile(r"(?i)\b(?:so angry|furious|fuming|livid|fed up with|really annoyed|so annoyed)\b")),
]

ASK_NORMAL = re.compile(r"(?i)\b(?:is (?:it|this|that) (?:normal|ok|okay|weird|silly|strange)|am i (?:being )?(?:silly|weird|overreacting|normal)|"
                        r"is it normal|do (?:other )?people feel)\b")
ASK_DO = re.compile(r"(?i)\b(?:what (?:should|can|could|do) (?:i|we) do|what (?:now|next)|how do (?:i|we) (?:cope|deal|handle|move on|get over|stop|keep|"
                    r"stay|help)|any (?:tips|advice|ideas)|how (?:can|could|do) (?:i|we)|how do people|where do i start|what would you (?:do|suggest)|what helps)\b")
ASK_HELP_OTHER = re.compile(r"(?i)\bhow (?:do|can|could|should) (?:i|we) (?:help|support|talk to|reassure|cheer up) (?:him|her|them)\b|\bhelp (?:him|her|them)\b")
LEFT_OUT = re.compile(r"(?i)\b(?:left out|excluded|leaving (?:her|him) out|no(?:body| one) (?:to play|plays|invited)|not invited|wasn'?t invited|"
                      r"none of (?:her|his) friends|bullied|bullying|picked on|on (?:her|his) own at (?:break|lunch|school)|no friends)\b")

ACK = {
    'grief': "I'm so sorry. Losing {who} is a real loss, and the quiet afterwards can be the hardest part.",
    'leaving': "That's a big change. It's completely natural to feel sad about it, even while you're glad for them.",
    'nerves': "That's completely understandable. Nearly everyone feels like this beforehand, and it usually feels worse in the run-up than on the day.",
    'setback': "I'm sorry, that's a real disappointment, especially when you'd put so much into it.",
    'dispute': "That's really stressful, especially with money already paid. You're right to want it sorted.",
    'lonely': "That sounds hard. Working or living in a way where you don't see people can creep up on you, and loneliness is far more common than people admit.",
    'self_doubt': "I'm sorry you're feeling that way. One setback can make it feel like proof about yourself, but it isn't.",
    'overwhelmed': "That sounds like a lot to carry at once. It makes sense that you're feeling stretched.",
    'angry': "That would make anyone angry. It's fair to feel that way.",
}
SECOND = {
    'grief': "Grief often comes in waves, and small things (a bowl, a spot on the sofa, a sound) can set it off.",
    'leaving': "Friendships that matter usually survive distance; they just need a bit more planning than before.",
    'nerves': "Nerves are your body getting ready, and a little of it actually helps you perform.",
    'setback': "Results like this often come down to small margins and things you can't see, not to whether you're good enough.",
    'dispute': "There are clear steps you can take, and having already paid gives you rights, not fewer.",
    'lonely': "Small, regular contact tends to help more than one big effort.",
    'self_doubt': "The fact that it hurts shows how much it matters to you, and that's worth something.",
    'overwhelmed': "You don't have to sort everything today; one small thing at a time is enough.",
    'angry': "It's worth letting the first wave pass before you decide what to do about it.",
}
OFFER = {
    'grief': "Would you like to talk about {her}?",
    'leaving': "Would it help to think about ways to stay close?",
    'nerves': "Would a few ideas for staying calm on the day help?",
    'setback': "Do you want to talk about how it went, or think about what to do next?",
    'dispute': "Would it help to go through what you can do next?",
    'lonely': "Would you like a few ideas that people find help?",
    'self_doubt': "What happened that's made you feel this way?",
    'overwhelmed': "What's weighing on you most right now?",
    'angry': "What happened?",
}
NORMAL = {
    'grief': "Yes, completely. For many people a pet is family: there every day, part of every routine, and losing them is real grief. "
             "Feeling this sad, the house feeling empty, even expecting to see them: all of that is normal, and it usually softens with time "
             "rather than all at once. If it stays this heavy for many weeks, or stops you getting through the day, talking to someone (a friend, "
             "your GP, or a pet bereavement line) can really help.",
    'leaving': "Yes. Missing someone before they've even gone is very common, because you're already picturing the gap. It usually eases once "
               "you've found a new rhythm of keeping in touch.",
    'nerves': "Yes, very. Almost everyone is nervous before something that matters to them, and it often peaks the night before. It doesn't mean "
              "it will go badly.",
    'setback': "Yes. Feeling flat, doubting yourself and replaying it all are normal for a few days after a knock like this. It usually passes "
               "faster if you rest a little and then take one small next step.",
    'child_upset': "Yes. Children often say harsh things about themselves when they're disappointed or hurt; it's a feeling, not a fixed belief, and "
                   "how the adults around them respond makes a big difference.",
    'dispute': "Yes, completely. Money and your home are both involved, which is about as stressful as everyday problems get.",
    'lonely': "Yes, very. Loneliness is common, especially after a change like working from home or moving, and it's nothing to be ashamed of.",
    'self_doubt': "Yes. Most people feel like this after a setback; it's a passing feeling, not a fact about you.",
    'overwhelmed': "Yes. When too much lands at once, feeling overwhelmed is a normal reaction, not a sign you're failing.",
    'angry': "Yes. Anger is a normal reaction to being let down or treated unfairly.",
}
DO = {
    'grief': ["Let yourself be sad: there's no right amount of time.", "Keep a little routine going (meals, a walk), even if it feels pointless.",
              "Do something to remember them: photos, a small memorial, or writing down favourite memories.",
              "Talk about them with someone who knew them; many people find a pet bereavement line helpful too.",
              "Put away their things when you feel ready, not before."],
    'leaving': ["Set a regular time to talk (a video call every week or two) so it doesn't depend on remembering.",
                "Work out the time difference early and pick a slot that suits you both.",
                "Share small everyday things: photos, voice notes, a book or series you both follow.",
                "Plan a visit, even a long way off: having a date to look forward to helps a lot.",
                "Mark the big days (birthdays, news) with a card or a parcel."],
    'nerves': ["Prepare the practical bits the day before (documents, route, what you'll wear) so the morning is calm.",
               "Sleep and eat normally; skip extra caffeine.",
               "Breathe out slowly and longer than you breathe in for a minute: it calms the body quickly.",
               "Arrive a little early, and focus only on the next step rather than the whole thing.",
               "If something goes wrong, keep going: one mistake rarely decides the outcome."],
    'setback': ["Give yourself a day or two to be disappointed before deciding anything.",
                "Ask for feedback: many places will tell you what tipped it, and it's useful next time.",
                "Write down what went well, as well as what you'd change.",
                "Keep going with the next application or attempt, so this one stops feeling like the only chance.",
                "Talk it through with someone who knows you; they'll see your strengths more clearly than you can right now."],
    'dispute': ["Write down the dates, what was agreed and everything you've paid, with receipts and messages.",
                "Send a clear written message (email or letter) saying what's left to do and giving a deadline, say 14 days.",
                "Don't pay anything more until the work is done or agreed in writing.",
                "Check the contract or quote, and whether you paid by card (your card provider may be able to help).",
                "If there's no reply, a consumer advice service or the small claims court can help you get the money back."],
    'lonely': ["Build one regular contact into your week: a call with a friend, a class, a club or a volunteering slot.",
               "Work somewhere else now and then: a café, library or coworking space.",
               "Say yes to small invitations, and send a few yourself; most people are glad to be asked.",
               "Get out of the house every day, even for a short walk.",
               "If it's been weighing on you for a long time, it's worth mentioning to your GP."],
    'self_doubt': ["Look at the evidence: what have you done well, and what would you say to a friend in the same spot?",
                   "Separate one result from who you are.", "Pick one small next step you can manage this week.",
                   "Talk to someone who knows you well; they'll see it more clearly."],
    'overwhelmed': ["Write everything down so it's out of your head.", "Pick the one or two things that really have to happen this week.",
                    "Ask for help with something, or let something go for now.", "Protect sleep and a little time off; it's not a luxury when you're stretched."],
    'angry': ["Wait until the first wave passes before you reply or act.", "Say what happened and how it affected you, not what's wrong with them.",
              "Decide what outcome you actually want, and ask for that.", "If it's serious, put it in writing."],
}
LEAD_DO = {'grief': "A few things that people find help:", 'leaving': "A few things that keep long-distance friendships going:",
           'nerves': "A few things that help on the day:", 'setback': "A few things that help after a knock like this:",
           'dispute': "Here's what I'd do next:", 'lonely': "A few things that people find help:", 'self_doubt': "A few things that can help:",
           'overwhelmed': "A few things that help when it's too much:", 'angry': "A few things that help:"}
CHILD = {
    'left_out': dict(
        ack="That's so hard to see, and it's clear how much it's hurting {him}. Being left out by friends is one of the most painful parts of school.",
        second="It's very common at this age, when friendship groups shift a lot, and it often settles, especially with a parent quietly in {his} corner.",
        offer="Would it help to think about how to talk to {him} about it, or whether to speak to the school?",
        lead="A few things that tend to help a child who's being left out:",
        do=["Listen without rushing to fix it, and say the feelings make sense.",
            "Ask gently what happens at break and lunch, so you know whether it's a falling-out or something that keeps happening.",
            "Help {him} build one or two friendships outside the group: invite a classmate round, or join a club or activity {he} likes.",
            "Talk through what {he} could say or do, without making it {his} fault.",
            "If it carries on, or {he}'s being picked on, have a calm word with the teacher; schools deal with this a lot and can help quietly.",
            "Keep home warm and predictable, so it's a safe place to come back to."]),
    'setback': dict(
        ack="That's hard to watch as a parent. It's good that {he}'s telling you how {he} feels.",
        second="What children say in the moment, like calling themselves stupid, is usually the disappointment talking, not a fixed belief.",
        offer="Would it help to think about what to say to {him}?",
        lead="A few things that help a child who's feeling like that:",
        do=["Listen first and name the feeling: \"You're really disappointed\" before any fixing.",
            "Separate the result from {him}: a bad test is something that happened, not who {he} is.",
            "Praise effort and progress rather than results, and remind {him} of something {he} found hard and then got better at.",
            "Make a small, doable plan together: a little practice, or a question for the teacher about what to work on.",
            "If it keeps happening or {he} seems very low, have a word with the teacher."]),
}


def frame_of(users):
    """(frame, the user turn it came from) for the last three user turns, newest first."""
    for t in reversed(users[-3:]):
        for name, pat in FRAMES:
            if pat.search(t):
                return name, t
    return None, None


def who_died(text):
    m = re.search(r"(?i)\b(?:my|our) (dog|cat|rabbit|hamster|horse|pet|mum|mom|dad|mother|father|grandma|grandad|grandmother|grandfather|"
                  r"husband|wife|partner|friend|brother|sister)\b", text or '')
    return 'your ' + m[1].lower() if m else 'someone you love'


def pronouns(users):
    text = ' '.join(users)
    if re.search(r"(?i)\b(?:daughter|girl|she|her)\b", text):
        return dict(he='she', him='her', his='her')
    if re.search(r"(?i)\b(?:son|boy|he|him)\b", text):
        return dict(he='he', him='him', his='his')
    return dict(he='they', him='them', his='their')


def child_kind(users):
    return 'left_out' if LEFT_OUT.search(' '.join(users[-3:])) else 'setback'


def respond(messages):
    users = [m['content'] for m in messages if m.get('role') == 'user' and isinstance(m.get('content'), str)]
    if not users:
        return None
    last = users[-1]
    if any(re.search(r"(?i)\b(?:no advice|not? (?:give|giving) (?:me )?advice|don'?t advise|just (?:listen|want to vent)|no (?:questions|suggestions|solutions)|"
                     r"don'?t ask|not looking for (?:advice|solutions)|don'?t try to fix|without giving advice|or quiz me)\b", t) for t in users[-4:]):
        return None                                 # the user has said how they want to be answered: the conversation rules keep that
    if not any(FEEL.search(t) for t in users[-3:]):
        return None                                 # no feeling in the conversation: not the Supporter's
    frame, told = frame_of(users)
    if not frame:
        return None
    if re.search(r"(?i)\b(?:\d+\s*[%$£€]|\$\s?\d|how much (?:is|do|does|should|will)|calculate|percent)\b", last) and not ASK_DO.search(last):
        return None                                 # a sum, even in an emotional conversation: the Calculator's
    asked = last.strip().endswith('?')
    p = pronouns(users)
    child = CHILD[child_kind(users)] if frame == 'child_upset' else None

    def fill(x):
        return x.format(who=who_died(told), her=p['him'], **p)

    if asked and ASK_NORMAL.search(last):
        return dict(route='chat/support', response=NORMAL[frame], sources=[], details=f'The Supporter: is it normal, in a "{frame}" situation (support.py).')
    if asked and (ASK_DO.search(last) or ASK_HELP_OTHER.search(last)):
        items, lead = (child['do'], child['lead']) if child else (DO[frame], LEAD_DO[frame])
        warm = {'grief': "I'm sorry again for your loss.", 'self_doubt': "And for what it's worth, one result doesn't define you.",
                'setback': "And it's okay to still feel flat about it for a bit."}.get(frame, '')
        text = lead + '\n\n' + '\n'.join(f'- {fill(x)}' for x in items) + (f'\n\n{warm}' if warm else '')
        return dict(route='chat/support', response=text, sources=[], details=f'The Supporter: what helps, in a "{frame}" situation (support.py).')
    if asked:
        return None                                 # a question about something else: the other agents
    if re.search(r"(?i)\b(?:he|she) says (?:he'?s|she'?s)\b", last) and frame != 'child_upset':
        frame, child = 'child_upset', CHILD['setback']
    if child:
        ack, second, offer = fill(child['ack']), fill(child['second']), fill(child['offer'])
    else:
        ack, second, offer = fill(ACK[frame]), fill(SECOND[frame]), fill(OFFER[frame])
    if frame == 'dispute' and re.search(r"(?i)\bpaid\b", last):
        second = "Having paid most of the money doesn't leave you without options: you're owed the work or a refund, and there are steps to get it."
    if frame == 'self_doubt' and len(users) > 1:
        ack = ("I'm sorry you're feeling that way, but one result doesn't mean you're not good enough. Decisions like that come down to small "
               "margins and things you never see.")
        second = "The fact that you got that far says something."
    # more told after the Supporter's own acknowledgement: reflect the new detail and move to what helps, never the same words
    before = [m.get('content') or '' for m in messages[:-1] if m.get('role') == 'assistant']
    if len(users) > 1 and before and before[-1][:30] == ack[:30]:
        items = child['do'] if child else DO[frame]
        reflect = {'child_upset': f"Hearing {p['him']} say that is hard. It's the disappointment talking: one result is a snapshot, not a verdict on {p['him']}.",
                   'lonely': "That's a long time to go without company, and it makes sense that it's getting to you.",
                   'grief': "Of course. The gaps they leave are everywhere at first.",
                   'leaving': "That makes complete sense: you're already feeling the gap."}.get(frame, "That makes sense, and it's a lot to carry.")
        if child is CHILD['left_out']:
            reflect = f"Coming home in tears again is a sign it's really getting to {p['him']}, and it's good {p['he']} can bring it to you."
        text = f"{reflect} Two things that often help straight away:\n\n- {fill(items[0])}\n- {fill(items[1])}\n\nWould you like a few more ideas?"
        return dict(route='chat/support', response=text, sources=[], details=f'The Supporter: more told in a "{frame}" situation (support.py).')
    return dict(route='chat/support', response=f"{ack} {second} {offer}", sources=[], details=f'The Supporter: a feeling told in a "{frame}" situation (support.py).')
