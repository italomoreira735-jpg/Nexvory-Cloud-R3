from __future__ import annotations
import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from sqlalchemy import create_engine, text
from app.domain.enums import AccountMode, RiskPeriod, RobotState, StopReason
from app.domain.models import ExecutionRecord, RiskCounters, RiskLimits, RobotSession

class PostgresRepository:
    """Persistência multi-instância para servidor Cloud.

    Usa chaves únicas no PostgreSQL para manter idempotência mesmo após restart
    ou concorrência entre processos. A estratégia não conhece esta classe.
    """
    def __init__(self, url: str):
        self.engine=create_engine(url,pool_pre_ping=True,future=True)
        self._init_schema()
    def _init_schema(self):
        ddl='''
        CREATE TABLE IF NOT EXISTS nexvory_sessions(
          tenant_id TEXT NOT NULL,
          account_id TEXT NOT NULL,
          payload JSONB NOT NULL,
          PRIMARY KEY(tenant_id,account_id)
        );
        CREATE TABLE IF NOT EXISTS nexvory_executions(
          idempotency_key TEXT PRIMARY KEY,
          payload JSONB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS nexvory_idempotency(
          k TEXT PRIMARY KEY,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        '''
        with self.engine.begin() as c:
            for stmt in [x.strip() for x in ddl.split(';') if x.strip()]:
                c.execute(text(stmt))
    @staticmethod
    def _session_dict(s):
        d=asdict(s); d['account_mode']=s.account_mode.value; d['state']=s.state.value
        d['stop_reason']=s.stop_reason.value; d['risk_limits']['period']=s.risk_limits.period.value
        for k in ('max_profit','max_loss'):
            v=d['risk_limits'][k]; d['risk_limits'][k]=None if v is None else str(v)
        d['counters']['profit']=str(s.counters.profit); d['updated_at']=s.updated_at.isoformat()
        return d
    @staticmethod
    def _session(d):
        l=d['risk_limits']; c=d['counters']
        return RobotSession(d['tenant_id'],d['account_id'],d['broker'],AccountMode(d['account_mode']),
            d['strategy_id'],RobotState(d['state']),StopReason(d['stop_reason']),
            RiskLimits(RiskPeriod(l['period']),Decimal(l['max_profit']) if l['max_profit'] is not None else None,
                       Decimal(l['max_loss']) if l['max_loss'] is not None else None,
                       l['max_wins'],l['max_losses'],l['max_operations']),
            RiskCounters(Decimal(c['profit']),c['wins'],c['losses'],c['operations']),
            datetime.fromisoformat(d['updated_at']))
    def get(self,tenant_id,account_id):
        with self.engine.begin() as c:
            row=c.execute(text('SELECT payload FROM nexvory_sessions WHERE tenant_id=:t AND account_id=:a'),{'t':tenant_id,'a':account_id}).first()
        return self._session(row[0]) if row else None
    def save(self,s):
        payload=json.dumps(self._session_dict(s),ensure_ascii=False)
        with self.engine.begin() as c:
            c.execute(text('''INSERT INTO nexvory_sessions(tenant_id,account_id,payload)
                VALUES(:t,:a,CAST(:p AS JSONB))
                ON CONFLICT(tenant_id,account_id) DO UPDATE SET payload=EXCLUDED.payload'''),
                {'t':s.tenant_id,'a':s.account_id,'p':payload})
        return self.get(s.tenant_id,s.account_id)
    def reserve_idempotency(self,key):
        with self.engine.begin() as c:
            row=c.execute(text('INSERT INTO nexvory_idempotency(k) VALUES(:k) ON CONFLICT DO NOTHING RETURNING k'),{'k':key}).first()
        return bool(row)
    def save_execution(self,r):
        payload=json.dumps(asdict(r),ensure_ascii=False)
        with self.engine.begin() as c:
            c.execute(text('''INSERT INTO nexvory_executions(idempotency_key,payload)
                VALUES(:k,CAST(:p AS JSONB))
                ON CONFLICT(idempotency_key) DO UPDATE SET payload=EXCLUDED.payload'''),
                {'k':r.idempotency_key,'p':payload})
        return self.get_execution(r.idempotency_key)
    def get_execution(self,key):
        with self.engine.begin() as c:
            row=c.execute(text('SELECT payload FROM nexvory_executions WHERE idempotency_key=:k'),{'k':key}).first()
        return ExecutionRecord(**row[0]) if row else None
