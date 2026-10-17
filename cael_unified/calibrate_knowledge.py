"""Refit the passage ranker after development checks; keep the text index fixed."""
import hashlib
import json
from itertools import groupby
import sqlite3
from .bundle import ROOT
from .knowledge import DEFAULT, answer_features
from .knowledge_query import content_words
from .train_news_policy import fit


def main():
    out = DEFAULT.parent
    ranker = json.loads((out / 'ranker.json').read_text(encoding='utf-8'))
    report = json.loads((out / 'report.json').read_text(encoding='utf-8'))
    prior = ROOT / 'research/knowledge_023/initial_ranker.json'
    if not prior.exists():
        prior.write_text(json.dumps(ranker), encoding='utf-8')
    splits = dict(train=[], development=[], confirmation=[])
    cues = {'cause': ('cause', 'etiology', 'causation'),
            'mechanism': ('mechanism', 'operation', 'principle', 'process', 'mechanics', 'drivetrain', 'power transmission'),
            'location': ('geography', 'distribution', 'location'), 'time': ('history', 'origin'), 'definition': ('introduction',)}
    connection = sqlite3.connect(DEFAULT.resolve().as_uri() + '?mode=ro', uri=True)
    titles = dict(connection.execute('SELECT id,title FROM documents'))
    cursor = connection.execute('SELECT docid,heading,body,position FROM passages ORDER BY rowid')
    for docid, grouped in groupby(cursor, key=lambda row: row[0]):
        title = titles[docid]
        bucket = int(hashlib.sha256(title.encode()).hexdigest()[:8], 16) % 10
        split = 'confirmation' if bucket == 0 else 'development' if bucket == 1 else 'train'
        paragraphs = [(heading, body, position) for _, heading, body, position in grouped]
        for kind, needles in cues.items():
            positives = [(heading, body, position) for heading, body, position in paragraphs if any(cue in heading.lower() for cue in needles)]
            negatives = [(heading, body, position) for heading, body, position in paragraphs if not any(cue in heading.lower() for cue in needles)]
            if not positives or not negatives:
                continue
            for label, rows in ((1, positives), (0, negatives)):
                for heading, body, position in rows[:2]:
                    splits[split].append(dict(features=answer_features(kind, heading, body, int(position), content_words(title)), target=label))
    connection.close()
    with sqlite3.connect(DEFAULT) as spans_connection:
        ranker['document_ranges'] = {str(docid): [first, last] for docid, first, last in spans_connection.execute(
            'SELECT docid,min(rowid),max(rowid) FROM passages GROUP BY docid')}
    spans_connection.close()
    weights = fit(splits['train'], lambda row: row['features'], lambda row: row['target'], seed=230023)
    ranker['answer_weights'] = weights
    ranker['training_passages'] = len(splits['train'])
    ranker['calibration'] = 'Development rules require topic-proximate causal evidence and reject damaged/incomplete excerpts; mechanism labels include mechanics/drivetrain headings.'
    (out / 'ranker.json').write_text(json.dumps(ranker, separators=(',', ':')), encoding='utf-8')
    report['training_examples'] = len(splits['train'])
    for name in ('development', 'confirmation'):
        rows = splits[name]
        correct = sum(int(sum(weights.get(k, 0.) * v for k, v in row['features'].items()) > 0) == row['target'] for row in rows)
        report[name] = dict(correct=correct, total=len(rows), accuracy=round(correct / len(rows), 5))
    report['ranker_sha256'] = hashlib.sha256((out / 'ranker.json').read_bytes()).hexdigest()
    report['calibration'] = ranker['calibration']
    report['limitation'] = 'Lexical/extractive memory is not unrestricted reasoning. Weak section-heading labels do not establish answer correctness. Development probes informed rule calibration; this is not independent answer-quality confirmation.'
    (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
