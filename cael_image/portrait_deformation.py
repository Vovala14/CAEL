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
    def __init__(self, state, warp_strength=.6, latent_ca=False, latent_joint_seed=False, safe_warp=False):
        self.state, self.warp_strength, self.latent_ca = state, warp_strength, latent_ca
        self.latent_joint_seed = latent_joint_seed
        self.safe_warp = safe_warp

    @classmethod
    def fit(cls, images, population_means, rank=8, seed=150016, population_assignments=None, medoid_frame=False, minimum_population=16):
        import cv2
        lab = rgb2lab(images.float())
        scale = torch.tensor([40., 20., 20.])
        size = images.shape[1]
        if images.ndim != 4 or images.shape[1:3] != (size, size) or size % 16:
            raise ValueError('Expected square fitting images divisible by sixteen')
        features = (downsample_lab(lab, 16) / scale).flatten(1)
        centres = (downsample_lab(population_means.reshape(-1, size, size, 3), 16) / scale).flatten(1)
        assignment = torch.cdist(features, centres).argmin(1) if population_assignments is None else population_assignments.long()
        if assignment.shape != (len(images),) or int(assignment.min()) < 0:
            raise ValueError('Invalid fitting population assignment')
        while population_assignments is None and len(centres) > 1:
            counts = torch.bincount(assignment, minlength=len(centres))
            if int(counts.min()) >= max(minimum_population, rank + 3):
                break
            centres = centres[torch.arange(len(centres)) != counts.argmin()]
            assignment = torch.cdist(features, centres).argmin(1)
        means, bases, deviations, sizes, latent_statistics = [], [], [], [], []
        y, x = np.mgrid[0:size, 0:size].astype(np.float32)
        flow_limit = 4. * size / 64
        with torch.random.fork_rng():
            torch.manual_seed(seed)
            for k in range(int(assignment.max()) + 1):
                source = images[assignment == k].numpy()
                if len(source) < rank + 3:
                    raise ValueError('Population too small for the requested rank')
                registered = source.astype(np.float32)
                flows = []
                medoid = None
                if medoid_frame:
                    cluster = features[assignment == k]
                    medoid = int(torch.cdist(cluster, cluster).sum(1).argmin())
                for iteration in range(2):
                    template = source[medoid] if medoid_frame and iteration == 0 else registered.mean(0).clip(0, 255).astype(np.uint8)
                    grey_template = cv2.equalizeHist(cv2.cvtColor(template, cv2.COLOR_RGB2GRAY))
                    registered, flows = [], []
                    for rgb in source:
                        grey = cv2.equalizeHist(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
                        flow = cv2.calcOpticalFlowFarneback(grey_template, grey, None, .5, 3, 15, 6, 7, 1.5,
                                                          cv2.OPTFLOW_FARNEBACK_GAUSSIAN)
                        flow = cv2.GaussianBlur(flow, (3, 3), .6).clip(-flow_limit, flow_limit)
                        registered.append(cv2.remap(rgb.astype(np.float32), x + flow[..., 0], y + flow[..., 1],
                                                    cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE))
                        flows.append(flow)
                    registered = np.stack(registered)
                appearance = rgb2lab(torch.from_numpy(registered).clamp(0, 255)) / scale
                values = torch.cat([appearance.flatten(1), torch.from_numpy(np.stack(flows)).flatten(1) / flow_limit], 1)
                mean = values.mean(0)
                _, singular, basis = torch.pca_lowrank(values - mean, q=rank + 2, center=False, niter=3)
                means.append(mean)
                bases.append(basis[:, :rank].T.contiguous())
                deviations.append(singular[:rank] / math.sqrt(len(values) - 1))
                sizes.append(len(values))
                if rank % 4 == 0:
                    from cael_image.portrait_latent_ca import compile_latent_counts
                    z = ((values - mean) @ basis[:, :rank]) / deviations[-1].clamp_min(1e-6)
                    latent_statistics.append(compile_latent_counts(z))
        return cls(dict(format='cael-shape-appearance-pca-v1', means=torch.stack(means),
                        bases=torch.stack(bases), scales=torch.stack(deviations), counts=torch.tensor(sizes),
                        rank=rank, fit_seed=seed, source_images_stored=False, flow_limit=flow_limit,
                        image_size=size,
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
                coefficients[selected] = sample_latent_ca(self.state['latent_statistics'][population], int(selected.sum()), generator,
                                                          joint_seed=self.latent_joint_seed)
        coefficients *= self.state['scales'][populations] * variation
        values = self.state['means'][populations] + torch.einsum('br,brd->bd', coefficients, self.state['bases'][populations])
        size = self.state.get('image_size', 64)
        lab = values[:, :size * size * 3].reshape(batch, size, size, 3) * torch.tensor([40., 20., 20.])
        limit = self.state.get('flow_limit', 4.)
        flow = (values[:, size * size * 3:].reshape(batch, size, size, 2) * limit).clamp(-limit, limit) * self.warp_strength
        if self.safe_warp:
            flow = F.avg_pool2d(F.pad(flow.permute(0, 3, 1, 2), (3, 3, 3, 3), mode='replicate'), 7, stride=1).permute(0, 2, 3, 1)
            dx = (flow[:, :, 1:] - flow[:, :, :-1]).abs().flatten(1).amax(1)
            dy = (flow[:, 1:] - flow[:, :-1]).abs().flatten(1).amax(1)
            # Bound the displacement Jacobian so inversion cannot fold the grid.
            factor = (.8 / (dx + dy).clamp_min(.8)).clamp_max(1)
            flow = flow * factor[:, None, None, None]
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
