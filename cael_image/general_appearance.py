"""Subject-conditioned statistical image generator derived from portrait code.

The synthetic teacher is neural; this aggregate appearance sampler is not.
Only finite learned subject categories are supported, with no compositional
text encoder or claim of arbitrary text-to-image understanding.
"""
import re

from .portrait_appearance import sample_guarded_appearance
from .portrait_deformation import DeformationPrior


def resolve_subject(text, aliases, seed=0):
    lower = text.lower()
    if lower.strip() in aliases:
        return lower.strip()
    spans = []
    for subject, words in aliases.items():
        for word in words:
            spans.extend((match.start(), match.end(), subject) for match in re.finditer(r'\b' + re.escape(word) + r'\b', lower))
    # "computer" inside "computer mouse" is a nested alias, while "computer
    # mouse and dog" still contains two separately requested subjects.
    matches = {subject for start, end, subject in spans if not any(
        other_start <= start and end <= other_end and (other_start, other_end) != (start, end)
        for other_start, other_end, _ in spans)}
    if not matches and re.search(r'\b(person|people|portrait)\b', lower):
        return 'woman' if seed % 2 == 0 else 'man'
    if len(matches) != 1:
        raise ValueError('Choose one supported subject category' if matches else 'This subject is not in the trained image vocabulary')
    return next(iter(matches))


class GeneralAppearance:
    def __init__(self, checkpoint, fallback=None, enabled_subjects=None):
        if checkpoint['format'] not in ('cael-general-appearance-v1', 'cael-general-shape-ca-v2'):
            raise ValueError('Unsupported general-image model format')
        self.checkpoint = checkpoint
        self.fallback = fallback
        self.enabled_subjects = set(enabled_subjects) if enabled_subjects is not None else None
        self.shape_ca = None
        if checkpoint['format'] == 'cael-general-shape-ca-v2':
            from .general_shape_ca import GeneralShapeCA
            self.shape_ca = GeneralShapeCA(checkpoint)

    def generate(self, text, n=2, seed=42):
        if not 1 <= n <= 8:
            raise ValueError('Choose between 1 and 8 images')
        subject = resolve_subject(text, self.checkpoint['aliases'], seed)
        if self.shape_ca is not None:
            if self.fallback is not None and self.enabled_subjects is not None and subject not in self.enabled_subjects:
                return self.fallback.generate(text, n=n, seed=seed)
            return self.shape_ca.generate(text, n=n, seed=seed)
        settings = self.checkpoint['settings']
        prior = DeformationPrior(self.checkpoint['priors'][subject], warp_strength=settings['warp_strength'])
        # Include all fitting subjects in the guard; held-out images never enter it.
        images, checks = sample_guarded_appearance(prior, n, seed, self.checkpoint['guard_references'],
                                                  variation=settings['variation'], sharpen=settings['sharpen'],
                                                  threshold=settings['guard_threshold'])
        return images, dict(subject=subject, seed=seed, checks=checks,
                            limitation='64x64 single-subject statistics; colour, layout and style instructions are not learned controls')
