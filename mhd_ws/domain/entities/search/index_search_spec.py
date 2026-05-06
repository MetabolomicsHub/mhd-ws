"""Compatibility re-export for advanced-search spec models.

Prefer importing from ``mhd_ws.domain.entities.search.advanced_core`` for any
new advanced-search code. This shim keeps older imports working during the
Phase 1 extraction prep.
"""

from mhd_ws.domain.entities.search.advanced_core.spec import (
    CharacteristicPairClauseSpec,
    ComparatorClauseSpec,
    DescriptorClauseSpec,
    FieldClauseSpec,
    FieldRef,
    ParameterPairClauseSpec,
    SearchSpec,
    Target,
    TermClauseSpec,
    ValueType,
)

__all__ = [
    "CharacteristicPairClauseSpec",
    "ComparatorClauseSpec",
    "DescriptorClauseSpec",
    "FieldClauseSpec",
    "FieldRef",
    "ParameterPairClauseSpec",
    "SearchSpec",
    "Target",
    "TermClauseSpec",
    "ValueType",
]
