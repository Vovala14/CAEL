FILLER = """Ugh, the weather can't make up its mind today.
I keep losing my pens, it's ridiculous.
Do you ever just stare out of the window for a while?
I've been humming the same tune all morning.
My neighbour's lawnmower woke me up.
I really should stretch more.
The shop around the corner has started selling fresh bread.
I tried a new podcast yesterday, it was just okay.
I think my laptop fan is getting louder.
Honestly I could use a long nap.
I watched a documentary about octopuses last night.
Why do printers always jam when you're in a hurry?
I'm trying to drink more water.
There's a strange noise coming from the fridge.
I finally cleaned out my inbox.
Do you think people still write letters?
I'm in a baking mood but have no flour.
The sunset looked amazing earlier.
My headphones keep tangling themselves.
I've been reading the same chapter for ages.
Sometimes I wish I could type faster.
The streets were super quiet this morning.
I'm thinking about rearranging my desk.
Is it weird that I like the sound of rain?
I need new socks, all mine have holes.
Someone left a puzzle in the shared hallway.
I tried juggling and failed spectacularly.
The lift was out of order, as usual.
I love the smell of freshly cut grass.
My phone battery drains so fast lately.
I found an old photo album today.
Is it too early to start thinking about holidays?
I'm learning to whistle properly.
The neighbours are having a barbecue, smells great.
I never know what to do with leftover rice.
Sorry, I'm a bit distracted today.
There's a spider on my ceiling, we're coexisting.
I keep forgetting to water my plants.
Do you like thunderstorms?
I spent ages untangling a ball of string.
The wifi has been so flaky.
I made a really good playlist.
I'm obsessed with crossword puzzles right now.
Winter is coming and I'm not ready.
My chair squeaks every time I lean back.
I keep putting off errands.
Funny how time speeds up on weekends.
I just ate a perfectly ripe pear.
The cafe nearby plays really good music.
I wonder how clouds stay up there.
I should really learn to cook more things.
A pigeon walked right into the shop earlier.
I think I'm getting a little bit sleepy.
Do you ever get songs stuck in your head?
I tidied my bookshelf and feel accomplished.
The moon is really bright tonight.
I dropped my toast butter-side down, naturally.
My fingers are freezing.
I love a good cardigan.
Binge-watching old sitcoms is my guilty pleasure.
Why is it so hard to fold a fitted sheet?
The floor is cold in the mornings.
I saw a really funny sign on a shop door.
I'm bad at remembering jokes.
My candle smells like vanilla.
I think I'll have soup later.
There's a lot of construction noise nearby.
I got stuck in a really long queue earlier.
I'm hopeless at parallel parking.
Do you think robots will ever do the dishes?
My plant seems happier since I moved it.
I discovered a new kind of jam today.
I like walking without a destination.
The lobby music here is hilarious.
My pillow has gone flat.
I hate it when a zip gets stuck.
Somebody was whistling in the stairwell.
I wish I had more shelf space.
I tried to draw a horse and it looked like a table.
Mornings are easier with a bit of music.
My handwriting has gotten terrible.
I saw a hedgehog in the garden last night.
There's something satisfying about a tidy inbox.
I keep meaning to fix that wobbly shelf.
The bakery smell on my street is dangerous.
I got a bit sunburnt on my nose.
I'm bad at small talk with strangers.
I could eat toast all day.
That film everyone's talking about looks overrated.
The wind turned my brolly inside out.
Every time I sit down, someone calls.
I've started doodling during calls.
I like how quiet it gets after it snows.
Do you think it's too late to learn the violin?
I should really back up my photos.
Someone nearby is practising drums.
I just realised I've been wearing mismatched socks.
Breakfast is my favourite meal.
I need to stop doomscrolling.
The light in my room is strange today.
I'd love a lazy afternoon in a deckchair.
My shoelaces keep coming undone.
I overheard a funny conversation on the street.
It smells like autumn today.
I'm wondering what to cook tomorrow.
I really enjoy folding laundry, weirdly.
The tap in my kitchen drips constantly.
I swear my clock runs fast.
Do you prefer mornings or evenings?
I wonder if bees get tired.
Someone left a kind note on my door.
The air feels so fresh after the rain.
I need a bookmark that actually stays put.
I need to find a better mug.
People who clap when planes land baffle me.
I spilled a little juice on my sleeve.
I'd like to try pottery someday.
I always get lost in big supermarkets.
Anyway, just chatting.
My elbow has been clicking lately.
Isn't it odd how quiet libraries are?
I keep humming in the shower.
Cheese on toast is underrated.""".split("\n")

PREFIX = ["", "", "", "", "btw, ", "anyway, ", "oh, ", "random, but ", "hm, ", "so yeah, ", "lol ", "honestly, "]

AR = ["Okay.", "Got it.", "Nice!", "Sure.", "Alright.", "Right.", "Makes sense.", "Ah, I see.", "Cool.", "Noted.",
      "Sounds good.", "Oh nice.", "Fair enough.", "Mm-hm.", "I hear you.", "Understood.", "Great.", "Ha, okay.",
      "Thanks for telling me.", "Yep.", "I see.", "Oh, okay.", "Hah, true.", "Fine by me.", "Interesting.", "Okay, cool.",
      "Sure thing.", "Gotcha.", "Ah.", "That's fair."]

