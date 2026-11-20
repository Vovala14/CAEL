"""Everyday situations and their follow-ups (authored, no model).

A situation is named once ('I keep arguing with my brother', 'How do I politely decline a wedding invitation?') and then
the follow-ups are short: 'How do I bring it up?', 'Should I give a reason?', 'I water it every day.' A web search on those
few words drifts to forum threads about tattoos or toddlers. Here each situation keeps its subject from the earlier turns,
and the follow-up gets the answer a sensible friend would give next.

Each entry: name, subject (pattern over the user's turns), first (answer when the situation is first named, or None to leave
the first answer to another desk), and follow-ups [(pattern, answer)]. An answer may be a function of the conversation.
"""
import re

FAMILY = r'(?:brother|sister|sibling|mum|mom|mother|dad|father|parents?|son|daughter|partner|husband|wife|boyfriend|girlfriend|flatmate|roommate|housemate|best friend|friend)'

# language: (speakers, where, effort for an English speaker)
LANGS = {
    'spanish': ('about 550 million speakers', 'Spain, Mexico, most of Central and South America (not Brazil) and large parts of the US',
                'one of the easiest for English speakers: regular spelling, clear pronunciation; about 6 months of steady study to get conversational'),
    'french': ('about 300 million speakers', 'France, Belgium, Switzerland, Quebec and much of West and Central Africa',
               'easy vocabulary for English speakers (many shared words) but harder pronunciation and spelling; similar time to Spanish'),
    'german': ('about 130 million speakers', 'Germany, Austria and Switzerland', 'more grammar to learn (cases, three genders); a bit longer than Spanish or French'),
    'italian': ('about 65 million speakers', 'Italy and parts of Switzerland', 'easy pronunciation and spelling; about as quick as Spanish'),
    'portuguese': ('about 260 million speakers', 'Brazil, Portugal, Angola and Mozambique', 'close to Spanish in grammar, trickier vowels; similar time to Spanish'),
    'mandarin': ('about 1.1 billion speakers', 'China, Taiwan and Singapore', 'much harder: tones and characters; several times longer than Spanish'),
    'japanese': ('about 125 million speakers', 'Japan', 'much harder: three writing systems and very different grammar; several times longer than Spanish'),
}
LANG_ALIASES = {'chinese': 'mandarin'}
PLACES = [
    (r'\bbrazil', 'portuguese'), (r'\bportugal', 'portuguese'),
    (r'\bsouth america|\blatin america|\bcentral america|\bmexic|\bspain\b|\bargentin|\bperu\b|\bcolombia|\bchile\b|\bcuba\b|\bcosta rica|\bbolivia|\becuador|\bvenezuela|\buruguay|\bparaguay|\bguatemala', 'spanish'),
    (r'\bfrance\b|\bparis\b|\bquebec|\bmontreal|\bbelgi|\bwest africa|\bsenegal|\bmorocco|\bfrench-speaking', 'french'),
    (r'\bgermany|\bberlin|\baustria|\bvienna|\bmunich', 'german'), (r'\bital(?:y|ian)\b|\brome\b|\bmilan|\bflorence', 'italian'),
    (r'\bchina\b|\btaiwan|\bbeijing|\bshanghai', 'mandarin'), (r'\bjapan|\btokyo|\bkyoto|\bosaka', 'japanese'),
]
LANG_RE = r'(spanish|french|german|italian|portuguese|mandarin|chinese|japanese)'


def lang(w):
    w = w.lower()
    return LANG_ALIASES.get(w, w)


def languages_first(convo):
    m = re.search(r'(?i)\b' + LANG_RE + r'\b.{0,30}\bor\b.{0,10}\b' + LANG_RE + r'\b', convo['last'])
    a, b = lang(m[1]), lang(m[2])
    if a == b:
        return None
    rows = '\n'.join(f'- **{x.title()}**: {LANGS[x][0]}, spoken in {LANGS[x][1]}; {LANGS[x][2]}.' for x in (a, b))
    return (f'Both are good choices; the deciding question is usually where and with whom you want to use it.\n\n{rows}\n\n'
            f'If you have no strong reason either way, pick the one you will hear and use most: the places you travel to, people you know, '
            f'or films and music you enjoy. Learning the second one later is much quicker, because so much carries over. Where do you see yourself using it?')


