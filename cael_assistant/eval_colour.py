"""Measure whether colour words change the output: same seeds, 48 samples each, no selection.
Metric: share of clothing/hair-region pixels within dE<25 of the target colour (hand-defined Lab targets)."""
import sys, json, torch; sys.path.insert(0, __import__('os').path.dirname(__file__))
import imagegen as ig
t = ig.ImageTool(); m = t.ensure(); res = {}
for targets in [[], [('clothing','red')], [('clothing','blue')], [('clothing','green')], [('hair','blonde')], [('hair','red')]]:
    for st in ([0.0] if not targets else [0.15, 0.35]):
        _, G = ig.generate2(t, targets, n=48, oversample=1, seed=777, strength=st, outdir=ig.HERE/'outputs'/'eval_colour', tag='eval', select=False)
        row = {}
        for reg, col in [('clothing','red'),('clothing','blue'),('clothing','green'),('hair','blonde'),('hair','red')]:
            row[f'{reg}:{col}'] = round(float(ig.colour_score(m, G, [(reg, col)]).mean()), 3)
        res[f'{targets} s={st}'] = row; print(json.dumps({f'{targets} s={st}': row}), flush=True)
json.dump(res, open(ig.HERE/'outputs'/'eval_colour'/'colour_effect.json','w'), indent=1)
print('peak VRAM', round(torch.cuda.max_memory_allocated()/2**30,2))

