"""Build a portable CAEL 0.2.1 ZIP from explicit public source paths."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
PUBLIC_FILES = ['README.md', 'MODEL_CARD.md', 'STORY_MODEL.md', 'STORY_MODEL_CARD.md',
                'REPORT.md', 'NOTICE.md', 'LICENSE', 'PROTOCOL.md', 'requirements.txt',
                'requirements-unified.txt', 'requirements-training.txt', 'cael.py', 'chat.py',
                'curriculum.py', 'train.py', 'evaluate.py', 'build_release.py',
                'build_unified_bundle.py', 'bundle_config.json', 'natural_prompts.json',
                'natural_frame_holdout.json', '.gitignore', '.gitattributes', 'RUN.bat', 'SETUP.bat']
PUBLIC_DIRS = ['cael_unified', 'cael_image', 'cael_assistant', 'chat_v6_7', 'licenses',
               'models/cael-story-0.1', 'reference', 'results', 'tests', '.github']


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def public_paths():
    paths = [ROOT / p for p in PUBLIC_FILES]
    for directory in PUBLIC_DIRS:
        paths.extend(p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths = sorted(set(paths))
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        relative = path.relative_to(ROOT)
        if any(part in ('research', 'outputs', '.git', '.venv', 'chat_worker') for part in relative.parts):
            raise ValueError('Private or local-only path in source archive')
        if path.suffix.lower() in ('.pt', '.safetensors', '.sqlite', '.duckdb') or path.name in ('chat_backend.json', 'relay_key.txt', 'ui_token.txt'):
            raise ValueError('Unapproved weight, credential or database in source archive')
    return paths


def source_bytes(path):
    """Match Git's declared LF text format without modifying the checkout."""
    raw = path.read_bytes()
    relative = path.relative_to(ROOT)
    binary = relative.parts[0] == 'models' or relative.as_posix() == 'reference/model.json'
    text = path.suffix.lower() in ('.py', '.md', '.json', '.yml', '.yaml', '.txt', '.bat') or path.name in ('.gitignore', '.gitattributes')
    return raw.replace(b'\r\n', b'\n') if text and not binary else raw


def main(out, bundle):
    if out.exists():
        raise FileExistsError(out)
    paths = public_paths()
    sums = {p.relative_to(ROOT).as_posix(): hashlib.sha256(source_bytes(p)).hexdigest() for p in paths}
    if bundle:
        if not bundle.is_file():
            raise FileNotFoundError(bundle)
        config = json.loads((ROOT / 'bundle_config.json').read_text())
        if digest(bundle) != config['sha256']:
            raise ValueError('Bundle differs from release configuration')
        sums['models/cael-0.2.1.cael'] = config['sha256']
    manifest = ROOT / 'SHA256SUMS.json'
    manifest.write_text(json.dumps(sums, indent=2) + '\n', encoding='utf-8')
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths + [manifest]:
            info = zipfile.ZipInfo('CAEL-0.2.1/' + path.relative_to(ROOT).as_posix(), date_time=(2026, 10, 16, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source_bytes(path))
        if bundle:
            archive.write(bundle, 'CAEL-0.2.1/models/cael-0.2.1.cael', compress_type=zipfile.ZIP_STORED)
    print(json.dumps(dict(archive=str(out), sha256=digest(out), bytes=out.stat().st_size, source_files=len(paths)), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'dist' / 'CAEL-0.2.1.zip')
    parser.add_argument('--bundle', type=Path, default=ROOT / 'dist' / 'cael-0.2.1.cael')
    parser.add_argument('--source-only', action='store_true')
    args = parser.parse_args()
    main(args.out.resolve(), None if args.source_only else args.bundle.resolve())
