"""ARC-style grid tasks: many small checked solvers, ranked by description length, two attempts (non-neural).

Ideas taken (not code) from the Looped mdlARC write-up (mvakde.github.io/blog/looped-mdlarc), without its network:
- minimum description length: among hypotheses that reproduce every demonstration exactly, the shortest wins;
- augment and vote: the task is also solved under the 8 grid symmetries, each answer mapped back, equal answers pooled;
- two attempts: the best two different answers are returned instead of refusing when hypotheses disagree.

Every candidate reproduces every demonstration exactly before it may predict. Nothing here knows task ids or answers.
"""
from collections import Counter, defaultdict
import json
import os
import time

from . import grid_programs as gp
from .grid_induction import Unsupported, components, crop, grid, rotate

G = tuple  # a grid is a tuple of row tuples


# ---------------------------------------------------------------- small helpers
def T(g):
    return tuple(zip(*g))


def flip_h(g):
    return tuple(r[::-1] for r in g)


def dihedral(g, k):
    """k in 0..7: rotations, then reflected rotations."""
    if k >= 4:
        g = flip_h(g)
    for _ in range(k % 4):
        g = rotate(g)
    return g


def undihedral(g, k):
    for _ in range((4 - k % 4) % 4):
        g = rotate(g)
    return flip_h(g) if k >= 4 else g


def shape(g):
    return len(g), len(g[0])


def bg_of(g):
    return Counter(v for r in g for v in r).most_common(1)[0][0]


def colors(g):
    return Counter(v for r in g for v in r)


def blank(h, w, c=0):
    return tuple(tuple(c for _ in range(w)) for _ in range(h))


def ok_grid(g):
    return isinstance(g, tuple) and 1 <= len(g) <= 30 and 1 <= len(g[0]) <= 30 and all(len(r) == len(g[0]) for r in g)


def objects(g, bg, diagonal=False, by_color=True):
    h, w = shape(g)
    seen, out = set(), []
    for y in range(h):
        for x in range(w):
            if g[y][x] == bg or (y, x) in seen:
                continue
            c = g[y][x]
            todo, cells = [(y, x)], []
            seen.add((y, x))
            while todo:
                a, b = todo.pop()
                cells.append((a, b))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if (dy or dx) and (diagonal or not (dy and dx)):
                            na, nb = a + dy, b + dx
                            if 0 <= na < h and 0 <= nb < w and (na, nb) not in seen and g[na][nb] != bg and (not by_color or g[na][nb] == c):
                                seen.add((na, nb))
                                todo.append((na, nb))
            out.append(cells)
    return out


def bbox(cells):
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return min(ys), min(xs), max(ys), max(xs)


def sub(g, y0, x0, y1, x1):
    return tuple(tuple(g[y][x0:x1 + 1]) for y in range(y0, y1 + 1))


# ---------------------------------------------------------------- solvers
# Each solver: fit(pairs) -> list of (cost, name, predict) where predict(query) -> grid. A solver returns nothing
# unless its hypothesis reproduces every pair exactly. Costs are description lengths in rough "steps".

def s_program_search(pairs, budget):
    """CAEL's existing compositional search (grid_programs), keeping every fit instead of refusing on ties."""
    inputs = tuple(a for a, _ in pairs)
    outputs = tuple(b for _, b in pairs)
    from collections import deque
    ops = gp.grammar()
    todo = deque([(inputs, [])])
    seen = {inputs}
    found = []
    best = None
    started = time.monotonic()
    while todo and time.monotonic() - started < budget and len(seen) < 6000:
        values, program = todo.popleft()
        depth = len(program)
        if best is not None and depth > best + 1:
            break
        m = gp.recolor(values, outputs, values[0])
        if m:
            cost = depth + m[2]
            best = cost if best is None else min(best, cost)
            found.append((cost + 0.5, 'program:' + json.dumps(program), program, m[1]['mapping']))
        if depth >= 3:
            continue
        for op in ops:
            try:
                new = tuple(grid([list(r) for r in gp.apply(g, op)]) for g in values)
            except Exception:
                continue
            if new not in seen:
                seen.add(new)
                todo.append((new, program + [op]))
    out = []
    for cost, name, program, mapping in found:
        def predict(q, program=program, mapping=mapping):
            v = q
            for op in program:
                v = grid([list(r) for r in gp.apply(v, op)])
            if any(c not in mapping for r in v for c in r) and any(a != b for a, b in mapping.items()):
                raise Unsupported('unseen colour')
            return tuple(tuple(mapping.get(c, c) for c in r) for r in v)
        out.append((cost, name, predict))
    return out


def s_split_combine(pairs, budget):
    """Input = k equal parts (split by a separator line or exactly), output = a cell-wise logic combination of them."""
    out = []
    for direction in ('v', 'h'):
        for k in (2, 3):
            def parts_of(g, direction=direction, k=k):
                gg = g if direction == 'h' else T(g)
                h, w = shape(gg)
                if (h - (k - 1)) % k == 0:
                    size = (h - (k - 1)) // k
                    seps = [gg[(i + 1) * size + i] for i in range(k - 1)]
                    if all(len(set(s)) == 1 for s in seps):
                        ps = [gg[i * (size + 1):i * (size + 1) + size] for i in range(k)]
                        return [p if direction == 'h' else T(p) for p in ps]
                if h % k == 0:
                    size = h // k
                    ps = [gg[i * size:(i + 1) * size] for i in range(k)]
                    return [p if direction == 'h' else T(p) for p in ps]
                return None
            try:
                split = [parts_of(a) for a, _ in pairs]
            except Exception:
                continue
            if any(s is None or shape(s[0]) != shape(b) for s, (_, b) in zip(split, pairs)):
                continue
            bgs = [bg_of(a) if bg_of(a) in (0,) else 0 for a, _ in pairs]
            ops = {'and': all, 'or': any, 'xor': lambda v: sum(v) % 2 == 1, 'nor': lambda v: not any(v), 'one': lambda v: sum(v) == 1,
                   'first-only': lambda v: v[0] and not any(v[1:])}
            for name, f in ops.items():
                fg = set()
                good = True
                for s, (_, b) in zip(split, pairs):
                    for y in range(len(b)):
                        for x in range(len(b[0])):
                            hit = f([p[y][x] != 0 for p in s])
                            if hit:
                                fg.add(b[y][x])
                            elif b[y][x] != 0:
                                good = False
                    if not good:
                        break
                if not good or len(fg) != 1 or 0 in fg:
                    continue
                c = fg.pop()

                def predict(q, parts_of=parts_of, f=f, c=c):
                    s = parts_of(q)
                    if s is None:
                        raise Unsupported('no split')
                    return tuple(tuple(c if f([p[y][x] != 0 for p in s]) else 0 for x in range(len(s[0][0]))) for y in range(len(s[0])))
                if all(predict(a) == b for a, b in pairs):
                    out.append((2.0, f'split-{direction}{k}-{name}', predict))
            # overlay: parts stacked, later non-zero cells win (or earlier)
            for order in ('first', 'last'):
                def predict(q, parts_of=parts_of, order=order):
                    s = parts_of(q)
                    if s is None:
                        raise Unsupported('no split')
                    seq = s if order == 'first' else s[::-1]
                    h, w = shape(s[0])
                    return tuple(tuple(next((p[y][x] for p in seq if p[y][x] != 0), 0) for x in range(w)) for y in range(h))
                try:
                    if all(predict(a) == b for a, b in pairs):
                        out.append((2.5, f'split-{direction}{k}-overlay-{order}', predict))
                except Exception:
                    pass
    return out


def s_tiling(pairs, budget):
    """Output = an (a x b) tiling of the input, each tile one of the 8 symmetries (learned per tile position)."""
    out = []
    a0, b0 = pairs[0]
    h, w = shape(a0)
    H, W = shape(b0)
    if H % h or W % w:
        return out
    ra, rb = H // h, W // w
    if ra * rb == 1 or ra > 4 or rb > 4:
        return out
    if any(shape(b) != (shape(a)[0] * ra, shape(a)[1] * rb) for a, b in pairs):
        return out
    choice = {}
    for i in range(ra):
        for j in range(rb):
            options = None
            for a, b in pairs:
                hh, ww = shape(a)
                tile = sub(b, i * hh, j * ww, (i + 1) * hh - 1, (j + 1) * ww - 1)
                fits = {k for k in range(8) if dihedral(a, k) == tile and shape(dihedral(a, k)) == shape(tile)}
                options = fits if options is None else options & fits
            if not options:
                return out
            choice[(i, j)] = min(options)

    def predict(q):
        hh, ww = shape(q)
        rows = []
        for i in range(ra):
            tiles = [dihedral(q, choice[(i, j)]) for j in range(rb)]
            for y in range(hh):
                rows.append(tuple(v for t in tiles for v in t[y]))
        return tuple(rows)
    out.append((1.5 + 0.1 * len(set(choice.values())), 'tile', predict))
    return out


def s_self_tile(pairs, budget):
    """Output (h*h, w*w): block (i, j) is the input where input[i][j] is foreground (or its inverse)."""
    out = []
    for mode in ('copy', 'inverse'):
        def predict(q, mode=mode):
            h, w = shape(q)
            if h * h > 30 or w * w > 30:
                raise Unsupported('too big')
            bg = 0
            rows = []
            for i in range(h):
                for y in range(h):
                    row = []
                    for j in range(w):
                        on = q[i][j] != bg
                        for x in range(w):
                            if mode == 'copy':
                                row.append(q[y][x] if on else bg)
                            else:
                                row.append(q[y][x] if not on else bg)
                    rows.append(tuple(row))
            return tuple(rows)
        try:
            if all(predict(a) == b for a, b in pairs):
                out.append((1.5, 'self-tile-' + mode, predict))
        except Exception:
            pass
    return out


SELECTORS = ['largest', 'smallest', 'tallest', 'widest', 'most-colours', 'unique-colour', 'rarest-colour', 'commonest-colour',
             'unique-shape', 'top-left', 'bottom-right', 'densest', 'sparsest', 'symmetric', 'asymmetric', 'touches-single', 'has-hole']


def _obj_grid(g, o, b, bg):
    cells = set(o)
    return tuple(tuple(g[y][x] if (y, x) in cells else bg for x in range(b[1], b[3] + 1)) for y in range(b[0], b[2] + 1))


def _symmetric(m):
    return m == tuple(tuple(reversed(r)) for r in m) or m == tuple(reversed(m))


def select(g, kind, diagonal, by_color):
    bg = bg_of(g)
    objs = objects(g, bg, diagonal=diagonal, by_color=by_color)
    if not objs or len(objs) > 60:
        raise Unsupported('no objects')
    boxes = [bbox(o) for o in objs]
    if kind == 'largest':
        key = [len(o) for o in objs]; pick = max(key)
    elif kind == 'smallest':
        key = [len(o) for o in objs]; pick = min(key)
    elif kind == 'tallest':
        key = [b[2] - b[0] for b in boxes]; pick = max(key)
    elif kind == 'widest':
        key = [b[3] - b[1] for b in boxes]; pick = max(key)
    elif kind == 'most-colours':
        key = [len({g[y][x] for y, x in o}) for o in objs]; pick = max(key)
    elif kind in ('unique-colour', 'rarest-colour', 'commonest-colour'):
        col = [g[o[0][0]][o[0][1]] for o in objs]
        cnt = Counter(col)
        if kind == 'unique-colour':
            key = [cnt[c] == 1 for c in col]; pick = True
        else:
            total = colors(g)
            key = [total[c] for c in col]; pick = min(key) if kind == 'rarest-colour' else max(key)
    elif kind == 'unique-shape':
        norm = [frozenset((y - b[0], x - b[1]) for y, x in o) for o, b in zip(objs, boxes)]
        cnt = Counter(norm)
        key = [cnt[n] == 1 for n in norm]; pick = True
    elif kind == 'top-left':
        key = [(b[0], b[1]) for b in boxes]; pick = min(key)
    elif kind == 'bottom-right':
        key = [(b[2], b[3]) for b in boxes]; pick = max(key)
    elif kind in ('densest', 'sparsest'):
        key = [len(o) / ((b[2] - b[0] + 1) * (b[3] - b[1] + 1)) for o, b in zip(objs, boxes)]
        pick = max(key) if kind == 'densest' else min(key)
    elif kind in ('symmetric', 'asymmetric'):
        key = [_symmetric(_obj_grid(g, o, b, bg)) for o, b in zip(objs, boxes)]
        pick = kind == 'symmetric'
    elif kind == 'touches-single':
        singles = {o[0] for o in objs if len(o) == 1}
        key = [len(o) > 1 and any((y + dy, x + dx) in singles for y, x in o for dy in (-1, 0, 1) for dx in (-1, 0, 1)) for o in objs]
        pick = True
    elif kind == 'has-hole':
        def holed(o, b):
            cells = set(o)
            inside = [(y, x) for y in range(b[0] + 1, b[2]) for x in range(b[1] + 1, b[3]) if (y, x) not in cells]
            return bool(inside)
        key = [holed(o, b) for o, b in zip(objs, boxes)]
        pick = True
    else:
        raise Unsupported(kind)
    chosen = [i for i, k in enumerate(key) if k == pick]
    if len(chosen) != 1:
        raise Unsupported('tie')
    return objs[chosen[0]], boxes[chosen[0]], bg


