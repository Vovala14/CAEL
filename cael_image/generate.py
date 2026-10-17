"""Generate one 64x64 image using a trained non-neural CAEL image checkpoint."""
import argparse
import json
from pathlib import Path
import sys

from .model import generate_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prompt')
    parser.add_argument('--model', type=Path, default=Path(__file__).resolve().parents[1] / 'models/cael-image-female-64-v2/model.npz')
    parser.add_argument('--output', type=Path, default=Path('outputs/female-character.png'))
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--steps', type=int)
    parser.add_argument('--noise', type=int)
    parser.add_argument('--sampler', choices=['stable', 'legacy'], default='stable')
    args = parser.parse_args()
    try:
        result = generate_file(args.model, args.prompt, args.output, args.seed, args.steps, args.noise, args.sampler)
    except (ValueError, OSError, ImportError) as exc:
        print('CAEL image generation: ' + str(exc), file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(dict(output=str(args.output.resolve()), **result), indent=2))


if __name__ == '__main__':
    main()
