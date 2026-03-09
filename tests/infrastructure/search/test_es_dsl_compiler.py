import pytest

from mhd_ws.domain.entities.search.predicate_tree import (
    AndExpr,
    ExactMatchPredicate,
    NotExpr,
    OrExpr,
    PhraseMatchPredicate,
    RangePredicate,
    TermMatchPredicate,
)
from mhd_ws.domain.entities.search.registries.field_registry import FIELD_REGISTRY
from mhd_ws.domain.entities.search.registries.index_capability_registry import (
    INDEX_CAPABILITIES,
)
from mhd_ws.infrastructure.search.es.es_dsl_compiler import EsDslCompiler


@pytest.fixture
def dataset_compiler() -> EsDslCompiler:
    caps = INDEX_CAPABILITIES.get_index_strict("dataset-index")
    return EsDslCompiler(caps)


@pytest.fixture
def ms_dataset_compiler() -> EsDslCompiler:
    caps = INDEX_CAPABILITIES.get_index_strict("ms-dataset-index")
    return EsDslCompiler(caps)


@pytest.fixture
def metabolite_compiler() -> EsDslCompiler:
    caps = INDEX_CAPABILITIES.get_index_strict("metabolite-index")
    return EsDslCompiler(caps)


@pytest.fixture
def facet_fields() -> list:
    return [f for f in FIELD_REGISTRY.fields if f.facet_key is not None]


class TestLeafPredicates:
    def test_term_match_on_text(self, dataset_compiler: EsDslCompiler) -> None:
        pred = TermMatchPredicate(field_key="dataset.title", value="cancer")
        result = dataset_compiler.compile_query(pred)
        assert result == {"match": {"study.title": "cancer"}}

    def test_phrase_match(self, dataset_compiler: EsDslCompiler) -> None:
        pred = PhraseMatchPredicate(field_key="dataset.title", value="breast cancer")
        result = dataset_compiler.compile_query(pred)
        assert result == {"match_phrase": {"study.title": "breast cancer"}}

    def test_exact_match_uses_exact_es_path(self, dataset_compiler: EsDslCompiler) -> None:
        pred = ExactMatchPredicate(field_key="dataset.title", value="My Study")
        result = dataset_compiler.compile_query(pred)
        assert result == {"term": {"study.title.keyword": "My Study"}}

    def test_exact_match_keyword_field(self, dataset_compiler: EsDslCompiler) -> None:
        pred = ExactMatchPredicate(
            field_key="dataset.facets.organisms", value="Homo sapiens"
        )
        result = dataset_compiler.compile_query(pred)
        assert result == {"term": {"facets.organisms": "Homo sapiens"}}

    def test_range_gt(self, dataset_compiler: EsDslCompiler) -> None:
        pred = RangePredicate(field_key="dataset.title", op="GT", value=100)
        result = dataset_compiler.compile_query(pred)
        assert result == {"range": {"study.title": {"gt": 100}}}

    def test_range_lte(self, dataset_compiler: EsDslCompiler) -> None:
        pred = RangePredicate(field_key="dataset.title", op="LTE", value=50)
        result = dataset_compiler.compile_query(pred)
        assert result == {"range": {"study.title": {"lte": 50}}}

    def test_range_eq(self, dataset_compiler: EsDslCompiler) -> None:
        pred = RangePredicate(field_key="dataset.title", op="EQ", value=42)
        result = dataset_compiler.compile_query(pred)
        assert result == {"range": {"study.title": {"gte": 42, "lte": 42}}}


