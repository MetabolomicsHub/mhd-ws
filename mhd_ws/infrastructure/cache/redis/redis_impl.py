from typing import Any, Union

from redis.asyncio import Redis

from mhd_ws.application.services.interfaces.cache_service import CacheService
from mhd_ws.infrastructure.cache.redis.redis_config import RedisConnection


class RedisCacheImpl(CacheService):
    def __init__(self, config: dict[str, Any]):
        self.connection = RedisConnection.model_validate(config, from_attributes=True)

        self.redis = Redis(
            host=self.connection.redis_service.host,
            port=self.connection.redis_service.port,
            db=self.connection.db,
            password=self.connection.password,
            decode_responses=True,
            socket_connect_timeout=self.connection.socket_timeout,
        )
        rc = self.connection
        self.url_repr = (
            f"redis://:***@{rc.redis_service.host}:{rc.redis_service.port}/{rc.db}"
        )

    async def get_connection_repr(self) -> None:
        return self.url_repr

    async def ping(self) -> None:
        return await self.redis.ping()

    async def keys(self, key_pattern: str) -> list[str]:
        return [key for key in await self.redis.keys(key_pattern)]

    async def does_key_exist(self, key: str) -> bool:
        return await self.redis.exists(key) > 0

    async def get_value(self, key: str) -> Any:
        value = await self.redis.get(key)
        if value is not None:
            return value
        return None

    async def set_value_with_expiration_time(
        self, key: str, value: Any, expiration_timestamp: int
    ):
        return await self.redis.setex(key, expiration_timestamp, value)

    async def set_value(
        self, key: str, value: Any, expiration_time_in_seconds: Union[None, int] = None
    ) -> bool:
        if expiration_time_in_seconds:
            return await self.redis.setex(key, expiration_time_in_seconds, value)
        return await self.redis.set(key, value)

    async def delete_key(self, key: str) -> bool:
        return await self.redis.delete(key) > 0

    async def get_ttl_in_seconds(self, key: str) -> int:
        return await self.redis.ttl(key)
