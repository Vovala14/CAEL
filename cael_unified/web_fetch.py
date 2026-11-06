"""Bounded read-only public HTTP text fetches. No generated/untrusted code runs.

Resolve once, reject nonpublic addresses, connect to that numeric address while
retaining TLS hostname verification. Check every redirect. Never forward private
URLs through a remote reader. This is a page reader, not a general browser.
"""
from datetime import datetime,timezone
from html.parser import HTMLParser
import http.client,ipaddress,re,socket,ssl,time,threading
from urllib.parse import urlparse,urljoin,parse_qsl,quote

MAX_BYTES=1_000_000
MAX_TEXT=120_000
UA='CAEL/0.3.9-conversation (+https://github.com/Vovala14/CAEL; non-neural)'
DNS_SLOTS=threading.BoundedSemaphore(4)
class Blocked(ValueError):pass
class Text(HTMLParser):
    SKIP={'script','style','nav','footer','header','aside','form','noscript','svg','template'}
    def __init__(self):super().__init__();self.parts=[];self.depth=0
    def handle_starttag(self,tag,attrs):
        if tag in self.SKIP:self.depth+=1
        elif not self.depth and tag in {'p','br','li','h1','h2','h3','tr','div','section'}:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in self.SKIP and self.depth:self.depth-=1
        elif not self.depth and tag in {'p','li','h1','h2','h3','tr','div','section'}:self.parts.append('\n')
    def handle_data(self,data):
        if not self.depth:self.parts.append(re.sub(r'\s+',' ',data))
def resolve_addresses(host,port,timeout):
    if not DNS_SLOTS.acquire(blocking=False):raise Blocked('Public DNS reader is busy')
    done=threading.Event();result=[];errors=[]
    def run():
        try:result.extend(socket.getaddrinfo(host,port,type=socket.SOCK_STREAM))
        except OSError as e:errors.append(type(e).__name__)
        finally:DNS_SLOTS.release();done.set()
    threading.Thread(target=run,daemon=True,name='cael-public-dns').start()
    if not done.wait(max(.01,min(2,float(timeout)))):raise Blocked('Public DNS lookup timed out')
    if errors:raise Blocked('Public hostname could not be resolved')
    return {x[4][0].split('%')[0] for x in result}
def destination(url,timeout=2):
    try:p=urlparse(url);port=p.port
    except (ValueError,TypeError):raise Blocked('Invalid public URL')
    if (p.scheme not in ('http','https') or not p.hostname or p.username or p.password
        or port not in (None,443 if p.scheme=='https' else 80) or len(url)>2048):raise Blocked('Unsupported public URL')
    if any(re.search(r'(?i)token|secret|password|signature|credential|api.?key|authorization',k) for k,v in parse_qsl(p.query)):
        raise Blocked('A URL containing credentials is not sent to a lookup service')
    host=p.hostname.encode('idna').decode()
    try:addresses=resolve_addresses(host,port or (443 if p.scheme=='https' else 80),timeout)
    except (OSError,UnicodeError):raise Blocked('Public hostname could not be resolved')
    if not addresses or not all(ipaddress.ip_address(x).is_global for x in addresses):raise Blocked('Only public internet addresses can be read')
    return p,host,sorted(addresses,key=lambda value:(':' in value,value))[0]
class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,ip,timeout):super().__init__(host,timeout=timeout,context=ssl.create_default_context());self.ip=ip
    def connect(self):
        sock=socket.create_connection((self.ip,self.port),self.timeout)
        try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except BaseException:sock.close();raise
class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self,host,ip,timeout):super().__init__(host,timeout=timeout);self.ip=ip
    def connect(self):self.sock=socket.create_connection((self.ip,self.port),self.timeout)
def fetch(url,timeout=6):
    started=time.monotonic();deadline=started+min(max(float(timeout),.1),10);original=url
    result={'requested_url':url,'url':url,'status':'error','text':'','fetched_at':datetime.now(timezone.utc).isoformat(),'bytes':0,'text_truncated':False}
    for redirect in range(3):
        connection=None
        try:
            p,host,ip=destination(url,deadline-time.monotonic());remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('Read deadline')
            connection=(PinnedHTTPS if p.scheme=='https' else PinnedHTTP)(host,ip,remaining)
            path=quote(p.path or '/',safe='/%:@-._~!$&\'()*+,;=')+('?' + p.query if p.query else '')
            connection.request('GET',path,headers={'User-Agent':UA,'Accept':'text/html,text/plain,application/xhtml+xml','Accept-Encoding':'identity','Connection':'close'})
            transport=connection.sock;response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location or redirect==2:raise Blocked('Redirect bound exceeded')
                url=urljoin(url,location);continue
            if response.status!=200:return {**result,'status':'unavailable','http_status':response.status,'url':url}
            kind=response.getheader('Content-Type','').split(';')[0].casefold()
            if kind not in ('text/html','text/plain','application/xhtml+xml'):return {**result,'status':'unsupported_type','url':url}
            if response.getheader('Content-Encoding','identity') not in ('identity',''):return {**result,'status':'unsupported_encoding','url':url}
            body=bytearray()
            while len(body)<=MAX_BYTES:
                # A length-delimited response closes its file/socket as soon as
                # read1 consumes the final byte. Do not set a timeout on that
                # closed socket just to make a redundant EOF read (Windows).
                if getattr(response,'isclosed',lambda:False)():break
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('Read deadline')
                if transport:transport.settimeout(remaining)
                chunk=response.read1(min(65536,MAX_BYTES+1-len(body)))
                if not chunk:break
                body.extend(chunk)
            if len(body)>MAX_BYTES:return {**result,'status':'too_large','bytes':len(body),'url':url}
            charset=response.headers.get_content_charset() or 'utf-8'
            if charset.casefold().replace('_','-') not in ('utf-8','utf8','iso-8859-1','latin-1','windows-1252'):charset='utf-8'
            text=body.decode(charset,errors='replace')
            if kind!='text/plain':parser=Text();parser.feed(text);text=''.join(parser.parts)
            text=re.sub(r'[ \t]+',' ',text);text=re.sub(r'\n\s*\n+','\n',text).strip()
            return {**result,'status':'read' if text else 'empty','url':url,'bytes':len(body),'text':text[:MAX_TEXT],
                    'text_truncated':len(text)>MAX_TEXT,'seconds':time.monotonic()-started}
        except Blocked as e:return {**result,'status':'blocked','reason':str(e),'url':url}
        except (OSError,ValueError,http.client.HTTPException) as e:return {**result,'status':'error','reason':type(e).__name__,'error_number':getattr(e,'errno',None),'url':url}
        finally:
            if connection:connection.close()
    return result
