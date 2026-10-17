"""Synthetic and metadata-only tests: never access private training photos."""
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from unittest.mock import patch

from cael_unified.assistant import route_request
from cael_unified.bundle import REQUIRED, open_bundle
from cael_unified.helper import calculate
from cael_unified.web import handler_for
from cael_image.general_appearance import resolve_subject


class UnifiedTests(unittest.TestCase):
    def test_router_preserves_code_and_howto_requests(self):
        self.assertEqual(route_request('Make a picture of a car'), 'image')
        self.assertEqual(route_request('Generate a bicycle'), 'image')
        self.assertEqual(route_request('Make a pizza emoji'), 'emoji')
        self.assertEqual(route_request('How do I draw an image in Python?'), 'chat')
        self.assertEqual(route_request('What is an emoji?'), 'chat')
        self.assertEqual(route_request('Write a script to generate a photo'), 'chat')

    def test_explicit_mode_and_unknown_mode(self):
        self.assertEqual(route_request('phone', 'image'), 'image')
        with self.assertRaises(ValueError):
            route_request('hello', 'unknown')

    def test_malformed_messages_are_rejected_without_loading_engines(self):
        from cael_unified.assistant import Assistant
        assistant = Assistant.__new__(Assistant)
        for messages in [None, [], ['text'], [{'role': 'assistant', 'content': 'hello'}]]:
            with self.assertRaises(ValueError):
                assistant.respond(messages)

    def test_stored_emoji_prior_works_without_network(self):
        import torch
        from types import SimpleNamespace
        from cael_unified.emoji import EmojiTool
        tool = EmojiTool.__new__(EmojiTool)
        tool.online, tool._online_misses = False, {}   # this test is about the stored, offline path
        tool.m = SimpleNamespace(C=2)
        references = torch.zeros(1, 64, 64, 3, dtype=torch.uint8)
        tool.learned = {'kiwibird': dict(counts=torch.ones(1024, 2), classmaps=torch.zeros(1, 1024, dtype=torch.long),
                                        pixels=references, sources=[dict(source='synthetic fixture', licence='MIT')])}
        with patch('urllib.request.urlopen', side_effect=AssertionError('Network forbidden')):
            priors, pixels, sources = tool.fetched_prior('kiwi bird')
            self.assertIsNone(tool.fetched_prior('missing word')[0])
        torch.testing.assert_close(priors[0].sum(1), torch.ones(1024))
        self.assertTrue(bool((priors[0][:, 0] > priors[0][:, 1]).all()))
        self.assertIs(pixels, references)
        self.assertEqual(sources[0]['source'], 'synthetic fixture')

    def test_helper_uses_exact_bounded_arithmetic(self):
        self.assertEqual(calculate('Calculate 0.1 + 0.2')['response'], '0.1 + 0.2 = 3/10')
        self.assertEqual(calculate('What is (12 + 3) * 4?')['response'], '(12 + 3) * 4 = 60')
        self.assertIsNone(calculate('__import__("os").system("echo nope")'))
        self.assertIsNone(calculate('9 ** 99999999'))
        self.assertIsNone(calculate('1 / 0'))

    def test_subjects_require_word_boundaries_and_one_category(self):
        aliases = {'car': ['car', 'automobile'], 'cat': ['cat'], 'phone': ['phone', 'smartphone']}
        self.assertEqual(resolve_subject('a smartphone photo', aliases), 'phone')
        with self.assertRaises(ValueError):
            resolve_subject('a carpet photo', aliases)
        with self.assertRaises(ValueError):
            resolve_subject('a car and a cat', aliases)
        with self.assertRaises(ValueError):
            resolve_subject('a unicorn', aliases)

    def make_bundle(self, path, extra=None, corrupt=None):
        content = {name: ('synthetic fixture ' + name).encode() for name in REQUIRED}
        if extra:
            content.update(extra)
        manifest = dict(format='cael-unified-v1', version='0.2.1',
                        files={name: hashlib.sha256(value).hexdigest() for name, value in content.items()})
        if corrupt:
            content[corrupt] = b'changed after hashing'
        with zipfile.ZipFile(path, 'w') as archive:
            for name, value in content.items():
                archive.writestr(name, value)
            archive.writestr('bundle.json', json.dumps(manifest))

    def test_bundle_rejects_traversal_before_writing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'unsafe.cael'
            self.make_bundle(path, extra={'../escaped.txt': b'no'})
            with self.assertRaises(ValueError):
                open_bundle(path, Path(temp) / 'cache')
            self.assertFalse((Path(temp) / 'escaped.txt').exists())

    def test_bundle_rejects_altered_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'altered.cael'
            self.make_bundle(path, corrupt='image/model.pt')
            with self.assertRaises(ValueError):
                open_bundle(path, Path(temp) / 'cache')

    def test_bundle_verifies_cached_weights_again(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'valid.cael'
            self.make_bundle(path)
            root, _ = open_bundle(path, Path(temp) / 'cache')
            (root / 'image/model.pt').write_bytes(b'modified cached data')
            with self.assertRaises(ValueError):
                open_bundle(path, Path(temp) / 'cache')

    def test_web_serves_only_generated_pngs_and_rejects_cross_origin(self):
        class FakeAssistant:
            def respond(self, messages, **kwargs):
                return dict(response='fixture reply', paths=[])
        with tempfile.TemporaryDirectory() as temp:
            assistant = FakeAssistant()
            assistant.output_root = Path(temp) / 'outputs'
            assistant.output_root.mkdir()
            (Path(temp) / 'secret.txt').write_text('should never be served')
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(assistant))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            root = f'http://127.0.0.1:{server.server_port}'
            try:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(root + '/outputs/%2e%2e/secret.txt')
                self.assertEqual(error.exception.code, 404)
                request = urllib.request.Request(root + '/api/respond', data=b'{}',
                                                 headers={'Content-Type': 'application/json', 'Origin': 'https://example.com'})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code, 403)
                request = urllib.request.Request(root + '/', headers={'Host': 'example.com'})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code, 403)
                request = urllib.request.Request(root + '/api/respond', data=json.dumps({'messages': [{'role': 'user', 'content': 'hello'}]}).encode(),
                                                 headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(json.load(response)['response'], 'fixture reply')
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
