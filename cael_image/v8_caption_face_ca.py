"""CAEL image v8: caption attributes + per-image colour roles + aligned face parts on the v7 part/region CA.
No neural nets. Additions over v7:
 1. Caption attributes: colour words before clothing nouns / 'hair', and pose words. Each attribute keeps a
    count-averaged Lab target for its role (e.g. 'red dress' -> clothes colour). Generation snaps that role's anchor
    to the nearest palette colour of the target (+ small jitter). Cluster choice uses caption words (stronger weight).
 2. Colour balance: per training image, the skin / hair / clothes / background ROLE colours are measured on that image
    (mean Lab inside its own head box, hair ring, body area, border) and counted into per-role palette histograms.
    Each sample draws its role colours from these (independently per role, never one image's tuple), replacing v6/v7
    region anchors that mixed many images and drifted pink.
 3. Aligned face parts: head crops are aligned to their head boxes and resampled to 16x16; count-averaged darkness
    gives a canonical face; eye and mouth positions are its darkest points in the eye / mouth bands (fallback: standard
    proportions). Generation stamps dark eye and mouth seeds into the head ellipse and grows them with a small CA
    (dark cell spreads to a neighbour with learned probability), then a mode filter. Face skin texture is damped.
Torch is only a tensor engine ('cuda' via ROCm, or CPU)."""
import argparse, json, re, sys, time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.data import discover, split_records, read_rgb
from cael_image.model import tokens
from cael_image.v4_multiscale_ca import pick_device, stats, shifts
from cael_image.v6_region_ca import rgb2lab, lab2rgb, mode3, nb_key
from cael_image.v7_part_ca import CA7, tern_key

COLOURS = ['black', 'white', 'red', 'pink', 'blue', 'green', 'purple', 'yellow', 'orange', 'brown', 'grey', 'gray',
           'blonde', 'silver', 'gold', 'beige', 'navy', 'teal', 'tan', 'cream']
CLOTHES = ['dress', 'shirt', 'top', 'skirt', 'jacket', 'coat', 'sweater', 'bikini', 'swimsuit', 'outfit', 'suit', 'jeans',
           'pants', 'shorts', 'lingerie', 'robe', 'blouse', 'hoodie', 'gown', 'bra', 'clothes', 'uniform']
POSES = ['sitting', 'standing', 'laying', 'lying', 'kneeling', 'posing', 'leaning']

NAMED = dict(black=(15, 0, 0), white=(93, 0, 2), red=(45, 62, 40), pink=(70, 38, 2), blue=(40, 15, -50), green=(48, -40, 30),
             purple=(38, 40, -38), yellow=(88, -5, 75), orange=(65, 40, 65), brown=(35, 15, 25), grey=(55, 0, 0), blonde=(80, 2, 35),
             silver=(75, 0, -2), gold=(72, 5, 60), beige=(82, 3, 15), navy=(22, 10, -35), teal=(50, -30, -8), tan=(65, 10, 28), cream=(90, 0, 12))

def attributes(caption):
    w = re.findall(r"[a-z]+", caption.lower()); out = dict(cloth=None, hair=None, pose=None)
    for i, t in enumerate(w):
        if t in POSES and out['pose'] is None: out['pose'] = 'laying' if t == 'lying' else t
        if t in COLOURS:
            nxt = w[i + 1:i + 4]
            if 'hair' in nxt[:2] or t == 'blonde': out['hair'] = out['hair'] or t
            elif any(n in CLOTHES for n in nxt) and out['cloth'] is None: out['cloth'] = 'grey' if t == 'gray' else t
    return out

