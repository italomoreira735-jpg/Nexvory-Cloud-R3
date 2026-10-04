import hashlib
from pathlib import Path

EXPECTED = 'eb671cac0a290eee63fab4581d7b2b7de96dc745fb8d7d5d6dfeb21e7d087f03'

def test_r39_flow_core_snapshot_integrity():
    data = Path('app/strategies/flow_r39_core.py').read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED
