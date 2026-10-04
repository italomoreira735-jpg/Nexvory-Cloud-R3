from pydantic import BaseModel, Field
from typing import Literal

class CreateSessionRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=80)
    account_id: str = Field(min_length=1, max_length=120)
    broker: str = "deriv"
    strategy_id: str = "FLOW_M1"
    account_mode: Literal["DEMO", "REAL", "TOURNAMENT"] = "DEMO"

class LimitsRequest(BaseModel):
    period: Literal["DAILY", "SESSION"] = "SESSION"
    max_profit: float | None = None
    max_loss: float | None = None
    max_wins: int | None = None
    max_losses: int | None = None
    max_operations: int | None = None

class ResultRequest(BaseModel):
    pnl: float
