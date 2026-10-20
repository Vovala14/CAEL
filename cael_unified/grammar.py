"""English grammar help: correct a sentence and say why, explain common confusions, change tense or voice,
name the subject and verb, and add punctuation.

Rule-based and explainable: every change names the rule that made it. Parts of speech and irregular forms come
from the offline dictionary (dictionary.py, WordNet 3.0); spelling from the 50,000-word frequency list. It
handles common learner and typing errors, not every sentence of English, and says so when it finds nothing.
"""
import re

from . import dictionary as dic

DETAILS = ('Rule-based grammar check: each change comes from a named rule (agreement, articles, commonly confused '
           'words, irregular verbs, spelling, capitals, punctuation). Parts of speech from WordNet 3.0.')

SUBJECT_ONE = {'he', 'she', 'it', 'this', 'that', 'everyone', 'everybody', 'someone', 'somebody', 'nobody', 'each', 'one'}
SUBJECT_MANY = {'i', 'you', 'we', 'they', 'these', 'those'}
NUMBERS = {'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'many', 'several', 'few', 'both', 'some',
           'twenty', 'hundred', 'dozen'}
AN_EXCEPTIONS = {'university', 'unicorn', 'user', 'useful', 'usual', 'euro', 'european', 'one', 'once', 'uniform', 'unit', 'union', 'unique', 'utensil'}
A_EXCEPTIONS = {'hour', 'honest', 'honour', 'honor', 'heir', 'herb'}
CONTRACTIONS = {'dont': "don't", 'doesnt': "doesn't", 'didnt': "didn't", 'cant': "can't", 'couldnt': "couldn't", 'wouldnt': "wouldn't",
                'shouldnt': "shouldn't", 'isnt': "isn't", 'arent': "aren't", 'wasnt': "wasn't", 'werent': "weren't", 'havent': "haven't",
                'hasnt': "hasn't", 'im': "I'm", 'ive': "I've", 'youve': "you've", 'theyre': "they're", 'thats': "that's", 'whats': "what's",
                'wont': "won't", 'ill': None, 'id': None, 'hes': "he's", 'shes': "she's", 'theyve': "they've", 'weve': "we've",
                'youll': "you'll", 'theyll': "they'll", 'itll': "it'll", 'wouldve': "would've", 'couldve': "could've", 'shouldve': "should've"}
VOCATIVE = {'grandma', 'grandpa', 'mom', 'mum', 'dad', 'mother', 'father', 'sir', 'madam', 'everyone', 'guys', 'friends', 'kids',
            'children', 'son', 'honey', 'darling', 'boss', 'doctor', 'teacher', 'class'}
BE = {'is': 'was', 'am': 'was', 'are': 'were'}
MODALS = {'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might', 'must', 'did', 'does', 'do', 'is', 'was', 'has', 'had', 'used', 'ought', 'dare', 'need'}
OBJECT = {'me': 'I', 'him': 'he', 'her': 'she', 'us': 'we', 'them': 'they'}

