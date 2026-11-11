"""Everyday knowledge, advice and jokes for conversation (2026-11 round 2). Non-neural.

Each entry has `need` (word stems that must all appear), `keys` (extra stems that raise the score),
an `answer`, and optional `follow` entries for second turns ([need stems], answer). Matching is on
word stems of the user's message, so paraphrases hit without exact phrasing. Content is authored,
general and cautious; health topics point to a professional for anything persistent.
"""
import re

STOP = set('a an the is are was were be been do does did to of in on at for and or but if so it its this that with my me i you your we our '
           'can could would should will just really very any some how why what when where who which there here about from into than then '
           'have has had get got not no yes please tell give make one more most also too like'.split())


def stems(text):
    out = set()
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in STOP:
            continue
        out.add(w)
        for suf in ('ing', 'ies', 'ed', 'es', 's', 'ly'):
            if len(w) > len(suf) + 2 and w.endswith(suf):
                w = w[:-len(suf)] + ('y' if suf == 'ies' else '')
                break
        out.add(w)
    return out


E = []


CHAT_OK = {'soup', 'guitar|fingertip|finger|string', 'muscle|sore|ache', 'lonely|alone|loneliness|friend', 'sleep|slept|insomnia|asleep',
           'stress|stressed|anxious|anxiety|overwhelm|worried|worry', 'motivat|procrastinat|lazy|unmotivated'}


def entry(need, keys, answer, follow=()):
    E.append(dict(need=[set(n.split('|')) for n in need.split()], keys=stems(keys), answer=answer, chat=need in CHAT_OK,
                  follow=[(f[0].split(), f[1]) for f in follow]))


# ---------------------------------------------------------------- advice & everyday life
entry('sleep|slept|insomnia|asleep', 'bad badly poor trouble suggest tip help gentle night tired awake restless week',
      'Sorry you have been sleeping badly. A few gentle things that often help:\n'
      '1. **Keep a steady rhythm**: get up at about the same time every day, even after a poor night. It anchors your body clock.\n'
      '2. **Wind down for 30–60 minutes**: dim lights, something calm like reading, stretching or a warm shower.\n'
      '3. **Screens and light**: phones and bright screens late at night can keep your brain alert; try putting the phone away a little earlier.\n'
      '4. **Caffeine and heavy meals**: avoid coffee after early afternoon and big meals close to bedtime.\n'
      '5. **If you cannot sleep**: after about 20 minutes, get up and do something quiet in dim light, then go back when sleepy.\n'
      'If it goes on for weeks or affects your days a lot, it is worth talking to a doctor.',
      follow=[('phone|screen|scroll|tablet|laptop|tv', 'Yes, it can matter. Phones affect sleep in two ways: the bright screen light signals "daytime" to your brain and can delay '
               'the release of melatonin, the sleep hormone, and scrolling keeps your mind busy and alert, which is often the bigger effect. Try leaving the phone '
               'out of reach for the last 30–60 minutes, or at least turning the brightness down and switching to something calmer like a book or audio. '
               'A cheap alarm clock helps if the phone is your alarm.'),
              ('coffee|caffeine|tea', 'Caffeine can stay in your system for many hours (its effect halves roughly every 5 hours), so an afternoon coffee can still affect sleep at night. '
               'Try having your last caffeine before about 2 pm for a week and see if it helps.'),
              ('nap|naps', 'Short naps (20 minutes or less, before mid-afternoon) are usually fine, but long or late naps can make it harder to fall asleep at night.')])
entry('stress|stressed|anxious|anxiety|overwhelm|worried|worry', 'feel lot work deal cope handle help tip calm',
      'That sounds hard. A few things that often help when stress builds up:\n'
      '1. **Slow breathing**: breathe in for about 4 seconds and out for about 6, for a couple of minutes; a longer out-breath calms the body.\n'
      '2. **Write it down**: list what is on your mind, then mark the one thing you can act on today. Getting it out of your head reduces the load.\n'
      '3. **Move a little**: even a 10-minute walk helps many people feel calmer.\n'
      '4. **Talk to someone** you trust about it.\n'
      'If the stress or anxiety is constant or affects your sleep and daily life for a long time, a doctor or counsellor can really help.')
