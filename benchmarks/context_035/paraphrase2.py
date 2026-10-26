"""Second post-freeze set (round 2): 100 questions in wording families written AFTER the round-2 parser freeze.

    python paraphrase2.py   -> fresh2.jsonl

fresh.jsonl became a declared development set in round 2 (its failures were used to generalise the parser), so this
set is the blind check for round 2: new sentence frames, new plans, run once, nothing tuned on it.
"""
import json
import random
from pathlib import Path

from generate import CITIES, DAYS, FOODS, JOBS, OBJECTS, Builder

HERE = Path(__file__).resolve().parent
COLOURS = ['red', 'blue', 'green', 'yellow', 'black', 'white', 'silver', 'purple']


def pick(b, options):
    return b.rng.choice(options)


def memory(b):
    used = set()
    a, c = b.person(used), b.person(used)
    kind = b.rng.choice(['home', 'job', 'pet', 'colour', 'food', 'object', 'date'])
    if kind == 'home':
        x, y = b.rng.sample(CITIES, 2)
        return ([pick(b, [f'{a} has been living in {x} for three years.', f'{a}\'s flat is in {x}.', f'{a} works remotely from {x}, where {a} lives.']),
                 pick(b, [f'{c} spent a weekend in {y}.', f'{c} once visited {y}.'])],
                pick(b, [f'Remind me which city {a} lives in?', f'Where is {a} based?', f'Which city does {a} call home?']), dict(any=[[x]], none=[y]))
    if kind == 'job':
        j, k = b.rng.sample(JOBS, 2)
        return ([pick(b, [f'{a} is employed as a {j} at the hospital.', f'{a} got hired as a {j} last month.', f'{a} earns a salary as a {j}.']),
                 pick(b, [f'{c} dreams of becoming a {k}.', f'{c} might train as a {k}.'])],
                pick(b, [f'What is {a}\'s profession?', f'What was {a} hired as?', f'What job does {a} have?']), dict(any=[[j]], none=[k]))
    if kind == 'pet':
        animal, name = b.rng.choice([('dog', 'Bruno'), ('cat', 'Simba'), ('hamster', 'Peanut'), ('parrot', 'Rio'), ('rabbit', 'Clover')])
        return ([pick(b, [f'There is a {animal} at {a}\'s place called {name}.', f'{a} named the new {animal} {name}.', f'{a}\'s {animal} answers to {name}.'])],
                pick(b, [f'What is {a}\'s {animal} named?', f'Tell me the name of {a}\'s {animal}.', f'What did {a} call the {animal}?']), dict(any=[[name]], none=[]))
    if kind == 'colour':
        col, other = b.rng.sample(COLOURS, 2)
        thing = b.rng.choice(['car', 'bike', 'van'])
        return ([pick(b, [f'{a}\'s new {thing} is painted {col}.', f'{a} showed up in a {col} {thing}.', f'The {thing} {a} bought is {col}.']),
                 pick(b, [f'{c} has a {other} {thing}.', f'{c}\'s {thing} is {other}.'])],
                pick(b, [f'Which colour is {a}\'s {thing}?', f'What color is the {thing} {a} owns?', f'{a}\'s {thing}: what color is it?']),
                dict(any=[[col]], none=[other]))
    if kind == 'food':
        f, g = b.rng.sample(FOODS, 2)
        return ([pick(b, [f'{a} orders {f} every single time.', f'{a} says {f} is the best thing ever.', f'Give {a} some {f} and {a} is happy.']),
                 pick(b, [f'{c} is not a fan of {g}.', f'{c} ate {g} once.'])],
                pick(b, [f'What does {a} always order?', f'What is {a}\'s go-to food?', f'What food would make {a} happy?']), dict(any=[[f]], none=[]))
    if kind == 'object':
        obj, spots = b.rng.choice(OBJECTS)
        spot = b.rng.choice(spots)
        be = 'are' if obj.endswith('s') else 'is'
        return ([pick(b, [f'My {obj} {be} on top of the {spot}.', f'I tucked my {obj} into the {spot}.', f'The {obj} {be} in the {spot}, I think.'])],
                pick(b, [f'Where {be} my {obj} again?', f'Where did I tuck the {obj}?', f'Do you know where the {obj} {be}?']), dict(any=[[spot]], none=[]))
    day = b.rng.choice(DAYS)
    return ([pick(b, [f'Lunch with {a} is set for {day}.', f'{a} and I have a coffee date on {day}.', f'{a} booked a table for us on {day}.'])],
            pick(b, [f'When is lunch with {a}?', f'Which day am I seeing {a}?', f'When do I see {a}?']), dict(any=[[day]], none=[]))


