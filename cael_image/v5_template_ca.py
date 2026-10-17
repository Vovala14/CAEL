"""CAEL image v5: global figure templates + region-locked multi-scale integer CA. No neural nets.
(1) k-means (tensor ops) on 16x16 colour + 16x16 edge/silhouette maps -> K figure clusters (small ones merged).
    Each cluster stores per-position colour COUNT histograms at 16x16 and region-label histograms (never one image).
(2) Generation: sample cluster (prior x caption-word counts), sample 16x16 cells from the cluster's per-position
    histograms, CA sweeps combining template counts with local 4-neighbour count rules; then 32 and 64 split/refine
    CA (v4 count tables) restricted to colours of the template's region at that position (children keep parent region).
(3) 3x3 majority smoothing CA. Torch is only a tensor engine ('cuda' via ROCm or CPU)."""
import argparse, json, sys, time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.data import discover, split_records, read_rgb
from cael_image.model import tokens
from cael_image.v4_multiscale_ca import CA4, C, pick_device, q64, palette, key4, shifts, stats

def kmeans(X, k, iters, gen):
    gen = torch.Generator().manual_seed(int(torch.randint(0, 2**31, (1,), generator=gen, device=gen.device).item()))
    cent = X[torch.randperm(len(X), generator=gen)[:k].to(X.device)].clone()
    for _ in range(iters):
        a = torch.cdist(X, cent).argmin(1)
        for j in range(k):
            m = a == j
            cent[j] = X[m].mean(0) if m.any() else X[torch.randint(0, len(X), (1,), generator=gen).item()]
    return cent, torch.cdist(X, cent).argmin(1)

