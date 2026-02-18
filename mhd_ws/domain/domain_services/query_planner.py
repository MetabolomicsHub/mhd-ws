from __future__ import annotations

from mhd_ws.domain.entities.search.index_search_spec import (
    ComparatorClauseSpec,
    FieldClauseSpec,
    SearchSpec,
    Target,
    TermClauseSpec,
    ValueType,
)
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
from mhd_ws.domain.entities.search.stages import (
    DatasetIdConstraint,
    DatasetSearchStage,
    MetaboliteIdStage,
    QueryPlan,
)


class QueryPlanner:
    def plan(self, spec: SearchSpec) -> QueryPlan:
        dataset_clauses: list[FieldClauseSpec] = []
        metabolite_clauses: list[FieldClauseSpec] = []

        for clause in spec.clauses:
            if clause.field.target == Target.DATASET:
                dataset_clauses.append(clause)
            else:
                metabolite_clauses.append(clause)

        dataset_predicates = self._compile_clauses(
            dataset_clauses, spec.inter_field_combiner
        )

        if spec.query_text:
            qt_pred = TermMatchPredicate(
                field_key="dataset.search_text", value=spec.query_text
            )
            if dataset_predicates.kind == "AND":
                dataset_predicates = AndExpr(
                    children=[*dataset_predicates.children, qt_pred]
                )
            else:
                dataset_predicates = AndExpr(children=[dataset_predicates, qt_pred])

        if metabolite_clauses:
            met_predicate = self._compile_clauses(
                metabolite_clauses, spec.inter_field_combiner
            )
            met_stage = MetaboliteIdStage(metabolite_predicate=met_predicate)
            ds_stage = DatasetSearchStage(
                dataset_predicate=dataset_predicates,
                constraints=[DatasetIdConstraint()],
            )
            return QueryPlan(stages=[met_stage, ds_stage])

        ds_stage = DatasetSearchStage(dataset_predicate=dataset_predicates)
        return QueryPlan(stages=[ds_stage])

    def _compile_clauses(
        self, clauses: list[FieldClauseSpec], inter_combiner: str
    ) -> BoolExpr:
        if not clauses:
            return AndExpr(children=[])

        predicates: list[BoolExpr] = []
        for clause in clauses:
            expr = self._clause_to_expr(clause)
            if clause.negated:
                expr = NotExpr(child=expr)
            predicates.append(expr)

        if len(predicates) == 1:
            return predicates[0]

        if inter_combiner == "AND":
            return AndExpr(children=predicates)
        return OrExpr(children=predicates)

    def _clause_to_expr(self, clause: FieldClauseSpec) -> BoolExpr:
        if isinstance(clause, TermClauseSpec):
            return self._term_clause_to_expr(clause)
        if isinstance(clause, ComparatorClauseSpec):
            return RangePredicate(
                field_key=clause.field.field_key,
                op=clause.comparator,
                value=clause.value,
            )
        raise TypeError(f"Unknown clause type: {type(clause)}")

    def _term_clause_to_expr(self, clause: TermClauseSpec) -> BoolExpr:
        leaf_predicates: list[BoolExpr] = []
        for term in clause.terms:
            leaf_predicates.append(
                self._make_term_leaf(clause.field.field_key, clause.field.value_type, clause.match, term)
            )

        if len(leaf_predicates) == 1:
            return leaf_predicates[0]

        if clause.combine_within_field == "AND":
            return AndExpr(children=leaf_predicates)
        return OrExpr(children=leaf_predicates)

    @staticmethod
    def _make_term_leaf(
        field_key: str, value_type: ValueType, match_mode: str, value: str
    ) -> BoolExpr:
        if match_mode == "PHRASE":
            return PhraseMatchPredicate(field_key=field_key, value=value)
        if match_mode == "EXACT":
            return ExactMatchPredicate(field_key=field_key, value=value)
        # AUTO: TEXT → TermMatch, KEYWORD → ExactMatch
        if value_type == ValueType.TEXT:
            return TermMatchPredicate(field_key=field_key, value=value)
        return ExactMatchPredicate(field_key=field_key, value=value)