def s_crop_object(pairs, budget):
    """Output = the bounding box of one selected object (as drawn in the input, or only its own cells), then a symmetry/recolour."""
    out = []
    if all(shape(b)[0] * shape(b)[1] >= shape(a)[0] * shape(a)[1] for a, b in pairs):
        return out
    for kind in SELECTORS:
        for diagonal in (False, True):
            for by_color in (True, False):
                for alone in (False, True):
                    def predict(q, kind=kind, diagonal=diagonal, by_color=by_color, alone=alone):
                        o, (y0, x0, y1, x1), bg = select(q, kind, diagonal, by_color)
                        box = sub(q, y0, x0, y1, x1)
                        if alone:
                            keep = set(o)
                            box = tuple(tuple(q[y][x] if (y, x) in keep else bg for x in range(x0, x1 + 1)) for y in range(y0, y1 + 1))
                        return box
                    try:
                        cand = [predict(a) for a, _ in pairs]
                    except Exception:
                        continue
                    for k in range(8):
                        moved = [dihedral(c, k) for c in cand]
                        if all(m == b for m, (_, b) in zip(moved, pairs)):
                            out.append((2.0 + 0.5 * (k > 0) + 0.25 * alone + 0.25 * diagonal + 0.25 * (not by_color), f'crop-{kind}-{k}',
                                        lambda q, p=predict, k=k: dihedral(p(q), k)))
                            break
                    else:
                        m = gp.recolor(tuple(cand), tuple(b for _, b in pairs), cand[0])
                        if m and m[2]:
                            mapping = m[1]['mapping']
                            out.append((3.0, f'crop-{kind}-recolour', lambda q, p=predict, mp=mapping: tuple(tuple(mp.get(v, v) for v in r) for r in p(q))))
                if len(out) > 40:
                    return out
    return out


PROPS = {
    'size': lambda o, g, bg: len(o),
    'size-rank': None,  # filled in per grid
    'is-largest': None,
    'is-smallest': None,
    'touches-border': lambda o, g, bg: any(y in (0, len(g) - 1) or x in (0, len(g[0]) - 1) for y, x in o),
    'has-hole': None,
    'height': lambda o, g, bg: bbox(o)[2] - bbox(o)[0] + 1,
    'width': lambda o, g, bg: bbox(o)[3] - bbox(o)[1] + 1,
    'is-rect': lambda o, g, bg: len(o) == (bbox(o)[2] - bbox(o)[0] + 1) * (bbox(o)[3] - bbox(o)[1] + 1),
    'shape': lambda o, g, bg: frozenset((y - bbox(o)[0], x - bbox(o)[1]) for y, x in o),
}


def prop_values(g, objs, bg, name):
    if name in ('size-rank', 'is-largest', 'is-smallest'):
        sizes = sorted({len(o) for o in objs}, reverse=True)
        if name == 'size-rank':
            return [sizes.index(len(o)) for o in objs]
        if name == 'is-largest':
            return [len(o) == sizes[0] for o in objs]
        return [len(o) == sizes[-1] for o in objs]
    if name == 'has-hole':
        res = []
        for o in objs:
            y0, x0, y1, x1 = bbox(o)
            cells = set(o)
            inner = [(y, x) for y in range(y0 + 1, y1) for x in range(x0 + 1, x1) if (y, x) not in cells]
            res.append(bool(inner))
        return res
    return [PROPS[name](o, g, bg) for o in objs]


def s_recolour_objects(pairs, budget):
    """Same shape in and out; each object keeps its cells and gets a new colour decided by one of its properties."""
    out = []
    if any(shape(a) != shape(b) for a, b in pairs):
        return out
    for diagonal in (False, True):
        for by_color in (True, False):
            for name in PROPS:
                table = {}
                good = True
                for a, b in pairs:
                    bg = bg_of(a)
                    objs = objects(a, bg, diagonal=diagonal, by_color=by_color)
                    if not objs or len(objs) > 60:
                        good = False; break
                    # outside objects nothing may change
                    cells = {c for o in objs for c in o}
                    if any(a[y][x] != b[y][x] for y in range(len(a)) for x in range(len(a[0])) if (y, x) not in cells):
                        good = False; break
                    for o, v in zip(objs, prop_values(a, objs, bg, name)):
                        new = {b[y][x] for y, x in o}
                        if len(new) != 1:
                            good = False; break
                        c = new.pop()
                        if table.setdefault(v, c) != c:
                            good = False; break
                    if not good:
                        break
                if not good or len(set(table.values())) < 2 and all(k is not None for k in table):
                    if not good:
                        continue
                if all(a == b for a, b in pairs):
                    continue

                def predict(q, diagonal=diagonal, by_color=by_color, name=name, table=dict(table)):
                    bg = bg_of(q)
                    objs = objects(q, bg, diagonal=diagonal, by_color=by_color)
                    rows = [list(r) for r in q]
                    for o, v in zip(objs, prop_values(q, objs, bg, name)):
                        if v not in table:
                            raise Unsupported('unseen property value')
                        for y, x in o:
                            rows[y][x] = table[v]
                    return tuple(map(tuple, rows))
                try:
                    if all(predict(a) == b for a, b in pairs):
                        out.append((2.5 + 0.1 * len(table) + 0.25 * diagonal + 0.25 * (not by_color), f'recolour-by-{name}', predict))
                except Exception:
                    pass
    return out


DIRS = {'up': (-1, 0), 'down': (1, 0), 'left': (0, -1), 'right': (0, 1), 'ul': (-1, -1), 'ur': (-1, 1), 'dl': (1, -1), 'dr': (1, 1)}
DIR_SETS = [('up',), ('down',), ('left',), ('right',), ('up', 'down'), ('left', 'right'), ('up', 'down', 'left', 'right'),
            ('ul', 'ur', 'dl', 'dr'), ('up', 'down', 'left', 'right', 'ul', 'ur', 'dl', 'dr')]


def s_lines(pairs, budget):
    """From every cell of colour c, draw rays in fixed directions until the border (optionally stopping at obstacles)."""
    out = []
    if any(shape(a) != shape(b) for a, b in pairs):
        return out
    added = set()
    for a, b in pairs:
        for y in range(len(a)):
            for x in range(len(a[0])):
                if a[y][x] != b[y][x]:
                    if a[y][x] != bg_of(a):
                        return out          # rays only paint background
                    added.add(b[y][x])
    if not added:
        return out
    sources = set(v for a, _ in pairs for r in a for v in r)
    for c in sources:
        for dirs in DIR_SETS:
            for stop in (False, True):
                for same in (True, False):
                    def predict(q, c=c, dirs=dirs, stop=stop, same=same):
                        bg = bg_of(q)
                        if c == bg:
                            raise Unsupported('bg')
                        rows = [list(r) for r in q]
                        h, w = shape(q)
                        paint = c if same else None
                        for y in range(h):
                            for x in range(w):
                                if q[y][x] != c:
                                    continue
                                for d in dirs:
                                    dy, dx = DIRS[d]
                                    yy, xx = y + dy, x + dx
                                    while 0 <= yy < h and 0 <= xx < w:
                                        if q[yy][xx] != bg:
                                            if stop:
                                                break
                                        else:
                                            rows[yy][xx] = paint if paint is not None else rows[yy][xx]
                                        yy += dy; xx += dx
                        return tuple(map(tuple, rows))
                    if not same:
                        continue
                    try:
                        if all(predict(a) == b for a, b in pairs):
                            out.append((2.0 + 0.1 * len(dirs) + 0.2 * stop, f'rays-{c}-{"+".join(dirs)}', predict))
                    except Exception:
                        pass
    # 0.4.4: every coloured cell sends rays of its own colour (stopping at other cells, or crossing them)
    for dirs in DIR_SETS:
        for stop in (True, False):
            def every(q, dirs=dirs, stop=stop):
                bg = bg_of(q)
                h, w = shape(q)
                rows = [list(r) for r in q]
                for y in range(h):
                    for x in range(w):
                        c = q[y][x]
                        if c == bg:
                            continue
                        for d in dirs:
                            dy, dx = DIRS[d]
                            yy, xx = y + dy, x + dx
                            while 0 <= yy < h and 0 <= xx < w:
                                if q[yy][xx] != bg:
                                    if stop:
                                        break
                                elif rows[yy][xx] not in (bg, c):
                                    raise Unsupported('rays cross')
                                else:
                                    rows[yy][xx] = c
                                yy += dy; xx += dx
                return tuple(map(tuple, rows))
            if _fits(pairs, every):
                out.append((2.3 + 0.1 * len(dirs) + 0.2 * stop, f'rays-all-{"+".join(dirs)}', every))
    return out


def s_constant_size_count(pairs, budget):
    """Output is a 1xN / Nx1 / NxN grid of one colour, N = number of objects (of the most common object colour)."""
    out = []
    for diagonal in (False, True):
        def count(g, diagonal=diagonal):
            bg = bg_of(g)
            return len(objects(g, bg, diagonal=diagonal, by_color=True))
        try:
            ns = [count(a) for a, _ in pairs]
        except Exception:
            continue
        for form in ('row', 'col'):
            def predict(q, form=form, count=count, colour=None):
                n = count(q)
                if not 1 <= n <= 30:
                    raise Unsupported('count')
                col = Counter(v for r in q for v in r if v != bg_of(q)).most_common(1)[0][0]
                return ((col,) * n,) if form == 'row' else tuple((col,) for _ in range(n))
            try:
                if all(predict(a) == b for a, b in pairs):
                    out.append((2.5, f'count-{form}', predict))
            except Exception:
                pass
    return out


def s_denoise(pairs, budget):
    """Remove small specks: keep objects of at least k cells (k learned), everything else becomes background."""
    out = []
    if any(shape(a) != shape(b) for a, b in pairs):
        return out
    for k in (2, 3, 4, 5):
        for diagonal in (False, True):
            def predict(q, k=k, diagonal=diagonal):
                bg = bg_of(q)
                rows = [list(r) for r in q]
                for o in objects(q, bg, diagonal=diagonal, by_color=False):
                    if len(o) < k:
                        for y, x in o:
                            rows[y][x] = bg
                return tuple(map(tuple, rows))
            try:
                if all(predict(a) == b for a, b in pairs) and any(a != b for a, b in pairs):
                    out.append((2.0 + 0.1 * k, f'denoise-{k}', predict))
            except Exception:
                pass
    return out


def s_fill_enclosed(pairs, budget):
    """Background regions not connected to the border get one colour (learned)."""
    out = []
    if any(shape(a) != shape(b) for a, b in pairs):
        return out
    fills = set()
    for a, b in pairs:
        for y in range(len(a)):
            for x in range(len(a[0])):
                if a[y][x] != b[y][x]:
                    fills.add(b[y][x])
    if len(fills) != 1:
        return out
    c = fills.pop()

    def predict(q):
        bg = bg_of(q)
        h, w = shape(q)
        outside = set()
        todo = [(y, x) for y in range(h) for x in range(w) if (y in (0, h - 1) or x in (0, w - 1)) and q[y][x] == bg]
        outside.update(todo)
        while todo:
            y, x = todo.pop()
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in outside and q[ny][nx] == bg:
                    outside.add((ny, nx)); todo.append((ny, nx))
        return tuple(tuple(c if q[y][x] == bg and (y, x) not in outside else q[y][x] for x in range(w)) for y in range(h))
    try:
        if all(predict(a) == b for a, b in pairs):
            out.append((1.5, 'fill-enclosed', predict))
    except Exception:
        pass
    return out