def languages_follow(convo):
    users = ' '.join(convo['before'])
    m = re.search(r'(?i)\b' + LANG_RE + r'\b.{0,30}\bor\b.{0,10}\b' + LANG_RE + r'\b', users)
    if not m:
        return None
    options = {lang(m[1]), lang(m[2])}
    here = next((l for p, l in PLACES if re.search('(?i)' + p, convo['last'])), None)
    if not here:
        return None
    if here in options:
        other = (options - {here}).pop()
        extra = (' Brazil is the exception: there it is Portuguese, which Spanish speakers can often half-understand.'
                 if here == 'spanish' and re.search(r'(?i)south america', convo['last']) else '')
        return (f'Then **{here.title()}**. It is the language of {LANGS[here][1]}, so you will use it every day there, and locals '
                f'appreciate even a little.{extra} Start with travel phrases, numbers, food and directions, and aim for short daily practice. '
                f'{other.title()} can come later, and it will be quicker then.')
    return (f'Neither, for that trip: the main language there is {here.title()}. If the trip is your main reason, it may be worth learning '
            f'{here.title()} instead, or a few survival phrases in it alongside whichever of the two you pick.')


def savings_follow(convo):
    m = re.search(r'(?i)\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve|eighteen)\s+months?\b', convo['last'])
    if not m:
        return None
    words = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'twelve': 12, 'eighteen': 18}
    n = int(m[1]) if m[1].isdigit() else words[m[1].lower()]
    said = m[1] if m[1].isdigit() else m[1].lower()
    if n >= 12:
        verdict = f'{said.capitalize()} months of savings is a strong cushion: more than most people have when they start.'
    elif n >= 6:
        verdict = (f'{said.capitalize()} months is a reasonable cushion, but tighter than it sounds: most new businesses take longer than expected to pay you a '
                   'wage, often a year or more.')
    else:
        verdict = (f'{said.capitalize()} months is a thin cushion: most new businesses take a year or more before they pay a wage, so it would be safer to build '
                   'more savings or start alongside your job first.')
    return (verdict + ' Ways to make it go further:\n\n'
            '- Work out your bare monthly costs (rent, bills, food, debt payments) and divide your savings by that, not by what you spend now.\n'
            '- Test the business while still employed: evenings, weekends or a few paying customers first.\n'
            '- Set a checkpoint in advance (for example: if it isn\'t making X by month 4, I go back to part-time work), so you decide calmly, not in a panic.\n'
            '- Keep one or two months untouched as a true emergency fund.')


def decline_first(convo):
    """The wording depends on the occasion: 'you both' and a registry belong to a wedding, not a birthday party."""
    text = ' '.join(convo['before'] + [convo['last']])
    if re.search(r'(?i)\bwedding\b', text):
        return ('Reply soon, keep it warm and short, and you don\'t need a detailed excuse. For example:\n\n'
                '> Thank you so much for the invitation, it means a lot that you thought of us. Unfortunately we won\'t be able to come, but we\'re '
                'so happy for you both and hope you have a wonderful day.\n\n'
                '- Reply by the RSVP date, in the way they asked (card, website or message).\n'
                '- For a close friend or family, a short call or personal message before the formal RSVP is kinder.\n'
                '- Sending a card or a small gift from the registry is a nice touch, though not required if you\'re not attending.')
    if re.search(r'(?i)\bbirthday\b', text):
        who = 'her' if re.search(r'(?i)\b(?:her|she)\b', text) else 'him' if re.search(r'(?i)\b(?:him|he)\b', text) else 'them'
        return (f'Tell {who} soon and personally (a message or call, not just a no on the group chat), say you\'re sorry to miss it, and offer '
                'another way to celebrate. For example:\n\n'
                '> Thanks so much for inviting me! I\'m really sorry, I can\'t make it that day. I hope you have a brilliant birthday. '
                'Can I take you out for a drink or a coffee the week after to celebrate properly?\n\n'
                '- You don\'t need a long excuse; a short, true reason is enough if you want to give one.\n'
                '- A card, a message on the day, or a small present when you meet up shows you care even though you can\'t be there.')
    return ('Reply soon, thank them, and keep it short and warm; you don\'t need a detailed excuse. For example:\n\n'
            '> Thank you so much for the invitation, it\'s really kind of you to think of me. Unfortunately I can\'t make it this time, but I hope '
            'it\'s a lovely evening, and I\'d love to catch up soon.\n\n'
            '- Reply by any date they gave, the way they asked.\n'
            '- If it\'s someone close, a quick call or personal message is kinder than a one-line reply.')


