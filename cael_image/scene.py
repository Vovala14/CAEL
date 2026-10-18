"""Reasoning about picture requests: several objects, how they relate, and follow-up edits.

"a big red car to the left of a small tree on a beach" becomes a scene:
    objects   [car (red, big), tree (small)]
    relations [car left-of tree]
    background beach
The layout is solved like the 2-D position puzzles in the text reasoner: left/right
constraints give a left-to-right order (contradictions are reported, not drawn),
on/above/under stack objects in one column, and sizes follow real-world sizes from
concepts.FACTS, so an elephant is drawn larger than a cat. Subjects can be named
indirectly ("the animal that says moo", "a poodle"); every substitution is explained.
Follow-ups ("make it blue", "add a cow", "remove the dog", "put them in a forest")
edit the scene that the conversation built. Authored algorithms; no neural network.
"""
import copy
import re

import numpy as np
from PIL import Image, ImageFilter

from . import concepts
from .request import COLOURS, STYLES

NUMBER = {'a': 1, 'an': 1, 'one': 1, 'single': 1, 'two': 2, 'pair of': 2, 'couple of': 2, 'three': 3, 'four': 4, 'five': 5,
          'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'several': 3, 'some': 2, 'many': 4, 'lots of': 4}
SIZE_WORDS = {'tiny': .6, 'little': .75, 'small': .75, 'baby': .75, 'big': 1.3, 'large': 1.3, 'huge': 1.5, 'giant': 1.5, 'enormous': 1.5}
MAX_EACH, MAX_TOTAL = 3, 6
# Relation phrases between two objects, longest first.
RELATIONS = [
    (r'to the left of|on the left of|left of', 'left'), (r'to the right of|on the right of|right of', 'right'),
    (r'on top of|sitting on|standing on|lying on|perched on|riding|on', 'on'),
    (r'flying over|flying above|hovering over|above|over', 'above'),
    (r'underneath|beneath|under|below', 'below'), (r'in front of', 'front'), (r'behind', 'behind'),
    (r'between', 'between'), (r'next to|beside|besides|alongside|near|close to|by|with|and|holding|chasing|facing', 'next'),
]
ANCHORS = [(r'on the left|at the left', 'left'), (r'on the right|at the right', 'right'), (r'in the middle|in the centre|in the center', 'middle'),
           (r'in the sky|flying|in the air', 'sky')]
UNKNOWN_PLACES = ('desert', 'snow', 'field', 'meadow', 'park', 'garden', 'room', 'kitchen', 'bedroom', 'river', 'lake', 'moon', 'space',
                  'farm', 'zoo', 'island', 'cave', 'arctic', 'savanna', 'savannah', 'pond', 'playground', 'school', 'office', 'house',
                  'water', 'ocean', 'sea', 'underwater', 'night', 'rain', 'sunset', 'jungle', 'hills', 'street', 'town', 'woods')
# Background words -> background topics in order of preference (the first one the model can draw is used).
SCENE_WORDS = {'beach': ('beach',), 'sea': ('ocean', 'beach'), 'ocean': ('ocean', 'beach'), 'water': ('ocean', 'beach'),
               'underwater': ('ocean',), 'shore': ('beach',), 'seaside': ('beach',), 'forest': ('forest',), 'woods': ('forest',),
               'jungle': ('forest',), 'city': ('city',), 'street': ('city',), 'town': ('city',), 'mountain': ('mountain',),
               'mountains': ('mountain',), 'hills': ('mountain', 'field'), 'waterfall': ('waterfall',), 'volcano': ('volcano',),
               'castle': ('castle',), 'desert': ('desert',), 'dunes': ('desert',), 'snow': ('snow',), 'winter': ('snow',),
               'park': ('park', 'field'), 'garden': ('park', 'field'), 'field': ('field', 'park'), 'meadow': ('field', 'park'),
               'grass': ('field', 'park'), 'farm': ('field',), 'room': ('room',), 'living room': ('room',), 'house': ('room',),
               'sky': ('sky',), 'clouds': ('sky',)}
DEFAULT_SCENES = ('beach', 'forest', 'city', 'mountain', 'waterfall', 'volcano', 'castle')
DESCRIPTION = re.compile(
    r'\b(?:(?:a|an|the|some|any)\s+)?(?:\w+\s+){0,2}?(?:animal|creature|pet|fruit|vegetable|food|snack|dessert|treat|vehicle|plant|'
    r'building|instrument|toy|furniture|device|gadget|insect|bug|thing|object)s?\b(?:\s+(?:that|which|who|with|you|from|i|people)\b[^,]*?)?'
    r'(?=$|,|\s+and\s+(?:a|an|the|two|three|some)\b|\s+(?:next to|beside|to the left|to the right|left of|right of|above|over|below|'
    r'under|on top of|in front of|behind|between|near|on|in|at)\s)'
    r'|\bsomething\b[^,]*?(?=$|,|\s+(?:next to|beside|to the left|to the right|on|in|at)\s)'
    r"|\b(?:the )?(?:king of the jungle|man's best friend|mans best friend)\b")


class SceneError(ValueError):
    """A request about a picture that cannot be drawn, with the reason in words."""


def words_of(topic):
    return topic.replace('_', ' ')


def article(word):
    return ('an ' if word[0] in 'aeiou' else 'a ') + word


def because(reasons):
    out = []
    for r in reasons:
        if r.startswith('not: '):
            r = r[5:].replace('it can ', "it can't ").replace('it is ', "it isn't ").replace('it has ', "it doesn't have ").replace('you can ', "you can't ")
        out.append(r)
    return ' and '.join(out)


# ---------------------------------------------------------------- parsing

def vocabulary(aliases, topics):
    """word -> (topic, how): exact names, kinds of a thing ('poodle' is a dog), and nearest stand-ins."""
    words = {}
    for topic in topics:
        for word in aliases.get(topic, [words_of(topic)]) + [words_of(topic)]:
            words.setdefault(word.lower(), (topic, 'name'))
        name = words_of(topic)
        for plural in (name + 's', name + 'es', name[:-1] + 'ies' if name.endswith('y') else None):
            if plural:
                words.setdefault(plural, (topic, 'name'))
    for topic, kinds in concepts.KIND_OF.items():
        if topic in topics:
            for word in kinds.split():
                for form in (word, word + 's', word + 'es'):
                    words.setdefault(form, (topic, 'kind'))
    for word, topic in concepts.SIMILAR.items():
        if topic in topics:
            for form in (word, word + 's'):
                words.setdefault(form, (topic, 'similar'))
    if 'mouse' not in topics:
        words.pop('mouse', None)      # "mouse" alone means the animal, not the computer mouse
    return words


def clean(text):
    lower = ' '.join(text.lower().replace('-', ' ').replace('’', "'").split())
    lower = re.sub(r"^(?:please\s+)?(?:(?:can|could|would|will) you\s+)?(?:please\s+)?"
                   r"(?:draw|paint|sketch|render|make|create|generate|show|give)(?:\s+me)?(?:\s+(?:a|an|the|some))?"
                   r"(?:\s+(?:small\s+)?(?:image|picture|photo|photograph|drawing|illustration|pic|painting|sketch)s?\s+(?:of|with|showing))?\s+", '', lower)
    return lower.strip(' .!?')


def scene_for(word, topics):
    """The background topic a place word means, or None when none of its choices can be drawn."""
    available = set(topics) if topics is not None else set(DEFAULT_SCENES)
    return next((t for t in SCENE_WORDS.get(word, ()) if t in available), None)


def find_background(lower, notes, topics=None):
    """'... on a beach' -> ('beach', text without it); places that cannot be drawn are reported."""
    words = sorted((w for w in SCENE_WORDS if w != 'sky'), key=len, reverse=True)   # "in the sky" places an object, see ANCHORS
    match = re.search(r'\b(?:on|at|in|by|near|with|against|under)\s+(?:the\s+|a\s+|an\s+)?(' + '|'.join(words) + r')(?:\s+background)?\b(?!\s+(?:with|and))\s*', lower)
    if match and not re.match(r'\s*(?:of)\b', lower[match.end():]):
        topic = scene_for(match[1], topics)
        if topic:
            return topic, lower[:match.start()] + ' ' + lower[match.end():]
        notes.append(f"I can't draw {article(match[1])} background yet, so I used a plain one.")
        return 'plain', lower[:match.start()] + ' ' + lower[match.end():]
    match = re.search(r'\b(?:with\s+)?(?:a\s+)?(' + '|'.join(sorted(SCENE_WORDS, key=len, reverse=True)) + r')\s+background\b', lower)
    if match:
        topic = scene_for(match[1], topics)
        if topic:
            return topic, lower[:match.start()] + lower[match.end():]
        notes.append(f"I can't draw {article(match[1])} background yet, so I used a plain one.")
        return 'plain', lower[:match.start()] + lower[match.end():]
    if re.search(r'\b(?:on|against|with)\s+(?:a\s+)?(?:plain|white|blank|simple|empty)\s+background\b', lower):
        return 'plain', re.sub(r'\b(?:on|against|with)\s+(?:a\s+)?(?:plain|white|blank|simple|empty)\s+background\b', '', lower)
    unknown = [w for w in UNKNOWN_PLACES if w not in SCENE_WORDS]
    match = re.search(r'\b(?:in|on|at|under)\s+(?:the\s+|a\s+|an\s+)?(' + '|'.join(unknown) + r')\b\s*$', lower)
    if match:
        notes.append(f"I can't draw {article(match[1])} background yet, so I used a plain one.")
        return 'plain', lower[:match.start()]
    return None, lower


def mentions(lower, vocab, topics, seed, notes):
    """Object mentions in order: dicts with span, topic and the reasoning that chose it."""
    found = []
    for match in DESCRIPTION.finditer(lower):
        phrase = match[0].strip()
        if not phrase or any(re.search(r'\b' + re.escape(w) + r'\b', phrase) for w in vocab if vocab[w][1] == 'name' and len(w) > 2
                             and w not in ('bird',)):
            continue  # "a red car" contains a real subject name; the description is not needed
        matches, reasons = concepts.describe(phrase, topics)
        if not reasons:
            continue
        if not matches:
            raise SceneError(f'I could not think of anything I can draw that fits "{phrase}".')
        topic = matches[seed % len(matches)] if len(matches) > 1 else matches[0]
        others = [words_of(t) for t in matches if t != topic]
        why = f'For "{phrase}" I drew {article(words_of(topic))}: {because(reasons)}.'
        if others:
            why += ' Other fits: ' + ', '.join(others[:5]) + '.'
        found.append(dict(start=match.start(), end=match.end(), topic=topic, asked=phrase, why=why, described=True))
    taken = [(m['start'], m['end']) for m in found]
    for word in sorted(vocab, key=len, reverse=True):
        for match in re.finditer(r'\b' + re.escape(word) + r'\b', lower):
            if any(a < match.end() and match.start() < b for a, b in taken):
                continue
            topic, how = vocab[word]
            # "orange cat": orange is the colour when another subject follows directly.
            if topic == 'orange':
                following = lower[match.end():].split()[:1]
                if following and following[0] in vocab and vocab[following[0]][0] != 'orange':
                    continue
            why = None
            if how == 'kind':
                why = f'{article(word.rstrip("s")).capitalize()} is a kind of {words_of(topic)}, so I drew {article(words_of(topic))}.'
            elif how == 'similar':
                why = f"I can't draw {article(word.rstrip('s'))} yet, so I drew the closest thing I can: {article(words_of(topic))}."
            found.append(dict(start=match.start(), end=match.end(), topic=topic, asked=word, why=why, described=False))
            taken.append((match.start(), match.end()))
    if 'mouse' not in topics and re.search(r'\bmouse\b|\bmice\b', lower) and not any(m['topic'] == 'computer_mouse' for m in found):
        notes.append("I can't draw a mouse (the animal) yet, so I left it out.")
    return sorted(found, key=lambda m: m['start'])


def attributes(lower, mention, previous_end, notes):
    """Count, colour, size and excluded colours from the words around one mention."""
    before = lower[previous_end:mention['start']].split()[-4:]
    after = lower[mention['end']:].split()[:5]
    joined = ' '.join(before)
    count = 1
    for phrase, value in sorted(NUMBER.items(), key=lambda kv: -len(kv[0])):
        if re.search(r'(?:^|\s)' + re.escape(phrase) + r'(?:\s|$)', ' ' + joined + ' '):
            count = value
            break
    digits = re.search(r'\b(\d+)\s*$', joined)
    if digits:
        count = int(digits[1])
    if count == 1 and mention['asked'].endswith('s') and mention['asked'] not in ('glasses', 'grapes', 'headphones', 'scissors', 'bus') \
            and not mention['described'] and re.search(r'\b(?:some|many|several)\b', joined):
        count = 2
    if count > MAX_EACH:
        notes.append(f'I can draw at most {MAX_EACH} of one thing in a picture, so I drew {MAX_EACH} {words_of(mention["topic"])}s.')
        count = MAX_EACH
    colour = next((w for w in reversed(before[-3:]) if w in COLOURS), None)
    tail = ' '.join(after)
    later = re.match(r'(?:that is|which is|that are|in|coloured|colored|painted)\s+(\w+)', tail)
    if colour is None and later and later[1] in COLOURS:
        colour = later[1]
    excluded = [w for w in re.findall(r'\b(?:not|non|no)\s+(\w+)', ' '.join(before + after[:4])) if w in COLOURS]
    if colour in excluded:
        colour = None
    size = 1.0
    for word in before[-3:]:
        size *= SIZE_WORDS.get(word, 1.0)
    return dict(count=count, colour=colour, not_colours=excluded, size=size)


def relation_between(gap):
    gap = ' ' + gap.strip() + ' '
    for pattern, name in RELATIONS:
        if re.search(r'\s(?:' + pattern + r')\s', gap):
            return name
    return 'next'


def parse(text, aliases, topics, seed=0):
    """A scene dict from a picture request, or raises SceneError (or ValueError when no subject is found)."""
    notes = []
    lower = clean(text)
    style = None
    for phrase, value in sorted(STYLES.items(), key=lambda kv: -len(kv[0])):
        if re.search(r'\b' + re.escape(phrase) + r'\b', lower):
            style = value
            lower = re.sub(r',?\s*(?:in\s+(?:a\s+)?)?\b' + re.escape(phrase) + r'\b(?:\s+style)?', ' ', lower)
            break
    background, lower = find_background(lower, notes, topics)
    vocab = vocabulary(aliases, topics)
    found = mentions(lower, vocab, topics, seed, notes)
    if not found:
        raise ValueError('This subject is not in the trained image vocabulary')
    objects, relations = [], []
    slot = []                           # mention -> object index ("the dog" refers back to a dog already mentioned)
    for index, m in enumerate(found):
        previous_end = found[index - 1]['end'] if index else 0
        anchor = None
        following = lower[m['end']:found[index + 1]['start'] if index + 1 < len(found) else len(lower)]
        for pattern, name in ANCHORS:
            if re.search(r'^\W*(?:\w+\s+){0,2}?(?:' + pattern + r')\b', following):
                anchor = name
        earlier = [k for k, o in enumerate(objects) if o['topic'] == m['topic']]
        if earlier and re.search(r'\b(?:the|that|this)\s+$', lower[previous_end:m['start']]):
            slot.append(earlier[-1])
            if anchor:
                objects[earlier[-1]]['anchor'] = anchor
            continue
        attrs = attributes(lower, m, previous_end, notes)
        slot.append(len(objects))
        objects.append(dict(topic=m['topic'], asked=m['asked'], why=m['why'], anchor=anchor, **attrs))
    for index in range(1, len(found)):
        gap = lower[found[index - 1]['end']:found[index]['start']]
        for pattern, _ in ANCHORS[:3]:
            gap = re.sub(r'\b(?:' + pattern + r')\b', ' ', gap)
        name = relation_between(gap)
        a, b = slot[index - 1], slot[index]
        if a == b:
            continue
        if name == 'between' and index + 1 < len(found):
            relations.append((a, 'between', b, slot[index + 1]))
        elif name != 'next' and not (relations and relations[-1][1] == 'between' and relations[-1][3] == b):
            relations.append((a, name, b))
    total = sum(o['count'] for o in objects)
    while total > MAX_TOTAL:
        biggest = max(objects, key=lambda o: o['count'])
        biggest['count'] -= 1
        total -= 1
    return dict(objects=objects, relations=relations, background=background, style=style, notes=notes)


def simple(scene):
    """One object, no relations: the single-subject drawing path handles it (and keeps its quality)."""
    return len(scene['objects']) == 1 and not scene['relations'] and not scene['objects'][0]['anchor'] \
        and not scene['objects'][0]['not_colours']


# ---------------------------------------------------------------- follow-up edits

EDIT = re.compile(r"(?i)^\s*(?:now\s+|and\s+|ok\s+|okay\s+|please\s+|can you\s+|could you\s+)*"
                  r"(?:make|turn|change|colou?r|paint|add|put|place|move|remove|delete|take away|take out|get rid of|replace|swap|"
                  r"draw (?:it|them|that) again|again|another|one more|same|without|with|bigger|smaller|larger)\b")


def is_edit(text):
    return bool(EDIT.search(text)) and len(text) < 200


def target(scene, lower, vocab):
    """Indices of the objects a follow-up refers to ('it' = the last one, 'them' = all)."""
    hits = []
    for index, obj in enumerate(scene['objects']):
        names = [w for w, (t, _) in vocab.items() if t == obj['topic']] + [obj['asked']]
        if any(re.search(r'\b' + re.escape(n) + r'\b', lower) for n in names):
            hits.append(index)
    if hits:
        return hits
    if re.search(r'\b(?:them|they|all|both|everything)\b', lower):
        return list(range(len(scene['objects'])))
    return [len(scene['objects']) - 1]


def edit(scene, text, aliases, topics, seed=0):
    """Apply a follow-up to a scene; 'make the cat orange and add a dog' is two edits, applied in order."""
    parts = re.split(r'(?i)\s*(?:,\s*)?\b(?:and|then|and then|also)\s+(?=(?:make|turn|change|colou?r|paint|add|put|place|move|remove|'
                     r'delete|take|get rid|replace|swap)\b)', text.strip())
    notes, changes = [], []
    for part in parts:
        scene, change = edit_one(scene, part, aliases, topics, seed)
        notes += scene['notes']
        changes.append(change)
    scene['notes'] = list(dict.fromkeys(notes))
    return scene, ' '.join(changes)


def edit_one(scene, text, aliases, topics, seed=0):
    """Apply one follow-up to a scene; returns (new scene, what changed) or raises SceneError."""
    scene = copy.deepcopy(scene)
    scene['notes'] = []
    lower = ' '.join(text.lower().replace('-', ' ').split()).strip(' .!?')
    vocab = vocabulary(aliases, topics)
    changes = []
    if re.search(r'\b(?:again|another|one more|same)\b', lower) and not re.search(r'\b(?:add|with|but)\b', lower):
        return scene, 'Drew the same scene again.'
    replace = re.search(r'\b(?:replace|swap)\s+(?:the\s+)?(.+?)\s+(?:with|for)\s+(.+)$|\b(?:change|turn)\s+(?:the\s+)?(.+?)\s+(?:into|to)\s+(?:an?\s+)?(.+)$', lower)
    if replace:
        old, new = (replace[1], replace[2]) if replace[1] else (replace[3], replace[4])
        if not any(w in COLOURS for w in new.split()) and not re.search(r'\b(?:background|cartoon|photo|drawing|illustration)\b', new):
            found = mentions(clean('draw ' + new), vocab, topics, seed, scene['notes'])
            if found:
                index = target(scene, old, vocab)[0]
                before = scene['objects'][index]['topic']
                scene['objects'][index].update(topic=found[0]['topic'], asked=found[0]['asked'], why=found[0]['why'], colour=None)
                return scene, f'Replaced the {words_of(before)} with {article(words_of(found[0]["topic"]))}.'
    removing = re.search(r'\b(?:remove|delete|take away|take out|get rid of|without)\s+(?:the\s+)?(.+)$', lower)
    if removing:
        gone = [i for i in target(scene, removing[1], vocab)]
        if len(gone) >= len(scene['objects']):
            raise SceneError('That would leave the picture empty. Ask for a new picture instead.')
        names = [words_of(scene['objects'][i]['topic']) for i in gone]
        keep = [i for i in range(len(scene['objects'])) if i not in gone]
        renumber = {old: new for new, old in enumerate(keep)}
        scene['objects'] = [scene['objects'][i] for i in keep]
        scene['relations'] = [tuple(renumber[x] if isinstance(x, int) else x for x in r) for r in scene['relations']
                              if all(x in renumber for x in r if isinstance(x, int))]
        return scene, 'Removed the ' + ' and the '.join(names) + '.'
    adding = re.search(r'\b(?:add|put in|include|with)\s+(.+)$', lower)
    if adding and not re.search(r'^(?:a|an|the)?\s*(?:' + '|'.join(SCENE_WORDS) + r')\s+background', adding[1]) \
            and not re.fullmatch(r'(?:a|an|the)?\s*(?:' + '|'.join(SCENE_WORDS) + r')', adding[1].strip()):
        # "add a cow next to the horse": new objects before the relation, an existing one after it.
        rest, relation, existing = adding[1], None, None
        for pattern, name in RELATIONS[:-1] + [(r'next to|beside|alongside|near|close to|by', 'next')]:
            m = re.search(r'\s(?:' + pattern + r')\s+(?:the\s+)?(.+)$', ' ' + rest)
            if m and m[1].split()[0] not in ('a', 'an'):
                hits = target(dict(objects=scene['objects']), m[1], vocab)
                if any(re.search(r'\b' + re.escape(words_of(scene['objects'][i]['topic'])) + r'\b', m[1]) for i in hits):
                    relation, existing, rest = name, hits[0], rest[:m.start() - 1]
                    break
        addition = parse('draw ' + rest, aliases, topics, seed)
        offset = len(scene['objects'])
        scene['objects'] += addition['objects']
        scene['relations'] += [tuple(x + offset if isinstance(x, int) else x for x in r) for r in addition['relations']]
        scene['notes'] += addition['notes']
        if relation and relation not in ('between', 'next'):
            scene['relations'].append((offset, relation, existing))
        elif relation == 'next' and existing != offset - 1:
            # Beside an earlier object: move the new one right after it in the left-to-right order.
            scene['relations'].append((offset, 'right', existing))
        if addition['background']:
            scene['background'] = addition['background']
        return scene, 'Added ' + ', '.join(article(words_of(o['topic'])) if o['count'] == 1 else f"{o['count']} {words_of(o['topic'])}s"
                                            for o in addition['objects']) + '.'
    background, rest = find_background(lower, scene['notes'], topics)
    if background or re.search(r'\bbackground\b', lower):
        scene['background'] = background or 'plain'
        changes.append('background: ' + (scene['background']))
    for phrase, value in sorted(STYLES.items(), key=lambda kv: -len(kv[0])):
        if re.search(r'\b' + re.escape(phrase) + r'\b', lower):
            scene['style'] = value
            changes.append('style: ' + phrase)
            break
    chosen = target(scene, lower, vocab)
    colour = next((w for w in lower.split() if w in COLOURS), None)
    if colour and re.search(r'\b(?:make|turn|change|colou?r|paint|it|them|the)\b', lower):
        for i in chosen:
            scene['objects'][i]['colour'] = colour
            scene['objects'][i]['not_colours'] = []
        changes.append(colour)
    count = re.search(r'\b(one|two|three|four|five|2|3|4|5)\b(?:\s+of\s+(?:them|it))?', lower)
    if count and re.search(r'\b(?:make|now|want|draw|show|them|it|of)\b', lower) and not colour:
        value = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}.get(count[1]) or int(count[1])
        for i in chosen:
            scene['objects'][i]['count'] = min(value, MAX_EACH)
        changes.append(f'{min(value, MAX_EACH)} of them')
        if value > MAX_EACH:
            scene['notes'].append(f'I can draw at most {MAX_EACH} of one thing in a picture.')
    if re.search(r'\b(?:bigger|larger|huge|giant)\b', lower):
        for i in chosen:
            scene['objects'][i]['size'] *= 1.35
        changes.append('bigger')
    if re.search(r'\b(?:smaller|tiny|little)\b', lower):
        for i in chosen:
            scene['objects'][i]['size'] /= 1.35
        changes.append('smaller')
    moved = re.search(r'\b(?:move|put|place)\s+(?:the\s+)?(.+?)\s+(' + '|'.join(p for p, _ in RELATIONS[:-2]) + r')\s+(?:the\s+)?(.+)$', lower)
    named = moved and any(re.search(r'\b' + re.escape(w) + r'\b', moved[3]) for w, (t, _) in vocab.items()
                          if any(o['topic'] == t for o in scene['objects']))
    if moved and named and not background:
        a, b = target(scene, moved[1], vocab)[0], target(scene, moved[3], vocab)[0]
        if a != b:
            name = relation_between(' ' + moved[2] + ' ')
            scene['relations'] = [r for r in scene['relations'] if not (len(r) == 3 and {r[0], r[2]} == {a, b})] + [(a, name, b)]
            changes.append(f'{words_of(scene["objects"][a]["topic"])} {name} {words_of(scene["objects"][b]["topic"])}')
    elif re.search(r'\bswap\b', lower) and len(scene['objects']) >= 2:
        scene['relations'] = [(r[2], r[1], r[0]) if len(r) == 3 and r[1] in ('left', 'right') else r for r in scene['relations']]
        if not any(r[1] in ('left', 'right') for r in scene['relations']):
            scene['objects'] = scene['objects'][::-1]
        changes.append('swapped places')
    if not changes:
        raise SceneError('I did not understand how to change the picture.')
    return scene, 'Changed: ' + ', '.join(changes) + '.'


