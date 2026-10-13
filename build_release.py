"""Build a portable CAEL archive from explicit public project paths."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent
PUBLIC_FILES=['README.md','MODEL_CARD.md','REPORT.md','NOTICE.md','LICENSE',
    'PROTOCOL.md','requirements.txt','cael.py','chat.py','train.py','evaluate.py',
    'build_release.py','natural_prompts.json','natural_frame_holdout.json',
    '.gitignore','.gitattributes','results/portability.json']
PUBLIC_DIRS=['models/cael-story-0.1','reference','results/cael-story-0.1','tests','.github']

def main(out):
    paths=[ROOT/p for p in PUBLIC_FILES]
    paths += [p for directory in PUBLIC_DIRS for p in (ROOT/directory).rglob('*')
              if p.is_file() and '__pycache__' not in p.parts]
    missing=[str(p.relative_to(ROOT)) for p in paths if not p.is_file()]
    if missing:raise FileNotFoundError(missing)
    sums={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    manifest=ROOT/'SHA256SUMS.json'
    manifest.write_text(json.dumps(sums,indent=2)+'\n',encoding='utf-8',newline='\n')
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(paths+[manifest]):
            item=zipfile.ZipInfo('CAEL-0.1.0/'+p.relative_to(ROOT).as_posix(),date_time=(2026,10,13,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(item,p.read_bytes())
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
    print(json.dumps(dict(archive=str(out),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),files=len(paths)+1),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=ROOT/'dist'/'cael-story-0.1.0.zip')
    main(p.parse_args().out.resolve())
