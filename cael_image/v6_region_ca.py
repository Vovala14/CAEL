"""CAEL image v6: Lab palette + region-map cellular automaton + per-sample colour schemes. No neural nets.
v5 root cause of brick-red mud: a fixed 4-levels-per-channel palette (85-step) maps most skin, hair and
clothes tones to the same few colours, and 6 regions merged them further; rare-colour global fallback gave speckle.
v6:
 1. 256-colour palette by k-means in CIE Lab on training pixels; 14 regions by count-weighted k-means of palette.
 2. 32x32 figure templates: k-means (>=12 images/cluster, small clusters merged) storing per-position REGION
    count histograms and per-region colour histograms + a per-position luminance (shading) mean. No image stored.
 3. Generation: pick cluster (prior x caption words); sample a 32x32 region map; region CA sweeps at 32 and 64 with
    count-learned rule P(region | 4 neighbour regions) x template; per sample choose ONE anchor colour per region
    from the cluster's colour histogram; cell colour = anchor shifted by template shading, quantised only to palette
    colours near that anchor (no global/rare fallback). Optional face-detail: count-learned 2x2 luminance patterns
    for the skin region in the upper half.
 4. 3 passes of 3x3 mode filtering on the region map and the colour map.
Torch is only a tensor engine ('cuda' via ROCm, or CPU)."""
import argparse, json, sys, time
from collections import Counter
from pathlib import Path
import numpy as np
import torch

def mat3(x, M):  # x(...,3) @ M.T without matmul: ROCm 7.2 matmul gives wrong values for >~1M x 3 inputs
    return torch.stack([x[..., 0] * M[i, 0] + x[..., 1] * M[i, 1] + x[..., 2] * M[i, 2] for i in range(3)], -1)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.data import discover, split_records, read_rgb
from cael_image.model import tokens
from cael_image.v4_multiscale_ca import pick_device, stats, shifts

def rgb2lab(x):  # x float 0..255 (...,3)
    c = x / 255; c = torch.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = torch.tensor([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], device=x.device)
    xyz = mat3(c, M) / torch.tensor([0.95047, 1.0, 1.08883], device=x.device)
    f = torch.where(xyz > 0.008856, xyz.clamp_min(1e-9) ** (1 / 3), 7.787 * xyz + 16 / 116)
    return torch.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)
def lab2rgb(l):
    fy = (l[..., 0] + 16) / 116; fx = fy + l[..., 1] / 500; fz = fy - l[..., 2] / 200
    f = torch.stack([fx, fy, fz], -1); xyz = torch.where(f > 0.2069, f ** 3, (f - 16 / 116) / 7.787)
    xyz = xyz * torch.tensor([0.95047, 1.0, 1.08883], device=l.device)
    M = torch.tensor([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]], device=l.device)
    c = mat3(xyz, M).clamp(0, 1); c = torch.where(c > 0.0031308, 1.055 * c ** (1 / 2.4) - 0.055, 12.92 * c)
    return (c * 255).round().clamp(0, 255).to(torch.uint8)
def kmeans(X, k, iters, seed, w=None):
    g = torch.Generator().manual_seed(seed); cent = X[torch.randperm(len(X), generator=g)[:k].to(X.device)].clone()
    w = torch.ones(len(X), device=X.device) if w is None else w
    for _ in range(iters):
        a = torch.cdist(X, cent).argmin(1)
        s = torch.zeros_like(cent).index_add_(0, a, X * w[:, None]); n = torch.zeros(k, device=X.device).index_add_(0, a, w)
        cent = torch.where(n[:, None] > 0, s / n.clamp_min(1e-9)[:, None], cent)
    return cent, torch.cdist(X, cent).argmin(1)
def mode3(g, passes):
    for _ in range(passes):
        st = torch.stack(list(shifts(g).values()), -1); m, _ = torch.mode(st, -1)
        g = torch.where((st == m[..., None]).sum(-1) >= 4, m, g)
    return g
def nb_key(r, R):
    s = shifts(r); return ((s[(-1, 0)] * R + s[(1, 0)]) * R + s[(0, -1)]) * R + s[(0, 1)]
def down(x, L):  # (B,64,64,3) -> (B,L,L,3) mean
    k = 64 // L; return x.reshape(len(x), L, k, L, k, 3).mean((2, 4))

