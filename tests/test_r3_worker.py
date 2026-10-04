import asyncio
from decimal import Decimal
from app.brokers.demo import DemoBrokerAdapter
from app.domain.enums import AccountMode
from app.domain.models import MarketTick, StrategySignal
from app.services.execution_coordinator import ExecutionCoordinator
from app.services.robot_service import RobotService
from app.services.session_worker import SessionWorker
from app.storage.repository import InMemoryRepository

class OneTickBroker(DemoBrokerAdapter):
    async def history_ticks(self,symbol,count=5000): return []
    async def stream_ticks(self, account_ref, symbols):
        import time
        yield MarketTick(symbols[0],int(time.time()),100.0)

class SignalStrategy:
    async def on_tick(self,t):
        return [StrategySignal('FLOW_M1_R39','R39','sig',t.symbol,'CALL',t.epoch,60,{})]

def test_worker_executes_and_registers_result():
    async def scenario():
        repo=InMemoryRepository(); robot=RobotService(repo)
        s=robot.ensure_session('u','a','demo','FLOW_M1_R39',AccountMode.DEMO); robot.start(s)
        b=OneTickBroker(); b.results['demo-1']='4.35'
        w=SessionWorker(repo=repo,robot_service=robot,coordinator=ExecutionCoordinator(repo),
            broker=b,strategy=SignalStrategy(),tenant_id='u',account_id='a',symbols=['R_25'],amount=Decimal('5'))
        task=asyncio.create_task(w.run_forever())
        await asyncio.sleep(.05)
        s2=repo.get('u','a'); robot.stop_user(s2)
        await asyncio.wait_for(task,1)
        if w._result_tasks: await asyncio.gather(*list(w._result_tasks))
        z=repo.get('u','a')
        assert len(b.executions)==1
        assert z.counters.operations==1 and z.counters.profit==Decimal('4.35')
    asyncio.run(scenario())
