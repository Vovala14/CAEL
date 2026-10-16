"""Integrity-checked portable bundle; no private machine paths or credentials."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / 'models' / 'cael-0.2.1.cael'
REQUIRED = {'chat/model_v1.json.gz', 'chat/model_v2.json.gz', 'chat/knowledge.json.gz',
            'story/model.json', 'emoji/model.pt', 'emoji/references.pt', 'emoji/learned.pt',
            'emoji/learned_sources.json', 'image/model.pt', 'portrait/model.pt'}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def safe_member(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name or not path.parts:
        raise ValueError('Unsafe model bundle member')
    return path


def open_bundle(path=None, cache_root=None):
    path = Path(path or os.environ.get('CAEL_MODEL_BUNDLE', DEFAULT_BUNDLE)).resolve()
    if not path.is_file():
        raise FileNotFoundError('Model bundle missing. Run: python -m cael_unified --download')
    fingerprint = digest(path)
    cache_root = Path(cache_root or path.parent / '.cael-cache')
    cache_root.mkdir(parents=True, exist_ok=True)
    destination = cache_root / fingerprint
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or sum(i.file_size for i in entries) > 2 * 1024 ** 3:
            raise ValueError('Duplicate entries or oversized model bundle')
        for entry in entries:
            safe_member(entry.filename)
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Symlinks are not permitted in a model bundle')
        manifest = json.loads(archive.read('bundle.json'))
        if manifest.get('format') != 'cael-unified-v1' or manifest.get('version') != '0.2.1':
            raise ValueError('Unsupported model bundle format or version')
        files = manifest['files']
        if set(names) != set(files) | {'bundle.json'} or not REQUIRED <= set(files):
            raise ValueError('Incomplete or unlisted model bundle files')
        for name in files:
            safe_member(name)
        if destination.is_dir():
            for name, expected in files.items():
                if digest(destination / name) != expected:
                    raise ValueError('Cached model file failed its checksum: ' + name)
            return destination, manifest
        staging = Path(tempfile.mkdtemp(prefix='extract-', dir=cache_root))
        for name, expected in files.items():
            target = staging.joinpath(*safe_member(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open('xb') as output:
                actual = hashlib.sha256()
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    actual.update(block)
                    output.write(block)
            if actual.hexdigest() != expected:
                raise ValueError('Model file failed its checksum: ' + name)
        (staging / 'bundle.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        try:
            staging.rename(destination)
        except FileExistsError:
            # Another reader may have completed the same immutable cache.
            for name, expected in files.items():
                if digest(destination / name) != expected:
                    raise ValueError('Concurrent bundle cache failed verification')
    return destination, manifest


def download_bundle(destination=None):
    config = json.loads((ROOT / 'bundle_config.json').read_text(encoding='utf-8'))
    destination = Path(destination or DEFAULT_BUNDLE)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if digest(destination) != config['sha256']:
            raise ValueError('Existing bundle differs from the release checksum; choose another path')
        return destination
    request = urllib.request.Request(config['url'], headers={'User-Agent': 'CAEL/0.2.1'})
    temporary = destination.with_suffix('.download')
    with urllib.request.urlopen(request, timeout=180) as source, temporary.open('wb') as output:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            output.write(block)
    if digest(temporary) != config['sha256']:
        raise ValueError('Downloaded bundle failed its checksum')
    temporary.rename(destination)
    return destination
