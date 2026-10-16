"""v7 silhouette guidance (integer votes, no NN).
For a request we gather the same emoji from several licensed sets (training Noto/Blobmoji items whose CLDR name matches,
or OpenMoji/Twemoji/Emojitwo/Fluent images for fetched / mapped words), map each to the model's 32x32 class grid, and take:
  mask  = cells that are foreground in >= half of the sets (integer vote)
  edge  = mask cells 4-adjacent to the outside (outline band)
  vote  = per-cell class counts across sets (structure prior: screen rectangle, thumb, ...)
The CA sweeps then run with outside = background, edge band biased to outline classes, interior biased to the vote."""
import re, torch, numpy as np
import torch.nn.functional as Fn
def to_cls(m, F, rgb2lab):
    lab = rgb2lab(F.float()); n = len(F)
    q = torch.cat([torch.cdist(x.reshape(-1, 3), m.pal).argmin(1) for x in lab.reshape(n, -1, 3).split(64)]).reshape(n, 64, 64)
    blk = m.pal[q.reshape(-1, 32, 2, 32, 2).permute(0, 1, 3, 2, 4).reshape(-1, 32, 32, 4)].reshape(-1, 12)
    cbl = m.pal[m.cb].reshape(len(m.cb), 12)
    pid = torch.cat([torch.cdist(x, cbl).argmin(1) for x in blk.split(65536)])
    cls = m.cls_of[pid].reshape(n, 32, 32)
    fg = ~(F.float().reshape(n, 32, 2, 32, 2, 3).mean((2, 4)) > 235).all(-1)
    return cls, fg
def build_index(m, names, rgb2lab):
    cl, fg = [], []
    for s0 in range(0, len(m.T), 512):
        c, f = to_cls(m, m.T[s0:s0 + 512], rgb2lab); cl.append(c); fg.append(f)
    m.Tcls = torch.cat(cl); m.Tfg = torch.cat(fg); m.Tname = [frozenset(n) for n in names]
def match_train(m, words, k=6, min_j=0.5):
    W = frozenset(words)
    if not W: return []
    sc = []
    for i, N in enumerate(m.Tname):
        if not N: continue
        j = len(W & N) / len(W | N)
        if j >= min_j: sc.append((-(j + (0.5 if N == W else 0)), i))
    exact = [x for x in sc if m.Tname[x[1]] == W]
    if len(exact) >= 2: sc = exact            # same CLDR name in >= 2 sets: use only those (fire != fire engine)
    sc.sort(); out = []; seen = set()
    for _, i in sc:
        key = (m.Tname[i], int(m.Tfg[i].sum()))
        if key in seen: continue
        seen.add(key); out.append(i)
        if len(out) >= k: break
    return out
def consensus(cls, fg, C, shift=(0, 0)):
    n = len(cls)
    if n < 2: return None
    votes = fg.long().sum(0); mask = votes * 2 >= n
    if shift != (0, 0): mask = torch.roll(mask, shift, (0, 1))
    pad = Fn.pad((~mask).float()[None, None], (1, 1, 1, 1), value=1.0)
    out_n = Fn.max_pool2d(pad, 3, 1, 0)[0, 0] > 0
    edge = mask & out_n
    vote = torch.zeros(32, 32, C); vote.scatter_add_(2, cls.permute(1, 2, 0).long(), torch.ones(32, 32, n))
    if shift != (0, 0): vote = torch.roll(vote, shift, (0, 1))
    agree = vote.max(2).values * 3 >= 2 * n    # structure only where >= 2/3 of the sets agree
    return dict(mask=mask, edge=edge, vote=vote, agree=agree, n=n)
def apply_prior(pr, sil, C, bgc, w_vote=0.5):
    """pr: 1024,C prior -> mixed with the class vote where sets agree"""
    if sil is None: return pr
    v = (sil['vote'] + 0.05) / (sil['vote'] + 0.05).sum(2, keepdim=True)
    a = sil['agree'].reshape(1024, 1).float() * w_vote
    return (1 - a) * pr + a * v.reshape(1024, C)
def apply_guide(g, sil, C, bgc, outl, edge_boost=4.0):
    """g: 1024,C multiplicative guide -> silhouette constrained"""
    if sil is None: return g
    g = g.clone().reshape(32, 32, C); mask = sil['mask']
    g[~mask] = 1e-6; g[~mask, bgc] = 1.0
    g[mask, bgc] = g[mask, bgc] * 0.02
    if outl:
        e = sil['edge']; idx = torch.tensor(outl)
        ge = g[e]; ge[:, idx] = ge[:, idx] * edge_boost; g[e] = ge
    return g.reshape(1024, C)
