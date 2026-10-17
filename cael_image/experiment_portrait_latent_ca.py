"""Last bounded experiment: count-trained joint appearance-factor constraints."""
import json
from pathlib import Path
import sys

import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_image.portrait_structure import load_guard_references
from cael_image.portrait_appearance import load_eye_aligned, sample_guarded_appearance
from cael_image.portrait_deformation import DeformationPrior
from cael_assistant.eval_portrait_sampling import diagnostics, save_grid


def main():
    torch.set_num_threads(4)
    out = Path('research/portrait_latent_ca_v16_a')
    out.mkdir(parents=True, exist_ok=False)
    protocol = dict(seed=644016, samples=16, threshold=.12, variance=.85, sharpen=.3,
                    variants=['registered_gaussian', 'registered_latent_ca'],
                    stop_rule='Keep prior version and stop if the factor CA gives no clear visible improvement',
                    source_photos_displayed=False, heldout_excluded=True)
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    eye_state = torch.load('research/portrait_appearance_v14_a/appearance.pt', weights_only=True)
    train = load_eye_aligned(eye_state['alignment'])
    old = torch.load('models/cael-portrait-64-v13-structure/model_v13.pt', weights_only=True)
    references = torch.cat([load_guard_references(old['source_guard']), train])
    del old
    print('Fitting aggregate appearance-factor count rules', flush=True)
    fitted = DeformationPrior.fit(train, eye_state['rank8']['means'])
    torch.save(dict(prior=fitted.state, alignment=eye_state['alignment']), out / 'latent_ca.pt')
    report = dict(protocol=protocol, variants={})
    for name in protocol['variants']:
        prior = DeformationPrior(fitted.state, warp_strength=.6, latent_ca=name.endswith('latent_ca'))
        outputs, checks = [], []
        for i in range(0, 16, 4):
            G, check = sample_guarded_appearance(prior, 4, protocol['seed'] + i, references, sharpen=.3)
            outputs.append(G)
            checks.append(check)
        G = torch.cat(outputs)
        row = diagnostics(G)
        row.update(guard_checks=checks)
        report['variants'][name] = row
        save_grid(G, out / f'{name}.png', columns=4)
        for i, pixels in enumerate(G.numpy()):
            Image.fromarray(pixels).save(out / f'{name}_{i:02d}.png')
        (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(name, json.dumps(row), flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
