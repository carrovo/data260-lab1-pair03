#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON="$PROJECT_ROOT/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "error: repository virtual environment not found at $PYTHON" >&2
  exit 2
fi

cd "$PROJECT_ROOT"
exec "$PYTHON" -m backend.harness.runner "$@"
