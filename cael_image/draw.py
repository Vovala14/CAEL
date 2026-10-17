"""Carry out a parsed picture request with the hybrid model, reporting anything that could not be honoured."""
import numpy as np

from .compose import place, recolour

STYLE_NAMES = {0: 'photo', 1: 'side view', 2: 'illustration'}


def donor_background(model, topic, donors):
    """The plain background colour of the donor renders (their border median)."""
    images = model.pyramid(topic)[model.size][donors]
    border = np.concatenate([images[:, 0], images[:, -1], images[:, :, 0], images[:, :, -1]], 1).reshape(-1, 3)
    return np.median(border, 0) * 255


def usable(mask):
    return mask is not None and 0.04 <= float((mask > 0.5).mean()) <= 0.85


def draw(model, request, n=2, seed=0, settings=None, clean_background=True):
    """request: output of request.parse. Returns (images uint8 n x S x S x 3, info dict).

    Objects come with masks synthesised from the clean training renders, so they can be
    recoloured, placed on scenes, or given a clean plain background instead of the patchy
    one that patch synthesis leaves behind.
    """
    settings = dict(settings or {})
    subject, count, colour = request['subject'], request['count'], request['colour']
    background = request['background']
    notes = list(request['notes'])
    style = request['style']
    if style is not None and not (model.styles(subject) == style).sum() >= 2:
        notes.append(f'I have no {STYLE_NAMES[style]} examples of {subject.replace("_", " ")}, so the style may differ.')
        style = None
    if background not in (None, 'plain') and background not in model.topics:
        notes.append(f'I cannot draw a {background} background yet, so I used a plain one.')
        background = 'plain'
    images, reports = [], []
    size = model.size
    for picture in range(n):
        objects, picture_reports, masks = model.generate(subject, n=count, seed=seed * 7 + picture * 101, style=style,
                                                         return_masks=True, **settings)
        picture_reports = [dict(r) for r in picture_reports]
        if not all(usable(m) for m in masks):
            if colour or count > 1 or background not in (None, 'plain'):
                notes.append(f'I could not separate the {subject.replace("_", " ")} from its surroundings, '
                             'so I could not change its colour, number or background.')
            images.append(objects[0])
            reports.append(picture_reports)
            continue
        if colour:
            objects = np.stack([recolour(obj, mask, colour) for obj, mask in zip(objects, masks)])
        if background in (None, 'plain'):
            if count == 1 and not clean_background and not colour:
                images.append(objects[0])
                reports.append(picture_reports)
                continue
            scene = np.tile(donor_background(model, subject, picture_reports[0]['donors']).astype(np.uint8), (size, size, 1))
        else:
            scene_images, scene_reports = model.generate(background, n=1, seed=seed * 13 + picture, **settings)
            scene = scene_images[0]
            picture_reports += [dict(r) for r in scene_reports]
        if count == 1 and background in (None, 'plain'):
            # Keep the object where and how big it was drawn; only the patchy background is replaced.
            a = masks[0][..., None]
            images.append(np.clip(objects[0] * a + scene * (1 - a), 0, 255).astype(np.uint8))
        else:
            images.append(place(scene, list(objects), masks))
        reports.append(picture_reports)
    applied = [f'{count} x' if count > 1 else None, colour, subject.replace('_', ' '),
               f'({STYLE_NAMES[style]})' if style is not None else None,
               f'on a {background} background' if background not in (None, 'plain') else None]
    info = dict(subject=' '.join(a for a in applied if a), request=request,
                notes=list(dict.fromkeys(notes)), sources=reports)
    return np.stack(images), info
