from decimal import Decimal
from app.domain.enums import AccountMode, RiskPeriod, RobotState, StopReason
from app.domain.models import RobotSession, RiskLimits
from app.services.state_machine import RobotStateMachine
from app.services.risk_service import RiskService
from app.storage.repository import InMemoryRepository

class RobotService:
    def __init__(self, repo: InMemoryRepository):
        self.repo = repo

    def ensure_session(self, tenant_id: str, account_id: str, broker: str, strategy_id: str,
                       account_mode: AccountMode = AccountMode.DEMO) -> RobotSession:
        s = self.repo.get(tenant_id, account_id)
        if s:
            return s
        s = RobotSession(tenant_id, account_id, broker, account_mode, strategy_id)
        return self.repo.save(s)

    def configure_limits(self, s: RobotSession, *, period: RiskPeriod,
                         max_profit=None, max_loss=None, max_wins=None,
                         max_losses=None, max_operations=None) -> RobotSession:
        s.risk_limits = RiskLimits(
            period=period,
            max_profit=Decimal(str(max_profit)) if max_profit is not None else None,
            max_loss=Decimal(str(max_loss)) if max_loss is not None else None,
            max_wins=max_wins,
            max_losses=max_losses,
            max_operations=max_operations,
        )
        return self.repo.save(s)

    def start(self, s: RobotSession) -> RobotSession:
        reason = RiskService.evaluate(s)
        if reason:
            RobotStateMachine.risk_stop(s, reason)
        else:
            RobotStateMachine.start(s)
        return self.repo.save(s)

    def stop_user(self, s: RobotSession) -> RobotSession:
        return self.repo.save(RobotStateMachine.user_stop(s))

    def temporary_failure(self, s: RobotSession) -> RobotSession:
        return self.repo.save(RobotStateMachine.temporary_failure(s))

    def recovered(self, s: RobotSession) -> RobotSession:
        return self.repo.save(RobotStateMachine.recovered(s))

    def register_result(self, s: RobotSession, pnl) -> RobotSession:
        reason = RiskService.register_result(s, Decimal(str(pnl)))
        if reason:
            RobotStateMachine.risk_stop(s, reason)
        return self.repo.save(s)
