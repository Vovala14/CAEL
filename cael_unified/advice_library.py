"""Everyday advice by topic and aspect: the knowledge an ordinary helpful person has, written down once.

Round 8 and 9 showed where CAEL loses to small language models: "How often should I water it?" about a monstera,
"How much exercise does a greyhound need?", "What's the simplest loaf to start with?", "What do I need to buy before
I start cycling to work?". A single stored forum answer rarely fits; an authored answer per topic and aspect does,
and one entry covers many specific things because the subject is generalised first (WordNet: monstera -> vine ->
plant; greyhound -> hound -> dog; ukulele -> guitar-family).

Each topic has words or classes that place a conversation in it, and aspects: a pattern over the question and a
reply written for that aspect. {thing} is filled with what the user called it ("your monstera", "Biscuit"). Replies
are general and cautious, give rules of thumb with their usual range, and say what would change the advice. Health
and safety topics point to a professional for anything persistent. Authored text and patterns; no model.
"""
import re

from . import open_chat as oc


COOKING = re.compile(r"(?i)\b(?:roast\w*|crisp\w*|soggy|cook\w*|bak(?:e|ed|ing)|fr(?:y|ied|ying)|boil\w*|oven|recipe|tray|pan|taste\w*|mash\w*)\b")
GARDEN = {'veg_garden', 'houseplant', 'compost', 'plants_away'}


class Topic:
    def __init__(self, key, words, classes=(), thing=None, aspects=()):
        self.key = key
        self.words = re.compile(r'(?i)\b(?:' + words + r')\b')
        self.classes = set(classes)
        self.thing = thing
        # whole words only: "train" must not match the rain aspect, "routine" must not match inside other words
        # a word may take an ending ("droop" -> "drooping") but not become another word ("pot" -> "potatoes")
        self.aspects = [(re.compile(r'(?i)\b(?:' + p + r')(?=(?:s|es|ed|d|ing|er|ers|y|ly|ies)?(?![a-z]))'), t) for p, t in aspects]


T = []


def topic(key, words, classes=(), thing=None):
    def add(*aspects):
        T.append(Topic(key, words, classes, thing, aspects))
    return add


# ------------------------------------------------------------------------------------------------------------ plants
topic('houseplant', r'houseplants?|house plants?|plants?|monsteras?|ferns?|cact(?:us|i)|succulents?|orchids?|pothos|peace lil(?:y|ies)|spider plants?|'
      r'snake plants?|rubber plants?|fiddle leaf figs?|figs?|aloe|bonsai|ivy|calathea|philodendrons?|yucca|dracaena|palm',
      {'plant', 'houseplant', 'vine', 'flower', 'succulent', 'shrub', 'herb'}, thing='your {n}')(
    (r'how (?:often|much|regularly).*\bwater|\bwater(?:ing)?\b.*how (?:often|much)|over-?water|under-?water|when (?:should|do) i water',
     "Water {thing} when the top few centimetres of soil are dry, not on a fixed schedule. For most houseplants that works out at about once a week in "
     "spring and summer and every two to three weeks in winter, when growth slows.\n\n- Push a finger into the soil: dry at the second knuckle means water.\n"
     "- Water thoroughly until it runs out of the drainage holes, then empty the saucer so the roots don't sit in water.\n"
     "- A pot with no drainage hole is the most common reason plants get overwatered.\n- Succulents and cacti need much less; ferns and calatheas like the soil kept slightly moist."),
    (r'yellow|turning brown|brown (?:tips|edges|spots)|leaves (?:are )?(?:dying|droop|wilt|curl)|droop|wilt|what am i doing wrong|dying',
     "Yellowing leaves usually come down to water, and most often too much of it:\n\n"
     "- **Overwatering** (most common): soil that stays wet, lower leaves going yellow and soft. Let the top few centimetres dry out before watering, "
     "and check the pot drains.\n- **Underwatering**: leaves yellow and crisp, soil pulling away from the pot. Water thoroughly, then more regularly.\n"
     "- **Light**: too little light gives pale, yellowing leaves and leggy growth; harsh direct sun can scorch.\n"
     "- **Natural ageing**: one or two old leaves at the bottom yellowing now and then is normal.\n\n"
     "Change one thing at a time and give it a couple of weeks; new leaves will show whether it's working."),
    (r'sun(?:light)?|light|window|dark|shade|where (?:should|do) i (?:put|keep|place)',
     "Most houseplants, {thing} included, do best in bright, indirect light: near a window but out of strong midday sun, which can scorch the leaves. "
     "A few signs help: pale leaves and long gaps between them mean too little light; bleached or brown patches mean too much direct sun. "
     "Cacti and succulents are the exception and like as much sun as you can give them."),
    (r'repot|bigger pot|new pot|pot size|transplant',
     "Repot when the roots have filled the pot: roots circling the bottom or coming out of the drainage holes, or water running straight through. "
     "Spring is the best time, as the plant is starting to grow. Go up only one pot size (a few centimetres wider), use fresh potting mix, and water well "
     "afterwards. If it was only just bought and looks healthy, it's usually best to leave it for a few weeks to settle first."),
    (r'feed|fertili[sz]|plant food|nutrients',
     "Feed {thing} during the growing season (spring and summer) with a general houseplant fertiliser, about once a month, at the strength on the label "
     "or a little weaker. Don't feed in winter or right after repotting, and never feed a dry plant: water first."),
    (r'holiday|away for|going away|on vacation',
     "For a week or two away: water thoroughly the day before you go and move the plant out of direct sun. For longer, stand pots on a tray of wet "
     "pebbles, use a self-watering spike, or ask someone to water once a week."),
    (r'bugs?|pests?|flies|gnats|mites|aphids|white (?:spots|stuff)|sticky',
     "Small flies around the soil are usually fungus gnats, a sign the compost stays too wet: let it dry out more between waterings. For aphids, mites or "
     "mealybugs, wipe the leaves with soapy water, isolate the plant from others, and repeat every few days until they're gone."),
)

