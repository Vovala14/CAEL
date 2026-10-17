"""Classical eye-pair alignment metadata from fitting photos; never show photos."""
import argparse
import itertools
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():
        raise FileExistsError(out)
    manifest = json.loads(Path('models/cael-portrait-64-v12-522/data_manifest.json').read_text())
    faces = json.loads(Path('research/portrait_structure_train_faces_20261016.json').read_text())
    root = Path(manifest['root'])
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye_tree_eyeglasses.xml')
    pairs, targets = {}, []
    for record in manifest['train']:
        name = record['image']
        if name not in faces:
            continue
        x, y, fw, fh, w, h = faces[name]
        with Image.open(root / name) as im:
            rgb = np.asarray(ImageOps.exif_transpose(im).convert('RGB'))
        roi = cv2.cvtColor(rgb[y:y + int(fh * .65), x:x + fw], cv2.COLOR_RGB2GRAY)
        if not roi.size:
            continue
        scale = max(1., min(4., 128 / fw))
        roi = cv2.resize(roi, None, fx=scale, fy=scale)
        roi = cv2.equalizeHist(roi)
        eyes = detector.detectMultiScale(roi, 1.05, 5, minSize=(max(6, int(fw * scale * .12)),) * 2)
        options = []
        for a, b in itertools.combinations(eyes, 2):
            left, right = sorted([a, b], key=lambda r: r[0])
            p = np.array([left[0] + left[2] / 2, left[1] + left[3] / 2]) / scale + [x, y]
            q = np.array([right[0] + right[2] / 2, right[1] + right[3] / 2]) / scale + [x, y]
            dx, dy = q - p
            centre = (p + q) / 2
            if not (.2 * fw < dx < .7 * fw and abs(dy) < .18 * fh and
                    x + .3 * fw < centre[0] < x + .7 * fw and y + .1 * fh < centre[1] < y + .55 * fh):
                continue
            score = abs(dy) / fh + abs(dx / fw - .4) + abs(centre[0] - x - fw / 2) / fw
            options.append((score, p, q))
        if not options:
            continue
        _, p, q = min(options, key=lambda item: item[0])
        side = min(int(max(fw, fh) * 1.8), w, h)
        cx, cy = x + fw / 2, y + fh / 2
        l = min(max(int(cx - side / 2), 0), w - side)
        t = min(max(int(cy - side * .45), 0), h - side)
        p64, q64 = (p - [l, t]) * 64 / side, (q - [l, t]) * 64 / side
        targets.append([(p64[0] + q64[0]) / 2, (p64[1] + q64[1]) / 2, float(np.linalg.norm(q64 - p64))])
        pairs[name] = dict(left=p.tolist(), right=q.tolist(), image_file_sha256=record['image_file_sha256'])
    if len(pairs) < 24:
        raise ValueError(f'Only {len(pairs)} plausible eye pairs; too few for fitting')
    cx, cy, span = np.median(np.array(targets), axis=0)
    result = dict(root=str(root), pairs=pairs,
                  target_left=[float(cx - span / 2), float(cy)], target_right=[float(cx + span / 2), float(cy)],
                  method='Haar eye-pair detector; similarity alignment target is fitting-population median',
                  private_images_displayed=False, heldout_processed=False)
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(fitting_faces=len(faces), paired_eyes=len(pairs),
                         target_left=result['target_left'], target_right=result['target_right'])))


if __name__ == '__main__':
    main()
