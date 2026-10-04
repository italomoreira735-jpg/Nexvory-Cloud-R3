from __future__ import annotations
import asyncio
from decimal import Decimal, InvalidOperation
import itertools
import json

from app.brokers.base import BrokerAdapter, BrokerCapabilities
from app.brokers.deriv_protocol import check_response, send_request
from app.domain.enums import AccountMode
from app.domain.models import ContractOutcome, ExecutionIntent, MarketTick

class DerivAdapter(BrokerAdapter):
    """Deriv New Options API adapter — R3 executa apenas DEMO."""
    name = "deriv"
    capabilities = BrokerCapabilities(
        demo=True, real=False, tournament=False,
        supports_binary_options=True, supports_market_stream=True,
    )

    def __init__(self, api_base: str = "https://api.derivws.com",
                 public_ws_url: str = "wss://api.derivws.com/trading/v1/options/ws/public",
                 bearer_token: str | None = None, app_id: str | None = None,
                 currency: str = "USD", allow_demo_execution: bool = False):
        self.api_base = api_base.rstrip("/")
        self.public_ws_url = public_ws_url
        self.bearer_token = bearer_token
        self.app_id = app_id
        self.currency = str(currency).upper()
        self.allow_demo_execution = bool(allow_demo_execution)
        self._req = itertools.count(1)

    def _req_id(self) -> int:
        return next(self._req)

    async def health(self) -> bool:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.api_base}/v1/health")
                return r.status_code == 200 and r.text.strip().upper() == "OK"
        except Exception:
            return False

    async def get_authenticated_ws_url(self, account_ref: str) -> str:
        import httpx
        if not self.bearer_token:
            raise RuntimeError("DERIV_TOKEN_AUSENTE")
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        if self.app_id:
            headers["Deriv-App-ID"] = self.app_id
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{self.api_base}/trading/v1/options/accounts/{account_ref}/otp",
                headers=headers,
            )
            r.raise_for_status()
            payload = r.json()
        candidates = []
        if isinstance(payload, dict):
            if isinstance(payload.get("data"), dict):
                candidates.append(payload["data"].get("url"))
            candidates.extend(payload.get(k) for k in ("url", "websocket_url", "ws_url"))
        url = next((str(x) for x in candidates if x), "")
        if not url.startswith("wss://"):
            raise RuntimeError("DERIV_OTP_SEM_URL")
        return url

    @staticmethod
    def _require_demo_url(url: str) -> None:
        if "/trading/v1/options/ws/demo" not in url:
            raise RuntimeError("DERIV_R3_BLOQUEIO_REAL_URL_NAO_DEMO")

    async def get_balance(self, account_ref: str) -> Decimal:
        import websockets
        url = await self.get_authenticated_ws_url(account_ref)
        self._require_demo_url(url)
        async with websockets.connect(url, ping_interval=30, close_timeout=5) as ws:
            data = await send_request(ws, {"balance": 1, "req_id": self._req_id()})
        try:
            return Decimal(str(data["balance"]["balance"]))
        except (KeyError, TypeError, InvalidOperation) as exc:
            raise RuntimeError("DERIV_BALANCE_INVALIDO") from exc

    async def list_symbols(self, account_ref: str = "") -> list[str]:
        import websockets
        async with websockets.connect(self.public_ws_url, ping_interval=30, close_timeout=5) as ws:
            data = await send_request(ws, {
                "active_symbols": "brief",
                "contract_type": ["CALL", "PUT"],
                "req_id": self._req_id(),
            })
        out = []
        for item in data.get("active_symbols") or []:
            symbol = item.get("symbol") or item.get("underlying_symbol")
            if symbol:
                out.append(str(symbol))
        return out

    async def history_ticks(self, symbol: str, count: int = 5000) -> list[MarketTick]:
        import websockets
        count = max(100, min(int(count), 10000))
        async with websockets.connect(self.public_ws_url, ping_interval=30, close_timeout=5) as ws:
            data = await send_request(ws, {
                "ticks_history": str(symbol), "style": "ticks", "end": "latest",
                "count": count, "adjust_start_time": 1, "req_id": self._req_id(),
            }, timeout=30)
        history = data.get("history") or {}
        times = history.get("times") or []
        prices = history.get("prices") or []
        result = []
        for epoch, price in zip(times, prices):
            try:
                result.append(MarketTick(str(symbol), int(epoch), float(price)))
            except (TypeError, ValueError):
                continue
        return result

    async def stream_ticks(self, account_ref: str, symbols: list[str]):
        import websockets
        symbols = [str(s) for s in symbols if str(s)]
        if not symbols:
            return
        backoff = 1
        while True:
            try:
                async with websockets.connect(self.public_ws_url, ping_interval=30,
                                              close_timeout=5) as ws:
                    await ws.send(json.dumps({
                        "ticks": symbols if len(symbols) > 1 else symbols[0],
                        "subscribe": 1, "req_id": self._req_id(),
                    }, separators=(",", ":")))
                    backoff = 1
                    async for raw in ws:
                        data = check_response(json.loads(raw))
                        tick = data.get("tick")
                        if not tick:
                            continue
                        symbol = tick.get("symbol") or tick.get("underlying_symbol")
                        quote = tick.get("quote")
                        epoch = tick.get("epoch")
                        try:
                            yield MarketTick(str(symbol), int(epoch), float(quote))
                        except (TypeError, ValueError):
                            continue
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(30, backoff * 2)

    async def execute(self, intent: ExecutionIntent) -> dict:
        if intent.account_mode != AccountMode.DEMO:
            raise RuntimeError("DERIV_R3_REAL_HARD_BLOCK")
        if not self.allow_demo_execution:
            raise RuntimeError("DERIV_R3_DEMO_EXECUTION_DISABLED")
        if intent.direction not in {"CALL", "PUT"}:
            raise RuntimeError("DERIV_DIRECAO_NAO_SUPORTADA")
        if intent.duration_seconds <= 0:
            raise RuntimeError("DERIV_DURACAO_INVALIDA")

        import websockets
        url = await self.get_authenticated_ws_url(intent.account_id)
        self._require_demo_url(url)
        async with websockets.connect(url, ping_interval=30, close_timeout=5) as ws:
            proposal_req = {
                "proposal": 1,
                "amount": float(intent.amount),
                "basis": "stake",
                "contract_type": intent.direction,
                "currency": self.currency,
                "duration": int(intent.duration_seconds),
                "duration_unit": "s",
                "underlying_symbol": intent.symbol,
                "req_id": self._req_id(),
            }
            proposal_msg = await send_request(ws, proposal_req, timeout=15)
            proposal = proposal_msg.get("proposal") or {}
            proposal_id = proposal.get("id")
            if not proposal_id:
                raise RuntimeError("DERIV_PROPOSTA_SEM_ID")
            ask_raw = proposal.get("ask_price", intent.amount)
            try:
                ask_price = Decimal(str(ask_raw))
            except InvalidOperation as exc:
                raise RuntimeError("DERIV_PROPOSTA_PRECO_INVALIDO") from exc
            max_price = max(ask_price, Decimal(intent.amount))
            buy_msg = await send_request(ws, {
                "buy": str(proposal_id),
                "price": float(max_price),
                "req_id": self._req_id(),
            }, timeout=15)
            buy = buy_msg.get("buy") or {}
            contract_id = buy.get("contract_id")
            if not contract_id:
                raise RuntimeError("DERIV_COMPRA_SEM_CONTRACT_ID")
            return {
                "accepted": True,
                "mode": "DEMO",
                "contract_id": str(contract_id),
                "transaction_id": buy.get("transaction_id"),
                "buy_price": str(buy.get("buy_price", ask_price)),
                "balance_after": buy.get("balance_after"),
                "purchase_time": buy.get("purchase_time"),
            }

    async def wait_contract_result(self, account_ref: str, contract_id: str,
                                   timeout_seconds: int = 180) -> ContractOutcome:
        import websockets
        url = await self.get_authenticated_ws_url(account_ref)
        self._require_demo_url(url)
        req_id = self._req_id()
        async with websockets.connect(url, ping_interval=30, close_timeout=5) as ws:
            await ws.send(json.dumps({
                "proposal_open_contract": 1,
                "contract_id": int(contract_id),
                "subscribe": 1,
                "req_id": req_id,
            }, separators=(",", ":")))
            deadline = asyncio.get_running_loop().time() + max(10, timeout_seconds)
            subscription_id = None
            last = {}
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError("DERIV_RESULTADO_TIMEOUT")
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                data = check_response(json.loads(raw))
                if data.get("msg_type") != "proposal_open_contract":
                    continue
                contract = data.get("proposal_open_contract") or {}
                last = contract
                sub = data.get("subscription") or {}
                if sub.get("id"):
                    subscription_id = sub["id"]
                if contract.get("is_sold") or contract.get("is_expired"):
                    try:
                        pnl = Decimal(str(contract.get("profit", "0")))
                    except InvalidOperation:
                        pnl = Decimal("0")
                    if subscription_id:
                        try:
                            await ws.send(json.dumps({"forget": subscription_id,
                                                      "req_id": self._req_id()}))
                        except Exception:
                            pass
                    return ContractOutcome(
                        contract_id=str(contract_id), settled=True, pnl=pnl,
                        status=str(contract.get("status") or "SETTLED"), raw=dict(last),
                    )
