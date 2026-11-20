"""Advice schemas: what a sensible person knows about a whole class of things, not about one thing.

Most everyday problems belong to a handful of classes: plumbing, household appliances, gadgets, the fabric of a house,
clothes and soft furnishings, plants, pets, children, other people, food and cooking, the body, cars and bikes, money,
and travel. For each class this file holds the usual causes, the first checks, the fix, the tools, who to call, the
warning signs, how to prevent it and what is normal. An answer is put together from the class and from the question
asked ("why", "can I fix it myself", "is it anything to worry about", "what will I need"), and it names the user's
own thing. CAEL knows the class of a thing from a word list (LEXICON), with WordNet's classes as a fallback.

This is the pattern half of "know the pattern and search well": general guidance that is right for the whole class.
The Researcher's threads add specifics when there are any. Authored text; no model.
"""
import re

LEXICON = {
    'plumbing': 'tap taps faucet toilet cistern flush sink basin drain drains plughole pipe pipes shower showerhead bath bathtub radiator radiators boiler '
                'valve stopcock hose washer u-bend trap outdoor-tap water-heater immersion',
    'appliance': 'fridge freezer refrigerator washing-machine washer dryer tumble-dryer dishwasher oven cooker hob microwave kettle toaster iron hoover '
                 'vacuum blender mixer food-processor slow-cooker extractor fan dehumidifier heater smoke-alarm alarm doorbell thermostat coffee-machine',
    'gadget': 'phone smartphone iphone laptop computer pc tablet ipad printer router wifi wi-fi broadband tv television speaker headphones earbuds '
              'charger cable keyboard mouse screen monitor watch smartwatch console camera app email',
    'house': 'window windows door doors wall walls ceiling floor floorboard floorboards roof gutter gutters fence gate shed tile tiles grout sealant '
             'silicone skirting stair stairs staircase loft hatch lock handle hinge hinges drawer cupboard shelf curtain rail mirror patio decking '
             'washing-line line paint wallpaper damp mould mold condensation draught draft',
    'fabric': 'sofa couch carpet rug mattress pillow duvet curtain curtains cushion shirt shirts jumper sweater jeans trousers coat jacket dress '
              'shoes boots trainers clothes clothing towel towels sheets doormat mat stain stains fabric suede leather wool',
    'plant': 'plant plants tree trees shrub hedge lawn grass flower flowers rose roses tomato tomatoes basil mint herb herbs orchid cactus succulent '
             'succulents palm fern seedling seedlings bulb bulbs lavender pear apple fig lemon courgette courgettes cucumber strawberries lettuce '
             'potatoes carrots beans hydrangea ivy moss weeds vegetable vegetables garden',
    'pet': 'dog dogs puppy puppies cat cats kitten kittens rabbit rabbits bunny hamster hamsters guinea-pig budgie budgies parrot parrots bird birds '
           'fish goldfish tortoise turtle ferret ferrets chicken chickens horse pony pet pets',
    'child': 'baby babies toddler toddlers child children kid kids son daughter boy girl teenager teen teens twins nine-year-old four-year-old '
             'two-year-old three-year-old five-year-old six-year-old seven-year-old eight-year-old ten-year-old month-old',
    'person': 'friend friends neighbour neighbours neighbor neighbors colleague colleagues coworker boss manager partner husband wife boyfriend '
              'girlfriend mother-in-law father-in-law in-law in-laws sister brother mum mom dad mother father parent parents flatmate roommate '
              'housemate relative relatives landlord landlady family',
    'food': 'bread dough loaf cake cakes sponge pastry pie pancakes pancake rice pasta potatoes chips roast stew soup sauce gravy curry custard '
            'eggs meringue jam scones cookies biscuits brownies pizza steak chicken beef garlic onions popcorn gnocchi flapjacks dish recipe '
            'dinner meal',
    'body': 'back neck shoulder shoulders knee knees ankle foot feet calf muscle muscles head headache eyes ear ears nose throat cough cold skin '
            'rash cramp cramps stomach tooth teeth gums mouth ulcer blister blisters hands fingers wrist hip joints sleep tired insomnia',
    'vehicle': 'car cars bike bicycle tyre tyres tire tires engine clutch brakes battery windscreen motorbike scooter van',
    'money': 'rent bill bills fine fee fees insurance mortgage loan debt budget savings salary pay price tax council-tax deposit subscription '
             'membership contract tariff',
    'travel': 'flight flights layover airport plane train trip holiday hotel passport luggage suitcase visa ferry cruise jet-lag road-trip',
}
WORDS = {}
for cls, words in LEXICON.items():
    for w in words.split():
        WORDS.setdefault(w.replace('-', ' '), cls)
