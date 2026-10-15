"""CAEL image v9: learned generative multi-scale integer cellular automaton. No neural nets, no hand-placed parts.
The picture is built only by learned local rules:
  palette  : 64 colours by k-means in Lab on training pixels; a 16-colour 'coarse' code = k-means of those 64.
  seed     : 4x4 grid; each cell's colour ~ counts[position, 4 neighbour coarse colours] (Gibbs CA sweeps).
  growth   : at each scale 8,16,32,64 every cell splits 2x2; child colour ~ counts[parent colour, parent's 3x3 coarse
             neighbourhood, child quadrant, position bucket].
  refine   : several checkerboard CA sweeps per scale; cell colour ~ counts[parent colour, 4 current neighbours (coarse),
             position bucket].
  back-off : hashed full key -> key without position -> parent+quadrant/parent only, when a context has < min-count.
Counts are learned from training images only (integer counts). Sampling is stochastic (temperature per scale).
Hand-written parts (generic, not face-specific): the scale schedule, palette sizes, key layout, back-off thresholds,
temperatures, number of sweeps. There is no face, hair or body code; anything figure-like must come from the counts.
Torch is only a tensor engine ('cuda' via ROCm, or CPU)."""
import argparse, json, sys, time
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.data import discover, split_records, read_rgb
from cael_image.v4_multiscale_ca import pick_device, stats, shifts
from cael_image.v6_region_ca import rgb2lab, lab2rgb, kmeans

LEVELS = (4, 8, 16, 32, 64); HB = 20  # hash bits per table
EXT = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
PAD_MODE = 'black'  # v10 sets 'clamp'

def gather(root, sources, include_root, boxes):
    """Captions are not needed (v9 is unconditional). Returns list of (relative path, face box or None)."""
    root = Path(root); out = []
    dirs = [root / d for d in sources] + ([root] if include_root else [])
    for d in dirs:
        it = d.rglob('*') if d != root else d.glob('*')
        for p in sorted(it):
            if p.is_file() and p.suffix.lower() in EXT:
                rel = p.relative_to(root).as_posix(); out.append((rel, boxes.get(rel)))
    return out

def load64(root, rel, box, zoom):
    from PIL import Image, ImageOps
    with Image.open(Path(root) / rel) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        if box is not None:   # face-centred square crop: crop side = zoom x face size, face centre at 45% height
            x, y, fw, fh, W, H = box; side = int(max(fw, fh) * zoom); cx, cy = x + fw / 2, y + fh / 2
            l, t = int(cx - side / 2), int(cy - side * 0.45)
            if PAD_MODE == 'clamp':   # keep the crop inside the image: no black padding is ever counted
                side = min(side, W, H); l = min(max(l, 0), W - side); t = min(max(t, 0), H - side)
            im = im.crop((l, t, l + side, t + side))
        im = ImageOps.fit(im, (64, 64), method=Image.Resampling.LANCZOS)
        return np.asarray(im, dtype=np.uint8)
