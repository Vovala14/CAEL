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
import io
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


def resize_gray(array, size):
    image = Image.fromarray(np.clip(array * 255 + 0.5, 0, 255).astype(np.uint8))
    return np.asarray(image.resize((size, size), Image.Resampling.BICUBIC), dtype=np.float32) / 255


def border_colour(image):
    return tuple(float(v) for v in np.median(np.concatenate([image[0], image[-1], image[:, 0], image[:, -1]]), 0))


def warp(image, transform, fill):
    """Apply (scale, dx, dy, mirror) about the centre; dx, dy are fractions of the width. Works at any size."""
    scale, dx, dy, mirror = transform
    if scale == 1.0 and dx == 0.0 and dy == 0.0 and not mirror:
        return image
    size = image.shape[0]
    channels = image.shape[2]
    out = []
    for c in range(channels):
        plane = Image.fromarray(image[..., c].astype(np.float32), mode='F')
        if mirror:
            plane = plane.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        # Output pixel p comes from input (p - centre - shift) / scale + centre.
        centre = (size - 1) / 2
        a = 1 / scale
        tx, ty = dx * size, dy * size
        coeffs = (a, 0, centre - a * (centre + tx), 0, a, centre - a * (centre + ty))
        plane = plane.transform((size, size), Image.Transform.AFFINE, coeffs, resample=Image.Resampling.BILINEAR, fillcolor=fill[c])
        out.append(np.asarray(plane, np.float32))
    return np.clip(np.stack(out, -1), 0, 1)


def silhouette_transform(anchor, mask):
    """Shift, scale and mirror that put this silhouette onto the anchor's (centroid, area, overlap)."""
    size = anchor.shape[0]
    yy, xx = np.mgrid[:size, :size]

    def moments(m):
        total = max(float(m.sum()), 1.0)
        return (xx * m).sum() / total, (yy * m).sum() / total, np.sqrt(total)
    ax, ay, asz = moments(anchor)
    best = None
    for mirror in (False, True):
        m = mask[:, ::-1] if mirror else mask
        mx, my, msz = moments(m)
        scale = float(np.clip(asz / max(msz, 1.0), 0.6, 1.6))
        centre = (size - 1) / 2
        # After scaling about the centre the donor centroid sits at centre + scale * (m - centre).
        dx = (ax - (centre + scale * (mx - centre))) / size
        dy = (ay - (centre + scale * (my - centre))) / size
        moved = warp(m[..., None], (scale, dx, dy, False), (0.0,))[..., 0]
        overlap = float(np.minimum(moved, anchor).sum() / max(np.maximum(moved, anchor).sum(), 1.0))
        if best is None or overlap > best[0]:
            best = (overlap, (scale, dx, dy, mirror))
    return best[1]


def scene_transform(anchor, image):
    """Scenes: mirror if that matches better, and a vertical shift that lines up the horizon (row brightness)."""
    def rows(im):
        r = im.mean((1, 2))
        return (r - r.mean()) / (r.std() + 1e-6)
    a = rows(anchor)
    size = anchor.shape[0]
    mirror = float(np.abs(anchor - image[:, ::-1]).mean()) < float(np.abs(anchor - image).mean())
    b = rows(image)
    limit = size // 8
    shifts = range(-limit, limit + 1)
    score = [float((a[max(0, s):size + min(0, s)] * b[max(0, -s):size - max(0, s)]).mean()) for s in shifts]
    shift = list(shifts)[int(np.argmax(score))]
    return (1.0, 0.0, shift / size, mirror)


