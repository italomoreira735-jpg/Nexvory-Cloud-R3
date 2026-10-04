from decimal import Decimal
from app.brokers.base import BrokerAdapter, BrokerCapabilities
from app.domain.models import ContractOutcome, ExecutionIntent

class DemoBrokerAdapter(BrokerAdapter):
    name = "demo"
    capabilities = BrokerCapabilities(demo=True, supports_binary_options=True, supports_market_stream=False)
    def __init__(self):
        self.executions=[]
        self.results={}
    async def health(self): return True
    async def get_balance(self, account_ref): return Decimal("10000")
    async def execute(self, intent: ExecutionIntent):
        cid=f"demo-{len(self.executions)+1}"
        self.executions.append(intent)
        return {"accepted": True, "mode":"DEMO", "contract_id":cid,
                "amount":str(intent.amount), "symbol":intent.symbol,
                "direction":intent.direction, "duration_seconds":intent.duration_seconds}
    async def wait_contract_result(self, account_ref, contract_id, timeout_seconds=180):
        pnl=Decimal(str(self.results.get(contract_id, "0")))
        return ContractOutcome(contract_id, True, pnl, "won" if pnl>0 else "lost" if pnl<0 else "sold", {})