# ------------------------------------------------------------------------------------------------------------ dogs
topic('dog', r'dogs?|pupp(?:y|ies)|greyhounds?|labradors?|spaniels?|terriers?|collies?|retrievers?|poodles?|beagles?|whippets?|lurchers?|huskies|husky|'
      r'pugs?|dachshunds?|rescue dog', {'dog', 'puppy', 'hound'}, thing='{n}')(
    (r'how much (?:exercise|walk)|how (?:long|far|often) (?:should|do) (?:i|we) walk|exercise|walks? (?:a|per|each) day|enough exercise',
     "It depends on the breed and age. As a rough guide:\n\n- Most adult dogs: 30 minutes to 2 hours of activity a day, split into two or three walks.\n"
     "- Greyhounds and other sighthounds are sprinters, not marathon runners: two 20 to 30 minute walks a day plus a safe off-lead run now and then "
     "is usually plenty, and they happily sleep much of the rest.\n- Working breeds (collies, spaniels, huskies) need more, with play and training.\n"
     "- Puppies: short sessions, roughly five minutes per month of age, twice a day.\n\n"
     "A tired, settled dog at home is the sign it's enough; restlessness or chewing often means it isn't."),
    (r'sleeps? (?:a lot|so much|all day|\d+ hours)|how much (?:do|should) .* sleep|sleeping (?:a lot|too much)',
     "Lots of sleep is normal for dogs: adults typically sleep 12 to 14 hours a day, and greyhounds, older dogs and puppies often 16 to 18 or more. "
     "What matters is change: if {thing} suddenly sleeps much more than usual, or seems weak, off food or in pain, see a vet."),
    (r'treats?|reward',
     "The best training treats are small, soft and smelly, so they're eaten in a second: pea-sized pieces of cooked chicken, cheese, hot dog or "
     "commercial soft training treats. Keep the high-value ones for hard things like recall, and count them in the day's food so {thing} doesn't put "
     "on weight."),
    (r'how (?:much|often) (?:should|do) i feed|how much food|feeding|portion',
     "Most adult dogs do well on two meals a day; puppies need three or four. Start with the amount on the food packet for {thing}'s weight, then "
     "adjust: you should be able to feel the ribs easily but not see them. Treats count towards the total."),
    (r'pull(?:s|ing)? on the (?:lead|leash)|lead|leash',
     "For pulling on the lead: stop the moment the lead goes tight and only move on when it slackens; reward {thing} for walking beside you, with "
     "treats at your leg. A harness that clips at the chest helps. Short, frequent practice beats long frustrating walks."),
    (r'bark',
     "Work out what the barking is about first: boredom, alarm at noises, or being left alone. More exercise and something to chew help boredom; "
     "for alarm barking, calmly reward quiet rather than shouting (which sounds like joining in). Barking only when alone points to separation "
     "anxiety, which needs very gradual practice at short absences."),
    (r'alone|left on (?:his|her|their) own|separation|while i(?:\'m| am) at work',
     "Build up time alone gradually: start with a few minutes, come back before {thing} gets upset, and lengthen slowly. A walk beforehand, a "
     "long-lasting chew or stuffed toy, and a calm exit and return all help. Most adult dogs shouldn't be left more than about four hours at a "
     "stretch without a break."),
    (r'settle|new home|just adopted|first (?:few )?(?:days|weeks|night)|rescue',
     "Give {thing} time: a rescue dog often takes three days to decompress, three weeks to learn the routine and three months to feel at home. "
     "Keep things quiet and predictable at first, give a safe den-like spot, keep walks short and familiar, and let them come to you rather than "
     "fussing them. Training can wait until they've settled."),
    (r'toilet|house ?train|potty|pee|wee|accidents?',
     "Take {thing} out first thing in the morning, after meals, after naps and play, and last thing at night; praise and reward the moment they go "
     "outside. Clean accidents with an enzyme cleaner so the smell doesn't draw them back, and never punish after the event."),
    (r'chew',
     "Chewing is normal, especially in puppies and bored dogs. Give plenty of safe chews and rotate them, tidy away shoes and cables, and swap the "
     "wrong item for a right one when you catch it. More exercise and things to sniff and solve usually cut chewing down a lot."),
)

