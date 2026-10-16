"""Build the 0.2.1 bundle from an explicit, privacy-auditable input allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from cael_unified.bundle import REQUIRED, ROOT, digest


def build(inputs, general_model, output):
    inputs, general_model, output = Path(inputs), Path(general_model), Path(output)
    if output.exists():
        raise FileExistsError(output)
    files = {name: inputs / name for name in REQUIRED if name != 'image/model.pt'}
    files['image/model.pt'] = general_model
    for path in (ROOT / 'licenses').iterdir():
        if path.is_file():
            files['licenses/' + path.name] = path
    files['licenses/CAEL-LICENSE.txt'] = ROOT / 'LICENSE'
    manifest = dict(format='cael-unified-v1', version='0.2.1',
                    components={'chat': 'Portable legacy CA chat fallback and small factual store',
                                'helper': 'Authored exact arithmetic and existing writing programs',
                                'emoji': 'Caption-conditioned integer CA v7, public Noto/Blobmoji references',
                                'portrait': 'v15 aggregate registered appearance parameters, no private source records',
                                'image': '32 subject-conditioned statistical appearance models trained on local SD1.5 synthetic outputs'},
                    architecture='Shared router and one model archive containing distinct engines, not a single jointly trained weight tensor',
                    private_training_photos_included=False, credentials_included=False,
                    photo_guard_limit='Public synthetic references only. Private portrait source references are not distributed.',
                    training_teacher='Neural Stable Diffusion 1.5; runtime image and emoji samplers are non-neural',
                    files={name: digest(path) for name, path in sorted(files.items())})
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 16, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with path.open('rb') as source, archive.open(info, 'w', force_zip64=True) as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
        archive.writestr('bundle.json', json.dumps(manifest, indent=2))
    result = dict(version='0.2.1', url='https://github.com/Vovala14/CAEL/releases/download/v0.2.1/cael-0.2.1.cael',
                  sha256=digest(output), bytes=output.stat().st_size)
    (ROOT / 'bundle_config.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True)
    parser.add_argument('--general-model', required=True)
    parser.add_argument('--out', default=str(ROOT / 'dist' / 'cael-0.2.1.cael'))
    args = parser.parse_args()
    build(args.inputs, args.general_model, args.out)
