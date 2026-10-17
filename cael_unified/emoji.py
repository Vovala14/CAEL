# Modified for CAEL 0.2.1: frozen base inputs plus licensed online word learning.
"""CAEL 0.2.1 emoji tool: model bundle emoji/model.pt = 2x2-patch integer cellular automaton at 32x32 (emoji_ca_v9.py, no NN).
Class CA (Gibbs sweeps on learned neighbour counts, guided by caption-word counts) -> patch CA (codebook 2x2 palette patches) -> 64x64.
Out-of-vocabulary words: openly licensed images are fetched (emoji_fetch.py), quantized to the same palette/codebook,
and their average per-cell class histogram (integer counts) becomes the prior for the same CA sweeps.
No-copy guard at run time: an output closer than 0.10 (RMS) to any training emoji is resampled hotter (up to 8 times)."""
import sys, re, time, json, math, zlib
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).resolve().parent; CAEL = HERE.parent
sys.path.insert(0, str(CAEL)); sys.path.insert(0, str(CAEL / 'cael_image'))
from cael_image.v6_region_ca import rgb2lab, lab2rgb
from cael_image.v4_multiscale_ca import nn as NN
MODEL = CAEL / 'models' / 'cael-emoji-64-v7' / 'model_emoji.pt'
GUARD = 0.10
CLEAN = dict(mode_thr=2, iters=2, min_comp=4, pscale=1.0)   # v6 speckle post-pass (tuned on internal val; see research/emoji_iter_log.md)
MODEL_NAME = 'cael-emoji-64-v7'
SIL = True   # v7 silhouette + structure guidance (emoji_sil.py)
# OOV concept mapping: hand table (checked against the v5 caption vocabulary at load) -> then emoji-set fetch -> then WordNet 3.0 hypernyms
HAND = {**{w: 'mobile phone' for w in 'iphone smartphone android cellphone cellular mobile galaxy pixel'.split()},
        **{w: 'computer' for w in 'laptop macbook notebook chromebook pc desktop'.split()},
        **{w: 'automobile' for w in 'toyota bmw tesla honda ford audi mercedes ferrari porsche volkswagen vw sedan suv hatchback jeep nissan kia hyundai lamborghini'.split()},
        'puppy': 'dog', 'doggy': 'dog', 'kitten': 'cat', 'kitty': 'cat', 'tv': 'television', 'burger': 'hamburger', 'fries': 'french fries', 'soda': 'cup with straw',
        'motorbike': 'motorcycle', 'bike': 'bicycle', 'plane': 'airplane', 'aeroplane': 'airplane', 'jet': 'airplane', 'ship': 'ship', 'boat': 'sailboat',
        'cupcake': 'cupcake', 'tablet': 'computer', 'ipad': 'computer', 'headphone': 'headphone', 'headphones': 'headphone', 'earbuds': 'headphone',
        'football': 'soccer ball', 'soccer': 'soccer ball', 'basketball': 'basketball', 'bulb': 'light bulb', 'lightbulb': 'light bulb', 'love': 'heart', 'like': 'thumbs up'}
