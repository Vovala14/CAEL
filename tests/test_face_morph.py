"""Landmark face morphing and eye finding (synthetic faces; no OpenCV needed at runtime)."""
import unittest

import numpy as np

from cael_image import faces
from cael_image.morph import anchor_points, morph, piecewise_warp


def synthetic_face(size=128, eye_y=52, gap=24, shade=0.8):
    """A light face disc with two dark eyes and a dark mouth on a grey background."""
    yy, xx = np.mgrid[:size, :size]
    img = np.full((size, size, 3), 0.4, np.float32)
    face = (xx - size / 2) ** 2 / 30 ** 2 + (yy - 60) ** 2 / 40 ** 2 < 1
    img[face] = shade
    for x in (size / 2 - gap / 2, size / 2 + gap / 2):
        img[(xx - x) ** 2 + (yy - eye_y) ** 2 < 9] = 0.1
    img[(np.abs(xx - size / 2) < 8) & (np.abs(yy - 80) < 2)] = 0.2
    return img


def landmarks_for(size=128, eye_y=52, gap=24):
    """68 plausible points: jaw arc, brows, nose, eyes, mouth (only their layout matters here)."""
    cx = size / 2
    jaw = [(cx + 30 * np.cos(a), 60 + 40 * np.sin(a)) for a in np.linspace(np.pi * 0.95, np.pi * 0.05, 17)]
    jaw = [(x, 120 - (y - 60)) if y < 60 else (x, y) for x, y in jaw]
    brows = [(cx - gap / 2 - 8 + 4 * i, eye_y - 8) for i in range(5)] + [(cx + gap / 2 - 8 + 4 * i, eye_y - 8) for i in range(5)]
    nose = [(cx, eye_y + 4 * i) for i in range(4)] + [(cx - 6 + 3 * i, eye_y + 16) for i in range(5)]
    eyes = [(cx - gap / 2 + 3 * np.cos(a), eye_y + 2 * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 7)[:6]] + \
           [(cx + gap / 2 + 3 * np.cos(a), eye_y + 2 * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 7)[:6]]
    mouth = [(cx + 8 * np.cos(a), 80 + 3 * np.sin(a)) for a in np.linspace(0, 2 * np.pi, 21)[:20]]
    return np.array(jaw + brows + nose + eyes + mouth, np.float32)


class FaceMorphTests(unittest.TestCase):
    def test_warp_with_identical_points_is_identity(self):
        img = synthetic_face()
        points = anchor_points(landmarks_for(), 128)
        out = piecewise_warp(img, points, points, None)
        self.assertLess(float(np.abs(out - img).mean()), 0.01)

    def test_morph_of_one_face_with_itself_is_that_face(self):
        img, marks = synthetic_face(), landmarks_for()
        out, target, ghost = morph([img, img, img], [marks, marks, marks], np.array([0.4, 0.3, 0.3]))
        self.assertLess(float(np.abs(out - img).mean()), 0.01)
        self.assertLess(ghost, 1e-4)

    def test_morph_lands_features_between_the_people(self):
        a, b = synthetic_face(eye_y=48), synthetic_face(eye_y=58)
        out, target, ghost = morph([a, b], [landmarks_for(eye_y=48), landmarks_for(eye_y=58)], np.array([0.5, 0.5]))
        eye_row = int(np.argmin(out[40:66, 52].mean(1))) + 40         # darkest row through the left eye
        self.assertTrue(50 <= eye_row <= 56, eye_row)                  # one eye, halfway, not two ghosts
        self.assertGreater(ghost, 0.0)

    def test_eye_finder_and_consensus(self):
        img = synthetic_face(size=128, eye_y=52)
        eyes = faces.find_eyes(img)
        self.assertIsNotNone(eyes)
        (lx, ly), (rx, ry) = eyes
        self.assertAlmostEqual((lx + rx) / 2, 64, delta=3)
        self.assertAlmostEqual(ly, 52, delta=3)
        kept, canonical = faces.consensus({i: eyes for i in range(5)}, 128)
        self.assertEqual(len(kept), 5)


if __name__ == '__main__':
    unittest.main()
