import tempfile
import unittest
from pathlib import Path

import numpy as np

from cael_image.hybrid import HybridModel, fit


def toy_topic(seed, colour, count=8, size=64):
    """Squares of one colour at slightly different places on a light background, with fine texture."""
    rng = np.random.default_rng(seed)
    images = np.full((count, size, size, 3), 230, np.uint8)
    for i in range(count):
        y, x = rng.integers(12, 28, 2)
        images[i, y:y + 24, x:x + 24] = colour
        images[i, y:y + 24:2, x:x + 24] = (np.array(colour) * 0.6).astype(np.uint8)   # stripes = sharp detail
    return images


class HybridImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.data = {'red_box': toy_topic(1, (200, 30, 30)), 'blue_box': toy_topic(2, (30, 30, 200))}
        path = Path(cls.folder.name) / 'model.npz'
        np.savez(path, **fit(cls.data, {'red_box': ['red box'], 'blue_box': ['blue box']}))
        cls.model = HybridModel(path)

    @classmethod
    def tearDownClass(cls):
        cls.model.data.close()
        cls.folder.cleanup()

    def test_generates_the_requested_topic_reproducibly(self):
        images, reports = self.model.generate('red_box', n=2, seed=5, donors=4, detail=True)
        self.assertEqual(images.shape, (2, 64, 64, 3))
        again, _ = self.model.generate('red_box', n=2, seed=5, donors=4, detail=True)
        self.assertTrue(np.array_equal(images, again))
        red = images[..., 0].astype(int) - images[..., 2].astype(int)
        self.assertGreater(red.max(), 100, 'a red topic should produce red regions')

    def test_outputs_mix_sources_and_are_not_copies(self):
        images, reports = self.model.generate('blue_box', n=3, seed=1, donors=4, detail=True)
        for image, report in zip(images, reports):
            self.assertGreaterEqual(report['sources_used'], 2)
            self.assertLess(report['largest_source_share'], 0.95)
            distance = np.sqrt(((self.data['blue_box'].astype(float) - image.astype(float)) ** 2).mean((1, 2, 3))).min()
            self.assertGreater(distance, 1.0, 'an output must not be an exact training image')

    def test_unknown_topic_is_rejected(self):
        with self.assertRaises(ValueError):
            self.model.generate('dragon', n=1)


if __name__ == '__main__':
    unittest.main()
