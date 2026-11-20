"""Everyday requests that other desks got wrong (0.4.4): jokes, a recipe step said on its own, common myths, and a bare
"Why?" after a short factual answer.

All of it is authored rules and a small table; nothing is learned, and nothing here looks anything up.
"""
import re

from . import smalltalk

JOKE_ASK = re.compile(r"(?i)^\s*(?:(?:thanks|thank you|thx|cheers|great|cool|ok|okay|nice|haha|lol)[!.,]*\s+)*"
                      r"(?:(?:can|could|would|will) you\s+|please\s+)?(?:tell|give|say)\s+(?:me|us)?\s*(?:a|another|one more|some|your best)\s+"
                      r"(?:good\s+|funny\s+|short\s+|silly\s+|bad\s+|dad\s+)?(?:joke|pun)s?(?:\s+please)?\s*[?!.]*\s*$|"
                      r"^\s*(?:(?:thanks|thank you)[!.,]*\s+)?(?:make me laugh|do you know (?:a|any) (?:good )?jokes?|i (?:want|need) a joke)\s*[?!.]*\s*$")
AGAIN = re.compile(r"(?i)^\s*(?:(?:haha|lol|ha)[!.,]*\s+)?(?:another(?: one)?|one more|tell me another(?: one)?|more|again|"
                   r"another joke|got (?:any )?more|any more)\s*[?!.]*\s*$")
MORE_JOKES = [
    "I told my computer I needed a break. It said: no problem, it will go to sleep.",
    "Why did the maths book look sad? It had too many problems.",
    "What do you call a sleeping dinosaur? A dino-snore.",
    "Why did the tomato blush? It saw the salad dressing.",
    "What do you call cheese that isn't yours? Nacho cheese.",
    "Why do bees have sticky hair? Because they use honeycombs.",
    "Why did the golfer bring two pairs of trousers? In case he got a hole in one.",
    "What did the ocean say to the beach? Nothing, it just waved.",
]
ALL_JOKES = list(smalltalk.JOKES) + MORE_JOKES


def joke(messages):
    users = [m.get('content') or '' for m in messages if m.get('role') == 'user']
    said = [m.get('content') or '' for m in messages if m.get('role') == 'assistant']
    last = users[-1] if users else ''
    told = [j for j in ALL_JOKES if any(j in s for s in said)]
    if JOKE_ASK.match(last) or (AGAIN.match(last) and told and said and any(j in said[-1] for j in ALL_JOKES)):
        fresh = [j for j in ALL_JOKES if j not in told] or ALL_JOKES
        pick = fresh[sum(map(len, users)) % len(fresh)]
        lead = 'Sure! ' if re.match(r'(?i)\s*(?:thanks|thank you|thx|cheers)', last) else ''
        if not fresh or len(told) >= len(ALL_JOKES):
            lead = "That's all my best ones, so here's one again: "
        return dict(route='chat/joke', response=lead + pick, sources=[],
                    details='An authored joke, not one told before in this chat (common_asks.py).')
    return None


STEP_VERBS = (r'add|stir|mix|whisk|chop|dice|slice|fry|boil|simmer|bake|roast|grill|season|pour|knead|fold|blend|drain|'
              r'peel|grate|heat|preheat|cover|leave|let it|serve|sprinkle|toss|melt|beat|cream|rinse|marinate|sear|reduce')
KITCHEN = re.compile(r"(?i)\b(?:salt|pepper|oil|butter|flour|sugar|water|eggs?|onions?|garlic|sauce|pan|pot|oven|heat|dough|pasta|"
                     r"rice|milk|cream|cheese|mixture|batter|stock|vegetables|veg|meat|chicken|beef|mince|tomato(?:es)?|herbs|spices|"
                     r"lemon|juice|vinegar|wine|bowl|tray|tin|minutes|mins|until (?:golden|soft|brown|thick|smooth|boiling)|"
                     r"carrots?|potato(?:es)?|beans|lentils|tofu|fish|noodles|chocolate|yeast|honey|cinnamon|ginger|mushrooms?)\b")
STEP = re.compile(r"(?i)^\s*(?:(?:then|now|next|and|after that|finally|ok|okay)[,\s]+)*(?:" + STEP_VERBS + r")\b[^?]{0,80}[.!]?\s*$")


def recipe_step(messages):
    """'Then add some salt and stir.' said on its own: the person is cooking, not telling us something about their day."""
    users = [m.get('content') or '' for m in messages if m.get('role') == 'user']
    last = users[-1].strip() if users else ''
    if not STEP.match(last) or len(last.split()) > 16 or not KITCHEN.search(last) or re.search(r'\d+\s*(?:and|\+|to)\s*\d+', last):
        return None
    step = re.sub(r'(?i)^\s*(?:(?:then|now|next|and|after that|finally|ok|okay)[,\s]+)*', '', last).rstrip('.! ')
    step = step[:1].lower() + step[1:]
    return dict(route='chat/recipe-step', sources=[],
                response=f'Got it: {step}. Are you following a recipe? Tell me what you are making and I can help with the next step, '
                         'the timing or the amounts.',
                details='A cooking step said on its own (common_asks.py).')


