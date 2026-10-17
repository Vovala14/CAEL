"""CAEL emoji v3 (= v2 + cross-source base split; v2 changes: one representative per base name for word priors, name words counted x--name-weight): caption-conditioned v10 integer CA (no NN, no hand-drawn parts) for 64x64 emoji.
Data: per-source folders under --data-root (noto now; blobmoji later: drop data/emoji/blobmoji/ with the same
manifest.json format {items:[{file,name,base,keywords}]} and pass --sources noto,blobmoji). RGBA is alpha-composited
on WHITE (255,255,255) at load (recorded in metrics.json).
Caption conditioning (learned counts only): for every caption word w (CLDR short name + CLDR keywords) we count
palette colours at every position of scales 4..32: wp[L][w, y, x, colour]. A prompt's prior = idf-weighted mean of
its known words' normalised histograms (64 uses the 32 prior upsampled), mixed with the global prior, used as the
v10 ratio guide on top of the shared (caption-free) CA rule tables. Unknown prompt words are ignored; a prompt with
no known word falls back to the unconditional prior (FLAGGED in metrics as fallback_prompts).
Split: 10% of BASE names held out (skin-tone variants stay on one side) for no-copy and steering tests."""
import sys, json, time, re, math
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cael_image.v10_prior_ca as v10   # parses v10 guide args (parse_known_args) and patches v9
import cael_image.v9_generative_ca as v9
import argparse
A = v10.A
ap = argparse.ArgumentParser()
ap.add_argument('-Device', '--device', default='gpu', choices=['gpu', 'cpu'])
ap.add_argument('--out', required=True); ap.add_argument('--data-root', default='data/emoji'); ap.add_argument('--sources', default='noto,blobmoji')
ap.add_argument('--palette', type=int, default=48); ap.add_argument('--coarse', type=int, default=16)
ap.add_argument('--buckets', type=int, default=8); ap.add_argument('--min-count', type=int, default=2)
ap.add_argument('--hash-bits', default='20,21,21,22'); ap.add_argument('--holdout', type=float, default=0.10)
ap.add_argument('--min-df', type=int, default=2); ap.add_argument('--cond-mix', type=float, default=0.1)
ap.add_argument('--keywords', type=int, default=1, help='1 = use CLDR keywords as caption words too')
ap.add_argument('--per-style', type=int, default=1, help='1 = word priors per source (style); grid alternates styles'); ap.add_argument('--name-weight', type=int, default=2); ap.add_argument('--seed', type=int, default=1234); ap.add_argument('--flip', action='store_true')
ap.add_argument('--despeckle', type=int, default=0); ap.add_argument('--best-of', type=int, default=1); ap.add_argument('--steer-n', type=int, default=128); ap.add_argument('--shape-t', type=float, default=0); ap.add_argument('--shape-k', type=int, default=0); ap.add_argument('--template', type=int, default=0); ap.add_argument('--tpl-thr', type=float, default=0.0); ap.add_argument('--val-mode', type=int, default=0); ap.add_argument('--guard', type=float, default=0.1); ap.add_argument('--shape-w', type=float, default=1.0); ap.add_argument('--shape-fill', type=int, default=1); ap.add_argument('--prompts', default='happy face|cat|heart|fire|pizza|thumbs up|sad face|star')
a = ap.parse_args()
STOP = {'a', 'an', 'the', 'of', 'with', 'and', 'in', 'on', 'for', 'to', 'at', 'by'}
def toks(s): return [w for w in re.findall(r'[a-z0-9]+', s.lower()) if w not in STOP]

class ECA(v9.GCA):   # v9.GCA is v10.GCA10 after import
    def alloc_words(s, V):
        s.V = V; s.wp = {L: torch.zeros(V * L * L, s.P, device=s.dev, dtype=torch.int32) for L in (4, 8, 16, 32)}
    def observe_words(s, lab, pi, pw):
        p = s.pyr(lab)
        for L in s.wp:
            g = p[L][pi]; pos = torch.arange(L * L, device=s.dev).reshape(1, L, L).expand_as(g)
            s.add(s.wp[L], pw.view(-1, 1, 1) * (L * L) + pos, g)
    def make_cond(s, wl):   # wl: list of [(word id, weight)]
        s.cond = {}
        for L in v9.LEVELS:
            base = s.prior[L].float(); base = base / base.sum(1, keepdim=True).clamp_min(1); rows = []
            for ws in wl:
                if not ws: rows.append(base); continue
                Lw = min(L, 32); acc = 0; tw = 0
                for w, wt in ws:
                    h = s.wp[Lw].view(s.V, Lw * Lw, s.P)[w].float(); acc = acc + wt * h / h.sum(1, keepdim=True).clamp_min(1); tw += wt
                h = acc / tw
                if L == 64: h = h.reshape(32, 32, s.P).repeat_interleave(2, 0).repeat_interleave(2, 1).reshape(64 * 64, s.P)
                rows.append((1 - a.cond_mix) * h + a.cond_mix * base)
            s.cond[L] = torch.stack(rows)
    def guide(s, L, g):
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

