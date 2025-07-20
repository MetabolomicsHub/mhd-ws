from typing import List

from pydantic import BaseModel

from mhd_ws.infrastructure.cache.redis.redis_config import RedisService


class RedisSentinelConnection(BaseModel):
    master_name: str = "redis"
    password: str = ""
    db: int = 10
    sentinel_services: List[RedisService] = []
    socket_timeout: float = 0.5
