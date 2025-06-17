import abc
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseClient(abc.ABC):
    @abc.abstractmethod
    async def get_connection_repr(self) -> str: ...

    @abc.abstractmethod
    async def session(self) -> AsyncGenerator[AsyncSession, None]: ...
