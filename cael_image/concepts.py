"""What CAEL knows about the things it can draw: kinds, real sizes, colours, sounds, abilities.

Authored knowledge, no learning. Used to reason about picture requests: "the animal that
says moo" -> cow, "a poodle" -> dog (a poodle is a dog), "a yellow fruit" -> banana, and
to draw an elephant larger than a cat.
"""
import json
from pathlib import Path
import re

# topic: (kinds, typical size in metres, typical colours, abilities/features)
FACTS = {
    'airplane': ('vehicle', 30, 'white', 'flies wings wheels'),
    'apple': ('fruit food', .08, 'red green', 'edible'),
    'backpack': ('clothing', .5, 'blue black red', 'wearable'),
    'ball': ('toy', .25, 'red white', 'play'),
    'balloon': ('toy', .3, 'red', 'flies'),
    'banana': ('fruit food', .2, 'yellow', 'edible'),
    'bear': ('animal wild', 2, 'brown', 'fur'),
    'bed': ('furniture', 2, 'white', 'sit'),
    'bicycle': ('vehicle', 1.7, 'red blue', 'wheels ride'),
    'bird': ('animal', .2, 'blue red yellow', 'flies wings feathers eggs'),
    'boat': ('vehicle', 6, 'white', 'water'),
    'book': ('object', .25, 'red blue', 'read'),
    'bottle': ('kitchen', .3, 'green', 'drink'),
    'bread': ('food', .3, 'brown', 'edible'),
    'burger': ('food', .12, 'brown', 'edible'),
    'bus': ('vehicle', 12, 'yellow red', 'wheels'),
    'butterfly': ('animal insect', .08, 'orange blue yellow', 'flies wings'),
    'cactus': ('plant', 2, 'green', 'thorns desert'),
    'cake': ('food dessert', .25, 'white pink brown', 'edible'),
    'camera': ('device', .15, 'black', 'photo'),
    'car': ('vehicle', 4.5, 'red blue white black', 'wheels'),
    'carrot': ('vegetable food', .2, 'orange', 'edible'),
    'castle': ('building', 40, 'gray', ''),
    'cat': ('animal pet', .45, 'orange gray black white', 'fur whiskers'),
    'chair': ('furniture', .9, 'brown', 'sit'),
    'chicken': ('animal farm bird', .4, 'white brown', 'wings feathers eggs'),
    'clock': ('object', .3, 'white', 'time'),
    'computer_mouse': ('device', .1, 'black white', ''),
    'cow': ('animal farm', 2.2, 'black white brown', 'milk spots horns'),
    'cup': ('kitchen', .1, 'white', 'drink'),
    'dog': ('animal pet', .7, 'brown black white', 'fur'),
    'donut': ('food dessert', .1, 'pink brown', 'edible'),
    'dragon': ('animal mythical', 15, 'green red', 'flies wings fire scales'),
    'duck': ('animal farm bird', .4, 'yellow white', 'flies wings feathers eggs water swims'),
    'elephant': ('animal wild', 4, 'gray', 'trunk tusks'),
    'fish': ('animal pet sea', .3, 'orange blue', 'water swims fins scales eggs'),
    'flower': ('plant', .4, 'pink red yellow', 'petals'),
    'frog': ('animal', .1, 'green', 'water swims jumps eggs'),
    'giraffe': ('animal wild', 5, 'yellow brown', 'long_neck spots'),
    'glasses': ('clothing', .14, 'black', 'wearable'),
    'grapes': ('fruit food', .15, 'purple green', 'edible'),
    'guitar': ('instrument', 1, 'brown', 'music play'),
    'hat': ('clothing', .3, 'black brown', 'wearable'),
    'headphones': ('device', .2, 'black', 'music wearable'),
    'helicopter': ('vehicle', 12, 'red yellow', 'flies'),
    'horse': ('animal farm', 2.2, 'brown black white', 'mane ride'),
    'house': ('building', 10, 'white red', ''),
    'ice_cream': ('food dessert', .18, 'pink white brown', 'edible cold melts'),
    'key': ('object', .07, 'gold gray', ''),
    'keyboard': ('device', .45, 'black', ''),
    'kite': ('toy', 1, 'red yellow', 'flies play'),
    'lamp': ('furniture', .5, 'white', 'light'),
    'laptop': ('device', .35, 'gray', ''),
    'lighthouse': ('building', 30, 'white red', 'light sea'),
    'lion': ('animal wild', 2, 'yellow brown', 'mane fur'),
    'man': ('person', 1.75, '', ''),
    'monitor': ('device', .6, 'black', 'screen'),
    'monkey': ('animal wild', .6, 'brown', 'fur climbs'),
    'motorcycle': ('vehicle', 2, 'black red', 'wheels ride'),
    'mushroom': ('plant food', .1, 'red white brown', 'edible'),
    'orange': ('fruit food', .08, 'orange', 'edible'),
    'owl': ('animal bird', .4, 'brown', 'flies wings feathers eggs night'),
    'penguin': ('animal bird sea', .7, 'black white', 'wings feathers eggs water swims cold'),
    'phone': ('device', .15, 'black', 'screen'),
    'pig': ('animal farm', 1.2, 'pink', ''),
    'pizza': ('food', .35, 'red yellow', 'edible'),
    'rabbit': ('animal pet', .4, 'white gray brown', 'fur jumps'),
    'robot': ('toy machine', 1.5, 'gray white', ''),
    'rocket': ('vehicle', 50, 'white', 'flies space'),
    'rose': ('plant flower', .4, 'red', 'petals thorns'),
    'scissors': ('tool', .2, 'gray', 'cut'),
    'shark': ('animal sea', 4, 'gray', 'water swims fins teeth'),
    'sheep': ('animal farm', 1.2, 'white', 'wool'),
    'shoe': ('clothing', .3, 'black brown white', 'wearable'),
    'snake': ('animal', 1.5, 'green', 'scales eggs'),
    'snowman': ('object', 1.6, 'white', 'cold melts'),
    'sofa': ('furniture', 2, 'gray brown', 'sit'),
    'spaceship': ('vehicle', 30, 'gray white', 'flies space'),
    'strawberry': ('fruit food', .04, 'red', 'edible'),
    'sunflower': ('plant flower', 1.5, 'yellow', 'petals'),
    'table': ('furniture', 1.5, 'brown', ''),
    'tablet': ('device', .25, 'black', 'screen'),
    'teapot': ('kitchen', .2, 'white', 'drink'),
    'television': ('device', 1, 'black', 'screen'),
    'tent': ('object', 2.5, 'orange green', ''),
    'tiger': ('animal wild', 2.5, 'orange', 'stripes fur'),
    'tractor': ('vehicle farm', 4, 'green red', 'wheels'),
    'train': ('vehicle', 30, 'red', 'wheels'),
    'tree': ('plant', 8, 'green', 'leaves'),
    'truck': ('vehicle', 8, 'red white', 'wheels'),
    'turtle': ('animal sea pet', .4, 'green', 'shell water swims eggs slow'),
    'umbrella': ('object', 1, 'black red', 'rain'),
    'watch': ('clothing device', .05, 'gold gray', 'time wearable'),
    'whale': ('animal sea', 25, 'blue gray', 'water swims fins'),
    'woman': ('person', 1.65, '', ''),
    'zebra': ('animal wild', 2.2, 'black white', 'stripes'),
}
FACTS.update({
    'mouse': ('animal', .08, 'gray brown white', 'fur'),
    'fox': ('animal wild', .7, 'orange', 'fur'),
    'wolf': ('animal wild', .8, 'gray', 'fur'),
    'deer': ('animal wild', 1.5, 'brown', 'fur jumps'),
    'dolphin': ('animal sea', 2.5, 'gray blue', 'water swims fins jumps'),
})
SCENES = ('beach', 'city', 'forest', 'mountain', 'waterfall', 'volcano', 'castle', 'desert', 'snow', 'sky', 'ocean', 'park', 'field', 'room')
FACTS.update({s: ('place', 50, '', '') for s in SCENES if s not in FACTS})

