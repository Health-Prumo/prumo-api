#!/usr/bin/env bash
set -euo pipefail

raiz_prumo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -x "$raiz_prumo/.venv/bin/python" ]]; then
    python_prumo="$raiz_prumo/.venv/bin/python"
elif [[ -x "$raiz_prumo/.venv/Scripts/python.exe" ]]; then
    python_prumo="$raiz_prumo/.venv/Scripts/python.exe"
else
    echo 'Crie a venv Python 3.12 e instale requirements/development.txt.' >&2
    exit 1
fi
exec "$python_prumo" "$raiz_prumo/scripts/dev.py" "$@"
