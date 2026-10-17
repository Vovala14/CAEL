"""Fit a non-neural 128px grouped shape/CA student on synthetic teacher data."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageDraw
import torch

from .general_curriculum import curriculum
from .general_detail_ca import DetailCA
from .general_shape_ca import GeneralShapeCA
from .portrait_deformation import DeformationPrior
from .portrait_sampling import downsample_lab
from .v6_region_ca import rgb2lab, kmeans


def sharpness(images):
    grey = images.float().mean(-1) / 255
    return float((grey[:, 1:] - grey[:, :-1]).abs().mean() + (grey[:, :, 1:] - grey[:, :, :-1]).abs().mean()) / 2


def fitting_centres(images, groups, seed):
    lab = rgb2lab(images.float())
    scale = torch.tensor([40., 20., 20.])
    features = (downsample_lab(lab, 16) / scale).flatten(1)
    centres, assignment = kmeans(features, groups, 25, seed)
    quotas = [len(images) // groups + (index < len(images) % groups) for index in range(groups)]
    for _ in range(12):
        distances = torch.cdist(features, centres)
        assignment = torch.full((len(images),), -1, dtype=torch.long)
        counts = [0] * groups
        for entry in distances.flatten().argsort().tolist():
            row, group = divmod(entry, groups)
            if assignment[row] < 0 and counts[group] < quotas[group]:
                assignment[row] = group
                counts[group] += 1
        centres = torch.stack([features[assignment == group].mean(0) for group in range(groups)])
    means = torch.stack([lab[assignment == group].mean(0).flatten() for group in range(groups)])
    return means, assignment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--subjects', default='')
    parser.add_argument('--rank', type=int, default=16)
    parser.add_argument('--groups', type=int, default=3)
    parser.add_argument('--detail-strength', type=float, default=.35)
    parser.add_argument('--variation', type=float, default=.7)
    parser.add_argument('--warp-strength', type=float, default=.8)
    parser.add_argument('--sharpen', type=float, default=.25)
    parser.add_argument('--no-latent-ca', action='store_true')
    parser.add_argument('--joint-seed', action='store_true')
    parser.add_argument('--image-size', type=int, choices=(128, 256), default=128)
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    torch.set_num_threads(4)
    started = time.monotonic()
    dataset, out = Path(args.dataset).resolve(), Path(args.out).resolve()
    protocol = json.loads((dataset / 'protocol.json').read_text())
    vocabulary = curriculum(protocol.get('curriculum', 'base'))
    if protocol.get('source') != 'Synthetic teacher outputs only' or protocol.get('private_images_read') is not False:
        raise ValueError('Only the declared synthetic teacher dataset is accepted')
    subjects = args.subjects.split(',') if args.subjects else protocol['subjects']
    if not args.pilot and not (dataset / 'manifest.json').is_file():
        raise ValueError('Full fitting requires a completed frozen manifest')
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((dataset / 'manifest.json').read_text()) if (dataset / 'manifest.json').exists() else None
    known_records = {row['image']: row for row in manifest['records']} if manifest else {}
    fixed_split = None
    if protocol.get('fixed_split'):
        if protocol['fixed_split'] != 'split_plan.json':
            raise ValueError('Only a dataset-local split_plan.json is accepted')
        fixed_split = json.loads((dataset / 'split_plan.json').read_text())
    if manifest and len({row['pixel_sha256'] for row in manifest['records']}) != len(manifest['records']):
        raise ValueError('Duplicate synthetic pixel groups require a global grouped split before fitting')
    priors, details, references, split, metrics = {}, {}, [], {}, {}
    for index, subject in enumerate(subjects):
        subject_seed = 220022 + protocol['subjects'].index(subject)
        records = []
        for path in sorted((dataset / subject).glob('*.png')):
            rel = path.relative_to(dataset).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if known_records and known_records[rel]['image_file_sha256'] != digest:
                raise RuntimeError('Frozen synthetic input changed')
            with Image.open(path) as source:
                if source.size != (args.image_size, args.image_size):
                    raise ValueError(f'This experiment requires native {args.image_size}px training inputs')
                pixels = np.asarray(source.convert('RGB'))
            pixel_hash = hashlib.sha256(pixels.tobytes()).hexdigest()
            records.append(dict(image=rel, file_sha256=digest, pixel_sha256=pixel_hash, pixels=pixels))
        unique = {row['pixel_sha256']: row for row in records}
        rows = list(unique.values())
        if len(rows) < 48:
            raise ValueError('Need at least 48 unique synthetic images per fitted subject')
        if fixed_split is not None:
            plan = fixed_split[subject]
            by_image = {row['image']: row for row in rows}
            assigned = [image for partition in ('train', 'development', 'confirmation', 'excluded') for image in plan.get(partition, [])]
            if len(assigned) != len(set(assigned)) or set(assigned) != set(by_image):
                raise ValueError('Fixed partitions must classify every unique input exactly once')
            train, development, confirmation = [[by_image[image] for image in plan[key]] for key in ('train', 'development', 'confirmation')]
            if min(len(development), len(confirmation)) < 4:
                raise ValueError('Need separate development and confirmation inputs')
        else:
            # Sorting by the pixel hash makes the split stable even if file order changes.
            rows.sort(key=lambda row: row['pixel_sha256'])
            np.random.default_rng(220022 + protocol['subjects'].index(subject)).shuffle(rows)
            hold = max(8, len(rows) // 4)
            held, train = rows[:hold], rows[hold:]
            development = held[:len(held) // 2]
            confirmation = held[len(held) // 2:]
        images = torch.from_numpy(np.stack([row['pixels'] for row in train]))
        alignment = dict(applied=False)
        if subject in ('woman', 'man'):
            from .synthetic_face_alignment import align_synthetic_faces
            original = images
            images, accepted, alignment = align_synthetic_faces(images)
            if alignment['applied']:
                train = [train[position] for position in accepted]
                references.append(original[accepted])
        groups = min(args.groups, len(images) // (args.rank + 3))
        centres, assignment = fitting_centres(images, groups, subject_seed)
        prior = DeformationPrior.fit(images, centres, rank=args.rank, seed=subject_seed,
                                     population_assignments=assignment, medoid_frame=True, minimum_population=args.rank + 3)
        priors[subject] = prior.state
        details[subject] = DetailCA.fit(images, seed=subject_seed).state if args.detail_strength else {}
        references.append(images)
        strip = lambda records: [{k: value for k, value in row.items() if k != 'pixels'} for row in records]
        split[subject] = dict(train=strip(train), development=strip(development), confirmation=strip(confirmation))
        metrics[subject] = dict(training_images=len(train), development_images=len(development), confirmation_images=len(confirmation),
                                populations=prior.state['counts'].tolist(), training_native_sharpness=sharpness(images), alignment=alignment)
        print(json.dumps(dict(fitted=subject, **metrics[subject])), flush=True)
    settings = dict(variation=args.variation, warp_strength=args.warp_strength, sharpen=args.sharpen,
                    detail_strength=args.detail_strength, guard_threshold=.04,
                    joint_seed=args.joint_seed, latent_ca=not args.no_latent_ca)
    aliases = {subject: list(vocabulary[subject][1]) for subject in subjects}
    if 'woman' in aliases:
        aliases['woman'] = [word for word in aliases['woman'] if word not in ('person', 'people', 'portrait')]
    checkpoint = dict(format='cael-general-shape-ca-v2', image_size=args.image_size, priors=priors, detail_ca=details,
                      aliases=aliases, guard_references=torch.cat(references), settings=settings,
                      architecture='Grouped classical shape/appearance statistics; learned integer factor counts; '
                                   + ('factor CA active' if settings['latent_ca'] else 'continuous Gaussian factor sampler, factor CA disabled')
                                   + ('; luminance-patch CA active' if args.detail_strength else '; luminance-patch CA disabled'),
                      provenance=dict(teacher=protocol, synthetic_only=True, private_photos_read=False, neural_student=False),
                      license='Existing CAEL software terms; synthetic student also subject to CreativeML OpenRAIL-M')
    model_path = out / 'model_general.pt'
    torch.save(checkpoint, model_path)
    generator = GeneralShapeCA(torch.load(model_path, weights_only=True, map_location='cpu'))
    columns = 4
    row_height = args.image_size + 22
    grid = Image.new('RGB', (columns * args.image_size, len(subjects) * row_height), 'white')
    draw = ImageDraw.Draw(grid)
    for index, subject in enumerate(subjects):
        generated, info = generator.generate(subject, n=4, seed=222022 + protocol['subjects'].index(subject) * 4)
        metrics[subject]['generated_native_sharpness'] = sharpness(generated)
        reduced = torch.from_numpy(np.stack([np.asarray(Image.fromarray(image.numpy()).resize((64, 64), Image.Resampling.LANCZOS)) for image in generated]))
        metrics[subject]['generated_64px_sharpness'] = sharpness(reduced)
        metrics[subject]['guard'] = info['checks']
        draw.text((4, index * row_height + 2), subject, fill='black')
        for col, image in enumerate(generated):
            Image.fromarray(image.numpy()).save(out / f'generated_{subject}_{col}.png')
            grid.paste(Image.fromarray(image.numpy()), (col * args.image_size, index * row_height + 20))
    grid.save(out / 'generated_all_subjects.png')
    report = dict(format='cael-general-shape-ca-report-v2', subjects=subjects, image_size=args.image_size, settings=settings, metrics=metrics,
                  training_images=sum(len(row['train']) for row in split.values()),
                  heldout_images=sum(len(row['development']) + len(row['confirmation']) for row in split.values()),
                  pilot=args.pilot, private_photos_read=False, training_images_displayed=False,
                  model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(), seconds=round(time.monotonic() - started, 2),
                  limitation='Sharpness and RMS similarity checks do not measure semantic correctness, anatomy or realism. Confirmation images are excluded from fitting and guard.')
    (out / 'split.json').write_text(json.dumps(split, indent=2), encoding='utf-8')
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', json.dumps(dict(training_images=report['training_images'], heldout_images=report['heldout_images'], seconds=report['seconds'])), flush=True)


if __name__ == '__main__':
    main()