# ---------------------------------------------------------------- layout

def layout(scene, canvas):
    """Boxes (x, y_bottom, height, depth) for every object instance; adds notes for conflicts."""
    objects, notes = scene['objects'], scene['notes']
    n = len(objects)
    column = list(range(n))            # stacked objects share a column

    def root(i):
        while column[i] != i:
            i = column[i]
        return i
    vertical = {}                       # object -> (base object, relation)
    for r in scene['relations']:
        if r[1] in ('on', 'above', 'below', 'front', 'behind'):
            a, b = r[0], r[2]
            if r[1] == 'below':
                a, b, name = b, a, 'above'
            else:
                name = r[1]
            if a in vertical or root(a) == root(b):
                notes.append(f'I could not also put the {words_of(objects[r[0]]["topic"])} {r[1]} the {words_of(objects[r[2]]["topic"])}; it conflicts with the rest.')
                continue
            vertical[a] = (b, name)
            column[root(a)] = root(b)
    columns = sorted({root(i) for i in range(n)})
    # Left-to-right order of columns from left/right/between, keeping contradictions out.
    edges = set()

    def reachable(a, b):
        seen, todo = set(), [a]
        while todo:
            x = todo.pop()
            if x == b:
                return True
            seen.add(x)
            todo += [y for (p, y) in edges if p == x and y not in seen]
        return False
    pairs = []
    for r in scene['relations']:
        if r[1] == 'left':
            pairs.append(((r[0], r[2]), r))
        elif r[1] == 'right':
            pairs.append(((r[2], r[0]), r))
        elif r[1] == 'between':
            pairs += [((r[2], r[0]), r), ((r[0], r[3]), r)]
    for (a, b), r in pairs:
        a, b = root(a), root(b)
        if a == b:
            continue
        if reachable(b, a):
            names = [words_of(objects[i]['topic']) for i in (r[0], r[2])]
            notes.append(f'Your placements contradict each other, so I ignored "{names[0]} {r[1]} of {names[1]}".')
            continue
        edges.add((a, b))
    rank = {'left': 0, 'middle': 1, None: 1, 'sky': 1, 'right': 2}
    order, placed = [], set()
    while len(order) < len(columns):
        ready = [c for c in columns if c not in placed and not any(b == c and a not in placed for a, b in edges)]
        if not ready:
            ready = [c for c in columns if c not in placed]
        ready.sort(key=lambda c: (rank[objects[c]['anchor']], c))
        order.append(ready[0])
        placed.add(ready[0])
    # Sizes: square root of real size relative to the largest, so a cat next to an elephant is still visible.
    biggest = max(concepts.size(o['topic']) for o in objects)
    relative = [max(0.22, (concepts.size(o['topic']) / biggest) ** 0.5) * o['size'] for o in objects]
    # Width of each column = widest member (all instances side by side), height = stack.
    def width(i):
        return relative[i] * (objects[i]['count'] * 0.85 + 0.15)
    members = {c: [i for i in range(n) if root(i) == c] for c in columns}
    col_width = {c: max(width(i) for i in members[c]) for c in columns}
    col_height = {}
    for c in columns:
        height = 0
        for i in members[c]:
            name = vertical.get(i, (None, None))[1]
            height += relative[i] * (0.9 if name in ('on', 'above') else (0 if name in ('front', 'behind') else 1))
        col_height[c] = max(height, max(relative[i] for i in members[c]))
    skyward = [i for i in range(n) if objects[i]['anchor'] == 'sky' or (concepts.flies(objects[i]['topic']) and i not in vertical
               and not any(i in r[2:] for r in scene['relations'] if r[1] in ('on', 'above', 'below')) and n > 1
               and objects[i]['anchor'] is None and any(not concepts.flies(o['topic']) for o in objects))]
    total_width = sum(col_width.values()) * 1.08
    unit = min(canvas * 0.92 / total_width, canvas * 0.86 / max(col_height[c] + (0.35 if c in skyward else 0) for c in columns), canvas * 0.72)
    ground = canvas * 0.95
    boxes = {}
    x = (canvas - total_width * unit) / 2
    for c in order:
        centre = x + col_width[c] * unit * 1.04 / 2
        x += col_width[c] * unit * 1.08
        pending = sorted(members[c], key=lambda i: (i in vertical, i))
        for i in pending:
            h = relative[i] * unit
            if i in vertical:
                base, name = vertical[i]
                bx, by, bh, bd = boxes[base]
                if name == 'on':
                    boxes[i] = (bx, by - bh * 0.82, h, bd + 1)
                elif name == 'above':
                    boxes[i] = (bx, by - bh - h * 0.25, h, bd + 1)
                elif name == 'front':
                    boxes[i] = (bx + bh * 0.15, by + canvas * 0.02, h, bd + 2)
                else:   # behind
                    boxes[i] = (bx - bh * 0.15, by - canvas * 0.06, h * 0.85, bd - 2)
            else:
                bottom = ground - (canvas * 0.45 if i in skyward else 0)
                boxes[i] = (centre, bottom, h, 0)
    # Keep everything inside the canvas.
    for i, (bx, by, h, d) in boxes.items():
        top = by - h
        if top < canvas * 0.02:
            by += canvas * 0.02 - top
        boxes[i] = (bx, by, h, d)
    return boxes, order, members


