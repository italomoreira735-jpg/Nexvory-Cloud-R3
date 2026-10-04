from copy import deepcopy
from threading import RLock
from app.domain.models import RobotSession, ExecutionRecord

class InMemoryRepository:
    """R2 local/teste. Produção trocará por PostgreSQL mantendo esta fronteira."""
    def __init__(self):
        self._lock = RLock()
        self._sessions: dict[tuple[str, str], RobotSession] = {}
        self._idempotency: set[str] = set()
        self._executions: dict[str, ExecutionRecord] = {}

    def get(self, tenant_id: str, account_id: str) -> RobotSession | None:
        with self._lock:
            s = self._sessions.get((tenant_id, account_id))
            return deepcopy(s) if s else None

    def save(self, s: RobotSession) -> RobotSession:
        with self._lock:
            self._sessions[(s.tenant_id, s.account_id)] = deepcopy(s)
            return deepcopy(s)

    def reserve_idempotency(self, key: str) -> bool:
        with self._lock:
            if key in self._idempotency:
                return False
            self._idempotency.add(key)
            return True

    def save_execution(self, record: ExecutionRecord) -> ExecutionRecord:
        with self._lock:
            self._executions[record.idempotency_key] = deepcopy(record)
            return deepcopy(record)

    def get_execution(self, key: str) -> ExecutionRecord | None:
        with self._lock:
            r = self._executions.get(key)
            return deepcopy(r) if r else None