USAGE = [
    (r'\bfewer\b.*\bless\b|\bless\b.*\bfewer\b', 'Use **fewer** for things you can count ("fewer people", "fewer cars") and '
     '**less** for amounts you cannot count ("less water", "less time"). So: "fewer people".'),
    (r'\bwho\b.*\bwhom\b|\bwhom\b.*\bwho\b', 'Use **who** for the subject (the one doing it: "Who called?") and **whom** for '
     'the object (the one it is done to: "Whom did you call?", "to whom"). Quick test: if you could answer with "he", use '
     'who; if with "him", use whom.'),
    (r'\baffect\b.*\beffect\b|\beffect\b.*\baffect\b', '**Affect** is usually a verb, to influence something ("The rain '
     'affected the game"). **Effect** is usually a noun, the result ("The rain had an effect on the game"). Tip: '
     'Affect = Action, Effect = End result.'),
    (r'\bthen\b.*\bthan\b|\bthan\b.*\bthen\b', 'Use **than** to compare ("taller than me") and **then** for time or order '
     '("first this, then that").'),
    (r'\bits\b.*\bit\'?s\b|\bit\'s\b.*\bits\b', '**It\'s** means "it is" or "it has" ("It\'s raining"). **Its** shows '
     'possession, like his or her ("The dog wagged its tail").'),
    (r'\btheir\b.*\bthere\b|\bthere\b.*\btheir\b|\bthey\'?re\b', '**Their** shows possession ("their house"), **there** is a '
     'place or starts a sentence ("over there", "There is a book"), and **they\'re** means "they are" ("They\'re late").'),
    (r'\byour\b.*\byou\'?re\b|\byou\'re\b.*\byour\b', '**Your** shows possession ("your bag"); **you\'re** means "you are" '
     '("You\'re right").'),
    (r'\blie\b.*\blay\b|\blay\b.*\blie\b', '**Lie** means to rest flat and takes no object ("I lie down"; past: lay). '
     '**Lay** means to put something down and needs an object ("Lay the book on the table"; past: laid).'),
    (r'\bbetween you and (?:i|me)\b', '"Between you and **me**" is correct. "Between" is a preposition, so it takes the object '
     'form (me), even though "between you and I" is common in speech.'),
    (r'\b(?:a|an)\s+(?:apple|hour|university|apple)\b.*\b(?:a|an)\b|"a\s+\w+"\s+or\s+"an', 'Use **an** before a vowel *sound* '
     'and **a** before a consonant sound: "an apple", "an hour" (silent h), but "a university" (sounds like "you").'),
    (r'\bgood\b.*\bwell\b|\bwell\b.*\bgood\b', '**Good** is an adjective ("a good book", "I feel good"); **well** is the '
     'adverb ("She sings well") and also means healthy ("I am well").'),
    (r'\bloose\b.*\blose\b|\blose\b.*\bloose\b', '**Lose** is a verb, to misplace or not win ("Don\'t lose your keys"). '
     '**Loose** is an adjective, not tight ("a loose shirt").'),
    (r'\bcould of\b|\bcould have\b.*\bof\b', 'Write **could have** (often said "could\'ve"), never "could of". The same goes for '
     'should have and would have.'),
    (r'\bwhich\b.*\bthat\b|\bthat\b.*\bwhich\b', 'Use **that** for information you need to identify the thing ("The car that '
     'I bought is red") and **which**, with commas, for extra information ("My car, which is red, is fast").'),
    (r'\bme\b.*\b(?:i|myself)\b|\b(?:i|myself)\b.*\bme\b', 'Use **I** as the subject ("My friend and I went") and **me** as '
     'the object ("She called my friend and me"). Tip: remove the other person and see which sounds right ("I went", "she '
     'called me").'),
]

ASK_FIX = re.compile(r'(?i)^\s*(?:please\s+)?(?:can you\s+)?(?:correct|fix|check|proofread|improve|edit)(?:\s+(?:the|my))?(?:\s+(?:grammar|spelling|sentence|text|this|it))*'
                     r'(?:\s+(?:of|in|for))?(?:\s+(?:this|the|my)\s+(?:sentence|text|line))?\s*[:\-]\s*(.+)$|^\s*(?:correct|fix)\s+(?:this|the sentence)\s+(.+)$')
ASK_CHECK = re.compile(r'(?i)^\s*(?:is|was)\s+(?:this|the following)\s+(?:sentence\s+)?(?:grammatically\s+)?(?:correct|right|ok|okay|good english)\s*[:?\-]?\s*(.+)$'
                       r'|^\s*is\s+["“](.+?)["”]\s+(?:grammatically\s+)?(?:correct|right|ok)\s*\??\s*$')
ASK_PAST = re.compile(r'(?i)\b(?:make|put|change|turn|rewrite|write)\s+(?:this|the|it|the sentence|this sentence)?\s*(?:sentence\s+)?(?:in|into|to)?\s*(?:the\s+)?past(?: tense)?\s*[:\-]?\s*(.+)$')
ASK_PASSIVE = re.compile(r'(?i)\b(?:put|make|change|turn|rewrite|write)\s+(?:this|it|the sentence)?\s*(?:in|into|to)?\s*(?:the\s+)?passive(?: voice)?\s*[:\-]?\s*(.+)$')
ASK_ROLE = re.compile(r'(?i)^\s*what(?:\'s| is| are)\s+(?:the|a)?\s*(subject|verbs?|object|nouns?|adjectives?|adverbs?)\s+(?:in|of)\s+(.+?)\s*\??\s*$')
ASK_PUNCT = re.compile(r'(?i)\b(?:add|fix|correct|insert)\s+(?:the\s+)?punctuation(?:\s+(?:to|in))?\s*[:\-]?\s*(.+)$')
ASK_USAGE = re.compile(r'(?i)\b(?:difference between|when (?:do|should) (?:i|you) use|should i (?:say|use|write)|which is (?:correct|right)|'
                       r'is it\s+["“]?\w+|or\s+["“]?\w+["”]?\s*\?|correct to say|grammatically correct)')


def out(response, route):
    return dict(response=response, route='chat/grammar-' + route, sources=[], details=DETAILS)


def unquote(text):
    return re.sub(r'^\s*["“\'‘]|["”\'’]\s*$', '', text.strip()).strip()


