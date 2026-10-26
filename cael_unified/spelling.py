"""Spelling and chat-speak correction for everyday messages, never a neural model.

Word frequencies and word-pair counts come from CAEL's own Wikipedia snapshot (models/cael-spelling-v1, counts only),
plus the vocabulary of the active count-language model and WordNet 3.0 lemmas. A word that is not known is replaced
by the most likely known word within one edit (two for longer words), scored by how common it is, how well it fits
between its neighbours ("wich planet" -> "which planet", "deal with stres" -> "deal with stress"), and the kind of
slip (swapped letters, a neighbouring key, "ph"/"f" sounds). A hand-written list covers the most common English
misspellings, words typed together ("blackhole") are split, and chat shorthand ("u", "r", "thx", "2day") is expanded.
Code, links, numbers, quoted text and names are left alone.

`correct(text)` returns (corrected text, list of (original, replacement)).
"""
from functools import lru_cache
import gzip
import json
import math
from pathlib import Path
import re
import sqlite3

from .bundle import ROOT

COUNTS = ROOT / 'models' / 'cael-spelling-v1'
SHORTHAND = {
    'u': 'you', 'r': 'are', 'ur': 'your', 'urself': 'yourself', 'ya': 'you', 'yu': 'you', 'thx': 'thanks', 'thanx': 'thanks',
    'ty': 'thank you', 'pls': 'please', 'plz': 'please', 'pleas': 'please', 'b4': 'before', '2day': 'today', '2morrow': 'tomorrow',
    '2nite': 'tonight', 'tmrw': 'tomorrow', 'tmr': 'tomorrow', 'wat': 'what', 'wut': 'what', 'wats': "what's", 'whats': "what's",
    'hows': "how's", 'whos': "who's", 'wheres': "where's", 'im': "I'm", 'ive': "I've", 'id': "I'd", 'ill': "I'll",
    'dont': "don't", 'doesnt': "doesn't", 'didnt': "didn't", 'cant': "can't", 'wont': "won't", 'isnt': "isn't",
    'arent': "aren't", 'wasnt': "wasn't", 'shouldnt': "shouldn't", 'couldnt': "couldn't", 'wouldnt': "wouldn't",
    'thats': "that's", 'theres': "there's", 'lets': "let's", 'youre': "you're", 'theyre': "they're", 'gonna': 'going to',
    'wanna': 'want to', 'gotta': 'got to', 'kinda': 'kind of', 'idk': "I don't know", 'btw': 'by the way', 'abt': 'about',
    'cuz': 'because', 'coz': 'because', 'bc': 'because', 'becuz': 'because', 'nite': 'night', 'luv': 'love', 'k': 'okay',
    'ok': 'okay', 'pic': 'picture', 'pics': 'pictures', 'msg': 'message', 'info': 'information', 'diff': 'difference',
    'helo': 'hello', 'hellow': 'hello', 'helllo': 'hello', 'hlpe': 'help', 'hepl': 'help', 'halp': 'help', 'hlep': 'help',
    'n': 'and', 'w/': 'with', 'wiht': 'with', 'teh': 'the', 'hte': 'the', 'adn': 'and', 'waht': 'what', 'hwo': 'how',
}
# The most common English misspellings (hand-written list; these words never need guessing).
MISSPELLED = {w: r for r, ws in {
    'which': 'wich whcih wihch witch_', 'with': 'wtih whit_', 'the': 'teh', 'because': 'becuase becasue beacuse becouse',
    'believe': 'beleive belive', 'receive': 'recieve recive', 'definitely': 'definately definatly defintely',
    'separate': 'seperate', 'until': 'untill', 'weird': 'wierd', 'their': 'thier', 'tomorrow': 'tommorow tomorow tommorrow',
    'wednesday': 'wensday wedensday', 'february': 'febuary', 'government': 'goverment govermant', 'environment': 'enviroment',
    'beautiful': 'beautifull beatiful butiful', 'interesting': 'intresting intersting', 'probably': 'probaly probly',
    'really': 'realy relly', 'finally': 'finaly', 'coming': 'comming', 'writing': 'writting', 'beginning': 'begining',
    'occurred': 'occured', 'accommodate': 'accomodate', 'achieve': 'acheive', 'address': 'adress', 'argument': 'arguement',
    'calendar': 'calender', 'cemetery': 'cemetary', 'conscious': 'concious', 'embarrass': 'embarass', 'existence': 'existance',
    'foreign': 'foriegn', 'grammar': 'grammer', 'harass': 'harrass', 'independent': 'independant', 'knowledge': 'knowlege',
    'library': 'libary', 'millennium': 'millenium', 'necessary': 'neccessary necessery', 'noticeable': 'noticable',
    'occasion': 'ocassion occassion', 'pursue': 'persue', 'possession': 'posession', 'preferred': 'prefered',
    'publicly': 'publically', 'recommend': 'reccomend recomend reccommend', 'relevant': 'relevent', 'rhythm': 'rythm',
    'sense': 'sence', 'successful': 'succesful sucessful', 'surprise': 'suprise supprise', 'tomatoes': 'tomatos',
    'truly': 'truely', 'whether': 'wether', 'written': 'writen', 'friend': 'freind frend', 'friends': 'freinds frends',
    'know': 'kno', 'favorite': 'favrite favorit',
    'different': 'diffrent', 'difference': 'diffrence diference', 'people': 'poeple peopel', 'thought': 'thougth',
    'question': 'quesiton qustion', 'answer': 'anwser answr', 'something': 'somthing', 'sometimes': 'somtimes',
    'everything': 'everthing', 'everyone': 'everone', 'again': 'agian', 'about': 'abuot', 'could': 'coudl', 'would': 'woudl',
    'should': 'shoudl shuold', 'little': 'littel', 'school': 'scool shcool', 'science': 'sience', 'machine': 'machien',
    'language': 'langauge languge', 'country': 'contry',
    'restaurant': 'resturant restaraunt', 'business': 'buisness bussiness', 'minute': 'minuet', 'tongue': 'tounge',
    'chocolate': 'choclate chocolat', 'vegetable': 'vegtable', 'vegetables': 'vegtables',
    'exercise': 'excercise exersize', 'experience': 'experiance', 'genius': 'genious', 'guarantee': 'garantee',
    'height': 'heighth', 'immediately': 'immediatly', 'island': 'iland', 'jewelry': 'jewelery', 'mathematics': 'mathmatics',
    'medicine': 'medecine', 'particular': 'particuler', 'piece': 'peice', 'pronunciation': 'pronounciation',
    'schedule': 'schedual', 'temperature': 'temprature', 'weather': 'wheather', 'wonderful': 'wonderfull', 'tired': 'tierd', 'story': 'storie stroy', 'complete': 'compleet complet',
    'anniversary': 'aniversary anniversery',
}.items() for w in ws.split() if not w.endswith('_')}
# Words CAEL must not "correct": its own names, site features and common chat words outside the dictionaries.
OWN = set('cael vynly mica mage sudoku sparks spark trails trail flares flare midjourney dalle sora runway flux comfyui c2pa synthid '
          'okay ok hey hi hello lol haha yeah yep nope wow omg emoji emojis selfie online offline email emails app apps '
          'youtube tiktok instagram google facebook whatsapp iphone android wifi covid'.split())
