"""Shared metrics: per-category accuracy, the two headline numbers, latency and compression."""
from collections import defaultdict
from statistics import median

CONTEXT = ('memory', 'reference', 'conflict', 'planning')     # context accuracy: everything except plain fact updates
UPDATE = ('update',)


def pct(rows):
    return round(100 * sum(r['ok'] for r in rows) / len(rows), 1) if rows else None


def summary(rows):
    by = defaultdict(list)
    for r in rows:
        by[r['category']].append(r)
    seconds = sorted(r['seconds'] for r in rows)
    ratios = [r['compression'] for r in rows if r.get('compression')]
    return dict(
        n=len(rows), overall=pct(rows),
        context_accuracy=pct([r for r in rows if r['category'] in CONTEXT]),
        fact_update_accuracy=pct([r for r in rows if r['category'] in UPDATE]),
        by_category={k: dict(n=len(v), accuracy=pct(v)) for k, v in sorted(by.items())},
        short_vs_long={'5-20 messages': pct([r for r in rows if r['n_messages'] <= 20]),
                       '21-50 messages': pct([r for r in rows if r['n_messages'] > 20])},
        latency_median_s=round(median(seconds), 4) if seconds else None,
        latency_p95_s=round(seconds[int(0.95 * (len(seconds) - 1))], 4) if seconds else None,
        cpu_seconds_total=round(sum(r.get('cpu_seconds', 0) for r in rows), 2),
        compression_ratio_median=round(median(ratios), 2) if ratios else None)
