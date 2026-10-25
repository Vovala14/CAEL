"""Read-only access to reviewed free commercial providers, with shared caching."""
from collections import OrderedDict
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import gzip
import io
import json
import ssl
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse, parse_qs
import zlib

UA = 'CAEL/0.3.3 (https://github.com/Vovala14/CAEL)'
HOSTS = frozenset({'en.wikipedia.org', 'www.wikidata.org', 'commons.wikimedia.org',
                  'upload.wikimedia.org', 'thumb.wikimedia.org', 'api.met.no', 'api.gdeltproject.org',
                  'raw.githubusercontent.com', 'api.github.com'})
HOSTS = HOSTS | {'dl.fbaipublicfiles.com', 'datasets-server.huggingface.co', 's3.amazonaws.com'}
REPOSITORIES = ('/hfg-gmuend/openmoji/', '/jdecked/twemoji/',
                '/EmojiTwo/emojitwo/', '/microsoft/fluentui-emoji/',
                '/hermitdave/FrequencyWords/', '/asaparov/prontoqa/', '/google/BIG-bench/')


class LookupUnavailable(RuntimeError):
    pass


def allowed_url(url):
    try:
        parsed = urlparse(url)
        port = parsed.port
    except (ValueError, TypeError):
        return False
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username or parsed.password or port not in (None, 443):
        return False
    if parsed.hostname == 'raw.githubusercontent.com':
        return parsed.path.startswith(REPOSITORIES)
    if parsed.hostname == 'api.github.com':
        return parsed.path.startswith('/repos/microsoft/fluentui-emoji/')
    if parsed.hostname == 'dl.fbaipublicfiles.com':
        return parsed.path == '/babi/tasks_1-20_v1-2.tar.gz'
    if parsed.hostname == 's3.amazonaws.com':
        return parsed.path == '/text-datasets/babi_tasks_1-20_v1-2.tar.gz'
    if parsed.hostname == 'datasets-server.huggingface.co':
        return parsed.path in ('/rows', '/splits') and parse_qs(parsed.query).get('dataset') == ['facebook/babi_qa']
    return True


class ReviewedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise LookupUnavailable('The provider redirected outside reviewed sources')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass
class Cached:
    body: bytes
    expires: float
    last_modified: str | None = None


class Network:
    def __init__(self):
        self.cache = OrderedDict()
        self.cache_bytes = 0
        self.lock = threading.Lock()
        self.host_locks = {host: threading.Lock() for host in HOSTS}
        self.next_request = {}
        self.blocked_until = {}
        context = ssl.create_default_context()
        try:
            import certifi
            context.load_verify_locations(cafile=certifi.where())
        except ImportError:
            pass
        self.opener = urllib.request.build_opener(ReviewedRedirect(), urllib.request.HTTPSHandler(context=context))

    def get(self, url, ttl=300, timeout=8, max_bytes=16 * 1024 * 1024):
        if not allowed_url(url):
            raise LookupUnavailable('This provider is not approved for free commercial use')
        host = urlparse(url).hostname
        with self.host_locks[host]:
            now = time.time()
            with self.lock:
                cached = self.cache.get(url)
                if cached and cached.expires > now:
                    self.cache.move_to_end(url)
                    return cached.body
            if self.blocked_until.get(host, 0) > now:
                raise LookupUnavailable('The provider is temporarily unavailable or rate limited')
            time.sleep(max(0, self.next_request.get(host, 0) - now))
            headers = {'User-Agent': UA, 'Accept-Encoding': 'gzip, deflate'}
            if cached and cached.last_modified:
                headers['If-Modified-Since'] = cached.last_modified
            try:
                with self.opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as response:
                    body = response.read(max_bytes + 1)
                    if len(body) > max_bytes:
                        raise LookupUnavailable('Provider response too large')
                    encoding = response.headers.get('Content-Encoding', '')
                    if encoding == 'gzip':
                        with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
                            body = stream.read(max_bytes + 1)
                    elif encoding == 'deflate':
                        body = zlib.decompressobj().decompress(body, max_bytes + 1)
                    if len(body) > max_bytes:
                        raise LookupUnavailable('Provider response too large')
                    expires = time.time() + ttl
                    last_modified = response.headers.get('Last-Modified')
                    expiry = response.headers.get('Expires')
                    if expiry:
                        try:
                            expires = max(expires, parsedate_to_datetime(expiry).timestamp())
                        except (TypeError, ValueError):
                            pass
            except urllib.error.HTTPError as error:
                if error.code == 304 and cached:
                    cached.expires = time.time() + ttl
                    return cached.body
                delay = 30
                if error.code in (429, 503):
                    retry = error.headers.get('Retry-After', '60')
                    try:
                        delay = max(60, int(retry))
                    except ValueError:
                        try:
                            delay = max(60, parsedate_to_datetime(retry).timestamp() - time.time())
                        except (ValueError, TypeError):
                            delay = 60
                self.blocked_until[host] = time.time() + delay
                raise LookupUnavailable('The provider did not return usable data') from error
            except (OSError, ValueError, EOFError, zlib.error) as error:
                self.blocked_until[host] = time.time() + 30
                raise LookupUnavailable('Could not connect to the provider securely') from error
            finally:
                self.next_request[host] = time.time() + 1
            with self.lock:
                old = self.cache.pop(url, None)
                self.cache_bytes -= len(old.body) if old else 0
                self.cache[url] = Cached(body, expires, last_modified)
                self.cache_bytes += len(body)
                while len(self.cache) > 256 or self.cache_bytes > 64 * 1024 * 1024:
                    _, old = self.cache.popitem(last=False)
                    self.cache_bytes -= len(old.body)
            return body

    def json(self, url, **kwargs):
        try:
            return json.loads(self.get(url, **kwargs))
        except (ValueError, UnicodeError) as error:
            raise LookupUnavailable('The provider did not return JSON') from error


NETWORK = Network()