# Kinds of a thing CAEL can draw: drawn as that thing, and said so.
KIND_OF = {
    'dog': 'poodle labrador retriever terrier bulldog beagle husky dachshund chihuahua collie pug shepherd corgi spaniel doggy hound',
    'cat': 'kitty tabby siamese persian tomcat',
    'horse': 'pony stallion mare foal',
    'cow': 'calf ox',
    'sheep': 'lamb ram ewe',
    'pig': 'piglet hog',
    'bird': 'eagle sparrow robin pigeon crow hawk seagull falcon canary finch',
    'fish': 'goldfish salmon trout tuna',
    'chicken': 'hen rooster chick',
    'duck': 'duckling',
    'flower': 'tulip daisy lily daffodil orchid',
    'tree': 'oak pine palm birch maple',
    'car': 'taxi jeep convertible',
    'truck': 'lorry van',
    'boat': 'yacht canoe kayak ship',
    'airplane': 'airliner',
    'rabbit': 'bunny',
    'bear': 'grizzly',
    'house': 'cottage cabin',
    'shoe': 'sneaker boot sandal',
    'hat': 'cap',
    'cake': 'cupcake',
    'monkey': 'chimp chimpanzee gorilla',
}

def register(topic, kinds, size, colours, features):
    """Add drawing knowledge for a subject the nightly run taught the picture model (topic_catalogue.py)."""
    FACTS.setdefault(topic, (kinds, size, colours, features))


