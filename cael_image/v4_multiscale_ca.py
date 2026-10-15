"""CAEL image v4: caption-conditioned multi-scale count-learned integer cellular automaton.
No neural nets: every rule is a count table learned by counting. Torch (ROCm 'cuda' or CPU)
is used only as a tensor engine for counting, table lookup, sampling and metrics.
Levels: 8x8 layout CA (3x3 neighbourhood + position + caption words, backoff 3x3 -> 4-nbr -> position)
-> 16 -> 32 -> 64 split/refine CA (min-count backoff) -> 3x3 majority smoothing CA pass."""
import argparse, json, sys, time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.data import discover, split_records, read_rgb
from cael_image.model import tokens

C = 64; LEVELS = (8, 16, 32, 64); HASH = 1 << 20; DISTS = (1, 2, 4, 8, 16)

def pick_device(name):
    if name == 'gpu':
        if torch.cuda.is_available(): return torch.device('cuda')
        print('GPU not available; falling back to CPU')
    return torch.device('cpu')
def q64(f):  # float (...,3) 0..255 -> 0..63
    v = torch.clamp(torch.round(f / 85.0), 0, 3).long(); return v[..., 0] * 16 + v[..., 1] * 4 + v[..., 2]
def c8(c): return ((c >> 5) & 1) * 4 + ((c >> 3) & 1) * 2 + ((c >> 1) & 1)
def palette(dev):
    i = torch.arange(C, device=dev); return (torch.stack([i // 16, (i // 4) % 4, i % 4], -1) * 85).to(torch.uint8)
def pyramid(rgb):  # rgb (B,64,64,3) uint8 -> {L: (B,L,L) long}
    f = rgb.float(); out = {}
    for L in LEVELS:
        k = 64 // L; out[L] = q64(f.reshape(-1, L, k, L, k, 3).mean((2, 4)))
    return out
def shifts(g):  # g (B,L,L) -> dict offset->neighbour (edge replicate)
    p = torch.nn.functional.pad(g[:, None].float(), (1, 1, 1, 1), mode='replicate')[:, 0].long()
    L = g.shape[1]; return {(dy, dx): p[:, 1 + dy:1 + dy + L, 1 + dx:1 + dx + L] for dy in (-1, 0, 1) for dx in (-1, 0, 1)}
def key4(g):
    s = shifts(g); return ((c8(s[(-1, 0)]) * 8 + c8(s[(1, 0)])) * 8 + c8(s[(0, -1)])) * 8 + c8(s[(0, 1)])
def key9(g, pos):  # hashed position + 8 neighbours (coarse8)
    s = shifts(g); k = pos.expand_as(g).clone()
    for off in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
        k = (k * 8 + c8(s[off])) % 2147483647
    return (k * 2654435761) % HASH
def add(table, key, val):
    table.view(-1).index_add_(0, (key.reshape(-1) * C + val.reshape(-1)), torch.ones(key.numel(), device=table.device))

class CA4:
    def __init__(s, vocab, dev, minc=4):
        s.dev, s.vocab, s.minc = dev, list(vocab), minc; s.wi = {w: i for i, w in enumerate(s.vocab)}
        z = lambda *sh: torch.zeros(*sh, C, device=dev)
        s.pos = z(64); s.k4 = z(64 * 4096); s.k9 = z(HASH); s.word = z(len(s.vocab), 64)
        s.up = {L: z(C * 4096 * 4) for L in LEVELS[1:]}; s.upb = {L: z(C * 4) for L in LEVELS[1:]}
        s.ref = {L: z(C * 4096) for L in LEVELS[1:]}
        yy, xx = torch.meshgrid(torch.arange(8, device=dev), torch.arange(8, device=dev), indexing='ij')
        s.p8 = (yy * 8 + xx)[None]
    def quad(s, L):
        yy, xx = torch.meshgrid(torch.arange(L, device=s.dev), torch.arange(L, device=s.dev), indexing='ij')
        return ((yy % 2) * 2 + xx % 2)[None]
    @staticmethod
    def up2(x): return x.repeat_interleave(2, 1).repeat_interleave(2, 2)
    def observe(s, rgb, captions):
        pyr = pyramid(rgb); g = pyr[8]; B = g.shape[0]; P = s.p8.expand(B, 8, 8)
        add(s.pos, P, g); add(s.k4, P * 4096 + key4(g), g); add(s.k9, key9(g, s.p8), g)
        for b, cap in enumerate(captions):
            for w in tokens(cap):
                if w in s.wi: add(s.word[s.wi[w]], s.p8[0], g[b])
        for L in LEVELS[1:]:
            par = s.up2(pyr[L // 2]); pk = s.up2(key4(pyr[L // 2])); qd = s.quad(L).expand_as(par); ch = pyr[L]
            add(s.up[L], (par * 4096 + pk) * 4 + qd, ch); add(s.upb[L], par * 4 + qd, ch)
            add(s.ref[L], par * 4096 + key4(ch), ch)
    def backoff(s, *rows):  # first row set with >= minc observations wins (rows ordered specific -> general)
        out = rows[-1] + 1e-3
        for r in reversed(rows[:-1]):
            out = torch.where((r.sum(-1, keepdim=True) >= s.minc), r, out)
        return out
    def draw(s, prob, temp, gen):
        p = prob.reshape(-1, C).clamp_min(1e-9); p = p ** (1.0 / temp)
        return torch.multinomial(p / p.sum(-1, keepdim=True), 1, generator=gen).reshape(prob.shape[:-1])
    def word_bias(s, prompts, weight):
        bias = torch.ones(len(prompts), 64, C, device=s.dev); base = (s.pos + 1) / (s.pos + 1).sum(-1, keepdim=True)
        for b, pr in enumerate(prompts):
            ids = [s.wi[w] for w in tokens(pr or '') if w in s.wi]
            if ids:
                wp = (s.word[ids] + 1) / (s.word[ids] + 1).sum(-1, keepdim=True)
                bias[b] = torch.exp(weight * torch.log(wp / base[None]).mean(0))
        return bias.reshape(len(prompts), 8, 8, C)
    def generate(s, prompts, seed=0, layout_sweeps=24, sweeps=4, ftemp=0.6, text_weight=1.0, smooth=1):
        gen = torch.Generator(device=s.dev); gen.manual_seed(seed); B = len(prompts)
        P = s.p8.expand(B, 8, 8); bias = s.word_bias(prompts, text_weight)
        g = s.draw((s.pos[P] + 1) * bias, 1.0, gen)
        phase = (s.p8 // 8 % 2) * 2 + (s.p8 % 8 % 2)  # 4-colouring so 8-neighbourhood updates are synchronous-safe
        for it in range(layout_sweeps):
            t = 1.0 - 0.2 * it / max(layout_sweeps - 1, 1)
            prob = s.backoff(s.k9[key9(g, s.p8)], s.k4[P * 4096 + key4(g)], s.pos[P] + 1) * bias
            new = s.draw(prob, t, gen); g = torch.where(phase == it % 4, new, g)
        for L in LEVELS[1:]:
            par = s.up2(g); pk = s.up2(key4(g)); qd = s.quad(L).expand_as(par); t = 1.0 if L <= 16 else ftemp
            back = s.upb[L][par * 4 + qd] + 1e-3
            g = s.draw(s.backoff(s.up[L][(par * 4096 + pk) * 4 + qd], back), t, gen)
            chk = (s.quad(L) == 0) | (s.quad(L) == 3)
            for it in range(sweeps):
                new = s.draw(s.backoff(s.ref[L][par * 4096 + key4(g)], back), t, gen)
                g = torch.where(chk == (it % 2 == 0), new, g)
        for _ in range(smooth):  # majority CA: a cell adopts the 3x3 majority colour if it holds >= 5 of 9
            st = torch.stack(list(shifts(g).values()), -1); mode, _ = torch.mode(st, -1)
            cnt = (st == mode[..., None]).sum(-1); g = torch.where(cnt >= 5, mode, g)
        return palette(s.dev)[g]
    def save(s, path):
        torch.save(dict(vocab=s.vocab, minc=s.minc, pos=s.pos.int().cpu(), k4=s.k4.int().to_sparse().cpu(),
                        k9=s.k9.int().to_sparse().cpu(), word=s.word.int().cpu(),
                        up={L: v.int().to_sparse().cpu() for L, v in s.up.items()}, upb={L: v.int().cpu() for L, v in s.upb.items()},
                        ref={L: v.int().to_sparse().cpu() for L, v in s.ref.items()}), path)

def falloff(X):  # mean |I(x)-I(x+d)| over grey, horizontal+vertical, per distance
    f = X.float().mean(-1)
    return [float(((f[:, :, d:] - f[:, :, :-d]).abs().mean() + (f[:, d:] - f[:, :-d]).abs().mean()) / 2) for d in DISTS]
def nn(A, B, same=False):
    a = A.reshape(len(A), -1).float() / 255; out = []
    for i in range(0, len(a), 64):
        d = torch.cdist(a[i:i + 64], B.reshape(len(B), -1).float() / 255)
        if same: d[torch.arange(d.shape[0]), torch.arange(i, i + d.shape[0])] = 1e9
        out.append(d.min(1).values)
    return torch.cat(out) / np.sqrt(a.shape[1])
def stats(X, T, gen):
    i = torch.randint(0, len(X), (400, 2), generator=gen); i = i[i[:, 0] != i[:, 1]]
    e = lambda f: float(((f[:, :, 1:] - f[:, :, :-1]).abs() > 24).float().mean() + ((f[:, 1:] - f[:, :-1]).abs() > 24).float().mean()) / 2
    d = nn(X, T)
    return dict(n=len(X), pairwise_L1=round(float((X[i[:, 0]].float() - X[i[:, 1]].float()).abs().mean()), 2),
                edge_density=round(e(X.float().mean(-1)), 4), falloff=[round(v, 2) for v in falloff(X)],
                nn_to_train_min=round(float(d.min()), 4), nn_to_train_median=round(float(d.median()), 4))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-Device', '--device', default='gpu', choices=['gpu', 'cpu'])
    ap.add_argument('--config', default='train_image_config.json'); ap.add_argument('--out', default='models/cael-image-female-64-v4')
    ap.add_argument('--n', type=int, default=64); ap.add_argument('--max-images', type=int, default=0)
    ap.add_argument('--batch', type=int, default=256); ap.add_argument('--min-count', type=int, default=4)
    ap.add_argument('--text-weight', type=float, default=1.0); ap.add_argument('--ftemp', type=float, default=0.6)
    ap.add_argument('--sweeps', type=int, default=4); ap.add_argument('--layout-sweeps', type=int, default=24)
    ap.add_argument('--smooth', type=int, default=1); a = ap.parse_args()
    t0 = time.time(); dev = pick_device(a.device); print('device', dev)
    out = Path(a.out)
    if out.exists(): raise SystemExit(f'{out} exists; choose a new --out (existing models are never overwritten).')
    cfg = json.load(open(a.config, encoding='utf-8-sig')); root = Path(cfg['dataset_dir'])
    recs = discover(root, cfg['resize_mode']); tr, va = split_records(recs, cfg['validation_fraction'], cfg['seed'])
    if a.max_images: tr, va = tr[:a.max_images], va[:max(8, a.max_images // 8)]
    df = Counter(w for r in tr for w in tokens(r['caption']))
    vocab = [w for w, c in df.most_common() if c >= 5][:256]
    T = torch.from_numpy(np.stack([read_rgb(root / r['image'], cfg['resize_mode']) for r in tr])).to(dev)
    V = torch.from_numpy(np.stack([read_rgb(root / r['image'], cfg['resize_mode']) for r in va])).to(dev)
    m = CA4(vocab, dev, a.min_count)
    for i in range(0, len(T), a.batch): m.observe(T[i:i + a.batch], [r['caption'] for r in tr[i:i + a.batch]])
    print(f'counted {len(T)} images in {time.time() - t0:.1f}s')
    prompts = [va[i % len(va)]['caption'] for i in range(a.n)]
    G = torch.cat([m.generate(prompts[i:i + 64], seed=cfg['seed'] + i, layout_sweeps=a.layout_sweeps, sweeps=a.sweeps,
                              ftemp=a.ftemp, text_weight=a.text_weight, smooth=a.smooth) for i in range(0, a.n, 64)])
    print(f'generated {a.n} in {time.time() - t0:.1f}s')
    Vq = palette(dev)[q64(V[:256].float())]; gen = torch.Generator(); gen.manual_seed(1)
    rep = dict(device=str(dev), train_images=len(T), vocabulary=len(vocab), args=vars(a),
               heldout_quantized=stats(Vq, T, gen), v4=stats(G, T, gen))
    h, g = rep['heldout_quantized'], rep['v4']
    fall_err = float(np.mean([abs(x - y) / max(y, 1e-6) for x, y in zip(g['falloff'], h['falloff'])]))
    checks = dict(diversity=g['pairwise_L1'] >= 0.5 * h['pairwise_L1'],
                  edges=0.5 * h['edge_density'] <= g['edge_density'] <= 2 * h['edge_density'],
                  falloff=fall_err <= 0.25, no_copies=g['nn_to_train_min'] >= 0.5 * h['nn_to_train_median'])
    rep.update(falloff_rel_error=round(fall_err, 4), checks=checks, pass_=all(checks.values()),
               pass_rule='diversity >= 0.5x heldout; edge density 0.5x-2x heldout; mean relative falloff error <= 0.25 '
                         'at d=1,2,4,8,16; nearest-train distance min >= 0.5x heldout median (pass rule fixed before v4 run)',
               seconds=round(time.time() - t0, 1))
    out.mkdir(parents=True)
    from PIL import Image
    Gc = G.cpu().numpy(); k = int(np.sqrt(len(Gc)))
    for i in range(min(16, len(Gc))): Image.fromarray(Gc[i]).save(out / f'preview_{i:02d}.png')
    if k > 1: Image.fromarray(Gc[:k * k].reshape(k, k, 64, 64, 3).transpose(0, 2, 1, 3, 4).reshape(k * 64, k * 64, 3)).save(out / 'preview_grid.png')
    m.save(out / 'model_v4_counts.pt')
    json.dump(rep, open(out / 'metrics.json', 'w'), indent=2)
    print(json.dumps(rep, indent=2)); print('PASS' if rep['pass_'] else 'FAIL')
    if dev.type == 'cuda': print(f'peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB')
if __name__ == '__main__': main()