def s_symmetry_complete(pairs, budget):
    """Cells of one 'mask' colour are filled from the grid's own mirror images / rotations (repair a symmetric picture)."""
    out = []
    if any(shape(a) != shape(b) for a, b in pairs):
        return out
    masks = set()
    for a, b in pairs:
        for y in range(len(a)):
            for x in range(len(a[0])):
                if a[y][x] != b[y][x]:
                    masks.add(a[y][x])
    if len(masks) != 1:
        return out
    m = masks.pop()

    def predict(q):
        h, w = shape(q)
        rows = [list(r) for r in q]
        views = [flip_h(q), q[::-1], flip_h(q[::-1])]
        if h == w:
            views += [T(q), rotate(q), rotate(rotate(rotate(q))), T(flip_h(q[::-1]))]
        for y in range(h):
            for x in range(w):
                if q[y][x] == m:
                    for v in views:
                        if v[y][x] != m:
                            rows[y][x] = v[y][x]; break
                    else:
                        raise Unsupported('cannot repair')
        return tuple(map(tuple, rows))
    try:
        if all(predict(a) == b for a, b in pairs):
            out.append((2.0, 'symmetry-repair', predict))
    except Exception:
        pass
    # output is only the repaired patch under the mask
    def patch(q):
        cells = [(y, x) for y in range(len(q)) for x in range(len(q[0])) if q[y][x] == m]
        if not cells:
            raise Unsupported('no mask')
        y0, x0, y1, x1 = bbox(cells)
        full = predict(q)
        return sub(full, y0, x0, y1, x1)
    try:
        if all(patch(a) == b for a, b in pairs):
            out.append((2.5, 'symmetry-patch', patch))
    except Exception:
        pass
    return out


def s_mirror_concat(pairs, budget):
    """Output = the input next to / above its mirror image (all 8 two-part arrangements)."""
    out = []
    forms = {
        'h-flip': lambda q: tuple(r + r[::-1] for r in q), 'flip-h': lambda q: tuple(r[::-1] + r for r in q),
        'v-flip': lambda q: q + q[::-1], 'flip-v': lambda q: q[::-1] + q,
        'quad': lambda q: (lambda top: top + top[::-1])(tuple(r + r[::-1] for r in q)),
        'quad-rot': lambda q: (lambda top: top + tuple(r[::-1] for r in top[::-1]))(tuple(r + r[::-1] for r in q)),
    }
    for name, f in forms.items():
        try:
            if all(f(a) == b for a, b in pairs):
                out.append((1.5, 'mirror-' + name, f))
        except Exception:
            pass
    return out


def _features(g):
    """Per-cell descriptions of increasing size, computed once per grid: [(name, cost, grid of keys)]."""
    h, w = shape(g)
    bg = bg_of(g)
    at = lambda y, x: g[y][x] if 0 <= y < h and 0 <= x < w else -1
    rows_c = [frozenset(r) for r in g]
    cols_c = [frozenset(g[y][x] for y in range(h)) for x in range(w)]

    def ray(y, x, dy, dx):
        y += dy; x += dx
        while 0 <= y < h and 0 <= x < w:
            if g[y][x] != bg:
                return g[y][x]
            y += dy; x += dx
        return -1
    sizes, objinfo = {}, {}
    boxes = []
    for o in objects(g, bg, diagonal=False, by_color=True):
        y0, x0, y1, x1 = bbox(o)
        boxes.append((y0, x0, y1, x1, g[o[0][0]][o[0][1]]))
        for c in o:
            sizes[c] = len(o)
            objinfo[c] = (len(o), y1 - y0 + 1, x1 - x0 + 1, c[0] in (y0, y1) or c[1] in (x0, x1))
    in_box = [[frozenset(col for y0, x0, y1, x1, col in boxes if y0 <= y <= y1 and x0 <= x <= x1) for x in range(w)] for y in range(h)]

    def dray(y, x, dy, dx):
        n = 0
        y += dy; x += dx
        while 0 <= y < h and 0 <= x < w:
            n += 1
            if g[y][x] != bg:
                return g[y][x], n
            y += dy; x += dx
        return -1, 0
    feats = {
        'cell': lambda y, x: (g[y][x],),
        'n4': lambda y, x: (g[y][x], at(y - 1, x), at(y + 1, x), at(y, x - 1), at(y, x + 1)),
        'n4-set': lambda y, x: (g[y][x], frozenset((at(y - 1, x), at(y + 1, x), at(y, x - 1), at(y, x + 1)))),
        'n8': lambda y, x: (g[y][x],) + tuple(at(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx),
        'n8-count': lambda y, x: (g[y][x], tuple(sorted(Counter(at(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx).items()))),
        'rays': lambda y, x: (g[y][x], ray(y, x, -1, 0), ray(y, x, 1, 0), ray(y, x, 0, -1), ray(y, x, 0, 1)),
        'ray-pairs': lambda y, x: (g[y][x], ray(y, x, -1, 0) == ray(y, x, 1, 0) != -1 and ray(y, x, -1, 0),
                                   ray(y, x, 0, -1) == ray(y, x, 0, 1) != -1 and ray(y, x, 0, -1)),
        'row-col': lambda y, x: (g[y][x], rows_c[y], cols_c[x]),
        'size': lambda y, x: (g[y][x], sizes.get((y, x), 0)),
        'parity': lambda y, x: (g[y][x], y % 2, x % 2),
        'border': lambda y, x: (g[y][x], y in (0, h - 1), x in (0, w - 1)),
        'object': lambda y, x: (g[y][x], objinfo.get((y, x))),
        'in-box': lambda y, x: (g[y][x], in_box[y][x]),
        'diag-rays': lambda y, x: (g[y][x], ray(y, x, -1, -1), ray(y, x, -1, 1), ray(y, x, 1, -1), ray(y, x, 1, 1)),
        'mod3': lambda y, x: (g[y][x], y % 3, x % 3),
        'ray-dist': lambda y, x: (g[y][x],) + tuple((lambda r: (r[0], r[1] % 2))(dray(y, x, dy, dx)) for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))),
    }
    cost = {'cell': 1.0, 'n4': 2.6, 'n4-set': 2.2, 'n8': 3.4, 'n8-count': 3.0, 'rays': 2.6, 'ray-pairs': 2.3, 'row-col': 2.8,
            'size': 2.0, 'parity': 1.8, 'border': 1.8, 'object': 2.4, 'in-box': 2.2, 'diag-rays': 2.6, 'mod3': 2.0, 'ray-dist': 3.0}
    return [(n, cost[n], [[f(y, x) for x in range(w)] for y in range(h)]) for n, f in feats.items()]


def s_local_rule(pairs, budget):
    """Same-shape tasks: each output cell = a lookup of a small description of the input cell's surroundings. The table must
    agree on every demonstration cell; the smallest description that does wins (fewest distinct keys breaks ties)."""
    out = []
    if any(shape(a) != shape(b) for a, b in pairs) or all(a == b for a, b in pairs):
        return out
    per = [(_features(a), b) for a, b in pairs]
    names = [n for n, _, _ in per[0][0]]
    combos = [(i,) for i in range(len(names))] + [(i, j) for i in range(len(names)) for j in range(i + 1, len(names)) if i and j]
    started = time.monotonic()
    for combo in combos:
        if time.monotonic() - started > budget:
            break
        table = {}
        good = True
        for feats, b in per:
            keys = [list(zip(*(feats[c][2][y] for c in combo))) for y in range(len(b))] if len(combo) > 1 else feats[combo[0]][2]
            for y, row in enumerate(keys):
                for x, k in enumerate(row):
                    if table.setdefault(k, b[y][x]) != b[y][x]:
                        good = False; break
                if not good:
                    break
            if not good:
                break
        if not good:
            continue
        cost = sum(per[0][0][c][1] for c in combo) + 0.01 * len(table)
        name = '+'.join(names[c] for c in combo)

        for keep in (False, True):
            def predict(q, combo=combo, table=dict(table), keep=keep):
                f = _features(q)
                keys = [list(zip(*(f[c][2][y] for c in combo))) for y in range(len(q))] if len(combo) > 1 else f[combo[0]][2]
                res = []
                for y, row in enumerate(keys):
                    r = []
                    for x, k in enumerate(row):
                        if k not in table:
                            if not keep:
                                raise Unsupported('unseen neighbourhood')
                            r.append(q[y][x])     # a neighbourhood never seen in the examples: leave the cell as it is
                        else:
                            r.append(table[k])
                    res.append(tuple(r))
                return tuple(res)
            # the keep-as-is variant is only allowed when unchanged cells are the rule's own default in the examples
            if keep and not all(sum(a[y][x] == b[y][x] for y in range(len(a)) for x in range(len(a[0]))) * 2 > len(a) * len(a[0]) for a, b in pairs):
                continue
            out.append((cost + (1.5 if keep else 0), 'local-' + name + ('-keep' if keep else ''), predict))
    return out


def s_periodic(pairs, budget):
    """Same-shape: one 'mask' colour hides part of a repeating pattern; the smallest period consistent with the rest fills it."""
    out = []
    if any(shape(a) != shape(b) for a, b in pairs):
        return out
    masks = {a[y][x] for a, b in pairs for y in range(len(a)) for x in range(len(a[0])) if a[y][x] != b[y][x]}
    if len(masks) != 1:
        return out
    m = masks.pop()

    def fill(q, crop_out=False):
        h, w = shape(q)
        for total in range(2, h + w + 1):
            for py in range(1, min(h, total) + 1):
                px = total - py
                if not 1 <= px <= w:
                    continue
                table = {}
                good = True
                for y in range(h):
                    for x in range(w):
                        v = q[y][x]
                        if v == m:
                            continue
                        if table.setdefault((y % py, x % px), v) != v:
                            good = False; break
                    if not good:
                        break
                if good and all((y % py, x % px) in table for y in range(h) for x in range(w)):
                    return tuple(tuple(table[(y % py, x % px)] for x in range(w)) for y in range(h))
        raise Unsupported('no period')
    try:
        if all(fill(a) == b for a, b in pairs):
            out.append((2.0, 'periodic-fill', fill))
    except Exception:
        pass
    return out


def s_object_gravity(pairs, budget):
    """Same-shape: every object of the moving colour(s) slides in one direction until it touches something or the border."""
    out = []
    if any(shape(a) != shape(b) for a, b in pairs):
        return out
    for d in ('up', 'down', 'left', 'right'):
        dy, dx = DIRS[d]
        for moving in ('all', 'non-largest'):
            def predict(q, dy=dy, dx=dx, moving=moving):
                bg = bg_of(q)
                h, w = shape(q)
                objs = objects(q, bg, diagonal=True, by_color=False)
                if not objs or len(objs) > 30:
                    raise Unsupported('objects')
                fixed = set()
                if moving == 'non-largest':
                    big = max(objs, key=len)
                    fixed = set(big)
                    objs = [o for o in objs if o is not big]
                order = sorted(objs, key=lambda o: -max(y * dy + x * dx for y, x in o))
                occupied = set(fixed) | {c for o in objs for c in o}
                rows = [list(r) for r in q]
                for o in order:
                    cells = set(o)
                    occupied -= cells
                    colour = {c: q[c[0]][c[1]] for c in o}
                    k = 0
                    while all(0 <= y + (k + 1) * dy < h and 0 <= x + (k + 1) * dx < w and (y + (k + 1) * dy, x + (k + 1) * dx) not in occupied for y, x in o):
                        k += 1
                    for y, x in o:
                        rows[y][x] = bg
                    for y, x in o:
                        rows[y + k * dy][x + k * dx] = colour[(y, x)]
                        occupied.add((y + k * dy, x + k * dx))
                return tuple(map(tuple, rows))
            try:
                if all(predict(a) == b for a, b in pairs) and any(a != b for a, b in pairs):
                    out.append((2.0 + 0.3 * (moving != 'all'), f'gravity-{d}-{moving}', predict))
            except Exception:
                pass
    return out


def s_native(pairs, budget):
    """CAEL's earlier checked engines: the native integer-stream solver and the geometry/scale/colour-map inducer."""
    out = []
    examples = [dict(input=[list(r) for r in a], output=[list(r) for r in b]) for a, b in pairs]

    def stream(q):
        from . import stream_grid
        return grid(stream_grid.solve(dict(examples=examples, query=[list(r) for r in q]))['prediction'])

    def induced(q):
        from . import grid_induction
        return grid(grid_induction.solve(examples, [list(r) for r in q])['prediction'])
    out.append((1.0, 'native-stream', stream))
    out.append((1.2, 'induction', induced))
    return out


