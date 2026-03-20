from __future__ import annotations

import logging
import uuid
from typing import Any

from mhd_ws.application.services.interfaces.advanced_search_port import (
    AdvancedSearchPort,
)
from mhd_ws.domain.entities.search.index_search import (
    FacetBucket,
    FacetResponse,
    IndexSearchResult,
    PageModel,
    SortModel,
)
from mhd_ws.domain.entities.search.index_search_spec import SearchSpec
from mhd_ws.domain.entities.search.predicate_tree import AndExpr
from mhd_ws.domain.entities.search.registries.models import (
    FieldRegistry,
    IndexCapabilitiesRegistry,
)
from mhd_ws.domain.entities.search.stages import (
    DatasetSearchStage,
    MetaboliteIdStage,
    QueryPlan,
)
from mhd_ws.domain.domain_services.query_planner import QueryPlanner
from mhd_ws.infrastructure.search.es.es_configuration import (
    AdvancedSearchConfiguration,
)
from mhd_ws.infrastructure.search.es.es_dsl_compiler import EsDslCompiler
from mhd_ws.infrastructure.search.es_client import ElasticsearchClient

logger = logging.getLogger(__name__)


class AdvancedSearchGateway(AdvancedSearchPort):
    def __init__(
        self,
        client: ElasticsearchClient,
        config: AdvancedSearchConfiguration,
        planner: QueryPlanner,
        index_registry: IndexCapabilitiesRegistry,
        field_registry: FieldRegistry,
        facet_size: int = 25,
    ) -> None:
        self._client = client
        self._config = config
        self._planner = planner
        self._index_registry = index_registry
        self._facet_size = facet_size
        self._facet_fields = [f for f in field_registry.fields if f.facet_key is not None]

    async def get_index_mapping(self) -> dict[str, Any]:
        index_caps = self._index_registry.get_index_strict("ms-dataset-index")
        return await self._client.get_mapping(
            index=index_caps.concrete_index_or_alias,
            api_key_name=index_caps.api_key_name,
        )

    async def advanced_search(
        self,
        spec: SearchSpec,
        page: PageModel | None = None,
        sort: SortModel | None = None,
    ) -> IndexSearchResult:
        page = page or PageModel()
        plan = self._planner.plan(spec)

        dataset_ids: set[str] | None = None
        for stage in plan.stages:
            if isinstance(stage, MetaboliteIdStage):
                dataset_ids = await self._execute_metabolite_stage(stage)
            elif isinstance(stage, DatasetSearchStage):
                return await self._execute_dataset_stage(
                    stage, plan, page, sort, dataset_ids
                )

        return IndexSearchResult(request_id=str(uuid.uuid4()))

    # ------------------------------------------------------------------
    # Stage executors
    # ------------------------------------------------------------------

    async def _execute_metabolite_stage(
        self, stage: MetaboliteIdStage
    ) -> set[str]:
        index_caps = self._index_registry.get_index_strict(stage.index_key)
        compiler = EsDslCompiler(index_caps)
        query = compiler.compile_query(stage.metabolite_predicate)

        join_field = index_caps.get_field_strict(
            index_caps.join.dataset_id_field_key
        )
        dataset_id_es_path = join_field.es_path

        collected_ids: set[str] = set()
        after_key: dict[str, Any] | None = None
        max_ids = stage.output.max_ids

        while True:
            aggs = compiler.compile_metabolite_composite_agg(
                dataset_id_es_path, page_size=min(1000, max_ids)
            )
            if after_key:
                aggs["dataset_ids"]["composite"]["after"] = after_key

            body: dict[str, Any] = {"size": 0, "query": query, "aggs": aggs}
            raw = await self._client.search(
                index=index_caps.concrete_index_or_alias,
                body=body,
                api_key_name=index_caps.api_key_name,
            )

            composite_agg = raw.get("aggregations", {}).get("dataset_ids", {})
            buckets = composite_agg.get("buckets", [])

            for bucket in buckets:
                collected_ids.add(str(bucket["key"]["dataset_id"]))
                if len(collected_ids) >= max_ids:
                    break

            if not buckets or len(collected_ids) >= max_ids:
                break

            after_key = composite_agg.get("after_key")
            if after_key is None:
                break

        logger.debug(
            "Metabolite stage collected %d dataset IDs", len(collected_ids)
        )
        return collected_ids

    async def _execute_dataset_stage(
        self,
        stage: DatasetSearchStage,
        plan: QueryPlan,
        page: PageModel,
        sort: SortModel | None,
        dataset_ids: set[str] | None,
    ) -> IndexSearchResult:
        index_caps = self._index_registry.get_index_strict(stage.index_key)
        compiler = EsDslCompiler(index_caps)

        query_dsl = compiler.compile_query(stage.dataset_predicate)

        if dataset_ids is not None and stage.constraints:
            join_field = index_caps.get_field_strict(
                index_caps.join.dataset_id_field_key
            )
            id_filter = {
                "terms": {join_field.es_path: sorted(dataset_ids)}
            }
            if "bool" in query_dsl:
                query_dsl["bool"].setdefault("filter", []).append(id_filter)
            else:
                query_dsl = {"bool": {"must": [query_dsl], "filter": [id_filter]}}

        body: dict[str, Any] = {"query": query_dsl}
        body.update(compiler.compile_pagination(page.current, page.size))

        if sort:
            body["sort"] = compiler.compile_sort(sort.field, sort.direction)
        else:
            body["sort"] = [{"_score": {"order": "desc"}}]

        body["aggs"] = compiler.compile_facet_aggs(self._facet_fields, self._facet_size)

        logger.debug(
            "Advanced search payload for index=%s: %s",
            index_caps.concrete_index_or_alias,
            body,
        )

        raw = await self._client.search(
            index=index_caps.concrete_index_or_alias,
            body=body,
            api_key_name=index_caps.api_key_name,
        )

        results = [self._map_hit(hit) for hit in raw.get("hits", {}).get("hits", [])]
        total = self._extract_total(raw)
        facets = self._map_aggs(raw.get("aggregations", {}))

        return IndexSearchResult(
            results=results,
            total_results=total,
            facets=facets,
            request_id=str(uuid.uuid4()),
        )

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

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
    def _map_aggs(aggs: dict[str, Any]) -> dict[str, FacetResponse]:
        facets: dict[str, FacetResponse] = {}
        for name, agg_data in aggs.items():
            # Nested agg: no top-level "buckets"; inner sub-agg is named "values"
            if "buckets" not in agg_data and "values" in agg_data:
                buckets_raw = agg_data["values"].get("buckets", [])
                facet_type = "value"
            else:
                buckets_raw = agg_data.get("buckets", [])
                facet_type = (
                    "range"
                    if any("from" in b or "to" in b for b in buckets_raw)
                    else "value"
                )
            buckets = [
                FacetBucket(
                    value=b.get("key_as_string", str(b["key"])), count=b["doc_count"]
                )
                for b in buckets_raw
                if b.get("doc_count", 0) > 0
            ]
            facets[name] = FacetResponse(type=facet_type, data=buckets)
        return facets
