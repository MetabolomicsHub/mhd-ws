from enum import Enum

from mtbls_advanced_search.domain.spec import (
    CharacteristicPairClauseSpec,
    ComparatorClauseSpec,
    DATASET_TARGET,
    DescriptorClauseSpec,
    FieldClauseSpec,
    FieldRef,
    ParameterPairClauseSpec,
    SearchSpec,
    TermClauseSpec,
    ValueType,
)


class Target(str, Enum):
    DATASET = DATASET_TARGET
    METABOLITE = "METABOLITE"


__all__ = [
    "CharacteristicPairClauseSpec",
    "ComparatorClauseSpec",
    "DATASET_TARGET",
    "DescriptorClauseSpec",
    "FieldClauseSpec",
    "FieldRef",
    "ParameterPairClauseSpec",
    "SearchSpec",
    "Target",
    "TermClauseSpec",
    "ValueType",
]
