#!/usr/bin/env bash
set -euo pipefail

REPO="seanbman/grapher"
APP="grapher"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="${HOME}/.local/bin"
APP_HOME="$DATA_HOME/$APP"
VENV="$APP_HOME/venv"

command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 1; }

mkdir -p "$APP_HOME" "$BIN_HOME"

TAG="${GRAPHER_VERSION:-}"
if [[ -z "$TAG" ]]; then
  TAG="$(python3 - <<'PY'
import json, urllib.request
url='https://api.github.com/repos/seanbman/grapher/releases?per_page=20'
with urllib.request.urlopen(url, timeout=8) as r:
    releases=json.load(r)
for rel in releases:
    if not rel.get('draft'):
        print(rel['tag_name'])
        break
else:
    raise SystemExit('No published Grapher release found')
PY
)"
fi

echo "Installing Grapher $TAG"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install --upgrade "git+https://github.com/$REPO.git@$TAG"
ln -sfn "$VENV/bin/grapher" "$BIN_HOME/grapher"

cat <<EOF
Installed Grapher $TAG
Launcher: $BIN_HOME/grapher

Ensure $BIN_HOME is on PATH. Then run:
  grapher
EOF