FUNCTION = set('the a an and or but if then than so because as of in on at by for with about into onto from to up down out '
               'over under again further once here there when where why how all any both each few more most other some such '
               'no nor not only own same too very can will just should now is are was were be been being have has had having '
               'do does did doing would could might must shall may i me my myself we our ours ourselves you your yours '
               'yourself yourselves he him his himself she her hers herself it its itself they them their theirs themselves '
               'what which who whom whose this that these those am an also yes yet ever never always often sometimes '
               'everyone everything someone something anyone anything nobody nothing whatever whoever whichever '
               'hello hi hey thanks please sorry okay'.split())
# Opening words a capitalised typo may be corrected to ("Explane how ..." -> "Explain how ...").
OPENERS = set('what who whom whose where when why how which is are was were do does did can could would should will '
              'explain tell write describe define give make show list name find calculate convert translate summarize '
              'compare help please create draw suggest recommend teach'.split())
TOKEN = re.compile(r"[A-Za-z][A-Za-z']*|\d+[A-Za-z]+|[A-Za-z]+\d+|w/")
PROTECT = re.compile(r"```.*?```|`[^`]*`|\"[^\"]*\"|“[^”]*”|https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+|\b[\w-]+\.(?:com|org|net|co|io|ai|py|js|txt)\b",
                     re.S)
