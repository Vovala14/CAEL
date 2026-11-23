"""Short authored explanations for common "why / how / what's the difference" questions (0.4.4). Non-neural: each entry
needs all of its key terms in the question, so an entry only answers the question it was written for."""
import re

ROUTE = 'chat/explain'

# (all of these terms must appear, as regex fragments), answer
ENTRIES = [
    # ---- language
    (['affect', 'effect'], '"Affect" is usually a verb meaning to influence ("The rain affected the match"). "Effect" is usually a noun meaning a result ("The rain had an effect on the match"). Rarer uses: "effect" as a verb means to bring about ("to effect change"), and "affect" as a noun is a psychology term for displayed emotion.'),
    ([r"\bits\b", r"\bit'?s\b"], '"It\'s" is short for "it is" or "it has" ("It\'s raining", "It\'s been ages"). "Its" is the possessive, like "his" or "her", with no apostrophe ("The dog wagged its tail").'),
    (['their', 'there', "they'?re"], '"Their" shows possession ("their house"), "there" is a place or introduces a statement ("over there", "there is"), and "they\'re" is short for "they are".'),
    (['your', "you'?re"], '"Your" shows possession ("your coat"); "you\'re" is short for "you are" ("you\'re late").'),
    (['fewer', 'less'], 'Traditionally, "fewer" is for things you can count ("fewer apples") and "less" for amounts you can\'t ("less water"). In everyday speech "less" is often used for both, but careful writing keeps the distinction.'),
    (['then', 'than'], '"Than" compares ("taller than me"); "then" is about time or sequence ("first this, then that") or consequence ("if so, then...").'),
    (['principal', 'principle'], 'A "principal" is a head person (a school principal) or main ("the principal reason"); a "principle" is a rule or belief ("a matter of principle").'),
    (['lose', 'loose'], '"Lose" is a verb, to misplace or fail to win ("lose a key"); "loose" is an adjective, not tight ("a loose screw").'),
    (['whom', r'\bwho\b'], '"Who" is the subject (who did it: "Who called?"); "whom" is the object (it was done to them: "To whom did you write?"). A quick test: if "he" fits, use "who"; if "him" fits, use "whom".'),
    (['i\\.?e\\.?', 'e\\.?g\\.?'], '"e.g." (Latin exempli gratia) means "for example" and introduces examples; "i.e." (id est) means "that is" and introduces a restatement or the exact thing meant.'),
    ([r"leap'?\s*year", r'called|name|why'], 'In an ordinary year a date moves forward one weekday from one year to the next (365 days is 52 weeks plus 1 day). After 29 February is added, dates after it jump, or "leap", forward two weekdays, skipping one: hence "leap year". The extra day keeps the calendar in step with Earth\'s orbit of about 365.24 days.'),
    (['oxford comma|serial comma'], 'The Oxford (serial) comma is the comma before "and" or "or" at the end of a list: "red, white, and blue". Some style guides use it, others drop it; it can prevent ambiguity ("my parents, Ann, and Tom" versus "my parents, Ann and Tom").'),
    (['palindrome'], 'A palindrome reads the same backwards and forwards, like "level", "racecar" or "never odd or even" (ignoring spaces and punctuation).'),
    (['acronym', 'initialism'], 'An acronym is pronounced as a word (NASA, laser); an initialism is said letter by letter (BBC, FBI). Many people call both acronyms.'),
    # ---- physics and everyday science
    (['spoon|straw|pencil|stick', 'bent|broken|bend', 'water|glass'], 'Refraction. Light travels more slowly in water than in air, so it changes direction where it crosses the surface. Your eyes assume light travels in straight lines, so the part of the spoon under water appears in a different place from where it really is, and the spoon looks bent at the surface.'),
    (['thermos|vacuum flask|flask', 'hot|cold|warm'], 'A thermos has two walls with a vacuum between them. Heat normally moves by conduction and convection, and both need matter, so the vacuum blocks them; the shiny inner surfaces reflect heat radiation back; and the stopper limits heat lost from the top. Heat still leaks slowly, so drinks cool over hours, not minutes.'),
    (['balloon', 'stick|stuck|cling', 'hair|wool|rub'], 'Static electricity. Rubbing the balloon on your hair moves electrons onto the balloon, giving it a negative charge. Near the wall, that charge pushes the wall\'s electrons slightly away, leaving the nearby surface slightly positive, and opposite charges attract, so the balloon sticks until the charge leaks away.'),
    (['compass', 'north'], 'A compass needle is a small magnet that can turn freely. Earth behaves like a giant magnet, and the needle lines up with Earth\'s magnetic field, so one end points to magnetic north. Magnetic north is close to, but not exactly at, the geographic North Pole; maps give the difference (the declination).'),
    (['bicycle|bike', 'upright|balance|fall'], 'Mostly through steering. When a moving bike starts to lean, the rider (and the bike\'s front-fork geometry) turns the front wheel into the lean, which moves the wheels back under the centre of mass. Speed makes these small corrections effective; gyroscopic effects of the wheels help a little but are not the main reason.'),
    (['noise.cancell', 'how|work'], 'Microphones on the headphones pick up the surrounding sound, and electronics play an "anti-noise" wave that is the mirror image of it (peaks where it has troughs). The two waves cancel each other out, a process called destructive interference. It works best on steady low sounds such as engine hum.'),
    (['microwave', 'heat|cook|work'], 'A microwave oven makes microwaves that make water molecules in food flip back and forth rapidly as the field oscillates. That motion becomes heat, so the food cooks from the water inside it. The metal box and the mesh in the door keep the microwaves in.'),
    (['rainbow'], 'Sunlight is made of all colours. When it enters raindrops it bends (refracts), reflects off the back of the drop and bends again on the way out. Each colour bends by a slightly different amount, so the colours spread out into a band. You see a rainbow with the Sun behind you and rain in front.'),
    (['plane|aeroplane|airplane', 'fly|stay up|lift'], 'The wings are shaped and angled so that air moving over them is pushed downwards. By Newton\'s third law the air pushes the wing up: that is lift. The engines provide thrust to keep air flowing over the wings fast enough for the lift to match the plane\'s weight.'),
    (['boat|ship', 'float'], 'A boat floats because it pushes aside (displaces) water, and the water pushes back up with a force equal to the weight of the water displaced (Archimedes\' principle). A steel ship is mostly air inside, so its hull displaces enough water to equal its weight before it sinks too deep.'),
    (['moon', 'phase|shape|change'], 'The Moon is always half lit by the Sun. As it orbits Earth over about 29.5 days, we see different amounts of that lit half, from none (new moon) to all of it (full moon) and back. That changing view is the phases.'),
    (['tide'], 'Tides are caused mainly by the Moon\'s gravity, which pulls the ocean into two bulges, one facing the Moon and one on the far side. As Earth rotates, a coast passes through both bulges, so most places get two high and two low tides about every 24 hours 50 minutes. The Sun adds to or reduces the effect (spring and neap tides).'),
    (['sunset|sunrise', 'red|orange'], 'At sunrise and sunset sunlight passes through much more air to reach you. Air scatters blue light most, so most of the blue is scattered away along that long path, and the light that gets through is richer in red and orange.'),
    (['water', 'boil', 'mountain|altitude|higher'], 'Air pressure is lower at altitude, and water boils when its vapour pressure equals the surrounding pressure. With less pressure pushing down, water boils at a lower temperature, around 90 °C at 3,000 m, so food cooks more slowly.'),
    (['sweat|sweating', 'cool'], 'Sweat cools you as it evaporates: turning liquid water into vapour takes energy, and that energy is taken as heat from your skin. In humid air sweat evaporates slowly, so it cools you less.'),
    (['yawn'], 'Nobody is completely sure. Leading ideas are that yawning helps cool the brain and helps shift alertness when we\'re tired or bored. It\'s also contagious, probably as a social signal.'),
    (['hiccup'], 'Hiccups are sudden involuntary spasms of the diaphragm, the muscle under the lungs. Each spasm pulls in air, and the vocal cords snap shut, which makes the "hic" sound. Common triggers are eating fast, fizzy drinks or swallowing air.'),
    (['goosebump|goose bump|goose pimple'], 'Tiny muscles at the base of each hair contract, pulling the hairs upright and raising the skin around them. It\'s a reflex left over from furrier ancestors, for whom raised fur trapped warm air or made them look bigger. Cold or strong emotion triggers it.'),
    (['onion', 'cry|tears|eyes'], 'Cutting an onion breaks its cells and lets enzymes turn sulphur compounds into a gas (syn-propanethial-S-oxide). The gas reaches your eyes and irritates them, so they make tears to wash it away.'),
    (['cut', 'apple|avocado|banana|potato', 'brown'], 'Cutting breaks open cells and lets an enzyme (polyphenol oxidase) react with oxygen from the air, turning natural compounds into brown pigments. Lemon juice slows it by making the surface acidic, and cold slows it too.'),
    (['popcorn', 'pop'], 'Each kernel holds a little water inside a hard shell. Heated, the water turns to steam and pressure builds until the shell bursts, and the starch inside puffs up and sets as foam.'),
    (['soap|detergent', 'clean|grease|dirt|work'], 'Soap molecules have one end that is attracted to water and one end that is attracted to oil and grease. The oily ends surround grease particles while the water-loving ends face outward, so the grease is lifted off and rinsed away in the water.'),
    (['bread', 'rise'], 'Yeast in the dough feeds on sugars and gives off carbon dioxide gas. Kneading builds stretchy gluten, which traps the gas in bubbles, so the dough expands. In the oven the gas expands further and the structure sets.'),
    (['ice', 'float'], 'Ice is less dense than liquid water. When water freezes, its molecules lock into an open crystal pattern that takes up about 9% more space, so ice weighs less than the same volume of water and floats.'),
    (['sky', 'blue'], 'Sunlight contains all colours. As it passes through the air, the tiny gas molecules scatter short wavelengths (blue) much more than long ones (red): this is Rayleigh scattering. The scattered blue light reaches your eyes from every direction, so the sky looks blue.'),
    (['season'], 'Seasons happen because Earth\'s axis is tilted by about 23.5°. As Earth orbits the Sun, first one hemisphere and then the other leans towards the Sun, getting more direct sunlight and longer days (summer), while the other gets slanted light and short days (winter). It is not because of the distance to the Sun.'),
    (['thunder', 'lightning'], 'Lightning and thunder happen at the same moment, but light travels about a million times faster than sound. You see the flash almost instantly while the sound covers roughly 1 km every 3 seconds, so you hear the thunder later. Counting the seconds and dividing by 3 gives the distance in kilometres.'),
    (['leaves|leaf', 'colou?r|red|yellow|orange', 'autumn|fall'], 'Leaves are green because of chlorophyll. In autumn, as days shorten and cool, trees stop making chlorophyll and it breaks down, revealing yellow and orange pigments (carotenoids) that were there all along. Some trees also make red pigments (anthocyanins) from sugars trapped in the leaf.'),
    (['metal', 'cold|colder', 'wood|plastic'], 'Metal conducts heat much better than wood. At the same temperature (below your skin\'s), metal draws heat out of your hand faster, and your skin senses that heat loss as cold.'),
    (['fridge|refrigerator', 'cold|work'], 'A fridge moves heat rather than making cold. A refrigerant evaporates in coils inside the fridge, absorbing heat; a compressor squeezes the vapour, and it releases that heat through coils at the back as it condenses. The cycle repeats, pumping heat out.'),
    (['rust'], 'Rust forms when iron reacts with oxygen and water to make iron oxide. Salt speeds it up. Paint, oil, galvanising (a zinc coating) or stainless steel keep oxygen and water away or resist the reaction.'),
    (['salt', 'ice|icy|road|snow'], 'Salt lowers the temperature at which water freezes. A little liquid water on the ice dissolves the salt, and that salty water stays liquid below 0 °C, so it keeps melting the ice around it, down to about −9 °C for road salt.'),
    (['vaccine|vaccination', 'work'], 'A vaccine shows your immune system a harmless piece or version of a germ. The immune system learns to recognise it and keeps memory cells, so if the real germ arrives later it responds faster and more strongly, usually before you get seriously ill.'),
    (['wind'], 'Wind is air moving from areas of high pressure to areas of low pressure. Those pressure differences come mostly from the Sun heating the ground and air unevenly: warm air rises, leaving lower pressure that surrounding air flows into. Earth\'s rotation bends the flow (the Coriolis effect).'),
    (['star', 'twinkle'], 'Stars twinkle because their light passes through moving layers of air of different temperatures, which bend it slightly in changing directions. Stars are so far away that they are effectively points of light, so this bending makes them flicker; planets look like tiny discs and twinkle less.'),
    (['stomach|tummy', 'rumble|growl'], 'The rumbling is gas and fluid moving through your stomach and intestines as their muscles contract. It is loudest when they\'re nearly empty, because nothing muffles the sound.'),
    (['curl', 'paper|hair', 'wet|water'] , 'Water makes fibres swell. When one side of paper or hair takes up more water than the other, that side expands more and it curls away from the wet side.'),
    (['battery', 'work'], 'A battery has two different materials (electrodes) separated by an electrolyte. A chemical reaction pushes electrons out of one electrode; they can only reach the other through the wire of your circuit, and that flow is the electric current. When the chemicals are used up, the battery is flat.'),
    (['eclipse'], 'A solar eclipse happens when the Moon passes between the Sun and Earth and blocks the Sun. A lunar eclipse happens when Earth passes between the Sun and the Moon, so Earth\'s shadow falls on the Moon, often turning it red.'),
    (['heart', 'beat|pump'], 'The heart is a muscle with four chambers. An electrical signal from its natural pacemaker makes it contract in a set order, squeezing blood out; valves stop the blood from flowing backwards. The right side pumps blood to the lungs, the left side to the rest of the body.'),
    (['photosynthesis|plants? (?:make|get) (?:food|energy)'], 'Plants use the energy of sunlight, captured by green chlorophyll, to turn carbon dioxide from the air and water from the soil into sugar, releasing oxygen as a by-product. The sugar is their food and building material.'),
    (['salt', 'water', 'separate|get'], 'Evaporate the water: boil or leave the salty water in a shallow dish and the salt stays behind as crystals. To keep the water too, distil it: boil it, cool the steam and collect the condensed fresh water.'),
    (['egg', 'float'], 'An older egg floats because air enters through its shell over time, making the air pocket inside bigger, so the egg becomes less dense than water. A fresh egg sinks; an egg that floats is old and best checked before use.'),
    (['wet', 'dark'], 'Wet things look darker because water fills the tiny gaps and roughness at the surface. Less light is scattered straight back to your eyes and more passes into the material and is absorbed, so it looks darker.'),
    (['hot air balloon|hot-air balloon'], 'Heating the air inside the balloon makes it expand, so it becomes less dense than the cooler air outside. The denser outside air pushes the balloon up (buoyancy), just as water pushes up on a floating object.'),
    (['echo'], 'An echo is sound that bounces off a hard surface, like a cliff or wall, and returns to you. You hear it as a separate sound when the surface is far enough away (about 17 m or more) for the reflection to arrive at least a tenth of a second later.'),
    # ---- research methods and computing (2026-11-22, test-informed: added after a hard check missed them)
    (['double.blind'], 'In a double-blind trial neither the participants nor the researchers running it know who is getting the real treatment and who the placebo (or comparison treatment) until the results are in. That stops expectations, on either side, from colouring how people report or how outcomes are judged.'),
    (['single.blind'], 'In a single-blind trial the participants don\'t know whether they are getting the real treatment or a placebo, but the researchers do. It removes the participants\' expectations, though not the researchers\'.'),
    (['placebo', r'what|why|mean|effect'], 'A placebo is a dummy treatment with no active ingredient, such as a sugar pill. People given one often feel better simply because they expect to (the placebo effect), so trials compare a drug against a placebo to see what the drug itself adds.'),
    (['randomi[sz]ed', 'trial|study|control'], 'In a randomised trial a chance process, not the researchers or the patients, decides who gets which treatment. That makes the groups alike on average in everything, including things nobody measured, so a difference in outcomes can be put down to the treatment.'),
    (['hash (?:table|map)|hashmap', r'fast|quick|o\(1\)|constant|look ?up|why|how'], 'A hash table runs the key through a hash function that turns it into a number, and that number points straight at a slot in an array. So instead of searching through the entries, it jumps to the one place the key can be. Two keys can land in the same slot (a collision), but with a good hash and a table that is not too full there are only a few entries to check, so a lookup takes constant time on average.'),
    (['binary search', r'fast|quick|why|how|log'], 'Binary search works on a sorted list: look at the middle item, and because the list is sorted you know which half the target must be in, so you throw the other half away. Halving each time means a million items need only about 20 looks (log2 of the size).'),
    (['cache', r'fast|why|how does|how do'], 'A cache keeps a copy of data that was used recently in a small, fast place (memory instead of disk, or a nearby server instead of a distant one). The next request for the same data is answered from the copy, which is much quicker; the cost is keeping the copies up to date.'),
]


def respond(messages):
    users = [(m.get('content') or '').strip() for m in messages if m.get('role') == 'user']
    if not users:
        return None
    q = users[-1].lower()
    if not re.search(r"\b(?:why|how|what(?:'s| is)? the difference|what does|what do|difference between|compared with|explain|what makes|"
                     r"when (?:do|should) i use|which (?:is right|word|one is correct))\b", q):
        return None
    if len(q) > 300:
        return None
    best = None
    cue = re.search(r"differen|versus|\bvs\b|compared|when (?:do|should) i use|which (?:is|one) (?:is )?(?:right|correct)|"
                    r"\b(\w+'?\w*)['\"]?\s+(?:or|and)\s+['\"]?(\w+'?\w*)['\"]?\s*\?", q)
    for terms, text in ENTRIES:
        if text.startswith('"') and not cue:
            continue                    # a usage note answers only a question about the words themselves
        if all(re.search(r'(?:' + t + r')', q) for t in terms):
            if best is None or len(terms) > len(best[0]):
                best = (terms, text)
    if best is None:
        return None
    return dict(route=ROUTE, response=best[1], sources=[], details='authored explanation (explain_more.py)')
