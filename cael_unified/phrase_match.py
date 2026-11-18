"""Word-overlap matching of a question to authored answers (BM25 with light stemming and synonyms; no model).

The exact patterns of python_answers / concepts / beginner stay first. This catches rewordings: 'get rid of duplicate words
but keep the order' finds the de-duplication answer through 'remove', 'duplicate', 'order', 'list'. A match must clear an
absolute score and beat the runner-up by a margin, so a vague question gets no answer rather than a wrong one.
"""
import math
import re
from collections import Counter

STOP = set('''a an the to of in on for and or is are be by with from it its this that these those i me my you your we our they them
their do does did how what which who whom why when where can could would should will shall may might must just so if then than
there here please want like get got need make made use using way ways python thing things some any all into about also only
very really still now one ones am was were has have had not no yes'''.split())
SYN = {
    'rid': 'remove', 'delete': 'remove', 'drop': 'remove', 'erase': 'remove', 'discard': 'remove', 'eliminate': 'remove',
    'duplicates': 'duplicate', 'dupes': 'duplicate', 'repeated': 'duplicate', 'unique': 'duplicate', 'distinct': 'duplicate',
    'capital': 'upper', 'uppercase': 'upper', 'caps': 'upper', 'lowercase': 'lower', 'small': 'lower',
    'dictionary': 'dict', 'dictionaries': 'dict', 'dicts': 'dict', 'map': 'dict', 'hashmap': 'dict',
    'array': 'list', 'arrays': 'list', 'lists': 'list',
    'text': 'string', 'str': 'string', 'strings': 'string', 'sentence': 'string', 'word': 'string', 'words': 'string',
    'size': 'length', 'len': 'length', 'count': 'length', 'many': 'length',
    'combine': 'merge', 'join': 'merge', 'concatenate': 'merge', 'glue': 'merge',
    'pause': 'sleep', 'wait': 'sleep', 'delay': 'sleep', 'seconds': 'sleep',
    'kind': 'type', 'datatype': 'type', 'isinstance': 'type',
    'biggest': 'max', 'largest': 'max', 'highest': 'max', 'maximum': 'max', 'smallest': 'min', 'lowest': 'min', 'minimum': 'min',
    'order': 'order', 'sorted': 'sort', 'ordering': 'order', 'arrange': 'sort',
    'save': 'write', 'store': 'write', 'output': 'write', 'load': 'read', 'open': 'read',
    'folder': 'directory', 'dir': 'directory',
    'number': 'int', 'integer': 'int', 'numbers': 'int', 'integers': 'int', 'digits': 'int',
    'cash': 'money', 'loan': 'debt', 'borrow': 'debt', 'borrowing': 'debt',
}


def stem(w):
    for suf in ('ingly', 'ings', 'ing', 'edly', 'ied', 'ies', 'ed', 'es', 's'):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[:-len(suf)] + ('y' if suf in ('ied', 'ies') else '')
            break
    return w


def tokens(text):
    out = []
    for w in re.findall(r"[a-z_]+", (text or '').lower().replace("'", '')):
        if w in STOP or len(w) < 2:
            continue
        w = SYN.get(w, w)
        out.append(SYN.get(stem(w), stem(w)))
    return out


class Index:
    """BM25 over small authored documents: {id: text}."""

    def __init__(self, docs, k1=1.2, b=0.6):
        self.ids = list(docs)
        self.tf = [Counter(tokens(docs[i])) for i in self.ids]
        self.len = [sum(t.values()) or 1 for t in self.tf]
        self.avg = sum(self.len) / max(1, len(self.len))
        df = Counter(w for t in self.tf for w in t)
        n = len(self.ids)
        self.idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query):
        q = set(tokens(query))
        out = []
        for i, tf, ln in zip(self.ids, self.tf, self.len):
            s = 0.0
            for w in q:
                f = tf.get(w)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * ln / self.avg))
            out.append((s, i))
        return sorted(out, reverse=True)

    def best(self, query, least=3.0, margin=1.15, allowed=None):
        ranked = [(s, i) for s, i in self.scores(query) if allowed is None or i in allowed]
        if not ranked or ranked[0][0] < least:
            return None
        if len(ranked) > 1 and ranked[1][0] > 0 and ranked[0][0] < margin * ranked[1][0]:
            return None
        return ranked[0][1]
