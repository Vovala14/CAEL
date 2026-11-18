"""Follow-up knowledge: what a person who knows the subject says to the next question about an everyday problem.

Someone says "My car brakes squeak when I stop" and then asks "Is it the pads?", "How do I clean them?", "Do I need new
ones?". Those follow-ups name nothing, so a search on their words drifts (a bicycle thread for a car, houseplant feeding
for tomatoes). This table holds authored answers for common everyday problems, one per kind of follow-up: what causes it,
whether it is a given part, how to clean, test, feed or fix it, whether to replace it, whether to call someone, whether it
is safe, and how to stop it coming back. The thing is read from what the user first told; the kind of follow-up from the
last question. Authored text and patterns; no model.
"""
import re

ASKS = [
    # (kind, pattern over the last user turn), most specific first
    ('pro', re.compile(r"(?i)\b(?:do i need|should i (?:call|get)|is it worth (?:calling|getting))\b.*\b(?:plumber|mechanic|garage|electrician|engineer|"
                       r"vet|doctor|gp|professional|someone|an expert|a repair)\b|\bcall (?:a|someone|out)\b")),
    ('safe', re.compile(r"(?i)\bis (?:it|this|that) (?:safe|dangerous|ok to|okay to)\b|\bcan i still (?:eat|use|drive|ride|cook|wear)\b|\bsafe to\b")),
    ('replace', re.compile(r"(?i)\b(?:do i need (?:new|a new|to replace|replacing)|new ones|when should i replace|should i replace|replace (?:it|them)|"
                           r"time for (?:new|a new)|need replacing|worn out)\b")),
    ('clean', re.compile(r"(?i)\b(?:how (?:do|can|should) (?:i|you|we) clean|best way to clean|clean (?:it|them|the \w+)|what (?:do|should) i clean)\b")),
    ('test', re.compile(r"(?i)\bhow (?:can|do|would) (?:i|you) (?:test|check|tell|know)\b|\bis (?:it|my \w+|the \w+) (?:dead|still good|off|bad|ok|okay|alive|working)\b|"
                        r"\btest (?:it|them)\b")),
    ('feed_with', re.compile(r"(?i)\bwhat (?:should|do|can) (?:i|we) feed (?:it|them|my \w+(?: \w+)?) with\b|\bwhat (?:kind of |sort of )?(?:feed|fertili[sz]er|plant food)\b|"
                             r"\bwhich (?:feed|fertili[sz]er)\b")),
    ('feed', re.compile(r"(?i)\b(?:should i feed|what (?:should|do|can) i feed|feed (?:it|them)|fertili[sz]|plant food|tomato feed)\b")),
    ('water', re.compile(r"(?i)\b(?:too much|too little|not enough|over|under)[- ]?water|\bhow (?:often|much) (?:should|do) i water\b")),
    ('prevent', re.compile(r"(?i)\b(?:stop it (?:happening|coming back)|prevent|in (?:the )?future|next time|happening again|coming back)\b")),
    ('part', re.compile(r"(?i)^\s*(?:is|could|might|would) (?:it|that) (?:be )?(?:the|my|a|an) ([a-z]+(?: [a-z]+)?)\s*\?\s*$")),
    ('cause', re.compile(r"(?i)\b(?:what (?:causes|is causing|could cause|makes)|why (?:does|do|is|are|would)|what'?s causing|what could it be|what is it)\b")),
    ('fix', re.compile(r"(?i)\b(?:how (?:do|can|should) (?:i|we) (?:fix|stop|sort|get rid|unblock|cure|treat|deal)|what (?:can|should|do) (?:i|we) do|"
                       r"what if that doesn'?t work|anything else i can try|how do i make it)\b")),
]