def load(root, rel):
    from PIL import Image
    with Image.open(root / rel) as im:
        im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        return np.asarray(Image.alpha_composite(bg, im).convert('RGB').resize((64, 64), Image.Resampling.LANCZOS), dtype=np.uint8)

def despeckle(X, passes):
    # majority clean-up: a pixel whose colour occurs <= iso times in its 3x3 window takes the most common neighbour colour (no NN)
    if passes <= 0: return X
    import torch.nn.functional as F
    for _ in range(passes):
        B, H, W, C = X.shape; code = (X[..., 0].long() << 16) | (X[..., 1].long() << 8) | X[..., 2].long()
        P = F.pad(code.float().unsqueeze(1), (1, 1, 1, 1), mode='replicate').squeeze(1).long()
        nb = torch.stack([P[:, dy:dy + H, dx:dx + W] for dy in range(3) for dx in range(3)], -1)  # B,H,W,9
        same = (nb.unsqueeze(-1) == nb.unsqueeze(-2)).sum(-1)  # count of each window entry
        cnt_self = same[..., 4]; best = nb.gather(-1, same.argmax(-1, keepdim=True)).squeeze(-1)
        new = torch.where(cnt_self <= 2, best, code)
        X = torch.stack([(new >> 16) & 255, (new >> 8) & 255, new & 255], -1).to(X.dtype)
    return X
def shape_clean(X, m, t, fill):
    # shape-aware clean-up (integer/count based, no NN): the caption's word prior gives P(background) per pixel.
    # pixels the prior says are background (P_bg > 1-t) are set to white; background pixels inside the caption's
    # silhouette (P_bg < t) are filled with the most common non-white colour in their 5x5 window.
    if t <= 0: return X
    import torch.nn.functional as F
    B = X.shape[0]; wl = v9.rgb2lab(torch.tensor([[[[255., 255., 255.]]]], device=X.device))
    bg = int((m.pal - wl.reshape(1, 3)).abs().sum(1).argmin())
    pbg = m.cond[64][:B, :, bg].float().reshape(B, 64, 64)
    idx = m.quant(v9.rgb2lab(X.float())).reshape(B, 64, 64)
    white = torch.tensor([255, 255, 255], dtype=X.dtype, device=X.device)
    isbg = idx == bg
    X = torch.where((pbg > 1 - t).unsqueeze(-1), white, X)
    if fill:
        code = (X[..., 0].long() << 16) | (X[..., 1].long() << 8) | X[..., 2].long(); W = 0xFFFFFF
        P = F.pad(code.float().unsqueeze(1), (2, 2, 2, 2), mode='replicate').squeeze(1).long()
        nb = torch.stack([P[:, dy:dy + 64, dx:dx + 64] for dy in range(5) for dx in range(5)], -1)
        cnt = (nb.unsqueeze(-1) == nb.unsqueeze(-2)).sum(-1).masked_fill(nb == W, -1)
        best = nb.gather(-1, cnt.argmax(-1, keepdim=True)).squeeze(-1)
        hole = (code == W) & (pbg < t) & (best != W)
        new = torch.where(hole, best, code)
        X = torch.stack([(new >> 16) & 255, (new >> 8) & 255, new & 255], -1).to(X.dtype)
    return X
