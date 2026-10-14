"""Run: python tests/test_backend.py  (starts its own server on port 8765; uses the real Python runtime)"""
import json, os, re, subprocess, sys, time, urllib.request, urllib.error
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = "8765"; B = f"http://127.0.0.1:{PORT}"
srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "backend", "server.py")], env=dict(os.environ, PYLOCAL_PORT=PORT, PYLOCAL_TIMEOUT="6"), stdout=subprocess.DEVNULL)
time.sleep(1)
tok = re.search(r'name="tok" content="([^"]+)"', urllib.request.urlopen(B + "/").read().decode())[1]
def call(path, body=None, token=tok):
    r = urllib.request.Request(B + path, data=None if body is None else json.dumps(body).encode(), headers={"X-Token": token})
    try: return json.load(urllib.request.urlopen(r))
    except urllib.error.HTTPError as e: return {"http": e.code, **json.load(e)}
def stream(sid, on_out=None):
    out = err = ""; ex = None
    for line in urllib.request.urlopen(f"{B}/api/stream/{sid}?token={tok}"):
        if not line.startswith(b"data: "): continue
        m = json.loads(line[6:])
        if m["t"] == "out":
            out += m["d"]
            if on_out: on_out(sid, out)
        elif m["t"] == "err": err += m["d"]
        else: ex = m
    return out, err, ex
def run(code, inputs=()):
    sid = call("/api/run", {"code": code})["id"]
    for t in inputs: call(f"/api/input/{sid}", {"text": t + "\n"})
    return stream(sid)
fails = 0
def check(name, cond):
    global fails; fails += not cond; print(("PASS" if cond else "FAIL"), name)
try:
    o, e, x = run('print("Hello, World!")'); check("1 basic output", o.strip() == "Hello, World!" and x["code"] == 0)
    o, e, x = run('name = input("Enter your name: ")\nprint(f"Hello, {name}!")', ["Ada"]); check("2 input() prompt+echo", o == "Enter your name: Hello, Ada!\n")
    o, e, x = run("for i in range(5):\n    print(i)"); check("3 loops", o.split() == list("01234"))
    o, e, x = run("def add(a, b):\n    return a + b\nprint(add(10, 20))"); check("4 functions", o.strip() == "30")
    o, e, x = run("try:\n    result = 10 / 0\nexcept ZeroDivisionError as error:\n    print('Error:', error)"); check("5 exceptions", o.strip() == "Error: division by zero")
    o, e, x = run("print(undefined_variable)"); check("6 runtime error", "NameError" in e and 'File "main.py", line 1' in e and x["code"] == 1)
    o, e, x = run("print(1 +"); check("syntax error", "SyntaxError" in e and x["code"] == 1)
    o, e, x = run(""); check("empty program", x["code"] == 0)
    sid = call("/api/run", {"code": "import sys\nprint(sys.stdin.read().upper())"})["id"]
    call(f"/api/input/{sid}", {"text": "abc\n"}); call(f"/api/input/{sid}", {"eof": True}); o, e, x = stream(sid); check("EOF closes stdin", o.strip() == "ABC")
    for ex in sorted(os.listdir(os.path.join(ROOT, "examples"))):
        ins = {"02": ["6", "*", "7"], "03": ["bob", "30"], "04": ["80"], "10": ["add milk", "list", "quit"]}.get(ex[:2], [])
        o, e, x = run(open(os.path.join(ROOT, "examples", ex)).read(), ins); check("example " + ex, x["code"] == 0 and not e)
    sid = call("/api/run", {"code": "import time\nprint('start', flush=True)\ntime.sleep(60)"})["id"]
    check("409 while running", call("/api/run", {"code": "1"}).get("http") == 409)
    time.sleep(0.7); call(f"/api/stop/{sid}", {}); o, e, x = stream(sid); check("stop/cancel", x["reason"] == "stopped" and "start" in o)
    o, e, x = run("print('again')"); check("run after stop", o.strip() == "again")
    o, e, x = run("while True: pass"); check("timeout kills", x["reason"] == "timeout")
    o, e, x = run("while True: print('x'*1000)"); check("output limit", x["reason"] == "output-limit")
    check("bad token rejected", call("/api/info", token="nope").get("http") == 403)
    r = urllib.request.Request(B + "/api/info", headers={"X-Token": tok, "Host": "evil.com"})
    try: urllib.request.urlopen(r); bad = False
    except urllib.error.HTTPError as ex_: bad = ex_.code == 403
    check("foreign Host rejected", bad)
finally:
    srv.terminate()
print("FAILURES:", fails); sys.exit(1 if fails else 0)
