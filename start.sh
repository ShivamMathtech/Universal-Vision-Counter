#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  setup_python="$(command -v python3.12 || command -v python3.11 || command -v python3)"
  "$setup_python" scripts/setup.py
fi
exec .venv/bin/python scripts/run.py "$@"
