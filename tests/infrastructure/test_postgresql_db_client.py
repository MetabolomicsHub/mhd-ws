from __future__ import annotations

from typing import Any

import pytest

from mhd_ws.infrastructure.persistence.db.postgresql import db_client_impl
from mhd_ws.infrastructure.persistence.db.postgresql.db_client_impl import (
    DatabaseClientImpl,
)


class FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, Any] | None]] = []
        self.rolled_back = False

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def execute(
        self, statement: Any, params: dict[str, Any] | None = None
    ) -> None:
        self.executed.append((str(statement), params))

    async def rollback(self) -> None:
        self.rolled_back = True


def test_configured_schema_is_passed_to_asyncpg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, Any] = {}

    def fake_create_async_engine(*args: Any, **kwargs: Any) -> object:
        captured_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr(db_client_impl, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(
        db_client_impl, "async_sessionmaker", lambda *args, **kwargs: None
    )

    client = DatabaseClientImpl(
        {
            "host": "db.example.org",
            "port": 5432,
            "user": "mhd",
            "password": "secret",
            "database": "mmimhdpro",
            "url_scheme": "postgresql+asyncpg",
            "schema": "mhd",
        }
    )

    assert client.db_schema == "mhd"
    assert captured_kwargs["connect_args"] == {
        "server_settings": {"search_path": "mhd"}
    }


@pytest.mark.asyncio
async def test_session_sets_configured_search_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = FakeSession()

    monkeypatch.setattr(
        db_client_impl, "create_async_engine", lambda *args, **kwargs: object()
    )
    monkeypatch.setattr(
        db_client_impl,
        "async_sessionmaker",
        lambda *args, **kwargs: lambda: fake_session,
    )

    client = DatabaseClientImpl(
        {
            "host": "db.example.org",
            "port": 5432,
            "user": "mhd",
            "password": "secret",
            "database": "mmimhdpro",
            "url_scheme": "postgresql+asyncpg",
            "schema": "mhd",
        }
    )

    async with client.session() as session:
        assert session is fake_session

    assert fake_session.executed == [
        (
            "SELECT set_config('search_path', :schema, false)",
            {"schema": "mhd"},
        )
    ]
