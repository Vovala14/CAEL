"""Getting started with a hobby or habit (authored, no model): 'I'm interested in photography, any tips?', 'How do I start
gardening?', then 'What do I need?' or 'How long does it take to get good?' on the same subject."""
import re

# name: (pattern, tips, gear, time to progress)
B = {
    'photography': (r'\bphotograph(?:y|er|s)?\b|\btaking (?:better )?(?:photos|pictures)\b', [
        "Start with the camera you have: a phone takes excellent photos, and learning to see a picture matters more than the kit.",
        "Learn the rule of thirds: put the subject a third of the way in rather than dead centre, and keep horizons level.",
        "Watch the light: early morning and the hour before sunset (golden hour) give soft, warm light; harsh midday sun is hardest.",
        "Get closer and fill the frame, and check what's behind your subject before you press the button.",
        "Take lots, then pick your best three each time and ask yourself why they work. A weekly theme (doors, shadows, red things) keeps you going."],
        "A phone is enough to start. If you want more control later, a second-hand entry-level mirrorless camera with a kit lens is the usual step, plus a spare battery and memory card. A free editing app (Snapseed, Lightroom mobile) helps more than extra lenses.",
        "Most people see a clear difference within a month or two of shooting a few times a week."),
    'gardening': (r'\bgarden(?:ing)?\b|\bgrow(?:ing)? (?:my own |our own )?(?:vegetables|veg|herbs|plants|flowers)\b', [
        "Start small: a few pots or one raised bed is easier to keep on top of than a whole plot.",
        "Learn your light: note how many hours of sun each spot gets, and choose plants to match (the label says).",
        "Begin with easy wins: herbs (mint, chives, parsley), salad leaves, radishes, courgettes, or tough perennials like lavender.",
        "Water deeply and less often, in the morning or evening, and check the soil with a finger rather than by the calendar.",
        "Add compost every year and mulch around plants; healthy soil solves most problems."],
        "A trowel, a hand fork, gloves, a watering can, some peat-free compost and pots with drainage holes. Secateurs come next. Skip expensive gadgets until you know what you enjoy growing.",
        "A first season teaches a lot; most people feel confident after two or three."),
    'cooking': (r'\b(?:learn(?:ing)? to cook|cooking|get better at cooking|cook better)\b', [
        "Master five simple meals you like (a pasta, a stir-fry, a soup, an omelette, a roast tray bake) before branching out.",
        "Read the whole recipe first and get everything chopped and measured before you start.",
        "Taste as you go and season with salt and a squeeze of lemon at the end; that fixes most bland food.",
        "Keep a sharp knife: it's safer and faster than a blunt one.",
        "Cook the same dish twice in a week; the second time you'll understand it."],
        "One good chef's knife, a large chopping board, a big frying pan, a saucepan with a lid, a baking tray, a wooden spoon and a measuring jug.",
        "A few weeks of cooking three or four times a week makes a big difference."),
    'guitar': (r'\bguitar\b', [
        "Practise a little every day (15-20 minutes) rather than once a week for hours; your fingers toughen up faster.",
        "Learn a handful of open chords first: G, C, D, E minor and A minor play thousands of songs.",
        "Use a tuner every time you pick it up; an out-of-tune guitar sounds wrong however well you play.",
        "Pick songs you love and slow them down; free lessons online (JustinGuitar is a well-known free course) give a clear path.",
        "Expect sore fingertips for the first couple of weeks; it passes."],
        "A guitar that's comfortable and set up properly (a shop can check the action), a clip-on tuner, a few picks, and a strap. Nylon-string guitars are gentler on beginners' fingers.",
        "With daily practice, most people play simple songs within a month or two."),
    'drawing': (r'\bdraw(?:ing)?\b|\bsketch(?:ing)?\b', [
        "Draw from life every day for 10-15 minutes: a mug, your hand, the view from the window.",
        "Look more than you draw: spend as much time studying the shape as moving the pencil.",
        "Start with simple shapes: see objects as boxes, cylinders and spheres, then refine.",
        "Practise light, loose lines first and only press harder once the shapes are right.",
        "Keep every sketchbook; looking back after a few months shows progress you can't see day to day."],
        "A sketchbook, a couple of pencils (HB and 2B), a rubber and a sharpener. That's genuinely all you need to start.",
        "Daily practice shows clear improvement in four to eight weeks."),
    'chess': (r'\bchess\b', [
        "Learn the basic principles: control the centre, develop your knights and bishops early, castle to keep your king safe.",
        "Before every move, check what your opponent's last move threatens, and whether your piece is safe where you put it.",
        "Play slower games (10 minutes or more) rather than blitz while learning.",
        "Do a few tactics puzzles daily; most beginner games are decided by tactics.",
        "Review your losses to find the one move that turned it."],
        "Nothing but a free account on Lichess or Chess.com, or a physical set and a friend.",
        "Steady improvement over a few months with regular games and puzzles."),
    'yoga': (r'\byoga\b', [
        "Start with beginner classes or a beginner video series, 15-20 minutes, three times a week.",
        "Move within what feels okay: stretching is fine, sharp pain is a signal to stop.",
        "Focus on slow breathing; it's half the benefit.",
        "Use props (a block, a strap, a cushion) freely; they make poses safer, not easier."],
        "A non-slip mat and comfortable clothes. A block and a strap are cheap extras.",
        "Most people notice more flexibility and calm within a few weeks."),
    'meditation': (r'\bmeditat(?:e|ion|ing)\b|\bmindfulness\b', [
        "Start with five minutes a day, at the same time, sitting comfortably.",
        "Focus on the breath; when your mind wanders, which it will, notice and come back. That coming back is the practice.",
        "Guided meditations (free apps and videos) make the first weeks easier.",
        "Don't judge a session as good or bad; consistency matters more than how it felt."],
        "Nothing at all. A cushion or chair and a timer are enough.",
        "Many people feel calmer within two to four weeks of daily practice."),
    'language': (r'\blearn(?:ing)? (?:a (?:new )?language|spanish|french|german|italian|japanese|chinese|mandarin|portuguese|korean|arabic|english)\b', [
        "Little and often: 15-20 minutes every day beats two hours once a week.",
        "Learn the most common 500 words and phrases first; they cover most everyday conversation.",
        "Speak early, even badly: a language exchange partner or a tutor once a week speeds things up.",
        "Listen to easy content you enjoy: podcasts for learners, children's shows, music with lyrics.",
        "Use spaced repetition flashcards for vocabulary; they show you words just before you'd forget them."],
        "A free app for daily practice, a beginner's textbook or course for grammar, and a notebook. A conversation partner matters more than any purchase.",
        "Basic conversation usually takes a few months of daily practice; fluency takes years."),
    'swimming': (r'\bswim(?:ming)?\b', [
        "Take adult beginner lessons; good technique early saves years of struggling.",
        "Get comfortable breathing out under water first: blow bubbles, then turn your head to breathe in.",
        "Swim short lengths with rests rather than trying to go far.",
        "Practise kick with a float and arms separately before putting it together."],
        "A swimsuit, goggles that seal well, and a swimming cap if the pool asks.",
        "Most adults can swim a length comfortably after a term of lessons."),
    'saving_money': (r'\bsav(?:e|ing) (?:more )?money\b|\bbudget(?:ing)?\b|\bspend less\b', [
        "Track every expense for one month; most people are surprised where the money goes.",
        "Pay yourself first: move a set amount into savings on payday, before you can spend it.",
        "Cancel subscriptions you don't use and check bills (phone, energy, insurance) for a cheaper deal once a year.",
        "Plan meals and shop with a list; food waste is a big hidden cost.",
        "Build an emergency fund of one to three months' essentials before investing."],
        "A free budgeting app or a simple spreadsheet, and a separate savings account so the money isn't in sight.",
        "A clear picture after one month of tracking; habits settle in about three."),
    # habits: (pattern, tips, what helps as tools, how long, what if it still doesn't work)
    'procrastination': (r'\bprocrastinat\w*|\bput(?:ting)? things off\b|\bkeep putting (?:it|things) off\b|\bget (?:started|going) on\b.{0,20}\b(?:work|tasks?|essay|project)\b', [
        "Shrink the first step until it's silly: \"open the document and write one sentence\". Starting is the hard part; carrying on is easier.",
        "Use a timer: work for 25 minutes, then take 5 (the Pomodoro method). Anyone can do 25 minutes.",
        "Put your phone in another room and close the tabs you don't need before you start.",
        "Decide the night before exactly what you'll do first, and when.",
        "Be kind to yourself about yesterday: guilt makes putting things off worse, not better."],
        "A timer (any phone or kitchen timer), a short written to-do list with the first step of each task, and a website blocker if the internet is the main pull.",
        "Most people notice a difference within a week of using small first steps and a timer every day.",
        "Then make the first step even smaller, or change the setting: work somewhere else (a library or café), or with someone else working alongside you, even on a video call. If you've been stuck for weeks, feel low, or can't concentrate on anything, it's worth talking to your GP: that can be a sign of stress or low mood rather than laziness."),
    'sleep': (r'\bsleep(?:ing)? (?:better|more|well)\b|\b(?:can\'?t|cannot|trouble|struggle to|hard to) (?:get to )?sleep\b|\binsomnia\b|\bfall asleep\b', [
        "Keep the same wake-up time every day, weekends included; it sets your body clock more than the bedtime does.",
        "Have no caffeine after about 2 pm, and go easy on alcohol, which wrecks the second half of the night.",
        "Dim the lights and put screens away for the last half hour; read or listen to something calm instead.",
        "Keep the bedroom cool, dark and quiet.",
        "If you can't sleep after about 20 minutes, get up and do something boring in dim light, then go back when sleepy."],
        "Nothing expensive: blackout curtains or an eye mask, earplugs, and an old-fashioned alarm clock so the phone can stay out of the bedroom.",
        "A regular wake time usually helps within one to two weeks.",
        "If it carries on for more than a few weeks, or you're exhausted during the day, snore loudly or stop breathing at night, see your GP: a short course of sleep therapy (CBT for insomnia) works well and often better than pills."),
    'focus': (r'\b(?:focus|concentrat\w*)\b.{0,20}\b(?:better|more|on (?:my )?(?:work|studies|studying))\b|\b(?:stay|be) (?:focused|motivated)\b|\bmotivat(?:ed|ion)\b.{0,20}\b(?:study|work|exercise|gym)\b', [
        "Work in short, set blocks (25-50 minutes) with real breaks.",
        "Write down the one thing that matters most today and do it first.",
        "Remove the easiest distraction: phone in another room, notifications off.",
        "Tie the task to something you care about, and reward yourself when a block is done.",
        "Sleep, food and a short walk do more for concentration than any trick."],
        "A timer, a paper to-do list, noise-cancelling headphones or quiet music without lyrics, and a website blocker if needed.",
        "Most people notice a difference within a week or two.",
        "Then change one thing about the setting (place, time of day, who you're with), and look at sleep and stress. If you can never concentrate on anything, at home or work, it's worth mentioning to your GP."),
}
STUCK = re.compile(r"(?i)\bwhat if (?:i )?(?:still|it (?:still )?does ?n.t work|that does ?n.t work|nothing works)\b|\bstill (?:can'?t|cannot|don'?t)\b|\bdoes ?n.t (?:help|work)\b")

