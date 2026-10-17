"""CAEL emoji online learning for unknown words (integer counts, no NN).
When a word is not in the emoji vocabulary (after concept mapping), fetch images of it from COMMERCIAL-OK sources only:
  emoji sets via emoji_fetch (OpenMoji CC BY-SA 4.0 with attribution, Twemoji CC BY 4.0, Emojitwo CC BY 4.0, Fluent MIT)
  + Wikimedia Commons icons/drawings licensed CC0 / Public domain / CC BY (only if the emoji sets give < 2 images).
Every item's licence is checked against ALLOW; anything else (NC, ND, unknown) is rejected.
Needs >= 2 accepted images. The images are quantized to the live model's palette/codebook classes and turned into integer
per-cell class counts (1024 cells x C classes) = the learned prior for that word; saved persistently to
models/cael-emoji-learned/<word>/ (counts.npy int32, classmaps.npy uint8, norm_*.png 64x64 for the no-copy guard,
sources.json with url/source/licence/attribution). Next request for the word uses the stored counts instantly (no network).
The emoji model's own no-copy guard compares outputs against these images too. Hook: install(EmojiTool) wraps fetched_prior."""
import re, json, time, hashlib, urllib.request, urllib.parse
from pathlib import Path
import numpy as np
from cael_unified.licensing import commercial_image_licence
from cael_unified.network import NETWORK
CAEL = Path(__file__).resolve().parent.parent; STORE = CAEL / 'models' / 'cael-emoji-learned'
UA = {'User-Agent': 'CAEL/0.2 (https://github.com/Vovala14/CAEL)'}
ALLOW = re.compile(r'^(CC0|CC0 1\.0|Public domain|PD.*|CC BY(-SA)? [1-4]\.0.*|CC BY(-SA)?|MIT|Apache[- ]2\.0)$', re.I)
COMMONS_ALLOW = re.compile(r'^(CC0|CC0 1\.0|Public domain|PD.*|CC BY [1-4]\.0.*|CC BY)$', re.I)   # Commons: CC0/PD/CC BY only (per owner rule)
def ok_licence(l): return commercial_image_licence(l)
def _key(word): return re.sub(r'[^a-z0-9]+', '', word.lower())   # 'kiwi bird' and 'kiwibird' share one entry
def _get(url, t=25):
    return NETWORK.get(url, ttl=86400, timeout=min(t, 8))
def commons(word, k=8):
    """Wikimedia Commons drawings (SVG rendered to PNG thumbs) for '<word> icon', CC0/PD/CC BY only."""
    q = urllib.parse.urlencode(dict(action='query', format='json', generator='search', gsrnamespace=6, gsrlimit=25,
                                    gsrsearch=f'{word} icon filetype:drawing', prop='imageinfo', iiprop='url|extmetadata', iiurlwidth=128))
    try: d = json.loads(_get('https://commons.wikimedia.org/w/api.php?' + q))
    except Exception: return []
    out = []; ws = set(re.findall(r'[a-z0-9]+', word.lower()))
    for p in sorted(d.get('query', {}).get('pages', {}).values(), key=lambda p: p.get('index', 99)):
        ii = (p.get('imageinfo') or [{}])[0]; md = ii.get('extmetadata', {}); lic = md.get('LicenseShortName', {}).get('value', '')
        title = p.get('title', '')
        if not ws <= set(re.findall(r'[a-z0-9]+', title.lower())): continue   # file name must contain the word(s)
        if not commercial_image_licence(lic) or 'BY-SA' in lic.upper(): continue
        art = re.sub(r'<[^>]+>', '', md.get('Artist', {}).get('value', ''))[:120]
        out.append(dict(url=ii.get('thumburl') or ii.get('url'), source='Wikimedia Commons', licence=lic.strip(), title=title,
                        attribution=f'{art} / {title} / {lic} / {ii.get("descriptionurl", "")}'))
        if len(out) >= k: break
    return out
