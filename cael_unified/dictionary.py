"""English dictionary answers from Princeton WordNet 3.0 (models/cael-dictionary-wn30/dictionary.sqlite).

Definitions, synonyms, opposites, example sentences, idioms, word forms (plurals, past tenses), spelling,
rhymes (by spelling) and "is X a real word?". Every answer comes from the lookup tables; nothing is generated.
Built by research/dictionary/build.py. WordNet 3.0 licence: models/cael-dictionary-wn30/WordNet-LICENSE.txt.
"""
from functools import lru_cache
import json
from pathlib import Path
import re
import sqlite3

from .bundle import ROOT

PATH = ROOT / 'models' / 'cael-dictionary-wn30' / 'dictionary.sqlite'
WORDS = ROOT / 'data' / 'spell' / 'en_50k.txt'
DETAILS = ('From Princeton WordNet 3.0, an offline English dictionary (WordNet 3.0 licence). No web lookup and no '
           'generated text.')

# Common irregular verbs: base -> (past simple, past participle). WordNet lists irregular forms but not which is which.
IRREGULAR = {
    'be': ('was / were', 'been'), 'have': ('had', 'had'), 'do': ('did', 'done'), 'go': ('went', 'gone'), 'say': ('said', 'said'),
    'get': ('got', 'got / gotten'), 'make': ('made', 'made'), 'know': ('knew', 'known'), 'think': ('thought', 'thought'),
    'take': ('took', 'taken'), 'see': ('saw', 'seen'), 'come': ('came', 'come'), 'give': ('gave', 'given'), 'find': ('found', 'found'),
    'tell': ('told', 'told'), 'become': ('became', 'become'), 'leave': ('left', 'left'), 'feel': ('felt', 'felt'), 'bring': ('brought', 'brought'),
    'begin': ('began', 'begun'), 'keep': ('kept', 'kept'), 'hold': ('held', 'held'), 'write': ('wrote', 'written'), 'stand': ('stood', 'stood'),
    'hear': ('heard', 'heard'), 'let': ('let', 'let'), 'mean': ('meant', 'meant'), 'set': ('set', 'set'), 'meet': ('met', 'met'),
    'run': ('ran', 'run'), 'pay': ('paid', 'paid'), 'sit': ('sat', 'sat'), 'speak': ('spoke', 'spoken'), 'lie': ('lay', 'lain'),
    'lead': ('led', 'led'), 'read': ('read', 'read'), 'grow': ('grew', 'grown'), 'lose': ('lost', 'lost'), 'fall': ('fell', 'fallen'),
    'send': ('sent', 'sent'), 'build': ('built', 'built'), 'understand': ('understood', 'understood'), 'draw': ('drew', 'drawn'),
    'break': ('broke', 'broken'), 'spend': ('spent', 'spent'), 'cut': ('cut', 'cut'), 'rise': ('rose', 'risen'), 'drive': ('drove', 'driven'),
    'buy': ('bought', 'bought'), 'wear': ('wore', 'worn'), 'choose': ('chose', 'chosen'), 'seek': ('sought', 'sought'), 'throw': ('threw', 'thrown'),
    'catch': ('caught', 'caught'), 'deal': ('dealt', 'dealt'), 'win': ('won', 'won'), 'forget': ('forgot', 'forgotten'), 'sell': ('sold', 'sold'),
    'fight': ('fought', 'fought'), 'teach': ('taught', 'taught'), 'eat': ('ate', 'eaten'), 'sing': ('sang', 'sung'), 'swim': ('swam', 'swum'),
    'drink': ('drank', 'drunk'), 'fly': ('flew', 'flown'), 'sleep': ('slept', 'slept'), 'ride': ('rode', 'ridden'), 'hide': ('hid', 'hidden'),
    'shake': ('shook', 'shaken'), 'steal': ('stole', 'stolen'), 'freeze': ('froze', 'frozen'), 'bite': ('bit', 'bitten'), 'blow': ('blew', 'blown'),
    'hit': ('hit', 'hit'), 'put': ('put', 'put'), 'shut': ('shut', 'shut'), 'hurt': ('hurt', 'hurt'), 'cost': ('cost', 'cost'), 'quit': ('quit', 'quit'),
    'feed': ('fed', 'fed'), 'bend': ('bent', 'bent'), 'lend': ('lent', 'lent'), 'light': ('lit', 'lit'), 'shoot': ('shot', 'shot'),
    'dig': ('dug', 'dug'), 'hang': ('hung', 'hung'), 'stick': ('stuck', 'stuck'), 'strike': ('struck', 'struck'), 'swing': ('swung', 'swung'),
    'ring': ('rang', 'rung'), 'sink': ('sank', 'sunk'), 'shrink': ('shrank', 'shrunk'), 'tear': ('tore', 'torn'), 'bear': ('bore', 'born / borne'),
    'forgive': ('forgave', 'forgiven'), 'arise': ('arose', 'arisen'), 'awake': ('awoke', 'awoken'), 'beat': ('beat', 'beaten'),
    'bleed': ('bled', 'bled'), 'breed': ('bred', 'bred'), 'flee': ('fled', 'fled'), 'grind': ('ground', 'ground'), 'kneel': ('knelt', 'knelt'),
    'slide': ('slid', 'slid'), 'spin': ('spun', 'spun'), 'spit': ('spat', 'spat'), 'split': ('split', 'split'), 'spread': ('spread', 'spread'),
    'sting': ('stung', 'stung'), 'stink': ('stank', 'stunk'), 'swear': ('swore', 'sworn'), 'sweep': ('swept', 'swept'), 'weep': ('wept', 'wept'),
    'wake': ('woke', 'woken'), 'wind': ('wound', 'wound'), 'show': ('showed', 'shown'), 'sew': ('sewed', 'sewn'), 'prove': ('proved', 'proven'),
    'creep': ('crept', 'crept'), 'feel ': ('felt', 'felt'), 'dream': ('dreamed / dreamt', 'dreamed / dreamt'), 'learn': ('learned / learnt', 'learned / learnt'),
    'burn': ('burned / burnt', 'burned / burnt'), 'spell': ('spelled / spelt', 'spelled / spelt'), 'smell': ('smelled / smelt', 'smelled / smelt'),
    'lay': ('laid', 'laid'), 'forbid': ('forbade', 'forbidden'), 'undertake': ('undertook', 'undertaken'), 'withdraw': ('withdrew', 'withdrawn'),
    'overcome': ('overcame', 'overcome'), 'mistake': ('mistook', 'mistaken'), 'foresee': ('foresaw', 'foreseen'),
}
IRREGULAR_PLURAL = {'mouse': 'mice', 'goose': 'geese', 'man': 'men', 'woman': 'women', 'child': 'children', 'tooth': 'teeth',
                    'foot': 'feet', 'person': 'people', 'ox': 'oxen', 'louse': 'lice', 'cactus': 'cacti / cactuses',
                    'fungus': 'fungi', 'nucleus': 'nuclei', 'radius': 'radii', 'crisis': 'crises', 'analysis': 'analyses',
                    'thesis': 'theses', 'phenomenon': 'phenomena', 'criterion': 'criteria', 'datum': 'data', 'sheep': 'sheep',
                    'fish': 'fish / fishes', 'deer': 'deer', 'moose': 'moose', 'series': 'series', 'species': 'species',
                    'knife': 'knives', 'wife': 'wives', 'life': 'lives', 'leaf': 'leaves', 'wolf': 'wolves', 'half': 'halves',
                    'loaf': 'loaves', 'shelf': 'shelves', 'thief': 'thieves', 'calf': 'calves', 'potato': 'potatoes',
                    'tomato': 'tomatoes', 'hero': 'heroes', 'echo': 'echoes', 'cactus ': 'cacti'}