WNMAP = CAEL / 'data' / 'emoji_map' / 'wordnet_map.json'   # WordNet 3.0 (Princeton WordNet licence) hypernym -> vocab word
STOP = {'a', 'an', 'the', 'of', 'with', 'and', 'in', 'on', 'for', 'to', 'at', 'by', 'emoji', 'emojis', 'icon', 'please', 'me', 'some'}
def toks(s): return [w for w in re.findall(r'[a-z0-9]+', s.lower()) if w not in STOP]
class EmojiTool:
    def __init__(s, model_path, reference_path, online=True, online_store=None):
        s.m = None; s.model_path = Path(model_path); s.reference_path = Path(reference_path)
        s.learned = {}
        s.online = online
        s.online_store = Path(online_store or CAEL / 'data' / 'emoji_online_021')
        s._online_misses = {}
        s.last_learn = None
    def ensure(s):
        if s.m is not None: return s.m
        ck = torch.load(s.model_path, map_location='cpu', weights_only=True); a = ck['args']; m = type('M', (), {})()
        m.a = a; m.pal = ck['pal']; m.cb = ck['cb']; m.cls_of = ck['cls_of']; m.C = a['classes']; m.K = len(m.cb); m.bgc = ck['bgc']
        m.WP = ck['WP'].to_dense(); m.vocab = {w: i for i, w in enumerate(ck['vocab'])}; m.idf = ck['idf']; m.srcs = a['sources'].split(',')
        gl = ck['Gt'].float() + 0.5; m.gl = gl / gl.sum(1, keepdim=True)
        Nf = ck['Nt'].float() + 0.1; m.Nf = Nf / Nf.sum(1, keepdim=True)
        P = ck['PPt'].float() + 0.01; m.PPf = P / P.sum(2, keepdim=True)
        references = torch.load(s.reference_path, map_location='cpu', weights_only=True)
        m.T = references['pixels']; names = references['names']
        m.wn = {}  # No implicit reads from an installation's external data folder.
        s.learned = torch.load(s.model_path.parent / 'learned.pt', map_location='cpu', weights_only=True)
        from cael_image import emoji_sil as ES; ES.build_index(m, names, rgb2lab)
        s.m = m; return m
    def encode(s, words, style):
        m = s.m
        for src in [style] + [x for x in m.srcs if x != style]:
            e = [(m.vocab[f'{src}|{w}'], m.idf[f'{src}|{w}']) for w in words if f'{src}|{w}' in m.vocab]
            if e: return e
        return []
    def _nbr(s, x, fill):
        p = torch.nn.functional.pad(x.unsqueeze(1).float(), (1, 1, 1, 1), value=fill).squeeze(1).long()
        return p[:, :-2, 1:-1], p[:, 1:-1, 2:], p[:, 2:, 1:-1], p[:, 1:-1, :-2]
    def fetched_prior(s, word):
        if len(word) > 80 or not re.fullmatch(r'[a-z0-9 ]+', word):
            return None, None, []
        entry = s.learned.get(re.sub(r'[^a-z0-9]+', '', word.lower()))
        if entry is None:
            if not s.online or s._online_misses.get(word, 0) > time.time():
                return None, None, []
            from cael_assistant import emoji_learn as learning
            try:
                reused = learning.learned(word, store=s.online_store)
                if reused or learning.learn(s.m, word, store=s.online_store, log=lambda *args: None):
                    prior = learning.load(s.m, word, store=s.online_store)
                    s.last_learn = ('reused' if reused else 'learned', word)
                    return prior
            except (OSError, RuntimeError, ValueError, KeyError, TypeError):
                pass
            s._online_misses[word] = time.time() + 300
            if len(s._online_misses) > 256:
                s._online_misses.pop(next(iter(s._online_misses)))
            return None, None, []
        from .licensing import commercial_image_licence
        if not all(commercial_image_licence(item.get('licence')) for item in entry['sources']):
            return None, None, []
        pr = entry['counts'].float() + .05
        pr = pr / pr.sum(1, keepdim=True)
        per = []
        for row in entry['classmaps']:
            c1 = torch.zeros(1024, s.m.C)
            c1[torch.arange(1024), row.long()] = 1.
            weights = .75 * c1 + .25 * pr + .02
            per.append(weights / weights.sum(1, keepdim=True))
        return per, entry['pixels'], entry['sources']

    def prepare(s, subject):
        words = toks(subject)
        key = re.sub(r'[^a-z0-9]+', '', subject.lower())
        if key in s.learned:
            return key
        known = lambda word: any(f'{style}|{word}' in s.m.vocab for style in s.m.srcs) or word in HAND
        if s.online and 1 < len(words) <= 8 and not all(known(word) for word in words):
            # Keep a phrase intact when its online references are learned.
            if s.fetched_prior(' '.join(words))[0] is not None:
                return ' '.join(words)
        return subject
    def _gen(s, wl, seed, boost=0.0, extra=None, sil=None):
        m = s.m; a = m.a; C = m.C; gg = torch.Generator().manual_seed(seed); B = len(wl); rows = []
        for j, ws in enumerate(wl):
            ex = extra[j % len(extra)] if isinstance(extra, list) else extra
            if not ws and ex is not None: rows.append((1 - a['cond_mix']) * ex + a['cond_mix'] * m.gl); continue
            if not ws: rows.append(m.gl); continue
            acc = 0; tw = 0
            for w, wt in ws:
                h = m.WP[w].float() + 0.05; acc = acc + wt * h / h.sum(1, keepdim=True); tw += wt
            rows.append((1 - a['cond_mix']) * acc / tw + a['cond_mix'] * m.gl)
        from cael_image import emoji_clean as EC, emoji_sil as ES
        if not hasattr(m, 'outl'): m.outl = EC.outline_classes(m.pal, m.cb, m.cls_of, C)
        sil = sil if sil is not None else [None] * B
        rows = [ES.apply_prior(r, sil[j], C, m.bgc) for j, r in enumerate(rows)]
        pr = torch.stack(rows)
        guide = (pr / m.gl).clamp(1 / a['cclamp'], a['cclamp']) ** a['calpha'] * m.gl
        guide = torch.stack([ES.apply_guide(guide[j], sil[j], C, m.bgc, m.outl) for j in range(B)])
        p0 = pr * guide; p0 = p0 / p0.sum(-1, keepdim=True)
        x = torch.multinomial(p0.reshape(-1, C), 1, generator=gg).reshape(B, 32, 32)
        yy, xx = torch.meshgrid(torch.arange(32), torch.arange(32), indexing='ij'); chk = ((yy + xx) % 2).bool()
        for sw in range(a['csweeps']):
            for par in (False, True):
                n_, e_, s_, w_ = s._nbr(x, m.bgc); c_ = ((n_ * C + e_) * C + s_) * C + w_
                lp = torch.log(m.Nf[c_]) + torch.log(guide.reshape(B, 32, 32, C))
                t = (a['ctemp'] + boost) * (1 if sw < a['csweeps'] - 2 else 0.6)
                new = torch.multinomial(torch.softmax(lp / t, -1).reshape(-1, C), 1, generator=gg).reshape(B, 32, 32)
                x = torch.where((chk == par).unsqueeze(0), new, x)
        from cael_image import emoji_clean as EC
        if not hasattr(m, 'outl'): m.outl = EC.outline_classes(m.pal, m.cb, m.cls_of, C)
        x = EC.clean(x, C, m.outl, m.bgc, CLEAN['mode_thr'], CLEAN['iters'], CLEAN['min_comp'])
        for j in range(B):
            if sil[j] is not None: x[j][~sil[j]['mask']] = m.bgc
        n_, e_, s_, w_ = s._nbr(x, m.bgc)
        mk = (n_ == x).long() * 8 + (e_ == x).long() * 4 + (s_ == x).long() * 2 + (w_ == x).long()
        pp = torch.softmax(torch.log(m.PPf[x, mk]) / (a['ptemp'] * CLEAN['pscale'] + boost), -1)
        p = torch.multinomial(pp.reshape(-1, m.K), 1, generator=gg).reshape(B, 32, 32)
        img = m.cb[p].reshape(B, 32, 32, 2, 2).permute(0, 1, 3, 2, 4).reshape(B, 64, 64)
        return lab2rgb(m.pal[img]).clamp(0, 255).to(torch.uint8)
    def generate(s, subject, n=4, seed=None, outdir=None):
        m = s.ensure(); words = toks(subject); seed = int(time.time()) % 100000 if seed is None else seed
        mapped = []
        if not hasattr(m, 'wn'):
            try: m.wn = json.load(open(WNMAP, encoding='utf-8'))
            except Exception: m.wn = {}
        inv = lambda w: any(f'{x}|{w}' in m.vocab for x in m.srcs)
        nw = []
        for w in words:   # 1) hand concept table -> known CLDR words
            t = HAND.get(w)
            if not inv(w) and t and all(inv(x) for x in toks(t)): nw += toks(t); mapped.append((w, t, 'concept table'))
            else: nw.append(w)
        words = nw
        styles = [m.srcs[i % len(m.srcs)] for i in range(n)]; wl = [s.encode(words, st) for st in styles]
        known = sorted({w for w in words if any(f'{x}|{w}' in m.vocab for x in m.srcs)})
        t0 = time.time(); fetched = []; extra = None; Fimg = None; fetch_word = None
        unknown = [w for w in words if w not in known]
        if len(words) > 1 and unknown:
            extra, Fimg, fetched = s.fetched_prior(' '.join(words))
            if extra is not None:
                fetch_word = ' '.join(words); wl = [[] for _ in wl]
        if extra is None and not known and unknown:   # 2) out of vocabulary: licensed online emoji references
            for w in sorted(unknown, key=len, reverse=True)[:3]:
                extra, Fimg, fetched = s.fetched_prior(w)
                if extra is not None: fetch_word = w; break
            if extra is None:   # 3) WordNet hypernym -> known word (e.g. skyscraper -> building)
                for w in unknown:
                    t = m.wn.get(w)
                    if t and all(inv(x) for x in toks(t)):
                        mapped.append((w, t, 'WordNet')); words = [x for x in words if x != w] + toks(t)
                        styles_ = styles; wl = [s.encode(words, st) for st in styles_]; known = sorted({x for x in words if inv(x)}); break
        sil_src = None; S = [None] * n
        if SIL:
            from cael_image import emoji_sil as ES
            simgs = None
            if Fimg is not None: simgs = Fimg; sil_src = 'stored licensed emoji references'
            elif mapped and s.fetched_prior(mapped[-1][1])[0] is not None:   # mapped concept: emoji sets' layouts of the mapped name drive shape AND parts (approved override of v5 word prior)
                extra, Fimg, fetched = s.fetched_prior(mapped[-1][1]); fetch_word = mapped[-1][1]; wl = [[] for _ in wl]
                simgs = Fimg; sil_src = f'emoji sets for "{fetch_word}"'
            if simgs is not None:
                c_, f_ = ES.to_cls(m, simgs, rgb2lab); S = [ES.consensus(c_, f_, m.C)] * n
            elif known:
                idx = ES.match_train(m, words)
                if len(idx) >= 2: S = [ES.consensus(m.Tcls[idx], m.Tfg[idx], m.C)] * n; sil_src = f'{len(idx)} Noto/Blobmoji outlines'
        s.last_sil = S
        t1 = time.time(); G = s._gen(wl, seed, extra=extra, sil=S); resampled = 0
        def near(X):
            d = NN(X, m.T)
            if Fimg is not None: d = torch.minimum(d, NN(X, Fimg))
            return d
        for t_ in range(1, 9):
            bad = near(G) < GUARD
            if not bad.any(): break
            bi = torch.nonzero(bad).flatten().tolist(); resampled += len(bi)
            Sb = [S[i] for i in bi]
            if SIL and S[0] is not None and t_ >= 2:   # perturb: shift the silhouette by one cell
                from cael_image import emoji_sil as ES
                sh = [(1, 0), (0, 1), (-1, 0), (0, -1)][t_ % 4]
                Sb = [dict(x_, mask=torch.roll(x_['mask'], sh, (0, 1)), edge=torch.roll(x_['edge'], sh, (0, 1)), vote=torch.roll(x_['vote'], sh, (0, 1)), agree=torch.roll(x_['agree'], sh, (0, 1))) for x_ in Sb]
            G[bi] = s._gen([wl[i] for i in bi], seed + 7919 * t_, 0.25 * t_, extra=extra, sil=Sb)
        from PIL import Image
        outdir = Path(outdir or HERE / 'outputs' / 'emoji'); outdir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime('%Y%m%d_%H%M%S') + f'_{seed}'; tag = '_'.join(words)[:40] or 'emoji'; Gc = G.numpy(); paths = []
        for j in range(n):
            p = outdir / f'{stamp}_{tag}_{j}.png'; Image.fromarray(Gc[j]).resize((256, 256), Image.NEAREST).save(p); paths.append(str(p))
        grid = outdir / f'{stamp}_{tag}_grid.png'; Image.fromarray(np.concatenate(list(Gc), 1)).resize((256 * n, 256), Image.NEAREST).save(grid)
        return dict(paths=paths, grid=str(grid), words=words, known_words=known, unknown_words=[w for w in words if w not in known],
                    styles=styles, seed=seed, seconds=round(time.time() - t0, 1), fetch_seconds=round(t1 - t0, 1), guard_resampled=resampled, model=MODEL_NAME, mapped=mapped, silhouette=sil_src, n_fetch_imgs=(len(Fimg) if Fimg is not None else 0),
                    fetch_word=fetch_word, fetched=[dict(source=f['source'], licence=f['licence'], licence_url=f.get('licence_url', ''), title=f.get('title', ''), url=f['url'], attribution=f.get('attribution', '')) for f in fetched],
                    min_dist_fetched=(round(float(NN(G, Fimg).min()), 4) if Fimg is not None else None))