def _norm(path_or_bytes):
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(path_or_bytes)) if isinstance(path_or_bytes, bytes) else Image.open(path_or_bytes)
    with im:
        im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); im = Image.alpha_composite(bg, im).convert('RGB')
        im.thumbnail((64, 64), Image.Resampling.LANCZOS); cv = Image.new('RGB', (64, 64), (255, 255, 255)); cv.paste(im, ((64 - im.width) // 2, (64 - im.height) // 2))
        return np.asarray(cv, dtype=np.uint8)
def _phash(m):
    import torch
    return hashlib.sha256(m.pal.numpy().tobytes() + m.cb.numpy().tobytes() + m.cls_of.numpy().tobytes()).hexdigest()[:16]
def _classify(m, imgs):
    """same quantization as emojigen.fetched_prior: Lab palette -> 2x2 codebook patch -> class id per 32x32 cell."""
    import torch
    from cael_image.v6_region_ca import rgb2lab
    F = torch.from_numpy(np.stack(imgs)); lab = rgb2lab(F.float())
    q = torch.cdist(lab.reshape(-1, 3), m.pal).argmin(1).reshape(len(F), 64, 64)
    blk = m.pal[q.reshape(-1, 32, 2, 32, 2).permute(0, 1, 3, 2, 4).reshape(-1, 32, 32, 4)].reshape(-1, 12)
    cbl = m.pal[m.cb].reshape(len(m.cb), 12); pid = torch.cdist(blk, cbl).argmin(1)
    return m.cls_of[pid].reshape(len(F), 1024).numpy().astype(np.int64), F
def index(store=None):
    p = Path(store or STORE) / 'index.json'
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {}
def learned(word, store=None): return _key(word) in index(store)
def learn(m, word, log=print, store=None):
    """Fetch commercial-OK images, require >= 2, store integer counts. Returns entry dict or None."""
    from cael_assistant import emoji_fetch as EF
    store = Path(store or STORE)
    items = []
    try:
        for it in EF.fetch(word):
            if ok_licence(it.get('licence', '')) and not it['source'].startswith('Openverse'):
                items.append(dict(it, data=Path(it['path']).read_bytes()))
            else: log(f'reject licence {it.get("licence")} {it.get("source")}')
    except Exception as e: log('emoji_fetch failed', type(e).__name__)
    nm = lambda t_: ' '.join(re.findall(r'[a-z0-9]+', (t_ or '').lower()))
    ex = [it for it in items if nm(it.get('title')) == nm(word)]
    if len(ex) >= 2: items = ex
    if len(items) < 2:
        for c in commons(word):
            try: items.append(dict(c, data=_get(c['url'])))
            except Exception: pass
    imgs, used = [], []
    for it in items:
        try: imgs.append(_norm(it['data'])); used.append({k: v for k, v in it.items() if k not in ('data', 'path', 'file')})
        except Exception: pass
    if len(imgs) < 2: return None
    cls, _ = _classify(m, imgs)
    cnt = np.zeros((1024, m.C), np.int32); np.add.at(cnt, (np.tile(np.arange(1024), len(cls)), cls.reshape(-1)), 1)
    d = store / _key(word); d.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    for i, im in enumerate(imgs): Image.fromarray(im).save(d / f'norm_{i:02d}.png')
    np.save(d / 'counts.npy', cnt); np.save(d / 'classmaps.npy', cls.astype(np.uint8))
    ent = dict(word=word, n_images=len(imgs), learned=time.strftime('%Y-%m-%d %H:%M'), palette=_phash(m), classes=int(m.C),
               licences=sorted({u['licence'] for u in used}), sources=used)
    (d / 'sources.json').write_text(json.dumps(ent, indent=1, ensure_ascii=False), encoding='utf-8')
    ix = index(store); ix[_key(word)] = {k: ent[k] for k in ('word', 'n_images', 'learned', 'palette', 'licences')}
    store.mkdir(parents=True, exist_ok=True); (store / 'index.json').write_text(json.dumps(ix, indent=1, ensure_ascii=False), encoding='utf-8')
    with open(store / 'learn_log.jsonl', 'a', encoding='utf-8') as f: f.write(json.dumps(dict(word=word, n=len(imgs), at=ent['learned'], licences=ent['licences'])) + '\n')
    return ent
def load(m, word, store=None):
    """-> (per-image priors list, F images tensor, used sources) from the store, recomputing classes if the palette changed."""
    import torch
    d = Path(store or STORE) / _key(word); ent = json.loads((d / 'sources.json').read_text(encoding='utf-8'))
    if not ent.get('sources') or not all(commercial_image_licence(item.get('licence')) for item in ent['sources']):
        raise ValueError('Stored references lack commercial-compatible licences')
    from PIL import Image
    imgs = [np.asarray(Image.open(p).convert('RGB'), dtype=np.uint8) for p in sorted(d.glob('norm_*.png'))]
    if ent.get('palette') == _phash(m) and (d / 'classmaps.npy').exists():
        cls = np.load(d / 'classmaps.npy').astype(np.int64); cnt = np.load(d / 'counts.npy'); F = torch.from_numpy(np.stack(imgs))
    else:   # model palette changed (e.g. new emoji version): recount from stored images, integer again
        cls, F = _classify(m, imgs); cnt = np.zeros((1024, m.C), np.int32); np.add.at(cnt, (np.tile(np.arange(1024), len(cls)), cls.reshape(-1)), 1)
    pr = torch.from_numpy(cnt).float() + 0.05; pr = pr / pr.sum(1, keepdim=True); per = []
    for j in range(len(cls)):
        c1 = torch.zeros(1024, m.C); c1[torch.arange(1024), torch.from_numpy(cls[j])] = 1.0
        x = 0.75 * c1 + 0.25 * pr + 0.02; per.append(x / x.sum(1, keepdim=True))
    used = [dict(s, url=s.get('url', ''), attribution=s.get('attribution', '')) for s in ent['sources']]
    return per, F, used
def install(tool):
    """Wrap EmojiTool.fetched_prior: learned store first (instant, offline), else learn online (commercial-OK only) then use it."""
    cls = type(tool)
    if getattr(cls, '_learn_hooked', False): return
    orig = cls.fetched_prior
    def fetched_prior(s, word):
        m = s.m
        try:
            if learned(word): r = load(m, word); s.last_learn = ('reused', word); return r
            ent = learn(m, word)
            if ent: r = load(m, word); s.last_learn = ('learned', word); return r
            s.last_learn = ('none', word); return None, None, []
        except Exception as e:
            print('emoji_learn error', type(e).__name__, e); s.last_learn = ('error', word)
            return orig(s, word)
    cls.fetched_prior = fetched_prior; cls._learn_hooked = True

def prepare(tool, subject):
    """Multi-word subject with unknown word(s) next to known ones (e.g. 'kiwi bird'): learn the whole phrase (commercial-OK only)
    and return a single-token subject ('kiwibird') so the generator uses the learned phrase prior. Else return subject unchanged."""
    import emojigen as EG
    m = tool.ensure(); ws = EG.toks(subject)
    inv = lambda w: any(f'{x}|{w}' in m.vocab for x in m.srcs) or (w in EG.HAND)
    if len(ws) < 2 or all(inv(w) for w in ws) or not any(inv(w) for w in ws): return subject
    phrase = ' '.join(ws)
    try:
        if learned(phrase) or learn(m, phrase): return _key(phrase)
    except Exception as e: print('emoji_learn prepare', type(e).__name__, e)
    return subject
