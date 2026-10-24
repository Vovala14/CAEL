"""Fit subject-conditioned appearance statistics on frozen synthetic images."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.general_curriculum import SUBJECTS
from cael_image.general_appearance import GeneralAppearance
from cael_image.data import read_rgb
from cael_image.portrait_deformation import DeformationPrior
from cael_image.v6_region_ca import rgb2lab


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    torch.set_num_threads(4)
    started = time.monotonic()
    dataset = Path(args.dataset)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    manifest_path = dataset / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if manifest['protocol']['source'] != 'Synthetic teacher outputs only':
        raise ValueError('This release fit accepts synthetic inputs only')
    by_subject = {s: [] for s in SUBJECTS}
    for record in manifest['records']:
        by_subject[record['subject']].append(record)
    # Protect pixel groups globally, even if identical across category labels.
    held_pixels = set()
    for subject, records in by_subject.items():
        groups = sorted({r['pixel_sha256'] for r in records})
        np.random.default_rng(210021 + list(SUBJECTS).index(subject)).shuffle(groups)
        held_pixels.update(groups[:max(4, len(groups) // 4)])
    train_records, held_records, arrays = {}, {}, {}
    for subject, records in by_subject.items():
        train_records[subject], held_records[subject] = [], []
        seen = set()
        for record in records:
            path = dataset / record['image']
            if hashlib.sha256(path.read_bytes()).hexdigest() != record['image_file_sha256']:
                raise RuntimeError('Synthetic source changed: ' + record['image'])
            pixels = read_rgb(path)
            if hashlib.sha256(pixels.tobytes()).hexdigest() != record['pixel_sha256']:
                raise RuntimeError('Synthetic decoded pixels changed')
            arrays[record['image']] = pixels
            if record['pixel_sha256'] in seen:
                continue
            seen.add(record['pixel_sha256'])
            (held_records if record['pixel_sha256'] in held_pixels else train_records)[subject].append(record)
        if len(train_records[subject]) < 16:
            raise ValueError('Too few unique fitting images for ' + subject)
    split = dict(seed=210021, train=train_records, heldout=held_records,
                 manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                 method='Per-category pixel groups; globally protect every selected held-out pixel hash')
    (out / 'split.json').write_text(json.dumps(split, indent=2), encoding='utf-8')
    protocol = dict(training_source='Local Stable Diffusion 1.5 synthetic images only',
                    teacher=manifest['protocol'], architecture='Subject-specific registered shape/appearance PCA, based on portrait generator',
                    seed=210021, rank=8, training_images=sum(map(len, train_records.values())),
                    heldout_images=sum(map(len, held_records.values())), subjects=list(SUBJECTS),
                    settings=dict(variation=.85, sharpen=.3, warp_strength=.6, guard_threshold=.04),
                    private_photos_read=False, source_images_displayed=False,
                    limitations='Finite categories, not arbitrary compositional prompting; synthetic teacher biases and low-resolution statistical averaging remain')
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    priors, references = {}, []
    for subject, records in train_records.items():
        images = torch.from_numpy(np.stack([arrays[r['image']] for r in records]))
        mean = rgb2lab(images.float()).mean(0).flatten()[None]
        fitted = DeformationPrior.fit(images, mean, rank=8, seed=210021 + list(SUBJECTS).index(subject))
        priors[subject] = {k: v for k, v in fitted.state.items() if k != 'latent_statistics'}
        references.append(images)
        print('Fitted', subject, 'train', len(records), 'heldout', len(held_records[subject]), flush=True)
    aliases = {s: words for s, (_, words) in SUBJECTS.items()}
    aliases['woman'] = [w for w in aliases['woman'] if w not in ('person', 'people', 'portrait')]
    checkpoint = dict(format='cael-general-appearance-v1', priors=priors, aliases=aliases,
                      guard_references=torch.cat(references), settings=protocol['settings'], provenance=protocol,
                      license='CAEL Non-Commercial; also subject to CreativeML OpenRAIL-M including Attachment A',
                      reference_pixels_use='Synthetic fitting references for numerical rejection only; never retrieved for generation')
    model_path = out / 'model_general.pt'
    torch.save(checkpoint, model_path)
    checkpoint = torch.load(model_path, map_location='cpu', weights_only=True)
    generator = GeneralAppearance(checkpoint)
    # Evaluate category separation against synthetic held-outs. This is NOT a realism score.
    train_means = torch.stack([torch.from_numpy(np.stack([arrays[r['image']] for r in train_records[s]])).float().mean(0).flatten() for s in SUBJECTS])
    correct = total = 0
    reconstruction = {}
    for index, subject in enumerate(SUBJECTS):
        images = torch.from_numpy(np.stack([arrays[r['image']] for r in held_records[subject]])).float()
        predicted = torch.cdist(images.flatten(1) / 255., train_means / 255.).argmin(1)
        correct += int((predicted == index).sum()); total += len(images)
        reconstruction[subject] = round(float(((images.flatten(1) - train_means[index]) / 255.).square().mean().sqrt()), 5)
    grid = Image.new('RGB', (4 * 128, len(SUBJECTS) * 148), 'white')
    draw = ImageDraw.Draw(grid)
    guard_checks = {}
    all_generated = []
    for index, subject in enumerate(SUBJECTS):
        images, info = generator.generate(subject, n=4, seed=211021 + index * 4)
        guard_checks[subject] = info['checks']
        all_generated.append(images)
        draw.text((4, index * 148 + 2), subject, fill='black')
        for col, pixels in enumerate(images.numpy()):
            Image.fromarray(pixels).save(out / f'generated_{subject}_{col}.png')
            grid.paste(Image.fromarray(pixels).resize((128, 128), Image.Resampling.NEAREST), (col * 128, index * 148 + 20))
    grid.save(out / 'generated_all_subjects.png')
    # Compact generated-only comparison containing the first draw of every category.
    summary = Image.new('RGB', (8 * 128, 4 * 148), 'white')
    draw = ImageDraw.Draw(summary)
    for index, (subject, images) in enumerate(zip(SUBJECTS, all_generated)):
        row, col = divmod(index, 8)
        draw.text((col * 128 + 4, row * 148 + 2), subject, fill='black')
        summary.paste(Image.fromarray(images[0].numpy()).resize((128, 128), Image.Resampling.NEAREST), (col * 128, row * 148 + 20))
    summary.save(out / 'generated_summary.png')
    # Verify ALL source hashes after fitting, including held-out records.
    for record in manifest['records']:
        assert hashlib.sha256((dataset / record['image']).read_bytes()).hexdigest() == record['image_file_sha256']
    report = dict(protocol=protocol, heldout_category_nearest_mean=dict(correct=correct, total=total,
                  accuracy=round(correct / total, 4), chance=round(1 / len(SUBJECTS), 4),
                  limitation='Teacher-domain subject separation by RGB mean, not learned classifier accuracy or image realism'),
                  heldout_RMS_to_training_mean=reconstruction, generated_guard_checks=guard_checks,
                  source_files_unchanged=True, heldout_pixels_excluded_from_fit_and_guard=True,
                  model_reloaded=True, model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
                  seconds=round(time.monotonic() - started, 2))
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', json.dumps(report['heldout_category_nearest_mean']), flush=True)


if __name__ == '__main__':
    main()
