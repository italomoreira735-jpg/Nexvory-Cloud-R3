from __future__ import annotations
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    version: str = "R3"
    deriv_api_base: str = "https://api.derivws.com"
    deriv_public_ws_url: str = "wss://api.derivws.com/trading/v1/options/ws/public"
    allow_demo_execution: bool = False
    database_url: str = "sqlite:///./nexvory_r3.db"
    redis_url: str = "redis://redis:6379/0"

    @staticmethod
    def from_env() -> "Settings":
        def flag(name: str, default: bool = False) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return Settings(
            deriv_api_base=os.getenv("NEXVORY_DERIV_API_BASE", "https://api.derivws.com"),
            deriv_public_ws_url=os.getenv("NEXVORY_DERIV_PUBLIC_WS", "wss://api.derivws.com/trading/v1/options/ws/public"),
            allow_demo_execution=flag("NEXVORY_ALLOW_DEMO_EXECUTION", False),
            database_url=os.getenv("NEXVORY_DATABASE_URL", "sqlite:///./nexvory_r3.db"),
            redis_url=os.getenv("NEXVORY_REDIS_URL", "redis://redis:6379/0"),
        )
