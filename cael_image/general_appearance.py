"""Subject-conditioned statistical image generator derived from portrait code.

The synthetic teacher is neural; this aggregate appearance sampler is not.
Only finite learned subject categories are supported, with no compositional
text encoder or claim of arbitrary text-to-image understanding.
"""
import re

from .portrait_appearance import sample_guarded_appearance
from .portrait_deformation import DeformationPrior


def resolve_subject(text, aliases, seed=0):
    matches = set()
    lower = text.lower()
    for subject, words in aliases.items():
        for word in words:
            if re.search(r'\b' + re.escape(word) + r'\b', lower):
                matches.add(subject)
                break
    if not matches and re.search(r'\b(person|people|portrait)\b', lower):
        return 'woman' if seed % 2 == 0 else 'man'
    if len(matches) != 1:
        raise ValueError('Choose one supported subject category' if matches else 'This subject is not in the trained image vocabulary')
    return next(iter(matches))


class GeneralAppearance:
    def __init__(self, checkpoint):
        if checkpoint['format'] != 'cael-general-appearance-v1':
            raise ValueError('Unsupported general-image model format')
        self.checkpoint = checkpoint

    def generate(self, text, n=2, seed=42):
        if not 1 <= n <= 8:
            raise ValueError('Choose between 1 and 8 images')
        subject = resolve_subject(text, self.checkpoint['aliases'], seed)
        settings = self.checkpoint['settings']
        prior = DeformationPrior(self.checkpoint['priors'][subject], warp_strength=settings['warp_strength'])
        # Include all fitting subjects in the guard; held-out images never enter it.
        images, checks = sample_guarded_appearance(prior, n, seed, self.checkpoint['guard_references'],
                                                  variation=settings['variation'], sharpen=settings['sharpen'],
                                                  threshold=settings['guard_threshold'])
        return images, dict(subject=subject, seed=seed, checks=checks,
                            limitation='64x64 single-subject statistics; colour, layout and style instructions are not learned controls')
