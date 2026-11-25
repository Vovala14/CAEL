"""Cell rules for same-size ARC tasks (non-neural): each output cell = f(features of the input cell).

Every cell of every demonstration becomes one row of hand-written features (its colour, its neighbours, the object
it belongs to, what it sees along each direction, enclosure, symmetric partners, row and column contents, position
patterns). A small decision tree is grown until it reproduces every demonstration cell exactly. A leaf either gives a
fixed colour or copies one feature's colour (e.g. "the colour seen to the left"). The smallest exact tree wins; a
tree that cannot fit the demonstrations exactly gives no answer.
"""
from collections import Counter
import time

import numpy as np
from scipy import ndimage

S4 = ndimage.generate_binary_structure(2, 1)
S8 = ndimage.generate_binary_structure(2, 2)
DIRS8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
RAYS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


def bg_of(g):
    v, c = np.unique(g, return_counts=True)
    return int(v[np.argmax(c)])


def features(g):
    """(names, colour_feature_mask, matrix H*W x F)."""
    g = np.asarray(g, dtype=np.int16)
    h, w = g.shape
    bg = bg_of(g)
    cols = []
    names = []
    is_col = []

    def add(name, arr, colour=False):
        names.append(name)
        is_col.append(colour)
        cols.append(np.asarray(arr, dtype=np.int16).reshape(-1))

    yy, xx = np.mgrid[0:h, 0:w]
    add('color', g, True)
    add('is_bg', g == bg)
    pad = np.full((h + 2, w + 2), -1, dtype=np.int16)
    pad[1:-1, 1:-1] = g
    nb = []
    for k, (dy, dx) in enumerate(DIRS8):
        v = pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
        nb.append(v)
        add(f'nb{k}', v, True)
    nb = np.stack(nb)
    fgn = ((nb != bg) & (nb != -1))
    add('n_fg4', fgn[[1, 3, 4, 6]].sum(0))
    add('n_fg8', fgn.sum(0))
    add('n_same8', (nb == g[None]).sum(0))
    # what the cell sees along each ray: first non-background colour and its distance
    for k, (dy, dx) in enumerate(RAYS):
        # one pass per direction: walk each cell's predecessor first (dynamic programming along the ray)
        seen = np.full((h, w), -1, dtype=np.int16)
        dist = np.zeros((h, w), dtype=np.int16)
        ys = range(h - 1, -1, -1) if dy > 0 else range(h)
        xs = range(w - 1, -1, -1) if dx > 0 else range(w)
        gl = g.tolist()
        sl = seen.tolist()
        dl = dist.tolist()
        for y in ys:
            for x in xs:
                y2, x2 = y + dy, x + dx
                if 0 <= y2 < h and 0 <= x2 < w:
                    if gl[y2][x2] != bg:
                        sl[y][x] = gl[y2][x2]
                        dl[y][x] = 1
                    elif sl[y2][x2] != -1:
                        sl[y][x] = sl[y2][x2]
                        dl[y][x] = dl[y2][x2] + 1
        add(f'ray{k}', np.array(sl), True)
        add(f'raydist{k}', np.minimum(np.array(dl), 9))
    # pairs of opposite rays seeing the same colour: the cell lies between two equal colours
    for a, b in ((0, 1), (2, 3), (4, 7), (5, 6)):
        sa, sb = cols[names.index(f'ray{a}')].reshape(h, w), cols[names.index(f'ray{b}')].reshape(h, w)
        add(f'between{a}{b}', np.where((sa == sb) & (sa != -1), sa, -1), True)
    # objects
    fg = g != bg
    for diag, by_color, tag in ((False, True, 'o4'), (True, False, 'o8m')):
        lab = np.zeros((h, w), dtype=np.int32)
        n = 0
        if by_color:
            for c in np.unique(g[fg]):
                l, k = ndimage.label(g == c, structure=S8 if diag else S4)
                lab[l > 0] = l[l > 0] + n
                n += k
        else:
            lab, n = ndimage.label(fg, structure=S8 if diag else S4)
        size = np.zeros(n + 1, dtype=np.int16)
        hh = np.zeros(n + 1, dtype=np.int16)
        ww = np.zeros(n + 1, dtype=np.int16)
        ncol = np.zeros(n + 1, dtype=np.int16)
        touch = np.zeros(n + 1, dtype=np.int16)
        objs = ndimage.find_objects(lab)
        for i, sl in enumerate(objs, 1):
            if sl is None:
                continue
            m = lab[sl] == i
            size[i] = min(int(m.sum()), 30)
            hh[i] = sl[0].stop - sl[0].start
            ww[i] = sl[1].stop - sl[1].start
            ncol[i] = len(np.unique(g[sl][m]))
            touch[i] = int(sl[0].start == 0 or sl[1].start == 0 or sl[0].stop == h or sl[1].stop == w)
        sizes = sorted({int(s) for s in size[1:]}, reverse=True)
        rank = np.array([0] + [sizes.index(int(s)) if int(s) in sizes else 0 for s in size[1:]], dtype=np.int16)
        add(f'{tag}_size', size[lab])
        add(f'{tag}_h', hh[lab])
        add(f'{tag}_w', ww[lab])
        add(f'{tag}_ncol', ncol[lab])
        add(f'{tag}_touch', touch[lab])
        add(f'{tag}_rank', np.minimum(rank[lab], 5))
        add(f'{tag}_largest', (rank[lab] == 0) & (lab > 0))
        add(f'{tag}_smallest', (size[lab] == min(size[1:]) if n else 0) & (lab > 0))
        # position inside the object's bounding box
        top = np.zeros((h, w), dtype=np.int16)
        left = np.zeros((h, w), dtype=np.int16)
        for i, sl in enumerate(objs, 1):
            if sl is None:
                continue
            m = lab == i
            top[m] = (yy[m] - sl[0].start == 0) * 1 + (sl[0].stop - 1 - yy[m] == 0) * 2
            left[m] = (xx[m] - sl[1].start == 0) * 1 + (sl[1].stop - 1 - xx[m] == 0) * 2
        add(f'{tag}_edge_y', top)
        add(f'{tag}_edge_x', left)
    # enclosed background (holes) and inside some object's bounding box
    holes = ndimage.binary_fill_holes(fg) & ~fg
    add('enclosed', holes)
    lab_h, _ = ndimage.label(~fg, structure=S4)
    border_labels = set(np.unique(np.concatenate([lab_h[0], lab_h[-1], lab_h[:, 0], lab_h[:, -1]])).tolist())
    add('bg_region_open', np.isin(lab_h, list(border_labels)) & ~fg)
    # colour of the enclosing boundary for holes
    enc_col = np.full((h, w), -1, dtype=np.int16)
    if holes.any():
        lab_hole, nh = ndimage.label(holes, structure=S4)
        for i in range(1, nh + 1):
            m = lab_hole == i
            ring = ndimage.binary_dilation(m, structure=S4) & ~m
            cs = np.unique(g[ring])
            cs = cs[cs != bg]
            if len(cs) == 1:
                enc_col[m] = cs[0]
        add('enclosed_by', enc_col, True)
    else:
        add('enclosed_by', enc_col, True)
    # colour counts around the cell, inside other objects' boxes, the nearest coloured cell, the object's colours
    for c in range(10):
        if not (g == c).any():
            add(f'nbcnt{c}', np.zeros((h, w)))
            add(f'inbox{c}', np.zeros((h, w)))
            continue
        add(f'nbcnt{c}', (nb == c).sum(0))
        box = np.zeros((h, w), bool)
        lab_c, n_c = ndimage.label(g == c, structure=S8)
        for sl in ndimage.find_objects(lab_c):
            if sl is not None:
                box[sl] = True
        add(f'inbox{c}', box & (g != c))
    if fg.any():
        dist_t, (iy, ix) = ndimage.distance_transform_cdt(~fg, metric='taxicab', return_indices=True)
        near = g[iy, ix].astype(np.int16)
        add('near_col', np.where(fg, -1, near), True)
        add('near_dist', np.minimum(dist_t, 9))
    else:
        add('near_col', np.full((h, w), -1), True)
        add('near_dist', np.zeros((h, w)))
    lab8, n8 = ndimage.label(fg, structure=S8)
    has = np.zeros((10, n8 + 1), bool)
    for c in range(10):
        if (g == c).any():
            has[c, np.unique(lab8[(g == c) & fg])] = True
    for c in range(10):
        add(f'obj_has{c}', has[c][lab8] & (lab8 > 0))
    # symmetric partners
    add('mir_lr', g[:, ::-1], True)
    add('mir_ud', g[::-1], True)
    add('mir_rot', g[::-1, ::-1], True)
    add('mir_t', g.T if h == w else np.full((h, w), -1), True)
    # row / column contents
    for c in range(10):
        add(f'row_has{c}', (g == c).any(1)[:, None] * np.ones((1, w)))
        add(f'col_has{c}', (g == c).any(0)[None, :] * np.ones((h, 1)))
    rowfg = np.where(fg.any(1)[:, None], 1, 0) * np.ones((1, w))
    add('row_any', rowfg)
    add('col_any', np.where(fg.any(0)[None, :], 1, 0) * np.ones((h, 1)))
    # position patterns
    add('y', np.minimum(yy, 29))
    add('x', np.minimum(xx, 29))
    add('yr', np.minimum(h - 1 - yy, 29))
    add('xr', np.minimum(w - 1 - xx, 29))
    for m in (2, 3):
        add(f'y%{m}', yy % m)
        add(f'x%{m}', xx % m)
    add('border', (yy == 0) | (xx == 0) | (yy == h - 1) | (xx == w - 1))
    add('diag', (yy == xx) | (yy + xx == w - 1))
    # colour frequency rank in the grid
    v, n = np.unique(g, return_counts=True)
    order = {int(c): i for i, c in enumerate(v[np.argsort(-n, kind='stable')])}
    add('col_rank', np.vectorize(lambda c: min(order[int(c)], 4))(g))
    minority = int(v[np.argmin(n)]) if (n == n.min()).sum() == 1 else -1
    add('grid_minority', np.full((h, w), minority), True)
    majfg = -1
    if fg.any():
        vf, nf = np.unique(g[fg], return_counts=True)
        majfg = int(vf[np.argmax(nf)]) if (nf == nf.max()).sum() == 1 else -1
    add('grid_major_fg', np.full((h, w), majfg), True)
    add('bg', np.full((h, w), bg), True)
    return names, np.array(is_col), np.stack(cols, 1)