# ------------------------------------------------------------------------------------------------------------ cats
topic('cat', r'cats?|kittens?|kitty|tabby', {'cat', 'kitten'}, thing='{n}')(
    (r'how (?:often|much) (?:should|do) i feed|feeding|how much food|portion',
     "Kittens need several small meals a day: about four at 8 to 12 weeks, three until about six months, then two meals a day as adults. Use a "
     "kitten food until about a year old, follow the packet amount for {thing}'s weight and age, and keep fresh water out at all times. Wet food "
     "for some meals helps them drink enough."),
    (r'hid(?:e|es|ing)|under the bed|scared|shy',
     "Hiding is normal for a new cat or kitten: it's how they feel safe. Give {thing} a quiet room with food, water, litter and a box or bed to "
     "hide in, sit nearby without forcing contact, and let them come out on their own. Most cats are exploring within days to a couple of weeks. "
     "Hiding together with not eating, not using the litter tray or seeming unwell is a reason to see a vet."),
    (r'litter|toilet|pee|wee|poo',
     "One litter tray per cat plus one extra, in quiet spots away from food. Scoop daily, use unscented litter, and keep the tray clean: cats "
     "often avoid a dirty tray. Going outside the tray after it used to be fine can mean a health problem such as a urinary infection, so see a vet."),
    (r'scratch',
     "Give {thing} a tall, sturdy scratching post next to the spot they're scratching, rub it with catnip, and reward them for using it. Cover the "
     "sofa corner with a throw or double-sided tape for a few weeks so the post is the better option."),
    (r'play|bored|toys?|energy',
     "Two or three short play sessions a day with a wand toy, ending with a 'catch' and a little food, use up energy well, especially in the "
     "evening. Rotate toys so they stay new, and add a window perch or cardboard boxes for interest."),
    (r'outside|outdoors|go out|indoor',
     "Keep a new cat indoors for at least two to three weeks so they learn the house is home, and make sure they're neutered, vaccinated and "
     "microchipped first. Start outside time before a meal, so they come back when called for food."),
)

# ------------------------------------------------------------------------------------------------------------ moving house
topic('moving', r'mov(?:e|ing) (?:house|home|flat|out|in|to (?:a|the|our|my) (?:new )?(?:flat|house|place|apartment|home))|moving|removals?|'
      r'removal (?:firm|company|van)|movers|new (?:flat|house|place|apartment|home)|packing')(
    (r'sort out first|what (?:should|do) (?:we|i) (?:do|sort|organi[sz]e) first|where (?:do|should) (?:we|i) start|first step',
     "A good order for a move:\n\n1. **Fix the date** and book the van or movers early; good dates go fast.\n2. **Declutter** before you pack: sell, "
     "give away or bin what you won't take.\n3. **Notify**: landlord or agent, utilities, internet (it can take weeks to set up), bank, doctor and "
     "post redirection.\n4. **Measure** the new place, including the stairs and doors, so the big furniture will fit.\n5. **Pack** room by room, "
     "starting with what you use least.\n6. **First-night box**: kettle, mugs, toilet roll, chargers, bedding, medicines and a change of clothes."),
    (r'movers|removal|ourselves|do it (?:our|my)selves|diy|hire (?:a )?van|worth (?:it|paying)',
     "It mostly comes down to three things:\n\n- **How much stuff and how many stairs.** A third floor with no lift and heavy furniture is exactly "
     "where movers earn their money, and where people hurt their backs.\n- **Budget.** Doing it yourselves with a hired van and friends is much "
     "cheaper; movers cost more but take a day, not a weekend.\n- **Time and help.** If you can't get two or three strong helpers, movers win.\n\n"
     "A middle way works well: pack the boxes yourselves and pay movers just for the furniture and the stairs."),
    (r'how (?:early|soon|far in advance|long before)|when should (?:we|i) start packing',
     "Start about three to four weeks ahead for a flat, longer for a house. Pack the things you rarely use first (books, out-of-season clothes, "
     "spare bedding, decorations), keep going a few boxes a day, and leave the kitchen and everyday things for the last few days. Label each box with "
     "the room and a short list of what's in it."),
    (r'pack(?:ing)? tips|how (?:should|do) (?:we|i) pack|boxes',
     "- Heavy things (books) in small boxes, light things in big ones.\n- Wrap plates and glasses in clothes or towels and stand plates on their edge.\n"
     "- Label each box on the side with the room and what's in it.\n- Keep screws and fittings in a bag taped to the furniture they belong to.\n"
     "- Pack a first-night box and keep it with you."),
    (r'\bcat\b|\bdog\b|\bpets?\b|car journeys?|travel sick',
     "For a pet on moving day:\n\n- Keep them shut in one quiet room (or with a friend) while things are carried out, so they can't slip out.\n"
     "- For the journey, use a secure carrier with a familiar blanket; cover it, keep the car calm and cool, and don't feed a big meal just before.\n"
     "- Ask your vet beforehand if they get very stressed or travel sick; there are calming aids and medicines.\n"
     "- In the new home, set up one room first with their bed, food, water and litter, and let them explore the rest gradually. Keep cats in for "
     "at least two to three weeks."),
)

