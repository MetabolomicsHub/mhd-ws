from __future__ import annotations

import pytest

from mhd_ws.infrastructure.search.es_client import ElasticsearchClient


class FakeApiError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def test_basic_auth_uses_single_client_slot_even_with_named_api_keys():
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

    assert client._configured_api_key_names() == [None]
    assert client._effective_api_key_name("dataset_ms") is None


def test_authentication_error_message_is_explicit():
    client = ElasticsearchClient(
        {
            "hosts": ["https://127.0.0.1:9200"],
            "username": "elastic",
            "password": "secret",
        }
    )

    with pytest.raises(RuntimeError, match="credentials were rejected"):
        client._raise_api_error_with_context(
            FakeApiError(401),
            operation="index existence check",
            api_key_name="dataset_ms",
            index="dataset_ms_v1",
        )
