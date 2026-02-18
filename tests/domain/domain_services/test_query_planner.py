import pytest

from mhd_ws.domain.domain_services.query_planner import QueryPlanner
from mhd_ws.domain.entities.search.index_search_spec import (
    ComparatorClauseSpec,
    FieldRef,
    SearchSpec,
    Target,
    TermClauseSpec,
    ValueType,
)
from mhd_ws.domain.entities.search.predicate_tree import (
    AndExpr,
    ExactMatchPredicate,
    NotExpr,
    OrExpr,
    PhraseMatchPredicate,
    TermMatchPredicate,
)
from mhd_ws.domain.entities.search.stages import (
    DatasetSearchStage,
    MetaboliteIdStage,
)


@pytest.fixture
def planner() -> QueryPlanner:
    return QueryPlanner()


def _dataset_term_clause(**kwargs) -> TermClauseSpec:
    defaults = dict(
        field=FieldRef(
            field_key="dataset.title", target=Target.DATASET, value_type=ValueType.TEXT
        ),
        combine_within_field="AND",
        terms=["cancer"],
        match="AUTO",
    )
    defaults.update(kwargs)
    return TermClauseSpec(**defaults)


def _metabolite_term_clause(**kwargs) -> TermClauseSpec:
    defaults = dict(
        field=FieldRef(
            field_key="metabolite.name",
            target=Target.METABOLITE,
            value_type=ValueType.TEXT,
        ),
        combine_within_field="OR",
        terms=["glucose"],
        match="AUTO",
    )
    defaults.update(kwargs)
    return TermClauseSpec(**defaults)


class TestStagePlanning:
    def test_dataset_only_single_stage(self, planner: QueryPlanner) -> None:
        spec = SearchSpec(clauses=[_dataset_term_clause()])
        plan = planner.plan(spec)

        assert len(plan.stages) == 1
        assert isinstance(plan.stages[0], DatasetSearchStage)
        assert plan.stages[0].constraints == []

    def test_metabolite_only_two_stages(self, planner: QueryPlanner) -> None:
        spec = SearchSpec(clauses=[_metabolite_term_clause()])
        plan = planner.plan(spec)

        assert len(plan.stages) == 2
        assert isinstance(plan.stages[0], MetaboliteIdStage)
        assert isinstance(plan.stages[1], DatasetSearchStage)
        assert len(plan.stages[1].constraints) == 1

    def test_mixed_clauses_partitioned(self, planner: QueryPlanner) -> None:
        spec = SearchSpec(
            clauses=[_dataset_term_clause(), _metabolite_term_clause()]
        )
        plan = planner.plan(spec)

        assert len(plan.stages) == 2
        met_stage = plan.stages[0]
        ds_stage = plan.stages[1]
        assert isinstance(met_stage, MetaboliteIdStage)
        assert isinstance(ds_stage, DatasetSearchStage)


class TestPredicateGeneration:
    def test_query_text_injected(self, planner: QueryPlanner) -> None:
        spec = SearchSpec(query_text="proteomics")
        plan = planner.plan(spec)

        ds_stage = plan.stages[0]
        assert isinstance(ds_stage, DatasetSearchStage)
        pred = ds_stage.dataset_predicate
        # Empty clauses produce AndExpr([]), then query_text is appended as child
        assert isinstance(pred, AndExpr)
        assert len(pred.children) == 1
        qt_pred = pred.children[0]
        assert isinstance(qt_pred, TermMatchPredicate)
        assert qt_pred.field_key == "dataset.search_text"
        assert qt_pred.value == "proteomics"

    def test_query_text_with_clauses(self, planner: QueryPlanner) -> None:
        spec = SearchSpec(
            query_text="proteomics",
            clauses=[_dataset_term_clause()],
        )
        plan = planner.plan(spec)
        pred = plan.stages[0].dataset_predicate
        assert isinstance(pred, AndExpr)
        # Should have the clause predicate + query_text predicate
        assert len(pred.children) == 2

    def test_negation_wrapping(self, planner: QueryPlanner) -> None:
        spec = SearchSpec(
            clauses=[_dataset_term_clause(negated=True)]
        )
        plan = planner.plan(spec)
        pred = plan.stages[0].dataset_predicate
        assert isinstance(pred, NotExpr)

    def test_auto_on_text_produces_term_match(self, planner: QueryPlanner) -> None:
        spec = SearchSpec(
            clauses=[
                _dataset_term_clause(
                    field=FieldRef(
                        field_key="dataset.title",
                        target=Target.DATASET,
                        value_type=ValueType.TEXT,
                    ),
                    match="AUTO",
                )
            ]
        )
        plan = planner.plan(spec)
        pred = plan.stages[0].dataset_predicate
        assert isinstance(pred, TermMatchPredicate)

    def test_auto_on_keyword_produces_exact_match(self, planner: QueryPlanner) -> None:
        spec = SearchSpec(
            clauses=[
                TermClauseSpec(
                    field=FieldRef(
                        field_key="dataset.facets.organisms",
                        target=Target.DATASET,
                        value_type=ValueType.KEYWORD,
                    ),
                    combine_within_field="OR",
                    terms=["Homo sapiens"],
                    match="AUTO",
                )
            ]
        )
        plan = planner.plan(spec)
        pred = plan.stages[0].dataset_predicate
        assert isinstance(pred, ExactMatchPredicate)

    def test_phrase_match_mode(self, planner: QueryPlanner) -> None:
        spec = SearchSpec(
            clauses=[_dataset_term_clause(match="PHRASE")]
        )
        plan = planner.plan(spec)
        pred = plan.stages[0].dataset_predicate
        assert isinstance(pred, PhraseMatchPredicate)

    def test_multiple_terms_combined_with_or(self, planner: QueryPlanner) -> None:
        spec = SearchSpec(
            clauses=[
                _dataset_term_clause(
                    combine_within_field="OR",
                    terms=["cancer", "tumor"],
                )
            ]
        )
        plan = planner.plan(spec)
        pred = plan.stages[0].dataset_predicate
        assert isinstance(pred, OrExpr)
        assert len(pred.children) == 2

    def test_empty_clauses_produces_match_all(self, planner: QueryPlanner) -> None:
        spec = SearchSpec()
        plan = planner.plan(spec)
        pred = plan.stages[0].dataset_predicate
        assert isinstance(pred, AndExpr)
        assert pred.children == []
