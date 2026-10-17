"""Shared worker tests use synthetic inputs only; no training photos are read."""
import http.cookiejar
import json
from pathlib import Path
import secrets
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from cael_unified.public_worker import Busy, Server, SharedWorker, handler_for, session_owner, sign_session


class SharedWorkerTests(unittest.TestCase):
    def test_signed_sessions_reject_tampering(self):
        key = b'fixture-key'
        owner = secrets.token_urlsafe(24)
        cookie = sign_session(key, owner)
        self.assertEqual(session_owner(key, 'cael_session=' + cookie), owner)
        self.assertIsNone(session_owner(key, 'cael_session=' + cookie[:-1] + ('0' if cookie[-1] != '0' else '1')))
        self.assertIsNone(session_owner(key, 'bad cookie'))

    def test_chat_runs_while_image_queue_is_busy_and_jobs_are_owned(self):
        entered, release = threading.Event(), threading.Event()

        class FakeAssistant:
            def respond(self, messages, **kwargs):
                text = messages[-1]['content']
                if text.startswith('draw'):
                    entered.set()
                    release.wait(3)
                return dict(response=text, paths=[])

        with tempfile.TemporaryDirectory() as temp:
            worker = SharedWorker(output_root=temp, assistant_factory=FakeAssistant, capacity=2)
            try:
                image = worker.submit('alice', dict(messages=[dict(role='user', content='draw a car')], client_id='first'))
                self.assertTrue(entered.wait(1))
                self.assertIs(worker.submit('alice', dict(messages=[dict(role='user', content='draw a car')], client_id='first')), image)
                chat = worker.submit('bob', dict(messages=[dict(role='user', content='hello')]))
                limit = time.monotonic() + 2
                while chat.state != 'done' and time.monotonic() < limit:
                    time.sleep(.01)
                self.assertEqual(chat.state, 'done')
                self.assertEqual(image.state, 'running')
                self.assertIsNone(worker.get('alice', chat.id))
                self.assertIsNone(worker.get('bob', image.id))
                self.assertIsNone(chat.request)
            finally:
                release.set()
                worker.close()

    def test_backpressure_does_not_create_unbounded_work(self):
        entered, release = threading.Event(), threading.Event()

        class FakeAssistant:
            def respond(self, messages, **kwargs):
                entered.set()
                release.wait(3)
                return dict(response='ok', paths=[])

        with tempfile.TemporaryDirectory() as temp:
            worker = SharedWorker(output_root=temp, capacity=1, assistant_factory=FakeAssistant)
            try:
                worker.submit('alice', dict(messages=[dict(role='user', content='hello')]))
                self.assertTrue(entered.wait(1))
                with self.assertRaises(Busy):
                    worker.submit('bob', dict(messages=[dict(role='user', content='hello')]))
            finally:
                release.set()
                worker.close()

    def test_http_sessions_isolate_results_and_images(self):
        class FakeAssistant:
            def respond(self, messages, **kwargs):
                self.output_root.mkdir(parents=True, exist_ok=True)
                path = self.output_root / 'fixture.png'
                path.write_bytes(b'fixture image bytes')
                return dict(response='fixture', paths=[str(path)])

        with tempfile.TemporaryDirectory() as temp:
            worker = SharedWorker(output_root=temp, assistant_factory=FakeAssistant)
            server = Server(('127.0.0.1', 0), handler_for(worker, b'fixture-secret'))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            users = [urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())) for _ in range(2)]
            try:
                for client in users:
                    client.open(url + '/').close()
                payload = json.dumps(dict(messages=[dict(role='user', content='hello')])).encode()
                req = urllib.request.Request(url + '/api/jobs', data=payload, headers={'Content-Type': 'application/json'})
                with users[0].open(req) as response:
                    job = json.load(response)
                job_url = url + '/api/jobs/' + job['id']
                for _ in range(100):
                    with users[0].open(job_url) as response:
                        result = json.load(response)
                    if result['state'] == 'done':
                        break
                    time.sleep(.01)
                self.assertEqual(result['state'], 'done')
                image_url = url + result['result']['images'][0]
                with users[0].open(image_url) as response:
                    self.assertEqual(response.read(), b'fixture image bytes')
                for path in (job_url, image_url):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        users[1].open(path)
                    self.assertEqual(error.exception.code, 404)
                bad = urllib.request.Request(url + '/api/jobs', data=payload, headers={'Origin': 'https://example.com'})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    users[0].open(bad)
                self.assertEqual(error.exception.code, 403)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                worker.close()


if __name__ == '__main__':
    unittest.main()
