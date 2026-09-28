#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Set up the Python environment using README.md first."
  exit 1
fi
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
.venv/bin/python -m retention.cli bootstrap
exec .venv/bin/python -m retention.cli serve --port "${PORT:-8766}"
