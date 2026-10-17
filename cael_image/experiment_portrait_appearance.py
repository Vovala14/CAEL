"""Compare eye alignment and continuous rendering using generated samples only."""
import json
from pathlib import Path
import sys

import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.portrait_structure import StructurePrior, load_checkpoint, load_guard_references, generate_guarded
from cael_image.portrait_appearance import load_eye_aligned, sample_guarded_appearance
from cael_assistant.eval_portrait_sampling import diagnostics, save_grid, sha256


def main():
    torch.set_num_threads(4)
    out = Path('research/portrait_appearance_v14_a')
    out.mkdir(parents=True, exist_ok=False)
    protocol = dict(seed=344016, samples=16, batch=4, threshold=.12,
                    min_diversity_ratio=.7, min_members=16,
                    source_photos_displayed=False, heldout_sources_processed=False,
                    variants=['v13', 'v13_continuous', 'eyes_rank4', 'eyes_rank8_sharp'],
                    limitation='Generated development samples; no independent quality benchmark')
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    model, old_prior, state = load_checkpoint('models/cael-portrait-64-v13-structure/model_v13.pt')
    references = load_guard_references(state['source_guard'])
    alignment = json.loads(Path('research/portrait_eye_alignment_v14.json').read_text())
    train = load_eye_aligned(alignment)
    references = torch.cat([references, train])
    print('Fitting from', len(train), 'automatically eye-aligned training faces', flush=True)
    rank4 = StructurePrior.fit(train, clusters=3, rank=4, min_members=16, seed=140016)
    rank8 = StructurePrior.fit(train, clusters=3, rank=8, min_members=16, seed=140016)
    torch.save(dict(alignment=alignment, rank4=rank4.state, rank8=rank8.state), out / 'appearance.pt')
    report = dict(protocol=protocol, clusters=rank4.state['counts'].tolist(), variants={})
    for name, prior, sharpen in [('v13', old_prior, 0.), ('v13_continuous', old_prior, 0.),
                                  ('eyes_rank4', rank4, 0.), ('eyes_rank8_sharp', rank8, .6)]:
        outputs, checks = [], []
        try:
            for i in range(0, 16, 4):
                if name == 'v13':
                    G, check = generate_guarded(model, prior, 4, protocol['seed'] + i, references, **state['settings'])
                else:
                    G, check = sample_guarded_appearance(prior, 4, protocol['seed'] + i, references,
                                                        sharpen=sharpen, variation=.85)
                outputs.append(G)
                checks.append(check)
            G = torch.cat(outputs)
            row = diagnostics(G)
            row.update(guard_checks=checks, replacements=sum(c['replacements'] for c in checks))
            save_grid(G, out / f'{name}.png', columns=4)
            for i, pixels in enumerate(G.numpy()):
                Image.fromarray(pixels).save(out / f'{name}_{i:02d}.png')
            report['variants'][name] = row
            print(name, json.dumps(row), flush=True)
        except RuntimeError as error:
            report['variants'][name] = dict(failed=str(error))
            print(name, 'FAILED', error, flush=True)
        (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
