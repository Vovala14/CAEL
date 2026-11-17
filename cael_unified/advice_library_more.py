"""More everyday topics for advice_library.py (same format: topic words or WordNet classes, aspects, authored replies)."""
from .advice_library import topic

# ------------------------------------------------------------------------------------------------------------ running
topic('running', r'run(?:ning)?|jog(?:ging)?|5k|10k|half[- ]marathon|marathon|parkrun|couch to 5k|c25k', {'running', 'jogging', 'sport'})(
    (r'(?:is (?:that|it|this) )?(?:good|ok|okay|alright|decent|bad|slow) (?:time|for a first|for a beginner)|my time was|minutes? (?:for|is that)|minutes?\W.{0,25}\bis (?:that|it|this) (?:ok|okay|good|alright|decent|bad|slow)',
     "For a first one, that's a perfectly respectable time: anything that gets you round is a good start, and most new runners finish a first 5k "
     "somewhere between 30 and 40 minutes. Your next few runs will very likely be faster as your body adapts. Treat this one as the baseline to beat."),
    (r'how often|how many (?:times|days)|rest days?',
     "Three runs a week with a rest day in between is the classic beginner plan; the body adapts on the rest days. Keep most runs easy (you should be "
     "able to talk), and add no more than about 10% to your weekly distance at a time."),
    (r'shin|knee|ankle|hurt|pain|sore|ache',
     "Aches when starting out are common, often from doing too much too soon or worn-out shoes. Ease off for a few days, then build up more gently; "
     "try a run-walk mix and softer surfaces. Get properly fitted running shoes if yours are old or not for running. Sharp pain, swelling or pain "
     "that stays when you rest should be seen by a doctor or physio."),
    (r'breath|out of breath|stitch',
     "Slow down: being out of breath usually means going too fast for now. Run at a pace where you could still speak in short sentences, and use "
     "run-walk intervals. For a stitch, slow to a walk, breathe out fully and press gently on the spot; avoid big meals in the two hours before."),
    (r'(?:what )?shoes?|trainers|what (?:do|should) i (?:need|buy|wear)',
     "The one thing worth spending on is a pair of proper running shoes that fit well; a running shop can watch you run and suggest a few. "
     "Otherwise, comfortable breathable clothes and a good sports bra if you need one are all you need to start."),
)

# ------------------------------------------------------------------------------------------------------------ gym and strength
topic('gym', r'gym|weights?|lifting|strength training|workout|push-?ups|squats|muscle', {'exercise'})(
    (r'beginner|start|first time|routine|plan|how (?:should|do) i (?:start|begin)|nervous|intimidat',
     "A simple start: two or three full-body sessions a week, with a rest day between. Pick five or six basic moves (squat or leg press, a push such "
     "as press-ups or chest press, a pull such as rows, a hinge such as hip thrusts or deadlifts with light weight, and a plank), and do 2 to 3 sets "
     "of 8 to 12 reps with a weight that feels hard by the last few. Add weight slowly once it gets easy. Most gyms will show you the machines if you "
     "ask, and quiet times (mid-morning, early afternoon) make the first visits easier."),
    (r'sore|ache|stiff|doms',
     "Muscle soreness a day or two after a workout is normal, especially at the start; it fades as you get used to it. Gentle movement, a walk, and "
     "sleep help. Sharp pain or pain in a joint during an exercise is different: stop that exercise and get it checked if it persists."),
    (r'how often|how many (?:times|days)',
     "Two or three times a week is plenty to make good progress as a beginner, with at least a day between sessions for the same muscles. "
     "Consistency over months matters far more than the number of sessions in any one week."),
)

