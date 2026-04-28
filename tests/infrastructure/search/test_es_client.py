from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from elastic_transport import ConnectionTimeout
from elasticsearch import ApiError

from mhd_ws.infrastructure.search import es_client as es_client_module
from mhd_ws.infrastructure.search.es_client import ElasticsearchClient


class FakeApiError(ApiError):
    def __init__(self, status_code: int):
        Exception.__init__(self, f"HTTP {status_code}")
        self._status_code = status_code

    @property
    def status_code(self) -> int:
        return self._status_code


@pytest.mark.asyncio
async def test_basic_auth_named_api_key_requests_reuse_basic_auth_client(
    monkeypatch: pytest.MonkeyPatch,
):
    instances = []

    class FakeAsyncElasticsearch:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.ping = AsyncMock(return_value=True)
            self.info = AsyncMock(return_value={"cluster_name": "test"})
            self.close = AsyncMock()
            self.indices = object()
            instances.append(self)

    monkeypatch.setattr(es_client_module, "AsyncElasticsearch", FakeAsyncElasticsearch)

    client = ElasticsearchClient(
        {
            "hosts": ["https://127.0.0.1:9200"],
            "api_keys": {
                "dataset_ms": "",
                "metabolite": "",
            },
            "username": "elastic",
            "password": "secret",
        }
    )

    await client.start()
    info = await client.get_info(api_key_name="dataset_ms")

    assert info == {"cluster_name": "test"}
    assert len(instances) == 1
    assert instances[0].kwargs["basic_auth"] == ("elastic", "secret")
    assert "api_key" not in instances[0].kwargs

    await client.close()


@pytest.mark.asyncio
async def test_authentication_error_message_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeIndicesClient:
        async def exists(self, *, index: str) -> bool:
            raise FakeApiError(401)

    class FakeAsyncElasticsearch:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.ping = AsyncMock(return_value=True)
            self.close = AsyncMock()
            self.indices = FakeIndicesClient()

    monkeypatch.setattr(es_client_module, "AsyncElasticsearch", FakeAsyncElasticsearch)

    client = ElasticsearchClient(
        {
            "hosts": ["https://127.0.0.1:9200"],
            "username": "elastic",
            "password": "secret",
        }
    )

    with pytest.raises(RuntimeError, match="credentials were rejected"):
        await client.index_exists(
            "dataset_ms_v1",
            api_key_name="dataset_ms",
        )

    await client.close()


@pytest.mark.asyncio
async def test_bulk_upload_uses_bulk_request_timeout(
    monkeypatch: pytest.MonkeyPatch,
):
    captured_kwargs = {}

    class FakeAsyncElasticsearch:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.ping = AsyncMock(return_value=True)
            self.close = AsyncMock()
            self.indices = object()

    async def fake_async_streaming_bulk(*args, **kwargs):
        captured_kwargs.update(kwargs)
        yield True, {"index": {"_id": "doc-1"}}

    monkeypatch.setattr(es_client_module, "AsyncElasticsearch", FakeAsyncElasticsearch)
    monkeypatch.setattr(
        es_client_module, "async_streaming_bulk", fake_async_streaming_bulk
    )

    client = ElasticsearchClient(
        {
            "hosts": ["https://127.0.0.1:9200"],
            "username": "elastic",
            "password": "secret",
            "request_timeout": 5.0,
            "bulk_request_timeout": 90.0,
        }
    )

    await client.start()
    uploaded = await client.bulk_upload(
        [{"id": "doc-1", "name": "example"}],
        index_name="dataset_ms_v1",
    )

    assert uploaded == 1
    assert captured_kwargs["request_timeout"] == 90.0

    await client.close()


@pytest.mark.asyncio
async def test_bulk_upload_timeout_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeAsyncElasticsearch:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.ping = AsyncMock(return_value=True)
            self.close = AsyncMock()
            self.indices = object()

    async def fake_async_streaming_bulk(*args, **kwargs):
        raise ConnectionTimeout(message="timed out")
        yield

    monkeypatch.setattr(es_client_module, "AsyncElasticsearch", FakeAsyncElasticsearch)
    monkeypatch.setattr(
        es_client_module, "async_streaming_bulk", fake_async_streaming_bulk
    )

    client = ElasticsearchClient(
        {
            "hosts": ["https://127.0.0.1:9200"],
            "username": "elastic",
            "password": "secret",
            "bulk_request_timeout": 60.0,
        }
    )

    await client.start()

    with pytest.raises(RuntimeError, match="bulk_request_timeout"):
        await client.bulk_upload(
            [{"id": "doc-1", "name": "example"}],
            index_name="dataset_ms_v1",
        )

    await client.close()