# Common idioms (WordNet has few of them), meanings written for CAEL.
IDIOMS = {
    'break the ice': 'to say or do something that makes people who have just met feel more relaxed',
    'piece of cake': 'something very easy', 'under the weather': 'feeling a little ill',
    'hit the sack': 'to go to bed', 'hit the hay': 'to go to bed', 'cost an arm and a leg': 'to be very expensive',
    'let the cat out of the bag': 'to reveal a secret by accident', 'once in a blue moon': 'very rarely',
    'spill the beans': 'to tell a secret', 'bite the bullet': 'to make yourself do something difficult or unpleasant',
    'beat around the bush': 'to avoid saying something directly', 'call it a day': 'to stop working for now',
    'cut corners': 'to do something badly or cheaply to save time or money', 'get out of hand': 'to become out of control',
    'hang in there': 'to keep going in a difficult situation', 'it is raining cats and dogs': 'it is raining very heavily',
    'raining cats and dogs': 'raining very heavily', 'kill two birds with one stone': 'to achieve two things with one action',
    'miss the boat': 'to lose a chance by being too slow', 'on the ball': 'alert and quick to understand or react',
    'pull someone\'s leg': 'to joke with someone by telling them something untrue', 'pull your leg': 'to joke with you by telling you something untrue',
    'the ball is in your court': 'it is your turn to decide or act', 'the best of both worlds': 'all the advantages of two different things',
    'time flies': 'time passes very quickly', 'actions speak louder than words': 'what you do matters more than what you say',
    'add insult to injury': 'to make a bad situation worse', 'barking up the wrong tree': 'looking in the wrong place or blaming the wrong person',
    'better late than never': 'it is better to do something late than not at all', 'break a leg': 'good luck (said before a performance)',
    'by the skin of your teeth': 'only just; very narrowly', 'cry over spilt milk': 'to be upset about something that cannot be changed',
    'don\'t cry over spilt milk': 'do not be upset about something that cannot be changed', 'every cloud has a silver lining': 'something good can come out of a bad situation',
    'get cold feet': 'to become nervous just before doing something planned', 'give someone the cold shoulder': 'to ignore someone on purpose',
    'go the extra mile': 'to do more than what is expected', 'hit the nail on the head': 'to describe exactly what is causing a situation or problem',
    'in hot water': 'in trouble', 'keep an eye on': 'to watch or look after', 'let sleeping dogs lie': 'to avoid restarting an old problem',
    'make a long story short': 'to tell something briefly', 'no pain no gain': 'you have to work hard to achieve something',
    'on cloud nine': 'extremely happy', 'out of the blue': 'suddenly and unexpectedly', 'over the moon': 'extremely pleased',
    'see eye to eye': 'to agree with someone', 'sit on the fence': 'to avoid choosing a side', 'speak of the devil': 'said when someone appears just as you are talking about them',
    'take it with a grain of salt': 'to not completely believe something', 'the last straw': 'the last problem in a series that makes someone lose patience',
    'through thick and thin': 'in good times and bad times', 'throw in the towel': 'to give up', 'up in the air': 'not yet decided',
    'when pigs fly': 'never; it will not happen', 'you can\'t judge a book by its cover': 'you should not judge something only by how it looks',
    'a blessing in disguise': 'something that seems bad at first but turns out good', 'a dime a dozen': 'very common and of little value',
    'burn the midnight oil': 'to work late into the night', 'cut to the chase': 'to get to the point', 'face the music': 'to accept the consequences of what you did',
    'get the ball rolling': 'to start something', 'hold your horses': 'wait; be patient', 'jump on the bandwagon': 'to join something because it is popular',
    'keep your chin up': 'stay cheerful in a difficult situation', 'learn the ropes': 'to learn how to do a job or activity',
    'on thin ice': 'in a risky situation', 'put all your eggs in one basket': 'to risk everything on a single plan',
    'sleep on it': 'to wait until the next day before deciding', 'steal someone\'s thunder': 'to take the attention or praise someone else expected',
    'the elephant in the room': 'an obvious problem that people avoid talking about', 'wrap your head around': 'to understand something difficult',
    'your guess is as good as mine': 'I do not know either', 'a penny for your thoughts': 'what are you thinking about?',
    'easier said than done': 'harder to do than it sounds', 'feeling blue': 'feeling sad', 'break the bank': 'to cost too much money',
}
NONSTANDARD = {'irregardless': 'regardless', 'alot': 'a lot', 'could of': 'could have', 'should of': 'should have',
               'would of': 'would have', 'supposably': 'supposedly', 'expresso': 'espresso', 'nucular': 'nuclear'}