entry('motivat|procrastinat|lazy|unmotivated', 'feel lack no study work start task get going help',
      'Low motivation is very common, and it usually follows action rather than coming first. Try making the first step tiny: two minutes, one sentence, one dish. '
      'Set a short timer and allow yourself to stop when it rings. Remove one obstacle in advance (open the document, put the shoes by the door), and notice '
      'small wins. If low motivation comes with feeling down for weeks, it is worth talking to someone about it.')
entry('stud|exam|revis|learn', 'tip how best way remember focus better effective test prepare',
      'Some of the most reliable study habits:\n'
      '1. **Test yourself** instead of rereading: close the book and try to recall or explain the idea.\n'
      '2. **Spread it out**: several short sessions over days beat one long cram.\n'
      '3. **Mix topics** a little, and do practice questions.\n'
      '4. **Short focused blocks** (around 25 minutes) with phone out of reach, then a short break.\n'
      '5. **Sleep**: memory consolidates during sleep, so a good night before an exam helps more than a late cram.')
entry('guitar|fingertip|finger|string', 'hurt sore pain learn normal start play month calluses',
      'Yes, sore fingertips are completely normal when you start guitar. Pressing steel strings puts a lot of pressure on a small patch of skin. '
      'Over the first few weeks your fingertips build up calluses (tougher skin), and most people find the pain fades noticeably within two to four weeks of regular practice. '
      'Practising little and often, say 15–20 minutes a day, works better than long sessions; press only as hard as needed for a clean note; and take a break if it is sharp pain. '
      'Lighter-gauge strings or a lower action (string height) can make it easier too.',
      follow=[('normal|better|go|away|stop|improve|last', 'Yes, it is normal, and it gets better. As calluses form over the first few weeks of regular playing, the soreness '
               'usually fades a lot. Little and often is the way through it; stop if you feel sharp pain or numbness.')])
entry('muscle|sore|ache', 'exercise workout gym run after day legs arms normal',
      'Muscle soreness a day or two after new or harder exercise is normal (often called DOMS). It comes from small strains in the muscle that the body repairs, '
      'leaving the muscle a bit stronger. Gentle movement, a warm shower and enough sleep help; it usually fades within a few days. Sharp pain, swelling or pain in a joint is different and worth checking.')
entry('lonely|alone|loneliness|friend', 'feel make new adult move city people',
      'Feeling lonely is more common than people admit, and it says nothing bad about you. Things that tend to help: small regular contact rather than one big step '
      '(a weekly class, club or volunteering where you see the same faces), saying yes to small invitations, and reaching out first to one person you already know. '
      'Friendships usually grow from repeated, low-pressure time together.')
entry('habit|routine', 'build new start keep stick daily form',
      'To build a habit: make it tiny at first (one push-up, one page), attach it to something you already do ("after I make coffee, I…"), make it easy to start '
      '(put things where you will see them), and track it so you can see a streak. Missing one day is fine; just avoid missing two in a row.')
entry('water|drink|hydrat', 'much how day enough litre glass',
      'A common guideline is around 1.5–2 litres of fluid a day for many adults, but it varies with body size, activity and heat. Thirst and pale-yellow urine are good everyday guides. '
      'Tea, coffee and food with water count too.')
entry('cook|recipe|dinner|meal', 'easy quick simple idea tonight beginner',
      'Some easy, forgiving dinners: a vegetable stir-fry with rice or noodles; pasta with garlic, olive oil and whatever greens you have; an omelette or frittata; '
      'a tray bake (chopped vegetables and chicken or chickpeas, olive oil and seasoning, about 35 minutes at 200 °C); or a simple soup from onions, a stock cube and leftover vegetables.')
entry('soup', 'cook made pot smell amazing finish',
      'A big pot of soup is one of the best things to have on a cold evening, and it usually tastes even better the next day. What kind did you make?')
