import pytest

from mhd_ws.domain.domain_services.search_spec_resolver import SearchSpecResolver
from mhd_ws.domain.entities.search.dtos import (
    ComparatorClauseDTO,
    SearchRequestDTO,
    TermClauseDTO,
)
from mhd_ws.domain.entities.search.index_search_spec import (
    Target,
    ValueType,
)
from mhd_ws.domain.entities.search.registries.field_registry import FIELD_REGISTRY


@pytest.fixture
def resolver() -> SearchSpecResolver:
    return SearchSpecResolver(FIELD_REGISTRY)


class TestTermClauseResolution:
    def test_valid_term_clause_resolves(self, resolver: SearchSpecResolver) -> None:
        dto = SearchRequestDTO(
            clauses=[
                TermClauseDTO(
                    field_id="dataset_title",
                    op="AND",
                    terms=["cancer"],
                    match="AUTO",
                )
            ]
        )
        spec = resolver.resolve(dto)

        assert len(spec.clauses) == 1
        clause = spec.clauses[0]
        assert clause.kind == "terms"
        assert clause.field.field_key == "dataset.title"
        assert clause.field.target == Target.DATASET
        assert clause.field.value_type == ValueType.TEXT
        assert clause.terms == ["cancer"]

    def test_metabolite_field_resolves(self, resolver: SearchSpecResolver) -> None:
        dto = SearchRequestDTO(
            clauses=[
                TermClauseDTO(
                    field_id="metabolite_name",
                    op="OR",
                    terms=["glucose", "fructose"],
                    match="PHRASE",
                )
            ]
        )
        spec = resolver.resolve(dto)

        clause = spec.clauses[0]
        assert clause.field.target == Target.METABOLITE
        assert clause.field.field_key == "metabolite.name"
        assert clause.match == "PHRASE"

    def test_unknown_field_id_raises(self, resolver: SearchSpecResolver) -> None:
        dto = SearchRequestDTO(
            clauses=[
                TermClauseDTO(
                    field_id="nonexistent_field",
                    op="AND",
                    terms=["test"],
                )
            ]
        )
        with pytest.raises(ValueError, match="Unknown field_id"):
            resolver.resolve(dto)

    def test_disallowed_match_mode_raises(self, resolver: SearchSpecResolver) -> None:
        dto = SearchRequestDTO(
            clauses=[
                TermClauseDTO(
                    field_id="facet_organisms",
                    op="AND",
                    terms=["Homo sapiens"],
                    match="PHRASE",  # facet_organisms only allows EXACT
                )
            ]
        )
        with pytest.raises(ValueError, match="Match mode"):
            resolver.resolve(dto)

    def test_disallowed_intra_combiner_raises(
        self, resolver: SearchSpecResolver
    ) -> None:
        dto = SearchRequestDTO(
            clauses=[
                TermClauseDTO(
                    field_id="dataset_id",
                    op="AND",  # dataset_id only allows OR
                    terms=["MTBLS1"],
                    match="EXACT",
                )
            ]
        )
        with pytest.raises(ValueError, match="Intra-field combiner"):
            resolver.resolve(dto)


class TestComparatorClauseResolution:
    def test_disallowed_comparator_raises(self, resolver: SearchSpecResolver) -> None:
        dto = SearchRequestDTO(
            clauses=[
                ComparatorClauseDTO(
                    field_id="dataset_title",  # does not allow comparators
                    op="GT",
                    value=100,
                )
            ]
        )
        with pytest.raises(ValueError, match="does not support comparator"):
            resolver.resolve(dto)


class TestEdgeCases:
    def test_empty_clauses_with_query_text(self, resolver: SearchSpecResolver) -> None:
        dto = SearchRequestDTO(query_text="proteomics")
        spec = resolver.resolve(dto)

        assert spec.query_text == "proteomics"
        assert spec.clauses == []

    def test_negated_clause_passes_through(self, resolver: SearchSpecResolver) -> None:
        dto = SearchRequestDTO(
            clauses=[
                TermClauseDTO(
                    field_id="dataset_title",
                    op="AND",
                    terms=["cancer"],
                    match="AUTO",
                    **{"not": True},
                )
            ]
        )
        spec = resolver.resolve(dto)
        assert spec.clauses[0].negated is True
