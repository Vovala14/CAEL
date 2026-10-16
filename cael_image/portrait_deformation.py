"""Classical optical-flow registration and joint shape/appearance statistics.

No source photo or individual coefficient vector is retained. OpenCV is needed
only for fitting; generation uses tensor resampling and sampled aggregate modes.
"""
import math

import numpy as np
import torch
import torch.nn.functional as F

from cael_image.portrait_sampling import downsample_lab
from cael_image.v6_region_ca import rgb2lab, lab2rgb


class DeformationPrior:
    def __init__(self, state, warp_strength=.6, latent_ca=False):
        self.state, self.warp_strength, self.latent_ca = state, warp_strength, latent_ca

    @classmethod
    def fit(cls, images, population_means, rank=8, seed=150016):
        import cv2
        lab = rgb2lab(images.float())
        scale = torch.tensor([40., 20., 20.])
        features = (downsample_lab(lab, 16) / scale).flatten(1)
        centres = (downsample_lab(population_means.reshape(-1, 64, 64, 3), 16) / scale).flatten(1)
        assignment = torch.cdist(features, centres).argmin(1)
        while len(centres) > 1:
            counts = torch.bincount(assignment, minlength=len(centres))
            if int(counts.min()) >= 16:
                break
            centres = centres[torch.arange(len(centres)) != counts.argmin()]
            assignment = torch.cdist(features, centres).argmin(1)
        means, bases, deviations, sizes, latent_statistics = [], [], [], [], []
        y, x = np.mgrid[0:64, 0:64].astype(np.float32)
        with torch.random.fork_rng():
            torch.manual_seed(seed)
            for k in range(int(assignment.max()) + 1):
                source = images[assignment == k].numpy()
                registered = source.astype(np.float32)
                flows = []
                for iteration in range(2):
                    template = registered.mean(0).clip(0, 255).astype(np.uint8)
                    grey_template = cv2.equalizeHist(cv2.cvtColor(template, cv2.COLOR_RGB2GRAY))
                    registered, flows = [], []
                    for rgb in source:
                        grey = cv2.equalizeHist(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
                        flow = cv2.calcOpticalFlowFarneback(grey_template, grey, None, .5, 3, 15, 6, 7, 1.5,
                                                          cv2.OPTFLOW_FARNEBACK_GAUSSIAN)
                        flow = cv2.GaussianBlur(flow, (3, 3), .6).clip(-4, 4)
                        registered.append(cv2.remap(rgb.astype(np.float32), x + flow[..., 0], y + flow[..., 1],
                                                    cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE))
                        flows.append(flow)
                    registered = np.stack(registered)
                appearance = rgb2lab(torch.from_numpy(registered).clamp(0, 255)) / scale
                values = torch.cat([appearance.flatten(1), torch.from_numpy(np.stack(flows)).flatten(1) / 4], 1)
                mean = values.mean(0)
                _, singular, basis = torch.pca_lowrank(values - mean, q=rank + 2, center=False, niter=3)
                means.append(mean)
                bases.append(basis[:, :rank].T.contiguous())
                deviations.append(singular[:rank] / math.sqrt(len(values) - 1))
                sizes.append(len(values))
                if rank == 8:
                    from cael_image.portrait_latent_ca import compile_latent_counts
                    z = ((values - mean) @ basis[:, :rank]) / deviations[-1].clamp_min(1e-6)
                    latent_statistics.append(compile_latent_counts(z))
        return cls(dict(format='cael-shape-appearance-pca-v1', means=torch.stack(means),
                        bases=torch.stack(bases), scales=torch.stack(deviations), counts=torch.tensor(sizes),
                        rank=rank, fit_seed=seed, source_images_stored=False, flow_limit=4.,
                        latent_statistics=latent_statistics))

    def sample(self, batch, seed, variation=.85):
        if batch < 1 or not math.isfinite(variation) or variation < 0:
            raise ValueError('Need a positive batch and finite nonnegative variation')
        generator = torch.Generator().manual_seed(seed)
        counts = self.state['counts'].float()
        populations = torch.multinomial(counts / counts.sum(), batch, replacement=True, generator=generator)
        coefficients = torch.randn(batch, self.state['rank'], generator=generator).clamp(-2, 2)
        if self.latent_ca:
            from cael_image.portrait_latent_ca import sample_latent_ca
            for population in populations.unique().tolist():
                selected = populations == population
                coefficients[selected] = sample_latent_ca(self.state['latent_statistics'][population], int(selected.sum()), generator)
        coefficients *= self.state['scales'][populations] * variation
        values = self.state['means'][populations] + torch.einsum('br,brd->bd', coefficients, self.state['bases'][populations])
        lab = values[:, :64 * 64 * 3].reshape(batch, 64, 64, 3) * torch.tensor([40., 20., 20.])
        flow = (values[:, 64 * 64 * 3:].reshape(batch, 64, 64, 2) * 4).clamp(-4, 4) * self.warp_strength
        lab[..., 0].clamp_(0, 100)
        lab[..., 1:].clamp_(-100, 100)
        return invert_deformation(lab, flow), populations


def invert_deformation(field, flow, iterations=5):
    """Render a canonical field in a sampled shape by inverting its displacement."""
    batch, h, w, _ = field.shape
    y, x = torch.meshgrid(torch.arange(h), torch.arange(w), indexing='ij')
    target = torch.stack([x, y], -1).float()[None].expand(batch, -1, -1, -1)
    coordinates = target.clone()
    def norm(points):
        return points / torch.tensor([max(w - 1, 1), max(h - 1, 1)]) * 2 - 1
    for _ in range(iterations):
        displacement = F.grid_sample(flow.permute(0, 3, 1, 2), norm(coordinates),
                                     padding_mode='border', align_corners=True).permute(0, 2, 3, 1)
        coordinates = target - displacement
    return F.grid_sample(field.permute(0, 3, 1, 2), norm(coordinates),
                         mode='bicubic', padding_mode='border', align_corners=True).permute(0, 2, 3, 1)
