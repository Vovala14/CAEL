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
                  r"stressed|stress|anxious|nervous|scared|terrified|petrified|frightened|afraid|panicking|panicked|freaking out|"
                  r"worried|worrying|dreading|dread|overwhelmed|exhausted|angry|furious|fed up|hurt|ashamed|embarrassed|"
                  r"not good enough|stupid|useless|failure|worthless|empty|grief|grieving|died|passed away|rejected|didn'?t get|didn'?t pass|failed|"
                  r"left out|feel (?:like|so|really|awful|terrible|bad|low|down|flat)|imagining the worst|(?:thinking|expecting|assuming|fearing) the worst|"
                  r"worst[- ]case|can'?t stop thinking|can'?t stop worrying|on edge|a wreck|nervous wreck|bricking it|keep panicking)\b")

FRAMES = [
    # (name, pattern over the last few user turns), most specific first
    ('grief', re.compile(r"(?i)\b(?:died|passed away|put (?:him|her|them) (?:down|to sleep)|funeral|lost (?:my|our) (?:dog|cat|mum|mom|dad|mother|father|"
                         r"grandma|grandad|grandmother|grandfather|husband|wife|partner|friend|brother|sister|pet)|grieving|grief)\b")),
    ('health_wait', re.compile(r"(?i)\b(?:biopsy|scan|mri|x-?ray|mammogram|smear|blood (?:test|work)s?|test results?|results? from (?:the )?(?:doctor|hospital|gp|clinic)|"
                               r"lump|tumou?r|cancer|consultant|specialist|referral)\b.*\b(?:wait|waiting|hear|heard|results?|back|find out|news)\b|"
                               r"\b(?:wait|waiting|hear|heard|find out)\b.*\b(?:biopsy|scan|mri|mammogram|blood (?:test|work)|test results?|lump|cancer|consultant)\b")),
    ('waiting', re.compile(r"(?i)\b(?:results?|grades?|marks?) (?:come|comes|are|is|coming) out\b|\b(?:waiting (?:for|to hear|to find out)|haven'?t heard (?:back|anything)|"
                           r"find out (?:if|whether|on|next|tomorrow|soon))\b|\b(?:scared|worried|terrified|afraid|convinced|sure) (?:that )?i (?:failed|didn'?t pass|didn'?t get|"
                           r"messed (?:it )?up|bombed)\b|\b(?:anxious|nervous|worried|scared) about (?:my|the) (?:\w+ )?results?\b")),
    ('leaving', re.compile(r"(?i)\b(?:is|are|'s) (?:moving|emigrating|relocating) (?:to|away|abroad)\b|\bmoving (?:to|abroad|away)\b.*\b(?:miss|friend)\b|"
                           r"\b(?:going to|will) miss (?:her|him|them)\b|\blong[- ]distance\b|\bover that distance\b")),
    ('nerves', re.compile(r"(?i)\b(?:nervous|anxious|dreading|scared|terrified|petrified|frightened|afraid|worried|panicking)\b.*\b(?:test|exam|interview|presentation|speech|audition|"
                          r"first day|appointment|operation|performance|match|race|driving|drive|motorway|highway|freeway|flight|flying|fly|surgery|dentist|first time)\b|"
                          r"\b(?:driving|drive|flying|fly|motorway|highway|flight)\b.*\b(?:petrified|terrified|scared|frightened|afraid|nervous|anxious)\b|\b(?:test|exam|interview|presentation|speech|audition|"
                          r"first day|driving test)\b.*\b(?:nervous|anxious|dreading|scared|terrified|worried|stall|panic)\b")),
    ('child_upset', re.compile(r"(?i)\b(?:my|our) (?:little |young |eldest |youngest |oldest )?(?:son|daughter|child|kid|boy|girl|little one|teenager)\b.*\b(?:upset|crying|cried|sad|"
                               r"devastated|gutted|heartbroken|didn'?t get (?:in|into|picked|chosen|selected)|wasn'?t (?:picked|chosen|selected)|left out of|"
                               r"cries|clings|says (?:he'?s|she'?s)|"
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
    'waiting': "Waiting for results is horrible: there's nothing left to do, so your mind fills the gap with the worst case.",
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
    'waiting': "Most people come out of an exam sure they did worse than they did; the feeling is not a result.",
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
    'waiting': "Would it help to think about how to get through the days until then?",
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
    'waiting': "Yes, completely. Waiting is often harder than the exam itself, because there's nothing left you can do. Replaying answers and "
               "expecting the worst are very common, and they say little about the real result.",
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
    'waiting': ["Notice when you're replaying answers, and gently bring yourself back to today: it can't change the result now.",
                "Fill the days with things that need your attention: plans with friends, exercise, a film, a job to do.",
                "Limit checking forums or comparing answers with others; it feeds the worry without telling you anything.",
                "Make a simple plan B for the worst case (a resit, an appeal, another route). Knowing there's a next step takes the edge off.",
                "Plan something for the day the results come out, whatever they are, so it isn't only about the grade."],
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
LEAD_DO = {'waiting': "A few things that help while you wait:", 'grief': "A few things that people find help:", 'leaving': "A few things that keep long-distance friendships going:",
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


# Waiting for medical results: not an exam, so nothing about re-marks or retakes.
ACK['health_wait'] = "Waiting to hear back after a test like that is really hard. There's nothing you can do to speed it up, so your mind fills the gap."
SECOND['health_wait'] = ("Most biopsies and scans come back with something manageable or nothing serious at all, and imagining the worst is what "
                         "almost everyone does while they wait. It's a sign of how much it matters, not a sign of what the result will be.")
OFFER['health_wait'] = "Would it help to think about how to get through the next few days?"
NORMAL['health_wait'] = ("Completely normal. Almost everyone imagines the worst while waiting for results; the not-knowing is often harder than "
                         "the news itself. It doesn't mean anything about what they'll find.")
DO['health_wait'] = ["Ask the clinic or your GP when and how you'll hear, so you're not checking your phone every hour.",
                     "Keep your days ordinary and full: work, a walk, people you like. Busy hours pass faster than empty ones.",
                     "When the worst-case film starts playing, name it (\"that's the worry, not a fact\") and bring yourself back to what you're doing.",
                     "Tell one or two people you trust, so you're not holding it alone; having someone with you when you get the results helps too.",
                     "Go easy on searching online: it shows the rarest, scariest cases, not yours.",
                     "If the worry is overwhelming or you can't sleep for days, call your GP or the clinic: they're used to this and can talk it through."]
LEAD_DO['health_wait'] = "A few things that help people get through the wait:"

CHILD['new_school'] = dict(
    ack="Starting a new school is a big step, and it's very common to feel anxious beforehand. It's good that {he}'s telling you.",
    second="The usual worries are not knowing anyone and getting lost, and both tend to fade within the first week or two: almost everyone is new and looking for someone to talk to.",
    offer="Would it help to think about a few ways to help {him} feel ready?",
    lead="A few things that help a child before starting a new school:",
    do=["Listen and take the worry seriously, then remind {him} that almost everyone in the year is new and nervous too.",
        "Practise the practical bits: the route, what time to leave, where to go on the first morning. Less unknown means less worry.",
        "Think together about easy ways to start talking: \"Which form are you in?\", \"What did you think of that lesson?\"",
        "If anyone from {his} old school is going, arrange to walk in together or meet up beforehand.",
        "Suggest joining one club in the first weeks: friendships form fastest around something shared.",
        "Keep the first evenings calm and ask about one good thing from the day, not just how it went.",
        "If {he} is still very unhappy after a few weeks, talk to {his} form tutor; schools are used to helping new pupils settle."])

MORNING = re.compile(r"(?i)\b(?:tomorrow morning|in the morning|for the morning|this morning|on the day|before (?:i|we) (?:go|leave|set off)|tips for tomorrow)\b")
DRIVE = re.compile(r"(?i)\b(?:motorway|highway|freeway|driving|drive)\b")


def drive_what_if(last):
    if MORNING.search(last) or re.search(r"(?i)\btips\b", last):
        return ("A few things for the morning:\n\n"
                "- Plan the route the night before, including which junction you leave at, and look at the slip roads on a map so nothing surprises you.\n"
                "- Leave early so you're never rushing, and go at a quieter time if you can, after the rush hour.\n"
                "- Set the seat, mirrors and sat-nav before you set off, and have a drink of water.\n"
                "- Join from the slip road by matching the speed of the traffic, then settle into the left lane (the right in countries that drive on the right) and stay there.\n"
                "- Keep a two-second gap (four in the rain) to the car in front; it gives you time to think.\n"
                "- Plan an easy first trip: a short stretch, off at the next junction, and a break at services if you want one.\n\n"
                "Most people find the motorway calmer than town once they're on it: everyone goes the same way and there are no junctions to cross.")
    if WHAT_IF.search(last) and re.search(r"(?i)\b(?:panic|freeze|shake|shaking|lose it|can'?t cope)\b", last):
        return ("If you start to panic, keep it simple: stay in the left lane (the slow lane), ease off the accelerator a little, keep both hands on the "
                "wheel and breathe out slowly, longer than you breathe in. You don't have to overtake anyone. If you need to stop, leave at the next "
                "junction or pull into the next services; the hard shoulder is only for emergencies. Panic peaks and then passes within a few minutes, "
                "and lots of people feel it on their first motorway drive and are fine.")
    return None


# ---------------------------------------------------------------- round f: wider recognition (feelings shown, not named)
FEEL2 = re.compile(r"(?i)\b(?:knot in my stomach|(?:stomach|tummy) (?:is )?(?:in|tied in) knots|can'?t think (?:about|of) anything else|butterflies|a (?:nervous )?(?:mess|wreck)|feel(?:ing)? sick|sick with (?:nerves|worry)|(?:hands|legs) (?:are )?(?:already )?shaking|"
                   r"shaking|keep (?:refreshing|checking)|can'?t stop (?:checking|refreshing|thinking|worrying|crying)|on edge|can'?t concentrate|"
                   r"burn(?:ed|t)[- ]out|can (?:barely|hardly) get out of bed|running on empty|at the end of my tether|in pieces|beside myself|"
                   r"not coping|falling apart|really miss|miss (?:him|her|them) so much|keep expecting (?:him|her|them|to see)|keep crying|"
                   r"(?:he|she|they|son|daughter|child|kid|boy|girl|toddler|baby) (?:cries|cry|screams|clings)|won'?t settle)\b")
EMO_EVENT = re.compile(r"(?i)\b(?:had to (?:be )?put (?:him|her|them|it)? ?down|(?:was|were|got) put (?:down|to sleep)|put to sleep|passed away|died|funeral|"
                       r"emigrat\w+|moved (?:away|abroad|overseas|to (?:another|a different) (?:country|city))|"
                       r"(?:operation|surgery|biopsy|scan) (?:is )?(?:on|tomorrow|next|this)|waiting (?:on|for) (?:my |the |a )?(?:offer|reply|response|decision|callback|results?|news)|"
                       r"(?:hasn'?t|still hasn'?t|haven'?t|still haven'?t) (?:called|got|gotten|heard) back|didn'?t get the (?:job|promotion|place|flat|house)|"
                       r"kept (?:my|our) (?:whole |entire |full )?deposit)\b")
_EXTRA = {
    'grief': r"|\b(?:had to (?:be )?put (?:him|her|them|it)? ?down|(?:was|were|got) put (?:down|to sleep)|put to sleep|we lost (?:our|my))\b",
    'waiting': r"|\bwaiting (?:on|for) (?:my |the |a |an )?(?:\w+ )?(?:offer|reply|response|decision|callback|news|answer)\b|\b(?:hasn'?t|still hasn'?t|haven'?t|still haven'?t) "
               r"(?:called|got|gotten|heard) back\b|\bkeep (?:refreshing|checking) (?:my )?(?:phone|email|inbox)\b|\bwaiting for (?:my |the )?(?:\w+ )?(?:test )?results?\b",
    'nerves': r"|(?=.*\b(?:nervous|anxious|dreading|scared|terrified|petrified|frightened|afraid|worried|panicking|knot in my stomach|(?:stomach|tummy) (?:is )?in knots|can'?t settle|feel(?:ing)? sick|"
              r"shaking|a (?:nervous )?(?:mess|wreck)|butterflies)\b)(?=.*\b(?:test|exam|interview|presentation|speech|audition|first day|appointment|"
              r"operation|surgery|dentist|doctor|hospital|flight|flying|wedding|date|performance|match|race|driving)\b)",
    'leaving': r"|\b(?:emigrat\w+|moved (?:away|abroad|overseas)|moving (?:away|abroad|overseas))\b",
    'child_upset': r"|\b(?:my|our) (?:son|daughter|child|kid|boy|girl|little one|toddler|baby)\b.*\b(?:cries|crying|screams|clings|won'?t settle|nervous|scared|anxious)\b",
    'overwhelmed': r"|\b(?:burn(?:ed|t)[- ]out|can (?:barely|hardly) get out of bed|running on empty|not coping|falling apart)\b",
    'dispute': r"|\b(?:builder|plumber|electrician|roofer|decorator|tradesman|contractor|landlord|garage|mechanic|seller)\b.{0,40}\b(?:never (?:came|turned up|showed|finished|returned)|"
               r"didn'?t (?:come|turn up|show|finish)|took (?:our|my|a|the) (?:money|deposit|payment)|vanished|disappeared|ghosted)\b|\bkept (?:my|our) (?:whole |entire |full )?deposit\b|\b(?:won'?t|doesn'?t|refuses to) (?:answer|reply to|respond to) (?:my )?(?:emails?|calls?|messages?)\b",
}
FRAMES = [(n, re.compile(p.pattern + _EXTRA[n]) if n in _EXTRA else p) for n, p in FRAMES]
PUTTING_OFF = re.compile(r"(?i)\b(?:keep (?:putting|leaving) (?:off |it |things |my \w+ )|(?:putting|leaving) (?:it|things|my \w+(?: \w+)?) (?:off|to the last minute|until the last minute)|"
                         r"procrastinat\w+|can'?t (?:make myself|get myself to|get started on)|last minute)\b")
FRAMES.insert([n for n, _ in FRAMES].index('overwhelmed'), ('putting_off', PUTTING_OFF))

ACK['putting_off'] = "That's really common, and it's rarely laziness: putting something off is usually about the task feeling big or unpleasant."
SECOND['putting_off'] = "The trick is to make starting tiny, because starting is the hard part; carrying on is much easier."
OFFER['putting_off'] = "Would a few ways to get going help?"
NORMAL['putting_off'] = "Yes, very. Almost everyone puts off things that feel big, boring or worrying, and deadlines make it feel worse, not better."
DO['putting_off'] = ["Shrink the first step until it's silly: open the document and write one sentence, or fill in one box.",
                     "Set a timer for 25 minutes and only commit to that; stop when it rings if you want to.",
                     "Phone in another room, and the tabs you don't need closed, before you start.",
                     "Decide the night before exactly what you'll do first, and when.",
                     "Tell someone your deadline, or work alongside a friend: a little company makes it much easier."]
LEAD_DO['putting_off'] = "A few things that help most people get going:"
STUCK_AGAIN = ("Then make the first step even smaller, or change where you work: a library, a café, or alongside someone else, even on a video call. "
               "If you've been stuck for weeks, or can't concentrate on anything, it's worth talking to your GP: that can be stress or low mood rather than laziness.")

ACK['lonely'] = "That sounds hard. Loneliness can creep up on anyone, especially after a change, and it's far more common than people admit."

# kinds of waiting: the advice for an exam result is not the advice for a job, an application or a driving test
WAIT_IF = {}
WAIT_KIND = [('waiting_job', re.compile(r"(?i)\b(?:job|interview|offer letter|employer|recruiter|role|position|hiring)\b")),
             ('waiting_app', re.compile(r"(?i)\b(?:university|uni|college|course|place|offer|flat|house|apartment|mortgage|visa|application|applied|"
                                        r"agent|publisher|editor|manuscript|novel|book|audition|casting|competition|grant|scholarship)\b")),
             ('waiting_test', re.compile(r"(?i)\b(?:driving test|theory test|test result)\b"))]
for k, ack, second, normal, what in [
        ('waiting_job', "Waiting to hear about a job you really want is hard: there's nothing more you can do, so the mind keeps checking.",
         "Silence usually means they're busy or still deciding, not that it's a no.",
         "Yes, completely. Checking your email again and again while you wait for a job reply is very common.",
         "Then it's one no, not a verdict on you. Ask them for feedback (many will tell you what tipped it), keep one or two other applications "
         "going so this isn't the only door, and remember that getting to this stage means they saw something in you."),
        ('waiting_app', "Waiting for an answer on something you really want is hard, especially when it's out of your hands now.",
         "Most decisions take longer than people expect, and the wait itself says nothing about the answer.",
         "Yes. Refreshing your phone and imagining both answers is what nearly everyone does while they wait.",
         "Then you'd still have options: there are usually other places, other rounds or other routes in, and many people get what they want on a "
         "second try. It's worth having a plan B in mind, so a no is a change of route rather than the end of it."),
        ('waiting_test', "Waiting for a test result is nerve-racking, especially when it matters this much to you.",
         "Most people come out sure they did worse than they did; the feeling isn't the result.",
         "Yes, completely. Replaying every moment of a test while you wait is normal.",
         "Then you take it again, and lots of people need more than one go. Ask which faults came up, practise those specifically, and book the "
         "next one when you're consistently doing well; the second attempt is often easier because you know what to expect.")]:
    ACK[k], SECOND[k], NORMAL[k] = ack, second, normal
    WAIT_IF[k] = what
    OFFER[k] = OFFER['waiting']
    DO[k] = ["Decide when you'll check (say twice a day) instead of every few minutes; it stops the wait taking over.",
             "Fill the days with things that need your attention: work, exercise, friends, a film.",
             "Have a plan B in mind: knowing there's a next step whatever happens takes the edge off.",
             "Tell someone you trust that you're waiting, so you're not carrying it alone.",
             "Plan something nice for after you hear, whatever the answer."]
    LEAD_DO[k] = LEAD_DO['waiting']


def waiting_kind(told):
    for k, pat in WAIT_KIND:
        if pat.search(told or ''):
            return k
    return 'waiting'


OPERATION = re.compile(r"(?i)\b(?:operation|surgery|procedure|anaesthetic|anesthetic)\b")

# round g: a situation that is serious in itself claims the turn without a feeling word ("My mum is having heart surgery")
LOVED_ILL = re.compile(r"(?i)\b(?:my|our) (?:mum|mom|mother|dad|father|parents?|husband|wife|partner|son|daughter|child|brother|sister|grandma|grandad|"
                       r"grandmother|grandfather|nan|gran|friend|best friend|aunt|uncle)\b.{0,40}\b(?:is having|has|had|is in|was taken to|went into|"
                       r"(?:has been|was|got) diagnosed|is going in for|is going into|is getting)\b.{0,30}\b(?:surgery|operation|heart|cancer|a stroke|a heart attack|"
                       r"hospital|intensive care|icu|chemo|chemotherapy|tests|dementia|a fall|biopsy|scan)\b")
FRAMES.insert(0, ('loved_ill', LOVED_ILL))
ACK['loved_ill'] = "That's so worrying. When it's someone you love, it's hard to think about anything else, and that's completely natural."
SECOND['loved_ill'] = ("The waiting is often the hardest part. Hospitals do operations like this every day, and the team will check {him} carefully "
                       "before, during and after.")
OFFER['loved_ill'] = "Would it help to think about how to get through the next few days, or how to support {him}?"
NORMAL['loved_ill'] = ("Completely. Worrying constantly about someone you love who's ill or having an operation is what almost everyone feels; it's a "
                       "sign of how much they matter to you.")
DO['loved_ill'] = ["Ask {him} (or the hospital) when and how you'll get news, and who will call whom, so you're not waiting by the phone all day.",
                   "Write down questions for the doctors: what happens next, how long recovery takes, what to watch for.",
                   "Offer practical help rather than \"let me know\": a lift, a meal, sorting the post, visiting at a set time.",
                   "Keep your own basics going: sleep, food, a walk. You'll be more help to {him} if you're not running on empty.",
                   "Share the worry with someone you trust, so you're not carrying it alone."]
LEAD_DO['loved_ill'] = "A few things that help:"
LOVED_IF = ("It's natural to fear that. Most operations like this go as planned, and if anything does come up, the team is right there and "
            "trained for it. Ask the hospital what the realistic risks are; hearing the real picture usually helps more than imagining it. "
            "Whatever happens, you don't have to face it alone: lean on family and friends, and the hospital can tell you about support too.")
SITUATIONAL = {'loved_ill', 'putting_off', 'grief', 'health_wait', 'waiting', 'leaving', 'dispute', 'child_upset', 'setback'}
TELL_KIDS = ("Be honest and simple, using the real words: \"Max died last night. His body stopped working and he can't come back.\" Avoid \"put to "
             "sleep\" or \"went away\", which can confuse or frighten young children. Let them ask questions, tell them it's okay to be sad, and "
             "let them see you're sad too. Something to do helps: drawing a picture, choosing a photo, or planting something in his memory. "
             "Expect questions to come back over the next few days; that's normal.")
FUNERAL = ("Dreading a funeral is very natural: it makes the loss feel real. You don't have to be composed; tears are expected and nobody "
           "will judge you. It can help to know the plan for the day, to sit with someone you're close to, and to have a tissue and some water. "
           "Many people find, afterwards, that it was a chance to say goodbye and to hear stories about {who} that they'd never heard.")


def nerves_extra_what_if(last, told):
    """Worries the general nerves answers don't cover: an operation going wrong, stalling in a driving test."""
    if OPERATION.search(told or '') and re.search(r"(?i)\b(?:go(?:es)? wrong|complications?|don'?t wake up|anaesthetic|anesthetic|pain)\b", last):
        return ("That's one of the most common worries before an operation, and it's worth asking about directly. Serious problems are rare, and the "
                "team does this every day and checks you carefully before, during and after. Write down your questions (what the risks really are, "
                "what recovery looks like, what to tell them about medicines) and ask the surgeon or nurse; hearing the real numbers usually helps "
                "more than imagining them.")
    if re.search(r"(?i)\bdriving test\b", told or '') and re.search(r"(?i)\bstall", last):
        return ("Stalling isn't an automatic fail. Stay calm, put the handbrake on if you need to, check around you, restart and carry on safely; "
                "examiners see it all the time and care much more about how safely you handle it than about the stall itself.")
    return None


FLY = re.compile(r"(?i)\b(?:fly|flying|flight|plane|aeroplane|airplane)\b")


def fly_what_if(last):
    if re.search(r"(?i)\bturbulence|\bbump(?:s|y)\b|\bshak(?:e|ing|y)\b.*\bplane\b", last):
        return ("Turbulence feels alarming but it's normal and safe: it's the plane moving through uneven air, like a boat on small waves. "
                "Planes are built to handle far more than anything you'll feel, and pilots expect it and often fly around the worst of it. "
                "Keep your seatbelt fastened when you're seated, and it helps to watch the cabin crew: if they're calmly walking about, "
                "everything is fine. Breathing out slowly, longer than you breathe in, settles the jolt of adrenaline.")
    if re.search(r"(?i)\bcrash|\bsomething goes wrong\b|\bfall\b|\bengine\b", last):
        return ("It's one of the most common fears, and the numbers are very reassuring: flying is by far the safest way to travel, much safer "
                "per journey than driving to the airport. Every part of the plane has backups, the crew train for years, and a plane can fly "
                "safely on one engine. The noises you'll hear (the landing gear, the engines changing pitch, a thud as wheels go up) are normal.")
    if re.search(r"(?i)\bpanic|\bpanic attack|\bfreak out|\bcan'?t breathe|\btrapped\b", last):
        return ("If panic rises, keep it simple: breathe out slowly, longer than you breathe in, for a minute or two; press your feet into the floor "
                "and name five things you can see. Panic peaks and passes within minutes even if you do nothing. It helps to tell the cabin crew "
                "it's your first flight: they're used to nervous flyers and will check on you. An aisle seat helps if feeling hemmed in worries you.")
    if re.search(r"(?i)\btips\b|\bwhat should i do\b|\bhow (?:do|can) i (?:cope|prepare|stay calm)\b|\bbefore (?:the|my) flight\b", last):
        return ("A few things that help first-time flyers:\n\n"
                "- Arrive early so you're never rushing through security.\n"
                "- Tell the crew it's your first flight; they'll explain the noises and check on you.\n"
                "- Bring something absorbing: a series downloaded, a game, music.\n"
                "- Sip water, chew gum or yawn on take-off and landing to help your ears.\n"
                "- Expect a few bumps and normal noises (engines changing pitch, the landing gear going up), so they don't surprise you.\n"
                "- Many airlines run free or low-cost fear-of-flying courses and apps if you fly often.")
    return None


def interview_question(last):
    if re.search(r"(?i)\bwhy (?:i|did i|you) (?:left|leave|leaving)\b|\b(?:last|previous|old) job\b|\bwhy (?:i'?m|am i) leaving\b", last):
        return ("Then keep it short, honest and forward-looking. Say what you're looking for rather than what was wrong: \"I'd learned a lot there, "
                "and I was ready for more responsibility / a role closer to what I enjoy, which is why this job appeals to me.\" "
                "If you were let go, say so plainly in one sentence and move to what you learned. Never criticise the old employer: it worries interviewers more than the reason itself.")
    if re.search(r"(?i)\bweakness", last):
        return ("Pick a real but manageable weakness and show what you're doing about it: \"I used to take on too much myself; I've learned to "
                "agree priorities early and delegate.\" Avoid fake ones like \"I'm a perfectionist\": interviewers have heard them all.")
    if re.search(r"(?i)\btell (?:me|them|us) about yourself\b|\bintroduce myself\b", last):
        return ("Have a 60-second answer ready: who you are professionally now, one or two things you've done that fit this job, and why you want "
                "this role. Present, past, future. Practise it aloud a few times so it sounds natural, not memorised.")
    if re.search(r"(?i)\bsalary|\bpay\b|\bexpect(?:ed|ations)? (?:to be paid|money)\b", last):
        return ("Research the usual range first (job ads, salary sites). If asked, give a range with your target in the lower-middle of it, or ask "
                "what range they have in mind. It's fine to say you'd like to understand the whole role and benefits first.")
    if re.search(r"(?i)\bgap\b|\bunemployed\b|\btime off\b", last):
        return ("Explain it briefly and positively: what you did with the time (caring for family, study, health, travel, looking for the right "
                "role) and that you're ready now. One or two sentences is plenty.")
    if re.search(r"(?i)\bwhy (?:do )?(?:i|you) want (?:this|the) (?:job|role|position)\b|\bwhy (?:this|their) company\b|"
                 r"\bwhy (?:do )?(?:i|you) want to (?:work|be) (?:there|here|for (?:them|us|the company))\b|\bwhy (?:i|you) applied\b", last):
        return ("Link three things: what the company does that you genuinely like (read their site and news), what the role involves that suits "
                "your strengths, and where you want to grow. Specific beats general.")
    return None


WHAT_IF = re.compile(r"(?i)\bwhat (?:if|happens if|do i do if|should i do if)\b|\bi'?m (?:scared|worried|afraid) (?:that )?(?:i'?ll|i will|my|they'?ll)\b")
TONIGHT = re.compile(r"(?i)\b(?:tonight|this evening|the night before|before bed|before i (?:go to )?sleep|can'?t sleep|night before)\b")


def what_if(frame, last, told):
    """'What if my mind goes blank?', 'What if they ask something I don't know?', 'Any tips for tonight?' before an event;
    'What if I did fail?' while waiting for results."""
    event = re.search(r"(?i)\b(presentation|speech|talk|interview|exam|test|audition|performance|recital|match|race|first day|meeting|operation|surgery|"
                      r"appointment|wedding)\b", told or '')
    ev = event[1].lower() if event else 'it'
    the = f'the {ev}' if ev != 'it' else 'it'
    if frame in ('waiting_job', 'waiting_app', 'waiting_test') and (WHAT_IF.search(last) or re.search(r"(?i)\b(?:say no|reject|don'?t get|didn'?t pass)\b", last)):
        return {'waiting_job': None, 'waiting_app': None, 'waiting_test': None}.get(frame) or WAIT_IF[frame]
    if frame == 'waiting' and WHAT_IF.search(last):
        return ("Then you'd have options, even if it doesn't feel like it now. Most exams can be retaken or the paper re-marked, many courses "
                "and jobs have more than one way in, and schools, colleges and employers deal with this every year. It would be a setback, "
                "not the end of the road. And you don't know yet: it may well have gone better than it feels.")
    if frame == 'putting_off' and re.search(r"(?i)\bstill\b|\bdoes ?n.t work\b|\bcan'?t (?:get going|start)\b", last):
        return STUCK_AGAIN
    if frame != 'nerves':
        return None
    got = nerves_extra_what_if(last, told)
    if got:
        return got
    if DRIVE.search(told or '') and not re.search(r"(?i)\bdriving test\b", told or ''):
        got = drive_what_if(last)
        if got:
            return got
    if FLY.search(told or ''):
        got = fly_what_if(last)
        if got:
            return got
    if ev == 'interview':
        got = interview_question(last)
        if got:
            return got
    if TONIGHT.search(last):
        return (f"A few things for tonight:\n\n"
                f"- Get everything ready now (clothes, bag, documents, route and timings) so the morning is simple.\n"
                f"- Go over your main points once, then stop: last-minute cramming adds worry more than it adds anything you'll remember.\n"
                f"- Eat a normal dinner and go easy on caffeine and alcohol.\n"
                f"- Do something calm that isn't about {the}: a walk, a shower, a familiar programme.\n"
                f"- If you can't sleep, don't fight it: resting quietly still helps, and one short night won't spoil {the}.\n"
                f"- Set two alarms, so you're not lying awake checking.\n\n"
                f"Nearly everyone sleeps a little worse the night before, and they still do fine.")
    if not WHAT_IF.search(last):
        return None
    if re.search(r"(?i)\b(?:blank|forget|forgot|lose my (?:place|train of thought)|freeze|dry up|mind goes)\b", last):
        hold = {'interview': "Saying \"Let me think about that for a moment\" is completely normal in an interview, and interviewers respect it.",
                'exam': "Move on to a question you can do, and come back to it: the answer often returns once you've relaxed."}.get(
            ev, "A pause feels long to you, but to everyone else it looks like you're gathering your thoughts.")
        return (f"It happens to lots of people, and it's recoverable. If your mind goes blank: stop, take one slow breath out, and look at your "
                f"notes or go back to the last thing you said. {hold} It also helps to know your first couple of sentences by heart and to "
                f"have three or four key points on a card, so you always have somewhere to go back to.")
    if re.search(r"(?i)\b(?:don'?t know|can'?t answer|no idea)\b|\b(?:tricky|difficult|hard) question|\bask (?:me )?something\b", last):
        return ("Then say so honestly and show how you'd find out: \"I'm not sure, but here's how I'd approach it.\" Nobody expects you to know "
                "everything, and handling a question you can't answer calmly often impresses more than a perfect answer.")
    if re.search(r"(?i)\b(?:mess(?: it)? up|mistake|get it wrong|say something stupid|stumble|go wrong)\b", last):
        return (f"Then you carry on. People remember how {the} went overall, not one stumble, and most small mistakes aren't even noticed. "
                f"A quick \"sorry, let me put that another way\" and moving on is all it takes.")
    if re.search(r"(?i)\b(?:panic|shake|shaking|cry|sick|blush|sweat)\b", last):
        return ("Then you slow down and breathe out longer than you breathe in for a few breaths; it settles the body quickly. It looks far "
                "less obvious from outside than it feels inside, and a sip of water and a pause are always allowed.")
    return None


def frame_of(users):
    """(frame, the user turn it came from) for the last four user turns, newest first."""
    for t in reversed(users[-4:]):
        hypothetical = re.search(r"(?i)\b(?:what if|if i|in case|might have|may have|could have|scared (?:that )?i|worried (?:that )?i|afraid (?:that )?i)\b", t)
        for name, pat in FRAMES:
            if pat.search(t):
                if hypothetical and name in ('setback', 'self_doubt', 'grief'):
                    continue            # "What if I failed?" is a worry about a result, not a result: an earlier turn says what is happening
                return name, t
    return None, None


def who_died(text):
    m = re.search(r"(?i)\b(?:my|our) (?:old |lovely |little |beloved |dear )?(dog|cat|rabbit|hamster|horse|pet|mum|mom|dad|mother|father|grandma|grandad|"
                  r"grandmother|grandfather|nan|gran|husband|wife|partner|friend|brother|sister)\b", text or '')
    return 'your ' + m[1].lower() if m else 'someone you love'


def pronouns(users):
    text = ' '.join(users)
    if re.search(r"(?i)\b(?:daughter|girl|she|her)\b", text):
        return dict(he='she', him='her', his='her')
    if re.search(r"(?i)\b(?:son|boy|he|him)\b", text):
        return dict(he='he', him='him', his='his')
    return dict(he='they', him='them', his='their')


NEW_SCHOOL = re.compile(r"(?i)\b(?:starts?|starting|start at|going to|moving (?:to|schools?)|new) (?:a )?(?:new |secondary |high |big |middle |primary )?(?:school|nursery|class|college)\b|"
                        r"\bfirst day (?:at|of) (?:school|nursery|secondary|high school)\b|\b(?:secondary|high) school (?:on|next|this|in)\b")


LITTLE = re.compile(r"(?i)\b(?:nursery|preschool|pre-school|kindergarten|daycare|day care|childminder|reception class|toddler|baby)\b|"
                    r"\b(?:cries|crying|screams|clings) (?:every time|when) (?:i|we) (?:leave|drop)")
CHILD['little'] = dict(
    ack="That's so hard, and it's one of the most common things with little ones: crying at goodbyes usually means {he} feels safe with you, not that something is wrong.",
    second="Most young children settle within a few weeks, and staff often say the crying stops a few minutes after the parent has gone.",
    offer="Would it help to think about how to make the goodbyes easier?",
    lead="A few things that help little ones settle:",
    do=["Keep goodbyes short, warm and the same every time: a hug, a phrase, then go. Lingering makes it harder.",
        "Never slip away without saying goodbye; it makes the next drop-off more anxious.",
        "Let {him} take something from home: a small toy or a photo.",
        "Talk about what happens there and that you always come back, and say when in terms {he} understands (\"after lunch\").",
        "Ask the staff to message you once {he}'s settled, and tell them what comforts {him}.",
        "Expect a wobble after holidays or illness; it usually passes quickly."])


def child_kind(users):
    told = ' '.join(users[-3:])
    if LITTLE.search(told):
        return 'little'
    if NEW_SCHOOL.search(told) and not re.search(r"(?i)\b(?:failed|bad (?:mark|result|grade)|test result)\b", told):
        return 'new_school'
    return 'left_out' if LEFT_OUT.search(told) else 'setback'


def claims(messages):
    """True when the Supporter recognises the user's situation (a feeling shown or named, or a situation serious in itself)."""
    users = [m['content'] for m in messages if m.get('role') == 'user' and isinstance(m.get('content'), str)]
    if not users:
        return False
    frame, _ = frame_of(users[-1:])
    if not frame:
        return False
    return frame in SITUATIONAL or bool(FEEL.search(users[-1]) or FEEL2.search(users[-1]) or EMO_EVENT.search(users[-1]))


def respond(messages):
    users = [m['content'] for m in messages if m.get('role') == 'user' and isinstance(m.get('content'), str)]
    if not users:
        return None
    last = users[-1]
    if any(re.search(r"(?i)\b(?:no advice|not? (?:give|giving) (?:me )?advice|don'?t (?:give|offer) (?:me )?(?:any )?advice|don'?t advise|"
                     r"just (?:listen|want to vent)|no (?:questions|suggestions|solutions)|"
                     r"don'?t ask|not looking for (?:advice|solutions)|don'?t try to fix|without giving advice|or quiz me)\b", t) for t in users[-4:]):
        return None                                 # the user has said how they want to be answered: the conversation rules keep that
    felt = any(FEEL.search(t) or FEEL2.search(t) or EMO_EVENT.search(t) or PUTTING_OFF.search(t) for t in users[-4:])
    frame, told = frame_of(users)
    if not frame:
        return None
    if not felt and frame not in SITUATIONAL:
        return None                                 # no feeling (named or shown) and no situation serious in itself: not the Supporter's
    if frame == 'loved_ill':
        p0 = pronouns([told])
        if WHAT_IF.search(last) or re.search(r"(?i)\b(?:doesn'?t|does not) go well\b|\bgoes wrong\b", last):
            return dict(route='chat/support', response=LOVED_IF, sources=[], details='The Supporter: a worry about someone ill (support.py).')
    if frame == 'grief' and re.search(r"(?i)\btell (?:the |my |our )?(?:kids|children|son|daughter|little ones)\b", last):
        return dict(route='chat/support', response=TELL_KIDS, sources=[], details='The Supporter: telling children about a death (support.py).')
    if frame == 'grief' and re.search(r"(?i)\bfuneral\b", last):
        return dict(route='chat/support', response=FUNERAL.format(who=who_died(' '.join(users))), sources=[],
                    details='The Supporter: a funeral ahead (support.py).')
    if frame == 'overwhelmed' and len(users) == 1 and not last.strip().endswith('?') and not FEEL.search(last):
        return None                                 # a first "I'm burned out": the reflective responder opens; the Supporter goes on from there
    if frame == 'waiting':
        frame = waiting_kind(' '.join(users[-4:]))  # a job, an application or a test is not an exam result
    if re.search(r"(?i)\b(?:\d+\s*[%$£€]|\$\s?\d|how much (?:is|do|does|should|will)|calculate|percent)\b", last) and not ASK_DO.search(last):
        return None                                 # a sum, even in an emotional conversation: the Calculator's
    asked = last.strip().endswith('?')
    p = pronouns(users)
    child = CHILD[child_kind(users)] if frame == 'child_upset' else None

    def fill(x):
        return x.format(who=who_died(told), her=p['him'], **p)

    if asked and frame in ('nerves', 'waiting', 'waiting_job', 'waiting_app', 'waiting_test', 'putting_off'):
        got = what_if(frame, last, told)
        if got:
            return dict(route='chat/support', response=got, sources=[], details=f'The Supporter: a worry or the night before, in a "{frame}" situation (support.py).')
    if asked and ASK_NORMAL.search(last):
        return dict(route='chat/support', response=NORMAL[frame], sources=[], details=f'The Supporter: is it normal, in a "{frame}" situation (support.py).')
    if asked and (ASK_DO.search(last) or ASK_HELP_OTHER.search(last)):
        items, lead = (child['do'], child['lead']) if child else (DO[frame], LEAD_DO[frame])
        said = ' '.join(m.get('content') or '' for m in messages[:-1] if m.get('role') == 'assistant')
        fresh = [x for x in items if fill(x)[:50] not in said]
        if len(fresh) >= 2 and len(fresh) < len(items):
            items, lead = fresh, ("A few more things that help:" if frame != 'dispute' else lead)
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
        if child is CHILD['new_school']:
            reflect = (f"That fear makes sense: it's the biggest worry for most children starting somewhere new, and it usually fades within the "
                       f"first week or two, once {p['he']} has a familiar face or two.")
        if frame == 'health_wait':
            reflect = "That's so understandable. When there's nothing to do but wait, the mind runs straight to the worst case."
        if child is CHILD['left_out']:
            reflect = f"Coming home in tears again is a sign it's really getting to {p['him']}, and it's good {p['he']} can bring it to you."
        text = f"{reflect} Two things that often help straight away:\n\n- {fill(items[0])}\n- {fill(items[1])}\n\nWould you like a few more ideas?"
        return dict(route='chat/support', response=text, sources=[], details=f'The Supporter: more told in a "{frame}" situation (support.py).')
    return dict(route='chat/support', response=f"{ack} {second} {offer}", sources=[], details=f'The Supporter: a feeling told in a "{frame}" situation (support.py).')
