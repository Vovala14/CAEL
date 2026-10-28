"""Offline actual-unified reply replay; already-viewed packaging regression."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
assert not args.out.exists(),'Keep prior replay evidence'
sys.path.insert(0,str(ROOT))
os.environ.update(CAEL_WEB_SEARCH='0',CUDA_VISIBLE_DEVICES='',HIP_VISIBLE_DEVICES='')
def denied(*args,**kwargs):raise OSError('Offline packaging regression; network denied')
socket.create_connection=socket.socket.connect=socket.socket.connect_ex=denied
items=[json.loads(line) for line in (HERE/'final.jsonl').read_text(encoding='utf-8').splitlines()]
expected=[json.loads(line) for line in (HERE/'candidate.jsonl').read_text(encoding='utf-8').splitlines()]
settings=json.loads((HERE/'run_settings.json').read_text())
with tempfile.TemporaryDirectory(prefix='cael-release-replay-') as temporary:
    os.environ['CAEL_MEMORY_FILE']=str(Path(temporary)/'synthetic_memory.json')
    os.environ['CAEL_LTM']=str(Path(temporary)/'synthetic_ltm.json')
    from cael_unified import verify,bundle
    original=verify.apply
    verify.apply=lambda text,answer:original(text,answer,record=False)
    from cael_unified.assistant import Assistant
    assistant=Assistant(output_root=Path(temporary)/'outputs')
    rows=[]
    for item,wanted in zip(items,expected):
        assert item['id']==wanted['id']
        messages=[dict(role='system',content=settings['system_prompt'])]+item['history']+[dict(role='user',content=item['question'])]
        answer=assistant.respond(messages,n=1,seed=137,mode='chat')
        rows.append(dict(id=item['id'],reply_equal=answer.get('response','')==wanted['reply'],
            route_equal=answer.get('route')==wanted['route'],reply=answer.get('response',''),route=answer.get('route')))
    assert assistant._image is None and assistant._portrait is None
    record=dict(checked_utc=datetime.now(timezone.utc).isoformat(),version=bundle.VERSION,
        total=len(rows),identical_replies=sum(r['reply_equal'] for r in rows),
        identical_routes=sum(r['route_equal'] for r in rows),rows=rows,
        frozen_input_sha256=hashlib.sha256((HERE/'final.jsonl').read_bytes()).hexdigest(),
        kind='Already-viewed packaging regression, not new capability evidence',
        generated_code_executed_natively=False,network_access=False,images_rendered=0)
    args.out.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    assert len(rows)==80 and all(r['reply_equal'] and r['route_equal'] for r in rows),'Keep mismatches; do not tune frozen capability code'
    print(json.dumps({k:v for k,v in record.items() if k!='rows'}))
