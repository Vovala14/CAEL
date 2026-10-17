"""CAEL assistant emoji tool v5: models/cael-emoji-64-v5 = 2x2-patch integer cellular automaton at 32x32 (emoji_ca_v9.py, no NN).
Class CA (Gibbs sweeps on learned neighbour counts, guided by caption-word counts) -> patch CA (codebook 2x2 palette patches) -> 64x64.
No-copy guard at run time: an output closer than 0.10 (RMS) to any training emoji is resampled hotter (up to 8 times)."""
import sys, re, time, json, math, zlib
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).resolve().parent; CAEL = HERE.parent
sys.path.insert(0, str(CAEL))
from cael_image.v6_region_ca import rgb2lab, lab2rgb
from cael_image.v4_multiscale_ca import nn as NN
MODEL = CAEL / 'models' / 'cael-emoji-64-v5' / 'model_emoji.pt'
GUARD = 0.10
STOP = {'a', 'an', 'the', 'of', 'with', 'and', 'in', 'on', 'for', 'to', 'at', 'by', 'emoji', 'emojis', 'icon', 'please', 'me', 'some'}
def toks(s): return [w for w in re.findall(r'[a-z0-9]+', s.lower()) if w not in STOP]
def _load(rel):
    from PIL import Image
    with Image.open(rel) as im:
        im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        return np.asarray(Image.alpha_composite(bg, im).convert('RGB').resize((64, 64), Image.Resampling.LANCZOS), dtype=np.uint8)
def _train_images(a):
    # rebuild the exact TRAIN split used by emoji_ca_v9 (for the no-copy guard)
    items = []
    for src in a['sources'].split(','):
        d = CAEL / a['data_root'] / src; m = json.load(open(d / 'manifest.json', encoding='utf-8'))
        for it in m['items']: items.append(dict(path=d / it['file'], base=src + ':' + it['base']))
    bn = lambda i: i['base'].split(':', 1)[1]
    nb = sorted({i['base'] for i in items if i['base'].startswith('noto:')}); rng = np.random.default_rng(a['seed']); rng.shuffle(nb)
    hold = {b.split(':', 1)[1] for b in nb[:max(8, int(len(nb) * a['holdout']))]}; nset = {b.split(':', 1)[1] for b in nb}
    hold |= {bn(i) for i in items if bn(i) not in nset and zlib.crc32(bn(i).encode()) % 1000 < a['holdout'] * 1000}
    return torch.from_numpy(np.stack([_load(i['path']) for i in items if bn(i) not in hold]))