def tokens(text):
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+|[^\sA-Za-z\d]", text)


def join(words):
    text = ''
    for w in words:
        if re.fullmatch(r'[.,!?;:)\]]', w) or (text.endswith(('(', '[')) and w):
            text += w
        else:
            text += (' ' if text else '') + w
    return text


def pos_of(word):
    """Parts of speech a word can have, from the dictionary, through every base form ('chased' -> chase -> verb)."""
    lower = word.lower()
    kinds = set()
    for base in dic.bases(lower):
        found, used = dic.senses(base)
        if used == base:
            kinds |= {row[0] for row in found}
    return kinds


def main_pos(word):
    """The most common part of speech of the word itself ('tail' -> noun, though it can be a verb)."""
    found, _ = dic.senses(word.lower())
    return found[0][0] if found else None


def is_verb(word):
    lower = word.lower()
    return lower in dic.IRREGULAR or lower in BE or lower in ('has', 'have', 'had', 'does', 'do', 'did', 'was', 'were') or 'verb' in pos_of(lower)


def third_person(verb):
    special = {'have': 'has', 'do': 'does', 'go': 'goes', 'be': 'is'}
    if verb in special:
        return special[verb]
    if re.search(r'(?:s|x|z|ch|sh|o)$', verb):
        return verb + 'es'
    if re.search(r'[^aeiou]y$', verb):
        return verb[:-1] + 'ies'
    return verb + 's'


def base_verb(word):
    lower = word.lower()
    special = {'has': 'have', 'does': 'do', 'goes': 'go', 'is': 'be', 'was': 'be', 'were': 'be', 'am': 'be', 'are': 'be'}
    if lower in special:
        return special[lower]
    for past_base, (past, participle) in dic.IRREGULAR.items():
        if lower in [p.strip() for p in past.split('/')] + [p.strip() for p in participle.split('/')]:
            return past_base.strip()
    for b in dic.bases(lower):
        if b != lower and (b in dic.IRREGULAR or 'verb' in pos_of(b)):
            return b
    return lower


def past(verb):
    base = base_verb(verb)
    if base == 'be':
        return 'were' if verb.lower() in ('are', 'were') else 'was'
    if base in dic.IRREGULAR:
        return dic.IRREGULAR[base][0].split('/')[0].strip()
    if base.endswith('e'):
        return base + 'd'
    if re.search(r'[^aeiou]y$', base):
        return base[:-1] + 'ied'
    if re.search(r'^[^aeiou]*[aeiou][bdgmnprt]$', base):
        return base + base[-1] + 'ed'
    return base + 'ed'


def participle(verb):
    base = base_verb(verb)
    if base in dic.IRREGULAR:
        return dic.IRREGULAR[base][1].split('/')[0].strip()
    return past(base)


def plural_noun(noun):
    return dic.plural(noun.lower())['response'].split('**')[3].split(' / ')[0]


def capitalised(word):
    """'london' -> 'London' when the dictionary only knows the word as a name."""
    if len(word) < 3 or word.lower() in ('may', 'will', 'can', 'mark', 'bill', 'rose', 'pat', 'sue', 'jack', 'grace', 'bob') or base_verb(word) != word.lower():
        return word
    found, _ = dic.senses(word.lower())
    names = [w for row in found for w in row[3] if w.lower() == word.lower()]
    if names and all(w[0].isupper() for w in names):
        return names[0]
    return word


def spell(word):
    lower = word.lower()
    if len(lower) < 4 or lower in CONTRACTIONS or not re.fullmatch(r'[a-z]+', lower) or dic.known(lower):
        return word
    candidates = [w for w in dic.frequent()[:40000] if abs(len(w) - len(lower)) <= 1 and w[0] == lower[0]]
    best = min(candidates, key=lambda w: (dic.edit_distance(lower, w, 2), candidates.index(w)), default=None)
    if best and dic.edit_distance(lower, best, 2) <= (1 if len(lower) < 7 else 2):
        return best
    return word


