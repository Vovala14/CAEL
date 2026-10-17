"""Resumable text-only Wikipedia core-topic snapshot. Never opens local photos."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlencode, quote

from .bundle import ROOT
from .network import NETWORK, LookupUnavailable

WIKI = 'https://en.wikipedia.org/w/api.php?'
LIST = 'Wikipedia:Vital articles/Level 4'
SEEDS = ['Photosynthesis', 'Gravity', 'Sky', 'Rayleigh scattering', 'Rain', 'Rainbow', 'Earth', 'Moon',
         'Water', 'DNA', 'Evolution', 'Computer', 'Algorithm', 'Python (programming language)', 'Internet',
         'Electricity', 'Electric motor', 'Internal combustion engine', 'Bicycle', 'Car', 'Capybara',
         'Norway', 'Canada', 'Marie Curie', 'Albert Einstein', 'Solar System', 'Black hole', 'Climate change',
         'Football', 'Basketball', 'Cricket', 'Tennis', 'Temperature', 'Weather', 'Mitosis', 'Meiosis']


def fetch(**params):
    for attempt in range(4):
        try:
            data = NETWORK.json(WIKI + urlencode(dict(action='query', format='json', maxlag=5, **params)),
                                ttl=86400, timeout=35)
            if data.get('error'):
                raise LookupUnavailable(data['error'].get('info', 'API error'))
            return data
        except LookupUnavailable:
            if attempt == 3:
                raise
            time.sleep(35)


def collect_titles(destination, limit):
    if destination.exists():
        return json.loads(destination.read_text(encoding='utf-8'))
    pending, visited, topics = [LIST], set(), {title: 'Supplementary core topics' for title in SEEDS}
    while pending and len(visited) < 90:
        page = pending.pop(0)
        if page in visited:
            continue
        visited.add(page)
        data = NETWORK.json(WIKI + urlencode(dict(action='parse', format='json', page=page, prop='links', maxlag=5)),
                            ttl=86400, timeout=35)
        for link in data.get('parse', {}).get('links', []):
            title = link['*']
            if link['ns'] == 4 and title.startswith(LIST + '/') and title not in visited:
                pending.append(title)
            elif link['ns'] == 0 and page != LIST:
                topics.setdefault(title, page[len(LIST) + 1:].split('/')[0])
        print(json.dumps(dict(discovered=len(topics), lists=len(visited), page=page)), flush=True)
    # Mix domains deterministically so a bounded run never contains only the first sublist.
    buckets = {}
    for title, domain in sorted(topics.items()):
        buckets.setdefault(domain, []).append(title)
    rows = []
    while buckets and len(rows) < limit:
        for domain in list(buckets):
            title = buckets[domain].pop(0)
            rows.append(dict(title=title, domain=domain))
            if not buckets[domain]:
                del buckets[domain]
            if len(rows) >= limit:
                break
    destination.write_text(json.dumps(dict(rows=rows, list_pages=sorted(visited), discovered=len(topics)), indent=2), encoding='utf-8')
    return json.loads(destination.read_text(encoding='utf-8'))


def plain_sections(wikitext):
    import mwparserfromhell
    code = mwparserfromhell.parse(wikitext)
    for tag in list(code.filter_tags(recursive=True)):
        if str(tag.tag).lower() in ('ref', 'gallery', 'table', 'timeline', 'score', 'math', 'syntaxhighlight', 'code'):
            try:
                code.remove(tag)
            except ValueError:
                pass
    for link in list(code.filter_wikilinks(recursive=True)):
        if str(link.title).lower().startswith(('file:', 'image:', 'category:')):
            try:
                code.remove(link)
            except ValueError:
                pass
    sections, chars = [], 0
    for section in code.get_sections(flat=True, include_lead=True):
        headings = section.filter_headings()
        heading = headings[0].title.strip_code().strip() if headings else 'Introduction'
        if re.search(r'(?i)^(?:references|notes|citations|bibliography|external links|further reading|see also|sources|works cited)', heading):
            continue
        if headings:
            section.remove(headings[0])
        clean = section.strip_code(normalize=True, collapse=True)
        paragraphs = []
        for paragraph in re.split(r'\n\s*\n', clean):
            paragraph = re.sub(r'\s+', ' ', paragraph).strip(' *#:;\n')
            if len(paragraph) < 80 or re.match(r'^(?:\||!|Category:|File:|Image:)', paragraph):
                continue
            if len(paragraph) > 1800:
                chunks = re.split(r'(?<=[.!?])\s+(?=[A-Z])', paragraph)
                paragraph = ''
                for chunk in chunks:
                    if len(paragraph) + len(chunk) > 1500:
                        break
                    paragraph += (' ' if paragraph else '') + chunk
                if len(paragraph) < 80:
                    continue
            paragraphs.append(paragraph)
            chars += len(paragraph)
            if len(paragraphs) == 5 or chars > 24000:
                break
        if paragraphs:
            sections.append(dict(heading=heading, paragraphs=paragraphs))
        if chars > 24000 or sum(len(s['paragraphs']) for s in sections) >= 45:
            break
    return sections


def process_page(args):
    page, domains, redirects = args
    if 'missing' in page or 'disambiguation' in page.get('pageprops', {}) or not page.get('revisions'):
        return None
    revision = page['revisions'][0]
    raw = revision.get('slots', {}).get('main', {}).get('*', '')
    if not raw or len(raw) > 750000:
        return None
    sections = plain_sections(raw)
    if not sections:
        return None
    title = page['title']
    return dict(pageid=page['pageid'], title=title, aliases=[redirects[title]] if title in redirects else [],
        domain=domains.get(title, domains.get(redirects.get(title), 'Core topics')),
        revision=revision['revid'], revision_time=revision['timestamp'], retrieved_at=datetime.now(timezone.utc).isoformat(),
        url='https://en.wikipedia.org/w/index.php?oldid=' + str(revision['revid']),
        article_url=page.get('fullurl') or 'https://en.wikipedia.org/wiki/' + quote(title.replace(' ', '_')),
        raw_sha256=hashlib.sha256(raw.encode()).hexdigest(), sections=sections,
        licence='CC BY-SA 4.0', attribution='Wikipedia contributors; templates, media, references and markup removed by CAEL')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=str(ROOT / 'research/knowledge_023'))
    parser.add_argument('--limit', type=int, default=12000)
    parser.add_argument('--batch', type=int, default=25)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / 'tools/knowledge_dependencies'))
    import mwparserfromhell
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    chunks = out / 'batches'
    chunks.mkdir(exist_ok=True)
    curriculum = collect_titles(out / 'curriculum.json', args.limit)
    rows = curriculum['rows']
    started = time.monotonic()
    done = 0
    pool = ProcessPoolExecutor(max_workers=4)
    for offset in range(0, len(rows), args.batch):
        batch = rows[offset:offset + args.batch]
        path = chunks / f'{offset:05d}.jsonl'
        if path.exists():
            done += sum(1 for _ in path.open(encoding='utf-8'))
            continue
        data = fetch(titles='|'.join(row['title'] for row in batch), prop='revisions|info|pageprops',
                     rvprop='ids|timestamp|content', rvslots='main', inprop='url', redirects=1, ppprop='disambiguation')
        domains = {row['title']: row['domain'] for row in batch}
        redirects = {r['to']: r['from'] for r in data.get('query', {}).get('redirects', [])}
        records = [record for record in pool.map(process_page, [(page, domains, redirects)
                   for page in data.get('query', {}).get('pages', {}).values()]) if record]
        temporary = path.with_suffix('.tmp')
        temporary.write_text(''.join(json.dumps(record, ensure_ascii=False) + '\n' for record in records), encoding='utf-8')
        temporary.replace(path)
        done += len(records)
        progress = dict(requested=min(offset + args.batch, len(rows)), total_titles=len(rows), documents=done,
                        seconds=round(time.monotonic() - started, 1), current_batch=offset)
        (out / 'progress.json').write_text(json.dumps(progress), encoding='utf-8')
        print(json.dumps(progress), flush=True)
    pool.shutdown()
    manifest = dict(format='cael-static-wikipedia-v1', curriculum=curriculum, documents=done,
                    batches={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(chunks.glob('*.jsonl'))},
                    source='Wikipedia core-topic text only; no images or user conversations', licence='CC BY-SA 4.0',
                    collected_at=datetime.now(timezone.utc).isoformat(), parser='mwparserfromhell ' + mwparserfromhell.__version__)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('DONE', done, flush=True)


if __name__ == '__main__':
    main()