entry('focus|concentrat|distract', 'work study can not keep tip help phone',
      'To focus better: put your phone in another room, decide on one specific task for the next 25 minutes, close extra tabs, and write down distracting thoughts on paper to deal with later. '
      'Short breaks between blocks help you keep going.')
entry('headache', 'often have why help',
      'Common everyday triggers for headaches are not drinking enough, poor sleep, skipped meals, stress, screen strain and caffeine changes. Water, rest and regular meals help many people. '
      'A sudden severe headache, or headaches with fever, confusion, weakness or after an injury, need urgent medical attention.')
entry('cold|flu', 'catch sick get better fast feel',
      'For an ordinary cold, rest, fluids and time are the main things; most colds clear up in about a week to ten days. Warm drinks and honey can soothe a sore throat. '
      'See a doctor if you have trouble breathing, a high fever that lasts, or you are getting worse instead of better.')
entry('plant|houseplant', 'die dying yellow leaves water often keep alive',
      'The most common reason houseplants struggle is too much water. Check the soil with a finger: water only when the top couple of centimetres are dry, and make sure the pot drains. '
      'Yellow lower leaves often mean overwatering; crispy brown edges often mean dry air or underwatering. Most plants also want bright, indirect light.')
entry('money|save|saving|budget', 'how tip more month spend',
      'A simple way to start saving: move a fixed amount to savings on payday, before you spend, so it happens automatically. Track your spending for a month to see where it goes, '
      'cut one or two things you do not value much, and keep a small emergency fund before anything else.')
entry('run|running|jog', 'start beginner how begin',
      'For starting to run: begin with run–walk intervals (for example 1 minute running, 2 minutes walking, repeated for 20 minutes), three times a week, and build up slowly. '
      'Go at a pace where you could still talk. Walking parts of a run is completely normal and how most people build up.')
entry('dog', 'bark train puppy walk',
      'Dogs learn best with short, frequent training sessions and rewards right after the behaviour you want. Plenty of exercise and things to sniff and chew also reduce problem behaviour.')
entry('cat', 'why purr knead scratch',
      'Cats purr when content, but also to soothe themselves; kneading is a leftover from kittenhood; scratching keeps claws healthy and marks territory, so a scratching post helps protect furniture.')

# ---------------------------------------------------------------- knowledge & explanations
entry('apple|avocado|banana', 'cut brown turn why go',
      'Cut apples turn brown because cutting breaks open the cells. An enzyme inside them (polyphenol oxidase) then meets oxygen from the air and turns natural compounds '
      'called polyphenols into brown pigments. It is a harmless reaction, a bit like rusting, and does not mean the apple has gone bad.',
      follow=[('lemon|juice|stop|prevent|slow|acid', 'Yes, lemon juice really does slow it down. Its acid makes conditions worse for the browning enzyme, and its vitamin C (ascorbic acid) '
               'reacts with oxygen first. It slows browning rather than stopping it forever. Other tricks: a quick soak in lightly salted water, or keeping slices covered and cold.')])
entry('weather climate', 'difference between what',
      'Weather is what the atmosphere is doing at a particular place and time: today\'s rain, temperature and wind. Climate is the average pattern of weather in a region over many years, '
      'usually 30 or more. A simple way to remember it: weather is your mood today, climate is your personality.',
      follow=[('example|instance|each', 'Weather example: "It is raining and 12 °C in London this afternoon." Climate example: "London has mild, wet winters and cool summers." '
               'One cold day is weather; a region warming by a degree over decades is a change in climate.')])
entry('virus bacteria|bacterium', 'difference between what',
      'Bacteria are tiny living single-celled organisms that can live on their own; many are harmless or helpful, some cause illness, and antibiotics can kill them. '
      'Viruses are much smaller and are not cells: they can only reproduce inside the cells of a host. Antibiotics do not work on viruses.')
