from __future__ import annotations

import logging
import uuid
from typing import Any

from mhd_ws.application.services.interfaces.search_port import SearchPort
from mhd_ws.domain.entities.search.index_search import (
    FacetBucket,
    FacetResponse,
    FilterModel,
    IndexSearchResult,
    PageModel,
    SortModel,
)
from mhd_ws.infrastructure.search.es.es_configuration import (
    ElasticsearchConfiguration,
)
from mhd_ws.infrastructure.search.es_client import ElasticsearchClient

logger = logging.getLogger(__name__)


class BaseElasticSearchGateway(SearchPort):
    def __init__(
        self,
        client: ElasticsearchClient,
        config: ElasticsearchConfiguration,
    ):
        self._client = client
        self._config = config

    async def search(
        self,
        *,
        search_text: str | None = None,
        filters: list[FilterModel] | None = None,
        page: PageModel | None = None,
        sort: SortModel | None = None,
    ) -> IndexSearchResult:
        page = page or PageModel()
        payload = self._build_search_payload(
            search_text=search_text,
            filters=filters,
            page=page,
            sort=sort,
        )
        index_name = getattr(self._config, "index_name", "")
        api_key_name = self._config.api_key_name

        logger.debug("ES search payload for index=%s: %s", index_name, payload)
        raw = await self._client.search(
            index=index_name, body=payload, api_key_name=api_key_name
        )

        results = [self._map_hit(hit) for hit in raw.get("hits", {}).get("hits", [])]
        total = self._extract_total(raw)
        facets = self._map_aggs_to_searchui(raw.get("aggregations", {}))

        return IndexSearchResult(
            results=results,
            total_results=total,
            facets=facets,
            request_id=str(uuid.uuid4()),
        )

    async def get_index_mapping(self) -> dict[str, Any]:
        index_name = getattr(self._config, "index_name", "")
        return await self._client.get_mapping(
            index=index_name, api_key_name=self._config.api_key_name
        )

    # -- hook methods for subclasses ------------------------------------------

    def _build_search_payload(
        self,
        *,
        search_text: str | None,
        filters: list[FilterModel] | None,
        page: PageModel,
        sort: SortModel | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        query = self._build_query(search_text=search_text, filters=filters)
        if query:
            payload["query"] = query
        payload.update(self._build_pagination(page))
        sort_clause = self._build_sort(sort)
        if sort_clause:
            payload["sort"] = sort_clause
        aggs = self._build_aggs()
        if aggs:
            payload["aggs"] = aggs
        source = self._build_source()
        if source is not None:
            payload["_source"] = source
        return payload

    def _build_query(
        self,
        *,
        search_text: str | None,
        filters: list[FilterModel] | None,
    ) -> dict[str, Any] | None:
        return {"match_all": {}} if not search_text else None

    def _build_pagination(self, page: PageModel) -> dict[str, Any]:
        return {
            "from": (page.current - 1) * page.size,
            "size": page.size,
        }

    def _build_sort(self, sort: SortModel | None) -> list[dict[str, Any]] | None:
        if not sort:
            return None
        return [{sort.field: {"order": sort.direction}}]

    def _build_aggs(self) -> dict[str, Any] | None:
        return None

    def _build_source(self) -> list[str] | None:
        return None

    # -- mapping helpers ------------------------------------------------------

    @staticmethod
    def _map_hit(hit: dict[str, Any]) -> dict[str, Any]:
        source = hit.get("_source", {})
        source["_id"] = hit.get("_id")
        source["_score"] = hit.get("_score")
        return source

    @staticmethod
    def _extract_total(raw: dict[str, Any]) -> int:
        total = raw.get("hits", {}).get("total", 0)
        if isinstance(total, dict):
            return int(total.get("value", 0))
        return int(total)

    @staticmethod
    def _map_aggs_to_searchui(
        aggs: dict[str, Any],
    ) -> dict[str, FacetResponse]:
        facets: dict[str, FacetResponse] = {}
        for name, agg_data in aggs.items():
            buckets_raw = agg_data.get("buckets", [])
            buckets = [
                FacetBucket(
                    value=b.get("key_as_string", str(b["key"])), count=b["doc_count"]
                )
                for b in buckets_raw
                if b.get("doc_count", 0) > 0
            ]
            facet_type = (
                "range"
                if any("from" in b or "to" in b for b in buckets_raw)
                else "value"
            )
            facets[name] = FacetResponse(type=facet_type, data=buckets)
        return facets

    @staticmethod
    def _range_key(from_val: str | None, to_val: str | None) -> str:
        if from_val and to_val:
            return f"{from_val}-{to_val}"
        if from_val:
            return f"{from_val}-*"
        return f"*-{to_val}"

    @staticmethod
    def _range_query(
        field: str, from_val: str | None = None, to_val: str | None = None
    ) -> dict[str, Any]:
        range_clause: dict[str, Any] = {}
        if from_val:
            range_clause["gte"] = from_val
        if to_val:
            range_clause["lt"] = to_val
        return {"range": {field: range_clause}}
