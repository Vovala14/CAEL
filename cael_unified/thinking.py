"""CAEL works out its own answer to advice and how-to questions instead of copying one.

1. Understand: the kind of request (how-to, ideas) and the goal ("how do I keep my plants alive?" -> keep your plants alive).
2. Recall: find related questions by words, WordNet synonyms and meaning (LSA over question titles,
   models/cael-thinking-v2/meaning.npz). Each related question is weighed by how close it is.
3. Gather: the advice extracted from every answer to those questions (research/thinking/build.py, advice_text.py).
4. Think: group advice that says the same thing (same action and object), score each group by how many separate
   answers agree and how relevant and well-voted they are, drop one-off advice, and order by agreement.
5. Write: compose a new reply: an introduction for the goal, the leading points with reasons, related "don'ts" merged
   into one sentence, and a closing question. The advice phrases come from the sources; the selection, ranking,
   merging and the text around them are CAEL's own. Every reply lists its sources and how many answers agreed.
No neural network: string rules, counts, a dictionary and linear algebra (LSA).
"""
from functools import lru_cache
import json
import math
import random
import re
import sqlite3

import numpy as np

from .bundle import ROOT

FOLDER = ROOT / 'models' / 'cael-thinking-v2'
STOP = set('a an the and or but if of to in on at for with from by about as is are was were be been being am do does did done have has '
           'had i me my mine myself you your yours we us our they them their he him his she her it its this that these those there here '
           'what which who whom when where why how can could would should will shall may might must just really very so too also some '
           'any all each every no not only than then such into over under again once more most other up down out off both few get got '
           'make let thing things something anything way ways good best better one ok okay please tips tip advice help someone'.split())
SITES = {'stackexchange': 'Stack Exchange (CC BY-SA 4.0)', 'oasst2': 'OpenAssistant (Apache 2.0)', 'oasst1': 'OpenAssistant (Apache 2.0)',
         'dolly': 'databricks-dolly-15k (CC BY-SA 3.0)'}
GOAL = [
    (r"^how (?:do|can|should|would|could) (?:i|we|you|one|people) (.+)$", 'how'),
    (r"^how to (.+)$", 'how'),
    (r"^what(?:'s| is) the best way to (.+)$", 'how'),
    (r"^what (?:can|should) i do to (.+)$", 'how'),
    # "What can I do about my back pain?", "What should I do if I feel burned out?", "I need help falling asleep"
    (r"^what (?:can|should|could) i do (?:about|for|with) (.+)$", 'how'),
    (r"^what (?:can|should|do) (?:i|you) do (?:if|when) (.+)$", 'how'),
    (r"^(?:i need|i want|i'd like|i would like|please) (?:some )?(?:help|advice|tips) (?:with |on |for |about )?(.+)$", 'how'),
    (r"^(?:help me|can you help me|could you help me) (?:to )?(.+)$", 'how'),
    (r"^(?:any |some |give me (?:some )?)?(?:tips|advice) (?:for|on|about) (.+)$", 'how'),
    (r"^(?:give me |any |some |what are (?:some |good )?)?ideas? (?:for|to) (.+)$", 'ideas'),
    (r"^what should i (pack|bring|buy|get|take|wear|cook|make) (.+)$", 'ideas'),
]


GENERIC_VERBS = {'get', 'make', 'do', 'be', 'have', 'keep', 'deal', 'stop', 'start', 'become', 'improve', 'handle', 'manage', 'go', 'find',
                  'learn', 'use', 'feel', 'stay', 'take', 'give', 'help', 'avoid', 'cope', 'try', 'know', 'tell'}


@lru_cache(maxsize=1)
def db():
    path = FOLDER / 'knowledge.sqlite'
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True, check_same_thread=False) if path.exists() else None


@lru_cache(maxsize=1)
def meaning():
    path = FOLDER / 'meaning.npz'
    if not path.exists():
        return None
    data = np.load(path)
    vocabulary = json.loads(str(data['vocabulary']))
    return dict(terms=data['terms'], idf=data['idf'], questions=data['questions'].astype(np.float32),
                index={w: i for i, w in enumerate(vocabulary)}, stop=set(json.loads(str(data['stop']))))


def stem(word):
    word = word.lower().replace("'", '')
    for suffix in ('ingly', 'edly', 'ings', 'ing', 'ied', 'ies', 'ed', 'es', 's', 'ly', 'er'):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[:-len(suffix)]
            break
    return word[:-1] if word.endswith('e') and len(word) > 3 else word