WN = {'appliance': ('appliance', 'home appliance', 'white goods', 'machine'), 'gadget': ('computer', 'electronic equipment', 'electronic device'),
      'plant': ('plant', 'herb', 'shrub', 'tree', 'vascular plant', 'flower', 'vegetable'), 'pet': ('animal', 'bird', 'mammal', 'domestic animal', 'canine', 'feline'),
      'child': ('child', 'juvenile', 'offspring'), 'person': ('person', 'relative'), 'food': ('food', 'dish', 'baked goods', 'foodstuff'),
      'vehicle': ('vehicle', 'motor vehicle', 'wheeled vehicle'), 'body': ('body part', 'symptom', 'organ')}

S = {   # per class: causes, first, fix, tools, pro, urgent, prevent, normal, diy
    'plumbing': dict(
        causes="a worn washer or seal, a loose joint, a faulty valve or cartridge, or a build-up of limescale or debris",
        first="find where exactly the water is coming from (the spout, the handle, a joint or the pipe) and whether the isolating valve or stopcock turns it off",
        fix=["Turn off the water to it first: an isolating valve on the pipe, or the main stopcock.", "Open it up and check the washer, O-ring or cartridge; worn rubber parts are cheap and are the usual cause.",
             "Clean off limescale and grit, refit with a new part of the same size, and tighten joints gently (over-tightening cracks fittings).",
             "Turn the water back on slowly and check for drips."],
        tools="an adjustable spanner, screwdrivers, replacement washers or a cartridge (take the old one to the shop to match it), PTFE tape and an old towel",
        pro="a plumber", urgent="water is coming through a ceiling or near electrics, a pipe has burst, or you can't turn the supply off",
        prevent="don't over-tighten taps, descale in hard-water areas, and lag outdoor pipes and taps before winter",
        normal="Drips and slow leaks are very common and rarely an emergency, but they waste a lot of water and get worse, so they're worth fixing soon.",
        diy="Washers, cartridges and simple blockages are well within reach for most people with basic tools. Anything involving the pipework itself, gas, or a boiler is a job for a professional."),
    'appliance': dict(
        causes="a blocked filter or vent, a worn seal, a build-up of limescale or dirt, a faulty part such as a thermostat or element, or simply age",
        first="unplug it, check the plug, fuse and any filters or vents, and look up the model number and the manual's troubleshooting page",
        fix=["Unplug it before doing anything.", "Clean the filters, seals and vents, and descale it if your water is hard.",
             "Check the manual's troubleshooting section for your model: many 'faults' are a setting or a reset.", "If a part has failed, the model number lets you find the exact replacement part or a repair guide."],
        tools="the manual (most are online by model number), a screwdriver, a soft brush and cloth, and descaler or white vinegar",
        pro="a repair technician or the manufacturer's service line", urgent="it sparks, smells of burning, trips the electrics or leaks near the plug",
        prevent="clean filters and seals regularly, descale it every month or two in hard-water areas, and don't overload it",
        normal="Some noise, heat and wear are normal for any appliance, but a new smell, a new noise or a change in how it works usually means something needs attention.",
        diy="Cleaning, descaling and replacing simple parts like filters, seals or a fuse are fine to do yourself. Anything inside the electrics, or gas appliances, is a job for a qualified technician; and if it's still under guarantee, contact the maker first."),
    'gadget': dict(
        causes="a software glitch, a loose or worn cable or port, an out-of-date update, a full storage, or a battery that is wearing out",
        first="restart it properly, try a different cable, charger or socket, and check for updates",
        fix=["Restart it (a full shut-down, not just sleep).", "Try another cable and charger, and clean the port gently with a dry wooden toothpick or a soft brush.",
             "Install pending updates, free up some storage, and remove anything installed just before it started.", "If it still misbehaves, back up your data and look up your model's support page or reset steps."],
        tools="a spare cable and charger to test with, a soft brush or toothpick for ports, and the maker's support page for your model",
        pro="the manufacturer's support or a phone or computer repair shop", urgent="the battery is swollen, it gets very hot, or it smells of burning",
        prevent="keep it updated, use a decent cable and charger, keep ports clean and back up regularly",
        normal="Small glitches are common and a restart fixes a surprising number of them; a problem that keeps coming back after a restart and an update usually points to hardware.",
        diy="Restarts, updates, a different cable, cleaning ports and freeing storage are all safe to try. Opening it up or replacing a battery is best left to a repair shop, especially if it's under warranty."),
    'house': dict(
        causes="damp or condensation, swelling or shrinking with the weather, worn or loose fixings, old paint or sealant, or settlement over time",
        first="look closely at where the problem starts and whether it changes with the weather or with heating and ventilation",
        fix=["Find the cause first: damp, a loose fixing, a worn part, or paint and sealant that has failed.", "Tighten or replace loose screws and hinges, and ease sticking parts with a little lubricant or a light sand.",
             "Cut out and replace failed sealant or grout rather than covering it over.", "For damp and condensation, improve ventilation and heating, and dry the area before redecorating."],
        tools="screwdrivers, a utility knife, sandpaper, a filler or sealant gun, a spirit level and the right fixings for the wall",
        pro="a handyman or builder (or your landlord, if you rent)", urgent="there's water coming in, a crack is widening, or something structural is moving",
        prevent="ventilate kitchens and bathrooms, keep gutters clear, and fix small problems before they spread",
        normal="Older houses move and age, so small cracks, sticking doors and the odd draught are common; what matters is whether it's getting worse.",
        diy="Most small fixes (tightening, easing, resealing, filling) are fine to do yourself. Anything structural, electrical or on a roof is worth a professional, and if you rent, report it to your landlord first."),
    'fabric': dict(
        causes="a spill or stain that has set, sweat and body oils, damp, heat, or washing at the wrong temperature",
        first="check the care label, and test any cleaner on a hidden spot first",
        fix=["Act quickly on stains: blot (don't rub) to lift as much as you can.", "Rinse from the back with cold water; hot water can set protein stains like blood or sweat.",
             "Use a cleaner suited to the fabric (washing-up liquid, an enzyme stain remover, or a little white vinegar), test it first, then wash as the label says.",
             "For smells, wash or air it thoroughly and dry it completely; bicarbonate of soda sprinkled on, left and vacuumed off helps carpets and mattresses."],
        tools="clean white cloths, washing-up liquid, an enzyme stain remover, white vinegar and bicarbonate of soda",
        pro="a dry cleaner or an upholstery and carpet cleaner", urgent="it's a delicate, valuable or dry-clean-only item: don't experiment, take it to a professional",
        prevent="treat spills straight away, follow the care label, and let things dry fully before putting them away",
        normal="Most everyday stains come out with patience if you deal with them before they're dried or ironed in.",
        diy="Most stains and smells can be handled at home with gentle products and a test patch first. Delicate, valuable or dry-clean-only items are best left to a professional cleaner."),
    'plant': dict(
        causes="watering (too much more often than too little), the wrong amount of light, poor drainage, pests, or the wrong time of year",
        first="feel the soil a few centimetres down, check the pot drains, and look under the leaves for pests",
        fix=["Water only when the top few centimetres of soil are dry, and make sure the pot drains.", "Move it to the light it likes: most need bright, indirect light; fruiting plants need plenty of sun.",
             "Remove badly damaged leaves or stems, and treat pests with a jet of water or insecticidal soap.", "Feed it during the growing season, and give it time: plants respond over weeks, not days."],
        tools="a pot with drainage holes, fresh compost, clean secateurs, and a balanced feed",
        pro="a garden centre (take a photo or a leaf)", urgent="it is spreading quickly to other plants, which suggests pests or disease",
        prevent="water by feel rather than by schedule, give it the right light, and check for pests now and then",
        normal="Plants often drop a few old leaves or slow down in winter; it's the newest growth that tells you how it's doing.",
        diy="Almost everything with plants is DIY: watering, light, pruning and repotting. A garden centre can identify pests or diseases from a photo."),
    'pet': dict(
        causes="stress or boredom, a change in routine or home, fear, or an underlying health problem (especially if the change was sudden)",
        first="think about what changed recently, and rule out pain or illness, especially if it came on suddenly or in an older animal",
        fix=["Rule out health first: a sudden change in behaviour is often pain or illness, so a vet check is worth it.", "Keep routines steady, and give them a quiet, safe space of their own.",
             "Reward the behaviour you want straight away, and avoid punishment, which tends to make fear worse.", "Build up to difficult things in small, calm steps, with treats, over days or weeks."],
        tools="treats they love, a comfortable safe space or crate, enrichment toys, and patience",
        pro="your vet (and a qualified behaviourist for persistent behaviour problems)", urgent="they stop eating or drinking, seem in pain, have trouble breathing, or there's blood",
        prevent="regular routines, enough exercise and enrichment for the species, and regular vet checks",
        normal="Many behaviour quirks are normal for the species, but a sudden change in eating, drinking, toileting or behaviour is a reason to see the vet.",
        diy="Routine, enrichment and reward-based training are things you can do at home. Anything that might be health-related, or doesn't improve, is for the vet."),
    'child': dict(
        causes="tiredness, hunger, big changes (a new sibling, school, a move), wanting attention or control, or simply their stage of development",
        first="look for a pattern: when it happens, what comes just before, and what changed recently",
        fix=["Stay calm and consistent: the same response every time works better than a big reaction.", "Give attention and praise for the behaviour you want to see more of.",
             "Keep routines predictable, and give them small, real choices so they feel some control.", "Talk about feelings in simple words, and give it a few weeks: change takes time."],
        tools="a predictable routine, a simple reward chart for older children, and time together one to one",
        pro="your GP or health visitor, or the school if it's happening there", urgent="you're worried about their health, safety, weight, development or mood",
        prevent="steady routines, enough sleep, and some one-to-one time each day",
        normal="Phases like this are very common at many ages and usually pass with patience and consistency.",
        diy="Most behaviour phases respond to calm, consistent handling at home. If it's affecting their health, school or happiness, talk to your GP, health visitor or the school."),
    'person': dict(
        causes="different expectations, habits they may not realise bother you, stress on their side, or something that has never been talked about",
        first="decide what you actually want to change, and pick a calm, private moment to raise it",
        fix=["Pick a calm moment, not straight after it has happened.", "Talk about your side: 'When X happens, I feel Y' rather than 'You always...'.",
             "Ask for one specific change, and listen to their side too.", "Agree something concrete, and be ready to bring it up again kindly if it slips."],
        tools="a calm moment, one specific request, and a willingness to listen",
        pro="a mediator, or for neighbours and landlords your council or a tenants' advice service", urgent="you feel unsafe or threatened",
        prevent="raise small things early and calmly, before they build up",
        normal="Most people don't realise how their habits affect others until it's mentioned kindly; it's very common and usually solvable.",
        diy="A calm, specific conversation solves most of these. If it doesn't, or you feel unsafe, get outside help."),
    'food': dict(
        causes="the temperature (oven or pan too hot or not hot enough), the proportions, too much or too little liquid, the timing, or the ingredients' freshness",
        first="check the recipe's quantities and temperatures, and think about what you did differently from it",
        fix=["Measure by weight if you can: small changes in proportions make a big difference.", "Get the temperature right: preheat the oven or pan fully, and check it if your oven runs hot or cool.",
             "Don't overcrowd the pan, and give things time (resting dough, letting a pan heat up, letting a cake cool).", "Change one thing at a time next round, so you know what made the difference."],
        tools="kitchen scales, an oven thermometer, and a good non-stick or well-seasoned pan",
        pro="a tried-and-tested recipe from a reliable source", urgent="it's a food-safety question (meat not cooked through, leftovers kept too long): when in doubt, throw it out",
        prevent="weigh ingredients, preheat properly, and note what worked",
        normal="Almost everyone has this happen while learning; it usually comes down to one variable you can fix.",
        diy="This is all about practice and small adjustments; nothing here needs a professional."),
    'body': dict(
        causes="strain or overuse, posture, dehydration, poor sleep, or a minor infection or irritation",
        first="rest the area, notice what makes it better or worse, and check for warning signs",
        fix=["Rest it and avoid what makes it worse for a few days, but keep gently moving.", "Ice in the first day or two for a fresh strain or swelling; gentle heat later for stiffness.",
             "Drink enough water, stretch gently, and use simple painkillers if they're suitable for you.", "If it isn't clearly improving in a week or two, get it checked."],
        tools="an ice pack or bag of frozen peas wrapped in a cloth, a heat pad, and simple painkillers if suitable",
        pro="a pharmacist, your GP, or a physiotherapist", urgent="the pain is severe, there's numbness, weakness, a high fever, trouble breathing, or it's getting worse quickly",
        prevent="warm up before exercise, take breaks from sitting, and build activity up gradually",
        normal="Minor aches, strains and irritations are very common and usually settle within a week or two with simple care.",
        diy="Most minor strains and irritations get better with rest and simple care at home; a pharmacist can advise. Anything severe, worsening or not improving is for a doctor."),
    'vehicle': dict(
        causes="wear on a part, low fluid or tyre pressure, a weak battery, or technique (for clutch and gears)",
        first="check the simple things: tyre pressures, fluid levels, warning lights and the manual",
        fix=["Look up any warning light in the manual.", "Check tyre pressures and fluid levels, and top up to the marked levels.",
             "Note exactly when it happens (braking, turning, starting, at speed, cold or warm): it tells a mechanic where to look.",
             "If a part has worn, get it checked rather than driving on it."],
        tools="the manual, a tyre pressure gauge, and the right fluids for your vehicle",
        pro="a garage or mechanic (or a bike shop)", urgent="the brakes, steering or tyres feel wrong, or a red warning light comes on",
        prevent="regular servicing, checking tyres monthly, and not ignoring warning lights",
        normal="Small noises and vibrations are very common and often harmless; it's new or worsening symptoms, or anything to do with brakes or steering, that need checking.",
        diy="Checking pressures, fluids and bulbs is easy to do yourself. Brakes, steering and anything safety-critical are for a garage."),
    'money': dict(
        causes="a price rise, a fee or penalty, a contract that has rolled over, or spending that has crept up",
        first="read the letter or contract carefully: what exactly is changing, from when, and what notice you were given",
        fix=["Check your contract or agreement for the rules on rises, fees and notice.", "Compare with what others charge, so you know whether it's fair.",
             "Ask politely for a better deal or a discount (or appeal a fine) in writing, giving your reasons.", "If you're not happy with the answer, look at switching or at free advice services."],
        tools="the contract or letter, your recent bills or statements, and a comparison site",
        pro="a free advice service (Citizens Advice in the UK, or a tenants' or consumer advice service)", urgent="you're struggling to pay: contact the company early and ask about a payment plan",
        prevent="note renewal dates, review bills yearly, and set a simple budget",
        normal="Rises at renewal are very common, and a polite request or a switch often gets a better price.",
        diy="Negotiating, appealing and switching are all things you can do yourself; free advice services can help if it's a legal or contract question."),
    'travel': dict(
        causes="tiredness and changes to routine, crowds and queues, and unfamiliar rules at airports and borders",
        first="check the airline's and airport's own pages for the rules, facilities and times",
        fix=["Check the rules first: visas, transit, baggage and what you can take through security.", "Book what helps in advance: seats, a bassinet, airport lounges or transit hotels, transfers.",
             "Pack the essentials in your hand luggage: documents, medicines, chargers, snacks and a change of clothes.", "Build in spare time for queues and delays."],
        tools="your booking details, the airline's app, and a well-packed hand luggage bag",
        pro="your airline or travel agent", urgent="you might miss a connection or don't have the right documents: contact the airline straight away",
        prevent="check documents and rules a few weeks before, and leave buffer time",
        normal="Most of this is very common, and airlines and airports have help and facilities for exactly these situations.",
        diy="Almost all of this is planning you can do yourself; the airline can help with seats, bassinets and missed connections."),
}

