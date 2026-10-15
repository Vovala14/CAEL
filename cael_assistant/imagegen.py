"""CAEL assistant image tool: loads the i16 v10 integer-CA portrait model and generates 64x64 portraits.
No NN. The model is unconditional; colour words act only through a hand-written colour rule (generate2)."""
import sys, os, json, time, re
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).resolve().parent; CAEL = HERE.parent
sys.path.insert(0, str(CAEL))
_argv = sys.argv; sys.argv = [sys.argv[0]]
import cael_image.v10_prior_ca as v10
sys.argv = _argv
v9 = v10.v9
MODEL = CAEL / 'models' / 'cael-image-portrait-64-i16'
COND = HERE / 'model_cache' / 'prior_i16.pt'
I16 = dict(prior_alpha=1.6, sym_beta=0.6, temps='1,1,0.85,0.6,0.4', sweeps='8,6,6,6,8', guide='ratio', ratio_clamp=8.0,
           seed_mode='gibbs', guide_from=4, pad='clamp', prior_smooth=2.0)

def _setA():
    for k, v in I16.items(): setattr(v10.A, k, v)
    v9.PAD_MODE = 'clamp'

def load_model(dev=None):
    _setA()
    dev = dev or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if dev.type == 'cuda':
        tot = torch.cuda.get_device_properties(0).total_memory
        torch.cuda.set_per_process_memory_fraction(min(1.0, 13.5 * 2**30 / tot))
    ck = torch.load(MODEL / 'model_v9.pt', map_location='cpu', weights_only=False); a = ck['args']
    v9.HBITS.update(zip((8, 16, 32, 64), (int(x) for x in a['hash_bits'].split(','))))
    m = v10.GCA10(dev, a['palette'], a['coarse'], a['buckets'], a['min_count'])
    m.pal = ck['palette_lab'].to(dev); m.coarse = ck['coarse'].to(dev)
    m.seed = {k: v.to(dev) for k, v in ck['seed'].items()}
    m.t = {L: {k: v.to_dense().to(dev) for k, v in d.items()} for L, d in ck['tables'].items()}
    m.args = a
    return m

