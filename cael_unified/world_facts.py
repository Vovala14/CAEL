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
    ((r'(?:tallest|highest) (?:building|skyscraper)',), 'The Burj Khalifa in Dubai is the tallest building, at 828 m (2,717 ft); it opened in 2010.'),
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
    # sports
    ((r'how many players (?:are )?(?:on|in) an? (?:soccer|football) team', r'how many players (?:does|do) an? (?:soccer|football) team'),
     'A soccer (football) team has 11 players on the field, including the goalkeeper.'),
    ((r'how many players (?:are )?(?:on|in) an? basketball team',), 'A basketball team has 5 players on the court.'),
    ((r'how many players (?:are )?(?:on|in) an? (?:baseball) team',), 'A baseball team has 9 players on the field.'),
    ((r'how many players (?:are )?(?:on|in) an? (?:volleyball) team',), 'A volleyball team has 6 players on the court.'),
    ((r'how many players (?:are )?(?:on|in) an? (?:hockey|ice hockey) team',), 'An ice hockey team has 6 players on the ice, including the goalie.'),
    ((r'how many players (?:are )?(?:on|in) an? (?:american football|nfl) team',), 'An American football team has 11 players on the field.'),
    ((r'how many players (?:are )?(?:on|in) an? (?:rugby) team',), 'A rugby union team has 15 players; rugby league has 13.'),
    ((r'how many players (?:are )?(?:on|in) an? (?:cricket) team',), 'A cricket team has 11 players.'),
    ((r'how (?:long|many minutes) is an? (?:soccer|football) (?:game|match)',), 'A soccer match lasts 90 minutes: two halves of 45 minutes, plus stoppage time.'),
    ((r'how often (?:are|is) the olympics', r'how often do the olympics'), 'The Summer and Winter Olympic Games are each held every four years, two years apart.'),
    # breathing, plants, body
    ((r'(?:what )?gas (?:do )?(?:humans|people|we|you) (?:breathe|exhale) out', r'what do (?:humans|we|people) (?:breathe|exhale) out', r'what gas do we exhale'),
     'Humans breathe out carbon dioxide (CO₂), along with nitrogen, unused oxygen and water vapour.'),
    ((r'(?:what )?gas (?:do )?(?:humans|people|we|you) (?:breathe in|inhale|need to breathe)', r'what do (?:humans|we) breathe in'),
     'Humans breathe in air and use its oxygen (O₂); air is about 21% oxygen and 78% nitrogen.'),
    ((r'(?:what )?gas do plants (?:take in|absorb|use|need)', r'what do plants (?:take in|absorb) from the air'),
     'Plants take in carbon dioxide (CO₂) from the air and give off oxygen during photosynthesis.'),
    ((r'what do plants (?:give off|release|produce)',), 'Plants release oxygen as a by-product of photosynthesis.'),
    ((r'how many bones does a baby have', r'how many bones (?:is|are) a baby born with'), 'A newborn baby has about 270 to 300 bones; many fuse together, leaving 206 in an adult.'),
    ((r'how many (?:litres|liters) of blood', r'how much blood (?:is in|does) (?:the |a )?(?:human|body|adult|person)'), 'An adult has about 5 litres of blood (roughly 7 to 8% of body weight).'),
    ((r'how many senses',), 'People traditionally list five senses: sight, hearing, smell, taste and touch (balance and others are also senses).'),
    ((r'how many chromosomes',), 'Humans have 46 chromosomes in 23 pairs.'),
    ((r'normal (?:human )?body temperature', r'what is (?:the )?(?:average )?body temperature'), 'Normal human body temperature is about 37 °C (98.6 °F).'),
    ((r'how many hours of sleep (?:do|does|should)',), 'Adults need about 7 to 9 hours of sleep a night; teenagers about 8 to 10, and children more.'),
    # discoveries and inventions
    ((r'who discovered gravity', r'who (?:came up with|explained) gravity'), 'Isaac Newton described gravity with his law of universal gravitation (1687); Einstein later explained it as the curvature of space-time.'),
    ((r'who discovered penicillin',), 'Alexander Fleming discovered penicillin in 1928.'),
    ((r'who invented the (?:light ?bulb|lightbulb)', r'who made the first light ?bulb'),
     'Thomas Edison made the first commercially practical light bulb in 1879; Joseph Swan developed one at the same time in England.'),
    ((r'who invented the telephone',), 'Alexander Graham Bell is credited with inventing the telephone (patented in 1876).'),
    ((r'who invented the (?:airplane|aeroplane|plane)', r'who made the first (?:airplane|plane) flight'), 'The Wright brothers, Orville and Wilbur, made the first powered airplane flight in 1903.'),
    ((r'who invented the (?:internet|world wide web|web)\b',), 'Tim Berners-Lee invented the World Wide Web in 1989; the internet itself grew from ARPANET, designed by Vint Cerf, Bob Kahn and others.'),
    ((r'who invented the (?:printing press)',), 'Johannes Gutenberg invented the movable-type printing press around 1440.'),
    ((r'who discovered electricity',), 'No one person discovered electricity; Benjamin Franklin showed in 1752 that lightning is electrical, and Michael Faraday and others made it usable.'),
    ((r'who discovered america',), 'Indigenous peoples lived in the Americas for thousands of years; Leif Erikson reached North America around 1000, and Christopher Columbus arrived in 1492.'),
    ((r'who (?:proposed|came up with|developed) the theory of evolution', r'who discovered evolution'), 'Charles Darwin (with Alfred Russel Wallace) proposed evolution by natural selection, published in 1859.'),
    ((r'who (?:developed|came up with) the theory of relativity', r'who discovered relativity'), 'Albert Einstein developed the theory of relativity (special relativity in 1905, general relativity in 1915).'),
    # calendar and time
    ((r'how many hours (?:are )?in a day', r'how many hours does a day have'), 'A day has 24 hours.'),
    ((r'how many minutes (?:are )?in an hour',), 'An hour has 60 minutes.'),
    ((r'how many seconds (?:are )?in a minute',), 'A minute has 60 seconds.'),
    ((r'how many seconds (?:are )?in an hour',), 'An hour has 3,600 seconds (60 × 60).'),
    ((r'how many seconds (?:are )?in a day',), 'A day has 86,400 seconds (24 × 60 × 60).'),
    ((r'how many days (?:are )?in a week',), 'A week has 7 days.'),
    ((r'how many months (?:are )?in a year',), 'A year has 12 months.'),
    ((r'how many days (?:are )?in (?:february)',), 'February has 28 days, or 29 in a leap year.'),
    ((r'how many years (?:are )?in a (?:century)',), 'A century is 100 years.'),
    ((r'how many years (?:are )?in a (?:decade)',), 'A decade is 10 years.'),
    # nature and everyday science
    ((r'what colou?rs? (?:are|is) (?:in )?(?:the|a) rainbow', r'colou?rs of the rainbow'), 'A rainbow has seven named colours: red, orange, yellow, green, blue, indigo and violet.'),
    ((r'what colou?r is the sky', r'why is the sky blue'), 'The sky looks blue because air scatters the Sun\'s blue light much more than red light (Rayleigh scattering).'),
    ((r'how many colou?rs (?:are )?in (?:the|a) rainbow',), 'A rainbow is usually described with seven colours: red, orange, yellow, green, blue, indigo and violet.'),
    ((r'what are the primary colou?rs',), 'The traditional primary colours are red, yellow and blue; for light (screens) they are red, green and blue.'),
    ((r'what are the three states of matter', r'states of matter'), 'The three everyday states of matter are solid, liquid and gas (plasma is a fourth).'),
    ((r'how far is the moon', r'distance (?:from|between) (?:the )?earth (?:to|and) (?:the )?moon'), 'The Moon is about 384,400 km (238,900 miles) from Earth on average.'),
    ((r'how far is the sun', r'distance (?:from|between) (?:the )?earth (?:to|and) (?:the )?sun'), 'The Sun is about 150 million km (93 million miles) from Earth.'),
    ((r'how old is the earth', r'age of the earth'), 'Earth is about 4.54 billion years old.'),
    ((r'how old is the universe', r'age of the universe'), 'The universe is about 13.8 billion years old.'),
    ((r'how long does it take (?:for )?(?:the )?earth to (?:go around|orbit|circle) the sun',), 'Earth takes about 365.25 days to orbit the Sun, which is why we add a leap day every four years.'),
    ((r'how long does it take (?:for )?light (?:from the sun )?to (?:reach|get to) (?:the )?earth', r'how long does sunlight take'),
     'Sunlight takes about 8 minutes and 20 seconds to reach Earth.'),
    ((r'what is the (?:main|most common) gas in (?:the )?(?:air|atmosphere)', r'what is air made of'), 'Air is about 78% nitrogen and 21% oxygen, with argon, carbon dioxide and other gases making up the rest.'),
    ((r'what is the hardest (?:natural )?(?:substance|material|mineral)', r'hardest thing on earth'), 'Diamond is the hardest natural material.'),
    ((r'what is the moon made of', r'what(?: is|\'s) the moon made (?:of|from)'),
     'The Moon is made of rock: a crust of silicate rock (mostly feldspar-rich minerals and basalt), a rocky mantle and a small iron-rich core, covered in fine dust called regolith.'),
    ((r'why do (?:the )?leaves change colou?r', r'why do leaves turn (?:red|yellow|orange|brown)', r'why do leaves change in (?:autumn|fall)'),
     'In autumn, trees stop making green chlorophyll, so the yellow and orange pigments (carotenoids) that were hidden show through; some trees also make red pigments (anthocyanins).'),
    ((r'why (?:do|does) (?:we|the earth) have seasons', r'what causes (?:the )?seasons'),
     'Earth has seasons because its axis is tilted about 23.4°, so each hemisphere gets more direct sunlight for part of the year (summer) and less for the other part (winter).'),
    ((r'why is the (?:sea|ocean) salty', r'why are (?:the )?oceans salty'),
     'The sea is salty because rivers carry dissolved minerals from rocks into the ocean; when water evaporates, the salt stays behind.'),
    ((r'what causes thunder', r'why does thunder happen'), 'Thunder is the sound of air expanding explosively when a lightning bolt heats it to about 30,000 °C.'),
    ((r'why do stars twinkle',), 'Stars twinkle because moving layers of air in Earth\'s atmosphere bend their light slightly in changing directions.'),
    # animals and food
    ((r'(?:what|which) animal (?:lives|lived) the longest', r'longest living animal'), 'The Greenland shark can live around 400 years, the longest of any known vertebrate; some clams and sponges live even longer.'),
    ((r'smallest (?:mammal)',), 'The Etruscan shrew (by weight) and the bumblebee bat are the smallest mammals.'),
    ((r'(?:largest|biggest) mammal',), 'The blue whale is the largest mammal; on land it is the African bush elephant.'),
    ((r'what do (?:pandas) eat',), 'Giant pandas eat almost only bamboo, up to about 12 to 38 kg a day.'),
    ((r'what do (?:cows) eat',), 'Cows eat grass, hay and other plants; they are herbivores with a four-part stomach.'),
    ((r'what is the main ingredient (?:in|of) (?:guacamole)',), 'Avocado is the main ingredient of guacamole.'),
    ((r'what is the main ingredient (?:in|of) (?:hummus)',), 'Chickpeas are the main ingredient of hummus, with tahini, lemon juice and garlic.'),
    ((r'what is the main ingredient (?:in|of) (?:bread)',), 'Flour is the main ingredient of bread, with water, yeast and salt.'),
]
COMPILED = [([re.compile(r'\b' + p) for p in patterns], answer) for patterns, answer in FACTS]
QUESTION = re.compile(r'(?i)^\s*(?:what|which|who|how|when|why|in what|where|tell me|name)\b')


def reply(text):
    if len(text) > 160 or not QUESTION.match(text):
        return None
    q = re.sub(r'\s+', ' ', text.lower().strip().rstrip('?.!'))
    q = re.sub(r'\bour solar system\b', 'the solar system', q)
    for patterns, answer in COMPILED:
        for p in patterns:
            m = p.search(q)
            if not m:
                continue
            # A narrower place than the fact covers: "the largest bone in the human foot" is not the femur.
            rest = q[m.end():]
            scope = re.search(r'\b(?:in|of|on|inside) (?:the |a |an |our )?([a-z]+(?: [a-z]+)?)', rest)
            if scope and not re.search(r'\b(?:world|earth|planet|universe|solar system|human body|body|history|nature|sea|ocean|wild|space|'
                                       r'autumn|fall|winter|summer|spring|the air|air|a day|an hour|a year|a week|a minute|total)\b', scope[1] + rest):
                return None
            return dict(response=answer, route='chat/world-fact', sources=[], details=DETAILS)
    return None
