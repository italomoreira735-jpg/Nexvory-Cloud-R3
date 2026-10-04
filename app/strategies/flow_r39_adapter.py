from __future__ import annotations
from app.domain.models import MarketTick, StrategySignal
from app.strategies.base import StrategyAdapter
from app.strategies.flow_r39_core import FlowMotor, VERSAO as FLOW_R39_VERSAO

class FlowR39Adapter(StrategyAdapter):
    """Adapter Cloud do FLOW R39.

    O calculo operacional e o FlowMotor extraido sem alterar a logica do R39.
    Este adapter apenas normaliza entrada/saida; nao conhece Deriv nem Android.
    """
    strategy_id = "FLOW_M1_R39"
    strategy_version = FLOW_R39_VERSAO

    def __init__(self):
        self._motors: dict[str, FlowMotor] = {}
        self._audit_events: list[dict] = []

    def _motor(self, symbol: str) -> FlowMotor:
        symbol = str(symbol)
        if symbol not in self._motors:
            self._motors[symbol] = FlowMotor(symbol)
        return self._motors[symbol]

    async def on_tick(self, tick: MarketTick) -> list[StrategySignal]:
        events = self._motor(tick.symbol).on_tick(int(tick.epoch), float(tick.price))
        out: list[StrategySignal] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            self._audit_events.append(dict(event))
            if len(self._audit_events) > 5000:
                del self._audit_events[:1000]
            if event.get("tipo") != "SINAL":
                continue
            direction = str(event.get("direcao") or "")
            if direction not in ("CALL", "PUT"):
                continue
            signal_epoch = int(event.get("entrada_epoch") or tick.epoch)
            expiry_epoch = int(event.get("expira_epoch") or (signal_epoch + 60))
            out.append(StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                signal_id=str(event["id"]),
                symbol=str(event.get("simbolo") or tick.symbol),
                direction=direction,
                signal_epoch=signal_epoch,
                expiry_seconds=max(1, expiry_epoch - signal_epoch),
                metadata={
                    "epoch_m1": event.get("epoch_m1"),
                    "preco_entrada_teorico": event.get("preco_entrada"),
                    "setup": event.get("setup"),
                    "contexto_m5": event.get("contexto_m5"),
                    "origem": "R39_FLOW_M1",
                },
            ))
        return out

    def audit_snapshot(self, limit: int = 500) -> list[dict]:
        limit = max(1, min(5000, int(limit)))
        return [dict(x) for x in self._audit_events[-limit:]]

    def reset(self) -> None:
        self._motors.clear()
        self._audit_events.clear()