entry('lightning thunder', 'see hear before why first',
      'Lightning and thunder happen at the same moment, but light travels about a million times faster than sound. You see the flash almost instantly, while the sound '
      'travels at about 343 metres per second, roughly a kilometre every three seconds.',
      follow=[('far|distance|away|close|tell|storm', 'Count the seconds between the flash and the thunder, then divide by 3 to get the distance in kilometres '
               '(or divide by 5 for miles). For example, a 9-second gap means the storm is about 3 km away. If the gap gets shorter, the storm is coming closer; '
               'under about 30 seconds, it is safest to go indoors.')])
entry('rainbow', 'how form why appear',
      'A rainbow forms when sunlight enters raindrops, bends, reflects off the back of the drop and bends again on the way out. Each colour bends by a slightly different amount, '
      'so white light spreads into its colours. You see one when the Sun is behind you and rain is in front of you.')
entry('earthquake', 'cause why happen',
      'Earthquakes happen because Earth\'s outer shell is broken into huge plates that slowly move. Where plates press or slide past each other, stress builds up in the rock; '
      'when it suddenly slips, the released energy shakes the ground.')
entry('volcano', 'erupt why how',
      'A volcano erupts when molten rock (magma) from deep underground, full of dissolved gases, rises and the pressure becomes too great for the rock above. '
      'The gas expanding near the surface drives the eruption, a bit like opening a shaken fizzy drink.')
entry('dinosaur', 'extinct die why',
      'Most dinosaurs died out about 66 million years ago, very likely after a huge asteroid struck near what is now Mexico. The impact threw dust and gases into the sky, '
      'cooling the climate and collapsing food chains. Birds are the surviving descendants of dinosaurs.')
entry('heart', 'how work pump beat',
      'The heart is a muscle that pumps blood in two loops: the right side sends blood to the lungs to pick up oxygen, and the left side pumps that oxygen-rich blood to the rest of the body. '
      'Valves keep the blood flowing in one direction; the "lub-dub" sound is the valves closing.')
entry('dream', 'why do we',
      'Nobody knows for certain why we dream. Leading ideas are that dreaming helps the brain sort memories and emotions, rehearse responses to threats, or is a by-product of brain activity during REM sleep.')
entry('yawn', 'why contagious',
      'Scientists still debate why we yawn; ideas include tiredness, boredom, cooling the brain and social signalling. Yawns are contagious partly because we unconsciously mirror people around us.')
entry('hiccup', 'why cause stop',
      'Hiccups are sudden involuntary spasms of the diaphragm, followed by the vocal cords snapping shut, which makes the "hic". Eating fast, fizzy drinks and excitement can trigger them. '
      'They usually stop on their own; slow sips of water or holding your breath briefly help some people.')
entry('popcorn', 'pop why how',
      'Each popcorn kernel has a little water inside a hard shell. When heated, the water turns to steam and the pressure builds until the shell bursts, and the soft starch inside puffs out and sets into foam.')
entry('bee', 'honey make how',
      'Bees collect nectar from flowers, carry it back to the hive and pass it between them, adding enzymes. They store it in wax cells and fan it with their wings to evaporate water until it thickens into honey.')
entry('bird', 'migrat fly south why',
      'Many birds migrate to follow food and good breeding conditions: they fly to warmer areas when insects and plants become scarce in winter, and return in spring when food is plentiful. '
      'They navigate using the Sun, stars, Earth\'s magnetic field and landmarks.')
entry('leaf|leaves', 'change colour color autumn fall why',
      'Leaves are green because of chlorophyll. In autumn, shorter days make trees stop producing it; as the green fades, yellow and orange pigments that were there all along show through, '
      'and some trees make new red pigments.')
entry('ocean|sea', 'salt salty why',
      'Rain slowly dissolves minerals from rocks, and rivers carry them to the sea. Water evaporates from the ocean but the salts stay behind, so over millions of years the sea became salty.')
entry('sky', 'night dark why',
      'The night sky is dark because your side of Earth faces away from the Sun, so there is no sunlight scattering in the air above you. Stars are bright points, but far too distant to light the sky.')
entry('season', 'why have cause',
      'Seasons happen because Earth\'s axis is tilted about 23.5°. For part of the year your hemisphere leans toward the Sun: sunlight hits more directly and days are longer, so it is summer. '
      'Half a year later it leans away and it is winter. It is not mainly about distance from the Sun.')