def correct(sentence):
    """(corrected sentence, [reasons])."""
    words = tokens(sentence)
    notes = []

    def note(text):
        if text not in notes:
            notes.append(text)

    # Spelling and missing apostrophes.
    for i, w in enumerate(words):
        lower = w.lower()
        if lower in CONTRACTIONS and CONTRACTIONS[lower]:
            if lower == 'wont' and i and words[i - 1].lower() in ('the', 'his', 'her', 'their', 'my'):
                continue
            words[i] = CONTRACTIONS[lower]
            note(f'"{w}" needs an apostrophe: {CONTRACTIONS[lower]}')
        elif lower == 'lets' and i + 1 < len(words) and is_verb(words[i + 1]) and 'noun' not in pos_of(words[i + 1]) | ({'noun'} if words[i + 1].lower() in ('me', 'him', 'her', 'us', 'them') else set()):
            words[i] = "let's" if i else "Let's"
            note('"lets" here means "let us": let\'s')
        elif re.fullmatch(r'[a-z]+', lower):
            fixed = spell(w)
            if fixed != w:
                words[i] = fixed
                note(f'spelling: {w} → {fixed}')
    # "me and him goes" -> "he and I go"; "me and my friend was" -> "my friend and I were".
    text = ' '.join(words)
    pair = re.match(r'(?i)^(me|him|her|us|them)\s+and\s+(me|him|her|us|them|my \w+|the \w+|\w+)\b', text)
    if pair:
        first, second = pair[1].lower(), pair[2]
        second_subject = OBJECT.get(second.lower(), second)
        first_subject = OBJECT.get(first, first)
        if first_subject == 'I':
            replacement = f'{second_subject} and I'
        else:
            replacement = f'{first_subject} and {second_subject}'
        words = tokens(replacement + text[pair.end():])
        note('use the subject forms (I, he, she, we, they) for the people doing the action, and put yourself last: '
             f'"{replacement}"')
        compound = True
    else:
        compound = bool(re.match(r'(?i)^(?:\w+ )?\w+ and (?:\w+ )?\w+\b', text) and not re.match(r'(?i)^(?:and|but|or)\b', text))
    # Wrong plurals of irregular nouns: childs -> children, mouses -> mice.
    wrong_plural = {base + 's': plural.split(' / ')[0] for base, plural in dic.IRREGULAR_PLURAL.items()
                    if base.strip() == base and not plural.startswith(base + 's') and plural != base}
    for i, w in enumerate(words):
        if w.lower() in wrong_plural:
            words[i] = wrong_plural[w.lower()]
            note(f'the plural of "{w.lower()[:-1]}" is irregular: {words[i]}')
    # A noun subject and its verb: "The children plays" -> play, "The dog run" -> runs.
    lowered = [w.lower() for w in words]
    m = 0
    while m < len(lowered) and lowered[m] in ('the', 'a', 'an', 'my', 'his', 'her', 'our', 'their', 'your', 'this', 'that', 'these', 'those'):
        m += 1
    if 0 < m < len(lowered) - 1 and 'and' not in lowered[:m + 2]:
        noun, verb = lowered[m], lowered[m + 1]
        if 'noun' in pos_of(noun) and main_pos(verb) != 'noun' or verb in ('is', 'are', 'was', 'were', 'has', 'have'):
            # Plural: an irregular plural, or an -s word that is not itself a dictionary word ("dogs" is not; "news",
            # "bus" and "physics" are, so they stay singular).
            plural = noun in {p.split(' / ')[0] for p in dic.IRREGULAR_PLURAL.values()} or (
                noun.endswith('s') and not noun.endswith('ss') and dic.senses(noun)[1] != noun and lowered[m - 1] != 'this')
            fixed = None
            if plural and verb in ('is', 'was', 'has', 'does', 'goes'):
                fixed = {'is': 'are', 'was': 'were', 'has': 'have', 'does': 'do', 'goes': 'go'}[verb]
            elif plural and re.fullmatch(r'[a-z]+s', verb) and base_verb(verb) != verb and third_person(base_verb(verb)) == verb:
                fixed = base_verb(verb)
            elif not plural and lowered[m - 1] not in ('these', 'those') and verb in ('are', 'were', 'have', 'do'):
                fixed = {'are': 'is', 'were': 'was', 'have': 'has', 'do': 'does'}[verb]
            elif not plural and lowered[m - 1] not in ('these', 'those') and verb == base_verb(verb) and verb in dic.IRREGULAR | {'run': 0} \
                    and verb != past(verb):
                fixed = third_person(verb)
            if fixed:
                words[m + 1] = fixed
                note(f'"{words[m]}" is {"plural" if plural else "singular"}, so the verb is "{fixed}"')
    # Double negatives: "don't know nothing" -> "don't know anything".
    text_now = ' '.join(w.lower() for w in words)
    if re.search(r"n't\b|\bnot\b|\bnever\b", text_now):
        for i, w in enumerate(words):
            swap = {'nothing': 'anything', 'nobody': 'anybody', 'nowhere': 'anywhere', 'none': 'any'}.get(w.lower())
            if swap and i and any(re.search(r"n't$|^not$|^never$", x.lower()) for x in words[:i]):
                words[i] = swap
                note(f'one negative is enough: "{swap}", not "{w.lower()}" after a "not"')
    # Two people or things joined by "and" take a plural verb: "He and I go", "My friend and I were".
    lowered = [w.lower() for w in words]
    if 'and' in lowered[:5] and lowered.index('and') > 0:
        start = lowered.index('and') + 1
        for j in range(start + 1, min(len(words), start + 4)):
            w = lowered[j]
            fixed = {'was': 'were', 'is': 'are', 'has': 'have', 'does': 'do', 'goes': 'go', "doesn't": "don't", "isn't": "aren't",
                     "wasn't": "weren't", 'am': 'are'}.get(w)
            if not fixed and re.fullmatch(r'[a-z]+s', w) and base_verb(w) != w and third_person(base_verb(w)) == w:
                fixed = base_verb(w)
            if fixed:
                words[j] = fixed
                note(f'two subjects joined by "and" take a plural verb: "{fixed}", not "{w}"')
                break
            if is_verb(w) and main_pos(w) in ('verb', None):
                break
        compound = False
    # Subject-verb agreement on the first verb after a pronoun.
    for i, w in enumerate(words):
        lower = w.lower()
        prev = words[i - 1].lower() if i else ''
        subject_many = prev in SUBJECT_MANY or (compound and i > 2 and 'and' in [x.lower() for x in words[:i]] and
                                                not any(x.lower() in SUBJECT_ONE for x in words[:i]) and
                                                all(not is_verb(x) or x.lower() in ('and',) for x in words[:i - 1]))
        if prev in SUBJECT_ONE or subject_many:
            if lower in ('dont',) or lower == "don't":
                if prev in SUBJECT_ONE:
                    words[i] = "doesn't"
                    note(f'"{prev}" takes "doesn\'t", not "don\'t"')
                continue
            if subject_many and lower in ('was',) and prev != 'i':
                words[i] = 'were'
                note(f'a plural subject takes "were", not "was"')
            elif subject_many and lower == 'is':
                words[i] = 'are' if prev != 'i' else 'am'
                note(f'"{prev if prev else "they"}" takes "{words[i]}"')
            elif prev == 'i' and lower in ('has', 'is', 'are'):
                words[i] = {'has': 'have', 'is': 'am', 'are': 'am'}[lower]
                note(f'"I" takes "{words[i]}", not "{w}"')
            elif prev in SUBJECT_ONE and lower in ('have', 'are', 'were', 'do') and prev not in ('i', 'you'):
                words[i] = {'have': 'has', 'are': 'is', 'were': 'was', 'do': 'does'}[lower]
                note(f'"{prev}" takes "{words[i]}", not "{w}"')
            elif subject_many and lower in ('has',):
                words[i] = 'have'
                note(f'a plural subject takes "have", not "has"')
            elif subject_many and re.fullmatch(r'[a-z]+s', lower) and is_verb(lower) and lower not in ('was', 'has', 'is', 'does', 'goes') and base_verb(lower) != lower:
                fixed = base_verb(lower)
                if third_person(fixed) == lower:
                    words[i] = fixed
                    note(f'a plural subject takes "{fixed}", not "{w}"')
            elif subject_many and lower in ('goes', 'does'):
                words[i] = lower[:-2]
                note(f'a plural subject takes "{words[i]}", not "{w}"')
            elif prev in SUBJECT_ONE and re.fullmatch(r'[a-z]+', lower) and lower not in MODALS and is_verb(lower) \
                    and base_verb(lower) == lower and past(lower) != lower and main_pos(lower) != 'adjective':
                words[i] = third_person(lower)
                note(f'"{prev}" takes "{words[i]}", not "{w}"')
            break
        if is_verb(w) and i > 3:
            break
    # Irregular verbs given a regular -ed ending: runned -> ran, goed -> went.
    for i, w in enumerate(words):
        lower = w.lower()
        if lower.endswith('ed') and len(lower) > 3:
            for stem in (lower[:-2], lower[:-1], lower[:-3] if re.search(r'(.)\1ed$', lower) else None):
                if stem and stem in dic.IRREGULAR and dic.IRREGULAR[stem][0].split('/')[0].strip() not in (lower,):
                    words[i] = dic.IRREGULAR[stem][0].split('/')[0].strip()
                    note(f'"{stem}" is irregular: its past tense is {words[i]}, not {w}')
                    break
    # A past participle used alone as the past tense: "I seen" -> "I saw" (no have/has/had/be before it).
    participles = {dic.IRREGULAR[b][1].split('/')[0].strip(): dic.IRREGULAR[b][0].split('/')[0].strip() for b in dic.IRREGULAR
                   if dic.IRREGULAR[b][1] != dic.IRREGULAR[b][0]}
    for i, w in enumerate(words):
        lower = w.lower()
        if i and lower in participles and words[i - 1].lower() in SUBJECT_ONE | SUBJECT_MANY | {'he', 'she', 'they'}:
            words[i] = participles[lower]
            note(f'"{lower}" needs "have" before it; on its own the past tense is "{words[i]}"')
    # "were" for "where": "I don't know were he is".
    for i, w in enumerate(words):
        if w.lower() == 'were' and i and words[i - 1].lower() in ('know', 'sure', 'wonder', 'see', 'ask', 'tell', 'idea', 'remember', 'find', 'show', 'guess', 'from', 'is', 'and') \
                and i + 1 < len(words) and words[i + 1].lower() in SUBJECT_ONE | SUBJECT_MANY | {'the', 'my', 'your', 'his', 'her', 'our', 'their', 'you'}:
            words[i] = 'where'
            note('"where" (a place), not "were" (a form of "be")')
    # Numbers with singular nouns: "two cat" -> "two cats".
    for i in range(len(words) - 1):
        lower, nxt = words[i].lower(), words[i + 1]
        if (lower in NUMBERS or (lower.isdigit() and int(lower) > 1)) and re.fullmatch(r'[a-z]+', nxt) and 'noun' in pos_of(nxt) \
                and not nxt.endswith('s') and dic.plural(nxt)['response'].split('**')[3] != nxt and not is_verb(nxt) or \
                (lower in NUMBERS or (lower.isdigit() and int(lower) > 1)) and nxt in ('cat', 'dog', 'apple', 'book', 'car', 'friend', 'day'):
            fixed = plural_noun(nxt)
            if fixed != nxt:
                words[i + 1] = fixed
                note(f'after "{words[i]}" the noun is plural: {fixed}')
    # Commonly confused words.
    for i, w in enumerate(words):
        lower = w.lower()
        nxt = words[i + 1].lower() if i + 1 < len(words) else ''
        nxt2 = words[i + 2].lower() if i + 2 < len(words) else ''
        if lower == 'their' and nxt in ('is', 'are', 'was', 'were', "'s"):
            words[i] = 'there' if i else 'There'
            note('"there is/are" (something exists), not "their" (belonging to them)')
        elif lower == 'their' and nxt.endswith('ing') and base_verb(nxt) != nxt:
            words[i] = "they're" if i else "They're"
            note('"they\'re" (they are), not "their"')
        elif lower == 'there' and nxt and 'noun' in pos_of(nxt) and not is_verb(nxt) and nxt not in ('is', 'are', 'was', 'were') and i and words[i - 1].lower() not in ('over', 'in', 'from', 'out', 'up', 'down', 'is', 'are'):
            words[i] = 'their'
            note('"their" shows belonging (their car), not "there"')
        elif lower == "it's" and nxt and main_pos(nxt) == 'noun' and nxt not in ('a', 'an', 'the', 'not', 'been', 'going', 'time'):
            words[i] = 'its'
            note('"its" shows belonging (its tail); "it\'s" means "it is"')
        elif lower == 'its' and nxt in ('a', 'an', 'the', 'not', 'been', 'going', 'raining', 'my', 'your', 'so', 'very', 'too', 'time', 'ok', 'okay', 'true', 'fine'):
            words[i] = "it's" if i else "It's"
            note('"it\'s" means "it is"; "its" only shows belonging')
        elif lower == 'your' and nxt in ('welcome', 'right', 'wrong', 'going', 'not', 'a', 'the', 'so', 'very', 'late', 'here'):
            words[i] = "you're" if i else "You're"
            note('"you\'re" means "you are"; "your" shows belonging')
        elif lower == 'then' and i and re.search(r'(?:er|more|less|better|worse|rather|other)$', words[i - 1].lower()):
            words[i] = 'than'
            note('use "than" to compare (bigger than), not "then"')
        elif lower == 'of' and i and words[i - 1].lower() in ('could', 'should', 'would', 'must', 'might'):
            words[i] = 'have'
            note(f'"{words[i - 1].lower()} have", not "{words[i - 1].lower()} of"')
        elif lower in ('a', 'an') and nxt and re.fullmatch(r'[a-z]+', nxt):
            vowel = (nxt[0] in 'aeiou' and nxt not in AN_EXCEPTIONS and not nxt.startswith(('uni', 'use', 'eu'))) or nxt in A_EXCEPTIONS
            right = 'an' if vowel else 'a'
            if lower != right:
                words[i] = right if w.islower() else right.capitalize()
                note(f'"{right} {nxt}": use "an" before a vowel sound and "a" before a consonant sound')
    # Capitals: sentence start, "I", names; end punctuation.
    for i, w in enumerate(words):
        if w == 'i' or w.startswith("i'"):
            words[i] = 'I' + w[1:]
            note('"I" is always a capital letter')
        elif i and re.fullmatch(r'[a-z]+', w):
            named = capitalised(w)
            if named != w:
                words[i] = named
                note(f'names take a capital letter: {named}')
    if words and words[0][0].islower():
        words[0] = words[0][0].upper() + words[0][1:]
        note('a sentence starts with a capital letter')
    if words and words[-1] not in '.!?':
        question = words[0].lower() in ('is', 'are', 'do', 'does', 'did', 'can', 'could', 'will', 'would', 'what', 'who', 'where', 'when', 'why', 'how', 'which', 'should')
        words.append('?' if question else '.')
        note('a sentence ends with a full stop' + (' (or a question mark for a question)' if question else ''))
    return join(words), notes


