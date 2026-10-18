"""Faces for head-and-shoulders portraits: eye finding and part compositing (authored; no learned detector).

The people portraits in the training set are frontal and centred. In the blurred brightness image, the eyes
are the darkest pair of small blobs in the face band, roughly level and mirror-placed around the face
centre. Detections far from the consensus of all portraits are rejected.

A new face is composited from real, eye-aligned parts of different people: hair, outline and clothes from
one, the eye region from a second, nose and mouth from a third. The joins are fused in the gradient domain
(hybrid.seam_fuse), so every part is a real photographic region and the face is a new combination.
"""
import numpy as np
from scipy.ndimage import gaussian_filter, minimum_filter


def find_eyes(image, mask=None):
    """image: float HxWx3 in [0,1] (or uint8). Returns ((x_left, y_left), (x_right, y_right)) or None."""
    img = image.astype(np.float32)
    if img.max() > 1.5:
        img = img / 255
    size = img.shape[0]
    grey = img @ np.array([0.299, 0.587, 0.114], np.float32)
    if mask is not None and mask.mean() > 0.05:
        top = np.flatnonzero(mask.max(1) > 0.5)[0]
        probe = min(size - 1, top + int(0.15 * size))
        cols = np.flatnonzero(mask[probe] > 0.5)
        centre_x = cols.mean() if len(cols) else size / 2
    else:
        centre_x = size / 2
    # Head-and-shoulders framing puts the eyes in a fixed band of the picture.
    y0, y1 = int(0.30 * size), int(0.52 * size)
    x0, x1 = int(max(0, centre_x - 0.30 * size)), int(min(size, centre_x + 0.30 * size))
    smooth = gaussian_filter(grey, size / 110)
    region = smooth[y0:y1, x0:x1]
    surround = gaussian_filter(grey, size / 25)[y0:y1, x0:x1]
    depth = surround - region                       # an eye is darker than the skin around it
    minima = (region == minimum_filter(region, size=max(3, size // 32))) & (depth > 0.02)
    ys, xs = np.nonzero(minima)
    if len(ys) < 2:
        return None
    order = np.argsort(-depth[ys, xs])[:12]
    points = [(xs[i] + x0, ys[i] + y0, depth[ys[i], xs[i]]) for i in order]
    best, best_score = None, -1e9
    for i in range(len(points)):
        for j in range(len(points)):
            (ax, ay, ad), (bx, by, bd) = points[i], points[j]
            if ax >= bx:
                continue
            gap = (bx - ax) / size
            if not 0.09 <= gap <= 0.24 or abs(ay - by) > 0.04 * size:
                continue
            symmetry = abs((ax + bx) / 2 - centre_x) / size
            score = ad + bd - 2.0 * symmetry - 3.0 * abs(ay - by) / size
            if score > best_score:
                best, best_score = ((float(ax), float(ay)), (float(bx), float(by))), score
    return best


def consensus(found, size):
    """Keep detections near the typical eye height and spacing; returns (kept dict, canonical eye pair)."""
    pairs = {i: e for i, e in found.items() if e is not None}
    if len(pairs) < 4:
        return {}, None
    ys = np.array([(e[0][1] + e[1][1]) / 2 for e in pairs.values()])
    gaps = np.array([e[1][0] - e[0][0] for e in pairs.values()])
    xs = np.array([(e[0][0] + e[1][0]) / 2 for e in pairs.values()])
    my, mg, mx = np.median(ys), np.median(gaps), np.median(xs)
    kept = {i: e for i, e in pairs.items()
            if abs((e[0][1] + e[1][1]) / 2 - my) < 0.05 * size and abs((e[1][0] - e[0][0]) - mg) < 0.3 * mg
            and abs((e[0][0] + e[1][0]) / 2 - mx) < 0.08 * size}
    canonical = ((mx - mg / 2, my), (mx + mg / 2, my))
    return kept, canonical


def eye_transform(eyes, target, size):
    """(scale, dx, dy, mirror=False) for hybrid.warp that moves these eyes onto the target eye positions."""
    (lx, ly), (rx, ry) = eyes
    (tlx, tly), (trx, try_) = target
    scale = float(np.clip((trx - tlx) / max(rx - lx, 1e-3), 0.7, 1.4))
    centre = (size - 1) / 2
    mx, my = (lx + rx) / 2, (ly + ry) / 2
    tx, ty = (tlx + trx) / 2, (tly + try_) / 2
    dx = (tx - (centre + scale * (mx - centre))) / size
    dy = (ty - (centre + scale * (my - centre))) / size
    return (scale, dx, dy, False)


def part_labels(canonical, size):
    """Region map in the canonical frame: 0 = base (hair, outline, clothes), 1 = eye region, 2 = nose and mouth."""
    (lx, ly), (rx, ry) = canonical
    gap = rx - lx
    cx, ey = (lx + rx) / 2, (ly + ry) / 2
    yy, xx = np.mgrid[:size, :size].astype(np.float32)
    labels = np.zeros((size, size), np.int64)
    eyes = (np.abs(yy - ey) < 0.42 * gap) & (np.abs(xx - cx) < 1.05 * gap)
    mouth = (yy >= ey + 0.42 * gap) & (yy < ey + 1.55 * gap) & (np.abs(xx - cx) < 0.62 * gap)
    labels[eyes] = 1
    labels[mouth] = 2
    return labels


def composite(parts, labels, weight=0.002):
    """parts: three float images aligned to the base person (base, eyes, mouth). Poisson image editing: inside
    each region the gradients of that region's person; across region borders the base person's own gradients,
    so a transplanted part takes on the surrounding skin tone and lighting; colours weakly anchored to the base.
    """
    from .hybrid import seam_fuse
    sharp = np.where((labels == 0)[..., None], parts[0], np.where((labels == 1)[..., None], parts[1], parts[2]))
    return seam_fuse(parts[0], sharp, labels, weight, across=parts[0])
