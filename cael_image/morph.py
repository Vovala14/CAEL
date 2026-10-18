"""Landmark-based face morphing for head-and-shoulders portraits (classic, non-neural).

Each training portrait carries 68 facial landmarks (found offline). A new face:
1. picks a few similar-looking people;
2. sets a new face shape: a weighted mix of their landmark shapes;
3. warps every person onto that shape triangle by triangle (piecewise-affine, Delaunay triangulation over
   the landmarks plus border and forehead points);
4. blends the faces inside the face outline with the mixing weights; hair, clothes and background come from
   one person, warped to the new shape, with a soft transition so hair does not ghost.
The result is a face nobody in the training set has, with every feature in its place.
"""
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from scipy.spatial import Delaunay

JAW = list(range(0, 17))
BROWS = list(range(17, 27))


def anchor_points(points, size):
    """Landmarks + forehead points (brows lifted) + image border points, so the whole picture is triangulated."""
    p = np.asarray(points, np.float32)
    face_height = p[8, 1] - p[BROWS, 1].mean()
    forehead = p[BROWS].copy()
    forehead[:, 1] -= 0.55 * face_height
    edge = size - 1
    border = np.array([[0, 0], [edge / 2, 0], [edge, 0], [edge, edge / 2], [edge, edge], [edge / 2, edge], [0, edge], [0, edge / 2]],
                      np.float32)
    return np.concatenate([p, np.clip(forehead, 0, edge), border])


def piecewise_warp(image, source, target, triangles):
    """Warp image so source points land on target points (affine per triangle). image float HxWx3."""
    size = image.shape[0]
    out = np.zeros_like(image)
    yy, xx = np.mgrid[:size, :size]
    grid = np.stack([xx.ravel(), yy.ravel()], 1).astype(np.float32)
    # Which target triangle each output pixel is in, then that triangle's inverse affine map to the source.
    tri = Delaunay(target)
    owner = tri.find_simplex(grid)
    sx = np.zeros(len(grid), np.float32)
    sy = np.zeros(len(grid), np.float32)
    for t, simplex in enumerate(tri.simplices):
        inside = owner == t
        if not inside.any():
            continue
        dst = target[simplex]
        src = source[simplex]
        # Affine A with [x, y, 1] @ A = src, solved from the three corners.
        A = np.linalg.solve(np.c_[dst, np.ones(3)], src)
        mapped = np.c_[grid[inside], np.ones(inside.sum())] @ A
        sx[inside], sy[inside] = mapped[:, 0], mapped[:, 1]
    outside = owner < 0
    sx[outside], sy[outside] = grid[outside, 0], grid[outside, 1]
    from scipy.ndimage import map_coordinates
    for c in range(image.shape[2]):
        out[..., c] = map_coordinates(image[..., c], [sy.reshape(size, size), sx.reshape(size, size)], order=1, mode='nearest')
    return out


def face_mask(points, size, blur=None):
    """Soft mask of the face: jaw line and the forehead points, filled; feathered edges."""
    from PIL import ImageDraw
    p = np.asarray(points, np.float32)
    outline = np.concatenate([p[JAW], p[BROWS][::-1] - [0, 0.04 * size]])   # jaw, then just above the brows (no hair)
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).polygon([tuple(q) for q in outline], fill=255)
    m = np.asarray(mask, np.float32) / 255
    return gaussian_filter(m, blur or size / 40)


def morph(images, landmarks, weights, base=0, surround=None):
    """images: float HxWx3 list; landmarks: 68x2 each; weights: mixing weights (sum 1). Returns the new face.

    surround: weights for hair, clothes and background (default: the base person only). Mixing in a second
    person there makes the whole picture new, at the cost of slight softness in the hair.
    """
    size = images[0].shape[0]
    anchors = [anchor_points(p, size) for p in landmarks]
    target = sum(w * a for w, a in zip(weights, anchors))
    warped = [piecewise_warp(im, a, target, None) for im, a in zip(images, anchors)]
    blended = sum(w * im for w, im in zip(weights, warped))
    outside = warped[base] if surround is None else sum(w * im for w, im in zip(surround, warped))
    m = face_mask(target, size)[..., None]
    # Ghosting: how much the warped faces disagree inside the face (high = double features after blending).
    spread = sum(w * (im - blended) ** 2 for w, im in zip(weights, warped)).mean(2)
    ghost = float((spread * m[..., 0]).sum() / max(float(m.sum()), 1.0))
    return np.clip(outside * (1 - m) + blended * m, 0, 1), target, ghost
