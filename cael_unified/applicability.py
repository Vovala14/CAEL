"""Does a reply apply to this conversation? Subject checks shared by every route (John6666's point B, 2026-11-15).

A stored answer can match a question's words and still be about something else: "My fingers get tired when I play
the piano" matched an entry about guitar strings and calluses. A reply is not applicable when it names one member of
a group of alternatives (an instrument, an animal, a vehicle, a computer system, a sport, a device) that the user has
not mentioned, while the user has named a different member of the same group. Days out for people ("a museum, a
picnic") do not answer a question about a pet.

`conflict(conversation_text, reply_text)` returns the clashing pair (what the reply is about, what the user is about)
or None. Plain word lists; no model.
"""
import re

GROUPS = {
    'instrument': 'guitar ukulele uke violin viola cello piano keyboard bass drum drums flute clarinet trumpet trombone saxophone sax harp banjo mandolin '
                  'harmonica accordion recorder',
    'animal': 'dog dogs puppy puppies cat cats kitten kittens rabbit rabbits hamster hamsters horse horses pony parrot budgie fish goldfish tortoise '
              'snake lizard guinea ferret chicken chickens',
    'vehicle': 'car cars bike bikes bicycle bicycles motorbike motorcycle scooter van truck lorry boat',
    'system': 'windows mac macos macbook linux iphone ipad android chromebook',
    'sport': 'football soccer tennis golf swimming running cycling basketball rugby cricket badminton squash climbing skiing yoga pilates boxing',
    'plant': 'monstera cactus cacti succulent orchid fern tomato tomatoes basil mint rose roses lavender bonsai',
    'device': 'phone phones smartphone laptop laptops tablet tablets smokealarm thermostat doorbell router printer smartwatch headphones earbuds '
              'kindle bluetooth',
}
WORDS = {g: set(v.split()) for g, v in GROUPS.items()}
SAME = {'uke': 'ukulele', 'dogs': 'dog', 'puppy': 'dog', 'puppies': 'dog', 'cats': 'cat', 'kitten': 'cat', 'kittens': 'cat', 'rabbits': 'rabbit',
        'hamsters': 'hamster', 'horses': 'horse', 'pony': 'horse', 'goldfish': 'fish', 'bikes': 'bicycle', 'bike': 'bicycle', 'bicycles': 'bicycle',
        'cars': 'car', 'motorbike': 'motorcycle', 'drums': 'drum', 'sax': 'saxophone', 'macos': 'mac', 'macbook': 'mac', 'ipad': 'iphone',
        'chickens': 'chicken', 'cacti': 'cactus', 'tomatoes': 'tomato', 'roses': 'rose', 'keyboard': 'piano', 'soccer': 'football',
        'phones': 'phone', 'smartphone': 'phone', 'bluetooth': 'phone', 'laptops': 'laptop', 'tablets': 'tablet', 'earbuds': 'headphones'}
PASTIME = re.compile(r"(?i)\b(?:museum|gallery|galleries|picnic|cinema|a bike ride|board games?|a walk with a friend|call a friend|book club)\b")


MEAT = re.compile(r"(?i)\b(?:chicken|beef|pork|bacon|ham|lamb|steak|sausages?|mince|turkey|salmon|tuna|prawns?|anchov(?:y|ies)|chorizo|meatballs?)\b")


def named(text):
    """{group: {canonical member}} named in a text."""
    out = {}
    text = re.sub(r"(?i)\bsmoke (?:alarm|detector)s?\b", "smokealarm", text)
    text = re.sub(r"(?i)\bscreen brightness\b|\bbackground refresh\b", "phone", text)      # phone advice that never says "phone"
    low = re.findall(r"[a-z]+", text.lower())
    for g, words in WORDS.items():
        hit = {SAME.get(w, w) for w in low if w in words}
        if hit:
            out[g] = hit
    return out


def conflict(conversation, reply):
    """(reply member, user member) when the reply is about a different member of a group than the user, else None."""
    said = named(conversation)
    body = re.split(r'\n\nSource:', reply)[0]
    if re.search(r"(?i)\b(?:vegetarian|vegan|doesn'?t eat meat|don'?t eat meat|plant-based)\b", conversation) and MEAT.search(body):
        return MEAT.search(body)[0].lower(), 'vegetarian'      # a chicken tray bake for a vegetarian guest
    if not said:
        return None
    if 'animal' in said and PASTIME.search(body) and not re.search(r"(?i)\b(?:i|we)(?:'m| am| are|'re)? (?:bored|lonely)\b", conversation):
        return 'people', sorted(said['animal'])[0]      # "Could he be bored?" about a budgie, answered with days out for people
    got = named(body)
    if re.search(r"(?i)\btyres?\b|\btread\b|\bdriver'?s door\b", body) and 'vehicle' not in said and not re.search(r"(?i)\b(?:car|bike|van|tyres?|wheels?)\b", conversation):
        return 'tyres', next(iter(next(iter(said.values())))) if said else 'something else'      # "tire her out" is not about tyres
    for g, members in got.items():
        if g not in said:
            continue
        foreign = members - said[g]
        if foreign and not (members & said[g]):
            return sorted(foreign)[0], sorted(said[g])[0]
    return None
