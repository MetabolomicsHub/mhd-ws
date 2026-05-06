from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, Sequence

from mhd_ws.domain.entities.search.advanced_core.predicates import (
    AndExpr,
    BoolExpr,
    ExactMatchPredicate,
    NotExpr,
    OrExpr,
    PhraseMatchPredicate,
    RangePredicate,
    TermMatchPredicate,
)
from mhd_ws.domain.entities.search.advanced_core.registries import (
    FieldDef,
    IndexCapabilities,
)


class PredicateCompilerExtension(Protocol):
    def compile(
        self, expr: BoolExpr, compiler: "GenericEsDslCompiler"
    ) -> dict[str, Any] | None: ...


class GenericEsDslCompiler:
    def __init__(
        self,
        index_caps: IndexCapabilities,
        extensions: Sequence[PredicateCompilerExtension] = (),
    ) -> None:
        self._caps = index_caps
        self._extensions = tuple(extensions)

    def compile_query(self, expr: BoolExpr) -> dict[str, Any]:
        return self._compile(expr)

    def compile_pagination(self, page_current: int, page_size: int) -> dict[str, Any]:
        return {
            "from": (page_current - 1) * page_size,
            "size": page_size,
        }

    def compile_sort(self, field: str, direction: str) -> list[dict[str, Any]]:
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
                terms_agg = {"terms": {"field": cap.es_path, "size": facet_size}}
                if cap.nested:
                    if cap.nested.facet_filter:
                        aggs[field.facet_key] = {
                            "nested": {"path": cap.nested.path},
                            "aggs": {
                                "filtered": {
                                    "filter": cap.nested.facet_filter,
                                    "aggs": {"values": terms_agg},
                                }
                            },
                        }
                    else:
                        aggs[field.facet_key] = {
                            "nested": {"path": cap.nested.path},
                            "aggs": {"values": terms_agg},
                        }
                else:
                    aggs[field.facet_key] = terms_agg
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

    @staticmethod
    def compile_id_terms_composite_agg(
        agg_name: str, source_name: str, field_es_path: str, page_size: int
    ) -> dict[str, Any]:
        return {
            agg_name: {
                "composite": {
                    "size": page_size,
                    "sources": [
                        {source_name: {"terms": {"field": field_es_path}}},
                    ],
                }
            }
        }

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

        for extension in self._extensions:
            compiled = extension.compile(expr, self)
            if compiled is not None:
                return compiled

        raise TypeError(f"Unknown expression type: {type(expr)}")

    def _compile_and(self, expr: AndExpr) -> dict[str, Any]:
        if not expr.children:
            return {"match_all": {}}

        must: list[dict[str, Any]] = []
        filter_: list[dict[str, Any]] = []

        for child in expr.children:
            compiled = self._compile(child)
            if self.is_scored(child):
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
        return self.wrap_nested(pred.field_key, query)

    def _compile_phrase_match(self, pred: PhraseMatchPredicate) -> dict[str, Any]:
        cap = self._caps.get_field(pred.field_key)
        es_path = cap.es_path if cap else pred.field_key
        query: dict[str, Any] = {"match_phrase": {es_path: pred.value}}
        return self.wrap_nested(pred.field_key, query)

    def _compile_exact_match(self, pred: ExactMatchPredicate) -> dict[str, Any]:
        cap = self._caps.get_field(pred.field_key)
        if cap and cap.exact_es_path:
            es_path = cap.exact_es_path
        elif cap:
            es_path = cap.es_path
        else:
            es_path = pred.field_key
        query: dict[str, Any] = {"term": {es_path: pred.value}}
        return self.wrap_nested(pred.field_key, query)

    def _compile_range(self, pred: RangePredicate) -> dict[str, Any]:
        cap = self._caps.get_field(pred.field_key)
        es_path = cap.es_path if cap else pred.field_key
        if pred.op == "EQ":
            range_clause = {"gte": pred.value, "lte": pred.value}
        else:
            range_clause = {pred.op.lower(): pred.value}
        query: dict[str, Any] = {"range": {es_path: range_clause}}
        return self.wrap_nested(pred.field_key, query)

    def wrap_nested(self, field_key: str, query: dict[str, Any]) -> dict[str, Any]:
        cap = self._caps.get_field(field_key)
        if cap and cap.nested:
            return {"nested": {"path": cap.nested.path, "query": query}}
        return query

    def get_es_path(self, field_key: str, fallback: str) -> str:
        cap = self._caps.get_field(field_key)
        return cap.es_path if cap else fallback

    def get_exact_es_path(self, field_key: str, fallback: str) -> str:
        cap = self._caps.get_field(field_key)
        if cap and cap.exact_es_path:
            return cap.exact_es_path
        if cap:
            return cap.es_path
        return fallback

    @staticmethod
    def is_scored(expr: BoolExpr) -> bool:
        return isinstance(expr, (TermMatchPredicate, PhraseMatchPredicate))
