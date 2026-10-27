import sys, os
sys.path.insert(0, os.getcwd())
import json, random, re
from data1 import *

rnd = random.Random(2024)

FILLER = """Ugh, the weather has been so grey lately.
I just made a huge pot of coffee.
Have you ever tried those sourdough kits?
My internet kept dropping out this morning.
I think I need a new pair of running shoes.
Honestly I could sleep for a week.
There's a street market near my place on weekends.
I've been binge-watching a baking show.
Do you ever get songs stuck in your head?
The bus was packed this morning.
I finally cleaned out the junk drawer.
It smells like rain outside.
I can't decide what to cook tonight.
My favourite mug has a chip in it now.
I've been trying to drink more water.
The neighbours are doing some drilling again.
I watched a documentary about octopuses.
Someone left a bouquet on our doorstep.
I need to defrost the freezer at some point.
I tried a new type of tea today.
The sunset looked amazing yesterday.
My back is a bit sore from sitting.
I keep losing my reading glasses.
There was a funny video going around the office.
I'm thinking of getting a houseplant.
Traffic was awful on the way home.
I love the smell of fresh bread.
The cinema near me is showing old classics.
I spent ages looking for my umbrella.
My laptop fan is really loud lately.
I had the strangest dream last night.
I'm craving something sweet right now.
It's so quiet in the house this evening.
I dropped my toast butter side down, of course.
I might take a nap in a bit.
The elevator in my building is slow.
I found an old mixtape in a box.
Do you think pineapple belongs on pizza?
I'm trying to get into podcasts.
The park was full of kids and kites.
I just heard thunder far away.
My socks never match, it's a mystery.
I keep meaning to tidy up the balcony.
That new cafe has really comfy chairs.
I read half a magazine at the dentist.
The radiator is making clanking noises.
I should probably do some laundry.
There was a rainbow over the roofs earlier.
I've had a really long day.
My playlist is mostly acoustic stuff lately.
The cat from next door keeps visiting our window.
I think my plant is thirsty.
I had a surprisingly good sandwich at lunch.
The wind knocked over our recycling bin.
I'm planning a lazy afternoon.
My fingers are freezing today.
I tried juggling oranges and failed.
The air feels so fresh after the storm.
I keep forgetting to charge my earbuds.
We ran out of milk again.
A pigeon walked right into the shop.
The streetlight outside keeps flickering.
I love a good crossword on a slow morning.
My shoulders feel so tense.
The coffee machine at work is broken again.
I'm in the mood for a long walk.
Someone was playing the trumpet downstairs.
I never remember where I put the scissors.
I saw a squirrel carrying a whole bread roll.
The hallway light bulb just went out.
I'd love to learn how to bake pies properly.
It's strangely warm for this time of year.
The library had a sale on old paperbacks.
I'm trying out a new notebook system.
My phone battery drains so fast these days.
I could really go for some soup.
A parade went past the window earlier.
I tried to whistle a tune and failed.
I keep hitting snooze way too often.
There's a lovely smell coming from the bakery.
I need a haircut at some point.
The washing machine made a weird noise.
I love how quiet it is after midnight.
It took ages to find a parking space.
I put on some jazz while I work.
Do you like board games?
My eyes are tired from the screen.
The pavement is still wet from earlier.
I overslept a little today.
I saw a really nice poster downtown.
We should repaint the fence sometime.
I can't believe how fast this month is going.
I need to buy stamps.
The delivery guy waved at me today.
I have the tune of an old ad stuck in my head.
Somebody was flying a drone over the park.
I'm going to try making my own granola.
The microwave beeps far too loudly.
My bike tyre is a little flat.
The news was all about a giant pumpkin.
I've been feeling nostalgic for old cartoons.
I stirred sugar into my tea twice.""".strip().split("\n")