# ---------------------------------------------------------------- drawing

def crop(image, mask):
    rows, cols = np.where(mask > 0.3)
    if len(rows) == 0:
        return image, mask
    y0, y1, x0, x1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    return image[y0:y1, x0:x1], mask[y0:y1, x0:x1]


def paste(canvas, image, mask, centre_x, bottom, height):
    h = max(4, int(round(height)))
    w = max(4, int(round(image.shape[1] * h / image.shape[0])))
    obj = np.asarray(Image.fromarray(image).resize((w, h), Image.Resampling.LANCZOS), np.float32)
    alpha = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).resize((w, h), Image.Resampling.LANCZOS)
                       .filter(ImageFilter.GaussianBlur(0.6)), np.float32)[..., None] / 255
    size = canvas.shape[0]
    x0, y0 = int(round(centre_x - w / 2)), int(round(bottom - h))
    sx0, sy0 = max(0, -x0), max(0, -y0)
    ex, ey = min(w, size - x0), min(h, size - y0)
    if ex <= sx0 or ey <= sy0:
        return
    region = canvas[y0 + sy0:y0 + ey, x0 + sx0:x0 + ex]
    a = alpha[sy0:ey, sx0:ex]
    canvas[y0 + sy0:y0 + ey, x0 + sx0:x0 + ex] = region * (1 - a) + obj[sy0:ey, sx0:ex] * a