class TestNestedWrapping:
    def test_nested_field_wrapped(self, dataset_compiler: EsDslCompiler) -> None:
        pred = TermMatchPredicate(
            field_key="dataset.people.full_name", value="John"
        )
        result = dataset_compiler.compile_query(pred)
        assert result == {
            "nested": {
                "path": "people",
                "query": {"match": {"people.full_name": "John"}},
            }
        }

    def test_nested_exact_match(self, dataset_compiler: EsDslCompiler) -> None:
        pred = ExactMatchPredicate(
            field_key="dataset.people.full_name", value="John Smith"
        )
        result = dataset_compiler.compile_query(pred)
        assert result == {
            "nested": {
                "path": "people",
                "query": {"term": {"people.full_name.keyword": "John Smith"}},
            }
        }

    def test_metabolite_nested_identifiers(
        self, metabolite_compiler: EsDslCompiler
    ) -> None:
        pred = ExactMatchPredicate(
            field_key="metabolite.identifiers.accession", value="HMDB0000122"
        )
        result = metabolite_compiler.compile_query(pred)
        assert result == {
            "nested": {
                "path": "metabolite.identifiers",
                "query": {
                    "term": {"metabolite.identifiers.accession": "HMDB0000122"}
                },
            }
        }


class TestBooleanComposition:
    def test_and_expr(self, dataset_compiler: EsDslCompiler) -> None:
        expr = AndExpr(
            children=[
                TermMatchPredicate(field_key="dataset.title", value="cancer"),
                ExactMatchPredicate(
                    field_key="dataset.facets.organisms", value="Homo sapiens"
                ),
            ]
        )
        result = dataset_compiler.compile_query(expr)
        assert "bool" in result
        # TermMatch is scored → must; ExactMatch is filter
        assert result["bool"]["must"] == [{"match": {"study.title": "cancer"}}]
        assert result["bool"]["filter"] == [
            {"term": {"facets.organisms": "Homo sapiens"}}
        ]

    def test_or_expr(self, dataset_compiler: EsDslCompiler) -> None:
        expr = OrExpr(
            children=[
                TermMatchPredicate(field_key="dataset.title", value="cancer"),
                TermMatchPredicate(field_key="dataset.title", value="tumor"),
            ]
        )
        result = dataset_compiler.compile_query(expr)
        assert result == {
            "bool": {
                "should": [
                    {"match": {"study.title": "cancer"}},
                    {"match": {"study.title": "tumor"}},
                ],
                "minimum_should_match": 1,
            }
        }

    def test_not_expr(self, dataset_compiler: EsDslCompiler) -> None:
        expr = NotExpr(
            child=TermMatchPredicate(field_key="dataset.title", value="cancer")
        )
        result = dataset_compiler.compile_query(expr)
        assert result == {
            "bool": {"must_not": [{"match": {"study.title": "cancer"}}]}
        }

    def test_empty_and_produces_match_all(self, dataset_compiler: EsDslCompiler) -> None:
        expr = AndExpr(children=[])
        result = dataset_compiler.compile_query(expr)
        assert result == {"match_all": {}}


class TestFacetAggregations:
    def test_facet_aggs_keys(
        self, ms_dataset_compiler: EsDslCompiler, facet_fields: list
    ) -> None:
        aggs = ms_dataset_compiler.compile_facet_aggs(facet_fields)
        assert "organisms" in aggs
        assert "diseases" in aggs
        assert "submission_date" in aggs
        assert "public_release_date" in aggs
        assert "repository" in aggs

    def test_value_facet_structure(
        self, ms_dataset_compiler: EsDslCompiler, facet_fields: list
    ) -> None:
        aggs = ms_dataset_compiler.compile_facet_aggs(facet_fields, facet_size=10)
        assert aggs["organisms"] == {
            "terms": {"field": "facets.organisms", "size": 10}
        }

    def test_range_facet_structure(
        self, ms_dataset_compiler: EsDslCompiler, facet_fields: list
    ) -> None:
        aggs = ms_dataset_compiler.compile_facet_aggs(facet_fields)
        assert "date_range" in aggs["submission_date"]
        assert aggs["submission_date"]["date_range"]["field"] == "dates.submission"
        assert len(aggs["submission_date"]["date_range"]["ranges"]) > 0


class TestCompositeAgg:
    def test_metabolite_composite_agg(
        self, metabolite_compiler: EsDslCompiler
    ) -> None:
        result = metabolite_compiler.compile_metabolite_composite_agg(
            "dataset_id", page_size=500
        )
        assert result == {
            "dataset_ids": {
                "composite": {
                    "size": 500,
                    "sources": [
                        {"dataset_id": {"terms": {"field": "dataset_id"}}}
                    ],
                }
            }
        }
