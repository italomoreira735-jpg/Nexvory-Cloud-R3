from __future__ import annotations
from decimal import Decimal
from app.brokers.base import BrokerAdapter
from app.domain.models import MarketTick, RobotSession
from app.services.execution_coordinator import ExecutionCoordinator
from app.strategies.base import StrategyAdapter

class CloudRuntime:
    """Runtime por sessao/conta. O estado da estrategia nunca e compartilhado entre tenants."""
    def __init__(self, session: RobotSession, strategy: StrategyAdapter,
                 broker: BrokerAdapter, coordinator: ExecutionCoordinator,
                 amount: Decimal = Decimal("1")):
        self.session = session
        self.strategy = strategy
        self.broker = broker
        self.coordinator = coordinator
        self.amount = Decimal(amount)

    async def on_tick(self, tick: MarketTick):
        signals = await self.strategy.on_tick(tick)
        records = []
        for signal in signals:
            records.append(await self.coordinator.handle_signal(
                self.session, signal, self.broker, self.amount))
        return {"signals": signals, "executions": records}
