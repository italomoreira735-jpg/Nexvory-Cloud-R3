#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest -q
cat <<'TXT'

NEXVORY CLOUD R1 instalado e validado localmente.
Inicie com:
  source .venv/bin/activate
  uvicorn app.main:app --host 0.0.0.0 --port 8080

R1 NAO EXECUTA ORDENS REAIS.
TXT