class ImageTool:
    def __init__(s):
        s.m = None; s.cond = None
    def ensure(s):
        if s.m is None:
            s.m = load_model()
            if not COND.exists(): raise RuntimeError(f'{COND} missing: it ships with the release')
            c = torch.load(COND, map_location='cpu', weights_only=False)
            s.m.prior = {L: v.to(s.m.dev) for L, v in c['prior'].items()}; s.m.sym = {L: v.to(s.m.dev) for L, v in c['sym'].items()}
            s.cond = c
        return s.m
    def cond_keys(s, words):
        """pick learned caption keys present in cond table (bigram colour+garment first, then single words)."""
        s.ensure(); have = s.cond.get('words', {}); keys = []
        for w in words:
            if w in have and have[w]['n'] >= s.cond['min_images']: keys.append(w)
        return keys
    def _wguide(s, keys, gamma, Lmin=16):
        m = s.m; out = {}
        for L in v9.LEVELS:
            if L < Lmin or not keys: continue
            base = m.prior[L].float() + 1.0; base = base / base.sum(1, keepdim=True)
            r = torch.ones_like(base)
            for k in keys:
                w = s.cond['words'][k]['prior'][L].to(m.dev).float()
                w = (w + 2.0 * base * 10) ; w = w / w.sum(1, keepdim=True)   # smoothed toward the overall prior
                r = r * (w / base).clamp(1 / 6, 6)
            out[L] = (r ** gamma).reshape(1, L, L, m.P)
        return out
    def generate(s, caption_words, n=4, oversample=3, seed=None, gamma=1.0, outdir=None, tag='img'):
        m = s.ensure(); keys = s.cond_keys(caption_words)
        wg = s._wguide(keys, gamma); orig = v10.GCA10.guide
        def guide(self, L, g, _o=orig): 
            b = _o(self, L, g); return b * wg[L] if L in wg else b
        m.guide = guide.__get__(m)
        seed = int(time.time()) % 100000 if seed is None else seed
        t0 = time.time()
        try:
            G = m.generate(n * oversample, seed)
        finally:
            del m.guide
        # rerank by average log-ratio of the word prior at 16x16 (selection, not conditioning)
        score = torch.zeros(len(G))
        if keys:
            g16 = m.quant(v9.rgb2lab(G.float()).reshape(-1, 4, 16, 4, 16, 3).mean((2, 4)))
            lr = torch.log(_wguide_plain(s, keys)).to(m.dev)  # (256,P)
            pos = torch.arange(256, device=m.dev).reshape(1, 16, 16).expand_as(g16)
            score = lr[pos, g16].mean((1, 2)).cpu()
        order = torch.argsort(score, descending=True)[:n]
        outdir = Path(outdir or HERE / 'outputs'); outdir.mkdir(parents=True, exist_ok=True)
        from PIL import Image
        stamp = time.strftime('%Y%m%d_%H%M%S'); paths = []
        Gc = G.cpu().numpy()
        for j, i in enumerate(order.tolist()):
            p = outdir / f'{stamp}_{tag}_{j}.png'; Image.fromarray(Gc[i]).resize((256, 256), Image.NEAREST).save(p)
            Image.fromarray(Gc[i]).save(outdir / f'{stamp}_{tag}_{j}_64.png'); paths.append(str(p))
        grid = outdir / f'{stamp}_{tag}_grid.png'
        sel = Gc[order.numpy()]; Image.fromarray(np.concatenate(list(sel), 1)).resize((256 * len(sel), 256), Image.NEAREST).save(grid)
        info = dict(paths=paths, grid=str(grid), keys_used=keys, seed=seed, sampled=len(G), kept=n, seconds=round(time.time() - t0, 1),
                    scores=[round(float(score[i]), 4) for i in order])
        if m.dev.type == 'cuda': info['peak_vram_gib'] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
        return info, G, order

def _wguide_plain(s, keys):
    m = s.m; L = 16; base = m.prior[L].float() + 1.0; base = base / base.sum(1, keepdim=True); r = torch.ones_like(base)
    for k in keys:
        w = s.cond['words'][k]['prior'][L].to(m.dev).float(); w = (w + 20.0 * base); w = w / w.sum(1, keepdim=True)
        r = r * (w / base).clamp(1 / 6, 6)
    return r

# ---- hand-written colour steering (rule, not learned): bias palette colours near a target Lab colour in a region ----
COLOR_LAB = {'red': (45, 62, 45), 'pink': (70, 40, 5), 'orange': (65, 35, 60), 'yellow': (85, 0, 75), 'green': (50, -45, 35),
             'blue': (40, 10, -50), 'purple': (38, 40, -40), 'brown': (38, 15, 25), 'black': (12, 0, 0), 'white': (93, 0, 2),
             'grey': (55, 0, 0), 'gray': (55, 0, 0), 'blonde': (75, 5, 35), 'golden': (70, 10, 55), 'silver': (75, 0, -2),
             'teal': (50, -30, -10), 'navy': (25, 8, -35), 'beige': (78, 4, 18), 'violet': (45, 35, -45), 'gold': (70, 10, 55)}