KEYBOARD = ['qwertyuiop', 'asdfghjkl', 'zxcvbnm']
NEAR = {}
for row, keys in enumerate(KEYBOARD):
    for col, key in enumerate(keys):
        NEAR[key] = {KEYBOARD[r][c] for r in range(max(0, row - 1), min(3, row + 2))
                     for c in range(max(0, col - 1), col + 2) if c < len(KEYBOARD[r])} - {key}
SOUNDS = (('f', 'ph'), ('ph', 'f'), ('k', 'c'), ('c', 'k'), ('s', 'c'), ('c', 's'), ('z', 's'), ('ee', 'ea'), ('ea', 'ee'),
          ('i', 'y'), ('y', 'i'), ('er', 'or'), ('or', 'er'), ('ance', 'ence'), ('ence', 'ance'), ('able', 'ible'),
          ('ible', 'able'), ('shun', 'tion'), ('tion', 'sion'), ('sion', 'tion'), ('oo', 'u'), ('u', 'oo'), ('x', 'cks'),
          ('w', 'wh'), ('j', 'g'), ('g', 'j'), ('kw', 'qu'), ('nite', 'night'), ('ite', 'ight'), ('ks', 'x'), ('kes', 'x'))


def inflections(word, pos):
    """Regular plural / verb / comparative forms, which WordNet does not list."""
    out = []
    vowel = 'aeiou'
    pos = {'noun': 'n', 'verb': 'v', 'adjective': 'a', 'adjective satellite': 's', 'adverb': 'r'}.get(pos, pos)
    if pos in ('n', 'v'):
        if word.endswith(('s', 'x', 'z', 'ch', 'sh')):
            out.append(word + 'es')
        elif word.endswith('y') and len(word) > 2 and word[-2] not in vowel:
            out.append(word[:-1] + 'ies')
        else:
            out.append(word + 's')
    if pos == 'v':
        if word.endswith('e'):
            out += [word + 'd', word[:-1] + 'ing']
        elif word.endswith('y') and len(word) > 2 and word[-2] not in vowel:
            out += [word[:-1] + 'ied', word + 'ing']
        else:
            out += [word + 'ed', word + 'ing']
            if len(word) >= 3 and word[-1] not in vowel + 'wxy' and word[-2] in vowel and word[-3] not in vowel:
                out += [word + word[-1] + 'ed', word + word[-1] + 'ing']
    if pos in ('a', 's') and len(word) <= 7:
        base = word if word.endswith('e') else word[:-1] + 'i' if word.endswith('y') else word
        if len(word) == 3 and word[-1] not in vowel + 'wxy' and word[-2] in vowel and word[-3] not in vowel:
            base = word + word[-1]                     # big -> bigger, biggest
        out += [base + ('r' if word.endswith('e') else 'er'), base + ('st' if word.endswith('e') else 'est')]   # large: larger, largest
    return out