def content(text):
    return [w for w in re.findall(r"[a-z][a-z']+", text.lower()) if w not in STOP and len(w) > 2]


@lru_cache(maxsize=4096)
def synonyms(word):
    """A few everyday synonyms from WordNet ("procrastinate" -> "postpone", "delay")."""
    from . import dictionary as dic
    found, base = dic.senses(word)
    out = []
    for row in found[:2]:
        out += [w.lower() for w in row[3] if ' ' not in w and w.lower() != base]
    return tuple(dict.fromkeys(out))[:4]


LICENCES = {'stackexchange': ('CC BY-SA 4.0', 'https://creativecommons.org/licenses/by-sa/4.0/', 'Stack Exchange contributors (see the question for authors)'),
            'oasst2': ('Apache 2.0', 'https://www.apache.org/licenses/LICENSE-2.0', 'OpenAssistant volunteers'),
            'oasst1': ('Apache 2.0', 'https://www.apache.org/licenses/LICENSE-2.0', 'OpenAssistant volunteers'),
            'dolly': ('CC BY-SA 3.0', 'https://creativecommons.org/licenses/by-sa/3.0/', 'Databricks employees')}


def sources_for(questions, limit=3):
    """Links to the closest discussions an answer drew on (attribution for CC BY-SA sources)."""
    out, seen = [], set()
    for q in sorted(questions, key=lambda q: -q[4]):
        url = q[5] if len(q) > 5 else ''
        if not url or url in seen:
            continue
        seen.add(url)
        licence, licence_url, attribution = LICENCES.get(q[2], ('', '', ''))
        name = (f'Stack Exchange ({q[3]}): {q[1][:80]}' if q[2] == 'stackexchange' else f'{SITES.get(q[2], q[2])}: {q[1][:80]}')
        out.append(dict(source=name, url=url, licence=licence, licence_url=licence_url, attribution=attribution))
        if len(out) == limit:
            break
    return out


def understand(text):
    """(kind, goal phrase in the second person) or None."""
    lower = ' '.join(text.lower().strip().rstrip('?!.').split())
    lower = re.sub(r'^(?:please |can you tell me |could you tell me |do you know )', '', lower)
    for pattern, kind in GOAL:
        m = re.match(pattern, lower)
        if m:
            goal = ' '.join(g for g in m.groups() if g)
            goal = re.sub(r'\bmy\b', 'your', goal)
            goal = re.sub(r'\b(?:i|me)\b', 'you', goal)
            goal = re.sub(r'\bmyself\b', 'yourself', goal)
            return kind, as_action(pattern, goal)
    return None


def as_action(pattern, goal):
    """Make the goal read as something to do: "your back pain" -> "deal with your back pain",
    "your dog pulls on the lead" -> "handle it when your dog pulls on the lead", "falling asleep" -> "fall asleep"."""
    if '(?:about|for|with)' in pattern:
        return 'deal with ' + goal
    if '(?:if|when)' in pattern:
        return 'handle it when ' + goal
    first, _, rest = goal.partition(' ')
    if first.endswith('ing') and len(first) > 5:
        from .advice_text import gerund_to_base
        base = gerund_to_base(first)
        if base != first:
            return (base + ' ' + rest).strip()
    return goal


def meaning_vector(text):
    m = meaning()
    if not m:
        return None
    counts = {}
    for w in re.findall(r"[a-z][a-z]+", text.lower()):
        if w in m['stop'] or w not in m['index']:
            continue
        counts[m['index'][w]] = counts.get(m['index'][w], 0) + 1
    if not counts:
        return None
    idx = np.array(list(counts))
    weights = (1 + np.log(np.array(list(counts.values()), np.float32))) * m['idf'][idx]
    weights /= np.linalg.norm(weights) + 1e-9
    vector = weights @ m['terms'][idx]
    return vector / (np.linalg.norm(vector) + 1e-9)