entry('moon', 'phase change shape why',
      'The Moon does not make its own light; we see the half lit by the Sun. As it orbits Earth over about a month, we see different amounts of that lit half, from new moon to full moon and back.')
entry('electric|electricity', 'how work what',
      'Electricity is the flow of electric charge, usually electrons moving through a wire. A battery or power station pushes the charges (that push is voltage), and the flow (current) '
      'can do work, such as heating a kettle or lighting a bulb, as it passes through.')
entry('battery', 'how work',
      'A battery stores energy in chemicals. Inside, a chemical reaction pushes electrons out of one terminal; they flow through your device and back into the other terminal. '
      'When the chemicals are used up, the battery is flat; rechargeable ones reverse the reaction.')
entry('democracy', 'what is',
      'Democracy is a system of government in which the people hold power, usually by voting for representatives in free and fair elections, with rights such as free speech and equal treatment under the law.')
entry('recession', 'what is',
      'A recession is a significant, widespread decline in economic activity lasting months, usually seen as falling output, rising unemployment and lower spending. A common rule of thumb is two quarters in a row of shrinking GDP.')
entry('interest', 'compound what how',
      'Compound interest means earning interest on your interest: each period\'s interest is added to the balance, so the next interest is calculated on a bigger amount, and growth speeds up over time.')
entry('photosynthesis', 'what how',
      'In photosynthesis, plants use light energy to turn carbon dioxide from the air and water from the soil into sugar, releasing oxygen. The sugar is their food and building material.')
entry('dna', 'what is',
      'DNA is the long molecule in your cells that carries genetic instructions. Its sequence of four chemical "letters" (A, T, C, G) encodes how to build proteins, which do most of the work in the body.')
entry('blockchain', 'what is how',
      'A blockchain is a shared record (ledger) kept by many computers at once. New entries are grouped into blocks, each linked to the one before with a cryptographic fingerprint, '
      'so changing an old entry would break the chain and be noticed.')
entry('ai|artificial', 'intelligence what is how',
      'Artificial intelligence is the broad field of making computers do tasks that usually need human intelligence, like recognising speech, translating or planning. '
      'Many modern AI systems learn patterns from large amounts of example data rather than following hand-written rules; I, CAEL, mostly use explicit rules and counts instead.')

# ---------------------------------------------------------------- jokes
JOKES = {
    'penguin': ['Why don\'t penguins like talking to strangers at parties? They find it hard to break the ice.',
                'What do penguins wear on their heads? Ice caps.'],
    'owl': ['Why did the owl get invited to every party? Because he was a real hoot.', 'What do you call an owl that does magic tricks? Hoo-dini.'],
    'cat': ['Why did the cat sit on the computer? To keep an eye on the mouse.', 'What do cats eat for breakfast? Mice Krispies.'],
    'dog': ['Why did the dog sit in the shade? Because he didn\'t want to be a hot dog.', 'What do you call a dog magician? A labracadabrador.'],
    'cow': ['Where do cows go on a night out? To the moo-vies.'], 'bee': ['Why do bees have sticky hair? Because they use honeycombs.'],
    'fish': ['Why are fish so smart? Because they live in schools.'], 'bear': ['What do you call a bear with no teeth? A gummy bear.'],
    'duck': ['What time do ducks wake up? At the quack of dawn.'], 'frog': ['Why are frogs so happy? They eat whatever bugs them.'],
    'cheese': ['What do you call cheese that isn\'t yours? Nacho cheese.'], 'computer': ['Why did the computer go to the doctor? It had a virus.'],
    'math': ['Why was the maths book sad? It had too many problems.'], 'coffee': ['Why did the coffee file a police report? It got mugged.'],
    'banana': ['Why did the banana go to the doctor? It wasn\'t peeling well.'], 'skeleton': ['Why don\'t skeletons fight each other? They don\'t have the guts.'],
    'teacher': ['Why did the teacher wear sunglasses? Because her students were so bright.'], 'robot': ['Why was the robot so tired? It had a hard drive.'],
    'chicken': ['Why did the chicken join a band? Because it had the drumsticks.'], 'horse': ['What do you call a horse that lives next door? A neigh-bour.'],
}
GENERIC_JOKES = ['Why don\'t scientists trust atoms? Because they make up everything.', 'I told my plant a joke. It didn\'t laugh, but it did grow on me.']