def reference(b):
    used = set()
    kind = b.rng.choice(['person', 'puppy', 'group'])
    if kind == 'person':
        female = b.rng.random() < 0.5
        a = b.person(used, female)
        rel = b.rng.choice(['sister', 'niece', 'aunt']) if female else b.rng.choice(['brother', 'nephew', 'uncle'])
        pr = 'She' if female else 'He'
        job, city = b.rng.choice(JOBS), b.rng.choice(CITIES)
        facts = [pick(b, [f'I want you to meet my {rel}, {a}.', f'My {rel} {a} is visiting next month.']),
                 pick(b, [f'{pr} is a {job} by training.', f'{pr} works full time as a {job}.']),
                 pick(b, [f'{pr} recently moved to {city}.', f'{pr} settled in {city} last year.'])]
        if b.rng.random() < 0.5:
            return facts, pick(b, [f'Where did my {rel} move?', f'Which city is my {rel} living in?']), dict(any=[[city]], none=[])
        return facts, pick(b, [f'What is my {rel} by training?', f'What does my {rel} work as?']), dict(any=[[job]], none=[])
    if kind == 'puppy':
        pet, food = b.rng.choice(['Teddy', 'Ollie', 'Pepper', 'Juno']), b.rng.choice(['carrots', 'cheese', 'chicken'])
        facts = [pick(b, ['Our new puppy arrived today.', 'We picked up a puppy from the shelter.']),
                 pick(b, [f'His name is {pet}.', f'We decided to call him {pet}.']),
                 pick(b, [f'He goes crazy for {food}.', f'He begs for {food} all day.'])]
        if b.rng.random() < 0.5:
            return facts, pick(b, ['What is the puppy called?', 'What name did we give the puppy?']), dict(any=[[pet]], none=[])
        return facts, pick(b, [f'What does {pet} beg for?', f'What food does {pet} love?']), dict(any=[[food]], none=[])
    a, c = b.person(used), b.person(used)
    city, day = b.rng.choice(CITIES), b.rng.choice(DAYS)
    facts = [pick(b, [f'{a} and {c} are off on a road trip.', f'{a} and {c} are taking a short holiday.']),
             pick(b, [f'They are driving to {city}.', f'They will end up in {city}.']),
             pick(b, [f'They set out on {day}.', f'They start the journey on {day}.'])]
    if b.rng.random() < 0.5:
        return facts, pick(b, [f'Where are {a} and {c} headed?', f'Which city are {a} and {c} driving to?']), dict(any=[[city]], none=[])
    return facts, pick(b, [f'When do {a} and {c} set out?', f'What day do {a} and {c} start?']), dict(any=[[day]], none=[])


def update(b):
    used = set()
    a = b.person(used)
    kind = b.rng.choice(['home', 'job', 'day', 'money', 'object'])
    if kind == 'home':
        old, new = b.rng.sample(CITIES, 2)
        return ([f'{a} rents a flat in {old}.', pick(b, [f'{a} relocated, and now {a} lives in {new}.', f'{a} swapped {old} for {new}.', f'{a} left {old}; home is {new} now.'])],
                pick(b, [f'Where does {a} live these days?', f'Which city is {a} in now?']), dict(any=[[new]], none=[old]))
    if kind == 'job':
        old, new = b.rng.sample(JOBS, 2)
        return ([f'{a} is a {old}.', pick(b, [f'{a} switched careers and is a {new} now.', f'{a} stopped being a {old} and became a {new}.', f'{a} is not a {old} anymore, {a} is a {new}.'])],
                pick(b, [f'What does {a} do these days?', f'What is {a}\'s job now?']), dict(any=[[new]], none=[old]))
    if kind == 'day':
        old, new = b.rng.sample(DAYS, 2)
        return ([f'Team lunch is on {old}.', pick(b, [f'Team lunch got pushed to {new}.', f'We moved team lunch to {new}.', f'Team lunch is now on {new}.'])],
                pick(b, ['When is team lunch?', 'What day is team lunch?']), dict(any=[[new]], none=[old]))
    if kind == 'money':
        old, new = b.rng.choice([(200, 250), (90, 70), (500, 650)])
        return ([f'I set aside {old} dollars for the party.', pick(b, [f'Make that {new} dollars for the party.', f'The party budget went up to {new} dollars.' if new > old else f'The party budget went down to {new} dollars.', f'Now I have {new} dollars for the party.'])],
                pick(b, ['How much did I set aside for the party?', 'What is the party budget?']), dict(any=[[str(new)]], none=[str(old)]))
    obj, spots = b.rng.choice(OBJECTS)
    s1, s2 = b.rng.sample(spots, 2)
    be = 'are' if obj.endswith('s') else 'is'
    return ([f'My {obj} {be} in the {s1}.', pick(b, [f'The {obj} {be} in the {s2} now.', f'I put the {obj} away in the {s2}.', f'I took my {obj} to the {s2}.'])],
            pick(b, [f'Where {be} my {obj}?', f'Where did my {obj} end up?']), dict(any=[[s2]], none=[s1]))


