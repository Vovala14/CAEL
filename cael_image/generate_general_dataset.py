"""Generate resumable synthetic training data using a LOCAL sd-server.

No private input photos are read. Training images are never displayed.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import urllib.request
from urllib.parse import urlparse

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.general_curriculum import curriculum, prompt_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='http://127.0.0.1:18765')
    parser.add_argument('--out', required=True)
    parser.add_argument('--model-sha256', required=True)
    parser.add_argument('--per-subject', type=int, default=32)
    parser.add_argument('--batch', type=int, default=8)
    parser.add_argument('--steps', type=int, default=12)
    parser.add_argument('--render-size', type=int, default=384)
    parser.add_argument('--output-size', type=int, default=64)
    parser.add_argument('--seed', type=int, default=2101000)
    parser.add_argument('--subjects', help='Optional comma-separated pilot categories')
    parser.add_argument('--curriculum', choices=('base', 'expanded', 'portraits'), default='base')
    parser.add_argument('--keep-renders', action='store_true')
    args = parser.parse_args()
    if urlparse(args.server).hostname not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('Only a local teacher server is permitted')
    vocabulary = curriculum(args.curriculum)
    subjects = args.subjects.split(',') if args.subjects else list(vocabulary)
    if len(set(subjects)) != len(subjects) or any(subject not in vocabulary for subject in subjects):
        parser.error('Unknown or duplicate category')
    if min(args.per_subject, args.batch, args.steps, args.render_size, args.output_size) < 1 or args.per_subject % args.batch:
        parser.error('Positive values required; per-subject must be divisible by batch')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    protocol = dict(teacher='Stable Diffusion v1.5, local stable-diffusion.cpp', teacher_model_sha256=args.model_sha256,
                    teacher_license='CreativeML OpenRAIL-M', seed=args.seed, subjects=subjects,
                    per_subject=args.per_subject, batch=args.batch, steps=args.steps, render_size=args.render_size,
                    output_size=args.output_size, cfg=7., sampler='Euler a', source='Synthetic teacher outputs only',
                    private_images_read=False, training_images_displayed=False)
    if args.curriculum != 'base':
        protocol['curriculum'] = args.curriculum
    protocol_path = out / 'protocol.json'
    if protocol_path.exists() and json.loads(protocol_path.read_text()) != protocol:
        raise RuntimeError('Resume protocol mismatch')
    protocol_path.write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    started = time.monotonic()
    done = 0
    records = []
    if args.keep_renders:
        (out / 'renders').mkdir(exist_ok=True)
    for subject_index, subject in enumerate(subjects):
        folder = out / subject
        folder.mkdir(exist_ok=True)
        for group, start in enumerate(range(0, args.per_subject, args.batch)):
            prompt = prompt_for(subject, group, args.curriculum)
            seed = protocol['seed'] + subject_index * 1000 + start
            destinations = [folder / f'{i:04d}.png' for i in range(start, start + args.batch)]
            meta_path = folder / f'batch_{group:03d}.json'
            if not (all(p.is_file() for p in destinations) and meta_path.is_file()):
                request = dict(prompt=prompt, negative_prompt='text, watermark, logo, blurry, cropped, cut off, malformed, deformed, duplicate subject',
                               width=args.render_size, height=args.render_size, steps=args.steps, cfg_scale=7.,
                               seed=seed, batch_size=args.batch, sampler_name='Euler a')
                if args.curriculum == 'portraits':
                    request['negative_prompt'] += ', painting, illustration, abstract, blurred face, double face, extra eyes, crossed eyes, profile view, closed eyes'
                req = urllib.request.Request(args.server.rstrip('/') + '/sdapi/v1/txt2img',
                                             data=json.dumps(request).encode(), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=300) as response:
                    result = json.load(response)
                encoded = result.get('images', [])
                if len(encoded) != args.batch:
                    raise RuntimeError('Teacher returned an unexpected batch length')
                for destination, item in zip(destinations, encoded):
                    with Image.open(io.BytesIO(base64.b64decode(item.split(',')[-1]))) as source:
                        if args.keep_renders:
                            source.convert('RGB').save(out / 'renders' / f'{subject}_{destination.stem}.png')
                        rgb = source.convert('RGB').resize((args.output_size, args.output_size), Image.Resampling.LANCZOS)
                        rgb.save(destination, format='PNG')
                    destination.with_suffix('.txt').write_text(prompt, encoding='utf-8')
                meta_path.write_text(json.dumps(dict(subject=subject, request=request, teacher_info=result.get('info')), indent=2), encoding='utf-8')
            for destination in destinations:
                with Image.open(destination) as image:
                    if image.size != (args.output_size, args.output_size):
                        raise RuntimeError('Unexpected synthetic image dimensions')
                    pixels = image.convert('RGB').tobytes()
                records.append(dict(image=destination.relative_to(out).as_posix(), subject=subject, prompt=prompt,
                                    image_file_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                                    pixel_sha256=hashlib.sha256(pixels).hexdigest()))
            done += args.batch
            progress = dict(completed=done, total=len(subjects) * args.per_subject, subject=subject,
                            seconds=round(time.monotonic() - started, 1))
            (out / 'progress.json').write_text(json.dumps(progress), encoding='utf-8')
            print(json.dumps(progress), flush=True)
    (out / 'manifest.json').write_text(json.dumps(dict(protocol=protocol, records=records), indent=2), encoding='utf-8')
    print('DONE: synthetic dataset frozen', len(records), flush=True)


if __name__ == '__main__':
    main()
