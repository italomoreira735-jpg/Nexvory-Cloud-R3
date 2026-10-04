from __future__ import annotations
import asyncio
from decimal import Decimal
from app.domain.enums import RobotState

class SessionWorker:
    """Loop Cloud por conta. Android não participa deste ciclo de vida."""
    def __init__(self, *, repo, robot_service, coordinator, broker, strategy,
                 tenant_id: str, account_id: str, symbols: list[str], amount: Decimal,
                 warmup_count: int = 5000):
        self.repo=repo; self.robot=robot_service; self.coordinator=coordinator
        self.broker=broker; self.strategy=strategy
        self.tenant_id=tenant_id; self.account_id=account_id
        self.symbols=list(dict.fromkeys(symbols)); self.amount=Decimal(amount)
        self.warmup_count=warmup_count
        self._result_tasks:set[asyncio.Task]=set()

    def _session(self):
        return self.repo.get(self.tenant_id, self.account_id)

    async def warmup(self):
        for symbol in self.symbols:
            history = await self.broker.history_ticks(symbol, self.warmup_count)
            for tick in history:
                await self.strategy.on_tick(tick)

    async def _track_result(self, contract_id: str):
        try:
            outcome = await self.broker.wait_contract_result(self.account_id, contract_id)
            if outcome.settled:
                s=self._session()
                if s:
                    self.robot.register_result(s, outcome.pnl)
        except asyncio.CancelledError:
            raise
        except Exception:
            return

    async def run_forever(self):
        await self.warmup()
        backoff=1
        while True:
            s=self._session()
            if not s or s.state in {RobotState.STOPPED_USER, RobotState.STOPPED_RISK,
                                    RobotState.BLOCKED_SAFETY, RobotState.IDLE}:
                return
            try:
                if s.state == RobotState.PAUSED_RECONNECTING:
                    self.robot.recovered(s)
                async for tick in self.broker.stream_ticks(self.account_id, self.symbols):
                    s=self._session()
                    if not s or s.state != RobotState.RUNNING:
                        if s and s.state == RobotState.PAUSED_RECONNECTING:
                            break
                        return
                    signals=await self.strategy.on_tick(tick)
                    for signal in signals:
                        s=self._session()
                        if not s or s.state != RobotState.RUNNING:
                            return
                        rec=await self.coordinator.handle_signal(s, signal, self.broker, self.amount)
                        if rec.status == "ACCEPTED" and rec.result.get("contract_id"):
                            t=asyncio.create_task(self._track_result(str(rec.result["contract_id"])))
                            self._result_tasks.add(t)
                            t.add_done_callback(self._result_tasks.discard)
                    backoff=1
                # Stream terminou sem exceção: trate como desconexão temporária.
                s=self._session()
                if s and s.state == RobotState.RUNNING:
                    self.robot.temporary_failure(s)
                await asyncio.sleep(backoff)
                backoff=min(30, backoff*2)
            except asyncio.CancelledError:
                raise
            except Exception:
                s=self._session()
                if s and s.state == RobotState.RUNNING:
                    self.robot.temporary_failure(s)
                await asyncio.sleep(backoff)
                backoff=min(30, backoff*2)
