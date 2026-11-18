"""Everyday science, authored (no model): 'What causes rain?', then 'Why is it sometimes snow instead?'.

Each entry is (question pattern, answer, [(follow-up pattern, answer)]), the shape of chat_core.EXPLAIN, which this extends.
A follow-up names only the new thing ('snow instead', 'and the thunder?'), so a search on its few words drifts to forum
threads about bicycle tyres in snow; the earlier question gives it its subject, and the answer here is the one a person
who knows the subject would give next.
"""

ENTRIES = [
    (r'what (?:causes|makes|creates) (?:the )?rain|why (?:does it|do we get|is there) rain|how (?:does|do) rain (?:form|work|happen)|where does rain come from|\bhow rain forms?\b',
     'Rain starts with water evaporating from seas, lakes, plants and the ground. When moist air rises (over hills, along a weather front, or because the ground '
     'warmed it), it cools, and the water vapour condenses onto tiny specks of dust into cloud droplets. Inside the cloud, droplets bump into each other and '
     'merge, or grow on ice crystals that then melt as they fall, until they are too heavy for the rising air to hold up, and they fall as rain.',
     [(r'\bsnow\b',
       'It depends on the temperature on the way down. High in most clouds it is below freezing, so precipitation often starts as ice crystals that grow into '
       'snowflakes. If the air between the cloud and the ground is above about 0 °C (32 °F) for a long enough stretch, the flakes melt and arrive as rain. If it '
       'stays near or below freezing all the way down, they arrive as snow. That is why snow is most likely in winter, at night, and on high ground, where '
       'the air near the surface is colder. A mix of the two (partly melted flakes) is sleet in British usage.'),
      (r'\bhail\b',
       'Hail comes from tall thunderstorm clouds with strong updraughts. Raindrops are carried up into the freezing part of the cloud, freeze, fall, collect more '
       'water, and get carried up again, adding a layer of ice each time, until the hailstone is too heavy for the updraught and falls. That is why hail '
       'can fall even on a warm summer day.'),
      (r'\bdrizzle\b',
       'Drizzle is rain with very small drops, usually from low, thin clouds where droplets don\'t have room to grow big before they fall.'),
      (r'\bthunder|\blightning\b',
       'Thunderstorms grow from tall clouds with strong rising air. Inside, ice and water particles collide and build up electric charge; lightning is the '
       'giant spark that releases it, and thunder is the sound of the air around the flash heating and expanding almost instantly.'),
      (r'\bmore\b.*\b(?:winter|summer|places?|west|hills?|mountains?|uk|britain|coast)\b|\bso much\b|\bsome places\b',
       'Places get more rain where moist air is forced to rise: on the windward side of hills and mountains, near coasts facing the prevailing wind, and where '
       'weather fronts pass often. Seasons matter too: in many places winter storms bring more rain, while in the tropics a wet season follows the sun.'),
      (r'\bsmell\b',
       'The smell after rain is called petrichor: oils from plants and a chemical made by soil bacteria (geosmin) are released into the air when raindrops hit dry ground.')]),
    (r'what (?:causes|makes) (?:it )?snow|why (?:does it|do we get) snow|how (?:does|do) snow(?:flakes?)? (?:form|happen|work)|how are snowflakes made',
     'Snow forms in clouds that are below freezing. Water vapour freezes straight onto tiny particles as ice crystals, and they grow as more vapour freezes onto '
     'them, branching into snowflakes. If the air all the way to the ground stays at or near freezing, they land as snow; otherwise they melt into rain on the way down.',
     [(r'\btoo cold\b|\bcold(?:er)?\b.*\b(?:no|not|doesn|without)\b|\bdry\b',
       'Very cold air holds very little moisture, so the coldest days are often clear and dry. The heaviest snow tends to fall when it is only just below '
       'freezing, around 0 to -2 °C, when the air still holds plenty of water.'),
      (r'\bsix\b|\bhexagon|\bshape\b|\btwo\b.{0,20}\b(?:same|alike|identical)\b|\bunique\b',
       'Water molecules lock together in a six-sided pattern when they freeze, so snow crystals grow with six arms. Each flake takes its own path through slightly '
       'different temperatures and moisture, which is why no two look exactly alike.'),
      (r'\bwhite\b',
       'Snow is made of clear ice, but the countless crystal faces scatter all colours of light equally in every direction, and all colours together look white.')]),
    (r'what (?:causes|makes) (?:a )?hail|how (?:does|do) hail(?:stones)? form|why does it hail',
     'Hail comes from tall thunderstorm clouds with strong updraughts. Raindrops are carried up into the freezing part of the cloud, freeze, and collect more '
     'layers of ice each time they are carried up again, until they are too heavy and fall.', []),
    (r'what (?:causes|makes) (?:the )?(?:thunder|lightning)|why (?:does|do) (?:we get )?(?:thunder|lightning)|how (?:does|do) (?:thunder|lightning)(?: storms?)? (?:form|work|happen)',
     'Inside a tall storm cloud, ice crystals and small hailstones collide in strong rising and falling air and build up electric charge, usually positive at the '
     'top and negative lower down. When the charge gets big enough, it discharges as lightning, a spark several kilometres long. The lightning heats the air '
     'around it to about 30,000 °C in a split second, and the air expands so fast that it makes the bang we hear as thunder.',
     [(r'\bbefore\b|\bfirst\b|\bafter\b|\bdelay\b',
       'Light travels almost a million times faster than sound, so you see the flash at once while the sound takes about 3 seconds per kilometre (5 seconds per '
       'mile) to reach you. Count the seconds between flash and bang and divide by 3 for kilometres, or by 5 for miles.'),
      (r'\bhow far\b|\bdistance\b|\bclose\b',
       'Count the seconds between the flash and the thunder: divide by 3 for the distance in kilometres, or by 5 for miles. Under about 30 seconds (10 km) you are close enough to be struck, so go indoors.'),
      (r'\bsafe\b|\bcar\b|\boutside\b|\btree\b',
       'Indoors, or in a hard-topped car with the windows shut, is safe. Outside, avoid open ground, hilltops, water and lone trees; don\'t shelter under a tree. '
       'Wait about 30 minutes after the last thunder before going back out.')]),
    (r'what (?:causes|makes) (?:the )?(?:fog|mist)|why (?:is|do we get|does it get) (?:it )?(?:foggy|misty)|how (?:does|do) (?:fog|mist) form',
     'Fog is a cloud at ground level. It forms when air near the ground cools until it can\'t hold all its water vapour, often on clear, still nights or when '
     'moist air moves over cold ground or sea, so the vapour condenses into tiny droplets that hang in the air. Mist is the same thing but thinner.',
     [(r'\bmorning\b|\bclear\b|\bgo away\b|\blift\b',
       'Fog is common on autumn and winter mornings because the ground cools most on long, clear, calm nights. Once the sun warms the ground and the air, the droplets evaporate and the fog lifts.')]),
    (r'what (?:causes|makes) (?:the )?(?:dew|frost)|why (?:is|does) (?:the )?grass wet in the morning|how (?:does|do) (?:dew|frost) form',
     'On clear nights the ground and grass lose heat to the sky and become colder than the air. Water vapour in the air touching them condenses into droplets '
     'of dew; if the surface is below freezing, the vapour freezes straight into ice crystals instead, which is frost.', []),
    (r'why (?:is|does) (?:the )?sky (?:blue|look blue)|what makes (?:the )?sky blue',
     'Sunlight contains all colours. As it passes through the air, the tiny gas molecules scatter short wavelengths (blue) much more than long ones (red), so '
     'blue light is bounced around the whole sky and reaches your eyes from every direction. That scattered light is what you see as a blue sky.',
     [(r'\bsunsets?\b|\bsunrises?\b|\bred\b|\borange\b|\bpink\b|\bevening\b',
       'At sunrise and sunset the light travels through much more air to reach you. Most of the blue is scattered out of the beam along the way, so the light '
       'that gets through is mostly orange and red, and it lights up the clouds in those colours.'),
      (r'\bviolet\b|\bpurple\b',
       'Violet is scattered even more than blue, but sunlight has less violet in it, some is absorbed high up, and our eyes are less sensitive to it, so the mix looks blue.'),
      (r'\bspace\b|\bblack\b|\bnight\b|\bmoon\b',
       'In space there is almost no air to scatter sunlight, so the sky looks black even in daylight. At night, our side of Earth faces away from the Sun, so there is no sunlight in the air to scatter.'),
      (r'\bclouds?\b',
       'Cloud droplets are much bigger than air molecules, so they scatter all colours about equally, and all colours together look white. Thick clouds look grey because less light gets through them.')]),
    (r'why are (?:the )?sunsets? (?:red|orange|pink)|why (?:is|does) the sky (?:turn )?(?:red|orange|pink)',
     'At sunrise and sunset the light travels through much more air to reach you. Most of the blue is scattered out of the beam along the way, so the light '
     'that gets through is mostly orange and red, and it lights up the clouds in those colours.', []),
    (r'what (?:causes|makes) (?:the )?seasons|why (?:do|does) (?:we|earth|the earth) (?:have|get) (?:seasons|summer and winter|winter and summer)|why is (?:it )?(?:colder|warmer|hotter) in (?:winter|summer)|why (?:is )?summer (?:hot|warm)',
     'Seasons happen because Earth\'s axis is tilted by about 23.5°. As Earth orbits the Sun, first one half and then the other leans towards it. The half '
     'leaning towards the Sun gets higher, more direct sunlight and longer days, so it has summer; the half leaning away gets low, weak sunlight and short days, so it has winter.',
     [(r'\bclose(?:r|st)?\b|\bdistance\b|\bnear(?:er)?\b|\bfar(?:ther|ther)?\b',
       'Not the distance: Earth is actually closest to the Sun in early January, in the northern winter. The change in distance is small; the tilt matters far more.'),
      (r'\baustralia\b|\bsouthern\b|\bopposite\b|\bother side\b',
       'Because the tilt makes the two halves take turns: when the northern half leans towards the Sun (June), the southern half leans away, so Australia has winter while Europe has summer.'),
      (r'\bequator\b|\btropic',
       'Near the equator the Sun is high all year and days stay about 12 hours long, so there is little change in temperature; seasons there are wet and dry rather than warm and cold.')]),
    (r'why (?:are|do) (?:the )?clouds (?:white|grey|gray|dark|black)|why (?:are|do) (?:rain )?clouds (?:look )?(?:dark|grey|gray)',
     'Cloud droplets are much bigger than air molecules, so they scatter all colours of sunlight about equally, and all colours together look white. A thick '
     'cloud full of large drops lets little light through from above, so its underside looks grey or dark, which is often a sign it is about to rain.', []),
    (r'why (?:does|do) (?:the )?moon (?:change|chang\w+) (?:its )?shape|what (?:causes|are) (?:the )?(?:moon\'?s? )?phases|phases of the moon',
     'The Moon doesn\'t make light; we see the half lit by the Sun. As the Moon orbits Earth over about 29.5 days, we see different amounts of that lit half: '
     'all of it at full moon, none at new moon, and crescents and half moons in between.',
     [(r'\beclipse\b',
       'An eclipse happens when the Sun, Earth and Moon line up exactly. In a lunar eclipse Earth\'s shadow falls on the full Moon; in a solar eclipse the new '
       'Moon passes in front of the Sun. The Moon\'s orbit is slightly tilted, so they don\'t line up every month.'),
      (r'\bsame side\b|\bone side\b|\bdark side\b|\bfar side\b',
       'The Moon turns once on its axis in exactly the time it takes to orbit Earth, so the same side always faces us. The far side isn\'t dark; it gets sunlight just as often.')]),
    (r'why (?:do|does) (?:the )?leaves (?:change colou?r|turn (?:red|yellow|orange|brown)|fall)|why (?:do|does) (?:the )?trees? (?:lose|drop) (?:their )?leaves',
     'Leaves are green because of chlorophyll, which they use to make food from sunlight. In autumn, as days shorten and cool, trees stop making chlorophyll and '
     'break it down, so the yellow and orange pigments that were there all along show through; some trees also make new red pigments. Then a layer forms at the '
     'base of each leaf stalk, and the leaf drops, which saves the tree water and protects it in winter.', []),
    (r'what (?:causes|makes) (?:an? )?earthquakes?|why (?:do|does) (?:we get |there are )?earthquakes? (?:happen|occur)?|how (?:do|does) earthquakes? happen',
     'Earth\'s outer shell is broken into huge plates that slowly move, a few centimetres a year. Where plates meet, rock gets stuck and strain builds up for years; '
     'when it suddenly slips along a fault, the stored energy is released as shaking waves, which is an earthquake.',
     [(r'\btsunami',
       'When an undersea earthquake lifts or drops the sea floor, it shoves the whole column of water above it. That makes waves that cross oceans at the speed of a '
       'jet and grow tall when they reach shallow water near the coast: a tsunami.'),
      (r'\bpredict|\bwarning\b|\bforecast',
       'Scientists can say which areas are at high risk, but nobody can yet predict the day or hour of an earthquake. Early-warning systems give seconds to a minute of warning once one has started.')]),
    (r'what (?:causes|makes) (?:a )?volcano(?:es)? (?:to )?erupt|why (?:do|does) volcano(?:es)? erupt|how (?:do|does) volcano(?:es)? (?:form|work)',
     'Deep underground, rock melts into magma, mostly where tectonic plates pull apart or one dives under another. Magma is lighter than the rock around it, so it '
     'rises and collects in chambers. Gas dissolved in it builds up pressure, like in a shaken bottle, and when the pressure is too great the magma bursts out as an eruption.', []),
    (r'why (?:does|do) ice float|why (?:does|do) ice cubes float',
     'Ice floats because it is less dense than liquid water. When water freezes, its molecules lock into an open, six-sided pattern that takes up about 9% more '
     'space, so a litre of ice weighs less than a litre of water. That is also why lakes freeze from the top down and fish survive underneath.', []),
    (r'why (?:do|does) (?:we|people|i) sweat|what (?:is|does) sweat(?:ing)? (?:for|do)',
     'Sweating cools you down. Sweat glands put water on your skin, and when it evaporates it takes heat away with it. That is why humid days feel so hot: '
     'the sweat can\'t evaporate as easily.', []),
    (r'why (?:do|does) (?:salt|grit) melt ice|why (?:do they|do people) (?:put|spread) (?:salt|grit) on (?:the )?roads?',
     'Salt lowers the temperature at which water freezes. Dissolved in the thin film of water on ice, it makes salty water that stays liquid below 0 °C, down to '
     'about -9 °C in practice, so the ice melts. Grit adds grip on top.', []),
    (r'why (?:do|does) (?:iron|metal|my bike|my car|things) rust|what (?:causes|makes) rust',
     'Rust forms when iron or steel reacts with oxygen and water: the iron slowly turns into flaky reddish iron oxide. Salt speeds it up, which is why cars rust '
     'faster where roads are salted. Paint, oil or a zinc coating keep air and water off.', []),
    (r'why (?:do|does) bread rise|how (?:does|do) (?:yeast|bread) (?:work|rise)',
     'Yeast is a tiny living fungus. In dough it feeds on sugars and gives off carbon dioxide gas. Kneading builds stretchy gluten that traps the gas in '
     'bubbles, so the dough rises; baking sets the bubbles and the alcohol the yeast makes evaporates.', []),
    (r'why (?:do|does) (?:we|people) (?:catch|get) (?:more )?colds|what causes (?:a |the )?(?:common )?cold\b',
     'Colds are caused by viruses, most often rhinoviruses, that spread through droplets and on hands and surfaces. In winter people spend more time indoors '
     'close together, and dry air may help viruses survive and dry out the nose\'s defences. Being cold itself doesn\'t give you a cold, but washing hands helps a lot.', []),
    (r'why (?:is|does) (?:the )?sun (?:hot|shine|so hot)|how (?:does|do) (?:the )?sun (?:shine|burn|work|make (?:light|heat))',
     'The Sun is a huge ball of hot gas, mostly hydrogen. In its core the pressure and temperature (about 15 million °C) are so high that hydrogen nuclei fuse into '
     'helium, releasing enormous energy. That energy works its way out and leaves the surface as light and heat.', []),
    (r'why (?:do|does) (?:my )?(?:cats?) purr',
     'Cats purr by quickly twitching the muscles of their voice box while breathing in and out. They purr when content, but also when stressed or hurt, so it '
     'seems to be a way of calming themselves and signalling to others, not only happiness.', []),
]
