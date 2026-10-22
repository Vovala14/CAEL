"""Authored regressions: exact math chains and image-free bundle validation."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from cael_unified import orchestrator
from cael_unified.bundle import REQUIRED, PICTURE_FILES, open_bundle
from cael_unified.helper import calculate


class UpgradeTests(unittest.TestCase):
    def test_exact_fraction_chain(self):
        board = orchestrator.run(['calculate 1/3', 'multiply it by 3'], lambda text, history: calculate(text))
        self.assertEqual(board.entries[-1].value, '1')
        self.assertEqual(board.entries[0].value, '1/3')

    def test_decimal_source_precision(self):
        self.assertTrue(calculate('0.1234567890123456789 * 10000000000000000000')['response'].endswith('= 1234567890123456789'))
        from cael_unified.helper_math import parsed
        self.assertEqual(str(parsed('0.1234567890123456789 * 10000000000000000000')), '1234567890123456789')

    def test_independent_checker_preserves_exact_decimal(self):
        from cael_unified.verify import check_arithmetic
        expression = '0.1234567890123456789 * 10000000000000000000'
        self.assertEqual(check_arithmetic(expression, calculate(expression))['status'], 'verified')
        wrong = dict(response=expression+' = 1234567890123456800')
        self.assertEqual(check_arithmetic(expression, wrong)['value'], '1234567890123456789')

    def test_sequential_percentage_changes(self):
        steps = orchestrator.plan('Calculate 100. Then increase it by 20%. Then decrease it by 20%. Then triple it')
        self.assertEqual(len(steps), 4)
        board = orchestrator.run(steps, lambda text, history: calculate(text))
        self.assertEqual([e.value for e in board.entries], ['100', '120', '96', '288'])

    def test_ambiguous_solution_does_not_reuse_old_number(self):
        replies = iter([calculate('10'), dict(route='helper/algebra', response='x = -2 or x = 2')])
        board = orchestrator.run(['calculate 10', 'solve x squared = 4', 'double it'], lambda text, history: next(replies))
        self.assertIsNone(board.entries[1].value)
        self.assertEqual(board.entries[2].route, 'chat/plan-skipped')

    def test_no_images_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'fixture.cael'
            def write(extra=None):
                files = {name: b'fixture' for name in REQUIRED - PICTURE_FILES}
                files.update(extra or {})
                manifest = dict(format='cael-unified-v1', version='0.2.8', profile='no-images',
                                files={name: hashlib.sha256(data).hexdigest() for name, data in files.items()})
                with zipfile.ZipFile(path, 'w') as z:
                    for name, data in files.items():
                        z.writestr(name, data)
                    z.writestr('bundle.json', json.dumps(manifest))
            write()
            root, manifest = open_bundle(path, Path(temp) / 'cache')
            self.assertEqual(manifest['profile'], 'no-images')
            self.assertFalse((root / 'image').exists())
            write({'models/cael-image-test/test.npz': b'unwanted'})
            with self.assertRaises(ValueError):
                open_bundle(path, Path(temp) / 'cache')


if __name__ == '__main__':
    unittest.main()