# ------------------------------------------------------------------------------------------------------------ camping and hiking
topic('camping', r'camp(?:ing|site|er|fire)?|tent|hik(?:e|ing)|trek(?:king)?|walking holiday|ramble|trail', {'camping', 'hike'})(
    (r'meals?|cook|food|eat|camp stove|stove',
     "Easy camp-stove meals that need one pan:\n\n- Pasta with a jar of sauce or pesto, and some cheese.\n- Instant noodles with an egg and frozen veg.\n"
     "- Couscous (just add boiling water) with tinned chickpeas and spices.\n- Sausages or veggie sausages with bread rolls.\n- Porridge or eggs and "
     "beans for breakfast.\n\nPrep and chop at home, and bring a lighter, a sharp knife, a pan with a lid and a washing-up bowl."),
    (r'cold|warm enough|temperature|night',
     "Nights in a tent are usually colder than the daytime suggests. Sleep on an insulating mat (the ground takes more heat than the air), use "
     "sleeping bags rated for a few degrees below the forecast low, wear a hat and dry socks to bed, and have a warm drink before sleeping."),
    (r'blister|boots|shoes|feet',
     "Wear boots or shoes you've already broken in, with proper hiking socks (not cotton). At the first sign of a hot spot, stop and cover it with "
     "a blister plaster or tape; it's much easier to prevent a blister than treat one."),
    (r'beginner|first (?:hike|time)|how long|how far|start',
     "Start with a well-marked route of 5 to 10 km with little climbing, check the weather and daylight hours, and tell someone where you're going. "
     "Bring water, snacks, a waterproof, a warm layer, a charged phone and a map. A common rule of thumb is about 4 to 5 km an hour on the flat, "
     "plus an hour for every 600 m of climbing."),
)

# ------------------------------------------------------------------------------------------------------------ driving
topic('driving', r'driv(?:e|ing)|driving (?:test|lessons?|instructor)|learner driver|parallel park', {'driving'})(
    (r'test|nervous|exam|failed|pass',
     "Lots of people need more than one attempt. Ask your instructor which faults came up and practise those specifically; do a mock test on the "
     "real routes; book the test when you're consistently driving without prompting, not before. On the day, a lesson just beforehand helps you "
     "warm up, and if you make a mistake, keep going: one error doesn't always fail you."),
    (r'how many lessons|how long (?:does it|will it) take',
     "It varies a lot, but many learners need somewhere around 40 to 50 hours with an instructor, plus extra practice with family or friends if "
     "possible. Frequent lessons (two a week) usually get there faster than occasional ones."),
    (r'parallel park|parking|reverse',
     "For parallel parking: pull up alongside the car in front, about a door's width away; reverse slowly until your rear wheel lines up with their "
     "back bumper, turn full lock towards the kerb until you're at about 45 degrees, straighten, then full lock away as your front clears their car. "
     "Practise slowly in a quiet street with cones or bins."),
)

# ------------------------------------------------------------------------------------------------------------ gardening outdoors
topic('veg_garden', r'tomato(?:es)?|vegetables?|veg patch|allotment|garden|seeds?|seedlings?|lettuce|courgettes?|zucchini|potatoes|strawberr(?:y|ies)|herbs?|basil|mint',
      {'vegetable', 'herb'})(
    (r'when (?:should|do|can) i (?:plant|sow)|best time to (?:plant|sow)',
     "Most summer vegetables (tomatoes, courgettes, beans) go outside after the last frost, which is around mid to late spring in many places; sow "
     "them indoors 6 to 8 weeks before that. Hardy crops (peas, lettuce, spinach, potatoes) can go in earlier, from early spring. Your local "
     "last-frost date is the key thing to look up."),
    (r'how (?:often|much) (?:should|do) i water|watering',
     "Water deeply a couple of times a week rather than a little every day, so roots grow down; in hot spells, pots and tomatoes may need water "
     "daily. Water the soil, not the leaves, ideally in the morning or evening, and check by pushing a finger into the soil."),
    (r'yellow|brown|leaves|dying|wilting|pests?|slugs?|aphids',
     "The usual causes are watering (too much or too little), not enough feeding once fruit starts, or pests. Feed tomatoes weekly with a tomato "
     "feed once flowers appear, water regularly, and check under the leaves for aphids; slugs are best handled with beer traps, barriers or picking "
     "them off in the evening."),
    (r'balcony|small space|pots?|containers?|beginner|easy',
     "Easy things for pots: herbs (basil, mint in its own pot, parsley, chives), salad leaves and radishes, which grow fast, cherry tomatoes in a sunny "
     "spot, and strawberries. Use pots with drainage holes and good compost, and give them as much sun as you can; most need at least six hours."),
)

