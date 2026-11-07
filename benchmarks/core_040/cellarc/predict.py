"""Actual offline Assistant inference. This process never opens answer files."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,socket,sys,time
H=Path(__file__).resolve().parent;E=H.parent;P=E.parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--engine',choices=['baseline','candidate'],required=True);a=ap.parse_args()
R=H/'runs'/a.engine;R.mkdir(parents=True,exist_ok=False);O=E/(a.engine+'_runtime')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
seal=json.loads((H/'INPUT_SEAL.json').read_text());freeze=json.loads((E/'SOURCE_FREEZE.json').read_text())
assert sha(H/'inputs.jsonl')==seal['artifacts']['inputs.jsonl']
assert sha(H/'predict.py')==seal['evaluator_files']['predict.py']
if a.engine=='candidate':
    for n,v in freeze['files'].items():assert sha(O/n)==v,n
os.environ.update(CAEL_WEB_SEARCH='0',CAEL_LTM=str(R/'ltm.json'),CAEL_MEMORY_FILE=str(R/'memory.json'),
    OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode=True
sys.path[:0]=[str(O),str(P/'research/release_039_20261107/deployment_extra_deps'),str(P/'research/release_039_20261107/deploy_deps')]
def denied(*args,**kwargs):raise RuntimeError('Cellular task evaluation is offline')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=socket.socket.connect_ex=denied
start=time.perf_counter()
from cael_unified import Assistant,__version__
model=Assistant(output_root=R/'outputs');load_seconds=time.perf_counter()-start
rows=[json.loads(line) for line in (H/'inputs.jsonl').read_text().splitlines()]
errors=invalid=0;inference_start=time.perf_counter()
with (R/'predictions.jsonl').open('x',encoding='utf-8') as stream:
    for index,episode in enumerate(rows):
        task=episode['task'];assert set(task)=={'examples','query'}
        prompt='Infer discrete transition: '+json.dumps(task,separators=(',',':'))
        reply=None;error=None;t=time.perf_counter()
        try:reply=model.respond([dict(role='user',content=prompt)],seed=401107,mode='chat')
        except Exception as exc:error=type(exc).__name__+': '+str(exc);errors+=1
        elapsed=time.perf_counter()-t;prediction=None
        if reply is not None:
            try:
                decoded=json.loads(reply.get('response',''))
                if type(decoded) is list and len(decoded)==len(task['query']) and all(type(v) is int and 0<=v<=31 for v in decoded):
                    prediction=decoded
                diagnostic=reply.get('automaton') or {}
                if prediction is not None and 'prediction' in diagnostic:assert diagnostic['prediction']==prediction
            except (ValueError,TypeError):pass
        if prediction is None:invalid+=1
        result=dict(id=episode['id'],split=episode['split'],prediction=prediction,reply=reply,error=error,seconds=elapsed)
        stream.write(json.dumps(result,separators=(',',':'))+'\n');stream.flush()
        if (index+1)%250==0:print(json.dumps(dict(engine=a.engine,completed=index+1,total=len(rows))),flush=True)
def peak_memory():
    if os.name!='nt':return None
    import ctypes
    from ctypes import wintypes
    class Memory(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
                  *[(n,ctypes.c_size_t) for n in ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage',
                    'QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage']]]
    data=Memory();data.cb=ctypes.sizeof(data)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Memory),wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(data),data.cb):return None
    return data.PeakWorkingSetSize
result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),complete=True,engine=a.engine,version=__version__,
    total=len(rows),errors=errors,invalid_responses=invalid,load_seconds=load_seconds,
    inference_seconds=time.perf_counter()-inference_start,total_seconds=time.perf_counter()-start,
    peak_process_rss_bytes=peak_memory(),predictions_sha256=sha(R/'predictions.jsonl'),
    inputs_sha256=sha(H/'inputs.jsonl'),source_freeze_sha256=sha(E/'SOURCE_FREEZE.json'),
    actual_assistant=True,external_network_disabled=True,solution_or_metadata_read_by_predictor=False,
    original_resource_selection=json.loads((O/'research/active_models.json').read_text()),
    local_runtime_modules={n:m.__file__ for n,m in sys.modules.items() if n.startswith('cael_unified') and getattr(m,'__file__',None)})
assert all(Path(p).resolve().is_relative_to(O.resolve()) for p in result['local_runtime_modules'].values())
(R/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['engine','total','errors','invalid_responses','load_seconds','inference_seconds','peak_process_rss_bytes']}),flush=True)
