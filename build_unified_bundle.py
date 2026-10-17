"""Build the 0.2.3 model bundle from an explicit, privacy-auditable input allowlist.

0.2.3 = the published 0.2.1 bundle (chat, emoji, portrait, base image, story 0.1) plus the
runtime model folders the live assistant now uses, installed under models/ by
`python -m cael_unified --download`, and the model selections that make a fresh checkout
behave like the reviewed live configuration.
"""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

from cael_unified.bundle import REQUIRED, ROOT, VERSION, digest

# Runtime model folders, file by file where a folder also holds experiment leftovers.
MODEL_FILES = {
    'models/cael-language-0.3.2-math-python': None,          # whole folder: weights, licences, notices
    'models/cael-knowledge-v1': ['knowledge.sqlite', 'query_policy.json', 'query_report.json', 'ranker.json', 'report.json'],
    'models/cael-image-hybrid-0.3.9': ['final_102_topics.npz'],
    'models/cael-story-0.3.7-r2': None,
    'models/cael-prompts-0.3.7-r2': None,
    'models/cael-request-policy-0.3.6-r1': None,
    'models/cael-request-policy-v1': None,
    'models/cael-news-policy-0.3.6-r1': None,
    'models/cael-news-policy-v1': None,
    'models/cael-reasoning-v1': None,
    'models/cael-social-v1': None,
    'models/cael-code-0.3.8': None,
}
# Selected in the live configuration; general_image is dropped because the hybrid model covers all its subjects.
SELECTIONS = ('story', 'language', 'request_policy', 'news_policy', 'prompt', 'hybrid_image', 'choice')


def model_files():
    files = {}
    for folder, names in MODEL_FILES.items():
        base = ROOT / folder
        paths = [base / n for n in names] if names else sorted(p for p in base.rglob('*') if p.is_file())
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(path)
            if path.suffix in ('.pt',) or 'private' in path.name.lower():
                raise ValueError('Unexpected weight or private file in runtime model folder: ' + str(path))
            files[path.relative_to(ROOT).as_posix()] = path
    return files


def selections(files):
    live = json.loads((ROOT / 'research' / 'active_models.json').read_text(encoding='utf-8'))
    out = {}
    for key in SELECTIONS:
        entry = dict(live[key])
        if 'path' not in entry:
            # Code-only selection (multiple-choice chooser): its settings are tied to reviewed code by sha256.
            for name, expected in entry.get('code', {}).items():
                if digest(ROOT / 'cael_unified' / f'{name}.py') != expected:
                    raise ValueError(f'Selected {key} code {name}.py changed since it was reviewed')
            entry.pop('review', None)
            out[key] = entry
            continue
        relative = Path(entry['path']).resolve().relative_to(ROOT).as_posix()
        if relative not in files:
            raise ValueError(f'Selected {key} model {relative} is not in the bundle')
        if digest(files[relative]) != entry['sha256']:
            raise ValueError(f'Selected {key} model changed since it was reviewed')
        entry['path'] = relative
        entry.pop('review', None)          # review logs live in the private research folder
        out[key] = entry
    return out


def build(base_bundle, output):
    base_bundle, output = Path(base_bundle), Path(output)
    if output.exists():
        raise FileExistsError(output)
    extra = model_files()
    chosen = selections(extra)
    with zipfile.ZipFile(base_bundle) as base:
        base_manifest = json.loads(base.read('bundle.json'))
        if base_manifest.get('version') != '0.2.1' or not REQUIRED <= set(base_manifest['files']):
            raise ValueError('Base must be the published 0.2.1 bundle')
        licences = {'licenses/' + p.name: p for p in (ROOT / 'licenses').iterdir() if p.is_file()}
        licences['licenses/CAEL-LICENSE.txt'] = ROOT / 'LICENSE'
        components = dict(base_manifest['components'])
        components.update({
            'language': 'Unified count language 0.3.2 (sparse token counts; MIT / CC BY / CC BY-SA sources with notices)',
            'knowledge': 'Local Wikipedia knowledge snapshot (CC BY-SA 4.0) with lookup policy and ranker',
            'hybrid_image': '102-topic hybrid image model 0.3.9: PCA layout + patch synthesis from local SD1.5 renders',
            'story': 'Story 0.3.7-r2 bounded integer planner', 'prompt': 'Prompt writer 0.3.7-r2',
            'policies': 'Request and news routing policies, reasoning and social reasoning counts',
            'code': 'Code-search operation costs 0.3.8 (from MBPP training syntax trees, CC BY 4.0)',
            'reasoning': 'Rule chaining, case analysis (or / contradiction), story tracking; motivation table counted from bAbI task 20 train (CC BY 3.0)',
            'choice': 'Multiple-choice chooser settings (language model + local evidence + exact word-problem arithmetic)'})
        manifest = dict(base_manifest, version=VERSION, components=components, selections=chosen,
                        architecture='Shared router and one archive of distinct non-neural engines, not a single jointly trained weight tensor',
                        private_training_photos_included=False, credentials_included=False, private_queries_included=False,
                        training_teacher='Neural Stable Diffusion 1.5 for synthetic image data only; every runtime engine is non-neural')
        files = {}
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            def add(name, source_open, size_hint=None):
                info = zipfile.ZipInfo(name, date_time=(2026, 10, 17, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                with source_open() as source, archive.open(info, 'w', force_zip64=True) as target:
                    shutil.copyfileobj(source, target, 1024 * 1024)
            for name, expected in sorted(base_manifest['files'].items()):
                if name.startswith('licenses/'):
                    continue                     # replaced by the current, larger licence set
                add(name, lambda n=name: base.open(n))
                files[name] = expected
            for name, path in sorted({**licences, **extra}.items()):
                add(name, lambda p=path: p.open('rb'))
                files[name] = digest(path)
            manifest['files'] = files
            archive.writestr('bundle.json', json.dumps(manifest, indent=2))
    result = dict(version=VERSION, url=f'https://github.com/Vovala14/CAEL/releases/download/v{VERSION}/cael-{VERSION}.cael',
                  sha256=digest(output), bytes=output.stat().st_size)
    (ROOT / 'bundle_config.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default=str(ROOT / 'models' / 'cael-0.2.1.cael'))
    parser.add_argument('--out', default=str(ROOT / 'dist' / f'cael-{VERSION}.cael'))
    args = parser.parse_args()
    build(args.base, args.out)