STRIP = r'[\s"\'“”‘’`*?!.:,]+'
ASK_DEFINE = re.compile(r'(?i)^\s*(?:(?:can you |please )?(?:define|definition of|define the word|meaning of|what(?:\'s| is) the (?:meaning|definition) of)'
                        r'(?: the (?:word|term|idiom|phrase|expression))?\s+(.+?)'
                        r'|what (?:does|do) (?:the (?:word|term|idiom|phrase|expression) )?(.+?) mean'
                        r'|what is meant by (.+?)|(.+?) meaning)\s*\??\s*$')
ASK_SYN = re.compile(r'(?i)\b(?:synonyms?|another word|other words?|a different word|similar words?)\s+(?:for|of|to)\s+(?:the word\s+)?(.+?)\s*\??\s*$'
                     r'|^\s*what(?:\'s| is) a word (?:that means|for)\s+(.+?)\s*\??\s*$')
ASK_ANT = re.compile(r'(?i)\b(?:opposite|antonyms?|the reverse)\s+(?:of|for|to)\s+(?:the word\s+)?(.+?)\s*\??\s*$')
ASK_SENTENCE = re.compile(r'(?i)\b(?:use|put)\s+(?:the word\s+)?(.+?)\s+in\s+a\s+sentence|\b(?:example sentence|sentence) (?:with|using|for) (?:the word\s+)?(.+?)\s*\??\s*$')
ASK_PLURAL = re.compile(r'(?i)\bplural (?:of|for|form of)\s+(?:the word\s+)?(.+?)\s*\??\s*$|\bwhat is more than one\s+(.+?)\s*\??\s*$')
ASK_TENSE = re.compile(r'(?i)\b(past tense|past participle|present participle|-?ing form|third person|simple past)\s+(?:form\s+)?(?:of|for)\s+(?:the (?:verb|word)\s+)?(.+?)\s*\??\s*$')
ASK_SPELL = re.compile(r'(?i)^\s*(?:how (?:do (?:you|i)|to|should i) spell|spell(?: the word)?|what is the (?:correct )?spelling of|is (.+?) spelled (?:right|correctly))\s*(.+?)?\s*\??\s*$')
ASK_RHYME = re.compile(r'(?i)\b(?:rhymes? with|rhyming with|that rhymes? with)\s+(.+?)\s*\??\s*$')
ASK_REAL = re.compile(r'(?i)^\s*is\s+(.+?)\s+(?:a real word|a word|an actual word|a proper word|correct english|proper english)\s*\??\s*$')
ASK_ORIGIN = re.compile(r'(?i)\b(?:origin|etymology)\s+of\s+(?:the word\s+)?(.+?)\s*\??\s*$|\bwhat language (?:does|did) (?:the word\s+)?(.+?) come from')
ASK_POS = re.compile(r'(?i)^\s*(?:is|what part of speech is)\s+(?:the word\s+)?["\']?([a-z\-]+)["\']?\s+(?:a\s+)?(noun|verb|adjective|adverb)?\s*\??\s*$')


