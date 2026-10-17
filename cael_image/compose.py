"""Classic image operations that carry out a picture request: cut-out, recolour, place on a scene.

No neural networks: the object mask is a flood fill of the plain background from
the image border, recolouring rotates hue in HSV while keeping the shading, and
scenes are composed by alpha-blending scaled cut-outs.
"""
import numpy as np
from PIL import Image, ImageFilter

from .request import COLOURS


def smooth_background(pixels):
    """Background estimate interpolated from all four borders (a Coons patch), so gradients are allowed."""
    size_y, size_x = pixels.shape[:2]
    small = np.asarray(Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5)), np.float32)
    top, bottom, left, right = small[0], small[-1], small[:, 0], small[:, -1]
    v = np.linspace(0, 1, size_y)[:, None, None]
    u = np.linspace(0, 1, size_x)[None, :, None]
    ruled_y = (1 - v) * top[None] + v * bottom[None]
    ruled_x = (1 - u) * left[:, None] + u * right[:, None]
    corners = ((1 - u) * (1 - v) * small[0, 0] + u * (1 - v) * small[0, -1] + (1 - u) * v * small[-1, 0] + u * v * small[-1, -1])
    return ruled_y + ruled_x - corners


def flood(seed_mask, allowed):
    """Grow seed_mask through allowed pixels (4-neighbour), vectorised."""
    filled = seed_mask & allowed
    for _ in range(allowed.shape[0] * 3):
        grown = filled.copy()
        grown[1:] |= filled[:-1]
        grown[:-1] |= filled[1:]
        grown[:, 1:] |= filled[:, :-1]
        grown[:, :-1] |= filled[:, 1:]
        grown &= allowed
        if (grown == filled).all():
            break
        filled = grown
    return filled


def object_mask(image, tolerance=34.0):
    """Foreground mask (float 0..1) of one solid object on a plain or gradient background, or None.

    1. background = smooth surface interpolated from the borders;
    2. foreground candidates = pixels clearly different from it;
    3. keep the largest connected region and fill its holes;
    4. reject masks that are tiny, huge, or touch much of the border (scenes, crops).
    """
    pixels = image.astype(np.float32)
    difference = np.sqrt(((pixels - smooth_background(pixels)) ** 2).sum(2))
    candidate = difference > tolerance
    if candidate.mean() < 0.02:
        return None
    # Largest connected region: repeatedly grow from the strongest remaining pixel.
    remaining, best = candidate.copy(), None
    for _ in range(6):
        if not remaining.any():
            break
        seed = np.zeros_like(remaining)
        seed[np.unravel_index(np.argmax(np.where(remaining, difference, -1)), remaining.shape)] = True
        region = flood(seed, remaining)
        if best is None or region.sum() > best.sum():
            best = region
        remaining &= ~region
        if best.sum() > remaining.sum():
            break
    # Fill holes: everything not reachable from the border without crossing the object.
    border = np.zeros_like(best)
    border[0], border[-1], border[:, 0], border[:, -1] = True, True, True, True
    outside = flood(border & ~best, ~best)
    mask = ~outside
    share = mask.mean()
    edge = np.concatenate([mask[0], mask[-1], mask[:, 0], mask[:, -1]]).mean()
    if not 0.05 <= share <= 0.8 or edge > 0.25:
        return None
    soft = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0)), np.float32) / 255
    return soft


def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    v = rgb.max(-1)
    c = v - rgb.min(-1)
    s = np.where(v > 0, c / np.maximum(v, 1e-6), 0)
    safe = np.maximum(c, 1e-6)
    h = np.where(v == r, ((g - b) / safe) % 6, np.where(v == g, (b - r) / safe + 2, (r - g) / safe + 4)) / 6
    return np.stack([np.where(c > 0, h, 0), s, v], -1)


def hsv_to_rgb(hsv):
    h, s, v = hsv[..., 0] * 6, hsv[..., 1], hsv[..., 2]
    i = np.floor(h).astype(int) % 6
    f = h - np.floor(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    choices = [np.stack(x, -1) for x in ((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))]
    out = np.zeros(hsv.shape, np.float32)
    for k in range(6):
        out = np.where((i == k)[..., None], choices[k], out)
    return out


def recolour(image, mask, colour):
    """Give the masked object the named colour, keeping its light and shade."""
    hue, kind = COLOURS[colour]
    hsv = rgb_to_hsv(image.astype(np.float32) / 255)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    if kind == 'black':
        new = np.stack([h, s * 0.3, 0.08 + v * 0.3], -1)
    elif kind == 'white':
        new = np.stack([h, s * 0.08, 0.65 + v * 0.35], -1)
    elif kind == 'gray':
        new = np.stack([h, s * 0.06, 0.25 + v * 0.55], -1)
    else:
        saturation = np.clip(np.maximum(s, 0.55), 0, 1)
        value = v * (0.6 if kind == 'dark' else 1.0)
        if kind == 'light':
            saturation, value = saturation * 0.45, 0.55 + v * 0.45
        new = np.stack([np.full_like(h, hue), saturation, np.clip(value, 0, 1)], -1)
    coloured = hsv_to_rgb(new) * 255
    m = mask[..., None]
    return np.clip(image * (1 - m) + coloured * m, 0, 255).astype(np.uint8)


def place(scene, objects, masks):
    """Alpha-blend one to three cut-outs side by side onto a scene, standing on its lower part."""
    canvas = scene.astype(np.float32).copy()
    size = canvas.shape[0]
    count = len(objects)
    scale = {1: 0.68, 2: 0.5, 3: 0.4}[count]
    width = int(size * scale)
    for k, (obj, mask) in enumerate(zip(objects, masks)):
        small = np.asarray(Image.fromarray(obj).resize((width, width), Image.Resampling.LANCZOS), np.float32)
        alpha = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).resize((width, width), Image.Resampling.LANCZOS), np.float32)[..., None] / 255
        centre = int(size * (k + 1) / (count + 1))
        x0 = int(np.clip(centre - width // 2, 0, size - width))
        y0 = size - width - int(size * 0.04)
        region = canvas[y0:y0 + width, x0:x0 + width]
        canvas[y0:y0 + width, x0:x0 + width] = region * (1 - alpha) + small * alpha
    return np.clip(canvas, 0, 255).astype(np.uint8)


def plain_scene(objects, size):
    """A plain background in the median border colour of the first object."""
    border = np.concatenate([objects[0][0], objects[0][-1], objects[0][:, 0], objects[0][:, -1]])
    return np.tile(np.median(border, 0).astype(np.uint8), (size, size, 1))
