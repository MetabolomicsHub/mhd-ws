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

    def _uses_basic_auth(self) -> bool:
        return bool(self._config.username or self._config.password)

    def _configured_api_key_names(self) -> List[Optional[str]]:
        if self._uses_basic_auth():
            return [None]
        if self._config.api_keys:
            return list(self._config.api_keys.keys())
        return [None]

    def _effective_api_key_name(self, api_key_name: Optional[str]) -> Optional[str]:
        if self._uses_basic_auth():
            return None
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

    def _describe_auth_mode(self, api_key_name: Optional[str]) -> str:
        if self._uses_basic_auth():
            return "basic_auth"
        if self._resolve_api_key_value(api_key_name):
            return "api_key"
        return "none"

    def _raise_api_error_with_context(
        self,
        exc: Exception,
        *,
        operation: str,
        api_key_name: Optional[str] = None,
        index: Optional[str] = None,
    ) -> None:
        status = getattr(exc, "status_code", None)
        index_context = f" for index {index!r}" if index else ""
        auth_mode = self._describe_auth_mode(api_key_name)

        if status == 401:
            raise RuntimeError(
                f"Elasticsearch authentication failed during {operation}{index_context} "
                f"(HTTP 401). The Elasticsearch endpoint is reachable, but the configured "
                f"{auth_mode} credentials were rejected. Check the active username/password "
                f"or API key in your config/secrets."
            ) from exc

        if status == 403:
            raise RuntimeError(
                f"Elasticsearch authorization failed during {operation}{index_context} "
                f"(HTTP 403). The configured {auth_mode} credentials authenticated but do "
                f"not have permission for this action."
            ) from exc

        if isinstance(exc, Exception):
            raise exc

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
            auth_mode = self._describe_auth_mode(key_name)
            logger.info(
                "Connecting to Elasticsearch hosts: %s (auth=%s, timeout=%s, verify_certs=%s)",
                self._config.hosts,
                auth_mode,
                self._config.request_timeout,
                self._config.verify_certs,
            )

            try:
                es = AsyncElasticsearch(
                    hosts=self._config.hosts or None,
                    request_timeout=self._config.request_timeout,
                    verify_certs=self._config.verify_certs,
                    **auth_kwargs,
                )
                ok = await es.ping()
                if not ok:
                    logger.warning(
                        "Elasticsearch ping returned false while using %s. "
                        "If subsequent requests fail with HTTP 401, the credentials are invalid. "
                        "If they fail with HTTP 403, the credentials are authenticated but lack privileges.",
                        auth_mode,
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
                logger.exception("Unexpected Elasticsearch connection failure: %s", exc)
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
        except ApiError as exc:
            self._raise_api_error_with_context(
                exc,
                operation="search",
                api_key_name=api_key_name,
                index=index,
            )
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
        try:
            return await client.msearch(index=index, body=body)
        except ApiError as exc:
            self._raise_api_error_with_context(
                exc,
                operation="multi-search",
                api_key_name=api_key_name,
                index=index,
            )

    async def count(
        self, index, body: Optional[Dict[str, Any]], api_key_name: Optional[str] = None
    ) -> int:
        client = await self._get_started_client(api_key_name)
        try:
            resp = await client.count(index=index, body=body or {})
        except ApiError as exc:
            self._raise_api_error_with_context(
                exc,
                operation="count",
                api_key_name=api_key_name,
                index=index,
            )
        return int(resp.get("count", 0))

    async def get_info(self, api_key_name: Optional[str] = None) -> Dict[str, Any]:
        client = await self._get_started_client(api_key_name)
        try:
            return await client.info()
        except ApiError as exc:
            self._raise_api_error_with_context(
                exc,
                operation="cluster info request",
                api_key_name=api_key_name,
            )

    async def get_mapping(
        self, index: str, api_key_name: Optional[str] = None
    ) -> Dict[str, Any]:
        client = await self._get_started_client(api_key_name)
        try:
            response = await client.indices.get_mapping(index=index)
        except ApiError as exc:
            self._raise_api_error_with_context(
                exc,
                operation="mapping lookup",
                api_key_name=api_key_name,
                index=index,
            )
        return response.body

    async def index_exists(
        self, index: str, api_key_name: Optional[str] = None
    ) -> bool:
        client = await self._get_started_client(api_key_name)
        try:
            return await client.indices.exists(index=index)
        except ApiError as exc:
            self._raise_api_error_with_context(
                exc,
                operation="index existence check",
                api_key_name=api_key_name,
                index=index,
            )

    async def create_index(
        self, index: str, mapping: dict, api_key_name: Optional[str] = None
    ) -> None:
        client = await self._get_started_client(api_key_name)
        try:
            await client.indices.create(index=index, **mapping)
            logger.info("Created index: %s", index)
        except ApiError as e:
            self._raise_api_error_with_context(
                e,
                operation="index creation",
                api_key_name=api_key_name,
                index=index,
            )
            raise RuntimeError(f"Index creation failed for {index}: {e}") from e

    async def delete_index(
        self, index: str, api_key_name: Optional[str] = None
    ) -> None:
        client = await self._get_started_client(api_key_name)
        try:
            await client.indices.delete(index=index)
        except ApiError as exc:
            self._raise_api_error_with_context(
                exc,
                operation="index deletion",
                api_key_name=api_key_name,
                index=index,
            )
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

        logger.info("Bulk uploaded %d docs to index %s", total_uploaded, index_name)
        return total_uploaded