def main():
    t0 = time.time(); dev = v9.pick_device(a.device); print('device', dev, flush=True)
    v9.HBITS.update(zip((8, 16, 32, 64), (int(x) for x in a.hash_bits.split(','))))
    out = Path(a.out)
    if out.exists(): raise SystemExit(f'{out} exists; choose a new --out')
    items = []
    for src in a.sources.split(','):
        d = Path(a.data_root) / src; m = json.load(open(d / 'manifest.json', encoding='utf-8'))
        for it in m['items']:
            cap = it['name'] + ((' ' + ' '.join(it.get('keywords', []))) if a.keywords else '')
            items.append(dict(path=d / it['file'], name=it['name'], base=src + ':' + it['base'], words=sorted({src + '|' + w for w in toks(cap)}) if a.per_style else sorted(set(toks(cap))), src=src,
                              namew={src + '|' + w for w in toks(it['name'])} if a.per_style else set(toks(it['name'])), rep=False))
    seen = set()   # word priors count ONE representative per base name (skin-tone variants would swamp words like heart/fire)
    for i in sorted(items, key=lambda i: (i['base'], 'skin tone' in i['name'], len(i['name']))):
        if i['base'] not in seen: seen.add(i['base']); i['rep'] = True
    # v3 split: by base NAME across sources (same base -> same side). Noto held-out set identical to v1/v2
    # (same seed, same sorted noto base list); bases only in other sources: stable hash, ~holdout fraction.
    import zlib
    bn = lambda i: i['base'].split(':', 1)[1]
    nb = sorted({i['base'] for i in items if i['base'].startswith('noto:')}); rng = np.random.default_rng(a.seed); rng.shuffle(nb)
    hold = {b.split(':', 1)[1] for b in nb[:max(8, int(len(nb) * a.holdout))]}; nset = {b.split(':', 1)[1] for b in nb}
    hold |= {bn(i) for i in items if bn(i) not in nset and zlib.crc32(bn(i).encode()) % 1000 < a.holdout * 1000}
    tr = [i for i in items if bn(i) not in hold]; va = [i for i in items if bn(i) in hold]
    if a.val_mode:   # threshold tuning: split TRAIN bases into train'/val (crc32 % 10 == 3); the 635 held-out are dropped entirely
        vb = lambda i: zlib.crc32(('val|' + bn(i)).encode()) % 10 == 3
        va = [i for i in tr if vb(i)]; tr = [i for i in tr if not vb(i)]
    df = {}
    for i in tr:
        if not i['rep']: continue
        for w in i['words']: df[w] = df.get(w, 0) + 1
    vocab = sorted(w for w, n in df.items() if n >= a.min_df); wid = {w: k for k, w in enumerate(vocab)}
    nrep = sum(i['rep'] for i in tr); idf = {w: math.log(nrep / df[w]) + 0.1 for w in vocab}
    srcs = a.sources.split(',')
    def enc(ws, src=None):   # ws: plain words (prompt) or already-tagged words (held-out captions)
        if not a.per_style: return [(wid[w], idf[w]) for w in ws if w in wid]
        if ws and '|' in ws[0]: ws = [w.split('|', 1)[1] for w in ws]
        for s_ in [src] + [x for x in srcs if x != src]:   # FALLBACK: other style if the word is unknown in this one
            e = [(wid[s_ + '|' + w], idf[s_ + '|' + w]) for w in ws if s_ + '|' + w in wid and 'shp' not in w]
            if e and WC:
                v = sum(WC[s_ + '|' + w] * idf[s_ + '|' + w] / max(1.0, WC[s_ + '|' + w].sum()) for w in ws if s_ + '|' + w in WC and s_ + '|' + w in idf)
                if not isinstance(v, int):
                    st = s_ + '|shp' + str(int(np.argmax(v)))
                    if st in wid: e = e + [(wid[st], a.shape_w * max(x[1] for x in e))]
            if e: return e
        return []
    T = torch.from_numpy(np.stack([load(Path('.'), i['path']) for i in tr])).to(dev)
    V = torch.from_numpy(np.stack([load(Path('.'), i['path']) for i in va])).to(dev)
    WC = {}
    if a.shape_k > 0:
        # shape classes: integer k-means on 16x16 foreground masks of TRAIN representatives (no NN); the class
        # becomes an extra caption token so each class keeps its own per-pixel prior; at generation the class is
        # inferred from the caption WORDS only (train word->class counts), never from the held-out image.
        fg = ((T.float().mean(-1) < 245).float().reshape(len(T), 16, 4, 16, 4).mean((2, 4)) > 0.5).reshape(len(T), -1).cpu().numpy().astype(np.float32)
        rr = np.random.default_rng(a.seed); repi = np.array([k for k, i in enumerate(tr) if i['rep']])
        C = fg[rr.choice(repi, a.shape_k, replace=False)]
        for _ in range(25):
            lab_ = ((fg[:, None, :] - C[None]) ** 2).sum(-1).argmin(1)
            for c in range(a.shape_k):
                if (lab_[repi] == c).any(): C[c] = fg[repi][lab_[repi] == c].mean(0)
        for k, i in enumerate(tr):
            i['shape'] = int(lab_[k]); sw = i['src'] + '|shp' + str(lab_[k]) if a.per_style else 'shp' + str(lab_[k])
            i['words'] = sorted(set(i['words']) | {sw})
            if i['rep']:
                for w in i['words']:
                    if 'shp' not in w: WC.setdefault(w, np.zeros(a.shape_k))[lab_[k]] += 1
        df.clear()
        for i in tr:
            if not i['rep']: continue
            for w in i['words']: df[w] = df.get(w, 0) + 1
        vocab[:] = sorted(w for w, n in df.items() if n >= a.min_df); wid.clear(); wid.update({w: k for k, w in enumerate(vocab)})
        idf.clear(); idf.update({w: math.log(nrep / df[w]) + 0.1 for w in vocab})
        print('shape classes', np.bincount(lab_[repi], minlength=a.shape_k).tolist(), flush=True)
    print(f'{len(items)} emoji ({len(tr)} train / {len(va)} held-out, {len(hold)} held-out base names), vocab {len(vocab)} ({time.time()-t0:.1f}s)', flush=True)
    m = ECA(dev, a.palette, a.coarse, a.buckets, a.min_count); m.alloc(); m.alloc_words(len(vocab))
    labT = v9.rgb2lab(T.float()); m.fit_palette(labT, a.seed)
    for s0 in range(0, len(T), 128):
        x = labT[s0:s0 + 128]; pi, pw = [], []
        for j, it in enumerate(tr[s0:s0 + 128]):
            if not it['rep']: continue
            for w in it['words']:
                if w in wid:
                    for _ in range(a.name_weight if w in it['namew'] else 1): pi.append(j); pw.append(wid[w])
        pi = torch.tensor(pi, device=dev, dtype=torch.long); pw = torch.tensor(pw, device=dev, dtype=torch.long)
        for xx in ([x, x.flip(2)] if a.flip else [x]):
            m.observe(xx); m.observe_words(xx, pi, pw)
    print(f'counted ({time.time()-t0:.1f}s) coverage {m.coverage()}', flush=True)
    # ---- template-guided silhouette (chosen by caption WORDS only) ----
    from cael_image.v4_multiscale_ca import nn as _nn
    repk = [k for k, i in enumerate(tr) if i['rep']]
    WM = torch.zeros(len(repk), len(vocab), device=dev)
    for r_, k in enumerate(repk):
        for w in tr[k]['words']:
            if w in wid and w in tr[k]['namew']: WM[r_, wid[w]] = 1   # v8: own NAME words only
    FGM = (T[torch.tensor(repk, device=dev)].float().mean(-1) < 245)
    def _fill(X, mask, passes=8):
        import torch.nn.functional as F
        W = 0xFFFFFF; code = (X[..., 0].long() << 16) | (X[..., 1].long() << 8) | X[..., 2].long()
        code = torch.where(mask, code, torch.full_like(code, W))
        for _ in range(passes):
            hole = mask & (code == W)
            if not hole.any(): break
            P = F.pad(code.float().unsqueeze(1), (1, 1, 1, 1), mode='replicate').squeeze(1).long()
            nb = torch.stack([P[:, dy:dy + 64, dx:dx + 64] for dy in range(3) for dx in range(3)], -1)
            cnt = (nb.unsqueeze(-1) == nb.unsqueeze(-2)).sum(-1).masked_fill(nb == W, -1)
            best = nb.gather(-1, cnt.argmax(-1, keepdim=True)).squeeze(-1)
            code = torch.where(hole & (best != W), best, code)
        for b in range(code.shape[0]):   # leftover holes: most common non-white colour of that image
            h = mask[b] & (code[b] == W)
            if h.any():
                v, c = torch.unique(code[b][code[b] != W], return_counts=True)
                if len(v): code[b][h] = v[c.argmax()]
        return torch.stack([(code >> 16) & 255, (code >> 8) & 255, code & 255], -1).to(X.dtype)
    def _shift_mask(mk, g):
        import torch.nn.functional as F
        k = int(g.integers(0, 3))  # 0 erode, 1 dilate, 2 shift by 1-2 px
        f = mk.float().unsqueeze(0).unsqueeze(0)
        if k == 0: return (-F.max_pool2d(-f, 3, 1, 1))[0, 0] > 0.5
        if k == 1: return F.max_pool2d(f, 3, 1, 1)[0, 0] > 0.5
        return torch.roll(mk, (int(g.integers(-2, 3)), int(g.integers(-2, 3))), (0, 1))
    GUARD = dict(tried=0, perturbed=0, fellback=0)
    def template(X, wlc, seed):
        if a.template <= 0: return X
        B = X.shape[0]; wv = torch.zeros(B, len(vocab), device=dev)
        for b, ws in enumerate(wlc):
            for w, wt in ws: wv[b, w] += wt
        sc = (wv @ WM.T) / wv.sum(1, keepdim=True).clamp_min(1e-6); top = sc.topk(3, dim=1)
        ok = top.values[:, 0] >= a.tpl_thr
        masks = (FGM[top.indices].sum(1) >= 2); g = np.random.default_rng(seed)   # majority vote of top-3 outlines
        Y = _fill(X, masks)
        Y = torch.where(ok.view(-1, 1, 1, 1), Y, X)
        GUARD['tried'] += int(ok.sum())
        for tries in range(5):
            d = _nn(Y, T); bad = ok & (d < a.guard)
            if not bad.any(): break
            if tries == 4:
                GUARD['fellback'] += int(bad.sum()); Y = torch.where(bad.view(-1, 1, 1, 1), X, Y); break
            GUARD['perturbed'] += int(bad.sum())
            for b in torch.nonzero(bad).flatten().tolist(): masks[b] = _shift_mask(masks[b], g)
            Y = torch.where(bad.view(-1, 1, 1, 1), _fill(X, masks), Y)
        return Y
    def gen(wl, seed):
        outs = []
        for s0 in range(0, len(wl), 32):
            m.make_cond(wl[s0:s0 + 32]); nb = len(wl[s0:s0 + 32]); best = None; bsc = None
            for kk in range(max(1, a.best_of)):
                Xk = despeckle(template(despeckle(shape_clean(m.generate(nb, seed + s0 + 100003 * kk), m, a.shape_t, a.shape_fill), a.despeckle), wl[s0:s0 + 32], seed + s0 + kk), 1 if a.template else 0)
                if a.best_of <= 1: best = Xk; break
                idx = m.quant(v9.rgb2lab(Xk.float())).reshape(nb, -1)  # palette index per pixel (64x64)
                pc = m.cond[64].float().clamp_min(1e-6)
                sc = torch.log(pc.gather(-1, idx.unsqueeze(-1)).squeeze(-1)).mean(1)
                if best is None: best, bsc = Xk, sc
                else:
                    w = sc > bsc; best = torch.where(w.view(-1, 1, 1, 1), Xk, best); bsc = torch.maximum(sc, bsc)
            outs.append(best)
        return torch.cat(outs)
    prompts = a.prompts.split('|'); pw_ = [enc(toks(p), srcs[c % len(srcs)]) for p in prompts for c in range(8)]
    fallback = sorted({prompts[k // 8] for k, e in enumerate(pw_) if not e})
    G = gen(pw_, a.seed)
    # steering: held-out emoji generated from own caption vs another held-out emoji's caption
    nv = min(a.steer_n, len(va)); sel = rng.permutation(len(va))[:nv]; perm = np.roll(np.arange(nv), 1)
    own = [enc(va[k]['words'], va[k]['src']) for k in sel]; oth = [own[perm[k]] for k in range(nv)]
    Go = gen(own, a.seed + 7); Gs = gen(oth, a.seed + 7)
    tgt = v9.rgb2lab(V[torch.tensor(sel, device=dev)].float())
    def dist(X):  # Lab L1 at 16x16 (layout+colour, not texture)
        d = (v9.rgb2lab(X.float()) - tgt).reshape(nv, 16, 4, 16, 4, 3).mean((2, 4)).abs().mean((1, 2, 3)); return d
    do, ds = dist(Go), dist(Gs)
    steer = dict(n=nv, own_caption_L1=round(float(do.mean()), 3), other_caption_L1=round(float(ds.mean()), 3),
                 own_wins=round(float((do < ds).float().mean()), 3),
                 own_wins_noto=round(float((do < ds)[torch.tensor([va[k]['base'].startswith('noto:') for k in sel], device=dev)].float().mean()), 3), heldout_unknown_caption=sum(1 for e in own if not e))
    g2 = torch.Generator(); g2.manual_seed(1)
    Gall = torch.cat([G, Go])
    Vq = v9.lab2rgb(m.pal[m.quant(v9.rgb2lab(V[:256].float()))])
    gs, hs = v9.stats(Gall, T, g2), v9.stats(Vq, T, g2)
    fe = float(np.mean([abs(x - y) / max(y, 1e-6) for x, y in zip(gs['falloff'], hs['falloff'])]))
    checks = dict(diversity=gs['pairwise_L1'] >= 0.5 * hs['pairwise_L1'], edges=0.5 * hs['edge_density'] <= gs['edge_density'] <= 2 * hs['edge_density'],
                  falloff=fe <= 0.25, no_copies=gs['nn_to_train_min'] >= 0.5 * hs['nn_to_train_median'], steering=steer['own_wins'] > 0.5)
    rep = dict(device=str(dev), background='white (255,255,255) alpha composite', sources=a.sources, train=len(tr), heldout=len(va), vocab=len(vocab),
               args=vars(a), v10=vars(A), steering=steer, fallback_prompts=fallback, generated=gs, heldout_quantized=hs,
               falloff_rel_error=round(fe, 4), guard=dict(GUARD), checks=checks, pass_=all(checks.values()), seconds=round(time.time() - t0, 1))
    out.mkdir(parents=True)
    from PIL import Image, ImageDraw
    Gc = G.cpu().numpy(); W = 120; img = Image.new('RGB', (W + 8 * 66, len(prompts) * 66), 'white'); dr = ImageDraw.Draw(img)
    for r, p in enumerate(prompts):
        dr.text((4, r * 66 + 26), p, fill='black')
        for c in range(8): img.paste(Image.fromarray(Gc[r * 8 + c]), (W + c * 66, r * 66 + 1))
    img.save(out / 'prompt_grid.png')
    Oc, Sc, Vc = Go[:16].cpu().numpy(), Gs[:16].cpu().numpy(), V[torch.tensor(sel[:16], device=dev)].cpu().numpy()
    st = Image.new('RGB', (16 * 66, 3 * 66), 'white')
    for k in range(16):
        for r, X in enumerate((Vc, Oc, Sc)): st.paste(Image.fromarray(X[k]), (k * 66, r * 66))
    st.save(out / 'steering_heldout_real_own_other.png')
    json.dump([va[k]['name'] for k in sel[:16]], open(out / 'steering_names.json', 'w'))
    torch.save(dict(palette_lab=m.pal.cpu(), coarse=m.coarse.cpu(), seed={k: v.cpu() for k, v in m.seed.items()},
                    tables={L: {k: v.to_sparse().cpu() for k, v in d.items()} for L, d in m.t.items()},
                    prior={L: v.cpu() for L, v in m.prior.items()}, sym={L: v.to_sparse().cpu() for L, v in m.sym.items()},
                    word_prior={L: v.to_sparse().cpu() for L, v in m.wp.items()}, vocab=vocab, idf=idf, args=vars(a), v10=vars(A)), out / 'model_emoji.pt')
    json.dump(rep, open(out / 'metrics.json', 'w'), indent=2)
    print(json.dumps(dict(steering=steer, checks=checks, falloff=round(fe, 3), nn_min=gs['nn_to_train_min'], held_nn_med=hs['nn_to_train_median'],
                          div=[gs['pairwise_L1'], hs['pairwise_L1']], edges=[gs['edge_density'], hs['edge_density']], fallback=fallback)))
    print('PASS' if rep['pass_'] else 'FAIL')
    if dev.type == 'cuda': print(f'peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB')
    sys.stdout.flush(); import os; os._exit(0)

if torch.cuda.is_available():
    tot = torch.cuda.get_device_properties(0).total_memory; torch.cuda.set_per_process_memory_fraction(min(1.0, A.vram_cap_gb * 2**30 / tot))
main()











