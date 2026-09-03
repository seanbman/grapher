#!/usr/bin/env bash
# Optional embed integration tests — higher cap, loads fastembed (~1–2GB).
set -euo pipefail
cd "$(dirname "$0")/.."
MEM_MB="${GRAPHER_TEST_MEM_MB:-2048}"
echo "grapher embed tests (cap ${MEM_MB}MB)"
prlimit --as="$((MEM_MB * 1024 * 1024))" \
  uv run --extra dev --extra embed pytest tests/ -m embed "$@"
