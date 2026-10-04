from datetime import datetime, timezone
from app.domain.enums import RobotState, StopReason
from app.domain.models import RobotSession

class InvalidTransition(RuntimeError):
    pass

class RobotStateMachine:
    @staticmethod
    def start(s: RobotSession) -> RobotSession:
        if s.state == RobotState.BLOCKED_SAFETY:
            raise InvalidTransition("Sessão bloqueada por segurança")
        if s.state == RobotState.STOPPED_RISK:
            raise InvalidTransition("Limite de gerenciamento atingido; aguarde/reset o período")
        s.state = RobotState.RUNNING
        s.stop_reason = StopReason.NONE
        s.updated_at = datetime.now(timezone.utc)
        return s

    @staticmethod
    def user_stop(s: RobotSession) -> RobotSession:
        s.state = RobotState.STOPPED_USER
        s.stop_reason = StopReason.USER
        s.updated_at = datetime.now(timezone.utc)
        return s

    @staticmethod
    def temporary_failure(s: RobotSession) -> RobotSession:
        if s.state == RobotState.RUNNING:
            s.state = RobotState.PAUSED_RECONNECTING
            s.updated_at = datetime.now(timezone.utc)
        return s

    @staticmethod
    def recovered(s: RobotSession) -> RobotSession:
        if s.state == RobotState.PAUSED_RECONNECTING:
            s.state = RobotState.RUNNING
            s.stop_reason = StopReason.NONE
            s.updated_at = datetime.now(timezone.utc)
        return s

    @staticmethod
    def risk_stop(s: RobotSession, reason: StopReason) -> RobotSession:
        s.state = RobotState.STOPPED_RISK
        s.stop_reason = reason
        s.updated_at = datetime.now(timezone.utc)
        return s

    @staticmethod
    def safety_block(s: RobotSession, reason: StopReason) -> RobotSession:
        s.state = RobotState.BLOCKED_SAFETY
        s.stop_reason = reason
        s.updated_at = datetime.now(timezone.utc)
        return s
