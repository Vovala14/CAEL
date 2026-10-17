"""Understand a picture request: subject plus the attributes the user asked for.

"two red cars on a beach, cartoon style" -> subject car, count 2, colour red,
style illustration, background beach. Whatever cannot be honoured is reported
back by the caller instead of being silently dropped.
"""
import re

COLOURS = {
    'red': (0.0, 'chromatic'), 'orange': (0.07, 'chromatic'), 'yellow': (0.15, 'chromatic'), 'gold': (0.12, 'chromatic'),
    'golden': (0.12, 'chromatic'), 'green': (0.33, 'chromatic'), 'teal': (0.48, 'chromatic'), 'cyan': (0.5, 'chromatic'),
    'blue': (0.62, 'chromatic'), 'navy': (0.64, 'dark'), 'purple': (0.78, 'chromatic'), 'violet': (0.76, 'chromatic'),
    'pink': (0.92, 'light'), 'brown': (0.07, 'dark'), 'black': (None, 'black'), 'white': (None, 'white'),
    'gray': (None, 'gray'), 'grey': (None, 'gray'), 'silver': (None, 'gray'),
}
STYLES = {  # training prompt styles: 0 studio photo, 1 side-view product photo, 2 flat illustration
    'illustration': 2, 'drawing': 2, 'drawn': 2, 'cartoon': 2, 'clipart': 2, 'clip art': 2, 'flat': 2, 'simple': 2,
    'vector': 2, 'sketch': 2, 'animated': 2, 'photo': 0, 'photograph': 0, 'realistic': 0, 'photorealistic': 0, 'real': 0,
    'side view': 1, 'from the side': 1, 'profile': 1,
}
NUMBERS = {'a': 1, 'an': 1, 'one': 1, 'single': 1, 'two': 2, 'pair of': 2, 'couple of': 2, 'three': 3, '2': 2, '3': 3}
SCENES = {'beach': 'beach', 'sea': 'beach', 'ocean': 'beach', 'shore': 'beach', 'forest': 'forest', 'woods': 'forest',
          'jungle': 'forest', 'city': 'city', 'street': 'city', 'town': 'city', 'mountain': 'mountain', 'mountains': 'mountain',
          'hills': 'mountain', 'waterfall': 'waterfall', 'castle': 'castle'}
PLAIN = re.compile(r'(?i)\b(?:on|against|with)\s+(?:a\s+)?(?:plain|white|blank|simple|empty)\s+background\b')


def parse(text, subject_words):
    """subject_words: {topic: [words]}. Returns a dict, or raises ValueError like the topic resolver."""
    lower = ' '.join(text.lower().replace('-', ' ').split())
    out = dict(colour=None, style=None, count=1, background=None, notes=[])

    # Background first, so "on a beach" is not read as the subject "beach".
    scene = re.search(r'\b(?:on|at|in|by|near)\s+(?:the\s+|a\s+)?(' + '|'.join(SCENES) + r')\b', lower)
    if scene:
        out['background'] = SCENES[scene[1]]
        lower = lower[:scene.start()] + ' ' + lower[scene.end():]
    elif PLAIN.search(lower):
        out['background'] = 'plain'

    for phrase, style in sorted(STYLES.items(), key=lambda kv: -len(kv[0])):
        if re.search(r'\b' + re.escape(phrase) + r'\b', lower):
            out['style'] = style
            break

    # The colour word must sit right before the subject (or before one adjective): "a red car", "a big blue whale".
    names = sorted(((word, topic) for topic, words in subject_words.items() for word in words), key=lambda kv: -len(kv[0]))
    subject = None
    for word, topic in names:
        match = re.search(r'\b' + re.escape(word) + r'\b', lower)
        if not match:
            continue
        before = lower[:match.start()].split()
        colour_here = next((w for w in before[-2:] if w in COLOURS), None)
        # "orange cat": orange is the colour, not the fruit, when another subject word follows it directly.
        following = lower[match.end():].split()[:1]
        if topic == 'orange' and following and any(following[0] == w for w, t in names if t != 'orange'):
            continue
        subject = topic
        out['colour'] = colour_here
        number = next((NUMBERS[w] for w in before[-3:] if w in NUMBERS), None)
        multi = re.search(r'\b(two|three|2|3|pair of|couple of)\b', ' '.join(before[-4:]))
        out['count'] = NUMBERS[multi[1]] if multi else (number or 1)
        break
    if subject is None:
        raise ValueError('This subject is not in the trained image vocabulary')
    out['subject'] = subject
    if re.search(r'\b(?:four|five|six|many|several|lots of|\d{2,}|[4-9])\b', lower):
        out['notes'].append('I can draw at most three of something at once, so I drew one.')
    return out