def conflict(b):
    used = set()
    a = b.person(used)
    kind = b.rng.choice(['age', 'gossip', 'correction', 'control'])
    if kind == 'age':
        x, y = b.rng.sample([27, 32, 38, 43, 57], 2)
        return ([f'{a} turned {x} in May.', f'{a} is {y} years old.'], pick(b, [f'How old is {a}?', f'What is {a}\'s age?']),
                dict(any=[[str(x)], [str(y)]], none=[], clarify=True))
    if kind == 'gossip':
        c, d = b.person(used), b.person(used)
        x, y = b.rng.sample(DAYS, 2)
        return ([f'{c} told me the picnic is on {x}.', f'{d} thinks the picnic is on {y}.'], pick(b, ['When is the picnic?', 'What day is the picnic?']),
                dict(any=[[x], [y]], none=[], clarify=True))
    if kind == 'correction':
        x, y = b.rng.sample(DAYS, 2)
        return ([f'The workshop is on {x}.', pick(b, [f'Oh wait, I mixed it up: the workshop is on {y}.', f'Correction, {y}, not {x}.', f'Sorry, wrong day: the workshop is on {y}.'])],
                pick(b, ['When is the workshop?', 'Which day is the workshop?']), dict(any=[[y]], none=[x], no_clarify=True))
    c = b.person(used)
    x, y = b.rng.sample(COLOURS, 2)
    return ([f'{a} has a {x} car.', f'{c} has a {y} car.'], pick(b, [f'What colour is {a}\'s car?', f'Which color is {a}\'s car?']),
            dict(any=[[x]], none=[y], no_clarify=True))


PLANS = [('launch my blog', ['pick a name', 'set up hosting', 'write three posts', 'share the link']),
         ('organise the garage', ['empty the shelves', 'sort the tools', 'donate old stuff', 'label the boxes']),
         ('get fit for the race', ['buy running shoes', 'run three times a week', 'join a club', 'rest before the race'])]


def planning(b):
    goal, steps = b.rng.choice(PLANS)
    intro = pick(b, [f'Goal: {goal}. Steps: {", ".join(steps)}.', f'I am working on a project to {goal}; the tasks are {steps[0]}, {steps[1]}, {steps[2]} and {steps[3]}.'])
    kind = b.rng.choice(['next', 'left', 'skip', 'goal'])
    if kind == 'goal':
        return [intro], pick(b, ['What was my goal again?', 'What is the project about?']), dict(any=[[goal.split()[0]]], none=[])
    done = pick(b, [f'Finally finished {steps[0]}.', f'{steps[0].capitalize()}: check.', f'Got {steps[0]} done.'])
    if kind == 'next':
        return [intro, done], pick(b, ['What should I tackle next?', 'What is the next task?']), dict(any=[[steps[1]]], none=[])
    if kind == 'left':
        return [intro, done], pick(b, ['What is still pending?', 'Which tasks are not done yet?']), dict(any=[[s] for s in steps[1:]], none=[])
    return [intro, done, pick(b, [f'Let us not bother with {steps[3]}.', f'Remove {steps[3]} from the list.'])], \
        pick(b, ['What is still pending?', 'Which tasks are not done yet?']), dict(any=[[s] for s in steps[1:3]], none=[steps[3]])


FAMILIES = [('memory', memory, 25), ('reference', reference, 15), ('update', update, 25), ('conflict', conflict, 15), ('planning', planning, 20)]

if __name__ == '__main__':
    rng = random.Random(35004)
    b = Builder(rng, 1)
    items = []
    for name, make, count in FAMILIES:
        for k in range(count):
            facts, question, criteria = make(b)
            history, question = b.conversation(facts, question, rng.randint(5, 50))
            criteria.setdefault('clarify', False)
            criteria.setdefault('no_clarify', False)
            items.append(dict(id=f'fresh2-{name}-{k:03d}', split='fresh2', category=name, history=history, question=question,
                              criteria=criteria, n_messages=len(history) + 1))
    with (HERE / 'fresh2.jsonl').open('w', encoding='utf-8', newline='\n') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    print('fresh2', len(items))
