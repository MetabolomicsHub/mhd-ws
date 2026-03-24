from __future__ import annotations

from mhd_ws.domain.entities.search.dtos import (
    CharacteristicPairClauseDTO,
    ComparatorClauseDTO,
    DescriptorClauseDTO,
    ParameterPairClauseDTO,
    SearchRequestDTO,
    TermClauseDTO,
)
from mhd_ws.domain.entities.search.index_search_spec import (
    CharacteristicPairClauseSpec,
    ComparatorClauseSpec,
    DescriptorClauseSpec,
    FieldClauseSpec,
    FieldRef,
    ParameterPairClauseSpec,
    SearchSpec,
    TermClauseSpec,
)
from mhd_ws.domain.entities.search.registries.models import FieldDef, FieldRegistry


class SearchSpecResolver:
    def __init__(self, field_registry: FieldRegistry) -> None:
        self._registry = field_registry

    def resolve(self, dto: SearchRequestDTO) -> SearchSpec:
        clauses: list[FieldClauseSpec] = []
        for clause in dto.clauses:
            if isinstance(clause, TermClauseDTO):
                clauses.append(self._resolve_term_clause(clause))
            elif isinstance(clause, ComparatorClauseDTO):
                clauses.append(self._resolve_comparator_clause(clause))
            elif isinstance(clause, ParameterPairClauseDTO):
                clauses.append(self._resolve_parameter_pair_clause(clause))
            elif isinstance(clause, DescriptorClauseDTO):
                clauses.append(self._resolve_descriptor_clause(clause))
            elif isinstance(clause, CharacteristicPairClauseDTO):
                clauses.append(self._resolve_characteristic_pair_clause(clause))
        return SearchSpec(
            query_text=dto.query_text,
            inter_field_combiner=dto.inter_field_combiner,
            clauses=clauses,
        )

    def _resolve_term_clause(self, clause: TermClauseDTO) -> TermClauseSpec:
        field_def = self._lookup(clause.field_id)
        self._validate_term_ops(field_def, clause)
        return TermClauseSpec(
            field=FieldRef(
                field_key=field_def.field_key,
                target=field_def.target,
                value_type=field_def.value_type,
            ),
            combine_within_field=clause.op,
            negated=clause.not_,
            terms=clause.terms,
            match=clause.match,
        )

    def _resolve_comparator_clause(
        self, clause: ComparatorClauseDTO
    ) -> ComparatorClauseSpec:
        field_def = self._lookup(clause.field_id)
        self._validate_comparator_ops(field_def, clause)
        return ComparatorClauseSpec(
            field=FieldRef(
                field_key=field_def.field_key,
                target=field_def.target,
                value_type=field_def.value_type,
            ),
            comparator=clause.op,
            negated=clause.not_,
            value=clause.value,
        )

    @staticmethod
    def _resolve_parameter_pair_clause(
        clause: ParameterPairClauseDTO,
    ) -> ParameterPairClauseSpec:
        return ParameterPairClauseSpec(
            type_name=clause.type_name,
            values=clause.values,
            combine_values=clause.op,
            negated=clause.not_,
            include_facet=clause.include_facet,
        )

    @staticmethod
    def _resolve_descriptor_clause(
        clause: DescriptorClauseDTO,
    ) -> DescriptorClauseSpec:
        return DescriptorClauseSpec(
            relationship=clause.relationship,
            names=clause.names,
            combine_names=clause.op,
            negated=clause.not_,
        )

    @staticmethod
    def _resolve_characteristic_pair_clause(
        clause: CharacteristicPairClauseDTO,
    ) -> CharacteristicPairClauseSpec:
        return CharacteristicPairClauseSpec(
            type_name=clause.type_name.strip().lower(),
            values=clause.values,
            combine_values=clause.op,
            negated=clause.not_,
            include_facet=clause.include_facet,
        )

    def _lookup(self, field_id: str) -> FieldDef:
        return self._registry.get_by_id_strict(field_id)

    @staticmethod
    def _validate_term_ops(field_def: FieldDef, clause: TermClauseDTO) -> None:
        if not field_def.ops.allow_terms:
            raise ValueError(
                f"Field {field_def.field_id!r} does not support term queries"
            )
        if clause.match not in field_def.ops.allowed_match_modes:
            raise ValueError(
                f"Match mode {clause.match!r} not allowed for field "
                f"{field_def.field_id!r}; allowed: {field_def.ops.allowed_match_modes}"
            )
        if clause.op not in field_def.ops.allowed_intra_combiners:
            raise ValueError(
                f"Intra-field combiner {clause.op!r} not allowed for field "
                f"{field_def.field_id!r}; allowed: {field_def.ops.allowed_intra_combiners}"
            )

    @staticmethod
    def _validate_comparator_ops(
        field_def: FieldDef, clause: ComparatorClauseDTO
    ) -> None:
        if not field_def.ops.allow_comparators:
            raise ValueError(
                f"Field {field_def.field_id!r} does not support comparator queries"
            )
        if clause.op not in field_def.ops.allowed_comparators:
            raise ValueError(
                f"Comparator {clause.op!r} not allowed for field "
                f"{field_def.field_id!r}; allowed: {field_def.ops.allowed_comparators}"
            )
