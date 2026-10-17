"""CAEL emoji v9: 2x2-patch integer cellular automaton at 32x32 (no NN).
State: a 32x32 grid; each cell holds a patch id = a 2x2 block of palette colours from a learned codebook
(the most frequent 2x2 palette blocks in TRAIN, others mapped to the nearest codebook patch in Lab).
Every patch also has a coarse class (k-means of patch mean Lab, integer labels).
Learned integer counts:
  WP[word, cell, class]   caption-word prior of coarse class per cell (one representative per base, name words x name_weight)
  G[cell, class]          global prior
  N[ctx(N,E,S,W classes), class]          class transition rule (CA neighbourhood)
  PP[class, same-as-neighbour mask (4 bits), patch]  patch rule given class + which neighbours share the class
Generation: class CA = Gibbs checkerboard sweeps, P(c) ~ N[ctx,c] * (cond[cell,c]/global)^alpha, then patch CA picks a patch
for each cell from PP; it is rendered to 64x64. Torch is only a tensor engine. No neural nets."""
import sys, json, time, re, math, zlib, argparse
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.v6_region_ca import rgb2lab, lab2rgb
from cael_image.v4_multiscale_ca import nn as NN
ap = argparse.ArgumentParser(allow_abbrev=False)
ap.add_argument('--out', required=True); ap.add_argument('--data-root', default='data/emoji'); ap.add_argument('--sources', default='noto,blobmoji')
ap.add_argument('--palette', type=int, default=48); ap.add_argument('--codebook', type=int, default=512); ap.add_argument('--classes', type=int, default=16)
ap.add_argument('--holdout', type=float, default=0.10); ap.add_argument('--min-df', type=int, default=2); ap.add_argument('--cond-mix', type=float, default=0.2)
ap.add_argument('--name-weight', type=int, default=3); ap.add_argument('--seed', type=int, default=1234); ap.add_argument('--keywords', type=int, default=1)
ap.add_argument('--calpha', type=float, default=1.6); ap.add_argument('--csweeps', type=int, default=8); ap.add_argument('--ctemp', type=float, default=0.8)
ap.add_argument('--ptemp', type=float, default=0.7); ap.add_argument('--val-mode', type=int, default=0); ap.add_argument('--steer-n', type=int, default=635)
ap.add_argument('--guard', type=float, default=0.0); ap.add_argument('--cclamp', type=float, default=8.0)
ap.add_argument('--prompts', default='happy face|cat|heart|fire|pizza|thumbs up|sad face|star')
a, _unk = ap.parse_known_args()
STOP = {'a', 'an', 'the', 'of', 'with', 'and', 'in', 'on', 'for', 'to', 'at', 'by', 'emoji', 'emojis', 'icon', 'please', 'me', 'some'}
def toks(s): return [w for w in re.findall(r'[a-z0-9]+', s.lower()) if w not in STOP]
def load(rel):
    from PIL import Image
    with Image.open(rel) as im:
        im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        return np.asarray(Image.alpha_composite(bg, im).convert('RGB').resize((64, 64), Image.Resampling.LANCZOS), dtype=np.uint8)
def kmeans(X, k, it, g):
    C = X[torch.from_numpy(g.choice(len(X), k, replace=False))].clone()
    for _ in range(it):
        lab = torch.cdist(X, C).argmin(1)
        for j in range(k):
            s = lab == j
            if s.any(): C[j] = X[s].mean(0)
    return C, torch.cdist(X, C).argmin(1)
