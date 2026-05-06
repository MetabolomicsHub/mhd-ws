from __future__ import annotations

from pydantic import BaseModel

from mhd_ws.domain.entities.search.advanced_core.spec import (
    CharacteristicPairClauseSpec,
    ComparatorClauseSpec,
    DescriptorClauseSpec,
    FieldClauseSpec,
    ParameterPairClauseSpec,
    SearchSpec,
    Target,
    TermClauseSpec,
    ValueType,
)
from mhd_ws.domain.entities.search.advanced_core.predicates import (
    AndExpr,
    BoolExpr,
    CharacteristicPairPredicate,
    DescriptorPredicate,
    ExactMatchPredicate,
    NotExpr,
    OrExpr,
    ParameterPairPredicate,
    PhraseMatchPredicate,
    RangePredicate,
    TermMatchPredicate,
)
from mhd_ws.domain.entities.search.advanced_core.plan import (
    DatasetIdConstraint,
    DatasetIdSetOutput,
    DatasetSearchStage,
    MetaboliteIdStage,
    QueryPlan,
)


class PlannerConfig(BaseModel):
    primary_target: Target = Target.DATASET
    primary_index_key: str = "ms-dataset-index"
    join_target: Target | None = Target.METABOLITE
    join_index_key: str | None = "metabolite-index"
    query_text_field_key: str | None = "dataset.search_text"
    join_output_field_key: str = "dataset_id"


class QueryPlanner:
    def __init__(self, config: PlannerConfig | None = None) -> None:
        self._config = config or PlannerConfig()

    def plan(self, spec: SearchSpec) -> QueryPlan:
        dataset_clauses: list[FieldClauseSpec] = []
        metabolite_clauses: list[FieldClauseSpec] = []

        for clause in spec.clauses:
            if isinstance(
                clause,
                (
                    ParameterPairClauseSpec,
                    DescriptorClauseSpec,
                    CharacteristicPairClauseSpec,
                ),
            ):
                dataset_clauses.append(clause)
            elif clause.field.target == self._config.primary_target:
                dataset_clauses.append(clause)
            elif (
                self._config.join_target is not None
                and clause.field.target == self._config.join_target
            ):
                metabolite_clauses.append(clause)
            else:
                dataset_clauses.append(clause)

        dataset_predicates = self._compile_clauses(
            dataset_clauses, spec.inter_field_combiner
        )

        if spec.query_text and self._config.query_text_field_key:
            qt_pred = TermMatchPredicate(
                field_key=self._config.query_text_field_key,
                value=spec.query_text,
            )
            if dataset_predicates.kind == "AND":
                dataset_predicates = AndExpr(
                    children=[*dataset_predicates.children, qt_pred]
                )
            else:
                dataset_predicates = AndExpr(children=[dataset_predicates, qt_pred])

        if metabolite_clauses and self._config.join_index_key is not None:
            met_predicate = self._compile_clauses(
                metabolite_clauses, spec.inter_field_combiner
            )
            met_stage = MetaboliteIdStage(
                index_key=self._config.join_index_key,
                metabolite_predicate=met_predicate,
                output=DatasetIdSetOutput(field_key=self._config.join_output_field_key),
            )
            ds_stage = DatasetSearchStage(
                index_key=self._config.primary_index_key,
                dataset_predicate=dataset_predicates,
                constraints=[DatasetIdConstraint(from_stage_id=met_stage.id)],
            )
            return QueryPlan(stages=[met_stage, ds_stage], final_stage_id=ds_stage.id)

        ds_stage = DatasetSearchStage(
            index_key=self._config.primary_index_key,
            dataset_predicate=dataset_predicates,
        )
        return QueryPlan(stages=[ds_stage], final_stage_id=ds_stage.id)

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
        if isinstance(clause, ParameterPairClauseSpec):
            return ParameterPairPredicate(
                type_name=clause.type_name,
                values=clause.values,
                combine_values=clause.combine_values,
            )
        if isinstance(clause, DescriptorClauseSpec):
            return DescriptorPredicate(
                relationship=clause.relationship,
                names=clause.names,
                combine_names=clause.combine_names,
            )
        if isinstance(clause, CharacteristicPairClauseSpec):
            return CharacteristicPairPredicate(
                type_name=clause.type_name,
                values=clause.values,
                combine_values=clause.combine_values,
            )
        raise TypeError(f"Unknown clause type: {type(clause)}")

    def _term_clause_to_expr(self, clause: TermClauseSpec) -> BoolExpr:
        leaf_predicates: list[BoolExpr] = []
        for term in clause.terms:
            leaf_predicates.append(
                self._make_term_leaf(
                    clause.field.field_key, clause.field.value_type, clause.match, term
                )
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
