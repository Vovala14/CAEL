"""Expand fitting-only alignments through classical detector/flip agreement.

Writes coordinates and hashes only; no private source photo or crop is shown.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.portrait_alignment_geometry import mirror_pair, plausible_pair, pair_agreement


def face_proposals(rgb, cached, cascades):
    h, w = rgb.shape[:2]
    proposals = [tuple(cached[:4])] if cached else []
    scale = min(3., max(1., 240 / min(h, w)), 900 / max(h, w))
    grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    grey = cv2.resize(grey, None, fx=scale, fy=scale)
    grey = cv2.equalizeHist(grey)
    for cascade in cascades:
        found = cascade.detectMultiScale(grey, 1.06, 5, minSize=(max(24, int(24 * scale)),) * 2)
        for box in sorted(found, key=lambda f: int(f[2]) * int(f[3]), reverse=True)[:3]:
            candidate = tuple(float(v / scale) for v in box)
            if not any(np.linalg.norm(np.array(candidate) - np.array(old)) < .1 * candidate[2] for old in proposals):
                proposals.append(candidate)
    return proposals


def eye_options(rgb, face, detectors, normalize_large=False):
    x, y, fw, fh = face
    x0, y0 = max(0, int(x)), max(0, int(y))
    roi = rgb[y0:min(rgb.shape[0], int(y + fh * .76)), x0:min(rgb.shape[1], int(x + fw))]
    if roi.size == 0:
        return []
    grey = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
    options = []
    for name, detector in detectors:
        for target, mode in ((128, 'equalize'), (192, 'clahe')):
            scale = min(5., target / fw) if normalize_large else min(5., max(1., target / fw))
            sample = cv2.resize(grey, None, fx=scale, fy=scale)
            sample = cv2.equalizeHist(sample) if mode == 'equalize' else cv2.createCLAHE(2., (4, 4)).apply(sample)
            eyes = detector.detectMultiScale(sample, 1.05, 5,
                                            minSize=(max(6, int(fw * scale * .10)),) * 2,
                                            maxSize=(max(7, int(fw * scale * .43)),) * 2)
            for a, b in itertools.combinations(eyes, 2):
                a, b = sorted((a, b), key=lambda r: r[0])
                pair = ((float(x0 + (a[0] + a[2] / 2) / scale), float(y0 + (a[1] + a[3] / 2) / scale)),
                        (float(x0 + (b[0] + b[2] / 2) / scale), float(y0 + (b[1] + b[3] / 2) / scale)))
                if plausible_pair(pair, face):
                    options.append(dict(pair=pair, detector=name, mode=mode, target=target))
    return options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--manifest', default='models/cael-portrait-64-v12-522/data_manifest.json')
    parser.add_argument('--previous-alignments', default='research/portrait_eye_alignment_v14.json')
    parser.add_argument('--face-box-cache', default='research/portrait_structure_train_faces_20261016.json')
    parser.add_argument('--normalize-large-faces', action='store_true', help='Downsample large eye regions to detector working resolution')
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():
        raise FileExistsError(out)
    old_path = Path(args.previous_alignments)
    old = json.loads(old_path.read_text())
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    root = Path(manifest['root'])
    cached_faces = json.loads(Path(args.face_box_cache).read_text())
    cascades = [cv2.CascadeClassifier(cv2.data.haarcascades + name) for name in
                ('haarcascade_frontalface_default.xml', 'haarcascade_frontalface_alt2.xml', 'haarcascade_frontalface_alt.xml')]
    eyes = [(name, cv2.CascadeClassifier(cv2.data.haarcascades + name)) for name in
            ('haarcascade_eye_tree_eyeglasses.xml', 'haarcascade_eye.xml')]
    allowed = {r['image']: r for r in manifest['train']}
    pairs = {name: record for name, record in old['pairs'].items() if name in allowed and
             record['image_file_sha256'] == allowed[name]['image_file_sha256']}
    retained_count = len(pairs)
    rejected = []
    for index, record in enumerate(manifest['train']):
        name = record['image']
        path = root / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['image_file_sha256']:
            raise RuntimeError('Frozen fitting file changed: ' + name)
        if name in pairs:
            continue
        with Image.open(path) as image:
            rgb = np.asarray(ImageOps.exif_transpose(image).convert('RGB'))
        height, width = rgb.shape[:2]
        candidates = []
        for face in face_proposals(rgb, cached_faces.get(name), cascades):
            original = eye_options(rgb, face, eyes, args.normalize_large_faces)
            if not original:
                continue
            fx, fy, fw, fh = face
            flipped_face = (width - fx - fw, fy, fw, fh)
            reflected = eye_options(np.ascontiguousarray(rgb[:, ::-1]), flipped_face, eyes, args.normalize_large_faces)
            reflected = [dict(**d, unflipped_pair=mirror_pair(d['pair'], width)) for d in reflected]
            for option in original:
                support = [d for d in original if pair_agreement(option['pair'], d['pair'])]
                flip_support = [d for d in reflected if pair_agreement(option['pair'], d['unflipped_pair'])]
                detector_names = {d['detector'] for d in support + flip_support}
                if not flip_support or len(detector_names) < 2:
                    continue
                locations = [d['pair'] for d in support] + [d['unflipped_pair'] for d in flip_support]
                consensus = np.median(np.array(locations), axis=0)
                if not plausible_pair(consensus, face):
                    continue
                candidates.append(dict(left=consensus[0].tolist(), right=consensus[1].tolist(),
                                       image_file_sha256=record['image_file_sha256'], face_box=list(face),
                                       support=len(locations), detectors=sorted(detector_names), flip_agreement=True,
                                       face_area=float(fw * fh)))
        if candidates:
            selected = max(candidates, key=lambda c: (c['support'], c['face_area']))
            pairs[name] = selected
        else:
            rejected.append(name)
        if (index + 1) % 50 == 0:
            print(f'Processed {index + 1}/{len(manifest["train"])} fitting photos; accepted {len(pairs)} total', flush=True)
    result = dict(root=str(root), pairs=pairs, target_left=old['target_left'], target_right=old['target_right'],
                  method='Original alignments retained; added pairs require two classical eye detectors and horizontal-flip agreement',
                  old_alignment_sha256=hashlib.sha256(old_path.read_bytes()).hexdigest(),
                  source_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                  normalize_large_faces=args.normalize_large_faces,
                  counts=dict(previous=retained_count, accepted_total=len(pairs), recovered=len(pairs) - retained_count,
                              rejected=len(rejected), fitting_images=len(manifest['train']), heldout_excluded=len(manifest['heldout'])),
                  rejected_names=rejected, private_images_displayed=False, heldout_processed=False,
                  quality_limit='Automatic agreement is not visual confirmation of correct source landmarks')
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result['counts']), flush=True)


if __name__ == '__main__':
    main()
