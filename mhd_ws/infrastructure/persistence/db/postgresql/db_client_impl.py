import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Union

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient
from mhd_ws.infrastructure.persistence.db.postgresql.config import (
    DatabaseConnection,
)

logger = logging.getLogger(__name__)


class DatabaseClientImpl(DatabaseClient):
    def __init__(
        self,
        db_connection: Union[DatabaseConnection, dict[str, Any]],
        db_pool_size: Union[None, int] = 3,
    ) -> None:
        self.db_connection = db_connection
        if isinstance(db_connection, dict):
            self.db_connection = DatabaseConnection.model_validate(db_connection)
        cn = self.db_connection
        if not isinstance(cn, DatabaseConnection):
            raise TypeError(
                f"db_connection must be of type DatabaseConnection, got {type(cn)}"
            )
        self.db_url = (
            f"{cn.url_scheme}://{cn.user}:{cn.password}"
            + f"@{cn.host}:{cn.port}/{cn.database}"
        )
        self.db_url_repr = (
            f"{cn.url_scheme}://{cn.user}:***@{cn.host}:{cn.port}/{cn.database}"
        )
        if db_pool_size is not None and db_pool_size > 0:
            self.engine = create_async_engine(
                self.db_url,
                future=True,
                pool_size=db_pool_size,
                max_overflow=db_pool_size * 2,
            )
        else:
            logger.warning(
                "Database pool size is not set so connection pool will not be used. "
                "This may cause performance issues."
            )
            self.engine = create_async_engine(
                self.db_url,
                future=True,
                poolclass=NullPool,
            )
        self._async_session_factory = async_sessionmaker(
            self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    async def get_connection_repr(self) -> str:
        return self.db_url_repr

    

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._async_session_factory() as session:
            try:
                yield session
            except Exception as ex:
                await session.rollback()
                logger.exception(ex)
                raise ex