ASSIST = ["Okay.", "Got it.", "Interesting!", "Sure.", "Sounds fun.", "I see.", "Right.", "Ha, fair enough.", "Oh nice.", "Mm-hm.",
          "That makes sense.", "Alright.", "Oh really?", "Cool.", "Understood.", "Yeah.", "Noted.", "Ah, I see.", "Fair.", "Hmm, okay.",
          "That sounds good.", "Of course.", "Nice.", "Oh, wow.", "Sure thing.", "I hear you.", "Lovely.", "Fine by me.", "Gotcha.", "Oh dear."]


def norm_any(a):
    return [g if isinstance(g, list) else [g] for g in a]


def words_in(text, s):
    return re.search(r"(?<!\w)" + re.escape(s) + r"(?!\w)", text, re.I) is not None


def build(idx, cid, cat, feat, facts, q, anyl, none, longitem, **flags):
    feats = set()
    m = {"n": "negation", "p": "passive", "i": "indirect", "u": "unusual_structure", "m": "multistep", "r": "paraphrase"}
    for ch in feat:
        feats.add(m[ch])
    anyn = norm_any(anyl)
    crit_strings = [s for g in anyn for s in g] + list(none)
    allfacts = " ".join(facts) + " " + q
    avail = [f for f in FILLER if not any(words_in(f, s) for s in crit_strings)]
    nu = rnd.randint(21, 25) if longitem else rnd.randint(3, 8)
    if not longitem:
        nu = max(nu, len(facts) + 2)
    if longitem:
        feats.add("long")
    fillers = rnd.sample(avail, nu - len(facts))
    pos = sorted(rnd.sample(range(nu), len(facts)))
    users = []
    fi = iter(facts)
    fl = iter(fillers)
    for i in range(nu):
        users.append(next(fi) if i in pos else next(fl))
    hist = []
    last = None
    for u in users:
        hist.append({"role": "user", "content": u})
        a = rnd.choice([x for x in ASSIST if x != last])
        last = a
        hist.append({"role": "assistant", "content": a})
    crit = {"any": anyn, "none": list(none), "clarify": flags.get("clarify", False),
            "no_clarify": flags.get("no_clarify", False), "abstain": flags.get("abstain", False)}
    return {"id": f"ind-{cat}-{idx:03d}", "category": cat, "features": sorted(feats), "history": hist, "question": q, "criteria": crit}


items = []
counter = 0


def is_long():
    global counter
    counter += 1
    return counter % 10 == 0


def add(cat, rows, n, **flags):
    for k, r in enumerate(rows[:n]):
        feat, facts, q, anyl, none = r[0], r[1], r[2], r[3], r[4]
        items.append(build(k + 1, cat, feat, facts, q, anyl, none, is_long(), **flags))


# fix arg order: build(idx, cid, cat, ...) -> simplify
def build_wrap(*a, **k):
    pass


def add(cat, rows, n, **flags):  # noqa
    for k, r in enumerate(rows[:n]):
        feat, facts, q, anyl, none = r[0], r[1], r[2], r[3], r[4]
        items.append(build(k + 1, None, cat, feat, facts, q, anyl, none, is_long(), **flags))


add("memory", MEMORY, 45)
add("update", UPDATE, 45)
add("reference", REFERENCE, 40)
# conflict
k = 0
for r in CONFLICT_TRUE[:25]:
    k += 1
    feat, facts, q, anyl = r
    items.append(build(k, None, "conflict", feat, facts, q, anyl, [], is_long(), clarify=True))
for r in CONFLICT_CTRL[:15]:
    k += 1
    items.append(build(k, None, "conflict", r[0], r[1], r[2], r[3], r[4], is_long(), no_clarify=True))
add("planning", PLANNING, 40)
add("reasoning", REASONING, 45)
for k, r in enumerate(UNSUPPORTED[:45]):
    items.append(build(k + 1, None, "unsupported", r[0], r[1], r[2], [], r[3], is_long(), abstain=True))

with open("questions.jsonl", "w", encoding="utf-8") as f:
    for it in items:
        f.write(json.dumps(it, ensure_ascii=False) + "\n")
print(len(items))