ASPECTS = [
    ('urgent', r"\b(?:emergency|dangerous|safe|is it bad|harm|harmful|serious)\b"),
    ('pro', r"\b(?:take (?:him|her|it|them) to (?:a|the) (?:vet|doctor)|see a (?:doctor|gp|vet)|call (?:a|someone)|get someone in|plumber|electrician|"
            r"professional|worth getting someone|when should i (?:take|see|call))\b"),
    ('diy', r"\b(?:fix it myself|fix (?:it|this|that) myself|do it myself|myself|ourselves|diy|can i fix)\b"),
    ('worry', r"\b(?:worry|worried|normal|common|anything to worry|bad sign|concern)\b"),
    ('cause', r"^\s*(?:and |so |but )?why\b|\bwhat (?:causes|could be causing|could it be|else could it be|is causing)\b|\bhow come\b|\bcould it be\b"),
    ('tools', r"\bwhat (?:will|do|would|should) (?:i|we) need\b|\btools?\b|\bwhat (?:to|should i) buy\b"),
    ('prevent', r"\bagain\b|\bprevent|\bstop (?:it|that|this) (?:happening|from)\b|\bin future\b|\bavoid\b"),
    ('first', r"\bfirst\b|\beasiest\b|\bsimplest\b|\bwhere (?:do|should) i start\b"),
    ('replace', r"\breplace\b|\bnew one\b|\bbuy a new\b|\bworth (?:fixing|repairing)\b"),
    ('should', r"^\s*(?:and |so )?(?:should|shall) (?:i|we)\b|\bis it (?:ok|okay|worth)\b"),
    ('whatif', r"\bwhat if\b|\bregret"),
    ('fix', r"\bhow (?:do|can|should) (?:i|we)\b|\bwhat (?:can|should) (?:i|we) do\b|\bany (?:ideas|tips|advice)\b|\bhelp\b|\bfix\b|\bget rid\b|\bstop\b|\bsort\b"),
]


