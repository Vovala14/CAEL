"""Post-freeze robustness set: 100 questions in wording families written AFTER CAEL 0.3.5's parser was frozen.

    python paraphrase.py   -> fresh.jsonl

dev.jsonl and test.jsonl share phrasing families that the CAEL developer saw while writing the parser (test uses the
held-out half of each family, but the same author wrote both). This set exists to show how much of CAEL's score is
tied to the wordings it was built around: every sentence frame here is new, it was run once, and nothing was tuned on it.
"""
import json
import random
from pathlib import Path

from generate import ACKS, CITIES, COLORS, DAYS, FOODS, JOBS, NAMES_F, NAMES_M, OBJECTS, PETS, Builder

HERE = Path(__file__).resolve().parent


def pick(b, options):
    return b.rng.choice(options)


def memory(b):
    used = set()
    a, c = b.person(used), b.person(used)
    kind = b.rng.choice(['home', 'job', 'pet', 'colour', 'food', 'object', 'call'])
    if kind == 'home':
        x, y = b.rng.sample(CITIES, 2)
        return ([pick(b, [f'{a} calls {x} home.', f'These days {a} rents a place in {x}.', f'{a} settled down in {x}.']),
                 pick(b, [f'{c} grew up near {y}.', f'{c} is staying in {y} for work.'])],
                pick(b, [f'Where is {a} living these days?', f'Which city is home for {a}?', f'In what city does {a} reside?']),
                dict(any=[[x]], none=[]))
    if kind == 'job':
        j, k = b.rng.sample(JOBS, 2)
        return ([pick(b, [f'{a} makes a living as a {j}.', f'{a} has worked as a {j} since college.', f'{a} trained to be a {j} and loves it.']),
                 pick(b, [f'{c} wants to become a {k} one day.', f'{c} studies to be a {k}.'])],
                pick(b, [f'How does {a} earn money?', f'What is {a}\'s line of work?', f'What kind of work does {a} do?']),
                dict(any=[[j]], none=[]))
    if kind == 'pet':
        animal, names = b.rng.choice(PETS)
        pet = b.rng.choice(names)
        return ([pick(b, [f'{a}\'s pet {animal} goes by {pet}.', f'{a} owns a {animal}, {pet}.', f'{a} takes care of a {animal} called {pet}.'])],
                pick(b, [f'What\'s the name of {a}\'s {animal}?', f'How is {a}\'s {animal} called?', f'Which name does {a}\'s {animal} have?']),
                dict(any=[[pet]], none=[]))
    if kind == 'colour':
        col, other = b.rng.sample(COLORS, 2)
        thing = b.rng.choice(['car', 'bike', 'scooter'])
        return ([pick(b, [f'{a} drives a {col} {thing}.' if thing == 'car' else f'{a} rides a {col} {thing}.', f'{a} picked a {col} {thing} last year.']),
                 pick(b, [f'{c} wants an {other} {thing}.' if other[0] in 'aeiou' else f'{c} wants a {other} {thing}.'])],
                pick(b, [f'What colour is the {thing} {a} has?', f'Tell me the color of {a}\'s {thing}.', f'{a}\'s {thing} is what color?']),
                dict(any=[[col]], none=[other]))
    if kind == 'food':
        f, g = b.rng.sample(FOODS, 2)
        return ([pick(b, [f'For dinner {a} would always pick {f}.', f'Nothing makes {a} happier than {f}.', f'{a} is crazy about {f}.']),
                 pick(b, [f'{c} can not stand {g}.', f'{c} sometimes cooks {g}.'])],
                pick(b, [f'What does {a} like eating the most?', f'Which dish is {a}\'s favourite?', f'What should I cook for {a}?']),
                dict(any=[[f]], none=[]))
    if kind == 'object':
        obj, spots = b.rng.choice(OBJECTS)
        spot = b.rng.choice(spots)
        be = 'are' if obj.endswith('s') else 'is'
        return ([pick(b, [f'My {obj} {be} sitting in the {spot}.', f'I dropped my {obj} into the {spot} earlier.', f'I stuck my {obj} in the {spot}.'])],
                pick(b, [f'Any idea where my {obj} {be}?', f'Where did my {obj} end up?', f'Can you tell me where I left the {obj}?']),
                dict(any=[[spot]], none=[]))
    day, hour = b.rng.choice(DAYS), b.rng.choice(['9 am', '11 am', '1 pm', '5 pm'])
    return ([pick(b, [f'I have got a call with {a} on {day} at {hour}.', f'{a} scheduled a video call with me for {day}, {hour}.', f'There is a call with {a} on {day}.'])],
            pick(b, [f'When is the call with {a}?', f'What day did {a} schedule our call?', f'When am I talking to {a}?']),
            dict(any=[[day]], none=[]))


