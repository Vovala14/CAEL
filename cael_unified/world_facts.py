"""Well-known world facts CAEL can state directly: superlatives, counts, firsts and physical constants.

Hand-written for CAEL (facts are not copyrightable; no dataset text is copied). Each entry is a set of question
patterns and one short answer with the reason. Where a fact depends on how it is measured, the answer says so
("by area", "above sea level", "the Amazon may be longer by some measurements").
"""
import re

DETAILS = 'A well-known fact from CAEL\'s hand-written world-facts table. No web lookup and no neural model.'

# (patterns, answer). Patterns are matched against the lower-cased question without the final punctuation.
FACTS = [
    # planets and space
    ((r'(?:largest|biggest) planet',), 'Jupiter is the largest planet in the Solar System, more than 11 times wider than Earth.'),
    ((r'smallest planet',), 'Mercury is the smallest planet in the Solar System (Pluto is now classed as a dwarf planet).'),
    ((r'hottest planet',), 'Venus is the hottest planet (about 465 °C on the surface), because its thick carbon dioxide atmosphere traps heat.'),
    ((r'coldest planet',), 'Uranus has the coldest measured atmosphere (about −224 °C), although Neptune is farther from the Sun.'),
    ((r'(?:closest|nearest) planet to (?:the )?sun', r'first planet from the sun'), 'Mercury is the closest planet to the Sun.'),
    ((r'(?:farthest|furthest) planet from (?:the )?sun', r'last planet'), 'Neptune is the farthest planet from the Sun (Pluto is a dwarf planet).'),
    ((r'(?:closest|nearest) star to (?:the )?earth', r'(?:closest|nearest) star\b'), 'The Sun is the closest star to Earth; the next closest is Proxima Centauri, about 4.25 light-years away.'),
    ((r'how many planets',), 'There are eight planets in the Solar System: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus and Neptune.'),
    ((r'how many moons does (?:the )?earth have', r'how many moons (?:does|has) earth'), 'Earth has one natural satellite, the Moon.'),
    ((r'red planet',), 'Mars is called the Red Planet because iron oxide (rust) on its surface makes it look red.'),
    ((r'first (?:person|man|human) (?:to walk |to step |to land )?on the moon', r'who walked on the moon first'),
     'Neil Armstrong was the first person to walk on the Moon, on 20 July 1969 (Apollo 11).'),
    ((r'first (?:person|man|human) in(?:to)? space',), 'Yuri Gagarin was the first person in space, on 12 April 1961 (Vostok 1).'),
    ((r'first woman in(?:to)? space',), 'Valentina Tereshkova was the first woman in space, in June 1963 (Vostok 6).'),
    # Earth
    ((r'(?:largest|biggest) ocean',), 'The Pacific Ocean is the largest ocean, covering about a third of Earth\'s surface.'),
    ((r'smallest ocean',), 'The Arctic Ocean is the smallest ocean.'),
    ((r'deepest ocean',), 'The Pacific Ocean is the deepest ocean; its Mariana Trench reaches about 11,000 m.'),
    ((r'deepest (?:point|place)',), 'The Challenger Deep in the Mariana Trench (Pacific Ocean) is the deepest known point, about 10,900 m deep.'),
    ((r'how many oceans',), 'There are five oceans: the Pacific, Atlantic, Indian, Southern (Antarctic) and Arctic.'),
    ((r'how many continents',), 'There are seven continents in the most common model: Africa, Antarctica, Asia, Australia (Oceania), Europe, North America and South America.'),
    ((r'(?:largest|biggest) continent',), 'Asia is the largest continent by both area and population.'),
    ((r'smallest continent',), 'Australia (Oceania) is the smallest continent.'),
    ((r'(?:tallest|highest) mountain(?! in (?!the world|earth))',), 'Mount Everest is the highest mountain above sea level, at 8,849 m (Mauna Kea is taller measured from its base on the sea floor).'),
    ((r'(?:tallest|highest) mountain in europe',), 'Mount Elbrus (5,642 m) in Russia is the highest mountain in Europe; Mont Blanc (4,806 m) is the highest in Western Europe.'),
    ((r'(?:tallest|highest) mountain in (?:africa)',), 'Mount Kilimanjaro (5,895 m) in Tanzania is the highest mountain in Africa.'),
    ((r'(?:tallest|highest) mountain in (?:north america)',), 'Denali (6,190 m) in Alaska is the highest mountain in North America.'),
    ((r'(?:tallest|highest) mountain in (?:south america)',), 'Aconcagua (6,961 m) in Argentina is the highest mountain in South America.'),
    ((r'longest river(?! in (?!the world|earth))',), 'The Nile is usually listed as the longest river (about 6,650 km); by some measurements the Amazon is longer.'),
    ((r'longest river in africa',), 'The Nile is the longest river in Africa (about 6,650 km).'),
    ((r'longest river in (?:south america)',), 'The Amazon is the longest river in South America (about 6,400 km).'),
    ((r'longest river in (?:europe)',), 'The Volga is the longest river in Europe (about 3,530 km).'),
    ((r'longest river in (?:north america|the us|the usa|the united states|america)',), 'The Missouri River is the longest river in North America\'s United States (about 3,770 km); the Mississippi is about 3,730 km.'),
    ((r'longest river in asia',), 'The Yangtze is the longest river in Asia (about 6,300 km).'),
    ((r'(?:largest|biggest) desert',), 'Antarctica is the largest desert (a cold desert); the Sahara is the largest hot desert.'),
    ((r'(?:largest|biggest) hot desert',), 'The Sahara is the largest hot desert, covering much of North Africa.'),
    ((r'(?:largest|biggest) (?:freshwater )?lake',), 'The Caspian Sea is the largest lake by area; Lake Superior is the largest freshwater lake by area, and Lake Baikal holds the most fresh water.'),
    ((r'(?:largest|biggest) island',), 'Greenland is the largest island (Australia is counted as a continent).'),
    ((r'(?:largest|biggest) rainforest',), 'The Amazon rainforest is the largest tropical rainforest.'),
    ((r'(?:highest|tallest) waterfall',), 'Angel Falls in Venezuela is the highest uninterrupted waterfall, at 979 m.'),
    ((r'coldest (?:place|continent)',), 'Antarctica is the coldest place on Earth; the lowest measured air temperature, −89.2 °C, was at Vostok Station.'),
    ((r'hottest (?:place|temperature)',), 'The highest recorded air temperature, 56.7 °C, was measured in Death Valley, California, in 1913.'),
    # countries and cities
    ((r'(?:largest|biggest) country(?! in (?!the world))',), 'Russia is the largest country by area, about 17.1 million km².'),
    ((r'smallest country',), 'Vatican City is the smallest country, about 0.49 km².'),
    ((r'most populous country', r'country with the most people', r'(?:largest|biggest) country by population'),
     'India is the most populous country (it passed China in 2023); each has over 1.4 billion people.'),
    ((r'(?:largest|biggest) city(?! in (?!the world))', r'most populous city'), 'Tokyo is usually listed as the largest metropolitan area, with about 37 million people.'),
    ((r'how many countries',), 'There are 195 countries: 193 United Nations member states plus 2 observer states (Vatican City and Palestine).'),
    # animals
    ((r'(?:largest|biggest) animal(?! on land)',), 'The blue whale is the largest animal ever known, up to about 30 m long.'),
    ((r'(?:largest|biggest) land animal',), 'The African bush elephant is the largest land animal.'),
    ((r'(?:tallest|highest) animal',), 'The giraffe is the tallest animal, up to about 5.5 m.'),
    ((r'fastest (?:land )?animal(?! in the (?:sea|water))',), 'The cheetah is the fastest land animal (about 100–120 km/h in short bursts); the peregrine falcon is the fastest animal in a dive.'),
    ((r'fastest bird',), 'The peregrine falcon is the fastest bird, over 300 km/h in a dive.'),
    ((r'(?:largest|biggest) bird',), 'The ostrich is the largest living bird.'),
    ((r'smallest bird',), 'The bee hummingbird is the smallest bird, about 5 cm long.'),
    ((r'(?:largest|biggest) fish',), 'The whale shark is the largest fish, up to about 18 m long.'),
    ((r'how many legs does an? (?:spider|arachnid)', r'how many legs (?:do|have) spiders'), 'A spider has eight legs.'),
    ((r'how many legs does an? (?:insect|ant|bee|fly|beetle|butterfly)', r'how many legs (?:do|have) insects'), 'An insect has six legs.'),
    ((r'how many hearts does an? octopus', r'how many hearts (?:do|have) octopus'), 'An octopus has three hearts.'),
    ((r'how many legs does an? (?:octopus)',), 'An octopus has eight arms.'),
    # human body
    ((r'how many bones (?:are )?(?:in|does) (?:the |an? )?(?:adult )?(?:human|body|person)', r'how many bones in the human body'),
     'An adult human has 206 bones (babies are born with about 270, and some fuse as they grow).'),
    ((r'how many teeth (?:does an? )?(?:adult|human)', r'how many teeth do adults have'), 'An adult has 32 teeth, including the four wisdom teeth.'),
    ((r'(?:largest|biggest) organ',), 'The skin is the largest organ of the human body.'),
    ((r'(?:largest|biggest) bone',), 'The femur (thigh bone) is the largest and longest bone in the human body.'),
    ((r'smallest bone',), 'The stapes, in the middle ear, is the smallest bone in the human body.'),
    ((r'how many chambers (?:does|are in) the (?:human )?heart',), 'The human heart has four chambers: two atria and two ventricles.'),
    # time and physics
    ((r'how many days (?:are )?in a leap year', r'how many days does a leap year have'), 'A leap year has 366 days (February has 29).'),
    ((r'how many days (?:are )?in a year', r'how many days does a year have'), 'A normal year has 365 days; a leap year has 366.'),
    ((r'how many weeks (?:are )?in a year',), 'A year has 52 weeks and 1 day (2 days in a leap year).'),
    ((r'boiling point of water(?! in (?:fahrenheit|f\b))', r'water boil(?:s)? (?:at|in celsius)', r'temperature does water boil(?! in fahrenheit)'),
     'Water boils at 100 °C (212 °F) at sea-level pressure.'),
    ((r'boiling point of water in (?:fahrenheit|f\b)', r'water boil[a-z]* in fahrenheit'), 'Water boils at 212 °F (100 °C) at sea-level pressure.'),
    ((r'freezing point of water', r'water freeze', r'temperature does water freeze'), 'Water freezes at 0 °C (32 °F).'),
    ((r'speed of light',), 'Light travels at 299,792,458 m/s in a vacuum (about 300,000 km/s).'),
    ((r'speed of sound',), 'Sound travels at about 343 m/s in air at 20 °C.'),
    ((r'chemical symbol for gold',), 'The chemical symbol for gold is Au (from Latin aurum).'),
    ((r'chemical symbol for (?:silver)',), 'The chemical symbol for silver is Ag (from Latin argentum).'),
    ((r'chemical symbol for (?:iron)',), 'The chemical symbol for iron is Fe (from Latin ferrum).'),
    ((r'chemical (?:formula|symbol) for water',), 'The chemical formula for water is H₂O: two hydrogen atoms and one oxygen atom.'),
    ((r'how many elements (?:are )?(?:in|on) the periodic table',), 'There are 118 known chemical elements on the periodic table.'),
    # history
    ((r'(?:world war (?:ii|2|two)|second world war)\b.*\b(?:end|finish)', r'when did ww2 end'), 'World War II ended in 1945 (on 2 September 1945 in the Pacific; 8 May 1945 in Europe).'),
    ((r'(?:world war (?:ii|2|two)|second world war)\b.*\b(?:begin|start)', r'when did ww2 (?:start|begin)'), 'World War II began in 1939, when Germany invaded Poland on 1 September 1939.'),
    ((r'(?:world war (?:i|1|one)|first world war)\b.*\b(?:end|finish)', r'when did ww1 end'), 'World War I ended in 1918, with the armistice of 11 November 1918.'),
    ((r'(?:world war (?:i|1|one)|first world war)\b.*\b(?:begin|start)', r'when did ww1 (?:start|begin)'), 'World War I began in 1914 (28 July 1914).'),
]
COMPILED = [([re.compile(r'\b' + p) for p in patterns], answer) for patterns, answer in FACTS]
QUESTION = re.compile(r'(?i)^\s*(?:what|which|who|how|when|in what|where|tell me|name)\b')


def reply(text):
    if len(text) > 160 or not QUESTION.match(text):
        return None
    q = re.sub(r'\s+', ' ', text.lower().strip().rstrip('?.!'))
    q = re.sub(r'\bour solar system\b', 'the solar system', q)
    for patterns, answer in COMPILED:
        if any(p.search(q) for p in patterns):
            return dict(response=answer, route='chat/world-fact', sources=[], details=DETAILS)
    return None
