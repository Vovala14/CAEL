"""A compositional grid-program search for ARC-style tasks (non-neural).

A program is a short chain of general grid operations (geometry, cropping to a chosen object, splitting and
combining parts, gravity, tiling, symmetry, colour filters, scaling, ...) followed by an optional colour mapping.
The search applies every operation to all demonstration inputs at once, merges programs that give the same grids,
and keeps only programs whose result reproduces every demonstration output exactly. Shorter programs rank first
(minimum description length). Nothing here knows task ids or answers.
"""
from collections import Counter
import time

import numpy as np
from scipy import ndimage

S4 = ndimage.generate_binary_structure(2, 1)
S8 = ndimage.generate_binary_structure(2, 2)


# ---------------------------------------------------------------- helpers
def bg_of(g):
    v, c = np.unique(g, return_counts=True)
    return int(v[np.argmax(c)])


def crop_mask(g, m):
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return None
    return g[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def comps(g, bg, diag, by_color):
    """[(mask, colours)] connected components of non-background cells."""
    out = []
    fg = g != bg
    if by_color:
        for c in np.unique(g[fg]):
            lab, n = ndimage.label(g == c, structure=S8 if diag else S4)
            for i in range(1, n + 1):
                out.append(lab == i)
    else:
        lab, n = ndimage.label(fg, structure=S8 if diag else S4)
        for i in range(1, n + 1):
            out.append(lab == i)
    return out


def _unique_pick(objs, keys, want):
    vals = [k for k in keys]
    target = want(vals)
    idx = [i for i, v in enumerate(vals) if v == target]
    return objs[idx[0]] if len(idx) == 1 else None


def _shape_key(m):
    c = crop_mask(m.astype(np.uint8), m)
    return c.shape + (c.tobytes(),)


# ---------------------------------------------------------------- object selectors
def select_obj(g, how, diag, by_color):
    bg = bg_of(g)
    objs = comps(g, bg, diag, by_color)
    if not objs or len(objs) > 60:
        return None
    if len(objs) == 1:
        return objs[0] if how in ('largest', 'smallest') else None
    if how == 'largest':
        return _unique_pick(objs, [int(m.sum()) for m in objs], max)
    if how == 'smallest':
        return _unique_pick(objs, [int(m.sum()) for m in objs], min)
    if how == 'bbox_largest':
        return _unique_pick(objs, [int(np.ptp(np.nonzero(m)[0]) + 1) * int(np.ptp(np.nonzero(m)[1]) + 1) for m in objs], max)
    if how == 'top':
        return _unique_pick(objs, [int(np.nonzero(m)[0].min()) for m in objs], min)
    if how == 'bottom':
        return _unique_pick(objs, [int(np.nonzero(m)[0].max()) for m in objs], max)
    if how == 'left':
        return _unique_pick(objs, [int(np.nonzero(m)[1].min()) for m in objs], min)
    if how == 'right':
        return _unique_pick(objs, [int(np.nonzero(m)[1].max()) for m in objs], max)
    if how in ('uniq_color', 'common_color'):
        cols = [tuple(sorted(np.unique(g[m]).tolist())) for m in objs]
        cnt = Counter(cols)
        if how == 'uniq_color':
            idx = [i for i, c in enumerate(cols) if cnt[c] == 1]
        else:
            top = max(cnt.values())
            idx = [i for i, c in enumerate(cols) if cnt[c] == top]
        return objs[idx[0]] if len(idx) == 1 else None
    if how == 'uniq_shape':
        keys = [_shape_key(m) for m in objs]
        cnt = Counter(keys)
        idx = [i for i, k in enumerate(keys) if cnt[k] == 1]
        return objs[idx[0]] if len(idx) == 1 else None
    if how == 'most_colors':
        return _unique_pick(objs, [len(np.unique(g[m])) for m in objs], max)
    if how == 'densest':
        return _unique_pick(objs, [round(m.sum() / max(1, (np.ptp(np.nonzero(m)[0]) + 1) * (np.ptp(np.nonzero(m)[1]) + 1)), 4) for m in objs], max)
    if how == 'sparsest':
        return _unique_pick(objs, [round(m.sum() / max(1, (np.ptp(np.nonzero(m)[0]) + 1) * (np.ptp(np.nonzero(m)[1]) + 1)), 4) for m in objs], min)
    if how == 'symmetric':
        keys = []
        for m in objs:
            c = crop_mask(g, m)
            keys.append(bool(np.array_equal(c, c[:, ::-1]) or np.array_equal(c, c[::-1])))
        idx = [i for i, k in enumerate(keys) if k]
        return objs[idx[0]] if len(idx) == 1 else None
    if how == 'asymmetric':
        keys = []
        for m in objs:
            c = crop_mask(g, m)
            keys.append(bool(np.array_equal(c, c[:, ::-1]) or np.array_equal(c, c[::-1])))
        idx = [i for i, k in enumerate(keys) if not k]
        return objs[idx[0]] if len(idx) == 1 else None
    return None


SELECTORS = ('largest', 'smallest', 'bbox_largest', 'top', 'bottom', 'left', 'right', 'uniq_color', 'common_color',
             'uniq_shape', 'most_colors', 'densest', 'sparsest', 'symmetric', 'asymmetric')


# ---------------------------------------------------------------- operations: grid -> grid or None
def op_crop_nonbg(g):
    return crop_mask(g, g != bg_of(g))


def op_crop_non0(g):
    return crop_mask(g, g != 0)


def make_crop_obj(how, diag, by_color, keep_all):
    def f(g):
        m = select_obj(g, how, diag, by_color)
        if m is None:
            return None
        if keep_all:
            return crop_mask(g, m)
        o = np.full_like(g, bg_of(g))
        o[m] = g[m]
        return crop_mask(o, m)
    return f


def make_keep_obj(how, diag, by_color):
    def f(g):
        m = select_obj(g, how, diag, by_color)
        if m is None:
            return None
        o = np.full_like(g, bg_of(g))
        o[m] = g[m]
        return o
    return f


def make_remove_obj(how, diag, by_color):
    def f(g):
        m = select_obj(g, how, diag, by_color)
        if m is None:
            return None
        o = g.copy()
        o[m] = bg_of(g)
        return o
    return f


def make_filter_color(c):
    def f(g):
        if not (g == c).any():
            return None
        o = np.full_like(g, bg_of(g))
        o[g == c] = c
        return o
    return f


def make_erase_color(c):
    def f(g):
        b = bg_of(g)
        if c == b or not (g == c).any():
            return None
        o = g.copy()
        o[g == c] = b
        return o
    return f


def op_keep_major_fg(g):
    b = bg_of(g)
    v, n = np.unique(g[g != b], return_counts=True)
    if len(v) < 2:
        return None
    o = np.full_like(g, b)
    c = v[np.argmax(n)]
    o[g == c] = c
    return o


def op_keep_minor_fg(g):
    b = bg_of(g)
    v, n = np.unique(g[g != b], return_counts=True)
    if len(v) < 2:
        return None
    o = np.full_like(g, b)
    c = v[np.argmin(n)]
    if (n == n.min()).sum() > 1:
        return None
    o[g == c] = c
    return o


def make_scale_up(k):
    def f(g):
        if g.shape[0] * k > 30 or g.shape[1] * k > 30:
            return None
        return np.kron(g, np.ones((k, k), dtype=g.dtype))
    return f


def op_downscale(g):
    """Undo a block scaling: the smallest block size that makes every block a single colour."""
    h, w = g.shape
    for k in range(2, min(h, w) + 1):
        if h % k or w % k:
            continue
        s = g[::k, ::k]
        if np.array_equal(np.kron(s, np.ones((k, k), dtype=g.dtype)), g):
            return s
    return None


def op_compress_dups(g):
    keep_r = [0] + [i for i in range(1, g.shape[0]) if not np.array_equal(g[i], g[i - 1])]
    g2 = g[keep_r]
    keep_c = [0] + [j for j in range(1, g2.shape[1]) if not np.array_equal(g2[:, j], g2[:, j - 1])]
    o = g2[:, keep_c]
    return None if o.shape == g.shape else o


def op_remove_bg_lines(g):
    b = bg_of(g)
    rows = ~(g == b).all(1)
    cols = ~(g == b).all(0)
    if rows.all() and cols.all():
        return None
    o = g[rows][:, cols]
    return o if o.size else None


def make_tile(ry, rx, mode):
    def f(g):
        h, w = g.shape
        if h * ry > 30 or w * rx > 30:
            return None
        if mode == 'plain':
            return np.tile(g, (ry, rx))
        rows = []
        for i in range(ry):
            row = []
            for j in range(rx):
                t = g
                if mode == 'mirror':
                    if i % 2:
                        t = t[::-1]
                    if j % 2:
                        t = t[:, ::-1]
                elif mode == 'rot':
                    t = np.rot90(g, -(2 * i + j) if (ry, rx) == (2, 2) else 0)
                row.append(t)
            rows.append(np.hstack(row))
        return np.vstack(rows)
    return f


def make_half(which):
    def f(g):
        h, w = g.shape
        if which in ('top', 'bottom'):
            if h < 2:
                return None
            k = h // 2
            if h % 2 == 1:   # odd height: a separator row in the middle
                return g[:k] if which == 'top' else g[k + 1:]
            return g[:k] if which == 'top' else g[k:]
        if w < 2:
            return None
        k = w // 2
        if w % 2 == 1:
            return g[:, :k] if which == 'left' else g[:, k + 1:]
        return g[:, :k] if which == 'left' else g[:, k:]
    return f


def split_parts(g):
    """Split by full separator lines of one colour (rows and/or columns); else by exact halves. [parts], all one shape."""
    h, w = g.shape
    seps_r = [i for i in range(h) if len(set(g[i].tolist())) == 1 and (g[i] != bg_of(g)).any()]
    seps_c = [j for j in range(w) if len(set(g[:, j].tolist())) == 1 and (g[:, j] != bg_of(g)).any()]
    def cuts(n, seps):
        out, start = [], 0
        for s in seps + [n]:
            if s > start:
                out.append((start, s))
            start = s + 1
        return out
    if seps_r or seps_c:
        rs, cs = cuts(h, seps_r), cuts(w, seps_c)
        parts = [g[a:b, c:d] for a, b in rs for c, d in cs]
        if len(parts) >= 2 and len({p.shape for p in parts}) == 1:
            return parts
    if w % 2 == 0 and w >= 2:
        return [g[:, :w // 2], g[:, w // 2:]]
    if h % 2 == 0 and h >= 2:
        return [g[:h // 2], g[h // 2:]]
    return None


def make_combine(kind):
    def f(g):
        parts = split_parts(g)
        if not parts or len(parts) < 2:
            return None
        masks = [p != bg_of(g) if (p != bg_of(g)).any() else p != 0 for p in parts]
        if kind in ('and', 'or', 'xor', 'nor', 'a_not_b', 'b_not_a'):
            if len(masks) != 2:
                return None
            a, b = masks
            m = {'and': a & b, 'or': a | b, 'xor': a ^ b, 'nor': ~(a | b), 'a_not_b': a & ~b, 'b_not_a': b & ~a}[kind]
            return m.astype(g.dtype)   # 0/1, the final colour mapping names the colours
        if kind == 'overlay':          # later parts painted over earlier ones (non-background cells)
            o = parts[0].copy()
            b = bg_of(g)
            for p in parts[1:]:
                o[p != b] = p[p != b]
            return o
        if kind == 'overlay_rev':
            o = parts[-1].copy()
            b = bg_of(g)
            for p in parts[-2::-1]:
                o[p != b] = p[p != b]
            return o
        if kind == 'odd_one':          # the part that differs from all the others
            keys = [p.tobytes() for p in parts]
            cnt = Counter(keys)
            idx = [i for i, k in enumerate(keys) if cnt[k] == 1]
            return parts[idx[0]] if len(idx) == 1 and len(parts) >= 3 else None
        if kind in ('most_fg', 'least_fg'):
            vals = [int(m.sum()) for m in masks]
            t = max(vals) if kind == 'most_fg' else min(vals)
            idx = [i for i, v in enumerate(vals) if v == t]
            return parts[idx[0]] if len(idx) == 1 else None
        if kind in ('most_colors', 'least_colors'):
            vals = [len(np.unique(p)) for p in parts]
            t = max(vals) if kind == 'most_colors' else min(vals)
            idx = [i for i, v in enumerate(vals) if v == t]
            return parts[idx[0]] if len(idx) == 1 else None
        return None
    return f


def make_gravity(d):
    def f(g):
        b = bg_of(g)
        o = np.full_like(g, b)
        t = np.rot90(g, d)
        to = np.rot90(o, d).copy()
        for j in range(t.shape[1]):
            col = t[:, j]
            v = col[col != b]
            if len(v):
                to[t.shape[0] - len(v):, j] = v
        r = np.rot90(to, -d)
        return None if np.array_equal(r, g) else r
    return f


def make_symmetrize(kind):
    def f(g):
        b = bg_of(g)
        o = g.copy()
        mirrors = {'lr': [g[:, ::-1]], 'ud': [g[::-1]], 'both': [g[:, ::-1], g[::-1], g[::-1, ::-1]],
                   'diag': [g.T] if g.shape[0] == g.shape[1] else [],
                   'rot4': [np.rot90(g, k) for k in (1, 2, 3)] if g.shape[0] == g.shape[1] else []}[kind]
        if not mirrors:
            return None
        for m in mirrors:
            fill = (o == b) & (m != b)
            o[fill] = m[fill]
        return None if np.array_equal(o, g) else o
    return f


def make_fill_enclosed(c):
    def f(g):
        b = bg_of(g)
        holes = ndimage.binary_fill_holes(g != b) & (g == b)
        if not holes.any():
            return None
        o = g.copy()
        o[holes] = c
        return o
    return f


def op_outline(g):
    b = bg_of(g)
    fg = g != b
    inner = ndimage.binary_erosion(fg, structure=S4, border_value=0)
    if not inner.any():
        return None
    o = g.copy()
    o[inner] = b
    return o


def op_fill_bbox(g):
    """Each object's bounding box filled with its colour."""
    b = bg_of(g)
    o = g.copy()
    changed = False
    for m in comps(g, b, True, True):
        ys, xs = np.nonzero(m)
        box = o[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        sel = box == b
        if sel.any():
            box[sel] = g[ys[0], xs[0]]
            changed = True
    return o if changed else None


def op_majority_color(g):
    b = bg_of(g)
    v, n = np.unique(g[g != b], return_counts=True)
    if not len(v):
        return None
    return np.array([[v[np.argmax(n)]]], dtype=g.dtype)


def op_minority_color(g):
    v, n = np.unique(g, return_counts=True)
    if len(v) < 2 or (n == n.min()).sum() > 1:
        return None
    return np.array([[v[np.argmin(n)]]], dtype=g.dtype)


def op_count_objects_row(g):
    b = bg_of(g)
    n = len(comps(g, b, True, False))
    if not 0 < n <= 30:
        return None
    return np.full((1, n), 1, dtype=g.dtype)


def op_largest_rect(g):
    """The largest single-colour (non-background) solid rectangle's interior region of the grid, cropped."""
    b = bg_of(g)
    best = None
    for c in np.unique(g):
        if c == b:
            continue
        lab, n = ndimage.label(g == c, structure=S4)
        for i in range(1, n + 1):
            m = lab == i
            ys, xs = np.nonzero(m)
            area = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
            if area >= 4 and best is None or (best and area > best[0]):
                best = (area, ys.min(), ys.max(), xs.min(), xs.max())
    if not best:
        return None
    _, y0, y1, x0, x1 = best
    if y1 - y0 < 2 or x1 - x0 < 2:
        return None
    return g[y0 + 1:y1, x0 + 1:x1]


def op_inside_frame(g):
    """Contents of the largest one-colour rectangular frame."""
    b = bg_of(g)
    best = None
    for c in np.unique(g):
        if c == b:
            continue
        lab, n = ndimage.label(g == c, structure=S4)
        for i in range(1, n + 1):
            m = lab == i
            ys, xs = np.nonzero(m)
            y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
            if y1 - y0 < 2 or x1 - x0 < 2:
                continue
            edge = np.zeros_like(m)
            edge[y0, x0:x1 + 1] = edge[y1, x0:x1 + 1] = edge[y0:y1 + 1, x0] = edge[y0:y1 + 1, x1] = True
            if m[edge].all():
                area = (y1 - y0) * (x1 - x0)
                if best is None or area > best[0]:
                    best = (area, y0, y1, x0, x1)
    if not best:
        return None
    _, y0, y1, x0, x1 = best
    return g[y0 + 1:y1, x0 + 1:x1]


def make_shoot(d):
    """Every single non-background cell extends a line to the border in direction d (until it meets another colour)."""
    dy, dx = d
    def f(g):
        b = bg_of(g)
        o = g.copy()
        ys, xs = np.nonzero(g != b)
        if len(ys) > 40 or not len(ys):
            return None
        for y, x in zip(ys, xs):
            c = g[y, x]
            yy, xx = y + dy, x + dx
            while 0 <= yy < g.shape[0] and 0 <= xx < g.shape[1] and g[yy, xx] == b:
                o[yy, xx] = c
                yy += dy
                xx += dx
        return None if np.array_equal(o, g) else o
    return f


def op_connect_same(g):
    """Draw straight lines between pairs of same-coloured cells on one row or column."""
    b = bg_of(g)
    o = g.copy()
    changed = False
    for c in np.unique(g):
        if c == b:
            continue
        ys, xs = np.nonzero(g == c)
        if len(ys) > 30:
            continue
        pts = list(zip(ys, xs))
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                (y1, x1), (y2, x2) = pts[i], pts[j]
                if y1 == y2:
                    seg = o[y1, min(x1, x2) + 1:max(x1, x2)]
                    m = seg == b
                    if m.any():
                        seg[m] = c
                        changed = True
                elif x1 == x2:
                    seg = o[min(y1, y2) + 1:max(y1, y2), x1]
                    m = seg == b
                    if m.any():
                        seg[m] = c
                        changed = True
    return o if changed else None


def op_border(g):
    if g.shape[0] < 3 or g.shape[1] < 3:
        return None
    o = g.copy()
    o[0, :] = o[-1, :] = o[:, 0] = o[:, -1] = 10   # colour 10 = "new colour", named by the final colour mapping
    return o


def op_recolor_by_size(g):
    """Objects recoloured by their size rank (largest = 1, ...); the colour mapping names the colours."""
    b = bg_of(g)
    objs = comps(g, b, False, False)
    if not 2 <= len(objs) <= 9:
        return None
    sizes = sorted({int(m.sum()) for m in objs}, reverse=True)
    o = np.full_like(g, b)
    for m in objs:
        o[m] = 11 + sizes.index(int(m.sum()))
    return o


def op_recolor_by_shape_count(g):
    """Objects coloured by how many objects share their shape (unique shape vs repeated)."""
    b = bg_of(g)
    objs = comps(g, b, True, False)
    if not 2 <= len(objs) <= 30:
        return None
    keys = [_shape_key(m) for m in objs]
    cnt = Counter(keys)
    o = np.full_like(g, b)
    for m, k in zip(objs, keys):
        o[m] = 11 if cnt[k] == 1 else 12
    return o


def op_holes_count_color(g):
    """Objects coloured by their number of enclosed holes."""
    b = bg_of(g)
    objs = comps(g, b, False, False)
    if not 1 <= len(objs) <= 30:
        return None
    o = np.full_like(g, b)
    for m in objs:
        filled = ndimage.binary_fill_holes(m)
        _, nh = ndimage.label(filled & ~m, structure=S4)
        o[m] = 11 + min(nh, 4)
    return o


def op_count_cells_row(g):
    b = bg_of(g)
    fg = g != b
    n = int(fg.sum())
    v, c = np.unique(g[fg], return_counts=True)
    if not 0 < n <= 30 or len(v) != 1:
        return None
    return np.full((1, n), v[0], dtype=g.dtype)


def _period_fill(g, hole_c):
    """Fill cells of colour hole_c from the smallest 2-D period consistent with every other cell."""
    h, w = g.shape
    known = g != hole_c
    if known.all() or not known.any():
        return None
    for py in range(1, h + 1):
        for px in range(1, w + 1):
            if py * px >= h * w:
                continue
            tile = np.full((py, px), -1, dtype=np.int32)
            ok = True
            for y in range(h):
                for x in range(w):
                    if known[y, x]:
                        t = tile[y % py, x % px]
                        if t == -1:
                            tile[y % py, x % px] = g[y, x]
                        elif t != g[y, x]:
                            ok = False
                            break
                if not ok:
                    break
            if ok and (tile >= 0).all():
                return np.tile(tile, (h // py + 1, w // px + 1))[:h, :w].astype(g.dtype)
    return None


def _diag_period_fill(g, hole_c):
    """Fill hole_c cells when the colour depends only on (y + x) mod p or (y - x) mod p."""
    h, w = g.shape
    known = g != hole_c
    if known.all() or not known.any():
        return None
    yy, xx = np.mgrid[0:h, 0:w]
    for sign in (1, -1):
        for p in range(2, max(h, w) + 1):
            key = (yy + sign * xx) % p
            tab = {}
            ok = True
            for k, v in zip(key[known].tolist(), g[known].tolist()):
                if tab.setdefault(k, v) != v:
                    ok = False
                    break
            if ok and len(tab) == p:
                return np.vectorize(tab.get)(key).astype(g.dtype)
    return None


def make_period(crop_hole):
    def f(g):
        for hole_c in ([0] + [c for c in np.unique(g).tolist() if c != 0]):
            if not (g == hole_c).any():
                continue
            full = _period_fill(g, hole_c)
            if full is None:
                full = _diag_period_fill(g, hole_c)
            if full is None:
                continue
            if crop_hole:
                ys, xs = np.nonzero(g == hole_c)
                return full[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            return full
        return None
    return f


def make_fractal(inverse):
    """The grid stamped into every (non-)background cell of itself."""
    def f(g):
        h, w = g.shape
        if h * h > 30 or w * w > 30:
            return None
        b = bg_of(g)
        m = (g == b) if inverse else (g != b)
        out = np.full((h * h, w * w), b, dtype=g.dtype)
        for y in range(h):
            for x in range(w):
                if m[y, x]:
                    out[y * h:(y + 1) * h, x * w:(x + 1) * w] = g
        return out
    return f


def op_up_by_colours(g):
    k = len(set(np.unique(g).tolist()) - {bg_of(g)})
    if not 2 <= k <= 5 or g.shape[0] * k > 30 or g.shape[1] * k > 30:
        return None
    return np.kron(g, np.ones((k, k), dtype=g.dtype))


def op_pad1(g):
    if g.shape[0] + 2 > 30 or g.shape[1] + 2 > 30:
        return None
    o = np.full((g.shape[0] + 2, g.shape[1] + 2), 10, dtype=g.dtype)
    o[1:-1, 1:-1] = g
    return o


GEOM = [('rot90', lambda g: np.rot90(g, -1)), ('rot180', lambda g: np.rot90(g, 2)), ('rot270', lambda g: np.rot90(g, 1)),
        ('flip_lr', lambda g: g[:, ::-1]), ('flip_ud', lambda g: g[::-1]), ('transpose', lambda g: g.T),
        ('anti_t', lambda g: np.rot90(g, 2).T)]


def build_ops():
    ops = list(GEOM)
    ops += [('crop_nonbg', op_crop_nonbg), ('crop_non0', op_crop_non0), ('remove_bg_lines', op_remove_bg_lines),
            ('compress', op_compress_dups), ('downscale', op_downscale), ('keep_major', op_keep_major_fg),
            ('keep_minor', op_keep_minor_fg), ('outline', op_outline), ('fill_bbox', op_fill_bbox),
            ('majority', op_majority_color), ('minority', op_minority_color), ('count_row', op_count_objects_row),
            ('largest_rect', op_largest_rect), ('inside_frame', op_inside_frame), ('connect', op_connect_same),
            ('border', op_border), ('size_rank', op_recolor_by_size), ('shape_uniq', op_recolor_by_shape_count),
            ('holes', op_holes_count_color), ('count_cells_row', op_count_cells_row),
            ('period_fill', make_period(False)), ('period_hole', make_period(True)),
            ('fractal', make_fractal(False)), ('fractal_inv', make_fractal(True)), ('up_by_colours', op_up_by_colours),
            ('pad1', op_pad1)]
    for how in SELECTORS:
        for diag in (False, True):
            for by_color in (True, False):
                tag = f'{how}{"8" if diag else "4"}{"c" if by_color else "m"}'
                ops.append((f'crop_obj:{tag}', make_crop_obj(how, diag, by_color, True)))
                ops.append((f'crop_obj_only:{tag}', make_crop_obj(how, diag, by_color, False)))
                ops.append((f'keep_obj:{tag}', make_keep_obj(how, diag, by_color)))
                ops.append((f'remove_obj:{tag}', make_remove_obj(how, diag, by_color)))
    for c in range(10):
        ops.append((f'filter:{c}', make_filter_color(c)))
        ops.append((f'erase:{c}', make_erase_color(c)))
        ops.append((f'fill_enclosed:{c}', make_fill_enclosed(c)))
    for k in (2, 3, 4):
        ops.append((f'up{k}', make_scale_up(k)))
    for ry, rx in ((1, 2), (2, 1), (2, 2), (3, 3), (1, 3), (3, 1)):
        for mode in ('plain', 'mirror'):
            ops.append((f'tile{ry}x{rx}{mode}', make_tile(ry, rx, mode)))
    ops.append(('tile2x2rot', make_tile(2, 2, 'rot')))
    for w in ('top', 'bottom', 'left', 'right'):
        ops.append((f'half:{w}', make_half(w)))
    for kind in ('and', 'or', 'xor', 'nor', 'a_not_b', 'b_not_a', 'overlay', 'overlay_rev', 'odd_one', 'most_fg',
                 'least_fg', 'most_colors', 'least_colors'):
        ops.append((f'combine:{kind}', make_combine(kind)))
    for d in range(4):
        ops.append((f'gravity{d}', make_gravity(d)))
    for kind in ('lr', 'ud', 'both', 'diag', 'rot4'):
        ops.append((f'sym:{kind}', make_symmetrize(kind)))
    for d in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        ops.append((f'shoot{d}', make_shoot(d)))
    return ops


OPS = build_ops()


# ---------------------------------------------------------------- matching
def colour_map(results, outputs):
    """A consistent colour mapping m with m(result) == output for every pair, or None. Identity where unseen."""
    m = {}
    for r, o in zip(results, outputs):
        if r.shape != o.shape:
            return None
        for a, b in zip(r.ravel().tolist(), o.ravel().tolist()):
            if m.setdefault(a, b) != b:
                return None
    return m


def _key(gs):
    return tuple((g.shape, g.tobytes()) for g in gs)


KEYS = {
    'mask': lambda g: (g.shape, (g != bg_of(g)).tobytes()),
    'colours': lambda g: tuple(sorted(set(np.unique(g).tolist()) - {bg_of(g)})),
    'major': lambda g: op_majority_color(g).tobytes() if op_majority_color(g) is not None else None,
    'n_objects': lambda g: len(comps(g, bg_of(g), True, False)),
    'n_cells': lambda g: int((g != bg_of(g)).sum()),
}


def lookup(xs, ys, ts):
    """Output = a fixed grid chosen by one key of the input (its shape mask, its colours, ...), learned from the
    demonstrations; the test's key must have been seen."""
    out = []
    for name, key in KEYS.items():
        try:
            table = {}
            ok = True
            for x, y in zip(xs, ys):
                k = key(x)
                if k is None or table.setdefault(k, y.tobytes() + bytes(y.shape)) != y.tobytes() + bytes(y.shape):
                    ok = False
                    break
            if not ok or len(table) == len(xs) and len(xs) > 2 and len({y.tobytes() for y in ys}) == len(xs) and name != 'colours':
                pass
            if not ok or len(table) < 2:
                continue
            # the table must generalise: some key seen twice with the same output (an exact shape mask is enough alone)
            if name != 'mask' and len(table) >= len(xs):
                continue
            preds = []
            for t in ts:
                k = key(t)
                hit = [y for x, y in zip(xs, ys) if key(x) == k]
                if not hit:
                    preds = None
                    break
                preds.append(hit[0].astype(int).tolist())
            if preds:
                out.append((1.5 if name == 'mask' else 2.5, f'lookup:{name}', preds))
        except Exception:
            continue
    return out


def parts_map(xs, ys, ts):
    """Each part of the input (split by separator lines or equal blocks) becomes one block of the output, chosen by the
    part's shape mask; the output blocks are laid out like the parts (or transposed, or in one line)."""
    def blocks(y, n, layout):
        R, C = layout
        h, w = y.shape
        if h % R or w % C:
            return None
        bh, bw = h // R, w // C
        return [y[i * bh:(i + 1) * bh, j * bw:(j + 1) * bw] for i in range(R) for j in range(C)]
    def layouts(x):
        parts = split_parts(x)
        if not parts or len(parts) < 2:
            return None, None
        h, w = x.shape
        ph, pw = parts[0].shape
        R = max(1, round((h + 1) / (ph + 1))) if h > ph else 1
        C = len(parts) // R
        return parts, (R, C)
    for mode in ('same', 'T', 'row', 'col'):
        table = {}
        ok = True
        for x, y in zip(xs, ys):
            parts, (R, C) = layouts(x) if layouts(x)[0] is not None else (None, (0, 0))
            if parts is None or R * C != len(parts):
                ok = False
                break
            lay = {'same': (R, C), 'T': (C, R), 'row': (1, len(parts)), 'col': (len(parts), 1)}[mode]
            bl = blocks(y, len(parts), lay)
            if bl is None:
                ok = False
                break
            if mode == 'T':
                bl = [bl[j * R + i] for i in range(R) for j in range(C)] if False else bl
            for p, b in zip(parts, bl):
                k = (p != bg_of(x)).tobytes() + bytes(p.shape)
                v = b.tobytes() + bytes(b.shape)
                if table.setdefault(k, (v, b)) [0] != v:
                    ok = False
                    break
            if not ok:
                break
        if not ok or not table:
            continue
        preds = []
        for t in ts:
            parts, (R, C) = layouts(t) if layouts(t)[0] is not None else (None, (0, 0))
            if parts is None:
                preds = None
                break
            lay = {'same': (R, C), 'T': (C, R), 'row': (1, len(parts)), 'col': (len(parts), 1)}[mode]
            got = []
            for p in parts:
                k = (p != bg_of(t)).tobytes() + bytes(p.shape)
                if k not in table:
                    got = None
                    break
                got.append(table[k][1])
            if got is None:
                preds = None
                break
            rows = [np.hstack(got[i * lay[1]:(i + 1) * lay[1]]) for i in range(lay[0])]
            preds.append(np.vstack(rows).astype(int).tolist())
        if preds:
            out_ = [(1.5, f'parts_map:{mode}', preds)]
            return out_
    return []


def _parts_boxes(g):
    """Part rectangles (y0, y1, x0, x1) split by full one-colour separator lines, all the same size."""
    h, w = g.shape
    b = bg_of(g)
    seps_r = [i for i in range(h) if len(set(g[i].tolist())) == 1 and g[i, 0] != b]
    seps_c = [j for j in range(w) if len(set(g[:, j].tolist())) == 1 and g[0, j] != b]
    def cuts(n, seps):
        out, start = [], 0
        for s_ in seps + [n]:
            if s_ > start:
                out.append((start, s_))
            start = s_ + 1
        return out
    if not seps_r and not seps_c:
        return None
    boxes = [(a, b_, c, d) for a, b_ in cuts(h, seps_r) for c, d in cuts(w, seps_c)]
    if len(boxes) < 2 or len({(b_ - a, d - c) for a, b_, c, d in boxes}) != 1:
        return None
    return boxes


DIH = [lambda p: p, lambda p: np.rot90(p, -1), lambda p: np.rot90(p, 2), lambda p: np.rot90(p, 1),
       lambda p: p[:, ::-1], lambda p: p[::-1], lambda p: p.T, lambda p: np.rot90(p, 2).T]


def parts_dihedral(xs, ys, ts):
    """Output part i = transform T_i of the source part (the first part), T_i learned per position."""
    choice = None
    for x, y in zip(xs, ys):
        if x.shape != y.shape:
            return []
        boxes = _parts_boxes(x)
        if boxes is None:
            return []
        src = x[boxes[0][0]:boxes[0][1], boxes[0][2]:boxes[0][3]]
        if src.shape[0] != src.shape[1]:
            return []
        if not np.array_equal(y[boxes[0][0]:boxes[0][1], boxes[0][2]:boxes[0][3]], src):
            return []
        opts = []
        for a, b_, c, d in boxes:
            tgt = y[a:b_, c:d]
            opts.append({k for k, f in enumerate(DIH) if np.array_equal(f(src), tgt)})
        choice = opts if choice is None else ([o & c_ for o, c_ in zip(opts, choice)] if len(opts) == len(choice) else None)
        if choice is None or not all(choice):
            return []
    preds = []
    for t in ts:
        boxes = _parts_boxes(t)
        if boxes is None or len(boxes) != len(choice):
            return []
        o = t.copy()
        src = t[boxes[0][0]:boxes[0][1], boxes[0][2]:boxes[0][3]]
        for (a, b_, c, d), ks in zip(boxes, choice):
            o[a:b_, c:d] = DIH[min(ks)](src)
        preds.append(o.astype(int).tolist())
    return [(2.0, 'parts_dihedral', preds)]


def search(train_in, train_out, tests, seconds=4.0, max_depth=3, beam=400):
    """[(cost, program, [test predictions])] for programs that reproduce every demonstration."""
    xs = [np.asarray(g, dtype=np.int16) for g in train_in]
    ys = [np.asarray(g, dtype=np.int16) for g in train_out]
    ts = [np.asarray(g, dtype=np.int16) for g in tests]
    out_shapes = [y.shape for y in ys]
    started = time.monotonic()
    found = []
    for extra in (lookup, parts_map, parts_dihedral):
        try:
            found += extra(xs, ys, ts)
        except Exception:
            pass
    seen = {_key(xs)}
    level = [((), xs, ts)]
    best_depth = None

    def check(prog, rs, rt):
        m = colour_map(rs, ys)
        if m is None:
            return False
        if any(v >= 10 for v in m.values()):
            return False
        ident = all(a == b for a, b in m.items())
        preds = []
        for t in rt:
            if any(int(v) not in m and v >= 10 for v in np.unique(t)):
                return False
            if not ident and any(int(v) not in m for v in np.unique(t)):
                return False   # a colour never seen in the demonstrations: no rule for it
            p = np.vectorize(lambda v: m.get(int(v), int(v)))(t) if not ident else t
            if (p >= 10).any() or p.size == 0 or p.shape[0] > 30 or p.shape[1] > 30:
                return False
            preds.append(p.astype(int).tolist())
        cost = len(prog) + (0 if ident else 0.5)
        found.append((cost, ' > '.join(prog) + ('' if ident else ' > recolour'), preds))
        return True

    for depth in range(1, max_depth + 1):
        nxt = []
        for prog, rs, rt in level:
            for name, f in OPS:
                if time.monotonic() - started > seconds:
                    return sorted(found, key=lambda x: x[0])
                try:
                    nrs = []
                    for g in rs:
                        r = f(g)
                        if r is None or r.size == 0 or r.shape[0] > 30 or r.shape[1] > 30:
                            raise ValueError
                        nrs.append(np.ascontiguousarray(r))
                    k = _key(nrs)
                    if k in seen:
                        continue
                    nrt = []
                    for g in rt:
                        r = f(g)
                        if r is None or r.size == 0:
                            raise ValueError
                        nrt.append(np.ascontiguousarray(r))
                except Exception:
                    continue
                seen.add(k)
                np_ = prog + (name,)
                if check(np_, nrs, nrt) and best_depth is None:
                    best_depth = depth
                nxt.append((np_, nrs, nrt))
        if depth == 1 and best_depth is None and time.monotonic() - started < seconds * 0.6:
            # one reshaping step, then per-cell rules: programs whose grids already have the output sizes
            from . import arc_cellrules
            tried = 0
            for np_, nrs, nrt in nxt:
                if tried >= 12 or time.monotonic() - started > seconds * 0.6:
                    break
                if not all(r.shape == y.shape for r, y in zip(nrs, ys)) or all(np.array_equal(r, x) for r, x in zip(nrs, xs)):
                    continue
                if np_[0] in dict(GEOM) or all(np.array_equal(r, y) for r, y in zip(nrs, ys)):
                    continue
                tried += 1
                try:
                    res = arc_cellrules.solve(list(zip(nrs, ys)), nrt, seconds=0.3)
                except Exception:
                    res = []
                for cost, name, preds in res:
                    found.append((cost + 1.0, ' > '.join(np_) + ' > ' + name, preds))
        if depth == 1 and best_depth is None and time.monotonic() - started < seconds * 0.7 and                 all(x.shape == y.shape for x, y in zip(xs, ys)):
            # every same-size one-step result becomes an extra feature layer for one cell-rule tree
            from . import arc_cellrules
            lay_tr, lay_te, lay_names = [[] for _ in xs], [[] for _ in ts], []
            for np_, nrs, nrt in nxt:
                if len(lay_names) >= 40:
                    break
                if np_[0] in dict(GEOM) and np_[0] not in ('flip_lr', 'flip_ud', 'rot180'):
                    continue
                if not all(r.shape == x.shape for r, x in zip(nrs, xs)) or not all(r.shape == t.shape for r, t in zip(nrt, ts)):
                    continue
                if any((r >= 10).any() for r in nrs) and np_[0] not in ('size_rank', 'shape_uniq', 'holes', 'border'):
                    continue
                for i, r in enumerate(nrs):
                    lay_tr[i].append(r)
                for i, r in enumerate(nrt):
                    lay_te[i].append(r)
                lay_names.append(np_[0])
            if lay_names:
                try:
                    res = arc_cellrules.solve(list(zip(xs, ys)), ts, layers=lay_tr, layer_names=lay_names, test_layers=lay_te, seconds=1.0)
                except Exception:
                    res = []
                for cost, name, preds in res:
                    found.append((cost + 1.5, 'layers > ' + name, preds))
        if best_depth is not None or not nxt:
            break
        # beam: keep the most promising programs for the next level (right shapes first, then closeness)
        def score(item):
            _, rs, _ = item
            s = 0.0
            for r, y in zip(rs, ys):
                if r.shape == y.shape:
                    s += 2 + float((r == y).mean())
                else:
                    s -= abs(r.shape[0] - y.shape[0]) / 30 + abs(r.shape[1] - y.shape[1]) / 30
                    s += 0.5 * (len(set(np.unique(r).tolist()) & set(np.unique(y).tolist())) / max(1, len(np.unique(y))))
            return -s
        nxt.sort(key=score)
        level = nxt[:beam]
    return sorted(found, key=lambda x: x[0])