def joke(text, history_text):
    low = text.lower()
    if not re.search(r'\bjoke|\bpun\b|\bmake me laugh|\bsomething funny|\banother one\b|\bone (?:more )?(?:about|on|with) \w+|\bone more\b', low):
        return None
    if not re.search(r'\bjoke|\bpun\b|\blaugh|\bfunny', low) and not re.search(r'\bjoke|\bpun\b', history_text.lower()):
        return None
    used = set(re.findall(r"[^.?!]+\?[^.?!]+\.", history_text))
    for topic, items in JOKES.items():
        if re.search(r'\b' + topic, low):
            for j in items:
                if j not in history_text:
                    return j
            return items[0]
    for j in GENERIC_JOKES:
        if j not in history_text:
            return j
    return GENERIC_JOKES[0]


def about(text, e):
    """The stored answer must be about the things the person named: its text has to mention their rarest noun and
    at least half of their nouns ("water a cactus" is not the drinking-water entry, "cold brew" is not the cold one)."""
    from . import open_chat
    if open_chat.db() is None:
        return True
    s = stems(text)
    matched = {n for g in e['need'] for n in g if any(w.startswith(n) for w in s)} | (e['keys'] & s)
    matched = {m for m in matched if not any(o != m and o.startswith(m) for o in matched)}
    if len(matched) >= 2:
        return True          # two of the entry's own words: the person is asking about this topic
    nouns = []
    for w in open_chat.content(text):
        st = open_chat.stem(w)
        if open_chat.is_noun(w) and open_chat.idf(st) > 1.5:
            nouns.append((open_chat.idf(st), w, st))
    if not nouns:
        return e['chat']
    body = ' '.join(['|'.join(g) for g in e['need']] + sorted(e['keys']) + [e['answer']]).lower()
    have = {open_chat.stem(w) for w in re.findall(r"[a-z]+", body)}
    def hit(w, st):
        return st in have or w in have or any(h.startswith(w[:5]) for h in have if len(w) >= 5)
    covered = sum(n[0] for n in nouns if hit(n[1], n[2]))
    return covered >= 0.45 * sum(n[0] for n in nouns)


def best(text, prev=None):
    s = stems(text)
    low = text.lower()
    scored = []
    for i, e in enumerate(E):
        if all(any(any(w.startswith(n) for w in s) for n in group) for group in e['need']) and about(text, e):
            score = len(e['keys'] & s) + 2 * len(e['need'])
            scored.append((score, -i, e))
    if not scored:
        return None
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return scored[0][2]


def reply(messages):
    turns = [m['content'] for m in messages if m.get('role') == 'user']
    last = turns[-1]
    history = ' '.join(m['content'] for m in messages[:-1] if m.get('role') == 'assistant')
    j = joke(last, ' '.join(turns[:-1]) + ' ' + history)
    if j:
        lead = 'Here is another one: ' if len(turns) > 1 and re.search(r'another|one more|again', last, re.I) else ''
        return lead + j
    s = stems(last)
    # follow-up on an earlier topic
    if len(turns) > 1:
        for t in reversed(turns[:-1]):
            e = best(t)
            if e:
                for need, ans in e['follow']:
                    if any(any(w.startswith(n) for w in s) for n in need[0].split('|')):
                        return ans
                break
    e = best(last)
    asked = '?' in last or re.search(r'\b(?:suggest|tip|tips|advice|help|explain|tell me|show me|teach me|how do i|how to)\b', last, re.I)
    if e and (asked or (e['chat'] and len(last.split()) <= 40)):
        return e['answer']
    return None


from . import chat_knowledge_more  # noqa: E402,F401  (extends E)