@lru_cache(maxsize=1)
def db():
    if not PATH.exists():
        return None
    return sqlite3.connect(f'file:{PATH}?mode=ro', uri=True, check_same_thread=False)


@lru_cache(maxsize=1)
def frequent():
    """Common English words, most frequent first (data/spell/en_50k.txt: 'word count' lines)."""
    bundled = PATH.parent / 'frequent.txt'
    words = bundled if bundled.is_file() else WORDS
    if not words.exists():
        return []
    return [line.split()[0] for line in words.read_text(encoding='utf-8', errors='ignore').splitlines() if line.split()]


def clean(word):
    word = re.sub(r'^(?:the|a|an|to)\s+(?=\w)', '', re.sub(r'^' + STRIP + '|' + STRIP + '$', '', word.strip()).lower())
    return re.sub(r'\s+', ' ', word)


def bases(word):
    """Dictionary forms a word may come from: itself, irregular forms, then regular endings (WordNet's morphy rules)."""
    connection = db()
    out = [word]
    if connection:
        out += [row[0] for row in connection.execute('SELECT base FROM form WHERE form=?', (word,))]
    for suffix, replace in (('ies', 'y'), ('es', ''), ('s', ''), ('ied', 'y'), ('ed', ''), ('ed', 'e'), ('ing', ''), ('ing', 'e'),
                            ('er', ''), ('est', ''), ('er', 'e'), ('est', 'e'), ('ves', 'f'), ('ves', 'fe')):
        if word.endswith(suffix) and len(word) - len(suffix) >= 2:
            out.append(word[:-len(suffix)] + replace)
    if re.search(r'(.)\1(?:ed|ing)$', word):
        out.append(re.sub(r'(.)\1(?:ed|ing)$', r'\1', word))
    return list(dict.fromkeys(out))


