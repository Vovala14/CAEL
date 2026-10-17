"""Geometry and agreement checks for blind classical portrait alignment."""
import math


def mirror_pair(pair, width):
    """Reflect continuous OpenCV rectangle-centre coordinates and swap eyes."""
    left, right = pair
    return ((width - right[0], right[1]), (width - left[0], left[1]))


def plausible_pair(pair, face, minimum_span=8.):
    left, right = pair
    x, y, w, h = face[:4]
    dx, dy = right[0] - left[0], right[1] - left[1]
    cx, cy = (left[0] + right[0]) / 2, (left[1] + right[1]) / 2
    return (dx >= minimum_span and .25 * w <= dx <= .65 * w and
            abs(dy) <= .3 * dx and x + .3 * w <= cx <= x + .7 * w and
            y + .12 * h <= cy <= y + .60 * h)


def pair_agreement(a, b, tolerance=.12):
    span = max(1., (math.dist(a[0], a[1]) + math.dist(b[0], b[1])) / 2)
    return max(math.dist(a[0], b[0]), math.dist(a[1], b[1])) <= tolerance * span
