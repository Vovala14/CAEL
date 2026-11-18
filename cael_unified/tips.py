"""Ranked practical tips, authored (no model): 'I want to save money on groceries. Any tips?', then 'Which of those helps the
most?', 'Tell me more about the second one', 'Any others?'.

Each kind is (pattern, tips ranked by how much they usually help, why the first helps most, more tips). Being ranked, the list
can answer 'which helps most' and 'where do I start' from what was just said, instead of a search quoting one forum post.
"""
import re

# name: (pattern, [(tip, more detail)], why the first matters most, [more tips])
K = {
    'groceries': (r'\b(?:groceries|grocery|food shop(?:ping)?|supermarket|food bills?|food budget|spend(?:ing)? (?:less )?on food)\b', [
        ("Plan the week's meals and shop with a list.",
         "Check what's already in the fridge and cupboards, plan five or six dinners around it, and write a list by aisle. Stick to it in the shop; unplanned buys are where most of the money goes."),
        ("Waste less: use up leftovers and check what you have before you buy.",
         "A typical household throws away a big share of the food it buys. Cook with what's going off first, freeze bread, meat and leftovers before they spoil, and use 'first in, first out' in the fridge."),
        ("Switch to the shop's own brands.",
         "Supermarket own-label or value ranges are often made to similar standards and cost much less. Try them for staples like pasta, rice, tinned tomatoes, cereal and cleaning products."),
        ("Cook from basic ingredients and batch-cook.",
         "Ready meals and pre-cut produce carry a big mark-up. Cook a double batch of a stew, chilli or curry and freeze portions for busy nights."),
        ("Compare unit prices, not pack prices.",
         "The shelf label usually shows the price per kilo or per 100 g. Bigger packs and multibuys aren't always cheaper, and only help if you'll use it all."),
        ("Shop less often, and not when you're hungry.",
         "Every trip adds impulse buys. One planned weekly shop, after a meal, keeps the basket smaller.")],
     "Planning meals and shopping with a list usually saves the most, because it tackles the two biggest leaks at once: impulse buys in the shop and food you buy but never eat. Most people find it also makes the other tips (using leftovers, buying own brands) easier.",
     ["Try a cheaper supermarket or discounter for your staples.", "Buy fruit and vegetables loose and in season.",
      "Use a loyalty card or app only for things you'd buy anyway.", "Swap some meat meals for beans, lentils or eggs.",
      "Look at the reduced shelf late in the day, and freeze what you get."]),
    'energy': (r'\b(?:energy|electricity|gas|heating|power) (?:bills?|costs?|use|usage)\b|\bsave (?:on )?(?:energy|electricity|heating)\b|\buse less (?:energy|electricity|gas)\b', [
        ("Turn the heating thermostat down by one degree and heat only the rooms you use.",
         "Heating is usually the biggest part of a home energy bill, so even one degree lower makes a noticeable difference. Use timers so it's off when nobody's home, and close doors and radiator valves in empty rooms."),
        ("Stop draughts and add insulation.",
         "Draught-excluders for doors, sealing strips for windows and letterboxes, thick curtains at night, and loft insulation keep paid-for heat in. They're cheap compared with what they save."),
        ("Check your tariff and switch if there's a better deal.",
         "Compare your tariff once a year; a better fixed deal or the right off-peak tariff can save more than any habit change."),
        ("Wash clothes at 30 °C and skip the tumble dryer.",
         "Most of a washing machine's energy goes on heating water. Full loads at 30 °C clean well, and air-drying clothes saves a lot if you'd otherwise use a dryer."),
        ("Switch to LED bulbs and turn off things on standby.",
         "LEDs use far less electricity than old bulbs. TVs, consoles and chargers left on standby add up; a switched extension lead makes it easy."),
        ("Boil only the water you need and use a lid on pans.",
         "Small habits in the kitchen add up over a year: fill the kettle for what you need, use the microwave or a slow cooker for small meals.")],
     "Heating usually costs the most in a home, so turning the thermostat down a little and heating only the rooms you use tends to save the most. If your home is draughty, stopping the draughts comes a close second.",
     ["Bleed radiators so they heat properly.", "Fit a water-saving shower head; hot water is a big energy use.",
      "Defrost the freezer and keep the fridge at about 3-5 °C.", "Use a smart or programmable thermostat."]),
    'fuel': (r'\b(?:petrol|fuel|diesel|gas mileage|fuel economy|mpg)\b.{0,25}\b(?:save|cheaper|less|costs?|money|better|use)\b|\bsave (?:money )?on (?:petrol|fuel|diesel)\b', [
        ("Drive smoothly: accelerate gently and look ahead so you brake less.",
         "Harsh acceleration and braking can use a lot more fuel. Keep a steady speed and ease off early when you see a red light or a queue."),
        ("Slow down a little on fast roads.",
         "Fuel use rises steeply above about 50-60 mph (80-95 km/h); driving at 70 instead of 80 saves a noticeable amount."),
        ("Keep the tyres at the right pressure.",
         "Under-inflated tyres increase rolling resistance. Check them monthly against the figure in the door frame or handbook."),
        ("Take extra weight and roof boxes off.",
         "A roof box or rack adds drag even when empty, and heavy things in the boot cost fuel on every trip."),
        ("Combine short trips, or walk or cycle them.",
         "A cold engine uses much more fuel, so several short trips cost more than one longer one.")],
     "Driving smoothly usually makes the biggest difference, because it changes every mile you drive: gentle acceleration, looking ahead and braking less can cut fuel use noticeably without any cost.",
     ["Use air conditioning sparingly at low speed.", "Compare fuel prices with a free app before you fill up.",
      "Keep the car serviced; a clean air filter and the right oil help."]),
    'phone_bill': (r'\b(?:phone|mobile|broadband|internet) (?:bills?|contract|plan|costs?)\b', [
        ("Switch to a SIM-only deal when your contract ends.",
         "Once the phone is paid off, staying on the same contract often means paying for a handset you already own. A SIM-only plan with the data you actually use is usually much cheaper."),
        ("Check how much data you use and pick a plan to match.",
         "Your phone's settings show monthly data use. Many people pay for far more than they need."),
        ("Ring your provider and ask for a better deal before renewing.",
         "Tell them what competitors offer; the retention team can often match it."),
        ("Look at smaller networks that run on the big ones.",
         "They use the same masts and are often cheaper.")],
     "Moving to a SIM-only deal once your contract is up usually saves the most, because you stop paying for a phone you've already paid off.",
     ["Use Wi-Fi calling and messaging apps at home.", "Bundle or drop extras like insurance you don't need."]),
    'eat_healthier': (r'\beat(?:ing)? (?:more )?(?:healthi(?:er|ly)|better|well)\b|\bhealthier (?:diet|eating|food)\b', [
        ("Eat more vegetables, fruit and pulses, aiming for half your plate.",
         "Adding is easier than cutting: put an extra vegetable into dinners, keep fruit on hand, and add beans or lentils to soups and sauces."),
        ("Cut back on sugary drinks.",
         "Fizzy drinks, juices and sweetened coffees add a lot of sugar without filling you up. Water, sparkling water or tea are easy swaps."),
        ("Cook more at home.",
         "You control the salt, sugar and fat, and portions are usually smaller than takeaways."),
        ("Choose wholegrain bread, rice and pasta.",
         "They keep you full for longer and have more fibre."),
        ("Plan snacks: nuts, yoghurt, fruit.",
         "Having something ready stops you grabbing crisps or biscuits when you're hungry.")],
     "Eating more vegetables, fruit and pulses usually helps the most, because it improves the diet without having to give anything up, and it naturally leaves less room for the less healthy food.",
     ["Read labels for salt and sugar.", "Eat slowly and stop when you're comfortably full.", "Drink water through the day."]),
    'screen_time': (r'\b(?:screen time|on my phone (?:too much|less)|phone addiction|use my phone less|scroll(?:ing)? less|less time on (?:my )?(?:phone|screens?))\b', [
        ("Turn off non-essential notifications.",
         "Each buzz pulls you back in. Keep only calls and messages from people; switch off app, news and social media alerts."),
        ("Keep the phone out of the bedroom.",
         "Charge it in another room and use a cheap alarm clock; the first and last hour of the day are when scrolling eats the most time."),
        ("Set app time limits.",
         "Phones have built-in screen-time tools that lock an app after a daily limit."),
        ("Move tempting apps off the home screen, or log out.",
         "A little friction is enough to break the automatic habit."),
        ("Replace it with something: a book, a walk, a hobby.",
         "It's easier to do something else than to just not use the phone.")],
     "Turning off notifications usually helps the most, because most phone time starts with a buzz you didn't ask for. With fewer interruptions, you pick the phone up when you decide to.",
     ["Use greyscale mode; the phone becomes less attractive.", "Have phone-free meals.", "Check your weekly screen-time report."]),
    'cool_home': (r'\bkeep(?:ing)? (?:my |the |our )?(?:house|home|flat|apartment|bedroom|room) cool\b|\bcool (?:down )?(?:my |the |our )?(?:house|home|flat|room) (?:in|during|without)\b', [
        ("Keep the sun out: close curtains and blinds on sunny windows during the day.",
         "Most heat comes in as sunlight through glass. Pale or reflective blinds and curtains on the sunny side keep rooms much cooler."),
        ("Ventilate at night, close up by day.",
         "Open windows when it's cooler outside (night and early morning) to let cool air through, then shut them when the outside gets hotter than inside."),
        ("Use fans well.",
         "A fan in front of an open window at night pulls in cool air; in the day it cools you, not the room."),
        ("Turn off heat sources.",
         "Ovens, tumble dryers and old bulbs add heat; cook outside, use the microwave, or eat cold meals on hot days.")],
     "Keeping the sun out during the day usually helps the most: most of the heat comes in as sunlight through windows, and once it's in, it's hard to get out.",
     ["Sleep with a cotton sheet and a cool damp cloth.", "Plants and shade outside sunny windows help over time."]),
    'study': (r'\b(?:study|studying|revis(?:e|ing|ion)|learn(?:ing)?) (?:better|more effectively|for (?:an? |my )?(?:exams?|tests?))\b|\bexam (?:tips|revision|prep)\b', [
        ("Test yourself instead of re-reading.",
         "Close the book and try to recall or write down what you know, then check. Flashcards and past papers do this; it's the most reliable way to remember."),
        ("Spread revision out over days and weeks.",
         "Short sessions on a topic spaced over several days stick far better than one long session the night before."),
        ("Mix topics in a session.",
         "Switching between different kinds of problems helps you learn which method to use when."),
        ("Explain it in your own words.",
         "Teaching it to someone, or out loud to yourself, shows the gaps."),
        ("Sleep properly, especially before the exam.",
         "Memories are consolidated during sleep; an all-nighter usually costs more than it gains.")],
     "Testing yourself usually helps the most: trying to recall something, then checking, strengthens memory much more than reading the same notes again, and it shows you what you don't know yet.",
     ["Use past papers under timed conditions.", "Put your phone in another room while you work.", "Plan a timetable working back from the exam date."]),
    'save_water': (r'\bsav(?:e|ing) water\b|\buse less water\b|\bwater (?:bills?) (?:lower|cheaper|less)\b', [
        ("Take shorter showers.",
         "A shower uses several litres a minute; cutting a couple of minutes saves a lot, and saves on heating the water too."),
        ("Fix dripping taps and leaking toilets.",
         "A dripping tap or a toilet that keeps running wastes a surprising amount every day."),
        ("Run the washing machine and dishwasher only when full.",
         "A full load uses about the same water as a half one."),
        ("Turn the tap off while brushing your teeth.",
         "A running tap uses several litres a minute.")],
     "Shorter showers usually save the most for a household, because showers are one of the biggest daily water uses, and less hot water also cuts the energy bill.",
     ["Use a watering can rather than a hose in the garden.", "Collect rainwater for plants.", "Fit a dual-flush or a cistern bag."]),
}