def dominant_colour(image, mask):
    """The named colour closest to the object's average saturated hue (or None for grey-ish objects)."""
    from .compose import rgb_to_hsv
    hsv = rgb_to_hsv(image.astype(np.float32) / 255)
    keep = (mask > 0.5) & (hsv[..., 1] > 0.3) & (hsv[..., 2] > 0.2)
    if keep.mean() < 0.15:
        return None
    hue = hsv[..., 0][keep]
    angle = np.angle(np.exp(2j * np.pi * hue).mean()) / (2 * np.pi) % 1
    named = [(abs((angle - h + 0.5) % 1 - 0.5), name) for name, (h, kind) in COLOURS.items() if h is not None and kind == 'chromatic']
    return min(named)[1]


def render(model, scene, n=2, seed=0, settings=None):
    """Draw the scene n times. Returns (uint8 images n x S x S x 3, info)."""
    from .compose import object_mask, recolour
    from .draw import STYLE_NAMES, donor_background
    settings = dict(settings or {})
    size = model.size
    style = scene['style']
    notes = scene['notes']
    for obj in scene['objects']:
        if style is not None and not (model.styles(obj['topic']) == style).sum() >= 2:
            notes.append(f'I have no {STYLE_NAMES[style]} examples of {words_of(obj["topic"])}, so its style may differ.')
    background = scene['background']
    if background not in (None, 'plain') and background not in model.topics:
        notes.append(f"I can't draw {article(background)} background yet, so I used a plain one.")
        background = 'plain'
    boxes, order, members = layout(scene, size)
    pictures, reports = [], []
    for picture in range(n):
        picture_seed = seed * 7 + picture * 101
        cutouts, picture_reports = {}, []
        for index, obj in enumerate(scene['objects']):
            own_style = style if style is not None and (model.styles(obj['topic']) == style).sum() >= 2 else None
            images, report, masks = model.generate(obj['topic'], n=obj['count'], seed=picture_seed + index * 31, style=own_style,
                                                   return_masks=True, **settings)
            picture_reports += [dict(r, topic=obj['topic']) for r in report]
            items = []
            for image, mask in zip(images, masks):
                if mask is None or not 0.04 <= float((mask > 0.5).mean()) <= 0.9:
                    mask = object_mask(image)
                if mask is None:
                    yy, xx = np.mgrid[:size, :size] / (size - 1) - 0.5
                    mask = np.clip(1.4 - 3.2 * np.sqrt(xx ** 2 + yy ** 2), 0, 1).astype(np.float32)
                    notes.append(f'I could not cut the {words_of(obj["topic"])} out cleanly, so its edges are soft.')
                colour = obj['colour']
                if not colour and obj['not_colours'] and dominant_colour(image, mask) in obj['not_colours']:
                    colour = next(c for c in ('blue', 'green', 'white', 'black', 'yellow', 'red') if c not in obj['not_colours'])
                    notes.append(f'The {words_of(obj["topic"])} came out {dominant_colour(image, mask)}, which you did not want, so I made it {colour}.')
                if colour:
                    image = recolour(image, mask, colour)
                items.append(crop(image, mask))
            cutouts[index] = items
        if background is None and any(o['anchor'] == 'sky' for o in scene['objects']) and 'sky' in model.topics:
            background = 'sky'          # "a bird in the sky": the sky topic is the background
        if background in (None, 'plain') and any(o['anchor'] == 'sky' for o in scene['objects']) and background != 'plain':
            # "in the sky": a plain sky gradient instead of the studio backdrop.
            v = np.linspace(0, 1, size)[:, None, None]
            canvas = np.broadcast_to((1 - v) * np.array([110, 165, 225]) + v * np.array([200, 225, 245]), (size, size, 3)).astype(np.float32).copy()
        elif background in (None, 'plain'):
            first = next(r for r in picture_reports if r['topic'] == scene['objects'][0]['topic'])
            canvas = np.tile(donor_background(model, scene['objects'][0]['topic'], first['donors']).astype(np.float32), (size, size, 1))
        else:
            scenery, scene_report = model.generate(background, n=1, seed=picture_seed + 997, **settings)
            canvas = scenery[0].astype(np.float32)
            picture_reports += [dict(r, topic=background) for r in scene_report]
        # Far things first: by depth, then from the back of the picture to the front.
        for index in sorted(boxes, key=lambda i: (boxes[i][3], boxes[i][1])):
            cx, bottom, height, _ = boxes[index]
            items = cutouts[index]
            spread = height * 0.85
            for k, (image, mask) in enumerate(items):
                offset = (k - (len(items) - 1) / 2) * spread
                paste(canvas, image, mask, cx + offset, bottom - k % 2 * height * 0.03, height * (1 - 0.04 * (k % 2)))
        pictures.append(np.clip(canvas, 0, 255).astype(np.uint8))
        reports.append(picture_reports)
    return np.stack(pictures), dict(subject=summary(scene, order, members), notes=list(dict.fromkeys(notes)), sources=reports,
                                    scene=scene)


