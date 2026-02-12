from __future__ import annotations

import logging
from typing import Any

from mhd_ws.domain.entities.search.index_search import FilterModel, SortModel
from mhd_ws.domain.entities.search.legacy.facet_configuration import (
    LEGACY_FACET_CONFIG,
    RangeFacetConfig,
)
from mhd_ws.infrastructure.search.es.base_es_gateway import BaseElasticSearchGateway
from mhd_ws.infrastructure.search.es.es_configuration import (
    LegacyElasticSearchConfiguration,
)
from mhd_ws.infrastructure.search.es_client import ElasticsearchClient

logger = logging.getLogger(__name__)


class ElasticsearchLegacyGateway(BaseElasticSearchGateway):
    def __init__(
        self,
        client: ElasticsearchClient,
        config: LegacyElasticSearchConfiguration | None = None,
    ):
        self._legacy_config = config or LegacyElasticSearchConfiguration()
        super().__init__(client=client, config=self._legacy_config)

    # -- query ----------------------------------------------------------------

    def _build_query(
        self,
        *,
        search_text: str | None,
        filters: list[FilterModel] | None,
    ) -> dict[str, Any] | None:
        must_clauses: list[dict[str, Any]] = []
        filter_clauses: list[dict[str, Any]] = []

        if search_text:
            must_clauses.append(self._text_query(search_text))

        if filters:
            for f in filters:
                filter_clauses.append(self._filter_clause(f))

        if not must_clauses and not filter_clauses:
            return {"match_all": {}}

        bool_query: dict[str, Any] = {}
        if must_clauses:
            bool_query["must"] = must_clauses
        if filter_clauses:
            bool_query["filter"] = filter_clauses
        return {"bool": bool_query}

    def _text_query(self, text: str) -> dict[str, Any]:
        should: list[dict[str, Any]] = [
            {
                "multi_match": {
                    "query": text,
                    "fields": list(self._legacy_config.search_fields),
                    "type": "best_fields",
                    "operator": "or",
                }
            }
        ]
        for nested_field in self._legacy_config.nested_search_fields:
            should.append(
                {
                    "nested": {
                        "path": nested_field.path,
                        "query": {
                            "match": {
                                f"{nested_field.path}.{nested_field.field}": text
                            }
                        },
                    }
                }
            )
        return {"bool": {"should": should, "minimum_should_match": 1}}

    @staticmethod
    def _filter_clause(f: FilterModel) -> dict[str, Any]:
        if f.operator == "all":
            return {
                "bool": {
                    "must": [{"term": {f.field: v}} for v in f.values]
                }
            }
        if f.operator == "none":
            return {
                "bool": {
                    "must_not": [{"terms": {f.field: f.values}}]
                }
            }
        # default: "any"
        return {"terms": {f.field: f.values}}

    # -- aggregations ---------------------------------------------------------

    def _build_aggs(self) -> dict[str, Any] | None:
        aggs: dict[str, Any] = {}
        for name, facet_cfg in LEGACY_FACET_CONFIG.items():
            if isinstance(facet_cfg, RangeFacetConfig):
                aggs[name] = {
                    "date_range": {
                        "field": facet_cfg.field,
                        "ranges": facet_cfg.build_ranges(),
                    }
                }
            else:
                aggs[name] = {
                    "terms": {
                        "field": facet_cfg.field,
                        "size": self._legacy_config.facet_size,
                    }
                }
        return aggs or None

    # -- sort -----------------------------------------------------------------

    def _build_sort(self, sort: SortModel | None) -> list[dict[str, Any]] | None:
        if not sort:
            return [{"_score": {"order": "desc"}}]
        return [{sort.field: {"order": sort.direction}}]

    # -- source ---------------------------------------------------------------

    def _build_source(self) -> list[str] | None:
        return self._legacy_config.source_includes
