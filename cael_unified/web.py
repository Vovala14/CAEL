"""Local browser interface; serves generated files only, with isolated histories."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

# Room for a whole chat window (assistant.MAX_CHARACTERS) after JSON escaping.
MAX_REQUEST_BYTES = 4 * 400_000 + 65536

AVATAR_ASSETS = {
    '/assets/avatar_idle.jpg': 'image/jpeg',
    '/assets/avatar_think_loop.gif': 'image/gif',
    '/assets/avatar_think.jpg': 'image/jpeg',
}


def avatar_asset(path):
    """Serve only the three existing UI avatars, never arbitrary local files."""
    content_type = AVATAR_ASSETS.get(path)
    if content_type is None:
        return None
    target = Path(__file__).resolve().parents[1] / 'cael_assistant' / 'assets' / path.rsplit('/', 1)[1]
    return (target.read_bytes(), content_type) if target.is_file() else None

PAGE = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CAEL 0.2.4</title>
<style>*{box-sizing:border-box}body{margin:0;background:#10141c;color:#ecf0f7;font:16px system-ui;display:flex;flex-direction:column;height:100dvh}header{padding:18px;border-bottom:1px solid #333}small{color:#aebacb}#log{flex:1;overflow:auto;padding:18px}.message{white-space:pre-wrap;max-width:900px;margin:10px auto;padding:16px;border-radius:12px;background:#1c2330}.user{background:#203956}.images{display:flex;gap:8px;flex-wrap:wrap}.images img{width:192px;height:192px;image-rendering:pixelated;border-radius:8px}form{padding:16px;display:flex;gap:8px;background:#1b2230}input,select,button{font:inherit;border-radius:8px;border:1px solid #46536b;padding:12px;background:#151b26;color:inherit}#prompt{flex:1;min-width:0}button{background:#426de0;border:0;cursor:pointer}button:disabled{opacity:.5}details{font-size:13px;color:#b4bfce;margin-top:12px}@media(max-width:600px){form{flex-wrap:wrap}#prompt{flex-basis:70%}}</style>
<header><button id="new-chat" type="button" style="float:right;padding:7px 10px;font-size:13px;background:#29354b">New chat</button><b>CAEL <small>0.2.4</small></b><br><small>Chat, helper, emoji and small pictures in one place</small></header><main id="log" aria-live="polite"></main>
<style>#avatar{flex:0 0 36px;width:36px;height:36px;align-self:center;border-radius:50%;object-fit:cover;background:#000}#avatar.thinking{animation:aura 1.4s ease-in-out infinite}@keyframes aura{0%,100%{box-shadow:0 0 3px 1px rgba(90,160,255,.45)}50%{box-shadow:0 0 14px 5px rgba(120,190,255,.95)}}#activity{margin-left:8px;font-size:12px;color:#aebacb}@media(prefers-reduced-motion:reduce){#avatar.thinking{animation:none}}@media(max-width:600px){form{display:grid;grid-template-columns:36px minmax(0,1fr) auto}#mode{grid-column:1/-1;width:100%}#avatar{grid-column:1;grid-row:2}#prompt{grid-column:2;grid-row:2;width:100%}#send{grid-column:3;grid-row:2}}</style>
<style>textarea{font:inherit;border-radius:8px;border:1px solid #46536b;padding:12px;background:#151b26;color:inherit;resize:none;line-height:1.35;max-height:180px;overflow-y:auto}#mode,#send{align-self:end}#prompt{min-height:46px}</style>
<form id="form" aria-busy="false"><img id="avatar" src="/assets/avatar_idle.jpg" alt="" aria-hidden="true" width="36" height="36"><select id="mode" aria-label="Mode"><option value="auto">Auto</option><option value="chat">Chat / helper</option><option value="prompt">Prompt writer</option><option value="story">Story</option><option value="emoji">Emoji</option><option value="image">Picture</option></select><textarea id="prompt" aria-label="Message" placeholder="Ask something, or make a picture of a car" rows="1" required autocomplete="off"></textarea><button id="send">Send</button></form>
<script>const log=document.querySelector('#log'),form=document.querySelector('#form'),input=document.querySelector('#prompt'),button=document.querySelector('#send');let messages=[];
const IDLE='/assets/avatar_idle.jpg',THINK='/assets/avatar_think_loop.gif',THINK_STILL='/assets/avatar_think.jpg',avatar=document.querySelector('#avatar');
const activity=document.createElement('span');activity.id='activity';activity.setAttribute('role','status');activity.setAttribute('aria-live','polite');activity.textContent='Idle';document.querySelector('header').append(activity);
new Image().src=THINK;new Image().src=THINK_STILL;
avatar.addEventListener('error',()=>{const src=avatar.getAttribute('src');if(src===THINK)avatar.src=THINK_STILL;else if(src===THINK_STILL)avatar.src=IDLE});
function fitInput(){input.style.height='auto';input.style.height=Math.min(180,input.scrollHeight+2)+'px'}
input.addEventListener('input',fitInput);
input.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing&&(event.ctrlKey||event.metaKey||window.matchMedia('(pointer: fine)').matches)){event.preventDefault();if(!button.disabled)form.requestSubmit()}});
const newChat=document.querySelector('#new-chat');newChat.addEventListener('click',()=>{if(button.disabled)return;messages=[];log.replaceChildren();input.value='';fitInput();input.focus()});
function setThinking(on){fitInput();const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;avatar.src=on?(reduced?THINK_STILL:THINK):IDLE;avatar.classList.toggle('thinking',on);activity.textContent=on?'Thinking…':'Idle';form.setAttribute('aria-busy',String(on));button.disabled=on;newChat.disabled=on;button.textContent=on?'Working…':'Send'}
function add(text,user=false,images=[],details='',sources=[]){const box=document.createElement('div');box.className='message'+(user?' user':'');const p=document.createElement('div');p.textContent=text;box.append(p);if(images.length){const row=document.createElement('div');row.className='images';for(const src of images){const img=document.createElement('img');img.src=src;img.alt='Generated CAEL image';row.append(img)}box.append(row)}if(sources.length){const row=document.createElement('div');row.style.marginTop='10px';row.style.fontSize='13px';const seen=new Set();for(const source of sources){if(seen.has(source.url)||!/^https?:\/\//i.test(source.url))continue;seen.add(source.url);const a=document.createElement('a');a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';a.style.color='#9dc2ff';a.style.marginRight='12px';a.textContent=source.title||source.source||'Source';row.append(a)}box.append(row)}if(details){const el=document.createElement('details'),s=document.createElement('summary'),p=document.createElement('div');s.textContent='About this result';p.textContent=details;el.append(s,p);box.append(el)}log.append(box);log.scrollTop=log.scrollHeight}
form.addEventListener('submit',async event=>{event.preventDefault();const text=input.value.trim();if(!text)return;add(text,true);messages.push({role:'user',content:text});input.value='';setThinking(true);try{const response=await fetch('/api/respond',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:messages,mode:document.querySelector('#mode').value,n:2})});const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed');add(result.response,false,result.images||[],result.details||'');messages.push({role:'assistant',content:result.response})}catch(error){add(error.message);messages.pop()}finally{setThinking(false);input.focus()}});</script></html>'''


PAGE = PAGE.replace("add(result.response,false,result.images||[],result.details||'')", "add(result.response,false,result.images||[],result.details||'',result.sources||[])")


def handler_for(assistant):
    class Handler(BaseHTTPRequestHandler):
        def local_host(self):
            host = urlparse('http://' + self.headers.get('Host', '')).hostname
            return host in ('127.0.0.1', 'localhost', '::1')

        def log_message(self, *args):
            pass

        def send_json(self, data, status=200):
            body = json.dumps(data).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.local_host():
                self.send_json(dict(error='Local host required'), 403)
                return
            path = urlparse(self.path).path
            if path == '/':
                body = PAGE.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
            elif path in AVATAR_ASSETS:
                asset = avatar_asset(path)
                if asset is None:
                    self.send_json(dict(error='File not found'), 404)
                    return
                body, content_type = asset
                self.send_response(200)
                self.send_header('Content-Type', content_type)
            elif path.startswith('/outputs/'):
                target = (assistant.output_root / unquote(path[len('/outputs/'):])).resolve()
                if not target.is_relative_to(assistant.output_root) or target.suffix.lower() != '.png' or not target.is_file():
                    self.send_json(dict(error='File not found'), 404)
                    return
                body = target.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
            else:
                self.send_json(dict(error='Not found'), 404)
                return
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if not self.local_host():
                self.send_json(dict(error='Local host required'), 403)
                return
            if self.path != '/api/respond':
                self.send_json(dict(error='Not found'), 404)
                return
            origin = self.headers.get('Origin')
            if origin and urlparse(origin).netloc != self.headers.get('Host'):
                self.send_json(dict(error='Cross-origin request rejected'), 403)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_REQUEST_BYTES:
                    raise ValueError('Invalid request length')
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict):
                    raise ValueError('Expected an object')
                result = assistant.respond(request.get('messages'), n=request.get('n', 2),
                                           seed=request.get('seed'), mode=request.get('mode', 'auto'))
                result['images'] = ['/outputs/' + Path(p).resolve().relative_to(assistant.output_root).as_posix() for p in result.get('paths', [])]
                self.send_json(result)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
                self.send_json(dict(error=str(error)), 400)
            except Exception:
                self.send_json(dict(error='The local engine could not complete this request. Check the model bundle and dependencies.'), 500)
    return Handler


def serve(assistant, port=8765):
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(assistant))
    print(f'CAEL 0.2.4: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