def main():
    t0 = time.time(); torch.manual_seed(a.seed); g = np.random.default_rng(a.seed); dev = torch.device('cpu')
    out = Path(a.out)
    if out.exists(): raise SystemExit('exists')
    items = []
    for src in a.sources.split(','):
        d = Path(a.data_root) / src; m = json.load(open(d / 'manifest.json', encoding='utf-8'))
        for it in m['items']:
            cap = it['name'] + ((' ' + ' '.join(it.get('keywords', []))) if a.keywords else '')
            items.append(dict(path=d / it['file'], name=it['name'], base=src + ':' + it['base'], src=src,
                              words=sorted({src + '|' + w for w in toks(cap)}), namew={src + '|' + w for w in toks(it['name'])}, rep=False))
    seen = set()
    for i in sorted(items, key=lambda i: (i['base'], 'skin tone' in i['name'], len(i['name']))):
        if i['base'] not in seen: seen.add(i['base']); i['rep'] = True
    bn = lambda i: i['base'].split(':', 1)[1]
    nb = sorted({i['base'] for i in items if i['base'].startswith('noto:')}); rng = np.random.default_rng(a.seed); rng.shuffle(nb)
    hold = {b.split(':', 1)[1] for b in nb[:max(8, int(len(nb) * a.holdout))]}; nset = {b.split(':', 1)[1] for b in nb}
    hold |= {bn(i) for i in items if bn(i) not in nset and zlib.crc32(bn(i).encode()) % 1000 < a.holdout * 1000}
    tr = [i for i in items if bn(i) not in hold]; va = [i for i in items if bn(i) in hold]
    if a.val_mode:
        vb = lambda i: zlib.crc32(('val|' + bn(i)).encode()) % 10 == 3
        va = [i for i in tr if vb(i)]; tr = [i for i in tr if not vb(i)]
    df = {}
    for i in tr:
        if i['rep']:
            for w in i['words']: df[w] = df.get(w, 0) + 1
    vocab = sorted(w for w, n in df.items() if n >= a.min_df); wid = {w: k for k, w in enumerate(vocab)}
    nrep = sum(i['rep'] for i in tr); idf = {w: math.log(nrep / df[w]) + 0.1 for w in vocab}; srcs = a.sources.split(',')
    def enc(ws, src):
        ws = [w.split('|', 1)[1] if '|' in w else w for w in ws]
        for s_ in [src] + [x for x in srcs if x != src]:
            e = [(wid[s_ + '|' + w], idf[s_ + '|' + w]) for w in ws if s_ + '|' + w in wid]
            if e: return e
        return []
    T = torch.from_numpy(np.stack([load(i['path']) for i in tr])); V = torch.from_numpy(np.stack([load(i['path']) for i in va]))
    print(f'{len(tr)} train / {len(va)} eval, vocab {len(vocab)} ({time.time()-t0:.0f}s)', flush=True)
    # palette (Lab k-means on sampled train pixels)
    labT = rgb2lab(T.float()); px = labT.reshape(-1, 3)[torch.from_numpy(g.choice(labT.numel() // 3, 200000, replace=False))]
    pal, _ = kmeans(px, a.palette, 15, g)
    def quant(lab): return torch.cat([torch.cdist(x.reshape(-1, 3), pal).argmin(1) for x in lab.split(256)]).reshape(lab.shape[:-1])
    qT = quant(labT)                                     # n,64,64 palette ids
    P = a.palette
    pt = qT.reshape(-1, 32, 2, 32, 2).permute(0, 1, 3, 2, 4).reshape(-1, 32, 32, 4)  # 2x2 blocks
    key = ((pt[..., 0] * P + pt[..., 1]) * P + pt[..., 2]) * P + pt[..., 3]
    u, cnt = torch.unique(key.flatten(), return_counts=True)
    top = u[cnt.argsort(descending=True)[:a.codebook]]
    K = len(top); cb = torch.stack([top // P**3, (top // P**2) % P, (top // P) % P, top % P], 1)  # K,4 palette ids
    cbl = pal[cb].reshape(K, 12)
    # map all blocks to codebook ids (exact if present, else nearest in Lab)
    lut = {int(k): j for j, k in enumerate(top.tolist())}
    flat = key.flatten(); pid = torch.full_like(flat, -1)
    srt, idx = torch.sort(top); pos = torch.searchsorted(srt, flat).clamp(max=K - 1); hit = srt[pos] == flat; pid[hit] = idx[pos[hit]]
    miss = ~hit
    if miss.any():
        ml = pal[pt.reshape(-1, 4)[miss]].reshape(-1, 12)
        pid[miss] = torch.cat([torch.cdist(x, cbl).argmin(1) for x in ml.split(65536)])
    pid = pid.reshape(-1, 32, 32)
    pmean = pal[cb].mean(1)                                 # K,3
    Cc, cls_of = kmeans(pmean, a.classes, 25, g); C = a.classes
    # make white the class with the highest L (background)
    cl = cls_of[pid]                                        # n,32,32 classes
    print(f'codebook {K}, exact-hit {float(hit.float().mean()):.3f} ({time.time()-t0:.0f}s)', flush=True)
    # counts
    def nbr(x, fill):
        p = torch.nn.functional.pad(x.unsqueeze(1).float(), (1, 1, 1, 1), value=fill).squeeze(1).long()
        return p[:, :-2, 1:-1], p[:, 1:-1, 2:], p[:, 2:, 1:-1], p[:, 1:-1, :-2]
    bgc = int(cls_of[torch.cdist(torch.tensor([[100., 0., 0.]]), pmean).argmin()])
    n_, e_, s_, w_ = nbr(cl, bgc)
    ctx = ((n_ * C + e_) * C + s_) * C + w_
    Nt = torch.zeros(C**4, C, dtype=torch.int64); Nt.index_put_((ctx.flatten(), cl.flatten()), torch.ones(ctx.numel(), dtype=torch.int64), accumulate=True)
    msk = (n_ == cl).long() * 8 + (e_ == cl).long() * 4 + (s_ == cl).long() * 2 + (w_ == cl).long()
    PPt = torch.zeros(C, 16, K, dtype=torch.int64); PPt.index_put_((cl.flatten(), msk.flatten(), pid.flatten()), torch.ones(pid.numel(), dtype=torch.int64), accumulate=True)
    Gt = torch.zeros(1024, C, dtype=torch.int64); cell = torch.arange(1024).repeat(len(T))
    Gt.index_put_((cell, cl.reshape(-1)), torch.ones(cl.numel(), dtype=torch.int64), accumulate=True)
    WP = torch.zeros(len(vocab), 1024, C, dtype=torch.int32)
    for k, it in enumerate(tr):
        if not it['rep']: continue
        c1 = cl[k].reshape(-1)
        for w in it['words']:
            if w in wid:
                WP[wid[w], torch.arange(1024), c1] += (a.name_weight if w in it['namew'] else 1)
    print(f'counted ({time.time()-t0:.0f}s), WP {WP.numel()*4/1e9:.2f} GB', flush=True)
    gl = Gt.float() + 0.5; gl = gl / gl.sum(1, keepdim=True)
    def cond(wl):
        rows = []
        for ws in wl:
            if not ws: rows.append(gl); continue
            acc = 0; tw = 0
            for w, wt in ws:
                h = WP[w].float() + 0.05; acc = acc + wt * h / h.sum(1, keepdim=True); tw += wt
            rows.append((1 - a.cond_mix) * acc / tw + a.cond_mix * gl)
        return torch.stack(rows)                         # B,1024,C
    Nf = Nt.float() + 0.1; Nf = Nf / Nf.sum(1, keepdim=True)
    PPf = PPt.float() + 0.01; PPf = PPf / PPf.sum(2, keepdim=True)
    def generate(wl, seed, boost=0.0):
        gg = torch.Generator().manual_seed(seed); B = len(wl); pr = cond(wl)
        guide = (pr / gl.unsqueeze(0)).clamp(1 / a.cclamp, a.cclamp) ** a.calpha * gl.unsqueeze(0)  # B,1024,C
        x = torch.multinomial(pr.reshape(-1, C), 1, generator=gg).reshape(B, 32, 32)
        yy, xx = torch.meshgrid(torch.arange(32), torch.arange(32), indexing='ij'); chk = ((yy + xx) % 2).bool()
        for sw in range(a.csweeps):
            for par in (False, True):
                n_, e_, s_, w_ = nbr(x, bgc); c_ = ((n_ * C + e_) * C + s_) * C + w_
                lp = torch.log(Nf[c_]) + torch.log(guide.reshape(B, 32, 32, C))
                t = (a.ctemp + boost) if sw < a.csweeps - 2 else (a.ctemp + boost) * 0.6
                pr_ = torch.softmax(lp / t, -1).reshape(-1, C)
                new = torch.multinomial(pr_, 1, generator=gg).reshape(B, 32, 32)
                sel = (chk == par).unsqueeze(0); x = torch.where(sel, new, x)
        n_, e_, s_, w_ = nbr(x, bgc)
        mk = (n_ == x).long() * 8 + (e_ == x).long() * 4 + (s_ == x).long() * 2 + (w_ == x).long()
        pp = PPf[x, mk]                                   # B,32,32,K
        pp = torch.softmax(torch.log(pp) / (a.ptemp + boost), -1)
        p = torch.multinomial(pp.reshape(-1, K), 1, generator=gg).reshape(B, 32, 32)
        blk = cb[p]                                       # B,32,32,4 palette ids
        img = blk.reshape(B, 32, 32, 2, 2).permute(0, 1, 3, 2, 4).reshape(B, 64, 64)
        return lab2rgb(pal[img]).clamp(0, 255).to(torch.uint8)
    GU = dict(checked=0, resampled=0, failed=0)
    def gen(wl, seed):
        outs = []
        for s0 in range(0, len(wl), 32):
            sub = wl[s0:s0 + 32]; X = generate(sub, seed + s0)
            if a.guard > 0:
                GU['checked'] += len(sub)
                for t_ in range(1, 9):
                    bad = NN(X, T) < a.guard
                    if not bad.any(): break
                    bi = torch.nonzero(bad).flatten().tolist(); GU['resampled'] += len(bi)
                    X[bi] = generate([sub[i] for i in bi], seed + s0 + 7919 * t_, 0.25 * t_)
                bad = NN(X, T) < a.guard; GU['failed'] += int(bad.sum()); GU.setdefault('failed_caps', []).extend([' '.join(vocab[w] for w, _ in sub[i]) for i in torch.nonzero(bad).flatten().tolist()][:3])
            outs.append(X)
        return torch.cat(outs)
    prompts = a.prompts.split('|'); pw_ = [enc(toks(p), srcs[c % len(srcs)]) for p in prompts for c in range(8)]
    G = gen(pw_, a.seed)
    nv = min(a.steer_n, len(va)); sel = g.permutation(len(va))[:nv]; perm = np.roll(np.arange(nv), 1)
    own = [enc(va[k]['words'], va[k]['src']) for k in sel]; oth = [own[perm[k]] for k in range(nv)]
    Go = gen(own, a.seed + 7); Gs = gen(oth, a.seed + 7); tgt = rgb2lab(V[torch.from_numpy(sel)].float())
    def dist(X): return (rgb2lab(X.float()) - tgt).reshape(nv, 16, 4, 16, 4, 3).mean((2, 4)).abs().mean((1, 2, 3))
    do, ds = dist(Go), dist(Gs)
    isn = torch.tensor([va[k]['base'].startswith('noto:') for k in sel])
    steer = dict(n=nv, own_L1=round(float(do.mean()), 3), other_L1=round(float(ds.mean()), 3), own_wins=round(float((do < ds).float().mean()), 3),
                 own_wins_noto=round(float((do < ds)[isn].float().mean()), 3), unknown=sum(1 for e in own if not e))
    Vq = lab2rgb(pal[quant(rgb2lab(V[:256].float()))]).clamp(0, 255).to(torch.uint8)
    Gall = torch.cat([G, Go]); dg = NN(Gall, T); dh = NN(Vq, T)
    nocopy = dict(nn_min=round(float(dg.min()), 4), held_med=round(float(dh.median()), 4), threshold=round(0.5 * float(dh.median()), 4))
    nocopy['pass'] = nocopy['nn_min'] >= nocopy['threshold']
    pw = float(torch.cdist(Gall[:192].reshape(192, -1).float(), Gall[:192].reshape(192, -1).float()).mean() / math.sqrt(64 * 64 * 3))
    rep = dict(args=vars(a), steering=steer, nocopy=nocopy, guard=GU, codebook=K, classes=C, seconds=round(time.time() - t0, 1))
    out.mkdir(parents=True); json.dump(rep, open(out / 'metrics.json', 'w'), indent=1)
    from PIL import Image, ImageDraw
    Gc = G.numpy(); img = Image.new('RGB', (120 + 8 * 66, len(prompts) * 66), 'white'); dr = ImageDraw.Draw(img)
    for r, p_ in enumerate(prompts):
        dr.text((4, r * 66 + 26), p_, fill='black')
        for c in range(8): img.paste(Image.fromarray(Gc[r * 8 + c]), (120 + c * 66, r * 66 + 1))
    img.save(out / 'prompt_grid.png')
    torch.save(dict(pal=pal, cb=cb, cls_of=cls_of, Nt=Nt, PPt=PPt, Gt=Gt, WP=WP.to_sparse(), vocab=vocab, idf=idf, bgc=bgc, args=vars(a)), out / 'model_emoji.pt')
    print(json.dumps(dict(steering=steer, nocopy=nocopy, guard=GU)), flush=True); print('PASS' if nocopy['pass'] else 'FAIL')
if __name__ == '__main__': main()