def related(text, goal, limit=40):
    """[(question id, title, source, site, relevance)] for questions about the same thing."""
    connection = db()
    words = content(goal)
    if not connection or not words:
        return []
    expanded = list(dict.fromkeys(words + [s for w in words for s in synonyms(w)]))
    query = ' OR '.join(f'{stem(w)}*' if len(stem(w)) >= 4 else f'"{w}"' for w in expanded)
    candidates = {}
    try:
        for row in connection.execute('SELECT q.id, q.title, q.source, q.site, q.url FROM title_index JOIN question q ON q.id = title_index.rowid '
                                      'WHERE title_index MATCH ? ORDER BY bm25(title_index) LIMIT 400', (query,)):
            candidates[row[0]] = row
    except sqlite3.OperationalError:
        pass
    vector = meaning_vector(goal)
    m = meaning()
    similarity = {}
    if vector is not None and m is not None:
        scores = m['questions'] @ vector
        for i in np.argpartition(-scores, 80)[:80]:
            similarity[int(i) + 1] = float(scores[i])            # question ids start at 1, in title order
        missing = [i for i in similarity if i not in candidates]
        if missing:
            marks = ','.join('?' * len(missing))
            for row in connection.execute(f'SELECT id, title, source, site, url FROM question WHERE id IN ({marks})', missing):
                candidates[row[0]] = row
    # Each word counts by how rare it is among question titles: "procrastinating" decides, "stop" and "better" barely do.
    asked = {stem(w): rarity(w) for w in words}
    key_word = max(asked, key=asked.get)
    first = goal.split()[0] if goal.split() else ''
    action = stem(first) if first in words and first not in GENERIC_VERBS and stem(first) != key_word else None
    near = {stem(w): {stem(s) for s in synonyms(w)} for w in words}
    total = sum(asked.values())
    out = []
    for qid, row in candidates.items():
        title_words = {stem(w) for w in content(row[1])}
        if not title_words:
            continue
        hits = {w for w in asked if any(same_word(w, t) for t in title_words) or near[w] & title_words}
        covered = sum(asked[w] for w in hits) / total
        sim = similarity.get(qid)
        if sim is None and vector is not None:
            sim = float(m['questions'][qid - 1] @ vector)
        sim = sim or 0.0
        if key_word not in hits and sim < 0.8:
            continue                                     # the question must be about the rare, defining word
        if action and action not in hits and sim < 0.8:
            continue                                     # "train my puppy" needs training, not just puppies (or trains)
        if covered >= 0.55 or (sim >= 0.6 and covered >= 0.4):
            out.append((qid, row[1], row[2], row[3], 0.5 * covered + 0.5 * max(sim, 0), row[4]))
    out.sort(key=lambda r: -r[4])
    return out[:limit]


def same_word(a, b):
    """Two stems are the same word: equal, or sharing a long beginning ("procrastinat" / "procrastination")."""
    if a == b:
        return True
    n = min(len(a), len(b))
    return n >= 5 and a[:max(5, n - 1)] == b[:max(5, n - 1)]


@lru_cache(maxsize=8192)
def rarity(word):
    connection = db()
    s = stem(word)
    term = f'{s}*' if len(s) >= 4 else f'"{word}"'
    try:
        found = connection.execute('SELECT COUNT(*) FROM title_index WHERE title_index MATCH ?', (term,)).fetchone()[0]
    except sqlite3.OperationalError:
        found = 0
    total = connection.execute('SELECT COUNT(*) FROM question').fetchone()[0]
    return math.log((total + 1) / (found + 1)) + 0.5


def gather(questions, table='advice'):
    connection = db()
    if not questions:
        return []
    relevance = {q[0]: q[4] for q in questions}
    marks = ','.join('?' * len(relevance))
    if table == 'advice':
        rows = connection.execute(f'SELECT question, answer, key, action, reason, negative, weight FROM advice WHERE question IN ({marks})', list(relevance)).fetchall()
    else:
        rows = connection.execute(f'SELECT question, key, text, weight FROM idea WHERE question IN ({marks})', list(relevance)).fetchall()
    return [(r, relevance[r[0]]) for r in rows]


@lru_cache(maxsize=4096)
def verb_family(verb):
    """A verb and its WordNet synonyms: "rinse" and "wash" give the same advice."""
    return frozenset({verb} | set(synonyms(verb)))


