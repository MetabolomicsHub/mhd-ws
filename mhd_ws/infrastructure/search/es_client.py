import logging
import time
from typing import Any, Dict, Iterable, List, Optional

from elasticsearch import ApiError, AsyncElasticsearch
from elasticsearch.helpers import async_streaming_bulk
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ElasticsearchClientConfig(BaseModel):
    hosts: List[str] | str = Field(
        default_factory=list, description="List of Elasticsearch host URLs"
    )
    api_key: Optional[str] = Field(
        None, description="Deprecated single API key for Elasticsearch authentication"
    )
    api_keys: Optional[Dict[str, str]] = Field(
        default=None,
        description="Named API keys for Elasticsearch authentication",
    )
    username: Optional[str] = Field(
        default=None, description="Username for basic authentication"
    )
    password: Optional[str] = Field(
        default=None, description="Password for basic authentication"
    )
    request_timeout: Optional[float] = Field(
        5.0, description="Request timeout in seconds"
    )
    verify_certs: bool = Field(
        default=True, description="Verify SSL certificates for HTTPS connections"
    )
    indices: Dict[str, str] = Field(
        default_factory=dict,
        description="Logical index name → concrete ES index/alias",
    )


class ElasticsearchClient:
    def __init__(self, config: None | ElasticsearchClientConfig | dict[str, Any]):
        self._config = config
        if not self._config:
            self._config = ElasticsearchClientConfig()
        elif isinstance(self._config, dict):
            self._config = ElasticsearchClientConfig.model_validate(config)
        self._clients: Dict[Optional[str], AsyncElasticsearch] = {}

    def _configured_api_key_names(self) -> List[Optional[str]]:
        if self._config.api_keys:
            return list(self._config.api_keys.keys())
        return [None]

    def _effective_api_key_name(self, api_key_name: Optional[str]) -> Optional[str]:
        if api_key_name is not None:
            return api_key_name
        if self._config.api_keys:
            return next(iter(self._config.api_keys.keys()))
        return None

    def _resolve_api_key_value(self, api_key_name: Optional[str]) -> Optional[str]:
        if api_key_name:
            if self._config.api_keys and api_key_name in self._config.api_keys:
                return self._config.api_keys[api_key_name]
            raise ValueError(
                f"API key '{api_key_name}' is not configured; "
                f"available keys: {list(self._config.api_keys or {})}"
            )
        if self._config.api_key:
            return self._config.api_key
        return None

    async def start(self, api_key_name: Optional[str] = None) -> None:
        target_keys = (
            [api_key_name]
            if api_key_name is not None
            else self._configured_api_key_names()
        )

        for key_name in target_keys:
            if key_name in self._clients:
                continue

            api_key_value = self._resolve_api_key_value(key_name)
            auth_kwargs: Dict[str, Any] = {}
            if self._config.username or self._config.password:
                if not (self._config.username and self._config.password):
                    raise ValueError(
                        "Elasticsearch basic auth requires both username and password."
                    )
                auth_kwargs["basic_auth"] = (
                    self._config.username,
                    self._config.password,
                )
            elif api_key_value:
                auth_kwargs["api_key"] = api_key_value
            if "api_key" in auth_kwargs:
                auth_mode = "api_key"
            elif "basic_auth" in auth_kwargs:
                auth_mode = "basic_auth"
            else:
                auth_mode = "none"
            logger.info(
                "Connecting to Elasticsearch hosts: %s (auth=%s, timeout=%s, verify_certs=%s)",
                self._config.hosts,
                auth_mode,
                self._config.request_timeout,
                self._config.verify_certs,
            )
            es = AsyncElasticsearch(
                hosts=self._config.hosts or None,
                request_timeout=self._config.request_timeout,
                verify_certs=self._config.verify_certs,
                **auth_kwargs,
            )
            try:
                ok = await es.ping()
                if not ok:
                    # Likely a restricted API key without cluster privileges; keep client and proceed.
                    logger.warning(
                        "Elasticsearch ping failed; proceeding anyway (restricted auth or connectivity issue)."
                    )
                self._clients[key_name] = es
                if ok:
                    logger.info(
                        "Elasticsearch connection established successfully (auth=%s).",
                        auth_mode,
                    )
            except ApiError as e:
                status = getattr(e, "status_code", None)
                if status in (401, 403):
                    # Restricted auth cannot ping cluster; keep client and continue.
                    logger.warning(
                        "Elasticsearch ping unauthorized (status=%s); continuing.",
                        status,
                    )
                    self._clients[key_name] = es
                    continue
                await es.close()
                logger.exception("Elasticsearch API error during startup: %s", e)
                raise RuntimeError(f"Elasticsearch connection error: {e}") from e
            except Exception as exc:
                await es.close()
                logger.exception(
                    "Unexpected Elasticsearch connection failure: %s", exc
                )
                raise

    async def ensure_started(self, api_key_name: Optional[str] = None) -> None:
        target_keys = (
            [api_key_name]
            if api_key_name is not None
            else self._configured_api_key_names()
        )
        for key_name in target_keys:
            if key_name in self._clients:
                continue
            await self.start(key_name)

    async def _get_started_client(
        self, api_key_name: Optional[str]
    ) -> AsyncElasticsearch:
        effective_name = self._effective_api_key_name(api_key_name)
        await self.ensure_started(effective_name)
        assert effective_name in self._clients, (
            "Elasticsearch client not connected. Has start() been called?"
        )
        return self._clients[effective_name]

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()
        self._clients.clear()

    async def search(
        self, index, body: Dict[str, Any], api_key_name: Optional[str] = None
    ) -> Dict[str, Any]:
        client = await self._get_started_client(api_key_name)
        started = time.monotonic()
        try:
            return await client.search(index=index, body=body)
        finally:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            effective_key = api_key_name or self._effective_api_key_name(api_key_name)
            logger.debug(
                "Elasticsearch search completed in %sms (index=%s, api_key=%s)",
                elapsed_ms,
                index,
                effective_key,
            )
            if elapsed_ms > 2000:
                logger.debug(
                    "Slow Elasticsearch search (>2s) details: index=%s api_key=%s body=%s",
                    index,
                    effective_key,
                    body,
                )

    # no current usecase for multiple search, but adding for completeness / the future.
    async def msearch(
        self, index, body: Dict[str, Any], api_key_name: Optional[str] = None
    ) -> Dict[str, Any]:
        client = await self._get_started_client(api_key_name)
        return await client.msearch(index=index, body=body)

    async def count(
        self, index, body: Optional[Dict[str, Any]], api_key_name: Optional[str] = None
    ) -> int:
        client = await self._get_started_client(api_key_name)
        resp = await client.count(index=index, body=body or {})
        return int(resp.get("count", 0))

    async def get_info(self, api_key_name: Optional[str] = None) -> Dict[str, Any]:
        client = await self._get_started_client(api_key_name)
        return await client.info()

    async def get_mapping(
        self, index: str, api_key_name: Optional[str] = None
    ) -> Dict[str, Any]:
        client = await self._get_started_client(api_key_name)
        response = await client.indices.get_mapping(index=index)
        return response.body

    async def index_exists(
        self, index: str, api_key_name: Optional[str] = None
    ) -> bool:
        client = await self._get_started_client(api_key_name)
        return await client.indices.exists(index=index)

    async def create_index(
        self, index: str, mapping: dict, api_key_name: Optional[str] = None
    ) -> None:
        client = await self._get_started_client(api_key_name)
        try:
            await client.indices.create(index=index, **mapping)
            logger.info("Created index: %s", index)
        except ApiError as e:
            raise RuntimeError(
                f"Index creation failed for {index}: {e}"
            ) from e

    async def delete_index(
        self, index: str, api_key_name: Optional[str] = None
    ) -> None:
        client = await self._get_started_client(api_key_name)
        await client.indices.delete(index=index)
        logger.info("Deleted index: %s", index)

    async def ensure_index_exists(
        self,
        index: str,
        mapping: dict,
        recreate: bool = False,
        api_key_name: Optional[str] = None,
    ) -> None:
        exists = await self.index_exists(index, api_key_name)
        if exists:
            if not recreate:
                logger.info("Index %s already exists, skipping creation.", index)
                return
            await self.delete_index(index, api_key_name)
        await self.create_index(index, mapping, api_key_name)

    async def bulk_upload(
        self,
        docs: Iterable[Dict[str, Any]],
        index_name: str,
        op_type: str = "index",
        batch_size: int = 500,
        api_key_name: Optional[str] = None,
    ) -> int:
        client = await self._get_started_client(api_key_name)
        errors: List[Dict[str, Any]] = []
        total_uploaded = 0

        def actions():
            for doc in docs:
                action: Dict[str, Any] = {
                    "_op_type": op_type,
                    "_index": index_name,
                    "_source": doc,
                }
                doc_id = doc.get("id")
                if doc_id:
                    action["_id"] = doc_id
                yield action

        async for ok, item in async_streaming_bulk(
            client,
            actions(),
            chunk_size=batch_size,
            raise_on_error=False,
            raise_on_exception=True,
        ):
            if ok:
                total_uploaded += 1
                continue
            errors.append(item)

        if errors:
            sample = errors[:5]
            raise RuntimeError(
                f"Bulk upload failed for {len(errors)} items; sample: {sample}"
            )

        logger.info(
            "Bulk uploaded %d docs to index %s", total_uploaded, index_name
        )
        return total_uploaded