def phrase(obj):
    name = words_of(obj['topic'])
    if obj['colour']:
        name = obj['colour'] + ' ' + name
    if obj['size'] > 1.1:
        name = 'big ' + name
    elif obj['size'] < 0.9:
        name = 'small ' + name
    return article(name) if obj['count'] == 1 else f"{obj['count']} {name}{'es' if name.endswith(('s', 'sh', 'ch')) else 's'}"


def summary(scene, order=None, members=None):
    objects = scene['objects']
    names = {'on': 'on', 'above': 'above', 'below': 'below', 'front': 'in front of', 'behind': 'behind'}
    parts = []
    stacked = {r[0]: r for r in scene['relations'] if r[1] in names}
    bases = {r[2] for r in stacked.values()}
    for index, obj in enumerate(objects):
        if index in bases and index not in stacked:
            continue                     # mentioned with what stands on / above it
        text = phrase(obj)
        if index in stacked:
            r = stacked[index]
            text += f" {names[r[1]]} {phrase(objects[r[2]])}"
        if obj['not_colours'] and not obj['colour']:
            text += ' (not ' + ' or '.join(obj['not_colours']) + ')'
        parts.append(text)
    if order and len(order) > 1:
        columns = [' and '.join(phrase(objects[i]) for i in members[c] if i not in stacked) or phrase(objects[c]) for c in order]
        text = ', '.join(parts[:-1]) + ' and ' + parts[-1] if len(parts) > 1 else parts[0]
        text += ' (left to right: ' + ', '.join(c.replace('a ', '', 1).replace('an ', '', 1) for c in columns) + ')'
    else:
        text = ', '.join(parts[:-1]) + ' and ' + parts[-1] if len(parts) > 1 else parts[0]
    if scene['background'] not in (None, 'plain'):
        text += f" on {article(scene['background'])} background"
    return text