def cluster(rows):
    """Group advice that says the same thing; support = how many separate answers give it."""
    groups = {}
    for (qid, answer, key, action, reason, negative, weight), relevance in rows:
        g = groups.setdefault(key, dict(key=key, questions=set(), answers=set(), score=0.0, actions={}, reasons={},
                                        negative=bool(negative), best=0.0))
        g['best'] = max(g['best'], relevance)
        if answer not in g['answers']:
            g['score'] += relevance * min(weight, 4.0)
        g['questions'].add(qid)
        g['answers'].add(answer)
        phrase = re.sub(r'\s+(?:as well|too|etc|and so on|if possible|if you can)$', '', action.strip(' .'))
        g['actions'][phrase] = g['actions'].get(phrase, 0) + 1
        if reason:
            g['reasons'][reason] = g['reasons'].get(reason, 0) + 1
    # One piece of advice said several ways: a shared object word and the same verb or a synonym
    # ("water the plant" / "water your plants", "rinse the rice" / "wash the rice").
    merged = {}
    for key, g in sorted(groups.items(), key=lambda kv: -len(kv[1]['answers'])):
        verb, _, nouns = key.partition('|')
        negative = verb.startswith('no:')
        verb = verb[3:] if negative else verb
        target = None
        for k in merged:
            other, _, other_nouns = k.partition('|')
            if other.startswith('no:') != negative:
                continue
            other = other[3:] if negative else other
            if (other == verb or other in verb_family(verb)) and set(other_nouns.split('+')) & set(nouns.split('+')):
                target = k
                break
        if target:
            t = merged[target]
            t['score'] += g['score']
            t['best'] = max(t['best'], g['best'])
            t['questions'] |= g['questions']
            t['answers'] |= g['answers']
            for d in ('actions', 'reasons'):
                for k, v in g[d].items():
                    t[d][k] = t[d].get(k, 0) + v
        else:
            merged[key] = g
    for g in merged.values():
        g['support'] = len(g['answers'])
    return sorted(merged.values(), key=lambda g: (-g['support'], -g['score']))


def general(text):
    """Advice anyone could follow: short, no numbers, prices, quotes or unknown names."""
    from . import dictionary as dic
    words = re.findall(r"[a-z']+", text.lower())
    if not 2 <= len(words) <= 14 or re.search(r'[\d$€£"“”()]', text):
        return False
    common = set(dic.frequent()[:30000])
    return all(w in common or dic.known(w) for w in words if len(w) > 3)


def phrase_of(group):
    """The clearest way the group's advice was put: frequent, then short and complete."""
    options = sorted(group['actions'].items(), key=lambda kv: (-kv[1], abs(len(kv[0].split()) - 7)))
    text = options[0][0]
    text = re.sub(r'\byou\'?re\b', "you're", text)
    return text


def sentence(text):
    text = text.strip(' .;,')
    return text[:1].upper() + text[1:] + ('' if text.endswith(('!', '?')) else '.')


INTROS = {
    'how': ['Here is what helps most if you want to {goal}:', 'To {goal}, these points come up again and again:',
            'Good question! The advice people agree on most, if you want to {goal}:'],
    'ideas': ['Here are the ideas people suggest most for {goal}:', 'A few ideas that come up a lot for {goal}:'],
}
OUTROS = ['Want me to go deeper on any of these?', 'Which of these would you like to try first?', 'Is there one you would like more detail on?']


def write(kind, goal, groups, questions, seed):
    rng = random.Random(seed + len(goal))
    points, donts = [], []
    for g in groups:
        text = phrase_of(g)
        if g['negative'] or g['key'].startswith('no:'):
            donts.append(text)
            continue
        reason = max(g['reasons'].items(), key=lambda kv: kv[1])[0] if g['reasons'] else ''
        points.append((text, reason, g['support']))
        if len(points) >= 5:
            break
    lines = [rng.choice(INTROS['how']).format(goal=goal)] if kind == 'how' else [rng.choice(INTROS['ideas']).format(goal=goal)]
    for i, (text, reason, support) in enumerate(points, 1):
        line = f'{i}. **{sentence(text)}**'
        if reason and len(reason.split()) <= 20:
            line += ' ' + sentence(reason[0].upper() + reason[1:] if not reason.lower().startswith(('it ', 'this ', 'that ', 'you ')) else reason)
        lines.append(line)
    if donts:
        if len(donts) >= 2 and all(len(d.split()) <= 8 for d in donts[:2]):
            lines.append(f'\nAnd try not to {donts[0]}, or {donts[1]}.')
        else:
            lines.append(f'\nAnd try not to {donts[0]}.')
    answers = sum(g['support'] for g in groups[:len(points)])
    top = points[0][2]
    lines.append(('\nI put the most widely recommended first: the top point came up in ' + f'{top} separate discussions. ' if top > 1 else
                  '\nThese come mostly from the discussion closest to your question. ') + rng.choice(OUTROS))
    sources = sorted({SITES.get(q[2], q[2]) + (f': {q[3]}' if q[3] else '') for q in questions})
    details = (f'Written by CAEL from advice it extracted from answers to {len(questions)} related questions '
               f'(found by words, synonyms and meaning). Points are ordered by how many separate discussions agree '
               f'({", ".join(str(p[2]) for p in points)}). The advice phrases come from those answers; choosing, ranking, '
               f'merging and the wording around them are CAEL\'s. Sources: {"; ".join(sources[:8])}. No neural model.')
    return '\n'.join(lines), details


