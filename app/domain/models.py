from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any
from .enums import RobotState, StopReason, RiskPeriod, AccountMode

@dataclass
class RiskLimits:
    period: RiskPeriod = RiskPeriod.SESSION
    max_profit: Decimal | None = None
    max_loss: Decimal | None = None
    max_wins: int | None = None
    max_losses: int | None = None
    max_operations: int | None = None

@dataclass
class RiskCounters:
    profit: Decimal = Decimal("0")
    wins: int = 0
    losses: int = 0
    operations: int = 0

@dataclass
class RobotSession:
    tenant_id: str
    account_id: str
    broker: str
    account_mode: AccountMode
    strategy_id: str
    state: RobotState = RobotState.IDLE
    stop_reason: StopReason = StopReason.NONE
    risk_limits: RiskLimits = field(default_factory=RiskLimits)
    counters: RiskCounters = field(default_factory=RiskCounters)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass(frozen=True)
class MarketTick:
    symbol: str
    epoch: int
    price: float

@dataclass(frozen=True)
class StrategySignal:
    strategy_id: str
    strategy_version: str
    signal_id: str
    symbol: str
    direction: str
    signal_epoch: int
    expiry_seconds: int
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ExecutionIntent:
    tenant_id: str
    account_id: str
    account_mode: AccountMode
    broker: str
    strategy_id: str
    symbol: str
    direction: str
    amount: Decimal
    duration_seconds: int
    idempotency_key: str
    signal_id: str = ""
    signal_epoch: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ExecutionRecord:
    idempotency_key: str
    tenant_id: str
    account_id: str
    signal_id: str
    status: str
    broker: str
    result: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ContractOutcome:
    contract_id: str
    settled: bool
    pnl: Decimal
    status: str
    raw: dict[str, Any] = field(default_factory=dict)
