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

    def test_best_of_and_alignment_are_reproducible(self):
        for options in (dict(best_of=4), dict(align=True), dict(best_of=3, align=True, min_distance=5.0)):
            first, _ = self.model.generate('red_box', n=2, seed=9, donors=2, detail=True, **options)
            again, _ = self.model.generate('red_box', n=2, seed=9, donors=2, detail=True, **options)
            self.assertEqual(first.shape, (2, 64, 64, 3))
            self.assertTrue(np.array_equal(first, again), options)

    def test_silhouette_alignment_moves_and_mirrors_onto_the_anchor(self):
        from cael_image.hybrid import silhouette_transform, warp
        anchor = np.zeros((64, 64), np.float32)
        anchor[20:44, 8:24] = 1                       # tall box on the left
        other = np.zeros((64, 64), np.float32)
        other[26:38, 46:54] = 1                       # smaller box on the right
        moved = warp(other[..., None], silhouette_transform(anchor, other), (0.0,))[..., 0]
        overlap = np.minimum(moved, anchor).sum() / np.maximum(moved, anchor).sum()
        self.assertGreater(overlap, 0.5)

    def test_packed_model_draws_with_its_detail_images(self):
        from cael_image.hybrid import pack
        from PIL import Image
        big = {t: np.stack([np.asarray(Image.fromarray(im).resize((128, 128), Image.Resampling.LANCZOS)) for im in v])
               for t, v in self.data.items()}
        path = Path(self.folder.name) / 'packed.npz'
        pack(Path(self.folder.name) / 'model.npz', lambda t: big[t], path)
        packed = HybridModel(path)
        try:
            self.assertTrue(packed.has_detail)
            self.assertEqual(packed.images('red_box').shape, self.data['red_box'].shape)
            images, _ = packed.generate('red_box', n=2, seed=4, donors=2, detail=True, best_of=3, hires=True)
            self.assertEqual(images.shape, (2, 64, 64, 3))
            red = images[..., 0].astype(int) - images[..., 2].astype(int)
            self.assertGreater(red.max(), 100)
        finally:
            packed.data.close()


if __name__ == '__main__':
    unittest.main()
