"""One-time: rebuild the i16 v10 prior/sym counts (not saved in model_v9.pt) and per-caption-word position/colour
counts from the same training crops + captions, on this PC only. Saves integer counts to model_cache/cond_i16.pt.
Images never leave the PC; only counts are stored."""
import sys, json, re, collections
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import imagegen as ig
v9, v10 = ig.v9, ig.v10
WORDS = ['red','black','white','pink','blue','green','yellow','purple','brown','dark','blonde','orange','grey','gray',
         'dress','bikini','top','shirt','hat','hair','long','short','tattoos','glasses','smiling','beach','bed','mirror',
         'bathroom','couch','pool','room','wall']
COLS = ['red','black','white','pink','blue','green','yellow','purple','brown','orange','grey','gray','blonde']
GARM = ['dress','bikini','top','shirt','hat','hair','shorts','suit','sweater','jacket']
MINI = 12
m = ig.load_model(); a = m.args; root = Path(a['root'])
boxes = json.loads((ig.CAEL / a['face_boxes']).read_text(encoding='utf-8'))
items = v9.gather(root, [x for x in a['sources'].split(',') if x], a['include_root'], boxes)
if a['face_only']: items = [it for it in items if it[1] is not None]
cfg = json.load(open(ig.CAEL / a['config'], encoding='utf-8-sig'))
rng = np.random.default_rng(cfg['seed']); idx = rng.permutation(len(items)); nv = max(8, int(len(items) * cfg['validation_fraction']))
tr = idx[nv:]
print('train items', len(tr), flush=True)
def cap(rel):
    p = (root / rel).with_suffix('.txt')
    return re.findall(r'[a-z]+', p.read_text(encoding='utf-8', errors='ignore').lower()) if p.exists() else []
toks = {}
for i in tr:
    w = cap(items[i][0]); s = set(w)
    s |= {f'{x} {y}' for x, y in zip(w, w[1:]) if x in COLS and y in GARM}
    toks[i] = s
dfc = collections.Counter(t for s in toks.values() for t in s)
keys = [k for k in set(WORDS) | {k for k in dfc if ' ' in k} if dfc[k] >= MINI]
print('captioned', sum(1 for s in toks.values() if s), 'keys', sorted((k, dfc[k]) for k in keys), flush=True)
m.prior = {L: torch.zeros(L * L, m.P, device=m.dev, dtype=torch.int32) for L in v9.LEVELS}
m.sym = {L: torch.zeros(L * L * m.Q, m.P, device=m.dev, dtype=torch.int32) for L in v9.LEVELS}
W = {k: {L: torch.zeros(L * L, m.P, device=m.dev, dtype=torch.int32) for L in (16, 32)} for k in keys}
tr = list(tr)
for b in range(0, len(tr), 64):
    ids = tr[b:b + 64]
    X = torch.from_numpy(np.stack([v9.load64(root, items[i][0], items[i][1], a['zoom']) for i in ids])).to(m.dev)
    lab = v9.rgb2lab(X.float())
    for flip in (False, True) if a['flip'] else (False,):
        x = lab.flip(2) if flip else lab; p = m.pyr(x)
        for L in v9.LEVELS:
            g = p[L]; pos = torch.arange(L * L, device=m.dev).reshape(1, L, L).expand_as(g)
            m.add(m.prior[L], pos, g); m.add(m.sym[L], pos * m.Q + m.c(g.flip(2)), g)
        for j, i in enumerate(ids):
            for k in toks[i]:
                if k in W:
                    for L in (16, 32):
                        g = p[L][j:j+1]; pos = torch.arange(L * L, device=m.dev).reshape(1, L, L)
                        m.add(W[k][L], pos, g)
    print('batch', b, flush=True)
out = dict(prior={L: v.cpu() for L, v in m.prior.items()}, sym={L: v.cpu() for L, v in m.sym.items()}, min_images=MINI,
           words={k: dict(n=dfc[k], prior={L: v.cpu() for L, v in W[k].items()}) for k in keys}, n_train=len(tr))
torch.save(out, ig.COND); print('saved', ig.COND)
if m.dev.type == 'cuda': print('peak VRAM GiB', round(torch.cuda.max_memory_allocated() / 2**30, 2))
