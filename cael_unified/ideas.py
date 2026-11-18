"""Ideas on request (authored, no model): party, gift, rainy-day, date, dinner and weekend ideas, each with what you'd need,
plus fun facts. 'The second one sounds good. What would we need?' picks the idea back up from CAEL's own list."""
import random
import re

# kind: (request pattern, [(idea, one-line description, what you'd need)])
IDEAS = {
    'party_kids': (r"\b(?:party|birthday)\b.*\b(?:kid|child|children|year[- ]old|son|daughter|boy|girl|\d+(?:th|st|nd|rd))\b|\b(?:kid|child|children|year[- ]old)\b.*\b(?:party|birthday)\b", [
        ('Treasure hunt', 'clues hidden around the house or garden leading to a prize box, done in teams',
         'six to ten written clues, a small prize box (sweets, small toys), a map or first clue for each team, and someone to hide them beforehand'),
        ('Pizza and film night', 'everyone builds their own pizza, then a film with popcorn and blankets',
         'pizza bases, sauce, cheese and toppings in bowls, aprons, an oven, a film everyone can watch, popcorn, cushions and blankets'),
        ('Mini Olympics', 'a series of silly races and challenges in the garden or park, with medals at the end',
         'cones or markers, sacks or pillowcases for a sack race, eggs and spoons, a stopwatch, a score sheet, and cheap medals or stickers'),
        ('Craft party', 'decorate T-shirts, make slime or build something to take home',
         'plain T-shirts and fabric pens (or slime kit, or cardboard and tape), newspaper or a wipeable cloth, aprons, and a table per few children'),
        ('Escape room at home', 'a room with puzzles and locked boxes the children solve to "escape" in 30-45 minutes',
         'a story, five or six puzzles (codes, riddles, a jigsaw), a padlock or lockable box, a timer, and a small prize when they get out'),
        ('Science party', 'fizzy experiments: volcanoes, lava lamps, mentos fountains (outside)',
         'bicarbonate of soda, vinegar, food colouring, clear bottles, oil, effervescent tablets, goggles, and a garden or easy-clean space')]),
    'party_adult': (r"\b(?:party|birthday|celebration|get[- ]together)\b(?!.*\b(?:kid|child|year[- ]old|son|daughter)\b)", [
        ('Themed dinner party', 'a meal around one country or decade, guests dress up a little',
         'a menu of three easy dishes, a playlist, a few decorations, and invitations that say the theme'),
        ('Games night', 'board games, a quiz or charades with snacks',
         'three or four games for different group sizes, quiz questions, snacks, drinks, and enough seating'),
        ('Picnic or barbecue', 'outdoors in a park or garden, everyone brings something',
         'a barbecue or picnic blankets, food and drinks list shared out, cups and plates, a bin bag, and a rain plan'),
        ('Karaoke night', 'at home with a karaoke app or at a booked room',
         'a TV or speaker, a karaoke app or video playlist, one or two microphones, and snacks'),
        ('Cooking or cocktail class', 'learn something together, at a venue or with an online class at home',
         'a booking (or a recipe and ingredients for each person), aprons, and the equipment the recipe needs')]),
    'gift': (r"\b(?:gift|present)s?\b", [
        ('An experience', 'tickets for a show, a class or a day out instead of a thing',
         'their dates, the booking, and a card or printed voucher to give on the day'),
        ('Something personalised', 'a photo book, an engraved item, or a print of a place that matters to them',
         'photos or the place or words you want, and time for delivery (often one to two weeks)'),
        ('A hobby upgrade', 'a better version of something they already use for a hobby',
         'a quiet look at what they use now, so you get the right size or model'),
        ('A favourites hamper', 'a box of their favourite snacks, drinks and small treats',
         'a box or basket, their favourite things, and a short handwritten note'),
        ('Time together', 'a planned day, a meal you cook, or a trip you organise',
         'a date in both diaries, the plan written down, and anything you need to book')]),
    'rainy_day': (r"\b(?:rainy|raining|wet (?:day|weekend|sunday|saturday)|indoors?|stuck (?:inside|indoors|at home)|bored)\b|\bthings to do\b.*\b(?:inside|indoors|rain|at home)\b", [
        ('Build a blanket fort', 'chairs, sheets and cushions, then torches and a story inside', 'blankets, sheets, chairs, cushions, pegs, and a torch'),
        ('Bake something', 'cookies, flapjacks or a simple cake', 'a simple recipe, the ingredients, a mixing bowl, a tray and an oven'),
        ('Board games tournament', 'a few games with a score chart and a prize', 'three or four games, paper for a score chart, and a small prize'),
        ('Film marathon', 'pick a theme or a series and make it an event', 'two or three films, snacks, and blankets'),
        ('Craft or puzzle', 'a jigsaw, painting, or making a comic', 'a jigsaw or paper, paints or pens, and a table you can leave it on')]),
    'date': (r"\bdate (?:night )?ideas?\b|\bideas? for (?:a )?date\b|\b(?:romantic|anniversary)\b.*\bideas?\b", [
        ('Cook a new recipe together', 'pick a cuisine neither of you has cooked', 'the recipe, the ingredients, music, and something nice to drink'),
        ('A walk somewhere new', 'a park, coast path or town you haven\'t explored, ending at a café', 'the route, comfortable shoes, and a coffee or lunch stop'),
        ('Live music or comedy', 'a small local gig or comedy night', 'tickets and a plan for food before or after'),
        ('At-home tasting night', 'cheese, chocolate or wine to compare and score', 'three to five things to taste, small plates, and score cards'),
        ('Recreate your first date', 'go back to where you met or had your first date', 'the place, a booking if needed, and the story ready to tell')]),
    'dinner': (r"\b(?:dinner|tea|supper|meal)\b.*\bideas?\b|\bideas?\b.*\b(?:dinner|tea|supper|meal)s?\b|\bwhat (?:should|can|could) (?:i|we) (?:have|make|cook) for (?:dinner|tea|supper)\b", [
        ('Stir-fry', 'vegetables, a protein and noodles or rice in 15 minutes', 'a wok or big pan, vegetables, chicken, prawns or tofu, soy sauce, garlic and rice or noodles'),
        ('Pasta bake', 'pasta, tomato sauce and cheese baked until bubbling', 'pasta, a jar or tin of tomato sauce, cheese, and any vegetables you have'),
        ('Fajitas or tacos', 'everyone builds their own', 'wraps or taco shells, peppers, onions, chicken or beans, spices, and toppings like cheese and salsa'),
        ('Omelette or frittata', 'eggs with whatever is in the fridge', 'eggs, cheese, vegetables or ham, and a frying pan'),
        ('Soup and bread', 'a big pot of vegetable or lentil soup', 'onion, carrots, stock, lentils or potatoes, a pot, and some bread')]),
    'weekend': (r"\b(?:weekend|day off|saturday|sunday)\b.*\b(?:ideas?|things to do|plans?)\b|\bthings to do this weekend\b", [
        ('A day trip', 'a nearby town, coast or countryside you haven\'t been to', 'the route or train times, a packed lunch or café stop, and a rain plan'),
        ('A long walk or bike ride', 'a marked trail with a pub or café at the end', 'a route, comfortable shoes or a bike, water and snacks'),
        ('A museum or gallery', 'many are free; pick one exhibition', 'opening times, and a café for afterwards'),
        ('Invite friends round', 'a simple lunch or games afternoon', 'a few invitations, easy food, and a game or two'),
        ('A project at home', 'that thing you keep meaning to do: a shelf, a clear-out, the garden', 'the tools and materials, and one clear finish line')]),
}