# ------------------------------------------------------------------------------------------------------------ cleaning and laundry
topic('cleaning', r'clean(?:ing)?|mould|mold|limescale|oven|grease|stain|laundry|washing|shrunk|whites|carpet|bathroom|kitchen|declutter(?:ing)?|tidy',
      {'cleaning'})(
    (r'mould|mold|black (?:spots|stuff)|damp|condensation',
     "For small patches of mould on bathroom sealant or walls: wipe with a mould remover or a diluted bleach solution (with the window open and "
     "gloves on), then dry the area. Stopping it coming back is about moisture: open a window or run the fan during and after showers, wipe "
     "condensation off windows in the morning, and keep furniture a little away from cold outside walls."),
    (r'limescale|kettle|tap|shower ?head',
     "White vinegar or citric acid dissolves limescale: soak shower heads or tap ends in it for an hour (a bag held on with an elastic band works), or "
     "half-fill a kettle with water and vinegar, boil, leave for an hour and rinse well."),
    (r'oven',
     "Mix bicarbonate of soda with a little water into a paste, spread it over the inside of the cold oven (avoiding the heating elements), leave "
     "overnight, then wipe off with a damp cloth and spray a little vinegar on any residue. Soak the racks in hot soapy water."),
    (r'shr[ua]nk|shrink',
     "To rescue a shrunk wool jumper: soak it for 30 minutes in lukewarm water with a good squirt of hair conditioner, gently stretch it back into "
     "shape, roll it in a towel to remove water, and dry it flat, stretching it now and then. It won't always come back fully."),
    (r'declutter|tidy|organi[sz]e|too much stuff',
     "Start small so it doesn't stall: one drawer or shelf at a time, 15 minutes a day. Keep three piles (keep, give away or sell, bin), and for each "
     "item ask whether you've used it in the past year. Get the give-away bags out of the house the same day."),
    (r'cleaning routine|keep (?:the|my) (?:house|flat|home) (?:clean|tidy)|how often (?:should|do) i clean (?:the|my) (?:house|flat|home|bathroom|kitchen)',
     "A simple routine: ten minutes of tidying each evening, the kitchen wiped after cooking, and one bigger job a day (bathroom one day, hoovering "
     "another, bedding at the weekend). Little and often stops it building into a big weekend clean."),
)

# ------------------------------------------------------------------------------------------------------------ cars
topic('car', r'car|tyres?|tires?|engine|warning light|dashboard|mot|battery (?:is )?flat|flat battery|oil|brakes?|petrol|diesel', {'car'})(
    (r'warning light|dashboard|light (?:came|is) on|engine light',
     "It depends on the colour: red lights (brakes, oil pressure, engine temperature, battery) mean stop safely as soon as you can and check before "
     "driving on; amber or orange lights (engine management, tyre pressure) mean get it checked soon. The car's handbook shows what each symbol "
     "means. If the engine light flashes or the car runs roughly, stop and call for help."),
    (r'flat battery|won\'?t start|battery',
     "If the engine clicks or won't turn over, the battery is probably flat. You can jump-start it from another car with jump leads (red to the "
     "positive terminals, black from the good car's negative to bare metal on yours), or call a breakdown service. A battery that keeps going flat, "
     "especially if it's over four or five years old, usually needs replacing."),
    (r'tyre|tire|pressure|puncture',
     "Check tyre pressures about once a month when the tyres are cold, using the figures in the handbook or on a sticker inside the driver's door. "
     "Check the tread too: the legal minimum in many countries is about 1.6 mm, but grip drops well before that, especially in the wet."),
)