def fix_reply(sentence):
    sentence = unquote(sentence)
    if not sentence or len(sentence) > 400:
        return None
    fixed, notes = correct(sentence)
    if not notes:
        return out(f'I found no mistakes in "{sentence}". It looks correct to me (I check common errors: agreement, '
                   'articles, confused words, verb forms, spelling and capitals).', 'ok')
    only_style = all(n.startswith(('a sentence starts', 'a sentence ends')) for n in notes)
    lead = 'Corrected' if not only_style else 'Almost correct, just tidied'
    return out(f'{lead}: **{fixed}**\n\nWhat I changed:\n' + '\n'.join(f'- {n[0].upper() + n[1:]}.' for n in notes), 'fixed')


def check_reply(sentence):
    sentence = unquote(sentence)
    known_issue = usage_reply(sentence)            # "between you and I", "could of": a usage note answers it best
    if known_issue and re.search(r'(?i)\bbetween you and i\b|\bcould of\b|\bshould of\b|\bwould of\b', sentence):
        return known_issue
    fixed, notes = correct(sentence)
    real = [n for n in notes if not n.startswith(('a sentence starts', 'a sentence ends'))]
    if not real:
        return out(f'Yes, "{sentence}" is correct.' + (' Just remember the capital letter and the full stop.' if notes else ''), 'ok')
    return out(f'Not quite. It should be: **{fixed}**\n\n' + '\n'.join(f'- {n[0].upper() + n[1:]}.' for n in real), 'fixed')


