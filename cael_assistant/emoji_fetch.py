"""Fetch emoji from reviewed free commercial sources; reject other licences."""
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import quote

from cael_unified.licensing import commercial_image_licence
from cael_unified.network import NETWORK, allowed_url

CAEL = Path(__file__).resolve().parent.parent
ROOT = CAEL / 'data' / 'emoji_fetch'
IDX = ROOT / '_index'
_LOCK = threading.Lock()


def _get(url, timeout=8):
    return NETWORK.get(url, ttl=86400, timeout=timeout)


def _cached(name, url, ttl=7 * 86400):
    IDX.mkdir(parents=True, exist_ok=True)
    path = IDX / name
    if path.exists() and time.time() - path.stat().st_mtime <= ttl:
        return json.loads(path.read_text(encoding='utf-8'))
    data = _get(url)
    value = json.loads(data)
    path.write_bytes(data)
    return value


def _words(text):
    return set(re.findall(r'[a-z0-9]+', text.lower()))


def openmoji(word, k):
    data = _cached('openmoji.json', 'https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/data/openmoji.json')
    out = []
    words = _words(word)
    for entry in data:
        if entry.get('skintone'):
            continue
        annotation = _words(entry.get('annotation', ''))
        tags = _words(entry.get('tags', '') + ' ' + entry.get('openmoji_tags', ''))
        code = entry.get('hexcode', '')
        if not re.fullmatch('[0-9A-F-]+', code) or not (words <= annotation or words <= tags):
            continue
        rank = -1 if words == annotation else (0 if words <= annotation else 1)
        title = entry.get('annotation', '')
        out.append((rank, dict(url=f'https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/618x618/{code}.png',
                    source='OpenMoji', licence='CC BY-SA 4.0', title=title, attribution='OpenMoji contributors',
                    licence_url='https://creativecommons.org/licenses/by-sa/4.0/')))
        if not code.startswith('E'):
            tw = '-'.join(part for part in code.lower().split('-') if part != 'fe0f')
            out.append((rank, dict(url=f'https://raw.githubusercontent.com/jdecked/twemoji/main/assets/72x72/{tw}.png',
                        source='Twemoji', licence='CC BY 4.0', title=title, attribution='Twitter and Twemoji contributors',
                        licence_url='https://creativecommons.org/licenses/by/4.0/')))
            out.append((rank, dict(url=f'https://raw.githubusercontent.com/EmojiTwo/emojitwo/master/png/128/{tw}.png',
                        source='Emojitwo (EmojiOne 2.2)', licence='CC BY 4.0', title=title,
                        attribution='Emojitwo community; EmojiOne 2.2 by Ranks.com',
                        licence_url='https://creativecommons.org/licenses/by/4.0/')))
    return [item for _, item in sorted(out, key=lambda pair: pair[0])][:k]


def fluent(word, k):
    tree = _cached('fluent_tree.json', 'https://api.github.com/repos/microsoft/fluentui-emoji/git/trees/main?recursive=1')
    out = []
    for entry in tree.get('tree', []):
        path = entry['path']
        if path.startswith('assets/') and '/3D/' in path and path.endswith('.png'):
            name = path.split('/')[1]
            if _words(word) <= _words(name) and 'skin' not in path.lower():
                out.append(dict(url='https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/' + quote(path),
                            source='Microsoft Fluent Emoji', licence='MIT', title=name, attribution='Copyright Microsoft Corporation',
                            licence_url='https://github.com/microsoft/fluentui-emoji/blob/main/LICENSE'))
    return out[:k]


def fetch(word, want=8, min_n=1):
    word = ' '.join(re.findall(r'[a-z0-9]+', str(word).lower()))[:80]
    if not word:
        return []
    want = max(1, min(int(want), 16))
    with _LOCK:
        folder = ROOT / word
        meta = folder / 'sources.json'
        if meta.exists():
            try:
                data = json.loads(meta.read_text(encoding='utf-8'))
                accepted = []
                for item in data['items']:
                    path = (folder / item['file']).resolve()
                    if (path.is_relative_to(folder.resolve()) and path.is_file() and
                            commercial_image_licence(item.get('licence')) and allowed_url(item.get('url', '')) and
                            not item.get('source', '').startswith('Openverse')):
                        accepted.append(dict(item, path=str(path)))
                if accepted:
                    return accepted[:want]
            except (ValueError, KeyError, TypeError):
                pass
        candidates = []
        for provider in (openmoji, fluent):
            try:
                candidates += provider(word, want)
            except (OSError, RuntimeError, ValueError, KeyError):
                continue
        items = []
        for candidate in candidates[:want]:
            if not commercial_image_licence(candidate.get('licence')) or not allowed_url(candidate.get('url', '')):
                continue
            try:
                pixels = _get(candidate['url'])
                if not pixels.startswith(b'\x89PNG\r\n\x1a\n'):
                    continue
                folder.mkdir(parents=True, exist_ok=True)
                filename = f'{len(items):02d}.png'
                (folder / filename).write_bytes(pixels)
                items.append(dict(candidate, file=filename))
            except (OSError, RuntimeError):
                continue
        if items:
            meta.write_text(json.dumps(dict(word=word, fetched=time.strftime('%Y-%m-%d %H:%M'), items=items), indent=2), encoding='utf-8')
        return [dict(item, path=str(folder / item['file'])) for item in items]
