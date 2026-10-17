"""Generated-only comparisons and untouched synthetic confirmation diagnostics."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageDraw
import torch

from cael_unified.bundle import open_bundle
from .general_appearance import GeneralAppearance
from .general_curriculum import SUBJECTS
from .train_general_shape_ca import sharpness


def reduced(images):
    if images.shape[1] == 64:
        return images
    return torch.from_numpy(np.stack([np.asarray(Image.fromarray(image.numpy()).resize((64, 64), Image.Resampling.LANCZOS)) for image in images]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    torch.set_num_threads(4)
    started = time.monotonic()
    model, dataset, out = Path(args.model), Path(args.dataset), Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    split = json.loads((model.parent / 'split.json').read_text())
    root, _ = open_bundle()
    baseline = GeneralAppearance(torch.load(root / 'image/model.pt', map_location='cpu', weights_only=True))
    candidate = GeneralAppearance(torch.load(model, map_location='cpu', weights_only=True))
    centroids, reference_sharpness = [], {}
    for subject in SUBJECTS:
        records = split[subject]['confirmation']
        arrays = []
        for record in records:
            path = dataset / record['image']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['file_sha256']
            with Image.open(path) as source:
                arrays.append(np.asarray(source.convert('RGB').resize((64, 64), Image.Resampling.LANCZOS)))
        confirmation = torch.from_numpy(np.stack(arrays))
        centroids.append(confirmation.float().mean(0).flatten() / 255)
        reference_sharpness[subject] = sharpness(confirmation)
    centroids = torch.stack(centroids)
    pages = [Image.new('RGB', (8 * 128, 8 * 150), 'white') for _ in range(4)]
    draws = [ImageDraw.Draw(page) for page in pages]
    rows = {}
    separation = {'baseline': [0, 0], 'candidate': [0, 0]}
    for index, subject in enumerate(SUBJECTS):
        seed = 222022 + index * 4
        old, old_info = baseline.generate(subject, n=4, seed=seed)
        new, new_info = candidate.generate(subject, n=4, seed=seed)
        for name, images in [('baseline', old), ('candidate', new)]:
            predictions = torch.cdist(reduced(images).float().flatten(1) / 255, centroids).argmin(1)
            separation[name][0] += int((predictions == index).sum())
            separation[name][1] += len(predictions)
        page, row = divmod(index, 8)
        draws[page].text((4, row * 150 + 3), subject + ' — old64 (left), new128 (right); same fixed seeds', fill='black')
        for col, pixels in enumerate(old):
            pages[page].paste(Image.fromarray(pixels.numpy()).resize((128, 128), Image.Resampling.NEAREST), (col * 128, row * 150 + 20))
        for col, pixels in enumerate(new):
            pages[page].paste(Image.fromarray(pixels.numpy()), ((4 + col) * 128, row * 150 + 20))
            Image.fromarray(pixels.numpy()).save(out / f'generated_{subject}_{col}.png')
        rows[subject] = dict(baseline_64_sharpness=sharpness(old), candidate_64_sharpness=sharpness(reduced(new)),
                             confirmation_64_sharpness=reference_sharpness[subject], candidate_guard=new_info['checks'])
        print('Compared', subject, flush=True)
    for index, page in enumerate(pages):
        page.save(out / f'generated_comparison_page_{index + 1}.png')
    for record in json.loads((dataset / 'manifest.json').read_text())['records']:
        assert hashlib.sha256((dataset / record['image']).read_bytes()).hexdigest() == record['image_file_sha256']
    ratios = [row['candidate_64_sharpness'] / max(row['baseline_64_sharpness'], 1e-9) for row in rows.values()]
    minimum = min(min(row['candidate_guard']['nearest_RMS']) for row in rows.values())
    report = dict(model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(), subjects=rows, fixed_generated_samples=128,
                  median_sharpness_ratio_at_equal_64px_resolution=float(np.median(ratios)), minimum_generated_to_training_RMS=minimum,
                  heldout_RGB_centroid_separation={name: dict(correct=value[0], total=value[1]) for name, value in separation.items()},
                  source_files_unchanged=True, private_images_read=False, training_images_displayed=False,
                  seconds=round(time.monotonic() - started, 2),
                  limitations='Edge sharpness and RGB centroid separation do not measure realism, anatomical correctness, semantic generalization or independent human preference. Generated-only visual review is required.')
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', json.dumps({key: value for key, value in report.items() if key != 'subjects'}), flush=True)


if __name__ == '__main__':
    main()