def reference(b):
    used = set()
    kind = b.rng.choice(['she', 'he', 'kitten', 'they'])
    if kind in ('she', 'he'):
        female = kind == 'she'
        a = b.person(used, female)
        rel = b.rng.choice(['aunt', 'cousin', 'friend']) if female else b.rng.choice(['uncle', 'cousin', 'friend'])
        job, city = b.rng.choice(JOBS), b.rng.choice(CITIES)
        return _ref_person(b, a, rel, 'She' if female else 'He', job, city)
    if kind == 'kitten':
        pet, food = b.rng.choice(['Mochi', 'Pumpkin', 'Ziggy', 'Olive']), b.rng.choice(['tuna', 'salmon', 'chicken'])
        q, ans = (('What did we name the kitten?', pet) if b.rng.random() < 0.5 else (f'What does {pet} adore?', food))
        return ([pick(b, ['We adopted a kitten on Sunday.', 'A tiny kitten moved in with us.']),
                 pick(b, [f'She is called {pet}.', f'We gave her the name {pet}.']),
                 pick(b, [f'She adores {food}.', f'She goes wild for {food}.'])], q, dict(any=[[ans]], none=[]))
    a, c = b.person(used), b.person(used)
    city, day = b.rng.choice(CITIES), b.rng.choice(DAYS)
    q, ans = ((f'Where are {a} and {c} flying?', city) if b.rng.random() < 0.5 else (f'Which day do {a} and {c} fly?', day))
    return ([pick(b, [f'{a} and {c} booked tickets.', f'{a} and {c} finally planned a holiday.']),
             pick(b, [f'They fly to {city}.', f'They are heading off to {city}.']),
             pick(b, [f'Their plane takes off on {day}.', f'They go on {day}.'])], q, dict(any=[[ans]], none=[]))


def _ref_person(b, a, rel, pr, job, city):
    facts = [pick(b, [f'My {rel}, {a}, visited us.', f'Guess what, my {rel} {a} called.']),
             pick(b, [f'{pr} is a {job} at a big company.', f'{pr} has worked as a {job} for ten years.']),
             pick(b, [f'{pr} just bought a flat in {city}.', f'{pr} is renting in {city} now.'])]
    if b.rng.random() < 0.5:
        return facts, pick(b, [f'What is my {rel}\'s line of work?', f'What does my {rel} do for work?']), dict(any=[[job]], none=[])
    return facts, pick(b, [f'Where is my {rel} living?', f'Which city is my {rel} in?']), dict(any=[[city]], none=[])


def update(b):
    used = set()
    a = b.person(used)
    kind = b.rng.choice(['home', 'job', 'day', 'money', 'object'])
    if kind == 'home':
        old, new = b.rng.sample(CITIES, 2)
        return ([f'{a} lives in {old}.', pick(b, [f'Big news: {a} is in {new} now.', f'{a} said goodbye to {old} and settled in {new}.', f'{a} has a new address in {new}.'])],
                pick(b, [f'Where is {a} now?', f'Which city is {a} living in at present?']), dict(any=[[new]], none=[old]))
    if kind == 'job':
        old, new = b.rng.sample(JOBS, 2)
        return ([f'{a} works as a {old}.', pick(b, [f'{a} left the {old} job and is now a {new}.', f'{a} retrained as a {new}.', f'{a} gave up being a {old}; these days {a} is a {new}.'])],
                pick(b, [f'What is {a} doing for work now?', f'What is {a}\'s job these days?']), dict(any=[[new]], none=[old]))
    if kind == 'day':
        old, new = b.rng.sample(DAYS, 2)
        return ([f'The dentist appointment is on {old}.', pick(b, [f'Change of plan: the dentist is on {new} instead of {old}.', f'The dentist moved my appointment to {new}.', f'They rescheduled the dentist for {new}.'])],
                pick(b, ['When do I see the dentist?', 'What day is the dentist now?']), dict(any=[[new]], none=[old]))
    if kind == 'money':
        old, new = b.rng.choice([(300, 450), (80, 60), (1000, 1200)])
        return ([f'My budget for the trip is {old} dollars.', pick(b, [f'We bumped the trip budget from {old} to {new} dollars.', f'New number for the trip budget: {new} dollars.', f'I raised the budget for the trip to {new} dollars.' if new > old else f'I cut the budget for the trip to {new} dollars.'])],
                pick(b, ['How much is my trip budget now?', 'What is the budget for the trip at this point?']), dict(any=[[str(new)]], none=[str(old)]))
    obj, spots = b.rng.choice(OBJECTS)
    s1, s2 = b.rng.sample(spots, 2)
    be = 'were' if obj.endswith('s') else 'was'
    return ([f'My {obj} {be} in the {s1}.', pick(b, [f'I have since moved my {obj} to the {s2}.', f'The {obj} went from the {s1} to the {s2}.', f'Later I shifted my {obj} over to the {s2}.'])],
            pick(b, [f'Where are my {obj} right now?' if obj.endswith('s') else f'Where is my {obj} right now?', f'Where should I look for my {obj}?']),
            dict(any=[[s2]], none=[s1]))


