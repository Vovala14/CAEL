"""Package the frozen face-structure candidate and check guarded new samples."""
import json
from pathlib import Path
import sys

import torch
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_assistant import imagegen as ig
from cael_assistant.eval_portrait_sampling import diagnostics, save_grid, sha256
from cael_image.portrait_structure import StructurePrior, generate_guarded, load_guard_references
from cael_image.v4_multiscale_ca import nn as nearest


def main():
    torch.set_num_threads(4)
    out = Path('models/cael-portrait-64-v13-structure')
    out.mkdir(parents=True, exist_ok=False)
    base = Path('models/cael-portrait-64-v12-522')
    development = Path('research/portrait_structure_v13_a')
    manifest = json.loads((base / 'data_manifest.json').read_text())
    guard = dict(root=manifest['root'], training_records=manifest['train'],
                 structure_face_boxes=json.loads(Path('research/portrait_structure_train_faces_20261016.json').read_text()),
                 base_face_boxes=json.loads(Path('research/portrait_522_face_boxes.json').read_text()),
                 threshold=.12, max_attempts=8)
    settings = dict(mix=.95, sigma=6., variation=.85)
    protocol = dict(seed=841016, samples=32, batch=4, settings=settings,
                    guard_threshold=.12, guard_max_attempts=8,
                    selection='Frozen guided095 development choice; rejection rule added after first new-seed check missed distance cutoff once',
                    base_sha256=sha256(base / 'model_v9.pt'),
                    structure_sha256=sha256(development / 'structure.pt'),
                    fit_images=192, cluster_members=[60, 65, 67], heldout_excluded=52,
                    source_photos_displayed=False, source_pixels_stored_in_checkpoint=False,
                    limitation='Same-author generated-sample visual review; no new held-out photo evaluation or photorealism claim',
                    visual_rule='First 16: paired eyes, central nose and lower mouth belong to one recognisable face; retain distorted cases',
                    frozen_before_new_seeds=True)
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    refs = load_guard_references(guard)
    model = ig.ImageTool(device=torch.device('cpu'), model_dir=base).ensure()
    structure = StructurePrior(torch.load(development / 'structure.pt', weights_only=True))
    report = dict(protocol=protocol, variants={}, guard_batches=[])
    panels = []
    for name in ('baseline', 'candidate'):
        outputs = []
        for i in range(0, protocol['samples'], 4):
            seed = protocol['seed'] + i
            if name == 'baseline':
                G = model.generate(4, seed).cpu()
            else:
                G, check = generate_guarded(model, structure, 4, seed, refs, **settings)
                report['guard_batches'].append(check)
            outputs.append(G)
        G = torch.cat(outputs)
        row = diagnostics(G)
        distance = nearest(G, refs)
        row.update(nearest_source_RMS_min=float(distance.min()), nearest_source_RMS_median=float(distance.median()))
        report['variants'][name] = row
        save_grid(G, out / f'{name}_grid.png', columns=8)
        for i, x in enumerate(G.numpy()):
            Image.fromarray(x).save(out / f'{name}_{i:02d}.png')
        panels.append(G[:8])
        print(name, json.dumps(row), flush=True)
    report['guard_replacements'] = sum(x['replacements'] for x in report['guard_batches'])
    report['numeric_checks'] = dict(distance=report['variants']['candidate']['nearest_source_RMS_min'] >= .12,
                                    diversity=report['variants']['candidate']['pairwise_L1'] >= .7 * report['variants']['baseline']['pairwise_L1'])
    # Keep fixed first samples; no hand-picking of attractive outputs.
    canvas = Image.new('RGB', (1024, 308), 'white')
    draw = ImageDraw.Draw(canvas)
    for row, (label, samples) in enumerate(zip(['v12 baseline', 'v13 structure + CA'], panels)):
        draw.text((4, row * 154 + 4), label, fill='black')
        for col, pixels in enumerate(samples.numpy()):
            canvas.paste(Image.fromarray(pixels).resize((128, 128), Image.Resampling.NEAREST), (128 * col, row * 154 + 24))
    canvas.save(out / 'comparison.png')
    report['base_checkpoint_unchanged'] = sha256(base / 'model_v9.pt') == protocol['base_sha256']
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if not all(report['numeric_checks'].values()):
        raise RuntimeError('Frozen numeric checks failed; candidate was not packaged')
    checkpoint = dict(format='cael-portrait-structure-v13',
                      base_checkpoint=torch.load(base / 'model_v9.pt', map_location='cpu', weights_only=True),
                      structure=structure.state, settings=settings, source_guard=guard, provenance=protocol)
    torch.save(checkpoint, out / 'model_v13.pt')
    report['checkpoint_sha256'] = sha256(out / 'model_v13.pt')
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', report['numeric_checks'], 'resampled', report['guard_replacements'], flush=True)


if __name__ == '__main__':
    main()
