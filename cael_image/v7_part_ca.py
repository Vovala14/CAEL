"""CAEL image v7: part skeleton + region CA + head-crop face counts + 3x3 texture CA. No neural nets.
Builds on v6 (Lab palette, regions, cluster templates, colour schemes) and adds:
 1. Part skeleton per cluster: head box (skin region, upper 60%), hair region (most common non-skin region in a ring
    above/around head), torso/clothes region (below head, centre), background region (border mode). Head centre/size
    are stored as per-cluster integer MARGINAL histograms (sampled independently, never as one image's tuple).
    Generation draws parts (head ellipse, hair cap, torso trapezoid), mixes that skeleton with the cluster template
    and runs the v6 region CA so regions grow inside the skeleton. Hair is forced to differ from skin.
 2. Face model: 16x16 head crops -> 3 brightness levels (dark/mid/light) count table per position; sampled, mode-filtered
    and grown into the head ellipse as brightness offsets (eyes/mouth dark spots if the data has them).
 3. Texture CA at 64x64: per-region count table P(delta | 4 neighbour deltas) over ternary brightness deltas
    (darker/same/brighter than the 4-neighbour mean), sampled by checkerboard sweeps; amplitude learned per region.
 4. Colour balance: cluster choice uses prior**balance (default 0 = uniform over clusters).
Torch is only a tensor engine ('cuda' via ROCm, or CPU)."""
import argparse, json, sys, time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F  # only interpolate / pad, no layers
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.data import discover, split_records, read_rgb
from cael_image.model import tokens
from cael_image.v4_multiscale_ca import pick_device, stats, shifts
from cael_image.v6_region_ca import CA6, rgb2lab, lab2rgb, mode3, nb_key

def tern_key(t):  # t in {0,1,2}, 4-neighbour key 0..80
    s = shifts(t); return ((s[(-1, 0)] * 3 + s[(1, 0)]) * 3 + s[(0, -1)]) * 3 + s[(0, 1)]
def hist_add(h, idx): h.index_add_(0, idx, torch.ones(len(idx), device=h.device))