# Subjects added by the nightly run (research/image_nightly/nightly.py) after they passed its checks.
_LEARNED = Path(__file__).with_name('learned_topics.json')
if _LEARNED.exists():
    for _row in json.loads(_LEARNED.read_text(encoding='utf-8')):
        register(*_row[:5])

# Things it cannot draw, with the closest thing it can (said so explicitly).
SIMILAR = {
    'dolphin': 'whale', 'wolf': 'dog', 'fox': 'dog', 'rat': 'mouse', 'reindeer': 'deer', 'elk': 'deer', 'moose': 'deer', 'coyote': 'wolf', 'porpoise': 'dolphin', 'leopard': 'tiger', 'cheetah': 'tiger', 'panther': 'tiger',
    'donkey': 'horse', 'goat': 'sheep', 'deer': 'horse', 'hamster': 'rabbit', 'parrot': 'bird', 'swan': 'duck',
    'goose': 'duck', 'lizard': 'snake', 'crocodile': 'snake', 'alligator': 'snake', 'van': 'truck', 'scooter': 'motorcycle',
    'tulip': 'flower', 'lemon': 'orange', 'pear': 'apple', 'cherry': 'strawberry', 'muffin': 'cake', 'sandwich': 'burger',
    'mug': 'cup', 'tower': 'lighthouse', 'skyscraper': 'house', 'jet': 'airplane', 'ufo': 'spaceship', 'moth': 'butterfly',
    'bee': 'butterfly', 'tortoise': 'turtle', 'puppy': 'dog', 'kitten': 'cat', 'sweater': 'hat',
}
SOUNDS = {
    'moo': 'cow', 'woof': 'dog', 'bark': 'dog', 'barks': 'dog', 'meow': 'cat', 'meows': 'cat', 'purr': 'cat', 'purrs': 'cat',
    'oink': 'pig', 'baa': 'sheep', 'quack': 'duck', 'quacks': 'duck', 'neigh': 'horse', 'neighs': 'horse', 'roar': 'lion',
    'roars': 'lion', 'hoot': 'owl', 'hoots': 'owl', 'ribbit': 'frog', 'croak': 'frog', 'croaks': 'frog', 'hiss': 'snake',
    'hisses': 'snake', 'cluck': 'chicken', 'clucks': 'chicken', 'tweet': 'bird', 'chirp': 'bird', 'chirps': 'bird',
    'sings': 'bird', 'trumpets': 'elephant', 'ticks': 'clock', 'tick tock': 'clock',
}
IDIOMS = {"king of the jungle": 'lion', "man's best friend": 'dog', 'mans best friend': 'dog', 'ship of the desert': None,
          'big apple': 'city', 'keeps the doctor away': 'apple'}