def conflict(b):
    used = set()
    a = b.person(used)
    kind = b.rng.choice(['age', 'gossip', 'correction', 'control'])
    if kind == 'age':
        x, y = b.rng.sample([29, 31, 36, 44, 50], 2)
        return ([f'{a} is {x}.', pick(b, [f'{a} is {y} years old.', f'{a} celebrated turning {y}.'])],
                pick(b, [f'What age is {a}?', f'How old is {a}?']), dict(any=[[str(x)], [str(y)]], none=[], clarify=True))
    if kind == 'gossip':
        c, d = b.person(used), b.person(used)
        x, y = b.rng.sample(DAYS, 2)
        return ([pick(b, [f'{c} reckons the gig is on {x}.', f'{c} heard the gig is on {x}.']), pick(b, [f'{d} is convinced the gig is on {y}.', f'{d} reckons the gig is on {y}.'])],
                pick(b, ['Which day is the gig?', 'When is the gig?']), dict(any=[[x], [y]], none=[], clarify=True))
    if kind == 'correction':
        x, y = b.rng.sample(DAYS, 2)
        return ([f'The exam is on {x}.', pick(b, [f'Hmm no, the exam is on {y}.', f'I got that wrong, the exam is on {y}.', f'My bad, it is {y}, not {x}.'])],
                pick(b, ['When is the exam?', 'What day is the exam?']), dict(any=[[y]], none=[x], no_clarify=True))
    c = b.person(used)
    x, y = b.rng.sample(JOBS, 2)
    return ([f'{a} works as a {x}.', f'{c} works as a {y}.'], pick(b, [f'What does {a} do?', f'What is {a}\'s job?']), dict(any=[[x]], none=[y], no_clarify=True))


PLANS = [('paint the fence', ['buy brushes', 'sand the wood', 'apply primer', 'paint two coats']),
         ('host a dinner', ['write the menu', 'shop for food', 'set the table', 'cook the main course']),
         ('learn to swim', ['buy goggles', 'book a lesson', 'practice floating', 'swim one length'])]


def planning(b):
    goal, steps = b.rng.choice(PLANS)
    intro = pick(b, [f'Today\'s list to {goal}: {", ".join(steps)}.', f'To {goal} I need to {steps[0]}, {steps[1]}, {steps[2]} and {steps[3]}.'])
    kind = b.rng.choice(['next', 'left', 'skip', 'goal'])
    if kind == 'goal':
        return [intro], pick(b, ['What was I trying to get done?', 'Remind me what the list is for?']), dict(any=[[goal.split()[0]]], none=[])
    done = pick(b, [f'Ticked off: {steps[0]}.', f'{steps[0].capitalize()} - done.', f'Just finished: {steps[0]}.'])
    if kind == 'next':
        return [intro, done], pick(b, ['What is next on the list?', 'Which step comes after that?']), dict(any=[[steps[1]]], none=[])
    if kind == 'left':
        return [intro, done], pick(b, ['What is still open on my list?', 'How much is left to do?']), dict(any=[[s] for s in steps[1:]], none=[])
    return [intro, done, pick(b, [f'Forget "{steps[3]}", no time.', f'Cross out "{steps[3]}".'])], pick(b, ['What is still open on my list?', 'What remains?']), \
        dict(any=[[s] for s in steps[1:3]], none=[steps[3]])


FAMILIES = [('memory', memory, 25), ('reference', reference, 15), ('update', update, 25), ('conflict', conflict, 15), ('planning', planning, 20)]

if __name__ == '__main__':
    rng = random.Random(35003)
    b = Builder(rng, 0)
    items = []
    for name, make, count in FAMILIES:
        for k in range(count):
            facts, question, criteria = make(b)
            history, question = b.conversation(facts, question, rng.randint(5, 50))
            criteria.setdefault('clarify', False)
            criteria.setdefault('no_clarify', False)
            items.append(dict(id=f'fresh-{name}-{k:03d}', split='fresh', category=name, history=history, question=question,
                              criteria=criteria, n_messages=len(history) + 1))
    with (HERE / 'fresh.jsonl').open('w', encoding='utf-8', newline='\n') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    print('fresh', len(items))
