from typing import Any, Union

import redis.asyncio as redis
from redis.sentinel import Sentinel

from mhd_ws.application.services.interfaces.cache_service import CacheService
from mhd_ws.infrastructure.cache.redis_sentinel.redis_sentinel_config import (
    RedisSentinelConnection,
)


class RedisSentinelCacheImpl(CacheService):
    def __init__(self, config: dict[str, Any]):
        self.connection = RedisSentinelConnection.model_validate(config)
        connections = [(x.host, x.port) for x in self.connection.sentinel_services if x]
        self.sentinel = Sentinel(
            connections,
            socket_timeout=self.connection.socket_timeout,
            decode_responses=True,
            sentinel_kwargs={
                "password": self.connection.password,
            },
        )

        self.service_name = self.connection.master_name
        sc = self.connection
        self.url_repr = ";".join(
            [
                f"sentinel://:***@{service.host}:{service.port}/{sc.db}"
                for service in sc.sentinel_services
            ]
        )

    async def get_connection_repr(self) -> None:
        return self.url_repr

    async def _get_master_connection(self) -> redis.Redis:
        redis_master = self.sentinel.master_for(
            self.service_name,
            redis_class=redis.Redis,
            db=self.connection.db,
            password=self.connection.password,
            decode_responses=True,
            socket_connect_timeout=self.connection.socket_timeout,
        )
        return redis_master

    async def _get_slave_connection(self) -> redis.Redis:
        redis_slave = self.sentinel.slave_for(
            self.service_name,
            redis_class=redis.Redis,
            db=self.connection.db,
            password=self.connection.password,
            decode_responses=True,
            socket_connect_timeout=self.connection.socket_timeout,
        )
        return redis_slave

    async def keys(self, key_pattern: str) -> list[str]:
        master = await self._get_master_connection()
        return await master.keys(key_pattern)

    async def does_key_exist(self, key: str) -> bool:
        slave = await self._get_slave_connection()
        return await slave.exists(key) > 0

    async def get_value(self, key: str) -> Any:
        slave = await self._get_slave_connection()
        return await slave.get(key)

    async def set_value_with_expiration_time(
        self, key: str, value: Any, expiration_timestamp: int
    ):
        master = await self._get_master_connection()
        return await master.setex(key, expiration_timestamp, value)

    async def set_value(
        self, key: str, value: Any, expiration_time_in_seconds: Union[None, int] = None
    ) -> bool:
        master = await self._get_master_connection()
        if expiration_time_in_seconds:
            return await master.setex(key, expiration_time_in_seconds, value)
        return await master.set(key, value)

    async def delete_key(self, key: str) -> bool:
        master = await self._get_master_connection()
        return await master.delete(key) > 0

    async def get_ttl_in_seconds(self, key: str) -> int:
        slave = await self._get_slave_connection()
        return await slave.ttl(key)

    async def ping(self) -> None:
        master = await self._get_master_connection()
        return await master.ping()