CATEGORY_WORDS = {
    'animal': 'animal', 'animals': 'animal', 'creature': 'animal', 'creatures': 'animal', 'pet': 'pet', 'pets': 'pet',
    'fruit': 'fruit', 'fruits': 'fruit', 'vegetable': 'vegetable', 'vegetables': 'vegetable', 'food': 'food', 'snack': 'food',
    'dessert': 'dessert', 'treat': 'dessert', 'vehicle': 'vehicle', 'vehicles': 'vehicle', 'plant': 'plant', 'plants': 'plant',
    'building': 'building', 'instrument': 'instrument', 'toy': 'toy', 'toys': 'toy', 'furniture': 'furniture', 'device': 'device',
    'gadget': 'device', 'insect': 'insect', 'bug': 'insect', 'sea creature': 'sea', 'farm animal': 'farm', 'wild animal': 'wild',
    'thing': None, 'things': None, 'something': None, 'object': None,
}
# Phrases in a description -> the feature they require.
ABILITIES = [
    (r'\b(?:can|could|that|which)?\s*(?:fly|flies|flying)\b|\bwith wings\b|\bwinged\b', 'flies'),
    (r'\b(?:swim|swims|swimming)\b|\blives? in (?:the )?(?:water|sea|ocean)\b|\bunderwater\b', 'swims'),
    (r'\b(?:eat|edible|eaten)\b', 'edible'),
    (r'\bstripe[sd]?\b|\bstriped\b', 'stripes'), (r'\blong neck\b', 'long_neck'), (r'\btrunk\b', 'trunk'),
    (r'\bshell\b', 'shell'), (r'\bmane\b', 'mane'), (r'\bspot(?:s|ted)\b', 'spots'), (r'\bfeathers?\b', 'feathers'),
    (r'\bfins?\b', 'fins'), (r'\bwheels?\b', 'wheels'), (r'\bfire\b', 'fire'), (r'\b(?:lays? )?eggs\b', 'eggs'),
    (r'\bmilk\b', 'milk'), (r'\bthorns?\b|\bprickly\b|\bspiky\b', 'thorns'), (r'\bmelts?\b', 'melts'),
    (r'\b(?:tells? (?:the )?time|time)\b', 'time'), (r'\brain\b', 'rain'), (r'\bsit (?:on|in)\b', 'sit'),
    (r'\bride\b', 'ride'), (r'\bwear\b', 'wearable'), (r'\bdrink\b', 'drink'), (r'\bread\b', 'read'),
    (r'\bplay(?: with)?\b', 'play'), (r'\bmusic\b', 'music'), (r'\bjumps?\b|\bhops?\b', 'jumps'), (r'\bslow\b', 'slow'),
    (r'\bat night\b|\bnocturnal\b', 'night'), (r'\bwool\b', 'wool'), (r'\bteeth\b', 'teeth'), (r'\bscales\b', 'scales'),
    (r'\bcold\b', 'cold'), (r'\bspace\b', 'space'), (r'\bscreen\b', 'screen'), (r'\bclimbs?\b', 'climbs'), (r'\bcut\b', 'cut'),
]
FEATURE_TEXT = {
    'flies': 'it can fly', 'swims': 'it swims', 'edible': 'you can eat it', 'long_neck': 'it has a long neck', 'wheels': 'it has wheels',
    'stripes': 'it has stripes', 'spots': 'it has spots', 'eggs': 'it lays eggs', 'milk': 'it gives milk', 'melts': 'it melts',
    'time': 'it tells the time', 'rain': 'it keeps off the rain', 'sit': 'you can sit on it', 'ride': 'you can ride it',
    'wearable': 'you can wear it', 'drink': 'you drink from it', 'read': 'you can read it', 'play': 'you can play with it',
    'music': 'it makes music', 'jumps': 'it jumps', 'slow': 'it is slow', 'night': 'it is active at night', 'cold': 'it likes the cold',
    'space': 'it goes to space', 'climbs': 'it climbs', 'cut': 'it cuts', 'fire': 'it breathes fire',
}
NEGATIONS = {'not', 'cannot', "can't", 'cant', "doesn't", 'doesnt', "don't", 'dont', 'without', 'no', 'never', "isn't"}
SUPERLATIVE = {'biggest': 1, 'largest': 1, 'tallest': 1, 'heaviest': 1, 'smallest': -1, 'tiniest': -1, 'littlest': -1, 'shortest': -1}


