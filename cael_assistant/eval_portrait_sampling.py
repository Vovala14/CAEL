"""Compare i16 brightness calibration using saved counts only, on the local CPU.

No source images are read, rendered, copied, or uploaded. Diagnostics cannot
establish face quality, prompt following, or nearest-training-image distance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image, ImageDraw
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_assistant import imagegen as ig


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def diagnostics(images):
    f = images.cpu().float()
    lab = ig.v9.rgb2lab(f)
    grey = f.mean(-1)
    edges = [((grey[:, :, 1:] - grey[:, :, :-1]).abs() > 24).float().mean(),
             ((grey[:, 1:] - grey[:, :-1]).abs() > 24).float().mean()]
    pair = torch.triu_indices(len(f), len(f), offset=1)
    diversity = (f[pair[0]] - f[pair[1]]).abs().mean()
    return dict(mean_lab=[round(float(v), 4) for v in lab.mean((0, 1, 2))],
                pairwise_L1=round(float(diversity), 4),
                edge_density=round(float(torch.stack(edges).mean()), 4))


def generate(model, n, seed, bias, batch):
    model.luminance_bias = bias
    # Fixed batch schedule for every candidate, since batch size affects the RNG.
    return torch.cat([model.generate(min(batch, n - i), seed + i).cpu()
                      for i in range(0, n, batch)])


def save_grid(images, path, columns=8):
    pixels = images.cpu().numpy()
    rows = (len(pixels) + columns - 1) // columns
    grid = np.zeros((rows * 64, columns * 64, 3), dtype=np.uint8)
    for i, x in enumerate(pixels):
        y, col = divmod(i, columns)
        grid[y * 64:(y + 1) * 64, col * 64:(col + 1) * 64] = x
    Image.fromarray(grid).resize((columns * 128, rows * 128), Image.Resampling.NEAREST).save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('--pilot', type=int, default=16)
    ap.add_argument('--samples', type=int, default=32)
    ap.add_argument('--batch', type=int, default=4)
    ap.add_argument('--biases', default='0,0.1,0.2,0.3')
    ap.add_argument('--threads', type=int, default=4)
    a = ap.parse_args()
    if a.pilot < 2 or a.samples < 2 or a.batch < 1:
        ap.error('pilot/samples must be >=2 and batch must be >=1')
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(a.threads)
    start = time.time()
    protocol = dict(args=vars(a), pilot_seed=16102026, evaluation_seed=27102026,
                    selection='Minimum absolute mean L* error against saved training prior; ties prefer smaller absolute bias',
                    source_photos_accessed=False, neural_network_used=False,
                    limitation='Aggregate training-count calibration and new generated seeds; no new held-out photo evaluation or face-quality claim')
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    print('Loading i16 compact count tables on CPU', flush=True)
    tool = ig.ImageTool(device=torch.device('cpu'))
    model = tool.ensure()
    cnt = model.prior[64].double().sum(0)
    target = float((cnt * model.pal[:, 0].double()).sum() / cnt.sum())
    print(f'Loaded in {time.time() - start:.1f}s; training-prior target L* {target:.3f}', flush=True)
    pilots = []
    for bias in sorted(set(float(x) for x in a.biases.split(',')) | {0.0}):
        g = generate(model, a.pilot, protocol['pilot_seed'], bias, a.batch)
        row = dict(bias=bias, **diagnostics(g))
        row['lightness_error'] = abs(row['mean_lab'][0] - target)
        pilots.append(row)
        print('PILOT', json.dumps(row), flush=True)
        (out / 'pilots.json').write_text(json.dumps(pilots, indent=2), encoding='utf-8')
        save_grid(g, out / f'pilot_{bias:g}.png')
    chosen = min(pilots, key=lambda row: (row['lightness_error'], abs(row['bias'])))['bias']
    (out / 'selection.json').write_text(json.dumps(dict(bias=chosen, target_lightness=target)), encoding='utf-8')
    # Freeze selection before the separate generated evaluation seeds.
    report = dict(protocol=protocol, target_lightness=target, selected_bias=chosen, pilots=pilots,
                  model_sha256=sha256(ig.MODEL / 'model_v9.pt'), counts_sha256=sha256(ig.COND), evaluation={})
    panels = []
    for name, bias in [('baseline', 0.0), ('calibrated', chosen)]:
        g = generate(model, a.samples, protocol['evaluation_seed'], bias, a.batch)
        report['evaluation'][name] = diagnostics(g)
        save_grid(g, out / f'{name}_grid.png')
        for i, pixels in enumerate(g[:8].numpy()):
            Image.fromarray(pixels).save(out / f'{name}_{i:02d}_64.png')
        panels.append(g[:8])
        print('EVALUATION', name, json.dumps(report['evaluation'][name]), flush=True)
    # Same seeds: baseline on top, calibrated below. Labels are outside the pixels.
    canvas = Image.new('RGB', (8 * 128, 2 * 154), 'white')
    draw = ImageDraw.Draw(canvas)
    for row, (label, samples) in enumerate(zip(['i16 baseline', f'i16 calibrated (bias={chosen:g})'], panels)):
        draw.text((4, row * 154 + 4), label, fill='black')
        for col, pixels in enumerate(samples.numpy()):
            canvas.paste(Image.fromarray(pixels).resize((128, 128), Image.Resampling.NEAREST), (col * 128, row * 154 + 24))
    canvas.save(out / 'comparison.png')
    report['seconds'] = round(time.time() - start, 1)
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', out, flush=True)


if __name__ == '__main__':
    main()
