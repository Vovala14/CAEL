"""Integer-count CA for 2x2 luminance detail, guided by a sampled coarse field.

Each cell contains one learned residual-patch category. Synchronous checkerboard
updates read four adjacent cells and context from the fixed sampled shape.
Codebook centroids and transition counts are aggregates; no source patches are
retrieved at inference. This adds local detail, not new semantic understanding.
"""
import torch
import torch.nn.functional as F

from .v6_region_ca import rgb2lab, kmeans


def patches(luminance):
    b, size, _ = luminance.shape
    return luminance.reshape(b, size // 2, 2, size // 2, 2).permute(0, 1, 3, 2, 4).reshape(b, size // 2, size // 2, 4)


def context(luminance):
    low = F.avg_pool2d(F.pad(luminance[:, None], (2, 2, 2, 2), mode='replicate'), 5, stride=1)[:, 0]
    cells = patches(low)
    dx = (cells[..., 1] + cells[..., 3] - cells[..., 0] - cells[..., 2]) / 2
    dy = (cells[..., 2] + cells[..., 3] - cells[..., 0] - cells[..., 1]) / 2
    direction = (((torch.atan2(dy, dx) + torch.pi) / (2 * torch.pi) * 8).long() % 8)
    strength = torch.bucketize((dx.square() + dy.square()).sqrt().contiguous(), torch.tensor([.3, 1., 2.5, 5., 10., 20.]))
    return direction * 7 + strength


def neighbours(grid, boundary):
    previous = F.pad(grid[:, None].float(), (1, 1, 1, 1), value=boundary)[:, 0].long()
    return (previous[:, :-2, 1:-1], previous[:, 1:-1, 2:], previous[:, 2:, 1:-1], previous[:, 1:-1, :-2])


class DetailCA:
    def __init__(self, state):
        self.state = state

    @classmethod
    def fit(cls, images, classes=32, seed=220022):
        luminance = rgb2lab(images.float())[..., 0]
        cells = patches(luminance)
        residual = cells - cells.mean(-1, keepdim=True)
        flat = residual.reshape(-1, 4)
        gen = torch.Generator().manual_seed(seed)
        sample = flat[torch.randint(len(flat), (min(80000, len(flat)),), generator=gen)]
        centres, _ = kmeans(sample, classes, 15, seed)
        centres -= centres.mean(-1, keepdim=True)
        labels = torch.cat([torch.cdist(batch, centres).argmin(1) for batch in flat.split(65536)]).reshape(cells.shape[:-1])
        ctx = context(luminance)
        counts = torch.zeros(56, classes, dtype=torch.int32)
        counts.view(-1).index_add_(0, ctx.flatten() * classes + labels.flatten(), torch.ones(labels.numel(), dtype=torch.int32))
        pairs = torch.zeros(4, classes + 1, classes, dtype=torch.int32)
        for direction, other in enumerate(neighbours(labels, classes)):
            pairs[direction].view(-1).index_add_(0, other.flatten() * classes + labels.flatten(), torch.ones(labels.numel(), dtype=torch.int32))
        return cls(dict(format='cael-luminance-detail-ca-v1', codebook=centres, context_counts=counts, pairs=pairs,
                        source_patches_stored=False, classes=classes, fitting_images=len(images), seed=seed))

    def apply(self, field, seed, strength=.55, sweeps=4):
        if not 0 <= strength <= 1:
            raise ValueError('Detail strength must be between zero and one')
        if strength == 0:
            return field
        b, size, _, _ = field.shape
        classes = self.state['classes']
        ctx = context(field[..., 0])
        counts = self.state['context_counts'].float() + .25
        prior = counts[ctx]
        base = counts.sum(0)
        base /= base.sum()
        gen = torch.Generator().manual_seed(seed)
        grid = torch.multinomial(prior.flatten(0, 2), 1, generator=gen).reshape(ctx.shape)
        y, x = torch.meshgrid(torch.arange(size // 2), torch.arange(size // 2), indexing='ij')
        parity = (y + x) % 2
        for _ in range(sweeps):
            for part in (0, 1):
                # Every updated cell reads one frozen previous lattice.
                previous = grid.clone()
                weight = prior.clone()
                for direction, other in enumerate(neighbours(previous, classes)):
                    pair = self.state['pairs'][direction, other].float() + .25
                    conditional = pair / pair.sum(-1, keepdim=True)
                    weight *= (conditional / base).clamp(.25, 4.) ** .2
                sampled = torch.multinomial(weight.flatten(0, 2), 1, generator=gen).reshape(grid.shape)
                grid = torch.where((parity == part)[None], sampled, grid)
        detail = self.state['codebook'][grid].reshape(b, size // 2, size // 2, 2, 2).permute(0, 1, 3, 2, 4).reshape(b, size, size)
        # Do not erase the sampled shape; only add bounded zero-mean cell detail.
        output = field.clone()
        output[..., 0] = (output[..., 0] + detail.clamp(-10, 10) * strength).clamp(0, 100)
        return output