def pack(model_path, detail_images, output, quality=95):
    """A packed copy of a fitted model: every training image stored once, as a detail-size JPEG.

    detail_images(topic) -> uint8 N x 2S x 2S x 3 in the model's training order. The model-size images are
    then derived when the model loads, so the file is smaller and still carries the finer detail.
    """
    source = np.load(model_path, allow_pickle=False)
    meta = json.loads(bytes(source['meta']).decode('utf-8'))
    arrays = {}
    for name in source.files:
        topic, _, field = name.partition('/')
        if field == 'images':
            images = detail_images(topic)
            assert len(images) == len(source[name]), topic
            chunks, offsets = [], [0]
            for im in images:
                buffer = io.BytesIO()
                Image.fromarray(im).save(buffer, 'JPEG', quality=quality, subsampling=0)
                chunks.append(buffer.getvalue())
                offsets.append(offsets[-1] + len(chunks[-1]))
            arrays[f'{topic}/jpeg'] = np.frombuffer(b''.join(chunks), np.uint8)
            arrays[f'{topic}/jpeg_offsets'] = np.array(offsets, np.int64)
        elif name != 'meta':
            arrays[name] = source[name]
    meta['detail_size'] = int(images.shape[1])
    arrays['meta'] = np.frombuffer(json.dumps(meta).encode('utf-8'), dtype=np.uint8)
    np.savez_compressed(output, **arrays)


def deform(image, rng, strength):
    """A smooth random warp of a float image (and a mirror half the time): a new pose with the same parts.

    strength is the largest displacement as a fraction of the width. Low-frequency (4x4 control grid) so
    shapes bend rather than tear.
    """
    from scipy.ndimage import map_coordinates
    size = image.shape[0]
    if rng.random() < 0.5:
        image = image[:, ::-1]
    grid = rng.standard_normal((2, 4, 4)).astype(np.float32) * strength * size / 2
    field = np.stack([np.asarray(Image.fromarray(g, mode='F').resize((size, size), Image.Resampling.BICUBIC)) for g in grid])
    yy, xx = np.mgrid[:size, :size].astype(np.float32)
    out = np.stack([map_coordinates(image[..., c], [yy + field[0], xx + field[1]], order=1, mode='nearest')
                    for c in range(image.shape[2])], -1)
    return np.clip(out, 0, 1)


