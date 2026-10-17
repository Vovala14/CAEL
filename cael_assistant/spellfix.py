"""CAEL spell fix (symbolic, no NN). Runs on every user message before routing (chat, emoji, image, fetch).
Vocabulary + frequency:
  * English word frequencies: hermitdave/FrequencyWords en_50k (OpenSubtitles 2018, CC BY-SA 4.0), cached in data/spell/.
  * Emoji captions: Noto + Blobmoji manifest names/CLDR keywords (Apache-2.0); OpenMoji annotations/tags if cached (CC BY-SA 4.0).
  * Fetched words (data/emoji_fetch/<word>) and a small list of apostrophe-less contractions.
Correction: unknown lowercase alphabetic tokens (len >= 3) -> candidates with weighted Damerau-Levenshtein <= 2
(<= 1 for len <= 4); adjacent-key substitutions cost 0.8, transpositions 0.8. Score = log10(freq) - 2.2 * distance.
Skipped: URLs, emails, numbers / tokens with digits, Capitalised tokens (proper nouns), tokens or bigrams that are a
Wikipedia title (opensearch, cached, 3 s timeout). Clear win (score gap >= 1.0) -> auto-correct; else 'Did you mean A or B?'."""
import json, math, re, threading, time, urllib.parse, urllib.request
from pathlib import Path
CAEL = Path(__file__).resolve().parent.parent; SP = CAEL / 'data' / 'spell'
FREQ_URL = 'https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/en/en_50k.txt'
CONTR = {'whats': 1e6, 'im': 1e6, 'dont': 1e6, 'cant': 1e6, 'wont': 5e5, 'isnt': 5e5, 'thats': 5e5, 'youre': 5e5, 'didnt': 5e5, 'doesnt': 5e5,
         'ive': 3e5, 'id': 3e5, 'ill': 3e5, 'hes': 3e5, 'shes': 3e5, 'theyre': 3e5, 'wasnt': 3e5, 'arent': 3e5, 'couldnt': 2e5, 'wouldnt': 2e5,
         'shouldnt': 2e5, 'lets': 3e5, 'theres': 3e5, 'heres': 2e5, 'whos': 2e5, 'hows': 1e5, 'wheres': 1e5, 'emoji': 1e5, 'emojis': 5e4, 'cael': 1e5}
RARE = 300; RATIO = 100
ROWS = ['qwertyuiop', 'asdfghjkl', 'zxcvbnm']
POS = {c: (r, i) for r, row in enumerate(ROWS) for i, c in enumerate(row)}
def adj(a, b):
    if a not in POS or b not in POS: return False
    (r1, c1), (r2, c2) = POS[a], POS[b]; return abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1 and (a != b)
def wdl(s, t, cap=2.0):
    n, m = len(s), len(t)
    if abs(n - m) > cap: return 99
    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): D[i][0] = float(i)
    for j in range(m + 1): D[0][j] = float(j)
    for i in range(1, n + 1):
        best = 99
        for j in range(1, m + 1):
            c = 0.0 if s[i - 1] == t[j - 1] else (0.8 if adj(s[i - 1], t[j - 1]) else 1.0)
            v = min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + c)
            if i > 1 and j > 1 and s[i - 1] == t[j - 2] and s[i - 2] == t[j - 1]: v = min(v, D[i - 2][j - 2] + 0.8)
            D[i][j] = v; best = min(best, v)
        if best > cap: return 99
    return D[n][m]