def kinds(topic):
    return set(FACTS[topic][0].split())


def size(topic):
    return FACTS[topic][1]


def colours(topic):
    return FACTS[topic][2].split()


def features(topic):
    return set(FACTS[topic][3].split())


def flies(topic):
    return 'flies' in features(topic)


def aquatic(topic):
    return 'swims' in features(topic) and topic not in ('duck', 'penguin', 'frog', 'turtle')


def describe(phrase, topics):
    """Topics matching a description such as 'the animal that says moo' or 'a yellow fruit'.

    Returns (matches, reasons): matches is a list of topics (best first), reasons explain the choice.
    """
    from .request import COLOURS
    text = ' '.join(phrase.lower().replace('-', ' ').split())
    available = [t for t in topics if t in FACTS and 'place' not in kinds(t)]
    for idiom, topic in IDIOMS.items():
        if idiom in text and topic in topics:
            return [topic], [f'"{idiom}" means the {topic.replace("_", " ")}']
    reasons = []
    for sound, topic in sorted(SOUNDS.items(), key=lambda kv: -len(kv[0])):
        if re.search(r'\b' + re.escape(sound) + r'\b', text) and topic in topics:
            return [topic], [f'it is the one that goes "{sound}"']
    pool = available
    category = next((CATEGORY_WORDS[w] for w in sorted(CATEGORY_WORDS, key=len, reverse=True) if re.search(r'\b' + w + r'\b', text)), None)
    if category:
        pool = [t for t in pool if category in kinds(t)]
        if not re.search(r'\b(?:mythical|fantasy|magic|imaginary|fire)\b', text):
            pool = [t for t in pool if 'mythical' not in kinds(t)]     # "the biggest animal" means a real one
        reasons.append('it is ' + ('an ' if category[0] in 'aeiou' else 'a ') + category)
    for pattern, feature in ABILITIES:
        match = re.search(pattern, text)
        if match:
            negated = any(w in NEGATIONS for w in text[:match.start()].split()[-3:])
            pool = [t for t in pool if (feature in features(t)) != negated]
            reasons.append(('not: ' if negated else '') + FEATURE_TEXT.get(feature, 'it has ' + feature.replace('_', ' ')))
    asked_colours = [w for w in re.findall(r'[a-z]+', text) if w in COLOURS]
    for colour in asked_colours:
        coloured = [t for t in pool if colour in colours(t)]
        if coloured:
            pool = coloured
            reasons.append('it is usually ' + colour)
    order = next((v for w, v in SUPERLATIVE.items() if re.search(r'\b' + w + r'\b', text)), 0)
    if order:
        pool = sorted(pool, key=lambda t: -order * size(t))[:1]
        reasons.append('it is the ' + ('largest' if order > 0 else 'smallest') + ' of those I can draw')
    if not reasons:
        return [], []
    return pool, reasons