def seam_fuse(soft, sharp, owner, weight):
    """Screened Poisson fusion: the sharp image's gradients inside each source region, the soft image's gradients
    across region borders (where seams would be), and the soft image's colours as a weak anchor.

    Solves weight * I - laplace(I) = weight * soft - div(g) with mirrored borders, exactly, by a cosine transform.
    """
    from scipy.fft import dctn, idctn
    h, w = soft.shape[:2]
    same_x = owner[:, 1:] == owner[:, :-1]
    same_y = owner[1:] == owner[:-1]
    out = np.empty_like(soft)
    ky = 2 - 2 * np.cos(np.pi * np.arange(h) / h)
    kx = 2 - 2 * np.cos(np.pi * np.arange(w) / w)
    eigen = ky[:, None] + kx[None, :]
    for c in range(soft.shape[2]):
        s, t = soft[..., c], sharp[..., c]
        gx = np.where(same_x, t[:, 1:] - t[:, :-1], s[:, 1:] - s[:, :-1])
        gy = np.where(same_y, t[1:] - t[:-1], s[1:] - s[:-1])
        div = np.zeros_like(s)
        div[:, :-1] += gx
        div[:, 1:] -= gx
        div[:-1] += gy
        div[1:] -= gy
        rhs = dctn(weight * s - div, type=2, norm="ortho")
        out[..., c] = idctn(rhs / (weight + eigen), type=2, norm='ortho')
    return np.clip(out, 0, 1)


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

    def images(self, topic):
        """Training images at the model size (uint8). Packed models store them once, as detail-size JPEGs."""
        if f'{topic}/images' in self.data.files:
            return self.data[f'{topic}/images']
        return np.stack([np.asarray(Image.fromarray(im).resize((self.size, self.size), Image.Resampling.LANCZOS))
                         for im in self.detail_images(topic)])

    def detail_images(self, topic, indices=None):
        """Training images at the detail size (twice the model size) from the packed JPEG store."""
        key = ('detail', topic)
        if key not in self._pyramids:
            blob = self.data[f'{topic}/jpeg']
            offsets = self.data[f'{topic}/jpeg_offsets']
            self._pyramids[key] = [bytes(blob[offsets[i]:offsets[i + 1]]) for i in range(len(offsets) - 1)]
        encoded = self._pyramids[key]
        picks = range(len(encoded)) if indices is None else np.asarray(indices).tolist()
        return np.stack([np.asarray(Image.open(io.BytesIO(encoded[i])).convert('RGB')) for i in picks])

    @property
    def has_detail(self):
        return bool(self.topics) and f'{self.topics[0]}/jpeg' in self.data.files

    def pyramid(self, topic):
        if topic not in self._pyramids:
            images = self.images(topic).astype(np.float32) / 255
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

    def donors(self, topic, layout, count, style=None, pairing=False, allowed=None):
        """Training images whose 16x16 layout is closest to the sampled layout (of the requested style, if any).

        allowed limits the styles considered when no style is given (e.g. photos only for a plain request).
        pairing picks only the first donor by the layout and every further donor by how well it matches that
        first donor (same silhouette and same arrangement), so two different poses are not stitched together.
        """
        small = self.small(topic)
        distance = ((small - layout.reshape(1, -1)) ** 2).mean(1)
        styles = self.styles(topic)
        if style is not None:
            matching = styles == style
            if matching.sum() >= max(2, count):
                distance = np.where(matching, distance, np.inf)
        elif allowed is not None:
            matching = np.isin(styles, allowed)
            if matching.sum() >= max(2, count):
                distance = np.where(matching, distance, np.inf)
        order = np.argsort(distance)
        if not pairing or count < 2:
            return order[:count]
        anchor = order[0]
        eligible = np.isfinite(distance)
        likeness = ((small - small[anchor]) ** 2).mean(1)
        likeness = likeness / (np.median(likeness[eligible]) + 1e-6)
        shapes = self.small_masks(topic)
        if shapes is not None and self.data[f'{topic}/has_mask'][anchor]:
            overlap = np.minimum(shapes, shapes[anchor]).sum(1) / (np.maximum(shapes, shapes[anchor]).sum(1) + 1e-6)
            likeness = likeness + 2.0 * (1 - overlap)
        likeness = np.where(eligible, likeness, np.inf)
        likeness[anchor] = -np.inf
        return np.argsort(likeness)[:count]

    def small_masks(self, topic):
        """16x16 silhouettes of the training images (None for a topic without masks)."""
        key = ('small_mask', topic)
        if key not in self._pyramids:
            pyramid = self.pyramid(topic)
            self._pyramids[key] = (np.stack([resize_gray(m[..., 0], LAYOUT) for m in pyramid['mask']]).reshape(len(pyramid['mask']), -1)
                                   if 'mask' in pyramid else None)
        return self._pyramids[key]

    def small(self, topic):
        key = ('small', topic)
        if key not in self._pyramids:
            images = self.pyramid(topic)[self.size]
            self._pyramids[key] = np.stack([resize(im, LAYOUT) for im in images]).reshape(len(images), -1)
        return self._pyramids[key]

    def generate(self, topic, n=2, seed=0, iterations=4, guide_weight=0.35, usage_penalty=0.02, donors=None, sharpness=3.0,
                 unsharp=0.0, hard_final=False, detail=False, style=None, return_masks=False, same_style=False, min_distance=0.0,
                 best_of=1, align=False, hires=None, hires_steps=2, seam_blend=0.0, pairing=False, default_styles=None,
                 structure=0.0):
        """donors=None uses every training image of the topic; a small number gives more coherent pictures.

        best_of sketches that many candidates up to the second-finest level and finishes only the one whose
        overlapping patches disagree least (least ghosting). align warps every donor onto the first donor
        (shift, scale, mirror) before mixing. hires is a callable (topic, indices) -> uint8 images at twice the
        model size: the last synthesis level then runs at that size and the result is shrunk at the end.

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
            farthest = None
            for attempt in range(tries):
                result = self._one(topic, rng, iterations, guide_weight, usage_penalty, donors, sharpness, unsharp, hard_final,
                                   detail, style, return_masks, same_style, float(min_distance), best_of, align, hires,
                                   hires_steps, seam_blend, pairing, default_styles, structure)
                if farthest is None or result[4] > farthest[4]:
                    farthest = result
                if not min_distance or result[4] >= min_distance:
                    break
            # When no attempt clears the guard, keep the one farthest from any training image, never simply the last.
            current, sources, alpha, chosen, distance = farthest
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
             style, return_masks, same_style, measure, best_of=1, align=False, hires=None, hires_steps=2, seam_blend=0.0,
             pairing=False, default_styles=None, structure=0.0):
        """One picture: sample a layout, pick donors, run coarse-to-fine patch synthesis."""
        pyramid = self.pyramid(topic)
        coarse, finest = self.levels[:-1], self.levels[-1]
        candidates = []
        locked_style = style
        for _ in range(max(1, best_of)):
            layout = self.layout(topic, rng)
            # All candidates keep the first candidate's style: otherwise the choice drifts to flat illustrations,
            # which have little texture to disagree about.
            candidate_style = locked_style
            if candidate_style is not None and donors:
                # Start from a layout of the requested style, so the layout and the donors agree.
                matching = np.flatnonzero(self.styles(topic) == candidate_style)
                if len(matching) >= 2:
                    picks = rng.choice(matching, size=min(3, len(matching)), replace=False)
                    layout = self.small(topic)[picks].mean(0).reshape(LAYOUT, LAYOUT, 3)
            if same_style and candidate_style is None and donors:
                # Mixing a photo with an illustration gives the worst seams: take the style of the
                # closest donor and draw all donors from that style.
                nearest = self.donors(topic, layout, 1, allowed=default_styles)[0]
                if self.styles(topic)[nearest] >= 0:
                    candidate_style = int(self.styles(topic)[nearest])
            if locked_style is None:
                locked_style = candidate_style
            chosen = self.donors(topic, layout, donors, candidate_style, pairing=pairing) if donors else np.arange(len(pyramid[self.size]))
            stacks = self.aligned(topic, chosen) if (align or structure) and donors and len(chosen) > 1 else None
            guide = resize(layout, self.size)
            if structure and donors:
                # Structure from one real picture: the first donor, bent by a smooth random warp (and sometimes
                # mirrored) into a new pose. Its outline and proportions guide every synthesis step, so the result
                # has one coherent shape instead of two half-poses; the texture is rebuilt from both donors.
                anchor = (stacks[self.size][0] if stacks is not None else pyramid[self.size][chosen[0]])
                guide = deform(anchor, rng, structure)
            state = dict(chosen=chosen, stacks=stacks, guide=guide, current=resize(guide, self.levels[0]),
                         usage=np.zeros(len(chosen), np.float32), stats={}, structure=bool(structure and donors),
                         structure_floor=0.35)
            for size in (coarse if best_of > 1 else []):
                self._level(state, topic, size, iterations, guide_weight, usage_penalty, rng, sharpness, False, detail, False)
            if best_of > 1 and measure:
                # Novelty at the sketch stage: distance (0-255 RMSE) to the closest training image at this size.
                sketch = state['current']
                originals = pyramid[sketch.shape[0]]
                state['sketch_distance'] = float(np.sqrt(((originals - sketch[None]) ** 2).mean((1, 2, 3))).min() * 255)
            candidates.append(state)
        if best_of > 1 and measure:
            # Near-copies of one training image are not eligible, however clean they look.
            novel = [c for c in candidates if c['sketch_distance'] >= measure]
            if not novel:
                ranked = sorted(candidates, key=lambda c: -c['sketch_distance'])
                novel = ranked[:max(1, len(ranked) // 2)]
            candidates = novel
        # Ghosting relative to the picture's own detail: an empty, flat picture must not win just by being flat.
        state = min(candidates, key=lambda c: c['stats'].get('disagreement', 0.0) / (c['stats'].get('detail', 0.0) + 1e-4))
        chosen = state['chosen']
        for size in (self.levels if best_of <= 1 else [finest]):
            final = size == finest and hires is None
            self._level(state, topic, size, iterations, guide_weight, usage_penalty, rng, sharpness, hard_final and final, detail,
                        return_masks and final)
        if hires is True:          # the model's own packed detail images, when it has them
            hires = self.detail_images if self.has_detail else None
        if hires is not None:
            big = hires(topic, chosen).astype(np.float32) / 255
            if state['stacks'] is not None:
                big = np.stack([warp(im, t, fill) for im, t, fill in zip(big, state['stacks']['transforms'], state['stacks']['fills'])])
            size = big.shape[1]
            exemplars = {size: big, ('blur', size): blur(big, 2.4)}
            masks = None
            if return_masks and 'mask' in pyramid:
                small_masks = state['stacks']['mask'] if state['stacks'] is not None else pyramid['mask'][chosen]
                masks = np.stack([resize_gray(m[..., 0], size) for m in small_masks])[..., None]
            state['current'] = resize(state['current'], size)
            level_guide = resize(state['guide'], size)
            # Two steps are enough at the finest level: the structure is settled, only detail is added.
            for step in range(hires_steps):
                query = blur(state['current'][None], 2.4)[0] if detail else state['current']
                state['current'], state['sources'], state['alpha'] = self.patch_step(
                    query, level_guide, exemplars[size], size, guide_weight * 0.1 * (1 - step / hires_steps), usage_penalty, state['usage'],
                    rng, sharpness, False, exemplars[('blur', size)] if detail else None, masks if step == hires_steps - 1 else None,
                    window=max(2, size // 32), poisson=seam_blend if step == hires_steps - 1 else 0.0)
            # Shrink to the model size at the end: averaging four synthesised pixels into one hides blend noise.
            state['current'] = resize(state['current'], self.size)
            if state.get('alpha') is not None:
                state['alpha'] = resize_gray(state['alpha'][..., 0], self.size)[..., None]
        current = state['current']
        if unsharp:   # classic unsharp mask: add back a share of the detail a blur removes
            blurred = np.asarray(Image.fromarray(np.clip(current * 255 + 0.5, 0, 255).astype(np.uint8))
                                 .filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32) / 255
            current = np.clip(current + unsharp * (current - blurred), 0, 1)
        distance = 0.0
        if measure:
            # Compared at 64 px, where a copy of the shape cannot hide behind different fine detail, and
            # mirrored training images count too: a flipped copy is still a copy.
            check = min(64, self.size)
            originals = pyramid[check]
            small = resize(current, check)
            plain = np.sqrt(((originals - small[None]) ** 2).mean((1, 2, 3))).min()
            mirrored = np.sqrt(((originals[:, :, ::-1] - small[None]) ** 2).mean((1, 2, 3))).min()
            distance = float(min(plain, mirrored) * 255)
        return current, state.get('sources', np.zeros(1, int)), state.get('alpha'), chosen, distance

    def _level(self, state, topic, size, iterations, guide_weight, usage_penalty, rng, sharpness, hard_final, detail, with_mask):
        """Run the synthesis steps of one pyramid level on a candidate's state."""
        pyramid = self.pyramid(topic)
        stacks = state['stacks']
        source = stacks if stacks is not None else {k: v[state['chosen']] for k, v in pyramid.items() if k != 'mask' and (k == size or k == ('blur', size))}
        if stacks is None and 'mask' in pyramid:
            source['mask'] = pyramid['mask'][state['chosen']]
        if size != state['current'].shape[0]:
            state['current'] = resize(state['current'], size)
        level_guide = resize(state['guide'], size)
        for step in range(iterations):
            # The blurry layout steers early steps only; later steps follow the real patches.
            weight = guide_weight * (1 - step / iterations)
            if state.get('structure'):
                weight = max(weight, state['structure_floor'])   # the real structure keeps steering to the end
            final = step == iterations - 1
            # Optionally the very last step copies each pixel from its single nearest-centred
            # patch instead of averaging overlaps: real detail, at the cost of visible seams.
            hard = hard_final and final
            match = source[('blur', size)] if detail else None
            query = blur(state['current'][None])[0] if detail else state['current']
            alpha_source = source.get('mask') if (with_mask and final) else None
            state['current'], state['sources'], state['alpha'] = self.patch_step(
                query, level_guide, source[size], size, weight, usage_penalty, state['usage'], rng, sharpness, hard, match,
                alpha_source, stats=state['stats'])

    def aligned(self, topic, chosen):
        """Donor stacks with every donor warped onto the first one (shift, scale, mirror); all pyramid levels."""
        pyramid = self.pyramid(topic)
        images = pyramid[self.size][chosen]
        has_mask = self.data[f'{topic}/has_mask'][chosen] if f'{topic}/has_mask' in self.data.files else np.zeros(len(chosen), bool)
        masks = pyramid['mask'][chosen][..., 0] if 'mask' in pyramid else np.ones(images.shape[:3], np.float32)
        transforms, fills = [(1.0, 0.0, 0.0, False)], [border_colour(images[0])]
        for k in range(1, len(chosen)):
            if has_mask[0] and has_mask[k]:
                transforms.append(silhouette_transform(masks[0], masks[k]))
            else:
                transforms.append(scene_transform(images[0], images[k]))
            fills.append(border_colour(images[k]))
        warped = np.stack([warp(im, t, f) for im, t, f in zip(images, transforms, fills)])
        out = dict(transforms=transforms, fills=fills, mask=np.stack([warp(m[..., None], t, (0.0,)) for m, t in zip(masks, transforms)]))
        for s in self.levels:
            out[s] = warped if s == self.size else np.stack([resize(im, s) for im in warped])
            out[('blur', s)] = blur(out[s])
        return out

    @staticmethod
    def patch_step(current, guide, exemplars, size, guide_weight, usage_penalty, usage, rng, sharpness=3.0, hard=False, match=None, alpha=None,
                   window=None, stats=None, poisson=0.0):
        """One texture-optimisation step: match every overlapping patch, then blend the matches.

        stats, when given, receives 'disagreement': how much overlapping chosen patches differ where they
        overlap (mean per-pixel variance). High disagreement is what shows up as ghosting and smears.
        """
        window = window or max(2, size // 16)                  # how far a patch may move from its position
        positions = list(range(0, size - PATCH + 1, STRIDE))
        if positions[-1] != size - PATCH:
            positions.append(size - PATCH)
        target = (current + guide_weight * guide) / (1 + guide_weight)
        total = np.zeros_like(current)
        alpha_total = np.zeros(current.shape[:2] + (1,), np.float32) if alpha is not None else None
        weight = np.zeros(current.shape[:2] + (1,), np.float32)
        squares = np.zeros_like(current) if stats is not None and not hard else None
        if poisson:
            # Seam blending: also keep, per pixel, the single patch that covers it most centrally (sharp but
            # seamy), and which source region that patch came from (source image + displacement).
            sharp = np.zeros_like(current)
            owner = np.full(current.shape[:2], -1, np.int64)
            strongest = np.zeros(current.shape[:2], np.float32)
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
            if poisson:
                b = best % (ny * nx)
                py, px = y0 + b // nx, x0 + b % nx
                key = source * 1_000_000 + (py - y + 500) * 1000 + (px - x + 500)
                centre_weight = bump[..., 0]
                take = centre_weight > strongest[y:y + PATCH, x:x + PATCH]
                sharp[y:y + PATCH, x:x + PATCH][take] = patch[take]
                owner[y:y + PATCH, x:x + PATCH][take] = key
                strongest[y:y + PATCH, x:x + PATCH] = np.maximum(strongest[y:y + PATCH, x:x + PATCH], centre_weight)
            if hard:
                better = bump > weight[y:y + PATCH, x:x + PATCH]
                total[y:y + PATCH, x:x + PATCH] = np.where(better, patch, total[y:y + PATCH, x:x + PATCH])
                if alpha_patch is not None:
                    alpha_total[y:y + PATCH, x:x + PATCH] = np.where(better, alpha_patch, alpha_total[y:y + PATCH, x:x + PATCH])
                weight[y:y + PATCH, x:x + PATCH] = np.maximum(bump, weight[y:y + PATCH, x:x + PATCH])
            else:
                total[y:y + PATCH, x:x + PATCH] += patch * bump
                if squares is not None:
                    squares[y:y + PATCH, x:x + PATCH] += patch * patch * bump
                if alpha_patch is not None:
                    alpha_total[y:y + PATCH, x:x + PATCH] += alpha_patch * bump
                weight[y:y + PATCH, x:x + PATCH] += bump
        if hard:
            return total, np.array(sources), alpha_total
        norm = np.maximum(weight, 1e-6)
        if squares is not None:
            result = total / norm
            stats['disagreement'] = float(np.maximum(squares / norm - result ** 2, 0).mean())
            gy, gx = np.gradient(result.mean(2))
            stats['detail'] = float((gx ** 2 + gy ** 2).mean())        # how much real structure the picture has
        blended = total / norm
        if poisson:
            blended = seam_fuse(blended, sharp, owner, poisson)
        return blended, np.array(sources), (alpha_total / norm if alpha_total is not None else None)