def senses(word, pos=None):
    """[(pos, gloss, examples, words, antonyms, hypernyms, similar, synset id)] most common first."""
    connection = db()
    if not connection:
        return [], word
    for base in bases(word):
        query = ('SELECT s.pos, s.gloss, s.examples, s.words, s.antonyms, s.hypernyms, s.similar, s.id, l.tagged, l.rank '
                 'FROM lemma l JOIN synset s ON s.id=l.synset WHERE l.word=?')
        args = [base]
        if pos:
            query += ' AND l.pos=?'
            args.append(pos)
        rows = connection.execute(query + ' ORDER BY l.rank', args).fetchall()
        if rows:
            order = {'noun': 0, 'verb': 1, 'adjective': 2, 'adverb': 3}
            # Parts of speech by how often the word is used that way (WordNet's SemCor counts), then by sense count;
            # WordNet's own sense order inside each.
            usage, counts = {}, {}
            for row in rows:
                usage[row[0]] = max(usage.get(row[0], 0), row[8] or 0)
                counts[row[0]] = counts.get(row[0], 0) + 1
            ranked = sorted(rows, key=lambda r: (-usage[r[0]], -counts[r[0]], order[r[0]], r[9]))
            return [(r[0], r[1], json.loads(r[2]), json.loads(r[3]), json.loads(r[4]), json.loads(r[5]), json.loads(r[6]), r[7]) for r in ranked], base
    return [], word


def known(word):
    return bool(senses(word)[0]) or word in set(frequent()[:50000])


def out(response, route):
    return dict(response=response, route='chat/dictionary-' + route, sources=[], details=DETAILS)


def define(word):
    idiom = IDIOMS.get(word.replace('’', "'"))
    if idiom:
        return dict(out(f'**{word}** (idiom): {idiom[0].upper() + idiom[1:]}.', 'idiom'),
                    details='A short list of common English idioms written for CAEL.')
    found, base = senses(word)
    if not found:
        return None
    lines = [f'**{base}**' + (f' (from "{word}")' if base != word else '')]
    shown, by_pos = 0, {}
    for pos, gloss, examples, words, *_ in found:
        if by_pos.get(pos, 0) >= 2 or shown >= 3:
            continue
        by_pos[pos] = by_pos.get(pos, 0) + 1
        shown += 1
        line = f'{shown}. ({pos}) {gloss[0].upper() + gloss[1:]}.'
        example = next((e for e in examples if re.search(r'(?i)\b' + re.escape(base[:max(3, len(base) - 2)]), e)), examples[0] if examples else None)
        if example:
            line += f' Example: "{example}"'
        lines.append(line)
    more = len(found) - shown
    if more > 0:
        lines.append(f'({more} more meaning{"s" if more > 1 else ""} in my dictionary.)')
    return out('\n'.join(lines), 'define')


def synonyms(word):
    found, base = senses(word)
    if not found:
        return None
    # Candidates from the main part of speech: words sharing a meaning, then words close in meaning ("similar to"),
    # earlier senses first; shown most common first, so "glad, cheerful" beats "felicitous".
    rank = {w: i for i, w in enumerate(frequent()[:50000])}

    def pool_for(pos_wanted):
        rows = [r for r in found if r[0] == pos_wanted][:5]
        return [(i, w) for i, (pos, gloss, _, words, _, _, similar, _) in enumerate(rows)
                for w in words + similar if w.lower() != base and ' ' not in w and w.lower() in rank
                and base not in bases(w.lower())]          # not the word's own forms ("bigger" for big)

    # The word's most common part of speech, unless it has hardly any synonyms there ("fast" as an adverb).
    pools = {pos: pool_for(pos) for pos in dict.fromkeys(r[0] for r in found)}
    main = found[0][0]
    if len(set(w for _, w in pools[main])) < 3:
        main = max(pools, key=lambda p: len(set(w for _, w in pools[p])))
    pool = pools[main]
    if not pool:
        return out(f'My dictionary has no common synonyms listed for "{base}".', 'synonyms')
    best = sorted(dict.fromkeys(w for _, w in pool), key=lambda w: (min(i for i, x in pool if x == w) > 1, rank.get(w.lower(), 10 ** 6)))
    return out(f'Synonyms of **{base}** ({main}): {", ".join(best[:8])}.', 'synonyms')


