from __future__ import annotations

from typing import Any

from datetime import datetime

from mhd_ws.domain.entities.search.predicate_tree import (
    AndExpr,
    BoolExpr,
    ExactMatchPredicate,
    NotExpr,
    OrExpr,
    PhraseMatchPredicate,
    RangePredicate,
    TermMatchPredicate,
)
from mhd_ws.domain.entities.search.registries.models import FieldDef, IndexCapabilities


class EsDslCompiler:
    def __init__(self, index_caps: IndexCapabilities) -> None:
        self._caps = index_caps

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile_query(self, expr: BoolExpr) -> dict[str, Any]:
        return self._compile(expr)

    def compile_pagination(
        self, page_current: int, page_size: int
    ) -> dict[str, Any]:
        return {
            "from": (page_current - 1) * page_size,
            "size": page_size,
        }

    def compile_sort(
        self, field: str, direction: str
    ) -> list[dict[str, Any]]:
        return [{field: {"order": direction}}]

    def compile_facet_aggs(
        self, facet_fields: list[FieldDef], facet_size: int = 25
    ) -> dict[str, Any]:
        aggs: dict[str, Any] = {}
        for field in facet_fields:
            if not field.facet_key or not field.facet_type:
                continue
            cap = self._caps.get_field(field.field_key)
            if cap is None:
                continue
            if field.facet_type == "date_histogram":
                aggs[field.facet_key] = {
                    "date_histogram": {
                        "field": cap.es_path,
                        "calendar_interval": "year",
                        "format": "yyyy",
                        "order": {"_key": "desc"},
                        "min_doc_count": 1,
                    }
                }
            elif field.facet_type == "range":
                aggs[field.facet_key] = {
                    "date_range": {
                        "field": cap.es_path,
                        "ranges": self._build_year_ranges(),
                    }
                }
            elif field.facet_type == "value":
                if cap.nested:
                    aggs[field.facet_key] = {
                        "nested": {"path": cap.nested.path},
                        "aggs": {
                            "values": {"terms": {"field": cap.es_path, "size": facet_size}}
                        },
                    }
                else:
                    aggs[field.facet_key] = {
                        "terms": {"field": cap.es_path, "size": facet_size}
                    }
        return aggs

    @staticmethod
    def _build_year_ranges() -> list[dict]:
        current_year = datetime.now().year
        ranges: list[dict] = []
        for year in range(current_year, current_year - 20, -1):
            ranges.append(
                {
                    "from": f"{year}-01-01",
                    "to": f"{year + 1}-01-01",
                    "key": str(year),
                }
            )
        ranges.append(
            {"to": f"{current_year - 19}-01-01", "key": f"Before {current_year - 19}"}
        )
        return ranges

    def compile_metabolite_composite_agg(
        self, dataset_id_es_path: str, page_size: int
    ) -> dict[str, Any]:
        return {
            "dataset_ids": {
                "composite": {
                    "size": page_size,
                    "sources": [
                        {"dataset_id": {"terms": {"field": dataset_id_es_path}}}
                    ],
                }
            }
        }

    # ------------------------------------------------------------------
    # Recursive compilation
    # ------------------------------------------------------------------

    def _compile(self, expr: BoolExpr) -> dict[str, Any]:
        if isinstance(expr, AndExpr):
            return self._compile_and(expr)
        if isinstance(expr, OrExpr):
            return self._compile_or(expr)
        if isinstance(expr, NotExpr):
            return self._compile_not(expr)
        if isinstance(expr, TermMatchPredicate):
            return self._compile_term_match(expr)
        if isinstance(expr, PhraseMatchPredicate):
            return self._compile_phrase_match(expr)
        if isinstance(expr, ExactMatchPredicate):
            return self._compile_exact_match(expr)
        if isinstance(expr, RangePredicate):
            return self._compile_range(expr)
        raise TypeError(f"Unknown expression type: {type(expr)}")

    def _compile_and(self, expr: AndExpr) -> dict[str, Any]:
        if not expr.children:
            return {"match_all": {}}

        must: list[dict[str, Any]] = []
        filter_: list[dict[str, Any]] = []

        for child in expr.children:
            compiled = self._compile(child)
            if self._is_scored(child):
                must.append(compiled)
            else:
                filter_.append(compiled)

        clause: dict[str, Any] = {}
        if must:
            clause["must"] = must
        if filter_:
            clause["filter"] = filter_
        return {"bool": clause}

    def _compile_or(self, expr: OrExpr) -> dict[str, Any]:
        should = [self._compile(child) for child in expr.children]
        return {"bool": {"should": should, "minimum_should_match": 1}}

    def _compile_not(self, expr: NotExpr) -> dict[str, Any]:
        return {"bool": {"must_not": [self._compile(expr.child)]}}

    def _compile_term_match(self, pred: TermMatchPredicate) -> dict[str, Any]:
        cap = self._caps.get_field(pred.field_key)
        es_path = cap.es_path if cap else pred.field_key
        query: dict[str, Any] = {"match": {es_path: pred.value}}
        return self._maybe_nested(pred.field_key, query)

    def _compile_phrase_match(self, pred: PhraseMatchPredicate) -> dict[str, Any]:
        cap = self._caps.get_field(pred.field_key)
        es_path = cap.es_path if cap else pred.field_key
        query: dict[str, Any] = {"match_phrase": {es_path: pred.value}}
        return self._maybe_nested(pred.field_key, query)

    def _compile_exact_match(self, pred: ExactMatchPredicate) -> dict[str, Any]:
        cap = self._caps.get_field(pred.field_key)
        if cap and cap.exact_es_path:
            es_path = cap.exact_es_path
        elif cap:
            es_path = cap.es_path
        else:
            es_path = pred.field_key
        query: dict[str, Any] = {"term": {es_path: pred.value}}
        return self._maybe_nested(pred.field_key, query)

    def _compile_range(self, pred: RangePredicate) -> dict[str, Any]:
        cap = self._caps.get_field(pred.field_key)
        es_path = cap.es_path if cap else pred.field_key
        op = pred.op
        if op == "EQ":
            range_clause = {"gte": pred.value, "lte": pred.value}
        else:
            range_clause = {op.lower(): pred.value}
        query: dict[str, Any] = {"range": {es_path: range_clause}}
        return self._maybe_nested(pred.field_key, query)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _maybe_nested(self, field_key: str, query: dict[str, Any]) -> dict[str, Any]:
        cap = self._caps.get_field(field_key)
        if cap and cap.nested:
            return {"nested": {"path": cap.nested.path, "query": query}}
        return query

    @staticmethod
    def _is_scored(expr: BoolExpr) -> bool:
        return isinstance(expr, (TermMatchPredicate, PhraseMatchPredicate))
