import abc
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DatabaseClient(abc.ABC):
    @abc.abstractmethod
    async def get_connection_repr(self) -> str: ...

    @abc.abstractmethod
    async def session(
        self,
    ) -> AsyncGenerator[Any, async_sessionmaker[AsyncSession]]: ...
