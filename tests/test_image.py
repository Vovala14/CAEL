"""Synthetic software fixtures only; no female-character model is trained."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from cael_image.model import ImageCA, Counts, SIZE, COLORS, palette, quantize

try:
    from PIL import Image
except ImportError:
    Image = None

ROOT = Path(__file__).resolve().parents[1]


def fixture_model():
    """Analytic integer rules, not fitted images or a usable character checkpoint."""
    settings = dict(spatial_weight=1, text_weight=1, neighbor_weight=1, steps=2, noise=0)
    meta = dict(format='cael-integer-image-v1', size=64, colors=256, bins=1,
                vocabulary=['red', 'blue'], neural_parameters=0, settings=settings)
    conditional = np.zeros((2, 1, COLORS), np.int16)
    conditional[0, 0, 224] = 1000
    conditional[1, 0, 3] = 1000
    return ImageCA(meta, dict(spatial=np.zeros((SIZE, SIZE, COLORS), np.int16),
                             conditioned=conditional, pairs=np.zeros((4, COLORS, COLORS), np.int16),
                             palette=palette(), noise=np.arange(4096, dtype=np.int16) - 2048))


class ImageRuleTests(unittest.TestCase):
    def test_palette_round_trip(self):
        ids = np.arange(SIZE * SIZE, dtype=np.uint16).reshape(SIZE, SIZE).astype(np.uint8)
        np.testing.assert_array_equal(quantize(palette()[ids]), ids)

    def test_prompt_changes_pixels_without_answer_lookup(self):
        model = fixture_model()
        red, _ = model.generate('red', seed=7)
        blue, _ = model.generate('blue', seed=7)
        self.assertEqual(red.shape, (64, 64, 3))
        self.assertTrue(np.all(red == [255, 0, 0]))
        self.assertTrue(np.all(blue == [0, 0, 255]))
        with self.assertRaises(ValueError):
            model.generate('completely unknown caption')

    def test_seed_reproducibility_and_checkpoint_round_trip(self):
        model = fixture_model()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.npz'
            model.save(path)
            loaded = ImageCA.load(path)
            a, _ = model.generate('red blue', seed=7, noise=64)
            b, _ = loaded.generate('red blue', seed=7, noise=64)
            np.testing.assert_array_equal(a, b)
            with self.assertRaises(FileExistsError):
                model.save(path)

    def test_no_wrapped_edges_and_radius_one_old_state(self):
        model = fixture_model()
        model.arrays['pairs'][0, 3, 100] = -200
        original = np.zeros((64, 64), np.uint8)
        changed = original.copy()
        changed[-1] = 3
        energy, _ = model.condition('red')
        a = model.scores(original, energy)
        b = model.scores(changed, energy)
        np.testing.assert_array_equal(a[0], b[0])
        changed = original.copy()
        changed[40, 40] = 3
        b = model.scores(changed, energy)
        np.testing.assert_array_equal(a[10, 10], b[10, 10])
        self.assertNotEqual(a[41, 40, 100], b[41, 40, 100])

    def test_color_pair_counts_exclude_invalid_edges(self):
        counts = Counts(['red'], bins=1)
        counts.observe(np.zeros((64, 64), np.uint8), 'red')
        self.assertEqual(int(counts.spatial.sum()), 4096)
        self.assertEqual(int(counts.conditioned.sum()), 4096)
        self.assertEqual(int(counts.pairs.sum()), 4 * 64 * 63)

    def test_foreign_partial_file_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.npz'
            partial = path.with_name(path.name + '.partial')
            partial.write_bytes(b'other run')
            with self.assertRaises(FileExistsError):
                fixture_model().save(path)
            self.assertEqual(partial.read_bytes(), b'other run')

    def test_sparse_positive_neighbor_evidence_does_not_overpower_prior(self):
        model = fixture_model()
        model.arrays['pairs'][:, :, 7] = 30000
        rgb, _ = model.generate('red', noise=0, steps=6)
        self.assertTrue(np.all(rgb == [255, 0, 0]))

    def test_integer_layout_interpolation_and_small_cluster_merging(self):
        from cael_image.layout import upscale_integer, fit_layouts
        coarse = np.zeros((16, 16, 3), np.uint8)
        coarse[:, 8:] = 200
        fine = upscale_integer(coarse)
        self.assertEqual(fine.shape, (64, 64, 3))
        self.assertTrue(np.all(fine[:, 0] == 0))
        self.assertTrue(np.all(fine[:, -1] == 200))
        synthetic = [np.full((16, 16, 3), value, np.uint8) for value in [0, 0, 0, 0, 200, 200, 200, 255]]
        config = dict(layout_clusters=3, layout_size=16, layout_iterations=4, layout_min_images=3, seed=1)
        arrays, report = fit_layouts(synthetic, ['red'] * 8, ['red'], config)
        self.assertEqual(sum(report['members_per_cluster']), 8)
        self.assertTrue(all(size >= 3 for size in report['members_per_cluster']))
        self.assertEqual(arrays['layouts'].dtype, np.uint8)

    def test_v2_checkpoint_geometry_and_round_trip(self):
        old = fixture_model()
        meta = dict(old.metadata, format='cael-integer-image-v2', layout_clusters=1, layout_size=16)
        arrays = dict(old.arrays, layouts=np.full((1, 16, 16, 3), 100, np.uint8),
                      layout_prior=np.zeros(1, np.int16), layout_words=np.zeros((2, 1), np.int16))
        model = ImageCA(meta, arrays)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'v2.npz'
            model.save(path)
            reloaded = ImageCA.load(path)
            a, metadata = model.generate('red', seed=4, noise=0)
            b, _ = reloaded.generate('red', seed=4, noise=0)
            np.testing.assert_array_equal(a, b)
            self.assertEqual(metadata['layout_id'], 0)


@unittest.skipIf(Image is None, 'Install requirements-image.txt to test image I/O.')
class ImageDataTests(unittest.TestCase):
    def test_optional_captions_preserve_unlabelled_images_without_inventing_labels(self):
        from cael_image.data import discover, split_records
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, colour in [('labelled', 'red'), ('unlabelled', 'blue'), ('empty', 'green')]:
                Image.new('RGB', (64, 64), colour).save(root / (name + '.png'))
            (root / 'labelled.txt').write_text('red hair', encoding='utf-8')
            (root / 'empty.txt').write_text('  ', encoding='utf-8')
            records = discover(root, require_captions=False)
            self.assertEqual(len(records), 3)
            by_name = {r['image']: r for r in records}
            self.assertEqual(by_name['unlabelled.png']['caption'], '')
            self.assertIsNone(by_name['unlabelled.png']['caption_sha256'])
            self.assertEqual(by_name['empty.png']['caption'], '')
            self.assertIsNotNone(by_name['empty.png']['caption_sha256'])
            self.assertEqual(by_name['labelled.png']['caption'], 'red hair')
            fitting, validation = split_records(records, 0.3, 42)
            self.assertEqual(len(fitting) + len(validation), 3)
            with self.assertRaises(ValueError):
                discover(root)

    def test_duplicate_safe_split_and_dry_run_no_training(self):
        from cael_image.data import discover, split_records
        from cael_image.train import train
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'data'
            data.mkdir()
            for name, color in [('a', (255, 0, 0)), ('duplicate', (255, 0, 0)), ('b', (0, 0, 255))]:
                Image.new('RGB', (64, 64), color).save(data / (name + '.png'))
                (data / (name + '.txt')).write_text('female character red blue', encoding='utf-8')
            records = discover(data)
            fitting, validation = split_records(records, 0.3, 42)
            self.assertFalse({r['pixel_sha256'] for r in fitting} & {r['pixel_sha256'] for r in validation})
            config = json.loads((ROOT / 'train_image_config.json').read_text())
            config.update(dataset_dir='data', output_dir='output', min_token_images=1)
            config_path = root / 'config.json'
            config_path.write_text(json.dumps(config), encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                report = train(config_path, dry_run=True)
            self.assertFalse(report['training_started'])
            self.assertFalse((root / 'output').exists())

    def test_wrong_geometry_and_missing_caption(self):
        from cael_image.data import discover
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'x.png'
            Image.new('RGB', (32, 32), 'white').save(path)
            with self.assertRaisesRegex(ValueError, 'Missing matching caption'):
                discover(root)
            path.with_suffix('.txt').write_text('female character', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'expected 64x64'):
                discover(root)

    def test_image_cli_writes_64_png(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / 'fixture.npz'
            output = Path(directory) / 'output.png'
            fixture_model().save(model)
            result = subprocess.run([sys.executable, str(ROOT / 'chat.py'), 'red', '--image',
                                     '--model', str(model), '--output', str(output), '--steps', '0'],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with Image.open(output) as image:
                self.assertEqual(image.size, (64, 64))
            self.assertEqual(json.loads(output.with_suffix('.json').read_text())['matched_words'], ['red'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
