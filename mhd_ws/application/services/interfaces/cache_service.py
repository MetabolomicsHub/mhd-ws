import abc
from typing import Any, Union


class CacheService(abc.ABC):
    @abc.abstractmethod
    async def get_connection_repr(self) -> str: ...

    @abc.abstractmethod
    async def keys(self, key_pattern: str) -> list[str]: ...

    @abc.abstractmethod
    async def does_key_exist(self, key: str) -> bool: ...

    @abc.abstractmethod
    async def get_value(self, key: str) -> Any: ...

    @abc.abstractmethod
    async def set_value_with_expiration_time(
        self, key: str, value: Any, expiration_timestamp: int
    ): ...

    @abc.abstractmethod
    async def set_value(
        self,
        key: str,
        value: Any,
        expiration_time_in_seconds: Union[None, int] = None,
    ) -> bool: ...

    @abc.abstractmethod
    async def delete_key(self, key: str) -> bool: ...

    @abc.abstractmethod
    async def ping(self) -> None: ...

    @abc.abstractmethod
    async def get_ttl_in_seconds(self, key) -> int: ...
