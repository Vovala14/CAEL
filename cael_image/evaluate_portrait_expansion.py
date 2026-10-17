"""Generated-only portrait comparison; never display source photos or holdouts."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
import torch

from cael_unified.assistant import Assistant
from .general_appearance import GeneralAppearance
from .train_general_shape_ca import sharpness


def facial_structure(images):
    """Classical detection is a diagnostic, not a realism/identity test."""
    face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    eye_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye_tree_eyeglasses.xml')
    faces_found, eye_pairs = 0, 0
    for pixels in images:
        rgb = np.asarray(Image.fromarray(pixels).resize((128, 128), Image.Resampling.LANCZOS))
        grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        faces = face_detector.detectMultiScale(grey, 1.05, 4, minSize=(24, 24))
        if not len(faces):
            continue
        faces_found += 1
        x, y, width, height = max(faces, key=lambda box: box[2] * box[3])
        eyes = eye_detector.detectMultiScale(grey[y:y + int(height * .65), x:x + width], 1.05, 3, minSize=(8, 8))
        centres = [(box[0] + box[2] / 2, box[1] + box[3] / 2) for box in eyes]
        if any(.2 * width <= abs(a[0] - b[0]) <= .7 * width and abs(a[1] - b[1]) <= .15 * height
               for index, a in enumerate(centres) for b in centres[index + 1:]):
            eye_pairs += 1
    return dict(samples=len(images), face_detected=faces_found, horizontal_eye_pair_detected=eye_pairs,
                limitation='Haar face/eye detections can miss good faces or accept artifacts; visual review remains required.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    torch.set_num_threads(4)
    dataset, out = Path(args.dataset), Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    paths = {key: Path(getattr(args, key)) for key in ('control', 'candidate')}
    generators = {key: GeneralAppearance(torch.load(path, weights_only=True, map_location='cpu')) for key, path in paths.items()}
    splits = {key: json.loads(path.with_name('split.json').read_text()) for key, path in paths.items()}
    assert splits['control'] == splits['candidate'], 'Control/candidate partitions must match'
    baseline = Assistant(output_root=out / 'baseline_generated')
    rows, pages = {}, []
    for subject_index, subject in enumerate(('woman', 'man')):
        outputs = {key: [] for key in ('baseline', 'control', 'candidate')}
        for batch in range(4):
            seed = 2906000 + subject_index * 100 + batch * 4
            answer = baseline.image_reply(f'a portrait of an adult {subject}', 4, seed)
            assert answer['route'] == 'image/generated', answer
            arrays = []
            for path in answer['paths']:
                with Image.open(path) as image:
                    arrays.append(np.asarray(image.convert('RGB')))
            samples = dict(baseline=np.stack(arrays))
            for name, generator in generators.items():
                generated, _ = generator.generate(subject, n=4, seed=seed)
                samples[name] = generated.numpy()
            page = Image.new('RGB', (4 * 256, 3 * 280), 'white')
            draw = ImageDraw.Draw(page)
            for row, (name, images) in enumerate(samples.items()):
                outputs[name].extend(images)
                draw.text((4, row * 280 + 3), f'{subject}: {name}, seed {seed}; native {images.shape[1]}px', fill='black')
                for column, pixels in enumerate(images):
                    image = Image.fromarray(pixels)
                    image.save(out / f'generated_{subject}_{name}_{batch * 4 + column:02d}.png')
                    page.paste(image.resize((256, 256), Image.Resampling.NEAREST), (column * 256, row * 280 + 22))
            filename = f'generated_{subject}_comparison_{batch + 1}.png'
            page.save(out / filename)
            pages.append(filename)
        rows[subject] = {}
        for name, images in outputs.items():
            reduced = np.stack([np.asarray(Image.fromarray(image).resize((64, 64), Image.Resampling.LANCZOS)) for image in images])
            rows[subject][name] = dict(native_size=images[0].shape[0], equal_64px_sharpness=sharpness(torch.from_numpy(reduced)),
                                       structure=facial_structure(images))
        print('Compared generated portraits:', subject, flush=True)
    for record in json.loads((dataset / 'manifest.json').read_text())['records']:
        assert hashlib.sha256((dataset / record['image']).read_bytes()).hexdigest() == record['image_file_sha256']
    report = dict(subjects=rows, generated_samples_per_subject_per_model=16, generated_only_pages=pages,
                  model_sha256={key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()},
                  private_source_photos_opened=False, training_images_displayed=False, source_files_unchanged=True,
                  acceptance='Review every fixed generated sample for coherent eyes, nose, mouth and face shape. No promotion based on sharpness/detection counts alone.',
                  deployment='Not activated: generated-only visual review required.',
                  limitation='Finite unconditional adult portrait categories; no promise of photorealism, caption-attribute control or reliable facial anatomy.')
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE: portrait comparisons ready for visual review', flush=True)


if __name__ == '__main__':
    main()
