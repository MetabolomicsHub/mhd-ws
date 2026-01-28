from typing import List

from pydantic import BaseModel

from mhd_ws.infrastructure.cache.redis.redis_config import RedisService


class RedisSentinelService(RedisService):
    port: int = 26379


class RedisSentinelConnection(BaseModel):
    master_name: str = "redis"
    password: str = ""
    db: int = 10
    sentinel_services: List[RedisSentinelService] = []
    socket_timeout: float = 0.5
    max_connections: int = 30
