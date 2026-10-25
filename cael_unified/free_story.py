"""Short stories about any subject from hand-written story arcs, used when the trained story engine cannot handle
the request ("Tell me a short story about a dragon"). Never a neural model.

The subject comes from the request ("a dragon", "my cat Luna", "a robot who loves music"); a setting is chosen from
words in it (dragon -> mountains, robot -> city, fish -> sea ...); one of several arcs (a lost thing, a new friend, a
fear faced, a skill learned, a kindness repaid) is filled in with those slots. The seed picks the arc and details.
"""
import random
import re

ASK = re.compile(r"(?i)^\s*(?:please\s+)?(?:can you\s+|could you\s+)?(?:tell|write|make up|give)\s+(?:me\s+)?(?:a|an|one)?\s*"
                 r"(?:short\s+|little\s+|quick\s+|funny\s+|bedtime\s+|cute\s+|nice\s+|happy\s+|sad\s+|scary\s+)*"
                 r"(?:story|storie|storey|stroy|tale|fable)\s+(?:about|of|with|where)\s+(.+?)\s*[.!?]*$")

SETTINGS = [
    (r'dragon|knight|princess|prince|castle|wizard|witch|king|queen|giant', 'a castle on a misty mountain', 'the mountain path'),
    (r'robot|computer|car|train|city|alien|astronaut|rocket|space', 'a busy city full of lights', 'the old tower at the edge of town'),
    (r'fish|whale|shark|dolphin|octopus|pirate|ship|boat|mermaid|turtle|crab|sea', 'a bright coral reef', 'the deep blue water'),
    (r'bird|owl|eagle|butterfly|bee|bug|ant', 'a tall oak tree', 'the windy hill'),
    (r'cat|dog|puppy|kitten|mouse|rabbit|bunny|hamster|pet', 'a small house with a garden', 'the end of the garden'),
    (r'bear|fox|wolf|deer|lion|tiger|elephant|monkey|giraffe|squirrel', 'a green forest', 'the river at the edge of the forest'),
    (r'farm|cow|pig|horse|sheep|goat|chicken|duck', 'a sunny farm', 'the far field'),
    (r'snow|winter|penguin|polar', 'a snowy valley', 'the frozen lake'),
]
ARCS = [
    ['Once upon a time, {who} lived in {place}.',
     'One morning, {pron} discovered that {poss} favourite {thing} was gone.',
     '{Pron} searched everywhere, all the way to {far}, asking everyone {pron} met for help.',
     'At last, a small voice pointed the way, and there it was, safe and sound.',
     'From that day on, {who_short} took better care of the things {pron} loved, and never forgot the friend who helped.'],
    ['In {place}, there lived {who}, who often felt a little lonely.',
     'One day, {pron} noticed someone new sitting alone near {far}.',
     '{Pron} gathered all {poss} courage and said hello.',
     'They spent the whole afternoon laughing and exploring together.',
     'By sunset, {who_short} had found something better than any treasure: a true friend.'],
    ['{Who_cap} lived in {place}, and there was one thing {pron} feared more than anything: {fear}.',
     'One stormy evening, a friend needed help, and the only way was past {far}.',
     '{Pron} took a deep breath, remembered that brave does not mean unafraid, and went anyway.',
     'Step by step, the fear grew smaller, until {pron} reached {poss} friend.',
     'After that night, {who_short} still felt nervous sometimes, but {pron} knew {pron} could be brave.'],
    ['{Who_cap} lived in {place} and dreamed of learning to {skill}.',
     'The first try went badly. So did the second, and the tenth.',
     'Instead of giving up, {pron} practised a little every day near {far}.',
     'One bright morning, it finally worked, and everyone cheered.',
     '{Who_short_cap} smiled, because the hard days had made the good one possible.'],
    ['In {place}, {who} found a tiny creature stuck and shivering near {far}.',
     '{Pron} gently helped it free and kept it warm until it was strong again.',
     'Weeks later, {who_short} got lost on the way home as night fell.',
     'Suddenly, a familiar little glow appeared and led the way back.',
     'Kindness, {who_short} learned, has a way of finding its way home.'],
]
THINGS = ['red scarf', 'shiny stone', 'old map', 'golden key', 'blue kite', 'lucky coin', 'little drum']
FEARS = ['the dark', 'thunder', 'deep water', 'tall heights', 'loud noises']
SKILLS = ['fly', 'sing', 'dance', 'swim', 'paint', 'read', 'whistle']


def subject(text):
    m = ASK.match(text)
    if not m:
        return None
    who = m.group(1).strip()
    who = re.sub(r'(?i)^(?:a|an|the)\s+', lambda x: x.group(0).lower(), who)
    if not re.match(r'(?i)(?:a|an|the|my|our|his|her|their|two|three|some)\b|[A-Z]', who):
        who = ('an ' if who[:1].lower() in 'aeiou' else 'a ') + who
    return who if len(who.split()) <= 10 else None


def story(text, seed=0):
    who = subject(text)
    if not who:
        return None
    rng = random.Random(seed + len(who))
    low = who.lower()
    place, far = next(((p, f) for pattern, p, f in SETTINGS if re.search(pattern, low)), ('a quiet little village', 'the old bridge'))
    short = re.sub(r'(?i)^(?:a|an)\s+', 'the ', who.split(' who ')[0].split(' that ')[0].split(' with ')[0])
    plural = bool(re.match(r'(?i)(?:two|three|some)\b', who)) or re.search(r'\band\b', who)
    pron, poss = ('they', 'their') if plural else ('she', 'her') if re.search(r'(?i)\b(?:girl|princess|queen|mother|mom|sister|witch|lady|woman)\b', who) \
        else ('he', 'his') if re.search(r'(?i)\b(?:boy|prince|king|father|dad|brother|man|knight)\b', who) else ('it', 'its') \
        if re.search(r'(?i)\b(?:robot|car|train|rocket|computer)\b', who) else ('they', 'their')
    arc = rng.choice(ARCS)
    slots = dict(who=who, who_short=short, Who_cap=who[0].upper() + who[1:], Who_short_cap=short[0].upper() + short[1:],
                 place=place, far=far, pron=pron, Pron=pron.capitalize(), poss=poss, thing=rng.choice(THINGS),
                 fear=rng.choice(FEARS), skill=rng.choice(SKILLS))
    body = ' '.join(line.format(**slots) for line in arc)
    if pron == 'they' and not plural:
        body = body.replace('they was', 'they were').replace('they has', 'they have')
    body = re.sub(r'\b(they|They) (feared|lived|dreamed|noticed|took|found|discovered|searched|gathered|smiled)\b', r'\1 \2', body)
    return dict(route='chat/story-free', response='Story:\n' + body, sources=[],
                details='A short story from hand-written story arcs with your subject filled in (the trained story engine '
                        'does not cover this subject). No neural model.')
