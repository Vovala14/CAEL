"""CAEL local chat UI (stdlib only): python cael_assistant/web_ui.py  ->  open http://127.0.0.1:8765
Avatar: idle image normally; while the assistant is thinking/generating it swaps to the subtle thinking loop, then back.
Supports 2 concurrent browsers: per-tab sessionStorage history; no global chat lock (GPU lock in chat.py)."""
import json, sys, threading, mimetypes, argparse
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parent))  # Shared reviewed network helpers for direct-script launches.
from chat import Assistant
import spellfix
FEED = {}; FEED_LOCK = threading.Lock(); FEEDBACK = HERE.parent / 'research' / 'image_feedback.jsonl'
ASSETS = HERE / 'assets'; OUT = (HERE / 'outputs').resolve()
A = None; TOKEN = None  # no global respond lock: chat relay is concurrent; GPU work locks inside chat.py
# ---- chat relay: a remote worker (the v6.15 chat stack on the box) long-polls /relay/next and posts /relay/done.
import queue, uuid, time
RELAY_KEY = (HERE / 'relay_key.txt').read_text(encoding='utf-8').strip() if (HERE / 'relay_key.txt').exists() else None
JOBS = queue.Queue(); WAIT = {}; LAST_POLL = [0.0]; WAIT_LOCK = threading.Lock()
def relay(messages, timeout=90):
    if time.time() - LAST_POLL[0] > 90:
        return dict(route='chat-unavailable', response="The chat worker isn't connected right now. I can still make emoji and small portraits.")
    jid = uuid.uuid4().hex; ev = threading.Event()
    with WAIT_LOCK: WAIT[jid] = [ev, None]
    JOBS.put(dict(id=jid, messages=messages[-6:]))
    if not ev.wait(timeout):
        with WAIT_LOCK: WAIT.pop(jid, None)
        return dict(route='chat-timeout', response='The chat worker took too long. Please try again.')
    with WAIT_LOCK: slot = WAIT.pop(jid, None)
    return (slot[1] if slot and slot[1] is not None else dict(route='chat-empty', response='No reply from chat worker.'))
PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="theme-color" content="#0f1115"><title>CAEL</title><style>
body{font:15px system-ui,sans-serif;margin:0;background:#0f1115;color:#e6e6e6;display:flex;flex-direction:column;height:100vh;height:100dvh}
header{display:flex;align-items:center;gap:10px;padding:calc(8px + env(safe-area-inset-top)) 14px 8px;border-bottom:1px solid #222}
#av{flex:0 0 auto;align-self:center;width:36px;height:36px;border-radius:50%;object-fit:cover;background:#000;box-shadow:0 0 0 1px #333;transition:box-shadow .3s}
#av.on{animation:aura 1.4s ease-in-out infinite;-webkit-animation:aura 1.4s ease-in-out infinite}
@keyframes aura{0%,100%{box-shadow:0 0 3px 1px rgba(90,160,255,.45)}50%{box-shadow:0 0 14px 5px rgba(120,190,255,.95)}}
@-webkit-keyframes aura{0%,100%{box-shadow:0 0 3px 1px rgba(90,160,255,.45)}50%{box-shadow:0 0 14px 5px rgba(120,190,255,.95)}}
#st{font-size:12px;color:#8a8f98;margin-left:8px}
#log{flex:1;overflow:auto;padding:14px}
.m{max-width:min(760px,88%);word-wrap:break-word;margin:6px 0;padding:8px 12px;border-radius:10px;white-space:pre-wrap;line-height:1.4}
.u{background:#1f3b5c;margin-left:auto}.c{background:#1a1d24}.r{font-size:11px;color:#777;margin-top:4px}
.m img{width:min(128px,40vw);height:auto;aspect-ratio:1;image-rendering:pixelated;margin:4px 4px 0 0;border-radius:4px}
form{display:flex;gap:8px;padding:10px 14px calc(10px + env(safe-area-inset-bottom));border-top:1px solid #222}
input{flex:1;min-height:44px;font-size:16px;padding:9px 12px;border-radius:8px;border:1px solid #333;background:#15181e;color:#eee}
details{margin-top:6px;font-size:12px;color:#8a8f98}summary{cursor:pointer;min-height:28px}
.bx{display:flex;gap:8px;margin-top:6px;flex-wrap:wrap}.bx button{min-height:40px;min-width:80px;font-size:15px}
button{min-height:44px;min-width:64px;font-size:16px;padding:9px 16px;border-radius:8px;border:0;background:#2d6cdf;color:#fff}button:disabled{opacity:.5}
</style></head><body>
<header><b>CAEL</b><span id="st">idle</span></header>
<div id="log"></div>
<form id="f"><img id="av" src="/assets/avatar_idle.jpg" alt="" aria-hidden="true"><input id="q" placeholder='Ask something, or "make an emoji of fire"' autofocus><button id="b">Send</button></form>
<script>
const IDLE='/assets/avatar_idle.jpg', THINK='/assets/avatar_think_loop.gif', THINK_STILL='/assets/avatar_think.jpg';
new Image().src=THINK; new Image().src=THINK_STILL;
(function(){ const p=new URLSearchParams(location.search); const k=p.get('k'); if(k){ try{ sessionStorage.setItem('cael_k', k); }catch(e){}
  if(location.pathname==='/' || location.pathname==='/index.html'){ history.replaceState(null,'', '/'); } } })();
function authKey(){ try{ return sessionStorage.getItem('cael_k')||''; }catch(e){ return ''; } }
function apiUrl(path){ const k=authKey(); return path + (k ? ((path.indexOf('?')>=0?'&':'?')+'k='+encodeURIComponent(k)) : ''); }
const av=document.getElementById('av'), st=document.getElementById('st'), log=document.getElementById('log');
let hist=[]; try{ hist=JSON.parse(sessionStorage.getItem('cael_hist')||'[]')||[]; }catch(e){ hist=[]; }
function saveHist(){ try{ sessionStorage.setItem('cael_hist', JSON.stringify(hist.slice(-40))); }catch(e){} }
hist.forEach(m=>{ if(m.role==='user'){ const d=document.createElement('div'); d.className='m u'; d.textContent=m.content; log.appendChild(d);}
  else if(m.role==='assistant'){ const d=document.createElement('div'); d.className='m c'; d.textContent=(m.content||'').split('\n').filter(l=>!/\.png$/i.test(l.trim())).join('\n'); log.appendChild(d);} });
if(hist.length) log.scrollTop=log.scrollHeight;
av.onerror=()=>{ if(av.src.endsWith('.gif')) av.src=THINK_STILL; };
function think(on){ av.src = on ? THINK : IDLE; av.classList.toggle('on', !!on); st.textContent = on ? 'thinking…' : 'idle'; document.getElementById('b').disabled=on; }
function add(cls, text, imgs, route, extra){ const d=document.createElement('div'); d.className='m '+cls; d.textContent=text;
  (imgs||[]).forEach(u=>{const i=document.createElement('img'); i.src=u; d.appendChild(i);});
  if(extra&&extra.note){const nn=document.createElement('div'); nn.className='r'; nn.textContent=extra.note; d.insertBefore(nn, d.firstChild);}
  if(extra&&extra.choices){const bx=document.createElement('div'); bx.className='bx'; extra.choices.forEach(ch=>{const bb=document.createElement('button'); bb.type='button'; bb.textContent=ch.label; bb.onclick=()=>{ bx.querySelectorAll('button').forEach(x=>x.disabled=true); send(ch.text, true); }; bx.appendChild(bb);}); d.appendChild(bx);}
  if(extra&&extra.feedback){const q2=document.createElement('div'); q2.textContent=extra.feedback.question; d.appendChild(q2); const bx=document.createElement('div'); bx.className='bx';
    [['left','Left'],['right','Right']].forEach(([v,l])=>{const bb=document.createElement('button'); bb.type='button'; bb.textContent=l; bb.onclick=async()=>{ bx.querySelectorAll('button').forEach(x=>x.disabled=true);
      try{ const r=await fetch(apiUrl('/api/feedback'),{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify({id:extra.feedback.id,choice:v}),credentials:'same-origin'}); const o=await readJson(r); add('c', o.response||'Thanks!'); }
      catch(err){ add('c','Error: '+err.message); } }; bx.appendChild(bb);}); d.appendChild(bx);}
  if(extra&&extra.details){const dt=document.createElement('details'); const sm=document.createElement('summary'); sm.textContent='details'; dt.appendChild(sm); const dv=document.createElement('div'); dv.className='r'; dv.style.whiteSpace='pre-wrap'; dv.textContent=extra.details; dt.appendChild(dv); d.appendChild(dt);}
  if(route){const r=document.createElement('div'); r.className='r'; r.textContent='['+route+']'; d.appendChild(r);}
  log.appendChild(d); log.scrollTop=log.scrollHeight; }
async function readJson(r){
  const raw = await r.text();
  if(!raw) throw new Error('Empty reply (HTTP '+r.status+')');
  try{ return JSON.parse(raw); }
  catch(e){ throw new Error('Bad JSON (HTTP '+r.status+'): '+raw.slice(0,120)); }
}
async function send(t, nofix){ add('u', t); hist.push({role:'user',content:t}); saveHist(); think(true);
  try{ const r=await fetch(apiUrl('/api/chat'),{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify({messages:hist.slice(-6),nofix:!!nofix}),credentials:'same-origin'});
       const o=await readJson(r); const txt=(o.response||'').split('\n').filter(l=>!/\.png$/i.test(l.trim())).join('\n');
       if(o.corrected){ hist[hist.length-1].content=o.corrected; }
       add('c', txt, o.images, o.route, {note:o.note, choices:o.choices, feedback:o.feedback, details:o.details});
       if(o.route!=='spell/ask'){ hist.push({role:'assistant',content:o.response||''}); } else { hist.pop(); } saveHist(); }
  catch(err){ add('c','Error: '+err.message); } finally{ think(false); } }
document.getElementById('f').onsubmit=e=>{ e.preventDefault(); const q=document.getElementById('q'); const t=q.value.trim(); if(!t) return; q.value=''; send(t, false); };
</script></body></html>"""
class H(BaseHTTPRequestHandler):
    def log_message(s, *a): pass
    def pure(s):
        return urlparse(s.path).path
    def qs(s):
        return parse_qs(urlparse(s.path).query)
    def send(s, code, body, ctype):
        if isinstance(body, str): body = body.encode('utf-8')
        s.send_response(code); s.send_header('Content-Type', ctype); s.send_header('Content-Length', str(len(body)))
        s.send_header('Cache-Control', 'no-store'); s.end_headers(); s.wfile.write(body)
    def send_json(s, code, obj):
        s.send(code, json.dumps(obj, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')
    def set_auth_cookie(s):
        if not TOKEN: return
        parts = [f'cael_k={TOKEN}', 'Path=/', 'HttpOnly', 'SameSite=Lax', 'Max-Age=31536000']
        if s.headers.get('X-Forwarded-Proto') == 'https': parts.append('Secure')
        s.send_header('Set-Cookie', '; '.join(parts))
    def ok(s):
        if not TOKEN: return True
        q = s.qs().get('k', [''])[0]; c = s.headers.get('Cookie', '')
        return q == TOKEN or f'cael_k={TOKEN}' in c
    def rk(s): return RELAY_KEY and s.headers.get('X-CAEL-Relay') == RELAY_KEY
    def do_GET(s):
        path = s.pure()
        if path == '/relay/next' and s.rk():
            LAST_POLL[0] = time.time()
            try: j = JOBS.get(timeout=5)
            except queue.Empty: return s.send(200, b'{"idle":true}', 'application/json; charset=utf-8')
            try: return s.send(200, json.dumps(j).encode(), 'application/json; charset=utf-8')
            except Exception: JOBS.put(j); return
        if not s.ok():
            if path.startswith('/api/'): return s.send_json(403, dict(response='forbidden: open the URL with ?k=<token>', route='auth', images=[]))
            return s.send(403, '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><body style="font:17px system-ui;background:#0f1115;color:#eee;padding:24px"><h3>CAEL</h3><p>This link is missing its access key. Please ask Gleeb for the <b>full link</b> (it ends in <code>?k=…</code>). After opening it once, this browser remembers you for a year.</p></body>', 'text/html; charset=utf-8')
        if path in ('/', '/index.html'):
            s.send_response(200); s.set_auth_cookie()
            body = PAGE.encode('utf-8')
            s.send_header('Content-Type', 'text/html; charset=utf-8'); s.send_header('Content-Length', str(len(body)))
            s.send_header('Cache-Control', 'no-store'); s.end_headers(); s.wfile.write(body); return
        if path.startswith('/assets/'):
            p = (ASSETS / Path(path[8:]).name)
            if p.is_file(): return s.send(200, p.read_bytes(), mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
        if path.startswith('/out/'):
            p = (OUT / path[5:]).resolve()
            if p.is_file() and OUT in p.parents: return s.send(200, p.read_bytes(), 'image/png')
        s.send(404, b'not found', 'text/plain')
    def do_POST(s):
        path = s.pure()
        if path == '/relay/done' and s.rk():
            o = json.loads(s.rfile.read(int(s.headers.get('Content-Length', 0) or 0)))
            with WAIT_LOCK:
                if o.get('id') in WAIT: WAIT[o['id']][1] = dict(response=o.get('response', ''), route=o.get('route')); WAIT[o['id']][0].set()
            return s.send(200, b'ok', 'text/plain')
        if path == '/api/feedback':
            if not s.ok(): return s.send_json(403, dict(response='forbidden', route='auth', images=[]))
            try:
                o = json.loads(s.rfile.read(int(s.headers.get('Content-Length', 0) or 0)) or b'{}')
                with FEED_LOCK: ctx = FEED.pop(str(o.get('id')), None)
                if ctx is None: return s.send_json(200, dict(response='Thanks! (that choice was already recorded)', route='feedback/dup', images=[]))
                ch = 'left' if o.get('choice') == 'left' else 'right'
                rec = dict(ctx, choice=ch, chosen_image=ctx['images'][0 if ch == 'left' else 1] if len(ctx['images']) == 2 else None, ts=time.strftime('%Y-%m-%dT%H:%M:%S%z'))
                with FEED_LOCK:
                    with open(FEEDBACK, 'a', encoding='utf-8') as f: f.write(json.dumps(rec, ensure_ascii=False) + '\n')
                return s.send_json(200, dict(response=f'Thanks, noted: the {ch} one.', route='feedback/logged', images=[]))
            except Exception as e:
                return s.send_json(400, dict(response=f'bad feedback: {type(e).__name__}', route='error', images=[]))
        if path != '/api/chat':
            return s.send_json(404, dict(response='not found', route='error', images=[]))
        if not s.ok():
            return s.send_json(403, dict(response='forbidden: open the full link with ?k=… (same link for both phones)', route='auth', images=[]))
        try:
            raw = s.rfile.read(int(s.headers.get('Content-Length', 0) or 0))
            msgs = json.loads(raw or b'{}').get('messages', [])
        except Exception as e:
            return s.send_json(400, dict(response=f'bad request: {type(e).__name__}', route='error', images=[]))
        body0 = json.loads(raw or b'{}'); note = None; corrected = None
        try:
            if msgs and msgs[-1].get('role') == 'user' and not body0.get('nofix'):
                fx = spellfix.get().fix(str(msgs[-1].get('content', '')))
                if fx['ambiguous']:
                    am = fx['ambiguous']
                    return s.send_json(200, dict(response=f'Did you mean "{am["options"][0]}" or "{am["options"][1]}"?', route='spell/ask', images=[],
                                                 choices=[dict(label=o_, text=t_) for o_, t_ in zip(am['options'], am['texts'])]))
                if fx['changed']:
                    corrected = fx['text']; msgs[-1] = dict(msgs[-1], content=corrected)
                    note = 'I read that as "' + corrected + '".'
        except Exception as e:
            note = None
        try:
            o = A.respond(msgs) or {}
            imgs = []
            for p in o.get('paths') or []:
                try: imgs.append('/out/' + Path(p).resolve().relative_to(OUT).as_posix())
                except ValueError: pass
            body = dict(response=str(o.get('response', '')), route=o.get('route'), images=imgs)
            if note: body['note'] = note; body['corrected'] = corrected
            if o.get('details'): body['details'] = str(o['details'])
            if len(imgs) == 2 and str(o.get('route', '')).endswith('/generated'):
                tool = o.get('tool') or {}; fid = uuid.uuid4().hex[:12]
                model = tool.get('model') or ('cael-emoji-64-v5' if str(o.get('route')).startswith('emoji') else 'cael-image-female-64-v10-i16')
                with FEED_LOCK: FEED[fid] = dict(prompt=msgs[-1].get('content', ''), subject=o.get('subject') or o.get('caption'), model=model,
                                                 seed=tool.get('seed'), route=o.get('route'), images=[str(p) for p in (o.get('paths') or [])])
                body['feedback'] = dict(id=fid, question='Which came out better?')
        except Exception as e:
            body = dict(response=f'Error: {type(e).__name__}: {e}', route='error', images=[])
        s.send_json(200, body)
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--host', default='127.0.0.1', help='0.0.0.0 = reachable from LAN (phone); then a token is required')
    ap.add_argument('--token', default=None); a = ap.parse_args()
    import secrets; TOKEN = a.token or (secrets.token_urlsafe(12) if a.host != '127.0.0.1' else None)
    if TOKEN: print(f'access token: {TOKEN}  (open http://<this-pc>:{a.port}/?k={TOKEN})', flush=True)
    A = Assistant()
    if RELAY_KEY and A.v67 is None: A.remote_fn = relay; A.v67_err = None
    print(f'CAEL UI on http://127.0.0.1:{a.port}  (chat backend: {"on" if A.v67 else "off: " + str(A.v67_err)})', flush=True)
    ThreadingHTTPServer((a.host, a.port), H).serve_forever()