def lattice(g):
    """Cells of a grid split by full rows and columns of one separator colour: (separator, [[cell grids]]) or None."""
    h, w = shape(g)
    for sep in sorted(colors(g)):
        rs = [y for y in range(h) if all(v == sep for v in g[y])]
        cs = [x for x in range(w) if all(g[y][x] == sep for y in range(h))]
        if not rs and not cs:
            continue
        def spans(cut, n):
            out, start = [], 0
            for c in cut + [n]:
                if c > start:
                    out.append((start, c - 1))
                start = c + 1
            return out
        ys, xs = spans(rs, h), spans(cs, w)
        if len(ys) * len(xs) < 2 or len(ys) * len(xs) > 64:
            continue
        cells = [[sub(g, y0, x0, y1, x1) for x0, x1 in xs] for y0, y1 in ys]
        if any(sep in {v for r in c for v in r} for row in cells for c in row):
            continue
        return sep, cells
    return None


CELL_PICK = ['unique', 'most-fg', 'least-fg', 'most-colours', 'unique-colour-set']


def pick_cell(cells, kind):
    flat = [c for row in cells for c in row]
    bgc = Counter(v for c in flat for r in c for v in r).most_common(1)[0][0]
    if kind == 'unique':
        cnt = Counter(flat); key = [cnt[c] == 1 for c in flat]; want = True
    elif kind in ('most-fg', 'least-fg'):
        key = [sum(v != bgc for r in c for v in r) for c in flat]; want = max(key) if kind == 'most-fg' else min(key)
    elif kind == 'most-colours':
        key = [len({v for r in c for v in r}) for c in flat]; want = max(key)
    else:
        sets = [frozenset(v for r in c for v in r) for c in flat]
        cnt = Counter(sets); key = [cnt[s] == 1 for s in sets]; want = True
    chosen = [c for c, k in zip(flat, key) if k == want]
    if len(chosen) != 1:
        raise Unsupported('tie')
    return chosen[0]


def s_partition(pairs, budget):
    """Grids split into cells by separator lines: the answer is one selected cell, a summary grid (one pixel per cell), or
    an overlay of all cells."""
    out = []
    for kind in CELL_PICK:
        def predict(q, kind=kind):
            got = lattice(q)
            if not got:
                raise Unsupported('no lattice')
            return pick_cell(got[1], kind)
        try:
            if all(predict(a) == b for a, b in pairs):
                out.append((2.0, 'cell-' + kind, predict))
        except Exception:
            pass
    for mode in ('dominant', 'any-fg'):
        def summary(q, mode=mode):
            got = lattice(q)
            if not got:
                raise Unsupported('no lattice')
            cells = got[1]
            bgc = Counter(v for row in cells for c in row for r in c for v in r).most_common(1)[0][0]
            res = []
            for row in cells:
                r = []
                for c in row:
                    fg = Counter(v for rr in c for v in rr if v != bgc)
                    r.append(fg.most_common(1)[0][0] if fg else bgc)
                res.append(tuple(r))
            return tuple(res)
        try:
            if all(summary(a) == b for a, b in pairs):
                out.append((2.0, 'cell-summary-' + mode, summary))
        except Exception:
            pass
    for order in ('first', 'last'):
        def overlay(q, order=order):
            got = lattice(q)
            if not got:
                raise Unsupported('no lattice')
            flat = [c for row in got[1] for c in row]
            if len({shape(c) for c in flat}) != 1:
                raise Unsupported('cells differ')
            bgc = Counter(v for c in flat for r in c for v in r).most_common(1)[0][0]
            seq = flat if order == 'first' else flat[::-1]
            hh, ww = shape(flat[0])
            return tuple(tuple(next((c[y][x] for c in seq if c[y][x] != bgc), bgc) for x in range(ww)) for y in range(hh))
        try:
            if all(overlay(a) == b for a, b in pairs):
                out.append((2.2, 'cell-overlay-' + order, overlay))
        except Exception:
            pass
    return out


def s_crop_frame(pairs, budget):
    """The answer is what lies inside (or including) a rectangle frame drawn in one colour."""
    out = []
    for inner in (True, False):
        def predict(q, inner=inner):
            h, w = shape(q)
            found = []
            for c in colors(q):
                cells = [(y, x) for y in range(h) for x in range(w) if q[y][x] == c]
                y0, x0, y1, x1 = bbox(cells)
                if y1 - y0 < 2 or x1 - x0 < 2:
                    continue
                border = {(y, x) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if y in (y0, y1) or x in (x0, x1)}
                if border <= set(cells):
                    found.append((y0, x0, y1, x1))
            if len(found) != 1:
                raise Unsupported('frame')
            y0, x0, y1, x1 = found[0]
            return sub(q, y0 + 1, x0 + 1, y1 - 1, x1 - 1) if inner else sub(q, y0, x0, y1, x1)
        try:
            if all(predict(a) == b for a, b in pairs):
                out.append((1.8, 'frame-' + ('inside' if inner else 'with'), predict))
        except Exception:
            pass
    return out


def s_two_stage(pairs, budget):
    """A shape-changing first step (one grammar operation, a frame crop, a lattice overlay or a mirror form) that makes
    every input the size of its output, then a same-shape rule (local rule, object recolour) on the result."""
    out = []
    if all(shape(a) == shape(b) for a, b in pairs):
        return out
    started = time.monotonic()
    firsts = [('op', op) for op in gp.grammar()]
    firsts += [('frame', None), ('overlay', None)]
    for kind, op in firsts:
        if time.monotonic() - started > budget:
            break

        def first(q, kind=kind, op=op):
            if kind == 'op':
                return grid([list(r) for r in gp.apply(q, op)])
            if kind == 'frame':
                return s_crop_frame.__wrapped__(q) if hasattr(s_crop_frame, '__wrapped__') else _frame_inside(q)
            got = lattice(q)
            if not got:
                raise Unsupported('no lattice')
            flat = [c for row in got[1] for c in row]
            if len({shape(c) for c in flat}) != 1:
                raise Unsupported('cells differ')
            bgc = Counter(v for c in flat for r in c for v in r).most_common(1)[0][0]
            hh, ww = shape(flat[0])
            return tuple(tuple(next((c[y][x] for c in flat if c[y][x] != bgc), bgc) for x in range(ww)) for y in range(hh))
        try:
            mid = [(first(a), b) for a, b in pairs]
        except Exception:
            continue
        if any(shape(m) != shape(b) for m, b in mid) or all(m == b for m, b in mid):
            continue
        for solver in (s_local_rule, s_recolour_objects, s_stamp, s_span, s_nearest_recolour, s_bbox_fill, s_role_swap, s_lines):
            try:
                fits = solver(mid, max(0.2, (budget - (time.monotonic() - started)) / 4))
            except Exception:
                continue
            for cost, name, predict in fits[:4]:
                out.append((cost + 1.2, f'two-stage-{kind}-{name}', lambda q, f=first, p=predict: p(f(q))))
    return out


def _frame_inside(q):
    h, w = shape(q)
    found = []
    for c in colors(q):
        cells = [(y, x) for y in range(h) for x in range(w) if q[y][x] == c]
        y0, x0, y1, x1 = bbox(cells)
        if y1 - y0 < 2 or x1 - x0 < 2:
            continue
        border = {(y, x) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if y in (y0, y1) or x in (x0, x1)}
        if border <= set(cells):
            found.append((y0, x0, y1, x1))
    if len(found) != 1:
        raise Unsupported('frame')
    y0, x0, y1, x1 = found[0]
    return sub(q, y0 + 1, x0 + 1, y1 - 1, x1 - 1)


# ---------------------------------------------------------------- 0.4.4: drawing around and between cells (developed on training)
def _additive(pairs):
    """Same shapes, and the output only adds colour on background cells of the input."""
    for a, b in pairs:
        if shape(a) != shape(b):
            return False
        bg = bg_of(a)
        for ra, rb in zip(a, b):
            for x, y in zip(ra, rb):
                if x != y and x != bg:
                    return False
    return True


def _stamp_apply(a, stamps, singles_only):
    bg = bg_of(a)
    h, w = shape(a)
    out = [list(r) for r in a]
    wrote = {}
    single = None
    if singles_only:
        single = set()
        for y in range(h):
            for x in range(w):
                c = a[y][x]
                if c != bg and all(not (0 <= y + dy < h and 0 <= x + dx < w) or a[y + dy][x + dx] != c
                                   for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))):
                    single.add((y, x))
    for y in range(h):
        for x in range(w):
            c = a[y][x]
            if c == bg or c not in stamps or (single is not None and (y, x) not in single):
                continue
            for (dy, dx), k in stamps[c].items():
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and a[yy][xx] == bg:
                    if wrote.get((yy, xx), k) != k:
                        raise Unsupported('stamps overlap')
                    wrote[(yy, xx)] = k
                    out[yy][xx] = k
    return tuple(tuple(r) for r in out)


def s_stamp(pairs, budget):
    """Every cell of colour c gets the same pattern drawn on the background around it (learned per colour, radius 1-3)."""
    if not _additive(pairs):
        return []
    found = []
    for singles_only in (False, True):
        for R in (1, 2, 3):
            obs = defaultdict(lambda: defaultdict(set))
            for a, b in pairs:
                bg = bg_of(a)
                h, w = shape(a)
                for y in range(h):
                    for x in range(w):
                        c = a[y][x]
                        if c == bg:
                            continue
                        for dy in range(-R, R + 1):
                            for dx in range(-R, R + 1):
                                yy, xx = y + dy, x + dx
                                if (dy or dx) and 0 <= yy < h and 0 <= xx < w and a[yy][xx] == bg:
                                    obs[c][(dy, dx)].add(b[yy][xx] if b[yy][xx] != bg else -1)
            stamps = {}
            for c, offs in obs.items():
                st = {}
                for off, vals in offs.items():
                    if len(vals) == 1 and -1 not in vals:
                        st[off] = next(iter(vals))
                if st:
                    stamps[c] = st
            if not stamps:
                continue
            try:
                if all(_stamp_apply(a, stamps, singles_only) == b for a, b in pairs):
                    size = sum(len(s) for s in stamps.values())
                    found.append((2.0 + 0.05 * size + 0.3 * R + (0.2 if singles_only else 0), f'stamp-r{R}{"-single" if singles_only else ""}',
                                  lambda q, s=stamps, so=singles_only: _stamp_apply(q, s, so)))
                    break
            except Unsupported:
                continue
    return found


def _span_apply(a, axis, fill):
    bg = bg_of(a)
    h, w = shape(a)
    out = [list(r) for r in a]
    rows = [[(y, x) for x in range(w)] for y in range(h)]
    cols = [[(y, x) for y in range(h)] for x in range(w)]
    lines = {'row': rows, 'col': cols, 'both': rows + cols, 'row>col': cols + rows, 'col>row': rows + cols}[axis]
    over = axis in ('row>col', 'col>row')           # the second direction is drawn over the first where they cross
    for line in lines:
        where = defaultdict(list)
        for i, (y, x) in enumerate(line):
            if a[y][x] != bg:
                where[a[y][x]].append(i)
        for c, idx in where.items():
            if len(idx) < 2:
                continue
            k = c if fill is None else fill
            for i in range(idx[0] + 1, idx[-1]):
                y, x = line[i]
                if a[y][x] == bg:
                    if out[y][x] not in (bg, k) and not over:
                        raise Unsupported('spans cross')
                    out[y][x] = k
    return tuple(tuple(r) for r in out)


def s_span(pairs, budget):
    """In each row (or column), the background between the first and last cell of one colour is filled, with that colour or
    with one fixed colour."""
    if not _additive(pairs):
        return []
    added = {b[y][x] for a, b in pairs for y in range(len(a)) for x in range(len(a[0])) if a[y][x] != b[y][x]}
    fills = [None] + (sorted(added) if len(added) == 1 else [])
    found = []
    for axis in ('row', 'col', 'both', 'row>col', 'col>row'):
        for fill in fills:
            try:
                if all(_span_apply(a, axis, fill) == b for a, b in pairs):
                    found.append((2.5 + (0.3 if axis != 'row' and axis != 'col' else 0) + (0.2 if fill is not None else 0), f'span-{axis}',
                                  lambda q, ax=axis, f=fill: _span_apply(q, ax, f)))
            except Unsupported:
                continue
    return found


