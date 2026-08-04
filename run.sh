#!/usr/bin/env bash
# Launcher for ZCode Auto Clicker.
# Strips leaked PYTHONHOME/PYTHONPATH (from some AppImage hosts) and runs the
# bundled virtualenv. Creates the environment with `uv` if it is missing.
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

# Create the venv on first run (uses uv's managed Python, no system pip needed).
if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then
    UV_PYTHON_PREFERENCE=only-managed uv venv --python 3.12 .venv
    UV_PYTHON_PREFERENCE=only-managed uv pip install -p .venv PySide6
  else
    echo "uv is required to set up the environment. Install it from https://astral.sh/uv" >&2
    exit 1
  fi
fi

# The env strip is required: a leaked PYTHONHOME/PYTHONPATH from an AppImage host
# otherwise breaks the managed interpreter.
exec env -u PYTHONHOME -u PYTHONPATH .venv/bin/python -m autoclicker "$@"