def antonyms(word):
    found, base = senses(word)
    if not found:
        return None
    direct = [b for row in found for a, b in row[4] if a.lower() == base]
    if not direct:
        # Satellite adjectives ("ancient") have no direct opposite; the head adjective of their FIRST sense ("old") does.
        for row in found:
            if row[0] != 'adjective' or not row[6]:
                continue
            head = row[6][0]
            for _, _, _, _, ants, *_ in senses(head, 'adjective')[0]:
                direct += [b for a, b in ants if a.lower() == head.lower()]
            if direct:
                direct = direct[:2]
                break
    if not direct:
        return out(f'My dictionary has no opposite listed for "{base}".', 'antonyms')
    return out(f'The opposite of **{base}** is **{", ".join(dict.fromkeys(direct[:4]))}**.', 'antonyms')


def sentence(word):
    found, base = senses(word)
    if not found:
        return None
    for row in found:
        for example in row[2]:
            if re.search(r'(?i)\b' + re.escape(base[:max(4, len(base) - 3)]), example):
                return out(f'"{example[0].upper() + example[1:]}." ({row[0]}: {row[1]})', 'sentence')
    pos, gloss = found[0][0], found[0][1]
    return out(f'My dictionary has no example sentence for "{base}". It means: {gloss} ({pos}). For instance, '
               f'you could write: "The word {base} describes something {gloss.split(";")[0]}."' if pos == 'adjective' else
               f'My dictionary has no example sentence for "{base}". It means: {gloss} ({pos}).', 'sentence')


def plural(word):
    base = word
    if base in IRREGULAR_PLURAL:
        return out(f'The plural of **{base}** is **{IRREGULAR_PLURAL[base]}**.', 'forms')
    connection = db()
    if connection:
        row = connection.execute("SELECT form FROM form WHERE base=? AND pos='noun'", (base,)).fetchone()
        if row:
            return out(f'The plural of **{base}** is **{row[0]}**.', 'forms')
    if re.search(r'(?:s|x|z|ch|sh)$', base):
        form = base + 'es'
    elif re.search(r'[^aeiou]y$', base):
        form = base[:-1] + 'ies'
    else:
        form = base + 's'
    return out(f'The plural of **{base}** is **{form}**.', 'forms')


def tense(kind, word):
    verb = word
    for base in bases(word):
        if base in IRREGULAR or senses(base, 'verb')[0]:
            verb = base
            break
    kind = kind.lower()
    if 'present participle' in kind or 'ing' in kind:
        form = verb[:-1] + 'ing' if verb.endswith('e') and not verb.endswith('ee') else verb + 'ing'
        if re.search(r'[^aeiou][aeiou][bdgmnprt]$', verb) and len(verb) <= 4:
            form = verb + verb[-1] + 'ing'
        return out(f'The -ing form of **{verb}** is **{form}**.', 'forms')
    if 'third' in kind:
        form = verb + ('es' if re.search(r'(?:s|x|z|ch|sh|o)$', verb) else 's')
        if re.search(r'[^aeiou]y$', verb):
            form = verb[:-1] + 'ies'
        return out(f'With he/she/it: **{form}**.', 'forms')
    if verb in IRREGULAR:
        past, participle = IRREGULAR[verb]
        if 'participle' in kind:
            return out(f'The past participle of **{verb}** is **{participle}** (past simple: {past}).', 'forms')
        return out(f'The past tense of **{verb}** is **{past}** (past participle: {participle}).', 'forms')
    if verb.endswith('e'):
        form = verb + 'd'
    elif re.search(r'[^aeiou]y$', verb):
        form = verb[:-1] + 'ied'
    elif re.search(r'^[^aeiou]*[aeiou][bdgmnprt]$', verb):
        form = verb + verb[-1] + 'ed'
    else:
        form = verb + 'ed'
    what = 'past participle' if 'participle' in kind else 'past tense'
    return out(f'The {what} of **{verb}** is **{form}** (a regular verb).', 'forms')