def _nearest_apply(a, c, metric):
    bg = bg_of(a)
    h, w = shape(a)
    others = [(y, x, a[y][x]) for y in range(h) for x in range(w) if a[y][x] not in (bg, c)]
    if not others:
        raise Unsupported('nothing to take a colour from')
    out = [list(r) for r in a]
    for y in range(h):
        for x in range(w):
            if a[y][x] != c:
                continue
            best, cols = None, set()
            for yy, xx, k in others:
                d = abs(yy - y) + abs(xx - x) if metric == 'L1' else max(abs(yy - y), abs(xx - x))
                if best is None or d < best:
                    best, cols = d, {k}
                elif d == best:
                    cols.add(k)
            if len(cols) != 1:
                raise Unsupported('tie')
            out[y][x] = cols.pop()
    return tuple(tuple(r) for r in out)


def s_nearest_recolour(pairs, budget):
    """Every cell of one colour takes the colour of the nearest cell of another (non-background) colour."""
    if any(shape(a) != shape(b) for a, b in pairs):
        return []
    changed = {a[y][x] for a, b in pairs for y in range(len(a)) for x in range(len(a[0])) if a[y][x] != b[y][x]}
    if len(changed) != 1:
        return []
    c = changed.pop()
    found = []
    for metric in ('L1', 'Linf'):
        try:
            if all(_nearest_apply(a, c, metric) == b for a, b in pairs):
                found.append((3.0, f'nearest-{metric}', lambda q, c=c, m=metric: _nearest_apply(q, c, m)))
        except Unsupported:
            continue
    return found


def _mask_key(g, mode):
    bg = bg_of(g)
    if mode == 'mask':
        return tuple(tuple(int(v != bg) for v in r) for r in g)
    if mode == 'mask-crop':
        cells = [(y, x) for y, r in enumerate(g) for x, v in enumerate(r) if v != bg]
        if not cells:
            return ()
        y0, x0 = min(y for y, _ in cells), min(x for _, x in cells)
        y1, x1 = max(y for y, _ in cells), max(x for _, x in cells)
        return tuple(tuple(int(g[y][x] != bg) for x in range(x0, x1 + 1)) for y in range(y0, y1 + 1))
    return g


def s_lookup(pairs, budget):
    """The output is one of a few fixed grids, chosen by the input's pattern (exact, cropped, or as a shape mask). It predicts
    only when the test pattern was seen in a demonstration with an unambiguous answer."""
    outs = {b for _, b in pairs}
    if len(outs) == len(pairs) or len(pairs) < 3:
        return []
    found = []
    for mode in ('mask', 'mask-crop'):
        table = {}
        okay = True
        for a, b in pairs:
            k = _mask_key(a, mode)
            if table.setdefault(k, b) != b:
                okay = False
                break
        if not okay or len(table) == len(pairs):
            continue

        def predict(q, mode=mode, table=table):
            k = _mask_key(q, mode)
            if k not in table:
                raise Unsupported('unseen pattern')
            return table[k]
        found.append((3.5, f'lookup-{mode}', predict))
    return found


def _bbox_apply(a, fill, diagonal):
    bg = bg_of(a)
    out = [list(r) for r in a]
    for obj in objects(a, bg, diagonal=diagonal, by_color=True):
        cells = obj['cells'] if isinstance(obj, dict) else obj
        ys = [p[0] for p in cells]
        xs = [p[1] for p in cells]
        colour = a[ys[0]][xs[0]]
        k = colour if fill is None else fill
        for y in range(min(ys), max(ys) + 1):
            for x in range(min(xs), max(xs) + 1):
                if a[y][x] == bg:
                    if out[y][x] not in (bg, k):
                        raise Unsupported('boxes overlap')
                    out[y][x] = k
    return tuple(tuple(r) for r in out)


def s_bbox_fill(pairs, budget):
    """The background inside each object's bounding box is filled (with one colour, or the object's own)."""
    if not _additive(pairs):
        return []
    added = {b[y][x] for a, b in pairs for y in range(len(a)) for x in range(len(a[0])) if a[y][x] != b[y][x]}
    found = []
    for diagonal in (True, False):
        for fill in [None] + (sorted(added) if len(added) == 1 else []):
            try:
                if all(_bbox_apply(a, fill, diagonal) == b for a, b in pairs):
                    found.append((3.0 + (0.2 if fill is not None else 0), 'bboxfill', lambda q, f=fill, d=diagonal: _bbox_apply(q, f, d)))
                    return found
            except Unsupported:
                continue
    return found


def s_role_swap(pairs, budget):
    """Each input has the background, one colour F shared by every input, and one other colour V that varies. The output
    recolours by role: F, V and the background each become F, V, the background or one fixed colour."""
    if any(shape(a) != shape(b) for a, b in pairs):
        return []
    sets = [set(colors(a)) | {bg_of(a)} for a, _ in pairs]
    if any(len(s) != 2 and len(s) != 3 for s in sets):
        return []
    common = set.intersection(*sets)
    roles = []
    for (a, b), s in zip(pairs, sets):
        if len(s) == 2:
            fixed = common if len(common) == 1 else None
            if not fixed:
                return []
            f = next(iter(fixed))
            v = next(iter(s - fixed))
            roles.append(dict(F=f, V=v))
        else:
            return []
    found = []
    targets = ['F', 'V'] + sorted({c for _, b in pairs for r in b for c in r})
    for tf in targets:
        for tv in targets:
            def predict(q, tf=tf, tv=tv):
                cs = set(c for r in q for c in r)
                if len(cs) != 2 or roles[0]['F'] not in cs:
                    raise Unsupported('roles')
                f = roles[0]['F']
                v = next(iter(cs - {f}))
                pick = lambda t: f if t == 'F' else v if t == 'V' else t
                return tuple(tuple(pick(tf) if c == f else pick(tv) for c in r) for r in q)
            try:
                if all(predict(a) == b for a, b in pairs):
                    found.append((3.0, 'roleswap', predict))
                    return found
            except Unsupported:
                continue
    return found


def s_count_bar(pairs, budget):
    """The output is a fixed-size bar: as many cells of one colour as there are objects of one kind, the rest background."""
    outs = {shape(b) for _, b in pairs}
    if len(outs) != 1:
        return []
    oh, ow = next(iter(outs))
    if oh != 1 and ow != 1:
        return []
    found = []
    for diagonal in (False, True):
        kinds = set()
        for a, _ in pairs:
            bg = bg_of(a)
            for cells in objects(a, bg, diagonal=diagonal):
                kinds.add((a[cells[0][0]][cells[0][1]], len(cells)))
        preds = [('colour', c) for c in {k[0] for k in kinds}] + [('colour-size', k) for k in kinds] + [('any', None)]
        for kind, val in preds:
            def count(g, kind=kind, val=val, diagonal=diagonal):
                bg = bg_of(g)
                n = 0
                for cells in objects(g, bg, diagonal=diagonal):
                    c = g[cells[0][0]][cells[0][1]]
                    if kind == 'any' or (kind == 'colour' and c == val) or (kind == 'colour-size' and (c, len(cells)) == val):
                        n += 1
                return n
            fill = {v for _, b in pairs for r in b for v in r}
            for k in fill:
                for empty in fill:
                    if k == empty:
                        continue
                    def predict(q, count=count, k=k, empty=empty):
                        n = count(q)
                        flat = [k if i < n else empty for i in range(oh * ow)]
                        return tuple(tuple(flat[i * ow:(i + 1) * ow]) for i in range(oh))
                    if all(predict(a) == b for a, b in pairs) and len({count(a) for a, _ in pairs}) > 1:
                        found.append((3.5, 'countbar', predict))
                        return found
    return found


def s_union(pairs, budget):
    """A swarm of drawing specialists: when the output adds several colours, each added colour may be explained by a
    different family (stamps, spans, box fills), each fitted on its own colour only, and their drawings are merged."""
    if not _additive(pairs):
        return []
    added = sorted({b[y][x] for a, b in pairs for y in range(len(a)) for x in range(len(a[0])) if a[y][x] != b[y][x]})
    if len(added) < 2 or len(added) > 4:
        return []
    started = time.monotonic()
    parts = []
    for k in added:
        part = [(a, tuple(tuple(b[y][x] if (b[y][x] == k and a[y][x] != b[y][x]) else a[y][x] for x in range(len(a[0])))
                          for y in range(len(a)))) for a, b in pairs]
        best = None
        for solver in (s_stamp, s_span, s_bbox_fill, s_lines):
            if time.monotonic() - started > budget:
                return []
            try:
                fits = solver(part, budget / 4)
            except Exception:
                continue
            for cost, name, predict in fits:
                if best is None or cost < best[0]:
                    best = (cost, name, predict)
        if best is None:
            return []
        parts.append(best)

    def predict(q, parts=parts):
        bg = bg_of(q)
        out = [list(r) for r in q]
        for _, _, p in parts:
            got = p(q)
            for y, row in enumerate(got):
                for x, v in enumerate(row):
                    if v != q[y][x]:
                        if out[y][x] not in (q[y][x], v):
                            raise Unsupported('drawings collide')
                        out[y][x] = v
        return tuple(tuple(r) for r in out)
    try:
        if all(predict(a) == b for a, b in pairs):
            return [(sum(c for c, _, _ in parts) + 0.5, 'union-' + '+'.join(n for _, n, _ in parts), predict)]
    except Unsupported:
        pass
    return []


# ---------------------------------------------------------------- 0.4.4 round 2: rules with a parameter read from the input
def _fits(pairs, predict):
    try:
        return all(predict(a) == b for a, b in pairs)
    except Exception:
        return False


def _counts(g):
    return Counter(v for r in g for v in r)


def s_fill_one(pairs, budget):
    """The whole output (same size) is one colour: the commonest, the rarest, or the commonest non-background colour."""
    if any(shape(a) != shape(b) or len(set(v for r in b for v in r)) != 1 for a, b in pairs):
        return []
    rules = {'commonest': lambda g: _counts(g).most_common()[0][0],
             'rarest': lambda g: min(_counts(g).items(), key=lambda kv: (kv[1], kv[0]))[0],
             'commonest-fg': lambda g: Counter(v for r in g for v in r if v != bg_of(g)).most_common()[0][0]}
    out = []
    for name, f in rules.items():
        def predict(q, f=f):
            h, w = shape(q)
            return blank(h, w, f(q))
        if _fits(pairs, predict):
            out.append((2.0, f'fillone-{name}', predict))
    return out


def _scale(g, k):
    return tuple(tuple(v for v in r for _ in range(k)) for r in g for _ in range(k))


def s_scale_by(pairs, budget):
    """The input scaled up (or tiled) by a factor read from the input: its number of colours or of non-background cells."""
    feats = {'colours': lambda g: len(colors(g) - {bg_of(g)}) if isinstance(colors(g), set) else len(set(v for r in g for v in r) - {bg_of(g)}),
             'cells': lambda g: sum(v != bg_of(g) for r in g for v in r),
             'bg-cells': lambda g: sum(v == bg_of(g) for r in g for v in r)}
    out = []
    for fname, f in feats.items():
        for how in ('scale', 'tile'):
            def predict(q, f=f, how=how):
                k = f(q)
                if not 1 <= k <= 10:
                    raise Unsupported('factor')
                if how == 'scale':
                    return _scale(q, k)
                return tuple(tuple(v for _ in range(k) for v in r) for _ in range(k) for r in q)
            if _fits(pairs, predict) and len({f(a) for a, _ in pairs}) > 1:
                out.append((2.5, f'scaleby-{fname}-{how}', predict))
    return out


