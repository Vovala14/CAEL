"""Start the installed shared worker and a public Cloudflare test link."""
import ctypes
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.request

from .bundle import ROOT, VERSION


def alive(pid):
    if not pid:
        return False
    if sys.platform == 'win32':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return False
        code = ctypes.c_ulong()
        try:
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    import os
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def health(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=2) as response:
            return json.load(response).get('model') == 'CAEL ' + VERSION
    except (OSError, ValueError):
        return False


def main():
    state = ROOT / 'research' / 'shared_021'
    state.mkdir(parents=True, exist_ok=True)
    metadata = state / 'processes.json'
    previous = json.loads(metadata.read_text()) if metadata.exists() else {}
    if alive(previous.get('worker_pid')) and alive(previous.get('tunnel_pid')) and health(previous.get('port')):
        print(previous['url'], flush=True)
        return
    cloudflared = ROOT / 'tools' / ('cloudflared.exe' if sys.platform == 'win32' else 'cloudflared')
    if not cloudflared.is_file():
        raise FileNotFoundError('Install cloudflared in the project tools directory first')
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    stamp = time.strftime('%Y%m%d_%H%M%S', time.gmtime())
    if alive(previous.get('worker_pid')) and health(previous.get('port')):
        worker_pid, port = previous['worker_pid'], previous['port']
    else:
        for port in range(8766, 8786):
            with socket.socket() as sock:
                if sock.connect_ex(('127.0.0.1', port)) != 0:
                    break
        else:
            raise RuntimeError('No free local worker port')
        with (state / f'worker_{stamp}.log').open('wb') as log:
            worker = subprocess.Popen([sys.executable, '-u', '-m', 'cael_unified.public_worker', '--port', str(port), '--state-dir', str(state)],
                                      cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        worker_pid = worker.pid
        for _ in range(60):
            if health(port):
                break
            if worker.poll() is not None:
                raise RuntimeError('Worker exited; read its log in research/shared_021')
            time.sleep(.5)
        else:
            raise RuntimeError('Worker did not become ready')
    tunnel_log = state / f'cloudflared_{stamp}.log'
    with tunnel_log.open('wb') as log:
        tunnel = subprocess.Popen([str(cloudflared), 'tunnel', '--no-autoupdate', '--url', f'http://127.0.0.1:{port}', '--protocol', 'http2'],
                                  cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
    url = None
    for _ in range(120):
        text = tunnel_log.read_text(encoding='utf-8', errors='replace')
        match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', text)
        if match:
            url = match[0]
            break
        if tunnel.poll() is not None:
            raise RuntimeError('Tunnel exited; read its log in research/shared_021')
        time.sleep(.5)
    if not url:
        raise RuntimeError('Tunnel did not return a public URL')
    link = dict(url=url)
    temporary = state / 'link.tmp'
    temporary.write_text(json.dumps(link), encoding='utf-8')
    temporary.replace(state / 'link.json')
    record = dict(worker_pid=worker_pid, tunnel_pid=tunnel.pid, port=port, url=url,
                  tunnel_log=str(tunnel_log), model='CAEL ' + VERSION, user_cap=None,
                  note='Temporary public link; PC and tunnel processes must remain running')
    metadata.write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(url, flush=True)


if __name__ == '__main__':
    main()