def edit_distance(a, b, limit=3):
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def spelling(word):
    if not word or not re.fullmatch(r"[a-z\-']{2,30}", word):
        return None
    if known(word):
        return out(f'It is spelled **{word}**: {"-".join(word.upper())}.', 'spelling')
    candidates = [w for w in frequent()[:50000] if abs(len(w) - len(word)) <= 2 and w[0] == word[0]]
    best = sorted(candidates, key=lambda w: (edit_distance(word, w), candidates.index(w)))[:1]
    if best and edit_distance(word, best[0]) <= 2:
        return out(f'"{word}" is not in my dictionary. Did you mean **{best[0]}**? It is spelled {"-".join(best[0].upper())}.', 'spelling')
    return out(f'I could not find "{word}" or a close spelling in my dictionary.', 'spelling')


def rhymes(word):
    if not re.fullmatch(r'[a-z]{2,20}', word):
        return None
    ending = re.search(r'[aeiouy]+[^aeiouy]*$', word)
    if not ending:
        return None
    tail = ending[0]
    # Same vowel letters and ending, after a consonant (so "cat" does not match "great" or "boat"); "wa"/"wha" sound
    # different ("what"), so those are left out for a-words.
    shape = re.compile(r'(?:^|[^aeiouy])' + re.escape(tail) + '$')
    pool = [w for w in frequent()[:30000] if w != word and shape.search(w) and re.fullmatch(r'[a-z]+', w)
            and not w.endswith(word) and not (tail[0] == 'a' and re.search(r'w' + re.escape(tail) + '$|wh' + re.escape(tail) + '$', w))]
    picks = list(dict.fromkeys(w for w in pool if known(w)))[:10]
    if not picks:
        return out(f'I could not find common words that rhyme with "{word}".', 'rhymes')
    return out(f'Words that rhyme with **{word}**: {", ".join(picks)}. (I match spelling, not sound, so a few may not rhyme '
               'perfectly.)', 'rhymes')


def real_word(word):
    if word in NONSTANDARD:
        return out(f'"{word}" is used, but it is considered nonstandard. Use **{NONSTANDARD[word]}** in careful writing.', 'real-word')
    if known(word):
        found, base = senses(word)
        meaning = f' It means: {found[0][1]}.' if found else ''
        return out(f'Yes, "{word}" is a real English word.{meaning}', 'real-word')
    return spelling(word)


def reply(text):
    """A dictionary answer, or None when the message is not a word question this dictionary can answer."""
    if not db() or re.search(r'(?i)\bmeaning of (?:life|it all)\b', text):      # the big question, not a word lookup
        return None
    for pattern, handler in ((ASK_ANT, antonyms), (ASK_SYN, synonyms), (ASK_SENTENCE, sentence), (ASK_PLURAL, plural),
                             (ASK_RHYME, rhymes), (ASK_REAL, real_word)):
        match = pattern.search(text)
        if match:
            word = clean(next(g for g in match.groups() if g))
            if len(word.split()) <= 4:
                answer = handler(word)
                if answer:
                    return answer
    match = ASK_TENSE.search(text)
    if match:
        return tense(match[1], clean(match[2]))
    match = ASK_SPELL.match(text)
    if match and (match[1] or match[2]):
        return spelling(clean(match[1] or match[2]))
    match = ASK_ORIGIN.search(text)
    if match:
        word = clean(match[1] or match[2])
        if known(word):
            return out(f'My dictionary does not record where "{word}" comes from (word origins are not in WordNet), so I would '
                       'rather not guess. An etymological dictionary would have it.', 'origin')
    match = ASK_DEFINE.match(text)
    if match:
        word = clean(next(g for g in match.groups() if g))
        if 0 < len(word.split()) <= 5 and not re.search(r'\b(?:this|that|it|you|i|your)\b', word):
            return define(word)
    return None