KB = [
    dict(key='car brakes', thing=re.compile(r"(?i)\b(?:car|van)\b[^.?!]*\bbrakes?\b|\bbrakes?\b[^.?!]*\b(?:car|van)\b"),
         part={'pads': "Very often, yes. Squeaking when you stop usually comes from the brake pads: either a small metal wear indicator touching the "
                       "disc (it's designed to squeal when the pads are low), glazed or dusty pads, or new pads that haven't bedded in. Light squeaks "
                       "in the first few stops on a damp or cold morning are normal surface rust and go away. A constant squeal, or grinding, means "
                       "the pads should be checked soon.",
               'discs': "It can be. Worn, rusty or scored discs (rotors) squeak or grind, and you may feel a pulse through the pedal if they're warped. "
                        "A mechanic usually checks pads and discs together."},
         cause="The usual causes are the brake pads (worn down to the squeal indicator, glazed, or brand new and not bedded in), surface rust on the "
               "discs after rain or a night parked, dust or grit between pad and disc, or missing anti-squeal shims and grease behind the pads. "
               "A squeak only on the first few stops is usually harmless; a squeal every time, or grinding, means it's time for a check.",
         clean="Don't spray anything oily near them. If you want to try, spray brake cleaner (from a car parts shop) onto the disc and pad area "
               "through the wheel spokes, or with the wheel off, and let it dry; that clears dust that can cause squeaks. Never use WD-40, "
               "grease or household cleaners on the discs or pads: contaminated pads stop badly and have to be replaced. If you're not "
               "comfortable taking a wheel off, a garage will clean and check them quickly.",
         replace="Probably, if the squeal is constant. Most pads have a wear indicator that squeals when they're nearly worn out, and you can "
                 "often see the pad thickness through the wheel: under about 3 mm of pad material means replace them. Grinding means the pads "
                 "are down to metal, which damages the discs, so get them done straight away. Pads are always replaced in pairs (both front "
                 "or both rear).",
         pro="It's worth having a garage look at it, because brakes are safety-critical. A brake check is quick and often free or cheap. "
             "Go straight away if you hear grinding, the pedal feels soft or spongy, the car pulls to one side when braking, or a brake "
             "warning light is on.",
         safe="A light squeak, especially on cold or damp mornings, is usually safe to drive on, but get it checked soon. Don't keep driving if "
              "you hear grinding, the pedal feels soft, the car pulls to one side, or the brake light is on."),
    dict(key='bike brakes', thing=re.compile(r"(?i)\b(?:bike|bicycle|cycle)\b[^.?!]*\bbrakes?\b|\bbrakes?\b[^.?!]*\b(?:bike|bicycle)\b"),
         part={'pads': "Often, yes. Bike brakes squeal when the pads are contaminated (oil, chain lube, road grime), glazed, worn, or not lined up "
                       "with the rim or disc. On rim brakes, pads set slightly 'toed in' (the front edge touching the rim first) squeal much less. "
                       "On disc brakes, a little oil on the pads is the most common cause."},
         cause="Bike brakes usually squeal because of dirt or oil on the rims, discs or pads (chain lube spray is a common culprit), glazed or "
               "worn pads, or pads that aren't lined up properly. Wet weather makes almost all brakes noisy for a while.",
         clean="For rim brakes: wipe the rims with warm soapy water or rubbing alcohol on a clean cloth, and lightly sand the pad surface with "
               "fine sandpaper to remove the glaze and any grit. For disc brakes: wipe the disc with isopropyl alcohol on a clean cloth, never "
               "touch it with oily fingers, and keep lube spray well away. Disc pads that have soaked up oil often can't be saved and need replacing.",
         replace="Replace them when the grooves on the pads are worn away (rim brakes), or when the pad material is down to about 1 mm (disc "
                 "brakes), or if disc pads are contaminated with oil. Pads are cheap, and a bike shop can fit them in minutes."),
    dict(key='drain smell', thing=re.compile(r"(?i)\b(?:drain|sink|plughole|plug hole)\b[^.?!]*\b(?:smell|smells|smelly|stinks?|stinky|odou?r)\b|"
                                             r"\b(?:smell|stink|odou?r)\w*\b[^.?!]*\b(?:drain|sink|plughole)\b"),
         cause="Most smelly kitchen drains are caused by grease, food and soap building up in the pipe and the U-bend (the trap) under the sink, "
               "where bacteria grow. Less often the water seal in the trap has dried out or been siphoned away (by a dishwasher or washing "
               "machine draining), which lets sewer smells up from the pipes.",
         clean="Start simple: pour a kettle of very hot (not boiling, if you have plastic pipes) water down it. Then put about half a cup of "
               "bicarbonate of soda down the plughole, follow it with a cup of white vinegar, leave it for 15–20 minutes, and flush with more "
               "hot water. If it still smells, put a bucket underneath, unscrew the U-bend under the sink by hand, and clean out the gunk. "
               "Don't pour fat down the sink, and use a sink strainer for food.",
         fix="Clean the trap and pipe first (hot water, bicarbonate of soda and vinegar, then unscrew and clear the U-bend). Run the tap for a minute "
             "if it's a sink you rarely use, so the trap has water in it. If the smell comes back quickly or smells like sewage, the trap may be "
             "losing its water or a vent may be blocked, which is a job for a plumber.",
         pro="Not usually: cleaning the U-bend is an easy DIY job. Call a plumber if the smell is like sewage and keeps coming back after cleaning, "
             "several drains smell or gurgle at once, or water is backing up.",
         prevent="Wipe fat and food into the bin before washing up, use a strainer in the plughole, and once a week pour hot water (or the "
                 "bicarbonate of soda and vinegar mix) down the drain."),
    dict(key='slow drain', thing=re.compile(r"(?i)\b(?:sink|drain|bath|shower|basin|plughole)\b[^.?!]*\b(?:slow|slowly|blocked|clogged|backing up|won'?t drain|"
                                            r"not draining|isn'?t draining)\b"),
         cause="In a kitchen sink it's usually grease and food stuck in the U-bend or pipe; in a bathroom basin, bath or shower it's almost always "
               "hair tangled with soap scum just below the plughole.",
         fix="Pull out what you can from the plughole first (a bent wire or a cheap plastic drain snake works wonders for hair). Then use a plunger: "
             "fill a little water, cover the overflow hole with a wet cloth, and plunge firmly a dozen times. Hot water, then bicarbonate of soda "
             "and vinegar, helps with grease. If that fails, put a bucket underneath and unscrew the U-bend to clear it.",
         clean="Pour hot water down it, then half a cup of bicarbonate of soda and a cup of white vinegar; leave it 15–20 minutes and flush with "
               "hot water. For hair, a plastic drain snake from a hardware shop pulls it out far better than any chemical.",
         pro="Try a plunger and clearing the U-bend first. Call a plumber if several drains are slow at once, the toilet gurgles when the sink drains, "
             "or water is coming back up, because then the blockage is further down the pipe."),
    dict(key='bread', thing=re.compile(r"(?i)\b(?:bread|loaf|loaves|dough)\b[^.?!]*\b(?:flat|dense|heavy|didn'?t rise|doesn'?t rise|won'?t rise|not rising|"
                                       r"isn'?t rising|collapsed?|stodgy)\b"),
         test="Easy: stir a teaspoon of sugar into about 120 ml of lukewarm water (it should feel just warm on your wrist, not hot), sprinkle in "
              "the yeast, and leave it for 10 minutes. If it's alive it will turn foamy and bubbly and smell yeasty. If nothing happens, the "
              "yeast is dead and you need fresh. Yeast also dies if the water you use is too hot, so that's worth checking too.",
         cause="A flat or dense loaf usually means it didn't rise enough: old or dead yeast, water that was too hot (it kills yeast) or too cold, "
               "too little kneading, too much flour making a stiff dough, or not enough rising time. Over-proving can also make it collapse in the oven.",
         fix="Check the yeast is alive, use lukewarm water, knead until the dough is smooth and springy, and let it rise somewhere warm until it has "
             "roughly doubled. Shape it firmly, and bake when a gentle poke springs back slowly. Strong (bread) flour helps it rise higher than plain."),
    dict(key='tomato plants', thing=re.compile(r"(?i)\btomato(?:es| plants?)?\b"),
         feed="Yes, once the first flowers or small fruits appear. Tomatoes are hungry plants: give them a liquid tomato feed (high in potassium) "
              "once a week, at the strength on the bottle, watered onto damp soil. Before flowering, a balanced feed or rich compost is enough; "
              "too much nitrogen early on gives lots of leaves and little fruit.",
         feed_with="A liquid tomato feed from any garden centre is the easy choice: it's high in potassium (the K in N-P-K, the bigger last "
                   "number on the label), which helps flowers and fruit. Seaweed feed or home-made comfrey tea work too. Avoid lawn feed or "
                   "high-nitrogen fertiliser once it's flowering, and if the leaves yellow between the veins, a little Epsom salt (magnesium) "
                   "in the watering can helps.",
         water="It can be. Lower leaves turning yellow is often a watering problem: too much (soil that stays wet) or uneven watering. Tomatoes "
               "like deep, regular watering: soak the soil, let the top centimetre or two dry, then water again, usually every day or two in hot "
               "weather in pots and less in the ground. Water the soil, not the leaves.",
         cause="Yellow leaves at the bottom of a tomato plant are often normal ageing of the oldest leaves, but they can also mean uneven or too "
               "much watering, hunger (especially a lack of nitrogen or magnesium), or a fungal disease such as early blight if there are brown "
               "spots with rings. Pinch off yellow lower leaves and water at the base.",
         fix="Pinch off the yellow lower leaves, water deeply and regularly at the base (not on the leaves), and start a weekly tomato feed once it "
             "flowers. If the yellow leaves have brown ringed spots, remove them and bin them (not on the compost), as that's a fungus that spreads "
             "by splashing.",
         safe="Yes. Yellow or spotted leaves don't make the fruit unsafe; the tomatoes are fine to eat if they look and smell normal."),
    dict(key='tap', thing=re.compile(r"(?i)\b(?:tap|faucet)\b[^.?!]*\b(?:drip|dripping|leak|leaking|won'?t turn off|running)\b"),
         cause="A dripping tap is almost always a worn washer (in older taps with a rubber washer) or a worn ceramic cartridge (in quarter-turn and "
               "mixer taps). Limescale can also stop it sealing.",
         fix="Turn off the water to the tap (the isolating valve under the sink, or the main stopcock), open the tap to let it drain, then take off "
             "the handle and unscrew the headgear or cartridge. Replace the washer or cartridge with one of the same size (take the old one to a "
             "hardware shop), reassemble, and turn the water back on slowly.",
         pro="Most people can change a tap washer themselves in half an hour. Call a plumber if you can't turn the water off, the tap body itself is "
             "cracked, or it's leaking from underneath the sink."),
    dict(key='mould', thing=re.compile(r"(?i)\b(?:mould|mold|mouldy|moldy|black spots?)\b[^.?!]*\b(?:wall|walls|ceiling|bathroom|window|bedroom|corner|"
                                       r"sealant|silicone|grout)\b|\b(?:condensation|damp)\b"),
         cause="Most mould at home comes from condensation: warm, moist air from cooking, showers, drying clothes and breathing meets cold walls or "
               "windows. It's worst in corners, behind furniture and in bedrooms and bathrooms. A patch that keeps coming back in one place can "
               "also be a leak or rising damp.",
         clean="Wear gloves, and open a window. Wipe small patches with a mould spray or a cloth dipped in diluted bleach (or white vinegar on "
               "surfaces bleach would damage), then dry the area well. Don't brush it dry, which spreads spores. Mould in silicone sealant usually "
               "can't be cleaned out and the sealant needs replacing.",
         prevent="Open windows or use the extractor fan when cooking and showering (and for 15 minutes after), dry clothes outside or in a ventilated "
                 "room, keep furniture a few centimetres off outside walls, and heat rooms steadily rather than in short bursts. A dehumidifier helps a lot."),
    dict(key='squeaky door', thing=re.compile(r"(?i)\b(?:door|hinge|hinges|gate)\b[^.?!]*\b(?:squeak|squeaks|squeaky|creak|creaks|creaky)\b"),
         fix="Lift the hinge pin out (tap it up from below with a screwdriver and hammer while the door is closed), wipe it, coat it with a little "
             "grease, light oil or even petroleum jelly, and tap it back in. Or just drip oil onto the top of the hinge and swing the door back and "
             "forth. Silicone spray works too and attracts less dust.",
         cause="Squeaks come from metal rubbing on metal in a dry, dirty or slightly rusty hinge. A door that sags or rubs on the frame usually has a "
               "loose hinge screw, which is worth tightening at the same time."),
    dict(key='car battery', thing=re.compile(r"(?i)\bcar\b[^.?!]*\b(?:won'?t start|wouldn'?t start|doesn'?t start|not starting|clicking|flat battery|dead battery)\b"),
         cause="If the car clicks or turns over slowly, it's most likely a flat or failing battery, especially in cold weather, after short journeys, "
               "or if the battery is more than four or five years old. If the engine turns over normally but won't fire, it's more likely fuel or ignition.",
         fix="Try a jump-start with jump leads and another car (red to the positive terminals, black to the other car's negative and to bare metal on "
             "yours), or a portable jump starter. Then drive for at least half an hour to recharge it. If it goes flat again within a few days, "
             "the battery or alternator needs checking.",
         replace="If it's more than about five years old, or it goes flat again after a jump-start and a long drive, it's probably time for a new one. "
                 "Many garages and parts shops test batteries for free."),
]


