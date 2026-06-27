#!/usr/bin/env bash
set -euo pipefail
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

if [ ! -d tests ]; then
  echo "No tests directory exists; skipping normal acceptance gate."
  mkdir -p build/slow-lane
  printf '{}\n' > build/slow-lane/coverage.json
  exit 0
fi

mkdir -p build/slow-lane
uv run coverage erase
uv run coverage run -m pytest tests -vv --tb=long --showlocals
uv run coverage combine
uv run coverage json -o build/slow-lane/coverage.json
