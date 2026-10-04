from __future__ import annotations
import json, sqlite3
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from threading import RLock
from app.domain.enums import AccountMode, RiskPeriod, RobotState, StopReason
from app.domain.models import ExecutionRecord, RiskCounters, RiskLimits, RobotSession

class SqliteRepository:
    """Persistência R3 local/edge; mantém a mesma fronteira do repositório Cloud."""
    def __init__(self, path: str):
        self.path=path; self._lock=RLock()
        with self._db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS sessions(
              tenant_id TEXT NOT NULL, account_id TEXT NOT NULL, payload TEXT NOT NULL,
              PRIMARY KEY(tenant_id,account_id));
            CREATE TABLE IF NOT EXISTS executions(
              idempotency_key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS idempotency(k TEXT PRIMARY KEY);
            ''')
    def _db(self): return sqlite3.connect(self.path)
    @staticmethod
    def _session_to_json(s):
        d=asdict(s); d['account_mode']=s.account_mode.value; d['state']=s.state.value
        d['stop_reason']=s.stop_reason.value; d['risk_limits']['period']=s.risk_limits.period.value
        for k in ('max_profit','max_loss'):
            v=d['risk_limits'][k]; d['risk_limits'][k]=None if v is None else str(v)
        d['counters']['profit']=str(s.counters.profit); d['updated_at']=s.updated_at.isoformat()
        return json.dumps(d,separators=(',',':'),ensure_ascii=False)
    @staticmethod
    def _session_from_json(raw):
        d=json.loads(raw); l=d['risk_limits']; c=d['counters']
        return RobotSession(d['tenant_id'],d['account_id'],d['broker'],AccountMode(d['account_mode']),
            d['strategy_id'],RobotState(d['state']),StopReason(d['stop_reason']),
            RiskLimits(RiskPeriod(l['period']),Decimal(l['max_profit']) if l['max_profit'] is not None else None,
                       Decimal(l['max_loss']) if l['max_loss'] is not None else None,
                       l['max_wins'],l['max_losses'],l['max_operations']),
            RiskCounters(Decimal(c['profit']),c['wins'],c['losses'],c['operations']),
            datetime.fromisoformat(d['updated_at']))
    @staticmethod
    def _exec_to_json(r): return json.dumps(asdict(r),separators=(',',':'),ensure_ascii=False)
    @staticmethod
    def _exec_from_json(raw): return ExecutionRecord(**json.loads(raw))
    def get(self,tenant_id,account_id):
        with self._lock,self._db() as db:
            row=db.execute('SELECT payload FROM sessions WHERE tenant_id=? AND account_id=?',(tenant_id,account_id)).fetchone()
            return self._session_from_json(row[0]) if row else None
    def save(self,s):
        raw=self._session_to_json(s)
        with self._lock,self._db() as db:
            db.execute('INSERT INTO sessions VALUES(?,?,?) ON CONFLICT(tenant_id,account_id) DO UPDATE SET payload=excluded.payload',(s.tenant_id,s.account_id,raw))
        return self.get(s.tenant_id,s.account_id)
    def reserve_idempotency(self,key):
        with self._lock,self._db() as db:
            try: db.execute('INSERT INTO idempotency(k) VALUES(?)',(key,)); return True
            except sqlite3.IntegrityError: return False
    def save_execution(self,r):
        raw=self._exec_to_json(r)
        with self._lock,self._db() as db:
            db.execute('INSERT INTO executions VALUES(?,?) ON CONFLICT(idempotency_key) DO UPDATE SET payload=excluded.payload',(r.idempotency_key,raw))
        return self.get_execution(r.idempotency_key)
    def get_execution(self,key):
        with self._lock,self._db() as db:
            row=db.execute('SELECT payload FROM executions WHERE idempotency_key=?',(key,)).fetchone()
            return self._exec_from_json(row[0]) if row else None
