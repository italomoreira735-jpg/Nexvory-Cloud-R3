from __future__ import annotations
from decimal import Decimal
import time
from app.brokers.base import BrokerAdapter
from app.domain.enums import AccountMode, RobotState, StopReason
from app.domain.models import ExecutionIntent, ExecutionRecord, RobotSession, StrategySignal
from app.services.risk_service import RiskService
from app.services.state_machine import RobotStateMachine

class ExecutionCoordinator:
    """Único ponto autorizado a transformar sinal em ordem."""
    def __init__(self, repo):
        self.repo = repo

    async def handle_signal(self, session: RobotSession, signal: StrategySignal,
                            broker: BrokerAdapter, amount: Decimal) -> ExecutionRecord:
        if session.state != RobotState.RUNNING:
            return self._record(session, signal, "IGNORED_SESSION_NOT_RUNNING", broker.name)
        reason = RiskService.evaluate(session)
        if reason:
            RobotStateMachine.risk_stop(session, reason)
            self.repo.save(session)
            return self._record(session, signal, "BLOCKED_RISK", broker.name, {"reason": reason.value})
        if session.account_mode != AccountMode.DEMO:
            RobotStateMachine.safety_block(session, StopReason.SAFETY_EXECUTION_UNCERTAIN)
            self.repo.save(session)
            return self._record(session, signal, "BLOCKED_R3_NON_DEMO", broker.name)
        if not broker.capabilities.demo:
            RobotStateMachine.safety_block(session, StopReason.SAFETY_BROKER)
            self.repo.save(session)
            return self._record(session, signal, "BLOCKED_BROKER_CAPABILITY", broker.name)

        age = time.time() - float(signal.signal_epoch)
        if age > 7 or age < -4:
            return self._record(session, signal, "REJECTED_STALE_SIGNAL", broker.name, {"age": age})

        key = ":".join((session.tenant_id, session.account_id, signal.strategy_id, signal.signal_id))
        if not self.repo.reserve_idempotency(key):
            prior = self.repo.get_execution(key)
            if prior:
                return prior
            return self._record(session, signal, "DUPLICATE_SUPPRESSED", broker.name,
                                idempotency_key=key)

        intent = ExecutionIntent(
            tenant_id=session.tenant_id, account_id=session.account_id,
            account_mode=session.account_mode, broker=session.broker,
            strategy_id=signal.strategy_id, symbol=signal.symbol,
            direction=signal.direction, amount=Decimal(amount),
            duration_seconds=signal.expiry_seconds, idempotency_key=key,
            signal_id=signal.signal_id, signal_epoch=signal.signal_epoch,
            metadata=dict(signal.metadata),
        )
        try:
            result = await broker.execute(intent)
        except Exception as exc:
            RobotStateMachine.safety_block(session, StopReason.SAFETY_EXECUTION_UNCERTAIN)
            self.repo.save(session)
            return self._record(session, signal, "EXECUTION_UNCERTAIN_NO_RETRY", broker.name,
                                {"error_type": type(exc).__name__, "error": str(exc)[:120]}, key)
        status = "ACCEPTED" if result.get("accepted") else "REJECTED"
        return self._record(session, signal, status, broker.name, result, key)

    def _record(self, session: RobotSession, signal: StrategySignal, status: str,
                broker_name: str, result: dict | None = None,
                idempotency_key: str | None = None) -> ExecutionRecord:
        key = idempotency_key or ":".join((session.tenant_id, session.account_id,
                                           signal.strategy_id, signal.signal_id, status))
        rec = ExecutionRecord(key, session.tenant_id, session.account_id,
                              signal.signal_id, status, broker_name, result or {})
        return self.repo.save_execution(rec)
