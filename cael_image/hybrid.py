"""CAEL hybrid image model: statistical layout + non-parametric patch synthesis (no neural networks).

Generation for a topic, given a seed:

1. Layout. A per-topic PCA model of 16x16 training images is sampled. This
   gives a new, blurry arrangement of shape and colour that no training image
   has exactly.
2. Detail. Coarse-to-fine (32 then 64 px) texture optimisation in the style of
   Kwatra et al. (2005): every overlapping 8x8 patch of the current image is
   replaced by the most similar real patch from nearby positions in the topic's
   training images, and the overlapping choices are blended. A usage penalty
   stops one training image from supplying most of the picture, so outputs are
   recombinations of many sources rather than copies. Every result records how
   much its most-used source contributed.

The training images come from a local Stable Diffusion 1.5 teacher
(CreativeML OpenRAIL-M); the generator itself is PCA plus nearest-patch search.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

SIZE = 64
LAYOUT = 16
PATCH = 8
STRIDE = 4


def resize(array, size):
    """float [0,1] HxWx3 -> size x size (bicubic)."""
    image = Image.fromarray(np.clip(array * 255 + 0.5, 0, 255).astype(np.uint8))
    return np.asarray(image.resize((size, size), Image.Resampling.BICUBIC), dtype=np.float32) / 255


def blur(images, radius=1.2):
    """Gaussian blur of a float [0,1] image stack."""
    out = [np.asarray(Image.fromarray(np.clip(im * 255 + 0.5, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius)),
                      dtype=np.float32) / 255 for im in images]
    return np.stack(out)


def fit(images_by_topic, aliases, styles_by_topic=None, components=12):
    """images_by_topic: {topic: uint8 array N x S x S x 3} (S = 64 or 128). Returns arrays for np.savez."""
    topics = sorted(images_by_topic)
    size = int(next(iter(images_by_topic.values())).shape[1])
    arrays, meta = {}, dict(topics=topics, aliases=aliases, size=size, layout=LAYOUT, counts={})
    for topic in topics:
        images = images_by_topic[topic]
        small = np.stack([resize(im.astype(np.float32) / 255, LAYOUT) for im in images]).reshape(len(images), -1)
        mean = small.mean(0)
        centred = small - mean
        _, singular, vt = np.linalg.svd(centred, full_matrices=False)
        k = max(1, min(components, len(images) - 1))
        arrays[f'{topic}/images'] = images
        arrays[f'{topic}/styles'] = np.asarray((styles_by_topic or {}).get(topic, np.full(len(images), -1)), np.int8)
        # Object masks come from the clean training renders (plain backgrounds), never from generated
        # pictures; 255 everywhere marks an image with no separable object (a scene).
        from .compose import object_mask
        masks = [object_mask(im) for im in images]
        arrays[f'{topic}/masks'] = np.stack([(m * 255).astype(np.uint8) if m is not None else np.full(im.shape[:2], 255, np.uint8)
                                             for m, im in zip(masks, images)])
        arrays[f'{topic}/has_mask'] = np.array([m is not None for m in masks])
        arrays[f'{topic}/mean'] = mean.astype(np.float32)
        arrays[f'{topic}/components'] = vt[:k].astype(np.float32)
        arrays[f'{topic}/scales'] = (singular[:k] / np.sqrt(max(1, len(images) - 1))).astype(np.float32)
        meta['counts'][topic] = int(len(images))
    arrays['meta'] = np.frombuffer(json.dumps(meta).encode('utf-8'), dtype=np.uint8)
    return arrays


class HybridModel:
    def __init__(self, path):
        self.path = Path(path)
        self.data = np.load(self.path, allow_pickle=False)
        self.meta = json.loads(bytes(self.data['meta']).decode('utf-8'))
        self.topics = self.meta['topics']
        self.size = int(self.meta.get('size', SIZE))
        self.levels = [s for s in (32, 64, 128) if s <= self.size]   # coarse-to-fine synthesis sizes
        self._pyramids = {}

    def pyramid(self, topic):
        if topic not in self._pyramids:
            images = self.data[f'{topic}/images'].astype(np.float32) / 255
            self._pyramids[topic] = {s: images if s == self.size else np.stack([resize(im, s) for im in images]) for s in self.levels}
            # Blurred copies are what a (still blurry) work-in-progress image is matched against;
            # the sharp originals are what gets pasted. Matching sharp patches to a blurry query
            # would always pick flat, featureless patches.
            for s in self.levels:
                self._pyramids[topic][('blur', s)] = blur(self._pyramids[topic][s])
            if f'{topic}/masks' in self.data.files:
                masks = self.data[f'{topic}/masks'].astype(np.float32) / 255
                self._pyramids[topic]['mask'] = masks[..., None]
        return self._pyramids[topic]

    def layout(self, topic, rng, temperature=0.9):
        mean = self.data[f'{topic}/mean']
        components = self.data[f'{topic}/components']
        scales = self.data[f'{topic}/scales']
        z = rng.standard_normal(len(scales)).astype(np.float32) * scales * temperature
        return np.clip(mean + z @ components, 0, 1).reshape(LAYOUT, LAYOUT, 3)

    def styles(self, topic):
        key = f'{topic}/styles'
        return self.data[key] if key in self.data.files else np.full(len(self.pyramid(topic)[self.size]), -1, np.int8)

    def donors(self, topic, layout, count, style=None):
        """Training images whose 16x16 layout is closest to the sampled layout (of the requested style, if any)."""
        small = self.small(topic)
        distance = ((small - layout.reshape(1, -1)) ** 2).mean(1)
        if style is not None:
            matching = self.styles(topic) == style
            if matching.sum() >= max(2, count):
                distance = np.where(matching, distance, np.inf)
        return np.argsort(distance)[:count]

    def small(self, topic):
        key = ('small', topic)
        if key not in self._pyramids:
            images = self.pyramid(topic)[self.size]
            self._pyramids[key] = np.stack([resize(im, LAYOUT) for im in images]).reshape(len(images), -1)
        return self._pyramids[key]

    def generate(self, topic, n=2, seed=0, iterations=4, guide_weight=0.35, usage_penalty=0.02, donors=None, sharpness=3.0,
                 unsharp=0.0, hard_final=False, detail=False, style=None, return_masks=False, same_style=False, min_distance=0.0):
        """donors=None uses every training image of the topic; a small number gives more coherent pictures.

        same_style draws all donors of a picture from one style (photo / side view / illustration).
        min_distance (RMSE on a 0-255 scale) is a novelty guard: a picture closer than this to any single
        training render is discarded and redrawn, up to three tries.
        """
        if topic not in self.topics:
            raise ValueError(f'"{topic}" is not in the trained topics')
        rng = np.random.default_rng(seed)
        images, reports, masks = [], [], []
        tries = 3 if min_distance else 1
        for _ in range(n):
            for attempt in range(tries):
                current, sources, alpha, chosen, distance = self._one(topic, rng, iterations, guide_weight, usage_penalty, donors,
                                                                      sharpness, unsharp, hard_final, detail, style,
                                                                      return_masks, same_style, bool(min_distance))
                if not min_distance or distance >= min_distance:
                    break
            counts = np.bincount(sources, minlength=len(chosen))
            images.append(np.clip(current * 255 + 0.5, 0, 255).astype(np.uint8))
            report = dict(largest_source_share=round(float(counts.max() / counts.sum()), 3),
                          sources_used=int((counts > 0).sum()), donors=[int(i) for i in chosen[:16]])
            if min_distance:
                report.update(nearest_training_rmse=round(float(distance), 1), tries=attempt + 1)
            reports.append(report)
            if return_masks:
                usable = f'{topic}/has_mask' in self.data.files and bool(self.data[f'{topic}/has_mask'][chosen].all())
                masks.append(alpha[..., 0] if (alpha is not None and usable) else None)
        if return_masks:
            return np.stack(images), reports, masks
        return np.stack(images), reports

    def _one(self, topic, rng, iterations, guide_weight, usage_penalty, donors, sharpness, unsharp, hard_final, detail,
             style, return_masks, same_style, measure):
        """One picture: sample a layout, pick donors, run coarse-to-fine patch synthesis."""
        layout = self.layout(topic, rng)
        if style is not None and donors:
            # Start from a layout of the requested style, so the layout and the donors agree.
            matching = np.flatnonzero(self.styles(topic) == style)
            if len(matching) >= 2:
                picks = rng.choice(matching, size=min(3, len(matching)), replace=False)
                layout = self.small(topic)[picks].mean(0).reshape(LAYOUT, LAYOUT, 3)
        if same_style and style is None and donors:
            # Mixing a photo with an illustration gives the worst seams: take the style of the
            # closest donor and draw all donors from that style.
            nearest = self.donors(topic, layout, 1)[0]
            if self.styles(topic)[nearest] >= 0:
                style = int(self.styles(topic)[nearest])
        chosen = self.donors(topic, layout, donors, style) if donors else np.arange(len(self.pyramid(topic)[self.size]))
        guide = resize(layout, self.size)
        current = resize(guide, self.levels[0])
        usage = np.zeros(len(chosen), np.float32)
        pyramid = self.pyramid(topic)
        alpha = None
        for size in self.levels:
            if size != current.shape[0]:
                current = resize(current, size)
            level_guide = resize(guide, size)
            for step in range(iterations):
                # The blurry layout steers early steps only; later steps follow the real patches.
                weight = guide_weight * (1 - step / iterations)
                final = size == self.levels[-1] and step == iterations - 1
                # Optionally the very last step copies each pixel from its single nearest-centred
                # patch instead of averaging overlaps: real detail, at the cost of visible seams.
                hard = hard_final and final
                match = pyramid[('blur', size)][chosen] if detail else None
                query = blur(current[None])[0] if detail else current
                alpha_source = pyramid['mask'][chosen] if (return_masks and final and 'mask' in pyramid) else None
                current, sources, alpha = self.patch_step(query, level_guide, pyramid[size][chosen], size, weight,
                                                          usage_penalty, usage, rng, sharpness, hard, match, alpha_source)
        if unsharp:   # classic unsharp mask: add back a share of the detail a blur removes
            blurred = np.asarray(Image.fromarray(np.clip(current * 255 + 0.5, 0, 255).astype(np.uint8))
                                 .filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255
            current = np.clip(current + unsharp * (current - blurred), 0, 1)
        distance = 0.0
        if measure:
            originals = pyramid[self.size]
            distance = float(np.sqrt(((originals - current[None]) ** 2).mean((1, 2, 3))).min() * 255)
        return current, sources, alpha, chosen, distance

    @staticmethod
    def patch_step(current, guide, exemplars, size, guide_weight, usage_penalty, usage, rng, sharpness=3.0, hard=False, match=None, alpha=None):
        """One texture-optimisation step: match every overlapping patch, then blend the matches."""
        window = max(2, size // 16)                            # how far a patch may move from its position
        positions = list(range(0, size - PATCH + 1, STRIDE))
        if positions[-1] != size - PATCH:
            positions.append(size - PATCH)
        target = (current + guide_weight * guide) / (1 + guide_weight)
        total = np.zeros_like(current)
        alpha_total = np.zeros(current.shape[:2] + (1,), np.float32) if alpha is not None else None
        weight = np.zeros(current.shape[:2] + (1,), np.float32)
        yy, xx = np.mgrid[0:PATCH, 0:PATCH]
        centre = (PATCH - 1) / 2
        bump = np.exp(-((yy - centre) ** 2 + (xx - centre) ** 2) / (2 * (PATCH / sharpness) ** 2)).astype(np.float32)[..., None]
        sources = []
        usage[:] = 0
        order = [(y, x) for y in positions for x in positions]
        rng.shuffle(order)
        for y, x in order:
            y0, y1 = max(0, y - window), min(size - PATCH, y + window)
            x0, x1 = max(0, x - window), min(size - PATCH, x + window)
            def windows(stack):
                region = stack[:, y0:y1 + PATCH, x0:x1 + PATCH]
                view = np.lib.stride_tricks.sliding_window_view(region, (PATCH, PATCH), axis=(1, 2))
                return view.shape[:3], view.transpose(0, 1, 2, 4, 5, 3).reshape(-1, PATCH * PATCH * 3)
            (count, ny, nx), flat = windows(exemplars)          # what gets pasted
            compared = windows(match)[1] if match is not None else flat
            query = target[y:y + PATCH, x:x + PATCH].reshape(-1)
            distance = ((compared - query) ** 2).mean(1) + usage_penalty * np.repeat(usage, ny * nx) / max(1.0, len(order) / 20)
            best = int(np.argmin(distance))
            source = best // (ny * nx)
            usage[source] += 1
            sources.append(source)
            patch = flat[best].reshape(PATCH, PATCH, 3)
            alpha_patch = None
            if alpha is not None:   # the same source patch's mask, from the same place
                b = best % (ny * nx)
                py, px = y0 + b // nx, x0 + b % nx
                alpha_patch = alpha[source, py:py + PATCH, px:px + PATCH]
            if hard:
                better = bump > weight[y:y + PATCH, x:x + PATCH]
                total[y:y + PATCH, x:x + PATCH] = np.where(better, patch, total[y:y + PATCH, x:x + PATCH])
                if alpha_patch is not None:
                    alpha_total[y:y + PATCH, x:x + PATCH] = np.where(better, alpha_patch, alpha_total[y:y + PATCH, x:x + PATCH])
                weight[y:y + PATCH, x:x + PATCH] = np.maximum(bump, weight[y:y + PATCH, x:x + PATCH])
            else:
                total[y:y + PATCH, x:x + PATCH] += patch * bump
                if alpha_patch is not None:
                    alpha_total[y:y + PATCH, x:x + PATCH] += alpha_patch * bump
                weight[y:y + PATCH, x:x + PATCH] += bump
        if hard:
            return total, np.array(sources), alpha_total
        norm = np.maximum(weight, 1e-6)
        return total / norm, np.array(sources), (alpha_total / norm if alpha_total is not None else None)
