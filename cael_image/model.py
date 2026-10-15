"""Count-trained integer cellular image synthesis, without neural layers.

Each pixel is a cell. Its next color uses local static text/position fields,
four old neighboring colors and a seeded integer noise sample. Two checkerboard
phases update synchronously. There is no image lookup or nonlocal attention.
"""
import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np

SIZE = 64
COLORS = 256
SCALE = 64
DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))
STOPWORDS = set('a an the and with in on of is at to for her she'.split())


def tokens(text):
    return sorted(set(re.findall(r"[a-z][a-z0-9_-]*", text.casefold())) - STOPWORDS)


def palette():
    ids = np.arange(COLORS, dtype=np.uint16)
    return np.stack(((ids >> 5) * 255 // 7,
                     ((ids >> 2) & 7) * 255 // 7,
                     (ids & 3) * 255 // 3), axis=-1).astype(np.uint8)


def quantize(rgb):
    rgb = np.asarray(rgb)
    if rgb.shape != (SIZE, SIZE, 3) or rgb.dtype != np.uint8:
        raise ValueError('Expected a 64x64 RGB uint8 image.')
    values = rgb.astype(np.uint16)
    return (((values[..., 0] * 7 + 127) // 255) << 5 |
            ((values[..., 1] * 7 + 127) // 255) << 2 |
            (values[..., 2] * 3 + 127) // 255).astype(np.uint8)


def neighbors(state, dy, dx):
    """Read the old adjacent cell; invalid edges do not wrap around."""
    result = np.roll(state, (-dy, -dx), axis=(0, 1))
    valid = np.ones(state.shape, dtype=bool)
    if dy < 0:
        valid[: -dy] = False
    elif dy > 0:
        valid[-dy:] = False
    if dx < 0:
        valid[:, : -dx] = False
    elif dx > 0:
        valid[:, -dx:] = False
    return result, valid


def integer_log_prob(counts, smoothing=1):
    """Floating logs are used only when fitting; inference tables are integers."""
    values = counts.astype(np.float64) + smoothing
    probabilities = values / values.sum(axis=-1, keepdims=True)
    return np.rint(np.log(probabilities) * SCALE).astype(np.int16)


class Counts:
    def __init__(self, vocabulary, bins=8):
        self.vocabulary = list(vocabulary)
        self.index = {word: i for i, word in enumerate(vocabulary)}
        self.bins = bins
        yy, xx = np.indices((SIZE, SIZE))
        self.positions = (yy // (SIZE // bins) * bins + xx // (SIZE // bins)).ravel()
        self.spatial = np.zeros((SIZE, SIZE, COLORS), np.uint64)
        self.coarse = np.zeros((bins * bins, COLORS), np.uint64)
        self.conditioned = np.zeros((len(vocabulary), bins * bins, COLORS), np.uint64)
        self.pairs = np.zeros((4, COLORS, COLORS), np.uint64)
        self.global_counts = np.zeros(COLORS, np.uint64)
        self.images = 0

    def observe(self, state, caption):
        if state.shape != (SIZE, SIZE) or state.dtype != np.uint8:
            raise ValueError('Expected a 64x64 uint8 color state.')
        flat = state.ravel().astype(np.int64)
        self.spatial.reshape(-1, COLORS)[np.arange(SIZE * SIZE), flat] += 1
        histogram = np.bincount(self.positions * COLORS + flat,
                                minlength=self.bins * self.bins * COLORS)
        histogram = histogram.reshape(self.bins * self.bins, COLORS).astype(np.uint64)
        self.coarse += histogram
        for word in tokens(caption):
            if word in self.index:
                self.conditioned[self.index[word]] += histogram
        self.global_counts += np.bincount(flat, minlength=COLORS).astype(np.uint64)
        for d, (dy, dx) in enumerate(DIRECTIONS):
            adjacent, valid = neighbors(state, dy, dx)
            pair_ids = adjacent[valid].astype(np.int64) * COLORS + state[valid]
            self.pairs[d] += np.bincount(pair_ids, minlength=COLORS * COLORS).reshape(COLORS, COLORS).astype(np.uint64)
        self.images += 1

    def export(self, settings, layout_arrays=None):
        if not self.images:
            raise ValueError('No training images observed.')
        global_log = integer_log_prob(self.global_counts)
        coarse_log = integer_log_prob(self.coarse)
        conditioned = integer_log_prob(self.conditioned).astype(np.int32) - coarse_log[None]
        pair_scores = integer_log_prob(self.pairs).astype(np.int32)
        if layout_arrays is None:
            pair_scores -= global_log
        # A precomputed integer Gumbel lookup supplies approximate categorical noise.
        u = (np.arange(4096, dtype=np.float64) + 0.5) / 4096
        noise = np.rint(-np.log(-np.log(u)) * SCALE).astype(np.int16)
        arrays = dict(spatial=integer_log_prob(self.spatial),
                      conditioned=np.clip(conditioned, -32768, 32767).astype(np.int16),
                      pairs=np.clip(pair_scores, -32768, 32767).astype(np.int16),
                      noise=noise, palette=palette())
        metadata = dict(format='cael-integer-image-v2' if layout_arrays is not None else 'cael-integer-image-v1', size=SIZE, colors=COLORS,
                        bins=self.bins, vocabulary=self.vocabulary,
                        neural_parameters=0, training_images=self.images,
                        architecture='conditional count-trained integer 2D cellular automaton',
                        specialization='female characters', settings=settings)
        if layout_arrays is not None:
            arrays.update(layout_arrays)
            metadata.update(layout_clusters=len(layout_arrays['layouts']),
                            layout_size=layout_arrays['layouts'].shape[1],
                            architecture='non-neural coarse-layout prior plus integer 2D cellular refinement')
        return ImageCA(metadata, arrays)


class ImageCA:
    def __init__(self, metadata, arrays):
        if metadata.get('format') not in ('cael-integer-image-v1', 'cael-integer-image-v2') or metadata.get('size') != SIZE:
            raise ValueError('Not a supported CAEL 64x64 image model.')
        self.metadata = metadata
        self.arrays = {key: np.asarray(value) for key, value in arrays.items()}
        self.vocabulary = {word: i for i, word in enumerate(metadata['vocabulary'])}
        bins = int(metadata['bins'])
        if bins not in (1, 2, 4, 8, 16):
            raise ValueError('Invalid conditioning grid.')
        shapes = dict(spatial=(SIZE, SIZE, COLORS),
                      conditioned=(len(self.vocabulary), bins * bins, COLORS),
                      pairs=(4, COLORS, COLORS), noise=(4096,), palette=(COLORS, 3))
        if metadata['format'] == 'cael-integer-image-v2':
            count, size = int(metadata['layout_clusters']), int(metadata['layout_size'])
            if not 1 <= count <= 256 or size not in (8, 16):
                raise ValueError('Invalid coarse layout geometry.')
            shapes.update(layouts=(count, size, size, 3), layout_prior=(count,),
                          layout_words=(len(self.vocabulary), count))
        if set(arrays) != set(shapes):
            raise ValueError('Unexpected image model arrays.')
        for name, shape in shapes.items():
            dtype = np.dtype(np.uint8 if name in ('palette', 'layouts') else np.int16)
            if self.arrays[name].shape != shape or self.arrays[name].dtype != dtype:
                raise ValueError('Invalid integer table: ' + name)
        for key in ('spatial_weight', 'text_weight', 'neighbor_weight'):
            value = metadata['settings'].get(key)
            if type(value) is not int or not 0 <= value <= 16:
                raise ValueError('Invalid integer model setting: ' + key)
        yy, xx = np.indices((SIZE, SIZE))
        self.positions = yy // (SIZE // bins) * bins + xx // (SIZE // bins)
        self.phase = (yy + xx) % 2

    def choose_layout(self, prompt, rng=None, noise=None):
        if 'layouts' not in self.arrays:
            return None
        score = self.arrays['layout_prior'].astype(np.int32).copy()
        matched = [self.vocabulary[word] for word in tokens(prompt) if word in self.vocabulary]
        if matched:
            score += self.arrays['layout_words'][matched].astype(np.int32).sum(axis=0) // len(matched)
        if rng is not None:
            level = self.metadata['settings']['noise'] if noise is None else noise
            score += self.arrays['noise'][rng.integers(0, 4096, score.shape)].astype(np.int32) * level // SCALE
        return int(score.argmax())

    def save(self, path):
        path = Path(path)
        if path.exists():
            raise FileExistsError('Model already exists: ' + str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.partial')
        owns_temporary = False
        payload = np.frombuffer(json.dumps(self.metadata, sort_keys=True).encode('utf-8'), np.uint8)
        try:
            with temporary.open('xb') as stream:
                owns_temporary = True
                np.savez_compressed(stream, metadata=payload, **self.arrays)
            if path.exists():
                raise FileExistsError('Model appeared while writing; existing file preserved.')
            os.replace(temporary, path)
        finally:
            if owns_temporary and temporary.exists():
                temporary.unlink()

    @classmethod
    def load(cls, path):
        with np.load(Path(path), allow_pickle=False) as archive:
            metadata = json.loads(archive['metadata'].tobytes().decode('utf-8'))
            arrays = {key: archive[key] for key in archive.files if key != 'metadata'}
        return cls(metadata, arrays)

    def condition(self, prompt, layout_id=None):
        matched = [word for word in tokens(prompt) if word in self.vocabulary]
        if not matched:
            raise ValueError('No learned caption words matched this prompt. Use words present in your training captions.')
        settings = self.metadata['settings']
        energy = self.arrays['spatial'].astype(np.int32) * settings['spatial_weight']
        addition = np.zeros_like(energy)
        for word in matched:
            addition += self.arrays['conditioned'][self.vocabulary[word]][self.positions]
        energy += addition * settings['text_weight'] // len(matched)
        if 'layouts' in self.arrays:
            from .layout import upscale_integer
            layout_id = self.choose_layout(prompt) if layout_id is None else layout_id
            if not 0 <= layout_id < len(self.arrays['layouts']):
                raise ValueError('Invalid layout ID.')
            target = upscale_integer(self.arrays['layouts'][layout_id]).astype(np.int16)
            colors = self.arrays['palette'].astype(np.int16)
            distance = np.abs(target[:, :, None, :] - colors[None, None, :, :]).sum(axis=-1).astype(np.int32)
            energy -= distance * settings.get('layout_weight', 8) // 4
        return energy, matched

    def scores(self, state, condition, iteration=0, sampler='stable'):
        if state.shape != (SIZE, SIZE) or state.dtype != np.uint8:
            raise ValueError('Expected a 64x64 uint8 cellular state.')
        if condition.shape != (SIZE, SIZE, COLORS) or condition.dtype != np.int32:
            raise ValueError('Expected an integer local conditioning field.')
        result = condition.copy()
        strength = self.metadata['settings']['neighbor_weight']
        total = np.zeros_like(result)
        degree = np.zeros((SIZE, SIZE, 1), np.int32)
        for d, (dy, dx) in enumerate(DIRECTIONS):
            adjacent, valid = neighbors(state, dy, dx)
            evidence = self.arrays['pairs'][d][adjacent].astype(np.int32)
            if sampler == 'stable':
                # v1 sparse likelihood ratios must not reward unobserved rare colors.
                evidence = np.minimum(evidence, 0)
            elif sampler != 'legacy':
                raise ValueError('sampler must be stable or legacy.')
            total += evidence * valid[..., None] * strength
            degree += valid[..., None]
        result += total // np.maximum(degree, 1) if sampler == 'stable' else total
        return result

    def step(self, state, condition, rng, iteration, noise, sampler='stable'):
        result = self.scores(state, condition, iteration, sampler)
        if noise:
            jitter = self.arrays['noise'][rng.integers(0, 4096, result.shape)].astype(np.int32)
            result += jitter * noise // SCALE
        proposed = result.argmax(axis=-1).astype(np.uint8)
        return np.where(self.phase == iteration % 2, proposed, state).astype(np.uint8)

    def generate(self, prompt, seed=0, steps=None, noise=None, sampler='stable'):
        settings = self.metadata['settings']
        steps = settings['steps'] if steps is None else steps
        noise = settings['noise'] if noise is None else noise
        if not isinstance(steps, int) or not 0 <= steps <= 2048:
            raise ValueError('steps must be an integer between 0 and 2048.')
        if not isinstance(noise, int) or not 0 <= noise <= 1024:
            raise ValueError('noise must be an integer between 0 and 1024.')
        if sampler not in ('stable', 'legacy'):
            raise ValueError('sampler must be stable or legacy.')
        rng = np.random.default_rng(seed)
        layout_id = self.choose_layout(prompt, rng if noise else None, noise)
        energy, matched = self.condition(prompt, layout_id)
        initial = energy.copy()
        if noise:
            initial += self.arrays['noise'][rng.integers(0, 4096, initial.shape)].astype(np.int32) * noise // SCALE
        state = initial.argmax(axis=-1).astype(np.uint8)
        for iteration in range(steps):
            level = noise * (steps - iteration - 1) // max(steps, 1) if sampler == 'stable' else noise
            state = self.step(state, energy, rng, iteration, level, sampler)
        return self.arrays['palette'][state].astype(np.uint8), dict(
            prompt=prompt, matched_words=matched,
            unmatched_words=sorted(set(tokens(prompt)) - set(matched)),
            seed=seed, steps=steps, noise=noise, sampler=sampler, layout_id=layout_id, width=SIZE, height=SIZE,
            neural_parameters=0, generation_quality='unvalidated research prototype')


def generate_file(model_path, prompt, output, seed=0, steps=None, noise=None, sampler='stable'):
    from PIL import Image
    output = Path(output)
    if output.suffix.lower() != '.png':
        raise ValueError('Use a .png output filename.')
    if output.exists() or output.with_suffix('.json').exists():
        raise FileExistsError('Choose a new output filename; existing image/metadata is preserved.')
    model = ImageCA.load(model_path)
    rgb, metadata = model.generate(prompt, seed, steps, noise, sampler)
    metadata['model_sha256'] = hashlib.sha256(Path(model_path).read_bytes()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(output)
    output.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8', newline='\n')
    return metadata
