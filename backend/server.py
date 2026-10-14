#!/usr/bin/env python3
"""PyLocal Studio backend: stdlib-only HTTP server that runs code with the local Python.
API (all /api/* need the X-Token header, or ?token= for the SSE stream):
  GET  /api/info | /api/examples | /api/examples/<file>
  POST /api/run {code} -> {id} ; GET /api/stream/<id> (SSE) ; POST /api/input/<id> {text|eof} ; POST /api/stop/<id>
"""
import codecs, json, os, re, secrets, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONT, EXAMPLES, WS = (os.path.join(ROOT, d) for d in ("frontend", "examples", "workspace"))
HOST = os.environ.get("PYLOCAL_HOST", "127.0.0.1")
PORT = int(os.environ.get("PYLOCAL_PORT", "8000"))
TIMEOUT = int(os.environ.get("PYLOCAL_TIMEOUT", "300"))      # max wall-clock seconds per run
MEM_MB = int(os.environ.get("PYLOCAL_MEMORY_MB", "1024"))    # address-space cap (POSIX only, 0 = off)
MAX_OUT = 5 * 1024 * 1024                                    # kill runaway output
WIN = os.name == "nt"
TOKEN = secrets.token_urlsafe(24)                            # blocks other websites from calling the API
LOCAL = ("127.0.0.1", "localhost", "::1")

# POSIX-only launcher: applies resource limits, then replaces itself with the user's script.
LAUNCH = """import os,sys,resource as r
def L(k,v):
    try: r.setrlimit(k,(v,v))
    except Exception: pass
m=int(sys.argv[1])
if m: L(r.RLIMIT_AS,m<<20)
L(r.RLIMIT_CORE,0); L(r.RLIMIT_FSIZE,100<<20)
os.execv(sys.executable,[sys.executable,'-u','main.py'])"""

SESSIONS, LOCK = {}, threading.Lock()


class Session:
    def __init__(self, code):
        self.events, self.cv = [], threading.Condition()
        self.done, self.reason, self.out, self.t0 = False, None, 0, time.time()
        os.makedirs(WS, exist_ok=True)
        with open(os.path.join(WS, "main.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        cmd = [sys.executable, "-u", "main.py"] if WIN else [sys.executable, "-c", LAUNCH, str(MEM_MB)]
        kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if WIN else {"start_new_session": True}
        self.proc = subprocess.Popen(cmd, cwd=WS, env=env, bufsize=0, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)
        self.readers = [threading.Thread(target=self.pump, args=(self.proc.stdout, "out"), daemon=True),
                        threading.Thread(target=self.pump, args=(self.proc.stderr, "err"), daemon=True)]
        for t in self.readers:
            t.start()
        threading.Thread(target=self.watch, daemon=True).start()

    def push(self, **ev):
        with self.cv:
            self.events.append(ev)
            self.cv.notify_all()

    def pump(self, stream, kind):
        dec = codecs.getincrementaldecoder("utf-8")("replace")
        while True:
            b = stream.read(4096)  # raw pipe: returns as soon as any bytes (e.g. an input() prompt) arrive
            if not b:
                break
            self.out += len(b)
            txt = dec.decode(b)
            if kind == "err":  # show 'main.py' instead of the absolute workspace path in tracebacks
                txt = txt.replace(os.path.join(WS, "main.py"), "main.py")
            self.push(t=kind, d=txt)
            if self.out > MAX_OUT:
                self.kill("output-limit")
                break

    def watch(self):
        try:
            self.proc.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            self.kill("timeout")
            self.proc.wait()
        for t in self.readers:
            t.join(2)
        self.done = True
        self.push(t="exit", code=self.proc.returncode, reason=self.reason or "finished",
                  secs=round(time.time() - self.t0, 2))

    def kill(self, reason):
        if self.reason is None and self.proc.poll() is None:
            self.reason = reason
        try:
            if WIN:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], capture_output=True)
            else:
                import signal
                os.killpg(self.proc.pid, signal.SIGKILL)
        except Exception:
            pass

    def write(self, text=None, eof=False):
        try:
            if eof:
                self.proc.stdin.close()
            else:
                self.proc.stdin.write(text.encode("utf-8"))
                self.proc.stdin.flush()
            return True
        except (OSError, ValueError):
            return False


def active():
    return any(not s.done for s in SESSIONS.values())


