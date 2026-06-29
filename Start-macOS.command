#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export SHMAGSTICK_HOME="$ROOT"

for python in "$ROOT/.venv/bin/python" python3; do
    if command -v "$python" >/dev/null 2>&1 && "$python" -c 'import PyQt6, psutil' >/dev/null 2>&1; then
        exec "$python" "$ROOT/shmagstick.py" "$@"
    fi
done

echo "ShmagStick needs Python 3.9+ with PyQt6 and psutil."
echo "Install them, then run: python3 -m pip install -r requirements.txt"
read -r _
exit 1
