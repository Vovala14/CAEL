"""Non-neural coarse layout centroids fitted on the training split only.

These are 16x16 cluster means, not complete source images or a neural encoder.
Floating arithmetic is confined to fitting. Inference interpolation is integer.
"""
import numpy as np
from .model import SCALE, integer_log_prob, tokens


def thumbnail(rgb, size=16):
    # Area means for 64x64 -> a divisor-sized training thumbnail.
    block = 64 // size
    return np.rint(rgb.reshape(size, block, size, block, 3).mean(axis=(1, 3))).astype(np.uint8)


def upscale_integer(coarse):
    size = coarse.shape[0]
    positions = np.arange(64, dtype=np.int64) * (size - 1) * 256 // 63
    lo = positions // 256
    hi = np.minimum(lo + 1, size - 1)
    fraction = positions % 256
    pixels = coarse.astype(np.int64)
    horizontal = (pixels[:, lo] * (256 - fraction)[None, :, None] +
                  pixels[:, hi] * fraction[None, :, None] + 128) // 256
    output = (horizontal[lo] * (256 - fraction)[:, None, None] +
              horizontal[hi] * fraction[:, None, None] + 128) // 256
    return output.astype(np.uint8)


def fit_layouts(thumbnails, captions, vocabulary, config):
    data = np.stack(thumbnails).reshape(len(thumbnails), -1).astype(np.float32)
    if len(data) != len(captions):
        raise ValueError('Layout/caption count mismatch.')
    k = min(config['layout_clusters'], max(1, len(data) // config['layout_min_images']))
    rng = np.random.default_rng(config['seed'])
    centers = data[rng.choice(len(data), k, replace=False)].copy()
    old_labels = None
    norm = (data * data).sum(axis=1, keepdims=True)
    for _ in range(config['layout_iterations']):
        distances = norm + (centers * centers).sum(axis=1)[None] - 2 * data @ centers.T
        labels = distances.argmin(axis=1)
        if old_labels is not None and np.array_equal(labels, old_labels):
            break
        old_labels = labels.copy()
        for j in range(k):
            members = data[labels == j]
            if len(members):
                centers[j] = members.mean(axis=0)
            else:
                centers[j] = data[int(rng.integers(len(data)))]
    # Merge tiny clusters so prototypes normally average multiple images.
    active = sorted(set(map(int, labels)))
    while len(active) > 1:
        sizes = {j: int((labels == j).sum()) for j in active}
        smallest = min(active, key=lambda j: sizes[j])
        if sizes[smallest] >= config['layout_min_images']:
            break
        options = [j for j in active if j != smallest]
        target = min(options, key=lambda j: float(((centers[j] - centers[smallest])**2).sum()))
        labels[labels == smallest] = target
        centers[target] = data[labels == target].mean(axis=0)
        active.remove(smallest)
    remap = {old: new for new, old in enumerate(active)}
    labels = np.array([remap[int(label)] for label in labels], dtype=np.int32)
    means = np.stack([data[labels == j].mean(axis=0) for j in range(len(active))])
    layouts = np.rint(means).clip(0, 255).astype(np.uint8).reshape(-1, config['layout_size'], config['layout_size'], 3)
    sizes = np.bincount(labels, minlength=len(layouts)).astype(np.uint64)
    word_counts = np.zeros((len(vocabulary), len(layouts)), np.uint64)
    index = {word: i for i, word in enumerate(vocabulary)}
    for caption, label in zip(captions, labels):
        for word in tokens(caption):
            if word in index:
                word_counts[index[word], label] += 1
    prior = integer_log_prob(sizes)
    evidence = integer_log_prob(word_counts).astype(np.int32) - prior
    arrays = dict(layouts=layouts, layout_prior=prior,
                  layout_words=evidence.clip(-32768, 32767).astype(np.int16))
    report = dict(clusters=len(layouts), thumbnail_size=config['layout_size'],
                  training_images=len(data), members_per_cluster=sizes.tolist(),
                  method='k-means cluster means with small-cluster merging; no neural encoder',
                  warning='Coarse shape prior only; face/anatomy quality is not established.')
    return arrays, report