class Handler(BaseHTTPRequestHandler):
    server_version = "PyLocalStudio"

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def guard(self, q):
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        if HOST in LOCAL and host not in LOCAL:
            self.send(403, {"error": "bad host"})          # DNS-rebinding defence
            return False
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            self.send(403, {"error": "bad origin"})
            return False
        if self.path.startswith("/api/"):
            tok = self.headers.get("X-Token") or (q.get("token") or [""])[0]
            if not secrets.compare_digest(tok, TOKEN):
                self.send(403, {"error": "bad token"})
                return False
        return True

    def do_GET(self):
        u = urlparse(self.path)
        q, p = parse_qs(u.query), u.path
        if not self.guard(q):
            return
        if p in ("/", "/index.html"):
            with open(os.path.join(FRONT, "index.html"), encoding="utf-8") as f:
                html = f.read().replace("__TOKEN__", TOKEN)
            return self.send(200, html.encode(), "text/html; charset=utf-8")
        if p == "/api/info":
            return self.send(200, {"python": sys.version.split()[0], "timeout": TIMEOUT,
                                   "workspace": WS, "platform": sys.platform})
        if p == "/api/examples":
            out = []
            for n in sorted(os.listdir(EXAMPLES)):
                if n.endswith(".py"):
                    with open(os.path.join(EXAMPLES, n), encoding="utf-8") as f:
                        first = f.readline()
                    out.append({"file": n, "title": first.lstrip("# ").strip() or n})
            return self.send(200, out)
        m = re.fullmatch(r"/api/examples/([\w\-]+\.py)", p)
        if m and os.path.isfile(os.path.join(EXAMPLES, m[1])):
            with open(os.path.join(EXAMPLES, m[1]), encoding="utf-8") as f:
                return self.send(200, {"code": f.read()})
        m = re.fullmatch(r"/api/stream/(\w+)", p)
        if m and m[1] in SESSIONS:
            return self.stream(SESSIONS[m[1]])
        self.send(404, {"error": "not found"})

    def stream(self, s):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        i = 0
        try:
            while True:
                with s.cv:
                    if i >= len(s.events):
                        s.cv.wait(10)
                    batch, i = s.events[i:], len(s.events)
                if not batch:
                    self.wfile.write(b": keepalive\n\n")
                for ev in batch:
                    self.wfile.write(b"data: " + json.dumps(ev).encode() + b"\n\n")
                self.wfile.flush()
                if batch and batch[-1]["t"] == "exit":
                    return
        except (OSError, ValueError):
            if not s.done:
                s.kill("disconnected")   # tab closed/reloaded: don't leave orphan processes

    def do_POST(self):
        p = urlparse(self.path).path
        if not self.guard({}):
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 2_000_000:
                return self.send(413, {"error": "payload too large"})
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self.send(400, {"error": "invalid JSON"})
        if p == "/api/run":
            code = body.get("code")
            if not isinstance(code, str):
                return self.send(400, {"error": "'code' must be a string"})
            with LOCK:
                if active():
                    return self.send(409, {"error": "A program is already running. Stop it first."})
                for k in [k for k, v in SESSIONS.items() if v.done]:
                    del SESSIONS[k]
                try:
                    sid = secrets.token_hex(8)
                    SESSIONS[sid] = Session(code)
                except Exception as e:
                    return self.send(500, {"error": f"Could not start Python: {e}"})
            return self.send(200, {"id": sid})
        m = re.fullmatch(r"/api/(input|stop)/(\w+)", p)
        s = SESSIONS.get(m[2]) if m else None
        if not s:
            return self.send(404, {"error": "no such session"})
        if m[1] == "stop":
            s.kill("stopped")
            return self.send(200, {"ok": True})
        ok = s.write(None, True) if body.get("eof") else s.write(str(body.get("text", "")))
        self.send(200 if ok else 410, {"ok": ok})


def main():
    try:
        srv = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        sys.exit(f"Cannot listen on {HOST}:{PORT} ({e}). Set PYLOCAL_PORT to another port.")
    srv.daemon_threads = True
    if HOST not in LOCAL:
        print("WARNING: bound to a non-local address. Anyone who can reach it can run code as you!")
    print(f"PyLocal Studio on http://localhost:{PORT}  (Python {sys.version.split()[0]})  Ctrl+C to stop")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
