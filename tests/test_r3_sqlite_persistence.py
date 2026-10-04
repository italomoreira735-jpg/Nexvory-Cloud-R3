from decimal import Decimal
from app.domain.enums import AccountMode, RiskPeriod, RobotState
from app.services.robot_service import RobotService
from app.storage.sqlite_repository import SqliteRepository

def test_session_survives_repository_restart(tmp_path):
    db=tmp_path/'nex.db'; r=SqliteRepository(str(db)); s=RobotService(r)
    x=s.ensure_session('u','a','deriv','FLOW_M1_R39',AccountMode.DEMO)
    x=s.configure_limits(x,period=RiskPeriod.SESSION,max_profit=Decimal('10'))
    x=s.start(x)
    del r
    r2=SqliteRepository(str(db)); y=r2.get('u','a')
    assert y.state==RobotState.RUNNING
    assert y.risk_limits.max_profit==Decimal('10')

def test_idempotency_survives_restart(tmp_path):
    db=tmp_path/'nex.db'; r=SqliteRepository(str(db))
    assert r.reserve_idempotency('k') is True
    r2=SqliteRepository(str(db))
    assert r2.reserve_idempotency('k') is False
