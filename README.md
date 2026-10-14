# PyLocal Studio

Browser-based Python editor and terminal that runs your code with the **real Python installed on your computer**.
Pure standard library on both sides: no pip packages, no CDN, no external API. Works fully offline.

## Architecture (and why)
Native Python + a tiny local backend (`backend/server.py`, stdlib `http.server`), chosen over Pyodide for full
standard-library and installed-package compatibility.
- `Run` → backend writes `workspace/main.py`, starts `python -u main.py` as a child process (own process group).
- Output streams to the browser over Server-Sent Events (stdout and stderr separately); `input()` text is POSTed to the
  process's stdin. Everything is threaded, so neither the server nor the UI blocks.
- `Stop` kills the whole process tree. A 300 s time limit, a 5 MB output cap and (Linux/macOS) memory/file-size limits apply.
- The editor is a custom textarea + syntax-highlight overlay (`frontend/index.html`), so there are no editor assets to download.

## Requirements
Python **3.8+** (python.org). Nothing else to install; `requirements.txt` is intentionally empty.

## Launch
- **Windows:** double-click `run.bat` (or `py -3 backend\server.py`).
- **Linux / macOS:** `./run.sh` (or `python3 backend/server.py`).
- Open **http://localhost:8000**. Stop the server with **Ctrl+C** (closing the window on Windows).
- Another port: `PYLOCAL_PORT=9000 ./run.sh` (Windows: `set PYLOCAL_PORT=9000` first).
- Other settings: `PYLOCAL_TIMEOUT` (seconds), `PYLOCAL_MEMORY_MB` (0 = off).

### Offline
After Python is installed, no internet is ever used; disconnect and launch as normal. The page must be opened through the
server (`http://localhost:8000`), **not** by double-clicking `index.html`: a plain file cannot run native Python, and the
page needs the server's API and security token. (A `file://` page has no backend; a local server is what executes code.)

## Using it
Ctrl+Enter runs · Ctrl+S saves in this browser · Ctrl+/ comments · Tab / Shift+Tab indent. Type program input in the
`stdin ›` bar (Enter sends, Ctrl+D ends input). Download/Open handle `.py` files; the draft is auto-kept between visits;
unsaved changes trigger a warning on leaving. Files your programs create appear in `workspace/`.

## Security — read this
Your code runs **as your OS user with your permissions** (it can read/write your files and use the network). Resource
limits and the timeout are safety nets, **not a sandbox**. Mitigations: server binds to `127.0.0.1` only; per-launch
API token; Host/Origin checks (CSRF and DNS-rebinding defence); one program at a time; no privileged operations.
Do not run as root/Administrator. For untrusted code use a container/VM. Never set `PYLOCAL_HOST` to a public address.

## Tests
`python tests/test_backend.py` starts a server and checks: the six required programs, syntax error, empty program, EOF,
all 10 examples (with scripted input), stop, run-after-stop, timeout, output cap, token and Host rejection.

## Known limitations
- Verified by automated tests on the Linux sandbox only. The browser UI was **not** tested in a real browser, and Windows/macOS
  were not tested. Please report issues.
- Editor is intentionally simple: no autocomplete, bracket auto-closing, or multi-file projects. `\r` progress bars print as new lines.
- `input()` echo is drawn by the page (the process sees a pipe, not a TTY), so `getpass` and curses-style programs don't work.
- Memory limits are not enforced on Windows (and may not on macOS).

## Troubleshooting
- *"Python 3.8+ not found"*: install Python; on Windows tick "Add to PATH".
- *"Cannot listen on 127.0.0.1:8000"*: port busy → use `PYLOCAL_PORT`.
- *"Cannot reach the local server"*: the page was opened from a file, or the server stopped.
- *"A program is already running"*: press Stop (or reload the page, which also terminates it).
