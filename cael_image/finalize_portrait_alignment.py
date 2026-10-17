"""Freeze and verify the expanded-alignment candidate on new generated seeds."""
import json
from pathlib import Path
import sys

import torch
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.portrait_structure import load_guard_references
from cael_image.portrait_appearance import load_eye_aligned, sample_guarded_appearance
from cael_image.portrait_deformation import DeformationPrior
from cael_assistant.eval_portrait_sampling import diagnostics, save_grid, sha256


def main():
    torch.set_num_threads(4)
    out = Path('models/cael-portrait-64-v17-alignment')
    out.mkdir(parents=True, exist_ok=False)
    base_path = Path('models/cael-portrait-64-v15-appearance/model_v15.pt')
    candidate_path = Path('research/portrait_alignment_v17_b/candidate.pt')
    baseline = torch.load(base_path, map_location='cpu', weights_only=True)
    candidate = torch.load(candidate_path, map_location='cpu', weights_only=True)
    protocol = dict(seed=1755016, samples=32, batch=4, fit_images=125, previous_fit_images=76,
                    new_alignments=49, heldout_excluded=52, threshold=.12, min_diversity_ratio=.7,
                    populations=candidate['prior']['counts'].tolist(),
                    base_checkpoint_sha256=sha256(base_path), candidate_sha256=sha256(candidate_path),
                    selection='Inherited population fit selected on generated development samples; no source previews',
                    original_source_photos_displayed=False, frozen_before_generated_confirmation=True,
                    limitation='New generated seeds and same-author nonblind review, not an independent realism benchmark')
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    refs = torch.cat([load_guard_references(candidate['source_guard']), load_eye_aligned(candidate['alignment'])])
    report = dict(protocol=protocol, variants={})
    panels = []
    for name, state in [('v15', baseline), ('v17', candidate)]:
        prior = DeformationPrior(state['prior'], warp_strength=state['settings']['warp_strength'])
        outputs, checks = [], []
        for i in range(0, 32, 4):
            G, check = sample_guarded_appearance(prior, 4, protocol['seed'] + i, refs,
                                                variation=state['settings']['variation'], sharpen=state['settings']['sharpen'])
            outputs.append(G)
            checks.append(check)
        G = torch.cat(outputs)
        row = diagnostics(G)
        row.update(guard_checks=checks, replacements=sum(c['replacements'] for c in checks),
                   nearest_RMS_min=min(d for c in checks for d in c['nearest_RMS']))
        report['variants'][name] = row
        save_grid(G, out / f'{name}_grid.png', columns=8)
        for i, pixels in enumerate(G.numpy()):
            Image.fromarray(pixels).save(out / f'{name}_{i:02d}_64.png')
        panels.append(G[:8])
        print(name, json.dumps(row), flush=True)
    report['checks'] = dict(distance=report['variants']['v17']['nearest_RMS_min'] >= .12,
                            diversity=report['variants']['v17']['pairwise_L1'] >= .7 * report['variants']['v15']['pairwise_L1'])
    canvas = Image.new('RGB', (1024, 308), 'white')
    draw = ImageDraw.Draw(canvas)
    for row, (label, samples) in enumerate(zip(['v15: 76 accepted training alignments', 'v17: 125 accepted training alignments'], panels)):
        draw.text((4, row * 154 + 4), label, fill='black')
        for col, pixels in enumerate(samples.numpy()):
            canvas.paste(Image.fromarray(pixels).resize((128, 128), Image.Resampling.NEAREST), (col * 128, row * 154 + 24))
    canvas.save(out / 'comparison.png')
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if not all(report['checks'].values()):
        raise RuntimeError('Numeric checks failed; model not packaged')
    candidate['confirmation_protocol'] = protocol
    torch.save(candidate, out / 'model_v17.pt')
    report['checkpoint_sha256'] = sha256(out / 'model_v17.pt')
    report['v15_unchanged'] = sha256(base_path) == protocol['base_checkpoint_sha256']
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', report['checks'], flush=True)


if __name__ == '__main__':
    main()