LEAD = {'person': "A good way to raise it with {your}:", 'child': "What usually helps with {your}:", 'pet': "What usually helps with {your}:",
        'money': "A sensible way to handle it:", 'travel': "What makes it easier:", 'body': "Simple care that usually helps:",
        'food': "What usually fixes it:", 'plant': "What usually helps {your}:"}
MONEY_Q = re.compile(r"(?i)\b(?:negotiate|price|pay|paid|afford|cost|costs|notice|increase|rise|discount|appeal|fee|charge|cheaper|refund)\b")


HINTS = [(r"\b(?:doctor|gp|physio\w*|pharmacist|painkillers?|stretch\w*|hurts?|ache\w*|sore)\b", 'body', 2),
         (r"\b(?:vet|vets)\b", 'pet', 2), (r"\b(?:plumber)\b", 'plumbing', 2), (r"\b(?:engineer|repair|technician)\b", 'appliance', 1),
         (r"\b(?:negotiate|notice|price|cost|pay|paid|afford|fee|discount|appeal|refund|cheaper|put (?:the rent|it) up)\b", 'money', 4.5),
         (r"\b(?:dehumidifier|damp|mould|mold|condensation|ventilat\w*)\b", 'house', 4.5),
         (r"\b(?:teacher|school|homework)\b", 'child', 1), (r"\b(?:airport|flight|layover|luggage)\b", 'travel', 2)]