def subject_and_verbs(sentence):
    words = tokens(unquote(sentence))
    verbs = [w for w in words if re.fullmatch(r'[A-Za-z]+', w) and is_verb(w) and w.lower() not in ('a', 'an', 'the')
             and not ('noun' in pos_of(w) and words.index(w) and words[words.index(w) - 1].lower() in ('a', 'an', 'the', 'my', 'his', 'her', 'tall', 'big'))]
    # The main verb: the first verb-capable word after at least one noun or pronoun.
    main = None
    for i, w in enumerate(words):
        if i and w in verbs and any(x.lower() in SUBJECT_ONE | SUBJECT_MANY or 'noun' in pos_of(x) for x in words[:i]):
            if w.lower().endswith('ly') and 'adverb' in pos_of(w):
                continue
            main = i
            break
    if main is None:
        return None, [], words
    subject = ' '.join(words[:main])
    return subject, [words[main]] + [w for w in words[main + 1:] if w in verbs and not w.lower().endswith('ly') and 'noun' not in pos_of(w)][:2], words


def role_reply(role, sentence):
    subject, verbs, words = subject_and_verbs(sentence)
    role = role.lower().rstrip('s')
    if role == 'subject':
        if not subject:
            return out(f'I could not find the subject in "{unquote(sentence)}".', 'roles')
        return out(f'The subject is **{subject}**: who or what does the action ({verbs[0]}).', 'roles')
    if role == 'verb':
        if not verbs:
            return out(f'I could not find a verb in "{unquote(sentence)}".', 'roles')
        return out(f'The verb is **{verbs[0]}**' + (f' (base form: {base_verb(verbs[0])})' if base_verb(verbs[0]) != verbs[0].lower() else '')
                   + '. It is the action or state in the sentence.', 'roles')
    wanted = {'noun': 'noun', 'adjective': 'adjective', 'adverb': 'adverb', 'object': 'noun'}[role]
    found = [w for w in words if re.fullmatch(r'[A-Za-z]+', w) and wanted in pos_of(w) and w.lower() not in ('a', 'an', 'the')
             and (wanted != 'noun' or not (verbs and w == verbs[0]))]
    if role == 'object' and verbs:
        after = words[words.index(verbs[0]) + 1:]
        found = [w for w in after if 'noun' in pos_of(w) and w.lower() not in ('a', 'an', 'the')][-1:]
    if not found:
        return out(f'I could not find a{"n" if wanted[0] in "aeiou" else ""} {role} in "{unquote(sentence)}".', 'roles')
    return out(f'{"The " + role + " is" if len(found) == 1 else "The " + role + "s are"} **{", ".join(found)}**.', 'roles')


