"""Read advice out of free text: shared by the knowledge builder (research/thinking/build.py) and the thinker.

An answer like "You should avoid caffeine after 2pm, because it stays in your system for hours" becomes:
  action  'avoid caffeine after 2pm'   (an imperative, the same form for every source)
  key     'avoid|caffeine'             (verb + main nouns: answers that give the same advice share a key)
  reason  'it stays in your system for hours'
  negative False                       ('avoid' is already the verb; "don't drink coffee" -> negative 'drink|coffee')
Rule-based: sentence patterns plus parts of speech from the WordNet dictionary.
"""
from functools import lru_cache
import re

from . import dictionary as dic

DETERMINERS = {'a', 'an', 'the', 'your', 'my', 'his', 'her', 'their', 'our', 'this', 'that', 'these', 'those', 'some', 'any', 'it',
               'them', 'yourself', 'up', 'out', 'down', 'off', 'on', 'in', 'to', 'at', 'with', 'for', 'more', 'less', 'regular',
               'all', 'every', 'each', 'enough', 'plenty', 'lots', 'one', 'two', 'three', 'small', 'good', 'new', 'a lot'}
NOT_VERBS = {'i', 'it', 'this', 'that', 'there', 'if', 'when', 'yes', 'no', 'the', 'also', 'however', 'but', 'and', 'or', 'so', 'as',
             'my', 'your', 'one', 'some', 'most', 'many', 'people', 'what', 'how', 'why', 'well', 'in', 'on', 'at', 'for', 'with', 'by',
             'from', 'here', 'then', 'thanks', 'thank', 'hope', 'good', 'great', 'edit', 'update', 'note', 'source', 'sources', 'see',
             'like', 'just', 'even', 'still', 'only', 'now', 'today', 'first', 'second', 'third', 'finally', 'lastly', 'next', 'also',
             'other', 'another', 'both', 'each', 'all', 'any', 'no', 'not', 'very', 'really', 'much', 'more', 'less', 'once', 'after', 'before',
             'while', 'until', 'since', 'because', 'although', 'though', 'unless', 'whether', 'either', 'neither', 'can', 'will', 'would',
             'should', 'could', 'may', 'might', 'must', 'shall', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did',
             'mean', 'means', 'answer', 'question', 'example', 'e.g', 'ie', 'etc', 'ok', 'okay', 'sure', 'yeah', 'yep', 'nope', 'hi', 'hello', 'welcome'}
# Verbs people actually give advice with. An instruction must start with one of these (a word like "pay" or "level"
# can begin a statement or a heading just as easily: "Pay rises in the Australian context").
ADVICE_VERBS = set('''use avoid try keep make get take put add let give find ask tell talk go start stop set check buy clean wash rinse dry cook heat
cover cut mix stir water feed walk practice practise read write learn plan save spend pay focus work rest sleep eat drink exercise stretch
breathe relax call meet join look watch listen wear bring pack book store remove replace apply scrub soak season oil wipe brush train reward
praise ignore consider remember think decide prepare research show explain open close turn switch leave limit reduce increase cut lower
raise drop skip choose pick follow ask be stay move sit stand run jog swim lift build fix repair replace tighten loosen sand paint seal
test measure weigh count track record note list schedule set aim allow accept forgive apologize apologise thank compliment smile laugh
share help offer volunteer invite visit travel pack carry protect cover wrap freeze refrigerate thaw bake boil fry grill roast simmer
season taste serve slice chop peel grate whisk knead fold pour drain strain soak marinate sprinkle spread fill empty unplug plug restart
update install backup back download delete organize organise declutter tidy sort label clear sweep mop vacuum dust polish shine trim prune
plant repot mulch fertilize fertilise compost weed spray mist rotate expose shade hang place position hold grip press push pull release
breathe meditate journal write sketch draw sing play hum memorize memorise review revise study quiz teach explain summarize summarise
negotiate prepare rehearse dress arrive greet introduce mention emphasize emphasise highlight document email message text call phone
contact report escalate delegate prioritize prioritise batch break divide finish complete submit request demand insist refuse decline
say speak express describe admit acknowledge validate listen observe notice watch wait pause slow speed hurry relax calm cool warm
consult see visit hire ask contact find'''.split())
PRONOUNS = {'you', 'yourself', 'yourselves', 'they', 'them', 'it', 'its', 'we', 'us', 'doesn', 'don', 'isn', 'aren', 'didn', 'won', 'can',
            'things', 'thing', 'something', 'someone', 'anything', 'anyone', 'everything', 'everyone', 'nothing', 'way', 'lot', 'bit',
            'sure', 'using', 'doing', 'getting', 'making', 'going', 'time', 'times', 'what', 'which', 'whatever', 'people', 'person'}