def lex(word):
    w = word.lower().replace('-', ' ')
    for cand in (w, w[:-1] if w.endswith('s') else None, w[:-2] if w.endswith('es') else None, w[:-3] + 'y' if w.endswith('ies') else None):
        if cand and cand in WORDS:
            return WORDS[cand]
    return None


def best_class(thing_words, turns):
    """The class of the conversation by vote: the thing's own word counts most, then the last question's words, then the
    earlier turns, plus hints in the question ("doctor" -> body, "vet" -> pet). A rent rise asked about with "negotiate"
    is money; a stiff neck asked about with "doctor" is the body, whatever else was mentioned."""
    votes = {}
    thing_lex = next((lex(' '.join(thing_words[i:])) for i in range(len(thing_words)) if lex(' '.join(thing_words[i:]))), None) if thing_words else None
    thing_cls = thing_lex or (class_of(thing_words, '') if thing_words else None)
    if thing_cls:
        votes[thing_cls] = votes.get(thing_cls, 0) + (3 if thing_lex else 1)     # a WordNet guess ("machine" as a person) counts little
    for i, t in enumerate(turns[-4:]):
        k = 2 if t is turns[-1] else 1
        toks = re.findall(r"[a-z][a-z'-]+", t.lower())
        used = set()
        for j in range(len(toks) - 1):
            c = lex(toks[j] + ' ' + toks[j + 1])          # "washing machine", "smoke alarm"
            if c:
                votes[c] = votes.get(c, 0) + 2 * k
                used |= {j, j + 1}
        for j, w in enumerate(toks):
            c = lex(w) if j not in used else None
            if c:
                votes[c] = votes.get(c, 0) + k
        if re.search(r"\b\w+[- ](?:year|month)[- ]old\b", t.lower()):
            votes['child'] = votes.get('child', 0) + 2 * k
    for pat, c, k in HINTS:
        if re.search(pat, turns[-1].lower()):
            votes[c] = votes.get(c, 0) + k
    # a symptom told earlier keeps the conversation about the body: "Could it be my screen?" after "I've been getting
    # headaches every afternoon" asks about the headaches, not about fixing the screen
    if any(re.search(r"(?i)\b(?:headaches?|migraines?|aches?|aching|pains?|sore|hurts?|dizz\w*|nause\w*|tired(?:ness)?|eye ?strain|"
                     r"stiff(?:ness)?|cramps?|swollen|rash|cough\w*|fever)\b", t) for t in turns[-6:]):
        votes['body'] = votes.get('body', 0) + 6
    if not votes:
        return class_of(thing_words, ' '.join(turns[-4:]))
    return max(votes.items(), key=lambda x: x[1])[0]


