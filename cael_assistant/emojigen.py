"""CAEL assistant emoji tool: loads models/cael-emoji-64-v2 (caption-conditioned integer CA, no NN) and makes 64x64 emoji.
Prompt words steer through learned per-word colour/position counts (CLDR names + keywords of Noto/Blobmoji emoji);
the CA rule tables themselves are caption-free. Unknown words are ignored; if no word is known the output is an
unconditional emoji (reported as such)."""
import sys, re, time
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).resolve().parent; CAEL = HERE.parent
sys.path.insert(0, str(CAEL))
_argv = sys.argv; sys.argv = [sys.argv[0]]
import cael_image.v10_prior_ca as v10
sys.argv = _argv
v9 = v10.v9
MODEL = CAEL / 'models' / 'cael-emoji-64-v2' / 'model_emoji.pt'
STOP = {'a', 'an', 'the', 'of', 'with', 'and', 'in', 'on', 'for', 'to', 'at', 'by', 'emoji', 'emojis', 'icon', 'please', 'me', 'some'}
def toks(s): return [w for w in re.findall(r'[a-z0-9]+', s.lower()) if w not in STOP]

class EmojiModel(v10.GCA10):
    def make_cond(s, wl):
        s.cond = {}
        for L in v9.LEVELS:
            base = s.prior[L].float(); base = base / base.sum(1, keepdim=True).clamp_min(1); rows = []
            for ws in wl:
                if not ws: rows.append(base); continue
                Lw = min(L, 32); acc = 0; tw = 0
                for w, wt in ws:
                    h = s.wp[Lw][w].float(); acc = acc + wt * h / h.sum(1, keepdim=True).clamp_min(1); tw += wt
                h = acc / tw
                if L == 64: h = h.reshape(32, 32, s.P).repeat_interleave(2, 0).repeat_interleave(2, 1).reshape(64 * 64, s.P)
                rows.append((1 - s.cmix) * h + s.cmix * base)
            s.cond[L] = torch.stack(rows)
    def guide(s, L, g):
        A = v10.A
        if L < A.guide_from: return 1.0
        glob = s.prior[L].float().sum(0, keepdim=True); gl = glob / glob.sum(); gl = 0.9 * gl + 0.1 / s.P
        pr = s.cond[L]; B = pr.shape[0]; c = A.ratio_clamp
        if A.guide == 'ratio': pr = (pr / gl).clamp(1 / c, c)
        out = pr.reshape(B, L, L, s.P) ** A.prior_alpha
        if g is not None and A.sym_beta > 0:
            pos = torch.arange(L * L, device=s.dev).reshape(1, L, L).expand_as(g)
            sy = s.sym[L][pos * s.Q + s.c(g.flip(2))].float() + 0.5; sy = sy / sy.sum(-1, keepdim=True)
            if A.guide == 'ratio': sy = (sy / gl.reshape(1, 1, 1, s.P)).clamp(1 / c, c)
            out = out * sy ** A.sym_beta
        return out

class EmojiTool:
    def __init__(s): s.m = None
    def ensure(s):
        if s.m is not None: return s.m
        dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        if dev.type == 'cuda':
            tot = torch.cuda.get_device_properties(0).total_memory; torch.cuda.set_per_process_memory_fraction(min(1.0, 13.5 * 2**30 / tot))
        ck = torch.load(MODEL, map_location='cpu', weights_only=False); a = ck['args']
        for k, v in ck['v10'].items(): setattr(v10.A, k, v)
        v9.HBITS.update(zip((8, 16, 32, 64), (int(x) for x in a['hash_bits'].split(','))))
        m = EmojiModel(dev, a['palette'], a['coarse'], a['buckets'], a['min_count'])
        m.pal = ck['palette_lab'].to(dev); m.coarse = ck['coarse'].to(dev); m.seed = {k: v.to(dev) for k, v in ck['seed'].items()}
        m.t = {L: {k: v.to_dense().to(dev) for k, v in d.items()} for L, d in ck['tables'].items()}
        m.prior = {L: v.to(dev) for L, v in ck['prior'].items()}; m.sym = {L: v.to_dense().to(dev) for L, v in ck['sym'].items()}
        V = len(ck['vocab']); m.wp = {L: v.to_dense().to(dev).view(V, L * L, m.P) for L, v in ck['word_prior'].items()}
        m.vocab = {w: i for i, w in enumerate(ck['vocab'])}; m.idf = ck['idf']; m.cmix = a['cond_mix']
        m.srcs = a['sources'].split(','); m.per_style = a.get('per_style', 0); s.m = m
        return m
    def encode(s, words, style):
        m = s.m
        if not m.per_style: return [(m.vocab[w], m.idf[w]) for w in words if w in m.vocab]
        for src in [style] + [x for x in m.srcs if x != style]:
            e = [(m.vocab[f'{src}|{w}'], m.idf[f'{src}|{w}']) for w in words if f'{src}|{w}' in m.vocab]
            if e: return e
        return []
    def generate(s, subject, n=4, seed=None, outdir=None):
        m = s.ensure(); words = toks(subject); seed = int(time.time()) % 100000 if seed is None else seed
        styles = [m.srcs[i % len(m.srcs)] for i in range(n)]; wl = [s.encode(words, st) for st in styles]
        known = sorted({w for w in words if any(f'{x}|{w}' in m.vocab or w in m.vocab for x in m.srcs)})
        t0 = time.time(); m.make_cond(wl); G = m.generate(n, seed)
        from PIL import Image
        outdir = Path(outdir or HERE / 'outputs' / 'emoji'); outdir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime('%Y%m%d_%H%M%S') + f'_{seed}'; tag = '_'.join(words)[:40] or 'emoji'; Gc = G.cpu().numpy(); paths = []
        for j in range(n):
            p = outdir / f'{stamp}_{tag}_{j}.png'; Image.fromarray(Gc[j]).resize((256, 256), Image.NEAREST).save(p); paths.append(str(p))
        grid = outdir / f'{stamp}_{tag}_grid.png'; Image.fromarray(np.concatenate(list(Gc), 1)).resize((256 * n, 256), Image.NEAREST).save(grid)
        return dict(paths=paths, grid=str(grid), words=words, known_words=known, unknown_words=[w for w in words if w not in known],
                    styles=styles, seed=seed, seconds=round(time.time() - t0, 1))
