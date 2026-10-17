"""Generate portraits from an explicit self-contained CA checkpoint."""
import argparse
import json
from pathlib import Path
import sys

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_assistant import imagegen as ig


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model', required=True, help='Folder containing model_v9.pt with embedded conditioning')
    ap.add_argument('--prompt', default='a person with eyes closed')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--n', type=int, default=4)
    ap.add_argument('--oversample', type=int, default=3)
    ap.add_argument('--device', default='cpu', choices=['cpu', 'cuda'])
    ap.add_argument('--caption-strength', type=float, default=0.5)
    a = ap.parse_args()
    if a.n < 1 or a.oversample < 1 or not 0 <= a.caption_strength <= 1:
        ap.error('Need positive n/oversample and caption strength between 0 and 1')
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    # Match caption keys in deterministic order, including supported bigrams.
    from cael_image.train_portrait_update import caption_keys
    tool = ig.ImageTool(device=torch.device(a.device), model_dir=Path(a.model).resolve())
    info, _, _ = tool.generate(sorted(caption_keys(a.prompt)), n=a.n, oversample=a.oversample,
                               seed=a.seed, gamma=a.caption_strength, outdir=out, tag='portrait')
    info.update(model=str(Path(a.model).resolve()), prompt=a.prompt,
                conditioning='Weak count-learned caption priors plus sample ranking',
                luminance_bias=tool.m.luminance_bias)
    (out / 'generation.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