REGIONS = {'clothing': lambda y, x, L: y >= int(L * 0.78), 'hair': lambda y, x, L: (y < int(L * 0.22)) | ((y < int(L * 0.6)) & ((x < L // 6) | (x >= L - L // 6))),
           'background': lambda y, x, L: (y < int(L * 0.5)) & ((x < L // 8) | (x >= L - L // 8))}
def region_mask(name, L, dev):
    y = torch.arange(L, device=dev)[:, None].expand(L, L); x = torch.arange(L, device=dev)[None].expand(L, L)
    return REGIONS[name](y, x, L)
def colour_guide(m, targets, strength=4.0, Lmin=16):
    """targets: list of (region, colour). Returns {L: (1,L,L,P)} multiplicative boost."""
    out = {}
    for L in v9.LEVELS:
        if L < Lmin or not targets: continue
        G = torch.ones(L, L, m.P, device=m.dev)
        for reg, col in targets:
            t = torch.tensor(COLOR_LAB[col], device=m.dev, dtype=torch.float32)
            d = (m.pal - t).norm(dim=1)                         # (P,)
            boost = 1 + strength * torch.exp(-(d / 18.0) ** 2)  # palette colours near the target get up to (1+strength)x
            G[region_mask(reg, L, m.dev)] *= boost
        out[L] = G[None]
    return out
def colour_mix(m, targets, Lmin=8, Lmax=32):
    out = {}
    for L in v9.LEVELS:
        if L < Lmin or L > Lmax or not targets: continue
        W = torch.zeros(L, L, m.P, device=m.dev); M = torch.zeros(L, L, dtype=torch.bool, device=m.dev)
        for reg, col in targets:
            t = torch.tensor(COLOR_LAB[col], device=m.dev, dtype=torch.float32); d = (m.pal - t).norm(dim=1)
            w = torch.exp(-(d / 14.0) ** 2); w = w / w.sum(); mk = region_mask(reg, L, m.dev); W[mk] = w; M |= mk
        out[L] = (W[None], M)
    return out
def colour_score(m, G, targets):
    if not targets: return torch.zeros(len(G))
    lab = v9.rgb2lab(G.float()); sc = torch.zeros(len(G), device=m.dev)
    for reg, col in targets:
        mk = region_mask(reg, 64, m.dev); t = torch.tensor(COLOR_LAB[col], device=m.dev, dtype=torch.float32)
        d = (lab[:, mk] - t).norm(dim=-1); sc += (d < 25).float().mean(1)
    return (sc / len(targets)).cpu()

def generate2(tool, targets, n=4, oversample=3, seed=None, strength=4.0, outdir=None, tag='img', select=True):
    m = tool.ensure(); mix = colour_mix(m, targets); lam = strength; origd = m.draw
    def draw(p, temp, gen, _o=origd):   # additive rule mix: in the target region, put mass lam on target-like colours
        if p.dim() == 4 and p.shape[1] in mix and lam > 0:
            q = p.clamp_min(0); q = q / q.sum(-1, keepdim=True).clamp_min(1e-12)
            w, mk = mix[p.shape[1]]; q = torch.where(mk[None, :, :, None], (1 - lam) * q + lam * w, q); p = q
        return _o(p, temp, gen)
    m.draw = draw
    seed = int(time.time()) % 100000 if seed is None else seed; t0 = time.time()
    if m.dev.type == 'cuda': torch.cuda.reset_peak_memory_stats()
    try: G = m.generate(n * oversample, seed)
    finally: del m.draw
    score = colour_score(m, G, targets)
    order = torch.argsort(score, descending=True)[:n] if select else torch.arange(n)
    from PIL import Image
    outdir = Path(outdir or HERE / 'outputs'); outdir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S') + f'_{seed}'; Gc = G.cpu().numpy(); paths = []
    for j, i in enumerate(order.tolist()):
        p = outdir / f'{stamp}_{tag}_{j}.png'; Image.fromarray(Gc[i]).resize((256, 256), Image.NEAREST).save(p); paths.append(str(p))
    sel = Gc[order.numpy()]; grid = outdir / f'{stamp}_{tag}_grid.png'
    Image.fromarray(np.concatenate(list(sel), 1)).resize((256 * len(sel), 256), Image.NEAREST).save(grid)
    info = dict(paths=paths, grid=str(grid), targets=targets, seed=seed, sampled=len(G), kept=len(sel),
                seconds=round(time.time() - t0, 1), match_scores=[round(float(score[i]), 3) for i in order])
    if m.dev.type == 'cuda': info['peak_vram_gib'] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
    return info, G



