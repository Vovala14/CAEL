"""Finish a well-known line: "complete: roses are red", "roses are red, violets are", "an apple a day".

A hand-written table of traditional nursery rhymes, proverbs and common sayings (all public domain). A request to
complete, finish or continue a line is matched against the table by its start; a message that is only the start of a
listed line (at least three words) is completed too. Unknown lines get an honest reply instead of small talk.
"""
import re

LINES = [
    # Nursery rhymes and verses
    'Roses are red, violets are blue, sugar is sweet, and so are you.',
    'Twinkle, twinkle, little star, how I wonder what you are.',
    'Humpty Dumpty sat on a wall, Humpty Dumpty had a great fall.',
    'Jack and Jill went up the hill to fetch a pail of water.',
    'Mary had a little lamb, its fleece was white as snow.',
    'Baa, baa, black sheep, have you any wool? Yes sir, yes sir, three bags full.',
    'Hickory dickory dock, the mouse ran up the clock.',
    'Old MacDonald had a farm, E-I-E-I-O.',
    'Row, row, row your boat, gently down the stream.',
    'Rain, rain, go away, come again another day.',
    'Little Miss Muffet sat on a tuffet, eating her curds and whey.',
    'Hey diddle diddle, the cat and the fiddle, the cow jumped over the moon.',
    'Ring around the rosie, a pocket full of posies.',
    'Pat-a-cake, pat-a-cake, baker\'s man, bake me a cake as fast as you can.',
    'One, two, buckle my shoe; three, four, knock at the door.',
    'Sticks and stones may break my bones, but words will never hurt me.',
    'Star light, star bright, first star I see tonight.',
    'Early to bed and early to rise makes a man healthy, wealthy and wise.',
    'Once upon a time, there lived a king and a queen.',
    'The itsy bitsy spider climbed up the water spout.',
    'London Bridge is falling down, falling down, falling down.',
    'Georgie Porgie, pudding and pie, kissed the girls and made them cry.',
    'Little Bo Peep has lost her sheep and doesn\'t know where to find them.',
    'Three blind mice, three blind mice, see how they run.',
    # Proverbs and sayings
    'An apple a day keeps the doctor away.',
    'The early bird catches the worm.',
    'Actions speak louder than words.',
    'Better late than never.',
    'A picture is worth a thousand words.',
    'Don\'t count your chickens before they hatch.',
    'Don\'t judge a book by its cover.',
    'All that glitters is not gold.',
    'Where there\'s a will, there\'s a way.',
    'When in Rome, do as the Romans do.',
    'Rome wasn\'t built in a day.',
    'A bird in the hand is worth two in the bush.',
    'Birds of a feather flock together.',
    'Practice makes perfect.',
    'Two heads are better than one.',
    'Too many cooks spoil the broth.',
    'The pen is mightier than the sword.',
    'Honesty is the best policy.',
    'Look before you leap.',
    'Haste makes waste.',
    'Every cloud has a silver lining.',
    'Curiosity killed the cat.',
    'Absence makes the heart grow fonder.',
    'Beauty is in the eye of the beholder.',
    'You can\'t judge a book by its cover.',
    'You can lead a horse to water, but you can\'t make it drink.',
    'If at first you don\'t succeed, try, try again.',
    'Laughter is the best medicine.',
    'Knowledge is power.',
    'Time is money.',
    'No pain, no gain.',
    'Out of sight, out of mind.',
    'Slow and steady wins the race.',
    'The grass is always greener on the other side.',
    'There\'s no place like home.',
    'A penny saved is a penny earned.',
    'A friend in need is a friend indeed.',
    'Necessity is the mother of invention.',
    'Fortune favours the bold.',
    'Strike while the iron is hot.',
    'Kill two birds with one stone.',
    'It takes two to tango.',
    'Easy come, easy go.',
    'Great minds think alike.',
    'Many hands make light work.',
    'Still waters run deep.',
    'You reap what you sow.',
    'Don\'t put all your eggs in one basket.',
    'Don\'t bite the hand that feeds you.',
    'Every dog has its day.',
    'The squeaky wheel gets the grease.',
    'When life gives you lemons, make lemonade.',
    'Home is where the heart is.',
    'Life is like a box of chocolates.',
    # Famous public-domain lines
    'To be, or not to be, that is the question.',
    'All the world\'s a stage, and all the men and women merely players.',
    'I think, therefore I am.',
    'The quick brown fox jumps over the lazy dog.',
    'Four score and seven years ago our fathers brought forth on this continent a new nation.',
    'Ask not what your country can do for you, ask what you can do for your country.',
]

ASK = re.compile(r"(?i)^\s*(?:please\s+)?(?:can you\s+|could you\s+)?(?:compl[ie]te?|compete|finish|continue|end)"
                 r"(?:\s+(?:the|this|my))?(?:\s+(?:line|sentence|phrase|rhyme|poem|saying|proverb|quote|verse))?"
                 r"(?:\s+for me)?\s*[:,\-]?\s*(.+?)\s*$")
NEXT = re.compile(r"(?i)^\s*what comes (?:next|after)\s*[:,\-]?\s*(.+?)\s*$|^\s*(.+?)\s*[,:\-]?\s*what comes next\s*\??\s*$")


def norm(text):
    return ' '.join(re.findall(r"[a-z0-9']+", text.lower().replace('’', "'")))


def known(start):
    """The listed line that begins with these words, with the given start and the rest; None if none or several."""
    want = norm(start)
    if not want:
        return None
    hits = [line for line in LINES if norm(line).startswith(want) and norm(line) != want]
    lines = {norm(h): h for h in hits}
    if len(lines) != 1:
        return None
    line = next(iter(lines.values()))
    # Split the original line after as many words as were given.
    words = re.findall(r"\S+", line)
    cut = len(want.split())
    return ' '.join(words[:cut]), ' '.join(words[cut:])


def reply(text):
    asked = ASK.match(text) or NEXT.match(text)
    start = (asked.group(1) or asked.group(2) if asked and asked.lastindex else None) if asked else None
    start = start.strip(' "\'.…') if start else None
    if not start:
        if len(norm(text).split()) < 3 or '?' in text:
            return None
        start = text.strip(' "\'.…')
    found = known(start)
    if found:
        given, rest = found
        return dict(route='chat/complete-line', sources=[],
                    response=f'{given} **{rest}**',
                    details='Completed from CAEL\'s hand-written list of traditional rhymes, proverbs and sayings '
                            '(public domain). No neural model.')
    # "Continue the story about a dragon", "finish my essay": writing requests belong to the story/writing routes.
    if asked and not re.search(r'(?i)\b(?:story|tale|essay|letter|email|code|script|function|about|my (?:homework|work|task))\b', text):
        return dict(route='chat/complete-unknown', sources=[],
                    response="I don't know how that one goes, so I won't make it up. If it's a well-known rhyme, "
                             "proverb or quote, give me a few more words of it.",
                    details='No listed rhyme, proverb or saying starts with these words.')
    return None
