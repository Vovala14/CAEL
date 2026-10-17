"""Fit a lexical text memory, domain counts and a small passage ranker."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import time

from .bundle import ROOT
from .knowledge import SCHEMA, add_document, answer_features
from .knowledge_query import content_words
from .train_news_policy import fit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', default=str(ROOT / 'research/knowledge_023'))
    parser.add_argument('--out', default=str(ROOT / 'models/cael-knowledge-v1'))
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    dataset, out = Path(args.dataset), Path(args.out)
    manifest = json.loads((dataset / 'manifest.json').read_text(encoding='utf-8')) if not args.pilot else None
    out.mkdir(parents=True, exist_ok=True)
    destination = out / 'knowledge.sqlite'
    if destination.exists():
        raise ValueError('Refusing to overwrite an existing frozen knowledge model')
    staging = out / 'knowledge.build.sqlite'
    if staging.exists():
        raise ValueError('A previous build is present; inspect it before retrying')
    started = time.monotonic()
    connection = sqlite3.connect(staging)
    connection.executescript(SCHEMA)
    df, domain_counts, totals = Counter(), defaultdict(Counter), Counter()
    training, development, confirmation = [], [], []
    documents = passages = 0
    split_counts = Counter()
    for batch in sorted((dataset / 'batches').glob('*.jsonl')):
        if manifest and hashlib.sha256(batch.read_bytes()).hexdigest() != manifest['batches'][batch.name]:
            raise ValueError('Frozen source batch changed')
        for line in batch.read_text(encoding='utf-8').splitlines():
            record = json.loads(line)
            if connection.execute('SELECT 1 FROM documents WHERE id=?', (record['pageid'],)).fetchone():
                continue
            add_document(connection, record)
            documents += 1
            paragraphs = [(section['heading'], paragraph) for section in record['sections'] for paragraph in section['paragraphs']]
            passages += len(paragraphs)
            terms = content_words(record['title'] + ' ' + ' '.join(body for _, body in paragraphs))
            df.update(set(terms))
            domain_counts[record['domain']].update(terms)
            totals[record['domain']] += len(terms)
            bucket = int(hashlib.sha256(record['title'].encode()).hexdigest()[:8], 16) % 10
            split = 'confirmation' if bucket == 0 else 'development' if bucket == 1 else 'train'
            split_counts[split] += 1
            target_rows = confirmation if split == 'confirmation' else development if split == 'development' else training
            # Weak supervision from real section headings. All passages stay in the
            # retrieval memory; only train-topic passages fit the selection weights.
            cues = {'cause': ('cause', 'etiology', 'causation'), 'mechanism': ('mechanism', 'operation', 'principle', 'process'),
                    'location': ('geography', 'distribution', 'location'), 'time': ('history', 'origin'), 'definition': ('introduction',)}
            for kind, needles in cues.items():
                positives = [(i, heading, body) for i, (heading, body) in enumerate(paragraphs) if any(cue in heading.lower() for cue in needles)]
                negatives = [(i, heading, body) for i, (heading, body) in enumerate(paragraphs) if not any(cue in heading.lower() for cue in needles)]
                if not positives or not negatives:
                    continue
                for label, candidates in [(1, positives), (0, negatives)]:
                    for i, heading, body in candidates[:2]:
                        target_rows.append(dict(features=answer_features(kind, heading, body, i, content_words(record['title'])),
                                                target=label, kind=kind, title=record['title']))
        connection.commit()
        print(json.dumps(dict(documents=documents, passages=passages)), flush=True)
    weights = fit(training, lambda row: row['features'], lambda row: row['target'], seed=230023)
    def evaluate(rows):
        correct = sum(int(sum(weights.get(k, 0.) * v for k, v in row['features'].items()) > 0) == row['target'] for row in rows)
        return dict(correct=correct, total=len(rows), accuracy=round(correct / max(1, len(rows)), 5))
    ranker = dict(format='cael-knowledge-ranker-v1', architecture='BM25 lexical retrieval, learned token/category counts and linear passage selection',
                  answer_weights=weights, domain_counts={domain: dict(counts.most_common(12000)) for domain, counts in domain_counts.items()},
                  domain_totals=dict(totals), document_frequency=dict(df), document_count=documents,
                  training_passages=len(training), labelled_topic_splits=dict(split_counts),
                  limitations='Weak labels from section headings. Retrieval memory includes all topics; passage-ranker evaluation holds out topics, not stored facts.')
    ranker['document_ranges'] = {str(docid): [first, last] for docid, first, last in connection.execute(
        'SELECT docid,min(rowid),max(rowid) FROM passages GROUP BY docid')}
    (out / 'ranker.json').write_text(json.dumps(ranker, separators=(',', ':')), encoding='utf-8')
    metadata = dict(documents=documents, passages=passages, snapshot=datetime.now(timezone.utc).isoformat(),
                    licence='CC BY-SA 4.0', source='Wikipedia contributors', private_data=False)
    for key, value in metadata.items():
        connection.execute('INSERT INTO metadata VALUES(?,?)', (key, json.dumps(value)))
    connection.execute("INSERT INTO passages(passages) VALUES('optimize')")
    connection.commit()
    connection.close()
    staging.replace(destination)
    report = dict(**metadata, pilot=args.pilot, training_examples=len(training), development=evaluate(development),
                  confirmation=evaluate(confirmation), topic_splits=dict(split_counts),
                  seconds=round(time.monotonic() - started, 2), model_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                  limitation='Lexical/extractive memory is not unrestricted reasoning. Weak section-heading labels do not establish answer correctness.')
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('DONE', json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