FUN_FACTS = [
    "Honey found in ancient Egyptian tombs, thousands of years old, was still edible: honey hardly ever spoils.",
    "Octopuses have three hearts and blue blood.",
    "A day on Venus is longer than its year: it turns once every 243 Earth days but goes round the Sun in 225.",
    "Bananas are berries, but strawberries aren't, in the botanical sense.",
    "There are more possible orders of a shuffled deck of 52 cards than there are atoms on Earth, so a well-shuffled deck is almost certainly in an order no deck has ever been in before.",
    "Sharks are older than trees: sharks appeared around 450 million years ago, trees around 385 million years ago.",
    "Your stomach gets a new lining every few days, so it doesn't digest itself.",
    "The Eiffel Tower is about 15 cm taller in summer, because the iron expands in the heat.",
    "Wombats produce cube-shaped droppings.",
    "A group of flamingos is called a flamboyance.",
]

ASK_IDEAS = re.compile(r"(?i)\b(?:ideas?|suggest(?:ions?)?|recommend|what (?:should|can|could) (?:i|we) (?:do|get|buy|give|make|cook|have))\b")
COUNT = re.compile(r"(?i)\b(two|three|four|five|six|\d)\b")
WORDS = dict(two=2, three=3, four=4, five=5, six=6)
PICK = re.compile(r"(?i)\b(?:the )?(first|second|third|fourth|fifth|sixth|last|1st|2nd|3rd|4th|5th|6th)(?: one| idea| option)?\b|\b(?:number|no\.?|option) (\d)\b")
ORD = dict(first=0, second=1, third=2, fourth=3, fifth=4, sixth=5, last=-1, **{'1st': 0, '2nd': 1, '3rd': 2, '4th': 3, '5th': 4, '6th': 5})
NEED = re.compile(r"(?i)\b(?:what (?:would|do|will|should) (?:we|i) need|what do (?:we|i) need|what(?:'s| is) needed|how (?:do|would|should) (?:we|i) (?:do|plan|organise|organize|set up) (?:it|that|this)|tell me more|sounds good|let'?s do|we'?ll go with|i like)\b")
FACT = re.compile(r"(?i)\b(?:tell me|give me|share|know any|got any)\b.{0,12}\b(?:a |an |another |some )?(?:fun|interesting|random|cool|surprising|weird) (?:facts?|things?)\b|"
                  r"^\s*(?:a )?fun fact\??\s*$|\btell me something (?:interesting|fun|cool|new|surprising|i don'?t know)\b|\bsurprise me\b")