def ideas(goal, questions, seed):
    rows = gather(questions, 'idea')
    groups = {}
    for (qid, key, text, weight), relevance in rows:
        g = groups.setdefault(key, dict(questions=set(), texts={}, score=0.0))
        if qid not in g['questions']:
            g['score'] += relevance * min(weight, 4.0)
        g['questions'].add(qid)
        g['texts'][text] = g['texts'].get(text, 0) + 1
    ranked = sorted((g for g in groups.values() if len(g['questions']) >= 2), key=lambda g: (-len(g['questions']), -g['score']))[:7]
    if len(ranked) < 3:
        return None
    rng = random.Random(seed + len(goal))
    items = [max(g['texts'].items(), key=lambda kv: (kv[1], -len(kv[0])))[0] for g in ranked]
    body = rng.choice(INTROS['ideas']).format(goal=goal) + '\n' + '\n'.join(f'- {i[0].upper() + i[1:]}' for i in items)
    body += f'\n\nThe first ones were suggested in the most separate discussions. {rng.choice(OUTROS)}'
    return body


@lru_cache(maxsize=1)
def guides():
    path = FOLDER / 'guides.sqlite'
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True, check_same_thread=False) if path.exists() else None


UNITS = r'(?:cups?|c\.|tablespoons?|tbsp\.?|tbs|teaspoons?|tsp\.?|grams?|g|kg|kilograms?|ml|millilit(?:er|re)s?|l|lit(?:er|re)s?|ounces?|oz|pounds?|lbs?|' \
        r'pinch(?:es)?|dash(?:es)?|cloves?|cans?|packages?|pieces?|slices?|sticks?|large|medium|small|whole|fresh|chopped|minced|sliced|diced)'


def ingredient_name(line):
    """'1½ cups all-purpose flour, sifted' -> 'all-purpose flour'."""
    text = re.sub(r'\(.*?\)', '', line.lower())
    text = text.split(',')[0].split(' or ')[0]
    text = re.sub(r'[\d½¼¾⅓⅔⅛/.\-–]+\s*', ' ', text)
    text = re.sub(r'\b' + UNITS + r'\b', ' ', text)
    text = re.sub(r'\b(?:of|about|approximately|to taste|optional|for|the|a|an)\b', ' ', text)
    return ' '.join(text.split()).strip()


def head(ingredient):
    """The ingredient's main word, singular: 'large eggs' -> egg, 'all purpose flour' -> flour."""
    from .advice_text import noun_stem
    return noun_stem(ingredient.split()[-1])


