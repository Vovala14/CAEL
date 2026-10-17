"""Non-neural whole-image statistical structure plus local cellular sampling.

Mixture means and low-rank principal-component bases aggregate many fitting
faces. No source image, patch bank or source coefficient vector is stored.
This is a hybrid statistical prior and CA, not purely local CA geometry.
"""
import math

import torch

from cael_image.portrait_sampling import downsample_lab
from cael_image.v6_region_ca import rgb2lab, lab2rgb, kmeans


class StructurePrior:
    def __init__(self, state):
        self.state = state

    @classmethod
    def fit(cls, images, clusters=4, rank=8, min_members=24, seed=130016):
        if clusters < 1 or rank < 1 or min_members < 4:
            raise ValueError('Need positive clusters/rank and at least four members per population')
        if len(images) < min_members:
            raise ValueError('Too few fitting faces for an aggregate structure model')
        lab = rgb2lab(images.float())
        features = (downsample_lab(lab, 16) / torch.tensor([40., 20., 20.])).flatten(1)
        with torch.random.fork_rng():
            torch.manual_seed(seed)
            centres, assignment = kmeans(features, min(clusters, len(images) // min_members), 25, seed)
            # Merge small populations; no single-image prototype may survive.
            while len(centres) > 1:
                counts = torch.bincount(assignment, minlength=len(centres))
                if int(counts.min()) >= min_members:
                    break
                keep = torch.arange(len(centres)) != counts.argmin()
                centres = centres[keep]
                assignment = torch.cdist(features, centres).argmin(1)
            effective_rank = min(rank, int(torch.bincount(assignment, minlength=len(centres)).min()) - 2)
            means, bases, scales, counts = [], [], [], []
            for k in range(len(centres)):
                x = lab[assignment == k].flatten(1)
                mean = x.mean(0)
                centred = x - mean
                actual_rank = effective_rank
                _, singular, basis = torch.pca_lowrank(centred, q=actual_rank + 2, center=False, niter=3)
                means.append(mean)
                bases.append(basis[:, :actual_rank].T.contiguous())
                scales.append(singular[:actual_rank] / math.sqrt(len(x) - 1))
                counts.append(len(x))
        return cls(dict(format='cael-mixture-pca-structure-v1', means=torch.stack(means),
                        bases=torch.stack(bases), scales=torch.stack(scales),
                        counts=torch.tensor(counts), size=64, rank=effective_rank, fit_seed=seed,
                        min_members=min_members, source_images_stored=False))

    def sample(self, batch, seed, variation=0.85):
        if batch < 1 or not math.isfinite(variation) or variation < 0:
            raise ValueError('Need a positive batch and finite nonnegative variation')
        generator = torch.Generator().manual_seed(seed)
        counts = self.state['counts'].float()
        populations = torch.multinomial(counts / counts.sum(), batch, replacement=True, generator=generator)
        coefficients = torch.randn(batch, self.state['bases'].shape[1], generator=generator).clamp(-2, 2)
        coefficients *= self.state['scales'][populations] * variation
        lab = self.state['means'][populations] + torch.einsum('br,brd->bd', coefficients, self.state['bases'][populations])
        lab = lab.reshape(batch, 64, 64, 3)
        lab[..., 0].clamp_(0, 100)
        lab[..., 1:].clamp_(-100, 100)
        return lab, populations


def shape_probabilities(palette, field, sigma):
    if sigma <= 0:
        raise ValueError('Structure bandwidth must be positive')
    distance = ((field[..., None, :] - palette) ** 2).sum(-1)
    # Subtract the best distance before exp to avoid underflow.
    scores = -(distance - distance.min(-1, keepdim=True).values) / (2 * sigma ** 2)
    return torch.softmax(scores, -1)


def generate_structured(model, structure, batch, seed, mix=0.85, sigma=10., variation=0.85):
    """Same sampled whole-face field persists through all scales and sweeps."""
    if not 0 <= mix <= 1:
        raise ValueError('Structure mixing mass must be between 0 and 1')
    field, populations = structure.sample(batch, seed, variation)
    generator = torch.Generator(device=model.dev).manual_seed(seed)
    weights = {L: shape_probabilities(model.pal, downsample_lab(field, L).to(model.dev), sigma)
               for L in (4, 8, 16, 32, 64)}
    def draw(local, L, temp):
        local = local.float().clamp_min(0)
        local = local / local.sum(-1, keepdim=True).clamp_min(1e-12)
        prob = (1 - mix) * local + mix * weights[L]
        # Apply original temperatures, without the separate luminance tilt.
        return _draw(prob, temp, generator)
    pos = model.pos(4).expand(batch, 4, 4)
    grid = draw(model.seed['sp'][pos] + 1e-3, 4, 1.)
    temperatures = (1., 1., .85, .6, .4)
    sweeps = (8, 6, 6, 6, 8)
    check = (model.quad(4) == 0) | (model.quad(4) == 3)
    for it in range(sweeps[0] * 2):
        counts = model.seed['sf'][pos * model.Q ** 4 + model.k4(grid)].float()
        back = model.seed['sp'][pos].float() + 1e-3
        rows = torch.where(counts.sum(-1, keepdim=True) >= model.minc, counts, back)
        grid = torch.where(check == (it % 2 == 0), draw(rows, 4, temperatures[0]), grid)
    for i, L in enumerate((8, 16, 32, 64), 1):
        parent = grid
        tables = model.t[L]
        grid = draw(model.rows(tables, model.keys(L, parent)), L, temperatures[i])
        check = (model.quad(L) == 0) | (model.quad(L) == 3)
        for it in range(sweeps[i] * 2):
            rows = model.rows(tables, model.keys(L, parent, grid))
            grid = torch.where(check == (it % 2 == 0), draw(rows, L, temperatures[i]), grid)
    return lab2rgb(model.pal[grid]).cpu(), populations


def _draw(probability, temperature, generator):
    probability = probability.clamp_min(1e-12) ** (1 / temperature)
    flat = probability.flatten(0, -2)
    return torch.multinomial(flat / flat.sum(-1, keepdim=True), 1, generator=generator).reshape(probability.shape[:-1])


def generate_guarded(model, structure, batch, seed, references, threshold=.12, max_attempts=8, **settings):
    """Reject overly similar samples using private fitting pixels in memory only.

    References never enter the synthesis routine. A failed guard raises instead
    of returning rejected images. This RMS cutoff is a heuristic, not a proof
    of anonymity or lack of memorisation.
    """
    from cael_image.v4_multiscale_ca import nn as nearest
    images, populations = generate_structured(model, structure, batch, seed, **settings)
    distances = nearest(images, references)
    attempts, replacements = 0, 0
    while bool((distances < threshold).any()) and attempts < max_attempts:
        bad = torch.nonzero(distances < threshold).flatten()
        attempts += 1
        replacement, new_populations = generate_structured(
            model, structure, len(bad), seed + 7919 * attempts, **settings)
        images[bad], populations[bad] = replacement, new_populations
        distances[bad] = nearest(replacement, references)
        replacements += len(bad)
    if bool((distances < threshold).any()):
        raise RuntimeError('Similarity guard exhausted its retries; no accepted batch returned')
    return images, dict(replacements=replacements, rounds=attempts,
                        nearest_RMS=[round(float(x), 6) for x in distances])


def load_checkpoint(path):
    """Load the self-contained structure prior and inherited CA counts on CPU."""
    from cael_assistant import imagegen as ig
    from cael_image.portrait_sampling import CompactRows
    state = torch.load(path, map_location='cpu', weights_only=True)
    if state['format'] != 'cael-portrait-structure-v13':
        raise ValueError('Unsupported structure checkpoint format')
    base = state['base_checkpoint']
    a = base['args']
    model = ig.v10.GCA10(torch.device('cpu'), a['palette'], a['coarse'], a['buckets'], a['min_count'])
    model.pal, model.coarse = base['palette_lab'], base['coarse']
    model.seed = base['seed']
    model.t = {L: {k: CompactRows(t, 'cpu') for k, t in tables.items()} for L, tables in base['tables'].items()}
    model.prior = base['conditioning']['prior']
    model.sym = base['conditioning']['sym']
    return model, StructurePrior(state['structure']), state


def load_guard_references(guard):
    """Blindly read frozen fitting photos for numerical rejection only."""
    from pathlib import Path
    from cael_image.train_portrait_update import load_snapshot
    root = Path(guard['root'])
    faces = guard['structure_face_boxes']
    aligned_records = [r for r in guard['training_records'] if r['image'] in faces]
    aligned = load_snapshot(root, aligned_records, 'fit', faces, 1.8)
    original = load_snapshot(root, guard['training_records'], 'fit', guard['base_face_boxes'], 1.6)
    references = [aligned, original]
    for additional in guard.get('additional_training_sets', []):
        references.append(load_snapshot(Path(additional['root']), additional['training_records'], 'fit'))
    return torch.cat(references)