MORE = re.compile(r"(?i)^\s*(?:another(?: one)?|one more|more|again|tell me another|give me another|and another)\b.{0,15}$")


def ideas_list(kind, n):
    items = IDEAS[kind][1][:n]
    lines = [f"{i}. **{name}**: {desc}." for i, (name, desc, _) in enumerate(items, 1)]
    return "Here are a few ideas:\n\n" + '\n'.join(lines) + "\n\nWant me to go into what you'd need for one of them?"


def offered(messages):
    """(kind, ideas shown) from CAEL's last ideas list."""
    for m in reversed(messages[:-1]):
        if m.get('role') != 'assistant':
            continue
        said = m.get('content') or ''
        names = re.findall(r'^\d+\. \*\*([^*]+)\*\*', said, re.M)
        if not names:
            return None
        for kind, (_, items) in IDEAS.items():
            shown = [it for it in items if it[0] in names]
            if shown and len(shown) == len(names):
                return kind, shown
        return None
    return None


def respond(messages):
    text = (messages[-1].get('content') or '').strip()
    if not text or len(text) > 300:
        return None
    said_fact = next((m.get('content') or '' for m in reversed(messages[:-1]) if m.get('role') == 'assistant'), '').startswith("Here's one:")
    if FACT.search(text) or (said_fact and MORE.search(text)):
        said = ' '.join(m.get('content') or '' for m in messages if m.get('role') == 'assistant')
        fresh = [f for f in FUN_FACTS if f[:40] not in said] or FUN_FACTS
        fact = random.Random(len(messages)).choice(fresh)
        return dict(route='chat/fun-fact', response=f"Here's one: {fact}", sources=[], details='Authored fun facts (ideas.py), checked when written.')
    got = offered(messages)
    if got and (PICK.search(text) or NEED.search(text)):
        kind, shown = got
        m = PICK.search(text)
        if m:
            i = ORD.get((m[1] or '').lower(), int(m[2]) - 1 if m[2] else 0)
            if not -len(shown) <= i < len(shown):
                return None
            name, desc, need = shown[i]
        elif len(shown) == 1:
            name, desc, need = shown[0]
        else:
            return None
        return dict(route='chat/ideas-detail', response=f"For **{name.lower()}** ({desc}), you'd need: {need}.\n\nWould you like a rough timetable for it as well?",
                    sources=[], details='Authored idea details (ideas.py).')
    if not ASK_IDEAS.search(text):
        return None
    # the specific kinds first: "gift ideas for my dad's birthday" is about gifts, not a party
    order = ['gift', 'date', 'dinner', 'rainy_day', 'weekend', 'party_kids', 'party_adult']
    for kind in order + [k for k in IDEAS if k not in order]:
        pattern = IDEAS[kind][0]
        if re.search('(?i)' + pattern, text):
            c = COUNT.search(text)
            n = WORDS.get(c[1].lower(), None) if c and not c[1].isdigit() else (int(c[1]) if c else 4)
            if c and re.search(r'(?i)\b' + re.escape(c[1]) + r'[- ]year', text):
                n = 4                       # "10-year-old" is an age, not how many ideas
            n = max(2, min(n or 4, len(IDEAS[kind][1])))
            return dict(route='chat/ideas', response=ideas_list(kind, n), sources=[], details='Authored idea lists (ideas.py).')
    return None