# ---------------------------------------------------------------- tree
class Leaf:
    def __init__(self, kind, val):
        self.kind, self.val = kind, val   # 'const' colour, or 'copy' feature index

    def size(self):
        return 1

    def predict(self, X):
        return np.full(len(X), self.val, dtype=np.int16) if self.kind == 'const' else X[:, self.val].copy()


class Node:
    def __init__(self, f, v, yes, no):
        self.f, self.v, self.yes, self.no = f, v, yes, no

    def size(self):
        return 1 + self.yes.size() + self.no.size()

    def predict(self, X):
        out = np.empty(len(X), dtype=np.int16)
        m = X[:, self.f] == self.v
        if m.any():
            out[m] = self.yes.predict(X[m])
        if (~m).any():
            out[~m] = self.no.predict(X[~m])
        return out


def _leaf(X, y, col_feats):
    if (y == y[0]).all():
        return Leaf('const', int(y[0]))
    for j in col_feats:
        if (X[:, j] == y).all():
            return Leaf('copy', int(j))
    return None


def _gini(y):
    _, n = np.unique(y, return_counts=True)
    p = n / n.sum()
    return 1.0 - (p * p).sum()


def _splits(X, y, col_feats, E):
    """Candidate splits ranked by copy-aware impurity: [(score, feature, value, mask)]."""
    n = len(y)
    out = []
    for j in range(X.shape[1]):
        col = X[:, j]
        vals = np.unique(col)
        if len(vals) < 2 or len(vals) > 12:
            continue
        for v in vals:
            m = col == v
            k = int(m.sum())
            if k == 0 or k == n:
                continue
            ya, yb = y[m], y[~m]
            ia = 0.0 if (ya == ya[0]).all() or (E.shape[1] and E[m].all(0).any()) else _gini(ya) + 0.05
            ib = 0.0 if (yb == yb[0]).all() or (E.shape[1] and E[~m].all(0).any()) else _gini(yb) + 0.05
            out.append(((k * ia + (n - k) * ib) / n, j, int(v), m))
    out.sort(key=lambda t: t[0])
    return out


