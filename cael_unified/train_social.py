"""Fit integer observer updates and event vocabulary from an authored curriculum."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]


def fit():
    rng = random.Random(20261017)
    updates, vocabulary = defaultdict(Counter), defaultdict(Counter)
    train_hash = hashlib.sha256()
    for _ in range(20000):
        observed = rng.randrange(2)
        old, new = rng.sample(range(32), 2)
        expected = new if observed else old
        compatible = [code for code, result in enumerate((old, new)) if result == expected]
        for code in compatible:
            updates[str(observed)][code] += 1
        word = rng.choice(('put', 'placed', 'hid', 'moved', 'relocated'))
        vocabulary[word]['move'] += 1
        train_hash.update(json.dumps([observed, old, new, expected, word]).encode())
    model = dict(family='CAEL observer-state hybrid', neural_parameters=0,
                 updates={key: counts.most_common(1)[0][0] for key, counts in updates.items()},
                 update_counts={key: dict(counts) for key, counts in updates.items()},
                 move_words=sorted(vocabulary), vocabulary_counts={key: dict(counts) for key, counts in vocabulary.items()},
                 training_examples=20000, training_sha256=train_hash.hexdigest(),
                 authored_schema=True, authored_surface_parser=True, benchmark_training_examples=0,
                 limitation='One shared room, explicit observation/absence and first-order location beliefs. No inferred unmentioned observation or recursive mental states.')
    out = ROOT/'models/cael-social-v1'
    out.mkdir(parents=True, exist_ok=True)
    (out/'model.json').write_text(json.dumps(model, indent=2))
    (out/'sources.json').write_text(json.dumps(dict(source='Original authored abstract observer curriculum by the CAEL project',
        external_data=False, fee=0, restrictions_from_external_sources=False, no_benchmark_or_mica_training=True), indent=2))
    print(json.dumps(dict(path=str(out), training_examples=20000, sha256=hashlib.sha256((out/'model.json').read_bytes()).hexdigest())))


if __name__ == '__main__':
    fit()
