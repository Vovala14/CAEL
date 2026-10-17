"""Fit the 64x64 count-based image CA from a user-supplied captioned folder."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

from .data import discover, read_rgb, split_records
from .model import Counts, ImageCA, SCALE, SIZE, COLORS, palette, quantize, tokens
from .layout import thumbnail, fit_layouts


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n',
                          encoding='utf-8', newline='\n')


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    for key, value in dict(layout_clusters=32, layout_size=16, layout_iterations=12,
                           layout_min_images=8, layout_weight=8).items():
        config.setdefault(key, value)
    if not config.get('dataset_dir') or 'FILL_IN' in config['dataset_dir']:
        raise ValueError(f'Fill dataset_dir in {path} with your training folder first.')
    for key in ('dataset_dir', 'output_dir'):
        p = Path(config[key]).expanduser()
        config[key] = str((path.parent / p).resolve() if not p.is_absolute() else p.resolve())
    if config.get('image_size') != SIZE:
        raise ValueError('Stage one supports exactly 64x64; image_size must be 64.')
    if config.get('resize_mode') not in ('error', 'fit'):
        raise ValueError('resize_mode must be error or fit.')
    ranges = dict(max_vocabulary=(1, 1024), min_token_images=(1, 1000000000),
                  seed=(0, 2**32 - 1), validation_max_images=(1, 1000000),
                  preview_count=(0, 32), spatial_weight=(0, 16), text_weight=(0, 16),
                  neighbor_weight=(0, 16), steps=(0, 2048), noise=(0, 1024),
                  layout_clusters=(1, 256), layout_iterations=(1, 100),
                  layout_min_images=(2, 1000000), layout_weight=(0, 32))
    for key, (low, high) in ranges.items():
        value = config.get(key)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{key} must be an integer in [{low}, {high}].')
    if config.get('conditioning_bins') not in (1, 2, 4, 8, 16):
        raise ValueError('conditioning_bins must be 1, 2, 4, 8 or 16.')
    if config['layout_size'] not in (8, 16):
        raise ValueError('layout_size must be 8 or 16.')
    if not isinstance(config.get('validation_fraction'), (int, float)) or not 0 <= config['validation_fraction'] < 1:
        raise ValueError('validation_fraction must be in [0, 1).')
    return config


def checked_rgb(root, record, mode):
    path = root / record['image']
    if sha(path) != record['image_file_sha256'] or sha(path.with_suffix('.txt')) != record['caption_sha256']:
        raise ValueError('Source changed after preflight: ' + str(path))
    rgb = read_rgb(path, mode)
    if hashlib.sha256(rgb.tobytes()).hexdigest() != record['pixel_sha256']:
        raise ValueError('Decoded pixels changed after preflight: ' + str(path))
    return rgb


def preflight(config):
    records = discover(config['dataset_dir'], config['resize_mode'])
    train, val = split_records(records, config['validation_fraction'], config['seed'])
    frequency = Counter()
    for record in train:
        frequency.update(tokens(record['caption']))
    vocabulary = [word for word, count in sorted(frequency.items(), key=lambda item: (-item[1], item[0]))
                  if count >= config['min_token_images']][:config['max_vocabulary']]
    if not vocabulary:
        raise ValueError('No caption words qualify. Add repeated attribute captions or lower min_token_images.')
    count_entries = SIZE * SIZE * COLORS + (len(vocabulary) + 1) * config['conditioning_bins']**2 * COLORS + 4 * COLORS**2 + COLORS
    summary = dict(images=len(records), train_images=len(train), validation_images=len(val),
                   unique_pixel_images=len({r['pixel_sha256'] for r in records}),
                   caption_vocabulary=len(vocabulary), vocabulary_preview=vocabulary[:24],
                   count_storage_mib=round(count_entries * 8 / 1024**2, 2),
                   approximate_fit_peak_mib=round(count_entries * 8 * 5 / 1024**2, 2),
                   width=SIZE, height=SIZE, neural_parameters=0,
                   exact_pixel_overlap=0, training_started=False)
    summary['layout_training_storage_mib'] = round(len(train) * config['layout_size']**2 * 3 * 4 / 1024**2, 2)
    return records, train, val, vocabulary, summary


def validate(model, root, records, config):
    correct = baseline = total = 0
    bits = mae = 0.0
    used = []
    skipped = []
    for record in records[:config['validation_max_images']]:
        rgb = checked_rgb(root, record, config['resize_mode'])
        state = quantize(rgb)
        try:
            condition, matched = model.condition(record['caption'])
        except ValueError as exc:
            skipped.append(dict(image=record['image'], reason=str(exc)))
            continue
        scores = model.scores(state, condition)
        maximum = scores.max(axis=-1).astype(np.float64)
        actual = np.take_along_axis(scores, state[..., None].astype(np.int64), axis=-1)[..., 0]
        logsum = np.log(np.exp((scores.astype(np.float64) - maximum[..., None]) / SCALE).sum(axis=-1))
        bits += float((((maximum - actual) / SCALE + logsum) / np.log(2)).sum())
        correct += int((scores.argmax(axis=-1) == state).sum())
        baseline += int((condition.argmax(axis=-1) == state).sum())
        mae += float(np.abs(palette()[state].astype(np.int16) - rgb.astype(np.int16)).sum())
        total += SIZE * SIZE
        used.append(record['image'])
    return dict(evaluated_images=used, skipped_images=skipped,
                validation_max_images=config['validation_max_images'], pixels=total,
                teacher_forced_color_accuracy=correct / total if total else None,
                position_text_only_accuracy=baseline / total if total else None,
                conditional_pseudo_bits_per_palette_color=bits / total if total else None,
                palette_rgb_mean_absolute_error=mae / (total * 3) if total else None,
                interpretation='Ground-truth neighboring pixels are supplied here. These are local modelling diagnostics, not image quality, generative likelihood, compression rate or prompt-following accuracy.')


def train(config_path, dry_run=False):
    start = time.monotonic()
    config = load_config(config_path)
    records, train_records, val_records, vocabulary, summary = preflight(config)
    print(json.dumps(summary, indent=2), flush=True)
    if dry_run:
        print('Dry run complete: validated only; no training or output files written.')
        return summary
    out = Path(config['output_dir'])
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output folder is not empty. Set a new output_dir to preserve existing runs: ' + str(out))
    out.mkdir(parents=True, exist_ok=True)
    root = Path(config['dataset_dir'])
    write_json(out / 'config.json', config)
    manifest = dict(source_folder=str(root), train=train_records, validation=val_records,
                    split_group='SHA256 of decoded/composited 64x64 RGB pixels',
                    seed=config['seed'], exact_pixel_overlap=0,
                    config_file_sha256=sha(config_path), source_code_sha256={
                        p.name: sha(p) for p in Path(__file__).parent.glob('*.py')})
    write_json(out / 'data_manifest.json', manifest)
    counts = Counts(vocabulary, config['conditioning_bins'])
    thumbnails = []
    try:
        for i, record in enumerate(train_records, 1):
            rgb = checked_rgb(root, record, config['resize_mode'])
            counts.observe(quantize(rgb), record['caption'])
            thumbnails.append(thumbnail(rgb, config['layout_size']))
            if i == 1 or i % 100 == 0 or i == len(train_records):
                print(f'Fitted {i}/{len(train_records)} training images', flush=True)
                write_json(out / 'status.json', dict(stage='fitting', processed=i, total=len(train_records)))
        print('Fitting coarse non-neural layout centroids...', flush=True)
        write_json(out / 'status.json', dict(stage='fitting_layouts'))
        layouts, layout_report = fit_layouts(thumbnails, [r['caption'] for r in train_records], vocabulary, config)
        del thumbnails
        settings = {key: config[key] for key in ('spatial_weight', 'text_weight', 'neighbor_weight', 'steps', 'noise', 'layout_weight')}
        model = counts.export(settings, layouts)
        del counts
        model_path = out / 'model.npz'
        model.save(model_path)
        # Validate the actual saved integer tables, rather than the accumulator.
        model = ImageCA.load(model_path)
        write_json(out / 'status.json', dict(stage='validation', model_sha256=sha(model_path)))
        report = dict(model_sha256=sha(model_path), model_bytes=model_path.stat().st_size,
                      train_images=len(train_records), validation_images=len(val_records),
                      width=SIZE, height=SIZE, neural_parameters=0,
                      model_format=model.metadata['format'], layout_fit=layout_report,
                      validation=validate(model, root, val_records, config),
                      previews=[], seconds=None, generation_quality_validated=False)
        from PIL import Image
        for i, record in enumerate(val_records[:config['preview_count']]):
            try:
                rgb, metadata = model.generate(record['caption'], seed=config['seed'] + i)
            except ValueError as exc:
                report['previews'].append(dict(image=record['image'], error=str(exc)))
                continue
            preview = out / f'preview_{i:02d}.png'
            Image.fromarray(rgb).save(preview)
            write_json(preview.with_suffix('.json'), dict(**metadata, reference_image=record['image']))
            report['previews'].append(preview.name)
        report['seconds'] = time.monotonic() - start
        write_json(out / 'training_report.json', report)
        write_json(out / 'status.json', dict(stage='finished', model_sha256=report['model_sha256']))
        print(json.dumps(report, indent=2), flush=True)
        return report
    except (Exception, KeyboardInterrupt) as exc:
        write_json(out / 'status.json', dict(stage='failed', error=str(exc),
                                           note='No automatic resume. Preserve this run and choose a new output_dir for a retry.'))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[1] / 'train_image_config.json')
    parser.add_argument('--dry-run', action='store_true', help='Validate folder/captions and estimate memory; do not train.')
    args = parser.parse_args()
    try:
        train(args.config, args.dry_run)
    except (ValueError, OSError, ImportError) as exc:
        print('CAEL image training: ' + str(exc), file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