class CA7(CA6):
    def fit(s, T, caps, vocab, min_cluster):
        a = super().fit(T, caps, vocab, min_cluster); dev = s.dev; B = len(T); R, K = s.R, s.K
        lab = rgb2lab(T.float()); q = s.quant(lab); r64 = s.reg[q]
        r32 = r64.reshape(B, 32, 2, 32, 2).permute(0, 1, 3, 2, 4).reshape(B, 32, 32, 4).mode(-1).values
        # --- 1. part skeleton statistics (per-image loop runs on CPU: small torch.mode calls are slow on ROCm)
        gdev = dev; dev = torch.device('cpu'); r32c = r32.cpu(); L64c = lab[..., 0].cpu()
        s.hcy = torch.zeros(K * 32, device=dev); s.hcx = torch.zeros(K * 32, device=dev)
        s.hh = torch.zeros(K * 32, device=dev); s.hw = torch.zeros(K * 32, device=dev)
        s.hair = torch.zeros(K * R, device=dev); s.cloth = torch.zeros(K * R, device=dev); s.bg = torch.zeros(K * R, device=dev)
        boxes = []
        for i in range(B):
            r32 = r32c; k = int(a[i]); m = (r32[i] == s.skin); m[19:] = False
            border = torch.cat([r32[i, 0], r32[i, -1], r32[i, :, 0], r32[i, :, -1]]); bgr = int(border.mode().values)
            hist_add(s.bg, torch.tensor([k * R + bgr], device=dev))
            if m.sum() < 6: boxes.append(None); continue
            ys, xs = m.nonzero(as_tuple=True); y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
            cy, cx, h, w = (y0 + y1) // 2, (x0 + x1) // 2, y1 - y0 + 1, x1 - x0 + 1; boxes.append((y0, y1, x0, x1))
            for tab, v in ((s.hcy, cy), (s.hcx, cx), (s.hh, h), (s.hw, w)): hist_add(tab, torch.tensor([k * 32 + min(v, 31)], device=dev))
            ring = r32[i, max(0, y0 - 4):y0 + h // 2, max(0, x0 - 3):x1 + 4].reshape(-1)
            ring = ring[(ring != s.skin) & (ring != bgr)]
            if len(ring): hist_add(s.hair, torch.tensor([k * R + int(ring.mode().values)], device=dev))
            body = r32[i, min(31, y1 + 2):, max(0, cx - w):cx + w + 1].reshape(-1); body = body[(body != s.skin) & (body != bgr)]
            if len(body): hist_add(s.cloth, torch.tensor([k * R + int(body.mode().values)], device=dev))
        for n in ('hcy', 'hcx', 'hh', 'hw'): setattr(s, n, getattr(s, n).reshape(K, 32))
        for n in ('hair', 'cloth', 'bg'): setattr(s, n, getattr(s, n).reshape(K, R))
        # --- 2. face counts: 16x16 crops of brightness relative to crop mean, 3 levels
        s.facec = torch.ones(256, 3, device=dev); L64 = L64c
        for i, bx in enumerate(boxes):
            if bx is None: continue
            y0, y1, x0, x1 = (v * 2 for v in bx); crop = L64[i, y0:y1 + 2, x0:x1 + 2]
            if crop.shape[0] < 6 or crop.shape[1] < 6: continue
            c = F.interpolate(crop[None, None], size=(16, 16), mode='bilinear', align_corners=False)[0, 0]
            d = c - c.mean(); lv = torch.where(d < -8, 0, torch.where(d > 6, 2, 1))
            hist_add(s.facec.view(-1), torch.arange(256, device=dev) * 3 + lv.reshape(-1))
        for n in ('hcy', 'hcx', 'hh', 'hw', 'hair', 'cloth', 'bg', 'facec'): setattr(s, n, getattr(s, n).to(gdev))
        dev = gdev; L64 = lab[..., 0]; r32 = r32c.to(gdev)
        # --- 3. texture CA counts: ternary delta vs 4-neighbour mean, per region
        s.tex = torch.zeros(R * 81 * 3, device=dev); s.amp_r = torch.zeros(R, device=dev); n_r = torch.zeros(R, device=dev)
        for i in range(0, B, 128):
            Lb = L64[i:i + 128]; sh = shifts(Lb.contiguous()) if False else None
            p = F.pad(Lb[:, None], (1, 1, 1, 1), mode='replicate')[:, 0]
            nm = (p[:, :-2, 1:-1] + p[:, 2:, 1:-1] + p[:, 1:-1, :-2] + p[:, 1:-1, 2:]) / 4; d = Lb - nm
            t = torch.where(d < -3, 0, torch.where(d > 3, 2, 1)); rr = r64[i:i + 128]
            hist_add(s.tex, ((rr * 81 + tern_key(t)) * 3 + t).reshape(-1))
            s.amp_r.index_add_(0, rr.reshape(-1), d.abs().reshape(-1)); n_r.index_add_(0, rr.reshape(-1), torch.ones(rr.numel(), device=dev))
        s.tex = s.tex.reshape(R, 81, 3) + 0.5; s.amp_r = s.amp_r / n_r.clamp_min(1)
        return a
    def generate(s, prompts, seed, sweeps=6, text_weight=1.0, smooth=3, near=18.0, face=True, beta=1.0,
                 balance=0.0, skel=0.7, tex_sweeps=8, tex_gain=1.0, face_gain=1.0):
        dev = s.dev; gen = torch.Generator(device=dev); gen.manual_seed(seed); B = len(prompts); R = s.R
        draw = lambda p: torch.multinomial((p / p.sum(-1, keepdim=True)).reshape(-1, p.shape[-1]), 1, generator=gen).reshape(p.shape[:-1])
        ks = []
        for pr in prompts:
            sc = balance * torch.log(s.prior + 1); ids = [s.wi[w] for w in tokens(pr or '') if w in s.wi]
            if ids: sc = sc + text_weight * (torch.log(s.word[ids] + 1) - torch.log(s.prior + 1)).mean(0)
            ks.append(torch.multinomial(torch.softmax(sc, 0), 1, generator=gen))
        k = torch.cat(ks); bi = torch.arange(B, device=dev)
        cy, cx, hh, hw = (draw(getattr(s, n)[k] + 0.2) for n in ('hcy', 'hcx', 'hh', 'hw'))
        hh = hh.clamp(5, 20); hw = hw.clamp(5, 20); cy = cy.clamp(4, 22); cx = cx.clamp(6, 25)
        bgr = draw(s.bg[k] + 0.01)
        hair_p = s.hair[k] + 0.01; hair_p[bi, s.skin] = 0; hair_p[bi, bgr] *= 0.05; hair = draw(hair_p)
        clo_p = s.cloth[k] + 0.01; clo_p[bi, s.skin] = 0; clo = draw(clo_p)
        yy, xx = torch.meshgrid(torch.arange(32, device=dev).float(), torch.arange(32, device=dev).float(), indexing='ij')
        yy, xx = yy[None], xx[None]; cyf, cxf = cy[:, None, None].float(), cx[:, None, None].float()
        ry, rx = hh[:, None, None].float() / 2, hw[:, None, None].float() / 2
        head = ((yy - cyf) / ry) ** 2 + ((xx - cxf) / rx) ** 2 <= 1
        hairm = (((yy - cyf + ry * 0.35) / (ry * 1.35)) ** 2 + ((xx - cxf) / (rx * 1.3)) ** 2 <= 1) & ~head & (yy <= cyf + ry * 0.6)
        top = cyf + ry * 0.9; torso = (yy >= top) & ((xx - cxf).abs() <= rx * (0.9 + 0.08 * (yy - top)))
        part = torch.full((B, 32, 32), 0, device=dev, dtype=torch.long)
        part = torch.where(torso, clo[:, None, None], bgr[:, None, None]); part = torch.where(hairm, hair[:, None, None], part)
        part = torch.where(head, torch.full_like(part, s.skin), part)
        sk = F.one_hot(part, R).float()
        tm = (s.rh[k] + 0.01).reshape(B, 32, 32, R); tm = tm / tm.sum(-1, keepdim=True)
        tmpl = skel * sk + (1 - skel) * tm
        r = draw(tmpl)
        def ca(r, L, t):
            chk = ((torch.arange(L, device=dev)[:, None] + torch.arange(L, device=dev)[None]) % 2)[None]
            for it in range(sweeps * 2):
                rows = s.ca[L][nb_key(r, R)]; ok = rows.sum(-1, keepdim=True) >= s.minc
                loc = torch.where(ok, (rows + 0.1) / (rows.sum(-1, keepdim=True) + 0.1 * R), torch.ones_like(rows))
                r = torch.where(chk == it % 2, draw(t * loc ** beta), r)
            return mode3(r, smooth)
        up = lambda x: x.repeat_interleave(2, 1).repeat_interleave(2, 2)
        r = ca(r, 32, tmpl); r = ca(up(r), 64, up(tmpl))
        # colour scheme (anchor per region; hair/skin/clothes anchors from cluster histograms)
        anchor = draw(s.ch[k] + 1e-6); alab = s.pal[anchor]
        lab = alab[bi[:, None, None], r].clone(); lab[..., 0] = s.regL[r] + up(s.shade[k].reshape(B, 32, 32))
        # texture CA on ternary deltas
        t = draw(torch.ones(B, 64, 64, 3, device=dev))
        chk = ((torch.arange(64, device=dev)[:, None] + torch.arange(64, device=dev)[None]) % 2)[None]
        for it in range(tex_sweeps * 2):
            t = torch.where(chk == it % 2, draw(s.tex[r, tern_key(t)]), t)
        lab[..., 0] = lab[..., 0] + (t.float() - 1) * s.amp_r[r] * 1.6 * tex_gain
        # face: sample 16x16 levels, mode filter, grow into head ellipse
        if face:
            fl = mode3(draw(s.facec.expand(B, 256, 3)).reshape(B, 16, 16), 1)
            off = torch.tensor([-22.0, 0.0, 8.0], device=dev)[fl] * face_gain
            Y, X = torch.meshgrid(torch.arange(64, device=dev).float(), torch.arange(64, device=dev).float(), indexing='ij')
            fy = ((Y[None] / 2 - (cyf - ry)) / (2 * ry) * 16).long(); fx = ((X[None] / 2 - (cxf - rx)) / (2 * rx) * 16).long()
            inside = (fy >= 0) & (fy < 16) & (fx >= 0) & (fx < 16) & (r == s.skin)
            v = off[bi[:, None, None], fy.clamp(0, 15), fx.clamp(0, 15)]
            lab[..., 0] = lab[..., 0] + torch.where(inside, v, torch.zeros_like(v))
        q = s.quant(lab); far = (s.pal[q] - alab[bi[:, None, None], r]).norm(dim=-1) > near * 1.8
        q = torch.where(far, anchor[bi[:, None, None], r], q)
        return lab2rgb(s.pal[q]), k

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-Device', '--device', default='gpu', choices=['gpu', 'cpu'])
    ap.add_argument('--config', default='train_image_config.json'); ap.add_argument('--out', default='models/cael-image-female-64-v7')
    ap.add_argument('--n', type=int, default=64); ap.add_argument('--max-images', type=int, default=0)
    ap.add_argument('--palette', type=int, default=256); ap.add_argument('--regions', type=int, default=14)
    ap.add_argument('--clusters', type=int, default=48); ap.add_argument('--min-cluster', type=int, default=12)
    ap.add_argument('--min-count', type=int, default=4); ap.add_argument('--sweeps', type=int, default=6)
    ap.add_argument('--smooth', type=int, default=3); ap.add_argument('--near', type=float, default=18.0)
    ap.add_argument('--text-weight', type=float, default=1.0); ap.add_argument('--no-face', action='store_true')
    ap.add_argument('--balance', type=float, default=0.0); ap.add_argument('--skeleton', type=float, default=0.7)
    ap.add_argument('--tex-sweeps', type=int, default=8); ap.add_argument('--tex-gain', type=float, default=1.0)
    ap.add_argument('--face-gain', type=float, default=1.0)
    a = ap.parse_args(); t0 = time.time(); dev = pick_device(a.device); print('device', dev)
    out = Path(a.out)
    if out.exists(): raise SystemExit(f'{out} exists; choose a new --out (existing models are never overwritten).')
    cfg = json.load(open(a.config, encoding='utf-8-sig')); root = Path(cfg['dataset_dir'])
    recs = discover(root, cfg['resize_mode']); tr, va = split_records(recs, cfg['validation_fraction'], cfg['seed'])
    if a.max_images: tr, va = tr[:a.max_images], va[:max(8, a.max_images // 8)]
    caps = [r['caption'] for r in tr]; df = Counter(w for c in caps for w in tokens(c)); vocab = [w for w, c in df.most_common() if c >= 5][:256]
    T = torch.from_numpy(np.stack([read_rgb(root / r['image'], cfg['resize_mode']) for r in tr])).to(dev)
    V = torch.from_numpy(np.stack([read_rgb(root / r['image'], cfg['resize_mode']) for r in va])).to(dev)
    m = CA7(dev, a.palette, a.regions, a.clusters, a.min_count, cfg['seed']); m.fit(T, caps, vocab, a.min_cluster)
    print(f'fitted {len(T)} images: {m.K} clusters (min size {min(m.sizes)}), skin region {m.skin}, in {time.time() - t0:.1f}s')
    prompts = [va[i % len(va)]['caption'] for i in range(a.n)]; Gs, Ks = [], []
    for i in range(0, a.n, 32):
        g, k = m.generate(prompts[i:i + 32], cfg['seed'] + i, a.sweeps, a.text_weight, a.smooth, a.near, not a.no_face,
                          balance=a.balance, skel=a.skeleton, tex_sweeps=a.tex_sweeps, tex_gain=a.tex_gain, face_gain=a.face_gain)
        Gs.append(g); Ks.append(k)
    G = torch.cat(Gs); Kc = torch.cat(Ks)
    Vq = lab2rgb(m.pal[m.quant(rgb2lab(V[:256].float()))]); g2 = torch.Generator(); g2.manual_seed(1)
    ab = lambda X: [round(float(v), 2) for v in rgb2lab(X.float()).reshape(-1, 3).mean(0)]
    rep = dict(device=str(dev), train_images=len(T), clusters=m.K, cluster_sizes=m.sizes, args=vars(a),
               clusters_used=len(set(Kc.tolist())), mean_lab_heldout=ab(V), mean_lab_v7=ab(G),
               heldout_quantized=stats(Vq, T, g2), v7=stats(G, T, g2))
    h, g = rep['heldout_quantized'], rep['v7']
    fe = float(np.mean([abs(x - y) / max(y, 1e-6) for x, y in zip(g['falloff'], h['falloff'])]))
    checks = dict(diversity=g['pairwise_L1'] >= 0.5 * h['pairwise_L1'],
                  edges=0.5 * h['edge_density'] <= g['edge_density'] <= 2 * h['edge_density'],
                  falloff=fe <= 0.25, no_copies=g['nn_to_train_min'] >= 0.5 * h['nn_to_train_median'],
                  cluster_variety=rep['clusters_used'] >= min(8, m.K), min_cluster_ok=min(m.sizes) >= min(a.min_cluster, len(T)))
    rep.update(falloff_rel_error=round(fe, 4), checks=checks, pass_=all(checks.values()), seconds=round(time.time() - t0, 1),
               pass_rule='v6 rule (diversity, edges, falloff<=0.25, no copies, cluster variety, min cluster size); fixed before the v7 run')
    out.mkdir(parents=True)
    from PIL import Image
    Gc = G.cpu().numpy(); n = int(np.sqrt(len(Gc)))
    for i in range(min(16, len(Gc))): Image.fromarray(Gc[i]).save(out / f'preview_{i:02d}.png')
    if n > 1: Image.fromarray(Gc[:n * n].reshape(n, n, 64, 64, 3).transpose(0, 2, 1, 3, 4).reshape(n * 64, n * 64, 3)).save(out / 'preview_grid.png')
    torch.save(dict(palette_lab=m.pal.cpu(), region_of_colour=m.reg.cpu(), region_hist=m.rh.int().cpu(), colour_hist=m.ch.int().cpu(),
                    shade=m.shade.cpu(), region_ca={L: v.int().cpu() for L, v in m.ca.items()}, prior=m.prior.cpu(), word=m.word.cpu(),
                    vocab=vocab, skin_region=m.skin, head_hists=dict(cy=m.hcy.cpu(), cx=m.hcx.cpu(), h=m.hh.cpu(), w=m.hw.cpu()),
                    hair=m.hair.cpu(), cloth=m.cloth.cpu(), bg=m.bg.cpu(), face=m.facec.cpu(), tex=m.tex.cpu(), amp=m.amp_r.cpu()), out / 'model_v7.pt')
    json.dump(rep, open(out / 'metrics.json', 'w'), indent=2); print(json.dumps(rep, indent=2)); print('PASS' if rep['pass_'] else 'FAIL')
    if dev.type == 'cuda': print(f'peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB')
    sys.stdout.flush(); import os; os._exit(0)  # ROCm runtime can hang at interpreter exit
if __name__ == '__main__': main()


