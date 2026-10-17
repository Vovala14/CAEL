"""Compare generated student outputs without displaying training/held-out images."""
import argparse
import hashlib
import json
from pathlib import Path
import math

import numpy as np
from PIL import Image, ImageDraw
import torch

from .general_appearance import GeneralAppearance
from .train_general_shape_ca import sharpness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--control', required=True)
    parser.add_argument('--previous', required=True)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    torch.set_num_threads(4)
    out, dataset = Path(args.out), Path(args.dataset)
    out.mkdir(parents=True, exist_ok=False)
    paths = {key: Path(getattr(args, key)) for key in ('previous', 'control', 'candidate')}
    generators = {key: GeneralAppearance(torch.load(path, weights_only=True, map_location='cpu')) for key, path in paths.items()}
    subjects = list(generators['candidate'].checkpoint['priors'])
    split = json.loads(paths['candidate'].with_name('split.json').read_text())
    assert split == json.loads(paths['control'].with_name('split.json').read_text()), 'Comparisons require identical fitting/held-out records'
    pages = [Image.new('RGB', (12 * 128, 8 * 150), 'white') for _ in range(math.ceil(len(subjects) / 8))]
    metrics = {}
    for index, subject in enumerate(subjects):
        page, row = divmod(index, 8)
        draw = ImageDraw.Draw(pages[page])
        draw.text((4, row * 150 + 2), subject + ': previous v2 (left); rank8 control (middle); rank4 candidate (right)', fill='black')
        metrics[subject] = {}
        for column, (name, generator) in enumerate(generators.items()):
            if subject not in generator.checkpoint['priors']:
                draw.text((column * 512 + 8, row * 150 + 60), 'Not trained in this model', fill='black')
                continue
            images, info = generator.generate(subject, n=4, seed=250500 + index * 4)
            metrics[subject][name] = dict(native_sharpness=sharpness(images), guard=info['checks'])
            for offset, pixels in enumerate(images):
                image = Image.fromarray(pixels.numpy())
                image.save(out / f'generated_{subject}_{name}_{offset}.png')
                pages[page].paste(image, (column * 512 + offset * 128, row * 150 + 20))
        confirmation = []
        for record in split[subject]['confirmation']:
            path = dataset / record['image']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['file_sha256']
            with Image.open(path) as source:
                confirmation.append(np.asarray(source.convert('RGB')))
        metrics[subject]['confirmation_sharpness'] = sharpness(torch.from_numpy(np.stack(confirmation)))
        print('Compared', subject, flush=True)
    for index, page in enumerate(pages, 1):
        page.save(out / f'generated_comparison_page_{index}.png')
    for record in json.loads((dataset / 'manifest.json').read_text())['records']:
        assert hashlib.sha256((dataset / record['image']).read_bytes()).hexdigest() == record['image_file_sha256']
    report = dict(subjects=metrics, subjects_count=len(subjects), samples_per_subject_per_model=4,
                  fixed_seed_base=250500, model_sha256={key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()},
                  private_images_read=False, training_images_displayed=False, source_files_unchanged=True,
                  deployment='Not activated: generated-only visual review is required.',
                  limitation='Sharpness and similarity checks do not establish realistic geometry, semantic accuracy or human preference. The previous model is the raw v2 experiment, not the mixed live routing policy.')
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE: generated-only review pages ready', flush=True)


if __name__ == '__main__':
    main()
