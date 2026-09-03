#!/usr/bin/env bash
# Lightweight test run — memory-capped, no embed model loaded.
set -euo pipefail
cd "$(dirname "$0")/.."
MEM_MB="${GRAPHER_TEST_MEM_MB:-768}"
echo "grapher tests (cap ${MEM_MB}MB, no embed)"
prlimit --as="$((MEM_MB * 1024 * 1024))" \
  uv run --extra dev pytest tests/ -m "not embed" "$@"
