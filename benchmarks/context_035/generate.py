"""Context & reasoning benchmark for CAEL 0.3.5: conversations of 5-50 messages, one question at the end.

    python generate.py            -> dev.jsonl (development) and test.jsonl (200 held-out questions)

Every item is a fixed transcript (user messages plus short, fixed assistant acknowledgements), so every system sees an
identical history. Questions are graded by predefined criteria (see grade.py), not by exact wording:
  any:      each inner list must have at least one match (synonyms of the required answer)
  none:     must not appear (e.g. a superseded value stated as current), unless an "old_ok" word marks it as past
  clarify:  the reply must point out the contradiction / ask which is right
  no_clarify: the reply must answer directly without claiming a conflict (false-alarm control)

Held-out design: the test set uses different random names and values (seed) AND a disjoint half of every phrasing
family, so a parser tuned on dev wording cannot pass the test by memorising sentences. All templates were written by
the same author who develops CAEL; this is disclosed in the results.
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES_F = ['Anna', 'Maya', 'Sofia', 'Lena', 'Nora', 'Clara', 'Ivy', 'Hana', 'Zara', 'Elena', 'Rosa', 'Mila', 'Tara', 'Lucy', 'Ines', 'Amara']
NAMES_M = ['Ben', 'Leo', 'Omar', 'Felix', 'Hugo', 'Ravi', 'Theo', 'Kofi', 'Diego', 'Sam', 'Ivan', 'Noah', 'Marco', 'Jonas', 'Tariq', 'Pablo']
CITIES = ['Paris', 'Berlin', 'Madrid', 'Lisbon', 'Prague', 'Vienna', 'Oslo', 'Dublin', 'Warsaw', 'Athens', 'Rome', 'Tokyo', 'Toronto',
          'Chicago', 'Sydney', 'Seoul', 'Cairo', 'Lima', 'Nairobi', 'Helsinki']
JOBS = ['nurse', 'teacher', 'pilot', 'chef', 'lawyer', 'architect', 'dentist', 'engineer', 'baker', 'journalist', 'pharmacist',
        'firefighter', 'accountant', 'librarian', 'plumber', 'designer']
COLORS = ['red', 'blue', 'green', 'yellow', 'black', 'white', 'silver', 'orange', 'purple', 'grey']
FOODS = ['sushi', 'pizza', 'pasta', 'tacos', 'curry', 'ramen', 'salad', 'burgers', 'dumplings', 'paella']
PETS = [('dog', ['Rex', 'Biscuit', 'Max', 'Buddy']), ('cat', ['Luna', 'Milo', 'Pepper', 'Whiskers']), ('parrot', ['Kiwi', 'Polly', 'Mango']),
        ('rabbit', ['Coco', 'Thumper', 'Snowball'])]
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
PLACES = ['the library', 'the cafe on Main Street', 'the office', 'the park', 'the train station', 'the museum', 'the gym']
OBJECTS = [('keys', ['drawer', 'kitchen counter', 'blue bag', 'coat pocket']), ('passport', ['safe', 'desk drawer', 'backpack']),
           ('glasses', ['nightstand', 'car', 'bathroom shelf']), ('laptop', ['bedroom', 'office', 'car trunk'])]
RELATIONS = ['sister', 'brother', 'cousin', 'neighbor', 'coworker', 'best friend', 'boss', 'roommate']
ACKS = ['Got it.', 'Okay, noted.', 'Thanks for telling me.', 'Understood.', 'Sounds good.', 'Okay!', 'Noted.', 'I see.']
FILLER = ['The weather was really nice today.', 'I watched a funny movie last night.', 'I had coffee this morning.',
          'Traffic was terrible on the way home.', 'I need to buy groceries at some point.', 'My phone battery died earlier.',
          'I started reading a new book.', 'The train was a bit late today.', 'I went for a short walk after lunch.',
          'My favorite show has a new season.', 'I tried a new recipe for dinner.', 'It rained a little in the evening.',
          'I cleaned my desk today.', 'I listened to some music while working.', 'The meeting at work ran long.',
          'I should drink more water.', 'My neighbor\'s garden looks lovely.', 'I fixed the squeaky door.',
          'I found an old photo album.', 'I want to learn to play the guitar someday.']
OLD_OK = ['before', 'previously', 'used to', 'earlier', 'originally', 'moved from', 'at first', 'formerly', 'no longer', 'not anymore',
          'changed from', 'instead of', 'was ', 'initially']
CLARIFY = ['which', 'clarify', 'conflict', 'contradict', 'both', 'not sure', 'two different', 'disagree', 'confirm', 'inconsistent', 'differ']


class Builder:
    def __init__(self, rng, half):
        self.rng, self.half = rng, half                  # half 0 = dev phrasings, 1 = test phrasings

    def say(self, options):
        """One phrasing from this split's half of a phrasing family (options are listed dev-first, test-second)."""
        n = len(options)
        mine = options[:max(1, n // 2)] if self.half == 0 else options[n // 2:]
        return self.rng.choice(mine)

    def person(self, used, female=None):
        pool = NAMES_F if female else NAMES_M if female is False else NAMES_F + NAMES_M
        name = self.rng.choice([n for n in pool if n not in used])
        used.add(name)
        return name

    def conversation(self, facts, question, total):
        """User fact messages in order, filler between them, padded to `total` messages (user+assistant)."""
        slots = max((total - 1) // 2, len(facts), 2)     # user/assistant pairs before the question: 5..49 messages
        fillers = self.rng.sample(FILLER, k=max(0, min(len(FILLER), slots - len(facts))))
        while len(facts) + len(fillers) < slots:
            fillers.append(self.rng.choice(FILLER))
        order = sorted(self.rng.sample(range(slots), len(facts)))
        lines, fi, fj = [], 0, 0
        for i in range(slots):
            if fj < len(order) and i == order[fj]:
                lines.append(facts[fj]); fj += 1
            else:
                lines.append(fillers[fi]); fi += 1
        history = []
        for line in lines:
            history += [dict(role='user', content=line), dict(role='assistant', content=self.rng.choice(ACKS))]
        return history, question


# ---------------------------------------------------------------- item families

def memory_item(b):
    used = set()
    kind = b.rng.choice(['city', 'job', 'relation', 'pet', 'color', 'food', 'object', 'event'])
    a, c = b.person(used), b.person(used)
    distract_city, city = b.rng.sample(CITIES, 2)
    job, other_job = b.rng.sample(JOBS, 2)
    if kind == 'city':
        facts = [b.say([f'{a} lives in {city}.', f'My friend {a} lives in {city}.', f'{a} has an apartment in {city}.', f'{a} is based in {city} these days.']),
                 b.say([f'{c} lives in {distract_city}.', f'{c} is from {distract_city}.', f'{c} stays in {distract_city}.', f'{c} lives over in {distract_city}.'])]
        q = b.say([f'Where does {a} live?', f'What city does {a} live in?', f'Which city is {a} in?', f'Remind me where {a} lives?'])
        return facts, q, dict(any=[[city]], none=[distract_city])
    if kind == 'job':
        facts = [b.say([f'{a} works as a {job}.', f'{a} is a {job}.', f'{a} has a job as a {job}.', f'By the way, {a} works as a {job} now.']),
                 b.say([f'{c} is a {other_job}.', f'{c} works as a {other_job}.', f'{c} has been a {other_job} for years.', f'{c}\'s job is {other_job}.'])]
        q = b.say([f'What does {a} do for a living?', f'What is {a}\'s job?', f'What does {a} work as?', f'What is {a}\'s profession?'])
        return facts, q, dict(any=[[job]], none=[other_job])
    if kind == 'relation':
        rel = b.rng.choice(RELATIONS)
        facts = [b.say([f'{a} is my {rel}.', f'My {rel} is called {a}.', f'My {rel}\'s name is {a}.', f'{a} is my {rel}, by the way.']),
                 b.say([f'{c} is my dentist.', f'{c} is a friend from school.', f'I met {c} at the gym.', f'{c} lives next to the park.'])]
        q = b.say([f'Who is my {rel}?', f'What is my {rel}\'s name?', f'What\'s the name of my {rel}?', f'Can you remind me who my {rel} is?'])
        return facts, q, dict(any=[[a]], none=[])
    if kind == 'pet':
        animal, names = b.rng.choice(PETS)
        pet = b.rng.choice(names)
        facts = [b.say([f'{a} has a {animal} named {pet}.', f'{a}\'s {animal} is called {pet}.', f'{a} adopted a {animal}; its name is {pet}.', f'{pet} is the name of {a}\'s {animal}.'])]
        q = b.say([f'What is the name of {a}\'s {animal}?', f'What is {a}\'s {animal} called?', f'What did {a} name the {animal}?', f'Do you remember the name of {a}\'s {animal}?'])
        return facts, q, dict(any=[[pet]], none=[])
    if kind == 'color':
        col, other = b.rng.sample(COLORS, 2)
        thing = b.rng.choice(['car', 'bike', 'jacket', 'umbrella'])
        facts = [b.say([f'{a}\'s {thing} is {col}.', f'{a} has a {col} {thing}.', f'{a} just bought a {col} {thing}.', f'The {thing} that {a} owns is {col}.']),
                 b.say([f'{c}\'s {thing} is {other}.', f'{c} has an {other} {thing}.' if other[0] in 'aeiou' else f'{c} has a {other} {thing}.', f'{c} owns a {other} {thing}.', f'{c} painted the {thing} {other}.'])]
        q = b.say([f'What color is {a}\'s {thing}?', f'Which color is the {thing} that {a} has?', f'What colour is {a}\'s {thing}?', f'Remind me, what color is {a}\'s {thing}?'])
        return facts, q, dict(any=[[col]], none=[other])
    if kind == 'food':
        food, other = b.rng.sample(FOODS, 2)
        facts = [b.say([f'{a}\'s favorite food is {food}.', f'{a} loves {food} more than anything.', f'{a} always orders {food}.', f'The food {a} likes most is {food}.']),
                 b.say([f'{c} loves {other}.', f'{c}\'s favorite food is {other}.', f'{c} always orders {other}.', f'{c} likes {other} best.'])]
        q = b.say([f'What is {a}\'s favorite food?', f'What food does {a} like most?', f'What does {a} love to eat?', f'Which food is {a}\'s favorite?'])
        return facts, q, dict(any=[[food]], none=[other])
    if kind == 'object':
        obj, spots = b.rng.choice(OBJECTS)
        spot = b.rng.choice(spots)
        facts = [b.say([f'I left my {obj} in the {spot}.', f'My {obj} {"are" if obj.endswith("s") else "is"} in the {spot}.', f'I put my {obj} in the {spot}.', f'I keep my {obj} in the {spot}.'])]
        q = b.say([f'Where are my {obj}?' if obj.endswith('s') else f'Where is my {obj}?', f'Where did I leave my {obj}?', f'Where did I put my {obj}?', f'Do you remember where my {obj} {"are" if obj.endswith("s") else "is"}?'])
        return facts, q, dict(any=[[spot]], none=[])
    day = b.rng.choice(DAYS)
    place = b.rng.choice(PLACES)
    hour = b.rng.choice(['9 am', '10 am', '2 pm', '3 pm', '4 pm', '6 pm'])
    facts = [b.say([f'I have a meeting with {a} on {day} at {hour}.', f'My meeting with {a} is on {day} at {hour}.', f'I\'m meeting {a} on {day} at {hour}.', f'{a} and I will meet on {day} at {hour}.']),
             b.say([f'The meeting with {a} will be at {place}.', f'We will meet at {place}.', f'The meeting place is {place}.', f'{a} wants to meet at {place}.'])]
    which = b.rng.choice(['day', 'place'])
    if which == 'day':
        q = b.say([f'When is my meeting with {a}?', f'What day am I meeting {a}?', f'On which day is the meeting with {a}?', f'When do I meet {a}?'])
        return facts, q, dict(any=[[day]], none=[])
    q = b.say([f'Where is my meeting with {a}?', f'Where am I meeting {a}?', f'Where will the meeting with {a} be?', f'What place did we pick for the meeting with {a}?'])
    return facts, q, dict(any=[[place.replace('the ', '')]], none=[])


def reference_item(b):
    used = set()
    kind = b.rng.choice(['she', 'he', 'it', 'they', 'my-rel', 'earlier'])
    if kind in ('she', 'he'):
        female = kind == 'she'
        a = b.person(used, female)
        other = b.person(used, not female)
        rel = b.rng.choice(['sister', 'cousin', 'friend', 'neighbor']) if female else b.rng.choice(['brother', 'cousin', 'friend', 'neighbor'])
        job, city = b.rng.choice(JOBS), b.rng.choice(CITIES)
        facts = [b.say([f'My {rel} {a} just got a new job.', f'I want to tell you about my {rel} {a}.', f'Let me tell you about {a}, my {rel}.', f'You should know my {rel} {a}.']),
                 b.say([f'{kind.capitalize()} works as a {job} now.', f'{kind.capitalize()} is a {job}.', f'These days {kind} works as a {job}.', f'{kind.capitalize()} became a {job}.']),
                 b.say([f'{kind.capitalize()} lives in {city}.', f'{kind.capitalize()} moved to {city} a while ago.', f'{kind.capitalize()} is living in {city}.', f'Home for {"her" if female else "him"} is {city}.']),
                 b.say([f'My coworker {other} is very funny.', f'{other} from work told a great joke.', f'I had lunch with {other}.', f'{other} called me yesterday.'])]
        asks_job = b.rng.random() < 0.5
        q = b.say([f'What does my {rel} do?', f'What is my {rel}\'s job?', f'What does my {rel} work as?', f'What job does my {rel} have?']) if asks_job \
            else b.say([f'Where does my {rel} live?', f'Which city does my {rel} live in?', f'Where is my {rel} living?', f'What city is my {rel} in?'])
        answer = job if asks_job else city
        return facts, q, dict(any=[[answer]], none=[])
    if kind == 'it':
        animal, names = b.rng.choice(PETS)
        pet = b.rng.choice(names)
        food = b.rng.choice(['carrots', 'fish', 'chicken', 'seeds', 'apples'])
        facts = [b.say([f'We got a {animal} last week.', f'My family adopted a {animal}.', f'There is a new {animal} in our house.', f'We brought home a {animal}.']),
                 b.say([f'We named it {pet}.', f'Its name is {pet}.', f'We call it {pet}.', f'The kids named it {pet}.']),
                 b.say([f'It loves {food}.', f'It eats a lot of {food}.', f'Its favorite snack is {food}.', f'It only wants {food}.'])]
        q = b.say([f'What is our {animal}\'s name?', f'What did we call the {animal}?', f'What\'s the {animal} called?', f'What is the name of the {animal}?']) \
            if b.rng.random() < 0.5 else b.say([f'What does {pet} like to eat?', f'What food does {pet} love?', f'What is {pet}\'s favorite snack?', f'What does {pet} eat?'])
        return facts, q, dict(any=[[pet] if 'name' in q or 'call' in q else [food]], none=[])
    if kind == 'they':
        a, c = b.person(used), b.person(used)
        city = b.rng.choice(CITIES)
        day = b.rng.choice(DAYS)
        facts = [b.say([f'{a} and {c} are planning a trip.', f'{a} and {c} want to travel together.', f'My friends {a} and {c} are going away.', f'{a} is traveling with {c}.']),
                 b.say([f'They are going to {city}.', f'They chose {city} for the trip.', f'Their destination is {city}.', f'They picked {city}.']),
                 b.say([f'They leave on {day}.', f'They will fly out on {day}.', f'Their flight is on {day}.', f'They depart on {day}.'])]
        q = b.say([f'Where are {a} and {c} going?', f'What city are {a} and {c} traveling to?', f'Where is {a}\'s trip with {c}?', f'Which city did {a} and {c} pick?']) \
            if b.rng.random() < 0.5 else b.say([f'When do {a} and {c} leave?', f'What day is {a} and {c}\'s flight?', f'On which day do {a} and {c} depart?', f'When are {a} and {c} leaving?'])
        return facts, q, dict(any=[[city] if any(w in q for w in ('Where', 'city', 'Which city')) else [day]], none=[])
    if kind == 'my-rel':
        rel = b.rng.choice(['sister', 'brother', 'boss', 'neighbor'])
        female = rel == 'sister' or (rel in ('boss', 'neighbor') and b.rng.random() < 0.5)
        a = b.person(used, female)
        food = b.rng.choice(FOODS)
        facts = [b.say([f'My {rel} is called {a}.', f'{a} is my {rel}.', f'My {rel}\'s name is {a}.', f'I should mention that {a} is my {rel}.']),
                 b.say([f'My {rel} really likes {food}.', f'My {rel} eats {food} every week.', f'My {rel}\'s favorite food is {food}.', f'My {rel} can\'t stop eating {food}.'])]
        q = b.say([f'What food does {a} like?', f'What is {a}\'s favorite food?', f'What does {a} like to eat?', f'Which food does {a} love?'])
        return facts, q, dict(any=[[food]], none=[])
    city1, city2 = b.rng.sample(CITIES, 2)
    facts = [b.say([f'Last summer I visited {city1}.', f'I went to {city1} for a holiday.', f'My last trip was to {city1}.', f'I spent a week in {city1}.']),
             b.say([f'Next year I want to visit {city2}.', f'I\'m dreaming of a trip to {city2}.', f'My next trip will be to {city2}.', f'I hope to see {city2} soon.'])]
    q = b.say(['Which city did I visit last summer?', 'Where did I go on holiday?', 'What was the city I visited before?', 'Which place did I already visit?']) \
        if b.rng.random() < 0.5 else b.say(['Which city do I want to visit next?', 'Where is my next trip?', 'What city am I hoping to visit?', 'Where do I want to go next year?'])
    first = any(w in q for w in ('last summer', 'holiday', 'before', 'already'))
    return facts, q, dict(any=[[city1 if first else city2]], none=[city2 if first else city1])


def update_item(b):
    used = set()
    kind = b.rng.choice(['move', 'job', 'correction', 'number', 'chain', 'history', 'object'])
    a = b.person(used)
    if kind in ('move', 'history'):
        old, new = b.rng.sample(CITIES, 2)
        facts = [b.say([f'{a} lives in {old}.', f'{a} has a flat in {old}.', f'{a} is living in {old}.', f'{a}\'s home is in {old}.']),
                 b.say([f'{a} moved to {new} last month.', f'{a} just relocated to {new}.', f'{a} doesn\'t live in {old} anymore; {a} lives in {new} now.', f'{a} packed up and moved to {new}.'])]
        if kind == 'move':
            q = b.say([f'Where does {a} live now?', f'Where does {a} live?', f'What city is {a} in now?', f'Which city does {a} live in at the moment?'])
            return facts, q, dict(any=[[new]], none=[old])
        q = b.say([f'Where did {a} live before?', f'Which city did {a} live in previously?', f'Where did {a} use to live?', f'What was {a}\'s old city?'])
        return facts, q, dict(any=[[old]], none=[])
    if kind == 'job':
        old, new = b.rng.sample(JOBS, 2)
        facts = [b.say([f'{a} works as a {old}.', f'{a} is a {old}.', f'{a} has a job as a {old}.', f'{a} earns a living as a {old}.']),
                 b.say([f'{a} quit and now works as a {new}.', f'{a} changed careers and is a {new} now.', f'{a} is no longer a {old}; {a} became a {new}.', f'{a} switched jobs and became a {new}.'])]
        q = b.say([f'What does {a} do now?', f'What is {a}\'s job now?', f'What is {a}\'s current job?', f'What does {a} work as at the moment?'])
        return facts, q, dict(any=[[new]], none=[old])
    if kind == 'correction':
        old, new = b.rng.sample(DAYS, 2)
        facts = [b.say([f'My dentist appointment is on {old}.', f'I have a dentist appointment on {old}.', f'The dentist booked me for {old}.', f'I see the dentist on {old}.']),
                 b.say([f'Sorry, I meant {new}, not {old}.', f'Actually, the appointment is on {new}.', f'Correction: it\'s on {new}, not {old}.', f'Wait, I was wrong: the dentist is on {new}.'])]
        q = b.say(['When is my dentist appointment?', 'What day is my dentist appointment?', 'Which day do I see the dentist?', 'When do I go to the dentist?'])
        return facts, q, dict(any=[[new]], none=[old])
    if kind == 'number':
        old, new = b.rng.choice([(300, 450), (500, 650), (1200, 900), (80, 120), (40, 55), (2000, 1500)])
        thing = b.rng.choice(['budget for the trip', 'savings goal', 'monthly budget', 'budget for the party'])
        facts = [b.say([f'My {thing} is {old} dollars.', f'I set my {thing} at {old} dollars.', f'I have {old} dollars as my {thing}.', f'The {thing} is {old} dollars.']),
                 b.say([f'Let\'s change the {thing} to {new} dollars.', f'Update: my {thing} is now {new} dollars.', f'I decided to make the {thing} {new} dollars instead.', f'Make the {thing} {new} dollars, please.'])]
        q = b.say([f'What is my {thing}?', f'What is my {thing} now?', f'How much is my {thing}?', f'What did we set the {thing} to?'])
        return facts, q, dict(any=[[str(new)]], none=[str(old)])
    if kind == 'chain':
        c1, c2, c3 = b.rng.sample(COLORS, 3)
        thing = b.rng.choice(['car', 'front door', 'bike'])
        facts = [b.say([f'My {thing} is {c1}.', f'I have a {c1} {thing}.', f'The {thing} I own is {c1}.', f'My {thing} has always been {c1}.']),
                 b.say([f'I painted my {thing} {c2}.', f'My {thing} is {c2} now.', f'I repainted the {thing} {c2}.', f'Now the {thing} is {c2}.']),
                 b.say([f'I painted my {thing} again, this time {c3}.', f'Changed my mind: the {thing} is {c3} now.', f'Final change: the {thing} is {c3}.', f'Now it\'s {c3}; I repainted the {thing} once more.'])]
        if b.rng.random() < 0.6:
            q = b.say([f'What color is my {thing} now?', f'What color is my {thing}?', f'What is the current color of my {thing}?', f'What colour is the {thing} at the moment?'])
            return facts, q, dict(any=[[c3]], none=[c1, c2])
        q = b.say([f'What color was my {thing} originally?', f'What was the first color of my {thing}?', f'What color was the {thing} at the start?', f'What was the original color of my {thing}?'])
        return facts, q, dict(any=[[c1]], none=[])
    obj, spots = b.rng.choice(OBJECTS)
    s1, s2 = b.rng.sample(spots, 2)
    facts = [b.say([f'My {obj} {"are" if obj.endswith("s") else "is"} in the {s1}.', f'I put my {obj} in the {s1}.', f'I left the {obj} in the {s1}.', f'The {obj} {"are" if obj.endswith("s") else "is"} in the {s1}.']),
             b.say([f'I moved my {obj} to the {s2}.', f'Now my {obj} {"are" if obj.endswith("s") else "is"} in the {s2}.', f'I took the {obj} out and put {"them" if obj.endswith("s") else "it"} in the {s2}.', f'I relocated my {obj} to the {s2}.'])]
    q = b.say([f'Where are my {obj}?' if obj.endswith('s') else f'Where is my {obj}?', f'Where did I put my {obj} last?', f'Where {"are" if obj.endswith("s") else "is"} my {obj} now?', f'Where can I find my {obj}?'])
    return facts, q, dict(any=[[s2]], none=[s1])


def conflict_item(b):
    used = set()
    kind = b.rng.choice(['contradiction', 'contradiction', 'disagreement', 'disagreement', 'correction', 'control'])
    a = b.person(used)
    if kind == 'contradiction':
        if b.rng.random() < 0.5:
            x, y = b.rng.sample([28, 30, 33, 35, 41, 45, 52], 2)
            facts = [b.say([f'{a} is {x} years old.', f'{a} is {x}.', f'{a} turned {x} this year.', f'{a}\'s age is {x}.']),
                     b.say([f'{a} is {y} years old.', f'{a} is {y}.', f'{a} just turned {y}.', f'{a}\'s age is {y}.'])]
            q = b.say([f'How old is {a}?', f'What is {a}\'s age?', f'How old is {a} now?', f'Do you know {a}\'s age?'])
            return facts, q, dict(any=[[str(x)], [str(y)]], none=[], clarify=True)
        x, y = b.rng.sample(CITIES, 2)
        facts = [b.say([f'{a} was born in {x}.', f'{a}\'s birthplace is {x}.', f'{a} comes from {x}, where {a} was born.', f'{a} was born in the city of {x}.']),
                 b.say([f'{a} was born in {y}.', f'{a}\'s birthplace is {y}.', f'{a} is a native of {y} and was born there.', f'{a} was born in the city of {y}.'])]
        q = b.say([f'Where was {a} born?', f'What is {a}\'s birthplace?', f'In which city was {a} born?', f'Where is {a} originally from?'])
        return facts, q, dict(any=[[x], [y]], none=[], clarify=True)
    if kind == 'disagreement':
        c, d = b.person(used), b.person(used)
        x, y = b.rng.sample(DAYS, 2)
        event = b.rng.choice(['party', 'concert', 'exam', 'match'])
        facts = [b.say([f'{c} says the {event} is on {x}.', f'According to {c}, the {event} is on {x}.', f'{c} told me the {event} is on {x}.', f'{c} thinks the {event} is on {x}.']),
                 b.say([f'{d} says the {event} is on {y}.', f'But {d} insists the {event} is on {y}.', f'{d} told me it\'s on {y}.', f'{d} is sure the {event} is on {y}.'])]
        q = b.say([f'When is the {event}?', f'What day is the {event}?', f'On which day is the {event}?', f'When does the {event} happen?'])
        return facts, q, dict(any=[[x], [y]], none=[], clarify=True)
    if kind == 'correction':
        x, y = b.rng.sample(DAYS, 2)
        event = b.rng.choice(['party', 'concert', 'exam', 'match'])
        facts = [b.say([f'The {event} is on {x}.', f'My {event} is on {x}.', f'The {event} takes place on {x}.', f'We have the {event} on {x}.']),
                 b.say([f'Oops, I mean {y}, not {x}.', f'Sorry, my mistake: the {event} is on {y}.', f'Let me correct that: it is on {y}.', f'Scratch that, the {event} is on {y}.'])]
        q = b.say([f'When is the {event}?', f'What day is the {event}?', f'On which day is the {event}?', f'When does the {event} happen?'])
        return facts, q, dict(any=[[y]], none=[x], no_clarify=True)
    c = b.person(used)
    x, y = b.rng.sample(CITIES, 2)
    facts = [b.say([f'{a} lives in {x}.', f'{a} has a home in {x}.', f'{a} is based in {x}.', f'{a} lives over in {x}.']),
             b.say([f'{c} lives in {y}.', f'{c} has a home in {y}.', f'{c} is based in {y}.', f'{c} lives over in {y}.'])]
    q = b.say([f'Where does {a} live?', f'Which city is {a} in?', f'What city does {a} live in?', f'Where is {a} based?'])
    return facts, q, dict(any=[[x]], none=[y], no_clarify=True)


TASKS = [
    ('bake a cake', ['buy flour', 'mix the batter', 'bake it for 30 minutes', 'add the frosting']),
    ('plan a trip to the coast', ['book the train', 'reserve a hotel', 'pack the bags', 'print the tickets']),
    ('move into a new flat', ['pack the boxes', 'hire a van', 'clean the old flat', 'set up the internet']),
    ('throw a birthday party', ['send the invitations', 'order the cake', 'buy decorations', 'make a playlist']),
    ('start a vegetable garden', ['buy seeds', 'prepare the soil', 'plant the seeds', 'set up watering']),
    ('prepare for the exam', ['review chapter one', 'do the practice test', 'make flashcards', 'review my mistakes']),
    ('fix up the bike', ['pump the tires', 'oil the chain', 'replace the brake pads', 'adjust the seat']),
    ('redecorate the living room', ['choose a paint color', 'buy the paint', 'move the furniture', 'paint the walls']),
]


def planning_item(b):
    goal, steps = b.rng.choice(TASKS)
    kind = b.rng.choice(['next', 'left', 'goal', 'skip', 'add', 'constraint'])
    key = lambda s: s.split()[0] if s.split()[0] not in ('the', 'a', 'set', 'make', 'do', 'review', 'buy') else ' '.join(s.split()[:2])
    intro = b.say([f'I want to {goal}. The steps are: {", ".join(steps[:-1])}, and {steps[-1]}.',
                   f'My goal is to {goal}. Plan: first {steps[0]}, then {steps[1]}, then {steps[2]}, and finally {steps[3]}.',
                   f'Help me keep track: I am going to {goal}. Steps: {"; ".join(steps)}.',
                   f'Here is my plan to {goal}: 1) {steps[0]} 2) {steps[1]} 3) {steps[2]} 4) {steps[3]}.'])
    done = b.rng.randint(1, 2)
    progress = b.say([f'I finished the first {done} steps.' if done > 1 else 'I finished the first step.',
                      'Done: ' + ' and '.join(steps[:done]) + '.',
                      'I have completed ' + ' and '.join(steps[:done]) + '.',
                      'Update: ' + ' and '.join(steps[:done]) + (' are' if done > 1 else ' is') + ' done.'])
    if kind == 'goal':
        q = b.say(['What was my goal?', 'What am I trying to do?', 'What is the plan for?', 'Remind me what my goal is?'])
        return [intro], q, dict(any=[[goal.split()[0] + ' ' + goal.split()[1]]], none=[])
    if kind == 'next':
        q = b.say(['What should I do next?', 'What is the next step?', 'What\'s my next step?', 'What comes next in my plan?'])
        return [intro, progress], q, dict(any=[[steps[done]]], none=[])
    if kind == 'left':
        q = b.say(['What steps are left?', 'What do I still need to do?', 'What is left in my plan?', 'Which steps remain?'])
        return [intro, progress], q, dict(any=[[s] for s in steps[done:]], none=[steps[0]])
    if kind == 'skip':
        skipped = steps[-1]
        change = b.say([f'Let\'s skip "{skipped}".', f'Change of plans: no need to {skipped}.', f'I decided not to {skipped}.', f'Drop the step "{skipped}".'])
        q = b.say(['What steps are left?', 'What do I still need to do?', 'What is left in my plan?', 'Which steps remain?'])
        return [intro, progress, change], q, dict(any=[[s] for s in steps[done:-1]], none=[skipped])
    if kind == 'add':
        extra = b.rng.choice(['call the landlord', 'buy batteries', 'check the weather', 'ask for help'])
        change = b.say([f'Also add a step: {extra}.', f'Please add "{extra}" at the end.', f'One more step: {extra}.', f'Add {extra} to the list.'])
        q = b.say(['What steps are left?', 'What do I still need to do?', 'What is left in my plan?', 'Which steps remain?'])
        return [intro, progress, change], q, dict(any=[[s] for s in steps[done:]] + [[extra]], none=[])
    old, new = b.rng.choice([(100, 150), (60, 40), (200, 120), (50, 80)])
    facts = [intro, b.say([f'The budget for this is {old} dollars.', f'I can spend {old} dollars on it.', f'My limit for this is {old} dollars.', f'I have {old} dollars for it.']),
             b.say([f'Change the budget to {new} dollars.', f'New budget: {new} dollars.', f'Actually I can only spend {new} dollars now.' if new < old else f'I can spend {new} dollars now.', f'Let\'s set the limit to {new} dollars.'])]
    q = b.say(['What is my budget for this?', 'How much can I spend on it?', 'What is my spending limit now?', 'What budget did we settle on?'])
    return facts, q, dict(any=[[str(new)]], none=[str(old)])


FAMILIES = [('memory', memory_item), ('reference', reference_item), ('update', update_item), ('conflict', conflict_item), ('planning', planning_item)]
TEST_COUNTS = {'memory': 50, 'reference': 30, 'update': 50, 'conflict': 35, 'planning': 35}
DEV_COUNTS = {'memory': 30, 'reference': 20, 'update': 30, 'conflict': 20, 'planning': 20}


def build(split, counts, seed):
    rng = random.Random(seed)
    b = Builder(rng, 0 if split == 'dev' else 1)
    items = []
    for name, make in FAMILIES:
        for k in range(counts[name]):
            facts, question, criteria = make(b)
            total = rng.randint(5, 50)
            history, question = b.conversation(facts, question, total)
            criteria.setdefault('clarify', False)
            criteria.setdefault('no_clarify', False)
            items.append(dict(id=f'{split}-{name}-{k:03d}', split=split, category=name, history=history, question=question,
                              criteria=criteria, n_messages=len(history) + 1))
    return items


if __name__ == '__main__':
    for split, counts, seed in (('dev', DEV_COUNTS, 35001), ('test', TEST_COUNTS, 35002)):
        items = build(split, counts, seed)
        with (HERE / f'{split}.jsonl').open('w', encoding='utf-8', newline='\n') as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + '\n')
        lengths = [it['n_messages'] for it in items]
        print(split, len(items), 'items; messages', min(lengths), '-', max(lengths))
