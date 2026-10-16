"""CAEL image v10: v9 generative integer CA guided by a count-learned per-position prior. No NN, no parts, no collage.
Added on top of v9 (everything else is v9 unchanged: data, face-centred crops, palette, rule tables, back-off, metrics):
  prior[L][y, x, colour]   : integer counts of palette colours at every position of every scale, from the training
                             crops (aligned faces when --face-only / face boxes are used). Smoothed toward the global
                             colour histogram so it never pins a pixel to one image.
  sym[L][y, x, coarse(m)]  : integer counts P(colour | coarse colour of the horizontally mirrored cell) per position,
                             a learned left/right pairing statistic (lets an eye on one side favour one on the other).
At every growth and refine step the v9 rule probabilities are multiplied by prior**alpha * sym**beta.
alpha < 1 and stochastic sampling keep diversity; metrics report distance to the mean training image to show
whether output collapsed to the 'mean face'."""
import sys, argparse, json
from pathlib import Path
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cael_image.v9_generative_ca as v9

pre = argparse.ArgumentParser(add_help=False)
pre.add_argument('--prior-alpha', type=float, default=1.0); pre.add_argument('--sym-beta', type=float, default=0.3)
pre.add_argument('--temps', default='1,1,0.9,0.8,0.7', help='sampling temperature per scale 4,8,16,32,64')
pre.add_argument('--guide', default='ratio', choices=['ratio', 'product'], help='ratio = prior/global frequency (no double counting)')
pre.add_argument('--ratio-clamp', type=float, default=4.0, help='ratio boost kept in [1/c, c]')
pre.add_argument('--seed-mode', default='gibbs', choices=['gibbs', 'marginal'], help='marginal = 4x4 drawn once from per-position counts, no sweeps/guide')
pre.add_argument('--guide-from', type=int, default=4, help='apply prior/mirror guide only at scales >= this')
pre.add_argument('--sweeps', default='8,6,6,5,4', help='refine sweeps per scale 4,8,16,32,64')
pre.add_argument('--vram-cap-gb', type=float, default=13.5)
pre.add_argument('--pad', default='clamp', choices=['clamp', 'black'])
pre.add_argument('--prior-smooth', type=float, default=2.0, help='pseudo-count weight of the global colour histogram')
A, rest = pre.parse_known_args(); sys.argv = [sys.argv[0]] + rest