ASK = re.compile(r"(?i)\b(?:tips?|advice|(?:good|best|better) way(?:s)? to|ways to|how (?:do|can|could) i (?:stop|beat|get over|improve)|help me (?:stop|sleep|focus)|"
                 r"where (?:do|should) i (?:start|begin)|how (?:do|can|should) i (?:start|begin|get started|get into|learn|get better)|"
                 r"(?:want|would like|thinking) (?:to|about) (?:start|learn|take up|try|get into)|getting started|beginner|new to|interested in|take up)\b")
GEAR = re.compile(r"(?i)\bwhat (?:do|would|should) i (?:need|buy|get)\b|\b(?:equipment|gear|kit|tools)\b|\bwhat to buy\b")
TIME = re.compile(r"(?i)\bhow long\b|\bhow (?:quickly|fast)\b|\bwhen will i\b")


def find(text):
    for name, row in B.items():
        if re.search('(?i)' + row[0], text):
            return name
    return None


_index = None


def matched(text):
    global _index
    if _index is None:
        from .phrase_match import Index
        _index = Index({n: n.replace('_', ' ') + ' ' + ' '.join(row[1]) + ' ' + row[2] for n, row in B.items()})
    return _index.best(text, least=6.0, margin=1.3)


def respond(messages):
    text = (messages[-1].get('content') or '').strip()
    if not text or len(text) > 240:
        return None
    name = find(text)
    if name is None and ASK.search(text):
        name = matched(text)                # a rewording: word overlap with the guides' own text (phrase_match)
    if name and ASK.search(text) and not re.search(r'(?i)\b(?:broken|won\'?t|stopped|problem|fix|repair|leak|error)\b', text):
        tips = B[name][1]
        habit = len(B[name]) > 4
        lead = 'A few things that help most people:' if habit else 'A few things that help most beginners:'
        close = '' if habit else "\n\nWant to know what you'd need to get started?"
        return dict(route='chat/beginner', response=lead + '\n\n' + '\n'.join(f'- {t}' for t in tips) + close,
                    sources=[], details=f'Authored beginner guide ({name}; beginner.py).')
    if name is None and len(text.split()) <= 14:
        for m in reversed(messages[:-1]):
            if m.get('role') != 'assistant':
                continue
            said = m.get('content') or ''
            prev = next((n for n, row in B.items() if row[1][0][:40] in said or said.startswith(row[2][:40]) or said.startswith(row[3][:40])), None)
            if prev and (GEAR.search(text) or re.search(r"(?i)^\s*(?:yes|yeah|sure|please|ok)\b", text)):
                return dict(route='chat/beginner-followup', response=B[prev][2], sources=[], details=f'Authored beginner guide ({prev}; beginner.py).')
            if prev and len(B[prev]) > 4 and STUCK.search(text):
                return dict(route='chat/beginner-followup', response=B[prev][4], sources=[], details=f'Authored habit guide ({prev}; beginner.py).')
            if prev and TIME.search(text):
                return dict(route='chat/beginner-followup', response=B[prev][3], sources=[], details=f'Authored beginner guide ({prev}; beginner.py).')
            break
    return None
