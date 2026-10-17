"""Generate with the non-neural registered appearance branch; guarded, CPU only."""
import argparse
import json
from pathlib import Path
import sys

import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.portrait_appearance import load_eye_aligned, sample_guarded_appearance
from cael_image.portrait_structure import load_guard_references
from cael_image.portrait_deformation import DeformationPrior
from cael_assistant.eval_portrait_sampling import save_grid, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='models/cael-portrait-64-v15-appearance/model_v15.pt')
    parser.add_argument('--out', required=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--n', type=int, default=4)
    args = parser.parse_args()
    if args.n < 1:
        parser.error('n must be positive')
    torch.set_num_threads(4)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    checkpoint = torch.load(args.model, map_location='cpu', weights_only=True)
    if checkpoint['format'] not in ('cael-portrait-appearance-v15', 'cael-portrait-appearance-v17', 'cael-portrait-appearance-v18'):
        raise ValueError('Unsupported appearance model format')
    settings = checkpoint['settings']
    prior = DeformationPrior(checkpoint['prior'], warp_strength=settings['warp_strength'])
    references = torch.cat([load_guard_references(checkpoint['source_guard']), load_eye_aligned(checkpoint['alignment'])])
    images, checks = [], []
    for i in range(0, args.n, 4):
        G, check = sample_guarded_appearance(prior, min(4, args.n - i), args.seed + i, references,
                                            variation=settings['variation'], sharpen=settings['sharpen'])
        images.append(G)
        checks.append(check)
    G = torch.cat(images)
    paths = []
    for i, pixels in enumerate(G.numpy()):
        path = out / f'portrait_{i:02d}_64.png'
        Image.fromarray(pixels).save(path)
        paths.append(str(path))
    save_grid(G, out / 'grid.png', columns=min(4, args.n))
    info = dict(paths=paths, grid=str(out / 'grid.png'), seed=args.seed, batch=4,
                model_sha256=sha256(args.model), settings=settings, guard_checks=checks,
                architecture='Non-neural registered joint shape/appearance statistics; continuous renderer',
                neural_network=False, pixel_CA=False, source_photos_displayed=False,
                source_photos_read_blindly_for_similarity_guard=True)
    (out / 'generation.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