DIAG = dict(scale_mean_lab={}, fallback={})
class GCA10(v9.GCA):
    def draw(s, p, temp, gen):
        bias = getattr(s, 'luminance_bias', 0.0)
        if bias:
            from cael_image.portrait_sampling import luminance_weights
            p = p * luminance_weights(s.pal, bias, temp)
        return super().draw(p, temp, gen)

    def rows(s, table, chain):
        name0, k0 = chain[0]; r0 = table[name0][s.slot(table[name0], name0, k0)]
        n = r0.sum(-1) >= s.minc; L = k0.shape[-1]; key = f'{L}{name0[0]}'
        d = DIAG['fallback'].setdefault(key, [0, 0]); d[0] += int((~n).sum()); d[1] += n.numel()
        return super().rows(table, chain)
    def alloc(s):
        super().alloc()
        s.prior = {L: torch.zeros(L * L, s.P, device=s.dev, dtype=torch.int32) for L in v9.LEVELS}
        s.sym = {L: torch.zeros(L * L * s.Q, s.P, device=s.dev, dtype=torch.int32) for L in v9.LEVELS}
    def observe(s, lab):
        super().observe(lab); p = s.pyr(lab)
        for L in v9.LEVELS:
            g = p[L]; pos = torch.arange(L * L, device=s.dev).reshape(1, L, L).expand_as(g)
            s.add(s.prior[L], pos, g); s.add(s.sym[L], pos * s.Q + s.c(g.flip(2)), g)
    def guide(s, L, g):
        if L < A.guide_from: return 1.0
        pr = s.prior[L].float(); glob = pr.sum(0, keepdim=True); n = pr.sum(1, keepdim=True).clamp_min(1)
        pr = (pr + A.prior_smooth * glob / glob.sum() * n.mean().clamp_min(1) * 0 + A.prior_smooth * glob / glob.sum() * 10) / 1.0
        pr = pr / pr.sum(1, keepdim=True)                                       # (L*L, P)
        gl = glob / glob.sum(); gl = 0.9 * gl + 0.1 / s.P   # floored global frequency
        c = A.ratio_clamp
        if A.guide == 'ratio': pr = (pr / gl).clamp(1 / c, c)   # boost only what is MORE likely here than on average
        out = pr.reshape(1, L, L, s.P) ** A.prior_alpha
        if g is not None and A.sym_beta > 0:
            pos = torch.arange(L * L, device=s.dev).reshape(1, L, L).expand_as(g)
            sy = s.sym[L][pos * s.Q + s.c(g.flip(2))].float() + 0.5
            sy = sy / sy.sum(-1, keepdim=True)
            if A.guide == 'ratio': sy = (sy / gl.reshape(1, 1, 1, s.P)).clamp(1 / c, c)
            out = out * sy ** A.sym_beta
        return out
    def generate(s, B, seed, sweeps=None, temps=None):
        sweeps = tuple(int(x) for x in A.sweeps.split(',')) if sweeps is None else sweeps
        temps = tuple(float(x) for x in A.temps.split(',')) if temps is None else temps
        gen = torch.Generator(device=s.dev); gen.manual_seed(seed)
        ps = s.pos(4).expand(B, 4, 4)
        g = s.draw((s.seed['sp'][ps].float() + 1e-3) * s.guide(4, None), 1.0, gen)
        chk4 = (s.quad(4) == 0) | (s.quad(4) == 3)
        for it in range(0 if A.seed_mode == 'marginal' else sweeps[0] * 2):
            r = s.seed['sf'][ps * s.Q ** 4 + s.k4(g)].float(); back = s.seed['sp'][ps].float() + 1e-3
            pr = torch.where(r.sum(-1, keepdim=True) >= s.minc, r, back) * s.guide(4, g)
            g = torch.where(chk4 == (it % 2 == 0), s.draw(pr, temps[0], gen), g)
        for li, L in enumerate(v9.LEVELS[1:], 1):
            DIAG['scale_mean_lab'].setdefault(L // 2, []).append([float(v) for v in s.pal[g].reshape(-1, 3).mean(0)])
            T = s.t[L]; par = g
            g = s.draw(s.rows(T, s.keys(L, par)) * s.guide(L, None), temps[li], gen)
            chk = (s.quad(L) == 0) | (s.quad(L) == 3)
            for it in range(sweeps[li] * 2):
                new = s.draw(s.rows(T, s.keys(L, par, g)) * s.guide(L, g), temps[li], gen)
                g = torch.where(chk == (it % 2 == 0), new, g)
        DIAG['scale_mean_lab'].setdefault(64, []).append([float(v) for v in s.pal[g].reshape(-1, 3).mean(0)])
        return v9.lab2rgb(s.pal[g])

_stats = v9.stats
def stats10(X, T, gen):  # v9 stats + distance to the mean training image (mean-face collapse check)
    out = _stats(X, T, gen); mu = T.float().mean(0, keepdim=True)
    d = ((X.float() - mu) / 255).reshape(len(X), -1).norm(dim=1) / (X[0].numel() ** 0.5)
    out['dist_to_train_mean_median'] = round(float(d.median()), 4)
    out['mean_lab'] = [round(float(v), 2) for v in v9.rgb2lab(X.float()).reshape(-1, 3).mean(0)]
    if DIAG['scale_mean_lab']:
        out['scale_mean_lab'] = {L: [round(sum(x[i] for x in v) / len(v), 2) for i in range(3)] for L, v in sorted(DIAG['scale_mean_lab'].items())}
        out['fallback_rate'] = {k: round(a / max(b, 1), 3) for k, (a, b) in DIAG['fallback'].items()}
        print('SCALE_DIAG', json.dumps(out['scale_mean_lab']), 'FALLBACK', json.dumps(out['fallback_rate']), flush=True)
    return out
v9.stats = stats10; v9.GCA = GCA10; v9.PAD_MODE = A.pad
if __name__ == '__main__':
    if torch.cuda.is_available():   # hard VRAM cap: allocations beyond it raise OOM instead of spilling past the limit
        tot = torch.cuda.get_device_properties(0).total_memory
        torch.cuda.set_per_process_memory_fraction(min(1.0, A.vram_cap_gb * 2**30 / tot))
        print(f'VRAM cap {A.vram_cap_gb} GiB of {tot / 2**30:.1f} GiB', flush=True)
    print(f'v10 guide: prior_alpha={A.prior_alpha} sym_beta={A.sym_beta} prior_smooth={A.prior_smooth} temps={A.temps} pad={A.pad} guide={A.guide}', flush=True)
    v9.main()