def s_repeat_unit(pairs, budget):
    """The input is a repetition (with possible mirroring) of the output: the output is its smallest repeating unit, or one
    of two equal halves."""
    def unit(q):
        h, w = shape(q)
        for uh in range(1, h + 1):
            if h % uh:
                continue
            for uw in range(1, w + 1):
                if w % uw or (uh, uw) == (h, w):
                    continue
                if all(q[y][x] == q[y % uh][x % uw] for y in range(h) for x in range(w)):
                    return tuple(tuple(q[y][x] for x in range(uw)) for y in range(uh))
        raise Unsupported('no repeat')
    out = []
    if _fits(pairs, unit):
        out.append((2.0, 'repeat-unit', unit))
    for side in ('left', 'top'):
        def half(q, side=side):
            h, w = shape(q)
            if side == 'left':
                if w % 2:
                    raise Unsupported('odd')
                return tuple(r[:w // 2] for r in q)
            if h % 2:
                raise Unsupported('odd')
            return tuple(q[:h // 2])

        def either(q, half=half):
            h, w = shape(q)
            if w % 2 == 0 and all(r[:w // 2] == r[w // 2:] for r in q):
                return tuple(r[:w // 2] for r in q)
            if h % 2 == 0 and q[:h // 2] == q[h // 2:]:
                return tuple(q[:h // 2])
            raise Unsupported('no equal halves')
        if _fits(pairs, either):
            out.append((2.2, 'equal-half', either))
            break
    return out


def _blocks(q, oh, ow):
    h, w = shape(q)
    if h % oh or w % ow or (h, w) == (oh, ow):
        raise Unsupported('no split')
    return [tuple(tuple(q[y][x] for x in range(bx, bx + ow)) for y in range(by, by + oh)) for by in range(0, h, oh) for bx in range(0, w, ow)]


BLOCK_PICK = {
    'odd-one-out': lambda bs: [b for b in bs if sum(c == b for c in bs) == 1] if len(set(bs)) == 2 else [],
    'asymmetric': lambda bs: [b for b in bs if not (b == tuple(tuple(reversed(r)) for r in b) or b == tuple(reversed(b)) or b == T(b))],
    'symmetric': lambda bs: [b for b in bs if b == tuple(tuple(reversed(r)) for r in b) or b == tuple(reversed(b)) or b == T(b)],
    'most-cells': lambda bs: [max(bs, key=lambda b: sum(v != bg_of(b) for r in b for v in r))],
    'fewest-cells': lambda bs: [min(bs, key=lambda b: sum(v != bg_of(b) for r in b for v in r))],
    'most-colours': lambda bs: [max(bs, key=lambda b: len(set(v for r in b for v in r)))],
    'fewest-colours': lambda bs: [min(bs, key=lambda b: len(set(v for r in b for v in r)))],
    'odd-colour': lambda bs: [b for b in bs if sum(set(v for r in c for v in r) == set(v for r in b for v in r) for c in bs) == 1],
    'odd-mask': lambda bs: _odd_mask(bs),
}


def _odd_mask(bs):
    B = Counter(v for b in bs for r in b for v in r).most_common(1)[0][0]
    masks = [tuple(tuple(v != B for v in r) for r in b) for b in bs]
    return [b for b, m in zip(bs, masks) if masks.count(m) == 1]


def s_pick_block(pairs, budget):
    """The input is k equal blocks side by side or stacked (no separator lines); the output is the one block picked by a
    rule (the odd one out, the asymmetric one, the one with most cells or colours, ...)."""
    shapes = {shape(b) for _, b in pairs}
    out = []
    for name, pick in BLOCK_PICK.items():
        def predict(q, pick=pick):
            h, w = shape(q)
            if len(shapes) == 1:                     # every output is the same block size: split by it
                bh, bw = next(iter(shapes))
            else:
                (ha, wa), (hb, wb) = shape(pairs[0][0]), shape(pairs[0][1])
                if ha % hb or wa % wb:
                    raise Unsupported('ratio')
                bh, bw = h // (ha // hb), w // (wa // wb)
            bs = _blocks(q, bh, bw)
            got = pick(bs)
            if len(got) != 1:
                raise Unsupported('not one')
            return got[0]
        if _fits(pairs, predict):
            out.append((2.6, f'pickblock-{name}', predict))
    return out


FEATURES = {
    'sym-lr': lambda g: g == tuple(tuple(reversed(r)) for r in g),
    'sym-ud': lambda g: g == tuple(reversed(g)),
    'sym-any': lambda g: g == tuple(tuple(reversed(r)) for r in g) or g == tuple(reversed(g)),
    'n-objects': lambda g: len(objects(g, bg_of(g))),
    'n-objects-8': lambda g: len(objects(g, bg_of(g), diagonal=True)),
    'n-colours': lambda g: len(set(v for r in g for v in r) - {bg_of(g)}),
    'commonest-fg': lambda g: Counter(v for r in g for v in r if v != bg_of(g)).most_common()[0][0],
    'rarest-fg': lambda g: min(Counter(v for r in g for v in r if v != bg_of(g)).items(), key=lambda kv: (kv[1], kv[0]))[0],
    'n-cells': lambda g: sum(v != bg_of(g) for r in g for v in r),
    'connected': lambda g: len(objects(g, bg_of(g), diagonal=True, by_color=False)) == 1,
    'largest-colour': lambda g: (lambda o: g[o[0][0]][o[0][1]])(max(objects(g, bg_of(g)), key=len)),
}


def s_classify(pairs, budget):
    """The output is one of a few small grids (or one colour), chosen by one property of the input: symmetry, number of
    objects or colours, the commonest colour, connectedness. Learned as a table from the demonstrations."""
    outs = [b for _, b in pairs]
    if len(set(outs)) == len(pairs) or len(pairs) < 3:
        if not all(shape(b) == (1, 1) for b in outs):
            return []
    found = []
    for name, f in FEATURES.items():
        table = {}
        try:
            okay = all(table.setdefault(f(a), b) == b for a, b in pairs)
        except Exception:
            continue
        if not okay or len(table) < 2:
            continue

        def predict(q, f=f, table=table):
            k = f(q)
            if k not in table:
                raise Unsupported('unseen')
            return table[k]
        found.append((3.0 + 0.1 * len(table), f'classify-{name}', predict))
    # a one-cell answer that is a colour read off the input
    if all(shape(b) == (1, 1) for b in outs):
        for name, f in FEATURES.items():
            def colour(q, f=f):
                v = f(q)
                if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 9:
                    raise Unsupported('not a colour')
                return ((v,),)
            if _fits(pairs, colour):
                found.append((2.5, f'colourof-{name}', colour))
    return found


ROW_FEATS = {
    'uniform': lambda r, bg: len(set(r)) == 1,
    'uniform-colour': lambda r, bg: r[0] if len(set(r)) == 1 else None,
    'has-fg': lambda r, bg: any(v != bg for v in r),
    'n-fg': lambda r, bg: sum(v != bg for v in r),
    'commonest': lambda r, bg: Counter(r).most_common()[0][0],
}


def s_row_rule(pairs, budget):
    """Each row (or column) of the output is a whole row of one colour chosen by one property of the input row."""
    if any(shape(a) != shape(b) for a, b in pairs):
        return []
    found = []
    for axis in ('row', 'col'):
        tp = [(a, b) if axis == 'row' else (T(a), T(b)) for a, b in pairs]
        if any(len(set(r)) != 1 for _, b in tp for r in b):
            continue
        for name, f in ROW_FEATS.items():
            table = {}
            try:
                okay = all(table.setdefault(f(ra, bg_of(a)), rb[0]) == rb[0] for a, b in tp for ra, rb in zip(a, b))
            except Exception:
                continue
            if not okay or len(table) < 2:
                continue

            def predict(q, f=f, table=table, axis=axis):
                g = q if axis == 'row' else T(q)
                bg = bg_of(q)
                rows = []
                for r in g:
                    k = f(r, bg)
                    if k not in table:
                        raise Unsupported('unseen')
                    rows.append(tuple(table[k] for _ in r))
                got = tuple(rows)
                return got if axis == 'row' else T(got)
            if _fits(pairs, predict):
                found.append((2.8, f'rowrule-{axis}-{name}', predict))
    return found


def s_pad(pairs, budget):
    """The output is the input with a border of width 1 copied from its edge cells (corners background or copied)."""
    out = []
    for corners in ('bg', 'copy'):
        def predict(q, corners=corners):
            h, w = shape(q)
            bg = 0 if corners == 'bg' else None
            rows = [tuple([q[0][0] if bg is None else bg] + list(q[0]) + [q[0][-1] if bg is None else bg])]
            for r in q:
                rows.append(tuple([r[0]] + list(r) + [r[-1]]))
            rows.append(tuple([q[-1][0] if bg is None else bg] + list(q[-1]) + [q[-1][-1] if bg is None else bg]))
            return tuple(rows)
        if _fits(pairs, predict):
            out.append((2.5, f'pad-{corners}', predict))
    return out


def s_marker_recolour(pairs, budget):
    """A lone marker cell gives its colour to the other object(s), and the marker itself is erased (or kept)."""
    if any(shape(a) != shape(b) for a, b in pairs):
        return []
    out = []
    for keep in (False, True):
        def predict(q, keep=keep):
            bg = bg_of(q)
            objs = objects(q, bg, diagonal=True)
            singles = [o for o in objs if len(o) == 1]
            if len(singles) != 1 or len(objs) < 2:
                raise Unsupported('one marker')
            (my, mx), = singles[0]
            k = q[my][mx]
            g = [list(r) for r in q]
            for o in objs:
                if o is singles[0]:
                    continue
                for y, x in o:
                    g[y][x] = k
            if not keep:
                g[my][mx] = bg
            return tuple(tuple(r) for r in g)
        if _fits(pairs, predict):
            out.append((2.6, f'markerrecolour-{"keep" if keep else "erase"}', predict))
    return out


def s_shift(pairs, budget):
    """Everything moves by one fixed offset (cells pushed off the edge are lost), with an optional colour change."""
    if any(shape(a) != shape(b) for a, b in pairs):
        return []
    out = []
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if not (dy or dx):
                continue

            def moved(q, dy=dy, dx=dx):
                h, w = shape(q)
                bg = bg_of(q)
                return tuple(tuple(q[y - dy][x - dx] if 0 <= y - dy < h and 0 <= x - dx < w else bg for x in range(w)) for y in range(h))
            mid = []
            try:
                mid = [(moved(a), b) for a, b in pairs]
            except Exception:
                continue
            mapping = {}
            okay = True
            for m, b in mid:
                for rm, rb in zip(m, b):
                    for u, v in zip(rm, rb):
                        if mapping.setdefault(u, v) != v:
                            okay = False
                            break
                    if not okay:
                        break
                if not okay:
                    break
            if not okay:
                continue

            def predict(q, moved=moved, mapping=mapping):
                return tuple(tuple(mapping.get(v, v) for v in r) for r in moved(q))
            if _fits(pairs, predict):
                out.append((2.4 + 0.1 * (abs(dy) + abs(dx)), f'shift-{dy}-{dx}', predict))
                return out
    return out


def s_corner_crop(pairs, budget):
    """The output (always the same size) is a fixed corner or the centre of the input."""
    shapes = {shape(b) for _, b in pairs}
    if len(shapes) != 1:
        return []
    oh, ow = next(iter(shapes))
    out = []
    for where in ('tl', 'tr', 'bl', 'br', 'centre'):
        def predict(q, where=where):
            h, w = shape(q)
            if h < oh or w < ow or (h, w) == (oh, ow):
                raise Unsupported('size')
            y0 = 0 if where in ('tl', 'tr') else h - oh if where in ('bl', 'br') else (h - oh) // 2
            x0 = 0 if where in ('tl', 'bl') else w - ow if where in ('tr', 'br') else (w - ow) // 2
            return tuple(tuple(q[y][x0:x0 + ow]) for y in range(y0, y0 + oh))
        if _fits(pairs, predict):
            out.append((2.2, f'corner-{where}', predict))
    return out


def s_corner_overlay(pairs, budget):
    """The output (always the same size) overlays the input's four corner regions: a coloured cell in any corner wins."""
    shapes = {shape(b) for _, b in pairs}
    if len(shapes) != 1:
        return []
    oh, ow = next(iter(shapes))

    def predict(q):
        h, w = shape(q)
        if h < oh or w < ow or (h, w) == (oh, ow):
            raise Unsupported('size')
        bg = bg_of(q)
        out = [[bg] * ow for _ in range(oh)]
        for y0, x0 in ((0, 0), (0, w - ow), (h - oh, 0), (h - oh, w - ow)):
            for y in range(oh):
                for x in range(ow):
                    v = q[y0 + y][x0 + x]
                    if v != bg:
                        if out[y][x] not in (bg, v):
                            raise Unsupported('corners clash')
                        out[y][x] = v
        return tuple(map(tuple, out))
    return [(2.6, 'corner-overlay', predict)] if _fits(pairs, predict) else []


def _period_fill(q, hole):
    """Fill cells of colour `hole` from the smallest 2-D period (with offsets) that the other cells agree on."""
    h, w = shape(q)
    for ph in range(1, h + 1):
        for pw in range(1, w + 1):
            if ph * pw >= h * w / 2 + 1:
                continue
            tile = {}
            ok = True
            for y in range(h):
                for x in range(w):
                    v = q[y][x]
                    if v == hole:
                        continue
                    k = (y % ph, x % pw)
                    if tile.setdefault(k, v) != v:
                        ok = False
                        break
                if not ok:
                    break
            if ok and len(tile) == ph * pw:
                return tuple(tuple(q[y][x] if q[y][x] != hole else tile[(y % ph, x % pw)] for x in range(w)) for y in range(h))
    raise Unsupported('no period')


def s_period_hole(pairs, budget):
    """A repeating pattern has a hole of one colour; the output is the pattern with the hole filled, or just the patch that
    belongs in the hole."""
    out = []
    holes = set()
    for a, b in pairs:
        cs = Counter(v for r in a for v in r)
        holes |= {c for c in cs}
    for hole in sorted(holes):
        def full(q, hole=hole):
            if not any(hole in r for r in q):
                raise Unsupported('no hole')
            return _period_fill(q, hole)

        def patch(q, hole=hole):
            filled = full(q)
            cells = [(y, x) for y, r in enumerate(q) for x, v in enumerate(r) if v == hole]
            y0, x0 = min(y for y, _ in cells), min(x for _, x in cells)
            y1, x1 = max(y for y, _ in cells), max(x for _, x in cells)
            return tuple(tuple(filled[y][x0:x1 + 1]) for y in range(y0, y1 + 1))
        if all(shape(a) == shape(b) for a, b in pairs) and _fits(pairs, full):
            out.append((2.8, f'periodhole-full-{hole}', full))
        elif _fits(pairs, patch):
            out.append((2.8, f'periodhole-patch-{hole}', patch))
    return out


def s_count_line(pairs, budget):
    """The output is a single row (or column) with one cell per coloured input cell (or object), in that colour."""
    out = []
    for unit in ('cells', 'objects'):
        for axis in ('row', 'col'):
            def predict(q, unit=unit, axis=axis):
                bg = bg_of(q)
                cs = set(v for r in q for v in r) - {bg}
                if len(cs) != 1:
                    raise Unsupported('one colour')
                c = cs.pop()
                n = sum(v == c for r in q for v in r) if unit == 'cells' else len(objects(q, bg, diagonal=True))
                if n < 1:
                    raise Unsupported('none')
                return ((c,) * n,) if axis == 'row' else tuple((c,) for _ in range(n))
            if _fits(pairs, predict):
                out.append((2.4, f'countline-{unit}-{axis}', predict))
    return out


def s_keep_line(pairs, budget):
    """Only the middle column (or row) of the input is kept; everything else becomes background."""
    if any(shape(a) != shape(b) for a, b in pairs):
        return []
    out = []
    for axis in ('col', 'row'):
        def predict(q, axis=axis):
            h, w = shape(q)
            bg = 0
            if axis == 'col':
                if w % 2 == 0:
                    raise Unsupported('even')
                return tuple(tuple(v if x == w // 2 else bg for x, v in enumerate(r)) for r in q)
            if h % 2 == 0:
                raise Unsupported('even')
            return tuple(r if y == h // 2 else tuple(bg for _ in r) for y, r in enumerate(q))
        if _fits(pairs, predict):
            out.append((2.4, f'keepline-{axis}', predict))
    return out


def s_header_rows(pairs, budget):
    """A header row of colours above a separator line becomes full rows of those colours, repeated down to the bottom."""
    if any(shape(a) != shape(b) for a, b in pairs):
        return []
    out = []
    for axis in ('row', 'col'):
        def predict(q, axis=axis):
            g = q if axis == 'row' else T(q)
            h, w = shape(g)
            if h < 3 or len(set(g[1])) != 1 or g[1][0] == bg_of(g):
                raise Unsupported('no header')
            colours = list(g[0])
            rows = [g[0], g[1]]
            i = 0
            while len(rows) < h:
                rows.append(tuple(colours[i % len(colours)] for _ in range(w)))
                i += 1
            got = tuple(rows)
            return got if axis == 'row' else T(got)
        if _fits(pairs, predict):
            out.append((2.6, f'headerrows-{axis}', predict))
    return out


def s_sort_bars(pairs, budget):
    """Horizontal (or vertical) bars are stacked at the bottom, sorted by length, and aligned to one side."""
    if any(shape(a) != shape(b) for a, b in pairs):
        return []
    out = []
    for axis in ('row', 'col'):
        for align in ('right', 'left'):
            def predict(q, axis=axis, align=align):
                g = q if axis == 'row' else T(q)
                h, w = shape(g)
                bg = bg_of(g)
                bars = []
                for r in g:
                    cells = [v for v in r if v != bg]
                    if not cells:
                        continue
                    if len(set(cells)) != 1:
                        raise Unsupported('mixed row')
                    bars.append((len(cells), cells[0]))
                bars.sort()
                rows = [tuple(bg for _ in range(w)) for _ in range(h - len(bars))]
                for n, c in bars:
                    row = [bg] * (w - n) + [c] * n if align == 'right' else [c] * n + [bg] * (w - n)
                    rows.append(tuple(row))
                got = tuple(rows)
                return got if axis == 'row' else T(got)
            if _fits(pairs, predict):
                out.append((2.6, f'sortbars-{axis}-{align}', predict))
    return out


def s_shape_of_colour(pairs, budget):
    """The output always has the same size and is filled with one colour read off the input (the largest object's colour,
    the commonest or rarest colour, ...)."""
    shapes = {shape(b) for _, b in pairs}
    if len(shapes) != 1 or any(len(set(v for r in b for v in r)) != 1 for _, b in pairs):
        return []
    oh, ow = next(iter(shapes))
    out = []
    for name, f in FEATURES.items():
        def predict(q, f=f):
            v = f(q)
            if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 9:
                raise Unsupported('not a colour')
            return blank(oh, ow, v)
        if _fits(pairs, predict):
            out.append((2.6, f'shapecolour-{name}', predict))
    return out


def s_downscale(pairs, budget):
    """Each k×k block of the input becomes one cell: its majority colour (noise ignored), or any non-background colour."""
    out = []
    for how in ('majority', 'any-fg'):
        def predict(q, how=how):
            (ha, wa), (hb, wb) = shape(pairs[0][0]), shape(pairs[0][1])
            if ha % hb or wa % wb or (ha, wa) == (hb, wb):
                raise Unsupported('ratio')
            ky, kx = ha // hb, wa // wb
            h, w = shape(q)
            if h % ky or w % kx:
                raise Unsupported('size')
            bg = bg_of(q)
            rows = []
            for by in range(0, h, ky):
                row = []
                for bx in range(0, w, kx):
                    cells = [q[y][x] for y in range(by, by + ky) for x in range(bx, bx + kx)]
                    if how == 'majority':
                        cnt = Counter(cells).most_common()
                        if len(cnt) > 1 and cnt[0][1] == cnt[1][1]:
                            raise Unsupported('tie')
                        row.append(cnt[0][0])
                    else:
                        fg = Counter(c for c in cells if c != bg).most_common(1)
                        row.append(fg[0][0] if fg else bg)
                rows.append(tuple(row))
            return tuple(rows)
        if _fits(pairs, predict):
            out.append((2.5, f'downscale-{how}', predict))
    return out


def _colour_box_apply(a, fill):
    bg = bg_of(a)
    out = [list(r) for r in a]
    for c in set(v for r in a for v in r) - {bg}:
        cells = [(y, x) for y, r in enumerate(a) for x, v in enumerate(r) if v == c]
        if len(cells) < 2:
            continue
        ys, xs = [y for y, _ in cells], [x for _, x in cells]
        for y in range(min(ys), max(ys) + 1):
            for x in range(min(xs), max(xs) + 1):
                if a[y][x] == bg:
                    k = c if fill is None else fill
                    if out[y][x] not in (bg, k):
                        raise Unsupported('boxes overlap')
                    out[y][x] = k
    return tuple(map(tuple, out))


def s_colour_box(pairs, budget):
    """All cells of one colour span a box, and the box is filled (with that colour or one fixed colour)."""
    if not _additive(pairs):
        return []
    added = {b[y][x] for a, b in pairs for y in range(len(a)) for x in range(len(a[0])) if a[y][x] != b[y][x]}
    out = []
    for fill in [None] + (sorted(added) if len(added) == 1 else []):
        if _fits(pairs, lambda q, f=fill: _colour_box_apply(q, f)):
            out.append((2.8, 'colourbox', lambda q, f=fill: _colour_box_apply(q, f)))
    return out


def s_interior_rank(pairs, budget):
    """The inside of every solid rectangle (its cells one step in from the edge) is filled with a colour chosen by the
    rectangle's size rank (largest, second, ...) or by its size."""
    if any(shape(a) != shape(b) for a, b in pairs):
        return []
    out = []
    for by in ('rank', 'size'):
        table = {}

        def boxes_of(g):
            bg = bg_of(g)
            got = []
            for o in objects(g, bg):
                b = bbox(o)
                if (b[2] - b[0] + 1) * (b[3] - b[1] + 1) != len(o) or b[2] - b[0] < 2 or b[3] - b[1] < 2:
                    continue
                got.append((len(o), b))
            sizes = sorted({n for n, _ in got}, reverse=True)
            return [((sizes.index(n) if by == 'rank' else n), b) for n, b in got]
        okay = True
        try:
            for a, b in pairs:
                for k, bx in boxes_of(a):
                    v = b[bx[0] + 1][bx[1] + 1]
                    if table.setdefault(k, v) != v:
                        okay = False
        except Exception:
            okay = False
        if not okay or not table:
            continue

        def predict(q, table=table, boxes_of=boxes_of):
            g = [list(r) for r in q]
            for k, bx in boxes_of(q):
                if k not in table:
                    raise Unsupported('unseen')
                for y in range(bx[0] + 1, bx[2]):
                    for x in range(bx[1] + 1, bx[3]):
                        g[y][x] = table[k]
            return tuple(map(tuple, g))
        if _fits(pairs, predict):
            out.append((2.8, f'interior-{by}', predict))
    return out


def s_block_overlay(pairs, budget):
    """The input is k equal parts (halves or quarters, or blocks the size of the output); the output lays them over one
    another in a fixed priority order, or keeps the cells where they all agree, or where exactly one is coloured."""
    from itertools import permutations
    shapes = {shape(b) for _, b in pairs}
    if len(shapes) != 1:
        return []
    oh, ow = next(iter(shapes))
    out = []

    def parts(q):
        h, w = shape(q)
        bs = _blocks(q, oh, ow)
        if len(bs) > 4:
            raise Unsupported('too many')
        return bs
    try:
        k = len(parts(pairs[0][0]))
    except Exception:
        return []
    for order in permutations(range(k)):
        def predict(q, order=order):
            bs = parts(q)
            if len(bs) != k:
                raise Unsupported('parts')
            bg = bg_of(q)
            return tuple(tuple(next((bs[i][y][x] for i in order if bs[i][y][x] != bg), bg) for x in range(ow)) for y in range(oh))
        if _fits(pairs, predict):
            out.append((2.8, 'blockoverlay-' + ''.join(map(str, order)), predict))
            break
    return out


def _object_stamp_apply(a, stamps):
    bg = bg_of(a)
    h, w = shape(a)
    out = [list(r) for r in a]
    for o in objects(a, bg, diagonal=True):
        b = bbox(o)
        key = (a[o[0][0]][o[0][1]], frozenset((y - b[0], x - b[1]) for y, x in o))
        for (dy, dx), k in stamps.get(key, {}).items():
            yy, xx = b[0] + dy, b[1] + dx
            if 0 <= yy < h and 0 <= xx < w and a[yy][xx] == bg:
                if out[yy][xx] not in (bg, k):
                    raise Unsupported('overlap')
                out[yy][xx] = k
    return tuple(map(tuple, out))


def s_object_stamp(pairs, budget):
    """Every object of a given colour and shape gets the same pattern drawn around it, placed relative to its box."""
    if not _additive(pairs):
        return []
    obs = defaultdict(lambda: defaultdict(set))
    for a, b in pairs:
        bg = bg_of(a)
        h, w = shape(a)
        for o in objects(a, bg, diagonal=True):
            bx = bbox(o)
            key = (a[o[0][0]][o[0][1]], frozenset((y - bx[0], x - bx[1]) for y, x in o))
            for y in range(bx[0] - 2, bx[2] + 3):
                for x in range(bx[1] - 2, bx[3] + 3):
                    if 0 <= y < h and 0 <= x < w and a[y][x] == bg:
                        obs[key][(y - bx[0], x - bx[1])].add(b[y][x] if b[y][x] != bg else -1)
    stamps = {}
    for key, offs in obs.items():
        st = {off: next(iter(v)) for off, v in offs.items() if len(v) == 1 and -1 not in v}
        if st:
            stamps[key] = st
    if not stamps:
        return []
    pred = lambda q, s=stamps: _object_stamp_apply(q, s)
    return [(2.6 + 0.02 * sum(len(s) for s in stamps.values()), 'objstamp', pred)] if _fits(pairs, pred) else []


def _corner_interior_apply(a, fill):
    bg = bg_of(a)
    out = [list(r) for r in a]
    for c in set(v for r in a for v in r) - {bg}:
        cells = [(y, x) for y, r in enumerate(a) for x, v in enumerate(r) if v == c]
        if len(cells) < 2:
            continue
        ys, xs = [y for y, _ in cells], [x for _, x in cells]
        groups = [cells]
        for y in range(min(ys) + 1, max(ys)):
            for x in range(min(xs) + 1, max(xs)):
                if a[y][x] == bg:
                    out[y][x] = fill
    return tuple(map(tuple, out))


def s_corner_interior(pairs, budget):
    """The cells strictly inside the box spanned by cells of one colour are filled with one fixed colour."""
    if not _additive(pairs):
        return []
    added = {b[y][x] for a, b in pairs for y in range(len(a)) for x in range(len(a[0])) if a[y][x] != b[y][x]}
    if len(added) != 1:
        return []
    k = added.pop()
    pred = lambda q: _corner_interior_apply(q, k)
    return [(2.8, 'cornerinterior', pred)] if _fits(pairs, pred) else []


def s_singletons(pairs, budget):
    """Isolated single cells (no neighbour of their colour, 4- or 8-connected) are recoloured to one colour, or erased."""
    if any(shape(a) != shape(b) for a, b in pairs):
        return []
    out = []
    targets = {b[y][x] for a, b in pairs for y in range(len(a)) for x in range(len(a[0])) if a[y][x] != b[y][x]}
    if len(targets) != 1:
        return []
    k = targets.pop()
    for diagonal in (False, True):
        def predict(q, diagonal=diagonal):
            bg = bg_of(q)
            g = [list(r) for r in q]
            for o in objects(q, bg, diagonal=diagonal):
                if len(o) == 1:
                    y, x = o[0]
                    g[y][x] = k
            return tuple(map(tuple, g))
        if _fits(pairs, predict):
            out.append((2.5, f'singletons-{"8" if diagonal else "4"}', predict))
            break
    return out


def s_rank_recolour(pairs, budget):
    """The largest object gets one colour, the smallest another, and all other objects a third (or are erased)."""
    if any(shape(a) != shape(b) for a, b in pairs):
        return []
    out = []
    for diagonal in (False, True):
        table = {}
        okay = True
        for a, b in pairs:
            bg = bg_of(a)
            objs = objects(a, bg, diagonal=diagonal, by_color=False)
            if len(objs) < 3:
                okay = False
                break
            sizes = sorted(len(o) for o in objs)
            if sizes[-1] == sizes[-2] or sizes[0] == sizes[1]:
                okay = False
                break
            for o in objs:
                role = 'largest' if len(o) == sizes[-1] else 'smallest' if len(o) == sizes[0] else 'other'
                vals = {b[y][x] for y, x in o}
                if len(vals) != 1 or table.setdefault(role, vals.pop()) != b[o[0][0]][o[0][1]]:
                    okay = False
                    break
            if not okay:
                break
        if not okay or len(table) < 2:
            continue

        def predict(q, table=table, diagonal=diagonal):
            bg = bg_of(q)
            objs = objects(q, bg, diagonal=diagonal, by_color=False)
            sizes = sorted(len(o) for o in objs)
            if len(objs) < 3 or sizes[-1] == sizes[-2] or sizes[0] == sizes[1]:
                raise Unsupported('ranks')
            g = [list(r) for r in q]
            for o in objs:
                role = 'largest' if len(o) == sizes[-1] else 'smallest' if len(o) == sizes[0] else 'other'
                for y, x in o:
                    g[y][x] = table.get(role, q[y][x])
            return tuple(map(tuple, g))
        if _fits(pairs, predict):
            out.append((2.7, 'rankrecolour', predict))
            break
    return out


def s_alt_rays(pairs, budget):
    """Every coloured cell sends a ray in one direction that alternates its own colour with one fixed colour."""
    if not _additive(pairs):
        return []
    added = Counter(b[y][x] for a, b in pairs for y in range(len(a)) for x in range(len(a[0])) if a[y][x] != b[y][x])
    out = []
    for k in added:
        for d in ('right', 'left', 'down', 'up'):
            def predict(q, k=k, d=d):
                bg = bg_of(q)
                h, w = shape(q)
                dy, dx = DIRS[d]
                g = [list(r) for r in q]
                for y in range(h):
                    for x in range(w):
                        c = q[y][x]
                        if c == bg or c == k:
                            continue
                        i, yy, xx = 1, y + dy, x + dx
                        while 0 <= yy < h and 0 <= xx < w and q[yy][xx] == bg:
                            g[yy][xx] = k if i % 2 else c
                            i += 1; yy += dy; xx += dx
                return tuple(map(tuple, g))
            if _fits(pairs, predict):
                out.append((2.6, f'altrays-{d}', predict))
                return out
    return out


SOLVERS = [s_native, s_stamp, s_span, s_nearest_recolour, s_lookup, s_bbox_fill, s_role_swap, s_count_bar, s_union,
           s_object_stamp, s_corner_interior, s_singletons, s_rank_recolour, s_alt_rays,
           s_shape_of_colour, s_downscale, s_colour_box, s_interior_rank, s_block_overlay,
           s_corner_crop, s_corner_overlay, s_period_hole, s_count_line, s_keep_line, s_header_rows, s_sort_bars,
           s_fill_one, s_scale_by, s_repeat_unit, s_pick_block, s_classify, s_row_rule, s_pad, s_marker_recolour, s_shift, s_program_search, s_split_combine, s_tiling, s_self_tile, s_mirror_concat, s_crop_object, s_recolour_objects,
           s_lines, s_constant_size_count, s_denoise, s_fill_enclosed, s_symmetry_complete, s_local_rule, s_periodic, s_object_gravity,
           s_partition, s_crop_frame, s_two_stage]
def _load_prior():
    """Cost adjustment per solver family, -0.5*log2(precision) on clean mdlARC practice puzzles (models/cael-arc-priors-v1)."""
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'models/cael-arc-priors-v1/arc_priors.json'
    try:
        return json.loads(path.read_text(encoding='utf-8'))['prior']
    except Exception:
        return {}


PRIOR = _load_prior()


def family(name):
    return name.split(':')[0].split('-')[0]


def candidates(pairs, query, seconds):
    """[(cost, solver, prediction)] from every solver whose hypothesis reproduces all pairs."""
    found = []
    started = time.monotonic()
    for solver in SOLVERS:
        left = seconds - (time.monotonic() - started)
        if left <= 0:
            break
        key = (hash(tuple(pairs)), solver.__name__)
        if key in FIT_CACHE:                 # the same task's other test inputs reuse the rules already learned
            fits = FIT_CACHE[key]
        else:
            try:
                fits = solver(pairs, min(left, seconds * 0.5))
            except Exception:
                fits = []
            if len(FIT_CACHE) > 400:
                FIT_CACHE.clear()
            FIT_CACHE[key] = fits
        for cost, name, predict in fits:
            try:
                p = predict(query)
            except Exception:
                continue
            if ok_grid(p) and all(len(r) == len(p[0]) for r in p):
                found.append((cost + PRIOR.get(family(name), 0.3), name, p))
                ORIGIN.setdefault(id(found), {})[p] = (solver, name)
    return found


FIT_CACHE = {}     # (hash of the demonstrations, solver) -> fitted rules
ORIGIN = {}        # id(candidate list) -> {prediction: (solver, name)}, read once by attempts()


def held_out(solver, name, pairs, budget):
    """Leave-one-out self-check: the rule is learned again without one demonstration and must predict that one. The share
    of demonstrations predicted this way, or None when there are too few to hold one out."""
    if len(pairs) < 3:
        return None
    started = time.monotonic()
    right = 0
    for i in range(len(pairs)):
        if time.monotonic() - started > budget:
            return None
        rest = pairs[:i] + pairs[i + 1:]
        try:
            fits = [p for _, n, p in solver(rest, budget / len(pairs)) if n == name]
            right += bool(fits) and fits[0](pairs[i][0]) == pairs[i][1]
        except Exception:
            continue
    return right / len(pairs)


def attempts(train, query, seconds=8.0, views=(0, 1, 2, 3, 4, 5, 6, 7)):
    """Up to two different predicted grids (lists), best first. Each view solves the task under one symmetry; answers are
    mapped back and pooled: a prediction's score adds 1 / (1 + cost) for every view and solver that produced it."""
    pairs = [(grid(p['input']), grid(p['output'])) for p in train]
    q = grid(query)
    score = defaultdict(float)
    best_cost = {}
    makers = {}
    started = time.monotonic()
    # The general learners (a compositional program search and per-cell rule trees) see the task once; they handle
    # symmetry themselves, so each of their answers counts as if every view had found it.
    general = []
    if os.environ.get('CAEL_ARC_GENERAL', '1') != '0':
        from . import arc_cellrules, arc_dsl
        ins, outs = [p['input'] for p in train], [p['output'] for p in train]
        for maker, run in (('cell', lambda: arc_cellrules.solve(list(zip(ins, outs)), [query])),
                           ('dsl', lambda: arc_dsl.search(ins, outs, [query], seconds=min(12.0, seconds * 0.4)))):
            try:
                for cost, name, preds in run()[:4]:
                    general.append((cost, maker + ':' + name, grid(preds[0])))
            except Exception:
                pass
        seconds = max(1.0, seconds - (time.monotonic() - started))
        started = time.monotonic()
    per_view = seconds / max(1, len(views))
    for k in views:
        if time.monotonic() - started > seconds:
            break
        vp = [(dihedral(a, k), dihedral(b, k)) for a, b in pairs]
        vq = dihedral(q, k)
        view = {}
        found = candidates(vp, vq, per_view if k else seconds * 0.4)
        origin = ORIGIN.pop(id(found), {})
        for cost, name, p in found:
            back = undihedral(p, k)
            if back == q:
                continue                     # copying the test input is never an answer
            view[back] = max(view.get(back, 0.0), 1.0 / (1.0 + cost))      # one vote per view: its best description
            best_cost[back] = min(best_cost.get(back, 99), cost)
            if k == 0 and p in origin:
                makers.setdefault(back, origin[p])
        for back, v in view.items():
            score[back] += v
    for cost, name, p in general:     # several learners agreeing on one answer each add their weight
        if p == q:
            continue
        score[p] += len(views) / (1.0 + cost) * (1.0 if len(train) >= 3 else 0.5)   # unverified on 2 pairs
        best_cost[p] = min(best_cost.get(p, 99), cost)
    ranked = sorted(score, key=lambda g: (-score[g], best_cost[g]))
    # Think before answering: when several different answers compete, each of the leading ones is checked by holding out
    # one demonstration at a time; a rule that predicts the held-out demonstrations generalises, one that only memorised
    # them does not. The check reorders the leaders; it never adds an answer.
    if len(ranked) > 1 and os.environ.get('CAEL_ARC_THINK', '1') != '0':
        for g in ranked[:4]:
            left = seconds * 0.95 - (time.monotonic() - started)   # the whole call stays inside its budget
            if left <= 0.3 or g not in makers:
                continue
            solver, name = makers[g]
            share = held_out(solver, name, pairs, min(left, seconds * 0.15))
            if share is not None:
                score[g] += 1.0 * share
        ranked = sorted(score, key=lambda g: (-score[g], best_cost[g]))
    return [[list(r) for r in g] for g in ranked[:2]]
