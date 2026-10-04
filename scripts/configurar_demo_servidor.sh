#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' \
'R3 usa credenciais somente no SERVIDOR. Não cole tokens em código/ZIP/APK.' \
'Copie .env.example para .env e preencha apenas no servidor Linux.' \
'Por padrão NEXVORY_ALLOW_DEMO_EXECUTION=false.' \
'Só altere para true depois que health, símbolos, saldo DEMO e auditoria forem validados.' \
'Conta REAL é bloqueada no código mesmo com essa flag.'
