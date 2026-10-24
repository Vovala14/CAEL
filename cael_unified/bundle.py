"""Integrity-checked portable bundle; no private machine paths or credentials."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.2.9'
SUPPORTED = {'0.2.1', '0.2.2', '0.2.3', '0.2.4', '0.2.5', '0.2.6', '0.2.7', '0.2.8', '0.2.9'}
DEFAULT_BUNDLE = ROOT / 'models' / f'cael-{VERSION}.cael'
INSTALLED = 'models/'   # bundle members under models/ are installed into the checkout, not the cache
REQUIRED = {'chat/knowledge.json.gz',
            'story/model.json', 'emoji/model.pt', 'emoji/references.pt', 'emoji/learned.pt',
            'emoji/learned_sources.json', 'image/model.pt', 'portrait/model.pt'}
PICTURE_FILES = {'image/model.pt', 'portrait/model.pt'}
# Members of older bundles that are never shipped or loaded again: the 0.2.1 small-talk reply models were fitted on
# EmpatheticDialogues (CC BY-NC 4.0, non-commercial). CAEL uses only data that allows commercial use.
NON_COMMERCIAL = {'chat/model_v1.json.gz', 'chat/model_v2.json.gz'}


def required_members(manifest):
    profile = manifest.get('profile', 'full')
    if profile not in ('full', 'no-images'):
        raise ValueError('Unsupported bundle profile')
    if profile == 'no-images':
        files = manifest.get('files', {})
        if any(name.startswith(('image/', 'portrait/', 'models/cael-image-', 'models/cael-general-')) for name in files):
            raise ValueError('Image model in a no-images bundle')
        if any(key in manifest.get('selections', {}) for key in ('general_image', 'hybrid_image', 'portrait_image')):
            raise ValueError('Image selection in a no-images bundle')
        return REQUIRED - PICTURE_FILES
    return REQUIRED


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
        if len(names) != len(set(names)) or sum(i.file_size for i in entries) > 4 * 1024 ** 3:
            raise ValueError('Duplicate entries or oversized model bundle')
        for entry in entries:
            safe_member(entry.filename)
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Symlinks are not permitted in a model bundle')
        manifest = json.loads(archive.read('bundle.json'))
        if manifest.get('format') != 'cael-unified-v1' or manifest.get('version') not in SUPPORTED:
            raise ValueError('Unsupported model bundle format or version')
        files = manifest['files']
        if set(names) != set(files) | {'bundle.json'} or not required_members(manifest) <= set(files):
            raise ValueError('Incomplete or unlisted model bundle files')
        for name in files:
            safe_member(name)
        cached = {name: expected for name, expected in files.items() if not name.startswith(INSTALLED)}
        if destination.is_dir():
            for name, expected in cached.items():
                if digest(destination / name) != expected:
                    raise ValueError('Cached model file failed its checksum: ' + name)
            return destination, manifest
        staging = Path(tempfile.mkdtemp(prefix='extract-', dir=cache_root))
        for name, expected in cached.items():
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
            for name, expected in cached.items():
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
    request = urllib.request.Request(config['url'], headers={'User-Agent': f'CAEL/{VERSION}'})
    temporary = destination.with_suffix('.download')
    with urllib.request.urlopen(request, timeout=180) as source, temporary.open('wb') as output:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            output.write(block)
    if digest(temporary) != config['sha256']:
        raise ValueError('Downloaded bundle failed its checksum')
    temporary.rename(destination)
    return destination


def install_models(path=None, root=ROOT):
    """Install the bundle's models/ folders into the checkout and record its model selections.

    Existing identical files are kept; a different existing file is never overwritten (local
    experiments stay intact). The selections become research/active_models.json only when that
    file does not exist yet, so a developer machine keeps its own choices.
    """
    path = Path(path or DEFAULT_BUNDLE).resolve()
    root = Path(root)
    installed = kept = conflicts = 0
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read('bundle.json'))
        if manifest.get('format') != 'cael-unified-v1' or manifest.get('version') not in SUPPORTED:
            raise ValueError('Unsupported model bundle format or version')
        for name, expected in manifest['files'].items():
            if not name.startswith(INSTALLED):
                continue
            target = root.joinpath(*safe_member(name).parts)
            if target.exists():
                if digest(target) == expected:
                    kept += 1
                else:
                    conflicts += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + '.partial')
            with archive.open(name) as source, partial.open('wb') as output:
                actual = hashlib.sha256()
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    actual.update(block)
                    output.write(block)
            if actual.hexdigest() != expected:
                partial.unlink()
                raise ValueError('Model file failed its checksum: ' + name)
            partial.replace(target)
            installed += 1
    selections = root / 'research' / 'active_models.json'
    wrote = False
    if manifest.get('selections') and not selections.exists():
        chosen = {}
        for key, entry in manifest['selections'].items():
            entry = dict(entry)
            if 'path' in entry:          # code-only selections (the multiple-choice chooser) carry no file
                entry['path'] = str(root.joinpath(*safe_member(entry['path']).parts))
            chosen[key] = entry
        selections.parent.mkdir(parents=True, exist_ok=True)
        selections.write_text(json.dumps(chosen, indent=2), encoding='utf-8')
        wrote = True
    return dict(installed=installed, already_present=kept, kept_local_differences=conflicts, wrote_selections=wrote)