def class_of(thing_words, text=''):
    """The class of the thing talked about: word list first ("tap" -> plumbing), then WordNet (any sense)."""
    words = [w.lower() for w in thing_words if w]
    for n in (2, 1):
        for i in range(len(words) - n + 1):
            key = ' '.join(words[i:i + n])
            if lex(key):
                return lex(key)
    low = text.lower()
    for phrase, cls in sorted(WORDS.items(), key=lambda x: -len(x[0])):
        if ' ' in phrase and phrase in low:
            return cls
    try:
        from .recall_agent import is_a
        # people first: a plumber, roofer or teacher is a person (WordNet also reaches "animal" from people through
        # organism senses, which made a plumber who won't come back a pet problem)
        order = ['child', 'person'] + [c for c in WN if c not in ('child', 'person')]
        for w in words[::-1]:
            for cls in order:
                if any(is_a(w, u) for u in WN[cls]):
                    return cls
    except Exception:
        pass
    if re.search(r"\b\w+[- ](?:year|month)[- ]old\b", low):
        return 'child'
    for w in re.findall(r"[a-z][a-z'-]+", low):
        if w in WORDS or w.replace('-', ' ') in WORDS:
            return WORDS.get(w) or WORDS[w.replace('-', ' ')]
    return None


def aspect_of(question):
    q = question.lower()
    for name, pat in ASPECTS:
        if re.search(pat, q):
            return name
    return 'fix'