ENTRIES = [
    dict(name='family_conflict',
         subject=r'\b(?:argu(?:e|ing|ments?)|fight(?:ing|s)?|bicker(?:ing)?|row(?:ing|s)?|clash(?:ing)?|fall(?:ing)? out|snap(?:ping)? at|keep disagreeing)\b.{0,50}\b' + FAMILY + r'\b|'
                 r'\b' + FAMILY + r'\b.{0,40}\b(?:argu(?:e|ing)|fight(?:ing)?|bicker(?:ing)?|we keep (?:arguing|fighting))\b',
         first=('That is wearing, especially when it\'s over small things: the small things are usually standing in for something bigger, like feeling '
                'unheard, taken for granted, or old roles from growing up. A few things that usually help:\n\n'
                '- Notice the pattern: what the arguments are about, when they happen (tired, hungry, around certain topics), and who starts them.\n'
                '- In the moment, step back before it escalates: "I don\'t want to fight about this, can we talk later?" is enough.\n'
                '- Have one calm conversation about the pattern itself, not the latest argument.\n\n'
                'Would you like help with how to bring it up?'),
         follow=[(r'\bbring (?:it|this) up|\btalk to (?:him|her|them)|\bhow (?:do|should|can) i (?:say|start|raise|approach|tell)|\bwhat (?:do|should) i say\b|\bwithout (?:it )?(?:turning|becoming|starting)|\byes\b|\bplease\b',
                  'Pick a calm moment, not straight after a row, and somewhere private. Then:\n\n'
                  '1. **Start with the relationship:** "I don\'t like how often we end up arguing. I\'d like us to get on better."\n'
                  '2. **Describe the pattern, not the person:** "We seem to clash over small things like the dishes," not "you always start it."\n'
                  '3. **Own your part:** "I know I get snappy when I\'m tired." It makes it much easier for them to admit theirs.\n'
                  '4. **Ask, then listen:** "Does it feel like that to you? Is something bothering you?" Let them finish before you answer.\n'
                  '5. **Agree one small thing:** a signal to pause ("let\'s leave it"), or a rule for the usual trigger.\n\n'
                  'If it starts heating up, stop and come back to it: "I don\'t want this to become another fight. Let\'s try again tomorrow."'),
                 (r'\bdefensive|\bangry|\bshout|\bwon\'?t listen|\bdoesn\'?t listen|\bdenies|\bblames? me|\bwhat if (?:he|she|they) (?:gets?|says?|won\'?t|doesn\'?t)',
                  'Then don\'t push on in that moment. Stay calm, say "I\'m not trying to blame you, I just want us to get on better," and if it still '
                  'escalates, end it kindly: "Let\'s leave it for now." One try rarely fixes it; what changes things is you consistently not taking the bait. '
                  'If the arguments ever turn frightening or abusive, that is different: talk to someone you trust or a support line.'),
                 (r'\bnormal\b|\bcommon\b|\beveryone\b',
                  'Very normal. Close family see each other at their most tired and least guarded, and old roles from childhood stick around. '
                  'It\'s worth working on because it usually gets better once the pattern is named.'),
                 (r'\blet it go\b|\bignore\b|\bjust leave it\b|\bnot worth\b',
                  'Letting small things go is often right, as long as you are really letting go, not storing it up. If the same thing keeps bothering you, '
                  'one calm conversation is better than many small fights.')]),
    dict(name='decline_invitation',
         subject=r'\b(?:decline|turn down|say no to|refuse|get out of|not (?:going|go|attend)|can\'?t (?:go|attend|make it|come))\b.{0,40}\b(?:invit\w*|wedding|party|event|dinner|baby shower|hen do|stag do|bachelor|birthday)\b|'
                 r'\b(?:invit\w*|wedding|party)\b.{0,40}\b(?:decline|turn (?:it )?down|say no|can\'?t (?:go|attend|make it))\b',
         first=lambda c: decline_first(c),
         follow=[(r'\breason\b|\bexcuse\b|\bsay why\b|\bexplain why\b|\btell (?:them|her|him) why\b|\bhave to (?:say|explain)\b',
                  'You don\'t have to give one. "We won\'t be able to make it" is complete and polite. If you want to, keep it brief and true '
                  '("we\'re away that weekend", "it\'s too far for us this time"). Avoid inventing elaborate excuses: they\'re easy to trip over later.'),
                 (r'\bgift\b|\bpresent\b|\bsend something\b|\bcard\b',
                  'It\'s a kind gesture but not obligatory when you\'re not going. A card with a warm note is always fine; for a close friend or relative, '
                  'many people send a small gift from the registry or a modest amount in a card.'),
                 (r'\bupset\b|\boffended\b|\bhurt\b|\bangry\b|\bmad\b|\bwhat if (?:they|she|he)\b',
                  'Most people are disappointed briefly and then busy with everything else. Saying no early, warmly and without a pile of excuses is the most '
                  'respectful way. If it\'s someone close, a quick call to say how sorry you are to miss it, and a plan to celebrate with them later, helps a lot.'),
                 (r'\btext\b|\bshort(?:er)?\b|\bmessage\b|\bwhatsapp\b|\bemail\b',
                  lambda c: 'Short version: "Thank you so much for inviting us! Sadly we can\'t make it, but we\'ll be thinking of you on the day. Congratulations!"'
                  if re.search(r'(?i)\bwedding\b', ' '.join(c['before'])) else
                  'Short version: "Thanks so much for the invite! Sadly I can\'t make it, but I hope it\'s a great one. Let\'s catch up soon!"'),
                 (r'\bfamily\b|\bbest friend\b|\bclose friend\b|\bsister\b|\bbrother\b|\bcousin\b',
                  'For someone close, tell them personally first (a call or a face-to-face chat), then send the RSVP. Say you\'re sorry to miss it, and offer '
                  'something else: dinner before or after, or helping with something in the run-up.')]),
    dict(name='quit_for_business',
         subject=r'\b(?:quit(?:ting)?|leav(?:e|ing)|give up)\b.{0,25}\b(?:my )?(?:job|work|career)\b.{0,40}\b(?:start|starting|open|launch|run)\b.{0,20}\b(?:business|company|shop|startup|own thing|cafe|café|bakery)\b|'
                 r'\bstart(?:ing)? (?:my own |a )?(?:business|company|startup)\b.{0,40}\bquit',
         first=('Not crazy: plenty of people do it, and it can be the right call. It\'s safer when a few things are true first:\n\n'
                '1. **Real customers:** someone has already paid you, or clearly would, for the thing you plan to sell.\n'
                '2. **A runway:** savings to cover your bare living costs for a good while, since most new businesses take a year or more to pay a wage.\n'
                '3. **A test while employed:** evenings, weekends or a few early customers, so you learn the hard parts before giving up your income.\n'
                '4. **A fallback:** skills and contacts that would let you find work again if it doesn\'t work out.\n\n'
                'How much savings do you have, and have you been able to test the idea yet?'),
         follow=[(r'\bsavings?\b|\bsaved\b|\bmonths?\b.{0,20}\b(?:money|cushion|runway)\b', savings_follow),
                 (r'\btest\b|\bvalidate\b|\bcheck (?:the|if|whether)\b|\bhow (?:do|can) i know\b',
                  'Sell before you build: describe the offer and ask 10-20 likely customers to pre-order, book or pay a deposit. Run a small version on '
                  'weekends, or one paid pilot for a real client. Track two numbers: how many say yes when asked to pay, and what it costs you to deliver.'),
                 (r'\bpart[- ]time\b|\bside\b|\bkeep (?:my )?job\b|\bboth\b',
                  'Starting on the side is often the best first step: you keep your income and find out whether people pay. Check your contract for '
                  'non-compete or side-work clauses, and move to part-time or leave once the business covers a meaningful part of your costs.'),
                 (r'\bfail|\bdoesn\'?t work|\bgoes wrong|\bworst case\b',
                  'Then you go back to work with skills most employers value: selling, managing money, running projects. Decide your stop point in advance '
                  '(a date or an amount of savings left), and keep your network warm so finding work again is quick.')]),
    dict(name='budget_dinners',
         subject=r'\b(?:plan|ideas? for|help (?:me )?(?:plan|with))\b.{0,30}\b(?:week(?:ly)?|7|seven)\b.{0,20}\b(?:dinners?|meals?|evening meals?)\b|\bmeal plan\b|\b(?:cheap|budget|inexpensive)\b.{0,15}\b(?:dinners?|meals?)\b|\bdinners?\b.{0,15}\bon a budget\b',
         first=('Here\'s a cheap week built around a few ingredients that carry over, so nothing goes to waste:\n\n'
                '1. **Monday:** chilli con carne with rice (make a double batch).\n'
                '2. **Tuesday:** leftover chilli in baked potatoes or wraps.\n'
                '3. **Wednesday:** pasta with tomato sauce, spinach and a tin of tuna or white beans.\n'
                '4. **Thursday:** chicken thigh and vegetable tray bake (carrots, onions, potatoes).\n'
                '5. **Friday:** egg fried rice with frozen peas and any leftover chicken.\n'
                '6. **Saturday:** homemade pizza on flatbreads or wraps.\n'
                '7. **Sunday:** big vegetable and lentil soup with bread; freeze the rest for lunches.\n\n'
                'Shop with a list, buy supermarket own brands, and use frozen vegetables freely: they are just as nutritious. '
                'Tell me if you don\'t eat meat or are cooking for children and I\'ll adjust it.'),
         follow=[(r'\b(?:don\'?t|do not|doesn\'?t|can\'?t) eat (?:meat|fish|chicken)|\bvegetarian\b|\bveggie\b|\bno meat\b|\bmeat[- ]free\b|\bvegan\b',
                  lambda c: ('A meat-free version of the same week:\n\n'
                             '1. **Monday:** bean and lentil chilli with rice (double batch).\n'
                             '2. **Tuesday:** leftover chilli in baked potatoes or wraps.\n'
                             '3. **Wednesday:** pasta with tomato sauce, spinach and white beans.\n'
                             '4. **Thursday:** chickpea and vegetable tray bake with ' + ('a tahini dressing' if re.search(r'(?i)vegan', c['last']) else 'feta or halloumi') + '.\n'
                             '5. **Friday:** ' + ('tofu' if re.search(r'(?i)vegan', c['last']) else 'egg') + ' fried rice with frozen peas and sweetcorn.\n'
                             '6. **Saturday:** homemade pizza on flatbreads' + (' with vegetables and vegan cheese' if re.search(r'(?i)vegan', c['last']) else '') + '.\n'
                             '7. **Sunday:** red lentil and vegetable soup with bread; freeze the rest.\n\n'
                             'Beans, lentils, chickpeas' + (', tofu' if re.search(r'(?i)vegan', c['last']) else ', eggs') + ' and frozen vegetables are among the cheapest protein there is, so this week usually costs less than the meat one.')),
                 (r'\bshopping list\b|\bwhat (?:do|should) i buy\b|\bingredients\b',
                  'Core shopping list: rice, pasta, potatoes, a bag of onions, carrots, garlic, 2-3 tins of chopped tomatoes, tins of beans and lentils, '
                  'frozen peas and spinach, eggs, cheese, flatbreads or wraps, stock cubes, and (if you eat meat) mince and chicken thighs. Check what you '
                  'already have first.'),
                 (r'\bkids?\b|\bchildren\b|\bfamily\b|\bfussy\b|\bpicky\b',
                  'For children, keep the same week but serve parts separately (plain rice, sauce on the side), make the chilli mild, and let them build their '
                  'own wraps and pizzas: they eat more of what they assemble.'),
                 (r'\bhow much\b|\bcost\b|\bcheap(?:er)?\b|\bprice\b',
                  'It varies by country and shop, but a week like this for two usually costs about the same as two takeaways. Batch cooking and using '
                  'leftovers the next day are what keep it cheap.')]),
    dict(name='learn_cooking', subject=r'\b(?:learn(?:ing)? to cook|start(?:ing)? (?:to )?cook|cooking for (?:the first time|beginners)|get better at cooking|cook better|beginner cook)\b',
         first=None,
         follow=[(r'\bwhat (?:should|could|do) i (?:make|cook|try) first\b|\bfirst (?:thing|dish|meal|recipe)\b|\beasy (?:first )?(?:dish|meal|recipe)\b|\bwhere do i start\b',
                  'Start with **a simple tomato pasta**: it teaches the basics in 20 minutes.\n\n'
                  '1. Soften a chopped onion and two garlic cloves in olive oil over a medium heat for 5-8 minutes.\n'
                  '2. Add a tin of chopped tomatoes, a pinch of salt and sugar, and simmer for 10 minutes while the pasta boils in well-salted water.\n'
                  '3. Stir the drained pasta into the sauce with a splash of the cooking water, and finish with cheese or basil.\n\n'
                  'After that: an omelette (heat control), a stir-fry (prep and timing), and a tray bake (using the oven). Those four cover most everyday cooking.')]),
    dict(name='yellow_plant', subject=r'\b(?:plant|leaves|leaf)\b.{0,40}\b(?:yellow|turning brown|drooping|wilting|dying)\b|\byellow(?:ing)? leaves\b',
         first=None,
         follow=[(r'\b(?:water(?:ing)?|watered)\b.{0,20}\b(?:every ?day|daily|twice a day|each day|every morning|every evening|a lot)\b|\bevery ?day\b.{0,15}\bwater',
                  'That\'s very likely the cause: watering every day keeps the soil wet, the roots can\'t get air, and the plant shows it with yellow, often '
                  'soft lower leaves. What to do:\n\n'
                  '1. Stop watering until the top few centimetres of soil feel dry (push a finger in); for most houseplants that\'s about once a week in summer and less in winter.\n'
                  '2. Make sure the pot has a drainage hole and empty the saucer after watering.\n'
                  '3. If the soil smells sour or the roots are brown and mushy, repot into fresh, dry compost and trim the rotten roots.\n\n'
                  'Yellow leaves won\'t turn green again, but healthy new growth in a few weeks shows it has recovered.'),
                 (r'\b(?:hardly|rarely|once a month|forget to water|don\'?t water|not (?:often|much))\b',
                  'Then it\'s probably thirst: leaves going yellow and crisp, soil pulling away from the pot. Water thoroughly until it runs out of the bottom, '
                  'then again whenever the top few centimetres are dry.'),
                 (r'\bno (?:drainage|holes?)\b|\bwithout (?:a )?(?:drainage|holes?)\b',
                  'That\'s a common culprit: water collects at the bottom and rots the roots. Move it into a pot with a drainage hole (or use the current '
                  'pot as an outer decorative one) and water less often.'),
                 (r'\b(?:dark|no window|north[- ]facing|corner|away from the window|low light)\b',
                  'Too little light gives pale, yellowing leaves and slow, stretched growth. Move it close to a bright window but out of harsh midday sun, '
                  'and water less while it adjusts, since plants in low light use less water.')]),
    dict(name='languages', subject=r'\b(?:learn|study|pick|choose|start)\b.{0,30}\b' + LANG_RE + r'\b.{0,30}\bor\b.{0,10}\b' + LANG_RE + r'\b',
         first=languages_first,
         follow=[(r'\b(?:travel|trip|visit|going|go|move|live|work|holiday|family|partner)\b', languages_follow)]),
    dict(name='visit_ideas',
         subject=r'\b' + FAMILY + r's?\b.{0,30}\b(?:is|are|\'s|\'re)\s+(?:visiting|coming|staying|over)\b.{0,60}\b(?:ideas?|things to do|what (?:should|could|can) we do|plans?|suggestions?|entertain|keep (?:him|her|them) busy)\b|'
                 r'\b(?:ideas?|things to do|what to do)\b.{0,40}\bwhen (?:my )?' + FAMILY + r'\b.{0,20}\b(?:visits?|comes?|stays?)\b',
         first=('Nice, having someone to stay is a good excuse to do things you never get round to. A mix usually works best:\n\n'
                '- **Show them your area:** your favourite café or bakery, a market, a good walk or viewpoint, the best local pub or restaurant.\n'
                '- **One bigger outing:** a museum or gallery, a day trip to a nearby town, the coast or countryside, a match or a show.\n'
                '- **Something active:** a hike, a bike ride, bowling, climbing, mini golf or an escape room.\n'
                '- **Easy evenings at home:** cook together, a takeaway and a film or series, board games or cards.\n'
                '- **Leave some slack:** visits are tiring; one free afternoon to just catch up is often the best part.\n\n'
                'What do they enjoy, and is there a budget? I can narrow it down.'),
         follow=[(r'\b(?:cheap|free|budget|money|afford|broke|not much)\b',
                  'On a budget: free museums and galleries, a long walk or a picnic somewhere with a view, a market for browsing, '
                  'cooking a nice meal at home instead of eating out, board games or a film night, and checking local listings for '
                  'free events, open days or live music.'),
                 (r'\b(?:rain|raining|rainy|bad weather|wet|cold|indoors?|inside)\b',
                  'For bad weather: a museum, aquarium or gallery, the cinema, bowling or an escape room, an indoor climbing wall, '
                  'a long lunch somewhere cosy, or a day in with baking, games and a film.'),
                 (r'\b(?:kids?|children|nephews?|nieces?|little ones|family with)\b',
                  'With children along: a park or playground, a farm or zoo, a swimming pool, a science or natural history museum, '
                  'soft play or trampolines on a wet day, and keep outings to half a day with a food stop.'),
                 (r'\b(?:outdoors?|hik\w*|walk\w*|nature|active|sport\w*)\b',
                  'For someone who likes the outdoors: a day hike or coastal walk, cycling, kayaking or paddleboarding if there is water '
                  'nearby, climbing, and a good pub or café at the end of it.'),
                 (r'\b(?:food|foodie|eat\w*|restaurants?|cook\w*)\b',
                  'For a food lover: a market or food hall, the best local spot for your area\'s speciality, a cooking session at home '
                  'together, a bakery or brunch crawl, and one nicer dinner out.')]),
]
for e in ENTRIES:
    e['subject'] = re.compile('(?i)' + e['subject'])
    e['follow'] = [(re.compile('(?i)' + p), t) for p, t in e['follow']]


def render(answer, convo):
    return answer(convo) if callable(answer) else answer


def respond(messages):
    users = [m.get('content') or '' for m in messages if m.get('role') == 'user']
    if not users:
        return None
    last = users[-1].strip()
    if not last or len(last) > 300:
        return None
    convo = dict(last=last, before=users[-4:-1])
    for e in ENTRIES:
        if e['first'] is not None and e['subject'].search(last):
            text = render(e['first'], convo)
            if text:
                return dict(route='chat/situation', response=text, sources=[], details=f'Authored situation ({e["name"]}; situations.py).')
    if len(users) < 2 or len(last.split()) > 25:
        return None
    for back in reversed(users[-4:-1]):        # the nearest earlier turn that named a situation
        for e in ENTRIES:
            if not e['subject'].search(back):
                continue
            for pattern, answer in e['follow']:
                if pattern.search(last):
                    text = render(answer, convo)
                    if text:
                        return dict(route='chat/situation-followup', response=text, sources=[], details=f'Authored situation ({e["name"]}; situations.py).')
            break
    return None
