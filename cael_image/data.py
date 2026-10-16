"""Captioned image validation and duplicate-safe splits; no dataset execution."""
import hashlib
from pathlib import Path

import numpy as np

from .model import SIZE

EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}


def read_rgb(path, resize_mode='error'):
    from PIL import Image, ImageOps
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        if image.size != (SIZE, SIZE):
            if resize_mode == 'fit':
                image = ImageOps.fit(image, (SIZE, SIZE), method=Image.Resampling.LANCZOS)
            else:
                raise ValueError(f'{path}: expected 64x64, got {image.size}.')
        # Transparency is composited over white; this is part of the data contract.
        rgba = image.convert('RGBA')
        background = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
        rgb = Image.alpha_composite(background, rgba).convert('RGB')
        return np.array(rgb, dtype=np.uint8)


def discover(root, resize_mode='error', require_captions=True):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Dataset folder does not exist: ' + str(root))
    records = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        caption_path = path.with_suffix('.txt')
        if not path.resolve().is_relative_to(root) or not caption_path.resolve().is_relative_to(root):
            raise ValueError('Dataset paths must remain inside the source folder.')
        has_caption = caption_path.is_file()
        if not has_caption and require_captions:
            raise ValueError('Missing matching caption: ' + str(caption_path))
        if has_caption and caption_path.stat().st_size > 65536:
            raise ValueError('Caption exceeds 64 KiB: ' + str(caption_path))
        caption = caption_path.read_text(encoding='utf-8-sig').strip() if has_caption else ''
        if not caption and require_captions:
            raise ValueError('Empty caption: ' + str(caption_path))
        rgb = read_rgb(path, resize_mode)
        records.append(dict(image=path.relative_to(root).as_posix(), caption=caption,
                            image_file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            caption_sha256=hashlib.sha256(caption_path.read_bytes()).hexdigest() if has_caption else None,
                            pixel_sha256=hashlib.sha256(rgb.tobytes()).hexdigest()))
    if not records:
        raise ValueError('No captioned images found. Add 64x64 images and matching .txt captions.' if require_captions
                         else 'No supported images found in the dataset folder.')
    return records


def split_records(records, validation_fraction, seed):
    if not 0 <= validation_fraction < 1:
        raise ValueError('validation_fraction must be in [0, 1).')
    groups = sorted({r['pixel_sha256'] for r in records})
    if validation_fraction and len(groups) < 2:
        raise ValueError('At least two distinct images are needed for a validation split.')
    rng = np.random.default_rng(seed)
    rng.shuffle(groups)
    count = min(len(groups) - 1, max(1, round(len(groups) * validation_fraction))) if validation_fraction else 0
    heldout = set(groups[:count])
    train = [r for r in records if r['pixel_sha256'] not in heldout]
    val = [r for r in records if r['pixel_sha256'] in heldout]
    return train, val