def past_reply(sentence):
    words = tokens(unquote(sentence))
    subject, verbs, _ = subject_and_verbs(sentence)
    if not verbs:
        return out(f'I could not find the verb to change in "{unquote(sentence)}".', 'tense')
    index = words.index(verbs[0])
    if words[index].lower() in ('will',) and index + 1 < len(words):
        words[index:index + 2] = [past(words[index + 1])]
    elif index + 1 < len(words) and words[index].lower() in BE and words[index + 1].lower().endswith('ing'):
        words[index] = past(words[index])
    else:
        words[index] = past(words[index])
    sentence_out, _ = correct(join(words))
    return out(f'In the past tense: **{sentence_out}**', 'tense')


def passive_reply(sentence):
    words = tokens(unquote(sentence).rstrip('.!'))
    subject, verbs, _ = subject_and_verbs(sentence)
    if not verbs or not subject:
        return out(f'I could not find a subject, verb and object in "{unquote(sentence)}".', 'voice')
    index = words.index(verbs[0])
    obj = ' '.join(words[index + 1:]).strip()
    if not obj:
        return out(f'"{unquote(sentence)}" has no object, so it cannot be made passive.', 'voice')
    verb = words[index].lower()
    plural_obj = obj.split()[-1].endswith('s') and not obj.split()[-1].endswith('ss')
    if verb == past(verb) or verb.endswith('ed') or (base_verb(verb) in dic.IRREGULAR and verb == dic.IRREGULAR[base_verb(verb)][0].split('/')[0].strip()):
        be = 'were' if plural_obj else 'was'
    else:
        be = 'are' if plural_obj else 'is'
    agent = subject[0].lower() + subject[1:] if subject.split()[0].lower() in ('the', 'a', 'an', 'my', 'his', 'her', 'our', 'their', 'this', 'that') else subject
    agent = {'i': 'me', 'he': 'him', 'she': 'her', 'we': 'us', 'they': 'them'}.get(agent.lower(), agent)
    obj = {'me': 'I', 'him': 'He', 'her': 'She', 'us': 'We', 'them': 'They'}.get(obj.lower(), obj)
    text = f'{obj[0].upper() + obj[1:]} {be} {participle(verb)} by {agent}.'
    return out(f'In the passive voice: **{text}**\n\n(The object, {obj.lower() if obj.islower() else obj}, becomes the subject; '
               f'the verb becomes "{be} {participle(verb)}"; the doer follows "by".)', 'voice')


