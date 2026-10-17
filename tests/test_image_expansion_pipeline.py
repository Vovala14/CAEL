"""Synthetic-only fixtures protect held-out data across curriculum expansion."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from research.general_image_025 import run_pipeline as pipeline


class ExpansionPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.old, self.new, self.merged, self.model = [root / name for name in ('old', 'new', 'merged', 'model')]
        self.model.mkdir()
        self.patches = [patch.object(pipeline, key, value) for key, value in
                        [('OLD', self.old), ('NEW', self.new), ('MERGED', self.merged), ('OLD_MODEL', self.model)]]
        for item in self.patches:
            item.start()
        old = self.source(self.old, 'car', 5, 1)
        self.source(self.new, 'apple', 8, 30)
        split = dict(car=dict(train=[old[0], old[1]], development=[old[2]], confirmation=[old[3]]))
        (self.model / 'split.json').write_text(json.dumps(split))

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def source(self, destination, subject, count, offset):
        records = []
        folder = destination / subject
        folder.mkdir(parents=True)
        for index in range(count):
            image = Image.new('RGB', (128, 128), (offset + index, 0, 0))
            path = folder / f'{index:04d}.png'
            image.save(path)
            records.append(dict(image=path.relative_to(destination).as_posix(), subject=subject, prompt='Synthetic fixture only',
                                image_file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest()))
        protocol = dict(source='Synthetic teacher outputs only', private_images_read=False, output_size=128,
                        teacher_model_sha256=pipeline.TEACHER_HASH)
        (destination / 'manifest.json').write_text(json.dumps(dict(protocol=protocol, records=records)))
        return records

    def test_previous_holdouts_and_exclusions_survive_merge(self):
        pipeline.merge()
        manifest = json.loads((self.merged / 'manifest.json').read_text())
        plans = json.loads((self.merged / 'split_plan.json').read_text())
        self.assertEqual(len(manifest['records']), 13)
        self.assertEqual({key: len(value) for key, value in plans['car'].items()},
                         dict(train=2, development=1, confirmation=1, excluded=1))
        self.assertEqual({key: len(value) for key, value in plans['apple'].items()},
                         dict(train=6, development=1, confirmation=1, excluded=0))
        self.assertEqual(plans['car']['confirmation'], ['car/00003.png'])
        self.assertEqual(plans['car']['excluded'], ['car/00004.png'])
        assigned = [image for plan in plans.values() for partition in plan.values() for image in partition]
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(set(assigned), {record['image'] for record in manifest['records']})
        self.assertTrue(all((self.merged / record['image']).with_suffix('.txt').is_file() for record in manifest['records']))

    def test_cross_dataset_duplicates_require_grouped_resplit(self):
        old = json.loads((self.old / 'manifest.json').read_text())
        new = json.loads((self.new / 'manifest.json').read_text())
        new['records'][0]['pixel_sha256'] = old['records'][0]['pixel_sha256']
        (self.new / 'manifest.json').write_text(json.dumps(new))
        with self.assertRaisesRegex(ValueError, 'Duplicate pixels'):
            pipeline.merge()
        self.assertFalse((self.merged / 'manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
