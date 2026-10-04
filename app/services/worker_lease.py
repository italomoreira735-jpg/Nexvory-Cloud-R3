from __future__ import annotations
class RedisWorkerLease:
    """Evita dois workers operando a mesma conta em múltiplas instâncias Cloud."""
    def __init__(self, redis_client, ttl_seconds: int = 60):
        self.redis=redis_client; self.ttl=ttl_seconds
    def acquire(self, tenant_id: str, account_id: str, owner: str) -> bool:
        key=f"nexvory:worker:{tenant_id}:{account_id}"
        return bool(self.redis.set(key, owner, nx=True, ex=self.ttl))
    def renew(self, tenant_id: str, account_id: str, owner: str) -> bool:
        key=f"nexvory:worker:{tenant_id}:{account_id}"
        current=self.redis.get(key)
        valid={owner, owner.encode() if isinstance(owner,str) else owner}
        if current not in valid:
            return False
        return bool(self.redis.expire(key,self.ttl))