# ------------------------------------------------------------------------------------------------------------ work life
topic('work', r'new job|first day|first week|manager|boss|colleagues?|coworkers?|work(?:ing)? from home|wfh|remote work|office|salary|raise|pay rise|resign|quit my job|career',
      {'work'})(
    (r'first day|first week|new job|start(?:ing)? (?:a |my )?new',
     "A few things that help in a new job: get there a bit early, write down names and how things work (no one expects you to remember everything), "
     "ask questions freely in the first weeks, and set up a short chat with your manager about what good looks like after the first month or three. "
     "Say yes to lunches and coffees: relationships are most of the first month."),
    (r'work(?:ing)? from home|wfh|remote|focus|distract',
     "Working from home goes better with a fixed start and finish time, a separate spot you only use for work, and getting dressed and out for a short "
     "walk first thing. Batch notifications, work in focused blocks (say 50 minutes on, 10 off), and keep a proper lunch break away from the screen."),
    (r'raise|pay rise|salary|ask for more money|negotiat',
     "Pick a good moment (a review, or after a clear success), and prepare: what you've delivered, any new responsibilities, and what the role pays "
     "elsewhere. Ask for a specific figure, explain why briefly, and then stop talking and listen. If the answer is not now, ask what you'd need to "
     "show and agree a date to revisit it."),
    (r'quit|resign|leave (?:my|the) job|hand in (?:my )?notice',
     "Before resigning, it usually helps to have the next thing lined up, or savings for a few months. Tell your manager in person first, then put "
     "it in writing with your last day based on your notice period. Keep it short and positive; you may want a reference later."),
)

# ------------------------------------------------------------------------------------------------------------ children
topic('kids', r'toddler|baby|babies|newborn|my (?:son|daughter|kids?|children)|bedtime|picky eater|fussy eater|tantrums?|screen time|teenager',
      {'child', 'baby', 'toddler'})(
    (r'won\'?t sleep|bedtime|sleep(?:ing)?|wakes? up|night',
     "A calm, predictable routine helps most children sleep: the same steps in the same order each night (bath, pyjamas, teeth, story, lights out), "
     "a consistent bedtime, a dark and cool room, and no screens in the hour before. If they get up, return them to bed calmly and with as little "
     "chat as possible. It often takes a week or two of consistency to see a change."),
    (r'won\'?t eat|picky|fussy|vegetables|eating',
     "Picky eating is very common and usually passes. Keep offering small amounts of new foods alongside ones they like, without pressure or bribes; "
     "it can take 10 to 15 tries before a child accepts a food. Eat together, let them help prepare food, and keep snacks and drinks away from the hour "
     "before meals."),
    (r'tantrums?|meltdowns?|screams?|hitting',
     "Stay calm and keep them safe; during a tantrum, talking or reasoning rarely helps. Name the feeling afterwards ('you were really cross that "
     "we had to leave'), keep the limits the same, and notice and praise calm behaviour. Tiredness and hunger make tantrums far more likely, so "
     "routines and snacks help."),
    (r'screen time|phone|tablet|ipad|gaming',
     "Agree simple rules together and keep them consistent: screens off at meals and an hour before bed, devices charging outside the bedroom, and a "
     "rough daily limit. Swapping screen time for something they enjoy (outdoors, friends, a hobby) works better than just taking it away."),
)

# ------------------------------------------------------------------------------------------------------------ events and gifts
topic('events', r'party|parties|birthday|wedding|speech|toast|best man|maid of honou?r|gift|present|anniversary|dinner party|hosting', {'party', 'gift'})(
    (r'gift|present|what (?:should|could|can) i (?:get|buy)',
     "A few ways to find a good gift: think about something they've mentioned wanting, an upgrade to something they use every day, or an experience "
     "to share (a meal, a class, tickets). A small thoughtful thing with a handwritten note often lands better than something expensive and generic."),
    (r'(?:wedding|best man|maid of honou?r)\b.*\b(?:speech|toast)|(?:speech|toast)\b.*\bwedding|best man|maid of honou?r',
     "A good wedding speech is short (three to five minutes) and warm: thank the hosts, tell one or two stories that show who the person is (kind, "
     "not embarrassing), say something genuine about the couple together, and finish with a toast. Write it out, practise it aloud a few times, "
     "and keep the jokes gentle; avoid ex-partners and in-jokes that only a few people get."),
    (r'speech|toast|say a few words|a few words',
     "Keep it short (two to four minutes) and personal: open with who you are and why you're glad to be there, tell one or two warm stories "
     "that show what the person is like, say something specific about what they've meant to the people in the room, and end by raising a glass "
     "to them. Write it out, practise it aloud a few times, and keep any jokes kind."),
    (r'surprise|keep it (?:a )?secret|without (?:him|her|them) knowing|find out',
     "To keep a surprise party secret: tell guests in writing that it's a surprise and keep the group chat away from the person, give them a "
     "believable cover plan for the day (a quiet dinner, a family visit), get one trusted person to bring them at the right time, and have "
     "everyone arrive at least half an hour earlier. Keep decorations and food somewhere they won't look."),
    (r'where (?:should|do) i start|planning|plan (?:it|a|the)|organi[sz]e',
     "A simple order for planning a party:\n\n1. **Date, size and budget** first; everything else follows from those.\n2. **Venue**: home, a "
     "restaurant's private room, a pub function room or a community hall; book early.\n3. **Guest list and invitations**, about four to six weeks "
     "ahead.\n4. **Food and drink**: caterer, buffet, or a few dishes plus help from family.\n5. **The personal touches**: a speech, photos, a "
     "card or book with messages from everyone.\n\nMake a short checklist with who is doing what, and share it with one or two helpers."),
    (r'host|dinner party|how much food',
     "Keep it simple: one main dish you've made before, things you can prepare ahead, and let guests bring drinks or dessert. Ask about dietary "
     "needs when you invite people. Plan the timings backwards from when you want to eat, and have nibbles ready for when people arrive."),
)

