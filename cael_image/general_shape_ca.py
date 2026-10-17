"""Grouped statistical shape generator with integer-count latent/detail CAs."""
import torch

from .general_appearance import resolve_subject
from .general_detail_ca import DetailCA
from .portrait_appearance import continuous_render
from .portrait_deformation import DeformationPrior
from .v4_multiscale_ca import nn as nearest


class GeneralShapeCA:
    def __init__(self, checkpoint):
        if checkpoint.get('format') != 'cael-general-shape-ca-v2':
            raise ValueError('Unsupported shape CA format')
        self.checkpoint = checkpoint

    def generate(self, text, n=2, seed=42):
        if not 1 <= n <= 8:
            raise ValueError('Choose between 1 and 8 images')
        subject = resolve_subject(text, self.checkpoint['aliases'], seed)
        settings = {**self.checkpoint['settings'], **self.checkpoint.get('subject_settings', {}).get(subject, {})}
        prior = DeformationPrior(self.checkpoint['priors'][subject], warp_strength=settings['warp_strength'], latent_ca=settings.get('latent_ca', True),
                                 latent_joint_seed=settings.get('joint_seed', False), safe_warp=True)
        detail = DetailCA(self.checkpoint['detail_ca'][subject])
        references = self.checkpoint['guard_references']

        def draw(count, draw_seed):
            field, populations = prior.sample(count, draw_seed, variation=settings['variation'])
            field = detail.apply(field, draw_seed + 271, strength=settings['detail_strength'])
            return continuous_render(field, settings['sharpen']), populations

        images, groups = draw(n, seed)
        distances = nearest(images, references)
        replacements = 0
        for attempt in range(8):
            bad = (distances < settings['guard_threshold']).nonzero().flatten()
            if not len(bad):
                break
            sampled, populations = draw(len(bad), seed + 7919 * (attempt + 1))
            images[bad], groups[bad] = sampled, populations
            distances[bad] = nearest(sampled, references)
            replacements += len(bad)
        if bool((distances < settings['guard_threshold']).any()):
            raise RuntimeError('The synthetic-reference similarity guard exhausted its retries')
        return images, dict(subject=subject, seed=seed, populations=groups.tolist(),
                            checks=dict(replacements=replacements, nearest_RMS=[round(float(value), 6) for value in distances]),
                            limitation=f'{self.checkpoint.get("image_size", 128)}x{self.checkpoint.get("image_size", 128)} finite subject categories; grouped statistical shapes with '
                                       + ('a learned count-based factor cellular automaton' if settings.get('latent_ca', True) else 'continuous Gaussian factor sampling')
                                       + '. Non-neural student; arbitrary prompt attributes are not learned controls.')