def recipe(text, seed=0):
    """'how do I make pancakes?': the ingredients most recipes share, and a method condensed from the closest one."""
    m = re.match(r"(?i)^\s*(?:how (?:do|can|should) (?:i|you|we) |how to |what(?:'s| is) the best way to )(?:make|cook|bake|prepare)\s+(?:a |an |some |the |my )?(.+?)\s*\??\s*$", text)
    connection = guides()
    if not m or not connection:
        return None
    dish = m[1].lower().strip()
    if len(dish.split()) > 4:
        return None
    core = stem(dish.split()[-1])
    rows = connection.execute('SELECT title, ingredients, steps, url FROM recipe WHERE dish LIKE ?', (f'%{core}%',)).fetchall()
    others = [w for w in content(dish)[:-1]]

    def title_words(r):
        return {stem(w) for w in re.findall(r'[a-z]+', r[0].split(':', 1)[1].lower())}

    # Whole words only: "bread" is not "Shortbread", "cake" is not "Pancakes".
    rows = [r for r in rows if core in title_words(r) and all(stem(w) in title_words(r) for w in others)]
    if len(rows) < 2:
        return None
    # General recipes first: the fewer extra words in the title, the more basic the recipe.
    rows.sort(key=lambda r: (len(r[0].split(':', 1)[1].split()), len(r[0])))
    rows = rows[:10]
    recipes = [(r[0].split(':', 1)[1], [ingredient_name(i) for i in json.loads(r[1])], json.loads(r[2]), r[3]) for r in rows]
    counts = {}
    for _, ingredients, _, _ in recipes:
        for name in {head(i) for i in ingredients if i}:
            counts[name] = counts.get(name, 0) + 1
    shared = [n for n, c in sorted(counts.items(), key=lambda kv: -kv[1]) if c >= max(2, len(recipes) * 0.4)]
    if len(shared) < 3 or len([n for n in shared if counts[n] >= len(recipes) * 0.5]) < 4:
        return None                      # "soup" covers too many different dishes to share a core
    # The most basic recipe: many shared ingredients, few unusual ones, and a plain title ("Pancakes", not "Durian Pancake").
    def basic(r):
        names = {head(i) for i in r[1] if i}
        extra_title = len(r[0].split()) - len(dish.split())
        return len(names & set(shared)) - 0.6 * len(names - set(shared)) - 0.8 * max(0, extra_title)
    best = max(recipes, key=basic)
    if len({head(i) for i in best[1] if i} - set(shared)) > 4:
        return None                      # no basic recipe to show: the closest one is still a special regional dish
    full_names = {}
    for _, ingredients, _, _ in recipes:
        for i in ingredients:
            if i and head(i) in shared and len(i.split()) <= 3:
                full_names.setdefault(head(i), {}).setdefault(i, 0)
                full_names[head(i)][i] += 1
    names = [max(full_names.get(n, {n: 1}).items(), key=lambda kv: (kv[1], -len(kv[0])))[0] for n in shared[:10]]
    steps = []
    for step in best[2][:8]:
        first = re.split(r'(?<=[.!?])\s+', step.strip())[0].rstrip('.')
        if first:
            steps.append(first[0].upper() + first[1:] + '.')
    rng = random.Random(seed + len(dish))
    body = (f'{rng.choice(["Here is how I would make", "Let me walk you through"])} {dish}.\n\n'
            f'**What you need:** {", ".join(names)}. (Of the {len(recipes)} {dish} recipes I know, most use these.)\n\n'
            f'**Method** (condensed from the recipe closest to that core, "{best[0]}"):\n'
            + '\n'.join(f'{i}. {s}' for i, s in enumerate(steps, 1))
            + '\n\nWant a variation, such as a vegan or gluten-free version?')
    return dict(response=body, route='chat/thinking-recipe',
                sources=[dict(source=f'Wikibooks Cookbook: {best[0]}', url=best[3], licence='CC BY-SA 4.0',
                              licence_url='https://creativecommons.org/licenses/by-sa/4.0/', attribution='Wikibooks contributors')],
                details=(f'CAEL compared {len(recipes)} recipes from the Wikibooks Cookbook (CC BY-SA), kept the ingredients most of them share, '
                         f'and condensed the method of the closest one: {best[3]}. No neural model.'))