DEADLINE = [float('inf')]


def grow_mdl(X, y, col_feats, depth, budget, k=4, levels=2):
    """Like grow, but at the top levels the k best splits are each grown and the smallest exact tree is kept."""
    lf = _leaf(X, y, col_feats)
    if lf is not None:
        return lf
    if depth == 0 or budget[0] <= 0:
        return None
    if levels <= 0 or time.monotonic() > DEADLINE[0]:
        return grow(X, y, col_feats, depth, budget)
    E = (X[:, col_feats] == y[:, None]) if col_feats else np.zeros((len(y), 0), bool)
    best = None
    seen_masks = set()
    for score, j, v, m in _splits(X, y, col_feats, E):
        key = m.tobytes()
        if key in seen_masks:
            continue
        seen_masks.add(key)
        if len(seen_masks) > k:
            break
        b = [budget[0]]
        yes = grow_mdl(X[m], y[m], col_feats, depth - 1, b, k, levels - 1)
        if yes is None:
            continue
        no = grow_mdl(X[~m], y[~m], col_feats, depth - 1, b, k, levels - 1)
        if no is None:
            continue
        t = Node(j, v, yes, no)
        if best is None or t.size() < best.size():
            best = t
    return best


def grow(X, y, col_feats, depth, budget):
    """Greedy exact tree. A side that is pure, or equals one colour feature (a copy leaf), counts as solved, so splits
    that leave a copyable side are found even when the plain impurity would not drop."""
    lf = _leaf(X, y, col_feats)
    if lf is not None:
        return lf
    if depth == 0 or budget[0] <= 0:
        return None
    budget[0] -= 1
    n = len(y)
    E = (X[:, col_feats] == y[:, None]) if col_feats else np.zeros((n, 0), bool)
    best = None
    for j in range(X.shape[1]):
        col = X[:, j]
        vals = np.unique(col)
        if len(vals) < 2 or len(vals) > 12:
            continue
        for v in vals:
            m = col == v
            k = int(m.sum())
            if k == 0 or k == n:
                continue
            ya, yb = y[m], y[~m]
            ia = 0.0 if (ya == ya[0]).all() or (E.shape[1] and E[m].all(0).any()) else _gini(ya) + 0.05
            ib = 0.0 if (yb == yb[0]).all() or (E.shape[1] and E[~m].all(0).any()) else _gini(yb) + 0.05
            score = (k * ia + (n - k) * ib) / n
            if best is None or score < best[0] - 1e-12:
                best = (score, j, int(v), m)
    if best is None:
        return None
    _, j, v, m = best
    yes = grow(X[m], y[m], col_feats, depth - 1, budget)
    if yes is None:
        return None
    no = grow(X[~m], y[~m], col_feats, depth - 1, budget)
    if no is None:
        return None
    return Node(j, v, yes, no)


