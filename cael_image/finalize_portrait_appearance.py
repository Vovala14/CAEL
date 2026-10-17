"""Save the best registered appearance model; blind source access only."""
import json
from pathlib import Path
import sys

import torch
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.portrait_structure import load_checkpoint, load_guard_references, generate_guarded
from cael_image.portrait_appearance import load_eye_aligned, sample_guarded_appearance
from cael_image.portrait_deformation import DeformationPrior
from cael_assistant.eval_portrait_sampling import diagnostics, save_grid, sha256


def main():
    torch.set_num_threads(4)
    out = Path('models/cael-portrait-64-v15-appearance')
    out.mkdir(parents=True, exist_ok=False)
    v13path = Path('models/cael-portrait-64-v13-structure/model_v13.pt')
    model, v13, old = load_checkpoint(v13path)
    fitted = torch.load('research/portrait_latent_ca_v16_a/latent_ca.pt', map_location='cpu', weights_only=True)
    prior_state = {k: v for k, v in fitted['prior'].items() if k != 'latent_statistics'}
    alignment = fitted['alignment']
    eye_train = load_eye_aligned(alignment)
    references = torch.cat([load_guard_references(old['source_guard']), eye_train])
    prior = DeformationPrior(prior_state, warp_strength=.6, latent_ca=False)
    protocol = dict(seed=744016, samples=32, batch=4, fit_images=len(eye_train),
                    populations=prior_state['counts'].tolist(), rank=8, variation=.85, sharpen=.3, warp_strength=.6,
                    guard_threshold=.12, min_diversity_ratio=.7,
                    selected='registered Gaussian shape/appearance; latent CA did not show clear development improvement',
                    v13_sha256=sha256(v13path), original_source_photos_displayed=False,
                    heldout_images_used_for_fit=0, heldout_total=52,
                    architecture='Non-neural joint shape/appearance PCA with classical registration and continuous rendering; no pixel CA in this branch',
                    limit='Generated-seed comparison, same-author nonblind review; not an independent realism benchmark',
                    frozen_before_new_seeds=True)
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    report = dict(protocol=protocol, variants={})
    panels = []
    for name in ('v13', 'v15'):
        outputs, checks = [], []
        for i in range(0, 32, 4):
            if name == 'v13':
                G, check = generate_guarded(model, v13, 4, protocol['seed'] + i, references, **old['settings'])
            else:
                G, check = sample_guarded_appearance(prior, 4, protocol['seed'] + i, references, variation=.85, sharpen=.3)
            outputs.append(G)
            checks.append(check)
        G = torch.cat(outputs)
        row = diagnostics(G)
        row.update(guard_checks=checks, replacements=sum(x['replacements'] for x in checks),
                   nearest_RMS_min=min(d for check in checks for d in check['nearest_RMS']))
        report['variants'][name] = row
        save_grid(G, out / f'{name}_grid.png', columns=8)
        for i, pixels in enumerate(G.numpy()):
            Image.fromarray(pixels).save(out / f'{name}_{i:02d}_64.png')
        panels.append(G[:8])
        print(name, json.dumps(row), flush=True)
    report['checks'] = dict(distance=report['variants']['v15']['nearest_RMS_min'] >= .12,
                            diversity=report['variants']['v15']['pairwise_L1'] >= .7 * report['variants']['v13']['pairwise_L1'])
    canvas = Image.new('RGB', (1024, 308), 'white')
    draw = ImageDraw.Draw(canvas)
    for row, (label, samples) in enumerate(zip(['v13 structure + pixel CA', 'v15 aligned appearance (continuous)'], panels)):
        draw.text((4, row * 154 + 4), label, fill='black')
        for col, pixels in enumerate(samples.numpy()):
            canvas.paste(Image.fromarray(pixels).resize((128, 128), Image.Resampling.NEAREST), (col * 128, row * 154 + 24))
    canvas.save(out / 'comparison.png')
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if not all(report['checks'].values()):
        raise RuntimeError('Frozen numeric checks failed; no final checkpoint saved')
    checkpoint = dict(format='cael-portrait-appearance-v15', prior=prior_state, alignment=alignment,
                      source_guard=old['source_guard'], settings=dict(variation=.85, sharpen=.3, warp_strength=.6),
                      provenance=protocol)
    torch.save(checkpoint, out / 'model_v15.pt')
    report['checkpoint_sha256'] = sha256(out / 'model_v15.pt')
    report['v13_checkpoint_unchanged'] = sha256(v13path) == protocol['v13_sha256']
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', report['checks'], flush=True)


if __name__ == '__main__':
    main()