# ------------------------------------------------------------------------------------------------------------ baking bread
topic('bread', r'bread|loaf|loaves|dough|bake|baking|yeast|sourdough')(
    (r'simplest|easiest|start with|first (?:loaf|bread)|beginner|never baked',
     "The easiest first loaf is a simple white or no-knead bread: just flour, water, salt and dried yeast.\n\n"
     "- **No-knead**: mix about 500 g strong white flour, 350 ml lukewarm water, 1 teaspoon salt and 1 teaspoon dried yeast; cover and leave 12 to 18 "
     "hours; shape gently, rise 1 to 2 hours, then bake in a hot lidded pot at about 230 °C for 30 minutes with the lid on and 10 to 15 off.\n"
     "- **Basic kneaded loaf**: knead 10 minutes, rise about 1 hour, shape into a tin, rise 30 to 45 minutes, bake about 30 to 35 minutes at 220 °C.\n\n"
     "Allow about 3 hours start to finish for a kneaded loaf, mostly waiting. Leave sourdough until you've made a few yeasted loaves."),
    (r'dense|heavy|didn\'t rise|flat|not rising|brick',
     "A dense loaf usually means it didn't rise enough: the yeast was old or killed by water that was too hot, the dough was too cold, or it went in "
     "the oven too early. Use lukewarm water, let the dough roughly double in size before shaping, and do the 'poke test' before baking: a gentle "
     "poke should spring back slowly."),
    (r'knead|how long',
     "Knead for about 10 minutes by hand (5 to 7 in a mixer) until the dough is smooth and springy; a small piece should stretch thin without "
     "tearing. Then let it rise somewhere warm until about doubled, usually 1 to 2 hours."),
    (r'sourdough|starter',
     "A sourdough starter takes 5 to 10 days to get going: mix equal weights of flour and water, keep it at room temperature, and each day throw "
     "most away and feed it fresh flour and water. It's ready when it reliably doubles within 4 to 8 hours of a feed and smells pleasantly sour."),
)

# ------------------------------------------------------------------------------------------------------------ money
topic('money', r'save money|saving|savings|budget|spend(?:ing)?|cheaper|afford|money|takeaway coffee|coffee (?:out|shop)|lunch out|buy lunch|debt')(
    (r'cut (?:that|it|this|back|down)|without giving (?:it )?up|easy way to (?:cut|spend less|save)|reduce',
     "Cut it down rather than out, so it sticks:\n\n- Keep the takeaway as a treat on set days (say two a week) instead of every day.\n"
     "- Make the cheap option easy: a decent home coffee and a travel cup ready by the door.\n- Go smaller or simpler when you do buy.\n"
     "- Put the money you don't spend into savings straight away, so you can see it add up."),
    (r'cheaper|worth it|save much|how much (?:would|could|do) i save|really much',
     "Yes, by a lot. A takeaway coffee costs many times a home-made one: even good beans or a pod work out at well under a dollar a cup, against "
     "several dollars in a café. At about $6 a day, five days a week, that's around $1,500 a year; making most of them at home saves the bulk of it, "
     "even after buying a simple coffee maker."),
    (r'lunch|instead',
     "- Cook a bit extra at dinner and take the leftovers.\n- Batch-make something on Sunday (soup, chilli, pasta salad, curry) and portion it for "
     "the week.\n- Keep easy standbys at work: oats, soup, tins of fish, crackers.\n- Start with two or three packed lunches a week rather than all five."),
    (r'budget|track|plan',
     "Yes, a weekly budget is one of the simplest ways to get spending under control. Set amounts for the things that vary (food, coffee and "
     "lunches, going out), pay the fixed bills and your savings first, and check once a week how you did. Paying for the flexible spending from one "
     "card or a separate account makes it easy to see what's left."),
    (r'emergency|how much (?:should|to) (?:i )?save|start saving',
     "A common rule of thumb is to build an emergency fund of three to six months of essential costs, starting with a first target of one month. "
     "Set up an automatic transfer on payday so saving happens before spending, even if it's a small amount at first."),
)

# ------------------------------------------------------------------------------------------------------------ sugar and snacks
topic('sugar', r'sugar|sugary|sweet(?:s|eners?)?|snack(?:s|ing)?|biscuits?|cookies|chocolate|cravings?')(
    (r'cut (?:back|down|it down)|reduce|less sugar|without hating|easiest way',
     "Cut it gradually so your taste adjusts:\n\n- Go from three teaspoons to two and a half for a week or two, then two, and so on; most people stop "
     "noticing each step.\n- Try a stronger or different tea (or a splash more milk), which can make it taste less in need of sugar.\n"
     "- Don't swap to honey or syrup, which are still sugar.\n- Expect the first week or two to be the hardest; after that, very sweet things often "
     "start to taste too sweet."),
    (r'sweeteners?|stevia|aspartame|sucralose',
     "Sweeteners have no or very few calories and don't raise blood sugar, so they can help while you cut down, and they're considered safe at "
     "normal amounts. The catch is that they keep your taste used to sweetness, so many people find it easier in the long run to reduce sweetness "
     "overall rather than swap one for the other."),
    (r'instead of|snack|eat (?:instead|rather)|what could i eat',
     "Some swaps that keep you going in the afternoon:\n\n- A piece of fruit with a handful of nuts.\n- Yoghurt (plain or Greek) with berries.\n"
     "- Oatcakes or wholegrain crackers with cheese or hummus.\n- Carrot or cucumber sticks with hummus.\n- A boiled egg.\n\n"
     "Keep them at your desk so they're as easy as the biscuits, and eat a proper lunch: a lot of afternoon snacking is hunger from too small a lunch."),
    (r'fruit',
     "Whole fruit does contain sugar, but it comes with fibre and water, which slow it down and fill you up, so it isn't counted with the added "
     "sugar health guidelines warn about. Juice and smoothies are different: they count as free sugar, so keep them to a small glass a day."),
)

