from dataclasses import asdict
from fastapi import FastAPI, HTTPException
from app.api.schemas import CreateSessionRequest, LimitsRequest, ResultRequest
from app.domain.enums import AccountMode, RiskPeriod
from app.config import Settings
from app.storage.factory import build_repository
from app.services.robot_service import RobotService

app = FastAPI(title="Nexvory Cloud", version="R3")
settings = Settings.from_env()
repo = build_repository(settings.database_url)
robot = RobotService(repo)

def serial(s):
    d = asdict(s)
    # FastAPI/Pydantic consegue serializar enums/Decimal na resposta após normalização simples.
    for path in (("state",), ("stop_reason",), ("account_mode",)):
        k = path[0]
        if hasattr(d[k], "value"): d[k] = d[k].value
    if hasattr(d["risk_limits"]["period"], "value"):
        d["risk_limits"]["period"] = d["risk_limits"]["period"].value
    d["counters"]["profit"] = str(d["counters"]["profit"])
    for k in ("max_profit", "max_loss"):
        v = d["risk_limits"][k]
        d["risk_limits"][k] = None if v is None else str(v)
    d["updated_at"] = d["updated_at"].isoformat()
    return d

@app.get("/health")
def health():
    return {"ok": True, "service": "nexvory-cloud", "version": "R3", "real_trading": False, "deriv_execution": "DEMO_GATED"}

@app.post("/v1/sessions")
def create_session(req: CreateSessionRequest):
    s = robot.ensure_session(req.tenant_id, req.account_id, req.broker, req.strategy_id, AccountMode(req.account_mode))
    return serial(s)

@app.get("/v1/sessions/{tenant_id}/{account_id}")
def get_session(tenant_id: str, account_id: str):
    s = repo.get(tenant_id, account_id)
    if not s: raise HTTPException(404, "Sessão não encontrada")
    return serial(s)

@app.post("/v1/sessions/{tenant_id}/{account_id}/limits")
def configure_limits(tenant_id: str, account_id: str, req: LimitsRequest):
    s = repo.get(tenant_id, account_id)
    if not s: raise HTTPException(404, "Sessão não encontrada")
    s = robot.configure_limits(s, period=RiskPeriod(req.period), max_profit=req.max_profit,
        max_loss=req.max_loss, max_wins=req.max_wins, max_losses=req.max_losses,
        max_operations=req.max_operations)
    return serial(s)

@app.post("/v1/sessions/{tenant_id}/{account_id}/start")
def start(tenant_id: str, account_id: str):
    s = repo.get(tenant_id, account_id)
    if not s: raise HTTPException(404, "Sessão não encontrada")
    try: s = robot.start(s)
    except Exception as e: raise HTTPException(409, str(e))
    return serial(s)

@app.post("/v1/sessions/{tenant_id}/{account_id}/stop")
def stop(tenant_id: str, account_id: str):
    s = repo.get(tenant_id, account_id)
    if not s: raise HTTPException(404, "Sessão não encontrada")
    return serial(robot.stop_user(s))

@app.post("/v1/sessions/{tenant_id}/{account_id}/temporary-failure")
def temporary_failure(tenant_id: str, account_id: str):
    s = repo.get(tenant_id, account_id)
    if not s: raise HTTPException(404, "Sessão não encontrada")
    return serial(robot.temporary_failure(s))

@app.post("/v1/sessions/{tenant_id}/{account_id}/recovered")
def recovered(tenant_id: str, account_id: str):
    s = repo.get(tenant_id, account_id)
    if not s: raise HTTPException(404, "Sessão não encontrada")
    return serial(robot.recovered(s))

@app.post("/v1/sessions/{tenant_id}/{account_id}/result")
def result(tenant_id: str, account_id: str, req: ResultRequest):
    s = repo.get(tenant_id, account_id)
    if not s: raise HTTPException(404, "Sessão não encontrada")
    return serial(robot.register_result(s, req.pnl))