def punctuation_reply(sentence):
    words = tokens(unquote(sentence))
    fixed, notes = correct(' '.join(words))
    parts = tokens(fixed)
    # A person spoken to at the end gets a comma: "Let's eat, Grandma!"
    for i in range(len(parts) - 1, 0, -1):
        if parts[i].lower() in VOCATIVE and parts[i - 1] not in ',':
            parts.insert(i, ',')
            parts[i + 1] = parts[i + 1].capitalize()
            notes.append(f'a comma before the person you are speaking to ("{parts[i + 1]}"), so it is not read as part of the action')
            if parts[-1] == '.' and parts[0].lower() in ("let's",):
                parts[-1] = '!'
            break
    return out(f'With punctuation: **{join(parts)}**\n\n' + '\n'.join(f'- {n[0].upper() + n[1:]}.' for n in notes), 'punctuation')


def usage_reply(text):
    lower = text.lower()
    for pattern, answer in USAGE:
        if re.search(pattern, lower):
            return out(answer, 'usage')
    return None


def reply(text):
    """A grammar answer, or None."""
    if not dic.db() or len(text) > 600 or '```' in text:
        return None
    for pattern, handler in ((ASK_PUNCT, punctuation_reply), (ASK_PASSIVE, passive_reply), (ASK_PAST, past_reply)):
        match = pattern.search(text)
        if match and match[1].strip():
            return handler(match[1])
    match = ASK_ROLE.match(text)
    if match:
        return role_reply(match[1], match[2])
    if ASK_USAGE.search(text):
        answer = usage_reply(text)
        if answer:
            return answer
    match = ASK_CHECK.match(text)
    if match:
        return check_reply(match[1] or match[2])
    match = ASK_FIX.match(text)
    if match:
        target = match[1] or match[2]
        if target and not re.search(r'\b(?:def|return|import|print\(|=)\b', target):
            return fix_reply(target)
    return None