# ------------------------------------------------------------------------------------------------------------ cycling
topic('cycling', r'cycl(?:e|ing)|bikes?|bicycles?|commut(?:e|ing) by bike|ride to work')(
    (r'what (?:do|should) i (?:need to )?(?:buy|get|have)|before i start|equipment|kit|gear',
     "For commuting about 8 km each way, the essentials are:\n\n- **A bike that fits** and is roadworthy (have a shop check the brakes and tyres).\n"
     "- **A helmet** and **front and rear lights** (lights are a legal requirement after dark in many places).\n- **A good lock**: a D-lock is the "
     "usual minimum in towns.\n- **Waterproof jacket** and, if it rains a lot, mudguards.\n- **A pump, spare inner tube and tyre levers**, and learn "
     "to fix a puncture.\n\nNice to have: a pannier or backpack, reflective clothing, and a change of clothes at work."),
    (r'safe|traffic|route|dangerous',
     "Plan a quieter route rather than the fastest (a cycle map or app helps), and try it on a weekend first. Ride a door's width away from parked "
     "cars, take the lane where it's narrow, make eye contact at junctions and stay out of lorries' blind spots, and use lights day and night."),
    (r'sweat|shower|arrive|clothes',
     "Ride at an easy pace, wear breathable layers and carry work clothes in a pannier. If there's no shower, a quick wash with wipes and a fresh "
     "shirt is usually enough over 8 km. Leaving a few clothes at work saves carrying them every day."),
    (r'rain|wet|winter|cold',
     "Mudguards make the biggest difference in the rain, then a waterproof jacket, gloves and overshoes or waterproof trousers if it's heavy. "
     "Brakes take longer to bite in the wet, so leave more room, and take care on painted lines, metal covers and leaves."),
)

# ------------------------------------------------------------------------------------------------------------ swimming
topic('swimming', r'swim(?:ming)?|pool|lengths?')(
    (r'panic|face in the water|face (?:is )?in|put my face|under ?water|breath(?:e|ing)',
     "Yes, that's very common for adults learning to swim. Breathing is the skill to build first:\n\n- Stand in shallow water, take a breath, put your "
     "face in and blow out slowly through your nose and mouth (bubbles), then lift and breathe in. Repeat until it feels boring.\n"
     "- Good goggles help a lot: being able to see underwater takes much of the panic away.\n- Hold the wall or a float and do the same while kicking.\n"
     "Most people find it eases within a few sessions."),
    (r'practi[sc]e first|start with|learn first|what should i (?:practi[sc]e|do|learn)',
     "In this order: breathing out into the water (bubbles), floating on your front and back with a float, gliding from the wall, kicking with a "
     "float, and then adding arms. Breaststroke or front crawl with a float are the usual first strokes. Short, frequent sessions help more than "
     "long ones."),
    (r'full length|realistic|doable|by the summer|how long (?:will|does) it take',
     "Very doable. Going twice a week, most adult beginners can swim a full length within a couple of months once they're comfortable breathing "
     "with their face in the water. Practise widths first, then build up to a length, and a few lessons make it quicker."),
    (r'embarrass|self-conscious|people (?:watching|looking)|others',
     "Most people at the pool are concentrating on their own lengths and won't notice. A few things help: go at quieter times (early morning or "
     "adult-only sessions), use the shallow end or a learner lane, and remember that adult beginners are common; lifeguards and other swimmers usually "
     "respect someone learning. An adult lesson group puts you among people at the same stage."),
)

# ------------------------------------------------------------------------------------------------------------ dance
topic('dance', r'salsa|danc(?:e|ing)|tango|ballroom|bachata|swing|zumba')(
    (r'step(?:ping|ped)? on|feet|toes|clumsy|everyone do that|at the start|normal',
     "Yes, practically everyone does that at first. You're thinking about the steps, the beat and your partner at the same time, and that takes a "
     "few weeks to become automatic. Keep your steps small, listen for the count (in salsa, 1-2-3, pause, 5-6-7), practise the basic step at home "
     "to a few songs, and laugh it off: teachers and partners expect it from beginners."),
    (r'practi[sc]e|at home|get better|improve',
     "Practise the basic step to music at home for ten minutes a few times a week, counting out loud at first. Watch your teacher's footwork videos "
     "if they share them, and dance with as many different partners as you can at class; that improves leading and following fastest."),
)

# ------------------------------------------------------------------------------------------------------------ instruments
topic('instrument', r'guitar|ukulele|uke|piano|keyboard|violin|cello|drums?|flute|bass|instrument|chords?|practi[sc]e')(
    (r'(?:which|what) chords?|chords? (?:should|to) (?:i )?learn|first chords|learn first',
     None),      # filled by chords() below, which knows the instrument
    (r'fingers? (?:get|are|feel) tired|hands? (?:get|are|feel) tired|tired fingers|fingers? hurt|fingertips?',
     None),      # filled by fingers() below
    (r'how (?:long|often|much) (?:should|do) i practi[sc]e|practi[sc]e (?:every|each|a) day|practice routine',
     "Short and regular beats long and rare: 15 to 30 minutes most days is ideal for a beginner. Start with a few minutes of warm-up, then the one "
     "thing you're working on, and end by playing something you enjoy. Stop before your hands are sore."),
    (r'song|songs|play (?:something|a song)|first song',
     "Pick songs with only three or four chords you already know, at a slow tempo, and use a simplified version at first. Playing real songs early "
     "keeps practice fun; add a new chord or rhythm only once the current one feels easy."),
)