class Speller:
    def __init__(s):
        s.F = {}; s.lock = threading.Lock(); s.wiki = {}; s.load()
    def load(s):
        SP.mkdir(parents=True, exist_ok=True); fp = SP / 'en_50k.txt'
        if not fp.exists():
            from cael_unified.network import NETWORK
            fp.write_bytes(NETWORK.get(FREQ_URL, ttl=86400, timeout=8))
            (SP / 'SOURCES.md').write_text('en_50k.txt: hermitdave/FrequencyWords (OpenSubtitles 2018), content licence CC BY-SA 4.0\n', encoding='utf-8')
        for line in fp.read_text(encoding='utf-8').splitlines():
            p = line.split()
            if len(p) == 2 and p[0].isalpha(): s.F[p[0].lower()] = s.F.get(p[0].lower(), 0) + int(p[1])
        extra = set()
        for man in (CAEL / 'data' / 'emoji').glob('*/manifest.json'):
            try:
                for it in json.loads(man.read_text(encoding='utf-8'))['items']:
                    extra |= set(re.findall(r'[a-z]+', (it['name'] + ' ' + ' '.join(it.get('keywords', []))).lower()))
            except Exception: pass
        om = CAEL / 'data' / 'emoji_fetch' / '_index' / 'openmoji.json'
        if om.exists():
            for e in json.loads(om.read_text(encoding='utf-8')):
                extra |= set(re.findall(r'[a-z]+', (e.get('annotation', '') + ' ' + e.get('tags', '')).lower()))
        for d in (CAEL / 'data' / 'emoji_fetch').glob('*'):
            if d.is_dir() and not d.name.startswith('_'): extra.add(d.name.lower())
        for w in extra:
            if len(w) >= 2: s.F[w] = max(s.F.get(w, 0), 200)
        for w, f in CONTR.items(): s.F[w] = max(s.F.get(w, 0), int(f))
        s.bylen = {}
        for w, f in s.F.items():
            if f >= 3: s.bylen.setdefault(len(w), []).append(w)
    def is_wiki(s, title):
        k = title.lower()
        if k in s.wiki: return s.wiki[k]
        ok = False
        try:
            q = urllib.parse.urlencode(dict(action='opensearch', search=title, limit=3, namespace=0, format='json'))
            from cael_unified.network import NETWORK
            r = NETWORK.json('https://en.wikipedia.org/w/api.php?' + q, ttl=86400, timeout=3)
            ok = any(t.lower() == k for t in r[1])
        except Exception: ok = False
        s.wiki[k] = ok; return ok
    def cands(s, w):
        cap = 1.0 if len(w) <= 4 else 2.0; out = []
        for L in range(len(w) - int(cap), len(w) + int(cap) + 1):
            for c in s.bylen.get(L, []):
                if c[0] != w[0] and (len(w) <= 3 or c[:2] == w[:2] and False): pass
                d = wdl(w, c, cap)
                if d <= cap: out.append((math.log10(s.F[c]) - 2.2 * d, c, d))
        return sorted(out, reverse=True)[:5]
    def fix(s, text):
        """returns dict(text=corrected, changed=[(old,new)], ambiguous=None | dict(token, options=[a,b], texts=[ta,tb]))"""
        toks = list(re.finditer(r"https?://\S+|\S+@\S+|[A-Za-z']+|\d[\w.,:/-]*|\S", text)); words = [t.group(0) for t in toks]
        changed = []; amb = None; new = list(words)
        for i, t in enumerate(words):
            if not re.fullmatch(r"[a-z]+", t) or len(t) < 3: continue
            rare = t in s.F and s.F[t] < RARE   # real but rare word: only replaced by a far more frequent close word
            if t in s.F and not rare: continue
            prev = words[i - 1] if i and re.fullmatch(r"[A-Za-z]+", words[i - 1]) else None
            nxt = words[i + 1] if i + 1 < len(words) and re.fullmatch(r"[A-Za-z]+", words[i + 1]) else None
            cs = [c for c in s.cands(t) if c[1] != t]
            if rare: cs = [c for c in cs if c[2] <= 1.0 and s.F[c[1]] >= RATIO * s.F[t]]
            if not cs: continue
            if (prev and s.is_wiki(prev + ' ' + t)) or (nxt and s.is_wiki(t + ' ' + nxt)): continue   # multi-word names (tel aviv)
            if cs[0][2] > 1.0 and s.is_wiki(t): continue   # single-token name only protects when no close correction exists
            cs = sorted(((sc + ctx_bonus(c, words, i), c, d) for sc, c, d in cs), reverse=True)
            if len(cs) == 1 or cs[0][0] - cs[1][0] >= 1.0: new[i] = cs[0][1]; changed.append((t, cs[0][1]))
            elif amb is None: amb = dict(token=t, options=[cs[0][1], cs[1][1]], idx=i)
        def join(ws):
            out = text; off = 0
            for tk, w in zip(toks, ws):
                a, b = tk.span(); out = out[:a + off] + w + out[b + off:]; off += len(w) - (b - a)
            return out
        res = dict(text=join(new), changed=changed, ambiguous=None)
        if amb:
            texts = []
            for o in amb['options']:
                ws = list(new); ws[amb['idx']] = o; texts.append(join(ws))
            res['ambiguous'] = dict(token=amb['token'], options=amb['options'], texts=texts)
        return res
_S = [None]; _L = threading.Lock()
ROUTE_KW = set("weather temperature forecast time date president minister prime capital population currency leader king queen mayor "
               "score scores result results price prices news latest match game emoji portrait".split())
def ctx_bonus(c, words, i):
    """Symbolic context bias: route keywords +0.8; neighbouring-word patterns add more (no NN)."""
    lw = [w.lower() for w in words]; nxt = lw[i + 1] if i + 1 < len(lw) else ''; prv = lw[i - 1] if i else ''
    b = 0.8 if c in ROUTE_KW else 0.0
    if c in ('weather', 'temperature', 'forecast', 'time') and (nxt in ('in', 'at', 'for', 'today', 'now', 'outside') or prv in ('the', "today's")): b += 1.2
    if c in ('president', 'capital', 'population', 'currency', 'mayor', 'leader', 'king', 'queen') and nxt == 'of': b += 1.2
    if c in ('score', 'scores', 'result', 'results', 'news', 'price', 'prices') and ('latest' in lw or 'last' in lw or 'today' in lw or nxt in ('of', 'for', 'today', '')): b += 1.0
    return b
def get():
    with _L:
        if _S[0] is None: _S[0] = Speller()
        return _S[0]
