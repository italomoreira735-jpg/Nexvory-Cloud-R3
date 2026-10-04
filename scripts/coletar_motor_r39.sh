#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/nexvory/android/app/src/main/python
OUT=/sdcard/Download/Nexvory-Motor-R39-Para-Cloud.zip
REQ=(v14_7_engine.py nexvory_bridge.py nexvory_flow_m1.py nexvory_flow_exec_demo.py)
for f in "${REQ[@]}"; do
  [ -f "$ROOT/$f" ] || { echo "FALTA: $ROOT/$f" >&2; exit 2; }
done
# Não imprime conteúdo. Apenas hashes e empacotamento local.
echo "ARQUIVOS ATIVOS:"
for f in "${REQ[@]}"; do sha256sum "$ROOT/$f"; done
rm -f "$OUT"
zip -j "$OUT" "${REQ[@]/#/$ROOT/}" >/dev/null
unzip -t "$OUT" >/dev/null
echo "ZIP: $OUT"
sha256sum "$OUT"
echo "ATENCAO: antes de compartilhar, confirme que os fontes nao possuem tokens/segredos embutidos."