# ------------------------------------------------------------------------------------------------------------ language learning
topic('language', r'spanish|french|german|italian|japanese|chinese|mandarin|portuguese|korean|arabic|russian|dutch|language|vocabulary|words?|duolingo')(
    (r'forget(?:ting)?|remember|keep forgetting|won\'t stick|memori[sz]',
     "Completely normal: almost everyone forgets new words several times before they stick. What helps most is reviewing at growing intervals "
     "(spaced repetition, as in Anki or many apps), learning words in short phrases rather than alone, and using them: say them out loud, write a "
     "sentence with each, and look for them in things you read or watch."),
    (r'realistic|by (?:then|march|april|may|june|july|the summer)|hold a (?:basic )?conversation|how long (?:will|does) it take',
     "Yes, for a basic conversation, if you focus on it. With regular daily study, a few months is enough for simple exchanges: greetings, ordering, "
     "asking directions, talking about yourself. Spend part of each session speaking out loud, learn the phrases you'll actually need on the trip, "
     "and try a few conversations with a tutor or language partner before you go."),
)

# ------------------------------------------------------------------------------------------------------------ starting school
topic('school', r'school|nursery|kindergarten|reception|first day|teacher')(
    (r'nervous|scared|worried|anxious|help (?:him|her|them)|ideas|tips|prepare',
     "A few things that help a child starting school:\n\n- Talk about it positively and simply: what a day will look like, who will be there.\n"
     "- Visit or walk past the school beforehand, and look at photos of the classroom if they share them.\n"
     "- Read a picture book about starting school together.\n- Practise the practical bits: shoes, coat, lunchbox, asking to go to the toilet.\n"
     "- Keep goodbyes short and cheerful, and tell the teacher about the nerves; they're used to it.\n\n"
     "Most children settle within a few weeks."),
)

# ------------------------------------------------------------------------------------------------------------ compost
topic('compost', r'compost(?:ing)?|food scraps|worm (?:bin|farm)|bokashi')(
    (r'what (?:do|should) i (?:actually )?need|get started|how (?:do|should) i start|smell',
     "On a small balcony there are two easy ways:\n\n- **Bokashi bin**: an airtight bucket where kitchen scraps are fermented with bran; compact and "
     "doesn't smell when sealed. The result then needs burying in soil or a planter.\n- **Worm bin (wormery)**: worms turn scraps into compost; it "
     "needs some shade and not too much at once.\n\nEither way you'll need a lidded bin, 'browns' such as shredded cardboard or paper, and a small "
     "caddy in the kitchen. A well-run bin smells earthy, not bad; a bad smell means too wet or too many scraps, fixed by adding more cardboard and "
     "leaving out meat, dairy and oily food."),
)

# ------------------------------------------------------------------------------------------------------------ explanations people often follow up on
topic('rainbow', r'rainbows?')(
    (r'second (?:one|rainbow|bow)|fainter|double rainbow|another (?:one|rainbow)|two rainbows',
     "That's a double rainbow. The second, fainter bow comes from light that reflects twice inside each raindrop instead of once. The extra "
     "reflection loses more light, so it's dimmer, and it flips the order, so its colours run the other way round (red on the inside). The darker "
     "band of sky between the two bows is called Alexander's band."),
)
topic('lightning', r'lightning|thunder(?:storm)?s?|storm')(
    (r'(?:count|counted|\d+|one|two|three|four|five|six|seven|eight|nine|ten) seconds?\b.*\b(?:far|away|distance)|how far (?:away )?is (?:the|a) storm',
     "Sound travels about a kilometre every 3 seconds (a mile every 5). So count the seconds between the flash and the thunder and divide by 3 for "
     "kilometres or by 5 for miles: five seconds means the storm is about 1.7 km (about a mile) away. If the gap is 30 seconds or less, you're within "
     "range of a strike, so get indoors."),
    (r'how hot|temperature',
     "A lightning channel heats the air to around 30,000 °C (roughly 50,000 °F) for a split second, about five times hotter than the surface of the "
     "Sun. That sudden heating makes the air expand explosively, which is the thunder you hear."),
    (r'safe|indoors|outside|car|tree',
     "The safest place is inside a building or a hard-topped car with the windows closed. Outdoors, avoid open ground, hilltops, water and lone "
     "trees; there is no truly safe spot outside. Wait 30 minutes after the last thunder before going back out."),
)
topic('explain', r'microwave|noise[- ]cancell?ing|headphones')(
    (r'metal|foil|spoon|fork',
     "Metal reflects microwaves instead of absorbing them, and they make electric currents in it. Thin or pointed metal (foil edges, forks, "
     "gold-trimmed plates) concentrates that charge so sparks can jump, which can start a fire or damage the oven. Smooth, thick metal is less "
     "dangerous, but it shields the food so it doesn't heat, which is why it's best to keep metal out altogether."),
    (r'plane|cafe|café|talking|voices|people',
     "Noise-cancelling works best on steady, low-pitched sound, like an aircraft engine's drone: the headphones measure it with microphones and play "
     "the opposite wave to cancel it, which is easy for a constant hum. Voices are higher-pitched and change all the time, so the electronics can't "
     "predict and cancel them nearly as well; the ear cushions block some of them, but conversation still gets through."),
)