def poskey(L, buckets):
    y = torch.arange(L); b = (y * buckets // L); return (b[:, None] * buckets + b[None, :])
def hsh(k): return k  # raw exact key; each table hashes with its own size (see GCA.slot)
HBITS = {8: 20, 16: 21, 32: 22, 64: 22}  # hashed-table bits per scale (set by --hash-bits-64 etc.)

class GCA:
    def __init__(s, dev, P=64, Q=16, buckets=8, minc=3):
        s.dev, s.P, s.Q, s.bk, s.minc = dev, P, Q, buckets, minc
    def quant(s, lab):
        f = lab.reshape(-1, 3); return torch.cat([torch.cdist(f[i:i + 65536], s.pal).argmin(1) for i in range(0, len(f), 65536)]).reshape(lab.shape[:-1])
    def pyr(s, lab):  # Lab (B,64,64,3) -> {L: palette ids (B,L,L)}
        out = {}
        for L in LEVELS:
            k = 64 // L; out[L] = s.quant(lab.reshape(-1, L, k, L, k, 3).mean((2, 4)))
        return out
    def c(s, g): return s.coarse[g]
    def k3(s, g):  # parent 3x3 coarse neighbourhood (9 x 4 bits) hashed later
        sh = shifts(g); k = torch.zeros_like(g)
        for o in sorted(sh): k = (k * s.Q + s.c(sh[o])) % 2147483629
        return k
    def k4(s, g):
        sh = shifts(g); return ((s.c(sh[(-1, 0)]) * s.Q + s.c(sh[(1, 0)])) * s.Q + s.c(sh[(0, -1)])) * s.Q + s.c(sh[(0, 1)])
    def quad(s, L): y = torch.arange(L, device=s.dev); return ((y[:, None] % 2) * 2 + y[None] % 2)[None]
    def pos(s, L): return poskey(L, min(s.bk, L)).to(s.dev)[None]
    def keys(s, L, par, g=None):
        """Returns list of (table name, key) from most to least specific for growth (g None) or refine (g given)."""
        if g is None:
            P, K3 = s.up2(par), s.up2(s.k3(par)); q = s.quad(L).expand_as(P); ps = s.pos(L).expand_as(P)
            return [('gf', hsh(((K3 * 4 + q) * 1024 + ps) * 67 + P)), ('gn', hsh((K3 * 4 + q) * 131 + P)), ('gp', P * 4 + q)]
        P = s.up2(par); K4 = s.k4(g); ps = s.pos(L).expand_as(P)
        Pc = s.c(P)  # refine uses the COARSE parent so block borders can move (fine parent kept blocks frozen)
        return [('rf', hsh((K4 * 1024 + ps) * 17 + Pc)), ('rn', hsh(K4 * 17 + Pc)), ('rp', P)]
    @staticmethod
    def up2(x): return x.repeat_interleave(2, 1).repeat_interleave(2, 2)
    def alloc(s):
        z = lambda n: torch.zeros(n, s.P, device=s.dev, dtype=torch.int32)
        s.t = {}
        for L in LEVELS[1:]:
            hb = HBITS[L]; s.t[L] = dict(gf=z(1 << hb), gn=z(1 << max(hb - 2, 18)), gp=z(s.P * 4), rf=z(1 << hb), rn=z(1 << max(hb - 2, 18)), rp=z(s.P))
        s.seed = dict(sf=z(16 * s.Q ** 4), sp=z(16))
    @staticmethod
    def add(t, k, v): t.view(-1).index_add_(0, (k.reshape(-1) * t.shape[1] + v.reshape(-1)), torch.ones(k.numel(), device=t.device, dtype=torch.int32))
    def fit_palette(s, lab, seed):
        g = torch.Generator().manual_seed(seed); f = lab.reshape(-1, 3)
        sm = f[torch.randint(0, len(f), (min(400000, len(f)),), generator=g).to(f.device)]
        s.pal, _ = kmeans(sm, s.P, 25, seed); _, s.coarse = kmeans(s.pal, s.Q, 25, seed + 1)
    def observe(s, lab):
        p = s.pyr(lab); g4 = p[4]; ps = s.pos(4).expand_as(g4)
        s.add(s.seed['sf'], ps * s.Q ** 4 + s.k4(g4), g4); s.add(s.seed['sp'], ps, g4)
        for L in LEVELS[1:]:
            par, ch = p[L // 2], p[L]; T = s.t[L]
            for name, k in s.keys(L, par): s.add(T[name], s.slot(T[name], name, k), ch)
            for name, k in s.keys(L, par, ch): s.add(T[name], s.slot(T[name], name, k), ch)
    def rows(s, table, chain):
        out = None
        for name, k in reversed(chain):
            r = table[name][s.slot(table[name], name, k)].float()
            out = r + 1e-3 if out is None else torch.where(r.sum(-1, keepdim=True) >= s.minc, r, out)
        return out
    @staticmethod
    def slot(t, name, k):
        return k if name in ('gp', 'rp') else (k * 2654435761 + 97) % t.shape[0]
    def draw(s, p, temp, gen):
        p = p.clamp_min(1e-9) ** (1.0 / temp); f = p.reshape(-1, p.shape[-1])
        return torch.multinomial(f / f.sum(-1, keepdim=True), 1, generator=gen).reshape(p.shape[:-1])
    def generate(s, B, seed, sweeps=(8, 6, 6, 5, 4), temps=(1.0, 1.0, 0.9, 0.8, 0.7)):
        gen = torch.Generator(device=s.dev); gen.manual_seed(seed)
        ps = s.pos(4).expand(B, 4, 4)
        g = s.draw(s.seed['sp'][ps].float() + 1e-3, 1.0, gen)
        chk4 = (s.quad(4) == 0) | (s.quad(4) == 3)
        for it in range(sweeps[0] * 2):
            r = s.seed['sf'][ps * s.Q ** 4 + s.k4(g)].float(); back = s.seed['sp'][ps].float() + 1e-3
            new = s.draw(torch.where(r.sum(-1, keepdim=True) >= s.minc, r, back), temps[0], gen)
            g = torch.where(chk4 == (it % 2 == 0), new, g)
        for li, L in enumerate(LEVELS[1:], 1):
            T = s.t[L]; par = g
            g = s.draw(s.rows(T, s.keys(L, par)), temps[li], gen)
            chk = (s.quad(L) == 0) | (s.quad(L) == 3)
            for it in range(sweeps[li] * 2):
                new = s.draw(s.rows(T, s.keys(L, par, g)), temps[li], gen)
                g = torch.where(chk == (it % 2 == 0), new, g)
        return lab2rgb(s.pal[g])
    def coverage(s):  # share of non-empty hashed rows per table (diagnostic for sparsity)
        return {f'{L}{n}': round(float((v.sum(1) > 0).float().mean()), 4) for L, d in s.t.items() for n, v in d.items() if n in ('gf', 'rf', 'gn', 'rn')}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-Device', '--device', default='gpu', choices=['gpu', 'cpu'])
    ap.add_argument('--config', default='train_image_config.json'); ap.add_argument('--out', default='models/cael-image-female-64-v9')
    ap.add_argument('--resize', default='fit', choices=['error', 'fit'], help='fit = centre-crop + resize larger images to 64x64')
    ap.add_argument('--n', type=int, default=64); ap.add_argument('--max-images', type=int, default=0)
    ap.add_argument('--palette', type=int, default=64); ap.add_argument('--coarse', type=int, default=16)
    ap.add_argument('--buckets', type=int, default=4); ap.add_argument('--min-count', type=int, default=3)
    ap.add_argument('--flip', action='store_true', help='also count horizontally mirrored images (doubles data)')
    ap.add_argument('--root', default='data/images')
    ap.add_argument('--sources', default='1,2', help='subfolders of --root to use')
    ap.add_argument('--include-root', action='store_true', help='also use images directly in --root')
    ap.add_argument('--face-boxes', default='')
    ap.add_argument('--face-weight', type=int, default=1, help='count images with a detected face this many times')
    ap.add_argument('--face-only', action='store_true'); ap.add_argument('--zoom', type=float, default=2.2)
    ap.add_argument('--hash-bits', default='20,21,22,22', help='hashed table bits for scales 8,16,32,64 (VRAM ~ 2^bits*256 B per table)')
    a = ap.parse_args(); t0 = time.time(); dev = pick_device(a.device); print('device', dev, flush=True)
    HBITS.update(zip((8, 16, 32, 64), (int(x) for x in a.hash_bits.split(','))))
    out = Path(a.out)
    if out.exists(): raise SystemExit(f'{out} exists; choose a new --out (existing models are never overwritten).')
    cfg = json.load(open(a.config, encoding='utf-8-sig')); root = Path(a.root)
    bp = Path(a.face_boxes); boxes = json.loads(bp.read_text(encoding='utf-8')) if a.face_boxes and bp.exists() else {}
    items = gather(root, [x for x in a.sources.split(',') if x], a.include_root, boxes)
    if a.face_only: items = [it for it in items if it[1] is not None]
    rng = np.random.default_rng(cfg['seed']); idx = rng.permutation(len(items)); nv = max(8, int(len(items) * cfg['validation_fraction']))
    va_i, tr_i = idx[:nv], idx[nv:]
    if a.max_images:
        fi = [i for i in tr_i if items[i][1] is not None]; oi = [i for i in tr_i if items[i][1] is None]
        tr_i = np.array((fi + oi)[:a.max_images]); va_i = va_i[:max(8, a.max_images // 8)]
    load = lambda ids: np.stack([load64(root, items[i][0], items[i][1], a.zoom) for i in ids])
    T = torch.from_numpy(load(tr_i)).to(dev); V = torch.from_numpy(load(va_i)).to(dev)
    tr_face = torch.tensor([items[i][1] is not None for i in tr_i], device=dev)
    pass
    pass
    m = GCA(dev, a.palette, a.coarse, a.buckets, a.min_count); m.alloc()
    labT = rgb2lab(T.float()); m.fit_palette(labT, cfg['seed'])
    for i in range(0, len(T), 128):
        x = labT[i:i + 128]; f = tr_face[i:i + 128]
        for rep_i in range(max(1, a.face_weight)):
            xs = x if rep_i == 0 else x[f]
            if len(xs) == 0: break
            m.observe(xs)
            if a.flip: m.observe(xs.flip(2))
    print(f'counted ({time.time() - t0:.1f}s); hash coverage {m.coverage()}', flush=True)
    G = torch.cat([m.generate(min(32, a.n - i), cfg['seed'] + i) for i in range(0, a.n, 32)])
    Vq = lab2rgb(m.pal[m.quant(rgb2lab(V[:256].float()))]); g2 = torch.Generator(); g2.manual_seed(1)
    ab = lambda X: [round(float(v), 2) for v in rgb2lab(X.float()).reshape(-1, 3).mean(0)]
    rep = dict(device=str(dev), coverage=m.coverage(),
               mean_lab_heldout=ab(V), mean_lab_v9=ab(G), heldout_quantized=stats(Vq, T, g2), v9=stats(G, T, g2))
    h, g = rep['heldout_quantized'], rep['v9']
    fe = float(np.mean([abs(x - y) / max(y, 1e-6) for x, y in zip(g['falloff'], h['falloff'])]))
    da = abs(rep['mean_lab_v9'][1] - rep['mean_lab_heldout'][1]); db = abs(rep['mean_lab_v9'][2] - rep['mean_lab_heldout'][2])
    checks = dict(diversity=g['pairwise_L1'] >= 0.5 * h['pairwise_L1'],
                  edges=0.5 * h['edge_density'] <= g['edge_density'] <= 2 * h['edge_density'],
                  falloff=fe <= 0.25, no_copies=g['nn_to_train_min'] >= 0.5 * h['nn_to_train_median'],
                  colour_balance=da <= 4.0 and db <= 4.0)
    rep.update(falloff_rel_error=round(fe, 4), colour_shift_ab=[round(da, 2), round(db, 2)], checks=checks, pass_=all(checks.values()),
               seconds=round(time.time() - t0, 1),
               pass_rule='diversity >=0.5x held-out; edges 0.5-2x; falloff err <=0.25; nearest-train min >=0.5x held-out median; mean a*/b* within 4. '
                         'Metrics cannot detect faces: judge preview_grid.png by eye.')
    out.mkdir(parents=True)
    from PIL import Image
    Gc = G.cpu().numpy(); n = int(np.sqrt(len(Gc)))
    for i in range(min(16, len(Gc))): Image.fromarray(Gc[i]).save(out / f'preview_{i:02d}.png')
    if n > 1: Image.fromarray(Gc[:n * n].reshape(n, n, 64, 64, 3).transpose(0, 2, 1, 3, 4).reshape(n * 64, n * 64, 3)).save(out / 'preview_grid.png')
    torch.save(dict(palette_lab=m.pal.cpu(), coarse=m.coarse.cpu(), seed=m.seed and {k: v.cpu() for k, v in m.seed.items()},
                    tables={L: {k: v.to_sparse().cpu() for k, v in d.items()} for L, d in m.t.items()}, args=vars(a)), out / 'model_v9.pt')
    json.dump(rep, open(out / 'metrics.json', 'w'), indent=2); print(json.dumps(rep, indent=2)); print('PASS' if rep['pass_'] else 'FAIL')
    if dev.type == 'cuda': print(f'peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB')
    sys.stdout.flush(); import os; os._exit(0)
if __name__ == '__main__': main()


