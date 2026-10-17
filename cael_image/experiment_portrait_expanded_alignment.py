"""Fit expanded accepted alignments and compare generated portraits with v15."""
import argparse
import json
from pathlib import Path
import sys

import torch
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.portrait_structure import StructurePrior, load_guard_references
from cael_image.portrait_appearance import load_eye_aligned, sample_guarded_appearance
from cael_image.portrait_deformation import DeformationPrior
from cael_assistant.eval_portrait_sampling import diagnostics, save_grid, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inherited-populations', action='store_true')
    parser.add_argument('--out', default='research/portrait_alignment_v17_a')
    args = parser.parse_args()
    torch.set_num_threads(4)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    base_path = Path('models/cael-portrait-64-v15-appearance/model_v15.pt')
    alignment_path = Path('research/portrait_alignment_v17_robust.json')
    alignment = json.loads(alignment_path.read_text())
    baseline = torch.load(base_path, map_location='cpu', weights_only=True)
    manifest = json.loads(Path('models/cael-portrait-64-v12-522/data_manifest.json').read_text())
    assert set(alignment['pairs']) <= {r['image'] for r in manifest['train']}
    assert not set(alignment['pairs']) & {r['image'] for r in manifest['heldout']}
    protocol = dict(seed=1744016, samples=16, batch=4, threshold=.12, min_diversity_ratio=.7,
                    fit_images=len(alignment['pairs']), old_fit_images=len(baseline['alignment']['pairs']),
                    old_checkpoint_sha256=sha256(base_path), alignment_sha256=sha256(alignment_path),
                    rank=8, rough_clusters=3, min_members=16, variation=.85, sharpen=.3, warp_strength=.6,
                    population_initialization='v15 population templates' if args.inherited_populations else 'fresh clustering',
                    heldout_excluded=len(manifest['heldout']), source_photos_displayed=False,
                    comparison='Same fixed generated-seed schedule and common numerical reference set',
                    quality_limit='Automated alignment count and numerical diagnostics do not establish face quality')
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    T = load_eye_aligned(alignment)
    refs = torch.cat([load_guard_references(baseline['source_guard']), T])
    print('Fitting appearance model from', len(T), 'accepted training alignments', flush=True)
    if args.inherited_populations:
        means = baseline['prior']['means'][:, :64 * 64 * 3].reshape(-1, 64, 64, 3) * torch.tensor([40., 20., 20.])
        population_means = means.flatten(1)
    else:
        rough = StructurePrior.fit(T, clusters=3, rank=8, min_members=16, seed=140016)
        population_means = rough.state['means']
    fitted = DeformationPrior.fit(T, population_means, rank=8, seed=150016)
    prior_state = {k: v for k, v in fitted.state.items() if k != 'latent_statistics'}
    candidate = dict(format='cael-portrait-appearance-v17', prior=prior_state, alignment=alignment,
                     source_guard=baseline['source_guard'], settings=baseline['settings'], provenance=protocol)
    torch.save(candidate, out / 'candidate.pt')
    report = dict(protocol=protocol, populations=prior_state['counts'].tolist(), variants={})
    panels = []
    for name, state in [('v15', baseline), ('v17', candidate)]:
        prior = DeformationPrior(state['prior'], warp_strength=.6)
        outputs, checks = [], []
        for i in range(0, 16, 4):
            G, check = sample_guarded_appearance(prior, 4, protocol['seed'] + i, refs, variation=.85, sharpen=.3)
            outputs.append(G)
            checks.append(check)
        G = torch.cat(outputs)
        row = diagnostics(G)
        row.update(guard_checks=checks, replacements=sum(c['replacements'] for c in checks))
        report['variants'][name] = row
        save_grid(G, out / f'{name}.png', columns=4)
        for i, pixels in enumerate(G.numpy()):
            Image.fromarray(pixels).save(out / f'{name}_{i:02d}_64.png')
        panels.append(G[:8])
        print(name, json.dumps(row), flush=True)
    canvas = Image.new('RGB', (1024, 308), 'white')
    draw = ImageDraw.Draw(canvas)
    for row, (label, samples) in enumerate(zip(['v15: 76 accepted fitting faces', 'v17 candidate: 125 accepted fitting faces'], panels)):
        draw.text((4, row * 154 + 4), label, fill='black')
        for col, pixels in enumerate(samples.numpy()):
            canvas.paste(Image.fromarray(pixels).resize((128, 128), Image.Resampling.NEAREST), (col * 128, row * 154 + 24))
    canvas.save(out / 'comparison.png')
    report['old_checkpoint_unchanged'] = sha256(base_path) == protocol['old_checkpoint_sha256']
    report['diversity_check'] = report['variants']['v17']['pairwise_L1'] >= .7 * report['variants']['v15']['pairwise_L1']
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', report['populations'], 'diversity', report['diversity_check'], flush=True)


if __name__ == '__main__':
    main()