# ------------------------------------------------------------------------------------------------------------ travel
topic('travel', r'trip|travel(?:ling)?|holiday|vacation|flight|visit(?:ing)?|going to (?-i:[A-Z])[a-z]+|abroad')(
    (r'what (?:should|could|would) (?:i|we) do (?:there )?first|first thing|when (?:i|we) (?:arrive|get there|land)',
     "Good first steps in a new place: drop the bags and freshen up, get a local transport card or ticket app, find a cash machine or check your card "
     "works, and then take an easy walk around the area you're staying in and have a meal somewhere local. Save the big sights for the next day, "
     "when you're rested. If there's a time difference, staying up until a normal bedtime helps beat jet lag."),
    (r'jet ?lag',
     "Switch to the new time zone as soon as you board: sleep or stay awake to match it, get daylight in the morning at your destination, drink "
     "water rather than alcohol on the flight, and keep naps under half an hour. Going east is usually harder than going west."),
    (r'pack|bring|take with',
     "Pack less than you think: clothes for about a week and do a wash, layers rather than bulky items, and comfortable shoes you've already worn. "
     "Keep documents, medicines, chargers and a change of clothes in your hand luggage, and check the plug type and the weather before you go."),
)


# ---------------------------------------------------------------------------------------------- instrument specifics
CHORDS = {
    'ukulele': "Start with C, A minor, F and G: those four cover hundreds of songs. C and A minor are one and two fingers, so begin there, then add F, "
               "and G last as it's the hardest. Practise switching between pairs (C to A minor, F to G) slowly, and play a simple song as soon as "
               "you have three of them.",
    'guitar': "The usual first chords are E minor, A minor, C, G and D. E minor and A minor are the easiest, so begin with those; then G, C and D. "
              "With G, C and D you can already play a huge number of songs. Practise changing between two chords slowly until it's smooth.",
    'piano': "On piano, start with the C major chord (C-E-G) and the other white-key chords built the same way: F major, G major and A minor. "
             "Those four (C, G, A minor, F) play a lot of pop songs. Learn them with your right hand first, then add the root note in the left hand.",
}
FINGERS = {
    'piano': "Yes, that's normal when you're starting the piano: the small muscles in your fingers and hands aren't used to the work yet, and it "
             "improves with regular practice over a few weeks. Keep your wrists level and relaxed, curve your fingers, and don't press harder than "
             "you need to. Practise in short sessions with breaks, and stop if you feel pain, tingling or numbness rather than tiredness.",
    'guitar': "Yes, sore fingertips are normal when you start guitar. Pressing the strings puts a lot of pressure on a small patch of skin, and "
              "over the first few weeks your fingertips build up calluses; most people find the pain fades noticeably within two to four weeks. "
              "Practise little and often, press only as hard as needed for a clean note, and stop if you get sharp pain.",
    'ukulele': "Yes, sore fingertips are normal at first on the ukulele, though nylon strings are gentler than a steel-string guitar. Calluses "
               "build up over a couple of weeks of regular practice. Keep sessions short, press only as hard as you need, and rest if it gets painful.",
    'violin': "Yes, that's normal at first: your fingertips and the small muscles in your hand are getting used to the strings. It eases over a few "
              "weeks. Keep your hand relaxed, don't squeeze the neck, and practise in short sessions.",
}


VARIANTS = {
    "Water {thing} when the top few centimetres": [
        (r'\b(?:cact(?:us|i)|succulents?|aloe)\b',
         "Much less often than most plants: cacti and succulents store water. Water {thing} thoroughly only when the soil has dried out completely, "
         "which is usually every two to three weeks in spring and summer and about once a month or less in winter. Use a gritty, fast-draining mix "
         "and a pot with a drainage hole; soft, mushy or yellowing stems are the sign of too much water.")],
    "Kittens need several small meals a day": [
        (r'\b(?:cat|he|she) is (?:[2-9]|1[0-9]|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen)\b|\b(?:adult|older|senior|elderly) cat\b|'
         r'\b(?:[2-9]|1[0-9]|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[- ]years?[- ]old\b',
         "Most adult cats do well on two meals a day, or several small ones if they prefer to graze. Follow the packet amount for {thing}'s weight, "
         "adjust so you can feel but not see the ribs, and count treats in the total. Older cats (from about 11) often need a senior food, and a "
         "change in appetite or weight at that age is worth a vet check. Fresh water should always be available, and wet food helps them drink enough.")],
}


def instrument_of(text):
    low = text.lower()
    for name, pat in (('ukulele', r'\b(?:ukulele|uke)\b'), ('piano', r'\b(?:piano|keyboard)\b'), ('violin', r'\b(?:violin|viola|cello)\b'),
                      ('guitar', r'\bguitar\b')):
        if re.search(pat, low):
            return name
    return None


