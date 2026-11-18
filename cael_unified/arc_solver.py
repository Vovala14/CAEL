"""ARC-style grid tasks: many small checked solvers, ranked by description length, two attempts (non-neural).

Ideas taken (not code) from the Looped mdlARC write-up (mvakde.github.io/blog/looped-mdlarc), without its network:
- minimum description length: among hypotheses that reproduce every demonstration exactly, the shortest wins;
- augment and vote: the task is also solved under the 8 grid symmetries, each answer mapped back, equal answers pooled;
- two attempts: the best two different answers are returned instead of refusing when hypotheses disagree.

Every candidate reproduces every demonstration exactly before it may predict. Nothing here knows task ids or answers.
"""
from collections import Counter, defaultdict
import json
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
             'unique-shape', 'top-left', 'bottom-right', 'densest', 'sparsest']


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
        for solver in (s_local_rule, s_recolour_objects):
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


SOLVERS = [s_native, s_program_search, s_split_combine, s_tiling, s_self_tile, s_mirror_concat, s_crop_object, s_recolour_objects,
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
        try:
            fits = solver(pairs, min(left, seconds * 0.5))
        except Exception:
            continue
        for cost, name, predict in fits:
            try:
                p = predict(query)
            except Exception:
                continue
            if ok_grid(p) and all(len(r) == len(p[0]) for r in p):
                found.append((cost + PRIOR.get(family(name), 0.3), name, p))
    return found


def attempts(train, query, seconds=8.0, views=(0, 1, 2, 3, 4, 5, 6, 7)):
    """Up to two different predicted grids (lists), best first. Each view solves the task under one symmetry; answers are
    mapped back and pooled: a prediction's score adds 1 / (1 + cost) for every view and solver that produced it."""
    pairs = [(grid(p['input']), grid(p['output'])) for p in train]
    q = grid(query)
    score = defaultdict(float)
    best_cost = {}
    started = time.monotonic()
    per_view = seconds / max(1, len(views))
    for k in views:
        if time.monotonic() - started > seconds:
            break
        vp = [(dihedral(a, k), dihedral(b, k)) for a, b in pairs]
        vq = dihedral(q, k)
        view = {}
        for cost, name, p in candidates(vp, vq, per_view if k else seconds * 0.4):
            back = undihedral(p, k)
            if back == q:
                continue                     # copying the test input is never an answer
            view[back] = max(view.get(back, 0.0), 1.0 / (1.0 + cost))      # one vote per view: its best description
            best_cost[back] = min(best_cost.get(back, 99), cost)
        for back, v in view.items():
            score[back] += v
    ranked = sorted(score, key=lambda g: (-score[g], best_cost[g]))
    return [[list(r) for r in g] for g in ranked[:2]]
