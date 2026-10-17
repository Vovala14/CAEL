"""Incrementally fit i16 integer portrait rules on photos with optional captions.

The source photos are processed blindly and are never displayed or exported.
Original checkpoints are read only. Each new training image is counted once
(and once mirrored); repeating epochs would only repeat the same evidence.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import time

import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_assistant import imagegen as ig
from cael_assistant.eval_portrait_sampling import sha256, generate, save_grid, diagnostics
from cael_image.data import discover, split_records, read_rgb
from cael_image.portrait_sampling import CompactRows
from cael_image.v4_multiscale_ca import stats


STOPWORDS = set('a an the and or of with in on at to is are has have this that it its for from by'.split())


def caption_keys(caption):
    words = re.findall(r'[a-z]+', caption.lower())
    singles = {w for w in words if w not in STOPWORDS}
    bigrams = {f'{x} {y}' for x, y in zip(words, words[1:]) if x not in STOPWORDS and y not in STOPWORDS}
    return singles | bigrams


def add_counts(table, keys, colours):
    if isinstance(table, CompactRows):
        table.add_(keys, colours)
    else:
        ig.v9.GCA.add(table, keys, colours)


def continuation_split(records, previous, fraction, seed):
    """Keep prior evaluation pixels reserved and count only unseen source pixels."""
    current = {r['image']: r for r in records}
    old_train = previous['train']
    old_heldout = previous['heldout']
    training_pixels = {r['pixel_sha256'] for r in old_train}
    heldout_pixels = {r['pixel_sha256'] for r in old_heldout}
    if training_pixels & heldout_pixels:
        raise ValueError('Previous manifest has overlapping training and held-out pixels')
    for record in old_train + old_heldout:
        now = current.get(record['image'])
        if now is None or any(now[k] != record[k] for k in
                              ('image_file_sha256', 'caption_sha256', 'pixel_sha256')):
            raise ValueError('Previously frozen source changed or disappeared: ' + record['image'])
    unseen = [r for r in records if r['pixel_sha256'] not in training_pixels | heldout_pixels]
    if len({r['pixel_sha256'] for r in unseen}) < 2:
        raise ValueError('Need at least two distinct new images for a continuation split')
    delta, fresh_heldout = split_records(unseen, fraction, seed)
    reserved = [r for r in records if r['pixel_sha256'] in heldout_pixels]
    cumulative = [current[r['image']] for r in old_train] + delta
    return delta, reserved + fresh_heldout, cumulative, reserved, fresh_heldout


def load_snapshot(root, records, resize_mode='fit', boxes=None, zoom=1.6):
    images = []
    for record in records:
        p = root / record['image']
        caption_path = p.with_suffix('.txt')
        caption_hash = sha256(caption_path) if caption_path.is_file() else None
        if sha256(p) != record['image_file_sha256'] or caption_hash != record['caption_sha256']:
            raise RuntimeError(f'Source changed after manifest freeze: {record["image"]}')
        pixels = read_rgb(p, resize_mode)
        if hashlib.sha256(pixels.tobytes()).hexdigest() != record['pixel_sha256']:
            raise RuntimeError(f'Decoded pixels changed after manifest freeze: {record["image"]}')
        # Face alignment matches i16; undetected faces retain a centre crop.
        if boxes and record['image'] in boxes:
            pixels = ig.v9.load64(root, record['image'], boxes[record['image']], zoom)
        images.append(pixels)
    return torch.from_numpy(np.stack(images))


def local_diagnostic(model, rgb):
    """Teacher-forced local pseudo bits/colour; not generative likelihood."""
    pyramid = model.pyr(ig.v9.rgb2lab(rgb.float()))
    result = {}
    for L in ig.v9.LEVELS[1:]:
        child, parent = pyramid[L], pyramid[L // 2]
        r = model.rows(model.t[L], model.keys(L, parent, child)) * model.guide(L, child)
        p = r / r.sum(-1, keepdim=True).clamp_min(1e-12)
        selected = p.gather(-1, child[..., None]).squeeze(-1).clamp_min(1e-12)
        result[str(L)] = round(float(-selected.log2().mean()), 5)
    return result


def save_checkpoint(model, cond, out, provenance):
    ck = dict(palette_lab=model.pal.cpu(), coarse=model.coarse.cpu(),
              seed={k: v.cpu() for k, v in model.seed.items()},
              tables={L: {k: v.to_sparse().cpu() for k, v in d.items()} for L, d in model.t.items()},
              args={**model.args, 'out': str(out)}, conditioning=cond,
              luminance_bias=model.luminance_bias, provenance=provenance)
    temporary = out / 'model_v9.pt.partial'
    torch.save(ck, temporary)
    temporary.rename(out / 'model_v9.pt')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=16102026)
    ap.add_argument('--validation-fraction', type=float, default=0.1)
    ap.add_argument('--samples', type=int, default=64)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--batch', type=int, default=4)
    ap.add_argument('--luminance-bias', type=float, default=0.2)
    ap.add_argument('--resize-mode', default='fit', choices=['fit', 'error'])
    ap.add_argument('--face-boxes')
    ap.add_argument('--zoom', type=float, default=1.6)
    ap.add_argument('--require-captions', action='store_true', help='Reject missing or empty captions; otherwise learn image rules from every photo')
    ap.add_argument('--base-model', help='Self-contained candidate to continue; defaults to original i16')
    ap.add_argument('--previous-manifest', help='Previous split manifest, defaulting to the base-model data_manifest.json')
    a = ap.parse_args()
    if a.samples < 8 or a.batch < 1 or not 0 < a.validation_fraction < 1:
        ap.error('Need samples >=8, batch >=1, and a validation fraction between 0 and 1')
    out, root = Path(a.out).resolve(), Path(a.root).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.time()
    torch.set_num_threads(a.threads)
    def write(name, value):
        (out / name).write_text(json.dumps(value, indent=2), encoding='utf-8')
    def status(phase):
        write('status.json', dict(phase=phase, seconds=round(time.time() - start, 1)))
        print(phase, flush=True)
    try:
        status('validating source images and optional captions blindly')
        records = discover(root, a.resize_mode, require_captions=a.require_captions)
        base = Path(a.base_model).resolve() if a.base_model else ig.MODEL
        previous_path = Path(a.previous_manifest).resolve() if a.previous_manifest else base / 'data_manifest.json'
        if a.base_model or a.previous_manifest:
            previous = json.loads(previous_path.read_text(encoding='utf-8'))
            base_report = json.loads((base / 'training_report.json').read_text(encoding='utf-8'))
            if sha256(base / 'model_v9.pt') != base_report['model_sha256']:
                raise ValueError('Base checkpoint does not match its training report')
            train, heldout, cumulative_train, previous_heldout, fresh_heldout = continuation_split(
                records, previous, a.validation_fraction, a.seed)
        else:
            train, heldout = split_records(records, a.validation_fraction, a.seed)
            cumulative_train, previous_heldout, fresh_heldout = train, [], heldout
        if len(train) < 8 or len(heldout) < 2:
            raise ValueError('Need at least eight training images and two held-out images')
        source_hashes = {str(p.relative_to(ig.CAEL)): sha256(p) for p in
                         [Path(__file__), ig.CAEL / 'cael_image' / 'portrait_sampling.py',
                          ig.CAEL / 'cael_image' / 'v10_prior_ca.py', ig.CAEL / 'cael_assistant' / 'imagegen.py']}
        provenance = dict(base_model=str(base), base_checkpoint_sha256=sha256(base / 'model_v9.pt'),
                          base_conditioning_sha256=None if a.base_model else sha256(ig.COND), source_code_sha256=source_hashes,
                          previous_manifest_sha256=sha256(previous_path) if a.base_model or a.previous_manifest else None,
                          new_training_images=len(train), new_heldout_images=len(heldout),
                          fresh_heldout_images=len(fresh_heldout), previous_heldout_images=len(previous_heldout),
                          cumulative_source_training_images=len(cumulative_train),
                          captioned_training_images=sum(bool(r['caption']) for r in train),
                          uncaptioned_training_images=sum(not r['caption'] for r in train),
                          seed=a.seed, flip=True, epochs=1, image_weight=1,
                          private_source_rendered=False, private_source_exported=False,
                          method='Incremental integer local-rule, position, mirror and caption count fitting; frozen i16 palette',
                          limits='Exact pixel duplicates grouped within new dataset. Cross-source duplicates against original i16 photos not audited. Caption priors are weak steering, not language understanding.')
        boxes = json.loads(Path(a.face_boxes).read_text(encoding='utf-8')) if a.face_boxes else {}
        provenance['preprocessing'] = dict(resize_mode=a.resize_mode, zoom=a.zoom,
                                          face_box_sha256=sha256(a.face_boxes) if a.face_boxes else None,
                                          aligned_face_images=sum(r['image'] in boxes for r in records),
                                          other_images='Centre crop and resize; no source pixels exported')
        write('protocol.json', dict(args=vars(a), **provenance,
                                   frozen_before_evaluation=True, calibration_selected_before_new_data=True,
                                   visual_assessment='Generated samples only; original source photos are never inspected'))
        fields = ('image', 'image_file_sha256', 'caption_sha256', 'pixel_sha256')
        write('data_manifest.json', dict(root=str(root), train=[{k: r[k] for k in fields} for r in cumulative_train],
                                        fit_this_run=[{k: r[k] for k in fields} for r in train],
                                        heldout=[{k: r[k] for k in fields} for r in heldout],
                                        heldout_previous=[r['image'] for r in previous_heldout],
                                        heldout_fresh=[r['image'] for r in fresh_heldout]))
        T, V = (load_snapshot(root, rows, a.resize_mode, boxes, a.zoom) for rows in (train, heldout))
        print(f'Frozen {len(T)} new train / {len(V)} new held-out photos', flush=True)
        tool = ig.ImageTool(device=torch.device('cpu'), model_dir=base if a.base_model else None)
        model = tool.ensure()
        model.add = add_counts
        original_training_images = tool.cond['n_train']
        # All evaluation settings were fixed before any new held-out diagnostics.
        status('evaluating base model on held-out data')
        before = local_diagnostic(model, V)
        fresh_before = local_diagnostic(model, V[len(previous_heldout):])
        baseline = generate(model, a.samples, a.seed + 100000, a.luminance_bias, a.batch)
        baseline_stats = stats(baseline, T, torch.Generator().manual_seed(7))
        baseline_stats.update(diagnostics(baseline))
        save_grid(baseline, out / 'baseline_grid.png')
        cond = tool.cond
        token_sets = [caption_keys(r['caption']) for r in train]
        df = Counter(k for keys in token_sets for k in keys)
        new_words = [k for k, n in sorted(df.items(), key=lambda item: (-item[1], item[0]))
                     if n >= cond['min_images']][:128]
        for word in new_words:
            if word not in cond['words']:
                cond['words'][word] = dict(n=0, prior={L: torch.zeros(L * L, model.P, dtype=torch.int32) for L in (16, 32)})
        status('fitting new integer rule and caption counts')
        for first in range(0, len(T), 32):
            lab = ig.v9.rgb2lab(T[first:first + 32].float())
            for mirrored in (False, True):
                x = lab.flip(2) if mirrored else lab
                model.observe(x)
                pyramid = model.pyr(x)
                for j in range(len(x)):
                    for word in token_sets[first + j]:
                        if word not in cond['words']:
                            continue
                        for L in (16, 32):
                            pos = torch.arange(L * L).reshape(1, L, L)
                            model.add(cond['words'][word]['prior'][L], pos, pyramid[L][j:j + 1])
            print(f'Counted {min(first + 32, len(T))}/{len(T)} new photos (+ mirrored observations)', flush=True)
        for word in cond['words']:
            cond['words'][word]['n'] += df[word]
        cond['n_train'] += len(T)
        cond['prior'] = {L: value.cpu() for L, value in model.prior.items()}
        cond['sym'] = {L: value.cpu() for L, value in model.sym.items()}
        status('evaluating updated candidate')
        after = local_diagnostic(model, V)
        fresh_after = local_diagnostic(model, V[len(previous_heldout):])
        updated = generate(model, a.samples, a.seed + 100000, a.luminance_bias, a.batch)
        updated_stats = stats(updated, T, torch.Generator().manual_seed(7))
        updated_stats.update(diagnostics(updated))
        save_grid(updated, out / 'preview_grid.png')
        for i, pixels in enumerate(updated[:16].numpy()):
            Image.fromarray(pixels).save(out / f'preview_{i:02d}.png')
        comparison = torch.stack([baseline[:8], updated[:8]], 0).reshape(16, 64, 64, 3)
        save_grid(comparison, out / 'training_comparison.png')
        quantized_heldout = ig.v9.lab2rgb(model.pal[model.quant(ig.v9.rgb2lab(V.float()))])
        heldout_stats = stats(quantized_heldout, T, torch.Generator().manual_seed(7))
        heldout_stats.update(diagnostics(quantized_heldout))
        report = dict(provenance=provenance, original_training_images=original_training_images,
                      total_training_observations=tool.cond['n_train'],
                      new_caption_word_counts={k: df[k] for k in new_words},
                      local_pseudo_bits_per_colour_before=before, local_pseudo_bits_per_colour_after=after,
                      fresh_heldout_local_before=fresh_before, fresh_heldout_local_after=fresh_after,
                      local_diagnostic_limit='Ground-truth parent and neighbours supplied; not generative likelihood, face quality or prompt following',
                      baseline_calibrated=baseline_stats, updated_calibrated=updated_stats,
                      new_heldout_quantized=heldout_stats,
                      nearest_distance_limit='Nearest-source audit covers new training subset only; original i16 source images were not reread',
                      luminance_bias=a.luminance_bias, seconds=round(time.time() - start, 1))
        status('saving self-contained checkpoint')
        save_checkpoint(model, cond, out, provenance)
        report['model_sha256'] = sha256(out / 'model_v9.pt')
        write('training_report.json', report)
        status('finished')
        print(json.dumps(dict(new_train=len(T), new_heldout=len(V), local_before=before, local_after=after,
                              before=baseline_stats, after=updated_stats)), flush=True)
    except Exception as error:
        write('status.json', dict(phase='failed', error=f'{type(error).__name__}: {error}'))
        raise


if __name__ == '__main__':
    main()
