import re
import time
from typing import Any, Union

from mhd_ws.application.services.interfaces.cache_service import CacheService


class InMemoryCacheImpl(CacheService):
    def __init__(self):
        # Dictionary to store the cache data
        self.store: dict[str, Any] = {}
        # Dictionary to store expiration times (as Unix timestamps)
        self.expiration_times = {}

    async def _is_expired(self, key: str) -> bool:
        # Check if the key has expired based on the current time and the stored expiration timestamp
        if key in self.expiration_times:
            if self.expiration_times[key] <= int(time.time()):
                # Key has expired, remove it
                await self.delete_key(key)
                return True
        return False

    async def keys(self, key_pattern: str) -> list[str]:
        # Return a list of keys that match the given pattern
        if "*" in key_pattern:
            regex = key_pattern.replace("*", ".*")
            return [key for key in self.store.keys() if re.match(regex, key)]

        return [key for key in self.store.keys() if key_pattern in key]

    async def does_key_exist(self, key: str) -> bool:
        # Check if the key exists and is not expired
        if key in self.store and not await self._is_expired(key):
            return True
        return False

    async def get_value(self, key: str) -> Any:
        # Return the value for a given key if it exists and has not expired
        if await self.does_key_exist(key):
            return self.store[key]
        return None

    async def set_value_with_expiration_time(
        self, key: str, value: Any, expiration_timestamp: int
    ):
        # Set a value with a specific expiration timestamp (Unix timestamp in seconds)
        self.store[key] = value
        self.expiration_times[key] = expiration_timestamp

    async def set_value(
        self, key: str, value: Any, expiration_time_in_seconds: Union[None, int] = None
    ) -> bool:
        # Set the value in the cache and optionally set an expiration time
        self.store[key] = value
        if expiration_time_in_seconds is not None:
            self.expiration_times[key] = int(time.time()) + expiration_time_in_seconds
        return True

    async def delete_key(self, key: str) -> bool:
        # Delete the key from both the store and expiration dictionary if it exists
        if key in self.store:
            del self.store[key]
        if key in self.expiration_times:
            del self.expiration_times[key]
        return True

    async def get_ttl_in_seconds(self, key: str) -> int:
        if key not in self.store:
            return -2

        if key not in self.expiration_times:
            return -1

        ttl = self.expiration_times[key] - int(time.time())
        if ttl <= 0:
            await self.delete_key(key)
            ttl = 0

        return ttl

    async def get_connection_repr(self):
        return "in-memory"

    async def ping(self):
        return "pong"