def slots(cls, told):
    """The class's slots, with those of the first sub-schema whose pattern matches what was told."""
    from .advice_subschemas import SUB
    s = dict(S[cls])
    for c, pat, sub in SUB:
        if c == cls and re.search('(?i)' + pat, told):
            s.update(sub)
            s['_sub'] = pat[:40]
            break
    return s


QUESTION = {}


def compose(cls, aspect, thing, told=''):
    s = slots(cls, told)
    the = f'the {thing}' if thing else 'it'
    The = the[:1].upper() + the[1:]
    steps = '\n'.join(f'{i}. {x}' for i, x in enumerate(s['fix'], 1))
    your = f'your {thing}' if thing else 'it'
    if aspect == 'cause':
        return f"With {your}, the usual causes are {s['causes']}. A good first step is to {s['first']}; that usually narrows it down quickly."
    if aspect == 'first':
        return f"The easiest thing to try first: {s['first']}. If that doesn't sort it:\n\n{steps}"
    if aspect == 'diy':
        return f"{s['diy']} Start by trying to {s['first']}."
    if aspect == 'pro':
        return f"It's worth getting {s['pro']} involved if it isn't improving, or straight away if {s['urgent']}. Otherwise, start by trying to {s['first']}."
    if aspect == 'worry':
        return f"{s['normal']} Get help promptly if {s['urgent']}."
    if aspect == 'urgent':
        return f"Treat it as urgent if {s['urgent']}. Otherwise it's usually manageable: {s['first']}."
    if aspect == 'tools':
        return f"For {your} you'll usually need {s['tools']}."
    if aspect == 'prevent':
        return f"To stop it happening again: {s['prevent']}."
    if aspect in ('should', 'whatif'):
        return follow_up(cls, thing, told.split('  ')[-1] if False else (QUESTION.get('q') or ''), told, '') or f"{s['normal']} If you're unsure, {s['pro']} can advise."
    if aspect == 'replace':
        return (f"It's usually worth fixing first if the cause is a cheap part or a clean-up ({s['causes']}). Replacing makes more sense if it's old, "
                f"the repair costs more than half the price of a new one, or it keeps coming back.")
    lead = LEAD.get(cls, "A sensible way to sort out {your}:").format(your=your)
    return f"{lead}\n\n{steps}\n\nGet {s['pro']} if it doesn't improve, or straight away if {s['urgent']}."


def follow_up(cls, thing, question, told, said):
    """A follow-up after the steps were already given: the step that speaks to the question (said again if it was the
    answer), with what is normal or when to get help, instead of the same list again."""
    s = slots(cls, told)
    q = {w for w in re.findall(r"[a-z]{4,}", question.lower())} - {'should', 'could', 'would', 'what', 'when', 'they', 'them', 'that', 'this', 'with', 'about',
                                                                    'there', 'will', 'does', 'help', 'have', 'from', 'your', 'need'}
    scored = []
    for step in s['fix'] + [s['normal'], s['diy'], s['prevent'], s['first']]:
        words = set(re.findall(r"[a-z]{4,}", step.lower()))
        n = len({w for w in q if any(x.startswith(w[:5]) for x in words)})
        if n:
            scored.append((n, step[:50] not in said, step))
    scored.sort(key=lambda x: (-x[0], not x[1]))
    best = scored[0][2] if scored else None
    best = (best[:1].upper() + best[1:]) if best else None
    again = bool(scored) and not scored[0][1]
    if best and not best.endswith('.'):
        best += '.'
    if re.match(r"(?i)\s*(?:and |so )?(?:should|shall|is it (?:ok|okay|worth)|do (?:i|we) need to)\b", question):
        return (s['normal'] + (' ' + best if best and best[:50] not in s['normal'] else '') + f" If you're unsure, {s['pro']} can advise.").strip()
    if re.search(r"(?i)\bwhat if\b|\bregret|\bworr", question):
        return f"{s['normal']} Either way, it isn't a final decision: things can be revisited later, and keeping the door open matters more than getting it perfect now."
    if re.search(r"(?i)\bwhen will\b|\bhow long\b|\bgrow out\b", question):
        return f"{s['normal']} If it hasn't eased after a few weeks of steady routine, or it changes suddenly, {s['pro']} can help."
    if best:
        return ('As I mentioned: ' + best[:1].lower() + best[1:]) if again else best
    return f"{s['normal']} The steps above are the place to start; if they don't help, {s['pro']} can advise."


