from abc import ABC, abstractmethod
from app.domain.models import MarketTick, StrategySignal

class StrategyAdapter(ABC):
    """Contrato universal: estrategia recebe mercado normalizado e devolve sinais.

    Nenhuma estrategia deve importar SDK/API de corretora, token, WebSocket de broker
    ou classes Android.
    """
    strategy_id: str
    strategy_version: str

    @abstractmethod
    async def on_tick(self, tick: MarketTick) -> list[StrategySignal]: ...

    async def next_intents(self):
        # Compatibilidade temporaria com a Foundation R1.
        return []