class CA8(CA7):
    def fit(s, T, caps, vocab, min_cluster):
        a = super().fit(T, caps, vocab, min_cluster); gdev = s.dev; B = len(T); P = s.P
        lab = rgb2lab(T.float()).cpu(); pal = s.pal.cpu(); reg = s.reg.cpu(); q = s.quant(rgb2lab(T.float())).cpu(); r64 = reg[q]
        quant = lambda v: int(torch.cdist(v[None], pal).argmin())
        s.role = {n: torch.ones(P) * 0.01 for n in ('skin', 'hair', 'cloth', 'bg')}
        s.attr = {}; crops = []; amask = torch.zeros(B, dtype=torch.bool)
        for i in range(B):
            L = lab[i]; r = r64[i]; m = (r == s.skin); m[38:] = False
            border = torch.cat([L[0], L[-1], L[:, 0], L[:, -1]]); bg = border.mean(0); s.role['bg'][quant(bg)] += 1
            at = attributes(caps[i]); roles = {}
            if m.sum() >= 24:
                ys, xs = m.nonzero(as_tuple=True); y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
                skin = L[m].mean(0); roles['skin'] = skin; s.role['skin'][quant(skin)] += 1
                ring = L[max(0, y0 - 6):y0 + (y1 - y0) // 3, max(0, x0 - 4):x1 + 5].reshape(-1, 3)
                ring = ring[(ring - skin).norm(dim=-1) > 18]; ring = ring[(ring - bg).norm(dim=-1) > 12]
                if len(ring) >= 8: roles['hair'] = ring.mean(0); s.role['hair'][quant(roles['hair'])] += 1
                cx, w = (x0 + x1) // 2, x1 - x0 + 1
                body = L[min(63, y1 + 3):, max(0, cx - w):cx + w + 1].reshape(-1, 3)
                body = body[(body - skin).norm(dim=-1) > 18]; body = body[(body - bg).norm(dim=-1) > 12]
                if len(body) >= 16: roles['cloth'] = body.mean(0); s.role['cloth'][quant(roles['cloth'])] += 1
                if y1 - y0 >= 7 and x1 - x0 >= 6:
                    c = F.interpolate(L[y0:y1 + 1, x0:x1 + 1, 0][None, None], size=(16, 16), mode='bilinear', align_corners=False)[0, 0]
                    crops.append(c - c.mean())
            for role, key in (('cloth', 'cloth'), ('hair', 'hair')):
                if at[key] and role in roles:
                    acc = s.attr.setdefault(role + ':' + at[key], [torch.zeros(3), 0]); acc[0] += roles[role]; acc[1] += 1
        s.attr = {k: (v[0] / v[1]).to(gdev) for k, v in s.attr.items() if v[1] >= 3}
        s.attr_counts = {}
        # canonical aligned face and eye / mouth positions
        s.eyes, s.mouth = [(6, 4), (6, 11)], (12, 8); s.face_ok = False
        if len(crops) >= 10:
            canon = torch.stack(crops).mean(0); s.canon = canon
            band = canon[4:9, 2:7]; ly, lx = divmod(int(band.argmin()), 5)
            band2 = canon[4:9, 9:14]; ry_, rx_ = divmod(int(band2.argmin()), 5)
            mb = canon[10:14, 5:11]; my, mx = divmod(int(mb.argmin()), 6)
            contrast = float(canon[4:14, 2:14].mean() - min(band.min(), band2.min()))
            e1, e2, mo = (4 + ly, 2 + lx), (4 + ry_, 9 + rx_), (10 + my, 5 + mx)
            sane = (e2[1] - e1[1] >= 5) and (mo[0] - max(e1[0], e2[0]) >= 3) and (e1[1] < mo[1] < e2[1]) and abs(e1[0] - e2[0]) <= 1
            if contrast > 1.0 and sane: s.eyes, s.mouth, s.face_ok = [e1, e2], mo, True
            s.face_learned_raw = [e1, e2, mo]
            s.face_contrast = round(contrast, 2)
        else:
            s.canon = torch.zeros(16, 16); s.face_contrast = 0.0; s.face_learned_raw = None
        for n in s.role: s.role[n] = s.role[n].to(gdev)
        # colour calibration: measure mean a*/b* of a 32-sample generation batch vs training, store as fixed offset
        s.ab_shift = torch.zeros(2, device=gdev)
        g = torch.cat([s.generate(caps[j::max(1, len(caps) // 64)][:32], seed=12345 + j)[0] for j in (0, 1)])
        s.ab_shift = (rgb2lab(T.float()).reshape(-1, 3).mean(0) - rgb2lab(g.float()).reshape(-1, 3).mean(0))[1:]
        return a
    def generate(s, prompts, seed, sweeps=6, text_weight=2.0, smooth=3, near=18.0, face=True, beta=1.0,
                 balance=0.0, skel=0.7, tex_sweeps=8, tex_gain=1.0, face_gain=1.0, jitter=4.0):
        dev = s.dev; gen = torch.Generator(device=dev); gen.manual_seed(seed); B = len(prompts); R = s.R
        draw = lambda p: torch.multinomial((p / p.sum(-1, keepdim=True)).reshape(-1, p.shape[-1]), 1, generator=gen).reshape(p.shape[:-1])
        ks = []
        for pr in prompts:
            sc = balance * torch.log(s.prior + 1); ids = [s.wi[w] for w in tokens(pr or '') if w in s.wi]
            if ids: sc = sc + text_weight * (torch.log(s.word[ids] + 1) - torch.log(s.prior + 1)).mean(0)
            ks.append(torch.multinomial(torch.softmax(sc, 0), 1, generator=gen))
        k = torch.cat(ks); bi = torch.arange(B, device=dev)
        cy, cx, hh, hw = (draw(getattr(s, n)[k] + 0.2) for n in ('hcy', 'hcx', 'hh', 'hw'))
        hh = hh.clamp(6, 20); hw = hw.clamp(6, 20); cy = torch.maximum(cy, hh // 2 + 2).clamp(4, 22); cx = cx.clamp(7, 24)
        # regions: background / hair / clothes ids exactly as v7; colours come from roles below
        bgr = draw(s.bg[k] + 0.01)
        hair_p = s.hair[k] + 0.01; hair_p[bi, s.skin] = 0; hair_p[bi, bgr] *= 0.05; hair = draw(hair_p)
        clo_p = s.cloth[k] + 0.01; clo_p[bi, s.skin] = 0; clo_p[bi, hair] *= 0.2; clo = draw(clo_p)
        yy, xx = torch.meshgrid(torch.arange(32, device=dev).float(), torch.arange(32, device=dev).float(), indexing='ij')
        yy, xx = yy[None], xx[None]; cyf, cxf = cy[:, None, None].float(), cx[:, None, None].float()
        ry, rx = hh[:, None, None].float() / 2, hw[:, None, None].float() / 2
        head = ((yy - cyf) / ry) ** 2 + ((xx - cxf) / rx) ** 2 <= 1
        hairm = (((yy - cyf + ry * 0.35) / (ry * 1.35)) ** 2 + ((xx - cxf) / (rx * 1.3)) ** 2 <= 1) & ~head & (yy <= cyf + ry * 0.6)
        top = cyf + ry * 0.9; torso = (yy >= top) & ((xx - cxf).abs() <= rx * (0.9 + 0.08 * (yy - top)))
        part = torch.where(torso, clo[:, None, None], bgr[:, None, None]); part = torch.where(hairm, hair[:, None, None], part)
        part = torch.where(head, torch.full_like(part, s.skin), part)
        tm = (s.rh[k] + 0.01).reshape(B, 32, 32, R); tm = tm / tm.sum(-1, keepdim=True)
        tmpl = skel * F.one_hot(part, R).float() + (1 - skel) * tm
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
        # ---- per-sample role colours (per-image role histograms + caption attributes)
        anchor = draw(s.ch[k] + 1e-6); alab = s.pal[anchor].clone()          # other regions: v6 anchors
        role_lab = {}
        for name in ('skin', 'hair', 'cloth', 'bg'):
            role_lab[name] = s.pal[draw(s.role[name].expand(B, -1))].clone()
        for b, pr in enumerate(prompts):
            at = attributes(pr or '')
            for role in ('cloth', 'hair'):
                key = f'{role}:{at[role]}' if at[role] else None
                if key in s.attr:
                    tgt = 0.7 * torch.tensor(NAMED[at[role]], device=dev, dtype=torch.float32) + 0.3 * s.attr[key] if at[role] in NAMED else s.attr[key]
                    role_lab[role][b] = tgt + torch.randn(3, device=dev, generator=gen) * jitter
        alab[bi, bgr] = role_lab['bg']; alab[bi, hair] = role_lab['hair']; alab[bi, clo] = role_lab['cloth']
        alab[bi, s.skin] = role_lab['skin']
        alab[..., 1:] = alab[..., 1:] + getattr(s, 'ab_shift', torch.zeros(2, device=dev))
        lab = alab[bi[:, None, None], r].clone()
        rel = up(s.shade[k].reshape(B, 32, 32)).clamp(-15, 15)
        lab[..., 0] = lab[..., 0] + rel * 0.6
        # ---- texture CA (damped on skin)
        t = draw(torch.ones(B, 64, 64, 3, device=dev))
        chk = ((torch.arange(64, device=dev)[:, None] + torch.arange(64, device=dev)[None]) % 2)[None]
        for it in range(tex_sweeps * 2):
            t = torch.where(chk == it % 2, draw(s.tex[r, tern_key(t)]), t)
        g = torch.where(r == s.skin, 0.25, 1.0)
        lab[..., 0] = lab[..., 0] + (t.float() - 1) * s.amp_r[r] * 1.6 * tex_gain * g
        # ---- aligned face parts: eye / mouth seeds grown by a small CA inside the head ellipse
        if face:
            Y, X = torch.meshgrid(torch.arange(64, device=dev).float(), torch.arange(64, device=dev).float(), indexing='ij')
            fy = (Y[None] / 2 - (cyf - ry)) / (2 * ry) * 16; fx = (X[None] / 2 - (cxf - rx)) / (2 * rx) * 16
            inhead = (fy >= 0) & (fy < 16) & (fx >= 0) & (fx < 16) & up(head)
            seed = torch.zeros(B, 64, 64, dtype=torch.bool, device=dev)
            for (ey, ex) in s.eyes:
                seed |= inhead & ((fy - ey - 0.5).abs() < 0.9) & ((fx - ex - 0.5).abs() < 1.0)
            my, mx = s.mouth; mouth = inhead & ((fy - my - 0.5).abs() < 0.7) & ((fx - mx - 0.5).abs() < 2.0)
            # growth CA: a dark cell turns a 4-neighbour dark with p=0.15 for 1 step (soft blobs, not squares)
            nbd = torch.stack([v for o, v in shifts(seed.long()).items() if abs(o[0]) + abs(o[1]) == 1], -1).sum(-1)
            grow = (nbd > 0) & inhead & (torch.rand(seed.shape, device=dev, generator=gen) < 0.15)
            eyes = seed | grow
            lab[..., 0] = torch.where(eyes, torch.full_like(lab[..., 0], 18.0), lab[..., 0])
            lab[..., 1:] = torch.where(eyes[..., None], lab[..., 1:] * 0.3, lab[..., 1:])
            ml = role_lab['skin'][:, None, None, :].expand_as(lab).clone(); ml[..., 0] -= 28 * face_gain; ml[..., 1] += 10
            lab = torch.where(mouth[..., None], ml, lab)
        q = s.quant(lab); far = (s.pal[q] - alab[bi[:, None, None], r]).norm(dim=-1) > near * 1.8
        if face: far &= ~(eyes | mouth)
        q = torch.where(far, s.quant(alab[bi[:, None, None], r]), q)
        return lab2rgb(s.pal[q]), k

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-Device', '--device', default='gpu', choices=['gpu', 'cpu'])
    ap.add_argument('--config', default='train_image_config.json'); ap.add_argument('--out', default='models/cael-image-female-64-v8')
    ap.add_argument('--n', type=int, default=64); ap.add_argument('--max-images', type=int, default=0)
    ap.add_argument('--palette', type=int, default=256); ap.add_argument('--regions', type=int, default=14)
    ap.add_argument('--clusters', type=int, default=64); ap.add_argument('--min-cluster', type=int, default=12)
    ap.add_argument('--min-count', type=int, default=4); ap.add_argument('--sweeps', type=int, default=6)
    ap.add_argument('--smooth', type=int, default=3); ap.add_argument('--near', type=float, default=18.0)
    ap.add_argument('--text-weight', type=float, default=1.0); ap.add_argument('--no-face', action='store_true')
    ap.add_argument('--balance', type=float, default=0.0); ap.add_argument('--skeleton', type=float, default=0.7)
    ap.add_argument('--tex-sweeps', type=int, default=8); ap.add_argument('--tex-gain', type=float, default=1.0)
    ap.add_argument('--face-gain', type=float, default=1.0)
    a = ap.parse_args(); t0 = time.time(); dev = pick_device(a.device); print('device', dev, flush=True)
    out = Path(a.out)
    if out.exists(): raise SystemExit(f'{out} exists; choose a new --out (existing models are never overwritten).')
    cfg = json.load(open(a.config, encoding='utf-8-sig')); root = Path(cfg['dataset_dir'])
    recs = discover(root, cfg['resize_mode']); tr, va = split_records(recs, cfg['validation_fraction'], cfg['seed'])
    if a.max_images: tr, va = tr[:a.max_images], va[:max(8, a.max_images // 8)]
    caps = [r['caption'] for r in tr]; df = Counter(w for c in caps for w in tokens(c)); vocab = [w for w, c in df.most_common() if c >= 5][:256]
    T = torch.from_numpy(np.stack([read_rgb(root / r['image'], cfg['resize_mode']) for r in tr])).to(dev)
    V = torch.from_numpy(np.stack([read_rgb(root / r['image'], cfg['resize_mode']) for r in va])).to(dev)
    print(f'loaded {len(T)} train / {len(V)} held-out images in {time.time() - t0:.1f}s', flush=True)
    m = CA8(dev, a.palette, a.regions, a.clusters, a.min_count, cfg['seed']); m.fit(T, caps, vocab, a.min_cluster)
    print(f'fitted: {m.K} clusters (min size {min(m.sizes)}), attributes {len(m.attr)}, face contrast {m.face_contrast}, '
          f'eyes {m.eyes} mouth {m.mouth} learned={m.face_ok}, {time.time() - t0:.1f}s', flush=True)
    prompts = [va[i % len(va)]['caption'] for i in range(a.n)]; Gs, Ks = [], []
    for i in range(0, a.n, 32):
        g, k = m.generate(prompts[i:i + 32], cfg['seed'] + i, a.sweeps, a.text_weight, a.smooth, a.near, not a.no_face,
                          balance=a.balance, skel=a.skeleton, tex_sweeps=a.tex_sweeps, tex_gain=a.tex_gain, face_gain=a.face_gain)
        Gs.append(g); Ks.append(k)
    G = torch.cat(Gs); Kc = torch.cat(Ks)
    Vq = lab2rgb(m.pal[m.quant(rgb2lab(V[:256].float()))]); g2 = torch.Generator(); g2.manual_seed(1)
    ab = lambda X: [round(float(v), 2) for v in rgb2lab(X.float()).reshape(-1, 3).mean(0)]
    # caption-following check: for prompts naming a clothing colour, is the generated torso area closer to that
    # attribute's colour than to the average of other attributes' colours?
    hits = tot = 0
    for i, p in enumerate(prompts):
        c = attributes(p)['cloth']
        if c and f'cloth:{c}' in m.attr and len(m.attr) > 1:
            body = rgb2lab(G[i, 44:60, 20:44].float()).reshape(-1, 3).mean(0)
            d = {kk: float((body - v).norm()) for kk, v in m.attr.items() if kk.startswith('cloth:')}
            tot += 1; hits += int(min(d, key=d.get) == f'cloth:{c}')
    rep = dict(device=str(dev), train_images=len(T), clusters=m.K, cluster_sizes=m.sizes, args=vars(a),
               attributes={kk: [round(float(x), 1) for x in v] for kk, v in m.attr.items()},
               face=dict(raw_learned=m.face_learned_raw, ab_calibration=[round(float(x), 2) for x in m.ab_shift], learned=m.face_ok, contrast=m.face_contrast, eyes=m.eyes, mouth=m.mouth),
               caption_colour_hits=f'{hits}/{tot}', clusters_used=len(set(Kc.tolist())),
               mean_lab_heldout=ab(V), mean_lab_v8=ab(G), heldout_quantized=stats(Vq, T, g2), v8=stats(G, T, g2))
    h, g = rep['heldout_quantized'], rep['v8']
    fe = float(np.mean([abs(x - y) / max(y, 1e-6) for x, y in zip(g['falloff'], h['falloff'])]))
    da = abs(rep['mean_lab_v8'][1] - rep['mean_lab_heldout'][1]); db = abs(rep['mean_lab_v8'][2] - rep['mean_lab_heldout'][2])
    checks = dict(diversity=g['pairwise_L1'] >= 0.5 * h['pairwise_L1'],
                  edges=0.5 * h['edge_density'] <= g['edge_density'] <= 2 * h['edge_density'],
                  falloff=fe <= 0.25, no_copies=g['nn_to_train_min'] >= 0.5 * h['nn_to_train_median'],
                  cluster_variety=rep['clusters_used'] >= min(8, m.K), min_cluster_ok=min(m.sizes) >= min(a.min_cluster, len(T)),
                  colour_balance=da <= 4.0 and db <= 4.0,
                  caption_colour=(tot == 0) or hits >= 0.5 * tot)
    rep.update(falloff_rel_error=round(fe, 4), colour_shift_ab=[round(da, 2), round(db, 2)], checks=checks,
               pass_=all(checks.values()), seconds=round(time.time() - t0, 1),
               pass_rule='v7 rule + mean a*/b* within 4 of held-out + >=50% of clothing-colour prompts closest to their colour; fixed before the v8 run')
    out.mkdir(parents=True)
    from PIL import Image
    Gc = G.cpu().numpy(); n = int(np.sqrt(len(Gc)))
    for i in range(min(16, len(Gc))): Image.fromarray(Gc[i]).save(out / f'preview_{i:02d}.png')
    if n > 1: Image.fromarray(Gc[:n * n].reshape(n, n, 64, 64, 3).transpose(0, 2, 1, 3, 4).reshape(n * 64, n * 64, 3)).save(out / 'preview_grid.png')
    (out / 'preview_prompts.json').write_text(json.dumps(prompts[:n * n], indent=1), encoding='utf-8')
    torch.save(dict(palette_lab=m.pal.cpu(), region_of_colour=m.reg.cpu(), region_hist=m.rh.int().cpu(), shade=m.shade.cpu(),
                    region_ca={L: v.int().cpu() for L, v in m.ca.items()}, prior=m.prior.cpu(), word=m.word.cpu(), vocab=vocab,
                    skin_region=m.skin, roles={kk: v.cpu() for kk, v in m.role.items()}, attributes={kk: v.cpu() for kk, v in m.attr.items()},
                    face_canon=m.canon.cpu(), eyes=m.eyes, mouth=m.mouth, tex=m.tex.cpu(), amp=m.amp_r.cpu(),
                    head_hists=dict(cy=m.hcy.cpu(), cx=m.hcx.cpu(), h=m.hh.cpu(), w=m.hw.cpu()), hair=m.hair.cpu(), cloth=m.cloth.cpu(), bg=m.bg.cpu()),
               out / 'model_v8.pt')
    json.dump(rep, open(out / 'metrics.json', 'w'), indent=2); print(json.dumps(rep, indent=2)); print('PASS' if rep['pass_'] else 'FAIL')
    if dev.type == 'cuda': print(f'peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB')
    sys.stdout.flush(); import os; os._exit(0)
if __name__ == '__main__': main()



