from decimal import Decimal
from app.domain.enums import AccountMode, RiskPeriod, RobotState, StopReason
from app.storage.repository import InMemoryRepository
from app.services.robot_service import RobotService


def test_temporary_failure_does_not_stop():
    repo = InMemoryRepository(); service = RobotService(repo)
    s = service.ensure_session("u1", "a1", "deriv", "FLOW_M1", AccountMode.DEMO)
    s = service.start(s)
    s = service.temporary_failure(s)
    assert s.state == RobotState.PAUSED_RECONNECTING
    s = service.recovered(s)
    assert s.state == RobotState.RUNNING


def test_user_stop_is_definitive():
    repo = InMemoryRepository(); service = RobotService(repo)
    s = service.ensure_session("u1", "a1", "deriv", "FLOW_M1", AccountMode.DEMO)
    s = service.start(s)
    s = service.stop_user(s)
    assert s.state == RobotState.STOPPED_USER
    assert s.stop_reason == StopReason.USER


def test_profit_limit_stops_robot():
    repo = InMemoryRepository(); service = RobotService(repo)
    s = service.ensure_session("u1", "a1", "deriv", "FLOW_M1", AccountMode.DEMO)
    s = service.configure_limits(s, period=RiskPeriod.SESSION, max_profit=10)
    s = service.start(s)
    s = service.register_result(s, Decimal("6"))
    assert s.state == RobotState.RUNNING
    s = service.register_result(s, Decimal("4"))
    assert s.state == RobotState.STOPPED_RISK
    assert s.stop_reason == StopReason.RISK_PROFIT


def test_tenants_are_isolated():
    repo = InMemoryRepository(); service = RobotService(repo)
    a = service.ensure_session("u1", "same", "deriv", "FLOW_M1", AccountMode.DEMO)
    b = service.ensure_session("u2", "same", "deriv", "FLOW_M1", AccountMode.DEMO)
    service.start(a)
    assert repo.get("u1", "same").state == RobotState.RUNNING
    assert repo.get("u2", "same").state == RobotState.IDLE


def test_idempotency_reservation():
    repo = InMemoryRepository()
    assert repo.reserve_idempotency("signal-123") is True
    assert repo.reserve_idempotency("signal-123") is False
