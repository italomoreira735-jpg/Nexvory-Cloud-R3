from decimal import Decimal
from app.domain.enums import StopReason
from app.domain.models import RobotSession

class RiskService:
    @staticmethod
    def evaluate(s: RobotSession) -> StopReason | None:
        l, c = s.risk_limits, s.counters
        if l.max_profit is not None and c.profit >= l.max_profit:
            return StopReason.RISK_PROFIT
        if l.max_loss is not None and c.profit <= -abs(l.max_loss):
            return StopReason.RISK_LOSS
        if l.max_wins is not None and c.wins >= l.max_wins:
            return StopReason.RISK_WINS
        if l.max_losses is not None and c.losses >= l.max_losses:
            return StopReason.RISK_LOSSES
        if l.max_operations is not None and c.operations >= l.max_operations:
            return StopReason.RISK_OPERATIONS
        return None

    @staticmethod
    def register_result(s: RobotSession, pnl: Decimal) -> StopReason | None:
        s.counters.operations += 1
        s.counters.profit += pnl
        if pnl > 0:
            s.counters.wins += 1
        elif pnl < 0:
            s.counters.losses += 1
        return RiskService.evaluate(s)