def plausibility(scene):
    """Notes for scenes that break common sense; they are drawn anyway, as asked."""
    notes = []
    objects = scene['objects']
    for r in scene['relations']:
        a = objects[r[0]]['topic']
        if r[1] == 'above' and not concepts.flies(a) and len(r) == 3:
            notes.append(f"{article(words_of(a)).capitalize()} can't fly, but I drew it above the {words_of(objects[r[2]]['topic'])} as you asked.")
        if r[1] == 'on' and len(r) == 3 and concepts.size(a) > concepts.size(objects[r[2]]['topic']) * 3:
            notes.append(f"{article(words_of(a)).capitalize()} is much bigger than {article(words_of(objects[r[2]]['topic']))} in real life; I drew it on top anyway.")
    if len(objects) > 1 and any(o['topic'] in ('man', 'woman') for o in objects):
        notes.append('I can only draw people as head-and-shoulders portraits, so they will look odd in a scene.')
    for obj in objects:
        if obj['anchor'] == 'sky' and not concepts.flies(obj['topic']):
            notes.append(f"{article(words_of(obj['topic'])).capitalize()} can't fly, but I put it in the sky as you asked.")
        if scene['background'] == 'desert' and 'cold' in concepts.features(obj['topic']):
            notes.append(f"{article(words_of(obj['topic'])).capitalize()} lives in the cold, not in a desert; drawn as asked.")
        if scene['background'] in ('forest', 'city', 'mountain', 'volcano', 'castle', 'desert', 'snow', 'park', 'field', 'room') \
                and concepts.aquatic(obj['topic']):
            notes.append(f"{article(words_of(obj['topic'])).capitalize()} lives in water, not in {article(scene['background'])}; drawn as asked.")
    return notes