def load_counts(name):
    try:
        with gzip.open(COUNTS / name, 'rt', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def pairs():
    return load_counts('pairs.json.gz')


@lru_cache(maxsize=1)
def lexicon():
    """(frequency of every known word, set of words known to the dictionaries)."""
    counts = dict(load_counts('words.json.gz'))
    known = set()
    # Spoken-English word frequencies (OpenSubtitles via hermitdave/FrequencyWords, CC BY-SA 4.0), shipped with the
    # dictionary: everyday words ("delete", "friends") that an encyclopedia rarely uses.
    for path in (ROOT / 'models/cael-dictionary-wn30/frequent.txt', ROOT / 'data/spell/en_50k.txt'):
        try:
            for line in path.read_text(encoding='utf-8').splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[0].isalpha() and parts[1].isdigit():
                    counts[parts[0]] = counts.get(parts[0], 0) + int(parts[1]) // 20
            break
        except OSError:
            continue
    try:
        active = json.loads((ROOT / 'research/active_models.json').read_text(encoding='utf-8'))
        folder = Path(active['language']['path']).parent
    except Exception:
        folder = ROOT / 'models/cael-language-0.3.2-math-python'
    try:
        import numpy as np
        words = json.loads((folder / 'vocab.json').read_text(encoding='utf-8'))
        totals = np.load(folder / 'global.npy')
        for w, c in zip(words, totals.tolist()):
            if w.isalpha() and w.islower() and c >= 3:
                counts[w] = counts.get(w, 0) + int(c) // 4
    except Exception:
        pass
    try:
        with sqlite3.connect(f'file:{ROOT / "models/cael-dictionary-wn30/dictionary.sqlite"}?mode=ro', uri=True) as db:
            for w, pos in db.execute('select distinct word, pos from lemma'):
                if w.isalpha():
                    w = w.lower()
                    known.add(w)
                    known.update(inflections(w, pos))
            for (w,) in db.execute('select distinct form from form'):
                if w.isalpha():
                    known.add(w.lower())
    except Exception:
        pass
    for w in known:
        counts[w] = max(counts.get(w, 0), 3)
    for w in OWN | FUNCTION:
        counts[w] = max(counts.get(w, 0), 1000)
        known.add(w)
    for w in MISSPELLED:
        counts.pop(w, None)
        known.discard(w)
    return counts, known


def vocabulary():
    return lexicon()[0]


@lru_cache(maxsize=1)
def deletes_index():
    """SymSpell-style index: every word (seen 3+ times) under each single-letter deletion of it."""
    index = {}
    for w, n in vocabulary().items():
        if 3 <= len(w) <= 18 and n >= 3:
            for i in range(len(w)):
                index.setdefault(w[:i] + w[i + 1:], []).append(w)
            index.setdefault(w, []).append(w)
    return index


def damerau(a, b, limit=2):
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    rows = [list(range(len(b) + 1))]
    for i, x in enumerate(a, 1):
        row = [i]
        for j, y in enumerate(b, 1):
            v = min(row[-1] + 1, rows[-1][j] + 1, rows[-1][j - 1] + (x != y))
            if i > 1 and j > 1 and x == b[j - 2] and a[i - 2] == y:
                v = min(v, rows[-2][j - 2] + 1)
            row.append(v)
        if min(row) > limit:
            return limit + 1
        rows.append(row)
    return rows[-1][-1]


def candidates(word):
    """{candidate: edit cost}: known words within one edit (two for 5+ letters), sound-alikes and two-word splits."""
    vocab = vocabulary()
    index = deletes_index()
    keys = {word} | {word[:i] + word[i + 1:] for i in range(len(word))}
    found = set()
    for k in keys:
        found.update(index.get(k, ()))
    if len(word) >= 5:
        for k in {k[:i] + k[i + 1:] for k in keys for i in range(len(k))}:
            found.update(index.get(k, ()))
    out = {w: d for w in found if (d := damerau(word, w, 2 if len(word) >= 5 else 1)) <= (2 if len(word) >= 5 else 1)}
    for i in range(len(word)):                            # "aminal" -> "animal": two letters swapped further apart
        for j in range(i + 2, min(len(word), i + 4)):
            alt = word[:i] + word[j] + word[i + 1:j] + word[i] + word[j + 1:]
            if alt != word and vocab.get(alt, 0) >= 3:
                out[alt] = 1
    for a, b in SOUNDS:                                   # "fotos" -> "photos" counts as one slip
        start = word.find(a)
        while start >= 0:
            alt = word[:start] + b + word[start + len(a):]
            if vocab.get(alt, 0) >= 3:
                out[alt] = min(out.get(alt, 9), 1)
            start = word.find(a, start + 1)
    if len(word) >= 6:                                    # "blackhole" -> "black hole"
        for i in range(3, len(word) - 2):
            left, right = word[:i], word[i:]
            if vocab.get(left, 0) >= 300 and vocab.get(right, 0) >= 300 and pairs().get(f'{left} {right}', 0) >= 20:
                out[f'{left} {right}'] = 1
    return out


def score(word, cand, dist, before, after, opening):
    vocab = vocabulary()
    parts = cand.split()
    freq = pairs().get(cand, 0) * 3 if len(parts) == 2 else vocab.get(cand, 0)
    s = math.log1p(freq) - 3.0 * dist
    first, last = parts[0], parts[-1]
    if before:
        s += 0.8 * math.log1p(pairs().get(f'{before} {first}', 0))
    if after:
        s += 0.8 * math.log1p(pairs().get(f'{last} {after}', 0))
    if cand[0] == word[0]:
        s += 1.0
    if len(cand) == len(word) and sorted(cand) == sorted(word):
        s += 1.5 if damerau(word, cand, 1) == 1 else 0.6   # swapped neighbours ("joek"); farther swaps are rarer
    if len(cand) == len(word) + 1 and any(cand[:i] + cand[i + 1:] == word and (cand[i] == cand[i - 1] if i else False)
                                          for i in range(1, len(cand))):
        s += 1.2                                       # one of a double letter left out ("talest" -> "tallest")
    if len(cand) == len(word):
        diffs = [(x, y) for x, y in zip(word, cand) if x != y]
        if len(diffs) == 1 and diffs[0][1] in NEAR.get(diffs[0][0], ()):
            s += 0.4                                   # a neighbouring key
    if opening and cand in OPENERS:
        s += 1.5
    if word.endswith('s') == cand.endswith('s'):
        s += 0.5                                       # keep a plural plural ("pancaks" -> "pancakes")
    if len(cand) == len(word) + 1 and any(cand[:i] + cand[i + 1:] == word for i in range(len(cand))):
        s += 0.6                                       # a letter left out is the most common slip ("finsh" -> "finish")
    if re.search(r'q(?!u)', word) and 'qu' in cand:
        s += 5.0                                       # "q" is nearly always followed by "u" ("sqared" -> "squared")
    return s


@lru_cache(maxsize=8192)
def fix_word(word, before='', after='', opening=False):
    """The corrected spelling of one lowercase word in its context, or None when it is fine or unclear."""
    best = ranked_fixes(word, before, after, opening)
    return best[0] if len(best) == 1 else None


@lru_cache(maxsize=8192)
def ranked_fixes(word, before='', after='', opening=False):
    """(the fix,) when one correction is clear; (first, second) when two are about equally likely; () otherwise."""
    if word in MISSPELLED:
        return (MISSPELLED[word],)
    counts, known = lexicon()
    if not word.isalpha() or not 3 <= len(word) <= 18:
        return ()
    freq = counts.get(word, 0)
    if word in known or freq >= 40:
        return real_word_fix(word, before, after, freq)
    found = candidates(word)
    found.pop(word, None)
    if not found:
        return ()
    # A reasonable one-slip fix beats any two-letter guess ("delet" is "delete", not "felt").
    if any(d == 1 and (pairs().get(c, 0) if ' ' in c else counts.get(c, 0)) >= 20 for c, d in found.items()):
        found = {c: d for c, d in found.items() if d == 1}
    ranked = sorted(((score(word, c, d, before, after, opening), c) for c, d in found.items()), reverse=True)
    best = ranked[0][1]
    best_freq = pairs().get(best, 0) if ' ' in best else counts.get(best, 0)
    # The neighbours can show a slip even in a rare real word: "eifel tower" is never written, "eiffel tower" often.
    context = (pairs().get(f'{before} {best.split()[0]}', 0) + pairs().get(f'{best.split()[-1]} {after}', 0)) >= 20 and         pairs().get(f'{before} {word}', 0) + pairs().get(f'{word} {after}', 0) == 0
    if best_freq < 20 or best_freq < (5 if context else 30) * max(freq, 1):
        return ()                                      # the typed word may be a rare real word; leave it
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.8:
        return (best, ranked[1][1])                    # two about equally likely words: no single fix
    return (best,)


def real_word_fix(word, before, after, freq):
    """A real word that its neighbours show is a slip: "the capitol of canada" (capital), "make tee" (tea).
    Only when the typed word is fairly rare, a one-letter neighbour is far more common in exactly this context, and
    the replacement is not a little function word."""
    if freq >= 1500 or len(word) < 4 or not (before and after) or word in FUNCTION or word in OWN:
        return ()
    def around(w):
        return pairs().get(f'{before} {w}', 0) + pairs().get(f'{w} {after}', 0) if before or after else 0
    if pairs().get(f'{before} {word}', 0) or pairs().get(f'{word} {after}', 0):
        return ()                                      # the typed word is seen next to one of its neighbours: fine
    best = None
    for cand, d in candidates(word).items():
        # Only one changed letter (capitol/capital): not an added or dropped letter (thinks/think, toys/toy).
        if d != 1 or ' ' in cand or len(cand) != len(word) or cand in FUNCTION or vocabulary().get(cand, 0) < 3 * max(freq, 1):
            continue
        if cand[:-1] == word[:-1]:
            continue                                   # only the ending differs: another form of the same word
        if pairs().get(f'{before} {cand}', 0) < 10 or pairs().get(f'{cand} {after}', 0) < 10:
            continue                                   # the fix must fit both neighbours
        n = around(cand)
        if best is None or n > best[0]:
            best = (n, cand)
    return (best[1],) if best else ()


@lru_cache(maxsize=2048)
def adjective_only(word):
    """True when WordNet gives the word more adjective senses than noun senses ("funny", "smart"; not "name")."""
    try:
        with sqlite3.connect(f'file:{ROOT / "models/cael-dictionary-wn30/dictionary.sqlite"}?mode=ro', uri=True) as db:
            kinds = dict(db.execute('select pos, count(*) from lemma where word = ? group by pos', (word,)).fetchall())
    except sqlite3.Error:
        return False
    adjective = kinds.get('adjective', 0) + kinds.get('adjective satellite', 0)
    return adjective > kinds.get('noun', 0)


def variants(text):
    """Other readings of the text for words with two about equally likely fixes ("talest": latest / tallest)."""
    base, _ = correct(text)
    tokens = list(TOKEN.finditer(base))
    out = []
    for i, m in enumerate(tokens):
        word = m.group(0)
        if not word.isalpha() or word[0].isupper():
            continue
        opening = m.start() == 0 or bool(re.search(r'[.!?]\s*$', base[:m.start()]))
        before = tokens[i - 1].group(0).lower() if i > 0 and not opening else ''
        after = tokens[i + 1].group(0).lower() if i + 1 < len(tokens) else ''
        options = ranked_fixes(word.lower(), before, after, opening)
        if len(options) == 2:
            out += [base[:m.start()] + o + base[m.end():] for o in options]
        if len(out) >= 4:
            break
    return out[:4]


# Real words in the wrong place, fixed only inside these exact phrases.
PHRASES = [(r'\bloose (weight|some weight|fat|pounds|kilos)\b', r'lose \1'), (r'\b(what|how|why|when|where|who) dose\b', r'\1 does'),
           (r'\bdose (it|he|she|this|that|a|an|the)\b', r'does \1'), (r'\bpoem about the see\b', 'poem about the sea'),
           (r'\b(i|you|we|they) should of\b', r'\1 should have'), (r'\b(could|would) of\b', r'\1 have'),
           (r'\byour welcome\b', "you're welcome"), (r'\btye (a|my|your|the) tie\b', r'tie \1 tie'),
           (r'\bits (raining|snowing|sunny|cold|hot|late|ok|okay|fine)\b', r"it's \1"), (r'\bto (much|many|late|early)\b', r'too \1'),
           (r'\b(a|short|bedtime|funny|little|the) storey\b', r'\1 story'), (r'\bbreath (out|in)\b', r'breathe \1'),
           (r'\b(\d+)\s*[x×]\s*(\d+)\b', r'\1 * \2'), (r'\bcapitol of\b', 'capital of'), (r'\bsing up\b', 'sign up'),
           (r'\bsing in\b', 'sign in'), (r'\b(more|be|feel|so|very|not) confidant\b', r'\1 confident'),
           (r'\bfirst women (in|to)\b', r'first woman \1'), (r'\bmake (a )?tee\b', r'make \1tea'), (r'\bcup of tee\b', 'cup of tea')]


def correct(text):
    if not text or len(text) > 2000:
        return text, []
    phrase_changes = []
    for pattern, repl in PHRASES:
        found = re.search('(?i)' + pattern, text)
        if found:
            new = re.sub('(?i)' + pattern, repl, text)
            if new != text:
                phrase_changes.append((found.group(0), re.sub('(?i)' + pattern, repl, found.group(0))))
                text = new
    text, changes = correct_words(text)
    return text, phrase_changes + changes


def correct_words(text):
    protected = [m.span() for m in PROTECT.finditer(text)]
    code = re.search(r'```|\b(?:def|class|import|return)\s+\w|[{};]\s*$|\w+\([^)]*\)\s*$', text)
    if code:
        protected.append((code.start(), len(text)))
    tokens = list(TOKEN.finditer(text))
    changes = []
    out = []
    last = 0
    for i, m in enumerate(tokens):
        if any(a <= m.start() < b for a, b in protected):
            continue
        original = m.group(0)
        word = original.lower()
        replacement = None
        # Letters joined to digits are codes, not words ("r1c1", "4x4", "b12").
        if text[m.end():m.end() + 1].isdigit() or (m.start() and text[m.start() - 1].isdigit()):
            continue
        # A capitalised word followed by a verb is a name ("Helo splits 28 apples", "Theo has ...").
        follow = re.match(r"\s+([a-z]+)", text[m.end():])
        named = original[0].isupper() and bool(follow) and (
            follow.group(1) in ('has', 'had', 'is', 'was', 'went', 'gave', 'got', 'said', 'says', 'and', 'buys', 'bought')
            or (follow.group(1).endswith('s') and len(follow.group(1)) > 3 and follow.group(1)[:-1] in vocabulary()))
        opening = m.start() == 0 or bool(re.search(r'[.!?]\s*$', text[:m.start()]))
        if original[0].isupper() and "'" not in SHORTHAND.get(word, '') and (
                len(re.findall(r'\b' + re.escape(original) + r'\b', text)) > 1 or not opening):
            named = True                               # repeated or mid-sentence capitalised word: a name
        if named:
            continue
        if word in SHORTHAND:
            replacement = SHORTHAND[word]
            if word in ('ur', 'u r'):
                # "ur funny" is "you're funny"; "ur name" is "your name".
                follow_word = re.match(r"\s+([a-z]+)", text[m.end():].lower())
                if follow_word and (follow_word.group(1) in ('so', 'very', 'really', 'not', 'too', 'such', 'the', 'a', 'an', 'welcome',
                                                             'right', 'wrong', 'awesome', 'amazing', 'cool', 'cute', 'smart')
                                    or follow_word.group(1).endswith('ing') or adjective_only(follow_word.group(1))):
                    replacement = "you're"
            if word == 'id' and not re.match(r"(?i)\s*(?:like|love|rather|say|be|go|think)\b", text[m.end():]):
                replacement = None
            if word == 'ill' and not re.match(r"(?i)\s*(?:be|go|do|have|try|need|get|see|call)\b", text[m.end():]):
                replacement = None
            if word in ('n', 'k', 'r', 'u') and (m.start() > 0 and text[m.start() - 1] in "'-"):
                replacement = None
            if word == 'lets' and not re.match(r"(?i)\s*(?:go|do|make|play|talk|see|try|start|get|have|chat|write)\b", text[m.end():]):
                replacement = None
        elif "'" not in word and word.isalpha():
            before = tokens[i - 1].group(0).lower() if i > 0 and not opening else ''
            after = tokens[i + 1].group(0).lower() if i + 1 < len(tokens) else ''
            fixed = fix_word(word, before, after, opening)
            # A capitalised word is usually a name ("Theo", "Felix"): only an opening question or command word.
            if fixed and original[0].isupper() and not (opening and fixed in OPENERS):
                fixed = None
            replacement = fixed
        if replacement and replacement.lower() != word:
            if original.isupper() and len(original) > 1:
                replacement = replacement.upper()
            elif original[0].isupper():
                replacement = replacement[0].upper() + replacement[1:]
            out.append(text[last:m.start()] + replacement)
            last = m.end()
            changes.append((original, replacement))
    out.append(text[last:])
    return ''.join(out), changes