POS_ABS = ('y', 'x', 'yr', 'xr', 'diag', 'border')
POS_MOD = ('y%2', 'x%2', 'y%3', 'x%3')


def _fit(Xs, Ys, allowed, col_feats, max_depth):
    X = np.concatenate([x[:, allowed] for x in Xs])
    Y = np.concatenate(Ys)
    cf = [allowed.index(j) for j in col_feats if j in allowed]
    tree = grow_mdl(X, Y, cf, max_depth, [MAX_NODES])
    return tree


MAX_NODES = 120


def _with_layers(names, is_col, F, layers, layer_names, base):
    """Append extra colour layers (same-size grids from general grid operations) as features."""
    if not layers:
        return names, is_col, F
    cols = [np.asarray(L, dtype=np.int16).reshape(-1) for L in layers]
    chg = [(np.asarray(L) != base).reshape(-1).astype(np.int16) for L in layers]
    names = list(names) + [f'L:{n}' for n in layer_names] + [f'Lchg:{n}' for n in layer_names]
    is_col = np.concatenate([is_col, np.ones(len(cols), bool), np.zeros(len(chg), bool)])
    return names, is_col, np.concatenate([F, np.stack(cols, 1), np.stack(chg, 1)], 1)


def solve(train_pairs, tests, max_depth=8, layers=None, layer_names=(), test_layers=None, seconds=4.0):
    """[(cost, description, [prediction per test])] or [] when no small exact tree exists."""
    DEADLINE[0] = time.monotonic() + seconds   # after this the tree search is plain greedy
    Xs, Ys = [], []
    names = is_col = None
    for a, b in train_pairs:
        a = np.asarray(a)
        b = np.asarray(b)
        if a.shape != b.shape:
            return []
        names, is_col, F = features(a)
        if layers:
            names, is_col, F = _with_layers(names, is_col, F, layers[len(Xs)], layer_names, a)
        Xs.append(F)
        Ys.append(b.reshape(-1).astype(np.int16))
    if all((x[:, 0] == y).all() for x, y in zip(Xs, Ys)):
        return []   # the identity: nothing to learn
    col_feats = [j for j, c in enumerate(is_col) if c]
    tiers = [[j for j, n in enumerate(names) if n not in POS_ABS + POS_MOD],
             [j for j, n in enumerate(names) if n not in POS_ABS],
             list(range(len(names)))]
    TF = []
    for i, t in enumerate(tests):
        nm, ic, F = features(np.asarray(t))
        if layers:
            F = _with_layers(nm, ic, F, test_layers[i], layer_names, np.asarray(t))[2]
        TF.append(F)
    for tier, allowed in enumerate(tiers):
        tree = _fit(Xs, Ys, allowed, col_feats, max_depth)
        if tree is None:
            continue
        # leave one demonstration out: the rule learned without it must predict it
        held = 0
        if len(Xs) >= 3:
            for i in range(len(Xs)):
                t2 = _fit(Xs[:i] + Xs[i + 1:], Ys[:i] + Ys[i + 1:], allowed, col_feats, max_depth)
                if t2 is not None and (t2.predict(Xs[i][:, allowed]) == Ys[i]).all():
                    held += 1
            if held < len(Xs) - 1:
                continue        # does not generalise across demonstrations
        preds = []
        for t, F in zip(tests, TF):
            p = tree.predict(F[:, allowed]).reshape(np.asarray(t).shape)
            if (p < 0).any() or (p > 9).any():
                preds = None
                break
            preds.append(p.astype(int).tolist())
        if preds is None:
            continue
        return [(1.0 + 0.5 * tree.size() + tier, f'cell-tree:t{tier}:{tree.size()}', preds)]
    return []