def respond(messages, thing=None):
    """An answer from the class of the thing the chat is about, for the kind of question asked; None if the class is unknown."""
    turns = [m['content'] for m in messages if m.get('role') == 'user']
    if not turns:
        return None
    last = turns[-1]
    if re.search(r"(?i)\b(?:write|draft|compose|poem|story|note|message|letter|card|email|text|rhyme|funnier|warmer|shorter|longer|more formal|friendlier)\b", last) \
            or re.search(r"(?i)^\s*(?:who|when|where|which|what year|how many|how much)\b", last) and not re.search(r"(?i)\b(?:i|we|my|our|it|she|he|they)\b", last) \
            or re.search(r"\d", last) and re.search(r"(?i)\bhow (?:much|many|long)\b|\bwhat time\b|\bcheaper\b", last):
        return None                         # writing, a fact or a sum: other agents do those
    # 0.4.4: a question that asks for one value (which one, what time or date or order, how many, who, is X on)
    # with no trouble or request for help told anywhere is not advice: "Reading left to right, what's the lineup?" about
    # jars got baking tips, "What's the least we can spend?" on plant pots got watering tips.
    q = re.split(r",\s*", (re.findall(r"[^.!?]*\?", last) or [last])[-1])[-1]       # "Reading left to right, what's the lineup?"
    if re.search(r"(?i)^\s*(?:and\s+|so\s+)?(?:which|who|whose|where|how many|how much|what(?:'s| is| are| was| were)? (?:the )?(?:time|day|date|order|"
                 r"line-?up|number|name|colou?r|age|total|weekday|month|year|room|exact)|what (?:day|time|date|number|name|month|year|age)|is [a-z]+ (?:on|off|lit|open|closed)|"
                 r"could (?:it|he|she|this|that)|does (?:that|this)(?: alone)? (?:prove|mean)|can we (?:work out|tell))\b", q.strip()) \
            and not re.search(r"(?i)\b(?:help|fix|stop|keeps?|won'?t|doesn'?t work|broken|problem|advice|tips?|should i|how (?:do|can|should) i|what should|"
                              r"best way|recommend|struggl|worried|annoy|upset)\b", ' '.join(turns[-4:])):
        return None
    if not thing:
        try:
            from .team import thing_of
            thing = thing_of(turns[0]) or thing_of(' '.join(turns[-4:])) or ''
        except Exception:
            thing = ''
    words = (thing or '').split()
    if words and words[-1] in ('wants', 'keeps', 'has', 'is', 'says', 'said'):
        words = words[:-1]
        thing = ' '.join(words)
    cls = best_class(words, turns)
    if thing and lex(thing.split()[-1]) not in (cls, None) and not (len(thing.split()) > 1 and lex(thing) == cls):
        thing = ''                          # "machine" read as a person: name the thing of the chosen class instead
    if not thing:
        toks = re.findall(r"[a-z][a-z'-]+", ' '.join(turns[-4:]).lower())
        pairs = [toks[j] + ' ' + toks[j + 1] for j in range(len(toks) - 1)]
        thing = next((x for x in pairs if lex(x) == cls), None) or next((x for x in toks if lex(x) == cls and len(x) > 2), '')
        if thing and thing.endswith('s') and lex(thing[:-1]) == cls:
            thing = thing[:-1]
    if not thing:
        m = re.search(r"(?i)\b(?:our|my|the)\s+((?:\w+-)+old|baby|toddler|son|daughter|cat|dog|tap|car)\b", ' '.join(turns[-4:]))
        thing = m[1].lower() if m else ''
        if thing.endswith('-old'):
            thing = 'child'
    if not cls:
        return None
    aspect = aspect_of(last)
    QUESTION['q'] = last
    told = ' '.join(([turns[0]] if len(turns) > 4 else []) + turns[-4:])     # the first told sentence stays part of the scene
    text = compose(cls, aspect, thing, told)
    said = ' '.join(str(m.get('content') or '') for m in messages[:-1] if m.get('role') == 'assistant')
    if text[:80] in said or (aspect in ('fix', 'first') and re.search(r'(?m)^1\. ', text) and text.split('\n1. ', 1)[-1][:60] in said):
        text = follow_up(cls, thing, last, told, said)
        if not text:
            return None
    specific = '_sub' in slots(cls, told)
    return dict(route='chat/advice-schema', response=text, sources=[], specific=specific,
                details=f'General advice for the class "{cls}", aspect "{aspect}", about "{thing or "it"}"'
                        f'{" (a sub-schema for this problem)" if specific else ""} (advice_schemas.py).')