def reasoned(goal, known, questions, seed):
    """Combine what CAEL knows about a topic with what related discussions agree on, then write the answer."""
    from .advice_text import key_of
    rng = random.Random(seed + len(goal))
    groups = []
    for i, (action, reason) in enumerate(known):
        groups.append(dict(key=key_of(action, False) or action, action=action, reason=reason, backing=0, order=i))
    extra = []
    backing_questions = set()
    if questions:
        for g in cluster(gather(questions)):
            if g['negative'] or not general(phrase_of(g)):
                continue
            verb, _, nouns = g['key'].partition('|')
            match = next((k for k in groups if k['key'].partition('|')[0] in verb_family(verb)
                          and set(k['key'].partition('|')[2].split('+')) & set(nouns.split('+'))), None)
            if match:
                match['backing'] += g['support']             # the discussions agree with what CAEL knows
                backing_questions |= g['questions']
            elif g['support'] >= 3:
                extra.append(g)                              # something many answers add that CAEL did not know
                if len(extra) == 1:
                    backing_questions |= g['questions']      # only the one extra point that is shown
    # Known advice that discussions back up comes first; then the rest in CAEL's own order of importance.
    ordered = sorted(groups, key=lambda g: (-min(g['backing'], 3), g['order']))[:5]
    intros = ['Here is what helps most if you want to {goal}:', 'If you want to {goal}, these make the biggest difference:',
              'Good question! What really helps if you want to {goal}:']
    lines = [rng.choice(intros).format(goal=goal)]
    for i, g in enumerate(ordered, 1):
        line = f'{i}. **{sentence(g["action"])}**'
        if g['reason']:
            line += ' ' + sentence(g['reason'][0].upper() + g['reason'][1:])
        lines.append(line)
    for g in extra[:1]:
        lines.append(f'{len(ordered) + 1}. **{sentence(phrase_of(g))}** (many people who answered this recommend it)')
    backed = sum(1 for g in ordered if g['backing'])
    if questions and backed:
        lines.append(f'\nThese are well-established tips, and {len(questions)} related discussions back up {backed} of them. '
                     + rng.choice(OUTROS))
    else:
        lines.append('\n' + rng.choice(OUTROS))
    if re.search(r'(?i)anxi|lonel|breakup|heartbreak|stress', goal):
        lines.append('If it is weighing on you a lot or for a long time, talking to a doctor or counsellor really helps.')
    details = (f'Written by CAEL from its general knowledge of this topic, checked against {len(questions)} related discussions '
               f'({backed} of the points are backed up by them). The order and wording are CAEL\'s. No neural model.')
    # Credit only the discussions whose advice actually backed a point.
    backing = [q for q in questions if q[0] in backing_questions]
    return dict(response='\n'.join(lines), route='chat/thinking', sources=sources_for(backing), details=details)


def reply(text, messages=(), seed=0):
    """CAEL's own answer to an advice or ideas request, or None when it does not know enough."""
    if not db():
        return None
    # "make/bake X" is a recipe; "cook rice" is first a technique question (the advice side answers it better).
    made = recipe(text, seed) if not re.search(r'(?i)\bcook\b', text) else None
    if made:
        return made
    understood = understand(text)
    if not understood:
        return None
    kind, goal = understood
    questions = [q for q in related(text, goal) if q[4] >= 0.6]
    from .life_advice import topic_for
    # The person's own words ("my nails"), not the rewritten goal. An ideas request ("ideas for a date night") uses the
    # knowledge only when it asks what to do ("what should I pack..."); otherwise it wants ideas, not advice.
    known = topic_for(text) if kind == 'how' or re.match(r'(?:pack|bring|buy|get|take|wear|cook|make)\b', goal) else None
    if known:
        return reasoned(goal, known, questions, seed)
    if len(questions) < 3:
        return None
    if kind == 'ideas':
        body = ideas(goal, questions, seed)
        if body:
            return dict(response=body, route='chat/thinking-ideas', sources=sources_for(questions),
                        details=f'Ideas CAEL gathered from {len(questions)} related discussions and ranked by how often they '
                                'were suggested. No neural model.')
        return None
    # Advice several separate discussions agree on, or advice from a discussion that is almost exactly this question.
    groups = [g for g in cluster(gather(questions)) if g['support'] >= 2 or g['best'] >= 0.85]
    # On topic: a point shares a word with the question or with what the related discussions are usually about,
    # or at least three separate discussions recommend it.
    topic = {stem(w) for w in content(goal)} | {stem(s) for w in content(goal) for s in synonyms(w)}
    counts = {}
    for q in questions:
        for w in {stem(w) for w in content(q[1])}:
            counts[w] = counts.get(w, 0) + 1
    topic |= {w for w, c in counts.items() if c >= max(3, len(questions) * 0.25)}
    verbs = {stem(content(goal)[0])} if content(goal) else set()

    def on_topic(g):
        words = [stem(w) for a in g['actions'] for w in content(a)[1:]]       # the object words, not the verb
        return any(same_word(w, t) for w in words for t in topic - verbs)

    # Points must be on topic, or agreed by several answers in discussions that match the question very closely.
    groups = [g for g in groups if (g['support'] >= 3 or on_topic(g) or (g['support'] >= 2 and g['best'] >= 0.9)) and general(phrase_of(g))]
    agreed = [g for g in groups if g['support'] >= 2 and not g['negative']]
    if not agreed or (agreed[0]['support'] < 3 and len(agreed) < 4):
        return None                                      # not enough agreement to say something of its own
    if len([g for g in groups if not g['negative']]) < 3:
        return None
    body, details = write(kind, goal, groups, questions, seed)
    return dict(response=body, route='chat/thinking', sources=sources_for(questions), details=details)
