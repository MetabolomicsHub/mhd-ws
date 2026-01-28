from typing import Any, Union

import redis.asyncio as redis
from redis.asyncio.sentinel import Sentinel

from mhd_ws.application.services.interfaces.cache_service import CacheService
from mhd_ws.infrastructure.cache.redis_sentinel.redis_sentinel_config import (
    RedisSentinelConnection,
)


class RedisSentinelCacheImpl(CacheService):
    def __init__(self, config: dict[str, Any]):
        self._conn = RedisSentinelConnection.model_validate(config)
        sentinels: list[tuple[str, int]] = [
            (s.host, s.port) for s in (self._conn.sentinel_services or [])
        ]
        if not sentinels:
            raise ValueError("sentinel_services must not be empty")

        self._sentinel = Sentinel(
            sentinels,
            socket_timeout=self._conn.socket_timeout,
            decode_responses=True,
            sentinel_kwargs={
                "password": self._conn.password,
            },
        )

        self._master: redis.Redis = self._sentinel.master_for(
            service_name=self._conn.master_name,
            redis_class=redis.Redis,
            db=self._conn.db,
            password=self._conn.password or None,
            socket_timeout=self._conn.socket_timeout,
            socket_connect_timeout=self._conn.socket_timeout,
            max_connections=self._conn.max_connections,
            decode_responses=True,
        )
        sc = self._conn
        self.url_repr = ";".join(
            [f"sentinel://:***@{x.host}:{x.port}/{sc.db}" for x in sc.sentinel_services]
        )

    async def get_connection_repr(self) -> None:
        return self.url_repr

    async def keys(self, key_pattern: str) -> list[str]:
        # Use SCAN instead of KEYS to avoid blocking Redis
        cursor = 0
        out: list[str] = []
        while True:
            cursor, batch = await self._master.scan(
                cursor=cursor, match=key_pattern, count=1000
            )
            out.extend(batch)
            if cursor == 0:
                break
        return out

    async def does_key_exist(self, key: str) -> bool:
        return bool(await self._master.exists(key))

    async def get_value(self, key: str) -> Any:
        return await self._master.get(key)

    async def set_value_with_expiration_time(
        self, key: str, value: Any, expiration_timestamp: int
    ):
        await self._master.set(key, value, exat=expiration_timestamp)

    async def set_value(
        self,
        key: str,
        value: Any,
        expiration_time_in_seconds: Union[None, int] = None,
    ) -> bool:
        if expiration_time_in_seconds is None:
            return bool(await self._master.set(key, value))

        return bool(
            await self._master.set(key, value, ex=int(expiration_time_in_seconds))
        )

    async def delete_key(self, key: str) -> bool:
        return (await self._master.delete(key)) > 0

    async def get_ttl_in_seconds(self, key) -> int:
        # -2: key doesn't exist, -1: no expiry, >=0: seconds remaining
        return int(await self._master.ttl(key))

    async def ping(self) -> None:
        return bool(await self._master.ping())