ASK = re.compile(r"(?i)\b(?:tips?|advice|ideas?|suggestions?|ways? to|how (?:can|do|could|should) (?:i|we)|help me|what (?:can|should) (?:i|we) do|any (?:good )?(?:ideas|tips))\b")
MOST = re.compile(r"(?i)\b(?:which|what)(?: one)?(?: of (?:those|these|them|the tips))?\b.{0,25}\b(?:help|work|save|matter|make)s?\b.{0,20}\b(?:most|biggest|best)\b|"
                  r"\b(?:the )?(?:most (?:important|effective|helpful|useful)|biggest difference|best one|single best)\b|\bwhere (?:should|do) (?:i|we) start\b|"
                  r"\bif i (?:only|could only) do one\b|\bwhich (?:one|is best|first)\b")
MORE = re.compile(r"(?i)\b(?:any (?:more|others?|other (?:tips|ideas|ways))|anything else|more tips|other tips|what else)\b")
ORD = {'first': 0, '1st': 0, 'second': 1, '2nd': 1, 'third': 2, '3rd': 2, 'fourth': 3, '4th': 3, 'fifth': 4, '5th': 4, 'sixth': 5, 'last': -1}
PICK = re.compile(r"(?i)\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|last)\b(?: one| tip| idea)?")
LEAD = 'Roughly in order of how much they usually help:'