# ------------------------------------------------------------------------------------------------------------ social life
topic('social', r'make (?:new )?friends|new city|new town|moved here|lonely|first date|dating|date (?:ideas|night)|nervous about (?:the )?date',
      {'friend'})(
    (r'make (?:new )?friends|meet (?:new )?people|new city|new town|moved here|lonely',
     "Meeting people as an adult mostly comes from seeing the same faces regularly. Pick one or two things that meet weekly (a class, a running or "
     "walking club, a choir, volunteering, a sports team, a board-game night) and keep going; friendships grow after a few weeks of small chats. "
     "Say yes to invitations, and suggest a coffee to someone you get on with: most people are glad to be asked."),
    (r'first date|date ideas|what should we do|nervous',
     "Keep a first date short, public and easy to talk through: coffee, a walk, a casual drink or something with a bit to look at like a market or a "
     "gallery. Ask open questions and listen properly; nerves are normal and usually shared. If it goes well, you can always suggest extending it."),
)

# ------------------------------------------------------------------------------------------------------------ small pets
topic('small_pets', r'rabbits?|bunn(?:y|ies)|hamsters?|guinea pigs?|fish ?tank|aquarium|goldfish|budgies?|parrots?|tortoise', {'rabbit', 'fish', 'bird'})(
    (r'feed|food|eat',
     "Rabbits and guinea pigs should eat mostly hay (unlimited, it should be about 80% of their diet), plus a handful of fresh greens and a small "
     "portion of pellets; guinea pigs also need vitamin C from fresh veg. Hamsters eat a hamster mix with small amounts of fresh veg. Fish need only "
     "what they finish in a couple of minutes, once or twice a day."),
    (r'clean|tank|water|cage|hutch',
     "Spot-clean cages and hutches daily and do a full clean weekly. For a fish tank, change about 10 to 20% of the water every week with "
     "dechlorinated water at the same temperature, and never clean the filter under tap water (rinse it in old tank water)."),
)

# ------------------------------------------------------------------------------------------------------------ cooking extras
topic('cooking', r'cook(?:ing)?|recipe|dinner|meal prep|batch cook|rice|pasta|chicken|steak|eggs?|vegetarian|vegan|curry|soup|oven|pan', {'dish', 'food'})(
    (r'quick|easy|simple|beginner|tonight|weeknight|ideas',
     "Some quick, forgiving dinners: a vegetable stir-fry with rice or noodles; pasta with garlic, olive oil and greens; an omelette or frittata; a "
     "tray bake (chopped vegetables and chicken or chickpeas, olive oil and seasoning, about 35 to 40 minutes at 200 °C); or a soup from an onion, a "
     "stock cube and leftover vegetables."),
    (r'meal prep|batch|for the week|lunches',
     "Pick two or three things that keep well (chilli, curry, pasta bake, soup, roasted vegetables with grains), cook them on one day, and portion "
     "them into containers. Most keep three to four days in the fridge; freeze the rest. Keep some sauces or toppings separate so the week doesn't "
     "get boring."),
    (r'cooked|safe|done|how (?:do|can) i (?:tell|know)',
     "Chicken and other poultry must be cooked through: the juices should run clear and there should be no pink, and a thermometer in the thickest "
     "part should read at least 74 °C (165 °F). Mince and sausages also need cooking right through; whole cuts of beef or lamb can be served pink."),
)

