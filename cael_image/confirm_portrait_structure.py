"""Frozen structure candidate versus v12 on new generated seeds; no photo previews."""
import json
from pathlib import Path
import sys
import time

import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_assistant import imagegen as ig
from cael_assistant.eval_portrait_sampling import save_grid, diagnostics, sha256
from cael_image.train_portrait_update import load_snapshot
from cael_image.portrait_structure import StructurePrior, generate_structured
from cael_image.v4_multiscale_ca import nn as nearest


def main():
    torch.set_num_threads(4)
    base = Path('models/cael-portrait-64-v12-522')
    development = Path('research/portrait_structure_v13_a')
    out = Path('research/portrait_structure_v13_confirmation')
    out.mkdir(parents=True, exist_ok=False)
    start = time.time()
    def write(name, data):
        (out / name).write_text(json.dumps(data, indent=2), encoding='utf-8')
    protocol = dict(selected_variant='guided095', mix=.95, sigma=6., variation=.85,
                    samples=32, seed=741016, batch=4,
                    frozen_structure_sha256=sha256(development / 'structure.pt'),
                    base_sha256=sha256(base / 'model_v9.pt'),
                    checks=dict(minimum_nearest_RMS=.12, minimum_diversity_ratio=.7),
                    visual_rule='Count recognisable paired eyes, central nose and lower mouth within one coherent face; record distortions separately',
                    limitation='New generated seeds; same-author nonblind visual assessment, not an independent photo or realism benchmark',
                    private_sources_displayed=False, heldout_source_images_loaded=False)
    write('protocol.json', protocol)
    manifest = json.loads((base / 'data_manifest.json').read_text())
    root = Path(manifest['root'])
    boxes = json.loads(Path('research/portrait_structure_train_faces_20261016.json').read_text())
    aligned_records = [r for r in manifest['train'] if r['image'] in boxes]
    aligned = load_snapshot(root, aligned_records, 'fit', boxes, 1.8)
    original_boxes = json.loads(Path('research/portrait_522_face_boxes.json').read_text())
    all_fitting = load_snapshot(root, manifest['train'], 'fit', original_boxes, 1.6)
    references = torch.cat([aligned, all_fitting])
    structure = StructurePrior(torch.load(development / 'structure.pt', map_location='cpu', weights_only=True))
    model = ig.ImageTool(device=torch.device('cpu'), model_dir=base).ensure()
    report = dict(protocol=protocol, variants={})
    for name in ('baseline', 'candidate'):
        outs = []
        for i in range(0, protocol['samples'], 4):
            seed = protocol['seed'] + i
            if name == 'baseline':
                G = model.generate(4, seed).cpu()
            else:
                G, _ = generate_structured(model, structure, 4, seed, mix=.95, sigma=6.)
            outs.append(G)
        G = torch.cat(outs)
        d = nearest(G, references)
        row = diagnostics(G)
        row.update(nearest_source_RMS_min=float(d.min()), nearest_source_RMS_median=float(d.median()),
                   per_sample_nearest_RMS=[round(float(x), 6) for x in d])
        report['variants'][name] = row
        save_grid(G, out / f'{name}_grid.png', columns=8)
        for i, pixels in enumerate(G.numpy()):
            Image.fromarray(pixels).save(out / f'{name}_{i:02d}.png')
        print(name, json.dumps(row), flush=True)
        write('report.json', report)
    baseline, candidate = report['variants']['baseline'], report['variants']['candidate']
    report['checks'] = dict(diversity=candidate['pairwise_L1'] >= .7 * baseline['pairwise_L1'],
                            minimum_distance=candidate['nearest_source_RMS_min'] >= .12)
    report['seconds'] = round(time.time() - start, 1)
    write('report.json', report)
    print('DONE', report['checks'], flush=True)


if __name__ == '__main__':
    main()