STEMLESS = {'news', 'glasses', 'clothes', 'series', 'species', 'physics', 'mathematics'}
LEADS = [
    (r"^(?:you\s+)?(?:should|could|can|might want to|may want to|need to|have to|must|ought to|will want to|want to)\s+(?:also\s+|definitely\s+|really\s+|probably\s+|always\s+)?", ''),
    (r"^(?:it(?:'s| is)\s+(?:a good idea|best|important|helpful|useful|wise|worth it|key|essential|better)\s+to\s+)", ''),
    (r"^(?:it\s+helps\s+to\s+|it\s+can\s+help\s+to\s+|the key is to\s+|the trick is to\s+|my advice (?:is|would be) to\s+|the best (?:thing|way) is to\s+)", ''),
    (r"^(?:i\s+(?:would\s+)?(?:recommend|suggest|advise)\s+(?:that\s+you\s+)?(?:to\s+)?)", ''),
    (r"^(?:make sure (?:that )?(?:you\s+)?|be sure to\s+|remember to\s+|try (?:to|and)\s+|consider\s+|don'?t forget to\s+)", ''),
    (r"^(?:always\s+|just\s+|simply\s+|definitely\s+|also\s+|then\s+|first(?:ly)?,?\s+|second(?:ly)?,?\s+|finally,?\s+|lastly,?\s+)", ''),
]
NEGATIONS = [(r"^(?:don'?t|do not|never|avoid)\s+", 'avoid')]
REASON = re.compile(r"\s*(?:,\s*)?\b(?:because|since|so that|as this|as it|which (?:will|helps|makes|can)|in order to|otherwise|to make sure)\b\s*(.+)$", re.I)


@lru_cache(maxsize=1)
def verb_lemmas():
    connection = dic.db()
    if not connection:
        return set()
    return {row[0] for row in connection.execute("SELECT DISTINCT word FROM lemma WHERE pos='verb' AND word NOT LIKE '% %'")}


@lru_cache(maxsize=200_000)
def main_pos(word):
    found, base = dic.senses(word)
    return (found[0][0], base) if found else (None, word)


def stem(word):
    word = word.lower()
    if word in STEMLESS:
        return word
    pos, base = main_pos(word)
    return base if pos in ('noun', 'verb', 'adjective') else word


@lru_cache(maxsize=200_000)
def can_be_noun(word):
    for base in dic.bases(word):
        found, used = dic.senses(base, 'noun')
        if found and used == base:
            return True
    return False


@lru_cache(maxsize=200_000)
def noun_stem(word):
    word = word.lower()
    tries = [word]
    if word.endswith('ies'):
        tries.append(word[:-3] + 'y')
    if word.endswith('es') and re.search(r'(?:s|x|z|ch|sh|o)es$', word):
        tries.append(word[:-2])
    if word.endswith('s') and not word.endswith('ss'):
        tries.append(word[:-1])                # "phones" -> phone (not "phon")
    for base in tries + dic.bases(word):
        found, used = dic.senses(base, 'noun')
        if found and used == base:
            return base                       # "worries" -> worry, "phones" -> phone
    return word.lower()


def gerund_to_base(word):
    for b in dic.bases(word):
        if b != word and b in verb_lemmas():
            return b
    return word