# ------------------------------------------------------------------------------------------------------------ home DIY
topic('diy', r'paint(?:ing)? (?:a |the |my )?(?:room|wall|walls|bedroom|ceiling|door|fence)|repaint|wallpaper|shelf|shelves|drill|leaking tap|dripping tap|blocked (?:sink|drain)|squeaky door',
      {'diy'})(
    (r'how (?:do|should) i paint|tips|first time|how many coats|prep',
     "Preparation makes the finish: fill holes and sand, wipe the walls down, and tape edges with masking tape. Cut in around the edges with a brush "
     "first, then roll the main areas in overlapping 'W' shapes. Two thin coats are better than one thick one; let the first dry fully (usually 2 to "
     "4 hours) before the second, and remove the tape while the last coat is slightly wet."),
    (r'blocked|drain|sink|plughole',
     "Try boiling water first (not for plastic pipes that are very old), then a plunger with the overflow covered. Baking soda followed by vinegar, "
     "left for half an hour and flushed with hot water, can shift soap and grease. If it's hair, a cheap plastic drain snake works well. Avoid "
     "mixing chemical drain cleaners."),
    (r'drip|leak',
     "A dripping tap is usually a worn washer or cartridge. Turn off the water to that tap (the valve under the sink, or the main stopcock), open the "
     "tap to drain it, take off the handle and head, and replace the washer or cartridge with the same type. If you rent, it's the landlord's job: "
     "report it in writing."),
)

# ------------------------------------------------------------------------------------------------------------ mind and wellbeing
topic('wellbeing', r'meditat(?:e|ion)|mindful(?:ness)?|journal(?:ing)?|burn(?:ed|t)? ?out|overwhelmed|stress(?:ed)?|anxious|anxiety|calm down|relax',
      {'stress'})(
    (r'meditat|mindful|how (?:do|should) i start|beginner',
     "Start with five minutes a day: sit comfortably, set a timer, and pay attention to your breathing. When your mind wanders (it will, constantly), "
     "notice it without judging and bring it back; that bringing back is the exercise. A free guided app or recording helps at first. Same time each "
     "day, such as after brushing your teeth, makes it a habit."),
    (r'burn|overwhelmed|too much|stressed|can\'?t cope',
     "When it all feels like too much, it helps to make it smaller: write down everything on your mind, pick the one thing that matters most today, "
     "and let some of the rest wait. Protect sleep, take short breaks outside, and talk to someone you trust. If it's been going on for weeks or "
     "affecting sleep, eating or work, a doctor or counsellor can help, and it's worth telling your manager if work is the cause."),
)

# ------------------------------------------------------------------------------------------------------------ reading and habits
topic('habits', r'read more|reading habit|habit|routine|wake up earlier|morning routine|procrastinat|motivation|screen time|phone less', {'habit'})(
    (r'read more|reading',
     "Make it easy and small: keep a book where you'd otherwise pick up your phone (bed, bag, sofa), read ten pages a day, and choose books you "
     "actually enjoy rather than ones you think you should. Audiobooks count too. If a book isn't working after 50 pages, it's fine to stop."),
    (r'wake up earlier|morning|get up',
     "Move your wake-up time earlier by 15 minutes every few days rather than all at once, and move bedtime with it. Put the alarm across the room, "
     "open the curtains or get daylight straight away, and have something you look forward to in the first half hour."),
    (r'phone less|screen time|doomscroll|social media',
     "Make the phone a little harder to reach for: turn off non-essential notifications, move social apps off the home screen, set app time limits, "
     "and keep the phone out of the bedroom overnight. Replace the habit rather than just removing it: a book, a short walk, or a call to a friend."),
)
