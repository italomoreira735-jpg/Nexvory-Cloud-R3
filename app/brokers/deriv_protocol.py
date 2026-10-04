from __future__ import annotations
import asyncio
import json
from typing import Any

class DerivProtocolError(RuntimeError):
    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message

def check_response(data: dict[str, Any]) -> dict[str, Any]:
    err = data.get("error")
    if err:
        raise DerivProtocolError(str(err.get("code") or "DERIV_ERROR"),
                                 str(err.get("message") or ""))
    return data

async def send_request(ws, payload: dict[str, Any], *, timeout: float = 20.0) -> dict[str, Any]:
    req_id = payload.get("req_id")
    await ws.send(json.dumps(payload, separators=(",", ":")))
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        data = check_response(json.loads(raw))
        if req_id is None or data.get("req_id") == req_id:
            return data