class CA6:
    def __init__(s, dev, P, R, K, minc, seed): s.dev, s.P, s.R, s.Kreq, s.minc, s.seed = dev, P, R, K, minc, seed
    def quant(s, lab):  # (...,3) -> palette ids
        sh = lab.shape[:-1]; f = lab.reshape(-1, 3)
        return torch.cat([torch.cdist(f[i:i + 65536], s.pal).argmin(1) for i in range(0, len(f), 65536)]).reshape(sh)
    def fit(s, T, caps, vocab, min_cluster):
        dev = s.dev; B = len(T); lab = rgb2lab(T.float())
        g = torch.Generator().manual_seed(s.seed)
        sample = lab.reshape(-1, 3)[torch.randint(0, B * 4096, (min(400000, B * 4096),), generator=g).to(dev)]
        s.pal, _ = kmeans(sample, s.P, 25, s.seed)
        q = s.quant(lab); cnt = torch.bincount(q.reshape(-1), minlength=s.P).float()
        rc, s.reg = kmeans(s.pal, s.R, 30, s.seed + 1, w=cnt.sqrt() + 1e-3)   # palette colour -> region
        lab32 = down(lab, 32); q32 = s.quant(lab32); r32 = s.reg[q32]; r64 = s.reg[q]
        grey = lab32[..., 0]; e = torch.zeros_like(grey)
        e[:, :, 1:] += (grey[:, :, 1:] - grey[:, :, :-1]).abs(); e[:, 1:] += (grey[:, 1:] - grey[:, :-1]).abs()
        X = torch.cat([down(lab, 16).reshape(B, -1) / 50, e[:, ::2, ::2].reshape(B, -1) / 25], 1)
        cent, a = kmeans(X, min(s.Kreq, B), 25, s.seed + 2)
        keep = (torch.bincount(a, minlength=len(cent)) >= min_cluster).nonzero().flatten()
        if len(keep) == 0: keep = torch.bincount(a, minlength=len(cent)).argmax()[None]
        a = torch.cdist(X, cent[keep]).argmin(1); s.K = len(keep)
        K, R, P = s.K, s.R, s.P; pos = torch.arange(1024, device=dev)
        s.rh = torch.zeros(K * 1024 * R, device=dev).index_add_(0, ((a[:, None] * 1024 + pos) * R + r32.reshape(B, -1)).reshape(-1),
                                                                torch.ones(B * 1024, device=dev)).reshape(K, 1024, R)
        s.ch = torch.zeros(K * R * P, device=dev).index_add_(0, ((a[:, None] * R + s.reg[q32].reshape(B, -1)) * P + q32.reshape(B, -1)).reshape(-1),
                                                             torch.ones(B * 1024, device=dev)).reshape(K, R, P)
        # shading: per cluster/position mean of (L - region mean L) at 32x32
        regL = torch.zeros(R, device=dev).index_add_(0, s.reg, s.pal[:, 0] * cnt) / torch.zeros(R, device=dev).index_add_(0, s.reg, cnt).clamp_min(1)
        dL = (lab32[..., 0] - regL[r32]).reshape(B, -1)
        s.shade = torch.zeros(K, 1024, device=dev).index_add_(0, a, dL) / torch.bincount(a, minlength=K).clamp_min(1)[:, None]
        s.ca = {L: torch.zeros(R ** 5, device=dev) for L in (32, 64)}
        for L, rm in ((32, r32), (64, r64)):
            for i in range(0, B, 256):
                x = rm[i:i + 256]; s.ca[L].index_add_(0, (nb_key(x, R) * R + x).reshape(-1), torch.ones(x.numel(), device=dev))
            s.ca[L] = s.ca[L].reshape(R ** 4, R)
        # face detail: 2x2 luminance-rank patterns (4 bits: brighter than block mean) in the skin-like region, upper half
        skin = torch.tensor([[68.0, 14.0, 18.0]], device=dev); s.skin = int(torch.cdist(rc, skin).argmin())
        L64 = lab[..., 0]; blk = L64.reshape(B, 32, 2, 32, 2).permute(0, 1, 3, 2, 4).reshape(B, 32, 32, 4)
        bits = (blk > blk.mean(-1, keepdim=True)).long(); pat = (bits * torch.tensor([1, 2, 4, 8], device=dev)).sum(-1)
        msk = (r32 == s.skin); msk[:, 16:] = False
        s.face = torch.bincount(pat[msk], minlength=16).float() + 1
        s.amp = float((blk - blk.mean(-1, keepdim=True)).abs()[msk].mean()) if msk.any() else 0.0
        s.prior = torch.bincount(a, minlength=K).float(); s.sizes = s.prior.long().tolist()
        s.vocab = vocab; s.wi = {w: i for i, w in enumerate(vocab)}; s.word = torch.zeros(len(vocab), K, device=dev)
        for i, c in enumerate(caps):
            for w in tokens(c):
                if w in s.wi: s.word[s.wi[w], a[i]] += 1
        s.regL = regL; return a
    def generate(s, prompts, seed, sweeps=6, text_weight=1.0, smooth=3, near=10.0, face=True, beta=1.0):
        dev = s.dev; gen = torch.Generator(device=dev); gen.manual_seed(seed); B = len(prompts); R, P = s.R, s.P
        draw = lambda p: torch.multinomial((p / p.sum(-1, keepdim=True)).reshape(-1, p.shape[-1]), 1, generator=gen).reshape(p.shape[:-1])
        ks = []
        for pr in prompts:
            sc = torch.log(s.prior + 1); ids = [s.wi[w] for w in tokens(pr or '') if w in s.wi]
            if ids: sc = sc + text_weight * (torch.log(s.word[ids] + 1) - torch.log(s.prior + 1)).mean(0)
            ks.append(torch.multinomial(torch.softmax(sc, 0), 1, generator=gen))
        k = torch.cat(ks)
        tmpl = (s.rh[k] + 0.01).reshape(B, 32, 32, R); tmpl = tmpl / tmpl.sum(-1, keepdim=True)
        r = draw(tmpl)
        def ca(r, L, tm):
            yy, xx = torch.meshgrid(torch.arange(L, device=dev), torch.arange(L, device=dev), indexing='ij'); chk = ((yy + xx) % 2)[None]
            for it in range(sweeps * 2):
                rows = s.ca[L][nb_key(r, R)]; ok = rows.sum(-1, keepdim=True) >= s.minc
                loc = torch.where(ok, (rows + 0.1) / (rows.sum(-1, keepdim=True) + 0.1 * R), torch.ones_like(rows))  # backoff: template only
                r = torch.where(chk == it % 2, draw(tm * loc ** beta), r)
            return mode3(r, smooth)
        r = ca(r, 32, tmpl)
        r = ca(r.repeat_interleave(2, 1).repeat_interleave(2, 2), 64, tmpl.repeat_interleave(2, 1).repeat_interleave(2, 2))
        # per-sample colour scheme: one anchor colour per region
        anchor = draw(s.ch[k] + 1e-6)                                        # (B,R) palette ids
        alab = s.pal[anchor]                                                 # (B,R,3)
        sh = s.shade[k].reshape(B, 32, 32).repeat_interleave(2, 1).repeat_interleave(2, 2)
        lab = alab[torch.arange(B, device=dev)[:, None, None], r].clone()
        lab[..., 0] = lab[..., 0] + sh - (alab[..., 0].gather(1, r.reshape(B, -1)).reshape(B, 64, 64) - s.regL[r])
        if face and s.amp > 0:
            pat = draw(s.face.expand(B, 32, 32, 16)); bits = ((pat[..., None] >> torch.arange(4, device=dev)) & 1).float() * 2 - 1
            d = bits.reshape(B, 32, 32, 2, 2).permute(0, 1, 3, 2, 4).reshape(B, 64, 64) * s.amp
            m = (r == s.skin); m[:, 32:] = False; lab[..., 0] = lab[..., 0] + d * torch.where(m, 1.0, 0.6)  # 2x2 texture everywhere, full strength on face
        # quantise only to palette colours within `near` Lab of the region's anchor (no rare/global fallback)
        q = s.quant(lab); ql = s.pal[q]; ok = (ql - alab[torch.arange(B, device=dev)[:, None, None], r]).norm(dim=-1) <= near
        q = torch.where(ok, q, anchor[torch.arange(B, device=dev)[:, None, None], r]) if face else q
        q = mode3(q, 1)  # light colour filter keeps shading; region map already had smooth passes
        return lab2rgb(s.pal[q]), k

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-Device', '--device', default='gpu', choices=['gpu', 'cpu'])
    ap.add_argument('--config', default='train_image_config.json'); ap.add_argument('--out', default='models/cael-image-female-64-v6')
    ap.add_argument('--n', type=int, default=64); ap.add_argument('--max-images', type=int, default=0)
    ap.add_argument('--palette', type=int, default=256); ap.add_argument('--regions', type=int, default=14)
    ap.add_argument('--clusters', type=int, default=48); ap.add_argument('--min-cluster', type=int, default=12)
    ap.add_argument('--min-count', type=int, default=4); ap.add_argument('--sweeps', type=int, default=6)
    ap.add_argument('--smooth', type=int, default=3); ap.add_argument('--near', type=float, default=18.0)
    ap.add_argument('--text-weight', type=float, default=1.0); ap.add_argument('--no-face', action='store_true')
    a = ap.parse_args(); t0 = time.time(); dev = pick_device(a.device); print('device', dev)
    out = Path(a.out)
    if out.exists(): raise SystemExit(f'{out} exists; choose a new --out (existing models are never overwritten).')
    cfg = json.load(open(a.config, encoding='utf-8-sig')); root = Path(cfg['dataset_dir'])
    recs = discover(root, cfg['resize_mode']); tr, va = split_records(recs, cfg['validation_fraction'], cfg['seed'])
    if a.max_images: tr, va = tr[:a.max_images], va[:max(8, a.max_images // 8)]
    caps = [r['caption'] for r in tr]; df = Counter(w for c in caps for w in tokens(c)); vocab = [w for w, c in df.most_common() if c >= 5][:256]
    T = torch.from_numpy(np.stack([read_rgb(root / r['image'], cfg['resize_mode']) for r in tr])).to(dev)
    V = torch.from_numpy(np.stack([read_rgb(root / r['image'], cfg['resize_mode']) for r in va])).to(dev)
    m = CA6(dev, a.palette, a.regions, a.clusters, a.min_count, cfg['seed'])
    m.fit(T, caps, vocab, a.min_cluster)
    print(f'fitted {len(T)} images: {m.K} clusters (min size {min(m.sizes)}), {m.P} colours, {m.R} regions in {time.time() - t0:.1f}s')
    prompts = [va[i % len(va)]['caption'] for i in range(a.n)]; Gs, Ks = [], []
    for i in range(0, a.n, 32):
        g, k = m.generate(prompts[i:i + 32], cfg['seed'] + i, a.sweeps, a.text_weight, a.smooth, a.near, not a.no_face); Gs.append(g); Ks.append(k)
    G = torch.cat(Gs); Kc = torch.cat(Ks)
    Vq = lab2rgb(m.pal[m.quant(rgb2lab(V[:256].float()))]); g2 = torch.Generator(); g2.manual_seed(1)
    rep = dict(device=str(dev), train_images=len(T), clusters=m.K, cluster_sizes=m.sizes, args=vars(a),
               clusters_used=len(set(Kc.tolist())), heldout_quantized=stats(Vq, T, g2), v6=stats(G, T, g2))
    h, g = rep['heldout_quantized'], rep['v6']
    fe = float(np.mean([abs(x - y) / max(y, 1e-6) for x, y in zip(g['falloff'], h['falloff'])]))
    checks = dict(diversity=g['pairwise_L1'] >= 0.5 * h['pairwise_L1'],
                  edges=0.5 * h['edge_density'] <= g['edge_density'] <= 2 * h['edge_density'],
                  falloff=fe <= 0.25, no_copies=g['nn_to_train_min'] >= 0.5 * h['nn_to_train_median'],
                  cluster_variety=rep['clusters_used'] >= min(8, m.K), min_cluster_ok=min(m.sizes) >= min(a.min_cluster, len(T)))
    rep.update(falloff_rel_error=round(fe, 4), checks=checks, pass_=all(checks.values()), seconds=round(time.time() - t0, 1),
               pass_rule='v5 rule + every cluster >= min-cluster images; fixed before the v6 run')
    out.mkdir(parents=True)
    from PIL import Image
    Gc = G.cpu().numpy(); n = int(np.sqrt(len(Gc)))
    for i in range(min(16, len(Gc))): Image.fromarray(Gc[i]).save(out / f'preview_{i:02d}.png')
    if n > 1: Image.fromarray(Gc[:n * n].reshape(n, n, 64, 64, 3).transpose(0, 2, 1, 3, 4).reshape(n * 64, n * 64, 3)).save(out / 'preview_grid.png')
    torch.save(dict(palette_lab=m.pal.cpu(), region_of_colour=m.reg.cpu(), region_hist=m.rh.int().cpu(), colour_hist=m.ch.int().cpu(),
                    shade=m.shade.cpu(), region_ca={L: v.int().cpu() for L, v in m.ca.items()}, face=m.face.cpu(), prior=m.prior.cpu(),
                    word=m.word.cpu(), vocab=vocab, skin_region=m.skin), out / 'model_v6.pt')
    json.dump(rep, open(out / 'metrics.json', 'w'), indent=2); print(json.dumps(rep, indent=2)); print('PASS' if rep['pass_'] else 'FAIL')
    if dev.type == 'cuda': print(f'peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB')
    sys.stdout.flush()
if __name__ == '__main__': main()