def kind_of(last):
    for kind, pat in ASKS:
        m = pat.search(last)
        if m:
            return kind, m
    return None, None


def entry_for(turns):
    """The table entry for what the user first told (the first two turns), or None."""
    told = ' '.join(turns[:2])
    for e in KB:
        if e['thing'].search(told):
            return e
    return None


def respond(messages):
    turns = [m['content'] for m in messages if m.get('role') == 'user' and isinstance(m.get('content'), str)]
    if len(turns) < 2:
        return None
    last = turns[-1].strip()
    if not last.endswith('?') or len(last.split()) > 18:
        return None
    e = entry_for(turns[:-1])
    if not e:
        return None
    kind, m = kind_of(last)
    text = None
    if kind == 'part':
        word = m[1].lower().split()[-1]
        parts = e.get('part') or {}
        text = parts.get(word) or parts.get(word.rstrip('s')) or parts.get(word + 's')
        if not text and e.get('cause'):
            text = f"It could be, but it's not the most common cause. {e['cause']}"
    elif kind:
        text = e.get(kind) or (e.get('feed') if kind == 'feed_with' else None)
        if not text and kind == 'prevent':
            text = e.get('fix')
        if not text and kind in ('fix', 'clean') and e.get('clean' if kind == 'fix' else 'fix'):
            text = e.get('clean' if kind == 'fix' else 'fix')
    if not text:
        return None
    said = ' '.join(str(x.get('content') or '') for x in messages[:-1] if x.get('role') == 'assistant')
    if text[:80] in said:
        # asked again in other words ("How can I test it?" after the test): point back to it briefly, never the same answer twice
        steps = re.split(r'(?<=[.!?])\s+', text)
        core = next((s for s in steps if len(s.split()) > 8), steps[0])
        return dict(route='chat/followup-kb', response=f"That's the one I described just now: {core[:1].lower() + core[1:]} "
                                                       f"Tell me what happens and I'll help with the next step.", sources=[],
                    details=f'Follow-up knowledge: "{kind}" about {e["key"]}, asked again (followup_kb.py).')
    return dict(route='chat/followup-kb', response=text, sources=[],
                details=f'Follow-up knowledge: "{kind}" about {e["key"]} (followup_kb.py).')
