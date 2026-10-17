"""Blindly refit the appearance generator with accepted older alignments.

Only generated outputs are saved as images. Raw and decoded-pixel duplicates
of either source's protected validation records are excluded before fitting.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

import torch
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.data import read_rgb
from cael_image.portrait_appearance import load_eye_aligned, sample_guarded_appearance
from cael_image.portrait_deformation import DeformationPrior
from cael_image.portrait_structure import load_guard_references
from cael_assistant.eval_portrait_sampling import diagnostics, save_grid, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--older-run', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    torch.set_num_threads(4)
    started = time.monotonic()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    older_run = Path(args.older_run)
    old_manifest = json.loads((older_run / 'data_manifest.json').read_text())
    old_alignment = json.loads((older_run / 'alignments.json').read_text())
    current_manifest_path = Path('models/cael-portrait-64-v12-522/data_manifest.json')
    current = json.loads(current_manifest_path.read_text())
    base_path = Path('models/cael-portrait-64-v17-alignment/model_v17.pt')
    v15_path = Path('models/cael-portrait-64-v15-appearance/model_v15.pt')
    baseline = torch.load(base_path, map_location='cpu', weights_only=True)
    base_alignment = baseline['alignment']
    current_root = Path(current['root']).resolve()
    old_root = Path(old_manifest['root']).resolve()
    if Path(base_alignment['root']).resolve() != current_root or Path(old_alignment['root']).resolve() != old_root:
        raise RuntimeError('Alignment root does not match its manifest')
    if any(base_alignment[k] != old_alignment[k] for k in ('target_left', 'target_right')):
        raise RuntimeError('Alignment target positions differ')
    current_allowed = {r['image']: r for r in current['train']}
    older_allowed = {r['image']: r for r in old_manifest['train']}
    if not set(base_alignment['pairs']) <= current_allowed.keys() or not set(old_alignment['pairs']) <= older_allowed.keys():
        raise RuntimeError('Alignment includes a non-fitting name')

    frozen = {}

    def freeze(root, record):
        path = root / record['image']
        key = str(path.resolve())
        if key in frozen:
            return frozen[key]
        digest = sha256(path)
        if digest != record['image_file_sha256']:
            raise RuntimeError('Frozen file changed: ' + str(path))
        pixels = read_rgb(path, 'fit')
        pixel_digest = hashlib.sha256(pixels.tobytes()).hexdigest()
        if 'pixel_sha256' in record and record['pixel_sha256'] != pixel_digest:
            raise RuntimeError('Frozen decoded pixels changed: ' + str(path))
        caption = path.with_suffix('.txt')
        caption_digest = sha256(caption) if caption.is_file() else None
        if 'caption_sha256' in record and record['caption_sha256'] != caption_digest:
            raise RuntimeError('Frozen caption changed: ' + str(path))
        result = dict(image=record['image'], image_file_sha256=digest,
                      pixel_sha256=pixel_digest, caption_sha256=caption_digest)
        frozen[key] = result
        return result

    protected = [freeze(current_root, r) for r in current['heldout']]
    protected += [freeze(old_root, r) for r in old_manifest['heldout']]
    protected_files = {r['image_file_sha256'] for r in protected}
    protected_pixels = {r['pixel_sha256'] for r in protected}

    def blocked(record):
        return record['image_file_sha256'] in protected_files or record['pixel_sha256'] in protected_pixels

    combined = dict(root=str(old_root), pairs={}, target_left=base_alignment['target_left'],
                    target_right=base_alignment['target_right'], private_images_displayed=False)
    prefix = current_root.relative_to(old_root).as_posix()
    used_pixels = set()
    older_records, excluded = [], []
    kept = {'existing': 0, 'older': 0}
    for group, root, alignment, allowed in [('existing', current_root, base_alignment, current_allowed),
                                          ('older', old_root, old_alignment, older_allowed)]:
        for name, pair in alignment['pairs'].items():
            record = freeze(root, allowed[name])
            if pair['image_file_sha256'] != record['image_file_sha256']:
                raise RuntimeError('Alignment file hash mismatch')
            if blocked(record) or record['pixel_sha256'] in used_pixels:
                excluded.append(dict(group=group, image=name,
                                     reason='protected_file_or_pixels' if blocked(record) else 'duplicate_fitting_pixels'))
                continue
            used_pixels.add(record['pixel_sha256'])
            combined_name = prefix + '/' + name if group == 'existing' else name
            if combined_name in combined['pairs']:
                raise RuntimeError('Combined path collision')
            combined['pairs'][combined_name] = pair
            kept[group] += 1
            if group == 'older':
                older_records.append(record)
    if not kept['older']:
        raise RuntimeError('No new older alignments remain after holdout/duplicate checks')
    combined['counts'] = dict(existing=kept['existing'], older=kept['older'], total=len(used_pixels))
    guard = copy.deepcopy(baseline['source_guard'])
    guard['training_records'] = [r for r in guard['training_records'] if not blocked(freeze(current_root, r))]
    guard['additional_training_sets'] = [dict(root=str(old_root), training_records=older_records)]
    assert not used_pixels & protected_pixels
    protocol = dict(seed=1866016, samples=32, batch=4, fit_seed=150016, rank=8,
                    fit_images=len(used_pixels), existing_fit_images=kept['existing'], added_older_images=kept['older'],
                    protected_current_files=len(current['heldout']), protected_older_files=len(old_manifest['heldout']),
                    duplicate_or_protected_exclusions=excluded, threshold=.12, min_diversity_ratio=.7,
                    settings=baseline['settings'], population_initialization='v17 aggregate population templates',
                    base_checkpoint_sha256=sha256(base_path), v15_checkpoint_sha256=sha256(v15_path),
                    older_alignment_sha256=sha256(older_run / 'alignments.json'),
                    current_manifest_sha256=sha256(current_manifest_path),
                    private_source_images_displayed=False, source_previews_created=False,
                    selection='Single candidate, unchanged settings, all fixed-seed outputs retained',
                    architecture='Non-neural registered statistical shape/appearance model with continuous rendering',
                    limitation='Historical older file identities are uncertain; filename candidates are used. Numeric diagnostics do not measure facial realism.')
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    (out / 'alignment.json').write_text(json.dumps(combined, indent=2), encoding='utf-8')
    (out / 'additional_training_manifest.json').write_text(json.dumps(guard['additional_training_sets'], indent=2), encoding='utf-8')
    print('Blind source checks complete:', json.dumps(combined['counts']), flush=True)
    T = load_eye_aligned(combined)
    means = baseline['prior']['means'][:, :64 * 64 * 3].reshape(-1, 64, 64, 3) * torch.tensor([40., 20., 20.])
    fitted = DeformationPrior.fit(T, means.flatten(1), rank=8, seed=protocol['fit_seed'])
    candidate = dict(format='cael-portrait-appearance-v18',
                     prior={k: v for k, v in fitted.state.items() if k != 'latent_statistics'},
                     alignment=combined, source_guard=guard, settings=baseline['settings'], provenance=protocol)
    model_path = out / 'model_v18.pt'
    torch.save(candidate, model_path)
    # Generate from a reloaded checkpoint, using one common fitting-only guard.
    candidate = torch.load(model_path, map_location='cpu', weights_only=True)
    refs = torch.cat([load_guard_references(candidate['source_guard']), load_eye_aligned(candidate['alignment'])])
    report = dict(protocol=protocol, populations=candidate['prior']['counts'].tolist(), variants={})
    panels = []
    for name, state in [('v15', torch.load(v15_path, map_location='cpu', weights_only=True)),
                        ('v17', baseline), ('v18', candidate)]:
        settings = state['settings']
        prior = DeformationPrior(state['prior'], warp_strength=settings['warp_strength'])
        outputs, checks = [], []
        for i in range(0, protocol['samples'], protocol['batch']):
            images, check = sample_guarded_appearance(prior, protocol['batch'], protocol['seed'] + i, refs,
                                                     variation=settings['variation'], sharpen=settings['sharpen'])
            outputs.append(images)
            checks.append(check)
        images = torch.cat(outputs)
        row = diagnostics(images)
        row.update(guard_checks=checks, replacements=sum(c['replacements'] for c in checks),
                   nearest_RMS_min=min(d for c in checks for d in c['nearest_RMS']))
        report['variants'][name] = row
        save_grid(images, out / (name + '_generated_grid.png'), columns=8)
        for i, pixels in enumerate(images.numpy()):
            Image.fromarray(pixels).save(out / f'{name}_generated_{i:02d}_64.png')
        panels.append(images[:8])
        print(name, json.dumps({k: v for k, v in row.items() if k != 'guard_checks'}), flush=True)
    canvas = Image.new('RGB', (1024, 462), 'white')
    draw = ImageDraw.Draw(canvas)
    for row, (label, images) in enumerate(zip(['v15: 76 fitting alignments', 'v17: 125 fitting alignments',
                                              f'v18: {len(T)} fitting alignments, {kept["older"]} added older photos'], panels)):
        draw.text((4, row * 154 + 4), label, fill='black')
        for col, pixels in enumerate(images.numpy()):
            canvas.paste(Image.fromarray(pixels).resize((128, 128), Image.Resampling.NEAREST), (col * 128, row * 154 + 24))
    canvas.save(out / 'generated_comparison.png')
    for absolute, record in frozen.items():
        if sha256(absolute) != record['image_file_sha256']:
            raise RuntimeError('Source file changed during training')
    report['checks'] = dict(source_files_unchanged=True, protected_file_and_pixel_duplicates_excluded=True,
                            existing_checkpoints_unchanged=sha256(base_path) == protocol['base_checkpoint_sha256'] and sha256(v15_path) == protocol['v15_checkpoint_sha256'],
                            distance=report['variants']['v18']['nearest_RMS_min'] >= protocol['threshold'],
                            diversity_vs_v17=report['variants']['v18']['pairwise_L1'] >= protocol['min_diversity_ratio'] * report['variants']['v17']['pairwise_L1'],
                            diversity_vs_v15=report['variants']['v18']['pairwise_L1'] >= protocol['min_diversity_ratio'] * report['variants']['v15']['pairwise_L1'])
    report.update(checkpoint_sha256=sha256(model_path), source_files_verified=len(frozen),
                  seconds=round(time.monotonic() - started, 2), promotion='Separate candidate; defaults unchanged')
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', json.dumps(report['checks']), 'populations', report['populations'], flush=True)


if __name__ == '__main__':
    main()
