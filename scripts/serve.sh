#!/bin/sh
# Start the quote service in the foreground, bound to loopback only.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if [ -x .venv/bin/python ]; then
  PYTHON=.venv/bin/python
else
  PYTHON=python3
fi

mkdir -p logs
export PYTHONUNBUFFERED=1
exec "$PYTHON" -m uvicorn quote_service.api:app --host 127.0.0.1 --port 8080 >>logs/quote_service.log 2>&1
