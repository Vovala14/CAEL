"""Shared 0.2.4 worker: anonymous sessions, queued jobs, private image access.

There is no visitor-count cap. Bounded work queues protect the PC's resources;
chat and image work use separate pools so image generation does not block chat.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import html
import hmac
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import shutil
import threading
import time
from urllib.parse import urlparse

from .assistant import Assistant, MAX_CHARACTERS, MAX_MESSAGES, route_request
from .bundle import ROOT, VERSION
from .web import MAX_REQUEST_BYTES, PAGE as LOCAL_PAGE, avatar_asset

PUBLIC_SCRIPT = '''
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function submitJob(payload){for(let attempt=0;attempt<40;attempt++){const response=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(response.status===503||response.status===429){button.textContent='Waiting for a turn…';await delay(Math.min(15000,2000+attempt*500));continue}const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed');return result.id}throw new Error('The worker is busy. Please try again shortly.')}
async function waitJob(id){const started=Date.now();while(Date.now()-started<900000){await delay(1500);const response=await fetch('/api/jobs/'+id);if(response.status===429||response.status===502||response.status===503){await delay(3000);continue}const job=await response.json();if(!response.ok)throw new Error(job.error||'Request failed');if(job.state==='done')return job.result;if(job.state==='failed')throw new Error(job.error||'The worker could not finish');button.textContent=job.state==='queued'?'Queued…':'Working…'}throw new Error('This request took too long. Please try again.')}
form.addEventListener('submit',async event=>{event.preventDefault();const text=input.value.trim();if(!text)return;add(text,true);messages.push({role:'user',content:text});input.value='';setThinking(true);try{const payload={messages:messages,mode:document.querySelector('#mode').value,n:2,client_id:crypto.randomUUID()};const id=await submitJob(payload);const result=await waitJob(id);add(result.response,false,result.images||[],result.details||'');messages.push({role:'assistant',content:result.response})}catch(error){add(error.message);messages.pop()}finally{setThinking(false);input.focus()}});
'''
PAGE = LOCAL_PAGE[:LOCAL_PAGE.index("form.addEventListener('submit'")] + PUBLIC_SCRIPT + '</script></html>'
PAGE = PAGE.replace('Chat, helper, emoji and small pictures in one place', 'Chat, helper, emoji and small pictures · shared 0.2.4 worker')
PAGE = PAGE.replace('</header>', '<br><small><a href="/sources" target="_blank" rel="noopener" style="color:inherit">Internet data sources and licences</a></small></header>')
PAGE = PAGE.replace("add(result.response,false,result.images||[],result.details||'')", "add(result.response,false,result.images||[],result.details||'',result.sources||[])")


def sources_page():
    notices = []
    active=ROOT/'research/active_models.json'
    language=json.loads(active.read_text()).get('language') if active.is_file() else None
    repair=json.loads(active.read_text()).get('text_repair') if active.is_file() else None
    if repair:
        notices.append('<h2>Spelling interpretation</h2><p>Locally authored control-phrase word and bigram counts; no neural model or private conversations. '
                       'A do-not-rewrite vocabulary is adapted from '
                       '<a href="https://github.com/hermitdave/FrequencyWords">FrequencyWords, Hermit Dave and contributors, OpenSubtitles 2018</a> '
                       'under <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>. '
                       'Only alphabetic words occurring at least 1,000 times were retained. The derived checkpoint includes attribution and the full licence. '
                       'These authors do not endorse CAEL. Interpretations appear under About this result; names, code and negation are protected conservatively.</p>')
    if language:
        notices.append('<h2>Unified language training data</h2><p>Non-neural sparse token counts and authored social scenarios. '
                       'No private conversations or Tiny Theory of Mind test answers were used for fitting.</p>'
                       '<p><a href="https://maartensap.com/social-iqa/">Social IQa</a> — Maarten Sap, Hannah Rashkin, '
                       'Derek Chen, Ronan LeBras and Yejin Choi; <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. '
                       'Contexts and answer annotations were converted to fitted lexical and token counts.</p>')
        if language.get('wordnet'):
            notices.append('<p><a href="https://wordnet.princeton.edu/license-and-commercial-use">WordNet 3.0</a> — '
                       'Copyright 2006 Princeton University. Lexical relations compiled into probability-transfer and query-expansion tables; '
                       'full licence and disclaimer retained below. These authors do not endorse CAEL.</p>')
        for source in language.get('training_sources', []):
            if source['name'] == 'Social IQa':
                continue  # Credited above, including older checkpoints.
            notices.append('<p><a href="'+html.escape(source['url'],quote=True)+'">'
                           +html.escape(source['name'])+'</a> — '+html.escape(source['authors'])
                           +'; <a href="'+html.escape(source['licence_url'],quote=True)+'">'
                           +html.escape(source['licence'])+'</a>. Converted into fitted statistical tables; '
                           'full notices accompany the checkpoint. No endorsement is implied.</p>')
    reasoning_sources=ROOT/'models/cael-reasoning-v1/sources.json'
    if reasoning_sources.is_file():
        reasoning=json.loads(reasoning_sources.read_text(encoding='utf-8'))
        notices.append('<h2>Reasoning training data</h2><p>Non-neural count grammars and automaton transitions fitted from licensed synthetic text. '
                       'Proof/state algorithms and constraint solvers are authored. User-provided premises are not saved as training data.</p><ul>'
                       + ''.join('<li><a href="'+html.escape(row['url'],quote=True)+'">'+html.escape(row['source'])+'</a> — '
                                 +html.escape(row['attribution'])+'; <a href="'+html.escape(row['licence_url'],quote=True)+'">'
                                 +html.escape(row['licence'])+'</a>. Source text converted into learned counts by CAEL.</li>' for row in reasoning['sources'])
                       + '</ul><p>BIG-bench logical deduction (James Simon, Chandan Singh and BIG-bench contributors), Apache 2.0, was used only for evaluation.</p>')
    knowledge_report = ROOT / 'models/cael-knowledge-v1/report.json'
    if knowledge_report.is_file():
        knowledge = json.loads(knowledge_report.read_text(encoding='utf-8'))
        notices.append('<h2>Local knowledge snapshot</h2><p>Wikipedia contributors — CC BY-SA 4.0. '
                       + str(int(knowledge['documents'])) + ' articles and ' + str(int(knowledge['passages']))
                       + ' text passages. Snapshot: ' + html.escape(knowledge['snapshot'])
                       + '. Text was stripped of media, markup and reference lists, indexed, and converted into lexical counts for non-neural retrieval. '
                       'Local answers link to their specific source revision and keep attribution and share-alike terms. '
                       'A stored snapshot is not a fresh verification. Canonical public article text fetched on a miss can be retained for 30 days; '
                       'private conversations are not training data.</p><p><a href="https://en.wikipedia.org/wiki/Wikipedia:Vital_articles/Level_4">'
                       'Core-topic curriculum</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a></p>')
    news_sources = ROOT / 'models' / 'cael-news-policy-v1' / 'sources.json'
    if news_sources.is_file():
        credits = json.loads(news_sources.read_text(encoding='utf-8'))
        notices.append('<h2>News topic training sources</h2><p>Wikipedia contributors, CC BY-SA 4.0. '
                       'The non-neural topic classifier was fitted on earlier-month summaries; source text was converted to integer token/category counts.</p><ul>'
                       + ''.join('<li><a href="' + html.escape(row['url'], quote=True) + '">' + html.escape(row['url']) + '</a></li>' for row in credits)
                       + '</ul>')
    for name in ('LICENSE-Fluent-Emoji-MIT.txt', 'LICENSE-CC-BY-4.0.txt', 'LICENSE-CC-BY-SA-4.0.txt',
                 'LICENSE-PrOntoQA-Apache-2.0.txt','LICENSE-BIG-bench-Apache-2.0.txt','REASONING_DATA_NOTICES.md',
                 'LICENSE-WordNet-3.0.txt','TOM_027_TRAINING_NOTICES.md'):
        path = ROOT / 'licenses' / name
        if path.is_file():
            notices.append('<h2>' + html.escape(name) + '</h2><pre style="white-space:pre-wrap">' + html.escape(path.read_text(encoding='utf-8')) + '</pre>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>CAEL data sources</title>'
            '<body style="max-width:900px;margin:30px auto;font:16px system-ui;padding:16px">'
            '<h1>CAEL internet sources</h1><p>Responses include the actual source, licence and attribution. '
            'Queries are sent to the named provider; conversation history and private training photos are not sent.</p>'
            '<ul><li><a href="https://www.wikidata.org/wiki/Wikidata:Copyright">Wikidata contributors — CC0</a></li>'
            '<li><a href="https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use">Wikipedia contributors — CC BY-SA 4.0</a>. '
            'Excerpts and news digest text retain share-alike terms.</li>'
            '<li><a href="https://api.met.no/doc/License">Data from MET Norway — CC BY 4.0</a>. Forecasts are formatted by CAEL.</li>'
            '<li><a href="https://www.gdeltproject.org/about.html#termsofuse">The GDELT Project — free commercial dataset terms</a>. '
            'Article texts and publisher images are not downloaded.</li>'
            '<li><a href="https://github.com/hfg-gmuend/openmoji">OpenMoji contributors — CC BY-SA 4.0</a></li>'
            '<li><a href="https://github.com/jdecked/twemoji">Twitter and Twemoji contributors — CC BY 4.0</a></li>'
            '<li>Emoji artwork from <a href="https://github.com/EmojiTwo/emojitwo/">Emojitwo</a>, originally '
            '<a href="https://www.emojione.com">EmojiOne 2.2</a> by Ranks.com, with Emojitwo community contributions — CC BY 4.0</li>'
            '<li><a href="https://github.com/microsoft/fluentui-emoji">Microsoft Fluent Emoji — MIT</a></li>'
            '<li>Wikimedia Commons icons — per-file CC0, public domain or CC BY only; creators and file pages appear with the result.</li></ul>'
            '<p>CAEL normalizes and transforms emoji reference shapes. Retain credits and licence information with reused outputs. '
            'Derived outputs using OpenMoji or other share-alike references are distributed under CC BY-SA 4.0. '
            'Source permission does not change the licence of the CAEL software or establish rights in private portrait data.</p>'
            + ''.join(notices) + '</body></html>')


@dataclass
class Job:
    id: str
    owner: str
    request: dict | None
    created: float
    client_id: str | None = None
    state: str = 'queued'
    result: dict | None = None
    error: str | None = None
    finished: float | None = None


class Busy(Exception):
    pass


class SharedWorker:
    def __init__(self, bundle=None, output_root=None, capacity=128, result_ttl=3600, assistant_factory=None):
        if capacity < 1:
            raise ValueError('Positive queue capacity required')
        self.bundle = bundle
        self.output_root = Path(output_root or ROOT / 'outputs' / 'shared_021').resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.result_ttl = result_ttl
        self.jobs = {}
        self.clients = {}
        self.lock = threading.RLock()
        self.slots = threading.BoundedSemaphore(capacity)
        self.local = threading.local()
        self.assistant_factory = assistant_factory or (lambda: Assistant(self.bundle, self.output_root))
        self.chat_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='cael-chat')
        self.image_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='cael-images')

    @staticmethod
    def validate(request):
        if not isinstance(request, dict):
            raise ValueError('Expected a JSON object')
        messages = request.get('messages')
        if not isinstance(messages, list) or not messages or len(messages) > MAX_MESSAGES:
            raise ValueError('Invalid conversation')
        if not all(isinstance(m, dict) and m.get('role') in ('user', 'assistant', 'system') and isinstance(m.get('content'), str) for m in messages):
            raise ValueError('Invalid message')
        if messages[-1]['role'] != 'user' or not messages[-1]['content'].strip() or sum(len(m['content']) for m in messages) > MAX_CHARACTERS:
            raise ValueError('Invalid conversation length or last message')
        count = request.get('n', 2)
        if type(count) is not int or not 1 <= count <= 8:
            raise ValueError('Choose between 1 and 8 images')
        seed = request.get('seed')
        if seed is not None and (type(seed) is not int or not 0 <= seed < 2 ** 31):
            raise ValueError('Invalid seed')
        mode = request.get('mode', 'auto')
        route = route_request(messages[-1]['content'], mode)
        client = request.get('client_id')
        if client is not None and (not isinstance(client, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', client)):
            raise ValueError('Invalid request identifier')
        return route

    def submit(self, owner, request):
        route = self.validate(request)
        self.cleanup()
        client_id = request.get('client_id')
        with self.lock:
            if client_id and (owner, client_id) in self.clients:
                return self.jobs[self.clients[owner, client_id]]
            if not self.slots.acquire(blocking=False):
                raise Busy()
            job = Job(secrets.token_hex(16), owner, request, time.monotonic(), client_id)
            self.jobs[job.id] = job
            if client_id:
                self.clients[owner, client_id] = job.id
        pool = self.image_pool if route in ('image', 'emoji') else self.chat_pool
        try:
            pool.submit(self.run, job)
        except Exception:
            with self.lock:
                self.jobs.pop(job.id, None)
                self.clients.pop((owner, client_id), None)
            self.slots.release()
            raise
        return job

    def run(self, job):
        try:
            if time.monotonic() - job.created > 900:
                raise TimeoutError('Expired queue entry')
            with self.lock:
                job.state = 'running'
            if not hasattr(self.local, 'assistant'):
                self.local.assistant = self.assistant_factory()
            assistant = self.local.assistant
            # The instance is thread-local; this change cannot redirect another job.
            assistant.output_root = self.output_root / job.id
            request = job.request
            result = assistant.respond(request['messages'], n=request.get('n', 2), seed=request.get('seed'), mode=request.get('mode', 'auto'))
            with self.lock:
                job.result = result
                job.state = 'done'
        except Exception as error:
            print('Worker request failed:', type(error).__name__, flush=True)
            with self.lock:
                job.state = 'failed'
                job.error = 'The worker could not finish this request. Please try again.'
        finally:
            with self.lock:
                job.request = None  # Do not retain conversation inputs after completion.
                job.finished = time.monotonic()
            self.slots.release()

    def get(self, owner, job_id):
        self.cleanup()
        with self.lock:
            job = self.jobs.get(job_id)
            return job if job and secrets.compare_digest(job.owner, owner) else None

    def cleanup(self):
        expired = []
        now = time.monotonic()
        with self.lock:
            for job_id, job in list(self.jobs.items()):
                if job.finished is not None and now - job.finished > self.result_ttl:
                    expired.append(job_id)
                    self.jobs.pop(job_id)
                    if job.client_id:
                        self.clients.pop((job.owner, job.client_id), None)
        for job_id in expired:
            target = (self.output_root / job_id).resolve()
            # Windows deletion stays within this service's own generated-job root.
            if target != self.output_root and target.is_relative_to(self.output_root) and target.is_dir():
                shutil.rmtree(target)

    def close(self):
        self.chat_pool.shutdown(wait=True)
        self.image_pool.shutdown(wait=True)


def proxy_site():
    """The site whose server-side proxy calls this worker (requests without a browser Origin), from
    research/active_models.json {"site_proxy": {"site": "vynly.co"}}; None when not configured."""
    try:
        entry = json.loads((ROOT / 'research' / 'active_models.json').read_text(encoding='utf-8')).get('site_proxy') or {}
    except (OSError, ValueError):
        return None
    site = entry.get('site')
    return site if isinstance(site, str) and re.fullmatch(r'[a-z0-9.-]{3,60}', site) else None


def sign_session(key, owner):
    return owner + '.' + hmac.new(key, owner.encode('ascii'), hashlib.sha256).hexdigest()


def session_owner(key, cookie_header):
    try:
        cookie = SimpleCookie()
        cookie.load(cookie_header or '')
        signed = cookie['cael_session'].value
        owner, signature = signed.split('.')
        if not re.fullmatch(r'[A-Za-z0-9_-]{32}', owner):
            return None
        expected = sign_session(key, owner)
        return owner if hmac.compare_digest(signed, expected) else None
    except (KeyError, ValueError, TypeError, CookieError):
        return None


def handler_for(worker, key, link_file=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def host_allowed(self):
            host = urlparse('http://' + self.headers.get('Host', '')).hostname
            allowed = {'127.0.0.1', 'localhost', '::1'}
            if link_file and Path(link_file).is_file():
                try:
                    allowed.add(urlparse(json.loads(Path(link_file).read_text())['url']).hostname)
                except (OSError, ValueError, KeyError):
                    pass
            return host in allowed

        def send(self, status, body, content_type='application/json; charset=utf-8', cookie=None):
            if isinstance(body, dict):
                body = json.dumps(body).encode('utf-8')
            elif isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Vary', 'Cookie')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            if status == 503:
                self.send_header('Retry-After', '3')
            if cookie:
                host = urlparse('http://' + self.headers.get('Host', '')).hostname
                secure = '; Secure' if host not in ('127.0.0.1', 'localhost', '::1') or self.headers.get('X-Forwarded-Proto') == 'https' else ''
                self.send_header('Set-Cookie', 'cael_session=' + cookie + '; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400' + secure)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if not self.host_allowed():
                return self.send(403, dict(error='Unknown host'))
            path = urlparse(self.path).path
            asset = avatar_asset(path)
            if asset is not None:
                return self.send(200, asset[0], asset[1])
            owner = session_owner(key, self.headers.get('Cookie'))
            if path == '/':
                signed = None if owner else sign_session(key, secrets.token_urlsafe(24))
                return self.send(200, PAGE, 'text/html; charset=utf-8', signed)
            if path == '/api/health':
                active = ROOT/'research/active_models.json'
                language = json.loads(active.read_text()).get('language') if active.is_file() else None
                return self.send(200, dict(status='ok', model='CAEL ' + VERSION, user_cap=None,
                                          chat_backend='unified count language; legacy free-text fallback' if language else 'installed legacy fallback',
                                          language_model=Path(language['path']).parent.name if language else None,
                                          internet_lookup=True, sources=['Wikipedia', 'Wikidata', 'MET Norway', 'GDELT', 'licensed emoji repositories']))
            if path == '/sources':
                return self.send(200, sources_page(), 'text/html; charset=utf-8')
            match = re.fullmatch(r'/api/jobs/([0-9a-f]{32})(?:/images/(\d+))?', path)
            if not match or not owner:
                return self.send(404, dict(error='Not found'))
            job = worker.get(owner, match[1])
            if not job:
                return self.send(404, dict(error='Not found'))
            if match[2] is not None:
                paths = (job.result or {}).get('paths', [])
                index = int(match[2])
                if job.state != 'done' or index >= len(paths):
                    return self.send(404, dict(error='Not found'))
                target = Path(paths[index]).resolve()
                job_root = (worker.output_root / job.id).resolve()
                if not target.is_relative_to(job_root) or target.suffix.lower() != '.png' or not target.is_file():
                    return self.send(404, dict(error='Not found'))
                return self.send(200, target.read_bytes(), 'image/png')
            response = dict(id=job.id, state=job.state)
            if job.state == 'done':
                result = job.result
                public = {k: result[k] for k in ('response', 'route', 'details', 'seed', 'sources') if k in result}
                public['images'] = [f'/api/jobs/{job.id}/images/{i}' for i in range(len(result.get('paths', [])))]
                sources = result.get('tool', {}).get('fetched', [])
                if sources:
                    public['details'] = public.get('details', '') + '\nSources: ' + '; '.join(s['source'] + ': ' + s['url'] for s in sources)
                response['result'] = public
            elif job.state == 'failed':
                response['error'] = job.error
            return self.send(200, response)

        def do_POST(self):
            if not self.host_allowed():
                return self.send(403, dict(error='Unknown host'))
            origin = self.headers.get('Origin')
            if origin and urlparse(origin).netloc.lower() != self.headers.get('Host', '').lower():
                return self.send(403, dict(error='Cross-origin request rejected'))
            if self.path != '/api/jobs':
                return self.send(404, dict(error='Not found'))
            owner = session_owner(key, self.headers.get('Cookie'))
            if not owner:
                return self.send(403, dict(error='Open the shared link first to start your session'))
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_REQUEST_BYTES:
                    raise ValueError('Invalid request size')
                request = json.loads(self.rfile.read(length))
                site = proxy_site()
                if site and not origin and isinstance(request, dict) and isinstance(request.get('messages'), list) \
                        and not any(isinstance(m, dict) and m.get('role') == 'system' for m in request['messages']):
                    # No browser Origin: a server-side proxy (vynly.co's /api/assistant) sent this. Say so, so CAEL
                    # answers site help questions from that site's knowledge.
                    request['messages'] = [dict(role='system', content='site: ' + site)] + request['messages']
                job = worker.submit(owner, request)
                return self.send(202, dict(id=job.id, state=job.state))
            except Busy:
                return self.send(503, dict(error='The worker is busy. Your browser can retry shortly.'))
            except (ValueError, TypeError, UnicodeDecodeError):
                return self.send(400, dict(error='Invalid request'))
    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--bundle')
    parser.add_argument('--state-dir', type=Path, default=ROOT / 'research' / 'shared_021')
    args = parser.parse_args()
    args.state_dir.mkdir(parents=True, exist_ok=True)
    key_file = args.state_dir / 'session.key'
    if not key_file.exists():
        with key_file.open('xb') as output:
            output.write(secrets.token_bytes(32))
    key = key_file.read_bytes()
    worker = SharedWorker(args.bundle)
    server = Server(('127.0.0.1', args.port), handler_for(worker, key, args.state_dir / 'link.json'))
    stop = threading.Event()

    def cleanup():
        while not stop.wait(30):
            worker.cleanup()

    threading.Thread(target=cleanup, daemon=True).start()
    print(f'Shared CAEL {VERSION} worker ready on 127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        worker.close()


if __name__ == '__main__':
    main()
