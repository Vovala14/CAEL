"""v2 face boxes: same Haar (non-neural) approach, plus upscaling of small images, alt2 cascade, and
lower minNeighbors as a second pass for images where pass 1 found nothing. Coordinates only."""
import argparse, json
from pathlib import Path
import cv2
EXT = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--out', required=True)
a = ap.parse_args(); root = Path(a.root)
C = [cv2.CascadeClassifier(cv2.data.haarcascades + n) for n in ('haarcascade_frontalface_default.xml', 'haarcascade_frontalface_alt2.xml')]
boxes = {}; n2 = 0
for p in sorted(root.rglob('*')):
    if p.suffix.lower() not in EXT: continue
    img = cv2.imread(str(p))
    if img is None: continue
    g = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)); h, w = g.shape
    s = 800 / max(h, w) if max(h, w) > 800 else (400 / max(h, w) if max(h, w) < 400 else 1.0)
    gs = cv2.resize(g, None, fx=s, fy=s) if s != 1 else g
    ms = (max(12, int(min(gs.shape) * 0.12)),) * 2; f = ()
    for casc, nb in ((C[0], 5), (C[1], 4), (C[0], 3)):
        f = casc.detectMultiScale(gs, 1.05, nb, minSize=ms)
        if len(f): break
    if len(f):
        if nb != 5: n2 += 1
        x, y, fw, fh = (int(v / s) for v in max(f, key=lambda r: r[2] * r[3]))
        boxes[p.relative_to(root).as_posix()] = [x, y, fw, fh, w, h]
Path(a.out).write_text(json.dumps(boxes), encoding='utf-8'); print(f'{len(boxes)} boxes ({n2} from pass 2/3) -> {a.out}')