class CA5:
    def __init__(s, ca4, dev): s.l, s.dev = ca4, dev
    def fit(s, T, captions, K, regions, min_size, gen, iters=20):
        f = T.float(); g16 = f.reshape(-1, 16, 4, 16, 4, 3).mean((2, 4))
        grey = g16.mean(-1); e = torch.zeros_like(grey)
        e[:, :, 1:] += (grey[:, :, 1:] - grey[:, :, :-1]).abs(); e[:, 1:] += (grey[:, 1:] - grey[:, :-1]).abs()
        X = torch.cat([g16.reshape(len(T), -1) / 255, 2 * (e.reshape(len(T), -1) / 255)], 1)
        cent, a = kmeans(X, K, iters, gen)
        sizes = torch.bincount(a, minlength=K); keep = (sizes >= min_size).nonzero().flatten()
        a = torch.cdist(X, cent[keep]).argmin(1); s.K = len(keep)  # merge small clusters into nearest kept one
        # region labels: k-means over training pixel colours of the 64-colour palette (count weighted)
        q = q64(f.reshape(-1, 3)); cnt = torch.bincount(q, minlength=C).float()
        pal = palette(s.dev).float(); used = (cnt > 0).nonzero().flatten()
        rc, _ = kmeans(pal[used].repeat_interleave(torch.clamp((cnt[used] / cnt.sum() * 4000).long(), 1, 400), 0), regions, 20, gen)
        s.reg = torch.cdist(pal, rc).argmin(1); s.R = regions          # colour -> region id
        q16 = q64(g16); s.hist = torch.zeros(s.K, 256, C, device=s.dev)
        s.hist.view(-1).index_add_(0, ((a[:, None] * 256 + torch.arange(256, device=s.dev)) * C + q16.reshape(len(T), -1)).reshape(-1),
                                   torch.ones(q16.numel(), device=s.dev))
        s.glob = s.hist.sum(0, keepdim=True)
        s.prior = torch.bincount(a, minlength=s.K).float()
        s.word = torch.zeros(len(s.l.vocab), s.K, device=s.dev)
        for i, cap in enumerate(captions):
            for w in tokens(cap):
                if w in s.l.wi: s.word[s.l.wi[w], a[i]] += 1
        s.sizes = s.prior.long().tolist(); return a
    def template(s, k):  # per-position probability, smoothed toward global so small clusters do not reproduce images
        h = s.hist[k] + 0.25 * s.glob[0] / s.glob[0].sum(-1, keepdim=True) * s.prior[k][:, None, None] + 1e-4
        return h / h.sum(-1, keepdim=True)
    def pick(s, prompts, gen, text_weight):
        out = []
        for p in prompts:
            sc = torch.log(s.prior + 1)
            ids = [s.l.wi[w] for w in tokens(p or '') if w in s.l.wi]
            if ids: sc = sc + text_weight * (torch.log(s.word[ids] + 1) - torch.log(s.prior + 1)).mean(0)
            out.append(torch.multinomial(torch.softmax(sc, 0), 1, generator=gen))
        return torch.cat(out)
    def generate(s, prompts, seed, sweeps=6, ftemp=0.6, text_weight=1.0, smooth=2, local=0.5, leak=0.002):
        gen = torch.Generator(device=s.dev); gen.manual_seed(seed); l = s.l
        k = s.pick(prompts, gen, text_weight); tp = s.template(k).reshape(-1, 16, 16, C)
        region16 = s.reg[None, None, None, :] == torch.arange(s.R, device=s.dev)[:, None, None, None]  # R x1x1xC
        rp = torch.einsum('bhwc,rc->bhwr', tp, (s.reg[None] == torch.arange(s.R, device=s.dev)[:, None]).float())
        regmap = rp.argmax(-1)                                              # template region label per 16x16 cell
        g = l.draw(tp, 1.0, gen)
        chk = ((torch.arange(16, device=s.dev)[:, None] + torch.arange(16, device=s.dev)[None]) % 2)[None]
        par8 = None
        for it in range(sweeps * 2):  # CA at 16: template counts x local neighbour count rule
            loc = l.ref[16][l.up2(g[:, ::2, ::2]) * 4096 + key4(g)]
            loc = (loc + 1) / (loc + 1).sum(-1, keepdim=True)
            new = l.draw(tp * loc ** local, 1.0, gen); g = torch.where(chk == it % 2, new, g)
        def mask(L):
            r = regmap.repeat_interleave(L // 16, 1).repeat_interleave(L // 16, 2)
            return torch.where(s.reg[None, None, None] == r[..., None], 1.0, leak)
        for L in (32, 64):
            par = l.up2(g); pk = l.up2(key4(g)); qd = l.quad(L).expand_as(par); M = mask(L)
            back = l.upb[L][par * 4 + qd] + 1e-3
            g = l.draw(l.backoff(l.up[L][(par * 4096 + pk) * 4 + qd], back) * M, 1.0 if L == 32 else ftemp, gen)
            c = (l.quad(L) == 0) | (l.quad(L) == 3)
            for it in range(sweeps):
                new = l.draw(l.backoff(l.ref[L][par * 4096 + key4(g)], back) * M, 1.0 if L == 32 else ftemp, gen)
                g = torch.where(c == (it % 2 == 0), new, g)
        for _ in range(smooth):
            st = torch.stack(list(shifts(g).values()), -1); mode, _ = torch.mode(st, -1)
            g = torch.where((st == mode[..., None]).sum(-1) >= 5, mode, g)
        return palette(s.dev)[g], k

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-Device', '--device', default='gpu', choices=['gpu', 'cpu'])
    ap.add_argument('--config', default='train_image_config.json'); ap.add_argument('--out', default='models/cael-image-female-64-v5')
    ap.add_argument('--n', type=int, default=64); ap.add_argument('--max-images', type=int, default=0)
    ap.add_argument('--clusters', type=int, default=48); ap.add_argument('--regions', type=int, default=6)
    ap.add_argument('--min-cluster', type=int, default=12); ap.add_argument('--min-count', type=int, default=4)
    ap.add_argument('--text-weight', type=float, default=1.0); ap.add_argument('--ftemp', type=float, default=0.6)
    ap.add_argument('--sweeps', type=int, default=6); ap.add_argument('--smooth', type=int, default=2)
    a = ap.parse_args(); t0 = time.time(); dev = pick_device(a.device); print('device', dev)
    out = Path(a.out)
    if out.exists(): raise SystemExit(f'{out} exists; choose a new --out (existing models are never overwritten).')
    cfg = json.load(open(a.config, encoding='utf-8-sig')); root = Path(cfg['dataset_dir'])
    recs = discover(root, cfg['resize_mode']); tr, va = split_records(recs, cfg['validation_fraction'], cfg['seed'])
    if a.max_images: tr, va = tr[:a.max_images], va[:max(8, a.max_images // 8)]
    df = Counter(w for r in tr for w in tokens(r['caption'])); vocab = [w for w, c in df.most_common() if c >= 5][:256]
    T = torch.from_numpy(np.stack([read_rgb(root / r['image'], cfg['resize_mode']) for r in tr])).to(dev)
    V = torch.from_numpy(np.stack([read_rgb(root / r['image'], cfg['resize_mode']) for r in va])).to(dev)
    caps = [r['caption'] for r in tr]; l = CA4(vocab, dev, a.min_count)
    for i in range(0, len(T), 256): l.observe(T[i:i + 256], caps[i:i + 256])
    gen = torch.Generator(device=dev); gen.manual_seed(cfg['seed'])
    m = CA5(l, dev); m.fit(T, caps, min(a.clusters, len(T)), a.regions, a.min_cluster if len(T) > 200 else 2, gen)
    print(f'fitted {len(T)} images, {m.K} clusters (sizes min {min(m.sizes)}) in {time.time() - t0:.1f}s')
    prompts = [va[i % len(va)]['caption'] for i in range(a.n)]; Gs, Ks = [], []
    for i in range(0, a.n, 64):
        g, k = m.generate(prompts[i:i + 64], cfg['seed'] + i, a.sweeps, a.ftemp, a.text_weight, a.smooth); Gs.append(g); Ks.append(k)
    G = torch.cat(Gs); Kc = torch.cat(Ks)
    Vq = palette(dev)[q64(V[:256].float())]; g2 = torch.Generator(); g2.manual_seed(1)
    rep = dict(device=str(dev), train_images=len(T), clusters=m.K, cluster_sizes=m.sizes, args=vars(a),
               clusters_used=len(set(Kc.tolist())), heldout_quantized=stats(Vq, T, g2), v5=stats(G, T, g2))
    h, g = rep['heldout_quantized'], rep['v5']
    fe = float(np.mean([abs(x - y) / max(y, 1e-6) for x, y in zip(g['falloff'], h['falloff'])]))
    checks = dict(diversity=g['pairwise_L1'] >= 0.5 * h['pairwise_L1'],
                  edges=0.5 * h['edge_density'] <= g['edge_density'] <= 2 * h['edge_density'],
                  falloff=fe <= 0.25, no_copies=g['nn_to_train_min'] >= 0.5 * h['nn_to_train_median'],
                  cluster_variety=rep['clusters_used'] >= min(8, m.K))
    rep.update(falloff_rel_error=round(fe, 4), checks=checks, pass_=all(checks.values()), seconds=round(time.time() - t0, 1),
               pass_rule='v4 rule (diversity, edges, falloff<=0.25, no copies) + >=8 distinct clusters used in 64 samples; fixed before v5 run')
    out.mkdir(parents=True)
    from PIL import Image
    Gc = G.cpu().numpy(); n = int(np.sqrt(len(Gc)))
    for i in range(min(16, len(Gc))): Image.fromarray(Gc[i]).save(out / f'preview_{i:02d}.png')
    if n > 1: Image.fromarray(Gc[:n * n].reshape(n, n, 64, 64, 3).transpose(0, 2, 1, 3, 4).reshape(n * 64, n * 64, 3)).save(out / 'preview_grid.png')
    torch.save(dict(hist=m.hist.int().cpu(), prior=m.prior.cpu(), word=m.word.cpu(), reg=m.reg.cpu(), vocab=vocab), out / 'model_v5_templates.pt')
    l.save(out / 'model_v5_local_counts.pt')
    json.dump(rep, open(out / 'metrics.json', 'w'), indent=2); print(json.dumps(rep, indent=2)); print('PASS' if rep['pass_'] else 'FAIL')
    if dev.type == 'cuda': print(f'peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB')
if __name__ == '__main__': main()



