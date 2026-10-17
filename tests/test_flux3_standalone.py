"""Offline synthetic fixtures for same-prompt standalone batches."""
import base64
from contextlib import nullcontext
import io
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
try:
    from local_tools.flux3 import generate
    from local_tools.flux3 import setup
except ModuleNotFoundError as error:
    if error.name and (error.name == 'local_tools' or error.name.startswith('local_tools.flux3')):
        raise unittest.SkipTest('Standalone FLUX installation was removed by the owner') from error
    raise


def batch():
    return dict(count=2, base_seed=31, caption='One fixed detailed scene caption.', width=256, height=256,
                steps=16, completed=0, model_revision='fixture', cael_training_allowed=False)


def encoded_image():
    output = io.BytesIO()
    Image.new('RGB', (256, 256), (100, 150, 200)).save(output, format='PNG')
    return dict(images=[base64.b64encode(output.getvalue()).decode()])


class FluxBatchTests(unittest.TestCase):
    def test_replaced_weight_is_rejected_before_engine_start(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(generate, 'ROOT', Path(directory)):
            folder = Path(directory)
            path = folder / 'model.safetensors'
            path.write_bytes(b'replaced')
            record = dict(path=path.name, bytes=100, mtime_ns=path.stat().st_mtime_ns, sha256='unused')
            (folder / 'install_manifest.json').write_text(json.dumps(dict(weights=[record])))
            config = {name: path.name for name in ('diffusion_model', 'text_encoder', 'vae')}
            with self.assertRaisesRegex(RuntimeError, 'replaced or is incomplete'):
                generate.validate_weights(config)

    def test_same_size_changed_weight_must_match_checksum(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(generate, 'ROOT', Path(directory)):
            folder = Path(directory)
            path = folder / 'model.safetensors'
            path.write_bytes(b'wrong')
            record = dict(path=path.name, bytes=5, mtime_ns=0, sha256=hashlib.sha256(b'valid').hexdigest())
            (folder / 'install_manifest.json').write_text(json.dumps(dict(weights=[record])))
            config = {name: path.name for name in ('diffusion_model', 'text_encoder', 'vae')}
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                generate.validate_weights(config)
            path.write_bytes(b'valid')
            generate.validate_weights(config)

    def test_repair_preserves_wrong_file_and_bypasses_stale_download_cache(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(setup, 'ROOT', Path(directory)), \
             patch.object(setup, 'WEIGHTS', Path(directory) / 'weights'):
            target = setup.WEIGHTS / 'flux3/model.safetensors'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'wrong model')
            calls = []
            def download(repo, name, **kwargs):
                calls.append(kwargs)
                target.write_bytes(b'official model')
                return str(target)
            expected = hashlib.sha256(b'official model').hexdigest()
            path, digest = setup.download_verified(download, 'fixture', 'revision', target.name, 'flux3', expected)
            self.assertEqual(digest, expected)
            self.assertEqual(path.read_bytes(), b'official model')
            self.assertTrue(calls[0]['force_download'])
            preserved = list((Path(directory) / 'recovered_files').rglob('model.safetensors'))
            self.assertEqual(len(preserved), 1)
            self.assertEqual(preserved[0].read_bytes(), b'wrong model')

    def test_caption_is_identical_and_seeds_are_distinct(self):
        plan = batch()
        requests = [generate.request_for(plan, index) for index in range(2)]
        self.assertEqual([r['prompt'] for r in requests], [plan['caption']] * 2)
        self.assertEqual([r['seed'] for r in requests], [31, 32])
        self.assertTrue(all(r['batch_size'] == 1 for r in requests))
        self.assertNotEqual(generate.image_name(plan, 0), generate.image_name(plan, 1))

    def test_model_is_loaded_once_and_each_image_keeps_metadata(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(generate, 'engine_command', return_value=['fixture']), \
             patch.object(generate, 'OwnedServer', return_value=nullcontext()) as server, \
             patch.object(generate, 'http_json', return_value=encoded_image()) as api:
            folder = Path(directory)
            plan = batch()
            generate.run_batch(folder, plan, {})
            self.assertEqual(server.call_count, 1)
            self.assertEqual(api.call_count, 2)
            for index in range(2):
                path = folder / generate.image_name(plan, index)
                self.assertEqual(path.with_suffix('.txt').read_text(), plan['caption'])
                record = json.loads(path.with_suffix('.json').read_text())
                self.assertEqual(record['seed'], 31 + index)
                self.assertFalse(record['cael_training_allowed'])
            self.assertEqual(json.loads((folder / 'batch.json').read_text())['status'], 'complete')

    def test_interrupted_batch_resumes_without_regenerating_saved_image(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(generate, 'engine_command', return_value=['fixture']), \
             patch.object(generate, 'OwnedServer', return_value=nullcontext()):
            folder = Path(directory)
            plan = batch()
            with patch.object(generate, 'http_json', side_effect=[encoded_image(), OSError('fixture failure')]):
                with self.assertRaises(OSError):
                    generate.run_batch(folder, plan, {})
            first = folder / generate.image_name(plan, 0)
            before = first.read_bytes()
            with patch.object(generate, 'http_json', return_value=encoded_image()) as api:
                generate.run_batch(folder, plan, {})
                self.assertEqual(api.call_count, 1)
                self.assertEqual(api.call_args.args[1]['seed'], 32)
            self.assertEqual(first.read_bytes(), before)

    def test_engine_binds_only_to_localhost_with_expected_sampling(self):
        config = dict(diffusion_model='fixture', text_encoder='fixture', vae='fixture', backend='vulkan0',
                      max_vram_gib=12, weight_type='q8_0', steps=16, cfg_scale=1.)
        command = generate.engine_command(config, 12345)
        self.assertEqual(command[command.index('--listen-ip') + 1], '127.0.0.1')
        self.assertEqual(command[command.index('--scheduler') + 1], 'discrete')
        self.assertEqual(command[command.index('--flow-shift') + 1], '6.93')


if __name__ == '__main__':
    unittest.main()