FN = ["Maya", "Lena", "Priya", "Sofia", "Hana", "Ingrid", "Yara", "Nora", "Tess", "Carla", "Mina", "Rosa", "Dana", "Elif", "Greta", "Isla", "Wanda", "Zoe"]
MN = ["Tomas", "Ben", "Omar", "Felix", "Diego", "Anton", "Kofi", "Ravi", "Hugo", "Leo", "Sven", "Marcus", "Idris", "Pavel", "Callum", "Bruno2", "Nils", "Joaquin"]
MN = [n for n in MN if "2" not in n]
CITIES = ["Lisbon", "Oslo", "Denver", "Kyoto", "Leeds", "Porto", "Tallinn", "Austin", "Bruges", "Cork", "Dundee", "Graz", "Malmo", "Perth", "Quebec", "Seville", "Turin", "Utrecht", "Valencia", "Wellington", "Zagreb", "Bergen", "Galway", "Nantes", "Ghent"]
COLOURS = ["red", "blue", "green", "yellow", "orange", "purple", "pink", "grey", "black", "white", "brown", "teal"]
OBJS = ["umbrella", "passport", "charger", "wallet", "scarf", "racket", "notebook", "headphones", "stapler", "torch"]
LOCS = ["garage", "attic", "basement", "hallway", "balcony", "pantry", "wardrobe", "cellar", "shed", "drawer", "bookcase", "porch"]
SPECIES = ["cat", "dog", "rabbit", "parrot", "hamster", "tortoise"]
PETN = ["Biscuit", "Pickle", "Juno", "Mochi", "Waffles", "Pepper", "Nugget", "Olive", "Ziggy", "Clover", "Maple", "Bruno"]
JOBS = ["nurse", "plumber", "architect", "baker", "pilot", "dentist", "electrician", "librarian", "translator", "carpenter", "chemist", "journalist"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
FOODS = ["ramen", "tacos", "paella", "pierogi", "falafel", "risotto", "dumplings", "curry"]
SUBJECTS = ["geology", "linguistics", "economics", "chemistry", "philosophy", "forestry", "astronomy", "musicology"]
GIFTS = ["telescope", "cookbook", "backpack", "kettle", "hammock", "ukulele", "lantern", "sketchbook"]
DRINKS = ["cider", "kombucha", "lemonade", "matcha", "cocoa", "ginger"]
DESSERTS = ["tiramisu", "baklava", "cheesecake", "pavlova", "gelato", "brownies"]
STREETS = ["Maple", "Harbour", "Willow", "Cedar", "Station", "Orchard", "Mill", "Church"]
VENUES = ["library", "barn", "rooftop", "boathouse", "clubhouse", "greenhouse"]
PACK = ["raincoat", "tent", "camera", "flask", "compass", "towel", "binoculars", "journal"]
SURN = ["Okafor", "Lindqvist", "Marlow", "Petrov", "Haddad", "Brandt", "Kowalski", "Fenwick"]
AIR = ["Nordair", "Skyvale", "Aerolune", "Bluejet", "Cirrus"]
HOTELS = ["Marlowe", "Larkspur", "Ashgrove", "Belvedere", "Cormorant"]

NW = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
      11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen",
      19: "nineteen", 20: "twenty"}

PLANS = [
    ("repaint the garden fence", "fence", [("sand the boards", "sand"), ("prime the wood", "prime"), ("brush on two coats", "coats"), ("rehang the gate", "gate")]),
    ("move to a new flat", "flat", [("book a van", "van"), ("pack the books", "books"), ("cancel the broadband", "broadband"), ("hand back the keys", "keys")]),
    ("launch a newsletter", "newsletter", [("pick a platform", "platform"), ("write the first issue", "issue"), ("collect some emails", "emails"), ("schedule the send", "schedule")]),
    ("learn the guitar", "guitar", [("buy a tuner", "tuner"), ("learn three chords", "chords"), ("practise scales", "scales"), ("play for friends", "friends")]),
    ("start a vegetable garden", "vegetable", [("clear the weeds", "weeds"), ("build raised beds", "beds"), ("order seeds", "seeds"), ("install a water butt", "butt")]),
    ("organise a school reunion", "reunion", [("pick a date", "date"), ("book the hall", "hall"), ("send invitations", "invitations"), ("arrange catering", "catering")]),
    ("finish a thesis chapter", "chapter", [("outline the argument", "outline"), ("draft the introduction", "introduction"), ("collect citations", "citations"), ("proofread everything", "proofread")]),
    ("run a 10k", "10k", [("get shoes fitted", "shoes"), ("build up to five kilometres", "kilometres"), ("sign up for the race", "race"), ("taper in the final week", "taper")]),
]
EXTRAS = [("take photos of the result", "photos"), ("throw a small party", "party"), ("write a thank-you card", "card"), ("tell the neighbours", "neighbours")]
