"""Bounded face-structure experiment: source photos processed blindly."""
import argparse
import json
from pathlib import Path
import sys
import time

import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_assistant import imagegen as ig
from cael_assistant.eval_portrait_sampling import generate, save_grid, diagnostics, sha256
from cael_image.train_portrait_update import load_snapshot
from cael_image.portrait_structure import StructurePrior, generate_structured
from cael_image.v6_region_ca import lab2rgb
from cael_image.v4_multiscale_ca import nn as nearest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--base', default='models/cael-portrait-64-v12-522')
    parser.add_argument('--faces', default='research/portrait_structure_train_faces_20261016.json')
    parser.add_argument('--samples', type=int, default=16)
    args = parser.parse_args()
    torch.set_num_threads(4)
    start = time.time()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    def write(name, value):
        (out / name).write_text(json.dumps(value, indent=2), encoding='utf-8')
    base = Path(args.base).resolve()
    manifest = json.loads((base / 'data_manifest.json').read_text())
    faces = json.loads(Path(args.faces).read_text())
    training = [r for r in manifest['train'] if r['image'] in faces]
    assert not {r['pixel_sha256'] for r in training} & {r['pixel_sha256'] for r in manifest['heldout']}
    protocol = dict(base_checkpoint_sha256=sha256(base / 'model_v9.pt'),
                    training_manifest_sha256=sha256(base / 'data_manifest.json'),
                    fitting_images=len(training), fitting_names=[r['image'] for r in training],
                    excluded_heldout=len(manifest['heldout']), clusters=4, rank=8, min_members=24,
                    alignment='Haar detected training faces, clamped crop at zoom 1.8; no source previews',
                    seed=261016, samples=args.samples, source_photos_displayed=False,
                    variants=[dict(name='pca_control', renderer='continuous Lab field'),
                              dict(name='guided085', mix=.85, sigma=10.), dict(name='guided095', mix=.95, sigma=6.)],
                    selection='Review first 16 generated images for paired eyes, central nose and lower mouth; track diversity and nearest-source distance',
                    limitation='Same-author unblinded development visual assessment; no realism or independent confirmation claim')
    write('protocol.json', protocol)
    print(f'Loading {len(training)} automatically detected fitting faces; held-out sources excluded', flush=True)
    T = load_snapshot(Path(manifest['root']), training, 'fit', faces, zoom=1.8)
    print('Fitting mixture and principal-component structure (non-neural)', flush=True)
    structure = StructurePrior.fit(T)
    torch.save(structure.state, out / 'structure.pt')
    print('Cluster sizes', structure.state['counts'].tolist(), flush=True)
    tool = ig.ImageTool(device=torch.device('cpu'), model_dir=base)
    model = tool.ensure()
    report = dict(protocol=protocol, cluster_sizes=structure.state['counts'].tolist(), variants={})
    for name, mix, sigma in [('baseline', None, None), ('pca_control', None, None),
                             ('guided085', .85, 10.), ('guided095', .95, 6.)]:
        outputs = []
        for first in range(0, args.samples, 4):
            batch, seed = min(4, args.samples - first), protocol['seed'] + first
            if name == 'baseline':
                G = model.generate(batch, seed).cpu()
            elif name == 'pca_control':
                field, _ = structure.sample(batch, seed)
                G = lab2rgb(field)
            else:
                G, _ = generate_structured(model, structure, batch, seed, mix=mix, sigma=sigma)
            outputs.append(G)
        G = torch.cat(outputs)
        row = diagnostics(G)
        distances = nearest(G, T)
        row.update(nearest_to_fitting_faces_min=float(distances.min()), nearest_to_fitting_faces_median=float(distances.median()))
        report['variants'][name] = row
        save_grid(G, out / f'{name}.png', columns=4)
        for i, pixels in enumerate(G.numpy()):
            Image.fromarray(pixels).save(out / f'{name}_{i:02d}.png')
        write('report.json', report)
        print(name, json.dumps(row), flush=True)
    report['seconds'] = round(time.time() - start, 1)
    write('report.json', report)
    print('DONE', out, flush=True)


if __name__ == '__main__':
    main()
