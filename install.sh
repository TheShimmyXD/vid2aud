#!/usr/bin/env bash
# Instala vid2aud en Linux: entorno virtual, dependencias y acceso en el menu.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    echo "vid2aud necesita Python 3.12 o superior ($PYTHON no sirve)." >&2
    echo "Puedes indicar otro con: PYTHON=python3.12 ./install.sh" >&2
    exit 1
fi

if ! "$PYTHON" -m venv .venv; then
    echo "No se pudo crear el entorno virtual." >&2
    echo "En Debian/Ubuntu/Mint instala el paquete python3-venv y vuelve a intentarlo." >&2
    exit 1
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --install-launcher

echo
echo "Listo. Abre vid2aud desde el menu de aplicaciones o con:"
echo "  .venv/bin/python main.py"