def find(text):
    for name, row in K.items():
        if re.search('(?i)' + row[0], text):
            return name
    return None


def answered(said):
    """The kind of the ranked list CAEL just gave, from its opening tip."""
    if not said.startswith(LEAD):
        return None
    return next((n for n, row in K.items() if row[1][0][0] in said), None)


def out(text, name, kind):
    return dict(route=f'chat/tips{"-" + kind if kind else ""}', response=text, sources=[], details=f'Authored ranked tips ({name}; tips.py).')


def respond(messages):
    text = (messages[-1].get('content') or '').strip()
    if not text or len(text) > 240:
        return None
    name = find(text)
    if name and ASK.search(text) and not re.search(r'(?i)\b(?:broken|won\'?t|stopped|leak\w*|error)\b', text):
        tips = K[name][1]
        body = '\n'.join(f'{i}. **{t}** {d}' for i, (t, d) in enumerate(tips, 1))
        return out(f'{LEAD}\n\n{body}\n\nIf you only do one, start with the first.', name, '')
    if len(text.split()) > 16:
        return None
    said = [m.get('content') or '' for m in messages[:-1] if m.get('role') == 'assistant'][-3:]
    prev = next((answered(x) for x in reversed(said) if answered(x)), None)   # the list, also after a follow-up about it
    if not prev:
        return None
    tips = K[prev][1]
    if MOST.search(text):
        return out(f'**{tips[0][0]}** {K[prev][2]}', prev, 'followup')
    if MORE.search(text):
        return out('A few more:\n\n' + '\n'.join(f'- {t}' for t in K[prev][3]), prev, 'followup')
    p = PICK.search(text)
    if p and re.search(r"(?i)\b(?:more|explain|how|tell me|about|what do you mean|why)\b", text):
        i = ORD[p[1].lower()]
        if -len(tips) <= i < len(tips):
            t, d = tips[i]
            return out(f'**{t}** {d}', prev, 'followup')
    return None
