import asyncio
from decimal import Decimal
from pathlib import Path
from app.brokers.demo import DemoBrokerAdapter
from app.domain.enums import AccountMode, RobotState, StopReason
from app.domain.models import MarketTick, StrategySignal
from app.services.execution_coordinator import ExecutionCoordinator
from app.storage.repository import InMemoryRepository
from app.services.robot_service import RobotService
from app.strategies.flow_r39_adapter import FlowR39Adapter


def run(coro):
    return asyncio.run(coro)


def test_flow_core_has_no_broker_or_android_dependencies():
    import ast
    src = Path('app/strategies/flow_r39_core.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    imported = set()
    called = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported.update(a.name.split('.')[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            imported.add(n.module.split('.')[0])
        elif isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name): called.add(n.func.id)
            elif isinstance(n.func, ast.Attribute): called.add(n.func.attr)
    assert 'requests' not in imported
    assert 'websocket' not in imported
    assert 'conectar_demo' not in called
    assert 'create_connection' not in called
    assert 'Chaquopy' not in src and 'android.' not in src


def test_adapter_converts_r39_signal_without_broker_knowledge():
    class FakeMotor:
        def on_tick(self, epoch, price):
            return [{
                'tipo': 'SINAL', 'id': 'R_25:1000:CALL', 'simbolo': 'R_25',
                'entrada_epoch': 1000, 'expira_epoch': 1060, 'direcao': 'CALL',
                'epoch_m1': 960, 'preco_entrada': 123.45,
                'setup': {'n_corr': 2}, 'contexto_m5': {'m5_disponivel': False},
            }]
    a = FlowR39Adapter()
    a._motors['R_25'] = FakeMotor()
    signals = run(a.on_tick(MarketTick('R_25', 1000, 123.45)))
    assert len(signals) == 1
    s = signals[0]
    assert s.strategy_id == 'FLOW_M1_R39'
    assert s.direction == 'CALL'
    assert s.expiry_seconds == 60
    assert s.signal_id == 'R_25:1000:CALL'


def test_adapter_state_isolated_per_instance():
    a = FlowR39Adapter(); b = FlowR39Adapter()
    assert a._motor('R_25') is not b._motor('R_25')


def test_execution_idempotency_suppresses_duplicate_order():
    repo = InMemoryRepository(); robot = RobotService(repo)
    session = robot.ensure_session('u1', 'a1', 'demo', 'FLOW_M1_R39', AccountMode.DEMO)
    session = robot.start(session)
    broker = DemoBrokerAdapter(); coord = ExecutionCoordinator(repo)
    import time
    sig = StrategySignal('FLOW_M1_R39', 'R39', 'sig-1', 'R_25', 'CALL', int(time.time()), 60)
    first = run(coord.handle_signal(session, sig, broker, Decimal('5')))
    second = run(coord.handle_signal(session, sig, broker, Decimal('5')))
    assert first.status == 'ACCEPTED'
    assert second.status == 'ACCEPTED'
    assert len(broker.executions) == 1


def test_non_demo_is_blocked_in_r2():
    repo = InMemoryRepository(); robot = RobotService(repo)
    session = robot.ensure_session('u1', 'real1', 'demo', 'FLOW_M1_R39', AccountMode.REAL)
    session = robot.start(session)
    broker = DemoBrokerAdapter(); coord = ExecutionCoordinator(repo)
    import time
    sig = StrategySignal('FLOW_M1_R39', 'R39', 'sig-real', 'R_25', 'CALL', int(time.time()), 60)
    rec = run(coord.handle_signal(session, sig, broker, Decimal('5')))
    assert rec.status == 'BLOCKED_R3_NON_DEMO'
    saved = repo.get('u1', 'real1')
    assert saved.state == RobotState.BLOCKED_SAFETY
    assert saved.stop_reason == StopReason.SAFETY_EXECUTION_UNCERTAIN
    assert len(broker.executions) == 0


def test_stale_signal_is_not_executed():
    repo = InMemoryRepository(); robot = RobotService(repo)
    session = robot.ensure_session('u1', 'a1', 'demo', 'FLOW_M1_R39', AccountMode.DEMO)
    session = robot.start(session)
    broker = DemoBrokerAdapter(); coord = ExecutionCoordinator(repo)
    import time
    sig = StrategySignal('FLOW_M1_R39', 'R39', 'old', 'R_25', 'PUT', int(time.time())-20, 60)
    rec = run(coord.handle_signal(session, sig, broker, Decimal('5')))
    assert rec.status == 'REJECTED_STALE_SIGNAL'
    assert len(broker.executions) == 0
