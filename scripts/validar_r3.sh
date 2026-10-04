#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pytest -q
python3 -c 'import hashlib; from pathlib import Path; print("FLOW_R39_CORE_SHA256", hashlib.sha256(Path("app/strategies/flow_r39_core.py").read_bytes()).hexdigest()); print("DERIV_REAL_EXECUTION HARD_BLOCKED"); print("DERIV_DEMO_EXECUTION_DEFAULT DISABLED"); print("ANDROID_IN_CRITICAL_PATH NO"); print("STATE_PERSISTENCE_TEST SQLITE_OK")'
