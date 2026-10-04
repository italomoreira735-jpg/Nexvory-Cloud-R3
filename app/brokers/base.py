from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import AsyncIterator
from app.domain.models import ContractOutcome, ExecutionIntent, MarketTick

@dataclass(frozen=True)
class BrokerCapabilities:
    demo: bool = True
    real: bool = False
    tournament: bool = False
    supports_binary_options: bool = False
    supports_cfd: bool = False
    supports_market_stream: bool = False

class BrokerAdapter(ABC):
    """Interface universal de corretora. O Strategy Core nunca importa corretora concreta."""
    name: str
    capabilities: BrokerCapabilities

    @abstractmethod
    async def health(self) -> bool: ...

    @abstractmethod
    async def get_balance(self, account_ref: str) -> Decimal: ...

    async def list_symbols(self, account_ref: str) -> list[str]:
        raise NotImplementedError

    async def history_ticks(self, symbol: str, count: int = 5000) -> list[MarketTick]:
        raise NotImplementedError

    async def stream_ticks(self, account_ref: str, symbols: list[str]) -> AsyncIterator[MarketTick]:
        raise NotImplementedError
        yield  # pragma: no cover

    @abstractmethod
    async def execute(self, intent: ExecutionIntent) -> dict: ...

    async def wait_contract_result(self, account_ref: str, contract_id: str,
                                   timeout_seconds: int = 180) -> ContractOutcome:
        raise NotImplementedError
