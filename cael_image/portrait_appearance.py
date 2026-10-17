"""Non-neural eye-aligned appearance experiments; source photos never displayed."""
import hashlib
from pathlib import Path

import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image, ImageOps

from cael_image.v6_region_ca import lab2rgb


def align_similarity(rgb, left, right, target_left, target_right, output_size=64):
    """Resample RGB so two detected points map to learned reference positions."""
    left, right = torch.tensor(left).float(), torch.tensor(right).float()
    tl, tr = torch.tensor(target_left).float(), torch.tensor(target_right).float()
    d, target_d = right - left, tr - tl
    denom = (d * d).sum()
    if float(denom) < 1:
        raise ValueError('Detected alignment points are too close')
    c = (d * target_d).sum() / denom
    s = (target_d[1] * d[0] - target_d[0] * d[1]) / denom
    matrix = torch.stack([torch.stack([c, -s]), torch.stack([s, c])])
    translation = tl - matrix @ left
    y, x = torch.meshgrid(torch.arange(output_size), torch.arange(output_size), indexing='ij')
    source = (torch.stack([x, y], -1).float() - translation) @ torch.linalg.inv(matrix).T
    h, w = rgb.shape[:2]
    source[..., 0] = source[..., 0] * 2 / max(w - 1, 1) - 1
    source[..., 1] = source[..., 1] * 2 / max(h - 1, 1) - 1
    tensor = torch.from_numpy(np.array(rgb, copy=True)).float().permute(2, 0, 1)[None]
    result = F.grid_sample(tensor, source[None], mode='bicubic', padding_mode='border', align_corners=True)
    return result[0].permute(1, 2, 0).round().clamp(0, 255).to(torch.uint8)


def load_eye_aligned(alignment):
    images = []
    root = Path(alignment['root'])
    for name, record in alignment['pairs'].items():
        path = root / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['image_file_sha256']:
            raise RuntimeError('Frozen fitting image changed: ' + name)
        with Image.open(path) as image:
            rgb = np.asarray(ImageOps.exif_transpose(image).convert('RGB'))
        images.append(align_similarity(rgb, record['left'], record['right'],
                                       alignment['target_left'], alignment['target_right']))
    return torch.stack(images)


def continuous_render(field, sharpen=0.):
    """Render sampled Lab with optional conventional luminance unsharp mask."""
    if sharpen:
        L = field[..., 0][:, None]
        kernel = torch.tensor([[1., 2, 1], [2, 4, 2], [1, 2, 1]])[None, None] / 16
        low = F.conv2d(F.pad(L, (1, 1, 1, 1), mode='replicate'), kernel)
        field = field.clone()
        field[..., 0] = (L + sharpen * (L - low))[:, 0].clamp(0, 100)
    return lab2rgb(field)


def sample_guarded_appearance(prior, batch, seed, references, variation=.85, sharpen=0., threshold=.12, max_attempts=8):
    from cael_image.v4_multiscale_ca import nn as nearest
    def draw(count, draw_seed):
        field, _ = prior.sample(count, draw_seed, variation)
        return continuous_render(field, sharpen)
    G = draw(batch, seed)
    distances = nearest(G, references)
    attempts, replacements = 0, 0
    while bool((distances < threshold).any()) and attempts < max_attempts:
        bad = torch.nonzero(distances < threshold).flatten()
        attempts += 1
        new = draw(len(bad), seed + 7919 * attempts)
        G[bad] = new
        distances[bad] = nearest(new, references)
        replacements += len(bad)
    if bool((distances < threshold).any()):
        raise RuntimeError('Appearance similarity guard exhausted its retries')
    return G, dict(replacements=replacements, rounds=attempts,
                   nearest_RMS=[round(float(d), 6) for d in distances])
