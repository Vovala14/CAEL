"""Freeze available older fitting copies without displaying private images.

Reconstructs the i16 split from its saved face inventory and seed. Missing
root-level files may have several resized namesakes in the source folders;
include available fitting candidates, but exclude ALL validation namesakes.
No claim is made that resized namesakes are byte-identical historical files.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    metrics_path = Path('models/cael-image-female-64-v10-i16/metrics.json')
    metrics = json.loads(metrics_path.read_text())
    original_args = metrics['args']
    cfg = json.loads(Path(original_args['config']).read_text())
    root = Path(original_args['root'])
    boxes = json.loads(Path(original_args['face_boxes']).read_text())
    sources = original_args['sources'].split(',')
    names = []
    for source in sources:
        names.extend(sorted((n for n, b in boxes.items() if b is not None and n.startswith(source + '/')), key=Path))
    if original_args['include_root']:
        names.extend(sorted((n for n, b in boxes.items() if b is not None and '/' not in n), key=Path))
    nv = max(8, int(len(names) * cfg['validation_fraction']))
    permutation = np.random.default_rng(cfg['seed']).permutation(len(names))
    original_heldout = [names[i] for i in permutation[:nv]]
    original_train = [names[i] for i in permutation[nv:]]
    if len(original_train) != metrics['train_images'] or nv != metrics['heldout_quantized']['n']:
        raise RuntimeError('Saved inventory no longer reproduces the recorded split sizes')

    by_basename = collections.defaultdict(list)
    for source in sources:
        for path in sorted((root / source).rglob('*')):
            if path.is_file() and path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}:
                by_basename[path.name.casefold()].append(path.relative_to(root).as_posix())

    def candidates(name, protect_all=False):
        found = list(by_basename[Path(name).name.casefold()])
        if (root / name).is_file():
            if protect_all:
                return sorted(set(found + [name]))
            return [name]
        return found

    digest_cache = {}

    def digest(name):
        if name not in digest_cache:
            digest_cache[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
        return digest_cache[name]

    protected_names = {p for n in original_heldout for p in candidates(n, protect_all=True)}
    protected_hashes = {digest(p) for p in protected_names}
    proposed = collections.defaultdict(list)
    missing = []
    ambiguous = []
    for name in original_train:
        found = candidates(name)
        if not found:
            missing.append(name)
        if len(found) > 1:
            ambiguous.append(name)
        for current in found:
            proposed[current].append(name)
    training = []
    seen_hashes = set()
    excluded = collections.Counter()
    for current, historical in sorted(proposed.items()):
        sha = digest(current)
        if current in protected_names or sha in protected_hashes:
            excluded['validation_name_or_identical_file'] += 1
            continue
        if sha in seen_hashes:
            excluded['identical_fitting_copy'] += 1
            continue
        seen_hashes.add(sha)
        training.append(dict(image=current, image_file_sha256=sha, historical_names=historical))
    heldout = [dict(image=n, image_file_sha256=digest(n)) for n in sorted(protected_names)]
    manifest = dict(root=str(root), train=training, heldout=heldout,
                    original_train=original_train, original_heldout=original_heldout,
                    split_seed=cfg['seed'], original_metrics_sha256=hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
                    policy='All validation filenames and identical files protected; fitting namesakes are candidates, not verified historical originals',
                    counts=dict(original_inventory=len(names), original_train=len(original_train), original_heldout=nv,
                                available_unique_fitting_candidates=len(training), protected_available_files=len(heldout),
                                missing_original_training_names=len(missing), ambiguous_original_training_names=len(ambiguous),
                                exclusions=dict(excluded)),
                    missing_original_training_names=missing, ambiguous_original_training_names=ambiguous,
                    private_images_displayed=False)
    (out / 'data_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    # Do not reuse old full-resolution face coordinates on resized copies.
    (out / 'face_boxes.json').write_text('{}', encoding='utf-8')
    prior = json.loads(Path('research/portrait_eye_alignment_v14.json').read_text())
    seed = dict(root=str(root), pairs={}, target_left=prior['target_left'], target_right=prior['target_right'])
    (out / 'alignment_seed.json').write_text(json.dumps(seed, indent=2), encoding='utf-8')
    print(json.dumps(manifest['counts']), flush=True)


if __name__ == '__main__':
    main()
