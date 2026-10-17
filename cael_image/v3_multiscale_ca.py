"""CAEL image v3: multi-scale count-learned integer cellular automaton (no neural nets).
Growth: 4x4 -> 8 -> 16 -> 32 -> 64. Each level: every cell splits into 2x2 children whose
colors are sampled from integer count tables keyed by parent color + 4 parent neighbours
(coarse) + quadrant; then checkerboard CA sweeps resample cells from counts keyed by
parent color + 4 same-level neighbours. Rules are learned purely by counting.
GPU (torch, ROCm 'cuda') is used only as a tensor engine for metrics; auto-falls back to CPU."""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.data import discover, split_records, read_rgb

C = 64  # 4 levels per channel
LEVELS = (8, 16, 32, 64)

def q64(rgb):  # float rgb 0..255 -> 0..63
    v = np.clip(np.rint(rgb / 85.0), 0, 3).astype(np.int64)
    return v[..., 0] * 16 + v[..., 1] * 4 + v[..., 2]
def coarse8(c):
    return ((c >> 5) & 1) * 4 + ((c >> 3) & 1) * 2 + ((c >> 1) & 1)
def pal():
    i = np.arange(C); return (np.stack([i // 16, (i // 4) % 4, i % 4], -1) * 85).astype(np.uint8)
def pyramid(rgb):
    f = rgb.astype(np.float64); out = {}
    for s in LEVELS:
        k = 64 // s; out[s] = q64(f.reshape(s, k, s, k, 3).mean((1, 3)))
    return out
def nb4(g):  # up, down, left, right with edge replicate
    p = np.pad(g, 1, mode='edge')
    return p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]
def nkey(g):
    u, d, l, r = nb4(g); return ((coarse8(u) * 8 + coarse8(d)) * 8 + coarse8(l)) * 8 + coarse8(r)

class Model:
    def __init__(s):
        s.seed = np.zeros((64, C), np.int64); s.seed_ca = np.zeros((64 * 4096, C), np.int64)
        s.up = {L: np.zeros((C * 4096 * 4, C), np.int32) for L in LEVELS[1:]}
        s.upb = {L: np.zeros((C * 4, C), np.int64) for L in LEVELS[1:]}
        s.ref = {L: np.zeros((C * 4096, C), np.int32) for L in LEVELS[1:]}
    def observe(s, pyr):
        g = pyr[8]; np.add.at(s.seed, (np.arange(64), g.ravel()), 1)
        np.add.at(s.seed_ca, (np.arange(64) * 4096 + nkey(g).ravel(), g.ravel()), 1)
        for L in LEVELS[1:]:
            P = pyr[L // 2]; ch = pyr[L]
            par = np.repeat(np.repeat(P, 2, 0), 2, 1); pk = np.repeat(np.repeat(nkey(P), 2, 0), 2, 1)
            yy, xx = np.indices((L, L)); qd = (yy % 2) * 2 + xx % 2
            k = (par * 4096 + pk) * 4 + qd
            np.add.at(s.up[L], (k.ravel(), ch.ravel()), 1)
            np.add.at(s.upb[L], ((par * 4 + qd).ravel(), ch.ravel()), 1)
            np.add.at(s.ref[L], ((par * 4096 + nkey(ch)).ravel(), ch.ravel()), 1)
    @staticmethod
    def sample(rows, back, rng, minc=4, temp=1.0):
        rows = rows.astype(np.float64); tot = rows.sum(1)
        use = np.where((tot >= minc)[:, None], rows, back.astype(np.float64) + rows) + 1e-9
        if temp != 1.0: use = use ** (1.0 / temp)
        cdf = np.cumsum(use, 1); u = rng.random(len(use)) * cdf[:, -1]
        return np.minimum((cdf < u[:, None]).sum(1), C - 1)
    def sweeps(s, g, table, keybase, back, rng, n, temp=1.0):
        L = g.shape[0]; yy, xx = np.indices((L, L))
        for it in range(n):
            m = ((yy + xx) % 2 == it % 2).ravel()
            k = (keybase * 4096 + nkey(g)).ravel()[m]
            flat = g.ravel().copy(); flat[m] = s.sample(table[k], back.reshape(-1, C)[m], rng, minc=6, temp=temp)
            g = flat.reshape(L, L)
        return g
    def generate(s, rng, sweeps=4, ftemp=0.6):
        g = s.sample(s.seed, np.ones((64, C)), rng, minc=1).reshape(8, 8)
        for t in np.linspace(1.0, 0.8, 24):
            g = s.sweeps(g, s.seed_ca, np.arange(64).reshape(8, 8), s.seed, rng, 1, temp=t)
        for L in LEVELS[1:]:
            par = np.repeat(np.repeat(g, 2, 0), 2, 1); pk = np.repeat(np.repeat(nkey(g), 2, 0), 2, 1)
            yy, xx = np.indices((L, L)); qd = (yy % 2) * 2 + xx % 2
            bk = s.upb[L][(par * 4 + qd).ravel()]
            t = 1.0 if L <= 16 else ftemp
            g = s.sample(s.up[L][((par * 4096 + pk) * 4 + qd).ravel()], bk, rng, temp=t).reshape(L, L)
            g = s.sweeps(g, s.ref[L], par, bk, rng, sweeps, temp=t)
        return pal()[g]

def get_torch(device):
    if device == 'gpu':
        try:
            import torch
            if torch.cuda.is_available(): return torch, 'cuda'
            print('GPU unavailable, falling back to CPU')
        except Exception as e: print('torch unavailable, CPU fallback:', e)
    return None, 'cpu'
def nn_dist(A, B, torch, dev, same=False):
    A = A.reshape(len(A), -1).astype(np.float32) / 255; B = B.reshape(len(B), -1).astype(np.float32) / 255
    if torch:
        a = torch.tensor(A, device=dev); b = torch.tensor(B, device=dev); d = torch.cdist(a, b)
        if same: d.fill_diagonal_(1e9)
        return (d.min(1).values / np.sqrt(A.shape[1])).cpu().numpy()
    out = []
    for x in A:
        d = np.sqrt(((B - x) ** 2).sum(1)); out.append(d)
    d = np.array(out)
    if same: np.fill_diagonal(d, 1e9)
    return d.min(1) / np.sqrt(A.shape[1])
def quant(X): return pal()[q64(X.astype(np.float64))]
def edges(X):
    f = X.astype(np.float32).mean(-1)
    return float((np.abs(np.diff(f, axis=1)) > 24).mean() + (np.abs(np.diff(f, axis=2)) > 24).mean()) / 2
def stats(X, train, torch, dev, rng):
    i = rng.integers(0, len(X), (400, 2)); i = i[i[:, 0] != i[:, 1]]
    pair = float(np.abs(X[i[:, 0]].astype(np.int32) - X[i[:, 1]]).mean())
    return dict(n=len(X), pairwise_L1=round(pair, 2), edge_density=round(edges(X), 4),
                pixel_std=round(float(X.reshape(len(X), -1, 3).std(1).mean()), 2),
                nn_to_train_min=round(float(nn_dist(X, train, torch, dev).min()), 4),
                nn_to_train_median=round(float(np.median(nn_dist(X, train, torch, dev))), 4))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('-Device', '--device', default='gpu', choices=['gpu', 'cpu'])
    ap.add_argument('--out', default='models/cael-image-female-64-v3'); ap.add_argument('--n', type=int, default=64)
    ap.add_argument('--sweeps', type=int, default=4); ap.add_argument('--ftemp', type=float, default=0.6); a = ap.parse_args()
    torch, dev = get_torch(a.device); print('device', dev)
    cfg = json.load(open('train_image_config.json', encoding='utf-8-sig'))
    recs = discover(cfg['dataset_dir'], cfg['resize_mode']); tr, va = split_records(recs, 0.1, 42)
    root = Path(cfg['dataset_dir'])
    T = np.stack([read_rgb(root / r['image']) for r in tr]); V = np.stack([read_rgb(root / r['image']) for r in va])
    m = Model()
    for x in T: m.observe(pyramid(x))
    rng = np.random.default_rng(7)
    G = np.stack([m.generate(rng, a.sweeps, a.ftemp) for _ in range(a.n)])
    from PIL import Image
    import zipfile
    v2 = np.stack([np.array(Image.open(p).convert('RGB')) for p in sorted(Path('models/cael-image-female-64-v2').glob('preview_*.png'))])
    rs = np.random.default_rng(1)
    rep = dict(train_images=len(T), heldout_quantized=stats(quant(V[:256]), T, torch, dev, rs), heldout=stats(V[:256], T, torch, dev, rs), v2_previews=stats(v2, T, torch, dev, rs),
               v3=stats(G, T, torch, dev, rs),
               train_self_nn_min=round(float(nn_dist(T[:512], T, torch, dev, same=True).min()), 4))
    h, g = rep['heldout_quantized'], rep['v3']
    rep['pass_rule'] = ('pairwise_L1 >= 0.5*heldout; edge_density within 0.5x-2x heldout; '
                        'nn_to_train_min >= 0.5*heldout nn_to_train_median (no copies)')
    rep['pass'] = bool(g['pairwise_L1'] >= 0.5 * h['pairwise_L1'] and 0.5 * h['edge_density'] <= g['edge_density'] <= 2 * h['edge_density']
                       and g['nn_to_train_min'] >= 0.5 * h['nn_to_train_median'])
    out = Path(a.out); out.mkdir(parents=True, exist_ok=False)
    for i in range(16): Image.fromarray(G[i]).save(out / f'preview_{i:02d}.png')
    grid = G[:64].reshape(8, 8, 64, 64, 3).transpose(0, 2, 1, 3, 4).reshape(512, 512, 3)
    Image.fromarray(grid).save(out / 'preview_grid_8x8.png')
    np.savez_compressed(out / 'model_counts.npz', seed=m.seed, seed_ca=m.seed_ca,
                        **{f'up{L}': m.up[L] for L in LEVELS[1:]}, **{f'upb{L}': m.upb[L] for L in LEVELS[1:]},
                        **{f'ref{L}': m.ref[L] for L in LEVELS[1:]})
    json.dump(rep, open(out / 'metrics.json', 'w'), indent=2); print(json.dumps(rep, indent=2))
if __name__ == '__main__': main()

