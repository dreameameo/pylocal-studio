#!/usr/bin/env sh
# Launch PyLocal Studio (Linux/macOS). No internet and no pip install needed.
cd "$(dirname "$0")" || exit 1
for PY in python3 python; do
  if command -v "$PY" >/dev/null 2>&1 && "$PY" -c 'import sys;sys.exit(sys.version_info<(3,8))'; then
    exec "$PY" backend/server.py
  fi
done
echo "Python 3.8+ not found. Install it from https://www.python.org/downloads/ (one-time)."; exit 1
