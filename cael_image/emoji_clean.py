"""Integer speckle cleanup for the emoji class grid (no NN).
clean(x, outline, bgc, mode_thr, iters, min_comp):
  1. majority (3x3 mode) filter on interior cells: a non-background, non-outline cell whose own class appears <= mode_thr times
     in its 3x3 window takes the window's most frequent class (ties -> keep). Outline classes (dark) are never changed.
  2. small-component removal: 4-connected components of one class with < min_comp cells (not bg, not outline) are merged
     into the most frequent class on their 4-neighbour border."""
import numpy as np, torch
def mode_filter(x, C, protect, mode_thr, iters):
    for _ in range(iters):
        oh = torch.nn.functional.one_hot(x, C).permute(0, 3, 1, 2).float()                    # B,C,32,32
        cnt = torch.nn.functional.avg_pool2d(oh, 3, 1, 1, count_include_pad=False) * 9      # approx counts (edges scaled)
        cnt = torch.round(cnt).long()
        best = cnt.argmax(1); own = cnt.gather(1, x.unsqueeze(1)).squeeze(1)
        bestc = cnt.max(1).values
        chg = (own <= mode_thr) & (bestc > own) & ~protect[x] & ~protect[best]
        if not chg.any(): break
        x = torch.where(chg, best, x)
    return x
def small_comp(x, protect, min_comp):
    """pure-python 4-connected labelling (32x32 grids are tiny)."""
    X = x.numpy().copy(); P = protect.numpy(); B, H, W = X.shape
    for b in range(B):
        g = X[b]; seen = np.zeros((H, W), bool)
        for i in range(H):
            for j in range(W):
                if seen[i, j]: continue
                c = g[i, j]; comp = [(i, j)]; seen[i, j] = True; k = 0
                while k < len(comp):
                    y, z = comp[k]; k += 1
                    for dy, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        yy, zz = y + dy, z + dz
                        if 0 <= yy < H and 0 <= zz < W and not seen[yy, zz] and g[yy, zz] == c: seen[yy, zz] = True; comp.append((yy, zz))
                if P[c] or len(comp) >= min_comp: continue
                cs = set(comp); ring = []
                for y, z in comp:
                    for dy, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        yy, zz = y + dy, z + dz
                        if 0 <= yy < H and 0 <= zz < W and (yy, zz) not in cs: ring.append(g[yy, zz])
                if ring:
                    v = np.bincount(np.array(ring)).argmax()
                    for y, z in comp: g[y, z] = v
    return torch.from_numpy(X)
def clean(x, C, outline_classes, bgc, mode_thr=2, iters=2, min_comp=4):
    protect = torch.zeros(C, dtype=torch.bool); protect[list(outline_classes)] = True; protect[bgc] = True
    if iters > 0: x = mode_filter(x, C, protect, mode_thr, iters)
    if min_comp > 1: x = small_comp(x, protect, min_comp)
    return x
def outline_classes(pal, cb, cls_of, C, L_max=35.0):
    pm = pal[cb].mean(1); out = []
    for c in range(C):
        sel = cls_of == c
        if sel.any() and float(pm[sel, 0].mean()) < L_max: out.append(c)
    return out
