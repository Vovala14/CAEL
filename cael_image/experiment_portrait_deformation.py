"""Bounded appearance/shape comparison using fitting photos blindly."""
import json
from pathlib import Path
import sys

import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.portrait_structure import StructurePrior, load_guard_references
from cael_image.portrait_appearance import load_eye_aligned, sample_guarded_appearance
from cael_image.portrait_deformation import DeformationPrior
from cael_assistant.eval_portrait_sampling import diagnostics, save_grid, sha256


def main():
    torch.set_num_threads(4)
    out = Path('research/portrait_deformation_v15_a')
    out.mkdir(parents=True, exist_ok=False)
    protocol = dict(seed=544016, samples=16, batch=4, threshold=.12,
                    rank=8, min_members=16, flow_iterations=2,
                    source_photos_displayed=False, heldout_sources_processed=False,
                    variants=['eyes_rank8', 'registered_static', 'registered_shape'],
                    limitation='Development generated-sample comparison; classical registration, no neural fitting')
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    state = torch.load('research/portrait_appearance_v14_a/appearance.pt', map_location='cpu', weights_only=True)
    train = load_eye_aligned(state['alignment'])
    raw = torch.load('models/cael-portrait-64-v13-structure/model_v13.pt', map_location='cpu', weights_only=True)
    references = torch.cat([load_guard_references(raw['source_guard']), train])
    del raw
    eye_prior = StructurePrior(state['rank8'])
    print('Fitting joint appearance and displacement from', len(train), 'fitting faces', flush=True)
    shape = DeformationPrior.fit(train, state['rank8']['means'])
    torch.save(dict(prior=shape.state, alignment=state['alignment']), out / 'deformation.pt')
    report = dict(protocol=protocol, cluster_sizes=shape.state['counts'].tolist(), variants={})
    for name in protocol['variants']:
        prior = eye_prior if name == 'eyes_rank8' else DeformationPrior(shape.state, warp_strength=0. if name == 'registered_static' else .6)
        outputs, checks = [], []
        try:
            for i in range(0, 16, 4):
                G, check = sample_guarded_appearance(prior, 4, protocol['seed'] + i, references, sharpen=.3)
                outputs.append(G)
                checks.append(check)
            G = torch.cat(outputs)
            row = diagnostics(G)
            row.update(guard_checks=checks, replacements=sum(c['replacements'] for c in checks))
            report['variants'][name] = row
            save_grid(G, out / f'{name}.png', columns=4)
            for i, pixels in enumerate(G.numpy()):
                Image.fromarray(pixels).save(out / f'{name}_{i:02d}.png')
            print(name, json.dumps(row), flush=True)
        except RuntimeError as error:
            report['variants'][name] = dict(failed=str(error))
            print(name, 'FAILED', error, flush=True)
        (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
