"""Generate with the v13 non-neural structural prior and guarded CA sampler."""
import argparse
import json
from pathlib import Path
import sys

import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.portrait_structure import load_checkpoint, load_guard_references, generate_guarded
from cael_assistant.eval_portrait_sampling import save_grid, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='models/cael-portrait-64-v13-structure/model_v13.pt')
    parser.add_argument('--out', required=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--n', type=int, default=4)
    args = parser.parse_args()
    if args.n < 1:
        parser.error('n must be positive')
    torch.set_num_threads(4)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    model, structure, state = load_checkpoint(args.model)
    references = load_guard_references(state['source_guard'])
    images, checks = [], []
    for i in range(0, args.n, 4):
        G, check = generate_guarded(model, structure, min(4, args.n - i), args.seed + i,
                                    references, threshold=state['source_guard']['threshold'],
                                    max_attempts=state['source_guard']['max_attempts'], **state['settings'])
        images.append(G)
        checks.append(check)
    G = torch.cat(images)
    paths = []
    for i, pixels in enumerate(G.numpy()):
        path = out / f'portrait_{i:02d}_64.png'
        Image.fromarray(pixels).save(path)
        paths.append(str(path))
    save_grid(G, out / 'grid.png', columns=min(4, len(G)))
    info = dict(model=str(Path(args.model).resolve()), model_sha256=sha256(args.model),
                seed=args.seed, batch=4, paths=paths, grid=str(out / 'grid.png'),
                sampler=state['settings'], guard_checks=checks,
                architecture='Non-neural mixture/PCA whole-face prior plus integer-count cellular sampling',
                caption_conditioning=False, source_photos_displayed=False,
                source_photos_read_blindly_for_numerical_guard=True)
    (out / 'generation.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