def imperative(clause):
    """(action text, negative) when the clause gives advice, else None."""
    text = clause.strip().strip('*_-•· ').strip()
    text = re.sub(r'^\d+[.)]\s*', '', text)
    text = re.sub(r'^\*\*(.+?)\*\*[:.]?\s*', r'\1 ', text).strip()
    lower = text.lower()
    negative = False
    for pattern, replacement in NEGATIONS:
        if re.match(pattern, lower):
            lower = re.sub(pattern, '', lower)
            negative = True
            break
    for _ in range(2):                        # leads can stack: "You should also make sure to ..."
        for pattern, replacement in LEADS:
            lower = re.sub(pattern, replacement, lower)
    # "Avoid eating late", "I recommend reading", "Consider writing": the -ing verb becomes the advice.
    m = re.match(r"([a-z]+ing)\b(.*)$", lower)
    gerund_lead = negative or re.match(r"(?i)^\W*(?:i\s+(?:would\s+)?(?:recommend|suggest)|consider)\b", clause.strip())
    if m and gerund_lead and m[1] not in ('nothing', 'something', 'anything', 'everything', 'morning', 'evening', 'thing', 'spring', 'string'):
        base = gerund_to_base(m[1])
        if base != m[1]:
            lower = base + m[2]
    words = lower.split()
    if len(words) < 2 or len(words) > 22:
        return None
    first = re.sub(r"[^a-z']", '', words[0])
    if first in NOT_VERBS or first not in ADVICE_VERBS:
        return None
    second = re.sub(r"[^a-z']", '', words[1]) if len(words) > 1 else ''
    if second in ('is', 'are', 'was', 'were', 'has', 'have', 'had', 'can', 'will', 'would', 'should', 'may', 'might', 'of', "'s", 's'):
        return None                        # "Cast iron care is ...", "Pay rises of ...": a statement, not an instruction
    pos, _ = main_pos(first)
    if pos != 'verb' and second not in DETERMINERS and not (main_pos(second)[0] == 'noun') and not second.endswith('ly'):
        return None                        # "Water is ..." is a statement; "Water the plants" is advice
    if ':' in clause[:40] and not clause.strip().lower().startswith(first):
        return None                        # "Full disclosure: ...", "Level A: ..." are labels
    if first in ('avoid',) and not negative:
        negative = False
    action = re.sub(r'\s+', ' ', ' '.join(words)).strip(' .,;:!')
    return action, negative


def split_reason(action):
    m = REASON.search(action)
    if m and len(action[:m.start()].split()) >= 2:
        return action[:m.start()].strip(' ,;'), m[1].strip(' .')
    return action, ''


def key_of(action, negative):
    words = re.findall(r"[a-z]+", action.lower())
    verb = words[0]
    nouns = []
    for w in words[1:9]:
        if w in DETERMINERS or w in NOT_VERBS or w in PRONOUNS or len(w) < 3:
            continue
        pos, base = main_pos(w)
        if pos == 'noun' or (pos is None and w.isalpha()) or (pos == 'verb' and can_be_noun(w) and not w.endswith('ing')):
            nouns.append(noun_stem(w))
        if len(nouns) == 2:
            break
    if not nouns:
        if len(words) <= 3:                  # short advice without an object: "exercise regularly", "sleep more"
            return ('no:' if negative else '') + verb + '|' + (words[1] if len(words) > 1 else '')
        return None
    return ('no:' if negative else '') + verb + '|' + '+'.join(sorted(nouns))


def units(text):
    """Advice-sized pieces of an answer: list items and sentences."""
    out = []
    for line in re.split(r'\n+', text):
        line = line.strip()
        if not line:
            continue
        if re.match(r'^(?:[-*•]|\d+[.)])\s+', line):
            line = re.sub(r'^(?:[-*•]|\d+[.)])\s+', '', line)
            out.append(re.split(r'(?<=[.!?])\s+', line)[0])
            continue
        out += re.split(r'(?<=[.!?])\s+(?=[A-Z])', line)
    return [u.strip() for u in out if 8 <= len(u) <= 220]


SITUATIONAL = re.compile(r"\b(?:he|him|his|she|her|hers|op|the op|the person|this person|that person|the guy|this guy|the girl|"
                         r"the poster|the asker|the author|the employee|the candidate|the manager|i|i'm|i've|my|mine|we|our)\b|\?|https?://|@\w|\(.*\)\s*\(")


def advice_in(text):
    """[(key, action, reason, negative)] for the general advice an answer gives (not advice about one particular person)."""
    found = []
    for unit in units(text):
        for clause in re.split(r';\s+|\s+-\s+|:\s+(?=[a-z])', unit):
            got = imperative(clause)
            if not got:
                continue
            action, negative = got
            if SITUATIONAL.search(action):
                continue
            action, reason = split_reason(action)
            if reason and (len(reason.split()) < 4 or SITUATIONAL.search(reason)):
                reason = ''
            key = key_of(action, negative)
            if key:
                found.append((key, action, reason, negative))
    return found