class EmojiTool:
    def __init__(s): s.m = None
    def ensure(s):
        if s.m is not None: return s.m
        ck = torch.load(MODEL, map_location='cpu', weights_only=False); a = ck['args']; m = type('M', (), {})()
        m.a = a; m.pal = ck['pal']; m.cb = ck['cb']; m.cls_of = ck['cls_of']; m.C = a['classes']; m.K = len(m.cb); m.bgc = ck['bgc']
        m.WP = ck['WP'].to_dense(); m.vocab = {w: i for i, w in enumerate(ck['vocab'])}; m.idf = ck['idf']; m.srcs = a['sources'].split(',')
        gl = ck['Gt'].float() + 0.5; m.gl = gl / gl.sum(1, keepdim=True)
        Nf = ck['Nt'].float() + 0.1; m.Nf = Nf / Nf.sum(1, keepdim=True)
        P = ck['PPt'].float() + 0.01; m.PPf = P / P.sum(2, keepdim=True)
        m.T = _train_images(a); s.m = m; return m
    def encode(s, words, style):
        m = s.m
        for src in [style] + [x for x in m.srcs if x != style]:
            e = [(m.vocab[f'{src}|{w}'], m.idf[f'{src}|{w}']) for w in words if f'{src}|{w}' in m.vocab]
            if e: return e
        return []
    def _nbr(s, x, fill):
        p = torch.nn.functional.pad(x.unsqueeze(1).float(), (1, 1, 1, 1), value=fill).squeeze(1).long()
        return p[:, :-2, 1:-1], p[:, 1:-1, 2:], p[:, 2:, 1:-1], p[:, 1:-1, :-2]
    def _gen(s, wl, seed, boost=0.0):
        m = s.m; a = m.a; C = m.C; gg = torch.Generator().manual_seed(seed); B = len(wl); rows = []
        for ws in wl:
            if not ws: rows.append(m.gl); continue
            acc = 0; tw = 0
            for w, wt in ws:
                h = m.WP[w].float() + 0.05; acc = acc + wt * h / h.sum(1, keepdim=True); tw += wt
            rows.append((1 - a['cond_mix']) * acc / tw + a['cond_mix'] * m.gl)
        pr = torch.stack(rows)
        guide = (pr / m.gl).clamp(1 / a['cclamp'], a['cclamp']) ** a['calpha'] * m.gl
        x = torch.multinomial(pr.reshape(-1, C), 1, generator=gg).reshape(B, 32, 32)
        yy, xx = torch.meshgrid(torch.arange(32), torch.arange(32), indexing='ij'); chk = ((yy + xx) % 2).bool()
        for sw in range(a['csweeps']):
            for par in (False, True):
                n_, e_, s_, w_ = s._nbr(x, m.bgc); c_ = ((n_ * C + e_) * C + s_) * C + w_
                lp = torch.log(m.Nf[c_]) + torch.log(guide.reshape(B, 32, 32, C))
                t = (a['ctemp'] + boost) * (1 if sw < a['csweeps'] - 2 else 0.6)
                new = torch.multinomial(torch.softmax(lp / t, -1).reshape(-1, C), 1, generator=gg).reshape(B, 32, 32)
                x = torch.where((chk == par).unsqueeze(0), new, x)
        n_, e_, s_, w_ = s._nbr(x, m.bgc)
        mk = (n_ == x).long() * 8 + (e_ == x).long() * 4 + (s_ == x).long() * 2 + (w_ == x).long()
        pp = torch.softmax(torch.log(m.PPf[x, mk]) / (a['ptemp'] + boost), -1)
        p = torch.multinomial(pp.reshape(-1, m.K), 1, generator=gg).reshape(B, 32, 32)
        img = m.cb[p].reshape(B, 32, 32, 2, 2).permute(0, 1, 3, 2, 4).reshape(B, 64, 64)
        return lab2rgb(m.pal[img]).clamp(0, 255).to(torch.uint8)
    def generate(s, subject, n=4, seed=None, outdir=None):
        m = s.ensure(); words = toks(subject); seed = int(time.time()) % 100000 if seed is None else seed
        styles = [m.srcs[i % len(m.srcs)] for i in range(n)]; wl = [s.encode(words, st) for st in styles]
        known = sorted({w for w in words if any(f'{x}|{w}' in m.vocab for x in m.srcs)})
        t0 = time.time(); G = s._gen(wl, seed); resampled = 0
        for t_ in range(1, 9):
            bad = NN(G, m.T) < GUARD
            if not bad.any(): break
            bi = torch.nonzero(bad).flatten().tolist(); resampled += len(bi)
            G[bi] = s._gen([wl[i] for i in bi], seed + 7919 * t_, 0.25 * t_)
        from PIL import Image
        outdir = Path(outdir or HERE / 'outputs' / 'emoji'); outdir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime('%Y%m%d_%H%M%S') + f'_{seed}'; tag = '_'.join(words)[:40] or 'emoji'; Gc = G.numpy(); paths = []
        for j in range(n):
            p = outdir / f'{stamp}_{tag}_{j}.png'; Image.fromarray(Gc[j]).resize((256, 256), Image.NEAREST).save(p); paths.append(str(p))
        grid = outdir / f'{stamp}_{tag}_grid.png'; Image.fromarray(np.concatenate(list(Gc), 1)).resize((256 * n, 256), Image.NEAREST).save(grid)
        return dict(paths=paths, grid=str(grid), words=words, known_words=known, unknown_words=[w for w in words if w not in known],
                    styles=styles, seed=seed, seconds=round(time.time() - t0, 1), guard_resampled=resampled, model='cael-emoji-64-v5')
