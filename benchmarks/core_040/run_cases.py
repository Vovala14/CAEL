"""Actual unified replies with identical offline/configuration contracts."""
from pathlib import Path
import argparse,hashlib,json,os,socket,sys,time
H=Path(__file__).resolve().parent;P=H.parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--runtime',required=True);ap.add_argument('--cases',required=True,type=Path);ap.add_argument('--label',required=True);a=ap.parse_args()
O=H/a.runtime;R=H/'case_runs'/a.label;R.mkdir(parents=True,exist_ok=False)
os.environ.update(CAEL_WEB_SEARCH='0',CAEL_LTM=str(R/'ltm.json'),CAEL_MEMORY_FILE=str(R/'memory.json'),
                  OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode=True
sys.path[:0]=[str(O),str(P/'research/release_039_20261107/deployment_extra_deps'),str(P/'research/release_039_20261107/deploy_deps')]
def denied(*args,**kwargs):raise RuntimeError('Offline qualification: network disabled')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=socket.socket.connect_ex=denied
from core_cases import accepted,score
from cael_unified import Assistant
model=Assistant(output_root=R/'outputs')
cases=json.loads(a.cases.read_text(encoding='utf-8'));rows=[]
for case in cases:
    started=time.perf_counter();error=None;reply=None
    try:reply=model.respond(case.get('messages') or [dict(role='user',content=case['prompt'])],seed=401107,mode='chat')
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    rows.append(dict(id=case['id'],family=case['family'],safety=case['safety'],prompt=case['prompt'],expected=case['expected'],
                     reply=reply,error=error,accepted=accepted(reply),correct=score(case,reply,error),seconds=time.perf_counter()-started))
    (R/'rows.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
families={f:dict(correct=sum(x['correct'] for x in rows if x['family']==f),total=sum(x['family']==f for x in rows)) for f in sorted({x['family'] for x in rows})}
summary=dict(total=len(rows),correct=sum(r['correct'] for r in rows),errors=sum(bool(r['error']) for r in rows),families=families,
    cases_sha256=hashlib.sha256(a.cases.read_bytes()).hexdigest(),source_sha256={p.relative_to(O).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (O/'cael_unified').rglob('*.py')},
    configuration='Identical fresh installer selections; inherited count fallback active in both',offline=True,
    limitations=['Authored/adaptive known-family development; not an external benchmark or general chat score'])
(R/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:summary[k] for k in ['total','correct','errors','families']}),flush=True)
