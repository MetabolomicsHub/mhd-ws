import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Union

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient
from mhd_ws.infrastructure.persistence.db.sqlite.config import SQLiteDatabaseConnection

logger = logging.getLogger(__name__)


class SQLiteDatabaseClientImpl(DatabaseClient):
    def __init__(
        self,
        db_connection: Union[SQLiteDatabaseConnection, dict[str, any]],
    ) -> None:
        self.db_connection = db_connection
        if isinstance(db_connection, dict):
            self.db_connection = SQLiteDatabaseConnection.model_validate(db_connection)
        cn = self.db_connection
        real_path = os.path.realpath(cn.file_path)
        self.db_url = f"{cn.url_scheme}:///{real_path}"
        self.db_url_repr = self.db_url
        logger.warning("Database is SQLite and it is only for development.")
        self.engine = create_async_engine(self.db_url, echo=True)

        self._async_session_factory = async_sessionmaker(
            self.engine, expire_on_commit=False
        )

    async def get_connection_repr(self) -> str:
        return self.db_url_repr

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[Any, async_sessionmaker[AsyncSession]]:
        try:
            async with self._async_session_factory() as session:
                yield session
        except Exception as ex:
            await session.rollback()
            logger.exception(ex)
            raise Exception("Session rollback", self.db_url_repr) from ex
        finally:
            await session.close()