def thing_name(turns, t):
    """What the user called the thing: a pet's name, or 'your monstera'."""
    text = ' '.join(turns[-6:])
    if t.key in ('dog', 'cat'):
        m = re.findall(r"\b(?:called|named|name is|name's)\s+([A-Z][a-z]+)\b", text)
        if m:
            return m[-1]
        m = t.words.findall(text)
        return f'your {m[-1].lower()}' if m else ('your dog' if t.key == 'dog' else 'your cat')
    if t.thing:
        m = [w for w in t.words.findall(text) if w.lower() not in ('plant', 'plants', 'houseplant', 'houseplants', 'house plant', 'house plants')]
        n = (m[-1] if m else 'plant').lower()
        return t.thing.replace('{n}', n)
    return ''


def topics_in(turns):
    """Topics the conversation is about, nearest first: words in the turns, or a noun whose WordNet class is the topic's."""
    from .advisor import general
    found = []
    for t in reversed(turns[-6:]):
        hits = [x for x in T if x.words.search(t)]
        if COOKING.search(t):
            hits = [x for x in hits if x.key not in GARDEN]        # roast potatoes are a cooking question
        if not hits and not re.search(r"(?i)\b(?:roast\w*|crisp\w*|soggy|cook\w*|bak(?:e|ed|ing)|fr(?:y|ied|ying)|boil\w*|oven|recipe|tray|pan|eat|taste\w*)\b", t):
            # a noun whose WordNet class is a topic's ("monstera" is a houseplant); not for food being cooked ("roast potatoes"
            # are vegetables, but not a gardening question)
            for w in oc.content(t):
                if oc.is_noun(w) and oc.idf(oc.stem(w)) > 4:
                    classes = set(general(w.lower()))
                    hits += [x for x in T if x.classes & classes]
        for x in hits:
            if x.key not in [f.key for f in found]:
                found.append(x)
    return found


def reply(messages):
    """An authored answer for this topic and aspect, or None."""
    turns = oc.user_turns(messages)
    if not turns:
        return None
    last = turns[-1].strip()
    asked = [s for s in re.split(r'(?<=[.!?])\s+', last) if s.strip().endswith('?')]
    q = asked[-1] if asked else last
    if not asked and not re.match(r'(?i)\s*(?:any|some)\s+(?:tips|ideas|advice)|tell me|how (?:do|can|should) i', q):
        return None
    if re.search(r"(?i)\b(?:did|have) (?:i|we) (?:say|said|tell|told|mention)|\bagain\s*\??\s*$|^\s*what(?:'s| is| was) (?:my|our) [a-z ]+?(?: now)?\s*\??\s*$|"
                 r"^\s*(?:when|where|what time) (?:is|are|was) (?:my|our|the|mum|mom|dad)\b", q):
        return None                             # asking back what was said ("What's my budget now?") is for the memory, not advice
    from .applicability import conflict
    found = topics_in(turns)
    # a topic that sets the terms of the whole chat ("she's vegetarian", "the smoke alarm") comes before a general one picked
    # up from the last question's words ("main course")
    found = [t for t in found if t.key in STICKY] + [t for t in found if t.key not in STICKY]
    for t in found:
        for pattern, text in t.aspects:
            if not pattern.search(last):        # the question and what was said with it ("My fingers get tired ... Is that normal?")
                continue
            if text is None:
                inst = instrument_of(' '.join(turns[-6:])) or 'guitar'
                text = CHORDS.get(inst) if 'chord' in pattern.pattern else FINGERS.get(inst)
                if not text:
                    continue
                from .applicability import conflict
                if conflict(' '.join(turns[-6:]), text):
                    continue
            context = ' '.join(turns[-6:]).lower()
            for cue, alt in next((v for k, v in VARIANTS.items() if text.startswith(k)), ()):
                if re.search(cue, context):
                    text = alt
                    break
            out = text.replace('{thing}', thing_name(turns, t) or 'it')
            said = {oc.stem(w) for w in oc.content(' '.join(turns[-3:])) if len(w) > 3}
            hit = pattern.search(last)
            picked_by = {oc.stem(w) for w in oc.content(hit[0])} if hit else set()
            if said and not ((said - picked_by) & {oc.stem(w) for w in oc.content(out)}) and not t.words.search(last):
                continue                        # salary tips for "how to raise our kids": nothing but the matched word in common
            if conflict(' '.join(turns[-6:]), out):
                continue                        # about something else: a phone battery for a smoke alarm, chicken for a vegetarian
            out = re.sub(r'^(?:your|Your) (\w)', lambda m: 'Your ' + m[1], out) if out.startswith(('your', 'Your')) else out
            out = out[:1].upper() + out[1:]
            return dict(route='chat/advice', response=out, sources=[],
                        details=f'Authored everyday advice: topic "{t.key}", aspect /{pattern.pattern[:60]}/ (advice_library.py).')
    return None


def respond(messages):
    try:
        return reply(messages)
    except Exception:
        return None


from . import advice_library_more  # noqa: E402,F401  (adds more topics to T)
STICKY = {'vegetarian', 'smoke_alarm'}
from . import advice_library_extra  # noqa: E402,F401  (ailments, computers, flights, business, family, plants while away)
from . import advice_library_r14  # noqa: E402,F401  (vegetarian guests, smoke alarms, clover in lawns)
