"""Fit a non-neural topic classifier on earlier-month Wikipedia news summaries."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from .bundle import ROOT
from .facts import NewsItems, WIKI
from .network import NETWORK
from .news_relevance import NewsRelevance, words


def main():
    root = ROOT / 'research' / 'news_policy_022'
    root.mkdir(exist_ok=True)
    out = ROOT / 'models' / 'cael-news-policy-v1'
    rows, sources = [], []
    # Fixed chronological split: Apr-Aug fitting, Sep development, Oct confirmation.
    seen = set()
    for month in ('April', 'May', 'June', 'July', 'August', 'September', 'October'):
        page = 'Portal:Current_events/' + month + '_2026'
        url = WIKI + urlencode(dict(action='parse', format='json', page=page, prop='text', disableeditsection=1))
        parser = NewsItems()
        parser.feed(NETWORK.json(url, ttl=86400)['parse']['text']['*'])
        count = 0
        for row in parser.records:
            text = row['text']
            key = hashlib.sha256(text.encode()).hexdigest()
            if not row['category'] or not row['date'] or len(words(text)) < 5 or key in seen:
                continue
            if row['date'] > datetime.now(timezone.utc).date():
                continue
            seen.add(key)
            split = 'confirmation' if month == 'October' else 'development' if month == 'September' else 'train'
            rows.append(dict(text=text, category=row['category'], date=row['date'].isoformat(), split=split,
                             source='https://en.wikipedia.org/wiki/' + page, licence='CC BY-SA 4.0'))
            count += 1
        sources.append(dict(url='https://en.wikipedia.org/wiki/' + page, examples=count, licence='CC BY-SA 4.0',
                            attribution='Wikipedia contributors', modification='Leaf current-event summaries extracted; integer token/category counts compiled'))
        print(json.dumps(dict(month=month, examples=count)), flush=True)
    train = [row for row in rows if row['split'] == 'train']
    categories = sorted({row['category'] for row in train})
    counters = {category: Counter() for category in categories}
    vocabulary = Counter()
    for row in train:
        tokens = set(words(row['text']))
        counters[row['category']].update(tokens)
        vocabulary.update(tokens)
    vocabulary = {word: count for word, count in vocabulary.items() if count >= 2}
    counts = {category: {word: count for word, count in counter.items() if word in vocabulary} for category, counter in counters.items()}
    state = dict(format='cael-news-relevance-counts-v1', categories=categories, counts=counts, vocabulary=vocabulary,
                 totals={category: sum(counter.values()) for category, counter in counts.items()}, source_examples=len(train),
                 architecture='Classical smoothed multinomial integer token counts; equal category priors; no neural network',
                 licence='Derived news counts: CC BY-SA 4.0; retain Wikipedia source credits', sources=sources)
    path = out / 'relevance.json'
    path.write_text(json.dumps(state, indent=2), encoding='utf-8')
    model = NewsRelevance(path)
    report = dict(training_examples=len(train), categories=categories, source_license='CC BY-SA 4.0', splits={},
                  limitation='Wikipedia section labels and chronological evaluation; not independent labels or a guarantee of headline truth')
    for split in ('development', 'confirmation'):
        items = [row for row in rows if row['split'] == split]
        correct = sum(model.classify(row['text'])[0] == row['category'] for row in items)
        report['splits'][split] = dict(correct=correct, total=len(items), accuracy=round(correct / max(1, len(items)), 4))
    report['model_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (out / 'relevance_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (out / 'sources.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    (root / 'news_training.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