# Common beliefs that are false, each with the short true answer. Written from general knowledge.
MYTHS = [
    (r'\ball swans\b.{0,20}\bwhite\b|\bswans?\b.{0,20}\balways white\b|\bare there black swans\b',
     "**No.** Most swans in Europe and North America are white, but the black swan is native to Australia, and the black-necked "
     "swan lives in South America. Europeans assumed all swans were white until black swans were recorded in Australia in 1697, "
     "which is why a 'black swan' came to mean a surprise that breaks a rule everyone took for granted."),
    (r'\bgoldfish\b.{0,40}\b(?:memory|remember|forget)\b',
     "**No.** Goldfish remember things for months, not three seconds. They can be trained to respond to sounds, colours and "
     "feeding times."),
    (r'\bbulls?\b.{0,30}\b(?:red|colour|color)\b',
     "**No.** Bulls are red-green colour-blind. In a bullfight they charge the cape because of its movement, not its colour."),
    (r'\b(?:great wall)\b.{0,40}\b(?:space|moon|orbit)\b',
     "**No.** The Great Wall is very long but only a few metres wide, so it is not visible to the naked eye from the Moon, and "
     "astronauts in low orbit say it is very hard or impossible to pick out without help."),
    (r'\blightning\b.{0,30}\b(?:never|twice|same place)\b',
     "**No.** Lightning often strikes the same place more than once, especially tall, pointed things: the Empire State Building is "
     "hit about 20 to 25 times a year."),
    (r'\b(?:only )?(?:use|using)\b.{0,10}\b10 ?(?:%|percent)\b.{0,20}\bbrains?\b|\b10 ?(?:%|percent) of (?:our|the|your) brains?\b',
     "**No.** People use virtually all of their brain. Scans show activity across the whole brain over a day, and damage to almost "
     "any part causes problems."),
    (r'\bbats?\b.{0,20}\bblind\b',
     "**No.** Bats can see. Many also use echolocation to hunt in the dark, and fruit bats have good eyesight."),
    (r'\b(?:hair|nails?)\b.{0,40}\b(?:grow|keep growing)\b.{0,30}\b(?:after death|after (?:you|they|we|people) die|dead)\b',
     "**No.** Hair and nails don't grow after death. The skin dries and pulls back, which makes them look longer."),
    (r'\bsugar\b.{0,40}\b(?:hyper|hyperactive|hyperactivity)\b',
     "**No.** Controlled studies have not found that sugar makes children hyperactive. The excitement of parties, where children "
     "eat a lot of sugar, is the more likely cause."),
    (r'\bcrack\w*\b.{0,20}\bknuckles?\b.{0,40}\barthritis\b',
     "**No.** Cracking your knuckles has not been shown to cause arthritis. The sound is a gas bubble in the joint fluid."),
    (r'\bostrich\w*\b.{0,40}\bbur(?:y|ies)\b.{0,20}\bheads?\b',
     "**No.** Ostriches don't bury their heads in sand. They lower their heads to the ground to turn their eggs or to hide, which "
     "may have started the story."),
    (r'\bchameleons?\b.{0,40}\b(?:camouflage|blend in|match)\b',
     "**Not mainly.** Chameleons change colour mostly to signal mood and to control their temperature, not to match their "
     "background."),
]
MYTHS = [(re.compile('(?i)' + p), a) for p, a in MYTHS]
ASKS_IF_TRUE = re.compile(r"(?i)\b(?:is it true|true that|is it a myth|myth that|do|does|did|are|is|can|really)\b|\?\s*$")


def myth(messages):
    users = [m.get('content') or '' for m in messages if m.get('role') == 'user']
    last = users[-1].strip() if users else ''
    if not last or len(last) > 200 or not ASKS_IF_TRUE.search(last):
        return None
    for pattern, answer in MYTHS:
        if pattern.search(last):
            return dict(route='chat/myth', response=answer, sources=[], details='A common belief that is false (common_asks.py table).')
    return None


WHY_ALONE = re.compile(r"(?i)^\s*(?:but\s+|and\s+|so\s+)?(?:why|how come|why is that|why's that)\s*\??\s*$")
FACT = re.compile(r"^\s*(?:The\s+)?(.+?)\s+of\s+(.+?)\s+(?:is|was|are)\s+\*\*(.+?)\*\*")


def why_question(messages):
    """'Why?' after 'The capital of Italy is **Rome**.' becomes 'Why is Rome the capital of Italy?', the question the person
    means, so it is looked up on its own."""
    users = [m for m in messages if m.get('role') == 'user']
    said = [m.get('content') or '' for m in messages if m.get('role') == 'assistant']
    if len(users) < 2 or not said or not WHY_ALONE.match(users[-1].get('content') or ''):
        return None
    m = FACT.match(said[-1])
    if not m:
        return None
    what, of, value = m[1].strip(), m[2].strip(), m[3].strip()
    return f'Why is {value} the {what.lower()} of {of}?'


def respond(messages):
    for desk in (joke, recipe_step, myth):
        got = desk(messages)
        if got is not None:
            return got
    return None


def why_checked(meant, answered):
    """Keep the answer to 'Why is Rome the capital of Italy?' only when it is about Rome or Italy: a quote from a thread on
    something else ("the two closest capital cities") is worse than saying there is no good source."""
    m = re.match(r'Why is (.+?) the (.+?) of (.+?)\?$', meant)
    if not m:
        return answered
    value, what, of = m[1], m[2], m[3]
    text = str(answered.get('response') or '')
    route = str(answered.get('route') or '')
    source = re.search(r'(?im)^Source:\s*(.+)$', text)
    title = source[1] if source else ''
    about = re.search(r'(?i)\b(?:' + re.escape(value) + '|' + re.escape(of) + r')\b', title)
    trusted = route.startswith(('chat/concept', 'chat/core-', 'chat/web-checked', 'chat/web-exact'))
    if about or (trusted and re.search(r'(?i)\b' + re.escape(value) + r'\b', text)):
        return answered
    return dict(route='chat/why-no-source', sources=[], replaced_route=route,
                response=f"I don't have a reliable source on why {value} is the {what} of {of}: what I found was about something "
                         f"else, so I'd rather not guess. The history of {of} would be the place to look; ask me about it and I'll search.",
                details='The looked-up answer was not about the thing asked (common_asks.why_checked).')
