"""Fresh authored instances generated only after exact source freeze."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
from core_cases import make_cases
H=Path(__file__).resolve().parent
assert (H/'SOURCE_FREEZE.json').exists()
dest=H/'confirmation_cases.json';assert not dest.exists()
cases=make_cases(4071139,scale=3)
# The shared generator's four fixed syntax-boundary fixtures were deliberately
# rejected by the exact-overlap guard. Author new values before any responses;
# do not relax the guard, alter the model, or reuse development fixtures.
fresh_invalid=[dict(examples=[dict(input=[2],output=[3]),dict(input=[2],output=[4])],query=[2]),
               dict(examples=[dict(input=[3,4],output=[4,3])]*2,query=[4,3],solution=[3,4]),
               dict(examples=[dict(input=[1,2],output=[2,1])]*2,query=[True]),
               dict(examples=[dict(input=[1,2,3],output=[2,3])]*2,query=[3,2,1])]
for case,payload in zip([c for c in cases if c['family']=='invalid-transition'],fresh_invalid,strict=True):
    case['prompt']='Infer discrete transition: '+json.dumps(payload)
prior=json.loads((H/'development_cases2.json').read_text())
assert not {c['prompt'] for c in cases}&{c['prompt'] for c in prior}
dest.write_text(json.dumps(cases,indent=2)+'\n',encoding='utf-8')
(H/'CONFIRMATION_SEAL.json').write_text(json.dumps(dict(created_utc=datetime.now(timezone.utc).isoformat(),
    source_freeze_sha256=hashlib.sha256((H/'SOURCE_FREEZE.json').read_bytes()).hexdigest(),
    input_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),cases=len(cases),seed=4071139,
    positive=sum(not c['safety'] for c in cases),boundaries=sum(c['safety'] for c in cases),
    scope='New authored instances of development-aware finite families, not an independent public benchmark'),indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(cases=len(cases),positive=sum(not c['safety'] for c in cases),boundaries=sum(c['safety'] for c in cases))))
