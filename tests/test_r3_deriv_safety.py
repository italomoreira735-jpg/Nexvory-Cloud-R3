import asyncio
from decimal import Decimal
import pytest
from app.brokers.deriv import DerivAdapter
from app.domain.enums import AccountMode
from app.domain.models import ExecutionIntent

def run(c): return asyncio.run(c)

def intent(mode=AccountMode.DEMO):
    return ExecutionIntent('u','acc',mode,'deriv','FLOW_M1_R39','R_25','CALL',Decimal('5'),60,'k','s',1,{})

def test_real_hard_block_happens_before_network():
    b=DerivAdapter(allow_demo_execution=True)
    with pytest.raises(RuntimeError, match='REAL_HARD_BLOCK'):
        run(b.execute(intent(AccountMode.REAL)))

def test_demo_execution_disabled_by_default_before_network():
    b=DerivAdapter(allow_demo_execution=False)
    with pytest.raises(RuntimeError, match='DEMO_EXECUTION_DISABLED'):
        run(b.execute(intent(AccountMode.DEMO)))

def test_demo_url_guard_rejects_real_endpoint():
    with pytest.raises(RuntimeError, match='URL_NAO_DEMO'):
        DerivAdapter._require_demo_url('wss://api.derivws.com/trading/v1/options/ws/real?otp=x')
    DerivAdapter._require_demo_url('wss://api.derivws.com/trading/v1/options/ws/demo?otp=x')

def test_capabilities_never_advertise_real():
    assert DerivAdapter.capabilities.demo is True
    assert DerivAdapter.capabilities.real is False
